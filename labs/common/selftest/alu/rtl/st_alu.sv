// SELFTEST DESIGN -- not course material. DD105-A's selftest ALU, unchanged but
// for these comments: a small ALU with three planted bugs behind the course's
// run-time switch, so the selftest can prove the graders
// against a real build without waiting for a lab's design.
//
// op: 0 ADD, 1 SUB, 2 AND, 3 OR, 4 XOR, 5 SHL, 6 SHR, 7 PASS_B.
// carry is ADD's carry-out, SUB's borrow (a < b) and SHL's last bit out.
//
// The bug switch follows the contract labs/common/README.md describes:
//   no +BUG             the golden design; nothing printed
//   +BUG=<known id>     that bug on
//   +BUG=<unknown id>   $fatal
// This design also prints "DD105-BUG: <id> enabled", which a lab's design
// need not do; the selftest's Makefile sets BUG_CONFIRM to check it.
// Which bug is on, as a package variable, the way the router's faulty build
// keeps it. A testbench could read it (cocotb.packages.st_bug_pkg); check.py
// refuses one that does.
package st_bug_pkg;
  int unsigned bug_id = 0;
endpackage

module st_alu (
  input  logic       clk, rst_n,
  input  logic       in_valid,
  input  logic [2:0] op,
  input  logic [7:0] a, b,
  output logic       out_valid,
  output logic [7:0] result,
  output logic       carry, zero
);
  bit b01, b02, b03;
  initial begin
    string id;
    if ($value$plusargs("BUG=%s", id)) begin
      case (id)
        "B01": begin b01 = 1; st_bug_pkg::bug_id = 1; end   // SUB sets the borrow when a == b
        "B02": begin b02 = 1; st_bug_pkg::bug_id = 2; end   // zero looks at the low nibble only
        "B03": begin b03 = 1; st_bug_pkg::bug_id = 3; end   // ADD 5A + A5 gives 00
        default: $fatal(1, "DD105-BUG: unknown bug id '%s'", id);
      endcase
      $display("DD105-BUG: %s enabled", id);
    end
  end

  logic [8:0] r;
  always_comb begin
    case (op)
      3'd0: r = (b03 && a == 8'h5A && b == 8'hA5) ? 9'd0 : {1'b0, a} + {1'b0, b};
      3'd1: r = {(b01 ? (a <= b) : (a < b)), a - b};
      3'd2: r = {1'b0, a & b};
      3'd3: r = {1'b0, a | b};
      3'd4: r = {1'b0, a ^ b};
      3'd5: r = {1'b0, a} << b[2:0];
      3'd6: r = {1'b0, a >> b[2:0]};
      default: r = {1'b0, b};
    endcase
  end

  always_ff @(posedge clk or negedge rst_n)
    if (!rst_n) begin
      out_valid <= 1'b0; result <= '0; carry <= 1'b0; zero <= 1'b0;
    end else begin
      out_valid <= in_valid;
      if (in_valid) begin
        result <= r[7:0];
        carry  <= r[8];
        zero   <= b02 ? (r[3:0] == 4'd0) : (r[7:0] == 8'd0);
      end
    end
endmodule
