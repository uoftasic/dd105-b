// DD105-A: assertions for the router's valid/ready and APB rules.
//
// Plain SystemVerilog with no UVM in it, so any testbench can use it: the SV
// UVM environment in labs/ref binds it into the router (router_sva_bind.sv),
// and a pyuvm or cocotb testbench can bind it the same way and read the
// counters. The rule names (I1, O2, A6, ...) are the ones in the router
// specification, docs/reference/router-spec.md.
//
// Every assertion has its own failure counter, n_<rule>, and n_fail is their
// sum. A failure also calls $error, which this simulator prints as
// "%Error: ... Assertion failed in ...". Its default error limit is 1, so the
// first failure ends the run unless the run has +verilator+error+limit+N;
// labs/ref's Makefile passes a large limit, so every failure prints and the
// counters keep counting.
//
// Rules about normal operation are disabled while rst_n is 0. The rules
// about reset itself (I7, the first half of O4 and A4, and the reset values)
// are checked without that, at every rising edge.
//
// Some rules need a little state kept beside them (the specification says
// which): CTRL.EN as written over APB for I5, whether a packet is in progress
// for I5 and I6, and per output the beats of the current packet for O6. The
// rest of O5, O6 and O8, and I3, I4, O3 and O7, belong to a scoreboard.

