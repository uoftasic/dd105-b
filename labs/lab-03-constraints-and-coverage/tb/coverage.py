"""
DD105-B Lab 03: functional coverage, with cocotb-coverage. You write the
coverpoints (Part 2).

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

from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db  # noqa: F401

# TODO (Part 2): the coverpoints and the cross, as decorators on sample_pkt().


def sample_pkt(rec):
    pass


def report(log):
    if "router.pkt" not in coverage_db:
        log.info("[COV] no coverpoint named router.pkt.* yet, so no coverage.xml")
        return
    coverage_db.export_to_xml("coverage.xml")
    pkt = coverage_db["router.pkt"]
    log.info(f"[COV] router.pkt: {pkt.coverage} of {pkt.size} bins hit; coverage.xml written")
