"""
DD105-B guide example, "Register models in pyuvm": a bus agent for
regblk.sv, a register model of its four registers on pyuvm's classes, an
adapter, a predictor, and three tests.

  BusItem, BusDriver, BusMonitor, BusAgent, BusRawSeq
                  the bus: one transfer per item; BusRawSeq sends one
                  transfer that goes around the register model
  IdReg ... CountReg, RegBlk
                  the register model: four registers in one map
  BusAdapter      a register operation to one BusItem, and back
  RegPredictor    keeps the mirror in step with every transfer the monitor
                  sees (pyuvm's uvm_reg_predictor class is empty)
  RegMirrorTest   a write through the model, a raw write around it, and a
                  read checked against the mirror; then a volatile field.
                  +PREDICT=predictor (the default), none or auto
  RegPredictTest  what each kind of predict() does to four mirrors
  RegQuirksTest   what pyuvm 4.0.1 does with a misspelt access policy, an
                  address written as "0x00", two operations on one register
                  at once, a back-door read and a read with CHECK, and which
                  SystemVerilog UVM methods and sequences it doesn't have

The bus driver changes the pins right after a rising edge, and the monitor
reads them at the falling edge, the course's timing rule.
"""

import cocotb
import pyuvm
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge
from pyuvm import (ConfigDB, access_e, check_t, path_t, uvm_agent, uvm_analysis_port,
                   uvm_component, uvm_driver, uvm_monitor, uvm_predict_e, uvm_reg,
                   uvm_reg_adapter, uvm_reg_block, uvm_reg_field, uvm_reg_map, uvm_resp_t,
                   uvm_sequence, uvm_sequence_item, uvm_sequencer, uvm_subscriber)

from dd105b_base import BaseTest


# ── the bus ──────────────────────────────────────────────────────────────────

class BusItem(uvm_sequence_item):
    def __init__(self, name="bus_item", write=False, addr=0, wdata=0):
        super().__init__(name)
        self.write, self.addr, self.wdata, self.rdata = write, addr, wdata, 0

    def __str__(self):
        return (f"write {self.wdata:04x} to {self.addr:x}" if self.write
                else f"read {self.rdata:04x} from {self.addr:x}")


class BusDriver(uvm_driver):
    """One transfer per item: sel for one cycle, then an idle cycle."""

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d = self.dut
        while True:
            t = await self.seq_item_port.get_next_item()
            await RisingEdge(d.clk)
            d.sel.value, d.wr.value = 1, int(t.write)
            d.addr.value, d.wdata.value = t.addr, t.wdata
            await FallingEdge(d.clk)
            t.rdata = int(d.rdata.value)
            await RisingEdge(d.clk)
            d.sel.value = 0
            self.seq_item_port.item_done()


class BusMonitor(uvm_monitor):
    """A BusItem for every transfer, written at the falling edge of its cycle."""

    def build_phase(self):
        self.ap = uvm_analysis_port("ap", self)
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        d = self.dut
        while True:
            await FallingEdge(d.clk)
            if d.rst_n.value and d.sel.value:
                t = BusItem("seen", bool(d.wr.value), int(d.addr.value), int(d.wdata.value))
                t.rdata = int(d.rdata.value)
                self.ap.write(t)


class BusAgent(uvm_agent):
    def build_phase(self):
        self.sqr = uvm_sequencer("sqr", self)
        self.drv = BusDriver.create("drv", self)
        self.mon = BusMonitor.create("mon", self)

    def connect_phase(self):
        self.drv.seq_item_port.connect(self.sqr.seq_item_export)


class BusRawSeq(uvm_sequence):
    """One transfer, straight to the bus agent's sequencer."""

    def __init__(self, name="raw", write=False, addr=0, wdata=0):
        super().__init__(name)
        self.write, self.addr, self.wdata = write, addr, wdata

    async def body(self):
        t = BusItem("raw", self.write, self.addr, self.wdata)
        await self.start_item(t)
        await self.finish_item(t)


