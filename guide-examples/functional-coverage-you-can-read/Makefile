# DD105-B guide example: Functional coverage you can read
# (docs/guide/functional-coverage-you-can-read.md).
#
# Random vectors on Lab 01's ALU, counted by cocotb-coverage coverpoints and
# a cross. Each run writes coverage.xml into its run folder, and `make cov`
# merges them, as in every lab. guide-examples/README.md lists the commands
# that made the outputs the page quotes.
#
#   make venv                          once: the course venv (cocotb-coverage)
#   make run TEST=CovPlainTest
#   make cov

TOPLEVEL     := ALU
DUT_SRCS     := ../../labs/lab-01-one-alu-two-frameworks/rtl/alu.sv
PY_DIRS      := .
TEST_MODULES := cov_tests
TESTS        := CovPlainTest CovBiasedTest CovIllegalTest
NEEDS_VENV   := 1
include ../../labs/common/pyuvm.mk
