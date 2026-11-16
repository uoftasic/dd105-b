"""
DD105-B reference environment: the scoreboard, the coverage and the
environment that holds the agents.

The scoreboard runs router_model.RouterModel on the cycle monitor's samples
and compares, in every cycle: in_ready, both out_valid (and out_data and
out_last while valid), irq, pready, pslverr and prdata. That covers every
register read (prdata, rule A8), every drop (a packet that should have come
out and didn't, or the other way round), the cycle each beat appears (O8),
the cut of an oversize packet, and the values after a reset. A mismatch is
logged with self.logger.error(), which BaseTest turns into a failing test;
after MAX_ERRORS of them the scoreboard stops the test, because a model that
has lost step with the design only prints more of the same.
"""

from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_component, uvm_env, uvm_subscriber

from router_agents import ApbAgent, CycleMonitor, SinkCfg, SinkDriver, SrcAgent
from router_model import RouterModel, bad_addr
from router_ral import ApbRegAdapter, RouterRegs

try:                                    # in the course venv (`make venv`)
    from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
except ImportError:                     # without it, the environment runs with no coverage
    CoverPoint = None


class _Fwd(uvm_subscriber):
    """pyuvm has no uvm_analysis_imp_decl, so a component with several inputs
    gets one of these per input, forwarding to a method."""

    def __init__(self, name, parent, fn):
        super().__init__(name, parent)
        self.fn = fn

    def write(self, t):
        self.fn(t)


CHECKED = ("in_ready", "out0_valid", "out1_valid", "irq", "pready", "pslverr", "prdata")


class RouterScoreboard(uvm_component):
    MAX_ERRORS = 50

    def build_phase(self):
        self.model = RouterModel()
        self.pkt_ap = uvm_analysis_port("pkt_ap", self)
        self.model.on_packet = self.pkt_ap.write
        self.sample_imp = _Fwd("sample_imp", self, self.write_sample)
        self.n_err = 0
        self.cycles = self.resets = self.reads = self.writes = self.bad = 0
        self.irq_high = self.in_beats = 0
        self.out_beats = [0, 0]
        self.fates = {}
        self._in_reset = False

    def error(self, s, msg):
        self.n_err += 1
        self.logger.error(f"cycle {s.cycle}: {msg}")
        assert self.n_err < self.MAX_ERRORS, (
            f"{self.n_err} mismatches with the model; stopping, since the model has lost step "
            "with the design")

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
                what = k
                if k == "prdata":
                    what = "prdata (the last read's value)"
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
        for pkt in self.model.packets:
            key = pkt.fate + (" oversize" if pkt.oversize else "")
            self.fates[key] = self.fates.get(key, 0) + 1
        fates = ", ".join(f"{n} {k}" for k, n in sorted(self.fates.items()))
        self.logger.info(f"[SB] {self.cycles} cycles, {self.resets} resets; {self.in_beats} input beats "
                         f"in {len(self.model.packets)} packets: {fates}; output beats "
                         f"{self.out_beats[0]} and {self.out_beats[1]}")
        self.logger.info(f"[SB] {self.reads} register reads and {self.writes} writes checked, "
                         f"{self.bad} transfers to bad addresses; irq 1 in {self.irq_high} cycles; "
                         f"{self.n_err} mismatches")


class RouterCoverage(uvm_subscriber):
    """Each packet's length, DST, fate and the level of its output when its
    header was decided, with cocotb-coverage when the course venv has it.
    Writes coverage.xml into the run folder; `make cov` merges them."""

    LEVELS = [(0, 0), (1, 7), (8, 8), (9, 9), (10, 16)]

    def build_phase(self):
        self.on = CoverPoint is not None
        if not self.on:
            return
        lv = self.LEVELS

        def lvl(p):
            return next(i for i, (a, b) in enumerate(lv) if a <= p.level <= b)

        # A FULL drop needs a level of 9 or more, and a forwarded packet 8 or less.
        impossible = [("full", b) for b in ("empty", "low", "at_8")] + \
                     [(f, b) for f in ("out0", "out1") for b in ("at_9", "high")]

        @CoverPoint("router.pkt.len", xf=lambda p: min(p.beats, 9), bins=list(range(1, 10)),
                    bins_labels=[f"len{n}" for n in range(1, 9)] + ["oversize"])
        @CoverPoint("router.pkt.dst", xf=lambda p: p.dst, bins=[0, 1, 2, 3])
        @CoverPoint("router.pkt.fate", xf=lambda p: p.fate, bins=["noroute", "full", "out0", "out1"])
        @CoverPoint("router.pkt.level", xf=lvl, bins=list(range(len(lv))),
                    bins_labels=["empty", "low", "at_8", "at_9", "high"])
        @CoverCross("router.pkt.fate_x_level", items=["router.pkt.fate", "router.pkt.level"],
                    ign_bins=impossible)
        def sample(p):
            pass

        self.sample = sample

    def write(self, pkt):
        if self.on:
            self.sample(pkt)

    def report_phase(self):
        if not self.on:
            self.logger.info("[COV] cocotb-coverage isn't installed (make venv); no coverage collected")
            return
        coverage_db.export_to_xml("coverage.xml")
        top = coverage_db["router.pkt"]
        self.logger.info(f"[COV] {top.cover_percentage:.1f}% of {top.size} bins; coverage.xml written")


class RouterEnv(uvm_env):
    def build_phase(self):
        self.sink_cfg = [SinkCfg(100), SinkCfg(100)]
        for k in (0, 1):
            ConfigDB().set(self, f"sink{k}", f"SINK{k}", self.sink_cfg[k])
        self.apb = ApbAgent("apb", self)
        self.src = SrcAgent("src", self)
        self.sink = [SinkDriver("sink0", self, 0), SinkDriver("sink1", self, 1)]
        self.mon = CycleMonitor("mon", self)
        self.sb = RouterScoreboard.create("sb", self)
        self.cov = RouterCoverage.create("cov", self)
        self.regs = RouterRegs()
        self.adapter = ApbRegAdapter()

    def connect_phase(self):
        self.mon.ap.connect(self.sb.sample_imp.analysis_export)
        self.sb.pkt_ap.connect(self.cov.analysis_export)
        self.regs.map.set_sequencer(self.apb.sqr)
        self.regs.map.set_adapter(self.adapter)
