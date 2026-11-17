"""
DD105-B guide example: the tests for Monitors, analysis ports and scoreboards.

  MonRandTest     200 random vectors through the environment
  MonAliasTest    the same, with a monitor that fills in one item again and
                  again, swapped in by a factory override
  MonConnectTest  an environment that connects the monitor's port to the
                  scoreboard itself instead of to its analysis_export
"""

import pyuvm
from pyuvm import uvm_factory

from mon_env import AluMonitor, MonBaseTest, MonEnv
from sq_agent import AluItem


@pyuvm.test()
class MonRandTest(MonBaseTest):
    pass


class AliasMonitor(AluMonitor):
    """Makes one item and fills it in again for every vector."""

    def next_item(self):
        if not hasattr(self, "one"):
            self.one = AluItem.create("seen")
        return self.one


@pyuvm.test()
class MonAliasTest(MonBaseTest):
    def build_phase(self):
        uvm_factory().set_type_override_by_type(AluMonitor, AliasMonitor)
        super().build_phase()


class WrongEnv(MonEnv):
    def connect_phase(self):
        self.agt.mon.ap.connect(self.sb)


@pyuvm.test()
class MonConnectTest(MonBaseTest):
    def build_phase(self):
        uvm_factory().set_type_override_by_type(MonEnv, WrongEnv)
        super().build_phase()
