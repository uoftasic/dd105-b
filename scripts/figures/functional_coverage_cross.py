"""Functional coverage you can read: the cross alu.x_op_eq after two runs.

The counts are from guide-examples/functional-coverage-you-can-read, the two
"[COV] x_op_eq" lines that each of these runs prints:

    make run TEST=CovPlainTest
    make run TEST=CovBiasedTest

    python3 scripts/figures/functional_coverage_cross.py
"""
from matplotlib.patches import Rectangle

from uvm_figure_style import BLUE, GRID, INK, INK_2, MONO, canvas, save

OPS = ["add", "sub", "or_op", "nand_op", "shl", "shr"]
RUNS = [
    ("CovPlainTest: A and B uniformly random",
     {"differ": [50, 57, 41, 45, 52, 53], "equal": [1, 0, 0, 0, 1, 0]}),
    ("CovBiasedTest: A == B in one vector in eight",
     {"differ": [50, 44, 42, 43, 38, 34], "equal": [4, 6, 4, 13, 10, 12]}),
]

CW, CH = 1.12, 0.42
fig, ax = canvas(10.0, 2.55, xlim=(-1.25, 15.8), ylim=(-0.35, 2.05))

for k, (title, counts) in enumerate(RUNS):
    x0 = k * 8.5
    ax.text(x0 + 3 * CW, 1.85, title, ha="center", va="center", size=8.8, color=INK)
    for j, op in enumerate(OPS):
        ax.text(x0 + (j + 0.5) * CW, 1.5, op, ha="center", va="center", family=MONO, size=8,
                color=INK)
    for r, row in enumerate(("differ", "equal")):
        y = 0.85 - r * CH
        if k == 0:
            ax.text(x0 - 0.12, y + CH / 2, row, ha="right", va="center", family=MONO, size=8,
                    color=INK)
        for j, n in enumerate(counts[row]):
            x = x0 + j * CW
            if n > 0:
                ax.add_patch(Rectangle((x, y), CW, CH, facecolor="#dbe8f8", edgecolor="white",
                                       lw=2))
                ax.text(x + CW / 2, y + CH / 2, str(n), ha="center", va="center", size=8.5,
                        color=INK)
            else:
                ax.add_patch(Rectangle((x + 0.03, y + 0.03), CW - 0.06, CH - 0.06,
                                       facecolor="white", edgecolor=BLUE, lw=1.2, hatch="////"))
                ax.text(x + CW / 2, y + CH / 2, "0", ha="center", va="center", size=8.5,
                        color=INK, bbox=dict(facecolor="white", edgecolor="none", pad=1))
    hit = sum(1 for row in counts.values() for n in row if n > 0)
    ax.text(x0 + 3 * CW, 0.0, f"{hit} of 12 bins hit", ha="center", va="center", size=8.5,
            color=INK_2)
    ax.plot([x0, x0 + 6 * CW], [0.85 + CH + 0.08, 0.85 + CH + 0.08], color=GRID, lw=0.8)

save(fig, "functional-coverage-cross")
