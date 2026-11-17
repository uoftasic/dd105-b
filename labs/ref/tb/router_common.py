"""
DD105-B reference environment: what the agents share.

  ResetState  how the reset driver warns the drivers a reset can interrupt
  Clocked     lets a driver start an item in the cycle right after the last one
  Fwd         one input of a component that has several (pyuvm has no
              uvm_analysis_imp_decl)
  plusarg     an integer plusarg, or a default

Timing, as router-spec.md's "Cycles and handshakes" describes it: every driver
changes the router's inputs right after a rising edge and looks at its
outputs at the falling edge in the middle of the cycle, so nothing changes at
the moment anything is sampled. Every monitor samples at the falling edge.
"""

import cocotb
from cocotb.triggers import RisingEdge
from cocotb.utils import get_sim_time
from pyuvm import ConfigDB, uvm_subscriber
from pyuvm.error_classes import UVMConfigItemNotFound


class ResetState:
    """Shared through ConfigDB under "RESET". The reset driver
    (router_env.ResetDriver) sets `soon` right after the rising edge before
    the one at which it pulls rst_n low, records the time it did so in
    `soon_time`, and clears `soon` when it lets rst_n go. `epoch` counts the
    resets started.

    So right after a rising edge a driver can tell three things apart: no
    reset coming; a reset that starts at the next edge (`soon` set in this
    same time step), when a transfer already under way must carry on for one
    more cycle, since rule A1 holds until rst_n is 0; and a reset that starts
    at this edge (`soon` set at an earlier one), when it must stop at once.
    The APB driver uses that to keep psel at 0 in every reset cycle (rule A4)
    and start an interrupted transfer again afterwards. The source driver
    abandons a packet whose epoch has moved (rule I3)."""

    def __init__(self):
        self.soon = False
        self.soon_time = 0
        self.epoch = 0

    def starts_now(self):
        """Right after a rising edge: rst_n falls at this edge, or is low."""
        return self.soon and self.soon_time < get_sim_time("step")


def reset_state(comp):
    """The environment's ResetState, or one that never changes if nothing
    put one in ConfigDB (an agent used without the reset driver)."""
    try:
        return ConfigDB().get(comp, "", "RESET")
    except UVMConfigItemNotFound:
        return ResetState()


class Clocked:
    """A driver that has just finished an item right after a rising edge can
    start the next one in the same time step, so items that follow each other
    need no idle cycle between them (rule A3 allows back-to-back transfers)."""

    def _mark_edge(self):
        self._t_edge = get_sim_time("step")

    async def _to_edge(self, clk):
        if getattr(self, "_t_edge", None) != get_sim_time("step"):
            await RisingEdge(clk)
            self._mark_edge()


class Fwd(uvm_subscriber):
    """pyuvm has no uvm_analysis_imp_decl, so a component with several inputs
    gets one of these per input, forwarding each write to a method."""

    def __init__(self, name, parent, fn):
        super().__init__(name, parent)
        self.fn = fn

    def write(self, t):
        self.fn(t)


def plusarg(name, default):
    try:
        return int(cocotb.plusargs.get(name, default))
    except (TypeError, ValueError):
        return default
