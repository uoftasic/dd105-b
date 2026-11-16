"""
DD105-B: does the grader actually grade?

    cd labs/common/selftest && make            the fast parts, no simulator
    cd labs/common/selftest && make FULL=1     ... and every grader, for real
    cd labs/common/selftest && make capture    re-record logs/ from real runs

DD104's rule, and the reason this file exists:

    A grader that says PASS when it did nothing is worse than no grader at all.

So the graders are themselves tested, by pointing them at tests that are
known to be bad in one specific way and reading what they say. The fixture
tests are in alu/tb/test_st.py; each names the verdict it must provoke. This
is DD105-A's selftest.py with pyuvm fixtures and DD105-B's verdict classes.

────────────────────────────────────────────────────────────────────────────
PART 1 -- the classifier, against real runs, with no simulator
────────────────────────────────────────────────────────────────────────────
logs/<scenario>/ holds run.log, results.xml and exit_status from a real run
of each scenario below in the course image (`make capture` re-records them).
Each is read through verdict.py and must land in the class the table says.

────────────────────────────────────────────────────────────────────────────
PART 2 -- the graders, end to end (FULL=1)
────────────────────────────────────────────────────────────────────────────
Builds alu/ once (seconds), then runs make check, check-all, the hunt,
regress, seeds, waves, regcheck and the register-model guard with the
fixture tests, and reads what they print and their exit status.

────────────────────────────────────────────────────────────────────────────
PART 3 -- every grader reads the rule from verdict.py
────────────────────────────────────────────────────────────────────────────
No grader may carry its own copy of the classification.
"""

import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMMON = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(COMMON, "..", ".."))
ALU = os.path.join(HERE, "alu")
LOGS = os.path.join(HERE, "logs")
sys.path.insert(0, COMMON)

import verdict as V                              # noqa: E402

RULE = "=" * 72
THIN = "-" * 72

# alu/'s design prints this line for a bug, and alu/Makefile sets BUG_CONFIRM
# to it. A lab's design need not print anything.
CONFIRM = "DD105-BUG: {id} enabled"


class Scn:
    """One run of alu/ through `make _run`. make_args are extra make variables."""

    def __init__(self, name, test, bug="", make_args=(), timeout=60, read_bug=None,
                 confirm=CONFIRM, kind="pass", key=None, why=""):
        self.name, self.test, self.bug, self.make_args = name, test, bug, list(make_args)
        self.timeout = timeout
        self.read_bug = bug if read_bug is None else read_bug   # what verdict.py is told
        self.confirm = confirm
        self.kind, self.key, self.why = kind, key, why


