"""Register §8 6.3a's seed arithmetic, by the eps rule's own t (gpu_world.sh's block between its markers).

FAIL needs the lower bound mean - t(1 - a/(K x 4), n - 1) x sd / sqrt(n) above eps, a Bonferroni split over
the 4 areas with Holm's first level a/K across the K act arms; PASS needs mean + t(0.95, n - 1) x sd / sqrt(n)
at most eps. Each cell is the largest per-seed SD of the paired difference at which a true mean of the given
size resolves (arithmetic; no run).

    python3 power.py [path/to/gpu_world.sh]
"""
import math
import re
import sys

src = open(sys.argv[1] if len(sys.argv) > 1 else "/home/user/LLM-Test/gpu_world.sh", encoding="utf-8").read()
exec(re.search(r"^# >>> THE ε RULE.*?^# <<< THE ε RULE$", src, re.M | re.S).group(0))
eps = 0.05
print("n  | max sd for FAIL of +0.09 / +0.10 / +0.11 at K=1 | K=2 | K=3 || max sd for PASS of true 0 / +0.02")
for n in range(3, 12):
    row = []
    for K in (1, 2, 3):
        tq = t_quantile(1 - 0.05 / K / 4, n - 1)
        row.append(" ".join(f"{(m - eps) * math.sqrt(n) / tq:.4f}" for m in (0.09, 0.10, 0.11)))
    tp = t_quantile(0.95, n - 1)
    print(f"{n:2d} | " + " | ".join(row) + f" || {eps * math.sqrt(n) / tp:.4f} / {(eps - 0.02) * math.sqrt(n) / tp:.4f}")
