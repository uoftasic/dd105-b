"""
DD105-B Lab 03: the tests.

Each test starts a 10 ns clock, holds rst_n low through the third rising
edge, makes the environment and runs its steps, as Lab 02's test did. They
are plain cocotb tests, so the lab's Makefile sets BASE_TEST := 0.

  router_rand_test   CTRL.EN, then +PHASES phases (default 4) of +N random
                     packets each (default 200), each phase with its own
                     random routing table and a DROP_CNT check; then
                     close_holes() and a last DROP_CNT check. `make check`
                     grades this one.
  router_fill_test   close_holes() on its own, for a short run and its waves.
                     It fails until close_holes() sends something, because
                     the scoreboard reports a test that checked no packet.
  router_class_test  Lab 02's test: +N packets (default 100) on +ROUTES.

The driver, the scoreboard and the DROP_CNT check log each error they find
and count it, and a logged error fails nothing by itself. The assert at the
end of each test is what fails it when the count isn't 0, and an
AssertionError is what the course's verdict counts as a check that fired.
"""

import logging
import random

import cocotb
import vsc  # noqa: F401  (Part 4's FillPlan is a pyvsc class)
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from env import Env
from packet import RandPacket, RouterCfg  # noqa: F401  (close_holes() makes RandPackets)

INPUTS = ("psel", "penable", "pwrite", "paddr", "pwdata",
          "in_valid", "in_data", "in_last", "out0_ready", "out1_ready")

log = logging.getLogger("tb.test")


async def make_env(dut):
    """The clock, the reset, and the environment, as Lab 02's test made them."""
    for name in INPUTS:
        getattr(dut, name).value = 0
    dut.rst_n.value = 0
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    return Env(dut, RouterCfg.from_plusargs())


def check_errors(env):
    n = env.n_errors()
    assert n == 0, f"the testbench reported {n} error{'' if n == 1 else 's'}; the first: {env.first_error()}"


def random_routes():
    """A random routing table, written as +ROUTES is, with at least one
    disabled route and an enabled route to each output."""
    while True:
        r = "".join(random.choice("-01") for _ in range(4))
        if "-" in r and "0" in r and "1" in r:
            return r


# TODO (Part 4): a pyvsc class FillPlan, whose randomize() picks packet
# lengths that add up to 8.


async def close_holes(env):
    """Stimulus that reaches the two coverage holes."""
    # TODO (Part 4)
    pass


@cocotb.test()
async def router_rand_test(dut):
    env = await make_env(dut)
    n = int(cocotb.plusargs.get("N", 200))
    n_phases = int(cocotb.plusargs.get("PHASES", 4))
    await env.start()
    await env.enable()
    for k in range(1, n_phases + 1):
        routes = random_routes()
        log.info(f"[PHASE] {k} of {n_phases}: routes {routes}, {n} packets")
        await env.write_routes(routes)
        await env.send_random(n)
        await env.drain()
        await env.check_drops()
        await env.clear_drops()
    await close_holes(env)
    await env.check_drops()
    env.report()
    check_errors(env)


@cocotb.test()
async def router_fill_test(dut):
    env = await make_env(dut)
    await env.start()
    await env.enable()
    await close_holes(env)
    await env.check_drops()
    env.report()
    check_errors(env)


@cocotb.test()
async def router_class_test(dut):
    """Lab 02's test. Env.run() now also checks DROP_CNT."""
    env = await make_env(dut)
    await env.run()
    check_errors(env)
