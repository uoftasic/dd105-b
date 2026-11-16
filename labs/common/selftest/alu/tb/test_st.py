"""
SELFTEST FIXTURES -- not course material, and not examples to copy. Every test
here except StGoodTest is broken in one specific way, and its docstring names
the verdict labs/common/verdict.py must give it. selftest.py runs them.

The environment: a driver that sends one ALU operation every other cycle, a
monitor that pairs each result with its operation, and a scoreboard that
checks result and carry. Nothing in Python checks the zero flag; only the
assertion bound into the ALU (tb/st_sva.sv) does, so B02 is caught by an
assertion or not at all.
"""

import random

import cocotb
import pyuvm
from cocotb.clock import Clock
from cocotb.triggers import Event, FallingEdge, RisingEdge
from pyuvm import (ConfigDB, UVMFatalError, uvm_analysis_port, uvm_component, uvm_driver,
                   uvm_env, uvm_sequence, uvm_sequence_item, uvm_sequencer, uvm_subscriber,
                   uvm_test)

from dd105b_base import BaseTest

try:
    from cocotb_coverage.coverage import CoverPoint, coverage_db
except ImportError:
    CoverPoint = None

OPS = ("ADD", "SUB", "AND", "OR", "XOR", "SHL", "SHR", "PASS_B")


def expect(op, a, b):
    """(result, carry) for one operation, as the ALU's comment defines them."""
    r = {0: a + b, 1: ((a - b) & 0xFF) | (0x100 if a < b else 0), 2: a & b, 3: a | b, 4: a ^ b,
         5: a << (b & 7), 6: a >> (b & 7), 7: b}[op]
    return r & 0xFF, (r >> 8) & 1


class StItem(uvm_sequence_item):
    def __init__(self, name="st_item", op=0, a=0, b=0):
        super().__init__(name)
        self.op, self.a, self.b = op, a, b

    def __str__(self):
        return f"{OPS[self.op]} {self.a:02x} {self.b:02x}"


class StRandSeq(uvm_sequence):
    """N random operations; a quarter of them with a == b."""

    def __init__(self, name="st_rand", n=300):
        super().__init__(name)
        self.n = n
        self.sample = None                   # StGoodTest's coverage, if any

    def item(self):
        a, b = random.randrange(256), random.randrange(256)
        return StItem("it", random.randrange(8), a, a if random.random() < 0.25 else b)

    async def body(self):
        for _ in range(self.n):
            it = self.item()
            if self.sample:
                self.sample(it)
            await self.start_item(it)
            await self.finish_item(it)


class StDriver(uvm_driver):
    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.sent = 0

    async def run_phase(self):
        d = self.dut
        d.in_valid.value = 0
        while True:
            it = await self.seq_item_port.get_next_item()
            await RisingEdge(d.clk)
            d.in_valid.value, d.op.value, d.a.value, d.b.value = 1, it.op, it.a, it.b
            await RisingEdge(d.clk)
            d.in_valid.value = 0
            self.sent += 1
            self.seq_item_port.item_done()


