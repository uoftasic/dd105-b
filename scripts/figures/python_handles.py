"""Python classes and cocotb concurrency: names, objects and copies.

Left, guide-examples/python-classes-and-cocotb-concurrency handles_test: a and
b name one Packet; c is copy.copy(a), a new Packet whose data is a's list; d
is copy.deepcopy(a), with a list of its own. Right, reuse_test: a list of
three references to one reused Packet, and a list of three Packets. The
values are the ones the example printed. Adapted from DD105-A's handles.py.
"""
import schemdraw.elements as elm
import schemdraw.flow as flow

from circuit_style import drawing, save

TEXT_DROP = 0.11    # schemdraw puts the baseline on y; this centres the letters on it instead
NOTE = 11


def text(d, xy, s, halign="center", size=None):
    """Text at xy. right() stops it inheriting the last element's direction."""
    d.add(elm.Label().right().at((xy[0], xy[1] - TEXT_DROP)).label(s, halign=halign, fontsize=size))


def name(d, x, y, s):
    """A small square for a name, the name to its left. Returns the square."""
    text(d, (x - 0.45, y), s, halign="right")
    return d.add(flow.Box(w=0.6, h=0.6).anchor("center").at((x, y)))


def obj(d, x, y, label, w=2.4):
    """An object: a box with its label, centred on (x, y)."""
    return d.add(flow.Box(w=w, h=0.8).anchor("center").at((x, y)).label(label, fontsize=NOTE))


d = drawing()
d.config(margin=0.3)

# ── handles_test ─────────────────────────────────────────────────────────────
text(d, (3.6, 7.4), "handles_test", size=NOTE)
na = name(d, 0.9, 6.2, "a")
nb = name(d, 0.9, 5.0, "b")
nc = name(d, 0.9, 3.2, "c")
nd = name(d, 0.9, 1.0, "d")
p1 = obj(d, 3.6, 5.6, "Packet, id 0")
p2 = obj(d, 3.6, 3.2, "Packet, id 0")
p3 = obj(d, 3.6, 1.0, "Packet, id 0")
for n, p in ((na, p1), (nb, p1), (nc, p2), (nd, p3)):
    d.add(elm.Arrow().at(n.center).to(p.W))
l1 = obj(d, 8.4, 4.4, "[80 11 22 33]", w=3.0)
l2 = obj(d, 8.4, 1.0, "[80 11 22 33 44]", w=3.0)
d.add(elm.Arrow().at(p1.E).to(l1.W).label("data", loc="top", fontsize=NOTE))
d.add(elm.Arrow().at(p2.E).to(l1.W).label("data", loc="bottom", fontsize=NOTE))
d.add(elm.Arrow().at(p3.E).to(l2.W).label("data", loc="top", fontsize=NOTE))

# ── reuse_test ───────────────────────────────────────────────────────────────
X0 = 11.8
text(d, (X0 + 1.2, 7.4), "kept_once", size=NOTE)
text(d, (X0 + 7.0, 7.4), "kept_new", size=NOTE)
once = [name(d, X0 + 1.2, 6.0 - 1.6 * k, "[%d]" % k) for k in range(3)]
o3 = obj(d, X0 + 3.9, 4.4, "pkt 0: 02 a2")
for n in once:
    d.add(elm.Arrow().at(n.center).to(o3.W))
new = [name(d, X0 + 7.0, 6.0 - 1.6 * k, "[%d]" % k) for k in range(3)]
for k, n in enumerate(new):
    o = obj(d, X0 + 9.7, 6.0 - 1.6 * k, "pkt %d: %02x a%d" % (k + 1, k, k))
    d.add(elm.Arrow().at(n.center).to(o.W))

print(save(d, "dd105b-python-handles"))
