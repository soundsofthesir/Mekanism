#!/bin/sh
# Runs the machine logic's tests. A bundle's crate may not ship a Cargo.lock, so this removes the one
# cargo writes.
set -e
python3 "$(dirname "$0")/source_hash.py" stamp
cd "$(dirname "$0")/machine/engine"
trap 'rm -f Cargo.lock' EXIT
cargo test "$@"
