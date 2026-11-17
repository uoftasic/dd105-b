"""Register models in pyuvm: the path of a model operation to the bus, and the predictor.

    python3 scripts/figures/register_model_paths.py

writes docs/assets/img/register-model-paths.svg, the testbench of
guide-examples/register-models-in-pyuvm. A write() or read() on the model goes through the map
and the adapter's reg2bus() to the bus agent's sequencer and driver, and bus2reg() turns the
finished item back into the operation's status and data. A raw sequence goes straight to the
sequencer. pyuvm's auto-predict is off and its uvm_reg_predictor class is empty, so the only
thing that moves the mirror is a predictor you write: a subscriber on the monitor that calls
predict() for every transfer, whoever started it.
"""
import schemdraw.elements as elm
import schemdraw.flow as flow

from circuit_style import drawing, save

NOTE = 11
H = 1.1
TEXT_DROP = 0.11


def box(d, x, y, label, w=2.4):
    return d.add(flow.Box(w=w, h=H).anchor("center").at((x, y)).label(label, fontsize=12))


def text(d, xy, s, halign="center", size=NOTE):
    d.add(elm.Label().right().at((xy[0], xy[1] - TEXT_DROP)).label(s, halign=halign, fontsize=size))


d = drawing()
d.config(margin=0.3)

# The model's operations, left to right, down to the design.
model = box(d, 1.2, 0, "register model\nthe mirror", w=2.9)
amap = box(d, 5.2, 0, "map", w=1.5)
adapter = box(d, 8.4, 0, "adapter\nreg2bus()\nbus2reg()", w=2.3)
sqr = box(d, 12.3, 0, "sequencer", w=2.2)
drv = box(d, 15.4, 0, "driver", w=1.8)
dut = box(d, 19.1, 0, "design", w=1.9)
d.add(elm.Arrow().at(model.E).to(amap.W).label("write()\nread()", loc="top", fontsize=NOTE))
d.add(elm.Arrow().at(amap.E).to(adapter.W))
d.add(elm.Arrow().at(adapter.E).to(sqr.W).label("bus item", loc="top", fontsize=NOTE))
d.add(elm.Arrow().at(sqr.E).to(drv.W))
d.add(elm.Arrow().at(drv.E).to(dut.W).label("bus", loc="top", fontsize=NOTE))

# A raw sequence goes around the model.
raw = box(d, 12.3, 2.4, "raw sequence", w=2.8)
d.add(elm.Arrow().at(raw.S).to(sqr.N))

# The monitor sees every transfer on the bus, whoever started it.
tap_x = (drv.E[0] + dut.W[0]) / 2
mon = box(d, tap_x, -2.6, "monitor", w=1.9)
d.add(elm.Dot().at((tap_x, 0)))
d.add(elm.Arrow().at((tap_x, 0)).to(mon.N))
pred = box(d, 8.4, -2.6, "your predictor", w=2.7)
d.add(elm.Arrow().at(mon.W).to(pred.E).label("every transfer", loc="bottom", fontsize=NOTE))
d.add(elm.Line().at(pred.W).to((model.S[0], -2.6)))
d.add(elm.Arrow().at((model.S[0], -2.6)).to(model.S))
text(d, (model.S[0] + 0.15, -1.6), "predict()", halign="left")

save(d, "register-model-paths")
