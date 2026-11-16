# DD105-B: the shared cocotb + pyuvm build. Every lab's Makefile names its
# sources and tests and includes this file:
#
#     TOPLEVEL     := router
#     DUT_F        := build/rtl/router.f
#     BUILD_DEPS   := build/rtl/router.f
#     SVA_SRCS     := tb/router_sva.sv tb/router_sva_bind.sv
#     TEST_MODULES := test_router
#     TESTS        := RouterSmokeTest RouterRandTest
#     include ../common/pyuvm.mk
#
# One Verilator build serves every test in the lab. The test, the seed, the
# plusargs and the planted bug are all chosen when you run, so changing them
# never rebuilds:
#
#     make                                   build if needed, run the first test
#     make run TEST=RouterRandTest SEED=3 PLUSARGS=+N=500
#     make run BUG=B03                       the same, with planted bug B03 on
#
# `make help` lists every target and variable; labs/common/README.md has the
# full table. Paths are worked out from this file's location, so it runs from
# a lab folder in the workspace clone (/foss/designs/...) and in a bare
# container alike, with make and the course image.

SHELL := /bin/bash
.DEFAULT_GOAL := all

PYUVM_MK     := $(abspath $(lastword $(MAKEFILE_LIST)))
COMMON       := $(patsubst %/,%,$(dir $(PYUVM_MK)))
REPO_ROOT    := $(abspath $(COMMON)/../..)
LAB_MAKEFILE := $(abspath $(firstword $(MAKEFILE_LIST)))
LAB_DIR      := $(patsubst %/,%,$(dir $(LAB_MAKEFILE)))

# ── what the lab's Makefile sets ─────────────────────────────────────────────
# TOPLEVEL is the module cocotb sees as cocotb.top (dut). DUT_F names Verilator
# file lists (passed with -F, so their paths are relative to the list), for
# example the faulty router's build/rtl/router.f; BUILD_DEPS are extra
# prerequisites of the build, such as the rule that writes that list. SVA_SRCS
# are SystemVerilog files bound into the design (assertions); runs of a lab
# that has them get +verilator+error+limit+$(ERROR_LIMIT). PY_DIRS are the
# folders that hold the lab's Python (added to PYTHONPATH); TEST_MODULES the
# modules cocotb imports tests from; TESTS the test classes in them.
TOPLEVEL      ?=
DUT_F         ?=
DUT_SRCS      ?=
SVA_SRCS      ?=
BUILD_DEPS    ?=
VFLAGS        ?=
PY_DIRS       ?= tb
TEST_MODULES  ?=
TESTS         ?=
BUG_LIST      ?=
BUG_CATALOGUE ?=
HUNT_POOL     ?= $(BUG_LIST)
# If the design prints a line when a bug is on, BUG_CONFIRM is that line with
# {id} for the bug, and the graders then refuse a bug run without it. Off by
# default: the router prints nothing unless the run has +BUG_ECHO.
BUG_CONFIRM   ?=
# REG_MODEL is the register model the graders build before any verdict, as
# <file>:<class> relative to the lab (for example tb/router_ral.py:RouterRegs).
# pyuvm raises AssertionError for a model that is wrong, which a verdict would
# otherwise count as a check that fired.
REG_MODEL     ?=
# BASE_TEST=1: every test derives from dd105b_base.BaseTest, and a test that
# passes without the line BaseTest prints at its end is BROKEN. Lab 01's
# cocotb test and Lab 02's plain-cocotb testbench set it to 0.
BASE_TEST     ?= 1
# NEEDS_VENV=1: the lab imports pyvsc or cocotb-coverage, so it stops with a
# message if the course venv (`make venv`) isn't there.
NEEDS_VENV    ?= 0

