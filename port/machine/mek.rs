// What Mekanism's blocks share in the game: side configuration, energy between blocks, and cable
// networks. The rules that need no game types are in `mekmachine_engine`.
use mekmachine_engine::upgrades::Upgrades;
use super::Game;
use horizon_core::geometry::Direction;
use horizon_world::nbt::{Compound, JavaString, Tag};
use mekmachine_engine::split::split;
use std::{cell::RefCell, collections::HashMap};

use mekmachine_engine::tiers;

const CUBE_KIND: &str = "energy_cube";
const CABLE_KIND: &str = "universal_cable";

pub(crate) fn is_cube(block: &str) -> bool {
    tiers::tier_of(block, CUBE_KIND).is_some()
}

pub(crate) fn is_cable(block: &str) -> bool {
    tiers::tier_of(block, CABLE_KIND).is_some()
}

/// A cable's share of its network's capacity. Cables of different tiers join.
fn cable_capacity(block: &str) -> i64 {
    tiers::value_of(block, CABLE_KIND, &tiers::CABLE_CAPACITY).unwrap_or(0)
}

pub(crate) fn cube_capacity(block: &str) -> Option<i64> {
    tiers::value_of(block, CUBE_KIND, &tiers::CUBE_CAPACITY)
}

pub(crate) fn cube_rate(block: &str) -> i64 {
    tiers::value_of(block, CUBE_KIND, &tiers::CUBE_RATE).unwrap_or(0)
}
pub(crate) const GENERATOR: &str = "mekanismgenerators:heat_generator";
/// `GeneratorsStorageConfig.heatGenerator`.
pub(crate) const GENERATOR_CAPACITY: i32 = 240;
/// `heatTankCapacity`.
pub(crate) const LAVA_TANK_CAPACITY: i32 = 1_000;
/// `DataType` ordinals, as saved in `component_config`.
pub(crate) const SIDE_INPUT: i32 = 1;
pub(crate) const SIDE_OUTPUT: i32 = 4;
pub(crate) const SIDE_ENERGY: i32 = 8;
/// `LightConfigInfo.MACHINE`: right is the output, back the energy slot, the rest input.
const MACHINE_ITEM_SIDES: [i32; 6] = [SIDE_INPUT, SIDE_INPUT, SIDE_OUTPUT, SIDE_ENERGY, SIDE_INPUT, SIDE_INPUT];
/// `ItemBlockEnergyCube.SIDE_CONFIG`: `FRONT_OUT_EJECT` for energy, `FRONT_OUT_NO_EJECT` for items.
const CUBE_ENERGY_SIDES: [i32; 6] = [SIDE_OUTPUT, SIDE_INPUT, SIDE_INPUT, SIDE_INPUT, SIDE_INPUT, SIDE_INPUT];
const CUBE_ITEM_SIDES: [i32; 6] = CUBE_ENERGY_SIDES;
/// `TransmissionType.ENERGY`'s index, in `config0` and `eject0`.
pub(crate) const ENERGY_CONFIG: &str = "config0";
/// `TransmissionType.ITEM`'s index.
pub(crate) const ITEM_CONFIG: &str = "config3";
/// `Direction` order, as `EnumUtils.DIRECTIONS`.
pub(crate) const DIRECTIONS: [Direction; 6] = [
    Direction::Down,
    Direction::Up,
    Direction::North,
    Direction::South,
    Direction::West,
    Direction::East,
];

/// The slot after those the machines in `process_table.rs` share with the other machines.
pub(crate) const ADVANCED_SECONDARY: usize = 5;
pub(crate) const ADVANCED_SLOTS: usize = 6;

pub(crate) fn has_block_entity(block: &str) -> bool {
    matches!(block, "mekanism:enrichment_chamber" | "mekanism:crusher" | "mekanism:energized_smelter")
        || mekmachine_engine::process_table::process(block).is_some()
        || is_cube(block)
        || is_cable(block)
        || block == GENERATOR
        || block == super::chem::OXIDIZER
        || super::chem::is_tube(block)
        || super::chem::is_tank(block)
        || super::pipe::is_pipe(block)
        || super::pipe::is_tank(block)
}

/// The side config a block's item gives it when placed (`AttachedSideConfig`). The real mod applies
/// it only to a player's placement, so a bare `setblock` there has none and one here does.
pub(crate) fn default_config(block: &str) -> Compound {
    if block == super::chem::OXIDIZER {
        return chemical_out_config();
    }
    if super::chem::is_tank(block) {
        return chemical_tank_config();
    }
    let (energy, items): ([i32; 6], [i32; 6]) = match block {
        cube if is_cube(cube) => (CUBE_ENERGY_SIDES, CUBE_ITEM_SIDES),
        "mekanism:enrichment_chamber" | "mekanism:crusher" | "mekanism:energized_smelter" => {
            ([SIDE_INPUT; 6], MACHINE_ITEM_SIDES)
        }
        block if mekmachine_engine::process_table::process(block).is_some() => ([SIDE_INPUT; 6], MACHINE_ITEM_SIDES),
        _ => return Compound::new(),
    };
    let mut config = Compound::new();
    config.insert(JavaString::from(ENERGY_CONFIG), Tag::IntArray(energy.to_vec()));
    config.insert(JavaString::from(ITEM_CONFIG), Tag::IntArray(items.to_vec()));
    if is_cube(block) {
        config.insert(JavaString::from("eject0"), Tag::Byte(1));
    }
    let mut nbt = Compound::new();
    nbt.insert(JavaString::from("component_config"), Tag::Compound(config));
    nbt
}

/// `AttachedSideConfig.CHEMICAL_OUT_MACHINE`: `LightConfigInfo.RIGHT_OUTPUT` ejects.
fn chemical_out_config() -> Compound {
    const RIGHT_OUTPUT: [i32; 6] = [0, 0, SIDE_OUTPUT, 0, 0, 0];
    let mut config = Compound::new();
    config.insert(JavaString::from(ENERGY_CONFIG), Tag::IntArray(vec![SIDE_INPUT; 6]));
    config.insert(JavaString::from(ITEM_CONFIG), Tag::IntArray(MACHINE_ITEM_SIDES.to_vec()));
    config.insert(JavaString::from(super::chem::CHEMICAL_CONFIG), Tag::IntArray(RIGHT_OUTPUT.to_vec()));
    config.insert(JavaString::from("eject2"), Tag::Byte(1));
    let mut nbt = Compound::new();
    nbt.insert(JavaString::from("component_config"), Tag::Compound(config));
    nbt
}

