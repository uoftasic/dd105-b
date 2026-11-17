# Lab 01: reference solution

Open this after `make check BUG=A03` passes on your own scoreboard.

| File | What it is |
|---|---|
| `alu_uvm.py` | `tb/alu_uvm.py` with the scoreboard extended to check `N` and `Z` |

Apart from its header comment, only `AluScoreboard` differs from the shipped file. Compare the two
with:

```bash
diff tb/alu_uvm.py solutions/alu_uvm.py
```

To run the solution, keep a copy of your own file outside `tb/` and put the solution in its place:

```bash
cp tb/alu_uvm.py my_alu_uvm.py
cp solutions/alu_uvm.py tb/alu_uvm.py
make check-all
cp my_alu_uvm.py tb/alu_uvm.py
```

Swapping the file rebuilds nothing, because the simulator is built from `rtl/alu.sv` alone and
the testbench is Python: `make build` printed `Vtop is up to date.` after the swap, in 0.07 s.

## The change to the scoreboard

`write()` compares the flags after the value, with its own counters, and starts each message
with `[FLAGS]`:

```python
if (t.N, t.Z) != (n, z):
    self.n_bad_flags += 1
    self.bad_flags[t.op] += 1
    self.logger.error(f"[FLAGS] {t}, expected N={n} Z={z}")
```

`build_phase` adds `n_bad_flags` and `bad_flags`, and `report_phase` adds the flag count to its
`[SB]` line. pyuvm has no report server and no message IDs, so the two counts on that line are
the only place the run counts value and flag mismatches apart; `BaseTest` counts every logged
error together.

A wrong value can bring wrong flags with it, and then the vector is logged twice, once as
`[VALUE]` and once as `[FLAGS]`. On seed 1 that happened to all 291 wrong `SUB` vectors under A01
and to 143 of the 278 wrong `NAND` vectors under A02. On A03 every value is right and only
`[FLAGS]` fires.

## Measured

All in the course image (`asic-edu/gui-rig:2026.08`, which is `hpretl/iic-osic-tools:2026.08`
with X11 layers added) with 2 CPUs and 3 GB, on Nov 16, 2026. "Errors" is the count `BaseTest`
prints, every `[VALUE]`, `[FLAGS]` and `[COUNT]` message the run logged.

### Every bug on seed 1

Lab 01's design is the ALU, and its catalogue (`bugs.json`) has three bugs. The router's B01 to
B15 aren't in this build; Lab 02 is the first lab on the router. `make check-all`, test
`AluRandTest`, seed 1:

| Bug | Starter | Solution |
|---|---|---|
| golden | ok, 0 errors | ok, 0 errors |
| A03 | MISSED, 0 errors | caught, 125 errors |
| A01 | caught, 291 errors | caught, 582 errors |
| A02 | caught, 278 errors | caught, 421 errors |
| total | `2 of 3 caught.` | `3 of 3 caught.` |

### The lab's own bugs on seeds 1 to 5

`make check-all SEED=<n>`. The starter missed A03 on all five seeds and the solution caught it on
all five, so A03 is the bug that meets the course's rule (missed by the starter, caught by the
solution, on seeds 1 to 5).

| Bug | | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Seed 5 |
|---|---|---|---|---|---|---|
| A03 | starter | MISSED | MISSED | MISSED | MISSED | MISSED |
| A03 | solution | 125 | 147 | 143 | 135 | 134 |
| A01 | starter | 291 | 277 | 304 | 299 | 298 |
| A01 | solution | 582 | 554 | 608 | 598 | 596 |
| A02 | starter | 278 | 280 | 293 | 292 | 311 |
| A02 | solution | 421 | 426 | 455 | 444 | 475 |

The solution's `[SB]` lines on seed 1:

```
[SB] 2000 vectors checked: 291 value mismatches (SUB 291), 291 flag mismatches (SUB 291)
[SB] 2000 vectors checked: 278 value mismatches (NAND 278), 143 flag mismatches (NAND 143)
[SB] 2000 vectors checked: 0 value mismatches, 125 flag mismatches (ADD 18, SUB 18, OR 6, NAND 2, SHL 65, SHR 16)
```

On every seed A01's flag count equals its value count, so its total is exactly double.

### The golden ALU on seeds 1 to 5

`make seeds SEEDS="1 2 3 4 5"` printed `5 ok  (5 runs)` for `AluRandTest` and for
`AluDirectedTest` (`TEST=AluDirectedTest`), with the starter and with the solution: 0 errors in
every run, 0.5 s a run for `AluRandTest` and 0.3 s for `AluDirectedTest`.

### `make check`

With no `BUG`, `make check` grades A03, the first bug in `BUG_LIST`. The starter:

