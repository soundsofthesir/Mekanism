fn mekmachine_container(block: &str, container: &mut Option<horizon_client::containers::ModContainer>) {
    if matches!(block, "mekanism:enrichment_chamber" | "mekanism:crusher" | "mekanism:energized_smelter") {
        const INPUT: usize = 0;
        const OUTPUT: usize = 1;
        const ENERGY: usize = 2;
        *container = Some(horizon_client::containers::ModContainer {
            slots: 3,
            // Every side reaches every slot here; `container_accepts` applies the saved config.
            faces: std::array::from_fn(|_| vec![INPUT, OUTPUT, ENERGY]),
            inputs: vec![INPUT, ENERGY],
            outputs: vec![OUTPUT],
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
