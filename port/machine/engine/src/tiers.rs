//! `CableTier`, `TubeTier`, `ChemicalTankTier` and `EnergyCubeTier`, without their creative tiers.

pub const TIERS: [&str; 4] = ["basic", "advanced", "elite", "ultimate"];
pub const CABLE_CAPACITY: [i64; 4] = [8_000, 128_000, 1_024_000, 8_192_000];
pub const TUBE_CAPACITY: [i64; 4] = [4_000, 16_000, 256_000, 1_024_000];
pub const TANK_CAPACITY: [i64; 4] = [64_000, 256_000, 1_024_000, 8_192_000];
pub const TANK_RATE: [i64; 4] = [1_000, 16_000, 128_000, 512_000];
pub const PIPE_CAPACITY: [i64; 4] = [2_000, 8_000, 32_000, 128_000];
pub const FLUID_TANK_CAPACITY: [i64; 4] = [32_000, 64_000, 128_000, 256_000];
pub const FLUID_TANK_RATE: [i64; 4] = [1_000, 4_000, 16_000, 64_000];
pub const CUBE_CAPACITY: [i64; 4] = [4_000_000, 16_000_000, 64_000_000, 256_000_000];
pub const CUBE_RATE: [i64; 4] = [4_000, 16_000, 64_000, 256_000];

/// Which tier a block is, for a block named `mekanism:<tier>_<kind>`.
pub fn tier_of(id: &str, kind: &str) -> Option<usize> {
    let tier = id.strip_prefix("mekanism:")?.strip_suffix(kind)?.strip_suffix('_')?;
    TIERS.iter().position(|each| *each == tier)
}

/// That tier's value, for a block of that kind.
pub fn value_of(id: &str, kind: &str, values: &[i64; 4]) -> Option<i64> {
    tier_of(id, kind).map(|tier| values[tier])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_give_their_tier() {
        assert_eq!(tier_of("mekanism:elite_universal_cable", "universal_cable"), Some(2));
        assert_eq!(tier_of("mekanism:creative_energy_cube", "energy_cube"), None);
        assert_eq!(tier_of("mekanism:basic_energy_cube", "universal_cable"), None);
        assert_eq!(value_of("mekanism:ultimate_energy_cube", "energy_cube", &CUBE_RATE), Some(256_000));
    }
}
