#!/usr/bin/env python3
"""Phase 3 test: cable networks and the ore-to-ingots chain in Horizon against the real mod.

    python3 port/test_chain.py --engine port/.work/machine-export/horizon-engine
    python3 port/test_chain.py --engine port/.work/machine-export/horizon-engine --dedicated --eula

Replays each recording in port/reference/ with the same `tick step` method, and every row must
match. The chain stops for lack of power, the world restarts, and a command adds energy, so the rows
after the restart prove what was saved.
"""

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Callable

from horizon_driver import DedicatedServer, SinglePlayer, TestFailure, install_content, begin_checks, run_test

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"
REFERENCE = HERE / "reference"
Y = 100
STEP_TIMEOUT_SECONDS = 30
CHUNK_SETTLE_SECONDS = 5
# A recording can't show each side's own temperature to the last digit of a float's conversion,
# and heat is the only value compared less than exactly.
HEAT_TOLERANCE = 0.000001
ALL_IN = "[I;1,1,1,1,1,1]"
ALL_OUT = "[I;4,4,4,4,4,4]"
FRONT_OUT = "[I;4,1,1,1,1,1]"
BOTTOM_OUT = "[I;1,1,1,1,1,4]"
CUBE = "mekanism:basic_energy_cube"
CABLE = "mekanism:basic_universal_cable"
CHAMBER = "mekanism:enrichment_chamber"
SMELTER = "mekanism:energized_smelter"
GENERATOR = "mekanismgenerators:heat_generator"
GENERATOR_AT = (50, Y, 40)
CUBE_AT = (51, Y, 40)
CABLES = ((52, Y, 40), (53, Y, 40), (53, Y - 1, 40), (53, Y - 2, 40))
CHAMBER_AT = (53, Y, 39)
HOPPER_AT = (53, Y - 1, 39)
SMELTER_AT = (53, Y - 2, 39)
CHAIN_POWER = 1500
RESUMED_POWER = 20000


def lava(amount: int) -> str:
    return f'fluids:[{{Fluid:"minecraft:lava",Amount:{amount}}}]'


def source_cube(stored: int, config: str = ALL_OUT) -> str:
    return f"{CUBE}{{component_config:{{config0:{config},eject0:1b}},energy:{stored}}}"


def input_cube() -> str:
    return f"{CUBE}{{component_config:{{config0:{ALL_IN}}}}}"


def input_machine(block: str, items: str = "", item_config: str = ALL_IN) -> str:
    extra = f",Items:[{items}]" if items else ""
    return f"{block}{{component_config:{{config0:{ALL_IN},config3:{item_config}}}{extra}}}"


NORMAL_TICK_RATE = 20
# A control request waits for a client frame, on top of the server's tick.
MAX_FPS = 260


class Rig:
    def __init__(self, world) -> None:
        self.world = world

    def text(self, line: str) -> str:
        return " ".join(self.world.command(line))

    def game_time(self) -> int:
        return int(re.search(r"game time is (\d+)", self.text("time query gametime")).group(1))

    def step(self) -> None:
        before = self.game_time()
        self.world.command("tick step 1")
        deadline = time.monotonic() + STEP_TIMEOUT_SECONDS
        while self.game_time() != before + 1:
            if time.monotonic() > deadline:
                raise TestFailure(f"a step did not move game time from {before}")

    def freeze(self) -> None:
        self.world.command("tick freeze")
        self.world.command(f"tick rate {self.world.FAST_TICK_RATE}")

    def unfreeze(self) -> None:
        self.world.command(f"tick rate {NORMAL_TICK_RATE}")
        self.world.command("tick unfreeze")

    def clear(self, box: str) -> None:
        self.unfreeze()
        self.world.command(f"fill {box} air")
        self.freeze()

    def place(self, x: int, y: int, z: int, block: str) -> None:
        answer = self.text(f"setblock {x} {y} {z} {block}")
        if "Changed" not in answer:
            raise TestFailure(f"setblock {x} {y} {z} {block}: {answer}")

    def nbt(self, x: int, y: int, z: int) -> str:
        return self.text(f"data get block {x} {y} {z}")


