#!/usr/bin/env python3
"""Does the run know how long it is going to be?

The LR horizon has been wrong twice, and both times the symptom was the same: the cosine was stretched over a
horizon the run never reached, so it never annealed and the loss rose after its own minimum.

  1. `_total_steps = EPOCHS * (tokens // WIN)`, measured ONCE at the seed vocabulary. Minted tokens are longer,
     so later epochs cover the same bytes in fewer steps. Measured 31-40% high; `_proj_steps` fixed that.
  2. The residual, which this file exists for: `_proj_steps` priced every REMAINING epoch at the CURRENT
     epoch's length. Minting does not stop, so later epochs are shorter than the one being measured, and the
     estimate is high by construction at every step of the run.

The evidence for (2) is the `curve` column of round4 -- how far a run rises after its own minimum. It separates
perfectly on whether the vocabulary was FIXED:

    frozen2k  fixed at 2048 (TOK_MINT_UNTIL)                curve +0.000
    growcap   fixed at 1024 (a soft cap that never lifted)  curve +0.000
    base      grows to 2048                                 curve +0.285
    rescue    grows to 2048                                 curve +0.286
    ecw       grows to 2048                                 curve +0.401
    mask      grows to 2048                                 curve +0.430

Two different mechanisms, one intermediate state -- a vocabulary that stops moving -- and the same result. A
fixed vocabulary is exactly the case where this projection is already exact, which is the whole of what it was
doing for those arms.

Run: python3 proj_test.py
"""
import os
import sys

# LOADED FROM THE SHIPPED SOURCE, not imported and not re-typed. proj_arith is pure arithmetic, but importing
# self_organize drags in torch, and a test of a pure function should not be unrunnable because a GPU library is
# missing -- this container has been through several rebuilds where it was. Lifting the function out of the file
# by AST keeps the thing under test as THE SHIPPED TEXT, which is the property that matters: a re-typed copy in
# the test would pass happily while the real code was wrong.
import ast

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_organize.py")
_tree = ast.parse(open(_SRC).read())
_fn = next((n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == "proj_arith"), None)
if _fn is None:
    print("!! proj_arith is not a module-level function in self_organize.py -- it was hoisted there so this "
          "test could exercise the shipped code; if it moved back into a closure, this test is testing nothing.")
    sys.exit(1)
_ns = {}
exec(compile(ast.Module(body=[_fn], type_ignores=[]), _SRC, "exec"), _ns)
proj_arith = _ns["proj_arith"]

FAILED = []


def check(cond, msg):
    if not cond: FAILED.append(msg); print(f"  FAIL  {msg}")
    else: print(f"  ok    {msg}")


def flat(step, horizon, epoch, ep_start, per):
    """The OLD formula, kept so the improvement is measured rather than asserted."""
    return max(step + 1, ep_start + (horizon - epoch) * per)


def shrinking(n, first=10000, ratio=0.9):
    lens = [first]
    for _ in range(n - 1): lens.append(int(lens[-1] * ratio))
    return lens


print("proj_arith known-answer tests\n")

# --- 1. A RUN WHOSE EPOCHS SHRINK: the case the whole file is about -----------------------------------------
EP = 8
true_lens = shrinking(EP)
TRUE = sum(true_lens)
print(f"SHRINKING RUN -- 8 epochs, each 10% shorter than the last, true total {TRUE} steps")
worst_new, worst_old = 0.0, 0.0
for ep in range(EP):
    spent = sum(true_lens[:ep]); per = true_lens[ep]
    old = flat(spent, EP, ep, spent, per)
    new = proj_arith(spent, EP, ep, spent, per, true_lens[:ep])
    e_old, e_new = old / TRUE - 1, new / TRUE - 1
    worst_old = max(worst_old, abs(e_old)); worst_new = max(worst_new, abs(e_new))
    print(f"  epoch {ep}: OLD {old:6d} ({e_old:+.1%})   NEW {new:6d} ({e_new:+.1%})")
# From two completed epochs on, the ratio is estimable and the projection should be essentially exact.
for ep in range(2, EP):
    spent = sum(true_lens[:ep])
    new = proj_arith(spent, EP, ep, spent, true_lens[ep], true_lens[:ep])
    check(abs(new / TRUE - 1) < 0.02, f"epoch {ep}: projection within 2% of the true end ({new} vs {TRUE})")
