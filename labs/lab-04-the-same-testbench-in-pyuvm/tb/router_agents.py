"""
DD105-B Lab 04: the agents. One agent for each kind of port, each with the
same shape: a driver that puts values on the pins, a monitor that reports
what moved on them, and (for the two that take items) a sequencer.

  RouterPkt        one input packet, the item the source driver sends: Lab 03's
                   RandPacket, with the same fields and constraints
  StreamBeat       one beat a monitor saw move, stamped with its cycle
  SrcDriver, SrcMonitor, SrcAgent            the input stream
  OutCfg           one output's knobs: which output, and how often it's ready
  OutReadyDriver, OutMonitor, OutAgent       an output stream; the environment
                   makes one OutAgent for each output it watches
  ApbItem, ApbDriver, ApbMonitor, ApbAgent   the APB port
  RouterRandSeq    n random packets (Lab 03's generator)
  RouterOneSeq     one packet that the test made itself
  ApbRwSeq         one APB transfer

The timing rule is Lab 02's: every driver changes the router's inputs right
after a rising edge, and every monitor reads the pins at the falling edge in
the middle of the cycle, where nothing is changing. Each monitor counts the
falling edges from the start of the test, so cycle n is the clock period that
holds the nth falling edge, and the three monitors agree on it.

Every class here derives from a pyuvm class, so each can be made with
create(), and a test can swap in a subclass through the factory.
"""

import enum
import random

import vsc
from cocotb.triggers import FallingEdge, RisingEdge
from pyuvm import (ConfigDB, uvm_agent, uvm_analysis_port, uvm_component, uvm_driver,
                   uvm_monitor, uvm_sequence, uvm_sequence_item, uvm_sequencer)


async def after_rising_edge(dut):
    """Return right after a rising edge: at once if the clock is high, which
    is where every step of a test returns, or at the next rising edge if it is
    low."""
    if not dut.clk.value:
        await RisingEdge(dut.clk)


# ── the packet ───────────────────────────────────────────────────────────────
# Lab 03's RandPacket, as a sequence item. Its fields and its three
# constraints are Lab 03's: c_dst keeps it on an enabled route, c_kind weights
# the three length kinds 25/50/25, and c_len solves length from kind.
# post_randomize() fills in the beats and the idle cycles before them, as Lab
# 03's build() did. Packets are 1 to 8 beats: nothing here is oversize.

class LenKind(enum.IntEnum):
    LEN_ONE = 0     # 1 beat
    LEN_MID = 1     # 2 to 7 beats
    LEN_MAX = 2     # 8 beats


