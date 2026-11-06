fn mekmachine_menu_button(entity: &mut horizon_client::containers::ModBlockEntity, id: i32) {
    use crate::game::mek;
    if !crate::game::Game::mek_is_machine(&entity.id) || !(0..2 * mek::BUTTONS_PER_ROW).contains(&id) {
        return;
    }
    let index = (id % mek::BUTTONS_PER_ROW) as usize;
    let nbt = &mut entity.nbt;
    if id < mek::BUTTONS_PER_ROW {
        mek::cycle_side(nbt, mek::ITEM_CONFIG, index, &mek::ITEM_SIDE_CYCLE);
    } else {
        mek::cycle_side(nbt, mek::ENERGY_CONFIG, index, &mek::ENERGY_SIDE_CYCLE);
    }
}
