# DD105-B guide example for "Virtual sequences": a four-beat FIFO
# (fifo4.sv), a source agent, a sink steered by a knob, and DemoVseq, which
# is given the environment and steers both.
#
#   make run                              DemoVseq's three steps
#   make run PLUSARGS=+SERIAL             step 1 with the release after the send
#   make run TEST=VseqItemTest            a virtual sequence that calls start_item()
#
# guide-examples/README.md lists the runs the page quotes.

TOPLEVEL     := fifo4
DUT_SRCS     := fifo4.sv
PY_DIRS      := .
TEST_MODULES := test_vseq
TESTS        := VseqTest VseqItemTest
include ../../labs/common/pyuvm.mk
