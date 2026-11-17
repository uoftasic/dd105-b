"""
DD105-B Lab 04: the scoreboard, the coverage and the environment.

  Fwd               one input of a component that has several
  PktRecord         what happened to one input packet, for the coverage
  RouterScoreboard  Lab 03's scoreboard and tracker in one component, fed by
                    the monitors' analysis ports
  RouterCoverage    Lab 03's coverage, as a subscriber
  RouterEnv         makes the agents, the scoreboard and the coverage, and
                    connects them

Lab 03's testbench watched only output 0, and so does this port of it.
Parts 2 and 3 of the lab fill in the TODOs below.
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
        # TODO (Part 3): Lab 03's tracker took output 1's level as 0, because
        # no test stalled output 1, so it never held more than a beat or two,
        # and this does the same. Make it give output 1's real level, as it
        # does output 0's.
        if p == 1:
            return 0
        n = self.written[p] - self.taken[p]
        if self.taken[p] > 0 and self.last_take[p] == t:
            n += 1
        return n

    def write_in(self, b):
        """A beat taken from the input."""
        if self.in_beats == 0:
            # The header: the router decides here what happens to the whole packet.
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
            # TODO (Part 2): Lab 03 watched only output 0, so this queues only
            # output 0's beats. Queue output 1's as well, once RouterEnv
            # connects output 1's monitor.
            if self.in_port == 0:
                self.expected[0].append((b.data, last))
            else:
                self.n_unwatched += 1
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
        check_drops() did. The tests write the routing table only while no
        packet is coming in, so a write never lands in the cycle of a
        header."""
        if t.slverr:
            return
        if t.write:
            if t.addr == DROP_CNT:
                self.noroute_cnt = 0
                self.full_cnt = 0
            elif t.addr in (0x20, 0x24, 0x28, 0x2C):
                r = (t.addr - ROUTE0) >> 2
                self.route_en[r] = t.wdata & 1
                self.route_port[r] = (t.wdata >> 1) & 1
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
# Lab 03's coverage, with the same names and bins: 41 in all. The level's bins
# are ranges, so the coverpoint needs rel= (Lab 03, Part 2).

LEVEL_BINS = [(0, 0), (1, 7), (8, 8), (9, 9), (10, 16)]


def in_range(value, rng):
    return rng[0] <= value <= rng[1]


@CoverPoint("router.pkt.len", xf=lambda rec: rec.length, bins=list(range(1, 9)),
            bins_labels=[f"len{n}" for n in range(1, 9)])
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
    coverage.xml into the run's folder at the end, where `make cov` finds
    it."""

    def write(self, rec):
        sample_pkt(rec)

    def report_phase(self):
        coverage_db.export_to_xml("coverage.xml")
        pkt = coverage_db["router.pkt"]
        self.logger.info(f"[COV] router.pkt: {pkt.coverage} of {pkt.size} bins hit; coverage.xml written")


# ── the environment ──────────────────────────────────────────────────────────
# Lab 03's Env built its pieces in its constructor and handed them queues.
# Here build_phase makes them through the factory, and connect_phase joins
# each monitor's analysis port to the scoreboard.

class RouterEnv(uvm_env):
    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.src = SrcAgent.create("src", self)
        self.apb = ApbAgent.create("apb", self)
        self.out = [OutAgent.create("out0", self)]
        # TODO (Part 2): make the agent for output 1, named "out1", and add it
        # to self.out. The test has already put an OutCfg for it in ConfigDB.
        self.sb = RouterScoreboard.create("sb", self)
        self.cov = RouterCoverage.create("cov", self)

    def connect_phase(self):
        self.src.mon.ap.connect(self.sb.in_imp.analysis_export)
        self.apb.mon.ap.connect(self.sb.apb_imp.analysis_export)
        self.out[0].mon.ap.connect(self.sb.out_imp.analysis_export)
        # TODO (Part 2): connect output 1's monitor to the scoreboard.
        self.sb.fate_ap.connect(self.cov.analysis_export)

    async def run_phase(self):
        # An output with no agent has nothing driving its out_ready. Hold it
        # at 1, as Lab 03's sink did, so the output is always ready.
        for p in range(len(self.out), 2):
            getattr(self.dut, f"out{p}_ready").value = 1
