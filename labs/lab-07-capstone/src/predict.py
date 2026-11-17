"""
DD105-B Lab 06: what predict() does to a register's mirror.

    make predict

Builds your register model, RouterRegs in tb/router_ral.py, outside the
simulator, as `make regcheck` does, puts its mirror at the reset values,
and then calls predict() on four of its registers the way a predictor
would after a write or a read, printing the mirror after each call. Nothing
here touches the router: the mirror is only what the model believes the
register holds.

  UVM_PREDICT_WRITE    the value was written: each field takes what its
                       access policy gives it
  UVM_PREDICT_READ     the value was read: what pyuvm then does depends on
                       the field's policy
  UVM_PREDICT_DIRECT   take the value as it is
"""

from pyuvm import uvm_predict_e

from router_ral import RouterRegs

WRITE, READ, DIRECT = (uvm_predict_e.UVM_PREDICT_WRITE, uvm_predict_e.UVM_PREDICT_READ,
                       uvm_predict_e.UVM_PREDICT_DIRECT)
NAME = {WRITE: "UVM_PREDICT_WRITE", READ: "UVM_PREDICT_READ", DIRECT: "UVM_PREDICT_DIRECT"}


def policies(reg):
    """'W1C' if every field has that policy, or each field's: 'EN RW, PORT RW'."""
    acc = {f.get_access() for f in reg.get_fields()}
    if len(acc) == 1:
        return acc.pop()
    return ", ".join(f"{f.get_name()} {f.get_access()}" for f in reg.get_fields())


def main():
    regs = RouterRegs()
    regs.map.reset("HARD")
    steps = [
        (regs.STATUS, [(0x7, DIRECT), (0x1, WRITE), (0x6, READ), (0x6, DIRECT)]),
        (regs.DROP_CNT, [(0x302, DIRECT), (0x5, WRITE), (0x302, DIRECT), (0x302, READ)]),
        (regs.CTRL, [(0x1, WRITE), (0x1, READ)]),
        (regs.ID, [(0x1234, WRITE)]),
    ]
    for reg, calls in steps:
        if not reg.get_fields():
            print(f"{reg.get_name()} has no fields yet, so its mirror is always 0x0 (Part 2)")
            continue
        print(f"{reg.get_name()} ({policies(reg)}), after the reset: {reg.get_mirrored_value():#x}")
        for value, kind in calls:
            reg.predict(value, kind=kind)
            call = f"predict({value:#x}, {NAME[kind]})"
            print(f"  then {call:<36} {reg.get_mirrored_value():#x}")


if __name__ == "__main__":
    main()
