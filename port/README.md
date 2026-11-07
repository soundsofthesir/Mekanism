# Port

## Carry the content over

```sh
python3 port/make_resource_jar.py upstream port/.work/mekanism-10.8.0-resources.jar
horizon-port-pack check port/.work/mekanism-10.8.0-resources.jar port/.work/check
python3 port/patch_worldgen.py port/.work/check/carry
python3 port/add_common_tags.py port/.work/neoforge-26.3.0.100-universal.jar port/.work/check/carry
horizon-port-pack check port/.work/MekanismGenerators-26.3-10.8.0.homebaked.jar port/.work/check-generators
python3 port/add_machine_content.py port/.work/check/carry port/.work/check-generators/carry upstream
python3 port/test_phase1.py port/.work/check/carry
```

The NeoForge jar comes from the Java server's install, described in `java_server.py`.

## Machine mod

`machine/` is a native mod. `machine/engine/` holds the machine logic with no game types, and `port/test_engine.sh` runs its tests. The `.rs` files beside it compile inside the game.

## Build and test the machine mod

Read `machine/` first. Both flags are your decisions: `--trust-native-code` that you trust that code, and `--eula` that you agree to the Minecraft EULA.

```sh
sh port/build_and_test.sh --trust-native-code --eula
```

It writes the build's output to `.work/build.txt` and the test results, with each group's time, to `.work/results.txt`. To run less:

```sh
sh port/build_and_test.sh --trust-native-code --eula --changed      # build, then the groups for the changed files
sh port/build_and_test.sh --trust-native-code --eula --no-build gui menu
python3 port/run_tests.py --list
python3 port/run_tests.py --changed main --dry-run
```

`python3 port/test_run_tests.py` tests the runner itself and needs no game.

Use `--all` before a merge. `python3 port/gen_transmitter_model.py upstream` regenerates `machine/engine/src/transmitter_model.rs` from Mekanism's OBJ models.
