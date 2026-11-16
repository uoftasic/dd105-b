# labs/common/smoke/Makefile
#
# Builds and runs the router's plain SystemVerilog testbenches on Verilator.
# Run it inside the course image.
#
#   make                  tb_smoke.sv on the golden RTL in ../rtl
#   make faulty           tb_smoke.sv on the faulty build, no bug selected
#   make faulty BUG=B07   the same build, with bug B07 switched on at run time
#   make lint             verilator --lint-only -Wall on the golden RTL
#   make clean            remove $(BUILD)
#
# The faulty build is ../rtl with every bug in ../bugs.py compiled in behind
# a run-time switch (see ../inject.py). It is built once; BUG only changes the
# plusarg passed to the simulator.
#
# TB_SRC picks another testbench, and its top module must have the same name
# as its file:
#
#   make TB_SRC=../solutions/tb_directed.sv
#
# BUILD moves everything this makefile writes: make BUILD=/somewhere/else

COMMON  := $(abspath ..)
RTL     := $(COMMON)/rtl
BUILD   ?= build
TB_SRC  ?= tb_smoke.sv
TOP     := $(basename $(notdir $(TB_SRC)))
BUG     ?=
PLUSARGS ?=

FAULTY_RTL := $(BUILD)/faulty-rtl

VERILATOR ?= verilator
# --trace writes VCD. --trace-fst would be smaller, but Verilator 5.050's FST
# writer needs lz4.h and the course image has only the lz4 runtime library,
# so the build fails. vcd2fst (from GTKWave, in the image) converts instead.
VFLAGS    := --binary --timing --timescale 1ns/1ps -Wall --trace -j 2

GOLDEN_SIM := $(BUILD)/$(TOP)-golden/sim
FAULTY_SIM := $(BUILD)/$(TOP)-faulty/sim

.PHONY: all golden faulty lint clean

all: golden

# Each run leaves its waveform as $(BUILD)/<name>.fst.
GOLDEN_WAVE := $(BUILD)/$(TOP)-golden
FAULTY_WAVE := $(BUILD)/$(TOP)-faulty$(if $(BUG),-$(BUG))

golden: $(GOLDEN_SIM)
	$(GOLDEN_SIM) +vcd=$(GOLDEN_WAVE).vcd $(PLUSARGS)
	vcd2fst $(GOLDEN_WAVE).vcd $(GOLDEN_WAVE).fst && rm -f $(GOLDEN_WAVE).vcd

faulty: $(FAULTY_SIM)
	$(FAULTY_SIM) +vcd=$(FAULTY_WAVE).vcd $(if $(BUG),+BUG=$(BUG)) $(PLUSARGS)
	vcd2fst $(FAULTY_WAVE).vcd $(FAULTY_WAVE).fst && rm -f $(FAULTY_WAVE).vcd

$(GOLDEN_SIM): $(wildcard $(RTL)/*.sv) $(RTL)/router.f $(TB_SRC)
	mkdir -p $(BUILD)/$(TOP)-golden
	$(VERILATOR) $(VFLAGS) -Mdir $(BUILD)/$(TOP)-golden -o sim \
	    -F $(RTL)/router.f $(TB_SRC) --top-module $(TOP)

$(FAULTY_RTL)/router.f: $(wildcard $(RTL)/*.sv) $(RTL)/router.f $(COMMON)/bugs.py $(COMMON)/inject.py
	python3 $(COMMON)/inject.py --all --out $(FAULTY_RTL)

$(FAULTY_SIM): $(FAULTY_RTL)/router.f $(TB_SRC)
	mkdir -p $(BUILD)/$(TOP)-faulty
	$(VERILATOR) $(VFLAGS) -Mdir $(BUILD)/$(TOP)-faulty -o sim \
	    -F $(FAULTY_RTL)/router.f $(TB_SRC) --top-module $(TOP)

lint:
	$(VERILATOR) --lint-only -Wall -F $(RTL)/router.f --top-module router

clean:
	rm -rf $(BUILD)
