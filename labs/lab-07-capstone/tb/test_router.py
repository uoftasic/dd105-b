"""
DD105-B Lab 07: the tests. Every one runs on the same simulator, and TEST=
picks one when the simulator starts:

  RouterTest        RouterLab06Vseq, then RouterInjectTest's steps, then
                    RouterLab05Vseq, then RouterLab07Vseq; make check, make
                    check-all and the hunts grade this one
  RouterLab07Test   RouterLab07Vseq on its own (Lab 07)
  RouterResetTest   RouterResetVseq on its own (Lab 07, Part 5)
  RouterSaturateTest  RouterSaturateVseq on its own (Lab 07, Part 6)
  RouterLab06Test   Lab 06's: RouterLab06Vseq on its own, the first part of
                    RouterTest, cycle for cycle
  RouterLab05Test   Lab 05's: RouterLab05Vseq on its own
  RouterSinkTest    Lab 05's: RouterRandTest with both sinks in SNK_RANDOM,
                    each beat answered by an item
  RouterInjectTest  Lab 04's: RouterStallTest, with NoroutePkt swapped in for
                    RouterPkt by a factory override
  RouterStallTest   Lab 04's: RouterRandTest, with one output stalled in each
                    phase while the other runs
  RouterRandTest    Lab 03's router_rand_test: CTRL.EN, then +PHASES phases
                    of +N random packets, each with its own random routing
                    table and a DROP_CNT check; then close_holes() and a last
                    DROP_CNT check
  RouterFillTest    Lab 03's close_holes() on its own
  RouterClassTest   Lab 02's test: +N random packets on +ROUTES, and a
                    DROP_CNT check

Plusargs: +N=<packets> (200 a phase; 100 in RouterClassTest), +PHASES=<n>
(4), +ROUTES=<abcd> (0110, RouterClassTest only), +MAX_CYCLES=<n> (200000),
and +OVERRIDE=<class>,<class>, a factory override by name, which the base
test applies before it builds anything.

This is Lab 06's file, with Lab 07's change to RouterTest and its three
tests at the end, marked "Lab 07". The base test starts a SinkSeq on each
output before anything else (Lab 05). Nothing in this file is left for you
to write.

Every test derives from RouterLabTest, which derives from the course's
RouterBaseTest (labs/common/py/dd105b_base.py). BaseTest's final_phase fails
the test if any component logged an error. Lab 03's tests counted their
errors and asserted at the end; BaseTest does the same for every component.
"""

import random

import cocotb
import pyuvm
import vsc
from cocotb.triggers import ClockCycles, First, RisingEdge
from pyuvm import ConfigDB, uvm_factory

from dd105b_base import RouterBaseTest
from router_agents import (SNK_PCT, SNK_RANDOM, ApbRwSeq, OutCfg, RouterOneSeq, RouterPkt,
                           RouterRandSeq, SinkSeq)
from router_env import RouterEnv
from router_vseq import (RouterLab05Vseq, RouterLab06Vseq, RouterLab07Vseq, RouterResetVseq,
                         RouterSaturateVseq)

CTRL, DROP_CNT, ROUTE0 = 0x04, 0x10, 0x20


def plusarg(name, default):
    try:
        return int(cocotb.plusargs.get(name, default))
    except ValueError:
        raise ValueError(f"+{name} takes a whole number") from None


@vsc.randobj
class FillPlan:
    """Lab 03's FillPlan: packet lengths that add up to 8. A 0 is "no
    packet", so the plan has 1 to 8 packets."""

    def __init__(self):
        self.lens = vsc.rand_list_t(vsc.uint8_t(), sz=8)

    @vsc.constraint
    def c_sum(self):
        with vsc.foreach(self.lens, idx=True) as i:
            self.lens[i] <= 8
        self.lens.sum == 8


# ── the base test ────────────────────────────────────────────────────────────
# Lab 03's tests made the environment and called its steps (write_routes,
# enable, send_random, send, drain, check_drops and so on). Here build_phase
# builds, the agents fetch what they need from ConfigDB, and those steps are
# methods of the base test, written on the agents' sequences.

