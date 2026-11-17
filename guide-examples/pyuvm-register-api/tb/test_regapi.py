"""
DD105-B guide example for docs/reference/pyuvm-register-api.md: what
pyuvm 4.0.1's register layer does, run on the router in the course image.

  RegPolicyTest       no bus: predict() on a field of every access policy,
                      predict()'s arguments, what configure(), add_reg() and
                      reset() refuse, and which methods and classes exist
  RegOpsTest          read() and write() through the map: what each returns,
                      what reaches the adapter, and what happens to the mirror
  RegTwoOpsTest       two operations on one register at once, and on two
  RegBackdoorTest     the back door and the user front door
  RegAutoPredictTest  pyuvm's auto-predict switch, turned on
  RegAddrTest         register addresses as strings, and the map's base address

The bus side is labs/ref's APB agent, its register model (RouterRegs) and
its adapter (ApbRegAdapter), on the golden router. Every line the tests
print starts with "REGAPI", so `grep REGAPI` pulls them out of run.log.
Each test catches what an operation raises and prints it, so the test
itself passes.
"""

import cocotb
import pyuvm
import pyuvm.s21_uvm_reg_map as s21
import pyuvm.s24_uvm_reg_includes as s24
from pyuvm import (check_t, path_t, uvm_door_e, uvm_env, uvm_mem, uvm_predict_e, uvm_reg,
                   uvm_reg_block, uvm_reg_field, uvm_reg_map, uvm_reg_policy_t,
                   uvm_reg_predictor, uvm_subscriber)

from apb_agent import ApbAgent
from dd105b_base import RouterBaseTest
from router_ral import ApbRegAdapter, RouterRegs

DIRECT = uvm_predict_e.UVM_PREDICT_DIRECT
READ = uvm_predict_e.UVM_PREDICT_READ
WRITE = uvm_predict_e.UVM_PREDICT_WRITE
FD, NO = path_t.FRONTDOOR, check_t.NO_CHECK


def say(msg):
    print(f"REGAPI {msg}", flush=True)


def fmt(r):
    """A value an operation returned: a uvm_resp_t, a (status, data) pair, or None."""
    if isinstance(r, tuple):
        return f"({r[0].name}, {r[1]:#x})"
    if hasattr(r, "name"):
        return r.name
    return repr(r)


async def attempt(label, coro):
    """Await coro and say what it returned or raised."""
    try:
        r = await coro
    except Exception as e:
        say(f"{label}: raised {type(e).__name__}: {e}")
        return None
    say(f"{label}: returned {fmt(r)}")
    return r


def tryit(label, fn):
    """Call fn and say what it returned or raised."""
    try:
        r = fn()
    except Exception as e:
        say(f"{label}: raised {type(e).__name__}: {e}")
        return
    say(f"{label}: {r}")


class OneFieldReg(uvm_reg):
    """A 32-bit register with one field, F."""

    def __init__(self, name, access="RW", reset=0x5, size=4, lsb=0):
        super().__init__(name, 32)
        self.f_args = (size, lsb, access, reset)

    def build(self):
        size, lsb, access, reset = self.f_args
        self.F = uvm_reg_field("F")
        self.F.configure(self, size, lsb, access, False, reset)


class TwoFieldReg(uvm_reg):
    """STATUS's NOROUTE (bit 0) and FULL (bit 1), configured in the order
    given: a list of (name, lsb)."""

    def __init__(self, name, order):
        super().__init__(name, 32)
        self.order = order

    def build(self):
        for n, lsb in self.order:
            f = uvm_reg_field(n)
            f.configure(self, 1, lsb, "W1C", True, 0)


# ── the bus side ─────────────────────────────────────────────────────────────

class SayAdapter(ApbRegAdapter):
    """labs/ref's adapter, saying what the map hands it."""

    def reg2bus(self, rw):
        say(f"  reg2bus() got a {type(rw).__name__}: kind {rw.kind.name}, addr {rw.addr!r}, "
            f"data {rw.data:#x}, n_bits {rw.n_bits}, byte_en {rw.byte_en}")
        return super().reg2bus(rw)


class Transfers(uvm_subscriber):
    """Counts and prints every transfer the APB monitor sees complete."""

    def build_phase(self):
        self.n = 0

    def write(self, t):
        self.n += 1
        say(f"  bus, cycle {t.cycle}: {t}")


