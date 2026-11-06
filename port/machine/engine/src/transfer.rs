//! What a machine does with its own energy and fluid during its tick. Horizon takes a block entity
//! out of the world while it ticks, so its helpers can't move anything out of the ticking block:
//! the machine offers to its neighbour and subtracts what the neighbour took.

/// An energy store: what it holds and the most it can hold.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Buffer {
    pub amount: i32,
    pub capacity: i32,
}

impl Buffer {
    /// Adds up to `rate`, stopping at the capacity.
    pub fn generate(&mut self, rate: i32) {
        self.amount = self.amount.saturating_add(rate).min(self.capacity);
    }

    /// Offers up to `limit` to `accept`, which answers how much it took.
    pub fn push(&mut self, limit: i32, accept: impl FnOnce(i32) -> i32) -> i32 {
        let offered = self.amount.min(limit);
        if offered <= 0 {
            return 0;
        }
        let taken = accept(offered).clamp(0, offered);
        self.amount -= taken;
        taken
    }
}

/// One tank: its fluid, what it holds and the most it can hold.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Tank {
    pub fluid: Option<String>,
    pub amount: i32,
    pub capacity: i32,
}

impl Tank {
    /// Adds up to `amount` of `fluid`, if the tank is empty or holds it. Answers what didn't fit.
    pub fn fill(&mut self, fluid: &str, amount: i32) -> i32 {
        if self.fluid.as_deref().is_some_and(|held| held != fluid) {
            return amount;
        }
        let taken = amount.min(self.capacity - self.amount).max(0);
        if taken > 0 {
            self.fluid = Some(fluid.to_owned());
            self.amount += taken;
        }
        amount - taken
    }

    /// Offers up to `limit` to `insert`, which answers what did not fit, as Horizon's does.
    pub fn push(&mut self, limit: i32, insert: impl FnOnce(&str, i32) -> i32) -> i32 {
        let offered = self.amount.min(limit);
        let Some(fluid) = self.fluid.as_deref().filter(|_| offered > 0) else {
            return 0;
        };
        let left = insert(fluid, offered).clamp(0, offered);
        let moved = offered - left;
        self.amount -= moved;
        if self.amount == 0 {
            self.fluid = None;
        }
        moved
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn buffer(amount: i32) -> Buffer {
        Buffer {
            amount,
            capacity: 1000,
        }
    }

    fn water(amount: i32) -> Tank {
        Tank {
            fluid: Some("minecraft:water".to_owned()),
            amount,
            capacity: 1000,
        }
    }

    #[test]
    fn generating_stops_at_the_capacity() {
        let mut b = buffer(990);
        b.generate(40);
        assert_eq!(b.amount, 1000);
    }

    #[test]
    fn a_push_offers_the_limit_and_keeps_what_was_refused() {
        let mut b = buffer(500);
        let mut offered = 0;
        let moved = b.push(100, |amount| {
            offered = amount;
            30
        });
        assert_eq!(offered, 100);
        assert_eq!(moved, 30);
        assert_eq!(b.amount, 470);
    }

    #[test]
    fn a_push_offers_no_more_than_it_holds() {
        let mut b = buffer(20);
        let mut offered = 0;
        b.push(100, |amount| {
            offered = amount;
            amount
        });
        assert_eq!(offered, 20);
        assert_eq!(b.amount, 0);
    }

    #[test]
    fn an_empty_buffer_offers_nothing() {
        let mut b = buffer(0);
        assert_eq!(b.push(100, |_| panic!("offered from an empty buffer")), 0);
    }

    #[test]
    fn filling_an_empty_tank_sets_its_fluid() {
        let mut t = Tank {
            fluid: None,
            amount: 0,
            capacity: 1000,
        };
        assert_eq!(t.fill("minecraft:lava", 200), 0);
        assert_eq!(t.fluid.as_deref(), Some("minecraft:lava"));
        assert_eq!(t.amount, 200);
    }

    #[test]
    fn a_tank_answers_what_did_not_fit() {
        let mut t = water(900);
        assert_eq!(t.fill("minecraft:water", 300), 200);
        assert_eq!(t.amount, 1000);
    }

    #[test]
    fn a_tank_refuses_another_fluid() {
        let mut t = water(100);
        assert_eq!(t.fill("minecraft:lava", 300), 300);
        assert_eq!(t.fluid.as_deref(), Some("minecraft:water"));
        assert_eq!(t.amount, 100);
    }

    #[test]
    fn a_tank_push_keeps_what_did_not_fit() {
        let mut t = water(500);
        let moved = t.push(100, |fluid, amount| {
            assert_eq!(fluid, "minecraft:water");
            assert_eq!(amount, 100);
            40
        });
        assert_eq!(moved, 60);
        assert_eq!(t.amount, 440);
    }

    #[test]
    fn a_tank_emptied_by_a_push_has_no_fluid() {
        let mut t = water(50);
        assert_eq!(t.push(100, |_, _| 0), 50);
        assert_eq!(t.fluid, None);
        assert_eq!(t.amount, 0);
    }

    #[test]
    fn an_empty_tank_offers_nothing() {
        let mut t = Tank {
            fluid: None,
            amount: 0,
            capacity: 1000,
        };
        assert_eq!(t.push(100, |_, _| panic!("offered from an empty tank")), 0);
    }
}
