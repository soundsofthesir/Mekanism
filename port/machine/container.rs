fn mekmachine_container(block: &str, container: &mut Option<horizon_client::containers::ModContainer>) {
    if matches!(block, "mekanism:enrichment_chamber" | "mekanism:crusher" | "mekanism:energized_smelter") {
        const INPUT: usize = 0;
        const OUTPUT: usize = 1;
        const ENERGY: usize = 2;
        *container = Some(horizon_client::containers::ModContainer {
            slots: crate::game::mek::MACHINE_SLOTS,
            // Every side reaches every slot here; `container_accepts` applies the saved config.
            faces: std::array::from_fn(|_| vec![INPUT, OUTPUT, ENERGY]),
            inputs: vec![INPUT, ENERGY],
            outputs: vec![OUTPUT],
            menu: Some(block.to_owned()),
        });
        return;
    }
    if block == crate::game::mek::COMPRESSOR {
        use crate::game::mek::{ADVANCED_SECONDARY, ADVANCED_SLOTS, ENERGY_SLOT};
        const INPUT: usize = 0;
        const OUTPUT: usize = 1;
        *container = Some(horizon_client::containers::ModContainer {
            slots: ADVANCED_SLOTS,
            faces: std::array::from_fn(|_| vec![INPUT, OUTPUT, ENERGY_SLOT, ADVANCED_SECONDARY]),
            inputs: vec![INPUT, ENERGY_SLOT, ADVANCED_SECONDARY],
            outputs: vec![OUTPUT],
            menu: Some(block.to_owned()),
        });
        return;
    }
    if crate::game::mek::is_cube(block) {
        use crate::game::mek::{CUBE_CHARGE, CUBE_DISCHARGE, CUBE_SLOTS};
        *container = Some(horizon_client::containers::ModContainer {
            slots: CUBE_SLOTS,
            faces: std::array::from_fn(|_| vec![CUBE_DISCHARGE, CUBE_CHARGE]),
            inputs: vec![CUBE_DISCHARGE, CUBE_CHARGE],
            outputs: vec![],
            menu: Some(block.to_owned()),
        });
        return;
    }
    if block == crate::game::chem::OXIDIZER {
        const INPUT: usize = 0;
        const CHEMICAL_ITEM: usize = 1;
        const ENERGY: usize = 2;
        *container = Some(horizon_client::containers::ModContainer {
            slots: crate::game::mek::MACHINE_SLOTS,
            faces: std::array::from_fn(|_| vec![INPUT, CHEMICAL_ITEM, ENERGY]),
            inputs: vec![INPUT, ENERGY],
            outputs: vec![CHEMICAL_ITEM],
            menu: Some(block.to_owned()),
        });
        return;
    }
    if block == crate::game::mek::GENERATOR {
        const FUEL: usize = 0;
        *container = Some(horizon_client::containers::ModContainer {
            slots: 1,
            faces: std::array::from_fn(|_| vec![FUEL]),
            inputs: vec![FUEL],
            outputs: vec![],
            menu: Some(block.to_owned()),
        });
        return;
    }
    if block != "mekmachine:furnace" {
        return;
    }
    const INPUT: usize = 0;
    const FUEL: usize = 1;
    const OUTPUT: usize = 2;
    // Faces by `Direction` number: down, up, north, south, west, east (`AbstractFurnaceBlockEntity`).
    *container = Some(horizon_client::containers::ModContainer {
        slots: 3,
        faces: [
            vec![OUTPUT, FUEL],
            vec![INPUT],
            vec![FUEL],
            vec![FUEL],
            vec![FUEL],
            vec![FUEL],
        ],
        inputs: vec![INPUT, FUEL],
        outputs: vec![OUTPUT],
        menu: Some("minecraft:furnace".to_owned()),
    });
}
