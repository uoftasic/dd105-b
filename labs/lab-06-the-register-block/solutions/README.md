# Lab 06: reference solution

Open this after `make check-all` prints `5 of 5 caught.` with your own files, or when you're stuck
on a part.

| File | Parts | Replaces | What it adds |
|---|---|---|---|
| `router_ral.py` | 2, 3 | `tb/router_ral.py` | the fields of `STATUS`, `DROP_CNT`, `LEVEL` and `RouteReg`; the adapter; `RegResetSeq.body()`; the predictor's `write()`; `RegBitBashSeq.body()` |
| `router_env.py` | 3, 5 | `tb/router_env.py` | the predictor's connections in `RouterEnv.connect_phase()`; the `irq` check in `RouterScoreboard.write_sys()` |
| `router_vseq.py` | 2 to 5 | `tb/router_vseq.py` | `RouterLab06Vseq.body()` |

The files differ from the starter's only in the code that fills each `TODO`, the comments about
the `TODO`s, and the module docstrings. To compare one with yours, run, for example:

```bash
diff tb/router_ral.py solutions/router_ral.py
```

To run the solution, keep a copy of your files outside `tb/` and put the solution's in their place:

```bash
mkdir -p mine && cp tb/router_ral.py tb/router_env.py tb/router_vseq.py mine/
cp solutions/router_ral.py solutions/router_env.py solutions/router_vseq.py tb/
make check-all
cp mine/* tb/
```

All three are Python, so swapping them rebuilds nothing.

## What changed

| Part | Where | Change |
|---|---|---|
| 2 | `StatusReg`, `DropCntReg`, `LevelReg`, `RouteReg` | `STATUS.*` `W1C`, volatile; `DROP_CNT.*` `WC`, volatile; `LEVEL.*` `RO`, volatile; `ROUTEn.EN` and `ROUTEn.PORT` `RW`, not volatile; widths and positions from the register map, configured from bit 0 up; every reset value 0 |
| 2 | `ApbRegAdapter` | `reg2bus()`: `write` from `rw.kind`, `addr` is `int(rw.addr, 16)`, `wdata` is `rw.data` for a write and 0 for a read. `bus2reg()`: `kind`, `data` (`wdata` for a write, `rdata` for a read), and `ERROR_RESP` when `slverr` is 1, otherwise `PASS_RESP` |
| 2 | `RegResetSeq.body()` | `map.reset("HARD")`, then every register with a field that isn't volatile read and compared with `reset_value()` outside `volatile_mask()` |
| 2 | `RouterLab06Vseq.body()` | `RegResetSeq` started on the model, reporting through the env's logger |
| 3 | `RouterRegPredictor.write()` | skip `slverr` and addresses with no register; a write: `predict(wdata, UVM_PREDICT_WRITE)`; a read: compare with the mirror outside the volatile fields, then `predict(rdata, UVM_PREDICT_DIRECT)` |
| 3 | `RegBitBashSeq.body()` | for every bit outside `volatile_mask()`, twice: write the mirror with that bit flipped, take the mirror, read, compare |
| 3 | `RouterEnv.connect_phase()` | `predictor.regs = regs`; `apb.mon.ap` connected to `predictor.analysis_export` |
| 3 | `RouterLab06Vseq.body()` | `RegBitBashSeq`; raw `route(0, 1, 0)`, `route(1, 1, 1)`, `route(2, 0, 1)`, `route(3, 1, 1)`, `ctrl(1)`; `check_reg()` on `CTRL` and the four `ROUTEn` |
| 4 | `RouterLab06Vseq.body()` | `rd()` of every address `good_addr()` rejects, then `wr()` of `0xFFFF_FFFF` to each, then `rd_all_regs()` |
| 5 | `RouterScoreboard.write_sys()` | in a reset cycle `irq` must be 0; in every other cycle `irq` must equal `irq()`, with one error per stretch of wrong cycles |
| 5 | `RouterLab06Vseq.body()` | `DST` 1 disabled, both sinks `SNK_FAST`; a NOROUTE packet, a 9-beat packet, a drain, output 0 stalled and ten 1-beat packets to `DST` 0; a `STATUS` read; each `INT_EN` bit alone for two cycles; `INT_EN` `0b111`, then `STATUS` written with `0b001`, `0b100` and `0b010`, read after each; a drain and `rd_all_regs()` |

