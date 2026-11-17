"""
DD105-B guide example: Functional coverage you can read.

Each test puts random vectors on SimProc's ALU, one every 10 ns, and samples
every vector it sent into cocotb-coverage:

  alu.op       the six operations
  alu.a        three kinds of A: zero, ones, and every other value
  alu.eq       whether the two operands differed or were equal
  alu.x_op_eq  the cross of alu.op and alu.eq: 12 bins

and, in a group of their own so that alu's counts stay clean, two items that
show how cocotb-coverage counts:

  quirk.a_no_rel    alu.a written with a tuple for its range and no rel=
  quirk.op_legal    a CoverCheck that fails on an operation the ALU doesn't have

  CovPlainTest      300 vectors, A and B uniformly random
  CovBiasedTest     the same, with A == B in one vector in eight
  CovIllegalTest    CovPlainTest's vectors and one with ALUop 6 at the end
"""

import random

import cocotb
import pyuvm
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCheck, CoverCross, CoverPoint, coverage_db

from dd105b_base import BaseTest

OPS = ["add", "sub", "or_op", "nand_op", "shl", "shr"]


def in_range(value, rng):
    """rel= for a bin written as (low, high)."""
    return rng[0] <= value <= rng[1]


@CoverPoint("alu.op", xf=lambda op, a, b: op, bins=list(range(6)), bins_labels=OPS)
@CoverPoint("alu.a", xf=lambda op, a, b: a, bins=[(0, 0), (1, 254), (255, 255)], rel=in_range,
            bins_labels=["zero", "other", "ones"])
@CoverPoint("alu.eq", xf=lambda op, a, b: int(a == b), bins=[0, 1], bins_labels=["differ", "equal"])
@CoverCross("alu.x_op_eq", items=["alu.op", "alu.eq"])
@CoverPoint("quirk.a_no_rel", xf=lambda op, a, b: a, bins=[0, (1, 254), 255],
            bins_labels=["zero", "other", "ones"])
@CoverCheck("quirk.op_legal", f_fail=lambda op, a, b: op > 5, f_pass=lambda op, a, b: True)
def sample(op, a, b):
    pass


def line(name):
    item = coverage_db[name]
    return f"{name}: {item.coverage} of {item.size} bins, {item.cover_percentage:.2f}%"


class CovBaseTest(BaseTest):
    N = 300
    SAME = 0          # 1 in SAME vectors has A == B; 0 leaves B uniform
    EXTRA = []        # (op, A, B) vectors sent after the random ones

    async def run_phase(self):
        self.raise_objection()
        dut = cocotb.top
        vectors = []
        for _ in range(self.N):
            op, a = random.randrange(6), random.randrange(256)
            b = a if self.SAME and random.randrange(self.SAME) == 0 else random.randrange(256)
            vectors.append((op, a, b))
        vectors += self.EXTRA
        n_eq = 0
        for op, a, b in vectors:
            dut.ALUop.value, dut.A.value, dut.B.value = op, a, b
            await Timer(10, "ns")
            sample(op, a, b)
            n_eq += a == b
        print(f"[COV] {len(vectors)} vectors, {n_eq} with A == B", flush=True)
        for name in ("alu", "alu.op", "alu.a", "alu.eq", "alu.x_op_eq", "quirk",
                     "quirk.a_no_rel", "quirk.op_legal"):
            print(f"[COV] {line(name)}", flush=True)
        cross = coverage_db["alu.x_op_eq"].detailed_coverage
        for eq in ("differ", "equal"):
            print(f"[COV] x_op_eq, {eq:6}: " + "  ".join(f"{op} {cross[(op, eq)]:3}" for op in OPS),
                  flush=True)
        print(f"[COV] quirk.a_no_rel: {coverage_db['quirk.a_no_rel'].detailed_coverage}", flush=True)
        print(f"[COV] quirk.op_legal: {coverage_db['quirk.op_legal'].detailed_coverage}", flush=True)
        coverage_db.export_to_xml("coverage.xml")
        self.drop_objection()


@pyuvm.test()
class CovPlainTest(CovBaseTest):
    pass


@pyuvm.test()
class CovBiasedTest(CovBaseTest):
    SAME = 8


@pyuvm.test()
class CovIllegalTest(CovBaseTest):
    EXTRA = [(6, 0x12, 0x34)]
