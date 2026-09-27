"""O14 Step 1 confirmation OC with both conditions (mean d > Mbar, one-sided t at alpha), scratch."""
import math, random, statistics
from power import t_ppf
def oc(n, harm_run_sd, alpha, draws=60000, seed=21):
    # run noise SD 1; paired-diff SD sqrt(2); harm in units of the paired-diff SD
    rng = random.Random(seed); tc = t_ppf(1 - alpha, n - 1); hit = 0
    h = harm_run_sd * math.sqrt(2)
    for _ in range(draws):
        k0 = [rng.gauss(0, 1) for _ in range(n)]
        nu = [rng.gauss(0, 1) for _ in range(n)]
        c = [rng.gauss(h, 1) for _ in range(n)]
        d = [a - b for a, b in zip(c, k0)]
        mbar = sum(abs(a - b) for a, b in zip(k0, nu)) / n
        m = sum(d) / n; s = statistics.stdev(d)
        hit += (m > mbar and m / (s / math.sqrt(n)) > tc)
    return hit / draws
for hs in (0.0, 1.0, 1.5, 2.0):
    print(f"n=6 harm {hs} x paired-diff SD: P(confirmed) alpha .025 = {oc(6, hs, 0.025):.3f}; alpha .05 = {oc(6, hs, 0.05):.3f}")
