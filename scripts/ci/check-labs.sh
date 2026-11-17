#!/usr/bin/env bash
# DD105-B: the checks .github/workflows/labs.yml runs on the reference
# solutions, one step at a time. DD105-A's scripts/ci/check-labs.sh, with a
# step for the course venv. Run each step in the course image, from the top
# of the course clone:
#
#   scripts/ci/in-image.sh scripts/ci/check-labs.sh venv
#   scripts/ci/in-image.sh scripts/ci/check-labs.sh selftest
#   scripts/ci/in-image.sh scripts/ci/check-labs.sh ref
#   scripts/ci/in-image.sh scripts/ci/check-labs.sh lab lab-01-one-alu-two-frameworks
#   scripts/ci/in-image.sh scripts/ci/check-labs.sh lab lab-02-a-layered-testbench-without-pyuvm
#   scripts/ci/in-image.sh scripts/ci/check-labs.sh lab lab-03-constraints-and-coverage
#   scripts/ci/in-image.sh scripts/ci/check-labs.sh lab lab-04-the-same-testbench-in-pyuvm
#   scripts/ci/in-image.sh scripts/ci/check-labs.sh lab lab-05-protocol-rules-and-backpressure
#   scripts/ci/in-image.sh scripts/ci/check-labs.sh lab lab-06-the-register-block
#
#   venv        `make venv`: the course venv (pyvsc, cocotb-coverage), made from
#               scratch in the clone unless it is already there
#   selftest    labs/common/selftest with FULL=1: the verdict classifier on its
#               recorded runs, and every grader end to end on its small ALU
#   ref         labs/ref: `make check-all` must catch all 15 planted bugs, and
#               `make seeds NSEEDS=5` must find RouterAllTest ok on the golden
#               router on seeds 1 to 5 (it needs the course venv)
#   lab <lab>   the starter's `make check` must FAIL with the verdict
#               "your test passes <bug> too", and the solution's must PASS
#
# A lab's solution is run by copying each file in solutions/ over its
# namesake in tb/; a lab whose solutions/ has its own Makefile runs from
# there. The starter's files are put back afterwards, even if the step fails.
#
# A step that passes runs `make clean` on what it built; the ccache (.ccache at
# the top of the clone) and the venv are kept. A step that fails keeps its
# build folders, so the workflow can upload the logs. Every step ends with one
# line starting "CI:", which the workflow copies into the job summary.

set -uo pipefail

RULE="========================================================================"
cd "$(dirname "$0")/../.."

say()  { printf '%s\n' "$RULE" " $*" "$RULE"; }
took() { printf '%dm%02ds' $((SECONDS / 60)) $((SECONDS % 60)); }
cache_line() {
  local hits
  hits=$(CCACHE_DIR="$PWD/.ccache" ccache -s 2>/dev/null \
           | grep -m2 -E '^ *(Hits|Misses):' | tr -s ' ' | paste -sd ';' -)
  echo "$hits; $(du -sh .ccache 2>/dev/null | cut -f1) in .ccache"
}
pass() { echo "CI: PASS  $1   ($(took))"; echo "    ccache: $(cache_line)"; exit 0; }
fail() { echo "CI: FAIL  $1   ($(took))"; exit 1; }

# make -C <dir> <target...>: the output goes to the log and to $OUT; the exit
# status to $RC.
run_make() {
  OUT=$(mktemp)
  make -C "$@" 2>&1 | tee "$OUT"
  RC=${PIPESTATUS[0]}
}
verdict() { grep -m1 -o 'VERDICT: .*' "$OUT" || echo "no VERDICT line"; }

step_venv() {
  say "the course venv: make venv"
  run_make labs/ref venv
  if [ "$RC" -ne 0 ] || ! grep -qE '^pyvsc +1\.1\.0$' "$OUT" || ! grep -qE '^cocotb-coverage +2\.0$' "$OUT"; then
    fail "make venv: expected pyvsc 1.1.0 and cocotb-coverage 2.0 (exit status $RC)"
  fi
  pass "the course venv: $(grep -m1 -oE 'created in .*|already there.*' "$OUT")"
}

