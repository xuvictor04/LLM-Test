import sys; sys.path.insert(0, "/tmp/claude-0/-home-user-LLM-Test/e880caf7-1208-58de-93fd-49c41549bf70/scratchpad/dec/verify/emp2/d977/src")
import torch
from spine import assemble, units as U
from opt import api as O
opt = assemble.build(environ={})[0]["OPT"]
for W in (102382, 103281, 103889, 105025, 105823):
    st = O.build(opt, param_groups={"base": [torch.nn.Parameter(torch.zeros(2))], "encoder": []}, run_windows=U.Windows(W))
    print(W, "lr frac at step 20000:", round(O.lr_at(opt, st, U.Steps(20000)) / float(opt.lr), 4))
