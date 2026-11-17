"""
DD105-B guide example: The pyuvm skeleton.

A testbench with no design to test: a test, an environment, two agents with
one child each, and a component called mon that loops forever the way a
monitor does. Each of them prints a line in every phase, so you can watch the
order in which pyuvm calls them. Lab 01's ALU is the toplevel only because
cocotb needs one; nothing drives it.

  SkPhaseTest      every phase; the test holds an objection for 100 ns and
                   env.a1.child holds one for 150 ns
  SkNoObjTest      the same tree, with no component holding an objection
  SkErrorTest      logs one error at 50 ns, and derives from BaseTest
  SkPlainErrorTest the same, deriving from pyuvm's uvm_test
  SkHangTest       raises an objection and never drops it, with a timeout
                   of 1 us on @pyuvm.test()
  SkFinalErrorTest a component that logs an error in its own final_phase
"""

import pyuvm
from cocotb.simtime import get_sim_time
from cocotb.triggers import Timer
from pyuvm import uvm_agent, uvm_analysis_port, uvm_component, uvm_env, uvm_test

from dd105b_base import BaseTest

FUNCTION_PHASES = ("build_phase", "connect_phase", "end_of_elaboration_phase",
                   "start_of_simulation_phase", "extract_phase", "check_phase",
                   "report_phase", "final_phase")


def say(comp, what):
    print(f"{int(get_sim_time('ns')):<4} ns  {what:<27}{comp.get_full_name()}", flush=True)


class Loud:
    """Mixed into every class below: prints a line in each function phase,
    then does what the class itself does in it (build_here, connect_here)."""

    def build_phase(self):
        say(self, "build_phase")
        super().build_phase()
        self.build_here()

    def build_here(self):
        pass

    def connect_phase(self):
        say(self, "connect_phase")
        super().connect_phase()

    def end_of_elaboration_phase(self):
        say(self, "end_of_elaboration_phase")
        super().end_of_elaboration_phase()

    def start_of_simulation_phase(self):
        say(self, "start_of_simulation_phase")
        super().start_of_simulation_phase()

    def extract_phase(self):
        say(self, "extract_phase")
        super().extract_phase()

    def check_phase(self):
        say(self, "check_phase")
        super().check_phase()

    def report_phase(self):
        say(self, "report_phase")
        super().report_phase()

    def final_phase(self):
        say(self, "final_phase")
        super().final_phase()


class SkLeaf(Loud, uvm_component):
    HOLD_NS = 0     # how long run_phase holds an objection; 0 holds none

    async def run_phase(self):
        say(self, "run_phase starts")
        if self.HOLD_NS:
            self.raise_objection()
            await Timer(self.HOLD_NS, "ns")
            say(self, f"drops after {self.HOLD_NS} ns")
            self.drop_objection()


class SkLongLeaf(SkLeaf):
    HOLD_NS = 150


class SkAgent(Loud, uvm_agent):
    LEAF = SkLeaf

    def build_here(self):
        self.child = self.LEAF.create("child", self)


class SkLongAgent(SkAgent):
    LEAF = SkLongLeaf


class SkWatcher(Loud, uvm_component):
    """Loops forever, as a monitor does, and holds no objection."""

    def build_here(self):
        self.ap = uvm_analysis_port("ap", self)

    async def run_phase(self):
        while True:
            say(self, "run_phase: still looping")
            await Timer(40, "ns")


class SkEnv(Loud, uvm_env):
    A1 = SkLongAgent    # a1's child holds an objection for 150 ns

    def build_here(self):
        # Made in this order on purpose: not the order of their names.
        self.mon = SkWatcher.create("mon", self)
        self.a1 = self.A1.create("a1", self)
        self.a0 = SkAgent.create("a0", self)


class SkQuietEnv(SkEnv):
    A1 = SkAgent        # no component holds an objection


def tree(comp, depth=0):
    """The component tree below comp, one line each: name and class."""
    lines = [f"{'  ' * depth}{comp.get_name():<{24 - 2 * depth}}{type(comp).__name__}"]
    for child in comp.children:
        lines += tree(child, depth + 1)
    return lines


class SkBaseTest(Loud, BaseTest):
    HOLD_NS = 100
    ENV = SkEnv

    def build_here(self):
        self.env = self.ENV.create("env", self)

    def end_of_elaboration_phase(self):
        super().end_of_elaboration_phase()
        if self.HOLD_NS:
            print("\n".join(tree(self)), flush=True)

    async def run_phase(self):
        say(self, "run_phase starts")
        if self.HOLD_NS:
            self.raise_objection()
            await Timer(self.HOLD_NS, "ns")
            say(self, f"drops after {self.HOLD_NS} ns")
            self.drop_objection()


@pyuvm.test()
class SkPhaseTest(SkBaseTest):
    pass


@pyuvm.test()
class SkNoObjTest(SkBaseTest):
    HOLD_NS = 0
    ENV = SkQuietEnv


@pyuvm.test()
class SkErrorTest(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        await Timer(50, "ns")
        self.logger.error("a check failed at 50 ns")
        self.drop_objection()


@pyuvm.test()
class SkPlainErrorTest(uvm_test):
    async def run_phase(self):
        self.raise_objection()
        await Timer(50, "ns")
        self.logger.error("a check failed at 50 ns")
        self.drop_objection()


@pyuvm.test(timeout_time=1, timeout_unit="us")
class SkHangTest(BaseTest):
    async def run_phase(self):
        self.raise_objection()
        await Timer(10, "us")
        self.drop_objection()


class SkLateChecker(uvm_component):
    """Logs an error in its final_phase, after the test's final_phase has run."""

    def final_phase(self):
        self.logger.error("a check failed in final_phase")


@pyuvm.test()
class SkFinalErrorTest(BaseTest):
    def build_phase(self):
        self.checker = SkLateChecker.create("checker", self)

    async def run_phase(self):
        self.raise_objection()
        await Timer(10, "ns")
        self.drop_objection()
