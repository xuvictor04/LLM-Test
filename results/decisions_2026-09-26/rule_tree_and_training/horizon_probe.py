# Read-only probe of the tree's pure LR-schedule functions: what rate does a CONTINUED run
# (resume at a longer run length) train at, with and without a Q-OPT-10 revision log?
import sys, math
sys.path.insert(0, "/home/user/LLM-Test/src")
from opt import api as O
from spine import units as U
H = O.Horizon
lr, mf = 2e-3, 0.05
def rate(h, revs, s):
    eff = O._effective_step(h, revs, s) if revs else None
    r, _ = O._schedule(lr=lr, sched="cosine", min_frac=mf, restarts=True, decay=1.0, shift_warm=0,
                       restart_amp=1.0, shift_at=None, horizon=h, step=s, eff_step=eff)
    return r
# parent: build horizon 20000 steps, warmup 1000, one cycle; acts shortened it to 19000
hb = H(run_steps=U.Steps(20000), warmup=U.Steps(1000), wavelength=U.Steps(20000), n_cycles=1)
revs = [(5000, 19500), (10000, 19000)]
print("parent end (step 19000) with log:", rate(hb, revs, 19000)/lr)
# child resumes at step 19000 asking for 40000 total: load_state appends (19000, 40000) to the log
revs_c = revs + [(19000, 40000)]
for s in (19001, 25000, 39999):
    print(f"  child WITH log, step {s}: {rate(hb, revs_c, s)/lr:.4f} of peak")
# no-log parent (k0: no act fired): the child prices on the LIVE horizon (40000)
hl = H(run_steps=U.Steps(40000), warmup=U.Steps(1000), wavelength=U.Steps(40000), n_cycles=1)
for s in (20001, 25000, 39999):
    print(f"  child WITHOUT log, step {s}: {rate(hl, [], s)/lr:.4f} of peak")
print("parent end (step 20000) without log:", rate(hb, [], 20000)/lr)
