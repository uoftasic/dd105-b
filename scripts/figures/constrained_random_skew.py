"""Constrained random with pyvsc: how often each operation came out.

The counts are the two [SKEW] lines of a run of
guide-examples/constrained-random-with-pyvsc:

    make run TEST=CrSkewTest

1000 randomizations of AluVecFree, which has no constraint, and 1000 of
AluVec, whose c_shift keeps B below 4 when the operation is a shift.

    python3 scripts/figures/constrained_random_skew.py
"""
from uvm_figure_style import BLUE, GRID, INK, INK_2, MONO, ORANGE, canvas, save

OPS = ["ADD", "SUB", "OR", "NAND", "SHL", "SHR"]
FREE = [177, 166, 172, 159, 165, 161]
SHIFT = [392, 150, 168, 179, 50, 61]

fig, ax = canvas(7.6, 2.9, axis=True)
xs = range(len(OPS))
w = 0.38
ax.bar([x - w / 2 for x in xs], FREE, width=w, color=BLUE, label="no constraint")
ax.bar([x + w / 2 for x in xs], SHIFT, width=w, color=ORANGE, label="with c_shift")
for x, a, b in zip(xs, FREE, SHIFT):
    ax.text(x - w / 2, a + 8, str(a), ha="center", va="bottom", size=8, color=INK)
    ax.text(x + w / 2, b + 8, str(b), ha="center", va="bottom", size=8, color=INK)
ax.axhline(1000 / 6, color=INK_2, lw=0.9, ls=(0, (3, 2)), label="1000 / 6, an even spread")
ax.set_xticks(list(xs))
ax.set_xticklabels(OPS, family=MONO, size=9)
ax.set_ylabel("draws of 1000", size=9, color=INK)
ax.set_ylim(0, 440)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
ax.grid(axis="y", color=GRID, lw=0.7)
ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=8.5, loc="upper right")

save(fig, "constrained-random-skew")
