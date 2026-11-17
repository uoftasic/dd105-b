"""
DD105-B reference environment: the APB agent.

  ApbItem     one transfer: data is the write data, or what a read returned
  ApbDriver   a master that keeps rules A1 to A4
  ApbMonitor  one ApbItem for every transfer that completes, whoever started it
  ApbAgent    the sequencer, the driver and the monitor
  ApbRawSeq   one transfer to any address, good or bad, outside the register model

The register model's front-door reads and writes reach the bus through this
agent's sequencer (router_ral.ApbRegAdapter), and its predictor learns every
transfer from this agent's monitor.
"""

from cocotb.triggers import FallingEdge, RisingEdge
from pyuvm import (ConfigDB, uvm_agent, uvm_analysis_port, uvm_driver, uvm_monitor, uvm_sequence,
                   uvm_sequence_item, uvm_sequencer)

from router_common import Clocked, reset_state


class ApbItem(uvm_sequence_item):
    """One APB transfer. data is the write data, or what a read returned.
    idle is the number of idle cycles the driver leaves before the setup
    cycle. The monitor fills in cycle: the cycle in which it completed."""

    def __init__(self, name="apb_item", addr=0, data=0, write=False, idle=0):
        super().__init__(name)
        self.addr, self.data, self.write, self.idle = addr, data, write, idle
        self.slverr = 0
        self.cycle = 0

    def __str__(self):
        return f"APB {'W' if self.write else 'R'} {self.addr:02x} {self.data:08x}" + \
               (" PSLVERR" if self.slverr else "")


class ApbDriver(uvm_driver, Clocked):
    """A master that keeps rules A1 to A3: a setup cycle, access cycles until
    pready, then the next transfer at once or an idle bus. It reads pready,
    prdata and pslverr at the falling edge, and the transfer completes at the
    rising edge after it.

    Rule A4: psel is 0 while rst_n is 0. The reset driver announces a reset
    one edge ahead (router_common.ResetState). This driver starts no
    transfer while one is announced, and after every rising edge of a
    transfer under way it checks whether rst_n falls at that edge; if so it
    drops psel at once, so psel is 0 from the first reset cycle. It doesn't
    stop any earlier: rule A1 holds until the reset starts, so a setup cycle
    in the last cycle before it is still followed by an access cycle. The
    transfer is abandoned and started again from its setup cycle once the
    reset is over; to the router it is just the next transfer. `restarts`
    counts them."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.rst = reset_state(self)
        self.restarts = 0

    def idle(self):
        self.dut.psel.value = 0
        self.dut.penable.value = 0

    def reset_coming(self):
        return self.rst.soon or not self.dut.rst_n.value

    def reset_now(self):
        return self.rst.starts_now() or not self.dut.rst_n.value

    async def _clear_of_reset(self):
        """Right after a rising edge, with no reset in progress or announced."""
        await self._to_edge(self.dut.clk)
        while self.reset_coming():
            self.idle()
            await RisingEdge(self.dut.clk)
            self._mark_edge()

    async def run_phase(self):
        self.idle()
        while True:
            it = await self.seq_item_port.get_next_item()
            while not await self._transfer(it):
                self.restarts += 1
            self.seq_item_port.item_done()

    async def _transfer(self, it):
        """One try at the transfer: True if it completed, False if a reset
        came first."""
        d = self.dut
        await self._clear_of_reset()
        for _ in range(it.idle):
            await RisingEdge(d.clk)
            self._mark_edge()
            if self.reset_coming():
                self.idle()
                return False
        epoch = self.rst.epoch
        d.psel.value = 1
        d.penable.value = 0
        d.pwrite.value = int(it.write)
        d.paddr.value = it.addr
        d.pwdata.value = it.data if it.write else 0
        await RisingEdge(d.clk)                      # the setup cycle ends
        while True:
            self._mark_edge()
            if self.reset_now() or self.rst.epoch != epoch:
                self.idle()
                return False
            d.penable.value = 1
            await FallingEdge(d.clk)
            if d.pready.value:
                if not it.write:
                    it.data = int(d.prdata.value)
                it.slverr = int(d.pslverr.value)
                break
            await RisingEdge(d.clk)                  # another access cycle
        await RisingEdge(d.clk)                      # the transfer completes at this edge
        self._mark_edge()
        self.idle()
        return True


class ApbMonitor(uvm_monitor):
    """Reads the APB pins at every falling edge and writes one ApbItem for
    each transfer that completes in that cycle (psel, penable and pready all
    1), with the read data or the write data, pslverr and the cycle number.
    Cycle 1 is the clock period that holds the first falling edge."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d = self.dut
        cycle = 0
        while True:
            await FallingEdge(d.clk)
            cycle += 1
            if d.rst_n.value and d.psel.value and d.penable.value and d.pready.value:
                write = bool(d.pwrite.value)
                it = ApbItem("mon", int(d.paddr.value),
                             int(d.pwdata.value) if write else int(d.prdata.value), write)
                it.slverr = int(d.pslverr.value)
                it.cycle = cycle
                self.ap.write(it)


class ApbAgent(uvm_agent):
    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = ApbDriver.create("drv", self)
        self.mon = ApbMonitor.create("mon", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


class ApbRawSeq(uvm_sequence):
    """One raw transfer, to any address: how the tests reach bad addresses,
    and write ID and LEVEL, which the register model's map has as read-only."""

    def __init__(self, name="apb_raw", addr=0, data=0, write=False, idle=0):
        super().__init__(name)
        self.item = ApbItem("raw", addr, data, write, idle)

    async def body(self):
        await self.start_item(self.item)
        await self.finish_item(self.item)
