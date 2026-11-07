#!/usr/bin/env python3
"""Replays the Osmium Compressor's recordings from `java_reference_advanced.py`, in single player and
on a dedicated server. Every field of every row must match.

The port's slots are input 0, output 1, energy 2, then two for upgrades, then secondary 5.
"""

import argparse
import re
import sys
from pathlib import Path

import java_reference_advanced as java
import test_features
from horizon_driver import DedicatedServer, SinglePlayer, TestFailure, begin_checks, install_content, run_test

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
REFERENCE = HERE / "reference"
Y = 200
NORMAL_TICK_RATE = 20
# The real mod's slots to this port's: input, secondary, output and energy.
SLOT_MAP = {"0": "0", "1": "5", "2": "1", "3": "2"}


def here_block(block: str) -> str:
    block = re.sub(r"\{container:(\d)b", lambda m: f"{{container:{SLOT_MAP[m.group(1)]}b", block)
    # The tank's `container:0b` stays as it was.
    return test_features.here_format(block)


def here_change(line: str) -> str:
    """The real mod's slot empties by its amount, and this port's by the item command."""
    if "items[0].stored.amount set value 0L" in line:
        return f"item replace block 0 {Y} 0 container.0 with minecraft:air"
    raise TestFailure(f"no form of this change here: {line}")


def row(world, tick: str) -> list[str]:
    nbt = " ".join(world.command(f"data get block 0 {Y} 0"))
    get = lambda pattern: (re.search(pattern, nbt) or [None, "0"])[1]
    tank = re.search(r'chemical_tanks: \[\{container: 0b, stored: \{amount: (\d+)L, type: "([^"]+)"', nbt)
    return [
        tick,
        get(r"progress: (\d+)"),
        get(r"active_state: (\d+)"),
        get(r"\benergy: (\d+)"),
        test_features.slot_of(nbt, 0),
        test_features.slot_of(nbt, 5),
        test_features.slot_of(nbt, 1),
        tank.group(2) if tank else "-",
        tank.group(1) if tank else "0",
    ]


def replay(world, scenario: java.Scenario) -> list[str]:
    world.command(f"tick rate {NORMAL_TICK_RATE}")
    world.command("tick unfreeze")
    world.command(f"fill 0 {Y} 0 2 {Y} 1 air")
    world.command("tick freeze")
    world.command(f"tick rate {world.FAST_TICK_RATE}")
    for x, block in enumerate(scenario.blocks):
        answer = " ".join(world.command(f"setblock {x} {Y} 0 {here_block(block)}"))
        if "Changed" not in answer:
            raise TestFailure(f"{scenario.name}: setblock answered {answer}")
    expected = (REFERENCE / f"{scenario.name}.tsv").read_text().splitlines()
    changes = dict(scenario.changes)
    failures = []
    got = row(world, "0")
    if got != expected[1].split("\t"):
        failures.append(f"{scenario.name} tick 0: got {got} expected {expected[1]}")
    for line in expected[2:]:
        if failures:
            break
        wanted = line.split("\t")
        if int(wanted[0]) in changes:
            world.command(here_change(changes[int(wanted[0])]))
        test_features.step(world)
        got = row(world, wanted[0])
        if got != wanted:
            failures.append(f"{scenario.name} tick {wanted[0]}: got {got} expected {wanted}")
    print(f"  {scenario.name}: {len(expected) - 2} rows, {'differs' if failures else 'matches'}", flush=True)
    return failures


def run(world) -> None:
    world.start()
    world.command("forceload add 0 0")
    begin_checks()
    failures: list[str] = []
    for scenario in java.SCENARIOS:
        failures += replay(world, scenario)
    world.command(f"tick rate {NORMAL_TICK_RATE}")
    world.command("tick unfreeze")
    world.stop()
    if failures:
        raise TestFailure("\n".join(failures))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
