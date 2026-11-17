"""
DD105-B Lab 02: the test.

router_class_test does what the top module and the test did in DD105-A's
Lab 02: it starts a 10 ns clock, holds rst_n low through the third rising
edge, makes the environment and runs it. It is a plain cocotb test, so the
lab's Makefile sets BASE_TEST := 0: there is no pyuvm and no BaseTest in this
lab.

The driver and the scoreboard log each error they find and count it, and a
logged error fails nothing by itself. The assert at the end is what fails the
test when the count isn't 0, and an AssertionError is what the course's
verdict counts as a check that fired.

You don't need to change this file.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from env import Env
from packet import RouterCfg

INPUTS = ("psel", "penable", "pwrite", "paddr", "pwdata",
          "in_valid", "in_data", "in_last", "out0_ready", "out1_ready")


@cocotb.test()
async def router_class_test(dut):
    for name in INPUTS:
        getattr(dut, name).value = 0
    dut.rst_n.value = 0
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1

    env = Env(dut, RouterCfg.from_plusargs())
    await env.run()

    n = env.n_errors()
    assert n == 0, f"the testbench reported {n} error{'' if n == 1 else 's'}; the first: {env.first_error()}"
