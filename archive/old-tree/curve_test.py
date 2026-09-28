#!/usr/bin/env python3
"""The three end-of-run decisions that had no test, and every wrong answer they have shipped.

selftest.sh checked that these sections APPEARED. That is not the same as checking what they say, and all
three have been wrong in production while printing a confident sentence and exiting 0:

  curve_verdict   four wrong verdicts across five thresholds -- sign read backwards, "DIVERGING" for a flat
                  tail, "PLATEAUED ... nothing is degrading" for a run that lost 1.118 b/B and never got it
                  back, and "flat since" for a curve falling at -0.086.
  bwt_of          checked only by grepping the log for the words "BWT" and "negative = old domains IMPROVED".
                  Reversing the subtraction passes both, and inverts the project's headline continual-learning
                  claim -- the source says so itself: "a sign error here would invert the project's headline".
  cull_gate_open  no test at all, and three mechanisms live behind it (the utilization cull, the utilization
                  spare, FAB_RESCUE). It has already silently removed all three from a whole investigation.

Loaded from the shipped source by AST, so it runs without torch.

Run: python3 curve_test.py
"""
import ast
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_organize.py")
_tree = ast.parse(open(_SRC).read())
_ns = {n.targets[0].id: n.value.value for n in _tree.body
       if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
       and n.targets[0].id.startswith("CURVE_")}
_want = ("curve_verdict", "bwt_of", "forgetting_of", "cull_gate_open")
for _w in _want:
    _fn = next((n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == _w), None)
    if _fn is None:
        print(f"!! {_w} is not a module-level function in self_organize.py -- it was hoisted there so this "
              f"test could exercise the shipped decision; back inside main() it is untestable again.")
        sys.exit(1)
    exec(compile(ast.Module(body=[_fn], type_ignores=[]), _SRC, "exec"), _ns)
curve_verdict, bwt_of = _ns["curve_verdict"], _ns["bwt_of"]
forgetting_of, cull_gate_open = _ns["forgetting_of"], _ns["cull_gate_open"]
RISE, FLAT, TOK = _ns["CURVE_RISE_BLEWUP"], _ns["CURVE_FLAT"], _ns["CURVE_TOK_RISE"]

FAILED = []


def check(cond, msg):
    if not cond: FAILED.append(msg); print(f"  FAIL  {msg}")
    else: print(f"  ok    {msg}")


print(f"thresholds from the source: blew-up {RISE}, flat +/-{FLAT}, per-token {TOK}\n")

# --- 1. THE FOUR WRONG VERDICTS IT HAS ACTUALLY SHIPPED --------------------------------------------------------
# Each row is a real run: (rise since minimum, change over the last two thirds, per-token rise, what it must say)
print("EVERY VERDICT THIS CASCADE HAS GOT WRONG, as a known answer")
REAL = [
    # rise since minimum, change over the last two thirds, per-token rise -- all read off the logs, and the
    # verdict each one PRINTED at the time, so a fix that silently changes an old answer fails here.
    ("sched_ctl",          0.036, -0.086, 0.000, "recovering", "printed PLATEAUED while FALLING at -0.086"),
    ("round12 lr_vcap",    0.005, -0.294, 0.000, "recovering", "printed PLATEAUED while falling at -0.294"),
    ("round13 lr_expvalve", 1.118,  0.037, 0.539, "blewup",    "printed PLATEAUED, nothing is degrading"),
    ("0.75 GB lr_pilot2_1", 0.235, -0.541, 0.447, "recovering", "printed PLATEAUED"),
    ("0.75 GB lr_075",     0.725,  0.574, 0.302, "blewup",     "printed BLEW UP -- correct, and must stay"),
    ("sched_both",         0.133,  0.089, 0.082, "diverging",  "printed DIVERGING -- correct, and must stay"),
    ("round11 lr_pilot2",  0.000, -0.259, 0.498, "vocab",      "printed NOT DIVERGING -- the vocabulary"),
]
for name, rise, tail, tok, want, why in REAL:
    got = curve_verdict(rise, tail, tok)
    print(f"  {name:20s} rise {rise:+.3f} tail {tail:+.3f} -> {got:11s} ({why})")
    check(got == want, f"{name}: verdict is {got}, must be {want}")

# --- 2. HEIGHT AND TAIL ARE TWO QUESTIONS ----------------------------------------------------------------------
# Every past failure came from reading one and not the other.
print("\nHEIGHT AND TAIL ARE SEPARATE QUESTIONS -- reading one alone is how all four failures happened")
check(curve_verdict(1.5, 0.0, 0.0) == "blewup", "a big rise with a FLAT tail is still a blow-up (the round13 case)")
# A per-token rise with a flat bits/byte curve is the VOCABULARY, and that branch is FIRST -- it outranks a
# climbing tail, because a tail measured in per-token units is exactly what the vocabulary moves.
check(curve_verdict(0.0, 0.5, 0.5) == "vocab", "per-token up, no bits/byte rise -> vocab, before anything else")
# ...and with NO per-token rise it says nothing at all, which is what the cascade has always done: DIVERGING
# was guarded on the per-token curve agreeing. Asserted once, at the faithfulness check further down -- an
# earlier draft of this file asserted "diverging" here and "none" there for the identical inputs, which is the
# same two-lines-apart contradiction the cascade itself shipped.
check(curve_verdict(0.02, -0.5, 0.0) == "recovering", "a falling tail is never 'flat', however small the rise")
check(curve_verdict(0.02, 0.0, 0.0) == "plateau", "small rise, flat tail: the one case that IS a plateau")

