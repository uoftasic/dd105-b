"""
DD105-B reference environment: the tests.

Every test derives from RouterRefTest, which derives from the course's
RouterBaseTest. None of the steps below checks anything itself: the
scoreboard compares every pin with the model in every cycle, so a step only
has to make something happen. Each step starts with a reset.

    make run TEST=RouterRandTest SEED=7 PLUSARGS="+N=500 +PHASES=6"

Plusargs: +N (packets per random phase, default 250) and +PHASES (random
phases, default 4).
"""

import random

import cocotb
import pyuvm
from cocotb.triggers import RisingEdge
from pyuvm import check_t, path_t

from dd105b_base import RouterBaseTest
from router_agents import ApbRawSeq, PktSeq, make_packet
from router_env import RouterEnv
from router_ral import REGISTERS

REG_NAMES = [r[0] for r in REGISTERS]


def plusarg(name, default):
    try:
        return int(cocotb.plusargs.get(name, default))
    except (TypeError, ValueError):
        return default


class RouterRefTest(RouterBaseTest):
    """The environment, and the helpers every step uses."""

    def build_phase(self):
        super().build_phase()
        self.env = RouterEnv("env", self)

    @property
    def model(self):
        return self.env.sb.model

    # registers, through the register model or raw
    async def wr(self, reg, value):
        r = self.env.regs
        await getattr(r, reg).write(value, r.map, path_t.FRONTDOOR, check_t.NO_CHECK)

    async def rd(self, reg):
        r = self.env.regs
        _, data = await getattr(r, reg).read(r.map, path_t.FRONTDOOR, check_t.NO_CHECK)
        return data

    async def raw(self, addr, write=False, data=0):
        seq = ApbRawSeq("raw", addr, data, write)
        await seq.start(self.env.apb.sqr)
        return seq.item

    async def read_all(self):
        for name in REG_NAMES:
            await self.rd(name)

    async def routes(self, table):
        """table: four (EN, PORT) pairs."""
        for n, (en, port) in enumerate(table):
            await self.wr(f"ROUTE{n}", (port << 1) | en)

    # traffic
    async def send(self, pkts):
        await PktSeq("pkts", pkts).start(self.env.src.sqr)

    def sinks(self, pct0, pct1):
        self.env.sink_cfg[0].ready_pct = pct0
        self.env.sink_cfg[1].ready_pct = pct1

    async def drain(self, limit=400):
        """Both sinks ready until the model's buffers are empty."""
        self.sinks(100, 100)
        for _ in range(limit):
            if self.model.level(0) == 0 and self.model.level(1) == 0 and not self.env.src.drv.busy:
                break
            await RisingEdge(self.dut.clk)
        await self.cycles(3)

    async def fill(self, dst, n):
        """n one-beat packets for dst."""
        await self.send([make_packet(dst, 1) for _ in range(n)])

    async def start(self, table, int_en=0, en=1):
        await self.reset()
        await self.routes(table)
        await self.wr("INT_EN", int_en)
        await self.wr("CTRL", en)

    # ── the directed steps ──────────────────────────────────────────────────
    async def step_regs(self):
        """Reset values, every register written and read back with values whose
        bits differ, the first 64 addresses read (misaligned ones included),
        bad and ignored writes."""
        await self.reset()
        await self.read_all()
        for v in (1, 0):
            await self.wr("CTRL", v)
            await self.rd("CTRL")
        for v in (1, 2, 4, 7, 0):
            await self.wr("INT_EN", v)
            await self.rd("INT_EN")
        for n in range(4):
            for v in (1, 2, 3, 0):
                await self.wr(f"ROUTE{n}", v)
                await self.rd(f"ROUTE{n}")
        await self.routes([(1, 0), (0, 1), (1, 1), (0, 0)])
        for addr in range(0x40):
            await self.raw(addr)
        for addr in (0x18, 0x1C, 0x30, 0x7C, 0xFC, 0xFF):
            await self.raw(addr)
        for addr in (0x05, 0x06, 0x07, 0x0D, 0x21, 0x22, 0x2F, 0x18, 0x1C, 0x40, 0xF0):
            await self.raw(addr, write=True, data=0xFFFF_FFFF)
            await self.read_all()
        await self.raw(0x00, write=True, data=0)
        await self.raw(0x14, write=True, data=0xFFFF)
        await self.read_all()

    async def step_full(self):
        """The admission threshold from both sides, on each output, with the
        other output empty or full, and a disabled route whose PORT names a
        full output."""
        await self.start([(1, 0), (1, 1), (0, 0), (0, 1)], int_en=7)
        self.sinks(0, 0)
        await self.send([make_packet(0, 8), make_packet(0, 1)])   # level 8, then admitted at 8
        await self.send([make_packet(0, 1)])                      # FULL at 9
        await self.send([make_packet(2, 2)])                      # NOROUTE, its PORT 0 full
        await self.send([make_packet(1, 3)])                      # output 1 at 0: admitted
        await self.cycles(4)
        for reg in ("STATUS", "DROP_CNT", "LEVEL"):
            await self.rd(reg)
        self.sinks(0, 100)                                        # output 1 runs, 0 stalled
        await self.cycles(12)
        await self.rd("LEVEL")
        await self.drain()
        await self.wr("STATUS", 7)
        await self.wr("DROP_CNT", 0)
        self.sinks(0, 0)
        await self.fill(1, 9)                                     # output 1 at 9
        await self.send([make_packet(1, 1), make_packet(0, 2)])   # FULL on 1; output 0 at 0
        await self.send([make_packet(3, 1)])                      # NOROUTE, its PORT 1 full
        await self.cycles(4)
        for reg in ("STATUS", "DROP_CNT", "LEVEL"):
            await self.rd(reg)
        self.sinks(100, 0)
        await self.cycles(8)
        await self.drain()
        await self.read_all()

    async def step_oversize(self):
        """Packets of 9 to 12 beats, forwarded on both outputs, dropped as
        NOROUTE and as FULL (E6)."""
        await self.start([(1, 0), (1, 1), (0, 0), (1, 0)])
        await self.send([make_packet(0, 9), make_packet(1, 10), make_packet(2, 11),
                         make_packet(3, 12, gap_pct=50), make_packet(0, 8)])
        await self.drain()
        await self.rd("STATUS")
        await self.wr("STATUS", 4)
        self.sinks(0, 100)
        await self.fill(0, 9)
        await self.send([make_packet(0, 10), make_packet(1, 9)])
        await self.cycles(4)
        await self.read_all()
        await self.drain()

    async def step_irq(self):
        """Each STATUS bit against all eight INT_EN settings, cleared one bit at a time."""
        await self.start([(1, 0), (0, 0), (0, 0), (0, 0)])
        for order in ((0, 1, 2), (2, 1, 0), (1, 0, 2)):
            self.sinks(0, 100)
            await self.fill(0, 9)
            await self.send([make_packet(0, 1)])                  # FULL
            await self.send([make_packet(1, 1)])                  # NOROUTE
            await self.drain()
            await self.send([make_packet(0, 9)])                  # OVERSIZE
            await self.drain()
            await self.rd("STATUS")
            for v in range(8):
                await self.wr("INT_EN", v)
                await self.cycles(2)
            for bit in order:
                await self.wr("STATUS", 1 << bit)
                await self.rd("STATUS")
                for v in range(8):
                    await self.wr("INT_EN", v)
            await self.wr("INT_EN", 0)

    async def step_ctrl(self):
        """CTRL.EN cleared in the middle of a packet (E7), and set again while a
        header waits."""
        await self.start([(1, 0), (1, 1), (0, 0), (0, 0)])
        long = cocotb.start_soon(self.send([make_packet(0, 8, gap_pct=60), make_packet(1, 2)]))
        await self.cycles(3)
        await self.wr("CTRL", 0)
        await self.cycles(20)
        await self.rd("CTRL")
        await self.wr("CTRL", 1)
        await long
        await self.drain()

    async def step_reset(self):
        """Reset with beats waiting on both stalled outputs (E8), then nothing
        may come out."""
        for _ in range(2):
            await self.start([(1, 0), (1, 1), (0, 0), (0, 0)])
            self.sinks(0, 0)
            await self.send([make_packet(0, 2), make_packet(1, 3), make_packet(0, 1)])
            await self.cycles(5)
            await self.reset()
            self.sinks(100, 100)
            await self.cycles(10)
            await self.read_all()

    async def step_saturate(self):
        """Both drop counters past 255, and cleared."""
        await self.start([(1, 0), (0, 0), (0, 0), (0, 0)])
        await self.fill(1, 260)
        await self.rd("DROP_CNT")
        self.sinks(0, 100)
        await self.fill(0, 9)
        await self.fill(0, 260)
        await self.rd("DROP_CNT")
        await self.wr("DROP_CNT", 0)
        await self.rd("DROP_CNT")
        await self.drain()

    async def step_random(self, phases=None, n=None):
        """Random routing tables, packets, idle cycles, backpressure and
        register traffic, all at once, with resets between some phases."""
        phases = plusarg("PHASES", 4) if phases is None else phases
        n = plusarg("N", 250) if n is None else n
        for ph in range(phases):
            if ph == 0 or random.random() < 0.4:
                await self.reset()
            table = [(random.randint(0, 1), random.randint(0, 1)) for _ in range(4)]
            off, on = random.sample(range(4), 2)       # at least one route off and one on
            table[off] = (0, random.randint(0, 1))
            table[on] = (1, random.randint(0, 1))
            await self.routes(table)
            await self.wr("INT_EN", random.randrange(8))
            await self.wr("CTRL", 1)
            self.busy = True
            src = cocotb.start_soon(self._random_packets(n))
            apb = cocotb.start_soon(self._random_apb())
            snk = cocotb.start_soon(self._random_sinks())
            await src
            self.busy = False
            await apb
            await snk
            await self.drain()
            await self.read_all()
            if random.random() < 0.5:                  # a reset with beats waiting
                self.sinks(0, random.choice([0, 100]))
                await self.send([make_packet(d, random.randint(1, 6)) for d in range(4)])
                await self.cycles(random.randint(0, 6))
                await self.reset()
                self.sinks(100, 100)
                await self.cycles(5)

    async def _random_packets(self, n):
        pkts = []
        for _ in range(n):
            r = random.randrange(100)
            length = 1 if r < 20 else random.randint(2, 7) if r < 70 else 8 if r < 85 else random.randint(9, 12)
            pkts.append(make_packet(random.randrange(4), length, gap_pct=30))
        await self.send(pkts)

    async def _random_sinks(self):
        while self.busy:
            self.sinks(random.choice([100, 100, 75, 50, 20, 0]), random.choice([100, 100, 75, 50, 20, 0]))
            await self.cycles(random.randint(10, 80))

    async def _random_apb(self):
        while self.busy:
            r = random.randrange(100)
            if r < 40:
                await self.rd(random.choice(REG_NAMES))
            elif r < 55:
                await self.wr("STATUS", random.randrange(8))
            elif r < 60:
                await self.wr("DROP_CNT", random.randrange(1 << 16))
            elif r < 68:
                await self.wr("INT_EN", random.randrange(8))
            elif r < 74:
                await self.wr(f"ROUTE{random.randrange(4)}", random.randrange(4))
            elif r < 77:
                await self.wr("CTRL", 0)
                await self.cycles(random.randint(1, 20))
                await self.wr("CTRL", 1)
            elif r < 92:
                await self.raw(random.randrange(256), write=random.random() < 0.5,
                               data=random.randrange(1 << 32))
                await self.wr("CTRL", 1)               # a bad write mustn't have changed it
            else:
                await self.cycles(random.randint(1, 10))

    async def run_steps(self, *steps):
        self.raise_objection()
        for step in steps:
            await step()
        await self.drain()
        self.drop_objection()


