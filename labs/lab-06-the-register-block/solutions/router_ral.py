"""
DD105-B Lab 06: the router's register layer, on pyuvm 4.0.1.

  IdReg ... RouteReg  the router's registers, one class each (the four
                      ROUTE registers share RouteReg), with the fields of
                      router-spec.md's "Register map"
  RouterRegs          the register model: the ten registers in one map
  ApbRegAdapter       a register operation to one ApbItem, and back (Part 2)
  RouterRegPredictor  keeps the model's mirror in step with every transfer
                      the APB monitor sees, and checks every read (Part 3)
  RegSeq              what the two register sequences share
  RegResetSeq         reads every register it can check and compares it
                      with its reset value (Part 2)
  RegBitBashSeq       writes every bit outside a volatile field both ways
                      and reads it back (Part 3)

pyuvm has the classes for the model, the map and the adapter, and nothing
that keeps the mirror up to date: its uvm_reg_predictor class is empty,
auto-predict is off, a register has no mirror(), and none of SystemVerilog
UVM's built-in register sequences is there. So this lab writes the
predictor and the two sequences.

This file imports nothing from the course venv, so `make regcheck`, and the
graders before every verdict, can build RouterRegs with the image's own
Python.

This is the reference solution: the fields of STATUS, DROP_CNT, LEVEL and
the ROUTE registers, the adapter, the predictor's write() and both
sequences' body() are filled in, as Parts 2 and 3 of the lab ask.
"""

from pyuvm import (access_e, check_t, path_t, uvm_predict_e, uvm_reg, uvm_reg_adapter,
                   uvm_reg_block, uvm_reg_field, uvm_reg_map, uvm_resp_t, uvm_sequence,
                   uvm_subscriber)

# The ten addresses of the register map (router-spec.md). Every other one of
# the 256 is a bad address, which gets PSLVERR.
ADDRS = (0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x20, 0x24, 0x28, 0x2C)


def good_addr(a):
    """True for the ten addresses that have a register."""
    return a in ADDRS


# ── the registers ────────────────────────────────────────────────────────────
# Each register's build() makes its fields and configures each one:
#
#   field.configure(parent, size, lsb_pos, access, is_volatile, reset)
#
# with the field's width and lowest bit, its access policy ("RO", "RW",
# "W1C", "WC", ...), whether the router changes it on its own (volatile), and
# its reset value. pyuvm checks each field against the one configured just
# before it, so configure them from bit 0 up. uvm_reg.configure() calls
# build(), so the fields exist once RouterRegs has configured the register.

class IdReg(uvm_reg):
    """ID (0x00): the design's ID, read-only."""

    def __init__(self, name="ID"):
        super().__init__(name, 32)

    def build(self):
        self.ID = uvm_reg_field("ID")
        self.ID.configure(self, 32, 0, "RO", False, 0xD105_0001)


class CtrlReg(uvm_reg):
    """CTRL (0x04): EN, which opens the input."""

    def __init__(self, name="CTRL"):
        super().__init__(name, 32)

    def build(self):
        self.EN = uvm_reg_field("EN")
        self.EN.configure(self, 1, 0, "RW", False, 0)


class StatusReg(uvm_reg):
    """STATUS (0x08): NOROUTE, FULL and OVERSIZE, which the router sets and a
    write of 1 clears."""

    def __init__(self, name="STATUS"):
        super().__init__(name, 32)

    def build(self):
        self.NOROUTE = uvm_reg_field("NOROUTE")
        self.NOROUTE.configure(self, 1, 0, "W1C", True, 0)
        self.FULL = uvm_reg_field("FULL")
        self.FULL.configure(self, 1, 1, "W1C", True, 0)
        self.OVERSIZE = uvm_reg_field("OVERSIZE")
        self.OVERSIZE.configure(self, 1, 2, "W1C", True, 0)


