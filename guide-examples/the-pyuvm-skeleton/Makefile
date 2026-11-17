# DD105-B guide example: The pyuvm skeleton (docs/guide/the-pyuvm-skeleton.md).
#
# A component tree with no design to test: every component prints a line in
# every phase. Lab 01's ALU is the toplevel only because cocotb needs one.
# guide-examples/README.md lists the commands that made the outputs the page
# quotes.
#
#   make run TEST=SkPhaseTest
#   make run TEST=SkPlainErrorTest BASE_TEST=0

TOPLEVEL     := ALU
DUT_SRCS     := ../../labs/lab-01-one-alu-two-frameworks/rtl/alu.sv
PY_DIRS      := .
TEST_MODULES := sk_tests
TESTS        := SkPhaseTest SkNoObjTest SkErrorTest SkPlainErrorTest SkHangTest
include ../../labs/common/pyuvm.mk
