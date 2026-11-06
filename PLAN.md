# Plan: port Mekanism to Horizon

Status: not started. The scope decision below is open.

## Source and target

- **Source:** Mekanism 10.8.0 for Minecraft 26.3 and NeoForge, commit `ff721ff39f`. It is MIT licensed, so a port must keep its copyright notice. `upstream/` holds a clone for reference and git ignores it. To recreate it, run `git clone https://github.com/mekanism/mekanism upstream`.
- **Target:** [Horizon](https://github.com/horizon-rust/horizon), a Rust rewrite of Minecraft 26.3. These findings come from revision `baa379d`.

## Findings

- Java code doesn't run in Horizon, so all of the mod's code needs rewriting. That is about 209k lines to port, including 39k of client code. Datagen, integrations and tests are another 45k.
- `horizon-port-pack` carries over data, assets, worldgen and basic block and item definitions.
- Horizon has no mod API for ticking block entities, menus, energy, item and fluid transfer, or custom recipe types. API 0.4 would add them, but it is a draft (#1189), and the roadmap says the code-mods path hasn't started.
- WebAssembly mods are ruled out because that runtime is due for removal.
- Native mods are the only route. They are experimental, unsandboxed and compiled into a separate game build.

## Phases

| # | Work | Done when | Complexity |
|---|---|---|---|
| 0 | Read #1189 and test the riskiest part with a native mod | A ticking block keeps its state through save and load, in single player and on a dedicated server | Medium, go/no-go |
| 1 | Run `horizon-port-pack` on a Mekanism jar | Ores generate; items, simple blocks and ordinary crafting recipes work | Low |
| 2 | Build the machine layer: block entities, menus and screens, energy, item and fluid transfer, client sync | A furnace matches vanilla tick for tick | High |
| 3 | Build one working chain: recipe engine, Heat Generator, Universal Cable, Energy Cube, Enrichment Chamber, Crusher, Energized Smelter | Ore to doubled ingots on cable power, with progress, energy and saved state matching Java | High |
| 4 | All cables and pipes, chemicals, remaining machines and tiers | About 119 block entity types and 72 menus work (counts approximate) | Very high |
| 5 | Multiblocks: Dynamic Tank, Induction Matrix, boiler, evaporation, SPS | Each forms, runs and reloads | High |
| 6 | Digital Miner, teleporter, logistics, QIO, Robit, MekaSuit and its 32 modules | Each passes its own comparison test | Very high |
| 7 | Generators (including fission and fusion), Additions, Tools | Each module passes its tests | High |

## Testing

Each machine is compared against the Java mod in a fixture world: output, energy and progress per tick, menu values, and NBT after reload. Horizon's `docs/modpacks.md` sets out this method.

## Risks

- **High, API overlap.** API 0.4 could replace the machine layer in Phase 2. Keeping Mekanism logic separate from the Horizon integration limits the rewrite.
- **High, Horizon updates.** Mixins pin the mod to one Horizon revision, so each update may need rework. Stay on one revision and update on purpose.
- **High, Phase 0 could fail.** Nobody has confirmed that mixins can reach the server and world code cleanly. If they can't, the choices are a Horizon fork or waiting for API 0.4.
- **Medium, bot compatibility.** Added blocks and items may break `horizon-companion`, which reads vanilla data and pins its protocol version. Its soak runs should stay on an unmodded server.
- **Medium, rendering.** Mekanism's custom renderers may need draw access that Horizon's hooks don't offer yet.
- **Low, dropped integrations.** The first version leaves out the 15k lines of integrations, such as other mods' APIs, and the mod's in-game config screens.

## Estimate

These figures are modelled, not measured, and could be off by a factor of 2 to 3.

| Phase | Rust lines | Agent-hours | Total tokens |
|---|---|---|---|
| 0: Feasibility test | 1k | 5-15 | 5-20M |
| 1: Static content | 2k | 5-15 | 10-30M |
| 2: Machine layer | 15-25k | 40-90 | 80-250M |
| 3: Working chain | 8-12k | 25-50 | 40-120M |
| 4: Cables, chemicals, machines | 60-70k | 110-240 | 170-600M |
| 5: Multiblocks | 12-18k | 30-70 | 40-150M |
| 6: Miner, logistics, MekaSuit | 35-45k | 70-160 | 100-400M |
| 7: Generators, Additions, Tools | 15-20k | 30-70 | 40-150M |
| **Total** | **150-190k** | **315-710** | **0.5-1.7B** |
| **Phases 0-3 only** | **26-40k** | **75-170** | **135-420M** |

With three parallel agents from Phase 4, the whole port takes 170 to 390 hours of elapsed time. At about 8 hours a day that is 4 to 10 weeks, before usage limits and review time.

About 6-20M of the tokens would be output. The rest is input, roughly 90% of it cache reads.

Assumptions:

- Rust comes to about 70-90% of the 209k Java lines, including the new machine layer.
- Each finished line takes about 3 written lines, at about 12 tokens a line.
- Each 1,000 finished lines take about 3M input tokens: around 40 turns at 80k of context.
- A verified, tested port produces about 250-500 finished lines per agent-hour.
- Three parallel agents do the work of about 2.5.

The biggest unknowns are Horizon build times and memory use, the Phase 0 outcome, and the work to build the Java comparison tests. After Phase 3, replace these assumptions with the measured tokens per line and lines per hour, then re-estimate Phases 4 to 7.

## Open decision

Scope: Phases 0 to 3 only (recommended), the full port, or wait for API 0.4.