# ── the register model ───────────────────────────────────────────────────────
# field.configure(parent, size, lsb_pos, access, is_volatile, reset)

class IdReg(uvm_reg):
    def __init__(self, name="ID"):
        super().__init__(name, 16)

    def build(self):
        self.ID = uvm_reg_field("ID")
        self.ID.configure(self, 16, 0, "RO", False, 0x105B)


class CtrlReg(uvm_reg):
    def __init__(self, name="CTRL"):
        super().__init__(name, 16)

    def build(self):
        self.EN = uvm_reg_field("EN")
        self.EN.configure(self, 1, 0, "RW", False, 0)
        self.MODE = uvm_reg_field("MODE")
        self.MODE.configure(self, 3, 1, "RW", False, 0)


class FlagsReg(uvm_reg):
    def __init__(self, name="FLAGS"):
        super().__init__(name, 16)

    def build(self):
        self.OVF = uvm_reg_field("OVF")
        self.OVF.configure(self, 1, 0, "W1C", True, 0)
        self.ERR = uvm_reg_field("ERR")
        self.ERR.configure(self, 1, 1, "W1C", True, 0)


class CountReg(uvm_reg):
    def __init__(self, name="COUNT"):
        super().__init__(name, 16)

    def build(self):
        self.COUNT = uvm_reg_field("COUNT")
        self.COUNT.configure(self, 8, 0, "WC", True, 0)


class RegBlk(uvm_reg_block):
    """The four registers in one map. Each register is configured at its
    address as hex() prints it, and added to the map at offset "0x0"."""

    def __init__(self, name="regs"):
        super().__init__(name)
        self.map = uvm_reg_map("map")
        self.map.configure(self, 0)
        self.ID = self.add(IdReg("ID"), 0x0, "RO")
        self.CTRL = self.add(CtrlReg("CTRL"), 0x4)
        self.FLAGS = self.add(FlagsReg("FLAGS"), 0x8)
        self.COUNT = self.add(CountReg("COUNT"), 0xC)

    def add(self, reg, addr, rights="RW"):
        reg.configure(self, hex(addr), "", False, False)
        self.map.add_reg(reg, "0x0", rights)
        return reg

    def by_addr(self, addr):
        return self.map.get_registers(as_dict=True).get(hex(addr))


class BusAdapter(uvm_reg_adapter):
    def reg2bus(self, rw):
        """rw.addr is the address as the string the register was configured with."""
        write = rw.kind == access_e.UVM_WRITE
        return BusItem("reg", write, int(rw.addr, 16), rw.data if write else 0)

    def bus2reg(self, t, rw):
        rw.kind = access_e.UVM_WRITE if t.write else access_e.UVM_READ
        rw.data = t.wdata if t.write else t.rdata
        rw.status = uvm_resp_t.PASS_RESP


class RegPredictor(uvm_subscriber):
    """A write: predict(value, UVM_PREDICT_WRITE), so each field follows its
    access policy. A read: predict(value, UVM_PREDICT_DIRECT)."""

    def build_phase(self):
        self.regs = None

    def write(self, t):
        reg = self.regs.by_addr(t.addr)
        if reg is None:
            return
        if t.write:
            reg.predict(t.wdata, kind=uvm_predict_e.UVM_PREDICT_WRITE)
        else:
            reg.predict(t.rdata, kind=uvm_predict_e.UVM_PREDICT_DIRECT)


class RegEnv(uvm_component):
    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.bus = BusAgent.create("bus", self)
        self.predictor = RegPredictor.create("predictor", self)
        self.regs = RegBlk("regs")
        self.adapter = BusAdapter("adapter")

    def connect_phase(self):
        self.regs.map.set_sequencer(self.bus.sqr)
        self.regs.map.set_adapter(self.adapter)
        self.regs.map.reset("HARD")
        self.predictor.regs = self.regs
        self.mode = cocotb.plusargs.get("PREDICT", "predictor")
        if self.mode == "predictor":
            self.bus.mon.ap.connect(self.predictor.analysis_export)
        elif self.mode == "auto":
            # pyuvm's switch for auto-predict is a module global that the map's
            # module copies when it is imported, so it has to be set there.
            import pyuvm.s21_uvm_reg_map as m
            m.enable_auto_predict = True


