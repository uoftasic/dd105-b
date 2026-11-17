"""
DD105-B Lab 05: the virtual sequences.

A virtual sequence drives every agent from one place: register writes and
reads through the APB agent, packets through the source agent, and each
sink's backpressure through its OutCfg.

  RouterBaseVseq   the steps every virtual sequence uses, written on Lab 04's
                   sequences (ApbRwSeq, RouterRandSeq, RouterOneSeq)
  RouterLab05Vseq  this lab's: backpressure, oversize packets, and routes
                   that move while packets are coming in (Part 4)

pyuvm has no p_sequencer, so a virtual sequence is given the environment
when it is made, and it runs on no sequencer of its own:

    await RouterLab05Vseq("vseq", self.env).start()

Its steps start Lab 04's sequences on the agents' sequencers, as the base
test's steps did. None of them checks anything itself. The scoreboard and
the assertions check every cycle of every run, so a sequence only has to
make the interesting thing happen.
"""

import random

import cocotb
from cocotb.triggers import RisingEdge
from pyuvm import uvm_sequence

from router_agents import (SNK_FAST, SNK_PCT, SNK_RANDOM, SNK_SLOW, ApbRwSeq, RouterOneSeq,
                           RouterPkt, RouterRandSeq)

CTRL, DROP_CNT, ROUTE0 = 0x04, 0x10, 0x20


class RouterBaseVseq(uvm_sequence):
    """The steps are the base test's (Lab 04), rewritten as a sequence's
    methods: a virtual sequence can't call the test's methods, but it
    reaches every sequencer through the environment."""

    def __init__(self, name="vseq", env=None):
        super().__init__(name)
        self.env = env
        self.route_en = 0               # the EN bits this sequence has written, for the packets' c_dst
        self.next_tag = 0               # the next packet's number, for its header
        self.traffic_done = False       # set by a sequence when its packets have all gone in

    async def body(self):
        pass

    @staticmethod
    async def par(*coros):
        """Start every coroutine at once and wait until all of them are done:
        SystemVerilog's fork ... join."""
        tasks = [cocotb.start_soon(c) for c in coros]
        for t in tasks:
            await t

    # ── time ────────────────────────────────────────────────────────────────
    async def cycles(self, n):
        """n clock cycles; each wait ends at a rising edge."""
        for _ in range(n):
            await RisingEdge(self.env.dut.clk)

    # ── registers ───────────────────────────────────────────────────────────
    # One APB transfer each, as the base test's write_reg() and read_reg().
    # The scoreboard checks every DROP_CNT read, so a read is a check, and
    # nothing here needs the value.
    async def wr(self, addr, data):
        await ApbRwSeq("wr", True, addr, data).start(self.env.apb.sqr)

    async def rd(self, addr):
        await ApbRwSeq("rd", False, addr).start(self.env.apb.sqr)

    async def route(self, n, en, port):
        """Routing table entry n: EN and PORT."""
        self.route_en = (self.route_en & ~(1 << n)) | (en << n)
        await self.wr(ROUTE0 + 4 * n, (port << 1) | en)

    async def ctrl(self, en):
        await self.wr(CTRL, en)

    # ── packets ─────────────────────────────────────────────────────────────
    async def send(self, pkts):
        """Packets made by hand, in order, each with the next tag. Returns
        when the last one has gone into the router."""
        for p in pkts:
            p.set_tag(self.next_tag)
            self.next_tag += 1
            await RouterOneSeq("one", p).start(self.env.src.sqr)

    async def burst(self, dst, n, length):
        """n packets of `length` beats for DST dst, back to back. length may
        be more than 8."""
        await self.send([RouterPkt.make(dst, length) for _ in range(n)])

    async def send_rand(self, n, gap_one_in=4, w_over=0):
        """n random packets to the routes this sequence has enabled.
        gap_one_in: one beat in this many waits 1 to 3 idle cycles first (4,
        as in Lab 04; 0 for none). w_over: the weight of oversize packets (9
        to 12 beats) against 100 for the other lengths."""
        seq = RouterRandSeq("rand", n, self.route_en, self.next_tag, gap_one_in, w_over)
        self.next_tag += n
        await seq.start(self.env.src.sqr)

    # ── the sinks ───────────────────────────────────────────────────────────
    def sink(self, p, mode, ready_pct=100):
        """Sink p's mode from now on; ready_pct matters only in SNK_PCT. The
        driver sees the change at the next rising edge."""
        cfg = self.env.out[p].drv.cfg
        cfg.mode = mode
        cfg.ready_pct = ready_pct

    def stall(self, p):
        """Sink p stalled: Lab 04's sink with ready_pct 0."""
        self.sink(p, SNK_PCT, 0)

    async def drain(self):
        """The base test's drain(): both sinks always ready, then wait until
        the scoreboard expects no more beats, or 300 cycles."""
        self.sink(0, SNK_PCT, 100)
        self.sink(1, SNK_PCT, 100)
        for _ in range(300):
            if self.env.sb.outstanding() == 0:
                break
            await self.cycles(1)
        await self.cycles(4)


# ══════════════════════════════════════════════════════════════════════════════
# Lab 05: backpressure, oversize packets, and a routing table that changes
# while packets are coming in.
# ══════════════════════════════════════════════════════════════════════════════
class RouterLab05Vseq(RouterBaseVseq):

    async def backpressure(self):
        """Until traffic_done, every 30 to 250 cycles each sink takes a new
        mode, drawn on its own: SNK_RANDOM, SNK_FAST, SNK_SLOW or stalled."""
        while not self.traffic_done:
            for p in (0, 1):
                k = random.randrange(100)
                if k < 40:
                    self.sink(p, SNK_RANDOM)
                elif k < 60:
                    self.sink(p, SNK_FAST)
                elif k < 80:
                    self.sink(p, SNK_SLOW)
                else:
                    self.stall(p)
            await self.cycles(random.randint(30, 250))

    async def body(self):
        # TODO (Part 4): this sequence's steps. Part 4 of the lab says what
        # each one must do:
        #   1. configure the router: every route enabled, two DSTs to each
        #      output, and CTRL.EN set;
        #   2. stall output 1 and send packets to both outputs, then stall
        #      output 0 instead, with a drain() after each;
        #   3. oversize packets (9 beats or more) to every DST, with both
        #      sinks in SNK_RANDOM, then drain();
        #   4. random packets with oversize ones among them, backpressure(),
        #      and two routes moved to the other output and back while the
        #      packets are in flight, all at once with par(); then drain()
        #      and read DROP_CNT.
        # Until you write them, the sequence does nothing: RouterTest runs
        # Lab 04's RouterInjectTest alone, and RouterLab05Test checks nothing
        # at all.
        pass
