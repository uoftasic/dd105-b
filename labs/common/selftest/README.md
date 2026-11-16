# `selftest/`: checking the graders

```bash
cd labs/common/selftest
make              # the classifier on recorded runs, and the source audit. About a second.
make FULL=1       # ... and every grader end to end on alu/. One build, then about 30 s.
make capture      # re-record logs/ from real runs (after an image, cocotb or pyuvm change)
```

DD104's rule applies here too: a grader that says PASS when it did nothing is worse than no grader.
DD104 shipped one, and it told a student `3 of 3 ALU bugs caught` about a testbench that raised
`NameError` on every core.

A pyuvm run can go wrong without failing its test, in ways a plain cocotb test can't. `self.logger.error()` fails nothing,
so a scoreboard can log a thousand mismatches in a test that passes; pyuvm raises `AssertionError`
for a register model that is wrong, which reads exactly like a check; and Verilator stops a run at
its first failed assertion unless the error limit is raised. `../verdict.py` is the one place that
tells a check that fired from a run that broke, and `../dd105b_base.py`'s `BaseTest` is what turns a
logged error into a failing test. This folder checks that both still work.

## Files

| Path | What it is |
|---|---|
| `selftest.py` | the three parts below, and `--capture` |
| `alu/` | DD105-A's selftest ALU, with three planted bugs behind `+BUG=`, built with `../pyuvm.mk`. Not course material. |
| `alu/rtl/st_alu.sv` | the ALU, with `st_bug_pkg::bug_id` set the way the router's faulty build sets its own, and a `DD105-BUG: <id> enabled` line that `alu/Makefile` checks through `BUG_CONFIRM` |
| `alu/tb/st_sva.sv` | an assertion bound to the ALU, with its counter `n_fail`; the only check on the zero flag, so bug B02 can only be caught by an assertion |
| `alu/tb/test_st.py` | the environment and the fixture tests; each test's docstring names the verdict it must provoke |
| `alu/tb/st_regs.py` | three register models for `regcheck.py`: one whose fields overlap, one with a register at `"0x00"`, and one that builds |
| `alu/tb/test_broken.py` | a test module that doesn't import |
| `alu/cheat/test_cheat.py` | a test that reads `+BUG` and `st_bug_pkg.bug_id`; never run |
| `alu/broken/st_syntax_error.sv` | a file that does not compile |
| `logs/<scenario>/` | `run.log`, `results.xml` and `exit_status` from a real run of each scenario, recorded in `asic-edu/gui-rig:2026.08` |

## The fixtures

| Fixture | Broken how | On the golden design | On a bug |
|---|---|---|---|
| `StGoodTest` | not broken: the reference | ok | B01 caught (a logged MISMATCH), B02 caught (the assertion), B03 MISSED |
| `StEmptyTest` | sends nothing | ok | MISSED |
| `StFixedTest` | sends `ADD 01 02` three hundred times | ok | MISSED |
| `StPlainTest` | derives from `uvm_test`, not `BaseTest`; logs MISMATCH and passes | BROKEN (no BaseTest line) | BROKEN, though the scoreboard logged the bug |
| `StAssertTest` | checks with a plain `assert` in the scoreboard | ok | caught (`AssertionError`) |
| `StCrashTest` | `NameError` while reporting a mismatch | ok | BROKEN |
| `StFatalCheckTest` | reports a mismatch with `UVMFatalError` | ok | BROKEN |
| `StConfigTest` | asks `ConfigDB` for a name nobody set | BROKEN (`UVMConfigItemNotFound`) | |
| `StHangTest` | waits for an event that never comes | BROKEN (`RUN_TIMEOUT`) | |
| `StWatchdogTest` | the same hang under `@pyuvm.test(timeout_time=2, timeout_unit="us")` | FAIL (`SimTimeoutError` is a check) | |
| `StNoSuperTest` | overrides the two phases that install the error counter, without `super()` | BROKEN (`BaseTestNotSetUp`) | |
| `StFinalNoSuperTest` | overrides `final_phase` without `super()` | | BROKEN (no BaseTest line), though errors were logged |
| `StRegModelTest` | builds a register model whose fields overlap | FAIL from `verdict.py` alone; `check.py` refuses it before any run | |
| `NoSuchTest` | a `TEST` that doesn't exist | BROKEN (every test skipped, exit status 0) | |
| `TEST_MODULES=test_broken` | a test module that doesn't import | BROKEN (no `results.xml`) | |
| `StGoodTest` with `ERROR_LIMIT=1` | Verilator's error limit left at 1 | | B02 caught, with a note that the run stopped there |
| `StCheatTest` | reads `+BUG` and `st_bug_pkg.bug_id` | refused before anything is built | |
| `broken/st_syntax_error.sv` | does not compile | BROKEN (the build) | |

## The three parts

The script prints them in the order 1, 3, 2, fastest first.

1. **The classifier, on real runs.** Each scenario's recorded log and `results.xml` go through
   `verdict.py` and have to land in the class the table in `selftest.py` gives them: pass, caught
   or BROKEN, and the reason. Two cases read a real run the wrong way round (a golden run graded as
   a bug run, and a bug run graded as golden) to prove `BUG_CONFIRM` is enforced when a lab sets it,
   and a third reads the golden run as a bug run without `BUG_CONFIRM`, as the router's labs do. No
   simulator; under a second.
2. **The graders, end to end** (`FULL=1`). Builds `alu/` once, then runs `make check`, `check-all`,
   `regcheck`, `new`, `hunt`, `verdict`, `reveal`, `regress`, `seeds` and `waves` with the fixtures,
   and checks what each prints and its exit status. It checks that the waves hold the design and
   its assertion and no package variable, so `st_bug_pkg.bug_id` stays out of them. If the course
   venv exists, `make regress` must also print the merged coverage.
3. **The source audit.** `check.py`, `hunt.py` and `regress.py` must import `verdict.py` and must
   not read `results.xml`, the log or the exit status themselves.

`make capture` reruns every scenario and rewrites `logs/`. Read the diff before committing it: a
changed log is how a new image, cocotb or pyuvm version shows up here first.
