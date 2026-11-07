#!/usr/bin/env python3
"""Records upgrades, redstone control and item ejecting from the real mod into `port/reference/`.

    python3 port/java_reference_features.py [scenario names]

Needs `java_server.py`'s server running on Tower. Rows are one tick apart, with `tick step 1`.
"""

import re
import sys
from pathlib import Path
from typing import NamedTuple

import java_server

OUT = Path(__file__).resolve().parent / "reference"
Y = 100
CHAMBER = "mekanism:enrichment_chamber"
OXIDIZER = "mekanism:chemical_oxidizer"
CUBE = "mekanism:basic_energy_cube"
ORE = "minecraft:iron_ore"
DUST = "mekanism:dust_iron"
SULFUR = "mekanism:dust_sulfur"
ALL_IN = "[I;1,1,1,1,1,1]"
ALL_OUT = "[I;4,4,4,4,4,4]"
FIELDS = ["progress", "active", "energy", "input", "output", "tank", "chest"]


def stack(index: int, item: str, count: int) -> str:
    return f'{{container:{index}b,stored:{{amount:{count}L,type:{{id:"{item}"}}}}}}'


def machine(
    block: str = CHAMBER,
    speed: int = 0,
    energy_upgrades: int = 0,
    energy: int = 0,
    items: tuple[str, ...] = (),
    control: str = "",
    item_sides: str = ALL_IN,
    eject: bool = False,
    upgrade_slot: str = "",
) -> str:
    upgrades = ",".join(
        f'"mekanism:{name}":{count}' for name, count in (("speed", speed), ("energy", energy_upgrades)) if count
    )
    parts = ([f"upgrades:{{{upgrades}}}"] if upgrades else []) + ([f"items:[{upgrade_slot}]"] if upgrade_slot else [])
    upgrade = f"component_upgrade:{{{','.join(parts)}}}," if parts else ""
    held = f"items:[{','.join(items)}]," if items else ""
    power = f"energy_container:{{stored:{energy}L}}," if energy else ""
    redstone = f'control_type:"{control}",' if control else ""
    config = f"config0:{ALL_IN},config3:{item_sides},eject3:{int(eject)}b"
    return f"{block}{{{upgrade}{held}{power}{redstone}component_config:{{{config}}}}}"


CUBE_FULL = (
    f"{CUBE}{{component_config:{{config0:{ALL_OUT},eject0:1b}},energy_container:{{stored:1000000L}}}}"
)
ORES = (stack(0, ORE, 16),)
LOTS = 100_000_000


class Scenario(NamedTuple):
    name: str
    blocks: tuple[str, ...]
    ticks: int
    # (tick, command): run just before that tick.
    changes: tuple[tuple[int, str], ...] = ()
    # Blocks beside the row, placed as (x, z, block), such as a supply out of a redstone block's way.
    extra: tuple[tuple[int, int, str], ...] = ()


def tablet(index: int, stored: int) -> str:
    """A charged Energy Tablet in a slot, with `ATTACHED_ENERGY`'s component."""
    return (
        f'{{container:{index}b,stored:{{amount:1L,type:{{id:"mekanism:energy_tablet",'
        f'components:{{"mekanism:energy":{stored}L}}}}}}}}'
    )


def upgrade_stack(kind: str, count: int) -> str:
    """What a machine's upgrade slot saves, with `IUpgradeHelper.getPatch`'s component."""
    return (
        f'{{container:0b,stored:{{amount:{count}L,type:{{id:"mekanism:upgrade",'
        f'components:{{"mekanism:upgrade_type":"mekanism:{kind}"}}}}}}}}'
    )


