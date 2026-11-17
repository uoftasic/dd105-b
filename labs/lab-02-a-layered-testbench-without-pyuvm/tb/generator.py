"""
DD105-B Lab 02: the generator.

Makes cfg.n packets and puts them in a queue for the driver. Each header is
(DST << 6) | tag: DST is picked from cfg.dsts, and the tag is the packet's
sequence number (0, 1, 2, ... wrapping at 64), so you can find a packet in a
log by its header. The other beats are random bytes, and about one beat in
four waits 1 to 3 idle cycles before it is offered.

The values come from Python's `random`, which cocotb seeds with the run's
seed, so `make run SEED=7` changes them. Lab 03 replaces this with
constrained-random packets.
"""

import random

from packet import Packet


class Generator:
    def __init__(self, cfg, to_drv):
        self.cfg = cfg
        self.to_drv = to_drv        # a cocotb.queue.Queue of Packets

    async def run(self):
        for k in range(self.cfg.n):
            n = self.cfg.length or random.randint(1, 8)
            dst = int(random.choice(self.cfg.dsts))
            p = Packet()
            for i in range(n):
                p.data.append((dst << 6) | (k & 0x3F) if i == 0 else random.randrange(256))
                p.gaps.append(random.randint(1, 3) if random.randrange(4) == 0 else 0)
            await self.to_drv.put(p)
