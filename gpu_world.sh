#!/bin/bash
# ==================================================================================================
# THE Q-WORLD-10 GPU EXPERIMENT, RUN AS A FLEET THAT FILLS THE CARD
# ==================================================================================================
# WHAT IT DECIDES. Whether WORLD_FEEDBACK stays True (the forecast wired into LM.encode, world_proj
# born zero) and, if it helps, whether the help is WORLD MODELLING or just added capacity. The
# protocol is the judge's from Q-WORLD-10 in docs/04_CONTRACT.md:
#
#   fb_off     WORLD_FEEDBACK=0                          the control; bit-identical to the tree before
#                                                        the forecast had a call site
#   fb_on      the defaults                              wired, world_proj born zero
#   skip       WORLD_PREDICT_W=0 WORLD_COLLAPSE_W=0      the same forecast network in the forward,
#                                                        trained ONLY by the LM loss: the CAPACITY
#                                                        control
#   world_off  WORLD_ENABLED=0                           prices the whole subsystem
#
# plus fb_off seed 0 run TWICE, which measures this card's run-to-run floor (cuDNN's GRU is not
# guaranteed bit-exact, so "identical seed" is not "identical run" on a GPU until measured).
# Metric: per seed, the mean over the LAST HALF of the per-flush loss curve of (arm - fb_off), then
# mean +- SE across seeds and how many seeds come out negative. RUN_EPOCHS=1, so the last half is
# prequential loss on text the model has not trained on yet.
#
# WHY A FLEET AND NOT ONE BIG RUN. One run of this model is LAUNCH-BOUND: sweep_gpu.sh measured the
# best single arm at 30.8% utilisation of an H100 with 1.8 GiB of its 79 in use. A bigger batch
# would fill it but changes the experiment (fewer optimizer steps per window, which sweep_gpu.sh
# showed trades directly against learning). What fills the card WITHOUT changing the experiment is
# running the independent seeds and arms CONCURRENTLY: every process keeps its own geometry and
# step count, and the card interleaves their kernels. So this script:
#   1. smokes every arm for SMOKE_WINDOWS on the card (fails fast, checks each arm's tripwires,
#      measures one process's memory and speed),
#   2. sizes the parallelism from GPU memory, GPU count and CPU cores (each process needs one core
#      to launch its kernels),
#   3. starts CUDA MPS when it can (kernels from different processes then run SIMULTANEOUSLY
#      instead of time-slicing; the numbers each process computes are unchanged),
#   4. FILLS spare slots with extra seeds -- more seeds is the one use of spare card that makes the
#      decision sharper rather than just faster,
#   5. samples nvidia-smi through the whole fleet and says whether the card was actually full,
#   6. analyses the curves and prints the decision.
#
#     bash gpu_world.sh                                   # 20,000 windows, seeds 0-4, auto-filled
#     WINDOWS=5000 bash gpu_world.sh                      # a quicker first look
#     EXTRA="LM_WIDTH=512 LM_LAYERS=2" bash gpu_world.sh  # your standard geometry, applied to EVERY arm
#     ARCH_ALSO=transformer bash gpu_world.sh             # + fb_off/fb_on at LM_ARCH=transformer
#     LONG=100000 bash gpu_world.sh                       # + one fb_on/fb_off pair (seed 0) that long
#     PAR=12 MPS=0 FILL=0 bash gpu_world.sh               # manual parallelism, no MPS, no extra seeds
#     cat gpu_world_out/SUMMARY.txt
#
# IT WRITES NO CHECKPOINTS AND TOUCHES NOTHING IN runs/. CKPT_DIR is left unset on purpose: saving
# is the most expensive operation in the loop, and nothing here needs to be resumed.
# DEVICE=cpu runs the same pipeline without the GPU parts; it exists so the script itself can be
# tested on a machine without a card, and its numbers mean nothing about the GPU.
set -u

