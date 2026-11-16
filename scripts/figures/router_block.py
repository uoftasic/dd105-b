"""The router in one page: the four blocks of labs/common/rtl/router.sv and the signals between them."""
import schemdraw.elements as elm
import schemdraw.flow as flow

from circuit_style import drawing, save

TEXT_DROP = 0.11    # schemdraw puts the baseline on y; this centres the letters on it instead
NOTE = 11           # font size for the signal names on the arrows
RIGHT = 11.8        # where the arrows that leave the router end


def text(d, xy, s, halign="center", size=None):
    """Text at xy. right() stops it inheriting the last element's direction."""
    d.add(elm.Label().right().at((xy[0], xy[1] - TEXT_DROP))
          .label(s, halign=halign, fontsize=size))


def block(d, x, y, w, h, name, note=None):
    """A box centred on (x, y), with its name in the middle, or its name over a note."""
    box = d.add(flow.Box(w=w, h=h).anchor("center").at((x, y)))
    if note is None:
        text(d, (x, y), name)
    else:
        text(d, (x, y + 0.2), name)
        text(d, (x, y - 0.24), note, size=NOTE)
    return box


d = drawing()
d.config(margin=0.3)     # a little white around the edge, so no text touches it

ing = block(d, 3.6, 4.0, 3.0, 2.0, "ingress", "route, drop, cut")
b0 = block(d, 8.6, 4.6, 2.6, 0.9, "buffer 0", "16 beats")
b1 = block(d, 8.6, 3.4, 2.6, 0.9, "buffer 1", "16 beats")
regs = block(d, 6.15, 0.6, 8.1, 1.0, "registers")
# A dashed outline round the two buffers, which the levels leave from.
bufs = d.add(flow.Box(w=3.2, h=2.5).anchor("center").at((8.6, 4.0)).linestyle("--"))

# The input stream comes in on the left; the output streams leave on the right.
d.add(elm.Arrow().at((0.5, 4.0)).to((ing.W[0], 4.0)))
text(d, (0.5, 4.4), "in_*", halign="left", size=NOTE)
d.add(elm.Arrow().at((ing.E[0], 4.6)).to((b0.W[0], 4.6)))
text(d, (6.0, 4.9), "push0", size=NOTE)
d.add(elm.Arrow().at((ing.E[0], 3.4)).to((b1.W[0], 3.4)))
text(d, (6.0, 3.7), "push1", size=NOTE)
d.add(elm.Arrow().at((b0.E[0], 4.6)).to((RIGHT, 4.6)))
text(d, (RIGHT + 0.1, 4.6), "out0_*", halign="left", size=NOTE)
d.add(elm.Arrow().at((b1.E[0], 3.4)).to((RIGHT, 3.4)))
text(d, (RIGHT + 0.1, 3.4), "out1_*", halign="left", size=NOTE)

# The APB port, both ways (writes in, read data out), and irq.
d.add(elm.Arrow(double=True).at((0.5, 0.6)).to((regs.W[0], 0.6)))
text(d, (0.5, 1.0), "APB", halign="left", size=NOTE)
d.add(elm.Arrow().at((regs.E[0], 0.6)).to((RIGHT, 0.6)))
text(d, (RIGHT + 0.1, 0.6), "irq", halign="left", size=NOTE)

# Between the registers and the ingress: the configuration up, the events down.
d.add(elm.Arrow().at((2.6, regs.N[1])).to((2.6, ing.S[1])))
text(d, (2.45, 2.25), "CTRL.EN,", halign="right", size=NOTE)
text(d, (2.45, 1.85), "ROUTE0-3", halign="right", size=NOTE)
d.add(elm.Arrow().at((3.6, ing.S[1])).to((3.6, regs.N[1])))
text(d, (3.75, 2.05), "drops, oversize", halign="left", size=NOTE)

# Both buffers' levels go to the registers (LEVEL) and back to the ingress,
# which admits a packet only while its output holds 8 beats or fewer.
d.add(elm.Arrow().at((8.6, bufs.S[1])).to((8.6, regs.N[1])))
text(d, (8.75, 1.85), "LEVEL0, LEVEL1", halign="left", size=NOTE)
d.add(elm.Line().at((8.6, 2.5)).to((5.0, 2.5)))
d.add(elm.Arrow().at((5.0, 2.5)).to((5.0, ing.S[1])))

print(save(d, "router-block"))
