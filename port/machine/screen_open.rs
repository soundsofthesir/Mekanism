// The real mod's window closes with its screen.
fn mekmachine_screen_open(screen: &horizon_client::mod_api::NativeScreenView<'_>) {
    let _ = screen;
    crate::game::gui::set_open_kind(None);
}
