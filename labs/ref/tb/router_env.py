"""
DD105-B reference environment: everything above the agents.

  SysAgent          the reset driver, its sequencer and ResetSeq
  CycleMonitor      every pin of the router at every falling edge
  RouterScoreboard  runs router_model.RouterModel on the cycle monitor's
                    samples and reports every place the router disagrees
  RouterCoverage    functional coverage, with cocotb-coverage
  RouterEnv         builds and connects the lot, the register model included

The scoreboard compares, in every cycle: in_ready, both out_valid (and
out_data and out_last while valid), irq, pready, pslverr and prdata. That
covers every register read (prdata, rule A8), every drop (a packet that
should have come out and didn't, or the other way round), the cycle each beat
appears (O8), the cut of an oversize packet, and the values after a reset. A
mismatch is logged with self.logger.error(), which BaseTest turns into a
failing test. After MAX_ERRORS of them the scoreboard sets its `stop` event
and the test ends (RouterRefTest.run_phase), because a model that has lost
step with the design only prints more of the same.
"""

from cocotb.triggers import Event, FallingEdge, RisingEdge
from cocotb.utils import get_sim_time
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from pyuvm import (ConfigDB, uvm_agent, uvm_analysis_port, uvm_component, uvm_driver, uvm_env,
                   uvm_monitor, uvm_sequence, uvm_sequence_item, uvm_sequencer)

from apb_agent import ApbAgent
from router_common import Fwd, ResetState
from router_model import RouterModel, Sample, bad_addr
from router_ral import ApbRegAdapter, RouterRegPredictor, RouterRegs
from stream_agents import SinkAgent, SinkCfg, SrcAgent


# ── reset ────────────────────────────────────────────────────────────────────

class ResetItem(uvm_sequence_item):
    """rst_n low for `cycles` cycles."""

    def __init__(self, name="reset", cycles=3):
        super().__init__(name)
        self.cycles = cycles


