fn mekmachine_fluids(block: &str, fluids: &mut Option<horizon_client::containers::ModFluidTanks>) {
    use horizon_client::containers::ModFluidTanks;
    const TANK: usize = 0;
    let tank = |inputs: Vec<usize>| ModFluidTanks {
        tanks: vec![1000],
        faces: std::array::from_fn(|_| vec![TANK]),
        inputs,
        outputs: vec![TANK],
    };
    match block {
        "mekmachine:water_source" | "mekmachine:lava_source" => *fluids = Some(tank(vec![])),
        "mekmachine:tank" => *fluids = Some(tank(vec![TANK])),
        _ => {}
    }
}
