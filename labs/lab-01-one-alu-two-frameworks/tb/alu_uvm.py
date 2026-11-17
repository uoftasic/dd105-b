"""
DD105-B Lab 01: the pyuvm testbench for SimProc's ALU.

The same job as cocotb/test_alu.py, built the UVM way: a transaction class,
sequences that make transactions, a driver that puts them on the pins, a
monitor that reads the pins back into transactions, and a scoreboard that
checks what the monitor saw. It has the same pieces as DD105-A's alu_pkg.sv
and alu_if.sv, in Python. The test is chosen when the simulator starts
(`make run TEST=AluDirectedTest`), so one build serves both tests.

  AluIf            the ALU's pins, and the period and valid flag that the
                   driver and the monitor share
  AluItem          one vector, and what the ALU answered
  AluRandSeq       N random vectors (+N=, default 2000)
  AluDirectedSeq   DD104 Lab 03's six directed vectors
  AluDriver        puts each vector on the pins for one 10 ns period
  AluMonitor       turns every period that carries a vector back into an AluItem
  AluAgent         the sequencer, the driver and the monitor
  AluScoreboard    checks each AluItem against a model of the ALU
  AluEnv           the agent and the scoreboard, connected
  AluBaseTest      builds the env; AluRandTest and AluDirectedTest
"""

import random

import cocotb
import pyuvm
from cocotb.triggers import Timer
from pyuvm import (ConfigDB, uvm_agent, uvm_analysis_port, uvm_driver, uvm_env, uvm_monitor,
                   uvm_sequence, uvm_sequence_item, uvm_sequencer, uvm_subscriber)

from dd105b_base import BaseTest

# SimProc's opcodes, the same encoding as the RTL's aluop_t. 6 and 7 are
# unassigned, and these tests don't send them.
ADD, SUB, OR, NAND, SHL, SHR = range(6)
OPS = ("ADD", "SUB", "OR", "NAND", "SHL", "SHR")


# ── the pins ─────────────────────────────────────────────────────────────────

class AluIf:
    """The ALU's pins, as the driver and the monitor see them.

    The ALU has no clock and no valid signal, because it's combinational: the
    cocotb test drives a vector, waits 1 ns and reads the answer. A UVM driver
    and monitor are separate pieces, so they need to agree on when a vector is
    on the pins. DD105-A's alu_if added a clock and a valid signal for that.
    This class adds a period and a valid flag instead. Neither one is a pin of
    the ALU, and neither shows in the waves: the period is a Timer, and valid
    is a Python attribute, which the driver sets while a vector is on the pins
    and the monitor reads.

    The driver writes each vector at the start of a 10 ns period and holds it
    for the whole period, and the monitor reads the pins 5 ns into every
    period. The sequences here send their vectors back to back from time 0,
    so every vector starts at a multiple of 10 ns, and the pins never change
    at the moment the monitor reads them.
    """

    PERIOD_NS = 10

    def __init__(self, dut):
        self.dut = dut
        self.valid = False


# ── the transaction ──────────────────────────────────────────────────────────

class AluItem(uvm_sequence_item):
    """One vector: the stimulus, which a sequence sets, and the response,
    which the monitor fills in from the pins."""

    def __init__(self, name="alu_item"):
        super().__init__(name)
        self.op, self.A, self.B = ADD, 0, 0          # the stimulus
        self.ALUout, self.N, self.Z = 0, 0, 0        # the response

    def randomize(self):
        """Draws a random vector from Python's random module, which cocotb
        seeds from SEED.

        One vector in eight has A == B, because SUB rX, rX and NAND rX, rX are
        how SimProc programs clear a register and write NOT, and uniform random
        operands would give A == B once in 256."""
        self.op = random.randrange(6)
        self.A = random.randrange(256)
        same = random.randrange(8) == 0
        self.B = self.A if same else random.randrange(256)

    def __str__(self):
        op = OPS[self.op] if self.op < len(OPS) else f"op{self.op}"
        return (f"{op} A={self.A:02x} B={self.B:02x} -> "
                f"ALUout={self.ALUout:02x} N={self.N} Z={self.Z}")


