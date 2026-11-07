#!/usr/bin/env python3
"""Replays recordings of upgrades and redstone control from `java_reference_features.py`.

Every field of every row must match, including what the chest beside the machine holds.
"""

import argparse
import re
import sys
from pathlib import Path

import java_reference_features as java
from horizon_driver import DedicatedServer, SinglePlayer, TestFailure, begin_checks, install_content, run_test

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
REFERENCE = HERE / "reference"
Y = 200
NORMAL_TICK_RATE = 20
PREFIXES = ("upgrade_", "redstone_", "eject_", "install_", "energy_slot_")
UPGRADE_SLOT = re.compile(r'items:\[\{container:0b,stored:\{amount:(\d+)L,type:\{id:"mekanism:upgrade",components:\{("[^"]+":"[^"]+")\}\}\}\}\]')
ITEM = re.compile(r'\{container:(\d+)b,stored:\{amount:(\d+)L,type:\{id:"([^"]+)"(?:,components:\{"mekanism:energy":(\d+)L\})?\}\}\}')


def here_format(block: str) -> str:
    """The recording's block data in this port's format: its items and energy are Horizon's, and the
    upgrade slot is the container's slot 3 rather than `component_upgrade.items`."""
    extra = ""
    found = UPGRADE_SLOT.search(block)
    if found:
        extra = f'{{Slot:3b,id:"mekanism:upgrade",count:{found.group(1)},components:{{{found.group(2)}}}}}'
        block = block.replace(found.group(0), "").replace(",}", "}")
    def item(m: re.Match) -> str:
        # Horizon's item energy helpers keep it in `horizon_energy`.
        data = f',components:{{"minecraft:custom_data":{{horizon_energy:{m.group(4)}}}}}' if m.group(4) else ""
        return f'{{Slot:{m.group(1)}b,id:"{m.group(3)}",count:{m.group(2)}{data}}}'

    block = ITEM.sub(item, block)
    block = block.replace("items:[", "Items:[")
    if extra and "Items:[" in block:
        block = re.sub(r"Items:\[([^\]]*)\]", lambda m: f"Items:[{m.group(1)},{extra}]", block, count=1)
    elif extra:
        block = block.replace("{", f"{{Items:[{extra}],", 1)
    return re.sub(r"energy_container:\{stored:(\d+)L\}", r"energy:\1", block)


def here_command(line: str) -> str:
    return line.replace(f" {java.Y} ", f" {Y} ")


def item_entries(nbt: str) -> list[str]:
    """The compounds directly inside `Items`, each of which may nest its components."""
    start = nbt.find("Items: [")
    if start < 0:
        return []
    entries, depth, begin = [], 0, 0
    for at in range(start + len("Items: ["), len(nbt)):
        if nbt[at] == "{":
            begin = at if depth == 0 else begin
            depth += 1
        elif nbt[at] == "}":
            depth -= 1
            if depth == 0:
                entries.append(nbt[begin : at + 1])
        elif nbt[at] == "]" and depth == 0:
            break
    return entries


def slot_of(nbt: str, slot: int) -> str:
    for entry in item_entries(nbt):
        if f"Slot: {slot}b" in entry:
            count = re.search(r"count: (\d+)", entry)
            return f'{re.search(r'\bid: "([^"]+)"', entry).group(1)}x{count.group(1)}'
    return "-"


def upgrade_columns(nbt: str) -> list[str]:
    installed = lambda name: (re.search(rf'"mekanism:{name}": (\d+)', nbt) or [None, "0"])[1]
    held = slot_of(nbt, 3)
    return [installed("speed"), installed("energy"), held.split("x")[-1] if held != "-" else "0"]


def energy_slot_columns(nbt: str) -> list[str]:
    held = re.search(r"horizon_energy: (\d+)", nbt)
    return [slot_of(nbt, 2), held.group(1) if held else "0"]


def row(world, tick: str, has_chest: bool, has_upgrades: bool = False, has_energy_slot: bool = False) -> list[str]:
    nbt = " ".join(world.command(f"data get block 0 {Y} 0"))
    get = lambda pattern: (re.search(pattern, nbt) or [None, "0"])[1]
    tank = re.search(r"chemical_tanks: \[\{container: 0b, stored: \{amount: (\d+)L", nbt)
    return [
        tick,
        get(r"progress: (\d+)"),
        get(r"active_state: (\d+)"),
        get(r"\benergy: (\d+)"),
        slot_of(nbt, 0),
        slot_of(nbt, 1),
        tank.group(1) if tank else "0",
        java.chest_items(" ".join(world.command(f"data get block 1 {Y} 0"))) if has_chest else "-",
        *(upgrade_columns(nbt) if has_upgrades else []),
        *(energy_slot_columns(nbt) if has_energy_slot else []),
    ]


def step(world) -> None:
    before = world.command("time query gametime")
    world.command("tick step 1")
    while world.command("time query gametime") == before:
        pass


def replay(world, scenario: java.Scenario) -> list[str]:
    world.command(f"tick rate {NORMAL_TICK_RATE}")
    world.command("tick unfreeze")
    world.command(f"fill 0 {Y} 0 2 {Y} 1 air")
    world.command("tick freeze")
    world.command(f"tick rate {world.FAST_TICK_RATE}")
    for x, block in enumerate(scenario.blocks):
        answer = " ".join(world.command(f"setblock {x} {Y} 0 {here_format(block)}"))
        if "Changed" not in answer and "air" not in block:
            raise TestFailure(f"{scenario.name}: setblock answered {answer}")
    for x, z, block in scenario.extra:
        world.command(f"setblock {x} {Y} {z} {here_format(block)}")
    expected = (REFERENCE / f"{scenario.name}.tsv").read_text().splitlines()
    changes = dict(scenario.changes)
    failures = []
    has_chest = any("chest" in block for block in scenario.blocks)
    has_upgrades = scenario.name.startswith("install_")
    for line in expected[2:]:
        wanted = line.split("\t")
        tick = int(wanted[0])
        if tick in changes:
            world.command(here_command(changes[tick]))
        step(world)
        got = row(world, wanted[0], has_chest, has_upgrades, scenario.name.startswith("energy_slot_"))
        if got != wanted:
            failures.append(f"{scenario.name} tick {tick}: got {got} expected {wanted}")
            break
    print(f"  {scenario.name}: {len(expected) - 2} rows, {'differs' if failures else 'matches'}", flush=True)
    return failures


def run(world) -> None:
    world.start()
    world.command("forceload add 0 0")
    begin_checks()
    failures = []
    for scenario in java.SCENARIOS:
        if scenario.name.startswith(PREFIXES):
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
