"""
DD105-B guide example: the tests for Sequences, sequencers and drivers.

  SqTimelineTest   one sequence of three random vectors, every step printed
  SqTwoTest        two sequences of two vectors each, on one sequencer at once
  SqNestedTest     a sequence that starts two others
  SqReadTest       the test sends single vectors and reads back each answer
  SqDoubleGetTest  a driver that calls get_next_item() twice without item_done()
"""

import cocotb
import pyuvm
from cocotb.triggers import Combine
from pyuvm import ConfigDB, uvm_agent, uvm_driver, uvm_env, uvm_sequencer

from dd105b_base import BaseTest
from sq_agent import AluAgent, AluIf, AluNestedSeq, AluOneSeq, AluOp, AluRandSeq


class SqEnv(uvm_env):
    def build_phase(self):
        self.agt = AluAgent.create("agt", self)


class SqBaseTest(BaseTest):
    TRACE = True

    def build_phase(self):
        super().build_phase()
        ConfigDB().set(None, "*", "vif", AluIf(cocotb.top, trace=self.TRACE))
        self.env = SqEnv.create("env", self)

    async def run_phase(self):
        self.raise_objection()
        await self.body()
        self.drop_objection()


@pyuvm.test()
class SqTimelineTest(SqBaseTest):
    async def body(self):
        await AluRandSeq("a", n=3).start(self.env.agt.sqr)


@pyuvm.test()
class SqTwoTest(SqBaseTest):
    async def body(self):
        a = cocotb.start_soon(AluRandSeq("a", n=2).start(self.env.agt.sqr))
        b = cocotb.start_soon(AluRandSeq("b", n=2).start(self.env.agt.sqr))
        await Combine(a, b)


@pyuvm.test()
class SqNestedTest(SqBaseTest):
    async def body(self):
        await AluNestedSeq("nest").start(self.env.agt.sqr)


@pyuvm.test()
class SqReadTest(SqBaseTest):
    TRACE = False

    async def alu(self, op, a, b):
        """One vector through the agent, as Lab 04's read_reg() is one APB
        read: returns what the ALU answered."""
        s = AluOneSeq("one", op, a, b)
        await s.start(self.env.agt.sqr)
        return s.req.ALUout

    async def body(self):
        for op, a, b in ((AluOp.SUB, 0xC8, 0x3C), (AluOp.NAND, 0xC3, 0x1D), (AluOp.SHR, 0xF8, 3)):
            out = await self.alu(op, a, b)
            print(f"[READ] {op.name}({a:02x}, {b:02x}) = {out:02x}", flush=True)


class GreedyDriver(uvm_driver):
    """Asks for a second item before it has finished the first."""

    async def run_phase(self):
        await self.seq_item_port.get_next_item()
        await self.seq_item_port.get_next_item()


class GreedyAgent(uvm_agent):
    def build_phase(self):
        super().build_phase()
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = GreedyDriver("drv", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


@pyuvm.test(timeout_time=1, timeout_unit="us")
class SqDoubleGetTest(SqBaseTest):
    TRACE = False

    def build_phase(self):
        super().build_phase()
        self.greedy = GreedyAgent("greedy", self)

    async def body(self):
        await AluRandSeq("a", n=2).start(self.greedy.sqr)