@vsc.randobj
class RouterPkt(uvm_sequence_item):
    def __init__(self, name="pkt"):
        super().__init__(name)
        self.hdr_dst = vsc.rand_bit_t(2)       # the header's DST: which routing table entry it uses
        self.kind = vsc.rand_enum_t(LenKind)   # one beat, 2 to 7 beats, or exactly 8
        self.length = vsc.rand_uint8_t()       # beats, header included
        self.tag = 0                           # the header's other six bits: the packet's number
        self.route_en = vsc.uint8_t(0xF)       # set by whoever makes it: bit d is ROUTE[d].EN
        # How often each kind comes out, in parts of the total. The solver reads
        # them at every randomize(), so a test can change them first.
        self.w_one = vsc.uint8_t(25)
        self.w_mid = vsc.uint8_t(50)
        self.w_max = vsc.uint8_t(25)
        self.data = []                         # the beats; data[0] is the header
        self.gaps = []                         # idle cycles the driver leaves before each beat

    # Only to enabled routes, so a random packet is never dropped as NOROUTE.
    # The bit is picked with a shift because the index, hdr_dst, is random.
    @vsc.constraint
    def c_dst(self):
        ((self.route_en >> self.hdr_dst) & 1) == 1

    @vsc.constraint
    def c_kind(self):
        vsc.dist(self.kind, [vsc.weight(LenKind.LEN_ONE, self.w_one),
                             vsc.weight(LenKind.LEN_MID, self.w_mid),
                             vsc.weight(LenKind.LEN_MAX, self.w_max)])

    @vsc.constraint
    def c_len(self):
        with vsc.if_then(self.kind == LenKind.LEN_ONE):
            self.length == 1
        with vsc.else_if(self.kind == LenKind.LEN_MID):
            self.length.inside(vsc.rangelist((2, 7)))
        with vsc.else_then:
            self.length == 8

    def post_randomize(self):
        """pyvsc calls this after every randomize()."""
        self.build(random_gaps=True)

    def build(self, random_gaps):
        """Fill data and gaps from hdr_dst, tag and length. The payload is
        random, and with random_gaps about one beat in four waits 1 to 3 idle
        cycles before it is offered, as in Lab 03; without, the beats go back
        to back. Both come from Python's random, not from the solver, as in
        Lab 03."""
        n = int(self.length)
        self.data = [(int(self.hdr_dst) << 6) | (self.tag & 0x3F)] + \
                    [random.randrange(256) for _ in range(n - 1)]
        self.gaps = [random.randint(1, 3) if random_gaps and random.randrange(4) == 0 else 0
                     for _ in range(n)]

    def set_tag(self, tag):
        """Give the packet its number, which is the header's low six bits."""
        self.tag = tag & 0x3F
        self.data[0] = (int(self.hdr_dst) << 6) | self.tag

    @staticmethod
    def make(dst, length, tag=0):
        """A packet built by hand, without the solver: `length` beats for DST
        `dst`, back to back. It is made with the constructor, so a factory
        override never reaches it."""
        p = RouterPkt("pkt")
        p.hdr_dst = dst
        p.kind = (LenKind.LEN_ONE if length == 1 else
                  LenKind.LEN_MID if length < 8 else LenKind.LEN_MAX)
        p.length = length
        p.tag = tag
        p.build(random_gaps=False)
        return p

    def __str__(self):
        """'dst 2, 3 beats: 85 3c f0', as Lab 03 printed a packet."""
        n = len(self.data)
        beats = " ".join(f"{b:02x}" for b in self.data)
        return f"dst {self.data[0] >> 6 if self.data else '-'}, {n} beat{'' if n == 1 else 's'}: {beats}"


class StreamBeat(uvm_sequence_item):
    """A beat that moved: the monitors make one for every handshake."""

    def __init__(self, port, data, last, cycle):
        super().__init__("beat")
        self.port = port        # 0 or 1 for an output, -1 for the input
        self.data = data
        self.last = last
        self.cycle = cycle      # the cycle of the handshake

    def __str__(self):
        """'80 in cycle 23', or '68 last in cycle 1936'."""
        return f"{self.data:02x}{' last' if self.last else ''} in cycle {self.cycle}"


# ── the input stream ─────────────────────────────────────────────────────────

class SrcDriver(uvm_driver):
    """Lab 03's Driver, as a uvm_driver: it takes each packet from the
    sequencer instead of a queue, leaves the packet's idle cycles before its
    beats, and offers each beat (in_valid = 1) until a cycle in which in_ready
    is also 1. That cycle is the handshake, and the beat moves at the rising
    edge that ends it. A beat that waits MAX_WAIT cycles is an error, and the
    rest of its packet is dropped."""

    MAX_WAIT = 1000

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d = self.dut
        d.in_valid.value = 0
        while True:
            p = await self.seq_item_port.get_next_item()
            await after_rising_edge(d)
            await self.send(p)
            d.in_valid.value = 0
            self.seq_item_port.item_done()

    async def send(self, p):
        d = self.dut
        for i, beat in enumerate(p.data):
            if p.gaps[i]:
                d.in_valid.value = 0
                for _ in range(p.gaps[i]):
                    await RisingEdge(d.clk)
            d.in_valid.value = 1
            d.in_data.value = beat
            d.in_last.value = int(i == len(p.data) - 1)
            waited = 0
            while True:
                await FallingEdge(d.clk)
                waited += 1
                if d.in_ready.value:
                    break
                await RisingEdge(d.clk)
                if waited == self.MAX_WAIT:
                    self.logger.error(f"in_ready stayed 0 for {waited} cycles with beat {i} of {p} "
                                      "on offer; dropping the rest of it")
                    return
            await RisingEdge(d.clk)                 # the beat moves at this edge


