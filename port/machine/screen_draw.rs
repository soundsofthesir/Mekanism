// Mekanism's machine screens, with its own art for the electric machines. The generator's is still plain.
fn mekmachine_screen_draw(
    game: &crate::game::Game<'_>,
    block: &str,
    data: &[i32],
    batch: &mut horizon_client::hud::HudBatch,
    origin: [f32; 2],
) {
    use crate::game::mek;
    if block == mek::GENERATOR {
        const DARK: u32 = 0xFF55_5555;
        const ORANGE: u32 = 0xFFE0_7A1E;
        const GREEN: u32 = 0xFF3C_C83C;
        const TEXT: u32 = 0x40_40_40;
        let [x, y] = origin;
        let value = |slot: usize| data.get(slot).copied().unwrap_or(0);
        let share = |value: i32, total: i32| (value as f32 / total as f32).clamp(0.0, 1.0);
        let bar = |left: f32, amount: f32, colour: u32, batch: &mut horizon_client::hud::HudBatch| {
            let [top, width, height] = [16.0, 6.0, 52.0];
            game.native_fill(batch, [x + left, y + top, width, height], DARK);
            let filled = height * amount;
            game.native_fill(batch, [x + left, y + top + height - filled, width, filled], colour);
        };
        bar(40.0, share(value(mek::GENERATOR_DATA_LAVA), mek::LAVA_TANK_CAPACITY), ORANGE, batch);
        bar(164.0, share(value(mek::GENERATOR_DATA_ENERGY), mek::GENERATOR_CAPACITY), GREEN, batch);
        let temperature = format!("{} K", value(mek::GENERATOR_DATA_TEMPERATURE));
        game.native_text(batch, &temperature, [x + 56.0, y + 38.0], TEXT, false);
        return;
    }
    if mek::is_cube(block) {
        game.gui_cube(batch, data, origin);
    } else if block == crate::game::chem::OXIDIZER {
        game.gui_oxidizer(batch, data, origin);
    } else if let Some(def) = mekmachine_engine::process_table::process(block) {
        game.gui_process(batch, data, origin, def);
    } else if crate::game::Game::mek_is_machine(block) {
        game.gui_machine(batch, data, origin);
    }
}
