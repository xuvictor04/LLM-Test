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
    assert type(derive.pin_tick(Steps(2650), True, Steps(16))) is Steps, "pin_tick lost its unit type"
    assert derive.pin_tick(Steps(2650), True, Steps(16)) == Steps(2666)
    assert type(derive.pin_tick(2650, True, 16)) is Steps          # bare ints coerce IN, Steps comes OUT
    assert derive.pin_tick(Steps(8), False, Steps(16)) == Steps(0)  # clamped at zero, still carrying kind
    for bad in (Flushes(2650), Windows(2650), Backwards(2650)):
        try:
            derive.pin_tick(bad, True, Steps(16))
            raise AssertionError(f"foreign clock accepted as held: {bad!r}")
        except UnitError:
            pass
        try:
            derive.pin_tick(Steps(2650), True, bad)
            raise AssertionError(f"foreign clock accepted as dstep: {bad!r}")
        except UnitError:
            pass
    # The kind has to survive OUT of the function, because the comparison -- not the accumulation -- is
    # where the 16x error actually landed. A Steps answer measures against a Steps threshold and REFUSES
    # the same threshold expressed in flushes, which is the failure the shipped code never got.
    held = derive.pin_tick(Steps(43645), True, Steps(0))
    assert held >= Steps(20000)                                   # 43,645 real steps: the lift was earned
    try:
        _ = held >= derive.flush_period(Steps(20000), 16)         # the same threshold, in flushes: 1250
        raise AssertionError("a steps clock compared against a flush threshold and did not raise")
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
