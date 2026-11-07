// The Mechanical Pipe and Fluid Tank's own ticks. Their networks tick after every block, in `networks.rs`.
fn mekmachine_pipes(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut horizon_client::containers::ModBlockEntity,
) {
    use crate::game::pipe;
    if pipe::is_pipe(&entity.id) {
        game.pipe_register(pos);
    } else if pipe::is_tank(&entity.id) {
        game.pipe_tick_tank(pos, entity);
    }
}