# ── what you set when you run ────────────────────────────────────────────────
TEST         ?= $(firstword $(TESTS))
SEED         ?= 1
BUG          ?=
PLUSARGS     ?=
NSEEDS       ?= 10
SEEDS        ?= $(shell seq 1 $(NSEEDS))
RUN_TIMEOUT  ?= 300
VERBOSE      ?=
ERROR_LIMIT  ?= 100000

# ── the course venv: pyvsc and cocotb-coverage ───────────────────────────────
# Created by `make venv`, with --system-site-packages so the image's cocotb
# 2.0.1 and pyuvm 4.0.1 stay the ones in use. It lives in the workspace under
# /foss/designs when that is writable (it then survives a container restart
# and serves every clone), and otherwise in the top of this clone, which
# .gitignore leaves out. The simulator's Python doesn't see an activated venv:
# cocotb starts the interpreter named by PYGPI_PYTHON_BIN, so the runs below
# set it to the venv's python whenever the venv exists.
VENV_REQS    := $(COMMON)/requirements.txt
VENV_DIR     ?= $(shell if [ -d /foss/designs ] && [ -w /foss/designs ]; then echo /foss/designs/.venvs/dd105-b; \
                         else echo $(REPO_ROOT)/.venv; fi)
VENV_PY      := $(VENV_DIR)/bin/python
SYSTEM_PY    ?= /usr/bin/python3
PYTHON_BIN   := $(if $(wildcard $(VENV_PY)),$(VENV_PY),$(SYSTEM_PY))
PYTHON       ?= python3

# ── how the build is done ────────────────────────────────────────────────────
BUILD_DIR ?= $(LAB_DIR)/build
SIM_BUILD := $(BUILD_DIR)/sim_build
SIM       := $(SIM_BUILD)/Vtop
BUILD_LOG := $(BUILD_DIR)/build.log
STAMP     := $(BUILD_DIR)/build.flags
SIM_ENV   := $(BUILD_DIR)/sim.env
JOBS      ?= 2
# TRACE=1 builds with VCD tracing, so `make waves` works. The image's
# Verilator can't build FST (its writer needs lz4.h, which the image lacks),
# so `make waves` converts the VCD with vcd2fst.
TRACE     ?= 1
VERILATOR ?= verilator
# Evaluated only when a build needs it: it starts Python.
COCOTB_MAKEFILES = $(shell $(SYSTEM_PY) -m cocotb_tools.config --makefiles 2>/dev/null)

ifeq ($(SEED),random)
  override SEED := $(shell echo $$((RANDOM * 32768 + RANDOM + 1)))
endif

# ccache lives at the top of the course clone, which is in your workspace
# (/foss/designs), so it survives a container restart.
CCACHE_DIR     := $(REPO_ROOT)/.ccache
CCACHE_MAXSIZE := 1G
export CCACHE_DIR CCACHE_MAXSIZE

abs      = $(foreach f,$(1),$(if $(filter /%,$(f)),$(f),$(LAB_DIR)/$(f)))
comma    := ,
space    := $(subst ,, )

# The files the build compiles, in order: the file lists, the design, then the
# bound assertions. cocotb's Verilator makefile adds --vpi --public-flat-rw
# (every signal reachable from Python, the bound u_sva included) and
# --timescale 1ns/1ps. Assertions are on by default in Verilator 5.050.
VL_FILES := $(call abs,$(DUT_SRCS) $(SVA_SRCS))
# TRACE=1 also passes dd105b_trace.vlt, which leaves packages (and with them
# the variable that says which bug is on) out of the waves.
VL_ARGS  := $(addprefix -F ,$(call abs,$(DUT_F))) $(VFLAGS) \
            $(if $(filter 1,$(TRACE)),--trace $(COMMON)/dd105b_trace.vlt) -Wno-fatal
