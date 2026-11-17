// DD105-B guide example, "Reactive agents and backpressure": the design.
//
// A source of numbered beats, 0, 1, 2 and so on. After each handshake it
// leaves its output idle for 1 to 4 cycles, a number it takes from an LFSR,
// then puts the next beat on the output, where the beat stays until the
// sink takes it. The design, not the testbench, decides when each beat
// appears, which is what makes the testbench's sink a reactive agent.

module beat_src (
  input  logic        clk,
  input  logic        rst_n,
  output logic        valid,
  output logic [15:0] data,
  input  logic        ready
);
  logic [7:0] lfsr;     // x^8 + x^6 + x^5 + x^4 + 1
  logic [2:0] idle;     // idle cycles left before the next beat

  always_ff @(posedge clk or negedge rst_n)
    if (!rst_n) begin
      valid <= 1'b0;
      data  <= 16'd0;
      lfsr  <= 8'hA5;
      idle  <= 3'd1;
    end else begin
      lfsr <= {lfsr[6:0], lfsr[7] ^ lfsr[5] ^ lfsr[4] ^ lfsr[3]};
      if (valid && ready) begin
        valid <= 1'b0;
        data  <= data + 16'd1;
        idle  <= {1'b0, lfsr[1:0]} + 3'd1;      // 1 to 4 idle cycles
      end else if (!valid) begin
        if (idle == 3'd1) valid <= 1'b1;
        else              idle  <= idle - 3'd1;
      end
    end
endmodule
