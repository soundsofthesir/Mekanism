#!/usr/bin/env python3
"""Removes the launcher's older server builds of this project's mod.

The launcher keeps a server build of about 1 GB for each distinct mod build and never removes
one. A folder counts as this project's only when its native-mods.json names exactly the mod
`mekmachine` and no other, so builds of other mods stay. The newest of ours stays too.
"""
import json
import pathlib
import shutil
import sys

SERVER_BUILDS = pathlib.Path.home() / "Library/Application Support/horizon-launcher/native/server-builds"
MOD_ID = "mekmachine"


def is_ours(folder):
    """True when the folder's manifest names only this project's mod."""
    try:
        manifest = json.loads((folder / "native-mods.json").read_text())
        return [mod["id"] for mod in manifest["mods"]] == [MOD_ID]
    except (OSError, ValueError, KeyError, TypeError):
        return False


def older_builds(root):
    """This project's build folders in `root`, without the newest."""
    if not root.is_dir():
        return []
    ours = [folder for folder in root.iterdir() if folder.is_dir() and is_ours(folder)]
    ours.sort(key=lambda folder: folder.stat().st_mtime)
    return ours[:-1]


def main():
    root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else SERVER_BUILDS
    for folder in older_builds(root):
        print(f"Removing old server build {folder.name}")
        shutil.rmtree(folder)


if __name__ == "__main__":
    main()
