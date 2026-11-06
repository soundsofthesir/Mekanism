// A press on a machine's screen. It runs before the game's slots, so the side config window can cover
// them, and it sends its own button clicks.
fn mekmachine_screen_press(
    game: &crate::game::Game<'_>,
    screen: &horizon_client::mod_api::NativeScreenView<'_>,
    button: i32,
    modifiers: u32,
    canceled: &mut bool,
) {
    use crate::game::gui;
    use mekmachine_engine::gui_layout::{Click, Press, press};
    const LEFT_BUTTON: i32 = 0;
    const RIGHT_BUTTON: i32 = 1;
    const SHIFT: u32 = 1;
    if !screen.menu.is_some_and(crate::game::Game::mek_is_machine) {
        return;
    }
    let click = match button {
        RIGHT_BUTTON => Click::Right,
        LEFT_BUTTON if modifiers & SHIFT != 0 => Click::Shift,
        LEFT_BUTTON => Click::Left,
        _ => return,
    };
    let origin = gui::origin();
    let at = [screen.mouse[0] - origin[0], screen.mouse[1] - origin[1]];
    match press(at, gui::open_kind(), click) {
        Press::Pass => return,
        Press::Nothing => {}
        Press::OpenWindow => gui::set_open_kind(Some(mekmachine_engine::gui_layout::ITEM_KIND)),
        Press::CloseWindow => gui::set_open_kind(None),
        Press::ShowKind(kind) => gui::set_open_kind(Some(kind)),
        Press::Button(id) => game.mek_send_menu_button(id),
    }
    *canceled = true;
}
