#!/usr/bin/env python3
"""Records the machines that share `machine/advanced.rs` from the real mod.

    python3 port/java_reference_process.py [scenario names, or `rates`]

Needs `java_server.py`'s server running on Tower. A scenario names its slots by what they do, and each
machine's `slots` says where the real mod keeps them. `port/test_process.py` replays every scenario.

A `*_rate.tsv` file holds many random draws. Its numbers are checked against a bound from the source.
"""

import re
import sys
import time
from pathlib import Path
from typing import NamedTuple

import java_server
from java_reference_features import ALL_IN, get, slot, split_upgrades, stack

OUT = Path(__file__).resolve().parent / "reference"
Y = 100
LOTS = 100_000
HEADER = ["tick", "progress", "active", "energy", "input", "extra", "output", "chemical", "tank"]


class Machine(NamedTuple):
    block: str
    # Logical slot name to the real mod's container index.
    slots: dict[str, int]
    has_tank: bool = False


# `getInitialInventory` of each machine gives these orders.
COMPRESSOR_ORDER = {"input": 0, "extra": 1, "output": 2, "energy": 3}
COMBINER = Machine("mekanism:combiner", COMPRESSOR_ORDER)
SAWMILL = Machine("mekanism:precision_sawmill", {"input": 0, "output": 1, "extra": 2, "energy": 3})
PURIFIER = Machine("mekanism:purification_chamber", COMPRESSOR_ORDER, True)
INJECTOR = Machine("mekanism:chemical_injection_chamber", COMPRESSOR_ORDER, True)
INFUSER = Machine("mekanism:metallurgic_infuser", {"extra": 0, "input": 1, "output": 2, "energy": 3}, True)


class Scenario(NamedTuple):
    name: str
    machine: Machine
    items: dict[str, tuple[str, int]]
    ticks: int
    energy: int = LOTS
    tank: int = 0
    chemical: str = ""
    speed: int = 0
    # A slot's name and the tick at which it empties.
    empty: tuple[str, int] | None = None


def block_of(s: Scenario) -> str:
    m = s.machine
    upgrade = f'component_upgrade:{{upgrades:{{"mekanism:speed":{s.speed}}}}},' if s.speed else ""
    entries = sorted((m.slots[name], item, count) for name, (item, count) in s.items.items())
    held = f"items:[{','.join(stack(*entry) for entry in entries)}]," if entries else ""
    power = f"energy_container:{{stored:{s.energy}L}}," if s.energy else ""
    gas = f'chemical_tanks:[{{container:0b,stored:{{amount:{s.tank}L,type:"{s.chemical}"}}}}],' if s.tank else ""
    chem_side = f"config2:{ALL_IN}," if m.has_tank else ""
    config = f"config0:{ALL_IN},{chem_side}config3:{ALL_IN},eject3:0b"
    return f"{m.block}{{{upgrade}{held}{power}{gas}component_config:{{{config}}}}}"


# Combining: 5 diamond dust and a cobblestone make a diamond ore.
DIAMOND = {"input": ("mekanism:dust_diamond", 12), "extra": ("minecraft:cobblestone", 8)}
ORE_OSMIUM = "mekanism:osmium_ore"
OXYGEN = "mekanism:oxygen"
HCL = "mekanism:hydrogen_chloride"
# `sawing/planks`: 6 sticks and a chance of 0.25 at sawdust.
PLANKS = {"input": ("minecraft:oak_planks", 4)}
# Infusing: 3 copper dust and 10 tin make 4 bronze dust.
COPPER = {"input": ("mekanism:dust_copper", 7)}

