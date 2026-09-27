#!/bin/bash
# ==================================================================================================
# THE OWNER'S GPU FLEETS, EACH RUN AS A FLEET THAT FILLS THE CARD: Q-WORLD-10's WORLD EXPERIMENT,
# 03b S0b's RETOK SHIP RULE, AND THE WHOLE-EPOCH WORLD RE-RUN'S SIZING
# ==================================================================================================
# EXP CHOOSES THE EXPERIMENT, AND ANY OTHER VALUE IS REFUSED BY NAME (Proposal 05 §8 1.5): a
# misspelled EXP used to fall through to the WORLD fleet, which then ran under the label meant for
# another one.
#   EXP=world        the default: Q-WORLD-10's four arms, the 2026-09-24 fleet (below)
#   EXP=retok        03b S0b's ship rule for TOK_RETOK_EVERY, with kept checkpoints (§8 2.1)
#   EXP=world_epoch  the whole-epoch, phase-traversing WORLD re-run: sized, and refused until SR0
#
# WHAT EXP=world DECIDED (2026-09-24: within noise, WORLD_FEEDBACK now ships False). Whether WORLD_FEEDBACK stays True (the forecast wired into LM.encode, world_proj
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
#   6. analyses the curves, prints the decision, prints the block to paste back and packs $OUT.
#
#     bash gpu_world.sh                                   # 20,000 windows, seeds 0-4, auto-filled
#     WINDOWS=5000 bash gpu_world.sh                      # a quicker first look
#     EXTRA="LM_WIDTH=512 LM_LAYERS=2" bash gpu_world.sh  # your standard geometry, applied to EVERY arm
#     ARCH_ALSO=transformer bash gpu_world.sh             # + fb_off/fb_on at LM_ARCH=transformer
#     LONG=100000 bash gpu_world.sh                       # + one fb_on/fb_off pair (seed 0) that long
#     PAR=12 MPS=0 FILL=0 bash gpu_world.sh               # manual parallelism, no MPS, no extra seeds
#     KEEP_CKPT=1 bash gpu_world.sh                       # + one final checkpoint per run (below)
#     bash gpu_world.sh --status                          # progress and time left; changes nothing
#     bash gpu_world.sh --analyze                         # re-analyse what is on disk, paste back, pack
#     cat gpu_world_out/SUMMARY.txt
#
# CHECKPOINTS ARE OFF BY DEFAULT AND ON AT EXP=retok (KEEP_CKPT; Proposal 05 §8 1.5, register note
# retok fleet (1)). Saving is the most expensive operation in the loop and nothing EXP=world measures
# needs a resume, so there CKPT_DIR stays unset unless KEEP_CKPT=1 asks for one final checkpoint per
# run. At EXP=retok every run gets CKPT_DIR=$OUT/ckpt/<arm>.s<seed>: the act arms save once, at the
# end (CKPT_EVERY 0); k0, k0_nuis and k0_rerun save every KEEP_EVERY windows (default: the gcd of the
# act cadences, 1000); and k0's saves are HARD-LINKED ASIDE as $OUT/ckpt/keep/k0.s<seed>.w<step>,
# with the vocabulary beside each as k0.s<seed>.w<step>.dyntok.json, because CKPT's ring keeps only
# ckpt.pt and ckpt.pt.prev (src/ckpt/api.py::save). A periodic save lands on the window an act of that
# cadence fires at (j x K + 1) and leaves the run's losses bit-identical (tests/test_continuation.py
# S11), so arm - k0 pairs a saving control with arms that save only at the end. The kept copies are
# the spike test's maturity-matched control (register note retok fleet (4)) and parents for
# continuations:
#     CKPT_RESUME=gpu_retok_out/ckpt/keep/k0.s0.w3001 CKPT_DIR=<a NEW directory> TOK_RETOK_EVERY=0 \
#         <the fleet's EXTRA> python3 run.py ...
# RESUME INTO A NEW CKPT_DIR, NEVER THE KEPT ONE: a save there rotates the kept copy away, and the
# read-only bit the index sets on kept files stops no rename. Nothing is written under runs/, and a
# SIGUSR1 save lands in the run's own CKPT_DIR (at EXP=world by default there is none, so it saves
# nothing). A hard link costs no disk until the ring drops its own name for the file; the fleet's
# checkpoint disk is estimated from the smoke's largest checkpoint before FILL adds seeds.
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
# RETOK_ARMS names the act cadences (arm k<c> each; default "3000 1000", today's arms in today's
# order), and COOLDOWN_ARM=<v> adds k<fastest>_cd<v> at FAB_COOLDOWN=<v>, reported beside the rule and
# never a ship candidate. CALIBRATION RUNS 600 WINDOWS HERE (CAL_WINDOWS; 150 at EXP=world), past FAB's
# first manage pass at window 501: the 2026-09-24 fleet ran about 15x slower than its 150-window
# calibration said, because the per-pass cost starts after it (LOW-GPU-WORLD-ETA). Beside the rule,
# never in it, the analysis reports RATES (windows/s and bytes/s per arm, the act's per-byte cost
# against k0, the aggregate over the fleet's wall, and the ETA against that wall: the post-fix
# throughput re-baseline), SECONDARIES (acts, FAB growth, the blackout share, MEM's re-cut share,
# bytes per token per act, mint waits, the act's share of loop time, bits/byte per phase; §8 1.3's
# counters where the tree has them and one "absent" line where it does not) with a BLACKOUT ALARM
# above 20% of windows (C13) that orders COOLDOWN_ARM=100, and the KEPT CHECKPOINTS with their
# coverage of the act windows. The verdict is labelled B-provisional (note retok fleet (3)), and
# pre-Levels when this tree lacks DOM_LEVELS or the fleet turns it off (C12). IF THIS FLEET RUNS AFTER
# SR0, 04-Q5's pin rule applies: its margin pairs with pre-SR0 runs, so SR0's build adds
# DATA_SYNTH_HOLDOUT=0 EVAL_RETENTION_EVERY=0 DATA_TRUST=off to every retok run here.
#     EXP=retok bash gpu_world.sh                         # 20,000 windows, seeds 0-2, auto-filled
#     EXP=retok RETOK_ARMS="3000 1000 500" bash gpu_world.sh   # another cadence set
#     EXP=retok COOLDOWN_ARM=100 bash gpu_world.sh        # + k1000_cd100 (the blackout alarm's arm)
#     EXP=retok KEEP_CKPT=0 bash gpu_world.sh             # no checkpoints: the spike test loses its control
#     EXP=retok bash gpu_world.sh --analyze
#
# EXP=world_epoch IS THE WORLD RE-RUN'S SHAPE, SIZED AND GUARDED BUT NOT RUN (register note WORLD 3-4,
# §8 6.5). The 2026-09-24 fleet read phase 1 of a 20 MB stream and never saw an area arrive or fade.
# This shape reads ONE WHOLE EPOCH of a WINDOWS x 189-byte stream (EPOCH_BYTES), as EXP=retok does, with
# the window cap out of reach and "RAN OUT OF STREAM" replaced by a window-cap flag, so every arm
# crosses all four phases. It pins TOK_RETOK_EVERY (PIN_RETOK, 3000; S0b-ship: every dependent
# experiment pins and labels it) and DATA_DRAW=planned (note WORLD 3). Its pre-registered rule reads
# SR0's retention probe with DATA_SYNTH_HOLDOUT ON, which this tree does not declare, so it prints its
# sizing and the pre-registration and exits 2 having written nothing, until GO_WORLD_EPOCH=1 (SR0's
# build adds those settings to its pins and lifts the guard; before that, only an operation check).
#     EXP=world_epoch bash gpu_world.sh                   # the sizing and the pre-registration; exit 2
#     EXP=world_epoch GO_WORLD_EPOCH=1 bash gpu_world.sh  # after SR0
#
# EVERY FLEET ENDS IN A BLOCK TO PASTE BACK AND AN ARCHIVE TO KEEP. The GPU box has a checkout and no
# push token (results/gpu_world_2026-09-24/ANALYSIS.txt was transcribed from its terminal by hand), so
# the end of every fleet, every --analyze and every early stop prints ONE block, from
# "==== PASTE THIS BACK ====" to "==== END ====", at most 80 lines, and writes it to
# $OUT/PASTE_BACK.txt: the commit, the card, the shape, the failed runs, and the result (at EXP=retok
# the per-seed bits/byte, the margin, the verdict, rates, secondaries and kept checkpoints). Paste it
# into the chat. $OUT is then packed beside itself as <name>_<launch date>.tgz -- logs, curves, smoke,
# calibration, SUMMARY, ANALYSIS, the block, KEPT.txt; never a checkpoint -- which the owner keeps
# (the 2026-09-24 precedent, gpu_world_2026-09-24.tgz, and the layout tools/read_fleet_archive.sh reads).
set -u

_EXP_GIVEN=${EXP+x}
EXP=${EXP:-world}
case "$EXP" in
  world|retok|world_epoch) ;;
  *) echo "!! EXP='$EXP' is not an experiment this script runs: world (the default), retok or world_epoch." \
          "Nothing was started."; exit 2 ;;
esac
case "$EXP" in retok) _o=gpu_retok_out ;; world_epoch) _o=gpu_world_epoch_out ;; *) _o=gpu_world_out ;; esac
OUT=${OUT:-$_o}
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
# EXP=world_epoch takes the same whole-epoch sizing, for its own reason: the WORLD re-run must cross
# every phase of the stream, and a window cap below the epoch would stop it inside one.
if [[ "$EXP" == retok ]]; then
  BYTES=${RETOK_BYTES:-$(( WINDOWS * 189 ))}
  RUN_WIN=$(( WINDOWS * 3 ))
elif [[ "$EXP" == world_epoch ]]; then
  BYTES=${EPOCH_BYTES:-$(( WINDOWS * 189 ))}
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
# 600 AT THE WHOLE-EPOCH SHAPES, 150 AT EXP=world (LOW-GPU-WORLD-ETA). 600 is past FAB's first manage
# pass at window 501, which the 2026-09-24 fleet's 150-window calibration never reached: that fleet
# then ran about 15x slower than its ETA. EXP=world keeps 150 until the retok fleet's ETA-against-wall
# reading, which its block prints, says the calibration still misses by more than 1.5x.
CAL_WINDOWS=${CAL_WINDOWS:-$([[ "$EXP" == world ]] && echo 150 || echo 600)}
LADDER=${LADDER:-"1 2 4 8 12 16 24 32 48 64 96 128"}
# THE SCRIPT'S OWN KNOBS ARE NAMED CLEAR OF EVERY PACKAGE PREFIX (RUN_, DATA_, TOK_, FAB_, CKPT_, ...):
# they reach the runs' environment too, and a lever answering to one of these names would be set by
# accident, silently -- spine/lever.py ignores undeclared names under a declared prefix.
RETOK_ARMS=${RETOK_ARMS:-"3000 1000"}      # EXP=retok: the act cadences, one arm k<c> each
COOLDOWN_ARM=${COOLDOWN_ARM:-}             # EXP=retok: FAB_COOLDOWN of an extra arm at the fastest cadence
KEEP_CKPT=${KEEP_CKPT:-$([[ "$EXP" == retok ]] && echo 1 || echo 0)}
KEEP_POLL=${KEEP_POLL:-1}                  # seconds between the kept-checkpoint watcher's looks
PIN_RETOK=${PIN_RETOK:-3000}               # EXP=world_epoch: the TOK_RETOK_EVERY every run pins
GO_WORLD_EPOCH=${GO_WORLD_EPOCH:-0}
# LM_CTX TURNS PER-TOKEN NATS INTO BITS PER BYTE, so the analysis must use the one the runs used: from
# EXTRA, else from this environment (which the runs inherit), else the lever's default.
CTX=$(echo " $EXTRA " | sed -n 's/.* LM_CTX=\([0-9][0-9]*\) .*/\1/p')
CTX=${CTX:-${LM_CTX:-128}}

