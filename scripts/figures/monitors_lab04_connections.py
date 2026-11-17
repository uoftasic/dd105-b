"""Monitors, analysis ports and scoreboards: where Lab 04's transactions go.

The connections are the ones RouterEnv.connect_phase makes in
labs/lab-04-the-same-testbench-in-pyuvm/solutions/router_env.py:

    self.src.mon.ap.connect(self.sb.in_imp.analysis_export)
    self.apb.mon.ap.connect(self.sb.apb_imp.analysis_export)
    self.out[0].mon.ap.connect(self.sb.out_imp.analysis_export)
    self.out[1].mon.ap.connect(self.sb.out_imp.analysis_export)
    self.sb.fate_ap.connect(self.cov.analysis_export)

and the methods are the ones each Fwd passes its writes to.

    python3 scripts/figures/monitors_lab04_connections.py
"""
from matplotlib.patches import Circle, Rectangle

from uvm_figure_style import BLUE, INK, INK_2, MONO, arrow, box, canvas, save

fig, ax = canvas(9.2, 4.0, xlim=(0, 10.4), ylim=(0.1, 4.6))

# the monitors, on the left, each in its agent
mons = [("src.mon", "SrcMonitor", 3.75),
        ("apb.mon", "ApbMonitor", 2.75),
        ("out0.mon", "OutMonitor", 1.75),
        ("out1.mon", "OutMonitor", 0.75)]
MW, MH = 1.75, 0.62
for name, cls, y in mons:
    box(ax, 0.2, y - MH / 2, MW, MH, name, cls, size=9)

# the scoreboard, with its three Fwd inputs and the method each one calls
SBX, SBW = 5.0, 2.3
box(ax, SBX, 0.35, SBW, 3.85, "", None)
ax.text(SBX + SBW / 2, 3.95, "sb", ha="center", va="center", family=MONO, size=10, color=INK)
ax.text(SBX + SBW / 2, 3.68, "RouterScoreboard", ha="center", va="center", family=MONO,
        size=8, color=INK_2)
inputs = [("in_imp", "write_in()", 3.05), ("apb_imp", "write_apb()", 2.2),
          ("out_imp", "write_out()", 1.25)]
for name, fn, y in inputs:
    ax.add_patch(Circle((SBX, y), 0.07, facecolor="white", edgecolor=INK, lw=1.1, zorder=3))
    ax.text(SBX + 0.15, y + 0.12, name, ha="left", va="center", family=MONO, size=8.5, color=INK)
    ax.text(SBX + 0.15, y - 0.16, fn, ha="left", va="center", family=MONO, size=8.5, color=BLUE)

# the analysis ports on the monitors, and the connections
targets = {"src.mon": 3.05, "apb.mon": 2.2, "out0.mon": 1.25, "out1.mon": 1.25}
for name, _, y in mons:
    x0 = 0.2 + MW
    ax.add_patch(Rectangle((x0 - 0.06, y - 0.06), 0.12, 0.12, facecolor=INK, edgecolor=INK,
                           zorder=3))
    arrow(ax, (x0 + 0.06, y), (SBX - 0.08, targets[name]), lw=1.1)
ax.text(2.1, 4.35, "ap.write(t): one call per beat or transfer", ha="left", va="center",
        size=8.5, color=INK_2)

# the coverage subscriber, fed by the scoreboard's own analysis port
FY = 2.62
ax.add_patch(Rectangle((SBX + SBW - 0.06, FY - 0.06), 0.12, 0.12, facecolor=INK, edgecolor=INK,
                       zorder=3))
ax.text(SBX + SBW - 0.15, FY + 0.02, "fate_ap", ha="right", va="center", family=MONO, size=8.5,
        color=INK)
box(ax, 8.3, FY - 0.31, 1.85, 0.62, "cov", "RouterCoverage", size=9)
arrow(ax, (SBX + SBW + 0.06, FY), (8.3 - 0.02, FY), lw=1.1)
ax.text(8.3 + 0.92, FY - 0.58, "write(): sample_pkt()", ha="center", va="center", family=MONO,
        size=8, color=BLUE)

save(fig, "monitors-lab04-connections")
