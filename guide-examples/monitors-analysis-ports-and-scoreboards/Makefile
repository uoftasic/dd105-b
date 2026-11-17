# DD105-B guide example: Monitors, analysis ports and scoreboards
# (docs/guide/monitors-analysis-ports-and-scoreboards.md).
#
# A complete agent for Lab 01's ALU and three subscribers on its monitor's
# analysis port. The ALU's +BUG switch works here too, so `make run BUG=A01`
# runs the same test on the same build with the ALU whose SUB computes B - A.
# guide-examples/README.md lists the commands that made the outputs the page
# quotes.
#
#   make venv                          once: the course venv
#   make run TEST=MonRandTest BUG=A01
#   make check-all

TOPLEVEL      := ALU
DUT_SRCS      := ../../labs/lab-01-one-alu-two-frameworks/rtl/alu.sv
PY_DIRS       := . ../sequences-sequencers-and-drivers
TEST_MODULES  := mon_tests
TESTS         := MonRandTest MonAliasTest MonConnectTest
BUG_LIST      := A01 A02 A03
BUG_CATALOGUE := ../../labs/lab-01-one-alu-two-frameworks/bugs.json
NEEDS_VENV    := 1
include ../../labs/common/pyuvm.mk
