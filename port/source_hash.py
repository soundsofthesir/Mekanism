#!/usr/bin/env python3
"""Ties an exported engine to the source it was built from.

    python3 port/source_hash.py stamp          before a build: write the stamp
    python3 port/source_hash.py stamp --force  the same, with a new nonce whatever was built last
    python3 port/source_hash.py record         after a build: check the engine holds the hash, and record it

`native-build` can say "Incremental rebuild" and still export the previous binary. The launcher keeps
the patched source of earlier builds, keyed by the mod's files, and its copies keep their old modified
times. So going back to a source it has seen gives cargo files that look older than the last compile,
and cargo compiles nothing. A build of a source still in `server-builds` is "Up to date" and only
exports. PLAN.md's stale engine section has the measurements.

The stamp is a file in the engine crate that holds the source's hash and a nonce. A nonce the launcher
has never seen means a new key, freshly patched source and a recompile of the engine crate and the
game crate, which depends on it. `SOURCE` is kept in the game by `networks.rs`, so the runner can read
the hash from the engine's own bytes. A record file alone would prove nothing about the binary.
"""
import hashlib
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MACHINE = HERE / "machine"
WORK = HERE / ".work"
EXPORT = WORK / "machine-export"
ENGINE = EXPORT / "horizon-engine"
STAMP = MACHINE / "engine/src/build_stamp.rs"
RECORD_NAME = "source-hash"
LAST_BUILT = WORK / "last-built-source-hash"
PREFIX = "mekmachine-source-"
LEFT_OUT = {"build_stamp.rs", "Cargo.lock"}
LEFT_OUT_FOLDERS = {"target", "__pycache__"}


def source_hash(machine: Path = MACHINE) -> str:
    """The hash of every file of the bundle, by path and content, without the stamp."""
    digest = hashlib.sha256()
    for path in sorted(machine.rglob("*")):
        relative = path.relative_to(machine)
        if not path.is_file() or path.name in LEFT_OUT or LEFT_OUT_FOLDERS & set(relative.parts):
            continue
        digest.update(str(relative).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def stamp_text(wanted: str, nonce: str) -> str:
    return (
        "// Written by port/source_hash.py on each build. Not in git.\n"
        f"// Nonce, so that the launcher can't take this for an earlier build: {nonce}\n"
        f'pub const SOURCE: &str = "{PREFIX}{wanted}";\n'
    )


def write_stamp(force: bool = False) -> None:
    """Keeps the stamp only if this source is the last one built and the stamp says so. A failed
    compile of another source leaves its stamp here, and a stale nonce would reuse an old key."""
    wanted = source_hash()
    last = LAST_BUILT.read_text().strip() if LAST_BUILT.exists() else ""
    current = STAMP.read_text() if STAMP.exists() else ""
    if force or wanted != last or f"{PREFIX}{wanted}" not in current:
        STAMP.write_text(stamp_text(wanted, secrets.token_hex(8)))


def engine_holds(engine: Path, wanted: str) -> bool:
    return f"{PREFIX}{wanted}".encode() in engine.read_bytes()


def record() -> int:
    wanted = source_hash()
    if not engine_holds(ENGINE, wanted):
        print(f"The exported engine doesn't hold source hash {wanted}: it isn't this source.", file=sys.stderr)
        return 1
    (EXPORT / RECORD_NAME).write_text(wanted + "\n")
    LAST_BUILT.write_text(wanted + "\n")
    return 0


def problem_with(export: Path = EXPORT, machine: Path = MACHINE) -> str | None:
    """Why the exported engine can't be tested as this source, or None if it can."""
    engine = export / "horizon-engine"
    record_file = export / RECORD_NAME
    if not engine.exists() or not record_file.exists():
        return "there is no exported engine with a recorded source hash"
    built, current = record_file.read_text().strip(), source_hash(machine)
    if built != current:
        return f"the engine was built from source {built[:12]}, but port/machine is now {current[:12]}"
    if not engine_holds(engine, current):
        return f"the engine's own stamp doesn't say source {current[:12]}"
    return None


def main() -> int:
    if sys.argv[1:] in (["stamp"], ["stamp", "--force"]):
        write_stamp(force="--force" in sys.argv)
        return 0
    if sys.argv[1:] == ["record"]:
        return record()
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
