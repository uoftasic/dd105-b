"""
DD105-B reference environment: the tests.

Every test derives from RouterRefTest, which derives from the course's
RouterBaseTest (labs/common/py/dd105b_base.py): its final_phase turns logged
errors and failed assertions into a failing test. RouterRefTest builds the
environment, starts a SinkSeq on each sink that runs for the whole test, and
runs one virtual sequence (router_seqs), which each test names.

    make run TEST=RouterRandTest SEED=7 PLUSARGS="+N=3000 +PHASES=8"

Plusargs: +N (packets in RouterRandTest, default 1200), +PHASES (its phases,
default 6) and +MAX_CYCLES (default 400000): a test still running after that
many clock cycles ends with "[WATCHDOG]", so a router that stops answering is
a failed check rather than a hang. A test also ends once the scoreboard has
counted 50 mismatches.
"""

import cocotb
import pyuvm
from cocotb.triggers import ClockCycles, First

from dd105b_base import RouterBaseTest
from router_common import plusarg
from router_env import ResetSeq, RouterEnv
from router_seqs import (AllVseq, CtrlVseq, FullVseq, IrqVseq, OversizeVseq, RandVseq, RegsVseq,
                         ResetVseq, RouterVseq, SameCycleVseq, SaturateVseq, SmokeVseq)
from router_ral import RegBitBashSeq, RegResetSeq
from stream_agents import SinkSeq


class RouterRefTest(RouterBaseTest):
    """The environment, the sinks' sequences, the watchdog, and the one
    virtual sequence VSEQ."""

    VSEQ = SmokeVseq

    def build_phase(self):
        super().build_phase()
        self.env = RouterEnv.create("env", self)

    async def reset(self, cycles=3):
        """Through the reset driver, so the other drivers hear of it first."""
        await ResetSeq("reset", cycles).start(self.env.sys.sqr)

    async def watchdog(self, n):
        await ClockCycles(self.dut.clk, n)
        self.logger.error(f"[WATCHDOG] the test was still running after {n} cycles (+MAX_CYCLES)")

    async def run_phase(self):
        self.raise_objection()
        for k in (0, 1):
            cocotb.start_soon(SinkSeq(f"sink{k}_seq", self.env.sink_cfg[k]).start(self.env.sink[k].sqr))
        vseq = self.VSEQ(self.VSEQ.__name__, self.env)
        main = cocotb.start_soon(vseq.start())
        dog = cocotb.start_soon(self.watchdog(plusarg("MAX_CYCLES", 400000)))
        await First(main.complete, dog.complete, self.env.sb.stop.wait())
        for t in (main, dog):
            if t.done():
                # Waiting on a task's `complete` doesn't raise what the task
                # raised, and cocotb 2.0.1 then treats it as handled: without
                # this line a NameError in a sequence ends it, and the test passes.
                t.result()
            else:
                t.cancel()
        self.drop_objection()


def ref_test(cls):
    return pyuvm.test(timeout_time=5, timeout_unit="ms")(cls)


@ref_test
class RouterAllTest(RouterRefTest):
    """Every directed sequence, then 600 random packets in 4 phases: `make check` grades this one."""
    VSEQ = AllVseq


@ref_test
class RouterSmokeTest(RouterRefTest):
    VSEQ = SmokeVseq


@ref_test
class RouterRandTest(RouterRefTest):
    VSEQ = RandVseq


@ref_test
class RouterFullTest(RouterRefTest):
    VSEQ = FullVseq


@ref_test
class RouterOversizeTest(RouterRefTest):
    VSEQ = OversizeVseq


@ref_test
class RouterCtrlTest(RouterRefTest):
    VSEQ = CtrlVseq


@ref_test
class RouterSameCycleTest(RouterRefTest):
    VSEQ = SameCycleVseq


@ref_test
class RouterSaturateTest(RouterRefTest):
    VSEQ = SaturateVseq


@ref_test
class RouterRegsTest(RouterRefTest):
    VSEQ = RegsVseq


@ref_test
class RouterResetTest(RouterRefTest):
    VSEQ = ResetVseq


@ref_test
class RouterIrqTest(RouterRefTest):
    VSEQ = IrqVseq


class _RegSeqVseq(RouterVseq):
    SEQ = RegResetSeq

    async def body(self):
        await self.reset(3)
        await self.SEQ(self.SEQ.__name__, self.regs, self.env.predictor.logger).start()


class _BitBashVseq(_RegSeqVseq):
    SEQ = RegBitBashSeq


@ref_test
class RouterRegResetTest(RouterRefTest):
    """RegResetSeq on its own, straight after a reset."""
    VSEQ = _RegSeqVseq


@ref_test
class RouterBitBashTest(RouterRefTest):
    """RegBitBashSeq on its own, straight after a reset."""
    VSEQ = _BitBashVseq