# These are passed to cocotb's own Verilator makefile, which does the build.
COCOTB_BUILD = $(MAKE) --no-print-directory -f $(COCOTB_MAKEFILES)/Makefile.sim \
               SIM=verilator TOPLEVEL_LANG=verilog COCOTB_TOPLEVEL=$(TOPLEVEL) \
               SIM_BUILD=$(SIM_BUILD) VERILOG_SOURCES="$(VL_FILES)" \
               EXTRA_ARGS="$(VL_ARGS)" BUILD_ARGS="-j $(JOBS)" PYTHON_BIN=$(SYSTEM_PY) \
               $(SIM)

SRC_DIRS := $(sort $(dir $(call abs,$(DUT_F) $(DUT_SRCS) $(SVA_SRCS))))
SRC_DEPS := $(sort $(VL_FILES) $(COMMON)/dd105b_trace.vlt \
              $(wildcard $(foreach d,$(SRC_DIRS),$(d)*.sv $(d)*.svh $(d)*.v $(d)*.vh $(d)*.f)))

# ── how a test is run ────────────────────────────────────────────────────────
# cocotb picks tests with COCOTB_TEST_FILTER, a regular expression searched
# for in each test's full name (module.Class); this one matches TEST exactly.
# pyuvm registers each @pyuvm.test() class under its class name.
PY_PATH  := $(subst $(space),:,$(strip $(call abs,$(PY_DIRS)) $(COMMON)/py))
RUN_NAME ?= $(TEST)-s$(SEED)$(if $(BUG),-$(BUG))
RUN_DIR  ?= $(BUILD_DIR)/runs/$(RUN_NAME)
RUN_PLUSARGS = $(if $(BUG),+BUG=$(BUG)) $(if $(strip $(SVA_SRCS)),+verilator+error+limit+$(ERROR_LIMIT)) $(PLUSARGS)
TEST_MODULES_CSV = $(subst $(space),$(comma),$(strip $(TEST_MODULES)))

# $(call run_sim,<run dir>,<extra plusargs>,<quiet>) runs the simulator once in
# its own folder and leaves run.log, results.xml, exit_status, seconds and cmd
# there. This is the only place a simulation is started; the graders call it
# through `make _run`. It starts the simulator directly, with the environment
# cocotb's makefiles would give it, which saves their 1.5 to 2 s a run. A run
# longer than RUN_TIMEOUT seconds is stopped (exit status 124).
define run_sim
mkdir -p $(1) && cd $(1) && rm -f run.log results.xml exit_status seconds cmd waves.vcd waves.fst && \
. $(SIM_ENV) && \
printf '%s\n' 'COCOTB_TEST_FILTER=(^|\.)$(TEST)$$ COCOTB_RANDOM_SEED=$(SEED) $(SIM) $(strip $(RUN_PLUSARGS) $(2))' > cmd && \
t0=$$(date +%s.%N); \
env PYTHONPATH="$(PY_PATH)$${PYTHONPATH:+:$$PYTHONPATH}" PYGPI_PYTHON_BIN=$(PYTHON_BIN) LIBPYTHON_LOC="$$LIBPYTHON_LOC" \
    COCOTB_TOPLEVEL=$(TOPLEVEL) TOPLEVEL_LANG=verilog COCOTB_TEST_MODULES=$(TEST_MODULES_CSV) \
    COCOTB_TEST_FILTER='(^|\.)$(TEST)$$' COCOTB_RANDOM_SEED=$(SEED) COCOTB_RESULTS_FILE=$$PWD/results.xml \
    COCOTB_TRUST_INERTIAL_WRITES=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  timeout -k 5 $(RUN_TIMEOUT) stdbuf -oL -eL $(SIM) $(RUN_PLUSARGS) $(2) 2>&1 | $(if $(3),cat > run.log,tee run.log); \
rc=$${PIPESTATUS[0]}; t1=$$(date +%s.%N); echo $$rc > exit_status; \
awk "BEGIN{printf \"%.2f\n\", $$t1 - $$t0}" > seconds
endef

