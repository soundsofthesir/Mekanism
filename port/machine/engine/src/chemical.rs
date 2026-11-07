//! Chemicals: a stack, a tank, and how a tube network holds and shares what it carries. This follows
//! `BasicChemicalTank`, `DynamicBufferedResourceNetwork` and `ChemicalNetwork`.
use crate::recipe_machine::Output;
use crate::split::split;

/// `TileEntityChemicalOxidizer.MAX_GAS`.
pub const OXIDIZER_CAPACITY: i64 = 10_000;
/// `TileEntityChemicalOxidizer.BASE_TICKS_REQUIRED`.
pub const OXIDIZER_TICKS: i32 = 100;
/// `UsageConfig.chemicalOxidizer`.
pub const OXIDIZER_USAGE: i64 = 15;
/// `GeneralConfig.chemicalAutoEjectRate`.
pub const AUTO_EJECT_RATE: i64 = 1_024;
/// `ChemicalTankTier.BASIC`.
pub const BASIC_TANK_CAPACITY: i64 = 64_000;
pub const BASIC_TANK_RATE: i64 = 1_000;
/// `TubeTier.BASIC`: what each tube adds to its network's capacity.
pub const BASIC_TUBE_CAPACITY: i64 = 4_000;

/// `ChemicalStack`: some amount of one chemical.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Chem {
    pub id: String,
    pub amount: i64,
}

impl Chem {
    pub fn new(id: &str, amount: i64) -> Self {
        Self { id: id.to_owned(), amount }
    }
}

/// A tank holds one chemical at a time, up to its capacity.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Tank {
    pub capacity: i64,
    pub held: Option<Chem>,
}

impl Tank {
    pub fn new(capacity: i64, held: Option<Chem>) -> Self {
        Self { capacity, held }
    }

    /// How much of `id` would go in.
    pub fn room(&self, id: &str) -> i64 {
        match &self.held {
            Some(held) if held.id != id => 0,
            Some(held) => (self.capacity - held.amount).max(0),
            None => self.capacity,
        }
    }

    /// Adds up to `amount` of `id`, and answers what went in.
    pub fn insert(&mut self, id: &str, amount: i64) -> i64 {
        let added = self.room(id).min(amount).max(0);
        if added > 0 {
            match self.held.as_mut() {
                Some(held) => held.amount += added,
                None => self.held = Some(Chem::new(id, added)),
            }
        }
        added
    }

    /// Takes up to `amount`, and answers what came out.
    pub fn extract(&mut self, amount: i64) -> i64 {
        let Some(held) = self.held.as_mut() else {
            return 0;
        };
        let taken = held.amount.min(amount).max(0);
        held.amount -= taken;
        if held.amount == 0 {
            self.held = None;
        }
        taken
    }
}

impl Output for Tank {
    type Made = Chem;

    fn fits(&self, made: &Chem, _max_stack: &dyn Fn(&str) -> u32) -> bool {
        self.room(&made.id) >= made.amount
    }

    fn put(&mut self, made: &Chem) {
        self.insert(&made.id, made.amount);
    }
}

/// What a network's tubes hold together: the sum of their shares, of one chemical.
pub fn network_total(shares: &[Option<Chem>]) -> Option<Chem> {
    let first = shares.iter().flatten().next()?;
    let amount = shares
        .iter()
        .flatten()
        .filter(|share| share.id == first.id)
        .map(|share| share.amount)
        .sum();
    Some(Chem::new(&first.id, amount))
}

/// `updateSaveShares`: what each tube saves of what the network holds.
pub fn save_shares(total: Option<&Chem>, tubes: usize) -> Vec<Option<Chem>> {
    save_shares_by(total, &vec![BASIC_TUBE_CAPACITY; tubes])
}

/// `updateSaveShares` when tubes hold different amounts, as a network of mixed tiers does.
pub fn save_shares_by(total: Option<&Chem>, capacities: &[i64]) -> Vec<Option<Chem>> {
    let Some(total) = total else {
        return vec![None; capacities.len()];
    };
    split(total.amount, capacities)
        .into_iter()
        .map(|amount| (amount > 0).then(|| Chem::new(&total.id, amount)))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::recipe_machine::{Machine, Recipe, Recipes};
    use crate::furnace::Stack;

    const SO2: &str = "mekanism:sulfur_dioxide";

    #[test]
    fn a_tank_takes_only_its_own_chemical_up_to_capacity() {
        let mut tank = Tank::new(100, None);
        assert_eq!(tank.insert(SO2, 60), 60);
        assert_eq!(tank.insert("mekanism:hydrogen", 10), 0);
        assert_eq!(tank.insert(SO2, 60), 40);
        assert_eq!(tank.held, Some(Chem::new(SO2, 100)));
    }

    #[test]
    fn an_empty_tank_forgets_its_chemical() {
        let mut tank = Tank::new(100, Some(Chem::new(SO2, 10)));
        assert_eq!(tank.extract(25), 10);
        assert_eq!(tank.held, None);
        assert_eq!(tank.room("mekanism:hydrogen"), 100);
    }

    #[test]
    fn shares_add_back_to_the_total() {
        let shares = save_shares(Some(&Chem::new(SO2, 1000)), 3);
        assert_eq!(network_total(&shares), Some(Chem::new(SO2, 1000)));
        let amounts: Vec<i64> = shares.iter().flatten().map(|share| share.amount).collect();
        assert_eq!(amounts, vec![334, 333, 333]);
    }

    struct Oxidizing;

    impl Recipes<Chem> for Oxidizing {
        fn find(&self, input: &Stack) -> Option<Recipe<Chem>> {
            (input.item == "sulfur").then(|| Recipe {
                id: "so2".to_owned(),
                input_count: 1,
                output: Chem::new(SO2, 100),
            })
        }

        fn max_stack(&self, _item: &str) -> u32 {
            64
        }
    }

    fn oxidizer(held: Option<Chem>) -> Machine<Tank> {
        Machine {
            input: Some(Stack::new("sulfur", 2)),
            output: Tank::new(OXIDIZER_CAPACITY, held),
            energy: 10_000,
            progress: 0,
            active: false,
            recipe: None,
        }
    }

    #[test]
    fn the_oxidizer_makes_a_chemical_after_its_ticks() {
        let mut machine = oxidizer(None);
        for _ in 0..OXIDIZER_TICKS {
            machine.tick_for(&Oxidizing, OXIDIZER_USAGE, OXIDIZER_TICKS);
        }
        assert_eq!(machine.output.held, Some(Chem::new(SO2, 100)));
        assert_eq!(machine.input, Some(Stack::new("sulfur", 1)));
        assert_eq!(machine.progress, 0);
    }

    #[test]
    fn the_oxidizer_waits_when_its_tank_has_no_room() {
        let mut machine = oxidizer(Some(Chem::new(SO2, OXIDIZER_CAPACITY - 50)));
        machine.tick_for(&Oxidizing, OXIDIZER_USAGE, OXIDIZER_TICKS);
        assert_eq!(machine.progress, 0);
        assert!(!machine.active);
    }
}
