# `labs/ref`: the router's reference pyuvm environment

A complete pyuvm testbench for the packet router, written from the specification
([`docs/reference/router-spec.md`](../../docs/reference/router-spec.md)), without reading the
router's RTL. Its author had read the bug catalogue, `labs/common/bugs.py`, so the directed steps
were not written blind. It builds with `labs/common/pyuvm.mk` like every DD105-B lab, and the
graders in `labs/common` run it. CI requires its `make check-all` to catch all 15 planted bugs.

It has an APB agent, a source agent for the input stream, two sinks with random backpressure, a
cycle monitor that reads every pin at every falling edge, a scoreboard whose reference model
follows the specification cycle by cycle, a register model on pyuvm's `uvm_reg` classes with an
APB adapter, functional coverage with cocotb-coverage, and DD105-A's assertions for the
valid/ready, APB and reset rules, bound into the router from a file of their own.

## Running it

From this folder, in the course image:

```bash
make venv                              # once: the course venv (coverage needs it)
make                                   # build if needed, then run RouterAllTest
make run TEST=RouterRandTest SEED=7 PLUSARGS="+N=500 +PHASES=6"
make regress                           # every test on seeds 1 to 10, then the coverage
make check-all                         # RouterAllTest on the golden design and on each planted bug
make clean
```

Without the venv everything runs the same, with no coverage collected. `labs/common/README.md`
has the full list of targets and variables. The ones this folder adds are plusargs read by the
tests:

| Plusarg | Default | Meaning |
|---|---|---|
| `+N=<n>` | 250 | packets in each random phase |
| `+PHASES=<n>` | 4 | random phases, each with its own routing table, `INT_EN` and backpressure |

## Tests

Every test extends `RouterRefTest`, which extends the course's `RouterBaseTest`. Each step below
starts with a reset.

| Test | What it does |
|---|---|
| `RouterAllTest` | every directed step below, then the random phases; `make check` and `make check-all` grade this one |
| `RouterRandTest` | random routing tables (at least one route off and one on), packets of 1 to 12 beats with idle cycles, backpressure that changes every 10 to 80 cycles, and register traffic at the same time: reads, `STATUS` and `DROP_CNT` clears, `INT_EN`, `ROUTE` and `CTRL` writes, and transfers to random addresses; resets between some phases, some with beats waiting |
| `RouterSmokeTest` | one routing table, a packet to each DST, every register read before and after |
| `RouterRegsTest` | reset values, every read-write field written and read back, the first 64 addresses read (the misaligned ones too), bad writes, and writes to `ID` and `LEVEL` |
| `RouterFullTest` | the admission threshold from both sides on each output, with the other output empty or full, and a disabled route whose `PORT` names a full output |
| `RouterOversizeTest` | packets of 9 to 12 beats, forwarded on both outputs and dropped as NOROUTE and as FULL (E6) |
| `RouterIrqTest` | each `STATUS` bit against all eight `INT_EN` settings, cleared one bit at a time |
| `RouterCtrlTest` | `CTRL.EN` cleared in the middle of a packet (E7) |
| `RouterResetTest` | reset with beats waiting on both stalled outputs (E8) |
| `RouterSaturateTest` | both drop counters past 255, and cleared |

## Checks

None of the steps checks anything itself. The scoreboard runs `router_model.RouterModel` on the
cycle monitor's samples and compares, in every cycle: `in_ready`, both `out_valid`s (and `out_data`
and `out_last` while valid), `irq`, `pready`, `pslverr` and `prdata`. That covers the value of every
register read (rule A8), every drop, the cycle each beat appears (O8), the cut of an oversize packet,
and the values after a reset. The model is plain Python with no cocotb in it; `python3 tb/check_model.py` feeds it the
inputs of the specification's nine timing examples and compares every output and register value in
their tables, and it gives all of them, 77 cycles in all. A mismatch is logged with `self.logger.error()`, which `BaseTest` turns into a
failing test. After 50 mismatches the scoreboard stops the test with an `AssertionError`, raised
inside the cycle monitor's task; cocotb 2.0.1 then ends the test with that exception, and
`results.xml` records it as `AssertionError`.

The assertions in `tb/router_sva.sv` are DD105-A's reference set: I1, I2, I5, I6, I7, O1, O2, O4,
O6, A1 to A8 and the reset values. Each counts its own failures, `n_fail` is their sum, and
`BaseTest` reads it as `cocotb.top.u_sva.n_fail`.

