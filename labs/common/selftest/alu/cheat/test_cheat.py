"""SELFTEST FIXTURE -- a test that asks the simulator which bug is on, and so
"catches" every bug without checking anything. check.py and hunt.py must
refuse it before they build or run anything. It is never run."""
import cocotb
import pyuvm
from test_st import StGoodTest


@pyuvm.test()
class StCheatTest(StGoodTest):
    def final_phase(self):
        if cocotb.plusargs.get("BUG"):
            self.logger.error("a bug is on")
        if int(cocotb.packages.st_bug_pkg.bug_id.value):
            self.logger.error("a bug is on")
        super().final_phase()
