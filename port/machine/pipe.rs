// Fluids in the game: the Fluid Tank and Mechanical Pipe networks, in the real mod's saved format. This
// follows `chem.rs`, whose tank and split rules hold for fluids too.
use super::Game;
use super::mek::{DIRECTIONS, offset};
use horizon_core::geometry::Direction;
use horizon_world::nbt::{Compound, JavaString, Tag};
use mekmachine_engine::chemical::{self, Chem, Tank};
use mekmachine_engine::split::split;
use mekmachine_engine::tiers;
use std::{cell::RefCell, collections::HashMap};

const PIPE_KIND: &str = "mechanical_pipe";
const TANK_KIND: &str = "fluid_tank";
const TANKS_KEY: &str = "fluid_tanks";
const STORED_KEY: &str = "stored";

pub(crate) fn is_pipe(block: &str) -> bool {
    tiers::tier_of(block, PIPE_KIND).is_some()
}

pub(crate) fn is_tank(block: &str) -> bool {
    tiers::tier_of(block, TANK_KIND).is_some()
}

fn pipe_capacity(block: &str) -> i64 {
    tiers::value_of(block, PIPE_KIND, &tiers::PIPE_CAPACITY).unwrap_or(0)
}

fn tank_capacity(block: &str) -> i64 {
    tiers::value_of(block, TANK_KIND, &tiers::FLUID_TANK_CAPACITY).unwrap_or(0)
}

/// `{amount: 100L, type: {id: "minecraft:water"}}`.
fn read_stack(tag: Option<&Tag>) -> Option<Chem> {
    let Some(Tag::Compound(stack)) = tag else {
        return None;
    };
    let amount = match stack.get(&JavaString::from("amount")) {
        Some(Tag::Long(amount)) => *amount,
        Some(Tag::Int(amount)) => i64::from(*amount),
        _ => return None,
    };
    let Some(Tag::Compound(kind)) = stack.get(&JavaString::from("type")) else {
        return None;
    };
    match kind.get(&JavaString::from("id")) {
        Some(Tag::String(id)) if amount > 0 => Some(Chem::new(&id.to_string_lossy(), amount)),
        _ => None,
    }
}

fn stack_tag(fluid: &Chem) -> Tag {
    let mut kind = Compound::new();
    kind.insert(JavaString::from("id"), Tag::String(JavaString::from(fluid.id.as_str())));
    let mut stack = Compound::new();
    stack.insert(JavaString::from("amount"), Tag::Long(fluid.amount));
    stack.insert(JavaString::from("type"), Tag::Compound(kind));
    Tag::Compound(stack)
}

fn read_tank(nbt: &Compound, capacity: i64) -> Tank {
    let held = match nbt.get(&JavaString::from(TANKS_KEY)) {
        Some(Tag::List(list)) => match list.first() {
            Some(Tag::Compound(entry)) => read_stack(entry.get(&JavaString::from(STORED_KEY))),
            _ => None,
        },
        _ => None,
    };
    let mut tank = Tank::new(capacity, None);
    tank.held = held;
    tank
}

fn write_tank(nbt: &mut Compound, tank: &Tank) {
    let key = JavaString::from(TANKS_KEY);
    match &tank.held {
        Some(fluid) => {
            let mut entry = Compound::new();
            entry.insert(JavaString::from("container"), Tag::Byte(0));
            entry.insert(JavaString::from(STORED_KEY), stack_tag(fluid));
            nbt.insert(key, Tag::List(vec![Tag::Compound(entry)]));
        }
        None => {
            nbt.remove(&key);
        }
    }
}

fn read_share(nbt: &Compound) -> Option<Chem> {
    read_stack(nbt.get(&JavaString::from(STORED_KEY)))
}

fn write_share(nbt: &mut Compound, share: Option<&Chem>) {
    let key = JavaString::from(STORED_KEY);
    match share {
        Some(fluid) => {
            nbt.insert(key, stack_tag(fluid));
        }
        None => {
            nbt.remove(&key);
        }
    }
}

