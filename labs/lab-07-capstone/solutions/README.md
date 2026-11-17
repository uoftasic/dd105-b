# Lab 07: reference solution

Open this after your own `make check-all` prints `15 of 15 caught.`

| File | Part | What it is |
|---|---|---|
| `tb/router_sva.sv` | 5 | `../tb/router_sva.sv` with `a_I7`, `a_O4_rst`, `a_O4_after` (with its flip-flops `seen1` and `seen2`), `a_A4`, and `a_R_pready`, `a_R_pslverr`, `a_R_prdata`, `a_R_irq`: DD105-A's Lab 07 solution, with DD105-B's comments |
| `tb/router_vseq.py` | 5, 6 | `../tb/router_vseq.py` with `RouterResetVseq.body()`, `RouterSaturateVseq.body()`, and in `RouterLab07Vseq` the lines that run them and the resets in the random phases |
| `Makefile` | 5, 6 | builds the two files above with the rest of `../tb/`; `RouterResetTest` and `RouterSaturateTest` in `TESTS`, 12 tests in all |
| `PLAN.md` | 2, 3 | the verification plan, filled in for this environment |
| `REPORT-EXAMPLE.md` | 4, 8 | a verification report, with the numbers from the runs below |

Apart from the header comments, only the code the `TODO`s mark differs from the lab folder's
files:

```bash
diff ../tb/router_sva.sv tb/router_sva.sv
diff ../tb/router_vseq.py tb/router_vseq.py
```

Run it from this folder; it needs no copy of the rest of the testbench. `PY_DIRS` puts `tb/`
before `../tb/`, so the tests import this folder's `router_vseq.py`.

```bash
make                 # build if needed, then run RouterTest
make regress         # all 12 tests on seeds 1 to 10
make check-all       # RouterTest against all 15 bugs
make clean
```

## What changed

| Part | Where | What |
|---|---|---|
| 5 | `router_sva_out` | `seen1` and `seen2`, cleared by `rst_n`, so that `seen2` is 1 from two cycles after the first input handshake since the reset; `a_O4_rst` (`!rst_n \|-> !valid`, no `disable iff`) and `a_O4_after` (`!seen2 \|-> !valid`, with `disable iff (!rst_n)`) |
| 5 | `router_sva` | `a_I7`, `a_A4` and the four `a_R_` assertions, each `!rst_n \|-> ...` with no `disable iff` |
| 5 | `RouterResetVseq.body()` | `setup()`; E8: output 0 stalled, a 2-beat packet waiting, an 8-beat packet whose third beat waits 3 cycles, and `reset(2)` 3 cycles after it starts; the sink made fast, 20 cycles, `rd_all_regs()`; three packets whose first header waits until `setup()`; a loop of 12 `STATUS` reads and `INT_EN` writes with `reset(1)` after `cycles(8)`, which lands in the second read; output 1 slow and part way through an 8-beat packet when `reset(3)` comes; `reset(2)` in the middle of 30 random packets |
| 5 | `RouterLab07Vseq.body()` | `run()` of `RouterResetVseq`; in phases 2 to 4, half the time, a third thread beside the traffic and the backpressure that waits 30 to 300 cycles, resets for 1 to 4 cycles and calls `random_config()` |
| 6 | `RouterSaturateVseq.body()` | `reset(3)` and `ctrl(1)`; 250, 4, 1 and 5 one-beat packets for `DST` 0, whose route is disabled, with a `DROP_CNT` read after each burst; `ROUTE0` enabled, output 0 stalled, 9 packets to fill it, then 250, 5 and 5 FULL drops with a read after each; a write of `12345678` to `DROP_CNT`, a read, one more drop, a read, `drain()` and `rd_all_regs()` |
| 6 | `RouterLab07Vseq.body()` | `run()` of `RouterSaturateVseq` |

These are DD105-A's steps, written on this course's helpers.

## Measured

All in the course image (`asic-edu/gui-rig:2026.08`, which is `hpretl/iic-osic-tools:2026.08`
with X11 layers added) with 2 CPUs and 3 GB, on Nov 17, 2026, `RouterTest` unless a row says
otherwise. A count is the errors that `BaseTest` counted, then the failures the bound assertions
counted (`u_sva.n_fail`); 50 errors is a run the scoreboard stopped at its 50th error. The starter
is the lab folder as shipped; the solution is this folder.

### Every bug on seed 1

`make check-all` (`BUG_LIST` is all 15), with the golden router `ok` every time. The Lab 06 column
is from `labs/lab-06-the-register-block/solutions/README.md`.

