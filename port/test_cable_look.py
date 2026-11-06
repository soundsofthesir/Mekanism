#!/usr/bin/env python3
"""The Universal Cable drawn from Mekanism's OBJ model and textures, read back from screenshots.

    python3 port/test_cable_look.py --engine port/.work/machine-export/horizon-engine --art upstream/src/main/resources/assets/mekanism/textures [--screenshot FILE]

There is no picture of the real mod to compare with, because a Java client is not set up. A straight
down view gives the cable's size on screen: the OBJ's cross section is 6 of 16 of a block wide.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from horizon_driver import SinglePlayer, TestFailure, install_content
from png_tools import Image

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
CABLE = "mekanism:basic_universal_cable"
CAMERA_HEIGHT = 2.5
Y = 200
SETTLE_SECONDS = 1.5
# `transmitter_small.obj.mek`: 0.3125 to 0.6875 of a block. The plain model before it was 4/16.
SECTION = 6 / 16
SECTION_TOLERANCE = 0.03
# Three cables in a row end at their centres' outer faces: 1 + 2 x (1 - 0.3125) blocks.
RUN_LENGTH = 2.375
EDGE_STEP = 90
# `CableTier.BASIC`.
CABLE_CAPACITY = 8000
MIN_CHANGE = 12
MIN_CHANGED_PIXELS = 200
MAX_DRAINED_PIXELS = 20
DRAIN_SECONDS = 3
CUBE = "mekanism:basic_energy_cube"
PLATE = "minecraft:white_concrete"
CLOSE_TO_ART = 14
# At least this share of the cable's pixels should have a colour from its two textures.
MIN_ART_SHARE = 0.5
CABLE_ART = ("block/models/multipart/basic_universal_cable.png", "block/models/multipart/basic_universal_cable_vertical.png")


def near(a, b, tolerance: int) -> bool:
    return all(abs(x - y) <= tolerance for x, y in zip(a[:3], b[:3]))


def first_edge(pixels: list) -> int:
    """How far along a line the first sharp change is. The plate's own shading changes slowly."""
    for at in range(1, len(pixels)):
        if sum(abs(a - b) for a, b in zip(pixels[at - 1][:3], pixels[at][:3])) > EDGE_STEP:
            return at
    raise TestFailure("no edge on a line through the picture")


def box(image: Image) -> tuple[int, int, int, int]:
    """Where the cable is: left, top, width and height, from the lines through the picture's middle."""
    middle_x, middle_y = image.width // 2, image.height // 2
    row = [image.pixel(x, middle_y) for x in range(image.width)]
    column = [image.pixel(middle_x, y) for y in range(image.height)]
    left, right = first_edge(row), first_edge(row[::-1])
    top, bottom = first_edge(column), first_edge(column[::-1])
    return left, top, image.width - left - right, image.height - top - bottom


def art_share(image: Image, area, art: Path) -> float:
    colours = set()
    for name in CABLE_ART:
        texture = Image(art / name)
        for y in range(texture.height):
            for x in range(texture.width):
                colours.add(texture.pixel(x, y)[:3])
    left, top, width, height = area
    cells = [(left + x, top + y) for y in range(height) for x in range(width)]
    hits = sum(any(near(image.pixel(*cell), colour, CLOSE_TO_ART) for colour in colours) for cell in cells)
    return hits / len(cells)


def picture(world, path: Path) -> Image:
    time.sleep(SETTLE_SECONDS)
    world.ctl("screenshot", path)
    time.sleep(SETTLE_SECONDS)
    return Image(path)


def run(world, folder: Path, art: Path, screenshot: Path | None) -> None:
    world.start()
    # Chat over the middle of the picture would look like part of the cable.
    world.command("gamerule send_command_feedback false")
    world.command("forceload add -16 -16 16 16")
    world.command("time set noon")
    world.command("gamemode spectator")
    world.command(f"tp @s 0.5 {Y + CAMERA_HEIGHT} 0.5")
    world.command(f"fill -12 {Y - 2} -12 12 {Y - 2} 12 {PLATE}")
    world.command(f"setblock 0 {Y} 0 {CABLE}")
    world.command(f"setblock -1 {Y} 0 {CABLE}")
    world.command(f"setblock 1 {Y} 0 {CABLE}")
    world.command("tick freeze")
    world.ctl("look", 0, 90)
    plain = picture(world, folder / "joined.png")
    if screenshot:
        shutil.copy(folder / "joined.png", screenshot)
    area = box(plain)
    width, height = area[2], area[3]
    ratio = height / width * RUN_LENGTH
    print(f"  a straight run of 3 from above: {width} by {height} pixels")
    print(f"  the section against a block: {ratio:.3f}")
    if abs(ratio - SECTION) > SECTION_TOLERANCE:
        raise TestFailure(f"the section's share of a block is {ratio:.3f}, not near {SECTION}")
    share = art_share(plain, area, art)
    print(f"  pixels with a colour from the cable's textures: {share:.2f}")
    if share < MIN_ART_SHARE:
        raise TestFailure(f"only {share:.2f} of the cable's pixels look like its textures")
    # The energy contents show through the side texture's window, as the block's update gives them.
    world.command("tick unfreeze")
    for x in (-1, 0, 1):
        world.command(f"setblock {x} {Y} 0 air")
    for x in (-1, 0, 1):
        world.command(f"setblock {x} {Y} 0 {CABLE}{{energy:{CABLE_CAPACITY}}}")
    world.command("tick freeze")
    world.ctl("look", 0, 90)
    charged = picture(world, folder / "charged.png")
    if screenshot:
        shutil.copy(folder / "charged.png", screenshot.with_name("cable_charged.png"))
    left, top, width, height = area
    changed = sum(
        not near(charged.pixel(left + x, top + y), plain.pixel(left + x, top + y), MIN_CHANGE)
        for y in range(height)
        for x in range(width)
    )
    print(f"  pixels changed by holding energy: {changed} of {width * height}")
    if changed < MIN_CHANGED_PIXELS:
        raise TestFailure("what the cable holds doesn't change how it looks")
    # A cube at the end drains them with no block changing, so the update has to come from the network.
    world.command("tick unfreeze")
    world.command(f"setblock 2 {Y} 0 {CUBE}")
    time.sleep(DRAIN_SECONDS)
    world.command("tick freeze")
    world.ctl("look", 0, 90)
    drained = picture(world, folder / "drained.png")
    # The middle cable's own part of the run: the same as before it held anything.
    block_width = width / RUN_LENGTH
    middle_left = int(left + width / 2 - block_width / 2) + 2
    still_lit = sum(
        not near(drained.pixel(middle_left + x, top + y), plain.pixel(middle_left + x, top + y), MIN_CHANGE)
        for y in range(height)
        for x in range(int(block_width) - 4)
    )
    print(f"  pixels of the middle cable unlike its empty look after draining: {still_lit}")
    if still_lit > MAX_DRAINED_PIXELS:
        raise TestFailure("a drained cable still looks charged")
    world.command("gamerule send_command_feedback true")
    saved = " ".join(world.command(f"data get block 0 {Y} 0"))
    print(f"  the middle cable afterwards: {saved[-16:]}")
    if "energy: 0L" not in saved:
        raise TestFailure(f"the cube did not drain the cables: {saved}")
    world.command("tick unfreeze")
    world.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--art", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(dir=WORK))
    world = SinglePlayer(folder, args.engine.resolve(), {})
    install_content(world.content_dir, WORK / "check/carry", WORK / "check-generators/carry")
    try:
        run(world, folder, args.art.resolve(), args.screenshot.resolve() if args.screenshot else None)
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
