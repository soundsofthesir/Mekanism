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

/// `GuiChemicalOxidizer`, and the slots from `TileEntityChemicalOxidizer`: input, drain, energy.
pub const OXIDIZER_SLOTS: [[f32; 2]; 3] = [[26.0, 36.0], [152.0, 55.0], [152.0, 14.0]];
pub const OXIDIZER_PROGRESS: [f32; 4] = [64.0, 40.0, 48.0, 8.0];
/// `GaugeOverlay.STANDARD`'s 16 by 58, with a pixel on each side.
pub const OXIDIZER_GAUGE: [f32; 4] = [131.0, 13.0, 18.0, 60.0];
pub const OXIDIZER_POWER_BAR: [f32; 4] = [115.0, 75.0, 54.0, 6.0];
pub const OXIDIZER_TITLE_Y: f32 = 5.0;
pub const TITLE_Y: f32 = 6.0;

/// `GuiTankGauge.getScaledLevel`: at least a pixel when anything is held.
pub fn gauge_level(stored: i64, capacity: i64, inside: i32) -> i32 {
    if stored <= 0 || capacity <= 0 {
        return 0;
    }
    ((stored as f64 / capacity as f64 * f64::from(inside)).round() as i32).max(1)
}

/// `GuiBar.calculateSize`, whose result is at least a pixel.
pub fn bar_size(level: f64, inside: f32) -> f32 {
    (level * f64::from(inside - 1.0)).ceil() as f32 + 1.0
}

/// `GuiProgress.calculateProgressSize`.
pub fn progress_size(share: f32, size: f32) -> f32 {
    (share * (size - 1.0)).ceil() + 1.0
}

/// `TextUtils.format` in English, with its grouping.
pub fn format_number(value: i64) -> String {
    let digits = value.abs().to_string();
    let mut out = String::new();
    for (index, digit) in digits.chars().enumerate() {
        if index > 0 && (digits.len() - index).is_multiple_of(3) {
            out.push(',');
        }
        out.push(digit);
    }
    if value < 0 { format!("-{out}") } else { out }
}

/// What the energy parts of a screen say, as `EnergyDisplay` with the default compact display.
pub fn energy_text(value: i64) -> String {
    const PREFIXES: [(f64, &str); 7] = [
        (1.0, ""),
        (1e3, "k"),
        (1e6, "M"),
        (1e9, "G"),
        (1e12, "T"),
        (1e15, "P"),
        (1e18, "E"),
    ];
    if value == 0 {
        return "0 FE".to_owned();
    }
    let number = value as f64;
    let (size, prefix) = PREFIXES.iter().rev().find(|(size, _)| number >= *size).copied().unwrap_or(PREFIXES[0]);
    let rounded = ((number / size) * 100.0).trunc() / 100.0;
    format!("{} {prefix}FE", trim_number(rounded))
}

fn trim_number(value: f64) -> String {
    let text = format!("{value:.2}");
    text.trim_end_matches('0').trim_end_matches('.').to_owned()
}

/// `MekanismLang.GENERIC_FRACTION` of two energies.
pub fn energy_fraction(stored: i64, capacity: i64) -> String {
    format!("{}/{}", energy_text(stored), energy_text(capacity))
}

/// `GuiEnergyTab`'s lines.
pub fn energy_tab_lines(using: i64, needed: i64) -> Vec<String> {
    vec![
        format!("Using: {}/t", energy_text(using)),
        format!("Needed: {}", energy_text(needed)),
        "Unit: FE".to_owned(),
    ]
}

/// `GuiTankGauge.getContentsTooltips`.
pub fn gauge_lines(name: Option<&str>, amount: i64) -> Vec<String> {
    match name {
        Some(name) if amount > 0 => vec![format!("{name}: {} mB", format_number(amount))],
        _ => vec!["Empty".to_owned()],
    }
}
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
pub const CHEMICAL_KIND: usize = 2;
/// `AttributeSideConfig`: a window's kinds, in tab order.
pub const ELECTRIC_KINDS: &[usize] = &[ITEM_KIND, ENERGY_KIND];
pub const OXIDIZER_KINDS: &[usize] = &[ITEM_KIND, CHEMICAL_KIND, ENERGY_KIND];
const KIND_COUNT: i32 = 3;

/// Menu button ids. A kind's row of six, then the same for right clicks and for shift clicks.
pub const RIGHT_CLICK_BASE: i32 = 20;
pub const SHIFT_CLICK_BASE: i32 = 40;
pub const EJECT_BASE: i32 = 60;
pub const CLEAR_BASE: i32 = EJECT_BASE + KIND_COUNT;
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

/// The tab of a window's kind at this place in its list, on the window's left.
pub fn kind_tab(place: usize) -> [f32; 2] {
    [WINDOW[0] - TAB_SIZE, WINDOW[1] + 2.0 + 28.0 * place as f32]
}

fn on_tab_button(at: [f32; 2], tab: [f32; 2]) -> bool {
    let [x, y] = tab_button_at(tab);
    inside(at, x, y, TAB_BUTTON, TAB_BUTTON)
}

