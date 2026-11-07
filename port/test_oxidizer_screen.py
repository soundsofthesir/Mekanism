#!/usr/bin/env python3
"""Compares the Chemical Oxidizer's screen with Mekanism's art at the positions in its source, and
plays through its side config window, as `test_gui.py` does for the Enrichment Chamber.

Each element's position is `GuiChemicalOxidizer`'s. Tooltips are checked by the size of what appears
in a screenshot; their words are tested in `mekmachine_engine::gui_layout`.
"""

import argparse
import math
import re
import shutil
import sys
import time
from pathlib import Path

from horizon_driver import SinglePlayer, TestFailure, begin_checks, install_content, run_test
from png_tools import Image
from test_gui import (
    MAX_CHANNEL_DIFFERENCE,
    SETTLE_SECONDS,
    SIDE_MIDDLE,
    SIDE_TAB_BUTTON_AT,
    TAB_MIDDLE,
    TOP,
    TOP_BUTTON_AT,
    WINDOW_AT,
    CLOSE_AT,
    EJECT_AT,
    Screen,
    check_tab_tints,
    click,
    expect,
    shot,
    sides,
    text,
)

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
Y = 200
OXIDIZER = "mekanism:chemical_oxidizer"
PANEL = (176, 166)
INPUT_MENU_SLOT = 300
INPUT_AT = (26, 36)
DRAIN_AT = (152, 55)
ENERGY_SLOT_AT = (152, 14)
PROGRESS_AT = (64, 40)
PROGRESS_SIZE = (48, 8)
GAUGE_AT = (131, 13)
GAUGE_INSIDE = (16, 58)
BAR_AT = (115, 75)
BAR_INSIDE = (52, 4)
TICKS = 100
PROGRESS = 50
ENERGY = 10
# `TileEntityChemicalOxidizer`'s usage times `AttributeEnergy.STORAGE_MULTIPLIER`, read from the menu.
ENERGY_CAPACITY = 60
CHEMICAL = 2500
TANK_CAPACITY = 10_000
# `ChemicalConstants.SULFUR_DIOXIDE`.
TINT = (0xA9, 0x9D, 0x90)
CHEMICAL_CONFIG, ENERGY_CONFIG, ITEM_CONFIG = "config2", "config0", "config3"
# `GuiConfigTypeTab`'s place in the window: items, chemicals, energy.
CHEMICAL_TAB_AT = (-11, 49)
ENERGY_TAB_AT = (-11, 77)
SIDES = "component_config:{config3:[I;1,1,4,8,1,1],config0:[I;1,1,1,1,1,1],config2:[I;0,0,4,0,0,0]}"
TANK = f'chemical_tanks:[{{container:0b,stored:{{amount:{CHEMICAL}L,type:"mekanism:sulfur_dioxide"}}}}]'
ORE = '{Slot:0b,id:"mekanism:dust_sulfur",count:8}'
# The least a tooltip changes, in screen pixels.
TOOLTIP_PIXELS = 200


def origin_of(world) -> tuple[float, float]:
    for widget in world.ctl("ui")["widgets"]:
        if widget.get("id") == f"slot-{INPUT_MENU_SLOT}":
            return widget["bounds"][0] - INPUT_AT[0], widget["bounds"][1] - INPUT_AT[1]
    raise TestFailure("the input slot is not among the screen's widgets")


def check_art(screen: Screen, art: Path) -> None:
    for name, sprite, at in (
        ("input slot", "slot/input", (INPUT_AT[0] - 1, INPUT_AT[1] - 1)),
        ("drain slot", "slot/extra", (DRAIN_AT[0] - 1, DRAIN_AT[1] - 1)),
        ("energy slot", "slot/power", (ENERGY_SLOT_AT[0] - 1, ENERGY_SLOT_AT[1] - 1)),
        ("inventory slot", "slot/normal", (7, 83)),
        ("side config tab's icon", "button/configuration", SIDE_TAB_BUTTON_AT),
        ("energy tab", "tab/energy_info", (-26, 137)),
        ("gauge's overlay", "gauge/overlay/standard", (GAUGE_AT[0] + 1, GAUGE_AT[1] + 1)),
    ):
        part = (0, 0, 18, 1) if name == "input slot" else None
        expect(f"{name}: pixels unlike {sprite}", screen.matches_art(Image(art / f"{sprite}.png"), at, part), 0)
    corner = Image(art / "gauge/normal.png")
    expect("gauge's frame corner", screen.matches_art(corner, GAUGE_AT, (0, 0, 2, 2)), 0)
    base = Image(art / "bar/base.png")
    expect("power bar's frame corner", screen.matches_art(base, BAR_AT, (0, 0, 1, 1)), 0)


