"""
DD105-B Lab 02: the scoreboard, with run(), predict(), check() and the
checks in report() written (the reference solution).

Predicts which input packets come out of output 0, and checks that output 0
delivers exactly those, in the order they went in, with every beat
unchanged. That is rule O5 of the specification, for output 0, with the
routing table deciding which packets are "routed to it".

Each input packet is decided by the routing table entry its DST names. In
this lab the sinks are always ready, so an output never holds more than a
few beats, no packet is ever dropped as FULL, and the prediction is one
line: a packet comes out of output 0 if ROUTE[DST] is enabled and its PORT
is 0. Packets for output 1 or a disabled route aren't checked here.

Report every mismatch with self.error(), which logs the message as an error
and counts it in n_errors. The test fails at the end if the count isn't 0.
"""

import cocotb
from cocotb.simtime import get_sim_time


class Scoreboard:
    def __init__(self, cfg, from_in, from_out0, log):
        self.cfg = cfg
        self.from_in = from_in      # cocotb.queue.Queues of Packets, from the two monitors
        self.from_out0 = from_out0
        self.log = log
        self.expected = []          # packets predicted for output 0, oldest first
        self.n_in = 0               # packets the input monitor saw
        self.n_predicted = 0        # ... of which predicted for output 0
        self.n_checked = 0          # packets from output 0 compared with a prediction
        self.n_errors = 0
        self.first_error = None     # (time in ns, message)

    def error(self, msg):
        self.n_errors += 1
        if self.first_error is None:
            self.first_error = (get_sim_time("ns"), msg)
        self.log.error(msg)

    async def run(self):
        ins = cocotb.start_soon(self.take_inputs())
        outs = cocotb.start_soon(self.take_outputs())
        await ins
        await outs

    async def take_inputs(self):
        while True:
            self.predict(await self.from_in.get())

    async def take_outputs(self):
        while True:
            self.check(await self.from_out0.get())

    def predict(self, p):
        self.n_in += 1
        d = p.dst()
        if self.cfg.route_en(d) and self.cfg.route_port(d) == 0:
            self.expected.append(p)
            self.n_predicted += 1

    def check(self, got):
        if not self.expected:
            self.error(f"out0 delivered {got} at {got.t_last} ns, and no packet was expected")
            return
        want = self.expected.pop(0)
        self.n_checked += 1
        if not got.same(want):
            self.error(f"out0 delivered {got} at {got.t_last} ns; expected {want}, "
                       f"which went in at {want.t_last} ns")

    def report(self):
        """Called once, at the end of the test, after the outputs have drained."""
        for want in self.expected:
            self.error(f"{want}, which went in at {want.t_last} ns, never came out of output 0")
        if self.n_checked == 0:
            self.error("no packet was checked: output 0 delivered nothing that was compared "
                       "with a prediction")
        errors = f"{self.n_errors} error{'' if self.n_errors == 1 else 's'}"
        self.log.info(f"[SB] {self.n_in} packets in, {self.n_predicted} predicted for output 0, "
                      f"{self.n_checked} checked, {errors}")
