# DD105-B Lab 01: the cocotb side.
#
# You don't run this file yourself. The lab's Makefile runs it, from the lab
# folder, for `make cocotb` and `make cocotb-all`. It is a Makefile of its
# own because one Makefile has one BASE_TEST. The cocotb test is plain
# cocotb, with no BaseTest, so its runs end without the line BaseTest prints,
# and BASE_TEST := 0 tells the verdict that a pass doesn't need that line.
#
#   TB    the Python module with the tests, in this folder (default test_alu)
#   BUG   empty for the golden ALU, or A01, A02 or A03
#
# The ALU is elaborated on its own as the top level (TOPLEVEL := ALU), as in
# DD104 Lab 03, so a test written there for dut.ALUop, dut.A, dut.B,
# dut.ALUout, dut.N and dut.Z runs here unchanged. TEST is a regular
# expression that matches every test in TB, so one run is t01, t02 and t03,
# and the run folder is named after TB instead. The bug is picked at run time
# with +BUG, so one build serves all four designs. The build goes in the
# lab's build/cocotb/, so the lab's `make clean` removes it.

HERE          := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
TB            ?= test_alu
TOPLEVEL      := ALU
DUT_SRCS      := ../rtl/alu.sv
PY_DIRS       := .
TEST_MODULES  := $(TB)
TESTS         := t01_one_vector_per_operation t02_every_vector_the_alu_can_be_given \
                 t03_the_undefined_opcodes
TEST          ?= .*
RUN_NAME      ?= $(TB)-s$(SEED)$(if $(BUG),-$(BUG))
BUG_LIST      := A03 A01 A02
BUG_CATALOGUE := ../bugs.json
BASE_TEST     := 0
BUILD_DIR     ?= $(abspath $(HERE)/../build/cocotb)
include $(HERE)/../../common/pyuvm.mk