The coverage (`RouterCoverage`) records each packet's length, `DST`, fate and the level of its
output when its header was decided, and the cross of fate and level, with the seven combinations
the router can't produce (a FULL drop at a level of 8 or less, a forwarded packet at 9 or more) as
ignore bins.

## Results

All 10 tests pass on the golden design on seeds 1 to 10, 100 runs in 70.7 s:

```
  100 ok  (100 runs)
```

and the merged coverage of those runs:

```
  top                                          100.00 %   35 of 35 bins
    top.router                                   100.00 %   35 of 35 bins
      top.router.pkt                               100.00 %   35 of 35 bins
        top.router.pkt.len                           100.00 %   9 of 9 bins
        top.router.pkt.dst                           100.00 %   4 of 4 bins
        top.router.pkt.fate                          100.00 %   4 of 4 bins
        top.router.pkt.level                         100.00 %   5 of 5 bins
        top.router.pkt.fate_x_level                  100.00 %   13 of 13 bins
```

`RouterAllTest` took 1.9 to 2.7 s per run over those ten seeds. On seed 4 its scoreboard reported:

```
[SB] 12003 cycles, 15 resets; 6087 input beats in 1614 packets: 304 full, 11 full oversize, 674 noroute, 70 noroute oversize, 249 out0, 49 out0 oversize, 215 out1, 42 out1 oversize; output beats 1350 and 1189
[SB] 1314 register reads and 1656 writes checked, 439 transfers to bad addresses; irq 1 in 5297 cycles; 0 mismatches
```

`make check-all` on seed 1 (12.6 s in all):

```
      ok  the golden design                        0 errors, 0 assertions          2.0s
------------------------------------------------------------------------
  caught  tier 1  B01_status_write_clears_all      AssertionError                  0.5s
  caught  tier 1  B02_irq_ignores_int_en           AssertionError                  0.5s
  caught  tier 1  B03_route3_readback_swapped      AssertionError                  0.7s
  caught  tier 1  B04_misaligned_address_accepted  AssertionError, 24 assertions    0.4s
  caught  tier 2  B05_dst_field_off_by_one         AssertionError                  0.5s
  caught  tier 2  B06_disabled_route_forwards      AssertionError                  0.6s
  caught  tier 2  B07_full_counted_on_disabled_route AssertionError                  1.0s
  caught  tier 3  B08_admission_off_by_one         AssertionError                  0.5s
  caught  tier 3  B09_write_pointer_power_of_two   AssertionError, 2 assertions    0.5s
  caught  tier 4  B10_output_reloads_while_stalled AssertionError, 11 assertions    0.5s
  caught  tier 4  B11_cut_packet_has_no_last       AssertionError, 26 assertions    1.2s
  caught  tier 5  B12_out1_uses_out0_ready         AssertionError, 1 assertion     0.5s
  caught  tier 5  B13_admission_checks_other_output AssertionError                  0.5s
  caught  tier 6  B14_enable_resets_to_one         AssertionError, 46 assertions    0.4s
  caught  tier 6  B15_output_valid_survives_reset  35 errors, 35 assertions        2.0s
------------------------------------------------------------------------
 15 of 15 caught.
```

A row that says only `AssertionError` is a run the scoreboard stopped at its 50th mismatch, before
`BaseTest` printed its counts. Seeds 2, 3 and 4 gave `15 of 15 caught.` as well, in 12.3 to 13.2 s.

## Build and run times

Measured on ieee-asic-1 in the course image with 2 CPUs and 3 GB. The build, with an empty ccache,
took 8.0 to 8.2 s in three builds, and 0.7 s after a file was touched with the ccache warm. A run
that needs no rebuild started and finished `RouterSmokeTest` in 0.46 s of wall time through
`make run`.

## Files

| File | What it is |
|---|---|
| `Makefile` | the lab's sources and tests; includes `../common/pyuvm.mk` |
| `tb/router_model.py` | the cycle-exact model of the router, plain Python |
| `tb/check_model.py` | the model against the specification's timing examples, with no simulator |
| `tb/router_agents.py` | the transactions, the APB and source agents, the sinks, the cycle monitor and the raw sequences |
| `tb/router_ral.py` | the register model and the APB adapter (`REG_MODEL`, which the graders build first) |
| `tb/router_env.py` | the scoreboard, the coverage and the environment |
| `tb/test_router.py` | the tests and their steps |
| `tb/router_sva.sv` | the assertions, with a failure counter each (DD105-A's) |
| `tb/router_sva_bind.sv` | the `bind` that puts them into every `router` (DD105-A's) |
