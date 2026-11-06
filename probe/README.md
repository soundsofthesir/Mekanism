# Phase 0 probe

`mekprobe` is a native mod with one block, `mekprobe:ticker`. Its block entity adds one to a saved `ticks` value on every server tick. Nothing here is Mekanism code.

It is pinned to Nightly `f319701` (hook API 409). The test uses the launcher and prepared game files from that Nightly.

## Build

This compiles the mod into a game of its own and leaves your instances alone. `--trust-native-code` records your decision, so run it yourself after reading `mekprobe/api/src/lib.rs`.

```sh
/Applications/Horizon.app/Contents/MacOS/horizon-launcher native-build probe/mekprobe \
  --server-output probe/.run/export --version nightly-2026-11-05-f319701 \
  --profile dev --trust-native-code
```

## Test

```sh
python3 probe/run_phase0.py --engine probe/.run/export/horizon-engine singleplayer
python3 probe/run_phase0.py --engine probe/.run/export/horizon-engine dedicated --eula
```

`--eula` means you agree to the Minecraft EULA. It writes `eula=true` in a throwaway server folder.

Phase 0 passes when both modes print `PASS`.
