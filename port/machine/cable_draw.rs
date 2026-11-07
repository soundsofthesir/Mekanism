// Draws the Universal Cable with Mekanism's own OBJ model and textures, and its energy contents.
fn mekmachine_cable_draw(
    game: &crate::game::Game<'_>,
    block: &str,
    state: horizon_world::registry::BlockStateId,
    entity: &horizon_client::containers::ModBlockEntity,
    draw: &mut crate::game::native_block_entity_draw::BlockEntityDraw,
) {
    if crate::game::mek::is_cable(block) {
        game.mek_draw_cable(state, entity, draw);
    }
}
