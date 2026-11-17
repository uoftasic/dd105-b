"""
DD105-B guide example for "From cocotb tests to pyuvm components".

  T01Test          DD104 Lab 03's t01, written as one pyuvm test: the same six
                   vectors, spec() and alu(), with every check in run_phase
  T01UvmTest       the same run_phase in a test derived from pyuvm's uvm_test
                   instead of the course's BaseTest
  PhaseOrderTest   a test, an environment and two components that print a line
                   in every phase, so the log shows the order pyuvm calls them in
  NoObjectionTest  the same tree, with a run_phase that never raises an objection

spec() and alu() are copied from labs/lab-01-one-alu-two-frameworks/cocotb/test_alu.py,
which is DD104 Lab 03's reference test.
"""

import cocotb
import pyuvm
from cocotb.simtime import get_sim_time
from cocotb.triggers import Timer
from pyuvm import uvm_component, uvm_env, uvm_test

from dd105b_base import BaseTest

ADD, SUB, OR, NAND, SHL, SHR = 0, 1, 2, 3, 4, 5
OPS = {ADD: "ADD", SUB: "SUB", OR: "OR", NAND: "NAND", SHL: "SHL", SHR: "SHR"}

CASES = [(ADD, 200, 60), (SUB, 200, 60), (OR, 0xF0, 0x0F),
         (NAND, 0xC3, 0x1D), (SHL, 0x21, 2), (SHR, 0xF8, 3)]


def spec(op, a, b):
    """What the ALU is supposed to produce: (out, N, Z)."""
    if op == ADD:
        out = (a + b) & 0xFF
    elif op == SUB:
        out = (a - b) & 0xFF
    elif op == OR:
        out = a | b
    elif op == NAND:
        out = (~(a & b)) & 0xFF
    elif op == SHL:
        out = (a << (b & 3)) & 0xFF
    elif op == SHR:
        out = a >> (b & 3)
    else:
        out = 0
    return out, (out >> 7) & 1, int(out == 0)


async def alu(dut, op, a, b):
    """Drive one vector and read the three outputs back."""
    dut.ALUop.value = op
    dut.A.value = a
    dut.B.value = b
    await Timer(1, unit="ns")
    return int(dut.ALUout.value), int(dut.N.value), int(dut.Z.value)


# ── t01 as one pyuvm test ────────────────────────────────────────────────────

@pyuvm.test()
class T01Test(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        dut = cocotb.top
        for op, a, b in CASES:
            got = await alu(dut, op, a, b)
            want = spec(op, a, b)
            if got != want:
                self.logger.error(
                    f"{OPS[op]}(0x{a:02X}, 0x{b:02X}) gave out=0x{got[0]:02X} "
                    f"N={got[1]} Z={got[2]}, expected out=0x{want[0]:02X} "
                    f"N={want[1]} Z={want[2]}")
        self.logger.info(f"[T01] {len(CASES)} directed vectors checked")
        self.drop_objection()


@pyuvm.test()
class T01UvmTest(uvm_test):
    # T01Test's run_phase, line for line, in a test derived from uvm_test.
    # (A comment rather than a docstring: cocotb prints a test's docstring.)
    async def run_phase(self):
        self.raise_objection()
        dut = cocotb.top
        for op, a, b in CASES:
            got = await alu(dut, op, a, b)
            want = spec(op, a, b)
            if got != want:
                self.logger.error(
                    f"{OPS[op]}(0x{a:02X}, 0x{b:02X}) gave out=0x{got[0]:02X} "
                    f"N={got[1]} Z={got[2]}, expected out=0x{want[0]:02X} "
                    f"N={want[1]} Z={want[2]}")
        self.logger.info(f"[T01] {len(CASES)} directed vectors checked")
        self.drop_objection()


# ── the order of the phases ──────────────────────────────────────────────────

def say(comp, phase):
    print(f"{get_sim_time('ns'):4.0f} ns  {phase:<26} {comp.get_full_name()}", flush=True)


class Shows(uvm_component):
    """A component that prints a line in every phase except run_phase."""

    def build_phase(self):
        say(self, "build_phase")

    def connect_phase(self):
        say(self, "connect_phase")

    def end_of_elaboration_phase(self):
        say(self, "end_of_elaboration_phase")

    def start_of_simulation_phase(self):
        say(self, "start_of_simulation_phase")

    def extract_phase(self):
        say(self, "extract_phase")

    def check_phase(self):
        say(self, "check_phase")

    def report_phase(self):
        say(self, "report_phase")

    def final_phase(self):
        say(self, "final_phase")


class Ticker(Shows):
    """Counts the 10 ns ticks of its run_phase, which never returns."""

    def build_phase(self):
        super().build_phase()
        self.ticks = 0

    async def run_phase(self):
        say(self, "run_phase starts")
        while True:
            await Timer(10, unit="ns")
            self.ticks += 1

    def report_phase(self):
        super().report_phase()
        print(f"           {self.get_full_name()} counted {self.ticks} ticks", flush=True)


class Quiet(Shows):
    """Its run_phase returns at once."""

    async def run_phase(self):
        say(self, "run_phase starts")


class DemoEnv(uvm_env, Shows):
    def build_phase(self):
        Shows.build_phase(self)
        self.drv = Ticker.create("drv", self)
        self.sb = Quiet.create("sb", self)

    async def run_phase(self):
        say(self, "run_phase starts")


class PhaseDemoTest(BaseTest, Shows):
    """BaseTest's own end_of_elaboration, start_of_simulation and final phases
    still run, through super()."""

    def build_phase(self):
        Shows.build_phase(self)
        self.env = DemoEnv.create("env", self)

    def end_of_elaboration_phase(self):
        Shows.end_of_elaboration_phase(self)
        super().end_of_elaboration_phase()

    def start_of_simulation_phase(self):
        Shows.start_of_simulation_phase(self)
        super().start_of_simulation_phase()

    def final_phase(self):
        Shows.final_phase(self)
        super().final_phase()


@pyuvm.test()
class PhaseOrderTest(PhaseDemoTest):
    async def run_phase(self):
        say(self, "run_phase starts")
        self.raise_objection()
        await Timer(35, unit="ns")
        say(self, "drop_objection()")
        self.drop_objection()


@pyuvm.test()
class NoObjectionTest(PhaseDemoTest):
    async def run_phase(self):
        say(self, "run_phase starts")
        await Timer(35, unit="ns")
        say(self, "the stimulus is done")
