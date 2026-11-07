#!/usr/bin/env python3
"""Compares the Osmium Compressor's screen with Mekanism's art at the positions in its source, and
plays through its slots and side config window, as `test_oxidizer_screen.py` does for the oxidizer.

Each element's position is `GuiAdvancedElectricMachine`'s, and each slot's is from
`TileEntityAdvancedElectricMachine`.
"""

import argparse
import math
import re
import sys
import time
from pathlib import Path

import test_oxidizer_screen as oxidizer
from horizon_driver import SinglePlayer, TestFailure, begin_checks, install_content, run_test
from png_tools import Image
from test_upgrades import carried, hotbar
from test_gui import MAX_CHANNEL_DIFFERENCE, SETTLE_SECONDS, Screen, check_tab_tints, click, expect, shot, text

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
Y = 200
COMPRESSOR = "mekanism:osmium_compressor"
INPUT_AT = (64, 17)
SECONDARY_AT = (64, 53)
OUTPUT_AT = (116, 35)
ENERGY_AT = (39, 35)
PROGRESS_AT = (86, 38)
PROGRESS_SIZE = (25, 9)
BAR_AT = (68, 36)
BAR_INSIDE = (6, 12)
POWER_AT = (164, 16)
POWER_INSIDE = (4, 52)
TANK_CAPACITY = 210
TICKS = 200
PROGRESS = 100
ENERGY = 30
# `osmiumCompressor`'s usage times `AttributeEnergy.STORAGE_MULTIPLIER`.
ENERGY_CAPACITY = 60
OSMIUM = 150
SIDES = "component_config:{config0:[I;1,1,1,1,1,1],config2:[I;1,1,1,1,1,1],config3:[I;1,1,1,1,1,1]}"
TANK = 'chemical_tanks:[{container:0b,stored:{amount:%dL,type:"mekanism:osmium"}}]'
DUST = '{Slot:0b,id:"minecraft:glowstone_dust",count:8}'
SLOT_MIDDLE = 8
# `data/mekanism/mekanism/chemical/osmium.json`'s tint.
TINT = (0x52, 0xBD, 0xCA)


def origin_of(world) -> tuple[float, float]:
    for widget in world.ctl("ui")["widgets"]:
        if widget.get("id") == "slot-300":
            return widget["bounds"][0] - INPUT_AT[0], widget["bounds"][1] - INPUT_AT[1]
    raise TestFailure("the input slot is not among the screen's widgets")


def check_art(screen: Screen, art: Path) -> None:
    for name, sprite, at, part in (
        ("input slot", "slot/input", (INPUT_AT[0] - 1, INPUT_AT[1] - 1), (0, 0, 18, 1)),
        ("secondary slot", "slot/extra", (SECONDARY_AT[0] - 1, SECONDARY_AT[1] - 1), (0, 0, 18, 1)),
        ("output slot", "slot/output", (OUTPUT_AT[0] - 1, OUTPUT_AT[1] - 1), None),
        ("energy slot", "slot/power", (ENERGY_AT[0] - 1, ENERGY_AT[1] - 1), None),
        ("inventory slot", "slot/normal", (7, 83), None),
    ):
        expect(f"{name}: pixels unlike {sprite}", screen.matches_art(Image(art / f"{sprite}.png"), at, part), 0)
    base = Image(art / "bar/base.png")
    expect("chemical bar's frame corner", screen.matches_art(base, BAR_AT, (0, 0, 1, 1)), 0)
    expect("power bar's frame corner", screen.matches_art(base, POWER_AT, (0, 0, 1, 1)), 0)


