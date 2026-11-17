// DD105-B guide example, "Assertions for interface rules": the checker.
//
// Rules S1 to S3 of stage.sv as concurrent assertions, and the bind that puts
// one copy of this module inside every stage, as u_sva. The stage's RTL
// doesn't change.
//
// Each assertion counts its failures, and n_fail is their sum. Python reads
// it through the design as cocotb.top.u_sva.n_fail, which is where the
// course's BaseTest looks. A failure also calls $error. Verilator's default
// error limit is 1, so the first failing assertion ends the run, unless the
// run raises the limit with +verilator+error+limit+N; labs/common/pyuvm.mk
// does that for every folder that sets SVA_SRCS.
//
// n_tried counts the cycles in which S1 and S2 had something to check: a beat
// on the output that the sink didn't take. If it stays 0, those two
// assertions passed without ever being tried. c_S1 asks the same question
// with a cover property, whose pass statement counts n_covered.

module stage_sva (
  input logic       clk,
  input logic       rst_n,
  input logic       in_valid,
  input logic       in_ready,
  input logic       out_valid,
  input logic       out_ready,
  input logic [7:0] out_data
);
  int unsigned n_S1 = 0, n_S2 = 0, n_S3 = 0;
  int unsigned n_tried = 0;
  int unsigned n_covered = 0;
  int unsigned n_fail;
  assign n_fail = n_S1 + n_S2 + n_S3;

  always @(posedge clk)
    if (rst_n && out_valid && !out_ready) n_tried++;

  // S1: in a cycle where a beat waits (the antecedent, left of |=>), out_valid
  // is still 1 in the next cycle (the consequent).
  a_S1: assert property (@(posedge clk) disable iff (!rst_n)
                         out_valid && !out_ready |=> out_valid)
    else begin n_S1++; $error("S1: out_valid fell without a handshake"); end

  // S2: in the same cycles, out_data in the next cycle equals out_data now.
  a_S2: assert property (@(posedge clk) disable iff (!rst_n)
                         out_valid && !out_ready |=> $stable(out_data))
    else begin n_S2++; $error("S2: out_data changed while the beat waited"); end

  // S3 is about one cycle, so its consequent is checked in the same cycle (|->).
  a_S3: assert property (@(posedge clk) disable iff (!rst_n)
                         !out_valid |-> in_ready)
    else begin n_S3++; $error("S3: the stage is empty and in_ready is 0"); end

  // The same question as n_tried, asked with cover property.
  c_S1: cover property (@(posedge clk) disable iff (!rst_n) out_valid && !out_ready)
    n_covered++;
endmodule

bind stage stage_sva u_sva (
  .clk(clk), .rst_n(rst_n),
  .in_valid(in_valid), .in_ready(in_ready),
  .out_valid(out_valid), .out_ready(out_ready), .out_data(out_data)
);
