"""Monte Carlo check of the seed counts (noncentral t), scratch only."""
import math, random
from power import t_ppf, N

def nct_sf(tc, df, ncp, draws=100000, seed=7):
    rng = random.Random(seed); hit = 0
    for _ in range(draws):
        z = rng.gauss(0, 1); v = rng.gammavariate(df / 2, 2)
        if (z + ncp) / math.sqrt(v / df) > tc: hit += 1
    return hit / draws

def pw(n, M, sd, mu=0.0):
    return nct_sf(t_ppf(0.95, n - 1), n - 1, (M - mu) * math.sqrt(n) / sd)

def n_mc(C, M, sd, mu=0.0, start=3):
    per = 0.8 ** (1 / C)
    n = start
    while pw(n, M, sd, mu) < per:
        n += 1
    return n

eps = 0.05
sds = [("easy", 0.0527), ("cred", 0.0624), ("hard", 0.1279), ("untagged-mean", 0.0445)]
print("5-seed per-component admission power at mu=0 (MC):")
for k, sd in sds:
    p = pw(5, eps, sd)
    print(f"  {k}: {p:.3f}; joint C=4 {p**4:.4f}; C=7 {p**7:.5f}; C=29 {p**29:.2e}")
print("MC seeds for >=80% joint power (independent), mu=0:")
for C in (1, 4, 6, 7, 29):
    out = []
    for k, sd in sds:
        out.append(f"{k}:{n_mc(C, eps, sd, start=5)}")
    print(f"  C={C}: " + "  ".join(out))
