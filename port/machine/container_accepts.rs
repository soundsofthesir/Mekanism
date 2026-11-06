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
    if entity.id == mek::GENERATOR {
        // `FluidFuelInventorySlot`: only what burns. Its right side is the energy slot's.
        let right = face.is_some_and(|face| mek::relative_index(game.mek_facing(pos), face) == mek::RIGHT_INDEX);
        if right || game.mek_fuel_value(&stack.item).burn_time <= 0 {
            *cancel = true;
        }
        return;
    }
    if !crate::game::Game::mek_is_machine(&entity.id) {
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
