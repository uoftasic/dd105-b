"""
DD105-B guide example: Constrained random with pyvsc.

Each test randomizes a small pyvsc class, most of them shaped like one vector
for SimProc's ALU, and prints what came out. The tests derive from the
course's BaseTest only so that `make run` grades them as it grades a lab's
tests; none of them drives the ALU.

  CrItemTest    randomize(), randomize_with(), a call that can't be met,
                and constraint_mode()
  CrSkewTest    how often each operation comes out, with and without a
                constraint that ties B to the shifts
  CrAttrTest    a constraint that reads a plain Python attribute, and one
                that reads a vsc.uint8_t attribute
  CrDistTest    dist, then randomize_with() on the same variable, and on a
                variable that depends on it
  CrSoftTest    soft constraints, against an inline constraint and each other
  CrSolveTest   solve_order()
  CrSeedTest    which random state an object takes, and when
  CrSpeedTest   randomizations per second
"""

import enum
import random
import time
from collections import Counter

import pyuvm
import vsc
from vsc.model.solve_failure import SolveFailure

from dd105b_base import BaseTest

N = 1000


def say(msg):
    print(msg, flush=True)


class AluOp(enum.IntEnum):
    ADD = 0
    SUB = 1
    OR = 2
    NAND = 3
    SHL = 4
    SHR = 5


@vsc.randobj
class AluVec:
    """One ALU vector. SimProc's shifts use only B[1:0], so c_shift keeps B
    below 4 whenever the operation is a shift, and leaves it free otherwise."""

    def __init__(self):
        self.op = vsc.rand_enum_t(AluOp)
        self.A = vsc.rand_bit_t(8)
        self.B = vsc.rand_bit_t(8)

    @vsc.constraint
    def c_shift(self):
        with vsc.implies(self.op.inside(vsc.rangelist(AluOp.SHL, AluOp.SHR))):
            self.B < 4

    def __str__(self):
        return f"{AluOp(int(self.op)).name:4} A={int(self.A):02x} B={int(self.B):02x}"


def op_counts(values):
    c = Counter(values)
    return "  ".join(f"{op.name} {c.get(op, 0):3}" for op in AluOp)