SCENARIOS = [
    Scn("good_golden", "StGoodTest", kind="pass",
        why="the reference test on the golden design"),
    Scn("good_B01", "StGoodTest", "B01", kind="caught", key="check",
        why="a logged MISMATCH, turned into AssertionError by BaseTest, is a check"),
    Scn("good_B02", "StGoodTest", "B02", kind="caught", key="assertion",
        why="a failed assertion bound to the design is a check (u_sva.n_fail)"),
    Scn("good_B03", "StGoodTest", "B03", kind="pass",
        why="a bug the stimulus never reaches: a clean pass, so MISSED"),
    Scn("empty_B01", "StEmptyTest", "B01", kind="pass",
        why="sends nothing: passes on a broken design, so MISSED"),
    Scn("fixed_B01", "StFixedTest", "B01", kind="pass",
        why="one item, repeated: passes on a broken design, so MISSED"),
    Scn("plain_golden", "StPlainTest", kind="broken", key="no-base-test",
        why="uvm_test, not BaseTest: a logged error would fail nothing"),
    Scn("plain_B01", "StPlainTest", "B01", kind="broken", key="no-base-test",
        why="uvm_test on a broken design: MISMATCH logged, test passed, not a catch"),
    Scn("assert_B01", "StAssertTest", "B01", kind="caught", key="AssertionError",
        why="a plain assert in the scoreboard is a check, as in DD104"),
    Scn("crash_golden", "StCrashTest", kind="pass",
        why="the crash path is never reached on the golden design"),
    Scn("crash_B01", "StCrashTest", "B01", kind="broken", key="NameError",
        why="NameError in the mismatch path: a crash, not a catch (DD104's bug)"),
    Scn("fatal_check_B01", "StFatalCheckTest", "B01", kind="broken", key="UVMFatalError",
        why="UVMFatalError used as a check"),
    Scn("config_missing", "StConfigTest", kind="broken", key="UVMConfigItemNotFound",
        why="a ConfigDB name nobody set is configuration, not a check"),
    Scn("hang_timeout", "StHangTest", make_args=["RUN_TIMEOUT=10"], timeout=10, kind="broken",
        key="timeout", why="stopped by RUN_TIMEOUT"),
    Scn("watchdog_golden", "StWatchdogTest", kind="caught", key="SimTimeoutError",
        why="SimTimeoutError is a check, as in DD104: on the golden design, a FAIL"),
    Scn("nosuper", "StNoSuperTest", kind="broken", key="BaseTestNotSetUp",
        why="the error counter was never installed"),
    Scn("final_nosuper_B01", "StFinalNoSuperTest", "B01", kind="broken", key="no-base-test",
        why="final_phase overridden without super(): errors logged, nothing failed"),
    Scn("regmodel_alone", "StRegModelTest", kind="caught", key="overlap",
        why="pyuvm's AssertionError for a bad register model reads as a check here; "
            "check.py's REG_MODEL guard is what stops it (part 2)"),
    Scn("no_such_test", "NoSuchTest", kind="broken", key="skipped",
        why="a TEST that doesn't exist: every test skipped, exit status 0"),
    Scn("import_error", "StGoodTest", make_args=["TEST_MODULES=test_broken"], kind="broken",
        key="noresults", why="a test module that doesn't import: no results.xml"),
    Scn("unknown_bug", "StGoodTest", "B99", kind="broken", key="bug-id",
        why="the design refuses a bug id it does not know ($fatal)"),
    Scn("limit_B02", "StGoodTest", "B02", make_args=["ERROR_LIMIT=1"], kind="caught",
        key="assertion", why="Verilator stopped at its error limit after an assertion: caught"),
    # The bug-switch contract, using real logs read the wrong way round.
    Scn("good_golden", "StGoodTest", read_bug="B01", kind="broken", key="bug-unconfirmed",
        why="BUG_CONFIRM set: asked for B01, and the design never said it was on"),
    Scn("good_B01", "StGoodTest", "B01", read_bug="", kind="broken", key="bug-on-golden",
        why="BUG_CONFIRM set: a 'golden' run in which the design says a bug is on"),
    Scn("good_golden", "StGoodTest", read_bug="B01", confirm=None, kind="pass",
        why="no BUG_CONFIRM (the router's case): the graders don't need the line"),
]


def keys(run):
    """Every reason a run is BROKEN, or every kind of check that fired."""
    return [k for k, _ in (run.problems or run.fired)]


def matches(run, s):
    """The run is in the expected class, and the expected reason is among its
    reasons, or in the text of one of them."""
    if run.kind != s.kind:
        return False
    texts = [l for _, l in (run.problems or run.fired)]
    return s.key is None or s.key in keys(run) or any(s.key in l for l in texts)


def part1():
    print(RULE)
    print(" PART 1   verdict.py against real runs (logs/, recorded in the course image)")
    print(RULE)
    bad = 0
    for s in SCENARIOS:
        d = os.path.join(LOGS, s.name)
        if not os.path.exists(os.path.join(d, "run.log")):
            print(f"  {'WRONG':>6}  {s.name}: logs/{s.name}/run.log is missing (make capture)")
            bad += 1
            continue
        r = V.read_run(d, expect_bug=s.read_bug or None, confirm=s.confirm)
        ok = matches(r, s)
        bad += not ok
        tag = f"{s.name}" + (f" read as +BUG={s.read_bug}" if s.read_bug != s.bug else "") \
            + (" no BUG_CONFIRM" if s.confirm is None else "")
        shown = s.key if ok and s.key else (keys(r)[0] if keys(r) else "")
        print(f"  {'ok' if ok else 'WRONG':>6}  {tag:<38} {r.kind:<7} {shown:<16}")
        print(f"          {s.why}")
        if not ok:
            print(f"          EXPECTED {s.kind}/{s.key}, got {r.kind}/{keys(r)}")
            for k, l in (r.problems or r.fired)[:3]:
                print(f"            {k}: {l[:90]}")
    print(THIN)
    print(f" {len(SCENARIOS) - bad} of {len(SCENARIOS)} classifier cases correct.")
    print(RULE)
    return bad == 0


