fn mekmachine_energy(block: &str, energy: &mut Option<horizon_client::containers::ModEnergyBuffer>) {
    use horizon_client::containers::ModEnergyBuffer;
    // Faces by `Direction` number: down, up, north, south, west, east.
    const WEST_ONLY: [bool; 6] = [false, false, false, false, true, false];
    const EAST_ONLY: [bool; 6] = [false, false, false, false, false, true];
    const NONE: [bool; 6] = [false; 6];
    const ALL: [bool; 6] = [true; 6];
    let cell = |insert_faces| ModEnergyBuffer {
        capacity: 500,
        max_insert: 30,
        max_extract: 0,
        insert_faces,
        extract_faces: NONE,
    };
    // `AttributeEnergy.STORAGE_MULTIPLIER` times the usage. A recording of the real mod shows a
    // chamber with no upgrades charging to 20.
    const STORAGE_MULTIPLIER: i32 = 4;
    let machine = |usage: i32| ModEnergyBuffer {
        capacity: usage * STORAGE_MULTIPLIER,
        max_insert: usage * STORAGE_MULTIPLIER,
        max_extract: 0,
        insert_faces: ALL,
        extract_faces: NONE,
    };
    match block {
        "mekanism:enrichment_chamber" | "mekanism:energized_smelter" => *energy = Some(machine(5)),
        "mekanism:crusher" => *energy = Some(machine(8)),
        "mekmachine:energy_gen" => {
            *energy = Some(ModEnergyBuffer {
                capacity: 1000,
                max_insert: 0,
                max_extract: 100,
                insert_faces: NONE,
                extract_faces: ALL,
            });
        }
        "mekmachine:energy_cell" => *energy = Some(cell(WEST_ONLY)),
        "mekmachine:energy_cell_east" => *energy = Some(cell(EAST_ONLY)),
        _ => {}
    }
}
