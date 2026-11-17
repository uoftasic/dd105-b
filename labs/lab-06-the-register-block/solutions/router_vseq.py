"""
DD105-B Lab 06: the virtual sequences.

A virtual sequence drives every agent from one place: register writes and
reads through the APB agent, packets through the source agent, and each
sink's backpressure through its OutCfg.

  RouterBaseVseq   the steps every virtual sequence uses, written on Lab 04's
                   sequences (ApbRwSeq, RouterRandSeq, RouterOneSeq) and, in
                   Lab 06, on the register model
  RouterLab05Vseq  Lab 05's: backpressure, oversize packets, and routes that
                   move while packets are coming in
  RouterLab06Vseq  this lab's: the register model's sequences, the addresses
                   outside the map, and STATUS and INT_EN (Parts 2 to 5)

pyuvm has no p_sequencer, so a virtual sequence is given the environment
when it is made, and it runs on no sequencer of its own:

    await RouterLab05Vseq("vseq", self.env).start()

Its steps start Lab 04's sequences on the agents' sequencers, as the base
test's steps did. None of them checks anything itself. The scoreboard and
the assertions check every cycle of every run, so a sequence only has to
make the interesting thing happen.

Lab 06 adds the register helpers wr_reg(), rd_reg(), check_reg() and
rd_all_regs(), which go through the register model, to the raw ones,
wr() and rd(), which go around it. This is the reference solution:
RouterLab05Vseq.body() is our Lab 05 solution, and RouterLab06Vseq.body()
is filled in, as Parts 2 to 5 of the lab ask.
"""

import random

import cocotb
from cocotb.triggers import Lock, RisingEdge
from pyuvm import check_t, path_t, uvm_resp_t, uvm_sequence

from router_agents import (SNK_FAST, SNK_PCT, SNK_RANDOM, SNK_SLOW, ApbRwSeq, RouterOneSeq,
                           RouterPkt, RouterRandSeq)
from router_ral import RegBitBashSeq, RegResetSeq, good_addr, volatile_mask

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

    # ── registers, raw ──────────────────────────────────────────────────────
    # One APB transfer each, as the base test's write_reg() and read_reg(),
    # to any address, good or bad: these go around the register model. The
    # scoreboard checks every DROP_CNT read, so a read is a check, and
    # nothing here needs the value. In Lab 06 the scoreboard also checks
    # PSLVERR on every transfer, and every read of STATUS and of a bad
    # address.
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

    # ── Lab 06: registers through the register model ────────────────────────
    # Each helper takes a register of the model (self.regs.CTRL,
    # self.regs.ROUTE[2], ...). The map turns the operation into one APB
    # transfer through the adapter, so the APB monitor, the scoreboard and
    # the predictor see it as they see a raw one. pyuvm raises
    # UVMFatalError for two operations on one register at once, where
    # SystemVerilog UVM makes the second wait, so each helper holds a lock
    # for its register while the operation runs.
    @property
    def regs(self):
        return self.env.regs

    @property
    def logger(self):
        """A pyuvm sequence has no logger, so the virtual sequences report
        through the env's, which BaseTest counts."""
        return self.env.logger

    def lock(self, reg):
        locks = self.env.__dict__.setdefault("reg_locks", {})
        if reg.get_name() not in locks:
            locks[reg.get_name()] = Lock()
        return locks[reg.get_name()]

    async def wr_reg(self, reg, value):
        """Write value to reg through the model."""
        async with self.lock(reg):
            status = await reg.write(value, self.regs.map, path_t.FRONTDOOR, check_t.NO_CHECK)
        if status != uvm_resp_t.PASS_RESP:
            self.logger.error(f"[VSEQ] writing {value:#x} to {reg.get_name()} returned {status.name}")

    async def rd_reg(self, reg):
        """Read reg through the model, and return the value read. The
        scoreboard checks every read of STATUS, and the predictor, once it
        is connected (Part 3), checks every read against the mirror outside
        the volatile fields."""
        async with self.lock(reg):
            status, value = await reg.read(self.regs.map, path_t.FRONTDOOR, check_t.NO_CHECK)
        if status != uvm_resp_t.PASS_RESP:
            self.logger.error(f"[VSEQ] reading {reg.get_name()} returned {status.name}")
        return value

    async def check_reg(self, reg):
        """Read reg through the model and compare the value read with what
        the mirror held before the read, outside the volatile fields: what
        SystemVerilog UVM's mirror(UVM_CHECK) does, which pyuvm doesn't
        have. The mirror is taken first because the predictor, once it's
        connected, puts the value read in it as the read completes."""
        dc = volatile_mask(reg)
        want = reg.get_mirrored_value()
        got = await self.rd_reg(reg)
        if (got | dc) != (want | dc):
            self.logger.error(f"[VSEQ] check_reg: {reg.get_name()} read {got:#x}; "
                              f"the mirror held {want:#x}")

    async def rd_all_regs(self):
        """Every register read once through the model, in address order."""
        for reg in self.regs.regs:
            await self.rd_reg(reg)

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
        # 1. The configuration: every route enabled, two DSTs to each output.
        await self.route(0, 1, 0)
        await self.route(1, 1, 1)
        await self.route(2, 1, 0)
        await self.route(3, 1, 1)
        await self.ctrl(1)

        # 2. Output 1 stalled while packets go to both outputs, then output 0
        #    stalled instead.
        self.stall(1)
        self.sink(0, SNK_FAST)
        await self.burst(0, 4, 3)
        await self.burst(1, 2, 3)
        await self.cycles(10)
        await self.drain()
        self.stall(0)
        self.sink(1, SNK_FAST)
        await self.burst(1, 4, 3)
        await self.burst(0, 2, 3)
        await self.cycles(10)
        await self.drain()

        # 3. Oversize packets to every DST, with both sinks random. Each
        #    should come out cut to 8 beats, the 8th with out_last.
        self.sink(0, SNK_RANDOM)
        self.sink(1, SNK_RANDOM)
        await self.burst(0, 1, 9)
        await self.burst(1, 1, 12)
        await self.burst(2, 2, 10)
        await self.burst(3, 1, 20)
        await self.drain()

        # 4. Everything at once: random packets with oversize ones among them,
        #    while each sink changes its mode on its own and two routes move
        #    to the other output and back.
        self.traffic_done = False

        async def traffic():
            await self.send_rand(300, gap_one_in=5, w_over=15)
            self.traffic_done = True

        async def moves():
            await self.cycles(150)
            await self.route(1, 1, 0)
            await self.cycles(150)
            await self.route(2, 1, 1)
            await self.cycles(150)
            await self.route(1, 1, 1)
            await self.route(2, 1, 0)

        await self.par(traffic(), self.backpressure(), moves())
        await self.drain()
        await self.rd(DROP_CNT)


