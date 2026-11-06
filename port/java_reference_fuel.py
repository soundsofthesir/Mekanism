#!/usr/bin/env python3
"""Records the Heat Generator's fuel slot from the real mod into port/reference/.

    python3 port/java_server.py start --eula
    python3 port/java_reference_fuel.py
    python3 port/java_server.py stop
"""

import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
import java_server  # noqa: E402

OUT = Path(__file__).resolve().parent / "reference"
Y = 100
GENERATOR = "mekanismgenerators:heat_generator"
TICKS = 60
CHUNK_SETTLE_SECONDS = 5
HEADER = "tick\theat\tenergy\tlava\tactive\tfuel"
SCENARIOS = (
    ("generator_fuel_coal", 0, "minecraft:coal", 64),
    ("generator_fuel_bucket", 0, "minecraft:lava_bucket", 1),
    ("generator_fuel_bucket_no_room", 500, "minecraft:lava_bucket", 1),
    ("generator_fuel_blaze_rod", 0, "minecraft:blaze_rod", 2),
    ("generator_fuel_not_fuel", 0, "minecraft:stone", 3),
)


def get(text: str, pattern: str, default: str = "0") -> str:
    found = re.search(pattern, text)
    return found.group(1) if found else default


def fuel(nbt: str) -> str:
    found = re.search(r'items: \[\{container: 0b, stored: \{amount: (\d+)L, type: \{id: "([^"]+)"', nbt)
    return f"{found.group(2)}x{found.group(1)}" if found else "-"


def tank(nbt: str) -> str:
    return get(nbt, r'fluid_tanks: \[\{container: 0b, stored: \{amount: (\d+)L')


def record(rcon: java_server.Rcon, name: str, lava: int, item: str, count: int) -> None:
    at = f"0 {Y} 0"
    rcon.command("tick unfreeze")
    rcon.command(f"setblock {at} air")
    rcon.command("tick freeze")
    fluids = (
        f'fluid_tanks:[{{container:0b,stored:{{amount:{lava}L,type:{{id:"minecraft:lava"}}}}}}],'
        if lava
        else ""
    )
    stored = f'items:[{{container:0b,stored:{{amount:{count}L,type:{{id:"{item}"}}}}}}]'
    answer = rcon.command(f"setblock {at} {GENERATOR}{{{fluids}{stored}}}")
    if "Changed" not in answer:
        raise SystemExit(f"{name}: {answer}")
    lines = [HEADER]
    for tick in range(1, TICKS + 1):
        java_server.step(rcon)
        nbt = rcon.command(f"data get block {at}")
        fields = (
            tick,
            get(nbt, r"heat: ([\d.E-]+)d"),
            get(nbt, r"energy_container: \{stored: (\d+)L"),
            tank(nbt),
            get(nbt, r"active_state: (\d)b"),
            fuel(nbt),
        )
        lines.append("\t".join(map(str, fields)))
    (OUT / f"{name}.tsv").write_text("\n".join(lines) + "\n")
    print(name, lines[1], "|", lines[-1])


def main() -> int:
    rcon, tunnel = java_server.connect()
    try:
        rcon.command("save-off")
        rcon.command("forceload add 0 0")
        time.sleep(CHUNK_SETTLE_SECONDS)
        for name, lava, item, count in SCENARIOS:
            record(rcon, name, lava, item, count)
        rcon.command("tick unfreeze")
    finally:
        tunnel.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
