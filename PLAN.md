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

- Machines: no sounds, particles or radiation. Items aren't ejected on their own (`eject3` is ignored; see Phase 4's next steps). Energy item slots are hidden. A menu's input slot takes any item, because Horizon's slot rule has no recipe table at hand, though a hopper is held to recipes.
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

- Chemicals: basic tube and basic tank only. Only the oxidizer holds chemicals as a machine. No gas dumping, radiation, chemical item slots or `canEject` rules beyond the sides. A tube has no connection modes or redstone control.
- Tube shares: the real mod's network order comes from a hash, so which tube gets a remainder isn't copied. `test_chemical` compares shares sorted within each row. Two real runs gave the same order, so it may be stable there, but its source says identity hash.
- Tubes with different chemicals don't join, which matches `isValidTransmitter`, but no recording covers it or the merge when two networks meet.
- Oxidizer: its `active` state isn't shown on the block, whose carried model has none. See its screen below for the rest.
- Chemical Tank: no screen, slots or dump mode. Its carried block is a carved pumpkin template with its real model name, and its real tank model's custom drawing isn't done.
- Machine screen: there is no recording of the real screen, because that needs a Java client. Positions and art come from source. Tabs for upgrades, security, redstone, experience and transporter config are drawn but do nothing, so a player can't install upgrades or change redstone control yet: only saved data does. Tooltips cover side buttons, the power bar, the side tab, the energy tab and the gauge. No warnings, recipe viewer, block icons on side buttons or window dragging and pinning. Item ejecting can be toggled but still does nothing. A press makes no click sound, since the hook is read only. Text is hard-coded English from `en_us.json` for the window. The energy slot is drawn but isn't in the menu.
- The Heat Generator's screen is still the plain one, and the Energy Cube has none.
- Universal Cable: base tier, normal and none connections only, with no glass or pull and push parts. Connections come from a tag list, not from checking that the neighbour's side takes energy. Contents show this cable's share, not the network's scale with its fade of 0.02 a tick. Alpha below 100% and the look on a dedicated server's client are unverified. The Pressurized Tube still uses the plain model.
- `port/machine` adds `mek_send_menu_button` and `vertices_mut` use, both outside the named catalog.

Not tested: a client on a dedicated server, and frame time with many cables.

Full run on the slice, `--all` after a clean build: 13 of 14 runs passed in 58 minutes. The 14th, `menu`, stopped when the game crashed while opening its world, before any of the test's checks. It then passed 3 of 3 runs on the same build. The crash is a null `Arc` clone in the `lan_host` closure while it maps `StateFacts`, under `ChunkEncoder::with_signs` (macOS report at 22:20). The cause is unknown. Nothing in `port/machine` names `lan_host` or `ChunkEncoder`, but that doesn't clear the mod, because its blocks are in that state table. It happened once in an estimated 40 launches and may recur in any group. A crash before a test's first check isn't a test failure, but it must be recorded here.

Group times, each mode, before the change below: chain 1,025 s, chemical 325 s, machines 265 s, generator 83 s, furnace 55 s and 39 s, menu 40 s, cable look 33 s, GUI 24 s, transfer 17 s and 14 s.

### Next steps

Item ejecting is not done. `port/reference/eject_*.tsv` already holds the recordings and `java_reference_features.py` makes them. What they and `TileComponentEjector` show:

- The ejector ticks before the recipe, and after each attempt it waits `tickDelay = 10`, so attempts come every 11 ticks from the first tick (ticks 1, 12, ... 210, ... 408). A running chamber's result made at tick 201 leaves at tick 210.
- An attempt moves a whole slot in one tick: 70 dust left at tick 1 into a chest, in one attempt.
- `eject_off` and `eject_closed_side` move nothing.
- What's needed: a way to put items in a neighbour. Look at how Horizon's hopper inserts, and add `test_features` rows that compare the chest column, which it currently skips. Remove "Items aren't ejected" from Phase 3's differences only when `eject_*` match.

After that, the shared features still missing from a player's reach: the upgrade tab and slot, and the redstone tab's button. `machines`, `chemical` and `generator` groups could take the chain's fast tick rate, since they also step while frozen, and would save several minutes a run.

