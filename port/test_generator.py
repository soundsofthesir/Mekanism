#!/usr/bin/env python3
"""Phase 3 test: the Heat Generator's fuel slot and menu in Horizon against the real mod.

    python3 port/test_generator.py --engine port/.work/machine-export/horizon-engine
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from horizon_driver import SinglePlayer, TestFailure, install_content

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
REFERENCE = HERE / "reference"
Y = 100
GENERATOR = "mekanismgenerators:heat_generator"
STEP_TIMEOUT_SECONDS = 30
CHUNK_SETTLE_SECONDS = 5
SETTLE_SECONDS = 0.5
HEAT_TOLERANCE = 0.000001
FUEL_MENU_SLOT = 300
HOTBAR_SLOT = 0
SCENARIOS = (
    ("generator_fuel_coal", 0, "minecraft:coal", 64),
    ("generator_fuel_bucket", 0, "minecraft:lava_bucket", 1),
    ("generator_fuel_bucket_no_room", 500, "minecraft:lava_bucket", 1),
    ("generator_fuel_blaze_rod", 0, "minecraft:blaze_rod", 2),
    ("generator_fuel_not_fuel", 0, "minecraft:stone", 3),
)


def text(world, line: str) -> str:
    return " ".join(world.command(line))


def game_time(world) -> int:
    return int(re.search(r"game time is (\d+)", text(world, "time query gametime")).group(1))


def step(world) -> None:
    before = game_time(world)
    world.command("tick step 1")
    deadline = time.monotonic() + STEP_TIMEOUT_SECONDS
    while game_time(world) != before + 1:
        if time.monotonic() > deadline:
            raise TestFailure(f"a step did not move game time from {before}")


def get(nbt: str, pattern: str, default: str = "0") -> str:
    found = re.search(pattern, nbt)
    return found.group(1) if found else default


def fuel(nbt: str) -> str:
    for entry in re.findall(r"\{[^{}]*\}", nbt):
        if re.search(r"\bSlot: 0b", entry):
            item = re.search(r'id: "([^"]+)"', entry).group(1)
            return f"{item}x{re.search(r'count: (\d+)', entry).group(1)}"
    return "-"


def replay(world, name: str, lava: int, item: str, count: int) -> list[str]:
    # The position the recordings used: temperature varies from one block to the next.
    at = f"0 {Y} 0"
    fluids = f'fluids:[{{Fluid:"minecraft:lava",Amount:{lava}}}],' if lava else ""
    world.command("tick unfreeze")
    world.command(f"setblock {at} air")
    world.command("tick freeze")
    answer = text(world, f'setblock {at} {GENERATOR}{{{fluids}Items:[{{Slot:0b,id:"{item}",count:{count}}}]}}')
    if "Changed" not in answer:
        raise TestFailure(f"{name}: {answer}")
    expected = (REFERENCE / f"{name}.tsv").read_text().splitlines()
    failures = []
    for line in expected[1:]:
        wanted = line.split("\t")
        step(world)
        nbt = text(world, f"data get block {at}")
        heat = float(get(nbt, r"heat: ([\d.E-]+)d"))
        got = [
            get(nbt, r"\benergy: (\d+)"),
            get(nbt, r"Amount: (\d+)"),
            get(nbt, r"active_state: (\d)"),
            fuel(nbt),
        ]
        if got != wanted[2:] or abs(heat - float(wanted[1])) > HEAT_TOLERANCE:
            failures.append(f"{name} tick {wanted[0]}: got {heat} {got}, expected {wanted[1:]}")
            break
    print(f"  {name}: {len(expected) - 1} rows, {'differs' if failures else 'matches'}", flush=True)
    return failures


def check_menu(world, screenshot: Path | None) -> None:
    x, z = 40, 0
    world.command("tick unfreeze")
    world.command(f"setblock {x} {Y} {z} {GENERATOR}")
    world.command(f"setblock {x} {Y - 1} {z - 1} minecraft:stone")
    world.command(f"tp @s {x} {Y} {z - 1}")
    world.command("clear @s")
    world.command("give @s minecraft:lava_bucket 1")
    time.sleep(SETTLE_SECONDS)
    world.ctl("interact", x, Y, z)
    time.sleep(SETTLE_SECONDS)
    screen = world.ctl("screen")
    if screen.get("screen") != "container":
        raise TestFailure(f"the generator's menu did not open: {screen.get('screen')}")
    world.ctl("click-slot", HOTBAR_SLOT, "shift")
    time.sleep(SETTLE_SECONDS * 4)
    nbt = text(world, f"data get block {x} {Y} {z}")
    energy = int(get(nbt, r"\benergy: (\d+)"))
    bucket = fuel(nbt)
    print(f"  through the menu: energy {energy}, slot {bucket}")
    # A bucket burns in 10 ticks, so what shows it went in is the energy made and the bucket left.
    if energy <= 0 or bucket != "minecraft:bucketx1":
        raise TestFailure(f"a lava bucket in the menu: energy {energy}, slot {bucket}")
    if screenshot:
        world.ctl("screenshot", screenshot)
    world.ctl("close")


def run(world, screenshot: Path | None) -> None:
    world.start()
    world.command("forceload add 0 0 47 15")
    time.sleep(CHUNK_SETTLE_SECONDS)
    failures = []
    for name, lava, item, count in SCENARIOS:
        failures += replay(world, name, lava, item, count)
    if failures:
        raise TestFailure("\n".join(failures))
    check_menu(world, screenshot)
    world.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(dir=WORK))
    world = SinglePlayer(folder, args.engine.resolve(), {})
    install_content(world.content_dir, WORK / "check/carry", WORK / "check-generators/carry")
    screenshot = args.screenshot.resolve() if args.screenshot else None
    try:
        run(world, screenshot)
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
