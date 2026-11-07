// The component that says which upgrade a `mekanism:upgrade` item is.
fn mekmachine_component_types(types: &mut Vec<String>) {
    types.push(crate::game::mek::UPGRADE_COMPONENT.to_owned());
}
