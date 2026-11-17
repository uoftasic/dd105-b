# `labs/common`: the cocotb + pyuvm build and the graders

Every DD105-B lab builds its design with `pyuvm.mk` and is graded by the Python scripts here. A
lab's `Makefile` names its design, its bound assertions and its tests, and includes `pyuvm.mk`. For
the router, whose planted bugs `inject.py` writes into one faulty copy of the RTL:

```make
TOPLEVEL      := router
DUT_F         := build/rtl/router.f
BUILD_DEPS    := build/rtl/router.f
SVA_SRCS      := tb/router_sva.sv tb/router_sva_bind.sv
PY_DIRS       := tb
TEST_MODULES  := test_router
TESTS         := RouterSmokeTest RouterRandTest
BUG_CATALOGUE := ../common/bugs.py
include ../common/pyuvm.mk

build/rtl/router.f: $(wildcard ../common/rtl/*.sv) ../common/bugs.py ../common/inject.py
	python3 ../common/inject.py --all --out build/rtl
```

It runs in the course image (IIC-OSIC-TOOLS 2026.08: Verilator 5.050, cocotb 2.0.1, pyuvm 4.0.1,
Python 3.12) from a lab folder in your workspace clone under `/foss/designs`, or in a bare container
with the clone mounted anywhere, with `make`.

One build serves every test in a lab. The test, the seed, the plusargs and the planted bug are
chosen when you run, so changing them never rebuilds.

## The course venv

pyvsc (constrained random) and cocotb-coverage (functional coverage) aren't in the image. From
Lab 03 on, the labs use them, and so does `labs/ref`, from a venv that one target makes:

```bash
make venv          # from any lab folder, once
```

It creates the venv with `--system-site-packages`, so the image's cocotb and pyuvm stay the ones in
use, and installs `requirements.txt` into it: `pyvsc==1.1.0` and `cocotb-coverage==2.0`. The venv
lives in your workspace, `/foss/designs/.venvs/dd105-b`, when `/foss/designs` is writable, so it
survives a container restart; otherwise it goes in the top of the clone as `.venv`, which
`.gitignore` leaves out. In the course image with 2 CPUs and 3 GB, made from nothing, it took 10.3 s
and 11.6 s in two runs and came to 37 MB. pyvsc also pulls in pyboolector, dv-solve, toposort and
pyucis, and pyucis an MCP server stack (mcp, starlette, uvicorn, httpx2); none of it is used here.

The simulator's Python doesn't see an activated venv: cocotb starts the interpreter named by
`PYGPI_PYTHON_BIN`. So `pyuvm.mk` sets it to the venv's `python` for every run whenever the venv
exists, and to `/usr/bin/python3` when it doesn't. A lab that needs the venv sets `NEEDS_VENV := 1`
and stops with a message if it isn't there. uoftasic/workspace issue #3 tracks moving both packages
into the image, which would make the venv unnecessary.

## Targets

| Target | What it does |
|---|---|
| `make` | build if needed, then run `TEST` |
| `make build` | build the simulator if a source or a build setting changed |
| `make run` | run one test; prints cocotb's log and a one-line verdict |
| `make waves` | the same run, writing `waves.fst` into the run folder |
| `make tests` | list the lab's tests (`TESTS`) |
| `make regress` | every test in `TESTS` on every seed in `SEEDS`, then the merged coverage |
| `make seeds` | `TEST` on every seed in `SEEDS` |
| `make cov` | merge every `coverage.xml` under `build/runs` with cocotb-coverage and list the bins |
| `make check` | your test must pass the golden design and fail on `BUG` |
| `make check-all` | the same against every bug in `BUG_LIST` (or the catalogue) |
| `make regcheck` | build the lab's register model (`REG_MODEL`) on its own, in a second |
| `make new` / `hunt` / `verdict` / `reveal` | the mystery-bug hunt |
| `make venv` | make the course venv (above) |
| `make clean` | remove `build/` |
| `make clean-venv` / `clean-cache` | remove the venv / the ccache |
| `make help` | the targets and the current variables |

## Variables

Set these on the command line, for example `make run TEST=RouterRandTest SEED=7`.

