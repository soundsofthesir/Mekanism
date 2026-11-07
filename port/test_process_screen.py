#!/usr/bin/env python3
"""Compares each `process_table.rs` machine's screen with Mekanism's art at the positions in its source,
and plays through its extra slot and side config window.

The positions here come from each machine's `Gui*` and `TileEntity*` classes.
"""

import argparse
import math
import sys
import re
import time
from pathlib import Path
from typing import NamedTuple

import test_gui as gui
import test_oxidizer_screen as oxidizer
from horizon_driver import SinglePlayer, TestFailure, begin_checks, install_content, run_test
from png_tools import Image
from test_gui import MAX_CHANNEL_DIFFERENCE, SETTLE_SECONDS, Screen, check_tab_tints, click, expect, shot, text
from test_upgrades import carried, hotbar

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
Y = 200
SLOT_MIDDLE = 8
PROGRESS = 100
TICKS = 200
ENERGY = 15
TOAST_SECONDS = 30
POWER_INSIDE = (4, 52)
SIDES = "component_config:{config0:[I;1,1,1,1,1,1],config2:[I;1,1,1,1,1,1],config3:[I;1,1,1,1,1,1]}"


class Spec(NamedTuple):
    block: str
    input_at: tuple[int, int]
    output_at: tuple[int, int]
    energy_at: tuple[int, int]
    extra_at: tuple[int, int]
    extra_art: str | None
    frame: tuple[int, int, int, int] | None
    arrow_at: tuple[int, int] | None
    progress_at: tuple[int, int]
    progress_art: str
    progress_size: tuple[int, int]
    bar_at: tuple[int, int] | None
    bar_inside: tuple[int, int]
    power_at: tuple[int, int]
    dump_at: tuple[int, int] | None
    capacity: int
    input_item: str
    tank: int = 0
    chemical: str = ""
    stored: int = 0
    tint: tuple[int, int, int] = (0, 0, 0)
    tile: str = ""
    # What the extra slot takes: none for an output slot.
    extra_item: str | None = None


LIQUID = "mek_liquid/liquid.png"
ADVANCED = {
    "input_at": (64, 17), "output_at": (116, 35), "energy_at": (39, 35), "extra_at": (64, 53),
    "extra_art": "slot/extra", "frame": None, "arrow_at": None, "progress_at": (86, 38), "progress_art": "bar",
    "progress_size": (25, 9), "bar_at": (68, 36), "bar_inside": (6, 12), "power_at": (164, 16), "dump_at": None,
    "tank": 210, "stored": 150, "tile": LIQUID,
}
SPECS = (
    Spec(block="mekanism:combiner", **{**ADVANCED, "arrow_at": (68, 38), "bar_at": None, "bar_inside": (0, 0), "power_at": (164, 15),
         "tank": 0, "stored": 0, "tile": ""}, capacity=20, input_item="mekanism:dust_diamond", extra_item="minecraft:cobblestone"),
    Spec(block="mekanism:precision_sawmill", input_at=(56, 17), output_at=(116, 35), energy_at=(56, 53), extra_at=(132, 35), extra_art=None,
         frame=(111, 30, 42, 26), arrow_at=(60, 38), progress_at=(78, 38), progress_art="bar", progress_size=(25, 9), bar_at=None,
         bar_inside=(0, 0), power_at=(164, 15), dump_at=None, capacity=20, input_item="minecraft:oak_planks"),
    # `data/mekanism/mekanism/chemical/oxygen.json`.
    Spec(block="mekanism:purification_chamber", **ADVANCED, capacity=40, input_item="mekanism:osmium_ore", chemical="mekanism:oxygen",
         tint=(0x6C, 0xE2, 0xFF), extra_item="minecraft:flint"),
    # `hydrogen_chloride.json`.
    Spec(block="mekanism:chemical_injection_chamber", **ADVANCED, capacity=60, input_item="mekanism:osmium_ore",
         chemical="mekanism:hydrogen_chloride", tint=(0xA8, 0xF1, 0xE9), extra_item="mekanism:salt"),
    # `tin.json`, whose icon is `mek_chemical/infuse_type/base`.
    Spec(block="mekanism:metallurgic_infuser", input_at=(51, 43), output_at=(109, 43), energy_at=(143, 35), extra_at=(17, 35),
         extra_art="slot/extra", frame=None, arrow_at=None, progress_at=(72, 47), progress_art="right", progress_size=(32, 8),
         bar_at=(7, 15), bar_inside=(4, 52), power_at=(164, 15), dump_at=(16, 59), capacity=20, input_item="mekanism:dust_copper",
         tank=1000, chemical="mekanism:tin", stored=700, tint=(0xCC, 0xCC, 0xD9), tile="mek_chemical/infuse_type/base.png",
         extra_item="mekanism:dust_tin"),
)


def origin_of(world) -> tuple[float, float]:
    ui = world.ctl("ui")
    width, height = ui["gui_size"]
    return (width - oxidizer.PANEL[0]) // 2, (height - oxidizer.PANEL[1]) // 2


