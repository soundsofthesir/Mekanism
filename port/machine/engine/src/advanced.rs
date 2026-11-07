//! The machines in `process_table.rs`: an item input, then a tank, a second item or a chance output,
//! then an item output. This follows `ItemStackConstantChemicalToObjectCachedRecipe`,
//! `TwoInputCachedRecipe` and `OneInputCachedRecipe`. The recordings are `port/reference/`.

use crate::chemical::Tank;
use crate::furnace::Stack;
use crate::recipe_machine::Output;
use std::sync::atomic::{AtomicU64, Ordering};

/// `TileEntityAdvancedElectricMachine.BASE_TICKS_REQUIRED`, the others' and `MAX_GAS`.
pub const BASE_TICKS: i32 = 200;
pub const TANK_CAPACITY: i64 = 210;
/// `GeneralConfig.maxUpgradeMultiplier`, and the number of upgrades that reach it.
const UPGRADE_MULTIPLIER: f64 = 10.0;
const MAX_UPGRADES: f64 = 8.0;
/// A forced roll for a chance output, which is compared to the chance with `<=`.
pub const ROLL_ALWAYS: f64 = 0.0;
pub const ROLL_NEVER: f64 = 2.0;

/// What a recipe needs beside its item input.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Need {
    Nothing,
    /// A second item, used when the recipe ends.
    Item(u32),
    /// A chemical used on each tick.
    PerTick(i64),
    /// A chemical used when the recipe ends.
    AtEnd(i64),
}

#[derive(Clone, Debug, PartialEq)]
pub struct ProcessRecipe {
    pub id: String,
    pub input_count: u32,
    pub need: Need,
    pub output: Option<Stack>,
    /// `SawmillRecipe`'s secondary output and its chance.
    pub byproduct: Option<(Stack, f64)>,
}

/// The recipes a machine can use. `chemical` is what its tank holds, if anything: a tank with no
/// chemical still matches by item.
pub trait ProcessRecipes {
    fn find(&self, input: &Stack, extra: Option<&Stack>, chemical: Option<&str>) -> Option<ProcessRecipe>;
    fn max_stack(&self, item: &str) -> u32;
}

/// This tick's draws: how many times a recipe's amount `inversePoisson` asked for, if the machine's
/// use is random, and `SawmillRecipe.RANDOM`'s next double.
#[derive(Clone, Copy, Debug)]
pub struct Rolls {
    pub chemical: Option<i64>,
    pub byproduct: f64,
}

pub struct AdvancedMachine {
    pub input: Option<Stack>,
    /// A second item input or a chance output, by the machine's `Extra`.
    pub extra: Option<Stack>,
    pub output: Option<Stack>,
    pub tank: Tank,
    pub energy: i64,
    pub progress: i32,
    pub used_so_far: i32,
    pub active: bool,
    pub recipe: Option<String>,
}

/// `ChemicalUsageMultiplier.constantUse`.
pub fn chemical_to_use(base_total: i32, used_so_far: i32, ticks_required: i32, operating_ticks: i32) -> i64 {
    let base_remaining = base_total - used_so_far;
    let remaining_ticks = ticks_required - operating_ticks;
    if base_remaining < remaining_ticks {
        0
    } else if base_remaining == remaining_ticks {
        1
    } else {
        i64::from((base_remaining / remaining_ticks.max(1)).max(0))
    }
}

/// `StatUtils.inversePoisson`, with `u` as its `rand.nextDouble()`.
pub fn inverse_poisson(mean: f64, u: f64) -> i64 {
    const STIRLING_COEFF: f64 = 0.398_942_280_401_432_7;
    let r = u * mean.exp();
    let stirling = mean * std::f64::consts::E;
    let bound = 3.0 * mean.ceil();
    let (mut m, mut p) = (0.0_f64, 1.0_f64);
    while p < r && m < bound {
        m += 1.0;
        p += STIRLING_COEFF / m.sqrt() * (stirling / m).powf(m);
    }
    m as i64
}

