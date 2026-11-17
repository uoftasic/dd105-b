# Guide examples

This folder holds the examples that the guide pages in `docs/guide/` quote. Each folder belongs to
one page and has the page's name. Every folder has a `Makefile` that includes the labs' shared
[`labs/common/pyuvm.mk`](../labs/common/README.md), so it builds with Verilator 5.050 and runs with
cocotb 2.0.1 and pyuvm 4.0.1 in the course image, and it has the same targets as a lab (`make build`,
`make run`, `make check-all`, `make cov`, `make clean` and the rest). One build serves every test in
a folder, and `TEST=` picks the test when you run.

The guide pages are for reading, and none of them asks you to run anything here. The sections below
give the commands that produced each output a page quotes, so the folders are for anyone who wants
to check what a page says, or to change an example and see what happens. Run each command from the
example's folder, in the course image, and finish with `make clean`. A folder whose Makefile sets
`NEEDS_VENV := 1` needs the course venv first (`make venv`, as in Lab 03, Part 1).

The design in every folder below is Lab 01's ALU,
`labs/lab-01-one-alu-two-frameworks/rtl/alu.sv`, with its `+BUG` switch. In the first three it is
the toplevel only because cocotb needs one, and nothing drives it.

## constrained-random-with-pyvsc

Page: [Constrained random with pyvsc](../docs/guide/constrained-random-with-pyvsc.md). Every test
randomizes small pyvsc classes and prints one line per experiment; `cr_tests.py` has them all.

| Command | What the page quotes |
|---|---|
| `make run TEST=CrItemTest` | the eleven `[ITEM]` lines and `Solve failure: set 'solve_fail_debug=1' for more details` |
| `make run TEST=CrSkewTest` | the two `[SKEW]` lines (and the figure, `scripts/figures/constrained_random_skew.py`) |
| `make run TEST=CrAttrTest` | the two `[ATTR]` lines |
| `make run TEST=CrDistTest` | the four `[DIST]` lines |
| `make run TEST=CrSoftTest` | the two `[SOFT]` lines |
| `make run TEST=CrSolveTest` | the two `[SOLVE]` lines |
| `make run TEST=CrSeedTest` and `make run TEST=CrSeedTest SEED=2` | the three `[SEED]` lines of each |
| `make run TEST=CrSpeedTest` | the `[SPEED]` line |
| `make import-time` | the three `import vsc:` lines |

## functional-coverage-you-can-read

Page: [Functional coverage you can read](../docs/guide/functional-coverage-you-can-read.md). Each
test sends random vectors to the ALU and samples each one into cocotb-coverage; each run writes
`coverage.xml` into its run folder, and `make cov` merges every run under `build/runs`.

| Command | What the page quotes |
|---|---|
| `make run TEST=CovPlainTest`, then `make cov` | the `[COV]` lines, and `make cov`'s report of 1 run |
| `make run TEST=CovBiasedTest`, then `make cov` | the `[COV] x_op_eq` lines, and `make cov`'s report of 2 runs |
| `make run TEST=CovIllegalTest`, then `make cov` | the `[COV] quirk` lines, and `make cov`'s report of 3 runs with `200.00 %` |

The figure `scripts/figures/functional_coverage_cross.py` draws the `[COV] x_op_eq` lines of the
first two runs.

## the-pyuvm-skeleton

Page: [The pyuvm skeleton](../docs/guide/the-pyuvm-skeleton.md). A component tree with no design to
test, in which every component prints a line in every phase.

| Command | What the page quotes |
|---|---|
| `make run TEST=SkPhaseTest` | the phase lines, the printed tree, `DD105-B BaseTest: 0 errors logged` (and the figure, `scripts/figures/the_pyuvm_skeleton_objections.py`) |
| `make run TEST=SkNoObjTest` | `You did not call self.raise_objection() in any run_phase`, and `extract_phase` at 0 ns |
| `make run TEST=SkErrorTest` | the `ERROR` line, `DD105-B BaseTest: 1 error logged`, and `FAIL: 1 error` |
| `make run TEST=SkPlainErrorTest BASE_TEST=0 RUN_NAME=SkPlainErrorTest-s1-nobase` | `ok: passed` |
| `make run TEST=SkPlainErrorTest` | `BROKEN: no BaseTest line` |
| `make run TEST=SkHangTest` | `FAIL: SimTimeoutError` at 1000 ns |
| `make run TEST=SkPhaseTset` | `No tests left after filtering`, and `BROKEN: every test skipped` |

