// DD105-B guide example, "Virtual sequences": the design.
//
// A FIFO that holds four 8-bit beats, with a valid/ready stream on each side.
// in_ready is 1 while it has room, out_valid while it holds a beat, and level
// says how many beats it holds. A beat can go in and another come out in the
// same cycle.

module fifo4 (
  input  logic       clk,
  input  logic       rst_n,
  input  logic       in_valid,
  output logic       in_ready,
  input  logic [7:0] in_data,
  output logic       out_valid,
  input  logic       out_ready,
  output logic [7:0] out_data,
  output logic [2:0] level
);
  logic [7:0] mem [4];
  logic [1:0] rd, wr;

  assign in_ready  = level != 3'd4;
  assign out_valid = level != 3'd0;
  assign out_data  = mem[rd];

  wire push = in_valid && in_ready;
  wire pop  = out_valid && out_ready;

  always_ff @(posedge clk or negedge rst_n)
    if (!rst_n) begin
      rd    <= 2'd0;
      wr    <= 2'd0;
      level <= 3'd0;
    end else begin
      if (push) begin
        mem[wr] <= in_data;
        wr      <= wr + 2'd1;
      end
      if (pop) rd <= rd + 2'd1;
      level <= level + {2'd0, push} - {2'd0, pop};
    end
endmodule
