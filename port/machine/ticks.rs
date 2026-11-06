fn mekmachine_ticks(block: &str, ticks: &mut bool) {
    if block.starts_with("mekmachine:") {
        *ticks = true;
    }
}
