"""
DD105-B Lab 07: the agents. One agent for each kind of port, each with the
same shape: a driver that puts values on the pins, a monitor that reports
what moved on them, and a sequencer for the driver's items.

  RouterPkt        one input packet, the item the source driver sends: Lab 03's
                   RandPacket, with the same fields and constraints, and in
                   Lab 05 an oversize kind that is off until a sequence
                   gives it a weight
  StreamBeat       one beat a monitor saw move, stamped with its cycle and,
                   on an output, how long it waited (Lab 05)
  SrcDriver, SrcMonitor, SrcAgent            the input stream
  OutCfg           one output's knobs: which output, how its sink answers
                   (Lab 05), and how often it's ready
  ReadyItem        what a sink does for one output beat (Lab 05)
  SinkSeq          a sink's sequence: one ReadyItem per beat, forever (Lab 05)
  SinkDriver, OutMonitor, OutAgent           an output stream; the environment
                   makes one OutAgent for each output. SinkDriver is Lab 04's
                   OutReadyDriver, which in Lab 05 can also answer each beat
                   with an item from SinkSeq
  ApbItem, ApbDriver, ApbMonitor, ApbAgent   the APB port; the monitor stamps
                   each transfer with its cycle (Lab 05)
  SysSample, SysMonitor                      rst_n and irq in every cycle (Lab 06)
  ResetState       how the reset driver warns the other drivers that a reset
                   is coming (Lab 07)
  ResetItem, ResetDriver, SysAgent           the reset driver, with the sys
                   monitor beside it (Lab 07)
  RouterRandSeq    n random packets (Lab 03's generator)
  RouterOneSeq     one packet that the test made itself
  ApbRwSeq         one APB transfer
  ResetSeq         one reset (Lab 07)

This is Lab 06's file. Lab 07 adds the reset driver, and teaches two
drivers what to do when rst_n falls in the middle of their work: the source
driver abandons the packet it was sending (rule I3), and the APB driver
keeps psel at 0 while rst_n is 0, abandoning a transfer the reset
interrupts and starting it again afterwards (rule A4). Neither waits any
longer than in Lab 06 when there is no reset, so a test that never resets
runs cycle for cycle as it did in Lab 06. Lab 07's additions are marked
"Lab 07". Nothing in this file is left for you to write.

The timing rule is Lab 02's: every driver changes the router's inputs right
after a rising edge, and every monitor reads the pins at the falling edge in
the middle of the cycle, where nothing is changing. Each monitor counts the
falling edges from the start of the test, so cycle n is the clock period that
holds the nth falling edge, and the monitors agree on it.

Every class here derives from a pyuvm class, so each can be made with
create(), and a test can swap in a subclass through the factory.
"""

import enum
import random

import vsc
from cocotb.triggers import FallingEdge, RisingEdge
from cocotb.utils import get_sim_time
from pyuvm import (ConfigDB, uvm_agent, uvm_analysis_port, uvm_driver,
                   uvm_monitor, uvm_sequence, uvm_sequence_item, uvm_sequencer)
from pyuvm.error_classes import UVMConfigItemNotFound


async def after_rising_edge(dut):
    """Return right after a rising edge: at once if the clock is high, which
    is where every step of a test returns, or at the next rising edge if it is
    low."""
    if not dut.clk.value:
        await RisingEdge(dut.clk)


# ── Lab 07: the warning before a reset ───────────────────────────────────────

class ResetState:
    """How the reset driver warns the drivers that a reset is coming. The
    environment makes one and puts it in ConfigDB as "RESET".

    The reset driver sets `soon` right after the rising edge before the one
    at which it pulls rst_n low, and records the time it did so in
    `soon_time`. Right after the next edge it pulls rst_n low and adds one
    to `epoch`, and it clears `soon` when it lets rst_n go. So right after a
    rising edge a driver can tell three things apart: no reset coming; a
    reset that starts at the next edge (`soon` set in this time step), when
    a transfer already under way carries on for one more cycle, because rule
    A1 holds until rst_n is 0; and a reset that starts at this edge (`soon`
    set at an earlier one), when it must stop at once. The APB driver keeps
    psel at 0 in every reset cycle that way (rule A4), and the source driver
    abandons a packet once `epoch` has moved (rule I3)."""

    def __init__(self):
        self.soon = False
        self.soon_time = 0
        self.epoch = 0

    def starts_now(self):
        """Right after a rising edge: True if rst_n falls at this edge."""
        return self.soon and self.soon_time < get_sim_time("step")


