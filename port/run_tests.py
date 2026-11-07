#!/usr/bin/env python3
"""Runs test groups against a built game, and writes each group's time and result.

    python3 port/run_tests.py --list
    python3 port/run_tests.py --all
    python3 port/run_tests.py chain menu machines:dedicated
    python3 port/run_tests.py --changed [GIT_REF] [--dry-run]

A group is `name` for all its modes, or `name:single` or `name:dedicated` for one. `--changed` picks
the groups for the files that differ from GIT_REF (default HEAD), including uncommitted ones. A
changed file with no rule selects every group, so the choice errs towards running more. The full
set stays `--all`, and a merge to main should use it.

A game that dies before a group's first check is a "launch crash": the group runs once more, and the
output records it. If the group then passes on the same build it counts as passed. A failure after
the first check is never retried. The runner stops any game its groups leave running and removes
their folders, and removes what earlier runs left in `port/.work`.
"""

import argparse
import fnmatch
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from horizon_driver import CHECKS_BEGIN, LAUNCH_CRASH_EXIT, RUN_FOLDER, stop_processes_in

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORK = HERE / ".work"
ENGINE = WORK / "machine-export/horizon-engine"
RESULTS = WORK / "results.txt"
SINGLE, DEDICATED = "single", "dedicated"
PASS, FAIL, CRASH = "PASS", "FAIL", "LAUNCH CRASH"


# name: (script, modes, extra arguments)
GROUPS = {
    "furnace": ("test_phase2.py", (SINGLE, DEDICATED), []),
    "transfer": ("test_transfer.py", (SINGLE, DEDICATED), []),
    "machines": ("test_phase3.py", (SINGLE, DEDICATED), []),
    "menu": ("test_menu.py", (SINGLE,), ["--screenshot", str(WORK / "menu.png")]),
    "generator": ("test_generator.py", (SINGLE,), ["--screenshot", str(WORK / "generator.png")]),
    "gui": ("test_gui.py", (SINGLE,), [
        "--art", str(ROOT / "upstream/src/main/resources/assets/mekanism/textures/gui/sprites"),
        "--screenshot", str(WORK / "gui.png"),
    ]),
    "oxidizer_screen": ("test_oxidizer_screen.py", (SINGLE,), [
        "--art", str(ROOT / "upstream/src/main/resources/assets/mekanism/textures/gui/sprites"),
        "--textures", str(ROOT / "upstream/src/main/resources/assets/mekanism/textures"),
        "--screenshot", str(WORK / "oxidizer.png"),
    ]),
    "cable_look": ("test_cable_look.py", (SINGLE,), [
        "--art", str(ROOT / "upstream/src/main/resources/assets/mekanism/textures"),
        "--screenshot", str(WORK / "cable.png"),
    ]),
    "chain": ("test_chain.py", (SINGLE, DEDICATED), []),
    "chemical": ("test_chemical.py", (SINGLE, DEDICATED), []),
}

# The first matching rule wins. Paths are relative to the project.
RULES = [
    ("port/run_tests.py", []),
    ("port/test_run_tests.py", []),
    ("port/build_and_test.sh", []),
    ("port/README.md", []),
    ("PLAN.md", []),
    ("port/java_reference_chemical.py", ["chemical"]),
    ("port/java_*", []),
    ("port/reference/oxidizer_*", ["chemical"]),
    ("port/reference/tube_*", ["chemical"]),
    ("port/reference/generator_*", ["generator", "chain"]),
    ("port/reference/heat_generator*", ["generator", "chain"]),
    ("port/reference/chain_*", ["chain"]),
    ("port/reference/network_*", ["chain"]),
    ("port/reference/cube_*", ["chain"]),
    ("port/reference/*", ["machines"]),
    ("port/test_chemical.py", ["chemical"]),
    ("port/test_phase2.py", ["furnace"]),
    ("port/test_transfer.py", ["transfer"]),
    ("port/test_phase3.py", ["machines"]),
    ("port/test_menu.py", ["menu"]),
    ("port/test_generator.py", ["generator"]),
    ("port/test_chain.py", ["chain"]),
    ("port/machine/chem*.rs", ["chemical"]),
    ("port/machine/engine/src/chemical.rs", ["chemical"]),
    ("port/machine/tick.rs", ["furnace"]),
    ("port/machine/engine/src/furnace.rs", ["furnace"]),
    ("port/machine/transfer.rs", ["transfer"]),
    ("port/machine/fluids.rs", ["transfer"]),
    ("port/machine/engine/src/transfer.rs", ["transfer"]),
    ("port/machine/machines.rs", ["machines", "menu", "chain"]),
    ("port/machine/engine/src/recipe_machine.rs", ["machines", "menu", "chain", "chemical"]),
    ("port/machine/power.rs", ["generator", "chain"]),
    ("port/machine/engine/src/heat_generator.rs", ["generator", "chain"]),
    ("port/machine/engine/src/energy_network.rs", ["chain"]),
    ("port/machine/engine/src/split.rs", ["chain"]),
    ("port/machine/networks.rs", ["chain"]),
    ("port/test_cable_look.py", ["cable_look"]),
    ("port/gen_transmitter_model.py", ["cable_look"]),
    ("port/machine/cable_draw.rs", ["cable_look"]),
    ("port/machine/update_tag.rs", ["cable_look"]),
    ("port/machine/engine/src/transmitter_*.rs", ["cable_look"]),
    ("port/test_gui.py", ["gui", "oxidizer_screen"]),
    ("port/test_oxidizer_screen.py", ["oxidizer_screen"]),
    ("port/png_tools.py", ["gui", "oxidizer_screen"]),
    ("port/machine/gui.rs", ["gui", "menu", "oxidizer_screen"]),
    ("port/machine/engine/src/gui_layout.rs", ["gui", "menu", "oxidizer_screen"]),
    ("port/machine/screen*.rs", ["menu", "generator", "gui", "oxidizer_screen"]),
    ("port/machine/menu_button.rs", ["menu", "gui", "oxidizer_screen"]),
]


