fn mekmachine_screen(block: &str, screen: &mut Option<horizon_client::mod_api::NativeScreen>) {
    use mekmachine_engine::gui_layout as layout;
    if block == crate::game::mek::GENERATOR {
        // The fuel slot's position in `TileEntityHeatGenerator`.
        *screen = Some(horizon_client::mod_api::NativeScreen {
            width: 176.0,
            height: 166.0,
            slots: vec![Some([17.0, 35.0])],
            inventory_y: 84.0,
            inventory_x: 8.0,
            own_labels: false,
            own_background: false,
        });
        return;
    }
    if block == crate::game::chem::OXIDIZER {
        // The slot that drains the tank is drawn, but stays out of the menu until a chemical item is ported.
        let [input, _drain, energy] = layout::OXIDIZER_SLOTS;
        *screen = Some(horizon_client::mod_api::NativeScreen {
            width: layout::SCREEN_WIDTH,
            height: layout::SCREEN_HEIGHT,
            slots: vec![Some(input), None, Some(energy), Some(layout::OFF_SCREEN), Some(layout::OFF_SCREEN)],
            inventory_y: layout::INVENTORY[1],
            inventory_x: layout::INVENTORY[0],
            own_labels: true,
            own_background: true,
        });
        return;
    }
    if crate::game::mek::is_cube(block) {
        let [discharge, charge] = layout::CUBE_SLOTS;
        *screen = Some(horizon_client::mod_api::NativeScreen {
            width: layout::SCREEN_WIDTH,
            height: layout::SCREEN_HEIGHT,
            slots: vec![Some(discharge), Some(charge)],
            inventory_y: layout::INVENTORY[1],
            inventory_x: layout::INVENTORY[0],
            own_labels: true,
            own_background: true,
        });
        return;
    }
    if !crate::game::Game::mek_is_machine(block) {
        return;
    }
    // Slot positions from `TileEntityElectricMachine`'s inventory.
    let [input, output, energy] = layout::CHAMBER_SLOTS;
    *screen = Some(horizon_client::mod_api::NativeScreen {
        width: layout::SCREEN_WIDTH,
        height: layout::SCREEN_HEIGHT,
        slots: vec![Some(input), Some(output), Some(energy), Some(layout::OFF_SCREEN), Some(layout::OFF_SCREEN)],
        inventory_y: layout::INVENTORY[1],
        inventory_x: layout::INVENTORY[0],
        own_labels: true,
        own_background: true,
    });
}
