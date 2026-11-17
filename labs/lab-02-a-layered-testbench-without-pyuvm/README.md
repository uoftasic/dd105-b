# Lab 02: A layered testbench without pyuvm

Writeup: [`docs/labs/lab-02-a-layered-testbench-without-pyuvm-overview.md`](../../docs/labs/lab-02-a-layered-testbench-without-pyuvm-overview.md)

This package is a testbench for the router's input and output 0, written as plain Python classes
on cocotb that pass packets to each other through queues. The generator, driver, sinks, APB writer
and environment are shipped; you write the monitor (`tb/monitor.py`) and the scoreboard
(`tb/scoreboard.py`), and catch B05 and B09.

Run it in the course image, from this folder:

```bash
make build                                   # the simulator (about 8 s with an empty ccache)
make run                                     # router_class_test on the golden router
make run PLUSARGS="+SHOW=5"                  # the same, logging the first 5 packets on each stream
make run BUG=B09 PLUSARGS="+DSTS=0 +LEN=1 +N=16"
make check-all                               # the golden router, then B05 and B09
make clean                                   # remove build/ (the ccache at the top of the clone stays)
```

## Targets

The targets come from [`../common/pyuvm.mk`](../common/README.md). The ones this lab uses:

| Target | What it does |
|---|---|
| `make build` | build the simulator if the RTL or a build setting changed; editing `tb/` never rebuilds |
| `make run` | run `router_class_test` once and print a verdict |
| `make waves` | the same run, writing `build/runs/<run>/waves.fst` |
| `make seeds` | the test on seeds 1 to 10 (`SEEDS="1 2 3 4 5"` for 1 to 5) |
| `make check` | the test must pass the golden router and fail on `BUG` (default `B05`) |
| `make check-all` | the same against B05 and B09 |
| `make clean` | remove `build/` |
| `make help` | every target and the current variables |

## Variables and plusargs

| Variable | Default | Meaning |
|---|---|---|
| `BUG` | empty | `B05` or `B09` (or any id in `../common/bugs.py`); empty runs the golden router |
| `SEED` | `1` | the seed cocotb gives Python's `random`; it changes every random choice the generator makes |
| `PLUSARGS` | empty | the test's knobs, below |

| Plusarg | Default | Meaning |
|---|---|---|
| `+N=<n>` | `100` | packets to send |
| `+DSTS=<digits>` | `0123` | the `DST` values the generator picks from, for example `+DSTS=0` |
| `+ROUTES=<abcd>` | `0110` | `ROUTE0` to `ROUTE3`, one character each: `0` or `1` is the output, `-` is disabled |
| `+LEN=<n>` | `0` | every packet `n` beats long (1 to 8); `0` picks each length from 1 to 8 |
| `+SHOW=<n>` | `0` | each monitor logs the first `n` packets it sees |

[`../common/README.md`](../common/README.md) lists the rest.

## Files

| File | What it is |
|---|---|
| `tb/packet.py` | `Packet`, the transaction, and `RouterCfg`, the knobs above |
| `tb/generator.py` | `Generator`: makes the packets |
| `tb/driver.py` | `Driver` (input stream), `Sink` (outputs, always ready) and `ApbMaster` (writes only) |
| `tb/monitor.py` | `Monitor`: turns a stream's handshakes into packets. You write `run()`. |
| `tb/scoreboard.py` | `Scoreboard`: predicts output 0 and checks it. You write `run()`, `predict()`, `check()` and the checks in `report()`. |
| `tb/env.py` | `Env`: builds the pieces, connects them with `cocotb.queue.Queue`s, and runs the test |
| `tb/test_router.py` | `router_class_test`: the clock, the reset, the `Env`, and the assert that fails the test when the testbench reported errors |
| `solutions/` | a reference monitor and scoreboard; see [`solutions/README.md`](solutions/README.md) |
| `Makefile` | the lab's settings and `include ../common/pyuvm.mk` |

The test is plain cocotb, with no pyuvm and no `BaseTest`, so the Makefile sets `BASE_TEST := 0`.
The simulator is built from the router's RTL alone (`build/rtl/router.f`, written by
`../common/inject.py` with every planted bug behind `+BUG`), so one build serves every run of this
lab.
