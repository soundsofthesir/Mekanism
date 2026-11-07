# Plan: port Mekanism to Horizon

Status: Phases 0 to 3 passed on 2026-11-06. Phase 4's calibration slice is done (see "Phase 4 result"), and the rest of Phases 4 to 7 waits for its review. The estimate below uses what Phases 0 to 3 measured.

## Source and target

- **Source:** Mekanism 10.8.0 for Minecraft 26.3 and NeoForge, commit `ff721ff39f`. It is MIT licensed, so a port must keep its copyright notice. `upstream/` holds a clone for reference and git ignores it. To recreate it, run `git clone https://github.com/mekanism/mekanism upstream`.
- **Target:** [Horizon](https://github.com/horizon-rust/horizon), a Rust rewrite of Minecraft 26.3. The findings below come from Nightly `f319701` (2026-11-05, hook API 409), which replaced the first survey at `baa379d`. Main gained 13,707 commits in the week between `baa379d` and the 2026-11-06 head.

## Findings

- Java code doesn't run in Horizon, so all of the mod's code needs rewriting. That is about 209k lines to port, including 39k of client code. Datagen, integrations and tests are another 45k.
- `horizon-port-pack` carries over data, assets, worldgen and basic block and item definitions.
- Native mods now document hooks for ticking and saved block entities (API 15), item slots (16), menus and screens (17, 19), custom recipe types (36), client sync (45), fluid tanks (54), block entity drawing (71) and energy buffers (142). Phase 0 ran the block entity hooks. The others are documented but untested here.
- Mods can't look up vanilla fuels or smelting results through the stable API, at `f319701` or at `origin/main` on 2026-11-06. `recipes_of_type` covers only types outside `minecraft`, and no helper gives a burn time. Mixin helpers compiled inside the game can reach both tables. The Heat Generator and Energized Smelter need these.
- API 0.4 won't arrive: #1189 closed on 2026-10-31 because main removed WebAssembly mods in favour of native ones.
- Native mods are the only route. They are unsandboxed and compiled into a separate game build. The launcher builds them only with `--trust-native-code`, which the docs say an agent must not supply.
- Dedicated servers run native mods through a standalone export (`native-build --server-output`).

## Phases

| # | Work | Done when | Complexity |
|---|---|---|---|
| 0 | Test the riskiest part with a native mod (`probe/`) | A ticking block keeps its state through save and load, in single player and on a dedicated server | Medium, go/no-go |
| 1 | Run `horizon-port-pack` on a Mekanism jar | Ores generate; items, simple blocks and ordinary crafting recipes work | Low |
| 2 | Build the machine layer: block entities, menus and screens, energy, item and fluid transfer, client sync | A furnace matches vanilla tick for tick | High |
| 3 | Build one working chain: recipe engine, Heat Generator, Universal Cable, Energy Cube, Enrichment Chamber, Crusher, Energized Smelter | Ore to doubled ingots on cable power, with progress, energy and saved state matching Java | High |
| 4 | All cables and pipes, chemicals, remaining machines and tiers | About 119 block entity types and 72 menus work (counts approximate) | Very high |
| 5 | Multiblocks: Dynamic Tank, Induction Matrix, boiler, evaporation, SPS | Each forms, runs and reloads | High |
| 6 | Digital Miner, teleporter, logistics, QIO, Robit, MekaSuit and its 32 modules | Each passes its own comparison test | Very high |
| 7 | Generators (including fission and fusion), Additions, Tools | Each module passes its tests | High |

## Phase 0 result

`probe/run_phase0.py` passed in single player and on a dedicated server, on Nightly `f319701` with a `dev` build:

- The block counted 102 ticks over 102 game ticks, before the restart and after it.
- The count was 205-206 at the last read before the stop and 214-229 at the first read after the start. A 24-second run can't reach those values from a reset.
- A first build took 4 min 32 s on this 8GB Mac.

The test reads the count with the game running, so it can't catch the loss of a few ticks at the save. It covers one saved number in a force-loaded chunk. It doesn't cover items, menus, client sync, or a player next to the block. Phase 2's NBT comparison has to cover those.

## Phase 1 result

`port/test_phase1.py` passed 3 of 3 runs on the unmodded Nightly `f319701`, in single player only:

- All five ores generate. A scan of 144 chunks below y 64 found about 6,970 osmium, 12,510 tin, 6,380 lead, 5,780 uranium and 7,170 fluorite.
- Blocks place and survive a reload. Osmium ore's loot table gives raw osmium.
- Shaped (with a `c:` tag) and shapeless recipes craft at a table, and a furnace smelts raw osmium. That is 3 crafting recipes and 1 smelting recipe of the 225 vanilla-type recipes.
- A screenshot shows the blocks and items with their real textures.

There is no compiled jar: 26.3 has no published release, so `port/make_resource_jar.py` zips the source's assets and generated data.

`port/patch_worldgen.py` is needed after the carry, for two reasons:

- Mekanism's ore and salt files use Java types that read its config, so Horizon skipped all 11. The script writes the default values into vanilla's types and removes retrogen.
- Horizon reads a mod's features only from `worldgen/configured_feature/`, but 26.3 datagen writes `worldgen/feature/`. `origin/main` had the same gap on 2026-11-06.

Known gaps:

- 76 machine blocks and their 76 recipes are left out, and 1,718 recipes of Mekanism's own types do nothing. Phases 3 and 4 add them.
- The other 124 blocks use guessed vanilla templates (87 copy stone, 36 copy a carved pumpkin), so hardness, tool, sounds and shapes are unchecked against Java.
- The 5 energy cubes have no model, and `cardboard_box` and `configurator` have no item definition.
- Ore counts aren't compared with Java, and they differ by a few blocks between runs of one seed (tin 12,509-12,517, uranium constant). The cause is unknown.
- Salt and dedicated servers are untested.

## Phase 2 result

`port/test_phase2.py` runs a mod furnace (`port/machine`) beside a vanilla one through 9 scenarios and a reload, in single player and on a dedicated server. No trace row differs across about 700 ticks each. The furnace's menu opens with the same slots as vanilla's, a shift-click takes its output, and a screenshot shows the flame and progress arrow.

The comparison is against Horizon's vanilla furnace, which Horizon's harnesses check against Java. No Java run is involved here.

A reload can move the vanilla furnace after the mod's in the tick order. The test then allows one fixed shift of one tick for that load.

Known gaps:

- A hopper can put any item in the fuel slot, where vanilla takes only fuel, and can't pull a bucket out of it.
- The input check compares item ids, so swapping to the same item with other components doesn't restart cooking.
- The block has no language file, so the menu's title shows `block.mekmachine.furnace`.
- Experience, stats and comparator output are untested.
- `native_block_entity_update_tag` is unused, and no client has joined a dedicated server in these tests. The menu's data slots and the `lit` state reach a single-player client.
- The transfer test blocks are stand-ins, not Mekanism's machines, and their rates are the test's own.

`port/test_transfer.py` moves energy and fluids along 6 lines of test blocks, in single player and on a dedicated server. Rates are exact until the stores fill, a face that refuses takes nothing, a tank keeps its first fluid, and a reload finds the same amounts.

A block entity is out of the world during its own tick, so Horizon's energy and fluid helpers answer 0 for it. A machine offers to its neighbour and subtracts what was taken (`port/machine/engine/src/transfer.rs`). A cable or pipe holds nothing, so the helpers' moves between its two neighbours work.

Builds on this 8GB Mac: 4 min 32 s for the first and 2 min 7 s for a mod change, in the `dev` profile.

## Phase 3 result

Phase 3's done-when is met for the machines and values below, in single player and on a dedicated server. Run all of it with `sh port/build_and_test.sh --trust-native-code --eula`, which writes `port/.work/results.txt`.

- `port/test_chain.py` replays cable networks, the Heat Generator and the whole chain from recordings of the real mod. A generator and a cube power a chamber and a smelter through four cables and a hopper, turning 2 ore into 4 ingots. Power runs out, the world restarts, and a command adds energy, so the 900 rows after the restart prove what was saved. All 1,704 rows match. Energy, lava, slots, progress and activity match exactly, and heat to within 0.000001.
- `port/test_phase3.py` replays 10 recordings of the Enrichment Chamber, Crusher and Energized Smelter: 1,270 ticks with no differences.
- `port/test_generator.py` replays 5 recordings of the generator's fuel slot, and fills it from its menu. Single player only.
- `port/test_menu.py` plays as a player: a shift-click fills a machine, side buttons change its saved sides, a hopper follows them, and they survive a reload. Single player only, with no recording to compare, because the real mod's screens need a client.

Two carry steps are needed. `port/add_common_tags.py` adds NeoForge's `c:` tags, because 131 of the 198 that Mekanism's recipes use were missing, which Phase 1's 4-recipe sample didn't catch. `port/add_machine_content.py` adds the menu types and replaces the cable's and basic cube's models.

Known differences from the real mod:

- Machines: no sounds, particles or radiation. A menu's input slot takes any item, because Horizon's slot rule has no recipe table at hand, though a hopper is held to recipes.
- Sides: a hopper putting items in follows the saved sides, but one taking items out doesn't, so a hopper below can always pull the output. A bare `setblock` gets the item's default sides here and none in the real mod.
- Blocks: the three machines and the generator copy a furnace, so they have an unused `lit` state and face only the four compass directions. Their hardness, tools, sounds and shapes are unchecked against Java, as are the other carried blocks'.
- Energy Cube: basic tier only, with no menu and no charge or discharge slots, so a player can't change its sides. Its transfer limit is per call, not per tick. Its model doesn't show side settings. Its energy doesn't stay in the item when broken (unverified against Java).
- Universal Cable: basic tier only, with no connection modes or redstone control. A cable's model is a plain core and arms, not the real OBJ. Each cable's saved share is unverified, because the recordings compare the chain's cables by their sum. A network is searched afresh each tick, whose cost is unmeasured.
- Heat Generator: no energy slot, no Nether bonus, no heat passed to a block below, and lava in its own block space isn't counted. A hopper can't pull out an empty bucket.
- Not tested: a client on a dedicated server, other biomes or positions beyond the recorded ones, other recipes beyond iron ore, gold ore, cobblestone and raw iron in machines, and performance.
- `port/machine` hooks one function outside the named catalog (`native_container_accepts`), so a Horizon update may break it.
- Superseded by Phase 4: the plain layout and coloured squares on the electric machines' screens.

Measured sizes: `port/machine` is about 2,000 lines of glue and engine code, plus tests. That covers 6 machines and the shared layer, well under the 8-12k and 3-8k estimated for Phases 3 and 2, because the hooks do much of the work. A build after a mod change took 1 to 2 minutes.

## Phase 4 result

This covers the calibration slice only: chemicals, one tube, one chemical machine, the real screen on the electric machines, one custom renderer and a split test suite.

`port/run_tests.py` runs test groups one at a time and reports each one's time. `--changed` picks groups from the files that differ from a git ref, and a file with no rule selects every group. `--all` keeps the full set, which is the one to use before a merge. `port/build_and_test.sh` takes `--no-build` and the same arguments.

The Chemical Oxidizer was the machine chosen because it has one item input and one chemical output, with no chemical input or fluid, so it tests a tank, ejecting and a recipe's chemical result and nothing else. It sends into a Pressurized Tube, and a basic Chemical Tank takes the result. It shares the recipe logic of the other machines through a generic `Machine<Output>`.

- `port/java_reference_chemical.py` records 16 scenarios from the real mod. `port/test_chemical.py` replays them in single player and on a dedicated server, including a server restart with chemicals in tubes. All rows match: rates, shares, full and wrong-chemical targets, closed sides, and `recipes_used`.
- Chemicals save as the real mod does: `chemical_tanks: [{container: 0b, stored: {amount: 100L, type: "..."}}]` and, on a tube, `stored: {amount: ..., type: "..."}`. A block's other values keep Horizon's container format (`Items`, `energy`).
- `port/test_gui.py` compares a screenshot with Mekanism's art at the source's positions: slots, arrow, tabs and their tints, both bars. Clicks open the side config window, change sides (left, right, shift clears), change kind and toggle eject, and the window blocks the slots under it. `port/test_menu.py` plays through the same window.
- `port/test_cable_look.py` measures a screenshot of the Universal Cable drawn from its OBJ model. A straight run's section is 0.378 of a block against the OBJ's 0.375. Energy contents appear and clear again without a block changing.

What each check was proven to fail on, by building the broken value:

| Broken | Failing test and message |
|---|---|
| Oxidizer ticks 100 to 99 | `test_chemical`: `oxidizer_normal tick 99` |
| Tube capacity 4,000 to 3,000 | `test_chemical`: `tube_fills tick 7` |
| `arrow/up` to `arrow/down` | `test_gui`: up arrow, 44 pixels |
| Security tab's colour bytes swapped | `test_gui`: security tab's holder, 12 pixels |
| Left click sends the right click's id | `test_gui`: top after a left click, got 0 |
| Contents scale forced to 0 | `test_cable_look`: holding energy changes nothing |
| Model's section shrunk to 0.67 | `test_cable_look`: section 0.273 |
| Client sync of a cable's energy removed | `test_cable_look`: drained cable, 1,200 pixels |

Horizon's hooks were enough for all of this, with no fork. Three findings matter for later work:

- `screen_mouse_button_pressed_pre` plus `screen_render_post` gives real windows over slots. The named `screen_click` hook isn't called over a slot, so it can't.
- `native_draw_quad` takes a rectangular UV and no alpha. Every transmitter face fits the rectangle. Alpha goes through `BlockEntityDraw::vertices_mut`, which is not in the named catalog, so a Horizon update may break it.
- The GUI atlas holds `<ns>:gui/...` and block textures, but not `mek_liquid/`, so the energy texture is copied to `textures/block/port_energy.png` in the carry step. The other chemical and fluid textures will need the same.

Known differences from the real mod:

- Chemicals: only the oxidizer holds chemicals as a machine. No gas dumping, radiation, chemical item slots or `canEject` rules beyond the sides. A tube has no connection modes or redstone control.
- Tube shares: the real mod's network order comes from a hash, so which tube gets a remainder isn't copied. `test_chemical` compares shares sorted within each row. Two real runs gave the same order, so it may be stable there, but its source says identity hash.
- Tubes with different chemicals don't join, which matches `isValidTransmitter`, but no recording covers it or the merge when two networks meet.
- Oxidizer: its `active` state isn't shown on the block, whose carried model has none. See its screen below for the rest.
- Chemical Tank: no screen, slots or dump mode. Its carried block is a carved pumpkin template with its real model name, and its real tank model's custom drawing isn't done.
- Machine screen: there is no recording of the real screen, because that needs a Java client. Positions and art come from source. Tabs for security, experience and transporter config are drawn but do nothing. Tooltips cover side buttons, the power bar, the side tab, the energy tab and the gauge. No warnings, recipe viewer, block icons on side buttons or window dragging and pinning.  A press makes no click sound, since the hook is read only. Text is hard-coded English from `en_us.json` for the window.
- The Heat Generator's screen is still the plain one, and the Energy Cube has none.
- Universal Cable: base tier, normal and none connections only, with no glass or pull and push parts. Connections come from a tag list, not from checking that the neighbour's side takes energy. Contents show this cable's share, not the network's scale with its fade of 0.02 a tick. Alpha below 100% and the look on a dedicated server's client are unverified. The Pressurized Tube still uses the plain model.
- `port/machine` adds `mek_send_menu_button` and `vertices_mut` use, both outside the named catalog.

Not tested: a client on a dedicated server, and frame time with many cables.

Full run on the slice, `--all` after a clean build: 13 of 14 runs passed in 58 minutes. The 14th, `menu`, stopped when the game crashed while opening its world, before any of the test's checks. It then passed 3 of 3 runs on the same build. The crash is a null `Arc` clone in the `lan_host` closure while it maps `StateFacts`, under `ChunkEncoder::with_signs` (macOS report at 22:20). The cause is unknown. Nothing in `port/machine` names `lan_host` or `ChunkEncoder`, but that doesn't clear the mod, because its blocks are in that state table. It happened once in an estimated 40 launches and may recur in any group. A crash before a test's first check isn't a test failure, but it must be recorded here.

Group times, each mode, before the change below: chain 1,025 s, chemical 325 s, machines 265 s, generator 83 s, furnace 55 s and 39 s, menu 40 s, cable look 33 s, GUI 24 s, transfer 17 s and 14 s.

### Next steps

The batch of 2026-11-07's stale engine guard, reload work and failure evidence are done, and so is the Osmium Compressor. In order, what's left:

1. The recipe machines, each with its real screen, one recording of normal running and one edge case at least, compared in both modes. Next: Combiner, Precision Sawmill, Purification Chamber, Chemical Injection Chamber, Metallurgic Infuser. Then Chemical Infuser, Chemical Washer, Chemical Crystallizer, Chemical Dissolution Chamber, Rotary Condensentrator, Electrolytic Separator, Pressurized Reaction Chamber. See "Osmium Compressor" for what a machine with a tank needs. A recipe's item and chemical inputs are in `item_input` and `chemical_input`. Purification and Injection set `useStatisticalMechanics`, so their chemical use is random (`StatUtils.inversePoisson`) and rows can only be compared within a bound. Sawmill recipes have a chance output, which is random too. Chemical inputs named by a `#` tag need tag reading: `native_recipe_chemical_matches` and `advanced.rs` read only a chemical's id. Block names are repeated in many `match` arms in `mek.rs`, `container.rs`, `energy.rs`, `blocks.rs`, `screen.rs` and `gui.rs`, and a table would make each machine cheaper.
2. Connection modes and redstone on transmitters, and pulling from a block: tube and pipe `pull` rates (`TubeTier`, `PipeTier`) are copied nowhere yet. `CableTier` has none.
3. Chemical item slots and the oxidizer's drain slot, once a chemical item is ported. Real Fluid Tank and Chemical Tank items and screens.
4. Creative tiers of the cube and tanks: no capacity fits `i32`, so they need a `Long` in the block's data and three data slots, and their own rule for never draining.
5. The heat generator's real screen and the transporter and security tabs, which are drawn but inert.

Rules for a fresh worker:

- `port/.work/check/carry` holds the carried content, and `add_machine_content.py` must run again after a machine is added to it, or the game has no menu for the machine. `cargo` isn't on the path: use the launcher's, in `~/Library/Application Support/horizon-launcher/rust/*/bin`.
- A `data` command on a machine rebuilds its block entity and clears `data`, including the recalculated mark. Empty a slot by `item replace`.
- `/give` has no parser for a mod's item component, though a chest's data and `item replace ... from block` keep it. `test_upgrades.py` uses that.
- A test that interacts just after a `setblock` must wait first: the client gets the block a little later, and `interact` answers "no face ... is visible".
- `horizon_driver` writes no `options.txt`. A test that reads the top right of a screen writes `tutorialStep:none`, or the tutorial's toast covers it.
- A child module of a Horizon file (`[[module]]`, `file = ".../machines.rs"`) can reach that file's private items. `mek_items.rs` and `mek_screen.rs` are the two uses. A `horizon-client` lib hook like `menu_slot_rules` can't see `crate::game`.
- Reference recordings stay on Tower: `python3 port/java_server.py start --eula`, then `port/java_reference_*.py`. Stop it with `python3 port/java_server.py stop`.

### Batch of 2026-11-07: ejecting, player controls, wide values, energy slots, tiers, pipes

Item ejecting. `mek_eject_items` follows `TileComponentEjector`: an attempt on tick 1 and every 11 ticks after, a whole slot at once, each output side in turn, before the recipe runs. Horizon's move drops anything past one stack (`stack.count.min(max)`), so `mek_insert_item` sends a stack at a time. `test_features` now compares the chest column in both modes. Broken and failed: one chest value in `eject_stack.tsv` (tick 29), and the delay from 10 to 9 (`eject_running` tick 210).

Upgrades and redstone by a player. The redstone tab cycles `disabled`, `high`, `low` and back. `ITileRedstone.supportsMode` leaves out `pulse` on these machines. The upgrade tab opens `GuiUpgradeWindow`: a list, a screen, Uninstall (shift for all), two slots that exist only while the window is open, and arrows. A window's slots move by `mek_screen_frame`, which runs on the `frame` hook and rewrites the open screen's slot positions, off screen when closed. `port/java_reference_features.py` records `install_*`: the slot counts 20 ticks and installs on tick 21, as many as fit. `port/test_upgrades.py` does all of this by clicks and then compares 30 rows of `redstone_high` and 140 rows of `upgrade_run_speed4` with the recording, from the state the clicks reached. Broken and failed: redstone buttons swapped ("got low, expected high"), uninstall removes 2 ("got 2, expected 3"), the slot's frame a pixel off ("got [165, 35]"), install ticks 20 to 19 (`features`).

A finding from `install_running`: once `recalculateUpgrades` has run, capacity is `usage * max(4, ticks)`, even with nothing installed, so a chamber holds 1,000 rather than 20. It runs when `component_upgrade` loads and after any install or uninstall.

Wide menu values. Energy, capacity and usage take two 16-bit data slots each, by `low_half`, `high_half` and `from_halves`, which allow for either sign. The engine tests it at 32,767, 32,768, 65,536, 4,000,000 and more. `port/test_cube_screen.py` reads the cube's gauge from screenshots at 32,767, 32,768, 40,000, 65,536, 1,000,000, 2,000,000 and 4,000,000 FE. Ignoring the high half fails it ("gauge rows at 32767 FE: got 47, expected 1").

Energy slots. They're in the machines' and the oxidizer's menus. `mek_fill_energy_slot` follows `fillContainerOrConvert`: from a charged item at its rate, or else a conversion recipe if all its energy fits. The Energy Tablet is the one energy item, by the `item_energy_buffer` hook at `GearConfig`'s 1,000,000 FE and 5,000 FE a tick, kept in Horizon's `horizon_energy` where the real mod has `mekanism:energy`. `energy_slot_*` recordings replay in `features` in both modes. Broken and failed: tablet rate 5,000 to 4,000 (`energy_slot_tablet` tick 1), a conversion that ignores room (`energy_slot_redstone` tick 2). The tablet's own crafting isn't checked.

Tiers. `machine/engine/src/tiers.rs` holds `CableTier`, `TubeTier`, `ChemicalTankTier`, `EnergyCubeTier`, `PipeTier` and `FluidTankTier` from source. `port/java_reference_tiers.py` records 22 scenarios and `port/test_tiers.py` replays them in both modes with every cell compared. Tiers of a kind join and capacities add. A network that has not yet ticked offers only the capacity of the block touching the sender, which `tier_cable_mixed` and `tier_tube_mixed` show on their first tick and the code now follows (`FORMED` in `mek.rs`, `chem.rs` and `pipe.rs`). The cube has its screen (`GuiEnergyCube`), side config with input and output on both kinds, and its discharge and charge slots, which the tier's rate limits. `cube_slot_*` covers those.

Mechanical Pipe. `port/machine/pipe.rs` follows `chem.rs`, and the Fluid Tank came with it because a pipe needs a source. A tank emits only downwards and only while `active_state` is set. `port/java_reference_pipe.py` records 16 scenarios, and `port/test_pipe.py` replays them in both modes. One thing looked strange until the code explained it: a tank above a basic pipe loses 1,000 a tick, not 2,000, because the pipe's network splits what it holds between both tanks and half goes back up.

Test speed. `machines` and `chemical` now use the chain's fast tick rate, with no row removed: `machines` 27 s and 26 s against 268 s and 266 s, `chemical` 41 s and 45 s against 325 s and 323 s. Changing one progress value at row 60 of `chamber_normal.tsv` and `oxidizer_normal.tsv` fails each group in both modes at tick 60. Other breaks: pipe capacity 2,000 to 1,500 and tank rate 4,000 to 3,000 fail `pipe`; a network offering its full capacity on its first tick fails `tiers`; cube rate 16,000 to 15,000 fails `tiers` at `tier_cube_advanced` tick 1, and cable capacity, tube capacity and tank rate each fail `tiers`. The failing row of those last ones wasn't captured.

Full run on this work, `--all` after a rebuild: 22 of 23 runs passed in 886 s (15 minutes, against 29). `upgrades` failed in 9 s, in `horizon-ctl launch`, before its first check, with an empty message and no new macOS crash report, and its folder was cleared before it could be read. It then passed 3 of 3 runs on the same build. The cause is unknown. The runner reports this as a plain failure rather than a launch crash, because the game wasn't known to have died. Group times: chain 74 s and 92 s, generator 83 s, features 70 s and 40 s, furnace 49 s and 39 s, chemical 41 s and 45 s, menu 40 s, oxidizer screen 37 s, cube screen 36 s, cable look 30 s, machines 27 s and 26 s, tiers 28 s and 20 s, GUI 26 s, pipe 22 s and 17 s, transfer 17 s and 15 s. `upgrades` takes 71 s when it runs.

Known differences this batch leaves:

- Upgrades: no sneak-use on a machine to install, no chemical, muffling or other kinds, no "supported" row or effect line in the window, and the window's list can't scroll (two kinds fit). The upgrade item has no icon, because Horizon lacks `mekanism:component_item`. Its slot's frame overlaps an inventory slot by 3 pixels, so a press on the frame's left edge takes the inventory slot. The window hides slot tooltips under it. The saved format is the container's slots 3 and 4, not `component_upgrade.items`.
- Saved machines: see "Saved machines through a reload".
- Ejecting: `eject_delay` and `upgrade_ticks` are saved, where the real mod's reset on a reload. A cube's item eject button stays in the side window, where the real mod has `setCanEject(false)`, though it does nothing.
- Energy slots: a player can place an empty tablet, which the real slot refuses. The tag `c:dusts/redstone` is reduced to redstone and a block of it in the slot's placement rule, though the recipes run from the real tag.
- Tiers: no creative tier. Tubes and pipes have no pull. Cables of other tiers draw from their own textures, but only the basic one's look was checked by test. Each pipe and tube still has the plain model.
- Cube: no tinted slot holder or energy tab text, no block icons on side buttons, and the item cycle has input and output only, no `INPUT_OUTPUT`.
- Fluid Tank: glass with no model, screen, slots, item or edit mode. It only stores and emits.
- Oxidizer: the drain slot stays out of the menu.

Cost per item, counted by hand from the transcript. Rust lines are additions in `port/machine`.

| Item | Turns | Elapsed | Rust lines |
|---|---|---|---|
| 0 Disk | 2 | About 2 min | 0 (32 lines of Python) |
| 1 Ejecting | 5 | 14 min | 120 |
| 2 Player controls, with 3's encoding | About 25 | 52 min | 627 |
| 4 Energy slots | 3 | 14 min | 111 |
| 5 Tiers and cube screen, with 3's game test | About 9 | Not split | 352 |
| 6 Mechanical Pipe and Fluid Tank | About 7 | Not split | 296 |
| 7 Test speed | 2 | Not split | 0 |

Items 5, 6 and 7 together took 45 minutes. Turns are approximate, and elapsed times come from commit times, so they include unattended test runs. About 8 of item 2's turns went on finding Horizon's APIs, and 2 on the launcher's stale engine.

Item 5 is 6 tiered kinds in the model's terms, plus one screen. Once the first tier ran, adding the others was data, so the tier work itself was near the model's 2 to 4 turns a unit. The cube's screen and the first-tick finding took the rest.

### Upgrades and redstone control

`machine/engine/src/upgrades.rs` holds `UpgradeUtils`' arithmetic and `port/test_features.py` replays 15 recordings of it (530 rows), in single player and on a dedicated server, with all fields matching. From the recordings:

- Usage is `ceil(base * 10^(2*speed/8 - energy/8))` and ticks are `max(1, trunc(base * 10^(-speed/8)))`.
- Capacity is `usage * max(4, ticks)` once anything is installed, and `usage * 4` with nothing installed. So a chamber goes from 20 to 400 with 4 energy upgrades, and a higher count gives less: 8 energy upgrades give 200. Horizon's energy buffer is per block type, so `mek_energy_room` applies this per block.
- `control_type: "high"` runs only with a signal and `"low"` only without. A stopped machine keeps its progress and clears `active_state`. `"pulse"` behaves as `"disabled"` on these machines.

Proven able to fail by building each break: speed share over 4 instead of 8 fails `upgrade_idle_speed4` at tick 1; energy share ignored fails `upgrade_idle_energy4` at tick 1; capacity with a multiplier of only 4 fails `upgrade_idle_speed4` at tick 1; `high` and `low` swapped fails `redstone_high` at tick 2. The engine's own tests also hold the recorded values.

Known differences: only speed and energy upgrades. `operationsPerTick` isn't ported, and no recording needs it, since a chamber's fastest recipe takes 20 ticks.

### Oxidizer screen

`gui_oxidizer` in `machine/gui.rs` draws `GuiChemicalOxidizer` on a screen shared with the electric machines: the chemical gauge with its overlay and tinted gas, the horizontal power bar, the large progress arrow, input, drain and energy slots, the tabs, three side config kinds (items, chemicals, energy) and tooltips. `port/test_oxidizer_screen.py` checks it with the same screenshot and click method as the Enrichment Chamber: the art at each position, the gauge's level at 2,500 and 7,500 mB, the bar's length, tab order, chemical side buttons and the eject toggle.

Tooltips' words are tested in the engine, including the compact energy text (`5 FE/20 FE`, `1.5 kFE`). In the game, the test only sees that a tooltip of the right size appears, because it can't read text in a screenshot.

Proven able to fail by building each break: `OXIDIZER_GAUGE` x 131 to 132 (frame corner, 3 pixels); gas tint bytes swapped (15 rows wrong); gauge level rounded down (1 row wrong); energy tab before chemicals (tab icon, 83 pixels); gauge tooltip removed (no tooltip, 0 pixels); drain slot art `slot/extra` to `slot/output` (68 pixels); power bar level doubled (bar runs past its end); chemical side cycle output to input (top side got 1). One break, the power bar's width 2 pixels more, passed, because at this energy level both widths round to the same 10 pixels, so it was replaced by the doubled level.

A menu type declares its data slots in `data/mekanism/horizon/menu/*.json`, and anything beyond that count is silently dropped, which cost several turns here. It is now 17 for the machines. Values go as 16 bits, so a larger one takes two slots.

Known differences: the gauge draws frame 0 of the animated gas texture. Only sulfur dioxide has its tint, and other oxidizer products draw untinted though their names are right. The drain slot is drawn but isn't in the menu. No warnings on the gauge, bar or arrow, and no recipe viewer.

Cost of this item, for re-estimating the other screens: about 34 turns and 16 minutes to a first full pass (00:07 to 00:23), plus 15 minutes of unattended builds for the 8 break runs. The commit adds 374 lines of Rust and removes 94, of which 152 added are in `gui.rs` and 152 in `gui_layout.rs` (with its tests), plus a 296-line test. Turns were counted by hand from the transcript, so treat them as approximate. Roughly a third of the turns went on reading Mekanism's source and about 8 on the data slot limit, so a next screen with the same elements should cost less, though that is untested. A screen with a new element type, such as a scroll list or text field, is unmeasured.

### Full run

`--all` on this work: 17 of 17 runs passed in 1,738 s (29 minutes, against 58 before), with no launch crash. Group times: chemical 325 s and 323 s, machines 268 s and 266 s, chain 74 s and 92 s, generator 82 s, furnace 51 s and 40 s, menu 41 s, oxidizer screen 37 s, features 33 s and 21 s, cable look 28 s, GUI 25 s, transfer 17 s and 15 s.

### The launch crash

The crash above is not explained. What was established, in a 45-minute look at the crash report, Horizon's source at `f319701` and loops of launches:

- The faulting read is `s.name.clone()` in `Game::lan_host`, on the server thread. Its `Arc<str>` field reads as null at a valid heap address, inside `Resources.core.facts.states`. Nothing about the fault points at a thread race on a half-built value: that table is built once in safe code (`horizon-items` has `forbid(unsafe_code)`) and is read-only behind an `Arc` before the server thread starts. So something zeroed live memory or the report's read isn't what it appears to be.
- `port/machine` contains no `unsafe`, and its frames aren't on the stack. It can't write that memory directly. It could still trigger a bug elsewhere, and this isn't ruled out.
- Horizon sets mimalloc's purge delay to 0 (`configure_allocator`), which returns freed pages to the system at once. That could explain a page reading as zeros, but this is a guess with no evidence behind it.
- Launches with the carried content: modded dev build 51, 1 failed; plain Nightly `horizon-client` 50, 0 failed. Without content: 17 and 17, 0 failed. No new macOS crash report appeared, so the one failure wasn't shown to be this crash. It was at launch 75 of the loop, after 9.4 s, and my loop cut its message short, so what it was is unknown. At 1 crash in about 40 launches, 67 plain launches with none would happen by chance about 18% of the time, so they don't clear Horizon or blame the mod.
- A build of Horizon without the mod in the same `dev` profile wasn't tried, because it needs a full rebuild.

So it is not shown to be the mod's fault, and no change was made for it. `run_tests.py` now records any repeat with the log's tail and the path of the macOS report, which is the way to learn more.

### Test runner

`horizon_driver.run_test` wraps every test. A test calls `begin_checks` just before its first check. If the game has died by then, the test exits with code 75 and `run_tests.py` reports `LAUNCH CRASH`, runs the group once more and records that in the output and the last line. A second crash fails the group. Anything after `begin_checks`, or a failure with the game still alive, is a plain failure and never retried. A group that passes without calling `begin_checks` fails, so a test can't skip the mark.

The runner gives each run a `port/.work/run-...` folder for the tests' folders. It stops anything left in them and removes them when it ends, including on SIGTERM, and clears any `tmp...` and `run-...` left by earlier runs when it starts. A process is identified by its arguments, or by its working directory or an open file in the folder, because macOS hides most processes' environments from `ps`. `port/test_run_tests.py` tests all of this with stand-ins and no game. A real launch was checked with an engine that exits at once (exit 75), and SIGTERM to the runner during a chain run left no process or folder. (The batch of 2026-11-07's later work renamed this outcome "launch failure". See "Stale engine guard and failure evidence".) A real segfault hasn't gone through this path, since none recurred. On a dedicated server the supervisor may restart a crashed engine, which would then show as a plain failure rather than a launch crash; that is unverified.

### Osmium Compressor

`port/java_reference_advanced.py` records 14 scenarios of `TileEntityOsmiumCompressor` and `port/test_advanced.py` replays them in both modes with every field compared. `machine/engine/src/advanced.rs` and `machine/advanced.rs` hold the machine, and `port/test_compressor_screen.py` checks its screen in the way the oxidizer's is checked: art at the source's positions, progress, chemical bar, power bar, tooltips, the secondary slot by clicks and the side window.

From the recordings:

- 200 ticks, 15 FE and 1 mB a tick, so a tank of 210 runs a dust and 10 ticks more. An empty tank pauses with progress kept. A wrong chemical or no recipe resets.
- With 4 speed upgrades a recipe takes 63 ticks and uses 200 mB by `constantUse`: 3 a tick, rising to 4 near the end. A tank with less than a tick's use pauses, so 1 mB left stays there.
- An ingot gives its 200 mB only when all of it fits (`compressor_ingot_exact_fit`), before the recipe runs in the same tick.
- A placed compressor with no energy upgrades holds 60 FE.

Breaks that failed: usage 15 to 14 (`compressor_normal` tick 1); `constantUse` rounding up (`compressor_speed4` tick 1); a conversion ignoring room (`compressor_ingot` tick 2); running on a tank with less than a tick's use (`compressor_speed4` tick 67). Tank capacity 210 to 200 passed at first, because every recording set the tank by command. I added `compressor_ingot_exact_fit`, which fails it at tick 2. Screen breaks that failed: osmium tint's bytes swapped (`chemical bar at 150`, 9 rows); secondary slot a pixel off (2 pixels); energy slot a pixel off (50 pixels); secondary slot taking anything (`dirt refused`). The engine's own 2 tests hold the recorded normal and speed runs.

Known differences: one recipe type, `mekanism:compressing`, with all of its recipes `per_tick_usage`. The tank takes chemical only from a conversion recipe, not from a tube, since no recording covers one and `TUBE_JOINS` leaves it out, and no chemical item works in its slot. Its side window has items, chemicals and energy, but the item kinds have no extra side, so a hopper reaches the secondary slot by an input side. `menu_slot_rules` allows only an osmium ingot and block in the secondary slot, where the real mod reads tags. Removing a dust and then adding one back resets `used_so_far` here, which I neither read in the source nor recorded, so it may differ. Its screen shows no warnings or recipe viewer, like the others.

Recipes: the carried data here holds 1,675 recipes of Mekanism's own types, counting both mods, not the 1,718 this plan quoted before, and I can't say where that figure came from. 491 now do something: crushing 255, enriching 205, oxidizing 25, compressing 2, energy conversion 2, and the 2 osmium chemical conversions. The other 22 chemical conversions are unused so far. Types that still do nothing: painting 288, pigment extracting 275, sawing 157, injecting 109, combining 106, mek data 38, metallurgic infusing 31, purifying 28, dissolution 23, nucleosynthesizing 23, rotary 20, pigment mixing 16, reaction 14, crystallizing 10, washing 7, chemical infusing 5, separating 3, activating 2, centrifuging 2, evaporating 2, bin extract 1, bin insert 1, clear configuration 1.

Cost: 22 tool rounds counted from the transcript, from the first read of its source to writing this, without the 7 rounds of the chunk unload work that interrupted it. About 12 of them were reading and writing the shape of a machine with a tank for the first time, before the first build. It's above the model's 8 to 15 turns for a medium unit, and a machine that reuses this one should cost less, but that isn't measured because no second one was added. Rust added: 139 lines in `machine/advanced.rs`, 168 in the engine's `advanced.rs` with its tests, and about 165 across the existing files. Python: 126 for the recorder, 119 for the replay and 203 for the screen test.

Full run on this work, `--all` after the guard's build: 28 of 28 runs passed in 1,105 s, with no launch failure. `port/.work/machine-export/source-hash` and the engine's bytes named this source. New groups: `reload` 29 s and 22 s, `advanced` 52 s and 29 s, `compressor_screen` 37 s.

### Saved machines through a reload

This plan used to say the real mod always writes `component_upgrade`, so a fresh machine reloads holding 1,000 where the port stayed at 20. That was wrong, and came from reading `serialize` without a recording. `port/java_reference_reload.py` records 8 scenarios through a real server restart and 3 through a real chunk unload, and `port/test_reload.py` replays them in both modes, every field of every row:

| Machine before the restart | Key saved | Holds after reload |
|---|---|---|
| Fresh, empty; fresh with 15 FE; fresh with ore | No | 20 |
| Given `component_upgrade:{}` by command | No | 20 |
| 4 speed upgrades installed | Yes | 3,150 |
| None installed, 2 upgrades in the output slot | Yes | 1,000 |
| The same, with the slot then emptied | No | 20 |
| The same with no reload at all (`live_output_emptied`) | No | 1,000 |
| Emptied, through a chunk unload (`unload_output_emptied`) | No | 20 |
| 2 in the output slot, through a chunk unload | Yes | 1,000 |
| Fresh with 15 FE, through a chunk unload | No | 20 |

So the real rule is that the key is saved only if something is installed or in an upgrade slot, and a machine's capacity follows its upgrades only after a recalculation in this load.

`chain_after_reload` passed because this path had no difference. Its chamber and smelter are fresh machines, and in all 901 rows, with a cube supplying them after the restart, neither holds more than 20. Port and recording agreed, and no check needed fixing. Making the port hold 1,000 on any fresh machine fails `chain` at `network_split` tick 1 and `reload` at `reload_fresh_empty` tick 1.

The port did differ elsewhere. It treated the key's presence as the rule, so a machine with everything uninstalled stayed at 1,000 through a reload. Now capacity follows its upgrades if any are installed, or if a mark says the block has recalculated since it loaded. An install, an uninstall or an item in either upgrade slot sets the mark. It lives in the block entity's `data`, one value past what a menu sends. Horizon doesn't save `data` and rebuilds it empty in `decode_mod_block_entity`, so the mark goes on any load, as the real mod's in-memory state does. The key goes when nothing is under it, as in the real mod.

An earlier version held the process id in the saved data. That survived a chunk unload, which the recording shows is wrong: rebuilt that way, the port fails `unload_output_emptied` tick 1 in both modes (got 1,000, expected 20) while every `reload_*` row passes. The test checks that a read answers "not loaded" before it loads the chunk again, on both sides.

Breaks: not carrying the mark from tick to tick fails `reload_output_slot` tick 1 (got 20); slots not recalculating failed the same row on the earlier version, and the mark outlasting a reload failed `reload_output_emptied` tick 1 (got 1,000); the key kept after uninstalling all passed `upgrades` at first, so `test_upgrades` now uninstalls all and fails with `no saved upgrades once all are uninstalled`.

Known differences: the port learns of a slot's item in its first tick, where the real mod does as it loads. `test_reload` allows for that with one tick before its first row, with nothing supplying the machines. The real mod saves the slots under `component_upgrade.items`, and the port as container slots 3 and 4, so the test's `component` column reads either. A `data` command on a machine rebuilds its block entity here, which clears the mark, where the real mod keeps the capacity, so the test empties the slot by `item replace`. Re-entering a single-player world isn't recorded, since the real mod needs a Java client for that. It goes through the same decode here.

### Stale engine guard and failure evidence

The stale engine is real and now explained. `native-build` said "Incremental rebuild" and exported the previous binary. This sequence with a marker string in each crate showed it, on the launcher's own commands:

| Step | Build's first line | Markers in the exported engine | Time |
|---|---|---|---|
| 1 A | Incremental | A | 60 s |
| 2 B, A's build kept | Incremental | B | 44 s |
| 3 back to A, kept | Up to date | A | 8 s |
| 4 B, after a prune | Up to date | B | 7 s |
| 5 back to A, pruned | Incremental | **B** | 17 s |

The launcher keeps each source's patched copy under a key from the mod's files (`inject_cache`). Going back to a source it has seen copies that snapshot into the stage, with its old modified times, as far as the behaviour shows. I read `sync` and `inject_cache` but did not inspect a stage file's time. Cargo then sees files older than its last compile and compiles nothing, though the new version folder is recorded as A. Step 8 of the same run showed the engine crate has the same problem when a file comes back with an old time, as `cp -p` does. A build still in `server-builds` is "Up to date", which exports that folder and was correct in steps 3 and 4.

`port/source_hash.py` handles it. A file `engine/src/build_stamp.rs`, not in git, holds a hash of port/machine's files and a nonce, and `networks.rs` keeps the hash in the game with `black_box`. It survives into the binary, which step 1 above tested. The hash is taken over every file in the folder, so a new file not yet in git counts too. A new nonce means a key the launcher hasn't seen, so freshly patched source and a recompile of the engine crate and then the game crate that depends on it. The nonce changes for any source other than the last one built. `build_and_test.sh` then reads the hash from the engine's bytes. If it isn't there, the script writes a new nonce and builds again, and it stops if the hash is still missing. Only then does it write `machine-export/source-hash`. `run_tests.py` refuses to start unless the record and the engine's own bytes both name the current source, with or without `--no-build`.

Proven by real builds, with `upgrades` or `tiers` run in the game:

- Break in a game file (`mek.rs` uninstall removes 2): `--no-build` gave `REFUSED: the engine was built from source dac95ea333bf, but port/machine is now 62b7d0a84f9b`. A build and run failed with `one uninstalled: got 2, expected 3`. After `git checkout`, `--no-build` was refused the other way round, and a build and run passed in 73 s.
- Break in the engine crate (cable capacity 8,000 to 12,345): `tiers` failed at `tier_cable_mixed` tick 1. After restoring the file with `cp -p`, so that its old time came back, the build and `tiers` passed.
- Forced rebuild: the stale case put back by hand, with A's old stamp and "last built" record after a build of B. The first build exported B: `The exported engine doesn't hold source hash dac95ea333bf...`, then `Forcing a real rebuild with a new stamp`, then `upgrades` passed.

Could an earlier result have run a stale engine? Yes, and it can't be ruled out from what's left, because the exported engines were overwritten and no hash was recorded. A stale engine needed a return to a source the launcher had already built, in practice the revert after a break. So:

- Every first build of new work was real, because new content has a new key.
- A plain `--all` result is safe in one direction. A stale engine holds a reverted break, each reported break was shown to fail a group in `--all`, and those runs didn't fail on that break. The 2 stale runs PLAN.md mentioned before were noticed this way.
- A `--changed` or named-group run after a revert could have passed on an engine still holding a break outside those groups. Nothing recorded lets me say whether one did.
- The `--all` on the guarded engine below is the first result tied to its source.

Failure evidence. `run_tests.py` gives each attempt a short folder of its own and, if it doesn't pass, copies the evidence to `port/.work/failures/<time>-<group>-<mode>-<attempt>/` before removing the folder. The copy has `result.txt` (the result, output and exit status), `c.log`, the game's logs and any macOS report the output names, with logs and text first, up to 20 MB a failure and 100 MB in all. It leaves out the carried content, and `skipped.txt` names anything else left out. The runner never clears that folder, only drops the oldest past the cap. `launching` in `horizon_driver.py` reports any failure of the commands that start a game as a `LaunchFailure`, with exit status, stdout and stderr, so a launch that fails before the first check is a launch failure and gets one retry whether or not a crash report exists. After the first check, as in a restart, it stays a plain failure. It did its job at once: my first per-attempt folder name made the socket path too long, the game exited with `path must be shorter than SUN_LEN`, and the kept `c.log` said so.

`port/test_run_tests.py` checks these with stand-ins and no game. Breaks that failed it: the `LaunchFailure` case removed from `run_test`, launch failure classified as plain failure, the refusal removed, the size cap removed, the check of the engine's bytes removed, and a stamp of another source kept. The original segfault and empty-message launch failures have not recurred, so their causes are still unknown.

### Chain speed

The chain took 1,025 s a mode, and starting `horizon-ctl` wasn't the main cost. A frozen game takes one command a tick, so each read cost 50 ms at 20 ticks a second. Batching over several sockets gave nothing in single player (9 commands, 450 ms) because replies come back one a tick.

- `test_chain` sets `tick rate` high while frozen, and back to 20 before anything unfreezes. A step still moves exactly one tick, as a measured run of 10 steps showed.
- Commands use one kept connection: the control socket in single player and the HTTP API in dedicated mode.
- In single player `maxFps` goes to 260, because a control request also waits for a client frame.
- Dedicated mode caps the rate at 400 a second. At 10,000 the supervisor's new connection per command used up the local ports (os error 49) partway through the last recording, after at least 804 rows.

The chain now takes 76 s in single player and 94 s on a dedicated server, against 1,025 s each. It has the same 1,704 rows and the same comparisons. Changing the cube's energy in row 897 of `chain_after_reload.tsv` from 0 to 1 fails both modes with `chain_after_reload tick 897: cube got 0 expected 1`.

### Cost against the model

Measured from the session's transcript:

| Measure | Slice |
|---|---|
| Turns | 99 |
| Time | 2.4 hours, 20:48 to 23:10 |
| Total tokens | 34.6M, 191k of it output |
| Context per turn | Mean 347k, ending at 513k |
| Hand-written Rust | About 1,520 lines, plus 205 generated |
| Scripts | About 1,000 lines of Python |

Rust lines by item: chemicals, tube, oxidizer and tank about 640; GUI core and side window about 660; cable renderer about 220. The transcript gives no turns or hours by item.

The slice is about 4 hard units and 1 medium. With the 1.2 to 1.5 multiplier, the model gives 100 to 260 turns and 3.1 to 9.8 hours for that, so 99 turns and 2.4 hours are at the low end. Context per turn is at the model's high end of 400k and passed it. Scripts add about 0.65 lines of Python per Rust line against the 1.5 measured before.

Limits on reading this:

- The GUI's two hard units look too few. This slice ported about ten element types of the 13.7k Java lines, and no gauge, scroll list, text field, or per-machine screen. Each machine's screen is a cost the model doesn't count, and it is unmeasured because the oxidizer's real screen wasn't done.
- The renderer covers one model type with one hook. Fluid and chemical contents in tanks, and the MekaSuit's models, may cost more.
- The chemical layer's cost benefits from copying the cable's shape, so the next system with no such shape may land higher.
- Full-suite time isn't in the turn figures. At 1 hour and growing, it limits how often a merge can happen.

## Java reference

`port/java_server.py` runs the real Mekanism jar on a NeoForge 26.3 server on Tower and reads machines over RCON with `tick freeze`, `tick step 1` and `data get block`. An Enrichment Chamber traced for 420 consecutive ticks: 5 energy a tick, 200 ticks a recipe, 2 dust per ore.

- The jar is built on Tower (`./gradlew jar`, 20 minutes, needs about 6GB of memory). It holds the main module only, so the Heat Generator, in the generators module, needs another build.
- A server with no players stops ticking after 60 seconds unless `pause-when-empty-seconds` is off.
- `tick step` returns before the tick runs, so a read must wait for game time to move.
- `port/java_reference.py` records 10 scenarios of the Enrichment Chamber, Crusher and Energized Smelter into `port/reference/`, and the engine's tests replay them exactly.
- `port/java_reference_power.py` records the Heat Generator and a cube, cable and chamber chain. Machines tick first, then the cable network sends.
- Side config indexes follow `TransmissionType`, so `config0` is energy and `config3` is items.
- A machine with no upgrades holds 4 times its usage: a chamber holds 20.
- A block's ambient temperature comes from its biome and height, and each side has its own. The Heat Generator's port needs this from Horizon, and its replay compares heat to within 0.001 because a recording can't show each side's value.
- `data remove` on a machine's slot does nothing, because loading leaves slots that aren't named as they are. Setting an amount works.
- A machine placed with `setblock` has every side set to `NONE` and takes nothing. The trace sets its side config, items and energy in the `setblock`. Whether a player's placement differs is unchecked.
- `port/java_reference_chemical.py` records the oxidizer, tube and tank. A machine ejects before it makes anything in a tick, so a recipe's result leaves a tick later. config2 is the chemical side config. Tube shares appear in `data get` as `stored`, because a save asks the network for them.

## Testing

Each machine is compared against the Java mod in a fixture world: output, energy and progress per tick, menu values, and NBT after reload. Horizon's `docs/modpacks.md` sets out this method.

## Risks

- **High, Horizon updates.** A native mod pins one Horizon commit, and the code changes quickly. Stay on one revision and update on purpose. Named hook contracts don't change, so prefer them to mixins.
- **High, untested hooks.** Phase 0 ran only the block entity hooks. If a later hook doesn't hold up, the fallback is a Horizon fork.
- **Medium, bot compatibility.** Added blocks and items may break `horizon-companion`, which reads vanilla data and pins its protocol version. Its soak runs should stay on an unmodded server.
- **Medium, rendering.** Mekanism's custom renderers may need draw access that Horizon's hooks don't offer yet.
- **Low, dropped integrations.** The first version leaves out the 15k lines of integrations, such as other mods' APIs, and the mod's in-game config screens.

## Estimate

The Phase 4 slice came in at the low end on turns and hours and at the high end on context per turn, so the phase totals below are unchanged.

Re-estimated on 2026-11-06 from Phases 0 to 3. Phases 4 to 7 are still a model and could be off by a factor of 2 to 3, because the measurements come from the simplest machines.

### Measured for Phases 0 to 3

| Measure | First estimate | Measured |
|---|---|---|
| Non-test Rust | 14-23k lines | 2,085 lines, plus 3,104 lines of test scripts and 25 recordings |
| Time | 43-110 agent-hours | 6.1 hours elapsed, 12:08 to 18:13 |
| Total tokens | 70-250M | 164M, 97% of it cache reads and 438k of it output |
| Turns | About 40 per 1,000 lines | 281, or 135 per 1,000 lines |
| Context per turn | 80k | About 430k in the main session and 860k in the worker |

The token count is in range only because each turn read far more context than assumed. The worker was forked from the main session and inherited its context, so fresh agents with a narrow brief should cost less per turn. That saving is not measured.

The Rust count is low for two reasons: Horizon's hooks do much of the work, and many features are not ported yet (see Phase 3's known differences). Lines per Java line can't be measured fairly from this slice.

### Phases 4 to 7

| Phase | Rust lines | Agent-hours | Turns | Total tokens |
|---|---|---|---|---|
| 4: Cables, chemicals, machines | 10-25k | 20-60 | 750-1,800 | 110-730M |
| 5: Multiblocks | 3-7k | 5-15 | 170-420 | 25-170M |
| 6: Miner, logistics, MekaSuit | 7-20k | 17-55 | 630-1,500 | 95-600M |
| 7: Generators, Additions, Tools | 3-7k | 6-18 | 210-510 | 30-200M |
| **Total** | **23-59k** | **48-148** | **1,760-4,230** | **0.26-1.7B** |

Test scripts would add about 1.5 lines per Rust line, the measured ratio. Output would be about 3-7M tokens, at the measured 1,560 per turn.

The first estimate for these phases was 122-153k lines, 240-540 agent-hours and 0.35-1.3B tokens.

Three parallel agents are not assumed, because this Mac has 8GB of memory and about 7GB of free disk. Run one at a time, the port takes 6 to 19 working days at 8 hours a day, before usage limits and review time.

### How the model works

Each phase is counted in units of work, using the Java sizes in `upstream/`:

| Unit | Turns | Hours | Rust lines | Basis |
|---|---|---|---|---|
| Hard: a new system with its own engine, recordings and tests | 20-40 | 0.6-1.5 | 300-800 | The worker built about 4 in 94 turns and 2.6 hours |
| Medium: a recipe family, special machine or module | 8-15 | 0.2-0.5 | 100-300 | Judgement |
| Simple: a tier or variant on an existing engine | 2-4 | 0.05-0.1 | 5-20 | Judgement, from the Crusher and Smelter sharing the Chamber's engine |

| Phase | Hard | Medium | Simple |
|---|---|---|---|
| 4 | 14 | 24 | 75 |
| 5 | 7 | 0 | 0 |
| 6 | 11 | 38 | 0 |
| 7 | 4 | 12 | 0 |

- Phase 4's hard units are chemicals, pipes, tubes, conductors, upgrades, redstone and security, full side config, item energy slots, factories, rendering, sounds and particles, radiation, and 2 for the GUI library (13.7k Java lines).
- Phase 6's hard units are the Digital Miner, teleporter, logistical transport, Robit, 3 for QIO and 4 for the MekaSuit and its base. Its 32 modules are medium units.
- Hours and turns are multiplied by 1.2 to 1.5 for integration and hook failures. This multiplier is a judgement.
- Tokens use 150k to 400k of context per turn. The high end is close to the main session's measured rate. The low end assumes fresh agents and is unmeasured.
- Phase 4's GUI line count is the least certain. Two hard units at the usual size may be too few for 13.7k Java lines.

### Unknowns that could break this model

- Test time: about 50 minutes passed between the final build and the final results for the current 10 test groups, and that grows with each machine. The suite will need splitting.
- Rendering and custom block models: nothing so far has used Mekanism's own renderers.
- Hooks: the chemical, multiblock and entity work may need hooks that don't exist, and the fallback is a Horizon fork.

## Scope

Phases 0 to 3, decided on 2026-11-06, are done. Deciding on Phases 4 to 7 comes next.
