#!/bin/bash
# ==================================================================================================
# READ THE 2026-09-24 WORLD FLEET'S ARCHIVE FOR THE FOUR THINGS ITS TRANSCRIBED ANALYSIS LEFT OUT
# ==================================================================================================
# Proposal 05 §8 0.2. results/gpu_world_2026-09-24/ANALYSIS.txt was transcribed from the owner's
# terminal; the logs and curves stayed on the GPU box (gpu_world_out/, or gpu_world_2026-09-24.tgz).
# Four register rows wait on lines only those logs hold:
#   LOW-D-A13            the data banner: which data source the fleet trained on (protocol=generated
#                        is the default synthetic source, whose text varies with RUN_SEED)
#   DECISIONS-Q-CAP-2    the n_live trajectory: does the population settle from FAB_N0=2048, and where
#   CONTRACT-Q-FAB-5     fab.experts_past_grace_ever and the cull / merge / rescue counts
#   CONTRACT-Q-OPT-3     opt.grad_norm p50 / p99 at the end, per arm
# and two more for O20 / NEW-20 (2026-09-27, Proposal 05 §8 1.5): one row per run and one pooled line,
# all they add to the block. The '-- per run' header line names the row and what freed/pass is; the
# pooled line says the lines off the ceiling read a pass's dip, and that the drops are a LOWER BOUND.
#   AT THE CEILING       FAB_SLOTS (off the growth gate's text, else any FAB_SLOTS= in the log, else
#                        SUMMARY.txt's EXTRA, else the lever's 4096, labelled assumed; in that order,
#                        as one fleet's arms can run at different ceilings), the first progress window
#                        with n_live >= FAB_SLOTS, the windows from there to the run's end ('=== N
#                        windows') as a share of the run, and how many progress lines from there on
#                        read n_live at FAB_SLOTS. The lines are 100 windows apart and one lands a
#                        window after each manage pass and reads its dip, so the count is a sample,
#                        not the time at it.
#   SLOTS FREED PER PASS the drops in n_live between consecutive progress lines whose earlier line is
#                        within 2% of FAB_SLOTS (median, max, count; a dip from further below, as a
#                        pass before the fill makes, is not counted): a LOWER BOUND, because spawns
#                        refill between the lines and the logs carry no per-pass count; beside it the
#                        whole run's fab.merged + fab.cull_fail + fab.cull_util (each frees one slot)
#                        over fab.manage_passes. The pooled line leaves out arms named *_rerun
#                        (replicates of another run).
# It READS ONLY. It writes one file, PASTE_BACK_archive.txt, next to where it is run, and prints the
# same block; copy the block from "==== PASTE THIS BACK ====" to "==== END ====" into the chat.
#
#     bash tools/read_fleet_archive.sh                          # ./gpu_world_out, else the .tgz
#     bash tools/read_fleet_archive.sh path/to/gpu_world_out    # an unpacked fleet directory
#     bash tools/read_fleet_archive.sh path/to/gpu_world_2026-09-24.tgz
set -u
SRC=${1:-}
if [[ -z "$SRC" ]]; then
  if [[ -d gpu_world_out/logs ]]; then SRC=gpu_world_out
  elif [[ -f gpu_world_2026-09-24.tgz ]]; then SRC=gpu_world_2026-09-24.tgz
  else echo "no gpu_world_out/ or gpu_world_2026-09-24.tgz here; pass the path: bash $0 <dir-or-tgz>"; exit 1; fi
fi
TMP=""
if [[ -f "$SRC" ]]; then
  TMP=$(mktemp -d); tar -xzf "$SRC" -C "$TMP" || { echo "could not unpack $SRC"; exit 1; }
  SRC=$(dirname "$(find "$TMP" -type d -name logs | head -1)")
  [[ -d "$SRC/logs" ]] || { echo "no logs/ directory inside the archive"; exit 1; }
