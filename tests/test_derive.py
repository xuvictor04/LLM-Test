"""Known-answer tables for spine.derive, replayed against the frozen oracle.

WHY THIS FILE IS A TABLE AND NOT A SET OF ASSERTIONS SOMEBODY WROTE. Every rule in spine.derive has been
the site of a defect that shipped, and in three of those cases a test existed and passed anyway:

  * `bwt_of` had its subtraction inverted -- on the single line the continual-learning claim rests on --
    and selftest.sh asserted only that the strings "BWT" and "negative = old domains IMPROVED" APPEARED
    IN THE LOG. A test on the words passes whichever way the arithmetic runs.
  * `curve_verdict` shipped four wrong verdicts across five thresholds; the test checked that the
    SECTION APPEARED.
  * `cap_test.py` records the failure mode this whole approach is built against: a RE-TYPED COPY of the
    shipped arithmetic passed happily while the real code was wrong.

So the expected answers here are not written by hand. `.rework/capture_oracle.py` lifted each function's
SOURCE TEXT out of self_organize.py by AST at rm-predict `aee4a52` -- not imported, because importing
self_organize.py runs the whole system, and not re-typed, for the reason above -- exec'd it, and dumped
the answers to `.rework/oracle/*.json` (P0, graft G11). This file replays those tables. A disagreement
means the rebuild changed a decision, and every such change has to be a decision somebody made.

    python3 tests/test_derive.py            # prints per-table case counts, exits non-zero on any miss

JSON ROUND-TRIP: json.load turns every captured tuple into a list, and that matters more than it looks.
Two of the tables were captured with tuple inputs -- `blowup_stale`'s `recent`, and the (mean, err) pair
that `bwt_of` and `forgetting_of` RAISE TypeError on -- and the raised message names the type:
"unsupported operand type(s) for -: 'tuple' and 'tuple'". Replaying with a list produces the same
exception with a different message, so the test would report a message mismatch on code that is correct.
`_as_captured` puts the tuples back before the call.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from spine import derive                                          # noqa: E402
from spine.units import Clock                                     # noqa: E402

ORACLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".rework", "oracle")

# The oracle is keyed by the SHIPPED function name. Only one name moved: `_phases` reached into the
# environment from inside its body for PHASES and PHASE_W, which is the L2 violation the rebuild forbids,
# so it is reborn as a public function whose parameters arrive as arguments. Everything else keeps its
# name AND its argument order -- `pin_tick(held, pinned, dstep)` in particular, whose order is odd enough
# that the capture grid itself passed the boolean and the count in each other's slots.
UNDER_TEST = {
    "cull_gate_open": derive.cull_gate_open,
    "operating_population": None,          # no shipped equivalent: the setpoint was never named, only implied
    "lift_to": derive.lift_to,
    "pin_tick": derive.pin_tick,
    "bwt_of": derive.bwt_of,
    "forgetting_of": derive.forgetting_of,
    "curve_verdict": derive.curve_verdict,
    "blowup_stale": derive.blowup_stale,
    "_phases": derive.phase_schedule,
}


def _as_captured(v):
    """Restore the JSON round-trip: every array was a tuple when the oracle ran. See the module note."""
    if isinstance(v, list):
        return tuple(_as_captured(x) for x in v)
    if isinstance(v, dict):
        return {k: _as_captured(x) for k, x in v.items()}
    return v


def _comparable(v):
    """Normalise a result for comparison against JSON. Tuples and lists are the same shape to json.

    A CLOCK IS UNWRAPPED TO ITS INT, AND THAT IS A HOLE THIS FUNCTION CANNOT AVOID. `pin_tick` returns
    Steps; the oracle captured bare ints, because the shipped function had no units. Left wrapped, the
    comparison would not merely fail -- `Steps(2666) != 2666` RAISES UnitError by design, so the replay
    would die rather than report. Unwrapping makes the 32 cases replay, and it makes this comparison
    blind to kind: a Flushes(2666) would pass here exactly as a Steps(2666) does. Nothing in any captured
    table can cover that, so the unit contract is asserted in smoke() instead, and only there.
    """
    if isinstance(v, Clock):
        return int(v)
    if isinstance(v, (list, tuple)):
        return [_comparable(x) for x in v]
    if isinstance(v, dict):
        return {k: _comparable(x) for k, x in v.items()}
    return v


def _call(fn, args):
    """Run one case the way the capture ran it: the exception is part of the answer, not a failure."""
    try:
        return _comparable(fn(*args))
    except Exception as e:
        # Same shape the capture recorded, INCLUDING the 200-char truncation. The message is compared,
        # not just the type, because `bwt_of`'s TypeError on a (mean, err) tuple is a documented contract
        # honoured by convention at the call site -- if the message changes, the contract moved.
        return {"__raised__": type(e).__name__, "msg": str(e)[:200]}


def replay(name):
    """Replay one oracle table. Returns (cases, misses) and prints every miss with both answers."""
    with open(os.path.join(ORACLE, name + ".json")) as fh:
        blob = json.load(fh)
    fn = UNDER_TEST[blob["function"]]
    misses = 0
    for case in blob["cases"]:
        args = tuple(_as_captured(a) for a in case["in"])
        got, want = _call(fn, args), _comparable(case["out"])
        if got != want:
            misses += 1
            print(f"  MISS {blob['function']}{args}\n       want {want!r}\n       got  {got!r}")
    return len(blob["cases"]), misses


def smoke():
    """Exercise every public function once, including the five with no shipped ancestor to replay.

    These five are new, so there is no table to hold them honest and the assertions here are the only
    thing that does. Each one checks the PROPERTY the function exists to guarantee, not a spot value --
    a spot value would have passed for the one-byte signature width too.
    """
    from fractions import Fraction
    from spine.units import Backwards, Epochs, Flushes, Steps, UnitError, Windows

    # operating_population is the setpoint the cull gate settles at, so the two must agree by
    # construction. This is the assertion that would have caught FAB_N0=2048 vs FAB_NMAX=4096 parking
    # occupancy at 0.50 under a pressure of 0.75 with three mechanisms silently unreachable behind it.
    for slots in (4, 100, 1024, 4096, 8192):
        for p in (0.05, 0.25, 0.45, 0.5, 0.75, 1.0):
            n = derive.operating_population(p, slots)
            assert 3 <= n <= slots, (p, slots, n)
            assert derive.cull_gate_open(n, slots, p), ("gate shut at its own setpoint", p, slots, n)
            if n > 3:
                assert not derive.cull_gate_open(n - 1, slots, p), ("gate open below setpoint", p, slots, n)
    assert derive.operating_population(0.45, 4096) == 1844        # 1843/4096 = 0.4499 is BELOW 0.45
    assert derive.operating_population(0.5, 4096) == 2048         # exact product, no ULP creep upward

    # bytes_per_token is MEASURED. 614 bytes over 256 tokens is 2.4 b/tok, the last run's figure.
    assert derive.bytes_per_token(614, 256) == 614 / 256
    try:
        derive.bytes_per_token(1000, 0); raise AssertionError("zero tokens must raise, not estimate")
    except ValueError:
        pass

    # The one signature width. WIN=256 at 2.4 b/tok is 614 -- the number the training path used while the
    # eval path used ONE. The floor property is the one that matters: it can never be narrower than the
    # loop stride, whatever the compression reads.
    assert derive.signature_width_bytes(256, 2.4) == 614
    assert derive.signature_width_bytes(256, 1.0) == 256
    assert derive.signature_width_bytes(256, 0.1) == 256          # sub-1 b/tok cannot narrow the window
    for win in (1, 64, 256, 1024):
        for bpt in (0.5, 1.0, 1.9, 2.4, 3.9):
            assert derive.signature_width_bytes(win, bpt) >= win

    # flush_period: GROW_CAP_EVERY=20000 steps at BATCH_W=16 is 1250 flushes. The shipped code compared a
    # flush count against 20000 directly, so the valve needed 320,000 real steps to fire.
    assert derive.flush_period(Steps(20000), 16) == Flushes(1250)
    assert derive.flush_period(Steps(20000), 1) == Flushes(20000)
    assert derive.flush_period(Steps(8), 16) == Flushes(1)        # never truncates to a period of zero
    for bad in (20000, Flushes(20000), Windows(20000)):
        try:
            derive.flush_period(bad, 16); raise AssertionError(f"bare/foreign clock accepted: {bad!r}")
        except UnitError:
            pass

    # flush_period_windows: THE SAME DIVISION, THE OTHER KIND, AND THE PAIR IS THE POINT. MANAGE_EVERY
    # and the capacity valve's pin threshold are compared against `step`, and `step` advances once per
    # WINDOW (`i += WIN; step += 1` at self_organize.py:6796 and :7708) -- so spine/assemble.py converts
    # them with this function and not with flush_period. Each function must refuse the other's kind, or
    # there is one function with two meanings again.
    assert derive.flush_period_windows(Windows(2000), 16) == Flushes(125)
    assert derive.flush_period_windows(Windows(20000), 16) == Flushes(1250)
    assert derive.flush_period_windows(Windows(20000), 1) == Flushes(20000)
    assert derive.flush_period_windows(Windows(8), 16) == Flushes(1)   # never a period of zero
    for bad in (20000, Flushes(20000), Steps(20000)):
        try:
            derive.flush_period_windows(bad, 16)
            raise AssertionError(f"bare/foreign clock accepted as a window cadence: {bad!r}")
        except UnitError:
            pass

    # --- units.py::Clock.convert, THE DECLARED PATH BETWEEN KINDS, AND THE TWO CALLERS ABOVE AT THE
    # ONE PLACE THEY DISAGREE WITH THE BODY THEY USED TO HAVE. The method divided in FLOAT until
    # 2026-09-04 -- `to(int(self.n / per))` -- and now divides in fractions.Fraction and truncates
    # once at the end. spine/derive.py::flush_period and spine/derive.py::flush_period_windows are
    # its only two callers in src/, so two of derive's five cross-kind conversions were performing
    # in float the operation spine/derive.py::opt_steps_from_backwards refuses BY NAME in its
    # closing comment ("Integer `//` and not `int(n / k)`: float division loses exactness above
    # 2**53 and a backward count is unbounded") -- and they were performing it BECAUSE they delegate
    # here rather than dividing themselves, which is the one way a module can break its own rule
    # while every line it owns still obeys it.
    #
    # A TABLE OF INPUTS WHERE FLOAT AND EXACT DIVISION AGREE WOULD TEST NOTHING HERE -- the
    # disagreement is the entire reason the body changed -- so every count below is chosen to make
    # them disagree, and the last assertion in the loop re-runs the OLD body to prove the case still
    # discriminates. The expected answers are hand arithmetic on the integers and not a recording of
    # what the function returned.
    #
    # THE MECHANISM, so the five rows read as arithmetic rather than as magic numbers. A float64
    # carries a 53-bit significand, so the representable integers step by 2 above 2**53 and by 4
    # above 2**54; every ODD integer in [2**53, 2**54) therefore sits exactly halfway between two
    # neighbours and float() resolves that tie to the EVEN one -- which is why the error goes DOWN
    # for some counts and UP for others rather than always toward zero.
    #
    #   n = 2**53+1 = 9007199254740993, per = 1
    #       exact 9007199254740993; float(n) ties DOWN to 2**53, so the old body answered
    #       9007199254740992 -- one flush short.
    #   n = 2**53+3 = 9007199254740995, per = 2
    #       9007199254740995 = 2 x 4503599627370497 + 1, so the truncated answer is 4503599627370497;
    #       float(n) ties UP to 9007199254740996 and half of that is 4503599627370498 -- ONE FLUSH
    #       LARGER than the true period. A period that rounds up FIRES LATE, the one direction both
    #       callers' docstrings say they refuse to bias toward. These two rows are the measurements
    #       units.py::Clock.convert quotes for itself.
    #   n = 2**53+7 = 9007199254740999, per = 4
    #       = 4 x 2251799813685249 + 3, so 2251799813685249; float(n) ties UP to 9007199254741000 and
    #       a quarter of that is 2251799813685250. Late again, at a third rate.
    #   n = 2**54+2 = 18014398509481986, per = 1 and per = 2
    #       above 2**54 the step is 4, so float(n) ties DOWN to 2**54 = 18014398509481984: the per=1
    #       answer was TWO short, and the per=2 answer -- 9007199254740993 exactly, no remainder --
    #       was one short. The same count under two rates, so the row is not a property of `per`.
    #
    # NO LIVE CONFIGURATION IS ANYWHERE NEAR THESE MAGNITUDES (the shipped cadences are in the tens
    # of thousands, so no shipped number moved), and that is the standing this file gives every
    # other rule in the spine rather than an argument against the repair: an inline cross-kind
    # division is a defect even when its number is right at the defaults.
    for n, per, want in ((2**53 + 1, 1, 9007199254740993),
                         (2**53 + 3, 2, 4503599627370497),
                         (2**53 + 7, 4, 2251799813685249),
                         (2**54 + 2, 1, 18014398509481986),
                         (2**54 + 2, 2, 9007199254740993)):
        assert type(derive.flush_period(Steps(n), per)) is Flushes, (n, per)
        assert derive.flush_period(Steps(n), per) == Flushes(want), ("flush_period", n, per)
        assert derive.flush_period_windows(Windows(n), per) == Flushes(want), ("fpw", n, per)
        # The old body, re-run. If this ever stops holding, the case has been softened into one
        # float gets right, and the table above would be green while proving nothing.
        assert int(n / per) != want, ("case no longer discriminates float from exact", n, per)

    # convert ITSELF, which nothing in this file had ever called even though units.py calls it "the
    # ONE legal way to cross kinds". The answer wears the TARGET kind, and 20000 / 16 = 1250.
    assert type(Steps(20000).convert(Flushes, per=16)) is Flushes
    assert Steps(20000).convert(Flushes, per=16) == Flushes(1250)
    # TRUNCATES TOWARD ZERO AT BOTH SIGNS, which is what `int()` on a Fraction does and what the
    # method promises ("truncation is preserved at every input, negatives included"). 7/2 = 3.5 -> 3
    # and -7/2 = -3.5 -> -3, where FLOOR would answer -4. Neither caller can reach the negative side
    # -- both floor their result at one flush -- so this is convert's own contract and nothing
    # else's, and it is the half of "exact" that a Fraction changes without changing the rounding.
    assert Steps(7).convert(Flushes, per=2) == Flushes(3)
    assert Steps(-7).convert(Flushes, per=2) == Flushes(-3)
    assert -7 // 2 == -4                       # floor's answer, so the contrast is in the file
    # A RATE BELOW ONE IS THE DOCUMENTED FLUSHES -> STEPS SPELLING (`per=1/batch_w`), and it is why
    # the body cannot be an integer `//`: the divisor is not always an integer. 1/16 is a binary
    # fraction, so the float literal and the exact rational are the SAME number here and both give
    # 250 / (1/16) = 4000.
    assert Flushes(250).convert(Steps, per=Fraction(1, 16)) == Steps(4000)
    assert Flushes(250).convert(Steps, per=1 / 16) == Steps(4000)
    # AND THIS IS WHAT A Fraction CANNOT FIX, which the method says in as many words: a rate that is
    # not a binary fraction is ALREADY inexact when it arrives. The literal 0.2 is exactly
    # 3602879701896397 / 2**54, which is LARGER than one fifth (3602879701896397 x 5 =
    # 18014398509481985, one more than 2**54), so 10 / 0.2 comes to just under 50 and truncates to
    # 49 -- while the rate the caller meant, Fraction(1, 5), gives exactly 50. BOTH are asserted
    # because the repair made the division exact over the rate it was HANDED, not over the rate the
    # caller had in mind, and a test carrying only the second number would claim the wrong thing.
    assert Steps(10).convert(Flushes, per=0.2) == Flushes(49)
    assert Steps(10).convert(Flushes, per=Fraction(1, 5)) == Flushes(50)
    # THE TARGET MUST BE A KIND AND NOT AN INSTANCE OF ONE. `period.convert(Flushes(1), ...)` is the
    # plausible slip, and without this arm it would be a TypeError from calling an instance.
    for bad_to in (int, float, None, "Flushes", Flushes(1)):
        try:
            Steps(10).convert(bad_to, per=2)
            raise AssertionError(f"convert accepted {bad_to!r} as a target kind")
        except UnitError:
            pass
    # A RATE OF ZERO OR BELOW, refused before anything divides.
    for bad in (0, -1, -0.5, float("-inf")):
        try:
            Steps(10).convert(Flushes, per=bad)
            raise AssertionError(f"convert accepted a rate of {bad!r}")
        except UnitError as e:
            assert "must be positive" in str(e), (bad, str(e))
    # nan AND inf REACH PAST THAT GUARD, which is the distinction the method draws and which a test
    # asserting only UnitError cannot see: both comparisons below are False, so the exact-value arm
    # is the one that fires, and the old float body answered nan with a ValueError out of int() and
    # inf with a SILENT ZERO -- a period of zero being the armed-and-inert class flush_period floors
    # at one flush to avoid. The message is asserted for the reason bwt_of's is: it is the only
    # thing that says WHICH arm refused.
    assert (float("nan") <= 0) is False and (float("inf") <= 0) is False
    for bad in (float("nan"), float("inf")):
        try:
            Steps(10).convert(Flushes, per=bad)
            raise AssertionError(f"convert accepted a rate of {bad!r}")
        except UnitError as e:
            assert "exact value" in str(e), (bad, str(e))
    # AND A Clock IS NOT A RATE HERE EITHER, though the refusal arrives by a different road than the
    # five named ones in derive: `per <= 0` compares a Clock against an int and units.Clock.__le__
    # raises on a cross-kind comparison, so convert refuses one line before any arm of its own. The
    # road matters because it is the one arm here that no line of convert's body spells out.
    for bad in (Windows(4), Steps(4), Flushes(4)):
        try:
            Steps(10).convert(Flushes, per=bad)
            raise AssertionError(f"convert accepted {bad!r} as a rate")
        except UnitError:
            pass

    # accum_due counts BACKWARD PASSES. At ACCUM=4 exactly a quarter of them are due; the window counter
    # that produced 55 steps where 13 were due cannot even be passed in.
    assert sum(derive.accum_due(Backwards(n), 4) for n in range(1, 53)) == 13
    assert derive.accum_due(Backwards(0), 4) is False
    assert all(derive.accum_due(Backwards(n), 1) for n in range(1, 10))
    for bad in (52, Windows(52), Steps(52)):
        try:
            derive.accum_due(bad, 4); raise AssertionError(f"non-Backwards accepted: {bad!r}")
        except UnitError:
            pass

    # run_windows_from_epochs: EPOCHS x windows-per-epoch, the conversion spine/compose.py's
    # _run_windows wrote inline as `units.Windows(_windows_in_epoch(sysm) * int(...epochs))`. The
    # body is `Windows(n_epochs.n * w)`, so the answers below are one multiplication each: 3 x 10 =
    # 30, 1 x 937 = 937, 0 x 10 = 0, 1 x 1 = 1.
    # NO FLOOR is the property, and it is the ruling opt_steps_from_backwards makes rather than the
    # one opt_steps_from_windows makes: RUN_EPOCHS=0 is refused with a sentence by
    # train/api.py::startup_refusals and deliberately not clamped, so clamping it here would restore
    # that clamp one file away from the refusal and report one epoch's worth of windows for a run
    # configured to make no passes.
    assert derive.run_windows_from_epochs(Epochs(3), 10) == Windows(30)
    assert type(derive.run_windows_from_epochs(Epochs(1), 937)) is Windows
    assert derive.run_windows_from_epochs(Epochs(1), 937) == Windows(937)
    assert derive.run_windows_from_epochs(Epochs(0), 10) == Windows(0)
    assert derive.run_windows_from_epochs(Epochs(1), 1) == Windows(1)
    for bad in (3, Windows(3), Steps(3), Flushes(3), Backwards(3), True, 3.0, None):
        try:
            derive.run_windows_from_epochs(bad, 10)
            raise AssertionError(f"non-Epochs accepted: {bad!r}")
        except UnitError:
            pass
    for bad in (0, -1):
        try:
            derive.run_windows_from_epochs(Epochs(3), bad)
            raise AssertionError(f"rate below 1 accepted: {bad!r}")
        except UnitError:
            pass

    # opt_steps_from_backwards: ONE boundary, so the divisor is accum ALONE, and the body on the
    # accepted domain is `Steps(n // k)`. 52 = 4 x 13 exactly; 62 = 4 x 15 + 2, so 15; 3 = 4 x 0 + 3,
    # so a partial step is not a step; 1000 = 1 x 1000. The last row is the two-boundary divisor the
    # function's own docstring names as the likeliest way to break the accumulation invariant while
    # appearing to repair it: 62 = 64 x 0 + 62, so it reports 0 steps due against the 15 that were
    # taken on fetch_big.py's heavy-run command, and a CORRECT run raises the P3-H29 message.
    assert derive.opt_steps_from_backwards(Backwards(52), 4) == Steps(13)
    assert derive.opt_steps_from_backwards(Backwards(62), 4) == Steps(15)
    assert derive.opt_steps_from_backwards(Backwards(0), 4) == Steps(0)     # no floor at one
    assert derive.opt_steps_from_backwards(Backwards(3), 4) == Steps(0)     # a partial step is not a step
    assert derive.opt_steps_from_backwards(Backwards(1000), 1) == Steps(1000)
    assert derive.opt_steps_from_backwards(Backwards(62), 64) == Steps(0)   # the two-boundary divisor
    for bad in (52, Steps(52), Windows(52), Flushes(52), Epochs(52), True, 52.0, None):
        try:
            derive.opt_steps_from_backwards(bad, 4)
            raise AssertionError(f"non-Backwards accepted: {bad!r}")
        except UnitError:
            pass
    # THE DIVISOR END OF THE SAME FUNCTION: accum below one is REFUSED here where accum_due CLAMPS
    # it, and the two are deliberately different -- see the accum_due assertions below.
    for bad in (0, -1):
        try:
            derive.opt_steps_from_backwards(Backwards(52), bad)
            raise AssertionError(f"accum below 1 accepted: {bad!r}")
        except UnitError:
            pass
    # A NEGATIVE COUNT IS REFUSED AT EVERY MAGNITUDE. The only route here is opt/api.py::counters'
    # resume subtraction, whose base is stamped FROM st.n_backward, so a negative says the backward
    # counter went BACKWARDS across a resume. It used to be caught only as a SIDE EFFECT of `//`
    # flooring a partial step up -- floor(n/k) is at most -1 for every n < 0 -- and the same-day
    # correction to truncation removed even that: at accum=4 the deltas -1, -2, -3 came back
    # Steps(0) against a `taken` of Steps(0) and counters() said nothing. The magnitudes below span
    # each accum's silent window and one past it.
    for accum in (1, 2, 4, 8):
        for n in (-1, -2, -3, -4, -5, -8, -9):
            try:
                derive.opt_steps_from_backwards(Backwards(n), accum)
                raise AssertionError(f"negative accepted: {n} at accum={accum}")
            except UnitError:
                pass

    # accum_due CLAMPS ITS RATE WHERE opt_steps_from_backwards REFUSES ONE, and that asymmetry is
    # deliberate -- accum_due's docstring keeps the shipped read-site `max(1, ...)`, and
    # opt_steps_from_backwards' says so in as many words at the end of its own refusal paragraph.
    # So `k = max(1, int(accum))` makes both rates below 1 into 1, and `n > 0 and n % 1 == 0` is
    # True for 52. Pinned so the difference is a decision on the record rather than one nobody
    # noticed. The third row is the count end: `n > 0` is False at -4, so a negative is not due --
    # answered rather than refused, which is the other half of the same asymmetry.
    assert derive.accum_due(Backwards(52), 0) is True
    assert derive.accum_due(Backwards(52), -4) is True
    assert derive.accum_due(Backwards(-4), 4) is False

    # THE RATE END, ALL FIVE CONVERSIONS AT ONCE. units.Clock declares __int__ and __index__, so
    # `int(Windows(4))` is 4 and every conversion that wrote `int(rate)` admitted at its divisor the
    # kind it refuses at its clock: opt_steps_from_backwards(Backwards(52), Windows(4)) answered
    # Steps(13) until 2026-09-04 -- a Windows crossing a function whose first act is to refuse a
    # Windows. A rate is a RATIO of two kinds and no count of one kind is ever the right value for
    # it, so all five refuse all six kinds rather than converting.
    for fn, clk in ((derive.flush_period, Steps(20000)),
                    (derive.flush_period_windows, Windows(20000)),
                    (derive.opt_steps_from_windows, Windows(1024)),
                    (derive.opt_steps_from_backwards, Backwards(52)),
                    (derive.accum_due, Backwards(52))):
        for rate in (Windows(4), Steps(4), Flushes(4), Backwards(4), Epochs(4)):
            try:
                fn(clk, rate)
                raise AssertionError(f"{fn.__name__} accepted {rate!r} as its rate")
            except UnitError:
                pass
    try:
        derive.run_windows_from_epochs(Epochs(3), Windows(4))
        raise AssertionError("run_windows_from_epochs accepted a Clock rate")
    except UnitError:
        pass
    # NEIGHBOURS, so the refusals above cannot be a blanket one: the bare-int rate still works, and
    # each of the four answers is the arithmetic named beside it.
    assert derive.flush_period(Steps(20000), 16) == Flushes(1250)           # 20000 = 16 x 1250
    assert derive.flush_period_windows(Windows(20000), 16) == Flushes(1250)
    assert derive.opt_steps_from_windows(Windows(1024), 64) == Steps(16)    # 1024 = 64 x 16
    assert derive.accum_due(Backwards(52), 4) is True                       # 52 = 4 x 13, remainder 0

    # pin_tick: THE ONE FUNCTION HERE WHOSE ORACLE TABLE CANNOT SEE ITS OWN DEFECT, so these assertions
    # are not a supplement to pin_tick.json -- they are the entire coverage of its units. The captured
    # grid passes bare ints in all 32 cases (the shipped function had no types to capture), a bare int
    # carries no kind, and _comparable unwraps the answer to an int before comparing; a typed
    # implementation and a completely untyped one therefore replay all 32 cases identically and both
    # report OK. Everything the table can prove about pin_tick is arithmetic. Everything below is unit.
    #
    # This matters more here than anywhere else in the file because pin_tick IS the project's flagship
    # unit defect: it counted FLUSHES against GROW_CAP_EVERY=20000 declared in STEPS, so at BATCH_W=16
    # the population sat pinned for 43,645 real steps while the clock read 2,650, and the report printed
    # a true sentence about a false clock. Untyped, `pin_tick(Flushes(2650), True, Flushes(16))` returned
    # 2666 and rebuilt that defect exactly, inside the function documenting it.
    #
    # THE KIND CHECK COMES BEFORE THE VALUE CHECK and that order is deliberate. `Steps(2666) == 2666`
    # RAISES rather than returning False, so against an untyped pin_tick the value assertion below fails
    # as a UnitError traceback out of units.Clock._same -- a real failure, reported as a crash in the
    # wrong file. Asserting the type first makes the same regression say what it is.
    # WINDOWS, NOT STEPS, AND THESE ASSERTIONS SAID Steps UNTIL THE CONTRADICTION WAS FOUND. Two frozen
    # surfaces disagreed: src/capacity/api.py:16 declared "pin_tick is re-typed to accumulate
    # units.Windows ... NO CONVERSION HAPPENS ANYWHERE" while derive.pin_tick refused a Windows, so a
    # P4 implementer following the contract got UnitError on the first flush and the only non-raising
    # implementation left was `int(held) >= cap.pin_windows` -- the original defect, restored at the
    # comparison. units.py settles which side was wrong: Steps is "Optimizer steps ... AND NOTHING
    # ELSE", Windows is "what `step` counts", and this clock accumulates deltas of `step`.
    # The 32 oracle cases above did not move: they record raw ints in and out, so they pin the
    # arithmetic and never saw the kind. These typed assertions are the only thing that did.
    assert type(derive.pin_tick(Windows(2650), True, Windows(16))) is Windows, "pin_tick lost its unit"
    assert derive.pin_tick(Windows(2650), True, Windows(16)) == Windows(2666)
    assert type(derive.pin_tick(2650, True, 16)) is Windows        # bare ints coerce IN, Windows comes OUT
    assert derive.pin_tick(Windows(8), False, Windows(16)) == Windows(0)   # clamped, still carrying kind
    for bad in (Flushes(2650), Steps(2650), Backwards(2650)):
        try:
            derive.pin_tick(bad, True, Windows(16))
            raise AssertionError(f"foreign clock accepted as held: {bad!r}")
        except UnitError:
            pass
        try:
            derive.pin_tick(Windows(2650), True, bad)
            raise AssertionError(f"foreign clock accepted as dstep: {bad!r}")
        except UnitError:
            pass
    # The kind has to survive OUT of the function, because the comparison -- not the accumulation -- is
    # where the 16x error actually landed. A Windows answer measures against CAP.pin_windows and REFUSES
    # the same threshold expressed in flushes, which is the failure the shipped code never got.
    held = derive.pin_tick(Windows(43645), True, Windows(0))
    assert held >= Windows(20000)                                 # 43,645 real ticks: the lift was earned
    for wrong in (derive.flush_period_windows(Windows(20000), 16),  # repair (b): the same threshold,
                  Steps(20000)):                                    # in flushes -- and the old kind
        try:
            _ = held >= wrong
            raise AssertionError(f"a windows clock compared against {wrong!r} and did not raise")
        except UnitError:
            pass

    # --- opt_steps_from_windows: the last unnamed cross-kind conversion in the tree, now named.
    # NO ORACLE ROW, and for the same reason as cadences_that_cannot_fire: the old tree resolved the
    # horizon by reading ANOTHER KNOB (`if LR_STEPS: return LR_STEPS`, else project through
    # LR_EPOCHS), so there is no captured table for this shape -- what was captured is the defect.
    # The rule is written here instead, and the numbers are the ones that matter.
    assert derive.opt_steps_from_windows(Windows(1024), 1) == Steps(1024)     # defaults: they coincide
    assert type(derive.opt_steps_from_windows(Windows(1024), 1)) is Steps
    # 64x is not academic: it is fetch_big.py's OWN recommended heavy-run command,
    # WIN=256 BATCH_W=16 ACCUM=4, so effective_batch_windows = 16 x 4. A horizon taken in the wrong
    # kind there puts every learning-rate result under a schedule 64 times longer than its label.
    assert derive.opt_steps_from_windows(Windows(1024), 64) == Steps(16)
    assert derive.opt_steps_from_windows(Windows(10), 64) == Steps(1)        # floored, never zero
    for bad in (Steps(1024), Flushes(1024), Backwards(1024), 1024):
        try:
            derive.opt_steps_from_windows(bad, 4)
            raise AssertionError(f"opt_steps_from_windows accepted {bad!r} as a window count")
        except UnitError:
            pass
    try:
        derive.opt_steps_from_windows(Windows(1024), 0)
        raise AssertionError("a zero divisor was accepted; n_cycles would divide by zero")
    except UnitError:
        pass
    # The answer is STEPS, so it refuses the two kinds it would otherwise be confused with -- which
    # is the entire reason the function exists rather than the division that was there before.
    for wrong in (Windows(16), Flushes(16)):
        try:
            _ = derive.opt_steps_from_windows(Windows(1024), 64) >= wrong
            raise AssertionError(f"a Steps horizon compared against {wrong!r} and did not raise")
        except UnitError:
            pass

    # --- cadences_that_cannot_fire: C11's measurement, pinned as a test rather than left in a doc.
    # NO ORACLE TABLE, and the reason is worth stating: this function has no old-tree equivalent to
    # capture -- the old system had no such audit, which is exactly why the ten defaults could sit
    # longer than the run for the whole project's life without anyone reading a line about it. So the
    # known-answer table is written here by hand from the SHIPPED defaults, and it fails the day
    # either the defaults or the run-length arithmetic moves.
    _per = {"curve": Windows(2000), "ckpt": Windows(1000), "fab.manage": Windows(500),
            "dom.manage": Windows(100), "dom.rekey": Windows(200)}
    # 506 windows = 120000 bytes / 1.85 bytes-per-token / 128 tokens, the project's own measured
    # compression against the shipped DATA.stream_bytes and LM.ctx.
    assert derive.cadences_that_cannot_fire(Windows(506), _per) == [("curve", 2000, 506),
                                                                    ("ckpt", 1000, 506)]
    # 937 = the same at the 1.0 bytes/token CEILING, which no real corpus reaches. Still two gates.
    assert derive.cadences_that_cannot_fire(Windows(937), _per) == [("curve", 2000, 937),
                                                                    ("ckpt", 1000, 937)]
    # At P3's own exit criterion -- 200 steps -- FOUR of the five gates cannot fire, and the fifth
    # (dom.manage at 100) fires twice. That is the sentence the audit exists to put in the report.
    assert len(derive.cadences_that_cannot_fire(Windows(200), _per)) == 4
    assert derive.cadences_that_cannot_fire(Windows(60000), _per) == []      # a real run: all reachable
    # A ZERO PERIOD IS A SENTINEL AND IS REPORTED, not skipped. CKPT.every defaults to 0, and
    # ckpt/api.py says what that means there -- "the only save is the final one plus SIGUSR1" -- a
    # legitimate configuration that the audit must SAY rather than leave to be inferred from a
    # missing line. The first version tested only `period >= run`, so the ckpt gate vanished from a
    # list whose whole purpose is naming gates that cannot fire; found by running the audit against
    # the real resolved defaults.
    assert derive.cadences_that_cannot_fire(Windows(60000), {"ckpt": Windows(0)}) == [("ckpt", 0, 0)]
    assert derive.cadences_that_cannot_fire(Windows(10), {"ckpt": Windows(0)}) == [("ckpt", 0, 0)]
    # STRICT AT THE BOUNDARY: a period equal to the run length is reported, because a gate fires on
    # elapsed-since-last-fire and one exactly-equal period has a single chance, at the final window.
    assert derive.cadences_that_cannot_fire(Windows(500), {"x": Windows(500)}) == [("x", 500, 500)]
    assert derive.cadences_that_cannot_fire(Windows(501), {"x": Windows(500)}) == []
    for bad_run, bad_per in ((Flushes(506), _per), (Windows(506), {"x": Steps(10)})):
        try:
            derive.cadences_that_cannot_fire(bad_run, bad_per)
            raise AssertionError("a foreign clock kind was accepted by cadences_that_cannot_fire")
        except UnitError:
            pass

    # The remaining five are covered by their tables; call each once so an import-time or signature
    # breakage cannot hide behind a table that is only read when the file is run.
    assert derive.cull_gate_open(2090, 4096, 0.45) is True
    assert derive.lift_to(160, 0.05, 16) == 176
    assert derive.bwt_of({"eng": 2.273}, {"eng": 2.125}) > 0      # POSITIVE = WORSE = FORGETTING
    assert derive.forgetting_of({"eng": 2.0}, {"eng": 2.125}) == 0.0
    assert derive.curve_verdict(1.118, 0.0, 0.0) == "blewup"      # the run that was called PLATEAUED
    # sched_ctl read 4.82 at step 14,000 and was back at 2.95 by the next probe. ONE elevated probe
    # among healthy ones cannot move the median, which is what defeated the alarm that fired on 4
    # of 4 healthy runs; a run that is elevated at the median and stale does still fire.
    assert derive.blowup_stale([2.0, 2.1, 4.82], 2.0, 100) is False
    assert derive.blowup_stale([3.0, 4.82, 2.95], 2.0, 300) is True
    assert derive.blowup_stale([3.0, 4.82, 2.95], 2.0, 50) is False    # elevated but not yet stale
    assert derive.phase_schedule(2)[-1] != [0, 1]                 # the last phase must exclude someone


def main():
    print(f"spine.derive replayed against {ORACLE}")
    total = bad = 0
    for name in sorted(os.listdir(ORACLE)):
        if not name.endswith(".json"):
            continue
        cases, misses = replay(name[:-5])
        total += cases
        bad += misses
        print(f"  {name[:-5]:<20} {cases:>4} cases  {'OK' if not misses else str(misses) + ' MISS'}")
    smoke()
    print(f"  {'smoke':<20} {'':>4}        OK")
    print(f"{total} oracle cases, {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