/// `ItemBlockChemicalTank.SIDE_CONFIG`: `FRONT_OUT_EJECT` for chemicals, no eject for items.
fn chemical_tank_config() -> Compound {
    const FRONT_OUT: [i32; 6] = [SIDE_OUTPUT, SIDE_INPUT, SIDE_INPUT, SIDE_INPUT, SIDE_INPUT, SIDE_INPUT];
    let mut config = Compound::new();
    config.insert(JavaString::from(super::chem::CHEMICAL_CONFIG), Tag::IntArray(FRONT_OUT.to_vec()));
    config.insert(JavaString::from(ITEM_CONFIG), Tag::IntArray(FRONT_OUT.to_vec()));
    config.insert(JavaString::from("eject2"), Tag::Byte(1));
    let mut nbt = Compound::new();
    nbt.insert(JavaString::from("component_config"), Tag::Compound(config));
    nbt
}

/// The data slots of a machine's menu.
pub(crate) const DATA_PROGRESS: usize = 0;
pub(crate) const DATA_TICKS: usize = 1;
pub(crate) const DATA_ENERGY: usize = 2;
pub(crate) const DATA_CAPACITY: usize = 3;
pub(crate) const DATA_ITEM_SIDES: usize = 4;
pub(crate) const DATA_ENERGY_SIDES: usize = 5;
pub(crate) const DATA_USING: usize = 6;
/// The high halves of the energy amounts, each of which takes two 16-bit slots.
pub(crate) const DATA_ENERGY_HIGH: usize = 10;
pub(crate) const DATA_CAPACITY_HIGH: usize = 11;
pub(crate) const DATA_USING_HIGH: usize = 12;
pub(crate) const DATA_CONTROL: usize = 13;
pub(crate) const DATA_SPEED: usize = 14;
pub(crate) const DATA_ENERGY_UPGRADES: usize = 15;
pub(crate) const DATA_INSTALL_TICKS: usize = 16;
/// The menu's data slots, the same for every machine. The oxidizer also fills the chemical ones.
pub(crate) const DATA_SLOTS: usize = 17;
/// Menu slots of every machine with upgrades: `TileComponentUpgrade`'s two.
pub(crate) const UPGRADE_INPUT: usize = 3;
pub(crate) const UPGRADE_OUTPUT: usize = 4;
pub(crate) const MACHINE_SLOTS: usize = 5;
pub(crate) const ENERGY_SLOT: usize = 2;
/// `TileEntityEnergyCube`'s slots.
pub(crate) const CUBE_DISCHARGE: usize = 0;
pub(crate) const CUBE_CHARGE: usize = 1;
pub(crate) const CUBE_SLOTS: usize = 2;
pub(crate) const ENERGY_TABLET: &str = "mekanism:energy_tablet";
pub(crate) const UPGRADE_COMPONENT: &str = "mekanism:upgrade_type";
pub(crate) const UPGRADE_ITEM: &str = "mekanism:upgrade";
/// `UPGRADE_NAMES`' order.
pub(crate) const UPGRADE_IDS: [&str; 2] = ["mekanism:speed", "mekanism:energy"];
/// The data slots of the generator's menu.
pub(crate) const GENERATOR_DATA_LAVA: usize = 0;
pub(crate) const GENERATOR_DATA_ENERGY: usize = 1;
pub(crate) const GENERATOR_DATA_TEMPERATURE: usize = 2;
/// `RelativeSide.RIGHT`'s index in a saved side config.
pub(crate) const RIGHT_INDEX: usize = 2;
/// Menu buttons: 0 to 5 change an item side, 6 to 11 an energy side, by saved index.
pub(crate) const BUTTONS_PER_ROW: i32 = 6;

/// The values a side cycles through, in the order `SideConfig` offers them for one-slot machines.
pub(crate) const ITEM_SIDE_CYCLE: [i32; 4] = [0, SIDE_INPUT, SIDE_OUTPUT, SIDE_ENERGY];
pub(crate) const ENERGY_SIDE_CYCLE: [i32; 2] = [0, SIDE_INPUT];
pub(crate) const CHEMICAL_SIDE_CYCLE: [i32; 2] = [0, SIDE_OUTPUT];
/// A cube's items and energy, each with an input and an output (`setupIOConfig`).
pub(crate) const CUBE_SIDE_CYCLE: [i32; 3] = [0, SIDE_INPUT, SIDE_OUTPUT];

/// The bits above a packed side config in a data slot: whether that kind ejects.
pub(crate) const EJECT_BIT: i32 = 12;
pub(crate) const SIDES: usize = 6;
pub(crate) const ITEM_EJECT: &str = "eject3";
pub(crate) const ENERGY_EJECT: &str = "eject0";

/// A side config packed into a data slot, 2 bits a side, as an index into its cycle.
pub(crate) fn pack_sides(nbt: &Compound, config: &str, cycle: &[i32]) -> i32 {
    let eject = match config {
        ITEM_CONFIG => ITEM_EJECT,
        super::chem::CHEMICAL_CONFIG => super::chem::EJECT,
        _ => ENERGY_EJECT,
    };
    let packed = (0..SIDES).fold(0, |packed, index| {
        let value = side_value(nbt, config, index);
        let position = cycle.iter().position(|v| *v == value).unwrap_or(0) as i32;
        packed | (position << (2 * index))
    });
    packed | (i32::from(is_ejecting(nbt, eject)) << EJECT_BIT)
}

/// `component_upgrade: {upgrades: {"mekanism:speed": 4}}`, as the real mod saves it.
pub(crate) fn upgrades_of(nbt: &Compound) -> Upgrades {
    let Some(Tag::Compound(component)) = nbt.get(&JavaString::from("component_upgrade")) else {
        return Upgrades::default();
    };
    let Some(Tag::Compound(installed)) = component.get(&JavaString::from("upgrades")) else {
        return Upgrades::default();
    };
    let count = |name: &str| match installed.get(&JavaString::from(name)) {
        Some(Tag::Int(count)) => (*count).max(0) as u32,
        _ => 0,
    };
    Upgrades { speed: count("mekanism:speed"), energy: count("mekanism:energy") }
}

/// Fills what every upgradable machine's menu shares.
pub(crate) fn fill_menu(data: &mut [i32], nbt: &Compound, energy: i64, capacity: i64, using: i64) {
    use mekmachine_engine::upgrades::{high_half, low_half};
    data[DATA_ENERGY] = low_half(energy);
    data[DATA_ENERGY_HIGH] = high_half(energy);
    data[DATA_CAPACITY] = low_half(capacity);
    data[DATA_CAPACITY_HIGH] = high_half(capacity);
    data[DATA_USING] = low_half(using);
    data[DATA_USING_HIGH] = high_half(using);
    let upgrades = upgrades_of(nbt);
    data[DATA_SPEED] = upgrades.speed as i32;
    data[DATA_ENERGY_UPGRADES] = upgrades.energy as i32;
    data[DATA_INSTALL_TICKS] = match nbt.get(&JavaString::from(INSTALL_TICKS_KEY)) {
        Some(Tag::Int(ticks)) => *ticks,
        _ => 0,
    };
    let control = match nbt.get(&JavaString::from("control_type")) {
        Some(Tag::String(mode)) => mode.to_string_lossy(),
        _ => String::new(),
    };
    let modes = mekmachine_engine::upgrades::CONTROL_MODES;
    data[DATA_CONTROL] = modes.iter().position(|mode| *mode == control).unwrap_or(0) as i32;
}

