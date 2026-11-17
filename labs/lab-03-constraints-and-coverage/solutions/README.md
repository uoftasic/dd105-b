# Lab 03: reference solution

Open this after `make check-all` prints `2 of 2 caught.` with your own files, or when you're stuck
on a part.

| File | Replaces | What it adds |
|---|---|---|
| `coverage.py` | `tb/coverage.py` | the coverpoints `router.pkt.len`, `dst`, `fate` and `level` and the cross `router.pkt.x_fate_level`, as decorators on `sample_pkt()`; the level's bins are ranges with a `rel=` (Part 2) |
| `packet.py` | `tb/packet.py` | in `RandPacket`: `length` made random, weights `w_one`, `w_mid`, `w_max` of 25/50/25, `c_kind`, a `dist` on `kind`, and `c_len`, which picks `length` from `kind`; `post_randomize()` only builds the beats (Part 3) |
| `test_router.py` | `tb/test_router.py` | `FillPlan` and `close_holes()` (Part 4) |

These files differ from the starter's only in the code that fills each `TODO`, the docstrings and
comments about the `TODO`s, and three `# noqa` comments that the starter needs on imports it
doesn't use yet. The rest of `tb/` is the same. To compare one of them with yours, run, for
example:

```bash
diff tb/packet.py solutions/packet.py
```

To run the solution, keep a copy of your files outside `tb/` and put the solution's in their place:

```bash
mkdir -p mine && cp tb/coverage.py tb/packet.py tb/test_router.py mine/
cp solutions/coverage.py solutions/packet.py solutions/test_router.py tb/
make check-all
cp mine/* tb/
```

The files are Python, so swapping them rebuilds nothing.

## The coverage

| Coverpoint | Bins |
|---|---|
| `router.pkt.len` | `len1` to `len8` |
| `router.pkt.dst` | `dst0` to `dst3` |
| `router.pkt.fate` | `noroute`, `full`, `out0`, `out1` (0 to 3, `NOROUTE` to `OUT1` in `tb/tracker.py`) |
| `router.pkt.level` | `empty` (0), `low` (1 to 7), `at_8`, `at_9`, `high` (10 to 16) |
| `router.pkt.x_fate_level` | `router.pkt.fate` crossed with `router.pkt.level`: 20 bins, which `make cov` names as pairs, such as `('out0', 'at_8')` |

That is 41 bins. Twelve can't be hit in this lab:

| Bins | Why |
|---|---|
| `('full', 'empty')`, `('full', 'low')`, `('full', 'at_8')`, `('out0', 'at_9')`, `('out0', 'high')`, `('out1', 'at_9')`, `('out1', 'high')` | the specification: a FULL drop happens only at a level of 9 or more, and a packet is admitted only at 8 or less |
| `('out1', 'low')`, `('out1', 'at_8')` | nothing watches output 1, so the tracker takes its level as 0 |
| `full`, `('full', 'at_9')`, `('full', 'high')` | no test in this lab drops a packet as FULL: Lab 02's scoreboard would expect it on output 0 (see `close_holes()` below) |

So 29 bins are reachable, and the solution's `router_rand_test` and `router_fill_test` together hit
24. The five reachable bins they leave empty are `at_9`, `('noroute', 'empty')`,
`('noroute', 'low')`, `('noroute', 'at_8')` and `('noroute', 'at_9')`.

cocotb-coverage compares a value with a bin with `==` unless the coverpoint has a `rel=`
(`operator.eq` is the default in `cocotb_coverage/coverage.py`). Written as
`bins=[0, (1, 7), 8, 9, (10, 16)]` with no `rel=`, the level coverpoint can never hit `low` or
`high`, and nothing warns; on seed 1 the starter's `router_rand_test` then gave `17 of 41` instead
of `19 of 41`. The solution writes every level bin as a range and passes `rel=in_range`.

## `close_holes()`

`close_holes()` works on output 0 only. It enables `ROUTE0` to output 0 and disables `ROUTE1` to
`ROUTE3` with `PORT` 0 (`write_routes("0---")`), stalls output 0's sink, waits two cycles, and
then sends:

| Packets | Fate in the golden router | Bin |
|---|---|---|
| a `FillPlan`: 1 to 8 packets for DST 0 whose lengths add up to 8, made with `RandPacket.make()` | admitted at levels 0 to 7 | `('out0', 'empty')`, `('out0', 'low')` |
| one random packet for DST 0 (`randomize_with()`, `hdr_dst == 0`) | admitted at level 8 | `('out0', 'at_8')` (B08's hole) |
| one random packet for DST 1, with `c_dst.constraint_mode(False)` | NOROUTE at level 9 to 16 | `('noroute', 'at_9')` or `('noroute', 'high')` (B07's hole) |

Then the sink is released and the outputs drain, and `router_rand_test` reads `DROP_CNT`, which
should be `00000001`. Nothing goes to output 1, and nothing more goes to output 0 while it holds
more than 8 beats. One more random packet for DST 0 at that point is dropped as FULL by the golden
router; the tracker predicts that, but Lab 02's scoreboard expects the packet on output 0 and fails
the golden run. Measured with that packet added to `router_fill_test` in a copy (seed 1):

```
[DROP] DROP_CNT 00000101 as expected
dst 0, 7 beats: 03 2f 67 b4 02 99 32, which went in at 365 ns, never came out of output 0
```

## The `DROP_CNT` read that later labs keep

B07 changes no packet. It adds 1 to `FULL_CNT` (and sets `STATUS.FULL`) for a packet dropped as
NOROUTE while its output holds more than 8 beats, so no packet that comes out shows it. In this lab
the only check that sees it is the `DROP_CNT` read in `Env.check_drops()` after `close_holes()`,
and it catches B07 with one error. Every later lab's graded test has to keep a `DROP_CNT` read
after its fill step, checked against the expected count. The later labs' `BUG_LIST`s don't include
B07, so their graders wouldn't show the loss.

## Measured

All in the course image (`asic-edu/gui-rig:2026.08`, which is `hpretl/iic-osic-tools:2026.08`
with X11 layers added) with 2 CPUs and 3 GB, on Nov 16, 2026. The tests are plain cocotb
(`BASE_TEST := 0`), so the grader's row for a caught bug says `AssertionError` instead of a count;
the counts below are from the assert's message in `make run BUG=<bug>`.

### Every bug on seed 1

`make check-all BUG_LIST="B01 B02 B03 B04 B05 B06 B07 B08 B09 B10 B11 B12 B13 B14 B15"`:

| Bug | Starter | Solution |
|---|---|---|
| golden | ok, passed | ok, passed |
| B01 to B04 | MISSED | MISSED |
| B05 | caught, 312 errors | caught, 395 errors |
| B06 | MISSED | MISSED |
| B07 | MISSED | caught, 1 error |
| B08 | MISSED | caught, 2 errors |
| B09 | caught, 246 errors | caught, 368 errors |
| B10 | MISSED | caught, 5 errors |
| B11 to B15 | MISSED | MISSED |
| total | `2 of 15 caught.` | `5 of 15 caught.` |

B05's counts include the `DROP_CNT` checks that disagreed: the starter's run logged 308 errors from
the scoreboard and 4 from `DROP_CNT`, and the solution's 390 and 5. B09's are all the scoreboard's.
A run with hundreds of errors took as long as a passing one.

### The lab's own bugs on seeds 1 to 5

`make check-all SEED=<n>` gave `0 of 2 caught.` for the starter and `2 of 2 caught.` for the
solution on every seed, with the golden router ok each time. So B07 and B08 both meet the course's
rule: missed by the starter and caught by the solution on seeds 1 to 5. On every seed the solution
caught B07 with 1 error and B08 with 2:

| Seed | `[HOLES]` line of the solution's golden run | B08's second error |
|---|---|---|
| 1 | `packets of 2 2 3 1 beats, then 7 beats for DST 0 and 7 for DST 1` | `dst 0, 7 beats: 24 28 19 4b 53 55 0b, which went in at 55355 ns, never came out of output 0` |
| 2 | `packets of 3 5 beats, then 5 beats for DST 0 and 1 for DST 1` | `dst 0, 5 beats: 22 e1 8e da bf, which went in at 53935 ns, never came out of output 0` |
| 3 | `packets of 8 beats, then 8 beats for DST 0 and 7 for DST 1` | `dst 0, 8 beats: 21 c7 15 06 bb 0b 30 e3, which went in at 55875 ns, never came out of output 0` |
| 4 | `packets of 2 6 beats, then 8 beats for DST 0 and 2 for DST 1` | `dst 0, 8 beats: 22 e2 54 58 99 31 e2 a7, which went in at 53785 ns, never came out of output 0` |
| 5 | `packets of 1 5 2 beats, then 3 beats for DST 0 and 8 for DST 1` | `dst 0, 3 beats: 23 4e 95, which went in at 53905 ns, never came out of output 0` |

B07's one error, and B08's first, was the same line on every seed:
`DROP_CNT read 00000101, expected 00000001 (FULL_CNT 0, NOROUTE_CNT 1)`.

### The golden router on several seeds

`make seeds SEEDS="1 2 3 4 5"` printed `5 ok  (5 runs)` with the starter and with the solution,
and `make seeds` (seeds 1 to 10) printed `10 ok  (10 runs)` with the solution. The starter's
`[TRK]` line said `the highest level a header saw was 2` on all five seeds; the solution's said
15, 13, 16, 16 and 11.

The solution's lines at the end of `router_rand_test` on seed 1, which Lab 04's port of this
testbench should reproduce:

```
[HOLES] output 0 stalled and filled to 8 by packets of 2 2 3 1 beats, then 7 beats for DST 0 and 7 for DST 1
[DROP] DROP_CNT 00000001 as expected
[ENV] sent 806 packets (3488 beats); output 0 took 1583 beats and output 1 took 1898
[TRK] 806 packets: 387 to output 0, 418 to output 1, 1 NOROUTE, 0 FULL; the highest level a header saw was 15
[SB] 806 packets in, 387 predicted for output 0, 387 checked, 0 errors
[COV] router.pkt: 24 of 41 bins hit; coverage.xml written
```

### `make check`

With no `BUG`, `make check` grades B07, the first bug in `BUG_LIST`. The starter:

```
      ok  the golden design                        passed                          3.3s
  MISSED  B07_full_counted_on_disabled_route       passed                          3.1s
------------------------------------------------------------------------
 VERDICT: FAIL -- your test passes B07_full_counted_on_disabled_route too.
```

The solution:

```
 VERDICT: PASS
   Your test passes the golden design, and on B07_full_counted_on_disabled_route a check FIRED:
       router_rand_test: AssertionError: the testbench reported 1 error; the first: DROP_CNT read 00000
```

### Side catches

- **B10** (Lab 05's) is caught by the solution, with 5 errors on seed 1, the first
  `out0 delivered dst 0, 1 beat: 0b at 55485 ns; expected dst 0, 2 beats: 20 a8, which went in at 55195 ns`.
  `close_holes()` stalls output 0 while it holds more than one beat, and under B10 the output
  register loads the next beat during the stall, so output 0 delivers the wrong beats. The starter, whose sinks never
  stall, misses it. The Lab 03 page doesn't mention it. Lab 05 starts from a testbench that already
  catches B10, and reframes it: its assertions name the rule the router breaks, in the cycle it
  breaks it.
- **B02** and **B14** stay missed by both. `close_holes()`'s NOROUTE drop sets `STATUS.NOROUTE`
  with `INT_EN` at 0, which raises `irq` under B02, and B14 makes `in_ready` 1 during the reset at
  time 0; nothing in this lab reads `irq`, `in_ready` during a reset, or `CTRL`.

### The tracker against the router's `level0`

A copy of the solution had two probe tests with the bodies of `router_rand_test` and
`router_fill_test` and a tracker that compared its own level with the router's `level0` at every
falling edge, before handling that cycle's handshakes. On seeds 1 to 5 neither found a difference.
On seed 1 the first compared 5760 cycles, and the router's `level0` reached 16. (The probe tests
had their own names, so their packets were not the shipped tests', for the reason given at the end
of the next section.)

### The order of random draws

The chain's rule is that a lab's additions draw from Python's `random` only after the previous
lab's stimulus, so the earlier counts come out again. `router_rand_test` is new in this lab, so
what that means here is three checks, all on the golden router:

- **Part 4 comes last.** The solution's `router_rand_test` with `close_holes()` skipped (a probe
  copy) printed the same `[PHASE]` and `[DROP]` lines as the solution, and the same `[ENV]`, `[TRK]`
  and `[SB]` lines as the starter with Parts 2 and 3 in it:
  `[ENV] sent 800 packets (3466 beats); output 0 took 1568 beats and output 1 took 1898`. The
  solution's own lines add `close_holes()`'s six packets to those.
- **Part 3 changes the packets.** The starter's and the solution's first `[PHASE]` line are the
  same (`routes 0-11`), and from the second on they differ, because the constrained packet draws
  differently.
- **Nothing else in the lab draws.** `router_class_test` is Lab 02's test, and its packets now come
  from pyvsc, so they differ from Lab 02's (`[ENV] sent 100 packets (474 beats)` with the starter).
  With Lab 02's generator put back in a probe copy and the `DROP_CNT` check left out, the starter's
  `router_class_test` printed Lab 02's lines number for number on seed 1,
  `[ENV] sent 100 packets (476 beats); output 0 took 243 beats and output 1 took 233` and
  `[SB] 100 packets in, 51 predicted for output 0, 51 checked, 0 errors`, and predicted 51, 52, 51,
  44 and 50 packets for output 0 on seeds 1 to 5, as Lab 02's README records. So the sink's stall
  knob, the read, the tracker, the coverage and the split `Env` take no value from `random`.

cocotb seeds Python's `random` for each test from `COCOTB_RANDOM_SEED` and the test's full name
(`regression.py` in cocotb 2.0.1 hashes `test_router.router_rand_test` with SHA-1). So the probes
above had to run under the shipped tests' names: the same body in a test named `ProbeLab02Gen`
sent different packets.

### Times

| What | Time |
|---|---|
| `make venv`, from nothing | 9.5 to 12.2 s in five runs; 37 MB |
| `make build`, after Lab 01's and Lab 02's builds | 2.1 s, 6 of 7 files from the ccache |
| `make run` after a change to `tb/` | no rebuild: the simulator is the router's alone |
| `make run`, `router_rand_test`, starter | 3.0 to 3.3 s; 4.1 to 4.2 s for the first run in a new container |
| `make run`, `router_rand_test`, solution | 4.7 to 4.8 s |
| `make run TEST=router_fill_test`, solution | 1.8 s |
| `make check-all` | 9.3 to 9.7 s (starter), 14.3 to 14.5 s (solution) |
| `make check-all` over all 15 bugs | 50 s (starter), 76 s (solution) |
| `make seeds SEEDS="1 2 3 4 5"` | 16 s (starter), 24 s (solution) |
| `make traps` | 12.8 to 13.0 s |
| `make cov` | 0.06 s (0.62 s once) |

A run takes longer than Lab 02's 0.25 s. `router_rand_test` sends 800 packets to Lab 02's 100;
cocotb reports 1.24 to 1.29 s of real time inside the starter's test and 2.93 to 2.95 s inside the
solution's, whose packets have three random fields and two more constraints; and importing pyvsc
takes about 1.5 s of every run (`labs/ref`'s README).

## Against the chain spec

| | Spec | Measured here |
|---|---|---|
| Starter | B05, B09 | `2 of 15 caught.`: B05, B09 |
| Solution | B05, B07, B08, B09, B10 (A: `5 of 15 caught.`) | `5 of 15 caught.`: B05, B07, B08, B09, B10 |
| Hard rule | B07, B08 | both, on seeds 1 to 5 |
| Side catches | B10 (reframed in Lab 05) | B10, 5 errors on seed 1 |

The catches are the spec's. The coverage numbers match DD105-A's: `19 of 41` bins (A: `46.3% (19/41)`)
before Part 4 and `24 of 41` (A: `58.5% (24/41)`) after it, with the same five reachable bins left
empty. B07's `DROP_CNT` line is DD105-A's, character for character. Where the spec left a choice:

- **The Part 2 trap** is cocotb-coverage's `rel=`: a level coverpoint written with tuples for its
  ranges and no `rel=` misses `low` and `high` without a warning (above). DD105-A's was Verilator's
  `COVERIGN`, which stopped the build.
- **`kind`** is a `vsc.rand_enum_t` of an `enum.IntEnum`. Unconstrained, it came out uniform, and a
  `dist` written with its names put each weight on the right name (`make traps`, lines 1 and 2).
- **`make cov` lists only the empty bins**, so the page reads the length bins' counts from
  `build/coverage/merged.xml` with `grep`.
- **`Env.first_error()`** puts a `DROP_CNT` error before a scoreboard error logged at the same
  time, because `check_drops()` runs before the scoreboard's `report()`; so the first error that
  B08's assert names is the `DROP_CNT` line, the first one in the log.

## Lab 04's files

Lab 04 is a port: its three files, `tb/router_agents.py`, `tb/router_env.py` and
`tb/test_router.py`, are new, written from this lab's `tb/` with these three solution files copied
in. The chain spec ("Lab 04", Starter) lists what they carry over from here: the constraints and
the 25/50/25 weights, the per-beat gaps, the coverage with the same names, bins and fate encoding
(41 bins), `FillPlan` and `close_holes()` with the same packets in the same order, the tracker's
level rule, the expected `DROP_CNT` of `00000001`, and `router_class_test` as `RouterClassTest`.

What the Lab 04 builder needs to know about this code:

- The generator makes a new `RandPacket` for every packet and randomizes it at once, so each packet
  draws one value from Python's `random` for pyvsc's random state at its first `randomize()`, then
  all its payload bytes, then all its gaps (`build()`). The starter's packet also draws the length
  of a `LEN_MID` packet, before `build()`. `close_holes()` draws the
  `FillPlan` first, builds the fill packets with `make()` (payload bytes only, no gaps), then the
  packet for DST 0 and the packet for DST 1.
- cocotb seeds each test from its own name, so Lab 04's `RouterRandTest` won't send this lab's
  packets even where it draws in the same order.
- `close_holes()` makes its two random packets with `env.gen.new_packet()`; in Lab 04 they must not
  come from the factory (the chain spec's Lab 04 risk).