| Bug | Lab 06's solution | This starter | This solution |
|---|---|---|---|
| B01 | caught, 3 errors | caught, 3 | caught, 3 |
| B02 | caught, 1 | caught, 1 | caught, 4 |
| B03 | caught, 4 | caught, 4 | caught, 5 |
| B04, B05, B06 | caught, 50 | caught, 50 | caught, 50 |
| B07 | caught, 4 | caught, 5 | caught, 6 |
| B08 | caught, 50 | caught, 50 | caught, 50 |
| B09 | caught, 50 and 1 assertion | caught, 50 and 1 | caught, 50 and 1 |
| B10 | caught, 50 and 368 assertions | caught, 50 and 368 | caught, 50 and 368 |
| B11 | caught, 27 and 23 assertions | caught, 50 and 43 | caught, 50 and 45 |
| B12 | caught, 50 and 3 assertions | caught, 50 and 3 | caught, 50 and 3 |
| B13 | caught, 50 | caught, 50 | caught, 50 |
| B14 | caught, 2 | caught, 2 | caught, 3 and 20 assertions |
| B15 | MISSED | MISSED | caught, 50 and 37 assertions |
| total | `14 of 15 caught.` | `14 of 15 caught.` | `15 of 15 caught.` |

The starter catches the same fourteen bugs as Lab 06's solution. The counts that move (B07 and
B11) are errors that `RouterLab07Vseq`'s random phases add at the end of the run; "The order of
random draws" below shows that everything before them is Lab 06's.

### The lab's bugs on seeds 1 to 5

This lab's bugs are all fifteen. `make check-all SEED=<n>`, with the golden router `ok` every time:

| Seed | Starter | Solution | Solution: B15 | Solution: B14 | Solution: B02 |
|---|---|---|---|---|---|
| 1 | `14 of 15 caught.`, B15 `MISSED` | `15 of 15 caught.` | 50 and 37 assertions | 3 and 20 assertions | 4 |
| 2 | `14 of 15 caught.`, B15 `MISSED` | `15 of 15 caught.` | 27 and 31 | 3 and 17 | 2 |
| 3 | `14 of 15 caught.`, B15 `MISSED` | `15 of 15 caught.` | 50 and 31 | 3 and 16 | 4 |
| 4 | `14 of 15 caught.`, B15 `MISSED` | `15 of 15 caught.` | 41 and 25 | 3 and 13 | 4 |
| 5 | `14 of 15 caught.`, B15 `MISSED` | `15 of 15 caught.` | 50 and 30 | 3 and 14 | 4 |

So B15 meets the course's rule: missed by the starter and caught by the solution on seeds 1 to 5.
The other fourteen are caught by both on every seed. On seeds 2 to 5 the starter's error counts
differ from seed 1's only for B02 (2 on seed 2), B03 (5 on seed 3), B07 (7, 6, 7 and 7) and B11
(48, 50, 43 and 50); the assertion counts of B09 to B13 vary from seed to seed, as they do in the
solution.

The first checks in the solution, the same on every seed apart from the cycle:

| Bug | First check | From |
|---|---|---|
| B15 | `u_out0.a_O4_rst`: `O4: out_valid is 1 during reset`, at 139460000 ps on seed 1 (cycle 13946, the first cycle of the E8 reset in `RouterResetVseq`) | this lab's assertion; the scoreboard follows with `output 0: got 00 in cycle 13949, and no beat was expected`, and on seeds 2 to 5 three or four cycles after the assertion |
| B14 | `a_I7`: `I7: in_ready is 1 during reset`, at 10000 ps (cycle 1), on every seed | this lab's assertion, during the reset at time 0; the starter's first check is the predictor's, `[RAL] CTRL read 0x1 in cycle 10; the mirror holds 0x0` |
| B02 | `irq is 1 from cycle 5906, but STATUS = 001 and INT_EN = 000 make it 0` | the `irq` check, in `RouterLab06Vseq`, as in Lab 06; the solution's later errors come after resets, which clear `STATUS` |

Every other bug's first check comes before `RouterLab07Vseq` starts (at 139200 ns on seed 1), in
the part of the run that is Lab 06's, so it is the check that fires first in Lab 06's solution, in
the same cycle; for B01, B03 and B04 those are the cycles Lab 06's README records (5955, 3663 and
4143).

### The golden router on several seeds

| Run | Result |
|---|---|
| the starter's `make seeds SEEDS="1 2 3 4 5"` | `5 ok  (5 runs)`, 11.2 to 11.4 s a run, 56.8 s in all |
| the solution's `make seeds SEEDS="1 2 3 4 5"`, then `SEEDS="6 7 8 9 10"` | `5 ok  (5 runs)` each, 11.9 to 12.2 s a run |
| the solution's `make seeds TEST=<t> SEEDS="1 2 3 4 5"` for `RouterResetTest`, `RouterSaturateTest` and `RouterLab07Test` | `5 ok  (5 runs)` each |
| the starter's `make regress` (10 tests on seeds 1 to 10; Part 3 of the page) | `100 ok  (100 runs)` in 8 min 27 s, `81.67 %   49 of 60 bins` |
| the lab folder's `make regress` with these files and this `TESTS` (Part 6 of the page) | `120 ok  (120 runs)` in 9 min 21 s, `88.33 %   53 of 60 bins` |
| this folder's `make regress` | `120 ok  (120 runs)` in 9 min 30 s, `88.33 %   53 of 60 bins` |

