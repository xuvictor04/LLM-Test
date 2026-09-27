"""O20: per-run pool trajectory from the 2026-09-24 fleet archive (scratch, read-only).
Reads the extracted archive at ../arc/gpu_world_out/logs."""
import re, glob, os, statistics
LOGS = os.path.join(os.path.dirname(__file__), "..", "arc", "gpu_world_out", "logs")
rows = []
for f in sorted(glob.glob(os.path.join(LOGS, "*.log"))):
    name = os.path.basename(f)[:-4]
    txt = open(f).read()
    prog = [(int(w), int(n)) for w, n in re.findall(r"^\[(\d+) windows\].*?n_live=(\d+)", txt, re.M)]
    c = {}
    for k in ("fab.spawned", "fab.spawn_declined", "fab.cull_fail", "fab.cull_util", "fab.merged",
              "fab.births", "fab.n_live", "fab.experts_past_grace_ever", "fab.manage_passes"):
        m = re.search(r"^\s+" + re.escape(k) + r"\s+(\S+)", txt, re.M)
        c[k] = float(m.group(1)) if m else None
    first_full = next((w for w, n in prog if n >= 4096), None)
    after = [n for w, n in prog if first_full is not None and w > first_full]
    frees = c["fab.cull_fail"] + c["fab.cull_util"] + c["fab.merged"]
    rows.append((name, first_full, min(after) if after else None, len(prog), c, frees))
print(f"{'run':18s} first_full  min_after  spawned declined  demand  frees(cf+cu+mg)  past_grace passes")
ff = []
for name, first_full, mn, npg, c, frees in rows:
    demand = c["fab.spawned"] + c["fab.spawn_declined"]
    print(f"{name:18s} {str(first_full):>10s} {str(mn):>10s} {c['fab.spawned']:7.0f} {c['fab.spawn_declined']:8.0f} {demand:7.0f} {frees:10.0f}   {c['fab.experts_past_grace_ever']:6.0f} {c['fab.manage_passes']:4.0f}")
    if first_full is not None and name != "fb_off_rerun.s0":
        ff.append(first_full)
print("progress lines per log:", rows[0][3])
print("distinct runs reaching 4096 (rerun excluded):", len(ff), "of", len([r for r in rows if r[0] != 'fb_off_rerun.s0']))
print("first-full windows (distinct runs): min", min(ff), "median", statistics.median(ff), "max", max(ff))
allff = [r[1] for r in rows if r[1] is not None]
print("first-full windows (all 21 logs): n", len(allff), "min", min(allff), "median", statistics.median(allff), "max", max(allff))
dem = [r[4]["fab.spawned"] + r[4]["fab.spawn_declined"] for r in rows]
fr = [r[5] for r in rows]
print("spawn demand range", min(dem), max(dem), "; frees range", min(fr), max(fr))
# frees per window after full, crude: frees over whole run / 20000 is a lower bound on the rate once full? report both
for name, first_full, mn, npg, c, frees in rows:
    pass
