// What Mekanism's blocks share in the game: side configuration, energy between blocks, and cable
// networks. The rules that need no game types are in `mekmachine_engine`.
use mekmachine_engine::upgrades::Upgrades;
use super::Game;
use horizon_core::geometry::Direction;
use horizon_world::nbt::{Compound, JavaString, Tag};
use mekmachine_engine::split::split;
use std::{cell::RefCell, collections::HashMap};

pub(crate) const CUBE: &str = "mekanism:basic_energy_cube";
pub(crate) const CABLE: &str = "mekanism:basic_universal_cable";
pub(crate) const GENERATOR: &str = "mekanismgenerators:heat_generator";
/// `EnergyCubeTier.BASIC`.
pub(crate) const CUBE_CAPACITY: i32 = 4_000_000;
pub(crate) const CUBE_RATE: i32 = 4_000;
/// `CableTier.BASIC`: each cable adds this to its network's capacity.
const CABLE_CAPACITY: i64 = 8_000;
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

pub(crate) fn has_block_entity(block: &str) -> bool {
    matches!(
        block,
        "mekanism:enrichment_chamber" | "mekanism:crusher" | "mekanism:energized_smelter"
    ) || block == CUBE
        || block == CABLE
        || block == GENERATOR
        || matches!(block, super::chem::OXIDIZER | super::chem::TUBE | super::chem::TANK)
}

/// The side config a block's item gives it when placed (`AttachedSideConfig`). The real mod applies
/// it only to a player's placement, so a bare `setblock` there has none and one here does.
pub(crate) fn default_config(block: &str) -> Compound {
    if block == super::chem::OXIDIZER {
        return chemical_out_config();
    }
    if block == super::chem::TANK {
        return chemical_tank_config();
    }
    let (energy, items): ([i32; 6], [i32; 6]) = match block {
        CUBE => (CUBE_ENERGY_SIDES, CUBE_ITEM_SIDES),
        "mekanism:enrichment_chamber" | "mekanism:crusher" | "mekanism:energized_smelter" => {
            ([SIDE_INPUT; 6], MACHINE_ITEM_SIDES)
        }
        _ => return Compound::new(),
    };
    let mut config = Compound::new();
    config.insert(JavaString::from(ENERGY_CONFIG), Tag::IntArray(energy.to_vec()));
    config.insert(JavaString::from(ITEM_CONFIG), Tag::IntArray(items.to_vec()));
    if block == CUBE {
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
/// The menu's data slots, the same for every machine. The oxidizer also fills the chemical ones.
pub(crate) const DATA_SLOTS: usize = 10;
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
        const SIDE: &str = "mekanism:block/models/multipart/basic_universal_cable_vertical";
        const CENTRE: &str = "mekanism:block/models/multipart/basic_universal_cable";
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
                let sprite = if face.centre && !centre_as_side { CENTRE } else { SIDE };
                self.native_draw_quad(draw, sprite, face.corners, face.uv, WHITE);
            }
            draw.pop();
        }
        let scale = plan::contents_scale(energy_of(&entity.nbt), CABLE_CAPACITY);
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
        Self::mek_is_machine(block) || block == super::chem::OXIDIZER
    }

    pub(crate) fn mek_is_machine(block: &str) -> bool {
        matches!(
            block,
            "mekanism:enrichment_chamber" | "mekanism:crusher" | "mekanism:energized_smelter"
        )
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

    fn mek_saved(&self, pos: [i32; 3]) -> Option<(&str, &Compound)> {
        match self.world.block_entities.get(&(pos[0], pos[1], pos[2])) {
            Some(horizon_client::containers::BlockEntity::Mod(entity)) if !entity.id.is_empty() => {
                Some((entity.id.as_str(), &entity.nbt))
            }
            _ => None,
        }
    }

    fn mek_is_cable(&self, pos: [i32; 3]) -> bool {
        self.mek_saved(pos).is_some_and(|(id, _)| id == CABLE)
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
    fn mek_upgraded_capacity(id: &str, nbt: &Compound) -> Option<i64> {
        let (usage, ticks) = match id {
            "mekanism:enrichment_chamber" | "mekanism:energized_smelter" => (5, 200),
            "mekanism:crusher" => (8, 200),
            super::chem::OXIDIZER => {
                use mekmachine_engine::chemical::{OXIDIZER_TICKS, OXIDIZER_USAGE};
                (OXIDIZER_USAGE, OXIDIZER_TICKS)
            }
            _ => return None,
        };
        let upgrades = upgrades_of(nbt);
        (upgrades != Upgrades::default()).then(|| upgrades.capacity(usage, ticks))
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
            seen_change = before * 100 / CABLE_CAPACITY != energy * 100 / CABLE_CAPACITY;
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
        if id == CABLE {
            let cables = self.mek_network(pos);
            let capacity = cables.len() as i64 * CABLE_CAPACITY;
            return (capacity - self.mek_network_energy(&cables)).max(0);
        }
        let facing = self.mek_facing(pos);
        let index = relative_index(facing, side);
        let nbt_side = side_value(nbt, ENERGY_CONFIG, index);
        if nbt_side != SIDE_INPUT {
            return 0;
        }
        if let Some(capacity) = Self::mek_upgraded_capacity(&id, nbt) {
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
            && Self::mek_upgraded_capacity(&id, nbt).is_some()
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
        if id == CABLE {
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
            cables.insert(dimension, live.clone());
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
        let room = vec![CABLE_CAPACITY; cables.len()];
        for (cable, share) in cables.iter().zip(split(left, &room)) {
            self.mek_write_cable(*cable, share);
        }
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
