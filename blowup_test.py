#!/usr/bin/env python3
"""Does the divergence alarm fire on runs that diverged, and stay quiet on runs that did not?

IT DID NOT. The first version compared ONE probe against the best-so-far and fired at +0.5 bits/byte. Across
the four-arm round15 pilot it went off in FOUR RUNS OUT OF FOUR, at steps 8,000-12,000 -- on runs that went on
to produce 1.94 b/B, the best number this project has recorded. Its own message told the reader the run was
"worth killing rather than finishing".

The reason is in the data. The per-process held-out curve genuinely wanders, and the best-so-far is the running
MINIMUM of a noisy series, so best+0.5 is crossed by noise in every healthy run:

    sched_ctl, first eight probes:  3.37  2.83  2.78  3.54  2.99  2.84  4.82  2.95

Best 2.78 at probe 3, then 3.54 at probe 4 -- fired. The 4.82 two probes later is a single spike and the run is
back at 2.95 immediately after. Nothing was wrong.

What actually separates a blow-up from wander is not the SIZE of an excursion but whether the run comes back.
Measured as probes spent elevated with NO new best, over the nine real runs available:

    healthy   sched_ctl 28   sched_step 20   sched_warm 22   sched_both 50   lr_vcap 22   lr_pilot2 11
    blown up  round13 261    0.75 GB 309

BLOWUP_STALE=80 separates all nine. This file holds the curves that defeated the old rule, so it cannot come
back, and checks the constants still sit between the two populations.

Loaded from the shipped source by AST like lift_to and pin_tick, so it runs without torch.

Run: python3 blowup_test.py
"""
import ast
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_organize.py")
_tree = ast.parse(open(_SRC).read())
# The constants first: they are the function's DEFAULT ARGUMENTS, so they have to be in the namespace before
# the def is executed. Read from the shipped source too, and the thresholds below are asserted against them --
# so editing one without the other fails here rather than silently changing when the alarm fires.
_ns = {n.targets[0].id: n.value.value for n in _tree.body
       if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
       and n.targets[0].id in ("BLOWUP_RISE", "BLOWUP_STALE")}
RISE, STALE = _ns.get("BLOWUP_RISE"), _ns.get("BLOWUP_STALE")
if RISE is None or STALE is None:
    print("!! BLOWUP_RISE / BLOWUP_STALE are not module-level constants in self_organize.py -- this test "
          "asserts the shipped thresholds and cannot find them.")
    sys.exit(1)
_fn = next((n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == "blowup_stale"), None)
if _fn is None:
    print("!! blowup_stale is not a module-level function in self_organize.py -- it was put there so this test "
          "could exercise the shipped rule; if it moved into a closure, this test is testing nothing.")
    sys.exit(1)
exec(compile(ast.Module(body=[_fn], type_ignores=[]), _SRC, "exec"), _ns)
blowup_stale = _ns["blowup_stale"]

FAILED = []


def check(cond, msg):
    if not cond: FAILED.append(msg); print(f"  FAIL  {msg}")
    else: print(f"  ok    {msg}")


def run(curve, rise=None, stale=None):
    """Drive the alarm over a curve exactly as the call site does. Returns the probe index it fired on, or None."""
    rise = RISE if rise is None else rise
    stale = STALE if stale is None else stale
    best, since, recent = None, 0, []
    for i, x in enumerate(curve):
        recent.append(x); del recent[:-5]
        if best is None or x < best - 1e-6:
            best = x; since = 0; continue
        since += 1
        if blowup_stale(recent, best, since, rise, stale): return i
    return None


print(f"blow-up alarm: BLOWUP_RISE={RISE}  BLOWUP_STALE={STALE}\n")
check(RISE is not None and STALE is not None, "both constants are module-level in the shipped source")

# --- 1. THE FALSE POSITIVE THAT PROMPTED THIS ------------------------------------------------------------------
# The real opening of sched_ctl. The old rule fired at probe 4 (step 8,000). This run ended at 1.956.
print("\nTHE FOUR-OUT-OF-FOUR FALSE POSITIVE -- real curve openings, all four arms ended healthy")
CTL_OPEN = [3.37, 2.83, 2.78, 3.54, 2.99, 2.84, 4.82, 2.95, 2.71, 2.66, 2.55, 2.49, 2.44, 2.39, 2.35, 2.31]
STEP_OPEN = [3.35, 2.75, 2.71, 3.03, 3.01, 3.24, 2.97, 3.02, 2.80, 2.71, 2.63, 2.58, 2.51, 2.47, 2.42, 2.38]
old = lambda c: next((i for i in range(1, len(c))
                      if c[i] > min(c[:i]) + 0.5), None)          # the rule that shipped and failed
