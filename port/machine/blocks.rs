fn mekmachine_blocks(blocks: &mut Vec<horizon_mods::content::Block>) {
    blocks.push(horizon_mods::content::Block {
        id: "mekmachine:furnace".into(),
        template: "minecraft:furnace".into(),
        item: true,
        ..Default::default()
    });
    for name in [
        "energy_gen",
        "energy_cell",
        "energy_cell_east",
        "energy_cable",
        "water_source",
        "lava_source",
        "tank",
        "fluid_pipe",
    ] {
        blocks.push(horizon_mods::content::Block {
            id: format!("mekmachine:{name}"),
            template: "minecraft:stone".into(),
            item: true,
            ..Default::default()
        });
    }
}
