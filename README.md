# Mekanism for Horizon

A port of the Mekanism mod (10.8.0, Minecraft 26.3) to [Horizon](https://github.com/horizon-rust/horizon), a Rust rewrite of Minecraft 26.3. The original is Java on NeoForge. The port is a Horizon native mod written in Rust.

This project is not affiliated with or endorsed by the Mekanism team or by Horizon. Mekanism is written by its authors at https://github.com/mekanism/Mekanism, and this port is built from their source.

## Status

The port is unfinished and cannot be played as a full mod. Phases 0 to 3 of the plan passed on 2026-11-06. Phase 4 (all cables and pipes, chemicals, the remaining machines and tiers) is in progress, and Phases 5 to 7 have not started. PLAN.md has the phases, measurements and known differences from the real mod.

What works:

- Ores and basic blocks and items, carried over from the Mekanism jar.
- A machine layer with block entities, menus and screens, energy, item and fluid transfer, and client sync.
- The chain from ore to doubled ingots: Heat Generator, Universal Cable, Energy Cube, Enrichment Chamber, Crusher and Energized Smelter.
- Chemicals, with the Chemical Oxidizer, the Pressurized Tube and the Chemical Tank.
- The Mechanical Pipe and the Fluid Tank.
- Cable, tube, pipe, cube and tank tiers.
- The Osmium Compressor, Combiner, Precision Sawmill, Purification Chamber, Chemical Injection Chamber and Metallurgic Infuser, each with its real screen.
- Upgrades, redstone control, side configuration, item ejecting and energy slots on the machines.

What is missing:

- Seven recipe machines, from the Chemical Infuser to the Pressurized Reaction Chamber. They need a second shared engine.
- Connection modes, redstone and pulling on cables, tubes and pipes.
- Chemical item slots, and real Fluid Tank and Chemical Tank items and screens.
- Creative tiers of the cube and tanks.
- The Heat Generator's real screen, and the security and transporter tabs, which are drawn but do nothing.
- Multiblocks, the Digital Miner, the teleporter, logistics, QIO, the Robit, the MekaSuit, generators beyond the Heat Generator, Additions and Tools.

## How it is checked

The real Java mod runs on a NeoForge server, and scripts record its behaviour tick by tick into `port/reference/`. The port's tests replay each scenario in single player and on a dedicated server, and compare every value with the recording.

## Build and test

The port is pinned to Horizon Nightly `f319701` (hook API 409), commit `f319701e8c9ab657ff562250b3ba07b2d654e3bc`. It needs that Nightly's launcher and game files, and a Python 3 install.

The build runs native code inside the game. `--trust-native-code` records that you read `port/machine` and trust it. `--eula` records that you agree to the Minecraft EULA, which the dedicated server tests need.

```sh
sh port/build_and_test.sh --trust-native-code --eula
```

This builds `port/machine`, then runs every test group. It writes build output to `port/.work/build.txt` and results, with each group's time, to `port/.work/results.txt`. To run less:

```sh
sh port/build_and_test.sh --trust-native-code --eula --changed
sh port/build_and_test.sh --trust-native-code --eula --no-build gui menu
python3 port/run_tests.py --list
python3 port/run_tests.py --all
python3 port/run_tests.py chain menu machines:dedicated
python3 port/run_tests.py --changed main --dry-run
```

`--changed [ref]` picks the groups for files that differ from a git ref. `--all` runs every group and is the one to use before a merge. A group name runs both modes, and `name:single` or `name:dedicated` runs one.

The machine logic in `port/machine/engine` has no game types. Test it alone with `sh port/test_engine.sh`. The runner's own tests need no game: `python3 port/test_run_tests.py`.

The scripts named `port/java_reference_*.py` record the real mod. They need a NeoForge 26.3 server with the real Mekanism jars, started with `port/java_server.py`. PLAN.md describes the setup. Replaying the existing recordings does not need that server.

`probe/README.md` explains the Phase 0 probe and its build and test commands.

## Layout

- `port/machine` is the native mod in Rust. `port/machine/engine` holds the machine logic and its unit tests.
- `port/reference` holds the recordings of the real mod.
- `port` also holds the Python tests, the recorders and the tools that carry Mekanism's content over.
- `probe` is the Phase 0 probe, a small native mod that checks a ticking block keeps its state through save and load.
- `PLAN.md` is the plan, with each phase's results.
- `LICENSE` is Mekanism's licence.

## Licence

Mekanism is MIT licensed. See `LICENSE` for its copyright notice and terms. This repository does not state a licence for the port's own code.
