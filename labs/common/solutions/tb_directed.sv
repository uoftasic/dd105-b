// tb_directed.sv
//
// The router's thorough directed test: the test we wrote to convince
// ourselves that rtl/ meets docs/reference/router-spec.md, and that every bug
// in bugs.py changes what the router does. It is not shipped to students. It
// catches all fifteen bugs, so it is an answer key; see README.md here.
//
// No classes and no UVM. Three things run side by side:
//
//   - a reference model, written from the spec, that predicts every beat on
//     both outputs, every register read, in_ready, PREADY, PSLVERR and irq,
//     cycle by cycle, and complains the moment the router disagrees;
//   - checkers for the spec's valid/ready and APB rules (I5 to I7, O1, O2,
//     O4 to O6 and A5 to A9), every cycle;
//   - nineteen directed checks, C01 to C19. Each one starts from a reset,
//     drives one feature, and also compares a few results with numbers
//     written out by hand, so a mistake shared by the model and the RTL
//     still shows up.
//
// Every failure is charged to the check that was running, and the summary
// at the end prints one line per check. Each check resets the router, so a
// bug that breaks one check doesn't spill into the next.
//
// Plusargs:
//   +vcd=<file>     waveform file (default directed.vcd)
//   +trace=<file>   also write every port of the router, every cycle, to a
//                   text file. Two runs that write identical traces drove
//                   identical inputs and saw identical outputs.
//   +BUG=Bnn        only meaningful on the faulty build (see inject.py)
//
// Build and run from labs/common/smoke:
//   make TB_SRC=../solutions/tb_directed.sv            golden RTL
//   make TB_SRC=../solutions/tb_directed.sv faulty BUG=B07