RUN_DEPS := $(if $(NOBUILD),,$(SIM))
RULE     := ========================================================================
GRADER    = --makefile $(LAB_MAKEFILE) --build-dir $(BUILD_DIR) \
            --test "$(TEST)" --seed "$(SEED)" --plusargs "$(PLUSARGS)" \
            --bugs "$(BUG_LIST)" --catalogue "$(BUG_CATALOGUE)" --pool "$(HUNT_POOL)" \
            --tb-dirs "$(call abs,$(PY_DIRS))" --timeout $(RUN_TIMEOUT) \
            --bug-confirm "$(BUG_CONFIRM)" --base-test $(BASE_TEST) \
            --reg-model "$(REG_MODEL)" --python-bin $(PYTHON_BIN) $(if $(VERBOSE),--verbose)
VERDICT   = $(PYTHON) $(COMMON)/verdict.py $(RUN_DIR) --base-test $(BASE_TEST) \
            --bug-confirm "$(BUG_CONFIRM)" $(if $(BUG),--bug $(BUG))
SAYFAIL   = { echo ""; echo "  The verdict above is FAIL, so this target exits non-zero and make"; \
              echo "  prints an error line under this one. That is the verdict talking,"; \
              echo "  not a broken Makefile."; exit 1; }

.PHONY: all build run waves tests regress seeds cov check check-all new hunt verdict \
        reveal regcheck venv venv-check clean clean-venv clean-cache help _run FORCE

## all — build if needed, then run TEST (what plain `make` does)
all: run

## build — build the simulator, if a source or a build flag changed
build: $(SIM)
	@echo " $(SIM) is up to date."

$(SIM): $(STAMP) $(BUILD_DEPS) $(SRC_DEPS)
	@if [ -z "$(strip $(TOPLEVEL))" ]; then echo "pyuvm.mk: the lab's Makefile must set TOPLEVEL."; exit 1; fi
	@if [ -z "$(COCOTB_MAKEFILES)" ]; then echo "pyuvm.mk: cocotb-config isn't on PATH. Are you in the course image?"; exit 1; fi
	@echo "$(RULE)"
	@echo " BUILD  $(TOPLEVEL)$(if $(strip $(SVA_SRCS)), with $(words $(SVA_SRCS)) bound file(s))   (Verilator, $(JOBS) jobs)"
	@echo " Full log: $(BUILD_LOG)"
	@echo "$(RULE)"
	@mkdir -p $(BUILD_DIR) $(CCACHE_DIR)
	@rm -f $(SIM) $(SIM_BUILD)/Vtop.mk; t0=$$(date +%s.%N); \
	( cd $(LAB_DIR) && MAKEFLAGS= MAKELEVEL= $(COCOTB_BUILD) ) > $(BUILD_LOG) 2>&1; rc=$$?; \
	t1=$$(date +%s.%N); secs=$$(awk "BEGIN{printf \"%.1f\", $$t1 - $$t0}"); echo $$secs > $(BUILD_DIR)/build.seconds; \
	grep -E '^%(Error|Warning)|: (fatal )?error: ' $(BUILD_LOG) | head -40; \
	if [ $$rc -ne 0 ] || [ ! -x $(SIM) ]; then \
	  echo "$(RULE)"; echo " BUILD FAILED after $$secs s. The last 30 lines of $(BUILD_LOG):"; \
	  echo "$(RULE)"; tail -n 30 $(BUILD_LOG); rm -f $(SIM); exit 1; fi; \
	printf 'LIBPYTHON_LOC=%q\nexport LIBPYTHON_LOC\n' "$$($(SYSTEM_PY) -m cocotb_tools.config --libpython)" > $(SIM_ENV); \
	echo "$(RULE)"; \
	echo " built $(SIM) in $$secs s ($$(du -sh $(SIM_BUILD) | cut -f1) in $(SIM_BUILD))"; \
	echo " ccache: $$(ccache -s 2>/dev/null | grep -m2 -E '^ *(Hits|Misses):' | tr -s ' ' | paste -sd ' ')"; \
	echo "$(RULE)"

