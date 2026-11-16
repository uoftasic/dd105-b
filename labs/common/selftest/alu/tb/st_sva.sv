// SELFTEST -- the zero flag is checked ONLY here, by an assertion bound into
// the design, so bug B02 can be caught by nothing but a failing assertion.
// That proves BaseTest reads the assertion's counter through cocotb
// (u_sva.n_fail), and that verdict.py counts "Assertion failed in ..." as a
// check. DD105-A's selftest assertion, with the counter added.
module st_alu_sva (
  input logic       clk, rst_n, out_valid, zero,
  input logic [7:0] result
);
  int unsigned n_fail = 0;
  a_zero_flag: assert property (@(posedge clk) disable iff (!rst_n)
                                out_valid |-> zero == (result == 8'd0))
    else begin n_fail++; $error("zero flag is %0b for result %02h", zero, result); end
endmodule

bind st_alu st_alu_sva u_sva (.clk(clk), .rst_n(rst_n), .out_valid(out_valid),
                              .zero(zero), .result(result));
