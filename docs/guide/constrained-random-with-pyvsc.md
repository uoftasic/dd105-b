# Constrained random with pyvsc

This page answers: *how do I get the random stimulus I asked for from pyvsc, and how do I know I
got it?*

Lab 02's generator chose each packet's DST and length itself, with calls to Python's `random`
written into its loop. In [Lab 03](../labs/lab-03-constraints-and-coverage-overview.md) the
generator works on a `RandPacket` instead, a class that pyvsc randomizes. The class declares which
of its fields are random and the rules they must follow, and the generator calls `randomize()`,
which hands those rules to a solver and lets it choose the values. That moves the decisions about
what the stimulus looks like out of the generator's code and into one class, where a test can
change them. It also means that what comes out depends on how the solver chooses among the values
your rules allow, and pyvsc doesn't always choose evenly.

pyvsc 1.1.0 isn't in the course image. It lives in the course venv, which you make with `make venv`
in Lab 03, Part 1, and it brings its own solver, Boolector, with it. This page explains what
`randomize()` does, how pyvsc picks the values, the constraints the labs use, and how seeds work.
The examples are in
[`guide-examples/constrained-random-with-pyvsc/`](https://github.com/uoftasic/dd105-b/tree/main/guide-examples/constrained-random-with-pyvsc).
They're small classes built on SimProc's ALU operations, each randomized inside a pyuvm test that
builds and runs with the course's `pyuvm.mk`, like every lab. You'll run the same kind of
experiment on the router's packet in
[Lab 03, Part 3](../labs/lab-03-constraints-and-coverage-overview.md#part-3-constraints-the-solver-honours).

## randobj, random fields, constraints and randomize()

A pyvsc class is an ordinary Python class with the `@vsc.randobj` decorator. Its random fields are
pyvsc types, such as `vsc.rand_bit_t(8)` for an 8-bit value and `vsc.rand_enum_t(...)` for an enum,
and each method marked `@vsc.constraint` holds rules that the fields must follow. Here is an ALU
vector:

```python
class AluOp(enum.IntEnum):
    ADD = 0
    SUB = 1
    OR = 2
    NAND = 3
    SHL = 4
    SHR = 5


@vsc.randobj
class AluVec:
    def __init__(self):
        self.op = vsc.rand_enum_t(AluOp)
        self.A = vsc.rand_bit_t(8)
        self.B = vsc.rand_bit_t(8)

    @vsc.constraint
    def c_shift(self):
        with vsc.implies(self.op.inside(vsc.rangelist(AluOp.SHL, AluOp.SHR))):
            self.B < 4
```

SimProc's shifts use only `B[1:0]`, so `c_shift` keeps `B` below 4 whenever the operation is a shift,
and leaves it free otherwise. The lines in a constraint method look like Python comparisons, but
pyvsc never evaluates them as `True` or `False`. It runs the method once, the first time the object
is randomized, and records each line as a rule for the solver. A call to `v.randomize()` asks for
values of `op`, `A` and `B` that meet every constraint that is switched on, all at once. A call can
add rules of its own with `randomize_with()`, which apply to that call only, on top of the class's
own:

```python
with v.randomize_with() as it:
    it.op == AluOp.SUB
    it.A == it.B
```

A constraint can be switched off with `v.c_shift.constraint_mode(False)`, and on again with
`True`.

`CrItemTest` randomizes one `AluVec` a few times:

```text
[ITEM] randomize():                         ADD  A=98 B=dd
[ITEM] randomize():                         SHR  A=5c B=03
[ITEM] randomize():                         NAND A=c3 B=b1
[ITEM] randomize():                         SUB  A=98 B=dc
[ITEM] randomize_with(op == SUB, A == B):   SUB  A=8a B=8a
[ITEM] randomize_with(op == SUB, A == B):   SUB  A=61 B=61
[ITEM] before:                              SUB  A=61 B=61
Solve failure: set 'solve_fail_debug=1' for more details
[ITEM] randomize_with(op == SHL, B == 5) raised SolveFailure: solve failure
[ITEM] after:                               SUB  A=b6 B=61
[ITEM] the same with c_shift off:           SHL  A=87 B=05
```

The call with `op == SHL` and `B == 5` can't be met, because `c_shift` says a shift has `B` below 4.
SystemVerilog's `randomize()` returns 0 when that happens, but pyvsc raises an exception,
`SolveFailure`, and prints the `Solve failure` line first. The failed call also changed the object:
`A` went from `61` to `b6`, while `op` and `B` kept their old values. So after the failure the
object held a combination that no call asked for. With `c_shift` switched off, the same call
succeeds.

That's why the labs' code never carries on past a failed `randomize()`. An exception that the test
doesn't catch ends the run, and the course's graders call such a run BROKEN, because a test that
stopped in the middle of its stimulus says nothing about the design. Lab 04's `RouterRandSeq`
catches the failure only to raise a clearer error, one that names the packet's class and the
routing table it was given. Lab 04, Part 4 describes a run that the graders called
`BROKEN: SolveFailure`, and why it failed.

## How pyvsc picks the values

pyvsc's constraints are meant to work as SystemVerilog's do, and Lab 03, Part 3 has you compare
them with the SystemVerilog standard. The standard makes every combination of values that meets the
constraints equally likely. pyvsc's source, `vsc/model/solvegroup_swizzler_partsel.py`, shows that it
chooses another way. For each random field, in
a random order, it picks a random target inside the range of values it has worked out the field can
take. Then it offers the targets to the solver one at a time, in a random order, keeps each one the
constraints still allow, and drops the rest. A field whose target was dropped gets whatever value
the solver finds, and that value isn't random.

You can see the result by counting. `CrSkewTest` randomizes 1,000 vectors with no constraint at
all, and 1,000 with `c_shift`:

```text
[SKEW] no constraint:     ADD 177  SUB 166  OR 172  NAND 159  SHL 165  SHR 161   B < 4 in 18
[SKEW] with c_shift:      ADD 392  SUB 150  OR 168  NAND 179  SHL  50  SHR  61   B < 4 in 119
```

![How often each operation came out in 1,000 randomizations, with no constraint and with c_shift](../assets/img/constrained-random-skew.svg)

*With no constraint, each operation came out about 1,000 / 6 times. With `c_shift`, the shifts came
out about a third as often, and `ADD` more than twice as often.*

Without the constraint, each operation came out close to 1,000 / 6 times, and `B` was below 4 in 18
draws, about the 16 that 4 values in 256 would give. With `c_shift`, a target of `SHL` or `SHR`
survives only if it's offered before `B`'s target, or if `B`'s target happens to be below 4. When
`B`'s target goes first and is 4 or more, the shift is dropped, and the solver puts `ADD` in its
place. So the two shifts came out 50 and 61 times, and `ADD` 392. Every draw met `c_shift`, and
nothing warned. A constraint decides which values can come out, and on this solver you can't rely
on it for how often each one does. The only way to know is to count, which is what Lab 03's
coverage does for the router's packet.

An enum that no constraint mentions came out even, as the first line shows. In DD105-A, Verilator
5.050 gave an enum whose four names fill its two bits its first name 813 times in 1,000 (DD105-A's
measurement), so if you've read that course, this is one thing you needn't work around here.

## Attributes that a constraint reads

A constraint can read attributes that aren't random, and Lab 03's packet does: its `c_dst` reads
`route_en`, the routing table's enable bits, to keep each packet on an enabled route. How you
declare such an attribute matters, because pyvsc reads the constraint methods only once.
`CrAttrTest` uses this class:

```python
@vsc.randobj
class Limited:
    def __init__(self):
        self.A = vsc.rand_bit_t(8)
        self.B = vsc.rand_bit_t(8)
        self.a_max = 4                 # a plain Python attribute
        self.b_max = vsc.uint8_t(4)    # a non-random pyvsc attribute

    @vsc.constraint
    def c_lim(self):
        self.A < self.a_max
        self.B < self.b_max
```

It randomizes the object 200 times, sets both limits to 200, and randomizes it 200 times more:

```text
[ATTR] a_max = 4, b_max = 4, 200 draws:     the largest A 3, the largest B 3
[ATTR] a_max = 200, b_max = 200, 200 draws: the largest A 3, the largest B 199
```

When pyvsc first read `c_lim`, `self.a_max` was the number 4, and it went into the rule as the
number 4, so changing the attribute later changed nothing. `self.b_max` is a pyvsc field, so the
rule refers to the field and reads its value at every call. That's why Lab 03's packet holds
`route_en` and its three length weights in `vsc.uint8_t` attributes: a test changes them between
calls, and the solver sees each change. No error or warning tells you that a plain attribute has
been frozen.

## dist

`vsc.dist()` gives each value or range a weight, and the solver picks among them in proportion to
the weights. `AluVecWeighted` makes `ADD` five times as likely as each other operation:

```python
@vsc.constraint
def c_op(self):
    vsc.dist(self.op, [vsc.weight(AluOp.ADD, 5), vsc.weight(AluOp.SUB, 1),
                       vsc.weight(AluOp.OR, 1), vsc.weight(AluOp.NAND, 1),
                       vsc.weight(AluOp.SHL, 1), vsc.weight(AluOp.SHR, 1)])
```

A `dist` is one more constraint, so a call can add others on the same variable. `CrDistTest` draws
1,000 vectors, then asks for `SUB` 1,000 times with the `dist` still on:

```text
[DIST] op dist ADD 5, others 1:                   ADD 516  SUB  89  OR 103  NAND 100  SHL 104  SHR  88
[DIST] the same, then randomize_with(op == SUB):  failed 0 times in 1000; ADD   0  SUB 1000  OR   0  NAND   0  SHL   0  SHR   0
```

The weights came out right, 5 / 10 of the draws for `ADD`, and asking for `SUB` never failed. pyvsc
tries up to four of the `dist`'s entries as targets, and if none of them fits, it falls back to the
field's whole range. The weights in a `dist` can be enum names, as here, or numbers.

The labs put the `dist` on a selector and choose the other fields from it with `vsc.if_then`. Lab
03's packet has a `kind`, weighted 25 / 50 / 25, and a `length` that `c_len` chooses from the kind.
`VecKind` does the same for `A`, with four kinds weighted 10 / 20 / 30 / 40: `A` is `00`, `ff`,
equal to `B`, or free. Then the test asks for `A < 0x10`, which no `ff` can meet:

```text
[DIST] kind dist 10/20/30/40:                     K_ZERO  89  K_ONES 194  K_SAME 295  K_ANY 422
[DIST] the same, then randomize_with(A < 0x10):   failed 0 times in 1000; K_ZERO 127  K_ONES   0  K_SAME 374  K_ANY 499
```

No call failed, and the other three kinds shared the draws in about the ratio 10 : 30 : 40 of their
weights. In DD105-A, Verilator failed 921 and 199 times in 1,000 on the same two shapes, because it
picks an entry of the `dist` first and solves the rest afterwards (DD105-A's measurements). On pyvsc
you can constrain a packet's length inline whatever its weights, and line 3 of Lab 03's
experiments shows it on the router's packet.

## soft

A soft constraint holds unless something else contradicts it, and then it gives way instead of
failing the call. `SoftVec` makes `B` 1 by default, and has two soft constraints on `A` that
disagree:

```python
@vsc.constraint
def c_b(self):
    vsc.soft(self.B == 1)

@vsc.constraint
def c_a(self):
    vsc.soft(self.A == 0x11)
    vsc.soft(self.A == 0x22)
```

`CrSoftTest` randomizes it 100 times, then 100 times with `B == 7` inline:

```text
[SOFT] randomize(), 100 times:              A=22 B=01 x100
[SOFT] randomize_with(B == 7), 100 times:   failed 0; A=22 B=07 x100
```

The inline constraint beat the soft one without a failure, and of the two soft constraints that
disagreed, the later one won every time. Both are the order that the SystemVerilog standard fixes:
a later soft constraint beats an earlier one, and an inline one beats the class's.

## solve_order

`vsc.solve_order(a, b)` asks for `a` to be chosen before `b`. That changes how often each value of
`a` comes out, without changing which values are legal. `ShiftSel` has a bit, `is_shift`, that
picks between the two shifts and the four other operations, and `ShiftSelOrdered` adds
`vsc.solve_order(self.is_shift, self.op)`:

```text
[SOLVE] solve_order(is_shift, op): is_shift in 509 of 1000;   ADD 251  SUB  60  OR  89  NAND  91  SHL  82  SHR 427
[SOLVE] without solve_order:       is_shift in 412 of 1000;   ADD 224  SUB 105  OR 133  NAND 126  SHL 144  SHR 268
```

By the standard, `is_shift` should come out about 500 times with `solve_order` and about 333 without,
because two of the six operations are shifts. pyvsc gave 509, and 412. So `solve_order` did its job
for `is_shift`, but the operations within each half are far from even, `SHR` 427 against `SHL` 82.
That's the dropped-target effect again. Once `is_shift` is fixed, `op`'s target is still one of
all six operations. When `is_shift` is 1, the four targets that aren't shifts are dropped and the
solver puts `SHR`; when it's 0, the two shift targets are dropped and the solver puts `ADD`. If the
spread of the operations matters to your test, count it.

Lab 03's experiments also try `unique` on a list and a constraint on a list's `sum`, the two that
DD105-A found Verilator gets wrong. Lab 03, Part 4 uses the second, in a `FillPlan` whose eight
lengths add up to 8.

## Seeds

Every run starts Python's `random` from a seed, which `make` passes as `COCOTB_RANDOM_SEED` from
its `SEED` variable (1 unless you set it). cocotb seeds `random` for each test from that seed and
the test's name, so two tests with the same body send different values. A pyvsc object takes its
own random state from Python's `random`, once, at its first `randomize()`. `CrSeedTest` shows when.
Each of its three rows starts from the random state the test started with: the first makes an
object and randomizes it six times, the second calls `random.seed(99)` between making the object and
its first `randomize()`, and the third calls it after the first `randomize()`. On seed 1:

```text
[SEED] make, then randomize() 6 times:          NAND SUB SHL SHL SHL NAND
[SEED] make, random.seed(99), then randomize(): SUB SHL ADD SUB OR OR
[SEED] make, randomize(), random.seed(99), ...: NAND SUB SHL SHL SHL NAND
```

and on seed 2:

```text
[SEED] make, then randomize() 6 times:          SHR SUB SHR SHL OR SHL
[SEED] make, random.seed(99), then randomize(): SUB SHL ADD SUB OR OR
[SEED] make, randomize(), random.seed(99), ...: SHR SUB SHR SHL OR SHL
```

The run's seed decided the first and third rows, and reseeding after the first `randomize()`
changed nothing. Reseeding before it decided the second row, whatever the run's seed. So an object
that the test makes and randomizes repeats with the seed, and you can rerun a failing seed and watch
the same failure happen again. Lab 03's generator makes and randomizes every packet inside the test
for that reason.

A seed reproduces a run only when the testbench draws the same numbers in the same order. Every
random value in the labs comes from Python's `random`, one draw after another: pyvsc's state for
each new packet, the payload bytes, the idle cycles. A change that draws one number more changes
every value after it. That's why Lab 03 says your own constraints may give different counts from
ours with the same seed.

## Speed

pyvsc is slow next to Python's own `random`. `CrSpeedTest` timed 1,000 calls of each kind:

```text
[SPEED] per second: randomize() on one AluVec 536; a new AluVec each time 495; three random.randrange() calls 1036873
```

That's about 1.9 ms a call, against about 1 µs for three `random.randrange()` calls. Importing pyvsc
costs time too. `make import-time` timed `import vsc` in the venv's Python three times:

```text
 import vsc: 1.43 s
 import vsc: 0.99 s
 import vsc: 1.00 s
```

Every run that uses pyvsc pays the import, once. So the labs give the solver only the fields that a constraint
mentions. Lab 03's packet randomizes its DST, its kind and its length with pyvsc, and its
`post_randomize()`, which pyvsc calls after every `randomize()`, fills in the payload bytes and the
idle cycles with `random`. Even so, Lab 03's graded test takes about 5 s, where Lab 02's took
0.25 s.

## Counting what came out

The shifts that came out a third as often as the other operations broke no constraint and printed
no warning, and the test passed. In a testbench with a design in it, the scoreboard wouldn't have
noticed either, because it checks the design's answers and not how often each input was sent. The
tests on this page found it by counting. In Lab 03 you count with coverpoints instead, and their
first run shows a third of the router's packets 1 beat long and a third 8 beats long (263 of 800
each), because the packet's length comes from a three-name enum, `kind`, that nothing weights yet.
[Functional coverage you can read](functional-coverage-you-can-read.md) explains how to read those
counts.

## Check yourself

1. A packet class has a constraint `self.length <= self.max_len`, with `self.max_len = 8` set in
   `__init__`. A test sets `p.max_len = 4` before it randomizes, and still gets 8-beat packets. Why,
   and what do you change?

   <details>
   <summary>Answer</summary>

   `max_len` is a plain Python attribute, so pyvsc read it as the number 8 when it first read the
   constraint, and the rule kept that number. Declare it as a pyvsc field,
   `self.max_len = vsc.uint8_t(8)`, and the solver reads its value at every call, as `b_max` in
   `CrAttrTest` and Lab 03's weights are read.

   </details>

2. A sequence calls `randomize_with()` with an inline constraint that contradicts one of the class's
   constraints, catches the `SolveFailure`, and sends the item anyway. What does the design get?

   <details>
   <summary>Answer</summary>

   An item that no call asked for. The failed call can change some fields and leave others as they
   were, as `A` changed from `61` to `b6` in `CrItemTest` while `op` and `B` didn't. Let the
   exception end the run, or switch the class's constraint off with `constraint_mode(False)` for
   that call.

   </details>

3. Two runs of the same test on seed 3 send different packets. The test makes its packets at the
   start of the test, and you added a component that calls `random.random()` once at time 0. Which
   packets change?

   <details>
   <summary>Answer</summary>

   Every packet whose first `randomize()` comes after that call, and every payload byte and idle
   cycle drawn after it. Each packet takes its random state from Python's `random` at its first
   `randomize()`, so one extra draw before it moves every value after it.

   </details>

## Further reading

pyvsc's own documentation is the authority on its API. ChipVerify's SystemVerilog pages explain the
constructs that pyvsc copies, with longer examples. Their code is SystemVerilog, and their output
comes from commercial simulators, so where pyvsc behaves differently, trust the counts on this page
and in Lab 03.

- pyvsc's [Constraints](https://fvutils.github.io/pyvsc/constraints.html),
  [Methods](https://fvutils.github.io/pyvsc/methods.html) and
  [Data Types](https://fvutils.github.io/pyvsc/data_types.html) pages. The Methods page says that
  an object's random state is made at its first `randomize()` if nothing has set it, as `CrSeedTest`
  shows. It doesn't say what a failed call does; `CrItemTest` shows that.
- ChipVerify's [SystemVerilog Randomization](https://chipverify.com/systemverilog/systemverilog-randomization)
  and [Inline Constraints](https://chipverify.com/systemverilog/systemverilog-inline-constraints).
  Both say that a failed `randomize()` returns 0 and leaves the variables as they were. pyvsc raises
  `SolveFailure` instead, and the failed call in `CrItemTest` changed `A`.
- [Soft Constraints](https://chipverify.com/systemverilog/systemverilog-soft-constraints).
  Correction: it says that when two soft constraints on one variable conflict, which one wins
  depends on the solver. The standard fixes the order, the later one wins, and pyvsc gave the later
  one in all 100 draws of `CrSoftTest`.
- [solve before](https://chipverify.com/systemverilog/systemverilog-solve-before) explains
  correctly what the standard means. pyvsc's `solve_order()` gave 509 in 1,000 for a bit that the
  standard puts at 50%.
- [Disable Constraints](https://chipverify.com/systemverilog/systemverilog-disable-constraints),
  for `constraint_mode()`.

Next: [Functional coverage you can read](functional-coverage-you-can-read.md).
