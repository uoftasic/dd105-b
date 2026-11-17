# Lab 04: reference solution

Open this after `make check-all` prints `2 of 2 caught.` with your own tests, or when you're stuck
on a part.

| File | Replaces | What it adds |
|---|---|---|
| `router_env.py` | `tb/router_env.py` | `out1` made and connected in `RouterEnv`, every forwarded beat queued in `write_in` (Part 2); output 1's real level in `level()` (Part 3) |
| `test_router.py` | `tb/test_router.py` | `RouterStallTest.set_sinks()` (Part 3); `NoroutePkt` and `RouterInjectTest.build_phase()` (Part 4) |

`router_agents.py` has no solution copy: nothing in it changes. The two files differ from the
starter's only in the code that fills each `TODO`, the comments about the `TODO`s, and the
docstrings of the module and of the three classes the student writes. To compare one with yours,
run, for example:

```bash
diff tb/router_env.py solutions/router_env.py
```

To run the solution, keep a copy of your files outside `tb/` and put the solution's in their place:

```bash
mkdir -p mine && cp tb/router_env.py tb/test_router.py mine/
cp solutions/router_env.py solutions/test_router.py tb/
make check-all
cp mine/* tb/
```

The files are Python, so swapping them rebuilds nothing.

## What changed

| Part | Where | Change |
|---|---|---|
| 2 | `RouterEnv.build_phase`, `connect_phase` | `out1` made with `OutAgent.create("out1", self)` and its monitor connected to `sb.out_imp` |
| 2 | `RouterScoreboard.write_in` | every forwarded beat queued on `expected[in_port]`, not only output 0's |
| 3 | `RouterScoreboard.level` | the `if p == 1: return 0` that took output 1's level as 0, as Lab 03's tracker did, removed |
| 3 | `RouterStallTest.set_sinks` | output 0 ready in 5% of cycles in phases 1 and 3, output 1 in phases 2 and 4, the other output in 100% |
| 4 | `NoroutePkt` | a `@vsc.randobj` subclass of `RouterPkt` whose `c_dst` (same name, so it replaces the parent's) sends a packet to a disabled route when `to_disabled` is 1; `pre_randomize()` sets `to_disabled` with `random.randrange(4) == 0`, only when some route is disabled |
| 4 | `RouterInjectTest.build_phase` | `uvm_factory().set_type_override_by_type(RouterPkt, NoroutePkt)` before `super().build_phase()` |

## Measured

All in the course image (`asic-edu/gui-rig:2026.08`, which is `hpretl/iic-osic-tools:2026.08`
with X11 layers added) with 2 CPUs and 3 GB, on Nov 17, 2026, `RouterInjectTest` unless a row says
otherwise. The grader's counts are the errors that `BaseTest` counted; 50 is a run the scoreboard
stopped at its 50th error.

### Every bug on seed 1

`make check-all BUG_LIST="B01 B02 B03 B04 B05 B06 B07 B08 B09 B10 B11 B12 B13 B14 B15"`, with the
golden router `ok` both times:

| Bug | Starter | Solution |
|---|---|---|
| B01 to B04 | MISSED | MISSED |
| B05 | caught, 50 errors | caught, 50 |
| B06 | MISSED (seeds 1 to 5) | caught, 50 |
| B07 | caught, 1 | caught, 3 |
| B08 | caught, 2 | caught, 50 |
| B09 | caught, 50 | caught, 50 |
| B10 | caught, 2 | caught, 50 |
| B11 | MISSED | MISSED |
| B12 | MISSED | caught, 50 |
| B13 | MISSED (seeds 1 to 5) | caught, 50 |
| B14, B15 | MISSED | MISSED |
| total | `5 of 15 caught.` | `8 of 15 caught.` |

The starter's column is Lab 03's solution's: B05, B07, B08, B09 and B10. B07 rises from 1 error
to 3, because the stall test holds output 0 above 8 in phases 1 and 3 while `NoroutePkt` sends
packets to disabled routes whose `PORT` is 0, so the `DROP_CNT` reads after those phases fail as
well as the one after `close_holes()`:

```text
DROP_CNT read 0000633a, expected 0000333a (FULL_CNT 51, NOROUTE_CNT 58)
DROP_CNT read 00005e39, expected 00003639 (FULL_CNT 54, NOROUTE_CNT 57)
DROP_CNT read 00000101, expected 00000001 (FULL_CNT 0, NOROUTE_CNT 1)
```

### The lab's own bugs on seeds 1 to 5

`make check-all SEED=<n>` gave `0 of 2 caught.` for the starter and `2 of 2 caught.` for the
solution on every seed, with the golden router ok each time, and the solution caught both B06 and
B13 with 50 errors on every seed. So both bugs meet the course's rule: missed by the starter and
caught by the solution on seeds 1 to 5. The solution's first errors on seed 1:

| Bug | First error |
|---|---|
| B06 | `output 0: got 40 in cycle 57, expected 01` |
| B13 | `output 0: got 94 in cycle 58, expected 1f` |

### The golden router on several seeds

`make seeds SEEDS="1 2 3 4 5"` printed `5 ok  (5 runs)` with the starter and with the solution, and
`make seeds` (seeds 1 to 10) printed `10 ok  (10 runs)` with the solution.

### `make check`

With no `BUG`, `make check` grades B06, the first bug in `BUG_LIST`. The starter:

```text
 VERDICT: FAIL -- your test passes B06_disabled_route_forwards too.
```

The solution:

```text
 VERDICT: PASS
   Your test passes the golden design, and on B06_disabled_route_forwards a check FIRED:
       RouterInjectTest: AssertionError: 50 errors logged, the first: output 0: got 40 in cycle 57, exp
```

and `make check BUG=B13` printed `VERDICT: PASS` too.

### Side catches

| Bug | Owner | Caught by | The solution's first error, seed 1 |
|---|---|---|---|
| B10 | Lab 05 | the starter already (Lab 03's `close_holes()` stalls output 0 with beats in it), and the stall test | `output 0: got 11 in cycle 57, expected 01` |
| B12 | Lab 05 | the stall test: output 1 carries traffic while the two `out_ready` signals differ | `output 1: got 87 in cycle 81, expected cf`, then `got 87` in cycles 82 and 83 |

Lab 04's page mentions neither. Lab 05 starts from this testbench, which already catches both, and
has you write the assertions that show the cycle in which the router goes wrong. Under B12 output
1's buffer moves on `out0_ready`, which is 1 in 5% of cycles in phase 1, while output 1's sink is
always ready, so output 1 holds the beat `87` and its monitor reports it again in each of cycles 81,
82 and 83. The starter's B10 run caught it in `close_holes()`, with
`output 0: got 76 last in cycle 5481, expected 20` and a report of 13 beats that never came out.

B02 and B14 stay missed by both: nothing reads `irq`, `in_ready` during a reset, or `CTRL`.

### Coverage

| Runs | Bins hit |
|---|---|
| the starter's `RouterClassTest`, `RouterInjectTest` and `RouterRandTest` on seed 1, merged (Part 1, step 4) | 24 of 41 |
| the starter's `make seeds SEEDS="1 2 3 4 5"` | 26 of 41 |
| the solution's `make regress SEEDS="1 2 3 4 5"`, 25 runs | 34 of 41 |

The seven bins the regression leaves empty are the ones the specification rules out: a FULL drop
happens only at a level of 9 or more, and a packet is admitted only at 8 or less. The three counts
are DD105-A's (A: `58.5% (24/41)`, 26 of 41 and `82.9% (34/41)`).

## `close_holes()` and the factory

`close_holes()` makes its two random packets in `new_packet()` with the constructor,
`RouterPkt("pkt")`, and `RouterPkt.make()` builds the fill packets the same way, so a factory
override reaches none of them. A probe copy made the two random packets with `create()`, and on
seeds 1 to 20 `RouterInjectTest` ended `BROKEN: SolveFailure` on seeds 11 and 15. Under the
override the packet for DST 0 was a `NoroutePkt`, and when `pre_randomize()` set `to_disabled`,
its `c_dst` asked for a disabled route while the inline constraint asked for DST 0, the one enabled
route. The packet for DST 1 can't fail that way: `close_holes()` switches its `c_dst` off, and a
`NoroutePkt` has only one `c_dst`, its own. In DD105-A it was the packet for DST 1 that failed,
because `constraint_mode(0)` through a `router_pkt` handle left the subclass's `c_dst` on.

## `NoroutePkt` with a `dist`

A probe copy replaced the `pre_randomize()` draw with a random `to_disabled` and
`vsc.dist(self.to_disabled, [vsc.weight(0, 3), vsc.weight(1, 1)])`. `make check-all` gave
`2 of 2 caught.` on seeds 1 to 5, and the golden runs counted 187 to 211 NOROUTE drops in 804 to
806 packets, against 218 in 804 for the solution on seed 1. Its golden runs took 5.6 to 5.8 s,
against 5.1 to 5.2 s for the solution's. The page says a `dist` works too and uses the `pre_randomize()` version.

## The order of random draws

Every random value in this testbench comes from Python's `random`, in one sequence, so a piece
that draws one value more moves every value after it. cocotb seeds `random` for each test from the
seed and the test's full name (`test_router.RouterRandTest` here, `test_router.router_rand_test`
in Lab 03), so this lab's tests never send Lab 03's packets under their own names. Three probes,
all on the golden router, on seeds 1 to 5:

- **The port against Lab 03.** A probe copy of the starter added three tests with Lab 03's names
  (`router_rand_test`, `router_fill_test` and `router_class_test`), each a subclass of its port
  with no code of its own. Each printed Lab 03's solution's routing tables, `[HOLES]` line and
  `DROP_CNT` values, and its packet counts number for number, on all five seeds. On seed 1:
  `806 packets in: 387 to output 0, 418 to output 1, 1 NOROUTE, 0 FULL; the highest level a header
  saw was 15`, with 1583 beats checked on output 0 and 1898 unwatched on output 1, which are Lab
  03's `[TRK]` line and its `output 0 took 1583 beats and output 1 took 1898`, and
  `24 of 41 bins hit`.
- **Parts 2 and 3 draw nothing in the random test.** The solution's `RouterRandTest`,
  `RouterClassTest` and `RouterFillTest` printed the starter's lines, apart from the lines that
  report output 1's beats as checked instead of unwatched. `OutReadyDriver` draws only when
  `ready_pct` is between 0 and 100, so output 1's new driver, always ready, draws nothing.
- **Part 4's additions come with the stall.** The solution's `RouterInjectTest` with the override
  and the stall taken out (a probe copy) printed the starter's `RouterInjectTest` lines, apart
  from the same output-1 lines and `25 of 41` bins instead of 24. The stall's draws come between
  packets, because a sink at 5% draws once a cycle, so `RouterStallTest`'s packets differ from
  `RouterRandTest`'s on the same seed, as well as by name.

## The scoreboard's levels

The monitors all read the pins at the same falling edge, and cocotb runs them in no fixed order,
so `level()` adds back a beat taken in the header's own cycle. A probe copy of the solution
compared `level(0)` and `level(1)` with the router's `level0` and `level1` at every header. On
seeds 1 to 5, in all five tests, it found no difference in 4 to 806 headers a run, with the
router's levels up to 16.

## Times

| What | Time |
|---|---|
| `make build`, after the builds of Labs 01 to 03 | 2.2 s, 6 of 7 files from the ccache |
| `make run` after a change to `tb/` | no rebuild: the simulator is the router's alone |
| `make run`, `RouterInjectTest`, `RouterStallTest` or `RouterRandTest` | 5.0 s (starter), 5.1 to 5.3 s (solution) |
| `make run TEST=RouterFillTest` | 2.0 s |
| `make run TEST=RouterClassTest` | 2.4 s; 3.6 s for the first run in a new container |
| `make check-all` | 15 s (starter), 10 s (solution) |
| `make check-all` over all 15 bugs | 75 s (starter), 63 s (solution) |
| `make seeds SEEDS="1 2 3 4 5"` | 25 s (starter), 26 s (solution) |
| `make regress SEEDS="1 2 3 4 5"` | 97 s |
| `make loc`, `make cov` | under 0.1 s |

A caught bug stops at 50 errors, which is why the solution's `check-all` is faster than the
starter's.

## Against the chain spec

| | Spec | Measured here |
|---|---|---|
| Starter | B05, B07, B08, B09, B10 (A: `5 of 15 caught.`) | `5 of 15 caught.`: B05, B07, B08, B09, B10 |
| Solution | B05 to B10, B12, B13 (A: `8 of 15 caught.`) | `8 of 15 caught.`: B05 to B10, B12, B13 |
| Hard rule | B06, B13 | both, on seeds 1 to 5 |
| Side catches | B12, B10 (reframed in Lab 05) | B12 and B10, 50 errors each on seed 1 |

Every count in the table of all 15 bugs is DD105-A's (`solutions/README.md` of its Lab 04), and so
are the coverage counts. Where the spec left a choice:

- **Output 1's ready in the starter.** `RouterBaseTest` sets `out1_ready` to 0, and the starter has
  no agent on output 1, so `RouterEnv.run_phase` holds the ready of an output with no agent at 1,
  as Lab 03's sink did. DD105-A's top module did this.
- **The sink's draws.** `OutReadyDriver` draws from `random` only between 0 and 100 (above).
- **`drain()`** has DD105-A's shape: both sinks at 100%, then up to 300 cycles until the
  scoreboard expects no beat, then 4 more. Lab 03's waited 50 cycles; a stalled output needs the
  release and the wait.
- **The cycle numbers** in the scoreboard's messages are each monitor's count of falling edges.
- **The scoreboard** carries Lab 03's error for a test that checked nothing (`no beat was
  checked`), which the spec lists as new in Lab 05, and Lab 03's report of beats that never came
  out. Every error goes through `error()`, which stops logging at 50.
- **The base test** is `RouterLabTest`, in `test_router.py`. Its steps are DD105-A's and Lab 03's
  names (`write_reg`, `read_reg`, `write_routes`, `enable`, `new_packet`, `send_random`, `send`,
  `cycles`, `drain`, `check_drops`, `clear_drops`, `close_holes`). It reads `+OVERRIDE` in
  `build_phase`, before it makes the environment, and waits for the body, the watchdog and the
  scoreboard's `stop` event, calling `result()` on whichever finished (`labs/ref` README, cocotb
  2.0.1).

## Lab 05's files

Lab 05's starter is this lab's `tb/` with the two solution files copied in: `router_agents.py`,
`router_env.py` and `test_router.py`. The chain spec ("Lab 05", Starter) lists what it adds:
`tb/router_vseq.py`, `tb/router_sva.sv` and `tb/router_sva_bind.sv`, a reactive sink in place of
`OutReadyDriver`, an oversize kind, `router.wait`, and route writes stamped with their cycle.

What the Lab 05 builder needs to know about this code:

- `ApbMonitor` doesn't stamp a transfer with its cycle, and the scoreboard applies a route write
  as soon as the monitor reports it, which is right only while no header is coming in.
- The scoreboard has no reset handling; nothing resets after time 0.
- `OutReadyDriver` draws only between 0 and 100. A sink in Lab 05's `SNK_PCT` mode that draws the
  same way leaves the packets of a test with always-ready sinks unchanged.
- cocotb seeds by test name, so Lab 05's `RouterTest` won't send this lab's packets; a probe class
  named `RouterInjectTest` in Lab 05's `test_router.py` would.
- `close_holes()`'s packets must keep coming from the constructor (above).
- `RouterLabTest.run_phase` ends the test on the scoreboard's `stop` event; a Lab 05 test that
  starts sink sequences must start them before the body.
