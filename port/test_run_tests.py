#!/usr/bin/env python3
"""Tests run_tests.py's handling of crashes and leftovers with small stand-ins for a test.

It needs a built game only for horizon-ctl, and starts no real game: the stand-in for the game is a
sleeping process that works in the test's folder.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import horizon_driver as driver
import run_tests


def expect(label: str, got: object, wanted: object) -> None:
    if got != wanted:
        raise SystemExit(f"{label}: got {got!r}, expected {wanted!r}")
    print(f"  {label}: {got}")


STAND_IN = r"""
import os, signal, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, {port!r})
import horizon_driver as d

class Fake:
    def __init__(self, folder):
        self.folder = folder
        self.env = dict(os.environ)
        self.game = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"], cwd=folder, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def stop(self):
        raise d.TestFailure("the game does not answer")

def body(world):
    {action}

sys.exit(d.run_test(Fake, body))
"""

KILL = "world.game.kill(); world.game.wait()"
ACTIONS = {
    # The launch command fails, with no crash report and no message, and the game is still alive.
    "launch_fails": "d.launching(lambda: d.run(['/bin/sh', '-c', 'exit 3'], dict(os.environ)))",
    # A launch failing after the first check, as in a restart, is a plain failure.
    "launch_fails_late": "d.begin_checks(); d.launching(lambda: d.run(['/bin/sh', '-c', 'exit 3'], dict(os.environ)))",
    # The game dies before the first check.
    "crash_before": f"{KILL}; raise d.TestFailure('launch failed')",
    # The game dies after the first check.
    "crash_after": f"d.begin_checks(); {KILL}; raise d.TestFailure('died')",
    # A check fails, and the game is still running.
    "wrong_value": "d.begin_checks(); raise d.TestFailure('wrong value')",
    # A failure before the first check with the game alive isn't a crash.
    "setup_failure": "raise d.TestFailure('bad setup')",
    # A bug in the test that isn't a TestFailure, leaving the game running.
    "test_bug": "d.begin_checks(); None.nothing",
    "passes": "d.begin_checks()",
    "no_mark": "pass",
    # Crashes on the first run and passes on the second.
    "flaky": (
        "marker = Path(os.environ[d.RUN_FOLDER]).parent / 'ran'\n"
        "    if not marker.exists():\n"
        "        marker.write_text('')\n"
        f"        {KILL}; raise d.TestFailure('launch failed')\n"
        "    world.game.kill(); world.game.wait(); d.begin_checks()"
    ),
}


def check_prune() -> None:
    """Old builds of this mod go, the newest stays, and another mod's build is never touched."""
    import json
    import prune_server_builds as prune

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for at, name, mods in ((1, "old", ["mekmachine"]), (2, "new", ["mekmachine"]), (0, "other", ["somemod"]), (0, "both", ["mekmachine", "somemod"])):
            folder = root / name
            folder.mkdir()
            (folder / "native-mods.json").write_text(json.dumps({"mods": [{"id": mod} for mod in mods]}))
            os.utime(folder, (1000 + at, 1000 + at))
        (root / "no_manifest").mkdir()
        expect("older builds", [folder.name for folder in prune.older_builds(root)], ["old"])


def check_source_hash() -> None:
    """An engine counts only if its record and its own bytes both say the current source."""
    import source_hash

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        machine, export = root / "machine", root / "export"
        machine.mkdir()
        export.mkdir()
        (machine / "a.rs").write_text("one")
        wanted = source_hash.source_hash(machine)
        expect("no engine", source_hash.problem_with(export, machine), "there is no exported engine with a recorded source hash")
        engine = export / "horizon-engine"
        engine.write_bytes(b"xx" + source_hash.stamp_text(wanted, "n").encode() + b"xx")
        (export / source_hash.RECORD_NAME).write_text(wanted)
        expect("the same source", source_hash.problem_with(export, machine), None)
        (machine / "b.rs").write_text("two")
        expect("a new file is noticed", (source_hash.problem_with(export, machine) or "")[:10], "the engine")
        (machine / "b.rs").unlink()
        (machine / "build_stamp.rs").write_text("changes nothing")
        expect("the stamp itself doesn't count", source_hash.problem_with(export, machine), None)
        engine.write_bytes(b"something else")
        expect("a record over another engine", (source_hash.problem_with(export, machine) or "")[:16], "the engine's own")

    # The stamp: kept only for the source last built, and only if it says that source.
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        kept = (source_hash.MACHINE, source_hash.STAMP, source_hash.LAST_BUILT)
        machine = root / "machine"
        machine.mkdir()
        (machine / "a.rs").write_text("one")
        source_hash.MACHINE, source_hash.STAMP, source_hash.LAST_BUILT = machine, machine / "build_stamp.rs", root / "last"
        source_hash.source_hash.__defaults__ = (machine,)
        try:
            source_hash.write_stamp()
            first = source_hash.STAMP.read_text()
            expect("a stamp names the source", source_hash.source_hash(machine) in first, True)
            source_hash.write_stamp()
            expect("a source never built gets a new nonce", source_hash.STAMP.read_text() != first, True)
            source_hash.LAST_BUILT.write_text(source_hash.source_hash(machine))
            second = source_hash.STAMP.read_text()
            source_hash.write_stamp()
            expect("the source last built keeps its stamp", source_hash.STAMP.read_text(), second)
            source_hash.write_stamp(force=True)
            expect("a forced stamp changes", source_hash.STAMP.read_text() != second, True)
            source_hash.STAMP.write_text(source_hash.stamp_text("another", "n"))
            source_hash.write_stamp()
            expect("another source's stamp is replaced", source_hash.source_hash(machine) in source_hash.STAMP.read_text(), True)
        finally:
            source_hash.MACHINE, source_hash.STAMP, source_hash.LAST_BUILT = kept
            source_hash.source_hash.__defaults__ = (kept[0],)


