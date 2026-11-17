"""
DD105-B guide example, "Virtual sequences": a source agent and a sink for
fifo4.sv, and a virtual sequence that steers both from one place.

  SrcItem, SrcSeq, SrcDriver, SrcAgent
              the input side: SrcSeq sends n beats numbered from `base`,
              one item per beat
  SnkCfg      the sink's one knob, ready_pct, which SnkDriver reads in
              every cycle; the sink has no sequencer
  FifoMonitor checks every beat that comes out against the order the beats
              went in, whatever is driving the FIFO
  FifoEnv     the agents, the sink, the monitor and the knob
  DemoVseq    the virtual sequence. pyuvm has no p_sequencer: the sequence
              is given the environment when it is made, and it runs on no
              sequencer of its own
  VseqTest    runs DemoVseq; with +SERIAL its first step runs the release
              after the send instead of beside it
  VseqItemTest  a virtual sequence that calls start_item() itself

The drivers change the FIFO's inputs right after a rising edge, and the
monitor reads the pins at the falling edge, the course's timing rule.
"""

import random
from collections import deque

import cocotb
import pyuvm
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, First, RisingEdge
from pyuvm import (ConfigDB, uvm_agent, uvm_component, uvm_driver, uvm_sequence,
                   uvm_sequence_item, uvm_sequencer)

from dd105b_base import BaseTest


# ── the source ───────────────────────────────────────────────────────────────

class SrcItem(uvm_sequence_item):
    def __init__(self, name="src_item", data=0):
        super().__init__(name)
        self.data = data


class SrcSeq(uvm_sequence):
    """n beats, numbered from base."""

    def __init__(self, name="src_seq", n=1, base=0):
        super().__init__(name)
        self.n, self.base = n, base

    async def body(self):
        for i in range(self.n):
            it = SrcItem("src_item")
            await self.start_item(it)
            it.data = (self.base + i) & 0xFF
            await self.finish_item(it)


class SrcDriver(uvm_driver):
    """Puts each item on the input until the FIFO takes it."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d = self.dut
        while True:
            it = await self.seq_item_port.get_next_item()
            if not d.clk.value:                 # drive only right after a rising edge
                await RisingEdge(d.clk)
            d.in_valid.value = 1
            d.in_data.value = it.data
            while True:
                await FallingEdge(d.clk)
                taken = bool(d.in_ready.value)
                await RisingEdge(d.clk)
                if taken:
                    break
            d.in_valid.value = 0
            self.seq_item_port.item_done()


class SrcAgent(uvm_agent):
    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = SrcDriver.create("drv", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


# ── the sink ─────────────────────────────────────────────────────────────────

class SnkCfg:
    def __init__(self):
        self.ready_pct = 100        # percent of cycles out_ready is 1; 0 stalls the FIFO's output


class SnkDriver(uvm_component):
    """Right after every rising edge, out_ready is 1 with probability
    ready_pct percent. It has no sequencer: the knob is all there is."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.cfg = ConfigDB().get(self, "", "snk_cfg")

    async def run_phase(self):
        d, cfg = self.dut, self.cfg
        while True:
            await RisingEdge(d.clk)
            p = cfg.ready_pct
            d.out_ready.value = 1 if p >= 100 else 0 if p <= 0 else int(random.randrange(100) < p)


# ── the checker and the environment ──────────────────────────────────────────

