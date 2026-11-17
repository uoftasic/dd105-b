"""
DD105-B guide example, "Regressions and seeds": the tests.

  CountTest       random inc and clr for +CYCLES cycles (300): inc in 60% of
                  cycles and clr in 15%. It checks the count against a model
                  in every cycle, collects four coverage bins, and writes
                  coverage.xml into its run folder
  RandomTest      two coroutines: A draws four values at time 0, B four more
                  a nanosecond later. +EXTRA=<what> makes A do one thing more
                  before it draws: draw (one more random draw), seq (make a
                  pyuvm sequence), start (make one and start it), vsc_new
                  (build a pyvsc randobj), vsc_rand (build one and randomize()
                  it)
  RandomTwinTest  RandomTest's body under another name

cocotb seeds Python's random module for each test from COCOTB_RANDOM_SEED
(make run SEED=n) and the test's full name, test_seeds.<class>.

The test changes the counter's inputs right after a rising edge and reads
the pins at the falling edge, the course's timing rule.
"""

import random

import cocotb
import pyuvm
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer
from cocotb_coverage.coverage import CoverPoint, coverage_db
from pyuvm import uvm_sequence

from dd105b_base import BaseTest


def in_range(value, b):
    return b[0] <= value <= b[1]


@CoverPoint("satcnt.count", xf=lambda count, inc: count, bins=[(0, 7), (8, 14), (15, 15)],
            bins_labels=["low", "mid", "top"], rel=in_range)
@CoverPoint("satcnt.inc_at_top", xf=lambda count, inc: count == 15 and inc, bins=[True],
            bins_labels=["inc_at_15"])
def sample(count, inc):
    """One sample per cycle: the count, and whether inc was 1 at 15."""


@pyuvm.test()
class CountTest(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        d = cocotb.top
        n_cycles = int(cocotb.plusargs.get("CYCLES", 300))
        d.rst_n.value = 0
        d.inc.value = 0
        d.clr.value = 0
        cocotb.start_soon(Clock(d.clk, 10, unit="ns").start())
        for _ in range(2):
            await RisingEdge(d.clk)
        d.rst_n.value = 1

        model = 0
        at_top = inc_at_top = 0
        for _ in range(n_cycles):
            d.inc.value = int(random.randrange(100) < 60)
            d.clr.value = int(random.randrange(100) < 15)
            await FallingEdge(d.clk)
            got, inc, clr = int(d.count.value), int(d.inc.value), int(d.clr.value)
            if got != model:
                self.logger.error(f"[COUNT] count is {got}, expected {model}")
                model = got
            sample(got, bool(inc and not clr))
            at_top += got == 15
            inc_at_top += got == 15 and inc and not clr
            # The count after the next edge.
            model = 0 if clr else min(model + inc, 15)
            await RisingEdge(d.clk)
        self.logger.info(f"[COUNT] {n_cycles} cycles: at 15 in {at_top}, incremented there {inc_at_top} times")
        self.drop_objection()

    def report_phase(self):
        coverage_db.export_to_xml("coverage.xml")


@pyuvm.test()
class RandomTest(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        extra = cocotb.plusargs.get("EXTRA", "")
        values = {}

        async def thread_a():
            if extra == "draw":
                random.getrandbits(32)
            elif extra == "seq":
                uvm_sequence("s")
            elif extra == "start":
                await uvm_sequence("s").start()
            elif extra in ("vsc_new", "vsc_rand"):
                import vsc

                @vsc.randobj
                class Obj:
                    def __init__(self):
                        self.x = vsc.rand_uint32_t()

                o = Obj()
                if extra == "vsc_rand":
                    o.randomize()
            values["A"] = [random.getrandbits(32) for _ in range(4)]

        async def thread_b():
            await Timer(1, "ns")
            values["B"] = [random.getrandbits(32) for _ in range(4)]

        a = cocotb.start_soon(thread_a())
        b = cocotb.start_soon(thread_b())
        await a
        await b
        for t in ("A", "B"):
            self.logger.info(f"[RANDOM] coroutine {t}: " + " ".join(f"{v:08x}" for v in values[t]))
        self.drop_objection()


@pyuvm.test()
class RandomTwinTest(RandomTest):
    """RandomTest's body, under another name."""
