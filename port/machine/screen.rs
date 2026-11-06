fn mekmachine_screen(block: &str, screen: &mut Option<horizon_client::mod_api::NativeScreen>) {
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
    if !crate::game::Game::mek_is_machine(block) {
        return;
    }
    // Slot positions from `TileEntityElectricMachine`'s inventory.
    *screen = Some(horizon_client::mod_api::NativeScreen {
        width: 176.0,
        height: 166.0,
        // The energy item slot is left out until something it charges from is ported.
        slots: vec![Some([64.0, 17.0]), Some([116.0, 35.0]), None],
        inventory_y: 84.0,
        inventory_x: 8.0,
        own_labels: false,
        own_background: false,
    });
}
