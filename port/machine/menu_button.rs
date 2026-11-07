fn mekmachine_menu_button(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut horizon_client::containers::ModBlockEntity,
    id: i32,
) {
    use crate::game::mek;
    use crate::game::chem;
    use mekmachine_engine::gui_layout::{
        CHEMICAL_KIND, CLEAR_BASE, EJECT_BASE, ENERGY_KIND, REDSTONE_NEXT, REDSTONE_PREVIOUS, RIGHT_CLICK_BASE,
        SHIFT_CLICK_BASE, UNINSTALL_ALL, UNINSTALL_ONE, UPGRADE_KINDS,
    };
    const KINDS: i32 = 3;
    if !crate::game::Game::mek_has_machine_screen(&entity.id) {
        return;
    }
    let _ = pos;
    let kinds = UPGRADE_KINDS as i32;
    if (UNINSTALL_ONE..UNINSTALL_ONE + kinds).contains(&id) {
        game.mek_uninstall(entity, (id - UNINSTALL_ONE) as usize, false);
        return;
    }
    if (UNINSTALL_ALL..UNINSTALL_ALL + kinds).contains(&id) {
        game.mek_uninstall(entity, (id - UNINSTALL_ALL) as usize, true);
        return;
    }
    let cube = mek::is_cube(&entity.id);
    let nbt = &mut entity.nbt;
    if id == REDSTONE_NEXT || id == REDSTONE_PREVIOUS {
        mek::cycle_control(nbt, id == REDSTONE_NEXT);
        return;
    }
    let config_of = |kind: usize| {
        match kind {
            ENERGY_KIND if cube => (mek::ENERGY_CONFIG, &mek::CUBE_SIDE_CYCLE[..], mek::ENERGY_EJECT),
            _ if cube => (mek::ITEM_CONFIG, &mek::CUBE_SIDE_CYCLE[..], mek::ITEM_EJECT),
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
