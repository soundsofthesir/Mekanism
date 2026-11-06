fn mekmachine_blocks(blocks: &mut Vec<horizon_mods::content::Block>) {
    blocks.push(horizon_mods::content::Block {
        id: "mekmachine:furnace".into(),
        template: "minecraft:furnace".into(),
        item: true,
        ..Default::default()
    });
}
