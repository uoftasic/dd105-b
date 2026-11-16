# DD105-B: the reference pyuvm environment for the router, written from the
# specification (docs/reference/router-spec.md). README.md says what's here.
#
#   make                       build if needed, run RouterAllTest
#   make run TEST=RouterRandTest SEED=7 PLUSARGS=+N=3000
#   make seeds                 RouterAllTest on seeds 1 to 10
#   make check-all             RouterAllTest against every planted bug

TOPLEVEL      := router
DUT_F         := build/rtl/router.f
BUILD_DEPS    := build/rtl/router.f
SVA_SRCS      := tb/router_sva.sv tb/router_sva_bind.sv
PY_DIRS       := tb
TEST_MODULES  := test_router
TESTS         := RouterAllTest RouterRandTest RouterSmokeTest RouterRegsTest \
                 RouterFullTest RouterOversizeTest RouterIrqTest RouterCtrlTest \
                 RouterResetTest RouterSaturateTest
BUG_CATALOGUE := ../common/bugs.py
REG_MODEL     := tb/router_ral.py:RouterRegs
include ../common/pyuvm.mk

build/rtl/router.f: $(wildcard ../common/rtl/*.sv) ../common/bugs.py ../common/inject.py
	python3 ../common/inject.py --all --out build/rtl
