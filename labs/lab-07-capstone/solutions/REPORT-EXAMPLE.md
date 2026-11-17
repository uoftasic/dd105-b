# Verification report: the packet router

An example of the report Part 8 asks for, written for the reference solution. Every number in it
comes from the runs in `solutions/README.md`. The hunt rows are three deals from those runs. The
first was dealt on the starter with `make new BUGPICK=B02`; the second was dealt with
`make new BUGPICK=B15`, once on the starter and once on the finished environment, which is what
keeping it sealed through Parts 5 and 6 would have given; the third was a random `make new` on the
finished environment.

Design: the packet router, `labs/common/rtl/`  
Specification: `docs/reference/router-spec.md`  
Plan: [`PLAN.md`](PLAN.md)  
Environment: `labs/lab-07-capstone/` with `solutions/tb/`

## 1. Summary

The router was verified against the 39 rows of `PLAN.md` with a pyuvm environment that checks it
three ways: a scoreboard, a predictor that compares register reads with the register model's
mirror, and assertions bound into the design. All 12 tests pass on seeds 1 to 10, 53 of the 60
coverage bins are hit and the other seven are ones the specification rules out, and the graded
test catches all 15 planted bugs on seeds 1 to 5. That meets every sign-off criterion in the plan.
The plan's open items are the larger part of this report, though: 10 of its rows have no checker
at all in this environment, and section 7 lists them.

## 2. The environment

| Component | What it does | File | Written in this lab? |
|---|---|---|---|
| Source agent | drives packets with idle cycles; abandons its packet at a reset (rule I3) | `tb/router_agents.py` | no |
| Output agents, one per output | a reactive sink: always ready, slow, random or stalled, set while the test runs | `tb/router_agents.py` | no |
| APB agent | drives one transfer at a time; keeps `psel` at 0 during a reset and starts an interrupted transfer again (rule A4); its monitor reports each completed transfer | `tb/router_agents.py` | no |
| Sys agent | drives the reset after time 0, warning the other drivers a cycle ahead; its monitor reports `rst_n` and `irq` every cycle | `tb/router_agents.py` | no |
| Register model | the ten registers on pyuvm's `uvm_reg` classes, with an adapter, a predictor on the APB monitor that checks reads of the non-volatile fields, and the reset and bit-bash sequences | `tb/router_ral.py` | no (Lab 06) |
| Scoreboard | predicts each packet's fate and checks every output beat in order; models `STATUS` and `INT_EN` cycle by cycle and checks `irq`, `STATUS` and `DROP_CNT` reads, `pslverr`, and bad reads; starts again from the reset values at a reset | `tb/router_env.py` | no |
| Coverage | packets by length, `DST`, fate and level; how long output beats wait; four corners the scoreboard counts | `tb/router_env.py` | no |
| Assertions | I1, I2, O1, O2, O6, and the rules about reset | `tb/router_sva.sv` | the reset rules: I7, O4, A4, the reset values |
| Sequences | Lab 05's and Lab 06's, `RouterResetVseq`, `RouterSaturateVseq`, and `RouterLab07Vseq`'s random phases | `tb/router_vseq.py` | `RouterResetVseq`, `RouterSaturateVseq`, the resets in the random phases |
| Tests | `RouterTest` is the graded one; one test per sequence, and Labs 02 to 04's tests | `tb/test_router.py` | no |

## 3. The plan's status

