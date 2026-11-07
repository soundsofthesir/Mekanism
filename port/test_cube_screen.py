#!/usr/bin/env python3
"""The Energy Cube's screen: its gauge read back from screenshots across the 16-bit limit of a menu's
data slot, and a side changed by a player's clicks."""

import argparse
import re
import sys
import time
from pathlib import Path

from png_tools import Image
from horizon_driver import SinglePlayer, TestFailure, begin_checks, install_content, run_test
from test_gui import SETTLE_SECONDS, TAB_MIDDLE, Y, click, expect, shot, text

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
DISCHARGE_MENU_SLOT = 300
DISCHARGE_AT = (17, 35)
SIDE_TAB_BUTTON_AT = (-21, 10)
WINDOW_AT = (10, 15)
TOP_BUTTON_AT = (67, 46)
SIDE_MIDDLE = 11
TOP = 4
# `GuiEnergyCube`'s gauge: the 48 rows inside it, and a column well inside its width.
GAUGE_INSIDE_TOP = 19
GAUGE_ROWS = 48
GAUGE_COLUMN = 90
OVERLAY = HERE.parent / "upstream/src/main/resources/assets/mekanism/textures/gui/sprites/gauge/overlay/wide.png"
GAUGE_INSIDE_LEFT = 56
CUBE = "mekanism:basic_energy_cube"
CAPACITY = 4_000_000
SIDES = "component_config:{config0:[I;4,1,1,1,1,1],config3:[I;4,1,1,1,1,1]}"


def origin_of(world) -> tuple[float, float]:
    for widget in world.ctl("ui")["widgets"]:
        if widget.get("id") == f"slot-{DISCHARGE_MENU_SLOT}":
            return widget["bounds"][0] - DISCHARGE_AT[0], widget["bounds"][1] - DISCHARGE_AT[1]
    raise TestFailure("the discharge slot is not among the screen's widgets")


def rows_of(screen) -> list[tuple[int, int, int]]:
    return [screen.at(GAUGE_COLUMN + 0.5, GAUGE_INSIDE_TOP + row + 0.5)[:3] for row in range(GAUGE_ROWS)]


def lit_rows(world, origin, scale: int, empty: list, energy: int, folder: Path) -> int:
    world.command(f"data modify block 0 {Y} 0 energy set value {energy}")
    time.sleep(2 * SETTLE_SECONDS)
    rows = rows_of(shot(world, folder / f"energy_{energy}.png", origin, scale))
    return sum(1 for got, before in zip(rows, empty) if got != before)


def run(world, folder: Path) -> None:
    world.start()
    world.command("forceload add 0 -16 16 16")
    time.sleep(SETTLE_SECONDS)
    world.command(f"setblock 0 {Y - 1} -1 minecraft:stone")
    world.command(f"tp @s 0 {Y} -1")
    time.sleep(SETTLE_SECONDS)
    world.command(f"setblock 0 {Y} 0 {CUBE}{{{SIDES}}}")
    time.sleep(SETTLE_SECONDS)
    world.ctl("interact", 0, Y, 0)
    time.sleep(SETTLE_SECONDS)
    begin_checks()
    origin = origin_of(world)
    gui_width = world.ctl("ui")["gui_size"][0]
    scale = round(shot(world, folder / "scale.png", origin, 1).image.width / gui_width)
    empty = rows_of(shot(world, folder / "empty.png", origin, scale))
    overlay = Image(OVERLAY)
    hidden = {row for row in range(GAUGE_ROWS) if overlay.pixel(GAUGE_COLUMN - GAUGE_INSIDE_LEFT, row)[3] == 255}
    for energy in (32_767, 32_768, 40_000, 65_536, 1_000_000, 2_000_000, CAPACITY):
        # `GuiTankGauge.getScaledLevel`: at least a row when anything is held.
        filled = max(1, round(energy / CAPACITY * GAUGE_ROWS))
        # The overlay's opaque tick marks hide the rows they cross.
        wanted = sum(1 for row in range(GAUGE_ROWS - filled, GAUGE_ROWS) if row not in hidden)
        expect(f"gauge rows at {energy} FE", lit_rows(world, origin, scale, empty, energy, folder), wanted)
    wx, wy = origin[0] + WINDOW_AT[0], origin[1] + WINDOW_AT[1]
    click(world, origin[0] + SIDE_TAB_BUTTON_AT[0] + TAB_MIDDLE, origin[1] + SIDE_TAB_BUTTON_AT[1] + TAB_MIDDLE)
    click(world, wx + TOP_BUTTON_AT[0] + SIDE_MIDDLE, wy + TOP_BUTTON_AT[1] + SIDE_MIDDLE)
    nbt = text(world, f"data get block 0 {Y} 0")
    sides = [int(v) for v in re.search(r"config3: \[I; ([^\]]+)\]", nbt).group(1).split(",")]
    expect("top item side after a click", sides[TOP], 4)
    world.ctl("close")
    world.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True)
    args = parser.parse_args()

    def make(folder: Path):
        world = SinglePlayer(folder, args.engine.resolve(), {})
        (world.game_dir / "options.txt").write_text("tutorialStep:none\n")
        install_content(world.content_dir, WORK / "check/carry", WORK / "check-generators/carry")
        return world

    return run_test(make, lambda world: run(world, world.folder))


if __name__ == "__main__":
    sys.exit(main())
