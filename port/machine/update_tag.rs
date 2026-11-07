// What a client needs of a cable to draw its contents.
fn mekmachine_update_tag(
    entity: &horizon_client::containers::ModBlockEntity,
    tag: &mut Option<horizon_world::nbt::Compound>,
) {
    use horizon_world::nbt::{Compound, JavaString, Tag};
    if !crate::game::mek::is_cable(&entity.id) {
        return;
    }
    let mut sent = Compound::new();
    sent.insert(JavaString::from("energy"), Tag::Long(crate::game::mek::energy_of(&entity.nbt)));
    *tag = Some(sent);
}
