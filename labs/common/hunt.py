"""
DD105-B: the bug hunt. DD105-A's hunt.py, run on cocotb + pyuvm.

    make new        deal a mystery bug. You are not told which one.
    make hunt       your test against it: the loop you live in (VERBOSE=1: the log)
    make verdict    the grade
    make reveal     give up, and be told the name

────────────────────────────────────────────────────────────────────────────
THE GRADE HAS TWO ROWS
────────────────────────────────────────────────────────────────────────────

    1.  your test on the GOLDEN design     must PASS
    2.  your test on the MYSTERY bug       must FAIL, with a check that fired

Both rows run the same simulator, built once: the golden design has no +BUG,
the mystery run has +BUG=<the sealed id>. There is no design to edit and fix
here, as there was in DD104, because the bugs are switches in one build. The
deliverable is row 2: a test that tells this bug from a correct design.

Row 2 is green only if a CHECK FIRED. A run that raised UVMFatalError, crashed
or timed out checked nothing, so it is marked BROKEN and never `caught`
(verdict.py decides). `make hunt` and `make verdict` print a summary; with
VERBOSE=1 they also print the simulator's log.

The sealed id is in .hunt in the lab folder, base64'd, and the bug id is
blanked out of the logs this script writes. Decoding it costs you the lab.
It is an honour system, and it is stated as one.
"""

import argparse
import base64
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import verdict as V                             # noqa: E402
from check import (Lab, RULE, THIN, add_lab_args, broken_verdict,  # noqa: E402
                   build_or_say_so, refuse_reading_bug, row)

SEALED = "<sealed>"


def seal_path(lab):
    return os.path.join(lab.lab_dir, ".hunt")


def seal(lab, bug):
    with open(seal_path(lab), "w") as f:
        f.write("# DD105-B: which bug you were dealt, base64'd.\n"
                "# Decoding this costs you the lab. `make reveal` does it for you\n"
                "# when you have had enough, and says so on the way past.\n")
        f.write(base64.b64encode(bug.encode()).decode() + "\n")


def unseal(lab):
    try:
        for line in open(seal_path(lab)):
            line = line.strip()
            if line and not line.startswith("#"):
                return base64.b64decode(line).decode()
    except OSError:
        pass
    return None


def redact(run, bug):
    """Blank the bug id out of the run's files and of what we print."""
    pat = re.compile(re.escape(bug))
    run.log = pat.sub(SEALED, run.log)
    run.fired = [(k, pat.sub(SEALED, l)) for k, l in run.fired]
    run.problems = [(k, pat.sub(SEALED, l)) for k, l in run.problems]
    for name in ("run.log", "cmd"):
        p = os.path.join(run.run_dir, name)
        if os.path.exists(p):
            text = open(p, errors="replace").read()
            with open(p, "w") as f:
                f.write(pat.sub(SEALED, text))


def deal(lab, pick=None):
    if not lab.pool:
        print("This lab has no HUNT_POOL or BUG_LIST, so there is nothing to deal.")
        return 1
    bug = pick or random.choice(lab.pool)
    if bug not in lab.pool:
        print(f"{bug} is not in this lab's pool.")
        return 1
    seal(lab, bug)
    print(RULE)
    print(" A MYSTERY BUG")
    print(RULE)
    print(f" One of {len(lab.pool)} planted bugs is now sealed in .hunt. `make hunt`")
    print(" and `make verdict` run your test with it switched on, in the same")
    print(" simulator as the golden design.")
    print("")
    print(" You are not told which. Don't read the bug catalogue or decode .hunt:")
    print(" it works, it takes a minute, and it skips the lab. The skill here is")
    print(" finding a bug you can't diff against a known-good design.")
    print("")
    print(" The loop:")
    print("   make hunt              your test against the mystery bug")
    print("   make hunt VERBOSE=1    the same, with the simulator's log")
    print("   make verdict           the grade")
    print("   make new               deal a different one")
    print(RULE)
    return 0