class RouterLabTest(RouterBaseTest):
    def build_phase(self):
        super().build_phase()
        self.max_cycles = plusarg("MAX_CYCLES", 200000)
        override = cocotb.plusargs.get("OVERRIDE")
        if override:
            names = str(override).split(",")
            if len(names) != 2:
                raise ValueError(f"+OVERRIDE={override}: give two class names, the original and "
                                 "its replacement, for example +OVERRIDE=RouterPkt,NoroutePkt")
            uvm_factory().set_type_override_by_name(names[0], names[1])
            self.logger.info(f"[OVERRIDE] the factory makes {names[1]} for every {names[0]} "
                             "(+OVERRIDE)")
        self.ocfg = [OutCfg(0), OutCfg(1)]     # each output agent's knobs; the test keeps the handles
        for p in (0, 1):
            ConfigDB().set(self, f"env.out{p}*", "cfg", self.ocfg[p])
        self.env = RouterEnv.create("env", self)
        self.routes = "----"                    # the routing table written last, as +ROUTES writes it
        self.route_en = 0                       # ... and its EN bits, for the packets' c_dst
        self.next_tag = 0                       # the next packet's number, for its header

    async def run_phase(self):
        self.raise_objection()
        # Lab 05: each sink's sequence runs for the whole test, so its driver
        # always has the next item when it asks for one. Nothing waits for it.
        for p in (0, 1):
            cocotb.start_soon(SinkSeq(f"sink{p}_seq", self.ocfg[p]).start(self.env.out[p].sqr))
        await self.reset()
        body = cocotb.start_soon(self.body())
        dog = cocotb.start_soon(self.watchdog(self.max_cycles))
        await First(body.complete, dog.complete, self.env.sb.stop.wait())
        for t in (body, dog):
            if t.done():
                # Waiting on a task's `complete` doesn't raise what the task
                # raised, and cocotb then counts it as handled: without this
                # line a NameError in body() would end it, and the test pass.
                t.result()
            else:
                t.cancel()
        self.drop_objection()

    async def watchdog(self, n):
        await ClockCycles(self.dut.clk, n)
        self.logger.error(f"[WATCHDOG] the test was still running after {n} cycles (+MAX_CYCLES)")

    async def body(self):
        """What the test does; each test overrides it."""

    # Lab 03's ApbMaster.write() and read(), as one-item sequences on the APB
    # agent. The APB monitor reports both to the scoreboard.
    async def write_reg(self, addr, data):
        await ApbRwSeq("wr", True, addr, data).start(self.env.apb.sqr)

    async def read_reg(self, addr):
        s = ApbRwSeq("rd", False, addr)
        await s.start(self.env.apb.sqr)
        return s.t.rdata

    async def write_routes(self, routes):
        """ROUTE0 to ROUTE3, written as Lab 03's Env.write_routes() wrote
        them: one character per route, 0 or 1 for the output, - for disabled
        (written with PORT 0). The scoreboard follows the table from the APB
        writes, so call this only while no packet is coming in."""
        if len(routes) != 4 or any(c not in "01-" for c in routes):
            raise ValueError(f"routes {routes}: give four characters, each 0, 1 or - (disabled), "
                             "for example 0110")
        self.routes = routes
        self.route_en = sum(1 << d for d in range(4) if routes[d] != "-")
        for d in range(4):
            await self.write_reg(ROUTE0 + 4 * d, (int(routes[d] == "1") << 1) | int(routes[d] != "-"))

    async def enable(self):
        """CTRL.EN, which opens the input."""
        await self.write_reg(CTRL, 1)

    def new_packet(self):
        """A new packet that knows which routes are enabled, not yet
        randomized, for close_holes(). It's made with the constructor rather
        than through the factory, so a factory override doesn't reach it."""
        p = RouterPkt("pkt")
        p.route_en = self.route_en
        return p

    async def send_random(self, n):
        """n random packets for the routes written last. Returns when the
        last one has gone into the router."""
        seq = RouterRandSeq("rand_seq", n, self.route_en, self.next_tag)
        self.next_tag += n
        await seq.start(self.env.src.sqr)

    async def send(self, pkts):
        """Packets the test made itself, in order, each with the next tag.
        Returns when the last one has gone into the router."""
        for p in pkts:
            p.set_tag(self.next_tag)
            self.next_tag += 1
            await RouterOneSeq("one_seq", p).start(self.env.src.sqr)

    async def cycles(self, n):
        for _ in range(n):
            await RisingEdge(self.dut.clk)

    def sink_desc(self, p):
        """How sink p answers, for the [PHASE] line: 'ready 5%' in SNK_PCT,
        as Lab 04 printed it, or the name of its mode (Lab 05)."""
        c = self.ocfg[p]
        return f"ready {c.ready_pct}%" if c.mode == SNK_PCT else c.mode

    async def drain(self):
        """Make both outputs ready and wait until the scoreboard expects
        nothing more, or 300 cycles."""
        for c in self.ocfg:
            c.ready_pct = 100
        for _ in range(300):
            if self.env.sb.outstanding() == 0:
                break
            await RisingEdge(self.dut.clk)
        await self.cycles(4)

    async def check_drops(self):
        """Lab 03's check_drops(): read DROP_CNT. The scoreboard compares what
        the read returns with the drops it predicted."""
        await self.read_reg(DROP_CNT)

    async def clear_drops(self):
        """Write DROP_CNT, which clears both counters. The scoreboard sees the
        write and clears its counts too."""
        await self.write_reg(DROP_CNT, 0)

    async def close_holes(self):
        """Lab 03's close_holes(): the two coverage holes, on output 0. ROUTE0
        is enabled to output 0 and the other three routes are disabled. With
        output 0's sink stalled, packets for DST 0 whose lengths add up to
        exactly 8 fill it to level 8, and then two packets follow:

          1. a random packet for DST 0: decided at level 8, so admitted
             (('out0', 'at_8'), B08's bin), which takes the level to 9 to 16;
          2. a random packet for DST 1, a disabled route whose PORT is 0:
             NOROUTE with the level above 8 (('noroute', 'at_9') or
             ('noroute', 'high'), B07's bin). c_dst would keep it off a
             disabled route, so it is switched off for this one packet.

        The two random packets come from new_packet(), and the fill packets
        from RouterPkt.make(), both of which use the constructor rather than
        the factory, so this sends the same packets whatever override a test
        sets. Nothing more goes to output 0 while it holds more than 8 beats,
        and nothing goes to output 1. The test reads DROP_CNT after this, and
        the scoreboard expects 00000001."""
        await self.write_routes("0---")
        self.ocfg[0].ready_pct = 0
        await self.cycles(2)
        plan = FillPlan()
        plan.randomize()
        lens = [int(n) for n in plan.lens if int(n) != 0]
        pkts = [RouterPkt.make(0, n) for n in lens]
        p = self.new_packet()
        with p.randomize_with() as it:
            it.hdr_dst == 0
        pkts.append(p)
        q = self.new_packet()
        q.c_dst.constraint_mode(False)
        with q.randomize_with() as it:
            it.hdr_dst == 1
        pkts.append(q)
        self.logger.info(f"[HOLES] output 0 stalled and filled to 8 by packets of "
                         f"{' '.join(map(str, lens))} beats, then {int(p.length)} beats for DST 0 "
                         f"and {int(q.length)} for DST 1")
        await self.send(pkts)
        self.ocfg[0].ready_pct = 100
        await self.drain()


