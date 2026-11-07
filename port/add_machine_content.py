#!/usr/bin/env python3
"""Adds the menu types the machine mod opens to the carried mods.

Usage: add_machine_content.py MEKANISM_CARRY GENERATORS_CARRY UPSTREAM
"""

import json
import sys
from pathlib import Path

MACHINES = ("enrichment_chamber", "crusher", "energized_smelter")
# The machine mod registers this block, so the carried definition has to go.
OXIDIZER = "chemical_oxidizer"
# Input, output, energy item, upgrade input, upgrade output. The output slots only give.
MACHINE_MENU = {"slots": 5, "data_slots": 17, "results": [1, 4]}
COMPRESSOR = "osmium_compressor"
# As the machines, then the slot after the upgrades. These are `process_table.rs`'s machines.
COMPRESSOR_MENU = {"slots": 6, "data_slots": 17, "results": [1, 4]}
PROCESS_MACHINES = {
    COMPRESSOR: COMPRESSOR_MENU,
    "purification_chamber": COMPRESSOR_MENU,
    "chemical_injection_chamber": COMPRESSOR_MENU,
    "combiner": COMPRESSOR_MENU,
    "metallurgic_infuser": COMPRESSOR_MENU,
    # Its slot after the upgrades is a second output.
    "precision_sawmill": {"slots": 6, "data_slots": 17, "results": [1, 4, 5]},
}
OXIDIZER_MENU = {"slots": 5, "data_slots": 17, "results": [1, 4]}
# Discharge and charge. Same data slots as the machines, which share the screen's code.
CUBE_MENU = {"slots": 2, "data_slots": 17}
# The fuel slot. Lava, energy, temperature.
GENERATOR_MENU = {"slots": 1, "data_slots": 3}


