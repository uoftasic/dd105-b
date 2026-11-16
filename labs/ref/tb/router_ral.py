"""
DD105-B reference environment: the router's register model, on pyuvm 4.0.1's
register layer, and the adapter that turns its operations into APB items.

The fields and access policies are router-spec.md's "Register map". Two
pyuvm habits shape this file:

  - A map keys its registers by the address as hex() prints it ("0x8"), and
    looks a register up by the address string it was configured with, so
    every address below is written the way hex() writes it.
  - pyuvm has no predictor and no auto-predict, and a write or a read doesn't
    update the mirror. This environment checks every register read in the
    scoreboard's cycle model, so it uses the model only to reach the
    registers by name, and doesn't predict.
"""

from pyuvm import access_e, uvm_reg, uvm_reg_adapter, uvm_reg_block, uvm_reg_field, uvm_reg_map, uvm_resp_t

from router_agents import ApbItem

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


class RouterRegs(uvm_reg_block):
    """The router's ten registers, in one map at address 0."""

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


class ApbRegAdapter(uvm_reg_adapter):
    def reg2bus(self, rw):
        addr = int(rw.addr, 16) if isinstance(rw.addr, str) else rw.addr
        write = rw.kind == access_e.UVM_WRITE
        return ApbItem("ral", addr, rw.data if write else 0, write)

    def bus2reg(self, item, rw):
        rw.kind = access_e.UVM_WRITE if item.write else access_e.UVM_READ
        rw.data = item.data
        rw.status = uvm_resp_t.ERROR_RESP if item.slverr else uvm_resp_t.PASS_RESP
