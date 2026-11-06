# Port

`make_resource_jar.py`, `patch_worldgen.py` and `test_phase1.py` carry Mekanism's static content over; each file's top comment shows how to run it.

`machine/` is a native mod. `machine/engine/` holds the machine logic with no game types, and `port/test_engine.sh` runs its tests. The `.rs` files beside it compile inside the game.

## Build and test the machine mod

Read `machine/` first. Both flags are your decisions: `--trust-native-code` that you trust that code, and `--eula` that you agree to the Minecraft EULA.

```sh
sh port/build_and_test.sh --trust-native-code --eula
```

It writes the build's output to `.work/build.txt` and the test results to `.work/results.txt`.
