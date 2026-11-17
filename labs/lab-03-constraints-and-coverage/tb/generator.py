"""
DD105-B Lab 03: the generator.

Makes packets and puts them in a queue for the driver. Lab 02's generator
picked every value with Python's random; this one randomizes a RandPacket,
so the constraints in packet.py decide its DST and its length. Each header
is still (DST << 6) | tag, and the tag is the packet's sequence number (0, 1,
2, ... wrapping at 64), so you can find a packet in a log by its header.

Every RandPacket is made and randomized here, inside the test. pyvsc takes
an object's random state from Python's random at the object's first
randomize(), and cocotb seeds Python's random with the run's seed, so
`make run SEED=7` changes the packets and the same seed repeats them.
"""

from packet import RandPacket


class Generator:
    def __init__(self, cfg, to_drv):
        self.cfg = cfg
        self.to_drv = to_drv        # a cocotb.queue.Queue of Packets
        self.n_made = 0             # packets passed to the driver so far

    def new_packet(self):
        """A new RandPacket that knows which routes cfg enables, not yet
        randomized."""
        p = RandPacket()
        p.route_en = sum(1 << d for d in range(4) if self.cfg.route_en(d))
        return p

    async def run(self, n):
        """Randomize n packets and pass them to the driver."""
        for _ in range(n):
            p = self.new_packet()
            try:
                p.randomize()
            except Exception as e:
                raise RuntimeError(f"generator: RandPacket randomize() failed with routes "
                                   f"{self.cfg.routes}: {type(e).__name__}") from None
            await self.put(p)

    async def put(self, p):
        """Give p the next tag and pass it to the driver."""
        p.tag = self.n_made & 0x3F
        p.data[0] = (int(p.hdr_dst) << 6) | p.tag
        self.n_made += 1
        await self.to_drv.put(p)