SCENARIOS = (
    Scenario("combiner_normal", COMBINER, DIAMOND, 420),
    Scenario("combiner_no_extra", COMBINER, {"input": DIAMOND["input"]}, 10),
    Scenario("combiner_wrong_extra", COMBINER, {"input": DIAMOND["input"], "extra": ("minecraft:dirt", 8)}, 10),
    Scenario("combiner_too_little_input", COMBINER, {"input": ("mekanism:dust_diamond", 4), "extra": ("minecraft:cobblestone", 8)}, 10),
    Scenario("combiner_output_full", COMBINER, {**DIAMOND, "output": ("minecraft:diamond_ore", 64)}, 10),
    Scenario("combiner_other_output", COMBINER, {**DIAMOND, "output": ("minecraft:dirt", 1)}, 10),
    Scenario("combiner_no_power", COMBINER, DIAMOND, 20, energy=30),
    Scenario("combiner_speed4", COMBINER, DIAMOND, 70, speed=4),
    Scenario("combiner_extra_removed", COMBINER, DIAMOND, 30, empty=("extra", 15)),
    # The roll for a secondary is 1.0 here, so these have no random part.
    Scenario("sawmill_always", SAWMILL, {"input": ("minecraft:pumpkin", 3)}, 420),
    Scenario("sawmill_no_secondary", SAWMILL, {"input": ("minecraft:bamboo_block", 2)}, 210),
    Scenario("sawmill_secondary_full", SAWMILL, {"input": ("minecraft:pumpkin", 3), "extra": ("minecraft:pumpkin_seeds", 62)}, 10),
    Scenario("sawmill_secondary_no_room_for_chance", SAWMILL, {**PLANKS, "extra": ("mekanism:sawdust", 64)}, 10),
    Scenario("sawmill_output_full", SAWMILL, {**PLANKS, "output": ("minecraft:stick", 60)}, 10),
    Scenario("sawmill_no_recipe", SAWMILL, {"input": ("minecraft:dirt", 2)}, 10),
    # Random: these rows show which operations gave a secondary.
    Scenario("sawmill_chance", SAWMILL, PLANKS, 820),
    Scenario("sawmill_speed4", SAWMILL, PLANKS, 260, speed=4),
    Scenario("purification_normal", PURIFIER, {"input": (ORE_OSMIUM, 4)}, 420, tank=210, chemical=OXYGEN),
    Scenario("purification_no_chemical", PURIFIER, {"input": (ORE_OSMIUM, 4)}, 20),
    Scenario("purification_runs_out", PURIFIER, {"input": (ORE_OSMIUM, 4)}, 60, tank=3, chemical=OXYGEN),
    Scenario("purification_no_power", PURIFIER, {"input": (ORE_OSMIUM, 4)}, 20, tank=210, chemical=OXYGEN, energy=35),
    Scenario("purification_output_full", PURIFIER, {"input": (ORE_OSMIUM, 4), "output": ("mekanism:clump_osmium", 63)}, 20, tank=210, chemical=OXYGEN),
    Scenario("purification_wrong_chemical", PURIFIER, {"input": (ORE_OSMIUM, 4)}, 10, tank=210, chemical=HCL),
    Scenario("purification_flint", PURIFIER, {"input": (ORE_OSMIUM, 4), "extra": ("minecraft:flint", 3)}, 40, tank=195, chemical=OXYGEN),
    Scenario("purification_flint_empty_tank", PURIFIER, {"input": (ORE_OSMIUM, 4), "extra": ("minecraft:flint", 3)}, 20),
    Scenario("purification_speed4", PURIFIER, {"input": (ORE_OSMIUM, 4)}, 70, tank=210, chemical=OXYGEN, speed=4),
    Scenario("purification_block", PURIFIER, {"input": ("mekanism:block_raw_osmium", 1)}, 230, tank=210, chemical=OXYGEN),
    Scenario("injection_normal", INJECTOR, {"input": (ORE_OSMIUM, 4)}, 420, tank=210, chemical=HCL),
    Scenario("injection_no_chemical", INJECTOR, {"input": (ORE_OSMIUM, 4)}, 20),
    Scenario("injection_salt", INJECTOR, {"input": (ORE_OSMIUM, 4), "extra": ("mekanism:salt", 3)}, 30),
    # A recipe that names `#mekanism:water_vapor`, whose values are water vapor and steam.
    Scenario("injection_tag_steam", INJECTOR, {"input": ("minecraft:dirt", 2)}, 230, tank=210, chemical="mekanism:steam"),
    Scenario("injection_tag_vapor", INJECTOR, {"input": ("minecraft:dirt", 2)}, 30, tank=210, chemical="mekanism:water_vapor"),
    Scenario("injection_tag_wrong", INJECTOR, {"input": ("minecraft:dirt", 2)}, 10, tank=210, chemical=OXYGEN),
    # The infuser takes its chemical at the end of a recipe.
    Scenario("infuser_normal", INFUSER, COPPER, 420, tank=25, chemical="mekanism:tin"),
    Scenario("infuser_no_chemical", INFUSER, COPPER, 10),
    Scenario("infuser_low_chemical", INFUSER, COPPER, 10, tank=9, chemical="mekanism:tin"),
    Scenario("infuser_wrong_chemical", INFUSER, COPPER, 10, tank=20, chemical="mekanism:redstone"),
    Scenario("infuser_low_item", INFUSER, {"input": ("mekanism:dust_copper", 2)}, 10, tank=20, chemical="mekanism:tin"),
    Scenario("infuser_output_full", INFUSER, {**COPPER, "output": ("mekanism:dust_bronze", 62)}, 10, tank=20, chemical="mekanism:tin"),
    Scenario("infuser_no_power", INFUSER, COPPER, 20, tank=20, chemical="mekanism:tin", energy=30),
    Scenario("infuser_convert", INFUSER, {**COPPER, "extra": ("mekanism:dust_tin", 3)}, 10),
    Scenario("infuser_convert_no_room", INFUSER, {**COPPER, "extra": ("mekanism:dust_tin", 3)}, 10, tank=995, chemical="mekanism:tin"),
    # A tank takes only a chemical some recipe has with the item in the input slot.
    Scenario("infuser_convert_wrong_for_input", INFUSER, {**COPPER, "extra": ("minecraft:redstone", 3)}, 10),
    Scenario("infuser_convert_block_redstone", INFUSER, {"input": ("mekanism:ingot_osmium", 1), "extra": ("minecraft:redstone_block", 1)}, 210),
    Scenario("infuser_speed4", INFUSER, COPPER, 70, tank=100, chemical="mekanism:tin", speed=4),
    Scenario("infuser_circuit_tag", INFUSER, {"input": ("mekanism:ingot_osmium", 2)}, 210, tank=40, chemical="mekanism:redstone"),
)
BY_NAME = {s.name: s for s in SCENARIOS}


