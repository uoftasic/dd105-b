"""
DD105-B Lab 02: the monitor. You write run() (Part 2 of the lab).

Watches one valid/ready stream and turns what moves on it into packets. The
environment makes two: `in` on the router's input and `out0` on its output 0.
Both are this class; only the prefix of the signal names they watch differs
(in_valid, in_ready, in_data, in_last, or out0_valid and so on).

A beat moves in a cycle where valid and ready are both 1 (a handshake), at
the rising edge that ends that cycle. A packet is the beats from one
handshake after the last packet's end up to and including the handshake
whose beat has last = 1. Each finished packet goes into the queue to_sb.

The monitor looks at the pins at the falling edge in the middle of each
cycle. The router's outputs change just after a rising edge, and the
testbench changes its inputs just after one too, so at the falling edge
every signal holds the value it has for the whole cycle: the value "in
cycle n", as router-spec.md's "Cycles and handshakes" numbers cycles. A
monitor only reads; it never drives the stream it watches.
"""

from cocotb.triggers import FallingEdge
from cocotb.simtime import get_sim_time

from packet import Packet


class Monitor:
    def __init__(self, name, dut, prefix, to_sb, log, show=0):
        self.name = name            # "in" or "out0", for messages
        self.dut = dut
        self.valid = getattr(dut, f"{prefix}_valid")
        self.ready = getattr(dut, f"{prefix}_ready")
        self.data = getattr(dut, f"{prefix}_data")
        self.last = getattr(dut, f"{prefix}_last")
        self.to_sb = to_sb          # a cocotb.queue.Queue of Packets
        self.log = log
        self.show = show            # log the first `show` packets
        self.n_pkts = 0
        self.n_beats = 0

    async def run(self):
        """Watch the stream forever, one falling edge at a time. At each
        falling edge, self.valid.value and the other signals hold their
        values in the cycle that edge is in."""
        p = None    # the packet being assembled, or None between packets
        # TODO (Part 2): forever, wait for the next falling edge with
        # `await FallingEdge(self.dut.clk)`, then
        #  - while self.dut.rst_n.value is 0, drop any half-assembled packet
        #    (p = None);
        #  - in a handshake cycle (self.valid.value and self.ready.value both 1):
        #      start a new packet if p is None, and set p.t_first to
        #      int(get_sim_time("ns")), the time of this falling edge in ns;
        #      append int(self.data.value) to p.data and count the beat in
        #      self.n_beats;
        #      if self.last.value is 1, the packet is finished: set p.t_last
        #      the same way, log it if self.n_pkts < self.show, as
        #        self.log.info(f"{p}")
        #      put it in to_sb with `await self.to_sb.put(p)`, count it in
        #      self.n_pkts, and set p = None.
