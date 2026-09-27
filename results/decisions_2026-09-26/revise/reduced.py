"""O6 component sets: full (per session end) vs reduced (per-area mean over sessions), scratch."""
import math
from power import power_comp
eps = 0.05
def full(sd):
    comps = [(eps, sd)] * 22 + [(2*eps, 2*sd)] * 4 + [(2*eps, math.sqrt(3)*sd), (2*eps, math.sqrt(2)*sd), (2*eps, sd)]
    return comps
def reduced(sd):
    comps = [(eps, sd/2)] * 4 + [(eps, sd/math.sqrt(3)), (eps, sd/math.sqrt(2)), (eps, sd)]
    comps += [(2*eps, 2*sd)] * 4 + [(2*eps, math.sqrt(3)*sd), (2*eps, math.sqrt(2)*sd), (2*eps, sd)]
    return comps
def joint(n, comps):
    p = 1.0
    for M, s in comps: p *= power_comp(n, M, s)
    return p
def nstar(comps):
    for n in range(3, 400):
        if joint(n, comps) >= 0.8: return n
for name, sd in (("easy", 0.0527), ("cred", 0.0624), ("hard", 0.1279)):
    print(f"{name} sd={sd}: full C={len(full(sd))} n*={nstar(full(sd))} joint@5={joint(5, full(sd)):.2e}; "
          f"reduced C={len(reduced(sd))} n*={nstar(reduced(sd))} joint@5={joint(5, reduced(sd)):.3f}")
# O9: 4 parent areas at eps
for name, sd in (("easy", 0.0527), ("cred", 0.0624), ("hard", 0.1279)):
    c = [(eps, sd)] * 4
    print(f"O9 C=4 {name}: n*={nstar(c)} joint@5={joint(5,c):.3f}")
