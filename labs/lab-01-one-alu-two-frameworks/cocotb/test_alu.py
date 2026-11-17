"""
DD105-B Lab 01: the reference cocotb test for SimProc's ALU.

This is the reference solution to DD104 Lab 03's test_alu.py (in DD104,
labs/lab-03-three-blocks-before-the-processor/solutions/test_alu.py), with
only this docstring changed. If you finished DD104 Lab 03, your own
test_alu.py does the same job: copy it into this folder under another name
and run it with TB=, as the lab's README says.

    make cocotb                     this file, against the golden ALU
    make cocotb BUG=A03             the same, with bug A03 switched on
    make cocotb-all                 the golden ALU, then each of A01 to A03

t01 and t03 are DD104's. t02 drives all 393,216 legal vectors and checks the
value and both flags, keeping value mismatches and flag mismatches in
separate counts, which is the difference between "the ALU is broken" and
"the Z flag is broken".
"""

import cocotb
from cocotb.triggers import Timer

# The opcode encoding, straight out of the RTL's typedef.
ADD, SUB, OR, NAND, SHL, SHR = 0, 1, 2, 3, 4, 5
OPS = {ADD: "ADD", SUB: "SUB", OR: "OR", NAND: "NAND", SHL: "SHL", SHR: "SHR"}


def spec(op, a, b):
    """What the ALU is supposed to produce.  Returns (out, N, Z).

    This is a specification, written from the ISA and not from the RTL.  If you
    write it by reading the Verilog you have built a machine that agrees with
    the design about everything including its bugs, which is the single most
    common way a verification effort wastes six months.

    Two details worth having in your hands before you look at any waveform:

      * The shifts use only `B[1:0]`, so the shift amount is 0-3 and never
        more.  Nothing in the instruction set can ask for a bigger shift.
      * N and Z are functions of the *result*, not of the operands. N is
        literally bit 7 of the output; Z is 'the output is all zeroes'. There
        is no carry flag and no overflow flag on this machine.
    """
    if op == ADD:
        out = (a + b) & 0xFF
    elif op == SUB:
        out = (a - b) & 0xFF
    elif op == OR:
        out = a | b
    elif op == NAND:
        out = (~(a & b)) & 0xFF
    elif op == SHL:
        out = (a << (b & 3)) & 0xFF
    elif op == SHR:
        out = a >> (b & 3)
    else:
        out = 0
    return out, (out >> 7) & 1, int(out == 0)


async def alu(dut, op, a, b):
    """Drive one vector and read the three outputs back."""
    dut.ALUop.value = op
    dut.A.value = a
    dut.B.value = b
    await Timer(1, unit="ns")
    return int(dut.ALUout.value), int(dut.N.value), int(dut.Z.value)


# ─────────────────────────────────────────────────────────────────────────────
# 1.  One vector per operation, chosen on purpose
# ─────────────────────────────────────────────────────────────────────────────

@cocotb.test()
async def t01_one_vector_per_operation(dut):
    """Six vectors.  Every one of them uses two different operand values.

    That is the whole design of this test.  The natural directed vectors —
    `SUB(x, x)` for 'clear', `NAND(x, x)` for 'not' — are exactly the ones a
    swapped subtractor and a NAND-that-is-really-NOR both survive."""
    cases = [
        (ADD,  200, 60),
        (SUB,  200, 60),
        (OR,   0xF0, 0x0F),
        (NAND, 0xC3, 0x1D),
        (SHL,  0x21, 2),
        (SHR,  0xF8, 3),
    ]
    for op, a, b in cases:
        got = await alu(dut, op, a, b)
        want = spec(op, a, b)
        assert got == want, (
            f"{OPS[op]}(0x{a:02X}, 0x{b:02X}) gave out=0x{got[0]:02X} "
            f"N={got[1]} Z={got[2]}, expected out=0x{want[0]:02X} "
            f"N={want[1]} Z={want[2]}")
    dut._log.info(f"{len(cases)} directed vectors, all correct")


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Exhaustive — on the values
# ─────────────────────────────────────────────────────────────────────────────

