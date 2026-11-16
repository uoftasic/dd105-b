// File: verilator_nba_repro.sv
//
// On Verilator 5.050, two nonblocking assignments to one signal in the same
// time step are committed in source order, not in the order they ran, when a
// timing control separates the two statements. xfer() raises a, waits for an edge
// and lowers it, the way a module-level driver task in a directed testbench does.
// Called three times in a row from a repeat loop, it should leave a high at three
// rising edges: each call's a <= 1 runs after the previous call's a <= 0, in the
// same time step, and wins. The same pattern in class code, in an interface task
// called from a class, and in UVM drivers gave 3 of 3; three calls written out
// one after another also gave 3 of 3 (../selftest/nba/nba_repro.sv pins them all).
//
// Observed in asic-edu/gui-rig:2026.08, from this folder:
//   $ verilator --binary --timing verilator_nba_repro.sv
//   $ obj_dir/Vverilator_nba_repro  ->  a high at 1 of 3 edges (LRM: 3)
//   $ iverilog -g2012 -o nba.vvp verilator_nba_repro.sv && vvp -n nba.vvp
//                                   ->  a high at 3 of 3 edges (LRM: 3)
// (Verilator 5.050 rev v5.050; Icarus Verilog 14.0 devel.)
// A comment line must not start with the word "verilator": Verilator reads
// it as a pragma and stops with BADVLTPRAGMA.
//
// A clocking-block drive, a blocking assignment 1 ns after the edge, or a
// task that leaves the trailing a <= 0 to its caller all give 3 of 3.

module verilator_nba_repro;
  logic clk = 1'b0, a = 1'b0;
  int   seen = 0;
  always #5 clk = ~clk;
  always @(posedge clk) seen += int'(a);
  task automatic xfer(); a <= 1'b1; @(posedge clk); a <= 1'b0; endtask
  initial begin
    @(posedge clk);
    repeat (3) xfer();
    @(posedge clk);
    $display("a high at %0d of 3 edges (LRM: 3)", seen);
    $finish;
  end
endmodule