step_selftest() {
  say "labs/common/selftest, FULL=1"
  run_make labs/common/selftest FULL=1
  if [ "$RC" -ne 0 ] || ! grep -q '^ SELFTEST: PASS$' "$OUT"; then
    fail "labs/common/selftest: expected SELFTEST: PASS (exit status $RC)"
  fi
  make -C labs/common/selftest clean
  pass "labs/common/selftest: SELFTEST: PASS"
}

step_ref() {
  say "labs/ref: make check-all, expecting 15 of 15 caught"
  run_make labs/ref check-all
  if [ "$RC" -ne 0 ] || ! grep -qx ' 15 of 15 caught\.' "$OUT"; then
    fail "labs/ref: expected 15 of 15 caught, got: $(grep -m1 -E 'caught\.|NO COUNT|VERDICT|course venv' "$OUT")"
  fi
  say "labs/ref: make seeds NSEEDS=5, expecting RouterAllTest ok on all five"
  run_make labs/ref seeds NSEEDS=5
  if [ "$RC" -ne 0 ] || ! grep -qx '  5 ok  (5 runs)' "$OUT"; then
    fail "labs/ref: expected 5 ok on seeds 1 to 5, got: $(grep -m1 -E 'runs\)|course venv' "$OUT")"
  fi
  make -C labs/ref clean
  pass "labs/ref: 15 of 15 caught; RouterAllTest ok on seeds 1 to 5"
}

BACKUP=""
restore_starter() {
  if [ -n "$BACKUP" ] && [ -d "$BACKUP" ]; then
    cp -p "$BACKUP"/* "$LABDIR/tb/"
    echo " starter files put back in $LABDIR/tb/"
    BACKUP=""
  fi
}

step_lab() {
  local lab=${1:?which lab? for example lab-01-one-alu-two-frameworks}
  LABDIR=labs/$lab
  [ -f "$LABDIR/Makefile" ] && [ -d "$LABDIR/solutions" ] || fail "$lab: no Makefile or no solutions/"

  say "$lab: the starter's make check, expecting FAIL"
  run_make "$LABDIR" check
  local starter
  starter=$(verdict)
  if [ "$RC" -eq 0 ] || ! grep -q 'VERDICT: FAIL -- your test passes ' "$OUT"; then
    fail "$lab: the starter should fail by missing its bug; exit status $RC, $starter"
  fi

  local soldir=$LABDIR
  if [ -f "$LABDIR/solutions/Makefile" ]; then
    soldir=$LABDIR/solutions
    say "$lab: the solution's make check, in solutions/, expecting PASS"
  else
    BACKUP=$(mktemp -d)
    trap restore_starter EXIT
    local f swapped=""
    for f in "$LABDIR"/solutions/*; do
      [ -f "$LABDIR/tb/$(basename "$f")" ] || continue
      cp -p "$LABDIR/tb/$(basename "$f")" "$BACKUP/"
      cp "$f" "$LABDIR/tb/"
      swapped="$swapped $(basename "$f")"
    done
    [ -n "$swapped" ] || fail "$lab: solutions/ has no file with a namesake in tb/"
    say "$lab: the solution's make check, with$swapped copied into tb/, expecting PASS"
  fi
  run_make "$soldir" check
  local solution
  solution=$(verdict)
  restore_starter
  if [ "$RC" -ne 0 ] || ! grep -q 'VERDICT: PASS' "$OUT"; then
    fail "$lab: the solution should pass; exit status $RC, $solution"
  fi

  [ "$soldir" = "$LABDIR" ] || make -C "$soldir" clean
  make -C "$LABDIR" clean
  pass "$lab: starter $starter; solution $solution"
}

case "${1:-}" in
  venv)     step_venv ;;
  selftest) step_selftest ;;
  ref)      step_ref ;;
  lab)      step_lab "${2:-}" ;;
  *)        sed -n '2,34p' "$0"; exit 2 ;;
esac
