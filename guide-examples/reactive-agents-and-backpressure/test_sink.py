"""
DD105-B guide example, "Reactive agents and backpressure": a sink agent
for beat_src.sv, and the test that measures how long its beats wait.

  SnkCfg      the sink's knobs, which the driver reads in every cycle and the
              sequence for every item
  SnkItem     what the sink does for one beat: how many cycles it waits
  SnkSeq      one item per beat, for as long as the test runs
  SnkDriver   drives `ready`: a coin flip in every cycle (mode coin), or one
              item per beat (mode beat)
  SnkMonitor  counts how many cycles each beat waited between appearing
              and being taken
  SinkTest    runs until the monitor has counted +N beats (2000), or for
              +MAX_CYCLES cycles (200000), and prints the waits

Plusargs: +MODE=coin|beat (coin), +READY_PCT=<p> (50, mode coin),
+MAX_DELAY=<d> (12, mode beat), +ITEM=random|vsc (random: each delay from
random.randint; vsc: from pyvsc's randomize() with the constraint
delay <= max_delay), +NOSEQ (start no sequence on the sink), +N, +MAX_CYCLES.

The driver changes `ready` right after a rising edge and looks at the pins
at the falling edge in the middle of the cycle, the course's timing rule.
"""

import random
import time

import cocotb
import pyuvm
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Event, FallingEdge, First, RisingEdge
from cocotb.utils import get_sim_time
from pyuvm import (ConfigDB, uvm_agent, uvm_driver, uvm_monitor, uvm_sequence,
                   uvm_sequence_item, uvm_sequencer)

from dd105b_base import BaseTest


def plusarg(name, default):
    return cocotb.plusargs.get(name, default)


class SnkCfg:
    """The sink's knobs. The test keeps the handle and could change any of
    them in the middle of a run."""

    def __init__(self):
        self.mode = "coin"          # coin: a coin flip every cycle; beat: one item per beat
        self.ready_pct = 50         # mode coin: percent of cycles `ready` is 1
        self.max_delay = 12         # mode beat: the longest delay an item may have
        self.item = "random"        # mode beat: random.randint, or pyvsc's randomize()


class SnkItem(uvm_sequence_item):
    """One beat's answer: the beat waits `delay` cycles after it first
    appears. A delay of 0 means `ready` is already 1 when it appears."""

    def __init__(self, name="snk_item"):
        super().__init__(name)
        self.delay = 0
        self.max_delay = 12

    def randomize(self):
        self.delay = random.randint(0, self.max_delay)


def vsc_item_class():
    """SnkItem as a pyvsc randobj, with the delay left to the solver. Made on
    first use, so the other runs don't import pyvsc."""
    import vsc

    @vsc.randobj
    class VscSnkItem(uvm_sequence_item):
        def __init__(self, name="snk_item"):
            super().__init__(name)
            self.delay = vsc.rand_uint8_t()
            self.max_delay = vsc.uint8_t(12)

        @vsc.constraint
        def c_delay(self):
            self.delay <= self.max_delay

    return VscSnkItem


class SnkSeq(uvm_sequence):
    """One item per beat, forever. start_item() returns when the driver asks
    for an item, and only then does the sequence decide the item's delay."""

    def __init__(self, name="snk_seq", cfg=None):
        super().__init__(name)
        self.cfg = cfg
        self.solve_s = 0.0          # seconds spent in randomize()
        self.n = 0

    async def body(self):
        make = vsc_item_class() if self.cfg.item == "vsc" else SnkItem
        while True:
            it = make("snk_item")
            await self.start_item(it)
            it.max_delay = self.cfg.max_delay
            self.timed(it.randomize)
            await self.finish_item(it)

    def timed(self, randomize):
        """Call randomize() and add up the wall time it takes."""
        t0 = time.perf_counter()
        randomize()
        self.solve_s += time.perf_counter() - t0
        self.n += 1


