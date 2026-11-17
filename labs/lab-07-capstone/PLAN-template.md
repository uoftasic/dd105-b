# Verification plan: the packet router

<!--
  DD105-A Lab 07. Copy this file to PLAN.md and fill it in; Part 2 of the lab
  says how. Delete these comments when you're done.
-->

Author: _your name_  
Design: the packet router, `labs/common/rtl/` (top module `router`)  
Specification: `docs/reference/router-spec.md`  
Environment: `labs/lab-07-capstone/`  
Date: _date_

## Scope

_Two or three sentences: what this plan covers, and what it leaves out on purpose (for example
anything below the router's pins, timing, or behaviour the specification doesn't describe)._

## How the environment checks

_One line for each checker, in your own words: what it compares, against what, and when it
fires. There are three: the scoreboard, the register model's mirror, and the bound
assertions._

| Checker | What it compares | Where |
|---|---|---|
| | | |
| | | |
| | | |

## The rules

One row per rule. The `I`, `O` and `A` ids are the specification's own; the others are this
plan's labels for rules the specification states in prose.

- **Checked by**: the check that fires if the router breaks the rule: an assertion (`a_O2`),
  a scoreboard check (say which `write_` function), the register model's mirror, or
  "nothing".
- **Made to happen by**: the sequence, and the step in it, that makes the situation occur. A rule
  nothing ever exercises is checked by nobody, however good its checker is.
- **Seen in coverage**: the coverage bin that shows it happened (`cg_pkt`, `cg_wait` or
  `cg_corner`), or "no bin".
- **Status**: `done`, `open` (you mean to close it), or `gap` (you won't, and say why).

Three rows, O1, RT1 and A7, are filled in as examples.

### Input stream

| Id | The rule | Checked by | Made to happen by | Seen in coverage | Status |
|---|---|---|---|---|---|
| I1, I2 | (source) `in_valid` holds until the handshake; `in_data` and `in_last` hold while it waits | | | | |
| I3 | (source) after a reset the first beat offered is a header | | | | |
| I4 | `in_ready` doesn't depend on `in_valid`, `in_data` or `in_last` in the same cycle | | | | |
| I5 | between packets, `in_ready` equals `CTRL.EN` | | | | |
| I6 | from a packet's first handshake to its last, `in_ready` is 1 | | | | |
| I7 | `in_ready` is 0 while `rst_n` is 0 | | | | |

### Outputs

| Id | The rule | Checked by | Made to happen by | Seen in coverage | Status |
|---|---|---|---|---|---|
| O1 | `out_valid` holds until the handshake | `a_O1` on each output | every stalled or slow sink: `router_inject_test`'s phases, and `backpressure()` in `router_lab05_vseq` | `cg_wait.x_port_wait`: `long_wait` and `stalled` on both outputs | done |
| O2 | `out_data` and `out_last` hold while the beat waits | | | | |
| O3 | the outputs don't depend on `out_ready` or any other input in the same cycle | | | | |
| O4 | `out_valid` is 0 during reset, and stays 0 until a beat accepted after it arrives | | | | |
| O5 | beats come out in order, unchanged, never interleaved | | | | |
| O6 | every output packet is 1 to 8 beats and ends with its only `out_last` | | | | |
| O7 | each output depends only on its own `out_ready` | | | | |
| O8 | beat $k$ is on the pins from cycle $\max(t_k + 2, h_{k-1} + 1)$ until it's taken | | | | |

### Routing, drops and oversize packets

| Id | The rule | Checked by | Made to happen by | Seen in coverage | Status |
|---|---|---|---|---|---|
| RT1 | the decision table: `EN` = 0 is NOROUTE, a level of 9 to 16 is FULL, 0 to 8 is written to output `PORT` | the scoreboard: `write_in` decides each packet's fate at its header, and `write_out`, `write_apb` and `write_sys` check the beats, the `DROP_CNT` and `STATUS` reads and `irq` against it | `router_inject_test`'s phases: random routing tables, packets to disabled routes, one output stalled | `cg_pkt.x_fate_level`: every fate at every level the specification allows | done |
| RT2 | the threshold itself: admitted at exactly 8, dropped at exactly 9 | | | | |
| RT3 | a disabled route is NOROUTE whatever its `PORT`'s level, never FULL | | | | |
| RT4 | a `ROUTE` or `CTRL` write affects headers from the cycle after it completes | | | | |
| RT5 | a dropped packet is still taken: `in_ready` stays 1 for all its beats | | | | |
| DR1 | a drop adds one to its counter and sets its `STATUS` bit, visible from the next cycle | | | | |
| DR2 | each counter stops at 255 | | | | |
| OV1 | an oversize packet goes out cut to 8 beats, the 8th with `out_last`, and sets `STATUS.OVERSIZE` once | | | | |
| OV2 | an oversize packet that is also dropped counts as one drop and sets `OVERSIZE` too | | | | |
| EN1 | `CTRL.EN` stops and starts the input only between packets (E7), and doesn't affect the outputs | | | | |

### APB and registers

| Id | The rule | Checked by | Made to happen by | Seen in coverage | Status |
|---|---|---|---|---|---|
| A1, A2, A3 | (master) setup then access; address and data hold; `penable` is 0 after a transfer | | | | |
| A4 | (master) `psel` is 0 during reset; a transfer cut by reset has no effect | | | | |
| A5, A6 | a write's first access cycle has `pready` 1; a read's has `pready` 0, then 1; nowhere else is it 0 | | | | |
| A7 | `pslverr` is 1 exactly when a transfer to a bad address completes | the scoreboard: `write_apb` compares `pslverr` with the address at every completion; nothing looks at `pslverr` in the other cycles | `router_lab06_vseq`, Part 4: every bad address read and written | no bin | done for the completions; open for the other cycles |
| A8 | a read returns the value in its first access cycle; `prdata` changes only then | | | | |
| A9 | each write takes effect by its field's access type; a bad write changes nothing | | | | |
| RG1 | every register's reset value | | | | |
| RG2 | `STATUS` is write-1-to-clear per bit, and an event in the clearing cycle wins | | | | |
| RG3 | any write clears `DROP_CNT`; a drop in the same cycle is counted after the clear (E9) | | | | |
| RG4 | `LEVEL` reads both levels, and a beat accepted in the read's first access cycle isn't in it | | | | |
| RG5 | bits that aren't fields read 0 and ignore writes; `ID` and `LEVEL` ignore writes | | | | |
| IRQ1 | `irq` is the OR of `STATUS & INT_EN`, in the same cycle as the bit that changes it | | | | |

### Reset

| Id | The rule | Checked by | Made to happen by | Seen in coverage | Status |
|---|---|---|---|---|---|
| RS1 | the Reset table's values while `rst_n` is 0: `pready` 1, `pslverr` 0, `prdata` 0, `irq` 0 | | | | |
| RS2 | a reset with beats in a buffer loses them, a waiting beat included, and nothing from before it comes out (E8) | | | | |
| RS3 | a reset in the middle of an input packet discards it, and the next beat accepted is a header | | | | |

## Sign-off criteria

_The conditions under which you'll call this router verified. Make each one a command and the
output it has to print, so anyone can check it. For example:_

- _`make regress` prints `... ok (... runs)` with no other class, on seeds ..._
- _..._

## Open items

_Anything you found while filling this in that needs a decision, a new check or new stimulus:
one line each, with the row it belongs to._