$(STAMP): FORCE
	@mkdir -p $(BUILD_DIR)
	@printf '%s\n' '$(subst ','\'',$(strip verilator=$(shell $(VERILATOR) --version 2>/dev/null) top=$(TOPLEVEL) $(VL_ARGS) $(VL_FILES)))' > $@.new; \
	if cmp -s $@.new $@; then rm -f $@.new; else mv -f $@.new $@; fi

venv-check:
	@if [ "$(NEEDS_VENV)" = 1 ] && [ ! -x $(VENV_PY) ]; then \
	  echo "$(RULE)"; echo " This lab needs the course venv (pyvsc and cocotb-coverage), and it isn't there:"; \
	  echo "   $(VENV_DIR)"; echo " Create it once with:  make venv"; echo "$(RULE)"; exit 1; fi

## run — run one test: TEST, SEED, BUG and PLUSARGS pick what runs
run: $(RUN_DEPS) | venv-check
	@$(call run_sim,$(RUN_DIR),,)
	@$(VERDICT)

# the graders' entry point: one quiet run into RUN_DIR, no verdict printed
_run: $(RUN_DEPS) | venv-check
	@$(call run_sim,$(RUN_DIR),$(EXTRA_PLUSARGS),quiet)

## waves — the same run as `make run`, writing waves.fst into the run folder
waves: $(RUN_DEPS) | venv-check
	@if [ "$(TRACE)" != 1 ]; then echo "This build has no tracing (TRACE=$(TRACE)). Build with TRACE=1."; exit 1; fi
	@$(call run_sim,$(RUN_DIR),--trace,)
	@$(VERDICT) || true
	@cd $(RUN_DIR) && mv -f dump.vcd waves.vcd && vcd2fst waves.vcd waves.fst > /dev/null && rm -f waves.vcd
	@echo " waves: $(RUN_DIR)/waves.fst ($$(du -h $(RUN_DIR)/waves.fst | cut -f1))"
	@echo " open them with:  surfer $(RUN_DIR)/waves.fst   (or gtkwave)"

## tests — the tests this lab lists in TESTS
tests:
	@echo "Tests in this lab (TESTS in $(LAB_MAKEFILE)):"
	@for t in $(TESTS); do echo "  $$t"; done
	@echo "Run one with:  make run TEST=<test>"

## regress — every test in TESTS on every seed in SEEDS
regress: $(SIM) | venv-check
	@$(PYTHON) $(COMMON)/regress.py $(GRADER) --tests "$(TESTS)" --seeds "$(SEEDS)" --bug "$(BUG)"

## seeds — TEST on every seed in SEEDS (NSEEDS=10: seeds 1 to 10)
seeds: $(SIM) | venv-check
	@$(PYTHON) $(COMMON)/regress.py $(GRADER) --tests "$(TEST)" --seeds "$(SEEDS)" --bug "$(BUG)"

## cov — merge the coverage.xml of every run in build/runs (cocotb-coverage)
cov: | venv-check
	@$(PYTHON_BIN) $(COMMON)/covmerge.py $(BUILD_DIR)/runs --out $(BUILD_DIR)/coverage

## regcheck — build the register model (REG_MODEL) outside the simulator
regcheck:
	@$(PYTHON) $(COMMON)/regcheck.py --lab-dir $(LAB_DIR) --model "$(REG_MODEL)" \
	  --py-path "$(PY_PATH)" --python-bin $(PYTHON_BIN)

## check — the verdict: your test passes the golden design and fails on BUG
check: | venv-check
	@$(PYTHON) $(COMMON)/check.py $(GRADER) --bug "$(BUG)" || $(SAYFAIL)

## check-all — your test against every bug in BUG_LIST, from one build
check-all: | venv-check
	@$(PYTHON) $(COMMON)/check.py $(GRADER) --all || $(SAYFAIL)

