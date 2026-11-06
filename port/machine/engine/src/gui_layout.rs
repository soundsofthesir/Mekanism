//! Where Mekanism's machine screen puts things, and what a press there does. Positions are in the
//! screen's own pixels and come from `GuiElectricMachine`, `GuiSideConfiguration` and their elements.

pub const SCREEN_WIDTH: f32 = 176.0;
pub const SCREEN_HEIGHT: f32 = 166.0;
/// `GuiSideConfigurationTab.createWindow`: centred across the screen, 15 from its top.
pub const WINDOW: [f32; 4] = [(SCREEN_WIDTH - 156.0) / 2.0, 15.0, 156.0, 135.0];
/// A tab's holder (`GuiInsetElement`) is this square, and its button sits inside it.
pub const TAB_SIZE: f32 = 26.0;
pub const TAB_BUTTON: f32 = 18.0;
/// Left of the screen.
pub const LEFT: f32 = -TAB_SIZE;
pub const RIGHT: f32 = SCREEN_WIDTH;
pub const SIDE_CONFIG_TAB: [f32; 2] = [LEFT, 6.0];
pub const TRANSPORTER_TAB: [f32; 2] = [LEFT, 34.0];
pub const ENERGY_TAB: [f32; 2] = [LEFT, 137.0];
pub const UPGRADE_TAB: [f32; 2] = [RIGHT, 6.0];
pub const SECURITY_TAB: [f32; 2] = [RIGHT, 34.0];
pub const XP_TAB: [f32; 2] = [RIGHT, 90.0];
pub const REDSTONE_TAB: [f32; 2] = [RIGHT, 137.0];
pub const UP_ARROW: [f32; 4] = [68.0, 38.0, 8.0, 10.0];
pub const PROGRESS: [f32; 4] = [86.0, 38.0, 25.0, 9.0];
/// `GuiBar` adds a pixel on each side of `GuiVerticalPowerBar`'s 4 by 52.
pub const POWER_BAR: [f32; 4] = [164.0, 16.0, 6.0, 54.0];
pub const CHAMBER_SLOTS: [[f32; 2]; 3] = [[64.0, 17.0], [116.0, 35.0], [64.0, 53.0]];
pub const INVENTORY: [f32; 2] = [8.0, 84.0];
pub const HOTBAR_Y: f32 = 142.0;

/// Inside the window, from its top left.
pub const CLOSE: [f32; 3] = [6.0, 6.0, 8.0];
pub const EJECT_BUTTON: [f32; 3] = [136.0, 6.0, 14.0];
pub const CLEAR_BUTTON: [f32; 3] = [136.0, 95.0, 14.0];
pub const EJECT_SCREEN: [f32; 4] = [38.0, 25.0, 80.0, 12.0];
pub const SIDE_BUTTON: f32 = 22.0;
/// Saved side index, as `RelativeSide`: front, left, right, back, top, bottom.
pub const SIDE_BUTTONS: [[f32; 2]; 6] = [
    [67.0, 69.0],
    [44.0, 69.0],
    [90.0, 69.0],
    [44.0, 92.0],
    [67.0, 46.0],
    [67.0, 92.0],
];
/// `TileComponentConfig` lists a machine's kinds as `AttributeSideConfig.ELECTRIC_MACHINE` does.
pub const ITEM_KIND: usize = 0;
pub const ENERGY_KIND: usize = 1;
pub const KINDS: usize = 2;

/// Menu button ids. A kind's row of six, then the same for right clicks and for shift clicks.
pub const RIGHT_CLICK_BASE: i32 = 20;
pub const SHIFT_CLICK_BASE: i32 = 40;
pub const EJECT_BASE: i32 = 60;
pub const CLEAR_BASE: i32 = 62;
const ROW: i32 = 6;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Click {
    Left,
    Right,
    Shift,
}

pub fn side_button_id(kind: usize, index: usize, click: Click) -> i32 {
    let base = match click {
        Click::Left => 0,
        Click::Right => RIGHT_CLICK_BASE,
        Click::Shift => SHIFT_CLICK_BASE,
    };
    base + kind as i32 * ROW + index as i32
}

/// What a press on the screen means.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Press {
    /// Not ours: slots and the game's own handling.
    Pass,
    /// Swallowed, with nothing to do: the window covers what is under it.
    Nothing,
    OpenWindow,
    CloseWindow,
    ShowKind(usize),
    Button(i32),
}

fn inside(at: [f32; 2], x: f32, y: f32, width: f32, height: f32) -> bool {
    at[0] >= x && at[0] < x + width && at[1] >= y && at[1] < y + height
}

/// Where a tab's button sits (`GuiInsetElement.getButtonX`).
pub fn tab_button_at(tab: [f32; 2]) -> [f32; 2] {
    let border = (TAB_SIZE - TAB_BUTTON) / 2.0;
    let nudge = if tab[0] < 0.0 { 1.0 } else { -1.0 };
    [tab[0] + border + nudge, tab[1] + border]
}

/// A side config kind's tab while the window shows another, on the window's left.
pub fn kind_tab(kind: usize) -> [f32; 2] {
    [WINDOW[0] - TAB_SIZE, WINDOW[1] + 2.0 + 28.0 * kind as f32]
}

fn on_tab_button(at: [f32; 2], tab: [f32; 2]) -> bool {
    let [x, y] = tab_button_at(tab);
    inside(at, x, y, TAB_BUTTON, TAB_BUTTON)
}