class RegEnv(uvm_env):
    def build_phase(self):
        self.apb = ApbAgent.create("apb", self)
        self.bus = Transfers.create("bus", self)
        self.regs = RouterRegs()
        self.regs.map.reset("HARD")
        self.adapter = SayAdapter()

    def connect_phase(self):
        self.apb.mon.ap.connect(self.bus.analysis_export)
        self.regs.map.set_sequencer(self.apb.sqr)
        self.regs.map.set_adapter(self.adapter)


class RegApiBase(RouterBaseTest):
    """Resets the router, runs body(), then waits for the bus to go quiet."""

    def build_phase(self):
        super().build_phase()
        self.env = RegEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        await self.reset()
        await self.body(self.env.regs, self.env.regs.map)
        await self.cycles(4)
        self.drop_objection()

    async def body(self, regs, map_):
        pass


# ── the tests ────────────────────────────────────────────────────────────────

@pyuvm.test()
class RegPolicyTest(RegApiBase):
    async def body(self, regs, map_):
        say(f"pyuvm {pyuvm.__version__}")

        say("predict() on a 4-bit field of each policy. The reset value is 0x5; before each call")
        say("the mirror is put at 0xc with UVM_PREDICT_DIRECT.")
        say("  policy    WRITE of 0xa    READ of 0x3")
        blk = uvm_reg_block("blk")
        for p in uvm_reg_policy_t:
            r = OneFieldReg(f"R_{p}", p)
            r.configure(blk, "0x0", "", False, False)
            r.reset()
            r.predict(0xC, kind=DIRECT)
            r.predict(0xA, kind=WRITE)
            w = r.get_mirrored_value()
            r.reset()
            r.predict(0xC, kind=DIRECT)
            r.predict(0x3, kind=READ)
            say(f"  {p:<9} {w:#5x}           {r.get_mirrored_value():#5x}")

        st = regs.STATUS
        st.predict(0x7, kind=DIRECT)
        st.predict(0x1, kind=WRITE)
        say(f"STATUS at 0x7, then predict(0x1, kind=UVM_PREDICT_WRITE): {st.get_mirrored_value():#x}")
        st.predict(0x7, kind=DIRECT)
        st.predict(0x1, kind=WRITE, path=path_t.FRONTDOOR)
        say("STATUS at 0x7, then predict(0x1, kind=UVM_PREDICT_WRITE, path=path_t.FRONTDOOR): "
            f"{st.get_mirrored_value():#x}")
        st.predict(0x7, kind=DIRECT)
        tryit("STATUS at 0x7, then predict(0x1, UVM_PREDICT_WRITE)",
              lambda: st.predict(0x1, WRITE))
        say(f"  STATUS's mirror after that: {st.get_mirrored_value():#x}")

        r = OneFieldReg("LOWER", "rw", reset=0, size=1)
        r.configure(blk, "0x0", "", False, False)
        r.F.predict(0x1, kind=WRITE)
        say(f'configure(..., "rw", ...): get_access() is {r.F.get_access()!r}; '
            f"after predict(0x1, kind=UVM_PREDICT_WRITE) the mirror is {r.get_mirrored_value():#x}")
        tryit("a 1-bit field with reset value 2",
              lambda: OneFieldReg("BIG", "RW", reset=2, size=1).configure(blk, "0x0", "", False, False))
        tryit("a field of size 0",
              lambda: OneFieldReg("ZERO", "RW", reset=0, size=0).configure(blk, "0x0", "", False, False))
        tryit("a 40-bit field in a 32-bit register",
              lambda: OneFieldReg("WIDE", "RW", reset=0, size=40).configure(blk, "0x0", "", False, False))
        tryit("STATUS's fields configured from bit 1 down",
              lambda: TwoFieldReg("STATUS", [("FULL", 1), ("NOROUTE", 0)]).configure(
                  blk, "0x8", "", False, False))
        r = OneFieldReg("R", "RW")
        r.configure(blk, "0x0", "", False, False)
        m = uvm_reg_map("m")
        m.configure(blk, 0)
        tryit('add_reg(reg, "0x0", "XX")', lambda: m.add_reg(r, "0x0", "XX"))
        tryit('map.reset("SOFT")', lambda: regs.map.reset("SOFT"))
        tryit('map.reset("POWER")', lambda: regs.map.reset("POWER"))
        tryit('add_hdl_path("dut.u_regs") on the block', lambda: regs.add_hdl_path("dut.u_regs"))
        tryit('uvm_mem("mem")', lambda: uvm_mem("mem"))

        own = sorted(n for n in vars(uvm_reg_predictor) if n == "__init__" or not n.startswith("__"))
        say(f"uvm_reg_predictor derives from {uvm_reg_predictor.__mro__[1].__name__} "
            f"and defines {own}")
        for cls, names in (
                (uvm_reg, ("read", "write", "predict", "get_mirrored_value", "get_desired",
                           "set_desired", "reset", "mirror", "update", "needs_update", "peek",
                           "poke", "get_reset", "set", "get")),
                (uvm_reg_field, ("predict", "get_value", "get_reset", "get", "field_set", "set",
                                 "reset", "is_volatile", "get_access")),
                (uvm_reg_map, ("set_sequencer", "set_adapter", "set_predictor", "reset",
                               "get_registers", "get_reg_by_offset", "set_auto_predict",
                               "set_check_on_read")),
                (uvm_reg_block, ("get_registers", "get_reg_by_name", "mirror", "update",
                                 "reset"))):
            has = [n for n in names if hasattr(cls, n)]
            lacks = [n for n in names if not hasattr(cls, n)]
            say(f"{cls.__name__} has {', '.join(has)}; it has no {', '.join(lacks)}")
        names = ("uvm_reg_predictor", "uvm_reg_hw_reset_seq", "uvm_reg_bit_bash_seq",
                 "uvm_reg_access_seq", "uvm_reg_mem_built_in_seq")
        say(f"in pyuvm: {', '.join(n for n in names if hasattr(pyuvm, n))}; "
            f"not in pyuvm: {', '.join(n for n in names if not hasattr(pyuvm, n))}")
        say(f"enable_auto_predict: {s21.enable_auto_predict} in s21_uvm_reg_map, "
            f"{s24.enable_auto_predict} in s24_uvm_reg_includes")


