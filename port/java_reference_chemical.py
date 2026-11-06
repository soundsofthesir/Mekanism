#!/usr/bin/env python3
"""Records the real mod's chemicals into port/reference/: the Chemical Oxidizer, the basic Pressurized
Tube and the basic Chemical Tank.

    python3 port/java_server.py start --eula
    python3 port/java_reference_chemical.py
    python3 port/java_server.py stop

Each scenario lists blocks along x at y 100 and z 0. A row holds one game tick, with the same fields
per block. `chem` is `id x amount`, or `-`. Side values follow `DataType`: 1 is input and 4 is output.
config2 is the chemical side config.
"""

import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.dont_write_bytecode = True
import java_server  # noqa: E402

OUT = Path(__file__).resolve().parent / "reference"
Y = 100
OXIDIZER = "mekanism:chemical_oxidizer"
TUBE = "mekanism:basic_pressurized_tube"
TANK = "mekanism:basic_chemical_tank"
SO2 = "mekanism:sulfur_dioxide"
HYDROGEN = "mekanism:hydrogen"
SULFUR = "mekanism:dust_sulfur"
ALL_IN = "[I;1,1,1,1,1,1]"
ALL_OUT = "[I;4,4,4,4,4,4]"
FIELDS = ("progress", "active", "energy", "input", "chem", "used")


def chemical(name: str, amount: int) -> str:
    return f'chemical_tanks:[{{container:0b,stored:{{amount:{amount}L,type:"{name}"}}}}]'


def oxidizer(item: str | None = SULFUR, count: int = 3, energy: int = 50000, eject: bool = False,
             tank: str = "") -> str:
    chem = f",config2:{ALL_OUT},eject2:1b" if eject else ""
    items = f'items:[{{container:0b,stored:{{amount:{count}L,type:{{id:"{item}"}}}}}}],' if item else ""
    extra = f",{tank}" if tank else ""
    return (
        f"{OXIDIZER}{{component_config:{{config0:{ALL_IN}{chem}}},"
        f"{items}energy_container:{{stored:{energy}L}}{extra}}}"
    )


def tank(side: str = ALL_IN, eject: bool = False, name: str = "", amount: int = 0) -> str:
    held = f",{chemical(name, amount)}" if name else ""
    return f"{TANK}{{component_config:{{config2:{side},eject2:{int(eject)}b}}{held}}}"


class Scenario(NamedTuple):
    name: str
    blocks: tuple[str, ...]
    ticks: int
    # (tick, command): run just before that tick.
    changes: tuple[tuple[int, str], ...] = ()
    restart_after: int = 0


SOURCE = tank(ALL_OUT, True, SO2, 8000)
SCENARIOS = (
    Scenario("oxidizer_normal", (oxidizer(),), 320),
    Scenario("oxidizer_last_item", (oxidizer(count=1),), 110),
    Scenario("oxidizer_low_energy", (oxidizer(energy=32),), 30,
             ((10, "data modify block 0 100 0 energy_container.stored set value 1000L"),)),
    Scenario("oxidizer_full_tank", (oxidizer(tank=chemical(SO2, 9950)),), 120),
    Scenario("oxidizer_other_chemical", (oxidizer(tank=chemical(HYDROGEN, 100)),), 120),
    Scenario("oxidizer_no_recipe", (oxidizer(item="minecraft:stick"),), 20),
    Scenario("tube_chain", (oxidizer(eject=True), TUBE, TUBE, TUBE, tank()), 240),
    Scenario("tube_rate", (SOURCE, TUBE, tank()), 30),
    Scenario("tube_fills", (tank(ALL_OUT, True, SO2, 20000), TUBE, TUBE), 30),
    Scenario("tube_target_full", (SOURCE, TUBE, tank(name=SO2, amount=63500)), 30),
    Scenario("tube_target_other", (SOURCE, TUBE, tank(name=HYDROGEN, amount=100)), 30),
    Scenario("tube_no_eject", (tank(ALL_OUT, False, SO2, 8000), TUBE, tank()), 10),
    Scenario("tube_input_side_closed", (SOURCE, TUBE, tank("[I;0,0,0,0,0,0]")), 10),
    # One tube between two tanks with a source above it, so the network splits what it gets.
    Scenario("tube_split", (tank(), TUBE, tank()), 6,
             ((1, f"setblock 1 {Y + 1} 0 {tank(ALL_OUT, True, SO2, 1001)}"),)),
    Scenario("tube_split_room", (tank(name=SO2, amount=63900), TUBE, tank()), 6,
             ((1, f"setblock 1 {Y + 1} 0 {tank(ALL_OUT, True, SO2, 1000)}"),)),
    Scenario("tube_shares_restart", (tank(ALL_OUT, True, SO2, 5000), TUBE, TUBE, TUBE), 30,
             restart_after=12),
)


