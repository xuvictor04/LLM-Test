#!/usr/bin/env bash
# ---------------------------------------------------------------------------------------------------------------
# sweep_domains.sh -- does the domain population CONVERGE, and to what, and why?
#
# Every stage answers one falsifiable question and prints one TSV row per run. Nothing here reads "the number went
# down": the count alone is uninterpretable (MAX_DOMAINS can produce it, and purity/homogeneity RISE with
# fragmentation). The admissible readouts are: live-count INVARIANCE to MAX_DOMAINS, live-count INVARIANCE to
# STREAM_LEN, completeness/V-measure, and the recurrence histogram.
#
#   bash sweep_domains.sh                 # all stages
#   STAGES="0 2 3" bash sweep_domains.sh  # a subset
# GH200: stage 0-3 ~25 min at STREAM_LEN=120000 (937 steps/run). Stage 4-5 ~20 min.
# ---------------------------------------------------------------------------------------------------------------
set -u

# ---- GUARD: every knob this sweep sets must actually be READ by self_organize.py. -------------------------------
# This project has lost a full benchmark campaign to D_MODEL_B, a variable read by nothing: every run silently used
# the default and the results described a model nobody intended. A sweep is the worst place for that failure, since
# each unread knob turns a whole stage into duplicate rows that look like a clean null result.
python3 - <<'PYGUARD' || { echo "!! aborting: fix or remove the unread knobs above"; exit 1; }
import re, sys
sw = open("sweep_domains.sh").read(); so = open("self_organize.py").read()
local = {"OUT","TSV","STAGES","SL","DOMS","COMMON","DATA_DIR","D_MODEL","STREAM_LEN","DOMAINS","LC_ALL","PYTHONWARNINGS"}
miss = [k for k in sorted(set(re.findall(r'\b([A-Z][A-Z0-9_]{2,})=', sw)))
        if k not in local and not re.search(r'["\']' + k + r'["\']', so)]
print("  UNREAD KNOBS (setting these does NOTHING): " + ", ".join(miss) if miss else "  all sweep knobs are read")
sys.exit(1 if miss else 0)
PYGUARD
OUT=${OUT:-runs/sweep_domains_$(date +%m%d_%H%M)}
mkdir -p "$OUT"
TSV="$OUT/results.tsv"
STAGES=${STAGES:-"0 1 2 3 4 5"}
SL=${STREAM_LEN:-120000}
DOMS=${DOMAINS:-eng,py,num,c}

# Assembly is independent of the LM (sig_of is no_grad; enc is trained only by contrastive_step), so run the
# cheapest LM that still exercises the real path. Raise D_MODEL only to reproduce a full run's wall-clock.
COMMON="DEVICE=cuda DATA_MODE=real DOMAINS=$DOMS DATA_DIR=${DATA_DIR:-data} D_MODEL=${D_MODEL:-128} \
WIN=128 SIG_MODE=learned SIG_D=64 ENC_BATCH=48 TEMP=0.1 REKEY_EVERY=200 EPOCHS=1 \
KEY_SRC=frozen MEM_CAP=${MEM_CAP:-20000} EVAL_N=64 PROFILE=0"

printf 'stage\tlabel\tlive\tcreated\tfolded\tmerged\tcapped\tbnds\tprec\trec\tpur\thom\tcomp\tV\tfrag\trecur\n' > "$TSV"

