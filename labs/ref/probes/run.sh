#!/usr/bin/env bash
# DD105-B labs/ref: the library probes, in the course image, after `make venv`
# and `make build` in labs/ref. Each prints what it found; labs/ref/README.md
# quotes the output.
set -u
cd "$(dirname "$0")/.."
VENV_PY=$(make -s help | sed -n 's/^  PYTHON_BIN=\([^ ]*\).*/\1/p')
echo "== probes/pyvsc_probe.py ($VENV_PY)"
"$VENV_PY" probes/pyvsc_probe.py
echo "== probes/pyuvm_probe.py (python3)"
python3 probes/pyuvm_probe.py
for t in TaskJoinedTest TaskCompleteTest TaskResultTest TaskUnwatchedTest; do
  echo "== probes/probe_tasks.py $t"
  make -s run TEST_MODULES=probe_tasks PY_DIRS="tb probes" BASE_TEST=0 TEST=$t 2>&1 |
    grep -E 'PROBE:|NameError|passed|failed|^ (ok|caught|BROKEN|FAIL)' | sed 's/^ *[0-9.]*ns //'
done
