"""Power arithmetic for the O6-O10 revision (pure Python; scratch only).

Admission (non-inferiority) per component: admit when mean + t_{0.95,n-1} * sd/sqrt(n) < M.
Power at true regression mu: P( T_{n-1, (M-mu)sqrt(n)/sd} > t_{0.95,n-1} ), noncentral t.
Joint power over C independent components = product (a conservative lower bound; positively
correlated components do better).
"""
import math, random, statistics

N = statistics.NormalDist()

def betacf(a, b, x, itmax=300, eps=3e-14):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(c) > 1e-300 else 1e300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(c) > 1e-300 else 1e300
        de = d * c; h *= de
        if abs(de - 1.0) < eps:
            break
    return h

def betai(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * betacf(a, b, x) / a
    return 1.0 - bt * betacf(b, a, 1 - x) / b

def t_cdf(t, df):
    x = df / (df + t * t)
    p = 0.5 * betai(df / 2, 0.5, x)
    return 1 - p if t > 0 else p

def t_ppf(p, df):
    lo, hi = -50.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def nct_sf(tc, df, ncp, draws=200000, seed=1):
    """P(T' > tc) for noncentral t by Monte Carlo (Z+ncp)/sqrt(chi2/df)."""
    rng = random.Random(seed)
    hit = 0
    for _ in range(draws):
        z = rng.gauss(0, 1)
        v = sum(rng.gauss(0, 1) ** 2 for _ in range(df)) if df <= 30 else rng.gammavariate(df / 2, 2)
        if (z + ncp) / math.sqrt(v / df) > tc:
            hit += 1
    return hit / draws

def nct_sf_fast(tc, df, ncp):
    # Johnson-Welch style normal approximation to the noncentral t tail.
    # P(T' > tc) ~ Phi( (ncp - tc) / sqrt(1 + tc^2/(2 df)) )
    return N.cdf((ncp - tc) / math.sqrt(1 + tc * tc / (2 * df)))

def power_comp(n, margin, sd, mu=0.0, fast=True):
    df = n - 1
    tc = t_ppf(0.95, df)
    ncp = (margin - mu) * math.sqrt(n) / sd
    return (nct_sf_fast if fast else nct_sf)(tc, df, ncp)

def n_needed(C, margin, sd, target=0.8, mu=0.0, nmax=400):
    per = target ** (1.0 / C)
    for n in range(3, nmax + 1):
        if power_comp(n, margin, sd, mu) >= per:
            return n
    return None

if __name__ == "__main__":
    eps = 0.05
    print("t_{0.95,4} =", round(t_ppf(0.95, 4), 3), " t_{0.95,9} =", round(t_ppf(0.95, 9), 3),
          " t_{0.95,19} =", round(t_ppf(0.95, 19), 3))
    sds = {"easy 0.0527": 0.0527, "cred 0.0624": 0.0624, "hard 0.1279": 0.1279,
           "untagged all-area 0.0445": 0.0445, "E1 TI gap 0.0306": 0.0306}
    print("\n5-seed per-component power to admit a zero-regression arm at margin eps=0.05")
    for k, sd in sds.items():
        pf = power_comp(5, eps, sd)
        pm = nct_sf(t_ppf(0.95, 4), 4, eps * math.sqrt(5) / sd, draws=100000)
        print(f"  {k:28s} normal-approx {pf:.3f}  MonteCarlo {pm:.3f}  UB half-width {t_ppf(0.95,4)*sd/math.sqrt(5):.4f}")
    print("\nSeeds needed for >=80% JOINT power (independent components) at mu=0, margin eps")
    for C in (1, 4, 6, 7, 14, 29):
        row = []
        for k, sd in list(sds.items())[:4]:
            row.append(f"{k.split()[0]}:{n_needed(C, eps, sd)}")
        print(f"  C={C:2d} per-comp power {0.8**(1/C):.4f} ->", "  ".join(row))
    print("\nSame at mu = eps/2 (a benign arm that regresses by 0.025)")
    for C in (1, 4, 7):
        row = []
        for k, sd in list(sds.items())[:4]:
            row.append(f"{k.split()[0]}:{n_needed(C, eps, sd, mu=0.025)}")
        print(f"  C={C:2d} ->", "  ".join(row))
    # 5-seed joint power at C components, easy SD
    print("\n5-seed joint power (independent) at mu=0:")
    for C in (4, 7, 29):
        print(f"  C={C}: easy {power_comp(5,eps,0.0527)**C:.4f} cred {power_comp(5,eps,0.0624)**C:.5f} hard {power_comp(5,eps,0.1279)**C:.2e}")
    # False FAIL (point estimate >= margin) at powered n for zero-regression arm
    print("\nP(point estimate >= eps | mu=0) per component = Phi(-eps*sqrt(n)/sd)")
    for (C, sd) in ((29, 0.0527), (29, 0.0624), (4, 0.0527), (4, 0.1279)):
        n = n_needed(C, eps, sd)
        p = N.cdf(-eps * math.sqrt(n) / sd)
        print(f"  C={C} sd={sd} n={n}: per comp {p:.2e}, any of C {1-(1-p)**C:.2e}")
    # O8 tie-read: P(tie | retention worse by eps on TI gap) at 5 seeds, SD 0.0306
    sd = 0.042 * math.sqrt(5) / (t_ppf(0.95, 4) + t_ppf(0.80, 4))
    print("\nE1 TI-gap SD implied by MDE 0.042 at 5 seeds (t_{.95,4}+t_{.80,4}):", round(sd, 4),
          " (t_{.80,4} =", round(t_ppf(0.8, 4), 3), ")")
    se = sd / math.sqrt(5)
    crit = t_ppf(0.95, 4) * se
    print("  significance threshold on mean diff:", round(crit, 4))
    # P(not significant | true diff = eps) via noncentral t
    ptie = 1 - nct_sf(t_ppf(0.95, 4), 4, 0.05 / se, draws=100000)
    print("  P(reads as tie | retention worse by eps=0.05):", round(ptie, 3))
    ptie2 = 1 - nct_sf(t_ppf(0.95, 4), 4, 0.042 / se, draws=100000)
    print("  P(reads as tie | worse by 0.042):", round(ptie2, 3))
    # Holm over 4 comparisons alpha levels
    print("\nHolm levels over 4 pairwise comparisons: ", [round(0.05 / (4 - i), 4) for i in range(4)])
    # O7 Bonferroni over 4 drops
    print("Bonferroni per-configuration alpha over 4 drops:", 0.05 / 4)
