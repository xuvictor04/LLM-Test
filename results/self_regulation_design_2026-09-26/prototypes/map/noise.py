import json, sys, math, statistics as st
for f in sys.argv[1:]:
    d = json.load(open(f)); L=[x/math.log(2) for x in d["loss"]]; A=d["area"]
    print(f)
    for a in d["area_names"]:
        idx=[i for i in range(len(L)) if A[i]==a]
        if len(idx)<20: continue
        last=[L[i] for i in idx[-40:]]
        # lag-1 differenced sd (removes trend), per window
        dif=[last[k+1]-last[k] for k in range(len(last)-1)]
        print(f"  {a:<4} n={len(idx)} last40 mean {st.mean(last):.3f} sd {st.pstdev(last):.3f} diff-sd/sqrt2 {st.pstdev(dif)/math.sqrt(2):.3f}  first20 mean {st.mean(L[i] for i in idx[:20]):.3f}")
