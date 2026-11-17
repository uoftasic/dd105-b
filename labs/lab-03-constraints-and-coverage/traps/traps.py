"""
DD105-B Lab 03: constraint experiments, with pyvsc and no simulator.

    make traps            run this file with the course venv's Python
    make traps SEED=2     the same with another seed

Each experiment randomizes a small pyvsc class many times and prints one
line: how often each value came out, or how often randomize() failed. Before
you run it, write down what each line should show if pyvsc follows
SystemVerilog's rules for the same constraints. Lines 1 to 3 use the shapes
of the lab's packet (three length kinds); the others are shapes its tests can
use. The numbers follow DD105-A's traps.sv, which ran the same experiments on
Verilator's solver. Change a class and run again.
"""

import argparse
import collections
import enum
import random
import time

import vsc


class LenKind(enum.IntEnum):    # the packet's three length kinds, as in tb/packet.py
    LEN_ONE = 0
    LEN_MID = 1
    LEN_MAX = 2


class Op(enum.IntEnum):         # an enum with four names, for comparison
    OP_ADD = 0
    OP_SUB = 1
    OP_AND = 2
    OP_OR = 3


# 1. A random enum that no constraint names, as kind is in tb/packet.py; then
#    an enum with four names.
@vsc.randobj
class T1Three:
    def __init__(self):
        self.dst = vsc.rand_bit_t(2)
        self.kind = vsc.rand_enum_t(LenKind)


@vsc.randobj
class T1Four:
    def __init__(self):
        self.dst = vsc.rand_bit_t(2)
        self.op = vsc.rand_enum_t(Op)


# 2. Weights 25/50/25 on the kind, written with the enum's names and as numbers.
@vsc.randobj
class T2Names:
    def __init__(self):
        self.kind = vsc.rand_enum_t(LenKind)

    @vsc.constraint
    def c_kind(self):
        vsc.dist(self.kind, [vsc.weight(LenKind.LEN_ONE, 25), vsc.weight(LenKind.LEN_MID, 50),
                             vsc.weight(LenKind.LEN_MAX, 25)])


@vsc.randobj
class T2Numbers:
    def __init__(self):
        self.kind = vsc.rand_enum_t(LenKind)

    @vsc.constraint
    def c_kind(self):
        vsc.dist(self.kind, [vsc.weight(0, 25), vsc.weight(1, 50), vsc.weight(2, 25)])


# 3. A dist on the length and a second constraint on the length; then the
#    weights on a selector, kind, with the length solved from kind and
#    constrained inline, as close_holes() could ask for a fill packet.
@vsc.randobj
class T3Len:
    def __init__(self):
        self.length = vsc.rand_uint8_t()

    @vsc.constraint
    def c_len(self):
        vsc.dist(self.length, [vsc.weight(1, 25), vsc.weight((2, 7), 50), vsc.weight(8, 25)])

    @vsc.constraint
    def c_no7(self):
        self.length != 7


@vsc.randobj
class T3Sel:
    def __init__(self):
        self.kind = vsc.rand_enum_t(LenKind)
        self.length = vsc.rand_uint8_t()

    @vsc.constraint
    def c_kind(self):
        vsc.dist(self.kind, [vsc.weight(LenKind.LEN_ONE, 25), vsc.weight(LenKind.LEN_MID, 50),
                             vsc.weight(LenKind.LEN_MAX, 25)])

    @vsc.constraint
    def c_len(self):
        with vsc.if_then(self.kind == LenKind.LEN_ONE):
            self.length == 1
        with vsc.else_if(self.kind == LenKind.LEN_MID):
            self.length.inside(vsc.rangelist((2, 7)))
        with vsc.else_then:
            self.length == 8


# 4. solve_order: make half the packets 8 beats long.
@vsc.randobj
class T4Solve:
    def __init__(self):
        self.big = vsc.rand_bit_t(1)
        self.length = vsc.rand_uint8_t()

    @vsc.constraint
    def c(self):
        with vsc.if_then(self.big == 1):
            self.length == 8
        with vsc.else_then:
            self.length.inside(vsc.rangelist((1, 7)))
        vsc.solve_order(self.big, self.length)


@vsc.randobj
class T4Plain:
    def __init__(self):
        self.big = vsc.rand_bit_t(1)
        self.length = vsc.rand_uint8_t()

    @vsc.constraint
    def c(self):
        with vsc.if_then(self.big == 1):
            self.length == 8
        with vsc.else_then:
            self.length.inside(vsc.rangelist((1, 7)))


# 5. Lengths that add up to 8: in a list of 8, and in a list whose size is
#    random too.
@vsc.randobj
class T5Fixed:
    def __init__(self):
        self.lens = vsc.rand_list_t(vsc.uint8_t(), sz=8)

    @vsc.constraint
    def c(self):
        with vsc.foreach(self.lens, idx=True) as i:
            self.lens[i] <= 8
        self.lens.sum == 8


@vsc.randobj
class T5Sized:
    def __init__(self):
        self.lens = vsc.randsz_list_t(vsc.uint8_t())

    @vsc.constraint
    def c(self):
        self.lens.size.inside(vsc.rangelist((1, 8)))
        with vsc.foreach(self.lens, idx=True) as i:
            self.lens[i].inside(vsc.rangelist((1, 8)))
        self.lens.sum == 8


