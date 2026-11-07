fn mekmachine_networks(game: &mut crate::game::Game<'_>) {
    // Keeps the source hash in the compiled engine, where `port/source_hash.py` looks for it.
    std::hint::black_box(mekmachine_engine::build_stamp::SOURCE);
    game.mek_tick_networks();
    game.chem_tick_networks();
    game.pipe_tick_networks();
}