def ref_test(cls):
    return pyuvm.test(timeout_time=5, timeout_unit="ms")(cls)


@ref_test
class RouterAllTest(RouterRefTest):
    """Every directed step, then the random phases: `make check` grades this one."""

    async def run_phase(self):
        await self.run_steps(self.step_regs, self.step_full, self.step_oversize, self.step_irq,
                             self.step_ctrl, self.step_reset, self.step_saturate, self.step_random)


@ref_test
class RouterRandTest(RouterRefTest):
    async def run_phase(self):
        await self.run_steps(self.step_random)


@ref_test
class RouterSmokeTest(RouterRefTest):
    """One routing table, a few packets, every register read before and after."""

    async def run_phase(self):
        async def smoke():
            await self.start([(1, 0), (1, 1), (0, 0), (1, 0)])
            await self.read_all()
            await self.send([make_packet(d, 3) for d in range(4)])
            await self.drain()
            await self.read_all()
        await self.run_steps(smoke)


@ref_test
class RouterRegsTest(RouterRefTest):
    async def run_phase(self):
        await self.run_steps(self.step_regs)


@ref_test
class RouterFullTest(RouterRefTest):
    async def run_phase(self):
        await self.run_steps(self.step_full)


@ref_test
class RouterOversizeTest(RouterRefTest):
    async def run_phase(self):
        await self.run_steps(self.step_oversize)


@ref_test
class RouterIrqTest(RouterRefTest):
    async def run_phase(self):
        await self.run_steps(self.step_irq)


@ref_test
class RouterCtrlTest(RouterRefTest):
    async def run_phase(self):
        await self.run_steps(self.step_ctrl)


@ref_test
class RouterResetTest(RouterRefTest):
    async def run_phase(self):
        await self.run_steps(self.step_reset)


@ref_test
class RouterSaturateTest(RouterRefTest):
    async def run_phase(self):
        await self.run_steps(self.step_saturate)
