fn mekmachine_block_entity(block: &str, entity: &mut Option<(String, horizon_world::nbt::Compound)>) {
    if block == "mekmachine:furnace" && entity.is_none() {
        *entity = Some((block.to_owned(), Default::default()));
    }
}
