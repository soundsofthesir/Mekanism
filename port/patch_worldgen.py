#!/usr/bin/env python3
"""Rewrite Mekanism's carried ores and salt to vanilla worldgen types Horizon can run.

Mekanism's feature files name Java types that read their numbers from its config. This writes
those numbers into vanilla's `minecraft:ore` and `minecraft:disk` and removes the retrogen files,
which only repopulate chunks generated before the mod was added. It also moves the features from
`worldgen/feature/` to `worldgen/configured_feature/`, the only folder Horizon `f319701` reads for
a mod, although vanilla 26.3 uses the first.

Usage: patch_worldgen.py CARRY
"""

import json
import sys
from pathlib import Path
from typing import NamedTuple


class Vein(NamedTuple):
    per_chunk: int
    discard_on_air: float
    size: int
    shape: str
    low: dict[str, int]
    high: dict[str, int]
    plateau: int = 0


def absolute(y: int) -> dict[str, int]:
    return {"absolute": y}


def above_bottom(y: int) -> dict[str, int]:
    return {"above_bottom": y}


def below_top(y: int) -> dict[str, int]:
    return {"below_top": y}


TRAPEZOID = "minecraft:trapezoid"
UNIFORM = "minecraft:uniform"
# The defaults in upstream's mekanism/common/resource/ore/OreType.java.
VEINS = {
    "ore_tin_small": Vein(14, 0, 4, TRAPEZOID, absolute(-20), absolute(94)),
    "ore_tin_large": Vein(12, 0, 9, TRAPEZOID, absolute(-32), absolute(72)),
    "ore_osmium_upper": Vein(65, 0, 7, TRAPEZOID, absolute(72), below_top(-24), 8),
    "ore_osmium_middle": Vein(6, 0, 9, TRAPEZOID, absolute(-32), absolute(56)),
    "ore_osmium_small": Vein(8, 0, 4, UNIFORM, above_bottom(0), absolute(64)),
    "ore_uranium_small": Vein(4, 0, 4, TRAPEZOID, above_bottom(0), absolute(8)),
    "ore_uranium_buried": Vein(7, 0.75, 9, TRAPEZOID, above_bottom(-24), above_bottom(56), 16),
    "ore_fluorite_normal": Vein(5, 0, 5, UNIFORM, above_bottom(0), absolute(23)),
    "ore_fluorite_buried": Vein(3, 1, 13, TRAPEZOID, above_bottom(0), absolute(4)),
    "ore_lead_normal": Vein(8, 0.25, 9, TRAPEZOID, above_bottom(-24), absolute(64)),
}
# The defaults in upstream's mekanism/common/config/WorldConfig.java.
SALT_PER_CHUNK = 2
SALT_RADIUS = (2, 3)
SALT_HALF_HEIGHT = 1


def height(vein: Vein) -> dict:
    shape = {"type": vein.shape, "min_inclusive": vein.low, "max_inclusive": vein.high}
    return {**shape, "plateau": vein.plateau} if vein.shape == TRAPEZOID else shape


def ore_feature(carried: dict, vein: Vein) -> dict:
    return {
        "type": "minecraft:ore",
        "size": vein.size,
        "discard_chance_on_air_exposure": vein.discard_on_air,
        "targets": carried["targets"],
    }


def ore_placement(name: str, vein: Vein) -> dict:
    return {
        "feature": f"mekanism:{name}",
        "placement": [
            {"type": "minecraft:count", "count": vein.per_chunk},
            {"type": "minecraft:in_square"},
            {"type": "minecraft:height_range", "height": height(vein)},
            {"type": "minecraft:biome"},
        ],
    }


def salt_feature(carried: dict) -> dict:
    low, high = SALT_RADIUS
    return {
        **carried,
        "type": "minecraft:disk",
        "half_height": SALT_HALF_HEIGHT,
        "radius": {"type": UNIFORM, "min_inclusive": low, "max_inclusive": high},
    }


def salt_placement(carried: dict) -> dict:
    kept = [step for step in carried["placement"] if step["type"] != "mekanism:disableable"]
    counted = [
        {"type": "minecraft:count", "count": SALT_PER_CHUNK}
        if step["type"] == "minecraft:count"
        else step
        for step in kept
    ]
    return {**carried, "placement": counted}


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    worldgen = Path(sys.argv[1]) / "data/mekanism/worldgen"
    features, placed = worldgen / "configured_feature", worldgen / "placed_feature"
    (worldgen / "feature").rename(features)
    retrogen = [*features.glob("*_retrogen.json"), *placed.glob("*_retrogen.json")]
    for path in retrogen:
        path.unlink()
    for name, vein in VEINS.items():
        write(features / f"{name}.json", ore_feature(read(features / f"{name}.json"), vein))
        write(placed / f"{name}.json", ore_placement(name, vein))
    write(features / "salt.json", salt_feature(read(features / "salt.json")))
    write(placed / "salt.json", salt_placement(read(placed / "salt.json")))
    print(f"{len(VEINS)} ores and salt rewritten, {len(retrogen)} retrogen files removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
