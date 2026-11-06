#!/usr/bin/env python3
"""Phase 2 test: a furnace on the mod hooks against vanilla's, tick by tick, in one world.

Build the game with mekmachine in it (port/README.md), then:

    python3 port/test_phase2.py --engine port/.work/machine-export/horizon-engine

Each scenario stands a vanilla furnace beside a mod one and changes both in the same tick with a
datapack function. The mod's tick writes both furnaces' slots, numbers and `lit` to a trace, and
every row must match, before and after a reload. Each scenario also has an outcome to reach, so a
pair that did nothing can't pass.

A row holds the vanilla furnace as the mod's tick finds it. When a reload puts the vanilla furnace
later in the tick order, that is its state from the tick before, so each load may match with one
fixed shift of one tick, and the first load, where vanilla was placed first, must match without.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, NamedTuple

NIGHTLY = (
    Path.home() / "Library/Application Support/horizon-launcher/versions/nightly-2026-11-05-f319701"
)
WORK = Path(__file__).resolve().parent / ".work"
CTL = NIGHTLY / "horizon-ctl"
RESOURCES = NIGHTLY / ".local/horizon-client/26.3"
PACK_FORMAT = 121
TIMEOUT_SECONDS = 120
Y = 200
SPACING = 4
INPUT, FUEL, OUTPUT = 0, 1, 2
# Long enough for 2 recipes of 200 ticks and for planks' 300-tick burn to run out and cool down.
RUN_TICKS_BEFORE_RELOAD = 500
RUN_TICKS_AFTER_RELOAD = 100
TICKS_PER_SECOND = 20
LATER_CHANGE_SECONDS = 2.5
MENU_SETTLE_SECONDS = 0.5
FIRST_CONTAINER_SLOT = 300
ARMOR_SLOT = 500
OUTPUT_MENU_SLOT = 302


class TestFailure(Exception):
    pass


class Row(NamedTuple):
    input: str
    fuel: str
    output: str
    lit_remaining: int
    lit_total: int
    cook_time: int
    cook_total: int
    lit: str


def parse_row(text: str) -> Row:
    fields = text.split()
    return Row(fields[0], fields[1], fields[2], *map(int, fields[3:7]), fields[7])


class Scenario(NamedTuple):
    name: str
    start: tuple[tuple[int, str], ...]
    later: tuple[tuple[int, str], ...]
    outcome: Callable[[list[Row]], bool]
    hoppers: bool = False


def made(rows: list[Row], count: int) -> bool:
    """At least `count` ingots: how long a run lasts depends on how fast the reload is."""
    item, _, made_count = rows[-1].output.partition("x")
    return item == "minecraft:iron_ingot" and int(made_count) >= count


SCENARIOS = (
    Scenario(
        "coal", ((INPUT, "raw_iron 9"), (FUEL, "coal 2")), (),
        lambda rows: made(rows, 2) and rows[-1].lit == "true",
    ),
    Scenario(
        "lava", ((INPUT, "raw_iron 3"), (FUEL, "lava_bucket 1")), (),
        lambda rows: rows[-1].fuel == "minecraft:bucketx1" and made(rows, 2),
    ),
    Scenario(
        "fuel_runs_out", ((INPUT, "raw_iron 9"), (FUEL, "oak_planks 1")), (),
        lambda rows: made(rows, 1) and rows[-1].lit == "false" and rows[-1].cook_time == 0,
    ),
    Scenario(
        "full_output", ((INPUT, "raw_iron 2"), (FUEL, "coal 1"), (OUTPUT, "iron_ingot 64")),
        ((OUTPUT, "air"),),
        lambda rows: rows[0].fuel == "minecraft:coalx1" and rows[-1].lit == "true",
    ),
    Scenario(
        "no_recipe", ((INPUT, "stick 1"), (FUEL, "coal 1")), (),
        lambda rows: rows[-1].fuel == "minecraft:coalx1" and rows[-1].lit == "false",
    ),
    Scenario(
        "swap_input", ((INPUT, "raw_iron 3"), (FUEL, "coal 1")), ((INPUT, "kelp 3"),),
        lambda rows: rows[-1].output == "minecraft:dried_kelpx3",
    ),
    Scenario(
        "take_input", ((INPUT, "raw_iron 3"), (FUEL, "coal 1")), ((INPUT, "air"),),
        lambda rows: rows[-1].input == "-" and rows[-1].cook_time == 0,
    ),
    Scenario(
        "wet_sponge", ((INPUT, "wet_sponge 1"), (FUEL, "coal 1")), ((FUEL, "bucket 1"),),
        lambda rows: rows[-1].fuel == "minecraft:water_bucketx1"
        and rows[-1].output == "minecraft:spongex1",
    ),
    Scenario(
        "hoppers", ((FUEL, "coal 1"),), (),
        lambda rows: rows[-1].input != "-" and any(r.cook_time > 0 for r in rows),
        hoppers=True,
    ),
)


def mod_x(index: int) -> int:
    return index * SPACING


def start_commands(index: int, scenario: Scenario) -> list[str]:
    x = mod_x(index)
    # Vanilla's first: it ticks first, so the mod's tick reads its state for the same tick.
    lines = [
        f"setblock {x + 1} {Y} 0 minecraft:furnace",
        f"setblock {x} {Y} 0 mekmachine:furnace",
    ]
    if scenario.hoppers:
        for at in (x + 1, x):
            lines.append(
                f"setblock {at} {Y + 1} 0 minecraft:hopper"
                '{Items:[{Slot:0b,id:"minecraft:raw_iron",count:5}]}'
            )
    return [*lines, *slot_commands(x, scenario.start)]


def slot_commands(x: int, changes: tuple[tuple[int, str], ...]) -> list[str]:
    return [
        f"item replace block {at} {Y} 0 container.{slot} with minecraft:{item}"
        for at in (x + 1, x)
        for slot, item in changes
    ]


def write_pack(world_dir: Path) -> None:
    pack = world_dir / "datapacks/mekmachine"
    functions = pack / "data/mekmachine/function"
    functions.mkdir(parents=True)
    mcmeta = {"pack": {"description": "", "min_format": PACK_FORMAT, "max_format": PACK_FORMAT}}
    (pack / "pack.mcmeta").write_text(json.dumps(mcmeta))
    for index, scenario in enumerate(SCENARIOS):
        (functions / f"start_{scenario.name}.mcfunction").write_text(
            "\n".join(start_commands(index, scenario)) + "\n"
        )
        (functions / f"later_{scenario.name}.mcfunction").write_text(
            "\n".join(slot_commands(mod_x(index), scenario.later)) + "\n"
        )


class World:
    def __init__(self, folder: Path, engine: Path, resources: Path) -> None:
        self.socket = folder / "c.sock"
        self.game_dir = folder / "game"
        self.game_dir.mkdir()
        (folder / "home").mkdir()
        self.trace = folder / "trace.txt"
        self.engine = engine
        self.resources = resources
        self.env = {
            **os.environ,
            "HORIZON_HOME": str(folder / "home"),
            "HORIZON_LAUNCHER_HOME": str(folder / "launcher"),
            "XDG_DATA_HOME": str(folder / "data"),
            "XDG_CONFIG_HOME": str(folder / "config"),
            "HORIZON_NO_AUDIO": "1",
            "HORIZON_LAUNCHER_NO_SELF_UPDATE": "1",
            "MEKMACHINE_TRACE": str(self.trace),
        }

    def ctl(self, *args: object) -> dict:
        done = subprocess.run(
            [str(CTL), "--socket", str(self.socket), *map(str, args)],
            env=self.env,
            cwd=self.game_dir,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        reply = json.loads(done.stdout or "{}")
        if done.returncode != 0 or "error" in reply:
            raise TestFailure(f"horizon-ctl {args}: {done.stdout}{done.stderr}")
        return reply

    def start(self) -> None:
        self.ctl(
            "launch", "--world", "W", "--seed", "2024", "--creative", "--offscreen", "--wait",
            "--game", self.engine, "--resources", self.resources, "--game-dir", self.game_dir,
        )

    def stop(self) -> None:
        self.ctl("quit")
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while self.socket.exists() and time.monotonic() < deadline:
            time.sleep(0.2)

    def command(self, line: str) -> list[str]:
        return self.ctl("command", line).get("chat", [])

    def function(self, name: str) -> None:
        answer = self.command(f"function mekmachine:{name}")
        if not any("Executed" in line or "Running" in line for line in answer):
            raise TestFailure(f"function {name} answered {answer}")


TraceRow = tuple[int, Row, Row]
RELOAD_MARK = "RELOAD"


def read_trace(path: Path) -> dict[str, list[list[TraceRow]]]:
    """Each furnace's rows, one list per load of the world."""
    loads = path.read_text().split(f"{RELOAD_MARK}\n")
    rows: dict[str, list[list[TraceRow]]] = {}
    for number, load in enumerate(loads):
        for line in load.splitlines():
            game_time, pos, modded, vanilla = line.split("|")
            series = rows.setdefault(pos, [[] for _ in loads])
            series[number].append((int(game_time), parse_row(modded), parse_row(vanilla)))
    return rows


