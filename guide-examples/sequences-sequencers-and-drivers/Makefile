# DD105-B guide example: Sequences, sequencers and drivers
# (docs/guide/sequences-sequencers-and-drivers.md).
#
# A sequence, a sequencer and a driver for Lab 01's ALU, with a line printed
# at every step of the handshake. guide-examples/README.md lists the commands
# that made the outputs the page quotes.
#
#   make venv                          once: the course venv (the item is a pyvsc randobj)
#   make run TEST=SqTimelineTest

TOPLEVEL     := ALU
DUT_SRCS     := ../../labs/lab-01-one-alu-two-frameworks/rtl/alu.sv
PY_DIRS      := .
TEST_MODULES := sq_tests
TESTS        := SqTimelineTest SqTwoTest SqNestedTest SqReadTest SqDoubleGetTest
NEEDS_VENV   := 1
include ../../labs/common/pyuvm.mk
