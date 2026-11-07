// `MekanismItems.ENERGY_TABLET`, with `GearConfig`'s defaults: 1,000,000 FE at 5,000 FE a tick.
fn mekmachine_item_energy_buffer(item: &str, buffer: &mut Option<crate::game::native_item_energy::ItemEnergyBuffer>) {
    const TABLET_CAPACITY: i32 = 1_000_000;
    const TABLET_RATE: i32 = 5_000;
    if item == crate::game::mek::ENERGY_TABLET {
        *buffer = Some(crate::game::native_item_energy::ItemEnergyBuffer {
            capacity: TABLET_CAPACITY,
            max_insert: TABLET_RATE,
            max_extract: TABLET_RATE,
        });
    }
}
