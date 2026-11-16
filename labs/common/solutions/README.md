# `labs/common/solutions`: the router's reference directed test

This is an answer key. `tb_directed.sv` catches all fifteen bugs in [`../bugs.py`](../bugs.py), and the
table below says which of its checks catches which bug. It is not part of any lab package.

| File | What it is |
|---|---|
| `tb_directed.sv` | The thorough directed test: a reference model written from the spec, the valid/ready and APB rule checkers, and 19 directed checks. No classes, no UVM. |
| `run_catalogue.py` | Checks the catalogue end to end and prints the table below. |
| `verilator_nba_repro.sv` | The Verilator nonblocking-assignment problem under "Verilator notes", in 13 lines of module code. |

## Running it

In the course image, from `labs/common/smoke`:

```bash
make TB_SRC=../solutions/tb_directed.sv                  # golden RTL
make TB_SRC=../solutions/tb_directed.sv faulty BUG=B07   # faulty build, bug B07
python3 ../solutions/run_catalogue.py                    # everything below, about 47 s
```

`run_catalogue.py` checks that every anchor matches, builds both testbenches on the golden RTL and
on the faulty build, then requires all of this:

- `tb_smoke.sv` passes on the golden RTL, on the faulty build with no bug, and with each of the 15 bugs.
- `tb_directed.sv` passes on the golden RTL and on the faulty build with no bug, and the two runs
  write identical traces of every router port on every cycle (6,852 cycles).
- `tb_directed.sv` fails at least one check with each of the 15 bugs.

## The checks

Every check starts with a reset. The model and the rule checkers run during all of them, so a check
can fail on something it wasn't aimed at. Every cycle, the model predicts `in_ready`, `irq`, `pready`,
`pslverr`, `prdata`, and each output's `out_valid`, `out_data` and `out_last` from the timing rule O8
in the spec, and compares them with the router.

| Check | What it drives |
|---|---|
| C01 `reset_values` | Every register and output after reset; a packet offered while `CTRL.EN` is 0 |
| C02 `reg_readback` | Every read-write field with values whose bits differ, reserved bits written as 1, writes to read-only registers |
| C03 `bad_address` | A read of all 256 byte addresses, a write to all 246 bad ones, then every register read back |
| C04 `routing` | Every DST under two routing tables, every length from 1 to 8; latency into an empty output |
| C05 `disabled_route` | 40 random packets with two routes disabled, then the table flipped |
| C06 `counters` | 300 NOROUTE drops and 300 FULL drops (both counters saturate at 255), cleared by writes |
| C07 `same_cycle` | A clearing write in the same cycle as a drop, for `DROP_CNT` and for `STATUS` |
| C08 `w1c` | All three `STATUS` bits set, then cleared one at a time |
| C09 `interrupt` | `irq` against every combination of `STATUS` and `INT_EN` that matters |
| C10 `admission` | An output filled to exactly 8 (admitted), to 16, and to 9 (the next packet dropped) |
| C11 `drop_reasons` | A disabled route that points at a full output |
| C12 `oversize` | Packets of 9, 10, 16 and 23 beats, and one for a disabled route |
| C13 `long_run` | 200 random packets, both outputs always ready |
| C14 `independent` | One output stalled while the other flows, then the other way round |
| C15 `random` | 400 random packets with random gaps, random stalls on both outputs, and register traffic |
| C16 `enable` | `CTRL.EN` cleared in the middle of a packet, then set again |
| C17 `config_midpacket` | The packet's route moved and then disabled while the packet is half sent |
| C18 `reset_midpacket` | Reset with beats waiting on both outputs and a packet half sent |
| C19 `apb_timing` | Cycles per write and per read; a read of `LEVEL` while the level changes |

## Which check catches which bug

From `run_catalogue.py` on the faulty build. "First failure" is the first message the directed test
prints with that bug switched on.

| Bug | Tier | Caught by | First failure |
|---|---|---|---|
| B01 | registers | C08, C15 | C08: `read of 0x08 returned 0x00000000, expected 0x00000005` |
| B02 | registers | C05, C06, C07, C08, C09, C10, C11, C12, C14, C15, C17 | C05: `irq is 1, expected 0 (STATUS 0x1, INT_EN 0x0)` |
| B03 | registers | C02 | C02: `read of 0x2c returned 0x00000002, expected 0x00000001` |
| B04 | registers | C03 | C03: `PSLVERR is 0 for a read to 0x01, expected 1` |
| B05 | routing | C04, C05, C06, C08, C10, C11, C12, C13, C14, C15, C16, C17, C18 | C04: `out0_valid is 0, expected 1` |
| B06 | routing | C05, C06, C07, C08, C09, C12, C17 | C05: `out1_valid is 1, expected 0` |
| B07 | routing | C11 | C11: `read of 0x10 returned 0x00000101, expected 0x00000001` |
| B08 | buffer corners | C06, C08, C10, C11, C14, C15 | C06: `out0_valid is 0, expected 1` |
| B09 | buffer corners | C04, C05, C10, C12, C13, C14, C15 | C04: `output 0 shows 0x22 last=1, expected 0x31 last=1` |
| B10 | protocol | C06, C08, C10, C11, C14, C15, C18 | C06: `output 0 shows 0x26 last=1, expected 0x07 last=1` |
| B11 | protocol | C08, C09, C12 | C08: `output 0 shows 0xc5 last=0, expected 0xc5 last=1` |
| B12 | backpressure | C10, C14, C15 | C10: `output 1 shows 0x62 last=0, expected 0x10 last=0` |
| B13 | backpressure | C06, C08, C10, C11, C14, C15 | C06: `read of 0x10 returned 0x00000000, expected 0x0000ff00` |
| B14 | reset | every check, C01 to C19 | before C01: `in_ready is high while rst_n is low` |
| B15 | reset | C18 | C18: `out0_valid is high while rst_n is low` |

Four bugs are caught by one check each, and each of those checks exists for that kind of bug:
`B03` by C02 (read-back), `B04` by C03 (the bad addresses), `B07` by C11 (both drop reasons at once)
and `B15` by C18 (reset with traffic in flight). `B14` fails every check because each check starts
with a reset, and the model expects `in_ready` low after it.

## Verilator notes

These came up while writing the testbenches, in the course image (Verilator 5.050):

- `--trace-fst` doesn't build: Verilator's FST writer includes `lz4.h`, and the image has only the
  lz4 runtime library (`liblz4.so.1`), no header. The makefile traces VCD with `--trace` and
  converts it with `vcd2fst`.
- Two nonblocking assignments to the same signal in the same time step, from two statements
  separated by a timing control, are committed in source order instead of the order they ran. A
  task `x <= 1; @(posedge clk); x <= 0;` called twice in a row leaves `x` low for the second call.
  `verilator_nba_repro.sv` gives `a high at 1 of 3 edges` on Verilator and `3 of 3` on Icarus 14.0. A
  clocking-block drive, a blocking assignment 1 ns after the edge, and dropping the trailing
  `x <= 0` all give 3 of 3. Both testbenches here drive with blocking assignments 1 ns after the edge.
