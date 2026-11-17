# The factory and ConfigDB

This page answers: *how does a test change what the environment builds, and how it's set up,
without editing the environment?*

pyuvm gives a test two ways to do it, the factory and `ConfigDB`, and
[Lab 04](../labs/lab-04-the-same-testbench-in-pyuvm-overview.md) has you use both. In Part 2 you
make a second copy of the output agent, and `ConfigDB` tells each copy which output it's on. In
Part 3 you write a stall test that changes a knob that the output drivers read, one output at a
time. In Part 4 you write a test that sends packets to disabled routes by telling the factory to make
a different packet class, and the sequence that makes the packets stays as it is. Part 5 then asks
what the extra lines of the pyuvm testbench bought you, and these two mechanisms are most of the
answer.

The example in
[`guide-examples/the-factory-and-configdb/`](https://github.com/uoftasic/dd105-b/tree/main/guide-examples/the-factory-and-configdb)
imports the files of the [monitors page](monitors-analysis-ports-and-scoreboards.md) example
unchanged, so it has that example's environment: an agent that drives SimProc's ALU, and a monitor
that feeds a scoreboard, a coverage collector and a history. Each of the example's tests changes what
that environment does without editing a line of it.

## The factory

pyuvm registers every class that derives from one of its own with the factory, under the class's
name, as soon as Python defines the class. The labs make almost everything by asking the factory for
it, as the example's sequence does for each vector:

```python
req = AluItem.create("req")
```

With no override set, that returns an `AluItem`, as the constructor would. But a test can tell the
factory to return a subclass of `AluItem` to all the code that asks for an `AluItem`, and that code
doesn't have to change.

`FacEqualTest` uses an override to give every vector equal operands. The override substitutes
`AluEqualItem`, a subclass of `AluItem` that replaces one of `AluItem`'s constraints:

```python
@vsc.randobj
class AluEqualItem(AluItem):
    @vsc.constraint
    def c_same(self):
        self.same == 1
        with vsc.implies(self.same == 1):
            self.B == self.A
```

`AluItem`'s `c_same` makes `same` 1 in one vector in eight, and makes `B` equal to `A` when it is. A
pyvsc constraint is a method, and a Python method with the same name as one in the parent class
replaces it, so `AluEqualItem` has this `c_same` and not its parent's. Lab 04's `NoroutePkt` replaces
`RouterPkt`'s `c_dst` the same way. The test sets the override in its `build_phase`, before
`super().build_phase()` builds the environment:

```python
def build_phase(self):
    uvm_factory().set_type_override_by_type(AluItem, AluEqualItem)
    super().build_phase()
```

and later, in its `end_of_elaboration_phase`, it prints the factory's overrides with
`uvm_factory().print(0)`:

```text
--- overrides ---

Overrides:
AluItem                  : Type Override: AluEqualItem || 
```

The sequence still calls `AluItem.create("req")` and still randomizes what it gets, so the one
override line in the test gives every one of its 200 vectors `A == B`. The history's first vectors
were `OR A=29 B=29`, `NAND A=e8 B=e8` and `ADD A=5d B=5d`. Run against Lab 01's three ALU bugs, the
test catches none of them:

```text
 0 of 3 caught.
 Still hiding from this test:
   A01_sub_operands_swapped
      hides behind: SUB rX, rX, the idiom for clearing a register
   A02_nand_is_nor
      hides behind: NAND rX, rX, the only way to write NOT
   A03_zero_flag_low_nibble
      hides behind: every check that compares results and not flags
```

That's DD104's lesson about equal operands again. With `A == B`, `A - B` and `B - A` are both 0, and
`~(A & B)` and `~(A | B)` are both `~A`, so A01 and A02 give the right answers. The coverage reported
`[COV] alu: 13 of 20 bins hit`, because no vector had unequal operands.

### What the factory doesn't reach

An override changes only the objects that the factory makes. `FacCtorTest` sets the same override and
then makes one item each way:

```text
[CTOR] AluItem.create('x') made AluEqualItem
[CTOR] AluItem('x') made AluItem
```

That's sometimes what you want. Lab 04's `close_holes()` needs its packets exactly as `RouterPkt`
defines them, so it makes them with the constructor, in `new_packet()` and `RouterPkt.make()`, which
the factory never sees. When we made its two random packets with `create()` instead,
`RouterInjectTest`'s override turned them into `NoroutePkt`s too, and `RouterInjectTest` ended `BROKEN: SolveFailure` on 2
of seeds 1 to 20 (Lab 04, Part 4, step 3).

Components go through the factory too, when they're made with `create()`. On the monitors page,
`MonAliasTest` swapped in a different monitor with an override of `AluMonitor`, and `MonConnectTest`
a different environment. Both overrides took effect because `MonAgent` and the test make those
components with `AluMonitor.create()` and `MonEnv.create()`. A component made with its constructor, as Lab 04's agents
make their sequencers with `uvm_sequencer("sqr", self)`, can't be swapped that way.

pyuvm clears every override at the start of each test, so one test's overrides never reach the next.
An override can also apply to a single component, named by its path in the tree, with
`uvm_factory().set_inst_override_by_type(original, override, path)`, but the course's labs use only
type overrides.

### An override from the command line

pyuvm 4.0.1 reads no plusargs of its own, so it can't take an override from the command line the way
SystemVerilog UVM's `+uvm_set_type_override` does. Lab 04's base test reads one of its own,
`+OVERRIDE=<class>,<class>`, and calls `uvm_factory().set_type_override_by_name()` with the two names
before it builds anything, and the example's base test does the same. So it works on `MonRandTest`,
which knows nothing about `AluEqualItem`:

```bash
make run TEST=MonRandTest BUG=A01 PLUSARGS=+OVERRIDE=AluItem,AluEqualItem
```

On the ALU with bug A01 the run logged

```text
     0.00ns INFO     ..-and-scoreboards/mon_env.py(169) [uvm_test_top]: [OVERRIDE] the factory makes AluEqualItem for every AluItem
```

and ended `MISSED: 0 errors`. The same test without the plusarg is `caught: 30 errors`. Changing a
plusarg rebuilds nothing, and Lab 04 uses one the same way on the router in Part 4, step 6.

## ConfigDB

`ConfigDB` is a table of values that one part of the testbench puts in and a component takes out.
The code that sets a value names the components that may read it, by a path in the component tree.
The path is relative to the component that makes the call:

```python
ConfigDB().set(self, "env.sb", "check_flags", True)                  # in the test
self.check_flags = ConfigDB().get(self, "", "check_flags", False)    # in the scoreboard
```

The test's full name is `uvm_test_top`, so its `set()` is for `uvm_test_top.env.sb`. The
scoreboard's `get()` has an empty path, so it looks for a value set for the scoreboard's own full
name, which is also `uvm_test_top.env.sb`. Its last argument, `False`, is the value it returns if
nobody set one.

The example's scoreboard checks only `ALUout` unless `check_flags` is set, and then it checks `N` and
`Z` as well. `FacFlagsTest` sets it, and catches all three bugs:

```text
      ok  the golden design                        0 errors                        2.5s
------------------------------------------------------------------------
  caught  tier 1  A01_sub_operands_swapped         32 errors                       2.5s
  caught  tier 1  A02_nand_is_nor                  18 errors                       2.5s
  caught  tier 1  A03_zero_flag_low_nibble         19 errors                       2.5s
------------------------------------------------------------------------
 3 of 3 caught.
```

A path in a `set()` can hold wildcards. They're globs, as in a shell, and not regular expressions:
`*` matches any run of characters, dots included, so `"env.*"` reaches every component below `env`.
A `get()` names one component, and pyuvm refuses a wildcard in its path. Lab 01's pyuvm test put its
`AluIf` in `ConfigDB` with no component as the context and the path `"*"`, so every component can
find it, and Lab 04's base test does the same with the router's handle, `DUT`.

### When nothing reads the value

`FacTypoTest` makes the same `set()` for `"env.scoreboard"`, and the environment has no component by
that name. The run passed, with no warning, and the scoreboard's `get()` found nothing, so
`check_flags` kept its default of `False` and the test missed A03 (`2 of 3 caught.`). To see what went
wrong, turn on `ConfigDB`'s trace with `ConfigDB().is_tracing = True`, which logs every `set()` and
every `get()` that finds a value. The test does that before its `set()`:

```text
     0.00ns INFO     uvm.logger_holder136667496791984   CFGDB/SET Context: uvm_test_top  --  uvm_test_top.env.scoreboard check_flags=True
[TEST] uvm_test_top set check_flags = True for "env.scoreboard"
     0.00ns INFO     uvm.logger_holder136667496791984   CFGDB/SET Context:   --  * vif=<sq_agent.AluIf object at 0x7c4c61993f50>
     0.00ns INFO     uvm.logger_holder136667496791984   CFGDB/GET Context: uvm_test_top.env.agt.drv  --  uvm_test_top.env.agt.drv vif=<sq_agent.AluIf object at 0x7c4c61993f50>
     0.00ns INFO     uvm.logger_holder136667496791984   CFGDB/GET Context: uvm_test_top.env.agt.mon  --  uvm_test_top.env.agt.mon vif=<sq_agent.AluIf object at 0x7c4c61993f50>
     0.00ns INFO     uvm.logger_holder136667496791984   CFGDB/GET Context:   --   vif=<sq_agent.AluIf object at 0x7c4c61993f50>
```

The `set()` was for `uvm_test_top.env.scoreboard`, and there's no `GET` line for `check_flags` at all,
because the trace leaves out a `get()` that finds nothing. Compare the path in each `SET` line with
the full names of the components that should read it. (The last `GET` is a sequence's, which has no
place in the tree.)

A knob with a sensible default can be read the way `check_flags` is, with a default in the `get()`.
A component that can't work without a value should get it with no default, and then a `get()` that
finds nothing raises `UVMConfigItemNotFound` and ends the run. `FacMissingTest` swaps in a scoreboard
that does that, with nothing set:

```text
 BROKEN: UVMConfigItemNotFound   1.89 s   log: build/runs/FacMissingTest-s1/run.log
   FacMissingTest: UVMConfigItemNotFound: "Component uvm_test_top.env.sb has no key: check_flags
   ConfigDB().get() asked for a name nobody set. That is configuration,
   not a check.
```

Every driver and monitor in Lab 04 gets the router's handle that way, and the output agent's driver
and monitor get their `OutCfg` that way too, so a missing one stops the run at once.

### When two components set the same value

`FacPrecTest` sets `check_flags` to `True` for `"env.sb"`, and it also overrides the environment with a
subclass, `FalseEnv`, that sets `check_flags` to `False` for its `"sb"` before it builds the
scoreboard. The environment is built after the test, so its `set()` comes second:

```text
[TEST] uvm_test_top set check_flags = True for "env.sb"
[ENV] uvm_test_top.env set check_flags = False for "sb"
```

The scoreboard still checked the flags, and reported `200 vectors checked with N and Z: 0 wrong`.
During the build phase, a `set()` made higher in the component tree wins over one made lower down,
even when the lower one comes later, so the test's `True` beat the environment's `False`. pyuvm
stores each `set()` made during `build_phase` with a precedence of 1000 minus the depth of the
component that made it. That rule lets an environment give its components defaults that any test can
override.

It has a limit, though. `FacGlobTest` is the same test with the test's `set()` for `"env.*"` instead:

```text
[TEST] uvm_test_top set check_flags = True for "env.*"
[ENV] uvm_test_top.env set check_flags = False for "sb"
```

This time the scoreboard reported `200 vectors checked: 0 wrong`, without the flags, and the test
missed A03. pyuvm's `get()` looks first for the most specific path that has the name, here
`uvm_test_top.env.sb` before `uvm_test_top.env.*`, and compares precedences only between sets for
that one path. So a test that wants to override an environment's default has to name the component
at least as exactly as the environment does. After the build phase, every `set()` has the same
precedence, and a later one for the same path replaces an earlier one.

### Objects by handle

`ConfigDB` can hold an object as well as a number. It stores the object itself, so the component
that gets the value and the one that set it share one object. Lab 04 uses that for the output agents.
`RouterLabTest` makes an `OutCfg` for each output, sets output 0's for `"env.out0*"` and output 1's
for `"env.out1*"`, and keeps the two handles:

```python
self.ocfg = [OutCfg(0), OutCfg(1)]
for p in (0, 1):
    ConfigDB().set(self, f"env.out{p}*", "cfg", self.ocfg[p])
```

Both output agents are the same class, `OutAgent`. Each one's driver and monitor get the `OutCfg`
from `ConfigDB` because their full names match the path it was set for, and its `port` says which
pins to use. Nothing else differs between the two. Because the test kept the handles, your Part 3
stall test can change `self.ocfg[p].ready_pct` in the middle of a run. Each `OutReadyDriver` reads
`ready_pct` again after every rising edge, so it follows the change at the next one.

## Check yourself

1. `FacEqualTest` and `MonRandTest` both derive from `MonBaseTest`, and `FacEqualTest` adds a type
   override. It catches none of the three bugs, and `MonRandTest` catches two of them. Did the
   override change the sequence?

   <details>
   <summary>Answer</summary>

   No. The sequence's code is the same, and it still asks the factory for an `AluItem` and
   randomizes it. The factory hands back an `AluEqualItem` instead, and that class's `c_same` decides
   the operands. Every item the sequence made had `A == B`, which hides A01 and A02, and the
   scoreboard didn't check the flags, so it missed A03 as it does in `MonRandTest`.

   </details>

2. A test sets a knob for its scoreboard, and the run is no different from a run without the
   `set()`. Nothing printed an error. What do you look at?

   <details>
   <summary>Answer</summary>

   Turn on the trace with `ConfigDB().is_tracing = True` and compare the path in the `CFGDB/SET` line
   with the scoreboard's full name. If there's no `CFGDB/GET` line for the knob, the scoreboard's
   `get()` found nothing, so the `set()` didn't name the component that reads the value, as in
   `FacTypoTest`. If the paths match, look for another `set()` for a more specific path, as in
   `FacGlobTest`.

   </details>

3. Lab 04's `close_holes()` makes its two random packets with the constructor. What happened in
   `RouterInjectTest` when they were made with `create()` instead?

   <details>
   <summary>Answer</summary>

   The test's override reached them too, so the packet for DST 0 was a `NoroutePkt`. Whenever its
   `pre_randomize()` decided on a disabled route, its `c_dst` asked for one, while the inline
   constraint asked for DST 0, the one enabled route. The solver found no solution, and the run ended
   `BROKEN: SolveFailure`, on seeds 11 and 15 of seeds 1 to 20 (Lab 04's solutions README).

   </details>

## Further reading

pyuvm's factory and `ConfigDB` are in its source at 4.0.1,
[`s08_factory_classes.py`](https://github.com/pyuvm/pyuvm/blob/4.0.1/pyuvm/s08_factory_classes.py)
and the end of
[`s13_uvm_component.py`](https://github.com/pyuvm/pyuvm/blob/4.0.1/pyuvm/s13_uvm_component.py),
whose comments say why `ConfigDB` uses globs. ChipVerify's pages are SystemVerilog UVM:

- [UVM Factory Override](https://www.chipverify.com/uvm/uvm-factory-override) covers type and
  instance overrides, and the difference in argument order between the factory's methods and the
  component's. pyuvm has only the factory's, called on `uvm_factory()`. Its last example calls
  methods on a variable named `factory` that it never declares there.
- [UVM config database](https://www.chipverify.com/uvm/uvm-config-db), for the API, the wildcards
  and the precedence rules. Its `get()` returns 0 when it finds nothing; pyuvm's raises
  `UVMConfigItemNotFound` unless you give it a default. Its precedence rules leave out pyuvm's first
  step, the most specific path, which `FacGlobTest` shows.
- [Configure Components](https://www.chipverify.com/uvm/configure-components), on configuration
  objects like Lab 04's `OutCfg`.

Next: [Lab 04: The same testbench in pyuvm](../labs/lab-04-the-same-testbench-in-pyuvm-overview.md).
