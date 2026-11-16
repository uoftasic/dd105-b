"""
DD105-B: the coverage of many runs together.

    make cov                       every run under build/runs
    python3 covmerge.py <folder>... --out <folder>

A test that collects functional coverage with cocotb-coverage writes it, at
the end of the run, to coverage.xml in its run folder:

    from cocotb_coverage.coverage import coverage_db
    coverage_db.export_to_xml("coverage.xml")

This finds every coverage.xml under the folders it is given, merges them with
cocotb-coverage's own merge_coverage(), and prints each coverpoint and cross
of the result with the bins nothing hit. The merge is cocotb-coverage's: this
file only finds the files and reads the merged one back.

It needs cocotb-coverage, so it runs with the course venv's Python, which
`make cov` and `make regress` pass it. Without the venv, or with no
coverage.xml anywhere, it says so and does nothing.
"""

import argparse
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

RULE = "=" * 72


def find(folders):
    out = []
    for d in folders:
        if os.path.isfile(os.path.join(d, "coverage.xml")):
            out.append(os.path.join(d, "coverage.xml"))
            continue
        for root, _, files in os.walk(d):
            if "coverage.xml" in files:
                out.append(os.path.join(root, "coverage.xml"))
    return sorted(set(out))


def show(path, limit=12):
    """Each coverpoint and cross of a merged file, and the bins with no hits."""
    root = ET.parse(path).getroot()

    def walk(el, depth):
        pct = el.get("cover_percentage")
        if pct is None:
            return
        bins = [b for b in el if b.get("hits") is not None]
        label = el.get("abs_name", el.tag)
        print(f"  {'  ' * depth}{label:<44} {float(pct):6.2f} %   "
              f"{el.get('coverage')} of {el.get('size')} bins")
        empty = [b.get("bin") for b in bins if int(b.get("hits", "0")) == 0]
        if empty:
            shown = ", ".join(empty[:limit]) + (f", ... ({len(empty) - limit} more)" if len(empty) > limit else "")
            print(f"  {'  ' * depth}    not hit: {shown}")
        for child in el:
            walk(child, depth + 1)

    walk(root, 0)


def merge(files, out_dir):
    from cocotb_coverage.coverage import merge_coverage
    os.makedirs(out_dir, exist_ok=True)
    merged = os.path.join(out_dir, "merged.xml")
    merge_coverage(lambda msg: None, merged, *files)
    return merged


def report(run_dirs, out_dir, python_bin=None):
    """For regress.py: run this file with the simulator's Python, which has
    cocotb-coverage when the venv exists."""
    files = find(run_dirs)
    if not files:
        return
    cmd = [python_bin or sys.executable, os.path.abspath(__file__), "--out", out_dir] + list(run_dirs)
    subprocess.run(cmd)


def main():
    ap = argparse.ArgumentParser(description="DD105-B: merge cocotb-coverage results")
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = find(a.folders)
    print(RULE)
    if not files:
        print(f" COVERAGE   no coverage.xml under {', '.join(a.folders)}")
        print(" A test writes one with coverage_db.export_to_xml(\"coverage.xml\").")
        print(RULE)
        return 0
    try:
        merged = merge(files, a.out)
    except ImportError:
        print(" COVERAGE   cocotb-coverage isn't importable here: run `make venv` first.")
        print(RULE)
        return 1
    print(f" COVERAGE   {len(files)} run{'s' if len(files) != 1 else ''}, merged by cocotb-coverage "
          f"into {os.path.relpath(merged)}")
    print(RULE)
    show(merged)
    print(RULE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