print("\n  the flat band is two-sided, which is the fault that recurred three times in this project")
check(curve_verdict(0.1, -FLAT * 1.01, 0.0) == "recovering", "just below the band -> falling, not flat")
check(curve_verdict(0.1, 0.0, 0.0) == "plateau", "inside the band -> flat")
check(curve_verdict(0.1, FLAT * 1.01, 0.2) == "diverging", "just above the band -> climbing, not flat")

print("\n  a per-token rise the bits/byte curve does not share is the VOCABULARY, not the model")
check(curve_verdict(0.0, 0.0, 0.5) == "vocab", "per-token up, bits/byte flat -> vocab")
check(curve_verdict(0.6, 0.0, 0.5) == "blewup", "...but a real blow-up outranks it")
check(curve_verdict(None, None, 0.5) == "diverging", "no unit-stable curve at all -> judged on per-token alone")
check(curve_verdict(None, None, 0.0) == "none", "...and nothing to say when neither curve moved")
# FAITHFULNESS: the shipped cascade only ever claimed DIVERGING when the per-token curve agreed.
check(curve_verdict(0.1, 0.5, 0.0) == "none",
      "a climbing tail with NO per-token rise stays silent, as the cascade has always done")

# --- 3. BWT: THE SIGN ------------------------------------------------------------------------------------------
print("\nBWT -- lower-is-better, so NEGATIVE means the old domains IMPROVED")
check(bwt_of({"eng": 1.9}, {"eng": 2.1}) < 0, "old material got better -> negative")
check(bwt_of({"eng": 2.3}, {"eng": 2.1}) > 0, "old material got worse -> positive")
check(abs(bwt_of({"eng": 1.9, "py": 2.1}, {"eng": 2.1, "py": 2.1}) - (-0.1)) < 1e-12, "it is the MEAN over domains")
# The reversal that selftest.sh could not have caught: it passes every string check in the log.
_rev = lambda now, prev: -bwt_of(now, prev)
check(bwt_of({"eng": 1.9}, {"eng": 2.1}) != _rev({"eng": 1.9}, {"eng": 2.1}),
      "a reversed subtraction is a DIFFERENT number here -- which grepping the legend text could never tell")
check(bwt_of({}, {}) == 0.0, "no shared domains -> 0, not a ZeroDivisionError at the end of a long run")
check(bwt_of({"eng": 1.9}, {"py": 2.1}) == 0.0, "no OVERLAP -> 0; it only averages domains present in both")

print("\nFORGETTING F -- clipped at zero, so improvement cannot cancel a regression")
check(forgetting_of({"eng": 2.3}, {"eng": 2.1}) > 0, "above its own best -> positive")
check(forgetting_of({"eng": 1.9}, {"eng": 2.1}) == 0.0, "below its own best -> 0, not negative")
_bwt = bwt_of({"a": 1.0, "b": 3.0}, {"a": 2.0, "b": 2.0})
_f = forgetting_of({"a": 1.0, "b": 3.0}, {"a": 2.0, "b": 2.0})
print(f"  one domain +1.0, one -1.0:  BWT {_bwt:+.2f}   F {_f:.2f}")
check(abs(_bwt) < 1e-12 and _f > 0,
      "BWT nets them to zero and F does not -- which is the whole reason both are reported")

# --- 4. THE CULL GATE ------------------------------------------------------------------------------------------
print("\nTHE CULL GATE -- three mechanisms live behind it")
check(cull_gate_open(2048, 4096, 0.45) is True, "0.50 occupancy against 0.45 -> open")
check(cull_gate_open(2048, 4096, 0.75) is False, "0.50 against 0.75 -> SHUT (the state that ran for a whole round)")
check(cull_gate_open(3000, 8192, 0.45) is False, "0.37 against 0.45 -> shut; the valve arm's standing state")
check(cull_gate_open(3932, 8192, 0.45) is True, "0.48 against 0.45 -> open once the ramp has built the population")
print("\n  and the floor, which is not a pressure test")
check(cull_gate_open(2, 2, 0.0) is False, "a population of 2 is never culled, whatever the occupancy")
check(cull_gate_open(3, 3, 0.0) is True, "3 is")
check(cull_gate_open(100, 0, 0.5) is True, "a zero cap does not divide by zero")
# The setpoint the report predicts from: population settles near pressure x cap.
check(cull_gate_open(int(0.45 * 8192) + 1, 8192, 0.45) and not cull_gate_open(int(0.45 * 8192) - 1, 8192, 0.45),
      "the gate turns over exactly at pressure x cap -- the settling point the report predicts")

print()
if FAILED:
    print(f"FAILED {len(FAILED)} check(s):")
    for f in FAILED: print(f"  - {f}")
    sys.exit(1)
print("curve_test: all checks passed")
