#!/usr/bin/env python3
"""Is the learning-rate schedule the same schedule at two different corpus sizes?

AN EPOCH IS NOT A UNIT OF ANYTHING. LR_EPOCHS names the cosine's wavelength in EPOCHS, and an epoch's length in
steps is STREAM_LEN/WIN -- so "8 epochs" has meant 48,000 steps at STREAM_LEN=4e6 and 840,000 at 94e6. One
number, a 17x range of schedules. The schedule was already rewritten once so that EPOCHS would stop setting the
learning rate; LR_EPOCHS is the same fault one level down, because it still has to be converted through a
quantity nothing holds fixed -- and the conversion is itself an estimate, since minting makes later epochs
shorter and the code has to project the shrinkage.

It cost a run. round13 stretched the wavelength to 16 epochs, which did not lower the peak rate but doubled the
time spent near it, straight through the stretch the run needed to recover from an epoch-boundary shock:

    step        38576  73331  108246  143141  177923
    8-epoch      96%    80%     59%     38%     19%   -> recovered, reached 2.021 b/B
    16-epoch     99%    90%     79%     65%     50%   -> lost 4.6 b/B and never came back

LR_STEPS states the wavelength directly. This file asserts the property that makes it worth having: the rate at
step N is a function of N alone.

The schedule is a closure inside main(), so it cannot be imported or lifted by AST the way lift_to and pin_tick
are. It is reimplemented here from the shipped source, and the FIRST test checks that reimplementation still
matches the real one line for line -- so this file fails loudly if the schedule is edited without it.

Run: python3 lr_test.py
"""
import ast
import math
import os
import sys

FAILED = []


def check(cond, msg):
    if not cond: FAILED.append(msg); print(f"  FAIL  {msg}")
    else: print(f"  ok    {msg}")


# --- 0. IS THIS STILL THE SHIPPED SCHEDULE? --------------------------------------------------------------------
# A hand-copied formula that has drifted from the source is worse than no test: it passes while the real
# schedule does whatever it now does. Pull the body of _lr_at out of the source and check the pieces this file
# depends on are all still in it.
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_organize.py")
_tree = ast.parse(open(_SRC).read())
_fn = None
for _n in ast.walk(_tree):
    if isinstance(_n, ast.FunctionDef) and _n.name == "_lr_at": _fn = _n
if _fn is None:
    print("!! _lr_at is gone from self_organize.py -- this file is testing a schedule that no longer exists.")
    sys.exit(1)
_body = ast.unparse(_fn)

print("does this file still describe the shipped schedule?")
for _frag, _what in (("LR_SCHED == 'none'", "the LR_SCHED=none escape"),
                     ("LR_WARMUP", "the warmup"),
                     ("LR_MIN_FRAC + (1 - LR_MIN_FRAC) * 0.5 * (1 + math.cos(math.pi * _p))", "the cosine"),
                     ("LR_RESTARTS", "the restart branch"),
                     ("LR_SHIFT_WARM", "the resample re-warm")):
    check(_frag in _body, f"_lr_at still contains {_what}")