@pyuvm.test()
class RegOpsTest(RegApiBase):
    async def body(self, regs, map_):
        bus = self.env.bus
        say(f"ID's mirror before the read: {regs.ID.get_mirrored_value():#x}")
        await attempt("ID.read(map, path_t.FRONTDOOR, check_t.NO_CHECK)",
                      regs.ID.read(map_, FD, NO))
        await attempt("CTRL.write(0x1, map, path_t.FRONTDOOR, check_t.NO_CHECK)",
                      regs.CTRL.write(0x1, map_, FD, NO))
        say(f"CTRL's mirror after the write: {regs.CTRL.get_mirrored_value():#x}")
        await attempt("CTRL.read(map, path_t.FRONTDOOR, check_t.CHECK)",
                      regs.CTRL.read(map_, FD, check_t.CHECK))
        say(f"CTRL's mirror after the read: {regs.CTRL.get_mirrored_value():#x}; "
            f"errors logged so far: {self.errors.count}")
        regs.INT_EN.set_desired(0x5)
        say(f"INT_EN.set_desired(0x5): get_desired() is {regs.INT_EN.get_desired():#x}, "
            f"get_mirrored_value() is {regs.INT_EN.get_mirrored_value():#x}")
        await attempt("INT_EN.write(None, map, path_t.FRONTDOOR, check_t.NO_CHECK)",
                      regs.INT_EN.write(None, map_, FD, NO))
        n0 = bus.n
        await attempt("CTRL.write(0x0, map, uvm_door_e.UVM_FRONTDOOR, check_t.NO_CHECK)",
                      regs.CTRL.write(0x0, map_, uvm_door_e.UVM_FRONTDOOR, NO))
        say(f"  transfers on the bus during that write: {bus.n - n0}")
        await attempt("CTRL.read(map, path_t.FRONTDOOR, check_t.NO_CHECK)",
                      regs.CTRL.read(map_, FD, NO))
        await attempt("ROUTE0.read(map, uvm_door_e.UVM_FRONTDOOR, check_t.NO_CHECK)",
                      regs.ROUTE0.read(map_, uvm_door_e.UVM_FRONTDOOR, NO))
        await attempt("ROUTE0.read(map, path_t.FRONTDOOR, check_t.NO_CHECK) after that",
                      regs.ROUTE0.read(map_, FD, NO))


@pyuvm.test()
class RegTwoOpsTest(RegApiBase):
    async def body(self, regs, map_):
        t1 = cocotb.start_soon(attempt("CTRL.write(0x1, ...), started first",
                                       regs.CTRL.write(0x1, map_, FD, NO)))
        t2 = cocotb.start_soon(attempt("CTRL.write(0x0, ...), started in the same time step",
                                       regs.CTRL.write(0x0, map_, FD, NO)))
        await t1
        await t2
        t3 = cocotb.start_soon(attempt("CTRL.write(0x0, ...)", regs.CTRL.write(0x0, map_, FD, NO)))
        await self.cycles(1)
        t4 = cocotb.start_soon(attempt("CTRL.read(...), one cycle into that write",
                                       regs.CTRL.read(map_, FD, NO)))
        await t3
        await t4
        t5 = cocotb.start_soon(attempt("CTRL.write(0x1, ...)", regs.CTRL.write(0x1, map_, FD, NO)))
        t6 = cocotb.start_soon(attempt("INT_EN.write(0x7, ...), started in the same time step",
                                       regs.INT_EN.write(0x7, map_, FD, NO)))
        await t5
        await t6
        await attempt("CTRL.read(...) after all that", regs.CTRL.read(map_, FD, NO))


