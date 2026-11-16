"""
SELFTEST FIXTURES -- register models for regcheck.py, each broken in one way
except GoodRegs. Not course material.

    OverlapRegs   two fields of one register overlap: pyuvm raises AssertionError
    ZeroAddrRegs  a register configured at "0x00", which pyuvm's map keys as "0x0",
                  so its first access would raise KeyError
    GoodRegs      builds
"""

from pyuvm import uvm_reg, uvm_reg_block, uvm_reg_field, uvm_reg_map


class _Reg(uvm_reg):
    FIELDS = [("A", 0, 4), ("B", 4, 4)]

    def __init__(self, name="R"):
        super().__init__(name, 32)

    def build(self):
        for fname, lsb, size in self.FIELDS:
            f = uvm_reg_field(fname)
            f.configure(self, size, lsb, "RW", False, 0)
            setattr(self, fname, f)


class _OverlapReg(_Reg):
    FIELDS = [("A", 0, 4), ("B", 2, 4)]


class _Block(uvm_reg_block):
    REG, ADDR = _Reg, "0x4"

    def __init__(self, name="st_regs"):
        super().__init__(name)
        self.map = uvm_reg_map("map")
        self.map.configure(self, 0)
        self.R = self.REG("R")
        self.R.configure(self, self.ADDR, "", False, False)
        self.map.add_reg(self.R, "0x0", "RW")


class GoodRegs(_Block):
    pass


class OverlapRegs(_Block):
    REG = _OverlapReg


class ZeroAddrRegs(_Block):
    ADDR = "0x00"
