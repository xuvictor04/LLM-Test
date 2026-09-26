#!/bin/bash
# ==================================================================================================
# THE Q-WORLD-10 GPU EXPERIMENT, RUN AS A FLEET THAT FILLS THE CARD
# ==================================================================================================
# WHAT IT DECIDED (2026-09-24: within noise, WORLD_FEEDBACK now ships False). Whether WORLD_FEEDBACK stays True (the forecast wired into LM.encode, world_proj
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
#
# EXP=retok RUNS 03b S0b's SHIP-RULE MEASUREMENT INSTEAD (2026-09-26): which TOK_RETOK_EVERY ships,
# now that the mid-epoch act performs a retok. Arms k0 (0, the control: no act), k3000 (the shipped
# value), k1000, and k0_nuis (0 again, with SIG_WARMUP=801 -- a small real perturbation neither the act
# nor TOK reads, so |k0 - k0_nuis| per seed is the paired noise the margin is made of). Metric: each
# run's PREQUENTIAL bits per byte, sum(per-flush loss x LM_CTX) / ln 2 / loop.bytes_scored -- every
# window at RUN_EPOCHS=1 is scored before its update, and bits per byte does not move with the
# segmentation, which is exactly what the arms change. Rule: M = max over seeds |k0 - k0_nuis|; a
# cadence ships if (arm - k0) <= M at EVERY seed; among those the lower mean wins; if none, 0 ships.
#     EXP=retok bash gpu_world.sh                         # 20,000 windows, seeds 0-2, auto-filled
#     EXP=retok bash gpu_world.sh --analyze
set -u

EXP=${EXP:-world}
OUT=${OUT:-$([[ "$EXP" == retok ]] && echo gpu_retok_out || echo gpu_world_out)}
WINDOWS=${WINDOWS:-20000}
SEEDS=${SEEDS:-$([[ "$EXP" == retok ]] && echo "0 1 2" || echo "0 1 2 3 4")}
# DATA_STREAM_BYTES >= 1000 x windows, so every run stops at --max-windows and never at the end of
# the stream. A run that ran out of stream is flagged in the summary; it is a different length of
# experiment wearing the same label.
BYTES=${BYTES:-$(( WINDOWS * 1000 > 2000000 ? WINDOWS * 1000 : 2000000 ))}
# EXP=retok COMPARES THE ARMS OVER THE SAME BYTES, NOT THE SAME WINDOWS. An arm that retokenizes packs
# more bytes into a window, so at a fixed window count it would score a longer stretch of the stream
# than the control and the two averages would be over different text. Every retok run therefore reads
# ONE WHOLE EPOCH of the same stream -- sized so the control takes about WINDOWS windows at the 189
# bytes/window measured on CPU (2026-09-26) -- and the window cap (RUN_WIN) is set out of reach.
if [[ "$EXP" == retok ]]; then
  BYTES=${RETOK_BYTES:-$(( WINDOWS * 189 ))}
  RUN_WIN=$(( WINDOWS * 3 ))
else
  RUN_WIN=$WINDOWS
fi
SMOKE_WINDOWS=${SMOKE_WINDOWS:-60}
EXTRA=${EXTRA:-}
ARCH_ALSO=${ARCH_ALSO:-}
LONG=${LONG:-0}
PAR=${PAR:-auto}
MPS=${MPS:-auto}
FILL=${FILL:-1}
MAX_SEEDS=${MAX_SEEDS:-16}
DEVICE=${DEVICE:-cuda}
CAL_WINDOWS=${CAL_WINDOWS:-150}
LADDER=${LADDER:-"1 2 4 8 12 16 24 32 48 64 96 128"}

cd "$(dirname "$0")"

