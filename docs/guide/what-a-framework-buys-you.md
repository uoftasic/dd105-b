# What a framework buys you

This page answers: *what is pyuvm for, and what does it cost compared with the cocotb tests you
already write?*

A testbench framework is a library of base classes plus a set of rules for how the pieces you build
from them fit together and when each one runs. UVM, the Universal Verification Methodology, is the
one this course uses, and pyuvm is UVM written in Python. In
[Lab 01](../labs/lab-01-one-alu-two-frameworks-overview.md) you'll test SimProc's ALU twice, once
with the cocotb test from DD104 Lab 03 and once with a pyuvm testbench, both on Verilator. You'll
measure what each costs in lines, build time and run time, and see what each reports on three
planted bugs. This page goes through what we measured when we ran the lab, so you know what you're
looking at when your own numbers come in. Your times will differ a little from ours, but the counts
(lines, vectors and errors) should match.

DD105-A teaches the same course with UVM in SystemVerilog, and its Lab 01 measured a SystemVerilog
UVM testbench of the same ALU. This course doesn't build that testbench. Where this page gives its
numbers, they're DD105-A's, from DD105-A's runs.

## What pyuvm is

UVM is standardised as IEEE 1800.2, as a library of SystemVerilog classes. pyuvm's README calls
pyuvm "a clean implementation of IEEE 1800.2 in Python", and pyuvm uses cocotb to talk to the
simulator. The course image has pyuvm 4.0.1 installed beside cocotb 2.0.1, and none of it is
compiled. Verilator builds the ALU, and cocotb imports pyuvm when the simulator starts, as it would
any other Python package.

The library gives you a base class for each job a testbench does, and the machinery that connects
them. Lab 01's testbench uses these parts of it:

- base classes for the pieces: `uvm_sequence_item` for one transaction, `uvm_sequence` for a
  stream of them, and `uvm_sequencer`, `uvm_driver`, `uvm_monitor`, `uvm_subscriber` (for the
  scoreboard), `uvm_agent`, `uvm_env` and `uvm_test` for the components;
- **phases**, which build every component, connect them, run them, and then call each one's check
  and report methods, in that order, and **objections**, which the test raises and drops to tell
  pyuvm when the run phase is over;
- `ConfigDB`, a store of named values that every component can read, which carries the object
  holding the ALU's pins from the test to the driver and the monitor;
- **analysis ports**, which pass each transaction the monitor writes to every component connected
  to the port, here the scoreboard;
- the **factory**, through which every component and transaction is made, with
  `AluDriver.create("drv", self)` rather than `AluDriver("drv", self)`.
  [Lab 04](../labs/lab-04-the-same-testbench-in-pyuvm-overview.md) adds a factory override, which
  lets a test swap one class for another without editing the code that makes it;
- `@pyuvm.test()`, which turns a test class into a cocotb test named after the class, so that
  `make run TEST=AluDirectedTest` picks it when the simulator starts.

