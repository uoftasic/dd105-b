# DD105-B — Testbenches with UVM

In this course you build testbenches in Python for a small packet router, and run them on
Verilator. Each one has a driver that sends packets into the router, a monitor that turns a
stream's valid/ready handshakes into packets, and a scoreboard that predicts what comes out and
checks it. In Lab 02 the course gives you the driver, and you write the monitor and the scoreboard
as plain Python classes on cocotb. In Lab 04 you finish our port of the same testbench to pyuvm, a
Python library of UVM's classes that runs on cocotb.

DD105-B is part of the UofT ASIC Team education materials, published at
<https://uoftasic.com/dd105-b/>. The labs run in the workbench: the IIC-OSIC-TOOLS container you
start from the `workspace` clone you set up in [IC101](https://uoftasic.com/ic101/). The
workbench's `mod add dd105-b` clones this course's [repository](https://github.com/uoftasic/dd105-b),
whose `labs/` folder holds everything the labs run.
[Lab 01, Part 1](labs/lab-01-one-alu-two-frameworks-overview.md#part-1-load-the-course) walks you
through `mod add dd105-b`.

## Who this course is for

You have finished [DD104](https://uoftasic.com/dd104/), where you wrote cocotb tests in Python that
caught all thirteen bugs planted in SimProc. Lab 01 starts on a design you know from it, SimProc's
ALU, with its three ALU bugs.

From Lab 02 on you test the router. It was written for DD105-A, in about 730 lines of
SystemVerilog, and this course has its own copy. It has one input stream and two output streams,
each output with its own buffer. Its routing table, drop counters and interrupt enables are
registers on an APB port. Fifteen one-line bugs are planted in it, and you switch one on when you
run a simulation. By the end of Lab 07 your pyuvm testbench catches all fifteen, and you have
written a verification plan and a verification report. Everything you write in the testbenches is
Python, apart from the assertions in Labs 05 and 07, which are SystemVerilog bound into the router.

| | |
|---|---|
| Track | Digital |
| Prerequisites | [DD104](https://uoftasic.com/dd104/), and through it [IC101](https://uoftasic.com/ic101/) and DD101 to DD103 |
| Tools | Verilator 5.050, cocotb 2.0.1, pyuvm 4.0.1, Python 3.12.3 and Surfer 0.7.0, all in the workbench image `hpretl/iic-osic-tools:2026.08`. From Lab 03 on the labs also use pyvsc 1.1.0 for constrained random and cocotb-coverage 2.0 for functional coverage, which aren't in the image, so Lab 03 has you install them into a Python venv with `make venv`. |
| Machine | The workbench you already have. Every time on these pages was measured with 2 CPUs and 3 GB. The router and its assertions build in about 8 s with an empty compiler cache, and an edit to a Python file rebuilds nothing. A run of a lab's graded test takes about 8 s in Lab 06 and about 12 s in Lab 07. The longest step, Lab 07's regression, takes about 9 minutes. |
| Total time | 21 h 10 min, the sum of the row times in the Course path below. The 14 h for the seven labs are the times the lab writeups give. The 7 h 10 min for the eighteen guide pages is our estimate, at a minute for every 130 words, plus 2 minutes for each figure and 1 minute for each 10 lines of code or output, with each Read row rounded to 5 minutes. <!-- READTIME: each Read row is the sum over its pages of (words outside code blocks / 130 + 2 min per figure + 1 min per 10 lines of code or output), rounded to 5 min; counted Nov 17, 2026, as DD105-A's were. Before rounding, rows 1, 3, 5, 7, 9, 11 and 13 came to 61.7, 63.9, 51.5, 93.0, 72.6, 48.2 and 33.1 min. --> |

## Course path

Work down this table in order. A Read row is a set of guide pages, which are for reading only and
have no commands in them. A Do row is one lab writeup, and the lab writeups are where every command
in the course lives.

| # | | What | Time |
|---|---|---|---|
| 1 | Read | [Getting started](guide/getting-started.md) · [What a framework buys you](guide/what-a-framework-buys-you.md) · [From cocotb tests to pyuvm components](guide/from-cocotb-tests-to-pyuvm-components.md) | 1 h |
| 2 | Do | [Lab 01: One ALU, two frameworks](labs/lab-01-one-alu-two-frameworks-overview.md). Test SimProc's ALU with DD104's cocotb test and with a pyuvm testbench, compare what each costs with DD105-A's SystemVerilog numbers, and extend the pyuvm scoreboard until it catches A03, the zero-flag bug. | 1 h 15 min |
| 3 | Read | [Python classes and cocotb concurrency](guide/python-classes-and-cocotb-concurrency.md) · [Driving and sampling on the clock](guide/driving-and-sampling-on-the-clock.md) | 1 h 5 min |
| 4 | Do | [Lab 02: A layered testbench without pyuvm](labs/lab-02-a-layered-testbench-without-pyuvm-overview.md). Write the monitor and the scoreboard of a plain-cocotb testbench for the router, catch B05 and B09 with it, and find out which part of the stimulus each catch depends on. | 1 h 30 min |
| 5 | Read | [Constrained random with pyvsc](guide/constrained-random-with-pyvsc.md) · [Functional coverage you can read](guide/functional-coverage-you-can-read.md) | 50 min |
| 6 | Do | [Lab 03: Constraints and coverage](labs/lab-03-constraints-and-coverage-overview.md). Add functional coverage to the Lab 02 testbench, weight its packet lengths with pyvsc constraints, and write the stimulus that reaches the two coverage holes where B07 and B08 are. | 1 h 30 min |
| 7 | Read | [The pyuvm skeleton](guide/the-pyuvm-skeleton.md) · [Sequences, sequencers and drivers](guide/sequences-sequencers-and-drivers.md) · [Monitors, analysis ports and scoreboards](guide/monitors-analysis-ports-and-scoreboards.md) · [The factory and ConfigDB](guide/the-factory-and-configdb.md) | 1 h 35 min |
| 8 | Do | [Lab 04: The same testbench in pyuvm](labs/lab-04-the-same-testbench-in-pyuvm-overview.md). Finish our pyuvm port of the Lab 03 testbench by adding an agent for output 1, a test that stalls one output at a time and a factory override that sends packets to disabled routes, so that it catches B06 and B13. | 2 h |
| 9 | Read | [Assertions for interface rules](guide/assertions-for-interface-rules.md) · [Reactive agents and backpressure](guide/reactive-agents-and-backpressure.md) · [Virtual sequences](guide/virtual-sequences.md) | 1 h 15 min |
| 10 | Do | [Lab 05: Protocol rules and backpressure](labs/lab-05-protocol-rules-and-backpressure-overview.md). Write three SystemVerilog assertions for the router's output rules, finish a sink driver that answers each output beat, and write a virtual sequence whose oversize packets reach B11. | 2 h |
| 11 | Read | [Register models in pyuvm](guide/register-models-in-pyuvm.md) · [Regressions and seeds](guide/regressions-and-seeds.md) | 50 min |
| 12 | Do | [Lab 06: The register block](labs/lab-06-the-register-block-overview.md). Write the missing fields, the adapter, the predictor and the reset and bit-bash sequences of a pyuvm register model of the router, then test the 246 addresses outside its map and check `irq` in every cycle, which together catch B01 to B04 and B14. | 2 h 15 min |
| 13 | Read | [Verification plans and sign-off](guide/verification-plans-and-sign-off.md) · [Writing the verification report](guide/writing-the-verification-report.md) | 35 min |
| 14 | Do | [Lab 07: Capstone](labs/lab-07-capstone-overview.md). Write the assertions for the rules about reset and a sequence that resets the router with packets in flight, which together catch B15, and keep your verification plan, regression results, mystery hunts and report in a GitHub repository of your own. | 3 h 30 min |

Keep these reference pages open in a tab while you work. They're for looking things up rather
than for reading from start to finish:

- [The router in one page](reference/the-router-in-one-page.md)
- [The packet router](reference/router-spec.md), the router's full specification
- [The pyuvm register API](reference/pyuvm-register-api.md), for Lab 06
- [Getting the tools outside the course image](reference/getting-the-tools-outside-the-course-image.md)

## DD105-A

DD105-A has the same router, the same fifteen bugs and the same seven labs in the same order as
this course, and you write its testbenches in SystemVerilog, with the UVM library, on Verilator
5.050. Students take one of the two courses, not both. In DD105-A's Lab 01, a SystemVerilog UVM
testbench for SimProc's ALU took 102 s to build, because Verilator compiled the whole UVM library
along with the ALU. An edit to its scoreboard took 99 s to rebuild. In this course's Lab 01, the
pyuvm testbench for the same ALU builds in 7.3 s with an empty compiler cache, because Verilator
compiles only the ALU. The testbench is Python, so an edit to it rebuilds nothing.

## Getting help

Ask in the [team Discord](https://discord.gg/hrJnP5UsGz). Say which lab and step you're on, paste
the command you ran and what it printed, and attach the `run.log` from the run's folder in
`build/runs/` if the question is about a simulation.