run () {  # run <stage> <label> <extra env...>
  local stage="$1"; local label="$2"; shift 2
  local log="$OUT/${stage}_${label//[^A-Za-z0-9._-]/_}.log"
  env $COMMON STREAM_LEN=$SL "$@" python3 self_organize.py > "$log" 2>&1
  python3 - "$stage" "$label" "$log" "$TSV" <<'PY'
import re, sys
stage, label, log, tsv = sys.argv[1:5]
t = open(log, errors="replace").read()
def g(pat, d="-", grp=1):
    m = re.search(pat, t)
    return m.group(grp) if m else d
row = [stage, label,
       g(r"SELF-ASSEMBLED (\d+) LIVE"),
       g(r"domain population: (\d+) created"),
       g(r"\| (\d+) folded"),
       g(r"\| (\d+) merged"),
       g(r"cap bound (\d+)x"),
       g(r"boundary detection: (\d+) found"),
       g(r"precision ([0-9.]+)"), g(r"recall ([0-9.]+)"),
       g(r"clustering purity: ([0-9.]+)"), g(r"homogeneity: ([0-9.]+)"),
       g(r"completeness: ([0-9.]+)"), g(r"V-measure: ([0-9.]+)"),
       g(r"= ([0-9.]+)x fragmentation"),
       g(r"recurrent \(>= \d+ entries\) (\d+/\d+)")]
open(tsv, "a").write("\t".join(row) + "\n")
print("\t".join(row))
PY
}

has () { [[ " $STAGES " == *" $1 "* ]]; }

# ---- STAGE 0. THE FALSIFIER. Is the cap doing the work? Run the SAME config at three caps. -------------------
# PASS = live count identical within +/-1 across all three AND capped==0 at MAX_DOMAINS=64.
# FAIL = the number tracks the cap; then no other row in this file means anything.
if has 0; then
  echo "== stage 0: cap invariance (baseline, current HEAD defaults) =="
  for M in 6 64 1024; do run 0 "cap$M" MAX_DOMAINS=$M; done
fi

# ---- STAGE 1. THE CEILING. Encoder budget is the dominant variable; find where V peaks. ----------------------
# Probe (no assembler) says window-pair AUC peaks at ~N=200 (0.954) and decays to 0.714 by N=4000, and the
# simulated best-achievable V at the measured geometry is 1.00 / 0.80 / 0.54 at N=200 / 1000 / 4000. No assign
# rule can beat the ceiling its metric allows, so measure the ceiling BEFORE tuning the rule.
if has 1; then
  echo "== stage 1: encoder training budget (ENC_EVERY=1 in-loop on top of warmup) =="
  for W in 200 400 800 2000 8000 30000; do
    run 1 "warmup$W" ENC_WARMUP=$W ENC_WARMUP_MIN=$W MAX_DOMAINS=1024
  done
  echo "== stage 1b: the loss-floor gate (continual-safe alternative to freezing) =="
  for K in 4 8 16; do run 1 "floorK$K" ENC_WARMUP=30000 ENC_FLOOR_K=$K MAX_DOMAINS=1024; done
fi

# ---- STAGE 2. THE PRIMARY. Per-domain measured radius vs the relative margin alone. --------------------------
# Prediction (simulation on the probe's measured geometry, N=1000 cell): margin-only 102 live / V 0.49;
# margin OR radius 8 live / V 0.80. If DOM_RADIUS=1 does not cut live by >=3x at ANY grid point, kill it.
if has 2; then
  echo "== stage 2: acceptance radius grid (MAX_DOMAINS=1024 so the cap cannot contribute) =="
  run 2 "radius_off" DOM_RADIUS=0 MAX_DOMAINS=1024
  run 2 "margin_off" DOM_RADIUS=1 DOM_RELATIVE=0 MAX_DOMAINS=1024
  for Q in 0.75 0.85 0.95; do
    for R in 1.0 1.3 1.6 2.0; do
      run 2 "rq${Q}_rm${R}" DOM_RADIUS=1 DOM_RQ=$Q DOM_RMULT=$R MAX_DOMAINS=1024
    done
  done
fi

