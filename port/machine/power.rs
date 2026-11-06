// The Energy Cube, Universal Cable and Heat Generator.
fn mekmachine_power(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut horizon_client::containers::ModBlockEntity,
) {
    use crate::game::mek;
    use horizon_world::nbt::{Compound, JavaString, Tag};
    use mekmachine_engine::heat_generator::{ENERGY_CAPACITY, HeatGenerator, Surroundings};

    fn read_lava(nbt: &Compound) -> i64 {
        let Some(Tag::List(list)) = nbt.get(&JavaString::from("fluids")) else {
            return 0;
        };
        let Some(Tag::Compound(tank)) = list.first() else {
            return 0;
        };
        match tank.get(&JavaString::from("Amount")) {
            Some(Tag::Int(amount)) => i64::from(*amount),
            _ => 0,
        }
    }
    fn write_lava(nbt: &mut Compound, amount: i64) {
        let mut tank = Compound::new();
        let fluid = if amount > 0 { "minecraft:lava" } else { "minecraft:empty" };
        tank.insert(JavaString::from("Fluid"), Tag::String(JavaString::from(fluid)));
        tank.insert(JavaString::from("Amount"), Tag::Int(amount as i32));
        nbt.insert(JavaString::from("fluids"), Tag::List(vec![Tag::Compound(tank)]));
    }

    match entity.id.as_str() {
        mek::CABLE => game.mek_register_cable(pos),
        mek::CUBE => {
            let saved = &entity.nbt;
            let ejects = matches!(
                saved.get(&JavaString::from("component_config")),
                Some(Tag::Compound(config)) if matches!(
                    config.get(&JavaString::from("eject0")),
                    Some(Tag::Byte(1))
                )
            );
            let held = mek::energy_of(saved);
            if !ejects || held <= 0 {
                return;
            }
            let facing = game.mek_facing(pos);
            let sides: Vec<_> = mek::DIRECTIONS
                .into_iter()
                .filter(|side| {
                    let index = mek::relative_index(facing, *side);
                    mek::side_value(saved, mek::ENERGY_CONFIG, index) == mek::SIDE_OUTPUT
                })
                .collect();
            let sent = game.mek_emit(pos, &sides, held.min(i64::from(mek::CUBE_RATE)));
            entity.nbt.insert(JavaString::from("energy"), Tag::Int((held - sent) as i32));
        }
        mek::GENERATOR => {
            let here = game.mek_ambient(pos);
            let ambient = mek::DIRECTIONS.map(|side| game.mek_ambient(mek::offset(pos, side)));
            let lava_sides = mek::DIRECTIONS
                .into_iter()
                .filter(|side| game.mek_is_lava(mek::offset(pos, *side)))
                .count() as i32;
            let heat = match entity.nbt.get(&JavaString::from("heat")) {
                Some(Tag::Double(bits)) => f64::from_bits(*bits),
                _ => here * 10.0,
            };
            let was_active = matches!(
                entity.nbt.get(&JavaString::from("active_state")),
                Some(Tag::Int(1))
            );
            let held = mek::energy_of(&entity.nbt);
            // `TileEntityGenerator`: it sends what it held before making more, out of its front.
            let front = game.mek_facing(pos);
            let sent = game.mek_emit(pos, &[front], held);
            let mut generator = HeatGenerator {
                heat,
                energy: held - sent,
                lava: read_lava(&entity.nbt),
                active: was_active,
            };
            generator.tick(&Surroundings { ambient, lava_sides }, here);
            debug_assert!(generator.energy <= ENERGY_CAPACITY);
            let nbt = &mut entity.nbt;
            nbt.insert(JavaString::from("heat"), Tag::Double(generator.heat.to_bits()));
            nbt.insert(JavaString::from("energy"), Tag::Int(generator.energy as i32));
            nbt.insert(JavaString::from("active_state"), Tag::Int(i32::from(generator.active)));
            write_lava(nbt, generator.lava);
            if generator.active != was_active {
                const UPDATE_ALL: i32 = 3;
                let active = if generator.active { "true" } else { "false" };
                game.native_set_block_property_with(pos, "active", active, UPDATE_ALL);
            }
        }
        _ => {}
    }
}