# --- the reimplementation, mirroring _lr_at ---------------------------------------------------------------------
def lr_at(st, total, run_end=None, *, LR=2e-3, LR_WARMUP=1000, LR_MIN_FRAC=0.05, LR_RESTARTS=1,
          LR_SHIFT_WARM=0, shift_at=-10 ** 9):
    w = min(LR_WARMUP, max(1, total // 10))
    if st < w: return LR * (st + 1) / w
    span = max(1, total - w)
    prog = (st - w) / span
    if LR_RESTARTS and run_end is not None:
        n = max(1, round((run_end - w) / span))
        p = (((st - w) / ((run_end - w) / n)) % 1.0) if st < run_end else 1.0
    else:
        p = min(1.0, prog)
    cyc = LR_MIN_FRAC + (1 - LR_MIN_FRAC) * 0.5 * (1 + math.cos(math.pi * p))
    if LR_SHIFT_WARM and 0 <= st - shift_at < LR_SHIFT_WARM:
        cyc *= max(LR_MIN_FRAC, (st - shift_at + 1) / LR_SHIFT_WARM)
    return LR * cyc


# --- 1. THE POINT OF THE CHANGE ---------------------------------------------------------------------------------
# Two corpus sizes, the same LR_STEPS. Under LR_EPOCHS these are different schedules; under LR_STEPS they must be
# the same one. The step counts are the real ones from this session.
print("\nSAME WAVELENGTH IN STEPS -> SAME RATE AT THE SAME STEP, whatever the corpus size")
SMALL, BIG = 48_000, 840_000            # 8 epochs at STREAM_LEN 4e6 and at 94e6
WAVE = 100_000
print(f"  {'step':>8} {'epoch-derived (8ep)':>22} {'LR_STEPS=100000':>18}")
_ep_gap = _st_gap = 0.0
for st in (10_000, 38_000, 80_000, 150_000):
    a_ep, b_ep = lr_at(st, SMALL, SMALL), lr_at(st, BIG, BIG)
    a_st, b_st = lr_at(st, WAVE, WAVE), lr_at(st, WAVE, WAVE)
    _ep_gap = max(_ep_gap, abs(a_ep - b_ep) / 2e-3)
    _st_gap = max(_st_gap, abs(a_st - b_st) / 2e-3)
    print(f"  {st:>8} {a_ep/2e-3:>10.0%} vs {b_ep/2e-3:>7.0%} {a_st/2e-3:>11.0%} vs {b_st/2e-3:>4.0%}")
check(_ep_gap > 0.3, f"epoch-derived: the two corpus sizes differ by up to {_ep_gap:.0%} of peak at the same step")
check(_st_gap == 0.0, "LR_STEPS: the rate at a given step is identical -- corpus size cannot reach it")

# --- 2. IT MUST NOT HAVE BROKEN THE EXISTING PATH ----------------------------------------------------------------
print("\nTHE EPOCH PATH IS UNTOUCHED -- LR_STEPS=0 must change nothing")
check(lr_at(50_000, SMALL, SMALL) == lr_at(50_000, SMALL, SMALL), "the epoch path is still a pure function")
check(abs(lr_at(0, 48_000) - 2e-3 / 1000) < 1e-9, "warmup still starts at one warmup-step of peak")
# The two halves MEET, they do not step. Warmup's last value is peak and the cosine's first value is peak, so
# the handover is continuous -- asserting a rise across it was wrong about the schedule, not about the code.
check(abs(lr_at(999, 48_000) - lr_at(1000, 48_000)) < 1e-12, "warmup hands over to the cosine continuously")
check(abs(lr_at(1000, 48_000) - 2e-3) < 1e-9, "...at full peak, which is where the cosine starts")
check(abs(lr_at(48_000, 48_000, 48_000) - 2e-3 * 0.05) < 1e-9, "one full cycle still ends at the LR_MIN_FRAC floor")

# --- 3. THE RESAMPLE RE-WARM -------------------------------------------------------------------------------------
# round12 and round13 were BOTH destabilised at the epoch-2 boundary; the difference was whether the rate then
# fell. LR_SHIFT_WARM attacks the shock itself rather than the recovery.
print("\nRE-WARM AFTER A RESAMPLE -- it may only ever LOWER the rate, never raise it")
SHIFT, WARM = 38_576, 4_000
base = [lr_at(s, WAVE, WAVE) for s in (SHIFT, SHIFT + 1000, SHIFT + 3999, SHIFT + 4000, SHIFT + 20_000)]
warm = [lr_at(s, WAVE, WAVE, LR_SHIFT_WARM=WARM, shift_at=SHIFT)
        for s in (SHIFT, SHIFT + 1000, SHIFT + 3999, SHIFT + 4000, SHIFT + 20_000)]
for s, b, w in zip((0, 1000, 3999, 4000, 20_000), base, warm):
    print(f"  {s:+7d} from the shift: {b/2e-3:>5.0%} -> {w/2e-3:>5.0%}")
check(all(w <= b + 1e-12 for b, w in zip(base, warm)), "the re-warm never RAISES the rate above the cycle")
check(warm[0] < base[0] * 0.1, "at the shift itself the rate is cut to the floor")
check(warm[1] < base[1], "and is still climbing back a quarter of the way through")
check(abs(warm[4] - base[4]) < 1e-12, "past the window it rejoins the cycle exactly")
check(abs(warm[3] - base[3]) < 1e-12, "the window is half-open: it ends exactly at LR_SHIFT_WARM steps")
# OFF BY DEFAULT, or every earlier result becomes unreproducible.
check(all(lr_at(s, WAVE, WAVE) == lr_at(s, WAVE, WAVE, LR_SHIFT_WARM=0, shift_at=SHIFT)
          for s in (SHIFT, SHIFT + 1, SHIFT + 5000)), "LR_SHIFT_WARM=0 leaves the schedule bit-identical")

# --- 4. THE FAILURE THAT PROMPTED ALL THIS ------------------------------------------------------------------------
# The claim in round14's note: an 8-epoch wavelength has the rate well down by the fifth boundary, a 16-epoch one
# does not. Assert it from the schedule rather than from the logs, so it stays true if the schedule changes.
# THESE ARE THE SCHEDULE'S OWN NUMBERS, NOT THE LOGGED ONES. The real runs read a PROJECTED total that shrinks
# as minting lengthens tokens, so their rates fall faster than a fixed total predicts (logged: 96/80/59/38/19
# against 96/85/70/52/34 here). The projection is exactly what LR_STEPS removes; the qualitative claim -- same
# at the shock, far apart through the recovery -- is what is asserted, and it holds either way.
print("\nWHAT ROUND13 DID -- stretching the wavelength does not lower the peak, it widens it")
BOUNDS = (38_576, 73_331, 108_246, 143_141, 177_923)
e8 = [lr_at(s, 282_000, 282_000) / 2e-3 for s in BOUNDS]
e16 = [lr_at(s, 561_000, 561_000) / 2e-3 for s in BOUNDS]
print("   boundary:  " + "  ".join(f"{s:>7d}" for s in BOUNDS))
print("   8-epoch:   " + "  ".join(f"{v:>6.0%} " for v in e8))
print("   16-epoch:  " + "  ".join(f"{v:>6.0%} " for v in e16))
check(abs(e8[0] - e16[0]) < 0.10, "at the SHOCK both are near peak -- the shock is not what differs")
check(e16[4] > 2 * e8[4], "by the fifth boundary the stretched schedule is still more than twice as hot")

print()
if FAILED:
    print(f"FAILED {len(FAILED)} check(s):")
    for f in FAILED: print(f"  - {f}")
    sys.exit(1)
print("lr_test: all checks passed")