# ── the sequences ────────────────────────────────────────────────────────────

class AluRandSeq(uvm_sequence):
    """n random vectors."""

    def __init__(self, name="alu_rand_seq"):
        super().__init__(name)
        self.n = 2000

    async def body(self):
        for _ in range(self.n):
            req = AluItem.create("req")
            await self.start_item(req)
            req.randomize()
            await self.finish_item(req)


class AluDirectedSeq(uvm_sequence):
    """DD104 Lab 03's t01: one vector per operation, each with two different
    operands, because SUB(x, x) and NAND(x, x) are exactly the vectors a
    swapped subtractor and a NAND that computes NOR both get right."""

    VECTORS = [(ADD, 200, 60), (SUB, 200, 60), (OR, 0xF0, 0x0F),
               (NAND, 0xC3, 0x1D), (SHL, 0x21, 2), (SHR, 0xF8, 3)]

    async def send(self, op, a, b):
        req = AluItem.create("req")
        await self.start_item(req)
        req.op, req.A, req.B = op, a, b
        await self.finish_item(req)

    async def body(self):
        for op, a, b in self.VECTORS:
            await self.send(op, a, b)


# ── the agent: driver, monitor, sequencer ────────────────────────────────────

class AluDriver(uvm_driver):
    """Puts each vector on the pins for one period, with valid set, and
    clears valid when there is no vector."""

    def build_phase(self):
        self.vif = ConfigDB().get(self, "", "vif")
        self.n_sent = 0                  # vectors driven; AluEnv checks the count

    async def run_phase(self):
        vif, d = self.vif, self.vif.dut
        vif.valid = False
        while True:
            req = await self.seq_item_port.get_next_item()
            d.ALUop.value = req.op
            d.A.value = req.A
            d.B.value = req.B
            vif.valid = True
            self.n_sent += 1
            await Timer(vif.PERIOD_NS, "ns")
            vif.valid = False
            self.seq_item_port.item_done()


class AluMonitor(uvm_monitor):
    """Reads every pin 5 ns into each period and, in every period that
    carries a vector, writes an AluItem to its analysis port. It knows nothing
    about what the answer should be; deciding that is the scoreboard's job."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.vif = ConfigDB().get(self, "", "vif")

    async def run_phase(self):
        vif, d = self.vif, self.vif.dut
        await Timer(vif.PERIOD_NS // 2, "ns")
        while True:
            if vif.valid:
                t = AluItem.create("t")
                t.op = int(d.ALUop.value)
                t.A = int(d.A.value)
                t.B = int(d.B.value)
                t.ALUout = int(d.ALUout.value)
                t.N = int(d.N.value)
                t.Z = int(d.Z.value)
                self.ap.write(t)
            await Timer(vif.PERIOD_NS, "ns")


class AluAgent(uvm_agent):
    def build_phase(self):
        self.sqr = uvm_sequencer.create("sqr", self)
        self.drv = AluDriver.create("drv", self)
        self.mon = AluMonitor.create("mon", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


# ── the scoreboard ───────────────────────────────────────────────────────────

class AluScoreboard(uvm_subscriber):
    """Checks every vector the monitor saw against predict(), a model of the
    ALU written from SimProc's instruction set rather than from the RTL. As
    shipped, it checks ALUout and nothing else.

    pyuvm has no uvm_analysis_imp. A uvm_subscriber has an analysis_export,
    and every item written to the port it's connected to arrives in write()."""

    def build_phase(self):
        self.n_checked = 0
        self.n_bad_value = 0
        self.bad_value = [0] * 6         # value mismatches, per operation

    @staticmethod
    def predict(t):
        """What the ALU should answer, as (ALUout, N, Z). The shifts use
        B[1:0] only, so they shift by 0 to 3. N is bit 7 of the result, and Z
        is set when the result is zero; SimProc has no carry or overflow flag."""
        if t.op == ADD:
            out = (t.A + t.B) & 0xFF
        elif t.op == SUB:
            out = (t.A - t.B) & 0xFF
        elif t.op == OR:
            out = t.A | t.B
        elif t.op == NAND:
            out = ~(t.A & t.B) & 0xFF
        elif t.op == SHL:
            out = (t.A << (t.B & 3)) & 0xFF
        elif t.op == SHR:
            out = t.A >> (t.B & 3)
        else:
            out = 0
        return out, out >> 7, int(out == 0)

    def write(self, t):
        """The monitor's analysis port calls this once for every vector it sees."""
        out, n, z = self.predict(t)
        self.n_checked += 1
        if t.ALUout != out:
            self.n_bad_value += 1
            self.bad_value[t.op] += 1
            self.logger.error(f"[VALUE] {t}, expected ALUout={out:02x}")
        # TODO (Lab 01, Part 5): predict() has already worked out n and z, and
        # the monitor has filled in t.N and t.Z. Compare them too. Count flag
        # mismatches separately from value mismatches, as DD104 Lab 03's t02
        # does, log each one with self.logger.error() and a message that
        # starts with "[FLAGS]", and add the count to the line report_phase
        # prints.

    @staticmethod
    def per_op(counts):
        """The nonzero counts, as " (OP n, OP n)", or "" when every count is 0."""
        s = ", ".join(f"{OPS[i]} {c}" for i, c in enumerate(counts) if c)
        return f" ({s})" if s else ""

    def report_phase(self):
        self.logger.info(f"[SB] {self.n_checked} vectors checked: "
                         f"{self.n_bad_value} value mismatches{self.per_op(self.bad_value)}")


