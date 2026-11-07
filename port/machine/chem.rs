// Chemicals in the game: saved tanks and tube shares in the real mod's format, ejecting, and tube
// networks. The rules that need no game types are in `mekmachine_engine::chemical`.
use super::Game;
use super::mek::{DIRECTIONS, SIDE_INPUT, SIDE_OUTPUT, offset, opposite, relative_index, side_value};
use horizon_core::geometry::Direction;
use horizon_world::nbt::{Compound, JavaString, Tag};
use mekmachine_engine::chemical::{self, Chem, Tank};
use mekmachine_engine::split::split;
use std::{cell::RefCell, collections::HashMap};

pub(crate) const OXIDIZER: &str = "mekanism:chemical_oxidizer";
pub(crate) const TUBE: &str = "mekanism:basic_pressurized_tube";
pub(crate) const TANK: &str = "mekanism:basic_chemical_tank";
/// `chemical.mekanism.*` in `en_us.json`, for what `oxidizing` recipes make. The menu sends a place
/// in this list, plus one, because its data slots hold numbers.
pub(crate) const OXIDIZED: [(&str, &str); 9] = [
    ("mekanism:sulfur_dioxide", "Sulfur Dioxide"),
    ("mekanism:brine", "Gaseous Brine"),
    ("mekanism:lithium", "Lithium"),
    ("mekanism:tin", "Tin"),
    ("mekanism:bio", "Biomass"),
    ("mekanism:carbon", "Carbon"),
    ("mekanism:diamond", "Diamond"),
    ("mekanism:redstone", "Redstone"),
    ("mekanism:refined_obsidian", "Refined Obsidian"),
];
/// `TransmissionType.CHEMICAL`'s index.
pub(crate) const CHEMICAL_CONFIG: &str = "config2";
/// The oxidizer menu's data slots for what its tank holds, and its chemical sides.
pub(crate) const DATA_CHEMICAL: usize = 7;
pub(crate) const DATA_CHEMICAL_KIND: usize = 8;
pub(crate) const DATA_CHEMICAL_SIDES: usize = 9;
pub(crate) const EJECT: &str = "eject2";
const TANKS_KEY: &str = "chemical_tanks";
const STORED_KEY: &str = "stored";

/// `{amount: 100L, type: "mekanism:sulfur_dioxide"}`, the real mod's `LargeResourceStack`.
fn read_stack(tag: Option<&Tag>) -> Option<Chem> {
    let Some(Tag::Compound(stack)) = tag else {
        return None;
    };
    let amount = match stack.get(&JavaString::from("amount")) {
        Some(Tag::Long(amount)) => *amount,
        Some(Tag::Int(amount)) => i64::from(*amount),
        _ => return None,
    };
    match stack.get(&JavaString::from("type")) {
        Some(Tag::String(id)) if amount > 0 => Some(Chem::new(&id.to_string_lossy(), amount)),
        _ => None,
    }
}

fn stack_tag(chem: &Chem) -> Tag {
    let mut stack = Compound::new();
    stack.insert(JavaString::from("amount"), Tag::Long(chem.amount));
    stack.insert(JavaString::from("type"), Tag::String(JavaString::from(chem.id.as_str())));
    Tag::Compound(stack)
}

/// The first of a block's saved tanks: `chemical_tanks: [{container: 0b, stored: {...}}]`.
pub(crate) fn read_tank(nbt: &Compound, capacity: i64) -> Tank {
    let held = match nbt.get(&JavaString::from(TANKS_KEY)) {
        Some(Tag::List(tanks)) => tanks.iter().find_map(|tank| match tank {
            Tag::Compound(tank) => read_stack(tank.get(&JavaString::from(STORED_KEY))),
            _ => None,
        }),
        _ => None,
    };
    Tank::new(capacity, held)
}

/// An empty tank saves nothing, as `storeNonEmpty` does.
pub(crate) fn write_tank(nbt: &mut Compound, tank: &Tank) {
    let key = JavaString::from(TANKS_KEY);
    let Some(held) = &tank.held else {
        nbt.remove(&key);
        return;
    };
    let mut entry = Compound::new();
    entry.insert(JavaString::from("container"), Tag::Byte(0));
    entry.insert(JavaString::from(STORED_KEY), stack_tag(held));
    nbt.insert(key, Tag::List(vec![Tag::Compound(entry)]));
}

fn read_share(nbt: &Compound) -> Option<Chem> {
    read_stack(nbt.get(&JavaString::from(STORED_KEY)))
}

