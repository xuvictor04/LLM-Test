"""Scratch driver: compose the shipped system, run N windows, and record per-window loss, the
window's DATA area label (majority over Segmentation.labels) and DOM's did -- without editing the
tree. Monkeypatches only module attributes the loop calls through (lm_api.lm_loss, dom_api.observe)."""
import os, sys, json, time, collections
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, "/home/user/LLM-Test/src")
import torch
torch.set_num_threads(1)
from spine.compose import compose
from spine import loop
from lm import api as lm_api
from domains import api as dom_api

N = int(sys.argv[1]); OUT = sys.argv[2]
rec = {"loss": [], "did": []}
_orig_loss = lm_api.lm_loss
def lm_loss(lm, logits, y):
    pw, m = _orig_loss(lm, logits, y)
    rec["loss"].extend(float(v) for v in pw.detach().reshape(-1))
    return pw, m
lm_api.lm_loss = lm_loss
_orig_obs = dom_api.observe
def observe(*a, **k):
    asg = _orig_obs(*a, **k)
    rec["did"].append(int(asg.did))
    return asg
dom_api.observe = observe

t0 = time.time()
sysm = compose(environ=os.environ)
t1 = time.time()
res = loop.run(sysm, max_windows=N, progress=False)
t2 = time.time()
ctx = int(sysm.configs["LM"].ctx)
labs = sysm.segmentation.labels
win_area = []
for i in range(len(rec["loss"])):
    seg = labs[i*ctx:i*ctx+ctx+1]
    win_area.append(collections.Counter(seg).most_common(1)[0][0] if seg else None)
report = {k: dict(v) if isinstance(v, dict) else v for k, v in res.report.items()}
out = {"compose_s": t1-t0, "loop_s": t2-t1, "windows": res.windows, "loss": rec["loss"],
       "did": rec["did"], "area": win_area, "protocol": sysm.plan.protocol,
       "schedule": [list(p) for p in sysm.plan.schedule], "area_names": list(sysm.areas.names),
       "phase_bounds": [list(b) for b in sysm.plan.phase_bounds],
       "per_area_drawn": sysm.stream.per_area_drawn,
       "ledger": {k: list(v) for k, v in res.cadence_ledger.items()},
       "report": json.loads(json.dumps(report, default=str))}
json.dump(out, open(OUT, "w"), default=str)
print("done", out["windows"], "compose", round(t1-t0,1), "loop", round(t2-t1,1))
