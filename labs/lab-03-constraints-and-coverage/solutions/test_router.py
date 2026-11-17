"""
DD105-B Lab 03: the tests (reference solution).

Each test starts a 10 ns clock, holds rst_n low through the third rising
edge, makes the environment and runs its steps, as Lab 02's test did. They
are plain cocotb tests, so the lab's Makefile sets BASE_TEST := 0.

  router_rand_test   CTRL.EN, then +PHASES phases (default 4) of +N random
                     packets each (default 200), each phase with its own
                     random routing table and a DROP_CNT check; then
                     close_holes() and a last DROP_CNT check. `make check`
                     grades this one.
  router_fill_test   close_holes() on its own, for a short run and its waves.
  router_class_test  Lab 02's test: +N packets (default 100) on +ROUTES.

The driver, the scoreboard and the DROP_CNT check log each error they find
and count it, and a logged error fails nothing by itself. The assert at the
end of each test is what fails it when the count isn't 0, and an
AssertionError is what the course's verdict counts as a check that fired.
"""

import logging
import random

import cocotb
import vsc
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from env import Env
from packet import RandPacket, RouterCfg

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


@vsc.randobj
class FillPlan:
    """Part 4: packet lengths that add up to 8. A 0 is "no packet", so the
    plan has 1 to 8 packets."""

    def __init__(self):
        self.lens = vsc.rand_list_t(vsc.uint8_t(), sz=8)

    @vsc.constraint
    def c_sum(self):
        with vsc.foreach(self.lens, idx=True) as i:
            self.lens[i] <= 8
        self.lens.sum == 8


async def close_holes(env):
    """Part 4: the two coverage holes, on output 0. ROUTE0 is enabled to
    output 0 and the other three routes are disabled. With output 0's sink
    stalled, packets for DST 0 whose lengths add up to exactly 8 fill it to
    level 8, and then two packets follow:

      1. a random packet for DST 0: decided at level 8, so admitted
         (('out0', 'at_8'), B08's bin), which takes the level to 9 to 16;
      2. a random packet for DST 1, a disabled route whose PORT is 0:
         NOROUTE with the level above 8 (('noroute', 'at_9') or
         ('noroute', 'high'), B07's bin). c_dst would keep it off a disabled
         route, so it is switched off for this one packet.

    Nothing more goes to output 0 while it holds more than 8 beats: the
    router would drop it as FULL, and the scoreboard, which expects every
    packet for an enabled route with PORT 0 to come out, would report it
    missing. Nothing goes to output 1. The test checks DROP_CNT after this."""
    await env.write_routes("0---")
    env.snk0.stall = True
    await env.cycles(2)
    plan = FillPlan()
    plan.randomize()
    lens = [int(n) for n in plan.lens if int(n) != 0]
    pkts = [RandPacket.make(0, n) for n in lens]
    p = env.gen.new_packet()
    with p.randomize_with() as it:
        it.hdr_dst == 0
    pkts.append(p)
    q = env.gen.new_packet()
    q.c_dst.constraint_mode(False)
    with q.randomize_with() as it:
        it.hdr_dst == 1
    pkts.append(q)
    log.info(f"[HOLES] output 0 stalled and filled to 8 by packets of {' '.join(map(str, lens))} "
             f"beats, then {int(p.length)} beats for DST 0 and {int(q.length)} for DST 1")
    await env.send(pkts)
    env.snk0.stall = False
    await env.drain()


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
