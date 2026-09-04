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

    # -- construction and display ----------------------------------------------------------------
    def __repr__(self): return f"{type(self).__name__}({self.n})"
    def __str__(self): return f"{self.n} {self.KIND}"
    def __int__(self): return self.n
    def __index__(self): return self.n            # so range(), slicing and % work
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
    """
    for kind in CLOCK_KINDS + (Clock,):
        probe = kind(1)
        try:
            probe.gates = ()
        except AttributeError:
            raise RuntimeError(
                f"spine.units.{kind.__name__} can no longer carry `.gates`. That attribute is the "
                f"DID IT FIRE channel decision D14 shipped CKPT.save_period on -- it returns a "
                f"units.Windows with `period.gates = (Gate('ckpt.periodic_armed', ...),)` -- and "
                f"without it that gate is lost with no error at the producer and no line in the "
                f"report. Restore 'gates' to spine/units.py::Clock's __slots__; do not add a "
                f"__slots__ of its own to a Clock kind that shadows it.") from None
        if hasattr(probe, "__dict__"):
            raise RuntimeError(
                f"spine.units.{kind.__name__} instances carry a __dict__ again, so `.gates` is once "
                f"more an ACCIDENT rather than the declared slot on spine/units.py::Clock, and any "
                f"undeclared attribute can be hung on a value object. This is the state the tree "
                f"was in until 2026-09-04, when the omission was the only reason CKPT.save_period "
                f"worked. Give every kind in CLOCK_KINDS `__slots__ = ()` back.")


_verify_gate_channel()
