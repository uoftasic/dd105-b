# DD105-B: does the grader actually grade? See selftest.py and README.md.
#
#   make              the classifier on recorded runs, and the source audit (a second)
#   make FULL=1       ... and every grader end to end on alu/ (a build, then minutes)
#   make capture      re-record logs/ from real runs, after an image or library change
#   make clean        remove alu/build

PYTHON ?= python3
FULL   ?=

.PHONY: selftest capture clean
selftest:
	@FULL=$(FULL) $(PYTHON) selftest.py

capture:
	@$(PYTHON) selftest.py --capture

clean:
	@$(MAKE) --no-print-directory -C alu clean