/// `window` is the kind the open side config window shows.
pub fn press(at: [f32; 2], window: Option<usize>, kinds: &[usize], click: Click) -> Press {
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
    for (place, other) in kinds.iter().enumerate().filter(|(_, other)| **other != kind) {
        if on_tab_button(at, kind_tab(place)) {
            return Press::ShowKind(*other);
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
        assert_eq!(press(tab_middle(SIDE_CONFIG_TAB), None, ELECTRIC_KINDS, Click::Left), Press::OpenWindow);
        assert_eq!(press(tab_middle(SIDE_CONFIG_TAB), Some(0), ELECTRIC_KINDS, Click::Left), Press::CloseWindow);
    }

    #[test]
    fn a_press_outside_any_control_passes_with_no_window() {
        assert_eq!(press([64.0, 17.0], None, ELECTRIC_KINDS, Click::Left), Press::Pass);
    }

    #[test]
    fn the_window_swallows_a_press_over_a_slot_under_it() {
        assert_eq!(press([26.0, 100.0], Some(ITEM_KIND), ELECTRIC_KINDS, Click::Left), Press::Nothing);
    }

    #[test]
    fn a_side_button_gives_its_kind_and_click() {
        let [x, y] = SIDE_BUTTONS[4];
        let at = [WINDOW[0] + x + 1.0, WINDOW[1] + y + 1.0];
        assert_eq!(press(at, Some(ITEM_KIND), ELECTRIC_KINDS, Click::Left), Press::Button(4));
        assert_eq!(press(at, Some(ENERGY_KIND), ELECTRIC_KINDS, Click::Left), Press::Button(10));
        assert_eq!(press(at, Some(ITEM_KIND), ELECTRIC_KINDS, Click::Right), Press::Button(RIGHT_CLICK_BASE + 4));
        assert_eq!(press(at, Some(ITEM_KIND), ELECTRIC_KINDS, Click::Shift), Press::Button(SHIFT_CLICK_BASE + 4));
    }

    #[test]
    fn the_shown_kind_has_no_tab_but_the_other_does() {
        let at = tab_middle(kind_tab(1));
        assert_eq!(press(at, Some(ITEM_KIND), ELECTRIC_KINDS, Click::Left), Press::ShowKind(ENERGY_KIND));
        assert_eq!(press(tab_middle(kind_tab(0)), Some(ITEM_KIND), ELECTRIC_KINDS, Click::Left), Press::Pass);
    }

    #[test]
    fn the_oxidizer_window_has_three_kinds_with_chemicals_second() {
        let at = tab_middle(kind_tab(1));
        assert_eq!(press(at, Some(ITEM_KIND), OXIDIZER_KINDS, Click::Left), Press::ShowKind(CHEMICAL_KIND));
        let at = tab_middle(kind_tab(2));
        assert_eq!(press(at, Some(ITEM_KIND), OXIDIZER_KINDS, Click::Left), Press::ShowKind(ENERGY_KIND));
        let [x, y] = SIDE_BUTTONS[4];
        let side = [WINDOW[0] + x + 1.0, WINDOW[1] + y + 1.0];
        assert_eq!(press(side, Some(CHEMICAL_KIND), OXIDIZER_KINDS, Click::Left), Press::Button(16));
        let [x, y, _] = EJECT_BUTTON;
        let eject = [WINDOW[0] + x + 1.0, WINDOW[1] + y + 1.0];
        assert_eq!(press(eject, Some(CHEMICAL_KIND), OXIDIZER_KINDS, Click::Left), Press::Button(62));
        let [x, y, _] = CLEAR_BUTTON;
        let clear = [WINDOW[0] + x + 1.0, WINDOW[1] + y + 1.0];
        assert_eq!(press(clear, Some(ITEM_KIND), OXIDIZER_KINDS, Click::Left), Press::Button(63));
    }

    #[test]
    fn the_gauge_shows_at_least_a_pixel_and_rounds() {
        assert_eq!(gauge_level(0, 10_000, 58), 0);
        assert_eq!(gauge_level(1, 10_000, 58), 1);
        assert_eq!(gauge_level(5_000, 10_000, 58), 29);
        assert_eq!(gauge_level(10_000, 10_000, 58), 58);
    }

    #[test]
    fn energy_text_is_compact_with_two_decimals_cut_off() {
        assert_eq!(energy_text(0), "0 FE");
        assert_eq!(energy_text(20), "20 FE");
        assert_eq!(energy_text(1_500), "1.5 kFE");
        assert_eq!(energy_text(1_999), "1.99 kFE");
        assert_eq!(energy_fraction(5, 20), "5 FE/20 FE");
    }

    #[test]
    fn the_gauge_tooltip_says_empty_or_the_amount() {
        assert_eq!(gauge_lines(None, 0), ["Empty"]);
        assert_eq!(gauge_lines(Some("Sulfur Dioxide"), 1_200), ["Sulfur Dioxide: 1,200 mB"]);
    }

    #[test]
    fn side_tint_follows_the_mods_colour_math() {
        // `Color.hsv` and its rounding, worked through by hand for `EnumColor.DARK_RED`: 226.5, 30.5, 54.8.
        assert_eq!(side_button_tint(0xC9071F), 0xFFE31F37);
        assert_eq!(side_button_tint(0xCFCFCF), 0xFFE9E9E9);
    }
}
