# DD105-B Lab 02: A layered testbench without pyuvm. README.md says what's here.
#
#   make                                    build if needed, then run router_class_test
#   make run PLUSARGS="+SHOW=5"             the same, logging the first 5 packets on each stream
#   make run BUG=B09 PLUSARGS="+DSTS=0 +LEN=1 +N=16"
#   make check-all                          the golden router, then B05 and B09
#
# `make help` lists every target; labs/common/README.md describes them.

TOPLEVEL      := router
DUT_F         := build/rtl/router.f
BUILD_DEPS    := build/rtl/router.f
PY_DIRS       := tb
TEST_MODULES  := test_router
TESTS         := router_class_test
# B05 first: make check with no BUG grades it, and the shipped testbench,
# whose monitor and scoreboard are empty, misses it.
BUG_LIST      := B05 B09
BUG_CATALOGUE := ../common/bugs.py
# The test is plain cocotb, with no pyuvm and no BaseTest, so a pass doesn't
# need the line BaseTest prints at the end.
BASE_TEST     := 0
include ../common/pyuvm.mk

build/rtl/router.f: $(wildcard ../common/rtl/*.sv) ../common/bugs.py ../common/inject.py
	python3 ../common/inject.py --all --out build/rtl