# bash gpu_world.sh --status : progress and time left of a fleet that is running (or finished),
# read off SUMMARY.txt and the logs. It changes nothing and is safe to run at any time.
# THE ANALYSIS, AS A FUNCTION so --analyze can re-run it on a finished (or interrupted) fleet.
analyze() {  # out device mps_on par ncpu
  if [[ "$EXP" == retok ]]; then analyze_retok "$@"; return; fi
  python3 - "$@" <<'PY'
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
        results[name] = (lh, se, neg, len(rows), {r[0]: r[1] for r in rows})
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
    lh, se, neg, n, fo_seeds = fo
    sig = n > 1 and lh < -2 * se
    if floor is not None and abs(lh) < floor:
        print(f"  fb_on - fb_off ({lh:+.4f}) is SMALLER than this card's run-to-run floor ({floor:.4f}): no decision possible.")
    if neg >= math.ceil(0.8 * n) and sig:
        print(f"  TURN WORLD_FEEDBACK ON (=1): lower in {neg}/{n} seeds and more than 2 SE below zero ({lh:+.4f} +- {se:.4f}).")
    else:
        print(f"  WITHIN NOISE ({neg}/{n} seeds negative, {lh:+.4f} +- {se:.4f}): WORLD_FEEDBACK stays off (its "
              f"default since 2026-09-24) -- the path would cost kernel launches for nothing.")
    if sk:
        # PAIRED, skip - fb_on per seed. The first version compared the two arms' means against the
        # larger of their SEs, so a skip arm that was WORSE on average but wildly variable (+0.09 vs
        # +0.003, one seed at +0.36) was printed as "skip ~= fb_on".
        both = [sk[4][s] - fo_seeds[s] for s in sk[4] if s in fo_seeds]
        d = sum(both) / len(both) if both else sk[0] - lh
        dse = (math.sqrt(sum((x - d) ** 2 for x in both) / (len(both) - 1) / len(both))
               if len(both) > 1 else float("inf"))
        if abs(d) <= 2 * dse:
            print(f"  skip - fb_on = {d:+.4f} +- {dse:.4f} (paired): not separable -- if fb_on helps at all, the help "
                  f"is CAPACITY, not world modelling.")
        elif d < 0:
            print(f"  skip BEATS fb_on ({sk[0]:+.4f} vs {lh:+.4f}): WORLD's objectives HURT the forecast path -- revisit "
                  f"WORLD_PREDICT_W / WORLD_COLLAPSE_W or detach the population's input.")
        else:
            print(f"  fb_on beats skip by {d:+.4f} +- {dse:.4f} (paired): WORLD's own objectives keep the forecast "
                  f"path stable (compare the arms' latent_std and extra_ratio_max).")
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
}