class SrcMonitor(uvm_monitor):
    """Lab 02's monitor, as a uvm_monitor: it writes each beat to its analysis
    port as the beat moves, instead of putting whole packets in a queue, so any
    number of subscribers can have it, and the monitor doesn't know who they
    are."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d = self.dut
        cycle = 0
        while True:
            await FallingEdge(d.clk)
            cycle += 1
            if d.rst_n.value and d.in_valid.value and d.in_ready.value:
                self.ap.write(StreamBeat(-1, int(d.in_data.value), int(d.in_last.value), cycle))


class SrcAgent(uvm_agent):
    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = SrcDriver.create("drv", self)
        self.mon = SrcMonitor.create("mon", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


# ── an output stream ─────────────────────────────────────────────────────────

class OutCfg:
    """The knobs of one output agent. The test makes one for each output and
    puts it in ConfigDB for that agent's path. It keeps the handle, so it can
    change ready_pct in the middle of a run, and the driver sees the change
    at the next rising edge."""

    def __init__(self, port):
        self.port = port            # 0 or 1: which output the agent watches
        self.ready_pct = 100        # percent of cycles out_ready is 1; 0 stalls the output


class OutReadyDriver(uvm_component):
    """Lab 03's Sink, with its stall knob grown into a percentage: right after
    every rising edge it sets out_ready to 1 with probability ready_pct
    percent, so 100 is the sink that is always ready and 0 is Lab 03's stall.
    It takes no items, so it's a plain component rather than a uvm_driver, and
    it counts nothing: the monitor beside it reports every beat.

    It draws from Python's random only when ready_pct is between 0 and 100. A
    sink that is always ready, or stalled, draws nothing, so a test whose
    sinks are always ready gets the same packets as one with no sink at all."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.cfg = ConfigDB().get(self, "", "cfg")

    async def run_phase(self):
        ready = getattr(self.dut, f"out{self.cfg.port}_ready")
        while True:
            await RisingEdge(self.dut.clk)
            pct = self.cfg.ready_pct
            ready.value = 1 if pct >= 100 else 0 if pct <= 0 else int(random.randrange(100) < pct)


class OutMonitor(uvm_monitor):
    """The input's monitor, on one output: it writes a StreamBeat for every
    handshake on out<port>, with port set to the output's number."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")
        self.cfg = ConfigDB().get(self, "", "cfg")

    async def run_phase(self):
        d, p = self.dut, self.cfg.port
        valid, ready = getattr(d, f"out{p}_valid"), getattr(d, f"out{p}_ready")
        data, last = getattr(d, f"out{p}_data"), getattr(d, f"out{p}_last")
        cycle = 0
        while True:
            await FallingEdge(d.clk)
            cycle += 1
            if d.rst_n.value and valid.value and ready.value:
                self.ap.write(StreamBeat(p, int(data.value), int(last.value), cycle))


class OutAgent(uvm_agent):
    """One class, made once for each output. Nothing in it says which output
    it's on: its driver and its monitor take the port number from the OutCfg
    that ConfigDB holds for their path."""

    def build_phase(self):
        self.drv = OutReadyDriver.create("drv", self)
        self.mon = OutMonitor.create("mon", self)


# ── the APB port ─────────────────────────────────────────────────────────────

class ApbItem(uvm_sequence_item):
    """One APB transfer. rdata and slverr are filled in when it completes."""

    def __init__(self, name="apb_item"):
        super().__init__(name)
        self.write = False
        self.addr = 0
        self.wdata = 0
        self.rdata = 0
        self.slverr = 0

    def __str__(self):
        return (f"{'WRITE' if self.write else 'READ '} {self.addr:02x} data "
                f"{self.wdata if self.write else self.rdata:08x}{' PSLVERR' if self.slverr else ''}")


class ApbDriver(uvm_driver):
    """Lab 03's ApbMaster.write() and read() in one driver: a setup cycle that
    starts right after the next rising edge, then access cycles until pready.
    A read's data is prdata as it is in the access cycle in which pready is
    1. The item is done right after the rising edge at which the transfer
    completes."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d = self.dut
        d.psel.value = 0
        d.penable.value = 0
        while True:
            t = await self.seq_item_port.get_next_item()
            await RisingEdge(d.clk)
            d.psel.value = 1
            d.penable.value = 0
            d.pwrite.value = int(t.write)
            d.paddr.value = t.addr
            d.pwdata.value = t.wdata if t.write else 0
            await RisingEdge(d.clk)                 # the setup cycle ends
            d.penable.value = 1
            while True:
                await FallingEdge(d.clk)
                done = bool(d.pready.value)
                rdata, slverr = int(d.prdata.value), int(d.pslverr.value)
                await RisingEdge(d.clk)
                if done:
                    break
            if not t.write:
                t.rdata = rdata
            t.slverr = slverr
            d.psel.value = 0
            d.penable.value = 0
            self.seq_item_port.item_done()


