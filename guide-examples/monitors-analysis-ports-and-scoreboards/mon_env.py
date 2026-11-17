"""
DD105-B guide example: Monitors, analysis ports and scoreboards.

A complete agent for SimProc's ALU (the sequencer and driver of the
sequences example, and a monitor), and three subscribers on the monitor's one
analysis port. The factory example builds this environment too.

  AluMonitor      reads the pins 5 ns into every period and writes a new
                  AluItem to its analysis port for each one that carries a vector
  MonAgent        the sequences example's AluAgent, with the monitor added
  AluScoreboard   checks each AluItem against a model of the ALU; it checks N
                  and Z too when ConfigDB gives it check_flags
  AluCoverage     samples each AluItem into cocotb-coverage
  AluHistory      keeps every AluItem it is given
  MonEnv          the agent and the three subscribers, connected
  MonBaseTest     builds the environment and runs one sequence; reads
                  +OVERRIDE=<class>,<class>, a factory override by name, as
                  Lab 04's base test does
"""

import cocotb
from cocotb.triggers import Timer
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from pyuvm import (ConfigDB, uvm_analysis_port, uvm_env, uvm_factory, uvm_monitor,
                   uvm_subscriber)

from dd105b_base import BaseTest
from sq_agent import AluAgent, AluIf, AluItem, AluOp, AluRandSeq


class AluMonitor(uvm_monitor):
    """Lab 01's AluMonitor: it reads every pin 5 ns into each period and, in
    every period that carries a vector, writes an AluItem to its analysis
    port. It knows nothing about what the answer should be."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.vif = ConfigDB().get(self, "", "vif")
        self.n_seen = 0

    def next_item(self):
        """A new item for every vector. A separate method only so that a
        test can swap in a monitor that gets its items another way."""
        return AluItem.create("seen")

    async def run_phase(self):
        vif, d = self.vif, self.vif.dut
        await Timer(vif.PERIOD_NS // 2, "ns")
        while True:
            if vif.valid:
                t = self.next_item()
                t.op = AluOp(int(d.ALUop.value))
                t.A = int(d.A.value)
                t.B = int(d.B.value)
                t.ALUout = int(d.ALUout.value)
                t.N = int(d.N.value)
                t.Z = int(d.Z.value)
                self.n_seen += 1
                self.ap.write(t)
            await Timer(vif.PERIOD_NS, "ns")


class MonAgent(AluAgent):
    def build_phase(self):
        super().build_phase()
        self.mon = AluMonitor.create("mon", self)


def predict(t):
    """What the ALU should answer, as (ALUout, N, Z), from SimProc's
    instruction set, as in Lab 01's scoreboard."""
    op, a, b = int(t.op), int(t.A), int(t.B)
    out = {AluOp.ADD: (a + b) & 0xFF, AluOp.SUB: (a - b) & 0xFF, AluOp.OR: a | b,
           AluOp.NAND: ~(a & b) & 0xFF, AluOp.SHL: (a << (b & 3)) & 0xFF,
           AluOp.SHR: a >> (b & 3)}[op]
    return out, out >> 7, int(out == 0)


class AluScoreboard(uvm_subscriber):
    """Checks every vector the monitor saw, inside write(). As shipped it
    compares ALUout only; with check_flags from ConfigDB it compares N and Z
    as well."""

    def build_phase(self):
        self.check_flags = ConfigDB().get(self, "", "check_flags", False)
        self.n_checked = 0
        self.n_bad = 0

    def write(self, t):
        out, n, z = predict(t)
        bad = t.ALUout != out
        if self.check_flags:
            bad = bad or t.N != n or t.Z != z
        self.n_checked += 1
        if bad:
            self.n_bad += 1
            self.logger.error(f"[SB] {t}, expected ALUout={out:02x} N={n} Z={z}")

    def check_phase(self):
        # A scoreboard that was never called reports no errors either.
        if self.n_checked == 0:
            self.logger.error("[SB] no vector was checked")

    def report_phase(self):
        flags = " with N and Z" if self.check_flags else ""
        self.logger.info(f"[SB] {self.n_checked} vectors checked{flags}: {self.n_bad} wrong")


@CoverPoint("alu.op", xf=lambda t: int(t.op), bins=list(range(6)),
            bins_labels=["add", "sub", "or_op", "nand_op", "shl", "shr"])
@CoverPoint("alu.eq", xf=lambda t: int(int(t.A) == int(t.B)), bins=[0, 1], bins_labels=["differ", "equal"])
@CoverCross("alu.x_op_eq", items=["alu.op", "alu.eq"])
def sample(t):
    pass


class AluCoverage(uvm_subscriber):
    """Samples every vector the monitor saw, and writes coverage.xml at the end."""

    def write(self, t):
        sample(t)

    def report_phase(self):
        coverage_db.export_to_xml("coverage.xml")
        g = coverage_db["alu"]
        self.logger.info(f"[COV] alu: {g.coverage} of {g.size} bins hit")


class AluHistory(uvm_subscriber):
    """Keeps every handle it is given, and at the end counts the objects
    they point at and prints the first three and the last."""

    def build_phase(self):
        self.kept = []

    def write(self, t):
        self.kept.append(t)

    def report_phase(self):
        n_obj = len({id(t) for t in self.kept})
        self.logger.info(f"[HIST] kept {len(self.kept)} handles to {n_obj} different objects")
        last = len(self.kept) - 1
        for i in (0, 1, 2, last):
            if 0 <= i <= last:
                self.logger.info(f"[HIST] vector {i}: {self.kept[i]}")


class MonEnv(uvm_env):
    def build_phase(self):
        self.agt = MonAgent.create("agt", self)
        self.sb = AluScoreboard.create("sb", self)
        self.cov = AluCoverage.create("cov", self)
        self.hist = AluHistory.create("hist", self)

    def connect_phase(self):
        self.agt.mon.ap.connect(self.sb.analysis_export)
        self.agt.mon.ap.connect(self.cov.analysis_export)
        self.agt.mon.ap.connect(self.hist.analysis_export)


class MonBaseTest(BaseTest):
    """Puts the ALU's pins in ConfigDB, builds the environment and sends N
    random vectors (+N=, default 200)."""

    def build_phase(self):
        super().build_phase()
        override = cocotb.plusargs.get("OVERRIDE")
        if override:
            original, replacement = str(override).split(",")
            uvm_factory().set_type_override_by_name(original, replacement)
            self.logger.info(f"[OVERRIDE] the factory makes {replacement} for every {original}")
        ConfigDB().set(None, "*", "vif", AluIf(cocotb.top))
        self.env = MonEnv.create("env", self)

    async def run_phase(self):
        self.raise_objection()
        seq = AluRandSeq("rand", n=int(cocotb.plusargs.get("N", 200)))
        await seq.start(self.env.agt.sqr)
        # The monitor reads each vector 5 ns into its period, so by now the
        # subscribers have every one.
        self.drop_objection()

    def report_phase(self):
        self.logger.info(f"[MON] the monitor wrote {self.env.agt.mon.n_seen} items")
