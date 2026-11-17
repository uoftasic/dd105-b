# DD105-B Lab 05: Protocol rules and backpressure. README.md says what's here.
#
# Our Lab 04 pyuvm testbench for the router, with assertions bound into the
# router, a sink that can answer each beat, and a virtual sequence. One build
# serves every test, seed and planted bug:
#
#   make build                 build the simulator (the router and the assertions)
#   make run                   RouterTest on the golden router
#   make run BUG=B10           the same, with planted bug B10 on
#   make run TEST=RouterLab05Test
#   make check                 the verdict: pass on the golden router, fail on B11
#   make check-all             the same against B11, B10 and B12
#
# `make help` lists every target; labs/common/README.md describes the shared ones.

TOPLEVEL      := router
DUT_F         := build/rtl/router.f
BUILD_DEPS    := build/rtl/router.f
# The assertions, bound into the router. A lab with SVA_SRCS gets
# +verilator+error+limit+$(ERROR_LIMIT) on every run, so every failing
# assertion prints and the run goes on; ERROR_LIMIT=1 is the simulator's own
# limit, which ends the run at the first failure.
SVA_SRCS      := tb/router_sva.sv tb/router_sva_bind.sv
PY_DIRS       := tb
TEST_MODULES  := test_router
TESTS         := RouterTest RouterLab05Test RouterSinkTest RouterInjectTest RouterStallTest \
                 RouterRandTest RouterFillTest RouterClassTest
# B11 first: make check with no BUG grades it, and it's the one bug of the
# three that Lab 04's testbench misses.
BUG_LIST      := B11 B10 B12
BUG_CATALOGUE := ../common/bugs.py
# The packets are pyvsc objects and the coverage is cocotb-coverage's.
NEEDS_VENV    := 1
include ../common/pyuvm.mk

build/rtl/router.f: $(wildcard ../common/rtl/*.sv) ../common/bugs.py ../common/inject.py
	python3 ../common/inject.py --all --out build/rtl

# ── line counts ──────────────────────────────────────────────────────────────
# FILES names another testbench to count beside this one, for example your
# Lab 04 files: make loc FILES="../lab-04-the-same-testbench-in-pyuvm/tb/*.py"

TB_FILES := tb/router_agents.py tb/router_env.py tb/router_vseq.py tb/test_router.py \
            tb/router_sva.sv tb/router_sva_bind.sv
FILES    ?=

.PHONY: loc

## loc — lines and code lines in this lab's testbench, and in FILES if you give it
loc:
	@echo "This lab's testbench:"
	@$(PYTHON) $(LAB_DIR)/src/loc.py $(TB_FILES)
	@if [ -n "$(strip $(FILES))" ]; then echo "FILES:"; $(PYTHON) $(LAB_DIR)/src/loc.py $(FILES); fi
