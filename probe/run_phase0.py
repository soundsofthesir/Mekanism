#!/usr/bin/env python3
"""Phase 0 test: does mekprobe:ticker keep its saved count through save and load?

Run after building the export (see probe/README.md):

    python3 probe/run_phase0.py --engine EXPORT/horizon-engine singleplayer
    python3 probe/run_phase0.py --engine EXPORT/horizon-engine dedicated --eula

Each mode passes when the block ticks once per game tick, its count is not lost when the world
stops and starts again, and it goes on ticking afterwards. All game files live in a new folder
under probe/.run/. The folder stays there on a failure, for its logs.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

NIGHTLY = (
    Path.home() / "Library/Application Support/horizon-launcher/versions/nightly-2026-11-05-f319701"
)
RUNS = Path(__file__).resolve().parent / ".run"
POS = "0 200 0"
READ_TICKS = f"data get block {POS} ticks"
READ_TIME = "time query gametime"
# A count this high can't be reached again in the moment between a restart and the first read,
# so a reset can't pass for a kept value.
MIN_COUNT_BEFORE_STOP = 200
# Each command waits for a tick, so the two reads of a sample can sit a tick or two apart.
TICK_SLACK = 2
SAMPLE_SECONDS = 5
TIMEOUT_SECONDS = 180


class TestFailure(Exception):
    pass


def run(args, env, timeout=TIMEOUT_SECONDS, check=True):
    done = subprocess.run(
        [str(a) for a in args], env=env, capture_output=True, text=True, timeout=timeout
    )
    if check and done.returncode != 0:
        raise TestFailure(f"{args[0]} {args[1:4]} failed: {done.stdout}{done.stderr}")
    return done.stdout


def scratch_env(folder):
    env = dict(os.environ)
    env.update(
        HORIZON_HOME=str(folder / "home"),
        HORIZON_LAUNCHER_HOME=str(folder / "launcher"),
        XDG_DATA_HOME=str(folder / "data"),
        XDG_CONFIG_HOME=str(folder / "config"),
        HORIZON_NO_AUDIO="1",
        HORIZON_LAUNCHER_NO_SELF_UPDATE="1",
    )
    (folder / "home").mkdir()
    return env


def last_number(lines, pattern):
    """The value in the newest line that matches, or None when no line does."""
    matches = (re.search(pattern, line) for line in reversed(lines))
    return next((int(m.group(1)) for m in matches if m), None)


class SinglePlayer:
    def __init__(self, folder, engine, resources):
        self.env = scratch_env(folder)
        self.ctl = NIGHTLY / "horizon-ctl"
        self.socket = folder / "c.sock"
        self.game_dir = folder / "game"
        self.game_dir.mkdir()
        self.engine = engine
        self.resources = resources

    def start(self):
        run(
            [
                self.ctl, "--socket", self.socket, "launch", "--world", "W", "--seed", "2024",
                "--creative", "--offscreen", "--wait", "--game", self.engine,
                "--resources", self.resources, "--game-dir", self.game_dir,
            ],
            self.env,
        )

    def command(self, line):
        out = run([self.ctl, "--socket", self.socket, "command", line], self.env)
        return json.loads(out).get("chat", [])

    def stop(self):
        run([self.ctl, "--socket", self.socket, "quit"], self.env)
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while self.socket.exists() and time.monotonic() < deadline:
            time.sleep(0.2)


class DedicatedServer:
    def __init__(self, folder, engine, resources):
        self.env = scratch_env(folder)
        self.tool = NIGHTLY / "horizon-server"
        self.dir = folder / "server"
        self.dir.mkdir()
        self.server(
            "init", "--eula", "--world", "W", "--seed", "2024", "--port", "25599",
            "--no-whitelist", "--offline", "--yes",
        )
        self.server("config", "set", f"engine.path={engine}", f"engine.resources={resources}")

    def server(self, *args):
        return run([self.tool, "--dir", self.dir, *args], self.env)

    def start(self):
        self.server("start")

    def command(self, line):
        return self.server("cmd", *line.split()).splitlines()

    def stop(self):
        self.server("stop")


def read_ticks(world):
    return last_number(world.command(READ_TICKS), r"block data: (\d+)L?\s*$")


def read_game_time(world):
    return last_number(world.command(READ_TIME), r"game time is (\d+)")


def sample(world):
    return read_ticks(world), read_game_time(world)


def wait_for_count(world, minimum):
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        ticks = read_ticks(world)
        if ticks is not None and ticks >= minimum:
            return ticks
        time.sleep(0.5)
    raise TestFailure(f"the count did not reach {minimum}: last read {ticks}")


def assert_ticks_once_per_game_tick(world):
    ticks_a, time_a = sample(world)
    time.sleep(SAMPLE_SECONDS)
    ticks_b, time_b = sample(world)
    counted, elapsed = ticks_b - ticks_a, time_b - time_a
    print(f"  counted {counted} ticks over {elapsed} game ticks")
    if elapsed <= 0 or abs(counted - elapsed) > TICK_SLACK:
        raise TestFailure(f"counted {counted} ticks over {elapsed} game ticks")


def place_block(world):
    world.command("forceload add 0 0")
    answer = world.command(f"setblock {POS} mekprobe:ticker")
    if not any("Changed the block" in line for line in answer):
        raise TestFailure(f"setblock answered {answer}")


def scenario(world):
    world.start()
    place_block(world)
    wait_for_count(world, 1)
    print("Before the stop:")
    assert_ticks_once_per_game_tick(world)
    before_stop = wait_for_count(world, MIN_COUNT_BEFORE_STOP)
    world.stop()

    world.start()
    after_start = read_ticks(world)
    print(f"Last count read before the stop: {before_stop}. First count after: {after_start}.")
    if after_start is None or after_start < before_stop:
        raise TestFailure(f"the count was lost: {before_stop} became {after_start}")
    print("After the start:")
    assert_ticks_once_per_game_tick(world)
    world.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", type=Path, required=True, help="the exported horizon-engine")
    parser.add_argument(
        "--resources", type=Path, default=NIGHTLY / ".local/horizon-client/26.3",
        help="the prepared game files",
    )
    parser.add_argument("mode", choices=["singleplayer", "dedicated"])
    parser.add_argument("--eula", action="store_true", help="you agree to the Minecraft EULA")
    args = parser.parse_args()
    if args.mode == "dedicated" and not args.eula:
        parser.error("dedicated writes eula=true: pass --eula if you agree to the Minecraft EULA")

    RUNS.mkdir(exist_ok=True)
    folder = Path(tempfile.mkdtemp(dir=RUNS))
    kind = SinglePlayer if args.mode == "singleplayer" else DedicatedServer
    world = None
    try:
        world = kind(folder, args.engine.resolve(), args.resources.resolve())
        scenario(world)
    except (TestFailure, subprocess.TimeoutExpired) as failure:
        if world is not None:
            try:
                world.stop()
            except (TestFailure, subprocess.TimeoutExpired):
                pass
        print(f"FAIL {args.mode}: {failure}\nFiles kept in {folder}", file=sys.stderr)
        return 1
    shutil.rmtree(folder)
    print(f"PASS {args.mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
