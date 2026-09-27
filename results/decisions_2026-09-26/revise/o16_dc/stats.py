"""Power and false-rate arithmetic for O16-O20 (scratch). Reuses ../power.py (the O6-O10 revision's
noncentral-t helpers) so every ruling uses the same computation."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from power import t_ppf, power_comp, n_needed
from power_mc import pw, n_mc
eps = 0.05
sds = [("easy", 0.0527), ("cred", 0.0624), ("hard", 0.1279)]
print("t_.95,4 =", round(t_ppf(0.95, 4), 3))
# O16 primary: E1 TI-gap SD 0.0306 (implied by MDE 0.042 at 5 seeds, ../power.py)
print("O16 primary, SD 0.0306, superiority power at delta=eps, 5 seeds (MC):", round(pw(5, eps, 0.0306), 3))
print("O16 primary, SD 0.0306, n for 80% (MC):", n_mc(1, eps, 0.0306, start=3))
# guards: C = 8 (4 areas x TI and end-state), reduced C = 4 (TI only)
for C in (8, 4, 1):
    print(f"C={C}: per-comp {0.8**(1/C):.4f}; n* (MC) " + "  ".join(f"{k}:{n_mc(C, eps, sd, start=5)}" for k, sd in sds))
# largest SD resolved at n_max 20 for C = 8 and 4 and 1
for C in (8, 4, 1):
    lo, hi = 0.001, 0.3
    for _ in range(40):
        mid = (lo + hi) / 2
        if power_comp(20, eps, mid) >= 0.8 ** (1 / C): lo = mid
        else: hi = mid
    print(f"n_max 20, C={C}: largest per-component SD with >=80% joint power (normal approx) = {lo:.4f}")
# 5-seed joint power at C=8 on register SDs (MC per component, independent)
for k, sd in sds:
    p = pw(5, eps, sd)
    print(f"5 seeds, {k}: per comp {p:.3f}, joint C=8 {p**8:.2e}, C=4 {p**4:.3f}")
# O18: false attack success per session and over the grid
share, conf, reread = 0.01, 0.05, 0.05
per = share * conf * reread
print("O18 false success per poisoned session <=", per)
for sessions in (21 * 5, 21 * 20):
    print(f"  over {sessions} poisoned sessions: P(any false success) <= {1 - (1 - per) ** sessions:.4f}")
print("  without the re-read (O10's two stages only), 105 sessions:", round(1 - (1 - share * conf) ** 105, 4))
# O18 sessions per seed per cap value: ceil(k/cap)+2 for k=25,100 and the 250 drip
for cap in (12, 25, 50):
    s = sum(math.ceil(k / cap) + 2 for k in (25, 100, 250))
    print(f"  cap {cap}: sessions per seed (k=25, 100, 250 drip) = {s}")
