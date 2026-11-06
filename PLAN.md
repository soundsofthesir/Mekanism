# Plan: port Mekanism to Horizon

Status: Phases 0, 1 and 2 passed on 2026-11-06. Phase 3 is in progress: the Enrichment Chamber, Crusher and Energized Smelter match the real mod's recordings in Horizon, in single player. The Heat Generator and one cable with one target match in the engine only. Menus, side config, cable networks and the full chain are left.

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

## Phase 3 progress

`port/test_phase3.py` replays 10 recordings of the real mod in Horizon with the same `tick step` method: 1,270 ticks and no differences. It compares progress, activity, energy and both slots.

`port/add_common_tags.py` is needed after the carry. Mekanism's recipes name `c:` tags that NeoForge's jar provides, and 131 of the 198 they use were missing. Without them, recipes with those ingredients find nothing, which Phase 1's 4-recipe sample didn't catch.

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

## Testing

Each machine is compared against the Java mod in a fixture world: output, energy and progress per tick, menu values, and NBT after reload. Horizon's `docs/modpacks.md` sets out this method.

## Risks

- **High, Horizon updates.** A native mod pins one Horizon commit, and the code changes quickly. Stay on one revision and update on purpose. Named hook contracts don't change, so prefer them to mixins.
- **High, untested hooks.** Phase 0 ran only the block entity hooks. If a later hook doesn't hold up, the fallback is a Horizon fork.
- **Medium, bot compatibility.** Added blocks and items may break `horizon-companion`, which reads vanilla data and pins its protocol version. Its soak runs should stay on an unmodded server.
- **Medium, rendering.** Mekanism's custom renderers may need draw access that Horizon's hooks don't offer yet.
- **Low, dropped integrations.** The first version leaves out the 15k lines of integrations, such as other mods' APIs, and the mod's in-game config screens.

## Estimate

These figures are modelled, not measured, and could be off by a factor of 2 to 3.

| Phase | Rust lines | Agent-hours | Total tokens |
|---|---|---|---|
| 0: Feasibility test | 1k | 5-15 | 5-20M |
| 1: Static content | 2k | 5-15 | 10-30M |
| 2: Machine layer | 3-8k | 8-30 | 15-80M |
| 3: Working chain | 8-12k | 25-50 | 40-120M |
| 4: Cables, chemicals, machines | 60-70k | 110-240 | 170-600M |
| 5: Multiblocks | 12-18k | 30-70 | 40-150M |
| 6: Miner, logistics, MekaSuit | 35-45k | 70-160 | 100-400M |
| 7: Generators, Additions, Tools | 15-20k | 30-70 | 40-150M |
| **Total** | **135-175k** | **285-650** | **0.45-1.5B** |
| **Phases 0-3 only** | **14-23k** | **43-110** | **70-250M** |

With three parallel agents from Phase 4, the whole port takes 140 to 325 hours of elapsed time. At about 8 hours a day that is 4 to 8 weeks, before usage limits and review time.

About 6-20M of the tokens would be output. The rest is input, roughly 90% of it cache reads.

Assumptions:

- Rust comes to about 70-90% of the 209k Java lines, including the machine layer.
- Phase 2 is now an adapter over Horizon's hooks, 3-8k lines instead of 15-25k, at the same hours and tokens per line. This is a judgement, not a measurement. Later phases keep their old figures, though the hooks may reduce them too.
- Each finished line takes about 3 written lines, at about 12 tokens a line.
- Each 1,000 finished lines take about 3M input tokens: around 40 turns at 80k of context.
- A verified, tested port produces about 250-500 finished lines per agent-hour.
- Three parallel agents do the work of about 2.5.

The biggest unknowns are incremental build times, how far the untested hooks hold up, and the work to build the Java comparison tests. After Phase 3, replace these assumptions with the measured tokens per line and lines per hour, then re-estimate Phases 4 to 7.

## Scope

Phases 0 to 3, decided on 2026-11-06. After Phase 3, replace the assumptions above with measured rates and decide on Phases 4 to 7.