def check_progress(screen: Screen, art: Path, progress: int) -> None:
    filled = math.ceil(progress / TICKS * (PROGRESS_SIZE[0] - 1)) + 1
    print(f"  progress {progress}, {filled} pixels filled")
    full, empty = Image(art / "progress/large_right/full.png"), Image(art / "progress/large_right/empty.png")
    height = PROGRESS_SIZE[1]
    expect("filled part of the progress bar", screen.matches_art(full, PROGRESS_AT, (0, 0, filled, height)), 0)
    rest = (PROGRESS_AT[0] + filled, PROGRESS_AT[1])
    expect("empty part of the progress bar", screen.matches_art(empty, rest, (filled, 0, PROGRESS_SIZE[0] - filled, height)), 0)


def is_gas(pixel: tuple, background: tuple, tiles: set[int], alpha: float) -> bool:
    """Whether a pixel is the tinted gas tile over the gauge's background."""
    for grey in tiles:
        wanted = [round(t * grey / 255 * alpha + b * (1 - alpha)) for t, b in zip(TINT, background)]
        if all(abs(a - b) <= MAX_CHANNEL_DIFFERENCE + 1 for a, b in zip(pixel, wanted)):
            return True
    return False


def check_gauge(screen: Screen, art: Path, gas: Image, stored: int, label: str) -> None:
    """The gauge's height comes from `GuiTankGauge.getScaledLevel`. A column the overlay leaves clear
    must be the background down to the level and the tinted gas from there. The rows the overlay's
    marks cross are skipped, and the overlay is compared elsewhere."""
    inside = GAUGE_INSIDE[1]
    level = max(1, math.floor(stored / TANK_CAPACITY * inside + 0.5)) if stored else 0
    background = Image(art / "gauge/normal.png").pixel(2, 2)[:3]
    tiles = {gas.pixel(x, y)[0] for y in range(gas.height) for x in range(gas.width)}
    alpha = gas.pixel(0, 0)[3] / 255
    column = GAUGE_AT[0] + 1 + 8
    print(f"  gauge at {label}: level {level}")
    overlay = Image(art / "gauge/overlay/standard.png")
    clear = [row for row in range(inside) if overlay.pixel(8, row)[3] == 0]
    wrong_above = wrong_below = 0
    for row in clear:
        pixel = screen.at(column + 0.5, GAUGE_AT[1] + 1 + row + 0.5)[:3]
        if row < inside - level:
            wrong_above += any(abs(a - b) > MAX_CHANNEL_DIFFERENCE for a, b in zip(pixel, background))
        else:
            wrong_below += not is_gas(pixel, background, tiles, alpha)
    expect(f"gauge at {label}: {inside - level} rows above the gas, pixels wrong", wrong_above, 0)
    expect(f"gauge at {label}: {level} rows of gas, pixels wrong", wrong_below, 0)


def check_power(screen: Screen, art: Path, energy: int) -> None:
    filled = math.ceil(energy / ENERGY_CAPACITY * (BAR_INSIDE[0] - 1)) + 1
    print(f"  energy {energy}, {filled} pixels filled")
    tile = Image(art / "bar/horizontal_power.png")
    row = 1
    y = BAR_AT[1] + 1 + row + 0.5
    # The tile is 2 pixels square and starts at the bar's inside, a pixel in.
    wrong = sum(
        any(
            abs(a - b) > MAX_CHANNEL_DIFFERENCE
            for a, b in zip(screen.at(BAR_AT[0] + 1 + x + 0.5, y)[:3], tile.pixel(x % 2, row)[:3])
        )
        for x in range(filled)
    )
    expect(f"the power bar's {filled} filled pixels, wrong", wrong, 0)
    after = screen.at(BAR_AT[0] + 1 + filled + 0.5, y)[:3]
    expect("the power bar stops there", after in {tile.pixel(0, row)[:3], tile.pixel(1, row)[:3]}, False)