def groups_for(paths: list[str]) -> list[str]:
    chosen: set[str] = set()
    for path in paths:
        for pattern, groups in RULES:
            if fnmatch.fnmatch(path, pattern):
                chosen.update(groups)
                break
        else:
            print(f"no rule for {path}: selecting every group")
            return list(GROUPS)
    return [name for name in GROUPS if name in chosen]


def changed_paths(ref: str) -> list[str]:
    def git(*args: str) -> list[str]:
        done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
        return done.stdout.splitlines()

    return sorted(set(git("diff", "--name-only", ref) + git("ls-files", "--others", "--exclude-standard")))


def expand(selection: list[str]) -> list[tuple[str, str]]:
    runs = []
    for item in selection:
        name, _, mode = item.partition(":")
        if name not in GROUPS:
            raise SystemExit(f"unknown group {name}; --list shows them")
        modes = GROUPS[name][1]
        if mode and mode not in modes:
            raise SystemExit(f"group {name} has no mode {mode}")
        runs.extend((name, each) for each in modes if not mode or each == mode)
    return runs


def classify(returncode: int, output: str) -> tuple[str, str]:
    """A launch crash needs the test's own exit code and no sign that its checks began. A pass with
    no sign of them means a test that doesn't mark its first check, which is a failure."""
    began = CHECKS_BEGIN in output.splitlines()
    if returncode == LAUNCH_CRASH_EXIT and not began:
        return CRASH, ""
    if returncode == 0 and began:
        return PASS, ""
    if returncode == 0:
        return FAIL, "the test passed without marking its first check"
    return FAIL, ""


def run_once(name: str, mode: str, folder: Path) -> tuple[str, str, float]:
    script, _, extra = GROUPS[name]
    command = [sys.executable, str(HERE / script), "--engine", str(ENGINE), *extra]
    if mode == DEDICATED:
        command += ["--dedicated", "--eula"]
    started = time.monotonic()
    done = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=ROOT,
        env={**os.environ, RUN_FOLDER: str(folder)},
    )
    result, note = classify(done.returncode, done.stdout)
    output = done.stdout.rstrip() + (f"\n{note}" if note else "")
    return result, output, time.monotonic() - started


def run_group(name: str, mode: str, folder: Path, out) -> tuple[bool, bool]:
    """Returns whether the group passed and whether a launch crash happened."""
    result, output, seconds = run_once(name, mode, folder)
    crashed = result == CRASH
    if crashed:
        report(f"== {name}, {mode}: {CRASH} in {seconds:.0f} s, running it once more", out)
        report(output, out)
        result, output, seconds = run_once(name, mode, folder)
        if result == CRASH:
            result = f"{CRASH} TWICE"
    after = ", after a launch crash" if crashed else ""
    report(f"== {name}, {mode}: {result} in {seconds:.0f} s{after}", out)
    report(output, out)
    return result == PASS, crashed


def sweep(folders: list[Path]) -> None:
    """Stops what these test folders left running and removes them."""
    for folder in folders:
        stopped = stop_processes_in(folder)
        if stopped:
            print(f"stopped processes left in {folder.name}: {stopped}", flush=True)
        shutil.rmtree(folder, ignore_errors=True)


def leftovers() -> list[Path]:
    """Only folders the test scripts make: `mkdtemp` names (`tmp...`) and this runner's `run-...`."""
    return [p for p in [*WORK.glob("tmp*"), *WORK.glob("run-*")] if p.is_dir()]


def report(line: str, out) -> None:
    print(line, flush=True)
    out.write(line + "\n")
    out.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("groups", nargs="*")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--changed", nargs="?", const="HEAD", metavar="GIT_REF")
    parser.add_argument("--dry-run", action="store_true", help="only say which groups would run")
    args = parser.parse_args()
    if args.list:
        for name, (script, modes, _) in GROUPS.items():
            print(f"{name}: {script}, {', '.join(modes)}")
        return 0
    selection = list(args.groups)
    if args.all:
        selection = list(GROUPS)
    elif args.changed:
        selection = groups_for(changed_paths(args.changed))
        print(f"changed since {args.changed}: {', '.join(selection) or 'no game tests'}")
    elif not selection:
        parser.error("name groups, or use --all, --changed or --list")
    runs = expand(selection)
    if args.dry_run:
        print(" ".join(f"{name}:{mode}" for name, mode in runs))
        return 0
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    sweep(leftovers())
    folder = Path(tempfile.mkdtemp(prefix="run-", dir=WORK))
    failed = 0
    crashes = []
    try:
        with RESULTS.open("w") as out:
            started = time.monotonic()
            for name, mode in runs:
                passed, crashed = run_group(name, mode, folder, out)
                failed += not passed
                if crashed:
                    crashes.append(f"{name}:{mode}")
            report(f"{len(runs) - failed} of {len(runs)} passed in {time.monotonic() - started:.0f} s", out)
            report(f"launch crashes: {', '.join(crashes) or 'none'}", out)
    finally:
        sweep([folder])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
