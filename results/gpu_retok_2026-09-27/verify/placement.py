"""Phase readings under three flush placements (first byte, last byte, pro rata), arm - k0 per phase.
    python3 placement.py <unpacked gpu_retok_out>"""
import json, math, os, sys
import numpy as np
OUT = sys.argv[1]; CTX, TOTAL, NPH = 128, 3780000, 4; L2 = math.log(2)
B = [round((j + 1) * TOTAL / NPH) for j in range(NPH)]
def ph(a, s, how):
    c = np.array(json.load(open(os.path.join(OUT, "curves", f"{a}.s{s}.json"))))
    fb = np.array(json.load(open(os.path.join(OUT, "curves", f"{a}.s{s}.bytes.json"))))
    o1 = np.cumsum(fb); o0 = o1 - fb; bits = c * CTX / L2
    out = []
    for k in range(NPH):
        lo, hi = (0 if k == 0 else B[k - 1]), B[k]
        if how == "first":
            m = (o0 >= lo) & (o0 < hi); out.append(bits[m].sum() / fb[m].sum())
        elif how == "last":
            e = o1 - 1; m = (e >= lo) & (e < hi); out.append(bits[m].sum() / fb[m].sum())
        else:
            ov = np.clip(np.minimum(o1, hi) - np.maximum(o0, lo), 0, None)
            out.append((ov / fb * bits).sum() / ov.sum())
    return np.array(out)
base = {a: np.mean([ph(a, s, "first") - ph("k0", s, "first") for s in range(3)], axis=0) for a in ("k3000", "k1000")}
for how in ("last", "prorata"):
    for a in ("k3000", "k1000"):
        d = np.mean([ph(a, s, how) - ph("k0", s, how) for s in range(3)], axis=0)
        print(f"{how:8} {a}: {' '.join(f'{x:+.4f}' for x in d)}  max |change vs first byte| {np.max(np.abs(d - base[a])):.4f}")
