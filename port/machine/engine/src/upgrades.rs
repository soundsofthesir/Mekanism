//! `UpgradeUtils`' arithmetic for a machine's speed and energy upgrades, and `MachineEnergyContainer`'s
//! capacity. `maxUpgradeMultiplier`'s default is 10, and each upgrade's maximum is 8.

const MULTIPLIER: f64 = 10.0;
const MAX_INSTALLED: f64 = 8.0;
/// `AttributeEnergy.STORAGE_MULTIPLIER`.
const STORAGE_MULTIPLIER: i64 = 4;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Upgrades {
    pub speed: u32,
    pub energy: u32,
}

impl Upgrades {
    fn speed_share(self) -> f64 {
        f64::from(self.speed) / MAX_INSTALLED
    }

    fn energy_share(self) -> f64 {
        f64::from(self.energy) / MAX_INSTALLED
    }

    /// `getTicks`: `clampToInt` cuts off the fraction.
    pub fn ticks(self, base: i32) -> i32 {
        ((f64::from(base) * MULTIPLIER.powf(-self.speed_share())) as i32).max(1)
    }

    /// `getEnergyPerTick`.
    pub fn energy_per_tick(self, base: i64) -> i64 {
        (base as f64 * MULTIPLIER.powf(2.0 * self.speed_share() - self.energy_share())).ceil() as i64
    }

    /// What `recalculateUpgrades` sets once it has run at all, even with nothing installed: when a
    /// machine loads a saved `component_upgrade`, or after an install or an uninstall.
    pub fn recalculated_capacity(self, base_usage: i64, base_ticks: i32) -> i64 {
        self.energy_per_tick(base_usage) * i64::from(self.ticks(base_ticks).max(STORAGE_MULTIPLIER as i32))
    }

    /// `updateMaxEnergy`, which only runs once something is installed.
    pub fn capacity(self, base_usage: i64, base_ticks: i32) -> i64 {
        if self == Self::default() {
            return base_usage * STORAGE_MULTIPLIER;
        }
        self.energy_per_tick(base_usage) * STORAGE_MULTIPLIER.max(i64::from(self.ticks(base_ticks)))
    }
}

/// `RedstoneControl`: whether a machine may run. `pulse` loads as `disabled` on these machines,
/// as a recording shows, because `supportedOrNextType` skips it.
pub fn may_run(control: &str, powered: bool) -> bool {
    match control {
        "high" => powered,
        "low" => !powered,
        _ => true,
    }
}

/// `TileComponentEjector.tickDelay`: an attempt on the first tick, then one every 11 ticks.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct EjectTimer {
    pub delay: i32,
}

/// What one tick of the timer gives.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct EjectTick {
    pub delay: i32,
    pub attempts: bool,
}

/// `MekanismUtils.TICKS_PER_HALF_SECOND`.
const EJECT_DELAY: i32 = 10;

impl EjectTimer {
    pub fn tick(self) -> EjectTick {
        if self.delay == 0 {
            EjectTick { delay: EJECT_DELAY, attempts: true }
        } else {
            EjectTick { delay: self.delay - 1, attempts: false }
        }
    }
}

/// `IRedstoneControl.RedstoneControl`'s order, as saved in `control_type`. `pulse` comes last.
pub const CONTROL_MODES: [&str; 4] = ["disabled", "high", "low", "pulse"];
/// The modes a press reaches: `ITileRedstone.supportsMode` leaves out `pulse` on these machines.
const SUPPORTED_MODES: usize = 3;

/// The next mode, or the previous one for a right click (`getNext`, `getPrevious`).
pub fn next_control(mode: &str, forward: bool) -> &'static str {
    let at = CONTROL_MODES[..SUPPORTED_MODES].iter().position(|each| *each == mode).unwrap_or(0);
    let step = if forward { 1 } else { SUPPORTED_MODES - 1 };
    CONTROL_MODES[(at + step) % SUPPORTED_MODES]
}

/// `TileComponentUpgrade.UPGRADE_TICKS_REQUIRED`, `SharedConstants.TICKS_PER_SECOND`.
pub const INSTALL_TICKS: i32 = 20;
/// `Upgrade.max` of speed and energy upgrades.
pub const MAX_OF_A_KIND: i32 = 8;

