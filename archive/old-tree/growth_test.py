#!/usr/bin/env python3
"""Known-answer tests for PlateauGrowth -- the trigger that gives a NEW AREA its capacity.

This exists because the REGRESSION trigger was measured firing ZERO times across every recent run while the
report read as healthy growth ("grow 417x on the RAMP, 0x on a REGRESSION, 0x on a stall"). Two separate
suppressions, both silent:

  1. THE RAMP STARVES IT. The ramp re-fires every cool//8 = 187 steps and each firing sets s.last, so the
     shared `t - s.last < s.cool` gate below it can never open. Fixed by latching the ramp (FAB_RAMP_TO=0.5
     against a population BUILT at FAB_N0=2048) rather than ramping to the cap.
  2. THE STALL COOLDOWN SWALLOWS IT. REGRESSION and stall shared one clock, so the common event suppressed
     the rare one -- traced to state W, unexpected TRUE, dropped on t - s.last = 772 against cool = 1500
     where s.last had been set by a routine stall. Fixed by giving REGRESSION its own cooldown, letting it
     preempt RECOVER, and COUNTING refusals instead of discarding them.

The point of the tests is that continual learning has exactly one signal saying "the material changed", and
a silent zero in that counter is indistinguishable from "nothing changed". Run: python3 growth_test.py
"""
import os, sys

os.environ.setdefault("DATA_MODE", "real")
os.environ.setdefault("BENCH", "1")
for _k in ("WORLD_MODEL", "FABRIC", "EXPERTS", "TOKENIZER"): os.environ.setdefault(_k, "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import self_organize as S

FAILED = []


def check(cond, msg):
    if not cond: FAILED.append(msg); print(f"  FAIL  {msg}")
    else: print(f"  ok    {msg}")


def run(steps=20000, n=2048, cap=4096, inject=None, blackout_at=None, **kw):
    """Drive PlateauGrowth over a synthetic loss curve. `inject` is (start, end, level)."""
    g = S.PlateauGrowth(ramp=4000, **kw)
    counts = {"ramp": 0, "REGRESSION": 0, "stall": 0}
    loss = 5.0
    for t in range(1, steps + 1):
        loss = max(1.9, loss - 0.0004)                       # ordinary training: improving, then flat
        if inject and inject[0] <= t < inject[1]: loss = inject[2]
        if blackout_at is not None and t == blackout_at: g.note_shift(t)
        if g.step(loss, t, n=n, cap=cap): counts[g.why] += 1
    # getattr, NOT g.n_regr_supp: against the PRE-FIX class the counter does not exist, and an AttributeError
    # would make these tests fail for the wrong reason. They have to fail on the BEHAVIOUR -- REGRESSION == 0.
    counts["refused"] = getattr(g, "n_regr_supp", 0)
    counts["latched"] = g.ramp_done
    return counts


print("PlateauGrowth known-answer tests\n")

# --- 1. THE HEADLINE: a new area arriving must reach the REGRESSION trigger --------------------------------
print("NEW AREA -- a sustained loss step-up, i.e. material the model has not seen")
c = run(inject=(12000, 13500, 3.1))
print(f"  {c}")
check(c["REGRESSION"] >= 1, "a sustained regression fires the REGRESSION trigger at least once")
check(c["ramp"] == 0, "the ramp is latched off and does not starve it")
check(c["latched"], "the ramp latched (N0=2048 >= FAB_RAMP_TO=0.5 x cap=4096)")

# --- 2. THE CONTROL: no change means no regression, or the trigger is just noise ---------------------------
print("\nSTATIONARY CONTROL -- nothing changes, so REGRESSION must stay at zero")
c0 = run(inject=None)
print(f"  {c0}")
check(c0["REGRESSION"] == 0, "a stationary corpus fires NO regression (no false positives)")
check(c0["refused"] == 0, "and nothing is even detected-then-refused")
check(c0["stall"] > 0, "stall growth still fires, so the machine is not simply inert")

# --- 3. THE REGRESSION THAT USED TO BE SWALLOWED -----------------------------------------------------------
# The defect: a routine STALL sets the shared clock, then a genuine regression arrives inside that cooldown
# and is dropped without ever being tested. Place the injection so a stall has recently fired.
print("\nSUPPRESSION -- a regression arriving inside a stall's cooldown must not be silently dropped")
best = None
for start in range(8000, 16000, 250):
    c = run(inject=(start, start + 1500, 3.1))
    if best is None or c["REGRESSION"] > best[1]["REGRESSION"]: best = (start, c)
    if c["REGRESSION"] == 0 and c["refused"] == 0:
        FAILED.append(f"regression at t={start} vanished entirely (fired 0, refused 0)")
        print(f"  FAIL  regression at t={start} vanished entirely -- fired 0 AND refused 0")
        break
else:
    print(f"  ok    every injection point from 8000..16000 either fired or was COUNTED as refused")

# --- 4. THE BLACKOUT MUST STILL HOLD -----------------------------------------------------------------------
# note_shift() marks a loss jump we caused ourselves (retok / resample). Growing on that is the system
# reacting to its own tokenizer change, and relaxing the regression gate must not have relaxed this one.
print("\nBLACKOUT -- a loss jump WE caused (retok) must not be read as new material")
c = run(inject=(12000, 13500, 3.1), blackout_at=12000)
print(f"  {c}")
check(c["REGRESSION"] == 0, "a regression inside the blackout window fires no growth")

# --- 5. REFUSALS ARE COUNTED, NOT DISCARDED ----------------------------------------------------------------
print("\nACCOUNTING -- a sustained regression re-reads as unexpected and must be counted while refused")
c = run(inject=(12000, 13500, 3.1))
check(c["refused"] > 0, "the sustained regression is refused-and-counted after its first burst")
check(c["REGRESSION"] <= 2, "and the cooldown still bounds it to a burst or two, not one per step")

print()
if FAILED:
    print(f"FAILED {len(FAILED)} check(s):")
    for f in FAILED: print(f"  - {f}")
    sys.exit(1)
print("growth_test: all checks passed")
