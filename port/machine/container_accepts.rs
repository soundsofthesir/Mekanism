// What a hopper may put in a machine: only through a side set to input, only into the input slot,
// and only what has a recipe (`InputInventorySlot.at(containsRecipe)`).
fn mekmachine_container_accepts(
    game: &crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &horizon_client::containers::ModBlockEntity,
    slot: usize,
    stack: &horizon_client::items::ItemStack,
    face: Option<horizon_core::geometry::Direction>,
    cancel: &mut bool,
) {
    use crate::game::mek;
    const INPUT: usize = 0;
    if mek::is_cube(&entity.id) {
        // `EnergyInventorySlot`: only what it can charge or discharge.
        let usable = match slot {
            mek::CUBE_DISCHARGE => matches!(&*stack.item, mek::ENERGY_TABLET | "minecraft:redstone" | "minecraft:redstone_block"),
            _ => &*stack.item == mek::ENERGY_TABLET,
        };
        if !usable {
            *cancel = true;
        }
        return;
    }
    if entity.id == mek::GENERATOR {
        // `FluidFuelInventorySlot`: only what burns. Its right side is the energy slot's.
        let right = face.is_some_and(|face| mek::relative_index(game.mek_facing(pos), face) == mek::RIGHT_INDEX);
        if right || game.mek_fuel_value(&stack.item).burn_time <= 0 {
            *cancel = true;
        }
        return;
    }
    if !crate::game::Game::mek_is_machine(&entity.id) && entity.id != crate::game::chem::OXIDIZER {
        return;
    }
    if slot == mek::UPGRADE_INPUT {
        // `UpgradeInventorySlot.input`: by hand only, and only what this port's machines support.
        if face.is_some() || game.mek_upgrade_kind(stack).is_none() {
            *cancel = true;
        }
        return;
    }
    if slot == mek::ADVANCED_SECONDARY
        && let Some(def) = mekmachine_engine::process_table::process(&entity.id)
    {
        // By a side set to input, and only what `ChemicalInventorySlot.fillOrConvert` or a recipe takes.
        let side_is_input = face.is_none_or(|face| {
            let index = mek::relative_index(game.mek_facing(pos), face);
            mek::side_value(&entity.nbt, mek::ITEM_CONFIG, index) == mek::SIDE_INPUT
        });
        if !side_is_input || !game.mek_extra_items(def).iter().any(|item| *item == *stack.item) {
            *cancel = true;
        }
        return;
    }
    if slot == mek::ENERGY_SLOT {
        // By a side set to energy, and only what `menu_slot_rules` lets a player place.
        let side_is_energy = face.is_none_or(|face| {
            let index = mek::relative_index(game.mek_facing(pos), face);
            mek::side_value(&entity.nbt, mek::ITEM_CONFIG, index) == mek::SIDE_ENERGY
        });
        let usable = matches!(&*stack.item, mek::ENERGY_TABLET | "minecraft:redstone" | "minecraft:redstone_block");
        if !side_is_energy || !usable {
            *cancel = true;
        }
        return;
    }
    let side_is_input = face.is_none_or(|face| {
        let index = mek::relative_index(game.mek_facing(pos), face);
        mek::side_value(&entity.nbt, mek::ITEM_CONFIG, index) == mek::SIDE_INPUT
    });
    if slot != INPUT || !side_is_input || !game.mek_has_recipe(&entity.id, stack) {
        *cancel = true;
    }
}