def reset_state(comp):
    """The environment's ResetState, or one that never changes if nothing put
    one in ConfigDB."""
    try:
        return ConfigDB().get(comp, "", "RESET")
    except UVMConfigItemNotFound:
        return ResetState()


# ── the packet ───────────────────────────────────────────────────────────────
# Lab 03's RandPacket, as a sequence item. Its fields and its three
# constraints are Lab 03's: c_dst keeps it on an enabled route, c_kind weights
# the length kinds 25/50/25, and c_len solves length from kind.
# post_randomize() fills in the beats and the idle cycles before them, as Lab
# 03's build() did.
#
# Lab 05 adds a fourth kind, LEN_OVER: an oversize packet of 9 to 12 beats,
# which the router cuts to 8 (router-spec.md, Oversize packets). Its weight,
# w_over, is 0 unless a sequence sets it, so until then every packet is 1 to
# 8 beats, as in Lab 04.

class LenKind(enum.IntEnum):
    LEN_ONE = 0     # 1 beat
    LEN_MID = 1     # 2 to 7 beats
    LEN_MAX = 2     # 8 beats
    LEN_OVER = 3    # 9 to 12 beats (Lab 05)


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
        self.w_over = vsc.uint8_t(0)           # Lab 05: oversize packets, off unless a sequence sets it
        self.gap_one_in = 4                    # Lab 05: one beat in this many waits first (0: none)
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
                             vsc.weight(LenKind.LEN_MAX, self.w_max),
                             vsc.weight(LenKind.LEN_OVER, self.w_over)])

    @vsc.constraint
    def c_len(self):
        with vsc.if_then(self.kind == LenKind.LEN_ONE):
            self.length == 1
        with vsc.else_if(self.kind == LenKind.LEN_MID):
            self.length.inside(vsc.rangelist((2, 7)))
        with vsc.else_if(self.kind == LenKind.LEN_MAX):
            self.length == 8
        with vsc.else_then:
            self.length.inside(vsc.rangelist((9, 12)))

    def post_randomize(self):
        """pyvsc calls this after every randomize()."""
        self.build(random_gaps=True)

    def build(self, random_gaps):
        """Fill data and gaps from hdr_dst, tag and length. The payload is
        random, and with random_gaps one beat in gap_one_in (about one in
        four, as in Lab 03) waits 1 to 3 idle cycles before it is offered;
        without, the beats go back to back. Both come from Python's random,
        not from the solver, as in Lab 03. With gap_one_in at 4 this draws
        exactly what Lab 04's build() drew."""
        n = int(self.length)
        self.data = [(int(self.hdr_dst) << 6) | (self.tag & 0x3F)] + \
                    [random.randrange(256) for _ in range(n - 1)]
        k = self.gap_one_in
        self.gaps = [random.randint(1, 3) if random_gaps and k and random.randrange(k) == 0 else 0
                     for _ in range(n)]

    def set_tag(self, tag):
        """Give the packet its number, which is the header's low six bits."""
        self.tag = tag & 0x3F
        self.data[0] = (int(self.hdr_dst) << 6) | self.tag

    @staticmethod
    def make(dst, length, tag=0):
        """A packet built by hand, without the solver: `length` beats for DST
        `dst`, back to back. `length` may be more than 8 (Lab 05). It is made
        with the constructor, so a factory override never reaches it."""
        p = RouterPkt("pkt")
        p.hdr_dst = dst
        p.kind = (LenKind.LEN_ONE if length == 1 else LenKind.LEN_MID if length < 8 else
                  LenKind.LEN_MAX if length == 8 else LenKind.LEN_OVER)
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

    def __init__(self, port, data, last, cycle, waited=0):
        super().__init__("beat")
        self.port = port        # 0 or 1 for an output, -1 for the input
        self.data = data
        self.last = last
        self.cycle = cycle      # the cycle of the handshake
        self.waited = waited    # Lab 05: cycles it was on offer before that one (outputs only)

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
    rest of its packet is dropped.

    Lab 07: rule I3. A reset ends the packet. In the first reset cycle the
    driver reports the packet as abandoned and, right after the next rising
    edge, lowers in_valid and takes the next packet, whose header it offers
    once the reset is over. Without this it would go on offering the rest of
    the old packet, and the router would take its next beat as a header."""

    MAX_WAIT = 1000

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.rst = reset_state(self)            # Lab 07
        self.abandoned = 0                      # Lab 07: packets a reset cut short

    async def run_phase(self):
        d = self.dut
        d.in_valid.value = 0
        while True:
            p = await self.seq_item_port.get_next_item()
            await after_rising_edge(d)
            await self.send(p)
            d.in_valid.value = 0
            self.seq_item_port.item_done()

    def reset_seen(self, epoch):
        """Lab 07: a reset has started since `epoch`, or rst_n is 0 now."""
        return self.rst.epoch != epoch or not self.dut.rst_n.value

    def abandon(self, p, i):
        """Lab 07: beats 0 to i-1 of p went in before the reset; the rest never will."""
        self.abandoned += 1
        self.logger.info(f"[SRC] reset: abandoned {p} after {i} beat{'' if i == 1 else 's'}")

    async def send(self, p):
        d = self.dut
        # Lab 07: start a packet only outside a reset, and not in the cycle
        # before one.
        while self.rst.soon or not d.rst_n.value:
            d.in_valid.value = 0
            await RisingEdge(d.clk)
        epoch = self.rst.epoch
        for i, beat in enumerate(p.data):
            if p.gaps[i]:
                d.in_valid.value = 0
                for _ in range(p.gaps[i]):
                    await RisingEdge(d.clk)
                    if self.reset_seen(epoch):          # Lab 07
                        self.abandon(p, i)
                        return
            d.in_valid.value = 1
            d.in_data.value = beat
            d.in_last.value = int(i == len(p.data) - 1)
            waited = 0
            while True:
                await FallingEdge(d.clk)
                waited += 1
                if self.reset_seen(epoch):              # Lab 07
                    self.abandon(p, i)
                    await RisingEdge(d.clk)
                    return
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
# How an output's sink answers (Lab 05):
#   SNK_PCT     Lab 04's sink: right after every rising edge out_ready is 1
#               with probability ready_pct percent, whatever is on the
#               output, so 100 is a sink that is always ready and 0 is Lab
#               03's stall. Every test from Lab 04 runs in this mode.
#   SNK_FAST    out_ready is already 1 when each beat appears
#   SNK_RANDOM  each beat's answer drawn at random (ReadyItem.randomize())
#   SNK_SLOW    each beat waits 4 to 20 cycles before out_ready rises

SNK_PCT, SNK_FAST, SNK_RANDOM, SNK_SLOW = "SNK_PCT", "SNK_FAST", "SNK_RANDOM", "SNK_SLOW"


class OutCfg:
    """The knobs of one output agent. The test makes one for each output and
    puts it in ConfigDB for that agent's path. It keeps the handle, so it can
    change ready_pct or mode in the middle of a run, and the driver sees the
    change at the next rising edge."""

    def __init__(self, port):
        self.port = port            # 0 or 1: which output the agent watches
        self.ready_pct = 100        # percent of cycles out_ready is 1 in SNK_PCT; 0 stalls the output
        self.mode = SNK_PCT         # Lab 05: how the sink answers


class ReadyItem(uvm_sequence_item):
    """Lab 05: what a sink does for one beat. out_ready is already 1 when the
    beat appears (pre_ready), or it rises once the beat has been on offer for
    `delay` cycles after the first. Drawn with Python's random rather than
    pyvsc: a sink makes one for every output beat, and at pyvsc's 400 or so
    randomizations a second that would cost seconds a run."""

    def __init__(self, name="ready"):
        super().__init__(name)
        self.pre_ready = True       # out_ready is already 1 when the beat appears
        self.delay = 0              # cycles the beat waits after its first cycle on offer

    def randomize(self):
        """Half the beats pre_ready; the delay 0 for half the items, 1 to 3
        for three in ten, and 4 to 12 for the rest."""
        self.pre_ready = random.randrange(2) == 1
        r = random.randrange(10)
        self.delay = 0 if r < 5 else random.randint(1, 3) if r < 8 else random.randint(4, 12)

    def __str__(self):
        return "pre_ready" if self.pre_ready else f"delay {self.delay}"


class SinkSeq(uvm_sequence):
    """Lab 05: a sink's sequence. One ReadyItem per beat, forever, made the
    way cfg.mode says at the moment the driver asks for it. The base test
    starts one on each output's sequencer before anything else happens, and
    nothing waits for it to finish. start_item() returns only when the
    driver asks for an item, so in SNK_PCT, where the driver asks for none,
    the sequence waits there and draws nothing."""

    def __init__(self, name="sink_seq", cfg=None):
        super().__init__(name)
        self.cfg = cfg

    async def body(self):
        while True:
            r = ReadyItem("ready")
            await self.start_item(r)
            if self.cfg.mode == SNK_FAST:
                r.pre_ready, r.delay = True, 0
            elif self.cfg.mode == SNK_SLOW:
                r.pre_ready, r.delay = False, random.randint(4, 20)
            else:
                r.randomize()
            await self.finish_item(r)


class SinkDriver(uvm_driver):
    """Lab 04's OutReadyDriver, which in Lab 05 can also answer each beat
    with an item from its sequence, as a reactive driver does: the router
    decides when a beat appears, and the item says how the sink responds.

    In SNK_PCT it is Lab 04's driver: right after every rising edge it sets
    out_ready to 1 with probability ready_pct percent, and it asks for no
    items. It draws from Python's random only when ready_pct is between 0
    and 100, as in Lab 04, so a test whose sinks are always ready gets the
    same packets as one with no sink at all.

    In the other modes it holds one item at a time, from when it gets it
    until the beat that item answers is taken. It looks at the output at the
    falling edge in the middle of each cycle, decides out_ready for the next
    cycle there, and drives it right after the rising edge. The monitor
    beside it reports every beat."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.cfg = ConfigDB().get(self, "", "cfg")

    async def run_phase(self):
        d, cfg = self.dut, self.cfg
        valid = getattr(d, f"out{cfg.port}_valid")
        ready = getattr(d, f"out{cfg.port}_ready")
        r = None                    # the item for the beat on offer, or for the next beat
        seen = False                # out_valid has been 1 for the beat r answers
        wait_left = 0               # cycles of r.delay still to wait
        rdy = 0                     # out_ready in this cycle
        while True:
            # The rising edge: out_ready for the cycle that starts here.
            await RisingEdge(d.clk)
            if cfg.mode == SNK_PCT:
                pct = cfg.ready_pct
                rdy = 1 if pct >= 100 else 0 if pct <= 0 else int(random.randrange(100) < pct)
            ready.value = rdy
            if cfg.mode == SNK_PCT and r is None:
                continue            # Lab 04's sink: nothing to decide in the middle of the cycle
            # The middle of the cycle: did a beat move, and what does the sink
            # do in the next cycle?
            await FallingEdge(d.clk)
            v = bool(d.rst_n.value and valid.value)
            if v and rdy:                       # the handshake: r has been answered
                if r is not None:
                    self.seq_item_port.item_done()
                r = None
            elif v and r is not None:
                # The beat r answers is waiting: seen in its first cycle on
                # offer, then one off wait_left a cycle, down to 0.
                if not seen:
                    seen = True
                elif wait_left > 0:
                    wait_left -= 1
            if cfg.mode != SNK_PCT:
                if r is None:
                    # SinkSeq is always waiting with the next item, so this
                    # returns at once.
                    r = await self.seq_item_port.get_next_item()
                    seen, wait_left = False, r.delay
                # out_ready in the next cycle: 1 for a pre_ready item, and
                # otherwise 1 once the beat has been seen and its wait is over.
                rdy = int(r.pre_ready or (seen and wait_left == 0))


