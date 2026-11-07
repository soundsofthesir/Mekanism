#!/bin/sh
# Builds port/machine into a game and runs test groups, writing port/.work/results.txt.
#
#   sh port/build_and_test.sh --trust-native-code --eula [--no-build] [run_tests.py arguments]
#
# With no test arguments it runs every group. `--changed` runs those for the files changed, and
# `python3 port/run_tests.py --list` names the groups.
#
# Both flags are your decisions: --trust-native-code that you read port/machine and trust it,
# --eula that you agree to the Minecraft EULA, which the dedicated server tests need.
set -u
cd "$(dirname "$0")/.."
if [ "${1:-}" != "--trust-native-code" ] || [ "${2:-}" != "--eula" ]; then
    echo "usage: sh port/build_and_test.sh --trust-native-code --eula [--no-build] [groups]" >&2
    exit 2
fi
shift 2
if [ "${1:-}" = "--no-build" ]; then
    shift
else
    build() {
        rm -rf port/.work/machine-export
        /Applications/Horizon.app/Contents/MacOS/horizon-launcher native-build port/machine \
            --server-output port/.work/machine-export --version nightly-2026-11-05-f319701 \
            --profile dev --trust-native-code >port/.work/build.txt 2>&1 || {
            tail -30 port/.work/build.txt | tee port/.work/results.txt
            exit 1
        }
    }
    echo "Building: progress is in port/.work/build.txt"
    python3 port/source_hash.py stamp
    build
    if ! python3 port/source_hash.py record; then
        echo "Forcing a real rebuild with a new stamp"
        python3 port/source_hash.py stamp --force
        build
        python3 port/source_hash.py record || { echo "Still not this source" | tee port/.work/results.txt; exit 1; }
    fi
    head -1 port/.work/build.txt
    python3 port/prune_server_builds.py
fi
[ $# -eq 0 ] && set -- --all
exec python3 port/run_tests.py "$@"
