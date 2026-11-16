"""
DD105 -- build broken routers from the bug catalogue.

    python3 inject.py --all --out DIR    one faulty build: every bug, picked at run time
    python3 inject.py B07 --out DIR      the golden RTL with only B07's line changed
    python3 inject.py --verify           check every anchor against rtl/, change nothing
    python3 inject.py --list             the catalogue, without the answers

THE FAULTY BUILD

A cold UVM build of the router takes 1.5 to 2.5 minutes on 2 CPUs, and even a
rebuild after a one-line design edit takes about 25 s, so building fifteen
broken routers one at a time would cost fifteen builds where one will do.
`--all` writes a single copy of the RTL with every bug in it, each one
switched off unless it is selected. Each anchored line from bugs.py keeps its
place in its file, and the one expression the bug changes becomes a choice
between the two versions:

    golden RTL:   assign room      = (lkp_level <= LEVEL_W'(ADMIT_MAX));
    faulty RTL:   assign room      = ((router_bug_pkg::bug_id == 8) ?
                                      ((lkp_level < LEVEL_W'(ADMIT_MAX))) :
                                      ((lkp_level <= LEVEL_W'(ADMIT_MAX))));  // inject.py: B08

(on one line in the file). `router_bug_pkg::bug_id` is a variable in a small
generated package, and an initial block that inject.py adds to router.sv sets
it at time 0 from the simulator's command line:

    +BUG=B08      switch on B08
    no +BUG       switch on nothing: the design behaves exactly like rtl/
    +BUG=none     the same as no +BUG
    +BUG_ECHO     also print, at time 0, which bug (if any) is switched on

Any other value of +BUG stops the simulation with $fatal at time 0, so a typo
can't quietly run the golden design. Without +BUG_ECHO the switch prints
nothing at all, so the log of a run doesn't say which bug it ran, and a run
of the golden design can't be told from a run of a mystery bug except by what
the testbench itself reports. The testbench needs no changes: it compiles the
files in DIR/router.f instead of rtl/router.f and passes the plusargs.

THE ANCHOR CHECK

Before writing anything, inject.py checks that every anchor in bugs.py matches
exactly one whole line of its file, and that the bug's `golden` expression
appears exactly once in that line. If any check fails it writes nothing and
exits with status 1. Patching the wrong line, or no line, would give a
"broken" router that is not broken, and every check against it would be
meaningless.
"""

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from bugs import BUGS, TIER_NAMES, buggy_line, ids, number, resolve  # noqa: E402

GOLDEN_RTL = os.path.join(HERE, "rtl")
FILELIST = "router.f"
TOP_FILE = "router.sv"
PKG_FILE = "router_bug_pkg.sv"


class AnchorError(Exception):
    pass


def rtl_files():
    """The source files named in rtl/router.f, in order."""
    files = []
    with open(os.path.join(GOLDEN_RTL, FILELIST)) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("//"):
                files.append(line)
    return files


def read_golden():
    """{file name: list of lines} for every file in router.f."""
    out = {}
    for name in rtl_files():
        with open(os.path.join(GOLDEN_RTL, name)) as f:
            out[name] = f.read().split("\n")
    return out


def locate(src, bug_id):
    """The index of the bug's anchor line, after checking it is unique."""
    b = BUGS[bug_id]
    if b["file"] not in src:
        raise AnchorError(f"{bug_id}: {b['file']} is not in rtl/{FILELIST}")
    lines = src[b["file"]]
    hits = [i for i, line in enumerate(lines) if line == b["anchor"]]
    if len(hits) != 1:
        raise AnchorError(
            f"{bug_id}: the anchor matches {len(hits)} lines of rtl/{b['file']}, not 1.\n"
            f"  anchor: {b['anchor']!r}")
    n = lines[hits[0]].count(b["golden"])
    if n != 1:
        raise AnchorError(
            f"{bug_id}: the golden expression appears {n} times in its anchor line, not 1.\n"
            f"  line:   {b['anchor']!r}\n  golden: {b['golden']!r}")
    if b["golden"] == b["buggy"]:
        raise AnchorError(f"{bug_id}: golden and buggy are the same text")
    return hits[0]


def check_all(src):
    """Every problem with the catalogue, as a list of messages."""
    problems = []
    seen = {}
    for k in ids():
        try:
            i = locate(src, k)
        except AnchorError as e:
            problems.append(str(e))
            continue
        where = (BUGS[k]["file"], i)
        if where in seen:
            problems.append(f"{k} and {seen[where]} anchor the same line of {where[0]}")
        seen[where] = k
    return problems


def switch(bug_id):
    """The text that replaces a bug's golden expression in the faulty build."""
    b = BUGS[bug_id]
    return f"((router_bug_pkg::bug_id == {number(bug_id)}) ? ({b['buggy']}) : ({b['golden']}))"


PKG_TEXT = """\
// router_bug_pkg.sv -- generated by labs/common/inject.py. Do not edit.
//
// The bug switch for the faulty build of the router. bug_id is 0 for none
// (the design then behaves exactly like the golden RTL) or N for bug BNN in
// labs/common/bugs.py. The initial block that inject.py adds to router.sv
// sets it once, at time 0, from +BUG on the simulator's command line.

`default_nettype none

package router_bug_pkg;
  int unsigned bug_id = 0;
endpackage

`default_nettype wire
"""


