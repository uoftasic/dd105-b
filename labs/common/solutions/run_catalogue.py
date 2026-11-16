"""
DD105 -- check the bug catalogue against the router, end to end.

    python3 run_catalogue.py [--build DIR]

Run it inside the course image, from anywhere. It does six things and prints
a table at the end:

  1. inject.py --verify: every anchor in bugs.py matches rtl/.
  2. Builds smoke/tb_smoke.sv and solutions/tb_directed.sv, each twice: on the
     golden RTL and on the faulty build from inject.py --all.
  3. The smoke test on the golden RTL, on the faulty build with no bug, and
     with each bug. Every one of these must pass: the shipped test is weak
     on purpose.
  4. The directed test on the golden RTL and on the faulty build with no bug,
     each writing a trace of every router port on every cycle. Both must pass
     and the two traces must be identical.
  5. The directed test with each bug. Each bug must fail at least one check;
     the table lists which.
  6. Exits 0 only if all of that held.

The whole run takes about two minutes on two CPUs.
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
COMMON = os.path.dirname(HERE)
SMOKE = os.path.join(COMMON, "smoke")
sys.path.insert(0, COMMON)

from bugs import BUGS, ids  # noqa: E402


def sh(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def make(build, target, tb_src, plusargs=""):
    cmd = ["make", "-s", f"BUILD={build}", f"TB_SRC={tb_src}", f"PLUSARGS={plusargs}"]
    if target:
        cmd.append(target)
    return sh(cmd, cwd=SMOKE)


def build_sims(build):
    for tb in ("tb_smoke.sv", "../solutions/tb_directed.sv"):
        top = os.path.splitext(os.path.basename(tb))[0]
        for kind in ("golden", "faulty"):
            target = f"{build}/{top}-{kind}/sim"
            t0 = time.time()
            rc, out = make(build, target, tb)
            if rc != 0:
                print(out)
                sys.exit(f"build of {top} ({kind}) failed")
            print(f"  built {top:<12} {kind:<7} {time.time() - t0:5.1f} s")


def run(build, top, kind, *plusargs):
    sim = os.path.join(build, f"{top}-{kind}", "sim")
    rc, out = sh([sim] + list(plusargs))
    return rc, out


def checks_failed(out):
    return [m.group(1) for m in re.finditer(r"^CHECK (C\d\d) \S+\s+FAIL", out, re.M)]


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default=os.path.join(SMOKE, "build"))
    args = ap.parse_args()
    build = os.path.abspath(args.build)
    os.makedirs(build, exist_ok=True)
    ok = True

    rc, out = sh([sys.executable, os.path.join(COMMON, "inject.py"), "--verify"])
    print(out.strip())
    if rc != 0:
        sys.exit(1)

    print("\nBuilding")
    build_sims(build)
    null = ["+vcd=/dev/null"]

    print("\nSmoke test (must pass everywhere)")
    for kind, bug in [("golden", None), ("faulty", None)] + [("faulty", b) for b in ids()]:
        plus = null + ([f"+BUG={bug}"] if bug else [])
        rc, out = run(build, "tb_smoke", kind, *plus)
        passed = rc == 0 and "SMOKE: PASS" in out
        ok &= passed
        print(f"  {'PASS' if passed else 'FAIL'}  {kind:<7} {bug or 'no bug'}")

    print("\nDirected test, no bug (must pass, with identical traces)")
    traces = {}
    for kind in ("golden", "faulty"):
        trace = os.path.join(build, f"trace-{kind}.txt")
        rc, out = run(build, "tb_directed", kind, *null, f"+trace={trace}")
        passed = rc == 0 and "DIRECTED: PASS" in out
        ok &= passed
        summary = re.search(r"DIRECTED: \d+ edges.*", out)
        traces[kind] = sha(trace)
        print(f"  {'PASS' if passed else 'FAIL'}  {kind:<7} {summary.group(0) if summary else ''}")
    same = traces["golden"] == traces["faulty"]
    ok &= same
    with open(os.path.join(build, "trace-golden.txt")) as f:
        n_lines = sum(1 for _ in f)
    print(f"  traces {'identical' if same else 'DIFFERENT'}: {n_lines} cycles, sha256 {traces['golden'][:16]}")

    print("\nDirected test, each bug (must fail at least one check)")
    rows = []
    for bug in ids():
        rc, out = run(build, "tb_directed", "faulty", *null, f"+BUG={bug}")
        failed = checks_failed(out)
        caught = rc != 0 and len(failed) > 0
        ok &= caught
        rows.append((bug, failed))
        print(f"  {'caught' if caught else 'MISSED'}  {bug}  {' '.join(failed)}")

    print("\n| Bug | Tier | Caught by |")
    print("|---|---|---|")
    for bug, failed in rows:
        print(f"| {bug} | {BUGS[bug]['tier']} | {', '.join(failed) or 'nothing'} |")

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
