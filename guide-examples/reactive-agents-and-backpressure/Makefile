# DD105-B guide example for "Reactive agents and backpressure": beat_src.sv
# decides when each beat appears, and the sink agent in test_sink.py takes
# them, either by flipping a coin every cycle or by answering each beat with
# an item from its sequence. SinkTest prints how long 2,000 beats waited.
#
#   make run PLUSARGS="+MODE=coin +READY_PCT=5"
#   make run PLUSARGS="+MODE=beat +MAX_DELAY=12"
#   make run PLUSARGS="+MODE=beat +MAX_DELAY=12 +ITEM=vsc"      pyvsc's solver
#   make run PLUSARGS="+MODE=beat +NOSEQ"                       no sequence on the sink
#
# guide-examples/README.md lists the runs the page quotes.

TOPLEVEL     := beat_src
DUT_SRCS     := beat_src.sv
PY_DIRS      := .
TEST_MODULES := test_sink
TESTS        := SinkTest
# +ITEM=vsc imports pyvsc, from the course venv (make venv).
NEEDS_VENV   := 1
include ../../labs/common/pyuvm.mk
