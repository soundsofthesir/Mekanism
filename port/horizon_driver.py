"""Starts a game for a test and runs commands in it, as single player or a dedicated server."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

NIGHTLY = (
    Path.home() / "Library/Application Support/horizon-launcher/versions/nightly-2026-11-05-f319701"
)
RESOURCES = NIGHTLY / ".local/horizon-client/26.3"
TIMEOUT_SECONDS = 120
WORLD = "W"
PORT = "25599"
SEED = "2024"
DATAPACK_FORMAT = 121


class TestFailure(Exception):
    pass


def run(args: list, env: dict, cwd: Path | None = None) -> str:
    done = subprocess.run(
        [str(a) for a in args], env=env, cwd=cwd, capture_output=True, text=True,
        timeout=TIMEOUT_SECONDS,
    )
    if done.returncode != 0:
        raise TestFailure(f"{args[0]} {args[1:5]}: {done.stdout}{done.stderr}")
    return done.stdout


def scratch_env(folder: Path, traces: dict[str, Path]) -> dict:
    (folder / "home").mkdir()
    return {
        **os.environ,
        "HORIZON_HOME": str(folder / "home"),
        "HORIZON_LAUNCHER_HOME": str(folder / "launcher"),
        "XDG_DATA_HOME": str(folder / "data"),
        "XDG_CONFIG_HOME": str(folder / "config"),
        "HORIZON_NO_AUDIO": "1",
        "HORIZON_LAUNCHER_NO_SELF_UPDATE": "1",
        **{name: str(path) for name, path in traces.items()},
    }


class SinglePlayer:
    has_player = True

    def __init__(self, folder: Path, engine: Path, traces: dict[str, Path]) -> None:
        self.env = scratch_env(folder, traces)
        self.socket = folder / "c.sock"
        self.game_dir = folder / "game"
        self.game_dir.mkdir()
        self.world_dir = self.game_dir / "saves" / WORLD
        self.content_dir = self.game_dir
        self.engine = engine

    def ctl(self, *args: object) -> dict:
        ctl = [NIGHTLY / "horizon-ctl", "--socket", self.socket, *args]
        reply = json.loads(run(ctl, self.env, self.game_dir) or "{}")
        if "error" in reply:
            raise TestFailure(f"horizon-ctl {args}: {reply}")
        return reply

    def start(self) -> None:
        self.ctl(
            "launch", "--world", WORLD, "--seed", SEED, "--creative", "--offscreen", "--wait",
            "--game", self.engine, "--resources", RESOURCES, "--game-dir", self.game_dir,
        )

    def stop(self) -> None:
        self.ctl("quit")
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while self.socket.exists() and time.monotonic() < deadline:
            time.sleep(0.2)

    def command(self, line: str) -> list[str]:
        return self.ctl("command", line).get("chat", [])


class DedicatedServer:
    has_player = False

    def __init__(self, folder: Path, engine: Path, traces: dict[str, Path]) -> None:
        self.env = scratch_env(folder, traces)
        self.dir = folder / "server"
        self.dir.mkdir()
        self.world_dir = self.dir / WORLD
        self.content_dir = self.dir
        self.server(
            "init", "--eula", "--world", WORLD, "--seed", SEED, "--port", PORT,
            "--no-whitelist", "--offline", "--yes",
        )
        self.server("config", "set", f"engine.path={engine}", f"engine.resources={RESOURCES}")

    def server(self, *args: object) -> str:
        return run([NIGHTLY / "horizon-server", "--dir", self.dir, *args], self.env)

    def start(self) -> None:
        self.server("start")

    def stop(self) -> None:
        self.server("stop")

    def command(self, line: str) -> list[str]:
        return self.server("cmd", *line.split()).splitlines()


def install_content(game_dir: Path, mekanism: Path, generators: Path) -> None:
    """Turns on the carried mods. The generators' copy of `mekanism:` files would clash with the
    main mod's, so they are left out, and its manifest stops claiming that namespace."""
    mods = game_dir / "horizon-mods"
    mods.mkdir()
    shutil.copytree(mekanism, mods / "mekanism")
    target = mods / "mekanismgenerators"
    shutil.copytree(generators, target, ignore=shutil.ignore_patterns("mekanism"))
    manifest = target / "horizon-mod.toml"
    lines = manifest.read_text().splitlines()
    manifest.write_text("\n".join(line for line in lines if not line.startswith("namespaces")) + "\n")
    (game_dir / "horizon-mods.txt").write_text("mod.mekanism:true\nmod.mekanismgenerators:true\n")


def write_functions(world_dir: Path, functions: dict[str, list[str]]) -> None:
    """A data pack in the world with one `mekmachine:<name>` function each: they run in one tick."""
    pack = world_dir / "datapacks/mekmachine"
    folder = pack / "data/mekmachine/function"
    folder.mkdir(parents=True)
    meta = {"pack": {"description": "", "min_format": DATAPACK_FORMAT, "max_format": DATAPACK_FORMAT}}
    (pack / "pack.mcmeta").write_text(json.dumps(meta))
    for name, lines in functions.items():
        (folder / f"{name}.mcfunction").write_text("\n".join(lines) + "\n")


def run_function(world, name: str) -> None:
    answer = world.command(f"function mekmachine:{name}")
    if not any("Executed" in line or "Running" in line for line in answer):
        raise TestFailure(f"function {name} answered {answer}")
