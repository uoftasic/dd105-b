# DD105-B guide example for "Register models in pyuvm": four registers on a
# one-cycle bus (regblk.sv), their register model on pyuvm's classes, an
# adapter and a predictor (test_regblk.py).
#
#   make run TEST=RegMirrorTest                       the mirror, with the predictor
#   make run TEST=RegMirrorTest PLUSARGS=+PREDICT=none
#   make run TEST=RegMirrorTest PLUSARGS=+PREDICT=auto
#   make run TEST=RegPredictTest                      the four kinds of predict()
#   make run TEST=RegQuirksTest
#   make regcheck                                     build the model outside the simulator
#
# guide-examples/README.md lists the runs the page quotes.

TOPLEVEL     := regblk
DUT_SRCS     := regblk.sv
PY_DIRS      := .
TEST_MODULES := test_regblk
TESTS        := RegMirrorTest RegPredictTest RegQuirksTest
REG_MODEL    := test_regblk.py:RegBlk
include ../../labs/common/pyuvm.mk
