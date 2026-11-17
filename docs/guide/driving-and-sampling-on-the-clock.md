# Driving and sampling on the clock

This page answers: *the router's flip-flops change at every rising edge. When should a testbench
change the router's inputs, and when should it read the pins, so that every value it reads is the
one the specification means?*

Lab 01's ALU has no clock, so its driver and monitor agreed on a 10 ns period between themselves.
The router has a clock, and every rule in its specification is stated cycle by cycle. In
[Lab 02](../labs/lab-02-a-layered-testbench-without-pyuvm-overview.md) the shipped driver, sinks
and APB writer change the router's inputs right after a rising edge, and every class that reads the
pins, including the monitor you'll write, reads them at the falling edge in the middle of the cycle.
DD105-A's testbenches got the same timing from SystemVerilog clocking blocks, and this course gets
it from that rule. This page runs the rule on the router, and then reads the same pins at the other
moments a testbench could choose.

The examples on this page drive the golden router from `labs/common/rtl`, and we ran them in the
course image. Their source is in
[`guide-examples/driving-and-sampling-on-the-clock/`](https://github.com/uoftasic/dd105-b/tree/main/guide-examples/driving-and-sampling-on-the-clock),
and `guide-examples/README.md` gives the command for each output, in its section for this page.

## Cycles and handshakes

The specification's [Cycles and handshakes](../reference/router-spec.md#cycles-and-handshakes)
section numbers the clock periods: cycle *n* is the period that ends at rising edge *n*, and the
value of a signal "in cycle *n*" is the value it holds just before that edge. The router samples its
inputs at rising edges, and most of its outputs come straight from flip-flops, so they change just
after a rising edge. A **handshake** on a stream is a cycle in which `valid` and `ready` are both 1,
and the beat moves at the rising edge that ends that cycle.

Two things follow for a testbench. An input that you change right after rising edge *n* has its new
value in cycle *n* + 1, and the router acts on it at the edge that ends that cycle. And at the falling
edge in the middle of a cycle nothing changes, because the router's outputs and the testbench's
inputs both changed just after the rising edge before it. Every signal then holds the value it has
for the whole cycle, which is the value the specification calls its value in that cycle.

## The rule in a driver

The example's `send_beat()` offers one beat on the router's input the way Lab 02's `Driver` does.
It's called right after a rising edge:

```python
async def send_beat(dut, data, last):
    dut.in_valid.value = 1
    dut.in_data.value = data
    dut.in_last.value = int(last)
    while True:
        await FallingEdge(dut.clk)
        if dut.in_ready.value:
            break
        await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)                   # the beat moves at this edge
```

The three writes give the beat's signals their values for the next cycle. At the falling edge in
the middle of that cycle the loop looks at `in_ready`. If it's 1, `in_valid` is 1 in the same cycle,
so this cycle is the handshake, and the beat moves at the rising edge that ends it. `send_beat()`
returns right after that edge, ready to offer the next beat. If `in_ready` is 0, the
loop waits for the rising edge, leaves the beat on offer, and looks again at the next falling edge.
Each pass of the loop is one clock cycle: drive, wait for the falling edge, look, wait for the
rising edge. The example's `apb_write()` is built the same way, from Lab 02's `ApbMaster.write()`,
and reads `pready` at the falling edge of each access cycle.

## What the pins read at each moment

`edge_test` holds the router in reset through the rising edges at 0, 10 and 20 ns, as Lab 02's test
does, then writes `ROUTE0` (enabled, `PORT` 0) and `CTRL.EN` with `apb_write()`, and offers a
two-beat packet, `00` and then `5a`, to `DST` 0 with `send_beat()`. Meanwhile a watcher task reads
`in_valid`, `in_ready` and `out0_valid` three times around every rising edge: at the falling edge
before it, as soon as the rising edge comes (`await RisingEdge(dut.clk)` and then a read), and in
cocotb's `ReadOnly` phase after it, the end of that time step, when every value has settled. It
prints the three readings for each edge from 70 ns to 120 ns, in that order:

```text
  20 ns: (in_valid in_ready out0_valid)
  70 ns: falling edge before: 0 0 0 | at the edge: 0 0 0 | ReadOnly: 0 0 0
  80 ns: CTRL.EN written
  80 ns: falling edge before: 0 0 0 | at the edge: 0 0 0 | ReadOnly: 1 1 0
  90 ns: beat 00 moved
  90 ns: falling edge before: 1 1 0 | at the edge: 1 1 0 | ReadOnly: 1 1 0
 100 ns: beat 5a moved
 100 ns: falling edge before: 1 1 0 | at the edge: 1 1 0 | ReadOnly: 0 1 1
 110 ns: falling edge before: 0 1 1 | at the edge: 0 1 1 | ReadOnly: 0 1 1
 120 ns: falling edge before: 0 1 1 | at the edge: 0 1 1 | ReadOnly: 0 1 0
```

Here is the same run in Surfer, from 60 ns to 130 ns:

![The router's APB write of CTRL.EN and a two-beat packet, driven right after rising edges, in Surfer](../assets/img/driving-edge-test.png)

*The `CTRL` write's setup cycle runs from 60 to 70 ns and its access cycle from 70 to 80 ns, and
`in_ready` rises at the 80 ns edge, when the write takes effect. `in_valid` also rises at 80 ns,
because the test drove it right after that edge. The router takes `00` at the 90 ns edge and `5a`
at the 100 ns edge, and `out0_valid` is high from 100 to 120 ns.*

Each beat came out on output 0 two cycles after its handshake on the input, as rule O8 of the
specification says. `00`'s handshake was the cycle from 80 to 90 ns, and `out0_data` holds `00` in
the cycle from 100 to 110 ns.

Here is the cycle that each of the three readings belongs to:

- **The falling edge before edge *n*** reads the values in cycle *n*, the cycle that edge *n* ends.
  At 85 ns, the falling edge before the 90 ns edge, it read `in_valid` and `in_ready` both 1, so the
  cycle from 80 to 90 ns is `00`'s handshake, and the beat moved at 90 ns, which is what the test
  printed.
- **At the edge**, on this setup, Python read the same values as at the falling edge before it,
  the values from before the edge. `in_ready` read 0 at the 80 ns edge, although the waveform shows
  it rising at 80 ns.
- **In `ReadOnly` after edge *n*** it read the values in cycle *n* + 1, the cycle that edge *n*
  starts: `in_ready` 1 at 80 ns, and the test's write of `in_valid`, made right after the same edge,
  already in place.

So at 80 ns `in_ready` read 0 or 1 depending on where in that moment the reading was taken, and a
waveform can't show you which, because Surfer draws a change made at the edge and a change made just
after it at the same instant.

## A write at the edge

A value you write at an edge isn't there yet for anything else that reads at that edge.
`same_edge_test` starts three
tasks that wait for the same rising edge: a reader, a writer that sets `in_data` to `aa`, and a
second reader, in that order. The second reader runs after the write and still reads the old value:

```text
  55 ns: at the falling edge: in_data 00, in_ready 1
  60 ns: reader 1: in_data reads 00, in_ready reads 1
  60 ns: writer: in_data = aa
  60 ns: reader 2: in_data reads 00, in_ready reads 1
  60 ns: ReadOnly: in_data aa, in_ready 1
```

cocotb's documentation says the same thing: writes "are not applied immediately, but delayed until
the next write cycle". The router doesn't see the write at that edge either, which is the other
half of the rule. A value written right after rising edge *n* is the input's value in cycle *n* + 1:
in `edge_test` the test wrote `00` right after the 80 ns edge, and the router took it at 90 ns.

## Reading in ReadOnly

`ReadOnly` is cocotb's name for the end of a time step, after the simulator has applied everything
for it. DD104's *Clocks, resets and triggers* page listed it as one way to read settled values after
an edge, and in `edge_test` it read the next cycle's values consistently. Two things make it awkward
in a testbench that also drives. The first is that you can't write in it. `readonly_test` waits for a
rising edge, waits for `ReadOnly`, and writes `in_valid`:

```text
  30 ns: in the ReadOnly phase after the rising edge; writing in_valid
    30.00ns WARNING  ..Test readonly_test.readonly_test Attempting settings a value during the ReadOnly phase.
```

The test stops there with a `RuntimeError`, and the verdict is `BROKEN: RuntimeError`. A loop that
reads in `ReadOnly` has to wait for another trigger before it can drive anything. The second is that its readings are stamped with the time of the edge that
starts the cycle they describe, so a log line at 80 ns describes the cycle from 80 to 90 ns, while a
falling-edge reading of the same cycle is stamped 85 ns.

## Three monitors

`monitor_test` sends 20 random packets, 73 beats, through the router, with Lab 02's idle gaps
between some of the beats, and runs three copies of an input monitor. They are the same code except
for when they read the pins: at the falling edge, as soon as the rising edge comes, and in `ReadOnly`
after the rising edge. Each records the beats of every handshake and the time it saw each packet's
last beat:

```text
1260 ns: the driver sent 73 beats in 20 packets; the first: 00 75 96 ab
1260 ns:  falling monitor: 73 beats in 20 packets, 20 the same as sent; the first: 00 75 96 ab at 215 ns
1260 ns:   rising monitor: 73 beats in 20 packets, 20 the same as sent; the first: 00 75 96 ab at 220 ns
1260 ns: readonly monitor: 73 beats in 20 packets, 20 the same as sent; the first: 00 75 96 ab at 210 ns
```

On this setup all three got every beat right, because each one reads all four of the stream's
signals at the same moment and so always sees one cycle whole. They stamp the first packet's last
beat at three different times, all for the cycle from 210 to 220 ns: the falling-edge monitor in the
middle of it, the rising-edge monitor at the edge that ends it, and the `ReadOnly` monitor at the
edge that starts it.

The trouble starts when one piece of code reads at two of these moments. In `edge_test`'s row for
80 ns, the falling-edge reading and the `ReadOnly` reading come from one pass of the watcher's loop,
5 ns apart, and they belong to two different cycles: `0 0 0` and `1 1 0`. A tracker that reads the
input's handshakes at one moment and an output's at another puts one of them in the wrong cycle.
Lab 03's tracker counts the beats waiting in output 0 from both, cycle by cycle, so it reads both
streams at the same falling edge and handles the input's handshake before the output's. Every class
in the course's testbenches reads at the falling edge, which is also why the times Lab 02's monitors
log, such as `265.00ns` for the first packet into the router, all end in 5.

## The job a clocking block did

In DD105-A, each class reached the pins through an interface with a clocking block, which sampled
its inputs just before each rising edge and drove its outputs 1 ns after it. The rule on this page
does the same job. Reading at the falling edge takes the cycle's value, half a period before the edge
rather than just before it. Writing right after the rising edge gives the router a value it first
acts on at the next edge, as the 1 ns output skew did, though in the waves the change is drawn at the
edge itself.

Plain Python does the interface's other job, which was to give a class a handle to one stream's
signals. Lab 02's `Monitor` is given the prefix of a stream's signal names, such as `in` or `out0`, and looks
each signal up with `getattr(dut, f"{prefix}_valid")`, so one class watches either stream. It never
writes to the signals it holds, which in DD105-A a monitor's interface enforced.

## Check yourself

1. A driver writes `in_valid = 1` right after the rising edge at 80 ns, and `in_ready` is 1 from
   then on. At which falling edge does a monitor see the handshake, and at which edge does the beat
   move?

   <details>
   <summary>Answer</summary>

   The monitor sees `in_valid` and `in_ready` both 1 at the falling edge at 85 ns, so the cycle from
   80 to 90 ns is the handshake, and the beat moves at the 90 ns edge. `edge_test` printed
   `beat 00 moved` at 90 ns.

   </details>

2. In the waveform, `in_valid` and `in_ready` both go to 1 at 80 ns, the same instant as a rising
   edge. Did the router take a beat at the 80 ns edge?

   <details>
   <summary>Answer</summary>

   No. Both changed at that edge, so in the cycle that the 80 ns edge ends they were both 0, as the
   falling edge at 75 ns read them. The first cycle with both at 1 is the one from 80 to 90 ns, and
   the router took `00` at 90 ns. A waveform draws a change at the edge and the value before it at the
   same instant, so read a cycle's values in the middle of it.

   </details>

3. Your monitor reads `valid` and `ready` at the falling edge, but reads `data` after
   `await RisingEdge(dut.clk)` and `await ReadOnly()`. What can go wrong?

   <details>
   <summary>Answer</summary>

   The data it reads belongs to the next cycle, so whenever the driver puts a new beat on the pins at
   the edge, the monitor pairs this cycle's handshake with the next beat's data. Read every signal of
   a stream at the same falling edge.

   </details>

## Further reading

- The router specification's [Cycles and handshakes](../reference/router-spec.md#cycles-and-handshakes)
  and [Valid/ready rules](../reference/router-spec.md#validready-rules), which state every rule in
  the cycle numbering this page uses.
- DD104's [Clocks, resets and triggers](https://uoftasic.com/dd104/guide/clocks-resets-and-triggers.html),
  "Reading at the clock edge". It measured a read at the rising edge on Icarus 14.0, and got the old
  value there too, and it lists the falling edge as the best of three ways to read a settled value.
- cocotb 2.0.1's [Writing Testbenches](https://docs.cocotb.org/en/v2.0.1/writing_testbenches.html),
  "Assigning values to signals": writes are delayed, which `same_edge_test` shows.
- ChipVerify's [Clocking Blocks](https://chipverify.com/systemverilog/systemverilog-clocking-blocks)
  and [Clocking Blocks Part 2](https://chipverify.com/systemverilog/systemverilog-clocking-blocks-part2):
  what DD105-A's clocking blocks do, with input and output skews and `#1step`. They are
  SystemVerilog, and nothing in this course uses one.

Next: [Lab 02: A layered testbench without pyuvm](../labs/lab-02-a-layered-testbench-without-pyuvm-overview.md).
