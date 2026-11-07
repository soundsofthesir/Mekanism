#!/usr/bin/env python3
"""Replays the Mechanical Pipe and Fluid Tank recordings: every cell of every row must match."""

import argparse
import sys
from pathlib import Path

import java_reference_pipe as java
import test_features as features
from horizon_driver import DedicatedServer, SinglePlayer, TestFailure, begin_checks, install_content, run_test

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
REFERENCE = HERE / "reference"
Y = java.Y
NORMAL_TICK_RATE = 20


def row(world, tick: int, count: int) -> list[str]:
    return [str(tick), *(java.amount(" ".join(world.command(f"data get block 0 {Y + y} 0"))) for y in range(count))]


def replay(world, scenario: java.Scenario) -> list[str]:
    world.command(f"tick rate {NORMAL_TICK_RATE}")
    world.command("tick unfreeze")
    world.command(f"fill 0 {Y} 0 0 {Y + 5} 0 air")
    world.command("tick freeze")
    world.command(f"tick rate {world.FAST_TICK_RATE}")
    for y, block in enumerate(scenario.blocks):
        answer = " ".join(world.command(f"setblock 0 {Y + y} 0 {block}"))
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