pyuvm leaves out some of SystemVerilog UVM. It has no macros, because Python doesn't need them to
register a class with the factory or to print and copy an object. It reports through Python's
`logging` rather than through a report server, and a component that calls `self.logger.error()`
prints a line and fails nothing. The course's `BaseTest`, which every pyuvm test in the course
derives from, counts those errors and fails the test at the end if there were any, and the course's
verdict calls a pyuvm run `BROKEN` if it passed without `BaseTest`'s closing line.
[From cocotb tests to pyuvm components](from-cocotb-tests-to-pyuvm-components.md#logged-errors-and-basetest)
shows a test with and without it.

## The two testbenches

![Lab 01's cocotb test beside its pyuvm testbench](../assets/img/dd105b-lab01-two-testbenches.svg){fig-alt="Two drawings side by side. On the left, a frame labelled cocotb/test_alu.py (Python) holds three boxes stacked with arrows between them: t01, t02, t03; alu(); and spec(), assert. A line with an arrowhead at each end, labelled dut, joins alu() to an ALU box in a dashed frame labelled Verilator: build/cocotb. On the right, a frame labelled uvm_test_top: AluRandTest (Python classes) holds a seq box above a frame labelled env (AluEnv). Inside env is a frame labelled agt (AluAgent) with boxes sqr, drv and mon, and outside the agent but inside env a box sb. Arrows go from seq to sqr and from sqr to drv, and an arrow labelled ap goes from mon to sb. Below env, still in the Python frame, a box labelled AluIf (from ConfigDB) has an arrow from drv and an arrow to mon. A line with an arrowhead at each end, labelled dut, joins AluIf to an ALU box in a dashed frame labelled Verilator: build."}

*Lab 01's two testbenches. Each is Python that cocotb runs inside a simulator of its own, and each
simulator is Verilator's build of `rtl/alu.sv` alone. The cocotb test reaches the pins through
`dut`; the pyuvm testbench reaches them through `AluIf`, which holds `dut`.*

Both testbenches do the same three things: make vectors, put them on the ALU's pins, and compare
what comes back with a model. The cocotb test does all three in one file of plain functions:
`alu()` drives the pins and reads them back, `spec()` is the model, and each test function loops
over its vectors and asserts.

The pyuvm testbench gives each job its own class. A sequence makes `AluItem` objects and hands them
to the sequencer, which passes them to the driver. The ALU has no clock, so the driver and the
monitor share a 10 ns period through `AluIf`: the driver holds each vector on the pins for one
period, and the monitor reads the pins back 5 ns into every period that carries a vector, into an
`AluItem` with the ALU's answer filled in. The monitor writes each item to its analysis port, and
it doesn't know what the answer should be. The scoreboard receives each item in its `write()`
method, works out the right answer with `predict()`, and compares it with what the monitor saw. The
agent and the environment create the pieces and connect them, and in its check phase the
environment also checks that the scoreboard checked every vector the driver sent. The test picks
which sequence to start. Lab 01, Part 3 has a table that matches each class with the part of
`test_alu.py` that does the same job.

## What it costs

These are the costs Lab 01 measured, in the course image on 2 CPUs. The third column is DD105-A's
Lab 01, on the same Verilator:

| | cocotb | pyuvm | SystemVerilog UVM (DD105-A) |
|---|---|---|---|
| Lines of code (not counting blank lines, comments and docstrings) | 94 | 161 | 282 |
| First build | 7.3 to 7.6 s | 7.3 s; 1.6 to 1.8 s after the cocotb build | 102 s |
| Rebuild after you change the testbench | none | none | 26 s to 99 s |
| Run | 11.0 to 11.7 s, 10.6 to 11.2 s of it in `t02`'s 393,216 vectors | 0.54 s for 2000 vectors | 1.17 s for 2000 vectors |
| Time per vector | about 0.03 ms | about 0.1 ms | at most 0.6 ms |

**Lines.** The pyuvm testbench has about 1.7 times the cocotb test's code lines. The extra lines
are in pieces the cocotb test doesn't need: an agent and an environment that only create and
connect the other pieces, `AluIf`, and a driver and a monitor that between them do what `alu()`
does in five lines. DD105-A's SystemVerilog testbench had three times the cocotb test's code lines,
and Lab 01, Part 3 asks you which of those lines Python doesn't need.

**Build.** Verilator compiles only the ALU, whichever testbench you run, and most of the first
build's 7.3 s goes on Verilator's and cocotb's support code, which the compiler cache keeps for the
next build ([Getting started](getting-started.md#how-long-things-take) has the numbers). DD105-A's
build took 102 s because Verilator compiled the whole UVM library along with the ALU and the
testbench. Its build report counted 24.157 MB of source in 386 modules, and g++ spent 98.5 s of the
102.

**Rebuilds.** A change to either Python testbench costs nothing before the next run, because
cocotb imports the testbench each time the simulator starts. After the flag-check edit in Lab 01,
Part 5, `make build` prints `Vtop is up to date.` and took 0.07 s. In DD105-A the same edit to the
SystemVerilog scoreboard cost a rebuild of 99 s, and DD105-A measured 26 s for a change inside a
function body and 93 s for one new class member.

**Speed.** cocotb's table puts `AluRandTest`'s 2000 vectors at 0.19 s of real time, about 0.1 ms
each, and `t02`'s 393,216 at 10.64 s, about 0.03 ms each. Each vector in the pyuvm testbench goes
through a sequence, the sequencer, the driver, the monitor's analysis port and the scoreboard,
where `t02` calls two functions. The run is still quick, because the test sends 2000 random
vectors rather than sweeping all 393,216 as DD104's `t02` does. DD105-A's 2000 vectors in 1.17 s
come to at most 0.6 ms each, because the 1.17 s also covers starting the simulator.

## What it buys

For that cost, Lab 01's pyuvm testbench gives you two things, both of them modest on a design as
small as one ALU.

- **Checking kept apart from stimulus.** In Lab 01, Part 5 you add a check of the `N` and `Z` flags
  to the scoreboard. Both `AluRandTest` and `AluDirectedTest` use it without being edited, because
  neither test does any checking of its own. In `test_alu.py`, `t01` and `t02` each do their own
  comparison, so a new check would have to be written into each of them.
- **Tests that reuse the pieces.** `AluDirectedTest` is one short sequence, DD104's six `t01`
  vectors, and one short test class that starts it. It reuses the driver, the monitor and the
  scoreboard as they are. Choosing it when you run needs no rebuild, but a plain cocotb test is
  chosen by name when the simulator starts in the same way, so that part isn't something pyuvm
  adds.

DD105-A's UVM also counted errors by ID in its report server, and printed `[VALUE]   282` at the
end of a run with A01 switched on. pyuvm 4.0.1 keeps no such count, so in this course the counts by
kind are the scoreboard's own, on the `[SB]` line its `report_phase` prints:
`[SB] 2000 vectors checked: 291 value mismatches (SUB 291)` on A01.

Deciding what to check is still up to you. Against Lab 01's three bugs, the shipped pyuvm scoreboard
caught A01 with 291 errors and A02 with 278, and missed A03 with no errors at all. The cocotb test
caught all three, because its `t02` compares the flags and the shipped scoreboard doesn't. Once you
add the flag check, the pyuvm test catches A03 with 125 errors in 2000 vectors.

You get more back on a bigger design, and the router you'll test from Lab 02 on is the kind of
design UVM was made for. The router has a register bus, an input stream and two output streams, so
a testbench for it has a driver and a monitor for each of those interfaces, and a scoreboard that
predicts which output each packet comes out of. Labs 02 and 03 build that testbench from plain
Python classes on cocotb first, so that each pyuvm piece has an obvious job when it appears.
Lab 04 then moves it into pyuvm and counts what moved and what was added.

## Check yourself

1. In Lab 01's scoreboard you change the body of `predict()`. How long will the rebuild take? How
   long did the same kind of change take in DD105-A?

   <details>
   <summary>Answer</summary>

   There's no rebuild: the simulator is built from `rtl/alu.sv` alone, and the scoreboard is Python
   that cocotb imports when the simulator starts, so `make build` prints `Vtop is up to date.`
   DD105-A measured 26 s for a change inside a function body, because there the scoreboard is
   compiled into the simulator.

   </details>

2. Lab 01's shipped scoreboard logs 291 `[VALUE]` errors on A01. If `AluBaseTest` derived from
   pyuvm's `uvm_test` instead of the course's `BaseTest`, what would cocotb report for the test?

   <details>
   <summary>Answer</summary>

   That it passed. pyuvm logs each error through Python's `logging`, and a logged error doesn't
   fail a test. `BaseTest` is what counts the errors and fails the test at the end, and without its
   line in the log the course's verdict calls the run `BROKEN`.

   </details>

3. The shipped pyuvm testbench misses A03 and the cocotb test catches it. Does that tell you
   anything about pyuvm?

   <details>
   <summary>Answer</summary>

   No. The cocotb test compares the flags and the shipped scoreboard compares only the value, so the
   two testbenches check different things. With the flag check added, the pyuvm testbench catches
   A03 too.

   </details>

## Further reading

- pyuvm's [README at release 4.0.1](https://github.com/pyuvm/pyuvm/tree/4.0.1): "IEEE 1800.2 and
  pyuvm" goes through the standard section by section and says what pyuvm keeps, changes or leaves
  out, and "The pyuvm testbench" walks through a testbench for an ALU.
- ChipVerify's [UVM Tutorial](https://www.chipverify.com/uvm/uvm-tutorial): a map of the
  library's main pieces. Its code is SystemVerilog, written for commercial simulators.
- ChipVerify's [UVM Introduction](https://www.chipverify.com/uvm/uvm-introduction): why UVM exists,
  and the difference between components and objects. Correction: its monitor fragment never
  constructs its analysis port, so as written its `ap.write()` would use a null handle. Lab 01's
  `AluMonitor` makes its port in `build_phase`, with `uvm_analysis_port("ap", self)`.

Next: [From cocotb tests to pyuvm components](from-cocotb-tests-to-pyuvm-components.md).