class IntEnReg(uvm_reg):
    """INT_EN (0x0C): one interrupt enable per STATUS bit."""

    def __init__(self, name="INT_EN"):
        super().__init__(name, 32)

    def build(self):
        self.NOROUTE = uvm_reg_field("NOROUTE")
        self.NOROUTE.configure(self, 1, 0, "RW", False, 0)
        self.FULL = uvm_reg_field("FULL")
        self.FULL.configure(self, 1, 1, "RW", False, 0)
        self.OVERSIZE = uvm_reg_field("OVERSIZE")
        self.OVERSIZE.configure(self, 1, 2, "RW", False, 0)


class DropCntReg(uvm_reg):
    """DROP_CNT (0x10): the two drop counters, which the router counts and any
    write clears."""

    def __init__(self, name="DROP_CNT"):
        super().__init__(name, 32)

    def build(self):
        self.NOROUTE_CNT = uvm_reg_field("NOROUTE_CNT")
        self.NOROUTE_CNT.configure(self, 8, 0, "WC", True, 0)
        self.FULL_CNT = uvm_reg_field("FULL_CNT")
        self.FULL_CNT.configure(self, 8, 8, "WC", True, 0)


class LevelReg(uvm_reg):
    """LEVEL (0x14): how many beats each output's buffer holds, read-only."""

    def __init__(self, name="LEVEL"):
        super().__init__(name, 32)

    def build(self):
        self.LEVEL0 = uvm_reg_field("LEVEL0")
        self.LEVEL0.configure(self, 5, 0, "RO", True, 0)
        self.LEVEL1 = uvm_reg_field("LEVEL1")
        self.LEVEL1.configure(self, 5, 8, "RO", True, 0)


class RouteReg(uvm_reg):
    """ROUTE0 to ROUTE3 (0x20 to 0x2C): one routing table entry each."""

    def __init__(self, name="ROUTE"):
        super().__init__(name, 32)

    def build(self):
        self.EN = uvm_reg_field("EN")
        self.EN.configure(self, 1, 0, "RW", False, 0)
        self.PORT = uvm_reg_field("PORT")
        self.PORT.configure(self, 1, 1, "RW", False, 0)


class RouterRegs(uvm_reg_block):
    """The router's ten registers in one map, `map`. Each register is an
    attribute (regs.CTRL, regs.STATUS, ...; the routing table is
    regs.ROUTE[0] to regs.ROUTE[3]), and `regs` lists all ten in address
    order.

    pyuvm keys a map's registers by the address as Python's hex() prints it
    ("0x8"), and looks a register up by the string it was configured with,
    so each address is given as hex(addr): "0x08" would raise KeyError at
    the register's first access."""

    def __init__(self, name="regs"):
        super().__init__(name)
        self.map = uvm_reg_map("map")
        self.map.configure(self, 0)
        self.ID = self.add(IdReg("ID"), 0x00, "RO")
        self.CTRL = self.add(CtrlReg("CTRL"), 0x04)
        self.STATUS = self.add(StatusReg("STATUS"), 0x08)
        self.INT_EN = self.add(IntEnReg("INT_EN"), 0x0C)
        self.DROP_CNT = self.add(DropCntReg("DROP_CNT"), 0x10)
        self.LEVEL = self.add(LevelReg("LEVEL"), 0x14, "RO")
        self.ROUTE = [self.add(RouteReg(f"ROUTE{n}"), 0x20 + 4 * n) for n in range(4)]
        self.regs = [self.ID, self.CTRL, self.STATUS, self.INT_EN, self.DROP_CNT, self.LEVEL,
                     *self.ROUTE]

    def add(self, reg, addr, rights="RW"):
        reg.configure(self, hex(addr), "", False, False)
        self.map.add_reg(reg, "0x0", rights)
        return reg

    def by_addr(self, addr):
        """The register at byte address `addr`, or None for a bad address."""
        if not good_addr(addr):
            return None
        return self.map.get_registers(as_dict=True)[hex(addr)]


def field_mask(f):
    """The bits of field f in its register."""
    return ((1 << f.get_n_bits()) - 1) << f.get_lsb_pos()


def volatile_mask(reg):
    """The bits of reg's volatile fields, which the router changes on its
    own, so a read can't be compared with the mirror there."""
    m = 0
    for f in reg.get_fields():
        if f.is_volatile():
            m |= field_mask(f)
    return m