def differences(load: list[TraceRow], shift: int) -> list[TraceRow]:
    """Rows where the mod's state isn't vanilla's, `shift` rows later in the trace."""
    pairs = zip(load, load[shift:])
    return [(row[0], row[1], later[2]) for row, later in pairs if row[1] != later[2]]


def compare_load(number: int, load: list[TraceRow]) -> tuple[int, list[TraceRow]]:
    """The shift that fits this load best, and what still differs with it."""
    shifts = (0,) if number == 0 else (0, 1)
    return min(((shift, differences(load, shift)) for shift in shifts), key=lambda s: len(s[1]))


def compare(trace: Path) -> None:
    rows = read_trace(trace)
    failures = []
    for index, scenario in enumerate(SCENARIOS):
        loads = rows.get(f"{mod_x(index)},{Y},0", [])
        if not all(loads) or not loads:
            failures.append(f"{scenario.name}: a load has no trace rows")
            continue
        results = [compare_load(number, load) for number, load in enumerate(loads)]
        different = [row for _, found in results for row in found]
        vanilla = [v for load in loads for _, _, v in load]
        outcome = scenario.outcome(vanilla)
        print(
            f"  {scenario.name}: {len(vanilla)} ticks, {len(different)} differ, "
            f"shifts {[shift for shift, _ in results]}, outcome {outcome}"
        )
        if different:
            t, m, v = different[0]
            failures.append(f"{scenario.name}: first difference at {t}:\n  mod {m}\n  van {v}")
        if not outcome:
            failures.append(f"{scenario.name}: outcome not reached, ended at {vanilla[-1]}")
    if failures:
        raise TestFailure("\n".join(failures))


