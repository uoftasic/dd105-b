"""
DD105-B Lab 03: the monitor, as Lab 02's solution wrote it.

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
        while True:
            await FallingEdge(self.dut.clk)
            if not self.dut.rst_n.value:
                p = None
                continue
            if self.valid.value and self.ready.value:
                if p is None:
                    p = Packet()
                    p.t_first = int(get_sim_time("ns"))
                p.data.append(int(self.data.value))
                self.n_beats += 1
                if self.last.value:
                    p.t_last = int(get_sim_time("ns"))
                    if self.n_pkts < self.show:
                        self.log.info(f"{p}")
                    await self.to_sb.put(p)
                    self.n_pkts += 1
                    p = None
