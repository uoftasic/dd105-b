"""
DD105-B Lab 05: the scoreboard, the coverage and the environment.

  Fwd                 one input of a component that has several
  PktRecord           what happened to one input packet, for the coverage
  RouterScoreboard    Lab 03's scoreboard and tracker in one component, fed by
                      the monitors' analysis ports
  RouterCoverage      Lab 03's coverage, as a subscriber, with an oversize
                      bin (Lab 05)
  RouterWaitCoverage  how long output beats waited (Lab 05)
  RouterEnv           makes the agents, the scoreboard and the coverage, and
                      connects them

This is our Lab 04 solution with Lab 05's additions, each marked "Lab 05":
the scoreboard follows route writes made while packets are coming in, the
packet coverage has an oversize bin, and RouterWaitCoverage is new. Nothing
in this file is left for you to write.
"""

from cocotb.triggers import Event
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component, uvm_env, uvm_subscriber

from router_agents import ApbAgent, OutAgent, SrcAgent

# Register addresses (router-spec.md, Register map).
DROP_CNT, ROUTE0 = 0x10, 0x20

# Lab 03's fates, in Lab 03's order: the coverage's router.pkt.fate bins are 0 to 3.
NOROUTE, FULL, OUT0, OUT1 = 0, 1, 2, 3


class Fwd(uvm_subscriber):
    """pyuvm has no uvm_analysis_imp_decl, so a component with several inputs
    gets one of these for each input, and each one passes what is written to
    it on to a method of the component."""

    def __init__(self, name, parent, fn):
        super().__init__(name, parent)
        self.fn = fn

    def write(self, t):
        self.fn(t)


class PktRecord:
    """Lab 03's PktRecord: what the coverage samples for one packet."""

    def __init__(self, dst, level):
        self.dst = dst          # the header's DST
        self.length = 0         # beats taken from the input, header included
        self.fate = None        # NOROUTE, FULL, OUT0 or OUT1
        self.level = level      # the level of output ROUTE[DST].PORT in the header's cycle


# ── the scoreboard ───────────────────────────────────────────────────────────
# Lab 03's scoreboard and its tracker, in one component. Both took their
# inputs in run() loops of their own, from queues and from the pins; here
# each monitor calls one of the write_*() methods below as each beat moves,
# and the scoreboard has no coroutine at all.
#
# For every packet that comes in, it decides at the header what the router
# must do with it (router-spec.md, Routing), as Lab 03's tracker did, from the
# routing table it has seen written over APB and the level of each output,
# and queues the beats it expects on that output. Lab 03's scoreboard
# expected every packet for an enabled route to come out; this one also
# predicts FULL drops, from the levels. Every beat that comes out must be the
# next one queued for its output, and every read of DROP_CNT must match the
# drops counted since DROP_CNT was last written.

