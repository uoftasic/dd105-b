// DD105-A Lab 07: assertions for the router's valid/ready rules, and for
// the rules about reset.
//
// Plain SystemVerilog with no UVM in it, so any testbench can use it: this
// lab binds it into the router (router_sva_bind.sv), and a testbench in
// another language could bind it the same way and read the counters. The
// rule names (I1, O2, ...) are the ones in the router specification,
// docs/reference/router-spec.md, "Valid/ready rules", "APB rules" and
// "Reset".
//
// Every assertion has its own failure counter, n_<rule>, and n_fail is their
// sum; the top module passes n_fail to the scoreboard, which reports it at
// the end of the test. A failure also calls $error, which this simulator
// prints as "%Error: ... Assertion failed in ...". Its default error limit is
// 1, so the first failure ends the run unless the run has
// +verilator+error+limit+N; this lab's Makefile passes a large limit, so
// every failure prints and the counters keep counting.
//
// Lab 05's rules (I1, I2, O1, O2, O6) are about normal operation, so each is
// disabled while rst_n is 0 (disable iff (!rst_n)): a reset ends a handshake
// without one, and that isn't a broken rule. The rules about reset itself
// (I7, the first half of O4 and of A4, and the Reset table's values) say
// what holds while rst_n is 0, so they are checked at every rising edge,
// reset cycles included, with no disable iff. The second half of O4 is
// about the cycles after a reset, so it keeps the disable iff.
//
// This is Lab 05's file. Lab 07 adds the APB signals and irq to the ports,
// because the Reset table names them, and the input handshake to the
// per-output module, for the second half of O4.
//
// This is the reference solution: the reset rules are filled in.

