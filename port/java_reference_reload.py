#!/usr/bin/env python3
"""Records machines through a real save and reload from the real mod into `port/reference/`.

    python3 port/java_reference_reload.py
    python3 port/java_reference_reload.py unload

Needs `java_server.py`'s server running on Tower, which it restarts. Each scenario places a machine
with no supply, so nothing changes in the unknown number of ticks around the restart. Row -1 is the
machine before the restart and row 0 is as the restart left it. A full cube then goes beside it, and
one row a tick after that shows what the machine now holds. `live_output_emptied` has the same rows
with no restart, to compare what an emptied machine holds before a reload. `unload` needs no restart:
it places machines far from anything, removes the chunk's force load, waits until a read says the
position isn't loaded, loads it again and has the same rows.
"""

import sys
import time
from pathlib import Path
from typing import NamedTuple

import java_server
from java_reference_features import CUBE_FULL, ORES, Y, get, machine, slot, split_upgrades, upgrade_stack

OUT = Path(__file__).resolve().parent / "reference"
HEADER = ["tick", "progress", "active", "energy", "input", "output", "component", "speed", "energy_upgrades"]
TICKS = 30
SAVE_SECONDS = 3


class Scenario(NamedTuple):
    name: str
    block: str
    # A command run once on the placed machine, with {at} for its position.
    change: str = ""


def with_empty_component(block: str) -> str:
    return block.replace("{", "{component_upgrade:{},", 1)


def with_output_slot(block: str) -> str:
    """Two speed upgrades in the upgrade output slot and none installed, as an uninstall leaves it."""
    return block.replace("{", f"{{component_upgrade:{{items:[{upgrade_stack('speed', 2).replace('container:0b', 'container:1b')}]}},", 1)


SCENARIOS = (
    Scenario("reload_fresh_empty", machine()),
    Scenario("reload_fresh_energy", machine(energy=15)),
    Scenario("reload_fresh_ore", machine(items=ORES)),
    Scenario("reload_empty_component", with_empty_component(machine(energy=15))),
    Scenario("reload_speed4", machine(speed=4, energy=15)),
    Scenario("reload_output_slot", with_output_slot(machine(energy=15))),
    Scenario(
        "reload_output_emptied", with_output_slot(machine(energy=15)),
        "data modify block {at} component_upgrade.items[0].stored.amount set value 0L",
    ),
)


LIVE = Scenario(SCENARIOS[-1].name.replace("reload", "live"), SCENARIOS[-1].block, SCENARIOS[-1].change)


def live(rcon: java_server.Rcon) -> list[list[str]]:
    """Frozen, so the placed machine has not ticked, as a loaded one hasn't."""
    x, z = at(len(SCENARIOS))
    rcon.command(f"setblock {x} {Y} {z} {LIVE.block}")
    rcon.command(LIVE.change.format(at=f"{x} {Y} {z}"))
    rows = [row(rcon, 0, x, z)]
    rcon.command(f"setblock {x + 1} {Y} {z} {CUBE_FULL}")
    for tick in range(1, TICKS + 1):
        java_server.step(rcon)
        rows.append(row(rcon, tick, x, z))
    return rows


UNLOAD_AT = (1024, 1024)
UNLOAD_SCENARIOS = (
    Scenario("unload_output_emptied", SCENARIOS[-1].block, SCENARIOS[-1].change),
    Scenario("unload_output_slot", SCENARIOS[-2].block),
    Scenario("unload_fresh_energy", machine(energy=15)),
)
LOAD_TIMEOUT_SECONDS = 120
UNLOADED_SECONDS = 5


def at(index: int) -> tuple[int, int]:
    """Each scenario's machine, far enough apart that no two touch."""
    return 0, index * 4


def row(rcon: java_server.Rcon, tick: int, x: int, z: int) -> list[str]:
    raw = rcon.command(f"data get block {x} {Y} {z}")
    component, nbt = split_upgrades(raw)
    return [
        str(tick),
        get(nbt, r"progress: (\d+)"),
        get(nbt, r"active_state: (\d)b"),
        get(nbt, r"energy_container: \{stored: (\d+)L"),
        slot(nbt, 0),
        slot(nbt, 1),
        "1" if component else "0",
        get(component, r'"mekanism:speed": (\d+)'),
        get(component, r'"mekanism:energy": (\d+)'),
    ]


def wait_loaded(rcon: java_server.Rcon, x: int, z: int, wanted: bool) -> None:
    deadline = time.monotonic() + LOAD_TIMEOUT_SECONDS
    while ("has the following" in rcon.command(f"data get block {x} {Y} {z}")) != wanted:
        if time.monotonic() > deadline:
            raise SystemExit(f"{x} {z} never became {'loaded' if wanted else 'unloaded'}")
        time.sleep(0.5)


