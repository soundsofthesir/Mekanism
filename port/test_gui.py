#!/usr/bin/env python3
"""The Enrichment Chamber's real screen: Mekanism's art at the source's positions, read back from a
screenshot, and its side config window used with a player's clicks.

    python3 port/test_gui.py --engine port/.work/machine-export/horizon-engine --art upstream/src/main/resources/assets/mekanism/textures/gui/sprites [--screenshot FILE]

There is no picture of the real mod to compare with, because its screens need a Java client. Each
check compares screen pixels with the art file named, at the position GuiElectricMachine gives.
"""

import argparse
import math
import re
import shutil
import sys
import time
from pathlib import Path

from horizon_driver import SinglePlayer, TestFailure, install_content, begin_checks, run_test
from png_tools import Image

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
Y = 200
CHAMBER = "mekanism:enrichment_chamber"
SETTLE_SECONDS = 0.6
INPUT_MENU_SLOT = 300
# `GuiElectricMachine`, `GuiSideConfiguration` and `GuiInsetElement`.
INPUT_SLOT_AT = (64, 17)
OUTPUT_SLOT_AT = (116, 35)
ENERGY_SLOT_AT = (64, 53)
UP_ARROW_AT = (68, 38)
PROGRESS_AT = (86, 38)
POWER_BAR_AT = (164, 16)
SIDE_TAB_BUTTON_AT = (-21, 10)
WINDOW_AT = (10, 15)
CLOSE_AT = (6, 6)
TOP_BUTTON_AT = (67, 46)
EJECT_AT = (136, 6)
ENERGY_KIND_TAB = (-11, 49)
TAB_MIDDLE = 9
SIDE_MIDDLE = 11
ITEM_CONFIG, ENERGY_CONFIG = "config3", "config0"
TOP = 4
# `AttachedSideConfig.ELECTRIC_MACHINE`: what a placed machine has, since a command's data replaces it.
SIDES = "component_config:{config3:[I;1,1,4,8,1,1],config0:[I;1,1,1,1,1,1]}"
PROGRESS_INSIDE = 23
PROGRESS_TICKS = 200
POWER_INSIDE = 52
# A chamber with no upgrades: `AttributeEnergy.STORAGE_MULTIPLIER` times its usage.
ENERGY_CAPACITY = 20
# How much of a sprite's pixels may differ: anything a window scale and a shader doesn't change.
MAX_CHANNEL_DIFFERENCE = 2


def blend(art, background):
    alpha = art[3] / 255
    return tuple(round(art[i] * alpha + background[i] * (1 - alpha)) for i in range(3))


class Screen:
    """A screenshot with what it takes to find the screen's own pixels in it."""

    def __init__(self, path: Path, origin: tuple[float, float], scale: int) -> None:
        self.image, self.origin, self.scale = Image(path), origin, scale

    def at(self, x: float, y: float) -> tuple[int, int, int, int]:
        px = int((self.origin[0] + x) * self.scale)
        py = int((self.origin[1] + y) * self.scale)
        return self.image.pixel(px, py)

    def matches_art(self, art: Image, at: tuple[int, int], part=None, tint=None, drawn=None) -> int:
        """Counts the opaque art pixels that differ from the screen at `at`. `drawn` is the size the
        art was stretched to, when not its own."""
        sx, sy, width, height = part or (0, 0, art.width, art.height)
        factor = (drawn[0] / width, drawn[1] / height) if drawn else (1, 1)
        wrong = 0
        for y in range(height):
            for x in range(width):
                pixel = art.pixel(sx + x, sy + y)
                if pixel[3] < 255:
                    continue
                expected = pixel[:3]
                if tint:
                    expected = tuple(round(channel * t / 255) for channel, t in zip(expected, tint))
                got = self.at(at[0] + (x + 0.5) * factor[0], at[1] + (y + 0.5) * factor[1])[:3]
                if any(abs(a - b) > MAX_CHANNEL_DIFFERENCE for a, b in zip(got, expected)):
                    wrong += 1
        return wrong


def expect(label: str, got: object, wanted: object) -> None:
    print(f"  {label}: {got}")
    if got != wanted:
        raise TestFailure(f"{label}: got {got}, expected {wanted}")


def text(world, line: str) -> str:
    return " ".join(world.command(line))


def sides(nbt: str, config: str) -> list[int]:
    return [int(v) for v in re.search(rf"{config}: \[I; ([^\]]+)\]", nbt).group(1).split(",")]


def click(world, x: float, y: float, button: str = "") -> None:
    world.ctl("click-at", x, y, *([button] if button else []))
    time.sleep(SETTLE_SECONDS)