| Variable | Default | Meaning |
|---|---|---|
| `TEST` | first of `TESTS` | the test class to run; it becomes `COCOTB_TEST_FILTER`, matched exactly |
| `SEED` | `1` | `COCOTB_RANDOM_SEED`, which seeds Python's `random` (and pyvsc with it); `SEED=random` picks one, and the run folder's name records it |
| `BUG` | empty | passed as `+BUG=<id>`; empty runs the golden design |
| `PLUSARGS` | the lab's | other plusargs, for example `+N=500`; a test reads them from `cocotb.plusargs` |
| `ERROR_LIMIT` | `100000` | `+verilator+error+limit+N`, passed to every run of a lab with `SVA_SRCS` |
| `SEEDS`, `NSEEDS` | `1` to `10` | the seeds `regress` and `seeds` use |
| `TESTS` | the lab's | the tests `regress` uses |
| `RUN_TIMEOUT` | `300` | seconds before a run is stopped (and graded BROKEN) |
| `VERBOSE` | empty | `VERBOSE=1` makes `check` and `hunt` print the simulator's log |
| `TRACE` | `1` | build with VCD tracing, so `make waves` works |
| `JOBS` | `2` | parallel g++ jobs |
| `BUILD_DIR` | `build` in the lab | where the simulator, runs and waves go |
| `VENV_DIR` | see above | where the course venv is |

A lab's `Makefile` also sets `TOPLEVEL` (the module cocotb sees as `cocotb.top`), `DUT_F` (file
lists, passed with `-F`), `DUT_SRCS`, `SVA_SRCS` (files bound into the design), `VFLAGS`,
`BUILD_DEPS`, `PY_DIRS` (the folders that hold its Python, added to `PYTHONPATH`), `TEST_MODULES`,
`TESTS`, `BUG_LIST`, `BUG_CATALOGUE`, `HUNT_POOL`, `REG_MODEL`, `NEEDS_VENV`, `BASE_TEST` and, if
its design prints one, `BUG_CONFIRM`. Paths are relative to the lab folder.

## How a run is started

`pyuvm.mk` builds with cocotb's own Verilator makefile, which adds `--vpi --public-flat-rw` (every
signal, the bound `u_sva` included, is reachable from Python) and `--timescale 1ns/1ps`. Verilator
5.050 checks assertions by default (`--no-assert` would turn them off). Then, for each run, it starts the simulator directly in
the run's own folder, with the environment cocotb's makefiles would give it: `COCOTB_TOPLEVEL`,
`COCOTB_TEST_MODULES`, `COCOTB_TEST_FILTER`, `COCOTB_RANDOM_SEED`, `COCOTB_RESULTS_FILE`,
`PYGPI_PYTHON_BIN`, `LIBPYTHON_LOC` and `COCOTB_TRUST_INERTIAL_WRITES=1`. That skips cocotb's
makefiles, which the course research measured at 1.5 to 2 s a run before the simulator starts.

Every run also gets `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. cocotb 2.0.1 sets up pytest's assertion
rewriting before it imports the tests, and pytest then loads every installed pytest plugin; one of
the image's imports siliconcompiler. The course research measured 8.6 to 9.8 s for one `make` run of
a short router test with the plugins and 4.7 to 5.7 s without, through cocotb's makefiles. Started
directly with the plugins off, `make run TEST=RouterSmokeTest` in `labs/ref` took 2.24 s of wall
time, twice, after a first run of 4.18 s, and 1.5 s of that is importing pyvsc (`python -c "import
vsc"` took 1.525 s in the venv).

`COCOTB_TEST_FILTER` is set to `(^|\.)<TEST>$`, so `TEST=RouterRandTest` runs that test and not
`RouterRandTestLong`. cocotb's own makefile pastes the filter into a shell line without quotes, so a
filter with `|` in it fails there; `pyuvm.mk` quotes it.

## Where things go

```
labs/<lab>/build/
  sim_build/Vtop      the simulator, about 2 MB with its objects
  build.log           the whole build log
  runs/<test>-s<seed>[-<bug>]/
      run.log  results.xml  cmd  exit_status  seconds  coverage.xml  waves.fst
  grade/  hunt/       the graders' runs
  coverage/           make cov and make regress: merged.xml
<clone>/.ccache       the ccache, shared by every lab, capped at 1 GB
<clone>/.venv         the course venv, when /foss/designs isn't writable
```

## Build times

Measured on `labs/ref` (the router, its bound assertions and tracing), in the course image with
2 CPUs and 3 GB:

| Build | Time |
|---|---|
| cold (empty ccache) | 8.0 to 8.2 s, in three builds |
| a source touched, warm ccache | 0.7 s |

The selftest's ALU took 7.3 s cold. The two builds together left 784 KB in the ccache.

## The base test

`py/dd105b_base.py` holds `BaseTest`, which every pyuvm test in the course derives from, and
`RouterBaseTest`, which adds the router's clock, its reset and the DUT in `ConfigDB`.

pyuvm reports through Python's `logging`, and its loggers don't propagate, so `self.logger.error()`
fails nothing: the test passes and `results.xml` says so. `BaseTest` adds one counting handler to
every component's logger (in `end_of_elaboration_phase`, and again in `start_of_simulation_phase`),
and in `final_phase` it prints one line and raises `AssertionError` if any component logged an error
or the bound assertions counted a failure:

```
DD105-B BaseTest: 0 errors logged, 0 assertion failures (u_sva.n_fail)
```

The assertion count is `cocotb.top.u_sva.n_fail`, the sum of every assertion's own counter in the
bound `router_sva`. A lab without assertions has no `u_sva`, and the line says "no bound assertions".

## Verdict classes

`verdict.py` reads `results.xml` the way DD104's does, and the log and exit status the way
DD105-A's does, and puts each run in one class:

| Class | Means |
|---|---|
| pass | at least one test ran, every test passed, BaseTest's line is in the log, and no assertion failed |
| caught | a check fired: a test ended with `AssertionError` (an `assert`, or BaseTest's verdict on logged errors and assertions) or `SimTimeoutError`, or Verilator printed a failed assertion |
| BROKEN | anything else: a failed build, a register model that doesn't build, any other exception (`NameError`, `UVMFatalError`, `UVMConfigItemNotFound`, ...), a `SimFailure` with no failed assertion, a `$fatal`, a timeout, a crash, no `results.xml`, no test or every test skipped, or a test that passed without BaseTest's line |

A BROKEN run is never a pass and never a catch. A run that Verilator stopped at its error limit
after a failed assertion (cocotb reports `SimFailure`) is caught, with a note: the limit is 1 unless
the run raises it, and `pyuvm.mk` raises it for every lab with assertions. `make check` needs pass on
the golden design and caught on the bug, so a bug run that is a pass is MISSED.

A test that passes without BaseTest's line, because it derives from `uvm_test` directly or
overrides `final_phase` without calling `super()`, is BROKEN rather than a pass, because its logged
errors failed nothing. Lab 01's cocotb test and Lab 02's plain-cocotb testbench have no BaseTest;
their labs set `BASE_TEST := 0`.

## The register model first

pyuvm 4.0.1 raises `AssertionError` for a register model that is wrong (two overlapping fields give
`AssertionError: ... Fields B overlap with field A`), and an `AssertionError` is how a check says
the design is wrong. So in a lab that sets `REG_MODEL` (`<file>:<class>`), `check`, `check-all`,
`hunt` and `verdict` build the model with `regcheck.py`, outside the simulator, before any run, and
stop with that script's message if it doesn't build. `regcheck.py` also catches a register
configured at an address that `hex()` wouldn't print that way, such as `"0x00"`: pyuvm keys its map
by `"0x0"` and looks the register up by `"0x00"`, so its first access raises `KeyError`.

## The bug switch

A lab's design carries every planted bug behind one run-time switch, so one build covers the golden
design and all the broken ones. The router's (from `inject.py --all`), unchanged from DD105-A:

- no `+BUG`, or `+BUG=none`: the golden design;
- `+BUG=Bnn`: that bug on;
- any other `+BUG`: `$fatal` at time 0;
- `+BUG_ECHO`: also print which bug is on. The graders never pass it.

It is read once, in an initial block. `+BUG` reaches the design's `$value$plusargs` on the
simulator's command line, so changing it never rebuilds. The graders pass only `+BUG=<id>`, with an
id from `BUG_LIST` or the catalogue, and nothing for the golden run. A lab whose design prints a line
for each bug can set `BUG_CONFIRM` to it, with `{id}` for the bug.

`check` and `hunt` fail a testbench whose Python or SystemVerilog reads `+BUG` (from
`cocotb.plusargs`, or with `$test$plusargs`) or a design's `*_bug_pkg`. `dd105b_trace.vlt` leaves
every package and the switch's initial block out of the waves, so `make waves` doesn't show
`router_bug_pkg.bug_id`.

## Files

| File | What it is |
|---|---|
| `pyuvm.mk` | the build and every target above; the only place a simulation is started |
| `requirements.txt` | what `make venv` installs, pinned |
| `py/dd105b_base.py` | `BaseTest` and `RouterBaseTest` |
| `dd105b_trace.vlt` | leaves packages and the bug switch out of the waves |
| `verdict.py` | pass, caught or BROKEN, from a run folder |
| `check.py` | `make check` and `make check-all` |
| `hunt.py` | `make new`, `hunt`, `verdict` and `reveal` |
| `regress.py` | `make regress` and `make seeds` |
| `regcheck.py` | `make regcheck`, and the register-model guard in the graders |
| `covmerge.py` | `make cov`: cocotb-coverage's `merge_coverage()` over the runs |
| `rtl/`, `bugs.py`, `inject.py` | the router, its bug catalogue and the faulty build, from DD105-A |
| `smoke/` | the router's shipped test and the spec's timing examples (`check_examples.py`), from DD105-A |
| `solutions/` | the router's directed reference test and `run_catalogue.py`, from DD105-A |
| `selftest/` | proves each verdict class fires; see [`selftest/README.md`](selftest/README.md) |