The starter leaves the four `router.corner` bins empty, and both leave the seven bins of
`router.pkt.x_fate_level` that the specification rules out (`full` at `empty`, `low` and `at_8`,
and `out0` and `out1` at `at_9` and `high`), as in Labs 04 to 06. DD105-A's regressions reached
the same totals: 49 of 60 (`81.7%`) and 53 of 60 (`88.3%`).

The solution's `RouterTest` on seed 1 prints these lines at its end:

```text
[SB] 2321 packets in: 541 to output 0, 460 to output 1, 509 NOROUTE, 808 FULL; the highest level a header saw was 16
[SB] beats checked: 2452 on output 0, 2007 on output 1; 57 DROP_CNT reads checked
[SB] registers: 935 reads, 80 of STATUS checked; 492 transfers to bad addresses; irq checked in 19823 cycles, wrong in 0
[SB] resets: 7 after the one at time 0, 53 expected beats lost; corners hit: reset_with_beats=5 reset_mid_packet=3 noroute_saturated=5 full_saturated=5
[RAL] 689 register reads checked against the mirror, 714 writes predicted; 0 mismatches
```

### `make check` and the hunts

With no `BUG`, `make check` grades B15. The starter says
`VERDICT: FAIL -- your test passes B15_output_valid_survives_reset too.`, and the solution says
`VERDICT: PASS`.

| Where | Deal | `make hunt` | `make verdict` |
|---|---|---|---|
| starter | `make new BUGPICK=B02` | `caught`, 1 error, 11.8 s | `VERDICT: PASS`, B02, 23.2 s |
| starter | `make new BUGPICK=B15` | `quiet`, `0 errors, 0 assertions`, 11.9 s | not run; `make reveal` names B15 |
| solution | `make new BUGPICK=B15` | `caught`, 50 errors, 37 assertions, 11.8 s | `VERDICT: PASS`, B15, 24.1 s |

## The order of random draws

Every random value in this testbench comes from Python's `random`, one after another, so a piece
that draws one value more moves every value after it (chain spec, decision 8). `RouterTest` runs
`RouterLab07Vseq` after everything Lab 06's `RouterTest` ran, so what it draws can move nothing
before it. These runs check that nothing else this lab adds moves anything either; the second is a
probe build, not shipped:

- Lab 06's solution, `RouterTest` on seeds 1 to 5: its `[PHASE]`, `[DROP]`, `[HOLES]`, `[SB]`,
  `[RAL]`, `[RegResetSeq]` and `[RegBitBashSeq]` lines.
- This lab's starter with the two lines that start `RouterLab07Vseq` taken out of `RouterTest`, on
  seeds 1 to 5: the same lines, line for line, with one more, the new
  `[SB] resets: 0 after the one at time 0, 0 expected beats lost; corners hit: ...`. On seed 1 they
  include `1135 packets in: 311 to output 0, 288 to output 1, 177 NOROUTE, 359 FULL` and
  `irq checked in 13918 cycles`.
- The same probe build's `make check-all` over all 15 bugs on seed 1: Lab 06's solution row,
  count for count (`14 of 15 caught.`, with B01 3, B02 1, B03 4, B07 4, B10 50 and 368, B11 27
  and 23, B14 2).

So the reset driver, the drivers' reset handling, the scoreboard's reset path, the corner
coverage and the new assertions change nothing in a run with no reset after time 0.

## Probes

Probe builds, not shipped, behind claims on the page:

| Probe | Result |
|---|---|
| Part 5 done and Part 6 not (`RouterSaturateVseq` empty and not run), `make check-all` on seed 1 | `15 of 15 caught.`, B15 at `50 errors, 14 assertions`: Part 6 closes two coverage bins and catches no further bug (Part 6, step 3) |
| the solution's `RouterResetTest` with the call to `reset_model()` taken out of `write_sys()`, golden | `FAIL: 56 errors, 0 assertions`: first the predictor (`[RAL] CTRL read 0x0 in cycle 57; the mirror holds 0x1`, and `INT_EN` and the four `ROUTE` registers after it), then the scoreboard (`output 0: got 02 in cycle 120, expected 00`) (Part 5, step 1) |
| the solution's `RouterResetTest` with Lab 06's `SrcDriver` and `ApbDriver` in place of this lab's, golden | `FAIL: 1 error, 3 assertions`: `in_ready stayed 0 for 1000 cycles with beat 2 of dst 0, 8 beats: 01 15 74 d5 6f da 03 ae on offer; dropping the rest of it`, then `a_I1` when it gave up, and `a_A4` (`A4: psel is 1 during reset`) and `a_R_pready` in a later reset (Part 5, step 1) |

