"""
DD105-B: does the router still do what the specification's timing examples say?

    python3 check_examples.py              (from labs/common/smoke, in the course image)

Builds tb_examples.sv on the golden RTL and on the faulty build with no bug
switched on (`make TB_SRC=tb_examples.sv` and `make faulty TB_SRC=...`),
takes the Markdown tables each run prints, and compares them, cell by cell,
with the tables under "Timing examples" in docs/reference/router-spec.md.
Exits 0 only if every table of both runs matches the page exactly.

tb_examples.sv writes no waveform, so the Makefile's vcd2fst step after it
fails and make exits 2 once the tables are printed. This reads the tables,
and needs only the line "EXAMPLES: done" at their end.

DD105-B changed nothing in the router's RTL, so this is the check that its
copy still matches the page it shares with DD105-A.
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "..", "..", "..", "docs", "reference", "router-spec.md")


def tables(text):
    """{'E1': [row, ...]} from '#### E<n>: ...' headings and the table under each."""
    out = {}
    for m in re.finditer(r"^#### (E\d+):[^\n]*\n((?:[^\n]*\n)*?)(?=^#### |^## |\Z)", text, re.M):
        rows = [l.strip() for l in m.group(2).splitlines() if l.strip().startswith("|")]
        out[m.group(1)] = rows
    return out


def norm(rows):
    """Rows as (label, cells). The page writes some labels differently from the
    run (`psel` for `PSEL`, `LEVEL0` (reg) for `LEVEL0 (reg)`), so a label is
    compared without case, backticks or spaces; every cell is compared exactly."""
    out = []
    for r in rows:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        out.append((re.sub(r"[`\s]", "", cells[0]).lower(), cells[1:]))
    return out


def run(target):
    cmd = ["make", "--no-print-directory", "-C", HERE, target, "TB_SRC=tb_examples.sv"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main():
    want = tables(open(SPEC).read())
    ok = True
    for target in ("golden", "faulty"):
        rc, out = run(target)
        got = tables(out)
        if "EXAMPLES: done" not in out:
            print(f"  {target}: the run failed (exit status {rc}). Its last lines:")
            print("\n".join("    " + l for l in out.strip().splitlines()[-15:]))
            ok = False
            continue
        bad = []
        for name, rows in want.items():
            if norm(got.get(name, [])) != norm(rows):
                bad.append(name)
                g = got.get(name, [])
                for i, (a, b) in enumerate(zip(rows, g)):
                    if norm([a]) != norm([b]):
                        print(f"    {target} {name}, row {i + 1}:\n      page: {a}\n      run:  {b}")
                        break
                else:
                    print(f"    {target} {name}: {len(rows)} rows on the page, {len(g)} in the run")
        extra = sorted(set(got) - set(want))
        n_cells = sum(len(r.split("|")) - 3 for rows in want.values() for r in rows[2:])
        print(f"  {target:<7} {len(want) - len(bad)} of {len(want)} examples match the page"
              f" ({n_cells} cells)" + (f"; the run also printed {', '.join(extra)}" if extra else ""))
        ok = ok and not bad and not extra
    print(" EXAMPLES: PASS" if ok else " EXAMPLES: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