The plan has 39 rows. 22 are `done`. Six are done in part: RT4 (route writes are followed, `CTRL`
isn't), A7 and A8 (the value at each completion is checked, the other cycles aren't), RG1 (every
register but `LEVEL`), and RG2 and RG3 (the clears are checked, the same-cycle cases aren't).
Ten rows have no checker: I4, I5, I6, O3, O8, RT5, EN1, A1 to A3, A5 and A6, and RG4. OV2 has a
checker but no sign that it was ever made to happen. Each of these is an open item in the plan.
Of the rows that are done, I1, I2, I7, A4, A9, RG5, IRQ1 and RS1 have no coverage bin; for each,
the plan names the sequence that makes it happen instead.

## 4. Regression

`make regress` in `solutions/`: 12 tests on seeds 1 to 10, 9 min 30 s of wall clock.

```text
  120 ok  (120 runs)
```

The first build of `solutions/`, with an empty ccache, took 9.3 s; the lab folder's first build,
also with an empty one, took 9.1 s.

## 5. Coverage

```text
  top                                           88.33 %   53 of 60 bins
```

The seven bins never hit are `('full', 'empty')`, `('full', 'low')`, `('full', 'at_8')`,
`('out0', 'at_9')`, `('out0', 'high')`, `('out1', 'at_9')` and `('out1', 'high')` in
`router.pkt.x_fate_level`. The specification rules all seven out: a packet is FULL only at a
level of 9 or more, and written to an output only at 8 or less.

Before this lab's work, the same regression with 10 tests hit 49 of the 60. The four it missed
were the bins of `router.corner`: `noroute_saturated` and `full_saturated`, now hit by
`RouterSaturateVseq` (5 times each on seed 1), and `reset_with_beats` and `reset_mid_packet`, now
hit by `RouterResetVseq` (3 times and once in `RouterResetTest` on seed 1).

cocotb-coverage's percentage for a group is the share of its bins that were hit, crosses
included, so a bin the specification rules out stays in the count. This report names the bins
from the merged list `make cov` prints, not only the percentage.

## 6. Bugs

### Mystery hunts

| Deal | The first check that fired (copied) | Diagnosis | Verdict | Which sequence made it show |
|---|---|---|---|---|
| 1 | `irq is 1 from cycle 5906, but STATUS = 001 and INT_EN = 000 make it 0` | IRQ1: `irq` is raised by a `STATUS` bit whose enable is 0, so the mask is missing; `router_regs.sv` | B02_irq_ignores_int_en | `RouterLab06Vseq`, its `STATUS` step, which drops a packet while `INT_EN` is 0 |
| 2 | none on the starter, where `make hunt` printed `quiet` and `0 errors, 0 assertions`. On the finished environment: `router_sva.sv:83: Assertion failed in router.u_sva.u_out0.a_O4_rst: O4: out_valid is 1 during reset`, and the first logged error, three cycles later, `output 0: got 00 in cycle 13949, and no beat was expected` | quiet while the plan's rows RS2, RS3 and DR2 had no stimulus and I7, O4 and A4 no assertion; on the finished environment, a beat from before a reset still on the output during it and delivered after it: O4 and RS2, `router_fifo.sv` | B15_output_valid_survives_reset | `RouterResetVseq`, example E8 |
| 3 | `[RAL] ROUTE3 read 0x2 in cycle 3663; the mirror holds 0x1`, then the bit bash's own error, `writing a 1 to bit 0 of ROUTE3 (was 0x0) read back 0x2, not 0x1` | the register map's `ROUTE3`: a 1 written to `EN` reads back in `PORT`, so a read of `ROUTE3` swaps its two fields; `router_regs.sv` | B03_route3_readback_swapped | `RouterLab06Vseq`, the bit bash (`RegBitBashSeq`) |

### The catalogue

`make check-all` printed `15 of 15 caught.` on each of seeds 1 to 5, with the golden design `ok`.
Seed 1:

```text
      ok  the golden design                        0 errors, 0 assertions         13.7s
------------------------------------------------------------------------
  caught  tier 6  B15_output_valid_survives_reset  50 errors, 37 assertions       11.5s
  caught  tier 1  B01_status_write_clears_all      3 errors, 0 assertions         12.3s
  caught  tier 1  B02_irq_ignores_int_en           4 errors, 0 assertions         12.2s
  caught  tier 1  B03_route3_readback_swapped      5 errors, 0 assertions         12.1s
  caught  tier 1  B04_misaligned_address_accepted  50 errors, 0 assertions         2.6s
  caught  tier 2  B05_dst_field_off_by_one         50 errors, 0 assertions         3.0s
  caught  tier 2  B06_disabled_route_forwards      50 errors, 0 assertions         3.2s
  caught  tier 2  B07_full_counted_on_disabled_route 6 errors, 0 assertions         12.3s
  caught  tier 3  B08_admission_off_by_one         50 errors, 0 assertions         3.5s
  caught  tier 3  B09_write_pointer_power_of_two   50 errors, 1 assertion          3.0s
  caught  tier 4  B10_output_reloads_while_stalled 50 errors, 368 assertions       3.6s
  caught  tier 4  B11_cut_packet_has_no_last       50 errors, 45 assertions       11.9s
  caught  tier 5  B12_out1_uses_out0_ready         50 errors, 3 assertions         2.8s
  caught  tier 5  B13_admission_checks_other_output 50 errors, 0 assertions         3.1s
  caught  tier 6  B14_enable_resets_to_one         3 errors, 20 assertions        12.1s
------------------------------------------------------------------------
 15 of 15 caught.
```

## 7. What this doesn't show

- Ten rows have no checker (section 3). A router whose `in_ready` ignored `CTRL.EN` between
  packets, whose beats came out a cycle late, or whose `LEVEL` read wrong would pass every test
  here, unless the fault happened to change something a check does look at.
- The scoreboard checks a `DROP_CNT` read correctly only while no packet is coming in, so the
  tests read `DROP_CNT` only between bursts, and example E9, a clear in the cycle of a drop, is
  never tried.
- The simulator has two states, so nothing here says anything about X: an uninitialized register
  starts at 0 on Verilator, and the specification says not to rely on it.
- The regression ran seeds 1 to 10 and the catalogue seeds 1 to 5. B15 was caught on every one of
  those five, with as few as 27 errors (seed 2) and 25 assertion failures (seed 4), each time
  first by `a_O4_rst` in the directed E8 step, so a reset sequence without that step could miss
  it.
- Catching the 15 planted bugs shows the environment finds those 15. A bug unlike all of them, in
  a rule the plan has no checker for, would go unseen.
- The register model has no back door, because pyuvm 4.0.1 has none, so nothing here reads or
  sets a register except through APB.

## 8. Sign-off

This router follows its specification at its pins in every situation the plan's rows describe and
has a checker for, on seeds 1 to 10 of 12 tests; the rows without a checker are listed in the
plan's open items and in section 7. To check it:

```bash
cd labs/lab-07-capstone/solutions
make regress          # 120 ok  (120 runs), top  88.33 %   53 of 60 bins
make check-all        # 15 of 15 caught.  (and SEED=2 to SEED=5)
```