fn write_share(nbt: &mut Compound, share: Option<&Chem>) {
    let key = JavaString::from(STORED_KEY);
    match share {
        Some(chem) => {
            nbt.insert(key, stack_tag(chem));
        }
        None => {
            nbt.remove(&key);
        }
    }
}

pub(crate) fn tank_capacity(block: &str) -> i64 {
    if block == OXIDIZER {
        chemical::OXIDIZER_CAPACITY
    } else {
        chemical::BASIC_TANK_CAPACITY
    }
}

/// The sides a block ejects chemicals through: none unless `eject2` is on.
pub(crate) fn eject_sides(nbt: &Compound, facing: Direction) -> Vec<Direction> {
    let on = matches!(
        nbt.get(&JavaString::from("component_config")),
        Some(Tag::Compound(config)) if matches!(config.get(&JavaString::from(EJECT)), Some(Tag::Byte(1)))
    );
    if !on {
        return Vec::new();
    }
    DIRECTIONS
        .into_iter()
        .filter(|side| side_value(nbt, CHEMICAL_CONFIG, relative_index(facing, *side)) == SIDE_OUTPUT)
        .collect()
}

thread_local! {
    /// The tubes of each level, in the order they first ticked.
    static TUBES: RefCell<HashMap<String, Vec<[i32; 3]>>> = RefCell::new(HashMap::new());
}

