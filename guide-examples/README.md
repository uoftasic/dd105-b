# Guide examples

This folder holds the examples that DD105-B's guide and reference pages quote. Each folder belongs to
one page and has the page's name. Every folder has a `Makefile` that includes the labs' shared
[`labs/common/pyuvm.mk`](../labs/common/README.md), so it builds its design with Verilator 5.050
and runs with cocotb 2.0.1 and pyuvm 4.0.1 in the course image, and it has the same targets as a lab
(`make build`, `make run`, `make waves`, `make clean` and the rest). One build serves every test in a
folder, and `TEST=` picks the test when you run. A folder whose Makefile sets `NEEDS_VENV := 1` also
needs the course venv, which `make venv` makes, as in Lab 03, Part 1.

The pages are for reading, and none of them asks you to run anything here. The sections below give
the commands that produced each output a page quotes, in course path order with the reference page
last, so the folders are for anyone who wants to check what a page says, or to change an example and
see what happens. Every quoted output came from a run in the course image with 2 CPUs and 3 GB, in a
folder with no `build/`. Run each command from the example's folder, and finish with `make clean`.

## Getting started and What a framework buys you

These two pages have no examples of their own. They quote Lab 01's writeup and its
`solutions/README.md`, and a run of Lab 01's own targets in `labs/lab-01-one-alu-two-frameworks`,
starting from an empty compiler cache:

```bash
make clean-cache && make clean
make cocotb                         # built ... in 7.3 s; ok: passed
make build                          # built ... in 1.6 s, 6 of 7 files from the ccache
make run                            # ok: 0 errors   0.53 s
make run TEST=AluDirectedTest       # ok: 0 errors   0.27 s
make check-all                      # 2 of 3 caught, then make's error line
make loc                            # 189/94 and 316/161
du -sh build ../../.ccache          # 3.4M and 672K
make clean                          # removed ... The ccache (...) and the venv are kept.
make venv && make clean-venv        # created in 9.6 s, 37M; then removed
```

and the version checks from Lab 01, Part 1. *What a framework buys you* quotes DD105-A's numbers
(lines, build and rebuild times, run time and error counts for its SystemVerilog UVM testbench) from
DD105-A's Lab 01, as DD105-B's Lab 01 does.

## from-cocotb-tests-to-pyuvm-components

Page: [From cocotb tests to pyuvm components](../docs/guide/from-cocotb-tests-to-pyuvm-components.md).
The design is Lab 01's ALU, `labs/lab-01-one-alu-two-frameworks/rtl/alu.sv`, with its `+BUG`
switch. The tests are pyuvm tests in `components_demo.py`.

| Command | What the page quotes |
|---|---|
| `make build` | |
| `make run TEST=T01Test` | `[T01] 6 directed vectors checked`, `DD105-B BaseTest: 0 errors logged, no bound assertions` |
| `make run TEST=T01Test BUG=A01` | the `SUB(0xC8, 0x3C) gave out=0x74 ...` error, the `BaseTest` line, `caught: 1 error` |
| `make run TEST=T01UvmTest BUG=A01` | the same error, `components_demo.T01UvmTest passed`, `BROKEN: no BaseTest line` |
| `make run TEST=PhaseOrderTest` | the 39 lines from `0 ns  build_phase` to the last `final_phase` |
| `make run TEST=NoObjectionTest` | `You did not call self.raise_objection() in any run_phase`, and the lines around it |

## python-classes-and-cocotb-concurrency

Page: [Python classes and cocotb concurrency](../docs/guide/python-classes-and-cocotb-concurrency.md).
Plain cocotb tests, as in Lab 02, so the Makefile sets `BASE_TEST := 0`. cocotb needs a design to
run in, and this is Lab 01's ALU, which the tests never touch. The class examples are in
`classes_demo.py` and the task examples in `tasks_demo.py`.

| Command | What the page quotes |
|---|---|
| `make build` | |
| `make run TEST=handles_test` | `a is None` ... `a is b: True, ... Packet.n_made: 1` |
| `make run TEST=reuse_test` | the six `one Packet, reused:` and `a new Packet each:` lines |
| `make run TEST=none_test` | `appending a beat to p`, the `AttributeError` traceback, `BROKEN: AttributeError` |
| `make run TEST=dispatch_test` | the two `report() of Component` lines |
| `make run TEST=super_test` | `made a ForgetfulScoreboard; its attributes: ['expected']` and the `AttributeError` |
| `make run TEST=class_attr_test` | the `Sink:` and `OwnSink:` lines |
| `make run TEST=start_test` | the sixteen lines from `start A, B and C, and await Combine(a, b, c)` |
| `make run TEST=capture_test` | `i = 2` three times, then `j = 0`, `j = 1`, `j = 2` |
| `make run TEST=queue_test` | the `Queue(maxsize=0)` and `Queue(maxsize=1)` timelines |
| `make run TEST=event_test` | the `first`, `second` and `third` waiters |
| `make run TEST=cancel_test` | the counts at 25 and 75 ns |
| `make run TEST=end_test` | `the test returns`, `the monitor was cancelled` |
| `make run TEST=unwatched_test` | `name 'pkts' is not defined` at 20 ns, `BROKEN: NameError` |
| `make run TEST=joined_test` | `BROKEN: NameError` |
| `make run TEST=first_test` | `First returned; t.done() is True`, `ok: passed` |
| `make run TEST=first_result_test` | `BROKEN: NameError` |

## driving-and-sampling-on-the-clock

Page: [Driving and sampling on the clock](../docs/guide/driving-and-sampling-on-the-clock.md).
The design is the golden router, `labs/common/rtl/router.f`, with no planted bugs. Plain cocotb
tests, as in Lab 02, so the Makefile sets `BASE_TEST := 0`.

| Command | What the page quotes |
|---|---|
| `make build` | |
| `make run TEST=edge_test` | the watcher's lines from 20 ns to 120 ns |
| `make waves TEST=edge_test` | `build/runs/edge_test-s1/waves.fst`, for the figure below |
| `make run TEST=same_edge_test` | the five lines from 55 ns to 60 ns |
| `make run TEST=readonly_test` | `Attempting settings a value during the ReadOnly phase.`, `BROKEN: RuntimeError` |
| `make run TEST=monitor_test` | the four lines at 1260 ns |

The figure `docs/assets/img/driving-edge-test.png` is that waveform, drawn from the top of the clone
with [`scripts/screenshots/shoot.sh`](../scripts/screenshots/README.md):

```bash
scripts/screenshots/shoot.sh surfer guide-examples/driving-and-sampling-on-the-clock/build/runs/edge_test-s1/waves.fst \
  -s router.clk,router.psel,router.penable,router.in_valid,router.in_ready,router.in_data,router.in_last,router.out0_valid,router.out0_data \
  --from 60ns --to 130ns --time-unit ns -o docs/assets/img/driving-edge-test.png
```

## constrained-random-with-pyvsc

Page: [Constrained random with pyvsc](../docs/guide/constrained-random-with-pyvsc.md). Every test
randomizes small pyvsc classes and prints one line per experiment; `cr_tests.py` has them all.
The toplevel is Lab 01's ALU, `labs/lab-01-one-alu-two-frameworks/rtl/alu.sv`, only because cocotb
needs one, and no test drives it.

| Command | What the page quotes |
|---|---|
| `make run TEST=CrItemTest` | the ten `[ITEM]` lines and `Solve failure: set 'solve_fail_debug=1' for more details` |
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
test sends random vectors to Lab 01's ALU and samples each one into cocotb-coverage; each run writes
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
test, in which every component prints a line in every phase. Lab 01's ALU is the toplevel only
because cocotb needs one.

| Command | What the page quotes |
|---|---|
| `make run TEST=SkPhaseTest` | the phase lines, the printed tree, `DD105-B BaseTest: 0 errors logged` (and the figure, `scripts/figures/the_pyuvm_skeleton_objections.py`) |
| `make run TEST=SkNoObjTest` | `You did not call self.raise_objection() in any run_phase`, and `extract_phase` at 0 ns |
| `make run TEST=SkErrorTest` | the `ERROR` line, `DD105-B BaseTest: 1 error logged`, and `FAIL: 1 error` |
| `make run TEST=SkPlainErrorTest BASE_TEST=0 RUN_NAME=SkPlainErrorTest-s1-nobase` | `ok: passed` |
| `make run TEST=SkPlainErrorTest` | `BROKEN: no BaseTest line` |
| `make run TEST=SkHangTest` | `FAIL: SimTimeoutError` at 1000 ns |
| `make run TEST=SkPhaseTset` | `No tests left after filtering`, and `BROKEN: every test skipped` |
| `make run TEST=SkFinalErrorTest` | `DD105-B BaseTest: 0 errors logged` before the `ERROR` line, and `ok: 0 errors` |

The tree of Lab 04's testbench in the figure `scripts/figures/the_pyuvm_skeleton_tree.py` comes
from a probe of Lab 04's solution, which the script's docstring describes.

## sequences-sequencers-and-drivers

Page: [Sequences, sequencers and drivers](../docs/guide/sequences-sequencers-and-drivers.md).
`sq_agent.py` holds the item, the sequences, the driver and the agent, which the next two examples
import; `sq_tests.py` holds the tests. The driver drives Lab 01's ALU, with its `+BUG` switch, here
and in the next two examples.

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

## assertions-for-interface-rules

Page: [Assertions for interface rules](../docs/guide/assertions-for-interface-rules.md).
A one-beat valid/ready stage (`stage.sv`), its three rules as assertions with a counter each
(`stage_sva.sv`, bound into the stage as `u_sva`), and `StageTest` (`test_stage.py`), which drives
random beats and a random `out_ready` for 200 cycles. `BUG=drop` and `BUG=bubble` switch on the two
planted bugs. No venv needed.

| Command | What the page quotes |
|---|---|
| `make run` | the golden stage: `a beat waited in 83 cycles (cover property: 0)`, `ok` |
| `make run BUG=drop ERROR_LIMIT=1` | the first `%Error` at `[720000]`, `caught: 1 assertion` and the note; `build/runs/StageTest-s1-drop/exit_status` holds 1 |
| `make run BUG=drop` | five `a_S1` failures, `DD105-B BaseTest: 0 errors logged, 5 assertion failures (u_sva.n_fail)`, `caught: 0 errors, 5 assertions` |
| `make run BUG=drop PLUSARGS=+UNCOUNTED` | the same five failures, `no bound assertions`, cocotb's `PASS`, and the grader's `caught: 0 errors` with its note |
| `make run BUG=drop PLUSARGS=+READY_PCT=100` | `a beat waited in 0 cycles (cover property: 0)`, `MISSED` |
| `make waves BUG=drop` | the waves for the figure below |
| `make build VFLAGS=--coverage-user BUILD_DIR=/tmp/cu` then `make run VFLAGS=--coverage-user BUILD_DIR=/tmp/cu` | Verilator's user coverage on (the build log shows `VM_COVERAGE=1`): `cover property: 83`, and a `coverage.dat` in the run folder |

The figure `docs/assets/img/assertions-drop-s1.png` is a screenshot of that run's waves, taken
from the top of the repo with [`scripts/screenshots/shoot.sh`](../scripts/screenshots/README.md):

```bash
scripts/screenshots/shoot.sh surfer guide-examples/assertions-for-interface-rules/build/runs/StageTest-s1-drop/waves.fst \
  -s stage.clk,stage.out_valid,stage.out_ready,stage.out_data,stage.u_sva.n_S1 \
  --from 640ns --to 750ns --time-unit ns -o docs/assets/img/assertions-drop-s1.png
```

## reactive-agents-and-backpressure

Page: [Reactive agents and backpressure](../docs/guide/reactive-agents-and-backpressure.md).
`beat_src.sv` decides when each beat appears; the sink agent in `test_sink.py` takes the beats
either by flipping a coin every cycle or by answering each beat with an item from its sequence.
`SinkTest` prints how long 2,000 beats waited (`[WAIT]`, `[HIST]`), and in beat mode how
`get_next_item()` behaved (`[DRV]`) and how long `randomize()` took (`[SEQ]`). Needs the venv
(`+ITEM=vsc` imports pyvsc).

| Command | What the page quotes |
|---|---|
| `make run PLUSARGS="+MODE=coin +READY_PCT=5"` | the `[WAIT]` and `[HIST]` lines for a coin flip at 5% |
| `make run PLUSARGS="+MODE=coin +READY_PCT=50"` | the same at 50% |
| `make run PLUSARGS="+MODE=coin +READY_PCT=95"` | the same at 95% |
| `make run PLUSARGS="+MODE=beat +MAX_DELAY=12"` | per-beat delays from `random.randint`; the `[DRV]` line |
| `make run PLUSARGS="+MODE=beat +MAX_DELAY=12 +ITEM=vsc"`, and the same with `SEED=2` and `SEED=3` | per-beat delays from pyvsc's `randomize()`; the `[SEQ]` line; the run's time |
| `make run PLUSARGS="+MODE=beat +NOSEQ +MAX_CYCLES=3000"` | `0 beats taken in 3001 cycles` and the `[DRV]` line |

`scripts/figures/reactive_wait_histograms.py` draws the page's figure from four of the `[HIST]`
lines.

## virtual-sequences

Page: [Virtual sequences](../docs/guide/virtual-sequences.md).
A four-beat FIFO (`fifo4.sv`), a source agent, a sink driven by a knob, and `DemoVseq`
(`test_vseq.py`), which is given the environment and steers both. No venv needed.

| Command | What the page quotes |
|---|---|
| `make run` | the `[VSEQ]` lines of all three steps and `[MON] 44 beats in, 44 out, 0 out of order` |
| `make run PLUSARGS=+SERIAL` | the `[TEST]` error after 2,000 cycles and `[MON] 4 beats in, 0 out, 0 out of order` |
| `make run TEST=VseqItemTest` | `BROKEN: UVMSequenceError` and its message |

`scripts/figures/virtual_sequence_handles.py` draws the page's diagram of this testbench.

## register-models-in-pyuvm

Page: [Register models in pyuvm](../docs/guide/register-models-in-pyuvm.md).
Four registers on a one-cycle bus (`regblk.sv`), their register model on pyuvm's classes, an
adapter and a predictor (`test_regblk.py`). `+PREDICT=predictor|none|auto` picks how the mirror
follows the design. No venv needed.

| Command | What the page quotes |
|---|---|
| `make regcheck` | the four registers and their fields, `the model builds: 4 registers` |
| `make run TEST=RegMirrorTest` | the `[RAL]` lines with the predictor, `FLAGS` included |
| `make run TEST=RegMirrorTest PLUSARGS=+PREDICT=none` | the mirror missing both writes, and `MISMATCH` |
| `make run TEST=RegMirrorTest PLUSARGS=+PREDICT=auto` | `UVMError: map -- predictor Not set`, BROKEN |
| `make run TEST=RegPredictTest` | the fifteen `[RAL]` lines of `predict()` on four mirrors |
| `make run TEST=RegQuirksTest` | `NOACCESS`, `KeyError: '0x00'`, the two writes at once, the `read(CHECK)`, the back door and the missing methods |

`scripts/figures/register_model_paths.py` draws the page's diagram of this testbench.

## regressions-and-seeds

Page: [Regressions and seeds](../docs/guide/regressions-and-seeds.md).
A 4-bit saturating counter (`satcnt.sv`) and three tests (`test_seeds.py`). `CountTest` drives
random `inc` and `clr` for 300 cycles, checks every cycle against a model and collects four
cocotb-coverage bins; `BUG=wrap` makes the counter wrap at 15. `RandomTest` prints the first values
two coroutines draw, so you can see what a seed fixes, and `+EXTRA=` makes one of them do one thing
more first; `RandomTwinTest` is the same test under another name. Needs the venv.

| Command | What the page quotes |
|---|---|
| `make seeds TEST=CountTest SEEDS="1 2 3 4 5 6 7 8 9 10"` | `10 ok  (10 runs)`, the merged coverage, and each run's `[COUNT]` line |
| `make seeds TEST=CountTest SEEDS="1 2 3 4 5 6 7 8 9 10" BUG=wrap` | which seeds catch the wrap, `5 MISSED, 5 caught  (10 runs)`, and the first error on seed 4 |
| `make run TEST=RandomTest SEED=1`, twice, then `SEED=2` | the two coroutines' values |
| `make run TEST=RandomTest SEED=1 PLUSARGS=+EXTRA=draw` (and `seq`, `start`, `vsc_new`, `vsc_rand`) | what one more draw, sequence or pyvsc object changes |
| `make run TEST=RandomTwinTest SEED=1` | the same body under another name |
| `make run TEST=CountTest SEED=random` | a run folder named after the seed it picked |

*Writing the verification report* quotes the same runs in its worked report. The page's section on
corners no seed reaches quotes the run of Lab 07's starter regression listed under *Verification
plans and sign-off* below, and that run's per-test times.

## Verification plans and sign-off

This page has no example of its own. It quotes runs of Lab 07's starter package in
`labs/lab-07-capstone`, made from a clean build: `make regress` (`100 ok  (100 runs)`, `81.67 %`,
8 min 10 s), `make check-all` (the B15 row and `14 of 15 caught.`) and a hunt dealt B15
(`make new BUGPICK=B15` then `make hunt`, which came back `quiet`).

## Lab outputs the pages quote

Besides their own examples, the pages from *Assertions for interface rules* on quote a few lines
from the lab writeups, each from the run the writeup records: *Assertions for interface rules* quotes Lab 05's first error on B10 (Part 1,
step 6), *Reactive agents and backpressure* the `router.wait` lines of Lab 05's `make cov`
(Part 1, step 3), and *Verification plans and sign-off* Lab 07's `120 ok  (120 runs)` and
`88.33 %   53 of 60 bins` (Part 6, step 3).

## pyuvm-register-api

Page: [The pyuvm register API](../docs/reference/pyuvm-register-api.md), a reference page.
Six pyuvm tests in `tb/test_regapi.py`, on the golden router. The bus side is
[`labs/ref`](../labs/ref/README.md)'s APB agent, register model and adapter, which `PY_DIRS` puts
on the path; none of them needs the course venv. Every line the tests print starts with `REGAPI`,
and each test catches what an operation raises and prints it, so every run ends with `ok`.

| Command | What the page quotes |
|---|---|
| `make run TEST=RegPolicyTest` | `predict()` on a field of each of the 26 access policies; `predict()`'s `kind` and `path` arguments; what `configure()`, `add_reg()`, `map.reset()`, `add_hdl_path()` and `uvm_mem` refuse; which methods and classes exist |
| `make run TEST=RegOpsTest` | `read()` and `write()` through the map, what `reg2bus()` receives, the mirror after each, `set_desired()` with `write(None, ...)`, and `uvm_door_e` passed as a path |
| `make run TEST=RegTwoOpsTest` | two operations on one register at once, and on two registers |
| `make run TEST=RegBackdoorTest` | `path_t.BACKDOOR` and `path_t.USER_FRONTDOOR`, and the register they leave stuck |
| `make run TEST=RegAutoPredictTest` | `enable_auto_predict` set in each of the two modules that hold it |
| `make run TEST=RegAddrTest` | registers configured at `"0x00"`, and added at an offset, and the map's base address |

`grep REGAPI build/runs/<test>-s1/run.log` pulls a test's lines out of its log. In the course image
with 2 CPUs and 3 GB, `make build` took 7.8 s with an empty ccache, and each run took 0.31 s to
1.17 s.

## Times

In the course image with 2 CPUs and 3 GB, starting from an empty compiler cache, the folders
`from-cocotb-tests-to-pyuvm-components`, `python-classes-and-cocotb-concurrency` and
`driving-and-sampling-on-the-clock` built in 7.3 s (the first, which compiles Verilator's and
cocotb's support code), 1.6 s and 2.1 s, and every run listed in their sections took 0.2 to 0.9 s.

## Paths in the outputs

The runs were made in a container with the clone mounted at `/w`, so a path in a quoted line starts
with `/w`. On the workbench it starts with `/foss/designs/modules/dd105-b`. *Getting started* and
*Getting the tools outside the course image* quote such lines and say so, and *Python classes and
cocotb concurrency* quotes one, in a traceback. No other page quotes a line with the path. The pages
from *Assertions for interface rules* on describe the lines that would have shown it (Verilator's
`Verilog $stop` line, for example) in the text instead.

## Cleaning up

`make clean` in each folder removes its `build/`. The examples share the course's compiler cache
in `.ccache` at the top of the clone with the labs, and `make clean-cache` removes it.