class StMonitor(uvm_component):
    """At each falling edge: an operation going in, and a result coming out."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d, pending = self.dut, []
        while True:
            await FallingEdge(d.clk)
            if d.out_valid.value and pending:
                self.ap.write((pending.pop(0), int(d.result.value), int(d.carry.value)))
            if d.in_valid.value:
                pending.append(StItem("seen", int(d.op.value), int(d.a.value), int(d.b.value)))


class StScoreboard(uvm_subscriber):
    def build_phase(self):
        self.seen = 0
        self.errors = 0

    def mismatch(self, it, r, c, want):
        self.logger.error(f"MISMATCH {it}: r={r:02x} c={c}, expected r={want[0]:02x} c={want[1]}")

    def write(self, t):
        it, r, c = t
        self.seen += 1
        want = expect(it.op, it.a, it.b)
        if (r, c) != want:
            self.errors += 1
            self.mismatch(it, r, c, want)


class StEnv(uvm_env):
    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = StDriver("drv", self)
        self.mon = StMonitor("mon", self)
        self.sb = StScoreboard.create("sb", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)
        self.mon.ap.connect(self.sb.analysis_export)

    def check_phase(self):
        if self.drv.sent != self.sb.seen:
            self.logger.error(f"the driver sent {self.drv.sent} items and the scoreboard saw "
                              f"{self.sb.seen}")


class _Setup:
    """The clock, the reset and the environment, shared by every fixture."""

    N = 300

    def build_phase(self):
        ConfigDB().set(None, "*", "DUT", cocotb.top)
        self.env = StEnv("env", self)

    def seq(self):
        return StRandSeq("seq", int(cocotb.plusargs.get("N", self.N)))

    async def reset(self):
        d = cocotb.top
        d.rst_n.value, d.in_valid.value = 0, 0
        cocotb.start_soon(Clock(d.clk, 10, unit="ns").start())
        for _ in range(3):
            await RisingEdge(d.clk)
        d.rst_n.value = 1

    async def body(self):
        await self.seq().start(self.env.sqr)

    async def run_phase(self):
        self.raise_objection()
        await self.reset()
        await self.body()
        for _ in range(4):
            await RisingEdge(cocotb.top.clk)
        self.drop_objection()


@pyuvm.test()
class StGoodTest(_Setup, BaseTest):
    """The reference: ok on golden, B01 caught (a logged MISMATCH), B02 caught
    (only the assertion sees it), B03 MISSED (one operand pair in 65,536).
    With the course venv it also writes coverage.xml, for `make regress`."""

    def end_of_elaboration_phase(self):
        super().end_of_elaboration_phase()
        self.cov = None
        if CoverPoint is not None:
            @CoverPoint("st.op", xf=lambda it: it.op, bins=list(range(8)), bins_labels=list(OPS))
            @CoverPoint("st.equal", xf=lambda it: it.a == it.b, bins=[True, False])
            def sample(it):
                pass
            self.cov = sample

    async def body(self):
        seq = self.seq()
        seq.sample = self.cov
        await seq.start(self.env.sqr)

    def report_phase(self):
        if self.cov:
            coverage_db.export_to_xml("coverage.xml")


@pyuvm.test()
class StEmptyTest(_Setup, BaseTest):
    """Sends nothing: ok on golden, and MISSED on every bug."""

    async def body(self):
        pass


class StFixedSeq(StRandSeq):
    def item(self):
        return StItem("it", 0, 1, 2)


@pyuvm.test()
class StFixedTest(_Setup, BaseTest):
    """Sends ADD 01 02 three hundred times: ok on golden, MISSED on B01."""

    def seq(self):
        return StFixedSeq("seq", self.N)


@pyuvm.test()
class StPlainTest(_Setup, uvm_test):
    """Derives from uvm_test, not BaseTest. Its scoreboard logs MISMATCH on B01
    and the test passes anyway: BROKEN (no BaseTest line), golden or not."""


class AssertScoreboard(StScoreboard):
    def mismatch(self, it, r, c, want):
        assert (r, c) == want, f"MISMATCH {it}: r={r:02x} c={c}"


@pyuvm.test()
class StAssertTest(_Setup, BaseTest):
    """Checks with a plain `assert` in the scoreboard, which raises inside the
    monitor's task: ok on golden, caught (AssertionError) on B01."""

    def build_phase(self):
        pyuvm.uvm_factory().set_type_override_by_type(StScoreboard, AssertScoreboard)
        super().build_phase()


class CrashScoreboard(StScoreboard):
    def mismatch(self, it, r, c, want):
        self.logger.error(f"MISMATCH {it}, first was {first_bad}")    # noqa: F821


@pyuvm.test()
class StCrashTest(_Setup, BaseTest):
    """NameError in the mismatch path, DD104's classic: ok on golden, BROKEN on B01."""

    def build_phase(self):
        pyuvm.uvm_factory().set_type_override_by_type(StScoreboard, CrashScoreboard)
        super().build_phase()


class FatalScoreboard(StScoreboard):
    def mismatch(self, it, r, c, want):
        raise UVMFatalError(f"MISMATCH {it}")


@pyuvm.test()
class StFatalCheckTest(_Setup, BaseTest):
    """Reports a mismatch with UVMFatalError: ok on golden, BROKEN on B01."""

    def build_phase(self):
        pyuvm.uvm_factory().set_type_override_by_type(StScoreboard, FatalScoreboard)
        super().build_phase()


@pyuvm.test()
class StConfigTest(_Setup, BaseTest):
    """Asks ConfigDB for a name nobody set: BROKEN (UVMConfigItemNotFound)."""

    def build_phase(self):
        super().build_phase()
        ConfigDB().get(self, "", "DVR")


@pyuvm.test()
class StHangTest(_Setup, BaseTest):
    """Waits for an event that never comes, with no timeout: stopped by
    RUN_TIMEOUT, BROKEN."""

    async def body(self):
        await Event().wait()


@pyuvm.test(timeout_time=2, timeout_unit="us")
class StWatchdogTest(_Setup, BaseTest):
    """The same hang under @pyuvm.test(timeout_time=2 us): SimTimeoutError, which
    counts as a check that fired (the event the test waited for never came), so
    on the golden design it is a FAIL."""

    async def body(self):
        await Event().wait()


@pyuvm.test()
class StNoSuperTest(_Setup, BaseTest):
    """Overrides both phases that install BaseTest's error counter without
    calling super(): BROKEN (BaseTestNotSetUp)."""

    def end_of_elaboration_phase(self):
        pass

    def start_of_simulation_phase(self):
        pass


@pyuvm.test()
class StFinalNoSuperTest(_Setup, BaseTest):
    """Overrides final_phase without calling super(), so logged errors fail
    nothing: BROKEN (no BaseTest line), even on B01."""

    def final_phase(self):
        pass


@pyuvm.test()
class StRegModelTest(_Setup, BaseTest):
    """Builds a register model whose fields overlap: pyuvm raises AssertionError
    in build_phase, which verdict.py alone would call caught. check.py builds
    the model first (REG_MODEL) and refuses it."""

    def build_phase(self):
        from st_regs import OverlapRegs
        super().build_phase()
        OverlapRegs()