# ── Lab 03 ───────────────────────────────────────────────────────────────────

@pyuvm.test()
class RouterRandTest(RouterLabTest):
    """Lab 03's router_rand_test."""

    async def body(self):
        n = plusarg("N", 200)
        n_phases = plusarg("PHASES", 4)
        await self.enable()
        for k in range(1, n_phases + 1):
            routes = self.random_routes()
            self.set_sinks(k)
            self.logger.info(f"[PHASE] {k} of {n_phases}: routes {routes}, {n} packets; "
                             f"output 0 {self.sink_desc(0)}, output 1 {self.sink_desc(1)}")
            await self.write_routes(routes)
            await self.send_random(n)
            await self.drain()
            await self.check_drops()
            await self.clear_drops()
        await self.close_holes()
        await self.check_drops()

    @staticmethod
    def random_routes():
        """Lab 03's random routing table, written as +ROUTES is, with at least
        one disabled route and an enabled route to each output."""
        while True:
            r = "".join(random.choice("-01") for _ in range(4))
            if "-" in r and "0" in r and "1" in r:
                return r

    def set_sinks(self, k):
        """How ready each output is in phase k (1 to +PHASES). In Lab 03 both
        always were."""
        self.ocfg[0].ready_pct = 100
        self.ocfg[1].ready_pct = 100


@pyuvm.test()
class RouterFillTest(RouterLabTest):
    """Lab 03's router_fill_test: close_holes() on its own."""

    async def body(self):
        await self.enable()
        await self.close_holes()
        await self.check_drops()


# ── Lab 02 ───────────────────────────────────────────────────────────────────

@pyuvm.test()
class RouterClassTest(RouterLabTest):
    """Lab 02's test: +N random packets on +ROUTES, then a DROP_CNT check.

    As Lab 03 kept it: 100 packets unless +N says otherwise, on the routing
    table +ROUTES gives (0110), a drain, and the DROP_CNT check."""

    async def body(self):
        n = plusarg("N", 100)
        routes = str(cocotb.plusargs.get("ROUTES", "0110"))
        self.logger.info(f"[ENV] {n} packets, routes {routes}")
        await self.write_routes(routes)
        await self.enable()
        await self.send_random(n)
        await self.drain()
        await self.check_drops()


# ── Lab 04 ───────────────────────────────────────────────────────────────────

@pyuvm.test()
class RouterStallTest(RouterRandTest):
    """Lab 04, Part 3: RouterRandTest with one output stalled in each phase.

    Output 0 in phases 1 and 3, and output 1 in phases 2 and 4, is ready in
    5% of cycles, so it fills past 8 beats while the other output, always
    ready, stays nearly empty."""

    def set_sinks(self, k):
        s = 0 if k % 2 == 1 else 1          # the output that stalls in phase k
        self.ocfg[s].ready_pct = 5
        self.ocfg[1 - s].ready_pct = 100


