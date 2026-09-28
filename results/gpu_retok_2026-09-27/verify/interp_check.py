"""Checks of the interpretive numbers RESULTS.md cites (end-of-run gap, area entries, act spikes, the
first acts' bins, n_live, act windows, FAB growth, k0's periodic saves, GPU busy), from the archive's
per-flush losses and bytes, logs, KEPT.txt and heartbeat. python3 interp_check.py <gpu_retok_out>"""
import json, math, os, re, sys
import numpy as np
from scipy import stats

OUT = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
CTX, TOTAL = 128, 3780000
L2 = math.log(2)
A = ("k0", "k3000", "k1000", "k0_nuis")


def load(a, s):
    c = np.array(json.load(open(os.path.join(OUT, "curves", f"{a}.s{s}.json"))))
    fb = np.array(json.load(open(os.path.join(OUT, "curves", f"{a}.s{s}.bytes.json"))))
    t = open(os.path.join(OUT, "logs", f"{a}.s{s}.log")).read()
    return c, fb, t


R = {(a, s): load(a, s) for a in A for s in range(3)}


def binned(a, s, edges):
    """bits/byte per byte bin, each flush split pro rata across bins."""
    c, fb, _ = R[(a, s)]
    o1 = np.cumsum(fb); o0 = o1 - fb
    bits = c * CTX / L2
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        ov = np.clip(np.minimum(o1, hi) - np.maximum(o0, lo), 0, None)
        out.append((ov / fb * bits).sum() / ov.sum())
    return np.array(out)


def lower(d):
    d = np.asarray(d); return d.mean() - stats.t.ppf(0.95, 2) * d.std(ddof=1) / math.sqrt(3)


print("END OF RUN: the last 5% and 10% of the stream's bytes, arm - k0 (mean [one-sided 95% lower], per seed)")
for frac in (0.05, 0.10):
    e = [TOTAL * (1 - frac), TOTAL]
    for a in ("k3000", "k1000", "k0_nuis"):
        d = [binned(a, s, e)[0] - binned("k0", s, e)[0] for s in range(3)]
        print(f"  last {int(frac * 100)}% {a:8} {np.mean(d):+.3f} [{lower(d):+.3f}]  {' '.join(f'{x:+.3f}' for x in d)}")

print("AREA ENTRIES: first 10 KB after num's (945,000) and c's (2,835,000) nominal entry, arm - k0")
for name, at in (("num", 945000), ("c", 2835000)):
    e = [at, at + 10000]
    for a in ("k3000", "k1000"):
        d = [binned(a, s, e)[0] - binned("k0", s, e)[0] for s in range(3)]
        print(f"  {name} {a:6} {np.mean(d):+.3f}  {' '.join(f'{x:+.3f}' for x in d)}")

print("ACT SPIKES: peak (10 KB bins, mean over seeds of arm - k0) within 200 KB after each act's byte offset")
spans = {}
for a in ("k3000", "k1000"):
    peaks, means = [], []
    c, fb, t = R[(a, 0)]
    acts = [int(w) for w in re.findall(r"mid-epoch act at window (\d+):", t)]
    for w in acts:
        pk, mn = [], []
        for s in range(3):
            c_, fb_, _ = R[(a, s)]
            at = int(np.cumsum(fb_)[min(w - 1, len(fb_) - 1)])
            e = np.arange(at, min(TOTAL, at + 200000) + 1, 10000)
            if len(e) < 2:
                continue
            pk.append(binned(a, s, e) - binned("k0", s, e))
            mn.append(binned(a, s, [e[0], e[-1]])[0] - binned("k0", s, [e[0], e[-1]])[0])
        n = min(len(p) for p in pk)
        peaks.append(float(np.max(np.mean([p[:n] for p in pk], axis=0))))
        means.append(float(np.mean(mn)))
    print(f"  {a}: acts at {acts} (seed 0); peaks {' '.join(f'{x:+.2f}' for x in peaks)}")
    spans[a] = (peaks, means)
