"""
DD105-B reference environment: the router's register layer, on pyuvm 4.0.1.

  RouterRegs          the register model: router-spec.md's "Register map"
  ApbRegAdapter       register operations to ApbItems and back
  RouterRegPredictor  keeps the model's mirror in step with every transfer
                      the APB monitor sees, and checks every read
  RegResetSeq         every register read straight after a reset
  RegBitBashSeq       every bit of every register written both ways and read back

pyuvm has the classes for the model, the map and the adapter, and nothing
that keeps the mirror up to date: no predictor (its uvm_reg_predictor class
is empty), no auto-predict, no mirror() or update(), and none of SystemVerilog
UVM's built-in register sequences. So this file has the course's own
predictor and the two sequences, which take the place of
uvm_reg_hw_reset_seq and uvm_reg_bit_bash_seq. Lab 06 has students write
all three.

Three pyuvm habits shape the model:

  - A map keys its registers by the address as hex() prints it ("0x8"), and
    looks a register up by the address string it was configured with, so
    every address below is written the way hex() writes it.
  - Two operations on one register at once raise UVMFatalError (SystemVerilog
    UVM would make the second wait), so the virtual sequences take a lock per
    register (router_seqs.RouterVseq).
  - predict(value, UVM_PREDICT_READ) sets a W1C field's mirror to its reset
    value rather than the value read, so after a read the predictor uses
    UVM_PREDICT_DIRECT, which takes the value as it is.

This file imports nothing that needs the course venv, so the graders'
register-model check (labs/common/regcheck.py) builds RouterRegs with the
image's own Python.
"""

import logging
import random

from pyuvm import (access_e, check_t, path_t, uvm_component, uvm_predict_e, uvm_reg, uvm_reg_adapter,
                   uvm_reg_block, uvm_reg_field, uvm_reg_map, uvm_resp_t, uvm_sequence)

from apb_agent import ApbItem
from router_common import Fwd

# name, address, [(field, lsb, size, access, volatile, reset)]
REGISTERS = [
    ("ID", 0x00, [("ID", 0, 32, "RO", False, 0xD105_0001)]),
    ("CTRL", 0x04, [("EN", 0, 1, "RW", False, 0)]),
    ("STATUS", 0x08, [("NOROUTE", 0, 1, "W1C", True, 0), ("FULL", 1, 1, "W1C", True, 0),
                      ("OVERSIZE", 2, 1, "W1C", True, 0)]),
    ("INT_EN", 0x0C, [("NOROUTE", 0, 1, "RW", False, 0), ("FULL", 1, 1, "RW", False, 0),
                      ("OVERSIZE", 2, 1, "RW", False, 0)]),
    ("DROP_CNT", 0x10, [("NOROUTE_CNT", 0, 8, "WC", True, 0), ("FULL_CNT", 8, 8, "WC", True, 0)]),
    ("LEVEL", 0x14, [("LEVEL0", 0, 5, "RO", True, 0), ("LEVEL1", 8, 5, "RO", True, 0)]),
] + [(f"ROUTE{n}", 0x20 + 4 * n, [("EN", 0, 1, "RW", False, 0), ("PORT", 1, 1, "RW", False, 0)])
     for n in range(4)]


class RouterReg(uvm_reg):
    def __init__(self, name, fields):
        super().__init__(name, 32)
        self._spec = fields

    def build(self):
        for fname, lsb, size, access, volatile, reset in self._spec:
            f = uvm_reg_field(fname)
            f.configure(self, size, lsb, access, volatile, reset)
            setattr(self, fname, f)


def field_mask(f):
    return ((1 << f.get_n_bits()) - 1) << f.get_lsb_pos()


def volatile_mask(reg):
    """The bits of the register's volatile fields, which hardware changes on
    its own, so a read can't be compared with the mirror there."""
    m = 0
    for f in reg.get_fields():
        if f.is_volatile():
            m |= field_mask(f)
    return m


def reset_value(reg):
    return sum(f.get_reset() << f.get_lsb_pos() for f in reg.get_fields())


class RouterRegs(uvm_reg_block):
    """The router's ten registers, in one map at address 0. `regs` lists them
    in address order; each is also an attribute (`regs.CTRL`)."""

    def __init__(self, name="router_regs"):
        super().__init__(name)
        self.map = uvm_reg_map("map")
        self.map.configure(self, 0)
        self.regs = []
        for name_, addr, fields in REGISTERS:
            reg = RouterReg(name_, fields)
            reg.configure(self, hex(addr), "", False, False)
            self.map.add_reg(reg, "0x0", "RO" if name_ in ("ID", "LEVEL") else "RW")
            setattr(self, name_, reg)
            self.regs.append(reg)

    def by_addr(self, addr):
        """The register at byte address `addr`, or None for a bad address."""
        if addr & 3:
            return None
        return self.map.get_registers(as_dict=True).get(hex(addr))


class ApbRegAdapter(uvm_reg_adapter):
    """A register operation becomes one ApbItem, with 0 to 2 idle cycles
    before it, as DD105-A's adapter does. PSLVERR comes back as ERROR_RESP."""

    def reg2bus(self, rw):
        addr = int(rw.addr, 16) if isinstance(rw.addr, str) else rw.addr
        write = rw.kind == access_e.UVM_WRITE
        return ApbItem("ral", addr, rw.data if write else 0, write, idle=random.randint(0, 2))

    def bus2reg(self, item, rw):
        rw.kind = access_e.UVM_WRITE if item.write else access_e.UVM_READ
        rw.data = item.data
        rw.status = uvm_resp_t.ERROR_RESP if item.slverr else uvm_resp_t.PASS_RESP


