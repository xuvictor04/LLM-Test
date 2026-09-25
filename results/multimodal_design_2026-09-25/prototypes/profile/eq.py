import os, sys, time, json, hashlib
sys.path.insert(0, sys.argv[1] + "/src")
import torch; torch.set_num_threads(1)
from spine.compose import compose
from spine import loop
env=dict(os.environ)
sysm=compose(environ=env)
t=time.perf_counter(); res=loop.run(sysm, max_windows=int(sys.argv[2]), progress=False); dt=time.perf_counter()-t
pop=sysm.fabric
h=hashlib.sha1()
for tname in ("A","B","cent"):
    h.update(getattr(pop,tname).detach().cpu().contiguous().numpy().tobytes() if False else str(getattr(pop,tname).detach().cpu().double().sum().item()).encode())
c=pop.counters
print(json.dumps({"secs":round(dt,1),"n_live":int(pop.n_live),"curve_tail":[round(x,6) for x in res.loss_curve[-5:]],
  "hash":h.hexdigest(),"merged":{k:v for k,v in c.items() if "merge" in k or "cull" in k}}))
