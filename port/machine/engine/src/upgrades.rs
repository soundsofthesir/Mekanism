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
}