These are DD105-A's steps, with the predictor and the two sequences that DD105-A's student took
from SystemVerilog UVM's library written out.

## Measured

All in the course image (`asic-edu/gui-rig:2026.08`, which is `hpretl/iic-osic-tools:2026.08`
with X11 layers added) with 2 CPUs and 3 GB, on Nov 17, 2026, `RouterTest` unless a row says
otherwise. A count is the errors that `BaseTest` counted, then the failures the bound assertions
counted (`u_sva.n_fail`); 50 errors is a run the scoreboard stopped at its 50th error.

### Every bug on seed 1

`make check-all BUG_LIST="B01 B02 B03 B04 B05 B06 B07 B08 B09 B10 B11 B12 B13 B14 B15"`, with the
golden router `ok` every time. The Lab 05 column is from
`labs/lab-05-protocol-rules-and-backpressure/solutions/README.md`.

| Bug | Lab 05's solution | This starter | This solution |
|---|---|---|---|
| B01 | MISSED | MISSED | caught, 3 errors |
| B02 | MISSED | MISSED | caught, 1 |
| B03 | MISSED | MISSED | caught, 4 |
| B04 | MISSED | MISSED | caught, 50 |
| B05, B06 | caught, 50 | caught, 50 | caught, 50 |
| B07 | caught, 4 | caught, 4 | caught, 4 |
| B08 | caught, 50 | caught, 50 | caught, 50 |
| B09 | caught, 50 and 1 assertion | caught, 50 and 1 | caught, 50 and 1 |
| B10 | caught, 50 and 284 assertions | caught, 50 and 284 | caught, 50 and 368 |
| B11 | caught, 20 and 18 assertions | caught, 20 and 18 | caught, 27 and 23 |
| B12 | caught, 50 and 3 assertions | caught, 50 and 3 | caught, 50 and 3 |
| B13 | caught, 50 | caught, 50 | caught, 50 |
| B14 | MISSED | MISSED | caught, 2 |
| B15 | MISSED | MISSED | MISSED |
| total | `9 of 15 caught.` | `9 of 15 caught.` | `14 of 15 caught.` |

The starter's column is Lab 05's solution's, count for count, because the starter's
`RouterTest` sends exactly Lab 05's packets (see "The order of random draws" below). In the
solution the packets after `RouterLab06Vseq` are other ones, so B10 and B11 fail other beats.
B15 is Lab 07's: the router is reset only at time 0.

### The lab's own bugs on seeds 1 to 5

`make check-all SEED=<n>`, with the golden router `ok` every time.

| Seed | Starter | Solution: B01, B02, B03, B04, B14 |
|---|---|---|
| 1 | `0 of 5 caught.` | `5 of 5 caught.`: 3, 1, 4, 50 and 2 errors |
| 2 | `0 of 5 caught.` | `5 of 5 caught.`: 3, 1, 4, 50 and 2 |
| 3 | `0 of 5 caught.` | `5 of 5 caught.`: 3, 1, 4, 50 and 2 |
| 4 | `0 of 5 caught.` | `5 of 5 caught.`: 3, 1, 4, 50 and 2 |
| 5 | `0 of 5 caught.` | `5 of 5 caught.`: 3, 1, 4, 50 and 2 |

So all five meet the course's rule: missed by the starter and caught by the solution on seeds 1 to
5. `RouterLab06Vseq` draws nothing from `random` before its Part 5 packets, and every one of the
five fails in it, so the first errors are the same on every seed:

| Bug | First error, every seed | From |
|---|---|---|
| B01 | `irq is 0 from cycle 5955, but STATUS = 110 and INT_EN = 111 make it 1` | the `irq` check, after `STATUS` is written with `0b001`; the scoreboard's two `STATUS` read errors follow (cycles 5958 and 5965) |
| B02 | `irq is 1 from cycle 5906, but STATUS = 001 and INT_EN = 000 make it 0` | the `irq` check, after the NOROUTE drop in Part 5 |
| B03 | `[RAL] ROUTE3 read 0x2 in cycle 3663; the mirror holds 0x1` | the predictor, during the bit bash; the bit bash's own error follows, and both again in cycle 3677 |
| B04 | `a read of 01, completing in cycle 4143: pslverr is 0, but 01 is a bad address` | the scoreboard, in the bad-address sweep |
| B14 | `[RAL] CTRL read 0x1 in cycle 10; the mirror holds 0x0` | the predictor, on the reset sequence's read of `CTRL`; `RegResetSeq`'s own error follows |

