"""
DD105-B guide example for "Python classes and cocotb concurrency": classes.

  handles_test     two names for one object, a shallow copy and a deep copy
  reuse_test       one Packet reused for three packets, against a new one each
  none_test        a beat appended to p while p is still None
  dispatch_test    a method in the base class that calls an overridden one
  super_test       a subclass whose __init__ leaves out super().__init__()
  class_attr_test  a list made in the class body, shared by every object

Packet is a cut-down version of Lab 02's (labs/lab-02-a-layered-testbench-
without-pyuvm/tb/packet.py), with a serial number added.
"""

import copy

import cocotb


class Packet:
    n_made = 0                    # a class attribute: one for the class

    def __init__(self, data=None):
        self.id = Packet.n_made   # instance attributes: one set per object
        Packet.n_made += 1
        self.data = list(data or [])

    def __str__(self):
        return f"pkt {self.id}: " + " ".join(f"{b:02x}" for b in self.data)


@cocotb.test()
async def handles_test(dut):
    Packet.n_made = 0
    a = None
    print(f"a is {a}")
    a = Packet([0x80, 0x11])
    b = a
    b.data.append(0x22)
    c = copy.copy(a)
    c.data.append(0x33)
    d = copy.deepcopy(a)
    d.data.append(0x44)
    for name, p in (("a", a), ("b", b), ("c", c), ("d", d)):
        print(f"{name}: {p}")
    print(f"a is b: {a is b}, a is c: {a is c}, a.data is c.data: {a.data is c.data}, "
          f"a.data is d.data: {a.data is d.data}, Packet.n_made: {Packet.n_made}")


@cocotb.test()
async def reuse_test(dut):
    Packet.n_made = 0
    kept_once = []
    p = Packet()
    for k in range(3):
        p.data.clear()
        p.data.append(k)
        p.data.append(0xA0 + k)
        kept_once.append(p)

    kept_new = []
    for k in range(3):
        p = Packet()
        p.data.append(k)
        p.data.append(0xA0 + k)
        kept_new.append(p)

    for i, p in enumerate(kept_once):
        print(f"one Packet, reused: [{i}] {p}")
    for i, p in enumerate(kept_new):
        print(f"a new Packet each:  [{i}] {p}")


@cocotb.test()
async def none_test(dut):
    p = None
    print("appending a beat to p")
    p.data.append(0x80)
    print("appended")


class Component:
    def __init__(self, name):
        self.name = name
        self.n_errors = 0

    def kind(self):
        return "a Component"

    def report(self):
        print(f"report() of Component, on {self.name}: {self.kind()}, {self.n_errors} errors")


class Scoreboard(Component):
    def __init__(self, name):
        super().__init__(name)
        self.expected = []

    def kind(self):
        return "a Scoreboard"


class ForgetfulScoreboard(Component):
    def __init__(self, name):
        self.expected = []        # no super().__init__(name)

    def kind(self):
        return "a ForgetfulScoreboard"


@cocotb.test()
async def dispatch_test(dut):
    Component("c").report()
    Scoreboard("sb").report()


@cocotb.test()
async def super_test(dut):
    sb = ForgetfulScoreboard("sb")
    print(f"made {sb.kind()}; its attributes: {sorted(vars(sb))}")
    sb.report()


class Sink:
    beats = []                    # in the class body: one list, shared

    def __init__(self, name):
        self.name = name


class OwnSink:
    def __init__(self, name):
        self.name = name
        self.beats = []           # in __init__: a list for each object


@cocotb.test()
async def class_attr_test(dut):
    for cls in (Sink, OwnSink):
        s0, s1 = cls("out0"), cls("out1")
        s0.beats.append(0x11)
        s1.beats.append(0x22)
        print(f"{cls.__name__}: out0 took {[hex(b) for b in s0.beats]}, "
              f"out1 took {[hex(b) for b in s1.beats]}")