/// `window` is the kind the open side config window shows.
pub fn press(at: [f32; 2], window: Option<usize>, click: Click) -> Press {
    let Some(kind) = window else {
        return if click != Click::Right && on_tab_button(at, SIDE_CONFIG_TAB) {
            Press::OpenWindow
        } else {
            Press::Pass
        };
    };
    if on_tab_button(at, SIDE_CONFIG_TAB) {
        return Press::CloseWindow;
    }
    for other in (0..KINDS).filter(|other| *other != kind) {
        if on_tab_button(at, kind_tab(other)) {
            return Press::ShowKind(other);
        }
    }
    let [left, top, width, height] = WINDOW;
    if !inside(at, left, top, width, height) {
        return Press::Pass;
    }
    let local = [at[0] - left, at[1] - top];
    let on = |[x, y, size]: [f32; 3]| inside(local, x, y, size, size);
    if on(CLOSE) {
        return Press::CloseWindow;
    }
    if on(EJECT_BUTTON) {
        return Press::Button(EJECT_BASE + kind as i32);
    }
    if on(CLEAR_BUTTON) {
        return Press::Button(CLEAR_BASE + kind as i32);
    }
    for (index, [x, y]) in SIDE_BUTTONS.into_iter().enumerate() {
        if inside(local, x, y, SIDE_BUTTON, SIDE_BUTTON) {
            return Press::Button(side_button_id(kind, index, click));
        }
    }
    Press::Nothing
}

/// `BasicColorButton.getButtonBlitColor`: a side's colour, 0.1 less saturated and 0.1 brighter.
pub fn side_button_tint(rgb: u32) -> u32 {
    let channel = |shift: u32| f64::from((rgb >> shift) & 0xFF) / 255.0;
    let (r, g, b) = (channel(16), channel(8), channel(0));
    let max = r.max(g).max(b);
    let min = r.min(g).min(b);
    let delta = max - min;
    let hue = if delta == 0.0 {
        0.0
    } else if max == r {
        ((g - b) / delta).rem_euclid(6.0)
    } else if max == g {
        (b - r) / delta + 2.0
    } else {
        (r - g) / delta + 4.0
    };
    let saturation = if max == 0.0 { 0.0 } else { delta / max };
    let saturation = (saturation - 0.1).max(0.0);
    let value = (max + 0.1).min(1.0);
    let chroma = value * saturation;
    let x = chroma * (1.0 - (hue.rem_euclid(2.0) - 1.0).abs());
    let (r, g, b) = match hue as u32 {
        0 => (chroma, x, 0.0),
        1 => (x, chroma, 0.0),
        2 => (0.0, chroma, x),
        3 => (0.0, x, chroma),
        4 => (x, 0.0, chroma),
        _ => (chroma, 0.0, x),
    };
    let m = value - chroma;
    let byte = |c: f64| ((c + m) * 255.0).round() as u32;
    0xFF00_0000 | byte(r) << 16 | byte(g) << 8 | byte(b)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tab_middle(tab: [f32; 2]) -> [f32; 2] {
        let [x, y] = tab_button_at(tab);
        [x + TAB_BUTTON / 2.0, y + TAB_BUTTON / 2.0]
    }

    #[test]
    fn the_side_tab_opens_the_window_and_closes_it() {
        assert_eq!(press(tab_middle(SIDE_CONFIG_TAB), None, Click::Left), Press::OpenWindow);
        assert_eq!(press(tab_middle(SIDE_CONFIG_TAB), Some(0), Click::Left), Press::CloseWindow);
    }

    #[test]
    fn a_press_outside_any_control_passes_with_no_window() {
        assert_eq!(press([64.0, 17.0], None, Click::Left), Press::Pass);
    }

    #[test]
    fn the_window_swallows_a_press_over_a_slot_under_it() {
        assert_eq!(press([26.0, 100.0], Some(ITEM_KIND), Click::Left), Press::Nothing);
    }

    #[test]
    fn a_side_button_gives_its_kind_and_click() {
        let [x, y] = SIDE_BUTTONS[4];
        let at = [WINDOW[0] + x + 1.0, WINDOW[1] + y + 1.0];
        assert_eq!(press(at, Some(ITEM_KIND), Click::Left), Press::Button(4));
        assert_eq!(press(at, Some(ENERGY_KIND), Click::Left), Press::Button(10));
        assert_eq!(press(at, Some(ITEM_KIND), Click::Right), Press::Button(RIGHT_CLICK_BASE + 4));
        assert_eq!(press(at, Some(ITEM_KIND), Click::Shift), Press::Button(SHIFT_CLICK_BASE + 4));
    }

    #[test]
    fn the_shown_kind_has_no_tab_but_the_other_does() {
        let at = tab_middle(kind_tab(ENERGY_KIND));
        assert_eq!(press(at, Some(ITEM_KIND), Click::Left), Press::ShowKind(ENERGY_KIND));
        assert_eq!(press(tab_middle(kind_tab(ITEM_KIND)), Some(ITEM_KIND), Click::Left), Press::Pass);
    }

    #[test]
    fn side_tint_follows_the_mods_colour_math() {
        // `Color.hsv` and its rounding, worked through by hand for `EnumColor.DARK_RED`: 226.5, 30.5, 54.8.
        assert_eq!(side_button_tint(0xC9071F), 0xFFE31F37);
        assert_eq!(side_button_tint(0xCFCFCF), 0xFFE9E9E9);
    }
}
