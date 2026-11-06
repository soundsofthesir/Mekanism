fn mekmachine_block_entity(block: &str, entity: &mut Option<(String, horizon_world::nbt::Compound)>) {
    let machine = matches!(block, "mekanism:enrichment_chamber" | "mekanism:crusher" | "mekanism:energized_smelter");
    if (machine || block.starts_with("mekmachine:")) && entity.is_none() {
        *entity = Some((block.to_owned(), Default::default()));
    }
}