impl Game<'_> {
    fn chem_saved(&self, pos: [i32; 3]) -> Option<(&str, &Compound)> {
        match self.world.block_entities.get(&(pos[0], pos[1], pos[2])) {
            Some(horizon_client::containers::BlockEntity::Mod(entity)) if !entity.id.is_empty() => {
                Some((entity.id.as_str(), &entity.nbt))
            }
            _ => None,
        }
    }

    fn chem_edit<R>(&mut self, pos: [i32; 3], edit: impl FnOnce(&mut Compound) -> R) -> Option<R> {
        let key = (pos[0], pos[1], pos[2]);
        let Some(horizon_client::containers::BlockEntity::Mod(entity)) =
            self.world.block_entities.get_mut(&key)
        else {
            return None;
        };
        let answer = edit(&mut entity.nbt);
        self.world.modified.insert((key.0 >> 4, key.2 >> 4));
        Some(answer)
    }

    fn chem_is_tube(&self, pos: [i32; 3]) -> bool {
        self.chem_saved(pos).is_some_and(|(id, _)| id == TUBE)
    }

    fn chem_share(&self, pos: [i32; 3]) -> Option<Chem> {
        self.chem_saved(pos).and_then(|(_, nbt)| read_share(nbt))
    }

    pub(crate) fn chem_register_tube(&self, pos: [i32; 3]) {
        let dimension = self.dim.id().to_owned();
        TUBES.with_borrow_mut(|tubes| {
            let level = tubes.entry(dimension).or_default();
            if !level.contains(&pos) {
                level.push(pos);
            }
        });
    }

    /// The tubes joined to `start`, nearest first. A tube holding another chemical doesn't join
    /// (`isValidTransmitter`).
    fn chem_network(&self, start: [i32; 3]) -> Vec<[i32; 3]> {
        let mut found = vec![start];
        let mut kind = self.chem_share(start).map(|share| share.id);
        let mut next = 0;
        while next < found.len() {
            let at = found[next];
            next += 1;
            for side in DIRECTIONS {
                let neighbour = offset(at, side);
                if !self.chem_is_tube(neighbour) || found.contains(&neighbour) {
                    continue;
                }
                let theirs = self.chem_share(neighbour).map(|share| share.id);
                if kind.is_some() && theirs.is_some() && kind != theirs {
                    continue;
                }
                kind = kind.or(theirs);
                found.push(neighbour);
            }
        }
        found
    }

    /// Whether the block has a chemical handler on that side, which a split counts as a target even
    /// if it won't take anything.
    fn chem_has_handler(&self, pos: [i32; 3], side: Direction) -> bool {
        let Some((id, nbt)) = self.chem_saved(pos) else {
            return false;
        };
        match id {
            TUBE => true,
            OXIDIZER | TANK => {
                side_value(nbt, CHEMICAL_CONFIG, relative_index(self.mek_facing(pos), side)) != 0
            }
            _ => false,
        }
    }

    /// How much of `id` the block at `pos` will take through `side`.
    fn chem_room(&self, pos: [i32; 3], side: Direction, id: &str) -> i64 {
        let Some((block, nbt)) = self.chem_saved(pos) else {
            return 0;
        };
        match block {
            TUBE => {
                let tubes = self.chem_network(pos);
                let shares: Vec<_> = tubes.iter().map(|at| self.chem_share(*at)).collect();
                let held = chemical::network_total(&shares);
                let capacity = tubes.len() as i64 * chemical::BASIC_TUBE_CAPACITY;
                Tank::new(capacity, held).room(id)
            }
            TANK => {
                let index = relative_index(self.mek_facing(pos), side);
                if side_value(nbt, CHEMICAL_CONFIG, index) == SIDE_INPUT {
                    read_tank(nbt, chemical::BASIC_TANK_CAPACITY).room(id)
                } else {
                    0
                }
            }
            _ => 0,
        }
    }

    fn chem_give(&mut self, pos: [i32; 3], chem: &Chem) {
        if chem.amount <= 0 {
            return;
        }
        let tube = self.chem_is_tube(pos);
        self.chem_edit(pos, |nbt| {
            if tube {
                let mut share = Tank::new(i64::MAX, read_share(nbt));
                share.insert(&chem.id, chem.amount);
                write_share(nbt, share.held.as_ref());
            } else {
                let mut tank = read_tank(nbt, chemical::BASIC_TANK_CAPACITY);
                tank.insert(&chem.id, chem.amount);
                write_tank(nbt, &tank);
            }
        });
    }

    /// Splits up to `amount` of `id` among the targets, and answers what went in.
    fn chem_send(&mut self, targets: &[([i32; 3], Direction)], id: &str, amount: i64) -> i64 {
        let targets: Vec<([i32; 3], Direction)> = targets
            .iter()
            .copied()
            .filter(|(at, side)| self.chem_has_handler(*at, *side))
            .collect();
        let rooms: Vec<i64> = targets.iter().map(|(at, side)| self.chem_room(*at, *side, id)).collect();
        let shares = split(amount, &rooms);
        let mut sent = 0;
        for ((at, _), share) in targets.iter().zip(shares) {
            self.chem_give(*at, &Chem::new(id, share));
            sent += share;
        }
        sent
    }

    /// `TileComponentEjector.eject` for a block's own tank, which is out of the world during its tick.
    pub(crate) fn chem_eject(&mut self, pos: [i32; 3], nbt: &Compound, tank: &mut Tank, rate: i64) {
        let Some(id) = tank.held.as_ref().map(|held| held.id.clone()) else {
            return;
        };
        let sides = eject_sides(nbt, self.mek_facing(pos));
        let targets: Vec<_> = sides.iter().map(|side| (offset(pos, *side), opposite(*side))).collect();
        let amount = tank.held.as_ref().map_or(0, |held| held.amount).min(rate);
        let sent = self.chem_send(&targets, &id, amount);
        tank.extract(sent);
    }

    /// `DynamicBufferedResourceNetwork.tickEmit` and `updateSaveShares` for this level's networks.
    pub(crate) fn chem_tick_networks(&mut self) {
        let dimension = self.dim.id().to_owned();
        let known = TUBES.with_borrow(|tubes| tubes.get(&dimension).cloned().unwrap_or_default());
        let live: Vec<[i32; 3]> = known.into_iter().filter(|at| self.chem_is_tube(*at)).collect();
        TUBES.with_borrow_mut(|tubes| {
            tubes.insert(dimension, live.clone());
        });
        let mut done: Vec<[i32; 3]> = Vec::new();
        for start in &live {
            if done.contains(start) {
                continue;
            }
            let joined = self.chem_network(*start);
            done.extend_from_slice(&joined);
            let tubes: Vec<[i32; 3]> = live.iter().copied().filter(|at| joined.contains(at)).collect();
            self.chem_tick_network(&tubes);
        }
    }

    fn chem_tick_network(&mut self, tubes: &[[i32; 3]]) {
        let shares: Vec<_> = tubes.iter().map(|at| self.chem_share(*at)).collect();
        let Some(mut held) = chemical::network_total(&shares) else {
            return;
        };
        let mut targets = Vec::new();
        for tube in tubes {
            for side in DIRECTIONS {
                let neighbour = offset(*tube, side);
                if !self.chem_is_tube(neighbour) {
                    targets.push((neighbour, opposite(side)));
                }
            }
        }
        held.amount -= self.chem_send(&targets, &held.id.clone(), held.amount);
        let left = (held.amount > 0).then_some(&held);
        for (tube, share) in tubes.iter().zip(chemical::save_shares(left, tubes.len())) {
            self.chem_edit(*tube, |nbt| write_share(nbt, share.as_ref()));
        }
    }
}
