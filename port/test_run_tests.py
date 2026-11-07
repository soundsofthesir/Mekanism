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
        "marker = Path(os.environ[d.RUN_FOLDER]) / 'ran'\n"
        "    if not marker.exists():\n"
        "        marker.write_text('')\n"
        f"        {KILL}; raise d.TestFailure('launch failed')\n"
        "    world.game.kill(); world.game.wait(); d.begin_checks()"
    ),
}


def main() -> int:
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

        expect("a crash before the first check", run_stand_in("crash_before"), run_tests.CRASH)
        expect("a crash after the first check", run_stand_in("crash_after"), run_tests.FAIL)
        expect("a wrong value", run_stand_in("wrong_value"), run_tests.FAIL)
        expect("a setup failure with the game alive", run_stand_in("setup_failure"), run_tests.FAIL)
        expect("a bug in a test", run_stand_in("test_bug"), run_tests.FAIL)
        expect("a pass", run_stand_in("passes"), run_tests.PASS)
        expect("a pass with no mark", run_stand_in("no_mark"), run_tests.FAIL)
        expect("a crash, then a pass", run_stand_in("flaky"), f"{run_tests.CRASH} then {run_tests.PASS}")

        # The runner's own path: a retry is recorded, and only a launch crash gets one.
        runs = []
        original = run_tests.run_once

        def fake(results: list):
            def run_once(name, mode, folder):
                runs.append(name)
                return results.pop(0), "output", 1.0
            return run_once

        with (base / "out.txt").open("w") as out:
            run_tests.run_once = fake([run_tests.CRASH, run_tests.PASS])
            expect("crash then pass", run_tests.run_group("g", "single", base, out), (True, True))
            expect("runs after a crash", len(runs), 2)
            runs.clear()
            run_tests.run_once = fake([run_tests.CRASH, run_tests.CRASH])
            expect("crash twice fails", run_tests.run_group("g", "single", base, out), (False, True))
            runs.clear()
            run_tests.run_once = fake([run_tests.FAIL, run_tests.PASS])
            expect("failure isn't retried", run_tests.run_group("g", "single", base, out), (False, False))
            expect("runs after a failure", len(runs), 1)
        run_tests.run_once = original
        recorded = (base / "out.txt").read_text()
        expect("the crash is recorded", "LAUNCH CRASH in 1 s, running it once more" in recorded, True)
        expect("the second crash is recorded", "LAUNCH CRASH TWICE" in recorded, True)

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
