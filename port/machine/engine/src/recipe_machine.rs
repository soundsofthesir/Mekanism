//! Mekanism's one-input machines: the Enrichment Chamber, Crusher, Energized Smelter and, with a
//! chemical output, the Chemical Oxidizer. This follows `CachedRecipe.process` with
//! `OneInputCachedRecipe`, without upgrades.
use crate::furnace::Stack;

/// `TileEntityElectricMachine.BASE_TICKS_REQUIRED`.
pub const TICKS_REQUIRED: i32 = 200;

/// A recipe that matches an input.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Recipe<M = Stack> {
    pub id: String,
    pub input_count: u32,
    pub output: M,
}

/// What the machine asks the game.
pub trait Recipes<M = Stack> {
    fn find(&self, input: &Stack) -> Option<Recipe<M>>;
    fn max_stack(&self, item: &str) -> u32;
}

/// Where a machine puts what it makes: an item slot or a chemical tank.
pub trait Output {
    type Made;
    fn fits(&self, made: &Self::Made, max_stack: &dyn Fn(&str) -> u32) -> bool;
    fn put(&mut self, made: &Self::Made);
}

impl Output for Option<Stack> {
    type Made = Stack;

    fn fits(&self, made: &Stack, max_stack: &dyn Fn(&str) -> u32) -> bool {
        self.as_ref()
            .is_none_or(|out| out.item == made.item && out.count + made.count <= max_stack(&out.item))
    }

    fn put(&mut self, made: &Stack) {
        match self.as_mut() {
            Some(out) => out.count += made.count,
            None => *self = Some(made.clone()),
        }
    }
}

/// A machine's slots and saved numbers.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Machine<O = Option<Stack>> {
    pub input: Option<Stack>,
    pub output: O,
    pub energy: i64,
    pub progress: i32,
    pub active: bool,
    /// The recipe the progress belongs to.
    pub recipe: Option<String>,
}

impl<O: Output> Machine<O> {
    pub fn tick(&mut self, recipes: &dyn Recipes<O::Made>, energy_per_tick: i64) {
        self.tick_for(recipes, energy_per_tick, TICKS_REQUIRED);
    }

    pub fn tick_for(&mut self, recipes: &dyn Recipes<O::Made>, energy_per_tick: i64, ticks_required: i32) {
        let found = self.input.as_ref().and_then(|input| recipes.find(input));
        let Some(recipe) = found else {
            self.stop_and_reset();
            return;
        };
        if self.recipe.as_ref().is_some_and(|id| *id != recipe.id) {
            self.progress = 0;
        }
        self.recipe = Some(recipe.id.clone());
        if self
            .input
            .as_ref()
            .is_none_or(|input| input.count < recipe.input_count)
        {
            self.stop_and_reset();
            return;
        }
        let fits = self.output.fits(&recipe.output, &|item: &str| recipes.max_stack(item));
        if !fits || self.energy < energy_per_tick {
            self.active = false;
            return;
        }
        self.energy -= energy_per_tick;
        self.active = true;
        if self.progress >= ticks_required - 1 {
            self.finish(&recipe);
        } else {
            self.progress += 1;
        }
    }

    fn stop_and_reset(&mut self) {
        self.active = false;
        self.progress = 0;
    }