OUT=${OUT:-gpu_world_out}
WINDOWS=${WINDOWS:-20000}
SEEDS=${SEEDS:-"0 1 2 3 4"}
# DATA_STREAM_BYTES >= 1000 x windows, so every run stops at --max-windows and never at the end of
# the stream. A run that ran out of stream is flagged in the summary; it is a different length of
# experiment wearing the same label.
BYTES=${BYTES:-$(( WINDOWS * 1000 > 2000000 ? WINDOWS * 1000 : 2000000 ))}
SMOKE_WINDOWS=${SMOKE_WINDOWS:-60}
EXTRA=${EXTRA:-}
ARCH_ALSO=${ARCH_ALSO:-}
LONG=${LONG:-0}
PAR=${PAR:-auto}
MPS=${MPS:-auto}
FILL=${FILL:-1}
MAX_SEEDS=${MAX_SEEDS:-16}
DEVICE=${DEVICE:-cuda}

cd "$(dirname "$0")"
mkdir -p "$OUT/logs" "$OUT/curves" "$OUT/smoke"
S="$OUT/SUMMARY.txt"
: > "$S"
say() { echo "$*" | tee -a "$S"; }

# ---------------------------------------------------------------- preflight
say "=== gpu_world.sh  $(date -u +%Y-%m-%dT%H:%M:%SZ)  commit $(git rev-parse --short HEAD 2>/dev/null)"
NCPU=$(nproc)
NGPU=0
GPU_MEM_MIB=0
if [[ "$DEVICE" == cuda ]]; then
  if ! command -v nvidia-smi >/dev/null; then say "!! nvidia-smi not found. DEVICE=cuda needs a GPU."; exit 1; fi
  if ! python3 -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"; then
    say "!! torch sees no CUDA device. Every arm sets RUN_DEVICE=cuda, and RUN.process_setup takes"
    say "!! it verbatim with no fallback, so each would raise at its first .to(). Stopping here."
    exit 1
  fi
  NGPU=$(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l)
  GPU_MEM_MIB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')
  nvidia-smi --query-gpu=index,name,memory.total,memory.used --format=csv | sed 's/^/    /' | tee -a "$S"
fi
say "=== $NCPU CPU core(s), $NGPU GPU(s), device=$DEVICE"
say "=== $WINDOWS windows per run, DATA_STREAM_BYTES=$BYTES, seeds: $SEEDS, EXTRA='$EXTRA'"
say ""

# every process: one CPU thread (N processes x torch's default of one thread per core is how this
# project once measured a 60x slowdown), the card, the seed, the stream, the shared geometry.
run_job() {  # name seed windows gpu arm-env...
  local name="$1" seed="$2" win="$3" gpu="$4"; shift 4
  local tag="$name.s$seed"
  local log="$OUT/logs/$tag.log" t0=$(date +%s)
  [[ -n "${JOB_DIR:-}" ]] && log="$JOB_DIR/$tag.log"
  local vis=()
  [[ "$DEVICE" == cuda ]] && vis=(CUDA_VISIBLE_DEVICES="$gpu")
  env "${vis[@]}" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 RUN_DEVICE="$DEVICE" RUN_SEED="$seed" \
      DATA_STREAM_BYTES="$BYTES" $EXTRA "$@" \
      python3 run.py --max-windows "$win" --loss-curve "${CURVE_DIR:-$OUT/curves}/$tag.json" \
      > "$log" 2>&1
  local rc=$?
  echo "$tag rc=$rc secs=$(( $(date +%s) - t0 ))" >> "${JOB_DIR:-$OUT/logs}/_done.txt"
  return $rc
}

# a job line is: name seed windows arm-env...   (arm-env may be empty)
declare -a JOBS=()
add_job() { JOBS+=("$*"); }

arm_env() {  # the lever settings that define each arm
  case "$1" in
    fb_off)    echo "WORLD_FEEDBACK=0" ;;
    fb_on)     echo "" ;;
    skip)      echo "WORLD_PREDICT_W=0.0 WORLD_COLLAPSE_W=0.0" ;;
    world_off) echo "WORLD_ENABLED=0" ;;
  esac
}
BASE_ARMS="fb_off fb_on skip world_off"

