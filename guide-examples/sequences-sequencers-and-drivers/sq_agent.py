"""
DD105-B guide example: Sequences, sequencers and drivers.

The pieces that take a vector from a sequence to the ALU's pins, in the
shapes of Lab 01's tb/alu_uvm.py and Lab 04's tb/router_agents.py. The
monitors and factory examples import this file too.

  AluIf            the ALU's pins, the 10 ns period and the valid flag that
                   the driver and the monitor share, as in Lab 01; with
                   trace=True the driver and the sequences print every step
  AluItem          one vector, a pyvsc randobj, as Lab 04's RouterPkt is
  AluRandSeq       n random vectors
  AluDirectedSeq   vectors whose fields the sequence sets by hand
  AluNestedSeq     a sequence that starts two others on its own sequencer
  AluOneSeq        one vector, which the caller reads back when start() returns
  AluDriver        puts each vector on the pins for one period
  AluAgent         the sequencer and the driver, connected
"""

import enum

import vsc
from cocotb.simtime import get_sim_time
from cocotb.triggers import Timer
from pyuvm import ConfigDB, uvm_agent, uvm_driver, uvm_sequence, uvm_sequence_item, uvm_sequencer


class AluOp(enum.IntEnum):
    ADD = 0
    SUB = 1
    OR = 2
    NAND = 3
    SHL = 4
    SHR = 5


class AluIf:
    """As Lab 01's AluIf: the driver holds each vector on the pins for one
    10 ns period and sets valid while it does. valid is a Python attribute,
    not a pin."""

    PERIOD_NS = 10

    def __init__(self, dut, trace=False):
        self.dut = dut
        self.valid = False
        self.trace = trace


def say(vif, who, msg):
    if vif.trace:
        print(f"{int(get_sim_time('ns')):<4} ns  [{who}]{' ' * max(1, 8 - len(who))}{msg}", flush=True)


@vsc.randobj
class AluItem(uvm_sequence_item):
    """One vector: the stimulus, which a sequence sets or randomizes, and the
    response, which the driver or the monitor fills in. One vector in eight
    has A == B, as in Lab 01."""

    def __init__(self, name="alu_item"):
        super().__init__(name)
        self.op = vsc.rand_enum_t(AluOp)
        self.A = vsc.rand_bit_t(8)
        self.B = vsc.rand_bit_t(8)
        self.same = vsc.rand_bit_t(1)
        self.tag = ""                       # the sequence that sent it
        self.ALUout, self.N, self.Z = 0, 0, 0

    @vsc.constraint
    def c_same(self):
        vsc.dist(self.same, [vsc.weight(0, 7), vsc.weight(1, 1)])
        with vsc.implies(self.same == 1):
            self.B == self.A

    def stimulus(self):
        return f"{AluOp(int(self.op)).name} A={int(self.A):02x} B={int(self.B):02x}"

    def __str__(self):
        return (f"{self.stimulus()} -> ALUout={self.ALUout:02x} N={self.N} Z={self.Z}")


class AluRandSeq(uvm_sequence):
    """n random vectors, each tagged with the sequence's label."""

    def __init__(self, name="rand", n=3):
        super().__init__(name)
        self.n = n

    async def body(self):
        vif = ConfigDB().get(None, "", "vif")
        me = f"seq {self.get_name()}"
        for _ in range(self.n):
            req = AluItem.create("req")
            req.tag = self.get_name()
            say(vif, me, "start_item(req): waiting for the driver")
            await self.start_item(req)
            say(vif, me, "start_item returned; randomize()")
            req.randomize()
            await self.finish_item(req)
            say(vif, me, f"finish_item returned: {req.tag}: {req.stimulus()} is done")


class AluDirectedSeq(uvm_sequence):
    """Vectors set by hand between start_item() and finish_item(), with no
    randomize() at all."""

    VECTORS = [(AluOp.SUB, 0x5A, 0x5A), (AluOp.SUB, 0x5A, 0x21)]

    async def body(self):
        vif = ConfigDB().get(None, "", "vif")
        for op, a, b in self.VECTORS:
            req = AluItem.create("req")
            req.tag = self.get_name()
            await self.start_item(req)
            req.op, req.A, req.B = op, a, b
            await self.finish_item(req)
            say(vif, f"seq {self.get_name()}", f"sent {req.tag}: {req.stimulus()}")


class AluNestedSeq(uvm_sequence):
    """Two random vectors, then the directed ones, both on this sequence's
    own sequencer."""

    async def body(self):
        await AluRandSeq("r", n=2).start(self.sequencer)
        await AluDirectedSeq("sub").start(self.sequencer)


class AluOneSeq(uvm_sequence):
    """One vector. The driver fills in ALUout before item_done(), and start()
    returns after finish_item() does, so the caller can read it."""

    def __init__(self, name="one", op=AluOp.ADD, a=0, b=0):
        super().__init__(name)
        self.op, self.a, self.b = op, a, b
        self.req = None

    async def body(self):
        self.req = AluItem.create("req")
        self.req.tag = self.get_name()
        await self.start_item(self.req)
        self.req.op, self.req.A, self.req.B = self.op, self.a, self.b
        await self.finish_item(self.req)


class AluDriver(uvm_driver):
    """Lab 01's AluDriver, with a line printed at every step when the
    interface traces."""

    def build_phase(self):
        self.vif = ConfigDB().get(self, "", "vif")
        self.n_sent = 0

    async def run_phase(self):
        vif, d = self.vif, self.vif.dut
        vif.valid = False
        while True:
            say(vif, "drv", "get_next_item: waiting for an item")
            req = await self.seq_item_port.get_next_item()
            say(vif, "drv", f"get_next_item returned {req.tag}: {req.stimulus()}")
            d.ALUop.value = int(req.op)
            d.A.value = int(req.A)
            d.B.value = int(req.B)
            vif.valid = True
            self.n_sent += 1
            await Timer(vif.PERIOD_NS, "ns")
            req.ALUout = int(d.ALUout.value)
            vif.valid = False
            say(vif, "drv", f"item_done, ALUout was {req.ALUout:02x}")
            self.seq_item_port.item_done()


class AluAgent(uvm_agent):
    def build_phase(self):
        super().build_phase()
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = AluDriver.create("drv", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)
