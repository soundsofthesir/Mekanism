"""Starts a game for a test and runs commands in it, as single player or a dedicated server.

`run_test` wraps a test's body. It stops every game the test started, even on failure, and exits
with `LAUNCH_FAILURE_EXIT` if the launch failed or the game died before the test called
`begin_checks`, whether or not a crash report exists. `run_tests.py` retries such a group once. A
failure after `begin_checks` is never reported as a launch failure.
"""

import http.client
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

NIGHTLY = (
    Path.home() / "Library/Application Support/horizon-launcher/versions/nightly-2026-11-05-f319701"
)
RESOURCES = NIGHTLY / ".local/horizon-client/26.3"
HERE = Path(__file__).resolve().parent
TIMEOUT_SECONDS = 120
TERM_WAIT_SECONDS = 5
WORLD = "W"
PORT = "25599"
SEED = "2024"
DATAPACK_FORMAT = 121
LAUNCH_FAILURE_EXIT = 75
CHECKS_BEGIN = "CHECKS BEGIN"
LOG_TAIL_LINES = 15
CRASH_REPORTS = Path.home() / "Library/Logs/DiagnosticReports"
# run_tests.py sets this, so that it can remove everything a run left.
RUN_FOLDER = "PORT_RUN_FOLDER"
API_ENDPOINT = ".horizon/api.json"


class TestFailure(Exception):
    pass


class LaunchFailure(TestFailure):
    """The command that starts the game failed. A plain failure once the checks have begun."""


_checks_begun = False


def begin_checks() -> None:
    """A test calls this just before its first check. A game that dies after it is a failure."""
    global _checks_begun
    if not _checks_begun:
        _checks_begun = True
        print(CHECKS_BEGIN, flush=True)


def run(args: list, env: dict, cwd: Path | None = None) -> str:
    done = subprocess.run(
        [str(a) for a in args], env=env, cwd=cwd, capture_output=True, text=True,
        timeout=TIMEOUT_SECONDS,
    )
    if done.returncode != 0:
        raise TestFailure(
            f"{args[0]} {args[1:5]}: exit status {done.returncode}, "
            f"stdout {done.stdout.strip()!r}, stderr {done.stderr.strip()!r}"
        )
    return done.stdout


def launching(start: Callable[[], object]) -> None:
    """Runs the commands that start a game, and reports any way they fail as a launch failure."""
    try:
        start()
    except (TestFailure, subprocess.TimeoutExpired, json.JSONDecodeError) as failure:
        raise LaunchFailure(str(failure)) from failure


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


def processes_in(folder: Path) -> dict[int, str]:
    """The processes started for a test, with their programs: those with the folder in their
    arguments, or with their working directory or an open file inside it. macOS hides most
    processes' environments from `ps`, so the scratch environment can't identify them."""
    if not folder.exists():
        return {}
    open_files = subprocess.run(["lsof", "-t", "+D", str(folder)], capture_output=True, text=True)
    pids = {int(pid) for pid in open_files.stdout.split()} - {os.getpid()}
    listing = subprocess.run(
        ["ps", "-axww", "-o", "pid=,command="], capture_output=True, text=True, check=True,
    ).stdout
    found = {}
    for line in listing.splitlines():
        pid, _, command = line.strip().partition(" ")
        if int(pid) != os.getpid() and (int(pid) in pids or f"{folder}/" in command or command.endswith(str(folder))):
            found[int(pid)] = command
    return found


def stop_processes_in(folder: Path) -> list[int]:
    """Stops whatever a test left running, and returns the process ids it had to stop."""
    left = list(processes_in(folder))
    for pid in left:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + TERM_WAIT_SECONDS
    while time.monotonic() < deadline and processes_in(folder):
        time.sleep(0.1)
    for pid in processes_in(folder):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return left


def game_alive(folder: Path) -> bool:
    """Whether a game process is running. horizon-ctl and a server's supervisor don't count."""
    tools = re.compile(r"(^|/)(horizon-ctl|horizon-server)( |$)")
    return any(not tools.search(command) for command in processes_in(folder).values())


class SinglePlayer:
    has_player = True
    # A frozen game takes one command a tick, so at the normal 20 a second a read costs 50 ms. A test
    # that only moves time with `tick step` can raise the target rate: a step still moves one tick.
    FAST_TICK_RATE = 10000

    def __init__(self, folder: Path, engine: Path, traces: dict[str, Path]) -> None:
        self.folder = folder
        self.env = scratch_env(folder, traces)
        self.socket = folder / "c.sock"
        self.game_dir = folder / "game"
        self.game_dir.mkdir()
        self.world_dir = self.game_dir / "saves" / WORLD
        self.content_dir = self.game_dir
        self.engine = engine
        self.link: socket.socket | None = None
        self.replies = None

    def ctl(self, *args: object) -> dict:
        ctl = [NIGHTLY / "horizon-ctl", "--socket", self.socket, *args]
        reply = json.loads(run(ctl, self.env, self.game_dir) or "{}")
        if "error" in reply:
            raise TestFailure(f"horizon-ctl {args}: {reply}")
        return reply

    def start(self) -> None:
        self.close_link()
        launching(lambda: self.ctl(
            "launch", "--world", WORLD, "--seed", SEED, "--creative", "--offscreen", "--wait",
            "--game", self.engine, "--resources", RESOURCES, "--game-dir", self.game_dir,
        ))

    def stop(self) -> None:
        self.close_link()
        self.ctl("quit")
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while self.socket.exists() and time.monotonic() < deadline:
            time.sleep(0.2)

    def close_link(self) -> None:
        if self.link is not None:
            self.replies.close()
            self.link.close()
            self.link = None

    def command(self, line: str) -> list[str]:
        """Runs one command over a kept connection, where horizon-ctl would start a process for each
        one and open the same socket. A slash and quotes need no treatment on this path."""
        if self.link is None:
            self.link = socket.socket(socket.AF_UNIX)
            self.link.settimeout(TIMEOUT_SECONDS)
            self.link.connect(str(self.socket))
            self.replies = self.link.makefile("r")
        self.link.sendall(f"command {line}\n".encode())
        answer = self.replies.readline()
        if not answer:
            raise TestFailure(f"the game closed the connection at: {line}")
        reply = json.loads(answer)
        if "error" in reply:
            raise TestFailure(f"command {line}: {reply}")
        return reply.get("chat", [])


