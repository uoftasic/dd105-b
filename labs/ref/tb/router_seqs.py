"""
DD105-B reference environment: the virtual sequences, DD105-A's
router_seq_pkg.sv in pyuvm.

A virtual sequence drives every agent at once: the register model (and raw
APB transfers for bad addresses), the source, the sinks' backpressure, and
reset. pyuvm has no p_sequencer, so each one is given the environment and
runs on no sequencer of its own (`await vseq.start()`); its helpers start the
agents' sequences on their sequencers. RouterVseq has the helpers; each
sequence below it sets up one part of the specification and pushes the
router into its corners. None of them checks anything itself: the
scoreboard, the predictor and the assertions check every cycle of every run,
so a sequence only has to make the interesting thing happen. The two
register sequences (router_ral) are the exception: like UVM's, they check
what they read.
"""

import random

import cocotb
from cocotb.triggers import ClockCycles, Lock
from pyuvm import check_t, path_t, uvm_resp_t, uvm_sequence

from apb_agent import ApbRawSeq
from router_common import plusarg
from router_env import ResetSeq
from router_model import bad_addr
from router_ral import RegBitBashSeq, RegResetSeq
from stream_agents import SNK_FAST, SNK_RANDOM, SNK_SLOW, PktSeq, RandPktSeq, make_packet


def dsts_of(mask):
    return tuple(d for d in range(4) if mask >> d & 1)


class RouterVseq(uvm_sequence):
    """The helpers every virtual sequence uses."""

    def __init__(self, name="vseq", env=None):
        super().__init__(name)
        self.env = env

    @property
    def regs(self):
        return self.env.regs

    @property
    def logger(self):
        return self.env.logger

    async def body(self):
        pass

    async def run(self, cls, **knobs):
        """Another virtual sequence, on the same environment."""
        v = cls(cls.__name__, self.env)
        for k, val in knobs.items():
            setattr(v, k, val)
        self.logger.info(f"[VSEQ] starting {cls.__name__}")
        await v.start()

    @staticmethod
    async def par(*coros):
        """Start every coroutine and wait for all of them: SystemVerilog's fork/join."""
        tasks = [cocotb.start_soon(c) for c in coros]
        for t in tasks:
            await t

    # ── time and reset ──────────────────────────────────────────────────────
    async def cycles(self, n):
        if n > 0:
            await ClockCycles(self.env.dut.clk, n)

    async def reset(self, n=3):
        """rst_n low for n cycles. The predictor puts the register model's
        mirror back to the reset values when it sees the reset start."""
        await ResetSeq("reset", n).start(self.env.sys.sqr)

    # ── registers ───────────────────────────────────────────────────────────
    def _lock(self, name):
        """pyuvm raises UVMFatalError for two operations on one register at
        once, where SystemVerilog UVM makes the second wait; a lock per
        register makes it wait here."""
        locks = self.env.__dict__.setdefault("reg_locks", {})
        if name not in locks:
            locks[name] = Lock()
        return locks[name]

    async def wr(self, name, value):
        reg = getattr(self.regs, name)
        async with self._lock(name):
            status = await reg.write(value, self.regs.map, path_t.FRONTDOOR, check_t.NO_CHECK)
        if status != uvm_resp_t.PASS_RESP:
            self.logger.error(f"[VSEQ] writing {value:#x} to {name} returned {status}")

    async def rd(self, name):
        reg = getattr(self.regs, name)
        async with self._lock(name):
            status, value = await reg.read(self.regs.map, path_t.FRONTDOOR, check_t.NO_CHECK)
        if status != uvm_resp_t.PASS_RESP:
            self.logger.error(f"[VSEQ] reading {name} returned {status}")
        return value

    async def rd_all(self):
        for reg in self.regs.regs:
            await self.rd(reg.get_name())

    async def route(self, n, en, port):
        await self.wr(f"ROUTE{n}", (port << 1) | en)

    async def ctrl(self, en):
        await self.wr("CTRL", en)

    async def raw(self, addr, write=False, data=0, idle=0):
        """A transfer to any address, good or bad, outside the register model."""
        seq = ApbRawSeq("raw", addr, data, write, idle)
        await seq.start(self.env.apb.sqr)
        return seq.item

    # ── stimulus ────────────────────────────────────────────────────────────
    async def send(self, pkts):
        await PktSeq("pkts", pkts).start(self.env.src.sqr)

    async def burst(self, dst, n, length=1, tag0=0):
        """n packets of `length` beats to DST `dst`, back to back, tags counting from tag0."""
        await self.send([make_packet(dst, length, tag0 + i) for i in range(n)])

    async def send_rand(self, n, mask=0xF, gap_pct=25, w_over=10):
        await RandPktSeq("rand", n, dsts_of(mask), gap_pct, w_over).start(self.env.src.sqr)

    # ── the sinks ───────────────────────────────────────────────────────────
    def sink(self, p, mode, stall=False):
        self.env.sink_cfg[p].mode = mode
        self.env.sink_cfg[p].stall = stall

    def stall(self, p, on):
        self.env.sink_cfg[p].stall = on

    async def drain(self, budget=3000):
        """Let both outputs empty: fast sinks, then wait until the model holds
        no beats and the source is idle, for 4 cycles in a row. A router that
        keeps beats forever is reported, and the test goes on."""
        self.sink(0, SNK_FAST)
        self.sink(1, SNK_FAST)
        quiet = n = 0
        while quiet < 4 and n < budget:
            await self.cycles(1)
            n += 1
            quiet = quiet + 1 if self.env.sb.idle() and not self.env.src.drv.busy else 0
        if quiet < 4:
            self.logger.error(f"[DRAIN] after {budget} cycles with both sinks always ready, beats are "
                              "still waiting to come out")


