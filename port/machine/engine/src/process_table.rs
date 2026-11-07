//! The machines that share `advanced.rs`: what each one is and where its screen puts things. Adding a
//! machine of these shapes means a row here, its recordings and its row in the tests.

/// What the slot after the upgrades does.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Extra {
    /// `ChemicalInventorySlot.fillOrConvert`: an item converts into the tank.
    Conversion,
    /// `InputInventorySlot`: a recipe's second item input.
    ItemInput,
    /// `OutputInventorySlot`: a chance output.
    ByProduct,
}

#[derive(Clone, Copy, Debug)]
pub struct ProcessScreen {
    pub input: [f32; 2],
    pub output: [f32; 2],
    pub energy: [f32; 2],
    pub extra: [f32; 2],
    /// `GuiSlot`'s art for the extra slot, or none when `output_frame` covers it.
    pub extra_art: Option<&'static str>,
    /// `new GuiSlot(SlotType.OUTPUT, ...)`, which replaces the output slots' art.
    pub output_frame: Option<[f32; 4]>,
    pub arrow: Option<[f32; 2]>,
    pub progress: [f32; 4],
    pub progress_art: &'static str,
    /// `GuiChemicalBar`'s position with its frame.
    pub chemical_bar: Option<[f32; 4]>,
    pub power_y: f32,
    pub dump: Option<[f32; 2]>,
}

#[derive(Clone, Copy, Debug)]
pub struct ProcessDef {
    pub block: &'static str,
    pub recipes: &'static str,
    /// `UsageConfig`.
    pub usage: i64,
    /// `MAX_GAS` or `MAX_INFUSE`, and 0 for a machine with no tank.
    pub tank: i64,
    /// `useStatisticalMechanics`, with `randomizedConsumption` at its default of true.
    pub statistical: bool,
    pub extra: Extra,
    pub screen: ProcessScreen,
}

/// `TileEntityAdvancedElectricMachine`'s slots and `GuiAdvancedElectricMachine`.
const ADVANCED: ProcessScreen = ProcessScreen {
    input: [64.0, 17.0],
    output: [116.0, 35.0],
    energy: [39.0, 35.0],
    extra: [64.0, 53.0],
    extra_art: Some("slot/extra"),
    output_frame: None,
    arrow: None,
    progress: [86.0, 38.0, 25.0, 9.0],
    progress_art: "bar",
    chemical_bar: Some([68.0, 36.0, 8.0, 14.0]),
    power_y: 16.0,
    dump: None,
};

pub const PROCESS: &[ProcessDef] = &[
    ProcessDef {
        block: "mekanism:osmium_compressor",
        recipes: "mekanism:compressing",
        usage: 15,
        tank: 210,
        statistical: false,
        extra: Extra::Conversion,
        screen: ADVANCED,
    },
    ProcessDef {
        block: "mekanism:purification_chamber",
        recipes: "mekanism:purifying",
        usage: 10,
        tank: 210,
        statistical: true,
        extra: Extra::Conversion,
        screen: ADVANCED,
    },
    ProcessDef {
        block: "mekanism:chemical_injection_chamber",
        recipes: "mekanism:injecting",
        usage: 15,
        tank: 210,
        statistical: true,
        extra: Extra::Conversion,
        screen: ADVANCED,
    },
    ProcessDef {
        block: "mekanism:combiner",
        recipes: "mekanism:combining",
        usage: 5,
        tank: 0,
        statistical: false,
        extra: Extra::ItemInput,
        // `GuiCombiner`, and the slots from `TileEntityCombiner`.
        screen: ProcessScreen { arrow: Some([68.0, 38.0]), chemical_bar: None, power_y: 15.0, ..ADVANCED },
    },
    ProcessDef {
        block: "mekanism:precision_sawmill",
        recipes: "mekanism:sawing",
        usage: 5,
        tank: 0,
        statistical: false,
        extra: Extra::ByProduct,
        // `GuiPrecisionSawmill`, and the slots from `TileEntityPrecisionSawmill`.
        screen: ProcessScreen {
            input: [56.0, 17.0],
            output: [116.0, 35.0],
            energy: [56.0, 53.0],
            extra: [132.0, 35.0],
            extra_art: None,
            output_frame: Some([111.0, 30.0, 42.0, 26.0]),
            arrow: Some([60.0, 38.0]),
            progress: [78.0, 38.0, 25.0, 9.0],
            progress_art: "bar",
            chemical_bar: None,
            power_y: 15.0,
            dump: None,
        },
    },
    ProcessDef {
        block: "mekanism:metallurgic_infuser",
        recipes: "mekanism:metallurgic_infusing",
        usage: 5,
        tank: 1000,
        statistical: false,
        extra: Extra::Conversion,
        // `GuiMetallurgicInfuser`, and the slots from `TileEntityMetallurgicInfuser`.
        screen: ProcessScreen {
            input: [51.0, 43.0],
            output: [109.0, 43.0],
            energy: [143.0, 35.0],
            extra: [17.0, 35.0],
            extra_art: Some("slot/extra"),
            output_frame: None,
            arrow: None,
            progress: [72.0, 47.0, 32.0, 8.0],
            progress_art: "right",
            chemical_bar: Some([7.0, 15.0, 6.0, 54.0]),
            power_y: 15.0,
            dump: Some([16.0, 59.0]),
        },
    },
];

pub fn process(block: &str) -> Option<&'static ProcessDef> {
    PROCESS.iter().find(|def| def.block == block)
}