@pyuvm.test()
class RegBackdoorTest(RegApiBase):
    async def body(self, regs, map_):
        await attempt("CTRL.read(map, path_t.BACKDOOR, check_t.NO_CHECK)",
                      regs.CTRL.read(map_, path_t.BACKDOOR, NO))
        await attempt("CTRL.read(map, path_t.FRONTDOOR, check_t.NO_CHECK) after that",
                      regs.CTRL.read(map_, FD, NO))
        await attempt("INT_EN.write(0x1, map, path_t.BACKDOOR, check_t.NO_CHECK)",
                      regs.INT_EN.write(0x1, map_, path_t.BACKDOOR, NO))
        await attempt("ROUTE0.read(map, path_t.USER_FRONTDOOR, check_t.NO_CHECK)",
                      regs.ROUTE0.read(map_, path_t.USER_FRONTDOOR, NO))
        say(f"transfers on the bus: {self.env.bus.n}")


@pyuvm.test()
class RegAutoPredictTest(RegApiBase):
    async def body(self, regs, map_):
        s24.enable_auto_predict = True
        await attempt("with s24_uvm_reg_includes.enable_auto_predict = True: CTRL.write(0x1, ...)",
                      regs.CTRL.write(0x1, map_, FD, NO))
        say(f"  CTRL's mirror after it: {regs.CTRL.get_mirrored_value():#x}")
        s24.enable_auto_predict = False
        s21.enable_auto_predict = True
        await attempt("with s21_uvm_reg_map.enable_auto_predict = True, no predictor: "
                      "INT_EN.write(0x1, ...)", regs.INT_EN.write(0x1, map_, FD, NO))
        map_.set_predictor(uvm_reg_predictor("predictor"))
        await attempt("the same, with map.set_predictor(uvm_reg_predictor(\"predictor\")): "
                      "ROUTE0.write(0x1, ...)", regs.ROUTE0.write(0x1, map_, FD, NO))
        s21.enable_auto_predict = False
        say(f"mirrors after the three writes: CTRL {regs.CTRL.get_mirrored_value():#x}, "
            f"INT_EN {regs.INT_EN.get_mirrored_value():#x}, "
            f"ROUTE0 {regs.ROUTE0.get_mirrored_value():#x}; transfers on the bus: {self.env.bus.n}")


class AddrRegs(uvm_reg_block):
    """Three registers whose addresses don't follow the map's rule."""

    def __init__(self, name="addr_regs"):
        super().__init__(name)
        self.map = uvm_reg_map("map")
        self.map.configure(self, 0x200)
        self.Z = OneFieldReg("Z")
        self.Z.configure(self, "0x00", "", False, False)
        self.map.add_reg(self.Z, "0x0", "RW")
        self.O = OneFieldReg("O")
        self.O.configure(self, "0x4", "", False, False)
        self.map.add_reg(self.O, "0x100", "RW")
        self.S = OneFieldReg("S")
        self.S.configure(self, "0x8", "", False, False)
        self.map.add_reg(self.S, "0x0", "RW")


@pyuvm.test()
class RegAddrTest(RegApiBase):
    async def body(self, regs, map_):
        a = AddrRegs()
        a.map.set_sequencer(self.env.apb.sqr)
        a.map.set_adapter(self.env.adapter)
        say(f"map.configure(block, 0x200); the map's keys: {list(a.map.get_registers(as_dict=True))}")
        await attempt('Z.read(...), Z configured at "0x00" and added at offset "0x0"',
                      a.Z.read(a.map, FD, NO))
        await attempt('O.read(...), O configured at "0x4" and added at offset "0x100"',
                      a.O.read(a.map, FD, NO))
        await attempt('S.read(...), S configured at "0x8" and added at offset "0x0"',
                      a.S.read(a.map, FD, NO))
        tryit('map.get_reg_by_offset("0x8").get_name()',
              lambda: a.map.get_reg_by_offset("0x8").get_name())
        tryit('map.get_reg_by_offset("0x08").get_name()',
              lambda: a.map.get_reg_by_offset("0x08").get_name())
