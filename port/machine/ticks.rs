fn mekmachine_ticks(block: &str, ticks: &mut bool) {
    let machine = crate::game::mek::has_block_entity(block);
    if machine || block.starts_with("mekmachine:") {
        *ticks = true;
    }
}
// Rebuild stamp: 423044505
