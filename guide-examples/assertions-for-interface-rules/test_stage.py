"""
DD105-B guide example, "Assertions for interface rules": the tests.

  StageTest   random beats into the stage for CYCLES cycles, and a sink that
              is ready in READY_PCT percent of them; at the end it prints
              what went through and what the checker counted

Plusargs: +CYCLES=<n> (200), +READY_PCT=<p> (50), and +UNCOUNTED, which
makes the test skip BaseTest's read of the bound assertions' count, as a
testbench that never reads it would. make run BUG=drop or BUG=bubble
switches on a planted bug (stage.sv).

The timing rule is the course's: the test changes the stage's inputs right
after a rising edge and reads its pins at the falling edge in the middle of
the cycle. The clock's period is 10 ns and its first rising edge is at
10 ns, so cycle n ends at the rising edge at 10n ns.
"""

import random

import cocotb
import pyuvm
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

from dd105b_base import BaseTest


def plusarg(name, default):
    return int(cocotb.plusargs.get(name, default))


@pyuvm.test()
class StageTest(BaseTest):
    """Random beats in, a random out_ready out. The bound checker does the
    checking; BaseTest reads its count, cocotb.top.u_sva.n_fail, at the end."""

    def build_phase(self):
        if "UNCOUNTED" in cocotb.plusargs:
            self.SVA_FAILS = None       # BaseTest then reports "no bound assertions"

    async def run_phase(self):
        self.raise_objection()
        d = cocotb.top
        n_cycles, ready_pct = plusarg("CYCLES", 200), plusarg("READY_PCT", 50)
        d.rst_n.value = 0
        d.in_valid.value = 0
        d.in_data.value = 0
        d.out_ready.value = 0
        cocotb.start_soon(Clock(d.clk, 10, unit="ns").start())
        for _ in range(2):
            await RisingEdge(d.clk)
        d.rst_n.value = 1

        n_in = n_out = 0
        data = 0
        for _ in range(n_cycles):
            # The middle of the cycle: which handshakes happen at the next edge.
            await FallingEdge(d.clk)
            took_in = bool(d.in_valid.value and d.in_ready.value)
            took_out = bool(d.out_valid.value and d.out_ready.value)
            n_in += took_in
            n_out += took_out
            await RisingEdge(d.clk)
            # Right after the edge: the next beat on offer, and the sink's ready.
            # A beat stays on offer until it is taken.
            if took_in or not d.in_valid.value:
                if random.randrange(100) < 70:
                    data = (data + 1) & 0xFF
                    d.in_valid.value = 1
                    d.in_data.value = data
                else:
                    d.in_valid.value = 0
            d.out_ready.value = int(random.randrange(100) < ready_pct)
        d.in_valid.value = 0
        await RisingEdge(d.clk)

        sva = d.u_sva
        self.logger.info(f"[STAGE] {n_in} beats in, {n_out} out; a beat waited in "
                         f"{int(sva.n_tried.value)} cycles (cover property: "
                         f"{int(sva.n_covered.value)}); {int(sva.n_fail.value)} assertion failures")
        self.drop_objection()

