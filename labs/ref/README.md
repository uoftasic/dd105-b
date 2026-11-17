# `labs/ref`: the router's reference pyuvm environment

A complete pyuvm testbench for the packet router, the counterpart of DD105-A's `labs/ref` in
pyuvm 4.0.1 on cocotb 2.0.1 and Verilator 5.050. Its cycle model was written from the specification
([`docs/reference/router-spec.md`](../../docs/reference/router-spec.md)). Before writing it, its
author had read the router's package and top module (`router_pkg.sv`, `router.sv`) and the bug
catalogue, `labs/common/bugs.py`, whose anchors quote one line of RTL for each bug, but not
`router_regs.sv`, `router_ingress.sv` or `router_fifo.sv`. So the directed sequences were not
written blind. It builds with `labs/common/pyuvm.mk` like every DD105-B lab, and the graders in
`labs/common` run it. CI requires its `make check-all` to catch all 15 planted bugs and
`RouterAllTest` to pass the golden router on seeds 1 to 5.

It has:

- an APB agent (driver, monitor and sequencer) and a raw-transfer sequence for bad addresses;
- a source agent whose random packets are pyvsc `randobj`s;
- a reactive sink agent on each output, which takes one ready item per beat from a sequence that
  runs for the whole test, with random backpressure;
- a sys agent whose reset driver warns the other drivers one edge ahead, so the APB driver keeps
  `psel` at 0 in every reset cycle and starts an interrupted transfer again, and the source drops a
  packet a reset cut short;
- a register model on pyuvm's `uvm_reg` classes, an APB adapter, a predictor written for the course
  (pyuvm has none), and reset-value and bit-bash sequences, which pyuvm doesn't have either;
- a scoreboard whose reference model follows the specification cycle by cycle, routing table
  included;
- functional coverage with cocotb-coverage: DD105-A's packet, APB and backpressure covergroups;
- DD105-A's assertions for the valid/ready, APB and reset rules, bound into the router from a file of
  their own, each with a failure counter;
- DD105-A's virtual sequences, one test for each, and a test for each register sequence.

## Running it

From this folder, in the course image:

```bash
make venv                              # once: the course venv, which this folder needs
make                                   # build if needed, then run RouterAllTest
make run TEST=RouterRandTest SEED=7 PLUSARGS="+N=3000 +PHASES=8"
make regress                           # every test on seeds 1 to 10, then the coverage
make seeds NSEEDS=5                    # RouterAllTest on seeds 1 to 5
make check-all                         # RouterAllTest on the golden design and on each planted bug
make clean
```

The packets need pyvsc and the coverage needs cocotb-coverage, so the Makefile sets
`NEEDS_VENV := 1`, and every target that runs the simulator stops with a message until `make venv`
has made the venv. `labs/common/README.md` has the full list of targets and variables. The ones
this folder adds are plusargs read by the tests:

| Plusarg | Default | Meaning |
|---|---|---|
| `+N=<n>` | 1200 | packets sent by `RouterRandTest` (`RouterAllTest` sends 600) |
| `+PHASES=<n>` | 6 | phases of `RouterRandTest`, each with its own configuration and backpressure (`RouterAllTest` has 4) |
| `+MAX_CYCLES=<n>` | 400000 | a watchdog: a test still running after this many cycles ends with an error that starts `[WATCHDOG]` |

A test also ends once the scoreboard has counted 50 mismatches, so a scoreboard that has lost step
with the router doesn't print thousands of lines.

## Tests

Every test extends `RouterRefTest`, which extends the course's `RouterBaseTest` (`BaseTest` turns
logged errors and assertion failures into a failing test). `RouterRefTest` builds the environment,
starts a sink sequence on each output that runs for the whole test, and runs one virtual sequence
from `tb/router_seqs.py`, which each test names. Each virtual sequence starts with a reset.

