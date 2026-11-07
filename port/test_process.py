#!/usr/bin/env python3
"""Replays the recordings from `java_reference_process.py` in single player and on a dedicated server.

Every field of every row must match. The real mod's two random sources are private and unseeded, so
a recording's rows give the rolls it made and a block's `test_rolls` plays them back here, one a tick.
`*_rate.tsv` then checks the draws themselves, of the recording and of this port running freely,
against bounds worked out from `StatUtils.inversePoisson` and a recipe's chance.

The port's slots are input 0, output 1, energy 2, then two for upgrades, then the extra slot 5.
"""

import argparse
import math
import os
import re
import sys
import time
from pathlib import Path

import java_reference_process as java
import test_features
from horizon_driver import DedicatedServer, SinglePlayer, TestFailure, begin_checks, install_content, run_test

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
REFERENCE = HERE / "reference"
Y = 200
NORMAL_TICK_RATE = 20
PORT_SLOTS = {"input": 0, "output": 1, "energy": 2, "extra": 5}
# A recipe's chemical amount, where it isn't 1.
AMOUNTS = {"purification_block": 2}
# `chemical_conversion`'s amounts for the items these scenarios convert.
CONVERTS = {"minecraft:flint": 10, "mekanism:salt": 2}
# A bound of this many standard deviations leaves one false failure in about 16,000 checks.
SIGMAS = 4
# `sawing/pressure_plate/oak`.
SAW_CHANCE = 0.25
SAW_COUNT = 2
SAW_OPERATIONS = 64


def here_block(s: java.Scenario, rolls: list[int] | None) -> str:
    to_port = {str(java_index): str(PORT_SLOTS[name]) for name, java_index in s.machine.slots.items()}
    block = re.sub(
        r"\{container:(\d)b(,stored:\{amount:\d+L,type:\{id)",
        lambda m: f"{{container:{to_port[m.group(1)]}b{m.group(2)}",
        java.block_of(s),
    )
    # A real save lists its slots in order, and this port's loader expects that.
    entry = r'\{container:\db,stored:\{amount:\d+L,type:\{id:"[^"]+"\}\}\}'
    held = re.search(rf"items:\[({entry}(?:,{entry})*)\]", block)
    if held:
        ordered = sorted(re.findall(entry, held.group(1)), key=lambda e: int(e[len("{container:")]))
        block = block.replace(held.group(1), ",".join(ordered))
    block = test_features.here_format(block)
    if rolls is not None:
        block = f"{block[:-1]},test_rolls:[I;{','.join(map(str, rolls))}]}}"
    return block


def count_of(cell: str) -> int:
    return int(cell.rsplit("x", 1)[1]) if cell != "-" else 0