# ─────────────────────────────────────────────────────────────────────────────
# Running the selftest design
# ─────────────────────────────────────────────────────────────────────────────

def make(*args, timeout=900):
    cmd = ["make", "--no-print-directory", "-C", ALU] + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def run_scenario(s, run_dir):
    make("_run", "NOBUILD=1", f"RUN_DIR={run_dir}", f"TEST={s.test}", "SEED=1", f"BUG={s.bug}",
         *s.make_args, timeout=s.timeout + 60)


def capture():
    """Re-record logs/ from real runs. Run this in the course image after an
    image or library change, then read the diff before committing it."""
    print(RULE)
    print(" CAPTURE   re-recording logs/ from real runs of alu/")
    print(RULE)
    rc, out = make("build")
    if rc != 0:
        print(out[-3000:])
        return False
    done = set()
    for s in SCENARIOS:
        if s.name in done:
            continue
        done.add(s.name)
        d = os.path.join(LOGS, s.name)
        shutil.rmtree(d, ignore_errors=True)
        tmp = os.path.join(ALU, "build", "capture", s.name)
        shutil.rmtree(tmp, ignore_errors=True)
        run_scenario(s, tmp)
        os.makedirs(d, exist_ok=True)
        for f in ("run.log", "exit_status", "results.xml"):
            src = os.path.join(tmp, f)
            if os.path.exists(src):
                text = open(src, errors="replace").read()
                # Make the logs independent of where the clone was mounted.
                text = text.replace(REPO + "/", "")
                open(os.path.join(d, f), "w").write(text)
        rc_text = open(os.path.join(d, "exit_status")).read().strip()
        size = len(open(os.path.join(d, "run.log")).read())
        has = "results.xml" if os.path.exists(os.path.join(d, "results.xml")) else "no results.xml"
        print(f"  {s.name:<22} exit {rc_text:>3}   {size:>6} bytes   {has}")
    print(RULE)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# PART 2 -- the graders, end to end
# ─────────────────────────────────────────────────────────────────────────────

class Expect:
    """Run a make target in alu/, then read what it printed."""

    def __init__(self, label, args, must_say, must_not_say=("VERDICT: PASS",),
                 exit_zero=False, then=None):
        self.label, self.args = label, args
        self.must_say, self.must_not_say = must_say, must_not_say
        self.exit_zero, self.then = exit_zero, then

    def check(self):
        code, out = make(*self.args)
        problems = [f'did not say "{s}"' for s in self.must_say if s not in out]
        problems += [f'said "{s}" and must not' for s in self.must_not_say if s in out]
        if self.exit_zero and code != 0:
            problems.append(f"exited {code}, expected 0")
        if not self.exit_zero and code == 0:
            problems.append("exited 0")
        if self.then:
            problems += self.then()
        return problems, out


def has_file(path):
    return lambda: [] if os.path.exists(path) else [f"{path} is missing"]


def venv_python():
    """The course venv's python, if the venv exists (make venv)."""
    rc, out = make("help")
    m = re.search(r"PYTHON_BIN=(\S+)", out)
    return m.group(1) if m and "/bin/python" in m.group(1) and ".venv" in m.group(1) else None