| Test | Virtual sequence | What it does |
|---|---|---|
| `RouterAllTest` | `AllVseq` | every directed sequence below, one after another, then 600 random packets in 4 phases; `make check` and `make check-all` grade this one |
| `RouterSmokeTest` | `SmokeVseq` | one routing table, four directed packets and 40 random ones, every register read before and after |
| `RouterRandTest` | `RandVseq` | random routing tables, packets, idle cycles, backpressure, register traffic (bad addresses included) and resets, all at once |
| `RouterFullTest` | `FullVseq` | the admission threshold from both sides (E5, and two 8-beat packets), headers decided in the cycle the sink starts taking beats again, a disabled route whose `PORT` names a full output, output 1 running while output 0 is stalled |
| `RouterOversizeTest` | `OversizeVseq` | packets of 9 to 20 beats, cut to 8 (E6): forwarded, dropped as NOROUTE, dropped as FULL |
| `RouterCtrlTest` | `CtrlVseq` | `CTRL.EN` cleared in the middle of a packet (E7), and toggled while 1-beat packets go in back to back |
| `RouterSameCycleTest` | `SameCycleVseq` | a `DROP_CNT` write in the cycle of a drop (E9), a `STATUS` clear in the cycle of an event, a `ROUTE` write in the cycle of a header, `LEVEL` read while beats go in |
| `RouterSaturateTest` | `SaturateVseq` | both drop counters driven past 255, and cleared |
| `RouterRegsTest` | `RegsVseq` | the reset-value and bit-bash sequences, then every one of the 256 addresses read, every bad address written, patterns through the read-write registers and `ID` and `LEVEL`, back-to-back transfers |
| `RouterResetTest` | `ResetVseq` | the reset values read before anything is set up; reset with a beat waiting on a stalled output and a packet half accepted (E8), in the middle of APB transfers, with a packet half delivered, and in the middle of random traffic |
| `RouterIrqTest` | `IrqVseq` | each `STATUS` bit against all eight `INT_EN` settings, cleared one bit at a time |
| `RouterRegResetTest` | | `RegResetSeq` on its own, straight after a reset |
| `RouterBitBashTest` | | `RegBitBashSeq` on its own, straight after a reset |

`RouterResetTest` holds what Lab 07's capstone needs for B14 and B15: the reset values read before
`CTRL` is written, and a reset with beats waiting on a stalled output, after which nothing from
before the reset may come out.

## Checks

The virtual sequences check nothing themselves. Three checkers run in every test, and the two
register sequences check what they read wherever they run:

- The scoreboard (`RouterScoreboard` in `tb/router_env.py`) runs `router_model.RouterModel` on the
  cycle monitor's samples, one per cycle, every pin of the router read at the falling edge. It
  compares, in every cycle: `in_ready`, both `out_valid`s (and `out_data` and `out_last` while
  valid), `irq`, `pready`, `pslverr` and `prdata`. That covers the value of every register read
  (rule A8), every drop, the cycle each beat appears (O8), the cut of an oversize packet, and the
  values after a reset. The model is plain Python with no cocotb in it; `python3 tb/check_model.py`
  feeds it the inputs of the specification's nine timing examples and compares every output and
  register value in their tables, 77 cycles in all, and they all match.
- The predictor (`RouterRegPredictor` in `tb/router_ral.py`) compares every register read the APB
  monitor sees with the register model's mirror, outside the volatile fields (`STATUS`, `DROP_CNT`
  and `LEVEL`), reserved bits included, like SystemVerilog UVM's `set_check_on_read(1)`.
- The assertions in `tb/router_sva.sv` are DD105-A's reference set: I1, I2, I5, I6, I7, O1, O2, O4,
  O6, A1 to A8 and the reset values. Each counts its own failures, `n_fail` is their sum, and
  `BaseTest` reads it as `cocotb.top.u_sva.n_fail`.
- `RegResetSeq` compares every field with its reset value, volatile fields included, and
  `RegBitBashSeq` compares each bit it flips with the mirror.

A mismatch is logged with `self.logger.error()`, which `BaseTest` turns into a failing test. At
the 50th the scoreboard sets an event, `RouterRefTest` stops the virtual sequence and ends the
test, and `BaseTest` prints its counts and raises `AssertionError`.

## The register layer

pyuvm 4.0.1 has the register model, the map and the adapter, and nothing that keeps the mirror up to
date. `tb/router_ral.py` adds three pieces, which Lab 06 has students write:

| Piece | Stands in for | What it does |
|---|---|---|
| `RouterRegPredictor` | `uvm_reg_predictor` | subscribes to the APB monitor. A write: `predict(value, UVM_PREDICT_WRITE)`, so each field follows its policy. A read: the check above, then `predict(value, UVM_PREDICT_DIRECT)`. The first cycle of a reset: `map.reset("HARD")`. A transfer with `PSLVERR`, or to an address that isn't a register, is skipped. |
| `RegResetSeq` | `uvm_reg_hw_reset_seq` | puts the mirror at the reset values and reads every register; each field must read its reset value |
| `RegBitBashSeq` | `uvm_reg_bit_bash_seq` | for every bit of every register outside a volatile field, twice: write the register with that bit flipped from the mirror, read it back, compare with the mirror the predictor moved |

