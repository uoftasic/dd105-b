# DD105-B guide example: The factory and ConfigDB
# (docs/guide/the-factory-and-configdb.md).
#
# The monitors example's environment, unchanged, and tests that change what
# it builds and how it's set up. It runs the monitors example's tests too, so
# MonRandTest works here with +OVERRIDE. The ALU's +BUG switch works as in the
# monitors example. guide-examples/README.md lists the commands that made the
# outputs the page quotes.
#
#   make venv                          once: the course venv
#   make check-all TEST=FacFlagsTest
#   make run TEST=MonRandTest PLUSARGS=+OVERRIDE=AluItem,AluEqualItem BUG=A01

TOPLEVEL      := ALU
DUT_SRCS      := ../../labs/lab-01-one-alu-two-frameworks/rtl/alu.sv
PY_DIRS       := . ../monitors-analysis-ports-and-scoreboards ../sequences-sequencers-and-drivers
TEST_MODULES  := fac_tests mon_tests
TESTS         := FacEqualTest FacCtorTest FacFlagsTest FacTypoTest FacPrecTest FacGlobTest \
                 FacMissingTest MonRandTest
BUG_LIST      := A01 A02 A03
BUG_CATALOGUE := ../../labs/lab-01-one-alu-two-frameworks/bugs.json
NEEDS_VENV    := 1
include ../../labs/common/pyuvm.mk