# ══════════════════════════════════════════════════════════════════════════════
# Smoke: one configuration, a few dozen packets, every register read.
# ══════════════════════════════════════════════════════════════════════════════
class SmokeVseq(RouterVseq):
    async def body(self):
        await self.reset(4)
        await self.rd_all()                       # every register at its reset value
        await self.route(0, 1, 0)                 # DST 0 to output 0
        await self.route(1, 1, 1)                 # DST 1 to output 1
        await self.route(2, 0, 1)                 # DST 2 disabled (PORT set anyway)
        await self.route(3, 1, 0)                 # DST 3 to output 0
        await self.wr("INT_EN", 0b111)
        await self.ctrl(1)
        self.sink(0, SNK_RANDOM)
        self.sink(1, SNK_RANDOM)
        await self.send([make_packet(0, 3, 1), make_packet(1, 1, 2), make_packet(3, 8, 3),
                         make_packet(2, 2, 4)])
        await self.send_rand(40)
        await self.rd_all()
        await self.drain()
        await self.rd_all()
        await self.wr("STATUS", 0b111)
        await self.wr("DROP_CNT", 0)
        await self.rd_all()


# ══════════════════════════════════════════════════════════════════════════════
# Registers: the two register sequences, then reset values, access policies,
# reserved bits and all 256 addresses.
# ══════════════════════════════════════════════════════════════════════════════
class RegsVseq(RouterVseq):
    PATTERNS = (0xFFFF_FFFF, 0x0000_0000, 0x5555_5555, 0xAAAA_AAAA,
                0x0000_0001, 0x0000_0002, 0x0000_0004, 0xFFFF_FFFE)

    async def set_nonzero(self):
        await self.ctrl(1)
        await self.wr("INT_EN", 0b111)
        for n in range(4):
            await self.route(n, 1, n & 1)

    async def body(self):
        log = self.env.predictor.logger
        await self.reset(3)
        await RegResetSeq("reg_reset_seq", self.regs, log).start()
        await RegBitBashSeq("reg_bit_bash_seq", self.regs, log).start()
        await self.reset(3)
        await self.rd_all()

        # Every address read with the read-write registers at their reset
        # values and then set, so that a bad address that aliases a register
        # returns something other than 0.
        for a in range(256):
            await self.raw(a)
        await self.set_nonzero()
        for a in range(256):
            await self.raw(a, idle=a % 2)

        # Zeros to every bad address, then all ones, and the good registers
        # read after each pass: a bad write changes nothing.
        for a in range(256):
            if bad_addr(a):
                await self.raw(a, True, 0, idle=a % 3)
        await self.rd_all()
        await self.reset(2)
        for a in range(256):
            if bad_addr(a):
                await self.raw(a, True, 0xFFFF_FFFF)
        await self.rd_all()

        # Patterns through the read-write registers; reserved bits read 0.
        # ID and LEVEL ignore writes (written raw: the map has them read-only).
        for pat in self.PATTERNS:
            await self.wr("CTRL", pat)
            await self.wr("INT_EN", pat)
            for n in range(4):
                await self.wr(f"ROUTE{n}", pat >> n)
            await self.raw(0x00, True, pat)
            await self.raw(0x14, True, pat)
            await self.rd_all()
        # STATUS and DROP_CNT written with everything: STATUS has nothing set,
        # and DROP_CNT clears whatever the value.
        await self.wr("STATUS", 0xFFFF_FFFF)
        await self.wr("DROP_CNT", 0xFFFF_FFFF)
        await self.rd_all()

        # Back-to-back transfers: no idle cycle between them.
        for i in range(40):
            await self.raw(0x0C if i % 4 == 3 else 4 * (i % 12), i % 2 == 1, random.getrandbits(32))
        await self.rd_all()