class OutMonitor(uvm_monitor):
    """The input's monitor, on one output: it writes a StreamBeat for every
    handshake on out<port>, with port set to the output's number. In Lab 05
    it also stamps each beat with how long it waited: the cycles between
    the first cycle it was on offer and the cycle it was taken."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")
        self.cfg = ConfigDB().get(self, "", "cfg")

    async def run_phase(self):
        d, p = self.dut, self.cfg.port
        valid, ready = getattr(d, f"out{p}_valid"), getattr(d, f"out{p}_ready")
        data, last = getattr(d, f"out{p}_data"), getattr(d, f"out{p}_last")
        cycle = 0
        first = None                # the first cycle the beat on offer was on offer
        while True:
            await FallingEdge(d.clk)
            cycle += 1
            if not (d.rst_n.value and valid.value):
                first = None
                continue
            if first is None:
                first = cycle
            if ready.value:
                self.ap.write(StreamBeat(p, int(data.value), int(last.value), cycle, cycle - first))
                first = None


class OutAgent(uvm_agent):
    """One class, made once for each output. Nothing in it says which output
    it's on: its driver and its monitor take the port number from the OutCfg
    that ConfigDB holds for their path. In Lab 05 it has a sequencer for the
    driver's items; the base test starts a SinkSeq on it."""

    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = SinkDriver.create("drv", self)
        self.mon = OutMonitor.create("mon", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


# ── the APB port ─────────────────────────────────────────────────────────────

class ApbItem(uvm_sequence_item):
    """One APB transfer. rdata and slverr are filled in when it completes,
    and the monitor's copy has the cycle it completed in (Lab 05)."""

    def __init__(self, name="apb_item"):
        super().__init__(name)
        self.write = False
        self.addr = 0
        self.wdata = 0
        self.rdata = 0
        self.slverr = 0
        self.cycle = 0

    def __str__(self):
        return (f"{'WRITE' if self.write else 'READ '} {self.addr:02x} data "
                f"{self.wdata if self.write else self.rdata:08x}{' PSLVERR' if self.slverr else ''}")


class ApbDriver(uvm_driver):
    """Lab 03's ApbMaster.write() and read() in one driver: a setup cycle that
    starts right after the next rising edge, then access cycles until pready.
    A read's data is prdata as it is in the access cycle in which pready is
    1. The item is done right after the rising edge at which the transfer
    completes.

    Lab 07: rule A4, psel is 0 while rst_n is 0. The driver starts no
    transfer while the reset driver has warned that a reset is coming
    (ResetState.soon) or rst_n is 0. After each rising edge of a transfer
    under way it checks whether rst_n falls at that edge, and if it does it
    drops psel at once, so psel is 0 from the first reset cycle. It doesn't
    stop any earlier: rule A1 holds until the reset starts, so a setup cycle
    in the last cycle before it is still followed by an access cycle. The
    transfer is abandoned and started again from its setup cycle once the
    reset is over, so the sequence that sent it still gets its answer.
    `restarts` counts them."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.rst = reset_state(self)            # Lab 07
        self.restarts = 0                       # Lab 07

    def idle(self):
        self.dut.psel.value = 0
        self.dut.penable.value = 0

    def reset_coming(self):
        """Lab 07: right after a rising edge, the next cycle must be idle."""
        return self.rst.soon or not self.dut.rst_n.value

    def reset_now(self):
        """Lab 07: right after a rising edge, rst_n falls at this edge or is 0."""
        return self.rst.starts_now() or not self.dut.rst_n.value

    async def run_phase(self):
        self.idle()
        while True:
            t = await self.seq_item_port.get_next_item()
            while not await self.transfer(t):
                self.restarts += 1          # Lab 07: a reset came first; again
                self.logger.info(f"[APB] reset: abandoned a {'write' if t.write else 'read'} of "
                                 f"{t.addr:02x}; it will start again after the reset")
            self.seq_item_port.item_done()

    async def transfer(self, t):
        """One try at the transfer: True if it completed, False if a reset
        came first (Lab 07)."""
        d = self.dut
        await RisingEdge(d.clk)
        while self.reset_coming():                  # Lab 07: no transfer in a reset
            self.idle()
            await RisingEdge(d.clk)
        d.psel.value = 1
        d.penable.value = 0
        d.pwrite.value = int(t.write)
        d.paddr.value = t.addr
        d.pwdata.value = t.wdata if t.write else 0
        await RisingEdge(d.clk)                     # the setup cycle ends
        if self.reset_now():                        # Lab 07
            self.idle()
            return False
        d.penable.value = 1
        while True:
            await FallingEdge(d.clk)
            done = bool(d.pready.value)
            rdata, slverr = int(d.prdata.value), int(d.pslverr.value)
            await RisingEdge(d.clk)
            if done:
                break
            if self.reset_now():                    # Lab 07
                self.idle()
                return False
        if not t.write:
            t.rdata = rdata
        t.slverr = slverr
        self.idle()
        return True


class ApbMonitor(uvm_monitor):
    """Reads the APB pins at every falling edge and writes one ApbItem for
    each transfer that completes in that cycle (psel, penable and pready all
    1), whoever started it. In Lab 05 it counts the falling edges as the
    stream monitors do, and stamps each transfer with its cycle."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d = self.dut
        cycle = 0
        while True:
            await FallingEdge(d.clk)
            cycle += 1
            if d.rst_n.value and d.psel.value and d.penable.value and d.pready.value:
                t = ApbItem("mon")
                t.cycle = cycle
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


# ── Lab 06: rst_n and irq ────────────────────────────────────────────────────

class SysSample(uvm_sequence_item):
    """rst_n and irq as they were in one cycle."""

    def __init__(self, cycle, rst_n, irq):
        super().__init__("sys")
        self.cycle = cycle
        self.rst_n = rst_n
        self.irq = irq


class SysMonitor(uvm_monitor):
    """Reads rst_n and irq at every falling edge and writes a SysSample for
    every cycle, counting the cycles as the other monitors do. The base test
    drives rst_n at time 0, the reset driver beside this monitor drives it
    after that (Lab 07), and the router drives irq. The scoreboard checks irq
    against its model of STATUS and INT_EN, and follows each reset."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d = self.dut
        cycle = 0
        while True:
            await FallingEdge(d.clk)
            cycle += 1
            self.ap.write(SysSample(cycle, int(d.rst_n.value), int(d.irq.value)))


# ── Lab 07: the reset driver ─────────────────────────────────────────────────

class ResetItem(uvm_sequence_item):
    """A request for a reset: rst_n low for `cycles` cycles."""

    def __init__(self, name="reset", cycles=3):
        super().__init__(name)
        self.cycles = cycles


class ResetDriver(uvm_driver):
    """Drives rst_n after time 0. For each item: right after the next rising
    edge it sets ResetState.soon, right after the edge after that it pulls
    rst_n low, and right after the edge that ends the item's last reset
    cycle it lets rst_n go and clears `soon`. So a reset covers `cycles`
    whole cycles, the first of them two cycles after the item arrives, and
    the APB driver has a cycle's warning. The item is done right after the
    edge at which rst_n goes back to 1, so whatever the sequence does next
    starts in the first cycle after the reset."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.rst = reset_state(self)

    async def run_phase(self):
        d = self.dut
        while True:
            it = await self.seq_item_port.get_next_item()
            await RisingEdge(d.clk)
            self.rst.soon = True
            self.rst.soon_time = get_sim_time("step")
            await RisingEdge(d.clk)
            d.rst_n.value = 0
            self.rst.epoch += 1
            for _ in range(max(1, it.cycles)):
                await RisingEdge(d.clk)
            d.rst_n.value = 1
            self.rst.soon = False
            self.seq_item_port.item_done()


class SysAgent(uvm_agent):
    """Lab 06 had the sys monitor on its own, because nothing in the
    testbench drove rst_n after time 0. Lab 07 puts it beside the reset
    driver and its sequencer."""

    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = ResetDriver.create("drv", self)
        self.mon = SysMonitor.create("mon", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


# ── sequences ────────────────────────────────────────────────────────────────

class RouterRandSeq(uvm_sequence):
    """Lab 03's generator. Each packet is made with RouterPkt.create("pkt"),
    which asks the factory for a RouterPkt, so a test can swap in a subclass
    of RouterPkt without touching this sequence. As in Lab 03, a packet's
    tag is its number, so you can find a packet in a log by its header.
    Lab 05 adds two knobs, copied into each packet: gap_one_in (one beat in
    this many waits 1 to 3 idle cycles first) and w_over (the weight of
    oversize packets, against 100 for the other lengths). Their defaults
    send Lab 04's packets."""

    def __init__(self, name="rand_seq", n=200, route_en=0xF, first_tag=0, gap_one_in=4, w_over=0):
        super().__init__(name)
        self.n, self.route_en, self.first_tag = n, route_en, first_tag
        self.gap_one_in, self.w_over = gap_one_in, w_over

    async def body(self):
        for k in range(self.n):
            p = RouterPkt.create("pkt")
            p.route_en = self.route_en
            p.tag = (self.first_tag + k) & 0x3F
            p.gap_one_in = self.gap_one_in
            p.w_over = self.w_over
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


class ResetSeq(uvm_sequence):
    """Lab 07: one reset of `cycles` cycles. start() returns right after the
    rising edge at which rst_n goes back to 1."""

    def __init__(self, name="reset_seq", cycles=3):
        super().__init__(name)
        self.cycles = cycles

    async def body(self):
        it = ResetItem("reset", self.cycles)
        await self.start_item(it)
        await self.finish_item(it)