// The rules that hold for each output separately: O1, O2, O4 and O6. The top
// of the file instantiates this twice, once per output.
module router_sva_out (
  input logic       clk,
  input logic       rst_n,
  input logic       in_hs,     // Lab 07: a handshake on the input stream
  input logic       valid,
  input logic       ready,
  input logic [7:0] data,
  input logic       last
);
  int unsigned n_O1 = 0, n_O2 = 0, n_O4_rst = 0, n_O4_after = 0, n_O6 = 0;
  int unsigned n_fail;
  assign n_fail = n_O1 + n_O2 + n_O4_rst + n_O4_after + n_O6;

  // Beats of the current output packet already taken, for O6: 0 at the
  // start of a packet, 7 when the beat on offer is the packet's 8th.
  logic [3:0] beats;
  always @(posedge clk or negedge rst_n)
    if (!rst_n)               beats <= 4'd0;
    else if (valid && ready)  beats <= last ? 4'd0 : beats + 4'd1;

  // seen2 is 1 in cycle t if the input stream had a handshake in some cycle
  // up to t-2 since the last reset. A beat reaches an output no sooner than
  // two cycles after its input handshake (rule O8), so until then out_valid
  // must be 0.
  logic seen1, seen2;
  always @(posedge clk or negedge rst_n)
    if (!rst_n) begin
      seen1 <= 1'b0;
      seen2 <= 1'b0;
    end else begin
      seen1 <= seen1 | in_hs;
      seen2 <= seen1;
    end

  // O1: once out_valid is 1, it stays 1 until the handshake.
  a_O1: assert property (@(posedge clk) disable iff (!rst_n)
                         valid && !ready |=> valid)
    else begin n_O1++; $error("O1: out_valid fell without a handshake"); end

  // O2: while out_valid is 1 and out_ready is 0, out_data and out_last hold.
  a_O2: assert property (@(posedge clk) disable iff (!rst_n)
                         valid && !ready |=> $stable(data) && $stable(last))
    else begin n_O2++; $error("O2: out_data or out_last changed while the beat waited"); end

  // O4, first half: out_valid is 0 while rst_n is 0.
  a_O4_rst: assert property (@(posedge clk) !rst_n |-> !valid)
    else begin n_O4_rst++; $error("O4: out_valid is 1 during reset"); end

  // O4, second half: out_valid stays 0 after reset until a beat accepted
  // after the reset could have reached the output.
  a_O4_after: assert property (@(posedge clk) disable iff (!rst_n)
                               !seen2 |-> !valid)
    else begin n_O4_after++; $error("O4: out_valid is 1 before any beat accepted since reset could arrive"); end

  // O6: no output packet is longer than 8 beats, so the 8th beat is the last.
  a_O6: assert property (@(posedge clk) disable iff (!rst_n)
                         valid && ready && beats == 4'd7 |-> last)
    else begin n_O6++; $error("O6: an output packet is longer than 8 beats"); end
endmodule

module router_sva (
  input logic        clk,
  input logic        rst_n,
  input logic        psel,      // Lab 07: the APB port and irq, for the reset rules
  input logic        penable,
  input logic        pwrite,
  input logic [7:0]  paddr,
  input logic [31:0] pwdata,
  input logic [31:0] prdata,
  input logic        pready,
  input logic        pslverr,
  input logic        irq,
  input logic        in_valid,
  input logic        in_ready,
  input logic [7:0]  in_data,
  input logic        in_last,
  input logic        out0_valid,
  input logic        out0_ready,
  input logic [7:0]  out0_data,
  input logic        out0_last,
  input logic        out1_valid,
  input logic        out1_ready,
  input logic [7:0]  out1_data,
  input logic        out1_last
);
  int unsigned n_I1 = 0, n_I2 = 0;
  // Lab 07: the rules about reset. The R counters are the Reset table's rows.
  int unsigned n_I7 = 0, n_A4 = 0;
  int unsigned n_R_pready = 0, n_R_pslverr = 0, n_R_prdata = 0, n_R_irq = 0;
  int unsigned n_fail;
  assign n_fail = n_I1 + n_I2 + n_I7 + n_A4
                + n_R_pready + n_R_pslverr + n_R_prdata + n_R_irq
                + u_out0.n_fail + u_out1.n_fail;

  wire in_hs = in_valid && in_ready;   // Lab 07: for O4's second half

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

  // I7: in_ready is 0 while rst_n is 0.
  a_I7: assert property (@(posedge clk) !rst_n |-> !in_ready)
    else begin n_I7++; $error("I7: in_ready is 1 during reset"); end

  // ── outputs: the router's promises ────────────────────────────────────────
  router_sva_out u_out0 (.clk(clk), .rst_n(rst_n), .in_hs(in_hs), .valid(out0_valid),
                         .ready(out0_ready), .data(out0_data), .last(out0_last));
  router_sva_out u_out1 (.clk(clk), .rst_n(rst_n), .in_hs(in_hs), .valid(out1_valid),
                         .ready(out1_ready), .data(out1_data), .last(out1_last));

  // ── APB and irq during reset (Lab 07) ─────────────────────────────────────
  // A4 (master), first half: psel is 0 while rst_n is 0. A master's rule, so
  // it checks the testbench's APB driver.
  a_A4: assert property (@(posedge clk) !rst_n |-> !psel)
    else begin n_A4++; $error("A4: psel is 1 during reset"); end

  // The specification's Reset table, for the signals this module can see.
  a_R_pready: assert property (@(posedge clk) !rst_n |-> pready)
    else begin n_R_pready++; $error("reset: pready is 0 during reset"); end
  a_R_pslverr: assert property (@(posedge clk) !rst_n |-> !pslverr)
    else begin n_R_pslverr++; $error("reset: pslverr is 1 during reset"); end
  a_R_prdata: assert property (@(posedge clk) !rst_n |-> prdata == 32'h0)
    else begin n_R_prdata++; $error("reset: prdata is %08h during reset", prdata); end
  a_R_irq: assert property (@(posedge clk) !rst_n |-> !irq)
    else begin n_R_irq++; $error("reset: irq is 1 during reset"); end
endmodule
