//! `AbstractFurnaceBlockEntity.serverTick`: the first machine on the mod hooks. The game's item,
//! recipe and fuel tables reach it through [`Facts`].

/// An item and how many.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Stack {
    pub item: String,
    pub count: u32,
}

impl Stack {
    pub fn new(item: &str, count: u32) -> Self {
        Self {
            item: item.to_owned(),
            count,
        }
    }
}

/// A cooking recipe's result and time in ticks.
#[derive(Clone, Debug, PartialEq)]
pub struct Cook {
    pub result: Stack,
    pub time: u32,
}

/// What an item does as fuel.
#[derive(Clone, Debug, PartialEq)]
pub struct Burn {
    pub time: i32,
    pub speed: f32,
    /// What is left of one item once burnt: a lava bucket's bucket.
    pub remainder: Option<String>,
}

/// What the machine asks the game.
pub trait Facts {
    fn cook(&self, input: &Stack) -> Option<Cook>;
    fn burn(&self, fuel: &Stack) -> Burn;
    fn max_stack(&self, item: &str) -> u32;
}

/// A furnace's slots and saved numbers.
#[derive(Clone, Debug, PartialEq)]
pub struct Furnace {
    pub input: Option<Stack>,
    pub fuel: Option<Stack>,
    pub output: Option<Stack>,
    pub lit_remaining: i32,
    pub lit_total: i32,
    pub cook_time: i32,
    pub cook_total: i32,
    pub speed: f32,
}

impl Default for Furnace {
    fn default() -> Self {
        Self {
            input: None,
            fuel: None,
            output: None,
            lit_remaining: 0,
            lit_total: 0,
            cook_time: 0,
            cook_total: 0,
            speed: 1.0,
        }
    }
}

const DEFAULT_COOK_TOTAL: i32 = 200;
const COOL_PER_TICK: i32 = 2;
const WET_SPONGE: &str = "minecraft:wet_sponge";
const BUCKET: &str = "minecraft:bucket";
const WATER_BUCKET: &str = "minecraft:water_bucket";

/// What one tick did besides changing the furnace.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Tick {
    /// The block's `lit` property must become this.
    pub lit_changed: Option<bool>,
    /// A fuel's remainder that had no room in the slot, dropped at the furnace.
    pub drops: Vec<Stack>,
}

impl Furnace {
    /// `setItem` on the input slot, which changed from outside the tick: anything but the same
    /// item restarts cooking, with the new input's time.
    pub fn input_changed(&mut self, facts: &dyn Facts, before: Option<&Stack>) {
        let same = matches!((before, &self.input), (Some(old), Some(new)) if old.item == new.item);
        if same {
            return;
        }
        let cook = self.input.as_ref().and_then(|input| facts.cook(input));
        self.cook_total = cook.map_or(DEFAULT_COOK_TOTAL, |cook| {
            scaled_time(cook.time, self.speed)
        });
        self.cook_time = 0;
    }

    /// The numbers and slots a comparison with another furnace looks at, one line.
    pub fn trace(&self) -> String {
        let slot = |s: &Option<Stack>| {
            s.as_ref()
                .map_or("-".to_owned(), |s| format!("{}x{}", s.item, s.count))
        };
        format!(
            "{} {} {} {} {} {} {}",
            slot(&self.input),
            slot(&self.fuel),
            slot(&self.output),
            self.lit_remaining,
            self.lit_total,
            self.cook_time,
            self.cook_total,
        )
    }

    pub fn tick(&mut self, facts: &dyn Facts) -> Tick {
        let was_lit = self.lit_remaining > 0;
        if was_lit {
            self.lit_remaining -= 1;
        }
        let mut lit = self.lit_remaining > 0;
        let mut drops = Vec::new();
        if lit || (self.input.is_some() && self.fuel.is_some()) {
            match self
                .input
                .as_ref()
                .map(|input| (input.clone(), facts.cook(input)))
            {
                Some((_, Some(cook))) => lit = self.work(facts, &cook, lit, &mut drops),
                Some((_, None)) => {}
                None => self.cook_time = 0,
            }
        } else if self.cook_time > 0 {
            self.cook_time = (self.cook_time - COOL_PER_TICK).clamp(0, self.cook_total);
        }
        Tick {
            lit_changed: (was_lit != lit).then_some(lit),
            drops,
        }
    }

