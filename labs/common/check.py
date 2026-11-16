"""
DD105-B: the verdict. DD105-A's check.py, run on cocotb + pyuvm.

    make check                 your test vs. the golden design and one bug
    make check BUG=B07         pick which bug
    make check-all             your test vs. every bug in the lab's BUG_LIST

────────────────────────────────────────────────────────────────────────────
WHY THIS EXISTS
────────────────────────────────────────────────────────────────────────────
A pyuvm test that sends nothing passes. So does one that sends the same item
two thousand times, and one whose scoreboard logged a thousand mismatches with
self.logger.error() and never failed the test. They pass on the golden design
and on every broken one, which means they distinguish nothing.

So "my test passes" is half a result. The verdict is two-sided:

    it must PASS on the golden design     or you are testing the wrong thing
    it must FAIL on the broken one        or you are not testing anything

and "FAIL" has to mean a CHECK FIRED. A run that raised NameError or
UVMFatalError, hit the time limit or crashed checked nothing; verdict.py marks
it BROKEN, and BROKEN is never a catch.

────────────────────────────────────────────────────────────────────────────
ONE BUILD
────────────────────────────────────────────────────────────────────────────
The course compiles every planted bug into the design behind a run-time
switch. The golden run has no +BUG; a bug run has +BUG=<id>, which reaches the
design's $value$plusargs through the simulator's command line. Both runs, and
every run of check-all, use the same simulator, built once at the start
(NOBUILD=1 after that, so nothing can rebuild halfway through). A lab whose
design prints a line for the bug it switched on sets BUG_CONFIRM, and
verdict.py then refuses a bug run without that line.

A test that reads +BUG could fail on every bug without checking anything, so
the check refuses a testbench that reads it.

────────────────────────────────────────────────────────────────────────────
THE REGISTER MODEL FIRST
────────────────────────────────────────────────────────────────────────────
pyuvm raises AssertionError for a register model that is wrong (two fields
that overlap), and an AssertionError is how a check says the design is wrong.
So in a lab that sets REG_MODEL, the model is built on its own, outside the
simulator (regcheck.py), before any run is graded, and a model that doesn't
build stops the check with its own message.
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import verdict as V                             # noqa: E402

RULE = "=" * 72
THIN = "-" * 72

# A testbench that asks which bug is on: reads +BUG from cocotb.plusargs, or
# reads the design's bug-switch package (router_bug_pkg::bug_id), from Python
# or from a bound SystemVerilog file. Static, so it only stops the obvious
# version; the course states the rest as an honour system.
READS_BUG = re.compile(
    r"""plusargs\s*(?:\.get\s*\(\s*|\[\s*)["']\+?BUG["']"""
    r"""|["']\+?BUG["']\s+(?:not\s+)?in\s+(?:cocotb\.)?plusargs"""
    r"""|\$(?:test|value)\$plusargs\s*\(\s*"\+?BUG"""
    r"""|\b\w+_bug_pkg\b""")
TB_SUFFIXES = (".py", ".sv", ".svh", ".v")


class Lab:
    """One lab, driven through its own Makefile, so pyuvm.mk stays the only
    place a simulation is started."""

    def __init__(self, a):
        self.makefile = os.path.abspath(a.makefile)
        self.lab_dir = os.path.dirname(self.makefile)
        self.build_dir = os.path.abspath(a.build_dir)
        self.test = a.test
        self.seed = a.seed
        self.plusargs = a.plusargs
        self.bugs = a.bugs.split()
        self.pool = a.pool.split() or list(self.bugs)
        self.tb_dirs = a.tb_dirs.split()
        self.timeout = int(a.timeout)
        self.verbose = a.verbose
        self.confirm = a.bug_confirm or None
        self.base_test = str(a.base_test) == "1"
        self.reg_model = a.reg_model
        self.python_bin = a.python_bin
        self.catalogue, order = {}, []
        if a.catalogue:
            path = a.catalogue if os.path.isabs(a.catalogue) else os.path.join(self.lab_dir, a.catalogue)
            self.catalogue, order = load_catalogue(path)
            if not self.bugs:
                self.bugs = order
            if not self.pool:
                self.pool = list(self.bugs)

    def make(self, *args, quiet=True, timeout=None):
        cmd = ["make", "--no-print-directory", "-f", self.makefile, "-C", self.lab_dir]
        if quiet:
            cmd.append("-s")
        cmd += list(args)
        if quiet:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return p.returncode, p.stdout + p.stderr
        p = subprocess.run(cmd, timeout=timeout)
        return p.returncode, ""

    def build(self):
        """Build (or confirm) the simulator, with make's output on the terminal."""
        rc, _ = self.make("build", quiet=False)
        return rc == 0

    def run(self, label, bug, run_dir, test=None, seed=None):
        """One run, quiet, read back through verdict.py."""
        args = ["_run", "NOBUILD=1", f"RUN_DIR={run_dir}",
                f"TEST={test or self.test}", f"SEED={seed or self.seed}",
                f"BUG={bug or ''}", f"PLUSARGS={self.plusargs}",
                f"RUN_TIMEOUT={self.timeout}"]
        try:
            rc, out = self.make(*args, timeout=self.timeout + 60)
        except subprocess.TimeoutExpired:
            out = "make _run did not return"
        r = V.read_run(run_dir, expect_bug=bug or None, label=label, confirm=self.confirm,
                       base_test=self.base_test)
        if not r.launched:
            r.log = out
        return r

    def name(self, bug):
        n = self.catalogue.get(bug, {}).get("name", "")
        if not n or n == bug:
            return bug
        return n if n.startswith(bug) else f"{bug}_{n}"

    def about(self, bug, key):
        return self.catalogue.get(bug, {}).get(key, "")

    def tb_files(self):
        """The testbench's files: Python and SystemVerilog in the lab's PY_DIRS."""
        out = []
        for d in self.tb_dirs:
            for root, dirs, files in os.walk(d):
                dirs[:] = [x for x in dirs if x not in ("__pycache__", "build")]
                out += [os.path.join(root, f) for f in sorted(files) if f.endswith(TB_SUFFIXES)]
        return out

    def reads_bug(self):
        """(file, line number, text) for every place the testbench reads +BUG."""
        hits = []
        for f in self.tb_files():
            try:
                lines = open(f, errors="replace").read().splitlines()
            except OSError:
                continue
            comment = "#" if f.endswith(".py") else "//"
            for i, l in enumerate(lines, 1):
                if READS_BUG.search(l.split(comment)[0]):
                    hits.append((os.path.relpath(f, self.lab_dir), i, l.strip()))
        return hits

    def regcheck(self):
        """Build the register model outside the simulator: (ok, what it printed)."""
        if not self.reg_model:
            return True, ""
        cmd = [self.python_bin, os.path.join(HERE, "regcheck.py"), "--lab-dir", self.lab_dir,
               "--model", self.reg_model,
               "--py-path", ":".join(self.tb_dirs + [os.path.join(HERE, "py")])]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return p.returncode == 0, (p.stdout + p.stderr).rstrip()

    def rel(self, path):
        return os.path.relpath(path, self.lab_dir)


def load_catalogue(path):
    """({id: {name, tier, hides_behind, teaches, ...}}, ids in order) from a
    JSON file, or from a Python file with a BUGS dict (and ids(), if it has
    one), such as the router's labs/common/bugs.py."""
    if path.endswith(".py"):
        spec = importlib.util.spec_from_file_location("dd105_lab_bugs", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        bugs = dict(mod.BUGS)
        order = list(mod.ids()) if hasattr(mod, "ids") else list(bugs)
        return bugs, order
    with open(path) as f:
        bugs = json.load(f)
    return bugs, list(bugs)


# ── shared pieces of the report ──────────────────────────────────────────────

def row(mark, label, run):
    return f"  {mark:>6}  {label:<40} {run.summary():<28} {run.seconds:6.1f}s"


def refuse_reading_bug(lab, hits):
    print(" VERDICT: FAIL -- your testbench reads which bug is on.")
    for f, n, text in hits[:5]:
        print(f"   {f}:{n}: {text[:80]}")
    print("")
    print("   A test that asks which bug is on can fail on every bug without")
    print("   checking anything. Take it out; the grade needs a test that finds")
    print("   the bug from what the design does.")
    print(RULE)


def build_or_say_so(lab):
    if not lab.build():
        print(RULE)
        print(f"  {'BROKEN':>6}  the build")
        print(THIN)
        print(" VERDICT: FAIL -- the simulator did not build, so nothing ran.")
        print(f"   The errors are above; the whole log is {lab.rel(os.path.join(lab.build_dir, 'build.log'))}.")
        print("   A build that fails is not a test that fails: fix it, then ask again.")
        print(RULE)
        return False
    ok, out = lab.regcheck()
    if ok:
        return True
    print(RULE)
    print(f"  {'BROKEN':>6}  the register model ({lab.reg_model})")
    print(THIN)
    for l in out.splitlines()[-8:]:
        print(f"   {l}")
    print(" VERDICT: FAIL -- the register model doesn't build, so nothing was graded.")
    print("   pyuvm raises AssertionError for a model that is wrong, and a run with")
    print("   one would read as a caught bug. Fix the model, then ask again:")
    print("   `make regcheck` builds it on its own, in a second.")
    print(RULE)
    return False


def broken_verdict(run, where):
    print(f" VERDICT: FAIL -- the run on {where} is BROKEN, so it checked nothing.")
    for l in V.explain(run):
        print(l)
    print(f"   Log: {run.run_dir}/run.log")


def golden_first(lab, good):
    """Shared by check and check-all: the golden row must be a clean pass."""
    print(row(good.mark("pass"), "the golden design", good))
    V.report_problems(good)
    if good.broken:
        print(THIN)
        broken_verdict(good, "the golden design")
        print(RULE)
        return False
    if not good.passed:
        print(THIN)
        print(" VERDICT: FAIL -- your test does not pass the GOLDEN design.")
        print("   A check fired on the design with no bug in it. Either the check")
        print("   expects the wrong thing, or the stimulus breaks a rule of the")
        print("   interface. Fix that first: `make run` shows the whole log.")
        print(f"   Log: {good.run_dir}/run.log")
        print(RULE)
        return False
    return True


# ── make check ───────────────────────────────────────────────────────────────

def check_one(lab, bug):
    print(RULE)
    print(f" CHECK   test: {lab.test}   seed: {lab.seed}   bug: {lab.name(bug)}")
    print(RULE)
    hits = lab.reads_bug()
    if hits:
        refuse_reading_bug(lab, hits)
        return False
    if not build_or_say_so(lab):
        return False
    print(RULE)

    grade = os.path.join(lab.build_dir, "grade")
    good = lab.run("the golden design", None, os.path.join(grade, "golden"))
    if not golden_first(lab, good):
        return False

    bad = lab.run(lab.name(bug), bug, os.path.join(grade, bug))
    print(row(bad.mark("fail"), lab.name(bug), bad))
    V.report_problems(bad)
    print(THIN)
    ok = False
    if bad.broken:
        broken_verdict(bad, lab.name(bug))
        print("")
        print("   The same test ran clean on the golden design, so whatever broke")
        print("   is on a path only a wrong answer reaches, usually the code that")
        print("   reports a mismatch. That path has to work too.")
    elif bad.caught:
        ok = True
        print(" VERDICT: PASS")
        print(f"   Your test passes the golden design, and on {lab.name(bug)} a check FIRED:")
        for _, line in bad.fired[:2]:
            print(f"       {line[:96]}")
        if lab.about(bug, "teaches"):
            print(f"   That bug teaches: {lab.about(bug, 'teaches')}")
    else:
        print(f" VERDICT: FAIL -- your test passes {lab.name(bug)} too.")
        print("   A test that passes on a broken design is not testing it. Did it")
        print("   send anything, and did the stimulus really vary? The coverage")
        print("   report (`make cov`) shows what it reached.")
        if lab.about(bug, "hides_behind"):
            print(f"   That bug hides behind: {lab.about(bug, 'hides_behind')}")
    print(f"   Logs: {lab.rel(good.run_dir)}/run.log, {lab.rel(bad.run_dir)}/run.log")
    print(RULE)
    if lab.verbose:
        print(bad.log)
    return ok


# ── make check-all ───────────────────────────────────────────────────────────

def check_all(lab):
    print(RULE)
    print(f" CHECK-ALL   test: {lab.test}   seed: {lab.seed}   {len(lab.bugs)} bugs")
    print(RULE)
    hits = lab.reads_bug()
    if hits:
        refuse_reading_bug(lab, hits)
        return False
    if not build_or_say_so(lab):
        return False
    print(RULE)

    grade = os.path.join(lab.build_dir, "grade")
    good = lab.run("the golden design", None, os.path.join(grade, "golden"))
    if not golden_first(lab, good):
        return False
    print(THIN)

    caught, missed, broken = [], [], []
    for bug in lab.bugs:
        r = lab.run(lab.name(bug), bug, os.path.join(grade, bug))
        mark = r.mark("fail")
        tier = lab.about(bug, "tier")
        label = (f"tier {tier}  " if tier != "" else "") + lab.name(bug)
        print(row(mark, label, r))
        if r.broken:
            broken.append((bug, r))
            V.report_problems(r, limit=1)
        elif r.caught:
            caught.append(bug)
        else:
            missed.append(bug)
    print(THIN)

    # A BROKEN run is not a count of anything, so print no count. "12 of 13
    # caught" is a claim about the design; a crash is a claim about the test.
    if broken:
        print(f" NO COUNT. {len(broken)} of the {len(lab.bugs)} bug runs are BROKEN:")
        for bug, r in broken:
            print(f"   {lab.name(bug)}: {r.problems[0][1][:90]}")
        print("")
        print(" A BROKEN run checked nothing, on that bug or any other, so there is")
        print(" no score until every run ends cleanly. `make run BUG=<id>` shows one")
        print(" in full.")
        print(RULE)
        return False
    print(f" {len(caught)} of {len(lab.bugs)} caught.")
    if missed:
        print(" Still hiding from this test:")
        for b in missed:
            print(f"   {lab.name(b)}")
            if lab.about(b, "hides_behind"):
                print(f"      hides behind: {lab.about(b, 'hides_behind')}")
    else:
        print(" Every bug in the list, each one caught by a check that fired.")
    print(RULE)
    return not missed


def add_lab_args(ap):
    ap.add_argument("--makefile", required=True, help="the lab's Makefile")
    ap.add_argument("--build-dir", required=True)
    ap.add_argument("--test", required=True, help="TEST: the test class")
    ap.add_argument("--seed", default="1")
    ap.add_argument("--plusargs", default="")
    ap.add_argument("--bugs", default="", help="the lab's BUG_LIST")
    ap.add_argument("--catalogue", default="", help="JSON: id -> name, tier, hides_behind, teaches")
    ap.add_argument("--pool", default="", help="the hunt's pool (default: every bug)")
    ap.add_argument("--tb-dirs", default="", help="testbench folders, scanned for +BUG")
    ap.add_argument("--timeout", default="300", help="seconds per run")
    ap.add_argument("--bug-confirm", default="", help="the line the design prints for a bug, with {id}")
    ap.add_argument("--base-test", default="1", help="1: a pass needs BaseTest's closing line")
    ap.add_argument("--reg-model", default="", help="REG_MODEL: <file>:<class>, built before any run")
    ap.add_argument("--python-bin", default=sys.executable, help="the simulator's Python")
    ap.add_argument("--verbose", action="store_true")


def main():
    # make's output goes straight to the terminal; keep ours in step with it
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description="DD105-B: pass on the golden design, fail on a bug")
    add_lab_args(ap)
    ap.add_argument("--bug", default="", help="which bug (default: the first in BUG_LIST)")
    ap.add_argument("--all", action="store_true", help="every bug in BUG_LIST")
    a = ap.parse_args()
    lab = Lab(a)
    if not lab.test:
        sys.exit("No test to check: set TEST, or TESTS in the lab's Makefile.")
    if not lab.bugs:
        sys.exit("This lab has no BUG_LIST, so there is nothing to check against.")
    if a.all:
        return 0 if check_all(lab) else 1
    bug = a.bug or lab.bugs[0]
    if bug not in lab.bugs:
        sys.exit(f"BUG={bug} is not one of this lab's bugs: {' '.join(lab.bugs)}")
    return 0 if check_one(lab, bug) else 1


if __name__ == "__main__":
    sys.exit(main())
