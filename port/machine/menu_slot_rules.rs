// `UpgradeInventorySlot.input`: a machine's upgrade slot takes only an upgrade this port's machines
// support. This compiles in `horizon-client`'s menu code, which can't see the game module, so its
// names are written out here. They match `mek::UPGRADE_*` and `Game::mek_has_machine_screen`.
fn mekmachine_menu_slot_rules(
    menu: &str,
    slot: usize,
    stack: &horizon_client::items::ItemStack,
    may_place: &mut bool,
) {
    const UPGRADE_INPUT: usize = 3;
    const MACHINES: [&str; 4] = [
        "mekanism:enrichment_chamber",
        "mekanism:crusher",
        "mekanism:energized_smelter",
        "mekanism:chemical_oxidizer",
    ];
    if slot != UPGRADE_INPUT || !MACHINES.contains(&menu) {
        return;
    }
    let kind = stack.data().and_then(|data| data.other("mekanism:upgrade_type"));
    let supported = matches!(
        kind,
        Some(horizon_world::nbt::Tag::String(kind))
            if matches!(kind.to_string_lossy().as_str(), "mekanism:speed" | "mekanism:energy")
    );
    *may_place = supported && &*stack.item == "mekanism:upgrade";
}
