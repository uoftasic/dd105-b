"""
DD105-B Lab 02: the transaction, and the test's knobs.

  Packet     one packet: its beats, header first
  RouterCfg  what the test sends and how the router is configured, read from
             plusargs, so a different test needs no rebuild
"""

import cocotb


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
    """The knobs. Each has a plusarg, so
    `make run PLUSARGS="+N=16 +DSTS=0"` changes the test without rebuilding
    the simulator.

      +N=<n>          packets to send (100)
      +DSTS=<digits>  the DST values the generator picks from (0123)
      +ROUTES=<abcd>  ROUTE0 to ROUTE3: 0 or 1 is the output, - is disabled (0110)
      +LEN=<n>        every packet n beats long, 1 to 8; 0 picks each length at random (0)
      +SHOW=<n>       each monitor logs the first n packets it sees (0)
    """

    def __init__(self, n=100, dsts="0123", routes="0110", length=0, show=0):
        self.n, self.dsts, self.routes, self.length, self.show = n, dsts, routes, length, show

    @classmethod
    def from_plusargs(cls):
        args = cocotb.plusargs
        cfg = cls()
        try:
            cfg.n = int(args.get("N", cfg.n))
            cfg.length = int(args.get("LEN", cfg.length))
            cfg.show = int(args.get("SHOW", cfg.show))
        except ValueError as e:
            raise ValueError(f"+N, +LEN and +SHOW take a whole number: {e}") from None
        cfg.dsts = str(args.get("DSTS", cfg.dsts))
        cfg.routes = str(args.get("ROUTES", cfg.routes))
        if not cfg.dsts or any(c not in "0123" for c in cfg.dsts):
            raise ValueError(f"+DSTS={cfg.dsts}: give one or more DSTs, 0 to 3, for example +DSTS=0123")
        if len(cfg.routes) != 4 or any(c not in "01-" for c in cfg.routes):
            raise ValueError(f"+ROUTES={cfg.routes}: give four characters, each 0, 1 or - (disabled), "
                             "for example +ROUTES=0110")
        if not 0 <= cfg.length <= 8:
            raise ValueError(f"+LEN={cfg.length}: a packet in this lab is 1 to 8 beats (0 picks at random)")
        return cfg

    def route_en(self, d):
        """ROUTE[d].EN, as the test configures it."""
        return self.routes[d] != "-"

    def route_port(self, d):
        """ROUTE[d].PORT, as the test configures it."""
        return 1 if self.routes[d] == "1" else 0

    def describe(self):
        lengths = ("1 to 8 beats" if self.length == 0
                   else f"{self.length} beat{'' if self.length == 1 else 's'}")
        return f"{self.n} packets, DST from {self.dsts}, routes {self.routes}, {lengths}"
