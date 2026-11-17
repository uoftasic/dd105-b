# DD105-B guide example: Constrained random with pyvsc
# (docs/guide/constrained-random-with-pyvsc.md).
#
# Small pyvsc classes built on SimProc's ALU operations, each randomized many
# times inside a pyuvm test. The ALU is Lab 01's, and it is here only because
# cocotb needs a design to start; nothing drives it. guide-examples/README.md
# lists the commands that made the outputs the page quotes.
#
#   make venv                          once: the course venv (pyvsc)
#   make run TEST=CrItemTest
#   make run TEST=CrSeedTest SEED=2
#   make import-time                   how long `import vsc` takes

TOPLEVEL     := ALU
DUT_SRCS     := ../../labs/lab-01-one-alu-two-frameworks/rtl/alu.sv
PY_DIRS      := .
TEST_MODULES := cr_tests
TESTS        := CrItemTest CrSkewTest CrAttrTest CrDistTest CrSoftTest CrSolveTest \
                CrSeedTest CrSpeedTest
NEEDS_VENV   := 1
include ../../labs/common/pyuvm.mk

.PHONY: import-time
## import-time — the time `import vsc` takes in the venv's Python, three times
import-time: | venv-check
	@for i in 1 2 3; do $(PYTHON_BIN) -c 'import time; t = time.perf_counter(); import vsc; print(f" import vsc: {time.perf_counter() - t:.2f} s")'; done
