# Figure scripts

Each script draws one diagram or chart for the site and writes it as an SVG into
`docs/assets/img/`. The schemdraw diagrams take their look from `circuit_style.py`, the style copied
from DD104 so that the courses' diagrams match. Six of the matplotlib figures take theirs from
`uvm_figure_style.py`, DD105-A's style for its UVM guide pages, copied unchanged, and
`reactive_wait_histograms.py` sets its own. Run a script from the top of the clone:

```bash
pip install -r scripts/figures/requirements.txt
python3 scripts/figures/<script>.py
```

With the versions in `requirements.txt` (schemdraw 0.23 and matplotlib 3.10.9), rerunning a script
reproduces its SVG byte for byte, apart from `router_block.py`, `lab01_two_testbenches.py`,
`python_handles.py` and `lab02_tasks.py`. Their SVGs were drawn in the course image, which has
matplotlib 3.11.1, so rerun those four there. `circuit_style.py`'s docstring says the same of
`router_block.py`.
To look at a figure while you work on it, set `FIG_PREVIEW=<folder>` and the script also writes a PNG
there; the site doesn't use the PNGs.

A script whose figure plots numbers from a run says in its docstring which run of which guide
example they came from.

| Script | Writes | Used on |
|---|---|---|
| `router_block.py` | `router-block.svg` | The router in one page |
| `lab01_two_testbenches.py` | `dd105b-lab01-two-testbenches.svg` | What a framework buys you |
| `python_handles.py` | `dd105b-python-handles.svg` | Python classes and cocotb concurrency |
| `lab02_tasks.py` | `dd105b-lab02-tasks.svg` | Python classes and cocotb concurrency |
| `constrained_random_skew.py` | `constrained-random-skew.svg` | Constrained random with pyvsc |
| `functional_coverage_cross.py` | `functional-coverage-cross.svg` | Functional coverage you can read |
| `the_pyuvm_skeleton_tree.py` | `the-pyuvm-skeleton-lab04-tree.svg` | The pyuvm skeleton |
| `the_pyuvm_skeleton_objections.py` | `the-pyuvm-skeleton-objections.svg` | The pyuvm skeleton |
| `sequences_handshake.py` | `sequences-handshake.svg` | Sequences, sequencers and drivers |
| `monitors_lab04_connections.py` | `monitors-lab04-connections.svg` | Monitors, analysis ports and scoreboards |
| `reactive_wait_histograms.py` | `reactive-wait-histograms.svg` | Reactive agents and backpressure |
| `virtual_sequence_handles.py` | `virtual-sequence-handles.svg` | Virtual sequences |
| `register_model_paths.py` | `register-model-paths.svg` | Register models in pyuvm |

Waveform screenshots, such as `assertions-drop-s1.png` on Assertions for interface rules, are made
with `scripts/screenshots/` instead; `guide-examples/README.md` gives the command for each.
