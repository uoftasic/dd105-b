# DD105-B guide example: From cocotb tests to pyuvm components.
#
# The design is Lab 01's ALU, with its +BUG switch. Every test here is a
# pyuvm test in components_demo.py; guide-examples/README.md lists the
# commands whose output the page quotes.
#
#   make build
#   make run TEST=T01Test                   DD104's t01 as one pyuvm test
#   make run TEST=T01Test BUG=A01           ... on the ALU with A01 switched on
#   make run TEST=T01UvmTest BUG=A01        ... derived from uvm_test, not BaseTest
#   make run TEST=PhaseOrderTest            which phase runs on which component, in order
#   make run TEST=NoObjectionTest           a run_phase that never raises an objection
#   make clean

TOPLEVEL      := ALU
DUT_SRCS      := ../../labs/lab-01-one-alu-two-frameworks/rtl/alu.sv
PY_DIRS       := .
TEST_MODULES  := components_demo
TESTS         := T01Test T01UvmTest PhaseOrderTest NoObjectionTest
BUG_LIST      := A01
BUG_CATALOGUE := ../../labs/lab-01-one-alu-two-frameworks/bugs.json
include ../../labs/common/pyuvm.mk