def changed_box(screen: Screen, other: Screen) -> tuple[int, int, int]:
    """The width, height and count of pixels that differ inside the screen's panel, which nothing
    moves behind. A tooltip is the only thing that changes there."""
    a, b = screen.image, other.image
    left, top = int(screen.origin[0] * screen.scale), int(screen.origin[1] * screen.scale)
    xs, ys = [], []
    for y in range(top + 4, top + (PANEL[1] - 4) * screen.scale):
        for x in range(left + 4, left + (PANEL[0] - 4) * screen.scale):
            if a.pixel(x, y) != b.pixel(x, y):
                xs.append(x)
                ys.append(y)
    if not xs:
        return 0, 0, 0
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, len(xs)


def tooltip_box(world, folder: Path, base: Screen, origin, scale, at: tuple[float, float], name: str) -> tuple[int, int, int]:
    click(world, origin[0] + at[0], origin[1] + at[1])
    hover = shot(world, folder / f"hover_{name}.png", origin, scale)
    return changed_box(hover, base)


def check_tooltips(world, folder: Path, origin, scale: int) -> None:
    """Moves the cursor with a press that does nothing, since the screen has no other way."""
    click(world, origin[0] + 80, origin[1] + 12)
    base = shot(world, folder / "no_hover.png", origin, scale)
    gauge = (GAUGE_AT[0] + 9, GAUGE_AT[1] + 30)
    gas = tooltip_box(world, folder, base, origin, scale, gauge, "gauge")
    bar = tooltip_box(world, folder, base, origin, scale, (BAR_AT[0] + 20, BAR_AT[1] + 3), "bar")
    tab = tooltip_box(world, folder, base, origin, scale, (-13, 150), "energy_tab")
    print(f"  tooltip sizes: gauge {gas}, power bar {bar}, energy tab {tab}")
    for name, box in (("gauge", gas), ("power bar", bar), ("energy tab", tab)):
        if box[2] < TOOLTIP_PIXELS:
            raise TestFailure(f"no tooltip over the {name}: {box}")
    if not tab[1] > gas[1]:
        raise TestFailure(f"the energy tab has 3 lines and the gauge 1: {tab}, {gas}")


def check_window(world, origin, scale: int, art: Path, x: int, z: int, folder: Path) -> None:
    ox, oy = origin
    wx, wy = ox + WINDOW_AT[0], oy + WINDOW_AT[1]
    nbt = lambda: text(world, f"data get block {x} {Y} {z}")
    click(world, ox + SIDE_TAB_BUTTON_AT[0] + TAB_MIDDLE, oy + SIDE_TAB_BUTTON_AT[1] + TAB_MIDDLE)
    screen = shot(world, folder / "window.png", origin, scale)
    chemicals = Image(art / "transmission/chemicals.png")
    expect("chemical kind's tab icon", screen.matches_art(chemicals, CHEMICAL_TAB_AT), 0)
    energy = Image(art / "transmission/energy.png")
    expect("energy kind's tab icon", screen.matches_art(energy, ENERGY_TAB_AT), 0)
    top_x, top_y = wx + TOP_BUTTON_AT[0] + SIDE_MIDDLE, wy + TOP_BUTTON_AT[1] + SIDE_MIDDLE
    click(world, top_x, top_y)
    expect("items: top after a left click", sides(nbt(), ITEM_CONFIG)[TOP], 4)
    click(world, top_x, top_y, "right")

    click(world, ox + CHEMICAL_TAB_AT[0] + TAB_MIDDLE, oy + CHEMICAL_TAB_AT[1] + TAB_MIDDLE)
    screen = shot(world, folder / "window_chemical.png", origin, scale)
    items = Image(art / "transmission/items.png")
    expect("item kind's tab icon on the chemical page", screen.matches_art(items, (-11, 21)), 0)
    click(world, top_x, top_y)
    expect("chemicals: top after a left click", sides(nbt(), CHEMICAL_CONFIG)[TOP], 4)
    click(world, top_x, top_y)
    expect("chemicals: top after another", sides(nbt(), CHEMICAL_CONFIG)[TOP], 0)
    before = "eject2: 1b" in nbt()
    click(world, wx + EJECT_AT[0] + 7, wy + EJECT_AT[1] + 7)
    expect("chemicals eject after its button", "eject2: 1b" in nbt(), not before)

    click(world, ox + ENERGY_TAB_AT[0] + TAB_MIDDLE, oy + ENERGY_TAB_AT[1] + TAB_MIDDLE)
    click(world, top_x, top_y)
    expect("energy: top after the energy tab and a click", sides(nbt(), ENERGY_CONFIG)[TOP], 0)
    click(world, wx + CLOSE_AT[0] + 4, wy + CLOSE_AT[1] + 4)