// The rules that hold for each output separately: O1, O2, O4 and O6.
module router_sva_out (
  input logic       clk,
  input logic       rst_n,
  input logic       in_hs,     // a handshake on the input stream
  input logic       valid,
  input logic       ready,
  input logic [7:0] data,
  input logic       last
);
  int unsigned n_O1 = 0, n_O2 = 0, n_O4_rst = 0, n_O4_after = 0, n_O6 = 0;
  int unsigned n_fail;
  assign n_fail = n_O1 + n_O2 + n_O4_rst + n_O4_after + n_O6;

  // seen2 is 1 in cycle t if the input stream had a handshake in some cycle
  // up to t-2 since the last reset. A beat reaches an output no sooner than
  // two cycles after its input handshake, so until then out_valid must be 0.
  logic seen1, seen2;
  always @(posedge clk or negedge rst_n)
    if (!rst_n) begin
      seen1 <= 1'b0;
      seen2 <= 1'b0;
    end else begin
      seen1 <= seen1 | in_hs;
      seen2 <= seen1;
    end

  // Beats of the current output packet already taken, for O6.
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

  // O4, first half: out_valid is 0 while rst_n is 0.
  a_O4_rst: assert property (@(posedge clk) !rst_n |-> !valid)
    else begin n_O4_rst++; $error("O4: out_valid is 1 during reset"); end

  // O4, second half: out_valid stays 0 after reset until a beat accepted
  // after the reset could have reached the output.
  a_O4_after: assert property (@(posedge clk) disable iff (!rst_n)
                               !seen2 |-> !valid)
    else begin n_O4_after++; $error("O4: out_valid is 1 before any beat accepted since reset could arrive"); end

  // O6: the 8th beat of an output packet is its last.
  a_O6: assert property (@(posedge clk) disable iff (!rst_n)
                         valid && ready && beats == 4'd7 |-> last)
    else begin n_O6++; $error("O6: an output packet is longer than 8 beats"); end
endmodule

module router_sva (
  input logic        clk,
  input logic        rst_n,
  input logic        psel,
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
  // ── failure counters ──────────────────────────────────────────────────────
  // Input stream
  int unsigned n_I1 = 0, n_I2 = 0, n_I5 = 0, n_I6 = 0, n_I7 = 0;
  // APB (A1 to A4 are the master's rules: they check the testbench)
  int unsigned n_A1 = 0, n_A2 = 0, n_A3 = 0, n_A4 = 0;
  int unsigned n_A5 = 0, n_A6_first = 0, n_A6_second = 0, n_A6_only = 0;
  int unsigned n_A7_only = 0, n_A7_bad = 0, n_A8 = 0;
  // Values while rst_n is 0
  int unsigned n_R_pready = 0, n_R_pslverr = 0, n_R_prdata = 0, n_R_irq = 0;

  int unsigned n_fail;
  assign n_fail = n_I1 + n_I2 + n_I5 + n_I6 + n_I7
                + n_A1 + n_A2 + n_A3 + n_A4 + n_A5 + n_A6_first + n_A6_second + n_A6_only
                + n_A7_only + n_A7_bad + n_A8
                + n_R_pready + n_R_pslverr + n_R_prdata + n_R_irq
                + u_out0.n_fail + u_out1.n_fail;

  // ── state kept beside the assertions ──────────────────────────────────────
  wire in_hs = in_valid && in_ready;

  // CTRL.EN as the APB port wrote it (CTRL is at 0x04, EN is bit 0).
  logic ctrl_en;
  always @(posedge clk or negedge rst_n)
    if (!rst_n)                                               ctrl_en <= 1'b0;
    else if (psel && penable && pready && pwrite && paddr == 8'h04) ctrl_en <= pwdata[0];

  // 1 from the cycle after a packet's first handshake to its last handshake.
  logic in_pkt;
  always @(posedge clk or negedge rst_n)
    if (!rst_n)     in_pkt <= 1'b0;
    else if (in_hs) in_pkt <= !in_last;

  // 1 in the cycle after an APB setup cycle: the first access cycle.
  logic setup_d, rd_first_d;
  always @(posedge clk or negedge rst_n)
    if (!rst_n) begin
      setup_d    <= 1'b0;
      rd_first_d <= 1'b0;
    end else begin
      setup_d    <= psel && !penable;
      rd_first_d <= psel && penable && !pwrite && setup_d;
    end
  wire first_access = psel && penable && setup_d;
  wire completes    = psel && penable && pready;

  function automatic bit bad_addr(logic [7:0] a);
    return !(a inside {8'h00, 8'h04, 8'h08, 8'h0C, 8'h10, 8'h14,
                       8'h20, 8'h24, 8'h28, 8'h2C});
  endfunction

  // ── input stream ──────────────────────────────────────────────────────────
  // I1 (source): once in_valid is 1, it stays 1 until the handshake.
  a_I1: assert property (@(posedge clk) disable iff (!rst_n)
                         in_valid && !in_ready |=> in_valid)
    else begin n_I1++; $error("I1: in_valid fell without a handshake"); end

  // I2 (source): while in_valid is 1 and in_ready is 0, in_data and in_last hold.
  a_I2: assert property (@(posedge clk) disable iff (!rst_n)
                         in_valid && !in_ready |=> $stable(in_data) && $stable(in_last))
    else begin n_I2++; $error("I2: in_data or in_last changed while the beat waited"); end

  // I5: between packets, in_ready equals CTRL.EN.
  a_I5: assert property (@(posedge clk) disable iff (!rst_n)
                         !in_pkt |-> in_ready == ctrl_en)
    else begin n_I5++; $error("I5: between packets in_ready is %0d but CTRL.EN is %0d", in_ready, ctrl_en); end

  // I6: from a packet's first handshake to its last, in_ready is 1.
  a_I6: assert property (@(posedge clk) disable iff (!rst_n)
                         in_pkt |-> in_ready)
    else begin n_I6++; $error("I6: in_ready is 0 in the middle of a packet"); end

  // I7: in_ready is 0 while rst_n is 0.
  a_I7: assert property (@(posedge clk) !rst_n |-> !in_ready)
    else begin n_I7++; $error("I7: in_ready is 1 during reset"); end

  // ── outputs ───────────────────────────────────────────────────────────────
  router_sva_out u_out0 (.clk(clk), .rst_n(rst_n), .in_hs(in_hs), .valid(out0_valid),
                         .ready(out0_ready), .data(out0_data), .last(out0_last));
  router_sva_out u_out1 (.clk(clk), .rst_n(rst_n), .in_hs(in_hs), .valid(out1_valid),
                         .ready(out1_ready), .data(out1_data), .last(out1_last));

  // ── APB: the master's rules ───────────────────────────────────────────────
  // A1: a setup cycle is followed by an access cycle.
  a_A1: assert property (@(posedge clk) disable iff (!rst_n)
                         psel && !penable |=> psel && penable)
    else begin n_A1++; $error("A1: a setup cycle was not followed by an access cycle"); end

  // A2: paddr, pwrite (and pwdata for a write) hold until the transfer ends.
  a_A2: assert property (@(posedge clk) disable iff (!rst_n)
                         psel && !completes |=> $stable(paddr) && $stable(pwrite) &&
                                                (!pwrite || $stable(pwdata)))
    else begin n_A2++; $error("A2: paddr, pwrite or pwdata changed during a transfer"); end

  // A3: in the cycle after a transfer completes, penable is 0.
  a_A3: assert property (@(posedge clk) disable iff (!rst_n)
                         completes |=> !penable)
    else begin n_A3++; $error("A3: penable is 1 in the cycle after a transfer completed"); end

  // A4, first half: psel is 0 while rst_n is 0.
  a_A4: assert property (@(posedge clk) !rst_n |-> !psel)
    else begin n_A4++; $error("A4: psel is 1 during reset"); end

  // ── APB: the router's rules ───────────────────────────────────────────────
  // A5: in the first access cycle of a write, pready is 1.
  a_A5: assert property (@(posedge clk) disable iff (!rst_n)
                         first_access && pwrite |-> pready)
    else begin n_A5++; $error("A5: pready is 0 in the first access cycle of a write"); end

  // A6: a read waits one cycle: pready is 0 in its first access cycle and 1
  // in its second, and that is the only time pready is 0.
  a_A6_first: assert property (@(posedge clk) disable iff (!rst_n)
                               first_access && !pwrite |-> !pready)
    else begin n_A6_first++; $error("A6: pready is 1 in the first access cycle of a read"); end
  a_A6_second: assert property (@(posedge clk) disable iff (!rst_n)
                                first_access && !pwrite |=> pready)
    else begin n_A6_second++; $error("A6: pready is 0 in the second access cycle of a read"); end
  a_A6_only: assert property (@(posedge clk) disable iff (!rst_n)
                              !pready |-> first_access && !pwrite)
    else begin n_A6_only++; $error("A6: pready is 0 outside the first access cycle of a read"); end

  // A7: pslverr is 1 exactly in the cycle a transfer to a bad address completes.
  a_A7_only: assert property (@(posedge clk) disable iff (!rst_n)
                              pslverr |-> completes && bad_addr(paddr))
    else begin n_A7_only++; $error("A7: pslverr is 1 outside the completion of a bad transfer"); end
  a_A7_bad: assert property (@(posedge clk) disable iff (!rst_n)
                             completes && bad_addr(paddr) |-> pslverr)
    else begin n_A7_bad++; $error("A7: a transfer to bad address %02h completed without pslverr", paddr); end

  // A8: prdata changes only at the edge that ends a read's first access cycle.
  a_A8: assert property (@(posedge clk) disable iff (!rst_n)
                         prdata != $past(prdata) |-> rd_first_d)
    else begin n_A8++; $error("A8: prdata changed outside the first access cycle of a read"); end

  // ── values while rst_n is 0 ───────────────────────────────────────────────
  a_R_pready: assert property (@(posedge clk) !rst_n |-> pready)
    else begin n_R_pready++; $error("reset: pready is 0 during reset"); end
  a_R_pslverr: assert property (@(posedge clk) !rst_n |-> !pslverr)
    else begin n_R_pslverr++; $error("reset: pslverr is 1 during reset"); end
  a_R_prdata: assert property (@(posedge clk) !rst_n |-> prdata == 32'h0)
    else begin n_R_prdata++; $error("reset: prdata is %08h during reset", prdata); end
  a_R_irq: assert property (@(posedge clk) !rst_n |-> !irq)
    else begin n_R_irq++; $error("reset: irq is 1 during reset"); end
endmodule
