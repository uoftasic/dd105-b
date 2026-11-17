# Lab 05: reference solution

Open this after `make check-all` prints `3 of 3 caught.` with your own files, or when you're stuck
on a part.

| File | Part | Replaces | What it adds |
|---|---|---|---|
| `router_sva.sv` | 2 | `tb/router_sva.sv` | `a_O1`, `a_O2` and `a_O6` in `router_sva_out`, each with its counter and an `$error` |
| `router_agents.py` | 3 | `tb/router_agents.py` | `SinkDriver`'s countdown and its `rdy` decision |
| `router_vseq.py` | 4 | `tb/router_vseq.py` | `RouterLab05Vseq.body()` |

The files differ from the starter's only in the code that fills each `TODO`, the comments about
the `TODO`s, and the module docstrings. To compare one with yours, run, for example:

```bash
diff tb/router_vseq.py solutions/router_vseq.py
```

To run the solution, keep a copy of your files outside `tb/` and put the solution's in their place:

```bash
mkdir -p mine && cp tb/router_sva.sv tb/router_agents.py tb/router_vseq.py mine/
cp solutions/router_sva.sv solutions/router_agents.py solutions/router_vseq.py tb/
make check-all
cp mine/* tb/
```

Copying `router_sva.sv` rebuilds the simulator at the next `make`; the two Python files rebuild
nothing.

## What changed

| Part | Where | Change |
|---|---|---|
| 2 | `router_sva_out` | `a_O1`: `valid && !ready \|=> valid`; `a_O2`: `valid && !ready \|=> $stable(data) && $stable(last)`; `a_O6`: `valid && ready && beats == 4'd7 \|-> last`; each with its counter and an `$error` |
| 3 | `SinkDriver.run_phase` | while a beat waits: `if not seen: seen = True` / `elif wait_left > 0: wait_left -= 1` |
| 3 | `SinkDriver.run_phase` | `rdy = int(r.pre_ready or (seen and wait_left == 0))` |
| 4 | `RouterLab05Vseq.body()` | every route enabled (DST 0 and 2 to output 0, 1 and 3 to output 1) and `CTRL.EN`; output 1 stalled with 4 three-beat packets to DST 0 and 2 to DST 1, then output 0 stalled the other way round, each drained; oversize packets of 9, 12, 10, 10 and 20 beats with both sinks in `SNK_RANDOM`; then `par()` of `send_rand(300, gap_one_in=5, w_over=15)`, `backpressure()`, and DST 1 and DST 2 moved to the other output and back with 150 cycles between the writes; then a drain and a `DROP_CNT` read |

These are DD105-A's assertions and DD105-A's sequence, step for step. `gap_one_in=5` is one beat
in five, A's `gap_pct` of 20.

## Measured

All in the course image (`asic-edu/gui-rig:2026.08`, which is `hpretl/iic-osic-tools:2026.08`
with X11 layers added) with 2 CPUs and 3 GB, on Nov 17, 2026, `RouterTest` unless a row says
otherwise. A count is the errors that `BaseTest` counted, then the failures the bound assertions
counted (`u_sva.n_fail`); 50 errors is a run the scoreboard stopped at its 50th error.

### Every bug on seed 1

`make check-all BUG_LIST="B01 B02 B03 B04 B05 B06 B07 B08 B09 B10 B11 B12 B13 B14 B15"`, with the
golden router `ok` every time. The middle column is the starter with only Part 2's assertions
added, which is where the page's Part 2 and Part 3 stand.

