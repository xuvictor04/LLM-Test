"""Unit kinds, and a runtime clock that cannot be compared against the wrong one.

WHY THIS IS NARROW ON PURPOSE. Thirty-two of the survey's 475 defect records are unit mismatches, and a
proposal to catch the whole family with a static checker was rejected during design review for a good
reason: static unit inference over arbitrary Python arithmetic is a type-inference engine with no type
system underneath it, and it is defeated by `n = cfg.FAB_NMAX` on the line above the comparison.

So this module does two different things with two different strengths:

  1. UNIT AS METADATA, for every lever and every reported number. Cheap, always correct, never enforced.
     It makes the unit visible in `docs/04_LEVERS.md`, in the report, and in code review.

  2. UNIT AS A RUNTIME TYPE, for CLOCKS ONLY. This is where the bugs actually were, every time:

       pin_tick counted FLUSHES against a threshold declared in STEPS  -> 16x slow at BATCH_W=16
       the capacity valve's clock counted calls, not steps
       four subsystems' modulo cadences never coincided with a flush step, so they never fired
       `step` advances per WINDOW while the loop body runs per FLUSH

     A clock is one number compared against one threshold. That is a small enough surface to type
     honestly, and `Steps(4000) >= Flushes(250)` raising is the whole mechanism.

Anything else -- bytes per token, bits per byte, fractions -- carries its unit as metadata and is checked
by the known-answer tables in `tests/test_derive.py`, not by the type system.
"""


class UnitError(TypeError):
    """Raised when two different clock kinds meet in one comparison or one sum."""


