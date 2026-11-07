// `UpgradeInventorySlot.input`: a machine's upgrade slot takes only an upgrade this port's machines
// support. This compiles in `horizon-client`'s menu code, which can't see the game module, so its
// names are written out here. They match `mek::UPGRADE_*` and `Game::mek_has_machine_screen`.
fn mekmachine_menu_slot_rules(
    menu: &str,
    slot: usize,
    stack: &horizon_client::items::ItemStack,
    may_place: &mut bool,
) {
    const ENERGY_SLOT: usize = 2;
    const UPGRADE_INPUT: usize = 3;
    use std::collections::{BTreeMap, BTreeSet};
    use std::sync::Mutex;
    // A slot rule can't reach the game or the engine crate, and what a machine's extra slot takes comes
    // from recipes and tags. So `Game::mek_register_extra_items` calls this once per item with a menu
    // of this prefix, on the machine's first tick. A client of a server has no machine to tick, so its
    // table is empty and it leaves the choice to the server.
    const REGISTER: &str = "mekmachine:extra_items:";
    static EXTRA_ITEMS: Mutex<BTreeMap<String, BTreeSet<String>>> = Mutex::new(BTreeMap::new());
    if let Some(block) = menu.strip_prefix(REGISTER) {
        if let Ok(mut table) = EXTRA_ITEMS.lock() {
            table.entry(block.to_owned()).or_default().insert(stack.item.to_string());
        }
        return;
    }
    // `process_table.rs`'s machines.
    const PROCESS: [&str; 6] = [
        "mekanism:osmium_compressor",
        "mekanism:purification_chamber",
        "mekanism:chemical_injection_chamber",
        "mekanism:combiner",
        "mekanism:precision_sawmill",
        "mekanism:metallurgic_infuser",
    ];
    const MACHINES: [&str; 4] = [
        "mekanism:enrichment_chamber",
        "mekanism:crusher",
        "mekanism:energized_smelter",
        "mekanism:chemical_oxidizer",
    ];
    if menu.starts_with("mekanism:") && menu.ends_with("_energy_cube") {
        *may_place = match slot {
            0 => matches!(&*stack.item, "mekanism:energy_tablet" | "minecraft:redstone" | "minecraft:redstone_block"),
            _ => &*stack.item == "mekanism:energy_tablet",
        };
        return;
    }
    if !MACHINES.contains(&menu) && !PROCESS.contains(&menu) {
        return;
    }
    if slot == ENERGY_SLOT {
        // `EnergyInventorySlot.canFillOrConvert`, for the only energy item and conversions ported.
        *may_place = matches!(&*stack.item, "mekanism:energy_tablet" | "minecraft:redstone" | "minecraft:redstone_block");
        return;
    }
    if slot == 5 && PROCESS.contains(&menu) {
        if let Some(allowed) = EXTRA_ITEMS.lock().ok().and_then(|table| table.get(menu).cloned()) {
            *may_place = allowed.contains(&*stack.item);
        }
        return;
    }
    if slot != UPGRADE_INPUT {
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
