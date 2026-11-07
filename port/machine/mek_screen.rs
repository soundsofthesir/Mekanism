// A child of `native_hooks`, whose open screen state is private: `GuiVirtualSlot`'s slots, which exist
// only while their window is open.
use super::Game;
use crate::game::{gui, mek};
use mekmachine_engine::gui_layout as layout;

impl Game<'_> {
    pub(in crate::game) fn mek_screen_frame(&mut self) {
        let open = gui::upgrades_open();
        let Some(screen) = self.mod_screen.as_mut() else {
            return;
        };
        if !Self::mek_has_machine_screen(&screen.block) {
            return;
        }
        let at = |frame| if open { layout::upgrade_slot_at(frame) } else { layout::OFF_SCREEN };
        if let Some(slot) = screen.screen.slots.get_mut(mek::UPGRADE_INPUT) {
            *slot = Some(at(layout::UPGRADE_INPUT_FRAME));
        }
        if let Some(slot) = screen.screen.slots.get_mut(mek::UPGRADE_OUTPUT) {
            *slot = Some(at(layout::UPGRADE_OUTPUT_FRAME));
        }
        if !open {
            return;
        }
        let shown = [
            self.slot_view(300 + mek::UPGRADE_INPUT),
            self.slot_view(300 + mek::UPGRADE_OUTPUT),
        ];
        gui::set_window_items(shown, self.carried.clone());
    }
}
