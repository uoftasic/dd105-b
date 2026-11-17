"""
DD105-B Lab 03: functional coverage, with cocotb-coverage (reference
solution).

The tracker calls sample_pkt() once for every packet the router took from
the input, when its last beat goes in, with a PktRecord (tracker.py):

  rec.length  its length in beats, 1 to 8
  rec.dst     its DST, 0 to 3
  rec.fate    NOROUTE, FULL, OUT0 or OUT1, which are 0 to 3
  rec.level   the level of the output its route names, in the cycle its
              header was accepted, 0 to 16

In cocotb-coverage a coverpoint is a decorator on the function that is
called with the values, here sample_pkt(). Each decorator takes the value it
counts out of the function's arguments with its xf=, and finds the bin it
falls in. The function's body stays empty.

report() runs once, at the end of every test. It writes the hit count of
every bin to coverage.xml in the run's folder, where `make cov` finds it, and
logs one line.
"""

from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db

# The level's bins are ranges. A bin that is a tuple matches only a value
# equal to the tuple unless the coverpoint has a rel= that says what "in the
# bin" means; without one, low and high are never hit, and nothing says so
# (Part 2).
LEVEL_BINS = [(0, 0), (1, 7), (8, 8), (9, 9), (10, 16)]


def in_range(value, rng):
    return rng[0] <= value <= rng[1]


@CoverPoint("router.pkt.len", xf=lambda rec: rec.length, bins=list(range(1, 9)),
            bins_labels=[f"len{n}" for n in range(1, 9)])
@CoverPoint("router.pkt.dst", xf=lambda rec: rec.dst, bins=[0, 1, 2, 3],
            bins_labels=["dst0", "dst1", "dst2", "dst3"])
@CoverPoint("router.pkt.fate", xf=lambda rec: rec.fate, bins=[0, 1, 2, 3],
            bins_labels=["noroute", "full", "out0", "out1"])
@CoverPoint("router.pkt.level", xf=lambda rec: rec.level, bins=LEVEL_BINS, rel=in_range,
            bins_labels=["empty", "low", "at_8", "at_9", "high"])
@CoverCross("router.pkt.x_fate_level", items=["router.pkt.fate", "router.pkt.level"])
def sample_pkt(rec):
    pass


def report(log):
    if "router.pkt" not in coverage_db:
        log.info("[COV] no coverpoint named router.pkt.* yet, so no coverage.xml")
        return
    coverage_db.export_to_xml("coverage.xml")
    pkt = coverage_db["router.pkt"]
    log.info(f"[COV] router.pkt: {pkt.coverage} of {pkt.size} bins hit; coverage.xml written")