    /// A tick with an input that has a recipe. Returns whether the furnace ends it lit.
    fn work(&mut self, facts: &dyn Facts, cook: &Cook, lit: bool, drops: &mut Vec<Stack>) -> bool {
        if self.cook_time == 0 {
            self.cook_total = scaled_time(cook.time, self.speed);
        }
        if !self.result_fits(facts, cook) {
            self.cook_time = 0;
            return lit;
        }
        let lit = lit || self.light(facts, cook, drops);
        if !lit {
            self.cook_time = 0;
            return false;
        }
        self.cook_time += 1;
        if self.cook_time >= self.cook_total {
            self.finish(cook);
        }
        true
    }

    fn result_fits(&self, facts: &dyn Facts, cook: &Cook) -> bool {
        self.output.as_ref().is_none_or(|out| {
            out.item == cook.result.item
                && out.count + cook.result.count <= facts.max_stack(&out.item)
        })
    }

    /// Starts burning the fuel slot's item. Returns whether it burns.
    fn light(&mut self, facts: &dyn Facts, cook: &Cook, drops: &mut Vec<Stack>) -> bool {
        let burn = self.fuel.as_ref().map_or(
            Burn {
                time: 0,
                speed: 1.0,
                remainder: None,
            },
            |fuel| facts.burn(fuel),
        );
        self.lit_remaining = burn.time;
        self.lit_total = burn.time;
        self.speed = burn.speed;
        if self.cook_total > 0 && self.cook_time < self.cook_total {
            let done = self.cook_time as f32 / self.cook_total as f32;
            self.cook_total = scaled_time(cook.time, self.speed);
            self.cook_time = (done * self.cook_total as f32).ceil() as i32;
        }
        if burn.time <= 0 {
            return false;
        }
        self.use_fuel_item(burn.remainder, drops);
        true
    }

    fn use_fuel_item(&mut self, remainder: Option<String>, drops: &mut Vec<Stack>) {
        let Some(fuel) = self.fuel.as_mut() else {
            return;
        };
        let remainder = remainder.map(|item| Stack::new(&item, 1));
        fuel.count -= 1;
        if fuel.count == 0 {
            self.fuel = remainder;
        } else {
            drops.extend(remainder);
        }
    }

    fn finish(&mut self, cook: &Cook) {
        self.cook_time = 0;
        self.cook_total = scaled_time(cook.time, self.speed);
        match self.output.as_mut() {
            Some(out) => out.count += cook.result.count,
            None => self.output = Some(cook.result.clone()),
        }
        if self
            .input
            .as_ref()
            .is_some_and(|input| input.item == WET_SPONGE)
            && self.fuel.as_ref().is_some_and(|fuel| fuel.item == BUCKET)
        {
            self.fuel = Some(Stack::new(WATER_BUCKET, 1));
        }
        if let Some(input) = self.input.as_mut() {
            input.count -= 1;
            if input.count == 0 {
                self.input = None;
            }
        }
    }
}

