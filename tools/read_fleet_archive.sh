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
import glob, os, re, sys
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
print("-- per run: final counters; n_live at windows 0/2k/5k/10k/15k/20k (from progress lines)")
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
print("==== END ====")
PY
[[ -n "$TMP" ]] && rm -rf "$TMP"
echo "(also written to $(pwd)/PASTE_BACK_archive.txt)"