class Clock:
    """A count of one kind of event. Compares and adds only with its own kind.

    Deliberately NOT an int subclass. `class Steps(int)` would let `Steps(4000) >= 250` succeed silently,
    which is the exact failure this exists to stop -- a threshold that came from somewhere else, in
    somebody else's unit, comparing fine.

    `gates` IS A DECLARED SLOT AND NOT AN OMISSION, which is what this docstring exists to say. A
    period accessor returns a Clock and carries its own DID IT FIRE record on it as a tuple of
    spine.gate.Gate -- decision D14 shipped `ckpt/api.py::save_period` on exactly that convention, and
    it is the ONE producer in the tree that attaches to a Clock (the other five attach to their own
    package record: FAB's Population, MEM's Store and TOK's Vocabulary all name `gates` in their OWN
    `__slots__`, and CAP's Valve and SIG's SigState carry their own `__dict__`; none of the five is a
    Clock subclass and none of them can be reached from this file). It USED TO WORK BY ACCIDENT: this
    class declared `__slots__ = ("n",)`, the six kinds below declared none of their own, and the
    implicit `__dict__` every subclass instance therefore carried was the only reason
    `period.gates = (gate,)` landed anywhere. That is the shape this project refuses everywhere else --
    a mechanism working because of what nobody wrote -- and it had the ordinary tidy-up as its
    trigger: adding `__slots__ = ()` to the six kinds, a plausible edit by anyone who has never read
    D14, turned save_period's last-but-one statement into `AttributeError: 'Windows' object has no
    attribute 'gates'`, measured on a scratch tree.

    SO THE AFFORDANCE IS NAMED AND THE TIDY-UP IS ALREADY DONE: `gates` is declared HERE, once, in the
    class the convention belongs to, and the six kinds carry `__slots__ = ()` so that the edit that
    used to break them is the state they ship in. Two things follow, and both are checked below by
    _verify_gate_channel: a Clock still accepts `.gates`, and a Clock accepts NOTHING ELSE -- the
    implicit `__dict__` is gone, so a value object can no longer be given an undeclared attribute by
    anyone who happens to have one in hand.

    WHAT WENT WITH THE `__dict__`, AND IT IS NOT ONLY THE UNDECLARED ATTRIBUTE. `__slots__ = ()` on
    the six kinds removed the implicit `__weakref__` slot along with the implicit `__dict__`, so a
    Clock IS NO LONGER WEAK-REFERENCEABLE: `weakref.ref(Windows(1))` raised nothing before this
    change and now raises "TypeError: cannot create weak reference to 'Windows' object". NOTHING IN
    THE TREE NEEDS ONE -- the only weakref in src/ is data/api.py::_REPLAY's `weakref.ref(areas,
    ...)`, over an Areas and not a Clock -- so this is recorded rather than repaired, because
    restoring the slot to satisfy no caller is the undeclared affordance this whole docstring is
    about, wearing the other sign. A caller that ever needs one adds `"__weakref__"` to the
    `__slots__` below, which costs one pointer per instance and is a decision somebody makes on
    purpose. _verify_gate_channel does NOT check this: there is nothing to check until something
    depends on it.

    WHAT THIS DOES NOT FIX, said here so it is not discovered: the slot is UNSET on a fresh instance
    and every operation returns a fresh instance, so `period - Windows(1)`, `Windows(period)` and
    `period + Windows(0)` all come back with no gates -- exactly as they did when the carrier was a
    `__dict__`. A reader must use `getattr(clock, "gates", ())` and a caller must not re-wrap a period
    it was handed. Declaring the slot makes the channel legal and findable; it does not make a value
    object carry state through its own arithmetic, and it should not.
    """

    # ("n", "gates"): the count, and the DID IT FIRE channel the docstring above declares. It is on
    # the BASE and not repeated on the six kinds because the convention is the Clock's, not any one
    # kind's -- today only Windows carries a gate, but every period accessor in the tree returns a
    # Clock and any of them may.
    __slots__ = ("n", "gates")
    KIND = "clock"

    def __init__(self, n=0):
        if isinstance(n, Clock):
            if type(n) is not type(self):
                raise UnitError(f"cannot build {type(self).__name__} from {type(n).__name__}")
            n = n.n
        self.n = int(n)

    # -- EVERY NEW KIND IS CHECKED AT THE MOMENT IT IS CREATED -------------------------------------
    def __init_subclass__(cls, **kw):
        """Run the gate-channel check on a new Clock kind as its `class` statement executes.

        THE GUARD USED TO WALK A HAND-WRITTEN LIST, so it stopped covering the tree the moment
        anyone added a kind. `_verify_gate_channel` iterated `CLOCK_KINDS + (Clock,)` -- the six
        names somebody remembered to list -- and a SEVENTH kind written without `__slots__ = ()`
        got the implicit `__dict__` back, accepted any attribute at all, and imported green. That
        is the same edit by the same reader the check exists to catch, one step earlier, and a
        check that silently stops covering new cases is worse than no check because the green
        import is read as evidence.

        A HOOK AND NOT A LONGER LIST: this fires for every subclass of Clock, in any module, at
        any time, and it cannot be forgotten by the person adding the kind because they do not have
        to remember it. See _verify_kind for what is checked and why each arm is refused.
        """
        super().__init_subclass__(**kw)
        _verify_kind(cls)

    # -- construction and display ----------------------------------------------------------------
    def __repr__(self): return f"{type(self).__name__}({self.n})"
    def __str__(self): return f"{self.n} {self.KIND}"
    def __int__(self): return self.n
    # __index__ FEEDS operator.index, WHICH IS range(), slicing, list indexing and hex/oct/bin --
    # AND NOT `%`, WHICH THIS COMMENT CLAIMED UNTIL 2026-09-04. `%` needs __mod__/__rmod__ and
    # nothing here defines them, in either direction and on every revision this file has ever had:
    # `Windows(7) % 3` and `7 % Windows(3)` are both TypeError, as are `//` and `*`. Their absence
    # is the mechanism, not an omission -- a cadence written `step % period` is exactly the
    # cross-kind arithmetic spine/derive.py::flush_period_windows exists to replace with a named
    # conversion, and a reader who believes the modulo works is a reader about to write it.
    def __index__(self): return self.n
    def __hash__(self): return hash((type(self).__name__, self.n))
    def __bool__(self): return self.n != 0

    def _same(self, other, op):
        if type(other) is not type(self):
            raise UnitError(
                f"{op}: {type(self).__name__} against "
                f"{type(other).__name__ if isinstance(other, Clock) else type(other).__name__}"
                f" -- if this conversion is real, name it in spine.derive and call it")
        return other

    # -- arithmetic within one kind --------------------------------------------------------------
    def __add__(self, o): return type(self)(self.n + self._same(o, "+").n)
    def __sub__(self, o): return type(self)(self.n - self._same(o, "-").n)
    def __eq__(self, o):
        # EQUALITY RAISES TOO. The first version returned plain False across kinds while <, <=, > and >=
        # raised, so `Flushes(10) == Steps(10)` was quietly False and `Steps(4000) == 4000` was quietly
        # False -- a mismatch reported as a legitimate answer, in the module whose entire mechanism is
        # that a cross-kind comparison cannot pass silently. An `==` against the wrong unit is the same
        # defect as a `>=` against it, and a cadence written `if clock == period:` is not unusual.
        # NotImplemented is kept ONLY for genuinely unrelated types, so `clock in [some, list]` and
        # dict lookups still behave.
        if isinstance(o, (Clock, int, float, bool)):
            return self._same(o, "==") is not None and o.n == self.n
        return NotImplemented
    def __lt__(self, o): return self.n < self._same(o, "<").n
    def __le__(self, o): return self.n <= self._same(o, "<=").n
    def __gt__(self, o): return self.n > self._same(o, ">").n
    def __ge__(self, o): return self.n >= self._same(o, ">=").n

    # -- the ONE legal way to cross kinds --------------------------------------------------------
    def convert(self, to, per):
        """Cross to another clock kind at an explicit rate. `per` is how many of SELF make one of TO.

        There is no implicit path between kinds. A caller that wants steps from flushes must say
        `Flushes(250).convert(Steps, per=1/batch_w)` -- or, better, call the named function in
        spine.derive that already knows the rate, so the conversion exists in one place with a name.
        """
        if not (isinstance(to, type) and issubclass(to, Clock)):
            raise UnitError(f"convert() target must be a Clock kind, got {to!r}")
        if per <= 0:
            raise UnitError(f"convert() rate must be positive, got {per!r}")
        return to(int(self.n / per))