SCENARIOS = (
    # Charging from a cube shows capacity: an idle machine stops at it.
    Scenario("upgrade_idle_none", (machine(), CUBE_FULL), 6),
    Scenario("upgrade_idle_speed4", (machine(speed=4), CUBE_FULL), 6),
    Scenario("upgrade_idle_energy4", (machine(energy_upgrades=4), CUBE_FULL), 6),
    Scenario("upgrade_idle_energy8", (machine(energy_upgrades=8), CUBE_FULL), 6),
    Scenario("upgrade_idle_speed8_energy8", (machine(speed=8, energy_upgrades=8), CUBE_FULL), 6),
    # Stored energy with no supply shows usage a tick and what loading a large amount does.
    Scenario("upgrade_battery_energy4", (machine(energy_upgrades=4, energy=LOTS, items=ORES),), 30),
    Scenario("upgrade_battery_speed2_energy8", (machine(speed=2, energy_upgrades=8, energy=LOTS, items=ORES),), 30),
    # With a supply, progress shows the ticks a recipe takes.
    Scenario("upgrade_run_speed4", (machine(speed=4, items=ORES), CUBE_FULL), 140),
    Scenario("upgrade_run_speed8", (machine(speed=8, items=ORES), CUBE_FULL), 50),
    Scenario("upgrade_run_speed8_energy8", (machine(speed=8, energy_upgrades=8, items=ORES), CUBE_FULL), 50),
    Scenario("upgrade_oxidizer_speed2", (machine(OXIDIZER, speed=2, items=(stack(0, SULFUR, 8),)), CUBE_FULL), 90),
    # Redstone control, with a redstone block placed and taken away beside the machine.
    Scenario(
        "redstone_high",
        (machine(control="high", items=ORES),),
        30,
        ((5, f"setblock 1 {Y} 0 minecraft:redstone_block"), (15, f"setblock 1 {Y} 0 minecraft:air")),
        ((0, 1, CUBE_FULL),),
    ),
    Scenario(
        "redstone_low",
        (machine(control="low", items=ORES),),
        30,
        ((5, f"setblock 1 {Y} 0 minecraft:redstone_block"), (15, f"setblock 1 {Y} 0 minecraft:air")),
        ((0, 1, CUBE_FULL),),
    ),
    Scenario(
        "redstone_pulse",
        (machine(control="pulse", items=ORES),),
        30,
        ((5, f"setblock 1 {Y} 0 minecraft:redstone_block"), (6, f"setblock 1 {Y} 0 minecraft:air")),
        ((0, 1, CUBE_FULL),),
    ),
    Scenario(
        "redstone_disabled",
        (machine(items=ORES),),
        20,
        ((5, f"setblock 1 {Y} 0 minecraft:redstone_block"),),
        ((0, 1, CUBE_FULL),),
    ),
    # Ejecting items: from a stack already in the output slot, and from a running recipe.
    Scenario(
        "eject_stack",
        (machine(item_sides=ALL_OUT, eject=True, items=(stack(1, DUST, 70),)), "minecraft:chest"),
        50,
    ),
    Scenario(
        "eject_off",
        (machine(item_sides=ALL_OUT, items=(stack(1, DUST, 70),)), "minecraft:chest"),
        30,
    ),
    Scenario(
        "eject_closed_side",
        (machine(eject=True, items=(stack(1, DUST, 70),)), "minecraft:chest"),
        30,
    ),
    Scenario(
        "eject_running",
        (machine(item_sides=ALL_OUT, eject=True, items=(stack(0, ORE, 2),)), "minecraft:chest"),
        440,
        (),
        ((0, 1, CUBE_FULL),),
    ),
    # The energy slot: `EnergyInventorySlot.fillContainerOrConvert`.
    Scenario("energy_slot_tablet", (machine(speed=8, items=(tablet(2, 100_000),)),), 30),
    Scenario("energy_slot_tablet_small", (machine(items=(tablet(2, 100_000),)),), 10),
    Scenario("energy_slot_tablet_low", (machine(speed=8, items=(tablet(2, 7_000),)),), 10),
    Scenario("energy_slot_redstone", (machine(speed=8, items=(stack(2, "minecraft:redstone", 3),)),), 10),
    Scenario("energy_slot_redstone_small", (machine(items=(stack(2, "minecraft:redstone", 3),)),), 10),
    Scenario("energy_slot_running", (machine(speed=8, items=(*ORES, tablet(2, 100_000))),), 60),
    Scenario("energy_slot_oxidizer", (machine(block="mekanism:chemical_oxidizer", speed=8, items=(tablet(2, 100_000),)),), 10),
    Scenario("energy_slot_not_energy", (machine(speed=8, items=(stack(2, "minecraft:dirt", 3),)),), 5),
    # Upgrades a player put in the upgrade slot: `TileComponentUpgrade.tickServer`.
    Scenario("install_speed3", (machine(upgrade_slot=upgrade_stack("speed", 3)),), 30),
    Scenario("install_energy4", (machine(upgrade_slot=upgrade_stack("energy", 4)),), 30),
    Scenario("install_over_max", (machine(speed=7, upgrade_slot=upgrade_stack("speed", 5)),), 30),
    Scenario("install_at_max", (machine(speed=8, upgrade_slot=upgrade_stack("speed", 2)),), 30),
    Scenario(
        "install_running",
        (machine(items=ORES, upgrade_slot=upgrade_stack("speed", 8)),),
        60,
        (),
        ((0, 1, CUBE_FULL),),
    ),
)