| Bug | Starter | With Part 2's assertions | Solution |
|---|---|---|---|
| B01 to B04 | MISSED | MISSED | MISSED |
| B05 | caught, 50 errors | caught, 50 | caught, 50 |
| B06 | caught, 50 | caught, 50 | caught, 50 |
| B07 | caught, 3 | caught, 3 | caught, 4 |
| B08 | caught, 50 | caught, 50 | caught, 50 |
| B09 | caught, 50 | caught, 50 and 1 assertion | caught, 50 and 1 assertion |
| B10 | caught, 50 | caught, 50 and 284 assertions | caught, 50 and 284 assertions |
| B11 | MISSED (seeds 1 to 5) | MISSED | caught, 20 and 18 assertions |
| B12 | caught, 50 | caught, 50 and 3 assertions | caught, 50 and 3 assertions |
| B13 | caught, 50 | caught, 50 | caught, 50 |
| B14, B15 | MISSED | MISSED | MISSED |
| total | `8 of 15 caught.` | `8 of 15 caught.` | `9 of 15 caught.` |

The starter's column is Lab 04's solution's, bug for bug and count for count. cocotb seeds each
test from its name, so `RouterTest` sends other packets than Lab 04's `RouterInjectTest` did, but
every caught bug but B07 stops at 50 errors either way, and B07's three errors are again the
`DROP_CNT` reads after phases 1 and 3 and after `close_holes()`. In the solution B07 rises to 4,
because the virtual sequence's last `DROP_CNT` read fails as well:

```text
DROP_CNT read 00007b01, expected 00007a01 (FULL_CNT 122, NOROUTE_CNT 1)
```

B10's 284 assertion failures are 270 of `u_out0.a_O2` and 14 of `u_out1.a_O2`, and B12's 3 are
`u_out1.a_O6`, at 400, 560 and 720 ns. B01 to B04 and B14 are Lab 06's bugs and B15 is Lab 07's:
nothing in this testbench reads `ID`, `CTRL`, `INT_EN`, `STATUS`, `LEVEL` or a `ROUTE` register,
writes `STATUS` or `INT_EN`, checks `irq` or `in_ready` during a reset, uses a bad address, or
resets the router after time 0.

### The lab's own bugs on seeds 1 to 5

`make check-all SEED=<n>`. The starter gave `2 of 3 caught.` on every seed, missing B11, and
caught B10 and B12 with 50 errors and no assertion failures each time. The solution gave
`3 of 3 caught.` on every seed. The golden router was `ok` in every run.

| Seed | B11 | B10 | B12 |
|---|---|---|---|
| 1 | 20 errors, 18 assertions | 50, 284 | 50, 3 |
| 2 | 23, 19 | 50, 173 | 50, 2 |
| 3 | 35, 28 | 50, 449 | 50, 3 |
| 4 | 30, 25 | 50, 248 | 50, 3 |
| 5 | 23, 19 | 50, 200 | 50, 3 |

So B11 meets the course's rule: missed by the starter and caught by the solution on seeds 1 to 5.

### The golden router on several seeds

| Run | Result |
|---|---|
| the starter's `make seeds SEEDS="1 2 3 4 5"` | `5 ok  (5 runs)`, 5.7 to 5.8 s a run |
| the solution's `make seeds SEEDS="1 2 3 4 5"`, then `SEEDS="6 7 8 9 10"` | `5 ok  (5 runs)` each, 7.0 to 7.5 s a run |
| the solution's `make seeds TEST=RouterLab05Test` (seeds 1 to 10) | `10 ok  (10 runs)` |
| the solution's `make seeds TEST=RouterSinkTest SEEDS="1 2 3 4 5"` | `5 ok  (5 runs)` |
| the solution's `make regress SEEDS="1 2 3 4 5"`, all eight tests | `40 ok  (40 runs)` in 188 s, `87.50 %   49 of 56 bins` |

The seven bins the regression leaves empty are the seven of `router.pkt.x_fate_level` that the
specification rules out, as in Lab 04. `router.pkt` has 42 bins now (`oversize` is new) and
`router.wait` 14, all hit. The three numbers are DD105-A's (A: 49 of 56, `87.5%`).

### `make check`

With no `BUG`, `make check` grades B11. The starter:

```text
 VERDICT: FAIL -- your test passes B11_cut_packet_has_no_last too.
```

The solution:

```text
 VERDICT: PASS
   Your test passes the golden design, and on B11_cut_packet_has_no_last a check FIRED:
       RouterTest: AssertionError: 20 errors logged, the first: output 1: got 55 in cycle 5496, expecte
       router_sva.sv:58: Assertion failed in router.u_sva.u_out1.a_O6: O6: an output packet is longer t
```

and `make check BUG=B10` and `make check BUG=B12` printed `VERDICT: PASS` too.

## B11

Under B11 the 8th beat of a cut packet has no `out_last`. No Lab 04 test sends a packet of more
than 8 beats (`hides behind: sending only legal packets of 8 beats or fewer`), so the starter misses
it on seeds 1 to 5. The solution's step 3 sends oversize packets to every DST. On seed 1 the first
`a_O6` failure and the scoreboard's first error are in the same cycle, in step 3:

```text
[54960000] %Error: router_sva.sv:58: Assertion failed in router.u_sva.u_out1.a_O6: O6: an output packet is longer than 8 beats
 54955.00ns ERROR    ..ckpressure/tb/router_env.py(116) [uvm_test_top.env.sb]: output 1: got 55 in cycle 5496, expected 55 last
```

The edge at 10*n* ns ends cycle *n*, so 54960000 ps is the edge that ends cycle 5496. Lab 04's
scoreboard already queued the 8th beat of a forwarded packet with `last` set, but no Lab 04 test
had sent one. On `RouterLab05Test` B11 gave `32 errors, 27 assertions`, first in cycle 116 on
output 0.

## Side catches: B10 and B12

| Bug | First check in `RouterTest`, seed 1 | First assertion | How the page uses it |
|---|---|---|---|
| B10 | the scoreboard, `output 0: got e5 last in cycle 34, expected 80`, in Lab 04's stall test (Lab 03's `close_holes()` reaches B10 too) | `u_out0.a_O2` at the edge that ends cycle 26 | Part 1 asks the student to predict the cycle in which `out0_data` first changes while `80` waits; Part 2's `a_O2` confirms cycle 26, 8 cycles before the scoreboard; the two figures show 190 to 360 ns |
| B12 | the scoreboard, `output 1: got c2 in cycle 34, expected 3b` (from Lab 04's stall test) | `u_out1.a_O6` at the edge that ends cycle 40 | Part 2 asks why O6, not O1 or O2, fires: output 1 is always ready in phase 1, so its held beat is taken again and again. Part 4 runs B12 on `RouterLab05Test`, which stalls output 1 first: `u_out1.a_O2` fails at the edge that ends cycle 33 and the scoreboard only in cycle 352 (`output 1: got 46 in cycle 352, expected 44`, `50 errors, 39 assertions`). Finishing question 1 is about O7 |

Seed 1's B10 story, from the waves of `make waves BUG=B10` (cycles of the monitors' count):
phase 1 routes DST 2 to output 0, which is ready in 5% of cycles. The packet `80 e5` comes in with
its header in cycle 21 and `e5` in cycle 24; the golden router puts `80` on `out0_data` in cycle 23
and keeps it there until output 0's sink is ready, in cycle 34. B10 loads `e5` over it in cycle 26,
and `level0` drops from 2 to 1, so `80` is lost. With the default error limit of 1
(`make run BUG=B10 ERROR_LIMIT=1`), the run stops at that first failure at 260000 ps, the verdict
is `caught: 1 assertion` with a note that Verilator stopped the run, and `exit_status` holds 1.

Part 3's sink catches no new bug, and the page says so: `RouterTest` keeps its sinks in Lab 04's
`SNK_PCT` mode until the virtual sequence, so `make check-all` gives the same counts after Part 3
as after Part 2.

## The order of random draws

Every random value in this testbench comes from Python's `random`, in one sequence, so a piece
that draws one value more moves every value after it (chain spec, decision 8). This lab's
additions draw nothing in Lab 04's tests:

