# Lab 01: One ALU, two frameworks

Writeup: [`docs/labs/lab-01-one-alu-two-frameworks-overview.md`](../../docs/labs/lab-01-one-alu-two-frameworks-overview.md)

This package holds SimProc's ALU from DD104, with DD104's three ALU bugs behind a run-time switch,
and two testbenches for it, both on Verilator: the cocotb test from DD104 Lab 03 and a pyuvm
testbench.

Run it in the course image, from this folder:

```bash
make cocotb            # the cocotb test on the golden ALU (about 20 s the first time)
make build             # the pyuvm testbench's simulator (about 2 s after make cocotb)
make run               # AluRandTest on the golden ALU
make check BUG=A03     # pass on the golden ALU, fail on A03
make clean             # remove build/ (the ccache at the top of the clone stays)
```

## Targets

This lab's own targets:

| Target | What it does |
|---|---|
| `make cocotb` | the cocotb test on the golden ALU, or on `BUG`; prints the build and run times |
| `make cocotb-all` | the cocotb test on the golden ALU and on each of A01 to A03, summarized |
| `make loc` | lines and code lines in `cocotb/$(TB).py` and in `tb/alu_uvm.py` |

and the targets from [`../common/pyuvm.mk`](../common/README.md) that this lab uses:

| Target | What it does |
|---|---|
| `make build` | build the pyuvm testbench's simulator if the RTL or a build setting changed |
| `make run` | run `TEST` (default `AluRandTest`) once and print a verdict |
| `make waves` | the same run, writing `build/runs/<run>/waves.fst` |
| `make tests` | list the tests: `AluRandTest`, `AluDirectedTest` |
| `make seeds` | `TEST` on every seed in `SEEDS` |
| `make check` | the test must pass the golden ALU and fail on `BUG` (default `A03`, the first in `BUG_LIST`) |
| `make check-all` | the same against A03, A01 and A02 |
| `make clean` | remove `build/`, the cocotb test's build included |
| `make help` | every target and the current variables |

## Variables

| Variable | Default | Meaning |
|---|---|---|
| `BUG` | empty | `A01`, `A02` or `A03`; empty runs the golden ALU |
| `TB` | `test_alu` | the cocotb test module in `cocotb/`, for `make cocotb`, `make cocotb-all` and `make loc` |
| `TEST` | `AluRandTest` | the pyuvm test for `make run` and `make check` |
| `PLUSARGS` | empty | for example `+N=500`, the number of vectors `AluRandTest` sends (default 2000) |
| `SEED` | `1` | the seed cocotb gives Python's `random` |

[`../common/README.md`](../common/README.md) lists the rest.

## Files

| File | What it is |
|---|---|
| `rtl/alu.sv` | the ALU (`module ALU`, from DD104's `simproc_system.sv`) and the bug switch: `+BUG=A01`, `A02` or `A03` |
| `bugs.json` | the bug catalogue `make check` reads |
| `cocotb/test_alu.py` | DD104 Lab 03's reference cocotb test |
| `cocotb/Makefile` | runs the cocotb test with `../../common/pyuvm.mk` and `BASE_TEST := 0`; `make cocotb` calls it |
| `tb/alu_uvm.py` | the pyuvm testbench: the pins, item, sequences, driver, monitor, agent, scoreboard, environment, tests |
| `src/loc.py` | the line counter behind `make loc` |
| `solutions/` | a scoreboard that checks the flags; see [`solutions/README.md`](solutions/README.md) |
| `Makefile` | the lab's settings, `include ../common/pyuvm.mk`, and the cocotb targets |