# ---- STAGE 3. INTENSIVITY + RECURRENCE. Does the count stop growing with the stream? -------------------------
# THE decisive convergence test. A population that is EXTENSIVE in bytes consumed has not converged, whatever its
# value at 120 kB. Prediction: HEAD roughly doubles (102 -> 193 in simulation); the fix stays flat (8 -> 9).
if has 3; then
  echo "== stage 3: stream-length doubling x recurrence fold =="
  for L in 120000 240000 480000; do
    SL=$L run 3 "len${L}_head"  DOM_RADIUS=0 DOM_RECUR=0 MAX_DOMAINS=1024
    SL=$L run 3 "len${L}_fix"   DOM_RADIUS=1 DOM_RECUR=1 MAX_DOMAINS=1024
    SL=$L run 3 "len${L}_norec" DOM_RADIUS=1 DOM_RECUR=0 MAX_DOMAINS=1024
  done
  echo "== stage 3b: recurrence horizon / min visits =="
  for H in 16 32 64; do for V in 2 3; do
    run 3 "h${H}_v${V}" DOM_RADIUS=1 DOM_RECUR=1 DOM_RECUR_HORIZON=$H DOM_MIN_VISITS=$V MAX_DOMAINS=1024
  done; done
fi

# ---- STAGE 4. (a) ENC_POS_MAX -- now INTERPRETABLE, because the radius rule re-quantiles itself. --------------
# A fixed-threshold sweep of this knob measures where a constant lands in a rescaled space (within-corpus p50
# moves 0.350 -> 0.168 from 2*WIN to 8*WIN), not representation quality. With DOM_RADIUS=1 the threshold follows
# the scale, so any remaining difference is real. Pre-registered prediction: NO radius above 2*WIN improves V at
# matched budget -- contamination = 0.75*(1-exp(-E[off]/1250)) reaches the segment scale before the invariance does.
if has 4; then
  echo "== stage 4: positive radius x encoder budget, with calibration free =="
  for P in 256 512 1024 2048; do for W in 400 4000; do
    run 4 "pos${P}_w${W}" ENC_POS_MAX=$P ENC_WARMUP=$W ENC_WARMUP_MIN=$W DOM_RADIUS=1 MAX_DOMAINS=1024
  done; done
fi

# ---- STAGE 5. (b) SPECULATIVE: the second positive drawn from the assembler's OWN reservoir. -----------------
# Corpus-scale separation at a contamination equal to (1 - domain purity), instead of 33-53% for a blind radius.
# Kill unless V rises >= 0.05 at matched budget AND homogeneity stays >= 0.85 (a collapse also lowers the count).
if has 5; then
  echo "== stage 5: reservoir (prototype) positive =="
  for A in 0.0 0.5 1.0 2.0; do
    run 5 "proto$A" ENC_PROTO=$A DOM_RADIUS=1 DOM_RECUR=1 MAX_DOMAINS=1024
  done
  echo "== stage 5b: controls =="
  run 5 "bigram" SIG_MODE=bigram DOM_RADIUS=1 DOM_RECUR=1 MAX_DOMAINS=1024
fi

echo; echo "== $TSV =="; column -t -s $'\t' "$TSV"
cat <<'GATE'

KILL CRITERIA (pre-registered -- apply in this order, stop at the first failure):
 0. stage 0 rows must agree within +/-1 and capped must be 0. Otherwise nothing else is interpretable.
 1. stage 3 len120000 -> len480000 must grow < 25%. Linear growth = not converged, whatever the value at 120 kB.
 2. V >= 0.80 AND completeness >= 0.70. purity/homogeneity alone are inadmissible (both rise with fragmentation).
 3. homogeneity >= 0.85 -- a low count reached by merging corpora is a failure the count cannot see.
 4. recur column >= 0.6 of live -- a "domain" entered once is a splice segment with a different name.
 5. stage 2: if no radius grid point beats radius_off by 3x on live AND +0.15 on V, the primary is wrong.
 6. stage 4: if no ENC_POS_MAX > 256 wins on V at matched budget, (a) is dead -- do not sweep it again.
 7. stage 5: proto arm needs +0.05 V and homogeneity >= 0.85, else revert to ENC_PROTO=0.
 8. If stage 1's best warmup beats stage 2's best grid point, the encoder BUDGET dominates the assign rule --
    say so; do not report the assign fix as the cause.
GATE
