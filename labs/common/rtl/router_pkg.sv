// router_pkg.sv
//
// Sizes, register offsets and shared types for the DD105 packet router.
// Every number here is also in docs/reference/router-spec.md, which is the
// document a testbench is written from. If you change one, change the other.

`default_nettype none

package router_pkg;

  // ---- The packet stream ---------------------------------------------------

  // One beat of a packet is one byte. The first beat of every packet is the
  // header, and its top two bits (DST) pick an entry in the routing table.
  localparam int unsigned DATA_W = 8;
  localparam int unsigned DST_W  = 2;
  localparam int unsigned NUM_DST = 1 << DST_W;      // 4 routing table entries

  // The longest packet the router forwards, header included. A longer packet
  // is cut to this length (see router_ingress.sv).
  localparam int unsigned MAX_LEN = 8;
  localparam int unsigned BEAT_W  = $clog2(MAX_LEN); // counts beats 0..7

  // ---- The output buffers --------------------------------------------------

  // Each output holds up to DEPTH beats: DEPTH-1 in a small RAM and one more
  // in the register that drives the output pins (see router_fifo.sv).
  localparam int unsigned DEPTH   = 16;
  localparam int unsigned LEVEL_W = $clog2(DEPTH + 1); // 0..16 needs 5 bits

  // A packet is admitted to an output only if that output has room for a
  // packet of MAX_LEN beats, so a packet that has been admitted always fits.
  // With DEPTH = 16 and MAX_LEN = 8 that means a level of 8 or less.
  localparam int unsigned ADMIT_MAX = DEPTH - MAX_LEN;

  // ---- The register port (APB) ---------------------------------------------

  localparam int unsigned PADDR_W = 8;
  localparam int unsigned PDATA_W = 32;

  // Register offsets are byte addresses. Bits [1:0] of a legal address are
  // always 0, so the decoder compares word numbers, PADDR[7:2].
  localparam logic [PADDR_W-3:0] W_ID       = 6'h00;  // 0x00
  localparam logic [PADDR_W-3:0] W_CTRL     = 6'h01;  // 0x04
  localparam logic [PADDR_W-3:0] W_STATUS   = 6'h02;  // 0x08
  localparam logic [PADDR_W-3:0] W_INT_EN   = 6'h03;  // 0x0C
  localparam logic [PADDR_W-3:0] W_DROP_CNT = 6'h04;  // 0x10
  localparam logic [PADDR_W-3:0] W_LEVEL    = 6'h05;  // 0x14
  localparam logic [PADDR_W-3:0] W_ROUTE0   = 6'h08;  // 0x20
  localparam logic [PADDR_W-3:0] W_ROUTE1   = 6'h09;  // 0x24
  localparam logic [PADDR_W-3:0] W_ROUTE2   = 6'h0A;  // 0x28
  localparam logic [PADDR_W-3:0] W_ROUTE3   = 6'h0B;  // 0x2C

  // What the read-only ID register returns: design 105, revision 1.
  localparam logic [PDATA_W-1:0] ID_VALUE = 32'hD105_0001;

  // ---- Events --------------------------------------------------------------

  // Bit positions in STATUS and INT_EN. Each event is a one-cycle pulse from
  // the ingress that sets its STATUS bit.
  localparam int unsigned EV_NOROUTE  = 0;  // dropped: the route is disabled
  localparam int unsigned EV_FULL     = 1;  // dropped: no room on its output
  localparam int unsigned EV_OVERSIZE = 2;  // a packet longer than MAX_LEN
  localparam int unsigned NUM_EV      = 3;

  // The drop counters saturate at 255.
  localparam int unsigned CNT_W = 8;

  // ---- Ingress state -------------------------------------------------------

  typedef enum logic [1:0] {
    ST_HEAD = 2'd0,  // between packets: the next beat is a header
    ST_FWD  = 2'd1,  // forwarding the rest of an admitted packet
    ST_DROP = 2'd2,  // discarding the rest of a dropped packet
    ST_TAIL = 2'd3   // discarding what is left of a packet cut at MAX_LEN
  } ingress_state_e;

endpackage

`default_nettype wire