class RouterScoreboard(uvm_component):
    MAX_ERRORS = 50     # after this many, stop the test: a scoreboard that has
                        # lost step with the router only prints more of the same

    def build_phase(self):
        self.in_imp = Fwd("in_imp", self, self.write_in)
        self.out_imp = Fwd("out_imp", self, self.write_out)
        self.apb_imp = Fwd("apb_imp", self, self.write_apb)
        self.fate_ap = uvm_analysis_port("fate_ap", self)
        self.stop = Event()             # set at the MAX_ERRORS-th error; the test then ends
        self.n_err = 0
        # The routing table, as written over APB (reset: every route disabled).
        self.route_en = [0, 0, 0, 0]
        self.route_port = [0, 0, 0, 0]
        # Lab 05: route writes not yet applied, as (cycle, route, en, port), in
        # the order they completed. A header accepted in the cycle a write
        # completes still uses the old entry (router-spec.md, Routing), so
        # write_in applies a write only at a header of a later cycle. The APB
        # and input monitors report at the same falling edge in no fixed
        # order, so the cycle decides, not the order of the calls.
        self.pending = []
        # The packet coming in.
        self.in_beats = 0               # beats of it taken so far; 0: the next beat is a header
        self.in_port = None             # the output it's written to, or None if it's dropped
        self.cur = None                 # its PktRecord
        # Each output.
        self.expected = [[], []]        # (data, last) of every beat still to come out, in order
        self.written = [0, 0]           # beats written into it so far
        self.taken = [0, 0]             # beats taken from it so far
        self.last_take = [0, 0]         # the cycle of the most recent of those
        # DROP_CNT, as the router should have it.
        self.noroute_cnt = 0
        self.full_cnt = 0
        # For the report.
        self.n_pkts = 0
        self.n_fate = [0, 0, 0, 0]
        self.n_ok = [0, 0]
        self.n_dropcnt = 0
        self.max_level = 0              # the highest level a header saw
        self.n_unwatched = 0            # beats written to an output that nothing watches

    def error(self, msg):
        self.n_err += 1
        if self.n_err > self.MAX_ERRORS:
            return
        self.logger.error(msg)
        if self.n_err == self.MAX_ERRORS:
            self.logger.warning(f"{self.n_err} errors: stopping the test")
            self.stop.set()

    def level(self, p, t):
        """The level of output p in cycle t: the beats written into it in
        cycles before t, minus the beats taken from it in cycles before t
        (router-spec.md, Routing). The monitors all read the pins at the same
        falling edge, in no fixed order, so a beat taken from output p in
        cycle t itself may already have been reported when the header of
        cycle t arrives. It doesn't count, so it's added back. That is Lab
        03's tracker's rule: a cycle's input handshake before its output
        handshake."""
        n = self.written[p] - self.taken[p]
        if self.taken[p] > 0 and self.last_take[p] == t:
            n += 1
        return n

    def write_in(self, b):
        """A beat taken from the input."""
        if self.in_beats == 0:
            # The header: the router decides here what happens to the whole packet.
            # Lab 05: first, the route writes that completed before this cycle.
            while self.pending and self.pending[0][0] < b.cycle:
                _, r, en, port = self.pending.pop(0)
                self.route_en[r] = en
                self.route_port[r] = port
            dst = b.data >> 6
            port = self.route_port[dst]
            self.cur = PktRecord(dst, self.level(port, b.cycle))
            self.max_level = max(self.max_level, self.cur.level)
            self.n_pkts += 1
            self.in_port = None
            if not self.route_en[dst]:
                self.cur.fate = NOROUTE
                self.noroute_cnt += 1
            elif self.cur.level > 8:
                self.cur.fate = FULL
                self.full_cnt += 1
            else:
                self.cur.fate = OUT1 if port == 1 else OUT0
                self.in_port = port
        self.in_beats += 1
        # A forwarded packet's first 8 beats are written to its output, and
        # the 8th always ends it (router-spec.md, Oversize packets).
        if self.in_port is not None and self.in_beats <= 8:
            self.written[self.in_port] += 1
            last = bool(b.last) or self.in_beats == 8
            self.expected[self.in_port].append((b.data, last))
        if b.last:
            self.cur.length = self.in_beats
            self.n_fate[self.cur.fate] += 1
            self.fate_ap.write(self.cur)
            self.in_beats = 0

    def write_out(self, b):
        """A beat taken from output b.port."""
        p = b.port
        self.taken[p] += 1
        self.last_take[p] = b.cycle
        if not self.expected[p]:
            self.error(f"output {p}: got {b}, and no beat was expected")
            return
        data, last = self.expected[p].pop(0)
        if (b.data, bool(b.last)) != (data, last):
            self.error(f"output {p}: got {b}, expected {data:02x}{' last' if last else ''}")
        else:
            self.n_ok[p] += 1

    def write_apb(self, t):
        """A completed APB transfer. Writes to ROUTE0 to ROUTE3 and DROP_CNT
        update the model, and every read of DROP_CNT is checked, as Lab 03's
        check_drops() did. Lab 04's tests wrote the routing table only while
        no packet was coming in; Lab 05's virtual sequence moves routes while
        packets are coming in, so a route write waits in `pending` for a
        header of a later cycle (see write_in). DROP_CNT is still written
        only while no packet is coming in."""
        if t.slverr:
            return
        if t.write:
            if t.addr == DROP_CNT:
                self.noroute_cnt = 0
                self.full_cnt = 0
            elif t.addr in (0x20, 0x24, 0x28, 0x2C):
                r = (t.addr - ROUTE0) >> 2
                self.pending.append((t.cycle, r, t.wdata & 1, (t.wdata >> 1) & 1))
        elif t.addr == DROP_CNT:
            # FULL_CNT in bits 15:8 and NOROUTE_CNT in bits 7:0, each stopping at 255.
            full, noroute = min(self.full_cnt, 255), min(self.noroute_cnt, 255)
            want = (full << 8) | noroute
            self.n_dropcnt += 1
            if t.rdata != want:
                self.error(f"DROP_CNT read {t.rdata:08x}, expected {want:08x} "
                           f"(FULL_CNT {full}, NOROUTE_CNT {noroute})")
            else:
                self.logger.info(f"[DROP] DROP_CNT {t.rdata:08x} as expected")

    def outstanding(self):
        """Beats still expected on either output. drain() waits for 0."""
        return len(self.expected[0]) + len(self.expected[1])

    def check_phase(self):
        for p in (0, 1):
            if self.expected[p]:
                n = len(self.expected[p])
                self.error(f"output {p}: {n} beat{'' if n == 1 else 's'} {'was' if n == 1 else 'were'} "
                           f"expected and never came out; the first is {self.expected[p][0][0]:02x}")
        if self.n_ok[0] + self.n_ok[1] == 0:
            self.error("no beat was checked: neither output delivered a beat that matched a prediction")

    def report_phase(self):
        n = self.n_fate
        self.logger.info(f"[SB] {self.n_pkts} packets in: {n[OUT0]} to output 0, {n[OUT1]} to output 1, "
                         f"{n[NOROUTE]} NOROUTE, {n[FULL]} FULL; the highest level a header saw was "
                         f"{self.max_level}")
        self.logger.info(f"[SB] beats checked: {self.n_ok[0]} on output 0, {self.n_ok[1]} on output 1; "
                         f"{self.n_dropcnt} DROP_CNT reads checked")
        if self.n_unwatched:
            self.logger.info(f"[SB] {self.n_unwatched} beats went to output 1, which nothing watches")


