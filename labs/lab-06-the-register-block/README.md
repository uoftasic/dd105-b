# Lab 06: The register block

Writeup: [`docs/labs/lab-06-the-register-block-overview.md`](../../docs/labs/lab-06-the-register-block-overview.md)

This package is our solution to Lab 05, with this lab's pieces added: a register model of the
router's ten registers on pyuvm's `uvm_reg` classes, with its adapter, a predictor and two
register sequences; a monitor that reports `rst_n` and `irq` every cycle; and scoreboard checks on
`STATUS` reads, on `PSLVERR` and on reads of bad addresses. Eight pieces are left for you, marked
`TODO (Part n)`: the fields of `STATUS`, `DROP_CNT`, `LEVEL` and the `ROUTE` registers, the
adapter, the reset sequence, the predictor, the predictor's connections in the env, the bit-bash
sequence, the `irq` check, and this lab's virtual sequence. The router and its planted bugs come from
[`../common`](../common/README.md).

Run it in the course image, from this folder:

```bash
make build                          # the simulator: the router with Lab 05's assertions bound in
make regcheck                       # the register model on its own, outside the simulator
make run                            # RouterTest on the golden router
make run BUG=B14                    # the same run with planted bug B14 on
make run TEST=RouterLab06Test       # your virtual sequence on its own
make check-all                      # pass on the golden router, fail on B01, B02, B03, B04 and B14
make clean                          # remove build/ (the ccache and the venv stay)
```

Every file you edit in this lab is Python, so nothing you do rebuilds the simulator.
`tb/router_ral.py` imports nothing from the course venv, so `make regcheck` and `make predict`
run with the image's own Python. `make check` and `make check-all` build the model the same way
before any run, and stop with `make regcheck`'s message if it doesn't build: pyuvm reports a wrong
model with `AssertionError`, which a run would count as a check that fired.

`RouterLab06Test` runs `RouterLab06Vseq` alone. Until you write that sequence's steps it reads
nothing and sends nothing, so the test fails on the golden router ("nothing was checked"), and so
does `make regress`, which runs every test in `TESTS`.

The packets need pyvsc and the coverage needs cocotb-coverage, so the Makefile sets
`NEEDS_VENV := 1`; Lab 03's Part 1 made the course venv, and `make venv` makes it if it's missing.

## Tests

| Test | What it does |
|---|---|
| `RouterTest` | `RouterLab06Vseq` (Parts 2 to 5), then `RouterInjectTest`, then `RouterLab05Vseq`; `make check` and `make check-all` grade this one |
| `RouterLab06Test` | `RouterLab06Vseq` on its own: the first part of `RouterTest`, cycle for cycle |
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

This lab's own targets:

| Target | What it does |
|---|---|
| `make predict` | builds your register model and prints what `predict()` does to the mirror of `STATUS`, `DROP_CNT`, `CTRL` and `ID` (Part 3) |
| `make loc` | lines and code lines in the testbench's seven files; `FILES="..."` counts another testbench beside it |

and the targets from [`../common/pyuvm.mk`](../common/README.md) that the writeup uses:

| Target | What it does |
|---|---|
| `make build` | build the simulator if the RTL, the assertions or a build setting changed |
| `make regcheck` | build the register model (`REG_MODEL`) on its own and list its registers and fields |
| `make run` | run `TEST` (default `RouterTest`) once and print a verdict |
| `make waves` | the same run, writing `build/runs/<run>/waves.fst` |
| `make check` | the test must pass the golden router and fail on `BUG` (default `B01`) |
| `make check-all` | the same against B01, B02, B03, B04 and B14 (`BUG_LIST`) |
| `make seeds` | `TEST` on seeds 1 to 10 (`SEEDS="1 2 3 4 5"` for others) |
| `make regress` | every test on every seed in `SEEDS`, then the coverage of those runs merged |
| `make clean` | remove `build/` |
| `make help` | every target and the current variables |

## Files

| File | What it is | Edit it? |
|---|---|---|
| `tb/router_ral.py` | the register model, the adapter, the predictor, and the reset and bit-bash sequences | Part 2: the fields of `STATUS`, `DROP_CNT`, `LEVEL` and `ROUTEn`, the adapter, `RegResetSeq`; Part 3: the predictor's `write()`, `RegBitBashSeq` |
| `tb/router_env.py` | the scoreboard, with its model of `STATUS` and `INT_EN`; the coverage; the environment, which makes the register model, the adapter and the predictor | Part 3: the predictor's connections; Part 5: the `irq` check |
| `tb/router_vseq.py` | `RouterBaseVseq` with its raw and register-model helpers, `RouterLab05Vseq` and `RouterLab06Vseq` | Parts 2 to 5: `RouterLab06Vseq.body()` |
| `tb/router_agents.py` | the packet, the input, output and APB agents with their sequences, and the sys monitor | no |
| `tb/test_router.py` | the base test, Lab 02's to Lab 05's tests, `RouterTest` and `RouterLab06Test` | no |
| `tb/router_sva.sv`, `tb/router_sva_bind.sv` | Lab 05's assertions and the `bind` that puts them in the router | no |
| `src/predict.py` | the script behind `make predict` | no |
| `src/loc.py` | the line counter behind `make loc` (Lab 01's) | no |
| `solutions/` | the three files with the TODOs filled in; see [`solutions/README.md`](solutions/README.md) | |
| `Makefile` | the lab's settings, `include ../common/pyuvm.mk`, `make predict` and `make loc` | no |