fi
python3 - "$SRC" <<'PY' | tee PASTE_BACK_archive.txt
import glob, os, re, statistics, sys
src = sys.argv[1]
logs = sorted(glob.glob(os.path.join(src, "logs", "*.log")))
logs = [l for l in logs if not os.path.basename(l).startswith("_")]
print("==== PASTE THIS BACK ====")
print(f"archive read: {src}  ({len(logs)} run logs)")
if not logs:
    print("NO RUN LOGS FOUND"); print("==== END ===="); sys.exit(0)
COUNTERS = ("fab.experts_past_grace_ever", "fab.cull_fail", "fab.cull_util", "fab.merged",
            "fab.n_live", "part.n_culled", "part.n_merged", "part.n_cull_candidates",
            "opt.grad_norm.p50", "opt.grad_norm.p99", "opt.grad_norm.samples")
def counters(t):
    r = {}
    for m in re.finditer(r"^\s+([a-z_]+\.[\w.]+)\s+(\S+)\s*$", t, re.M):
        if m.group(1) in COUNTERS or m.group(1).startswith("fab.rescue"):
            r[m.group(1)] = m.group(2)
    return r
first = open(logs[0], errors="replace").read()
m = re.search(r"^=== data plan:.*?(?=^===|\Z)", first, re.M | re.S)
print("-- data banner (first log, " + os.path.basename(logs[0]) + "):")
for line in ([x for x in m.group(0).splitlines() if not x.startswith("[")][:8] if m else ["(no '=== data plan' block found)"]):
    print("   " + line.strip()[:150])
srcs = set()
for l in logs:
    mm = re.search(r"^=== data plan: protocol=(\w+)", open(l, errors="replace").read(), re.M)
    srcs.add(mm.group(1) if mm else "?")
print(f"-- data protocol across all logs: {sorted(srcs)}")
# O20 / NEW-20: THE POOL AT ITS CEILING, off the progress lines (the header says what each figure is).
sm = os.path.join(src, "SUMMARY.txt")
sm = re.search(r"^=== \d+ windows per run, .*?EXTRA='(.*)'$", open(sm, errors="replace").read(), re.M) if os.path.exists(sm) else None
EXTRA = sm.group(1) if sm else ""
def pool(t, c, prog):
    sl = (re.search(r"^\s+gate:fab\.growth\s[^\n]*?FAB_SLOTS=(\d+)", t, re.M) or re.search(r"FAB_SLOTS=(\d+)", t)
          or re.search(r"(?:^| )FAB_SLOTS=(\d+)", EXTRA))
    slots = int(sl.group(1)) if sl else 4096
    e = re.search(r"^=== (\d+) windows, ", t, re.M)
    end = int(e.group(1)) if e else (prog[-1][0] if prog else 0)
    fill = next((w for w, n in prog if n >= slots), None)
    after = [n for w, n in prog if fill is not None and w >= fill]
    near = slots - max(1, round(0.02 * slots))
    drops = [n0 - n1 for (w0, n0), (w1, n1) in zip(prog, prog[1:]) if n0 >= near and n1 < n0]
    ks = [k for k in ("fab.merged", "fab.cull_fail", "fab.cull_util") if k in c]
    freed = sum(int(float(c[k])) for k in ks) if ks else None
    mp = re.search(r"^\s+fab\.manage_passes\s+(\d+)\s*$", t, re.M)
    me = re.search(r"^\s+fab\.manage_every_windows\s+(\d+)\s*$", t, re.M)
    return dict(slots=slots, lab=f"{slots}" + ("" if sl else " (assumed)"), end=end, fill=fill,
                at=sum(n >= slots for n in after), after=len(after), drops=drops, freed=freed,
                passes=int(mp.group(1)) if mp else None, every=int(me.group(1)) if me else None,
                gap=prog[1][0] - prog[0][0] if len(prog) > 1 else None,
                top=max(prog, key=lambda q: q[1]) if prog else None)
def share(p):
    return 100 * (p["end"] - p["fill"]) / max(1, p["end"])
