#!/usr/bin/env python3
"""Adds the menu types the machine mod opens to the carried mods.

Usage: add_machine_content.py MEKANISM_CARRY GENERATORS_CARRY
"""

import json
import sys
from pathlib import Path

MACHINES = ("enrichment_chamber", "crusher", "energized_smelter")
# Input, output, energy item. The output slot only gives.
MACHINE_MENU = {"slots": 3, "data_slots": 6, "results": [1]}
# The fuel slot. Lava, energy, temperature.
GENERATOR_MENU = {"slots": 1, "data_slots": 3}


CABLE_THICKNESS = 4
CABLE_TEXTURE = "mekanism:block/models/multipart/basic_universal_cable"
# Blocks a cable joins: everything with energy that is ported so far.
CABLE_JOINS = (
    "mekanism:basic_energy_cube",
    "mekanism:enrichment_chamber",
    "mekanism:crusher",
    "mekanism:energized_smelter",
    "mekanismgenerators:heat_generator",
)
SIDES = ("north", "south", "east", "west", "up", "down")


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def box_model(low: list[int], high: list[int]) -> dict:
    faces = {side: {"texture": "#cable"} for side in SIDES}
    return {
        "textures": {"particle": CABLE_TEXTURE, "cable": CABLE_TEXTURE},
        "elements": [{"from": low, "to": high, "faces": faces}],
    }


def arm_box(side: str) -> tuple[list[int], list[int]]:
    near, far = 8 - CABLE_THICKNESS // 2, 8 + CABLE_THICKNESS // 2
    return {
        "north": ([near, near, 0], [far, far, near]),
        "south": ([near, near, far], [far, far, 16]),
        "west": ([0, near, near], [near, far, far]),
        "east": ([far, near, near], [16, far, far]),
        "down": ([near, 0, near], [far, near, far]),
        "up": ([near, far, near], [far, 16, far]),
    }[side]


def add_cable(carry: Path) -> None:
    """The real cable is an OBJ model with Java geometry. This is a core and six arms in its texture."""
    assets = carry / "assets/mekanism"
    near, far = 8 - CABLE_THICKNESS // 2, 8 + CABLE_THICKNESS // 2
    write(assets / "models/block/port_cable/core.json", box_model([near] * 3, [far] * 3))
    parts = [{"apply": {"model": "mekanism:block/port_cable/core"}}]
    for side in SIDES:
        write(assets / f"models/block/port_cable/{side}.json", box_model(*arm_box(side)))
        parts.append({"when": {side: "true"}, "apply": {"model": f"mekanism:block/port_cable/{side}"}})
    write(assets / "blockstates/basic_universal_cable.json", {"multipart": parts})
    write(
        carry / "data/mekanism/horizon/block/basic_universal_cable.json",
        {
            "template": "minecraft:chorus_plant",
            "connects_to": "#mekanism:port_cable_joins",
            "thickness": CABLE_THICKNESS,
        },
    )
    write(carry / "data/mekanism/tags/block/port_cable_joins.json", {"values": [
        {"id": block, "required": False} for block in CABLE_JOINS
    ]})


def add_cube_model(carry: Path) -> None:
    """The real cube's model type draws its sides by their config. This is its plain model."""
    path = carry / "assets/mekanism/blockstates/basic_energy_cube.json"
    variants = json.loads(path.read_text())["variants"]
    plain = {name: entry["tier_model"] for name, entry in variants.items() if "tier_model" in entry}
    if plain:
        path.write_text(json.dumps({"variants": plain}))


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    menus = Path(sys.argv[1]) / "data/mekanism/horizon/menu"
    menus.mkdir(parents=True, exist_ok=True)
    for machine in MACHINES:
        (menus / f"{machine}.json").write_text(json.dumps(MACHINE_MENU))
    generators = Path(sys.argv[2]) / "data/mekanismgenerators/horizon/menu"
    generators.mkdir(parents=True, exist_ok=True)
    (generators / "heat_generator.json").write_text(json.dumps(GENERATOR_MENU))
    add_cable(Path(sys.argv[1]))
    add_cube_model(Path(sys.argv[1]))
    print(f"{len(MACHINES) + 1} menu types added, cable and cube models replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
