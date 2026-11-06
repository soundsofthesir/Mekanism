fn mekmachine_screen_click(block: &str, at: [f32; 2], button: &mut Option<i32>) {
    use crate::game::mek;
    if !crate::game::Game::mek_is_machine(block) {
        return;
    }
    for row in 0..2 {
        for index in 0..6 {
            let [x, y] = mek::side_button(row, index);
            let size = mek::SIDE_BUTTON_SIZE;
            if at[0] >= x && at[0] < x + size && at[1] >= y && at[1] < y + size {
                *button = Some(row as i32 * mek::BUTTONS_PER_ROW + index as i32);
            }
        }
    }
}
