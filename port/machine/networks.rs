fn mekmachine_networks(game: &mut crate::game::Game<'_>) {
    game.mek_tick_networks();
    game.chem_tick_networks();
    game.pipe_tick_networks();
}
