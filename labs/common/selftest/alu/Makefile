# SELFTEST design for labs/common/selftest/selftest.py. Not a lab: DD105-A's
# selftest ALU with three planted bugs, its bound assertion, and the pyuvm
# fixture tests in tb/test_st.py.
TOPLEVEL      := st_alu
DUT_SRCS      := rtl/st_alu.sv
SVA_SRCS      := tb/st_sva.sv
PY_DIRS       := tb
TEST_MODULES  := test_st
TESTS         := StGoodTest StEmptyTest
BUG_LIST      := B01 B02 B03
BUG_CATALOGUE := bugs.json
BUG_CONFIRM   := DD105-BUG: {id} enabled
PLUSARGS      ?= +N=300
RUN_TIMEOUT   ?= 60
include ../../pyuvm.mk
