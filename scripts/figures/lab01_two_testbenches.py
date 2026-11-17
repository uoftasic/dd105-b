"""What a framework buys you: Lab 01's two testbenches side by side.

Left, the cocotb test: one Python file whose functions drive the ALU's pins
and check them. Right, the pyuvm testbench: the test, the environment, the
agent and the scoreboard, all Python classes, reaching the pins through
AluIf. Each runs in a simulator of its own that Verilator built from
rtl/alu.sv alone. Adapted from DD105-A's lab01_uvm_structure.py.
"""
import schemdraw.elements as elm
import schemdraw.flow as flow

from circuit_style import drawing, save

TEXT_DROP = 0.11    # schemdraw puts the baseline on y; this centres the letters on it instead
NOTE = 11


def text(d, xy, s, halign="center", size=None):
    """Text at xy. right() stops it inheriting the last element's direction."""
    d.add(elm.Label().right().at((xy[0], xy[1] - TEXT_DROP)).label(s, halign=halign, fontsize=size))


def box(d, x, y, w, h, label=None, size=None):
    """A box centred on (x, y)."""
    b = flow.Box(w=w, h=h).anchor("center").at((x, y))
    if label:
        b = b.label(label, fontsize=size)
    return d.add(b)


def frame(d, x0, y0, x1, y1, title, dashed=False):
    """A thin frame from (x0, y0) to (x1, y1) with its title in the top left corner."""
    f = flow.Box(w=x1 - x0, h=y1 - y0).anchor("SW").at((x0, y0)).linewidth(0.8)
    d.add(f.linestyle("--") if dashed else f)
    text(d, (x0 + 0.2, y1 - 0.35), title, halign="left", size=NOTE)


d = drawing()
d.config(margin=0.3)

# ── the cocotb test ──────────────────────────────────────────────────────────
frame(d, 0, 2.0, 5.4, 10.4, "cocotb/test_alu.py (Python)")
t = box(d, 2.6, 8.9, 3.9, 1.0, "t01, t02, t03")
a = box(d, 2.6, 6.9, 3.9, 1.0, "alu()")
s = box(d, 2.6, 4.9, 3.9, 1.0, "spec(), assert")
d.add(elm.Arrow().at(t.S).to(a.N))
d.add(elm.Arrow().at(a.S).to(s.N))
frame(d, 0, -1.4, 5.4, 1.2, "Verilator: build/cocotb", dashed=True)
dut1 = box(d, 2.6, -0.3, 2.6, 0.9, "ALU")
# alu() writes the pins and reads them back: an arrowhead at each end.
d.add(elm.Arrow().at((5.05, a.E[1])).to(a.E))
d.add(elm.Line().at((5.05, a.E[1])).to((5.05, -0.3)))
d.add(elm.Arrow().at((5.05, -0.3)).to(dut1.E))
text(d, (4.85, 1.6), "dut", halign="right", size=NOTE)

# ── the pyuvm testbench: classes ─────────────────────────────────────────────
X0 = 6.4
frame(d, X0, 2.0, X0 + 10.6, 10.4, "uvm_test_top: AluRandTest (Python classes)")
frame(d, X0 + 0.4, 3.5, X0 + 10.2, 8.8, "env (AluEnv)")
frame(d, X0 + 0.8, 3.8, X0 + 7.4, 8.0, "agt (AluAgent)")
seq = box(d, X0 + 4.0, 9.45, 2.0, 0.7, "seq", size=NOTE)
sqr = box(d, X0 + 4.0, 6.75, 2.0, 0.9, "sqr")
drv = box(d, X0 + 4.0, 4.7, 2.0, 0.9, "drv")
mon = box(d, X0 + 6.2, 4.7, 2.0, 0.9, "mon")
sb = box(d, X0 + 8.8, 4.7, 2.0, 0.9, "sb")
d.add(elm.Arrow().at(seq.S).to(sqr.N))
d.add(elm.Arrow().at(sqr.S).to(drv.N))
d.add(elm.Arrow().at(mon.E).to(sb.W).label("ap", loc="top", fontsize=NOTE))

# AluIf isn't a component: the test puts it in ConfigDB as "vif", and the
# driver and the monitor get it from there.
aif = box(d, X0 + 5.1, 2.7, 4.6, 0.8, "AluIf (from ConfigDB)", size=NOTE)
d.add(elm.Arrow().at(drv.S).to((drv.S[0], aif.N[1])))
d.add(elm.Arrow().at((mon.S[0], aif.N[1])).to(mon.S))

# ── the simulator ────────────────────────────────────────────────────────────
frame(d, X0, -1.4, X0 + 10.6, 1.2, "Verilator: build", dashed=True)
dut2 = box(d, X0 + 5.1, -0.3, 2.6, 0.9, "ALU")
d.add(elm.Arrow().at(dut2.N).to(aif.S))
d.add(elm.Arrow().at(aif.S).to(dut2.N))
text(d, (X0 + 5.3, 1.6), "dut", halign="left", size=NOTE)

print(save(d, "dd105b-lab01-two-testbenches"))
