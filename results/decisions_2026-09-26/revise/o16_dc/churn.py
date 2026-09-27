"""O20: full-pool time and churn after the pool fills, from the 2026-09-24 fleet archive (scratch).
fab.spawn_declined counts spawn tests that RAN and said no; at a full pool the test does not run
(src/fabric/api.py:2079-2085 returns None; :2484-2488 counts a decline only when a gap was measured).
At OPT_BATCH_WINDOWS 1 one test runs per window, so windows at the ceiling = 20000 - spawned - declined."""
import re, glob, os, statistics
LOGS = os.path.join(os.path.dirname(__file__), "..", "arc", "gpu_world_out", "logs")
out = []
for f in sorted(glob.glob(os.path.join(LOGS, "*.log"))):
    name = os.path.basename(f)[:-4]
    if name == "fb_off_rerun.s0":
        continue  # bit-identical to fb_off.s0
    txt = open(f).read()
    prog = {int(w): int(n) for w, n in re.findall(r"^\[(\d+) windows\].*?n_live=(\d+)", txt, re.M)}
    g = lambda k: float(re.search(r"^\s+" + re.escape(k) + r"\s+(\S+)", txt, re.M).group(1))
    sp, dc = g("fab.spawned"), g("fab.spawn_declined")
    full_w = 20000 - sp - dc
    first = min((w for w, n in prog.items() if n >= 4096), default=None)
    # dips one window after each manage pass (passes at multiples of 500), after first fill
    dips = [4096 - prog[w] for w in sorted(prog) if first and w > first and (w - 1) % 500 == 0]
    post = (20000 - first) if first else 0
    share = full_w / post if post else None
    out.append((name, first, full_w, post, share, dips))
    print(f"{name:15s} first_full={str(first):>6s} windows_full={full_w:7.0f} of post-fill {post:6d} "
          f"share={'' if share is None else f'{share:.3f}'} dips/pass mean={statistics.mean(dips) if dips else 0:.1f} "
          f"max={max(dips) if dips else 0} passes={len(dips)}")
fulls = [o[2] for o in out]
print("windows at the ceiling per run (20 distinct runs): min", min(fulls), "median", statistics.median(fulls), "max", max(fulls))
sh = [o[4] for o in out if o[4] is not None]
print("share of post-fill windows at the ceiling (19 runs): min %.3f median %.3f max %.3f" % (min(sh), statistics.median(sh), max(sh)))
alld = [d for o in out for d in o[5]]
print("slots freed per manage pass after fill (read 1 window after the pass): n", len(alld), "median", statistics.median(alld), "min", min(alld), "max", max(alld))
