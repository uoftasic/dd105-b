# Guide examples

This folder holds the examples that DD105-B's guide and reference pages quote. Each folder belongs to
one page and has the page's name. Every folder has a `Makefile` that includes the labs' shared
[`labs/common/pyuvm.mk`](../labs/common/README.md), so it builds its design with Verilator 5.050
and runs with cocotb 2.0.1 and pyuvm 4.0.1 in the course image, and it has the same targets as a lab
(`make build`, `make run`, `make waves`, `make clean` and the rest). One build serves every test in a
folder, and `TEST=` picks the test when you run. A folder whose Makefile sets `NEEDS_VENV := 1` also
needs the course venv, which `make venv` makes, as in Lab 03, Part 1.

The pages are for reading, and none of them asks you to run anything here. The sections below give
the commands that produced each output a page quotes, in course path order with the reference page
last, so the folders are for anyone who wants to check what a page says, or to change an example and
see what happens. Every quoted output came from a run in the course image with 2 CPUs and 3 GB, in a
folder with no `build/`. Run each command from the example's folder, and finish with `make clean`.

## Getting started and What a framework buys you

These two pages have no examples of their own. They quote Lab 01's writeup and its
`solutions/README.md`, and a run of Lab 01's own targets in `labs/lab-01-one-alu-two-frameworks`,
starting from an empty compiler cache:

```bash
make clean-cache && make clean
make cocotb                         # built ... in 7.3 s; ok: passed
make build                          # built ... in 1.6 s, 6 of 7 files from the ccache
make run                            # ok: 0 errors   0.53 s
make run TEST=AluDirectedTest       # ok: 0 errors   0.27 s
make check-all                      # 2 of 3 caught, then make's error line
make loc                            # 189/94 and 316/161
du -sh build ../../.ccache          # 3.4M and 672K
make clean                          # removed ... The ccache (...) and the venv are kept.
make venv && make clean-venv        # created in 9.6 s, 37M; then removed
```

and the version checks from Lab 01, Part 1. *What a framework buys you* quotes DD105-A's numbers
(lines, build and rebuild times, run time and error counts for its SystemVerilog UVM testbench) from
DD105-A's Lab 01, as DD105-B's Lab 01 does.

## from-cocotb-tests-to-pyuvm-components

Page: [From cocotb tests to pyuvm components](../docs/guide/from-cocotb-tests-to-pyuvm-components.md).
The design is Lab 01's ALU, `labs/lab-01-one-alu-two-frameworks/rtl/alu.sv`, with its `+BUG`
switch. The tests are pyuvm tests in `components_demo.py`.

| Command | What the page quotes |
|---|---|
| `make build` | |
| `make run TEST=T01Test` | `[T01] 6 directed vectors checked`, `DD105-B BaseTest: 0 errors logged, no bound assertions` |
| `make run TEST=T01Test BUG=A01` | the `SUB(0xC8, 0x3C) gave out=0x74 ...` error, the `BaseTest` line, `caught: 1 error` |
| `make run TEST=T01UvmTest BUG=A01` | the same error, `components_demo.T01UvmTest passed`, `BROKEN: no BaseTest line` |
| `make run TEST=PhaseOrderTest` | the 39 lines from `0 ns  build_phase` to the last `final_phase` |
| `make run TEST=NoObjectionTest` | `You did not call self.raise_objection() in any run_phase`, and the lines around it |

## python-classes-and-cocotb-concurrency

Page: [Python classes and cocotb concurrency](../docs/guide/python-classes-and-cocotb-concurrency.md).
Plain cocotb tests, as in Lab 02, so the Makefile sets `BASE_TEST := 0`. cocotb needs a design to
run in, and this is Lab 01's ALU, which the tests never touch. The class examples are in
`classes_demo.py` and the task examples in `tasks_demo.py`.

| Command | What the page quotes |
|---|---|
| `make build` | |
| `make run TEST=handles_test` | `a is None` ... `a is b: True, ... Packet.n_made: 1` |
| `make run TEST=reuse_test` | the six `one Packet, reused:` and `a new Packet each:` lines |
| `make run TEST=none_test` | `appending a beat to p`, the `AttributeError` traceback, `BROKEN: AttributeError` |
| `make run TEST=dispatch_test` | the two `report() of Component` lines |
| `make run TEST=super_test` | `made a ForgetfulScoreboard; its attributes: ['expected']` and the `AttributeError` |
| `make run TEST=class_attr_test` | the `Sink:` and `OwnSink:` lines |
| `make run TEST=start_test` | the sixteen lines from `start A, B and C, and await Combine(a, b, c)` |
| `make run TEST=capture_test` | `i = 2` three times, then `j = 0`, `j = 1`, `j = 2` |
| `make run TEST=queue_test` | the `Queue(maxsize=0)` and `Queue(maxsize=1)` timelines |
| `make run TEST=event_test` | the `first`, `second` and `third` waiters |
| `make run TEST=cancel_test` | the counts at 25 and 75 ns |
| `make run TEST=end_test` | `the test returns`, `the monitor was cancelled` |
| `make run TEST=unwatched_test` | `name 'pkts' is not defined` at 20 ns, `BROKEN: NameError` |
| `make run TEST=joined_test` | `BROKEN: NameError` |
| `make run TEST=first_test` | `First returned; t.done() is True`, `ok: passed` |
| `make run TEST=first_result_test` | `BROKEN: NameError` |

