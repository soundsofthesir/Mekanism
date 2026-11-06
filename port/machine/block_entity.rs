fn mekmachine_block_entity(block: &str, entity: &mut Option<(String, horizon_world::nbt::Compound)>) {
    let machine = crate::game::mek::has_block_entity(block);
    if (machine || block.starts_with("mekmachine:")) && entity.is_none() {
        *entity = Some((block.to_owned(), crate::game::mek::default_config(block)));
    }
}
