// The tick of the machines in `process_table.rs`, through `mekmachine_engine::advanced`.
fn mekmachine_advanced(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut horizon_client::containers::ModBlockEntity,
) {
    use crate::game::{chem, mek};
    use horizon_client::items::ItemStack;
    use horizon_world::nbt::{JavaString, Tag};
    use mekmachine_engine::advanced::{self, AdvancedMachine, Need, ProcessRecipe, ProcessRecipes, Rolls};
    use mekmachine_engine::chemical::Tank;
    use mekmachine_engine::furnace::Stack;
    use mekmachine_engine::process_table::{self as table, Extra, ProcessDef};
    use std::{cell::RefCell, collections::HashMap};

    let Some(def) = table::process(&entity.id) else {
        return;
    };
    const INPUT: usize = 0;
    const OUTPUT: usize = 1;

    thread_local! {
        /// Each machine kind's recipes by input item, since an ingredient is slow to parse every tick.
        /// A change in the number of recipes clears it.
        static BY_ITEM: RefCell<HashMap<(&'static str, String), (usize, Vec<usize>)>> = RefCell::new(HashMap::new());
    }

    struct Lookup<'a, 'g> {
        game: &'a crate::game::Game<'g>,
        def: &'static ProcessDef,
    }
    impl Lookup<'_, '_> {
        fn parse(&self, recipe: &horizon_client::mod_api::CustomRecipe, extra: Option<&Stack>, chemical: Option<&str>) -> Option<ProcessRecipe> {
            let json = &recipe.json;
            let (wanted, need) = match self.def.recipes {
                "mekanism:combining" => {
                    let second = &json["extra_input"];
                    let extra = extra?;
                    let held = ItemStack::new(&extra.item, extra.count);
                    if !self.game.native_recipe_ingredient(&second["ingredient"])?.test(&held) {
                        return None;
                    }
                    (&json["main_input"], Need::Item(second["count"].as_u64().unwrap_or(1) as u32))
                }
                "mekanism:sawing" => (&json["input"], Need::Nothing),
                _ => {
                    let gas = &json["chemical_input"];
                    let ingredient = &gas["ingredient"];
                    if chemical.is_some_and(|held| !self.game.native_recipe_chemical_matches(ingredient, held)) {
                        return None;
                    }
                    let amount = gas["amount"].as_i64().unwrap_or(1);
                    let per_tick = json["per_tick_usage"].as_bool().unwrap_or(false);
                    (&json["item_input"], if per_tick { Need::PerTick(amount) } else { Need::AtEnd(amount) })
                }
            };
            let made = if self.def.recipes == "mekanism:sawing" { &json["main_output"] } else { &json["output"] };
            let output = (!made.is_null()).then(|| self.game.native_recipe_result(made)).flatten();
            let byproduct = self.game.native_recipe_result(&json["secondary_output"]).map(|out| {
                (Stack::new(&out.item, out.count as u32), json["secondary_chance"].as_f64().unwrap_or(0.0))
            });
            Some(ProcessRecipe {
                id: recipe.id.clone(),
                input_count: wanted["count"].as_u64().unwrap_or(1) as u32,
                need,
                output: output.map(|out| Stack::new(&out.item, out.count as u32)),
                byproduct,
            })
        }
    }
    impl ProcessRecipes for Lookup<'_, '_> {
        fn find(&self, input: &Stack, extra: Option<&Stack>, chemical: Option<&str>) -> Option<ProcessRecipe> {
            let recipes = self.game.native_recipes_of_type(self.def.recipes);
            let key = (self.def.block, input.item.clone());
            let known = BY_ITEM.with_borrow(|cache| cache.get(&key).filter(|(count, _)| *count == recipes.len()).map(|(_, list)| list.clone()));
            let matching = known.unwrap_or_else(|| {
                let stack = ItemStack::new(&input.item, 1);
                let list: Vec<usize> = recipes
                    .iter()
                    .enumerate()
                    .filter(|(_, recipe)| {
                        self.game
                            .native_recipe_ingredient(&recipe.json[mek::process_input_key(self.def.recipes)]["ingredient"])
                            .is_some_and(|ingredient| ingredient.test(&stack))
                    })
                    .map(|(index, _)| index)
                    .collect();
                BY_ITEM.with_borrow_mut(|cache| cache.insert(key, (recipes.len(), list.clone())));
                list
            });
            matching.into_iter().find_map(|index| self.parse(&recipes[index], extra, chemical))
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
    game.mek_register_extra_items(def);
    game.mek_tick_upgrades(entity);
    game.mek_eject_items(pos, entity, OUTPUT);
    if def.extra == Extra::ByProduct {
        game.mek_eject_items(pos, entity, mek::ADVANCED_SECONDARY);
    }
    game.mek_fill_energy_slot(entity, mek::ENERGY_SLOT, i64::MAX);

    let mut tank = if def.tank > 0 { chem::read_tank(&entity.nbt, def.tank) } else { Tank::new(0, None) };
    // `ChemicalInventorySlot.fillTankOrConvert`: one item, only if all of its chemical fits.
    if def.extra == Extra::Conversion
        && let Some(item) = entity.items[mek::ADVANCED_SECONDARY].clone()
        && let Some((id, amount)) = game.mek_chemical_from(&item, def, entity.items[INPUT].as_ref())
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
    let energy_per_tick = upgrades.energy_per_tick(def.usage);
    let was_active = int("active_state") != 0;
    let mut machine = AdvancedMachine {
        input: stack(entity.items.get(INPUT)),
        extra: if def.extra == Extra::Conversion { None } else { stack(entity.items.get(mek::ADVANCED_SECONDARY)) },
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
        let rolls = mek::process_rolls(entity, def, advanced::chemical_mean(upgrades.speed));
        machine.tick(&Lookup { game: &*game, def }, rolls, energy_per_tick, advanced::BASE_TICKS, ticks);
    } else {
        machine.active = false;
    }

    let fields = &mut **entity;
    store(&mut fields.items[INPUT], &machine.input);
    store(&mut fields.items[OUTPUT], &machine.output);
    if def.extra != Extra::Conversion {
        store(&mut fields.items[mek::ADVANCED_SECONDARY], &machine.extra);
    }
    let nbt = &mut fields.nbt;
    if def.tank > 0 {
        chem::write_tank(nbt, &machine.tank);
    }
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
    data[chem::DATA_CHEMICAL_KIND] = machine.tank.held.as_ref().map_or(0, |held| chem::chemical_kind(&held.id));
    mek::keep_recalculated(&fields.data, &mut data);
    fields.data = data;
    if machine.active != was_active {
        const UPDATE_ALL: i32 = 3;
        game.native_set_block_property_with(pos, "active", if machine.active { "true" } else { "false" }, UPDATE_ALL);
    }
}
