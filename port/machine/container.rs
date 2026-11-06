fn mekmachine_container(block: &str, container: &mut Option<horizon_client::containers::ModContainer>) {
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