DD105-A's solution caught the five with 3, 1, 4, 50 and 2 errors as well, B01 in cycle 5969, B02
in 5909 and B04 in 4145.

### The golden router on several seeds

| Run | Result |
|---|---|
| the starter's `make seeds SEEDS="1 2 3 4 5"` | `5 ok  (5 runs)`, 7.4 to 7.5 s a run |
| the solution's `make seeds SEEDS="1 2 3 4 5"`, then `SEEDS="6 7 8 9 10"` | `5 ok  (5 runs)` each, 8.1 to 8.7 s a run |
| the solution's `make seeds TEST=RouterLab06Test SEEDS="1 2 3 4 5"` | `5 ok  (5 runs)`, 2.7 s a run |
| the solution's `make regress SEEDS="1 2 3 4 5"`, all nine tests | `45 ok  (45 runs)` in 210 s, `87.50 %   49 of 56 bins` |

The seven bins the regression leaves empty are the seven of `router.pkt.x_fate_level` that the
specification rules out, as in Labs 04 and 05. DD105-A's regression reached the same total (A:
`covergroup : 87.5% (49/56)`).

The solution's `RouterTest` on seed 1 ends with:

```text
[SB] 1135 packets in: 311 to output 0, 288 to output 1, 177 NOROUTE, 359 FULL; the highest level a header saw was 16
[SB] beats checked: 1423 on output 0, 1285 on output 1; 40 DROP_CNT reads checked
[SB] registers: 870 reads, 64 of STATUS checked; 492 transfers to bad addresses; irq checked in 13918 cycles, wrong in 0
[RAL] 624 register reads checked against the mirror, 629 writes predicted; 0 mismatches
```

DD105-A's third line had the same 870 reads, 64 of `STATUS` and 492 bad transfers, and
`irq checked in 14840 cycles`.

### `make check`

With no `BUG`, `make check` grades B01. The starter says
`VERDICT: FAIL -- your test passes B01_status_write_clears_all too.`, and the solution says
`VERDICT: PASS`, with `make check BUG=` B02, B03, B04 and B14 also `VERDICT: PASS`.

## The order of random draws

Every random value in this testbench comes from Python's `random`, one after another, so a piece
that draws one value more moves every value after it (chain spec, decision 8). `RouterTest` runs
`RouterLab06Vseq` first, because a reset sequence has to run while the registers hold their reset
values, so whatever the sequence draws moves Lab 04's and Lab 05's packets. These runs measure it;
the second and fourth are probe builds, not shipped:

- The starter's `RouterTest` printed Lab 05's solution's `[PHASE]`, `[DROP]`, `[HOLES]` and `[SB]`
  lines on seeds 1 to 5, line for line, apart from the new `[SB] registers:` line. Its
  `RouterLab06Vseq` is empty, and making and starting a pyuvm sequence draws nothing.
- The solution's `RouterTest` with `RouterLab06Vseq` left out printed the same lines on seeds 1 to
  5, so nothing else this lab adds (the sys monitor, the scoreboard's model, the predictor, the
  adapter) draws.
- `RouterInjectTest` printed Lab 05's lines on seeds 1 to 5 in the starter and in the solution.
- The solution with `random`'s state saved before `RouterLab06Vseq` and put back after it: the
  sequence drew 8 values (`{'randrange': 8}`), the payload bytes of Part 5's 9-beat packet, and
  every `[PHASE]`, `[HOLES]` and `[DROP]` line after it was Lab 05's, apart from the first
  `DROP_CNT` read, which includes Part 5's two drops (`0000332a` against `00003229`). The `[SB]`
  totals were Lab 05's plus Part 5's 12 packets.
- The page's runs at each stage agree: `RouterTest`'s first two `[SB]` lines are Lab 05's after
  Parts 2, 3 and 4, although by Part 4 `RouterLab06Vseq` runs for about 5,900 cycles before Lab
  04's steps begin, and they change only with Part 5's step.