def rolls_from(s: java.Scenario, rows: list[list[str]]) -> list[int] | None:
    """What the real mod rolled on each tick, from what its rows show."""
    if s.machine is java.SAWMILL:
        return [int(count_of(now[5]) > count_of(before[5])) for before, now in zip(rows, rows[1:])]
    if s.machine not in (java.PURIFIER, java.INJECTOR):
        return None
    rolls = []
    item = s.items.get("extra", ("", 0))[0]
    for before, now in zip(rows, rows[1:]):
        filled = (count_of(before[5]) - count_of(now[5])) * CONVERTS.get(item, 0)
        held = int(before[8]) + filled
        if now[2] == "1":
            rolls.append((held - int(now[8])) // AMOUNTS.get(s.name, 1))
        else:
            # A pause: more than the tank holds was asked for, or something else stopped it.
            rolls.append(held + 1)
    return rolls


def row(world, tick: str) -> list[str]:
    nbt = " ".join(world.command(f"data get block 0 {Y} 0"))
    get = lambda pattern: (re.search(pattern, nbt) or [None, "0"])[1]
    tank = re.search(r'chemical_tanks: \[\{container: 0b, stored: \{amount: (\d+)L, type: "([^"]+)"', nbt)
    return [
        tick,
        get(r"progress: (\d+)"),
        get(r"active_state: (\d+)"),
        get(r"\benergy: (\d+)"),
        test_features.slot_of(nbt, PORT_SLOTS["input"]),
        test_features.slot_of(nbt, PORT_SLOTS["extra"]),
        test_features.slot_of(nbt, PORT_SLOTS["output"]),
        tank.group(2) if tank else "-",
        tank.group(1) if tank else "0",
    ]


def place(world, s: java.Scenario, rolls: list[int] | None) -> None:
    world.command(f"tick rate {NORMAL_TICK_RATE}")
    world.command("tick unfreeze")
    world.command(f"setblock 0 {Y} 0 air")
    world.command("tick freeze")
    world.command(f"tick rate {world.FAST_TICK_RATE}")
    answer = " ".join(world.command(f"setblock 0 {Y} 0 {here_block(s, rolls)}"))
    if "Changed" not in answer:
        raise TestFailure(f"{s.name}: setblock answered {answer}")


def replay(world, s: java.Scenario) -> list[str]:
    lines = (REFERENCE / f"{s.name}.tsv").read_text().splitlines()[1:]
    rows = [line.split("\t") for line in lines]
    place(world, s, rolls_from(s, rows))
    failures = []
    got = row(world, "0")
    if got != rows[0]:
        failures.append(f"{s.name} tick 0: got {got} expected {rows[0]}")
    for wanted in rows[1:]:
        if failures:
            break
        if s.empty and int(wanted[0]) == s.empty[1]:
            world.command(f"item replace block 0 {Y} 0 container.{PORT_SLOTS[s.empty[0]]} with minecraft:air")
        test_features.step(world)
        got = row(world, wanted[0])
        if got != wanted:
            failures.append(f"{s.name} tick {wanted[0]}: got {got} expected {wanted}")
    print(f"  {s.name}: {len(rows) - 1} rows, {'differs' if failures else 'matches'}", flush=True)
    return failures


def poisson_chances(mean: float = 1.0) -> list[float]:
    """The chance of each value of `StatUtils.inversePoisson(mean)`, from its source."""
    top = math.exp(mean)
    cuts, p = [1.0], 1.0
    bound = 3 * math.ceil(mean)
    for m in range(1, bound):
        p += 1 / math.sqrt(2 * math.pi) / math.sqrt(m) * (mean * math.e / m) ** m
        cuts.append(p)
    edges = [min(cut / top, 1.0) for cut in cuts] + [1.0]
    return [high - low for low, high in zip([0.0] + edges, edges)]


def bound_failures(label: str, seen: int, total: int, chance: float) -> list[str]:
    allowed = SIGMAS * math.sqrt(chance * (1 - chance) / total)
    share = seen / total
    if abs(share - chance) > allowed:
        return [f"{label}: {seen} of {total} is {share:.4f}, allowed {chance:.4f} by {allowed:.4f}"]
    return []


def chemical_rate_failures(label: str, rows: list[tuple[int, int, int, int]]) -> list[str]:
    """Rows of round, tick, tank and progress: a tick that ran shows its draw in the tank."""
    chances = poisson_chances()
    counts = [0] * len(chances)
    for before, now in zip(rows, rows[1:]):
        if before[0] == now[0] and before[3] != now[3]:
            draw = before[2] - now[2]
            if draw >= len(counts):
                return [f"{label}: a draw of {draw}, above the source's bound"]
            counts[draw] += 1
    total = sum(counts)
    print(f"  {label}: draws {counts}", flush=True)
    failures = []
    for value, chance in enumerate(chances):
        failures += bound_failures(f"{label} draws of {value}", counts[value], total, chance)
    return failures


def saw_rate_failures(label: str, secondaries: list[int]) -> list[str]:
    hits = sum(secondaries)
    if hits % SAW_COUNT:
        return [f"{label}: {hits} isn't a multiple of a recipe's {SAW_COUNT}"]
    total = len(secondaries) * SAW_OPERATIONS
    print(f"  {label}: {hits // SAW_COUNT} of {total}", flush=True)
    return bound_failures(label, hits // SAW_COUNT, total, SAW_CHANCE)


def recorded_rates() -> list[str]:
    failures = []
    for s in java.RATE_CHEMICAL:
        lines = (REFERENCE / f"{s.name}.tsv").read_text().splitlines()[1:]
        rows = [tuple(int(cell) for cell in line.split("\t")) for line in lines]
        failures += chemical_rate_failures(f"recorded {s.name}", rows)
    lines = (REFERENCE / f"{java.RATE_SAW.name}.tsv").read_text().splitlines()[1:]
    failures += saw_rate_failures("recorded sawmill", [count_of(line.split("\t")[3]) for line in lines])
    return failures


def port_chemical_rate(world, s: java.Scenario) -> list[str]:
    rows = []
    for number in range(java.CHEMICAL_ROUNDS):
        place(world, s, None)
        for tick in range(s.ticks + 1):
            if tick:
                test_features.step(world)
            fields = row(world, str(tick))
            rows.append((number, tick, int(fields[8]), int(fields[1])))
    return chemical_rate_failures(f"this port's {s.name}", rows)


def game_time(world) -> int:
    return int(re.search(r"(\d+)", " ".join(world.command("time query gametime"))).group(1))


def port_saw_rate(world) -> list[str]:
    s = java.RATE_SAW
    secondaries = []
    for _ in range(java.SAW_ROUNDS):
        place(world, s, None)
        start = game_time(world)
        world.command(f"tick step {s.ticks}")
        while game_time(world) < start + s.ticks:
            time.sleep(0.05)
        fields = row(world, "end")
        if fields[4] != "-":
            raise TestFailure(f"sawmill rate: input left after the round: {fields}")
        secondaries.append(count_of(fields[5]))
    return saw_rate_failures("this port's sawmill", secondaries)


def run(world) -> None:
    world.start()
    world.command("forceload add 0 0")
    begin_checks()
    failures = recorded_rates()
    # While working: PROCESS_ONLY names scenarios by prefix, and `rates` adds the port's own draws.
    only = os.environ.get("PROCESS_ONLY", "").split(",") if os.environ.get("PROCESS_ONLY") else None
    for s in java.SCENARIOS:
        if only is None or any(s.name.startswith(prefix) for prefix in only):
            failures += replay(world, s)
    if only is None or "rates" in only:
        failures += port_saw_rate(world)
        for s in java.RATE_CHEMICAL:
            failures += port_chemical_rate(world, s)
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
