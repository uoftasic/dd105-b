// DD105-B guide example, "Regressions and seeds": the design.
//
// A 4-bit counter that counts up on inc, goes back to 0 on clr (clr wins),
// and stops at 15. One planted bug, chosen at run time with +BUG=wrap: at 15,
// inc wraps the counter to 0.

module satcnt (
  input  logic       clk,
  input  logic       rst_n,
  input  logic       inc,
  input  logic       clr,
  output logic [3:0] count
);
  bit    bug_wrap;
  string bug;
  initial begin
    if (!$value$plusargs("BUG=%s", bug)) bug = "none";
    bug_wrap = (bug == "wrap");
  end

  always_ff @(posedge clk or negedge rst_n)
    if (!rst_n)                          count <= 4'd0;
    else if (clr)                        count <= 4'd0;
    else if (inc && count != 4'd15)      count <= count + 4'd1;
    else if (inc && bug_wrap)            count <= 4'd0;     // the planted bug
endmodule
