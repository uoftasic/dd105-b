// router_ingress.sv
//
// The input side of the router: it takes packets from the input stream, looks
// up each packet's route when its header arrives, and either writes the whole
// packet into one output buffer or drops the whole packet.
//
// The decision is made once per packet, in the cycle the header is accepted,
// from the values the routing table and the two buffer levels have in that
// cycle. The header's DST field (bits 7:6) selects a routing table entry:
//
//   - entry disabled               -> drop the packet, NOROUTE event
//   - entry enabled, no room       -> drop the packet, FULL event
//   - entry enabled, room          -> write the packet to the entry's output
//
// "Room" means the chosen output holds ADMIT_MAX (8) beats or fewer, so it has
// space for a packet of the maximum length. A dropped packet is still taken
// from the input, beat by beat, so the input never waits on a full output.
//
// A packet longer than MAX_LEN (8) beats is cut: the router keeps its first
// 8 beats, marks the 8th as the last, raises an OVERSIZE event, and discards
// the rest of the input packet up to and including its in_last beat.
//
// in_ready is high in the middle of a packet, always, and between packets
// only while CTRL.EN is 1. Clearing EN therefore stops the input at the next
// packet boundary and never cuts a packet in two.

`default_nettype none

module router_ingress
  import router_pkg::*;
(
  input  wire                 clk,
  input  wire                 rst_n,

  // Configuration, from the registers.
  input  wire                 en,          // CTRL.EN
  input  wire [NUM_DST-1:0]   route_en,    // ROUTEn.EN
  input  wire [NUM_DST-1:0]   route_port,  // ROUTEn.PORT

  // How many beats each output buffer holds right now.
  input  wire [LEVEL_W-1:0]   level0,
  input  wire [LEVEL_W-1:0]   level1,

  // The input stream.
  input  wire                 in_valid,
  output logic                in_ready,
  input  wire [DATA_W-1:0]    in_data,
  input  wire                 in_last,

  // Writes into the output buffers. At most one of push0, push1 is high.
  output logic                push0,
  output logic                push1,
  output logic [DATA_W-1:0]   wr_data,
  output logic                wr_last,

  // One-cycle events, for STATUS and the drop counters.
  output logic                ev_noroute,
  output logic                ev_full,
  output logic                ev_oversize
);

  ingress_state_e     state_q;
  logic               port_q;      // the output of the packet being forwarded
  logic [BEAT_W-1:0]  beat_q;      // beats of this packet accepted so far

  // ---- Handshake -----------------------------------------------------------

  logic hs;        // a beat moves on the input in this cycle
  logic at_head;   // and it is a header

  assign in_ready = (state_q != ST_HEAD) || en;
  assign hs       = in_valid && in_ready;
  assign at_head  = (state_q == ST_HEAD);

  // ---- Route lookup --------------------------------------------------------

  // These are computed every cycle from whatever is on in_data, but they are
  // used only when the beat is a header.
  logic [DST_W-1:0]   dst;
  logic               lkp_en;
  logic               lkp_port;
  logic [LEVEL_W-1:0] lkp_level;
  logic               room;
  logic               admit;

  assign dst       = in_data[7:6];
  assign lkp_en    = route_en[dst];
  assign lkp_port  = route_port[dst];
  assign lkp_level = lkp_port ? level1 : level0;
  assign room      = (lkp_level <= LEVEL_W'(ADMIT_MAX));
  assign admit     = lkp_en && room;

  // ---- Length limit --------------------------------------------------------

  // at_max: this is the MAX_LEN-th beat of the packet. If it isn't also the
  // packet's last beat, the packet is oversize. Beats are no longer counted
  // once a packet has been cut (ST_TAIL), so one packet raises one event.
  logic at_max;
  logic counting;

  assign at_max   = (beat_q == BEAT_W'(MAX_LEN - 1));
  assign counting = (state_q != ST_TAIL);

  // ---- Writes into the buffers ---------------------------------------------

  logic fwd;        // this beat goes into a buffer
  logic cur_port;   // and this is the buffer

  assign fwd      = hs && (at_head ? admit : (state_q == ST_FWD));
  assign cur_port = at_head ? lkp_port : port_q;
  assign push0    = fwd && !cur_port;
  assign push1    = fwd &&  cur_port;
  assign wr_data  = in_data;
  assign wr_last  = in_last || at_max;   // the 8th beat always ends the packet

  // ---- Events --------------------------------------------------------------

  assign ev_noroute  = hs && at_head && !lkp_en;
  assign ev_full     = hs && at_head && lkp_en && !room;
  assign ev_oversize = hs && counting && at_max && !in_last;

  // ---- Packet state --------------------------------------------------------

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state_q <= ST_HEAD;
      port_q  <= 1'b0;
      beat_q  <= '0;
    end else if (hs) begin
      if (in_last) begin
        // The packet is over, whatever state it was in.
        state_q <= ST_HEAD;
        beat_q  <= '0;
      end else if (counting && at_max) begin
        // The 8th beat, and the packet goes on: discard the rest.
        state_q <= ST_TAIL;
      end else begin
        if (counting) beat_q <= beat_q + 1'b1;
        if (at_head) begin
          // The decision for the whole packet, made once, here.
          if (admit) state_q <= ST_FWD;
          else       state_q <= ST_DROP;
          port_q  <= lkp_port;
        end
      end
    end
  end

endmodule

`default_nettype wire
