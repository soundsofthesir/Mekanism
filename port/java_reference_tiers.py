#!/usr/bin/env python3
"""Records the tiers of the transport blocks from the real mod into `port/reference/`.

    python3 port/java_reference_tiers.py [scenario ...]

Each row holds, for every block in the row at x = 0, 1, ...: its energy, its chemical amount and, for a
cube, what the Energy Tablet in each of its slots holds.
"""

import re
import sys
from pathlib import Path
from typing import NamedTuple

import java_reference_features as features
import java_server

OUT = Path(__file__).resolve().parent / "reference"
Y = 200
ALL_IN = "[I;1,1,1,1,1,1]"
ALL_OUT = "[I;4,4,4,4,4,4]"
SO2 = "mekanism:sulfur_dioxide"


class Scenario(NamedTuple):
    name: str
    blocks: tuple[str, ...]
    ticks: int


def cube(tier: str, stored: int = 0, out: bool = False, items: tuple[str, ...] = ()) -> str:
    config = f"config0:{ALL_OUT},eject0:1b" if out else f"config0:{ALL_IN}"
    power = f"energy_container:{{stored:{stored}L}}," if stored else ""
    held = f"items:[{','.join(items)}]," if items else ""
    return f"mekanism:{tier}_energy_cube{{{held}{power}component_config:{{{config}}}}}"


def tank(tier: str, stored: int = 0, out: bool = False) -> str:
    config = f"config2:{ALL_OUT},eject2:1b" if out else f"config2:{ALL_IN}"
    held = f'chemical_tanks:[{{container:0b,stored:{{amount:{stored}L,type:"{SO2}"}}}}],' if stored else ""
    return f"mekanism:{tier}_chemical_tank{{{held}component_config:{{{config}}}}}"


def cable(tier: str) -> str:
    return f"mekanism:{tier}_universal_cable"


def tube(tier: str) -> str:
    return f"mekanism:{tier}_pressurized_tube"


TIERS = ("advanced", "elite", "ultimate")
SCENARIOS = (
    *(Scenario(f"tier_cube_{tier}", (cube(tier, 100_000_000, True), cube("ultimate")), 8) for tier in TIERS),
    Scenario("tier_cube_fills_advanced", (cube("ultimate", 200_000_000, True), cube("advanced")), 70),
    *(Scenario(f"tier_cable_{tier}", (cube("ultimate", 200_000_000, True), cable(tier), cube("ultimate")), 8) for tier in TIERS),
    Scenario("tier_cable_mixed", (cube("ultimate", 200_000_000, True), cable("basic"), cable("ultimate"), cube("ultimate")), 8),
    Scenario("tier_cable_full_target", (cube("ultimate", 200_000_000, True), cable("advanced"), cube("basic")), 25),
    *(Scenario(f"tier_tank_{tier}", (tank(tier, 200_000, True), tank("ultimate")), 8) for tier in TIERS),
    Scenario("tier_tank_fills_advanced", (tank("ultimate", 1_000_000, True), tank("advanced")), 12),
    *(Scenario(f"tier_tube_{tier}", (tank("ultimate", 8_000_000, True), tube(tier), tank("ultimate")), 8) for tier in TIERS),
    Scenario("tier_tube_mixed", (tank("ultimate", 8_000_000, True), tube("basic"), tube("elite"), tank("ultimate")), 8),
    Scenario("cube_slot_charge", (cube("basic", 100_000, items=(features.tablet(1, 0),)),), 10),
    Scenario("cube_slot_charge_ultimate", (cube("ultimate", 100_000, items=(features.tablet(1, 0),)),), 10),
    Scenario("cube_slot_discharge", (cube("basic", items=(features.tablet(0, 100_000),)),), 10),
    Scenario("cube_slot_redstone", (cube("basic", items=(features.stack(0, "minecraft:redstone", 3),)),), 5),
    Scenario("cube_slot_both", (cube("advanced", 50_000, items=(features.tablet(0, 100_000), features.tablet(1, 0))),), 10),
)


def cells(nbt: str) -> list[str]:
    energy = re.search(r"energy_container: \{stored: (\d+)L", nbt) or re.search(r"\benergy: (\d+)L", nbt)
    chem = re.search(r"\bstored: \{amount: (\d+)L, (?:id|type): \"mekanism:sulfur", nbt)
    tablets = []
    for slot in (0, 1):
        held = re.search(rf'container: {slot}b, stored: \{{amount: \d+L, type: \{{components: \{{"mekanism:energy": (\d+)L', nbt)
        tablets.append(held.group(1) if held else "-")
    item = features.slot(nbt, 0)
    return [energy.group(1) if energy else "0", chem.group(1) if chem else "0", *tablets, item]


def read(rcon, tick: int, count: int) -> str:
    row = [str(tick)]
    for x in range(count):
        row += cells(rcon.command(f"data get block {x} {Y} 0"))
    return "\t".join(row)


def record(rcon, scenario: Scenario) -> None:
    rcon.command("tick unfreeze")
    for x in range(6):
        rcon.command(f"setblock {x} {Y} 0 air")
    rcon.command("tick freeze")
    # The last block goes in first, so that nothing moves between placements.
    for x, block in reversed(list(enumerate(scenario.blocks))):
        answer = rcon.command(f"setblock {x} {Y} 0 {block}")
        if "Changed" not in answer:
            raise SystemExit(f"{scenario.name}: setblock answered {answer}")
    count = len(scenario.blocks)
    lines = [read(rcon, 0, count)]
    for tick in range(1, scenario.ticks + 1):
        java_server.step(rcon)
        lines.append(read(rcon, tick, count))
    (OUT / f"{scenario.name}.tsv").write_text("\n".join(lines) + "\n")
    print(scenario.name, lines[-1].replace("\t", " "), flush=True)


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
