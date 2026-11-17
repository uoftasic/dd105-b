"""
DD105-B Lab 07: the scoreboard, the coverage and the environment.

  Fwd                   one input of a component that has several
  PktRecord             what happened to one input packet, for the coverage
  RegChange             what changes STATUS and INT_EN in one cycle (Lab 06)
  RouterScoreboard      Lab 03's scoreboard and tracker in one component, fed
                        by the monitors' analysis ports
  RouterCoverage        Lab 03's coverage, as a subscriber, with an oversize
                        bin (Lab 05)
  RouterWaitCoverage    how long output beats waited (Lab 05)
  RouterCornerCoverage  the four corners the scoreboard counts (Lab 07)
  RouterEnv             makes the agents, the scoreboard, the coverage and
                        the register model, and connects them

This is Lab 06's solution: the irq check in write_sys() and the predictor's
connections in RouterEnv.connect_phase() are filled in. Lab 06's additions
are still marked "Lab 06".

Lab 07 lets the testbench reset the router in the middle of a test, so the
scoreboard follows a reset with traffic in flight: in the first cycle of a
reset it throws away every beat it expected, the packet coming in and the
route writes it was holding, sets its routing table, levels and drop counts
back to their reset values, and puts the register model's mirror back to
its reset values too (reset_model()). It counts four corners for the
coverage (RouterCornerCoverage): a reset with beats still to come out, a
reset with a packet half accepted, and a drop of each kind with its counter
already at 255. The environment makes the sys agent, which has the reset
driver, in place of Lab 06's lone sys monitor, and the ResetState the
drivers share. Lab 07's additions are marked "Lab 07". Nothing in this file
is left for you to write.
"""

from cocotb.triggers import Event
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component, uvm_env, uvm_subscriber

from router_agents import ApbAgent, OutAgent, ResetState, SrcAgent, SysAgent
from router_ral import ApbRegAdapter, RouterRegPredictor, RouterRegs, good_addr

# Register addresses (router-spec.md, Register map).
STATUS, INT_EN, DROP_CNT, ROUTE0 = 0x08, 0x0C, 0x10, 0x20

# Lab 03's fates, in Lab 03's order: the coverage's router.pkt.fate bins are 0 to 3.
NOROUTE, FULL, OUT0, OUT1 = 0, 1, 2, 3

# Lab 07: the corners the scoreboard counts, in the order of router.corner's bins.
RESET_WITH_BEATS = 0        # a reset with beats still to come out of an output (E8)
RESET_MID_PACKET = 1        # a reset with a packet half accepted
NOROUTE_SATURATED = 2       # a NOROUTE drop with NOROUTE_CNT already at 255
FULL_SATURATED = 3          # a FULL drop with FULL_CNT already at 255
CORNERS = ["reset_with_beats", "reset_mid_packet", "noroute_saturated", "full_saturated"]


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
#
# Lab 06 adds the registers that change on their own, STATUS (and with it
# irq) and INT_EN, followed cycle by cycle from the drops, the oversize
# packets and the APB writes; and checks on every transfer's PSLVERR and on
# every read of STATUS and of a bad address. The register model's predictor
# checks the other registers' reads.
#
# Lab 07 adds reset_model(), for a reset after time 0, and the four corners.

class RegChange:
    """Lab 06: what changes STATUS and INT_EN in one cycle."""

    def __init__(self):
        self.set = 0            # STATUS bits that events set
        self.clr = 0            # STATUS bits that a write of 1 clears
        self.int_en = None      # INT_EN's new value, if a write changes it


