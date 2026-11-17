"""
DD105-B Lab 03: the transaction, the test's knobs, and the random packet.

  Packet      one packet: its beats, header first (Lab 02's, unchanged)
  RouterCfg   the routing table and the knobs, read from plusargs
  RandPacket  a Packet whose DST and length kind pyvsc picks. You give it
              its constraints in Part 3.
"""

import enum
import random

import cocotb
import vsc


class Packet:
    """One packet. The generator fills in data and gaps; a monitor fills in
    data, t_first and t_last from what it saw on the pins."""

    def __init__(self, data=None, gaps=None):
        self.data = list(data or [])  # the beats; data[0] is the header, DST its bits 7:6
        self.gaps = list(gaps or [])  # stimulus only: idle cycles before each beat
        self.t_first = None           # monitors: when the first beat's handshake was seen (ns)
        self.t_last = None            # monitors: the same for the last beat

    def dst(self):
        return self.data[0] >> 6

    def same(self, other):
        """Two packets are the same if they have the same beats. The gaps and
        the times say how a packet travelled, not what it is, so they don't
        count."""
        return self.data == other.data

    def __str__(self):
        """'dst 2, 3 beats: 85 3c f0'"""
        n = len(self.data)
        beats = " ".join(f"{b:02x}" for b in self.data)
        return f"dst {self.dst()}, {n} beat{'' if n == 1 else 's'}: {beats}"


class RouterCfg:
    """The knobs. Each has a plusarg, so `make run PLUSARGS="+N=16"` changes
    the test without rebuilding the simulator. Lab 02's +DSTS and +LEN are
    gone: RandPacket's constraints now choose the DST and the length.

      +N=<n>          packets to send (100 in router_class_test; 200 per phase
                      in router_rand_test, which reads it itself)
      +ROUTES=<abcd>  ROUTE0 to ROUTE3: 0 or 1 is the output, - is disabled
                      (0110, router_class_test's routing table)
      +SHOW=<n>       each monitor logs the first n packets it sees (0)

    routes is also the routing table the router has: Env.write_routes()
    changes both together, and the scoreboard, the tracker and the generator
    read it from here.
    """

    def __init__(self, n=100, routes="0110", show=0):
        self.n, self.routes, self.show = n, routes, show

    @classmethod
    def from_plusargs(cls):
        args = cocotb.plusargs
        cfg = cls()
        try:
            cfg.n = int(args.get("N", cfg.n))
            cfg.show = int(args.get("SHOW", cfg.show))
        except ValueError as e:
            raise ValueError(f"+N and +SHOW take a whole number: {e}") from None
        cfg.routes = cls.check_routes(str(args.get("ROUTES", cfg.routes)))
        return cfg

    @staticmethod
    def check_routes(routes):
        if len(routes) != 4 or any(c not in "01-" for c in routes):
            raise ValueError(f"routes {routes}: give four characters, each 0, 1 or - (disabled), "
                             "for example 0110")
        return routes

    def route_en(self, d):
        """ROUTE[d].EN, as the test configures it."""
        return self.routes[d] != "-"

    def route_port(self, d):
        """ROUTE[d].PORT, as the test configures it."""
        return 1 if self.routes[d] == "1" else 0

    def describe(self):
        return f"{self.n} packets, routes {self.routes}"


# ── the random packet ───────────────────────────────────────────────────────
# A packet whose header DST and length come from pyvsc's randomize(). The
# generator sets route_en, randomizes it and sets the tag; post_randomize()
# fills in data and gaps from the fields, as Lab 02's generator filled them
# from Python's random.
#
# Its DST field is called hdr_dst, because Packet.dst() already exists and
# the monitor and the scoreboard call it.

class LenKind(enum.IntEnum):
    LEN_ONE = 0     # 1 beat
    LEN_MID = 1     # 2 to 7 beats
    LEN_MAX = 2     # 8 beats


@vsc.randobj
class RandPacket(Packet):
    def __init__(self):
        super().__init__()
        self.hdr_dst = vsc.rand_bit_t(2)       # the header's DST: which routing table entry it uses
        self.kind = vsc.rand_enum_t(LenKind)   # one beat, 2 to 7 beats, or exactly 8
        self.length = 0                        # beats, header included
        self.tag = 0                           # the header's other six bits: the generator's count
        self.route_en = vsc.uint8_t(0xF)       # set by the generator: bit d is ROUTE[d].EN

    # Only to enabled routes, so a random packet is never dropped as NOROUTE.
    # The bit is picked with a shift because the index, hdr_dst, is random.
    @vsc.constraint
    def c_dst(self):
        ((self.route_en >> self.hdr_dst) & 1) == 1

    # TODO (Part 3): weights for the three kinds, and a constraint that picks
    # length from kind. Then make length random and delete its assignment in
    # post_randomize().

    def post_randomize(self):
        """pyvsc calls this after every randomize(). As shipped, no constraint
        mentions kind, so nothing says how often each kind should come out,
        and randomize() draws kind without the solver. Then length is picked
        here, from the kind that came out."""
        if self.kind == LenKind.LEN_ONE:
            self.length = 1
        elif self.kind == LenKind.LEN_MID:
            self.length = random.randint(2, 7)
        else:
            self.length = 8
        self.build(random_gaps=True)

    def build(self, random_gaps):
        """Fill data and gaps from hdr_dst, tag and length. The payload is
        random, and with random_gaps about one beat in four waits 1 to 3 idle
        cycles before it is offered, as in Lab 02; without, the beats go back
        to back. The payload and the gaps come from Python's random rather
        than from the solver, because pyvsc randomizes only a few hundred
        objects a second (make traps, line 7) and no constraint mentions
        them."""
        n = int(self.length)
        self.data = [(int(self.hdr_dst) << 6) | (self.tag & 0x3F)] + \
                    [random.randrange(256) for _ in range(n - 1)]
        self.gaps = [random.randint(1, 3) if random_gaps and random.randrange(4) == 0 else 0
                     for _ in range(n)]

    @staticmethod
    def make(dst, length, tag=0):
        """A packet built by hand, without the solver: `length` beats for DST
        `dst`, back to back."""
        p = RandPacket()
        p.hdr_dst = dst
        p.kind = (LenKind.LEN_ONE if length == 1 else
                  LenKind.LEN_MID if length < 8 else LenKind.LEN_MAX)
        p.length = length
        p.tag = tag
        p.build(random_gaps=False)
        return p