def cases(venv):
    T = "TEST="
    regress_says = ["4 ok"] + (["COVERAGE", "st.op"] if venv else [])
    return [
        Expect("reads +BUG and st_bug_pkg: refused before anything is built",
               ["check", T + "StCheatTest", "PY_DIRS=tb cheat"],
               ["reads which bug is on", "cheat/test_cheat.py:12", "cheat/test_cheat.py:14"],
               must_not_say=("VERDICT: PASS", " BUILD ")),
        Expect("a build that fails",
               ["check", T + "StGoodTest", "SVA_SRCS=tb/st_sva.sv broken/st_syntax_error.sv",
                f"BUILD_DIR={ALU}/build-broken"],
               ["BUILD FAILED", "BROKEN", "did not build"]),
        Expect("a register model whose fields overlap: refused before any run",
               ["check", T + "StRegModelTest", "REG_MODEL=tb/st_regs.py:OverlapRegs"],
               ["the register model", "doesn't build", "overlap"],
               must_not_say=("VERDICT: PASS", "the golden design")),
        Expect("make regcheck: a register at \"0x00\", which pyuvm keys as \"0x0\"",
               ["regcheck", "REG_MODEL=tb/st_regs.py:ZeroAddrRegs"],
               ["configured at '0x00'", "KeyError"]),
        Expect("make regcheck: a model that builds",
               ["regcheck", "REG_MODEL=tb/st_regs.py:GoodRegs"],
               ["the model builds: 1 registers"], must_not_say=(), exit_zero=True),
        Expect("the reference test, B01: a logged MISMATCH fails the test",
               ["check", T + "StGoodTest", "BUG=B01"],
               ["VERDICT: PASS", "caught", "MISMATCH SUB"],
               must_not_say=("VERDICT: FAIL", "BROKEN"), exit_zero=True),
        Expect("the reference test, B02: only an assertion can see it",
               ["check", T + "StGoodTest", "BUG=B02"],
               ["VERDICT: PASS", "assertion failure", "u_sva.n_fail"],
               must_not_say=("VERDICT: FAIL", "BROKEN"), exit_zero=True),
        Expect("the reference test against every bug",
               ["check-all", T + "StGoodTest"],
               ["2 of 3 caught", "MISSED", "B03_add_magic_pair", "one operand pair"],
               must_not_say=("NO COUNT", "BROKEN")),
        Expect("sends nothing",
               ["check", T + "StEmptyTest", "BUG=B01"],
               ["MISSED", "passes B01_sub_borrow_on_equal too"]),
        Expect("one item, repeated",
               ["check", T + "StFixedTest", "BUG=B01"],
               ["MISSED", "passes B01_sub_borrow_on_equal too"]),
        Expect("uvm_test, not BaseTest",
               ["check", T + "StPlainTest", "BUG=B01"],
               ["BROKEN", "no BaseTest line", "VERDICT: FAIL"]),
        Expect("a plain assert in the scoreboard",
               ["check", T + "StAssertTest", "BUG=B01"],
               ["VERDICT: PASS", "AssertionError"],
               must_not_say=("VERDICT: FAIL", "BROKEN"), exit_zero=True),
        Expect("NameError in the mismatch path",
               ["check", T + "StCrashTest", "BUG=B01"],
               ["ok", "BROKEN", "NameError", "VERDICT: FAIL", "only a wrong answer reaches"],
               must_not_say=("VERDICT: PASS", " caught ")),
        Expect("UVMFatalError used as a check",
               ["check", T + "StFatalCheckTest", "BUG=B01"],
               ["BROKEN", "UVMFatalError", "VERDICT: FAIL"]),
        Expect("a ConfigDB name nobody set",
               ["check", T + "StConfigTest", "BUG=B01"],
               ["BROKEN", "UVMConfigItemNotFound", "VERDICT: FAIL"]),
        Expect("a hang, stopped by RUN_TIMEOUT",
               ["check", T + "StHangTest", "BUG=B01", "RUN_TIMEOUT=10"],
               ["BROKEN", "timed out", "VERDICT: FAIL"]),
        Expect("the error counter never installed",
               ["check", T + "StNoSuperTest", "BUG=B01"],
               ["BROKEN", "BaseTestNotSetUp", "VERDICT: FAIL"]),
        Expect("final_phase without super()",
               ["check", T + "StFinalNoSuperTest", "BUG=B01"],
               ["BROKEN", "no BaseTest line", "VERDICT: FAIL"]),
        Expect("a TEST that doesn't exist",
               ["check", T + "NoSuchTest", "BUG=B01"],
               ["BROKEN", "every test skipped", "VERDICT: FAIL"]),
        Expect("a bug id the lab does not have",
               ["check", T + "StGoodTest", "BUG=B99"],
               ["is not one of this lab's bugs"]),
        Expect("a bug id the design does not know (make run)",
               ["run", T + "StGoodTest", "BUG=B99"],
               ["BROKEN", "unknown bug id"]),
        Expect("make run, golden: one line, ok",
               ["run", T + "StGoodTest"],
               ["ok: 0 errors, 0 assertions", "DD105-B BaseTest: 0 errors logged"],
               must_not_say=("BROKEN",), exit_zero=True),
        Expect("make regress: 2 tests x 2 seeds" + (", then the coverage" if venv else ""),
               ["regress", "TESTS=StGoodTest StEmptyTest", "SEEDS=1 2"],
               regress_says, must_not_say=("BROKEN", "FAIL"), exit_zero=True),
        Expect("make seeds: StGoodTest on 3 seeds",
               ["seeds", T + "StGoodTest", "NSEEDS=3"],
               ["3 ok"], must_not_say=("BROKEN", "FAIL"), exit_zero=True),
        Expect("make waves: an FST file with the design and its assertion in it",
               ["waves", T + "StGoodTest", "PLUSARGS=+N=20", "BUG=B01"],
               ["waves.fst"], must_not_say=("BROKEN",), exit_zero=True,
               then=wave_scopes(os.path.join(ALU, "build", "runs", "StGoodTest-s1-B01", "waves.fst"))),
    ]


