#!/usr/bin/env python3
"""Records machines with an item input, a chemical tank and an item output from the real mod.

    python3 port/java_reference_advanced.py [scenario names]

Needs `java_server.py`'s server running on Tower. Rows are one tick apart, with `tick step 1`. The
slots are input 0, secondary 1, output 2 and energy 3, and the tank is `chemical_tanks`' first.
"""

import re
import sys
from pathlib import Path
from typing import NamedTuple

import java_server
from java_reference_features import ALL_IN, CUBE_FULL, get, slot, split_upgrades, stack

OUT = Path(__file__).resolve().parent / "reference"
Y = 100
COMPRESSOR = "mekanism:osmium_compressor"
OSMIUM = "mekanism:osmium"
DUST = "minecraft:glowstone_dust"
INGOT = "mekanism:ingot_refined_glowstone"
LOTS = 100_000
HEADER = ["tick", "progress", "active", "energy", "input", "secondary", "output", "chemical", "tank"]


def advanced(
    block: str = COMPRESSOR,
    items: tuple[str, ...] = (),
    energy: int = LOTS,
    tank: int = 0,
    chemical: str = OSMIUM,
    speed: int = 0,
) -> str:
    upgrade = f'component_upgrade:{{upgrades:{{"mekanism:speed":{speed}}}}},' if speed else ""
    held = f"items:[{','.join(items)}]," if items else ""
    power = f"energy_container:{{stored:{energy}L}}," if energy else ""
    gas = f'chemical_tanks:[{{container:0b,stored:{{amount:{tank}L,type:"{chemical}"}}}}],' if tank else ""
    config = f"config0:{ALL_IN},config2:{ALL_IN},config3:{ALL_IN},eject3:0b"
    return f"{block}{{{upgrade}{held}{power}{gas}component_config:{{{config}}}}}"


class Scenario(NamedTuple):
    name: str
    blocks: tuple[str, ...]
    ticks: int
    changes: tuple[tuple[int, str], ...] = ()


DUSTS = (stack(0, DUST, 8),)
SCENARIOS = (
    # Normal running: a dust takes 200 ticks and one osmium a tick.
    Scenario("compressor_normal", (advanced(items=DUSTS, tank=210),), 420),
    # Edge cases.
    Scenario("compressor_no_chemical", (advanced(items=DUSTS),), 30),
    Scenario("compressor_runs_out", (advanced(items=DUSTS, tank=50),), 80),
    Scenario("compressor_no_power", (advanced(items=DUSTS, tank=210, energy=100),), 30),
    Scenario("compressor_one_dust_left", (advanced(items=(stack(0, DUST, 1),), tank=210),), 220),
    Scenario("compressor_output_full", (advanced(items=(stack(0, DUST, 8), stack(2, INGOT, 64)), tank=210),), 20),
    Scenario("compressor_wrong_item", (advanced(items=(stack(0, "minecraft:dirt", 8),), tank=210),), 10),
    Scenario("compressor_wrong_chemical", (advanced(items=DUSTS, tank=210, chemical="mekanism:oxygen"),), 10),
    Scenario("compressor_ingot", (advanced(items=DUSTS + (stack(1, "mekanism:ingot_osmium", 3),)),), 40),
    Scenario("compressor_ingot_no_room", (advanced(items=DUSTS + (stack(1, "mekanism:ingot_osmium", 3),), tank=100),), 20),
    # An ingot gives 200: it waits with 11 held, and fits the moment 10 are, at the tank's 210.
    Scenario("compressor_ingot_exact_fit", (advanced(items=DUSTS + (stack(1, "mekanism:ingot_osmium", 3),), tank=11),), 8),
    Scenario("compressor_speed4", (advanced(items=DUSTS, tank=210, speed=4),), 80),
    Scenario("compressor_input_removed", (advanced(items=DUSTS, tank=210),), 30, ((15, f"data modify block 0 {Y} 0 items[0].stored.amount set value 0L"),)),
    Scenario("compressor_supplied", (advanced(items=DUSTS, tank=210, energy=0), CUBE_FULL), 30),
)


def row(rcon: java_server.Rcon, tick: int) -> str:
    _, nbt = split_upgrades(rcon.command(f"data get block 0 {Y} 0"))
    tank = re.search(r'chemical_tanks: \[\{container: 0b, stored: \{amount: (\d+)L, type: "([^"]+)"', nbt)
    return "\t".join(
        [
            str(tick),
            get(nbt, r"progress: (\d+)"),
            get(nbt, r"active_state: (\d)b"),
            get(nbt, r"energy_container: \{stored: (\d+)L"),
            slot(nbt, 0),
            slot(nbt, 1),
            slot(nbt, 2),
            tank.group(2) if tank else "-",
            tank.group(1) if tank else "0",
        ]
    )


def record(rcon: java_server.Rcon, scenario: Scenario) -> None:
    rcon.command("tick unfreeze")
    for x in range(3):
        rcon.command(f"setblock {x} {Y} 0 air")
    rcon.command("tick freeze")
    for x, block in enumerate(scenario.blocks):
        answer = rcon.command(f"setblock {x} {Y} 0 {block}")
        if "Changed" not in answer:
            raise SystemExit(f"{scenario.name}: setblock answered {answer}")
    lines = ["\t".join(HEADER), row(rcon, 0)]
    changes = dict(scenario.changes)
    for tick in range(1, scenario.ticks + 1):
        if tick in changes:
            rcon.command(changes[tick])
        java_server.step(rcon)
        lines.append(row(rcon, tick))
    (OUT / f"{scenario.name}.tsv").write_text("\n".join(lines) + "\n")
    print(scenario.name, *(lines[i].replace("\t", " ") + " |" for i in (1, 2, 3, len(lines) // 2, -1)), flush=True)


def main() -> int:
    rcon, tunnel = java_server.connect()
    try:
        rcon.command("forceload add 0 0")
        wanted = sys.argv[1:]
        for scenario in SCENARIOS:
            if not wanted or scenario.name in wanted:
                record(rcon, scenario)
        rcon.command("tick unfreeze")
    finally:
        tunnel.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
