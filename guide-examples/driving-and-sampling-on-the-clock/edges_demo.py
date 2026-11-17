"""
DD105-B guide example for "Driving and sampling on the clock", on the golden
router.

  edge_test      sets ROUTE0 and CTRL.EN and offers a two-beat packet, the way
                 Lab 02's ApbMaster and Driver do, while a watcher prints three
                 pins at every rising edge from 65 to 125 ns, read three ways
  monitor_test   sends 20 random packets and runs three input monitors that
                 differ only in when they read the pins
  readonly_test  writes an input in the ReadOnly phase after a rising edge
  same_edge_test two tasks read in_data at one rising edge, before and after a
                 third task writes it there

apb_write() and send_beat() follow labs/lab-02-a-layered-testbench-without-
pyuvm/tb/driver.py: change the router's inputs right after a rising edge, and
read its outputs at the falling edge.
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.simtime import get_sim_time
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer

INPUTS = ("psel", "penable", "pwrite", "paddr", "pwdata",
          "in_valid", "in_data", "in_last", "out0_ready", "out1_ready")


def say(s):
    print(f"{get_sim_time('ns'):4.0f} ns: {s}", flush=True)


async def start(dut):
    """Lab 02's start: a 10 ns clock, and rst_n low through the rising edges at
    0, 10 and 20 ns. Both sinks are always ready."""
    for name in INPUTS:
        getattr(dut, name).value = 0
    dut.rst_n.value = 0
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    dut.out0_ready.value = 1
    dut.out1_ready.value = 1


async def apb_write(dut, addr, data):
    """One APB write, as Lab 02's ApbMaster.write(): returns right after the
    rising edge at which the write completes."""
    await RisingEdge(dut.clk)
    dut.psel.value = 1
    dut.penable.value = 0
    dut.pwrite.value = 1
    dut.paddr.value = addr
    dut.pwdata.value = data
    await RisingEdge(dut.clk)                   # the setup cycle ends
    dut.penable.value = 1
    while True:
        await FallingEdge(dut.clk)
        done = bool(dut.pready.value)
        await RisingEdge(dut.clk)
        if done:
            break
    dut.psel.value = 0
    dut.penable.value = 0


async def send_beat(dut, data, last):
    """Offer one beat, as Lab 02's Driver does. Call it right after a rising
    edge; it returns right after the rising edge at which the beat moved."""
    dut.in_valid.value = 1
    dut.in_data.value = data
    dut.in_last.value = int(last)
    while True:
        await FallingEdge(dut.clk)
        if dut.in_ready.value:
            break
        await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)                   # the beat moves at this edge


def pins(dut):
    return f"{int(dut.in_valid.value)} {int(dut.in_ready.value)} {int(dut.out0_valid.value)}"


async def watch(dut, t0, t1):
    """At every rising edge from t0 to t1 ns, print in_valid, in_ready and
    out0_valid as read at the falling edge before it, at the rising edge
    itself, and in the ReadOnly phase after it."""
    say("(in_valid in_ready out0_valid)")
    while True:
        await FallingEdge(dut.clk)
        fall = pins(dut)
        await RisingEdge(dut.clk)
        edge = pins(dut)
        await ReadOnly()
        ro = pins(dut)
        t = get_sim_time("ns")
        if t > t1:
            return
        if t >= t0:
            say(f"falling edge before: {fall} | at the edge: {edge} | ReadOnly: {ro}")


@cocotb.test()
async def edge_test(dut):
    await start(dut)
    watcher = cocotb.start_soon(watch(dut, 65, 125))
    await apb_write(dut, 0x20, 0x1)             # ROUTE0: enabled, PORT 0
    await apb_write(dut, 0x04, 0x1)             # CTRL.EN
    say("CTRL.EN written")
    for i, beat in enumerate((0x00, 0x5A)):
        await send_beat(dut, beat, i == 1)
        say(f"beat {beat:02x} moved")
    dut.in_valid.value = 0
    await watcher


class EdgeMonitor:
    """Lab 02's input monitor, with a choice of when it reads the pins:
    "falling" (the course's rule), "rising" (as soon as the rising edge
    comes), or "readonly" (in the ReadOnly phase after the rising edge)."""

    def __init__(self, dut, when):
        self.dut, self.when = dut, when
        self.pkts = []
        self.times = []         # when the monitor saw each packet's last beat (ns)
        self.n_beats = 0

    async def run(self):
        d, p = self.dut, []
        while True:
            if self.when == "falling":
                await FallingEdge(d.clk)
            else:
                await RisingEdge(d.clk)
                if self.when == "readonly":
                    await ReadOnly()
            if d.rst_n.value and d.in_valid.value and d.in_ready.value:
                p.append(int(d.in_data.value))
                self.n_beats += 1
                if d.in_last.value:
                    self.pkts.append(p)
                    self.times.append(int(get_sim_time("ns")))
                    p = []


def hexes(p):
    return " ".join(f"{b:02x}" for b in p)


@cocotb.test()
async def monitor_test(dut):
    await start(dut)
    mons = [EdgeMonitor(dut, when) for when in ("falling", "rising", "readonly")]
    for m in mons:
        cocotb.start_soon(m.run())
    for d in range(4):
        await apb_write(dut, 0x20 + 4 * d, (d & 1) << 1 | 1)    # ROUTE0 to ROUTE3: 0101
    await apb_write(dut, 0x04, 0x1)

    sent = []
    for k in range(20):
        n = random.randint(1, 8)
        p = [(random.randrange(4) << 6) | k] + [random.randrange(256) for _ in range(n - 1)]
        for i, beat in enumerate(p):
            if random.randrange(4) == 0:                         # an idle gap, as in Lab 02
                dut.in_valid.value = 0
                for _ in range(random.randint(1, 3)):
                    await RisingEdge(dut.clk)
            await send_beat(dut, beat, i == n - 1)
        sent.append(p)
    dut.in_valid.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk)

    say(f"the driver sent {sum(map(len, sent))} beats in {len(sent)} packets; "
        f"the first: {hexes(sent[0])}")
    for m in mons:
        same = sum(1 for a, b in zip(m.pkts, sent) if a == b)
        first = f"{hexes(m.pkts[0])} at {m.times[0]} ns" if m.pkts else "none"
        say(f"{m.when:>8} monitor: {m.n_beats} beats in {len(m.pkts)} packets, "
            f"{same} the same as sent; the first: {first}")


@cocotb.test()
async def readonly_test(dut):
    await start(dut)
    await RisingEdge(dut.clk)
    await ReadOnly()
    say("in the ReadOnly phase after the rising edge; writing in_valid")
    dut.in_valid.value = 1
    say("written")


async def edge_reader(dut, name):
    await RisingEdge(dut.clk)
    say(f"{name}: in_data reads {int(dut.in_data.value):02x}, in_ready reads {int(dut.in_ready.value)}")


async def edge_writer(dut):
    await RisingEdge(dut.clk)
    dut.in_data.value = 0xAA
    say("writer: in_data = aa")


@cocotb.test()
async def same_edge_test(dut):
    await start(dut)
    await apb_write(dut, 0x04, 0x1)             # CTRL.EN; in_ready is 1 from the next edge
    await FallingEdge(dut.clk)
    say(f"at the falling edge: in_data {int(dut.in_data.value):02x}, in_ready {int(dut.in_ready.value)}")
    tasks = [cocotb.start_soon(edge_reader(dut, "reader 1")),
             cocotb.start_soon(edge_writer(dut)),
             cocotb.start_soon(edge_reader(dut, "reader 2"))]
    for t in tasks:
        await t
    await ReadOnly()
    say(f"ReadOnly: in_data {int(dut.in_data.value):02x}, in_ready {int(dut.in_ready.value)}")