for _n, _c in (("sched_ctl", CTL_OPEN), ("sched_step", STEP_OPEN)):
    _o, _new = old(_c), run(_c)
    print(f"  {_n:11s} old rule fired at probe {_o}, new rule {'fired at ' + str(_new) if _new is not None else 'SILENT'}")
    check(_o is not None, f"{_n}: the old rule really did fire on this curve -- the regression is captured")
    check(_new is None, f"{_n}: the new rule stays quiet through the early transient")
check(run([2.78, 4.82, 2.95] + [2.5] * 200) is None,
      "a single 4.82 spike between healthy probes cannot fire it -- the median is judged, not the latest")

# --- 2. THE TWO RUNS THAT REALLY DID BLOW UP -------------------------------------------------------------------
# round13: best 2.23 at probe 19, then a sustained level near 3.4 for the remaining 260 probes.
print("\nTHE REAL ONES -- elevated and never coming back")
r13 = [3.0 - 0.04 * i for i in range(19)] + [3.40, 4.05, 6.80] + [3.4 + (0.1 if i % 3 else -0.1)
                                                                 for i in range(258)]
big = [3.0 - 0.03 * i for i in range(28)] + [2.7 + (0.2 if i % 2 else 0.0) for i in range(300)]
for _n, _c in (("round13-shaped", r13), ("0.75GB-shaped", big)):
    _f = run(_c)
    print(f"  {_n:15s} fires at probe {_f} of {len(_c)}")
    check(_f is not None, f"{_n}: a sustained elevated level does fire the alarm")
    check(_f is not None and _f < len(_c) * 0.75,
          f"{_n}: and fires with most of the run still to save (probe {_f} of {len(_c)})")

# --- 3. THE MARGIN, FROM THE MEASURED POPULATIONS --------------------------------------------------------------
# These are the observed staleness counts, not invented ones. The constant has to sit between them.
print("\nMARGIN -- the constant must separate two measured populations")
HEALTHY = {"sched_ctl": 28, "sched_step": 20, "sched_warm": 22, "sched_both": 50,
           "lr_vcap": 22, "lr_pilot2": 11}
BLOWN = {"round13": 261, "0.75GB": 309}
print(f"  healthy max {max(HEALTHY.values())} ({max(HEALTHY, key=HEALTHY.get)})   "
      f"blown min {min(BLOWN.values())} ({min(BLOWN, key=BLOWN.get)})   threshold {STALE}")
check(STALE > max(HEALTHY.values()), f"{STALE} is above every healthy run measured (worst {max(HEALTHY.values())})")
check(STALE < min(BLOWN.values()), f"{STALE} is below both blow-ups (earliest {min(BLOWN.values())})")
check(STALE >= max(HEALTHY.values()) * 1.5,
      "and it clears the healthy ceiling by half again, not by a probe or two")

# --- 4. THE RULE ITSELF ----------------------------------------------------------------------------------------
print("\nTHE RULE")
check(blowup_stale([3.0] * 5, 2.0, STALE) is True, "elevated and stale -> fires")
check(blowup_stale([3.0] * 5, 2.0, STALE - 1) is False, "elevated but one probe short of stale -> silent")
check(blowup_stale([2.4] * 5, 2.0, STALE * 10) is False, "stale but NOT elevated -> silent; a converged run is not a blow-up")
check(blowup_stale([3.0] * 5, None, STALE) is False, "no best yet -> silent")
check(blowup_stale([3.0, 3.0], 2.0, STALE) is False, "fewer than three probes of history -> silent")
check(blowup_stale([2.0, 2.0, 9.9, 9.9, 9.9], 2.0, STALE) is True, "the median follows a genuine shift in level")
check(blowup_stale([2.0, 2.0, 2.0, 2.0, 9.9], 2.0, STALE) is False, "...and ignores one outlier at the end")

print()
if FAILED:
    print(f"FAILED {len(FAILED)} check(s):")
    for f in FAILED: print(f"  - {f}")
    sys.exit(1)
print("blowup_test: all checks passed")
