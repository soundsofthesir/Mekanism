fn mekmachine_block_entity(block: &str, entity: &mut Option<(String, horizon_world::nbt::Compound)>) {
    if block.starts_with("mekmachine:") && entity.is_none() {
        *entity = Some((block.to_owned(), Default::default()));
    }
}
