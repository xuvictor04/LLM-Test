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
_fn = next((n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == "lift_to"), None)
if _fn is None:
    print("!! lift_to is not a module-level function in self_organize.py -- it was put there so this test could "
          "exercise the shipped code; if it moved into a closure, this test is testing nothing.")
    sys.exit(1)
_ns = {}
exec(compile(ast.Module(body=[_fn], type_ignores=[]), _SRC, "exec"), _ns)
lift_to = _ns["lift_to"]

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

print()
if FAILED:
    print(f"FAILED {len(FAILED)} check(s):")
    for f in FAILED: print(f"  - {f}")
    sys.exit(1)
print("cap_test: all checks passed")
