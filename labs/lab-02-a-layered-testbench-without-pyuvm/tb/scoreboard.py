"""
DD105-B Lab 02: the scoreboard. You write run(), predict(), check() and the
checks in report() (Part 3 of the lab).

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
        # TODO (Part 3): two loops that both run forever, as two coroutines:
        #  - get a packet from self.from_in and call self.predict() with it;
        #  - get a packet from self.from_out0 and call self.check() with it.
        # Write each loop as an `async def` method of its own, start both with
        # cocotb.start_soon(), and await both tasks.
        pass

    def predict(self, p):
        # TODO (Part 3): count p in n_in. self.cfg.route_en(p.dst()) and
        # self.cfg.route_port(p.dst()) say what ROUTE[DST] is set to. If the
        # packet will come out of output 0, append it to self.expected and
        # count it in n_predicted.
        pass

    def check(self, got):
        # TODO (Part 3): `got` is the next packet output 0 delivered. If
        # nothing is expected, that's an error. Otherwise take the oldest
        # expected packet (self.expected.pop(0)), count the check in
        # n_checked, and report an error if got.same() says the two differ.
        # Put both packets and their t_last times in the message, for example
        #   f"out0 delivered {got} at {got.t_last} ns; expected {want}, which went in at {want.t_last} ns"
        # because it's what you'll read when this fires.
        pass

    def report(self):
        """Called once, at the end of the test, after the outputs have drained."""
        # TODO (Part 3): every packet still in self.expected never came out,
        # which is an error each. And if n_checked is 0, the test checked
        # nothing, which is an error too.
        errors = f"{self.n_errors} error{'' if self.n_errors == 1 else 's'}"
        self.log.info(f"[SB] {self.n_in} packets in, {self.n_predicted} predicted for output 0, "
                      f"{self.n_checked} checked, {errors}")
