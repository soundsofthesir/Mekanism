#!/usr/bin/env python3
"""Replays machines through a save and reload from `java_reference_reload.py`, in single player and on
a dedicated server. Every field of every row must match, and row 0 is as the restart left the machine.

The port keeps the upgrade slots as the container's slots 3 and 4, so `component` here means what the
real mod's `component_upgrade` would hold: an installed upgrade, or an item in one of those slots.
"""

import argparse
import re
import sys
import time
from pathlib import Path

import java_reference_features as features
import java_reference_reload as java
import test_features
from horizon_driver import DedicatedServer, SinglePlayer, TestFailure, begin_checks, install_content, run_test

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
REFERENCE = HERE / "reference"
Y = 200
NORMAL_TICK_RATE = 20
OUTPUT_SLOT = re.compile(
    r'component_upgrade:\{items:\[\{container:1b,stored:\{amount:(\d+)L,type:\{id:"mekanism:upgrade",components:\{([^}]*)\}\}\}\}\]\},'
)
# The change that empties the output slot, in this port's format.
EMPTY_SLOT = "item replace block {at} container.4 with minecraft:air"


def here_block(block: str) -> str:
    found = OUTPUT_SLOT.search(block)
    if not found:
        return test_features.here_format(block)
    block = block.replace(found.group(0), "")
    slot = f'Items:[{{Slot:4b,id:"mekanism:upgrade",count:{found.group(1)},components:{{{found.group(2)}}}}}],'
    return test_features.here_format(block).replace("{", "{" + slot, 1)


def row(world, tick: int, x: int, z: int) -> list[str]:
    nbt = " ".join(world.command(f"data get block {x} {Y} {z}"))
    get = lambda pattern: (re.search(pattern, nbt) or [None, "0"])[1]
    speed, energy = get(r'"mekanism:speed": (\d+)'), get(r'"mekanism:energy": (\d+)')
    in_slots = test_features.slot_of(nbt, 3) != "-" or test_features.slot_of(nbt, 4) != "-"
    return [
        str(tick),
        get(r"progress: (\d+)"),
        get(r"active_state: (\d+)"),
        get(r"\benergy: (\d+)"),
        test_features.slot_of(nbt, 0),
        test_features.slot_of(nbt, 1),
        "1" if "component_upgrade: {" in nbt or in_slots else "0",
        speed,
        energy,
    ]


def freeze(world) -> None:
    world.command("tick freeze")
    world.command(f"tick rate {world.FAST_TICK_RATE}")


def unfreeze(world) -> None:
    world.command(f"tick rate {NORMAL_TICK_RATE}")
    world.command("tick unfreeze")


def place(world, scenario: java.Scenario, index: int) -> tuple[int, int]:
    x, z = java.at(index)
    answer = " ".join(world.command(f"setblock {x} {Y} {z} {here_block(scenario.block)}"))
    if "Changed" not in answer:
        raise TestFailure(f"{scenario.name}: setblock answered {answer}")
    return x, z


def expected(name: str) -> list[list[str]]:
    return [line.split("\t") for line in (REFERENCE / f"{name}.tsv").read_text().splitlines()[1:]]


def compare(name: str, got: list[str], wanted: list[str], failures: list[str]) -> None:
    if got != wanted:
        failures.append(f"{name} tick {wanted[0]}: got {got} expected {wanted}")


def unload_chunk(world, failures: list[str]) -> None:
    """Far from any player, so removing the force load really does unload the chunk."""
    x, z = java.UNLOAD_AT
    world.command(f"forceload add {x} {z}")
    wait_loaded(world, x, z, True)
    wanted = {scenario.name: expected(scenario.name) for scenario in java.UNLOAD_SCENARIOS}
    for index, scenario in enumerate(java.UNLOAD_SCENARIOS):
        at_z = z + index * 4
        answer = " ".join(world.command(f"setblock {x} {Y} {at_z} {here_block(scenario.block)}"))
        if "Changed" not in answer:
            raise TestFailure(f"{scenario.name}: setblock answered {answer}")
    # A tick for this port to learn of the slots. It's unfrozen here, so wait for one to pass.
    before = world.command("time query gametime")
    while world.command("time query gametime") == before:
        pass
    for index, scenario in enumerate(java.UNLOAD_SCENARIOS):
        if scenario.change:
            world.command(EMPTY_SLOT.format(at=f"{x} {Y} {z + index * 4}"))
    for index, scenario in enumerate(java.UNLOAD_SCENARIOS):
        compare(scenario.name, row(world, -1, x, z + index * 4), wanted[scenario.name][0], failures)
    world.command(f"forceload remove {x} {z}")
    wait_loaded(world, x, z, False)
    time.sleep(java.UNLOADED_SECONDS)
    world.command(f"forceload add {x} {z}")
    wait_loaded(world, x, z, True)
    freeze(world)
    for index, scenario in enumerate(java.UNLOAD_SCENARIOS):
        at_z = z + index * 4
        compare(scenario.name, row(world, 0, x, at_z), wanted[scenario.name][1], failures)
        world.command(f"setblock {x + 1} {Y} {at_z} {test_features.here_format(features.CUBE_FULL)}")
    for tick in range(1, java.TICKS + 1):
        test_features.step(world)
        for index, scenario in enumerate(java.UNLOAD_SCENARIOS):
            compare(scenario.name, row(world, tick, x, z + index * 4), wanted[scenario.name][tick + 1], failures)
    unfreeze(world)
    world.command(f"forceload remove {x} {z}")