# THE RETOK SHIP RULE (EXP=retok), 03b S0b. Prequential bits/byte per run, paired by seed.
analyze_retok() {  # out device mps_on par ncpu
  python3 - "$@" <<'PY'
import glob, json, math, os, re, sys
out = sys.argv[1]
ctx = int(os.environ.get("CTX", "128"))
runs = {}
for log in sorted(glob.glob(os.path.join(out, "logs", "*.log"))):
    tag = os.path.basename(log)[:-4]
    name, seed = tag.rsplit(".s", 1)
    t = open(log).read()
    m = re.search(r"^\s+loop\.bytes_scored\s+(\d+)\s*$", t, re.M)
    acts = re.search(r"^\s+loop\.acts\s+(\d+)\s*$", t, re.M)
    vocab = re.findall(r"vocab=(\d+)", t)
    try: curve = json.load(open(os.path.join(out, "curves", tag + ".json")))
    except (OSError, ValueError): curve = None
    bpb = (sum(curve) * ctx / math.log(2) / int(m.group(1))) if (curve and m and int(m.group(1))) else None
    runs[(name, int(seed))] = dict(bpb=bpb, acts=acts.group(1) if acts else "-", n=len(curve or []),
                                   vocab=vocab[-1] if vocab else "?",
                                   stopped="stopped at max_windows" in t)
print()
print(f"=== RUNS (prequential bits/byte = sum(loss) x LM_CTX {ctx} / ln 2 / loop.bytes_scored) ===")
for (name, seed), v in sorted(runs.items()):
    print(f"  {name:<10} s{seed:<3} {v['n']:>6} flushes  acts {v['acts']:>4}  vocab {v['vocab']:>5}  "
          f"preq {v['bpb'] if v['bpb'] is None else round(v['bpb'], 5)}"
          + ("  STOPPED AT THE WINDOW CAP: this run did not read the whole stream, so its bytes differ "
             "from the other arms'" if v["stopped"] else ""))
a, b = runs.get(("k0", 0)), runs.get(("k0_rerun", 0))
if a and b and a["bpb"] is not None and b["bpb"] is not None:
    print(f"\n=== RUN-TO-RUN (k0 seed 0 twice): |diff| {abs(a['bpb'] - b['bpb']):.3g}")
seeds = sorted({s for (n, s) in runs if n == "k0" and runs[(n, s)]["bpb"] is not None})
M = [abs(runs[("k0", s)]["bpb"] - runs[("k0_nuis", s)]["bpb"]) for s in seeds
     if runs.get(("k0_nuis", s), {}).get("bpb") is not None]
if not M:
    print("\n!! no paired k0 / k0_nuis seeds: the margin cannot be formed and no cadence can ship"); sys.exit(0)
margin = max(M)
print(f"\n=== MARGIN M = max over {len(M)} seed(s) |k0 - k0_nuis| = {margin:.5f} bits/byte ===")
ships = {}
tested = 0
for arm in ("k3000", "k1000"):
    d = {s: runs[(arm, s)]["bpb"] - runs[("k0", s)]["bpb"] for s in seeds
         if runs.get((arm, s), {}).get("bpb") is not None}
    if not d: continue
    fired = [s for s in seeds if runs.get((arm, s), {}).get("acts", "-") not in ("-", "0")]
    if not fired:
        print(f"  {arm:<6} NO ACT FIRED at any seed: the run is too short for this cadence to act, so it "
              f"is the control under another name -- no evidence either way, not a pass")
        continue
    tested += 1
    ok = len(d) == len(seeds) and all(x <= margin for x in d.values())
    mean = sum(d.values()) / len(d)
    print(f"  {arm:<6} - k0 per seed: " + "  ".join(f"s{s} {x:+.5f}" for s, x in sorted(d.items()))
          + f"   mean {mean:+.5f}   {'NON-INFERIOR at every seed' if ok else 'FAILS the margin'}")
    if ok: ships[arm] = mean
print()
if not tested:
    print("=== DECISION: UNDECIDED -- no cadence acted in these runs; raise WINDOWS past the first act "
          "(minting starts near window 120-200, the first act follows at the cadence) ===")
elif ships:
    best = min(ships, key=ships.get)
    print(f"=== DECISION: TOK_RETOK_EVERY ships {best[1:]} (lowest mean among the non-inferior; "
          f"negative = the act helps) ===")
else:
    print("=== DECISION: neither cadence is non-inferior; TOK_RETOK_EVERY ships 0 (the act still serves "
          "resume and, later, AUD) ===")
PY
}

# bash gpu_world.sh --analyze : the analysis of whatever runs are on disk, printed and written to
# ANALYSIS.txt. For a fleet that finished but never reached its own analysis, or one that was
# stopped part-way (the missing runs simply have no curve and are left out of the pairing).
if [[ "${1:-}" == --analyze ]]; then
  _par=$(sed -n 's/^=== [0-9]* run(s), \([0-9]*\) at a time.*/\1/p' "$OUT/SUMMARY.txt" 2>/dev/null | tail -1)
  _mps=0; grep -q "CUDA MPS started" "$OUT/SUMMARY.txt" 2>/dev/null && _mps=1
  _dev=cuda; [[ -f "$OUT/smi.csv" ]] || _dev=cpu
  analyze "$OUT" "$_dev" "$_mps" "${_par:-1}" "$(nproc)" | tee "$OUT/ANALYSIS.txt"
  echo "=== wrote $OUT/ANALYSIS.txt"
  exit 0
fi

if [[ "${1:-}" == --status ]]; then
  OUT="$OUT" python3 - <<'PY'