The tree of Lab 04's testbench in the figure `scripts/figures/the_pyuvm_skeleton_tree.py` comes
from a probe of Lab 04's solution, which the script's docstring describes.

## sequences-sequencers-and-drivers

Page: [Sequences, sequencers and drivers](../docs/guide/sequences-sequencers-and-drivers.md).
`sq_agent.py` holds the item, the sequences, the driver and the agent, which the next two examples
import; `sq_tests.py` holds the tests.

| Command | What the page quotes |
|---|---|
| `make run TEST=SqTimelineTest` | the timeline (and the figure, `scripts/figures/sequences_handshake.py`) |
| `make run TEST=SqTwoTest` | the timeline of two sequences |
| `make run TEST=SqNestedTest` | the lines from 20 ns on |
| `make run TEST=SqReadTest` | the three `[READ]` lines |
| `make run TEST=SqDoubleGetTest` | `BROKEN: UVMSequenceError` and its message |

## monitors-analysis-ports-and-scoreboards

Page: [Monitors, analysis ports and scoreboards](../docs/guide/monitors-analysis-ports-and-scoreboards.md).
`mon_env.py` adds a monitor, a scoreboard, a coverage collector and a history to the sequences
example's agent; `mon_tests.py` holds the tests.

| Command | What the page quotes |
|---|---|
| `make run TEST=MonRandTest` | the `[MON]`, `[SB]`, `[COV]` and `[HIST]` lines |
| `make run TEST=MonRandTest BUG=A01` | the first `ERROR` line, and `caught: 30 errors` |
| `make check-all` | the three bug rows and `2 of 3 caught.` |
| `make run TEST=MonAliasTest` | the `[HIST]` lines |
| `make run TEST=MonConnectTest` | `BROKEN: UVMTLMConnectionError` and its message |

## the-factory-and-configdb

Page: [The factory and ConfigDB](../docs/guide/the-factory-and-configdb.md). The tests in
`fac_tests.py` build the monitors example's environment unchanged. The folder runs the monitors
example's tests too, so `MonRandTest` works here with `+OVERRIDE`.

| Command | What the page quotes |
|---|---|
| `make run TEST=FacEqualTest` | the factory's printout and the `[COV]` line |
| `make check-all TEST=FacEqualTest` | `0 of 3 caught.` and the three hides-behind lines |
| `make run TEST=FacCtorTest` | the two `[CTOR]` lines |
| `make check-all TEST=FacFlagsTest` | the golden row, the three bug rows and `3 of 3 caught.` |
| `make run TEST=FacTypoTest` | the `CFGDB/SET` and `CFGDB/GET` lines |
| `make check-all TEST=FacTypoTest` | `2 of 3 caught.` |
| `make run TEST=FacPrecTest`, then `make check-all TEST=FacPrecTest` | the `[TEST]` and `[ENV]` lines, `[SB] 200 vectors checked with N and Z`, and `3 of 3 caught.` |
| `make run TEST=FacGlobTest`, then `make check-all TEST=FacGlobTest` | the `[TEST]` and `[ENV]` lines, `[SB] 200 vectors checked: 0 wrong`, and `2 of 3 caught.` |
| `make run TEST=FacMissingTest` | `BROKEN: UVMConfigItemNotFound` and its message |
| `make run TEST=MonRandTest BUG=A01 PLUSARGS=+OVERRIDE=AluItem,AluEqualItem RUN_NAME=MonRandTest-s1-A01-override` | the `[OVERRIDE]` line and `MISSED: 0 errors` |
| `make run TEST=MonRandTest BUG=A01` | `caught: 30 errors` |