def check_art(screen: Screen, art: Path, s: Spec) -> None:
    corner = lambda at: (at[0] - 1, at[1] - 1)
    parts = [("input slot", "slot/input", corner(s.input_at), (0, 0, 18, 1)), ("energy slot", "slot/power", corner(s.energy_at), None), ("inventory slot", "slot/normal", (7, 83), None)]
    if s.extra_art:
        parts.append(("extra slot", s.extra_art, corner(s.extra_at), (0, 0, 18, 1)))
    if s.frame is None:
        parts.append(("output slot", "slot/output", corner(s.output_at), None))
    if s.arrow_at:
        parts.append(("up arrow", "arrow/up", s.arrow_at, None))
    if s.dump_at:
        parts.append(("dump button", "button/dump", s.dump_at, None))
    for name, sprite, at, part in parts:
        expect(f"{s.block} {name}: pixels unlike {sprite}", screen.matches_art(Image(art / f"{sprite}.png"), at, part), 0)
    if s.frame:
        output = Image(art / "slot/output.png")
        x, y, w, h = s.frame
        expect(f"{s.block} wide output's corner", screen.matches_art(output, (x, y), (0, 0, 1, 1)), 0)
        expect(f"{s.block} wide output's far corner", screen.matches_art(output, (x + w - 1, y + h - 1), (17, 17, 1, 1)), 0)
    base = Image(art / "bar/base.png")
    expect(f"{s.block} power bar's frame corner", screen.matches_art(base, s.power_at, (0, 0, 1, 1)), 0)
    if s.bar_at:
        expect(f"{s.block} chemical bar's frame corner", screen.matches_art(base, s.bar_at, (0, 0, 1, 1)), 0)


def check_progress(screen: Screen, art: Path, s: Spec, progress: int) -> None:
    """`GuiProgress`: only `ProgressType.BAR` starts a pixel in on each side."""
    inset = 1 if s.progress_art == "bar" else 0
    width, height = s.progress_size
    filled = math.ceil(progress / TICKS * (width - 2 * inset - 1)) + 1
    full = Image(art / f"progress/{s.progress_art}/full.png")
    empty = Image(art / f"progress/{s.progress_art}/empty.png")
    x, y = s.progress_at
    expect(f"{s.block} filled part of the progress", screen.matches_art(full, (x + inset, y), (inset, 0, filled, height)), 0)
    rest = (inset + filled, 0, width - 2 * inset - filled, height)
    expect(f"{s.block} empty part of the progress", screen.matches_art(empty, (x + inset + filled, y), rest), 0)


def check_chemical_bar(screen: Screen, textures: Path, s: Spec) -> None:
    """Each filled row is the tile tinted, and each empty one isn't."""
    tile = Image(textures / s.tile)
    pixels = {tile.pixel(x, y) for x in range(tile.width) for y in range(tile.height)}
    background = screen.at(s.bar_at[0] + 1 + s.bar_inside[0] / 2, s.bar_at[1] + 1.5)[:3]

    def is_gas(pixel: tuple) -> bool:
        """The tile is partly see-through, so a filled row is it tinted over the bar's background."""
        for *colour, alpha in pixels:
            wanted = [c * t / 255 * alpha / 255 + b * (1 - alpha / 255) for c, t, b in zip(colour, s.tint, background)]
            if all(abs(a - w) <= MAX_CHANNEL_DIFFERENCE + 1 for a, w in zip(pixel, wanted)):
                return True
        return False

    inside = s.bar_inside
    filled = math.ceil(s.stored / s.tank * (inside[1] - 1)) + 1
    x = s.bar_at[0] + 1 + inside[0] / 2
    rows = [screen.at(x, s.bar_at[1] + 1 + row + 0.5)[:3] for row in range(inside[1])]
    above, below = rows[: inside[1] - filled], rows[inside[1] - filled :]
    expect(f"{s.block} chemical bar: rows above the gas that are gas", sum(is_gas(p) for p in above), 0)
    expect(f"{s.block} chemical bar: rows of gas that aren't", sum(not is_gas(p) for p in below), 0)


def check_power(screen: Screen, art: Path, s: Spec) -> None:
    filled = math.ceil(ENERGY / s.capacity * (POWER_INSIDE[1] - 1)) + 1
    tile = Image(art / "bar/vertical_power.png")
    colours = {tile.pixel(x, y)[:3] for x in range(tile.width) for y in range(tile.height)}
    x = s.power_at[0] + 1 + POWER_INSIDE[0] / 2
    bottom = s.power_at[1] + 1 + POWER_INSIDE[1]
    near = lambda pixel: any(all(abs(a - b) <= MAX_CHANNEL_DIFFERENCE for a, b in zip(pixel, each)) for each in colours)
    expect(f"{s.block} the power bar's {filled} filled rows, wrong", sum(not near(screen.at(x, bottom - row - 0.5)[:3]) for row in range(filled)), 0)
    expect(f"{s.block} the power bar stops there", near(screen.at(x, bottom - filled - 0.5)[:3]), False)


