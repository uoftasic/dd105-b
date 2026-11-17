"""
DD105-B labs/ref probe: pyuvm 4.0.1's register prediction on tb/router_ral.py's
model, outside the simulator. Run it from labs/ref with the image's Python:

    python3 probes/pyuvm_probe.py
"""

import sys

sys.path.insert(0, "tb")

from pyuvm import uvm_predict_e  # noqa: E402

from router_ral import RouterRegs  # noqa: E402

regs = RouterRegs()
regs.map.reset("HARD")
s = regs.STATUS
s.predict(0x7, kind=uvm_predict_e.UVM_PREDICT_DIRECT)
print(f"1  STATUS mirror after predict(0x7, DIRECT):           {s.get_mirrored_value():#x}")
s.predict(0x1, kind=uvm_predict_e.UVM_PREDICT_WRITE)
print(f"2  then predict(0x1, WRITE), W1C clears bit 0:          {s.get_mirrored_value():#x}")
s.predict(0x6, kind=uvm_predict_e.UVM_PREDICT_READ)
print(f"3  then predict(0x6, READ) after reading 0x6:           {s.get_mirrored_value():#x}")
s.predict(0x6, kind=uvm_predict_e.UVM_PREDICT_DIRECT)
print(f"4  then predict(0x6, DIRECT):                           {s.get_mirrored_value():#x}")
c = regs.CTRL
c.predict(0x1, kind=uvm_predict_e.UVM_PREDICT_READ)
print(f"5  CTRL (RW) after predict(0x1, READ):                  {c.get_mirrored_value():#x}")
d = regs.DROP_CNT
d.predict(0x0302, kind=uvm_predict_e.UVM_PREDICT_DIRECT)
d.predict(0x0, kind=uvm_predict_e.UVM_PREDICT_WRITE)
print(f"6  DROP_CNT (WC) at 0x302, then predict(0x0, WRITE):    {d.get_mirrored_value():#x}")
d.predict(0x0302, kind=uvm_predict_e.UVM_PREDICT_READ)
print(f"7  then predict(0x302, READ):                           {d.get_mirrored_value():#x}")
i = regs.ID
i.predict(0x1234, kind=uvm_predict_e.UVM_PREDICT_WRITE)
print(f"8  ID (RO) after predict(0x1234, WRITE):                {i.get_mirrored_value():#x}")
