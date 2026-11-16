"""
DD105-B: reading a cocotb + pyuvm run, and the one distinction every verdict
depends on.

    from verdict import read_run
    run = read_run("build/grade/golden", expect_bug=None)
    run.kind        'pass', 'caught' or 'broken'
    run.mark("pass")   'ok' / 'FAIL' / 'BROKEN'     (the golden design)
    run.mark("fail")   'caught' / 'MISSED' / 'BROKEN' (a design with a bug on)

    python3 verdict.py <run folder> [--bug ID]    one run, one line; exit 0 = pass

This is DD104's labs/common/verdict.py, which reads cocotb's results.xml,
with the run-folder reading and the bug switch of DD105-A's verdict.py.

────────────────────────────────────────────────────────────────────────────
WHY THIS FILE EXISTS
────────────────────────────────────────────────────────────────────────────
A test that does not pass has not necessarily checked anything. DD104's
grader once told a student `3 of 3 ALU bugs caught` about a testbench that
raised NameError on every core: three crashes, no catches. cocotb writes "the
check fired" and "the test blew up" into results.xml the same way, as a
<failure>, and only the exception's class name in error_type tells them apart.

pyuvm adds two traps of its own:

  - self.logger.error() fails nothing. The test passes, and so does a
    scoreboard that logged a thousand mismatches. Every DD105-B test derives
    from dd105b_base.BaseTest, which turns logged errors into an
    AssertionError at the end; a test that passes without BaseTest's closing
    line didn't go through it, and is graded BROKEN, not pass.
  - pyuvm raises AssertionError from inside the library for a register model
    that is wrong (two overlapping fields), which reads exactly like a check.
    The graders build the lab's register model before any verdict
    (regcheck.py), so that one never reaches this file.

And Verilator one: a bound assertion's $error counts towards Verilator's
error limit, 1 by default, and the first failure ends the simulation, which
cocotb reports as SimFailure. labs/common/pyuvm.mk raises the limit for every
lab with assertions. A run that stopped that way anyway is graded caught,
because the assertion's message is in the log, with a note that the rest of
the test didn't run (DD105-A grades the same case the same way).

A run is one of:

    pass     results.xml has at least one test, every test ran and passed,
             BaseTest's closing line is in the log, and no assertion failed
    caught   a CHECK fired, and nothing else went wrong
    BROKEN   anything else. A BROKEN run is a statement about the testbench
             or the setup, not about the design, so it is never a pass and
             never a catch.

────────────────────────────────────────────────────────────────────────────
WHAT COUNTS AS A CHECK: a whitelist, on purpose
────────────────────────────────────────────────────────────────────────────
  1. a test that ended with AssertionError: `assert got == want`, and
     BaseTest's own AssertionError for logged errors and assertion failures;
  2. a test that ended with SimTimeoutError: cocotb's with_timeout() expired,
     or a @pyuvm.test(timeout_time=...) ran out, so the event the test was
     waiting for never came;
  3. a failed SystemVerilog assertion, which Verilator prints as
     "%Error: <file>:<line>: Assertion failed in <instance>: ...".

Everything else is BROKEN: NameError, AttributeError and every other Python
exception, UVMFatalError, UVMConfigItemNotFound, a SimFailure without a failed
assertion, a $fatal (the router's unknown +BUG among them), a run that hit
RUN_TIMEOUT, a crash, no results.xml, no test run or every test skipped, and,
in a lab that sets BUG_CONFIRM, a bug switch the design did not confirm. As in
DD104, a whitelist and not a blacklist: a blacklist is wrong the first time a
test fails in a way nobody listed, and wrong in that direction means a crash
scored as a catch. When the course adds a new way for a check to say "the
design is wrong", add it here and to the selftest.
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

# ── the exceptions that mean "a check in this course fired" ─────────────────
CHECK_FIRED = {
    "AssertionError",       # assert, and BaseTest's verdict on logged errors and assertions
    "SimTimeoutError",      # with_timeout() or @pyuvm.test(timeout_time=...) expired
}

# ── the bug switch contract (the design under test provides this) ───────────
# No +BUG (or +BUG=none) is the golden design, +BUG=<id> turns one bug on, and
# an id the design doesn't know is a $fatal. The design need not say which bug
# is on. If it does, the lab sets BUG_CONFIRM to that line with {id} in it,
# and then a bug run without the line, or a golden run with one, is BROKEN.
BUG_UNKNOWN = re.compile(r"DD105-BUG: unknown bug id|is not a bug in this build")


def confirm_regex(confirm):
    """'DD105-BUG: {id} enabled' -> a regex that captures the id."""
    if not confirm:
        return None
    return re.compile(r"(\S+)".join(re.escape(p) for p in confirm.split("{id}")))


# ── the simulator's and the testbench's own lines ────────────────────────────
VL_ERROR = re.compile(r"^(?:\[[^\]]*\]\s*)?%(Error|Fatal)(?:-[A-Z0-9_]+)?:\s*(.*)$")
ASSERTION = re.compile(r"Assertion failed in")
MARKER = re.compile(r"^DD105-B BaseTest: (\d+) errors? logged, (?:(\d+) assertion failures?|no bound assertions)")

# What each kind of BROKEN means, in words a student can act on.
WHY = {
    "build": "The simulator did not build, so nothing ran. The build log says why.",
    "nolaunch": "The simulator never started, so nothing ran.",
    "noresults": ("The simulator ran but cocotb wrote no results.xml: it crashed, or Python "
                  "failed before cocotb started. The log says which."),
    "timeout": ("The run was still going when the time limit hit, and it was stopped. A hang "
                "is not a catch: if the design really stops answering, catch that with a "
                "check of your own, such as cocotb's with_timeout()."),
    "signal": ("The simulator crashed. Nothing after the crash was checked, so this says "
               "nothing about the design."),
    "notests": ("cocotb found no test to run. Check that TEST_MODULES names the module "
                "(test_router), not the file (test_router.py), and that each test class has "
                "@pyuvm.test()."),
    "skipped": ("Every test was skipped, so nothing ran and nothing was checked. TEST names a "
                "test that doesn't exist: compare it with `make tests`."),
    "errored": ("A test raised an exception that is not a check. It stopped before the "
                "comparison happened, or instead of it, so it says nothing about the design. "
                "Fix the testbench first; the traceback is in the log."),
    "UVMFatalError": ("UVMFatalError is how a testbench says it cannot go on. It is not a "
                      "check. If you meant it as one, log the mismatch with "
                      "self.logger.error(), and BaseTest fails the test at the end."),
    "UVMConfigItemNotFound": ("ConfigDB().get() asked for a name nobody set. That is "
                              "configuration, not a check."),
    "BaseTestNotSetUp": ("Some component's errors weren't being counted, so the test can't say "
                         "whether anything went wrong. Call super() in any phase method you "
                         "override, and make every component in build_phase."),
    "SimFailure": ("The simulator stopped before the test finished, and not because of a "
                   "failed assertion. A $finish, $stop or $fatal in the design does this."),
    "no-base-test": ("The test passed without BaseTest's closing line, so a logged error would "
                     "have failed nothing. Derive the test from BaseTest (or RouterBaseTest), "
                     "and call super().final_phase() if you override final_phase."),
    "fatal-sv": ("A $fatal stopped the run. It is how a design or a bound module gives up, not "
                 "how it checks: an assertion's $error is a check."),
    "runtime": ("The simulator stopped with an error that is not a check. The line above it in "
                "the log says what."),
    "exit": "The simulator exited non-zero, and nothing in the log says why.",
    "bug-id": "The design does not know that bug id. `make check-all` lists the ids.",
    "bug-unconfirmed": ("This run asked for a planted bug, and the design never printed the "
                        "line that says it is on (BUG_CONFIRM), so the bug may be off. A run "
                        "against a bug that is off says nothing."),
    "bug-on-golden": ("This was meant to be the golden design, but the design printed the "
                      "line that says a bug is on (BUG_CONFIRM)."),
    "regmodel": ("The register model doesn't build. pyuvm raises AssertionError for a model "
                 "that is wrong, which would read as a caught bug, so nothing was graded."),
}


class Outcome:
    """What happened to one cocotb test in results.xml. kind is 'passed',
    'failed' (a check fired), 'errored' (the test blew up) or 'skipped'."""

    def __init__(self, name, kind, error_type="", message="", sim_time_ns=0.0):
        self.name, self.kind, self.error_type = name, kind, error_type
        self.message, self.sim_time_ns = message, sim_time_ns

    @property
    def one_line(self):
        first = self.message.strip().splitlines()[0] if self.message.strip() else "(no message)"
        return f"{self.name}: {self.error_type or 'failure'}: {first}"


def read_results(path):
    """The <testcase>s of a cocotb results.xml, as Outcomes."""
    outcomes = []
    for case in ET.parse(path).getroot().iter("testcase"):
        name = case.get("name") or "(unnamed)"
        try:
            sim_ns = float(case.get("sim_time_ns") or 0.0)
        except ValueError:
            sim_ns = 0.0
        if case.find("skipped") is not None:
            outcomes.append(Outcome(name, "skipped", sim_time_ns=sim_ns))
            continue
        # cocotb 2.0.1 writes only <failure>; read <error> too, as DD104 does.
        bad = list(case.findall("failure")) + list(case.findall("error"))
        if not bad:
            outcomes.append(Outcome(name, "passed", sim_time_ns=sim_ns))
            continue
        e = bad[0]
        etype = (e.get("error_type") or e.get("type") or "").strip()
        text = (e.get("error_msg") or e.get("message") or e.get("msg") or e.text or "").strip()
        # A <failure> with no error_type is "Test initialization failed": the
        # test never started, so no check in it can have fired.
        kind = "failed" if etype in CHECK_FIRED else "errored"
        outcomes.append(Outcome(name, kind, etype, text, sim_ns))
    return outcomes


class Run:
    """What one simulation did, read from its folder (see pyuvm.mk's run_sim)."""

    def __init__(self, label="", run_dir="", log="", exit_status=None, seconds=0.0,
                 cmd="", launched=True, build_failed=False):
        self.label, self.run_dir, self.log = label, run_dir, log
        self.exit_status, self.seconds, self.cmd = exit_status, seconds, cmd
        self.launched, self.build_failed = launched, build_failed
        self.outcomes = []
        self.marker = None                   # (errors, assertion failures or None) from BaseTest
        self.assertions = []                 # Verilator's "Assertion failed" lines
        self.fired = []                      # (kind, one line): the checks that fired
        self.problems = []                   # (key, one line): why the run is BROKEN
        self.notes = []                      # remarks that change nothing

    @property
    def kind(self):
        if self.problems:
            return "broken"
        return "caught" if self.fired else "pass"

    @property
    def broken(self):
        return self.kind == "broken"

    @property
    def passed(self):
        return self.kind == "pass"

    @property
    def caught(self):
        return self.kind == "caught"

    def mark(self, expectation):
        """The word in a report row. expectation is 'pass' (the golden design:
        nothing may fire) or 'fail' (a bug is on: a check must fire)."""
        if self.broken:
            return "BROKEN"
        if expectation == "pass":
            return "ok" if self.passed else "FAIL"
        return "caught" if self.caught else "MISSED"

    def summary(self):
        """A few words for a report row."""
        if self.build_failed:
            return "the build failed"
        if not self.launched:
            return "did not run"
        if self.problems:
            key, _ = self.problems[0]
            words = {"timeout": "timed out", "signal": "crashed", "noresults": "no results.xml",
                     "notests": "no tests", "skipped": "every test skipped",
                     "no-base-test": "no BaseTest line", "regmodel": "register model broken"}
            if key in words:
                return words[key]
            if key.startswith("bug"):
                return "bug switch problem"
            return key[:28]
        bits = []
        if self.marker:
            n_err, n_sva = self.marker
            bits.append(f"{n_err} error{'' if n_err == 1 else 's'}")
            if n_sva is not None:
                bits.append(f"{n_sva} assertion{'' if n_sva == 1 else 's'}")
        elif self.assertions:
            bits.append(f"{len(self.assertions)} assertion" + ("" if len(self.assertions) == 1 else "s"))
        if self.fired and not self.marker:
            types = sorted({o.error_type for o in self.outcomes if o.kind == "failed"})
            if types:
                bits.insert(0, ", ".join(types))
        return ", ".join(bits) if bits else "passed"

    def first_fired(self):
        return self.fired[0][1] if self.fired else ""


# ── reading a run ────────────────────────────────────────────────────────────

def _read(path, default=""):
    try:
        with open(path, errors="replace") as f:
            return f.read()
    except OSError:
        return default


def read_run(run_dir, expect_bug=None, label="", confirm=None, base_test=True):
    """Read a run folder written by pyuvm.mk (run.log, results.xml,
    exit_status, seconds, cmd). expect_bug is the +BUG id the run was given
    (None: the golden design), confirm is the lab's BUG_CONFIRM line, if it has
    one, and base_test says whether a pass needs BaseTest's closing line."""
    if expect_bug and expect_bug.lower() == "none":
        expect_bug = None                    # +BUG=none is the golden design
    log = _read(os.path.join(run_dir, "run.log"), None)
    rc_text = _read(os.path.join(run_dir, "exit_status")).strip()
    if log is None or not rc_text:
        run = Run(label, run_dir, log or "", None, 0.0, launched=False)
        run.problems.append(("nolaunch", "the simulator never ran"))
        return run
    try:
        seconds = float(_read(os.path.join(run_dir, "seconds"), "0") or 0)
    except ValueError:
        seconds = 0.0
    run = Run(label, run_dir, log, int(rc_text), seconds,
              _read(os.path.join(run_dir, "cmd")).strip())
    results = os.path.join(run_dir, "results.xml")
    if os.path.exists(results):
        try:
            run.outcomes = read_results(results)
        except ET.ParseError as e:
            run.problems.append(("noresults", f"results.xml can't be read: {e}"))
    else:
        run.problems.append(("noresults", "no results.xml in the run folder"))
    classify(run, expect_bug, confirm, base_test)
    return run


def build_failed(label="the build", log=""):
    run = Run(label, "", log, None, 0.0, launched=False, build_failed=True)
    run.problems.append(("build", "the simulator did not build"))
    return run


def classify(run, expect_bug=None, confirm=None, base_test=True):
    """Fill run.fired, run.problems and run.notes from results.xml, run.log and
    the exit status."""
    lines = run.log.splitlines()
    P = run.problems
    confirm_rx = confirm_regex(confirm)
    bug_ids, fatal, runtime = [], [], []
    for line in lines:
        s = line.rstrip()
        m = MARKER.match(s)
        if m:
            run.marker = (int(m.group(1)), int(m.group(2)) if m.group(2) is not None else None)
        m = VL_ERROR.match(s)
        if m:
            sev, text = m.group(1), m.group(2).strip()
            if BUG_UNKNOWN.search(text) or "Verilog $stop" in text:
                pass
            elif ASSERTION.search(text) and sev == "Error":
                run.assertions.append(text)
            elif sev == "Fatal" or ASSERTION.search(text):
                fatal.append(text)
            else:
                runtime.append(text)
        m = confirm_rx.search(s) if confirm_rx else None
        if m:
            bug_ids.append(m.group(1))

    # how the process ended
    rc = run.exit_status
    if rc == 124:
        P.insert(0, ("timeout", f"stopped after {run.seconds:.0f} s (the RUN_TIMEOUT limit)"))
    elif rc is not None and (rc < 0 or rc >= 128):
        sig = -rc if rc < 0 else rc - 128
        P.insert(0, ("signal", f"killed by signal {sig} (exit status {rc})"))

    # the bug switch
    if BUG_UNKNOWN.search(run.log):
        P.append(("bug-id", next(l.strip() for l in lines if BUG_UNKNOWN.search(l))))
    elif confirm_rx and expect_bug and expect_bug not in bug_ids:
        P.append(("bug-unconfirmed", f"asked for +BUG={expect_bug}; no "
                  f"'{confirm.replace('{id}', expect_bug)}' line in the log"))
    elif confirm_rx and not expect_bug and bug_ids:
        P.append(("bug-on-golden", f"'{confirm.replace('{id}', bug_ids[0])}' on the golden design"))

    for f in fatal:
        P.append(("fatal-sv", f))

    # results.xml
    stopped_at_limit = False
    if run.outcomes or not any(k == "noresults" for k, _ in P):
        ran = [o for o in run.outcomes if o.kind != "skipped"]
        if not run.outcomes:
            P.append(("notests", "results.xml has no tests"))
        elif not ran:
            P.append(("skipped", f"all {len(run.outcomes)} tests were skipped"))
        for o in run.outcomes:
            if o.kind == "failed":
                run.fired.append(("check", o.one_line))
            elif o.kind == "errored":
                if o.error_type == "SimFailure" and run.assertions:
                    # Verilator stopped at its error limit after a failed assertion.
                    stopped_at_limit = True
                    continue
                key = o.error_type if o.error_type in WHY else (
                    "SimFailure" if o.error_type == "SimFailure" else "errored")
                P.append((key, o.one_line))
        if ran and all(o.kind == "passed" for o in ran) and base_test and run.marker is None:
            P.append(("no-base-test", "the test passed and the log has no 'DD105-B BaseTest:' line"))

    # Verilator's assertion failures are checks, whether or not the test read them
    for a in run.assertions[:1]:
        run.fired.append(("assertion", a))
    if run.assertions and not stopped_at_limit and run.outcomes and \
            all(o.kind in ("passed", "skipped") for o in run.outcomes):
        run.notes.append(f"{len(run.assertions)} assertion failure(s) are in the log and the test "
                         "passed: it doesn't read u_sva.n_fail, as BaseTest does.")
    if stopped_at_limit:
        run.notes.append("Verilator stopped the run at its error limit, so the rest of the test "
                         "didn't run. Runs through make raise it (+verilator+error+limit+N).")
    if runtime and not run.fired and not P:
        P.append(("runtime", runtime[0]))

    # an exit status that the rest doesn't explain
    if rc not in (0, None, 124) and 0 < rc < 128 and not run.fired and not P:
        P.append(("exit", f"exit status {rc}"))
    return run


# ── the words the verdict says ───────────────────────────────────────────────

def explain(run, indent="   ", width=70):
    """The reason a run is BROKEN, in sentences."""
    out = []
    if not run.problems:
        return out
    key, line = run.problems[0]
    out.append(f"{indent}{line[:200]}")
    words, cur = WHY.get(key, WHY["errored"]).split(), ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            out.append(indent + cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(indent + cur)
    if len(run.problems) > 1:
        out.append(f"{indent}(and {len(run.problems) - 1} more problem"
                   f"{'s' if len(run.problems) > 2 else ''} in the same run)")
    return out


def report_problems(run, indent="        ", limit=3):
    """Under a report row: what broke, or the first checks that fired."""
    for key, line in run.problems[:limit]:
        print(f"{indent}BROKEN: {line[:100]}")
    if not run.problems:
        for kind, line in run.fired[:limit]:
            print(f"{indent}{line[:100]}")
    for n in run.notes:
        print(f"{indent}note: {n[:200]}")


def main():
    ap = argparse.ArgumentParser(description="DD105-B: classify one cocotb + pyuvm run")
    ap.add_argument("run_dir")
    ap.add_argument("--bug", default="", help="the +BUG id the run was given, if any")
    ap.add_argument("--bug-confirm", default="", help="the lab's BUG_CONFIRM, if any")
    ap.add_argument("--base-test", default="1", help="1: a pass needs BaseTest's closing line")
    a = ap.parse_args()
    run = read_run(a.run_dir, expect_bug=a.bug or None, confirm=a.bug_confirm or None,
                   base_test=a.base_test == "1")
    rel = os.path.relpath(os.path.join(a.run_dir, "run.log"))
    mark = run.mark("fail" if a.bug and a.bug.lower() != "none" else "pass")
    print("-" * 72)
    print(f" {mark}: {run.summary()}   {run.seconds:.2f} s   log: {rel}")
    if run.broken:
        for l in explain(run):
            print(l)
    else:
        for kind, line in run.fired[:3]:
            print(f"   {line[:110]}")
    for n in run.notes:
        print(f"   note: {n}")
    print("-" * 72)
    return 0 if run.passed else 1


if __name__ == "__main__":
    sys.exit(main())
