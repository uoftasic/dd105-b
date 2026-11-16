# DD105-B — Testbenches with UVM

Build a UVM testbench in Python, with pyuvm and cocotb on Verilator, for the same packet router as DD105-A.

Part of the UofT ASIC Team education materials (`uoftasic`).
Course site: <https://uoftasic.com/dd105-b/> · Education hub: <https://edu.uoftasic.com/>

DD105-B is the pyuvm version of [DD105-A](https://uoftasic.com/dd105-a/), and comes after
[DD104](https://uoftasic.com/dd104/). It has the same router, the same fifteen planted bugs, the
same seven labs in the same order, and the same capstone. The testbenches are Python: pyuvm 4.0.1
on cocotb 2.0.1, with pyvsc for constrained random and cocotb-coverage for functional coverage, on
Verilator 5.050. The only SystemVerilog a student writes is the assertions in Lab 05.

This repository is being built. The labs aren't in it yet.

## Copied from DD105-A

DD105-B carries its own copy of everything it shares with DD105-A. There is no module shared
between the two courses, so a change to one course's copy doesn't reach the other. Every file
below was copied from [uoftasic/dd105-a](https://github.com/uoftasic/dd105-a) at commit
`da489f273945e44c49069adee8dc45ac346bd42a` (Nov 16, 2026). The commit that copied them,
"Copy the shared files from DD105-A da489f2", has them byte for byte; the commits after it hold
every change DD105-B made.

| Here | From DD105-A | What it is |
|---|---|---|
| `labs/common/rtl/` | `labs/common/rtl/` | the router's RTL, the golden design |
| `labs/common/bugs.py`, `labs/common/inject.py` | the same paths | the bug catalogue (B01 to B15) and the script that builds the faulty router with the `+BUG` switch |
| `labs/common/smoke/` | `labs/common/smoke/` (all but `build/`) | the router's shipped test, `tb_smoke.sv`, and `tb_examples.sv`, which prints the specification's timing examples |
| `docs/reference/router-spec.md`, `docs/reference/the-router-in-one-page.md` | the same paths | the router's specification and its one-page summary |
| `docs/assets/img/router-block.svg`, `scripts/figures/router_block.py`, `scripts/figures/circuit_style.py`, `scripts/figures/requirements.txt` | the same paths | the router's block diagram and the script that draws it |
| `labs/lab-05-protocol-rules-and-backpressure/tb/router_sva.sv`, `tb/router_sva_bind.sv`, `solutions/router_sva.sv` | the same paths | Lab 05's assertions (the starter with its TODOs, and the solution) and the `bind` that puts them into the router |
| `labs/ref/tb/router_sva.sv`, `labs/ref/tb/router_sva_bind.sv` | the same paths | the reference environment's full set of assertions (valid/ready, APB and reset rules) and their `bind` |
| `labs/lab-01-one-alu-two-frameworks/rtl/alu.sv`, `labs/lab-01-one-alu-two-frameworks/bugs.json` | `labs/lab-01-one-alu-two-testbenches/rtl/alu.sv`, `bugs.json` | SimProc's ALU with DD104's three ALU bugs, A01 to A03, behind `+BUG` |

DD105-B doesn't use DD105-A's `third_party/uvm` (the SystemVerilog UVM library), so it isn't copied.
DD105-A's `docs/reference/register-layer.md` documents SystemVerilog UVM's register layer, whose
API pyuvm's doesn't follow, so it isn't copied either.

## License

[MIT](LICENSE). Copyright UofT ASIC Team / `uoftasic`.