const INSTALL_TICKS_KEY: &str = "upgrade_ticks";

/// `IRedstoneControl.setControlType`, by a press on the tab.
pub(crate) fn cycle_control(nbt: &mut Compound, forward: bool) {
    let mode = match nbt.get(&JavaString::from("control_type")) {
        Some(Tag::String(mode)) => mode.to_string_lossy(),
        _ => String::new(),
    };
    let next = mekmachine_engine::upgrades::next_control(&mode, forward);
    nbt.insert(JavaString::from("control_type"), Tag::String(JavaString::from(next)));
}

/// A machine's capacity follows its upgrades once `recalculateUpgrades` has run, which it does when
/// `component_upgrade` loads and at any install or uninstall. The real mod's saved data has that key
/// only if something is installed or in an upgrade slot, so what says it has run must go on any load,
/// as a chunk unloading shows (`port/reference/unload_*`). A block entity's `data` isn't saved and
/// loads empty, so the mark is one more value there, past what a menu sends.
const DATA_RECALCULATED: usize = DATA_SLOTS;

fn mark_recalculated(data: &mut Vec<i32>) {
    if data.len() <= DATA_RECALCULATED {
        data.resize(DATA_RECALCULATED + 1, 0);
    }
    data[DATA_RECALCULATED] = 1;
}

/// Carries the mark to the data a machine's tick has just built.
pub(crate) fn keep_recalculated(old: &[i32], new: &mut Vec<i32>) {
    if old.get(DATA_RECALCULATED) == Some(&1) {
        mark_recalculated(new);
    }
}

fn is_recalculated(nbt: &Compound, data: &[i32]) -> bool {
    let installed = upgrades_of(nbt);
    installed.speed > 0 || installed.energy > 0 || data.get(DATA_RECALCULATED) == Some(&1)
}

/// Which of `UPGRADE_IDS` a saved `component_upgrade` count goes under. Like the real mod's, the key
/// goes when nothing is left under it.
fn set_installed(nbt: &mut Compound, id: &str, count: i32) {
    let key = JavaString::from("component_upgrade");
    let Tag::Compound(component) = nbt.entry(key.clone()).or_insert_with(|| Tag::Compound(Compound::new())) else {
        return;
    };
    let Tag::Compound(upgrades) = component
        .entry(JavaString::from("upgrades"))
        .or_insert_with(|| Tag::Compound(Compound::new()))
    else {
        return;
    };
    if count > 0 {
        upgrades.insert(JavaString::from(id), Tag::Int(count));
    } else {
        upgrades.remove(&JavaString::from(id));
    }
    if upgrades.is_empty() {
        nbt.remove(&key);
    }
}

fn installed_of(nbt: &Compound, id: &str) -> i32 {
    let upgrades = upgrades_of(nbt);
    if id == UPGRADE_IDS[0] { upgrades.speed as i32 } else { upgrades.energy as i32 }
}

pub(crate) fn is_ejecting(nbt: &Compound, eject: &str) -> bool {
    matches!(
        nbt.get(&JavaString::from("component_config")),
        Some(Tag::Compound(config)) if matches!(config.get(&JavaString::from(eject)), Some(Tag::Byte(1)))
    )
}

pub(crate) fn toggle_eject(nbt: &mut Compound, eject: &str) {
    let on = is_ejecting(nbt, eject);
    if let Tag::Compound(config) = nbt
        .entry(JavaString::from("component_config"))
        .or_insert_with(|| Tag::Compound(Compound::new()))
    {
        config.insert(JavaString::from(eject), Tag::Byte(i8::from(!on)));
    }
}

pub(crate) fn unpack_side(packed: i32, index: usize) -> usize {
    ((packed >> (2 * index)) & 3) as usize
}

fn side_mut<'a>(nbt: &'a mut Compound, config: &str, index: usize) -> Option<&'a mut i32> {
    let key = JavaString::from("component_config");
    let saved = nbt.entry(key).or_insert_with(|| Tag::Compound(Compound::new()));
    let Tag::Compound(saved) = saved else {
        return None;
    };
    let sides = saved
        .entry(JavaString::from(config))
        .or_insert_with(|| Tag::IntArray(vec![0; SIDES]));
    let Tag::IntArray(sides) = sides else {
        return None;
    };
    sides.get_mut(index)
}

/// Moves one side of a saved config `steps` along its cycle.
pub(crate) fn cycle_side(nbt: &mut Compound, config: &str, index: usize, cycle: &[i32], steps: usize) {
    if let Some(side) = side_mut(nbt, config, index) {
        let position = cycle.iter().position(|v| v == side).unwrap_or(0);
        *side = cycle[(position + steps) % cycle.len()];
    }
}

pub(crate) fn set_side(nbt: &mut Compound, config: &str, index: usize, value: i32) {
    if let Some(side) = side_mut(nbt, config, index) {
        *side = value;
    }
}

pub(crate) fn offset(pos: [i32; 3], side: Direction) -> [i32; 3] {
    let [dx, dy, dz] = match side {
        Direction::Down => [0, -1, 0],
        Direction::Up => [0, 1, 0],
        Direction::North => [0, 0, -1],
        Direction::South => [0, 0, 1],
        Direction::West => [-1, 0, 0],
        Direction::East => [1, 0, 0],
    };
    [pos[0] + dx, pos[1] + dy, pos[2] + dz]
}

pub(crate) fn opposite(side: Direction) -> Direction {
    match side {
        Direction::Down => Direction::Up,
        Direction::Up => Direction::Down,
        Direction::North => Direction::South,
        Direction::South => Direction::North,
        Direction::West => Direction::East,
        Direction::East => Direction::West,
    }
}

fn clockwise(side: Direction) -> Direction {
    match side {
        Direction::North => Direction::East,
        Direction::East => Direction::South,
        Direction::South => Direction::West,
        Direction::West => Direction::North,
        other => other,
    }
}

fn facing_of(name: &str) -> Direction {
    match name {
        "south" => Direction::South,
        "west" => Direction::West,
        "east" => Direction::East,
        "up" => Direction::Up,
        "down" => Direction::Down,
        _ => Direction::North,
    }
}

/// `RelativeSide.fromDirections` for a block facing a side of the compass: its index in a saved
/// side config, whose order is front, left, right, back, top, bottom.
pub(crate) fn relative_index(facing: Direction, side: Direction) -> usize {
    if side == facing {
        0
    } else if side == clockwise(facing) {
        1
    } else if side == opposite(clockwise(facing)) {
        2
    } else if side == opposite(facing) {
        3
    } else if side == Direction::Up {
        4
    } else {
        5
    }
}

