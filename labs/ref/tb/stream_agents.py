"""
DD105-B reference environment: the valid/ready stream agents.

  PktItem      one input packet: its beats, the idle cycles before each beat,
               and whether the source waits for in_ready before raising in_valid
  RandPkt      a PktItem whose length, DST and tag come from pyvsc constraints
  make_packet  a packet built by hand, for the directed steps (no solver)
  ReadyItem    what a sink does for one beat
  SinkCfg      how the virtual sequences steer a sink while traffic runs
  StreamBeat, StreamPkt   what a monitor saw
  SrcDriver, SinkDriver, StreamMonitor, SrcAgent, SinkAgent
  PktSeq, RandPktSeq, SinkSeq

Neither driver blocks forever on the router: the source gives up on a beat
that waits MAX_WAIT cycles for in_ready, logging an error, so a router that
stops answering ends the test with an error instead of a hang.

The source agent has no monitor. The scoreboard reads every pin through
router_env.CycleMonitor, and nothing else in the environment needs the input
packets as transactions. Each sink agent has one, because the coverage
records how long output beats waited.
"""

import random

import vsc
from cocotb.triggers import FallingEdge, RisingEdge
from pyuvm import (ConfigDB, uvm_agent, uvm_analysis_port, uvm_driver, uvm_monitor, uvm_sequence,
                   uvm_sequence_item, uvm_sequencer)

from router_common import Clocked, reset_state


# ── packets ──────────────────────────────────────────────────────────────────

class PktItem(uvm_sequence_item):
    """One input packet: data[i] is beat i (data[0] is the header, DST in its
    top two bits), gaps[i] the idle cycles before beat i. With wait_ready the
    source keeps in_valid at 0 until it sees in_ready = 1 before offering the
    header, which rule I4 allows."""

    def __init__(self, name="pkt", data=None, gaps=None):
        super().__init__(name)
        self.data = list(data or [])
        self.gaps = list(gaps) if gaps is not None else [0] * len(self.data)
        self.wait_ready = False

    def __str__(self):
        return f"PKT DST {self.data[0] >> 6 if self.data else '-'}, {len(self.data)} beats: " + \
               " ".join(f"{b:02x}" for b in self.data)


def make_packet(dst, length, tag=None, gap_pct=0):
    """A packet for DST `dst`, `length` beats long (more than 8 is oversize),
    built without the solver."""
    tag = random.randrange(64) if tag is None else tag & 0x3F
    data = [(dst << 6) | tag] + [random.randrange(256) for _ in range(length - 1)]
    gaps = [random.randint(1, 3) if random.randrange(100) < gap_pct else 0 for _ in data]
    return PktItem("pkt", data, gaps)


LEN_ONE, LEN_MID, LEN_EIGHT, LEN_OVER = 0, 1, 2, 3