    fn finish(&mut self, recipe: &Recipe<O::Made>) {
        self.progress = 0;
        self.output.put(&recipe.output);
        if let Some(input) = self.input.as_mut() {
            input.count -= recipe.input_count;
            if input.count == 0 {
                self.input = None;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const USAGE: i64 = 5;

    /// The enriching recipes these tests use, from Mekanism's data files.
    struct Enriching;

    impl Recipes for Enriching {
        fn find(&self, input: &Stack) -> Option<Recipe> {
            let (id, input_count, output, count) = match input.item.as_str() {
                "iron_ore" => ("iron", 1, "dust_iron", 2),
                "gold_ore" => ("gold", 1, "dust_gold", 2),
                "two_needed" => ("two", 2, "dust_two", 1),
                _ => return None,
            };
            Some(Recipe {
                id: id.to_owned(),
                input_count,
                output: Stack::new(output, count),
            })
        }

        fn max_stack(&self, _item: &str) -> u32 {
            64
        }
    }

    fn machine(item: &str, count: u32, energy: i64) -> Machine {
        Machine {
            input: Some(Stack::new(item, count)),
            energy,
            ..Machine::default()
        }
    }

    fn run(m: &mut Machine, ticks: i32) {
        for _ in 0..ticks {
            m.tick(&Enriching, USAGE);
        }
    }

    // The numbers in this test are from a trace of the real mod on a NeoForge server.
    #[test]
    fn it_matches_the_traced_enrichment_chamber() {
        let mut m = machine("iron_ore", 8, 50_000);
        m.tick(&Enriching, USAGE);
        assert_eq!((m.progress, m.energy, m.active), (1, 49_995, true));
        run(&mut m, 198);
        assert_eq!((m.progress, m.energy), (199, 49_005));
        assert_eq!(m.output, None);
        assert_eq!(m.input, Some(Stack::new("iron_ore", 8)));
        m.tick(&Enriching, USAGE);
        assert_eq!((m.progress, m.energy, m.active), (0, 49_000, true));
        assert_eq!(m.output, Some(Stack::new("dust_iron", 2)));
        assert_eq!(m.input, Some(Stack::new("iron_ore", 7)));
    }

    #[test]
    fn without_enough_energy_it_pauses_and_keeps_its_progress() {
        let mut m = machine("iron_ore", 8, 12);
        run(&mut m, 2);
        assert_eq!((m.progress, m.energy, m.active), (2, 2, true));
        m.tick(&Enriching, USAGE);
        assert_eq!((m.progress, m.energy, m.active), (2, 2, false));
        m.energy = 5;
        m.tick(&Enriching, USAGE);
        assert_eq!((m.progress, m.energy, m.active), (3, 0, true));
    }

    #[test]
    fn a_full_output_pauses_it_uses_no_energy_and_keeps_its_progress() {
        let mut m = machine("iron_ore", 8, 1000);
        m.progress = 50;
        m.recipe = Some("iron".to_owned());
        m.output = Some(Stack::new("dust_iron", 63));
        m.tick(&Enriching, USAGE);
        assert_eq!((m.progress, m.energy, m.active), (50, 1000, false));
    }

    #[test]
    fn another_item_in_the_output_pauses_it() {
        let mut m = machine("iron_ore", 8, 1000);
        m.output = Some(Stack::new("dust_gold", 1));
        m.tick(&Enriching, USAGE);
        assert_eq!((m.progress, m.energy, m.active), (0, 1000, false));
    }

    #[test]
    fn taking_the_input_resets_its_progress() {
        let mut m = machine("iron_ore", 1, 1000);
        run(&mut m, 50);
        m.input = None;
        m.tick(&Enriching, USAGE);
        assert_eq!((m.progress, m.active), (0, false));
        assert_eq!(m.energy, 1000 - 50 * USAGE);
    }

    #[test]
    fn an_input_with_no_recipe_resets_its_progress() {
        let mut m = machine("iron_ore", 1, 1000);
        run(&mut m, 50);
        m.input = Some(Stack::new("stick", 1));
        m.tick(&Enriching, USAGE);
        assert_eq!((m.progress, m.active), (0, false));
    }

    #[test]
    fn swapping_to_another_recipe_restarts_it() {
        let mut m = machine("iron_ore", 1, 1000);
        run(&mut m, 50);
        m.input = Some(Stack::new("gold_ore", 1));
        m.tick(&Enriching, USAGE);
        assert_eq!(m.progress, 1);
    }

    #[test]
    fn saved_progress_carries_on_after_a_reload() {
        let mut m = machine("iron_ore", 1, 1000);
        m.progress = 50;
        m.recipe = Some("iron".to_owned());
        m.tick(&Enriching, USAGE);
        assert_eq!(m.progress, 51);
    }

    #[test]
    fn less_input_than_the_recipe_needs_resets_its_progress() {
        let mut m = machine("two_needed", 1, 1000);
        m.progress = 50;
        m.recipe = Some("two".to_owned());
        m.tick(&Enriching, USAGE);
        assert_eq!((m.progress, m.energy, m.active), (0, 1000, false));
    }

    #[test]
    fn the_last_item_leaves_an_empty_input_slot() {
        let mut m = machine("iron_ore", 1, 10_000);
        run(&mut m, TICKS_REQUIRED);
        assert_eq!(m.input, None);
        assert_eq!(m.output, Some(Stack::new("dust_iron", 2)));
    }
}

/// Replays what the real mod did, recorded by `port/java_reference.py`.
#[cfg(test)]
mod reference {
    use super::*;

    /// A change to make just before the tick it names.
    type Change = (i32, fn(&mut Machine));

    struct Real;

    impl Recipes for Real {
        fn find(&self, input: &Stack) -> Option<Recipe> {
            let (output, count) = match input.item.as_str() {
                "minecraft:iron_ore" => ("mekanism:dust_iron", 2),
                "minecraft:gold_ore" => ("mekanism:dust_gold", 2),
                "minecraft:cobblestone" => ("minecraft:gravel", 1),
                "minecraft:raw_iron" => ("minecraft:iron_ingot", 1),
                _ => return None,
            };
            Some(Recipe {
                id: input.item.clone(),
                input_count: 1,
                output: Stack::new(output, count),
            })
        }

        fn max_stack(&self, _item: &str) -> u32 {
            64
        }
    }

    fn stack(text: &str) -> Option<Stack> {
        let (item, count) = text.rsplit_once('x')?;
        Some(Stack::new(item, count.parse().ok()?))
    }

    /// Changes apply just before their tick, as the recording made them.
    fn replay(recording: &str, usage: i64, start: Machine, changes: &[Change]) {
        let mut machine = start;
        for line in recording.lines().skip(1) {
            let fields: Vec<&str> = line.split('\t').collect();
            let tick: i32 = fields[0].parse().unwrap();
            for (_, change) in changes.iter().filter(|(at, _)| *at == tick) {
                change(&mut machine);
            }
            machine.tick(&Real, usage);
            let expected = (
                fields[1].parse::<i32>().unwrap(),
                fields[2] == "1",
                fields[3].parse::<i64>().unwrap(),
                stack(fields[4]),
                stack(fields[5]),
            );
            let got = (
                machine.progress,
                machine.active,
                machine.energy,
                machine.input.clone(),
                machine.output.clone(),
            );
            assert_eq!(got, expected, "tick {tick}");
        }
    }

    fn start(input: (&str, u32), output: Option<(&str, u32)>, energy: i64) -> Machine {
        Machine {
            input: Some(Stack::new(input.0, input.1)),
            output: output.map(|(item, count)| Stack::new(item, count)),
            energy,
            ..Machine::default()
        }
    }

    const IRON: (&str, u32) = ("minecraft:iron_ore", 8);
    const CHAMBER_USAGE: i64 = 5;
    const CRUSHER_USAGE: i64 = 8;
    const SMELTER_USAGE: i64 = 5;

    macro_rules! recording {
        ($name:literal) => {
            include_str!(concat!("../../../reference/", $name, ".tsv"))
        };
    }

    #[test]
    fn chamber_normal() {
        let m = start(IRON, None, 50_000);
        replay(recording!("chamber_normal"), CHAMBER_USAGE, m, &[]);
    }

    #[test]
    fn chamber_last_item() {
        let m = start(("minecraft:iron_ore", 1), None, 50_000);
        replay(recording!("chamber_last_item"), CHAMBER_USAGE, m, &[]);
    }

    #[test]
    fn chamber_low_energy() {
        let m = start(IRON, None, 12);
        replay(
            recording!("chamber_low_energy"),
            CHAMBER_USAGE,
            m,
            &[(10, |m| m.energy = 1000)],
        );
    }

    #[test]
    fn chamber_full_output() {
        let m = start(IRON, Some(("mekanism:dust_iron", 63)), 50_000);
        let shrink: fn(&mut Machine) = |m| m.output = Some(Stack::new("mekanism:dust_iron", 1));
        replay(
            recording!("chamber_full_output"),
            CHAMBER_USAGE,
            m,
            &[(10, shrink)],
        );
    }

    #[test]
    fn chamber_other_output() {
        let m = start(IRON, Some(("mekanism:dust_gold", 1)), 50_000);
        replay(recording!("chamber_other_output"), CHAMBER_USAGE, m, &[]);
    }

    #[test]
    fn chamber_take_input() {
        let m = start(IRON, None, 50_000);
        replay(
            recording!("chamber_take_input"),
            CHAMBER_USAGE,
            m,
            &[(50, |m| m.input = None)],
        );
    }

    #[test]
    fn chamber_swap_input() {
        let m = start(IRON, None, 50_000);
        let swap: fn(&mut Machine) = |m| m.input = Some(Stack::new("minecraft:gold_ore", 8));
        replay(
            recording!("chamber_swap_input"),
            CHAMBER_USAGE,
            m,
            &[(50, swap)],
        );
    }

    #[test]
    fn chamber_no_recipe() {
        let m = start(("minecraft:stick", 8), None, 50_000);
        replay(recording!("chamber_no_recipe"), CHAMBER_USAGE, m, &[]);
    }

    #[test]
    fn crusher_normal() {
        let m = start(("minecraft:cobblestone", 3), None, 50_000);
        replay(recording!("crusher_normal"), CRUSHER_USAGE, m, &[]);
    }

    #[test]
    fn smelter_normal() {
        let m = start(("minecraft:raw_iron", 3), None, 50_000);
        replay(recording!("smelter_normal"), SMELTER_USAGE, m, &[]);
    }
}