cd "$(dirname "$0")"

# ---------------------------------------------------------------- the arms
arm_env() {  # the lever settings that define each arm; an arm this does not know is refused
  case "$1" in
    fb_off)    echo "WORLD_FEEDBACK=0" ;;
    fb_on)     echo "WORLD_FEEDBACK=1" ;;
    skip)      echo "WORLD_FEEDBACK=1 WORLD_PREDICT_W=0.0 WORLD_COLLAPSE_W=0.0" ;;
    world_off) echo "WORLD_ENABLED=0" ;;
    k0)        echo "TOK_RETOK_EVERY=0" ;;
    k3000)     echo "TOK_RETOK_EVERY=3000" ;;
    k1000)     echo "TOK_RETOK_EVERY=1000" ;;
    k0_nuis)   echo "TOK_RETOK_EVERY=0 SIG_WARMUP=801" ;;
    k[1-9]*_cd[0-9]*) local c=${1%%_cd*}; echo "TOK_RETOK_EVERY=${c#k} FAB_COOLDOWN=${1##*_cd}" ;;
    k[1-9]*)   echo "TOK_RETOK_EVERY=${1#k}" ;;
    # NEVER AN EMPTY ANSWER: an unknown name used to return '' and run the defaults under it.
    *)         echo "!! arm_env: no arm named '$1'" >&2; return 1 ;;
  esac
}
if [[ "$EXP" == retok ]]; then
  for c in $RETOK_ARMS; do
    [[ "$c" =~ ^[1-9][0-9]*$ ]] || { echo "!! RETOK_ARMS: '$c' is not a positive cadence (arm k<c>; k0 is the control). Nothing was started."; exit 2; }
  done
  [[ -n "$RETOK_ARMS" ]] || { echo "!! RETOK_ARMS is empty: the retok fleet needs at least one act cadence."; exit 2; }
  [[ $(echo $RETOK_ARMS | tr ' ' '\n' | sort | uniq -d) ]] && { echo "!! RETOK_ARMS names a cadence twice: '$RETOK_ARMS'."; exit 2; }
  BASE_ARMS="k0"; for c in $RETOK_ARMS; do BASE_ARMS="$BASE_ARMS k$c"; done; BASE_ARMS="$BASE_ARMS k0_nuis"
  if [[ -n "$COOLDOWN_ARM" ]]; then
    [[ "$COOLDOWN_ARM" =~ ^[0-9]+$ ]] || { echo "!! COOLDOWN_ARM='$COOLDOWN_ARM' is not a window count (FAB_COOLDOWN)."; exit 2; }
    BASE_ARMS="$BASE_ARMS k$(echo $RETOK_ARMS | tr ' ' '\n' | sort -n | head -1)_cd$COOLDOWN_ARM"
  fi
  CTRL=k0
  # KEEP_EVERY DEFAULTS TO THE GCD OF THE CADENCES: an act of cadence K fires at window j x K + 1 and a
  # periodic save of period P lands at i x P + 1, so every act window is a save window iff P divides K.
  _g=0; for c in $RETOK_ARMS; do a=$_g; b=$c; while (( b )); do t=$(( a % b )); a=$b; b=$t; done; _g=$a; done
  KEEP_EVERY=${KEEP_EVERY:-$_g}
  [[ "$KEEP_EVERY" =~ ^[1-9][0-9]*$ ]] || { echo "!! KEEP_EVERY='$KEEP_EVERY' is not a positive window count."; exit 2; }
  for c in $RETOK_ARMS; do
    (( c % KEEP_EVERY == 0 )) || echo "WARNING: KEEP_EVERY=$KEEP_EVERY does not divide the k$c cadence: k0 keeps no copy at some k$c act windows."
  done
else
  BASE_ARMS="fb_off fb_on skip world_off"; CTRL=fb_off
  KEEP_EVERY=${KEEP_EVERY:-0}
fi
for a in $BASE_ARMS; do arm_env "$a" > /dev/null || exit 2; done
if [[ "$EXP" != world ]]; then
  [[ -n "$ARCH_ALSO" || "$LONG" -gt 0 ]] && echo "EXP=$EXP: ARCH_ALSO and LONG are ignored"
  ARCH_ALSO=""; LONG=0
fi
# THE PINS EVERY RUN OF THE EXPERIMENT CARRIES, after EXTRA and before the arm's own settings.
EXP_ENV=""
[[ "$EXP" == world_epoch ]] && EXP_ENV="TOK_RETOK_EVERY=$PIN_RETOK DATA_DRAW=planned"
# C12's LABEL, READ OFF THE TREE AND THE FLEET'S SETTINGS AT LAUNCH (so --analyze on another day
# reports what ran, not what the checkout holds then).
LEVELS="on (DOM_LEVELS declared, default on)"
grep -q "levels = Lever" src/domains/levers.py 2>/dev/null || LEVELS="pre-Levels (this tree declares no DOM_LEVELS)"
_dl=$(echo " $EXTRA " | sed -n 's/.* DOM_LEVELS=\([^ ]*\) .*/\1/p'); _dl=${_dl:-${DOM_LEVELS:-}}
case "$(echo "$_dl" | tr 'A-Z' 'a-z')" in 0|off|no|none|false) LEVELS="pre-Levels (DOM_LEVELS=$_dl)" ;; esac

# THE CHECKPOINT SETTINGS OF ONE RUN, '' AT KEEP_CKPT=0 -- so every default command line is the one
# this script ran before the option existed. Appended AFTER the arm's settings, so they win over EXTRA.
ckpt_env() {  # name seed base-dir [smoke]
  [[ "$KEEP_CKPT" == 1 ]] || return 0
  local every=0
  case "$1" in
    k0|k0_nuis|k0_rerun) every=$KEEP_EVERY; [[ -n "${4:-}" ]] && every=$(( SMOKE_WINDOWS / 2 > 0 ? SMOKE_WINDOWS / 2 : 1 )) ;;
  esac
  echo "CKPT_DIR=$3/$1.s$2 CKPT_EVERY=$every"
}
# HOW MANY CHECKPOINT FILES A RUN LEAVES AT MOST: k0 its kept saves plus the ring's two, the rest of
# the k0 family the ring's two, every other run its one final save.
ckpt_files() {  # name
  case "$1" in
    k0) echo $(( (11 * WINDOWS + 10 * KEEP_EVERY - 1) / (10 * KEEP_EVERY) + 2 )) ;;
    k0_nuis|k0_rerun) echo 2 ;;
    *) echo 1 ;;
  esac
}

plan_banner() {  # the fleet's shape, as SUMMARY records it and the EXP=world_epoch guard prints it
  echo "=== $WINDOWS windows per run, DATA_STREAM_BYTES=$BYTES, seeds: $SEEDS, EXTRA='$EXTRA'"
  echo "=== plan: EXP=$EXP; arms $BASE_ARMS, plus ${CTRL}_rerun at seed 0; window cap $RUN_WIN;" \
       "CAL_WINDOWS $CAL_WINDOWS; LM_CTX $CTX"
  if [[ "$KEEP_CKPT" == 1 && "$EXP" == retok ]]; then
    echo "=== kept checkpoints: ON, k0 family CKPT_EVERY=$KEEP_EVERY, act arms final only;" \
         "k0's saves hard-linked under $OUT/ckpt/keep"
  elif [[ "$KEEP_CKPT" == 1 ]]; then
    echo "=== kept checkpoints: ON, one final checkpoint per run under $OUT/ckpt"
  else
    echo "=== kept checkpoints: OFF"
  fi
  local p="" w
  for w in $EXP_ENV; do p="$p${p:+, }$w pinned"; done
  echo "=== pins: ${p:-none}"
  echo "=== DOM Levels: $LEVELS"
}

