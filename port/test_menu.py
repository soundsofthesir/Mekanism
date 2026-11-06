#!/usr/bin/env python3
"""Phase 3 test: a player's use of a machine: its menu, side settings and default sides.

    python3 port/test_menu.py --engine port/.work/machine-export/horizon-engine [--screenshot FILE]

This checks what a menu does, against Mekanism's source for the defaults. There is no recording of
the real mod's screens, because they need a client.
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
Y = 200
CHAMBER = "mekanism:enrichment_chamber"
SETTLE_SECONDS = 0.5
RUN_SECONDS = 3
INPUT_MENU_SLOT = 300
OUTPUT_MENU_SLOT = 301
HOTBAR_SLOT = 0
# Screen positions, from port/machine: where the input slot is, and each top-side button.
INPUT_SLOT_AT = (64, 17)
TOP_INDEX = 4
SIDE_BUTTON_LEFT, SIDE_BUTTON_TOP, SIDE_BUTTON_STEP = 8, 18, 8
SIDE_BUTTON_MIDDLE = 3
# `LightConfigInfo.MACHINE` and `INPUT_ONLY`, in front, left, right, back, top, bottom order.
DEFAULT_ITEM_SIDES = [1, 1, 4, 8, 1, 1]
DEFAULT_ENERGY_SIDES = [1, 1, 1, 1, 1, 1]


def text(world, line: str) -> str:
    return " ".join(world.command(line))


def sides(nbt: str, config: str) -> list[int]:
    found = re.search(rf"{config}: \[I; ([^\]]+)\]", nbt)
    if not found:
        raise TestFailure(f"no {config} in {nbt}")
    return [int(value) for value in found.group(1).split(",")]


def expect(label: str, got: object, wanted: object) -> None:
    print(f"  {label}: {got}")
    if got != wanted:
        raise TestFailure(f"{label}: got {got}, expected {wanted}")


def stand_at(world, x: int, z: int) -> None:
    world.command(f"setblock {x} {Y - 1} {z - 1} minecraft:stone")
    world.command(f"tp @s {x} {Y} {z - 1}")
    time.sleep(SETTLE_SECONDS)


def open_menu(world, x: int, z: int) -> dict:
    world.ctl("interact", x, Y, z)
    time.sleep(SETTLE_SECONDS)
    return world.ctl("screen")


def slot_item(screen: dict, number: int) -> tuple:
    for slot in screen["slots"]:
        if slot["slot"] == number:
            return slot.get("item"), slot.get("count")
    raise TestFailure(f"no slot {number} in the screen")


def check_defaults(world) -> None:
    x, z = 0, 0
    world.command(f"setblock {x} {Y} {z} {CHAMBER}")
    nbt = text(world, f"data get block {x} {Y} {z}")
    expect("default item sides", sides(nbt, "config3"), DEFAULT_ITEM_SIDES)
    expect("default energy sides", sides(nbt, "config0"), DEFAULT_ENERGY_SIDES)


def check_menu_runs_the_machine(world, screenshot: Path | None) -> None:
    x, z = 0, 0
    stand_at(world, x, z)
    world.command("clear @s")
    world.command(f"data modify block {x} {Y} {z} energy set value 20")
    world.command("give @s minecraft:iron_ore 8")
    time.sleep(SETTLE_SECONDS)
    screen = open_menu(world, x, z)
    expect("screen", screen["screen"], "container")
    world.ctl("click-slot", HOTBAR_SLOT, "shift")
    time.sleep(SETTLE_SECONDS)
    expect("input after a shift-click", slot_item(world.ctl("screen"), INPUT_MENU_SLOT),
           ("minecraft:iron_ore", 8))
    # A machine holds 20, so it needs a steady supply to run.
    for _ in range(RUN_SECONDS * 4):
        world.command(f"data modify block {x} {Y} {z} energy set value 20")
        time.sleep(0.25)
    progress = int(re.search(r"progress: (\d+)", text(world, f"data get block {x} {Y} {z}")).group(1))
    print(f"  progress after about {RUN_SECONDS} seconds: {progress}")
    if progress <= 0:
        raise TestFailure("the machine did not run from its menu")
    if screenshot:
        world.ctl("screenshot", screenshot)
    world.ctl("close")


def press_side_button(world, screen_x: float, screen_y: float, index: int) -> None:
    column, line = index % 3, index // 3
    world.ctl(
        "click-at",
        screen_x + SIDE_BUTTON_LEFT + SIDE_BUTTON_STEP * column + SIDE_BUTTON_MIDDLE,
        screen_y + SIDE_BUTTON_TOP + SIDE_BUTTON_STEP * line + SIDE_BUTTON_MIDDLE,
    )
    time.sleep(SETTLE_SECONDS)


def screen_origin(world) -> tuple[float, float]:
    for widget in world.ctl("ui")["widgets"]:
        if widget.get("id") == f"slot-{INPUT_MENU_SLOT}":
            bounds = widget["bounds"]
            return bounds[0] - INPUT_SLOT_AT[0], bounds[1] - INPUT_SLOT_AT[1]
    raise TestFailure("the input slot is not among the screen's widgets")


def ore_in_hopper(world, x: int, z: int) -> int:
    found = re.search(r"count: (\d+)", text(world, f"data get block {x} {Y + 1} {z} Items"))
    return int(found.group(1)) if found else 0


def check_side_button_and_hopper(world) -> None:
    x, z = 4, 0
    world.command(f"setblock {x} {Y} {z} {CHAMBER}")
    stand_at(world, x, z)
    open_menu(world, x, z)
    origin = screen_origin(world)
    print(f"  screen origin: {origin}")
    # Top goes input, output, energy, none: three presses turn it off from output's far side.
    for _ in range(3):
        press_side_button(world, *origin, TOP_INDEX)
    world.ctl("close")
    nbt = text(world, f"data get block {x} {Y} {z}")
    expect("item sides after 3 presses on top", sides(nbt, "config3")[TOP_INDEX], 0)

    hopper = 'minecraft:hopper{Items:[{Slot:0b,id:"minecraft:iron_ore",count:4}]}'
    world.command(f"setblock {x} {Y + 1} {z} {hopper}")
    time.sleep(RUN_SECONDS)
    expect("ore left in a hopper above a side set to none", ore_in_hopper(world, x, z), 4)

    open_menu(world, x, z)
    press_side_button(world, *screen_origin(world), TOP_INDEX)
    world.ctl("close")
    expect("top side after one more press", sides(text(world, f"data get block {x} {Y} {z}"), "config3")[TOP_INDEX], 1)
    time.sleep(RUN_SECONDS)
    expect("ore left in a hopper above an input side", ore_in_hopper(world, x, z), 0)


def check_saved(world) -> None:
    x, z = 8, 0
    world.command(f"setblock {x} {Y} {z} {CHAMBER}")
    stand_at(world, x, z)
    open_menu(world, x, z)
    press_side_button(world, *screen_origin(world), TOP_INDEX)
    world.ctl("close")
    before = sides(text(world, f"data get block {x} {Y} {z}"), "config3")
    world.stop()
    world.start()
    expect("sides after a reload", sides(text(world, f"data get block {x} {Y} {z}"), "config3"), before)


def run(world, screenshot: Path | None) -> None:
    world.start()
    world.command("forceload add 0 -16 16 16")
    time.sleep(SETTLE_SECONDS)
    print("Defaults:")
    check_defaults(world)
    print("Menu:")
    check_menu_runs_the_machine(world, screenshot)
    print("Side buttons and a hopper:")
    check_side_button_and_hopper(world)
    print("Saved:")
    check_saved(world)
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