/// `UpgradeUtils.getGasPerTickMeanMultiplier` for a machine that supports chemical upgrades, none of
/// which this port has.
pub fn chemical_mean(speed: u32) -> f64 {
    UPGRADE_MULTIPLIER.powf(2.0 * f64::from(speed) / MAX_UPGRADES)
}

/// The real mod's `RandomSource.create()` for each of these is private and unseeded, so a port has
/// no way to follow its numbers. This is its own, and leaves the level's random alone as the real one
/// does. SplitMix64.
pub fn next_unit() -> f64 {
    static STATE: AtomicU64 = AtomicU64::new(0);
    const GAMMA: u64 = 0x9E37_79B9_7F4A_7C15;
    if STATE.load(Ordering::Relaxed) == 0 {
        let now = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH);
        let seed = now.map_or(GAMMA, |since| since.as_nanos() as u64) | 1;
        let _ = STATE.compare_exchange(0, seed, Ordering::Relaxed, Ordering::Relaxed);
    }
    let mut z = STATE.fetch_add(GAMMA, Ordering::Relaxed).wrapping_add(GAMMA);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^= z >> 31;
    (z >> 11) as f64 / (1u64 << 53) as f64
}

fn take(slot: &mut Option<Stack>, count: u32) {
    if let Some(stack) = slot.as_mut() {
        stack.count -= count;
        if stack.count == 0 {
            *slot = None;
        }
    }
}

impl AdvancedMachine {
    pub fn tick(
        &mut self,
        recipes: &dyn ProcessRecipes,
        rolls: Rolls,
        energy_per_tick: i64,
        base_total: i32,
        ticks_required: i32,
    ) {
        let held = self.tank.held.as_ref().map(|held| held.id.clone());
        let found = self.input.as_ref().and_then(|input| recipes.find(input, self.extra.as_ref(), held.as_deref()));
        let Some(recipe) = found else {
            self.reset();
            return;
        };
        if self.recipe.as_ref().is_some_and(|id| *id != recipe.id) {
            self.progress = 0;
            self.used_so_far = 0;
        }
        self.recipe = Some(recipe.id.clone());
        let in_tank = self.tank.held.as_ref().map_or(0, |held| held.amount);
        let extra_count = self.extra.as_ref().map_or(0, |extra| extra.count);
        let lacking = self.input.as_ref().is_none_or(|input| input.count < recipe.input_count)
            || matches!(recipe.need, Need::Item(count) if extra_count < count)
            || matches!(recipe.need, Need::AtEnd(amount) if in_tank < amount);
        if lacking {
            self.reset();
            return;
        }
        let per_tick = match recipe.need {
            Need::PerTick(amount) => {
                let times = rolls
                    .chemical
                    .unwrap_or_else(|| chemical_to_use(base_total, self.used_so_far, ticks_required, self.progress));
                amount * times
            }
            _ => 0,
        };
        // `recipeChemical.isEmpty()` pauses whatever this tick would use.
        let enough = !matches!(recipe.need, Need::PerTick(_)) || (in_tank > 0 && in_tank >= per_tick);
        let max_stack = |item: &str| recipes.max_stack(item);
        let fits = recipe.output.as_ref().is_none_or(|made| self.output.fits(made, &max_stack))
            && recipe.byproduct.as_ref().is_none_or(|(made, _)| self.extra.fits(made, &max_stack));
        if !enough || !fits || self.energy < energy_per_tick {
            self.active = false;
            return;
        }
        self.energy -= energy_per_tick;
        self.active = true;
        self.used_so_far += per_tick as i32;
        self.drain(per_tick);
        if self.progress >= ticks_required - 1 {
            self.finish(&recipe, rolls.byproduct);
        } else {
            self.progress += 1;
        }
    }

    fn drain(&mut self, amount: i64) {
        if let Some(chem) = self.tank.held.as_mut() {
            chem.amount -= amount;
            if chem.amount == 0 {
                self.tank.held = None;
            }
        }
    }

