#!/usr/bin/env python3
"""How much capacity does one earned lift hand out?

This knob has been wrong twice, in opposite directions:

  1. A MULTIPLIER of 2.0. One lift doubled the cap, and each later lift handed out more than the one before --
     a valve that opens wider every time it opens.
  2. A flat COUNT of 256. That fixed the runaway, but the same number meant +160% against gc_pin's expert cap of
     160 and +12.5% against a vocabulary at 2048. One knob cannot be both a nudge and a doubling.

It is now a small FRACTION of the current cap, with GROW_LIFT_MIN as an absolute floor so small caps still move.
A fraction is the only form that means the same thing at 160 and at 4096, and a small one does not run away:
at 8% a cap needs nine lifts to grow by half and eleven to double.

Loaded from the shipped source by AST rather than imported, for the same reason as proj_test.py: this is pure
arithmetic and a test of it should not be unrunnable because torch is missing.

Run: python3 cap_test.py
"""
import ast
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_organize.py")
_tree = ast.parse(open(_SRC).read())
_ns = {}
for _want in ("lift_to", "pin_tick"):
    _fn = next((n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == _want), None)
    if _fn is None:
        print(f"!! {_want} is not a module-level function in self_organize.py -- it was put there so this test "
              f"could exercise the shipped code; if it moved into a closure, this test is testing nothing.")
        sys.exit(1)
    exec(compile(ast.Module(body=[_fn], type_ignores=[]), _SRC, "exec"), _ns)
lift_to = _ns["lift_to"]; pin_tick = _ns["pin_tick"]

FAILED = []


def check(cond, msg):
    if not cond: FAILED.append(msg); print(f"  FAIL  {msg}")
    else: print(f"  ok    {msg}")


FRAC, FLOOR = 0.08, 8

print("lift_to known-answer tests\n")

# --- 1. THE SAME PROPORTION AT EVERY SIZE -- the whole point of the change ----------------------------------
print("PROPORTIONALITY -- one lift should mean the same thing to a small cap and a large one")
for cap in (160, 640, 896, 2048, 4096):
    new = lift_to(cap, FRAC, FLOOR)
    pct = (new - cap) / cap
    print(f"  {cap:5d} -> {new:5d}  (+{new-cap:4d}, {pct:+.1%})")
    check(abs(pct - FRAC) < 0.02 or (new - cap) == FLOOR,
          f"cap {cap}: lift is {pct:.1%}, within tolerance of {FRAC:.0%} (or on the floor)")
# The old flat count is what this replaces: assert the spread across sizes actually collapsed.
_old = [(256 / c) for c in (160, 640, 2048)]
_new = [((lift_to(c, FRAC, FLOOR) - c) / c) for c in (160, 640, 2048)]
check(max(_new) - min(_new) < (max(_old) - min(_old)) / 10,
      f"spread across sizes: flat-256 {max(_old)-min(_old):.0%} -> proportional {max(_new)-min(_new):.1%}")

# --- 2. IT MUST NOT RUN AWAY -- the fault the flat count was introduced to fix ------------------------------
print("\nNO RUNAWAY -- a fraction compounds, so check how slowly")
cap, n = 640, 0
while cap < 1280 and n < 100:
    cap = lift_to(cap, FRAC, FLOOR); n += 1
print(f"  640 -> 1280 (a doubling) takes {n} lifts at {FRAC:.0%}")
check(n >= 8, f"doubling needs {n} lifts, not a handful -- this is a valve, not a floodgate")
# And against the multiplier it replaced, which doubled in ONE.
check(lift_to(640, FRAC, FLOOR) < 640 * 1.2, "a single lift is nowhere near the 2.0 multiplier it started as")

# --- 3. THE FLOOR ------------------------------------------------------------------------------------------
print("\nFLOOR -- a small cap must still move")
for cap in (1, 16, 64):
    new = lift_to(cap, FRAC, FLOOR)
    check(new >= cap + FLOOR, f"cap {cap} -> {new}: lifted by at least the floor of {FLOOR}")