class FifoMonitor(uvm_component):
    """At every falling edge: a beat going in joins the queue of expected
    beats, and a beat coming out must be the oldest one in it."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.expect = deque()
        self.n_in = self.n_out = self.n_bad = 0
        self.taken = []             # every beat that came out, in order

    async def run_phase(self):
        d = self.dut
        while True:
            await FallingEdge(d.clk)
            if not d.rst_n.value:
                continue
            if d.in_valid.value and d.in_ready.value:
                self.expect.append(int(d.in_data.value))
                self.n_in += 1
            if d.out_valid.value and d.out_ready.value:
                got = int(d.out_data.value)
                want = self.expect.popleft() if self.expect else None
                self.n_out += 1
                self.taken.append(got)
                if got != want:
                    self.n_bad += 1
                    self.logger.error(f"[MON] got {got:02x}, expected {want}")

    def report_phase(self):
        self.logger.info(f"[MON] {self.n_in} beats in, {self.n_out} out, {self.n_bad} out of order")


class FifoEnv(uvm_component):
    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.snk_cfg = SnkCfg()
        ConfigDB().set(self, "*", "snk_cfg", self.snk_cfg)
        self.src = SrcAgent.create("src", self)
        self.snk = SnkDriver.create("snk", self)
        self.mon = FifoMonitor.create("mon", self)


# ── the virtual sequences ────────────────────────────────────────────────────

class BaseVseq(uvm_sequence):
    """Handles the steps need, from the environment it is given. A pyuvm
    sequence has no logger, so it reports through the environment's."""

    def __init__(self, name="vseq", env=None):
        super().__init__(name)
        self.env = env
        self.traffic_done = False

    def info(self, msg):
        self.env.logger.info(f"[VSEQ] {msg}")

    @staticmethod
    async def par(*coros):
        """Start every coroutine at once and wait until all of them are done."""
        tasks = [cocotb.start_soon(c) for c in coros]
        for t in tasks:
            await t

    async def cycles(self, n):
        for _ in range(n):
            await RisingEdge(self.env.dut.clk)

    async def send(self, n, base):
        """n beats through the source agent, numbered from base. Returns when
        the last one has gone into the FIFO."""
        await SrcSeq(f"src_{base:02x}", n, base).start(self.env.src.sqr)

    def sink(self, pct):
        """The sink's readiness from the next rising edge on."""
        self.env.snk_cfg.ready_pct = pct
        self.info(f"sink ready {pct}% of cycles")

    async def drain(self):
        self.sink(100)
        while self.env.mon.expect:
            await self.cycles(1)


class DemoVseq(BaseVseq):
    async def body(self):
        d = self.env.dut

        # Step 1: the sink stalled while six beats go into a FIFO that holds
        # four, and a second branch that lets the sink go.
        self.sink(0)
        if "SERIAL" in cocotb.plusargs:
            await self.send(6, 0x10)
            self.sink(100)
        else:
            async def beats():
                await self.send(6, 0x10)
                self.info("step 1: all 6 beats have gone in")

            async def release():
                await self.cycles(15)
                self.info(f"step 1: the FIFO holds {int(d.level.value)} beats")
                self.sink(100)

            await self.par(beats(), release())

        # Step 2: 30 beats while another branch keeps changing the sink, until
        # the traffic branch says it's done.
        self.traffic_done = False

        async def traffic():
            await self.send(30, 0x40)
            self.traffic_done = True
            self.info("step 2: all 30 beats have gone in")

        async def backpressure():
            while not self.traffic_done:
                self.sink(random.choice([0, 30, 100]))
                await self.cycles(random.randint(4, 12))

        await self.par(traffic(), backpressure())
        await self.drain()

        # Step 3: two sequences on the source's sequencer at once.
        first = len(self.env.mon.taken)
        await self.par(self.send(4, 0x80), self.send(4, 0xA0))
        await self.drain()
        took = " ".join(f"{b:02x}" for b in self.env.mon.taken[first:])
        self.info(f"step 3: the sink took {took}")


class ItemVseq(BaseVseq):
    """A virtual sequence that tries to send an item itself."""

    async def body(self):
        it = SrcItem("src_item", 0x55)
        await self.start_item(it)
        await self.finish_item(it)


# ── the tests ────────────────────────────────────────────────────────────────

class VseqBaseTest(BaseTest):
    VSEQ = DemoVseq

    def build_phase(self):
        ConfigDB().set(None, "*", "DUT", cocotb.top)
        self.env = FifoEnv.create("env", self)

    async def run_phase(self):
        self.raise_objection()
        d = cocotb.top
        d.rst_n.value = 0
        d.in_valid.value = 0
        d.in_data.value = 0
        d.out_ready.value = 0
        cocotb.start_soon(Clock(d.clk, 10, unit="ns").start())
        for _ in range(2):
            await RisingEdge(d.clk)
        d.rst_n.value = 1
        # The virtual sequence runs on no sequencer: start() with no argument.
        v = cocotb.start_soon(self.VSEQ("v", self.env).start())
        await First(v.complete, ClockCycles(d.clk, 2000))
        if not v.done():
            self.logger.error(f"[TEST] the virtual sequence is still running after 2000 cycles; "
                              f"the FIFO holds {int(d.level.value)} beats")
            v.cancel()
        else:
            v.result()          # re-raises anything the sequence raised
        self.drop_objection()


@pyuvm.test()
class VseqTest(VseqBaseTest):
    VSEQ = DemoVseq


@pyuvm.test()
class VseqItemTest(VseqBaseTest):
    VSEQ = ItemVseq
