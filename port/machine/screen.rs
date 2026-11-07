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
        // The energy slot and the slot that drains the tank are drawn, but stay out of the menu
        // until what they use is ported.
        let [input, _drain, _energy] = layout::OXIDIZER_SLOTS;
        *screen = Some(horizon_client::mod_api::NativeScreen {
            width: layout::SCREEN_WIDTH,
            height: layout::SCREEN_HEIGHT,
            slots: vec![Some(input), None, None, Some(layout::OFF_SCREEN), Some(layout::OFF_SCREEN)],
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
    let [input, output, _energy] = layout::CHAMBER_SLOTS;
    *screen = Some(horizon_client::mod_api::NativeScreen {
        width: layout::SCREEN_WIDTH,
        height: layout::SCREEN_HEIGHT,
        // The energy item slot is left out until something it charges from is ported.
        slots: vec![Some(input), Some(output), None, Some(layout::OFF_SCREEN), Some(layout::OFF_SCREEN)],
        inventory_y: layout::INVENTORY[1],
        inventory_x: layout::INVENTORY[0],
        own_labels: true,
        own_background: true,
    });
}
