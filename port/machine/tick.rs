// The glue between the game and `mekmachine_engine`: this compiles inside the game, so it reads the
// recipe, item and fuel tables that the mod API doesn't offer.
fn mekmachine_tick(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut horizon_client::containers::ModBlockEntity,
) {
    use horizon_client::items::ItemStack;
    use horizon_world::nbt::{Compound, JavaString, Tag};
    use mekmachine_engine::furnace::{Burn, Cook, Facts, Furnace, Stack};

    const SMELTING: &str = "minecraft:smelting";
    const LAST_INPUT: &str = "last_input";
    /// The vanilla furnace to compare with stands this far along x.
    const VANILLA_OFFSET: i32 = 1;

    if entity.id != "mekmachine:furnace" {
        return;
    }

    struct Tables<'a> {
        recipes: &'a horizon_client::crafting::Recipes,
        items: &'a horizon_client::items::Items,
        providers: &'a horizon_client::providers::Providers,
    }
    impl Facts for Tables<'_> {
        fn cook(&self, input: &Stack) -> Option<Cook> {
            let cooking = self.recipes.cook(SMELTING, &ItemStack::new(&input.item, input.count))?;
            Some(Cook {
                result: Stack::new(&cooking.result.item, cooking.result.count as u32),
                time: cooking.time,
            })
        }
        fn burn(&self, fuel: &Stack) -> Burn {
            let stack = ItemStack::new(&fuel.item, fuel.count);
            Burn {
                time: self.providers.burn_time(self.items, &stack, false),
                speed: self.providers.speed(self.items, &stack, false),
                remainder: self
                    .items
                    .get(&fuel.item)
                    .and_then(|item| item.crafting_remainder.clone()),
            }
        }
        fn max_stack(&self, item: &str) -> u32 {
            self.items.get(item).map_or(64, |item| item.max_stack)
        }
    }

    fn stack(slot: Option<&Option<ItemStack>>) -> Option<Stack> {
        slot?.as_ref().map(|s| Stack::new(&s.item, s.count as u32))
    }
    fn int(nbt: &Compound, key: &str) -> i32 {
        match nbt.get(&JavaString::from(key)) {
            Some(Tag::Int(value)) => *value,
            _ => 0,
        }
    }
    // Keeps a stack's components while only its count changes.
    fn store(slot: &mut Option<ItemStack>, new: &Option<Stack>) {
        match (slot.as_mut(), new) {
            (Some(old), Some(new)) if *old.item == *new.item => old.count = new.count as _,
            (_, Some(new)) => *slot = Some(ItemStack::new(&new.item, new.count)),
            (_, None) => *slot = None,
        }
    }

    let tables = match &game.world_tables {
        Some(tables) => (&tables.recipes, &tables.items),
        None => (game.res.recipes(), game.res.items()),
    };
    let tables = Tables { recipes: tables.0, items: tables.1, providers: game.res.providers() };

    let speed = match entity.nbt.get(&JavaString::from("speed_multiplier")) {
        Some(Tag::Float(bits)) => f32::from_bits(*bits),
        _ => 1.0,
    };
    let mut furnace = Furnace {
        input: stack(entity.items.first()),
        fuel: stack(entity.items.get(1)),
        output: stack(entity.items.get(2)),
        lit_remaining: int(&entity.nbt, "lit_time_remaining"),
        lit_total: int(&entity.nbt, "lit_total_time"),
        cook_time: int(&entity.nbt, "cooking_time_spent"),
        cook_total: int(&entity.nbt, "cooking_total_time"),
        speed,
    };
    // A hopper, a menu or a command changed the input since the last tick: vanilla's `setItem`.
    let last = match entity.nbt.get(&JavaString::from(LAST_INPUT)) {
        Some(Tag::String(item)) => Some(Stack::new(&item.to_string_lossy(), 1)),
        _ => None,
    };
    if last.as_ref().map(|s| &s.item) != furnace.input.as_ref().map(|s| &s.item) {
        furnace.input_changed(&tables, last.as_ref());
    }

    let tick = furnace.tick(&tables);

    let fields = &mut **entity;
    fields.items.resize(3, None);
    store(&mut fields.items[0], &furnace.input);
    store(&mut fields.items[1], &furnace.fuel);
    store(&mut fields.items[2], &furnace.output);
    for (key, value) in [
        ("lit_time_remaining", furnace.lit_remaining),
        ("lit_total_time", furnace.lit_total),
        ("cooking_time_spent", furnace.cook_time),
        ("cooking_total_time", furnace.cook_total),
    ] {
        fields.nbt.insert(JavaString::from(key), Tag::Int(value));
    }
    fields.nbt.insert(JavaString::from("speed_multiplier"), Tag::Float(furnace.speed.to_bits()));
    match &furnace.input {
        Some(input) => {
            fields.nbt.insert(JavaString::from(LAST_INPUT), Tag::String(JavaString::from(input.item.as_str())));
        }
        None => {
            fields.nbt.remove(&JavaString::from(LAST_INPUT));
        }
    }
    // The furnace menu's data slots, in `AbstractFurnaceBlockEntity`'s order.
    fields.data = vec![furnace.lit_remaining, furnace.lit_total, furnace.cook_time, furnace.cook_total];

    if let Some(lit) = tick.lit_changed {
        const UPDATE_ALL: i32 = 3;
        game.native_set_block_property_with(pos, "lit", if lit { "true" } else { "false" }, UPDATE_ALL);
    }
    for drop in tick.drops {
        game.campfire_drop((pos[0], pos[1], pos[2]), ItemStack::new(&drop.item, drop.count));
    }

    // MEKMACHINE_TRACE names a file for one line a tick: this furnace, then the vanilla one beside it,
    // which ticks first when it was placed first.
    let Ok(path) = std::env::var("MEKMACHINE_TRACE") else {
        return;
    };
    let vanilla_pos = (pos[0] + VANILLA_OFFSET, pos[1], pos[2]);
    let Some(horizon_client::containers::BlockEntity::Furnace(vanilla)) =
        game.world.block_entities.get(&vanilla_pos)
    else {
        return;
    };
    let vanilla = Furnace {
        input: stack(vanilla.items.first()),
        fuel: stack(vanilla.items.get(1)),
        output: stack(vanilla.items.get(2)),
        lit_remaining: vanilla.lit_remaining,
        lit_total: vanilla.lit_total,
        cook_time: vanilla.cooking_timer,
        cook_total: vanilla.cooking_total,
        speed: vanilla.speed,
    };
    let lit_of = |at: [i32; 3]| game.native_block_property(at, "lit").unwrap_or_default();
    let line = format!(
        "{}|{},{},{}|{} {}|{} {}\n",
        game.world.game_time,
        pos[0],
        pos[1],
        pos[2],
        furnace.trace(),
        lit_of(pos),
        vanilla.trace(),
        lit_of([vanilla_pos.0, vanilla_pos.1, vanilla_pos.2]),
    );
    use std::io::Write;
    if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(path) {
        let _ = file.write_all(line.as_bytes());
    }
}