# ── the tests ────────────────────────────────────────────────────────────────

class RegBaseTest(BaseTest):
    def build_phase(self):
        ConfigDB().set(None, "*", "DUT", cocotb.top)
        self.env = RegEnv.create("env", self)

    async def start(self):
        d = cocotb.top
        for s in ("rst_n", "sel", "wr", "addr", "wdata", "ev_ovf", "ev_err"):
            getattr(d, s).value = 0
        cocotb.start_soon(Clock(d.clk, 10, unit="ns").start())
        for _ in range(2):
            await RisingEdge(d.clk)
        d.rst_n.value = 1
        self.regs = self.env.regs
        self.map = self.regs.map

    def say(self, msg):
        self.logger.info(f"[RAL] {msg}")

    async def write(self, reg, value):
        return await reg.write(value, self.map, path_t.FRONTDOOR, check_t.NO_CHECK)

    async def read(self, reg):
        return await reg.read(self.map, path_t.FRONTDOOR, check_t.NO_CHECK)

    async def raw_write(self, addr, value):
        await BusRawSeq("raw", True, addr, value).start(self.env.bus.sqr)


@pyuvm.test()
class RegMirrorTest(RegBaseTest):
    async def run_phase(self):
        self.raise_objection()
        await self.start()
        regs, d = self.regs, cocotb.top
        self.say(f"predict: {self.env.mode}")

        status = await self.write(regs.CTRL, 0x0005)
        self.say(f"write(0x0005) to CTRL through the model returned {status.name}; "
                 f"the mirror holds {regs.CTRL.get_mirrored_value():04x}")
        await self.raw_write(0x4, 0x000B)
        self.say(f"a raw write of 000b to CTRL, around the model; "
                 f"the mirror holds {regs.CTRL.get_mirrored_value():04x}")
        before = regs.CTRL.get_mirrored_value()
        status, value = await self.read(regs.CTRL)
        self.say(f"read CTRL through the model: {value:04x}; the mirror held {before:04x} "
                 f"before the read: {'match' if value == before else 'MISMATCH'}")

        # A volatile field: the design sets FLAGS.OVF on its own.
        await RisingEdge(d.clk)
        d.ev_ovf.value = 1
        await RisingEdge(d.clk)
        d.ev_ovf.value = 0
        self.say(f"after an overflow event, the mirror of FLAGS holds "
                 f"{regs.FLAGS.get_mirrored_value():04x}")
        status, value = await self.read(regs.FLAGS)
        self.say(f"read FLAGS through the model: {value:04x}; the mirror now holds "
                 f"{regs.FLAGS.get_mirrored_value():04x}")
        self.drop_objection()


@pyuvm.test()
class RegPredictTest(RegBaseTest):
    """predict() on its own, no transfers: what each kind does to a mirror."""

    async def run_phase(self):
        self.raise_objection()
        await self.start()
        regs = self.regs
        W, R, D = (uvm_predict_e.UVM_PREDICT_WRITE, uvm_predict_e.UVM_PREDICT_READ,
                   uvm_predict_e.UVM_PREDICT_DIRECT)
        steps = [(regs.FLAGS, [(0x3, D), (0x1, W), (0x2, R), (0x2, D)]),
                 (regs.COUNT, [(0x2A, D), (0x5, W), (0x2A, D), (0x2A, R)]),
                 (regs.CTRL, [(0xB, W), (0x5, R)]),
                 (regs.ID, [(0x1234, W)])]
        for reg, calls in steps:
            access = reg.get_fields()[0].get_access()
            self.say(f"{reg.get_name()} ({access}), after the reset: {reg.get_mirrored_value():#x}")
            for value, kind in calls:
                reg.predict(value, kind=kind)
                self.say(f"  then predict({value:#x}, {kind.name})".ljust(44)
                         + f"{reg.get_mirrored_value():#x}")
        self.drop_objection()