# ══════════════════════════════════════════════════════════════════════════════
# FULL: the admission threshold, from both sides, and independent outputs.
# ══════════════════════════════════════════════════════════════════════════════
class FullVseq(RouterVseq):
    async def body(self):
        await self.reset(3)
        await self.route(0, 1, 0)
        await self.route(1, 1, 1)
        await self.route(2, 1, 0)
        await self.route(3, 1, 1)
        await self.wr("INT_EN", 0b010)
        await self.ctrl(1)
        self.sink(1, SNK_FAST)

        # Nine 1-beat packets into a stalled output 0 are admitted at levels 0
        # to 8; the tenth finds level 9 and is dropped (E5).
        self.sink(0, SNK_FAST, True)
        await self.burst(0, 9, 1, 1)
        await self.cycles(3)
        await self.rd("LEVEL")
        await self.burst(0, 1, 2, 10)
        await self.rd("STATUS")
        await self.rd("DROP_CNT")
        # Output 1 keeps going while output 0 is stalled (O7).
        await self.burst(1, 4, 3, 20)
        await self.burst(3, 2, 8, 30)
        await self.cycles(12)
        await self.rd("LEVEL")
        await self.drain()

        # Two 8-beat packets: the second is admitted at exactly 8 and fills the
        # buffer to 16; the next packet for output 0 is dropped.
        self.stall(0, True)
        await self.burst(0, 2, 8, 1)
        await self.burst(2, 1, 1, 3)
        await self.cycles(3)
        await self.rd("LEVEL")
        await self.rd("DROP_CNT")
        await self.drain()

        # 8 beats, then a 1-beat packet at level 8 (admitted, level 9), then an
        # 8-beat packet at level 9 (dropped, all its beats taken anyway).
        self.stall(0, True)
        await self.burst(0, 1, 8, 1)
        await self.burst(0, 1, 1, 2)
        await self.burst(0, 1, 8, 3)
        await self.rd("LEVEL")

        # Headers arriving in the cycles the sink starts taking beats again:
        # the decision uses the level before that cycle's handshake.
        async def unstall():
            await self.cycles(3)
            self.sink(0, SNK_FAST, False)
        await self.par(self.burst(2, 14, 1, 10), unstall())
        await self.drain()

        # A disabled route whose PORT names a full output: NOROUTE, never FULL.
        # ROUTE1 is disabled with PORT = 0 while output 0 holds 9 beats, and a
        # FULL drop for DST 0 follows each one.
        await self.route(1, 0, 0)
        await self.wr("DROP_CNT", 0)
        await self.wr("STATUS", 0b111)
        self.stall(0, True)
        await self.burst(0, 9, 1, 40)
        for k in range(4):
            await self.burst(1, 1, 3, 50 + k)
            await self.burst(0, 1, 1, 60 + k)
        await self.rd("DROP_CNT")
        await self.rd("STATUS")
        await self.route(1, 1, 1)
        await self.drain()

        # The same threshold on output 1, with random gaps and backpressure.
        self.sink(1, SNK_SLOW)
        await self.send_rand(30, 0b1010, 10, 0)
        await self.rd("LEVEL")
        await self.rd("DROP_CNT")
        await self.drain()
        await self.rd_all()


