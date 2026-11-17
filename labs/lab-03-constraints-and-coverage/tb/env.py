"""
DD105-B Lab 03: the environment, which builds every other piece, connects
them with queues and runs them.

  Generator --(gen2drv)--> Driver --> router input
  router input --> in_mon   --(in2sb)----> Scoreboard
  router out0  --> out0_mon --(out02sb)--> Scoreboard
  router input and out0 --> Tracker --> coverage.sample_pkt()
  router out0, out1 <-- Sink (ready unless stalled)

Lab 02's run() was the whole test in one coroutine. Here it's split into the
steps a test calls one after another (start, write_routes, enable,
send_random or send, drain, check_drops, report), and run() is those steps in
Lab 02's order, so router_class_test still runs Lab 02's test.

check_drops() is new in this lab. A router that counts a drop wrongly can
deliver every packet correctly, so the scoreboard can't see it; reading
DROP_CNT and comparing it with the tracker's counts is the only check in
this testbench that can.

Each piece logs through a logger of its own, named tb.<piece>, so a line in
the log says which piece wrote it. Python's loggers show only warnings and
errors unless told otherwise, and cocotb sets its own loggers to show INFO
lines too, so the environment does the same for the tb loggers.
"""

import logging

import cocotb
from cocotb.queue import Queue
from cocotb.simtime import get_sim_time
from cocotb.triggers import RisingEdge

import coverage
from driver import ApbMaster, Driver, Sink
from generator import Generator
from monitor import Monitor
from packet import RouterCfg
from scoreboard import Scoreboard
from tracker import Tracker

CTRL, DROP_CNT, ROUTE0 = 0x04, 0x10, 0x20


class Env:
    DRAIN = 50                      # cycles after the last input beat

    def __init__(self, dut, cfg):
        self.dut = dut
        self.cfg = cfg
        logging.getLogger("tb").setLevel(logging.INFO)
        self.log = logging.getLogger("tb.env")
        self.gen2drv = Queue()
        self.in2sb = Queue()
        self.out02sb = Queue()
        self.gen = Generator(cfg, self.gen2drv)
        self.drv = Driver(dut, self.gen2drv, logging.getLogger("tb.drv"))
        self.snk0 = Sink(dut, "out0")
        self.snk1 = Sink(dut, "out1")
        self.apb = ApbMaster(dut)
        self.in_mon = Monitor("in", dut, "in", self.in2sb, logging.getLogger("tb.in"), cfg.show)
        self.out0_mon = Monitor("out0", dut, "out0", self.out02sb, logging.getLogger("tb.out0"),
                                cfg.show)
        self.sb = Scoreboard(cfg, self.in2sb, self.out02sb, logging.getLogger("tb.sb"))
        self.trk = Tracker(dut, cfg, coverage.sample_pkt, logging.getLogger("tb.trk"))
        self.n_drop_errors = 0
        self.first_drop_error = None    # (time in ns, message)

    async def start(self):
        """Wait for the reset to end, then start everything that runs for
        the whole test."""
        await self.apb.wait_for_reset()
        for piece in (self.snk0, self.snk1, self.in_mon, self.out0_mon, self.sb, self.trk):
            cocotb.start_soon(piece.run())

    async def write_routes(self, routes):
        """ROUTE0 to ROUTE3, written as +ROUTES is: one character per route,
        0 or 1 for the output, - for disabled (written with PORT 0).
        cfg.routes changes with them, and the scoreboard, the tracker and the
        generator predict from it, so call this only while no packet is
        coming in."""
        self.cfg.routes = RouterCfg.check_routes(routes)
        for d in range(4):
            await self.apb.write(ROUTE0 + 4 * d,
                                 (self.cfg.route_port(d) << 1) | int(self.cfg.route_en(d)))

    async def enable(self):
        """CTRL.EN, which opens the input."""
        await self.apb.write(CTRL, 1)

    async def configure(self):
        """Lab 02's configure(): the routing table from +ROUTES, then CTRL.EN."""
        await self.write_routes(self.cfg.routes)
        await self.enable()

    async def send_random(self, n):
        """n random packets for the routes in cfg.routes. Returns when the
        last one has gone into the router."""
        gen = cocotb.start_soon(self.gen.run(n))
        await self.drv.run(n)
        await gen

    async def send(self, pkts):
        """Packets the test built itself, in order, each with the next tag.
        Returns when the last one has gone into the router."""
        for p in pkts:
            await self.gen.put(p)
        await self.drv.run(len(pkts))

    async def cycles(self, n):
        for _ in range(n):
            await RisingEdge(self.dut.clk)

    async def drain(self):
        """Give the outputs DRAIN cycles to empty."""
        await self.cycles(self.DRAIN)

    async def check_drops(self):
        """Read DROP_CNT and compare it with the drops the tracker predicted."""
        got = await self.apb.read(DROP_CNT)
        want = self.trk.drop_cnt()
        if got != want:
            msg = (f"DROP_CNT read {got:08x}, expected {want:08x} "
                   f"(FULL_CNT {want >> 8}, NOROUTE_CNT {want & 0xFF})")
            self.n_drop_errors += 1
            if self.first_drop_error is None:
                self.first_drop_error = (get_sim_time("ns"), msg)
            self.log.error(msg)
        else:
            self.log.info(f"[DROP] DROP_CNT {got:08x} as expected")

    async def clear_drops(self):
        """Write DROP_CNT, which clears both counters, and clear the
        tracker's."""
        await self.apb.write(DROP_CNT, 0)
        self.trk.clear_drops()

    def report(self):
        self.log.info(f"[ENV] sent {self.drv.n_pkts} packets ({self.drv.n_beats} beats); output 0 "
                      f"took {self.snk0.n_beats} beats and output 1 took {self.snk1.n_beats}")
        self.trk.report()
        self.sb.report()
        coverage.report(self.log)

    async def run(self):
        """Lab 02's test: the routing table from +ROUTES, cfg.n random
        packets, a drain, and the report. The DROP_CNT check is this lab's."""
        self.log.info(f"[ENV] {self.cfg.describe()}")
        await self.start()
        await self.configure()
        await self.send_random(self.cfg.n)
        await self.drain()
        await self.check_drops()
        self.report()

    def n_errors(self):
        """Every error the testbench reported: the scoreboard's, the
        driver's and the DROP_CNT check's."""
        return self.drv.n_errors + self.sb.n_errors + self.n_drop_errors

    def first_error(self):
        """The message of the earliest error, or None. At the end of a test
        check_drops() runs before the scoreboard's report(), at the same
        time, so for two errors at the same time the DROP_CNT check's counts
        as the earlier."""
        firsts = [e for e in (self.drv.first_error, self.first_drop_error, self.sb.first_error)
                  if e is not None]
        return min(firsts, key=lambda e: e[0])[1] if firsts else None