def switch_block():
    """The initial block added to router.sv, just before endmodule."""
    known = ", ".join(str(number(k)) for k in ids())
    first, last = ids()[0], ids()[-1]
    return f"""\

  // ---- Added by labs/common/inject.py: the bug switch -----------------------
  // Reads +BUG=Bnn once, at time 0, and switches that bug on. With no +BUG,
  // or +BUG=none, every bug stays off. Anything else is a fatal error, so a
  // typo can't quietly run the golden design. It prints which bug is on only
  // when +BUG_ECHO is given too, so that a log doesn't give the bug away.
  initial begin : bug_switch
    string arg;
    int    id;
    id = 0;
    if ($value$plusargs("BUG=%s", arg)) begin
      arg = arg.toupper();
      if (arg == "NONE") id = 0;
      else if (arg.len() == 3 && arg.getc(0) == "B" &&
               arg.getc(1) >= "0" && arg.getc(1) <= "9" &&
               arg.getc(2) >= "0" && arg.getc(2) <= "9") id = arg.substr(1, 2).atoi();
      else id = -1;
      if (arg != "NONE" && !(id inside {{{known}}}))
        $fatal(1, "router: +BUG=%s is not a bug in this build ({first} to {last}, or none)", arg);
    end
    router_bug_pkg::bug_id = id;
    if ($test$plusargs("BUG_ECHO")) begin
      if (id != 0) $display("router: faulty build, bug B%02d switched on", id);
      else         $display("router: faulty build, no bug switched on");
    end
  end
"""


def write_faulty(out_dir):
    src = read_golden()
    problems = check_all(src)
    if problems:
        raise AnchorError("\n".join(problems))

    for k in ids():
        b = BUGS[k]
        lines = src[b["file"]]
        i = locate(src, k)
        lines[i] = lines[i].replace(b["golden"], switch(k), 1) + f"  // inject.py: {k}"

    top = src[TOP_FILE]
    ends = [i for i, line in enumerate(top) if line.strip() == "endmodule"]
    if len(ends) != 1:
        raise AnchorError(f"{TOP_FILE} has {len(ends)} endmodule lines, not 1")
    top[ends[0]:ends[0]] = switch_block().split("\n")

    os.makedirs(out_dir, exist_ok=True)
    for name, lines in src.items():
        with open(os.path.join(out_dir, name), "w") as f:
            f.write("\n".join(lines))
    with open(os.path.join(out_dir, PKG_FILE), "w") as f:
        f.write(PKG_TEXT)
    with open(os.path.join(out_dir, FILELIST), "w") as f:
        f.write("// The faulty build of the router, generated by labs/common/inject.py --all.\n")
        f.write("// Every bug in labs/common/bugs.py is compiled in; +BUG=Bnn picks one.\n")
        f.write("\n".join([PKG_FILE] + rtl_files()) + "\n")
    return out_dir


def write_one(bug_id, out_dir):
    """The golden RTL with one line changed: easy to diff, no switch."""
    src = read_golden()
    i = locate(src, bug_id)
    b = BUGS[bug_id]
    src[b["file"]][i] = buggy_line(bug_id)
    os.makedirs(out_dir, exist_ok=True)
    for name, lines in src.items():
        with open(os.path.join(out_dir, name), "w") as f:
            f.write("\n".join(lines))
    shutil.copy(os.path.join(GOLDEN_RTL, FILELIST), os.path.join(out_dir, FILELIST))
    return out_dir


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    ap.add_argument("bug", nargs="?", help="one bug, for example B07")
    ap.add_argument("--all", action="store_true", help="write the faulty build with every bug")
    ap.add_argument("-o", "--out", help="the directory to write")
    ap.add_argument("--verify", action="store_true", help="check every anchor, write nothing")
    ap.add_argument("--list", action="store_true", help="list the catalogue")
    args = ap.parse_args()

    if args.list:
        for k in ids():
            print(f"  {k}   tier {BUGS[k]['tier']} ({TIER_NAMES[BUGS[k]['tier']]})")
        return 0

    if args.verify:
        problems = check_all(read_golden())
        if problems:
            print("\n".join(problems))
            return 1
        print(f"all {len(BUGS)} anchors match exactly one line in rtl/, "
              f"and each golden expression appears once in its line")
        return 0

    if not args.out:
        ap.error("--out DIR is required")
    try:
        if args.all:
            write_faulty(args.out)
            print(f"faulty build with {len(BUGS)} bugs -> {args.out}/{FILELIST}")
        elif args.bug:
            k = resolve(args.bug)
            write_one(k, args.out)
            print(f"golden RTL with {k} -> {args.out}/{FILELIST}")
        else:
            ap.error("name a bug, or pass --all, --verify or --list")
    except AnchorError as e:
        print(f"{e}\n\nRefusing to inject: the catalogue no longer matches rtl/.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
