#!/usr/bin/env bash
# Run waveshot.py in the screenshot rig, from the host. README.md has the details.
#
#   scripts/screenshots/shoot.sh surfer  build/alu.fst -s aif.clk,aif.op -o docs/assets/img/x.png
#   scripts/screenshots/shoot.sh gtkwave build/alu.fst -s aif.clk,aif.op -o docs/assets/img/y.png
#
# The current directory is mounted at /w and is the working directory inside the
# container, so give every path relative to it (absolute paths under it also work).
#
#   SHOT_IMAGE  rig image (default asic-edu/shot-rig:2026.08)
#   SHOT_LOCK   if set, hold this lock file with flock while the container runs
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
image="${SHOT_IMAGE:-asic-edu/shot-rig:2026.08}"

args=()
for a in "$@"; do
  case "$a" in
    "$PWD"/*) args+=("/w/${a#"$PWD"/}") ;;
    *) args+=("$a") ;;
  esac
done

run=(docker run --rm --cpus 2 --memory 3g --network none
     --user "$(id -u):$(id -g)"
     -v "$PWD":/w -w /w -v "$here":/opt/waveshot:ro
     "$image" --skip python3 /opt/waveshot/waveshot.py "${args[@]}")

if [ -n "${SHOT_LOCK:-}" ]; then
  exec flock "$SHOT_LOCK" "${run[@]}"
fi
exec "${run[@]}"