def _verify_kind(kind):
    """Refuse a Clock kind that cannot carry `.gates`, or that can carry anything, or that is unlisted.

    CALLED FROM Clock.__init_subclass__, so it runs at CLASS CREATION for every kind in this file
    and for any kind added later anywhere else. _verify_gate_channel calls it again over every kind
    that exists at import, so removing the hook would not silently disarm the six.

    FOUR ARMS, EACH ONE A DEFECT SOMEBODY WOULD OTHERWISE SHIP GREEN:

      no `__slots__` of its own   the implicit `__dict__` comes back, `.gates` works again BY
                                  ACCIDENT rather than by the declaration on Clock, and any
                                  undeclared attribute can be hung on a value object.
      `__slots__` that shadows    a kind re-declaring "n" or "gates" gets a SECOND slot descriptor
                                  hiding the base's, which is the case the first refusal's message
                                  has always named ("do not add a __slots__ of its own to a Clock
                                  kind that shadows it") and which nothing detected until now.
      `.gates` unassignable       the D14 channel is gone; ckpt/api.py::save_period's gate is lost
                                  with no error at the producer and no line in the report.
      not in CLOCK_KINDS          the kind exists and the tree cannot name it. CLOCK_KINDS is a
                                  REGISTRY and not a convenience list: spine/wire.py::_known_units
                                  builds the legal wire-unit vocabulary from it, so a kind missing
                                  from it cannot be a wire's unit, and tests/test_ownership.py's
                                  O11 carries the same six names. A kind declared outside this
                                  module cannot be registered at all, which is why the message
                                  says to declare it here: one place, like every other declaration
                                  in the spine.

    The registry arm is SKIPPED while this module is still executing -- CLOCK_KINDS does not exist
    until below the six -- and _verify_gate_channel makes it up at the bottom of the file, so a
    seventh kind declared here and left out of the tuple still fails the import loudly.
    """
    own = kind.__dict__.get("__slots__", None)
    if own is None:
        raise RuntimeError(
            f"spine.units.{kind.__name__} is a Clock kind with no `__slots__` of its own, so its "
            f"instances carry an implicit __dict__ and `.gates` would work by ACCIDENT again -- "
            f"the state this module was in until 2026-09-04, when that omission was the only "
            f"reason ckpt/api.py::save_period's gate attachment landed anywhere. Every kind "
            f"declares `__slots__ = ()`; the channel is declared once, on Clock.")
    own = (own,) if isinstance(own, str) else tuple(own)
    shadow = sorted(set(own) & set(Clock.__slots__))
    if shadow:
        raise RuntimeError(
            f"spine.units.{kind.__name__} declares {shadow} in its own __slots__, which SHADOWS "
            f"the slot of the same name on spine/units.py::Clock. A shadowing slot is a second "
            f"descriptor over a second cell: the base's is still there, still allocated, and no "
            f"longer reachable through this kind. `gates` is the DID IT FIRE channel and `n` is "
            f"the count; both belong to Clock and neither is a kind's to re-declare.")
    probe = kind(1)
    try:
        probe.gates = ()
    except AttributeError:
        raise RuntimeError(
            f"spine.units.{kind.__name__} can no longer carry `.gates`. That attribute is the "
            f"DID IT FIRE channel decision D14 shipped CKPT.save_period on -- it returns a "
            f"units.Windows with `period.gates = (Gate('ckpt.periodic_armed', ...),)` -- and "
            f"without it that gate is lost with no error at the producer and no line in the "
            f"report. Restore 'gates' to spine/units.py::Clock's __slots__.") from None
    if hasattr(probe, "__dict__"):
        raise RuntimeError(
            f"spine.units.{kind.__name__} instances carry a __dict__, so `.gates` is once more an "
            f"ACCIDENT rather than the declared slot on spine/units.py::Clock, and any undeclared "
            f"attribute can be hung on a value object. Give it `__slots__ = ()` -- and if it "
            f"already has one, an ancestor between it and Clock does not.")
    registry = globals().get("CLOCK_KINDS")
    if registry is not None and kind not in registry:
        raise RuntimeError(
            f"spine.units.{kind.__name__} is a Clock kind that is not in CLOCK_KINDS. That tuple "
            f"is the registry, not a convenience list: spine/wire.py::_known_units builds the "
            f"legal set of wire units from it, so a kind absent from it cannot be named as a "
            f"unit by any coupling, and nothing that walks the kinds can see it. Declare the kind "
            f"in spine/units.py beside the other six and add it to CLOCK_KINDS in the same edit; "
            f"a kind declared in another module cannot be registered and must move here.")