def check_slots(world, origin, s: Spec, x: int, z: int) -> None:
    """The extra slot refuses bedrock, which no recipe names, and takes what its recipes or tags name. An output slot takes nothing."""
    at = lambda slot: (origin[0] + slot[0] + SLOT_MIDDLE, origin[1] + slot[1] + SLOT_MIDDLE)
    world.command("item replace entity @s hotbar.0 with minecraft:bedrock 4")
    world.command(f"item replace entity @s hotbar.1 with {s.extra_item or 'minecraft:stone'} 2")
    time.sleep(SETTLE_SECONDS)
    click(world, *hotbar(origin, 0))
    click(world, *at(s.extra_at))
    expect(f"{s.block} bedrock refused by the extra slot", carried(world) is not None, True)
    click(world, *hotbar(origin, 0))
    click(world, *hotbar(origin, 1))
    click(world, *at(s.extra_at))
    if s.extra_item:
        expect(f"{s.block} {s.extra_item} left the cursor", carried(world), None)
        expect(f"{s.block} it is in slot 5", "Slot: 5b" in text(world, f"data get block {x} {Y} {z}"), True)
    else:
        expect(f"{s.block} the output slot refused it", carried(world) is not None, True)
        click(world, *hotbar(origin, 1))


def check_one(world, s: Spec, art: Path, textures: Path, folder: Path, x: int, z: int) -> None:
    world.command("tick unfreeze")
    # A machine's slot test leaves items in the inventory, over the slot `check_art` compares.
    world.command("clear @s")
    world.command(f"tp @s {x} {Y} {z - 1}")
    tank = f',chemical_tanks:[{{container:0b,stored:{{amount:{s.stored}L,type:"{s.chemical}"}}}}]' if s.tank else ""
    state = f'{SIDES},control_type:"high",energy:{ENERGY},progress:{PROGRESS}{tank},Items:[{{Slot:0b,id:"{s.input_item}",count:8}}]'
    world.command(f"setblock {x} {Y} {z} {s.block}{{{state}}}")
    # The extra slot's table fills on the machine's first tick.
    time.sleep(SETTLE_SECONDS)
    world.command("tick freeze")
    time.sleep(SETTLE_SECONDS)
    world.ctl("interact", x, Y, z)
    time.sleep(SETTLE_SECONDS)
    origin = origin_of(world)
    gui_width = world.ctl("ui")["gui_size"][0]
    name = s.block.split(":")[1]
    scale = round(shot(world, folder / "scale.png", origin, 1).image.width / gui_width)
    world.command("tick step 1")
    time.sleep(SETTLE_SECONDS)
    screen = shot(world, folder / f"{name}.png", origin, scale)
    check_art(screen, art, s)
    check_tab_tints(screen, art)
    nbt = text(world, f"data get block {x} {Y} {z}")
    check_progress(screen, art, s, int(re.search(r"progress: (\d+)", nbt).group(1)))
    check_power(screen, art, s)
    click(world, origin[0] + 100, origin[1] + 8)
    base = shot(world, folder / f"{name}_no_hover.png", origin, scale)
    if s.bar_at:
        check_chemical_bar(screen, textures, s)
        box = oxidizer.tooltip_box(world, folder, base, origin, scale, (s.bar_at[0] + 3, s.bar_at[1] + 6), f"{name}_bar")
        if box[2] < oxidizer.TOOLTIP_PIXELS:
            raise TestFailure(f"{s.block}: no tooltip over the chemical bar: {box}")
    check_slots(world, origin, s, x, z)
    if s.bar_at:
        oxidizer.check_window(world, origin, scale, art, x, z, folder)
    else:
        # Items given above earn advancements, whose toasts cover the window's eject icon.
        time.sleep(TOAST_SECONDS)
        gui.check_window(world, origin, scale, art, x, z, folder, s.input_at)
    world.ctl("close")
    time.sleep(SETTLE_SECONDS)


def run(world, art: Path, textures: Path, folder: Path) -> None:
    world.start()
    world.command("forceload add 0 -16 32 16")
    world.command("gamerule doDaylightCycle false")
    time.sleep(SETTLE_SECONDS)
    begin_checks()
    for index, s in enumerate(SPECS):
        x, z = index * 3, 0
        world.command(f"setblock {x} {Y - 1} {z - 1} minecraft:stone")
        world.command("tick unfreeze")
        check_one(world, s, art, textures, folder, x, z)
        print(f"  {s.block}: art, bars, slots and side window match", flush=True)
    world.command("tick unfreeze")
    world.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--art", type=Path, required=True)
    args = parser.parse_args()
    textures = args.art.parent.parent

    def make(folder: Path):
        world = SinglePlayer(folder, args.engine.resolve(), {})
        install_content(world.content_dir, WORK / "check/carry", WORK / "check-generators/carry")
        return world

    folder = WORK / "process_screen"
    folder.mkdir(exist_ok=True)
    return run_test(make, lambda world: run(world, args.art, textures, folder))


if __name__ == "__main__":
    sys.exit(main())
