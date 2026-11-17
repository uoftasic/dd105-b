"""
DD105-B labs/ref probe: what pyvsc 1.1.0 does with the packet's constraints,
outside the simulator. Run it from labs/ref with the course venv's Python,
or with `bash probes/run.sh`, which finds that Python:

    <venv>/bin/python probes/pyvsc_probe.py

Each numbered line is one question, answered by drawing from a class shaped
like tb/stream_agents.py's RandPkt: a length kind drawn with dist, the
length from the kind's range, DST and a tag.
"""

import collections
import random
import time

import vsc
from pyuvm import uvm_sequence_item


@vsc.randobj
class Pkt(uvm_sequence_item):
    def __init__(self, name="pkt"):
        super().__init__(name)
        self.kind = vsc.rand_bit_t(2)
        self.length = vsc.rand_uint8_t()
        self.dst = vsc.rand_bit_t(2)
        self.tag = vsc.rand_bit_t(6)
        self.w_one, self.w_mid, self.w_eight, self.w_over = (vsc.uint8_t(20), vsc.uint8_t(50),
                                                             vsc.uint8_t(20), vsc.uint8_t(10))
        self.max_len = vsc.uint8_t(12)
        self.built = 0

    @vsc.constraint
    def c_kind(self):
        vsc.dist(self.kind, [vsc.weight(0, self.w_one), vsc.weight(1, self.w_mid),
                             vsc.weight(2, self.w_eight), vsc.weight(3, self.w_over)])

    @vsc.constraint
    def c_len(self):
        with vsc.if_then(self.kind == 0):
            self.length == 1
        with vsc.else_if(self.kind == 1):
            self.length.inside(vsc.rangelist((2, 7)))
        with vsc.else_if(self.kind == 2):
            self.length == 8
        with vsc.else_then:
            self.length.inside(vsc.rangelist((9, 255)))
            self.length <= self.max_len

    def post_randomize(self):
        self.built += 1


def kinds(p, n):
    c = collections.Counter()
    for _ in range(n):
        p.randomize()
        c[int(p.kind)] += 1
    return [c[k] for k in range(4)]


def tags(seed_before_build, seed_after_build, seed_after_first, n=6):
    random.seed(seed_before_build)
    p = Pkt()
    if seed_after_build is not None:
        random.seed(seed_after_build)
    out = []
    for i in range(n):
        p.randomize()
        out.append(int(p.tag))
        if i == 0 and seed_after_first is not None:
            random.seed(seed_after_first)
    return out


random.seed(1)
p = Pkt()
print("1  a @vsc.randobj subclass of uvm_sequence_item builds:", type(p).__name__, p.get_name())
print("2  kind with dist 20/50/20/10, 1000 draws:", kinds(p, 1000))
p.w_one, p.w_mid, p.w_eight, p.w_over = 0, 0, 0, 100
print("3  the weights are vsc.uint8_t attributes; set to 0/0/0/100, 200 draws:", kinds(p, 200))
p.w_one, p.w_mid, p.w_eight, p.w_over = 20, 50, 20, 10
c = collections.Counter()
for _ in range(300):
    with p.randomize_with() as it:
        it.dst.inside(vsc.rangelist(1, 3))
    c[int(p.dst)] += 1
print("4  dst.inside(rangelist(1, 3)) inline, 300 draws:", dict(sorted(c.items())))
print("5  post_randomize() ran", p.built, "times in", 1000 + 200 + 300, "randomize() calls")
base = tags(7, None, None)
print("6  seed 7 then build:                        ", base)
print("   seed 7, build, seed 99 before randomize():", tags(7, 99, None))
print("   seed 7, build, seed 12345 before it:      ", tags(7, 12345, None))
print("   seed 7, build, randomize(), then seed 99: ", tags(7, None, 99))
print("   seed 7, build, randomize(), then seed 123:", tags(7, None, 123))
t0 = time.perf_counter()
for _ in range(500):
    p.randomize()
t1 = time.perf_counter()
for _ in range(500):
    Pkt().randomize()
t2 = time.perf_counter()
for _ in range(500):
    Pkt()
t3 = time.perf_counter()
print(f"7  randomize() on one object: {500 / (t1 - t0):.0f} per s; a new object and randomize(): "
      f"{500 / (t2 - t1):.0f} per s; a new object alone: {500 / (t3 - t2):.0f} per s")
