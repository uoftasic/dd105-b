# DD105-B — Testbenches with UVM

Build a UVM testbench in Python, with pyuvm and cocotb on Verilator, for the same packet router as DD105-A.

Part of the UofT ASIC Team education materials (`uoftasic`).
Course site: <https://uoftasic.com/dd105-b/> · Education hub: <https://edu.uoftasic.com/>

DD105-B is the pyuvm version of [DD105-A](https://uoftasic.com/dd105-a/), and comes after
[DD104](https://uoftasic.com/dd104/). It has the same router, the same fifteen planted bugs, the
same seven labs in the same order, and a capstone and rubric like DD105-A's. The testbenches are
Python: pyuvm 4.0.1 on cocotb 2.0.1, with pyvsc 1.1.0 for constrained random and cocotb-coverage 2.0
for functional coverage, on Verilator 5.050. The only SystemVerilog a student writes is the
assertions in Labs 05 and 07.

This repository is being built. The shared build, the graders, the reference environment, CI,
Labs 01 to 07, the home page, the eighteen guide pages and the four reference pages are in place,
and the site and the course PDF build. The repository isn't on GitHub yet, so Getting started
describes `mod add dd105-b` without quoting what it prints.

## Quick start

Everything runs in the team workbench image `hpretl/iic-osic-tools:2026.08` (Verilator 5.050,
cocotb 2.0.1, pyuvm 4.0.1, Python 3.12). pyvsc and cocotb-coverage aren't in the image; `make venv`
puts them in a venv once (about 12 s and 37 MB), in your workspace under `/foss/designs` when it's
writable and otherwise in the clone.

From a clone of this repo, with Docker and the image:

```bash
git clone https://github.com/uoftasic/dd105-b.git
cd dd105-b
export IMAGE=hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7
scripts/ci/in-image.sh make -C labs/ref venv        # once
scripts/ci/in-image.sh make -C labs/ref check-all   # the reference environment against all 15 bugs
```

## Lab packages

| Path | What it is |
|---|---|
| `labs/common/` | the router's RTL and bug catalogue, the shared cocotb + pyuvm build (`pyuvm.mk`), the course venv's `requirements.txt`, the base test and the graders; see [`labs/common/README.md`](labs/common/README.md) |
| `labs/common/selftest/` | proves every verdict class still fires, on a small ALU with pyuvm fixtures |
| `labs/ref/` | the router's reference pyuvm environment, written from the specification; it catches all fifteen bugs |
| `labs/lab-01-one-alu-two-frameworks/` | Lab 01: SimProc's ALU with its three bugs, A01 to A03, DD104's cocotb test and a pyuvm testbench |
| `labs/lab-02-a-layered-testbench-without-pyuvm/` | Lab 02: a plain-cocotb testbench for the router, whose monitor and scoreboard the student writes, and B05 and B09 |
| `labs/lab-03-constraints-and-coverage/` | Lab 03: Lab 02's testbench with pyvsc packets, a level tracker and a `DROP_CNT` check; the student writes its coverage with cocotb-coverage, its length constraints and the stimulus that reaches B07 and B08 |
| `labs/lab-04-the-same-testbench-in-pyuvm/` | Lab 04: our Lab 03 solution ported to pyuvm; the student adds an agent for output 1, a stall test and a factory override that sends packets to disabled routes, which reach B06 and B13 |
| `labs/lab-05-protocol-rules-and-backpressure/` | Lab 05: our Lab 04 solution with assertions bound into the router, a sink that can answer each beat and a virtual sequence; the student writes three of the assertions, the sink driver's answer to a beat and the sequence, which reaches B11 |
| `labs/lab-06-the-register-block/` | Lab 06: our Lab 05 solution with a register model on pyuvm's `uvm_reg` classes and scoreboard checks on `STATUS`, `PSLVERR` and `irq`; the student writes seven registers' fields, the adapter, the predictor, the reset and bit-bash sequences, the `irq` check and the sequence that reaches B01 to B04 and B14 |
| `labs/lab-07-capstone/` | Lab 07: our Lab 06 solution with a reset driver, a scoreboard that follows a reset with traffic in flight and four corners in the coverage; the student writes a verification plan and report from the templates there, the assertions for the rules about reset, and the reset and saturation sequences, which reach B15 |

`labs/common/bugs.py` is the answer key to the planted bugs, so a student should not open it until
the labs are done.

`.github/workflows/labs.yml` checks the reference solutions in the course image: it makes the
course venv, then `labs/common/selftest` must pass, and `labs/ref` must catch all fifteen bugs and
pass the golden router on seeds 1 to 5. Each lab has a step that requires the starter's
`make check` to fail and the solution's to pass. It runs on changes to
`labs/`, its scripts in
`scripts/ci/` and itself, every Monday, and by hand. Each step is one command you can run locally,
for example `scripts/ci/in-image.sh scripts/ci/check-labs.sh ref`.

## Docs

The course site is built with Quarto from `./docs`. `docs/_quarto.yml` holds the site, sidebar
and navbar, and `docs/_quarto-pdf.yml` builds the whole course as one PDF. To preview it you need
[Quarto](https://quarto.org/docs/get-started/) 1.11:

```bash
quarto preview docs                            # -> http://localhost:4200
quarto render docs --profile pdf --to typst    # whole course as one PDF in docs/_book/
```

| Path | On Pages? | Purpose |
|------|-----------|---------|
| `docs/` | Yes | The course site; `docs/index.md` is the home page and has the Course path |
| `docs/guide/` | Yes | Guide pages: reading only, no commands |
| `docs/labs/` | Yes | Lab writeups: every command a student runs, in numbered parts and steps |
| `docs/reference/` | Yes | Lookup pages: the router's specification, a one-page summary of it, pyuvm's register API, and getting the tools outside the course image |
| `labs/` | No | Runnable packages |
| `guide-examples/` | No | The examples that the guide and reference pages quote, one folder per page, each built with `labs/common/pyuvm.mk`; [`guide-examples/README.md`](guide-examples/README.md) lists the commands behind every output a page quotes |
| `scripts/` | No | `check_site.py`, the link check for the rendered site; `ci/`, the reference-solution checks; `figures/`, the scripts that draw the site's SVG diagrams and charts; `screenshots/`, the tool that draws the waveform figures |
| `notebooks/`, `data/`, `figures/` | No | Repo scaffolding, unused by DD105-B |

On every push to `main` that touches `docs/`, `scripts/check_site.py` or the workflow itself,
`.github/workflows/site.yml` renders the site (with a PDF of every page) and the course PDF, checks
the rendered site's local links and anchors with `scripts/check_site.py`, and deploys `docs/_site`.
For the deploy, GitHub Pages has to be set to Source: GitHub Actions, which `TEMPLATE.md`'s
checklist still lists as to do, since the repository isn't on GitHub yet.

This repo was created from [uoftasic/course-template](https://github.com/uoftasic/course-template)
at commit `92e35ab`. `TEMPLATE.md`, `REFERENCE-SOLUTION-CI.md` and `scripts/init-template.py` are
that template's files and are not part of the course.

## Copied from DD105-A

DD105-B carries its own copy of everything it shares with DD105-A. No module is shared between the
two courses, so a change to one course's copy doesn't reach the other. Every file below was copied
from [uoftasic/dd105-a](https://github.com/uoftasic/dd105-a) at commit
`da489f273945e44c49069adee8dc45ac346bd42a` (Nov 16, 2026). Two commits, "Copy the shared files from
DD105-A da489f2" and "Copy the router's directed reference test from DD105-A da489f2", hold them
byte for byte, and the commits after those hold every change DD105-B made to them.
The copy of `scripts/screenshots/`, from the same DD105-A commit, is in a later commit of its own,
"Copy scripts/screenshots from DD105-A da489f2". Lab 07's assertions and templates, from the same
commit, are in another, "Copy Lab 07's assertions and templates from DD105-A da489f2", and
`scripts/figures/uvm_figure_style.py`, the same at that commit, is in "Figures: DD105-A's
uvm_figure_style.py, copied unchanged".

| Here | From DD105-A | What it is |
|---|---|---|
| `labs/common/rtl/` | `labs/common/rtl/` | the router's RTL, the golden design (unchanged) |
| `labs/common/bugs.py`, `labs/common/inject.py` | the same paths | the bug catalogue (B01 to B15) and the script that builds the faulty router with the `+BUG` switch |
| `labs/common/smoke/` | `labs/common/smoke/` (all but `build/`) | the router's shipped test, `tb_smoke.sv`, and `tb_examples.sv`, which prints the specification's timing examples |
| `labs/common/solutions/` | `labs/common/solutions/` | the router's directed reference test, `tb_directed.sv`, whose checks the catalogue's `caught_by` lists name, and `run_catalogue.py`, which checks the catalogue end to end |
| `docs/reference/router-spec.md`, `docs/reference/the-router-in-one-page.md` | the same paths | the router's specification and its one-page summary |
| `docs/assets/img/router-block.svg`, `scripts/figures/router_block.py`, `scripts/figures/circuit_style.py`, `scripts/figures/requirements.txt` | the same paths | the router's block diagram and the script that draws it |
| `labs/lab-05-protocol-rules-and-backpressure/tb/router_sva.sv`, `tb/router_sva_bind.sv`, `solutions/router_sva.sv` | the same paths | Lab 05's assertions (the starter with its TODOs, and the solution) and the `bind` that puts them into the router |
| `labs/ref/tb/router_sva.sv`, `labs/ref/tb/router_sva_bind.sv` | the same paths | the reference environment's full set of assertions (valid/ready, APB and reset rules) and their `bind` |
| `labs/lab-07-capstone/tb/router_sva.sv`, `tb/router_sva_bind.sv`, `solutions/tb/router_sva.sv` | the same paths | Lab 07's assertions (the starter, with the reset rules as TODOs, and the solution) and their `bind`, which adds the APB port and `irq` |
| `labs/lab-07-capstone/PLAN-template.md`, `REPORT-template.md` | the same paths | the capstone's verification plan and report templates |
| `labs/lab-01-one-alu-two-frameworks/rtl/alu.sv`, `labs/lab-01-one-alu-two-frameworks/bugs.json` | `labs/lab-01-one-alu-two-testbenches/rtl/alu.sv`, `bugs.json` | SimProc's ALU with DD104's three ALU bugs, A01 to A03, behind `+BUG` |
| `scripts/screenshots/` | `scripts/screenshots/` | the tool that draws the labs' waveform figures in a headless Surfer or GTKWave |
| `scripts/figures/uvm_figure_style.py` | the same path | the matplotlib style of six of the guide pages' figures (unchanged) |

DD105-B's changes to these files are comments, links and one sentence on each spec page, apart
from Lab 07's two templates: the assertion files, the ALU and `inject.py` describe DD105-B (Python
reads the counters, Verilator only), the spec pages link to this repository, and each spec page
says that this course's Python testbenches change the router's inputs right after a rising edge,
where DD105-A's pages say 1 ns after. The templates name this course's checkers, sequences and
coverage groups, and the report template's note on coverage numbers describes cocotb-coverage
instead of Verilator. The router's RTL needed no change: its assertions already sit in their own
file and are attached with `bind`, every assertion already counts its failures beside its `$error`
(`n_<rule>`, summed in `n_fail`, which DD105-B's base test reads through cocotb), and `+BUG` is
already a plusarg read once in an initial block. `labs/common/smoke/check_examples.py` (DD105-B's)
shows that the golden RTL and the faulty build still produce every table in the specification's
timing examples.

DD105-B also started from code it didn't copy byte for byte: `labs/common/check.py`, `hunt.py` and
`regress.py`, `scripts/ci/check-labs.sh` and `in-image.sh`, `labs/common/dd105b_trace.vlt` and the
selftest's ALU and assertion are DD105-A's, adapted; `labs/common/verdict.py` is DD104's, with
DD105-A's run-folder reading added. Each file's header says so. Lab 01's `cocotb/test_alu.py` (DD104
Lab 03's reference test) and `src/loc.py` are DD105-A's at the same commit, with the first line of
each docstring naming DD105-B.

DD105-B doesn't use DD105-A's `third_party/uvm` (the SystemVerilog UVM library), so it isn't copied.
DD105-A's `docs/reference/register-layer.md` documents SystemVerilog UVM's register layer, whose
API pyuvm's doesn't follow, so it isn't copied either; `docs/reference/pyuvm-register-api.md` is
DD105-B's own page for Lab 06. `docs/reference/getting-the-tools-outside-the-course-image.md`
follows DD105-A's page of that name, and its Verilator build steps are quoted from that page.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). Copyright UofT ASIC Team / `uoftasic`.