# ── the environment ──────────────────────────────────────────────────────────

class AluEnv(uvm_env):
    def build_phase(self):
        self.agt = AluAgent.create("agt", self)
        self.sb = AluScoreboard.create("sb", self)

    def connect_phase(self):
        self.agt.mon.ap.connect(self.sb.analysis_export)

    def check_phase(self):
        """A scoreboard that checked nothing passes, so check that it checked
        every vector the driver sent."""
        if self.sb.n_checked == 0:
            self.logger.error("[COUNT] the scoreboard checked no vectors")
        elif self.agt.drv.n_sent != self.sb.n_checked:
            self.logger.error(f"[COUNT] the driver sent {self.agt.drv.n_sent} vectors and "
                              f"the scoreboard checked {self.sb.n_checked}")


# ── the tests ────────────────────────────────────────────────────────────────

class AluBaseTest(BaseTest):
    """Puts the ALU's pins in ConfigDB, builds the environment and runs one
    sequence. BaseTest (labs/common/py/dd105b_base.py) turns any error a
    component logs into a failing test; without it, a pyuvm test whose
    scoreboard logs errors still passes."""

    def build_phase(self):
        super().build_phase()
        ConfigDB().set(None, "*", "vif", AluIf(cocotb.top))
        self.env = AluEnv.create("env", self)

    async def stimulus(self):
        pass

    async def run_phase(self):
        self.raise_objection()
        # The monitor reads each vector 5 ns into its period, and a sequence
        # ends when its last period does, so by then the scoreboard has
        # checked every vector.
        await self.stimulus()
        self.drop_objection()


@pyuvm.test()
class AluRandTest(AluBaseTest):
    """N random vectors: +N=500 changes N without a rebuild."""

    async def stimulus(self):
        seq = AluRandSeq.create("seq")
        seq.n = int(cocotb.plusargs.get("N", seq.n))
        await seq.start(self.env.agt.sqr)


@pyuvm.test()
class AluDirectedTest(AluBaseTest):
    """DD104 Lab 03's six t01 vectors."""

    async def stimulus(self):
        seq = AluDirectedSeq.create("seq")
        await seq.start(self.env.agt.sqr)
