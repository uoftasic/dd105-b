"""The pyuvm skeleton: the component tree of Lab 04's testbench.

The names and classes are the ones a probe test printed from Lab 04's
solution (labs/lab-04-the-same-testbench-in-pyuvm, with solutions/router_env.py
and solutions/test_router.py copied into tb/), walking every component's
children from uvm_test_top down at end_of_elaboration_phase. The probe test
derived from RouterInjectTest, which is drawn here. The ports and exports the
walk also printed (each monitor's ap, each sequencer's seq_item_export, each
driver's seq_item_port, the scoreboard's fate_ap, and an analysis_export under
each Fwd and under cov) are left out.

    python3 scripts/figures/the_pyuvm_skeleton_tree.py
"""
from uvm_figure_style import INK, box, canvas, save

W, H = 1.62, 0.62          # a box
CW, CH = 1.42, 0.5         # a child box
COL = 2.08                 # distance between columns

fig, ax = canvas(12.4, 5.0, xlim=(-0.2, 12.25), ylim=(-0.25, 4.85))


def tree_line(x0, y0, xs, y1):
    """From the bottom centre of a parent at (x0, y0) down to the tops of
    children whose centres are xs, all with their tops at y1."""
    ym = (y0 + y1) / 2
    ax.plot([x0, x0], [y0, ym], color=INK, lw=1.0)
    ax.plot([min(xs + [x0]), max(xs + [x0])], [ym, ym], color=INK, lw=1.0)
    for x in xs:
        ax.plot([x, x], [ym, y1], color=INK, lw=1.0)


# the test and the environment
cx = 0.8 + COL * 2.5
box(ax, cx - W / 2 - 0.25, 4.15, W + 0.5, H, "uvm_test_top", "RouterInjectTest")
box(ax, cx - W / 2, 3.15, W, H, "env", "RouterEnv")
tree_line(cx, 4.15, [cx], 3.15 + H)

# the environment's children, in the order RouterEnv makes them
kids = [("src", "SrcAgent"), ("apb", "ApbAgent"), ("out0", "OutAgent"),
        ("out1", "OutAgent"), ("sb", "RouterScoreboard"), ("cov", "RouterCoverage")]
xs = [0.8 + COL * i for i in range(len(kids))]
for (name, cls), x in zip(kids, xs):
    w = W + (0.22 if cls.startswith("Router") else 0)
    box(ax, x - w / 2, 1.95, w, H, name, cls)
tree_line(cx, 3.15, xs, 1.95 + H)

# the agents' and the scoreboard's children, stacked under each
stacked = {
    0: [("sqr", "uvm_sequencer"), ("drv", "SrcDriver"), ("mon", "SrcMonitor")],
    1: [("sqr", "uvm_sequencer"), ("drv", "ApbDriver"), ("mon", "ApbMonitor")],
    2: [("drv", "OutReadyDriver"), ("mon", "OutMonitor")],
    3: [("drv", "OutReadyDriver"), ("mon", "OutMonitor")],
    4: [("in_imp", "Fwd"), ("out_imp", "Fwd"), ("apb_imp", "Fwd")],
}
for i, children in stacked.items():
    x = xs[i]
    top = 1.95
    last = 1.13 - 0.62 * (len(children) - 1) + CH / 2
    ax.plot([x - CW / 2 - 0.08, x - CW / 2 - 0.08], [top, last], color=INK, lw=1.0)
    for k, (name, cls) in enumerate(children):
        y = 1.13 - 0.62 * k
        ax.plot([x - CW / 2 - 0.08, x - CW / 2 + 0.06], [y + CH / 2, y + CH / 2], color=INK, lw=1.0)
        box(ax, x - CW / 2 + 0.06, y, CW, CH, name, cls, size=8.5)

save(fig, "the-pyuvm-skeleton-lab04-tree")