def wave_scopes(fst):
    """The waves hold the ALU and its bound assertion, and no variable from any
    package, so st_bug_pkg.bug_id stays out of them (dd105b_trace.vlt)."""
    def check():
        if not os.path.exists(fst):
            return [f"{fst} is missing"]
        p = subprocess.run(["fst2vcd", fst], capture_output=True, text=True)
        head = p.stdout.split("$enddefinitions")[0]
        scopes, path, in_pkg = set(), [], []
        for line in head.splitlines():
            m = re.match(r"\$scope module (\S+) \$end", line)
            if m:
                path.append(m.group(1))
                scopes.add(m.group(1))
            elif line.startswith("$upscope"):
                path.pop()
            elif line.startswith("$var") and any("pkg" in s for s in path):
                in_pkg.append(".".join(path) + ": " + line.split()[4])
        out = [f"no scope {s} in the waves" for s in ("st_alu", "u_sva") if s not in scopes]
        out += [f"package variable in the waves: {v}" for v in in_pkg[:5]]
        if "bug_id" in head:
            out.append("bug_id is in the waves")
        return out
    return check


def hunt_cases():
    T = "TEST="
    seal = os.path.join(ALU, ".hunt")
    return [
        Expect("hunt: deal B01", ["new", "BUGPICK=B01"], ["A MYSTERY BUG"], must_not_say=("B01",),
               exit_zero=True, then=has_file(seal)),
        Expect("hunt: the loop names no bug", ["hunt", T + "StGoodTest", "VERBOSE=1"],
               ["<sealed>", "disagrees with your test"], must_not_say=("B01", "borrow"),
               exit_zero=True),
        Expect("hunt verdict: a test that catches it",
               ["verdict", T + "StGoodTest"],
               ["VERDICT: PASS", "B01_sub_borrow_on_equal"], must_not_say=("BROKEN",),
               exit_zero=True),
        Expect("hunt verdict: a test that sends nothing",
               ["verdict", T + "StEmptyTest"],
               ["MISSED", "row 2", "VERDICT: FAIL"]),
        Expect("hunt verdict: a crash in the mismatch path",
               ["verdict", T + "StCrashTest"],
               ["BROKEN", "VERDICT: FAIL"], must_not_say=("VERDICT: PASS", "B01")),
        Expect("hunt: reveal", ["reveal"], ["B01_sub_borrow_on_equal"], must_not_say=(),
               exit_zero=True),
    ]


