fn mekmachine_screen_tooltip(
    game: &crate::game::Game<'_>,
    block: &str,
    data: &[i32],
    at: [f32; 2],
    lines: &mut Vec<String>,
) {
    if crate::game::Game::mek_has_machine_screen(block) {
        game.gui_tooltip(block, data, at, lines);
    }
}
