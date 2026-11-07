fn mekmachine_menu_button(entity: &mut horizon_client::containers::ModBlockEntity, id: i32) {
    use crate::game::mek;
    use crate::game::chem;
    use mekmachine_engine::gui_layout::{CHEMICAL_KIND, CLEAR_BASE, EJECT_BASE, ENERGY_KIND, RIGHT_CLICK_BASE, SHIFT_CLICK_BASE};
    const KINDS: i32 = 3;
    if !crate::game::Game::mek_has_machine_screen(&entity.id) {
        return;
    }
    let nbt = &mut entity.nbt;
    let config_of = |kind: usize| {
        match kind {
            ENERGY_KIND => (mek::ENERGY_CONFIG, &mek::ENERGY_SIDE_CYCLE[..], mek::ENERGY_EJECT),
            CHEMICAL_KIND => (chem::CHEMICAL_CONFIG, &mek::CHEMICAL_SIDE_CYCLE[..], chem::EJECT),
            _ => (mek::ITEM_CONFIG, &mek::ITEM_SIDE_CYCLE[..], mek::ITEM_EJECT),
        }
    };
    let row = mek::BUTTONS_PER_ROW;
    let rows = KINDS * row;
    if (0..rows).contains(&id) {
        let (config, cycle, _) = config_of((id / row) as usize);
        mek::cycle_side(nbt, config, (id % row) as usize, cycle, 1);
    } else if (RIGHT_CLICK_BASE..RIGHT_CLICK_BASE + rows).contains(&id) {
        let offset = id - RIGHT_CLICK_BASE;
        let (config, cycle, _) = config_of((offset / row) as usize);
        mek::cycle_side(nbt, config, (offset % row) as usize, cycle, cycle.len() - 1);
    } else if (SHIFT_CLICK_BASE..SHIFT_CLICK_BASE + rows).contains(&id) {
        let offset = id - SHIFT_CLICK_BASE;
        let (config, _, _) = config_of((offset / row) as usize);
        mek::set_side(nbt, config, (offset % row) as usize, 0);
    } else if (EJECT_BASE..EJECT_BASE + KINDS).contains(&id) {
        let (_, _, eject) = config_of((id - EJECT_BASE) as usize);
        mek::toggle_eject(nbt, eject);
    } else if (CLEAR_BASE..CLEAR_BASE + KINDS).contains(&id) {
        let (config, _, _) = config_of((id - CLEAR_BASE) as usize);
        for index in 0..mek::SIDES {
            mek::set_side(nbt, config, index, 0);
        }
    }
}
