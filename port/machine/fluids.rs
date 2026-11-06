fn mekmachine_fluids(block: &str, fluids: &mut Option<horizon_client::containers::ModFluidTanks>) {
    use horizon_client::containers::ModFluidTanks;
    const TANK: usize = 0;
    let tank_of = |capacity: i32| ModFluidTanks {
        tanks: vec![capacity],
        faces: std::array::from_fn(|_| vec![TANK]),
        inputs: vec![TANK],
        outputs: vec![],
    };
    let tank = |inputs: Vec<usize>| ModFluidTanks {
        tanks: vec![1000],
        faces: std::array::from_fn(|_| vec![TANK]),
        inputs,
        outputs: vec![TANK],
    };
    match block {
        crate::game::mek::GENERATOR => *fluids = Some(tank_of(crate::game::mek::LAVA_TANK_CAPACITY)),
        "mekmachine:water_source" | "mekmachine:lava_source" => *fluids = Some(tank(vec![])),
        "mekmachine:tank" => *fluids = Some(tank(vec![TANK])),
        _ => {}
    }
}
