#!/usr/bin/env python3
"""Phase 1 test: Mekanism's carried content in a real Horizon world.

    python3 port/make_resource_jar.py upstream port/.work/mekanism-10.8.0-resources.jar
    horizon-port-pack check port/.work/mekanism-10.8.0-resources.jar port/.work/check
    python3 port/patch_worldgen.py port/.work/check/carry
    python3 port/test_phase1.py port/.work/check/carry

Checks that each ore generates, simple blocks place and survive a reload, the ore's loot table
works, and crafting and smelting recipes give what they should. The game is the installed Nightly,
with the mod switched on in a new world under port/.work/. The folder stays there on a failure.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

NIGHTLY = (
    Path.home() / "Library/Application Support/horizon-launcher/versions/nightly-2026-11-05-f319701"
)
WORK = Path(__file__).resolve().parent / ".work"
CTL = NIGHTLY / "horizon-ctl"
GAME = NIGHTLY / "horizon-client"
RESOURCES = NIGHTLY / ".local/horizon-client/26.3"

ORES = ("osmium", "tin", "lead", "uranium", "fluorite")
SCAN_CHUNK_RADIUS = 6
# One 16 x 16 column of this height is the most `horizon-ctl blocks` returns at once.
SCAN_Y = (-64, 63)
SIMPLE_BLOCKS = {
    (0, 200, 0): "mekanism:block_steel",
    (1, 200, 0): "mekanism:osmium_ore",
    (2, 200, 0): "mekanism:deepslate_tin_ore",
    (3, 200, 0): "mekanism:block_raw_uranium",
}
TABLE = (0, 200, 3)
TABLE_GRID_SIZE = 3
FURNACE = "0 200 5"
HAND_SLOT = 0
FIRST_GRID_SLOT = 100
RESULT_SLOT = 200
RING_OF_GRID = range(FIRST_GRID_SLOT, FIRST_GRID_SLOT + 9)
TIMEOUT_SECONDS = 120
SMELT_TIMEOUT_SECONDS = 30
SYNC_TIMEOUT_SECONDS = 5
# A click reaches the server a tick later, and the next click must see its result.
CLICK_SETTLE_SECONDS = 0.15


class TestFailure(Exception):
    pass


class World:
    def __init__(self, folder: Path, carry: Path) -> None:
        self.folder = folder
        self.socket = folder / "c.sock"
        self.game_dir = folder / "game"
        (self.game_dir / "horizon-mods").mkdir(parents=True)
        (folder / "home").mkdir()
        shutil.copytree(carry, self.game_dir / "horizon-mods/mekanism")
        (self.game_dir / "horizon-mods.txt").write_text("mod.mekanism:true\n")
        self.env = {
            **os.environ,
            "HORIZON_HOME": str(folder / "home"),
            "HORIZON_LAUNCHER_HOME": str(folder / "launcher"),
            "XDG_DATA_HOME": str(folder / "data"),
            "XDG_CONFIG_HOME": str(folder / "config"),
            "HORIZON_NO_AUDIO": "1",
            "HORIZON_LAUNCHER_NO_SELF_UPDATE": "1",
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
            "--game", GAME, "--resources", RESOURCES, "--game-dir", self.game_dir,
        )

    def stop(self) -> None:
        self.ctl("quit")
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while self.socket.exists() and time.monotonic() < deadline:
            time.sleep(0.2)

    def command(self, line: str) -> list[str]:
        return self.ctl("command", line).get("chat", [])

    def counts(self) -> dict[str, int]:
        return self.ctl("inventory").get("counts", {})


def check_features_run(world: World) -> None:
    log = (world.folder / "home/logs/latest.log").read_text()
    skipped = [line for line in log.splitlines() if "placed features cannot run" in line]
    if skipped:
        raise TestFailure(f"worldgen features skipped: {skipped}")


def check_ores(world: World) -> None:
    low, high = -SCAN_CHUNK_RADIUS, SCAN_CHUNK_RADIUS - 1
    world.command(f"forceload add {low * 16} {low * 16} {high * 16 + 15} {high * 16 + 15}")
    found = dict.fromkeys(ORES, 0)
    y_low, y_high = SCAN_Y
    for cx in range(low, high + 1):
        for cz in range(low, high + 1):
            box = (cx * 16, y_low, cz * 16, cx * 16 + 15, y_high, cz * 16 + 15)
            found = add_ores(found, loaded_counts(world, box))
    print(f"  ores in {(high - low + 1) ** 2} chunks: {found}")
    missing = [ore for ore, count in found.items() if count == 0]
    if missing:
        raise TestFailure(f"no {missing} generated")


def loaded_counts(world: World, box: tuple[int, ...]) -> dict[str, int]:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        blocks = world.ctl("blocks", *box).get("blocks", [])
        if blocks or time.monotonic() > deadline:
            return Counter(block for *_, block in blocks)
        time.sleep(0.5)


def add_ores(found: dict[str, int], counts: dict[str, int]) -> dict[str, int]:
    def in_chunk(ore: str) -> int:
        names = (f"mekanism:{ore}_ore", f"mekanism:deepslate_{ore}_ore")
        return sum(counts.get(name, 0) for name in names)

    return {ore: total + in_chunk(ore) for ore, total in found.items()}


def place_blocks(world: World) -> None:
    for (x, y, z), block in SIMPLE_BLOCKS.items():
        answer = world.command(f"setblock {x} {y} {z} {block}")
        if not any("Changed the block" in line for line in answer):
            raise TestFailure(f"setblock {block} answered {answer}")


def check_blocks_kept(world: World) -> None:
    for (x, y, z), block in SIMPLE_BLOCKS.items():
        answer = world.command(f"execute if block {x} {y} {z} {block}")
        if not any("Test passed" in line for line in answer):
            raise TestFailure(f"{block} at {x} {y} {z} was lost: {answer}")


def wait_for_counts(world: World, wanted: dict[str, int]) -> None:
    """Waits for the client's inventory, which reaches a server's change a tick or more later."""
    deadline = time.monotonic() + SYNC_TIMEOUT_SECONDS
    while True:
        counts = world.counts()
        if all(counts.get(item, 0) == count for item, count in wanted.items()):
            return
        if time.monotonic() > deadline:
            raise TestFailure(f"expected {wanted}, the inventory has {counts}")
        time.sleep(0.1)


def clear_inventory(world: World) -> None:
    world.command("clear @s")
    deadline = time.monotonic() + SYNC_TIMEOUT_SECONDS
    while world.counts():
        if time.monotonic() > deadline:
            raise TestFailure(f"the inventory did not clear: {world.counts()}")
        time.sleep(0.1)


def check_loot(world: World) -> None:
    clear_inventory(world)
    world.command("loot give @s loot mekanism:blocks/osmium_ore")
    wait_for_counts(world, {"mekanism:raw_osmium": 1})


def open_table(world: World) -> None:
    """Retries while the client's position lags a teleport, when the table is out of reach."""
    deadline = time.monotonic() + SYNC_TIMEOUT_SECONDS
    while True:
        try:
            world.ctl("interact", *TABLE)
        except TestFailure:
            if time.monotonic() > deadline:
                raise
        if world.ctl("screen").get("craft_size") == TABLE_GRID_SIZE:
            return
        if time.monotonic() > deadline:
            raise TestFailure("the crafting table did not open")
        time.sleep(0.2)


