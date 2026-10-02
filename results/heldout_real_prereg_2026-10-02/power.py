"""Register §8 6.3b's arithmetic for O16's CONFIRM, by the eps rule's own t (gpu_world.sh's block between its markers),
at LOOK_ALPHA, the level 6.3a reads each of its two looks at (the 7 seeds; a top-up's pooled 11, where O14's reading of
S against k0 is UNRESOLVED). O14's own cells at K=1 are results/heldout_prereg_2026-10-02/power.out's first columns.

(1) THE CELLS, arithmetic. CONFIRM needs the one-sided upper bound of the time-integrated all-area report gap,
S_replay - S, below 0: mean + t(1 - a, n - 1) x sd / sqrt(n) < 0. Each cell is the per-seed SD at which that bound,
taken at a true gain g with s = sd, just touches 0 (about 50% power), for g = 0.01, 0.02 and 0.05 bits/byte.
(2) THE ERROR OVER THE TWO LOOKS, simulated: a null 'replay' (no true gain), the area condition taken as met (the worst
case), read at 7 seeds and again over the pooled 11 (a top-up taken every time, the worst case), at 0.05 a look and at
LOOK_ALPHA a look; and a true gain of 0.92 per-seed SDs, CONFIRMed at 7 and by 11. The SD's scale does not enter.

    python3 power.py [path/to/gpu_world.sh]        # from any directory but a checkout's root
"""
import math
import os
import random
import re
import sys

src = open(sys.argv[1] if len(sys.argv) > 1 else
           os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "gpu_world.sh"), encoding="utf-8").read()
exec(re.search(r"^# >>> THE ε RULE.*?^# <<< THE ε RULE$", src, re.M | re.S).group(0))
LOOK = float(re.search(r"^LOOK_ALPHA = ([\d.]+)", src, re.M).group(1))

print(f"(1) the per-seed SD of the time-integrated gap at which a true gain g CONFIRMs at about 50% (one look), "
      f"a = {LOOK:g} a look")
print("n  | g 0.01 / 0.02 / 0.05")
for n in range(3, 12):
    tq = t_quantile(1 - LOOK, n - 1)
    print(f"{n:2d} | " + " / ".join(f"{g * math.sqrt(n) / tq:.4f}" for g in (0.01, 0.02, 0.05)))

DRAWS = 200000


def confirm(xs, a):
    n = len(xs)
    m = sum(xs) / n
    se = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n)
    return m + t_quantile(1 - a, n - 1) * se < 0


def procedure(gain, a, seed):
    """(CONFIRM at 7, CONFIRM at 7 or over the pooled 11), the share of draws; per-seed SD 1."""
    rnd = random.Random(seed)
    q7, q11 = t_quantile(1 - a, 6), t_quantile(1 - a, 10)
    c7 = c = 0
    for _ in range(DRAWS):
        xs = [rnd.gauss(-gain, 1.0) for _ in range(11)]
        m7, m11 = sum(xs[:7]) / 7, sum(xs) / 11
        s7 = math.sqrt(sum((x - m7) ** 2 for x in xs[:7]) / 6 / 7)
        s11 = math.sqrt(sum((x - m11) ** 2 for x in xs) / 10 / 11)
        h7 = m7 + q7 * s7 < 0
        c7 += h7
        c += h7 or m11 + q11 * s11 < 0
    return c7 / DRAWS, c / DRAWS


print()
print(f"(2) O16 over the two looks (7 seeds, then the pooled 11), {DRAWS:,} draws a row, per-seed SD 1")
print("a look | null 'replay': CONFIRM at 7, by 11 | gain 0.92 SD: CONFIRM at 7, by 11")
for a in (0.05, LOOK):
    n0, g0 = procedure(0.0, a, 1), procedure(0.92, a, 2)
    print(f"{a:<6g} | {n0[0]:>26.4f}, {n0[1]:.4f} | {g0[0]:>25.3f}, {g0[1]:.3f}")
