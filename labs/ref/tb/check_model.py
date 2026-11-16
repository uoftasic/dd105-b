"""
DD105-B reference environment: the model against the specification's timing
examples, with no simulator.

    python3 tb/check_model.py        (from labs/ref)

Reads the nine tables under "Timing examples" in docs/reference/router-spec.md,
sets the model up as each example's "Setup" line says, feeds it the inputs of
each cycle (rst_n, the APB inputs, in_valid, in_data, in_last and the
out_ready signals) and compares every other row: the outputs the model
predicts, and the register values marked (reg). A dash is a value that
doesn't matter, and is skipped. Exits 0 only if every cell matches.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from router_model import RouterModel, Sample  # noqa: E402

SPEC = os.path.join(HERE, "..", "..", "..", "docs", "reference", "router-spec.md")
INPUTS = ["rst_n", "psel", "penable", "pwrite", "paddr", "pwdata", "in_valid", "in_data",
          "in_last", "out0_ready", "out1_ready"]
HEX = {"paddr", "pwdata", "prdata", "in_data", "out0_data", "out1_data"}


def tables():
    text = open(SPEC).read()
    out = {}
    for m in re.finditer(r"#### (E\d):.*?\n((?:\|[^\n]*\n)+)", text, re.S):
        rows = {}
        for line in m.group(2).strip().splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells[0] == "cycle" or set(cells[0]) <= set("-"):
                continue
            rows[cells[0].replace("` (reg)", " (reg)").replace("`", "")] = cells[1:]
        out[m.group(1)] = rows
    return out


def value(cell, hexa):
    return None if cell == "-" else int(cell, 16 if hexa else 10)


def setup(name):
    """The state each example's Setup line describes, after a reset."""
    m = RouterModel()
    m.reset()
    if name in ("E2", "E3", "E5", "E6", "E7", "E8"):
        m.route_en[0], m.en = 1, 1                  # ROUTE0 = 0x1, CTRL.EN = 1
    if name == "E4":
        m.int_en, m.en = 1, 1                       # INT_EN = 0x1, every route disabled
    if name == "E9":
        m.en, m.cnt_noroute, m.status = 1, 2, 1     # two drops have made NOROUTE_CNT 2
    if name == "E5":
        for i in range(1, 10):                      # nine 1-beat packets waiting on output 0
            m.q[0].append((i, 1, -100 + i))
    if name == "E8":
        m.q[0].append((0x01, 0, -100))              # the packet 01 aa waiting on output 0
        m.q[0].append((0xAA, 1, -99))
    return m


def registers(m):
    return {"CTRL.EN (reg)": m.en, "STATUS (reg)": m.status, "LEVEL0 (reg)": m.level(0),
            "NOROUTE_CNT (reg)": m.cnt_noroute, "FULL_CNT (reg)": m.cnt_full}


def main():
    bad = cycles = 0
    for name, rows in tables().items():
        m = setup(name)
        n = len(next(iter(rows.values())))
        held = {}
        for c in range(n):
            pins = {"rst_n": 1, "out0_ready": 1, "out1_ready": 1}
            for k in INPUTS:
                if k in rows:
                    v = value(rows[k][c], k in HEX)
                    pins[k] = held.get(k, 0) if v is None else v
            held.update(pins)
            if not pins["rst_n"]:
                m.reset()
            regs = registers(m)
            p = m.step(Sample(cycle=c + 1, **pins))
            for k, cells in rows.items():
                want = value(cells[c], k in HEX)
                if want is None or k in INPUTS:
                    continue
                got = regs[k] if k in regs else p.get(k)
                if got != want:
                    bad += 1
                    print(f"  {name} cycle {c + 1} {k}: the model gives {got}, the page {want}")
        cycles += n
        print(f"  {name}: {n} cycles")
    print(f" {cycles} cycles in {len(tables())} examples, {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
