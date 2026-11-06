// Mekanism's own GUI art in the game: its sprites, nine-slices and the machine screen's elements. The
// positions and what a press does are in `mekmachine_engine::gui_layout`.
use super::Game;
use super::mek;
use horizon_client::hud::HudBatch;
use mekmachine_engine::gui_layout as layout;
use std::cell::{Cell, RefCell};

const WHITE: u32 = 0xFFFF_FFFF;
/// `SpecialColors`.
const TEXT_TITLE: u32 = 0x40_4040;
const TEXT_SCREEN: u32 = 0x3C_FE9A;
const TEXT_HEADING: u32 = 0x20_2020;
const TEXT_SUBHEADING: u32 = 0x78_7878;
const TAB_ENERGY_CONFIG: u32 = 0xFF59_C15F;
const TAB_ITEM_CONFIG: u32 = 0xFFCF_CFCF;
const TAB_REDSTONE: u32 = 0xFFC9_071F;
const TAB_SECURITY: u32 = 0xFFFF_A160;
const TAB_XP: u32 = 0xFF80_FF20;
/// `SpecialColors.TAB_CONFIGURATION` and its neighbours read white from `colormap/gui_objects.png`.
const TAB_PLAIN: u32 = WHITE;
/// `DataType.getColor` through `EnumColor`: none, input, output, energy.
const SIDE_NONE: u32 = 0xCF_CFCF;
const SIDE_INPUT: u32 = 0xC9_071F;
const SIDE_OUTPUT: u32 = 0x36_6BD0;
const SIDE_ENERGY: u32 = 0x59_C15F;

thread_local! {
    /// The kind the open side config window shows. The window is the client's own, as in the real mod.
    static WINDOW: Cell<Option<usize>> = const { Cell::new(None) };
    /// The screen's top left, from the last draw.
    static ORIGIN: Cell<[f32; 2]> = const { Cell::new([0.0, 0.0]) };
    /// The menu's data slots, from the last draw, for the window drawn after the items.
    static DATA: RefCell<Vec<i32>> = const { RefCell::new(Vec::new()) };
}

fn sprite(path: &str) -> String {
    format!("mekanism:gui/sprites/{path}")
}

pub(crate) fn origin() -> [f32; 2] {
    ORIGIN.get()
}

pub(crate) fn open_kind() -> Option<usize> {
    WINDOW.get()
}

pub(crate) fn set_open_kind(kind: Option<usize>) {
    WINDOW.set(kind);
}

fn side_rgb(value: i32) -> u32 {
    match value {
        mek::SIDE_INPUT => SIDE_INPUT,
        mek::SIDE_OUTPUT => SIDE_OUTPUT,
        mek::SIDE_ENERGY => SIDE_ENERGY,
        _ => SIDE_NONE,
    }
}

pub(crate) fn side_name(value: i32) -> &'static str {
    match value {
        mek::SIDE_INPUT => "Input",
        mek::SIDE_OUTPUT => "Output",
        mek::SIDE_ENERGY => "Energy",
        _ => "None",
    }
}