class TypoReg(uvm_reg):
    def __init__(self, name="TYPO"):
        super().__init__(name, 16)

    def build(self):
        self.F = uvm_reg_field("F")
        self.F.configure(self, 1, 0, "W1c", False, 0)


class ZeroBlk(uvm_reg_block):
    """One register configured at "0x00" instead of hex(0), "0x0"."""

    def __init__(self, name="zero"):
        super().__init__(name)
        self.map = uvm_reg_map("map")
        self.map.configure(self, 0)
        self.R = CtrlReg("R")
        self.R.configure(self, "0x00", "", False, False)
        self.map.add_reg(self.R, "0x0", "RW")


@pyuvm.test()
class RegQuirksTest(RegBaseTest):
    async def run_phase(self):
        self.raise_objection()
        await self.start()
        regs = self.regs

        # An access policy pyuvm doesn't know is accepted as "NOACCESS".
        t = TypoReg("TYPO")
        t.configure(uvm_reg_block("scratch"), hex(0x0), "", False, False)
        self.say(f'a field configured with "W1c" has the policy {t.F.get_access()}')

        # The map is keyed by hex(): "0x00" is never found.
        z = ZeroBlk("zero")
        z.map.set_sequencer(self.env.bus.sqr)
        z.map.set_adapter(self.env.adapter)
        try:
            await z.R.write(1, z.map, path_t.FRONTDOOR, check_t.NO_CHECK)
            self.say('a register configured at "0x00": the write went through')
        except Exception as e:
            self.say(f'a register configured at "0x00": {type(e).__name__}: {e}')

        # Two operations on one register at once.
        async def write(value):
            try:
                status = await self.write(regs.CTRL, value)
                return status.name
            except Exception as e:
                return f"{type(e).__name__}: {e}"
        t1 = cocotb.start_soon(write(0x1))
        t2 = cocotb.start_soon(write(0x2))
        r1, r2 = await t1, await t2
        self.say(f"two writes to CTRL at once: the first {r1}; the second {r2}")

        # read() with CHECK against a mirror that is out of date: CTRL holds
        # 0007, and the mirror is set to 0003 by hand.
        await self.raw_write(0x4, 0x0007)
        regs.CTRL.predict(0x0003, kind=uvm_predict_e.UVM_PREDICT_DIRECT)
        before = regs.CTRL.get_mirrored_value()
        status, value = await regs.CTRL.read(self.map, path_t.FRONTDOOR, check_t.CHECK)
        self.say(f"read(CHECK) of CTRL returned {status.name} with {value:04x}, "
                 f"against a mirror of {before:04x}")

        # The back door.
        try:
            await regs.ID.read(self.map, path_t.BACKDOOR, check_t.NO_CHECK)
            self.say("a back-door read of ID went through")
        except Exception as e:
            self.say(f"a back-door read of ID: {type(e).__name__}: {e}")

        # What SystemVerilog UVM has and pyuvm 4.0.1 doesn't.
        gone = [m for m in ("mirror", "update", "needs_update", "peek", "poke", "set", "get_reset")
                if not hasattr(uvm_reg, m)]
        self.say(f"uvm_reg has no {', '.join(gone)}")
        seqs = [s for s in ("uvm_reg_hw_reset_seq", "uvm_reg_bit_bash_seq", "uvm_reg_access_seq",
                            "uvm_reg_predictor") if hasattr(pyuvm, s)]
        self.say(f"of uvm_reg_hw_reset_seq, uvm_reg_bit_bash_seq, uvm_reg_access_seq and "
                 f"uvm_reg_predictor, pyuvm has {', '.join(seqs) or 'none'}")
        p = pyuvm.uvm_reg_predictor("p")
        own = [m for m in vars(type(p)) if not m.startswith("__")]
        self.say(f"uvm_reg_predictor's own methods: {', '.join(own) or 'none'}")
        self.drop_objection()
