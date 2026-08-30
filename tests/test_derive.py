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
    from spine.units import Backwards, Flushes, Steps, UnitError, Windows

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