def click(world: World, *args: object) -> None:
    world.ctl("click-slot", *args)
    time.sleep(CLICK_SETTLE_SECONDS)


def craft(world: World, given: str, grid_slots: range, expected: str, count: int) -> None:
    clear_inventory(world)
    world.command(f"give @s {given} {len(grid_slots)}")
    wait_for_counts(world, {given: len(grid_slots)})
    # A command closes the screen, so the table opens again for each craft.
    open_table(world)
    click(world, HAND_SLOT)
    for slot in grid_slots:
        click(world, slot, "right")
    click(world, RESULT_SLOT)
    click(world, HAND_SLOT)
    world.ctl("close")
    wait_for_counts(world, {expected: count})
    print(f"  {len(grid_slots)} x {given} made {count} x {expected}")


def check_crafting(world: World) -> None:
    x, y, z = TABLE
    # Something to stand on: the player would fall out of the table's reach.
    world.command(f"setblock {x} {y} {z - 1} minecraft:stone")
    world.command(f"tp @s {x} {y + 1} {z - 1}")
    world.command(f"setblock {x} {y} {z} minecraft:crafting_table")
    # A shaped recipe with a `c:` tag key, a shapeless one, and an item a mod made.
    craft(world, "mekanism:ingot_osmium", RING_OF_GRID, "mekanism:block_osmium", 1)
    craft(world, "mekanism:ingot_osmium", range(FIRST_GRID_SLOT, FIRST_GRID_SLOT + 1),
          "mekanism:nugget_osmium", 9)
    craft(world, "mekanism:nugget_osmium", RING_OF_GRID, "mekanism:ingot_osmium", 1)


def check_smelting(world: World) -> None:
    world.command(f"setblock {FURNACE} minecraft:furnace")
    world.command(f"item replace block {FURNACE} container.0 with mekanism:raw_osmium")
    world.command(f"item replace block {FURNACE} container.1 with minecraft:coal")
    deadline = time.monotonic() + SMELT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        answer = " ".join(world.command(f"data get block {FURNACE} Items"))
        if re.search(r'id: "mekanism:ingot_osmium"', answer):
            print("  the furnace smelted raw osmium into an ingot")
            return
        time.sleep(1)
    raise TestFailure(f"no ingot from the furnace: {answer}")


def scenario(world: World) -> None:
    world.start()
    print("World generation:")
    check_features_run(world)
    check_ores(world)
    print("Blocks, loot and recipes:")
    place_blocks(world)
    check_loot(world)
    check_crafting(world)
    check_smelting(world)
    world.stop()
    world.start()
    print("After a reload:")
    check_blocks_kept(world)
    print(f"  {len(SIMPLE_BLOCKS)} blocks kept")
    world.stop()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    folder = Path(tempfile.mkdtemp(dir=WORK))
    world = World(folder, Path(sys.argv[1]).resolve())
    try:
        scenario(world)
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
