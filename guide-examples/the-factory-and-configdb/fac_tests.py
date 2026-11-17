"""
DD105-B guide example: The factory and ConfigDB.

Every test here builds the monitors example's environment unchanged
(mon_env.py), and changes what it does without editing a line of it.

  FacEqualTest    a type override: every AluItem the factory makes is an
                  AluEqualItem, whose c_same replaces AluItem's
  FacCtorTest     the same override, against create() and the constructor
  FacFlagsTest    ConfigDB: check_flags for env.sb
  FacTypoTest     the same set, for a path where nothing reads it, traced
  FacPrecTest     two sets of check_flags for env.sb, from the test and from
                  the environment
  FacGlobTest     the test sets check_flags for env.*, the environment for sb
  FacMissingTest  a scoreboard that can't work without check_flags, and
                  nothing that sets it

AluEqualItem is defined here, so `+OVERRIDE=AluItem,AluEqualItem` works on
the monitors example's MonRandTest, which this folder also runs.
"""

import pyuvm
import vsc
from pyuvm import ConfigDB, uvm_factory

from mon_env import AluScoreboard, MonBaseTest, MonEnv
from sq_agent import AluItem


def say(msg):
    print(msg, flush=True)


@vsc.randobj
class AluEqualItem(AluItem):
    """AluItem with A == B in every vector. A constraint with the same name
    as one in the parent class replaces it."""

    @vsc.constraint
    def c_same(self):
        self.same == 1
        with vsc.implies(self.same == 1):
            self.B == self.A


@pyuvm.test()
class FacEqualTest(MonBaseTest):
    def build_phase(self):
        uvm_factory().set_type_override_by_type(AluItem, AluEqualItem)
        super().build_phase()

    def end_of_elaboration_phase(self):
        super().end_of_elaboration_phase()
        uvm_factory().print(0)


@pyuvm.test()
class FacCtorTest(MonBaseTest):
    def build_phase(self):
        uvm_factory().set_type_override_by_type(AluItem, AluEqualItem)
        super().build_phase()
        say(f"[CTOR] AluItem.create('x') made {type(AluItem.create('x')).__name__}")
        say(f"[CTOR] AluItem('x') made {type(AluItem('x')).__name__}")


class FlagsTest(MonBaseTest):
    PATH = "env.sb"

    def build_phase(self):
        ConfigDB().set(self, self.PATH, "check_flags", True)
        say(f"[TEST] {self.get_full_name()} set check_flags = True for \"{self.PATH}\"")
        super().build_phase()


@pyuvm.test()
class FacFlagsTest(FlagsTest):
    pass


@pyuvm.test()
class FacTypoTest(FlagsTest):
    PATH = "env.scoreboard"

    def build_phase(self):
        ConfigDB().is_tracing = True
        super().build_phase()


class FalseEnv(MonEnv):
    """Sets check_flags to False for its scoreboard before it builds it."""

    PATH = "sb"

    def build_phase(self):
        ConfigDB().set(self, self.PATH, "check_flags", False)
        say(f"[ENV] {self.get_full_name()} set check_flags = False for \"{self.PATH}\"")
        super().build_phase()


@pyuvm.test()
class FacPrecTest(FlagsTest):
    def build_phase(self):
        uvm_factory().set_type_override_by_type(MonEnv, FalseEnv)
        super().build_phase()


@pyuvm.test()
class FacGlobTest(FacPrecTest):
    PATH = "env.*"


class StrictScoreboard(AluScoreboard):
    """Can't work without check_flags, so it gets it with no default."""

    def build_phase(self):
        super().build_phase()
        self.check_flags = ConfigDB().get(self, "", "check_flags")


@pyuvm.test()
class FacMissingTest(MonBaseTest):
    def build_phase(self):
        uvm_factory().set_type_override_by_type(AluScoreboard, StrictScoreboard)
        super().build_phase()