import glob, os, re, datetime as dt
out = os.environ["OUT"]
s = open(f"{out}/SUMMARY.txt").read()
m = re.search(r"=== (\d+) run\(s\), (\d+) at a time", s)
if not m: raise SystemExit("the fleet has not started yet (still in the smoke or the calibration)")
n, par = map(int, m.groups())
win = int(re.search(r"(\d+) windows per run", s).group(1))
hh, mm, ss = map(int, re.search(r"fleet started (\d+):(\d+):(\d+)Z", s).groups())
now = dt.datetime.now(dt.timezone.utc)
start = now.replace(hour=hh, minute=mm, second=ss, microsecond=0)
if start > now: start -= dt.timedelta(days=1)
el = (now - start).total_seconds()
dtxt = open(f"{out}/logs/_done.txt").read() if os.path.exists(f"{out}/logs/_done.txt") else ""
done, failed = dtxt.count("rc="), len(re.findall(r"rc=[1-9]", dtxt))
logs = glob.glob(f"{out}/logs/*.log")
at = [int((re.findall(r"^\[(\d+) windows\]", open(l).read(), re.M) or [0])[-1]) for l in logs]
total, got = n * win, sum(min(a, win) for a in at)
rate = got / el if el else 0
left = (total - got) / rate / 3600 if rate else float("nan")
print(f"running {el/3600:.2f} h | runs {done}/{n} ended ({failed} FAILED), {len(logs)-done} in flight ({par} slots)")
print(f"windows {got:,}/{total:,} ({100*got/total:.0f}%) | {rate:.1f} w/s total, {rate/max(1,len(logs)-done):.2f} per run")
print(f"time left ~{left:.1f} h (finish ~{(now+dt.timedelta(hours=left)):%H:%M} UTC)")
for l in re.findall(r"=== ETA.*|=== parallelism.*|=== calibration.*", s): print(l)
PY
  exit 0
fi

mkdir -p "$OUT/logs" "$OUT/curves" "$OUT/smoke" "$OUT/cal"
S="$OUT/SUMMARY.txt"
: > "$S"
say() { echo "$*" | tee -a "$S"; }

# ---------------------------------------------------------------- preflight
say "=== gpu_world.sh  $(date -u +%Y-%m-%dT%H:%M:%SZ)  commit $(git rev-parse --short HEAD 2>/dev/null)"
NCPU=$(nproc)
# nproc READS THE CPU AFFINITY MASK, AND IN A CONTAINER THAT IS USUALLY THE HOST'S CORES. The cgroup
# QUOTA is what this container may actually use. The first version of this script sized its
# parallelism off nproc alone and put far more runs on the box than it had CPU for.
CPU_QUOTA=$(python3 - <<'PY'
def quota():
    try:
        a, b = open("/sys/fs/cgroup/cpu.max").read().split()
        return None if a == "max" else int(a) / int(b)
    except Exception:
        pass
    try:
        a = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
        b = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
        return None if a <= 0 else a / b
    except Exception:
        return None
q = quota()
print(max(1, int(q)) if q else 0)
PY
)
if [[ "$CPU_QUOTA" -gt 0 && "$CPU_QUOTA" -lt "$NCPU" ]]; then
  say "=== nproc reports $NCPU core(s) but the cgroup quota is $CPU_QUOTA: sizing by the quota"
  NCPU=$CPU_QUOTA
fi
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

# ---------------------------------------------------------------- 0. MPS, before anything is measured
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

# MPS SERVES AT MOST 48 CLIENT PROCESSES PER GPU (Volta and later). A client past that limit fails at
# CUDA init, and the first version of this script launched 65 runs at once: 48 ran and 17 failed.
MPS_CAP=0
[[ "$MPS_ON" == 1 ]] && MPS_CAP=$(( 48 * NGPU ))

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
    fb_on)     echo "WORLD_FEEDBACK=1" ;;
    skip)      echo "WORLD_FEEDBACK=1 WORLD_PREDICT_W=0.0 WORLD_COLLAPSE_W=0.0" ;;
    world_off) echo "WORLD_ENABLED=0" ;;
    k0)        echo "TOK_RETOK_EVERY=0" ;;
    k3000)     echo "TOK_RETOK_EVERY=3000" ;;
    k1000)     echo "TOK_RETOK_EVERY=1000" ;;
    k0_nuis)   echo "TOK_RETOK_EVERY=0 SIG_WARMUP=801" ;;
  esac
}
if [[ "$EXP" == retok ]]; then
  BASE_ARMS="k0 k3000 k1000 k0_nuis"; CTRL=k0
  [[ -n "$ARCH_ALSO" || "$LONG" -gt 0 ]] && echo "EXP=retok: ARCH_ALSO and LONG are ignored"
  ARCH_ALSO=""; LONG=0
else
  BASE_ARMS="fb_off fb_on skip world_off"; CTRL=fb_off
fi

