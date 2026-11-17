# DD105-B guide example for "Regressions and seeds": a 4-bit saturating
# counter (satcnt.sv) and three tests (test_seeds.py).
#
#   make seeds TEST=CountTest SEEDS="1 2 3 4 5 6 7 8 9 10"
#   make seeds TEST=CountTest SEEDS="1 2 3 4 5 6 7 8 9 10" BUG=wrap
#   make run TEST=RandomTest SEED=1
#   make run TEST=RandomTest PLUSARGS=+EXTRA=draw
#
# guide-examples/README.md lists the runs the page quotes.

TOPLEVEL     := satcnt
DUT_SRCS     := satcnt.sv
PY_DIRS      := .
TEST_MODULES := test_seeds
TESTS        := CountTest RandomTest RandomTwinTest
# The coverage is cocotb-coverage's, and +EXTRA=vsc_* imports pyvsc: the
# course venv (make venv).
NEEDS_VENV   := 1
include ../../labs/common/pyuvm.mk