    fn finish(&mut self, recipe: &ProcessRecipe, roll: f64) {
        self.progress = 0;
        self.used_so_far = 0;
        if let Some(made) = &recipe.output {
            self.output.put(made);
        }
        if let Some((made, chance)) = &recipe.byproduct
            && roll <= *chance
        {
            self.extra.put(made);
        }
        take(&mut self.input, recipe.input_count);
        match recipe.need {
            Need::Item(count) => take(&mut self.extra, count),
            Need::AtEnd(amount) => self.drain(amount),
            Need::Nothing | Need::PerTick(_) => {}
        }
    }

    fn reset(&mut self) {
        self.active = false;
        self.progress = 0;
        self.used_so_far = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::chemical::Chem;

    const NO_DRAW: Rolls = Rolls { chemical: None, byproduct: ROLL_NEVER };

    struct Compressing;

    impl ProcessRecipes for Compressing {
        fn find(&self, input: &Stack, _extra: Option<&Stack>, chemical: Option<&str>) -> Option<ProcessRecipe> {
            (input.item == "dust" && chemical.is_none_or(|held| held == "osmium")).then(|| ProcessRecipe {
                id: "ingot".to_owned(),
                input_count: 1,
                need: Need::PerTick(1),
                output: Some(Stack::new("ingot", 1)),
                byproduct: None,
            })
        }
        fn max_stack(&self, _item: &str) -> u32 {
            64
        }
    }

    fn machine(tank: i64, energy: i64) -> AdvancedMachine {
        AdvancedMachine {
            input: Some(Stack::new("dust", 8)),
            extra: None,
            output: None,
            tank: Tank::new(TANK_CAPACITY, (tank > 0).then(|| Chem::new("osmium", tank))),
            energy,
            progress: 0,
            used_so_far: 0,
            active: false,
            recipe: None,
        }
    }

    #[test]
    fn it_matches_the_recorded_normal_run() {
        let mut m = machine(210, 100_000);
        for _ in 0..200 {
            m.tick(&Compressing, NO_DRAW, 15, BASE_TICKS, BASE_TICKS);
        }
        assert_eq!((m.progress, m.energy, m.tank.held.as_ref().map(|h| h.amount)), (0, 97_000, Some(10)));
        assert_eq!(m.output, Some(Stack::new("ingot", 1)));
        for _ in 0..11 {
            m.tick(&Compressing, NO_DRAW, 15, BASE_TICKS, BASE_TICKS);
        }
        assert_eq!((m.progress, m.active, m.tank.held.as_ref()), (10, false, None));
    }

    #[test]
    fn four_speed_upgrades_use_the_recorded_amounts() {
        let mut m = machine(210, 100_000);
        for _ in 0..66 {
            m.tick(&Compressing, NO_DRAW, 150, BASE_TICKS, 63);
        }
        assert_eq!((m.progress, m.tank.held.as_ref().map(|h| h.amount)), (3, Some(1)));
        m.tick(&Compressing, NO_DRAW, 150, BASE_TICKS, 63);
        assert_eq!((m.progress, m.active), (3, false));
    }

    #[test]
    fn inverse_poisson_cuts_where_its_source_does() {
        // For a mean of 1 the sum `p` passes these points, in terms of `u = r / e`.
        let e = std::f64::consts::E;
        let cuts = [1.0 / e, 2.0845 / e, 2.6056 / e];
        assert_eq!(inverse_poisson(1.0, cuts[0] - 0.001), 0);
        assert_eq!(inverse_poisson(1.0, cuts[0] + 0.001), 1);
        assert_eq!(inverse_poisson(1.0, cuts[1] - 0.001), 1);
        assert_eq!(inverse_poisson(1.0, cuts[1] + 0.001), 2);
        assert_eq!(inverse_poisson(1.0, cuts[2] - 0.001), 2);
        assert_eq!(inverse_poisson(1.0, cuts[2] + 0.001), 3);
        assert_eq!(inverse_poisson(1.0, 0.9999), 3, "stops at 3 times the mean's ceiling");
    }

    #[test]
    fn next_unit_stays_in_range() {
        assert!((0..1000).map(|_| next_unit()).all(|u| (0.0..1.0).contains(&u)));
    }

    #[test]
    fn chemical_mean_at_four_speed_upgrades_is_ten() {
        assert!((chemical_mean(4) - 10.0).abs() < 1e-9);
    }
}
