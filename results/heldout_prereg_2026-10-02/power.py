"""Register §8 6.3a's seed arithmetic, by the eps rule's own t (gpu_world.sh's block between its markers), at the
level each of its two looks is read at -- LOOK_ALPHA, 0.025: the 7 seeds, then the pooled 11 where they are
UNRESOLVED, Bonferroni over the two (2026-10-02) -- with 0.05 a look, the level first registered, beside it.

(1) THE CELLS, arithmetic. FAIL needs the lower bound mean - t(1 - a/(K x 4), n - 1) x sd / sqrt(n) above eps (a
Bonferroni split over the 4 areas, Holm's first level a/K across the K act arms); PASS needs mean + t(1 - a, n - 1)
x sd / sqrt(n) at most eps. Each cell is the per-seed SD at which that bound, taken at the true mean with s = sd,
just touches eps: about 50% power, and for ONE area.
(2) THE ARM, simulated. One act arm, its four areas at the per-seed SDs the register cites (num 0.023 and c 0.046,
results/gpu_retok_2026-09-28/verify/j_main.out's phase-4 cells; eng and py, which no phase-4 cell reads, taken as
0.02), read at 7 seeds and, where UNRESOLVED, over the pooled 11, as the fleet and its top-up read k<c> (FAIL at
Holm's first level of two): a null arm, num at +0.10, and num at eps exactly, where a PASS is the error each look's
level bounds -- by 0.05 over the two looks at 0.025 a look, and not at 0.05.

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
eps = 0.05

print(f"(1) the per-seed SD at which the bound, at the true mean with s = sd, touches eps (about 50% power, one area), "
      f"a = {LOOK:g} a look")
print("n  | FAIL of +0.09 / +0.10 / +0.11 at K=1 | K=2 | K=3 || PASS of true 0 / +0.02")
for n in range(3, 12):
    row = []
    for K in (1, 2, 3):
        tq = t_quantile(1 - LOOK / K / 4, n - 1)
        row.append(" ".join(f"{(m - eps) * math.sqrt(n) / tq:.4f}" for m in (0.09, 0.10, 0.11)))
    tp = t_quantile(1 - LOOK, n - 1)
    print(f"{n:2d} | " + " | ".join(row) + f" || {eps * math.sqrt(n) / tp:.4f} / {(eps - 0.02) * math.sqrt(n) / tp:.4f}")

SD = {"eng": 0.02, "py": 0.02, "num": 0.023, "c": 0.046}
DRAWS = 100000
LEVELS = (0.05, LOOK)
# The quantiles, once per look and level: FAIL at Holm's first level of two arms (a/2), over the 4 areas.
Q = {(n, a): (t_quantile(1 - a / 2 / 4, n - 1), t_quantile(1 - a, n - 1)) for n in (7, 11) for a in LEVELS}


def verdict(stats, n, a):
    tf, tp = Q[(n, a)]
    if any(m - tf * se > eps for m, se in stats):
        return "FAIL"
    return "PASS" if all(m + tp * se <= eps for m, se in stats) else "UNRESOLVED"


def ms(xs):
    n = len(xs)
    m = sum(xs) / n
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n)


def arm(num_mean, seed):
    """{(level, verdict + '7' at 7 seeds, or verdict over the procedure): the share of draws}; the same draws at
    every level."""
    rnd = random.Random(seed)
    cnt = {(a, k): 0 for a in LEVELS for k in ("PASS7", "PASS", "FAIL7", "FAIL")}
    for _ in range(DRAWS):
        xs = [[rnd.gauss(num_mean if ar == "num" else 0.0, sd) for _ in range(11)] for ar, sd in SD.items()]
        s7, s11 = [ms(x[:7]) for x in xs], [ms(x) for x in xs]
        for a in LEVELS:
            v = verdict(s7, 7, a)
            f = v if v != "UNRESOLVED" else verdict(s11, 11, a)
            cnt[(a, v + "7")] = cnt.get((a, v + "7"), 0) + 1
            cnt[(a, f)] = cnt.get((a, f), 0) + 1
    return {k: v / DRAWS for k, v in cnt.items()}


print()
print(f"(2) one act arm over the procedure (7 seeds; the pooled 11 where UNRESOLVED), per-seed SD "
      + " ".join(f"{k} {v:g}" for k, v in SD.items()) + f", {DRAWS:,} draws a row")
print("a look | null arm: PASS at 7, by 11 | num +0.10: FAIL at 7, by 11 | num at eps, both errors: PASS by 11, FAIL by 11")
r0, r1, re_ = arm(0.0, 1), arm(0.10, 2), arm(eps, 3)
for a in LEVELS:
    print(f"{a:<6g} | {r0[(a, 'PASS7')]:>16.3f}, {r0[(a, 'PASS')]:.3f} | {r1[(a, 'FAIL7')]:>17.3f}, {r1[(a, 'FAIL')]:.3f} | "
          f"{re_[(a, 'PASS')]:>36.4f}, {re_[(a, 'FAIL')]:.4f}")
