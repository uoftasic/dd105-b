# DD105-B guide example: what pyuvm 4.0.1's register layer does, for
# docs/reference/pyuvm-register-api.md. guide-examples/README.md lists the
# commands behind every output the page quotes.
#
#   make run TEST=RegPolicyTest       predict() on every access policy, and what
#                                     configure(), add_reg() and the classes accept
#   make run TEST=RegOpsTest          read() and write() through the map, on the router
#   make run TEST=RegTwoOpsTest       two operations on one register at once
#   make run TEST=RegBackdoorTest     the back door and the user front door
#   make run TEST=RegAutoPredictTest  pyuvm's auto-predict switch, turned on
#   make run TEST=RegAddrTest         register addresses as strings
#
# The bus side is labs/ref's APB agent, register model and adapter, none of
# which needs the course venv. Every line the tests print starts with REGAPI.

TOPLEVEL      := router
DUT_F         := build/rtl/router.f
BUILD_DEPS    := build/rtl/router.f
PY_DIRS       := tb ../../labs/ref/tb
TEST_MODULES  := test_regapi
TESTS         := RegPolicyTest RegOpsTest RegTwoOpsTest RegBackdoorTest RegAutoPredictTest \
                 RegAddrTest
BUG_CATALOGUE := ../../labs/common/bugs.py
include ../../labs/common/pyuvm.mk

build/rtl/router.f: $(wildcard ../../labs/common/rtl/*.sv) ../../labs/common/bugs.py ../../labs/common/inject.py
	python3 ../../labs/common/inject.py --all --out build/rtl