# IT WAITS ON ITS OWN RUNS BY PID, NEVER WITH A BARE `wait`. The nvidia-smi sampler is a background
# child of this shell too, and it never exits by itself: the first fleet on a real card finished all
# 21 runs and then hung in a bare `wait` for the sampler, so the analysis never ran. `wait -n` had
# the same exposure in reverse (any child ending counted as a slot freed).
run_fleet() {  # runs JOBS with $1 slots, round-robin over GPUs
  local slots="$1" i=0 p
  local -a pids=()
  : > "${JOB_DIR:-$OUT/logs}/_done.txt"
  for line in "${JOBS[@]}"; do
    # shellcheck disable=SC2086
    set -- $line
    local name="$1" seed="$2" win="$3"; shift 3
    local gpu=0
    [[ "$NGPU" -gt 0 ]] && gpu=$(( i % NGPU ))
    while :; do                                   # a free slot = fewer than $slots of OUR pids alive
      local alive=0
      for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && alive=$(( alive + 1 )); done
      [[ "$alive" -lt "$slots" ]] && break
      sleep 2
    done
    run_job "$name" "$seed" "$win" "$gpu" "$@" &
    pids+=("$!")
    i=$(( i + 1 ))
  done
  for p in "${pids[@]}"; do wait "$p"; done
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

# ---------------------------------------------------------------- 1b. MEASURE the parallelism
# THE CEILING IS ARITHMETIC AND THE CHOICE IS A MEASUREMENT. Cores, GPU memory and the MPS client
# limit say how many runs COULD share the card; none of them says how many SHOULD. The first version
# of this script took the arithmetic ceiling as the answer: 125 slots, 65 runs at once, and the card
# delivered 16.5 windows/s in AGGREGATE -- 0.3 per run -- because a launch-bound process starved of
# CPU and time-sliced against 47 others is slower than the same work done a few at a time. So this
# runs k copies of one arm for CAL_WINDOWS windows at k = 1, 2, 4, 8, ... up to the ceiling, reads
# each run's own loop time (the "in Xs" of its summary line, which excludes startup), and takes the
# SMALLEST k within 10% of the best aggregate windows/s. Each step costs one short run; the ladder
# stops as soon as doubling k gains less than 10%, so the step where throughput collapses is the
# last one paid for.
CPU_SLOTS=$(( NCPU > 1 ? NCPU - 1 : 1 ))
CEIL=$CPU_SLOTS
if [[ "$DEVICE" == cuda ]]; then
  MEM_SLOTS=$(python3 -c "print(max(1, int(0.85*$GPU_MEM_MIB/1024 / (1.5*$PEAK_GIB + 0.5)) * $NGPU))")
  [[ "$MEM_SLOTS" -lt "$CEIL" ]] && CEIL=$MEM_SLOTS
  [[ "$MPS_CAP" -gt 0 && "$MPS_CAP" -lt "$CEIL" ]] && CEIL=$MPS_CAP
fi
say "=== ceiling: $CPU_SLOTS by CPU, ${MEM_SLOTS:-n/a} by GPU memory, ${MPS_CAP/#0/no} MPS cap -> at most $CEIL at once"
if [[ "$PAR" == auto ]]; then
  say "---- calibration: k copies of fb_on for $CAL_WINDOWS windows, aggregate windows/s"
  : > "$OUT/cal/table.txt"
  prev=0
  for k in $LADDER; do
    [[ "$k" -gt "$CEIL" ]] && break
    d="$OUT/cal/k$k"; mkdir -p "$d"
    JOBS=(); for j in $(seq 1 "$k"); do add_job "cal $(( 1000 + j )) $CAL_WINDOWS"; done
    JOB_DIR="$d" CURVE_DIR="$d" run_fleet "$k"
    line=$(python3 - "$d" "$k" <<'PY'
import glob, os, re, sys
d, k = sys.argv[1], int(sys.argv[2])
rate, n = 0.0, 0
for log in glob.glob(os.path.join(d, "*.log")):
    m = re.search(r"=== (\d+) windows[^\n]*? in ([\d.]+)s", open(log).read())
    if m and float(m.group(2)) > 0:
        rate += int(m.group(1)) / float(m.group(2)); n += 1
fails = open(os.path.join(d, "_done.txt")).read().count("rc=") - n
print(f"{k} {rate:.3f} {fails}")
PY
)
    echo "$line" >> "$OUT/cal/table.txt"
    set -- $line
    say "    k=$1  aggregate $2 windows/s  ($(python3 -c "print(f'{$2/$1:.2f}')") per run)  failed $3"
    if [[ "$3" -gt 0 ]]; then say "    runs FAILED at k=$1 -- the ladder stops below it"; sed -i '$d' "$OUT/cal/table.txt"; break; fi
    if python3 -c "import sys; sys.exit(0 if $prev > 0 and $2 < 1.10 * $prev else 1)"; then break; fi
    prev=$2
  done
  read PAR CAL_RATE < <(python3 - "$OUT/cal/table.txt" <<'PY'
import sys
rows = [tuple(map(float, l.split()[:2])) for l in open(sys.argv[1]) if l.strip()]
if not rows:                      # even k=1 failed: run one at a time and let the fleet's logs say why
    print(1, 0); raise SystemExit
best = max(r for _, r in rows)
k, r = min((k, r) for k, r in rows if r >= 0.9 * best)
print(int(k), r)
PY
)
  say "=== calibration: PAR=$PAR (aggregate $CAL_RATE windows/s; the smallest k within 10% of the best measured)"
else
  CAL_RATE=0
  say "=== PAR=$PAR set by hand; no calibration"
fi

# ---------------------------------------------------------------- 2. the job list and its size
JOBS=()
for s in $SEEDS; do for a in $BASE_ARMS; do add_job "$a $s $RUN_WIN $(arm_env $a)"; done; done
add_job "${CTRL}_rerun 0 $RUN_WIN $(arm_env $CTRL)"
if [[ -n "$ARCH_ALSO" ]]; then
  for s in $SEEDS; do for a in fb_off fb_on; do add_job "${a}@$ARCH_ALSO $s $WINDOWS LM_ARCH=$ARCH_ALSO $(arm_env $a)"; done; done
fi
if [[ "$LONG" -gt 0 ]]; then
  for a in fb_off fb_on; do add_job "${a}_long 0 $LONG $(arm_env $a)"; done
fi

# FILL: spare slots become extra seeds, added to EVERY base arm so the pairing stays complete.
if [[ "$FILL" == 1 && "${#JOBS[@]}" -lt "$PAR" ]]; then
  n_seeds=$(echo $SEEDS | wc -w); next=$(( $(echo $SEEDS | tr ' ' '\n' | sort -n | tail -1) + 1 ))
  added=""
  while [[ $(( ${#JOBS[@]} + 4 )) -le "$PAR" && "$n_seeds" -lt "$MAX_SEEDS" ]]; do
    for a in $BASE_ARMS; do add_job "$a $next $RUN_WIN $(arm_env $a)"; done
    added="$added $next"; next=$(( next + 1 )); n_seeds=$(( n_seeds + 1 ))
  done
  [[ -n "$added" ]] && say "=== FILL: spare slots -> extra seeds$added on every base arm (now $n_seeds seeds)"
fi
say "=== ${#JOBS[@]} run(s), $PAR at a time"
# THE ETA IS PRICED AT THE MEASURED AGGREGATE RATE at PAR, over every window the job list holds. It
# assumes every slot stays busy, so the last partial wave makes it slightly optimistic, and the rate
# was measured on short runs whose fabric had not grown yet.
python3 - "${CAL_RATE:-0}" "$SMOKE_WPS" "$PAR" <<PY | tee -a "$S"
import math
jobs = """$(printf '%s\n' "${JOBS[@]}")""".split("\n")
# A retok job's window count is its cap, set out of reach; it reads about WINDOWS windows.
total = sum(min(int(j.split()[2]), int("$WINDOWS")) for j in jobs if j.strip())
rate, smoke, par = float("${CAL_RATE:-0}"), float("$SMOKE_WPS" or 0), int("$PAR")
if rate <= 0: rate = smoke * par
if rate > 0:
    print(f"=== ETA: about {total / rate / 3600:.1f} h for {total:,} windows at {rate:.1f} windows/s aggregate")
PY

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
analyze "$OUT" "$DEVICE" "$MPS_ON" "$PAR" "$NCPU" >> "$S"
say "=== wrote $S"
cat "$S" | sed -n '/=== RUNS ===/,$p'