After a read the predictor uses `UVM_PREDICT_DIRECT`, because `UVM_PREDICT_READ` puts a W1C or WC
field at its reset value instead of the value read (lines 3 and 7 of the pyuvm probe under
[Library behaviour](#library-behaviour)).
pyuvm raises `UVMFatalError` for two operations on one register at once, where SystemVerilog UVM
makes the second wait, so the virtual sequences' `wr()` and `rd()` take a cocotb `Lock` per
register.

## Reset

The reset driver sets `ResetState.soon` right after rising edge x, pulls `rst_n` low right after
edge x+1, and clears `soon` when it lets `rst_n` go. The APB driver starts no transfer while `soon`
is set. A transfer already under way goes on until the edge at which `rst_n` falls, where the
driver drops `psel` (rule A4), and it is started again from its setup cycle after the reset. The
source driver drops the rest of a packet a reset interrupted (rule I3).

The APB driver first dropped `psel` as soon as it saw `soon`. That broke rule A1 whenever a
setup cycle fell in the last cycle before the reset, and on the golden router `RouterResetTest` on
seed 2 and `RouterAllTest` on seed 8 each failed with one assertion:

```
[1850000] %Error: router_sva.sv:195: Assertion failed in router.u_sva.a_A1: A1: a setup cycle was not followed by an access cycle
```

`ResetState.soon_time` lets the driver tell the edge at which `soon` was set from the next one.

## Coverage

`RouterCoverage` records DD105-A's covergroups apart from `cg_corner`, with A's bins:

| Group | Samples | Coverpoints and crosses | Bins |
|---|---|---|---|
| `router.pkt` | every packet, when its last beat is accepted (from the model) | `len` (1 to 8, oversize), `dst`, `act` (noroute, full, out0, out1), `level` of its output when the header was decided (empty, 1 to 7, 8, 9, 10 to 16); A's `x_dst_act` and `x_len_act`, and `x_act_level`, which A doesn't have, with the seven combinations the router can't produce as `ign_bins` | 87 |
| `router.apb` | every APB transfer (from the APB monitor) | `reg` (each register, a bad aligned address, a bad misaligned one), `dir`, `slverr`, `x_reg_dir` | 40 |
| `router.wait` | every output packet (from the sink monitors) | `port`, and `wait`, the longest any of its beats waited for `out_ready` (0, 1 to 3, 4 to 20, more), and their cross | 14 |

That is 141 bins. A's `cg_corner` (17 bins: a write in the cycle of an event, a counter saturating,
a reset mid-packet and so on) would need the scoreboard to spot each corner, and isn't here. Each
run writes `coverage.xml` into its run folder; `make cov` and `make regress` merge them with
cocotb-coverage's `merge_coverage()`.

## Results

All 13 tests pass on the golden design on seeds 1 to 10, 130 runs in 6 min 34 s of wall time
(`make regress`):

```
  130 ok  (130 runs)
```

and the merged coverage of those runs is every bin:

```
  top                                          100.00 %   141 of 141 bins
    top.router                                   100.00 %   141 of 141 bins
      top.router.pkt                               100.00 %   87 of 87 bins
        top.router.pkt.len                           100.00 %   9 of 9 bins
        top.router.pkt.dst                           100.00 %   4 of 4 bins
        top.router.pkt.act                           100.00 %   4 of 4 bins
        top.router.pkt.level                         100.00 %   5 of 5 bins
        top.router.pkt.x_dst_act                     100.00 %   16 of 16 bins
        top.router.pkt.x_len_act                     100.00 %   36 of 36 bins
        top.router.pkt.x_act_level                   100.00 %   13 of 13 bins
      top.router.apb                               100.00 %   40 of 40 bins
        top.router.apb.reg                           100.00 %   12 of 12 bins
        top.router.apb.dir                           100.00 %   2 of 2 bins
        top.router.apb.slverr                        100.00 %   2 of 2 bins
        top.router.apb.x_reg_dir                     100.00 %   24 of 24 bins
      top.router.wait                              100.00 %   14 of 14 bins
        top.router.wait.port                         100.00 %   2 of 2 bins
        top.router.wait.wait                         100.00 %   4 of 4 bins
        top.router.wait.x_port_wait                  100.00 %   8 of 8 bins
```

In that regression a run of `RouterAllTest` took 7.2 to 9.5 s (9.5 s was the first run of the
regression, seed 1), `RouterRandTest` 7.1 to 7.6 s, `RouterRegsTest` 3.2 to 3.3 s, and every other
test 1.9 to 2.6 s. On seed 1, `RouterAllTest` ran for 16,991 cycles and reached 139 of the 141 bins
on its own. The lines its components print at the end (timestamps and file names cut):

```
[uvm_test_top.env]: [ENV] 16 resets driven; 1 APB transfers started again after a reset; 2 packets abandoned at a reset or a wait limit
[uvm_test_top.env.sb]: [SB] 16991 cycles, 16 resets; 5249 input beats in 1713 packets: 480 full, 19 full oversize, 415 noroute, 4 noroute oversize, 423 out0, 42 out0 oversize, 295 out1, 35 out1 oversize; output beats 1576 and 1485
[uvm_test_top.env.sb]: [SB] 1200 register reads and 918 writes checked, 1001 transfers to bad addresses; irq 1 in 6307 cycles; 0 mismatches
[uvm_test_top.env.cov]: [COV] 139 of 141 bins (pkt 85 of 87, apb 40 of 40, wait 14 of 14); coverage.xml written
[uvm_test_top.env.predictor]: [RAL] 1200 register reads checked against the mirror, 918 writes predicted; 0 mismatches
DD105-B BaseTest: 0 errors logged, 0 assertion failures (u_sva.n_fail)
```

`make seeds NSEEDS=5`, which CI also runs, took 36.8 s:

```
========================================================================
 REGRESS   1 test x 5 seeds
========================================================================
      ok  RouterAllTest                seed 1      0 errors, 0 assertions          7.3s
      ok  RouterAllTest                seed 2      0 errors, 0 assertions          7.3s
      ok  RouterAllTest                seed 3      0 errors, 0 assertions          7.4s
      ok  RouterAllTest                seed 4      0 errors, 0 assertions          7.3s
      ok  RouterAllTest                seed 5      0 errors, 0 assertions          7.2s
------------------------------------------------------------------------
  5 ok  (5 runs)
```

`make check-all` on seed 1, 60.3 s in all:

```
      ok  the golden design                        0 errors, 0 assertions          8.6s
------------------------------------------------------------------------
  caught  tier 1  B01_status_write_clears_all      50 errors, 0 assertions         4.9s
  caught  tier 1  B02_irq_ignores_int_en           50 errors, 0 assertions         3.8s
  caught  tier 1  B03_route3_readback_swapped      56 errors, 0 assertions         3.4s
  caught  tier 1  B04_misaligned_address_accepted  50 errors, 32 assertions        3.0s
  caught  tier 2  B05_dst_field_off_by_one         50 errors, 0 assertions         2.0s
  caught  tier 2  B06_disabled_route_forwards      50 errors, 0 assertions         2.0s
  caught  tier 2  B07_full_counted_on_disabled_route 50 errors, 0 assertions         6.2s
  caught  tier 3  B08_admission_off_by_one         50 errors, 0 assertions         3.5s
  caught  tier 3  B09_write_pointer_power_of_two   50 errors, 1 assertion          2.0s
  caught  tier 4  B10_output_reloads_while_stalled 50 errors, 25 assertions        1.9s
  caught  tier 4  B11_cut_packet_has_no_last       50 errors, 25 assertions        4.7s
  caught  tier 5  B12_out1_uses_out0_ready         50 errors, 6 assertions         2.0s
  caught  tier 5  B13_admission_checks_other_output 50 errors, 0 assertions         2.1s
  caught  tier 6  B14_enable_resets_to_one         51 errors, 46 assertions        1.9s
  caught  tier 6  B15_output_valid_survives_reset  38 errors, 38 assertions        7.2s
------------------------------------------------------------------------
 15 of 15 caught.
```

Seeds 2 to 5 gave `15 of 15 caught.` as well, in 55.4, 55.7, 58.2 and 55.8 s, with the golden
design ok on each (7.4, 7.3, 7.3 and 7.2 s). The counts for every bug on seeds 1 to 5, as errors
logged and assertion failures:

| Bug | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Seed 5 |
|---|---|---|---|---|---|
| B01 | 50, 0 | 50, 0 | 50, 0 | 50, 0 | 50, 0 |
| B02 | 50, 0 | 50, 0 | 50, 0 | 50, 0 | 50, 0 |
| B03 | 56, 0 | 56, 0 | 56, 0 | 56, 0 | 56, 0 |
| B04 | 50, 32 | 50, 32 | 50, 32 | 50, 32 | 50, 32 |
| B05 | 50, 0 | 50, 0 | 50, 0 | 50, 0 | 50, 0 |
| B06 | 50, 0 | 50, 0 | 50, 0 | 50, 0 | 50, 0 |
| B07 | 50, 0 | 50, 0 | 50, 0 | 50, 0 | 50, 0 |
| B08 | 50, 0 | 50, 0 | 50, 0 | 50, 0 | 50, 0 |
| B09 | 50, 1 | 50, 0 | 50, 0 | 50, 0 | 50, 0 |
| B10 | 50, 25 | 50, 5 | 50, 17 | 50, 15 | 50, 22 |
| B11 | 50, 25 | 50, 33 | 50, 23 | 50, 24 | 50, 21 |
| B12 | 50, 6 | 50, 14 | 50, 4 | 50, 9 | 50, 9 |
| B13 | 50, 0 | 50, 1 | 50, 0 | 50, 0 | 50, 0 |
| B14 | 51, 46 | 51, 46 | 51, 46 | 51, 46 | 51, 44 |
| B15 | 38, 38 | 50, 50 | 27, 27 | 27, 27 | 22, 22 |

50 errors is a run the scoreboard stopped at its 50th mismatch. On seed 5 the extra errors came from
the predictor: B03's 56 are 50 from the scoreboard and 6 from the predictor, the first of them
`cycle 483: ROUTE3 read 0x2; the mirror holds 0x1`, and B14's 51 are 50 and 1. B14 is caught from
the first cycle of the first reset (`cycle 1: in_ready is 1, the model expects 0`), and B15 in
`ResetVseq`, from cycle 11374 on seed 5 (`out0_valid is 1, the model expects 0`).

Run against each test on its own (`bash probes/per_test.sh`, seed 1, 7 min 21 s), only
`RouterAllTest` catches every bug. Each line is the script's, and every golden run was ok:

```
RouterSmokeTest: golden ok; 9 of 15 caught.  not caught: B01 B02 B04 B07 B08 B15
RouterRandTest: golden ok; 14 of 15 caught.  not caught: B15
RouterFullTest: golden ok; 9 of 15 caught.  not caught: B01 B03 B04 B06 B11 B15
RouterOversizeTest: golden ok; 9 of 15 caught.  not caught: B01 B02 B03 B04 B07 B15
RouterCtrlTest: golden ok; 3 of 15 caught.  not caught: B01 B02 B03 B04 B06 B07 B08 B10 B11 B12 B13 B15
RouterSameCycleTest: golden ok; 8 of 15 caught.  not caught: B01 B03 B04 B07 B11 B12 B15
RouterSaturateTest: golden ok; 7 of 15 caught.  not caught: B01 B03 B04 B07 B09 B11 B12 B15
RouterRegsTest: golden ok; 3 of 15 caught.  not caught: B01 B02 B05 B06 B07 B08 B09 B10 B11 B12 B13 B15
RouterResetTest: golden ok; 9 of 15 caught.  not caught: B01 B02 B03 B04 B06 B07
RouterIrqTest: golden ok; 9 of 15 caught.  not caught: B03 B04 B05 B07 B12 B15
RouterRegResetTest: golden ok; 1 of 15 caught.  not caught: B01 B02 B03 B04 B05 B06 B07 B08 B09 B10 B11 B12 B13 B15
RouterBitBashTest: golden ok; 2 of 15 caught.  not caught: B01 B02 B04 B05 B06 B07 B08 B09 B10 B11 B12 B13 B15
```

`RouterResetTest` is the only test besides `RouterAllTest` that catches B15. The random test
resets in some phases, and on seed 1 none of its resets came while a beat waited on a stalled
output. Every test catches B14, because the scoreboard sees `in_ready` at 1 in the first cycle of
the first reset; that is all `RouterRegResetTest` catches, and `RouterBitBashTest` catches B03 as
well.

## Build and run times

Measured on ieee-asic-1 in the course image with 2 CPUs and 3 GB. The build compiles the RTL and
the assertions only, so the Python here doesn't change it: 8.0 s with an empty ccache (7 misses).
A run that needs no rebuild started and finished `RouterSmokeTest` through `make run` in 2.24 s of
wall time, twice, after a first run of 4.18 s. Importing pyvsc is 1.5 s of that: in the venv,
`python -c "import vsc"` took 1.525 s, `import cocotb_coverage.coverage` 0.035 s and
`import pyuvm` 0.195 s.

## Library behaviour

What the runs showed about the four libraries, where it differs from the course design
(`dd105b_design.md`, in the course research notes) or adds to it. `bash probes/run.sh`, from this folder after `make venv` and
`make build`, runs every probe quoted here; the output below is from one run of it.

### pyvsc 1.1.0

`probes/pyvsc_probe.py` draws from a class shaped like `RandPkt`:

```
1  a @vsc.randobj subclass of uvm_sequence_item builds: Pkt pkt
2  kind with dist 20/50/20/10, 1000 draws: [178, 519, 202, 101]
3  the weights are vsc.uint8_t attributes; set to 0/0/0/100, 200 draws: [0, 0, 0, 200]
4  dst.inside(rangelist(1, 3)) inline, 300 draws: {1: 163, 3: 137}
5  post_randomize() ran 1500 times in 1500 randomize() calls
6  seed 7 then build:                         [15, 50, 2, 26, 57, 32]
   seed 7, build, seed 99 before randomize(): [22, 32, 35, 37, 12, 1]
   seed 7, build, seed 12345 before it:       [34, 33, 29, 35, 46, 60]
   seed 7, build, randomize(), then seed 99:  [15, 50, 2, 26, 57, 32]
   seed 7, build, randomize(), then seed 123: [15, 50, 2, 26, 57, 32]
7  randomize() on one object: 475 per s; a new object and randomize(): 401 per s; a new object alone: 3026 per s
```

- **When the random state is taken** (differs from the design). The design says pyvsc draws an
  object's random state from Python's `random` when the object is built, and that reseeding
  `random` under an existing object changes nothing. Line 6 shows the state is taken at the
  object's first `randomize()`: reseeding between building the object and its first
  `randomize()` changes every value, and reseeding after it changes none. In pyvsc's source,
  `randobj_int.get_randstate()` calls `RandState.mk()`, which calls `random.randint()`, the first
  time it is asked. The design's advice still holds, since an object built and randomized inside
  the test repeats with the seed.
- **pyvsc constraints with cocotb-coverage coverage, on Verilator** (the design's open check). They
  ran together in every run above. The same-seed check: `RouterRandTest` on seed 7, run twice,
  printed the same two `[SB]` lines both times, and seed 8 printed different ones. The first line
  on seed 7 was
  `[SB] 8660 cycles, 3 resets; 5845 input beats in 1199 packets: 355 full, 25 full oversize, 312 noroute, 32 noroute oversize, 181 out0, 18 out0 oversize, 261 out1, 15 out1 oversize; output beats 933 and 1208`.
- A `@vsc.randobj` class can derive from `uvm_sequence_item` (line 1), `post_randomize()` runs after
  every `randomize()` (line 5), and `dist` weights held in non-random `vsc.uint8_t` attributes can
  be changed between calls (line 3), which is how `RandPktSeq` sets `w_over`.
- **Speed.** About 475 randomizations a second for this object, four random fields with a `dist` and
  an if/else, and about 400 with a new object each time (line 7). The design measured 133 a second
  with an 8-byte payload list and 1,092 for one field. At 400 a second the 1,200 packets of
  `RouterRandTest` cost about 3 s of its 7.1 to 7.6 s. So the payload bytes come from Python's
  `random` in `post_randomize()`, and the sinks' ready items aren't pyvsc objects at all: there is
  one per output beat. Importing pyvsc takes 1.5 s (above), in every run.

### cocotb-coverage 2.0

Nothing differed from the design. `ign_bins` on a cross take the bins' labels
(`x_act_level` has 13 of 13 bins once its seven combinations are ignored). A group counts the bins
of everything under it, as the design found: `RouterSmokeTest` on seed 1 printed
`[COV] 96 of 141 bins (pkt 54 of 87, apb 31 of 40, wait 11 of 14)`, and 96 and 141 are the three
groups' counts added up. `merge_coverage()` merged the 130 files of the regression above.

### pyuvm 4.0.1

`probes/pyuvm_probe.py` predicts on this folder's register model, outside the simulator:

```
1  STATUS mirror after predict(0x7, DIRECT):           0x7
2  then predict(0x1, WRITE), W1C clears bit 0:          0x6
3  then predict(0x6, READ) after reading 0x6:           0x0
4  then predict(0x6, DIRECT):                           0x6
5  CTRL (RW) after predict(0x1, READ):                  0x1
6  DROP_CNT (WC) at 0x302, then predict(0x0, WRITE):    0x0
7  then predict(0x302, READ):                           0x0
8  ID (RO) after predict(0x1234, WRITE):                0xd1050001
```

- `UVM_PREDICT_READ` puts a W1C field at its reset value (line 3), as the design found, and a WC
  field too (line 7); the design's reading of the source lists WC among the 14 other policies.
  RW and RO behave (lines 5 and 8). The predictor uses `UVM_PREDICT_DIRECT` after a read (line 4).
- These are additions; the design doesn't mention them. `create()` takes only a name and a parent,
  so a component that needs more (a sink's port number) gets it as an attribute set right after
  `create()`, before its `build_phase` runs. A driver has `get_next_item()` but no
  `try_next_item()`, so the reactive sink's sequence runs forever and always has the next item
  ready. A `uvm_sequence` has no logger, so the register sequences and the virtual sequences
  report through a component's (the predictor's and the environment's), which `BaseTest` counts.
- Two operations on one register at once raise `UVMFatalError`, as the design found. The virtual
  sequences wait on a lock per register instead.

### cocotb 2.0.1

`probes/probe_tasks.py` raises `NameError` in a task started with `cocotb.start_soon()` and then
waits for the task in four ways. The verdicts `make run` printed:

| Test | How it waits | Verdict |
|---|---|---|
| `TaskJoinedTest` | `await t` | `BROKEN: NameError` |
| `TaskCompleteTest` | `await First(t.complete, Timer(1, "us"))` | `ok: passed` |
| `TaskResultTest` | the same, then `t.result()` | `BROKEN: NameError` |
| `TaskUnwatchedTest` | never looks at the task again | `BROKEN: NameError` |

`TaskCompleteTest` logged `PROBE: First returned; t.done() is True` and
`PROBE: the test reached its end`. The design doesn't cover this: waiting on a task's `complete`
trigger counts as handling its exception, and the test passes. `RouterRefTest` waits that way, for
its virtual sequence, the watchdog and the scoreboard's stop event, so it calls `result()` on each
task that has finished. Before that line was there, `drain()` used an attribute the environment
didn't have, the `AttributeError` ended the virtual sequence after 440 cycles, and `make run`
printed `ok: 0 errors, 0 assertions` for `RouterSmokeTest`.

The design found that nothing in pyuvm or cocotb warned. `cocotb.triggers.Lock("CTRL")` does: an
earlier version of `router_seqs.py` named its locks, and every run printed
`DeprecationWarning: The 'name' argument will be removed in a future release.`

## Files

| File | What it is |
|---|---|
| `Makefile` | the lab's sources and tests; includes `../common/pyuvm.mk` |
| `tb/router_common.py` | what the agents share: `ResetState`, the drivers' sense of a rising edge, `Fwd` (one input of a component with several) and `plusarg()` |
| `tb/apb_agent.py` | `ApbItem`, the APB driver, monitor and agent, and `ApbRawSeq` |
| `tb/stream_agents.py` | the packets (`PktItem`, pyvsc's `RandPkt`, `make_packet()`), the source agent, the reactive sink agent with its monitor, and their sequences |
| `tb/router_ral.py` | the register model, the adapter, the predictor and the two register sequences (`REG_MODEL`, which the graders build first) |
| `tb/router_model.py` | the cycle-exact model of the router, plain Python |
| `tb/check_model.py` | the model against the specification's timing examples, with no simulator |
| `tb/router_env.py` | the sys agent with the reset driver, the cycle monitor, the scoreboard, the coverage and the environment |
| `tb/router_seqs.py` | the virtual sequences |
| `tb/test_router.py` | the tests |
| `tb/router_sva.sv` | the assertions, with a failure counter each (DD105-A's) |
| `tb/router_sva_bind.sv` | the `bind` that puts them into every `router` (DD105-A's) |
| `probes/` | the library probes quoted above, `run.sh` to run them, and `per_test.sh` |
