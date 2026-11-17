# Lab 07: Capstone

Writeup: [`docs/labs/lab-07-capstone-overview.md`](../../docs/labs/lab-07-capstone-overview.md)

This package is our solution to Lab 06, with this lab's pieces added: a reset driver, a source
driver and an APB driver that know what to do when a reset interrupts them, a scoreboard that
follows a reset with traffic in flight, and four corners in the coverage. Four pieces of code are
left for you, marked `TODO (Part n)`: the assertions for the rules about reset, the sequence that
resets the router with traffic in flight, the resets in `RouterLab07Vseq`'s random phases, and the
sequence that takes both drop counters to 255. A `TODO` in the Makefile says when to add the two
sequences' tests to `TESTS`. You also write a verification plan and a verification report from the
two templates here, and keep all of it in a GitHub repository of your own. The router and its
planted bugs come from [`../common`](../common/README.md).

Run it in the course image, from this folder:

```bash
make build                                   # the simulator: the router with the assertions bound in
make run                                     # RouterTest on the golden router
make regress                                 # every test in TESTS on seeds 1 to 10, then the coverage
make new && make hunt && make verdict        # a mystery bug from all 15 in the catalogue
make run TEST=RouterResetTest                # your Part 5 sequence on its own
make check-all                               # RouterTest on the golden router and on all 15 bugs
make clean                                   # remove build/ (the ccache and the venv stay)
```

The assertions are SystemVerilog, so `make build` rebuilds the simulator after you edit
`tb/router_sva.sv`. The sequences are Python and `TESTS` is a list of names in the Makefile, so
editing either rebuilds nothing.

`BUG_LIST` has all 15 bugs, with B15 first, because `make check` grades the first bug in the
list. `make check-all` and the hunts use the whole list.

`RouterResetTest` and `RouterSaturateTest` run sequences whose bodies are empty until you write
them, so they fail on the golden router ("nothing was checked"). They aren't in `TESTS` until you
add them.

The packets need pyvsc and the coverage needs cocotb-coverage, so the Makefile sets
`NEEDS_VENV := 1`; Lab 03's Part 1 made the course venv, and `make venv` makes it if it's missing.

## Tests

| Test | What it does |
|---|---|
| `RouterTest` | `RouterLab06Vseq`, then `RouterInjectTest`'s steps, then `RouterLab05Vseq`, then `RouterLab07Vseq`; `make check`, `make check-all` and the hunts grade this one |
| `RouterLab07Test` | `RouterLab07Vseq` on its own: your two sequences (once you add them), then four random phases |
| `RouterResetTest` | `RouterResetVseq` on its own (Part 5) |
| `RouterSaturateTest` | `RouterSaturateVseq` on its own (Part 6) |
| `RouterLab06Test` | Lab 06's: `RouterLab06Vseq` on its own |
| `RouterLab05Test` | Lab 05's: `RouterLab05Vseq` on its own |
| `RouterSinkTest` | Lab 05's: `RouterRandTest` with both sinks in `SNK_RANDOM` |
| `RouterInjectTest` | Lab 04's: `RouterStallTest` with `NoroutePkt` swapped in by a factory override |
| `RouterStallTest` | Lab 04's: `RouterRandTest` with one output stalled in each phase |
| `RouterRandTest` | Lab 03's: `CTRL.EN`, four phases of 200 random packets with a `DROP_CNT` check each, then `close_holes()` and a last check |
| `RouterFillTest` | Lab 03's `close_holes()` on its own |
| `RouterClassTest` | Lab 02's: 100 random packets on the routing table `+ROUTES` gives |

The plusargs are Lab 04's: `+N`, `+PHASES`, `+ROUTES`, `+MAX_CYCLES` and `+OVERRIDE`;
`tb/test_router.py` lists them with their defaults. A test also ends once the scoreboard has
counted 50 errors.

## Targets

This lab's own targets, carried from Lab 06:

| Target | What it does |
|---|---|
| `make loc` | lines and code lines in the testbench's seven files; `FILES="..."` counts another testbench beside it |
| `make predict` | Lab 06's: what `predict()` does to the mirror of `STATUS`, `DROP_CNT`, `CTRL` and `ID` |

and the targets from [`../common/pyuvm.mk`](../common/README.md) that the writeup uses:

| Target | What it does |
|---|---|
| `make build` | build the simulator if the RTL, the assertions or a build setting changed |
| `make run` | run `TEST` (default `RouterTest`) once and print a verdict |
| `make waves` | the same run, writing `build/runs/<run>/waves.fst` |
| `make regress` | every test in `TESTS` on every seed in `SEEDS` (1 to 10), then the coverage of those runs merged |
| `make seeds` | `TEST` on every seed in `SEEDS` |
| `make cov` | merge the `coverage.xml` of every run in `build/runs` and list the bins |
| `make check` | the test must pass the golden router and fail on `BUG` (default `B15`) |
| `make check-all` | the same against all 15 bugs (`BUG_LIST`) |
| `make new` | deal a mystery bug from all 15, sealed in `.hunt` |
| `make hunt` | `RouterTest` against the mystery bug; `VERBOSE=1` prints the log |
| `make verdict` | the hunt's grade: pass on the golden router, fail on the mystery bug |
| `make reveal` | give up, and be told which bug it was |
| `make clean` | remove `build/` |
| `make help` | every target and the current variables |

## Files

| File | What it is | Edit it? |
|---|---|---|
| `PLAN-template.md` | the verification plan, with the specification's rules as rows | copy to `PLAN.md` (Part 2) |
| `REPORT-template.md` | the verification report | copy to `REPORT.md` (Part 4), fill in (Part 8) |
| `tb/router_sva.sv` | Lab 05's assertions, with the APB port and `irq` added and a counter for each rule about reset | Part 5: the reset rules |
| `tb/router_vseq.py` | `RouterBaseVseq` and its helpers, with `reset()`; Lab 05's and Lab 06's sequences; `RouterResetVseq`, `RouterSaturateVseq` and `RouterLab07Vseq` | Part 5: `RouterResetVseq.body()` and the random resets; Part 6: `RouterSaturateVseq.body()`; both: the lines in `RouterLab07Vseq` that run them |
| `Makefile` | the lab's settings, `include ../common/pyuvm.mk`, `make loc` and `make predict` | Parts 5 and 6: two tests in `TESTS` |
| `tb/router_env.py` | the scoreboard, with its reset handling and its four corners; the coverage; the environment | no |
| `tb/router_agents.py` | the packet, the input, output and APB agents with their sequences, and the sys agent, which has the reset driver | no |
| `tb/router_ral.py` | Lab 06's register model, adapter, predictor and register sequences | no |
| `tb/test_router.py` | Lab 02's to Lab 06's tests, `RouterTest`, and this lab's three | no |
| `tb/router_sva_bind.sv` | the `bind` that puts the assertions in the router | no |
| `src/loc.py`, `src/predict.py` | the scripts behind `make loc` and `make predict` | no |
| `solutions/` | the finished files, a filled-in plan and an example report; see [`solutions/README.md`](solutions/README.md) | |