So the solution's counts move only through those 8 draws.

## Probes

Probe builds, not shipped, behind claims on the page:

| Probe | Result |
|---|---|
| `RegResetSeq` run after `RouterInjectTest`'s steps, golden | `FAIL: 4 errors`: `CTRL` and `ROUTE0` read `0x1`, each reported by the predictor and by `RegResetSeq` (Part 2, step 7) |
| the setup of Part 3, step 2 written through the model (`wr_reg()`), no predictor | `FAIL: 5 errors`, the same five `check_reg` errors as the raw writes (Part 3, step 2): pyuvm doesn't update the mirror after its own write |
| the predictor with `UVM_PREDICT_READ` after a read | the golden router `ok`, `5 of 5 caught.` with the same counts: nothing in this testbench compares a volatile field (Part 3, step 1) |
| `STATUS`'s fields configured from bit 2 down | `make regcheck`: `the model doesn't build: AssertionError: STATUS -- _add_field:                 Fields FULL overlap                 with field                 OVERSIZE`; `make check`: `BROKEN  the register model` and `VERDICT: FAIL -- the register model doesn't build, so nothing was graded.` (Part 2, step 2) |
| the bit bash taking the mirror after the read | the golden router `ok`, with `[RegBitBashSeq] 582 writes and 582 reads of 10 registers (ID, CTRL, STATUS, INT_EN, DROP_CNT, LEVEL, ROUTE0, ROUTE1, ROUTE2, ROUTE3); 0 mismatches`; B03 caught with 2 errors, both the predictor's, instead of 4 (Part 3, step 5) |

The pyuvm 4.0.1 source agrees with the probes: `uvm_reg_field.predict_read()` returns the reset
value for `W1C`, `WC` and 12 other policies; the map predicts after a register's `write()` or
`read()` only when the module global `enable_auto_predict` is set, and it is `False`; and
`uvm_reg._add_field()` compares a field's lowest bit with the highest bit of the field added just
before it.

## Times

| What | Time |
|---|---|
| `make build`, after the builds of Labs 01 to 05 | 2.4 s, 6 of 7 files from the ccache |
| `make build` with an empty ccache | 8.1 s, 0 of 7 files from the ccache |
| `make regcheck`, `make predict` | 0.2 s each |
| `make run` (`RouterTest`) | 7.2 to 8.8 s (starter), 7.2 to 8.1 s at the page's stages, 7.9 to 8.7 s (solution) |
| `make run TEST=RouterLab06Test` | 2.0 s (starter, FAIL), 2.6 to 2.7 s (solution) |
| `make check-all` | 44 to 45 s (starter), 42 to 48 s at the page's stages, 43 to 44 s (solution) |
| `make check-all` over all 15 bugs | 88 s (starter), 88 to 92 s (solution) |
| `make seeds SEEDS="1 2 3 4 5"` | 37 s (starter), 40 to 42 s (solution) |
| `make regress SEEDS="1 2 3 4 5"` | 210 s |

The page's outputs come from one run at the student's path (`/foss/designs/modules/dd105-b`),
after Labs 01 to 05 built from an empty ccache, with the solution's pieces copied in one `TODO`
at a time where the page has the student write code. A second run from nothing matched all 47
command logs line for line, apart from times and, because two docstrings changed between the
runs, the line numbers in the log prefixes.

## Against the chain spec

