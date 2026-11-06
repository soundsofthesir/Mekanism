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
"""

import argparse
import fnmatch
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORK = HERE / ".work"
ENGINE = WORK / "machine-export/horizon-engine"
RESULTS = WORK / "results.txt"
SINGLE, DEDICATED = "single", "dedicated"


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
    ("port/test_gui.py", ["gui"]),
    ("port/png_tools.py", ["gui"]),
    ("port/machine/gui.rs", ["gui", "menu"]),
    ("port/machine/engine/src/gui_layout.rs", ["gui", "menu"]),
    ("port/machine/screen*.rs", ["menu", "generator", "gui"]),
    ("port/machine/menu_button.rs", ["menu", "gui"]),
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


def run_group(name: str, mode: str, out) -> tuple[bool, float]:
    script, _, extra = GROUPS[name]
    command = [sys.executable, str(HERE / script), "--engine", str(ENGINE), *extra]
    if mode == DEDICATED:
        command += ["--dedicated", "--eula"]
    started = time.monotonic()
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=ROOT)
    seconds = time.monotonic() - started
    passed = done.returncode == 0
    report(f"== {name}, {mode}: {'PASS' if passed else 'FAIL'} in {seconds:.0f} s", out)
    report(done.stdout.rstrip(), out)
    return passed, seconds


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
    failed = 0
    with RESULTS.open("w") as out:
        started = time.monotonic()
        for name, mode in runs:
            passed, _ = run_group(name, mode, out)
            failed += not passed
        report(f"{len(runs) - failed} of {len(runs)} passed in {time.monotonic() - started:.0f} s", out)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