def part2(full):
    print(RULE)
    print(" PART 2   the graders, end to end, on alu/")
    print(RULE)
    if not full:
        print(" Skipped. This part builds alu/ and runs the graders: about two minutes.")
        print("     make FULL=1")
        print(RULE)
        return True
    if not shutil.which("verilator"):
        print(" verilator is not on PATH: run this in the course image.")
        print(RULE)
        return False
    if os.path.exists(os.path.join(ALU, ".hunt")):
        os.remove(os.path.join(ALU, ".hunt"))

    print(" building alu/ ...")
    rc, out = make("build")
    print("   " + "\n   ".join(l for l in out.splitlines() if re.search(r"built |up to date|FAILED", l)))
    if rc != 0:
        print(out[-3000:])
        return False
    venv = venv_python()
    print(f" course venv: {venv or 'not there (make venv); the coverage case is left out'}")

    bad = 0

    def show(label, problems, out):
        nonlocal bad
        bad += bool(problems)
        print(f"  {'ok' if not problems else 'WRONG':>6}  {label}")
        for p in problems:
            print(f"          {p}")
        if problems:
            print(THIN)
            for l in out.strip().splitlines()[-25:]:
                print("          " + l)
            print(THIN)

    try:
        for e in cases(venv):
            show(e.label, *e.check())
        for e in hunt_cases():
            show(e.label, *e.check())
    finally:
        for p in (os.path.join(ALU, ".hunt"),):
            if os.path.exists(p):
                os.remove(p)
        shutil.rmtree(os.path.join(ALU, "build-broken"), ignore_errors=True)

    print(THIN)
    print(" every grader gave every fixture the verdict it must." if not bad
          else f" {bad} case(s) got the wrong verdict. That is the serious kind.")
    print(RULE)
    return bad == 0


# ─────────────────────────────────────────────────────────────────────────────
# PART 3 -- nobody has re-grown their own copy of the rule
# ─────────────────────────────────────────────────────────────────────────────

GRADERS = ["check.py", "hunt.py", "regress.py"]
FORBIDDEN = [
    (re.compile(r"^\s*class (Run|Outcome)\b", re.M), "its own Run or Outcome class -- use verdict.read_run()"),
    (re.compile(r"^\s*def (classify|read_results)\(", re.M), "its own classifier -- use verdict.py"),
    (re.compile(r"ET\.parse|ElementTree|results\.xml"), "reads results.xml itself -- verdict.py does that"),
    (re.compile(r"error_type|CHECK_FIRED"), "classifies exceptions itself -- verdict.py does that"),
    (re.compile(r"Assertion failed"), "reads assertion failures itself -- verdict.py does that"),
    (re.compile(r"%Error|%Fatal"), "reads Verilator's messages itself -- verdict.py does that"),
    (re.compile(r"DD105-B BaseTest"), "reads BaseTest's line itself -- verdict.py does that"),
    (re.compile(r"open\([^)]*exit_status"), "reads exit_status itself -- verdict.py does that"),
]


def part3():
    print(RULE)
    print(" PART 3   every grader reads the rule from verdict.py")
    print(RULE)
    bad = 0
    for g in GRADERS:
        src = open(os.path.join(COMMON, g)).read()
        hits = [why for rx, why in FORBIDDEN if rx.search(src)]
        if not re.search(r"^import verdict as V", src, re.M):
            hits.append("does not import verdict.py")
        bad += bool(hits)
        print(f"  {'ok' if not hits else 'WRONG':>6}  {g}")
        for h in hits:
            print(f"          {h}")
    print(THIN)
    print(f" {len(GRADERS) - bad} of {len(GRADERS)} graders.")
    print(RULE)
    return bad == 0


def main():
    sys.stdout.reconfigure(line_buffering=True)
    if "--capture" in sys.argv:
        return 0 if capture() else 1
    full = os.environ.get("FULL", "").strip().lower() not in ("", "0", "no", "false")
    ok = part1()
    ok = part3() and ok
    ok = part2(full) and ok
    print("")
    print(" SELFTEST: PASS" if ok else " SELFTEST: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
