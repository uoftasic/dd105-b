#!/usr/bin/env bash
# DD105-B labs/ref: `make check-all` with each test on its own (SEED, default
# 1), to see which planted bugs each one catches. Run from labs/ref, in the
# course image, after `make venv`. About 8 minutes on 2 CPUs.
set -u
cd "$(dirname "$0")/.."
for t in $(make -s tests | sed -n 's/^  \(Router[A-Za-z]*\)$/\1/p'); do
  [ "$t" = RouterAllTest ] && continue
  out=$(make -s check-all TEST=$t SEED=${SEED:-1} 2>&1)
  missed=$(printf '%s\n' "$out" | awk '$1 != "caught" && $2 == "tier" {print $4}' | cut -d_ -f1 | paste -sd' ' -)
  golden=$(printf '%s\n' "$out" | grep -m1 'the golden design' | awk '{print $1}')
  echo "$t: golden $golden; $(printf '%s\n' "$out" | grep -m1 -oE '[0-9]+ of [0-9]+ caught\.')  not caught: ${missed:-none}"
done