# DO THE SPIKES GROW WITH THE ACT'S LATENESS? (2026-09-28, the review of this record: RESULTS.md said they
# did.) The peaks above do not; the mean over the same 200 KB after each act does, most at the last acts.
for a, (peaks, means) in spans.items():
    h = len(peaks) // 2
    print(f"  {a}: 200 KB means {' '.join(f'{x:+.3f}' for x in means)}; peaks first {h} {np.mean(peaks[:h]):+.3f} "
          f"last {h} {np.mean(peaks[-h:]):+.3f}; 200 KB means first {h} {np.mean(means[:h]):+.3f} last {h} "
          f"{np.mean(means[-h:]):+.3f}")

print("N_LIVE at the end, per run (the last progress line / fab.n_live)")
for a in A:
    vals = []
    for s in range(3):
        t = R[(a, s)][2]
        m = re.search(r"^\s+fab\.n_live\s+(\d+)", t, re.M)
        p = re.findall(r"n_live=(\d+)", t)
        vals.append(int(m.group(1)) if m else int(p[-1]))
    print(f"  {a:8} {vals}")
print("LAST ACT WINDOW and windows (blackout arithmetic: acts x 399 + the last act's remainder)")
for a in ("k3000", "k1000"):
    for s in range(3):
        c, fb, t = R[(a, s)]
        acts = [int(w) for w in re.findall(r"mid-epoch act at window (\d+):", t)]
        win = len(c)
        bw = int(re.search(r"^\s+fab\.blackout_windows\s+(\d+)", t, re.M).group(1))
        est = sum(min(399, win - w) for w in acts)
        print(f"  {a}.s{s}: {len(acts)} acts, last at {acts[-1]}, {win} windows; blackout {bw}; sum min(399, left) {est}")

print("THE FIRST ACTS' BINS: arm - k0 over a byte range (flushes split pro rata), per seed")
for a, lo, hi, what in (("k1000", 190000, 380000, "after k1000's first act (window 1001, about 0.19 MB)"),
                        ("k3000", 567000, 661500, "k3000's first act (window 3001, about 0.57 MB)")):
    d = [binned(a, s, [lo, hi])[0] - binned("k0", s, [lo, hi])[0] for s in range(3)]
    print(f"  {a} {lo / 1e6:.3f}-{hi / 1e6:.4f} MB, {what}: {np.mean(d):+.4f}  {' '.join(f'{x:+.4f}' for x in d)}"
          + (f"; its share of p1's mean difference {np.mean(d) * (hi - lo) / (TOTAL / 4):+.4f}" if a == "k3000" else ""))

print("FAB GROWTH per run: fab.grow_dev, regression asks outside the blackout, grown regression / stall, births, spawned;")
print("  regression asks refused by FAB_COOLDOWN's spacing and suppressed by the blackout, births the new_frac budget declined")
for a in A:
    for s in range(3):
        t = R[(a, s)][2]
        g = {k: re.search(rf"^\s+fab\.{re.escape(k)}\s+(\S+)", t, re.M) for k in
             ("grow_dev", "grow_asked_regression", "grown_regression", "grown_stall", "births", "spawned",
              "grow_regression_refused_cooldown", "growth_blackout_suppressed.regression", "declined_newfrac")}
        g = {k: (m.group(1) if m else "-") for k, m in g.items()}
        print(f"  {a}.s{s}: dev {g['grow_dev']} asked_reg {g['grow_asked_regression']} grown {g['grown_regression']}/"
              f"{g['grown_stall']} births {g['births']} spawned {g['spawned']}; refused by spacing "
              f"{g['grow_regression_refused_cooldown']}, suppressed by the blackout "
              f"{g['growth_blackout_suppressed.regression']}, declined_newfrac {g['declined_newfrac']}")

print("k0'S PERIODIC SAVES INSIDE ITS LOOP (the kept copies, KEPT.txt)")
kept = open(os.path.join(OUT, "KEPT.txt")).read()
for s in range(3):
    n_kept = len(re.findall(r"^k0\.s%d\.w\d+ " % s, kept, re.M))
    print(f"  k0.s{s}: {n_kept} kept saves")

