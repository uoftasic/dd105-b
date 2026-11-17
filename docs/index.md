# DD105-B — Testbenches with UVM

Build a UVM testbench in Python, with pyuvm and cocotb on Verilator, for the same packet router as DD105-A.

<!--
  Template: scripts/init-template.py fills in the {{...}} tokens (see
  TEMPLATE.md). Replace the _italic_ placeholders below by hand, then replace
  the course path rows with your own guide pages and labs. AGENTS.md describes
  the course structure.
-->

- Who it's for: _one line on who should take this course._
- Prerequisites: _earlier courses or background, with links._
- Total time: _about N hours, the sum of the times in the course path._

This site holds the reading and the lab writeups, and the code that each lab runs is in the course's [GitHub repo](https://github.com/uoftasic/dd105-b), under `labs/`. You'll find the other UofT ASIC courses listed at [edu.uoftasic.com](https://edu.uoftasic.com/).

## Course path

Work down the table in order. A Read row points you to one or more guide pages, which are for reading only, so there's nothing to run. A Do row is a lab, where you run things, make something of your own and check your results.

<!--
  Template: keep this table format in every course.
  - Read and Do are plain text, and Read and Do rows alternate in the order
    a student should work.
  - A Do row names the lab as "Lab NN: Title", the same as the lab page's
    header and the sidebar, and ends with one sentence on what you'll do.
  - Separate several guide pages in one Read row with " · ".
  - Give every row a time estimate. The row times add up to the total time
    above. Leave optional lab parts out of them.
  - Keep the sidebar in docs/_quarto.yml and the chapters in
    docs/_quarto-pdf.yml in the same order.
-->

| # | | What | Time |
|---|---|---|---|
| 1 | Read | [Getting started](guide/getting-started.md) | _N_ min |
| 2 | Do | [Lab 01: One ALU, two frameworks](labs/lab-01-one-alu-two-frameworks-overview.md). Test SimProc's ALU with DD104's cocotb test and with a pyuvm testbench, compare what each costs with DD105-A's SystemVerilog numbers, and extend the pyuvm scoreboard until it catches A03, the zero-flag bug. | 1 h 15 min |
| 3 | Do | [Lab 02: A layered testbench without pyuvm](labs/lab-02-a-layered-testbench-without-pyuvm-overview.md). Write the monitor and the scoreboard of a plain-cocotb testbench for the router, catch B05 and B09 with it, and find out which part of the stimulus each catch depends on. | 1 h 30 min |
| 4 | Do | [Lab 03: Constraints and coverage](labs/lab-03-constraints-and-coverage-overview.md). Add functional coverage to the Lab 02 testbench, weight its packet lengths with pyvsc constraints, and write the stimulus that reaches the two coverage holes where B07 and B08 are. | 1 h 30 min |
| 5 | Do | [Lab 04: The same testbench in pyuvm](labs/lab-04-the-same-testbench-in-pyuvm-overview.md). Finish our pyuvm port of the Lab 03 testbench by adding an agent for output 1, a test that stalls one output at a time and a factory override that sends packets to disabled routes, so that it catches B06 and B13. | 2 h |