pub(crate) fn energy_of(nbt: &Compound) -> i64 {
    match nbt.get(&JavaString::from("energy")) {
        Some(Tag::Int(value)) => i64::from(*value),
        Some(Tag::Long(value)) => *value,
        _ => 0,
    }
}

/// What a saved side config says about one side. Absent means `NONE`, as a block placed by a
/// command has in the real mod.
pub(crate) fn side_value(nbt: &Compound, config: &str, index: usize) -> i32 {
    let Some(Tag::Compound(saved)) = nbt.get(&JavaString::from("component_config")) else {
        return 0;
    };
    match saved.get(&JavaString::from(config)) {
        Some(Tag::IntArray(sides)) => sides.get(index).copied().unwrap_or(0),
        _ => 0,
    }
}

thread_local! {
    /// The cables of each level, in the order they first ticked, which is where a network's
    /// targets get their order. A broken cable leaves when a network is next built.
    static CABLES: RefCell<HashMap<String, Vec<[i32; 3]>>> = RefCell::new(HashMap::new());
    /// The cables whose network has ticked, so whose network has formed.
    static FORMED: RefCell<HashMap<String, Vec<[i32; 3]>>> = RefCell::new(HashMap::new());
}

/// Where a recipe type names its item input.
pub(crate) fn process_input_key(recipes: &str) -> &'static str {
    match recipes {
        "mekanism:combining" => "main_input",
        "mekanism:sawing" => "input",
        _ => "item_input",
    }
}

/// This tick's draws for a machine. A block's `test_rolls` forces them, for a recording's replay: one
/// number a tick, a multiple of the chemical amount, or 1 for a chance output and 0 for none. Only a
/// command can set it.
pub(crate) fn process_rolls(
    entity: &mut horizon_client::containers::ModBlockEntity,
    def: &mekmachine_engine::process_table::ProcessDef,
    mean: f64,
) -> mekmachine_engine::advanced::Rolls {
    use mekmachine_engine::advanced::{ROLL_ALWAYS, ROLL_NEVER, Rolls, inverse_poisson, next_unit};
    let at_key = JavaString::from("test_roll_at");
    let at = match entity.nbt.get(&at_key) {
        Some(Tag::Int(at)) => *at,
        _ => 0,
    };
    let forced = match entity.nbt.get(&JavaString::from("test_rolls")) {
        Some(Tag::IntArray(rolls)) => rolls.get(at as usize).copied(),
        _ => None,
    };
    if forced.is_some() {
        entity.nbt.insert(at_key, Tag::Int(at + 1));
    }
    Rolls {
        chemical: def.statistical.then(|| forced.map_or_else(|| inverse_poisson(mean, next_unit()), i64::from)),
        byproduct: match forced {
            Some(0) => ROLL_NEVER,
            Some(_) => ROLL_ALWAYS,
            None => next_unit(),
        },
    }
}