def get(text: str, pattern: str, default: str = "0") -> str:
    found = re.search(pattern, text)
    return found.group(1) if found else default


def energy(nbt: str) -> str:
    return get(nbt, r"\benergy: (\d+)")


def slot(nbt: str, number: int) -> str:
    for entry in re.findall(r"\{[^{}]*\}", nbt):
        if re.search(rf"\bSlot: {number}b", entry):
            item = re.search(r'id: "([^"]+)"', entry).group(1)
            return f"{item}x{re.search(r'count: (\d+)', entry).group(1)}"
    return "-"


def hopper(nbt: str) -> str:
    stacks = []
    for entry in re.findall(r"\{[^{}]*\}", nbt):
        item = re.search(r'id: "([^"]+)"', entry)
        count = re.search(r"count: (\d+)", entry)
        if item and count:
            stacks.append(f"{item.group(1)}x{count.group(1)}")
    return ",".join(stacks) or "-"


def lava_of(nbt: str) -> str:
    return get(nbt, r"Amount: (\d+)")


def same(field: str, got: str, expected: str) -> bool:
    if field == "heat":
        return abs(float(got) - float(expected)) < HEAT_TOLERANCE
    return got == expected


def replay(rig: Rig, name: str, read: Callable[[], tuple]) -> list[str]:
    expected = (REFERENCE / f"{name}.tsv").read_text().splitlines()
    fields = expected[0].split("\t")
    failures = []
    count = 0
    for line in expected[1:]:
        wanted = line.split("\t")
        if wanted[0] == "0":
            continue
        rig.step()
        got = [wanted[0], *map(str, read())]
        count += 1
        wrong = [i for i, f in enumerate(fields) if not same(f, got[i], wanted[i])]
        if wrong:
            detail = ", ".join(f"{fields[i]} got {got[i]} expected {wanted[i]}" for i in wrong)
            failures.append(f"{name} tick {wanted[0]}: {detail}")
            break
    print(f"  {name}: {count} rows, {'differs' if failures else 'matches'}", flush=True)
    return failures


def network_split(rig: Rig) -> list[str]:
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
            *(energy(rig.nbt(x, Y, 0)) for x in (1, 2, 3)),
            energy(rig.nbt(1, Y, 1)),
            energy(rig.nbt(2, Y, 1)),
            energy(rig.nbt(3, Y, 1)),
            energy(rig.nbt(4, Y, 0)),
        )

    return replay(rig, "network_split", read)


def network_remainder(rig: Rig) -> list[str]:
    rig.clear(f"8 {Y} 0 12 {Y} 2")
    rig.place(9, Y, 0, CABLE)
    rig.place(9, Y, 1, input_cube())
    rig.place(10, Y, 0, input_cube())
    rig.place(8, Y, 0, source_cube(7))

    def read() -> tuple:
        return (
            energy(rig.nbt(8, Y, 0)),
            energy(rig.nbt(9, Y, 0)),
            energy(rig.nbt(9, Y, 1)),
            energy(rig.nbt(10, Y, 0)),
        )

    return replay(rig, "network_remainder", read)


def cube_to_cube(rig: Rig) -> list[str]:
    rig.clear(f"16 {Y} 0 18 {Y} 1")
    rig.place(17, Y, 0, input_cube())
    rig.place(16, Y, 0, source_cube(10000))
    return replay(rig, "cube_to_cube", lambda: (energy(rig.nbt(16, Y, 0)), energy(rig.nbt(17, Y, 0))))


def generator_to_cube(rig: Rig) -> list[str]:
    rig.clear(f"24 {Y} 0 26 {Y} 1")
    rig.place(25, Y, 0, input_cube())
    rig.place(24, Y, 0, f"{GENERATOR}[facing=east]{{{lava(1000)}}}")

    def read() -> tuple:
        generator = rig.nbt(24, Y, 0)
        return (
            get(generator, r"heat: ([\d.E-]+)d"),
            energy(generator),
            lava_of(generator),
            energy(rig.nbt(25, Y, 0)),
        )

    return replay(rig, "generator_to_cube", read)