class ResetDriver(uvm_driver):
    """Drives rst_n. For each item: right after rising edge x it sets
    ResetState.soon (and soon_time), right after edge x+1 it pulls rst_n low,
    and right after
    the edge that ends the item's last reset cycle it lets rst_n go and
    clears `soon`. So rst_n changes just after a rising edge both ways, as
    router-spec.md's Reset section asks, and every cycle is wholly in reset
    or wholly out of it. RouterBaseTest holds rst_n at 0 from time 0, and the
    first reset item releases it."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.rst = ConfigDB().get(self, "", "RESET")

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
    """The reset driver and its sequencer. It has no monitor: rst_n and irq
    are in the cycle monitor's samples."""

    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = ResetDriver.create("drv", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


class ResetSeq(uvm_sequence):
    def __init__(self, name="reset_seq", cycles=3):
        super().__init__(name)
        self.cycles = cycles

    async def body(self):
        it = ResetItem("reset", self.cycles)
        await self.start_item(it)
        await self.finish_item(it)


# ── the cycle monitor ────────────────────────────────────────────────────────

class CycleMonitor(uvm_monitor):
    """Reads every pin of the router at every falling edge and writes one
    Sample per cycle. The scoreboard's model runs on these, cycle by cycle,
    and the predictor learns from them when a reset starts."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")
        self.cycle = 0

    async def run_phase(self):
        d = self.dut
        handles = [(p, getattr(d, p)) for p in Sample.PINS]
        while True:
            await FallingEdge(d.clk)
            self.cycle += 1
            s = Sample(self.cycle)
            for p, h in handles:
                setattr(s, p, int(h.value))
            self.ap.write(s)


# ── the scoreboard ───────────────────────────────────────────────────────────

CHECKED = ("in_ready", "out0_valid", "out1_valid", "irq", "pready", "pslverr", "prdata")


class RouterScoreboard(uvm_component):
    MAX_ERRORS = 50

    def build_phase(self):
        self.model = RouterModel()
        self.pkt_ap = uvm_analysis_port("pkt_ap", self)
        self.model.on_packet = self.pkt_ap.write
        self.sample_imp = Fwd("sample_imp", self, self.write_sample)
        self.stop = Event()
        self.n_err = 0
        self.cycles = self.resets = self.reads = self.writes = self.bad = 0
        self.irq_high = self.in_beats = 0
        self.out_beats = [0, 0]
        self._in_reset = False

    def idle(self):
        """No beat waiting in either buffer, as the model sees it."""
        return self.model.level(0) == 0 and self.model.level(1) == 0

    def error(self, s, msg):
        self.n_err += 1
        if self.n_err > self.MAX_ERRORS:
            return
        self.logger.error(f"cycle {s.cycle}: {msg}")
        if self.n_err == self.MAX_ERRORS:
            self.logger.warning(f"{self.n_err} mismatches with the model: stopping the test, since the "
                                "model has lost step with the design")
            self.stop.set()

    def write_sample(self, s):
        if not s.rst_n and not self._in_reset:
            self.resets += 1
        self._in_reset = not s.rst_n
        p = self.model.step(s)
        if p is None:
            return                              # before the first reset nothing is defined
        self.cycles += 1
        for k in CHECKED:
            got, want = getattr(s, k), p[k]
            if got != want:
                what = "prdata (the last read's value)" if k == "prdata" else k
                self.error(s, f"{what} is {got:x}, the model expects {want:x}")
        for k in (0, 1):
            if p[f"out{k}_valid"] and getattr(s, f"out{k}_valid"):
                d, l = getattr(s, f"out{k}_data"), getattr(s, f"out{k}_last")
                if (d, l) != (p[f"out{k}_data"], p[f"out{k}_last"]):
                    self.error(s, f"output {k} has data {d:02x} last {l}, the model expects "
                                  f"{p[f'out{k}_data']:02x} last {p[f'out{k}_last']}")
                if getattr(s, f"out{k}_ready"):
                    self.out_beats[k] += 1
        if s.rst_n:
            self.irq_high += p["irq"]
            if s.in_valid and p["in_ready"]:
                self.in_beats += 1
            if s.psel and s.penable and p["pready"]:
                if bad_addr(s.paddr):
                    self.bad += 1
                elif s.pwrite:
                    self.writes += 1
                else:
                    self.reads += 1

    def report_phase(self):
        fates = {}
        for pkt in self.model.packets:
            key = pkt.fate + (" oversize" if pkt.oversize else "")
            fates[key] = fates.get(key, 0) + 1
        fates = ", ".join(f"{n} {k}" for k, n in sorted(fates.items()))
        self.logger.info(f"[SB] {self.cycles} cycles, {self.resets} resets; {self.in_beats} input beats "
                         f"in {len(self.model.packets)} packets: {fates}; output beats "
                         f"{self.out_beats[0]} and {self.out_beats[1]}")
        self.logger.info(f"[SB] {self.reads} register reads and {self.writes} writes checked, "
                         f"{self.bad} transfers to bad addresses; irq 1 in {self.irq_high} cycles; "
                         f"{self.n_err} mismatches")


# ── coverage ─────────────────────────────────────────────────────────────────

def _ranges(rs):
    return dict(bins=list(rs), rel=lambda v, b: b[0] <= v <= b[1])


LEVELS = [(0, 0), (1, 7), (8, 8), (9, 9), (10, 16)]
LEVEL_LABELS = ["empty", "low", "at_8", "at_9", "high"]
REG_BINS = [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13]
REG_LABELS = ["id", "ctrl", "status", "int_en", "drop_cnt", "level",
              "route0", "route1", "route2", "route3", "bad_aligned", "bad_unaligned"]
WAITS = [(0, 0), (1, 3), (4, 20), (21, 10 ** 9)]


def apb_reg(addr):
    """DD105-A's cg_apb.cp_reg value: the register's word number (ROUTE0 to
    ROUTE3 are 8 to 11), 12 for a bad address that is a multiple of 4, 13 for
    one that isn't."""
    if bad_addr(addr):
        return 12 if addr & 3 == 0 else 13
    return addr >> 2


class RouterCoverage(uvm_component):
    """DD105-A's covergroups, in cocotb-coverage, apart from its cg_corner:

      router.pkt   every packet when its last beat is accepted (from the
                   scoreboard's model): its length, DST, what happened to it,
                   and the level of its output when its header was decided;
                   A's crosses DST x fate and length x fate, and one A doesn't
                   have, fate x level, with the seven combinations the router
                   can't produce as ign_bins (a FULL drop at a level of 8 or
                   less, a forwarded packet at 9 or more)
      router.apb   every APB transfer (from the APB monitor): which register,
                   or which kind of bad address, which direction, PSLVERR
      router.wait  every output packet (from the sink monitors): the longest
                   any of its beats waited for out_ready

    cocotb-coverage has no ignore bins on a coverpoint, only on a cross, so a
    value nobody wants counted is left out of a coverpoint's bins. Writes
    coverage.xml into the run folder in report_phase; `make cov` merges them."""

    def build_phase(self):
        self.pkt_in = Fwd("pkt_in", self, self.write_pkt)
        self.apb_in = Fwd("apb_in", self, self.write_apb)
        self.wait_in = [Fwd("wait0_in", self, lambda p: self.sample_wait(0, p.max_wait)),
                        Fwd("wait1_in", self, lambda p: self.sample_wait(1, p.max_wait))]

        def lvl(p):
            return next(i for i, (a, b) in enumerate(LEVELS) if a <= p.level <= b)

        impossible = [("full", b) for b in ("empty", "low", "at_8")] + \
                     [(f, b) for f in ("out0", "out1") for b in ("at_9", "high")]

        @CoverPoint("router.pkt.len", xf=lambda p: min(p.beats, 9), bins=list(range(1, 10)),
                    bins_labels=[f"len{n}" for n in range(1, 9)] + ["oversize"])
        @CoverPoint("router.pkt.dst", xf=lambda p: p.dst, bins=[0, 1, 2, 3],
                    bins_labels=["dst0", "dst1", "dst2", "dst3"])
        @CoverPoint("router.pkt.act", xf=lambda p: p.fate, bins=["noroute", "full", "out0", "out1"])
        @CoverPoint("router.pkt.level", xf=lvl, bins=list(range(len(LEVELS))), bins_labels=LEVEL_LABELS)
        @CoverCross("router.pkt.x_dst_act", items=["router.pkt.dst", "router.pkt.act"])
        @CoverCross("router.pkt.x_len_act", items=["router.pkt.len", "router.pkt.act"])
        @CoverCross("router.pkt.x_act_level", items=["router.pkt.act", "router.pkt.level"],
                    ign_bins=impossible)
        def sample_pkt(p):
            pass

        @CoverPoint("router.apb.reg", xf=lambda r, w, e: r, bins=REG_BINS, bins_labels=REG_LABELS)
        @CoverPoint("router.apb.dir", xf=lambda r, w, e: w, bins=[0, 1], bins_labels=["read", "write"])
        @CoverPoint("router.apb.slverr", xf=lambda r, w, e: e, bins=[0, 1], bins_labels=["ok", "err"])
        @CoverCross("router.apb.x_reg_dir", items=["router.apb.reg", "router.apb.dir"])
        def sample_apb(r, w, e):
            pass

        @CoverPoint("router.wait.port", xf=lambda k, w: k, bins=[0, 1], bins_labels=["out0", "out1"])
        @CoverPoint("router.wait.wait", xf=lambda k, w: w, bins_labels=["none", "short_wait", "long_wait",
                                                                        "stalled"], **_ranges(WAITS))
        @CoverCross("router.wait.x_port_wait", items=["router.wait.port", "router.wait.wait"])
        def sample_wait(k, w):
            pass

        self.sample_pkt, self.sample_apb, self.sample_wait = sample_pkt, sample_apb, sample_wait

    def write_pkt(self, pkt):
        self.sample_pkt(pkt)

    def write_apb(self, t):
        self.sample_apb(apb_reg(t.addr), int(t.write), t.slverr)

    def report_phase(self):
        coverage_db.export_to_xml("coverage.xml")
        parts = ", ".join(f"{g} {coverage_db[f'router.{g}'].coverage} of {coverage_db[f'router.{g}'].size}"
                          for g in ("pkt", "apb", "wait"))
        top = coverage_db["router"]
        self.logger.info(f"[COV] {top.coverage} of {top.size} bins ({parts}); coverage.xml written")


# ── the environment ──────────────────────────────────────────────────────────

class RouterEnv(uvm_env):
    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.rst = ResetState()
        ConfigDB().set(None, "*", "RESET", self.rst)
        self.sink_cfg = [SinkCfg(), SinkCfg()]
        for k in (0, 1):
            ConfigDB().set(self, f"sink{k}*", "SINK_CFG", self.sink_cfg[k])
        self.apb = ApbAgent.create("apb", self)
        self.src = SrcAgent.create("src", self)
        self.sink = []
        for k in (0, 1):
            a = SinkAgent.create(f"sink{k}", self)
            a.port = k
            self.sink.append(a)
        self.sys = SysAgent.create("sys", self)
        self.mon = CycleMonitor.create("mon", self)
        self.sb = RouterScoreboard.create("sb", self)
        self.cov = RouterCoverage.create("cov", self)
        self.predictor = RouterRegPredictor.create("predictor", self)
        self.regs = RouterRegs()
        self.adapter = ApbRegAdapter()

    def connect_phase(self):
        self.mon.ap.connect(self.sb.sample_imp.analysis_export)
        self.mon.ap.connect(self.predictor.reset_in.analysis_export)
        self.apb.mon.ap.connect(self.predictor.bus_in.analysis_export)
        self.apb.mon.ap.connect(self.cov.apb_in.analysis_export)
        self.sb.pkt_ap.connect(self.cov.pkt_in.analysis_export)
        for k in (0, 1):
            self.sink[k].mon.pkt_ap.connect(self.cov.wait_in[k].analysis_export)
        self.regs.map.set_sequencer(self.apb.sqr)
        self.regs.map.set_adapter(self.adapter)
        self.predictor.regs = self.regs

    def report_phase(self):
        self.logger.info(f"[ENV] {self.rst.epoch} resets driven; {self.apb.drv.restarts} APB transfers "
                         f"started again after a reset; {self.src.drv.abandoned} packets abandoned "
                         "at a reset or a wait limit")
