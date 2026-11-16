// router_regs.sv
//
// The APB register port and every register behind it.
//
// APB transfers. A transfer is a setup cycle (PSEL high, PENABLE low) and
// then an access phase (PSEL and PENABLE high) that lasts until PREADY is
// high. Writes take one access cycle: PREADY is high in the first, and the
// register changes at the clock edge that ends it. Reads take two: PREADY is
// low in the first access cycle, while the read data is captured into a
// register, and high in the second, when PRDATA is driven from that register.
// So a read returns the value the register had in the first access cycle.
//
// Errors. An address that isn't a register in the map, or isn't a multiple of
// 4, completes with PSLVERR high. A bad write changes nothing; a bad read
// returns 0. Writing a read-only register, or the reserved bits of any
// register, is not an error: the write is ignored.
//
// Register map (byte addresses):
//
//   0x00  ID        RO   reads 0xD105_0001
//   0x04  CTRL      RW   [0] EN
//   0x08  STATUS    W1C  [0] NOROUTE  [1] FULL  [2] OVERSIZE
//   0x0C  INT_EN    RW   [2:0], one enable per STATUS bit
//   0x10  DROP_CNT  RO, any write clears   [7:0] NOROUTE_CNT  [15:8] FULL_CNT
//   0x14  LEVEL     RO   [4:0] LEVEL0  [12:8] LEVEL1
//   0x20  ROUTE0    RW   [0] EN  [1] PORT
//   0x24  ROUTE1    RW   (as ROUTE0)
//   0x28  ROUTE2    RW   (as ROUTE0)
//   0x2C  ROUTE3    RW   (as ROUTE0)
//
// When a hardware event and a software write to the same bit land in the same
// cycle, the event wins: a STATUS bit that is being set stays 1 even if the
// same write clears it, and a counter cleared by a write while a drop is
// counted reads 1 afterwards. No event is ever lost to a write.