# ══════════════════════════════════════════════════════════════════════════════
# Oversize packets: cut to 8, the tail thrown away, STATUS.OVERSIZE.
# ══════════════════════════════════════════════════════════════════════════════
class OversizeVseq(RouterVseq):
    async def body(self):
        await self.reset(3)
        await self.route(0, 1, 0)
        await self.route(1, 1, 1)
        await self.route(2, 0, 0)
        await self.route(3, 1, 1)
        await self.wr("INT_EN", 0b100)
        await self.ctrl(1)
        self.sink(0, SNK_FAST)
        self.sink(1, SNK_RANDOM)

        await self.burst(0, 1, 9, 1)              # the shortest oversize packet
        await self.cycles(4)
        await self.rd("STATUS")
        await self.wr("STATUS", 0b100)
        await self.burst(0, 1, 8, 2)              # exactly 8: not oversize
        await self.burst(1, 1, 10, 3)             # E6
        await self.burst(1, 1, 1, 4)              # the next packet is handled normally
        await self.burst(3, 1, 20, 5)
        await self.burst(2, 1, 12, 6)             # oversize and NOROUTE: counted once, both bits
        await self.rd("STATUS")
        await self.rd("DROP_CNT")
        await self.wr("STATUS", 0b111)

        # Oversize with idle cycles inside it, and back to back with others.
        p = make_packet(0, 11, 7)
        p.gaps = [i % 3 for i in range(len(p.data))]
        await self.send([p, make_packet(0, 9, 8), make_packet(1, 9, 9), make_packet(0, 1, 10),
                         make_packet(3, 16, 11)])

        # Oversize while output 1 is full: a FULL drop and OVERSIZE.
        self.sink(1, SNK_FAST, True)
        await self.burst(1, 9, 1, 20)
        await self.burst(1, 1, 13, 30)
        await self.rd("STATUS")
        await self.rd("DROP_CNT")
        await self.drain()
        await self.rd_all()


# ══════════════════════════════════════════════════════════════════════════════
# CTRL.EN: the input stops and starts only between packets (E7).
# ══════════════════════════════════════════════════════════════════════════════
class CtrlVseq(RouterVseq):
    async def body(self):
        await self.reset(3)
        await self.route(0, 1, 0)
        await self.route(1, 1, 1)
        self.sink(0, SNK_FAST)
        self.sink(1, SNK_FAST)

        # CTRL.EN is 0 after reset: a header offered now waits.
        async def enable_later():
            await self.cycles(20)
            await self.rd("CTRL")
            await self.ctrl(1)
        await self.par(self.burst(0, 1, 3, 1), enable_later())

        # E7: CTRL.EN cleared while a packet with idle cycles is coming in. It
        # finishes; the next header waits until CTRL.EN is set again.
        p = make_packet(0, 8, 2)
        p.gaps = [0] + [2] * 7

        async def pause():
            await self.cycles(4)
            await self.ctrl(0)
            await self.cycles(40)
            await self.ctrl(1)
        await self.par(self.send([p, make_packet(1, 2, 3)]), pause())

        # CTRL written while 1-beat packets go in back to back, one per cycle,
        # so some writes complete in the cycle of a header.
        async def toggles():
            await self.cycles(5)
            await self.ctrl(0)
            await self.cycles(6)
            await self.ctrl(1)
            await self.cycles(3)
            await self.ctrl(0)
            await self.cycles(2)
            await self.ctrl(1)
            await self.ctrl(0)
            await self.ctrl(1)
        await self.par(self.burst(0, 60, 1, 0), toggles())

        # The same with longer packets and random gaps.
        async def random_toggles():
            for _ in range(8):
                await self.cycles(random.randint(2, 15))
                await self.ctrl(0)
                await self.cycles(random.randint(1, 10))
                await self.ctrl(1)
        await self.par(self.send_rand(30, 0b0011, 30, 5), random_toggles())
        await self.ctrl(1)
        await self.drain()
        await self.rd_all()