class DedicatedServer:
    has_player = False
    # The supervisor opens a new connection to the game for each command. Faster than about 400 a
    # second, closed connections use up the local ports and a command fails with os error 49.
    FAST_TICK_RATE = 400

    def __init__(self, folder: Path, engine: Path, traces: dict[str, Path]) -> None:
        self.folder = folder
        self.env = scratch_env(folder, traces)
        self.dir = folder / "server"
        self.dir.mkdir()
        self.world_dir = self.dir / WORLD
        self.content_dir = self.dir
        self.api: http.client.HTTPConnection | None = None
        self.token = ""
        self.server(
            "init", "--eula", "--world", WORLD, "--seed", SEED, "--port", PORT,
            "--no-whitelist", "--offline", "--yes",
        )
        self.server("config", "set", f"engine.path={engine}", f"engine.resources={RESOURCES}")
        # A server with no players stops ticking after 60 seconds by default, as vanilla's does.
        (self.dir / "server.properties").write_text("pause-when-empty-seconds=-1\n")

    def server(self, *args: object) -> str:
        return run([NIGHTLY / "horizon-server", "--dir", self.dir, *args], self.env)

    def start(self) -> None:
        self.api = None
        # `cmd` waits for a game that is still starting, so the first command takes that path.
        launching(lambda: (self.server("start"), self.server("cmd", "list")))
        endpoint = json.loads((self.dir / API_ENDPOINT).read_text())
        host, port = endpoint["address"].rsplit(":", 1)
        self.api = http.client.HTTPConnection(host, int(port), timeout=TIMEOUT_SECONDS)
        self.token = endpoint["token"]

    def stop(self) -> None:
        self.api = None
        self.server("stop")

    def command(self, line: str) -> list[str]:
        """Posts one command to the API that `horizon-server cmd` uses, over a kept connection."""
        if self.api is None:
            return self.server("cmd", *line.split()).splitlines()
        self.api.request(
            "POST", "/api/v1/command", json.dumps({"line": line}),
            {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        answer = self.api.getresponse()
        body = answer.read().decode()
        if answer.status != 200:
            raise TestFailure(f"command {line}: {answer.status} {body}")
        return json.loads(body).get("output", [])


def log_tail(folder: Path) -> str:
    logs = sorted(folder.rglob("latest.log"), key=lambda p: p.stat().st_mtime)
    if not logs:
        return "no game log"
    return "\n".join(logs[-1].read_text(errors="replace").splitlines()[-LOG_TAIL_LINES:])


def crash_report_since(moment: float) -> str:
    reports = [p for p in CRASH_REPORTS.glob("horizon-*.ips") if p.stat().st_mtime >= moment]
    return str(max(reports, key=lambda p: p.stat().st_mtime)) if reports else "no macOS crash report"


def new_folder() -> Path:
    parent = Path(os.environ.get(RUN_FOLDER, HERE / ".work"))
    return Path(tempfile.mkdtemp(dir=parent))


def run_test(make_world: Callable[[Path], object], body: Callable[[object], None]) -> int:
    """Runs a test in a new folder and returns its exit code. It removes the folder on a pass and
    keeps it on a failure, for `run_tests.py` to remove."""
    folder = new_folder()
    began = time.time()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    world = None
    try:
        world = make_world(folder)
        body(world)
    except Exception as failure:
        crashed = not _checks_begun and (isinstance(failure, LaunchFailure) or not game_alive(folder))
        if not crashed and world is not None:
            try:
                world.stop()
            except Exception as stopping:
                print(f"stopping the game after the failure: {stopping}", file=sys.stderr)
        if crashed:
            print(f"LAUNCH FAILURE: {failure}\n{crash_report_since(began)}\n{log_tail(folder)}")
            return LAUNCH_FAILURE_EXIT
        kind = "" if isinstance(failure, TestFailure) else f"{type(failure).__name__}: "
        print(f"FAIL: {kind}{failure}\nFiles kept in {folder}", file=sys.stderr)
        return 1
    finally:
        left = stop_processes_in(folder)
        if left:
            print(f"stopped processes left by the test: {left}", file=sys.stderr)
    shutil.rmtree(folder)
    print("PASS")
    return 0


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