@pyuvm.test()
class CrItemTest(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        v = AluVec()
        for _ in range(4):
            v.randomize()
            say(f"[ITEM] randomize():                         {v}")
        for _ in range(2):
            with v.randomize_with() as it:
                it.op == AluOp.SUB
                it.A == it.B
            say(f"[ITEM] randomize_with(op == SUB, A == B):   {v}")
        say(f"[ITEM] before:                              {v}")
        try:
            with v.randomize_with() as it:
                it.op == AluOp.SHL
                it.B == 5
            say(f"[ITEM] randomize_with(op == SHL, B == 5):   {v}")
        except SolveFailure as e:
            say(f"[ITEM] randomize_with(op == SHL, B == 5) raised {type(e).__name__}: {e}")
            say(f"[ITEM] after:                               {v}")
        v.c_shift.constraint_mode(False)
        with v.randomize_with() as it:
            it.op == AluOp.SHL
            it.B == 5
        say(f"[ITEM] the same with c_shift off:           {v}")
        self.drop_objection()


@vsc.randobj
class AluVecFree:
    """AluVec without c_shift."""

    def __init__(self):
        self.op = vsc.rand_enum_t(AluOp)
        self.A = vsc.rand_bit_t(8)
        self.B = vsc.rand_bit_t(8)


@pyuvm.test()
class CrSkewTest(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        free, v = AluVecFree(), AluVec()
        ops, b_small = [], 0
        for _ in range(N):
            free.randomize()
            ops.append(int(free.op))
            b_small += int(free.B) < 4
        say(f"[SKEW] no constraint:     {op_counts(ops)}   B < 4 in {b_small}")
        ops, b_small = [], 0
        for _ in range(N):
            v.randomize()
            ops.append(int(v.op))
            b_small += int(v.B) < 4
        say(f"[SKEW] with c_shift:      {op_counts(ops)}   B < 4 in {b_small}")
        self.drop_objection()


@vsc.randobj
class Limited:
    """Two limits on A: one a plain Python int, one a vsc.uint8_t."""

    def __init__(self):
        self.A = vsc.rand_bit_t(8)
        self.B = vsc.rand_bit_t(8)
        self.a_max = 4                 # a plain Python attribute
        self.b_max = vsc.uint8_t(4)    # a non-random pyvsc attribute

    @vsc.constraint
    def c_lim(self):
        self.A < self.a_max
        self.B < self.b_max


@pyuvm.test()
class CrAttrTest(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        p = Limited()
        a, b = [], []
        for _ in range(200):
            p.randomize()
            a.append(int(p.A))
            b.append(int(p.B))
        say(f"[ATTR] a_max = 4, b_max = 4, 200 draws:     the largest A {max(a)}, the largest B {max(b)}")
        p.a_max = 200
        p.b_max = 200
        a, b = [], []
        for _ in range(200):
            p.randomize()
            a.append(int(p.A))
            b.append(int(p.B))
        say(f"[ATTR] a_max = 200, b_max = 200, 200 draws: the largest A {max(a)}, the largest B {max(b)}")
        self.drop_objection()


@vsc.randobj
class AluVecWeighted:
    """AluVec with ADD five times as likely as each other operation."""

    def __init__(self):
        self.op = vsc.rand_enum_t(AluOp)
        self.A = vsc.rand_bit_t(8)
        self.B = vsc.rand_bit_t(8)

    @vsc.constraint
    def c_op(self):
        vsc.dist(self.op, [vsc.weight(AluOp.ADD, 5), vsc.weight(AluOp.SUB, 1),
                           vsc.weight(AluOp.OR, 1), vsc.weight(AluOp.NAND, 1),
                           vsc.weight(AluOp.SHL, 1), vsc.weight(AluOp.SHR, 1)])


class Kind(enum.IntEnum):
    K_ZERO = 0      # A is 00
    K_ONES = 1      # A is ff
    K_SAME = 2      # A equals B
    K_ANY = 3       # A is free


@vsc.randobj
class VecKind:
    """A dist on a selector, kind, and A chosen from kind."""

    def __init__(self):
        self.kind = vsc.rand_enum_t(Kind)
        self.A = vsc.rand_bit_t(8)
        self.B = vsc.rand_bit_t(8)

    @vsc.constraint
    def c_kind(self):
        vsc.dist(self.kind, [vsc.weight(Kind.K_ZERO, 10), vsc.weight(Kind.K_ONES, 20),
                             vsc.weight(Kind.K_SAME, 30), vsc.weight(Kind.K_ANY, 40)])

    @vsc.constraint
    def c_A(self):
        with vsc.if_then(self.kind == Kind.K_ZERO):
            self.A == 0x00
        with vsc.else_if(self.kind == Kind.K_ONES):
            self.A == 0xFF
        with vsc.else_if(self.kind == Kind.K_SAME):
            self.A == self.B


def kind_counts(values):
    c = Counter(values)
    return "  ".join(f"{k.name} {c.get(k, 0):3}" for k in Kind)


@pyuvm.test()
class CrDistTest(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        w = AluVecWeighted()
        ops = []
        for _ in range(N):
            w.randomize()
            ops.append(int(w.op))
        say(f"[DIST] op dist ADD 5, others 1:                   {op_counts(ops)}")
        fails, ops = 0, []
        for _ in range(N):
            try:
                with w.randomize_with() as it:
                    it.op == AluOp.SUB
                ops.append(int(w.op))
            except SolveFailure:
                fails += 1
        say(f"[DIST] the same, then randomize_with(op == SUB):  failed {fails} times in {N}; {op_counts(ops)}")
        k = VecKind()
        kinds = []
        for _ in range(N):
            k.randomize()
            kinds.append(int(k.kind))
        say(f"[DIST] kind dist 10/20/30/40:                     {kind_counts(kinds)}")
        fails, kinds = 0, []
        for _ in range(N):
            try:
                with k.randomize_with() as it:
                    it.A < 0x10
                kinds.append(int(k.kind))
            except SolveFailure:
                fails += 1
        say(f"[DIST] the same, then randomize_with(A < 0x10):   failed {fails} times in {N}; {kind_counts(kinds)}")
        self.drop_objection()


@vsc.randobj
class SoftVec:
    """B is 1 unless something else says otherwise, and A has two soft
    constraints that disagree."""

    def __init__(self):
        self.A = vsc.rand_bit_t(8)
        self.B = vsc.rand_bit_t(8)

    @vsc.constraint
    def c_b(self):
        vsc.soft(self.B == 1)

    @vsc.constraint
    def c_a(self):
        vsc.soft(self.A == 0x11)
        vsc.soft(self.A == 0x22)


@pyuvm.test()
class CrSoftTest(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        s = SoftVec()
        seen = Counter()
        for _ in range(100):
            s.randomize()
            seen[(int(s.A), int(s.B))] += 1
        say("[SOFT] randomize(), 100 times:              " +
            ", ".join(f"A={a:02x} B={b:02x} x{n}" for (a, b), n in sorted(seen.items())))
        seen = Counter()
        fails = 0
        for _ in range(100):
            try:
                with s.randomize_with() as it:
                    it.B == 7
                seen[(int(s.A), int(s.B))] += 1
            except SolveFailure:
                fails += 1
        say(f"[SOFT] randomize_with(B == 7), 100 times:   failed {fails}; " +
            ", ".join(f"A={a:02x} B={b:02x} x{n}" for (a, b), n in sorted(seen.items())))
        self.drop_objection()


@vsc.randobj
class ShiftSel:
    """is_shift picks the two shifts or the other four operations."""

    def __init__(self):
        self.is_shift = vsc.rand_bit_t(1)
        self.op = vsc.rand_enum_t(AluOp)

    @vsc.constraint
    def c_sel(self):
        with vsc.if_then(self.is_shift == 1):
            self.op.inside(vsc.rangelist(AluOp.SHL, AluOp.SHR))
        with vsc.else_then:
            self.op.inside(vsc.rangelist(AluOp.ADD, AluOp.SUB, AluOp.OR, AluOp.NAND))


@vsc.randobj
class ShiftSelOrdered(ShiftSel):
    """ShiftSel, with is_shift solved before op."""

    @vsc.constraint
    def c_order(self):
        vsc.solve_order(self.is_shift, self.op)


@pyuvm.test()
class CrSolveTest(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        for label, s in (("solve_order(is_shift, op):", ShiftSelOrdered()),
                         ("without solve_order:      ", ShiftSel())):
            shifts, ops = 0, []
            for _ in range(N):
                s.randomize()
                shifts += int(s.is_shift)
                ops.append(int(s.op))
            say(f"[SOLVE] {label} is_shift in {shifts} of {N};   {op_counts(ops)}")
        self.drop_objection()


def names(v, n, reseed_after_first=None):
    """n randomizations of v, as op names. With reseed_after_first, Python's
    random is seeded again with it after the first one."""
    out = []
    for i in range(n):
        v.randomize()
        out.append(AluOp(int(v.op)).name)
        if i == 0 and reseed_after_first is not None:
            random.seed(reseed_after_first)
    return " ".join(out)


@pyuvm.test()
class CrSeedTest(BaseTest):
    """Three rows, each starting from the random state the test started with."""

    async def run_phase(self):
        self.raise_objection()
        start = random.getstate()
        v = AluVecFree()
        say(f"[SEED] make, then randomize() 6 times:          {names(v, 6)}")
        random.setstate(start)
        v = AluVecFree()
        random.seed(99)
        say(f"[SEED] make, random.seed(99), then randomize(): {names(v, 6)}")
        random.setstate(start)
        v = AluVecFree()
        say(f"[SEED] make, randomize(), random.seed(99), ...: {names(v, 6, reseed_after_first=99)}")
        self.drop_objection()


@pyuvm.test()
class CrSpeedTest(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        v = AluVec()
        t = time.perf_counter()
        for _ in range(N):
            v.randomize()
        one = N / (time.perf_counter() - t)
        t = time.perf_counter()
        for _ in range(N):
            AluVec().randomize()
        new = N / (time.perf_counter() - t)
        t = time.perf_counter()
        for _ in range(100 * N):
            random.randrange(6), random.randrange(256), random.randrange(256)
        plain = 100 * N / (time.perf_counter() - t)
        say(f"[SPEED] per second: randomize() on one AluVec {one:.0f}; a new AluVec each time {new:.0f}; "
            f"three random.randrange() calls {plain:.0f}")
        self.drop_objection()
