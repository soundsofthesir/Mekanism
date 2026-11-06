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
pub const ENERGY_CAPACITY: i64 = 240;
/// `HeatAPI.EPSILON`, which is Minecraft's `Constants.EPSILON`, a float widened to a double.
const HEAT_EPSILON: f64 = 1.0e-6_f32 as f64;
/// `heatTankCapacity`.
const LAVA_CAPACITY: i64 = 1000;
/// `FluidType.BUCKET_VOLUME`.
const BUCKET_LAVA: i64 = 1000;
/// A lava bucket's `COOKING_FUEL` burn time in vanilla, the divisor in `TileEntityHeatGenerator`.
const LAVA_BUCKET_BURN_TIME: i64 = 20_000;
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

/// What an item in the fuel slot is worth.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct FuelItem {
    /// Its burn time in a furnace, in ticks.
    pub burn_time: i64,
    /// What one item leaves behind: a lava bucket's bucket.
    pub remainder: Option<String>,
}

/// The fuel slot's contents and what they are worth.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FuelSlot {
    pub item: String,
    pub count: u32,
    pub value: FuelItem,
}

impl FuelSlot {
    /// `FluidFuelInventorySlot.fillOrBurn`: one item's lava goes in if all of it fits. A lava
    /// bucket's thousand millibuckets go the same way. Answers the lava added.
    fn burn_into(&mut self, room: i64) -> i64 {
        let lava = BUCKET_LAVA * self.value.burn_time / LAVA_BUCKET_BURN_TIME;
        if lava <= 0 || lava > room {
            return 0;
        }
        self.count -= 1;
        lava
    }
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
    /// `fillOrBurn` for the fuel slot: it runs before the generator burns any lava this tick.
    /// The slot comes back as it should now be, and empty when used up.
    pub fn take_fuel(&mut self, slot: Option<FuelSlot>) -> Option<(String, u32)> {
        let mut slot = slot?;
        let room = LAVA_CAPACITY - self.lava;
        let added = if room > 0 { slot.burn_into(room) } else { 0 };
        self.lava += added;
        if slot.count > 0 {
            return Some((slot.item, slot.count));
        }
        slot.value.remainder.map(|item| (item, 1))
    }

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

    /// `BasicHeatCapacitor.handleHeat`: a transfer no bigger than `HeatAPI.EPSILON` does nothing, and
    /// heat never goes below zero.
    fn add_heat(&mut self, amount: f64) {
        if amount.abs() > HEAT_EPSILON {
            self.heat = (self.heat + amount).max(0.0);
        }
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
    fn a_transfer_no_bigger_than_epsilon_does_nothing() {
        let mut g = generator(0, 0);
        let before = g.heat;
        g.add_heat(HEAT_EPSILON);
        assert_eq!(g.heat, before);
        g.add_heat(HEAT_EPSILON * 2.0);
        assert!(g.heat > before);
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
mod fuel_reference {
    use super::*;

    const AMBIENT: f64 = 296.875;
    const HEAT_TOLERANCE: f64 = 0.001;

    /// Vanilla's burn times, from its item data.
    fn value(item: &str) -> FuelItem {
        match item {
            "minecraft:coal" => FuelItem {
                burn_time: 1600,
                remainder: None,
            },
            "minecraft:blaze_rod" => FuelItem {
                burn_time: 2400,
                remainder: None,
            },
            "minecraft:lava_bucket" => FuelItem {
                burn_time: 20_000,
                remainder: Some("minecraft:bucket".to_owned()),
            },
            _ => FuelItem::default(),
        }
    }

    fn replay(recording: &str, lava: i64, item: &str, count: u32) {
        let surroundings = Surroundings {
            ambient: [AMBIENT; 6],
            lava_sides: 0,
        };
        let mut generator = HeatGenerator {
            heat: AMBIENT * 10.0,
            energy: 0,
            lava,
            active: false,
        };
        let mut slot = Some((item.to_owned(), count));
        for line in recording.lines().skip(1) {
            let fields: Vec<&str> = line.split('\t').collect();
            slot = generator.take_fuel(slot.map(|(item, count)| FuelSlot {
                value: value(&item),
                item,
                count,
            }));
            generator.tick(&surroundings, AMBIENT);
            let heat: f64 = fields[1].parse().unwrap();
            assert!(
                (generator.heat - heat).abs() < HEAT_TOLERANCE,
                "tick {}: heat {} against {heat}",
                fields[0],
                generator.heat
            );
            let shown = slot
                .as_ref()
                .map_or("-".to_owned(), |(item, count)| format!("{item}x{count}"));
            let got = (generator.energy, generator.lava, generator.active, shown);
            let expected = (
                fields[2].parse().unwrap(),
                fields[3].parse().unwrap(),
                fields[4] == "1",
                fields[5].to_owned(),
            );
            assert_eq!(got, expected, "tick {}", fields[0]);
        }
    }

    #[test]
    fn coal() {
        let recording = include_str!("../../../reference/generator_fuel_coal.tsv");
        replay(recording, 0, "minecraft:coal", 64);
    }

    #[test]
    fn a_lava_bucket() {
        let recording = include_str!("../../../reference/generator_fuel_bucket.tsv");
        replay(recording, 0, "minecraft:lava_bucket", 1);
    }

    #[test]
    fn a_lava_bucket_waits_until_it_all_fits() {
        let recording = include_str!("../../../reference/generator_fuel_bucket_no_room.tsv");
        replay(recording, 500, "minecraft:lava_bucket", 1);
    }

    #[test]
    fn the_last_blaze_rod_empties_the_slot() {
        let recording = include_str!("../../../reference/generator_fuel_blaze_rod.tsv");
        replay(recording, 0, "minecraft:blaze_rod", 2);
    }

    #[test]
    fn something_that_does_not_burn_stays() {
        let recording = include_str!("../../../reference/generator_fuel_not_fuel.tsv");
        replay(recording, 0, "minecraft:stone", 3);
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