def pool_row(p):
    head = (f"ceiling {p['lab']} from w{p['fill']}: {p['end'] - p['fill']} of {p['end']} w to the end ({share(p):.1f}%), "
            f"at it on {p['at']}/{p['after']} lines" if p["fill"] is not None else
            f"ceiling {p['lab']} never reached (max n_live {p['top'][1]} at w{p['top'][0]})" if p["top"] else
            f"ceiling {p['lab']}: no progress lines")
    d = p["drops"]
    fr = (f"freed/pass >= med {statistics.median(d):g}, max {max(d)} ({len(d)} drop{'s' * (len(d) != 1)})" if d else
          "freed/pass: no drop near it")
    mc = ("merged+culled " + (f"{p['freed']} in {p['passes']} pass{'es' * (p['passes'] != 1)} ({p['freed'] / max(1, p['passes']):.1f}/pass, "
                               "whole run)"
                              if p["freed"] is not None and p["passes"] is not None else
                              f"{p['freed']}, passes absent" if p["freed"] is not None else "absent"))
    return f"{head}; {fr}; {mc}"
POOL = {}
print("-- per run: n_live at windows 0/2k/5k/10k/15k/20k (from progress lines); final counters; the pool at FAB_SLOTS "
      "from its first line there (O20, NEW-20; freed/pass: n_live drops between lines from within 2% of it)")
for l in logs:
    t = open(l, errors="replace").read()
    c = counters(t)
    prog = [(int(a), int(b)) for a, b in re.findall(r"^\[(\d+) windows\].*?n_live=(\d+)", t, re.M)]
    marks = []
    for w in (0, 2000, 5000, 10000, 15000, 20000):
        near = [p for p in prog if p[0] <= w] if w else prog[:1]
        if near:
            marks.append(f"{near[-1][0]}:{near[-1][1]}")
    def fmt(v):
        try:
            f = float(v)
            return str(int(f)) if f == int(f) else f"{f:.4g}"
        except ValueError:
            return v
    short = {k.replace("opt.grad_norm.", "gn.").replace("fab.", "").replace("part.", "p."): fmt(v)
             for k, v in c.items()}
    print(f"  {os.path.basename(l)[:-4]:<18} n_live {' '.join(marks) or '(no progress lines)'}")
    print(f"  {'':<18} " + " ".join(f"{k}={v}" for k, v in sorted(short.items())))
    POOL[os.path.basename(l)[:-4]] = p = pool(t, c, prog)
    print(f"  {'':<18} " + pool_row(p))
P = {k: v for k, v in POOL.items() if not k.split(".")[0].endswith("_rerun")}
F = [p for p in P.values() if p["fill"] is not None]
D = [d for p in P.values() for d in p["drops"]]
ev = sorted({p["every"] for p in P.values() if p["every"]}); gp = sorted({p["gap"] for p in P.values() if p["gap"]})
S = [share(p) for p in F]; A = [100 * p["at"] / p["after"] for p in F]
print(f"-- pool, {len(P)} runs (*_rerun left out): {len(F)}/{len(P)} reach the ceiling"
      + (f"; fill to end {min(S):.1f}-{max(S):.1f}% of the run (median {statistics.median(S):.1f}%); at it on "
         f"{min(A):.1f}-{max(A):.1f}% of the lines from the fill on (the rest read a pass's dip)" if F else "")
      + (f"; freed/pass >= med {statistics.median(D):g} ({min(D)}-{max(D)}, {len(D)} drops), a LOWER BOUND from the "
         "sampling (no log holds the per-pass count)" if D else "; no drop near it")
      + f"; passes every {'/'.join(map(str, ev)) or '?'} w, lines every {'/'.join(map(str, gp)) or '?'} w"
      + (" (a drop can span passes)" if ev and gp and min(ev) < max(gp) else ""))
print("==== END ====")
PY
[[ -n "$TMP" ]] && rm -rf "$TMP"
echo "(also written to $(pwd)/PASTE_BACK_archive.txt)"