# ══════════════════════════════════════════════════════════════════════════════
# Same-cycle rules: a write and an event in the same cycle.
# ══════════════════════════════════════════════════════════════════════════════
class SameCycleVseq(RouterVseq):
    async def body(self):
        await self.reset(3)
        await self.wr("INT_EN", 0b011)
        await self.ctrl(1)
        self.sink(0, SNK_FAST)
        self.sink(1, SNK_FAST)

        # E9: every route is disabled and 1-beat packets drop one per cycle,
        # so the DROP_CNT write completes in the cycle of a drop.
        async def clear_cnt():
            await self.cycles(10)
            await self.wr("DROP_CNT", 0xFFFF_FFFF)
            await self.rd("DROP_CNT")
        await self.par(self.burst(1, 30, 1, 0), clear_cnt())
        await self.rd("DROP_CNT")

        # A STATUS write that clears NOROUTE in the cycle another drop sets it.
        async def clear_status():
            await self.cycles(10)
            await self.wr("STATUS", 0b001)
            await self.rd("STATUS")
        await self.par(self.burst(2, 30, 1, 0), clear_status())
        await self.rd("STATUS")
        await self.wr("STATUS", 0b111)

        # ROUTE written while its packets go in one per cycle: the header in
        # the write's completion cycle uses the old entry.
        async def reroute():
            await self.cycles(6)
            await self.route(1, 1, 0)
            await self.cycles(5)
            await self.route(1, 1, 1)
            await self.cycles(4)
            await self.route(1, 0, 1)
            await self.route(1, 1, 0)
        await self.par(self.burst(1, 60, 1, 0), reroute())

        # INT_EN written while events keep coming.
        async def int_en():
            await self.cycles(4)
            await self.wr("INT_EN", 0b000)
            await self.wr("INT_EN", 0b001)
            await self.wr("STATUS", 0b001)
        await self.par(self.burst(3, 30, 1, 0), int_en())

        # LEVEL read while beats go in: a beat accepted in a read's first
        # access cycle isn't in the value it returns.
        async def levels(n):
            for _ in range(n):
                await self.rd("LEVEL")
        await self.route(0, 1, 0)
        self.sink(0, SNK_FAST, True)
        await self.par(self.burst(0, 2, 4, 0), levels(6))
        self.sink(0, SNK_RANDOM, False)
        await self.par(self.send_rand(20, 0b0001, 0, 0), levels(20))
        await self.drain()
        await self.rd_all()


# ══════════════════════════════════════════════════════════════════════════════
# Saturation: both counters to 255, and clears.
# ══════════════════════════════════════════════════════════════════════════════
class SaturateVseq(RouterVseq):
    async def body(self):
        await self.reset(3)
        await self.ctrl(1)
        self.sink(0, SNK_FAST)
        self.sink(1, SNK_FAST)

        async def reads(n, gap):
            for _ in range(n):
                await self.cycles(gap)
                await self.rd("DROP_CNT")

        # NOROUTE_CNT: 260 drops, one per cycle, read on the way past 255.
        await self.par(self.burst(0, 260, 1, 0), reads(6, 40))
        await self.rd("DROP_CNT")

        # A clear in the cycle of a drop at 255.
        async def clear():
            await self.cycles(4)
            await self.wr("DROP_CNT", 0)
        await self.par(self.burst(1, 10, 1, 0), clear())
        await self.rd("DROP_CNT")

        # FULL_CNT: fill output 0, then 270 more packets for it.
        await self.route(0, 1, 0)
        self.sink(0, SNK_FAST, True)
        await self.burst(0, 9, 1, 0)
        await self.par(self.burst(0, 270, 1, 0), reads(6, 45))
        await self.rd("DROP_CNT")
        await self.wr("DROP_CNT", 0x1234_5678)
        await self.rd("DROP_CNT")
        await self.burst(0, 1, 1, 0)
        await self.rd("DROP_CNT")
        await self.rd("LEVEL")
        await self.drain()
        await self.rd_all()


