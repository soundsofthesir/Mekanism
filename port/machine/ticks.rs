fn mekmachine_ticks(block: &str, ticks: &mut bool) {
    if block == "mekmachine:furnace" {
        *ticks = true;
    }
}
