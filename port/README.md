# Port

`make_resource_jar.py`, `patch_worldgen.py` and `test_phase1.py` carry Mekanism's static content over; each file's top comment shows how to run it.

`machine/` is a native mod. `machine/engine/` holds the machine logic with no game types, and `port/test_engine.sh` runs its tests. The `.rs` files beside it compile inside the game.

## Build the machine mod

`--trust-native-code` records your decision, so run this yourself after reading `machine/`. The export folder must not exist yet.

```sh
rm -rf port/.work/machine-export
/Applications/Horizon.app/Contents/MacOS/horizon-launcher native-build port/machine \
  --server-output port/.work/machine-export --version nightly-2026-11-05-f319701 \
  --profile dev --trust-native-code
python3 port/test_phase2.py --engine port/.work/machine-export/horizon-engine
```