@cocotb.test()
async def t02_every_vector_the_alu_can_be_given(dut):
    """All 393,216 legal vectors, checking the value AND both flags.

    Two buckets, reported separately.  That separation is the point of the
    test.  `0 value mismatches, 3840 flag mismatches on ADD` is a diagnosis:
    the adder is fine, the flag logic is not, and you have not opened a
    waveform yet.  One combined count of 3840 would have told you far less.

    And the factorisations are readable.  3840 = 15 x 256: fifteen non-zero
    results whose low nibble happens to be zero (0x10, 0x20, ... 0xF0), times
    256 operand pairs that produce each one.  255 on OR: the pairs where both
    low nibbles are zero, minus the one genuinely-zero case that is correct
    anyway.  When a failure count factors that cleanly, the factors are
    describing the bug."""
    bad_values = []
    bad_flags = []
    checked = 0

    for op in OPS:
        for a in range(256):
            for b in range(256):
                got = await alu(dut, op, a, b)
                want = spec(op, a, b)
                checked += 1
                if got[0] != want[0]:
                    bad_values.append((op, a, b, got[0], want[0]))
                if got[1:] != want[1:]:
                    bad_flags.append((op, a, b, got, want))

    def per_op(rows):
        d = {}
        for row in rows:
            d[OPS[row[0]]] = d.get(OPS[row[0]], 0) + 1
        return d

    v_counts, f_counts = per_op(bad_values), per_op(bad_flags)
    dut._log.info(f"{checked} vectors checked -- "
                  f"{len(bad_values)} value mismatches {v_counts or ''}, "
                  f"{len(bad_flags)} flag mismatches {f_counts or ''}")

    if bad_values:
        op, a, b, g, w = bad_values[0]
        raise AssertionError(
            f"{len(bad_values)} of {checked} vectors have the wrong VALUE: "
            f"{v_counts}.\n"
            f"  First one: {OPS[op]}(0x{a:02X}, 0x{b:02X}) = 0x{g:02X}, "
            f"expected 0x{w:02X}.")

    if bad_flags:
        op, a, b, g, w = bad_flags[0]
        raise AssertionError(
            f"Every value is correct, and {len(bad_flags)} of {checked} "
            f"vectors have the wrong FLAGS: {f_counts}.\n"
            f"  First one: {OPS[op]}(0x{a:02X}, 0x{b:02X}) = 0x{g[0]:02X} with "
            f"N={g[1]} Z={g[2]}, expected N={w[1]} Z={w[2]}.\n"
            f"  0 value mismatches and {len(bad_flags)} flag mismatches means "
            f"the arithmetic is right and the flag logic is not. Look at the "
            f"two `assign` lines at the bottom of the module, not at the case "
            f"statement above them.")


# ─────────────────────────────────────────────────────────────────────────────
# 3.  The two opcodes nobody specified
# ─────────────────────────────────────────────────────────────────────────────

@cocotb.test()
async def t03_the_undefined_opcodes(dut):
    """ALUop 6 and 7 are not in the enum.  They still do something.

    The `case` has a `default: ALUout = 8'h00;`, so opcodes 6 and 7 return
    zero — which also means N = 0 and Z = 1, a perfectly ordinary-looking
    'the answer was zero'.

    This test asserts the behaviour the RTL happens to have, which is a thing
    to do carefully and knowingly.  It is not in any specification. It is
    pinned here so that if somebody changes it — to an X, to a trap, to a
    passthrough — a test goes red and a human decides whether that was
    intended.  A test can be a record of a decision as well as a check of a
    requirement, and the comment is what tells the next reader which one it is.
    """
    for op in (6, 7):
        out, n, z = await alu(dut, op, 0xAB, 0xCD)
        assert (out, n, z) == (0, 0, 1), (
            f"ALUop {op} gave out=0x{out:02X} N={n} Z={z}, expected "
            f"out=0x00 N=0 Z=1 (the case default)")
    dut._log.info("opcodes 6 and 7 both return 0x00, with N=0 Z=1")
