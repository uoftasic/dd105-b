"""The pyuvm skeleton: what kept the run phase going in SkPhaseTest.

The times are from a run of guide-examples/the-pyuvm-skeleton:

    make run TEST=SkPhaseTest

uvm_test_top raised an objection at 0 ns and dropped it at 100 ns;
uvm_test_top.env.a1.child raised one at 0 ns and dropped it at 150 ns;
uvm_test_top.env.mon printed "still looping" at 0, 40, 80 and 120 ns;
extract_phase ran at 150 ns, and the test ended there.

    python3 scripts/figures/the_pyuvm_skeleton_objections.py
"""
from uvm_figure_style import BLUE, GRID, INK, INK_2, MONO, canvas, save

fig, ax = canvas(8.6, 2.7, xlim=(-62, 200), ylim=(-0.95, 3.35))

rows = [("uvm_test_top", 2.6), ("env.a1.child", 1.8), ("env.mon", 1.0)]
for name, y in rows:
    ax.text(-6, y, name, ha="right", va="center", family=MONO, size=9, color=INK)

# the time axis
ax.plot([0, 185], [0.3, 0.3], color=INK, lw=0.9)
for t in range(0, 181, 20):
    ax.plot([t, t], [0.3, 0.22], color=INK, lw=0.9)
    ax.text(t, 0.08, f"{t}", ha="center", va="top", size=8.5, color=INK)
ax.text(186, 0.08, "ns", ha="left", va="top", size=8.5, color=INK)
for t in (100, 150):
    ax.plot([t, t], [0.35, 3.05], color=GRID, lw=0.9, zorder=0)

# objections: a bar from raise to drop
ax.barh(2.6, 100, left=0, height=0.34, color=BLUE, edgecolor="none")
ax.barh(1.8, 150, left=0, height=0.34, color=BLUE, edgecolor="none")
ax.text(50, 2.6, "objection", ha="center", va="center", size=8.5, color="white")
ax.text(75, 1.8, "objection", ha="center", va="center", size=8.5, color="white")

# the monitor-like loop: a tick at each "still looping"
for t in (0, 40, 80, 120):
    ax.plot([t, t], [0.84, 1.16], color=INK, lw=1.4)
ax.plot([0, 150], [1.0, 1.0], color=INK, lw=0.8, ls=(0, (2, 2)))
ax.text(152, 1.0, "stops with the test", ha="left", va="center", size=8.5, color=INK_2)

ax.text(150, -0.45, "the last objection drops: extract_phase at 150 ns", ha="center",
        va="center", size=8.5, color=INK)

save(fig, "the-pyuvm-skeleton-objections")
