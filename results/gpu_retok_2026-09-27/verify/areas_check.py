"""The per-area check of the worst-area reading RESULTS.md reports, from the replayed labels
(labels.s*.npy beside this script, written by replay.py and validated against k0's per-flush bytes).
    python3 areas_check.py <gpu_retok_out>
Two estimates per (phase, area) cell: (A) each flush's bits split across areas by byte share; (B) only
flushes whose bytes are all one area."""
import json, math, os, sys
import numpy as np
from scipy import stats

OUT = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
CTX, TOTAL, NPH = 128, 3780000, 4
L2 = math.log(2)
B = [round((j + 1) * TOTAL / NPH) for j in range(NPH)]
NAMES = ["eng", "py", "num", "c"]
SCHED = [(0, 1), (1, 2), (1, 2), (2, 3)]
cells = [(p, a) for p in range(NPH) for a in SCHED[p]]
LAB = {s: np.load(os.path.join(HERE, f"labels.s{s}.npy")) for s in range(3)}


def cellbits(arm, s):
    c = np.array(json.load(open(os.path.join(OUT, "curves", f"{arm}.s{s}.json"))))
    fb = np.array(json.load(open(os.path.join(OUT, "curves", f"{arm}.s{s}.bytes.json"))))
    o1 = np.cumsum(fb); o0 = o1 - fb
    lab = LAB[s]
    ph = np.minimum(np.searchsorted(np.array(B), np.arange(len(lab)), side="right"), NPH - 1)
    cell = ph * 4 + lab.astype(np.int64)
    cum = np.zeros((16, len(lab) + 1), dtype=np.int64)
    for k in range(16):
        cum[k, 1:] = np.cumsum(cell == k)
    cnt = (cum[:, o1] - cum[:, o0]).astype(float)          # 16 x nflush
    bits = c * CTX / L2
    A_bits = (cnt / fb * bits).sum(axis=1); A_byt = cnt.sum(axis=1)
    single = (cnt.max(axis=0) == fb)
    B_bits = (cnt[:, single] / fb[single] * bits[single]).sum(axis=1); B_byt = cnt[:, single].sum(axis=1)
    return A_bits, A_byt, B_bits, B_byt


V = {(a, s): cellbits(a, s) for a in ("k0", "k3000", "k1000", "k0_nuis") for s in range(3)}


def val(a, s, p, ar, est):
    Ab, Ay, Bb, By = V[(a, s)]
    k = p * 4 + ar
    return (Ab[k] / Ay[k]) if est == "A" else (Bb[k] / By[k])


def bounds(d, lev, ntest):
    d = np.asarray(d); n = len(d); m = d.mean(); se = d.std(ddof=1) / math.sqrt(n)
    return m, m - stats.t.ppf(1 - lev / ntest, n - 1) * se, m + stats.t.ppf(0.95, n - 1) * se


for est in ("A", "B"):
    print(f"=== estimate {est} ({'byte-share split' if est == 'A' else 'single-area flushes only'})")
    if est == "B":
        share = [V[("k1000", s)][3][p * 4 + a] / V[("k1000", s)][1][p * 4 + a] for s in range(3) for p, a in cells]
        print(f"  single-area flushes hold {100 * min(share):.1f}-{100 * max(share):.1f}% of each k1000 cell's bytes")
    for arm, lev in (("k3000", 0.025), ("k1000", 0.05), ("k0_nuis", 0.05)):
        row = []
        for p, a in cells:
            d = [val(arm, s, p, a, est) - val("k0", s, p, a, est) for s in range(3)]
            m, lo, up = bounds(d, lev, len(cells))
            row.append(f"p{p+1}:{NAMES[a]} {m:+.4f} [{lo:+.3f},{up:+.3f}]")
        print(f"  {arm:8} " + " ".join(row))
    for arm in ("k1000", "k3000"):
        d = [val(arm, s, 3, 2, est) - val("k0", s, 3, 2, est) for s in range(3)]
        m = np.mean(d); se = np.std(d, ddof=1) / math.sqrt(3)
        print(f"  {arm} p4 num per seed {' '.join(f'{x:+.4f}' for x in d)}; unadjusted one-sided 95% lower "
              f"{m - stats.t.ppf(0.95, 2) * se:+.4f}; Bonferroni-8 lower (t {stats.t.ppf(1 - 0.05 / 8, 2):.3f}) "
              f"{m - stats.t.ppf(1 - 0.05 / 8, 2) * se:+.4f}; p(true <= 0.05) {stats.t.sf((m - 0.05) / se, 2):.3f}")
    # per area over the whole run
    for arm, lev in (("k3000", 0.025), ("k1000", 0.05)):
        out = []
        for a in range(4):
            d = []
            for s in range(3):
                def w(arm_):
                    Ab, Ay, Bb, By = V[(arm_, s)]
                    bb, yy = (Ab, Ay) if est == "A" else (Bb, By)
                    return sum(bb[p * 4 + a] for p in range(NPH)) / sum(yy[p * 4 + a] for p in range(NPH))
                d.append(w(arm) - w("k0"))
            m, lo, up = bounds(d, lev, 4)
            out.append(f"{NAMES[a]} {m:+.4f} [{lo:+.4f},{up:+.4f}]")
        print(f"  whole run per area {arm:6}: " + " | ".join(out))
