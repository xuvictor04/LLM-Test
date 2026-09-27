"""Arithmetic for the O11-O15 revision (scratch only; pure Python + power.py helpers)."""
import math, random, statistics
from power import t_ppf, power_comp, nct_sf, N

eps = 0.05
print("== O13: WORLD re-run (6.5) power ==")
# Fleet paired SEs (5 seeds) -> SDs. ANALYSIS.txt / note WORLD 5.
for name, se in (("world_off-fb_off full run", 0.0114), ("world_off-fb_off last half", 0.0016),
                 ("fb_on-fb_off full run", 0.0101), ("fb_on-fb_off last half", 0.0031)):
    sd = se * math.sqrt(5)
    print(f"  {name}: SE {se} -> SD {sd:.4f}")
sd_fleet = 0.0114 * math.sqrt(5)
hw5 = t_ppf(0.95, 4) * sd_fleet / math.sqrt(5)
print(f"  UB half-width at 5 seeds, SD {sd_fleet:.4f}: {hw5:.4f}")
print(f"  admission power at 5 seeds, 1 comp, SD {sd_fleet:.4f}: {nct_sf(t_ppf(0.95,4),4,eps*math.sqrt(5)/sd_fleet,draws=100000):.3f}")
p1 = nct_sf(t_ppf(0.95, 4), 4, eps * math.sqrt(5) / sd_fleet, draws=100000)
print(f"  joint over 4 areas at that SD (independent): {p1**4:.3f}")

def n_joint(C, sd, target=0.8, mu=0.0, nmax=400):
    per = target ** (1 / C)
    for n in range(3, nmax):
        if power_comp(n, eps, sd, mu) >= per:
            return n
for sd in (sd_fleet, 0.0445, 0.0527, 0.0624, 0.1279):
    print(f"  seeds for >=80% joint power over 4 areas at SD {sd:.4f}: {n_joint(4, sd)}; single comp {n_joint(1, sd)}")

# Detection power: true cost c in one area, test point>eps and one-sided t at alpha 0.0125
def det_power(n, sd, true, alpha=0.0125, draws=40000, seed=3):
    rng = random.Random(seed); tc = t_ppf(1 - alpha, n - 1); hit = 0
    for _ in range(draws):
        xs = [rng.gauss(true, sd) for _ in range(n)]
        m = sum(xs) / n; s = statistics.stdev(xs)
        if m > eps and m / (s / math.sqrt(n)) > tc:
            hit += 1
    return hit / draws
for sd in (sd_fleet, 0.0527, 0.0624):
    for n in (5, 10):
        print(f"  detect cost 2eps (0.10) in one area, SD {sd:.4f}, n {n}: {det_power(n, sd, 0.10):.3f}; "
              f"false detect at true 0: {det_power(n, sd, 0.0):.4f}; at true eps: {det_power(n, sd, 0.05):.3f}")

print("\n== O14: the S0b ship rule's operating characteristics (simulation) ==")
# Model: each run's bpb = seed effect + run noise tau (iid). k0, k0_nuis, k3000, k1000 per seed.
# M = max_s |k0 - nuis|; c ships iff (c - k0) <= M at every seed.
def ship_oc(n, d3, d1, draws=100000, seed=11):
    rng = random.Random(seed)
    ship3 = ship1 = none = 0
    for _ in range(draws):
        k0 = [rng.gauss(0, 1) for _ in range(n)]
        nu = [rng.gauss(0, 1) for _ in range(n)]
        c3 = [rng.gauss(d3, 1) for _ in range(n)]
        c1 = [rng.gauss(d1, 1) for _ in range(n)]
        M = max(abs(a - b) for a, b in zip(k0, nu))
        s3 = all(c - a <= M for c, a in zip(c3, k0))
        s1 = all(c - a <= M for c, a in zip(c1, k0))
        ship3 += s3; ship1 += s1; none += (not s3 and not s1)
    return ship3 / draws, ship1 / draws, none / draws
for n in (3, 6):
    for d in (0.0, 1.0, 2.0):
        s3, s1, nn = ship_oc(n, d, d)
        print(f"  n={n} true harm {d} x run-noise SD (both cadences): P(3000 passes) {s3:.3f}  P(none ships) {nn:.3f}")

# Confirmation test for the none-ships branch: one-sided paired t on (c - k0) > 0 at alpha 0.025
# (Holm over 2 cadences, the smaller p), n = 6, true harm 0 and 1 x SD_diff
def conf_power(n, d_over_sd_diff, alpha=0.025, draws=40000, seed=5):
    rng = random.Random(seed); tc = t_ppf(1 - alpha, n - 1); hit = 0
    for _ in range(draws):
        xs = [rng.gauss(d_over_sd_diff, 1) for _ in range(n)]
        m = sum(xs) / n; s = statistics.stdev(xs)
        hit += (m / (s / math.sqrt(n)) > tc)
    return hit / draws
for n in (6,):
    for d in (0.0, 1.0, 1.5):
        print(f"  confirmation t (alpha 0.025), n={n}, harm {d} x SD of the paired diff: P(confirmed) {conf_power(n, d):.3f}")

print("\n== O14: E2 held-out re-read at margin eps ==")
for n in (3,):
    for sd in (0.0527, 0.0624, 0.1279):
        hw = t_ppf(0.95, n - 1) * sd / math.sqrt(n)
        print(f"  3 seeds, SD {sd}: UB half-width {hw:.4f} (t_0.95,2 = {t_ppf(0.95,2):.3f})")

print("\n== O11: wall share of the floor cadence as the probe grows ==")
# m/t at 6 windows per area: 7.2% forward windows x forward-cost factor
for label, base in (("forward = 1/3 step", 0.072 / 3), ("toy wall basis 4.3/15", 0.072 * 4.3 / 15)):
    for w in (0.02, 0.10, 0.50):
        # w = x/(1+x), x = base * r -> r = w/((1-w) base)
        r = w / ((1 - w) * base)
        print(f"  {label}: m/t per unit r = {base:.4f}; w_F = {w:.0%} at r = {r:.2f} (probe {6*r:.0f} windows per area)")
print("  C03 cadence reads per 6000 windows at 333:", round(6000 / 333, 1), "; stamp-aligned: 2 x 4 =", 8)
print("  throughput 1 - w_F at w_F 0.10 / 0.50:", 0.9, 0.5)
