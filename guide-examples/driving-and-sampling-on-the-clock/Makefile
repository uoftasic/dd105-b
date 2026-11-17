# DD105-B guide example: Driving and sampling on the clock.
#
# The design is the golden router, labs/common/rtl (no planted bugs). The
# tests are plain cocotb, as in Lab 02, so BASE_TEST := 0.
# guide-examples/README.md lists the commands whose output the page quotes.
#
#   make build
#   make run TEST=edge_test             the pins read at each edge, three ways
#   make waves TEST=edge_test           the same run, with waves.fst
#   make run TEST=monitor_test          three input monitors, sampling at different times
#   make run TEST=readonly_test         a write in the ReadOnly phase
#   make run TEST=same_edge_test        a write and two reads at one rising edge
#   make clean

TOPLEVEL      := router
DUT_F         := ../../labs/common/rtl/router.f
PY_DIRS       := .
TEST_MODULES  := edges_demo
TESTS         := edge_test monitor_test readonly_test same_edge_test
BASE_TEST     := 0
include ../../labs/common/pyuvm.mk