## Times

| What | Time |
|---|---|
| `make build` in the lab folder, after the builds of Labs 01 to 06 | 2.4 s, 6 of 7 files from the ccache |
| `make build` with an empty ccache | 9.1 s (lab folder), 9.3 s (this folder) |
| `make build` after the Part 5 assertions | 2.5 s |
| `RouterTest` | 11.2 to 13.1 s (starter), 11.2 to 12.5 s at the page's stages, 11.9 to 13.7 s (solution) |
| `RouterResetTest`, `RouterSaturateTest` | 2.2 to 2.3 s, 2.5 s; 2.0 s each in the starter, which fails them |
| `make check-all` | 114.6 to 118.1 s (starter), 114.1 to 117.7 s at the page's stages, 117.8 to 123.8 s (solution) |
| `make hunt`, `make verdict` | 11.6 to 11.9 s, 23.0 to 24.1 s |
| `make regress` | 8 min 27 s (starter), 9 min 21 s (lab folder with these files), 9 min 30 s (this folder) |

The page's outputs come from one run at the student's path (`/foss/designs/modules/dd105-b`),
after Labs 01 to 06 built from an empty ccache, with this folder's pieces copied into the lab
folder part by part where the page has the student write code. The solution's own runs above
printed the same lines and counts at the same seeds.

## Against the chain spec

| | Spec | Measured here |
|---|---|---|
| Starter | the 14 Lab 06's solution catches | `14 of 15 caught.` on seeds 1 to 5: all but B15 |
| Solution | all 15 (A: `15 of 15 caught.` on seeds 1 to 5) | `15 of 15 caught.` on seeds 1 to 5 |
| Hard rule | B15 | missed by the starter and caught by the solution on seeds 1 to 5 |
| Side catch | B14's first check moves from the register model to `a_I7` | `a_I7` in cycle 1, nine cycles before the predictor's error in cycle 10 (A: cycle 2, ten before) |
| Random order | with `RouterLab07Vseq` skipped, the starter prints Lab 06's lines and catch row | it does, on seeds 1 to 5 (above) |
| Coverage | `router.corner`, for A's 60 bins | 60 bins; 49 of 60 (starter) and 53 of 60 (solution), A's totals |

Where the spec left a choice, or this lab differs from it or from DD105-A:

- **`solutions/` has its own `Makefile` and `tb/`**, as the spec and DD105-A have it, so the
  solution's `TESTS` can differ from the starter's. `scripts/ci/check-labs.sh` runs the solution
  from here.
- **The reset driver is in `router_agents.py`.** File names stay put from lab to lab (decision 2),
  so `labs/ref`'s `router_common.py` isn't carried; `ResetState`, `ResetItem`, `ResetDriver`,
  `ResetSeq` and `SysAgent` sit beside the other agents. The drivers' reset handling is
  `labs/ref`'s, written into Lab 06's drivers so that a run with no reset keeps Lab 06's timing:
  the APB driver keeps its idle cycle before each transfer, and the source driver puts nothing
  random on `in_data` between beats.
- **There is no `rst_soon` pin.** DD105-A's APB driver read a warning signal in the sys interface;
  here the warning is `ResetState`, a Python object the env puts in `ConfigDB`, so the figures
  have no `rst_soon` trace.
- **The reset at time 0 is two cycles long** in this course (`RouterBaseTest.reset()`), so `a_I7`
  fires on B14 in cycles 1 and 2, where DD105-A's fired from cycle 2.
- **`RouterLab07Vseq` takes `backpressure()` from `RouterLab05Vseq`**, which it extends, rather
  than a copy. Its random packets are `NoroutePkt`s in `RouterTest`, which keeps Lab 04's factory
  override.
- **There is no back-door test**, as in Lab 06, so `TESTS` has 10 tests in the starter and 12
  here, where DD105-A had 11 and 13.
- **The regressions take longer than DD105-A's**: 8 min 27 s and 9 min 30 s against A's 3 min
  57 s and 4 min 26 s, because a run of `RouterTest` takes about 12 s here and 7.2 to 7.9 s in
  A; the builds take seconds instead of about two minutes.
- **The templates** are DD105-A's with this course's names: the predictor where A had
  `set_check_on_read`, the coverage groups `router.pkt`, `router.wait` and `router.corner`, and a
  note on cocotb-coverage's percentage in place of A's note on Verilator's.

There is no Lab 08. A later course that starts from this testbench would copy `../tb/` with the
two files here in place of their namesakes, this folder's `Makefile` with its paths changed back
to the lab folder's, and `../src/loc.py` and `../src/predict.py`.
