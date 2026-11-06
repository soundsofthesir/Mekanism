#!/bin/sh
# Builds port/machine into a game and runs the machine tests, writing port/.work/results.txt.
#
#   sh port/build_and_test.sh --trust-native-code --eula
#
# Both flags are your decisions: --trust-native-code that you read port/machine and trust it,
# --eula that you agree to the Minecraft EULA, which the dedicated server tests need.
set -u
cd "$(dirname "$0")/.."
if [ "${1:-}" != "--trust-native-code" ] || [ "${2:-}" != "--eula" ]; then
    echo "usage: sh port/build_and_test.sh --trust-native-code --eula" >&2
    exit 2
fi
ENGINE=port/.work/machine-export/horizon-engine
RESULTS=port/.work/results.txt
rm -rf port/.work/machine-export
echo "Building: progress is in port/.work/build.txt"
if ! /Applications/Horizon.app/Contents/MacOS/horizon-launcher native-build port/machine \
    --server-output port/.work/machine-export --version nightly-2026-11-05-f319701 \
    --profile dev --trust-native-code >port/.work/build.txt 2>&1; then
    tail -30 port/.work/build.txt | tee "$RESULTS"
    exit 1
fi
if [ "${3:-}" = "--only" ]; then
    { echo "== generator"; python3 port/test_generator.py --engine "$ENGINE" --screenshot port/.work/generator.png
      echo "== menu"; python3 port/test_menu.py --engine "$ENGINE" --screenshot port/.work/menu.png
      echo "== machines, dedicated"; python3 port/test_phase3.py --engine "$ENGINE" --dedicated --eula; } 2>&1 | tee "$RESULTS"
    exit
fi
{
    echo "== furnace, single player"; python3 port/test_phase2.py --engine "$ENGINE"
    echo "== furnace, dedicated"; python3 port/test_phase2.py --engine "$ENGINE" --dedicated --eula
    echo "== transfer, single player"; python3 port/test_transfer.py --engine "$ENGINE"
    echo "== transfer, dedicated"; python3 port/test_transfer.py --engine "$ENGINE" --dedicated --eula
    echo "== machines against the real mod, single player"; python3 port/test_phase3.py --engine "$ENGINE"
    echo "== machines against the real mod, dedicated"; python3 port/test_phase3.py --engine "$ENGINE" --dedicated --eula
    echo "== a player's use of a machine"; python3 port/test_menu.py --engine "$ENGINE" --screenshot port/.work/menu.png
    echo "== the generator's fuel and menu"; python3 port/test_generator.py --engine "$ENGINE" --screenshot port/.work/generator.png
    echo "== cable networks and the chain, single player"; python3 port/test_chain.py --engine "$ENGINE"
    echo "== cable networks and the chain, dedicated"; python3 port/test_chain.py --engine "$ENGINE" --dedicated --eula
} 2>&1 | tee "$RESULTS"