`default_nettype none

module tb_directed;

  // Lint waivers, for this testbench only (the RTL needs none of these):
  //   BLKSEQ        the model is a clocked process that uses blocking
  //                 assignments on purpose, to compute each cycle's
  //                 prediction step by step, in order;
  //   WIDTHEXPAND   expect_eq() takes 64-bit values, and its callers pass
  //                 1- and 32-bit ones;
  //   UNUSEDSIGNAL  some reads are made only so the model checks them, and
  //                 their results are dropped;
  //   SYNCASYNCNET  the model samples rst_n on the clock, while the router
  //                 uses it as an asynchronous reset.
  /* verilator lint_off BLKSEQ */
  /* verilator lint_off WIDTHEXPAND */
  /* verilator lint_off UNUSEDSIGNAL */
  /* verilator lint_off SYNCASYNCNET */

  // ==== Clock, reset and the DUT ============================================

  logic clk;
  logic rst_n;

  initial begin
    clk = 1'b0;
    forever #5 clk = ~clk;
  end

  logic        psel, penable, pwrite;
  logic [7:0]  paddr;
  logic [31:0] pwdata;
  logic [31:0] prdata;
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

  // Both outputs as arrays, so checks can loop over them.
  logic       o_valid[2], o_ready[2], o_last[2];
  logic [7:0] o_data[2];
  always_comb begin
    o_valid[0] = out0_valid; o_ready[0] = out0_ready; o_data[0] = out0_data; o_last[0] = out0_last;
    o_valid[1] = out1_valid; o_ready[1] = out1_ready; o_data[1] = out1_data; o_last[1] = out1_last;
  end

  // ==== Register map (from the spec) ==========================================

  localparam logic [7:0] A_ID = 8'h00, A_CTRL = 8'h04, A_STATUS = 8'h08, A_INT_EN = 8'h0C,
                         A_DROP_CNT = 8'h10, A_LEVEL = 8'h14,
                         A_ROUTE0 = 8'h20, A_ROUTE1 = 8'h24, A_ROUTE2 = 8'h28, A_ROUTE3 = 8'h2C;
  localparam logic [31:0] ID_VALUE = 32'hD105_0001;

  function automatic bit is_reg(input logic [7:0] a);
    return a inside {A_ID, A_CTRL, A_STATUS, A_INT_EN, A_DROP_CNT, A_LEVEL,
                     A_ROUTE0, A_ROUTE1, A_ROUTE2, A_ROUTE3};
  endfunction

  function automatic logic [7:0] route_addr(input int n);
    return A_ROUTE0 + 8'(4 * n);
  endfunction

  // ==== Check bookkeeping ======================================================

  localparam int NCHK = 19;
  string chk_name[NCHK + 1];
  int    chk_fail[NCHK + 1];
  int    cur;            // the check now running (0 = between checks)
  longint cyc;           // rising edges since time 0

  task automatic fail(input string msg);
    chk_fail[cur]++;
    if (chk_fail[cur] <= 6)
      $display("FAIL C%02d %s @%0d: %s", cur, chk_name[cur], cyc, msg);
    else if (chk_fail[cur] == 7)
      $display("FAIL C%02d %s: more failures not printed", cur, chk_name[cur]);
  endtask

  task automatic expect_eq(input longint got, input longint want, input string what);
    if (got != want) fail($sformatf("%s is 0x%0h, expected 0x%0h", what, got, want));
  endtask

  // ==== The reference model ======================================================
  //
  // Everything here is predicted from the spec, at each rising edge, from the
  // values the signals had just before it. The state below is the model's
  // copy of the router's state.

  bit         m_en;
  bit [2:0]   m_status, m_inten;
  bit [7:0]   m_cnt_nr, m_cnt_full;
  bit [3:0]   m_ren, m_rport;
  int         m_state;                 // 0 between packets, 1 forwarding, 2 dropping, 3 cut
  bit         m_port;
  int         m_beat;                  // beats of this packet accepted so far
  int         m_level[2];
  bit [8:0]   exp_q[2][$];             // {last, data} still to come out of each output
  longint     exp_t[2][$];             // the cycle of each of those beats' input handshake
  longint     h_prev[2];               // the cycle of the latest handshake on each output
  logic [31:0] m_prdata;               // what prdata holds (rule A8)

  // APB transfer tracking.
  int         apb_n;                   // access-phase cycles already done in this transfer
  logic [31:0] rd_exp;
  bit         rd_exp_bad;

  // Counters the directed checks read.
  int         n_in_hs;                 // input handshakes
  int         n_out[2];                // output handshakes
  int         n_pkt_out[2];            // packets (out_last beats) delivered
  int         n_ev_oversize;
  int         m_beats, m_reads, m_writes;   // what the model has compared, in all
  longint     t_hs;                    // edge of the latest input handshake
  longint     t_rise[2];               // edge at which each out_valid was last seen rising

  // Previous-cycle samples, for the stability rules.
  bit         p_valid[2], p_ready[2], p_last[2];
  bit [7:0]   p_data[2];
  bit         p_rst_n;
  int         run_len[2];              // beats of the packet now leaving each output

  function automatic string kind(input bit w);
    return w ? "write" : "read";
  endfunction

  function automatic bit m_bad(input logic [7:0] a);
    return !is_reg(a);
  endfunction

  function automatic logic [31:0] m_read(input logic [7:0] a);
    case (a)
      A_ID:       return ID_VALUE;
      A_CTRL:     return {31'b0, m_en};
      A_STATUS:   return {29'b0, m_status};
      A_INT_EN:   return {29'b0, m_inten};
      A_DROP_CNT: return {16'b0, m_cnt_full, m_cnt_nr};
      A_LEVEL:    return {19'b0, 5'(m_level[1]), 3'b0, 5'(m_level[0])};
      A_ROUTE0:   return {30'b0, m_rport[0], m_ren[0]};
      A_ROUTE1:   return {30'b0, m_rport[1], m_ren[1]};
      A_ROUTE2:   return {30'b0, m_rport[2], m_ren[2]};
      A_ROUTE3:   return {30'b0, m_rport[3], m_ren[3]};
      default:    return 32'b0;
    endcase
  endfunction

  function automatic bit [7:0] bump(input bit [7:0] cnt, input bit inc, input bit clr);
    bit [7:0] n;
    n = clr ? 8'd0 : cnt;
    if (inc && n != 8'hFF) n = n + 8'd1;
    return n;
  endfunction

  task automatic model_reset();
    m_en = 0; m_status = 0; m_inten = 0; m_cnt_nr = 0; m_cnt_full = 0;
    m_ren = 0; m_rport = 0; m_state = 0; m_port = 0; m_beat = 0;
    m_level[0] = 0; m_level[1] = 0;
    exp_q[0].delete(); exp_q[1].delete();
    exp_t[0].delete(); exp_t[1].delete();
    h_prev[0] = -100; h_prev[1] = -100;
    m_prdata = 0;
    apb_n = 0;
  endtask

  always @(posedge clk) begin : model
    bit       access, exp_pready, wr_good;
    bit [2:0] ev, w1c;
    bit       clr;
    bit       hs, fwd, port, at_max, counting, last_out, room, e;
    bit [1:0] dst;
    bit       push[2], pop[2];
    int       next_state;
    bit       exp_valid;
    logic [31:0] prdata_next;

    cyc++;

    // ---- I7, O4: during reset -------------------------------------------------
    if (!rst_n) begin
      model_reset();
      if (in_ready)   fail("in_ready is high while rst_n is low");
      if (out0_valid) fail("out0_valid is high while rst_n is low");
      if (out1_valid) fail("out1_valid is high while rst_n is low");
      if (irq)        fail("irq is high while rst_n is low");
    end else begin

      // ---- Outputs that are pure functions of the model's state -------------------
      if (in_ready != ((m_state != 0) || m_en))
        fail($sformatf("in_ready is %0b, expected %0b", in_ready, (m_state != 0) || m_en));
      if (irq != |(m_status & m_inten))
        fail($sformatf("irq is %0b, expected %0b (STATUS 0x%0h, INT_EN 0x%0h)",
                       irq, |(m_status & m_inten), m_status, m_inten));

      // ---- APB: A5 to A9 ---------------------------------------------------------
      access   = psel && penable;
      wr_good  = 0;
      // A8, outside a completing read (that case is checked below).
      if (!(access && pready && !pwrite) && prdata != m_prdata)
        fail($sformatf("prdata is 0x%08h between reads, expected 0x%08h", prdata, m_prdata));
      prdata_next = m_prdata;
      if (access) begin
        exp_pready = pwrite || (apb_n >= 1);
        if (!pwrite && apb_n == 0) begin
          rd_exp      = m_read(paddr);
          rd_exp_bad  = m_bad(paddr);
          prdata_next = rd_exp_bad ? 32'h0 : rd_exp;
        end
        if (pready != exp_pready)
          fail($sformatf("PREADY is %0b in access cycle %0d of a %s to 0x%02h, expected %0b",
                         pready, apb_n + 1, kind(pwrite), paddr, exp_pready));
        if (pready) begin
          if (pslverr != m_bad(paddr))
            fail($sformatf("PSLVERR is %0b for a %s to 0x%02h, expected %0b",
                           pslverr, kind(pwrite), paddr, m_bad(paddr)));
          if (pwrite) m_writes++; else m_reads++;
          if (!pwrite && prdata != (rd_exp_bad ? 32'h0 : rd_exp))
            fail($sformatf("read of 0x%02h returned 0x%08h, expected 0x%08h",
                           paddr, prdata, rd_exp_bad ? 32'h0 : rd_exp));
          wr_good = pwrite && !m_bad(paddr);
          apb_n = 0;
        end else begin
          if (pslverr) fail("PSLVERR is high while PREADY is low");
          apb_n++;
        end
      end else begin
        apb_n = 0;
        if (pslverr) fail("PSLVERR is high outside an access phase");
      end

      // ---- The input beat: decided from the levels before this edge --------------------
      hs = in_valid && in_ready;
      ev = 3'b000;
      push[0] = 0; push[1] = 0;
      fwd = 0; port = 0; last_out = 0; next_state = m_state;
      if (hs) begin
        n_in_hs++;
        t_hs = cyc;
        counting = (m_state != 3);
        at_max   = (m_beat == 7);
        if (m_state == 0) begin
          dst  = in_data[7:6];
          e    = m_ren[dst];
          port = m_rport[dst];
          room = (m_level[port] <= 8);
          if (!e)         ev[0] = 1;     // NOROUTE
          else if (!room) ev[1] = 1;     // FULL
          fwd = e && room;
        end else begin
          port = m_port;
          fwd  = (m_state == 1);
        end
        if (counting && at_max && !in_last) begin
          ev[2] = 1;                      // OVERSIZE
          n_ev_oversize++;
        end
        last_out = in_last || at_max;
        if (fwd) push[port] = 1;

        if (in_last) begin
          next_state = 0;
          m_beat     = 0;
        end else if (counting && at_max) begin
          next_state = 3;
        end else begin
          if (counting) m_beat++;
          if (m_state == 0) begin
            next_state = fwd ? 1 : 2;
            m_port     = port;
          end
        end
      end
      m_state = next_state;

      // ---- Output beats: O5 and O6, then O1 and O2 -----------------------------------
      for (int p = 0; p < 2; p++) begin
        if (o_valid[p] && !p_valid[p] && p_rst_n) t_rise[p] = cyc;
        // O8: the oldest undelivered beat is on the output from cycle
        // max(t_in + 2, h_prev + 1) until it is taken, and out_valid is 0
        // in every other cycle.
        exp_valid = exp_q[p].size() != 0 &&
                    cyc >= ((exp_t[p][0] + 2 > h_prev[p] + 1) ? exp_t[p][0] + 2 : h_prev[p] + 1);
        if (o_valid[p] != exp_valid)
          fail($sformatf("out%0d_valid is %0b, expected %0b", p, o_valid[p], exp_valid));
        else if (exp_valid && {o_last[p], o_data[p]} != exp_q[p][0])
          fail($sformatf("output %0d shows 0x%02h last=%0b, expected 0x%02h last=%0b",
                         p, o_data[p], o_last[p], exp_q[p][0][7:0], exp_q[p][0][8]));
        pop[p] = o_valid[p] && o_ready[p];
        if (pop[p]) h_prev[p] = cyc;
        if (pop[p]) begin
          n_out[p]++;
          if (exp_q[p].size() == 0) begin
            fail($sformatf("output %0d delivered 0x%02h last=%0b, and no beat was expected",
                           p, o_data[p], o_last[p]));
          end else begin
            bit [8:0] want;
            want = exp_q[p].pop_front();
            void'(exp_t[p].pop_front());
            m_beats++;
            if ({o_last[p], o_data[p]} != want)
              fail($sformatf("output %0d delivered 0x%02h last=%0b, expected 0x%02h last=%0b",
                             p, o_data[p], o_last[p], want[7:0], want[8]));
          end
          run_len[p]++;
          if (run_len[p] > 8) fail($sformatf("output %0d sent a packet of more than 8 beats", p));
          if (o_last[p]) begin
            run_len[p] = 0;
            n_pkt_out[p]++;
          end
        end
        // O1, O2: a stalled beat stays, unchanged, until it is taken.
        if (p_rst_n && p_valid[p] && !p_ready[p]) begin
          if (!o_valid[p])
            fail($sformatf("out%0d_valid fell without a handshake", p));
          else if (o_data[p] != p_data[p] || o_last[p] != p_last[p])
            fail($sformatf("output %0d changed from 0x%02h/%0b to 0x%02h/%0b while stalled",
                           p, p_data[p], p_last[p], o_data[p], o_last[p]));
        end
      end

      // The beat accepted at this edge joins its queue after the outputs are
      // checked: it can't leave at the edge it arrived.
      for (int p = 0; p < 2; p++) begin
        if (push[p]) begin
          exp_q[p].push_back({last_out, in_data});
          exp_t[p].push_back(cyc);
        end
        m_level[p] += int'(push[p]) - int'(pop[p]);
      end

      // ---- Registers: the write that completes at this edge, then the events --------
      w1c = 3'b000;
      clr = 0;
      if (wr_good) begin
        case (paddr)
          A_CTRL:     m_en    = pwdata[0];
          A_INT_EN:   m_inten = pwdata[2:0];
          A_STATUS:   w1c     = pwdata[2:0];
          A_DROP_CNT: clr     = 1;
          A_ROUTE0:   {m_rport[0], m_ren[0]} = pwdata[1:0];
          A_ROUTE1:   {m_rport[1], m_ren[1]} = pwdata[1:0];
          A_ROUTE2:   {m_rport[2], m_ren[2]} = pwdata[1:0];
          A_ROUTE3:   {m_rport[3], m_ren[3]} = pwdata[1:0];
          default:    ;
        endcase
      end
      m_prdata   = prdata_next;
      m_status   = (m_status & ~w1c) | ev;
      m_cnt_nr   = bump(m_cnt_nr,   ev[0], clr);
      m_cnt_full = bump(m_cnt_full, ev[1], clr);
    end

    for (int p = 0; p < 2; p++) begin
      p_valid[p] = o_valid[p];
      p_ready[p] = o_ready[p];
      p_data[p]  = o_data[p];
      p_last[p]  = o_last[p];
      if (!rst_n) run_len[p] = 0;
    end
    p_rst_n = rst_n;
  end

  // ==== Stimulus =====================================================================
  //
  // Inputs change 1 ns after a rising edge, by blocking assignment, and every
  // decision about the cycle in progress (did PREADY come? did the router
  // take the beat?) is made at the falling edge, when everything has
  // settled. Only the router's flip-flops change at a rising edge, so the
  // testbench and the router never race. Every task here starts and ends
  // 1 ns after a rising edge.
  //
  // We tried nonblocking assignments first. Verilator 5.050 commits two
  // nonblocking assignments to one signal in the same time step in source
  // order rather than in the order they ran, when a timing control separates
  // the two statements: an APB task that ends with psel <= 0 and is called
  // again at once, starting with psel <= 1, leaves psel low. Icarus gets it
  // right. See README.md.

  bit abort_tx;   // set by a reset: the source gives up its packet

  task automatic tick();
    @(posedge clk);
    #1;
  endtask

  task automatic apb_write(input logic [7:0] a, input logic [31:0] d);
    bit done;
    psel = 1'b1; penable = 1'b0; pwrite = 1'b1; paddr = a; pwdata = d;
    tick();
    penable = 1'b1;
    do begin
      @(negedge clk);
      done = pready;
      tick();
    end while (!done);
    psel = 1'b0; penable = 1'b0;
  endtask

  task automatic apb_read(input logic [7:0] a, output logic [31:0] d, output bit err);
    bit done;
    psel = 1'b1; penable = 1'b0; pwrite = 1'b0; paddr = a;
    tick();
    penable = 1'b1;
    do begin
      @(negedge clk);
      done = pready;
      d    = prdata;
      err  = pslverr;
      tick();
    end while (!done);
    psel = 1'b0; penable = 1'b0;
  endtask

  // Read a register and compare it with a value written out by hand.
  task automatic read_expect(input logic [7:0] a, input logic [31:0] want, input string what);
    logic [31:0] d;
    bit err;
    apb_read(a, d, err);
    if (err) fail($sformatf("%s: PSLVERR on a read of 0x%02h", what, a));
    expect_eq(d, want, what);
  endtask

  task automatic set_route(input int n, input bit en, input bit port);
    apb_write(route_addr(n), {30'b0, port, en});
  endtask

  // Send one packet. gap_pct is the chance, in percent, of an idle cycle
  // before each beat.
  task automatic send(input bit [7:0] beats[$], input int gap_pct = 0);
    bit took;
    for (int i = 0; i < beats.size(); i++) begin
      while (gap_pct > 0 && $urandom_range(99) < gap_pct) begin
        in_valid = 1'b0;
        in_last  = 1'b0;
        tick();
        if (abort_tx) return;
      end
      in_valid = 1'b1;
      in_data  = beats[i];
      in_last  = (i == beats.size() - 1);
      do begin
        @(negedge clk);
        took = in_ready;
        tick();
        if (abort_tx) begin in_valid = 1'b0; in_last = 1'b0; return; end
      end while (!took);
    end
    in_valid = 1'b0;
    in_last  = 1'b0;
  endtask

  // A packet for `dst` with `len` beats: header {dst, tag}, then payload.
  function automatic void make_pkt(output bit [7:0] q[$], input bit [1:0] dst, input int len);
    q.delete();
    q.push_back({dst, 6'($urandom)});
    for (int i = 1; i < len; i++) q.push_back(8'($urandom));
  endfunction

  task automatic send_pkt(input bit [1:0] dst, input int len, input int gap_pct = 0);
    bit [7:0] q[$];
    make_pkt(q, dst, len);
    send(q, gap_pct);
  endtask

  // Output sinks. Mode 0: always ready; 1: never ready; 2: ready with
  // probability rdy_pct percent, each cycle.
  int rdy_mode[2];
  int rdy_pct[2];

  always @(posedge clk) begin : sinks
    #1;
    for (int p = 0; p < 2; p++) begin
      logic r;
      case (rdy_mode[p])
        0:       r = 1'b1;
        1:       r = 1'b0;
        default: r = ($urandom_range(99) < rdy_pct[p]);
      endcase
      if (p == 0) out0_ready = r; else out1_ready = r;
    end
  end

  task automatic set_ready(input int p, input int mode, input int pct = 50);
    rdy_mode[p] = mode;
    rdy_pct[p]  = pct;
  endtask

  task automatic idle(input int n);
    repeat (n) tick();
  endtask

  // Wait for both outputs to deliver everything the model expects, with both
  // sinks ready, then a few cycles more so that any extra beat shows up.
  task automatic drain(input int max_cycles = 3000);
    int n;
    set_ready(0, 0);
    set_ready(1, 0);
    n = 0;
    while ((exp_q[0].size() != 0 || exp_q[1].size() != 0) && n < max_cycles) begin
      tick();
      n++;
    end
    for (int p = 0; p < 2; p++)
      if (exp_q[p].size() != 0)
        fail($sformatf("%0d expected beats never came out of output %0d", exp_q[p].size(), p));
    idle(5);
  endtask

  task automatic do_reset(input int cycles = 3);
    abort_tx = 1;
    rst_n    = 1'b0;
    psel     = 1'b0; penable = 1'b0; pwrite = 1'b0; paddr = '0; pwdata = '0;
    in_valid = 1'b0; in_last = 1'b0; in_data = '0;
    repeat (cycles) tick();
    rst_n = 1'b1;
    tick();
    abort_tx = 0;
    tick();
  endtask

  task automatic begin_check(input int n, input string name);
    cur = 0;
    set_ready(0, 0);
    set_ready(1, 0);
    do_reset();
    cur = n;
    chk_name[n] = name;
    n_in_hs = 0; n_out[0] = 0; n_out[1] = 0; n_pkt_out[0] = 0; n_pkt_out[1] = 0;
    n_ev_oversize = 0;
  endtask

  task automatic end_check();
    drain();
    cur = 0;
  endtask

  // Turn on the router with the given routes.
  task automatic setup(input bit [3:0] en, input bit [3:0] port);
    for (int n = 0; n < 4; n++) set_route(n, en[n], port[n]);
    apb_write(A_CTRL, 32'h1);
  endtask

  // ==== The checks =====================================================================

  // C01: every register's reset value, and the pins after reset.
  task automatic c01_reset_values();
    int hs0;
    begin_check(1, "reset_values");
    expect_eq(in_ready, 0, "in_ready after reset");
    expect_eq(out0_valid, 0, "out0_valid after reset");
    expect_eq(out1_valid, 0, "out1_valid after reset");
    expect_eq(irq, 0, "irq after reset");
    read_expect(A_ID,       ID_VALUE, "ID after reset");
    read_expect(A_CTRL,     0, "CTRL after reset");
    read_expect(A_STATUS,   0, "STATUS after reset");
    read_expect(A_INT_EN,   0, "INT_EN after reset");
    read_expect(A_DROP_CNT, 0, "DROP_CNT after reset");
    read_expect(A_LEVEL,    0, "LEVEL after reset");
    for (int n = 0; n < 4; n++) read_expect(route_addr(n), 0, $sformatf("ROUTE%0d after reset", n));
    // Offer a packet with EN still 0: the router must not take it.
    hs0 = n_in_hs;
    in_valid = 1'b1; in_data = 8'h00; in_last = 1'b1;
    idle(10);
    in_valid = 1'b0; in_last = 1'b0;
    expect_eq(n_in_hs - hs0, 0, "handshakes while CTRL.EN is 0 after reset");
    end_check();
  endtask

  // C02: read back every read-write field with values whose bits differ, and
  // check that writes to read-only registers and reserved bits do nothing.
  task automatic c02_reg_readback();
    bit [1:0] v[4];
    begin_check(2, "reg_readback");
    apb_write(A_CTRL, 32'hFFFF_FFFF);   read_expect(A_CTRL, 32'h1, "CTRL after writing all ones");
    apb_write(A_CTRL, 32'hFFFF_FFFE);   read_expect(A_CTRL, 32'h0, "CTRL after writing 0xFFFFFFFE");
    apb_write(A_INT_EN, 32'h5);         read_expect(A_INT_EN, 32'h5, "INT_EN after writing 5");
    apb_write(A_INT_EN, 32'h2);         read_expect(A_INT_EN, 32'h2, "INT_EN after writing 2");
    apb_write(A_INT_EN, 32'hFFFF_FFF8); read_expect(A_INT_EN, 32'h0, "INT_EN after writing 0xFFFFFFF8");
    apb_write(A_INT_EN, 32'hFFFF_FFFF); read_expect(A_INT_EN, 32'h7, "INT_EN after writing all ones");
    apb_write(A_INT_EN, 32'h0);
    // The four routes at once, with four different values, rotated four times.
    for (int r = 0; r < 4; r++) begin
      for (int n = 0; n < 4; n++) begin
        v[n] = 2'((n + r) % 4);
        apb_write(route_addr(n), 32'hFFFF_FFFC | 32'(v[n]));   // reserved bits all 1
      end
      for (int n = 0; n < 4; n++)
        read_expect(route_addr(n), 32'(v[n]), $sformatf("ROUTE%0d after writing %0d", n, v[n]));
    end
    // Read-only registers and fields.
    apb_write(A_ID, 32'h0);              read_expect(A_ID, ID_VALUE, "ID after a write");
    apb_write(A_LEVEL, 32'hFFFF_FFFF);   read_expect(A_LEVEL, 32'h0, "LEVEL after a write");
    apb_write(A_STATUS, 32'hFFFF_FFFF);  read_expect(A_STATUS, 32'h0, "STATUS after writing ones to it");
    apb_write(A_DROP_CNT, 32'hFFFF_FFFF); read_expect(A_DROP_CNT, 32'h0, "DROP_CNT after a write");
    end_check();
  endtask

  // C03: every one of the 256 byte addresses, read and written. Unmapped and
  // misaligned addresses must fail and change nothing.
  task automatic c03_bad_address();
    logic [31:0] d;
    bit err;
    int n_bad;
    begin_check(3, "bad_address");
    n_bad = 0;
    for (int a = 0; a < 256; a++) begin
      apb_read(8'(a), d, err);
      if (err != !is_reg(8'(a))) fail($sformatf("read of 0x%02h: PSLVERR %0b", a, err));
      if (!is_reg(8'(a)) && d != 0) fail($sformatf("bad read of 0x%02h returned 0x%08h", a, d));
      n_bad += !is_reg(8'(a));
    end
    expect_eq(n_bad, 246, "number of bad addresses");
    for (int a = 0; a < 256; a++) begin
      if (is_reg(8'(a))) continue;
      apb_write(8'(a), 32'hFFFF_FFFF);
    end
    read_expect(A_CTRL,   0, "CTRL after writes to every bad address");
    read_expect(A_INT_EN, 0, "INT_EN after writes to every bad address");
    for (int n = 0; n < 4; n++)
      read_expect(route_addr(n), 0, $sformatf("ROUTE%0d after writes to every bad address", n));
    end_check();
  endtask

  // C04: every DST under two routing tables, every length from 1 to 8, and
  // the latency from the input to an empty output.
  task automatic c04_routing();
    begin_check(4, "routing");
    // Table A: PORT = DST bit 0. Table B: PORT = DST bit 1.
    for (int t = 0; t < 2; t++) begin
      setup(4'b1111, t == 0 ? 4'b1010 : 4'b1100);
      for (int len = 1; len <= 8; len++)
        for (int d = 0; d < 4; d++) send_pkt(2'(d), len);
      drain();
      expect_eq(n_pkt_out[0] + n_pkt_out[1], 32 * (t + 1), "packets delivered");
    end
    // Latency: a header taken at edge N into an empty output is first seen
    // valid at edge N + 2.
    send_pkt(2'd0, 1);
    idle(4);
    expect_eq(t_rise[0] - t_hs, 2, "edges from input handshake to out0_valid");
    end_check();
  endtask

  // C05: packets for disabled routes are dropped and counted, and routes can
  // be turned on and off between packets.
  task automatic c05_disabled_route();
    int want_nr;
    begin_check(5, "disabled_route");
    setup(4'b1001, 4'b1010);   // DST 0 -> out0, DST 3 -> out1; 1 and 2 disabled
    want_nr = 0;
    for (int i = 0; i < 40; i++) begin
      bit [1:0] d;
      d = 2'($urandom);
      send_pkt(d, $urandom_range(1, 8));
      if (d == 1 || d == 2) want_nr++;
    end
    drain();
    read_expect(A_DROP_CNT, 32'(want_nr), "DROP_CNT after 40 packets, routes 1 and 2 disabled");
    read_expect(A_STATUS, 32'h1, "STATUS after NOROUTE drops");
    // Flip the table: 1 and 2 on, 0 and 3 off.
    setup(4'b0110, 4'b0100);
    for (int d = 0; d < 4; d++) send_pkt(2'(d), 3);
    drain();
    read_expect(A_DROP_CNT, 32'(want_nr + 2), "DROP_CNT after flipping the table");
    end_check();
  endtask

  // C06: both drop counters saturate at 255, and a write clears them.
  task automatic c06_counters();
    begin_check(6, "counters");
    setup(4'b0000, 4'b0000);
    for (int i = 0; i < 300; i++) send_pkt(2'(i), 1);
    read_expect(A_DROP_CNT, 32'h0000_00FF, "DROP_CNT after 300 NOROUTE drops");
    apb_write(A_DROP_CNT, 32'h0);
    read_expect(A_DROP_CNT, 32'h0, "DROP_CNT after a write");
    // FULL: hold output 0, fill it to 9 beats, then 300 more packets.
    set_ready(0, 1);
    set_route(0, 1, 0);
    idle(2);
    for (int i = 0; i < 9; i++) send_pkt(2'd0, 1);
    for (int i = 0; i < 300; i++) send_pkt(2'd0, 1);
    read_expect(A_DROP_CNT, 32'h0000_FF00, "DROP_CNT after 300 FULL drops");
    apb_write(A_DROP_CNT, 32'h1234_5678);
    read_expect(A_DROP_CNT, 32'h0, "DROP_CNT after a write of 0x12345678");
    end_check();
  endtask

  // Drive an APB write and a one-beat packet so that the write completes at
  // the same edge as the packet's handshake.
  task automatic write_with_packet(input logic [7:0] a, input logic [31:0] d, input bit [7:0] hdr);
    psel = 1'b1; penable = 1'b0; pwrite = 1'b1; paddr = a; pwdata = d;
    tick();
    penable  = 1'b1;
    in_valid = 1'b1; in_data = hdr; in_last = 1'b1;
    @(negedge clk);
    if (!pready || !in_ready) fail("write_with_packet: the write and the packet did not line up");
    tick();
    psel = 1'b0; penable = 1'b0;
    in_valid = 1'b0; in_last = 1'b0;
  endtask

  // C07: an event in the same cycle as a clearing write wins.
  task automatic c07_same_cycle();
    begin_check(7, "same_cycle");
    setup(4'b0000, 4'b0000);
    for (int i = 0; i < 5; i++) send_pkt(2'd0, 1);
    read_expect(A_DROP_CNT, 32'h5, "DROP_CNT after 5 drops");
    write_with_packet(A_DROP_CNT, 32'h0, 8'h00);
    read_expect(A_DROP_CNT, 32'h1, "DROP_CNT cleared in the same cycle as a drop");
    read_expect(A_STATUS, 32'h1, "STATUS before the W1C race");
    write_with_packet(A_STATUS, 32'h1, 8'h00);
    read_expect(A_STATUS, 32'h1, "STATUS.NOROUTE cleared in the same cycle as a NOROUTE drop");
    apb_write(A_STATUS, 32'h1);
    read_expect(A_STATUS, 32'h0, "STATUS after a plain W1C");
    end_check();
  endtask

  // Make all three STATUS bits 1: a NOROUTE drop, a FULL drop and an oversize packet.
  task automatic make_all_events();
    setup(4'b0001, 4'b0000);   // only DST 0, to out0
    set_ready(0, 1);
    idle(2);
    send_pkt(2'd1, 1);         // NOROUTE
    send_pkt(2'd0, 9);         // OVERSIZE, cut to 8 beats: level 8
    send_pkt(2'd0, 1);         // admitted at level 8: level 9
    send_pkt(2'd0, 1);         // FULL
  endtask

  // C08: W1C clears only the bits written as 1.
  task automatic c08_w1c();
    begin_check(8, "w1c");
    make_all_events();
    read_expect(A_STATUS, 32'h7, "STATUS with all three events");
    apb_write(A_STATUS, 32'h2); read_expect(A_STATUS, 32'h5, "STATUS after writing 0x2");
    apb_write(A_STATUS, 32'h0); read_expect(A_STATUS, 32'h5, "STATUS after writing 0x0");
    apb_write(A_STATUS, 32'h4); read_expect(A_STATUS, 32'h1, "STATUS after writing 0x4");
    apb_write(A_STATUS, 32'hFFFF_FFF8); read_expect(A_STATUS, 32'h1, "STATUS after writing 0xFFFFFFF8");
    apb_write(A_STATUS, 32'h1); read_expect(A_STATUS, 32'h0, "STATUS after writing 0x1");
    end_check();
  endtask

  // C09: irq is STATUS AND INT_EN, bit by bit.
  task automatic c09_interrupt();
    begin_check(9, "interrupt");
    setup(4'b0001, 4'b0000);
    send_pkt(2'd1, 1);                     // NOROUTE, INT_EN still 0
    idle(3);
    expect_eq(irq, 0, "irq with STATUS.NOROUTE set and INT_EN = 0");
    apb_write(A_INT_EN, 32'h6);  idle(1);
    expect_eq(irq, 0, "irq with STATUS = 1 and INT_EN = 6");
    apb_write(A_INT_EN, 32'h1);  idle(1);
    expect_eq(irq, 1, "irq with STATUS = 1 and INT_EN = 1");
    apb_write(A_STATUS, 32'h1);  idle(1);
    expect_eq(irq, 0, "irq after clearing STATUS");
    apb_write(A_INT_EN, 32'h4);
    send_pkt(2'd0, 12);                    // OVERSIZE
    idle(1);
    expect_eq(irq, 1, "irq with STATUS = 4 and INT_EN = 4");
    apb_write(A_INT_EN, 32'h3);  idle(1);
    expect_eq(irq, 0, "irq with STATUS = 4 and INT_EN = 3");
    apb_write(A_INT_EN, 32'h7);
    apb_write(A_STATUS, 32'h7);  idle(1);
    expect_eq(irq, 0, "irq after clearing every STATUS bit");
    end_check();
  endtask

  // C10: the admission rule at its boundary: a level of exactly 8 admits, 9
  // doesn't, and an output can hold 16.
  task automatic c10_admission();
    begin_check(10, "admission");
    setup(4'b0011, 4'b0010);
    set_ready(0, 1);
    idle(2);
    send_pkt(2'd0, 8);                     // level 0 -> 8
    send_pkt(2'd0, 8);                     // admitted at exactly 8 -> 16
    send_pkt(2'd0, 1);                     // dropped at 16
    read_expect(A_LEVEL, 32'h10, "LEVEL with output 0 full");
    read_expect(A_DROP_CNT, 32'h100, "DROP_CNT after one FULL drop");
    send_pkt(2'd1, 8);                     // output 1 is unaffected
    drain();
    expect_eq(n_pkt_out[0], 2, "packets out of output 0");
    expect_eq(n_pkt_out[1], 1, "packets out of output 1");
    // Nine one-beat packets fill to 9 (admitted at 0..8); the tenth is dropped.
    set_ready(0, 1);
    idle(2);
    for (int i = 0; i < 10; i++) send_pkt(2'd0, 1);
    read_expect(A_LEVEL, 32'h9, "LEVEL after ten one-beat packets");
    read_expect(A_DROP_CNT, 32'h200, "DROP_CNT after the tenth packet");
    end_check();
  endtask

  // C11: a disabled route whose output is full counts as NOROUTE only.
  task automatic c11_drop_reasons();
    begin_check(11, "drop_reasons");
    setup(4'b0001, 4'b0000);               // DST 1 disabled, PORT 0
    set_ready(0, 1);
    idle(2);
    for (int i = 0; i < 9; i++) send_pkt(2'd0, 1);    // level 9
    send_pkt(2'd1, 2);                     // disabled, and its output is full
    read_expect(A_DROP_CNT, 32'h001, "DROP_CNT after a NOROUTE drop on a full output");
    read_expect(A_STATUS, 32'h1, "STATUS after a NOROUTE drop on a full output");
    send_pkt(2'd0, 2);                     // enabled and full
    read_expect(A_DROP_CNT, 32'h101, "DROP_CNT after a FULL drop");
    read_expect(A_STATUS, 32'h3, "STATUS after both drops");
    end_check();
  endtask

  // C12: packets longer than 8 beats are cut, flagged once, and don't
  // disturb the next packet.
  task automatic c12_oversize();
    begin_check(12, "oversize");
    setup(4'b0011, 4'b0010);               // DST 1 -> out1
    send_pkt(2'd0, 8);
    idle(2);
    read_expect(A_STATUS, 32'h0, "STATUS after an 8-beat packet");
    send_pkt(2'd0, 9);
    send_pkt(2'd1, 2);
    send_pkt(2'd0, 10);
    send_pkt(2'd0, 16);
    send_pkt(2'd0, 23, 30);
    send_pkt(2'd0, 3);
    drain();
    read_expect(A_STATUS, 32'h4, "STATUS after the cut packets");
    expect_eq(n_ev_oversize, 4, "OVERSIZE events (one per long packet)");
    expect_eq(n_out[0], 8 + 8 + 8 + 8 + 8 + 3, "beats out of output 0");
    expect_eq(n_pkt_out[0], 6, "packets out of output 0");
    // A long packet for a disabled route: dropped and still flagged.
    apb_write(A_STATUS, 32'h7);
    set_route(2, 0, 0);
    send_pkt(2'd2, 11);
    send_pkt(2'd0, 2);
    drain();
    read_expect(A_STATUS, 32'h5, "STATUS after a long packet for a disabled route");
    end_check();
  endtask

  // C13: a long run with both outputs always ready, to wrap every pointer.
  task automatic c13_long_run();
    begin_check(13, "long_run");
    setup(4'b1111, 4'b0110);
    for (int i = 0; i < 200; i++) send_pkt(2'($urandom), $urandom_range(1, 8));
    drain();
    expect_eq(n_pkt_out[0] + n_pkt_out[1], 200, "packets delivered");
    end_check();
  endtask

  // C14: one output stalled while the other flows, then the other way round.
  task automatic c14_independent();
    int got1, got0;
    begin_check(14, "independent");
    setup(4'b0011, 4'b0010);               // DST 0 -> out0, DST 1 -> out1
    for (int stalled = 0; stalled < 2; stalled++) begin
      set_ready(stalled, 1);
      set_ready(1 - stalled, 0);
      idle(2);
      got1 = n_pkt_out[1 - stalled];
      got0 = n_out[stalled];
      for (int i = 0; i < 20; i++) send_pkt(2'(i % 2), 4);
      idle(20);
      expect_eq(n_pkt_out[1 - stalled] - got1, 10,
                $sformatf("packets out of output %0d while output %0d is stalled", 1 - stalled, stalled));
      expect_eq(n_out[stalled] - got0, 0, $sformatf("beats out of stalled output %0d", stalled));
      drain();
    end
    end_check();
  endtask

  // C15: random traffic, random gaps, random stalls on both outputs, and
  // register reads in the middle of it.
  task automatic c15_random();
    begin_check(15, "random");
    setup(4'b1111, 4'b1010);
    set_ready(0, 2, 60);
    set_ready(1, 2, 25);
    fork
      for (int i = 0; i < 400; i++) send_pkt(2'($urandom), $urandom_range(1, 8), 20);
      begin
        logic [31:0] d;
        bit err;
        for (int i = 0; i < 300; i++) begin
          case ($urandom_range(3))
            0: apb_read(A_LEVEL, d, err);
            1: apb_read(A_DROP_CNT, d, err);
            2: apb_read(A_STATUS, d, err);
            default: apb_write(A_STATUS, 32'($urandom_range(7)));
          endcase
          idle($urandom_range(4));
        end
      end
    join
    drain();
    end_check();
  endtask

  // C16: clearing CTRL.EN in the middle of a packet stops the input only at
  // the end of that packet.
  task automatic c16_enable();
    int hs0;
    begin_check(16, "enable");
    setup(4'b0001, 4'b0000);
    fork
      send_pkt(2'd0, 8, 50);
      begin
        while (n_in_hs < 2) tick();
        apb_write(A_CTRL, 32'h0);
        if (n_in_hs >= 8) fail("setup: the packet ended before EN was cleared");
      end
    join
    drain();
    expect_eq(n_out[0], 8, "beats out after EN was cleared mid-packet");
    hs0 = n_in_hs;
    fork
      send_pkt(2'd0, 3);
      begin
        idle(20);
        expect_eq(n_in_hs - hs0, 0, "handshakes while CTRL.EN is 0");
        apb_write(A_CTRL, 32'h1);
      end
    join
    drain();
    expect_eq(n_out[0], 11, "beats out after EN was set again");
    end_check();
  endtask

  // C17: changing the routing table in the middle of a packet affects only
  // later packets.
  task automatic c17_config_midpacket();
    begin_check(17, "config_midpacket");
    setup(4'b0001, 4'b0000);
    fork
      send_pkt(2'd0, 8, 70);
      begin
        while (n_in_hs < 1) tick();
        set_route(0, 1, 1);                // move DST 0 to out1
        set_route(0, 0, 1);                // then disable it
        if (n_in_hs >= 8) fail("setup: the packet ended before the table changed");
      end
    join
    send_pkt(2'd0, 2);                     // dropped: DST 0 is now disabled
    drain();
    expect_eq(n_pkt_out[0], 1, "packets out of output 0");
    expect_eq(n_pkt_out[1], 0, "packets out of output 1");
    read_expect(A_DROP_CNT, 32'h1, "DROP_CNT");
    end_check();
  endtask

  // C18: reset with beats waiting on both outputs and a packet half sent.
  task automatic c18_reset_midpacket();
    begin_check(18, "reset_midpacket");
    setup(4'b0011, 4'b0010);
    set_ready(0, 1);
    set_ready(1, 1);
    idle(2);
    send_pkt(2'd0, 3);
    send_pkt(2'd1, 2);
    fork
      send_pkt(2'd0, 8);
      begin
        while (n_in_hs < 3) tick();
        do_reset();
      end
    join
    // Straight after reset: nothing valid, nothing ready, registers at reset.
    expect_eq(out0_valid, 0, "out0_valid after a reset with a beat waiting");
    expect_eq(out1_valid, 0, "out1_valid after a reset with a beat waiting");
    expect_eq(in_ready, 0, "in_ready after reset");
    read_expect(A_LEVEL, 0, "LEVEL after reset");
    read_expect(A_CTRL, 0, "CTRL after reset");
    read_expect(A_ROUTE0, 0, "ROUTE0 after reset");
    // Release the outputs: nothing old may come out.
    set_ready(0, 0);
    set_ready(1, 0);
    idle(20);
    expect_eq(n_out[0] + n_out[1], 0, "beats out after reset");
    // A new packet: its first beat must be taken as a header.
    setup(4'b0010, 4'b0010);
    send_pkt(2'd1, 5);
    drain();
    expect_eq(n_pkt_out[1], 1, "packets out of output 1 after reset");
    end_check();
  endtask

  // C19: APB timing. A read returns the value from its first access cycle,
  // even when the register changes before the second.
  task automatic c19_apb_timing();
    logic [31:0] d;
    bit err;
    time t0;
    begin_check(19, "apb_timing");
    setup(4'b0001, 4'b0000);
    set_ready(0, 1);
    idle(2);
    // A write: setup, then one access cycle. A read: setup, then two.
    t0 = $time;
    apb_write(A_INT_EN, 32'h1);
    expect_eq(($time - t0) / 10, 2, "clock cycles for a write");
    t0 = $time;
    apb_read(A_INT_EN, d, err);
    expect_eq(($time - t0) / 10, 3, "clock cycles for a read");
    // Read LEVEL while a header is taken at the edge that ends the read's
    // first access cycle: the read must return the old level, 0.
    psel = 1'b1; penable = 1'b0; pwrite = 1'b0; paddr = A_LEVEL;
    tick();
    penable  = 1'b1;
    in_valid = 1'b1; in_data = 8'h00; in_last = 1'b1;
    @(negedge clk);
    expect_eq(pready, 0, "PREADY in the first access cycle of a read");
    expect_eq(in_ready, 1, "in_ready in the first access cycle of the read");
    tick();
    in_valid = 1'b0; in_last = 1'b0;
    @(negedge clk);
    expect_eq(pready, 1, "PREADY in the second access cycle of a read");
    expect_eq(prdata, 0, "LEVEL read while a beat arrives");
    tick();
    psel = 1'b0; penable = 1'b0;
    idle(1);
    read_expect(A_LEVEL, 1, "LEVEL one read later");
    end_check();
  endtask

  // ==== Main ===========================================================================

  int trace_fd;

  initial begin : main
    string vcd, trace;
    int failed;

    void'($urandom(105));
    cur = 0; cyc = 0; abort_tx = 0;
    m_beats = 0; m_reads = 0; m_writes = 0;
    rst_n = 1'b0;
    psel = 0; penable = 0; pwrite = 0; paddr = 0; pwdata = 0;
    in_valid = 0; in_last = 0; in_data = 0;
    set_ready(0, 0);
    set_ready(1, 0);
    foreach (chk_fail[i]) chk_fail[i] = 0;
    model_reset();

    if (!$value$plusargs("vcd=%s", vcd)) vcd = "directed.vcd";
    $dumpfile(vcd);
    $dumpvars(0, tb_directed);
    trace_fd = 0;
    if ($value$plusargs("trace=%s", trace)) trace_fd = $fopen(trace, "w");

    tick();
    c01_reset_values();
    c02_reg_readback();
    c03_bad_address();
    c04_routing();
    c05_disabled_route();
    c06_counters();
    c07_same_cycle();
    c08_w1c();
    c09_interrupt();
    c10_admission();
    c11_drop_reasons();
    c12_oversize();
    c13_long_run();
    c14_independent();
    c15_random();
    c16_enable();
    c17_config_midpacket();
    c18_reset_midpacket();
    c19_apb_timing();

    failed = 0;
    $display("");
    for (int n = 1; n <= NCHK; n++) begin
      $display("CHECK C%02d %-17s %s", n, chk_name[n],
               chk_fail[n] == 0 ? "PASS" : $sformatf("FAIL (%0d)", chk_fail[n]));
      failed += (chk_fail[n] != 0);
    end
    if (chk_fail[0] != 0) $display("CHECK between checks: FAIL (%0d)", chk_fail[0]);
    $display("DIRECTED: %0d edges; the model compared %0d output beats, %0d reads and %0d writes",
             cyc, m_beats, m_reads, m_writes);
    if (trace_fd != 0) $fclose(trace_fd);
    if (failed == 0 && chk_fail[0] == 0) begin
      $display("DIRECTED: PASS (%0d checks)", NCHK);
      $finish;
    end else begin
      $display("DIRECTED: FAIL (%0d of %0d checks)", failed, NCHK);
      $fatal(1, "DIRECTED: FAIL");
    end
  end

  // Every port of the router, every cycle, for comparing two runs.
  always @(posedge clk) begin : tracer
    if (trace_fd != 0)
      $fwrite(trace_fd, "%0t %b %b%b%b %h %h %h %b%b %b | %b%b %h %b | %b%b %h %b | %b%b %h %b\n",
              $time, rst_n, psel, penable, pwrite, paddr, pwdata, prdata, pready, pslverr, irq,
              in_valid, in_ready, in_data, in_last,
              out0_valid, out0_ready, out0_data, out0_last,
              out1_valid, out1_ready, out1_data, out1_last);
  end

  initial begin : watchdog
    #20ms;
    $fatal(1, "DIRECTED: FAIL (timed out)");
  end

endmodule

`default_nettype wire