## driving-and-sampling-on-the-clock

Page: [Driving and sampling on the clock](../docs/guide/driving-and-sampling-on-the-clock.md).
The design is the golden router, `labs/common/rtl/router.f`, with no planted bugs. Plain cocotb
tests, as in Lab 02, so the Makefile sets `BASE_TEST := 0`.

| Command | What the page quotes |
|---|---|
| `make build` | |
| `make run TEST=edge_test` | the watcher's lines from 20 ns to 120 ns |
| `make waves TEST=edge_test` | `build/runs/edge_test-s1/waves.fst`, for the figure below |
| `make run TEST=same_edge_test` | the five lines from 55 ns to 60 ns |
| `make run TEST=readonly_test` | `Attempting settings a value during the ReadOnly phase.`, `BROKEN: RuntimeError` |
| `make run TEST=monitor_test` | the four lines at 1260 ns |

The figure `docs/assets/img/driving-edge-test.png` is that waveform, drawn from the top of the clone
with [`scripts/screenshots/shoot.sh`](../scripts/screenshots/README.md):

```bash
scripts/screenshots/shoot.sh surfer guide-examples/driving-and-sampling-on-the-clock/build/runs/edge_test-s1/waves.fst \
  -s router.clk,router.psel,router.penable,router.in_valid,router.in_ready,router.in_data,router.in_last,router.out0_valid,router.out0_data \
  --from 60ns --to 130ns --time-unit ns -o docs/assets/img/driving-edge-test.png
```

## pyuvm-register-api

Page: [The pyuvm register API](../docs/reference/pyuvm-register-api.md), a reference page.
Six pyuvm tests in `tb/test_regapi.py`, on the golden router. The bus side is
[`labs/ref`](../labs/ref/README.md)'s APB agent, register model and adapter, which `PY_DIRS` puts
on the path; none of them needs the course venv. Every line the tests print starts with `REGAPI`,
and each test catches what an operation raises and prints it, so every run ends with `ok`.

| Command | What the page quotes |
|---|---|
| `make run TEST=RegPolicyTest` | `predict()` on a field of each of the 26 access policies; `predict()`'s `kind` and `path` arguments; what `configure()`, `add_reg()`, `map.reset()`, `add_hdl_path()` and `uvm_mem` refuse; which methods and classes exist |
| `make run TEST=RegOpsTest` | `read()` and `write()` through the map, what `reg2bus()` receives, the mirror after each, `set_desired()` with `write(None, ...)`, and `uvm_door_e` passed as a path |
| `make run TEST=RegTwoOpsTest` | two operations on one register at once, and on two registers |
| `make run TEST=RegBackdoorTest` | `path_t.BACKDOOR` and `path_t.USER_FRONTDOOR`, and the register they leave stuck |
| `make run TEST=RegAutoPredictTest` | `enable_auto_predict` set in each of the two modules that hold it |
| `make run TEST=RegAddrTest` | registers configured at `"0x00"`, and added at an offset, and the map's base address |

`grep REGAPI build/runs/<test>-s1/run.log` pulls a test's lines out of its log. In the course image
with 2 CPUs and 3 GB, `make build` took 7.8 s with an empty ccache, and each run took 0.31 s to
1.17 s.

## Times

In the course image with 2 CPUs and 3 GB, starting from an empty compiler cache, the folders
`from-cocotb-tests-to-pyuvm-components`, `python-classes-and-cocotb-concurrency` and
`driving-and-sampling-on-the-clock` built in 7.3 s (the first, which compiles Verilator's and
cocotb's support code), 1.6 s and 2.1 s, and every run listed in their sections took 0.2 to 0.9 s.

## Cleaning up

`make clean` in each folder removes its `build/`. The examples share the course's compiler cache
in `.ccache` at the top of the clone with the labs, and `make clean-cache` removes it.
