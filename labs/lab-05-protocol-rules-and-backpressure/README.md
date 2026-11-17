# Lab 05: Protocol rules and backpressure

Writeup: [`docs/labs/lab-05-protocol-rules-and-backpressure-overview.md`](../../docs/labs/lab-05-protocol-rules-and-backpressure-overview.md)

This package is our solution to Lab 04, with this lab's pieces added: assertions bound into the
router, an output agent whose driver can answer each beat with an item from a sequence, virtual
sequences, and an oversize length kind in the packet, switched off until a sequence gives it a
weight. Three pieces are left for you, marked `TODO (Part n)`: three assertions, the sink driver's
answer to a beat, and the virtual sequence's body. The router and its planted bugs come from
[`../common`](../common/README.md).

Run it in the course image, from this folder:

```bash
make build                          # the simulator: the router with the assertions bound in
make run                            # RouterTest on the golden router
make run BUG=B10                    # the same run with planted bug B10 on
make run TEST=RouterLab05Test       # your Part 4 virtual sequence on its own
make check-all                      # pass on the golden router, fail on B11, B10 and B12
make clean                          # remove build/ (the ccache and the venv stay)
```

The assertions are SystemVerilog, so editing `tb/router_sva.sv` rebuilds the simulator; editing
the Python never does. Every run gets `+verilator+error+limit+100000`, so every failing assertion
prints and the run goes on. The simulator's own error limit is 1, which ends the run at the first
failing assertion; `make run BUG=B10 ERROR_LIMIT=1` shows that.

`RouterLab05Test` runs `RouterLab05Vseq` alone. Until you write that sequence's body it sends
nothing, so the test fails on the golden router ("no beat was checked"), and so does
`make regress`, which runs every test in `TESTS`.

The packets need pyvsc and the coverage needs cocotb-coverage, so the Makefile sets
`NEEDS_VENV := 1`; Lab 03's Part 1 made the course venv, and `make venv` makes it if it's missing.

## Tests

| Test | What it does |
|---|---|
| `RouterTest` | `RouterInjectTest`, then `RouterLab05Vseq` (Part 4); `make check` and `make check-all` grade this one |
| `RouterLab05Test` | `RouterLab05Vseq` on its own |
| `RouterSinkTest` | `RouterRandTest` with both sinks in `SNK_RANDOM`, each beat answered by an item (Part 3) |
| `RouterInjectTest` | Lab 04's: `RouterStallTest` with `NoroutePkt` swapped in by a factory override |
| `RouterStallTest` | Lab 04's: `RouterRandTest` with one output stalled in each phase |
| `RouterRandTest` | Lab 03's: `CTRL.EN`, four phases of 200 random packets with a `DROP_CNT` check each, then `close_holes()` and a last check |
| `RouterFillTest` | Lab 03's `close_holes()` on its own |
| `RouterClassTest` | Lab 02's: 100 random packets on the routing table `+ROUTES` gives |

The plusargs are Lab 04's: `+N`, `+PHASES`, `+ROUTES`, `+MAX_CYCLES` and `+OVERRIDE`;
`tb/test_router.py` lists them with their defaults. A test also ends once the scoreboard has
counted 50 errors.

## Targets

This lab's own target:

| Target | What it does |
|---|---|
| `make loc` | lines and code lines in the testbench's six files; `FILES="..."` counts another testbench beside it |

and the targets from [`../common/pyuvm.mk`](../common/README.md) that the writeup uses:

| Target | What it does |
|---|---|
| `make build` | build the simulator if the RTL, the assertions or a build setting changed |
| `make run` | run `TEST` (default `RouterTest`) once and print a verdict |
| `make waves` | the same run, writing `build/runs/<run>/waves.fst` |
| `make cov` | the coverage of every run in `build/runs`, merged; `rm -rf build/runs` first to see one run's |
| `make check` | the test must pass the golden router and fail on `BUG` (default `B11`) |
| `make check-all` | the same against B11, B10 and B12 (`BUG_LIST`) |
| `make seeds` | `TEST` on seeds 1 to 10 (`SEEDS="1 2 3 4 5"` for others) |
| `make regress` | every test on every seed in `SEEDS`, then the coverage of those runs merged |
| `make clean` | remove `build/` |
| `make help` | every target and the current variables |

## Files

| File | What it is | Edit it? |
|---|---|---|
| `tb/router_sva.sv` | the assertions for the valid/ready rules, each with a failure counter | Part 2: `a_O1`, `a_O2`, `a_O6` |
| `tb/router_sva_bind.sv` | the `bind` that puts `router_sva` into the router | no |
| `tb/router_agents.py` | the packet, and the input, output and APB agents with their sequences | Part 3: `SinkDriver` |
| `tb/router_env.py` | the scoreboard, the coverage (`router.pkt`, `router.wait`) and the environment | no |
| `tb/router_vseq.py` | `RouterBaseVseq`, the steps a virtual sequence uses, and `RouterLab05Vseq` | Part 4: `RouterLab05Vseq.body()` |
| `tb/test_router.py` | the base test, Lab 02's, Lab 03's and Lab 04's tests, and this lab's three | no |
| `src/loc.py` | the line counter behind `make loc` (Lab 01's) | no |
| `solutions/` | the three files with the TODOs filled in; see [`solutions/README.md`](solutions/README.md) | |
| `Makefile` | the lab's settings, `include ../common/pyuvm.mk`, and `make loc` | no |
