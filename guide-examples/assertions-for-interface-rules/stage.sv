// DD105-B guide example, "Assertions for interface rules": the design.
//
// A one-beat valid/ready stage. It takes a beat from its input when it is
// empty, or when the beat it holds is being taken in the same cycle, and it
// holds each beat on its output until the sink takes it. Its rules are:
//
//   S1  once out_valid is 1, it stays 1 until the handshake
//   S2  while out_valid is 1 and out_ready is 0, out_data doesn't change
//   S3  while the stage is empty (out_valid is 0), in_ready is 1
//
// Two planted bugs, chosen at run time with +BUG=<name> (make run BUG=drop):
//
//   drop    a beat that has waited 4 cycles is thrown away: out_valid falls
//           without a handshake, which breaks S1
//   bubble  in the cycle after each output handshake in_ready is 0, even when
//           that leaves the stage empty, which breaks S3

module stage (
  input  logic       clk,
  input  logic       rst_n,
  input  logic       in_valid,
  output logic       in_ready,
  input  logic [7:0] in_data,
  output logic       out_valid,
  input  logic       out_ready,
  output logic [7:0] out_data
);
  bit    bug_drop, bug_bubble;
  string bug;
  initial begin
    if (!$value$plusargs("BUG=%s", bug)) bug = "none";
    bug_drop   = (bug == "drop");
    bug_bubble = (bug == "bubble");
  end

  logic [2:0] waited;   // cycles the beat on the output has waited so far
  logic       gave;     // there was an output handshake in the last cycle

  assign in_ready = (!out_valid || out_ready) && !(bug_bubble && gave);

  always_ff @(posedge clk or negedge rst_n)
    if (!rst_n) begin
      out_valid <= 1'b0;
      out_data  <= 8'h00;
      waited    <= 3'd0;
      gave      <= 1'b0;
    end else begin
      gave <= out_valid && out_ready;
      if (in_valid && in_ready) begin
        out_valid <= 1'b1;
        out_data  <= in_data;
        waited    <= 3'd0;
      end else if (out_valid && out_ready) begin
        out_valid <= 1'b0;
      end else if (out_valid) begin
        if (bug_drop && waited == 3'd3) out_valid <= 1'b0;   // the planted bug
        else                            waited    <= waited + 3'd1;
      end
    end
endmodule