@vsc.randobj
class RandPkt(PktItem):
    """A random packet. Its length comes in four kinds, drawn with `dist` from
    weights a sequence can change before randomize() (they are vsc.uint8_t
    attributes, which the solver reads at every call); the length is then
    picked from the kind's range. DST and the tag are uniform unless a
    sequence constrains them inline with randomize_with().

    post_randomize() builds the beats: the header from DST and the tag, and
    the payload bytes, idle cycles and wait_ready from Python's random. No
    constraint mentions them, so the solver would only cost time: pyvsc
    1.1.0 randomizes this object about 400 times a second (probes/).

    pyvsc takes the object's random state from Python's random at its first
    randomize(), and cocotb seeds Python's random from COCOTB_RANDOM_SEED, so
    the same seed repeats the same packets."""

    def __init__(self, name="rand_pkt"):
        super().__init__(name)
        self.kind = vsc.rand_bit_t(2)
        self.length = vsc.rand_uint8_t()
        self.dst = vsc.rand_bit_t(2)
        self.tag = vsc.rand_bit_t(6)
        self.w_one = vsc.uint8_t(20)
        self.w_mid = vsc.uint8_t(50)
        self.w_eight = vsc.uint8_t(20)
        self.w_over = vsc.uint8_t(10)
        self.max_len = vsc.uint8_t(14)
        self.gap_pct, self.max_gap = 25, 3

    @vsc.constraint
    def c_kind(self):
        vsc.dist(self.kind, [vsc.weight(LEN_ONE, self.w_one), vsc.weight(LEN_MID, self.w_mid),
                             vsc.weight(LEN_EIGHT, self.w_eight), vsc.weight(LEN_OVER, self.w_over)])

    @vsc.constraint
    def c_len(self):
        with vsc.if_then(self.kind == LEN_ONE):
            self.length == 1
        with vsc.else_if(self.kind == LEN_MID):
            self.length.inside(vsc.rangelist((2, 7)))
        with vsc.else_if(self.kind == LEN_EIGHT):
            self.length == 8
        with vsc.else_then:
            self.length.inside(vsc.rangelist((9, 64)))
            self.length <= self.max_len

    def post_randomize(self):
        n = int(self.length)
        self.data = [(int(self.dst) << 6) | int(self.tag)] + [random.randrange(256) for _ in range(n - 1)]
        self.gaps = [random.randint(1, self.max_gap) if random.randrange(100) < self.gap_pct else 0
                     for _ in range(n)]
        self.wait_ready = random.randrange(4) == 0


# ── the sinks' items and configuration ──────────────────────────────────────

SNK_FAST, SNK_RANDOM, SNK_SLOW = "fast", "random", "slow"


class ReadyItem(uvm_sequence_item):
    """What a sink does for one beat: raise out_ready before out_valid
    appears (pre_ready), or wait `delay` cycles after out_valid appears and
    then raise it. Drawn with Python's random, not pyvsc: a sink makes one
    per output beat, about 2,500 in RouterAllTest, and at pyvsc's 400 a
    second that alone would add six seconds to every run."""

    def __init__(self, name="ready", pre_ready=True, delay=0):
        super().__init__(name)
        self.pre_ready, self.delay = pre_ready, delay

    def randomize(self):
        self.pre_ready = random.randrange(2) == 1
        r = random.randrange(10)
        self.delay = 0 if r < 5 else random.randint(1, 3) if r < 8 else random.randint(4, 12)


class SinkCfg:
    """How a sink behaves. The virtual sequences change it while traffic runs:
      mode   how SinkSeq makes its items: SNK_FAST (always ready), SNK_RANDOM
             or SNK_SLOW (4 to 20 cycles for every beat)
      stall  True holds out_ready at 0, whatever the item says"""

    def __init__(self, mode=SNK_FAST, stall=False):
        self.mode, self.stall = mode, stall


# ── what the monitors write ──────────────────────────────────────────────────

class StreamBeat(uvm_sequence_item):
    """A beat that moved: its data and last, the cycle of its handshake, and
    the first cycle it was offered (valid = 1)."""

    def __init__(self, data, last, cycle, first_cycle):
        super().__init__("beat")
        self.data, self.last, self.cycle, self.first_cycle = data, last, cycle, first_cycle


class StreamPkt(uvm_sequence_item):
    """The beats of one packet as a monitor assembled them, and the longest
    any of them waited for its handshake."""

    def __init__(self):
        super().__init__("obs_pkt")
        self.data = []
        self.first_cycle = self.last_cycle = 0
        self.max_wait = 0


# ── the source ───────────────────────────────────────────────────────────────

