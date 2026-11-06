#!/usr/bin/env python3
"""The Java reference for Phase 3: the real Mekanism jar on a NeoForge 26.3 server on Tower.

    python3 port/java_server.py start --eula    you agree to the Minecraft EULA
    python3 port/java_server.py smoke           places a machine and reads it for a few ticks
    python3 port/java_server.py trace OUT TICKS  an Enrichment Chamber's saved data, one line a tick
    python3 port/java_server.py stop

Machines are read with vanilla commands over RCON: `tick freeze`, `tick step 1` and `data get block`.
The server's world is thrown away by `start`. RCON listens only on Tower's loopback and is reached
through an SSH tunnel, with a new password for each start.
"""

import argparse
import re
import secrets
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

HOST = "tower"
ROOT = "/mnt/user/appdata/mekanism-horizon/server"
CONTAINER = "mek-java-server"
IMAGE = "eclipse-temurin:25-jdk"
NEOFORGE = "26.3.0.100"
RCON_PORT = 25575
LOCAL_PORT = 25576
PASSWORD_FILE = Path(__file__).resolve().parent / ".work/rcon-password"
START_TIMEOUT_SECONDS = 300
STEP_TIMEOUT_SECONDS = 180
# A save to Tower's array disks once held up a tick for 52 seconds.
RCON_TIMEOUT_SECONDS = 180
RCON_LOGIN = 3
RCON_COMMAND = 2


def ssh(script: str) -> str:
    done = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", HOST, script], capture_output=True, text=True, timeout=120
    )
    if done.returncode != 0:
        raise SystemExit(f"ssh failed: {done.stdout}{done.stderr}")
    return done.stdout


class Rcon:
    def __init__(self, port: int, password: str) -> None:
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=RCON_TIMEOUT_SECONDS)
        self.next_id = 1
        if self._send(RCON_LOGIN, password) is None:
            raise SystemExit("RCON refused the password")

    def _send(self, kind: int, text: str) -> str | None:
        request = self.next_id
        self.next_id += 1
        body = struct.pack("<ii", request, kind) + text.encode() + b"\0\0"
        self.socket.sendall(struct.pack("<i", len(body)) + body)
        size = struct.unpack("<i", self._read(4))[0]
        answer = self._read(size)
        answered, _ = struct.unpack("<ii", answer[:8])
        return None if answered == -1 else answer[8:-2].decode()

    def _read(self, count: int) -> bytes:
        data = b""
        while len(data) < count:
            part = self.socket.recv(count - len(data))
            if not part:
                raise SystemExit("RCON closed the connection")
            data += part
        return data

    def command(self, line: str) -> str:
        return self._send(RCON_COMMAND, line) or ""


def start() -> None:
    password = secrets.token_hex(16)
    PASSWORD_FILE.write_text(password)
    PASSWORD_FILE.chmod(0o600)
    properties = "\\n".join(
        [
            "enable-rcon=true",
            f"rcon.port={RCON_PORT}",
            f"rcon.password={password}",
            "online-mode=false",
            "level-seed=2024",
            "view-distance=4",
            "simulation-distance=4",
            "spawn-protection=0",
            # A server with no players stops ticking after 60 seconds by default.
            "pause-when-empty-seconds=-1",
        ]
    )
    ssh(
        f"set -e; cd {ROOT}; docker rm -f {CONTAINER} >/dev/null 2>&1 || true; rm -rf world logs; "
        f"printf 'eula=true\\n' > eula.txt; printf '{properties}\\n' > server.properties; "
        f"docker run -d --name {CONTAINER} --memory=4g --cpus=3 "
        f"-p 127.0.0.1:{RCON_PORT}:{RCON_PORT} -v {ROOT}:/s -w /s {IMAGE} "
        f"java -Xmx3G @libraries/net/neoforged/neoforge/{NEOFORGE}/unix_args.txt nogui >/dev/null"
    )
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        log = ssh(f"grep -E 'Done \\(|Failed to start|Crash report|Mod loading error' {ROOT}/logs/latest.log || true")
        if log.strip():
            print(log.strip()[-400:])
            return
        time.sleep(5)
    raise SystemExit("the server did not start in time")


def connect() -> tuple[Rcon, subprocess.Popen]:
    tunnel = subprocess.Popen(
        ["ssh", "-o", "BatchMode=yes", "-N", "-L", f"{LOCAL_PORT}:127.0.0.1:{RCON_PORT}", HOST]
    )
    time.sleep(2)
    return Rcon(LOCAL_PORT, PASSWORD_FILE.read_text()), tunnel


def smoke() -> None:
    rcon, tunnel = connect()
    try:
        for line in (
            "forceload add 0 0",
            "setblock 0 100 0 mekanism:enrichment_chamber",
            "tick freeze",
            "data get block 0 100 0",
            "tick step 1",
            "data get block 0 100 0",
            "tick unfreeze",
        ):
            print(f"> {line}\n{rcon.command(line)[:1500]}")
    finally:
        tunnel.terminate()


def game_time(rcon: Rcon) -> int:
    return int(re.search(r"\d+", rcon.command("time query gametime")).group())


def step(rcon: Rcon) -> int:
    """One tick. `tick step` only asks for it, so this waits until game time has moved."""
    before = game_time(rcon)
    rcon.command("tick step 1")
    deadline = time.monotonic() + STEP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        now = game_time(rcon)
        if now == before + 1:
            return now
        if now > before + 1:
            raise SystemExit(f"a step moved game time from {before} to {now}")
    raise SystemExit(f"a step did not move game time from {before}")


def trace(out: Path, ticks: int) -> None:
    rcon, tunnel = connect()
    at = "0 100 0"
    try:
        rcon.command("forceload add 0 0")
        rcon.command("tick unfreeze")
        rcon.command(f"setblock {at} air")
        rcon.command("setblock 0 101 0 air")
        rcon.command("tick freeze")
        placed = rcon.command(
            f"setblock {at} mekanism:enrichment_chamber{{"
            "component_config:{config0:[I;1,1,1,1,1,1],config3:[I;1,1,1,1,1,1]},"
            "energy_container:{stored:50000L},"
            'items:[{container:0b,stored:{amount:8L,type:{id:"minecraft:iron_ore"}}}]}'
        )
        print(placed.strip())
        with out.open("w") as file:
            for _ in range(ticks):
                now = step(rcon)
                file.write(f"{now}|{rcon.command(f'data get block {at}').strip()}\n")
        rcon.command("tick unfreeze")
    finally:
        tunnel.terminate()


def stop() -> None:
    ssh(f"docker rm -f {CONTAINER} >/dev/null 2>&1 || true")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["start", "smoke", "trace", "stop"])
    parser.add_argument("out", nargs="?", type=Path)
    parser.add_argument("ticks", nargs="?", type=int)
    parser.add_argument("--eula", action="store_true", help="you agree to the Minecraft EULA")
    args = parser.parse_args()
    if args.action == "start":
        if not args.eula:
            parser.error("start writes eula=true: pass --eula if you agree to the Minecraft EULA")
        start()
    elif args.action == "smoke":
        smoke()
    elif args.action == "trace":
        trace(args.out, args.ticks)
    else:
        stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
