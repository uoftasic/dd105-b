"""Sequences, sequencers and drivers: the handshake for the first two items.

The times are from a run of guide-examples/sequences-sequencers-and-drivers:

    make run TEST=SqTimelineTest

Item 1: start_item and get_next_item returned at 0 ns, item_done and
finish_item at 10 ns. Item 2: start_item and get_next_item returned at 10 ns,
item_done and finish_item at 20 ns. The driver holds each vector on the pins
for one 10 ns period, with valid set (a Python flag, as in Lab 01's AluIf),
and drives the next one in the same time step as item_done().

    python3 scripts/figures/sequences_handshake.py
"""
from uvm_figure_style import BLUE, GRID, INK, INK_2, MONO, canvas, save

fig, ax = canvas(8.8, 3.3, xlim=(-17, 32), ylim=(-0.7, 4.15))

ROWS = {"sequence": 3.45, "driver": 2.05, "valid": 0.95}
for name, y in ROWS.items():
    ax.text(-1.5, y, name, ha="right", va="center", family=MONO, size=9, color=INK)

# period boundaries and the time axis
for t in (10, 20):
    ax.plot([t, t], [0.55, 3.9], color=GRID, lw=0.9, zorder=0)
ax.plot([0, 30], [0.3, 0.3], color=INK, lw=0.9)
for t in range(0, 31, 5):
    ax.plot([t, t], [0.3, 0.22], color=INK, lw=0.9)
    ax.text(t, 0.1, f"{t}", ha="center", va="top", size=8.5, color=INK)
ax.text(31, 0.1, "ns", ha="left", va="top", size=8.5, color=INK)
ax.text(15, -0.45, "grey lines: item_done() and the next get_next_item()", ha="center",
        va="center", size=8.5, color=INK_2)

H = 0.36


def bar(y, t0, t1, label, solid):
    if solid:
        ax.barh(y, t1 - t0, left=t0, height=H, color=BLUE, edgecolor="white", linewidth=1.5)
        ax.text((t0 + t1) / 2, y, label, ha="center", va="center", size=8, color="white")
    else:
        ax.barh(y, t1 - t0, left=t0, height=H, color="white", edgecolor=BLUE, hatch="////",
                linewidth=1.0)
        ax.text((t0 + t1) / 2, y + 0.3, label, ha="center", va="bottom", size=8, color=INK_2)


# the sequence: blocked in finish_item() until item_done()
bar(ROWS["sequence"], 0, 10, "finish_item() waits", False)
bar(ROWS["sequence"], 10, 20, "finish_item() waits", False)
# the driver: holds each vector on the pins for one period
bar(ROWS["driver"], 0, 10, "item 1", True)
bar(ROWS["driver"], 10, 20, "item 2", True)

# valid, high while a vector is on the pins
vy = ROWS["valid"]
xs = [0, 0, 20, 20, 30]
ys = [0, 1, 1, 0, 0]
ax.plot(xs, [vy - 0.18 + 0.36 * v for v in ys], color=INK, lw=1.3)

# the calls
for t, row, text, dy in ((0, "sequence", "start_item, randomize", 0.0),
                         (10, "sequence", "start_item, randomize", 0.0),
                         (0, "driver", "get_next_item", 0.0),
                         (10, "driver", "item_done, get_next_item", 0.0),
                         (20, "driver", "item_done", -0.32)):
    y = ROWS[row] - 0.3 + dy
    ax.plot([t], [ROWS[row]], marker="o", ms=4.5, color=INK, zorder=4)
    ax.text(t + 0.4, y, text, ha="left", va="top", size=7.5, color=INK)

save(fig, "sequences-handshake")