def check_evidence(base: Path, always_fails: Path, flaky: Path) -> None:
    """A failed launch, by the runner's real path: retried once, with each attempt's status, message
    and log kept outside the folders the runner clears, up to the cap."""
    failures = base / "failures"
    (base / "ran").unlink()
    run_tests.keep_evidence.__defaults__ = (failures,)
    run_tests.GROUPS["stand_in"] = (str(always_fails), ("single",), [])
    run_tests.GROUPS["stand_in_flaky"] = (str(flaky), ("single",), [])
    run_folder = base / "run-evidence"
    run_folder.mkdir()
    with (base / "evidence.txt").open("w") as out:
        expect("a failed launch twice fails", run_tests.run_group("stand_in", "single", run_folder, out), (False, True))
        expect("a failed launch then a pass", run_tests.run_group("stand_in_flaky", "single", run_folder, out), (True, True))
    kept = sorted(path.name.split("-", 2)[2] for path in failures.iterdir())
    expect("each failed attempt is kept", kept, ["stand_in-single-1", "stand_in-single-2", "stand_in_flaky-single-1"])
    result = next(failures.glob("*stand_in-single-1")) / "result.txt"
    text = result.read_text()
    expect("the result is recorded", text.splitlines()[0], run_tests.LAUNCH_FAILURE)
    expect("the launch's exit status is recorded", "exit status 3" in text, True)
    expect("the test's exit status is recorded", f"exit status {driver.LAUNCH_FAILURE_EXIT}" in text, True)
    recorded = (base / "evidence.txt").read_text()
    expect("the output says where the evidence is", "evidence kept in" in recorded, True)
    expect("the attempts' folders are gone", [path for path in run_folder.iterdir() if path.is_dir()], [])
    expect("the runner's sweep doesn't match kept failures", failures in run_tests.leftovers(), False)
    del run_tests.GROUPS["stand_in"], run_tests.GROUPS["stand_in_flaky"]

    # The cap: logs before other files, the largest left out and named, the oldest failure dropped.
    folder = base / "attempt"
    (folder / "game/logs").mkdir(parents=True)
    (folder / "game/logs/latest.log").write_text("the log")
    (folder / "game/small.bin").write_bytes(b"x" * 100)
    (folder / "game/huge.bin").write_bytes(b"x" * (run_tests.KEEP_BYTES + 1))
    capped = base / "capped"
    first = run_tests.keep_evidence("old", "FAIL", "output", folder, capped)
    expect("the log is kept", (first / "game/logs/latest.log").read_text(), "the log")
    expect("a small file is kept", (first / "game/small.bin").exists(), True)
    expect("a file over the cap isn't", (first / "game/huge.bin").exists(), False)
    expect("what's left out is named", "huge.bin" in (first / "skipped.txt").read_text(), True)
    total = run_tests.KEEP_TOTAL_BYTES
    run_tests.KEEP_TOTAL_BYTES = 200
    (first / "padding").write_bytes(b"x" * 300)
    time.sleep(1.1)
    second = run_tests.keep_evidence("new", "FAIL", "output", folder, capped)
    run_tests.KEEP_TOTAL_BYTES = total
    expect("the oldest failure goes", (first.exists(), second.exists()), (False, True))


