//! `TileEntityHeatGenerator`'s tick: lava and neighbouring lava become heat, and heat above the
//! surroundings' temperature becomes energy.

const HEAT_CAPACITY: f64 = 10.0;
const INVERSE_CONDUCTION: f64 = 5.0;
const INVERSE_INSULATION: f64 = 100.0;
const AIR_INVERSE_COEFFICIENT: f64 = 10_000.0;
const THERMAL_EFFICIENCY: f64 = 0.5;
/// `heatGenerationFluidRate`: the tank burns this much a tick, or nothing.
const LAVA_PER_TICK: i64 = 100;
/// `heatGeneration`.
const HEAT_FROM_LAVA: f64 = 100.0;
/// `heatGenerationLava`, per side touching lava.
const LAVA_BOOST: i32 = 7;
/// `MAX_PRODUCTION`: `heatGenerationLava` for 7 sides, `heatGenerationNether` and `heatGeneration`.
const MAX_PRODUCTION: i64 = 7 * 7 + 10 + 100;
/// `GeneratorsStorageConfig.heatGenerator`: 12 times 20 ticks a second.
const ENERGY_CAPACITY: i64 = 240;
/// `Direction.DOWN`: `TileEntityHeatGenerator` has no insulation on its bottom.
const DOWN: usize = 0;

/// The generator's saved numbers.
#[derive(Clone, Debug, PartialEq)]
pub struct HeatGenerator {
    pub heat: f64,
    pub energy: i64,
    pub lava: i64,
    pub active: bool,
}

/// What the generator's surroundings give it this tick.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Surroundings {
    /// `HeatAPI.getAmbientTemp` for each side, in `Direction` order, down first.
    pub ambient: [f64; 6],
    /// How many sides touch lava, counting lava in the block's own space.
    pub lava_sides: i32,
}

impl HeatGenerator {
    /// `ambient_here` is the block's own temperature, where each side has its own in `surroundings`.
    pub fn tick(&mut self, surroundings: &Surroundings, ambient_here: f64) {
        self.add_heat(f64::from(LAVA_BOOST * surroundings.lava_sides));
        self.active = self.lava >= LAVA_PER_TICK && self.energy < ENERGY_CAPACITY;
        if self.active {
            self.lava -= LAVA_PER_TICK;
            self.add_heat(HEAT_FROM_LAVA);
        }
        self.heat_to_energy(ambient_here);
        self.lose_heat_to_surroundings(&surroundings.ambient);
    }

    fn temperature(&self) -> f64 {
        self.heat / HEAT_CAPACITY
    }

    /// `BasicHeatCapacitor.handleHeat`: heat never goes below zero.
    fn add_heat(&mut self, amount: f64) {
        self.heat = (self.heat + amount).max(0.0);
    }

    fn heat_to_energy(&mut self, ambient: f64) {
        let temperature = self.temperature();
        let efficiency = 1.0 - ambient.min(temperature) / ambient.max(temperature);
        let lost = THERMAL_EFFICIENCY * (temperature - ambient);
        self.add_heat(-lost);
        let made = ((lost.abs() * efficiency) as i64).min(MAX_PRODUCTION);
        self.energy = (self.energy + made).min(ENERGY_CAPACITY);
    }

    fn lose_heat_to_surroundings(&mut self, ambient: &[f64; 6]) {
        for (side, ambient) in ambient.iter().enumerate() {
            let insulation = if side == DOWN {
                0.0
            } else {
                INVERSE_INSULATION
            };
            let resistance = AIR_INVERSE_COEFFICIENT + insulation + INVERSE_CONDUCTION;
            let change = (self.temperature() - ambient) / resistance;
            self.add_heat(-change * HEAT_CAPACITY);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const AMBIENT: f64 = 300.0;

    fn generator(energy: i64, lava: i64) -> HeatGenerator {
        HeatGenerator {
            heat: AMBIENT * HEAT_CAPACITY,
            energy,
            lava,
            active: false,
        }
    }

    fn tick(generator: &mut HeatGenerator) {
        let surroundings = Surroundings {
            ambient: [AMBIENT; 6],
            lava_sides: 0,
        };
        generator.tick(&surroundings, AMBIENT);
    }

    #[test]
    fn a_full_generator_burns_no_lava() {
        let mut g = generator(ENERGY_CAPACITY, 1000);
        tick(&mut g);
        assert_eq!((g.lava, g.active), (1000, false));
    }

    #[test]
    fn energy_stops_at_the_capacity() {
        let mut g = generator(ENERGY_CAPACITY - 1, 1000);
        g.heat = 6000.0;
        tick(&mut g);
        assert_eq!(g.energy, ENERGY_CAPACITY);
    }

    #[test]
    fn less_lava_than_a_tick_burns_is_left_in_the_tank() {
        let mut g = generator(0, LAVA_PER_TICK - 1);
        tick(&mut g);
        assert_eq!((g.lava, g.active), (LAVA_PER_TICK - 1, false));
    }
}

#[cfg(test)]
mod reference {
    use super::*;

    /// The biome and height at the recording's position.
    const AMBIENT: f64 = 296.875;
    /// The recording can't show each side's own temperature, so heat is compared this closely.
    /// Energy, lava and activity are compared exactly.
    const HEAT_TOLERANCE: f64 = 0.001;

    fn replay(recording: &str, lava: i64, lava_sides: i32) {
        let surroundings = Surroundings {
            ambient: [AMBIENT; 6],
            lava_sides,
        };
        let mut generator = HeatGenerator {
            heat: AMBIENT * 10.0,
            energy: 0,
            lava,
            active: false,
        };
        for line in recording.lines().skip(1) {
            let fields: Vec<&str> = line.split('\t').collect();
            generator.tick(&surroundings, AMBIENT);
            let heat: f64 = fields[1].parse().unwrap();
            assert!(
                (generator.heat - heat).abs() < HEAT_TOLERANCE,
                "tick {}: heat {} against {heat}",
                fields[0],
                generator.heat
            );
            let got = (generator.energy, generator.lava, generator.active);
            let expected = (
                fields[2].parse().unwrap(),
                fields[3].parse().unwrap(),
                fields[4] == "1",
            );
            assert_eq!(got, expected, "tick {}", fields[0]);
        }
    }

    #[test]
    fn idle() {
        replay(
            include_str!("../../../reference/heat_generator_idle.tsv"),
            0,
            0,
        );
    }

    #[test]
    fn burning_lava_from_its_tank() {
        replay(
            include_str!("../../../reference/heat_generator_lava.tsv"),
            1000,
            0,
        );
    }

    #[test]
    fn with_lava_on_one_side() {
        replay(
            include_str!("../../../reference/heat_generator_lava_above.tsv"),
            0,
            1,
        );
    }
}
