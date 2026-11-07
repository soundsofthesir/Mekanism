#!/usr/bin/env python3
"""Records the Mechanical Pipe and the Fluid Tank from the real mod into `port/reference/`.

    python3 port/java_reference_pipe.py [scenario ...]

A scenario's blocks stack upwards from `Y` at x = 0: a tank emits only downwards. Each row holds what
every block holds.
"""

import re
import sys
from pathlib import Path
from typing import NamedTuple

import java_server

OUT = Path(__file__).resolve().parent / "reference"
Y = 200
TIERS = ("basic", "advanced", "elite", "ultimate")
WATER = "minecraft:water"
LAVA = "minecraft:lava"
FULL_ULTIMATE = 256_000


class Scenario(NamedTuple):
    name: str
    blocks: tuple[str, ...]
    ticks: int


def tank(tier: str, stored: int = 0, active: bool = False, fluid: str = WATER) -> str:
    """`active_state` is what a configurator's auto-eject sets, and a tank emits only then."""
    held = f'fluid_tanks:[{{container:0b,stored:{{amount:{stored}L,type:{{id:"{fluid}"}}}}}}],' if stored else ""
    return f"mekanism:{tier}_fluid_tank{{{held}active_state:{int(active)}b}}"


def pipe(tier: str) -> str:
    return f"mekanism:{tier}_mechanical_pipe"


SOURCE = tank("ultimate", FULL_ULTIMATE, True)
TARGET = tank("ultimate")
SCENARIOS = (
    *(Scenario(f"pipe_{tier}", (TARGET, pipe(tier), SOURCE), 8) for tier in TIERS),
    Scenario("pipe_chain", (TARGET, pipe("basic"), pipe("basic"), SOURCE), 8),
    Scenario("pipe_fills_target", (tank("basic"), pipe("ultimate"), SOURCE), 12),
    Scenario("pipe_slow_source", (TARGET, pipe("ultimate"), tank("basic", 32_000, True)), 8),
    Scenario("pipe_mid_source", (TARGET, pipe("ultimate"), tank("elite", 128_000, True)), 8),
    Scenario("pipe_mixed", (TARGET, pipe("basic"), pipe("ultimate"), SOURCE), 8),
    Scenario("pipe_other_fluid", (tank("ultimate", 100, False, LAVA), pipe("basic"), SOURCE), 8),
    *(Scenario(f"fluid_tank_{tier}", (TARGET, tank(tier, 32_000, True)), 8) for tier in TIERS),
    Scenario("fluid_tank_inactive", (TARGET, tank("ultimate", 32_000)), 4),
    Scenario("fluid_tank_full_below", (tank("basic", 31_000), tank("ultimate", 32_000, True)), 4),
)


def amount(nbt: str) -> str:
    found = re.search(r"\bstored: \{amount: (\d+)L", nbt)
    return found.group(1) if found else "0"


def read(rcon, tick: int, count: int) -> str:
    return "\t".join([str(tick), *(amount(rcon.command(f"data get block 0 {Y + y} 0")) for y in range(count))])


def record(rcon, scenario: Scenario) -> None:
    rcon.command("tick unfreeze")
    for y in range(6):
        rcon.command(f"setblock 0 {Y + y} 0 air")
    rcon.command("tick freeze")
    for y, block in enumerate(scenario.blocks):
        answer = rcon.command(f"setblock 0 {Y + y} 0 {block}")
        if "Changed" not in answer:
            raise SystemExit(f"{scenario.name}: setblock answered {answer}")
    count = len(scenario.blocks)
    lines = [read(rcon, 0, count)]
    for tick in range(1, scenario.ticks + 1):
        java_server.step(rcon)
        lines.append(read(rcon, tick, count))
    (OUT / f"{scenario.name}.tsv").write_text("\n".join(lines) + "\n")
    print(scenario.name, lines[1].replace("\t", " "), "|", lines[-1].replace("\t", " "), flush=True)


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