## new — deal a mystery bug from HUNT_POOL. You are not told which one.
new:
	@$(PYTHON) $(COMMON)/hunt.py new $(GRADER) $(if $(BUGPICK),--pick $(BUGPICK))

## hunt — your test against the mystery bug, no grade (VERBOSE=1 shows the log)
hunt: | venv-check
	@$(PYTHON) $(COMMON)/hunt.py hunt $(GRADER)

## verdict — the hunt's grade: pass on the golden design, fail on the mystery bug
verdict: | venv-check
	@$(PYTHON) $(COMMON)/hunt.py verdict $(GRADER) || $(SAYFAIL)

## reveal — give up on the hunt and be told which bug it was
reveal:
	@$(PYTHON) $(COMMON)/hunt.py reveal $(GRADER)

## venv — create the course venv (pyvsc, cocotb-coverage) once; see VENV_DIR
venv:
	@if [ -x $(VENV_PY) ] && $(VENV_PY) -c 'import vsc, cocotb_coverage' 2>/dev/null; then \
	  echo " The course venv is already there: $(VENV_DIR)"; \
	  $(VENV_PY) -m pip list 2>/dev/null | grep -iE '^(pyvsc|cocotb-coverage|cocotb|pyuvm) '; exit 0; fi; \
	echo "$(RULE)"; echo " VENV  $(VENV_DIR)"; echo "   from $(VENV_REQS)"; echo "$(RULE)"; \
	t0=$$(date +%s.%N); \
	mkdir -p $(dir $(VENV_DIR)) && $(SYSTEM_PY) -m venv --system-site-packages $(VENV_DIR) && \
	$(VENV_PY) -m pip install --disable-pip-version-check --no-input -q -r $(VENV_REQS) || \
	  { echo " pip failed; nothing is installed. Is the network up?"; rm -rf $(VENV_DIR); exit 1; }; \
	t1=$$(date +%s.%N); \
	$(VENV_PY) -c 'import vsc, cocotb_coverage, cocotb, pyuvm; print(" imports: vsc, cocotb_coverage, cocotb", cocotb.__version__, "pyuvm", pyuvm.__version__)' && \
	echo " created in $$(awk "BEGIN{printf \"%.1f\", $$t1 - $$t0}") s, $$(du -sh $(VENV_DIR) | cut -f1)" && \
	$(VENV_PY) -m pip list 2>/dev/null | grep -iE '^(pyvsc|cocotb-coverage|cocotb|pyuvm) '

## clean — remove build/ (the simulator, the runs, the waves); keeps the ccache and the venv
clean:
	rm -rf $(BUILD_DIR)
	@echo " removed $(BUILD_DIR). The ccache ($(CCACHE_DIR)) and the venv are kept."

## clean-venv — remove the course venv; `make venv` makes it again
clean-venv:
	rm -rf $(VENV_DIR)

## clean-cache — remove the ccache too; the next build is a cold one
clean-cache:
	rm -rf $(CCACHE_DIR)

## help — this list
help:
	@echo "Targets:"
	@grep -hE '^## ' $(LAB_MAKEFILE) $(PYUVM_MK) | sed 's/^## /  make /'
	@echo ""
	@echo "Variables (now):"
	@echo "  TEST=$(TEST)  SEED=$(SEED)  BUG=$(BUG)  PLUSARGS=$(PLUSARGS)"
	@echo "  SEEDS=$(strip $(SEEDS))  RUN_TIMEOUT=$(RUN_TIMEOUT)  ERROR_LIMIT=$(ERROR_LIMIT)"
	@echo "  JOBS=$(JOBS)  TRACE=$(TRACE)  BUILD_DIR=$(BUILD_DIR)"
	@echo "  VENV_DIR=$(VENV_DIR)  ($(if $(wildcard $(VENV_PY)),present,not created))"
	@echo "  PYTHON_BIN=$(PYTHON_BIN)   (the simulator's Python)"

FORCE:
