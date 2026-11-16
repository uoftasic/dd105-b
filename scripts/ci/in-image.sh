#!/usr/bin/env bash
# DD105-B: run a command in the course image, in the current folder (the top
# of the course clone), the way a student's container runs it. DD105-A's
# scripts/ci/in-image.sh.
#
#   IMAGE=hpretl/iic-osic-tools@sha256:... scripts/ci/in-image.sh <command> [args...]
#
# .github/workflows/labs.yml sets IMAGE to the course image, pinned by digest,
# and runs every step through this script, so the same command line rehearses
# a step on any machine with Docker and that image.
#
# The limits are the course's: 2 CPUs and 3 GB. Every build and run time in
# the lab pages is measured with them, so CI times compare with the pages.
# The image's entrypoint needs --skip to run a command instead of the desktop.
set -euo pipefail
: "${IMAGE:?set IMAGE to the course image, pinned by digest (see .github/workflows/labs.yml)}"
exec docker run --rm --cpus 2 --memory 3g --user "$(id -u):$(id -g)" \
  -v "$PWD":/w -w /w "$IMAGE" --skip "$@"