class RouterScoreboard(uvm_component):
    MAX_ERRORS = 50     # after this many, stop the test: a scoreboard that has
                        # lost step with the router only prints more of the same

    def build_phase(self):
        self.in_imp = Fwd("in_imp", self, self.write_in)
        self.out_imp = Fwd("out_imp", self, self.write_out)
        self.apb_imp = Fwd("apb_imp", self, self.write_apb)
        self.sys_imp = Fwd("sys_imp", self, self.write_sys)     # Lab 06
        self.fate_ap = uvm_analysis_port("fate_ap", self)
        self.corner_ap = uvm_analysis_port("corner_ap", self)   # Lab 07
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
        # Lab 06: STATUS and INT_EN, cycle by cycle. A drop or an oversize
        # packet in cycle c sets a STATUS bit from cycle c+1, and so does a
        # write that completes in cycle c (router-spec.md, STATUS and
        # INT_EN). Each change waits in `changes`, under the cycle it takes
        # effect in, until advance() brings the model to that cycle. A change
        # and a clearing write in the same cycle meet in one entry, and the
        # change wins, as the specification says.
        self.changes = {}               # cycle -> RegChange
        self.model_cycle = 0            # the cycle that status and int_en hold
        self.status = 0
        self.int_en = 0
        self.status_in = {}             # STATUS in the last few cycles, for reads
        self.irq_bad = False            # irq was wrong in the cycle before
        self.n_reads = 0                # register reads, good and bad addresses
        self.n_status = 0               # reads of STATUS checked
        self.n_bad = 0                  # transfers to bad addresses
        self.n_irq_checked = 0          # cycles irq was checked in
        self.n_irq_bad = 0              # ... and was wrong in
        # Lab 07: resets after the one at time 0, and the corners.
        self.regs = None                # the register model; the env sets it
        self.in_reset = True            # the cycle before was a reset cycle; the run starts in reset
        self.n_resets = 0               # resets after the one at time 0
        self.n_lost = 0                 # beats they threw away
        self.n_corner = [0, 0, 0, 0]    # how often each corner happened

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
                if self.noroute_cnt >= 255:
                    self.corner(NOROUTE_SATURATED)      # Lab 07
                self.noroute_cnt += 1
                self.status_event(b.cycle, 0b001)       # Lab 06: STATUS.NOROUTE
            elif self.cur.level > 8:
                self.cur.fate = FULL
                if self.full_cnt >= 255:
                    self.corner(FULL_SATURATED)         # Lab 07
                self.full_cnt += 1
                self.status_event(b.cycle, 0b010)       # Lab 06: STATUS.FULL
            else:
                self.cur.fate = OUT1 if port == 1 else OUT0
                self.in_port = port
        self.in_beats += 1
        # Lab 06: an 8th beat that isn't the last sets STATUS.OVERSIZE,
        # whether or not the packet is forwarded (router-spec.md, Oversize
        # packets).
        if self.in_beats == 8 and not b.last:
            self.status_event(b.cycle, 0b100)
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
        check_drops() did. Lab 05's virtual sequence moves routes while
        packets are coming in, so a route write waits in `pending` for a
        header of a later cycle (see write_in). DROP_CNT is still written
        only while no packet is coming in.

        Lab 06: every transfer's PSLVERR is checked against its address, a
        read of a bad address must return 0, writes to STATUS and INT_EN
        go into `changes`, and every read of STATUS is checked. The register
        model's predictor checks the reads of ID, CTRL, INT_EN and the
        ROUTE registers."""
        bad = not good_addr(t.addr)
        what = f"a {'write' if t.write else 'read'} of {t.addr:02x}, completing in cycle {t.cycle}"
        if not t.write:
            self.n_reads += 1
        if t.slverr != bad:
            self.error(f"{what}: pslverr is {t.slverr}, but {t.addr:02x} is "
                       f"{'a bad' if bad else 'a good'} address")
        if bad:
            # A bad transfer changes nothing, and a bad read returns 0.
            self.n_bad += 1
            if not t.write and t.rdata != 0:
                self.error(f"{what} returned {t.rdata:08x}; a read of a bad address returns 0")
            return
        if t.write:
            if t.addr == STATUS:
                self.change(t.cycle + 1).clr |= t.wdata & 0b111
            elif t.addr == INT_EN:
                self.change(t.cycle + 1).int_en = t.wdata & 0b111
            elif t.addr == DROP_CNT:
                self.noroute_cnt = 0
                self.full_cnt = 0
            elif t.addr in (0x20, 0x24, 0x28, 0x2C):
                r = (t.addr - ROUTE0) >> 2
                self.pending.append((t.cycle, r, t.wdata & 1, (t.wdata >> 1) & 1))
        elif t.addr == STATUS:
            # Lab 06: a read returns the value in its first access cycle, the
            # cycle before it completes (router-spec.md, APB).
            self.advance(t.cycle - 1)
            want = self.status_in[t.cycle - 1]
            self.n_status += 1
            if t.rdata != want:
                self.error(f"{what} returned {t.rdata:08x}; it should return {want:08x}, "
                           f"STATUS in cycle {t.cycle - 1}")
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

    # ── Lab 06: STATUS, INT_EN and irq ──────────────────────────────────────
    def change(self, c):
        """The changes that take effect in cycle c."""
        if c not in self.changes:
            self.changes[c] = RegChange()
        return self.changes[c]

    def status_event(self, c, bits):
        """An event in cycle c sets STATUS bits from cycle c+1."""
        self.change(c + 1).set |= bits

    def advance(self, c):
        """Bring STATUS and INT_EN to cycle c, applying in order every change
        that takes effect in a cycle up to c. write_sys() calls this every
        cycle; a read of STATUS may call it first."""
        while self.model_cycle < c:
            self.model_cycle += 1
            ch = self.changes.pop(self.model_cycle, None)
            if ch is not None:
                self.status = (self.status & ~ch.clr) | ch.set
                if ch.int_en is not None:
                    self.int_en = ch.int_en
            self.status_in[self.model_cycle] = self.status
            self.status_in.pop(self.model_cycle - 8, None)

    def irq(self):
        """irq as the specification defines it (INT_EN): 1 if any STATUS bit
        whose enable is set is 1, with no delay."""
        return int(self.status & self.int_en != 0)

    # ── Lab 07: resets and corners ──────────────────────────────────────────
    def corner(self, k):
        """A corner happened: count it and tell the corner coverage."""
        self.n_corner[k] += 1
        self.corner_ap.write(k)

    def reset_model(self, c):
        """The first cycle of a reset after the one at time 0. Every beat in
        the router is gone, the beats a sink was part way through included
        (router-spec.md, Reset), and so is the configuration. No monitor
        reports a beat or a transfer in a reset cycle, and every one from the
        cycles before has been reported by now, so nothing reported later is
        from before the reset."""
        lost = self.outstanding()
        self.n_resets += 1
        self.n_lost += lost
        if lost > 0:
            self.corner(RESET_WITH_BEATS)
        if self.in_beats > 0:
            self.corner(RESET_MID_PACKET)
        self.logger.info(f"[SB] reset from cycle {c}: {lost} expected beat{' is' if lost == 1 else 's are'} "
                         f"lost, {self.in_beats} beat{'' if self.in_beats == 1 else 's'} of the packet "
                         "coming in")
        for p in (0, 1):
            self.expected[p].clear()
            self.written[p] = 0
            self.taken[p] = 0
            self.last_take[p] = 0
        self.in_beats = 0
        self.in_port = None
        self.cur = None
        self.pending.clear()
        self.route_en = [0, 0, 0, 0]
        self.route_port = [0, 0, 0, 0]
        self.noroute_cnt = 0
        self.full_cnt = 0
        self.regs.map.reset("HARD")

    def write_sys(self, s):
        """rst_n and irq in cycle s.cycle, from the sys monitor. In a reset
        cycle every register is at its reset value. Lab 06 reset the router
        only at time 0, before anything had happened, so this reset only
        STATUS and INT_EN; for a reset after that, Lab 07's reset_model()
        does the rest."""
        if not s.rst_n:
            if not self.in_reset:
                self.reset_model(s.cycle)       # Lab 07
            self.in_reset = True
            self.changes.clear()
            self.status = 0
            self.int_en = 0
            self.model_cycle = s.cycle
            self.status_in[s.cycle] = 0
            self.irq_bad = False
            # irq is 0 while rst_n is 0 (router-spec.md, Reset).
            if s.irq:
                self.error(f"irq is 1 in cycle {s.cycle}, a reset cycle")
            return
        self.in_reset = False                   # Lab 07
        self.advance(s.cycle)
        # irq follows STATUS and INT_EN with no delay, so it's checked against
        # the model's registers in this cycle. A wrong irq is reported in the
        # first cycle it's wrong, not in every cycle after; n_irq_bad counts
        # the cycles.
        self.n_irq_checked += 1
        want = self.irq()
        if s.irq != want:
            if not self.irq_bad:
                self.error(f"irq is {s.irq} from cycle {s.cycle}, but STATUS = {self.status:03b} "
                           f"and INT_EN = {self.int_en:03b} make it {want}")
            self.irq_bad = True
            self.n_irq_bad += 1
        else:
            self.irq_bad = False

    def outstanding(self):
        """Beats still expected on either output. drain() waits for 0."""
        return len(self.expected[0]) + len(self.expected[1])

    def check_phase(self):
        for p in (0, 1):
            if self.expected[p]:
                n = len(self.expected[p])
                self.error(f"output {p}: {n} beat{'' if n == 1 else 's'} {'was' if n == 1 else 'were'} "
                           f"expected and never came out; the first is {self.expected[p][0][0]:02x}")
        # Lab 06: a test that only reads registers checks something too, since
        # the scoreboard and the predictor check every read.
        if self.n_ok[0] + self.n_ok[1] == 0 and self.n_reads == 0:
            self.error("nothing was checked: no output delivered a beat that matched a prediction, "
                       "and no register was read")

    def report_phase(self):
        n = self.n_fate
        self.logger.info(f"[SB] {self.n_pkts} packets in: {n[OUT0]} to output 0, {n[OUT1]} to output 1, "
                         f"{n[NOROUTE]} NOROUTE, {n[FULL]} FULL; the highest level a header saw was "
                         f"{self.max_level}")
        self.logger.info(f"[SB] beats checked: {self.n_ok[0]} on output 0, {self.n_ok[1]} on output 1; "
                         f"{self.n_dropcnt} DROP_CNT reads checked")
        self.logger.info(f"[SB] registers: {self.n_reads} reads, {self.n_status} of STATUS checked; "
                         f"{self.n_bad} transfers to bad addresses; irq checked in "
                         f"{self.n_irq_checked} cycles, wrong in {self.n_irq_bad}")      # Lab 06
        c = self.n_corner
        self.logger.info(f"[SB] resets: {self.n_resets} after the one at time 0, {self.n_lost} expected "
                         f"beats lost; corners hit: "
                         + " ".join(f"{CORNERS[k]}={c[k]}" for k in range(4)))     # Lab 07
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
    coverage.xml (every group) into the run's folder at the end, where
    `make cov` finds it."""

    def write(self, rec):
        sample_pkt(rec)

    def report_phase(self):
        coverage_db.export_to_xml("coverage.xml")
        pkt, wait = coverage_db["router.pkt"], coverage_db["router.wait"]
        corner = coverage_db["router.corner"]                   # Lab 07
        self.logger.info(f"[COV] router.pkt: {pkt.coverage} of {pkt.size} bins hit; router.wait: "
                         f"{wait.coverage} of {wait.size}; router.corner: {corner.coverage} of "
                         f"{corner.size}; coverage.xml written")


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


