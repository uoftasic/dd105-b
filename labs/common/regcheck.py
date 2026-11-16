"""
DD105-B: build a lab's register model on its own, before any verdict.

    python3 regcheck.py --lab-dir <lab> --model tb/router_ral.py:RouterRegs [--py-path a:b]
    make regcheck                                    (the lab's REG_MODEL)

pyuvm 4.0.1 checks a register model as it builds it, and reports what it
finds with AssertionError: two fields that overlap give
`AssertionError: ... Fields b overlap with field a`. In a test, that
AssertionError lands in results.xml exactly as a check that fired does, so a
broken model would be graded as a caught bug. check.py, regress.py and
hunt.py therefore run this first, outside the simulator, and stop with this
script's message if the model doesn't build.

It also catches one pyuvm trap that only shows at the first access: pyuvm
keys a map's registers by the address as Python's hex() prints it ("0x8"),
and looks a register up by the address string it was configured with, so a
register configured at "0x08" or "0x00" raises KeyError on its first read or
write.

Exit status 0 if the model builds, 1 if it doesn't, 2 for a usage problem.
"""

import argparse
import importlib.util
import os
import sys


def load(lab_dir, model, py_path):
    """The class named by <file>:<class>, imported from the lab."""
    if ":" not in model:
        raise SystemExit(f"REG_MODEL={model!r}: write it as <file>:<class>, "
                         "for example tb/router_ral.py:RouterRegs")
    path, cls_name = model.rsplit(":", 1)
    path = path if os.path.isabs(path) else os.path.join(lab_dir, path)
    for d in reversed([p for p in py_path.split(":") if p]):
        sys.path.insert(0, d if os.path.isabs(d) else os.path.join(lab_dir, d))
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None:
        raise SystemExit(f"REG_MODEL: no such file {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    try:
        return getattr(mod, cls_name)
    except AttributeError:
        raise SystemExit(f"REG_MODEL: {os.path.relpath(path, lab_dir)} has no class {cls_name}")


def registers(block):
    """[(name, configured address, offset key, reg)] for every register in every map."""
    out = []
    maps = [m for m in vars(block).values() if type(m).__name__ == "uvm_reg_map"]
    for m in maps:
        for key, reg in m.get_registers(as_dict=True).items():
            out.append((reg.get_name(), reg.get_address(), key, reg))
    return out


def main():
    ap = argparse.ArgumentParser(description="DD105-B: build a register model on its own")
    ap.add_argument("--lab-dir", default=os.getcwd())
    ap.add_argument("--model", default="", help="<file>:<class>, relative to the lab")
    ap.add_argument("--py-path", default="", help="folders for imports, separated by ':'")
    ap.add_argument("--python-bin", default="", help="ignored here; make passes it")
    a = ap.parse_args()
    if not a.model:
        print(" This lab sets no REG_MODEL, so there is no register model to build.")
        return 0

    print(f" REGCHECK  {a.model}")
    try:
        cls = load(a.lab_dir, a.model, a.py_path)
        block = cls()
        if hasattr(block, "build") and not registers(block):
            block.build()
        regs = registers(block)
    except SystemExit:
        raise
    except BaseException as e:                       # noqa: BLE001 -- any failure is the answer
        first = str(e).strip().splitlines()[0] if str(e).strip() else "(no message)"
        print(f"   the model doesn't build: {type(e).__name__}: {first}")
        return 1

    problems = []
    if not regs:
        problems.append("the model has no map with registers in it (uvm_reg_map, add_reg())")
    for name, addr, key, reg in regs:
        try:
            canonical = hex(int(str(addr), 16))
        except ValueError:
            problems.append(f"{name}: address {addr!r} isn't a hex number")
            continue
        if str(addr) != canonical:
            problems.append(f"{name}: configured at {addr!r}, which pyuvm looks up as {addr!r} in a "
                            f"map that keys it as {canonical!r}: the first access raises KeyError. "
                            f"Write it as {canonical!r}.")
    for p in problems:
        print(f"   {p}")
    if problems:
        return 1
    for name, addr, key, reg in sorted(regs, key=lambda r: int(r[2], 16)):
        fields = ", ".join(f"{f.get_name()}[{f.get_lsb_pos() + f.get_n_bits() - 1}:{f.get_lsb_pos()}] "
                           f"{f.get_access()}" for f in reg.get_fields())
        print(f"   {key:>5}  {name:<10} {fields}")
    print(f"   the model builds: {len(regs)} registers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
