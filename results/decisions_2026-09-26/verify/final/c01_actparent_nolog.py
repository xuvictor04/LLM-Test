# Price a child of a k3000 parent whose revision log was suppressed (OPT_HORIZON_REVISE=False), the case C01 names,
# with the real OPT.build/state_dict/load_state/lr_at. Inputs are approximate: parent build horizon = k0 epoch at
# 3.78 MB (19853, k0child_378MB_s0.out), parent final step E = windows a k3000 run needs to consume 3.78 MB
# (~15,300, from e2_splice.py's input), child horizon 2*W1 with W1 = 13516 (the 3.78 MB epoch re-tokenized with
# vocab 1106, which k3000 also ends at: acts_k3000_s0.out final vocab 1106).
import sys
sys.path.insert(0, "/home/user/LLM-Test/src")
import torch
from spine import assemble, units as U
from opt import api as O
configs, _, _ = assemble.build(environ={})
opt = configs["OPT"]; peak = float(opt.lr)
def mk(n):
    p = [torch.nn.Parameter(torch.zeros(4, 3))]; e = [torch.nn.Parameter(torch.zeros(2))]
    return O.build(opt, param_groups={"base": p, "encoder": e}, run_windows=U.Windows(int(n)))
for build, E, W1 in ((19853, 15300, 13516), (19853, 16780, 13516), (19853, 16780, 14000), (19853, 19853, 13516)):
    par = mk(build); par.opt_step = U.Steps(E)
    saved = O.state_dict(opt, par)
    ch = mk(2 * W1); O.load_state(opt, ch, saved)
    print(f"parent build {build}, stopped/ended at {E} (no log): parent rate {O.lr_at(opt, par, U.Steps(E))/peak:.4f}; child first step {O.lr_at(opt, ch, U.Steps(E+1))/peak:.4f} of peak (horizon {2*W1})")
