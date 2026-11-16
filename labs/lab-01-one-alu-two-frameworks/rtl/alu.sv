// DD105-A Lab 01: SimProc's ALU, with DD104's three ALU bugs behind a
// run-time switch.
//
// The module is `ALU` from DD104's labs/common/rtl/simproc_system.sv, lines
// 790 to 823, which is the SimProc RTL at github.com/uoftasic/simproc commit
// 1d97772. Its name and ports are unchanged, so a cocotb test written for it
// in DD104 Lab 03 runs against this file as it is. Three lines are changed,
// each into a choice between the golden expression and a bug (they're marked
// "bug A0n"), and the initial block at the bottom is new. With no +BUG the
// module computes exactly what DD104's golden ALU does.
//
// The bugs are DD104's B01 to B03, renamed so they can't be mistaken for the
// router's B01 to B15:
//
//   A01  SUB computes B - A instead of A - B     (DD104: B01_sub_operands_swapped)
//   A02  NAND computes ~(A | B), which is NOR    (DD104: B02_nand_is_nor)
//   A03  Z looks only at ALUout[3:0]             (DD104: B03_zero_flag_low_nibble)
//
// The switch works the same way as the router's faulty build
// (labs/common/inject.py), so one build holds the golden ALU and all three
// broken ones, and the simulator's command line picks one at time 0:
//
//   no +BUG, or +BUG=none   the golden ALU
//   +BUG=A01, A02 or A03    that bug on
//   any other +BUG          $fatal at time 0, so a typo can't run the golden ALU
//   +BUG_ECHO               also print which bug is on (the graders never pass it)
//
// Which bug is on lives in a package variable, as in the router. The waves
// leave packages out, and `make check` refuses a testbench that reads it.

package alu_bug_pkg;
  int unsigned bug_id = 0;
  // Icarus 14 can't assign alu_bug_pkg::bug_id from inside a module, so the
  // switch sets it through this function instead.
  function automatic void select(int unsigned id);
    bug_id = id;
  endfunction
endpackage

module ALU (
    input  logic    [2:0]   ALUop,
    input  logic    [7:0]   A,
    input  logic    [7:0]   B,
    output logic            N,
    output logic            Z,
    output logic    [7:0]   ALUout
);

    typedef enum logic [2:0] {
        ADD  = 3'b000,
        SUB  = 3'b001,
        OR   = 3'b010,
        NAND = 3'b011,
        SHL  = 3'b100,
        SHR  = 3'b101
    } aluop_t;

    always @ (*) begin
        case(ALUop)
            ADD:        ALUout = A + B;
            SUB:        ALUout = (alu_bug_pkg::bug_id == 1) ? (B - A) : (A - B);      // bug A01
            OR:         ALUout = A | B;
            NAND:       ALUout = (alu_bug_pkg::bug_id == 2) ? ~(A | B) : ~(A & B);    // bug A02
            SHL:        ALUout = A << B[1:0];
            SHR:        ALUout = A >> B[1:0];

            default:    ALUout = 8'h00;
        endcase
    end

    assign N = ALUout[7];
    assign Z = (alu_bug_pkg::bug_id == 3) ? ~(|ALUout[3:0]) : ~(|ALUout);         // bug A03

    // ---- The bug switch (DD105-A; not part of SimProc) ---------------------
    // Reads +BUG once, at time 0. It prints nothing unless +BUG_ECHO is given
    // too, so a run's log doesn't say which bug it ran.
    initial begin : bug_switch
        string arg;
        int    id;
        id = 0;
        if ($value$plusargs("BUG=%s", arg)) begin
            if      (arg == "none") id = 0;
            else if (arg == "A01")  id = 1;
            else if (arg == "A02")  id = 2;
            else if (arg == "A03")  id = 3;
            else $fatal(1, "ALU: +BUG=%s is not a bug in this build (A01 to A03, or none)", arg);
        end
        alu_bug_pkg::select(id);
        if ($test$plusargs("BUG_ECHO")) begin
            if (id != 0) $display("ALU: bug A%02d switched on", id);
            else         $display("ALU: no bug switched on, this is the golden ALU");
        end
    end
endmodule