class SnkDriver(uvm_driver):
    """Mode coin: right after every rising edge, `ready` is 1 with
    probability ready_pct percent, and the driver asks for no items.

    Mode beat: the driver holds one item at a time, from when it gets it
    until the beat that item answers is taken. At the falling edge it sees
    whether a beat moves at the next edge, counts down the item's delay
    while the beat waits, and asks for the next item once the beat has gone.
    It drives the `ready` it decided there right after the next rising edge."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.cfg = ConfigDB().get(self, "", "cfg")
        self.n_items = 0            # items get_next_item() returned
        self.later = []             # (called, returned) in ns, for each that returned at a later time
        self.waiting_since = None   # the time of a get_next_item() call that hasn't returned

    async def run_phase(self):
        d, cfg = self.dut, self.cfg
        it = None                   # the item for the beat on offer, or for the next beat
        wait_left = 0               # cycles the beat still has to wait
        rdy = 0                     # `ready` in the cycle that starts at the next edge
        while True:
            await RisingEdge(d.clk)
            if cfg.mode == "coin":
                rdy = int(random.randrange(100) < cfg.ready_pct)
            d.ready.value = rdy
            if cfg.mode == "coin":
                continue
            await FallingEdge(d.clk)
            v = bool(d.valid.value)
            if v and rdy:                       # the handshake: the item has had its beat
                self.seq_item_port.item_done()
                it = None
            elif v and wait_left > 0:           # the beat waits one more cycle
                wait_left -= 1
            if it is None:
                t0 = self.waiting_since = get_sim_time("ns")
                it = await self.seq_item_port.get_next_item()
                self.waiting_since = None
                self.n_items += 1
                if get_sim_time("ns") != t0:
                    self.later.append((t0, get_sim_time("ns")))
                wait_left = it.delay
            rdy = int(wait_left == 0)


class SnkMonitor(uvm_monitor):
    """At every falling edge: a beat on offer that wasn't there before has
    appeared; a beat on offer with `ready` 1 is taken at the next edge. It
    counts how many cycles each beat waited, and sets `done` at the Nth."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.n_want = int(plusarg("N", 2000))
        self.waits = []
        self.done = Event()
        self.cycles = 0

    async def run_phase(self):
        d = self.dut
        first = None
        while True:
            await FallingEdge(d.clk)
            self.cycles += 1
            if not (d.rst_n.value and d.valid.value):
                continue
            if first is None:
                first = self.cycles
            if d.ready.value:
                self.waits.append(self.cycles - first)
                first = None
                if len(self.waits) == self.n_want:
                    self.done.set()


class SnkAgent(uvm_agent):
    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = SnkDriver.create("drv", self)
        self.mon = SnkMonitor.create("mon", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


@pyuvm.test()
class SinkTest(BaseTest):
    """The sink against beat_src, until N beats have been taken."""

    def build_phase(self):
        self.cfg = SnkCfg()
        self.cfg.mode = plusarg("MODE", "coin")
        self.cfg.ready_pct = int(plusarg("READY_PCT", 50))
        self.cfg.max_delay = int(plusarg("MAX_DELAY", 12))
        self.cfg.item = plusarg("ITEM", "random")
        ConfigDB().set(None, "*", "DUT", cocotb.top)
        ConfigDB().set(None, "*", "cfg", self.cfg)
        self.snk = SnkAgent.create("snk", self)

    async def run_phase(self):
        self.raise_objection()
        d = cocotb.top
        d.rst_n.value = 0
        d.ready.value = 0
        cocotb.start_soon(Clock(d.clk, 10, unit="ns").start())
        for _ in range(2):
            await RisingEdge(d.clk)
        d.rst_n.value = 1
        # The sink's sequence runs for the whole test, so nothing waits for it
        # to finish, and it raises no objection: this test's objection decides
        # when the test ends.
        seq = SnkSeq("snk_seq", self.cfg)
        if "NOSEQ" not in cocotb.plusargs:
            cocotb.start_soon(seq.start(self.snk.sqr))
        mon, drv = self.snk.mon, self.snk.drv
        await First(mon.done.wait(), ClockCycles(d.clk, int(plusarg("MAX_CYCLES", 200000))))
        self.report(mon, drv, seq)
        self.drop_objection()

    def report(self, mon, drv, seq):
        cfg, w = self.cfg, mon.waits
        what = (f"coin flip, {cfg.ready_pct}%" if cfg.mode == "coin" else
                f"per beat, delays 0 to {cfg.max_delay} from "
                f"{'randomize()' if cfg.item == 'vsc' else 'random.randint'}")
        if not w:
            self.logger.info(f"[WAIT] {what}: 0 beats taken in {mon.cycles} cycles")
        else:
            buckets = [sum(1 for x in w if lo <= x <= hi) for lo, hi in ((0, 0), (1, 3), (4, 20))]
            buckets.append(sum(1 for x in w if x > 20))
            self.logger.info(f"[WAIT] {what}: {len(w)} beats in {mon.cycles} cycles; waited 0: "
                             f"{buckets[0]}, 1 to 3: {buckets[1]}, 4 to 20: {buckets[2]}, "
                             f"more than 20: {buckets[3]}; mean {sum(w) / len(w):.2f} cycles")
            top = 40
            hist = [sum(1 for x in w if x == k) for k in range(top)] + [sum(1 for x in w if x >= top)]
            self.logger.info("[HIST] " + " ".join(f"{k}:{n}" for k, n in enumerate(hist) if n))
        if cfg.mode == "beat":
            late = ", ".join(f"called at {a:.0f} ns, returned at {b:.0f} ns" for a, b in drv.later[:3])
            now = get_sim_time("ns")
            waiting = drv.waiting_since is not None and drv.waiting_since < now
            self.logger.info(f"[DRV] get_next_item() returned {drv.n_items} items, {len(drv.later)} "
                             f"of them at a later time than it was called" + (f" ({late})" if late else "")
                             + (f"; it has been waiting in get_next_item() since {drv.waiting_since:.0f} ns"
                                if waiting else ""))
            if seq.n:
                self.logger.info(f"[SEQ] {seq.n} items made; randomize() took {seq.solve_s:.3f} s "
                                 f"in all, {seq.n / seq.solve_s:.0f} a second")
