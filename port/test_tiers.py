#!/usr/bin/env python3
"""Replays the tier recordings from `java_reference_tiers.py`: every cell of every row must match."""

import argparse
import re
import sys
from pathlib import Path

import java_reference_tiers as java
import test_features as features
from horizon_driver import DedicatedServer, SinglePlayer, TestFailure, begin_checks, install_content, run_test

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
REFERENCE = HERE / "reference"
Y = java.Y
NORMAL_TICK_RATE = 20


def cells(nbt: str, chem_field: str) -> list[str]:
    energy = re.search(r"\benergy: (\d+)", nbt)
    chem = re.search(r"\bstored: \{amount: (\d+)L, (?:id|type): \"mekanism:sulfur", nbt)
    tablets = []
    for slot in (0, 1):
        found = next((entry for entry in features.item_entries(nbt) if f"Slot: {slot}b" in entry), "")
        held = re.search(r"horizon_energy: (\d+)", found)
        tablets.append(held.group(1) if held and held.group(1) != "0" else "-")
    return [energy.group(1) if energy else "0", chem.group(1) if chem else "0", *tablets, features.slot_of(nbt, 0)]


def row(world, tick: int, count: int) -> list[str]:
    out = [str(tick)]
    for x in range(count):
        out += cells(" ".join(world.command(f"data get block {x} {Y} 0")), "")
    return out


def replay(world, scenario: java.Scenario) -> list[str]:
    world.command(f"tick rate {NORMAL_TICK_RATE}")
    world.command("tick unfreeze")
    world.command(f"fill 0 {Y} 0 5 {Y} 0 air")
    world.command("tick freeze")
    world.command(f"tick rate {world.FAST_TICK_RATE}")
    for x, block in reversed(list(enumerate(scenario.blocks))):
        answer = " ".join(world.command(f"setblock {x} {Y} 0 {features.here_format(block)}"))
        if "Changed" not in answer:
            raise TestFailure(f"{scenario.name}: setblock answered {answer}")
    count = len(scenario.blocks)
    expected = (REFERENCE / f"{scenario.name}.tsv").read_text().splitlines()
    failures = []
    for line in expected[1:]:
        wanted = line.split("\t")
        features.step(world)
        got = row(world, int(wanted[0]), count)
        if got != wanted:
            failures.append(f"{scenario.name} tick {wanted[0]}: got {got} expected {wanted}")
            break
    print(f"  {scenario.name}: {len(expected) - 1} rows, {'differs' if failures else 'matches'}", flush=True)
    return failures


def run(world) -> None:
    world.start()
    world.command("forceload add 0 0")
    begin_checks()
    failures = []
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