# ══════════════════════════════════════════════════════════════════════════════
# Interrupt: each STATUS bit against each INT_EN setting.
# ══════════════════════════════════════════════════════════════════════════════
class IrqVseq(RouterVseq):
    async def body(self):
        await self.reset(3)
        await self.route(0, 1, 0)
        await self.route(1, 0, 0)
        await self.ctrl(1)
        self.sink(0, SNK_FAST)
        self.sink(1, SNK_FAST)
        for en in range(8):
            await self.wr("INT_EN", en)
            await self.burst(1, 1, 1, 0)          # NOROUTE
            await self.burst(0, 1, 9, 1)          # OVERSIZE
            self.sink(0, SNK_FAST, True)
            await self.burst(0, 10, 1, 2)         # the tenth is a FULL drop
            await self.rd("STATUS")
            await self.wr("INT_EN", 0b000)        # irq falls with its enable
            await self.wr("INT_EN", en)           # and rises again
            await self.wr("STATUS", 0b001)        # clear one bit at a time
            await self.cycles(2)
            await self.wr("STATUS", 0b100)
            await self.wr("STATUS", 0b010)
            await self.rd("STATUS")
            await self.drain()
        await self.rd_all()


# ══════════════════════════════════════════════════════════════════════════════
# Reset with packets in flight (E8), in the middle of APB transfers, and with
# a packet half delivered: what Lab 07's capstone needs for B14 and B15.
# ══════════════════════════════════════════════════════════════════════════════
class ResetVseq(RouterVseq):
    async def setup(self):
        """What a reset takes away: every route enabled, two DSTs to each
        output, every interrupt enabled, and the input open."""
        await self.route(0, 1, 0)
        await self.route(1, 1, 1)
        await self.route(2, 1, 0)
        await self.route(3, 1, 1)
        await self.wr("INT_EN", 0b111)
        await self.ctrl(1)

    async def body(self):
        await self.reset(3)
        # The reset values, read before anything is configured: CTRL.EN is 0,
        # and in_ready stays 0 (the scoreboard checks it in every cycle).
        await self.rd_all()
        await self.setup()

        # E8: output 0 stalled with a 2-beat packet waiting in its buffer, and
        # the next packet two beats in when the reset starts. Its third beat
        # waits 3 cycles, so the reset comes before it.
        self.sink(0, SNK_FAST, True)
        self.sink(1, SNK_FAST)
        await self.burst(0, 1, 2, 1)
        p = make_packet(0, 8, 2)
        p.gaps = [0 if i < 2 else 3 for i in range(8)]

        async def reset_soon(wait, n):
            await self.cycles(wait)
            await self.reset(n)
        await self.par(self.send([p]), reset_soon(3, 2))
        # Nothing from before the reset comes out, even with the sink ready.
        self.stall(0, False)
        await self.cycles(20)
        await self.rd_all()
        # CTRL.EN is 0 again: these headers wait until setup() opens the input.
        async def setup_later():
            await self.cycles(10)
            await self.setup()
        await self.par(self.burst(0, 3, 2, 3), setup_later())
        await self.drain()

        # A reset while register transfers are going on: the one in progress
        # is abandoned, and the APB driver starts it again afterwards.
        async def reg_traffic():
            for _ in range(12):
                await self.rd("STATUS")
                await self.wr("INT_EN", 0b101)
        await self.par(reg_traffic(), reset_soon(9, 1))
        await self.setup()

        # A reset with output 1 part way through delivering an 8-beat packet to
        # a slow sink.
        self.sink(1, SNK_SLOW)
        await self.burst(1, 1, 8, 4)
        await self.cycles(12)
        await self.reset(3)
        await self.setup()
        self.sink(1, SNK_RANDOM)
        await self.send_rand(20)

        # A reset in the middle of random traffic.
        async def reset_and_setup():
            await self.cycles(25)
            await self.reset(2)
            await self.setup()
        await self.par(self.send_rand(30), reset_and_setup())
        await self.drain()
        await self.rd_all()


