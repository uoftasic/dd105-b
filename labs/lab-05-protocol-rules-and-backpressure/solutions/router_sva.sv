// DD105-A Lab 05: assertions for the router's valid/ready rules.
//
// Plain SystemVerilog with no UVM in it, so any testbench can use it: this
// lab binds it into the router (router_sva_bind.sv), and a testbench in
// another language could bind it the same way and read the counters. The
// rule names (I1, O2, ...) are the ones in the router specification,
// docs/reference/router-spec.md, "Valid/ready rules".
//
// Every assertion has its own failure counter, n_<rule>, and n_fail is their
// sum; the top module passes n_fail to the scoreboard, which reports it at
// the end of the test. A failure also calls $error, which this simulator
// prints as "%Error: ... Assertion failed in ...". Its default error limit is
// 1, so the first failure ends the run unless the run has
// +verilator+error+limit+N; this lab's Makefile passes a large limit, so
// every failure prints and the counters keep counting.
//
// Every rule here is about normal operation, so every assertion is disabled
// while rst_n is 0 (disable iff (!rst_n)): a reset ends a handshake without
// one, and that isn't a broken rule.

// The rules that hold for each output separately: O1, O2 and O6. The top of
// the file instantiates this twice, once per output.
module router_sva_out (
  input logic       clk,
  input logic       rst_n,
  input logic       valid,
  input logic       ready,
  input logic [7:0] data,
  input logic       last
);
  int unsigned n_O1 = 0, n_O2 = 0, n_O6 = 0;
  int unsigned n_fail;
  assign n_fail = n_O1 + n_O2 + n_O6;

  // Beats of the current output packet already taken, for O6: 0 at the
  // start of a packet, 7 when the beat on offer is the packet's 8th.
  logic [3:0] beats;
  always @(posedge clk or negedge rst_n)
    if (!rst_n)               beats <= 4'd0;
    else if (valid && ready)  beats <= last ? 4'd0 : beats + 4'd1;

  // O1: once out_valid is 1, it stays 1 until the handshake.
  a_O1: assert property (@(posedge clk) disable iff (!rst_n)
                         valid && !ready |=> valid)
    else begin n_O1++; $error("O1: out_valid fell without a handshake"); end

  // O2: while out_valid is 1 and out_ready is 0, out_data and out_last hold.
  a_O2: assert property (@(posedge clk) disable iff (!rst_n)
                         valid && !ready |=> $stable(data) && $stable(last))
    else begin n_O2++; $error("O2: out_data or out_last changed while the beat waited"); end

  // O6: no output packet is longer than 8 beats, so the 8th beat is the last.
  a_O6: assert property (@(posedge clk) disable iff (!rst_n)
                         valid && ready && beats == 4'd7 |-> last)
    else begin n_O6++; $error("O6: an output packet is longer than 8 beats"); end
endmodule

module router_sva (
  input logic       clk,
  input logic       rst_n,
  input logic       in_valid,
  input logic       in_ready,
  input logic [7:0] in_data,
  input logic       in_last,
  input logic       out0_valid,
  input logic       out0_ready,
  input logic [7:0] out0_data,
  input logic       out0_last,
  input logic       out1_valid,
  input logic       out1_ready,
  input logic [7:0] out1_data,
  input logic       out1_last
);
  int unsigned n_I1 = 0, n_I2 = 0;
  int unsigned n_fail;
  assign n_fail = n_I1 + n_I2 + u_out0.n_fail + u_out1.n_fail;

  // ── input stream: the source's rules, so these check our own driver ───────
  // I1 (source): once in_valid is 1, it stays 1 until the handshake. Read it
  // as: in a cycle where a beat is offered and not taken (the antecedent,
  // left of |=>), valid is 1 in the next cycle too (the consequent).
  a_I1: assert property (@(posedge clk) disable iff (!rst_n)
                         in_valid && !in_ready |=> in_valid)
    else begin n_I1++; $error("I1: in_valid fell without a handshake"); end

  // I2 (source): while in_valid is 1 and in_ready is 0, in_data and in_last hold.
  a_I2: assert property (@(posedge clk) disable iff (!rst_n)
                         in_valid && !in_ready |=> $stable(in_data) && $stable(in_last))
    else begin n_I2++; $error("I2: in_data or in_last changed while the beat waited"); end

  // ── outputs: the router's promises ────────────────────────────────────────
  router_sva_out u_out0 (.clk(clk), .rst_n(rst_n), .valid(out0_valid), .ready(out0_ready),
                         .data(out0_data), .last(out0_last));
  router_sva_out u_out1 (.clk(clk), .rst_n(rst_n), .valid(out1_valid), .ready(out1_ready),
                         .data(out1_data), .last(out1_last));
endmodule
