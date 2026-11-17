"""
DD105-B Lab 03: the tracker, which follows output 0's level and decides what
the router must do with each packet.

  NOROUTE, FULL, OUT0, OUT1   what happens to a packet (0 to 3)
  PktRecord                   one record per packet, handed to the coverage
  Tracker                     the level model and the drop counts

The router decides a packet's fate once, in the cycle its header is
accepted, from ROUTE[DST] and the level of the output that the entry's PORT
names (router-spec.md, Routing). The level of an output in cycle t is the
beats written into it in input handshakes before t, minus the beats taken
from it in output handshakes before t. So the tracker watches the input and
output 0, once per cycle, and handles each cycle's input handshake before its
output handshake: a header sees only earlier cycles' handshakes.

It looks at the pins at the falling edge in the middle of each cycle, as the
monitors do, where nothing is changing. One coroutine reads both streams, so
the order within a cycle is the order of the code.

Nothing watches output 1 in this testbench, and output 1's sink is always
ready, so the tracker takes output 1's level as 0.

The tracker checks nothing itself. It counts the drops it predicts, which
Env.check_drops() compares with DROP_CNT, and it hands each packet's record
to the coverage when the packet's last beat goes in.
"""

from cocotb.triggers import FallingEdge

NOROUTE, FULL, OUT0, OUT1 = 0, 1, 2, 3
FATE_NAMES = ("NOROUTE", "FULL", "OUT0", "OUT1")


class PktRecord:
    """What the coverage samples for one packet."""

    def __init__(self, dst, level):
        self.dst = dst          # the header's DST
        self.length = 0         # beats taken from the input, header included
        self.fate = None        # NOROUTE, FULL, OUT0 or OUT1
        self.level = level      # the level of output ROUTE[DST].PORT in the header's cycle


class Tracker:
    def __init__(self, dut, cfg, sample_pkt, log):
        self.dut = dut
        self.cfg = cfg
        self.sample_pkt = sample_pkt    # called with each packet's PktRecord
        self.log = log
        self.level0 = 0                 # output 0's level, as of the cycles handled so far
        self.max_level0 = 0             # the highest level a header saw
        self.noroute_cnt = 0            # drops since DROP_CNT was last cleared
        self.full_cnt = 0
        self.n_pkts = 0
        self.n_fate = [0, 0, 0, 0]
        self.cur = None                 # the packet coming in, or None between packets
        self.to_out0 = False            # True if cur's beats are written into output 0

    async def run(self):
        d = self.dut
        while True:
            await FallingEdge(d.clk)
            if not d.rst_n.value:
                # A reset empties both outputs and abandons the packet coming in.
                self.level0 = 0
                self.cur = None
                continue
            if d.in_valid.value and d.in_ready.value:
                self.in_beat(int(d.in_data.value), bool(d.in_last.value))
            if d.out0_valid.value and d.out0_ready.value:
                self.level0 -= 1

    def in_beat(self, data, last):
        """A beat taken from the input."""
        if self.cur is None:
            # The header: the router decides here what happens to the whole packet.
            dst = data >> 6
            port = self.cfg.route_port(dst)
            self.cur = PktRecord(dst, 0 if port == 1 else self.level0)  # output 1's level is taken as 0
            self.max_level0 = max(self.max_level0, self.cur.level)
            self.to_out0 = False
            if not self.cfg.route_en(dst):
                self.cur.fate = NOROUTE
                self.noroute_cnt += 1
            elif self.cur.level > 8:
                self.cur.fate = FULL
                self.full_cnt += 1
            elif port == 1:
                self.cur.fate = OUT1
            else:
                self.cur.fate = OUT0
                self.to_out0 = True
        self.cur.length += 1
        # A forwarded packet's first 8 beats are written to its output, and
        # the 8th always ends it (router-spec.md, Oversize packets).
        if self.to_out0 and self.cur.length <= 8:
            self.level0 += 1
        if last:
            self.n_pkts += 1
            self.n_fate[self.cur.fate] += 1
            self.sample_pkt(self.cur)
            self.cur = None

    def clear_drops(self):
        """The test wrote DROP_CNT, which clears both counters."""
        self.noroute_cnt = 0
        self.full_cnt = 0

    def drop_cnt(self):
        """DROP_CNT as the router should have it: FULL_CNT in bits 15:8 and
        NOROUTE_CNT in bits 7:0, each stopping at 255 (router-spec.md,
        DROP_CNT)."""
        return (min(self.full_cnt, 255) << 8) | min(self.noroute_cnt, 255)

    def report(self):
        n = self.n_fate
        self.log.info(f"[TRK] {self.n_pkts} packets: {n[OUT0]} to output 0, {n[OUT1]} to output 1, "
                      f"{n[NOROUTE]} NOROUTE, {n[FULL]} FULL; the highest level a header saw was "
                      f"{self.max_level0}")