fn scaled_time(time: u32, speed: f32) -> i32 {
    if speed > 0.0 {
        (time as f32 / speed).ceil() as i32
    } else {
        time as i32
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const COAL_BURN: i32 = 1600;
    const LAVA_BURN: i32 = 20000;
    const IRON_COOK: i32 = 200;

    /// Vanilla's numbers for the few items these tests use.
    struct Vanilla;

    impl Facts for Vanilla {
        fn cook(&self, input: &Stack) -> Option<Cook> {
            match input.item.as_str() {
                "raw_iron" => Some(Cook {
                    result: Stack::new("iron_ingot", 1),
                    time: 200,
                }),
                "kelp" => Some(Cook {
                    result: Stack::new("dried_kelp", 1),
                    time: 100,
                }),
                _ => None,
            }
        }

        fn burn(&self, fuel: &Stack) -> Burn {
            let (time, remainder) = match fuel.item.as_str() {
                "coal" => (COAL_BURN, None),
                "lava_bucket" => (LAVA_BURN, Some("bucket".to_owned())),
                _ => (0, None),
            };
            Burn {
                time,
                speed: 1.0,
                remainder,
            }
        }

        fn max_stack(&self, item: &str) -> u32 {
            if item == "lava_bucket" { 1 } else { 64 }
        }
    }

    fn furnace(input: Option<(&str, u32)>, fuel: Option<(&str, u32)>) -> Furnace {
        let stack = |s: Option<(&str, u32)>| s.map(|(item, count)| Stack::new(item, count));
        Furnace {
            input: stack(input),
            fuel: stack(fuel),
            ..Furnace::default()
        }
    }

    fn run(f: &mut Furnace, ticks: i32) {
        for _ in 0..ticks {
            f.tick(&Vanilla);
        }
    }

    #[test]
    fn first_tick_lights_the_furnace_and_uses_a_fuel_item() {
        let mut f = furnace(Some(("raw_iron", 1)), Some(("coal", 2)));
        let tick = f.tick(&Vanilla);
        assert_eq!(tick.lit_changed, Some(true));
        assert_eq!(f.lit_remaining, COAL_BURN);
        assert_eq!(f.lit_total, COAL_BURN);
        assert_eq!(f.fuel, Some(Stack::new("coal", 1)));
        assert_eq!(f.cook_time, 1);
        assert_eq!(f.cook_total, IRON_COOK);
    }

    #[test]
    fn the_result_appears_on_the_tick_the_recipe_time_is_reached() {
        let mut f = furnace(Some(("raw_iron", 2)), Some(("coal", 1)));
        run(&mut f, IRON_COOK - 1);
        assert_eq!(f.output, None);
        assert_eq!(f.cook_time, IRON_COOK - 1);
        f.tick(&Vanilla);
        assert_eq!(f.output, Some(Stack::new("iron_ingot", 1)));
        assert_eq!(f.input, Some(Stack::new("raw_iron", 1)));
        assert_eq!(f.cook_time, 0);
    }

    #[test]
    fn a_recipe_sets_its_own_time() {
        let mut f = furnace(Some(("kelp", 1)), Some(("coal", 1)));
        f.tick(&Vanilla);
        assert_eq!(f.cook_total, 100);
    }

    #[test]
    fn one_coal_cooks_eight_items_and_then_it_goes_out() {
        let mut f = furnace(Some(("raw_iron", 64)), Some(("coal", 1)));
        run(&mut f, COAL_BURN);
        assert_eq!(f.output, Some(Stack::new("iron_ingot", 8)));
        assert_eq!(f.lit_remaining, 1);
        assert_eq!(f.cook_time, 0);
        let tick = f.tick(&Vanilla);
        assert_eq!(tick.lit_changed, Some(false));
        assert_eq!(f.lit_remaining, 0);
    }

    #[test]
    fn progress_cools_by_two_a_tick_once_it_is_out_and_stops_at_zero() {
        let mut f = furnace(Some(("raw_iron", 1)), None);
        f.lit_remaining = 1;
        f.cook_time = 3;
        f.cook_total = IRON_COOK;
        f.tick(&Vanilla);
        assert_eq!(f.cook_time, 1);
        f.tick(&Vanilla);
        assert_eq!(f.cook_time, 0);
    }

    #[test]
    fn a_stack_of_one_lava_bucket_leaves_its_bucket_in_the_slot() {
        let mut f = furnace(Some(("raw_iron", 1)), Some(("lava_bucket", 1)));
        let tick = f.tick(&Vanilla);
        assert_eq!(f.fuel, Some(Stack::new("bucket", 1)));
        assert_eq!(tick.drops, vec![]);
    }

    #[test]
    fn a_remainder_with_no_room_is_dropped() {
        let mut f = furnace(Some(("raw_iron", 1)), Some(("lava_bucket", 2)));
        let tick = f.tick(&Vanilla);
        assert_eq!(f.fuel, Some(Stack::new("lava_bucket", 1)));
        assert_eq!(tick.drops, vec![Stack::new("bucket", 1)]);
    }

    #[test]
    fn a_full_output_stops_it_and_keeps_the_fuel() {
        let mut f = furnace(Some(("raw_iron", 1)), Some(("coal", 1)));
        f.output = Some(Stack::new("iron_ingot", 64));
        let tick = f.tick(&Vanilla);
        assert_eq!(tick.lit_changed, None);
        assert_eq!(f.fuel, Some(Stack::new("coal", 1)));
        assert_eq!(f.lit_remaining, 0);
        assert_eq!(f.cook_time, 0);
    }

    #[test]
    fn an_output_of_another_item_stops_it() {
        let mut f = furnace(Some(("raw_iron", 1)), Some(("coal", 1)));
        f.output = Some(Stack::new("dried_kelp", 1));
        f.tick(&Vanilla);
        assert_eq!(f.lit_remaining, 0);
    }

    #[test]
    fn an_input_with_no_recipe_uses_no_fuel() {
        let mut f = furnace(Some(("stick", 1)), Some(("coal", 1)));
        f.tick(&Vanilla);
        assert_eq!(f.lit_remaining, 0);
        assert_eq!(f.fuel, Some(Stack::new("coal", 1)));
    }

    #[test]
    fn something_that_does_not_burn_is_left_in_the_fuel_slot() {
        let mut f = furnace(Some(("raw_iron", 1)), Some(("stick", 1)));
        let tick = f.tick(&Vanilla);
        assert_eq!(tick.lit_changed, None);
        assert_eq!(f.fuel, Some(Stack::new("stick", 1)));
        assert_eq!(f.cook_time, 0);
    }

    #[test]
    fn taking_the_input_while_lit_resets_progress() {
        let mut f = furnace(Some(("raw_iron", 1)), Some(("coal", 1)));
        run(&mut f, 50);
        f.input = None;
        f.tick(&Vanilla);
        assert_eq!(f.cook_time, 0);
        assert_eq!(f.lit_remaining, COAL_BURN - 50);
    }

    #[test]
    fn drying_a_wet_sponge_fills_a_bucket_in_the_fuel_slot() {
        struct Sponge;
        impl Facts for Sponge {
            fn cook(&self, _: &Stack) -> Option<Cook> {
                Some(Cook {
                    result: Stack::new("minecraft:sponge", 1),
                    time: 200,
                })
            }
            fn burn(&self, _: &Stack) -> Burn {
                Burn {
                    time: 0,
                    speed: 1.0,
                    remainder: None,
                }
            }
            fn max_stack(&self, _: &str) -> u32 {
                64
            }
        }
        let mut f = furnace(Some((WET_SPONGE, 1)), Some((BUCKET, 1)));
        f.lit_remaining = 1000;
        f.cook_time = 199;
        f.tick(&Sponge);
        assert_eq!(f.fuel, Some(Stack::new(WATER_BUCKET, 1)));
        assert_eq!(f.output, Some(Stack::new("minecraft:sponge", 1)));
    }

    #[test]
    fn swapping_the_input_restarts_cooking_with_the_new_recipes_time() {
        let mut f = furnace(Some(("raw_iron", 2)), Some(("coal", 1)));
        run(&mut f, 50);
        let before = f.input.take();
        f.input = Some(Stack::new("kelp", 1));
        f.input_changed(&Vanilla, before.as_ref());
        assert_eq!(f.cook_time, 0);
        assert_eq!(f.cook_total, 100);
    }

    #[test]
    fn adding_more_of_the_same_input_keeps_progress() {
        let mut f = furnace(Some(("raw_iron", 2)), Some(("coal", 1)));
        run(&mut f, 50);
        let before = f.input.clone();
        f.input = Some(Stack::new("raw_iron", 5));
        f.input_changed(&Vanilla, before.as_ref());
        assert_eq!(f.cook_time, 50);
    }
}
