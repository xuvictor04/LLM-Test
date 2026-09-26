# Reproduce the continuation LR with the real OPT.build / revise_horizon / state_dict / load_state / lr_at.
import sys
sys.path.insert(0, "/home/user/LLM-Test/src")
import torch
from spine import assemble, units as U
from opt import api as O
configs, _, _ = assemble.build(environ={})
opt = configs["OPT"]
peak = float(opt.lr)
print("OPT defaults: lr", peak, "warmup", opt.lr_warmup, "min_frac", opt.lr_min_frac, "restarts", opt.lr_restarts,
      "wavelength", opt.lr_wavelength, "decay", opt.lr_decay, "sched", opt.lr_sched)
def mk(run_windows):
    p = [torch.nn.Parameter(torch.zeros(4, 3))]; e = [torch.nn.Parameter(torch.zeros(2))]
    return O.build(opt, param_groups={"base": p, "encoder": e}, run_windows=U.Windows(int(run_windows)))
def frac(st, s): return O.lr_at(opt, st, U.Steps(int(s))) / peak

def case_no_act(N, child_mult=2):
    par = mk(N); par.opt_step = U.Steps(N)
    end = frac(par, N)
    saved = O.state_dict(opt, par)
    ch = mk(child_mult * N); rep = O.load_state(opt, ch, saved)
    return end, [round(frac(ch, N + d), 4) for d in (1, 100, 1000)], ch.counters.get("opt.ckpt.horizon_changed"), rep.restored

def case_act(N0, acts, child_mult=2):
    # acts: list of (step, revised run_windows); parent finishes at the last revised length
    par = mk(N0)
    for s, rw in acts:
        par.opt_step = U.Steps(s); O.revise_horizon(opt, par, run_windows=U.Windows(rw))
    N = acts[-1][1]; par.opt_step = U.Steps(N)
    end = frac(par, N)
    saved = O.state_dict(opt, par)
    ch = mk(child_mult * N); rep = O.load_state(opt, ch, saved)
    return end, [round(frac(ch, N + d), 4) for d in (1, 1000, 10000, N - 1)], ch.horizon_revisions[-2:], ch.counters.get("opt.ckpt.horizon_changed"), rep.restored

print("\nA. parent WITHOUT an act (no revision log), finished, resumed for one more equal epoch:")
for N in (1000, 3000, 5000, 20000, 50000, 105000):
    end, fr, hc, ok = case_no_act(N)
    print(f"  N={N:6d}: parent end {end:.4f} of peak; child first step {fr[0]:.4f}, +100 {fr[1]:.4f}, +1000 {fr[2]:.4f}  horizon_changed={hc} restored={ok}")
print("  child 3x length instead (N=20000):", case_no_act(20000, 3)[1])
print("\nB. parent WITH an act (revision log), finished, resumed for one more equal epoch:")
for N0, acts in ((105000, [(3000, 100000)]), (105000, [(3000, 100000), (6000, 98000), (9000, 97000)]), (20000, [(3000, 19000)])):
    end, fr, revs, hc, ok = case_act(N0, acts)
    print(f"  build {N0}, acts {acts}: parent end {end:.4f}; child steps +1,+1000,+10000,+N-1 -> {fr}; last revisions {revs}; horizon_changed={hc}")
print("  B with child 3x length:", case_act(105000, [(3000, 100000)], 3)[1])
# a parent that stopped BEFORE its revised end (e.g. --max-windows) is not at the floor:
par = mk(105000); par.opt_step = U.Steps(3000); O.revise_horizon(opt, par, run_windows=U.Windows(100000)); par.opt_step = U.Steps(20000)
saved = O.state_dict(opt, par); ch = mk(200000); O.load_state(opt, ch, saved)
print("\nC. act-parent stopped early at 20000 of 100000, child horizon 200000: parent", round(frac(par, 20000), 4), "child", [round(frac(ch, 20000 + d), 4) for d in (1, 50000, 150000)])