/// One tick of `TileComponentUpgrade.tickServer` with a supported upgrade in the slot: the counter
/// next, and how many upgrades go in. It waits `INSTALL_TICKS` ticks and then moves all it can.
pub fn install_tick(ticks: i32, installed: i32, in_slot: i32) -> (i32, i32) {
    if installed >= MAX_OF_A_KIND {
        (0, 0)
    } else if ticks < INSTALL_TICKS {
        (ticks + 1, 0)
    } else {
        (0, (MAX_OF_A_KIND - installed).min(in_slot))
    }
}

/// Menu data slots hold 16 bits, so a larger value takes two. Its low half.
pub fn low_half(value: i64) -> i32 {
    (value & 0xFFFF) as i32
}

pub fn high_half(value: i64) -> i32 {
    ((value >> 16) & 0xFFFF) as i32
}

/// A value back from its two data slots, whichever way the network signed each half.
pub fn from_halves(low: i32, high: i32) -> i64 {
    i64::from(low & 0xFFFF) | i64::from(high & 0xFFFF) << 16
}

#[cfg(test)]
mod tests {
    use super::*;

    const CHAMBER_USAGE: i64 = 5;
    const CHAMBER_TICKS: i32 = 200;

    fn upgrades(speed: u32, energy: u32) -> Upgrades {
        Upgrades { speed, energy }
    }

    #[test]
    fn capacity_matches_the_recordings_of_a_chamber() {
        for (speed, energy, wanted) in [(0, 0, 20), (4, 0, 3150), (0, 4, 400), (0, 8, 200), (8, 8, 1000), (8, 0, 10_000)] {
            assert_eq!(upgrades(speed, energy).capacity(CHAMBER_USAGE, CHAMBER_TICKS), wanted, "{speed} {energy}");
        }
    }

    #[test]
    fn capacity_matches_the_recording_of_an_oxidizer() {
        assert_eq!(upgrades(2, 0).capacity(15, 100), 2688);
    }

    #[test]
    fn usage_and_ticks_match_the_recordings() {
        assert_eq!(upgrades(0, 4).energy_per_tick(CHAMBER_USAGE), 2);
        assert_eq!(upgrades(2, 8).energy_per_tick(CHAMBER_USAGE), 2);
        assert_eq!(upgrades(4, 0).ticks(CHAMBER_TICKS), 63);
        assert_eq!(upgrades(8, 0).ticks(CHAMBER_TICKS), 20);
        assert_eq!(upgrades(2, 0).ticks(100), 56);
    }

    #[test]
    fn redstone_control_follows_its_mode() {
        assert!(may_run("high", true) && !may_run("high", false));
        assert!(may_run("low", false) && !may_run("low", true));
        assert!(may_run("disabled", false) && may_run("pulse", false));
    }

    #[test]
    fn eject_attempts_on_ticks_1_12_23() {
        let mut timer = EjectTimer { delay: 0 };
        let mut attempts = Vec::new();
        for tick in 1..=23 {
            let next = timer.tick();
            if next.attempts {
                attempts.push(tick);
            }
            timer = EjectTimer { delay: next.delay };
        }
        assert_eq!(attempts, [1, 12, 23]);
    }

    #[test]
    fn a_value_survives_two_sixteen_bit_slots() {
        for value in [0, 1, 32_767, 32_768, 65_535, 65_536, 4_000_000, 256_000_000, 2_147_483_647] {
            let (low, high) = (low_half(value), high_half(value));
            assert_eq!(from_halves(low, high), value);
            // As a network short, sign-extended.
            assert_eq!(from_halves(i32::from(low as i16), i32::from(high as i16)), value);
        }
    }

    #[test]
    fn install_waits_then_moves_what_fits() {
        assert_eq!(install_tick(0, 0, 3), (1, 0));
        assert_eq!(install_tick(19, 0, 3), (20, 0));
        assert_eq!(install_tick(20, 0, 3), (0, 3));
        assert_eq!(install_tick(20, 7, 5), (0, 1));
        assert_eq!(install_tick(5, 8, 2), (0, 0));
    }

    #[test]
    fn control_modes_cycle_both_ways() {
        assert_eq!(next_control("disabled", true), "high");
        assert_eq!(next_control("low", true), "disabled");
        assert_eq!(next_control("disabled", false), "low");
    }
}
