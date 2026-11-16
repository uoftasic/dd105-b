"""
DD105-B: the base test. Every pyuvm test in the course derives from BaseTest,
or from RouterBaseTest for the router.

    from dd105b_base import RouterBaseTest

    @pyuvm.test()
    class RouterSmokeTest(RouterBaseTest):
        async def run_phase(self):
            self.raise_objection()
            await self.reset()
            ...
            self.drop_objection()

────────────────────────────────────────────────────────────────────────────
WHY THIS EXISTS
────────────────────────────────────────────────────────────────────────────
pyuvm reports through Python's `logging`, and every component's logger has
propagate = False. `self.logger.error("MISMATCH")` prints a line and fails
nothing: the cocotb test still passes, and results.xml says so. It is the
same trap as SystemVerilog UVM's UVM_ERROR ending with exit status 0, and the
fix has the same shape as DD105-A's dd105_base_test.

BaseTest adds one counting handler to every component's logger, and in
final_phase it raises AssertionError if any component logged an error, or if
the assertions bound into the design (u_sva.n_fail) counted a failure.
AssertionError is what labs/common/verdict.py counts as "a check fired".

It also prints one line at the end, starting "DD105-B BaseTest:". A test that
passes without printing it didn't end through BaseTest.final_phase (it
derives from uvm_test directly, or overrides final_phase without calling
super()), so its logged errors may have counted for nothing, and verdict.py
grades the run BROKEN rather than calling it a pass.

────────────────────────────────────────────────────────────────────────────
THE ASSERTION COUNT
────────────────────────────────────────────────────────────────────────────
The labs bind router_sva into the router as u_sva. Each assertion counts its
own failures (n_I1, u_out0.n_O2, ...) and n_fail is their sum, so Python reads
cocotb.top.u_sva.n_fail. A failure also calls $error, and Verilator's default
error limit of 1 would end the simulation at the first one; labs/common/
pyuvm.mk passes +verilator+error+limit+100000 to every run of a lab that binds
assertions, so the run goes on and the count is read here. A lab with no
assertions has no u_sva, and the count is skipped.
"""

import logging

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge
from pyuvm import ConfigDB, uvm_test

MARKER = "DD105-B BaseTest:"


class BaseTestNotSetUp(Exception):
    """Raised when a component's errors weren't being counted: BROKEN, not a check."""


class ErrorCounter(logging.Handler):
    """Counts every record at ERROR or above, and keeps the first few."""

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.count = 0
        self.first = []

    def emit(self, record):
        self.count += 1
        if len(self.first) < 3:
            self.first.append(record.getMessage())


def components(top):
    """top and every component below it."""
    out, todo = [], [top]
    while todo:
        c = todo.pop()
        out.append(c)
        todo.extend(c.children)
    return out


class BaseTest(uvm_test):
    """Turns logged errors and bound-assertion failures into a failing test."""

    # Where the bound assertions count their failures, under cocotb.top.
    # None for a design with no assertions.
    SVA_FAILS = "u_sva.n_fail"

    def __init__(self, name="uvm_test_top", parent=None):
        super().__init__(name, parent)
        self.errors = ErrorCounter()

    def _count_errors(self):
        for c in components(self):
            if self.errors not in c.logger.handlers:
                c.add_logging_handler(self.errors)

    def end_of_elaboration_phase(self):
        self._count_errors()

    def start_of_simulation_phase(self):
        # Again, in case a subclass's end_of_elaboration_phase didn't call super().
        self._count_errors()

    def sva_failures(self):
        """u_sva.n_fail, or None if the design has no bound assertions."""
        if not self.SVA_FAILS:
            return None
        h = cocotb.top
        for part in self.SVA_FAILS.split("."):
            try:
                h = getattr(h, part)
            except AttributeError:
                return None
        return int(h.value)

    def final_phase(self):
        missed = [c.get_full_name() for c in components(self)
                  if self.errors not in c.logger.handlers]
        n_sva = self.sva_failures()
        sva = ("no bound assertions" if n_sva is None
               else f"{n_sva} assertion failure{'' if n_sva == 1 else 's'} ({self.SVA_FAILS})")
        print(f"{MARKER} {self.errors.count} error{'' if self.errors.count == 1 else 's'} "
              f"logged, {sva}", flush=True)
        if missed:
            raise BaseTestNotSetUp(
                f"errors from {', '.join(missed[:3])} were not counted: a component was made "
                "after end_of_elaboration_phase, or a test overrides it without calling super()")
        msgs = []
        if self.errors.count:
            msgs.append(f"{self.errors.count} error{'' if self.errors.count == 1 else 's'} "
                        f"logged, the first: {self.errors.first[0]}")
        if n_sva:
            msgs.append(f"{n_sva} assertion failure{'' if n_sva == 1 else 's'} ({self.SVA_FAILS})")
        assert not msgs, "; ".join(msgs)


class RouterBaseTest(BaseTest):
    """BaseTest for the router: the clock, the reset, and the DUT in ConfigDB.

    Inputs change right after a rising edge and outputs are read at the
    falling edge, as router-spec.md's "Cycles and handshakes" describes.
    """

    PERIOD_NS = 10

    def build_phase(self):
        self.dut = cocotb.top
        ConfigDB().set(None, "*", "DUT", self.dut)

    def start_of_simulation_phase(self):
        super().start_of_simulation_phase()
        d = self.dut
        d.rst_n.value = 0
        for name in ("psel", "penable", "pwrite", "paddr", "pwdata",
                     "in_valid", "in_data", "in_last", "out0_ready", "out1_ready"):
            getattr(d, name).value = 0
        cocotb.start_soon(Clock(d.clk, self.PERIOD_NS, unit="ns").start())

    async def reset(self, cycles=3):
        """rst_n low for `cycles` rising edges, released just after the last."""
        d = self.dut
        d.rst_n.value = 0
        for _ in range(cycles):
            await RisingEdge(d.clk)
        d.rst_n.value = 1

    async def cycles(self, n):
        for _ in range(n):
            await RisingEdge(self.dut.clk)

    async def falling(self):
        await FallingEdge(self.dut.clk)