run_fleet() {  # runs JOBS with $1 slots, round-robin over GPUs
  local slots="$1" i=0 running=0
  : > "${JOB_DIR:-$OUT/logs}/_done.txt"
  for line in "${JOBS[@]}"; do
    # shellcheck disable=SC2086
    set -- $line
    local name="$1" seed="$2" win="$3"; shift 3
    local gpu=0
    [[ "$NGPU" -gt 0 ]] && gpu=$(( i % NGPU ))
    run_job "$name" "$seed" "$win" "$gpu" "$@" &
    i=$(( i + 1 )); running=$(( running + 1 ))
    if [[ "$running" -ge "$slots" ]]; then wait -n; running=$(( running - 1 )); fi
  done
  wait
}

# ---------------------------------------------------------------- 1. smoke every arm
say "---- 1. smoke: every arm, seed 0, $SMOKE_WINDOWS windows, all at once"
JOBS=()
for a in $BASE_ARMS; do add_job "$a 0 $SMOKE_WINDOWS $(arm_env $a)"; done
if [[ -n "$ARCH_ALSO" ]]; then
  for a in fb_off fb_on; do add_job "${a}@$ARCH_ALSO 0 $SMOKE_WINDOWS LM_ARCH=$ARCH_ALSO $(arm_env $a)"; done
fi
JOB_DIR="$OUT/smoke" CURVE_DIR="$OUT/smoke" run_fleet "${#JOBS[@]}"
if grep -q "rc=[1-9]" "$OUT/smoke/_done.txt"; then
  say "!! a smoke arm FAILED -- stopping before the fleet:"
  grep "rc=[1-9]" "$OUT/smoke/_done.txt" | sed 's/^/    /' | tee -a "$S"
  for f in $(grep "rc=[1-9]" "$OUT/smoke/_done.txt" | cut -d' ' -f1); do
    say "    --- $f (last 8 lines)"; tail -8 "$OUT/smoke/$f.log" | sed 's/^/      /' | tee -a "$S"
  done
  exit 1
fi
# the tripwires and the sizing numbers, read off the smoke logs
SIZING=$(python3 - "$OUT/smoke" "$DEVICE" <<'PY' | tee -a "$S"
import re, sys, glob, os
d, dev = sys.argv[1], sys.argv[2]
def rep(t):
    out = {}
    for m in re.finditer(r"^\s+([A-Za-z_][\w.@()-]*\.[\w.@()-]+)\s+(\S+)\s*$", t, re.M):
        out[m.group(1)] = m.group(2)
    return out
bad, peak, wps = [], 0.0, []
for log in sorted(glob.glob(os.path.join(d, "*.log"))):
    t = open(log).read(); r = rep(t); arm = os.path.basename(log).split(".s")[0].split("@")[0]
    if dev == "cuda" and "device=cuda" not in t:
        bad.append(f"{arm}: the banner does not say device=cuda")
    fc, ea, built = r.get("world.forecasts"), r.get("lm.encode.extra_applied"), r.get("world.built")
    if arm in ("fb_on", "skip") and (ea is None or ea != fc):
        bad.append(f"{arm}: expected world.forecasts == lm.encode.extra_applied, got {fc} / {ea}")
    if arm == "fb_off" and ea is not None:
        bad.append(f"{arm}: lm.encode.extra_applied is PRESENT ({ea}) on the unwired control")
    if arm == "world_off" and built != "null":
        bad.append(f"{arm}: world.built is {built!r}, expected 'null'")
    m = re.search(r"peak CUDA memory [\d.]+ GiB allocated, ([\d.]+) GiB reserved", t)
    if m: peak = max(peak, float(m.group(1)))
    m = re.search(r"=== (\d+) windows[^\n]*? in ([\d.]+)s", t)
    if m and float(m.group(2)) > 0: wps.append(int(m.group(1)) / float(m.group(2)))
for b in bad: print("  TRIPWIRE:", b)
print(f"  smoke: {len(glob.glob(os.path.join(d, '*.log')))} arm(s) ran; peak reserved {peak:.3f} GiB per process; "
      f"{min(wps) if wps else 0:.1f}-{max(wps) if wps else 0:.1f} windows/s per process while all ran at once")
print(f"SIZING peak_gib={peak:.4f} wps={min(wps) if wps else 0:.3f} bad={len(bad)}")
PY
)
if echo "$SIZING" | grep -q "bad=[1-9]"; then say "!! a tripwire failed in the smoke -- stopping before the fleet."; exit 1; fi
PEAK_GIB=$(echo "$SIZING" | sed -n 's/.*peak_gib=\([0-9.]*\).*/\1/p')
SMOKE_WPS=$(echo "$SIZING" | sed -n 's/.*wps=\([0-9.]*\).*/\1/p')

