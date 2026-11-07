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
    const MACHINES: [&str; 5] = [
        "mekanism:osmium_compressor",
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
    if !MACHINES.contains(&menu) {
        return;
    }
    if slot == ENERGY_SLOT {
        // `EnergyInventorySlot.canFillOrConvert`, for the only energy item and conversions ported.
        *may_place = matches!(&*stack.item, "mekanism:energy_tablet" | "minecraft:redstone" | "minecraft:redstone_block");
        return;
    }
    if menu == "mekanism:osmium_compressor" && slot == 5 {
        // `ChemicalInventorySlot.fillOrConvert`, with what `#c:ingots/osmium` and its block's tag hold.
        *may_place = matches!(&*stack.item, "mekanism:ingot_osmium" | "mekanism:block_osmium");
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