```
      ok  the golden design                        0 errors                        0.5s
  MISSED  A03_zero_flag_low_nibble                 0 errors                        0.5s
------------------------------------------------------------------------
 VERDICT: FAIL -- your test passes A03_zero_flag_low_nibble too.
```

The solution:

```
      ok  the golden design                        0 errors                        0.5s
  caught  A03_zero_flag_low_nibble                 125 errors                      0.5s
        AluRandTest: AssertionError: 125 errors logged, the first: [FLAGS] SHR A=80 B=80 -> ALUout=80 N=1 Z=
------------------------------------------------------------------------
 VERDICT: PASS
```

### The order of random draws

Lab 01 is the first lab, so there is no earlier solution whose summary lines it has to repeat.
The check that applies is that the solution's flag check draws nothing from `random`, so the
starter and the solution send the same 2000 vectors. On seeds 1 to 5, under A01 and A02, the
starter's and the solution's `[VALUE]` lines are the same, line for line, with the same
timestamps (10 runs compared, 277 to 311 lines each), and their `[SB]` lines give the same value
counts.

### Times

| What | Time |
|---|---|
| the cocotb test's build, empty ccache | 7.3 to 7.6 s in six builds |
| `make cocotb` on the golden ALU, the run | 11.0 to 11.7 s in four runs (t02 alone 10.6 to 11.2 s) |
| `make cocotb`, all of it, from an empty ccache | 18.6 to 19.1 s in three runs |
| `make cocotb-all` | 44.3 to 44.8 s in three runs |
| `make build`, after `make cocotb` | 1.6 to 1.8 s in six builds, 6 of 7 compiled files from the ccache |
| `make build`, empty ccache | 7.3 s, twice |
| `make build` after a change to `tb/alu_uvm.py` | nothing to build (0.07 s) |
| `make run` (`AluRandTest`, 2000 vectors) | 0.54 s for the run, 0.65 s for the command |
| `make run TEST=AluDirectedTest` | 0.27 s for the run, 0.37 s for the command |
| `make check-all` | 2.0 s |

The cocotb test's counts on Verilator are DD104's: 65024 wrong values under A01, 65280 under A02,
and 25726 wrong flags under A03.

## Against the chain spec

The spec's rows for Lab 01 are predictions with DD105-A's counts beside them:

| | Spec | Measured here |
|---|---|---|
| Starter | catches A01, A02 (A: 282 and 255 `UVM_ERROR`s); misses A03 | catches A01, A02 (291 and 278 errors); misses A03 on seeds 1 to 5 |
| Solution | catches all three (A: 564, 394 and 131) | catches all three (582, 421 and 125 on seed 1) |
| Hard rule | A03 | A03 |

The catches are the spec's. The counts differ from A's because the vectors do: A's come from
Verilator's SystemVerilog `randomize()`, and these from Python's `random`, seeded by cocotb. The
counts relate to each other as A's do. A01's solution count is exactly double its starter count in both courses (282 to
564 in A, 291 to 582 here), A02's rises by about half (255 to 394 in A, 278 to 421 here), and
A03's share of flagged vectors is close to the exact fraction the sweep counts, 25726 of 393216
(6.5%): 131 of 2000 in A (6.6%) and 125 of 2000 here (6.25%).

Three details differ from the spec's description of the starter:

- The pyuvm testbench has one piece the spec doesn't list, `AluIf`, which stands in for A's
  `alu_if.sv` rather than for anything in `alu_pkg.sv`. The ALU has no clock, so the driver and
  the monitor share a 10 ns period and a Python `valid` flag through it.
- The spec names DD104's `labs/lab-03-three-blocks-before-the-processor/test_alu.py`, which is
  that lab's starter and checks values only. `cocotb/test_alu.py` is DD104's
  `solutions/test_alu.py`, the reference test, as DD105-A's copy is; it checks the flags too, which
  is where the 25726 comes from.
- `make cocotb` runs `t01` to `t03` in one run: `cocotb/Makefile` sets `TEST := .*`, which
  `pyuvm.mk` turns into a filter that matches every test, and names the run folder after the
  module (`build/cocotb/runs/test_alu-s1`). The verdict read that run's `results.xml`, with all
  three tests in it, as `ok: passed` on the golden ALU.

## Lab 02's files

Lab 01 carries nothing into Lab 02, which is the first lab on the router and starts from new files
(the chain spec, "Lab 02"): `tb/packet.py`, `tb/generator.py`, `tb/driver.py`, `tb/monitor.py`,
`tb/scoreboard.py`, `tb/env.py` and `tb/test_router.py`, plain cocotb, with a `Makefile` that sets
`BASE_TEST := 0` as `cocotb/Makefile` here does.
