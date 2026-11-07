#!/usr/bin/env python3
"""Phase 3 test: Mekanism's machines in Horizon against the real mod, tick by tick.

    python3 port/test_phase3.py --engine port/.work/machine-export/horizon-engine
    python3 port/test_phase3.py --engine port/.work/machine-export/horizon-engine --dedicated --eula

Replays each recording in port/reference/ with the same `tick step` method that made it, and every
row must match. Each machine starts in a new place, with the same contents as the recording.
"""

import argparse
import re
import sys
import time
from pathlib import Path
from typing import NamedTuple

from horizon_driver import DedicatedServer, SinglePlayer, TestFailure, install_content, begin_checks, run_test

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
REFERENCE = HERE / "reference"
Y = 200
STEP_TIMEOUT_SECONDS = 30
HEADER = "tick\tprogress\tactive\tenergy\tinput\toutput"
INPUT_SLOT, OUTPUT_SLOT = 0, 1
CHAMBER, CRUSHER, SMELTER = "enrichment_chamber", "crusher", "energized_smelter"
IRON_ORE = "minecraft:iron_ore"
DUST = "mekanism:dust_iron"


class Scenario(NamedTuple):
    name: str
    block: str
    energy: int
    items: tuple[tuple[int, str, int], ...]
    changes: tuple[tuple[int, str], ...] = ()


def slot_path(slot: int) -> str:
    return f"Items[{{Slot:{slot}b}}]"


SCENARIOS = (
    Scenario("chamber_normal", CHAMBER, 50000, ((0, IRON_ORE, 8),)),
    Scenario("chamber_last_item", CHAMBER, 50000, ((0, IRON_ORE, 1),)),
    Scenario("chamber_low_energy", CHAMBER, 12, ((0, IRON_ORE, 8),),
             ((10, "data modify block {at} energy set value 1000"),)),
    Scenario("chamber_full_output", CHAMBER, 50000, ((0, IRON_ORE, 8), (1, DUST, 63)),
             ((10, "data modify block {at} " + slot_path(1) + ".count set value 1"),)),
    Scenario("chamber_other_output", CHAMBER, 50000, ((0, IRON_ORE, 8), (1, "mekanism:dust_gold", 1))),
    Scenario("chamber_take_input", CHAMBER, 50000, ((0, IRON_ORE, 8),),
             ((50, "data remove block {at} " + slot_path(0)),)),
    Scenario("chamber_swap_input", CHAMBER, 50000, ((0, IRON_ORE, 8),),
             ((50, "data modify block {at} " + slot_path(0) + '.id set value "minecraft:gold_ore"'),)),
    Scenario("chamber_no_recipe", CHAMBER, 50000, ((0, "minecraft:stick", 8),)),
    Scenario("crusher_normal", CRUSHER, 50000, ((0, "minecraft:cobblestone", 3),)),
    Scenario("smelter_normal", SMELTER, 50000, ((0, "minecraft:raw_iron", 3),)),
)


def game_time(world) -> int:
    answer = " ".join(world.command("time query gametime"))
    return int(re.search(r"game time is (\d+)", answer).group(1))


def step(world) -> None:
    before = game_time(world)
    world.command("tick step 1")
    deadline = time.monotonic() + STEP_TIMEOUT_SECONDS
    while game_time(world) != before + 1:
        if time.monotonic() > deadline:
            raise TestFailure(f"a step did not move game time from {before}")


def number(nbt: str, key: str) -> str:
    found = re.search(rf"\b{key}: (-?\d+)", nbt)
    return found.group(1) if found else "0"


def slot(nbt: str, number_of_slot: int) -> str:
    for entry in re.findall(r"\{[^{}]*\}", nbt):
        if re.search(rf"\bSlot: {number_of_slot}b", entry):
            item = re.search(r'id: "([^"]+)"', entry).group(1)
            count = re.search(r"count: (\d+)", entry).group(1)
            return f"{item}x{count}"
    return "-"


def row(tick: int, nbt: str) -> str:
    fields = (
        tick,
        number(nbt, "progress"),
        number(nbt, "active_state"),
        number(nbt, "energy"),
        slot(nbt, INPUT_SLOT),
        slot(nbt, OUTPUT_SLOT),
    )
    return "\t".join(map(str, fields))


def place(world, scenario: Scenario, at: str) -> None:
    items = ",".join(
        f'{{Slot:{number_of_slot}b,id:"{item}",count:{count}}}'
        for number_of_slot, item, count in scenario.items
    )
    answer = world.command(
        f"setblock {at} mekanism:{scenario.block}{{energy:{scenario.energy},Items:[{items}]}}"
    )
    if not any("Changed the block" in line for line in answer):
        raise TestFailure(f"{scenario.name}: setblock answered {answer}")


def replay(world, scenario: Scenario, x: int) -> list[str]:
    at = f"{x} {Y} 0"
    expected = (REFERENCE / f"{scenario.name}.tsv").read_text().splitlines()
    if expected[0] != HEADER:
        raise TestFailure(f"{scenario.name}: unexpected header {expected[0]}")
    place(world, scenario, at)
    changes = dict(scenario.changes)
    failures = []
    for line in expected[1:]:
        tick = int(line.split("\t")[0])
        if tick in changes:
            answer = world.command(changes[tick].replace("{at}", at))
            if not any("Modified" in part or "Removed" in part for part in answer):
                raise TestFailure(f"{scenario.name}: {changes[tick]} answered {answer}")
        step(world)
        got = row(tick, " ".join(world.command(f"data get block {at}")))
        if got != line:
            failures.append(f"{scenario.name} tick {tick}:\n  got      {got}\n  expected {line}")
            break
    print(f"  {scenario.name}: {len(expected) - 1} ticks, {'differs' if failures else 'matches'}")
    return failures


def scenario_run(world) -> None:
    world.start()
    world.command("forceload add 0 -16 64 16")
    world.command("tick freeze")
    begin_checks()
    failures = []
    for index, scenario in enumerate(SCENARIOS):
        failures += replay(world, scenario, index * 2)
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

    return run_test(make, scenario_run)


if __name__ == "__main__":
    sys.exit(main())
