# Lab 03: Constraints and coverage

Writeup: [`docs/labs/lab-03-constraints-and-coverage-overview.md`](../../docs/labs/lab-03-constraints-and-coverage-overview.md)

This is the plain-cocotb testbench from Lab 02, with Lab 02's solution in `tb/monitor.py` and
`tb/scoreboard.py` and new pieces around it: packets that pyvsc randomizes, a sink that can stall,
an APB read, a tracker that follows output 0's level and predicts each packet's fate, and a check
that compares `DROP_CNT` with the tracker. You write the coverage with cocotb-coverage, constrain
the packet, and write the stimulus that reaches the two coverage holes where B07 and B08 are.

Run it in the course image, from this folder:

```bash
make venv                          # once: the course venv with pyvsc and cocotb-coverage
make build                         # the simulator (the same router build as Lab 02's)
make run                           # router_rand_test on the golden router
make cov                           # every coverage.xml under build/runs, merged
make traps                         # the constraint experiments in traps/traps.py
make check-all                     # router_rand_test on the golden router, B07 and B08
make clean                         # remove build/ (the ccache and the venv stay)
```

## Targets

This lab's own target:

| Target | What it does |
|---|---|
| `make traps` | runs `traps/traps.py` with the venv's Python, outside the simulator; prints one line per experiment and the time it took |

and the targets from [`../common/pyuvm.mk`](../common/README.md), the ones this lab uses:

| Target | What it does |
|---|---|
| `make venv` | make the course venv, once; `make run`, `waves`, `cov`, `seeds`, `check`, `check-all` and `traps` stop with a message until it exists |
| `make build` | build the simulator if the RTL or a build setting changed; editing `tb/` never rebuilds |
| `make run` | run `TEST` (default `router_rand_test`) once and print a verdict |
| `make waves` | the same run, writing `build/runs/<run>/waves.fst` |
| `make tests` | list the tests |
| `make cov` | merge every `coverage.xml` under `build/runs` with cocotb-coverage, and list each coverpoint and cross with the bins nothing hit; `build/coverage/merged.xml` has every bin's count |
| `make seeds` | `TEST` on seeds 1 to 10 (`SEEDS="1 2 3 4 5"` for others) |
| `make check` | the test must pass the golden router and fail on `BUG` (default `B07`) |
| `make check-all` | the same against B07 and B08 |
| `make clean` | remove `build/` |
| `make help` | every target and the current variables |

## Tests, variables and plusargs

| Test | What it does |
|---|---|
| `router_rand_test` | `CTRL.EN`, then four phases of 200 random packets, each with its own random routing table and a `DROP_CNT` check; then `close_holes()` and a last `DROP_CNT` check. `make check` grades this one. |
| `router_fill_test` | `close_holes()` on its own. Until you write `close_holes()` it sends nothing, and it fails on the golden router, because the scoreboard reports a test that checked no packet. |
| `router_class_test` | Lab 02's test: 100 random packets on the routing table `+ROUTES` gives, and a `DROP_CNT` check |

| Variable | Default | Meaning |
|---|---|---|
| `TEST` | `router_rand_test` | one of the tests above |
| `SEED` | `1` | the run's seed, for `make run` and `make traps` |
| `BUG` | empty | `B07` or `B08` (or any of `B01` to `B15`); empty runs the golden router |
| `PLUSARGS` | empty | the knobs below |

| Plusarg | Default | Meaning |
|---|---|---|
| `+N=<n>` | `200` in `router_rand_test` (per phase), `100` in `router_class_test` | packets to send |
| `+PHASES=<n>` | `4` | `router_rand_test`'s phases |
| `+ROUTES=<abcd>` | `0110` | `router_class_test`'s routing table: `0` or `1` is the output, `-` is disabled |
| `+SHOW=<n>` | `0` | each monitor logs the first `n` packets it sees |

Lab 02's `+DSTS` and `+LEN` are gone: the packet's constraints choose the DST and the length.

[`../common/README.md`](../common/README.md) lists the rest.

## Files

| File | What it is |
|---|---|
| `tb/packet.py` | `Packet` and `RouterCfg` from Lab 02, and `RandPacket`, whose DST and length kind come from pyvsc. Part 3 adds its constraints. |
| `tb/generator.py` | `Generator`: randomizes `RandPacket`s and gives each header its sequence number |
| `tb/driver.py` | Lab 02's `Driver`, `Sink` and `ApbMaster`, with a `stall` knob on the sink and `ApbMaster.read()` |
| `tb/monitor.py`, `tb/scoreboard.py` | Lab 02's solution, with the same code; your own Lab 02 files work here too |
| `tb/tracker.py` | `Tracker`: output 0's level, each packet's fate, and the drops `DROP_CNT` should count; `PktRecord`, what it hands to the coverage |
| `tb/coverage.py` | `sample_pkt()`, which the tracker calls once per packet, and `report()`, which writes `coverage.xml`. Part 2 adds the coverpoints. |
| `tb/env.py` | `Env`: builds the pieces and runs the steps a test calls, `check_drops()` among them |
| `tb/test_router.py` | the three tests. Part 4 adds `FillPlan` and `close_holes()`. |
| `traps/traps.py` | the constraint experiments behind `make traps` |
| `solutions/` | the reference solution; see [`solutions/README.md`](solutions/README.md) |
| `Makefile` | the lab's settings, `include ../common/pyuvm.mk`, and `make traps` |

The tests are plain cocotb, with no pyuvm and no `BaseTest`, so the Makefile sets
`BASE_TEST := 0`. The packets need pyvsc and the coverage needs cocotb-coverage, so it also sets
`NEEDS_VENV := 1`, and the simulator runs with the venv's Python. The simulator is built from the
router's RTL alone (`build/rtl/router.f`, written by `../common/inject.py` with every planted bug
behind `+BUG`), so one build serves every run of this lab.
