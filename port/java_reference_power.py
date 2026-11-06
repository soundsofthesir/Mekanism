#!/usr/bin/env python3
"""Records the Heat Generator and an energy chain from the real mod into port/reference/.

    python3 port/java_server.py start --eula
    python3 port/java_reference_power.py
    python3 port/java_server.py stop

Side config indexes follow `TransmissionType`: config0 is energy and config3 is items. Side values
follow `DataType`: 1 is input and 4 is output.
"""

import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import java_server  # noqa: E402

OUT = Path(__file__).resolve().parent / "reference"
Y = 100
GENERATOR = "mekanismgenerators:heat_generator"
LAVA_TANK = '[{container:0b,stored:{amount:%dL,type:{id:"minecraft:lava"}}}]'
ALL_INPUT = "[I;1,1,1,1,1,1]"
ALL_OUTPUT = "[I;4,4,4,4,4,4]"
CHAIN_TICKS = 60


def get(text: str, pattern: str, default: str = "0") -> str:
    found = re.search(pattern, text)
    return found.group(1) if found else default


def clear(rcon: java_server.Rcon, x_range: range, z: int = 0) -> None:
    for x in x_range:
        rcon.command(f"setblock {x} {Y} {z} air")
        rcon.command(f"setblock {x} {Y + 1} {z} air")


def generator_row(tick: int, nbt: str) -> str:
    fields = (
        tick,
        get(nbt, r"heat: ([\d.E-]+)d"),
        get(nbt, r"energy_container: \{stored: (\d+)L"),
        get(nbt, r"amount: (\d+)L"),
        get(nbt, r"active_state: (\d)b"),
    )
    return "\t".join(map(str, fields))


def record_generator(rcon: java_server.Rcon, name: str, lava: int, ticks: int, lava_above: bool) -> None:
    at = f"0 {Y} 0"
    rcon.command("tick unfreeze")
    clear(rcon, range(0, 2))
    rcon.command("tick freeze")
    tank = f"{{fluid_tanks:{LAVA_TANK % lava}}}" if lava else ""
    rcon.command(f"setblock {at} {GENERATOR}{tank}")
    if lava_above:
        rcon.command(f"setblock 0 {Y + 1} 0 minecraft:lava")
    lines = ["tick\theat\tenergy\tlava\tactive"]
    for tick in range(1, ticks + 1):
        java_server.step(rcon)
        lines.append(generator_row(tick, rcon.command(f"data get block {at}")))
    (OUT / f"{name}.tsv").write_text("\n".join(lines) + "\n")
    print(name, lines[-1])


def energy_of(rcon: java_server.Rcon, x: int, key: str) -> str:
    nbt = rcon.command(f"data get block {x} {Y} 0")
    return get(nbt, rf"{key}(\d+)L")


def record_chain(rcon: java_server.Rcon) -> None:
    rcon.command("tick unfreeze")
    clear(rcon, range(4, 8))
    rcon.command("tick freeze")
    rcon.command(f"setblock 5 {Y} 0 mekanism:basic_universal_cable")
    items = '[{container:0b,stored:{amount:8L,type:{id:"minecraft:iron_ore"}}}]'
    rcon.command(
        f"setblock 6 {Y} 0 mekanism:enrichment_chamber{{component_config:"
        f"{{config0:{ALL_INPUT},config3:{ALL_INPUT}}},items:{items}}}"
    )
    rcon.command(
        f"setblock 4 {Y} 0 mekanism:basic_energy_cube{{component_config:"
        f"{{config0:{ALL_OUTPUT},eject0:1b}},energy_container:{{stored:200000L}}}}"
    )
    lines = ["tick\tcube\tcable\tchamber\tprogress"]
    for tick in range(1, CHAIN_TICKS + 1):
        java_server.step(rcon)
        chamber = rcon.command(f"data get block 6 {Y} 0")
        lines.append(
            "\t".join(
                map(
                    str,
                    (
                        tick,
                        energy_of(rcon, 4, r"energy_container: \{stored: "),
                        energy_of(rcon, 5, r"energy: "),
                        get(chamber, r"energy_container: \{stored: (\d+)L"),
                        get(chamber, r"progress: (\d+)"),
                    ),
                )
            )
        )
    (OUT / "chain_cube_cable_chamber.tsv").write_text("\n".join(lines) + "\n")
    print("chain", lines[-1])


def main() -> int:
    rcon, tunnel = java_server.connect()
    try:
        rcon.command("save-off")
        rcon.command("forceload add 0 0")
        record_generator(rcon, "heat_generator_idle", 0, 30, False)
        record_generator(rcon, "heat_generator_lava", 1000, 40, False)
        record_generator(rcon, "heat_generator_lava_above", 0, 30, True)
        record_chain(rcon)
        rcon.command("tick unfreeze")
    finally:
        tunnel.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
