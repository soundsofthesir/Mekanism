#!/usr/bin/env python3
"""Writes `machine/engine/src/chemical_table.rs` from Mekanism's chemical data and language file.

    python3 port/gen_chemical_table.py upstream
"""

import json
import sys
from pathlib import Path

GENERATED = "src/datagen/generated"
HERE = Path(__file__).resolve().parent


def sprite(icon: str) -> str:
    """Where `add_machine_content.py` copies an icon, so that the GUI atlas holds it."""
    return "mekanism:block/port_" + icon.split(":")[1].replace("/", "_")


def main() -> int:
    upstream = Path(sys.argv[1])
    lang = {}
    for name in ("mekanism", "mekanismgenerators"):
        lang.update(json.loads((upstream / GENERATED / name / f"assets/{name}/lang/en_us.json").read_text()))
    rows = []
    for name in ("mekanism", "mekanismgenerators"):
        for path in sorted((upstream / GENERATED / name / f"data/{name}/mekanism/chemical").glob("*.json")):
            data = json.loads(path.read_text())
            if "icon" not in data:
                continue
            tint = int(data["tint"].lstrip("#"), 16)
            shown = lang.get(f"chemical.{name}.{path.stem}", path.stem)
            rows.append(f'    ("{name}:{path.stem}", "{shown}", 0x{tint:08X}, "{sprite(data["icon"])}"),')
    body = "\n".join(rows)
    (HERE / "machine/engine/src/chemical_table.rs").write_text(
        "//! Written by `port/gen_chemical_table.py`: each chemical's id, English name, tint and sprite.\n\n"
        f"pub const CHEMICALS: &[(&str, &str, u32, &str)] = &[\n{body}\n];\n"
    )
    print(f"{len(rows)} chemicals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
