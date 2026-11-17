"""
DD105-B labs/ref probe: what cocotb 2.0.1 does with an exception raised in a
task started with cocotb.start_soon(). Plain cocotb tests, no pyuvm, run on
labs/ref's build (the router is only there to have a clock):

    make run TEST_MODULES=probe_tasks PY_DIRS="tb probes" BASE_TEST=0 TEST=<test>

  TaskJoinedTest      awaits the task itself
  TaskCompleteTest    awaits First(task.complete, ...), as RouterRefTest does
  TaskResultTest      the same, then task.result()
  TaskUnwatchedTest   never looks at the task again
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import First, Timer


async def boom():
    await Timer(20, "ns")
    raise NameError("name 'oops' is not defined")


def clock(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())


@cocotb.test()
async def TaskJoinedTest(dut):
    clock(dut)
    t = cocotb.start_soon(boom())
    await t
    dut._log.info("PROBE: the test went on past `await t`")


@cocotb.test()
async def TaskCompleteTest(dut):
    clock(dut)
    t = cocotb.start_soon(boom())
    await First(t.complete, Timer(1, "us"))
    dut._log.info(f"PROBE: First returned; t.done() is {t.done()}")
    await Timer(100, "ns")
    dut._log.info("PROBE: the test reached its end")


@cocotb.test()
async def TaskResultTest(dut):
    clock(dut)
    t = cocotb.start_soon(boom())
    await First(t.complete, Timer(1, "us"))
    t.result()
    dut._log.info("PROBE: the test went on past t.result()")


@cocotb.test()
async def TaskUnwatchedTest(dut):
    clock(dut)
    cocotb.start_soon(boom())
    await Timer(1, "us")
    dut._log.info("PROBE: the test reached its end")
