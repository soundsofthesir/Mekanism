#!/usr/bin/env python3
"""A player's clicks on a machine's redstone tab and upgrade window, ending in the states the feature
recordings cover. What follows each click is compared with that recording, row by row.

    python3 port/test_upgrades.py --engine port/.work/machine-export/horizon-engine --art upstream/src/main/resources/assets/mekanism/textures/gui/sprites
"""

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

import java_reference_features as java
import test_features as features
from horizon_driver import SinglePlayer, TestFailure, begin_checks, install_content, run_test
from png_tools import Image
from test_gui import CHAMBER, SETTLE_SECONDS, SIDES, TAB_MIDDLE, Y, click, expect, origin_of, shot, text

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
REFERENCE = HERE / "reference"
# `GuiInsetElement` on the screen's right edge, and `GuiUpgradeWindow`'s elements.
UPGRADE_TAB = (179, 10)
REDSTONE_TAB = (179, 141)
WINDOW = (-11, 15)
INPUT_FRAME = (175, 18)
OUTPUT_FRAME = (175, 72)
# Each is the corner `in_window` adds 9 to: the first list row, and the Uninstall button.
LIST_ROW = (20, 14)
UNINSTALL = (134, 51)
CLOSE = (10, 10)
INSTALLING_ARROW = (176, 37)
UNINSTALLING_ARROW = (176, 58)
HOTBAR_FIRST = (8, 142)
SLOT_MIDDLE = 8
SPEED_STACK = '{Slot:0b,id:"mekanism:upgrade",count:4,components:{"mekanism:upgrade_type":"mekanism:speed"}}'
INSTALL_WAIT_SECONDS = 5


def tab(world, origin, at, button: str = "") -> None:
    click(world, origin[0] + at[0] + TAB_MIDDLE, origin[1] + at[1] + TAB_MIDDLE, button)


def control(world) -> str:
    return re.search(r'control_type: "(\w+)"', text(world, f"data get block 0 {Y} 0")).group(1)


def installed(world) -> int:
    found = re.search(r'"mekanism:speed": (\d+)', text(world, f"data get block 0 {Y} 0"))
    return int(found.group(1)) if found else 0


def in_window(origin, frame) -> tuple[float, float]:
    return origin[0] + WINDOW[0] + frame[0] + 9, origin[1] + WINDOW[1] + frame[1] + 9


def widget_at(world, slot: int) -> list[float]:
    for widget in world.ctl("ui")["widgets"]:
        if widget.get("id") == f"slot-{slot}":
            return widget["bounds"][:2]
    return []


def hotbar(origin, index: int) -> tuple[float, float]:
    return origin[0] + HOTBAR_FIRST[0] + 18 * index + SLOT_MIDDLE, origin[1] + HOTBAR_FIRST[1] + SLOT_MIDDLE


def carried(world):
    return world.ctl("screen").get("carried")


def wait_installed(world, count: int) -> None:
    deadline = time.time() + INSTALL_WAIT_SECONDS
    while time.time() < deadline and installed(world) != count:
        time.sleep(0.1)
    expect("speed upgrades installed", installed(world), count)


def compare(world, name: str, changes=()) -> None:
    """The recording's rows, from the state the player's clicks reached."""
    expected = (REFERENCE / f"{name}.tsv").read_text().splitlines()
    plan = dict(changes)
    for line in expected[2:]:
        wanted = line.split("\t")
        tick = int(wanted[0])
        if tick in plan:
            world.command(features.here_command(plan[tick]))
        features.step(world)
        got = features.row(world, wanted[0], False)
        if got != wanted:
            raise TestFailure(f"{name} tick {tick} after a player's clicks: got {got} expected {wanted}")
    print(f"  {name}: {len(expected) - 2} rows match after a player's clicks")


def supply(world, ores: str = '{Slot:0b,id:"minecraft:iron_ore",count:16}') -> None:
    """The recordings' machine contents and the cube beside it, placed while frozen."""
    world.command(f"data modify block 0 {Y} 0 Items set value [{ores}]")
    world.command(f"setblock 0 {Y} 1 {features.here_format(java.CUBE_FULL)}")


def check_redstone(world, origin, art: Path, folder: Path, scale: int) -> None:
    expect("control before a click", "control_type" in text(world, f"data get block 0 {Y} 0") and control(world), False)
    for mode in ("high", "low", "disabled"):
        tab(world, origin, REDSTONE_TAB)
        expect("control after a left click", control(world), mode)
    tab(world, origin, REDSTONE_TAB, "right")
    expect("control after a right click", control(world), "low")
    tab(world, origin, REDSTONE_TAB, "right")
    expect("control back at high", control(world), "high")
    screen = shot(world, folder / "redstone.png", origin, scale)
    icon = Image(art / "redstone_control/high.png")
    expect("redstone tab's icon: pixels unlike redstone_control/high", screen.matches_art(icon, REDSTONE_TAB), 0)


