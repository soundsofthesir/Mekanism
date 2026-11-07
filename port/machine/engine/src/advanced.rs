//! `TileEntityAdvancedElectricMachine`: an item input, a chemical tank and an item output, for a recipe
//! that uses chemical a tick. The recordings are `port/reference/compressor_*`.

use crate::chemical::Tank;
use crate::furnace::Stack;
use crate::recipe_machine::Output;

/// `TileEntityAdvancedElectricMachine.BASE_TICKS_REQUIRED` and `MAX_GAS`.
pub const BASE_TICKS: i32 = 200;
pub const TANK_CAPACITY: i64 = 210;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ChemicalRecipe {
    pub id: String,
    pub input_count: u32,
    pub chemical: String,
    pub amount: i64,
    pub output: Stack,
}

/// The recipes a machine can use. `chemical` is what its tank holds, if anything: a tank with no
/// chemical still matches by item, and pauses rather than resets.
pub trait ChemicalRecipes {
    fn find(&self, input: &Stack, chemical: Option<&str>) -> Option<ChemicalRecipe>;
    fn max_stack(&self, item: &str) -> u32;
}

pub struct AdvancedMachine {
    pub input: Option<Stack>,
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

impl AdvancedMachine {
    pub fn tick(&mut self, recipes: &dyn ChemicalRecipes, energy_per_tick: i64, base_total: i32, ticks_required: i32) {
        let held = self.tank.held.as_ref().map(|held| held.id.clone());
        let found = self.input.as_ref().and_then(|input| recipes.find(input, held.as_deref()));
        let Some(recipe) = found else {
            self.reset();
            return;
        };
        if self.recipe.as_ref().is_some_and(|id| *id != recipe.id) {
            self.progress = 0;
            self.used_so_far = 0;
        }
        self.recipe = Some(recipe.id.clone());
        if self.input.as_ref().is_none_or(|input| input.count < recipe.input_count) {
            self.reset();
            return;
        }
        let per_tick = recipe.amount * chemical_to_use(base_total, self.used_so_far, ticks_required, self.progress);
        let in_tank = self.tank.held.as_ref().map_or(0, |held| held.amount);
        // `recipeChemical.isEmpty()` pauses whatever this tick would use.
        let enough = in_tank > 0 && in_tank >= per_tick;
        let fits = self.output.fits(&recipe.output, &|item: &str| recipes.max_stack(item));
        if !enough || !fits || self.energy < energy_per_tick {
            self.active = false;
            return;
        }
        self.energy -= energy_per_tick;
        self.active = true;
        self.used_so_far += per_tick as i32;
        if let Some(chem) = self.tank.held.as_mut() {
            chem.amount -= per_tick;
            if chem.amount == 0 {
                self.tank.held = None;
            }
        }
        if self.progress >= ticks_required - 1 {
            self.progress = 0;
            self.used_so_far = 0;
            self.output.put(&recipe.output);
            if let Some(input) = self.input.as_mut() {
                input.count -= recipe.input_count;
                if input.count == 0 {
                    self.input = None;
                }
            }
        } else {
            self.progress += 1;
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

    struct Compressing;

    impl ChemicalRecipes for Compressing {
        fn find(&self, input: &Stack, chemical: Option<&str>) -> Option<ChemicalRecipe> {
            (input.item == "dust" && chemical.is_none_or(|held| held == "osmium")).then(|| ChemicalRecipe {
                id: "ingot".to_owned(),
                input_count: 1,
                chemical: "osmium".to_owned(),
                amount: 1,
                output: Stack::new("ingot", 1),
            })
        }
        fn max_stack(&self, _item: &str) -> u32 {
            64
        }
    }

    fn machine(tank: i64, energy: i64) -> AdvancedMachine {
        AdvancedMachine {
            input: Some(Stack::new("dust", 8)),
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
            m.tick(&Compressing, 15, BASE_TICKS, BASE_TICKS);
        }
        assert_eq!((m.progress, m.energy, m.tank.held.as_ref().map(|h| h.amount)), (0, 97_000, Some(10)));
        assert_eq!(m.output, Some(Stack::new("ingot", 1)));
        for _ in 0..11 {
            m.tick(&Compressing, 15, BASE_TICKS, BASE_TICKS);
        }
        assert_eq!((m.progress, m.active, m.tank.held.as_ref()), (10, false, None));
    }

    #[test]
    fn four_speed_upgrades_use_the_recorded_amounts() {
        let mut m = machine(210, 100_000);
        for _ in 0..66 {
            m.tick(&Compressing, 150, BASE_TICKS, 63);
        }
        assert_eq!((m.progress, m.tank.held.as_ref().map(|h| h.amount)), (3, Some(1)));
        m.tick(&Compressing, 150, BASE_TICKS, 63);
        assert_eq!((m.progress, m.active), (3, false));
    }
}
