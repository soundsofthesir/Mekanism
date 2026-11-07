fn mekmachine_blocks(blocks: &mut Vec<horizon_mods::content::Block>) {
    blocks.push(horizon_mods::content::Block {
        id: "mekmachine:furnace".into(),
        template: "minecraft:furnace".into(),
        item: true,
        ..Default::default()
    });
    // Mekanism's own blocks. The content mod `mekanism` holds their models and textures.
    let shared = mekmachine_engine::process_table::PROCESS.iter().map(|def| def.block.to_owned());
    let chambers = ["enrichment_chamber", "crusher", "energized_smelter"].map(|name| format!("mekanism:{name}"));
    for id in chambers.into_iter().chain(shared) {
        blocks.push(horizon_mods::content::Block {
            id,
            // A furnace's template opens a menu and faces like one. Its `lit` goes unused.
            template: "minecraft:furnace".into(),
            state_properties: [("active".to_owned(), horizon_mods::content::StateProperty::Boolean)]
                .into_iter()
                .collect(),
            item: true,
            ..Default::default()
        });
    }
    // The carried content has no Fluid Tank, whose real model is a custom one, so it has no look yet.
    for tier in mekmachine_engine::tiers::TIERS {
        blocks.push(horizon_mods::content::Block {
            id: format!("mekanism:{tier}_fluid_tank"),
            template: "minecraft:glass".into(),
            item: true,
            ..Default::default()
        });
    }
    // A cube opens a menu like a furnace too, so the mod declares it and the carried one goes.
    for tier in mekmachine_engine::tiers::TIERS {
        blocks.push(horizon_mods::content::Block {
            id: format!("mekanism:{tier}_energy_cube"),
            template: "minecraft:furnace".into(),
            item: true,
            ..Default::default()
        });
    }
    blocks.push(horizon_mods::content::Block {
        id: crate::game::chem::OXIDIZER.into(),
        template: "minecraft:furnace".into(),
        item: true,
        ..Default::default()
    });
    blocks.push(horizon_mods::content::Block {
        id: "mekanismgenerators:heat_generator".into(),
        template: "minecraft:furnace".into(),
        state_properties: [("active".to_owned(), horizon_mods::content::StateProperty::Boolean)]
            .into_iter()
            .collect(),
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
