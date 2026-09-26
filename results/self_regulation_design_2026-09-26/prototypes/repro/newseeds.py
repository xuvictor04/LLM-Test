import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmp import met, R
ARMS = [("base","d2","base"),("focus","d3","focus"),("m27","d3","replay_fixed_m27"),("fulltd","d3","fulltd"),
        ("tags","d2","tags"),("lp","d1","lp"),("lp_train","d1","lp_train"),("fulltd_tags","d3","fulltd_tags"),
        ("act6","d3","fulltd_act6"),("d1replay20","d1","replay"),("d3replay20","d3","replay_fixed"),
        ("mf_base","d3","mf_base"),("mf_trust_td","d3","mf_trust_td")]
seeds = [int(s) for s in sys.argv[1:]] or [0,3,4]
D = {}
for n, d, a in ARMS:
    for s in seeds:
        f = f"{R}/{d}/out/{a}_s{s}.json"
        if os.path.exists(f): D[(n, s)] = met(f)
keys = ["mean6","mean5","late","fh","fe","noise","Qc","Qc_sh","Wc","Qa","mean6_tag","mean5_tag","trustQc","td_trusted","rho3","tl0"]
for k in keys:
    print(f"\n== {k}  (seeds {seeds}) | diff vs base | diff vs m27")
    for n, _, _ in ARMS:
        v = [D.get((n, s), {}).get(k) for s in seeds]
        if all(x is None for x in v): continue
        fm = lambda x: f"{x:7.3f}" if isinstance(x, float) else f"{str(x):>7s}"
        row = " ".join(fm(x) for x in v)
        db = " ".join(f"{D[(n,s)][k]-D[('base',s)][k]:+.3f}" if (n,s) in D and ('base',s) in D and isinstance(D[(n,s)].get(k), float) and isinstance(D[('base',s)].get(k), float) else "   -  " for s in seeds)
        dm = " ".join(f"{D[(n,s)][k]-D[('m27',s)][k]:+.3f}" if (n,s) in D and ('m27',s) in D and isinstance(D[(n,s)].get(k), float) and isinstance(D[('m27',s)].get(k), float) else "   -  " for s in seeds)
        print(f"  {n:12s} {row} | {db} | {dm}")
