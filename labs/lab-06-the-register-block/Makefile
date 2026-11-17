# DD105-B Lab 06: The register block. README.md says what's here.
#
# Our Lab 05 pyuvm testbench for the router, with a register model, its
# adapter and its predictor, and scoreboard checks on STATUS, PSLVERR and
# irq. One build serves every test, seed and planted bug:
#
#   make build                 build the simulator (the router and the assertions)
#   make run                   RouterTest on the golden router
#   make run BUG=B14           the same, with planted bug B14 on
#   make run TEST=RouterLab06Test
#   make regcheck              build the register model on its own, outside the simulator
#   make check                 the verdict: pass on the golden router, fail on B01
#   make check-all             the same against B01, B02, B03, B04 and B14
#
# `make help` lists every target; labs/common/README.md describes the shared ones.

TOPLEVEL      := router
DUT_F         := build/rtl/router.f
BUILD_DEPS    := build/rtl/router.f
# Lab 05's assertions, bound into the router. A lab with SVA_SRCS gets
# +verilator+error+limit+$(ERROR_LIMIT) on every run, so every failing
# assertion prints and the run goes on.
SVA_SRCS      := tb/router_sva.sv tb/router_sva_bind.sv
PY_DIRS       := tb
TEST_MODULES  := test_router
TESTS         := RouterTest RouterLab06Test RouterLab05Test RouterSinkTest RouterInjectTest \
                 RouterStallTest RouterRandTest RouterFillTest RouterClassTest
# B01 first: make check with no BUG grades it. Lab 05's testbench misses all
# five.
BUG_LIST      := B01 B02 B03 B04 B14
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
# Lab 05 files: make loc FILES="../lab-05-protocol-rules-and-backpressure/tb/*.py"

TB_FILES := tb/router_agents.py tb/router_env.py tb/router_ral.py tb/router_vseq.py \
            tb/test_router.py tb/router_sva.sv tb/router_sva_bind.sv
FILES    ?=

.PHONY: loc predict

## loc — lines and code lines in this lab's testbench, and in FILES if you give it
loc:
	@echo "This lab's testbench:"
	@$(PYTHON) $(LAB_DIR)/src/loc.py $(TB_FILES)
	@if [ -n "$(strip $(FILES))" ]; then echo "FILES:"; $(PYTHON) $(LAB_DIR)/src/loc.py $(FILES); fi

## predict — what predict() does to the mirror of your model's registers (Part 3)
predict:
	@PYTHONPATH=$(LAB_DIR)/tb $(PYTHON) $(LAB_DIR)/src/predict.py