# ── the coverage ─────────────────────────────────────────────────────────────
# Lab 03's coverage, with the same names and bins, and in Lab 05 one more bin
# in router.pkt.len, `oversize`, for packets of 9 beats or more on the input,
# before the router cuts them: 42 in all. The level's bins are ranges, so the
# coverpoint needs rel= (Lab 03, Part 2), and so do the length's now.

LEVEL_BINS = [(0, 0), (1, 7), (8, 8), (9, 9), (10, 16)]
LEN_BINS = [(n, n) for n in range(1, 9)] + [(9, 1 << 30)]


def in_range(value, rng):
    return rng[0] <= value <= rng[1]


@CoverPoint("router.pkt.len", xf=lambda rec: rec.length, bins=LEN_BINS, rel=in_range,
            bins_labels=[f"len{n}" for n in range(1, 9)] + ["oversize"])
@CoverPoint("router.pkt.dst", xf=lambda rec: rec.dst, bins=[0, 1, 2, 3],
            bins_labels=["dst0", "dst1", "dst2", "dst3"])
@CoverPoint("router.pkt.fate", xf=lambda rec: rec.fate, bins=[0, 1, 2, 3],
            bins_labels=["noroute", "full", "out0", "out1"])
@CoverPoint("router.pkt.level", xf=lambda rec: rec.level, bins=LEVEL_BINS, rel=in_range,
            bins_labels=["empty", "low", "at_8", "at_9", "high"])
