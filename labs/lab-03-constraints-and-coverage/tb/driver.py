"""
DD105-B Lab 03: the classes that drive the router's pins.

  Driver     the input stream's source: takes packets from the generator's
             queue and offers them beat by beat
  Sink       an output stream's sink: holds ready at 1 unless the test
             stalls it, and counts beats
  ApbMaster  writes and reads a register over APB

Lab 02's three classes, with two additions for this lab: the sink's stall
knob, and ApbMaster.read().

The timing rule, which every class in this testbench keeps: change the
router's inputs right after a rising edge, and look at its outputs at the
falling edge in the middle of the cycle. The router samples its inputs at the
rising edge and its outputs come from flip-flops, so at the falling edge
nothing is changing, and what you read there is the value "in this cycle",
as router-spec.md's "Cycles and handshakes" numbers cycles. A loop of the
form "drive, await FallingEdge, look, await RisingEdge" takes one clock
cycle per iteration.
"""

from cocotb.triggers import FallingEdge, RisingEdge
from cocotb.simtime import get_sim_time


class Driver:
    MAX_WAIT = 1000                 # cycles a beat may wait for in_ready

    def __init__(self, dut, from_gen, log):
        self.dut = dut
        self.from_gen = from_gen    # a cocotb.queue.Queue of Packets
        self.log = log
        self.n_pkts = 0             # what went into the router
        self.n_beats = 0
        self.n_errors = 0
        self.first_error = None     # (time in ns, message)

    def error(self, msg):
        self.n_errors += 1
        if self.first_error is None:
            self.first_error = (get_sim_time("ns"), msg)
        self.log.error(msg)

    async def run(self, n):
        """Send n packets, then return. Call it right after a rising edge. A
        beat is offered (in_valid = 1) until a cycle in which in_ready is also
        1: that cycle is the handshake, and the beat moves at the rising edge
        that ends it."""
        d = self.dut
        for _ in range(n):
            p = await self.from_gen.get()
            for i, beat in enumerate(p.data):
                if p.gaps[i]:
                    d.in_valid.value = 0
                    for _ in range(p.gaps[i]):
                        await RisingEdge(d.clk)
                d.in_valid.value = 1
                d.in_data.value = beat
                d.in_last.value = int(i == len(p.data) - 1)
                waited = 0
                while True:
                    await FallingEdge(d.clk)
                    waited += 1
                    if d.in_ready.value:
                        break
                    await RisingEdge(d.clk)
                    if waited == self.MAX_WAIT:
                        self.error(f"driver: in_ready stayed 0 for {waited} cycles with beat {i} of "
                                   f"{p} on offer; stopping")
                        d.in_valid.value = 0
                        return
                await RisingEdge(d.clk)             # the beat moves at this edge
                self.n_beats += 1
            self.n_pkts += 1
        d.in_valid.value = 0


class Sink:
    """Holds one output's ready (out0_ready or out1_ready) at 1, so every
    beat the router offers is taken in the cycle it appears, except while the
    test sets stall. Lab 03 adds stall: while it is True, ready is 0 from the
    next rising edge on."""

    def __init__(self, dut, prefix):
        self.dut = dut
        self.valid = getattr(dut, f"{prefix}_valid")
        self.ready = getattr(dut, f"{prefix}_ready")
        self.n_beats = 0            # beats the router handed over
        self.stall = False          # Lab 03: while True, ready is 0 from the next rising edge

    async def run(self):
        """Each time round the loop, the sink drives ready right after a
        rising edge, from stall as it is then, and looks at valid at the
        falling edge in the middle of the cycle that edge began. A beat is
        taken in that cycle if valid and ready are both 1."""
        while True:
            await RisingEdge(self.dut.clk)
            rdy = 0 if self.stall else 1
            self.ready.value = rdy
            await FallingEdge(self.dut.clk)
            if self.dut.rst_n.value and self.valid.value and rdy:
                self.n_beats += 1


class ApbMaster:
    def __init__(self, dut):
        self.dut = dut

    async def write(self, addr, data):
        """One write: a setup cycle, then access cycles until pready. It
        returns right after the rising edge at which the write completes."""
        d = self.dut
        await RisingEdge(d.clk)
        d.psel.value = 1
        d.penable.value = 0
        d.pwrite.value = 1
        d.paddr.value = addr
        d.pwdata.value = data
        await RisingEdge(d.clk)                     # the setup cycle ends
        d.penable.value = 1
        while True:
            await FallingEdge(d.clk)
            done = bool(d.pready.value)
            await RisingEdge(d.clk)
            if done:
                break
        d.psel.value = 0
        d.penable.value = 0

    async def read(self, addr):
        """Lab 03: one read, with the same shape as a write. It returns
        prdata as it is in the cycle the read completes, the access cycle in
        which pready is 1, right after the rising edge that ends that cycle."""
        d = self.dut
        await RisingEdge(d.clk)
        d.psel.value = 1
        d.penable.value = 0
        d.pwrite.value = 0
        d.paddr.value = addr
        await RisingEdge(d.clk)                     # the setup cycle ends
        d.penable.value = 1
        while True:
            await FallingEdge(d.clk)
            done = bool(d.pready.value)
            data = int(d.prdata.value)
            await RisingEdge(d.clk)
            if done:
                break
        d.psel.value = 0
        d.penable.value = 0
        return data

    async def wait_for_reset(self):
        """Return at the first falling edge at which rst_n is 1."""
        while True:
            await FallingEdge(self.dut.clk)
            if self.dut.rst_n.value:
                return