CABLE_THICKNESS = 4
# Blocks a cable joins: everything with energy that is ported so far.
TIERS = ("basic", "advanced", "elite", "ultimate")
CABLE_JOINS = (
    *(f"mekanism:{tier}_energy_cube" for tier in TIERS),
    "mekanism:enrichment_chamber",
    "mekanism:crusher",
    "mekanism:energized_smelter",
    *(f"mekanism:{machine}" for machine in PROCESS_MACHINES),
    "mekanismgenerators:heat_generator",
)
CABLE_PARTICLE = "mekanism:block/models/multipart/basic_universal_cable"
# Blocks a tube joins: everything with chemicals that is ported so far.
TUBE_JOINS = ("mekanism:chemical_oxidizer", *(f"mekanism:{tier}_chemical_tank" for tier in TIERS))
# Blocks a pipe joins.
PIPE_JOINS = tuple(f"mekanism:{tier}_fluid_tank" for tier in TIERS)
SIDES = ("north", "south", "east", "west", "up", "down")


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def box_model(texture: str, low: list[int], high: list[int]) -> dict:
    faces = {side: {"texture": "#pipe"} for side in SIDES}
    return {
        "textures": {"particle": texture, "pipe": texture},
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


def add_pipe(carry: Path, block: str, joins: tuple[str, ...]) -> None:
    """The real pipes are an OBJ model with Java geometry. This is a core and six arms in the texture."""
    assets = carry / "assets/mekanism"
    texture = f"mekanism:block/models/multipart/{block}"
    tag = f"port_{block}_joins"
    near, far = 8 - CABLE_THICKNESS // 2, 8 + CABLE_THICKNESS // 2
    folder = f"port_{block}"
    write(assets / f"models/block/{folder}/core.json", box_model(texture, [near] * 3, [far] * 3))
    parts = [{"apply": {"model": f"mekanism:block/{folder}/core"}}]
    for side in SIDES:
        write(assets / f"models/block/{folder}/{side}.json", box_model(texture, *arm_box(side)))
        parts.append({"when": {side: "true"}, "apply": {"model": f"mekanism:block/{folder}/{side}"}})
    write(assets / f"blockstates/{block}.json", {"multipart": parts})
    write(
        carry / f"data/mekanism/horizon/block/{block}.json",
        {"template": "minecraft:chorus_plant", "connects_to": f"#mekanism:{tag}", "thickness": CABLE_THICKNESS},
    )
    write(carry / f"data/mekanism/tags/block/{tag}.json", {"values": [
        {"id": each, "required": False} for each in joins
    ]})


def add_cable_look(carry: Path, upstream: Path) -> None:
    """The machine mod draws the cable's OBJ model, so its block has no model of its own. The energy
    contents' texture is in a folder the game's atlas skips, so it goes where the atlas looks."""
    write(carry / "assets/mekanism/models/block/port_empty.json", {"textures": {"particle": CABLE_PARTICLE}, "elements": []})
    for tier in TIERS:
        write(
            carry / f"assets/mekanism/blockstates/{tier}_universal_cable.json",
            {"variants": {"": {"model": "mekanism:block/port_empty"}}},
        )
    source = upstream / "src/main/resources/assets/mekanism/textures/mek_liquid/energy.png"
    target = carry / "assets/mekanism/textures/block/port_energy.png"
    target.write_bytes(source.read_bytes())
    target.with_suffix(".png.mcmeta").write_bytes(source.with_suffix(".png.mcmeta").read_bytes())
    # The gas a gauge shows, for the same reason.
    source = upstream / "src/main/resources/assets/mekanism/textures/mek_liquid/liquid.png"
    target = carry / "assets/mekanism/textures/block/port_liquid.png"
    target.write_bytes(source.read_bytes())
    target.with_suffix(".png.mcmeta").write_bytes(source.with_suffix(".png.mcmeta").read_bytes())


def add_cube_model(carry: Path) -> None:
    """The real cube's model type draws its sides by their config. This is its plain model."""
    for tier in TIERS:
        path = carry / f"assets/mekanism/blockstates/{tier}_energy_cube.json"
        variants = json.loads(path.read_text())["variants"]
        plain = {name: entry["tier_model"] for name, entry in variants.items() if "tier_model" in entry}
        if plain:
            path.write_text(json.dumps({"variants": plain}))


def add_chemical_tags(carry: Path, generators: Path) -> None:
    """Horizon has no chemical tag registry, so each tag file also goes in as a recipe a hook can read."""
    out = carry / "data/mekanism/recipe/port_chemical_tag"
    out.mkdir(parents=True, exist_ok=True)
    tags: dict[str, list[str]] = {}
    for root in (carry, generators):
        for path in sorted((root / "data/mekanism/tags/mekanism/chemical").rglob("*.json")):
            name = path.relative_to(root / "data/mekanism/tags/mekanism/chemical").with_suffix("").as_posix()
            tags.setdefault(f"mekanism:{name}", []).extend(json.loads(path.read_text())["values"])

    def expand(values: list[str]) -> list[str]:
        out_values: list[str] = []
        for value in values:
            out_values.extend(expand(tags[value[1:]]) if value.startswith("#") else [value])
        return out_values

    for tag, values in tags.items():
        file = out / f"{tag.split(':')[1].replace('/', '_')}.json"
        file.write_text(json.dumps({"type": "mekmachine:chemical_tag", "tag": tag, "values": expand(values)}))


def add_chemical_art(carry: Path, upstream: Path) -> None:
    """The GUI atlas holds block textures, so chemical icons go there under `port_`, as `gen_chemical_table.py` names them."""
    art = upstream / "src/main/resources/assets/mekanism/textures"
    out = carry / "assets/mekanism/textures/block"
    for folder in ("mek_liquid", "mek_chemical/slurry", "mek_chemical/infuse_type"):
        for path in sorted((art / folder).glob("*.png")):
            name = "port_" + path.relative_to(art).with_suffix("").as_posix().replace("/", "_")
            (out / f"{name}.png").write_bytes(path.read_bytes())
            meta = path.with_suffix(".png.mcmeta")
            if meta.exists():
                (out / f"{name}.png.mcmeta").write_bytes(meta.read_bytes())


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    menus = Path(sys.argv[1]) / "data/mekanism/horizon/menu"
    menus.mkdir(parents=True, exist_ok=True)
    for machine in MACHINES:
        (menus / f"{machine}.json").write_text(json.dumps(MACHINE_MENU))
    generators = Path(sys.argv[2]) / "data/mekanismgenerators/horizon/menu"
    generators.mkdir(parents=True, exist_ok=True)
    (generators / "heat_generator.json").write_text(json.dumps(GENERATOR_MENU))
    (menus / f"{OXIDIZER}.json").write_text(json.dumps(OXIDIZER_MENU))
    for machine, menu in PROCESS_MACHINES.items():
        (menus / f"{machine}.json").write_text(json.dumps(menu))
        (Path(sys.argv[1]) / f"data/mekanism/horizon/block/{machine}.json").unlink(missing_ok=True)
    add_chemical_tags(Path(sys.argv[1]), Path(sys.argv[2]))
    add_chemical_art(Path(sys.argv[1]), Path(sys.argv[3]))
    (Path(sys.argv[1]) / f"data/mekanism/horizon/block/{OXIDIZER}.json").unlink(missing_ok=True)
    for tier in TIERS:
        (menus / f"{tier}_energy_cube.json").write_text(json.dumps(CUBE_MENU))
        (Path(sys.argv[1]) / f"data/mekanism/horizon/block/{tier}_energy_cube.json").unlink(missing_ok=True)
        add_pipe(Path(sys.argv[1]), f"{tier}_universal_cable", CABLE_JOINS)
        add_pipe(Path(sys.argv[1]), f"{tier}_pressurized_tube", TUBE_JOINS)
        add_pipe(Path(sys.argv[1]), f"{tier}_mechanical_pipe", PIPE_JOINS)
    add_cable_look(Path(sys.argv[1]), Path(sys.argv[3]))
    add_cube_model(Path(sys.argv[1]))
    print(f"{len(MACHINES) + 2} menu types added, cable, tube and cube models replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
