// Each frame, before anything draws: slots that only show inside a window move there, and the window
// keeps a copy of what it draws over them.
fn mekmachine_frame(game: &mut crate::game::Game<'_>) {
    game.mek_screen_frame();
}
