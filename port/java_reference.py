#!/usr/bin/env python3
"""Records the real mod's machines into port/reference/, for tests to compare with.

    python3 port/java_server.py start --eula
    python3 port/java_reference.py
    python3 port/java_server.py stop

Each scenario places a machine with its contents, then writes one line per game tick. A change at
a tick runs just before that tick. `data modify` reloads the machine from its saved data, so what a
change does may differ from a hopper or a player doing the same. `data remove` on a slot does
nothing, because loading leaves slots that aren't named as they are, so changes set an amount.
"""

import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.dont_write_bytecode = True
import java_server  # noqa: E402

OUT = Path(__file__).resolve().parent / "reference"
AT = "0 100 0"
ALL_SIDES = "[I;1,1,1,1,1,1]"
INPUT_SLOT, OUTPUT_SLOT = 0, 1
HEADER = "tick\tprogress\tactive\tenergy\tinput\toutput"


def item(slot: int, name: str, count: int) -> str:
    return f'{{container:{slot}b,stored:{{amount:{count}L,type:{{id:"{name}"}}}}}}'


class Scenario(NamedTuple):
    name: str
    block: str
    energy: int
    items: tuple[str, ...]
    ticks: int
    changes: tuple[tuple[int, str], ...] = ()


CHAMBER = "mekanism:enrichment_chamber"
IRON_ORE = "minecraft:iron_ore"
DUST = "mekanism:dust_iron"
SCENARIOS = (
    Scenario("chamber_normal", CHAMBER, 50000, (item(0, IRON_ORE, 8),), 420),
    Scenario("chamber_last_item", CHAMBER, 50000, (item(0, IRON_ORE, 1),), 210),
    Scenario(
        "chamber_low_energy", CHAMBER, 12, (item(0, IRON_ORE, 8),), 30,
        ((10, f"data modify block {AT} energy_container.stored set value 1000L"),),
    ),
    Scenario(
        "chamber_full_output", CHAMBER, 50000, (item(0, IRON_ORE, 8), item(1, DUST, 63)), 30,
        ((10, f"data modify block {AT} items[1].stored.amount set value 1L"),),
    ),
    Scenario("chamber_other_output", CHAMBER, 50000,
             (item(0, IRON_ORE, 8), item(1, "mekanism:dust_gold", 1)), 20),
    Scenario("chamber_take_input", CHAMBER, 50000, (item(0, IRON_ORE, 8),), 60,
             ((50, f"data modify block {AT} items[0].stored.amount set value 0L"),)),
    Scenario(
        "chamber_swap_input", CHAMBER, 50000, (item(0, IRON_ORE, 8),), 60,
        ((50, f'data modify block {AT} items[0].stored.type.id set value "minecraft:gold_ore"'),),
    ),
    Scenario("chamber_no_recipe", CHAMBER, 50000, (item(0, "minecraft:stick", 8),), 20),
    Scenario("crusher_normal", "mekanism:crusher", 50000, (item(0, "minecraft:cobblestone", 3),), 210),
    Scenario("smelter_normal", "mekanism:energized_smelter", 50000,
             (item(0, "minecraft:raw_iron", 3),), 210),
)


def field(text: str, pattern: str, default: str = "0") -> str:
    found = re.search(pattern, text)
    return found.group(1) if found else default


def slot(text: str, number: int) -> str:
    found = re.search(
        rf'container: {number}b, stored: \{{amount: (\d+)L, type: \{{id: "([^"]+)"', text
    )
    return f"{found.group(2)}x{found.group(1)}" if found else "-"


def row(tick: int, nbt: str) -> str:
    fields = (
        tick,
        field(nbt, r"progress: (\d+)"),
        field(nbt, r"active_state: (\d)b"),
        field(nbt, r"energy_container: \{stored: (\d+)L"),
        slot(nbt, INPUT_SLOT),
        slot(nbt, OUTPUT_SLOT),
    )
    return "\t".join(map(str, fields))


def place(rcon: java_server.Rcon, scenario: Scenario) -> None:
    rcon.command("tick unfreeze")
    rcon.command(f"setblock {AT} air")
    rcon.command("tick freeze")
    nbt = (
        f"{{component_config:{{config0:{ALL_SIDES},config3:{ALL_SIDES}}},"
        f"energy_container:{{stored:{scenario.energy}L}},items:[{','.join(scenario.items)}]}}"
    )
    answer = rcon.command(f"setblock {AT} {scenario.block}{nbt}")
    if "Changed" not in answer:
        raise SystemExit(f"{scenario.name}: setblock answered {answer}")


def record(rcon: java_server.Rcon, scenario: Scenario) -> None:
    place(rcon, scenario)
    changes = dict(scenario.changes)
    lines = [HEADER]
    for tick in range(1, scenario.ticks + 1):
        if tick in changes:
            answer = rcon.command(changes[tick])
            if "Modified" not in answer and "Removed" not in answer:
                raise SystemExit(f"{scenario.name}: {changes[tick]} answered {answer}")
        java_server.step(rcon)
        lines.append(row(tick, rcon.command(f"data get block {AT}")))
    (OUT / f"{scenario.name}.tsv").write_text("\n".join(lines) + "\n")
    print(scenario.name, lines[-1])


def main() -> int:
    OUT.mkdir(exist_ok=True)
    rcon, tunnel = java_server.connect()
    try:
        rcon.command("save-off")
        rcon.command("forceload add 0 0")
        rcon.command("setblock 0 101 0 air")
        for scenario in SCENARIOS:
            record(rcon, scenario)
        rcon.command("tick unfreeze")
    finally:
        tunnel.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