impl Game<'_> {
    /// `RenderUniversalCable` over `TransmitterBlockStateModel`: the model's parts for each side's
    /// connection, then, full bright, what the cable holds. The real mod's scale is the network's and
    /// fades by 0.02 a tick; here it is this cable's share of its capacity.
    pub(crate) fn mek_draw_cable(
        &self,
        state: horizon_world::registry::BlockStateId,
        entity: &horizon_client::containers::ModBlockEntity,
        draw: &mut super::native_block_entity_draw::BlockEntityDraw,
    ) {
        use mekmachine_engine::transmitter_draw::{self as plan, Part, SIDES as SIDE_NAMES};
        use mekmachine_engine::transmitter_model::{CONTENTS, SMALL};
        let tier = tiers::tier_of(&entity.id, CABLE_KIND).map_or(tiers::TIERS[0], |tier| tiers::TIERS[tier]);
        let centre_sprite = format!("mekanism:block/models/multipart/{tier}_universal_cable");
        let side_sprite = format!("{centre_sprite}_vertical");
        const ENERGY: &str = "mekanism:block/port_energy";
        const WHITE: u32 = 0xFF_FFFF;
        const FULL_BRIGHT: u32 = 240 | 240 << 8;
        const PIVOT: [f32; 3] = [0.5, 0.5, 0.5];
        let connected = SIDE_NAMES.map(|name| {
            self.native_block_state_property(state, name) == Some("true")
        });
        for part in plan::parts(connected) {
            let Part { group, centre_as_side, rotate_about } = part;
            let Some(found) = SMALL.iter().find(|each| each.name == group) else {
                continue;
            };
            draw.push();
            if let Some(axis) = rotate_about {
                draw.rotate_about(axis, plan::CONTIGUOUS_DEGREES, PIVOT);
            }
            for face in found.faces {
                let sprite: &str = if face.centre && !centre_as_side { &centre_sprite } else { &side_sprite };
                self.native_draw_quad(draw, sprite, face.corners, face.uv, WHITE);
            }
            draw.pop();
        }
        let scale = plan::contents_scale(energy_of(&entity.nbt), cable_capacity(&entity.id));
        if scale <= 0.0 {
            return;
        }
        let light = draw.light;
        draw.light = FULL_BRIGHT;
        let alpha = (scale * 255.0).round() as u32;
        for name in plan::contents_groups(connected) {
            let Some(found) = CONTENTS.iter().find(|each| each.name == name) else {
                continue;
            };
            for face in found.faces {
                let before = draw.vertices_mut().len();
                self.native_draw_quad(draw, ENERGY, face.corners, face.uv, WHITE);
                // A vertex's colour is RGBA8, with alpha in its top byte here.
                for vertex in &mut draw.vertices_mut()[before..] {
                    vertex.color = (vertex.color & 0x00FF_FFFF) | (alpha << 24);
                }
            }
        }
        draw.light = light;
    }

    /// Sends a press to the server as `native_screen_click` would. The hook that presses arrive on
    /// has no way to play the click sound.
    pub(crate) fn mek_send_menu_button(&self, button: i32) {
        let window = self.remote.as_ref().and_then(|r| r.menu.as_ref()).map(|(w, _)| *w);
        if let Some(container) = window {
            self.send(horizon_protocol::packets::play::Serverbound::ContainerButtonClick(
                horizon_protocol::packets::play::ContainerButtonClick { container, button },
            ));
        }
    }

    /// Whether a block uses `gui.rs`'s screen.
    pub(crate) fn mek_has_machine_screen(block: &str) -> bool {
        Self::mek_is_machine(block) || block == super::chem::OXIDIZER || is_cube(block)
    }

    pub(crate) fn mek_is_machine(block: &str) -> bool {
        matches!(block, "mekanism:enrichment_chamber" | "mekanism:crusher" | "mekanism:energized_smelter")
            || mekmachine_engine::process_table::process(block).is_some()
    }

    /// What an item is worth in the Heat Generator's fuel slot.
    pub(crate) fn mek_fuel_value(&self, item: &str) -> mekmachine_engine::heat_generator::FuelItem {
        let items = match &self.world_tables {
            Some(tables) => &tables.items,
            None => self.res.items(),
        };
        let stack = horizon_client::items::ItemStack::new(item, 1);
        mekmachine_engine::heat_generator::FuelItem {
            burn_time: i64::from(self.res.providers().burn_time(items, &stack, false)),
            remainder: items.get(item).and_then(|info| info.crafting_remainder.clone()),
        }
    }

    /// `TileEntityRecipeMachine.containsRecipe`.
    pub(crate) fn mek_has_recipe(&self, block: &str, stack: &horizon_client::items::ItemStack) -> bool {
        if let Some(def) = mekmachine_engine::process_table::process(block) {
            return self.native_recipes_of_type(def.recipes).iter().any(|recipe| {
                self.native_recipe_ingredient(&recipe.json[process_input_key(def.recipes)]["ingredient"])
                    .is_some_and(|ingredient| ingredient.test(stack))
            });
        }
        let kind = match block {
            "mekanism:enrichment_chamber" => "mekanism:enriching",
            "mekanism:crusher" => "mekanism:crushing",
            _ => {
                let recipes = match &self.world_tables {
                    Some(tables) => &tables.recipes,
                    None => self.res.recipes(),
                };
                return recipes.cook("minecraft:smelting", stack).is_some();
            }
        };
        self.native_recipes_of_type(kind).iter().any(|recipe| {
            self.native_recipe_ingredient(&recipe.json["input"]["ingredient"])
                .is_some_and(|ingredient| ingredient.test(stack))
        })
    }

    /// The block entity's unsaved `data`, for what `mek_saved` can't tell.
    fn mek_saved_data(&self, pos: [i32; 3]) -> &[i32] {
        match self.world.block_entities.get(&(pos[0], pos[1], pos[2])) {
            Some(horizon_client::containers::BlockEntity::Mod(entity)) => &entity.data,
            _ => &[],
        }
    }

    fn mek_saved(&self, pos: [i32; 3]) -> Option<(&str, &Compound)> {
        match self.world.block_entities.get(&(pos[0], pos[1], pos[2])) {
            Some(horizon_client::containers::BlockEntity::Mod(entity)) if !entity.id.is_empty() => {
                Some((entity.id.as_str(), &entity.nbt))
            }
            _ => None,
        }
    }

    fn mek_is_cable(&self, pos: [i32; 3]) -> bool {
        self.mek_saved(pos).is_some_and(|(id, _)| is_cable(id))
    }

    pub(crate) fn mek_register_cable(&self, pos: [i32; 3]) {
        let dimension = self.dim.id().to_owned();
        CABLES.with_borrow_mut(|cables| {
            let level = cables.entry(dimension).or_default();
            if !level.contains(&pos) {
                level.push(pos);
            }
        });
    }

    /// The cables joined to `start`, nearest first.
    fn mek_network(&self, start: [i32; 3]) -> Vec<[i32; 3]> {
        let mut found = vec![start];
        let mut next = 0;
        while next < found.len() {
            let at = found[next];
            next += 1;
            for side in DIRECTIONS {
                let neighbour = offset(at, side);
                if self.mek_is_cable(neighbour) && !found.contains(&neighbour) {
                    found.push(neighbour);
                }
            }
        }
        found
    }

    fn mek_network_energy(&self, cables: &[[i32; 3]]) -> i64 {
        cables
            .iter()
            .filter_map(|at| self.mek_saved(*at))
            .map(|(_, nbt)| energy_of(nbt))
            .sum()
    }

    /// What a machine's saved upgrades give, and whether its redstone control lets it run this tick.
    pub(crate) fn mek_may_run(&mut self, pos: [i32; 3], nbt: &Compound) -> bool {
        let control = match nbt.get(&JavaString::from("control_type")) {
            Some(Tag::String(mode)) => mode.to_string_lossy(),
            _ => return true,
        };
        let at = horizon_core::position::BlockPos::new(pos[0], pos[1], pos[2]);
        let powered = self.with_level(|b, level, ticks| b.has_neighbor_signal(level, ticks, at));
        mekmachine_engine::upgrades::may_run(&control, powered)
    }

    /// `MachineEnergyContainer`'s capacity when upgrades change it from what `energy.rs` declares.
    fn mek_usage_and_ticks(id: &str) -> Option<(i64, i32)> {
        match id {
            "mekanism:enrichment_chamber" | "mekanism:energized_smelter" => Some((5, 200)),
            "mekanism:crusher" => Some((8, 200)),
            block if mekmachine_engine::process_table::process(block).is_some() => {
                mekmachine_engine::process_table::process(block).map(|def| (def.usage, mekmachine_engine::advanced::BASE_TICKS))
            }
            super::chem::OXIDIZER => {
                use mekmachine_engine::chemical::{OXIDIZER_TICKS, OXIDIZER_USAGE};
                Some((OXIDIZER_USAGE, OXIDIZER_TICKS))
            }
            _ => None,
        }
    }

    pub(crate) fn mek_upgraded_capacity(id: &str, nbt: &Compound, data: &[i32]) -> Option<i64> {
        let (usage, ticks) = Self::mek_usage_and_ticks(id)?;
        is_recalculated(nbt, data).then(|| upgrades_of(nbt).recalculated_capacity(usage, ticks))
    }

    fn mek_cable_capacities(&self, cables: &[[i32; 3]]) -> Vec<i64> {
        cables.iter().map(|at| self.mek_saved(*at).map_or(0, |(id, _)| cable_capacity(id))).collect()
    }

    fn mek_write_cable(&mut self, pos: [i32; 3], energy: i64) {
        let key = (pos[0], pos[1], pos[2]);
        let mut seen_change = false;
        if let Some(horizon_client::containers::BlockEntity::Mod(entity)) =
            self.world.block_entities.get_mut(&key)
        {
            let before = energy_of(&entity.nbt);
            entity.nbt.insert(JavaString::from("energy"), Tag::Long(energy));
            self.world.modified.insert((key.0 >> 4, key.2 >> 4));
            // `MekanismUtils.scaleChanged`: clients hear of a change of 1% of the capacity or more.
            let capacity = cable_capacity(&entity.id).max(1);
            seen_change = before * 100 / capacity != energy * 100 / capacity;
        }
        if seen_change {
            self.native_block_entity_sync(pos);
        }
    }

    /// How much the block at `pos` will take through `side` right now.
    pub(crate) fn mek_energy_room(&mut self, pos: [i32; 3], side: Direction) -> i64 {
        let Some((id, nbt)) = self.mek_saved(pos) else {
            return 0;
        };
        if is_cable(id) {
            // A cable whose network hasn't formed yet offers only its own capacity, as the recording
            // of mixed tiers shows on its first tick.
            let dimension = self.dim.id().to_owned();
            let formed = FORMED.with_borrow(|formed| formed.get(&dimension).is_some_and(|level| level.contains(&pos)));
            let cables = if formed { self.mek_network(pos) } else { vec![pos] };
            let capacity = self.mek_cable_capacities(&cables).iter().sum::<i64>();
            return (capacity - self.mek_network_energy(&cables)).max(0);
        }
        let facing = self.mek_facing(pos);
        let index = relative_index(facing, side);
        let nbt_side = side_value(nbt, ENERGY_CONFIG, index);
        if nbt_side != SIDE_INPUT {
            return 0;
        }
        if let Some(capacity) = Self::mek_upgraded_capacity(&id, nbt, self.mek_saved_data(pos)) {
            return (capacity - energy_of(nbt)).max(0);
        }
        i64::from(self.native_energy_insert(pos, side, i32::MAX, true))
    }

    pub(crate) fn mek_facing(&self, pos: [i32; 3]) -> Direction {
        let name = self.native_block_property(pos, "facing").unwrap_or_default();
        facing_of(&name)
    }

    /// Gives the block at `pos` energy through `side`, up to what it will take. What went in.
    pub(crate) fn mek_give_energy(&mut self, pos: [i32; 3], side: Direction, amount: i64) -> i64 {
        let room = self.mek_energy_room(pos, side).min(amount);
        if room <= 0 {
            return 0;
        }
        if self.mek_is_cable(pos) {
            let held = self.mek_saved(pos).map_or(0, |(_, nbt)| energy_of(nbt));
            self.mek_write_cable(pos, held + room);
            return room;
        }
        if let Some((id, nbt)) = self.mek_saved(pos)
            && Self::mek_upgraded_capacity(&id, nbt, self.mek_saved_data(pos)).is_some()
        {
            let energy = energy_of(nbt) + room;
            let key = (pos[0], pos[1], pos[2]);
            if let Some(horizon_client::containers::BlockEntity::Mod(entity)) =
                self.world.block_entities.get_mut(&key)
            {
                entity.nbt.insert(JavaString::from("energy"), Tag::Int(energy as i32));
                self.world.modified.insert((key.0 >> 4, key.2 >> 4));
            }
            return room;
        }
        i64::from(self.native_energy_insert(pos, side, room as i32, false))
    }

    /// `EnergyUtils.emit`: splits up to `amount` among the blocks beside `pos` on `sides`.
    pub(crate) fn mek_emit(&mut self, pos: [i32; 3], sides: &[Direction], amount: i64) -> i64 {
        let targets: Vec<([i32; 3], Direction)> =
            sides.iter().map(|side| (offset(pos, *side), opposite(*side))).collect();
        self.mek_send(&targets, amount)
    }

    /// Whether the block has an energy handler on that side, which `SplitInfo` counts as a target
    /// even if it won't take anything. A side set to `NONE` has none, as air and a hopper have none.
    fn mek_has_energy_handler(&self, pos: [i32; 3], side: Direction) -> bool {
        let Some((id, nbt)) = self.mek_saved(pos) else {
            return false;
        };
        if is_cable(id) {
            return true;
        }
        if id == GENERATOR {
            return side == self.mek_facing(pos);
        }
        let state = self.world.block(pos[0], pos[1], pos[2]);
        if self.world.block_entities.mod_energy(state.0).is_none() {
            return false;
        }
        let index = relative_index(self.mek_facing(pos), side);
        side_value(nbt, ENERGY_CONFIG, index) != 0
    }

    fn mek_send(&mut self, targets: &[([i32; 3], Direction)], amount: i64) -> i64 {
        let targets: Vec<([i32; 3], Direction)> = targets
            .iter()
            .copied()
            .filter(|(at, side)| self.mek_has_energy_handler(*at, *side))
            .collect();
        let rooms: Vec<i64> = targets.iter().map(|(at, side)| self.mek_energy_room(*at, *side)).collect();
        let shares = split(amount, &rooms);
        targets
            .iter()
            .zip(shares)
            .map(|((at, side), share)| self.mek_give_energy(*at, *side, share))
            .sum()
    }

    /// `EnergyNetwork.tickEmit` and `updateSaveShares` for every network in this level. Machines
    /// have all ticked by now.
    pub(crate) fn mek_tick_networks(&mut self) {
        let dimension = self.dim.id().to_owned();
        let known = CABLES.with_borrow(|cables| cables.get(&dimension).cloned().unwrap_or_default());
        let live: Vec<[i32; 3]> = known.into_iter().filter(|at| self.mek_is_cable(*at)).collect();
        CABLES.with_borrow_mut(|cables| {
            cables.insert(dimension.clone(), live.clone());
        });
        let mut done: Vec<[i32; 3]> = Vec::new();
        for start in &live {
            if done.contains(start) {
                continue;
            }
            let joined = self.mek_network(*start);
            done.extend_from_slice(&joined);
            // Registration order, so targets come in the order the cables first ticked.
            let cables: Vec<[i32; 3]> =
                live.iter().copied().filter(|at| joined.contains(at)).collect();
            self.mek_tick_network(&cables);
        }
        FORMED.with_borrow_mut(|formed| {
            formed.insert(dimension, live);
        });
    }

    fn mek_tick_network(&mut self, cables: &[[i32; 3]]) {
        let mut targets = Vec::new();
        for cable in cables {
            for side in DIRECTIONS {
                let neighbour = offset(*cable, side);
                if !self.mek_is_cable(neighbour) {
                    targets.push((neighbour, opposite(side)));
                }
            }
        }
        let held = self.mek_network_energy(cables);
        let sent = self.mek_send(&targets, held);
        let left = held - sent;
        let room = self.mek_cable_capacities(cables);
        for (cable, share) in cables.iter().zip(split(left, &room)) {
            self.mek_write_cable(*cable, share);
        }
    }

    /// `TileComponentUpgrade`'s upgrade kind for an item in its slot.
    pub(crate) fn mek_upgrade_kind(&self, stack: &horizon_client::items::ItemStack) -> Option<&'static str> {
        if &*stack.item != UPGRADE_ITEM {
            return None;
        }
        let kind = self.native_component(stack, UPGRADE_COMPONENT).ok().flatten()?;
        let Tag::String(kind) = kind else {
            return None;
        };
        let kind = kind.to_string_lossy();
        UPGRADE_IDS.iter().find(|id| **id == kind).copied()
    }

    /// `MachineEnergyContainer.setMaxEnergy`: a smaller capacity cuts what's stored.
    fn mek_clamp_energy(entity: &mut horizon_client::containers::ModBlockEntity) {
        let Some(capacity) = Self::mek_upgraded_capacity(&entity.id, &entity.nbt, &entity.data) else {
            return;
        };
        let held = energy_of(&entity.nbt);
        if held > capacity {
            entity.nbt.insert(JavaString::from("energy"), Tag::Int(capacity as i32));
        }
    }

    /// `EnergyInventorySlot.fillContainerOrConvert`: from a charged item, or else from a conversion
    /// recipe, which only runs if all of its energy fits.
    pub(crate) fn mek_fill_energy_slot(&self, entity: &mut horizon_client::containers::ModBlockEntity, slot: usize, rate: i64) {
        let Some(stack) = entity.items.get(slot).cloned().flatten() else {
            return;
        };
        let capacity = Self::mek_capacity(&entity.id, &entity.nbt, &entity.data);
        let held = energy_of(&entity.nbt);
        let room = (capacity - held).max(0);
        if room > 0
            && let Some((moved, left)) = self.native_item_energy_extract(&stack, room.min(rate).min(i64::from(i32::MAX)) as i32)
            && moved > 0
        {
            entity.items[slot] = Some(left);
            entity.nbt.insert(JavaString::from("energy"), Tag::Int((held + i64::from(moved)) as i32));
            return;
        }
        for recipe in self.native_recipes_of_type("mekanism:energy_conversion") {
            let wanted = &recipe.json["input"];
            let Some(ingredient) = self.native_recipe_ingredient(&wanted["ingredient"]) else {
                continue;
            };
            let needed = wanted["count"].as_u64().unwrap_or(1) as u32;
            if !ingredient.test(&stack) || stack.count < needed {
                continue;
            }
            let output = recipe.json["output"].as_i64().unwrap_or(0);
            if output <= room {
                entity.items[slot] = (stack.count > needed).then(|| horizon_client::items::ItemStack {
                    count: stack.count - needed,
                    ..stack.clone()
                });
                entity.nbt.insert(JavaString::from("energy"), Tag::Int((held + output) as i32));
            }
            return;
        }
    }

    /// `EnergyInventorySlot.drainContainerIntoSlot`.
    pub(crate) fn mek_charge_slot(&self, entity: &mut horizon_client::containers::ModBlockEntity, slot: usize, rate: i64) {
        let Some(stack) = entity.items.get(slot).cloned().flatten() else {
            return;
        };
        let held = energy_of(&entity.nbt);
        let wanted = held.min(rate).min(i64::from(i32::MAX)) as i32;
        if wanted <= 0 {
            return;
        }
        if let Some((moved, charged)) = self.native_item_energy_insert(&stack, wanted)
            && moved > 0
        {
            entity.items[slot] = Some(charged);
            entity.nbt.insert(JavaString::from("energy"), Tag::Int((held - i64::from(moved)) as i32));
        }
    }

    /// What a machine holds at most right now.
    pub(crate) fn mek_capacity(id: &str, nbt: &Compound, data: &[i32]) -> i64 {
        cube_capacity(id)
            .or_else(|| Self::mek_upgraded_capacity(id, nbt, data))
            .or_else(|| Self::mek_usage_and_ticks(id).map(|(usage, ticks)| Upgrades::default().capacity(usage, ticks)))
            .unwrap_or(0)
    }

    /// What one item of `stack` converts to, by `mekanism:chemical_conversion`, if the machine's tank
    /// takes it. `containsRecipeBA` with an item in `input`, or `containsRecipeB` without one.
    pub(crate) fn mek_chemical_from(
        &self,
        stack: &horizon_client::items::ItemStack,
        def: &mekmachine_engine::process_table::ProcessDef,
        input: Option<&horizon_client::items::ItemStack>,
    ) -> Option<(String, i64)> {
        self.native_recipes_of_type("mekanism:chemical_conversion").iter().find_map(|recipe| {
            let ingredient = self.native_recipe_ingredient(&recipe.json["input"]["ingredient"])?;
            if !ingredient.test(stack) {
                return None;
            }
            let id = recipe.json["output"]["id"].as_str()?;
            self.mek_tank_takes(def, id, input)
                .then(|| Some((id.to_owned(), recipe.json["output"]["amount"].as_i64()?)))
                .flatten()
        })
    }

    /// `containsRecipeBA` or `containsRecipeB` for a machine's tank.
    pub(crate) fn mek_tank_takes(
        &self,
        def: &mekmachine_engine::process_table::ProcessDef,
        chemical: &str,
        input: Option<&horizon_client::items::ItemStack>,
    ) -> bool {
        self.native_recipes_of_type(def.recipes).iter().any(|recipe| {
            self.native_recipe_chemical_matches(&recipe.json["chemical_input"]["ingredient"], chemical)
                && input.is_none_or(|input| {
                    self.native_recipe_ingredient(&recipe.json[process_input_key(def.recipes)]["ingredient"])
                        .is_some_and(|ingredient| ingredient.test(input))
                })
        })
    }

    /// `ChemicalIngredient`: a chemical's id, or `#` and a tag. `add_machine_content.py` carries each
    /// of Mekanism's chemical tags as a recipe of type `mekmachine:chemical_tag`, since a hook has no
    /// way to read a tag registry that Horizon doesn't have.
    pub(crate) fn native_recipe_chemical_matches(&self, ingredient: &serde_json::Value, id: &str) -> bool {
        let Some(wanted) = ingredient.as_str() else {
            return false;
        };
        let Some(tag) = wanted.strip_prefix('#') else {
            return wanted == id;
        };
        self.native_recipes_of_type("mekmachine:chemical_tag").iter().any(|recipe| {
            recipe.json["tag"].as_str() == Some(tag)
                && recipe.json["values"].as_array().is_some_and(|values| values.iter().any(|value| value.as_str() == Some(id)))
        })
    }

    /// Tells the menu's slot rule what the extra slot of `def` takes, once for each machine kind.
    pub(crate) fn mek_register_extra_items(&self, def: &mekmachine_engine::process_table::ProcessDef) {
        thread_local! {
            static DONE: std::cell::RefCell<std::collections::HashSet<&'static str>> = Default::default();
        }
        if !DONE.with_borrow_mut(|done| done.insert(def.block)) {
            return;
        }
        let menu = format!("mekmachine:extra_items:{}", def.block);
        for item in self.mek_extra_items(def) {
            let (mut may_place, mut max_stack) = (true, 64);
            horizon_client::menu::native_menu_slot_rules(&menu, 0, &horizon_client::items::ItemStack::new(&item, 1), &mut may_place, &mut max_stack);
        }
    }

    /// What the extra slot of `def` takes: items that convert into its tank, or a recipe's second item.
    pub(crate) fn mek_extra_items(&self, def: &mekmachine_engine::process_table::ProcessDef) -> Vec<String> {
        use mekmachine_engine::process_table::Extra;
        let of = |json: &serde_json::Value| self.native_recipe_ingredient(json).map(|ingredient| ingredient.order).unwrap_or_default();
        match def.extra {
            Extra::ByProduct => Vec::new(),
            Extra::ItemInput => self
                .native_recipes_of_type(def.recipes)
                .iter()
                .flat_map(|recipe| of(&recipe.json["extra_input"]["ingredient"]))
                .collect(),
            Extra::Conversion => self
                .native_recipes_of_type("mekanism:chemical_conversion")
                .iter()
                .filter(|recipe| recipe.json["output"]["id"].as_str().is_some_and(|id| self.mek_tank_takes(def, id, None)))
                .flat_map(|recipe| of(&recipe.json["input"]["ingredient"]))
                .collect(),
        }
    }

    /// `TileComponentUpgrade.tickServer`.
    pub(crate) fn mek_tick_upgrades(&mut self, entity: &mut horizon_client::containers::ModBlockEntity) {
        if entity.items.len() < MACHINE_SLOTS {
            entity.items.resize(MACHINE_SLOTS, None);
        }
        // The real mod never saves an empty `component_upgrade`. A command can still give one.
        if matches!(entity.nbt.get(&JavaString::from("component_upgrade")), Some(Tag::Compound(held)) if held.is_empty()) {
            entity.nbt.remove(&JavaString::from("component_upgrade"));
        }
        // The real mod saves these slots under `component_upgrade`, so loading them recalculates.
        if (entity.items[UPGRADE_INPUT].is_some() || entity.items[UPGRADE_OUTPUT].is_some())
            && !is_recalculated(&entity.nbt, &entity.data)
        {
            mark_recalculated(&mut entity.data);
        }
        let found = entity.items[UPGRADE_INPUT].clone().and_then(|stack| {
            self.mek_upgrade_kind(&stack).map(|kind| (kind, stack.count as i32))
        });
        let ticks = match entity.nbt.get(&JavaString::from(INSTALL_TICKS_KEY)) {
            Some(Tag::Int(ticks)) => *ticks,
            _ => 0,
        };
        let Some((kind, count)) = found else {
            entity.nbt.insert(JavaString::from(INSTALL_TICKS_KEY), Tag::Int(0));
            return;
        };
        let installed = installed_of(&entity.nbt, kind);
        let (ticks, added) = mekmachine_engine::upgrades::install_tick(ticks, installed, count);
        entity.nbt.insert(JavaString::from(INSTALL_TICKS_KEY), Tag::Int(ticks));
        if added > 0 {
            set_installed(&mut entity.nbt, kind, installed + added);
            mark_recalculated(&mut entity.data);
            let left = count - added;
            entity.items[UPGRADE_INPUT] = if left > 0 {
                entity.items[UPGRADE_INPUT].clone().map(|stack| horizon_client::items::ItemStack { count: left as u32, ..stack })
            } else {
                None
            };
            Self::mek_clamp_energy(entity);
        }
    }

    /// `TileComponentUpgrade.removeUpgrade`: what the output slot can't hold stays installed. A
    /// press removes one, or with shift all of that kind.
    pub(crate) fn mek_uninstall(&mut self, entity: &mut horizon_client::containers::ModBlockEntity, kind: usize, all: bool) {
        let Some(id) = UPGRADE_IDS.get(kind).copied() else {
            return;
        };
        let installed = installed_of(&entity.nbt, id);
        if installed <= 0 {
            return;
        }
        entity.items.resize(MACHINE_SLOTS, None);
        let mut one = horizon_client::items::ItemStack::new(UPGRADE_ITEM, 1);
        if self.native_set_component(&mut one, UPGRADE_COMPONENT, Tag::String(JavaString::from(id))).is_err() {
            return;
        }
        let most = self.containers_max_stack(&one) as i32;
        let wanted = if all { installed } else { 1 };
        let (held, room) = match &entity.items[UPGRADE_OUTPUT] {
            None => (0, most),
            Some(old) if old.same_item_same_components(&one) => (old.count as i32, most - old.count as i32),
            Some(_) => return,
        };
        let removed = wanted.min(room);
        if removed <= 0 {
            return;
        }
        entity.items[UPGRADE_OUTPUT] = Some(horizon_client::items::ItemStack { count: (held + removed) as u32, ..one });
        set_installed(&mut entity.nbt, id, installed - removed);
        mark_recalculated(&mut entity.data);
        Self::mek_clamp_energy(entity);
    }

    /// `TileComponentEjector.outputItems` for one output slot: a whole stack leaves in one attempt,
    /// through each side set to output in turn. It ticks whether or not there is anything to send.
    pub(crate) fn mek_eject_items(
        &mut self,
        pos: [i32; 3],
        entity: &mut horizon_client::containers::ModBlockEntity,
        slot: usize,
    ) {
        use mekmachine_engine::upgrades::EjectTimer;
        if !is_ejecting(&entity.nbt, ITEM_EJECT) {
            return;
        }
        let key = JavaString::from("eject_delay");
        let delay = match entity.nbt.get(&key) {
            Some(Tag::Int(delay)) => *delay,
            _ => 0,
        };
        let timer = EjectTimer { delay }.tick();
        entity.nbt.insert(key, Tag::Int(timer.delay));
        if !timer.attempts {
            return;
        }
        let facing = self.mek_facing(pos);
        for side in DIRECTIONS {
            if side_value(&entity.nbt, ITEM_CONFIG, relative_index(facing, side)) != SIDE_OUTPUT {
                continue;
            }
            let Some(stack) = entity.items.get_mut(slot).and_then(Option::take) else {
                return;
            };
            let rest = self.mek_insert_item(offset(pos, side), opposite(side), stack);
            entity.items[slot] = rest;
        }
    }

    pub(crate) fn mek_is_lava(&self, pos: [i32; 3]) -> bool {
        let state = self.world.block(pos[0], pos[1], pos[2]);
        self.res.facts().get(state).fluid == horizon_client::blocks::Fluid::Lava
    }

    /// `HeatAPI.getAmbientTemp` at a position, from its biome and height.
    pub(crate) fn mek_ambient(&self, pos: [i32; 3]) -> f64 {
        const SEA_LEVEL: i32 = 63;
        let biomes = match &self.world_biomes {
            Some(biomes) => biomes,
            None => self.res.biomes(),
        };
        let Some(chunk) = self.world.chunks.get(&(pos[0] >> 4, pos[2] >> 4)) else {
            return 300.0;
        };
        let biome = &biomes.list[chunk.biome(pos[0], pos[1], pos[2]) as usize];
        let at = horizon_core::position::BlockPos::new(pos[0], pos[1], pos[2]);
        let temperature = f64::from(biome.temperature_at(at, SEA_LEVEL)).clamp(-5.0, 5.0);
        300.0 + 25.0 * (temperature - 0.8)
    }
}
