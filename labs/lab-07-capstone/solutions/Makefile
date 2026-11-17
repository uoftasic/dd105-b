# DD105-B Lab 07: the reference solution. README.md says what's here.
#
# It builds the lab's testbench with the two files you edit in the lab
# replaced by the finished ones in tb/; every other file comes from the lab
# folder above. Run it from this folder:
#
#   make                         build if needed, run RouterTest
#   make regress                 all 12 tests on seeds 1 to 10, then the coverage
#   make check-all               RouterTest against every planted bug
#   make clean

TOPLEVEL      := router
DUT_F         := build/rtl/router.f
BUILD_DEPS    := build/rtl/router.f
SVA_SRCS      := tb/router_sva.sv ../tb/router_sva_bind.sv
# tb/ comes first, so its router_vseq.py is the one the tests import.
PY_DIRS       := tb ../tb
TEST_MODULES  := test_router
TESTS         := RouterTest RouterLab07Test RouterResetTest RouterSaturateTest RouterLab06Test \
                 RouterLab05Test RouterSinkTest RouterInjectTest RouterStallTest RouterRandTest \
                 RouterFillTest RouterClassTest
BUG_LIST      := B15 B01 B02 B03 B04 B05 B06 B07 B08 B09 B10 B11 B12 B13 B14
BUG_CATALOGUE := ../../common/bugs.py
REG_MODEL     := ../tb/router_ral.py:RouterRegs
NEEDS_VENV    := 1
include ../../common/pyuvm.mk

build/rtl/router.f: $(wildcard ../../common/rtl/*.sv) ../../common/bugs.py ../../common/inject.py
	python3 ../../common/inject.py --all --out build/rtl