# 6. unique on a list of four 4-bit values, and on four separate variables.
@vsc.randobj
class T6List:
    def __init__(self):
        self.a = vsc.rand_list_t(vsc.bit_t(4), sz=4)

    @vsc.constraint
    def c(self):
        vsc.unique(self.a)


@vsc.randobj
class T6Vars:
    def __init__(self):
        self.w = vsc.rand_bit_t(4)
        self.x = vsc.rand_bit_t(4)
        self.y = vsc.rand_bit_t(4)
        self.z = vsc.rand_bit_t(4)

    @vsc.constraint
    def c(self):
        vsc.unique(self.w, self.x, self.y, self.z)


# ── running them ─────────────────────────────────────────────────────────────

def name(v):
    return v.name if hasattr(v, "name") else str(int(v))


def counts(obj, field, n=1000):
    c = collections.Counter()
    for _ in range(n):
        obj.randomize()
        c[name(getattr(obj, field))] += 1
    return c


def line(num, label, result):
    print(f"{num}  {label:<42} {result}", flush=True)


def spread(c, names):
    return "  ".join(f"{k} {c.get(k, 0):4d}" for k in names)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    seed = ap.parse_args().seed
    random.seed(seed)
    t0 = time.time()

    kinds = [k.name for k in LenKind]
    ops = [k.name for k in Op]
    line(1, "three names, no constraint names kind", spread(counts(T1Three(), "kind"), kinds))
    line(1, "four names, no constraint names op", spread(counts(T1Four(), "op"), ops))
    line(2, "kind dist, weights on LEN_ONE ... LEN_MAX", spread(counts(T2Names(), "kind"), kinds))
    line(2, "kind dist, weights on 0, 1, 2", spread(counts(T2Numbers(), "kind"), kinds))

    def lens(c):
        return " ".join(f"{k}:{c[k]}" for k in sorted(c, key=int))

    o = T3Len()
    c = collections.Counter()
    bad = 0
    for _ in range(1000):
        try:
            o.randomize()
            c[str(int(o.length))] += 1
        except Exception:
            bad += 1
    line(3, "length dist {...} and length != 7", f"randomize() failed {bad} times in 1000; {lens(c)}")
    o = T3Sel()
    c = collections.Counter()
    bad = 0
    for _ in range(1000):
        try:
            with o.randomize_with() as it:
                it.length == 3
            c[str(int(o.length))] += 1
        except Exception:
            bad += 1
    line(3, "kind dist, length from kind, length == 3", f"randomize() failed {bad} times in 1000; {lens(c)}")

    c = counts(T4Solve(), "big")
    line(4, "solve_order(big, length)", f"big in {c.get('1', 0)} of 1000")
    c = counts(T4Plain(), "big")
    line(4, "the same without solve_order", f"big in {c.get('1', 0)} of 1000")

    for label, cls in (("lens.sum == 8, list of 8", T5Fixed), ("lens.sum == 8, list of random size", T5Sized)):
        o = cls()
        bad, ok = 0, 0
        for _ in range(20):
            try:
                o.randomize()
                ok += sum(int(x) for x in o.lens) == 8
            except Exception:
                bad += 1
        line(5, label, f"randomize() failed {bad} times in 20; the sum was 8 in {ok}")

    for label, cls, get in (("unique on a list of four 4-bit values", T6List, lambda o: [int(x) for x in o.a]),
                            ("unique on w, x, y, z", T6Vars, lambda o: [int(o.w), int(o.x), int(o.y), int(o.z)])):
        o = cls()
        rep = 0
        for _ in range(1000):
            o.randomize()
            v = get(o)
            rep += len(set(v)) != len(v)
        line(6, label, f"a value repeated in {rep} of 1000")

    o = T3Sel()
    a = time.time()
    for _ in range(500):
        o.randomize()
    b = time.time()
    for _ in range(500):
        T3Sel().randomize()
    e = time.time()
    for _ in range(100000):
        random.randint(1, 8)
    f = time.time()
    line(7, "T3Sel randomize(), per second", f"one object {500 / (b - a):.0f}; a new object each time "
                                             f"{500 / (e - b):.0f}; random.randint() {100000 / (f - e):.0f}")

    def first_lengths(reseed_before=None, reseed_after=None):
        random.seed(7)
        o = T3Sel()
        if reseed_before is not None:
            random.seed(reseed_before)
        out = []
        for k in range(6):
            if k == 1 and reseed_after is not None:
                random.seed(reseed_after)
            o.randomize()
            out.append(int(o.length))
        return out

    line(8, "seed 7, make T3Sel, 6 x randomize()", first_lengths())
    line(8, "the same, seed 99 before the first", first_lengths(reseed_before=99))
    line(8, "the same, seed 99 after the first", first_lengths(reseed_after=99))

    print("=" * 72)
    print(f" traps: {time.time() - t0:.1f} s, seed {seed}")
    print("=" * 72)


if __name__ == "__main__":
    main()