class RouterRegPredictor(uvm_component):
    """The course's predictor: SystemVerilog UVM's uvm_reg_predictor, which
    pyuvm doesn't have. It subscribes to the APB monitor, so the mirror
    follows every transfer on the bus, whoever started it: the register
    model's own, the raw ones, and a transfer a reset abandoned and the
    driver started again.

      a write   predict(value, UVM_PREDICT_WRITE): each field takes the value
                its access policy says (RW the value, W1C clears the ones,
                WC clears, RO keeps what it had)
      a read    first, with check_on_read, compare the value read with the
                mirror outside the volatile fields (reserved bits included,
                which must read 0); then predict(value, UVM_PREDICT_DIRECT)
      a reset   map.reset("HARD"): every field back to its reset value

    A transfer that ended with PSLVERR, or to an address that isn't a
    register, has no register to predict, and is skipped; the scoreboard
    checks PSLVERR. The env sets `map` in its connect_phase."""

    def build_phase(self):
        self.bus_in = Fwd("bus_in", self, self.write_bus)
        self.reset_in = Fwd("reset_in", self, self.write_sample)
        self.regs = None
        self.check_on_read = True
        self.reads = self.writes = self.mismatches = 0
        self._in_reset = False

    def write_bus(self, t):
        if t.slverr:
            return
        reg = self.regs.by_addr(t.addr)
        if reg is None:
            return
        if t.write:
            self.writes += 1
            reg.predict(t.data, kind=uvm_predict_e.UVM_PREDICT_WRITE)
            return
        self.reads += 1
        if self.check_on_read:
            dc = volatile_mask(reg)
            want, got = reg.get_mirrored_value() | dc, t.data | dc
            if got != want:
                self.mismatches += 1
                self.logger.error(f"cycle {t.cycle}: {reg.get_name()} read {t.data:#x}; the mirror holds "
                                  f"{reg.get_mirrored_value():#x}"
                                  + (f" (bits {dc:#x} are volatile and not compared)" if dc else ""))
        reg.predict(t.data, kind=uvm_predict_e.UVM_PREDICT_DIRECT)

    def write_sample(self, s):
        """From the cycle monitor: put the mirror back to the reset values in
        the first cycle of each reset."""
        if not s.rst_n and not self._in_reset:
            self.regs.map.reset("HARD")
        self._in_reset = not s.rst_n

    def report_phase(self):
        self.logger.info(f"[RAL] {self.reads} register reads checked against the mirror, "
                         f"{self.writes} writes predicted; {self.mismatches} mismatches")


class RegSeq(uvm_sequence):
    """What the two register sequences share. They run on no sequencer: the
    map sends each operation to the APB sequencer itself. pyuvm sequences have
    no logger, so they report through a component's, which BaseTest counts:
    the predictor's, unless another is given."""

    def __init__(self, name, regs, logger=None):
        super().__init__(name)
        self.regs = regs
        self.logger = logger or logging.getLogger(name)
        self.errors = 0

    def fail(self, msg):
        self.errors += 1
        self.logger.error(f"[{self.get_name()}] {msg}")

    async def rd(self, reg):
        status, value = await reg.read(self.regs.map, path_t.FRONTDOOR, check_t.NO_CHECK)
        if status != uvm_resp_t.PASS_RESP:
            self.fail(f"reading {reg.get_name()} returned {status}")
        return value

    async def wr(self, reg, value):
        status = await reg.write(value, self.regs.map, path_t.FRONTDOOR, check_t.NO_CHECK)
        if status != uvm_resp_t.PASS_RESP:
            self.fail(f"writing {value:#x} to {reg.get_name()} returned {status}")


class RegResetSeq(RegSeq):
    """pyuvm's counterpart of uvm_reg_hw_reset_seq. Start it straight after a
    reset, before anything else touches the router: it puts the mirror back
    to the reset values and reads every register, and each must read its
    reset value. Unlike UVM's, it compares the volatile fields too (STATUS,
    DROP_CNT and LEVEL), which holds only while nothing has happened since
    the reset."""

    async def body(self):
        self.regs.map.reset("HARD")
        for reg in self.regs.regs:
            got, want = await self.rd(reg), reset_value(reg)
            if got != want:
                self.fail(f"{reg.get_name()} reads {got:#x} after reset; its reset value is {want:#x}")


class RegBitBashSeq(RegSeq):
    """pyuvm's counterpart of uvm_reg_bit_bash_seq. For every register, and
    every bit of it that isn't in a volatile field: write the register with
    that bit flipped from what the mirror holds, read it back, and compare
    with the mirror, which the predictor has moved by the field's policy.
    Each bit is flipped twice, so it is written both ways. A read-write bit
    must follow the write; a read-only bit, and every bit outside a field,
    must not change. Run it with no traffic: CTRL.EN and the routes change as
    it goes, and DROP_CNT is cleared by every write to it."""

    async def body(self):
        for reg in self.regs.regs:
            dc = volatile_mask(reg)
            for k in range(reg.get_reg_size()):
                if dc >> k & 1:
                    continue
                for _ in range(2):
                    before = reg.get_mirrored_value()
                    await self.wr(reg, before ^ (1 << k))
                    want = reg.get_mirrored_value() | dc
                    got = (await self.rd(reg)) | dc
                    if got != want:
                        self.fail(f"writing a {(before >> k & 1) ^ 1} to bit {k} of {reg.get_name()} "
                                  f"(was {before:#x}) read back {got & ~dc:#x}, not {want & ~dc:#x}")