# bash gpu_world.sh --status : progress and time left of a fleet that is running (or finished),
# read off SUMMARY.txt and the logs. It changes nothing and is safe to run at any time.
# THE ANALYSIS, AS A FUNCTION so --analyze can re-run it on a finished (or interrupted) fleet.
analyze() {  # out device mps_on par ncpu
  if [[ "$EXP" == retok ]]; then analyze_retok "$@"; return; fi
  # EXP=world_epoch READS ONE WHOLE EPOCH: its runs are meant to end at the stream's end, so the
  # flags turn over (the 6th argument). At EXP=world the output is what it always was.
  python3 - "$@" "$([[ "$EXP" == world_epoch ]] && echo 1 || echo 0)" <<'PY'
import glob, json, math, os, re, statistics, sys
out, dev, mps_on, par, ncpu = sys.argv[1], sys.argv[2], sys.argv[3] == "1", int(sys.argv[4]), int(sys.argv[5])
whole = len(sys.argv) > 6 and sys.argv[6] == "1"

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
    if whole:
        # A WHOLE-EPOCH RUN THAT HIT THE CAP read less than its epoch: a shorter experiment under the label.
        if v["stopped_at_max"]: flags.append("STOPPED AT THE WINDOW CAP: did not read the whole epoch")
    elif v["ok"] and not v["stopped_at_max"]: flags.append("RAN OUT OF STREAM (raise BYTES)")
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
if whole:
    print("  Q-WORLD-10's rule, shown for continuity; the pre-registered re-run rule (note WORLD 4) needs "
          "SR0's retention probe")
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

# THE RETOK SHIP RULE (EXP=retok), 03b S0b. Prequential bits/byte per run, paired by seed; then the
# rates, the secondaries and the kept checkpoints, and the block to paste back -- ONE program, so the
# verdict the block carries is the one ANALYSIS.txt printed, never a second reading of the logs.
analyze_retok() {  # out device mps_on par ncpu
  gw_py retok "$1" "$CTX" "$(archive_path)"
}

# THE BLOCK AND ITS PARTS (Proposal 05 §8 1.5). Modes: retok (the analysis above, which also writes
# PASTE_BACK.txt and KEPT.txt), wrap (EXP=world and world_epoch: the header plus ANALYSIS.txt from
# '=== RUNS ===' on), fail (a stop before the analysis). Every header is read off SUMMARY.txt alone,
# so --analyze reproduces the block the fleet wrote.
gw_py() {  # mode out ...
  python3 - "$@" <<'PY'
import glob, json, math, os, re, sys
MODE, OUT = sys.argv[1], sys.argv[2]
CAP = 80                              # lines in the block, both delimiters included
L2 = math.log(2)


def rd(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def rep(t):
    r = {}
    for m in re.finditer(r"^\s+([A-Za-z_][\w.@()-]*\.[\w.@()-]+)\s+(\S+)\s*$", t, re.M):
        r[m.group(1)] = m.group(2)
    return r


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x, spec=".2f", none="-"):
    if x is None:
        return none
    if spec == "n" and float(x) == int(x):
        return str(int(x))
    return format(x, ".2f" if spec == "n" else spec)


S = rd(os.path.join(OUT, "SUMMARY.txt"))


def sget(rx, g=1):
    m = re.search(rx, S, re.M)
    return m.group(g) if m else None


EXTRA = sget(r"^=== \d+ windows per run, DATA_STREAM_BYTES=\d+, seeds: .*?, EXTRA='(.*)'$") or ""
KEPT_ON = (sget(r"^=== kept checkpoints: (ON|OFF)") or "?")


def head(exp, labels=()):
    """The header, the card and the shape: three lines, the same whenever the block is written."""
    first = S.splitlines()[0] if S else ""
    m = re.match(r"=== gpu_world\.sh\s+(\S+)\s+commit\s*(\S*)(.*)$", first)
    when, commit, dirty = (m.group(1), m.group(2) or "?", "(dirty)" in m.group(3)) if m else ("?", "?", False)
    out = [f"gpu_world.sh EXP={exp}  commit {commit}"
           + (" (DIRTY: src, run.py or gpu_world.sh differed from it)" if dirty else "")
           + f"  launched {when}" + "".join("  " + l for l in labels)]
    gpus = re.findall(r"^\s+\d+, ([^,\n]+), (\d+) MiB, \d+ MiB\s*$", S, re.M)
    kinds = sorted({f"{n.strip()} {mib} MiB" for n, mib in gpus})
    card = (f"{len(gpus)} x {kinds[0]}" if len(kinds) == 1 else ", ".join(kinds)) if gpus else "no GPU listed"
    cores = re.search(r"^=== (\d+) CPU core\(s\), (\d+) GPU\(s\), device=(\w+)", S, re.M)
    par = re.findall(r"^=== \d+ run\(s\), (\d+) at a time", S, re.M)
    tv = sget(r"^=== (torch \S+, CUDA \S+)") or "torch ?"
    out.append(f"card: {card}; {tv}; "
               f"NCPU {cores.group(1) if cores else '?'}; PAR {par[-1] if par else '?'}; "
               f"MPS {'on' if 'CUDA MPS started' in S else 'off'}; device={cores.group(3) if cores else '?'}")
    sz = re.search(r"^=== (\d+) windows per run, DATA_STREAM_BYTES=(\d+), seeds: (.*?), EXTRA='(.*)'$", S, re.M)
    plan = sget(r"^=== plan: .*?window cap (\d+); CAL_WINDOWS (\d+); LM_CTX (\d+)", 0)
    pins = sget(r"^=== pins: (.*)$")
    shp = (f"shape: {sz.group(1)} windows/run, DATA_STREAM_BYTES={sz.group(2)}, seeds {sz.group(3)}, "
           f"EXTRA='{sz.group(4)}'" if sz else "shape: ? (SUMMARY.txt holds no sizing line)")
    if plan:
        pm = re.search(r"window cap (\d+); CAL_WINDOWS (\d+); LM_CTX (\d+)", plan)
        shp += f"; cap {pm.group(1)}; CAL {pm.group(2)}; LM_CTX {pm.group(3)}"
    shp += f"; kept ckpts {KEPT_ON}" + (f"; pins {pins}" if pins and pins != "none" else "")
    out.append(shp)
    return out


def archive_line(archive):
    return (f"archive: {os.path.basename(archive)} beside {OUT} (logs, curves, SUMMARY, ANALYSIS, this block; "
            f"no checkpoints) -- keep it")


def emit(sections):
    """Write the block, at most CAP lines. sections: (name, lines, rank) in order, the LAST one the
    archive line, which always closes the block. When the block is too long the highest rank goes
    first and rank 0 is never cut; if it is still too long the body is truncated. One line says what
    was cut, all of which is in ANALYSIS.txt and the archive."""
    budget = CAP - 2
    tail = sections[-1][1]
    sections = list(sections[:-1])
    cut = []

    def size():
        return sum(len(l) for _, l, _ in sections) + len(tail) + (1 if cut else 0)

    for rank in sorted({r for _, _, r in sections if r}, reverse=True):
        for i, (name, l, r) in enumerate(sections):
            if r == rank and l and size() > budget:
                cut.append(name)
                sections[i] = (name, [], r)
    body = [x for _, l, _ in sections for x in l]
    room = budget - len(tail)
    if cut or len(body) > room:
        room -= 1
    more = max(0, len(body) - room)
    body = body[:room]
    if cut or more:
        body.append(f"(cut to fit {CAP} lines: " + ", ".join(cut + ([f"the last {more} line(s)"] if more else []))
                    + " -- in ANALYSIS.txt and the archive)")
    lines = body + tail
    text = "\n".join(["==== PASTE THIS BACK ===="] + lines + ["==== END ===="]) + "\n"
    with open(os.path.join(OUT, "PASTE_BACK.txt"), "w") as fh:
        fh.write(text)


def done_book():
    d = {}
    for l in rd(os.path.join(OUT, "logs", "_done.txt")).splitlines():
        m = re.match(r"(\S+) rc=(-?\d+) secs=(\d+)", l)
        if m:
            d[m.group(1)] = (int(m.group(2)), int(m.group(3)))
    return d


def last_line(t):
    ls = [x.strip() for x in t.splitlines() if x.strip()]
    return ls[-1][:160] if ls else "(empty log)"


def failures(runs, done, cap=8):
    """rc != 0 with each log's last line (at most `cap`), then runs with no curve or stopped at the cap."""
    bad = [(tag, rc) for tag, (rc, _) in sorted(done.items()) if rc != 0]
    out = [f"runs: {len(done) - len(bad)} of {len(done)} ended rc=0" + (", every one" if not bad else "")]
    for tag, rc in bad[:cap]:
        out.append(f"  FAILED {tag} rc={rc}: {last_line(rd(os.path.join(OUT, 'logs', tag + '.log')))}")
    if len(bad) > cap:
        out.append(f"  ... {len(bad) - cap} more failed run(s): logs/_done.txt")
    nc = [f"{n}.s{s}" for (n, s), v in sorted(runs.items()) if v.get("curve") is None and done.get(f"{n}.s{s}", (0,))[0] == 0]
    cap_ = [f"{n}.s{s}" for (n, s), v in sorted(runs.items()) if v.get("stopped")]
    if nc:
        out.append(f"  NO CURVE: {' '.join(nc[:12])}" + (" ..." if len(nc) > 12 else ""))
    if cap_:
        out.append(f"  STOPPED AT THE WINDOW CAP (did not read the whole stream): {' '.join(cap_[:12])}"
                   + (" ..." if len(cap_) > 12 else ""))
    return out


# ------------------------------------------------------------------------------------------ retok
def retok(ctx_arg, archive):
    # LM_CTX: what the fleet recorded at launch, else its EXTRA, else what this shell was given.
    ctx = int(sget(r"^=== plan: .*?LM_CTX (\d+)") or (re.search(r"(?:^| )LM_CTX=(\d+)", EXTRA) or [0, 0])[1]
              or ctx_arg)
    done = done_book()
    runs = {}
    for log in sorted(glob.glob(os.path.join(OUT, "logs", "*.log"))):
        tag = os.path.basename(log)[:-4]
        name, _, seed = tag.rpartition(".s")
        if not name or not seed.isdigit():
            continue
        t = rd(log)
        m = re.search(r"^\s+loop\.bytes_scored\s+(\d+)\s*$", t, re.M)
        acts = re.search(r"^\s+loop\.acts\s+(\d+)\s*$", t, re.M)
        vocab = re.findall(r"vocab=(\d+)", t)
        try: curve = json.load(open(os.path.join(OUT, "curves", tag + ".json")))
        except (OSError, ValueError): curve = None
        try: fbytes = json.load(open(os.path.join(OUT, "curves", tag + ".bytes.json")))
        except (OSError, ValueError): fbytes = None
        bpb = (sum(curve) * ctx / math.log(2) / int(m.group(1))) if (curve and m and int(m.group(1))) else None
        w = re.search(r"=== (\d+) windows[^\n]*? in ([\d.]+)s", t)
        # EACH ACT'S OWN LINE: its window, and the tail's bytes per token before and after (§8 1.3), or
        # failing that the whole stream's ids before and after, whose ratio is the same kind of rise.
        at, rise, rise_kind = [], [], None
        for am in re.finditer(r"mid-epoch act at window (\d+):[^\n]*?\((\d+) -> (\d+) ids;([^\n]*)", t):
            at.append(int(am.group(1)))
            tb = re.search(r"Tail bytes/token ([\d.]+) -> ([\d.]+)", am.group(4))
            if tb:
                rise.append(float(tb.group(2)) / float(tb.group(1)) - 1.0); rise_kind = "tail"
            else:
                rise.append(int(am.group(2)) / int(am.group(3)) - 1.0); rise_kind = rise_kind or "ids"
        cd = re.search(r"cooldown=(\d+) windows", t)
        runs[(name, int(seed))] = dict(
            bpb=bpb, acts=acts.group(1) if acts else "-", n=len(curve or []), vocab=vocab[-1] if vocab else "?",
            stopped="stopped at max_windows" in t, r=rep(t), curve=curve, fbytes=fbytes,
            win=int(w.group(1)) if w else None, secs=float(w.group(2)) if w else None,
            bytes=int(m.group(1)) if m else None, at=at, rise=rise, rise_kind=rise_kind,
            cooldown=int(cd.group(1)) if cd else None)
    names = {n for (n, s) in runs}
    ACT = sorted((n for n in names if re.fullmatch(r"k[1-9]\d*", n)), key=lambda a: -int(a[1:]))
    CD = sorted(n for n in names if re.fullmatch(r"k[1-9]\d*_cd\d+", n))
    ORDER = [a for a in ["k0"] + ACT + CD + ["k0_nuis"] if a in names]
    levels = sget(r"^=== DOM Levels: (.*)$")
    labels = ["B-provisional"] + (["pre-Levels"] if levels and "pre-Levels" in levels else
                                  ["Levels unrecorded"] if levels is None else [])

    print()
    print(f"=== RUNS (prequential bits/byte = sum(loss) x LM_CTX {ctx} / ln 2 / loop.bytes_scored) ===")
    for (name, seed), v in sorted(runs.items()):
        print(f"  {name:<10} s{seed:<3} {v['n']:>6} flushes  acts {v['acts']:>4}  vocab {v['vocab']:>5}  "
              f"preq {v['bpb'] if v['bpb'] is None else round(v['bpb'], 5)}"
              + ("  STOPPED AT THE WINDOW CAP: this run did not read the whole stream, so its bytes differ "
                 "from the other arms'" if v["stopped"] else ""))
    a, b = runs.get(("k0", 0)), runs.get(("k0_rerun", 0))
    rerun = None
    if a and b and a["bpb"] is not None and b["bpb"] is not None:
        rerun = abs(a['bpb'] - b['bpb'])
        print(f"\n=== RUN-TO-RUN (k0 seed 0 twice): |diff| {rerun:.3g}")
    seeds = sorted({s for (n, s) in runs if n == "k0" and runs[(n, s)]["bpb"] is not None})
    M = [abs(runs[("k0", s)]["bpb"] - runs[("k0_nuis", s)]["bpb"]) for s in seeds
         if runs.get(("k0_nuis", s), {}).get("bpb") is not None]
    verdicts, decision, margin = [], None, None
    if not M:
        # NO MARGIN, NO VERDICT -- but the rates, secondaries and kept checkpoints below still print.
        print("\n!! no paired k0 / k0_nuis seeds: the margin cannot be formed and no cadence can ship")
        decision = "none -- no paired k0 / k0_nuis seeds: the margin cannot be formed and no cadence can ship"
    else:
        margin = max(M)
        print(f"\n=== MARGIN M = max over {len(M)} seed(s) |k0 - k0_nuis| = {margin:.5f} bits/byte ===")
        ships = {}
        tested = 0
        for arm in ACT:
            d = {s: runs[(arm, s)]["bpb"] - runs[("k0", s)]["bpb"] for s in seeds
                 if runs.get((arm, s), {}).get("bpb") is not None}
            if not d: continue
            fired = [s for s in seeds if runs.get((arm, s), {}).get("acts", "-") not in ("-", "0")]
            if not fired:
                print(f"  {arm:<6} NO ACT FIRED at any seed: the run is too short for this cadence to act, so it "
                      f"is the control under another name -- no evidence either way, not a pass")
                verdicts.append(f"  {arm}: NO ACT FIRED at any seed -- no evidence either way, not a pass")
                continue
            tested += 1
            ok = len(d) == len(seeds) and all(x <= margin for x in d.values())
            mean_ = sum(d.values()) / len(d)
            print(f"  {arm:<6} - k0 per seed: " + "  ".join(f"s{s} {x:+.5f}" for s, x in sorted(d.items()))
                  + f"   mean {mean_:+.5f}   {'NON-INFERIOR at every seed' if ok else 'FAILS the margin'}")
            verdicts.append(f"  {arm} - k0 mean {mean_:+.5f} over {len(d)} seed(s): "
                            f"{'NON-INFERIOR at every seed' if ok else 'FAILS the margin'}")
            if ok: ships[arm] = mean_
        # THE COOLDOWN ARM IS READ BESIDE THE RULE (C13): it prices the blackout, it is not a cadence.
        for arm in CD:
            parent = arm.split("_cd")[0]
            d = {s: runs[(arm, s)]["bpb"] - runs[("k0", s)]["bpb"] for s in seeds
                 if runs.get((arm, s), {}).get("bpb") is not None}
            if not d: continue
            dp = [runs[(arm, s)]["bpb"] - runs[(parent, s)]["bpb"] for s in d
                  if runs.get((parent, s), {}).get("bpb") is not None]
            line = (f"  {arm} - k0 per seed: " + "  ".join(f"s{s} {x:+.5f}" for s, x in sorted(d.items()))
                    + f"   mean {sum(d.values()) / len(d):+.5f}"
                    + (f"   vs {parent} {sum(dp) / len(dp):+.5f}" if dp else "")
                    + f"   (FAB_COOLDOWN={arm.split('_cd')[1]}: beside the rule, not a ship candidate)")
            print(line)
            verdicts.append(f"  {arm} - k0 mean {sum(d.values()) / len(d):+.5f}"
                            + (f", vs {parent} {sum(dp) / len(dp):+.5f}" if dp else "") + " (beside the rule)")
        print()
        if not tested:
            dl = ("=== DECISION: UNDECIDED -- no cadence acted in these runs; raise WINDOWS past the first act "
                  "(minting starts near window 120-200, the first act follows at the cadence) ===")
        elif ships:
            best = min(ships, key=ships.get)
            dl = (f"=== DECISION: TOK_RETOK_EVERY ships {best[1:]} (lowest mean among the non-inferior; "
                  f"negative = the act helps) ===")
        else:
            dl = ("=== DECISION: neither cadence is non-inferior; TOK_RETOK_EVERY ships 0 (the act still serves "
                  "resume and, later, AUD) ===")
        print(dl)
        decision = dl[len("=== DECISION: "):-len(" ===")]
    print("    label: B-provisional -- provisional until SR0's held-out worst-area re-read passes "
          "(register note retok fleet (3))"
          + ("; pre-Levels -- re-run the k0 vs chosen-cadence pair after Levels (C12)" if "pre-Levels" in labels
             else "; Levels unrecorded (SUMMARY.txt predates the record)" if "Levels unrecorded" in labels else ""))

    # ---------------------------------------------------------------- rates
    def per_arm(arm):
        return [(s, v) for (n, s), v in sorted(runs.items()) if n == arm]

    k0x = {s: v["secs"] / v["bytes"] for s, v in per_arm("k0") if v["secs"] and v["bytes"]}
    rate_rows, rate_short = [], []
    for arm in ORDER + (["k0_rerun"] if "k0_rerun" in names else []):
        rs = per_arm(arm)
        wps = [v["win"] / v["secs"] for _, v in rs if v["win"] and v["secs"]]
        bps = [v["bytes"] / v["secs"] for _, v in rs if v["bytes"] and v["secs"]]
        wall = [done[f"{arm}.s{s}"][1] for s, _ in rs if f"{arm}.s{s}" in done]
        cost = [v["secs"] / v["bytes"] / k0x[s] - 1.0 for s, v in rs
                if arm not in ("k0", "k0_nuis", "k0_rerun") and s in k0x and v["secs"] and v["bytes"]]
        if not wps:
            rate_rows.append(f"  {arm:<12} no '=== N windows ... in Xs' line in any log")
            rate_short.append(f"  {arm}: no rate")
            continue
        fam = arm in ("k0", "k0_nuis", "k0_rerun") and KEPT_ON == "ON"
        rate_rows.append(
            f"  {arm:<12} windows/s {mean(wps):.2f} [{min(wps):.2f}-{max(wps):.2f}]  bytes/s {mean(bps) or 0:.0f}  "
            f"wall {fmt(mean(wall), '.0f')} s  n={len(wps)}"
            + (f"  per-byte loop time vs k0 {100 * mean(cost):+.1f}%" if cost else "")
            + ("  (includes its periodic saves)" if fam else ""))
        rate_short.append(f"  {arm} {mean(wps):.2f} w/s [{min(wps):.2f}-{max(wps):.2f}] {mean(bps) or 0:.0f} B/s"
                          + (f", per-byte time vs k0 {100 * mean(cost):+.1f}%" if cost else "")
                          + (" (with saves)" if fam else ""))
    tw = sum(v["win"] for v in runs.values() if v["win"])
    fin = re.search(r"^---- fleet finished in \d+ min \((\d+) s\)", S, re.M)
    cal = re.search(r"^=== calibration: PAR=(\d+) \(aggregate ([\d.]+) windows/s", S, re.M)
    eta = re.search(r"^=== ETA: about ([\d.]+) h for ([\d,]+) windows at ([\d.]+) windows/s aggregate", S, re.M)
    par = (re.findall(r"^=== \d+ run\(s\), (\d+) at a time", S, re.M) or ["?"])[-1]
    agg = []
    if fin and int(fin.group(1)) > 0:
        wall_s = int(fin.group(1))
        agg.append(f"  aggregate: {tw:,} windows in {wall_s} s of fleet wall at PAR {par} = {tw / wall_s:.2f} windows/s"
                   + (f" (calibrated {float(cal.group(2)):.2f} at PAR {cal.group(1)}: measured/calibrated "
                      f"{tw / wall_s / float(cal.group(2)):.2f})" if cal and float(cal.group(2)) > 0 else ""))
        if eta and float(eta.group(3)) > 0:
            est = int(eta.group(2).replace(",", "")) / float(eta.group(3))
            ratio = wall_s / est if est > 0 else float("nan")
            agg.append(f"  ETA against wall: estimated {est:.0f} s ({eta.group(2)} windows at {eta.group(3)} "
                       f"windows/s), took {wall_s} s: {ratio:.2f}x")
            if ratio > 1.5:
                calw = sget(r"^=== plan: .*?CAL_WINDOWS (\d+)") or "?"
                agg.append(f"  LOW-GPU-WORLD-ETA: the ETA missed the wall by {ratio:.2f}x (> 1.5x) calibrated on "
                           f"{calw} windows: raise EXP=world's default CAL_WINDOWS to >= 520 "
                           f"(FAB_MANAGE_EVERY + 20)")
        else:
            agg.append("  ETA against wall: SUMMARY.txt holds no ETA line (PAR set by hand and no smoke rate)")
    else:
        agg.append(f"  aggregate: {tw:,} windows; no fleet wall time in SUMMARY.txt (the fleet did not finish there)")
    cores = re.search(r"^=== (\d+) CPU core\(s\), (\d+) GPU\(s\), device=(\w+)", S, re.M)
    gpu = (re.findall(r"^\s+\d+, ([^,\n]+), \d+ MiB, \d+ MiB\s*$", S, re.M) or ["no GPU listed"])[0].strip()
    card = (f"  recorded on: {gpu}, PAR {par}, MPS {'on' if 'CUDA MPS started' in S else 'off'}, "
            f"NCPU {cores.group(1) if cores else '?'}")
    print()
    print("=== RATES (post-fix rate at the retok shape; PENDING-GPU-THROUGHPUT-REBASELINE) ===")
    print("  per run: windows/s = N / X and bytes/s = loop.bytes_scored / X from each log's '=== N windows ... "
          "in Xs' (the loop's own time, startup excluded); wall = _done.txt secs; mean [min-max] over seeds")
    for l in rate_rows + agg + [card]:
        print(l)

    # ---------------------------------------------------------------- secondaries
    NEW13 = ("fab.blackout_windows", "tok.mint_wait_windows", "loop.act_seconds", "tok.bpt_tail")
    have13 = {k for v in runs.values() for k in v["r"] if k in NEW13}
    have_fb = any(v["fbytes"] for v in runs.values())
    absent = [k for k in NEW13 if k not in have13] + ([] if have_fb else ["per-flush bytes (run.py --flush-bytes)"])

    def cm(arm, key):
        return mean([fnum(v["r"].get(key)) for _, v in per_arm(arm)])

    def share(arm, key, den="win"):
        return mean([fnum(v["r"].get(key)) / v[den] for _, v in per_arm(arm)
                     if fnum(v["r"].get(key)) is not None and v[den]])

    # PER PHASE: the stream's phases are DATA_STREAM_BYTES cut into DATA_PHASES equal byte ranges
    # (data/api.py::data_plan), and each flush is placed by its first byte off the per-flush bytes.
    total = int(sget(r"DATA_STREAM_BYTES=(\d+)") or 0)
    nph, phase_note = 4, None
    if "DATA_PHASE_SCHED" in EXTRA:
        phase_note = "skipped: EXTRA sets DATA_PHASE_SCHED, so the phases are not equal quarters"
    elif re.search(r"(?:^| )DATA_PHASES=(\d+)", EXTRA):
        nph = max(2, int(re.search(r"(?:^| )DATA_PHASES=(\d+)", EXTRA).group(1)))

    def phases(v):
        c, fb = v["curve"], v["fbytes"]
        if not (c and fb and len(c) == len(fb) and total):
            return None
        lo_n, lo_b, off = [0.0] * nph, [0] * nph, 0
        for x, nb in zip(c, fb):
            k = min(nph - 1, next((j for j in range(nph) if off < round((j + 1) * total / nph)), nph - 1))
            lo_n[k] += x; lo_b[k] += nb; off += nb
        return [lo_n[k] * ctx / L2 / lo_b[k] if lo_b[k] else None for k in range(nph)]

    sec_rows, sec_short, phase_rows, alarms = [], [], [], []
    for arm in ORDER:
        rs = per_arm(arm)
        acts = cm(arm, "loop.acts")
        bw = share(arm, "fab.blackout_windows")
        cdv = mean([v["cooldown"] for _, v in rs])
        # AN UPPER BOUND: each notification can black out at most one cooldown, and never more than
        # the whole run (a short run's cooldowns overlap and overrun its end).
        ub = mean([min(1.0, fnum(v["r"].get("fab.shift_notifications")) * v["cooldown"] / v["win"]) for _, v in rs
                   if fnum(v["r"].get("fab.shift_notifications")) is not None and v["cooldown"] and v["win"]])
        waited, wwin = cm(arm, "tok.mint_waited"), cm(arm, "tok.mint_wait_windows")
        ash, rsh = share(arm, "loop.act_seconds", "secs"), share(arm, "loop.act_remap_seconds", "secs")
        # MEM'S RE-CUT SHARE: the entries an act's remap changed, over the store's capacity (n_opened).
        ev, ent, slots = cm(arm, "store.n_remap_events"), cm(arm, "store.n_remapped_entries"), cm(arm, "store.n_opened")
        recut = ent / ev / slots if ev and ent is not None and slots else None
        nr = max([len(v["rise"]) for _, v in rs] or [0])
        rise = [mean([v["rise"][i] for _, v in rs if len(v["rise"]) > i]) for i in range(nr)]
        kind = next((v["rise_kind"] for _, v in rs if v["rise_kind"]), None)
        sec_rows.append(
            f"  {arm:<12} acts {fmt(acts, 'n')} (noop {fmt(cm(arm, 'loop.acts_noop'), 'n')}, tok.retok_noop "
            f"{fmt(cm(arm, 'tok.retok_noop'), 'n')}), replay record {fmt(acts + 1 if acts is not None else None, 'n')} "
            f"event(s); FAB grown regression {fmt(cm(arm, 'fab.grown_regression'), 'n')} / stall "
            f"{fmt(cm(arm, 'fab.grown_stall'), 'n')}, births {fmt(cm(arm, 'fab.births'), 'n')}, blackout-suppressed "
            f"regression {fmt(cm(arm, 'fab.growth_blackout_suppressed.regression'), 'n')} / stall "
            f"{fmt(cm(arm, 'fab.growth_blackout_suppressed.stall'), 'n')}")
        sec_rows.append(
            f"  {'':<12} blackout {fmt(bw and 100 * bw, '.1f')}% of windows (fab.blackout_windows; upper bound "
            f"fab.shift_notifications x cooldown {fmt(cdv, '.0f')} / windows = {fmt(ub and 100 * ub, '.1f')}%); "
            f"mint wait {fmt(wwin / waited if waited else None, '.1f')} windows x {fmt(waited, 'n')} id(s); "
            f"act {fmt(ash and 100 * ash, '.2f')}% of loop time (MEM re-cut {fmt(rsh and 100 * rsh, '.2f')}%); "
            f"MEM re-cut {fmt(recut and 100 * recut, '.1f')}% of the store's slots per act; tok.bpt_tail "
            f"{fmt(cm(arm, 'tok.bpt_tail'), '.4f')}")
        if rise:
            sec_rows.append(f"  {'':<12} bytes/token rise per act ("
                            + ("the tail's, before -> after" if kind == "tail" else "whole-stream ids A/B - 1")
                            + "): " + " ".join(f"{100 * x:+.1f}%" for x in rise))
        sec_short.append(
            f"  {arm} acts {fmt(acts, 'n')} noop {fmt(cm(arm, 'loop.acts_noop'), 'n')}; grown reg "
            f"{fmt(cm(arm, 'fab.grown_regression'), 'n')}/stall {fmt(cm(arm, 'fab.grown_stall'), 'n')}; blackout "
            f"{fmt(bw and 100 * bw, '.1f')}% (<= {fmt(ub and 100 * ub, '.1f')}%); act {fmt(ash and 100 * ash, '.2f')}% "
            f"of loop; MEM re-cut {fmt(recut and 100 * recut, '.1f')}%/act; bpt rise/act "
            + (" ".join(f"{100 * x:+.1f}" for x in rise[:8]) + ("..." if len(rise) > 8 else "") + "%" if rise else "-"))
        ph = [phases(v) for _, v in rs]
        ph = [p for p in ph if p]
        if ph and not phase_note:
            phase_rows.append((arm, " ".join(fmt(mean([p[k] for p in ph]), '.4f') for k in range(nph)), len(ph)))
        if arm in ACT:
            s_ = bw if bw is not None else ub
            if s_ is not None and s_ > 0.20:
                fastest = min(ACT, key=lambda x: int(x[1:]))
                follow = (f"the cooldown arm {' '.join(CD)} is in this fleet: read its rows" if CD else
                          f"re-run with COOLDOWN_ARM=100 (adds {fastest}_cd100, FAB_COOLDOWN=100 at the fastest "
                          f"cadence)")
                alarms.append(f"  BLACKOUT ALARM (C13): {arm} blacks out {100 * s_:.1f}% of its windows"
                              + (" (upper bound)" if bw is None else "") + f", above 20%: {follow}")
    print()
    print("=== SECONDARIES (per arm, mean over seeds; beside the rule, never in it -- register note secondaries) ===")
    for l in sec_rows:
        print(l)
    if phase_note:
        print(f"  bits/byte by phase: {phase_note}")
    elif phase_rows:
        print(f"  by phase: the stream's {nph} equal byte ranges of DATA_STREAM_BYTES={total} (data_plan's "
              f"bounds), each flush placed by its first byte:")
        for arm, vals, n in phase_rows:
            print(f"  {arm:<12} bits/byte by phase: {vals}  ({n} seed(s))")
    if absent:
        print(f"  absent (§8 1.3 not in this tree): {', '.join(absent)}")
    for l in alarms:
        print(l)

    # ---------------------------------------------------------------- kept checkpoints
    kd = os.path.join(OUT, "ckpt", "keep")
    kfiles = sorted(glob.glob(os.path.join(kd, "*.kept.txt")))
    rows = []
    for f in kfiles:
        rows += [l for l in rd(f).splitlines() if l.strip()]
    if kfiles:
        with open(os.path.join(OUT, "KEPT.txt"), "w") as fh:
            fh.write("\n".join(rows) + "\n")
    kept_rows, kept_short = [], []
    if not os.path.isdir(os.path.join(OUT, "ckpt")):
        kept_rows.append("  none: no ckpt/ directory (KEEP_CKPT was off)")
        kept_short.append("KEPT: none (KEEP_CKPT off)")
    else:
        ks = {}
        for l in rows:
            m = re.match(r"^(\S+)\.s(\d+)\.w(\d+) step=(\d+) reason=(\S+) merges=(\S+) entries=(\S+) "
                         r"(coherent|INCOHERENT)", l)
            if m and m.group(1) == "k0":
                ks.setdefault(int(m.group(2)), []).append((int(m.group(4)), m.group(8) == "coherent"))
        cov_tot, short_bad = {}, []
        for s in sorted({s for (n, s) in runs if n == "k0"} | set(ks)):
            got = sorted(ks.get(s, []))
            steps = {st for st, _ in got}
            cov = []
            for arm in ACT + CD:
                aw = runs.get((arm, s), {}).get("at") or []
                if (arm, s) in runs:
                    hit = sum(1 for x in aw if x in steps)
                    cov.append(f"{arm} {hit}/{len(aw)}")
                    t_ = cov_tot.setdefault(arm, [0, 0]); t_[0] += hit; t_[1] += len(aw)
            inc = [st for st, ok in got if not ok]
            miss = [c_ for c_ in cov if c_.split()[1].split("/")[0] != c_.split()[1].split("/")[1]]
            if inc or miss:
                short_bad.append(f"  k0.s{s}: " + "; ".join(
                    ([f"INCOHERENT at {' '.join('w%d' % x for x in inc)}"] if inc else [])
                    + ([f"act windows not kept: {', '.join(miss)}"] if miss else [])))
            kept_rows.append(f"  k0.s{s}: {len(got)} kept" + (f", w{got[0][0]}-w{got[-1][0]}" if got else "")
                             + (", all coherent" if got and not inc else "")
                             + (f", INCOHERENT at {' '.join('w%d' % x for x in inc)}" if inc else "")
                             + ("; act windows covered: " + ", ".join(cov) if cov else ""))
        seen, du = set(), 0
        for root, _, fs in os.walk(os.path.join(OUT, "ckpt")):
            for fn in fs:
                try: st = os.lstat(os.path.join(root, fn))
                except OSError: continue
                if (st.st_dev, st.st_ino) not in seen:
                    seen.add((st.st_dev, st.st_ino)); du += st.st_size
        nk = sum(len(v) for v in ks.values())
        ninc = sum(1 for v in ks.values() for _, ok in v if not ok)
        kept_rows.append(f"  disk: {du / 1e9:.2f} GB under {os.path.join(OUT, 'ckpt')} (hard links counted once)")
        first = next((f"k0.s{s}.w{st}" for s in sorted(ks) for st, ok in sorted(ks[s]) if ok), None)
        if first:
            kept_rows.append(f"  resume one: CKPT_RESUME={os.path.join(kd, first)} CKPT_DIR=<a NEW directory> "
                             f"TOK_RETOK_EVERY=0 plus the fleet's EXTRA -- never CKPT_DIR=<a kept copy>")
        kept_short.append(f"KEPT: {nk} copies of {len(ks)} k0 run(s)"
                          + (", all coherent" if nk and not ninc else f", {ninc} INCOHERENT" if ninc else "")
                          + (", act windows covered " + ", ".join(f"{a} {h}/{n}" for a, (h, n) in cov_tot.items())
                             if cov_tot else "") + f"; ckpt/ {du / 1e9:.2f} GB")
        kept_short += short_bad[:4] + ([f"  ... {len(short_bad) - 4} more k0 run(s): KEPT.txt"] if len(short_bad) > 4 else [])
        if first:
            kept_short.append(f"  resume one: CKPT_RESUME={os.path.join(kd, first)} CKPT_DIR=<NEW dir> TOK_RETOK_EVERY=0")
    print()
    print("=== KEPT CHECKPOINTS (k0's periodic saves, hard-linked aside: the spike test's maturity-matched "
          "control, note retok fleet (1), (4)) ===")
    for l in kept_rows:
        print(l)

    # ---------------------------------------------------------------- the block
    arms_t = ORDER
    allseeds = sorted({s for (n, s) in runs if n in arms_t})
    wd = {a: max(9, len(a)) for a in arms_t}
    diffs = ACT + CD
    table = ["bits/byte per seed  " + " ".join(f"{a:>{wd[a]}}" for a in arms_t) + "  |k0-nuis|"
             + "".join(f" {a + '-k0':>{max(10, len(a) + 3)}}" for a in diffs)]
    for s in allseeds:
        g = lambda a: runs.get((a, s), {}).get("bpb")
        cells = " ".join(f"{fmt(g(a), '.5f'):>{wd[a]}}" for a in arms_t)
        nu = abs(g("k0") - g("k0_nuis")) if g("k0") is not None and g("k0_nuis") is not None else None
        ds = "".join(f" {fmt(g(a) - g('k0') if g(a) is not None and g('k0') is not None else None, '+.5f'):>{max(10, len(a) + 3)}}"
                     for a in diffs)
        table.append(f"  s{s:<16} {cells}  {fmt(nu, '.5f'):>9}{ds}")
    rr = [f"k0_rerun: k0 seed 0 twice, |diff| {rerun:.3g} bits/byte" + (" (BIT-EXACT)" if rerun == 0 else "")
          if rerun is not None else "k0_rerun: no pair (k0.s0 or k0_rerun.s0 has no reading)"]
    verdict = ([f"MARGIN M = {margin:.5f} bits/byte (max over {len(M)} seed(s) |k0 - k0_nuis|)"] if margin is not None else [])
    verdict += verdicts + [f"DECISION: {decision}  [{', '.join(labels)}]"]
    rates = ["RATES (post-fix rate at the retok shape; mean [min-max] over seeds):"]
    agg_short = [l for l in agg] + [card]
    sec_head = ["SECONDARIES (mean over seeds; beside the rule):"]
    sec_tail = ([f"  absent (§8 1.3 not in this tree): {', '.join(absent)}"] if absent else []) + alarms
    ph_short = [f"  bits/byte by phase ({nph} equal byte ranges), {arm}: {vals}" for arm, vals, _ in phase_rows]
    emit([
        ("head", head("retok", labels) + failures(runs, done), 0),
        ("verdict", table + rr + verdict, 0),
        ("rates", rates, 0), ("per-arm rates", rate_short, 2), ("aggregate", agg_short, 0),
        ("secondaries", sec_head, 0), ("per-arm secondaries", sec_short, 3), ("phases", ph_short, 4),
        ("absent and alarm", sec_tail, 0),
        ("kept checkpoints", kept_short, 1),
        ("archive", [archive_line(archive)], 0),
    ])


# ------------------------------------------------------------------------------------------ wrap
def wrap(exp, archive):
    """EXP=world and world_epoch: the header, then ANALYSIS.txt from '=== RUNS ===' on. The run rows
    are what gets cut when the block is too long; the pairing and the decision never are."""
    txt = rd(os.path.join(OUT, "ANALYSIS.txt"))
    i = txt.find("=== RUNS ===")
    body = [l.rstrip() for l in (txt[i:].splitlines() if i >= 0 else
                                 ["(no analysis: ANALYSIS.txt holds no '=== RUNS ===')"])]
    runs_part, rest = body, []
    if "" in body:
        j = body.index("")
        runs_part, rest = body[:j], body[j:]
    rest = [l for k, l in enumerate(rest) if l or not k or rest[k - 1]]      # one blank between sections
    hd = head(exp) + failures({}, done_book())
    fixed = len(hd) + len(rest) + 1
    room = CAP - 2 - fixed
    if len(runs_part) > room:
        keep = max(1, room - 1)
        runs_part = runs_part[:keep] + [f"  ... {len(runs_part) - keep} more run row(s) in ANALYSIS.txt"]
    emit([("head", hd, 0), ("runs", runs_part, 0), ("analysis", rest, 0), ("archive", [archive_line(archive)], 0)])


# ------------------------------------------------------------------------------------------ fail
def fail(exp, archive, reason, logs):
    lines = head(exp) + [f"STOPPED BEFORE THE ANALYSIS: {reason}"]
    for lg in logs:
        t = [x.rstrip()[:160] for x in rd(lg).splitlines() if x.strip()]
        lines += [f"--- {os.path.relpath(lg, OUT) if lg.startswith(OUT) else lg} (last 8 lines)"] + ["    " + x for x in t[-8:]]
    emit([("head", lines, 0), ("archive", [archive_line(archive)], 0)])


if MODE == "retok":
    retok(int(sys.argv[3]), sys.argv[4])
elif MODE == "wrap":
    wrap(sys.argv[3], sys.argv[4])
elif MODE == "fail":
    fail(sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6:])
PY
}