print("GPU BUSY from the heartbeat: the 12-run wave (12 training) and k0_rerun alone (1 training)")
hb = open(os.path.join(OUT, "heartbeat.log")).read()
for n in (12, 1):
    busy = [int(b) for tr, b in re.findall(r"fleet since [^|]*\|[^|]*PAR 12: \d+ on CPU, (\d+) training[^\n]*GPU (\d+)% busy", hb)
            if int(tr) == n]
    print(f"  {n} training: GPU {min(busy)}-{max(busy)}% busy over {len(busy)} heartbeat line(s)" if busy else f"  {n}: none")

print("THE ETA MISS: each run's start (logs/_started.txt t0) and wall (logs/_done.txt secs), the fleet wall, the ETAs")
t0 = {m.group(1): int(m.group(2)) for m in re.finditer(r"^(\S+) pid=\d+ t0=(\d+)", open(os.path.join(OUT, "logs", "_started.txt")).read(), re.M)}
secs = {m.group(1): int(m.group(2)) for m in re.finditer(r"^(\S+) rc=0 secs=(\d+)", open(os.path.join(OUT, "logs", "_done.txt")).read(), re.M)}
start = min(t0.values())
ends = {k: t0[k] - start + secs[k] for k in secs}
first = [k for k in t0 if t0[k] == start]
late = [k for k in t0 if t0[k] != start]
S = open(os.path.join(OUT, "SUMMARY.txt")).read()
wall = int(re.search(r"^---- fleet finished in \d+ min \((\d+) s\)", S, re.M).group(1))
cal = float(re.search(r"^    k=12  aggregate [\d.]+ windows/s  \(([\d.]+) per run\)", S, re.M).group(1))
up = float(re.search(r"startup: each smoke run built on the CPU for ([\d.]+) s", S).group(1))
eta = re.search(r"^=== ETA: about [\d.]+ h for ([\d,]+) windows at ([\d.]+) windows/s aggregate", S, re.M)
est = int(eta.group(1).replace(",", "")) / float(eta.group(2))
print(f"  {len(first)} runs started together; the last of them ended at +{max(ends[k] for k in first)} s")
for k in late:
    print(f"  {k} started at +{t0[k] - start} s and took {secs[k]} s, alone from +{max(ends[j] for j in first)} s, "
          f"ending at +{ends[k]} s; fleet wall {wall} s")
print(f"  the ETA: {est:.0f} s ({eta.group(1)} windows at {eta.group(2)} windows/s), wall/ETA {wall / est:.2f}; "
      f"priced by waves: 2 x (20,000 / {cal} + {up} s) = {2 * (20000 / cal + up):.0f} s ({2 * (20000 / cal + up) / wall - 1:+.1%} of the wall)")
hb_eta = re.search(r"ETA ~(\d+)m(\d+)s \(2 waves\)", hb)
he = int(hb_eta.group(1)) * 60 + int(hb_eta.group(2))
print(f"  the heartbeat's first fleet ETA: {he} s (2 waves), {he / wall - 1:+.1%} of the wall")
# THE HEARTBEAT'S ETA IS TIME LEFT, AT THE HEARTBEAT (2026-09-28, the review of this record: the line above
# set it against the whole wall). tools/fleet_dash.sh's step_eta returns the seconds left, and that line was
# written "fleet since ... (N s)" into the fleet: it put the end at N + ETA.
hb_at = re.search(r"fleet since [^(]*\((?:(\d+)m)?(\d+)\s?s\)[^\n]*ETA ~\d+m\d+s \(2 waves\)", hb)
el = int(hb_at.group(1) or 0) * 60 + int(hb_at.group(2))
print(f"  ... written {el} s into the fleet, as time left: the end at +{el + he} s against +{wall} s, "
      f"{(el + he) / wall - 1:+.1%}; {he} s left against {wall - el} s, {he / (wall - el) - 1:+.1%}")
