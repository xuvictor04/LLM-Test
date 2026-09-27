"""O20: after a manage pass frees slots on a full pool, how soon is the pool full again (scratch)."""
import re, glob, os
LOGS = os.path.join(os.path.dirname(__file__), "..", "arc", "gpu_world_out", "logs")
tot = back100 = back200 = 0
for f in sorted(glob.glob(os.path.join(LOGS, "*.log"))):
    if "rerun" in f: continue
    prog = {int(w): int(n) for w, n in re.findall(r"^\[(\d+) windows\].*?n_live=(\d+)", open(f).read(), re.M)}
    first = min((w for w, n in prog.items() if n >= 4096), default=None)
    if not first: continue
    for w in sorted(prog):
        if w > first and (w - 1) % 500 == 0 and prog[w] < 4096 and w + 100 in prog:
            tot += 1
            back100 += prog[w + 100] >= 4096
            back200 += prog.get(w + 200, 0) >= 4096
print(f"passes that freed slots after fill: {tot}; full again 100 windows later: {back100} ({back100/tot:.3f}); 200 later: {back200} ({back200/tot:.3f})")
