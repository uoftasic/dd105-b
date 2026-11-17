"""Python classes and cocotb concurrency: Lab 02's environment as tasks and queues.

From labs/lab-02-a-layered-testbench-without-pyuvm/tb/env.py. Env.run() runs
the driver itself and awaits the generator's task; the sinks, the monitors
and the scoreboard are tasks started with cocotb.start_soon() that nothing
awaits. The labels on the arrows between pieces are the queues. Adapted from
DD105-A's lab02_threads.py.
"""
import schemdraw.elements as elm
import schemdraw.flow as flow

from circuit_style import drawing, save

TEXT_DROP = 0.11    # schemdraw puts the baseline on y; this centres the letters on it instead
NOTE = 11


def text(d, xy, s, halign="center", size=None):
    """Text at xy. right() stops it inheriting the last element's direction."""
    d.add(elm.Label().right().at((xy[0], xy[1] - TEXT_DROP)).label(s, halign=halign, fontsize=size))


def box(d, x, y, w, h, label, lw=1.3):
    """A box centred on (x, y)."""
    return d.add(flow.Box(w=w, h=h).anchor("center").at((x, y)).label(label).linewidth(lw))


d = drawing()
d.config(margin=0.3)

Y = 6.0          # the row the stimulus and the router sit on
AWAITED = 2.6    # line width for the two pieces Env.run() waits for

gen = box(d, 1.4, Y, 2.4, 0.9, "generator", lw=AWAITED)
drv = box(d, 5.9, Y, 2.0, 0.9, "driver", lw=AWAITED)
rtr = d.add(flow.Box(w=2.4, h=1.8).anchor("center").at((11.0, Y)).label("router\n(the design)", fontsize=NOTE).linestyle("--"))
snk1 = box(d, 16.0, Y + 0.45, 1.6, 0.7, "snk1")
snk0 = box(d, 16.0, Y - 0.45, 1.6, 0.7, "snk0")

d.add(elm.Arrow().at(gen.E).to(drv.W).label("gen2drv", loc="top", fontsize=NOTE))
d.add(elm.Arrow().at(drv.E).to((rtr.W[0], Y)).label("in", loc="top", fontsize=NOTE))
d.add(elm.Line().at((rtr.E[0], Y + 0.45)).to(snk1.W).label("out1", loc="top", fontsize=NOTE))
d.add(elm.Line().at((rtr.E[0], Y - 0.45)).to(snk0.W).label("out0", loc="top", fontsize=NOTE))

# The monitors watch the input and output 0 without driving them.
in_mon = box(d, 8.5, 3.4, 2.0, 0.9, "in_mon")
out_mon = box(d, 13.6, 3.4, 2.2, 0.9, "out0_mon")
d.add(elm.Dot().at((8.5, Y)))
d.add(elm.Arrow().at((8.5, Y)).to(in_mon.N))
d.add(elm.Dot().at((13.6, Y - 0.45)))
d.add(elm.Arrow().at((13.6, Y - 0.45)).to(out_mon.N))

sb = box(d, 11.05, 0.8, 6.0, 0.9, "scoreboard")
d.add(elm.Arrow().at(in_mon.S).to((8.5, sb.N[1])).label("in2sb", loc="bottom", fontsize=NOTE))
d.add(elm.Arrow().at(out_mon.S).to((13.6, sb.N[1])).label("out02sb", loc="top", fontsize=NOTE))

text(d, (0.2, 3.2), "thick: Env.run() waits for", halign="left", size=NOTE)
text(d, (0.2, 2.65), "the generator and the driver", halign="left", size=NOTE)
text(d, (0.2, 1.75), "thin: start_soon(), never awaited;", halign="left", size=NOTE)
text(d, (0.2, 1.2), "cancelled when the test ends", halign="left", size=NOTE)

print(save(d, "dd105b-lab02-tasks"))
