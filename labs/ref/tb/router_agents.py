"""
DD105-B reference environment: the router's transactions, agents and raw
sequences, in pyuvm.

Timing, as router-spec.md's "Cycles and handshakes" describes it: every
driver changes the router's inputs right after a rising edge, and looks at
its outputs (in_ready, pready) at the falling edge in the middle of the
cycle, so nothing changes at the moment anything is sampled. The cycle
monitor reads every pin at every falling edge.
"""

import random

import cocotb
from cocotb.triggers import FallingEdge, RisingEdge
from cocotb.utils import get_sim_time
from pyuvm import (ConfigDB, uvm_agent, uvm_analysis_port, uvm_component, uvm_driver,
                   uvm_sequence, uvm_sequence_item, uvm_sequencer)

from router_model import Sample


# ── transactions ─────────────────────────────────────────────────────────────

class ApbItem(uvm_sequence_item):
    """One APB transfer. data is the write data, or what a read returned."""

    def __init__(self, name="apb_item", addr=0, data=0, write=False):
        super().__init__(name)
        self.addr, self.data, self.write, self.slverr = addr, data, write, 0

    def __str__(self):
        return f"APB {'W' if self.write else 'R'} {self.addr:02x} {self.data:08x}"


class PktItem(uvm_sequence_item):
    """One input packet: its beats, and the idle cycles before each beat."""

    def __init__(self, name="pkt", data=None, gaps=None):
        super().__init__(name)
        self.data = list(data or [])
        self.gaps = list(gaps) if gaps is not None else [0] * len(self.data)

    def __str__(self):
        return "PKT " + " ".join(f"{b:02x}" for b in self.data)


def make_packet(dst, length, tag=None, gap_pct=0, rng=random):
    """A packet for DST `dst`, `length` beats long (more than 8 is oversize)."""
    tag = rng.randrange(64) if tag is None else tag & 0x3F
    data = [(dst << 6) | tag] + [rng.randrange(256) for _ in range(length - 1)]
    gaps = [rng.randint(1, 3) if rng.randrange(100) < gap_pct else 0 for _ in data]
    return PktItem("pkt", data, gaps)


# ── a driver's sense of time ─────────────────────────────────────────────────

class _Clocked:
    """Lets a driver tell whether it is still right after a rising edge, so
    that items that follow each other need no idle cycle between them."""

    def _mark_edge(self):
        self._t_edge = get_sim_time("step")

    async def _to_edge(self, clk):
        if getattr(self, "_t_edge", None) != get_sim_time("step"):
            await RisingEdge(clk)
            self._mark_edge()


# ── APB ──────────────────────────────────────────────────────────────────────

class ApbDriver(uvm_driver, _Clocked):
    """A master that keeps rules A1 to A3: a setup cycle, access cycles until
    pready, then the next transfer at once or an idle bus."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")

    def idle(self):
        d = self.dut
        d.psel.value = 0
        d.penable.value = 0

    async def run_phase(self):
        d = self.dut
        self.idle()
        while True:
            it = await self.seq_item_port.get_next_item()
            await self._to_edge(d.clk)
            d.psel.value = 1
            d.penable.value = 0
            d.pwrite.value = int(it.write)
            d.paddr.value = it.addr
            d.pwdata.value = it.data if it.write else 0
            await RisingEdge(d.clk)
            d.penable.value = 1
            while True:
                await FallingEdge(d.clk)
                if d.pready.value:
                    if not it.write:
                        it.data = int(d.prdata.value)
                    it.slverr = int(d.pslverr.value)
                    break
                await RisingEdge(d.clk)
            await RisingEdge(d.clk)                  # the transfer completes at this edge
            self._mark_edge()
            self.idle()
            self.seq_item_port.item_done()


class ApbAgent(uvm_agent):
    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = ApbDriver.create("drv", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


class ApbRawSeq(uvm_sequence):
    """One raw transfer, to any address: how the tests reach bad addresses."""

    def __init__(self, name="apb_raw", addr=0, data=0, write=False):
        super().__init__(name)
        self.item = ApbItem("raw", addr, data, write)

    async def body(self):
        await self.start_item(self.item)
        await self.finish_item(self.item)


# ── the input stream ─────────────────────────────────────────────────────────

class SrcDriver(uvm_driver, _Clocked):
    """Sends each packet beat by beat, holding a beat until in_ready (rules
    I1 and I2). It gives up on a beat after MAX_WAIT cycles, logging an
    error, so a router that never takes anything can't hang the test."""

    MAX_WAIT = 2000

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.busy = False

    async def run_phase(self):
        d = self.dut
        d.in_valid.value = 0
        while True:
            pkt = await self.seq_item_port.get_next_item()
            self.busy = True
            await self._to_edge(d.clk)
            for i, beat in enumerate(pkt.data):
                for _ in range(pkt.gaps[i]):
                    d.in_valid.value = 0
                    await RisingEdge(d.clk)
                d.in_valid.value = 1
                d.in_data.value = beat
                d.in_last.value = int(i == len(pkt.data) - 1)
                for _ in range(self.MAX_WAIT):
                    await FallingEdge(d.clk)
                    if d.in_ready.value:
                        break
                    await RisingEdge(d.clk)
                else:
                    self.logger.error(f"in_ready stayed 0 for {self.MAX_WAIT} cycles; "
                                      f"abandoning {pkt}")
                    break
                await RisingEdge(d.clk)              # the beat moves at this edge
            self._mark_edge()
            d.in_valid.value = 0
            self.busy = False
            self.seq_item_port.item_done()


class SrcAgent(uvm_agent):
    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = SrcDriver.create("drv", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


class PktSeq(uvm_sequence):
    """Sends a list of PktItems, in order."""

    def __init__(self, name="pkt_seq", pkts=()):
        super().__init__(name)
        self.pkts = list(pkts)

    async def body(self):
        for p in self.pkts:
            await self.start_item(p)
            await self.finish_item(p)


# ── the outputs ──────────────────────────────────────────────────────────────

class SinkCfg:
    """How often a sink is ready. ready_pct is the chance of out_ready = 1 in
    each cycle; the tests change it while traffic runs."""

    def __init__(self, ready_pct=100):
        self.ready_pct = ready_pct


class SinkDriver(uvm_component):
    """Drives one out_ready, cycle by cycle, from its SinkCfg. The sink has no
    obligations (router-spec.md), so any pattern is legal."""

    def __init__(self, name, parent, port):
        super().__init__(name, parent)
        self.port = port

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.cfg = ConfigDB().get(self, "", f"SINK{self.port}")

    async def run_phase(self):
        rdy = getattr(self.dut, f"out{self.port}_ready")
        rdy.value = 0
        while True:
            await RisingEdge(self.dut.clk)
            pct = self.cfg.ready_pct
            rdy.value = 1 if pct >= 100 else (0 if pct <= 0 else int(random.randrange(100) < pct))


# ── the cycle monitor ────────────────────────────────────────────────────────

class CycleMonitor(uvm_component):
    """Reads every pin of the router at every falling edge and writes one
    Sample per cycle. The scoreboard's model runs on these, cycle by cycle."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")
        self.cycle = 0

    async def run_phase(self):
        d = self.dut
        handles = [(p, getattr(d, p)) for p in Sample.PINS]
        while True:
            await FallingEdge(d.clk)
            self.cycle += 1
            s = Sample(self.cycle)
            for p, h in handles:
                setattr(s, p, int(h.value))
            self.ap.write(s)