class Steps(Clock):
    """Optimizer steps. What the LR schedule's horizon is denominated in, and nothing else."""
    __slots__ = ()
    KIND = "steps"


class Flushes(Clock):
    """Batch flushes. The loop body runs once per flush; `step` advances per WINDOW. These are not the
    same number and treating them as one is the project's single most repeated defect."""
    __slots__ = ()
    KIND = "flushes"


class Windows(Clock):
    """Stream windows. What `step` counts, and what the router selects per."""
    __slots__ = ()
    KIND = "windows"


class Backwards(Clock):
    """Backward passes. What gradient accumulation must count, since ACCUM gating on a window counter
    accumulates nothing -- measured 55 optimizer steps where 13 were due."""
    __slots__ = ()
    KIND = "backward passes"


class Epochs(Clock):
    """Passes over the stream. Never a schedule horizon: EPOCHS setting both run length and the cosine
    horizon means two runs differing only in EPOCHS are two different learning-rate experiments."""
    __slots__ = ()
    KIND = "epochs"


class Selections(Clock):
    """Times an expert was chosen. The utilization clock, distinct from wall-clock age."""
    __slots__ = ()
    KIND = "selections"


# ---- unit METADATA for everything that is not a clock -------------------------------------------
# These are labels. They are printed beside every lever and every Reading, and they are never enforced
# at runtime -- their job is to make a mismatch visible to a reader and to the known-answer tables.
BYTES = "bytes"
TOKENS = "tokens"
BITS_PER_BYTE = "bits/byte"
BYTES_PER_TOKEN = "bytes/token"
FRACTION = "fraction 0..1"
PROBABILITY = "probability"
COUNT = "count"
SLOTS = "slots"
ENTRIES = "entries"
EXPERTS = "experts"
DOMAINS = "domains"
SECONDS = "seconds"
PATH = "path"
NAME = "name"
FLAG = "on/off"

CLOCK_KINDS = (Steps, Flushes, Windows, Backwards, Epochs, Selections)


