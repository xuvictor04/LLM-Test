"""Independent re-read of the 2026-09-27 retok fleet archive (numpy/scipy), for RESULTS.md: integrity, the
whole-run and per-phase readings, the eps rule with Holm, the choice and its other readings, the rates and
the blackout.
    python3 verify.py <unpacked gpu_retok_out>"""
import json, math, os, re, sys
import numpy as np
from scipy import stats

OUT = sys.argv[1]
CTX, TOTAL, NPH, EPS = 128, 3780000, 4, 0.05
L2 = math.log(2)
arms = ["k0", "k3000", "k1000", "k0_nuis", "k0_rerun"]
R = {}
for a in arms:
    for s in range(3):
        tag = f"{a}.s{s}"
        lg = os.path.join(OUT, "logs", tag + ".log")
        if not os.path.exists(lg):
            continue
        t = open(lg).read()
        c = json.load(open(os.path.join(OUT, "curves", tag + ".json")))
        b = json.load(open(os.path.join(OUT, "curves", tag + ".bytes.json")))
        bs = int(re.search(r"^\s+loop\.bytes_scored\s+(\d+)", t, re.M).group(1))
        w = re.search(r"=== (\d+) windows[^\n]*? in ([\d.]+)s", t)
        bw = re.search(r"^\s+fab\.blackout_windows\s+(\d+)", t, re.M)
        acts = re.search(r"^\s+loop\.acts\s+(\d+)", t, re.M)
        pe = re.search(r"gate:data\.phase_entered\s[^\n]*'(\d+) vs (\d+)'", t)
        seed = re.search(r"torch_seed=(\d+)", t).group(1)
        assert len(c) == len(b), tag
        assert all(math.isfinite(x) for x in c), tag
        wh = sum(c) * CTX / L2 / bs
        # phases: each flush by its first byte
        ln, lb, off = [0.0] * NPH, [0] * NPH, 0
        for x, nb in zip(c, b):
            k = min(NPH - 1, next((j for j in range(NPH) if off < round((j + 1) * TOTAL / NPH)), NPH - 1))
            ln[k] += x; lb[k] += nb; off += nb
        ph = [ln[k] * CTX / L2 / lb[k] for k in range(NPH)]
        R[(a, s)] = dict(c=c, b=b, bs=bs, sumb=sum(b), wh=wh, ph=ph, win=int(w.group(1)), secs=float(w.group(2)),
                         bw=int(bw.group(1)) if bw else None, acts=int(acts.group(1)) if acts else None,
                         pe=pe.groups() if pe else None, seed=seed, n=len(c))

print("RUNS (n flushes, sum(bytes) == bytes_scored, whole-run bits/byte, phase gate, torch_seed)")
for (a, s), v in sorted(R.items()):
    print(f"  {a:9} s{s} n={v['n']:6} win={v['win']:6} bytes {v['sumb']} {'==' if v['sumb'] == v['bs'] else '!='} {v['bs']} "
          f"preq {v['wh']:.5f} phases {' '.join(f'{x:.4f}' for x in v['ph'])} gate {v['pe']} acts {v['acts']}")
print("rerun bit-exact:", R[("k0", 0)]["c"] == R[("k0_rerun", 0)]["c"] and R[("k0", 0)]["b"] == R[("k0_rerun", 0)]["b"])
print("torch_seed equal per seed across arms:",
      all(len({R[(a, s)]["seed"] for a in arms if (a, s) in R}) == 1 for s in range(3)))
for a in ("k3000", "k1000"):
    k = 1000 if a == "k1000" else 3000
    same = []
    for s in range(3):
        c0, ca = R[("k0", s)]["c"], R[(a, s)]["c"]
        first = next(i for i, (x, y) in enumerate(zip(c0, ca)) if x != y)
        same.append(first)
    print(f"  {a}: first flush index differing from k0 per seed (0-based): {same} (cadence {k})")

print("\nWHOLE RUN, per seed, and differences")
def d(a, b_, s): return R[(a, s)]["wh"] - R[(b_, s)]["wh"]
for a in ("k0", "k3000", "k1000", "k0_nuis"):
    print(f"  {a:8}", " ".join(f"{R[(a, s)]['wh']:.5f}" for s in range(3)))
for a in ("k3000", "k1000"):
    xs = [d(a, "k0", s) for s in range(3)]
    print(f"  {a}-k0", " ".join(f"{x:+.5f}" for x in xs), f"mean {np.mean(xs):+.5f}")
M = max(abs(d("k0", "k0_nuis", s)) for s in range(3))
print(f"  M {M:.5f}; k0_nuis-k0 per seed", " ".join(f"{d('k0_nuis', 'k0', s):+.5f}" for s in range(3)))