def wait_loaded(world, x: int, z: int, wanted: bool) -> None:
    deadline = time.monotonic() + java.LOAD_TIMEOUT_SECONDS
    while True:
        answer = " ".join(world.command(f"data get block {x} {Y} {z}"))
        if ("not loaded" not in answer) == wanted:
            return
        if time.monotonic() > deadline:
            raise TestFailure(f"{x} {z} never became {'loaded' if wanted else 'unloaded'}: {answer[:120]}")
        time.sleep(0.5)


def run(world) -> None:
    world.start()
    world.command("forceload add 0 0 0 31")
    begin_checks()
    failures: list[str] = []
    wanted = {scenario.name: expected(scenario.name) for scenario in java.SCENARIOS}
    freeze(world)
    for index, scenario in enumerate(java.SCENARIOS):
        place(world, scenario, index)
    # A tick: this port learns of a machine's slots and tidies its data in one, where the real mod
    # does as it loads. Nothing else can change here, because nothing supplies these machines.
    test_features.step(world)
    for index, scenario in enumerate(java.SCENARIOS):
        if scenario.change:
            x, z = java.at(index)
            world.command(EMPTY_SLOT.format(at=f"{x} {Y} {z}"))
    for index, scenario in enumerate(java.SCENARIOS):
        compare(scenario.name, row(world, -1, *java.at(index)), wanted[scenario.name][0], failures)
    unfreeze(world)
    world.stop()
    world.start()
    world.command("forceload add 0 0 0 31")
    freeze(world)
    for index, scenario in enumerate(java.SCENARIOS):
        x, z = java.at(index)
        compare(scenario.name, row(world, 0, x, z), wanted[scenario.name][1], failures)
        world.command(f"setblock {x + 1} {Y} {z} {test_features.here_format(features.CUBE_FULL)}")
    for tick in range(1, java.TICKS + 1):
        test_features.step(world)
        for index, scenario in enumerate(java.SCENARIOS):
            compare(scenario.name, row(world, tick, *java.at(index)), wanted[scenario.name][tick + 1], failures)
    # Before any reload, an emptied machine still holds what its last recalculation gave.
    live = expected(java.LIVE.name)
    x, z = place(world, java.LIVE, len(java.SCENARIOS))
    test_features.step(world)
    world.command(EMPTY_SLOT.format(at=f"{x} {Y} {z}"))
    compare(java.LIVE.name, row(world, 0, x, z), live[0], failures)
    world.command(f"setblock {x + 1} {Y} {z} {test_features.here_format(features.CUBE_FULL)}")
    for tick in range(1, java.TICKS + 1):
        test_features.step(world)
        compare(java.LIVE.name, row(world, tick, x, z), live[tick], failures)
    unfreeze(world)
    unload_chunk(world, failures)
    world.stop()
    print(f"  {len(java.SCENARIOS) + len(java.UNLOAD_SCENARIOS) + 1} scenarios: {'differs' if failures else 'match'}", flush=True)
    if failures:
        raise TestFailure("\n".join(failures[:12]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--dedicated", action="store_true")
    parser.add_argument("--eula", action="store_true", help="you agree to the Minecraft EULA")
    args = parser.parse_args()
    if args.dedicated and not args.eula:
        parser.error("--dedicated writes eula=true: pass --eula if you agree to the Minecraft EULA")
    kind = DedicatedServer if args.dedicated else SinglePlayer

    def make(folder: Path):
        world = kind(folder, args.engine.resolve(), {})
        install_content(world.content_dir, WORK / "check/carry", WORK / "check-generators/carry")
        return world

    return run_test(make, run)


if __name__ == "__main__":
    sys.exit(main())