| | Spec | Measured here |
|---|---|---|
| Starter | B05 to B13 (Lab 05's solution row) | `9 of 15 caught.`: B05 to B13, with Lab 05's counts |
| Solution | everything but B15 (A: `14 of 15 caught.`) | `14 of 15 caught.`: all but B15 |
| Hard rule | B01, B02, B03, B04, B14 | each missed by the starter and caught by the solution on seeds 1 to 5 |
| First checks (A) | B14 reset sequence, B03 predictor in the bit bash, B04 `PSLVERR` in the sweep, B02 and B01 `irq` | the same, with the predictor's error on B14 one line before `RegResetSeq`'s |
| Random order | counts move, as A's did; probe with `RouterLab06Vseq` left out | the starter moves nothing; the solution moves only through Part 5's 8 payload draws (above) |

Every error count over the 15 bugs matches DD105-A's (`solutions/README.md` of its Lab 06),
except B11's, 27 where A's was 22. The assertion counts differ: B10 368 against A's 256, B11 23
against 19, and B13 0 against 1. The packets after the register steps are this course's, so the
cycles in which the router goes wrong are too. Where the spec left a choice, or this lab differs
from it:

- **The predictor is a `uvm_subscriber`.** The spec gives it `Fwd` inputs and a `write_bus()`. It
  has one input, the APB monitor, so it is a subscriber whose `write()` is the TODO, connected as
  the coverage is. `Fwd` lives in `router_env.py`, which imports cocotb-coverage, and the model's
  file must import nothing from the venv (`make regcheck` runs on the image's Python), so
  `router_ral.py` can't import it either. There is no reset input: the router is reset only at
  time 0, and the env puts the mirror at the reset values when it builds the model.
- **`ApbItem` is imported inside `reg2bus()`**, for the same reason: `router_agents.py` imports
  pyvsc.
- **The reset sequence compares with `reset_value()`**, not the mirror, so its own check works
  before the predictor exists. With the predictor connected, its read of `CTRL` under B14 gives
  two errors, the predictor's and its own, as DD105-A's gave two from `mirror()` and the
  predictor.
- **`check_reg()`** is the course's stand-in for `mirror(UVM_CHECK)`: it takes the mirror before
  the read and compares after, as UVM's `mirror()` does. Part 3's order differs from DD105-A's
  for that reason: the page has the student write the raw setup and `check_reg()` first (5 errors
  on the golden router), then the predictor, then the bit bash. DD105-A's bit bash passed on the
  golden router with no predictor connected (A's Part 3, step 3); this lab's bit bash compares
  with the mirror, which only the predictor moves (the `wr_reg()` probe above).
- **`make predict`** (`src/predict.py`) is new: it builds the student's model outside the
  simulator and prints what each kind of `predict()` does to four registers' mirrors, which is
  where the page meets `UVM_PREDICT_READ` on `W1C` and `WC` fields.
- **"Nothing was checked."** Lab 05's scoreboard failed a test in which no output beat matched;
  this one fails a test in which no beat matched and no register was read, because a register
  test checks its reads. DD105-A's Lab 06 made the same change.
- **No back door.** pyuvm raises `UVMNotImplemented` for a back-door access (the course design
  measured it, and the map's source raises it), so DD105-A's Part 6 isn't here, and nothing on
  the page reads the register flip-flops through cocotb.
- **`RegSeq.post_body()`** logs one line per sequence, `[RegResetSeq] 0 writes and 7 reads of 7
  registers (...)`, which the page greps where DD105-A's grepped UVM's `Verifying reset value`
  lines.

## Lab 07's files

Lab 07's starter is this lab's `tb/` with the three solution files copied in, which makes seven
files: `router_agents.py`, `router_env.py`, `router_ral.py`, `router_vseq.py`, `test_router.py`,
`router_sva.sv` and `router_sva_bind.sv`; then `Makefile`, `src/loc.py` and `src/predict.py`.

What the Lab 07 builder needs to know about this code:

- There is still no reset driver; `RouterBaseTest` resets the router once, at time 0. The
  scoreboard's `write_sys()` resets only its `STATUS` and `INT_EN` model in a reset cycle, and
  nothing throws away expected beats, pending route writes or drop counts. The predictor has no
  reset input; the env calls `regs.map.reset("HARD")` once, when it builds the model.
- `RouterTest` runs `RouterLab06Vseq` first, then `RouterInjectTest`'s steps, then
  `RouterLab05Vseq`. `RouterLab06Vseq` draws 8 values from `random`, all in Part 5's 9-beat
  packet; a sequence added last draws after everything above.
- `RouterLab06Vseq` leaves `INT_EN` at `0b111`, so `irq` is the OR of `STATUS` from then on, and
  nothing clears `STATUS` after it.
- The register helpers in `RouterBaseVseq` (`wr_reg`, `rd_reg`, `check_reg`, `rd_all_regs`) take a
  `cocotb.triggers.Lock` per register, kept on the env. `RegSeq` reports through the logger it is
  given; the virtual sequences give it the env's.
- The scoreboard reads `STATUS` as it was in the cycle before a read completes, and keeps
  `status_in` for the last 8 cycles.
