"""
DD105-B: a regression. DD105-A's regress.py, run on cocotb + pyuvm. Every
test in TESTS on every seed in SEEDS, from one build, then the coverage of
all of them together (cocotb-coverage's merge).

    make regress                       TESTS x SEEDS (NSEEDS=10: seeds 1 to 10)
    make seeds TEST=x NSEEDS=50
    make regress SEEDS="1 7 42" BUG=B03

Each run is classified by verdict.py, so a run that crashed or raised
UVMFatalError shows as BROKEN, not as a failure of the design. The seed is
COCOTB_RANDOM_SEED, which seeds Python's random module (and with it pyvsc). Every row ends
with the command that repeats it on its own.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import covmerge                                 # noqa: E402
import verdict as V                             # noqa: E402
from check import RULE, THIN, Lab, add_lab_args  # noqa: E402


def main():
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description="DD105-B: tests x seeds")
    add_lab_args(ap)
    ap.add_argument("--tests", required=True)
    ap.add_argument("--seeds", required=True)
    ap.add_argument("--bug", default="")
    a = ap.parse_args()
    lab = Lab(a)
    tests, seeds = a.tests.split(), a.seeds.split()
    if not tests:
        sys.exit("No tests: set TESTS in the lab's Makefile, or TEST.")
    expect = "fail" if a.bug else "pass"

    print(RULE)
    print(f" REGRESS   {len(tests)} test{'s' if len(tests) != 1 else ''} x "
          f"{len(seeds)} seed{'s' if len(seeds) != 1 else ''}"
          + (f"   with BUG={a.bug}" if a.bug else "") + (f"   {lab.plusargs}" if lab.plusargs else ""))
    print(RULE)
    root = os.path.join(lab.build_dir, "runs", "regress")
    runs, tally = [], {}
    for t in tests:
        for s in seeds:
            name = f"{t}-s{s}" + (f"-{a.bug}" if a.bug else "")
            r = lab.run(name, a.bug or None, os.path.join(root, name), test=t, seed=s)
            mark = r.mark(expect)
            tally[mark] = tally.get(mark, 0) + 1
            runs.append((t, s, r, mark))
            print(f"  {mark:>6}  {t:<28} seed {s:<6} {r.summary():<28} {r.seconds:6.1f}s")
    print(THIN)
    print("  " + ", ".join(f"{n} {m}" for m, n in sorted(tally.items())) + f"  ({len(runs)} runs)")

    bad = [(t, s, r, m) for t, s, r, m in runs if m not in ("ok", "caught")]
    for t, s, r, m in bad[:10]:
        why = r.problems[0][1] if r.problems else (r.first_fired() or "nothing fired")
        print(f"   {m} {t} seed {s}: {why[:90]}")
        print(f"      make run TEST={t} SEED={s}" + (f" BUG={a.bug}" if a.bug else ""))
    if len(bad) > 10:
        print(f"   ... and {len(bad) - 10} more")
    print(RULE)

    covmerge.report([r.run_dir for _, _, r, _ in runs],
                    os.path.join(lab.build_dir, "coverage", "regress"), lab.python_bin)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