def hunt(lab):
    bug = unseal(lab)
    if bug is None:
        print("There is no mystery bug yet. Run `make new` first.")
        return 1
    print(RULE)
    print(f" HUNT   test: {lab.test}   seed: {lab.seed}   bug: {SEALED}")
    print(RULE)
    hits = lab.reads_bug()
    if hits:
        refuse_reading_bug(lab, hits)
        return 1
    if not build_or_say_so(lab):
        return 1
    print(RULE)
    r = lab.run("the mystery bug", bug, os.path.join(lab.build_dir, "hunt", "mystery"))
    redact(r, bug)
    if lab.verbose:
        print(r.log.rstrip())
        print(THIN)
    print(row(r.mark("fail") if r.mark("fail") != "MISSED" else "quiet", "the mystery bug", r))
    V.report_problems(r)
    print(THIN)
    if r.broken:
        print(" This run is BROKEN, so it says nothing about the mystery bug:")
        for l in V.explain(r):
            print(l)
    elif r.caught:
        print(" Something in this design disagrees with your test. That is not yet")
        print(" a verdict: your test could be wrong. `make verdict` runs it against")
        print(" the golden design too, which settles it.")
    else:
        print(" Nothing your test drives tells this design from a correct one. The")
        print(" bug is in there; your stimulus or your checks have not reached it.")
        print(" `make cov` shows what the stimulus covered.")
    if not lab.verbose:
        print("")
        print(" To read the simulator's log as well: make hunt VERBOSE=1")
    print(RULE)
    return 0


def verdict(lab):
    bug = unseal(lab)
    if bug is None:
        print("There is no mystery bug yet. Run `make new` first.")
        return 1
    print(RULE)
    print(f" VERDICT   test: {lab.test}   seed: {lab.seed}")
    print(RULE)
    hits = lab.reads_bug()
    if hits:
        refuse_reading_bug(lab, hits)
        return 1
    if not build_or_say_so(lab):
        return 1
    print(RULE)

    good = lab.run("the golden design", None, os.path.join(lab.build_dir, "hunt", "golden"))
    if lab.verbose:
        print(good.log.rstrip())
        print(THIN)
    print(row(good.mark("pass"), "1. the golden design  must PASS", good))
    V.report_problems(good)
    if good.broken:
        print(THIN)
        broken_verdict(good, "the golden design")
        print(RULE)
        return 1
    if not good.passed:
        print(THIN)
        print(" VERDICT: FAIL -- row 1. Your test does not pass the GOLDEN design.")
        print("   Nothing else means anything until it does: a test that fails on a")
        print("   correct design is telling you about itself.")
        print(RULE)
        return 1

    bad = lab.run("the mystery bug", bug, os.path.join(lab.build_dir, "hunt", "mystery"))
    redact(bad, bug)
    if lab.verbose:
        print(bad.log.rstrip())
        print(THIN)
    print(row(bad.mark("fail"), "2. the mystery bug    must FAIL", bad))
    V.report_problems(bad)
    print(THIN)
    if bad.broken:
        broken_verdict(bad, "the mystery bug")
        print("")
        print("   The same test ran clean on the golden design, so whatever broke is")
        print("   on a path only a wrong answer reaches. That path has to work too.")
        print(RULE)
        return 1
    if not bad.caught:
        print(" VERDICT: FAIL -- row 2. Your test can't tell the mystery bug from a")
        print("   correct design. `make hunt` is the loop: widen the stimulus or add")
        print("   the check, and run it again.")
        print(RULE)
        return 1
    print(" VERDICT: PASS")
    print(f"   The bug was {lab.name(bug)}.")
    if lab.about(bug, "hides_behind"):
        print(f"   It hides behind: {lab.about(bug, 'hides_behind')}")
    if lab.about(bug, "teaches"):
        print(f"   It teaches: {lab.about(bug, 'teaches')}")
    print("")
    print("   Row 2 is the part worth keeping. Commit that test.")
    print(RULE)
    return 0


def reveal(lab):
    bug = unseal(lab)
    if bug is None:
        print("There is no mystery bug yet. Run `make new` first.")
        return 1
    print(RULE)
    print(" GIVING UP")
    print(RULE)
    print(f" The mystery bug is {lab.name(bug)}.")
    if lab.about(bug, "hides_behind"):
        print(f" It hides behind: {lab.about(bug, 'hides_behind')}")
    print("")
    print(" Knowing its name is not the deliverable. Write the test that catches")
    print(" it: `make verdict` still wants row 2 to fire.")
    print(RULE)
    return 0


def main():
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description="DD105-B: the bug hunt")
    ap.add_argument("mode", choices=["new", "hunt", "verdict", "reveal"])
    add_lab_args(ap)
    ap.add_argument("--pick", default=None, help="deal this bug instead of a random one")
    a = ap.parse_args()
    lab = Lab(a)
    if a.mode == "new":
        return deal(lab, a.pick)
    if a.mode == "reveal":
        return reveal(lab)
    if not lab.test:
        sys.exit("No test to run: set TEST, or TESTS in the lab's Makefile.")
    return hunt(lab) if a.mode == "hunt" else verdict(lab)


if __name__ == "__main__":
    sys.exit(main())
