import os, sys, collections, math
sys.path.insert(0, "/home/user/LLM-Test/src")
os.environ["DATA_AREAS"]="a0,a1,a2,a3,a4,a5"; os.environ["DATA_N_PROCESSES"]="6"
from spine import assemble
from data import api as D
cfg = assemble.build(dict(os.environ))[0]["DATA"]
A = D.open_areas(cfg, seed=0)
def table(b):
    t = collections.defaultdict(collections.Counter)
    for i in range(2, len(b)): t[b[i-2:i]][b[i]] += 1
    return t
t0, t5 = table(A.bodies["a0"]), table(A.bodies["a5"])
print("alphabets", sorted(set(A.bodies["a0"])) == sorted(set(A.bodies["a5"])), len(set(A.bodies["a0"])), len(set(A.bodies["a5"])))
shared = set(t0) & set(t5)
print("contexts a0", len(t0), "a5", len(t5), "shared", len(shared))
# fraction of shared contexts whose support sets differ, and mean total-variation distance
tv = []
for c in shared:
    p = t0[c]; q = t5[c]; sp = sum(p.values()); sq = sum(q.values())
    keys = set(p) | set(q)
    tv.append(0.5 * sum(abs(p[k]/sp - q[k]/sq) for k in keys))
print("mean TV distance over shared contexts", round(sum(tv)/len(tv), 3), "share with TV>0.5", round(sum(1 for x in tv if x > 0.5)/len(tv), 3))