@CoverCross("router.pkt.x_fate_level", items=["router.pkt.fate", "router.pkt.level"])
def sample_pkt(rec):
    pass


class RouterCoverage(uvm_subscriber):
    """Samples each PktRecord the scoreboard writes to its fate_ap, and writes
    coverage.xml (both groups) into the run's folder at the end, where
    `make cov` finds it."""

    def write(self, rec):
        sample_pkt(rec)

    def report_phase(self):
        coverage_db.export_to_xml("coverage.xml")
        pkt, wait = coverage_db["router.pkt"], coverage_db["router.wait"]
        self.logger.info(f"[COV] router.pkt: {pkt.coverage} of {pkt.size} bins hit; router.wait: "
                         f"{wait.coverage} of {wait.size}; coverage.xml written")


# Lab 05: backpressure. For each packet an output delivers, the longest any of
# its beats waited for out_ready: `none` is 0 cycles, `short_wait` 1 to 3,
# `long_wait` 4 to 20 and `stalled` more than 20; and the cross with the
# output. 14 bins. DD105-A's cg_wait.

WAIT_BINS = [(0, 0), (1, 3), (4, 20), (21, 1 << 30)]


@CoverPoint("router.wait.port", xf=lambda port, w: port, bins=[0, 1], bins_labels=["out0", "out1"])
@CoverPoint("router.wait.wait", xf=lambda port, w: w, bins=WAIT_BINS, rel=in_range,
            bins_labels=["none", "short_wait", "long_wait", "stalled"])
@CoverCross("router.wait.x_port_wait", items=["router.wait.port", "router.wait.wait"])
def sample_wait(port, w):
    pass


class RouterWaitCoverage(uvm_subscriber):
    """Subscribes to both output monitors, which stamp each beat with how
    long it waited, and samples router.wait at each packet's last beat with
    the longest wait of its beats."""

    def build_phase(self):
        self.max_wait = [0, 0]      # the longest wait so far in the packet coming out of each output

    def write(self, b):
        self.max_wait[b.port] = max(self.max_wait[b.port], b.waited)
        if b.last:
            sample_wait(b.port, self.max_wait[b.port])
            self.max_wait[b.port] = 0


# ── the environment ──────────────────────────────────────────────────────────
# Lab 03's Env built its pieces in its constructor and handed them queues.
# Here build_phase makes them through the factory, and connect_phase joins
# each monitor's analysis port to the scoreboard.

class RouterEnv(uvm_env):
    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.src = SrcAgent.create("src", self)
        self.apb = ApbAgent.create("apb", self)
        self.out = [OutAgent.create("out0", self), OutAgent.create("out1", self)]
        self.sb = RouterScoreboard.create("sb", self)
        self.cov = RouterCoverage.create("cov", self)
        self.wcov = RouterWaitCoverage.create("wcov", self)     # Lab 05

    def connect_phase(self):
        self.src.mon.ap.connect(self.sb.in_imp.analysis_export)
        self.apb.mon.ap.connect(self.sb.apb_imp.analysis_export)
        self.out[0].mon.ap.connect(self.sb.out_imp.analysis_export)
        self.out[1].mon.ap.connect(self.sb.out_imp.analysis_export)
        self.sb.fate_ap.connect(self.cov.analysis_export)
        for o in self.out:
            o.mon.ap.connect(self.wcov.analysis_export)         # Lab 05

    async def run_phase(self):
        # An output with no agent has nothing driving its out_ready. Hold it
        # at 1, as Lab 03's sink did, so the output is always ready.
        for p in range(len(self.out), 2):
            getattr(self.dut, f"out{p}_ready").value = 1