def unload(rcon: java_server.Rcon) -> None:
    """Unfrozen until the rows start, because a frozen server doesn't unload what it holds."""
    x, z = UNLOAD_AT
    rcon.command("tick unfreeze")
    rcon.command(f"forceload add {x} {z}")
    time.sleep(SAVE_SECONDS)
    rows: dict[str, list[list[str]]] = {}
    for index, scenario in enumerate(UNLOAD_SCENARIOS):
        at_z = z + index * 4
        rcon.command(f"setblock {x + 1} {Y} {at_z} air")
        rcon.command(f"setblock {x} {Y} {at_z} air")
        answer = rcon.command(f"setblock {x} {Y} {at_z} {scenario.block}")
        if "Changed" not in answer:
            raise SystemExit(f"{scenario.name}: setblock answered {answer}")
        if scenario.change:
            rcon.command(scenario.change.format(at=f"{x} {Y} {at_z}"))
        rows[scenario.name] = [row(rcon, -1, x, at_z)]
    rcon.command(f"forceload remove {x} {z}")
    wait_loaded(rcon, x, z, False)
    time.sleep(UNLOADED_SECONDS)
    rcon.command(f"forceload add {x} {z}")
    wait_loaded(rcon, x, z, True)
    rcon.command("tick freeze")
    for index, scenario in enumerate(UNLOAD_SCENARIOS):
        at_z = z + index * 4
        rows[scenario.name].append(row(rcon, 0, x, at_z))
        rcon.command(f"setblock {x + 1} {Y} {at_z} {CUBE_FULL}")
    for tick in range(1, TICKS + 1):
        java_server.step(rcon)
        for index, scenario in enumerate(UNLOAD_SCENARIOS):
            rows[scenario.name].append(row(rcon, tick, x, z + index * 4))
    rcon.command("tick unfreeze")
    rcon.command(f"forceload remove {x} {z}")
    for name, table in rows.items():
        lines = ["\t".join(HEADER), *("\t".join(each) for each in table)]
        (OUT / f"{name}.tsv").write_text("\n".join(lines) + "\n")
        print(name, *(lines[i].replace("\t", " ") + " |" for i in (1, 2, 3, -1)), flush=True)


def main() -> int:
    rcon, tunnel = java_server.connect()
    if sys.argv[1:] == ["unload"]:
        try:
            unload(rcon)
        finally:
            tunnel.terminate()
        return 0
    tables: dict[str, list[list[str]]] = {}
    try:
        rcon.command("forceload add 0 0 0 31")
        time.sleep(SAVE_SECONDS)
        rcon.command("tick freeze")
        for index, scenario in enumerate(SCENARIOS):
            x, z = at(index)
            rcon.command(f"setblock {x + 1} {Y} {z} air")
            rcon.command(f"setblock {x} {Y} {z} air")
            answer = rcon.command(f"setblock {x} {Y} {z} {scenario.block}")
            if "Changed" not in answer:
                raise SystemExit(f"{scenario.name}: setblock answered {answer}")
            if scenario.change:
                print(scenario.name, "change:", rcon.command(scenario.change.format(at=f"{x} {Y} {z}"))[:200], flush=True)
        for index, scenario in enumerate(SCENARIOS):
            x, z = at(index)
            tables[scenario.name] = [row(rcon, -1, x, z)]
            print(scenario.name, "before:", rcon.command(f"data get block {x} {Y} {z}")[:400], flush=True)
        rcon.command("tick unfreeze")
        rcon.command("save-all flush")
        time.sleep(SAVE_SECONDS)
    finally:
        tunnel.terminate()
    java_server.restart()
    rcon, tunnel = java_server.connect()
    try:
        rcon.command("tick freeze")
        for index, scenario in enumerate(SCENARIOS):
            x, z = at(index)
            tables[scenario.name].append(row(rcon, 0, x, z))
            print(scenario.name, "after:", rcon.command(f"data get block {x} {Y} {z}")[:400], flush=True)
            rcon.command(f"setblock {x + 1} {Y} {z} {CUBE_FULL}")
        for tick in range(1, TICKS + 1):
            java_server.step(rcon)
            for index, scenario in enumerate(SCENARIOS):
                x, z = at(index)
                tables[scenario.name].append(row(rcon, tick, x, z))
        tables[LIVE.name] = live(rcon)
        rcon.command("tick unfreeze")
    finally:
        tunnel.terminate()
    for name, rows in tables.items():
        lines = ["\t".join(HEADER), *("\t".join(each) for each in rows)]
        (OUT / f"{name}.tsv").write_text("\n".join(lines) + "\n")
        print(name, *(lines[i].replace("\t", " ") + " |" for i in (1, 2, 3, -1)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
