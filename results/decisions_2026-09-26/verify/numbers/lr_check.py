import sys, math
sys.path.insert(0, "/home/user/LLM-Test/src")
from opt.api import _schedule, Horizon
LR=2e-3; MF=0.05
def price(rs, step, w=1000):
    h = Horizon(run_steps=rs, warmup=w, wavelength=rs, n_cycles=1)
    r, _ = _schedule(lr=LR, sched="cosine", min_frac=MF, restarts=True, decay=1.0, shift_warm=0,
                     restart_amp=1.0, shift_at=None, horizon=h, step=step, eff_step=None)
    return r/LR
for rs in (102000, 105025):
    print(rs, "rate at 20000:", round(price(rs, 20000), 4))
# OFF arm under-anneal: run shortened by fraction f -> ends at rate on fitted horizon at (1-f)
for f in (0.05, 0.10, 0.15):
    rs=20000; stop=int(rs*(1-f))
    print(f, round(price(rs, stop), 4), round(0.05+0.95*(1-math.cos(math.pi*f))/2, 4))