def reset_value(reg):
    """The value reg holds after a reset: each field's reset value in its place."""
    return sum(f.get_reset() << f.get_lsb_pos() for f in reg.get_fields())


# ── the adapter ──────────────────────────────────────────────────────────────

class ApbRegAdapter(uvm_reg_adapter):
    """The map calls reg2bus() with each register operation, starts the
    ApbItem it returns on the APB sequencer, and when the driver has
    finished the transfer calls bus2reg() with the same item. The value
    bus2reg() puts in rw.status is what the register's read() or write()
    returns."""

    def reg2bus(self, rw):
        """One ApbItem for the operation rw: rw.kind is access_e.UVM_WRITE or
        UVM_READ, rw.addr is the address as the string the register was
        configured with ("0x8"), and rw.data is the value to write."""
        # Imported here, not at the top: router_agents imports pyvsc, and
        # `make regcheck` builds this file's model with the image's own
        # Python, which has no pyvsc.
        from router_agents import ApbItem
        t = ApbItem.create("reg")
        t.write = rw.kind == access_e.UVM_WRITE
        t.addr = int(rw.addr, 16)
        t.wdata = rw.data if t.write else 0
        return t

    def bus2reg(self, t, rw):
        """The finished transfer t, back into rw: the data written or read,
        and the status, ERROR_RESP when the transfer ended with PSLVERR."""
        rw.kind = access_e.UVM_WRITE if t.write else access_e.UVM_READ
        rw.data = t.wdata if t.write else t.rdata
        rw.status = uvm_resp_t.ERROR_RESP if t.slverr else uvm_resp_t.PASS_RESP


# ── the predictor ────────────────────────────────────────────────────────────

class RouterRegPredictor(uvm_subscriber):
    """The course's stand-in for SystemVerilog UVM's uvm_reg_predictor
    (pyuvm's class of that name is empty). It subscribes to the APB monitor,
    so the mirror follows every transfer on the bus, whoever started it:
    the register model's own operations, and the raw transfers of Lab 04's
    steps and Lab 05's sequence alike.

      a write   predict(value, UVM_PREDICT_WRITE): each field takes the
                value its access policy gives (RW the value written, W1C
                clears the bits written as 1, WC clears, RO keeps its value)
      a read    compare the value read with the mirror outside the volatile
                fields (reserved bits included, which must read 0, as the
                mirror has them), then predict(value, UVM_PREDICT_DIRECT)

    A transfer that ended with PSLVERR, or to an address with no register,
    is skipped: there is no register to predict, and the scoreboard checks
    those. The env gives the predictor the model in its connect_phase."""

    def build_phase(self):
        self.regs = None            # the register model; the env sets it
        self.reads = 0              # reads checked against the mirror
        self.writes = 0             # writes predicted
        self.mismatches = 0         # reads that didn't match

    def write(self, t):
        """One transfer the APB monitor saw complete (an ApbItem, with the
        cycle it completed in)."""
        if t.slverr:
            return
        reg = self.regs.by_addr(t.addr)
        if reg is None:
            return
        if t.write:
            self.writes += 1
            reg.predict(t.wdata, kind=uvm_predict_e.UVM_PREDICT_WRITE)
            return
        self.reads += 1
        dc = volatile_mask(reg)
        want = reg.get_mirrored_value()
        if (t.rdata | dc) != (want | dc):
            self.mismatches += 1
            self.logger.error(f"[RAL] {reg.get_name()} read {t.rdata:#x} in cycle {t.cycle}; "
                              f"the mirror holds {want:#x}")
        reg.predict(t.rdata, kind=uvm_predict_e.UVM_PREDICT_DIRECT)

    def report_phase(self):
        self.logger.info(f"[RAL] {self.reads} register reads checked against the mirror, "
                         f"{self.writes} writes predicted; {self.mismatches} mismatches")


# ── the register sequences ───────────────────────────────────────────────────