def check_window(world, origin, art: Path, folder: Path, scale: int) -> None:
    expect("upgrade slot while closed", widget_at(world, 303)[0] < 0, True)
    tab(world, origin, UPGRADE_TAB)
    bounds = widget_at(world, 303)
    expect("upgrade slot's place", [round(bounds[0] - origin[0]), round(bounds[1] - origin[1])], [WINDOW[0] + INPUT_FRAME[0] + 1, WINDOW[1] + INPUT_FRAME[1] + 1])
    screen = shot(world, folder / "upgrades.png", origin, scale)
    shutil.copy(folder / "upgrades.png", WORK / "upgrades.png")
    corner = lambda at: (WINDOW[0] + at[0], WINDOW[1] + at[1])
    for sprite, at in (
        ("progress/installing/empty", INSTALLING_ARROW),
        ("progress/uninstalling/empty", UNINSTALLING_ARROW),
        ("slot/normal", INPUT_FRAME),
        ("slot/normal", OUTPUT_FRAME),
    ):
        expect(f"window's {sprite}: unlike pixels", screen.matches_art(Image(art / f"{sprite}.png"), corner(at)), 0)

    # What the slot refuses stays on the cursor.
    click(world, *hotbar(origin, 1))
    expect("dirt picked up", carried(world) is not None, True)
    click(world, *in_window(origin, INPUT_FRAME))
    expect("dirt refused by the upgrade slot", carried(world) is not None, True)
    click(world, *hotbar(origin, 1))

    click(world, *hotbar(origin, 0))
    expect("upgrades picked up", carried(world) is not None, True)
    click(world, *in_window(origin, INPUT_FRAME))
    expect("upgrades left the cursor", carried(world), None)
    wait_installed(world, 4)
    nbt = text(world, f"data get block 0 {Y} 0")
    expect("nothing left in the upgrade slot", "Slot: 3b" in nbt, False)

    click(world, *in_window(origin, LIST_ROW))
    click(world, *in_window(origin, UNINSTALL))
    expect("one uninstalled", installed(world), 3)
    expect("it's in the output slot", features.slot_of(text(world, f"data get block 0 {Y} 0"), 4), "mekanism:upgradex1")
    click(world, *in_window(origin, OUTPUT_FRAME))
    expect("taken from the output slot", carried(world) is not None, True)
    click(world, *in_window(origin, INPUT_FRAME))
    wait_installed(world, 4)
    click(world, origin[0] + WINDOW[0] + CLOSE[0], origin[1] + WINDOW[1] + CLOSE[1])
    expect("upgrade slot closed again", widget_at(world, 303)[0] < 0, True)


def run(world, art: Path, folder: Path) -> None:
    world.start()
    world.command("forceload add 0 -16 16 16")
    time.sleep(SETTLE_SECONDS)
    world.command(f"setblock 0 {Y - 1} -1 minecraft:stone")
    world.command(f"tp @s 0 {Y} -1")
    time.sleep(SETTLE_SECONDS)
    world.command(f"setblock 0 {Y} 0 {CHAMBER}{{{SIDES}}}")
    # `give` has no parser for this component, though a chest's data and a slot copy keep it.
    world.command(f"setblock 2 {Y} 2 minecraft:chest{{Items:[{SPEED_STACK}]}}")
    world.command(f"item replace entity @s hotbar.0 from block 2 {Y} 2 container.0")
    world.command("item replace entity @s hotbar.1 with minecraft:dirt 4")
    time.sleep(SETTLE_SECONDS)
    world.ctl("interact", 0, Y, 0)
    time.sleep(SETTLE_SECONDS)
    begin_checks()
    origin = origin_of(world)
    gui_width = world.ctl("ui")["gui_size"][0]
    scale = round(shot(world, folder / "scale.png", origin, 1).image.width / gui_width)

    check_redstone(world, origin, art, folder, scale)
    world.command("tick freeze")
    supply(world)
    compare(world, "redstone_high", next(each for each in java.SCENARIOS if each.name == "redstone_high").changes)
    world.command("tick unfreeze")
    world.command(f"setblock 1 {Y} 0 air")
    world.command(f"setblock 0 {Y} 1 air")
    world.command(f"data modify block 0 {Y} 0 Items set value []")
    world.command(f'data modify block 0 {Y} 0 control_type set value "disabled"')
    world.command(f"data modify block 0 {Y} 0 progress set value 0")
    world.command(f"data modify block 0 {Y} 0 energy set value 0")

    check_window(world, origin, art, folder, scale)
    world.command("tick freeze")
    world.command(f"data modify block 0 {Y} 0 energy set value 0")
    supply(world)
    compare(world, "upgrade_run_speed4")
    world.command("tick unfreeze")
    world.ctl("close")
    world.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--art", type=Path, required=True)
    args = parser.parse_args()
    art = args.art.resolve()

    def make(folder: Path):
        world = SinglePlayer(folder, args.engine.resolve(), {})
        # The tutorial's toast would cover the window's right side.
        (world.game_dir / "options.txt").write_text("tutorialStep:none\n")
        install_content(world.content_dir, WORK / "check/carry", WORK / "check-generators/carry")
        return world

    return run_test(make, lambda world: run(world, art, world.folder))


if __name__ == "__main__":
    sys.exit(main())
