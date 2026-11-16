// tb_smoke.sv
//
// The router's shipped test. It is deliberately the kind of test a design
// often ships with, written by the designer on the afternoon the RTL first
// worked: it reads the ID register, sets up one route, sends three packets
// down it on the happy path and checks that they come out of output 0.
//
// It passes on the golden router, and it passes on every bug in
// labs/common/bugs.py too. That is the point of it: "the test passes" says
// very little about a design until you know what the test leaves out, and
// this one does nothing beyond what the paragraph above says.
//
// No classes and no UVM: plain tasks in a module, so it builds in seconds.
//
//   make            build and run it on the golden RTL
//   make faulty     run it on the faulty build (add BUG=B07 to pick a bug)

// Like the RTL, this file has no `timescale. The makefile passes
// --timescale 1ns/1ps, so #5 is 5 ns.

`default_nettype none

module tb_smoke;

  // ---- Clock, reset and the DUT --------------------------------------------

  logic clk;
  logic rst_n;

  initial begin
    clk = 1'b0;
    forever #5 clk = ~clk;   // 100 MHz
  end

  logic        psel, penable, pwrite;
  logic [7:0]  paddr;
  logic [31:0] pwdata;
  logic [31:0] prdata;
  logic        pready, pslverr;
  // Lint waiver: the smoke test never looks at the interrupt.
  /* verilator lint_off UNUSEDSIGNAL */
  logic        irq;
  /* verilator lint_on UNUSEDSIGNAL */

  logic        in_valid, in_last;
  logic [7:0]  in_data;
  logic        in_ready;

  logic        out0_valid, out0_last, out1_valid;
  logic [7:0]  out0_data;
  // Lint waiver: this test only counts the beats on output 1 (there should be
  // none), so it never looks at their data or last flag.
  /* verilator lint_off UNUSEDSIGNAL */
  logic [7:0]  out1_data;
  logic        out1_last;
  /* verilator lint_on UNUSEDSIGNAL */
  logic        out0_ready, out1_ready;

  router dut (
    .clk, .rst_n,
    .psel, .penable, .pwrite, .paddr, .pwdata, .prdata, .pready, .pslverr,
    .irq,
    .in_valid, .in_ready, .in_data, .in_last,
    .out0_valid, .out0_ready, .out0_data, .out0_last,
    .out1_valid, .out1_ready, .out1_data, .out1_last
  );

  // Waveforms: smoke.vcd, or the file named by +vcd=<path>. The makefile
  // converts it to FST with vcd2fst, because Verilator's own FST writer
  // needs lz4.h, which the course image doesn't have.
  initial begin
    string vcd;
    if (!$value$plusargs("vcd=%s", vcd)) vcd = "smoke.vcd";
    $dumpfile(vcd);
    $dumpvars(0, tb_smoke);
  end

  int errors = 0;   // set once here, only ever incremented

  task automatic check(input bit ok, input string what);
    if (!ok) begin
      errors++;
      $display("SMOKE: FAIL: %s", what);
    end
  endtask

  // ---- Driving the router -------------------------------------------------
  //
  // Inputs change 1 ns after a rising edge, by blocking assignment, and every
  // decision about the cycle in progress (did PREADY come? was the beat
  // taken?) is made at the falling edge, when everything has settled. Only
  // the router's flip-flops change at a rising edge, so the testbench and
  // the router never race. Every task starts and ends 1 ns after a rising
  // edge.

  task automatic tick();
    @(posedge clk);
    #1;
  endtask

  task automatic apb_write(input logic [7:0] addr, input logic [31:0] data);
    bit done;
    psel = 1'b1; penable = 1'b0; pwrite = 1'b1; paddr = addr; pwdata = data;
    tick();                                   // the setup cycle
    penable = 1'b1;
    do begin                                  // access cycles, until PREADY
      @(negedge clk);
      done = pready;
      if (done) check(!pslverr, $sformatf("PSLVERR on a write to 0x%02h", addr));
      tick();
    end while (!done);
    psel = 1'b0; penable = 1'b0;
  endtask

  task automatic apb_read(input logic [7:0] addr, output logic [31:0] data);
    bit done;
    psel = 1'b1; penable = 1'b0; pwrite = 1'b0; paddr = addr;
    tick();
    penable = 1'b1;
    do begin
      @(negedge clk);
      done = pready;
      data = prdata;
      if (done) check(!pslverr, $sformatf("PSLVERR on a read of 0x%02h", addr));
      tick();
    end while (!done);
    psel = 1'b0; penable = 1'b0;
  endtask

  // ---- Input stream ----------------------------------------------------------

  task automatic send_packet(input logic [7:0] beats[$]);
    bit taken;
    foreach (beats[i]) begin
      in_valid = 1'b1;
      in_data  = beats[i];
      in_last  = (i == beats.size() - 1);
      do begin                                // hold the beat until it is taken
        @(negedge clk);
        taken = in_ready;
        tick();
      end while (!taken);
    end
    in_valid = 1'b0;
    in_last  = 1'b0;
  endtask

  // ---- Output monitors ---------------------------------------------------------

  logic [7:0] got0[$];
  logic       got0_last[$];
  int         beats_on_1;
  initial beats_on_1 = 0;

  always @(posedge clk) begin
    if (out0_valid && out0_ready) begin
      got0.push_back(out0_data);
      got0_last.push_back(out0_last);
    end
    if (out1_valid && out1_ready) beats_on_1 <= beats_on_1 + 1;
  end

  // ---- The test ------------------------------------------------------------------

  initial begin : test
    logic [31:0] id;
    logic [7:0]  want[$];
    logic        want_last[$];
    logic [7:0]  p1[$], p2[$], p3[$];

    // Three packets for DST 0. The low bits of each header are a tag.
    p1 = '{8'h01, 8'hA0};
    p2 = '{8'h02, 8'hB0, 8'hB1, 8'hB2};
    p3 = '{8'h03, 8'hC0, 8'hC1};

    rst_n = 1'b0;
    psel = 1'b0; penable = 1'b0; pwrite = 1'b0; paddr = '0; pwdata = '0;
    in_valid = 1'b0; in_last = 1'b0; in_data = '0;
    out0_ready = 1'b1; out1_ready = 1'b1;     // never stalled
    repeat (5) tick();
    rst_n = 1'b1;
    repeat (2) tick();

    apb_read(8'h00, id);
    check(id == 32'hD105_0001, $sformatf("ID reads 0x%08h, expected 0xD1050001", id));

    apb_write(8'h20, 32'h1);    // ROUTE0: EN = 1, PORT = 0
    apb_write(8'h04, 32'h1);    // CTRL: EN = 1

    send_packet(p1);
    send_packet(p2);
    send_packet(p3);

    foreach (p1[i]) begin want.push_back(p1[i]); want_last.push_back(i == p1.size() - 1); end
    foreach (p2[i]) begin want.push_back(p2[i]); want_last.push_back(i == p2.size() - 1); end
    foreach (p3[i]) begin want.push_back(p3[i]); want_last.push_back(i == p3.size() - 1); end

    // Wait for the last beat, or give up after 100 cycles.
    for (int n = 0; n < 100 && got0.size() < want.size(); n++) tick();
    repeat (5) tick();

    check(got0.size() == want.size(),
          $sformatf("output 0 delivered %0d beats, expected %0d", got0.size(), want.size()));
    for (int i = 0; i < want.size() && i < got0.size(); i++) begin
      check(got0[i] == want[i] && got0_last[i] == want_last[i],
            $sformatf("beat %0d on output 0 is 0x%02h last=%0b, expected 0x%02h last=%0b",
                      i, got0[i], got0_last[i], want[i], want_last[i]));
    end
    check(beats_on_1 == 0, $sformatf("output 1 delivered %0d beats, expected 0", beats_on_1));

    if (errors == 0) begin
      $display("SMOKE: PASS (3 packets, %0d beats, all on output 0)", want.size());
      $finish;
    end else begin
      $fatal(1, "SMOKE: FAIL (%0d errors)", errors);
    end
  end

  initial begin : watchdog
    #100us;
    $fatal(1, "SMOKE: FAIL (timed out)");
  end

endmodule

`default_nettype wire