def menu_slots(screen: dict) -> list[dict]:
    return [slot for slot in screen["slots"] if FIRST_CONTAINER_SLOT <= slot["slot"] < ARMOR_SLOT]


def open_menu(world: World, x: int) -> dict:
    world.ctl("interact", x, Y, 0)
    time.sleep(MENU_SETTLE_SECONDS)
    return world.ctl("screen")


def check_menu(world: World) -> None:
    # The pair with no recipe: its slots stay as they are between the two reads.
    x = mod_x(next(i for i, scenario in enumerate(SCENARIOS) if scenario.name == "no_recipe"))
    world.command(f"setblock {x} {Y - 1} -1 minecraft:stone")
    world.command(f"tp @s {x} {Y} -1")
    time.sleep(MENU_SETTLE_SECONDS)
    vanilla = open_menu(world, x + 1)
    world.ctl("close")
    time.sleep(MENU_SETTLE_SECONDS)
    modded = open_menu(world, x)
    world.ctl("close")
    print(f"  screen {modded['screen']}, slots {menu_slots(modded)}")
    if modded["screen"] != vanilla["screen"] or menu_slots(modded) != menu_slots(vanilla):
        raise TestFailure(f"the menus differ:\n  mod {modded}\n  van {vanilla}")


def check_take_output(world: World) -> None:
    x = mod_x(len(SCENARIOS))
    world.command(f"setblock {x} {Y} 0 mekmachine:furnace")
    world.command(f"item replace block {x} {Y} 0 container.2 with minecraft:iron_ingot 5")
    world.command(f"setblock {x} {Y - 1} -1 minecraft:stone")
    world.command(f"tp @s {x} {Y} -1")
    world.command("clear @s")
    time.sleep(MENU_SETTLE_SECONDS)
    open_menu(world, x)
    world.ctl("click-slot", OUTPUT_MENU_SLOT, "shift")
    time.sleep(MENU_SETTLE_SECONDS)
    after = world.ctl("screen")
    world.ctl("close")
    time.sleep(MENU_SETTLE_SECONDS)
    counts = world.ctl("inventory").get("counts", {})
    print(f"  shift-click took {counts} and left {menu_slots(after)}")
    if counts.get("minecraft:iron_ingot") != 5 or any(s["item"] for s in menu_slots(after)):
        raise TestFailure(f"taking the output: inventory {counts}, menu {menu_slots(after)}")


def scenario_run(world: World) -> None:
    world.start()
    write_pack(world.game_dir / "saves/W")
    world.command("reload")
    world.command(f"forceload add 0 -16 {SPACING * (len(SCENARIOS) + 1)} 16")
    for scenario in SCENARIOS:
        world.function(f"start_{scenario.name}")
    time.sleep(LATER_CHANGE_SECONDS)
    for scenario in SCENARIOS:
        if scenario.later:
            world.function(f"later_{scenario.name}")
    time.sleep(RUN_TICKS_BEFORE_RELOAD / TICKS_PER_SECOND)
    print("Menu:")
    check_menu(world)
    check_take_output(world)
    world.stop()
    with world.trace.open("a") as trace:
        trace.write(f"{RELOAD_MARK}\n")
    world.start()
    time.sleep(RUN_TICKS_AFTER_RELOAD / TICKS_PER_SECOND)
    world.stop()
    print("Trace:")
    compare(world.trace)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--resources", type=Path, default=RESOURCES)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(dir=WORK))
    world = World(folder, args.engine.resolve(), args.resources.resolve())
    try:
        scenario_run(world)
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
