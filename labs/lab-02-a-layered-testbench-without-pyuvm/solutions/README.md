# Lab 02: reference solution

Open this after `make check-all` prints `2 of 2 caught.` with your own monitor and scoreboard.

| File | What it is |
|---|---|
| `monitor.py` | `tb/monitor.py` with `run()` written |
| `scoreboard.py` | `tb/scoreboard.py` with `run()`, `predict()`, `check()` and the checks in `report()` written, and two helper coroutines for `run()` |

Apart from the first line of each docstring, the solution differs from the shipped files only in
the bodies that the `TODO`s mark and in the scoreboard's two helper coroutines. Compare them with:

```bash
diff tb/monitor.py solutions/monitor.py
diff tb/scoreboard.py solutions/scoreboard.py
```

To run the solution, keep copies of your own files outside `tb/` and put the solution in their
place:

```bash
cp tb/monitor.py my_monitor.py
cp tb/scoreboard.py my_scoreboard.py
cp solutions/monitor.py solutions/scoreboard.py tb/
make check-all
cp my_monitor.py tb/monitor.py
cp my_scoreboard.py tb/scoreboard.py
```

Swapping the files rebuilds nothing, because the simulator is built from the router's RTL alone:
`make build` printed `Vtop is up to date.` after each swap, in 0.07 s.

## The monitor and the scoreboard

| Piece | How |
|---|---|
| `Monitor.run()` | At each falling edge: while `rst_n` is 0, drop the half-built packet; in a handshake cycle (`valid` and `ready` both 1), add the beat, and on `last` stamp `t_last` and put the packet in `to_sb` |
| `Scoreboard.run()` | starts `take_inputs()` (`from_in` to `predict()`) and `take_outputs()` (`from_out0` to `check()`) with `cocotb.start_soon`, and awaits both |
| `Scoreboard.predict()` | appends the packet to `expected` when `ROUTE[DST]` is enabled with `PORT` 0 |
| `Scoreboard.check()` | an output 0 packet with nothing expected is an error; otherwise it takes the oldest expected packet and compares the two with `Packet.same()` |
| `Scoreboard.report()` | each packet still expected is an error, and so is a run that checked no packets |

Each error goes through `self.error()`, which logs it on the `tb.sb` logger and counts it. The
test's last line asserts that the count is 0, so the run ends with `AssertionError`, and the
message carries the count and the first error.

## Measured

All in the course image (`asic-edu/gui-rig:2026.08`, which is `hpretl/iic-osic-tools:2026.08`
with X11 layers added) with 2 CPUs and 3 GB, on Nov 16, 2026. The test is plain cocotb
(`BASE_TEST := 0`), so the grader's row for a caught bug says `AssertionError` instead of a count;
the counts below are from the `[SB]` line of `make run BUG=<bug>` and from the assert's message.

### Every bug on seed 1

`make check-all BUG_LIST="B01 B02 B03 B04 B05 B06 B07 B08 B09 B10 B11 B12 B13 B14 B15"`:

| Bug | Starter | Solution |
|---|---|---|
| golden | ok, passed | ok, passed |
| B01 to B04 | MISSED | MISSED |
| B05 | MISSED | caught, 47 errors |
| B06 to B08 | MISSED | MISSED |
| B09 | MISSED | caught, 48 errors |
| B10 to B15 | MISSED | MISSED |
| total | `0 of 15 caught.` | `2 of 15 caught.` |

The starter's monitor and scoreboard are empty, so every run prints
`[SB] 0 packets in, 0 predicted for output 0, 0 checked, 0 errors` and passes.

### The lab's own bugs on seeds 1 to 5

`make check-all SEED=<n>` gave `0 of 2 caught.` for the starter and `2 of 2 caught.` for the
solution on every seed, with the golden router ok each time. So B05 and B09 both meet the course's
rule: missed by the starter and caught by the solution on seeds 1 to 5. The solution's error
counts:

| Bug | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Seed 5 |
|---|---|---|---|---|---|
| B05 | 47 | 47 | 46 | 44 | 49 |
| B09 | 48 | 48 | 42 | 41 | 40 |

The solution's `[SB]` lines on seed 1:

```
[SB] 100 packets in, 51 predicted for output 0, 51 checked, 0 errors
[SB] 100 packets in, 51 predicted for output 0, 49 checked, 47 errors
[SB] 100 packets in, 51 predicted for output 0, 50 checked, 48 errors
```

for the golden router, B05 and B09. The first errors:

```
out0 delivered dst 0, 4 beats: 03 03 16 14 at 505 ns; expected dst 3, 6 beats: c0 3d 1a f2 51 72, which went in at 265 ns
out0 delivered dst 3, 6 beats: c0 3d 1a f2 51 72 at 775 ns; expected dst 0, 1 beat: 05, which went in at 535 ns
```

Under B05 the router reads header bits 6:5, so `c0` (`DST` 3) goes to output 1 by `ROUTE2`.
Under B09 the 16th beat into output 0, `05`, is lost, and the six beats of the first packet come out
of the buffer a second time.

### The golden router on several seeds

`make seeds SEEDS="1 2 3 4 5"` printed `5 ok  (5 runs)` with the starter and with the solution,
and `make seeds` (seeds 1 to 10) printed `10 ok  (10 runs)` with the solution. The solution
predicted 51, 52, 51, 44 and 50 packets for output 0 on seeds 1 to 5, and checked every one.

### `make check`

With no `BUG`, `make check` grades B05, the first bug in `BUG_LIST`. The starter:

```
      ok  the golden design                        passed                          0.2s
  MISSED  B05_dst_field_off_by_one                 passed                          0.2s
------------------------------------------------------------------------
 VERDICT: FAIL -- your test passes B05_dst_field_off_by_one too.
```

The solution:

```
      ok  the golden design                        passed                          0.3s
  caught  B05_dst_field_off_by_one                 AssertionError                  0.3s
        router_class_test: AssertionError: the testbench reported 47 errors; the first: out0 delivered dst 0
------------------------------------------------------------------------
 VERDICT: PASS
```

### The stimulus experiments (Part 4 of the writeup)

With the solution, seed 1:

| `PLUSARGS` | B05 | B09 |
|---|---|---|
| `+ROUTES=0000` | MISSED | |
| `+DSTS=0 +N=32` | MISSED | |
| `+DSTS=0` | caught, 68 errors | |
| `+DSTS=0 +LEN=1 +N=15` | | MISSED |
| `+DSTS=0 +LEN=1 +N=16` | | caught, 1 error |

`+DSTS=0` gave `[SB] 100 packets in, 100 predicted for output 0, 64 checked, 68 errors`, and
`+N=16`'s one error was
`out0 delivered dst 0, 1 beat: 00 at 405 ns; expected dst 0, 1 beat: 0f, which went in at 385 ns`.

### The order of random draws

Lab 02 is the first lab on the router, so no earlier solution's summary lines have to come out
again. The check that applies is that the monitor and the scoreboard draw nothing from `random`, so
the starter and the solution send the same packets: only the generator draws, and it makes every
packet before the first beat is driven. On seeds 1 to 5, on the golden router, B05 and B09, the
starter's and the solution's `[ENV] sent` lines were the same in all 15 pairs of runs, for example
`[ENV] sent 100 packets (476 beats); output 0 took 243 beats and output 1 took 233` on seed 1.

### Times

| What | Time |
|---|---|
| `make build`, empty ccache | 7.6 to 7.7 s in four builds, 0 of 7 compiled files from the ccache |
| `make build` after Lab 01's builds of the ALU | 2.2 s in three builds, 5 of 7 from the ccache |
| `make build` after `make clean`, warm ccache | 0.6 s, 7 of 7 from the ccache |
| `make build` after a change to `tb/` | nothing to build (0.07 s) |
| `make run` | 0.25 to 0.27 s for the run, 0.36 to 0.38 s for the command |
| `make run`, the first Python run in a new container | 0.82 s for the run, 0.93 s for the command |
| `make check-all` | 0.91 s (starter), 0.97 to 0.98 s (solution) |
| `make check-all` over all 15 bugs | 4.3 s (starter), 4.6 to 4.8 s (solution) |
| `make seeds SEEDS="1 2 3 4 5"` | 1.4 to 1.5 s |

