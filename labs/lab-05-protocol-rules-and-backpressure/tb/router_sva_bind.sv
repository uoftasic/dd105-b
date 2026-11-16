// DD105-A Lab 05: attach the assertions to every router.
//
// The bind puts one router_sva, named u_sva, inside the router module, wired
// to the router's own ports. The router's RTL doesn't change, and the same
// bind works on the golden design and on the faulty build. The top module
// reads u_sva.n_fail (the number of assertion failures so far) through the
// router instance, dut.u_sva.n_fail.

bind router router_sva u_sva (
  .clk(clk), .rst_n(rst_n),
  .in_valid(in_valid), .in_ready(in_ready), .in_data(in_data), .in_last(in_last),
  .out0_valid(out0_valid), .out0_ready(out0_ready), .out0_data(out0_data), .out0_last(out0_last),
  .out1_valid(out1_valid), .out1_ready(out1_ready), .out1_data(out1_data), .out1_last(out1_last)
);
