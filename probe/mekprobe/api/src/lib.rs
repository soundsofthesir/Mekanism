//! Phase 0 probe: `mekprobe:ticker` adds one to its saved `ticks` on every server tick.
use horizon_client::mod_api::{
    BlockEntityEvent, BlockEntityTickEvent, BlockEntityTicksEvent, BlocksEvent, Compound, Hooks,
    Host, Tag,
};
use horizon_mods::content::Block;

const TICKER: &str = "mekprobe:ticker";
const TICKS: &str = "ticks";

pub fn hooks() -> Box<dyn Hooks> {
    Box::new(Mod)
}

struct Mod;

impl Hooks for Mod {
    fn blocks(&self, event: &mut BlocksEvent<'_>) {
        event.blocks.push(Block {
            id: TICKER.into(),
            template: "minecraft:stone".into(),
            item: true,
            ..Default::default()
        });
    }

    fn block_entity(
        &self,
        _host: &mut dyn Host,
        event: &mut BlockEntityEvent<'_>,
    ) -> Option<(String, Compound)> {
        (event.block == TICKER).then(|| (TICKER.to_owned(), Compound::new()))
    }

    fn block_entity_ticks(&self, _host: &dyn Host, event: &mut BlockEntityTicksEvent<'_>) {
        if event.block == TICKER {
            event.ticks = true;
        }
    }

    fn block_entity_tick(&self, _host: &mut dyn Host, event: &mut BlockEntityTickEvent<'_>) {
        if event.entity.id != TICKER {
            return;
        }
        let nbt = &mut event.entity.nbt;
        if let Tag::Long(count) = nbt.entry(TICKS.into()).or_insert(Tag::Long(0)) {
            *count += 1;
        }
    }
}