# ══════════════════════════════════════════════════════════════════════════════
# Random: random configurations, traffic, backpressure, register traffic and
# the occasional reset, all at once. +N=<packets> (default 1200), +PHASES=<n>
# (default 6).
# ══════════════════════════════════════════════════════════════════════════════
class RandVseq(RouterVseq):
    n_pkts = None
    n_phases = None
    resets = True

    async def random_config(self):
        for n in range(4):
            await self.route(n, int(random.randrange(100) < 80), random.randrange(2))
        await self.wr("INT_EN", random.randrange(8))
        await self.ctrl(1)

    async def reg_traffic(self):
        while not self.traffic_done:
            k = random.randrange(100)
            await self.cycles(random.randint(0, 30))
            if self.traffic_done:
                break
            if k < 25:
                await self.rd("STATUS")
            elif k < 45:
                await self.rd("DROP_CNT")
            elif k < 60:
                await self.rd("LEVEL")
            elif k < 66:
                await self.wr("STATUS", random.randrange(8))
            elif k < 70:
                await self.wr("DROP_CNT", random.getrandbits(32))
            elif k < 78:
                await self.route(random.randrange(4), int(random.randrange(100) < 75), random.randrange(2))
            elif k < 82:
                await self.wr("INT_EN", random.randrange(8))
            elif k < 86:
                await self.ctrl(0)
                await self.cycles(random.randint(0, 20))
                await self.ctrl(1)
            elif k < 90:
                await self.raw(random.randrange(256))
            elif k < 92:
                await self.raw(0x30 + random.randint(0, 200), True, random.getrandbits(32))
            else:
                await self.rd_all()

    async def sink_traffic(self):
        while not self.traffic_done:
            for p in (0, 1):
                k = random.randrange(100)
                if k < 40:
                    self.sink(p, SNK_RANDOM)
                elif k < 60:
                    self.sink(p, SNK_FAST)
                elif k < 75:
                    self.sink(p, SNK_SLOW)
                else:
                    self.sink(p, SNK_FAST, True)  # stalled
            await self.cycles(random.randint(30, 250))

    async def body(self):
        n_pkts = self.n_pkts or plusarg("N", 1200)
        n_phases = max(1, self.n_phases or plusarg("PHASES", 6))
        per = n_pkts // n_phases
        await self.reset(3)
        await self.random_config()
        for ph in range(n_phases):
            do_reset = self.resets and ph > 0 and random.randrange(100) < 35
            self.logger.info(f"[VSEQ] random phase {ph + 1} of {n_phases}: {per} packets"
                             + (", with a reset" if do_reset else ""))
            self.traffic_done = False

            async def traffic():
                await self.send_rand(per, 0xF, random.randint(0, 40), random.randint(0, 15))
                self.traffic_done = True

            async def a_reset():
                await self.cycles(random.randint(50, 400))
                await self.reset(random.randint(1, 4))
                await self.random_config()

            jobs = [traffic(), self.reg_traffic(), self.sink_traffic()]
            if do_reset:
                jobs.append(a_reset())
            await self.par(*jobs)
            if random.randrange(2):
                await self.drain()
            if random.randrange(2):
                await self.random_config()
        await self.drain()
        await self.rd_all()


# ══════════════════════════════════════════════════════════════════════════════
# All of the above, one after another: the test check-all grades.
# ══════════════════════════════════════════════════════════════════════════════
class AllVseq(RouterVseq):
    async def body(self):
        for cls in (SmokeVseq, RegsVseq, FullVseq, OversizeVseq, CtrlVseq, SameCycleVseq, SaturateVseq,
                    IrqVseq, ResetVseq):
            await self.run(cls)
        await self.run(RandVseq, n_pkts=600, n_phases=4)