# ---------------------------------------------------------------- 2. the job list and its size
JOBS=()
for s in $SEEDS; do for a in $BASE_ARMS; do add_job "$a $s $WINDOWS $(arm_env $a)"; done; done
add_job "fb_off_rerun 0 $WINDOWS $(arm_env fb_off)"
if [[ -n "$ARCH_ALSO" ]]; then
  for s in $SEEDS; do for a in fb_off fb_on; do add_job "${a}@$ARCH_ALSO $s $WINDOWS LM_ARCH=$ARCH_ALSO $(arm_env $a)"; done; done
fi
if [[ "$LONG" -gt 0 ]]; then
  for a in fb_off fb_on; do add_job "${a}_long 0 $LONG $(arm_env $a)"; done
fi

# the slots: CPU cores leave one for this shell and nvidia-smi; GPU memory takes the smoke's peak
# reserved plus a CUDA context (~0.5 GiB without MPS) with 50% headroom, since a 20,000-window run
# grows its allocator past a 60-window one.
if [[ "$PAR" == auto ]]; then
  CPU_SLOTS=$(( NCPU > 1 ? NCPU - 1 : 1 ))
  if [[ "$DEVICE" == cuda ]]; then
    MEM_SLOTS=$(python3 -c "import math; print(max(1, int(0.85*$GPU_MEM_MIB/1024 / (1.5*$PEAK_GIB + 0.5)) * $NGPU))")
  else
    MEM_SLOTS=$CPU_SLOTS
  fi
  PAR=$(( CPU_SLOTS < MEM_SLOTS ? CPU_SLOTS : MEM_SLOTS ))
  say "=== parallelism: $CPU_SLOTS slot(s) by CPU, $MEM_SLOTS by GPU memory -> PAR=$PAR"
  if [[ "$CPU_SLOTS" -lt "$MEM_SLOTS" ]]; then
    say "    CPU-bound: each process drives its own kernel launches from one core, so this box's"
    say "    $NCPU cores, not the card's memory, cap how many runs share the GPU."
  fi
fi