# ---- the gate channel is CHECKED, not merely declared -------------------------------------------
def _verify_gate_channel():
    """Refuse to import if a Clock can no longer carry its DID IT FIRE record, or can carry anything.

    THIS RUNS AT IMPORT AND IT IS NOT DECORATION. The `.gates` attachment used to work because the
    six kinds above declared no `__slots__` of their own, so every instance carried an implicit
    `__dict__` -- and the ordinary tidy-up that removes it (`__slots__ = ()` on a subclass of a
    slotted class) turned `ckpt/api.py::save_period`'s gate attachment into an AttributeError with
    nothing anywhere saying so. That was a silent break of a DID IT FIRE surface, which is the class
    of defect the whole gate record exists to refuse; a report that loses a gate and prints the rest
    is exactly the "armed, did not fire" that was never measured.

    An import-time check and not a test, for one reason: this file is imported by every package and
    by every tool, so the failure arrives at whoever made the edit, on the next thing they run,
    naming D14 and the producer. A test in tests/** would be the right shape too, and this does not
    replace it -- but tests can be run selectively and an import cannot be skipped.

    IT CHECKS BOTH DIRECTIONS, because the affordance is now a declaration and a declaration has two
    ways to go wrong. Removing `gates` from Clock.__slots__ breaks the producer. Deleting a kind's
    `__slots__ = ()` puts the implicit `__dict__` back, and the channel would then work again by
    accident -- the same undeclared affordance, silently restored, and any attribute at all could be
    hung on a value object. Both are refused here, by name.

    AND IT NO LONGER WALKS A HAND-WRITTEN LIST, WHICH IS THE THIRD WAY IT WENT WRONG. This loop read
    `CLOCK_KINDS + (Clock,)` -- the six names somebody remembered to write down -- so a SEVENTH kind
    added without `__slots__ = ()` escaped both refusals and imported green, with `.gates` working
    by accident on it and any undeclared attribute accepted. Demonstrated on a scratch copy of this
    module before the repair: a seventh kind took `n.anything = 1` and the import stayed silent.
    Two changes close it and they are deliberately not the same mechanism. Clock.__init_subclass__
    checks EVERY new kind as its class statement runs, wherever it is written, so nothing has to be
    remembered; and this function now enumerates `Clock.__subclasses__()` transitively rather than
    the tuple, so it also refuses a kind that exists but was left OUT of CLOCK_KINDS -- the registry
    spine/wire.py::_known_units builds the legal wire-unit vocabulary from, where an unlisted kind
    is invisible rather than wrong. The tuple is checked in the other direction too: an entry in it
    that is not a Clock kind would break `k.KIND` in that same reader.
    """
    probe = Clock(1)
    try:
        probe.gates = ()
    except AttributeError:
        raise RuntimeError(
            "spine.units.Clock can no longer carry `.gates`. That attribute is the DID IT FIRE "
            "channel decision D14 shipped CKPT.save_period on -- it returns a units.Windows with "
            "`period.gates = (Gate('ckpt.periodic_armed', ...),)` -- and without it that gate is "
            "lost with no error at the producer and no line in the report. Restore 'gates' to "
            "spine/units.py::Clock's __slots__.") from None
    if hasattr(probe, "__dict__"):
        raise RuntimeError(
            "spine.units.Clock instances carry a __dict__ again, so `.gates` is once more an "
            "ACCIDENT rather than a declared slot, and any undeclared attribute can be hung on a "
            "value object. Restore `__slots__ = (\"n\", \"gates\")` on Clock itself.")

    for kind in CLOCK_KINDS:
        if not (isinstance(kind, type) and issubclass(kind, Clock) and kind is not Clock):
            raise RuntimeError(
                f"spine.units.CLOCK_KINDS contains {kind!r}, which is not a Clock kind. That tuple "
                f"is read as a registry of kinds -- spine/wire.py::_known_units takes `k.KIND` off "
                f"every entry to build the legal wire-unit vocabulary -- so a non-kind in it is an "
                f"AttributeError in another package's import, arriving nowhere near this file.")

    # EVERY KIND THAT EXISTS, not the six that are listed: the listing is what this arm checks.
    seen, stack = [], [Clock]
    while stack:
        for sub in stack.pop().__subclasses__():
            if sub not in seen:
                seen.append(sub)
                stack.append(sub)
    for kind in seen:
        _verify_kind(kind)


_verify_gate_channel()