print("\nPER PHASE, arm means and eps rule")
for a in ("k0", "k3000", "k1000", "k0_nuis"):
    print(f"  {a:8}", " ".join(f"{np.mean([R[(a, s)]['ph'][k] for s in range(3)]):.4f}" for k in range(NPH)))
def bounds(xs, lvl):
    n = len(xs); m = np.mean(xs); se = np.std(xs, ddof=1) / math.sqrt(n)
    return m, m - stats.t.ppf(1 - lvl / NPH, n - 1) * se, m + stats.t.ppf(0.95, n - 1) * se
diffs = {a: [[R[(a, s)]["ph"][k] - R[("k0", s)]["ph"][k] for s in range(3)] for k in range(NPH)] for a in ("k3000", "k1000")}
def p_harm(xs):
    n = len(xs); m = np.mean(xs); se = np.std(xs, ddof=1) / math.sqrt(n)
    return stats.t.sf((m - EPS) / se, n - 1)
padj = {a: NPH * min(p_harm(xs) for xs in diffs[a]) for a in diffs}
order = sorted(diffs, key=lambda a: padj[a])
print("  Holm order", order, {a: round(padj[a], 3) for a in padj})
open_ = True
for i, a in enumerate(order):
    lvl = 0.05 / (len(order) - i)
    rows = [bounds(xs, lvl) for xs in diffs[a]]
    fail = open_ and any(lo > EPS for _, lo, _ in rows)
    ok = all(up <= EPS for _, _, up in rows)
    open_ = open_ and fail
    print(f"  {a} a={lvl}: " + " ".join(f"p{k+1} {m:+.4f} [{lo:+.4f},{up:+.4f}]" for k, (m, lo, up) in enumerate(rows))
          + f" -> {'FAIL' if fail else 'PASS' if ok else 'UNRESOLVED'}")
x = [d("k1000", "k3000", s) for s in range(3)]
m, sd = np.mean(x), np.std(x, ddof=1)
up = m + stats.t.ppf(0.95, 2) * sd / math.sqrt(3)
print(f"\nCHOICE whole-run k1000-k3000 per seed {' '.join(f'{v:+.5f}' for v in x)}; mean {m:+.5f} sd {sd:.5f} upper {up:+.5f} "
      f"p {stats.t.cdf(m / (sd / math.sqrt(3)), 2):.4f}")
# per-phase k1000 - k3000 upper bounds (the other readings of the choice)
for k in range(NPH):
    xs = [R[("k1000", s)]["ph"][k] - R[("k3000", s)]["ph"][k] for s in range(3)]
    mm = np.mean(xs); uu = mm + stats.t.ppf(0.95, 2) * np.std(xs, ddof=1) / math.sqrt(3)
    print(f"  p{k+1} k1000-k3000 mean {mm:+.4f} upper {uu:+.4f}  per seed {' '.join(f'{v:+.5f}' for v in xs)}")
# per-run worst-phase harm (reading c)
wk = [max(R[("k1000", s)]["ph"][k] - R[("k0", s)]["ph"][k] for k in range(NPH))
      - max(R[("k3000", s)]["ph"][k] - R[("k0", s)]["ph"][k] for k in range(NPH)) for s in range(3)]
print("  (c) each run's worst-phase harm, k1000 - k3000:", " ".join(f"{v:+.4f}" for v in wk),
      f"upper {np.mean(wk) + stats.t.ppf(0.95, 2) * np.std(wk, ddof=1) / math.sqrt(3):+.4f}")

print("\nRATES")
for a in ("k0", "k3000", "k1000", "k0_nuis", "k0_rerun"):
    rs = [v for (aa, s), v in R.items() if aa == a]
    wps = [v["win"] / v["secs"] for v in rs]; bps = [v["bs"] / v["secs"] for v in rs]
    print(f"  {a:8} {np.mean(wps):.2f} [{min(wps):.2f}-{max(wps):.2f}] w/s  {np.mean(bps):.0f} B/s  windows {[v['win'] for v in rs]}")
tw = sum(v["win"] for v in R.values())
print(f"  aggregate {tw} windows / 986 s = {tw / 986:.2f} w/s; ETA 260000/514.608 = {260000 / 514.608:.0f} s; ratio {986 / (260000 / 514.608):.2f}")
print("\nBLACKOUT")
for a in ("k3000", "k1000"):
    rs = [R[(a, s)] for s in range(3)]
    print(f"  {a}: blackout windows {[v['bw'] for v in rs]} of {[v['win'] for v in rs]} = "
          f"{np.mean([v['bw'] / v['win'] for v in rs]) * 100:.1f}%; acts {[v['acts'] for v in rs]}")