`default_nettype none

module router_regs
  import router_pkg::*;
(
  input  wire                 clk,
  input  wire                 rst_n,

  // APB (PCLK is clk and PRESETn is rst_n).
  input  wire                 psel,
  input  wire                 penable,
  input  wire                 pwrite,
  input  wire [PADDR_W-1:0]   paddr,
  // Lint waiver: PWDATA[31:3] is never read, because no register field sits
  // above bit 2 except in read-only registers, and writes to those are
  // ignored. The unused bits are part of the 32-bit APB port on purpose.
  /* verilator lint_off UNUSEDSIGNAL */
  input  wire [PDATA_W-1:0]   pwdata,
  /* verilator lint_on UNUSEDSIGNAL */
  output logic [PDATA_W-1:0]  prdata,
  output logic                pready,
  output logic                pslverr,

  // Configuration, to the ingress.
  output logic                en,
  output logic [NUM_DST-1:0]  route_en,
  output logic [NUM_DST-1:0]  route_port,

  // Events from the ingress, and the buffer levels.
  input  wire                 ev_noroute,
  input  wire                 ev_full,
  input  wire                 ev_oversize,
  input  wire [LEVEL_W-1:0]   level0,
  input  wire [LEVEL_W-1:0]   level1,

  // The interrupt: high while any enabled STATUS bit is set.
  output logic                irq
);

  // ---- Register state ------------------------------------------------------

  logic                en_q;
  logic [NUM_EV-1:0]   status_q;
  logic [NUM_EV-1:0]   int_en_q;
  logic [CNT_W-1:0]    cnt_noroute_q;
  logic [CNT_W-1:0]    cnt_full_q;
  logic [NUM_DST-1:0]  route_en_q;
  logic [NUM_DST-1:0]  route_port_q;

  // ---- Transfer phase --------------------------------------------------------

  logic access;     // in the access phase
  logic rd_wait_q;  // the first access cycle of a read has passed
  logic rd_first;   // the first access cycle of a read

  assign access   = psel && penable;
  assign rd_first = access && !pwrite && !rd_wait_q;
  assign pready   = !rd_first;

  // ---- Address decode ------------------------------------------------------

  logic [PADDR_W-3:0] word;
  logic               hit;       // the word is a register in the map
  logic               bad_addr;

  assign word = paddr[PADDR_W-1:2];

  always_comb begin
    case (word)
      W_ID, W_CTRL, W_STATUS, W_INT_EN, W_DROP_CNT, W_LEVEL,
      W_ROUTE0, W_ROUTE1, W_ROUTE2, W_ROUTE3: hit = 1'b1;
      default:                                hit = 1'b0;
    endcase
  end

  assign bad_addr = !hit || (paddr[1:0] != 2'b00);
  assign pslverr  = access && pready && bad_addr;

  // A write that does something: a good address, in its (only) access cycle.
  logic wr;
  logic wr_status;
  logic wr_drop_cnt;

  assign wr          = access && pwrite && !bad_addr;
  assign wr_status   = wr && (word == W_STATUS);
  assign wr_drop_cnt = wr && (word == W_DROP_CNT);

  // ---- Read data -------------------------------------------------------------

  logic [PDATA_W-1:0] rdata;

  always_comb begin
    rdata = '0;
    case (word)
      W_ID:       rdata                 = ID_VALUE;
      W_CTRL:     rdata[0]              = en_q;
      W_STATUS:   rdata[NUM_EV-1:0]     = status_q;
      W_INT_EN:   rdata[NUM_EV-1:0]     = int_en_q;
      W_DROP_CNT: rdata[2*CNT_W-1:0]    = {cnt_full_q, cnt_noroute_q};
      W_LEVEL:    rdata[8+LEVEL_W-1:0]  = {level1, 3'b000, level0};
      W_ROUTE0:   rdata[1:0]            = {route_port_q[0], route_en_q[0]};
      W_ROUTE1:   rdata[1:0]            = {route_port_q[1], route_en_q[1]};
      W_ROUTE2:   rdata[1:0]            = {route_port_q[2], route_en_q[2]};
      W_ROUTE3:   rdata[1:0]            = {route_port_q[3], route_en_q[3]};
      default:    rdata                 = '0;
    endcase
  end

  // PRDATA comes from a register loaded in the first access cycle of a read,
  // and keeps that value until the next read.
  logic [PDATA_W-1:0] prdata_q;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      rd_wait_q <= 1'b0;
      prdata_q  <= '0;
    end else begin
      rd_wait_q <= rd_first;
      if (rd_first) prdata_q <= bad_addr ? '0 : rdata;
    end
  end

  assign prdata = prdata_q;

  // ---- Read-write registers --------------------------------------------------

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      en_q          <= 1'b0;
      int_en_q      <= '0;
      route_en_q    <= '0;
      route_port_q  <= '0;
    end else if (wr) begin
      case (word)
        W_CTRL:   en_q     <= pwdata[0];
        W_INT_EN: int_en_q <= pwdata[NUM_EV-1:0];
        W_ROUTE0: {route_port_q[0], route_en_q[0]} <= pwdata[1:0];
        W_ROUTE1: {route_port_q[1], route_en_q[1]} <= pwdata[1:0];
        W_ROUTE2: {route_port_q[2], route_en_q[2]} <= pwdata[1:0];
        W_ROUTE3: {route_port_q[3], route_en_q[3]} <= pwdata[1:0];
        default:  ;
      endcase
    end
  end

  // ---- STATUS: set by events, cleared by writing 1 -----------------------

  logic [NUM_EV-1:0] ev;
  assign ev[EV_NOROUTE]  = ev_noroute;
  assign ev[EV_FULL]     = ev_full;
  assign ev[EV_OVERSIZE] = ev_oversize;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) status_q <= '0;
    else if (wr_status) status_q <= (status_q & ~pwdata[NUM_EV-1:0]) | ev;
    else status_q <= status_q | ev;
  end

  assign irq = |(status_q & int_en_q);

  // ---- DROP_CNT: two saturating counters, cleared by any write --------------

  // The clear happens first and the count second, so a drop in the same cycle
  // as the clearing write leaves the counter at 1.
  function automatic logic [CNT_W-1:0] bump(input logic [CNT_W-1:0] cnt,
                                            input logic inc, input logic clr);
    logic [CNT_W-1:0] next;
    next = clr ? '0 : cnt;
    if (inc && next != '1) next = next + 1'b1;
    return next;
  endfunction

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      cnt_noroute_q <= '0;
      cnt_full_q    <= '0;
    end else begin
      cnt_noroute_q <= bump(cnt_noroute_q, ev_noroute, wr_drop_cnt);
      cnt_full_q    <= bump(cnt_full_q,    ev_full,    wr_drop_cnt);
    end
  end

  // ---- Outputs ---------------------------------------------------------------

  assign en         = en_q;
  assign route_en   = route_en_q;
  assign route_port = route_port_q;

endmodule

`default_nettype wire