# FILL: spare slots become extra seeds, added to EVERY base arm so the pairing stays complete.
if [[ "$FILL" == 1 && "${#JOBS[@]}" -lt "$PAR" ]]; then
  n_seeds=$(echo $SEEDS | wc -w); next=$(( $(echo $SEEDS | tr ' ' '\n' | sort -n | tail -1) + 1 ))
  added=""
  while [[ $(( ${#JOBS[@]} + 4 )) -le "$PAR" && "$n_seeds" -lt "$MAX_SEEDS" ]]; do
    for a in $BASE_ARMS; do add_job "$a $next $WINDOWS $(arm_env $a)"; done
    added="$added $next"; next=$(( next + 1 )); n_seeds=$(( n_seeds + 1 ))
  done
  [[ -n "$added" ]] && say "=== FILL: spare slots -> extra seeds$added on every base arm (now $n_seeds seeds)"
fi
say "=== ${#JOBS[@]} run(s), $PAR at a time"
# THE ETA IS A FLOOR, AND SAYS SO. It is priced at the slowest per-process rate the smoke measured
# with every arm running at once; at PAR processes the card is busier than it was in the smoke, so
# each process runs at or below that rate. Read it as "not sooner than", not as a promise.
python3 - "$SMOKE_WPS" "${#JOBS[@]}" "$PAR" "$WINDOWS" "$LONG" <<'PY' | tee -a "$S"
import math, sys
wps, jobs, par, win, long_ = float(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
if wps > 0:
    waves = math.ceil(jobs / max(par, 1))
    hrs = waves * win / wps / 3600
    extra = f"; the LONG pair adds at least {long_ / wps / 3600:.1f} h" if long_ else ""
    print(f"=== ETA: at least {hrs:.1f} h ({waves} wave(s) of {par}, {win} windows each at <= {wps:.1f} windows/s per process){extra}")
PY

# ---------------------------------------------------------------- 3. MPS
MPS_ON=0
if [[ "$DEVICE" == cuda && "$MPS" != 0 ]] && command -v nvidia-cuda-mps-control >/dev/null; then
  export CUDA_MPS_PIPE_DIRECTORY="$PWD/$OUT/mps/pipe" CUDA_MPS_LOG_DIRECTORY="$PWD/$OUT/mps/log"
  mkdir -p "$CUDA_MPS_PIPE_DIRECTORY" "$CUDA_MPS_LOG_DIRECTORY"
  if nvidia-cuda-mps-control -d 2>/dev/null; then
    MPS_ON=1; say "=== CUDA MPS started (kernels from different runs execute concurrently)"
    trap 'echo quit | nvidia-cuda-mps-control >/dev/null 2>&1' EXIT
  else
    unset CUDA_MPS_PIPE_DIRECTORY CUDA_MPS_LOG_DIRECTORY
    say "=== CUDA MPS could not start (permissions or GPU mode); runs will time-slice instead"
  fi
elif [[ "$DEVICE" == cuda && "$MPS" != 0 ]]; then
  say "=== nvidia-cuda-mps-control not installed; runs will time-slice the GPU instead of sharing it"
fi

# ---------------------------------------------------------------- 4. the fleet, with a sampler
say "---- 2. fleet started $(date -u +%H:%M:%SZ)"
SMI_PID=""
if [[ "$DEVICE" == cuda ]]; then
  nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total \
             --format=csv,noheader,nounits -l 2 > "$OUT/smi.csv" 2>/dev/null &
  SMI_PID=$!
fi
T0=$(date +%s)
run_fleet "$PAR"
T1=$(date +%s)
[[ -n "$SMI_PID" ]] && kill "$SMI_PID" 2>/dev/null
[[ "$MPS_ON" == 1 ]] && { echo quit | nvidia-cuda-mps-control >/dev/null 2>&1; trap - EXIT; }
say "---- fleet finished in $(( (T1 - T0) / 60 )) min"
if grep -q "rc=[1-9]" "$OUT/logs/_done.txt"; then
  say "!! FAILED runs (their logs are in $OUT/logs):"
  grep "rc=[1-9]" "$OUT/logs/_done.txt" | sed 's/^/    /' | tee -a "$S"
fi

# ---------------------------------------------------------------- 5. analysis
python3 - "$OUT" "$DEVICE" "$MPS_ON" "$PAR" "$NCPU" >> "$S" <<'PY'
import glob, json, math, os, re, statistics, sys
out, dev, mps_on, par, ncpu = sys.argv[1], sys.argv[2], sys.argv[3] == "1", int(sys.argv[4]), int(sys.argv[5])

def rep(t):
    r = {}
    for m in re.finditer(r"^\s+([A-Za-z_][\w.@()-]*\.[\w.@()-]+)\s+(\S+)\s*$", t, re.M):
        r[m.group(1)] = m.group(2)
    return r

runs = {}
for log in sorted(glob.glob(os.path.join(out, "logs", "*.log"))):
    tag = os.path.basename(log)[:-4]
    name, seed = tag.rsplit(".s", 1)
    t = open(log).read(); r = rep(t)
    try: curve = json.load(open(os.path.join(out, "curves", tag + ".json")))
    except (OSError, ValueError): curve = None
    m = re.search(r"=== (\d+) windows[^\n]*? in ([\d.]+)s", t)
    vocab = re.findall(r"vocab=(\d+)", t)
    runs[(name, int(seed))] = dict(
        curve=curve, r=r, ok=curve is not None,
        windows=int(m.group(1)) if m else None, secs=float(m.group(2)) if m else None,
        stopped_at_max="stopped at max_windows" in t, nonfinite="non-finite" in t.lower() and "refus" in t.lower(),
        vocab=int(vocab[-1]) if vocab else None, mint=r.get("tok.mint"),
        peak=(re.search(r"peak CUDA memory [\d.]+ GiB allocated, ([\d.]+) GiB reserved", t) or [None, None])[1])

def half(a, b):
    n = min(len(a), len(b)); h = n // 2
    return (sum(a[i] - b[i] for i in range(h, n)) / (n - h), sum(a[i] - b[i] for i in range(n)) / n, n)

def stat(xs):
    m = sum(xs) / len(xs)
    se = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs)) if len(xs) > 1 else float("nan")
    return m, se

print()
print("=== RUNS ===")
for (name, seed), v in sorted(runs.items()):
    wps = v["windows"] / v["secs"] if v["windows"] and v["secs"] else float("nan")
    flags = []
    if not v["ok"]: flags.append("NO CURVE")
    if v["ok"] and not v["stopped_at_max"]: flags.append("RAN OUT OF STREAM (raise BYTES)")
    if v["nonfinite"]: flags.append("NON-FINITE STOP")
    r = v["r"]
    print(f"  {name:<18} s{seed:<3} {v['windows'] or '?':>6} win {wps:6.2f} w/s  vocab {v['vocab']}  mint {v['mint']}"
          f"  extra_ratio {r.get('lm.encode.extra_ratio', '-'):>9} max {r.get('lm.encode.extra_ratio_max', '-'):>9}"
          f"  latent_std {r.get('world.latent_std', '-'):>9}  peak {v['peak'] or '-'} GiB  {' '.join(flags)}")

# the run-to-run floor
a, b = runs.get(("fb_off", 0)), runs.get(("fb_off_rerun", 0))
floor = None
if a and b and a["curve"] and b["curve"]:
    n = min(len(a["curve"]), len(b["curve"]))
    mx = max(abs(a["curve"][i] - b["curve"][i]) for i in range(n))
    floor = abs(half(a["curve"], b["curve"])[0])
    print()
    print(f"=== RUN-TO-RUN FLOOR (fb_off seed 0 twice): max per-flush |diff| {mx:.3g}, "
          f"last-half mean |diff| {floor:.4f}" + ("  -> BIT-EXACT on this card" if mx == 0 else ""))

# paired comparisons against the group's fb_off
print()
print("=== PAIRED AGAINST fb_off (arm - fb_off, same seed; negative = the arm is better) ===")
results = {}
groups = {}
for (name, seed) in runs:
    if name == "fb_off_rerun": continue
    base, _, suffix = name.partition("@")
    long_ = base.endswith("_long")
    key = ("@" + suffix) if suffix else ("_long" if long_ else "")
    groups.setdefault(key, set()).add(name)
for key, names in sorted(groups.items()):
    ctrl = ("fb_off_long" if key == "_long" else "fb_off" + key)
    for name in sorted(names):
        if name == ctrl: continue
        rows = []
        for (n2, seed), v in sorted(runs.items()):
            if n2 != name: continue
            c = runs.get((ctrl, seed))
            if not (v["curve"] and c and c["curve"]): continue
            mismatch = v["vocab"] != c["vocab"] or v["mint"] != c["mint"]
            rows.append((seed,) + half(v["curve"], c["curve"]) + (mismatch,))
        if not rows: continue
        lh, se = stat([r[1] for r in rows]); fr, fse = stat([r[2] for r in rows])
        neg = sum(1 for r in rows if r[1] < 0)
        results[name] = (lh, se, neg, len(rows))
        print(f"  {name:<18} vs {ctrl:<12} last half {lh:+.4f} +- {se:.4f} SE   full run {fr:+.4f} +- {fse:.4f}"
              f"   {neg}/{len(rows)} seeds negative")
        print("      per seed (last half): " + "  ".join(f"s{r[0]} {r[1]:+.4f}" for r in rows))
        if any(r[4] for r in rows):
            print("      !! vocab size or tok.mint differs from fb_off on some seed: per-token nats are then not "
                  "comparable; convert to bits per byte before trusting this row")

# the decision, the judge's rule from Q-WORLD-10
print()
print("=== DECISION (Q-WORLD-10's rule) ===")
fo, sk, wo = results.get("fb_on"), results.get("skip"), results.get("world_off")
if fo:
    lh, se, neg, n = fo
    sig = n > 1 and lh < -2 * se
    if floor is not None and abs(lh) < floor:
        print(f"  fb_on - fb_off ({lh:+.4f}) is SMALLER than this card's run-to-run floor ({floor:.4f}): no decision possible.")
    if neg >= math.ceil(0.8 * n) and sig:
        print(f"  KEEP WORLD_FEEDBACK=True: lower in {neg}/{n} seeds and more than 2 SE below zero ({lh:+.4f} +- {se:.4f}).")
    else:
        print(f"  WITHIN NOISE ({neg}/{n} seeds negative, {lh:+.4f} +- {se:.4f}): the rule says set WORLD_FEEDBACK's "
              f"default to False -- the path would cost kernel launches for nothing.")
    if sk:
        d = sk[0] - lh
        if abs(d) <= max(se, sk[1]) * 2:
            print(f"  skip ~= fb_on ({sk[0]:+.4f} vs {lh:+.4f}): the gain is CAPACITY, not world modelling -- WORLD's "
                  f"own objectives contribute nothing measurable.")
        elif d < 0:
            print(f"  skip BEATS fb_on ({sk[0]:+.4f} vs {lh:+.4f}): WORLD's objectives HURT the forecast path -- revisit "
                  f"WORLD_PREDICT_W / WORLD_COLLAPSE_W or detach the population's input.")
        else:
            print(f"  fb_on beats skip ({lh:+.4f} vs {sk[0]:+.4f}): WORLD's objectives add to the forecast beyond capacity.")
    if wo and wo[0] < lh:
        print(f"  world_off is better than fb_on ({wo[0]:+.4f} vs {lh:+.4f}): the subsystem does not earn its cost.")
else:
    print("  fb_on has no paired rows; nothing to decide.")

# did the card fill
if dev == "cuda":
    print()
    try:
        rows = [l.strip().split(",") for l in open(os.path.join(out, "smi.csv")) if l.strip()]
        util = [float(r[1]) for r in rows]; mem = [float(r[2]) for r in rows]; tot = float(rows[0][3])
        k = len(util) // 10; body = util[k:len(util) - k] or util        # drop the ramp-up and tail-off
        print(f"=== GPU: utilisation mean {statistics.mean(body):.1f}%  median {statistics.median(body):.0f}%  "
              f">=90% on {100 * sum(u >= 90 for u in body) / len(body):.0f}% of samples  "
              f"memory peak {max(mem) / 1024:.1f} of {tot / 1024:.1f} GiB   (MPS {'on' if mps_on else 'off'}, {par} at a time)")
        if statistics.mean(body) < 80:
            why = (f"parallelism is capped by this box's {ncpu} CPU cores" if par >= ncpu - 1 else
                   "raise PAR (GPU memory allows more)")
            print(f"    The card was NOT full: {why}." + ("" if mps_on else " Without MPS the runs time-slice; MPS=1 if it can be enabled."))
    except (OSError, ValueError, IndexError) as e:
        print(f"=== GPU: no utilisation samples ({e})")
PY
say "=== wrote $S"
cat "$S" | sed -n '/=== RUNS ===/,$p'