@vsc.randobj
class NoroutePkt(RouterPkt):
    """Lab 04, Part 4: a RouterPkt that goes to a disabled route one time in
    four. Its constraint c_dst has the same name as RouterPkt's, so it
    replaces it. pre_randomize() runs before the solver, so to_disabled is
    already fixed when c_dst is solved."""

    def __init__(self, name="pkt"):
        super().__init__(name)
        self.to_disabled = vsc.uint8_t(0)

    def pre_randomize(self):
        # Only if some route is disabled, or c_dst could not be met.
        self.to_disabled = int(int(self.route_en) != 0xF and random.randrange(4) == 0)

    @vsc.constraint
    def c_dst(self):
        with vsc.if_then(self.to_disabled == 1):
            ((self.route_en >> self.hdr_dst) & 1) == 0
        with vsc.else_then:
            ((self.route_en >> self.hdr_dst) & 1) == 1


@pyuvm.test()
class RouterInjectTest(RouterStallTest):
    """Lab 04, Part 4: RouterStallTest with NoroutePkt in place of RouterPkt.

    Every RouterPkt the factory makes is a NoroutePkt. Nothing else
    changes."""

    def build_phase(self):
        uvm_factory().set_type_override_by_type(RouterPkt, NoroutePkt)
        super().build_phase()


# ── Lab 05 ───────────────────────────────────────────────────────────────────

@pyuvm.test()
class RouterSinkTest(RouterRandTest):
    """Lab 05, Part 3: RouterRandTest with both sinks in SNK_RANDOM, so the sink
    driver answers each beat with an item from SinkSeq. close_holes() stalls
    output 0 with ready_pct 0, which only SNK_PCT reads, so it switches both
    sinks back to SNK_PCT first."""

    def set_sinks(self, k):
        for c in self.ocfg:
            c.mode = SNK_RANDOM

    async def close_holes(self):
        for c in self.ocfg:
            c.mode = SNK_PCT
        await super().close_holes()


@pyuvm.test()
class RouterTest(RouterInjectTest):
    """The graded test. Lab 06: RouterLab06Vseq first, while the router
    still holds its reset values, because a reset sequence compares what it
    reads with them; then everything Lab 05's RouterTest did, unchanged:
    RouterInjectTest's steps and RouterLab05Vseq. The factory override is
    still on, so Lab 05's random packets are NoroutePkts; with every route
    enabled they behave as RouterPkts.

    Every random value comes from Python's random, one after another, so
    anything RouterLab06Vseq draws changes every packet after it.

    Lab 07: RouterLab07Vseq last, so that nothing it draws changes what runs
    before it. Its random packets are NoroutePkts too, and a phase whose
    routing table has a disabled route sends one in four of them there."""

    async def body(self):
        self.logger.info("[VSEQ] starting RouterLab06Vseq")
        await RouterLab06Vseq("lab06", self.env).start()
        self.logger.info("[VSEQ] RouterLab06Vseq is done; starting RouterInjectTest's steps")
        await super().body()
        self.logger.info("[VSEQ] RouterInjectTest's steps are done; starting RouterLab05Vseq")
        await RouterLab05Vseq("vseq", self.env).start()
        self.logger.info("[VSEQ] RouterLab05Vseq is done; starting RouterLab07Vseq")   # Lab 07
        await RouterLab07Vseq("lab07", self.env).start()


@pyuvm.test()
class RouterLab05Test(RouterLabTest):
    """Lab 05, Part 4: RouterLab05Vseq on its own, from a router just out of
    reset."""

    async def body(self):
        await RouterLab05Vseq("vseq", self.env).start()


# ── Lab 06 ───────────────────────────────────────────────────────────────────

@pyuvm.test()
class RouterLab06Test(RouterLabTest):
    """RouterLab06Vseq on its own: the first part of RouterTest, cycle for
    cycle."""

    async def body(self):
        await RouterLab06Vseq("lab06", self.env).start()


# ── Lab 07 ───────────────────────────────────────────────────────────────────

@pyuvm.test()
class RouterLab07Test(RouterLabTest):
    """RouterLab07Vseq on its own: your two sequences, once you run them
    from it, then four random phases."""

    async def body(self):
        await RouterLab07Vseq("lab07", self.env).start()


@pyuvm.test()
class RouterResetTest(RouterLabTest):
    """Part 5: the resets with traffic in flight, on their own."""

    async def body(self):
        await RouterResetVseq("reset", self.env).start()


@pyuvm.test()
class RouterSaturateTest(RouterLabTest):
    """Part 6: the drop counters at 255, on their own."""

    async def body(self):
        await RouterSaturateVseq("saturate", self.env).start()
