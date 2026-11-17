# DD105-B Lab 07: the capstone. README.md says what's here, and
# docs/labs/lab-07-capstone-overview.md is the lab.
#
# Our Lab 06 pyuvm testbench for the router, with a reset driver, a
# scoreboard that follows a reset with traffic in flight, four corners in the
# coverage, and assertions for the rules about reset. One build serves every
# test, seed and planted bug:
#
#   make build                 build the simulator (the router and the assertions)
#   make run                   RouterTest on the golden router
#   make regress               every test in TESTS on seeds 1 to 10, then the coverage
#   make new / hunt / verdict  a mystery bug from the whole catalogue
#   make check                 the verdict: pass on the golden router, fail on B15
#   make check-all             the same against all 15 bugs
#
# `make help` lists every target; labs/common/README.md describes the shared ones.

TOPLEVEL      := router
DUT_F         := build/rtl/router.f
BUILD_DEPS    := build/rtl/router.f
# The assertions, bound into the router: Lab 05's, and the rules about reset
# (Part 5). A lab with SVA_SRCS gets +verilator+error+limit+$(ERROR_LIMIT) on
# every run, so every failing assertion prints and the run goes on.
SVA_SRCS      := tb/router_sva.sv tb/router_sva_bind.sv
PY_DIRS       := tb
TEST_MODULES  := test_router
# RouterTest comes first: make, check, check-all and the hunts run it.
# TODO (Parts 5 and 6): add RouterResetTest and RouterSaturateTest once
# their sequences are written.
TESTS         := RouterTest RouterLab07Test RouterLab06Test RouterLab05Test RouterSinkTest \
                 RouterInjectTest RouterStallTest RouterRandTest RouterFillTest RouterClassTest
# Every bug in the catalogue. B15, the one this lab's work catches, comes
# first, because `make check` grades the first bug in the list.
BUG_LIST      := B15 B01 B02 B03 B04 B05 B06 B07 B08 B09 B10 B11 B12 B13 B14
BUG_CATALOGUE := ../common/bugs.py
# The register model, which the graders build on its own before any verdict
# (labs/common/regcheck.py): pyuvm reports a wrong model with AssertionError,
# which a run would count as a check that fired.
REG_MODEL     := tb/router_ral.py:RouterRegs
# The packets are pyvsc objects and the coverage is cocotb-coverage's.
NEEDS_VENV    := 1
include ../common/pyuvm.mk

build/rtl/router.f: $(wildcard ../common/rtl/*.sv) ../common/bugs.py ../common/inject.py
	python3 ../common/inject.py --all --out build/rtl

# ── this lab's own targets ───────────────────────────────────────────────────
# FILES names another testbench to count beside this one, for example your
# Lab 06 files: make loc FILES="../lab-06-the-register-block/tb/*.py"

TB_FILES := tb/router_agents.py tb/router_env.py tb/router_ral.py tb/router_vseq.py \
            tb/test_router.py tb/router_sva.sv tb/router_sva_bind.sv
FILES    ?=

.PHONY: loc predict

## loc — lines and code lines in this lab's testbench, and in FILES if you give it
loc:
	@echo "This lab's testbench:"
	@$(PYTHON) $(LAB_DIR)/src/loc.py $(TB_FILES)
	@if [ -n "$(strip $(FILES))" ]; then echo "FILES:"; $(PYTHON) $(LAB_DIR)/src/loc.py $(FILES); fi

## predict — what predict() does to the mirror of the model's registers (Lab 06, Part 3)
predict:
	@PYTHONPATH=$(LAB_DIR)/tb $(PYTHON) $(LAB_DIR)/src/predict.py
