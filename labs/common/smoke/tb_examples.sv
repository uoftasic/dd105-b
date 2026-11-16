// tb_examples.sv
//
// Runs each timing example in docs/reference/router-spec.md and prints it as
// a Markdown table, so that every value on that page comes from a run.
//
// Each example starts from a reset, sets the router up without recording,
// then records a few cycles. Column n of a table is cycle n: the clock period
// that ends at rising edge n. Each value is what the signal holds during the
// cycle, read at the falling edge in the middle of it. A dash means the
// value doesn't matter in that cycle (its valid or PSEL is low, or it's
// PWDATA outside a write), and the testbench prints a dash instead of
// whatever is left on the wires. Rows marked (reg) are register values inside the router: what a
// read starting in that cycle would return.
//
//   make TB_SRC=tb_examples.sv          (from labs/common/smoke)

`default_nettype none

module tb_examples;

  // Lint waivers, for this testbench only:
  //   UNUSEDSIGNAL  some reads are made only for the table; their results
  //                 are dropped.
  //   BLKSEQ        the recorder is a clocked process that fills its arrays
  //                 with blocking assignments, on purpose.
  //   SYNCASYNCNET  the recorder samples rst_n on the clock, while the
  //                 router uses it as an asynchronous reset.
  /* verilator lint_off UNUSEDSIGNAL */
  /* verilator lint_off BLKSEQ */
  /* verilator lint_off SYNCASYNCNET */

  logic clk;
  logic rst_n;

  initial begin
    clk = 1'b0;
    forever #5 clk = ~clk;
  end

  logic        psel, penable, pwrite;
  logic [7:0]  paddr;
  logic [31:0] pwdata, prdata;
  logic        pready, pslverr, irq;
  logic        in_valid, in_last, in_ready;
  logic [7:0]  in_data;
  logic        out0_valid, out0_ready, out0_last;
  logic [7:0]  out0_data;
  logic        out1_valid, out1_ready, out1_last;
  logic [7:0]  out1_data;

  router dut (
    .clk, .rst_n,
    .psel, .penable, .pwrite, .paddr, .pwdata, .prdata, .pready, .pslverr,
    .irq,
    .in_valid, .in_ready, .in_data, .in_last,
    .out0_valid, .out0_ready, .out0_data, .out0_last,
    .out1_valid, .out1_ready, .out1_data, .out1_last
  );

  // ---- Recorder -----------------------------------------------------------------

  typedef enum int {
    S_RST, S_PSEL, S_PENABLE, S_PWRITE, S_PADDR, S_PWDATA, S_PREADY, S_PRDATA, S_PSLVERR,
    S_IN_VALID, S_IN_READY, S_IN_DATA, S_IN_LAST,
    S_O0_VALID, S_O0_READY, S_O0_DATA, S_O0_LAST,
    S_O1_VALID, S_O1_READY, S_O1_DATA, S_O1_LAST,
    S_LEVEL0, S_CTRL, S_STATUS, S_NR_CNT, S_FULL_CNT, S_IRQ, S_NSIG
  } sig_e;

  string     sig_name[S_NSIG];
  int        sig_hex[S_NSIG];     // hex digits to print, 0 for a single bit
  logic [31:0] val[64][S_NSIG];
  bit        care[64][S_NSIG];
  bit        rec;
  int        n_cyc;

  initial begin
    sig_name[S_RST] = "rst_n";          sig_hex[S_RST] = 0;
    sig_name[S_PSEL] = "PSEL";          sig_hex[S_PSEL] = 0;
    sig_name[S_PENABLE] = "PENABLE";    sig_hex[S_PENABLE] = 0;
    sig_name[S_PWRITE] = "PWRITE";      sig_hex[S_PWRITE] = 0;
    sig_name[S_PADDR] = "PADDR";        sig_hex[S_PADDR] = 2;
    sig_name[S_PWDATA] = "PWDATA";      sig_hex[S_PWDATA] = 8;
    sig_name[S_PREADY] = "PREADY";      sig_hex[S_PREADY] = 0;
    sig_name[S_PRDATA] = "PRDATA";      sig_hex[S_PRDATA] = 8;
    sig_name[S_PSLVERR] = "PSLVERR";    sig_hex[S_PSLVERR] = 0;
    sig_name[S_IN_VALID] = "in_valid";  sig_hex[S_IN_VALID] = 0;
    sig_name[S_IN_READY] = "in_ready";  sig_hex[S_IN_READY] = 0;
    sig_name[S_IN_DATA] = "in_data";    sig_hex[S_IN_DATA] = 2;
    sig_name[S_IN_LAST] = "in_last";    sig_hex[S_IN_LAST] = 0;
    sig_name[S_O0_VALID] = "out0_valid"; sig_hex[S_O0_VALID] = 0;
    sig_name[S_O0_READY] = "out0_ready"; sig_hex[S_O0_READY] = 0;
    sig_name[S_O0_DATA] = "out0_data";  sig_hex[S_O0_DATA] = 2;
    sig_name[S_O0_LAST] = "out0_last";  sig_hex[S_O0_LAST] = 0;
    sig_name[S_O1_VALID] = "out1_valid"; sig_hex[S_O1_VALID] = 0;
    sig_name[S_O1_READY] = "out1_ready"; sig_hex[S_O1_READY] = 0;
    sig_name[S_O1_DATA] = "out1_data";  sig_hex[S_O1_DATA] = 2;
    sig_name[S_O1_LAST] = "out1_last";  sig_hex[S_O1_LAST] = 0;
    sig_name[S_LEVEL0] = "LEVEL0 (reg)"; sig_hex[S_LEVEL0] = -1;   // decimal
    sig_name[S_CTRL] = "CTRL.EN (reg)"; sig_hex[S_CTRL] = 0;
    sig_name[S_STATUS] = "STATUS (reg)"; sig_hex[S_STATUS] = 1;
    sig_name[S_NR_CNT] = "NOROUTE_CNT (reg)"; sig_hex[S_NR_CNT] = -1;
    sig_name[S_FULL_CNT] = "FULL_CNT (reg)"; sig_hex[S_FULL_CNT] = -1;
    sig_name[S_IRQ] = "irq";            sig_hex[S_IRQ] = 0;
  end

  always @(negedge clk) begin : recorder
    if (rec && n_cyc < 64) begin
      val[n_cyc][S_RST] = 32'(rst_n);             care[n_cyc][S_RST] = 1;
      val[n_cyc][S_PSEL] = 32'(psel);             care[n_cyc][S_PSEL] = 1;
      val[n_cyc][S_PENABLE] = 32'(penable);       care[n_cyc][S_PENABLE] = 1;
      val[n_cyc][S_PWRITE] = 32'(pwrite);         care[n_cyc][S_PWRITE] = psel;
      val[n_cyc][S_PADDR] = 32'(paddr);           care[n_cyc][S_PADDR] = psel;
      val[n_cyc][S_PWDATA] = pwdata;              care[n_cyc][S_PWDATA] = psel && pwrite;
      val[n_cyc][S_PREADY] = 32'(pready);         care[n_cyc][S_PREADY] = 1;
      val[n_cyc][S_PRDATA] = prdata;              care[n_cyc][S_PRDATA] = 1;
      val[n_cyc][S_PSLVERR] = 32'(pslverr);       care[n_cyc][S_PSLVERR] = 1;
      val[n_cyc][S_IN_VALID] = 32'(in_valid);     care[n_cyc][S_IN_VALID] = 1;
      val[n_cyc][S_IN_READY] = 32'(in_ready);     care[n_cyc][S_IN_READY] = 1;
      val[n_cyc][S_IN_DATA] = 32'(in_data);       care[n_cyc][S_IN_DATA] = in_valid;
      val[n_cyc][S_IN_LAST] = 32'(in_last);       care[n_cyc][S_IN_LAST] = in_valid;
      val[n_cyc][S_O0_VALID] = 32'(out0_valid);   care[n_cyc][S_O0_VALID] = 1;
      val[n_cyc][S_O0_READY] = 32'(out0_ready);   care[n_cyc][S_O0_READY] = 1;
      val[n_cyc][S_O0_DATA] = 32'(out0_data);     care[n_cyc][S_O0_DATA] = out0_valid;
      val[n_cyc][S_O0_LAST] = 32'(out0_last);     care[n_cyc][S_O0_LAST] = out0_valid;
      val[n_cyc][S_O1_VALID] = 32'(out1_valid);   care[n_cyc][S_O1_VALID] = 1;
      val[n_cyc][S_O1_READY] = 32'(out1_ready);   care[n_cyc][S_O1_READY] = 1;
      val[n_cyc][S_O1_DATA] = 32'(out1_data);     care[n_cyc][S_O1_DATA] = out1_valid;
      val[n_cyc][S_O1_LAST] = 32'(out1_last);     care[n_cyc][S_O1_LAST] = out1_valid;
      val[n_cyc][S_LEVEL0] = 32'(dut.level0);     care[n_cyc][S_LEVEL0] = 1;
      val[n_cyc][S_CTRL] = 32'(dut.u_regs.en_q);  care[n_cyc][S_CTRL] = 1;
      val[n_cyc][S_STATUS] = 32'(dut.u_regs.status_q); care[n_cyc][S_STATUS] = 1;
      val[n_cyc][S_NR_CNT] = 32'(dut.u_regs.cnt_noroute_q); care[n_cyc][S_NR_CNT] = 1;
      val[n_cyc][S_FULL_CNT] = 32'(dut.u_regs.cnt_full_q);  care[n_cyc][S_FULL_CNT] = 1;
      val[n_cyc][S_IRQ] = 32'(irq);               care[n_cyc][S_IRQ] = 1;
      n_cyc++;
    end
  end

  function automatic string fmt_cell(input int c, input sig_e s);
    if (!care[c][s]) return "-";
    if (sig_hex[s] == 0)  return $sformatf("%0d", val[c][s][0]);
    if (sig_hex[s] < 0)   return $sformatf("%0d", val[c][s]);
    if (sig_hex[s] == 1)  return $sformatf("%01h", val[c][s][3:0]);
    if (sig_hex[s] == 2)  return $sformatf("%02h", val[c][s][7:0]);
    return $sformatf("%08h", val[c][s]);
  endfunction

  task automatic print_table(input string title, input sig_e rows[$]);
    string line;
    $display("");
    $display("#### %s", title);
    $display("");
    line = "| cycle |";
    for (int c = 0; c < n_cyc; c++) line = {line, $sformatf(" %0d |", c + 1)};
    $display("%s", line);
    line = "|---|";
    for (int c = 0; c < n_cyc; c++) line = {line, "---|"};
    $display("%s", line);
    foreach (rows[r]) begin
      line = {"| `", sig_name[rows[r]], "` |"};
      for (int c = 0; c < n_cyc; c++) line = {line, " ", fmt_cell(c, rows[r]), " |"};
      $display("%s", line);
    end
  endtask

  task automatic start_rec();
    n_cyc = 0;
    rec   = 1;
  endtask

  task automatic stop_rec();
    rec = 0;
  endtask

  // ---- Driving (as in tb_directed.sv: change 1 ns after the edge) ---------------------

  task automatic tick();
    @(posedge clk);
    #1;
  endtask

  task automatic idle(input int n);
    repeat (n) tick();
  endtask

  task automatic apb_write(input logic [7:0] a, input logic [31:0] d);
    bit done;
    psel = 1'b1; penable = 1'b0; pwrite = 1'b1; paddr = a; pwdata = d;
    tick();
    penable = 1'b1;
    do begin @(negedge clk); done = pready; tick(); end while (!done);
    psel = 1'b0; penable = 1'b0;
  endtask

  task automatic apb_read(input logic [7:0] a, output logic [31:0] d);
    bit done;
    psel = 1'b1; penable = 1'b0; pwrite = 1'b0; paddr = a;
    tick();
    penable = 1'b1;
    do begin @(negedge clk); done = pready; d = prdata; tick(); end while (!done);
    psel = 1'b0; penable = 1'b0;
  endtask

  task automatic send(input bit [7:0] beats[$]);
    bit took;
    foreach (beats[i]) begin
      in_valid = 1'b1; in_data = beats[i]; in_last = (i == beats.size() - 1);
      do begin @(negedge clk); took = in_ready; tick(); end while (!took);
    end
    in_valid = 1'b0; in_last = 1'b0; in_data = '0;
  endtask

  task automatic do_reset();
    rst_n = 1'b0;
    psel = 1'b0; penable = 1'b0; pwrite = 1'b0; paddr = '0; pwdata = '0;
    in_valid = 1'b0; in_last = 1'b0; in_data = '0;
    out0_ready = 1'b1; out1_ready = 1'b1;
    idle(3);
    rst_n = 1'b1;
    idle(2);
  endtask

  // ---- The examples ------------------------------------------------------------------

  initial begin : main
    logic [31:0] d;
    rec = 0;
    tick();

    // E1: an APB write, a read, and a read of an unmapped address.
    do_reset();
    start_rec();
    apb_write(8'h04, 32'h0000_0001);
    apb_read(8'h00, d);
    apb_read(8'h18, d);
    idle(1);
    stop_rec();
    print_table("E1: a write, a read and a bad read", '{
      S_PSEL, S_PENABLE, S_PWRITE, S_PADDR, S_PWDATA, S_PREADY, S_PRDATA, S_PSLVERR,
      S_CTRL, S_IN_READY});

    // E2: a three-beat packet into an empty output that is always ready.
    do_reset();
    apb_write(8'h20, 32'h1);           // ROUTE0: EN, PORT 0
    apb_write(8'h04, 32'h1);           // CTRL.EN
    idle(1);
    start_rec();
    idle(1);
    send('{8'h05, 8'h11, 8'h22});
    idle(3);
    stop_rec();
    print_table("E2: a three-beat packet through an empty output", '{
      S_IN_VALID, S_IN_READY, S_IN_DATA, S_IN_LAST, S_LEVEL0,
      S_O0_VALID, S_O0_READY, S_O0_DATA, S_O0_LAST});

    // E3: the same packet, with the sink stalling.
    do_reset();
    apb_write(8'h20, 32'h1);
    apb_write(8'h04, 32'h1);
    idle(1);
    start_rec();
    idle(1);
    fork
      send('{8'h05, 8'h11, 8'h22});
      begin
        idle(3); out0_ready = 1'b0;    // low in cycles 5 to 7
        idle(3); out0_ready = 1'b1;
        idle(1); out0_ready = 1'b0;    // low in cycle 9
        idle(1); out0_ready = 1'b1;
      end
    join
    idle(4);
    stop_rec();
    print_table("E3: a stalling sink", '{
      S_IN_VALID, S_IN_READY, S_IN_DATA, S_IN_LAST, S_LEVEL0,
      S_O0_VALID, S_O0_READY, S_O0_DATA, S_O0_LAST});

    // E4: a two-beat packet for a disabled route, with its interrupt enabled.
    do_reset();
    apb_write(8'h0C, 32'h1);           // INT_EN.NOROUTE
    apb_write(8'h04, 32'h1);           // CTRL.EN, every route still disabled
    idle(1);
    start_rec();
    idle(1);
    send('{8'h47, 8'h99});             // DST 1
    idle(2);
    apb_write(8'h08, 32'h1);           // clear STATUS.NOROUTE
    idle(1);
    stop_rec();
    print_table("E4: a NOROUTE drop and a write that clears it", '{
      S_IN_VALID, S_IN_READY, S_IN_DATA, S_IN_LAST, S_O0_VALID, S_O1_VALID,
      S_STATUS, S_NR_CNT, S_IRQ, S_PSEL, S_PENABLE, S_PWRITE, S_PADDR, S_PWDATA, S_PREADY});

    // E5: output 0 stalled, holding 9 beats: the next packet for it is dropped.
    do_reset();
    apb_write(8'h20, 32'h1);
    apb_write(8'h04, 32'h1);
    out0_ready = 1'b0;
    for (int i = 0; i < 9; i++) send('{8'(8'h01 + i)});
    idle(1);
    start_rec();
    idle(1);
    send('{8'h3A, 8'hA0});
    idle(1);
    out0_ready = 1'b1;
    idle(3);
    stop_rec();
    print_table("E5: a FULL drop", '{
      S_IN_VALID, S_IN_READY, S_IN_DATA, S_IN_LAST, S_LEVEL0,
      S_O0_VALID, S_O0_READY, S_O0_DATA, S_STATUS, S_FULL_CNT});

    // E6: a ten-beat packet: cut to eight.
    do_reset();
    apb_write(8'h20, 32'h1);
    apb_write(8'h04, 32'h1);
    idle(1);
    start_rec();
    idle(1);
    send('{8'h00, 8'h01, 8'h02, 8'h03, 8'h04, 8'h05, 8'h06, 8'h07, 8'h08, 8'h09});
    idle(2);
    stop_rec();
    print_table("E6: a ten-beat packet", '{
      S_IN_VALID, S_IN_READY, S_IN_DATA, S_IN_LAST,
      S_O0_VALID, S_O0_READY, S_O0_DATA, S_O0_LAST, S_STATUS});

    // E7: CTRL.EN cleared while a packet is half sent.
    do_reset();
    apb_write(8'h20, 32'h1);
    apb_write(8'h04, 32'h1);
    idle(1);
    start_rec();
    fork
      begin
        idle(1);
        send('{8'h01, 8'h11, 8'h12, 8'h13});
        send('{8'h02, 8'h21});           // waits: EN is 0 by now
      end
      begin
        idle(2);
        apb_write(8'h04, 32'h0);         // completes at the end of cycle 4
      end
    join_none
    idle(9);
    stop_rec();
    disable fork;
    psel = 1'b0; penable = 1'b0; in_valid = 1'b0; in_last = 1'b0;
    print_table("E7: CTRL.EN cleared in the middle of a packet", '{
      S_PSEL, S_PENABLE, S_PWRITE, S_PADDR, S_PWDATA, S_PREADY, S_CTRL,
      S_IN_VALID, S_IN_READY, S_IN_DATA, S_IN_LAST, S_O0_VALID, S_O0_READY, S_O0_DATA});

    // E8: reset with a beat waiting on output 0 and a packet half sent.
    do_reset();
    apb_write(8'h20, 32'h1);
    apb_write(8'h04, 32'h1);
    out0_ready = 1'b0;
    send('{8'h01, 8'hAA});
    idle(1);
    start_rec();
    fork
      send('{8'h02, 8'hB0, 8'hB1, 8'hB2, 8'hB3});
      begin
        idle(2);
        rst_n = 1'b0;                  // low in cycles 3 and 4
        idle(2);
        rst_n = 1'b1;
        in_valid = 1'b0; in_last = 1'b0;
      end
    join_any
    disable fork;
    in_valid = 1'b0; in_last = 1'b0;
    idle(1);
    out0_ready = 1'b1;
    idle(2);
    stop_rec();
    print_table("E8: reset with a beat waiting on output 0", '{
      S_RST, S_IN_VALID, S_IN_READY, S_IN_DATA, S_IN_LAST, S_LEVEL0,
      S_O0_VALID, S_O0_READY, S_O0_DATA, S_CTRL});

    // E9: a write to DROP_CNT in the same cycle as a drop.
    do_reset();
    apb_write(8'h04, 32'h1);
    send('{8'h00});                    // one NOROUTE drop: the counter is 1
    send('{8'h00});                    // two
    idle(1);
    start_rec();
    psel = 1'b1; penable = 1'b0; pwrite = 1'b1; paddr = 8'h10; pwdata = 32'h0;
    tick();
    penable = 1'b1; in_valid = 1'b1; in_data = 8'h00; in_last = 1'b1;
    tick();
    psel = 1'b0; penable = 1'b0; in_valid = 1'b0; in_last = 1'b0;
    idle(2);
    stop_rec();
    print_table("E9: a write to DROP_CNT in the same cycle as a drop", '{
      S_PSEL, S_PENABLE, S_PWRITE, S_PADDR, S_PWDATA, S_PREADY,
      S_IN_VALID, S_IN_READY, S_IN_DATA, S_IN_LAST, S_NR_CNT, S_STATUS});

    $display("");
    $display("EXAMPLES: done");
    $finish;
  end

endmodule

`default_nettype wire
