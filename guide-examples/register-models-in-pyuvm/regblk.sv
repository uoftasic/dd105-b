// DD105-B guide example, "Register models in pyuvm": the design.
//
// Four 16-bit registers on a one-cycle bus. A transfer is one cycle with sel
// at 1: the block answers in that cycle (rdata is combinational), and a write
// takes effect at the rising edge that ends it. An address with no register
// reads 0, and a write to it changes nothing.
//
//   0x0  ID     RO   [15:0] reads 105B
//   0x4  CTRL   RW   [0] EN, [3:1] MODE; resets to 0
//   0x8  FLAGS  W1C  [0] OVF, [1] ERR: set by a pulse on ev_ovf or ev_err;
//                    writing 1 clears a bit, and an event in the same cycle wins
//   0xC  COUNT  WC   [7:0] events since the last write; any write clears it
//
// Two planted bugs, chosen at run time with +BUG=<name>:
//
//   en_reset_1  CTRL.EN resets to 1
//   mode_stuck  bit 3 of CTRL can't be set

module regblk (
  input  logic        clk,
  input  logic        rst_n,
  input  logic        sel,
  input  logic        wr,
  input  logic [3:0]  addr,
  input  logic [15:0] wdata,
  output logic [15:0] rdata,
  input  logic        ev_ovf,
  input  logic        ev_err
);
  bit    bug_en_reset_1, bug_mode_stuck;
  string bug;
  initial begin
    if (!$value$plusargs("BUG=%s", bug)) bug = "none";
    bug_en_reset_1 = (bug == "en_reset_1");
    bug_mode_stuck = (bug == "mode_stuck");
  end

  logic [3:0] ctrl;
  logic [1:0] flags;
  logic [7:0] count;

  always_comb
    case (addr)
      4'h0:    rdata = 16'h105B;
      4'h4:    rdata = {12'd0, ctrl};
      4'h8:    rdata = {14'd0, flags};
      4'hC:    rdata = {8'd0, count};
      default: rdata = 16'd0;
    endcase

  wire wr_ctrl  = sel && wr && addr == 4'h4;
  wire wr_flags = sel && wr && addr == 4'h8;
  wire wr_count = sel && wr && addr == 4'hC;

  always_ff @(posedge clk or negedge rst_n)
    if (!rst_n) begin
      ctrl  <= {3'd0, bug_en_reset_1};
      flags <= 2'd0;
      count <= 8'd0;
    end else begin
      if (wr_ctrl) ctrl <= wdata[3:0] & (bug_mode_stuck ? 4'b0111 : 4'b1111);
      flags <= (flags & ~(wr_flags ? wdata[1:0] : 2'b00)) | {ev_err, ev_ovf};
      if (wr_count)              count <= 8'd0;
      else if (ev_ovf || ev_err) count <= count + 8'd1;
    end
endmodule
