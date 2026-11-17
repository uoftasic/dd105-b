# Verification report: the packet router

<!--
  DD105-A Lab 07. Part 4 of the lab copies this file to REPORT.md and fills
  in the hunt table; Part 8 fills in the rest. Every number in it comes from
  a run you did: paste the line the tool printed, not your summary of it.
  Delete these comments when you're done.
-->

Author: _your name_  
Design: the packet router, `labs/common/rtl/`  
Specification: `docs/reference/router-spec.md`  
Plan: [`PLAN.md`](PLAN.md)  
Environment: _the commit of your capstone repository this report describes_  
Date: _date_

## 1. Summary

_Three or four sentences: what you verified, against which plan, and whether it meets the
plan's sign-off criteria. If it doesn't, say which criterion fails._

## 2. The environment

_One table: each component (agents, register model, scoreboard, coverage, assertions,
sequences and tests), one line on what it does, and which file it's in. Mark the parts you wrote
in this lab._

| Component | What it does | File | Yours? |
|---|---|---|---|
| | | | |

## 3. The plan's status

_How many rows the plan has, how many are `done`, and each `gap` with the reason in one line.
Name any rule whose only evidence is a check that has never fired._

## 4. Regression

_The command you ran, how many tests and seeds, the summary line it printed, and how long it
took (wall clock). Then the build time of the simulator it used._

```text
paste the summary line here
```

## 5. Coverage

_The `covergroup` line from the regression, the bins that were hard to reach and what reached
them, and anything coverage doesn't show (rules with "no bin" in the plan)._

```text
paste the covergroup line here
```

Coverage numbers from Verilator 5.050 don't follow the standard's formula (type-level
`get_coverage()` returns 0, `ignore_bins` stay in the denominator, `option.weight` is ignored),
so this report counts bins from `coverage.dat`, whose per-bin counts are right.

## 6. Bugs

### Mystery hunts

_One row per `make new`. Fill in the first three columns from `make hunt` before you run
`make verdict`._

| Deal | The first check that fired (copied) | Your diagnosis: the rule, and the block of the RTL | Verdict: the bug's name | Which sequence made it show |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

### The catalogue

_`make check-all`: the seeds you ran, and the summary line for each. Then the table from one
run, pasted whole._

```text
paste the check-all table here
```

## 7. What this doesn't show

_The limits of the claim in section 1: rules checked only indirectly, behaviour the simulator
can't show (it has two states, so no X), seeds you didn't run, and anything in the plan's Open
items._

## 8. Sign-off

_One sentence that starts "This router..." and keeps going until it's true, and the commands
anyone can run to check it._
