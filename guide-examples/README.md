# Guide examples

This folder holds the examples that the guide pages in `docs/guide/` quote. Each folder belongs to
one page and has the page's name. Every folder has a `Makefile` that includes the labs' shared
[`labs/common/pyuvm.mk`](../labs/common/README.md), so it builds its design with Verilator 5.050
and runs its pyuvm tests on cocotb 2.0.1, needs the course image (and, where the folder sets
`NEEDS_VENV := 1`, the course venv from `make venv`), and has the same targets as a lab
(`make build`, `make run`, `make seeds`, `make waves`, `make clean` and the rest). One build serves
every test in a folder, and `TEST=` picks the test when you run.

The guide pages are for reading, and none of them asks you to run anything here. The sections below
give the commands that produced each output a page quotes, so the folders are for anyone who wants
to check what a page says, or to change an example and see what happens. Every quoted output came
from a run, in the course image with 2 CPUs and 3 GB, in a folder that had just had `make clean`.
Run each command from the example's folder, and finish with `make clean`.

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

*Writing the verification report* quotes the same runs in its worked report.

## Verification plans and sign-off

This page has no example of its own. It quotes runs of Lab 07's starter package in
`labs/lab-07-capstone`, made from a clean build: `make regress` (`100 ok  (100 runs)`, `81.67 %`,
8 min 10 s), `make check-all` (the B15 row and `14 of 15 caught.`) and a hunt dealt B15
(`make new BUGPICK=B15` then `make hunt`, which came back `quiet`). Its `120 ok  (120 runs)` and
`88.33 %   53 of 60 bins` are Lab 07's, from Part 6 of its writeup.

## Paths in the outputs

The runs were made in a container with the clone mounted at `/w`. No line a page quotes contains
that path, and lines that would have shown it (Verilator's `Verilog $stop` line, for example) are
described in the text instead.

## Cleaning up

`make clean` in each folder removes its `build/`. The examples share the course's compiler cache
in `.ccache` at the top of the clone with the labs, and `make clean-cache` removes it.
