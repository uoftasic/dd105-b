"""Reactive agents and backpressure: how long each of 2,000 beats waited, for four sinks.

    python3 scripts/figures/reactive_wait_histograms.py

writes docs/assets/img/reactive-wait-histograms.svg. The counts are the [HIST] lines of four
runs of guide-examples/reactive-agents-and-backpressure on seed 1, copied here as printed:

    make run PLUSARGS="+MODE=coin +READY_PCT=5"
    make run PLUSARGS="+MODE=coin +READY_PCT=50"
    make run PLUSARGS="+MODE=beat +MAX_DELAY=12"
    make run PLUSARGS="+MODE=beat +MAX_DELAY=12 +ITEM=vsc"

Each line is wait:beats for every wait that some beat had, with 40 standing for 40 or more.
"""
import os

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "uoftasic-figures"
matplotlib.rcParams["font.family"] = "serif"
import matplotlib.pyplot as plt  # noqa: E402

RUNS = [
    ("coin flip, ready in 5% of cycles",
     "0:82 1:99 2:94 3:96 4:71 5:75 6:59 7:63 8:63 9:73 10:52 11:55 12:52 13:49 14:55 15:38 16:55 "
     "17:51 18:26 19:40 20:34 21:30 22:30 23:32 24:35 25:47 26:28 27:33 28:31 29:29 30:17 31:24 "
     "32:21 33:17 34:16 35:18 36:17 37:21 38:12 39:16 40:244"),
    ("coin flip, ready in 50% of cycles",
     "0:973 1:495 2:259 3:136 4:68 5:34 6:9 7:16 8:7 9:1 10:2"),
    ("per beat, delay 0 to 12 from random.randint",
     "0:164 1:158 2:151 3:156 4:131 5:154 6:149 7:162 8:154 9:143 10:156 11:138 12:184"),
    ("per beat, delay 0 to 12 from pyvsc's randomize()",
     "0:143 1:116 2:127 3:137 4:112 5:169 6:184 7:184 8:117 9:159 10:150 11:196 12:206"),
]

BAR = "#2a78d6"      # one series per panel, so one hue
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#d8d7d2"

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                    "docs", "assets", "img", "reactive-wait-histograms.svg"))

fig, axes = plt.subplots(len(RUNS), 1, figsize=(7.6, 7.2), sharex=True)
x = list(range(41))
for ax, (title, line) in zip(axes, RUNS):
    h = [0] * 41
    for pair in line.split():
        k, n = pair.split(":")
        h[int(k)] = int(n)
    assert sum(h) == 2000, title
    ax.bar(x, h, width=0.78, color=BAR, linewidth=0)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=4)
    # The two per-beat panels share a scale, so their bars can be compared.
    ax.set_ylim(0, 260 if title.startswith("per beat") else max(h) * 1.15)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.set_ylabel("beats", fontsize=9, color=MUTED)

axes[-1].set_xticks([0, 5, 10, 15, 20, 25, 30, 35, 40])
axes[-1].set_xticklabels(["0", "5", "10", "15", "20", "25", "30", "35", "40+"])
axes[-1].set_xlabel("cycles the beat waited before it was taken", fontsize=10, color=INK)
fig.tight_layout(h_pad=1.2)
fig.savefig(OUT, format="svg", facecolor="white", metadata={"Date": None})
if os.environ.get("FIG_PREVIEW"):
    fig.savefig(os.path.join(os.environ["FIG_PREVIEW"], "reactive-wait-histograms.png"), dpi=110)
print(OUT)
