# DD105-B guide example: Python classes and cocotb concurrency.
#
# Plain cocotb tests, as in Lab 02, so BASE_TEST := 0. cocotb needs a design
# to run in, and this is Lab 01's ALU, which the tests here never touch.
# guide-examples/README.md lists the commands whose output the page quotes.
#
#   make build
#   make run TEST=handles_test          and the other tests in TESTS
#   make clean

TOPLEVEL      := ALU
DUT_SRCS      := ../../labs/lab-01-one-alu-two-frameworks/rtl/alu.sv
PY_DIRS       := .
TEST_MODULES  := classes_demo tasks_demo
TESTS         := handles_test reuse_test none_test dispatch_test super_test class_attr_test \
                 start_test capture_test queue_test event_test cancel_test end_test \
                 unwatched_test joined_test first_test first_result_test
BASE_TEST     := 0
include ../../labs/common/pyuvm.mk
