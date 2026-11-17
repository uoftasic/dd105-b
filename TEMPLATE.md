# Template bootstrap (UofT ASIC)

To start a course or lab-notes repo: create it from this template under `uoftasic`, fill in the three course fields, and enable Pages.

## Fixed and fillable values

| Item | Value |
|------|--------|
| GitHub org | `uoftasic` (hardcoded, don't change it) |
| Team | UofT ASIC Team |

| Token | Meaning | Example |
|-------|---------|---------|
| `dd105-b` | Repo slug and course id | `dd103`, `ic101`, `serdes-lab` |
| `DD105-B — Testbenches with UVM` | Display name | `DD103 — RTL on FPGAs & ASICs` |
| `Build a UVM testbench in Python, with pyuvm and cocotb on Verilator, for the same packet router as DD105-A.` | One-line blurb | `RTL synthesis intro with Yosys` |

## Init script

```bash
python3 scripts/init-template.py \
  --id dd103 \
  --title "DD103 — RTL on FPGAs & ASICs" \
  --description "RTL on FPGAs and open-source ASIC flows"
```

Add `--dry-run` to see what it would change without writing anything.

## After-clone checklist

- [x] `scripts/init-template.py` run with the three values above
- [x] The template's sample lab removed (`docs/labs/lab-01-overview.md`, `labs/lab-01/`, `scripts/hello.py`)
- [x] Home page filled in: who the course is for, the prerequisites, the time for the labs, and the 14 course path rows
- [ ] The Read rows' times and the total time on the home page (marked `READTIME` in `docs/index.md`), once the guide pages exist, so the rows add up to the total
- [ ] The template's sample Getting started page, `docs/guide/getting-started.md`, replaced by DD105-B's own, and its sample figure, `docs/assets/img/sample-figure.png`, deleted
- [x] Sidebar in `docs/_quarto.yml` and chapters in `docs/_quarto-pdf.yml` in course path order: Home, then seven sections, each a Read row's guide pages and its lab (Getting started to Lab 07: Capstone), then the reference pages
- [ ] The course PDF builds (`quarto render docs --profile pdf --to typst`), which needs every guide page that `docs/_quarto-pdf.yml` lists
- [x] Math and figures render: the formulas and the block diagram on The router in one page, and the waveforms on the lab pages
- [ ] Repo created under `uoftasic`, named `dd105-b`, and pushed to `main`
- [ ] Pages: **Settings → Pages → Source: GitHub Actions** (`.github/workflows/site.yml` builds `docs/` with Quarto)
- [ ] Live at `https://uoftasic.com/dd105-b/` (org Pages; the hub is https://edu.uoftasic.com/)
- [ ] The first run of `.github/workflows/labs.yml` on GitHub passes

The pages follow the course structure in [AGENTS.md](AGENTS.md). The home page has the course path,
guide pages are for reading only, and lab writeups are the one place where students run things. The
seven labs are the worked examples of a lab writeup.

## Naming

Use a course id the team already follows (`ic###`, `ad###`, `dd###`) or a clear kebab-case lab name. Keep the GitHub repo name equal to `dd105-b` so the Pages and clone URLs are predictable.

## Related

Each course made from this template is published at `https://uoftasic.com/<course-id>/`, with its Quarto site under `docs/` and its runnable code in `labs/` and `scripts/`. The education hub is https://edu.uoftasic.com/.
