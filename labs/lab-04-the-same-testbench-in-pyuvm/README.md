# Lab 04: The same testbench in pyuvm

Writeup: [`docs/labs/lab-04-the-same-testbench-in-pyuvm-overview.md`](../../docs/labs/lab-04-the-same-testbench-in-pyuvm-overview.md)

This package is our solution to Lab 03, ported to pyuvm. It has an agent for the input stream, one
for the APB port, and one output agent class that the environment makes once for each output it
watches, with a scoreboard (Lab 03's scoreboard and tracker in one component) and Lab 03's
coverage as a subscriber, fed by analysis ports. The packet's constraints, the coverage,
`FillPlan` and `close_holes()` are Lab 03's. Four pieces are left for you, marked
`TODO (Part n)`: the second output agent, two parts of the scoreboard, the stall test, and
`NoroutePkt` with its factory override. The router and its planted bugs come from
[`../common`](../common/README.md).

Run it in the course image, from this folder:

```bash
make build                          # the simulator: the same router build as Labs 02 and 03
make run                            # RouterInjectTest on the golden router
make run TEST=RouterClassTest       # another test; nothing rebuilds
make check-all                      # pass on the golden router, fail on B06 and B13
make clean                          # remove build/ (the ccache and the venv stay)
```

The packets need pyvsc and the coverage needs cocotb-coverage, so the Makefile sets
`NEEDS_VENV := 1`, and every target that runs the simulator stops with a message until the course
venv is there. Lab 03's Part 1 made it; `make venv` makes it if it's missing.

## Tests

| Test | What it does |
|---|---|
| `RouterInjectTest` | `RouterStallTest` with `NoroutePkt` swapped in by a factory override; `make check` and `make check-all` grade this one (Part 4) |
| `RouterStallTest` | `RouterRandTest` with one output stalled in each phase (Part 3) |
| `RouterRandTest` | Lab 03's `router_rand_test`: `CTRL.EN`, then four phases of 200 random packets, each with its own random routing table and a `DROP_CNT` check; then `close_holes()` and a last `DROP_CNT` check |
| `RouterFillTest` | Lab 03's `close_holes()` on its own |
| `RouterClassTest` | Lab 02's test: 100 random packets on the routing table `+ROUTES` gives, and a `DROP_CNT` check |

Plusargs the tests read:

| Plusarg | Default | Meaning |
|---|---|---|
| `+N=<n>` | 200 (100 in `RouterClassTest`) | packets in each phase of `RouterRandTest` and the tests built on it, or in all of `RouterClassTest` |
| `+PHASES=<n>` | 4 | phases, each with its own routing table |
| `+ROUTES=<abcd>` | `0110` | `RouterClassTest`'s routing table: `0` or `1` is the output, `-` is disabled |
| `+MAX_CYCLES=<n>` | 200000 | a watchdog: a test still running after this many cycles ends with an error that starts `[WATCHDOG]` |
| `+OVERRIDE=<a>,<b>` | none | a factory override by name, set before the test builds anything: every `<a>` the factory makes is a `<b>` |

A test also ends once the scoreboard has counted 50 errors.

## Targets

This lab's own target:

| Target | What it does |
|---|---|
| `make loc` | lines and code lines in the testbench's three files; `FILES="..."` counts another testbench beside it |

and the targets from [`../common/pyuvm.mk`](../common/README.md) that the writeup uses:

| Target | What it does |
|---|---|
| `make build` | build the simulator if the RTL or a build setting changed; editing `tb/` never rebuilds |
| `make run` | run `TEST` (default `RouterInjectTest`) once and print a verdict |
| `make waves` | the same run, writing `build/runs/<run>/waves.fst` |
| `make tests` | list the tests |
| `make check` | the test must pass the golden router and fail on `BUG` (default `B06`) |
| `make check-all` | the same against B06 and B13 (`BUG_LIST`) |
| `make seeds` | `TEST` on seeds 1 to 10 (`SEEDS="1 2 3 4 5"` for others) |
| `make regress` | every test on every seed in `SEEDS`, then the coverage of those runs merged |
| `make cov` | the coverage of every run in `build/runs`, merged |
| `make clean` | remove `build/` |
| `make help` | every target and the current variables |

## Files

| File | What it is |
|---|---|
| `tb/router_agents.py` | the packet (`RouterPkt`, Lab 03's `RandPacket` with its constraints), the input, output and APB agents, and their sequences |
| `tb/router_env.py` | the scoreboard, the coverage and the environment; TODOs for Parts 2 and 3 |
| `tb/test_router.py` | Lab 03's `FillPlan`, the base test `RouterLabTest` with `close_holes()` and the other steps a test calls, and the tests; TODOs for Parts 3 and 4 |
| `src/loc.py` | the line counter behind `make loc` (Lab 01's) |
| `solutions/` | the two files with the TODOs filled in; see [`solutions/README.md`](solutions/README.md) |
| `Makefile` | the lab's settings, `include ../common/pyuvm.mk`, and `make loc` |
