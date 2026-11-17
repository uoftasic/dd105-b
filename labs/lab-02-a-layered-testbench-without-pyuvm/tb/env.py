"""
DD105-B Lab 02: the environment, which builds every other piece, connects
them with queues and runs them.

  Generator --(gen2drv)--> Driver --> router input
  router input --> in_mon   --(in2sb)----> Scoreboard
  router out0  --> out0_mon --(out02sb)--> Scoreboard
  router out0, out1 <-- Sink (always ready)

run() is the whole test: wait for reset, write the configuration over APB,
start the sinks, the monitors and the scoreboard, send the packets, wait for
the outputs to drain, and report. The end of the test doesn't depend on the
monitors or the scoreboard: it comes when the driver has sent every packet
and the outputs have had DRAIN cycles to empty.

Each piece logs through a logger of its own, named tb.<piece>, so a line in
the log says which piece wrote it. Python's loggers show only warnings and
errors unless told otherwise, and cocotb sets its own loggers to show INFO
lines too, so the environment does the same for the tb loggers.
"""

import logging

import cocotb
from cocotb.queue import Queue
from cocotb.triggers import RisingEdge

from driver import ApbMaster, Driver, Sink
from generator import Generator
from monitor import Monitor
from scoreboard import Scoreboard


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

    async def configure(self):
        """ROUTE0 to ROUTE3 from cfg.routes, then CTRL.EN, which opens the input."""
        for d in range(4):
            await self.apb.write(0x20 + 4 * d,
                                 (self.cfg.route_port(d) << 1) | int(self.cfg.route_en(d)))
        await self.apb.write(0x04, 1)

    async def run(self):
        self.log.info(f"[ENV] {self.cfg.describe()}")
        await self.apb.wait_for_reset()
        await self.configure()
        for piece in (self.snk0, self.snk1, self.in_mon, self.out0_mon, self.sb):
            cocotb.start_soon(piece.run())
        gen = cocotb.start_soon(self.gen.run())
        await self.drv.run(self.cfg.n)
        await gen
        for _ in range(self.DRAIN):
            await RisingEdge(self.dut.clk)
        self.log.info(f"[ENV] sent {self.drv.n_pkts} packets ({self.drv.n_beats} beats); output 0 "
                      f"took {self.snk0.n_beats} beats and output 1 took {self.snk1.n_beats}")
        self.sb.report()

    def n_errors(self):
        """Every error the testbench reported: the scoreboard's and the driver's."""
        return self.drv.n_errors + self.sb.n_errors

    def first_error(self):
        """The message of the earliest error, or None."""
        firsts = [e for e in (self.drv.first_error, self.sb.first_error) if e is not None]
        return min(firsts, key=lambda e: e[0])[1] if firsts else None
