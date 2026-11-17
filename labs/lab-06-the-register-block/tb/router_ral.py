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

Five pieces here are yours, marked TODO: the fields of STATUS, DROP_CNT,
LEVEL and the ROUTE registers, the adapter, and RegResetSeq.body() (Part
2); RouterRegPredictor.write() and RegBitBashSeq.body() (Part 3).
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
        # TODO (Part 2): the three fields, NOROUTE, FULL and OVERSIZE, as
        # IntEnReg makes them, with STATUS's access policy and volatility
        # from the specification's Register map.
        pass


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
        # TODO (Part 2): NOROUTE_CNT and FULL_CNT.
        pass


class LevelReg(uvm_reg):
    """LEVEL (0x14): how many beats each output's buffer holds, read-only."""

    def __init__(self, name="LEVEL"):
        super().__init__(name, 32)

    def build(self):
        # TODO (Part 2): LEVEL0 and LEVEL1.
        pass


class RouteReg(uvm_reg):
    """ROUTE0 to ROUTE3 (0x20 to 0x2C): one routing table entry each."""

    def __init__(self, name="ROUTE"):
        super().__init__(name, 32)

    def build(self):
        # TODO (Part 2): EN and PORT. The four ROUTE registers are all made
        # from this class.
        pass


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
        # TODO (Part 2): fill in t.write, t.addr (a number: int(rw.addr, 16))
        # and, for a write, t.wdata.
        return t

    def bus2reg(self, t, rw):
        """The finished transfer t, back into rw: the data written or read,
        and the status, ERROR_RESP when the transfer ended with PSLVERR."""
        # TODO (Part 2): rw.kind, rw.data (t.wdata for a write, t.rdata for
        # a read) and rw.status: uvm_resp_t.ERROR_RESP if t.slverr is 1,
        # otherwise uvm_resp_t.PASS_RESP.
        pass


# ── the predictor ────────────────────────────────────────────────────────────

class RouterRegPredictor(uvm_subscriber):
    """SystemVerilog UVM's uvm_reg_predictor, which pyuvm doesn't have. It
    subscribes to the APB monitor, so the mirror follows every transfer on
    the bus, whoever started it: the register model's own operations and
    the raw transfers of Labs 03 to 05 alike.

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
        # TODO (Part 3): as the class's comment says. Skip a transfer with
        # t.slverr set, or to an address with no register
        # (self.regs.by_addr(t.addr) is None). A write: count it in
        # self.writes, and reg.predict(t.wdata, kind=...) with the right
        # uvm_predict_e. A read: count it in self.reads; compare t.rdata
        # with reg.get_mirrored_value() outside the bits volatile_mask(reg)
        # gives, and for a mismatch count it in self.mismatches and report
        # it with self.logger.error(); then reg.predict(t.rdata, kind=...).
        # `make predict` shows what each kind does to the mirror.
        pass

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
        # TODO (Part 2): put the mirror at the reset values
        # (self.regs.map.reset("HARD")). Then, for each register in
        # self.regs.regs that has a field that isn't volatile
        # (f.is_volatile() for f in reg.get_fields()), read it with
        # self.rd(reg) and compare the value read with reset_value(reg)
        # outside the bits volatile_mask(reg) gives. Report a mismatch with
        # self.fail().
        pass


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
        # TODO (Part 3): for each register in self.regs.regs, and each bit k
        # of its reg.get_reg_size() that isn't in volatile_mask(reg), twice:
        # take the mirror (reg.get_mirrored_value()), write the register
        # with bit k of that value flipped (self.wr()), take the mirror
        # again, which the predictor has moved, then read the register back
        # (self.rd()) and compare the value read with the mirror you took
        # before the read, outside the volatile bits. Take it before the
        # read: once the read completes, the predictor puts the value read
        # in the mirror. Report a mismatch with self.fail().
        pass