class SrcDriver(uvm_driver, Clocked):
    """Sends each packet beat by beat, holding a beat until in_ready (rules
    I1 and I2), with the packet's idle cycles before each beat. While
    in_valid is 0 it puts random values on in_data and in_last: the router
    must ignore them.

    Rule I3: a reset abandons the packet. If a reset starts while a packet
    is under way (its epoch moves), the driver drops the rest of it and
    takes the next item, which it offers only once the reset is over, so the
    first beat after a reset is always a header."""

    MAX_WAIT = 4000

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.rst = reset_state(self)
        self.busy = False
        self.abandoned = 0

    def idle(self):
        d = self.dut
        d.in_valid.value = 0
        d.in_data.value = random.randrange(256)
        d.in_last.value = random.randrange(2)

    async def run_phase(self):
        self.idle()
        while True:
            pkt = await self.seq_item_port.get_next_item()
            self.busy = True
            if not await self._send(pkt):
                self.abandoned += 1
            self.idle()
            self.busy = False
            self.seq_item_port.item_done()

    async def _send(self, pkt):
        """True if every beat moved, False if a reset or the wait limit cut
        the packet short."""
        d = self.dut
        await self._to_edge(d.clk)
        while self.rst.soon or not d.rst_n.value:
            self.idle()
            await RisingEdge(d.clk)
            self._mark_edge()
        epoch = self.rst.epoch
        for i, beat in enumerate(pkt.data):
            for _ in range(pkt.gaps[i]):
                self.idle()
                await RisingEdge(d.clk)
                if self.rst.epoch != epoch:
                    return False
            if i == 0 and pkt.wait_ready:
                self.idle()
                for _ in range(self.MAX_WAIT):
                    await FallingEdge(d.clk)
                    if d.in_ready.value:
                        break
                    await RisingEdge(d.clk)
                    if self.rst.epoch != epoch:
                        return False
                await RisingEdge(d.clk)
                if self.rst.epoch != epoch:
                    return False
            d.in_valid.value = 1
            d.in_data.value = beat
            d.in_last.value = int(i == len(pkt.data) - 1)
            for _ in range(self.MAX_WAIT):
                await FallingEdge(d.clk)
                if not d.rst_n.value or self.rst.epoch != epoch:
                    await RisingEdge(d.clk)
                    self._mark_edge()
                    return False
                if d.in_ready.value:
                    break
                await RisingEdge(d.clk)
            else:
                self.logger.error(f"in_ready stayed 0 for {self.MAX_WAIT} cycles with beat {i} "
                                  f"offered; abandoning {pkt}")
                await RisingEdge(d.clk)
                self._mark_edge()
                return False
            await RisingEdge(d.clk)                  # the beat moves at this edge
        self._mark_edge()
        return True