def check_progress(screen: Screen, art: Path, progress: int) -> None:
    """`ProgressType.BAR` starts a pixel in on each side."""
    filled = math.ceil(progress / TICKS * (PROGRESS_SIZE[0] - 3)) + 1
    full, empty = Image(art / "progress/bar/full.png"), Image(art / "progress/bar/empty.png")
    expect("filled part of the progress bar", screen.matches_art(full, (PROGRESS_AT[0] + 1, PROGRESS_AT[1]), (1, 0, filled, PROGRESS_SIZE[1])), 0)
    rest = (PROGRESS_AT[0] + 1 + filled, PROGRESS_AT[1])
    expect("empty part of the progress bar", screen.matches_art(empty, rest, (1 + filled, 0, PROGRESS_SIZE[0] - 2 - filled, PROGRESS_SIZE[1])), 0)


def is_osmium(pixel: tuple, gas: Image) -> bool:
    """A pixel of the gas tile, tinted and over the bar: blue over red, as the tint's bytes order."""
    return pixel[2] > pixel[0] + MAX_CHANNEL_DIFFERENCE and pixel[1] > pixel[0] + MAX_CHANNEL_DIFFERENCE


def check_chemical_bar(screen: Screen, gas: Image, stored: int) -> None:
    filled = math.ceil(stored / TANK_CAPACITY * (BAR_INSIDE[1] - 1)) + 1
    x = BAR_AT[0] + 1 + BAR_INSIDE[0] / 2
    rows = [screen.at(x, BAR_AT[1] + 1 + row + 0.5)[:3] for row in range(BAR_INSIDE[1])]
    above, below = rows[: BAR_INSIDE[1] - filled], rows[BAR_INSIDE[1] - filled :]
    expect(f"chemical bar at {stored}: rows above the gas that are gas", sum(is_osmium(p, gas) for p in above), 0)
    expect(f"chemical bar at {stored}: rows of gas that aren't", sum(not is_osmium(p, gas) for p in below), 0)


def check_power(screen: Screen, art: Path, energy: int) -> None:
    filled = math.ceil(energy / ENERGY_CAPACITY * (POWER_INSIDE[1] - 1)) + 1
    tile = Image(art / "bar/vertical_power.png")
    colours = {tile.pixel(x, y)[:3] for x in range(tile.width) for y in range(tile.height)}
    x = POWER_AT[0] + 1 + POWER_INSIDE[0] / 2
    bottom = POWER_AT[1] + 1 + POWER_INSIDE[1]
    near = lambda pixel: any(all(abs(a - b) <= MAX_CHANNEL_DIFFERENCE for a, b in zip(pixel, each)) for each in colours)
    wrong = sum(not near(screen.at(x, bottom - row - 0.5)[:3]) for row in range(filled))
    expect(f"the power bar's {filled} filled rows, wrong", wrong, 0)
    expect("the power bar stops there", near(screen.at(x, bottom - filled - 0.5)[:3]), False)


def slot_at(origin, at: tuple[int, int]) -> tuple[float, float]:
    return origin[0] + at[0] + SLOT_MIDDLE, origin[1] + at[1] + SLOT_MIDDLE


def check_secondary_slot(world, origin, x: int, z: int) -> None:
    """Dirt is refused, and an ingot put there gives its 200 mB on a tick."""
    world.command("item replace entity @s hotbar.0 with minecraft:dirt 4")
    world.command("item replace entity @s hotbar.1 with mekanism:ingot_osmium 2")
    time.sleep(SETTLE_SECONDS)
    click(world, *hotbar(origin, 0))
    click(world, *slot_at(origin, SECONDARY_AT))
    expect("dirt refused by the secondary slot", carried(world) is not None, True)
    click(world, *hotbar(origin, 0))
    click(world, *hotbar(origin, 1))
    click(world, *slot_at(origin, SECONDARY_AT))
    expect("an ingot left the cursor", carried(world), None)
    nbt = text(world, f"data get block {x} {Y} {z}")
    expect("the ingots are in the port's slot 5", "Slot: 5b" in nbt, True)
    world.command(f"data modify block {x} {Y} {z} chemical_tanks[0].stored.amount set value 5L")
    world.command("tick step 1")
    time.sleep(SETTLE_SECONDS)
    nbt = text(world, f"data get block {x} {Y} {z}")
    held = int(re.search(r"chemical_tanks: \[\{container: 0b, stored: \{amount: (\d+)L", nbt).group(1))
    expect("the ingot's 200 mB", held, 5 + 200)


