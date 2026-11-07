// The Osmium Compressor's tick, through `mekmachine_engine::advanced`.
fn mekmachine_advanced(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut horizon_client::containers::ModBlockEntity,
) {
    use crate::game::{chem, mek};
    use horizon_client::items::ItemStack;
    use horizon_world::nbt::{JavaString, Tag};
    use mekmachine_engine::advanced::{self, AdvancedMachine, ChemicalRecipe, ChemicalRecipes};
    use mekmachine_engine::furnace::Stack;

    if entity.id != mek::COMPRESSOR {
        return;
    }
    const INPUT: usize = 0;
    const OUTPUT: usize = 1;
    const KIND: &str = "mekanism:compressing";

    struct Compressing<'a, 'g> {
        game: &'a crate::game::Game<'g>,
    }
    impl ChemicalRecipes for Compressing<'_, '_> {
        fn find(&self, input: &Stack, chemical: Option<&str>) -> Option<ChemicalRecipe> {
            let stack = ItemStack::new(&input.item, input.count);
            self.game.native_recipes_of_type(KIND).iter().find_map(|recipe| {
                let wanted = &recipe.json["item_input"];
                if !self.game.native_recipe_ingredient(&wanted["ingredient"])?.test(&stack) {
                    return None;
                }
                let gas = &recipe.json["chemical_input"];
                let id = gas["ingredient"].as_str()?;
                if chemical.is_some_and(|held| held != id) {
                    return None;
                }
                let output = self.game.native_recipe_result(&recipe.json["output"])?;
                Some(ChemicalRecipe {
                    id: recipe.id.clone(),
                    input_count: wanted["count"].as_u64().unwrap_or(1) as u32,
                    chemical: id.to_owned(),
                    amount: gas["amount"].as_i64().unwrap_or(1),
                    output: Stack::new(&output.item, output.count as u32),
                })
            })
        }
        fn max_stack(&self, item: &str) -> u32 {
            let items = match &self.game.world_tables {
                Some(tables) => &tables.items,
                None => self.game.res.items(),
            };
            items.get(item).map_or(64, |item| item.max_stack)
        }
    }

    fn stack(slot: Option<&Option<ItemStack>>) -> Option<Stack> {
        slot?.as_ref().map(|s| Stack::new(&s.item, s.count as u32))
    }
    fn store(slot: &mut Option<ItemStack>, new: &Option<Stack>) {
        match (slot.as_mut(), new) {
            (Some(old), Some(new)) if *old.item == *new.item => old.count = new.count as _,
            (_, Some(new)) => *slot = Some(ItemStack::new(&new.item, new.count)),
            (_, None) => *slot = None,
        }
    }

    if entity.items.len() < mek::ADVANCED_SLOTS {
        entity.items.resize(mek::ADVANCED_SLOTS, None);
    }
    game.mek_tick_upgrades(entity);
    game.mek_eject_items(pos, entity, OUTPUT);
    game.mek_fill_energy_slot(entity, mek::ENERGY_SLOT, i64::MAX);

    let mut tank = chem::read_tank(&entity.nbt, advanced::TANK_CAPACITY);
    // `ChemicalInventorySlot.fillTankOrConvert`: one item, only if all of its chemical fits.
    if let Some(item) = entity.items[mek::ADVANCED_SECONDARY].clone()
        && let Some((id, amount)) = game.mek_chemical_from(&item)
        && tank.room(&id) >= amount
    {
        tank.insert(&id, amount);
        entity.items[mek::ADVANCED_SECONDARY] =
            (item.count > 1).then(|| ItemStack { count: item.count - 1, ..item.clone() });
    }

    let int = |key: &str| match entity.nbt.get(&JavaString::from(key)) {
        Some(Tag::Int(value)) => *value,
        _ => 0,
    };
    let upgrades = mek::upgrades_of(&entity.nbt);
    let ticks = upgrades.ticks(advanced::BASE_TICKS);
    let energy_per_tick = upgrades.energy_per_tick(mek::COMPRESSOR_USAGE);
    let was_active = int("active_state") != 0;
    let mut machine = AdvancedMachine {
        input: stack(entity.items.get(INPUT)),
        output: stack(entity.items.get(OUTPUT)),
        tank,
        energy: i64::from(int("energy")),
        progress: int("progress"),
        used_so_far: int("used_so_far"),
        active: was_active,
        recipe: match entity.nbt.get(&JavaString::from("recipe")) {
            Some(Tag::String(id)) => Some(id.to_string_lossy()),
            _ => None,
        },
    };
    if game.mek_may_run(pos, &entity.nbt) {
        machine.tick(&Compressing { game: &*game }, energy_per_tick, advanced::BASE_TICKS, ticks);
    } else {
        machine.active = false;
    }

    let fields = &mut **entity;
    store(&mut fields.items[INPUT], &machine.input);
    store(&mut fields.items[OUTPUT], &machine.output);
    let nbt = &mut fields.nbt;
    chem::write_tank(nbt, &machine.tank);
    nbt.insert(JavaString::from("energy"), Tag::Int(machine.energy as i32));
    nbt.insert(JavaString::from("progress"), Tag::Int(machine.progress));
    nbt.insert(JavaString::from("used_so_far"), Tag::Int(machine.used_so_far));
    nbt.insert(JavaString::from("active_state"), Tag::Int(i32::from(machine.active)));
    if let Some(recipe) = &machine.recipe {
        nbt.insert(JavaString::from("recipe"), Tag::String(JavaString::from(recipe.as_str())));
    }
    let capacity = crate::game::Game::mek_capacity(&fields.id, &fields.nbt, &fields.data);
    let using = if machine.active { energy_per_tick } else { 0 };
    let mut data = vec![0; mek::DATA_SLOTS];
    mek::fill_menu(&mut data, &fields.nbt, machine.energy, capacity, using);
    data[mek::DATA_PROGRESS] = machine.progress;
    data[mek::DATA_TICKS] = ticks;
    data[mek::DATA_ITEM_SIDES] = mek::pack_sides(&fields.nbt, mek::ITEM_CONFIG, &mek::ITEM_SIDE_CYCLE);
    data[mek::DATA_ENERGY_SIDES] = mek::pack_sides(&fields.nbt, mek::ENERGY_CONFIG, &mek::ENERGY_SIDE_CYCLE);
    data[chem::DATA_CHEMICAL_SIDES] = mek::pack_sides(&fields.nbt, chem::CHEMICAL_CONFIG, &mek::CHEMICAL_SIDE_CYCLE);
    data[chem::DATA_CHEMICAL] = machine.tank.held.as_ref().map_or(0, |held| held.amount as i32);
    mek::keep_recalculated(&fields.data, &mut data);
    fields.data = data;
    if machine.active != was_active {
        const UPDATE_ALL: i32 = 3;
        game.native_set_block_property_with(pos, "active", if machine.active { "true" } else { "false" }, UPDATE_ALL);
    }
}