# HONEST ABOUT WHERE THE FIX DOES NOT REACH. Epochs 0 and 1 have no completed pair to estimate a ratio from,
# so they fall back to the flat formula and are UNIMPROVED -- the worst-case error is identical. The assertion
# here was originally "worst error improved" and it failed, correctly. Weakening a fix's test until it passes is
# how a fix comes to look bigger than it is, so the checks now measure what actually changed: everything from
# epoch 2 on, and the average across the run. The projection is monotone non-increasing, so once epoch 2
# corrects it the value is latched and the early overestimate cannot come back.
early_old = [abs(flat(sum(true_lens[:e]), EP, e, sum(true_lens[:e]), true_lens[e]) / TRUE - 1) for e in (0, 1)]
early_new = [abs(proj_arith(sum(true_lens[:e]), EP, e, sum(true_lens[:e]), true_lens[e], true_lens[:e]) / TRUE - 1)
             for e in (0, 1)]
check(early_new == early_old, f"epochs 0-1 are UNCHANGED by design ({early_old[0]:.1%}) -- no ratio to estimate yet")
late_old = [abs(flat(sum(true_lens[:e]), EP, e, sum(true_lens[:e]), true_lens[e]) / TRUE - 1) for e in range(2, EP)]
late_new = [abs(proj_arith(sum(true_lens[:e]), EP, e, sum(true_lens[:e]), true_lens[e], true_lens[:e]) / TRUE - 1)
            for e in range(2, EP)]
check(max(late_new) < 0.02 <= max(late_old),
      f"epoch 2 onward: worst error {max(late_old):.1%} -> {max(late_new):.1%}")
check(sum(late_new) / len(late_new) < sum(late_old) / len(late_old) / 10,
      f"epoch 2 onward: mean error {sum(late_old)/len(late_old):.1%} -> {sum(late_new)/len(late_new):.2%}")

# --- 2. A RUN THAT DOES NOT SHRINK must be unchanged --------------------------------------------------------
# A frozen vocabulary re-tokenizes to the same length every epoch. The old formula was already exact there, so
# the fix must not perturb it -- otherwise it trades one bias for another.
print("\nFIXED VOCABULARY -- every epoch the same length; the old formula was already exact here")
flat_lens = [10000] * EP
for ep in (0, 2, 5):
    spent = ep * 10000
    old = flat(spent, EP, ep, spent, 10000)
    new = proj_arith(spent, EP, ep, spent, 10000, flat_lens[:ep])
    check(new == old == EP * 10000, f"epoch {ep}: unchanged and exact ({new})")

# --- 3. GUARDS ----------------------------------------------------------------------------------------------
print("\nGUARDS")
# Never predict the past: the horizon must always be at least one step ahead.
check(proj_arith(999, 1, 0, 0, 10, []) > 999, "never projects an end at or before the current step")
# One completed epoch is not enough to estimate a ratio from; it must fall back, not invent one.
check(proj_arith(10000, EP, 1, 10000, 9000, [10000]) == flat(10000, EP, 1, 10000, 9000),
      "one completed epoch falls back to the flat projection")
# A ratio above 1 would predict epochs getting LONGER, which minting cannot do. Clamp it.
grow = proj_arith(20000, EP, 2, 20000, 10000, [8000, 10000])
check(grow == flat(20000, EP, 2, 20000, 10000), "a >1 ratio is clamped, so epochs are never projected to grow")
# And a collapse far past anything observed must not drive the horizon to nothing.
crash = proj_arith(20000, EP, 2, 20000, 10000, [10000, 1000])
check(crash > 20000 + 10000, f"a 10x collapse is clamped at 0.5, not believed ({crash})")
# The LR wavelength uses a DIFFERENT horizon from the ETA; a shorter one must project shorter.
check(proj_arith(0, 4, 0, 0, 10000, []) < proj_arith(0, 8, 0, 0, 10000, []),
      "a shorter horizon (LR_EPOCHS) projects a shorter end than EPOCHS")

print()
if FAILED:
    print(f"FAILED {len(FAILED)} check(s):")
    for f in FAILED: print(f"  - {f}")
    sys.exit(1)
print("proj_test: all checks passed")
