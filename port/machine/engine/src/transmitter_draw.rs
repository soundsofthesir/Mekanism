//! Which of a transmitter's model groups to draw (`TransmitterModelData`), without game types.

/// `Direction` order, as a block state names them.
pub const SIDES: [&str; 6] = ["down", "up", "north", "south", "west", "east"];
/// `VisualConnectionStatus.CONTIGUOUS_ROTATION`.
pub const CONTIGUOUS_DEGREES: f32 = 270.0;
/// `Direction.getUnitVec3f` negated, as `makeIconStatusTransform` uses it, in `SIDES`' order.
const AXES: [[f32; 3]; 6] = [
    [0.0, 1.0, 0.0],
    [0.0, -1.0, 0.0],
    [0.0, 0.0, 1.0],
    [0.0, 0.0, -1.0],
    [1.0, 0.0, 0.0],
    [-1.0, 0.0, 0.0],
];
const DOWN: usize = 0;
const UP: usize = 1;
const NORTH: usize = 2;
const SOUTH: usize = 3;
const WEST: usize = 4;
const EAST: usize = 5;

/// One group to draw.
#[derive(Clone, Debug, PartialEq)]
pub struct Part {
    pub group: String,
    /// `NoneSegmentRemap`: a side along a straight run shows `#side`, not its centre texture.
    pub centre_as_side: bool,
    /// `NONE_CONTIGUOUS_ROTATED` turns the part about this axis.
    pub rotate_about: Option<[f32; 3]>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum NoneStatus {
    Plain,
    Contiguous,
    Rotated,
}

/// `getStatus`: a face with no connection, between the two pairs of sides around it.
fn status(a: bool, b: bool, c: bool, d: bool) -> NoneStatus {
    if (a || b) != (c || d) {
        if a && b {
            return NoneStatus::Contiguous;
        }
        if c && d {
            return NoneStatus::Rotated;
        }
    }
    NoneStatus::Plain
}

fn none_status(side: usize, on: [bool; 6]) -> NoneStatus {
    match side {
        DOWN | UP => status(on[NORTH], on[SOUTH], on[EAST], on[WEST]),
        NORTH | SOUTH => status(on[UP], on[DOWN], on[EAST], on[WEST]),
        _ => status(on[UP], on[DOWN], on[NORTH], on[SOUTH]),
    }
}

/// The base model's parts for a block's connections, in `SIDES` order.
pub fn parts(connected: [bool; 6]) -> Vec<Part> {
    (0..SIDES.len())
        .map(|side| {
            if connected[side] {
                return Part {
                    group: format!("{}NORMAL", SIDES[side]),
                    centre_as_side: false,
                    rotate_about: None,
                };
            }
            let kind = none_status(side, connected);
            Part {
                group: format!("{}NONE", SIDES[side]),
                centre_as_side: kind != NoneStatus::Plain,
                rotate_about: (kind == NoneStatus::Rotated).then_some(AXES[side]),
            }
        })
        .collect()
}

/// `TransmitterContentsManager`: the same choice, with no join rule.
pub fn contents_groups(connected: [bool; 6]) -> Vec<String> {
    (0..SIDES.len())
        .map(|side| format!("{}{}", SIDES[side], if connected[side] { "NORMAL" } else { "NONE" }))
        .collect()
}

/// A share of a capacity, 0 to 1.
pub fn contents_scale(held: i64, capacity: i64) -> f32 {
    if capacity <= 0 {
        return 0.0;
    }
    (held as f32 / capacity as f32).clamp(0.0, 1.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn connections(on: &[usize]) -> [bool; 6] {
        let mut all = [false; 6];
        for side in on {
            all[*side] = true;
        }
        all
    }

    #[test]
    fn a_lone_cable_shows_six_plain_faces() {
        let shown = parts([false; 6]);
        assert_eq!(shown.len(), 6);
        assert!(shown.iter().all(|part| part.group.ends_with("NONE") && !part.centre_as_side));
    }

    #[test]
    fn a_straight_run_joins_its_sides_along_it() {
        let shown = parts(connections(&[NORTH, SOUTH]));
        assert_eq!(shown[NORTH].group, "northNORMAL");
        assert_eq!(shown[SOUTH].group, "southNORMAL");
        // Up and down have north and south as their first pair.
        assert_eq!(shown[UP].rotate_about, None);
        assert!(shown[UP].centre_as_side);
        // East and west have them as their second pair, so those faces turn.
        assert_eq!(shown[EAST].rotate_about, Some(AXES[EAST]));
    }

    #[test]
    fn a_bend_keeps_plain_faces() {
        let shown = parts(connections(&[NORTH, EAST]));
        assert!(shown[UP].group.ends_with("NONE") && !shown[UP].centre_as_side);
    }
}