# ---------------------------------------------------------------- kept checkpoints (EXP=retok's k0)
# ONE LOOK: hard-link every COMPLETE save generation of the run's ring not yet kept. CKPT.save and
# TOK.save_vocabulary each write a .tmp and os.replace it, so a save is a new file under the same
# name, and spine/loop.py::_save calls save_vocabulary only after CKPT.save returned True -- so a
# generation is complete exactly when its vocabulary is no older than its checkpoint. Both ring
# generations are looked at, ckpt.pt with <dir>.dyntok.json and ckpt.pt.prev with
# <dir>.prev.dyntok.json (TOK rotates its file with CKPT's, 2026-09-26), so a save that a look
# missed is still taken as .prev at the next one. A copy is identified by size and nanosecond mtime,
# which a hard link shares and `cp -p` (the fallback where a link fails) preserves. A save that lands
# between the look and the link shows as a changed identity, and the half-taken copy is removed for
# the next look to take whole. The index below still checks every copy's merge count against its
# vocabulary, so a wrong pairing is flagged INCOHERENT, never kept silently.
keep_sweep() {  # ckdir keepdir tag
  local ck="$1" kd="$2" tag="$3" sfx c v kc mc mv have d n
  have=" $(stat -c '%s:%.9Y' "$kd/$tag".save[0-9]*/ckpt.pt "$kd/$tag".w[0-9]*/ckpt.pt 2>/dev/null | tr '\n' ' ') "
  for sfx in "" .prev; do
    c="$ck/ckpt.pt$sfx"; v="$ck$sfx.dyntok.json"
    kc=$(stat -c '%s:%.9Y' "$c" 2>/dev/null) || continue
    mv=$(stat -c '%.9Y' "$v" 2>/dev/null) || continue
    [[ "$have" == *" $kc "* ]] && continue
    mc=${kc#*:}
    (( ${mv/./} >= ${mc/./} )) || continue           # its vocabulary has not landed yet: mid-save
    n=1; while [[ -e "$kd/$tag.save$(printf %03d $n)" ]]; do n=$(( n + 1 )); done
    d="$kd/$tag.save$(printf %03d $n)"
    mkdir -p "$d" || continue
    ln "$c" "$d/ckpt.pt" 2>/dev/null || cp -p "$c" "$d/ckpt.pt" 2>/dev/null
    ln "$v" "$d.dyntok.json" 2>/dev/null || cp -p "$v" "$d.dyntok.json" 2>/dev/null
    if [[ "$(stat -c '%s:%.9Y' "$d/ckpt.pt" 2>/dev/null)" == "$kc" && "$(stat -c '%.9Y' "$d.dyntok.json" 2>/dev/null)" == "$mv" ]]; then
      have="$have$kc "
    else
      rm -rf "$d" "$d.dyntok.json"
    fi
  done
}
# THE WATCHER: a look every KEEP_POLL seconds until run_job drops the stop file, then a last look. At
# the fleet's cadence (1000 windows) saves are tens of seconds to minutes apart, and a 1 s poll costs
# a few stat calls.
keep_watch() {  # ckdir keepdir tag
  local stop="$2/.$3.stop"
  while :; do
    if [[ -e "$stop" ]]; then keep_sweep "$@"; rm -f "$stop"; return 0; fi
    keep_sweep "$@"
    sleep "$KEEP_POLL"
  done
}
# THE INDEX, AFTER THE RUN: each copy is named for the step it holds, read off the file (never assumed
# from the cadence), and checked against its vocabulary (the checkpoint's TOK merge count against the
# file's entries, the pairing build_vocabulary refuses a resume on). The run's final save duplicates
# the ring's ckpt.pt and a repeated step duplicates a copy, so both are dropped. Kept files are made
# read-only, and <tag>.kept.txt lists every copy. Python from inside the keep directory with src/
# first on its path, as run.py arranges it: the repository root's memory.py shadows src/memory.
keep_index() {  # keepdir tag
  ( cd "$1" && python3 - "$PWD" "$2" "$ROOT_DIR" <<'PY'
import glob, json, os, stat, sys
kd, tag, root = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path[:] = [p for p in sys.path if p and os.path.abspath(p) != os.path.abspath(root)]
sys.path.insert(0, os.path.join(root, "src"))
import torch


def load(path):
    try:
        return torch.load(path, map_location="cpu", mmap=True, weights_only=False)
    except TypeError:                                   # a torch without mmap=
        return torch.load(path, map_location="cpu", weights_only=False)


def read(d):
    b = load(os.path.join(d, "ckpt.pt"))
    tok = (b.get("payload") or {}).get("TOK") or {}
    mc = tok.get("merge_count") if isinstance(tok, dict) else None
    try:
        with open(d + ".dyntok.json") as fh:
            ent = len(json.load(fh)["entries"])
    except (OSError, ValueError, KeyError, TypeError):
        ent = None
    return int(b["step"]), str(b["reason"]), mc, ent


def drop(d):
    for f in (os.path.join(d, "ckpt.pt"), d + ".dyntok.json"):
        if os.path.exists(f):
            os.remove(f)
    if os.path.isdir(d):
        os.rmdir(d)


for d in sorted(glob.glob(os.path.join(kd, glob.escape(tag) + ".save[0-9]*"))):
    if not os.path.isdir(d):
        continue
    try:
        step, reason, mc, ent = read(d)
    except Exception as e:                              # noqa: BLE001 -- said, and the copy is left
        print(f"{os.path.basename(d)}: unreadable ({type(e).__name__}: {e}); left as it is")
        continue
    dst = os.path.join(kd, f"{tag}.w{step}")
    if reason == "final" or os.path.exists(dst):
        print(f"{os.path.basename(d)}: step {step} reason {reason} -- "
              + ("the final save, which the ring keeps" if reason == "final" else "a duplicate step") + "; dropped")
        drop(d)
        continue
    os.rename(d, dst)
    if os.path.exists(d + ".dyntok.json"):
        os.rename(d + ".dyntok.json", dst + ".dyntok.json")
rows = []
for d in sorted((p for p in glob.glob(os.path.join(kd, glob.escape(tag) + ".w[0-9]*")) if os.path.isdir(p)),
                key=lambda p: int(p.rsplit(".w", 1)[1])):
    step, reason, mc, ent = read(d)
    ok = mc is not None and ent is not None and int(mc) == int(ent)
    for f in (os.path.join(d, "ckpt.pt"), d + ".dyntok.json"):
        if os.path.exists(f):
            os.chmod(f, os.stat(f).st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    rows.append(f"{os.path.basename(d)} step={step} reason={reason} merges={mc} entries={ent} "
                f"{'coherent' if ok else 'INCOHERENT'} bytes={os.path.getsize(os.path.join(d, 'ckpt.pt'))}")
with open(os.path.join(kd, tag + ".kept.txt"), "w") as fh:
    fh.write("".join(r + "\n" for r in rows))
print(f"{tag}: {len(rows)} kept")
PY
  )
}
ROOT_DIR=$PWD

# ---------------------------------------------------------------- the block and the archive
archive_path() {  # beside OUT, named for the fleet's LAUNCH date, so --analyze on a later day repacks the same name
  local d b
  d=$(sed -n '1s/^=== gpu_world\.sh  \([0-9-]*\)T.*/\1/p' "$OUT/SUMMARY.txt" 2>/dev/null)
  b=$(basename "$OUT")
  echo "$(dirname "$OUT")/${b%_out}_${d:-$(date -u +%Y-%m-%d)}.tgz"
}
paste_back() {  # print the owner's block (EXP=retok's analysis wrote it; the others are wrapped here)
  [[ "$EXP" == retok ]] || gw_py wrap "$OUT" "$EXP" "$(archive_path)"
  echo
  cat "$OUT/PASTE_BACK.txt"
}
pack() {  # everything under OUT but checkpoints, into the archive the owner keeps
  local a p b
  a=$(archive_path); p=$(dirname "$OUT"); b=$(basename "$OUT")
  if tar -czf "$a" -C "$p" --exclude="$b/ckpt" --exclude="$b/smoke/ckpt" --exclude="$b/mps" \
         --exclude='*.pt' --exclude='*.pt.*' "$b"; then
    echo "=== packed $a ($(du -h "$a" | cut -f1)): logs, curves, SUMMARY, ANALYSIS, the block; no checkpoints. Keep it."
  else
    echo "!! could not pack $a"
  fi
}
fail_back() {  # reason [log...] : a stop before the analysis still ends in a block and an archive
  gw_py fail "$OUT" "$EXP" "$(archive_path)" "$@"
  echo
  cat "$OUT/PASTE_BACK.txt"
  pack
}

# bash gpu_world.sh --analyze : the analysis of whatever runs are on disk, printed and written to
# ANALYSIS.txt, then the block and the archive. For a fleet that finished but never reached its own
# analysis, or one that was stopped part-way (the missing runs simply have no curve and are left out
# of the pairing; k0's copies an interrupted run never indexed are indexed first).
if [[ "${1:-}" == --analyze ]]; then
  [[ -f "$OUT/SUMMARY.txt" ]] || { echo "!! no $OUT/SUMMARY.txt: nothing to analyse here (OUT=$OUT)"; exit 1; }
  if [[ -z "$_EXP_GIVEN" ]]; then     # the experiment the fleet recorded, when EXP was not given
    _e=$(sed -n 's/^=== plan: EXP=\([a-z_]*\);.*/\1/p' "$OUT/SUMMARY.txt" | head -1)
    [[ -z "$_e" ]] && compgen -G "$OUT/logs/k0.s*.log" > /dev/null && _e=retok
    [[ -n "$_e" ]] && EXP=$_e
  fi
  _par=$(sed -n 's/^=== [0-9]* run(s), \([0-9]*\) at a time.*/\1/p' "$OUT/SUMMARY.txt" 2>/dev/null | tail -1)
  _mps=0; grep -q "CUDA MPS started" "$OUT/SUMMARY.txt" 2>/dev/null && _mps=1
  _dev=cuda; [[ -f "$OUT/smi.csv" ]] || _dev=cpu
  for _t in $(ls -d "$OUT"/ckpt/keep/*.save[0-9]*/ 2>/dev/null | sed 's#/$##; s#.*/##; s/\.save[0-9]*$//' | sort -u); do
    keep_index "$OUT/ckpt/keep" "$_t" > "$OUT/ckpt/keep/$_t.index.log" 2>&1
  done
  analyze "$OUT" "$_dev" "$_mps" "${_par:-1}" "$(nproc)" | tee "$OUT/ANALYSIS.txt"
  echo "=== wrote $OUT/ANALYSIS.txt"
  paste_back
  pack
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
# A FINISHED RUN COUNTS ITS SUMMARY LINE: a run shorter than the progress cadence prints no
# "[N windows]" line at all, and read as 0 it made the rate 0 and the finish time NaN (a traceback).
at = []
for l in logs:
    t = open(l).read()
    fin = re.search(r"^=== (\d+) windows, ", t, re.M)
    at.append(int(fin.group(1)) if fin else int((re.findall(r"^\[(\d+) windows\]", t, re.M) or [0])[-1]))
total, got = n * win, sum(min(a, win) for a in at)
rate = got / el if el else 0
left = (total - got) / rate / 3600 if rate else float("nan")
print(f"running {el/3600:.2f} h | runs {done}/{n} ended ({failed} FAILED), {len(logs)-done} in flight ({par} slots)")
print(f"windows {got:,}/{total:,} ({100*got/total:.0f}%) | {rate:.1f} w/s total, {rate/max(1,len(logs)-done):.2f} per run")
print(f"time left ~{left:.1f} h (finish ~{(now+dt.timedelta(hours=left)):%H:%M} UTC)" if left == left else
      "time left: unknown (no log holds a window count yet)")
for l in re.findall(r"=== ETA.*|=== parallelism.*|=== calibration.*", s): print(l)
PY
  exit 0
fi

# THE WHOLE-EPOCH WORLD RE-RUN WAITS FOR SR0 ("do not run it", Proposal 05 §8 1.5): the sizing and the
# pre-registration are printed and NOTHING is written, not even $OUT.
if [[ "$EXP" == world_epoch && "$GO_WORLD_EPOCH" != 1 ]]; then
  plan_banner
  echo "=== EXP=world_epoch IS SIZED, NOT RUN: it is the WORLD re-run pre-registered after SR0 (register"
  echo "    note WORLD 3-4, §8 6.5). All four arms in ONE post-SR0 commit, 5 paired seeds, every run reading"
  echo "    one whole epoch (all four phases) with TOK_RETOK_EVERY and DATA_DRAW pinned; DATA_SYNTH_HOLDOUT ON"
  echo "    and the retention probe ON, levers this tree does not declare yet (SR0's build adds them to the"
  echo "    pins). Rule: WORLD_FEEDBACK flips ON only if fb_on beats fb_off on the time-integrated all-area"
  echo "    held-out gap (one-sided paired t, alpha 0.05; end-state beside it), is not worse than eps on the"
  echo "    worst area, and no seed shows latent_std < 0.9 or extra_ratio_max > 10. Both endpoints are"
  echo "    reported, with Q-WORLD-10's last-half and full-run prequential statistic beside the rule."
  echo "    GO_WORLD_EPOCH=1 lifts this guard (before SR0, an operation check only). Nothing was written."
  exit 2
fi
if [[ "$KEEP_CKPT" == 1 && "$OUT" =~ [[:space:]] ]]; then
  echo "!! OUT='$OUT' holds whitespace, and with KEEP_CKPT=1 its path rides inside the job lines, which are"
  echo "   split on whitespace. Choose an OUT without spaces. Nothing was started."; exit 2
fi

mkdir -p "$OUT/logs" "$OUT/curves" "$OUT/smoke" "$OUT/cal"
S="$OUT/SUMMARY.txt"
: > "$S"
say() { echo "$*" | tee -a "$S"; }

# ---------------------------------------------------------------- preflight
# ONE FLEET, ONE COMMIT: a checkout that differs from its commit where the runs read (src, run.py, this
# script) is flagged, and the flag reaches the block.
COMMIT=$(git rev-parse --short HEAD 2>/dev/null)
DIRTY=""
[[ -n "$COMMIT" ]] && ! git diff --quiet HEAD -- src run.py gpu_world.sh 2>/dev/null && DIRTY=" (dirty)"
say "=== gpu_world.sh  $(date -u +%Y-%m-%dT%H:%M:%SZ)  commit $COMMIT$DIRTY"
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
  if ! command -v nvidia-smi >/dev/null; then
    say "!! nvidia-smi not found. DEVICE=cuda needs a GPU."; fail_back "nvidia-smi not found (DEVICE=cuda)"; exit 1
  fi
  if ! python3 -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"; then
    say "!! torch sees no CUDA device. Every arm sets RUN_DEVICE=cuda, and RUN.process_setup takes"
    say "!! it verbatim with no fallback, so each would raise at its first .to(). Stopping here."
    fail_back "torch sees no CUDA device (DEVICE=cuda)"
    exit 1
  fi
  NGPU=$(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l)
  GPU_MEM_MIB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')
  nvidia-smi --query-gpu=index,name,memory.total,memory.used --format=csv | sed 's/^/    /' | tee -a "$S"
fi
say "=== $NCPU CPU core(s), $NGPU GPU(s), device=$DEVICE"
say "=== $(python3 -c 'import torch; print(f"torch {torch.__version__}, CUDA {torch.version.cuda}")' 2>/dev/null || echo 'torch ?, CUDA ?')"
plan_banner | tee -a "$S"
# run.py --flush-bytes (§8 1.3) writes the bytes behind each loss, which the per-phase bits/byte
# needs. Passed at the whole-epoch shapes only, and only where this tree's run.py has the flag.
FLUSH_BYTES=0
[[ "$EXP" != world ]] && grep -q -- '--flush-bytes' run.py && FLUSH_BYTES=1
say ""

# ---------------------------------------------------------------- 0. MPS, before anything is measured
MPS_ON=0
if [[ "$DEVICE" == cuda && "$MPS" != 0 ]] && command -v nvidia-cuda-mps-control >/dev/null; then
  # AN ABSOLUTE PATH EITHER WAY: "$PWD/$OUT" was a path that does not exist when OUT is absolute.
  _ob=$OUT; [[ "$OUT" == /* ]] || _ob="$PWD/$OUT"
  export CUDA_MPS_PIPE_DIRECTORY="$_ob/mps/pipe" CUDA_MPS_LOG_DIRECTORY="$_ob/mps/log"
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
# project once measured a 60x slowdown), the card, the seed, the stream, the shared geometry, then the
# experiment's pins, then the arm's settings and its checkpoint settings (the later assignment wins).
# EXP=retok's k0 runs with a CKPT_DIR get the kept-checkpoint watcher beside them, and their index
# after them, before the _done.txt line.
run_job() {  # name seed windows gpu arm-env...
  local name="$1" seed="$2" win="$3" gpu="$4"; shift 4
  local tag="$name.s$seed"
  local log="$OUT/logs/$tag.log" t0=$(date +%s)
  [[ -n "${JOB_DIR:-}" ]] && log="$JOB_DIR/$tag.log"
  local vis=() fb=() ck="" kd="" w="" a
  [[ "$DEVICE" == cuda ]] && vis=(CUDA_VISIBLE_DEVICES="$gpu")
  [[ "$FLUSH_BYTES" == 1 ]] && fb=(--flush-bytes "${CURVE_DIR:-$OUT/curves}/$tag.bytes.json")
  if [[ "$KEEP_CKPT" == 1 && "$EXP" == retok && "$name" == k0 ]]; then
    for a in "$@"; do [[ "$a" == CKPT_DIR=* ]] && ck="${a#CKPT_DIR=}"; done
  fi
  if [[ -n "$ck" ]]; then
    kd="$(dirname "$ck")/keep"; mkdir -p "$kd"; rm -f "$kd/.$tag.stop"
    keep_watch "$ck" "$kd" "$tag" &
    w=$!
  fi
  env "${vis[@]}" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 RUN_DEVICE="$DEVICE" RUN_SEED="$seed" \
      DATA_STREAM_BYTES="$BYTES" $EXTRA $EXP_ENV "$@" \
      python3 run.py --max-windows "$win" --loss-curve "${CURVE_DIR:-$OUT/curves}/$tag.json" "${fb[@]}" \
      > "$log" 2>&1
  local rc=$?
  if [[ -n "$w" ]]; then
    : > "$kd/.$tag.stop"
    wait "$w"
    keep_index "$kd" "$tag" > "$kd/$tag.index.log" 2>&1
  fi
  echo "$tag rc=$rc secs=$(( $(date +%s) - t0 ))" >> "${JOB_DIR:-$OUT/logs}/_done.txt"
  return $rc
}

# a job line is: name seed windows arm-env...   (arm-env may be empty)
declare -a JOBS=()
add_job() { JOBS+=("$*"); }

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
for a in $BASE_ARMS; do add_job "$a 0 $SMOKE_WINDOWS $(arm_env $a) $(ckpt_env $a 0 "$OUT/smoke/ckpt" smoke)"; done
if [[ -n "$ARCH_ALSO" ]]; then
  for a in fb_off fb_on; do add_job "${a}@$ARCH_ALSO 0 $SMOKE_WINDOWS LM_ARCH=$ARCH_ALSO $(arm_env $a) $(ckpt_env "${a}@$ARCH_ALSO" 0 "$OUT/smoke/ckpt" smoke)"; done
fi
JOB_DIR="$OUT/smoke" CURVE_DIR="$OUT/smoke" run_fleet "${#JOBS[@]}"
if grep -q "rc=[1-9]" "$OUT/smoke/_done.txt"; then
  say "!! a smoke arm FAILED -- stopping before the fleet:"
  grep "rc=[1-9]" "$OUT/smoke/_done.txt" | sed 's/^/    /' | tee -a "$S"
  for f in $(grep "rc=[1-9]" "$OUT/smoke/_done.txt" | cut -d' ' -f1); do
    say "    --- $f (last 8 lines)"; tail -8 "$OUT/smoke/$f.log" | sed 's/^/      /' | tee -a "$S"
  done
  fail_back "a smoke arm failed" $(grep "rc=[1-9]" "$OUT/smoke/_done.txt" | cut -d' ' -f1 | sed "s#^#$OUT/smoke/#; s#\$#.log#")
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
if echo "$SIZING" | grep -q "bad=[1-9]"; then
  say "!! a tripwire failed in the smoke -- stopping before the fleet."
  fail_back "a smoke tripwire failed: $(echo "$SIZING" | grep TRIPWIRE | head -3 | sed 's/^ *TRIPWIRE: //' | tr '\n' ';')"
  exit 1
fi
PEAK_GIB=$(echo "$SIZING" | sed -n 's/.*peak_gib=\([0-9.]*\).*/\1/p')
SMOKE_WPS=$(echo "$SIZING" | sed -n 's/.*wps=\([0-9.]*\).*/\1/p')
# THE KEPT-CHECKPOINT TRIPWIRE: the smoke's k0 saved at SMOKE_WINDOWS/2, so the watcher and the index
# ran on this card in the first minute, and at least one copy must be kept and coherent. The smoke's
# checkpoints then size the fleet's disk and are deleted.
CKPT_BYTES=0
if [[ "$KEEP_CKPT" == 1 ]]; then
  if [[ "$EXP" == retok ]]; then
    _kept="$OUT/smoke/ckpt/keep/k0.s0.kept.txt"
    if [[ $(grep -c " coherent " "$_kept" 2>/dev/null) -lt 1 ]]; then
      say "!! kept-checkpoint tripwire: the smoke's k0 left no coherent kept copy ($_kept):"
      cat "$_kept" "$OUT/smoke/ckpt/keep/k0.s0.index.log" 2>/dev/null | sed 's/^/    /' | tee -a "$S"
      fail_back "the kept-checkpoint tripwire: no coherent copy of the smoke's k0 periodic save" \
                "$OUT/smoke/ckpt/keep/k0.s0.index.log" "$OUT/smoke/k0.s0.log"
      exit 1
    fi
    say "  smoke kept: $(grep " coherent " "$_kept" | head -1)"
  fi
  CKPT_BYTES=$(find "$OUT/smoke/ckpt" -type f -name 'ckpt.pt*' -printf '%s\n' 2>/dev/null | sort -n | tail -1)
  CKPT_BYTES=${CKPT_BYTES:-0}
  rm -rf "$OUT/smoke/ckpt"
  say "  smoke checkpoints: the largest was $(( CKPT_BYTES / 1000000 )) MB; deleted"
fi

# ---------------------------------------------------------------- 1b. MEASURE the parallelism
# THE CEILING IS ARITHMETIC AND THE CHOICE IS A MEASUREMENT. Cores, GPU memory and the MPS client
# limit say how many runs COULD share the card; none of them says how many SHOULD. The first version
# of this script took the arithmetic ceiling as the answer: 125 slots, 65 runs at once, and the card
# delivered 16.5 windows/s in AGGREGATE -- 0.3 per run -- because a launch-bound process starved of
# CPU and time-sliced against 47 others is slower than the same work done a few at a time. So this
# runs k copies of the shipped defaults for CAL_WINDOWS windows at k = 1, 2, 4, 8, ... up to the
# ceiling, reads each run's own loop time (the "in Xs" of its summary line, which excludes startup),
# and takes the SMALLEST k within 10% of the best aggregate windows/s. Each step costs one short run;
# the ladder stops as soon as doubling k gains less than 10%, so the step where throughput collapses
# is the last one paid for. The copies carry the experiment's pins and never save. CAL_WINDOWS is 600
# at the whole-epoch shapes, past the first FAB manage pass at window 501: the 2026-09-24 fleet ran
# about 15x slower than its 150-window calibration (LOW-GPU-WORLD-ETA).
CPU_SLOTS=$(( NCPU > 1 ? NCPU - 1 : 1 ))
CEIL=$CPU_SLOTS
if [[ "$DEVICE" == cuda ]]; then
  MEM_SLOTS=$(python3 -c "print(max(1, int(0.85*$GPU_MEM_MIB/1024 / (1.5*$PEAK_GIB + 0.5)) * $NGPU))")
  [[ "$MEM_SLOTS" -lt "$CEIL" ]] && CEIL=$MEM_SLOTS
  [[ "$MPS_CAP" -gt 0 && "$MPS_CAP" -lt "$CEIL" ]] && CEIL=$MPS_CAP
fi
say "=== ceiling: $CPU_SLOTS by CPU, ${MEM_SLOTS:-n/a} by GPU memory, ${MPS_CAP/#0/no} MPS cap -> at most $CEIL at once"
if [[ "$PAR" == auto ]]; then
  say "---- calibration: k copies of the shipped defaults for $CAL_WINDOWS windows, aggregate windows/s"
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
for s in $SEEDS; do for a in $BASE_ARMS; do add_job "$a $s $RUN_WIN $(arm_env $a) $(ckpt_env $a $s "$OUT/ckpt")"; done; done
add_job "${CTRL}_rerun 0 $RUN_WIN $(arm_env $CTRL) $(ckpt_env ${CTRL}_rerun 0 "$OUT/ckpt")"
if [[ -n "$ARCH_ALSO" ]]; then
  for s in $SEEDS; do for a in fb_off fb_on; do add_job "${a}@$ARCH_ALSO $s $WINDOWS LM_ARCH=$ARCH_ALSO $(arm_env $a) $(ckpt_env "${a}@$ARCH_ALSO" $s "$OUT/ckpt")"; done; done
fi
if [[ "$LONG" -gt 0 ]]; then
  for a in fb_off fb_on; do add_job "${a}_long 0 $LONG $(arm_env $a) $(ckpt_env ${a}_long 0 "$OUT/ckpt")"; done
fi

# THE CHECKPOINTS' DISK, SIZED BEFORE FILL (KEEP_CKPT=1): every file at twice the smoke's largest
# checkpoint (the fabric grows toward FAB_SLOTS), k0 at its kept saves plus the ring. FILL stops adding
# seeds past 0.9 of the free space, and a job list that does not fit at its base seeds is refused.
gb() { awk -v b="$1" 'BEGIN { printf "%.1f", b / 1e9 }'; }
jobs_need() {  # bytes the job list's checkpoints may take
  local n=0 line
  for line in "${JOBS[@]}"; do n=$(( n + $(ckpt_files "${line%% *}") )); done
  echo $(( n * CKPT_BYTES * 2 ))
}
if [[ "$KEEP_CKPT" == 1 ]]; then
  FREE_B=$(( $(df -Pk "$OUT" | awk 'NR == 2 {print $4}') * 1024 ))
  NEED_B=$(jobs_need)
  if [[ "$NEED_B" -gt "$FREE_B" ]]; then
    say "!! disk: the kept checkpoints may need $(gb $NEED_B) GB and $OUT has $(gb $FREE_B) GB free."
    say "!! Free space, run fewer SEEDS, or KEEP_CKPT=0 (which leaves the spike test without its control)."
    fail_back "disk: checkpoints may need $(gb $NEED_B) GB, $(gb $FREE_B) GB free (free space, fewer SEEDS, or KEEP_CKPT=0)"
    exit 1
  fi
fi

# FILL: spare slots become extra seeds, added to EVERY base arm so the pairing stays complete.
if [[ "$FILL" == 1 && "${#JOBS[@]}" -lt "$PAR" ]]; then
  n_seeds=$(echo $SEEDS | wc -w); next=$(( $(echo $SEEDS | tr ' ' '\n' | sort -n | tail -1) + 1 ))
  n_arms=$(echo $BASE_ARMS | wc -w)
  added=""
  while [[ $(( ${#JOBS[@]} + n_arms )) -le "$PAR" && "$n_seeds" -lt "$MAX_SEEDS" ]]; do
    if [[ "$KEEP_CKPT" == 1 ]]; then
      _more=0; for a in $BASE_ARMS; do _more=$(( _more + $(ckpt_files $a) )); done
      if [[ $(( $(jobs_need) + _more * CKPT_BYTES * 2 )) -gt $(( FREE_B / 10 * 9 )) ]]; then
        say "=== FILL stops at $n_seeds seeds: another would pass 0.9 of the free disk ($(gb $FREE_B) GB)"
        break
      fi
    fi
    for a in $BASE_ARMS; do add_job "$a $next $RUN_WIN $(arm_env $a) $(ckpt_env $a $next "$OUT/ckpt")"; done
    added="$added $next"; next=$(( next + 1 )); n_seeds=$(( n_seeds + 1 ))
  done
  [[ -n "$added" ]] && say "=== FILL: spare slots -> extra seeds$added on every base arm (now $n_seeds seeds)"
fi
[[ "$KEEP_CKPT" == 1 ]] && say "=== disk: checkpoints may take about $(gb $(jobs_need)) GB" \
  "($(( CKPT_BYTES / 1000000 )) MB x 2 per file) of $(gb $FREE_B) GB free at $OUT"
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
say "---- fleet finished in $(( (T1 - T0) / 60 )) min ($(( T1 - T0 )) s)"
if grep -q "rc=[1-9]" "$OUT/logs/_done.txt"; then
  say "!! FAILED runs (their logs are in $OUT/logs):"
  grep "rc=[1-9]" "$OUT/logs/_done.txt" | sed 's/^/    /' | tee -a "$S"
fi

# ---------------------------------------------------------------- 5. analysis, the block, the archive
analyze "$OUT" "$DEVICE" "$MPS_ON" "$PAR" "$NCPU" | tee "$OUT/ANALYSIS.txt" >> "$S"
say "=== wrote $S"
cat "$S" | sed -n '/^=== RUNS/,$p'
paste_back
pack
