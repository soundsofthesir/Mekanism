#!/usr/bin/env python3
"""Phase 2 test: energy and fluids moving between mod blocks, in a real world.

    python3 port/test_transfer.py --engine port/.work/machine-export/horizon-engine
    python3 port/test_transfer.py --engine port/.work/machine-export/horizon-engine --dedicated --eula

Each line of blocks runs west to east until its stores are full. The trace gives every block's
amount each tick: the rate must be exact until then, the final amounts must be the capacities, and
a reload must find exactly those amounts again.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

from horizon_driver import (
    DedicatedServer,
    SinglePlayer,
    TestFailure,
    run_function,
    write_functions,
)

WORK = Path(__file__).resolve().parent / ".work"
TRACE = "MEKMACHINE_TRANSFER_TRACE"
Y = 200
LINE_SPACING = 2
RUN_SECONDS = 6
AFTER_RELOAD_SECONDS = 3
RELOAD_MARK = "RELOAD"

# The rates and capacities the blocks declare in port/machine.
GENERATED = 40
GENERATOR_CAPACITY = 1000
CELL_INSERT = 30
CELL_CAPACITY = 500
CABLE_RATE = 25
SOURCE_PUSH = 100
PIPE_RATE = 50
TANK_CAPACITY = 1000
WATER = "minecraft:water"
LAVA = "minecraft:lava"


class Line(NamedTuple):
    name: str
    blocks: tuple[str, ...]


LINES = (
    Line("generator_to_cell", ("energy_gen", "energy_cell")),
    Line("wrong_face", ("energy_gen", "energy_cell_east")),
    Line("through_cable", ("energy_gen", "energy_cable", "energy_cell")),
    Line("source_to_tank", ("water_source", "tank")),
    Line("through_pipe", ("water_source", "fluid_pipe", "tank")),
    Line("two_fluids", ("water_source", "tank", "lava_source")),
)


class Sample(NamedTuple):
    time: int
    energy: int
    fluid: str
    amount: int


def line_z(index: int) -> int:
    return index * LINE_SPACING


def place_commands() -> list[str]:
    # West to east, so each block ticks before the one it feeds.
    return [
        f"setblock {x} {Y} {line_z(index)} mekmachine:{block}"
        for index, line in enumerate(LINES)
        for x, block in enumerate(line.blocks)
    ]


def read_trace(path: Path) -> list[dict[tuple[int, int], list[Sample]]]:
    """For each load of the world, each block's samples, by its (line, x)."""
    loads = []
    for text in path.read_text().split(f"{RELOAD_MARK}\n"):
        load = defaultdict(list)
        for row in text.splitlines():
            game_time, pos, _name, energy, fluid, amount = row.split("|")
            x, _, z = map(int, pos.split(","))
            sample = Sample(int(game_time), int(energy), fluid, int(amount))
            load[(z // LINE_SPACING, x)].append(sample)
        loads.append(load)
    return loads


def expect(failures: list[str], label: str, got: object, wanted: object) -> None:
    if got != wanted:
        failures.append(f"{label}: got {got}, expected {wanted}")


def rises_at(values: list[int], rate: int, cap: int) -> bool:
    """Each tick adds exactly `rate` until the last step to the cap, then nothing."""
    steps = zip(values, values[1:])
    return all(after == min(before + rate, cap) for before, after in steps)


def check_first_load(load: dict, failures: list[str]) -> None:
    def energies(line: int, x: int) -> list[int]:
        return [s.energy for s in load[(line, x)]]

    def amounts(line: int, x: int) -> list[int]:
        return [s.amount for s in load[(line, x)]]

    expect(failures, "cell rate", rises_at(energies(0, 1), CELL_INSERT, CELL_CAPACITY), True)
    expect(failures, "cell filled", energies(0, 1)[-1], CELL_CAPACITY)
    expect(failures, "generator filled", energies(0, 0)[-1], GENERATOR_CAPACITY)
    totals = [
        gen.energy + cell.energy
        for gen, cell in zip(load[(0, 0)], load[(0, 1)])
        if gen.energy < GENERATOR_CAPACITY
    ]
    expect(failures, "energy kept", totals, [GENERATED * (i + 1) for i in range(len(totals))])

    expect(failures, "wrong face took nothing", set(energies(1, 1)), {0})
    expect(failures, "wrong face generator filled", energies(1, 0)[-1], GENERATOR_CAPACITY)

    expect(failures, "cable rate", rises_at(energies(2, 2), CABLE_RATE, CELL_CAPACITY), True)
    expect(failures, "cable cell filled", energies(2, 2)[-1], CELL_CAPACITY)

    expect(failures, "tank rate", rises_at(amounts(3, 1), SOURCE_PUSH, TANK_CAPACITY), True)
    expect(failures, "tank filled", amounts(3, 1)[-1], TANK_CAPACITY)
    expect(failures, "tank fluid", load[(3, 1)][-1].fluid, WATER)

    expect(failures, "pipe rate", rises_at(amounts(4, 2), PIPE_RATE, TANK_CAPACITY), True)
    expect(failures, "pipe tank filled", amounts(4, 2)[-1], TANK_CAPACITY)

    expect(failures, "mixed tank's fluids", {s.fluid for s in load[(5, 1)]}, {WATER})
    expect(failures, "lava stayed", (load[(5, 2)][-1].fluid, load[(5, 2)][-1].amount),
           (LAVA, TANK_CAPACITY))


def check_reload(first: dict, second: dict, failures: list[str]) -> None:
    """Every store was full before the stop, so each must hold the same right after it."""
    for key, samples in first.items():
        before, after = samples[-1], second[key][0]
        expect(failures, f"block {key} energy after reload", after.energy, before.energy)
        expect(failures, f"block {key} fluid after reload", (after.fluid, after.amount),
               (before.fluid, before.amount))


def scenario_run(world, trace: Path) -> None:
    world.start()
    write_functions(world.world_dir, {"place": place_commands()})
    world.command("reload")
    world.command(f"forceload add 0 0 16 {LINE_SPACING * len(LINES)}")
    run_function(world, "place")
    time.sleep(RUN_SECONDS)
    world.stop()
    with trace.open("a") as file:
        file.write(f"{RELOAD_MARK}\n")
    world.start()
    time.sleep(AFTER_RELOAD_SECONDS)
    world.stop()
    first, second = read_trace(trace)
    failures: list[str] = []
    check_first_load(first, failures)
    check_reload(first, second, failures)
    print(f"{len(first)} blocks, {sum(map(len, first.values()))} samples before the reload")
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
    folder = Path(tempfile.mkdtemp(dir=WORK))
    trace = folder / "trace.txt"
    kind = DedicatedServer if args.dedicated else SinglePlayer
    world = kind(folder, args.engine.resolve(), {TRACE: trace})
    try:
        scenario_run(world, trace)
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
