import sys
sys.path.insert(0, "/home/user/LLM-Test/src")
from opt.api import _schedule, _effective_step, Horizon
LR=2e-3; MF=0.05
def H(rs, warm_lever=1000):
    w = min(warm_lever, max(1, rs // 10))
    return Horizon(run_steps=rs, warmup=w, wavelength=rs, n_cycles=1)
def price(h, step, revs=None):
    eff = _effective_step(h, revs, step) if revs else None
    r, _ = _schedule(lr=LR, sched="cosine", min_frac=MF, restarts=True, decay=1.0, shift_warm=0,
                     restart_amp=1.0, shift_at=None, horizon=h, step=step, eff_step=eff)
    return r / LR
print("== no act in parent (horizon_changed branch): live horizon in force")
for parent, child in [(1000, 2000), (3000, 6000), (20000, 40000), (105025, 210050), (20000, 30000), (20000, 60000), (20000, 22000)]:
    hp = H(parent); hc = H(child)
    print(f" parent {parent} end rate {price(hp, parent):.4f}; child {child} first step {parent+1}: {price(hc, parent+1):.4f}, +1000: {price(hc, parent+1000):.4f}")
print("== act fired in parent (horizon_revisions branch): saved build-time horizon + log")
for R0, act_at, Rp, child in [(22000, 3000, 20600, 41200), (105025, 3000, 98340, 196680), (4000, 3000, 3800, 7600)]:
    h = H(R0)
    revs = [(act_at, Rp)]
    end = price(h, Rp, revs)
    # load_state appends (opt_step, live run_steps) if differs
    revs2 = revs + [(Rp, child)]
    rates = [price(h, s, revs2) for s in (Rp + 1, Rp + 1000, (Rp + child)//2, child - 1)]
    print(f" build R={R0} act@{act_at} revised->{Rp}; parent end rate {end:.4f}; child horizon {child}: rates {[round(x,4) for x in rates]}")
    # a parent that stopped slightly early (e.g. act revision in windows != final step)
    for stop in (Rp - 50,):
        revs3 = revs + [(stop, child)]
        print(f"   parent stopped at {stop} (short of revised end by 50): child rates {[round(price(h, s, revs3),4) for s in (stop+1, stop+1000, (stop+child)//2, child-1)]}")
