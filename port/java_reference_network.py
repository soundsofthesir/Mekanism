#!/usr/bin/env python3
"""Records cable networks and the ore-to-ingots chain from the real mod into port/reference/.

    python3 port/java_server.py start --eula
    python3 port/java_reference_network.py
    python3 port/java_server.py stop

The chain's power runs out before the restart, so nothing changes in the unknown number of ticks
between the server starting and `tick freeze`. A command then adds energy, and it must carry on from
exactly the state it saved.
"""

import re
import sys
import time
from pathlib import Path
from typing import Callable

sys.dont_write_bytecode = True
import java_server  # noqa: E402

OUT = Path(__file__).resolve().parent / "reference"
Y = 100
ALL_IN = "[I;1,1,1,1,1,1]"
ALL_OUT = "[I;4,4,4,4,4,4]"
# RelativeSide order: front, left, right, back, top, bottom.
FRONT_OUT = "[I;4,1,1,1,1,1]"
BOTTOM_OUT = "[I;1,1,1,1,1,4]"
CUBE = "mekanism:basic_energy_cube"
CABLE = "mekanism:basic_universal_cable"
CHAMBER = "mekanism:enrichment_chamber"
SMELTER = "mekanism:energized_smelter"
GENERATOR = "mekanismgenerators:heat_generator"
LAVA = '[{container:0b,stored:{amount:%dL,type:{id:"minecraft:lava"}}}]'


def get(text: str, pattern: str, default: str = "0") -> str:
    found = re.search(pattern, text)
    return found.group(1) if found else default


def energy(nbt: str) -> str:
    return get(nbt, r"energy_container: \{stored: (\d+)L")


def cable(nbt: str) -> str:
    return get(nbt, r"\benergy: (\d+)L")


def source_cube(stored: int, config: str = ALL_OUT) -> str:
    return (
        f"{CUBE}{{component_config:{{config0:{config},eject0:1b}},"
        f"energy_container:{{stored:{stored}L}}}}"
    )


def input_cube() -> str:
    return f"{CUBE}{{component_config:{{config0:{ALL_IN}}}}}"


def input_machine(block: str, items: str = "", item_config: str = ALL_IN) -> str:
    extra = f",items:[{items}]" if items else ""
    return f"{block}{{component_config:{{config0:{ALL_IN},config3:{item_config}}}{extra}}}"


class Rig:
    def __init__(self, rcon: java_server.Rcon) -> None:
        self.rcon = rcon

    def clear(self, box: str) -> None:
        self.rcon.command("tick unfreeze")
        self.rcon.command(f"fill {box} air")
        self.rcon.command("tick freeze")

    def place(self, x: int, y: int, z: int, block: str) -> None:
        answer = self.rcon.command(f"setblock {x} {y} {z} {block}")
        if "Changed" not in answer:
            raise SystemExit(f"setblock {x} {y} {z} {block}: {answer}")

    def nbt(self, x: int, y: int, z: int) -> str:
        return self.rcon.command(f"data get block {x} {y} {z}")


def record(rig: Rig, name: str, header: str, ticks: int, read: Callable[[], tuple]) -> None:
    lines = [header]
    for tick in range(1, ticks + 1):
        java_server.step(rig.rcon)
        lines.append("\t".join(map(str, (tick, *read()))))
    (OUT / f"{name}.tsv").write_text("\n".join(lines) + "\n")
    print(name, lines[-1])


def split_targets(rig: Rig) -> None:
    rig.clear(f"0 {Y} 0 5 {Y} 2")
    for x in (1, 2, 3):
        rig.place(x, Y, 0, CABLE)
    rig.place(1, Y, 1, input_machine(CHAMBER))
    rig.place(2, Y, 1, input_cube())
    rig.place(3, Y, 1, input_cube())
    rig.place(4, Y, 0, input_machine(CHAMBER))
    rig.place(0, Y, 0, source_cube(200000))

    def read() -> tuple:
        return (
            energy(rig.nbt(0, Y, 0)),
            *(cable(rig.nbt(x, Y, 0)) for x in (1, 2, 3)),
            energy(rig.nbt(1, Y, 1)),
            energy(rig.nbt(2, Y, 1)),
            energy(rig.nbt(3, Y, 1)),
            energy(rig.nbt(4, Y, 0)),
        )

    header = "tick\tsource\tcable1\tcable2\tcable3\tchamber_a\tcube_b\tcube_c\tchamber_d"
    record(rig, "network_split", header, 30, read)


