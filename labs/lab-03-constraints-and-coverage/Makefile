# DD105-B Lab 03: Constraints and coverage. README.md says what's here.
#
# Lab 02's plain-cocotb testbench, with constrained-random packets (pyvsc), a
# level tracker, functional coverage (cocotb-coverage) and a check on
# DROP_CNT:
#
#   make venv                  once: the course venv with pyvsc and cocotb-coverage
#   make                       build if needed, then run router_rand_test
#   make cov                   merge every coverage.xml under build/runs and list the bins
#   make check-all             router_rand_test on the golden router, B07 and B08
#   make traps                 the constraint experiments in traps/traps.py (outside the simulator)
#
# `make help` lists every target; labs/common/README.md describes the shared ones.

TOPLEVEL      := router
DUT_F         := build/rtl/router.f
BUILD_DEPS    := build/rtl/router.f
PY_DIRS       := tb
TEST_MODULES  := test_router
TESTS         := router_rand_test router_fill_test router_class_test
# B07 first: make check with no BUG grades it, and the shipped testbench,
# whose random packets never reach a NOROUTE drop at a full output, misses it.
BUG_LIST      := B07 B08
BUG_CATALOGUE := ../common/bugs.py
# The tests are plain cocotb, with no pyuvm and no BaseTest, so a pass doesn't
# need the line BaseTest prints at the end.
BASE_TEST     := 0
# The packets are pyvsc objects and the coverage is cocotb-coverage's, so
# every target that runs the simulator needs the course venv (make venv).
NEEDS_VENV    := 1
include ../common/pyuvm.mk

build/rtl/router.f: $(wildcard ../common/rtl/*.sv) ../common/bugs.py ../common/inject.py
	python3 ../common/inject.py --all --out build/rtl

# ── the constraint experiments ───────────────────────────────────────────────
# traps/traps.py is plain Python with pyvsc, no simulator and no router. Each
# experiment randomizes a small class many times and prints one line.

.PHONY: traps
## traps — the constraint experiments in traps/traps.py, outside the simulator (SEED picks the seed)
traps: | venv-check
	@$(PYTHON_BIN) $(LAB_DIR)/traps/traps.py --seed $(SEED)