check(lift_to(100, 0.0, FLOOR) == 100 + FLOOR, "a zero fraction still moves by the floor, never by nothing")

# --- 4. GUARDS ---------------------------------------------------------------------------------------------
print("\nGUARDS")
check(lift_to(2048, FRAC, FLOOR) > 2048, "a lift always increases the cap")
check(isinstance(lift_to(640, FRAC, FLOOR), int), "returns an int -- it indexes preallocated rows")
# Monotone in the fraction: 10% must hand out at least as much as 5%.
check(lift_to(2048, 0.10, FLOOR) > lift_to(2048, 0.05, FLOOR), "a larger fraction lifts further")
# The floor must not silently dominate at sizes where the fraction is the intended lever.
check(lift_to(2048, FRAC, FLOOR) - 2048 > FLOOR, "at a large cap the FRACTION decides, not the floor")


# --- 5. THE PIN CLOCK, WHICH DECIDES *WHEN* A LIFT IS EARNED --------------------------------------------------
# A correct lift size is worth nothing if the clock that authorises it runs at the wrong rate. The valve's block
# sits below the batch early-out, so it executes once per FLUSH while `step` advances once per WINDOW; the clock
# was a bare +1/-1 per execution and therefore ran at 1/BATCH_W the rate GROW_CAP_EVERY is written in.
print("\nTHE PIN CLOCK -- it must count STEPS, not the number of times the valve was asked")
EVERY, BW = 20000, 16


def held_after(steps, batch_w, pinned=True):
    """Run the clock the way the call site does: one call per flush, batch_w steps of ground covered each."""
    held, prev = 0, 0
    for step in range(batch_w, steps + 1, batch_w):
        held = pin_tick(held, pinned, step - prev); prev = step
    return held


for bw in (1, 8, 16, 32):
    print(f"  BATCH_W={bw:2d}: after 43645 steps pinned the clock reads {held_after(43645, bw):6d}")
check(held_after(43645, 16) >= 43645 - 16, "at BATCH_W=16 the clock reads the steps that actually elapsed")
# Within ONE BATCH, not exactly equal: the clock can only be read on a flush, so the last partial batch is not
# yet counted. That is a rounding of at most BATCH_W steps against a threshold of 20000 -- the point is that the
# batch size no longer scales the knob's MEANING, which is what a bare +1 per flush did.
_spread = max(held_after(43645, b) for b in (1, 8, 16, 32)) - min(held_after(43645, b) for b in (1, 8, 16, 32))
print(f"  spread across batch sizes: {_spread} steps (was a factor of BATCH_W, i.e. 43645 -> 1364)")
check(_spread <= 32, "batch size costs at most the one unflushed batch, not a factor of BATCH_W")
# The measured failure, restated as an assertion: this is what the lr_pilot rehearsal actually did.
_bare = 43645 // 16                                   # what a bare +1 per flush accumulated
print(f"  the rehearsal: pinned 43645 steps, clock read {_bare} against GROW_CAP_EVERY={EVERY} -> no lift")
check(_bare < EVERY <= held_after(43645, 16),
      f"a run that WAS pinned long enough ({43645} >= {EVERY}) is now allowed the lift it earned")

print("\nAND IT MUST STILL DECAY -- a population mostly BELOW its cap cannot creep to a lift")
check(pin_tick(1000, False, 16) == 984, "unpinned, the clock gives back exactly the steps that elapsed")
check(pin_tick(8, False, 16) == 0, "it floors at zero rather than going negative")
check(pin_tick(1000, True, 0) == 1000, "a zero-step delta moves nothing")
# A brief dip must cost the dip, not the whole clock -- the fault the accumulate/decay form was built to fix.
_h = held_after(20000, 16)
check(pin_tick(_h, False, 16) > EVERY * 0.9, "one dip below the cap costs one dip, not the entire accumulation")

print()
if FAILED:
    print(f"FAILED {len(FAILED)} check(s):")
    for f in FAILED: print(f"  - {f}")
    sys.exit(1)
print("cap_test: all checks passed")
