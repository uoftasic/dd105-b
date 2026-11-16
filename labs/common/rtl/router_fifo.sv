// router_fifo.sv
//
// One output buffer of the router, and the valid/ready stream it drives.
//
// The buffer holds up to DEPTH (16) beats. DEPTH-1 of them sit in a small RAM,
// and the oldest one sits in an output register that drives out_valid,
// out_data and out_last straight from flip-flops. That register is what keeps
// the output stable while the sink holds out_ready low: nothing is allowed to
// load it until the beat in it has been taken.
//
// A beat moves from the RAM into the output register when the RAM is not
// empty and the register is either empty or being emptied in this cycle
// (out_valid && out_ready). So a stream that is never stalled moves one beat
// per cycle, and a beat pushed into an empty buffer in cycle n is on the
// output pins from cycle n + 2.
//
// `level` counts every beat in the buffer, RAM and output register together.
// It goes up by one for each push and down by one for each handshake on the
// output, and is what the ingress checks before it admits a packet.
//
// Nothing here guards against a push when the buffer is full. It can't
// happen: the ingress admits a packet only when level <= DEPTH - MAX_LEN, and
// no packet writes more than MAX_LEN beats. The output register also means
// the RAM never needs all 16 entries, as explained at RAM_DEPTH below.

`default_nettype none

module router_fifo
  import router_pkg::*;
(
  input  wire                clk,
  input  wire                rst_n,

  // Write side, from the ingress. One beat per cycle at most.
  input  wire                push,
  input  wire [DATA_W-1:0]   wr_data,
  input  wire                wr_last,

  // The output stream.
  output logic               out_valid,
  input  wire                out_ready,
  output logic [DATA_W-1:0]  out_data,
  output logic               out_last,

  // Beats held, 0 to DEPTH.
  output logic [LEVEL_W-1:0] level
);

  // The RAM has one entry fewer than the buffer, because the output register
  // is the sixteenth. The RAM can't overflow: while the output register is
  // empty the RAM holds at most one beat (it was empty last cycle, or the
  // register would have loaded), and while the register is full the RAM
  // holds level - 1 <= 15.
  localparam int unsigned RAM_DEPTH = DEPTH - 1;
  localparam int unsigned PTR_W     = $clog2(RAM_DEPTH);
  localparam logic [PTR_W-1:0] PTR_LAST = PTR_W'(RAM_DEPTH - 1);

  logic [DATA_W:0]      ram [RAM_DEPTH];   // {last, data}
  logic [PTR_W-1:0]     wr_ptr_q;          // next entry to write
  logic [PTR_W-1:0]     rd_ptr_q;          // oldest entry
  logic [LEVEL_W-1:0]   count_q;           // entries in use in the RAM

  logic                 ovalid_q;          // the output register holds a beat
  logic [DATA_W-1:0]    odata_q;
  logic                 olast_q;

  // Move the oldest RAM entry into the output register in this cycle.
  logic load;
  assign load = (count_q != '0) && (!ovalid_q || out_ready);

  // ---- RAM ----------------------------------------------------------------

  // No reset: an entry is read only after it has been written.
  always_ff @(posedge clk) begin
    if (push) ram[wr_ptr_q] <= {wr_last, wr_data};
  end

  // ---- Pointers, count and output valid ------------------------------------

  // RAM_DEPTH is 15, not a power of two, so both pointers wrap by hand.
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      wr_ptr_q <= '0;
      rd_ptr_q <= '0;
      count_q  <= '0;
      ovalid_q <= 1'b0;
    end else begin
      if (push) wr_ptr_q <= (wr_ptr_q == PTR_LAST) ? '0 : wr_ptr_q + 1'b1;
      if (load) rd_ptr_q <= (rd_ptr_q == PTR_LAST) ? '0 : rd_ptr_q + 1'b1;

      count_q <= count_q + LEVEL_W'(push) - LEVEL_W'(load);

      // The register is full after a load. Otherwise it empties when its
      // beat is taken, and keeps the beat for as long as out_ready is low.
      if (load)           ovalid_q <= 1'b1;
      else if (out_ready) ovalid_q <= 1'b0;
    end
  end

  // ---- Output register data -------------------------------------------------

  // No reset: out_data and out_last mean nothing while out_valid is low.
  always_ff @(posedge clk) begin
    if (load) {olast_q, odata_q} <= ram[rd_ptr_q];
  end

  assign out_valid = ovalid_q;
  assign out_data  = odata_q;
  assign out_last  = olast_q;

  assign level = count_q + LEVEL_W'(ovalid_q);

endmodule

`default_nettype wire