def small_amounts(rig: Rig) -> None:
    """Less than the targets want, split unevenly by a remainder."""
    rig.clear(f"8 {Y} 0 12 {Y} 2")
    rig.place(9, Y, 0, CABLE)
    rig.place(9, Y, 1, input_cube())
    rig.place(10, Y, 0, input_cube())
    rig.place(8, Y, 0, source_cube(7))

    def read() -> tuple:
        return (
            energy(rig.nbt(8, Y, 0)),
            cable(rig.nbt(9, Y, 0)),
            energy(rig.nbt(9, Y, 1)),
            energy(rig.nbt(10, Y, 0)),
        )

    record(rig, "network_remainder", "tick\tsource\tcable\tcube_a\tcube_b", 8, read)


def cube_to_cube(rig: Rig) -> None:
    rig.clear(f"16 {Y} 0 18 {Y} 1")
    rig.place(17, Y, 0, input_cube())
    rig.place(16, Y, 0, source_cube(10000))

    def read() -> tuple:
        return energy(rig.nbt(16, Y, 0)), energy(rig.nbt(17, Y, 0))

    record(rig, "cube_to_cube", "tick\tsource\tdest", 6, read)


def generator_to_cube(rig: Rig) -> None:
    rig.clear(f"24 {Y} 0 26 {Y} 1")
    rig.place(25, Y, 0, input_cube())
    tank = "{fluid_tanks:" + LAVA % 1000 + "}"
    rig.place(24, Y, 0, f"{GENERATOR}[facing=east]{tank}")

    def read() -> tuple:
        generator = rig.nbt(24, Y, 0)
        return (
            get(generator, r"heat: ([\d.E-]+)d"),
            energy(generator),
            get(generator, r"amount: (\d+)L"),
            energy(rig.nbt(25, Y, 0)),
        )

    record(rig, "generator_to_cube", "tick\theat\tgenerator\tlava\tcube", 60, read)


# The chain, in its own chunk.
GENERATOR_AT = (50, Y, 40)
CUBE_AT = (51, Y, 40)
CABLES = ((52, Y, 40), (53, Y, 40), (53, Y - 1, 40), (53, Y - 2, 40))
CHAMBER_AT = (53, Y, 39)
HOPPER_AT = (53, Y - 1, 39)
SMELTER_AT = (53, Y - 2, 39)
CHAIN_POWER = 1500
RESUMED_POWER = 20000
CHAIN_TICKS_BEFORE = 700
CHAIN_TICKS_AFTER = 900
SETTLE_SECONDS = 2
CHUNK_SETTLE_SECONDS = 5
CHAIN_HEADER = (
    "tick\tcube\tcables\tchamber_energy\tchamber_progress\tchamber_active\tchamber_input\t"
    "chamber_output\thopper\tsmelter_energy\tsmelter_progress\tsmelter_active\tsmelter_input\t"
    "smelter_output\tgenerator_energy\tlava"
)


def slot(text: str, number: int) -> str:
    found = re.search(rf'container: {number}b, stored: \{{amount: (\d+)L, type: \{{id: "([^"]+)"', text)
    return f"{found.group(2)}x{found.group(1)}" if found else "-"


def hopper(text: str) -> str:
    stacks = re.findall(r'\{count: (\d+), Slot: (\d+)b, id: "([^"]+)"\}', text)
    return ",".join(f"{item}x{count}" for count, _, item in stacks) or "-"