### Upgrades and redstone control

`machine/engine/src/upgrades.rs` holds `UpgradeUtils`' arithmetic and `port/test_features.py` replays 15 recordings of it (530 rows), in single player and on a dedicated server, with all fields matching. From the recordings:

- Usage is `ceil(base * 10^(2*speed/8 - energy/8))` and ticks are `max(1, trunc(base * 10^(-speed/8)))`.
- Capacity is `usage * max(4, ticks)` once anything is installed, and `usage * 4` with nothing installed. So a chamber goes from 20 to 400 with 4 energy upgrades, and a higher count gives less: 8 energy upgrades give 200. Horizon's energy buffer is per block type, so `mek_energy_room` applies this per block.
- `control_type: "high"` runs only with a signal and `"low"` only without. A stopped machine keeps its progress and clears `active_state`. `"pulse"` behaves as `"disabled"` on these machines.

Proven able to fail by building each break: speed share over 4 instead of 8 fails `upgrade_idle_speed4` at tick 1; energy share ignored fails `upgrade_idle_energy4` at tick 1; capacity with a multiplier of only 4 fails `upgrade_idle_speed4` at tick 1; `high` and `low` swapped fails `redstone_high` at tick 2. The engine's own tests also hold the recorded values.

Known differences: only speed and energy upgrades, with no installing by a player and no chemical or other upgrades. Capacity shown in a menu is cut to 16 bits by the menu's data slots, which holds for these numbers (a chamber's largest recorded capacity is 10,000) but not for an energy amount loaded above 32,767. `operationsPerTick` isn't ported, and no recording needs it, since a chamber's fastest recipe takes 20 ticks.

### Oxidizer screen

`gui_oxidizer` in `machine/gui.rs` draws `GuiChemicalOxidizer` on a screen shared with the electric machines: the chemical gauge with its overlay and tinted gas, the horizontal power bar, the large progress arrow, input, drain and energy slots, the tabs, three side config kinds (items, chemicals, energy) and tooltips. `port/test_oxidizer_screen.py` checks it with the same screenshot and click method as the Enrichment Chamber: the art at each position, the gauge's level at 2,500 and 7,500 mB, the bar's length, tab order, chemical side buttons and the eject toggle.

Tooltips' words are tested in the engine, including the compact energy text (`5 FE/20 FE`, `1.5 kFE`). In the game, the test only sees that a tooltip of the right size appears, because it can't read text in a screenshot.

Proven able to fail by building each break: `OXIDIZER_GAUGE` x 131 to 132 (frame corner, 3 pixels); gas tint bytes swapped (15 rows wrong); gauge level rounded down (1 row wrong); energy tab before chemicals (tab icon, 83 pixels); gauge tooltip removed (no tooltip, 0 pixels); drain slot art `slot/extra` to `slot/output` (68 pixels); power bar level doubled (bar runs past its end); chemical side cycle output to input (top side got 1). One break, the power bar's width 2 pixels more, passed, because at this energy level both widths round to the same 10 pixels, so it was replaced by the doubled level.

A menu type declares its data slots in `data/mekanism/horizon/menu/*.json`, and anything beyond that count is silently dropped, which cost several turns here. It is now 10 for the machines. Values go as 16 bits.

Known differences: the gauge draws frame 0 of the animated gas texture. Only sulfur dioxide has its tint, and other oxidizer products draw untinted though their names are right. The drain and energy slots are drawn but aren't in the menu. No warnings on the gauge, bar or arrow, and no recipe viewer.

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

The runner gives each run a `port/.work/run-...` folder for the tests' folders. It stops anything left in them and removes them when it ends, including on SIGTERM, and clears any `tmp...` and `run-...` left by earlier runs when it starts. A process is identified by its arguments, or by its working directory or an open file in the folder, because macOS hides most processes' environments from `ps`. `port/test_run_tests.py` tests all of this with stand-ins and no game. A real launch was checked with an engine that exits at once (exit 75), and SIGTERM to the runner during a chain run left no process or folder. A real segfault hasn't gone through this path, since none recurred. On a dedicated server the supervisor may restart a crashed engine, which would then show as a plain failure rather than a launch crash; that is unverified.

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