fn is_active(nbt: &Compound) -> bool {
    matches!(nbt.get(&JavaString::from("active_state")), Some(Tag::Byte(1) | Tag::Int(1)))
}

thread_local! {
    /// The pipes of each level, in the order they first ticked.
    static PIPES: RefCell<HashMap<String, Vec<[i32; 3]>>> = RefCell::new(HashMap::new());
    /// The pipes whose network has ticked, so whose network has formed.
    static FORMED: RefCell<HashMap<String, Vec<[i32; 3]>>> = RefCell::new(HashMap::new());
}

impl Game<'_> {
    fn pipe_is_pipe(&self, pos: [i32; 3]) -> bool {
        self.chem_saved(pos).is_some_and(|(id, _)| is_pipe(id))
    }

    fn pipe_share(&self, pos: [i32; 3]) -> Option<Chem> {
        self.chem_saved(pos).and_then(|(_, nbt)| read_share(nbt))
    }

    pub(crate) fn pipe_register(&self, pos: [i32; 3]) {
        let dimension = self.dim.id().to_owned();
        PIPES.with_borrow_mut(|pipes| {
            let level = pipes.entry(dimension).or_default();
            if !level.contains(&pos) {
                level.push(pos);
            }
        });
    }

    /// The pipes joined to `start`, nearest first. One holding another fluid doesn't join.
    fn pipe_network(&self, start: [i32; 3]) -> Vec<[i32; 3]> {
        let mut found = vec![start];
        let mut kind = self.pipe_share(start).map(|share| share.id);
        let mut next = 0;
        while next < found.len() {
            let at = found[next];
            next += 1;
            for side in DIRECTIONS {
                let neighbour = offset(at, side);
                if !self.pipe_is_pipe(neighbour) || found.contains(&neighbour) {
                    continue;
                }
                let theirs = self.pipe_share(neighbour).map(|share| share.id);
                if kind.is_some() && theirs.is_some() && kind != theirs {
                    continue;
                }
                kind = kind.or(theirs);
                found.push(neighbour);
            }
        }
        found
    }

    fn pipe_capacities(&self, pipes: &[[i32; 3]]) -> Vec<i64> {
        pipes.iter().map(|at| self.chem_saved(*at).map_or(0, |(id, _)| pipe_capacity(id))).collect()
    }

    /// How much of `id` the block at `pos` will take. A pipe whose network hasn't formed yet offers
    /// only its own capacity, as the recordings of chains and mixed tiers show on their first tick.
    fn pipe_room(&self, pos: [i32; 3], id: &str) -> i64 {
        let Some((block, nbt)) = self.chem_saved(pos) else {
            return 0;
        };
        if is_pipe(block) {
            let dimension = self.dim.id().to_owned();
            let formed = FORMED.with_borrow(|formed| formed.get(&dimension).is_some_and(|level| level.contains(&pos)));
            let pipes = if formed { self.pipe_network(pos) } else { vec![pos] };
            let shares: Vec<_> = pipes.iter().map(|at| self.pipe_share(*at)).collect();
            let capacity = self.pipe_capacities(&pipes).iter().sum::<i64>();
            return Tank::new(capacity, chemical::network_total(&shares)).room(id);
        }
        if is_tank(block) {
            return read_tank(nbt, tank_capacity(block)).room(id);
        }
        0
    }

    fn pipe_give(&mut self, pos: [i32; 3], fluid: &Chem) {
        if fluid.amount <= 0 {
            return;
        }
        let pipe = self.pipe_is_pipe(pos);
        let capacity = self.chem_saved(pos).map_or(0, |(id, _)| tank_capacity(id));
        self.chem_edit(pos, |nbt| {
            if pipe {
                let mut share = Tank::new(i64::MAX, read_share(nbt));
                share.insert(&fluid.id, fluid.amount);
                write_share(nbt, share.held.as_ref());
            } else {
                let mut tank = read_tank(nbt, capacity);
                tank.insert(&fluid.id, fluid.amount);
                write_tank(nbt, &tank);
            }
        });
    }

    /// `EmitUtils.sendToAcceptors`: anything with a fluid handler counts as a target.
    fn pipe_send(&mut self, targets: &[[i32; 3]], id: &str, amount: i64) -> i64 {
        let targets: Vec<[i32; 3]> = targets
            .iter()
            .copied()
            .filter(|at| self.chem_saved(*at).is_some_and(|(block, _)| is_pipe(block) || is_tank(block)))
            .collect();
        let rooms: Vec<i64> = targets.iter().map(|at| self.pipe_room(*at, id)).collect();
        let shares = split(amount, &rooms);
        let mut sent = 0;
        for (at, share) in targets.iter().zip(shares) {
            self.pipe_give(*at, &Chem::new(id, share));
            sent += share;
        }
        sent
    }

    /// `TileEntityFluidTank.onUpdateServer`: an active tank emits downwards. To another tank it
    /// sends no more than that tank needs.
    pub(crate) fn pipe_tick_tank(&mut self, pos: [i32; 3], entity: &mut horizon_client::containers::ModBlockEntity) {
        let rate = tiers::value_of(&entity.id, TANK_KIND, &tiers::FLUID_TANK_RATE).unwrap_or(0);
        let mut tank = read_tank(&entity.nbt, tank_capacity(&entity.id));
        let Some(held) = tank.held.clone() else {
            return;
        };
        if !is_active(&entity.nbt) {
            return;
        }
        let below = offset(pos, Direction::Down);
        let is_tank_at_below = self.chem_saved(below).is_some_and(|(block, _)| is_tank(block));
        let mut amount = held.amount.min(rate);
        if is_tank_at_below {
            amount = amount.min(self.pipe_room(below, &held.id));
        }
        tank.extract(self.pipe_send(&[below], &held.id, amount));
        write_tank(&mut entity.nbt, &tank);
    }

    pub(crate) fn pipe_tick_networks(&mut self) {
        let dimension = self.dim.id().to_owned();
        let known = PIPES.with_borrow(|pipes| pipes.get(&dimension).cloned().unwrap_or_default());
        let live: Vec<[i32; 3]> = known.into_iter().filter(|at| self.pipe_is_pipe(*at)).collect();
        PIPES.with_borrow_mut(|pipes| {
            pipes.insert(dimension.clone(), live.clone());
        });
        let mut done: Vec<[i32; 3]> = Vec::new();
        for start in &live {
            if done.contains(start) {
                continue;
            }
            let joined = self.pipe_network(*start);
            done.extend_from_slice(&joined);
            let pipes: Vec<[i32; 3]> = live.iter().copied().filter(|at| joined.contains(at)).collect();
            self.pipe_tick_network(&pipes);
        }
        FORMED.with_borrow_mut(|formed| {
            formed.insert(dimension, live);
        });
    }

    fn pipe_tick_network(&mut self, pipes: &[[i32; 3]]) {
        let shares: Vec<_> = pipes.iter().map(|at| self.pipe_share(*at)).collect();
        let Some(mut held) = chemical::network_total(&shares) else {
            return;
        };
        let mut targets = Vec::new();
        for pipe in pipes {
            for side in DIRECTIONS {
                let neighbour = offset(*pipe, side);
                if !self.pipe_is_pipe(neighbour) {
                    targets.push(neighbour);
                }
            }
        }
        held.amount -= self.pipe_send(&targets, &held.id.clone(), held.amount);
        let left = (held.amount > 0).then_some(&held);
        let capacities = self.pipe_capacities(pipes);
        for (pipe, share) in pipes.iter().zip(chemical::save_shares_by(left, &capacities)) {
            self.chem_edit(*pipe, |nbt| write_share(nbt, share.as_ref()));
        }
    }
}