The two files a build after Lab 01's compiles are `Vtop__ALL.o`, the router, and `verilator.o`,
cocotb's `main()` for the simulator, which includes `Vtop.h`, the header Verilator writes for
whichever design it built (ccache's log of the build). The other five are Verilator's support
code, which Lab 01's builds left in the ccache.

## Against the chain spec

| | Spec | Measured here |
|---|---|---|
| Starter | catches none; the empty scoreboard prints `[SB] 0 packets in` | `0 of 15 caught.`, with that line in every run |
| Solution | B05, B09 (A: `2 of 15 caught.`, 50 and 46 `$error`s on seed 1) | `2 of 15 caught.`, 47 and 48 errors on seed 1 |
| Hard rule | B05, B09 | both, on seeds 1 to 5 |
| Side catches | none | none |

The catches are the spec's. The counts differ from DD105-A's because the packets do: A's come from
`$urandom` and these from Python's `random`.

Two Part 4 results match A's exactly, and neither is luck:

- `+DSTS=0` gives 68 errors in both courses because the count follows from `+N` and the routing
  table, not from the random bytes or gaps. The header
  is `DST` 0 and the sequence number, so under B05 packets 32 to 63 and 96 to 99 (bit 5 set) go to
  output 1. Output 0 delivers packets 0 to 31 and 64 to 95, and from its 33rd packet on each one is
  compared with the wrong expected packet: 32 mismatches, then 36 packets that never came out.
- `+DSTS=0 +LEN=1 +N=16` prints the same message as A's, `00 at 405 ns`, `0f`, `385 ns`. The times
  mean different things: A stamped a packet at the rising edge its last beat moved, at 5 ns past a
  multiple of 10 in A's clock, and this monitor stamps it at the falling edge in the middle of that
  beat's handshake cycle, 5 ns before the beat moves, which in this course's clock is also 5 ns past
  a multiple of 10.

Two details the spec leaves open:

- Each piece logs on its own logger, `tb.env`, `tb.drv`, `tb.in`, `tb.out0` and `tb.sb`, which
  cocotb prints in its name column. Python's root logger shows only warnings and errors, so
  `Env.__init__` sets the `tb` loggers to INFO. A monitor's `+SHOW` line is the packet alone; the
  time is cocotb's column.
- `Driver`, `ApbMaster` and `Sink` follow the spec's timing rule: they drive right after a rising
  edge and read the pins at the falling edge. `ApbMaster.write()` starts with a rising edge, so
  writes have one idle cycle between them, as A's did.

## Lab 03's files

Lab 03 starts from this lab's `tb/` with `solutions/monitor.py` and `solutions/scoreboard.py` copied
in, and keeps their code. The chain spec ("Lab 03", Starter) lists what it adds:

- `driver.py`: `Sink.stall` and `ApbMaster.read(addr)`;
- `packet.py`: `RandPacket`, a `@vsc.randobj` subclass of `Packet` with `hdr_dst`, `kind`,
  `route_en` and `c_dst`; `Packet` and `RouterCfg` stay;
- `generator.py`: randomizes `RandPacket`s made inside the test; `+DSTS` and `+LEN` go;
- `tracker.py` and `coverage.py`, new;
- `env.py`: `run()` split into steps the tests call (start, `write_routes()`, `send()`, `drain()`,
  `check_drops()`, report), with `run()` still calling them in this lab's order;
- `test_router.py`: `router_rand_test` and `router_fill_test` before `router_class_test`;
- `traps/traps.py`, outside `tb/`, and a `traps` target;
- `Makefile`: `TESTS := router_rand_test router_fill_test router_class_test`,
  `BUG_LIST := B07 B08`, `NEEDS_VENV := 1`, `BASE_TEST := 0`.

What the Lab 03 builder needs to know about this code: the generator draws, for each packet in
turn, its length, then its `DST`, then each beat's byte (none for the header) and its gap.
`router_class_test` keeps that order if Lab 03 leaves `Generator` as it is for that test.
`scoreboard.py`'s docstring says the sinks are always ready, which Lab 03 changes to "until Part 4".