def get(text: str, pattern: str, default: str = "0") -> str:
    found = re.search(pattern, text)
    return found.group(1) if found else default


def slot(text: str, index: int) -> str:
    found = re.search(
        rf'container: {index}b, stored: \{{amount: (\d+)L, type: \{{(?:components: \{{[^}}]*\}}, )?id: "([^"]+)"', text
    )
    return f"{found.group(2)}x{found.group(1)}" if found else "-"


def chest_items(text: str) -> str:
    stacks = re.findall(r'\{(?:Slot: (\d+)b, )?(?:count: (\d+), )?(?:Slot: \d+b, )?id: "([^"]+)"', text)
    total: dict[str, int] = {}
    for _, count, item in stacks:
        total[item] = total.get(item, 0) + int(count or 1)
    return ",".join(f"{item}x{count}" for item, count in sorted(total.items())) or "-"


def split_upgrades(nbt: str) -> tuple[str, str]:
    """`component_upgrade`'s text, and the block's data without it, whose slots look the same."""
    start = nbt.find("component_upgrade: {")
    if start < 0:
        return "", nbt
    depth, at = 0, nbt.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(nbt[at], 0)
        at += 1
        if depth == 0:
            return nbt[start:at], nbt[:start] + nbt[at:]


def upgrade_columns(component: str) -> list[str]:
    """What's installed and what's still in the upgrade slot."""
    installed = lambda name: get(component, rf'"mekanism:{name}": (\d+)')
    held = re.search(r"items: \[.*?amount: (\d+)L", component)
    return [installed("speed"), installed("energy"), held.group(1) if held else "0"]


def energy_slot_columns(nbt: str) -> list[str]:
    """The energy slot's item and what a tablet in it holds."""
    held = re.search(r'"mekanism:energy": (\d+)L', nbt)
    return [slot(nbt, 2), held.group(1) if held else "0"]


def row(rcon: java_server.Rcon, tick: int, has_chest: bool, has_upgrades: bool = False, has_energy_slot: bool = False) -> str:
    component, nbt = split_upgrades(rcon.command(f"data get block 0 {Y} 0"))
    tank = re.search(r'chemical_tanks: \[\{container: 0b, stored: \{amount: (\d+)L', nbt)
    chest = chest_items(rcon.command(f"data get block 1 {Y} 0")) if has_chest else "-"
    return "\t".join(
        [
            str(tick),
            get(nbt, r"progress: (\d+)"),
            get(nbt, r"active_state: (\d)b"),
            get(nbt, r"energy_container: \{stored: (\d+)L"),
            slot(nbt, 0),
            slot(nbt, 1),
            tank.group(1) if tank else "0",
            chest,
            *(upgrade_columns(component) if has_upgrades else []),
            *(energy_slot_columns(nbt) if has_energy_slot else []),
        ]
    )


def record(rcon: java_server.Rcon, scenario: Scenario) -> None:
    rcon.command("tick unfreeze")
    for x in range(3):
        rcon.command(f"setblock {x} {Y} 0 air")
    rcon.command(f"setblock 0 {Y} 1 air")
    rcon.command("tick freeze")
    # The supply goes in last, so that a tick can't pass between the machine and it.
    for x, block in enumerate(scenario.blocks):
        answer = rcon.command(f"setblock {x} {Y} 0 {block}")
        if "Changed" not in answer and "air" not in block:
            raise SystemExit(f"{scenario.name}: setblock answered {answer}")
    for x, z, block in scenario.extra:
        rcon.command(f"setblock {x} {Y} {z} {block}")
    has_chest = any("chest" in block for block in scenario.blocks)
    extra = scenario.name.startswith("install_")
    energy_slot = scenario.name.startswith("energy_slot_")
    header = [*FIELDS, *(("speed", "energy_upgrades", "slot") if extra else ()), *(("energy_slot", "item_energy") if energy_slot else ())]
    lines = ["\t".join(["tick", *header]), row(rcon, 0, has_chest, extra, energy_slot)]
    changes = dict(scenario.changes)
    for tick in range(1, scenario.ticks + 1):
        if tick in changes:
            rcon.command(changes[tick])
        java_server.step(rcon)
        lines.append(row(rcon, tick, has_chest, extra, energy_slot))
    (OUT / f"{scenario.name}.tsv").write_text("\n".join(lines) + "\n")
    print(scenario.name, lines[1].replace("\t", " "), "|", lines[-1].replace("\t", " "), flush=True)


def main() -> int:
    OUT.mkdir(exist_ok=True)
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
