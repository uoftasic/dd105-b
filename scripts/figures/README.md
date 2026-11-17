# Figure scripts

Each script draws one diagram or chart for the site and writes it as an SVG into
`docs/assets/img/`. The block diagrams take their look from `circuit_style.py`, the schemdraw style
copied from DD104 so that the courses' diagrams match; the charts set their own. Run a script from
the top of the clone:

```bash
pip install -r scripts/figures/requirements.txt
python3 scripts/figures/<script>.py
```

With the versions in `requirements.txt` (schemdraw 0.23 and matplotlib 3.10.9), rerunning a script
reproduces its SVG byte for byte, apart from `router_block.py`, whose SVG was drawn in the course
image (see its docstring). To look at a figure while you work on it, set `FIG_PREVIEW=<folder>` and
the script also writes a PNG there; the site doesn't use the PNGs.

A script whose figure plots numbers from a run says in its docstring which run of which guide
example they came from.

| Script | Writes | Used on |
|---|---|---|
| `router_block.py` | `router-block.svg` | The router in one page |
| `reactive_wait_histograms.py` | `reactive-wait-histograms.svg` | Reactive agents and backpressure |
| `virtual_sequence_handles.py` | `virtual-sequence-handles.svg` | Virtual sequences |
| `register_model_paths.py` | `register-model-paths.svg` | Register models in pyuvm |

Waveform screenshots, such as `assertions-drop-s1.png` on Assertions for interface rules, are made
with `scripts/screenshots/` instead; `guide-examples/README.md` gives the command for each.