def get(text: str, pattern: str, default: str = "0") -> str:
    found = re.search(pattern, text)
    return found.group(1) if found else default


def stack(text: str, key: str) -> str:
    found = re.search(key + r': \[?\{(?:container: 0b, stored: \{)?amount: (\d+)L, (?:type|id): "([^"]+)"', text)
    return f"{found.group(2)}x{found.group(1)}" if found else "-"


def block_fields(nbt: str) -> list[str]:
    tube = re.search(r'stored: \{amount: (\d+)L, id: "([^"]+)"', nbt) or re.search(
        r'stored: \{amount: (\d+)L, type: "([^"]+)"', nbt
    )
    if '"mekanism:basic_pressurized_tube"' in nbt:
        chem = f"{tube.group(2)}x{tube.group(1)}" if tube else "-"
    else:
        chem = stack(nbt, "chemical_tanks")
    item = re.search(r'items: \[\{container: 0b, stored: \{amount: (\d+)L, type: \{id: "([^"]+)"', nbt)
    used = re.search(r'recipes_used: \{"[^"]+": (\d+)\}', nbt)
    return [
        get(nbt, r"progress: (\d+)"),
        get(nbt, r"active_state: (\d)b"),
        get(nbt, r"energy_container: \{stored: (\d+)L"),
        f"{item.group(2)}x{item.group(1)}" if item else "-",
        chem,
        used.group(1) if used else "0",
    ]


def row(rcon: java_server.Rcon, tick: int, count: int) -> str:
    cells = [str(tick)]
    for x in range(count):
        cells += block_fields(rcon.command(f"data get block {x} {Y} 0"))
    return "\t".join(cells)


def record(rcon: java_server.Rcon, scenario: Scenario) -> None:
    rcon.command("tick unfreeze")
    for x in range(8):
        rcon.command(f"setblock {x} {Y} 0 air")
    rcon.command(f"setblock 1 {Y + 1} 0 air")
    rcon.command("tick freeze")
    for x, block in enumerate(scenario.blocks):
        answer = rcon.command(f"setblock {x} {Y} 0 {block}")
        if "Changed" not in answer:
            raise SystemExit(f"{scenario.name}: setblock answered {answer}")
    count = len(scenario.blocks)
    header = ["tick"] + [f"{x}_{name}" for x in range(count) for name in FIELDS]
    lines = ["\t".join(header)]
    changes = dict(scenario.changes)
    for tick in range(1, scenario.ticks + 1):
        if tick in changes:
            answer = rcon.command(changes[tick])
            if "Modified" not in answer and "Changed" not in answer:
                raise SystemExit(f"{scenario.name}: {changes[tick]} answered {answer}")
        java_server.step(rcon)
        lines.append(row(rcon, tick, count))
        if tick == scenario.restart_after:
            (OUT / f"{scenario.name}_saved.txt").write_text(
                "\n".join(rcon.command(f"data get block {x} {Y} 0") for x in range(count)) + "\n"
            )
            rcon.command("save-all flush")
            rcon, tunnel = restart(rcon)
            lines.append(row(rcon, -1, count))
    (OUT / f"{scenario.name}.tsv").write_text("\n".join(lines) + "\n")
    print(scenario.name, lines[-1])
    return rcon


def restart(rcon):
    global TUNNEL
    rcon.command("tick unfreeze")
    TUNNEL.terminate()
    java_server.restart()
    rcon, TUNNEL = java_server.connect()
    rcon.command("tick freeze")
    return rcon, TUNNEL


def main() -> int:
    global TUNNEL
    OUT.mkdir(exist_ok=True)
    rcon, TUNNEL = java_server.connect()
    try:
        rcon.command("forceload add 0 0")
        wanted = sys.argv[1:]
        for scenario in SCENARIOS:
            if not wanted or scenario.name in wanted:
                rcon = record(rcon, scenario) or rcon
        rcon.command("tick unfreeze")
    finally:
        TUNNEL.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
