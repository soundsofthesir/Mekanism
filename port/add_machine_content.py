#!/usr/bin/env python3
"""Adds the menu types the machine mod opens to a carried Mekanism mod.

Usage: add_machine_content.py CARRY
"""

import json
import sys
from pathlib import Path

MACHINES = ("enrichment_chamber", "crusher", "energized_smelter")
# Input, output, energy item. The output slot only gives.
MACHINE_MENU = {"slots": 3, "data_slots": 6, "results": [1]}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    menus = Path(sys.argv[1]) / "data/mekanism/horizon/menu"
    menus.mkdir(parents=True, exist_ok=True)
    for machine in MACHINES:
        (menus / f"{machine}.json").write_text(json.dumps(MACHINE_MENU))
    print(f"{len(MACHINES)} menu types added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
