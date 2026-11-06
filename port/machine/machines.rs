// Mekanism's one-input electric machines, through `mekmachine_engine::recipe_machine`. Recipes of
// Mekanism's own types come from the content mod, and the Energized Smelter uses vanilla's.
fn mekmachine_machines(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut horizon_client::containers::ModBlockEntity,
) {
    use horizon_client::items::ItemStack;
    use horizon_world::nbt::{JavaString, Tag};
    use mekmachine_engine::furnace::Stack;
    use mekmachine_engine::recipe_machine::{Machine, Recipe, Recipes};
    use std::{cell::RefCell, collections::HashMap};

    const INPUT: usize = 0;
    const OUTPUT: usize = 1;
    const SLOTS: usize = 3;
    const VANILLA_SMELTING: &str = "minecraft:smelting";

    let (kind, usage) = match entity.id.as_str() {
        "mekanism:enrichment_chamber" => ("mekanism:enriching", 5),
        "mekanism:crusher" => ("mekanism:crushing", 8),
        "mekanism:energized_smelter" => (VANILLA_SMELTING, 5),
        _ => return,
    };

    thread_local! {
        // What each item matches, by recipe type. A `/reload` gives the table a new address, and
        // that drops the type's answers.
        static FOUND: RefCell<HashMap<&'static str, (usize, HashMap<String, Option<Recipe>>)>> =
            RefCell::new(HashMap::new());
    }

    struct Lookup<'a, 'g> {
        game: &'a crate::game::Game<'g>,
        kind: &'static str,
    }
    impl Lookup<'_, '_> {
        fn smelt(&self, input: &Stack) -> Option<Recipe> {
            let recipes = match &self.game.world_tables {
                Some(tables) => &tables.recipes,
                None => self.game.res.recipes(),
            };
            let cooking = recipes.cook(VANILLA_SMELTING, &ItemStack::new(&input.item, input.count))?;
            Some(Recipe {
                id: cooking.id.clone(),
                input_count: 1,
                output: Stack::new(&cooking.result.item, cooking.result.count as u32),
            })
        }
        fn scan(&self, input: &Stack) -> Option<Recipe> {
            let stack = ItemStack::new(&input.item, input.count);
            self.game.native_recipes_of_type(self.kind).iter().find_map(|recipe| {
                let wanted = &recipe.json["input"];
                let ingredient = self.game.native_recipe_ingredient(&wanted["ingredient"])?;
                if !ingredient.test(&stack) {
                    return None;
                }
                let output = self.game.native_recipe_result(&recipe.json["output"])?;
                Some(Recipe {
                    id: recipe.id.clone(),
                    input_count: wanted["count"].as_u64().unwrap_or(1) as u32,
                    output: Stack::new(&output.item, output.count as u32),
                })
            })
        }
    }
    impl Recipes for Lookup<'_, '_> {
        fn find(&self, input: &Stack) -> Option<Recipe> {
            if self.kind == VANILLA_SMELTING {
                return self.smelt(input);
            }
            let table = self.game.native_recipes_of_type(self.kind).as_ptr() as usize;
            FOUND.with_borrow_mut(|found| {
                let entry = found.entry(self.kind).or_insert_with(|| (table, HashMap::new()));
                if entry.0 != table {
                    *entry = (table, HashMap::new());
                }
                entry.1.entry(input.item.clone()).or_insert_with(|| self.scan(input)).clone()
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
    let int = |key: &str| match entity.nbt.get(&JavaString::from(key)) {
        Some(Tag::Int(value)) => *value,
        _ => 0,
    };

    let mut machine = Machine {
        input: stack(entity.items.get(INPUT)),
        output: stack(entity.items.get(OUTPUT)),
        energy: i64::from(int("energy")),
        progress: int("progress"),
        active: int("active_state") != 0,
        recipe: match entity.nbt.get(&JavaString::from("recipe")) {
            Some(Tag::String(id)) => Some(id.to_string_lossy()),
            _ => None,
        },
    };
    let was_active = machine.active;
    machine.tick(&Lookup { game: &*game, kind }, usage);

    let fields = &mut **entity;
    fields.items.resize(SLOTS, None);
    store(&mut fields.items[INPUT], &machine.input);
    store(&mut fields.items[OUTPUT], &machine.output);
    fields.nbt.insert(JavaString::from("energy"), Tag::Int(machine.energy as i32));
    fields.nbt.insert(JavaString::from("progress"), Tag::Int(machine.progress));
    fields.nbt.insert(JavaString::from("active_state"), Tag::Int(i32::from(machine.active)));
    if let Some(recipe) = &machine.recipe {
        fields.nbt.insert(JavaString::from("recipe"), Tag::String(JavaString::from(recipe.as_str())));
    }
    use crate::game::mek;
    let item_sides = mek::pack_sides(&fields.nbt, mek::ITEM_CONFIG, &mek::ITEM_SIDE_CYCLE);
    let energy_sides = mek::pack_sides(&fields.nbt, mek::ENERGY_CONFIG, &mek::ENERGY_SIDE_CYCLE);
    let mut data = vec![0; 6];
    data[mek::DATA_PROGRESS] = machine.progress;
    data[mek::DATA_TICKS] = mekmachine_engine::recipe_machine::TICKS_REQUIRED;
    data[mek::DATA_ENERGY] = machine.energy as i32;
    data[mek::DATA_CAPACITY] = (usage * 4) as i32;
    data[mek::DATA_ITEM_SIDES] = item_sides;
    data[mek::DATA_ENERGY_SIDES] = energy_sides;
    fields.data = data;
    if machine.active != was_active {
        const UPDATE_ALL: i32 = 3;
        let active = if machine.active { "true" } else { "false" };
        game.native_set_block_property_with(pos, "active", active, UPDATE_ALL);
    }
}
