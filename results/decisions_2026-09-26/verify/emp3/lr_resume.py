# Independent reproduction of the continuation learning rate with the tree's own OPT functions:
# build -> (revise_horizon at acts) -> state_dict -> fresh build at the child's horizon -> load_state -> lr_at.
import sys, math
sys.path.insert(0, "/home/user/LLM-Test/src")
import torch
from spine import assemble, units as U
from opt import api as O
cfg, _, _ = assemble.build(environ={})
opt = cfg["OPT"]
PEAK = float(opt.lr)
print(f"defaults: lr={PEAK} warmup={opt.lr_warmup} min_frac={opt.lr_min_frac} sched={opt.lr_sched} "
      f"restarts={opt.lr_restarts} wavelength={opt.lr_wavelength}")

def new(run_windows):
    groups = {"base": [torch.nn.Parameter(torch.zeros(3, 3))], "encoder": [torch.nn.Parameter(torch.zeros(3))]}
    return O.build(opt, param_groups=groups, run_windows=U.Windows(int(run_windows)))

def f(st, step):
    return O.lr_at(opt, st, U.Steps(int(step))) / PEAK

def resume(parent, child_windows):
    child = new(child_windows)
    rep = O.load_state(opt, child, O.state_dict(opt, parent))
    return child, rep

print("\n1. no-act parent (no revision log) that FINISHED its epoch of E windows; child RUN_EPOCHS=2 (2E):")
for E in (1000, 1300, 3000, 20000, 102382, 105025):
    p = new(E); p.opt_step = U.Steps(E)
    c, rep = resume(p, 2 * E)
    print(f"   E={E:6d} parent@end {f(p, E):.4f}  child@E+1 {f(c, E+1):.4f}  @E+E/2 {f(c, E + E//2):.4f}  "
          f"@2E {f(c, 2*E):.4f}  horizon_changed={c.counters.get('opt.ckpt.horizon_changed')} "
          f"lr_prev_cleared={c.counters.get('opt.ckpt.lr_prev_cleared')}")

print("\n2. parent with k3000 acts (revision log) that FINISHED; child 2x its final epoch:")
# the loop's revision: run_windows = step + (n_new - in_epoch) for a one-epoch run; take the act
# epoch lengths from the tree's own acts replay (ids/128 after each act, seed 0), rounded.
for build_E, acts in ((105025, [(3001, 96768), (6001, 92902), (9001, 90747), (12001, 89366), (15001, 88152), (18001, 86979)]),
                      (105025, [(3001, 96768)])):
    p = new(build_E)
    for s0, ew in acts:
        p.opt_step = U.Steps(s0); O.revise_horizon(opt, p, run_windows=U.Windows(ew))
    E = acts[-1][1]; p.opt_step = U.Steps(E)
    c, rep = resume(p, 2 * E)
    print(f"   acts {len(acts)} final E={E}: parent@end {f(p, E):.4f}; child @E+1 {f(c, E+1):.4f} @E+1000 {f(c, E+1000):.4f} "
          f"@1.5E {f(c, int(1.5*E)):.4f} @2E-1 {f(c, 2*E-1):.4f}; revs tail {c.horizon_revisions[-2:]}; "
          f"horizon_changed={c.counters.get('opt.ckpt.horizon_changed')}")

print("\n3. the WORLD-fleet shape: no-act parent stopped at window 20000 of a 105025-window epoch")
p = new(105025); print(f"   rate at window 20000: {f(p, 20000):.4f} of peak")

print("\n4. act-parent stopped early (window 20000 of its revised 86979), child 2x:")
p = new(105025)
for s0, ew in ((3001, 96768), (6001, 92902), (9001, 90747), (12001, 89366), (15001, 88152), (18001, 86979)):
    p.opt_step = U.Steps(s0); O.revise_horizon(opt, p, run_windows=U.Windows(ew))
p.opt_step = U.Steps(20000)
c, _ = resume(p, 2 * 86979)
print(f"   parent@20000 {f(p, 20000):.4f}; child@20001 {f(c, 20001):.4f}")