def chain_row(rig: Rig) -> tuple:
    chamber = rig.nbt(*CHAMBER_AT)
    smelter = rig.nbt(*SMELTER_AT)
    generator = rig.nbt(*GENERATOR_AT)
    return (
        energy(rig.nbt(*CUBE_AT)),
        sum(int(cable(rig.nbt(*at))) for at in CABLES),
        energy(chamber),
        get(chamber, r"progress: (\d+)"),
        get(chamber, r"active_state: (\d)b"),
        slot(chamber, 0),
        slot(chamber, 1),
        hopper(rig.nbt(*HOPPER_AT)),
        energy(smelter),
        get(smelter, r"progress: (\d+)"),
        get(smelter, r"active_state: (\d)b"),
        slot(smelter, 0),
        slot(smelter, 1),
        energy(generator),
        get(generator, r"amount: (\d+)L"),
    )


def chain_place(rig: Rig) -> None:
    rig.rcon.command("tick unfreeze")
    rig.rcon.command("forceload add 48 32 63 47")
    time.sleep(CHUNK_SETTLE_SECONDS)
    rig.clear(f"48 {Y - 4} 36 58 {Y + 2} 44")
    for at in CABLES:
        rig.place(*at, CABLE)
    rig.place(*SMELTER_AT, input_machine(SMELTER))
    rig.place(*HOPPER_AT, "minecraft:hopper")
    ore = '{container:0b,stored:{amount:2L,type:{id:"minecraft:iron_ore"}}}'
    rig.place(*CHAMBER_AT, input_machine(CHAMBER, ore, BOTTOM_OUT))
    rig.place(*CUBE_AT, f"{CUBE}[facing=east]{{component_config:{{config0:{FRONT_OUT},eject0:1b}},"
              f"energy_container:{{stored:{CHAIN_POWER}L}}}}")
    tank = "{fluid_tanks:" + LAVA % 200 + "}"
    rig.place(*GENERATOR_AT, f"{GENERATOR}[facing=east]{tank}")


def chain(rig: Rig) -> list[str]:
    chain_place(rig)
    lines = [CHAIN_HEADER]
    for tick in range(1, CHAIN_TICKS_BEFORE + 1):
        java_server.step(rig.rcon)
        lines.append("\t".join(map(str, (tick, *chain_row(rig)))))
    (OUT / "chain_before_reload.tsv").write_text("\n".join(lines) + "\n")
    print("chain before", lines[-1])
    return lines


def chain_after(rig: Rig) -> None:
    rig.rcon.command("tick freeze")
    # One row at once, as the restart left it, then more power by command.
    lines = [CHAIN_HEADER, "\t".join(map(str, (0, *chain_row(rig))))]
    x, y, z = CUBE_AT
    rig.rcon.command(f"data modify block {x} {y} {z} energy_container.stored set value {RESUMED_POWER}L")
    for tick in range(1, CHAIN_TICKS_AFTER + 1):
        java_server.step(rig.rcon)
        lines.append("\t".join(map(str, (tick, *chain_row(rig)))))
    (OUT / "chain_after_reload.tsv").write_text("\n".join(lines) + "\n")
    print("chain after", lines[1], "...", lines[-1])


def main() -> int:
    rcon, tunnel = java_server.connect()
    try:
        rig = Rig(rcon)
        rcon.command("save-off")
        rcon.command("tick unfreeze")
        rcon.command("forceload add 0 0 31 15")
        # A chunk just force loaded takes a moment to start ticking.
        time.sleep(CHUNK_SETTLE_SECONDS)
        split_targets(rig)
        small_amounts(rig)
        cube_to_cube(rig)
        generator_to_cube(rig)
        chain(rig)
        rcon.command("tick unfreeze")
        rcon.command("save-on")
        rcon.command("save-all flush")
        time.sleep(SETTLE_SECONDS)
    finally:
        tunnel.terminate()
    java_server.restart()
    rcon, tunnel = java_server.connect()
    try:
        rcon.command("save-off")
        chain_after(Rig(rcon))
        rcon.command("tick unfreeze")
    finally:
        tunnel.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
