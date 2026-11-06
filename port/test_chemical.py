#!/usr/bin/env python3
"""Replays the real mod's chemical recordings: the Chemical Oxidizer, the basic Pressurized Tube and
the basic Chemical Tank, in the format the real mod saves.

    python3 port/test_chemical.py --engine port/.work/machine-export/horizon-engine [--dedicated --eula]

A row holds one tick. The real mod's order of a network's tubes comes from a hash, so which tube gets
a remainder isn't compared: tube shares are compared sorted, and PLAN.md lists that difference.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from horizon_driver import DedicatedServer, SinglePlayer, TestFailure, install_content

sys.dont_write_bytecode = True
import java_reference_chemical as java  # noqa: E402
from test_phase3 import step  # noqa: E402

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
REFERENCE = HERE / "reference"
FIELD_COUNT = len(java.FIELDS)
CHEM_FIELD = java.FIELDS.index("chem")
TANKS = r'chemical_tanks: \[\{container: 0b, stored: \{amount: (\d+)L, type: "([^"]+)"\}\}\]'
TUBE_STORED = r'\bstored: \{amount: (\d+)L, type: "([^"]+)"\}'


def to_horizon(text: str) -> str:
    """Horizon's containers save `Items` and `energy`, so a recording's setup needs those names."""
    text = re.sub(r"energy_container:\{stored:(\d+)L\}", r"energy:\1", text)
    text = re.sub(
        r'items:\[\{container:0b,stored:\{amount:(\d+)L,type:\{id:"([^"]+)"\}\}\}\]',
        r'Items:[{Slot:0b,id:"\2",count:\1}]',
        text,
    )
    return re.sub(r"energy_container\.stored set value (\d+)L", r"energy set value \1", text)


def chem_cell(nbt: str) -> str:
    found = re.search(TUBE_STORED if java.TUBE in nbt else TANKS, nbt)
    return f"{found.group(2)}x{found.group(1)}" if found else "-"


def cells(nbt: str) -> list[str]:
    item = re.search(r'Items: \[\{[^{}]*\bSlot: 0b[^{}]*\}', nbt)
    held = "-"
    if item:
        held = f'{re.search(r"id: .([^,}]+).", item.group(0)).group(1).rstrip(chr(34))}x'
        held += re.search(r"count: (\d+)", item.group(0)).group(1)
    used = re.search(r'recipes_used: \{"?[^:]+:[^:]+"?: (\d+)\}', nbt)
    return [
        java.get(nbt, r"\bprogress: (\d+)"),
        java.get(nbt, r"\bactive_state: (\d)"),
        java.get(nbt, r"\benergy: (\d+)"),
        held,
        chem_cell(nbt),
        used.group(1) if used else "0",
    ]


def read_row(world, tick: int, count: int) -> str:
    row = [str(tick)]
    for x in range(count):
        row += cells(" ".join(world.command(f"data get block {x} {java.Y} 0")))
    return "\t".join(row)


def normalised(row: str, tubes: list[int]) -> list[str]:
    """Sorts the tubes' saved shares within a row."""
    parts = row.split("\t")
    at = [1 + x * FIELD_COUNT + CHEM_FIELD for x in tubes]
    for index, share in zip(at, sorted(parts[index] for index in at)):
        parts[index] = share
    return parts


def place(world, scenario) -> None:
    world.command("tick unfreeze")
    for x in range(8):
        world.command(f"setblock {x} {java.Y} 0 air")
    world.command(f"setblock 1 {java.Y + 1} 0 air")
    world.command("tick freeze")
    for x, block in enumerate(scenario.blocks):
        answer = " ".join(world.command(f"setblock {x} {java.Y} 0 {to_horizon(block)}"))
        if "Changed" not in answer:
            raise TestFailure(f"{scenario.name}: setblock answered {answer}")


def replay(world, scenario) -> None:
    lines = (REFERENCE / f"{scenario.name}.tsv").read_text().splitlines()
    place(world, scenario)
    count = len(scenario.blocks)
    tubes = [x for x, block in enumerate(scenario.blocks) if block.startswith(java.TUBE)]
    changes = dict(scenario.changes)
    expected = iter(lines[1:])
    for tick in range(1, scenario.ticks + 1):
        if tick in changes:
            answer = " ".join(world.command(to_horizon(changes[tick])))
            if "Modified" not in answer and "Changed" not in answer:
                raise TestFailure(f"{scenario.name}: {changes[tick]} answered {answer}")
        step(world)
        check(scenario, tick, read_row(world, tick, count), next(expected), tubes)
        if tick == scenario.restart_after:
            world.command("tick unfreeze")
            world.stop()
            world.start()
            world.command(f"forceload add 0 0")
            world.command("tick freeze")
            check(scenario, -1, read_row(world, -1, count), next(expected), tubes)
    print(f"  {scenario.name}: {len(lines) - 1} rows, matches")


def check(scenario, tick: int, got: str, expected: str, tubes: list[int]) -> None:
    if normalised(got, tubes) != normalised(expected, tubes):
        raise TestFailure(f"{scenario.name} tick {tick}:\n  got      {got}\n  expected {expected}")


def run(world) -> None:
    world.start()
    world.command("forceload add 0 0")
    for scenario in java.SCENARIOS:
        replay(world, scenario)
    world.command("tick unfreeze")
    world.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--dedicated", action="store_true")
    parser.add_argument("--eula", action="store_true", help="you agree to the Minecraft EULA")
    args = parser.parse_args()
    if args.dedicated and not args.eula:
        parser.error("--dedicated writes eula=true: pass --eula if you agree to the Minecraft EULA")
    folder = Path(tempfile.mkdtemp(dir=WORK))
    world = (DedicatedServer if args.dedicated else SinglePlayer)(folder, args.engine.resolve(), {})
    install_content(world.content_dir, WORK / "check/carry", WORK / "check-generators/carry")
    try:
        run(world)
    except (TestFailure, subprocess.TimeoutExpired) as failure:
        try:
            world.stop()
        except (TestFailure, subprocess.TimeoutExpired):
            pass
        print(f"FAIL: {failure}\nFiles kept in {folder}", file=sys.stderr)
        return 1
    shutil.rmtree(folder)
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
