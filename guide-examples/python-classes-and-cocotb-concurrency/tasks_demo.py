"""
DD105-B guide example for "Python classes and cocotb concurrency": tasks.

  start_test         three tasks awaited three ways: all of them, the first, none
  capture_test       tasks started in a loop, reading the loop variable two ways
  queue_test         a generator and a driver joined by a Queue, unbounded and maxsize=1
  event_test         Event.wait() before set(), after set(), and after clear()
  cancel_test        cancel() on a task, and on a task that started another one
  end_test           a task still running when the test ends
  unwatched_test     a task raises NameError, and nothing waits for it
  joined_test        ... and the test waits for it with `await t`
  first_test         ... and the test waits on First(t.complete, Timer)
  first_result_test  ... and then calls t.result()
"""

from asyncio import CancelledError

import cocotb
from cocotb.queue import Queue
from cocotb.simtime import get_sim_time
from cocotb.triggers import Combine, Event, First, Timer


def say(s):
    print(f"{get_sim_time('ns'):3.0f} ns: {s}", flush=True)


async def finish_after(name, ns):
    await Timer(ns, unit="ns")
    say(f"  {name} finished")


def start_three():
    return [cocotb.start_soon(finish_after(name, ns)) for name, ns in (("A", 10), ("B", 20), ("C", 30))]


@cocotb.test()
async def start_test(dut):
    say("start A, B and C, and await Combine(a, b, c)")
    a, b, c = start_three()
    await Combine(a, b, c)
    say("the test goes on after Combine")

    say("start A, B and C, and await First(a, b, c)")
    a, b, c = start_three()
    await First(a, b, c)
    say("the test goes on after First")
    await Combine(a, b, c)
    say("Combine returns")

    say("start A, B and C, and await none of them")
    a, b, c = start_three()
    say("the test goes on at once")
    await Timer(40, unit="ns")


@cocotb.test()
async def capture_test(dut):
    say("three tasks, each a closure that reads i")
    for i in range(3):
        async def show():
            say(f"  i = {i}")
        cocotb.start_soon(show())
    say("the loop has finished")
    await Timer(5, unit="ns")

    say("three tasks, each given i as an argument")

    async def show_arg(j):
        say(f"  j = {j}")

    for i in range(3):
        cocotb.start_soon(show_arg(i))
    say("the loop has finished")
    await Timer(5, unit="ns")


async def gen(q):
    for k in range(4):
        await q.put(k)
        say(f"gen put {k}")
    say("gen has made all four")


async def drv(q):
    for _ in range(4):
        k = await q.get()
        say(f"  drv got {k}")
        await Timer(10, unit="ns")


@cocotb.test()
async def queue_test(dut):
    for size in (0, 1):
        say(f"Queue(maxsize={size})")
        q = Queue(maxsize=size)
        g = cocotb.start_soon(gen(q))
        d = cocotb.start_soon(drv(q))
        await Combine(g, d)


@cocotb.test()
async def event_test(dut):
    done = Event()

    async def waiter(name):
        say(f"  {name}: waiting")
        await done.wait()
        say(f"  {name}: done.wait() returned")

    cocotb.start_soon(waiter("first"))
    await Timer(10, unit="ns")
    say("done.set()")
    done.set()
    cocotb.start_soon(waiter("second"))
    await Timer(10, unit="ns")
    say("done.clear()")
    done.clear()
    cocotb.start_soon(waiter("third"))
    await Timer(10, unit="ns")
    say("end of the test")


async def ticker(counts, name):
    while True:
        await Timer(10, unit="ns")
        counts[name] += 1


async def parent(counts):
    cocotb.start_soon(ticker(counts, "child"))
    while True:
        await Timer(10, unit="ns")
        counts["parent"] += 1


@cocotb.test()
async def cancel_test(dut):
    counts = {"mon": 0, "parent": 0, "child": 0}
    mon = cocotb.start_soon(ticker(counts, "mon"))
    par = cocotb.start_soon(parent(counts))
    await Timer(25, unit="ns")
    say(f"cancel the monitor and the parent: {counts}")
    mon.cancel()
    par.cancel()
    await Timer(50, unit="ns")
    say(f"50 ns later: {counts}")
    say(f"mon.cancelled() is {mon.cancelled()}, par.cancelled() is {par.cancelled()}")


async def forever_monitor():
    try:
        while True:
            await Timer(10, unit="ns")
    except CancelledError:
        say("  the monitor was cancelled")
        raise


@cocotb.test()
async def end_test(dut):
    cocotb.start_soon(forever_monitor())
    await Timer(35, unit="ns")
    say("the test returns")


async def broken_monitor():
    await Timer(20, unit="ns")
    pkts.append(0x80)             # noqa: F821, a name that doesn't exist


@cocotb.test()
async def unwatched_test(dut):
    cocotb.start_soon(broken_monitor())
    await Timer(100, unit="ns")
    say("the test reached its end")


@cocotb.test()
async def joined_test(dut):
    t = cocotb.start_soon(broken_monitor())
    await t
    say("the test reached its end")


@cocotb.test()
async def first_test(dut):
    t = cocotb.start_soon(broken_monitor())
    await First(t.complete, Timer(100, unit="ns"))
    say(f"First returned; t.done() is {t.done()}")
    say("the test reached its end")


@cocotb.test()
async def first_result_test(dut):
    t = cocotb.start_soon(broken_monitor())
    await First(t.complete, Timer(100, unit="ns"))
    say(f"First returned; t.done() is {t.done()}")
    t.result()
    say("the test reached its end")
