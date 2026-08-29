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
    """

    __slots__ = ("n",)
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
    KIND = "steps"


class Flushes(Clock):
    """Batch flushes. The loop body runs once per flush; `step` advances per WINDOW. These are not the
    same number and treating them as one is the project's single most repeated defect."""
    KIND = "flushes"


class Windows(Clock):
    """Stream windows. What `step` counts, and what the router selects per."""
    KIND = "windows"


class Backwards(Clock):
    """Backward passes. What gradient accumulation must count, since ACCUM gating on a window counter
    accumulates nothing -- measured 55 optimizer steps where 13 were due."""
    KIND = "backward passes"


class Epochs(Clock):
    """Passes over the stream. Never a schedule horizon: EPOCHS setting both run length and the cosine
    horizon means two runs differing only in EPOCHS are two different learning-rate experiments."""
    KIND = "epochs"


class Selections(Clock):
    """Times an expert was chosen. The utilization clock, distinct from wall-clock age."""
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