def chain_row(rig: Rig) -> tuple:
    chamber = rig.nbt(*CHAMBER_AT)
    smelter = rig.nbt(*SMELTER_AT)
    generator = rig.nbt(*GENERATOR_AT)
    return (
        energy(rig.nbt(*CUBE_AT)),
        sum(int(energy(rig.nbt(*at))) for at in CABLES),
        energy(chamber),
        get(chamber, r"progress: (\d+)"),
        get(chamber, r"active_state: (\d)"),
        slot(chamber, 0),
        slot(chamber, 1),
        hopper(rig.nbt(*HOPPER_AT)),
        energy(smelter),
        get(smelter, r"progress: (\d+)"),
        get(smelter, r"active_state: (\d)"),
        slot(smelter, 0),
        slot(smelter, 1),
        energy(generator),
        lava_of(generator),
    )


def chain_place(rig: Rig) -> None:
    rig.unfreeze()
    rig.world.command("forceload add 48 32 63 47")
    time.sleep(CHUNK_SETTLE_SECONDS)
    rig.clear(f"48 {Y - 4} 36 58 {Y + 2} 44")
    for at in CABLES:
        rig.place(*at, CABLE)
    rig.place(*SMELTER_AT, input_machine(SMELTER))
    rig.place(*HOPPER_AT, "minecraft:hopper")
    ore = '{Slot:0b,id:"minecraft:iron_ore",count:2}'
    rig.place(*CHAMBER_AT, input_machine(CHAMBER, ore, BOTTOM_OUT))
    rig.place(
        *CUBE_AT,
        f"{CUBE}[facing=east]{{component_config:{{config0:{FRONT_OUT},eject0:1b}},energy:{CHAIN_POWER}}}",
    )
    rig.place(*GENERATOR_AT, f"{GENERATOR}[facing=east]{{{lava(200)}}}")


def run(world) -> None:
    rig = Rig(world)
    world.start()
    if world.has_player:
        world.ctl("options-set", "maxFps", MAX_FPS)
    rig.unfreeze()
    world.command("forceload add 0 0 31 15")
    time.sleep(CHUNK_SETTLE_SECONDS)
    begin_checks()
    failures = []
    for scenario in (network_split, network_remainder, cube_to_cube, generator_to_cube):
        failures += scenario(rig)
    chain_place(rig)
    failures += replay(rig, "chain_before_reload", lambda: chain_row(rig))
    rig.unfreeze()
    world.stop()
    world.start()
    rig.freeze()
    x, y, z = CUBE_AT

    def read_after() -> tuple:
        return chain_row(rig)

    expected = (REFERENCE / "chain_after_reload.tsv").read_text().splitlines()
    first = expected[1].split("\t")
    got = ["0", *map(str, chain_row(rig))]
    if got != first:
        failures.append(f"chain after restart, before stepping:\n  got      {got}\n  expected {first}")
    print("  chain state after the restart:", "differs" if got != first else "matches", flush=True)
    world.command(f"data modify block {x} {y} {z} energy set value {RESUMED_POWER}")
    failures += replay(rig, "chain_after_reload", read_after)
    rig.unfreeze()
    world.stop()
    if failures:
        raise TestFailure("\n".join(failures))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--dedicated", action="store_true")
    parser.add_argument("--eula", action="store_true", help="you agree to the Minecraft EULA")
    args = parser.parse_args()
    if args.dedicated and not args.eula:
        parser.error("--dedicated writes eula=true: pass --eula if you agree to the Minecraft EULA")
    kind = DedicatedServer if args.dedicated else SinglePlayer

    def make(folder: Path):
        world = kind(folder, args.engine.resolve(), {})
        install_content(world.content_dir, WORK / "check/carry", WORK / "check-generators/carry")
        return world

    return run_test(make, run)


if __name__ == "__main__":
    sys.exit(main())