# ══════════════════════════════════════════════════════════════════════════════
# Lab 06: the register block. RouterTest runs this first, while the router
# still holds its reset values, and RouterLab06Test runs it alone.
# ══════════════════════════════════════════════════════════════════════════════
class RouterLab06Vseq(RouterBaseVseq):

    async def body(self):
        # Part 2: the reset values. The sequence reads every register with a
        # field it can check and compares it with its reset value.
        await RegResetSeq("RegResetSeq", self.regs, self.logger).start()

        # Part 3: every bit of every register written and read back. Then the
        # router set up with raw APB writes, as Labs 04 and 05 do, and read
        # back through the model, which knows about them only through the
        # predictor.
        await RegBitBashSeq("RegBitBashSeq", self.regs, self.logger).start()
        await self.route(0, 1, 0)
        await self.route(1, 1, 1)
        await self.route(2, 0, 1)
        await self.route(3, 1, 1)
        await self.ctrl(1)
        await self.check_reg(self.regs.CTRL)
        for r in self.regs.ROUTE:
            await self.check_reg(r)

        # Part 4: the 246 addresses outside the map, which the model can't
        # reach. Each must end with PSLVERR, read 0 and change nothing.
        for a in range(256):
            if not good_addr(a):
                await self.rd(a)
        for a in range(256):
            if not good_addr(a):
                await self.wr(a, 0xFFFF_FFFF)
        await self.rd_all_regs()

        # Part 5: STATUS and INT_EN. DST 1 is disabled, so its packet is a
        # NOROUTE drop; a 9-beat packet is OVERSIZE; and ten packets into a
        # stalled, empty output 0 end with a FULL drop. INT_EN is 0 all the
        # while, so irq stays 0.
        await self.route(1, 0, 0)
        self.sink(0, SNK_FAST)
        self.sink(1, SNK_FAST)
        await self.burst(1, 1, 1)               # NOROUTE
        await self.burst(0, 1, 9)               # OVERSIZE
        await self.drain()
        self.stall(0)
        await self.burst(0, 10, 1)              # FULL
        await self.rd_reg(self.regs.STATUS)
        # Each enable on its own: irq follows the one bit it lets through.
        for b in range(3):
            await self.wr_reg(self.regs.INT_EN, 1 << b)
            await self.cycles(2)
        # Every enable on, and the bits cleared one at a time: irq stays 1
        # until the last one goes.
        await self.wr_reg(self.regs.INT_EN, 0b111)
        await self.wr_reg(self.regs.STATUS, 0b001)
        await self.rd_reg(self.regs.STATUS)
        await self.wr_reg(self.regs.STATUS, 0b100)
        await self.rd_reg(self.regs.STATUS)
        await self.wr_reg(self.regs.STATUS, 0b010)
        await self.rd_reg(self.regs.STATUS)
        await self.drain()
        await self.rd_all_regs()
