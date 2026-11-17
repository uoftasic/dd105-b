"""Virtual sequences: one sequence steering a source agent and a sink's knob from the environment.

    python3 scripts/figures/virtual_sequence_handles.py

writes docs/assets/img/virtual-sequence-handles.svg, the testbench of
guide-examples/virtual-sequences. pyuvm has no p_sequencer, so the virtual sequence is given the
environment when it is made and runs on no sequencer: it starts SrcSeq on env.src.sqr and writes
env.snk_cfg.ready_pct. The monitor checks every beat, whoever caused it.
"""
import schemdraw.elements as elm
import schemdraw.flow as flow

from circuit_style import drawing, save

NOTE = 11
TEXT_DROP = 0.11


def box(d, x, y, label, w=2.6, h=1.1):
    return d.add(flow.Box(w=w, h=h).anchor("center").at((x, y)).label(label, fontsize=12))


def text(d, xy, s, halign="center", size=NOTE):
    d.add(elm.Label().right().at((xy[0], xy[1] - TEXT_DROP)).label(s, halign=halign, fontsize=size))


d = drawing()
d.config(margin=0.3)

ROW = 1.7
vseq = box(d, 1.6, 0, "virtual sequence\nself.env", w=3.0, h=2.0)
src_sqr = box(d, 8.6, ROW, "env.src.sqr", w=2.4)
cfg = box(d, 8.6, -ROW, "env.snk_cfg\nready_pct", w=2.4)
src_drv = box(d, 13.6, ROW, "source\ndriver", w=2.0)
snk_drv = box(d, 13.6, -ROW, "sink\ndriver", w=2.0)
fifo = box(d, 18.4, 0, "FIFO", w=1.8, h=4.5)
mon = box(d, 18.4, -4.0, "monitor", w=2.2)

# The virtual sequence reaches both through the environment it was given.
d.add(elm.Line().at((vseq.E[0], 0.5)).to((4.0, 0.5)))
d.add(elm.Line().at((4.0, 0.5)).to((4.0, ROW)))
d.add(elm.Arrow().at((4.0, ROW)).to(src_sqr.W))
text(d, (4.25, ROW + 0.4), "starts SrcSeq on it", halign="left")
d.add(elm.Line().at((vseq.E[0], -0.5)).to((4.0, -0.5)))
d.add(elm.Line().at((4.0, -0.5)).to((4.0, -ROW)))
d.add(elm.Arrow().at((4.0, -ROW)).to(cfg.W))
text(d, (4.25, -ROW - 0.42), "writes the knob", halign="left")

d.add(elm.Arrow().at(src_sqr.E).to(src_drv.W).label("items", loc="top", fontsize=NOTE))
d.add(elm.Arrow().at(cfg.E).to(snk_drv.W).label("read each cycle", loc="bottom", fontsize=NOTE))
d.add(elm.Arrow().at(src_drv.E).to((fifo.W[0], ROW)).label("in_valid, in_data", loc="top", fontsize=NOTE))
d.add(elm.Arrow().at(snk_drv.E).to((fifo.W[0], -ROW)).label("out_ready", loc="bottom", fontsize=NOTE))
d.add(elm.Arrow().at(fifo.S).to(mon.N))
text(d, (fifo.S[0] + 0.2, -2.85), "every beat in and out", halign="left")

save(d, "virtual-sequence-handles")
