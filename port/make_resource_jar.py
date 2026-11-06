#!/usr/bin/env python3
"""Zip Mekanism's assets, data and generated data into a jar horizon-port-pack can read.

The jar has no classes. Usage: make_resource_jar.py UPSTREAM OUT.jar
"""

import sys
import zipfile
from pathlib import Path

VERSION = "10.8.0"
FILLED = {
    "${file.jarVersion}": VERSION,
    "${mc_version}": "[26.3,26.4)",
    "${neo_version}": "[26.3.0.100,)",
    "${jei_version}": "*",
}
MOD_TOML = "META-INF/neoforge.mods.toml"


def files_under(root: Path, tops: tuple[str, ...]) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for top in tops
        for path in (root / top).rglob("*")
        if path.is_file() and not path.name.startswith(".")
    }


def filled_toml(text: str) -> str:
    for placeholder, value in FILLED.items():
        text = text.replace(placeholder, value)
    return text


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    upstream, out = Path(sys.argv[1]), Path(sys.argv[2])
    resources = upstream / "src/main/resources"
    generated = upstream / "src/datagen/generated/mekanism"
    # Generated files win: they are what the Gradle build merges over the hand-written ones.
    entries = {**files_under(resources, ("assets",)), **files_under(generated, ("assets", "data"))}
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as jar:
        jar.writestr(MOD_TOML, filled_toml((resources / MOD_TOML).read_text()))
        jar.write(upstream / "LICENSE", "META-INF/LICENSE")
        for name, path in sorted(entries.items()):
            jar.write(path, name)
    print(f"{out}: {len(entries)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