def run(world, art: Path, textures: Path, folder: Path) -> None:
    world.start()
    world.command("forceload add 0 -16 16 16")
    time.sleep(SETTLE_SECONDS)
    x, z = 0, 0
    world.command(f"setblock {x} {Y - 1} {z - 1} minecraft:stone")
    world.command(f"tp @s {x} {Y} {z - 1}")
    time.sleep(SETTLE_SECONDS)
    # Waiting on a redstone signal, so that its values hold still for the screenshots.
    state = f'{SIDES},control_type:"high",energy:{ENERGY},progress:{PROGRESS},{TANK % OSMIUM},Items:[{DUST}]'
    world.command(f"setblock {x} {Y} {z} {COMPRESSOR}{{{state}}}")
    world.command("tick freeze")
    time.sleep(SETTLE_SECONDS)
    world.ctl("interact", x, Y, z)
    time.sleep(SETTLE_SECONDS)
    begin_checks()
    origin = origin_of(world)
    gui_width = world.ctl("ui")["gui_size"][0]
    scale = round(shot(world, folder / "scale.png", origin, 1).image.width / gui_width)
    world.command("tick step 1")
    time.sleep(SETTLE_SECONDS)
    screen = shot(world, folder / "compressor.png", origin, scale)
    check_art(screen, art)
    check_tab_tints(screen, art)
    nbt = text(world, f"data get block {x} {Y} {z}")
    check_progress(screen, art, int(re.search(r"progress: (\d+)", nbt).group(1)))
    gas = Image(textures / "mek_liquid/liquid.png")
    check_chemical_bar(screen, gas, int(re.search(r"stored: \{amount: (\d+)L", nbt).group(1)))
    check_power(screen, art, int(re.search(r"\benergy: (\d+)", nbt).group(1)))

    click(world, origin[0] + 80, origin[1] + 12)
    base = shot(world, folder / "no_hover.png", origin, scale)
    bar = oxidizer.tooltip_box(world, folder, base, origin, scale, (BAR_AT[0] + 4, BAR_AT[1] + 6), "bar")
    if bar[2] < oxidizer.TOOLTIP_PIXELS:
        raise TestFailure(f"no tooltip over the chemical bar: {bar}")
    # This bar's tooltip opens past the panel's right edge, where `tooltip_box` doesn't look.
    click(world, origin[0] + POWER_AT[0] + 3, origin[1] + POWER_AT[1] + 20)
    hover = shot(world, folder / "hover_power.png", origin, scale)
    left, top = int(origin[0] * scale), int(origin[1] * scale)
    changed = sum(
        hover.image.pixel(px, py) != base.image.pixel(px, py)
        for py in range(top, top + oxidizer.PANEL[1] * scale)
        for px in range(left + oxidizer.PANEL[0] * scale, min(hover.image.width, left + (oxidizer.PANEL[0] + 60) * scale))
    )
    if changed < oxidizer.TOOLTIP_PIXELS:
        raise TestFailure(f"no tooltip over the power bar: {changed} pixels")
    check_secondary_slot(world, origin, x, z)
    oxidizer.check_window(world, origin, scale, art, x, z, folder)
    world.command("tick unfreeze")
    world.ctl("close")
    world.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--art", type=Path, required=True)
    args = parser.parse_args()
    art = args.art.resolve()
    textures = art.parent.parent

    def make(folder: Path):
        world = SinglePlayer(folder, args.engine.resolve(), {})
        install_content(world.content_dir, WORK / "check/carry", WORK / "check-generators/carry")
        return world

    return run_test(make, lambda world: run(world, art, textures, world.folder))


if __name__ == "__main__":
    sys.exit(main())