def check_refusal() -> None:
    """The runner refuses a stale engine before it runs any group or clears anything."""
    problem, sweep = run_tests.source_hash.problem_with, run_tests.sweep
    argv = sys.argv
    run_tests.source_hash.problem_with = lambda: "the engine was built from source a, but port/machine is now b"
    run_tests.sweep = lambda folders: (_ for _ in ()).throw(SystemExit("the runner went on past a stale engine"))
    sys.argv = ["run_tests.py", "gui"]
    try:
        expect("a stale engine is refused", run_tests.main(), 2)
    finally:
        run_tests.source_hash.problem_with, run_tests.sweep = problem, sweep
        sys.argv = argv


def main() -> int:
    check_prune()
    check_refusal()
    check_source_hash()
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary).resolve()
        scripts = {}
        for name, action in ACTIONS.items():
            scripts[name] = base / f"{name}.py"
            scripts[name].write_text(STAND_IN.format(port=str(driver.HERE), action=action))

        def run_stand_in(name: str) -> str:
            folder = Path(tempfile.mkdtemp(prefix="run-", dir=base))
            env = {**os.environ, driver.RUN_FOLDER: str(folder)}
            done = subprocess.run(
                [sys.executable, scripts[name]], env=env, capture_output=True, text=True,
            )
            result, _ = run_tests.classify(done.returncode, done.stdout)
            left = driver.processes_in(folder)
            expect(f"{name}: nothing left running", left, {})
            if name == "flaky":
                done = subprocess.run(
                    [sys.executable, scripts[name]], env=env, capture_output=True, text=True,
                )
                result = f"{result} then {run_tests.classify(done.returncode, done.stdout)[0]}"
            return result

        expect("a crash before the first check", run_stand_in("crash_before"), run_tests.LAUNCH_FAILURE)
        expect("a launch that fails with the game alive", run_stand_in("launch_fails"), run_tests.LAUNCH_FAILURE)
        expect("a launch that fails after the first check", run_stand_in("launch_fails_late"), run_tests.FAIL)
        expect("a crash after the first check", run_stand_in("crash_after"), run_tests.FAIL)
        expect("a wrong value", run_stand_in("wrong_value"), run_tests.FAIL)
        expect("a setup failure with the game alive", run_stand_in("setup_failure"), run_tests.FAIL)
        expect("a bug in a test", run_stand_in("test_bug"), run_tests.FAIL)
        expect("a pass", run_stand_in("passes"), run_tests.PASS)
        expect("a pass with no mark", run_stand_in("no_mark"), run_tests.FAIL)
        expect("a crash, then a pass", run_stand_in("flaky"), f"{run_tests.LAUNCH_FAILURE} then {run_tests.PASS}")

        check_evidence(base, scripts["launch_fails"], scripts["flaky"])

        # The runner's own path: a retry is recorded, and only a launch failure gets one.
        runs = []
        original = run_tests.run_once

        def fake(results: list):
            def run_once(name, mode, folder):
                runs.append(name)
                return results.pop(0), "output", 1.0
            return run_once

        with (base / "out.txt").open("w") as out:
            run_tests.run_once = fake([run_tests.LAUNCH_FAILURE, run_tests.PASS])
            expect("crash then pass", run_tests.run_group("g", "single", base, out), (True, True))
            expect("runs after a crash", len(runs), 2)
            runs.clear()
            run_tests.run_once = fake([run_tests.LAUNCH_FAILURE, run_tests.LAUNCH_FAILURE])
            expect("crash twice fails", run_tests.run_group("g", "single", base, out), (False, True))
            runs.clear()
            run_tests.run_once = fake([run_tests.FAIL, run_tests.PASS])
            expect("failure isn't retried", run_tests.run_group("g", "single", base, out), (False, False))
            expect("runs after a failure", len(runs), 1)
        run_tests.run_once = original
        recorded = (base / "out.txt").read_text()
        expect("the crash is recorded", "LAUNCH FAILURE in 1 s, running it once more" in recorded, True)
        expect("the second crash is recorded", "LAUNCH FAILURE TWICE" in recorded, True)

        # A previous run's orphan, with parent 1 after its parent exits, is found and stopped.
        old = base / "run-old"
        old.mkdir()
        env = dict(os.environ)
        subprocess.Popen(
            ["/bin/sh", "-c", f"'{sys.executable}' -c 'import time; time.sleep(600)' & exit 0"], env=env,
            cwd=old, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).wait()
        time.sleep(0.2)
        expect("the orphan is seen", len(driver.processes_in(old)), 1)
        run_tests.sweep([old])
        expect("the orphan is stopped", driver.processes_in(old), {})
        expect("its folder is removed", old.exists(), False)
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