class ApbMonitor(uvm_monitor):
    """Reads the APB pins at every falling edge and writes one ApbItem for
    each transfer that completes in that cycle (psel, penable and pready all
    1), whoever started it."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d = self.dut
        while True:
            await FallingEdge(d.clk)
            if d.rst_n.value and d.psel.value and d.penable.value and d.pready.value:
                t = ApbItem("mon")
                t.write = bool(d.pwrite.value)
                t.addr = int(d.paddr.value)
                t.wdata = int(d.pwdata.value)
                t.rdata = int(d.prdata.value)
                t.slverr = int(d.pslverr.value)
                self.ap.write(t)


class ApbAgent(uvm_agent):
    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = ApbDriver.create("drv", self)
        self.mon = ApbMonitor.create("mon", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


# ── sequences ────────────────────────────────────────────────────────────────

class RouterRandSeq(uvm_sequence):
    """Lab 03's generator. Each packet is made with RouterPkt.create("pkt"),
    which asks the factory for a RouterPkt, so a test can swap in a subclass
    of RouterPkt without touching this sequence. As in Lab 03, a packet's
    tag is its number, so you can find a packet in a log by its header."""

    def __init__(self, name="rand_seq", n=200, route_en=0xF, first_tag=0):
        super().__init__(name)
        self.n, self.route_en, self.first_tag = n, route_en, first_tag

    async def body(self):
        for k in range(self.n):
            p = RouterPkt.create("pkt")
            p.route_en = self.route_en
            p.tag = (self.first_tag + k) & 0x3F
            await self.start_item(p)
            try:
                p.randomize()
            except Exception as e:
                raise RuntimeError(f"{type(p).__name__} randomize() failed with route_en "
                                   f"{self.route_en:04b}: {type(e).__name__}") from None
            await self.finish_item(p)


class RouterOneSeq(uvm_sequence):
    """One packet that the test made itself, by hand or with randomize()."""

    def __init__(self, name="one_seq", pkt=None):
        super().__init__(name)
        self.pkt = pkt

    async def body(self):
        await self.start_item(self.pkt)
        await self.finish_item(self.pkt)


class ApbRwSeq(uvm_sequence):
    """One APB transfer. After start() returns, `t` holds what came back."""

    def __init__(self, name="apb_rw", write=False, addr=0, wdata=0):
        super().__init__(name)
        self.write, self.addr, self.wdata = write, addr, wdata
        self.t = None

    async def body(self):
        self.t = ApbItem.create("t")
        await self.start_item(self.t)
        self.t.write, self.t.addr, self.t.wdata = self.write, self.addr, self.wdata
        await self.finish_item(self.t)
