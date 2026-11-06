#!/usr/bin/env python3
"""Adds NeoForge's common `c:` tags to a carried mod.

Mekanism's recipes name tags such as `c:ores/iron`, which NeoForge's jar provides, not Mekanism's.
A tag both define keeps the entries of each.

Usage: add_common_tags.py NEOFORGE_UNIVERSAL_JAR CARRY
"""

import json
import sys
import zipfile
from pathlib import Path

PREFIX = "data/c/tags/"


def entries(tag: dict) -> list:
    return list(tag.get("values", []))


def merged(ours: dict, theirs: dict) -> dict:
    extra = [entry for entry in entries(theirs) if entry not in entries(ours)]
    return {**theirs, **ours, "values": entries(ours) + extra}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    carry = Path(sys.argv[2])
    added = combined = 0
    with zipfile.ZipFile(sys.argv[1]) as jar:
        for name in jar.namelist():
            if not name.startswith(PREFIX) or not name.endswith(".json"):
                continue
            theirs = json.loads(jar.read(name))
            path = carry / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                path.write_text(json.dumps(merged(json.loads(path.read_text()), theirs), indent=2))
                combined += 1
            else:
                path.write_text(json.dumps(theirs, indent=2))
                added += 1
    print(f"{added} common tags added, {combined} combined with the mod's")
    return 0


if __name__ == "__main__":
    sys.exit(main())
