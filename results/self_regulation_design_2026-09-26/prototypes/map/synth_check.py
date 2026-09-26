import os, sys, hashlib, math, collections
os.environ["OMP_NUM_THREADS"]="1"
sys.path.insert(0, "/home/user/LLM-Test/src")
from spine import assemble
from data import api as D
res = assemble.build({})  # empty env
dat = res[0]["DATA"]
out = {}
for seed in (0, 1, 7):
    a = D.open_areas(dat, seed=seed)
    out[seed] = {n: hashlib.sha1(a.bodies[n]).hexdigest()[:10] for n in a.names}
    print("seed", seed, out[seed], {n: len(a.bodies[n]) for n in a.names}, "holdout", {n: len(a.holdout[n]) for n in a.names})
# entropy estimate of order-2 conditional
a = D.open_areas(dat, seed=0)
for n in a.names:
    b = a.bodies[n].decode()
    ctx = collections.defaultdict(collections.Counter)
    for i in range(2, len(b)):
        ctx[b[i-2:i]][b[i]] += 1
    H = 0; N = 0
    for c, cnt in ctx.items():
        t = sum(cnt.values())
        for v in cnt.values():
            p = v/t; H -= v*math.log2(p)
        N += t
    print(n, "order2 cond entropy bits/sym", round(H/N,3), "contexts", len(ctx), "alphabet", len(set(b)))
