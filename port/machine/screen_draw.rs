// A plain version of `GuiElectricMachine`: progress, energy, and each side's setting.
fn mekmachine_screen_draw(
    game: &crate::game::Game<'_>,
    block: &str,
    data: &[i32],
    batch: &mut horizon_client::hud::HudBatch,
    origin: [f32; 2],
) {
    use crate::game::mek;
    if !crate::game::Game::mek_is_machine(block) {
        return;
    }
    const DARK: u32 = 0xFF55_5555;
    const GREEN: u32 = 0xFF3C_C83C;
    const WHITE: u32 = 0xFFFF_FFFF;
    const ITEM_COLOURS: [u32; 4] = [0xFF55_5555, 0xFFC8_3C3C, 0xFF3C_50C8, 0xFF3C_C83C];
    const ENERGY_COLOURS: [u32; 2] = [0xFF55_5555, 0xFF3C_C83C];
    let [x, y] = origin;
    let get = |slot: usize| data.get(slot).copied().unwrap_or(0);
    let share = |value: i32, total: i32| (value as f32 / total.max(1) as f32).clamp(0.0, 1.0);

    let [bar_x, bar_y, bar_w, bar_h] = mek::PROGRESS_BAR;
    game.native_fill(batch, [x + bar_x, y + bar_y, bar_w, bar_h], DARK);
    let done = share(get(mek::DATA_PROGRESS), get(mek::DATA_TICKS));
    game.native_fill(batch, [x + bar_x, y + bar_y, bar_w * done, bar_h], WHITE);

    let [power_x, power_y, power_w, power_h] = mek::POWER_BAR;
    game.native_fill(batch, [x + power_x, y + power_y, power_w, power_h], DARK);
    let filled = power_h * share(get(mek::DATA_ENERGY), get(mek::DATA_CAPACITY));
    game.native_fill(batch, [x + power_x, y + power_y + power_h - filled, power_w, filled], GREEN);

    for index in 0..6 {
        let items = mek::unpack_side(get(mek::DATA_ITEM_SIDES), index);
        let energy = mek::unpack_side(get(mek::DATA_ENERGY_SIDES), index) & 1;
        let [item_x, item_y] = mek::side_button(0, index);
        let [energy_x, energy_y] = mek::side_button(1, index);
        let size = mek::SIDE_BUTTON_SIZE;
        game.native_fill(batch, [x + item_x, y + item_y, size, size], ITEM_COLOURS[items]);
        game.native_fill(batch, [x + energy_x, y + energy_y, size, size], ENERGY_COLOURS[energy]);
    }
}