class RegSeq(uvm_sequence):
    """What the two register sequences share. They run on no sequencer: the
    map sends each operation to the APB sequencer itself. A pyuvm sequence
    has no logger, so they report through the logger of a component, which
    BaseTest counts; the virtual sequence passes the env's. When one ends,
    it logs one line with what it read and how many mismatches it found."""

    def __init__(self, name, regs, logger):
        super().__init__(name)
        self.regs = regs
        self.logger = logger
        self.n_reads = 0
        self.n_writes = 0
        self.errors = 0
        self.read_names = []        # the registers read, each once, in order

    def fail(self, msg):
        """Report one mismatch."""
        self.errors += 1
        self.logger.error(f"[{self.get_name()}] {msg}")

    async def rd(self, reg):
        """Read reg through the model; returns the value read."""
        status, value = await reg.read(self.regs.map, path_t.FRONTDOOR, check_t.NO_CHECK)
        self.n_reads += 1
        if reg.get_name() not in self.read_names:
            self.read_names.append(reg.get_name())
        if status != uvm_resp_t.PASS_RESP:
            self.fail(f"reading {reg.get_name()} returned {status.name}")
        return value

    async def wr(self, reg, value):
        """Write value to reg through the model."""
        status = await reg.write(value, self.regs.map, path_t.FRONTDOOR, check_t.NO_CHECK)
        self.n_writes += 1
        if status != uvm_resp_t.PASS_RESP:
            self.fail(f"writing {value:#x} to {reg.get_name()} returned {status.name}")

    async def post_body(self):
        """pyuvm calls this when body() returns."""
        names = ", ".join(self.read_names)
        self.logger.info(f"[{self.get_name()}] {self.n_writes} writes and {self.n_reads} reads "
                         f"of {len(self.read_names)} registers ({names}); "
                         f"{self.errors} mismatches")


class RegResetSeq(RegSeq):
    """pyuvm's stand-in for uvm_reg_hw_reset_seq. Start it while the router
    still holds its reset values, before anything has written a register.
    It puts the mirror at the reset values, then reads every register that
    has a field it can check, one that isn't volatile, and compares the
    value read with the register's reset value outside its volatile fields.
    A register whose fields are all volatile is skipped, as UVM's sequence
    skips it."""

    async def body(self):
        self.regs.map.reset("HARD")
        for reg in self.regs.regs:
            if all(f.is_volatile() for f in reg.get_fields()):
                continue
            dc = volatile_mask(reg)
            want = reset_value(reg)
            got = await self.rd(reg)
            if (got | dc) != (want | dc):
                self.fail(f"{reg.get_name()} reads {got:#x} after reset; its reset value is {want:#x}")


class RegBitBashSeq(RegSeq):
    """pyuvm's stand-in for uvm_reg_bit_bash_seq. For every register, and
    every bit of it that isn't in a volatile field: write the register with
    that bit flipped from what the mirror holds, take the mirror (which the
    predictor has moved by the field's policy), read the register back, and
    compare the two outside the volatile fields. Each bit is flipped twice,
    so it is written both ways. A read-write bit follows the write; a
    read-only bit, and every reserved bit, keeps its value. Run it with no
    traffic: CTRL.EN and the routes change as it goes, and every write to
    DROP_CNT clears the counters."""

    async def body(self):
        for reg in self.regs.regs:
            dc = volatile_mask(reg)
            for k in range(reg.get_reg_size()):
                if dc >> k & 1:
                    continue
                for _ in range(2):
                    before = reg.get_mirrored_value()
                    await self.wr(reg, before ^ (1 << k))
                    # The predictor has already seen the write: the monitor
                    # reports a transfer in the cycle it completes, and
                    # write() returns at the edge after it. Take the mirror
                    # now, because once the read completes the predictor
                    # puts the value read in it.
                    want = reg.get_mirrored_value()
                    got = await self.rd(reg)
                    if (got | dc) != (want | dc):
                        self.fail(f"writing a {(before >> k & 1) ^ 1} to bit {k} of {reg.get_name()} "
                                  f"(was {before:#x}) read back {got:#x}, not {want:#x}")