- `SinkDriver` in `SNK_PCT` with no item held runs Lab 04's loop exactly: right after each rising
  edge it draws only when `ready_pct` is between 0 and 100, and it doesn't wait for the falling
  edge, so its place among the tasks that wake at each rising edge is Lab 04's.
- `SinkSeq` makes each item's values after `start_item()` returns, which in pyuvm 4.0.1 is when
  the driver asks for the item (`get_next_item()` sets the item's `start_condition`). In
  `SNK_PCT` the driver asks for none, so the sequences draw nothing.
- `RouterPkt`'s fourth `dist` value with weight 0, and its fourth `c_len` branch, changed none of
  pyvsc's draws, and `gap_one_in` at 4 makes `build()` draw what Lab 04's did.
- `RouterTest` makes its virtual sequence after `RouterInjectTest`'s steps.

The probe: Lab 04's solution, this lab's starter and this lab's solution ran Lab 04's five tests on
the golden router, `RouterInjectTest` on seeds 1 to 5 and the others on seed 1, and every
`[PHASE]`, `[DROP]`, `[HOLES]` and `[SB]` line, with its time and file name cut, was the same in
all three. On seed 1, `RouterInjectTest` printed
`804 packets in: 193 to output 0, 196 to output 1, 218 NOROUTE, 197 FULL` and
`beats checked: 860 on output 0, 818 on output 1`, which are Lab 04's Part 4 lines. That makes
`RouterInjectTest` the decision's probe class, shipped rather than built for the check, and
Part 1 of the page has the student run it.

## Times

| What | Time |
|---|---|
| `make build`, after the builds of Labs 01 to 04 | 2.4 s, 6 of 7 files from the ccache |
| `make build` after Part 2's edit to `router_sva.sv` | 2.4 s, 6 of 7 files from the ccache |
| `make build` with an empty ccache | 8.0 s |
| `make run` after a change to the Python | no rebuild |
| `make run` (`RouterTest`) | 5.7 to 7.6 s (starter), 7.0 to 7.4 s (solution) |
| `make run TEST=RouterInjectTest`, `RouterStallTest`, `RouterRandTest`, `RouterSinkTest` | 5.3 to 5.8 s |
| `make run TEST=RouterLab05Test` | 3.3 to 3.5 s |
| `make run TEST=RouterFillTest`, `RouterClassTest` | 1.9 to 2.5 s |
| `make check-all` | 16.5 to 16.8 s (starter), 19.3 to 19.8 s (solution) |
| `make check-all` over all 15 bugs | 70 s (starter), 85 s (solution) |
| `make seeds SEEDS="1 2 3 4 5"` | 29 s (starter), 35 to 36 s (solution) |
| `make regress SEEDS="1 2 3 4 5"` | 188 s |

## Against the chain spec

| | Spec | Measured here |
|---|---|---|
| Starter | B05 to B10, B12, B13 (Lab 04's solution row) | `8 of 15 caught.`: B05 to B10, B12, B13 |
| Solution | B05 to B13 (A: `9 of 15 caught.`) | `9 of 15 caught.`: B05 to B13 |
| Hard rule | B11 | missed by the starter and caught by the solution on seeds 1 to 5 |
| Side catches | B10 (A: assertion in cycle 48, scoreboard in 56), B12 (A: scoreboard in cycle 24, `a_O6` in 64; on `router_lab05_test` `a_O2` in 40, scoreboard in 361) | B10: `a_O2` in cycle 26, scoreboard in 34; B12: scoreboard in cycle 34, `a_O6` in 40; on `RouterLab05Test` `a_O2` in 33, scoreboard in 352 |

Every error count in the table of all 15 bugs matches DD105-A's (`solutions/README.md` of its Lab
05) except B11's, which is 20 where A's was 33. The assertion counts differ: B10 284 against A's
244, B11 18 against 26, and B12 3 against 1. The packets are this course's, so the cycles in which
the router goes wrong are too. Where the spec left a choice, or this lab differs from it:

- **`OutCfg`, not `SinkCfg`.** The spec names `SinkCfg (mode, ready_pct, stall)`. Lab 04's
  `OutCfg` (`port`, `ready_pct`) gains `mode`, as DD105-A's `out_cfg` did, because the base test,
  `RouterStallTest` and Lab 04's page already use it. There is no `stall` field: the virtual
  sequence's `stall(p)` is `SNK_PCT` with `ready_pct` 0, DD105-A's definition, which is also how
  `close_holes()` stalls output 0.
- **`SinkDriver`, `ReadyItem` and `SinkSeq`** are the spec's names. The agent keeps Lab 04's name,
  `OutAgent`, and gains a sequencer.
- **`gap_one_in`, not `gap_pct`.** Lab 03's packet draws a gap with `random.randrange(4) == 0`,
  and a percentage would draw differently (`randrange(100) < 25`), which would change every
  packet of Lab 04's tests. `send_rand()` takes `gap_one_in` and `w_over`; the solution's
  `gap_one_in=5` is A's `gap_pct` of 20.
- **No `try_next_item()`.** The driver calls `get_next_item()` only when its mode isn't `SNK_PCT`
  and it holds no item, and `SinkSeq` is always waiting in `start_item()` with the next one, so the
  call returns in the same time step. Part 3's first question asks why.
- **The error limit.** `make run BUG=B10 ERROR_LIMIT=1` (above), where A's page set `PLUSARGS=`.
- **Route writes** are stamped with the cycle the APB monitor saw them complete, and applied at a
  header of a later cycle, as A's. `DROP_CNT` writes still apply at once; nothing writes it under
  traffic.
- **"Checked nothing."** Lab 04's scoreboard already had `no beat was checked`, which is what
  fails the starter's `RouterLab05Test`; this lab adds no other.
- **The `[PHASE]` line** names a sink's mode when it isn't `SNK_PCT` (`output 0 SNK_RANDOM`), and is
  Lab 04's line otherwise.
- **`tb/router_sva.sv`'s comment** had a line starting with the simulator's name, which Verilator
  5.050 read as a directive (`%Error-BADVLTPRAGMA`) and the build stopped. The comment is reworded
  in `tb/` and `solutions/`; the assertions are DD105-A's.

## Lab 06's files

Lab 06's starter is this lab's `tb/` with the three solution files copied in, which makes six
files: `router_agents.py`, `router_env.py`, `router_vseq.py`, `test_router.py`, `router_sva.sv`
and `router_sva_bind.sv`; then `Makefile` and `src/loc.py`. The chain spec ("Lab 06", Starter)
lists what it adds, among them `tb/router_ral.py`.

What the Lab 06 builder needs to know about this code:

- Registers are still reached by raw APB: `ApbRwSeq`, the base test's `write_reg()` and
  `read_reg()`, and the virtual sequence's `wr()` and `rd()`. The scoreboard checks only `DROP_CNT`
  and the output beats; `irq` is read by nothing, and nothing checks `in_ready` or `CTRL`.
- There is no reset driver, and nothing resets after time 0; the scoreboard has no reset handling.
- The base test starts a `SinkSeq` on each output before it resets the router. A test without
  them would hang in `get_next_item()` the first time a sink leaves `SNK_PCT`.
- `RouterTest` runs `RouterInjectTest`'s steps and then the virtual sequence. A sequence or a
  predictor that draws from `random` before the virtual sequence moves every packet after it;
  `RouterInjectTest` is the probe for that.
- `ApbMonitor` stamps each transfer with its cycle, and the scoreboard applies route writes by
  that stamp.
- Copying a file over a `tb/` file with `cp -p` keeps its old time, and `make` then thinks the
  simulator is newer than the assertions and doesn't rebuild. CI's `restore_starter` copies with
  `-p` but runs `make clean` after; a measurement that swaps `router_sva.sv` should `touch` it.