def row(rcon: java_server.Rcon, tick: int, m: Machine) -> str:
    _, nbt = split_upgrades(rcon.command(f"data get block 0 {Y} 0"))
    tank = re.search(r'chemical_tanks: \[\{container: 0b, stored: \{amount: (\d+)L, type: "([^"]+)"', nbt)
    return "\t".join(
        [
            str(tick),
            get(nbt, r"progress: (\d+)"),
            get(nbt, r"active_state: (\d)b"),
            get(nbt, r"energy_container: \{stored: (\d+)L"),
            slot(nbt, m.slots["input"]),
            slot(nbt, m.slots["extra"]),
            slot(nbt, m.slots["output"]),
            tank.group(2) if tank else "-",
            tank.group(1) if tank else "0",
        ]
    )


def place(rcon: java_server.Rcon, s: Scenario) -> None:
    rcon.command("tick unfreeze")
    rcon.command(f"setblock 0 {Y} 0 air")
    rcon.command("tick freeze")
    answer = rcon.command(f"setblock 0 {Y} 0 {block_of(s)}")
    if "Changed" not in answer:
        raise SystemExit(f"{s.name}: setblock answered {answer}")


def record(rcon: java_server.Rcon, s: Scenario) -> None:
    place(rcon, s)
    lines = ["\t".join(HEADER), row(rcon, 0, s.machine)]
    for tick in range(1, s.ticks + 1):
        if s.empty and tick == s.empty[1]:
            index = sorted(s.machine.slots[name] for name in s.items).index(s.machine.slots[s.empty[0]])
            rcon.command(f"data modify block 0 {Y} 0 items[{index}].stored.amount set value 0L")
        java_server.step(rcon)
        lines.append(row(rcon, tick, s.machine))
    (OUT / f"{s.name}.tsv").write_text("\n".join(lines) + "\n")
    print(s.name, *(lines[i].replace("\t", " ") + " |" for i in (1, 2, -1)), flush=True)


