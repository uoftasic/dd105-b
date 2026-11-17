"""Shared look for the figures on the UVM guide pages (plain matplotlib).

Every figure script in this folder whose name starts with a guide page's slug
imports this, draws on the axes it gets from canvas(), and calls save(), which
writes an SVG into docs/assets/img/ on a white background, so a figure reads the
same on the light and dark site themes and in the PDFs:

    python3 scripts/figures/the_uvm_skeleton_tree.py

The numbers a chart plots are copied from a run of the guide example named in
its script, and the script says which run. Rerunning a script with the same
matplotlib writes the same SVG: save() fixes the id salt and leaves out the date.
"""
import os

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "uoftasic-figures"
matplotlib.rcParams["font.family"] = "DejaVu Sans"
matplotlib.rcParams["font.size"] = 10
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

IMG_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "docs", "assets", "img"))

INK = "#0b0b0b"         # text and lines
INK_2 = "#52514e"       # secondary text
GRID = "#d9d8d4"        # recessive rules
FILL = "#f3f2ef"        # box fill
BLUE = "#2a78d6"        # first series
ORANGE = "#eb6834"      # second series
MONO = "DejaVu Sans Mono"


def canvas(w, h, xlim=None, ylim=None, axis=False):
    """A figure w x h inches with one axes. With axis=False the axes are hidden
    and xlim/ylim set a drawing area in data units."""
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    if not axis:
        ax.set_axis_off()
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_aspect("auto")
    return fig, ax


def box(ax, x, y, w, h, title, sub=None, fill=FILL, mono_title=True, size=9.5):
    """A rounded box with its lower left corner at (x, y): a name, and under it
    the class in smaller grey text."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08",
                                linewidth=1.1, edgecolor=INK, facecolor=fill))
    if sub is None:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", color=INK, size=size,
                family=MONO if mono_title else None)
    else:
        ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", color=INK, size=size,
                family=MONO if mono_title else None)
        ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", color=INK_2,
                size=size - 1.5, family=MONO)


def arrow(ax, xy_from, xy_to, color=INK, lw=1.1, style="-|>", rad=0.0):
    ax.annotate("", xy=xy_to, xytext=xy_from,
                arrowprops=dict(arrowstyle=style, color=color, lw=lw, shrinkA=0, shrinkB=0,
                                connectionstyle=f"arc3,rad={rad}", mutation_scale=10))


def save(fig, name):
    """Write docs/assets/img/<name>.svg on a white background and return its path."""
    path = os.path.join(IMG_DIR, name + ".svg")
    fig.savefig(path, format="svg", facecolor="white", bbox_inches="tight", pad_inches=0.08,
                metadata={"Date": None})
    preview = os.environ.get("FIG_PREVIEW_DIR")   # a PNG copy to look at, if set
    if preview:
        fig.savefig(os.path.join(preview, name + ".png"), format="png", dpi=110,
                    facecolor="white", bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return path
