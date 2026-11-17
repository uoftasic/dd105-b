# DD105-B Lab 01: One ALU, two frameworks.
#
# Two testbenches for SimProc's ALU from DD104, both on Verilator, one build
# of each:
#
#   make cocotb                the cocotb test (cocotb/test_alu.py) on the golden ALU
#   make cocotb BUG=A03        ... with bug A03 switched on
#   make cocotb-all            ... on the golden ALU and each of A01 to A03
#   make build                 build the pyuvm testbench's simulator
#   make run                   run AluRandTest on the golden ALU
#   make check                 the verdict: pass on the golden ALU, fail on A03
#   make check-all             the same against A03, A01 and A02
#   make loc                   count each testbench's lines
#
# `make help` lists every target; labs/common/README.md describes the ones
# that come from pyuvm.mk.

TOPLEVEL      := ALU
DUT_SRCS      := rtl/alu.sv
PY_DIRS       := tb
TEST_MODULES  := alu_uvm
TESTS         := AluRandTest AluDirectedTest
# A03 first: make check with no BUG grades it, and it's the one bug of the
# three that the shipped scoreboard misses.
BUG_LIST      := A03 A01 A02
BUG_CATALOGUE := bugs.json
include ../common/pyuvm.mk

# ── the cocotb testbench ─────────────────────────────────────────────────────
# cocotb/Makefile does the work, with the same pyuvm.mk. TB picks the Python
# module in cocotb/ (default test_alu).
TB     ?= test_alu
COCOTB := $(MAKE) --no-print-directory -f $(LAB_DIR)/cocotb/Makefile TB=$(TB)

# $(call cocotb_one,<bug or empty>): build if needed, then run every test in
# TB once, with +BUG_ECHO so the log says which ALU ran. Prints how long each
# half took, below cocotb's own report and the verdict.
define cocotb_one
t0=$$(date +%s.%N); $(COCOTB) build || exit 1; t1=$$(date +%s.%N); \
$(COCOTB) run BUG=$(1) PLUSARGS=+BUG_ECHO; rc=$$?; t2=$$(date +%s.%N); \
echo "$(RULE)"; \
awk "BEGIN{printf \" cocotb, $(TB) on Verilator, $(or $(1),the golden ALU): build %.1f s, run %.1f s\n\", $$t1 - $$t0, $$t2 - $$t1}"; \
echo "$(RULE)"; exit $$rc
endef

.PHONY: cocotb cocotb-all loc

## cocotb — the cocotb test (TB=test_alu) on the golden ALU, or on BUG
cocotb:
	@$(call cocotb_one,$(BUG))

## cocotb-all — the cocotb test on the golden ALU, then on A01, A02 and A03 in turn
cocotb-all:
	@for b in "" $(sort $(BUG_LIST)); do echo "$(RULE)"; $(MAKE) --no-print-directory -s cocotb BUG=$$b 2>&1 \
	  | grep -E '^ cocotb, |\*\* TESTS=|\*\* [^ ]+\.[^ ]+ +(PASS|FAIL) |^ *AssertionError: |^ALU: ' \
	  | sed -E 's/^ {20,}//'; done; echo "$(RULE)"

## loc — lines of code in each testbench: cocotb/$(TB).py, then tb/alu_uvm.py
loc:
	@echo "cocotb testbench:"
	@$(PYTHON) $(LAB_DIR)/src/loc.py cocotb/$(TB).py
	@echo "pyuvm testbench:"
	@$(PYTHON) $(LAB_DIR)/src/loc.py tb/alu_uvm.py
