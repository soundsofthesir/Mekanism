fn mekmachine_screen_post(
    game: &crate::game::Game<'_>,
    batch: &mut horizon_client::hud::HudBatch,
    screen: &horizon_client::mod_api::NativeScreenView<'_>,
) {
    if !screen.menu.is_some_and(crate::game::Game::mek_has_machine_screen) {
        return;
    }
    game.gui_side_window(batch);
}
