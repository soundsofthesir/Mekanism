// The energy and fluid test blocks. A generator and a source move what they hold through
// `mekmachine_engine`, because the helpers can't reach a block during its own tick. A cable and a
// pipe hold nothing, so the helpers' moves between their two neighbours work.
fn mekmachine_transfer(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut horizon_client::containers::ModBlockEntity,
) {
    use horizon_core::geometry::Direction;
    use horizon_world::nbt::{Compound, JavaString, Tag};
    use mekmachine_engine::transfer::{Buffer, Tank};

    const GENERATED: i32 = 40;
    const GENERATOR_CAPACITY: i32 = 1000;
    const GENERATOR_PUSH: i32 = 100;
    const CABLE_RATE: i32 = 25;
    const SOURCE_RATE: i32 = 200;
    const SOURCE_PUSH: i32 = 100;
    const PIPE_RATE: i32 = 50;
    const TANK_CAPACITY: i32 = 1000;

    fn read_energy(nbt: &Compound) -> i32 {
        match nbt.get(&JavaString::from("energy")) {
            Some(Tag::Int(energy)) => *energy,
            _ => 0,
        }
    }
    fn read_tank(nbt: &Compound) -> Tank {
        let entry = match nbt.get(&JavaString::from("fluids")) {
            Some(Tag::List(list)) => list.first(),
            _ => None,
        };
        let (mut fluid, mut amount) = (None, 0);
        if let Some(Tag::Compound(map)) = entry {
            if let Some(Tag::String(name)) = map.get(&JavaString::from("Fluid")) {
                fluid = Some(name.to_string_lossy()).filter(|name| name != "minecraft:empty");
            }
            if let Some(Tag::Int(held)) = map.get(&JavaString::from("Amount")) {
                amount = *held;
            }
        }
        Tank { fluid, amount, capacity: TANK_CAPACITY }
    }
    // Horizon's own layout, so its helpers read what this writes.
    fn write_tank(nbt: &mut Compound, tank: &Tank) {
        let mut map = Compound::new();
        let fluid = tank.fluid.as_deref().unwrap_or("minecraft:empty");
        map.insert(JavaString::from("Fluid"), Tag::String(JavaString::from(fluid)));
        map.insert(JavaString::from("Amount"), Tag::Int(tank.amount));
        nbt.insert(JavaString::from("fluids"), Tag::List(vec![Tag::Compound(map)]));
    }

    let id = entity.id.clone();
    let Some(name) = id.strip_prefix("mekmachine:").filter(|name| *name != "furnace") else {
        return;
    };
    let east = [pos[0] + 1, pos[1], pos[2]];
    let west = [pos[0] - 1, pos[1], pos[2]];
    let dimension = game.dim.id();

    match name {
        "energy_gen" => {
            let mut buffer = Buffer { amount: read_energy(&entity.nbt), capacity: GENERATOR_CAPACITY };
            buffer.generate(GENERATED);
            buffer.push(GENERATOR_PUSH, |amount| {
                game.native_energy_insert(east, Direction::West, amount, false)
            });
            entity.nbt.insert(JavaString::from("energy"), Tag::Int(buffer.amount));
        }
        "energy_cable" => {
            game.native_move_energy(dimension, west, Direction::East, east, Direction::West, CABLE_RATE);
        }
        "water_source" | "lava_source" => {
            let (fluid, to, face) = if name == "water_source" {
                ("minecraft:water", east, Direction::West)
            } else {
                ("minecraft:lava", west, Direction::East)
            };
            let mut tank = read_tank(&entity.nbt);
            tank.fill(fluid, SOURCE_RATE);
            tank.push(SOURCE_PUSH, |fluid, amount| game.native_fluid_insert(to, face, fluid, amount));
            write_tank(&mut entity.nbt, &tank);
        }
        "fluid_pipe" => {
            game.native_move_fluids(dimension, west, Direction::East, east, Direction::West, PIPE_RATE);
        }
        _ => {}
    }

    // MEKMACHINE_TRANSFER_TRACE names a file for one line per block per tick.
    let Ok(path) = std::env::var("MEKMACHINE_TRANSFER_TRACE") else {
        return;
    };
    let tank = read_tank(&entity.nbt);
    let line = format!(
        "{}|{},{},{}|{}|{}|{}|{}\n",
        game.world.game_time,
        pos[0],
        pos[1],
        pos[2],
        name,
        read_energy(&entity.nbt),
        tank.fluid.as_deref().unwrap_or("-"),
        tank.amount,
    );
    use std::io::Write;
    if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(path) {
        let _ = file.write_all(line.as_bytes());
    }
}
