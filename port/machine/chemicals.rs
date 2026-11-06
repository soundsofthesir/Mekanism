// The Chemical Oxidizer, Pressurized Tube and Chemical Tank's ticks.
fn mekmachine_chemicals(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut horizon_client::containers::ModBlockEntity,
) {
    use crate::game::chem;
    use horizon_client::items::ItemStack;
    use horizon_world::nbt::{Compound, JavaString, Tag};
    use mekmachine_engine::chemical::{self, Chem, Tank};
    use mekmachine_engine::furnace::Stack;
    use mekmachine_engine::recipe_machine::{Machine, Recipe, Recipes};

    match entity.id.as_str() {
        chem::TUBE => {
            game.chem_register_tube(pos);
            return;
        }
        chem::TANK => {
            let mut tank = chem::read_tank(&entity.nbt, chemical::BASIC_TANK_CAPACITY);
            game.chem_eject(pos, &entity.nbt, &mut tank, chemical::BASIC_TANK_RATE);
            chem::write_tank(&mut entity.nbt, &tank);
            return;
        }
        chem::OXIDIZER => {}
        _ => return,
    }

    struct Oxidizing<'a, 'g> {
        game: &'a crate::game::Game<'g>,
    }
    impl Recipes<Chem> for Oxidizing<'_, '_> {
        fn find(&self, input: &Stack) -> Option<Recipe<Chem>> {
            let stack = ItemStack::new(&input.item, input.count);
            self.game.native_recipes_of_type("mekanism:oxidizing").iter().find_map(|recipe| {
                let wanted = &recipe.json["input"];
                let ingredient = self.game.native_recipe_ingredient(&wanted["ingredient"])?;
                if !ingredient.test(&stack) {
                    return None;
                }
                let output = &recipe.json["output"];
                Some(Recipe {
                    id: recipe.id.clone(),
                    input_count: wanted["count"].as_u64().unwrap_or(1) as u32,
                    output: Chem::new(output["id"].as_str()?, output["amount"].as_i64()?),
                })
            })
        }
        fn max_stack(&self, _item: &str) -> u32 {
            64
        }
    }

    const INPUT: usize = 0;
    const SLOTS: usize = 3;
    let stack = entity
        .items
        .get(INPUT)
        .and_then(|slot| slot.as_ref())
        .map(|slot| Stack::new(&slot.item, slot.count as u32));
    let int = |key: &str| match entity.nbt.get(&JavaString::from(key)) {
        Some(Tag::Int(value)) => *value,
        _ => 0,
    };
    let mut tank: Tank = chem::read_tank(&entity.nbt, chemical::OXIDIZER_CAPACITY);
    // `TileEntityMekanism` ticks its ejector first, so what a recipe makes leaves a tick later.
    game.chem_eject(pos, &entity.nbt, &mut tank, chemical::AUTO_EJECT_RATE);
    let mut machine = Machine {
        input: stack,
        output: tank,
        energy: i64::from(int("energy")),
        progress: int("progress"),
        active: int("active_state") != 0,
        recipe: match entity.nbt.get(&JavaString::from("recipe")) {
            Some(Tag::String(id)) => Some(id.to_string_lossy()),
            _ => None,
        },
    };
    let before = machine.input.as_ref().map_or(0, |input| input.count);
    machine.tick_for(&Oxidizing { game: &*game }, chemical::OXIDIZER_USAGE, chemical::OXIDIZER_TICKS);
    let finished = machine.input.as_ref().map_or(0, |input| input.count) < before;

    let fields = &mut **entity;
    fields.items.resize(SLOTS, None);
    match (&machine.input, fields.items[INPUT].as_mut()) {
        (Some(input), Some(slot)) => slot.count = input.count as _,
        _ => fields.items[INPUT] = None,
    }
    let nbt = &mut fields.nbt;
    chem::write_tank(nbt, &machine.output);
    nbt.insert(JavaString::from("energy"), Tag::Int(machine.energy as i32));
    nbt.insert(JavaString::from("progress"), Tag::Int(machine.progress));
    nbt.insert(JavaString::from("active_state"), Tag::Int(i32::from(machine.active)));
    if let Some(recipe) = &machine.recipe {
        nbt.insert(JavaString::from("recipe"), Tag::String(JavaString::from(recipe.as_str())));
    }
    if let (true, Some(recipe)) = (finished, &machine.recipe) {
        // `recipes_used`: how many times each recipe finished, for the experience it gives.
        let used = nbt
            .entry(JavaString::from("recipes_used"))
            .or_insert_with(|| Tag::Compound(Compound::new()));
        if let Tag::Compound(used) = used {
            let count = match used.get(&JavaString::from(recipe.as_str())) {
                Some(Tag::Int(value)) => *value,
                _ => 0,
            };
            used.insert(JavaString::from(recipe.as_str()), Tag::Int(count + 1));
        }
    }
    let mut data = vec![0; 8];
    data[crate::game::mek::DATA_PROGRESS] = machine.progress;
    data[crate::game::mek::DATA_TICKS] = chemical::OXIDIZER_TICKS;
    data[crate::game::mek::DATA_ENERGY] = machine.energy as i32;
    data[crate::game::mek::DATA_CAPACITY] = chemical::OXIDIZER_USAGE as i32 * 4;
    data[chem::DATA_CHEMICAL] = machine.output.held.as_ref().map_or(0, |held| held.amount as i32);
    fields.data = data;
}