impl Game<'_> {
    /// Part of a sprite, `src` in its pixels, drawn over `dst`.
    fn gui_part(&self, batch: &mut HudBatch, path: &str, src: [f32; 4], dst: [f32; 4], tint: u32) {
        let Some(mut rect) = self.gui.atlas.sprites.get(sprite(path).as_str()).copied() else {
            return;
        };
        let (du, dv) = ((rect.u1 - rect.u0) / rect.w as f32, (rect.v1 - rect.v0) / rect.h as f32);
        rect.u0 += src[0] * du;
        rect.v0 += src[1] * dv;
        rect.u1 = rect.u0 + src[2] * du;
        rect.v1 = rect.v0 + src[3] * dv;
        // `rect_uv` takes its colour as RGBA8 bytes, low byte first, and these are 0xAARRGGBB.
        let [a, r, g, b] = tint.to_be_bytes();
        batch.rect_uv(dst[0], dst[1], dst[2], dst[3], rect, u32::from_le_bytes([r, g, b, a]));
    }

    /// `GuiSpriteScaling.Tile`, repeating the source part across `dst`.
    fn gui_tile(&self, batch: &mut HudBatch, path: &str, src: [f32; 4], dst: [f32; 4], tint: u32) {
        let [sx, sy, sw, sh] = src;
        let [x, y, w, h] = dst;
        let mut down = 0.0;
        while down < h {
            let row = sh.min(h - down);
            let mut across = 0.0;
            while across < w {
                let column = sw.min(w - across);
                self.gui_part(batch, path, [sx, sy, column, row], [x + across, y + down, column, row], tint);
                across += column;
            }
            down += row;
        }
    }

    /// `GuiSpriteScaling.NineSlice`: corners as they are, the rest tiled.
    fn gui_nine(&self, batch: &mut HudBatch, path: &str, size: [f32; 2], border: f32, dst: [f32; 4], tint: u32) {
        let [tw, th] = size;
        let [x, y, w, h] = dst;
        let (mw, mh) = (tw - 2.0 * border, th - 2.0 * border);
        let (cw, ch) = (w - 2.0 * border, h - 2.0 * border);
        let (rx, by) = (x + w - border, y + h - border);
        let (sr, sb) = (tw - border, th - border);
        for (src, at) in [
            ([0.0, 0.0], [x, y]),
            ([sr, 0.0], [rx, y]),
            ([0.0, sb], [x, by]),
            ([sr, sb], [rx, by]),
        ] {
            self.gui_part(batch, path, [src[0], src[1], border, border], [at[0], at[1], border, border], tint);
        }
        self.gui_tile(batch, path, [border, 0.0, mw, border], [x + border, y, cw, border], tint);
        self.gui_tile(batch, path, [border, sb, mw, border], [x + border, by, cw, border], tint);
        self.gui_tile(batch, path, [0.0, border, border, mh], [x, y + border, border, ch], tint);
        self.gui_tile(batch, path, [sr, border, border, mh], [rx, y + border, border, ch], tint);
        self.gui_tile(batch, path, [border, border, mw, mh], [x + border, y + border, cw, ch], tint);
    }

    fn gui_whole(&self, batch: &mut HudBatch, path: &str, dst: [f32; 4]) {
        self.gui_part(batch, path, [0.0, 0.0, dst[2], dst[3]], dst, WHITE);
    }

    fn gui_panel(&self, batch: &mut HudBatch, dst: [f32; 4]) {
        self.gui_nine(batch, "base", [16.0, 16.0], 4.0, dst, WHITE);
    }

    fn gui_button(&self, batch: &mut HudBatch, dst: [f32; 4], tint: u32) {
        self.gui_nine(batch, "button", [200.0, 20.0], 2.0, dst, tint);
    }

    /// `GuiInsetElement`: a tinted holder, its button and the icon on it.
    fn gui_tab(&self, batch: &mut HudBatch, origin: [f32; 2], tab: [f32; 2], icon: &str, tint: u32) {
        let [x, y] = [origin[0] + tab[0], origin[1] + tab[1]];
        let holder = if tab[0] < 0.0 { "holder_left" } else { "holder_right" };
        self.gui_nine(batch, holder, [26.0, 9.0], 4.0, [x, y, layout::TAB_SIZE, layout::TAB_SIZE], tint);
        let [bx, by] = layout::tab_button_at(tab);
        let button = [origin[0] + bx, origin[1] + by, layout::TAB_BUTTON, layout::TAB_BUTTON];
        self.gui_button(batch, button, WHITE);
        self.gui_whole(batch, icon, button);
    }

    fn gui_centred(&self, batch: &mut HudBatch, text: &str, middle: f32, y: f32, rgb: u32) {
        let width = self.native_text_width(text);
        self.native_text(batch, text, [middle - width / 2.0, y], rgb, false);
    }

    /// `GuiElectricMachine` over `GuiMekanism`'s background.
    pub(crate) fn gui_machine(&self, batch: &mut HudBatch, data: &[i32], origin: [f32; 2]) {
        ORIGIN.set(origin);
        DATA.with_borrow_mut(|saved| data.clone_into(saved));
        let [ox, oy] = origin;
        let at = |[x, y, w, h]: [f32; 4]| [ox + x, oy + y, w, h];
        let get = |slot: usize| data.get(slot).copied().unwrap_or(0);
        self.gui_panel(batch, [ox, oy, layout::SCREEN_WIDTH, layout::SCREEN_HEIGHT]);

        let [ix, iy] = layout::INVENTORY;
        for row in 0..4 {
            let y = if row == 3 { layout::HOTBAR_Y } else { iy + 18.0 * row as f32 };
            for column in 0..9 {
                let x = ix + 18.0 * column as f32;
                self.gui_whole(batch, "slot/normal", [ox + x - 1.0, oy + y - 1.0, 18.0, 18.0]);
            }
        }
        // `SlotType.get(DataType)`: input, output and energy, each with its own frame.
        for (slot, path) in layout::CHAMBER_SLOTS.into_iter().zip(["slot/input", "slot/output", "slot/power"]) {
            self.gui_whole(batch, path, [ox + slot[0] - 1.0, oy + slot[1] - 1.0, 18.0, 18.0]);
        }

        self.gui_whole(batch, "arrow/up", at(layout::UP_ARROW));

        let [px, py, pw, ph] = layout::PROGRESS;
        self.gui_whole(batch, "progress/bar/empty", [ox + px, oy + py, pw, ph]);
        let total = get(mek::DATA_TICKS);
        if get(mek::DATA_PROGRESS) > 0 && total > 0 {
            let share = (get(mek::DATA_PROGRESS) as f32 / total as f32).min(1.0);
            // `calculateProgressSize`: the bar's inside, with at least a pixel showing.
            let filled = (share * (pw - 3.0)).ceil() + 1.0;
            self.gui_part(batch, "progress/bar/full", [1.0, 0.0, filled, ph], [ox + px + 1.0, oy + py, filled, ph], WHITE);
        }

        let [bx, by, bw, bh] = layout::POWER_BAR;
        self.gui_nine(batch, "bar/base", [5.0, 5.0], 1.0, [ox + bx, oy + by, bw, bh], WHITE);
        let capacity = get(mek::DATA_CAPACITY).max(1);
        let level = (get(mek::DATA_ENERGY) as f64 / f64::from(capacity)).min(1.0);
        if level > 0.0 {
            // `GuiBar.calculateSize`.
            let filled = (level * f64::from(bh - 3.0)).ceil() as f32 + 1.0;
            let dst = [ox + bx + 1.0, oy + by + bh - 1.0 - filled, bw - 2.0, filled];
            self.gui_tile(batch, "bar/vertical_power", [0.0, 0.0, 2.0, 2.0], dst, WHITE);
        }

        self.gui_tab(batch, origin, layout::SIDE_CONFIG_TAB, "button/configuration", TAB_PLAIN);
        self.gui_tab(batch, origin, layout::TRANSPORTER_TAB, "button/transporter_config", TAB_PLAIN);
        self.gui_tab(batch, origin, layout::UPGRADE_TAB, "button/upgrade", TAB_PLAIN);
        self.gui_tab(batch, origin, layout::SECURITY_TAB, "security/public", TAB_SECURITY);
        self.gui_tab(batch, origin, layout::XP_TAB, "tab/xp_containment", TAB_XP);
        self.gui_tab(batch, origin, layout::REDSTONE_TAB, "redstone_control/disabled", TAB_REDSTONE);
        let [ex, ey] = layout::ENERGY_TAB;
        self.gui_whole(batch, "tab/energy_info", [ox + ex, oy + ey, layout::TAB_SIZE, layout::TAB_SIZE]);

        if let Some(title) = self.native_screen_title() {
            self.gui_centred(batch, &title, ox + layout::SCREEN_WIDTH / 2.0, oy + 6.0, TEXT_TITLE);
        }
        let inventory = self.translate("container.inventory", "Inventory");
        self.native_text(batch, &inventory, [ox + 8.0, oy + layout::INVENTORY[1] - 11.0], TEXT_TITLE, false);
    }

    /// `GuiSideConfiguration`, drawn after the items so it covers them.
    pub(crate) fn gui_side_window(&self, batch: &mut HudBatch) {
        let Some(kind) = WINDOW.get() else {
            return;
        };
        let data = DATA.with_borrow(Clone::clone);
        let origin = ORIGIN.get();
        let [wx, wy, ww, wh] = layout::WINDOW;
        let [x, y] = [origin[0] + wx, origin[1] + wy];
        self.gui_nine(batch, "shadow", [9.0, 9.0], 3.0, [x - 3.0, y - 3.0, ww + 6.0, wh + 6.0], WHITE);
        self.gui_panel(batch, [x, y, ww, wh]);

        for other in 0..layout::KINDS {
            if other != kind {
                let (icon, tint) = kind_look(other);
                self.gui_tab(batch, origin, layout::kind_tab(other), icon, tint);
            }
        }
        let [cx, cy, size] = layout::CLOSE;
        self.gui_button(batch, [x + cx, y + cy, size, size], WHITE);
        self.gui_whole_scaled(batch, "button/close", [12.0, 12.0], [x + cx, y + cy, size, size]);
        let middle = x + ww / 2.0;
        let title = if kind == layout::ITEM_KIND { "Items Config" } else { "Energy Config" };
        self.gui_centred(batch, title, middle, y + 5.0, TEXT_HEADING);
        self.gui_centred(batch, "Slots", middle, y + 120.0, TEXT_SUBHEADING);

        let packed = data.get(sides_slot(kind)).copied().unwrap_or(0);
        let [sx, sy, sw, sh] = layout::EJECT_SCREEN;
        self.gui_nine(batch, "inner_screen", [256.0, 256.0], 32.0, [x + sx, y + sy, sw, sh], WHITE);
        let ejecting = packed >> mek::EJECT_BIT & 1 == 1;
        let line = format!("Eject: {}", if ejecting { "on" } else { "off" });
        self.gui_centred(batch, &line, x + sx + sw / 2.0, y + sy + 2.0, TEXT_SCREEN);

        let [ex, ey, size] = layout::EJECT_BUTTON;
        self.gui_button(batch, [x + ex, y + ey, size, size], WHITE);
        self.gui_whole(batch, "button/auto_eject", [x + ex, y + ey, size, size]);
        let [ex, ey, size] = layout::CLEAR_BUTTON;
        self.gui_button(batch, [x + ex, y + ey, size, size], WHITE);
        self.gui_whole(batch, "button/clear_sides", [x + ex, y + ey, size, size]);

        for (index, [bx, by]) in layout::SIDE_BUTTONS.into_iter().enumerate() {
            let tint = layout::side_button_tint(side_rgb(side_of(packed, kind, index)));
            let size = layout::SIDE_BUTTON;
            self.gui_button(batch, [x + bx, y + by, size, size], tint);
        }
    }

    fn gui_whole_scaled(&self, batch: &mut HudBatch, path: &str, size: [f32; 2], dst: [f32; 4]) {
        self.gui_part(batch, path, [0.0, 0.0, size[0], size[1]], dst, WHITE);
    }

    /// What the cursor is over, for `GuiElement.renderToolTip`.
    pub(crate) fn gui_tooltip(&self, data: &[i32], at: [f32; 2], lines: &mut Vec<String>) {
        let on_tab = |tab: [f32; 2]| {
            let [x, y] = layout::tab_button_at(tab);
            at[0] >= x && at[0] < x + layout::TAB_BUTTON && at[1] >= y && at[1] < y + layout::TAB_BUTTON
        };
        if let Some(kind) = WINDOW.get() {
            let local = [at[0] - layout::WINDOW[0], at[1] - layout::WINDOW[1]];
            for (index, [x, y]) in layout::SIDE_BUTTONS.into_iter().enumerate() {
                let size = layout::SIDE_BUTTON;
                if local[0] >= x && local[0] < x + size && local[1] >= y && local[1] < y + size {
                    let packed = data.get(sides_slot(kind)).copied().unwrap_or(0);
                    lines.push(format!(
                        "{}: {}",
                        SIDE_NAMES[index],
                        side_name(side_of(packed, kind, index))
                    ));
                }
            }
            return;
        }
        if on_tab(layout::SIDE_CONFIG_TAB) {
            lines.push("Side Config".to_owned());
        }
        let [bx, by, bw, bh] = layout::POWER_BAR;
        if at[0] >= bx && at[0] < bx + bw && at[1] >= by && at[1] < by + bh {
            let energy = data.get(mek::DATA_ENERGY).copied().unwrap_or(0);
            let capacity = data.get(mek::DATA_CAPACITY).copied().unwrap_or(0);
            lines.push(format!("{energy}/{capacity} FE"));
        }
    }
}

const SIDE_NAMES: [&str; 6] = ["Front", "Left", "Right", "Back", "Top", "Bottom"];

fn kind_look(kind: usize) -> (&'static str, u32) {
    if kind == layout::ITEM_KIND {
        ("transmission/items", TAB_ITEM_CONFIG)
    } else {
        ("transmission/energy", TAB_ENERGY_CONFIG)
    }
}

fn sides_slot(kind: usize) -> usize {
    if kind == layout::ITEM_KIND {
        mek::DATA_ITEM_SIDES
    } else {
        mek::DATA_ENERGY_SIDES
    }
}

/// A side's saved value, from a data slot's 2 bits a side.
fn side_of(packed: i32, kind: usize, index: usize) -> i32 {
    let position = mek::unpack_side(packed, index);
    if kind == layout::ITEM_KIND {
        mek::ITEM_SIDE_CYCLE[position]
    } else {
        mek::ENERGY_SIDE_CYCLE[position & 1]
    }
}