def origin_of(world) -> tuple[float, float]:
    for widget in world.ctl("ui")["widgets"]:
        if widget.get("id") == f"slot-{INPUT_MENU_SLOT}":
            x, y = widget["bounds"][0], widget["bounds"][1]
            return x - INPUT_SLOT_AT[0], y - INPUT_SLOT_AT[1]
    raise TestFailure("the input slot is not among the screen's widgets")


def shot(world, path: Path, origin, scale: int) -> Screen:
    world.ctl("screenshot", path)
    time.sleep(SETTLE_SECONDS)
    return Screen(path, origin, scale)


def check_art(screen: Screen, art: Path) -> None:
    # The input slot holds ore, so only its frame's top row shows.
    frame = screen.matches_art(Image(art / "slot/input.png"), (INPUT_SLOT_AT[0] - 1, INPUT_SLOT_AT[1] - 1), (0, 0, 18, 1))
    expect("input slot's top row: pixels unlike slot/input", frame, 0)
    for name, sprite, at in (
        ("output slot", "slot/output", (OUTPUT_SLOT_AT[0] - 1, OUTPUT_SLOT_AT[1] - 1)),
        ("energy slot", "slot/power", (ENERGY_SLOT_AT[0] - 1, ENERGY_SLOT_AT[1] - 1)),
        ("inventory slot", "slot/normal", (7, 83)),
        ("up arrow", "arrow/up", UP_ARROW_AT),
        ("side config tab's icon", "button/configuration", SIDE_TAB_BUTTON_AT),
        ("energy tab", "tab/energy_info", (-26, 137)),
    ):
        expect(f"{name}: pixels unlike {sprite}", screen.matches_art(Image(art / f"{sprite}.png"), at), 0)


def check_tab_tints(screen: Screen, art: Path) -> None:
    """A tab's holder, tinted by `SpecialColors`: its nine-slice corner, unscaled, at the tab's corner."""
    holder = Image(art / "holder_right.png")
    for name, at, tint in (
        ("redstone tab's holder", (176, 137), (0xC9, 0x07, 0x1F)),
        ("security tab's holder", (176, 34), (0xFF, 0xA1, 0x60)),
        ("experience tab's holder", (176, 90), (0x80, 0xFF, 0x20)),
    ):
        expect(f"{name}: pixels unlike the tinted art", screen.matches_art(holder, at, (0, 0, 4, 4), tint), 0)


def check_bars(screen: Screen, art: Path, progress: int, energy: int) -> None:
    # `GuiProgress.calculateProgressSize`.
    filled = math.ceil(progress / PROGRESS_TICKS * (PROGRESS_INSIDE - 1)) + 1
    full, empty = Image(art / "progress/bar/full.png"), Image(art / "progress/bar/empty.png")
    expect(
        "progress bar's filled part",
        screen.matches_art(full, (PROGRESS_AT[0] + 1, PROGRESS_AT[1]), (1, 0, filled, 9)),
        0,
    )
    rest = (1 + filled, 0, 24 - filled, 9)
    expect(
        "progress bar's empty part",
        screen.matches_art(empty, (PROGRESS_AT[0] + 1 + filled, PROGRESS_AT[1]), rest),
        0,
    )
    # `GuiBar.calculateSize` of the 52 pixels inside the bar, from the bottom.
    bar = Image(art / "bar/vertical_power.png")
    x, y = POWER_BAR_AT[0] + 1, POWER_BAR_AT[1] + 1
    colours = {bar.pixel(px, py)[:3] for px in range(bar.width) for py in range(bar.height)}
    close = lambda got: any(all(abs(a - b) <= MAX_CHANNEL_DIFFERENCE for a, b in zip(got, colour)) for colour in colours)
    lit = sum(close(screen.at(x + 0.5, y + row + 0.5)[:3]) for row in range(POWER_INSIDE))
    expect("power bar's lit rows", lit, math.ceil(energy / ENERGY_CAPACITY * (POWER_INSIDE - 1)) + 1)


