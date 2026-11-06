fn mekmachine_ticks(block: &str, ticks: &mut bool) {
    let machine = matches!(block, "mekanism:enrichment_chamber" | "mekanism:crusher" | "mekanism:energized_smelter");
    if machine || block.starts_with("mekmachine:") {
        *ticks = true;
    }
}