# Draws of `StatUtils.inversePoisson`: rounds of 200 ticks, each with a fresh full tank.
CHEMICAL_ROUNDS = 10
CHEMICAL_TICKS = 200
RATE_CHEMICAL = (
    Scenario("purification_rate", PURIFIER, {"input": (ORE_OSMIUM, 4)}, CHEMICAL_TICKS, tank=210, chemical=OXYGEN),
    Scenario("injection_rate", INJECTOR, {"input": (ORE_OSMIUM, 4)}, CHEMICAL_TICKS, tank=210, chemical=HCL),
)
# Draws of `SawmillRecipe.RANDOM`: 64 pressure plates at a time, 8 speed upgrades, 20 ticks each.
SAW_ROUNDS = 8
SAW_TICKS = 64 * 20 + 2
RATE_SAW = Scenario("sawmill_rate", SAWMILL, {"input": ("minecraft:oak_pressure_plate", 64)}, SAW_TICKS, energy=2_000_000, speed=8)
FAST = 1000


def record_chemical_rate(rcon: java_server.Rcon, s: Scenario) -> None:
    lines = ["round\ttick\ttank\tprogress"]
    for number in range(CHEMICAL_ROUNDS):
        place(rcon, s)
        for tick in range(s.ticks + 1):
            if tick:
                java_server.step(rcon)
            fields = row(rcon, tick, s.machine).split("\t")
            lines.append(f"{number}\t{tick}\t{fields[8]}\t{fields[1]}")
    (OUT / f"{s.name}.tsv").write_text("\n".join(lines) + "\n")
    print(s.name, len(lines) - 1, flush=True)


def game_time(rcon: java_server.Rcon) -> int:
    return int(re.search(r"(\d+)", rcon.command("time query gametime")).group(1))


def record_saw_rate(rcon: java_server.Rcon, s: Scenario) -> None:
    lines = ["round\tinput\toutput\tsecondary"]
    rcon.command(f"tick rate {FAST}")
    for number in range(SAW_ROUNDS):
        place(rcon, s)
        start = game_time(rcon)
        rcon.command(f"tick step {s.ticks}")
        while game_time(rcon) < start + s.ticks:
            time.sleep(0.2)
        fields = row(rcon, s.ticks, s.machine).split("\t")
        lines.append(f"{number}\t{fields[4]}\t{fields[6]}\t{fields[5]}")
        print(lines[-1], flush=True)
    rcon.command("tick rate 20")
    (OUT / f"{s.name}.tsv").write_text("\n".join(lines) + "\n")


def main() -> int:
    rcon, tunnel = java_server.connect()
    try:
        rcon.command("forceload add 0 0")
        wanted = sys.argv[1:]
        rates = "rates" in wanted
        wanted = [name for name in wanted if name != "rates"]
        for s in SCENARIOS:
            if (not wanted and not rates) or s.name in wanted:
                record(rcon, s)
        if rates:
            record_saw_rate(rcon, RATE_SAW)
            for s in RATE_CHEMICAL:
                record_chemical_rate(rcon, s)
        rcon.command("tick unfreeze")
    finally:
        tunnel.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