def run(world, art: Path, textures: Path, screenshot: Path | None, folder: Path) -> None:
    world.start()
    world.command("forceload add 0 -16 16 16")
    time.sleep(SETTLE_SECONDS)
    x, z = 0, 0
    world.command(f"setblock {x} {Y - 1} {z - 1} minecraft:stone")
    world.command(f"tp @s {x} {Y} {z - 1}")
    time.sleep(SETTLE_SECONDS)
    state = f"{SIDES},energy:{ENERGY},progress:{PROGRESS},{TANK},Items:[{ORE}]"
    world.command(f"setblock {x} {Y} {z} {OXIDIZER}{{{state}}}")
    world.command("tick freeze")
    world.ctl("interact", x, Y, z)
    time.sleep(SETTLE_SECONDS)
    begin_checks()
    origin = origin_of(world)
    gui_width = world.ctl("ui")["gui_size"][0]
    first = shot(world, folder / "scale.png", origin, 1)
    scale = round(first.image.width / gui_width)
    print(f"  screen at {origin}, GUI scale {scale}")
    screen = shot(world, folder / "oxidizer.png", origin, scale)
    if screenshot:
        shutil.copy(folder / "oxidizer.png", screenshot)
    check_art(screen, art)
    check_tab_tints(screen, art)
    nbt = text(world, f"data get block {x} {Y} {z}")
    check_progress(screen, art, int(re.search(r"progress: (\d+)", nbt).group(1)))
    gas = Image(textures / "mek_liquid/liquid.png")
    check_gauge(screen, art, gas, CHEMICAL, str(CHEMICAL))
    check_power(screen, art, int(re.search(r"\benergy: (\d+)", nbt).group(1)))
    check_tooltips(world, folder, origin, scale)
    check_window(world, origin, scale, art, x, z, folder)

    fuller = 7_500
    world.command(f'data modify block {x} {Y} {z} chemical_tanks[0].stored.amount set value {fuller}L')
    time.sleep(SETTLE_SECONDS)
    world.command("tick step 1")
    time.sleep(SETTLE_SECONDS)
    click(world, origin[0] + 100, origin[1] + 70)
    screen = shot(world, folder / "fuller.png", origin, scale)
    check_gauge(screen, art, gas, fuller, str(fuller))
    world.command("tick unfreeze")
    world.ctl("close")
    world.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--art", type=Path, required=True)
    parser.add_argument("--textures", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    art, textures = args.art.resolve(), args.textures.resolve()
    screenshot = args.screenshot.resolve() if args.screenshot else None

    def make(folder: Path):
        world = SinglePlayer(folder, args.engine.resolve(), {})
        install_content(world.content_dir, WORK / "check/carry", WORK / "check-generators/carry")
        return world

    return run_test(make, lambda world: run(world, art, textures, screenshot, world.folder))


if __name__ == "__main__":
    sys.exit(main())
