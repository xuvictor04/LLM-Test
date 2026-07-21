#!/usr/bin/env python3
"""Live status panel for the Greg test.

    watch -n 15 python3 greg_status.py            # capability run
    watch -n 15 python3 greg_status.py ~/greg_completion.log

Reads the run log; shows arms done, the current arm's step/%/loss/ETA, a whole-run ETA,
the ranking so far, and a feed of the most recent events (evals, growth, completions).
"""
import sys, os, re

LOG = sys.argv[1] if len(sys.argv) > 1 else None
if LOG is None:                                          # no arg -> follow the most recently active phase log
    cands = [os.path.expanduser(f"~/{n}") for n in ("greg_test.log", "vs.log", "greg_completion.log")]
    cands = [c for c in cands if os.path.exists(c)]
    LOG = max(cands, key=os.path.getmtime) if cands else os.path.expanduser("~/greg_test.log")

lines = open(LOG).read().splitlines() if os.path.exists(LOG) else []
if not lines:
    print(f"(no log yet at {LOG})"); sys.exit(0)

def mins_of(s):
    m = re.search(r"(\d\d):(\d\d)", s)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None

def fmt(sec):
    if sec is None or sec < 0: return "?"
    h, m = int(sec // 3600), int((sec % 3600) // 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"

planned = None
for l in lines:
    if "GREG TEST |" in l:
        planned = 5 if "quick" in l else (9 if "full" in l else None)

banners = []                                            # (label, minute, line_idx)
for i, l in enumerate(lines):
    m = re.match(r"=== (.+?) \| (\d\d:\d\d) ===", l)
    if m and not m.group(1).startswith(("GREG TEST", "DONE", "GREG COMPLETION")):
        banners.append((m.group(1), mins_of(l), i))
done_count = sum(1 for l in lines if "DONE @ step" in l)

cur = banners[-1] if banners and not any("DONE @ step" in x for x in lines[banners[-1][2]:]) else None
target = cur_step = ema = nodes = it_s = None
region = lines[cur[2]:] if cur else lines
for l in region:
    mt = re.search(r"steps=(\d+)", l)
    if mt: target = int(mt.group(1))
    ms = re.search(r"step\s+(\d+) \| train_ce [\d.]+ \| ema ([\d.]+) \| nodes (\d+) \| layers \d+ \| ([\d.]+) it/s", l)
    if ms: cur_step, ema, nodes, it_s = int(ms.group(1)), float(ms.group(2)), int(ms.group(3)), float(ms.group(4))

diffs = [((b[1] - a[1]) % (24 * 60)) for a, b in zip(banners, banners[1:]) if a[1] is not None and b[1] is not None]
avg_min = (sum(diffs) / len(diffs)) if diffs else None
eta_arm = (target - cur_step) / it_s if (cur and it_s and target and cur_step is not None) else None

print("=" * 58)
print(" GREG TEST — live status" + (f"   ({os.path.basename(LOG)})" if "completion" in LOG else ""))
print("=" * 58)
print(f"  arms: {done_count}/{planned} done" if planned else f"  arms done: {done_count}")
if cur:
    print(f"  running: {cur[0]}")
    if cur_step is not None and target:
        print(f"    step {cur_step}/{target} ({100*cur_step/target:.0f}%)   ema {ema}   nodes {nodes}   {it_s} it/s   ETA {fmt(eta_arm)}")
    else:
        print("    (warming up base / no step logged yet)")
    if avg_min and planned:
        rem = max(0, planned - done_count - 1)
        print(f"    ~{avg_min:.0f} min/arm so far  ->  whole run ETA ~{fmt((eta_arm or 0) + rem * avg_min * 60)}")
else:
    print("  (between arms or finished — check the ranking below)")

print("-" * 58)
print("  ranking so far   (in-held / OOD bits/byte, lower = better):")
rows = []
for label, mm, idx in banners:
    nxt = next((b[2] for b in banners if b[2] > idx), len(lines))
    evs = [l for l in lines[idx:nxt] if "[eval@" in l]
    fin = any("DONE @ step" in l for l in lines[idx:nxt])
    if evs:
        me = re.search(r"in-held ([\d.]+) \| OOD ([\d.]+)", evs[-1])
        if me: rows.append((float(me.group(2)), label.split(" ")[0], me.group(1), me.group(2), fin))
for ood, name, ih, od, fin in sorted(rows):
    print(f"    {name:<12} {ih:>7} / {od:<7} {'' if fin else '(running)'}")

print("-" * 58)
print("  recent:")
feed = [l for l in lines if any(k in l for k in ("[eval@", "[grow]", "DONE @ step", "folders spawned"))][-5:]
for l in feed: print("   ", l.strip()[:72])
print("=" * 58)
