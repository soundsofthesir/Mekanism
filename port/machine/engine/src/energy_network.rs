//! A Universal Cable network's energy, as `EnergyNetwork` holds and sends it. Machines tick first,
//! then the network sends from its buffer. This covers one target; several aren't ported yet.

/// A connected group of cables.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Network {
    pub buffer: i64,
    pub capacity: i64,
}

impl Network {
    /// A machine pushes into the network: what fits is taken and answered.
    pub fn accept(&mut self, amount: i64) -> i64 {
        let taken = amount.min(self.capacity - self.buffer).max(0);
        self.buffer += taken;
        taken
    }

    /// Sends what the target has room for and answers how much went.
    pub fn emit(&mut self, room: i64) -> i64 {
        let sent = room.min(self.buffer).max(0);
        self.buffer -= sent;
        sent
    }
}

#[cfg(test)]
mod reference {
    use super::*;
    use crate::furnace::Stack;
    use crate::recipe_machine::{Machine, Recipe, Recipes};

    /// `EnergyCubeTier.BASIC`'s output per tick.
    const CUBE_OUTPUT: i64 = 4000;
    /// `CableTier.BASIC`'s capacity.
    const CABLE_CAPACITY: i64 = 8000;
    const CHAMBER_USAGE: i64 = 5;
    /// `AttributeEnergy.STORAGE_MULTIPLIER` times the usage.
    const CHAMBER_CAPACITY: i64 = 20;

    struct Iron;

    impl Recipes for Iron {
        fn find(&self, _input: &Stack) -> Option<Recipe> {
            Some(Recipe {
                id: "iron".to_owned(),
                input_count: 1,
                output: Stack::new("dust_iron", 2),
            })
        }

        fn max_stack(&self, _item: &str) -> u32 {
            64
        }
    }

    #[test]
    fn cube_through_a_cable_to_a_chamber() {
        let recording = include_str!("../../../reference/chain_cube_cable_chamber.tsv");
        let mut cube = 200_000_i64;
        let mut network = Network {
            buffer: 0,
            capacity: CABLE_CAPACITY,
        };
        let mut chamber = Machine {
            input: Some(Stack::new("iron_ore", 8)),
            ..Machine::default()
        };
        for line in recording.lines().skip(1) {
            let fields: Vec<i64> = line.split('\t').map(|f| f.parse().unwrap()).collect();
            chamber.tick(&Iron, CHAMBER_USAGE);
            cube -= network.accept(cube.min(CUBE_OUTPUT));
            chamber.energy += network.emit(CHAMBER_CAPACITY - chamber.energy);
            let got = (
                cube,
                network.buffer,
                chamber.energy,
                i64::from(chamber.progress),
            );
            assert_eq!(
                got,
                (fields[1], fields[2], fields[3], fields[4]),
                "tick {}",
                fields[0]
            );
        }
    }
}
