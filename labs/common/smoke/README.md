# `labs/common/smoke`: the router's shipped test

`tb_smoke.sv` is the test the router ships with. It reads `ID`, sets up `ROUTE0`, sends three short
packets and checks that they come out of output 0. It passes on the golden router and on every bug
in [`../bugs.py`](../bugs.py), which is the point of it. It is plain SystemVerilog: tasks in a
module, no classes and no UVM.

Run it in the course image:

| Command | What it does | Wall clock |
|---|---|---|
| `make` | builds and runs `tb_smoke.sv` on the golden RTL in `../rtl` | about 6 s |
| `make faulty` | the same on the faulty build from `../inject.py --all`, no bug switched on | about 6 s, or 2.4 s right after `make` |
| `make faulty BUG=B07` | the faulty build with bug B07 switched on at run time (no rebuild) | under 1 s once built |
| `make lint` | `verilator --lint-only -Wall` on the golden RTL | under 1 s |
| `make clean` | removes `build/` | |

`TB_SRC=` builds another plain testbench the same way (its top module must have the same name as its
file), and `BUILD=` moves the build folder. Each run leaves its waveform in `build/` as an `.fst`
file. Verilator's `--trace-fst` doesn't build in the course image, because its FST writer needs
`lz4.h` and the image has only the lz4 runtime library, so the makefile traces VCD and converts it
with `vcd2fst`.

| File | What it is |
|---|---|
| `tb_smoke.sv` | The shipped test |
| `tb_examples.sv` | Runs each timing example in the spec and prints it as a table: `make TB_SRC=tb_examples.sv` |
| `Makefile` | The targets above |