class SrcAgent(uvm_agent):
    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = SrcDriver.create("drv", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


# ── the sinks ────────────────────────────────────────────────────────────────

class SinkDriver(uvm_driver):
    """A reactive sink. Each ReadyItem is the response to one beat: out_ready
    is already 1 before out_valid appears (pre_ready), or it rises `delay`
    cycles after out_valid appears. SinkCfg.stall holds out_ready at 0
    whatever the item says. Like the source, it decides at the falling edge
    (did a beat move? what does the next cycle hold?) and drives right after
    the rising edge. The sink has no obligations (router-spec.md), so any
    pattern is legal; the scoreboard follows the out_ready it samples."""

    def __init__(self, name, parent, port=0):
        super().__init__(name, parent)
        self.port = port

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.cfg = ConfigDB().get(self, "", "SINK_CFG")

    async def run_phase(self):
        d = self.dut
        valid = getattr(d, f"out{self.port}_valid")
        ready = getattr(d, f"out{self.port}_ready")
        ready.value = 0
        rdy = 0
        item = await self.seq_item_port.get_next_item()
        seen, wait_left = False, item.delay
        while True:
            await FallingEdge(d.clk)
            v = d.rst_n.value and valid.value
            if v and rdy:                                    # a handshake this cycle
                self.seq_item_port.item_done()
                item = await self.seq_item_port.get_next_item()
                seen, wait_left = False, item.delay
            elif v:
                if not seen:
                    seen = True
                elif wait_left > 0 and not self.cfg.stall:
                    wait_left -= 1
            rdy = int(not self.cfg.stall and (item.pre_ready or (seen and wait_left == 0)))
            await RisingEdge(d.clk)
            ready.value = rdy


class StreamMonitor(uvm_monitor):
    """Watches one valid/ready stream (prefix "in", "out0" or "out1") at
    every falling edge. Writes a StreamBeat to beat_ap for every handshake
    and a StreamPkt to pkt_ap for every packet that ends with last = 1. A
    reset drops a half-assembled packet."""

    def __init__(self, name, parent, prefix="out0"):
        super().__init__(name, parent)
        self.prefix = prefix

    def build_phase(self):
        self.beat_ap = uvm_analysis_port("beat_ap", self)
        self.pkt_ap = uvm_analysis_port("pkt_ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d, p = self.dut, self.prefix
        valid, ready = getattr(d, f"{p}_valid"), getattr(d, f"{p}_ready")
        data, last = getattr(d, f"{p}_data"), getattr(d, f"{p}_last")
        cycle, first, pkt = 0, None, None
        while True:
            await FallingEdge(d.clk)
            cycle += 1
            if not d.rst_n.value:
                first, pkt = None, None
                continue
            if not valid.value:
                first = None
                continue
            if first is None:
                first = cycle
            if ready.value:
                b = StreamBeat(int(data.value), int(last.value), cycle, first)
                self.beat_ap.write(b)
                if pkt is None:
                    pkt = StreamPkt()
                    pkt.first_cycle = cycle
                pkt.data.append(b.data)
                pkt.max_wait = max(pkt.max_wait, cycle - first)
                if b.last:
                    pkt.last_cycle = cycle
                    self.pkt_ap.write(pkt)
                    pkt = None
                first = None


class SinkAgent(uvm_agent):
    def __init__(self, name, parent, port=0):
        super().__init__(name, parent)
        self.port = port

    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        # create() takes only a name and a parent, so the port goes in afterwards;
        # build_phase reaches the children only after this one returns.
        self.drv = SinkDriver.create("drv", self)
        self.drv.port = self.port
        self.mon = StreamMonitor.create("mon", self)
        self.mon.prefix = f"out{self.port}"

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


# ── sequences ────────────────────────────────────────────────────────────────

class PktSeq(uvm_sequence):
    """Sends a list of PktItems, in order."""

    def __init__(self, name="pkt_seq", pkts=()):
        super().__init__(name)
        self.pkts = list(pkts)

    async def body(self):
        for p in self.pkts:
            await self.start_item(p)
            await self.finish_item(p)


class RandPktSeq(uvm_sequence):
    """Sends n RandPkts. dsts limits the DST values (an inline constraint);
    the other knobs are copied into each packet before it is randomized."""

    def __init__(self, name="rand_pkts", n=20, dsts=(0, 1, 2, 3), gap_pct=25, w_over=10,
                 max_len=14):
        super().__init__(name)
        self.n, self.dsts, self.gap_pct, self.w_over, self.max_len = n, tuple(dsts), gap_pct, w_over, max_len

    async def body(self):
        for _ in range(self.n):
            p = RandPkt("pkt")
            p.w_over = self.w_over
            p.max_len = self.max_len
            p.gap_pct = self.gap_pct
            if len(self.dsts) < 4:
                with p.randomize_with() as it:
                    it.dst.inside(vsc.rangelist(*self.dsts))
            else:
                p.randomize()
            await self.start_item(p)
            await self.finish_item(p)


class SinkSeq(uvm_sequence):
    """A sink's sequence: one ReadyItem per beat, forever, made the way the
    sink's SinkCfg.mode says. The test starts one on each sink and leaves it
    running."""

    def __init__(self, name="sink_seq", cfg=None):
        super().__init__(name)
        self.cfg = cfg

    async def body(self):
        while True:
            r = ReadyItem("ready")
            if self.cfg.mode == SNK_FAST:
                r.pre_ready, r.delay = True, 0
            elif self.cfg.mode == SNK_SLOW:
                r.pre_ready, r.delay = False, random.randint(4, 20)
            else:
                r.randomize()
            await self.start_item(r)
            await self.finish_item(r)
