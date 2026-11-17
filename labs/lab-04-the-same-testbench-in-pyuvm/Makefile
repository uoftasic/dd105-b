# DD105-B Lab 04: The same testbench in pyuvm. README.md says what's here.
#
# Lab 03's plain-cocotb testbench for the router, ported to pyuvm. One build
# serves every test, seed and planted bug:
#
#   make venv                  once: the course venv (Lab 03 made it already)
#   make                       build if needed, then run RouterInjectTest
#   make run TEST=RouterRandTest SEED=3
#   make check BUG=B13         the verdict: pass on the golden router, fail on B13
#   make check-all             the same against B06 and B13
#   make loc                   count the testbench's lines (FILES=... adds yours)
#
# `make help` lists every target; labs/common/README.md describes the shared ones.

TOPLEVEL      := router
DUT_F         := build/rtl/router.f
BUILD_DEPS    := build/rtl/router.f
PY_DIRS       := tb
TEST_MODULES  := test_router
TESTS         := RouterInjectTest RouterStallTest RouterRandTest RouterFillTest RouterClassTest
# B06 first: make check with no BUG grades it, and the shipped testbench,
# whose random packets go only to enabled routes, misses it.
BUG_LIST      := B06 B13
BUG_CATALOGUE := ../common/bugs.py
# The packets are pyvsc objects and the coverage is cocotb-coverage's.
NEEDS_VENV    := 1
include ../common/pyuvm.mk

build/rtl/router.f: $(wildcard ../common/rtl/*.sv) ../common/bugs.py ../common/inject.py
	python3 ../common/inject.py --all --out build/rtl

# ── line counts ──────────────────────────────────────────────────────────────
# FILES names another testbench to count beside this one, for example your
# Lab 03 files: make loc FILES="../lab-03-constraints-and-coverage/tb/*.py"

TB_FILES := tb/router_agents.py tb/router_env.py tb/test_router.py
FILES    ?=

.PHONY: loc

## loc — lines and code lines in this lab's testbench, and in FILES if you give it
loc:
	@echo "This lab's pyuvm testbench:"
	@$(PYTHON) $(LAB_DIR)/src/loc.py $(TB_FILES)
	@if [ -n "$(strip $(FILES))" ]; then echo "FILES:"; $(PYTHON) $(LAB_DIR)/src/loc.py $(FILES); fi