# Lab 07: the four corners the scoreboard counts, one bin each, in the order
# of CORNERS. A test that never resets with traffic in flight, or never takes
# a counter to 255, leaves its bins empty. DD105-A's cg_corner. With these 4,
# the coverage has 60 bins.

@CoverPoint("router.corner.kind", xf=lambda k: k, bins=[0, 1, 2, 3], bins_labels=CORNERS)
def sample_corner(k):
    pass


class RouterCornerCoverage(uvm_subscriber):
    """Samples router.corner for each corner the scoreboard writes to its
    corner_ap."""

    def write(self, k):
        sample_corner(k)


# ── the environment ──────────────────────────────────────────────────────────
# Lab 03's Env built its pieces in its constructor and handed them queues.
# Here build_phase makes them through the factory, and connect_phase joins
# each monitor's analysis port to the scoreboard. Lab 06 adds the sys
# monitor and the register layer: the model, which isn't a component, its
# adapter, and the predictor. Lab 07 puts the sys monitor in a sys agent
# with the reset driver, and adds the corner coverage.

class RouterEnv(uvm_env):
    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        # Lab 07: the warning the reset driver gives the APB and source
        # drivers, in ConfigDB before they are made.
        self.rst = ResetState()
        ConfigDB().set(self, "*", "RESET", self.rst)
        self.src = SrcAgent.create("src", self)
        self.apb = ApbAgent.create("apb", self)
        self.out = [OutAgent.create("out0", self), OutAgent.create("out1", self)]
        self.sb = RouterScoreboard.create("sb", self)
        self.cov = RouterCoverage.create("cov", self)
        self.wcov = RouterWaitCoverage.create("wcov", self)     # Lab 05
        self.ccov = RouterCornerCoverage.create("ccov", self)   # Lab 07
        # Lab 06: rst_n and irq every cycle, and the register layer. The
        # router is reset at time 0, before anything reaches it, so the
        # model's mirror starts at the reset values. Lab 07: the sys agent
        # has the sys monitor and the reset driver.
        self.sys = SysAgent.create("sys", self)
        self.regs = RouterRegs("regs")
        self.regs.map.reset("HARD")
        self.adapter = ApbRegAdapter("adapter")
        self.predictor = RouterRegPredictor.create("predictor", self)

    def connect_phase(self):
        self.src.mon.ap.connect(self.sb.in_imp.analysis_export)
        self.apb.mon.ap.connect(self.sb.apb_imp.analysis_export)
        self.out[0].mon.ap.connect(self.sb.out_imp.analysis_export)
        self.out[1].mon.ap.connect(self.sb.out_imp.analysis_export)
        self.sb.fate_ap.connect(self.cov.analysis_export)
        for o in self.out:
            o.mon.ap.connect(self.wcov.analysis_export)         # Lab 05
        # Lab 06: the scoreboard's STATUS, INT_EN and irq model, and the map,
        # which sends each register operation through the adapter to the APB
        # agent's sequencer.
        self.sys.mon.ap.connect(self.sb.sys_imp.analysis_export)
        self.regs.map.set_sequencer(self.apb.sqr)
        self.regs.map.set_adapter(self.adapter)
        # Lab 06, Part 3: the predictor keeps the mirror in step with every
        # transfer on the bus, whoever started it, and checks every read
        # against it.
        self.predictor.regs = self.regs
        self.apb.mon.ap.connect(self.predictor.analysis_export)
        # Lab 07: the corners, and the model the scoreboard resets.
        self.sb.corner_ap.connect(self.ccov.analysis_export)
        self.sb.regs = self.regs

    async def run_phase(self):
        # An output with no agent has nothing driving its out_ready. Hold it
        # at 1, as Lab 03's sink did, so the output is always ready.
        for p in range(len(self.out), 2):
            getattr(self.dut, f"out{p}_ready").value = 1