def check_window(world, screen_origin, scale: int, art: Path, x: int, z: int, folder: Path) -> None:
    ox, oy = screen_origin
    wx, wy = ox + WINDOW_AT[0], oy + WINDOW_AT[1]
    click(world, ox + SIDE_TAB_BUTTON_AT[0] + TAB_MIDDLE, oy + SIDE_TAB_BUTTON_AT[1] + TAB_MIDDLE)
    screen = shot(world, folder / "window.png", screen_origin, scale)
    expect(
        "window's close icon: pixels unlike button/close",
        screen.matches_art(Image(art / "button/close.png"), (WINDOW_AT[0] + CLOSE_AT[0], WINDOW_AT[1] + CLOSE_AT[1]), drawn=(8, 8)),
        0,
    )
    expect(
        "eject icon: pixels unlike button/auto_eject",
        screen.matches_art(Image(art / "button/auto_eject.png"), (WINDOW_AT[0] + EJECT_AT[0], WINDOW_AT[1] + EJECT_AT[1])),
        0,
    )
    energy_tab_icon = Image(art / "transmission/energy.png")
    expect("energy kind's tab icon", screen.matches_art(energy_tab_icon, ENERGY_KIND_TAB), 0)

    nbt = text(world, f"data get block {x} {Y} {z}")
    before = sides(nbt, ITEM_CONFIG)[TOP]
    expect("top side before the window's button", before, 1)
    top_x, top_y = wx + TOP_BUTTON_AT[0] + SIDE_MIDDLE, wy + TOP_BUTTON_AT[1] + SIDE_MIDDLE
    click(world, top_x, top_y)
    expect("top after a left click", sides(text(world, f"data get block {x} {Y} {z}"), ITEM_CONFIG)[TOP], 4)
    click(world, top_x, top_y, "right")
    expect("top after a right click", sides(text(world, f"data get block {x} {Y} {z}"), ITEM_CONFIG)[TOP], 1)

    # A press on the window over the slot under it takes nothing out of the inventory.
    world.command("item replace entity @s container.9 with minecraft:iron_ore 8")
    time.sleep(SETTLE_SECONDS)
    click(world, ox + 8 + 8, oy + 84 + 8)
    expect("what a press outside the window's controls picks up, over a slot", world.ctl("screen").get("carried"), None)

    click(world, wx + EJECT_AT[0] + 7, wy + EJECT_AT[1] + 7)
    expect("items eject after its button", "eject3: 1b" in text(world, f"data get block {x} {Y} {z}"), True)
    click(world, ox + ENERGY_KIND_TAB[0] + TAB_MIDDLE, oy + ENERGY_KIND_TAB[1] + TAB_MIDDLE)
    click(world, top_x, top_y)
    expect("energy top after the energy tab and a click", sides(text(world, f"data get block {x} {Y} {z}"), ENERGY_CONFIG)[TOP], 0)
    click(world, wx + CLOSE_AT[0] + 4, wy + CLOSE_AT[1] + 4)
    closed = shot(world, folder / "closed.png", screen_origin, scale)
    frame = closed.matches_art(Image(art / "slot/input.png"), (INPUT_SLOT_AT[0] - 1, INPUT_SLOT_AT[1] - 1), (0, 0, 18, 1))
    expect("input slot back after closing", frame, 0)


def run(world, art: Path, screenshot: Path | None, folder: Path) -> None:
    world.start()
    world.command("forceload add 0 -16 16 16")
    time.sleep(SETTLE_SECONDS)
    x, z = 0, 0
    world.command(f"setblock {x} {Y - 1} {z - 1} minecraft:stone")
    world.command(f"tp @s {x} {Y} {z - 1}")
    time.sleep(SETTLE_SECONDS)
    ore = '{Slot:0b,id:"minecraft:iron_ore",count:8}'
    world.command(f"setblock {x} {Y} {z} {CHAMBER}{{{SIDES},energy:20,progress:100,Items:[{ore}]}}")
    world.command("tick freeze")
    world.ctl("interact", x, Y, z)
    time.sleep(SETTLE_SECONDS)
    begin_checks()
    origin = origin_of(world)
    gui_width = world.ctl("ui")["gui_size"][0]
    first = shot(world, folder / "scale.png", origin, 1)
    scale = round(first.image.width / gui_width)
    print(f"  screen at {origin}, GUI scale {scale}")
    screen = shot(world, folder / "machine.png", origin, scale)
    if screenshot:
        shutil.copy(folder / "machine.png", screenshot)
    check_art(screen, art)
    check_tab_tints(screen, art)
    nbt = text(world, f"data get block {x} {Y} {z}")
    check_bars(screen, art, int(re.search(r"progress: (\d+)", nbt).group(1)), int(re.search(r"\benergy: (\d+)", nbt).group(1)))
    world.command("tick unfreeze")
    check_window(world, origin, scale, art, x, z, folder)
    world.ctl("close")
    world.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--art", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    art = args.art.resolve()
    screenshot = args.screenshot.resolve() if args.screenshot else None
    kind = SinglePlayer

    def make(folder: Path):
        world = kind(folder, args.engine.resolve(), {})
        install_content(world.content_dir, WORK / "check/carry", WORK / "check-generators/carry")
        return world

    return run_test(make, lambda world: run(world, art, screenshot, world.folder))


if __name__ == "__main__":
    sys.exit(main())
