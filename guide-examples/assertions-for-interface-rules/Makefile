# DD105-B guide example for "Assertions for interface rules": a one-beat
# valid/ready stage, its three rules written as assertions, and a bind that
# puts them inside it. One build serves every run:
#
#   make run                                  the golden stage
#   make run BUG=drop                         the stage that drops a waiting beat
#   make run BUG=drop ERROR_LIMIT=1           the same, with the simulator's own error limit
#   make run BUG=drop PLUSARGS=+UNCOUNTED     a test that never reads the checker's count
#   make run BUG=drop PLUSARGS=+READY_PCT=100 a sink that is always ready
#
# guide-examples/README.md lists the runs the page quotes.

TOPLEVEL     := stage
DUT_SRCS     := stage.sv
# The checker and its bind. A folder with SVA_SRCS gets
# +verilator+error+limit+$(ERROR_LIMIT) on every run.
SVA_SRCS     := stage_sva.sv
PY_DIRS      := .
TEST_MODULES := test_stage
TESTS        := StageTest
include ../../labs/common/pyuvm.mk
