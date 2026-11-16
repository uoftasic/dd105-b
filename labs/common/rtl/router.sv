// router.sv
//
// The DD105 packet router: one input stream, two output streams, and an APB
// register port that configures it. This is the top of the design under test.
//
//                   +-------------+    push0    +-------------+
//   in_* ---------->|   ingress   |------------>| buffer 0    |----> out0_*
//                   | route, drop |    push1    +-------------+
//                   |  and cut    |------------>| buffer 1    |----> out1_*
//                   +-------------+             +-------------+
//                       ^     | events             | levels
//               config  |     v                    v
//   APB <---------->+-----------------------------------+
//                   |      registers                    |----> irq
//                   +-----------------------------------+
//
// Each packet's header picks a routing table entry; the entry says whether
// the route is enabled and which output it uses. The whole packet goes to that
// output, or the whole packet is dropped and counted. The two outputs have
// their own buffers and their own out_ready, so a stalled output never stops
// the other one: packets for a stalled output are dropped once its buffer is
// too full to take a packet of the maximum length.
//
// One clock (clk) and one active-low asynchronous reset (rst_n) serve the
// whole design, the APB port included.
//
// The full specification is docs/reference/router-spec.md.

`default_nettype none

module router
  import router_pkg::*;
(
  input  wire                clk,
  input  wire                rst_n,

  // APB register port: the APB3 signals, one slave select, no PSTRB.
  input  wire                psel,
  input  wire                penable,
  input  wire                pwrite,
  input  wire [PADDR_W-1:0]  paddr,
  input  wire [PDATA_W-1:0]  pwdata,
  output logic [PDATA_W-1:0] prdata,
  output logic               pready,
  output logic               pslverr,

  // Interrupt, active high, level.
  output logic               irq,

  // Input stream.
  input  wire                in_valid,
  output logic               in_ready,
  input  wire [DATA_W-1:0]   in_data,
  input  wire                in_last,

  // Output stream 0.
  output logic               out0_valid,
  input  wire                out0_ready,
  output logic [DATA_W-1:0]  out0_data,
  output logic               out0_last,

  // Output stream 1.
  output logic               out1_valid,
  input  wire                out1_ready,
  output logic [DATA_W-1:0]  out1_data,
  output logic               out1_last
);

  // Configuration from the registers.
  logic               en;
  logic [NUM_DST-1:0] route_en;
  logic [NUM_DST-1:0] route_port;

  // Events from the ingress.
  logic ev_noroute;
  logic ev_full;
  logic ev_oversize;

  // Writes from the ingress into the buffers, and how full the buffers are.
  logic               push0;
  logic               push1;
  logic [DATA_W-1:0]  wr_data;
  logic               wr_last;
  logic [LEVEL_W-1:0] level0;
  logic [LEVEL_W-1:0] level1;

  router_regs u_regs (
    .clk         (clk),
    .rst_n       (rst_n),
    .psel        (psel),
    .penable     (penable),
    .pwrite      (pwrite),
    .paddr       (paddr),
    .pwdata      (pwdata),
    .prdata      (prdata),
    .pready      (pready),
    .pslverr     (pslverr),
    .en          (en),
    .route_en    (route_en),
    .route_port  (route_port),
    .ev_noroute  (ev_noroute),
    .ev_full     (ev_full),
    .ev_oversize (ev_oversize),
    .level0      (level0),
    .level1      (level1),
    .irq         (irq)
  );

  router_ingress u_ingress (
    .clk         (clk),
    .rst_n       (rst_n),
    .en          (en),
    .route_en    (route_en),
    .route_port  (route_port),
    .level0      (level0),
    .level1      (level1),
    .in_valid    (in_valid),
    .in_ready    (in_ready),
    .in_data     (in_data),
    .in_last     (in_last),
    .push0       (push0),
    .push1       (push1),
    .wr_data     (wr_data),
    .wr_last     (wr_last),
    .ev_noroute  (ev_noroute),
    .ev_full     (ev_full),
    .ev_oversize (ev_oversize)
  );

  router_fifo u_buf0 (
    .clk       (clk),
    .rst_n     (rst_n),
    .push      (push0),
    .wr_data   (wr_data),
    .wr_last   (wr_last),
    .out_valid (out0_valid),
    .out_ready (out0_ready),
    .out_data  (out0_data),
    .out_last  (out0_last),
    .level     (level0)
  );

  router_fifo u_buf1 (
    .clk       (clk),
    .rst_n     (rst_n),
    .push      (push1),
    .wr_data   (wr_data),
    .wr_last   (wr_last),
    .out_valid (out1_valid),
    .out_ready (out1_ready),
    .out_data  (out1_data),
    .out_last  (out1_last),
    .level     (level1)
  );

endmodule

`default_nettype wire
