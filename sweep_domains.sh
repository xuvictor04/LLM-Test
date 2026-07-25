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
  for K in 0 4 8 16 32; do run 1 "floorK$K" ENC_WARMUP=30000 ENC_FLOOR_K=$K MAX_DOMAINS=1024; done
fi

# ---- STAGE 2. THE PRIMARY. Measured per-domain radius OR'd with the landed margin. --------------------------
# Measured on the SHIPPED DomainAssembler, isolated from the encoder (synthetic signatures, 4 recurring processes,
# 3 seeds, uncapped) -- this is what stage 2 has to reproduce on real text or the mechanism does not transfer:
#   constant thresholds     64.0 live | V 0.82 | completeness 0.70 | 4 of 64 domains recurrent
#   + radius x1.2           18.0 live | V 0.95 | completeness 0.91
#   + recurrence fold        4.0 live | V 1.00 | completeness 1.00 | 4 of 4 recurrent
# DOM_RCAP is the sensitive knob and NOT in the direction first assumed: 0.5 is the WORST value in the table (65
# live / V 0.82 -- it strangles the radius back to baseline, because the cap is set by a SAME-corpus sibling and
# so forbids exactly the absorption that would consolidate them), while 0 (off) and >=1.5 are indistinguishable.
# The shipped default is 2.0: free in the healthy regime, still a bound on a runaway.
# IT DOES NOT TRANSFER CLEANLY, and that is the interesting part. Same mechanism on REAL text (60 kB, 4 corpora,
# ENC_WARMUP=4000) moves 50 -> 36 live and recurrence 34% -> 61%, but leaves V flat (0.42 -> 0.40) and costs
# homogeneity (0.80 -> 0.70). What DOES move V is the encoder loss floor (stage 1b): 50 -> 23 alone, 50 -> 16
# combined with radius+fold at 88% recurrent, V 0.50. So the assign rule was never the dominant term -- the
# encoder's geometry was. Stage 2 exists to confirm that ranking at 120 kB, not to reproduce the isolated numbers.
if has 2; then
  echo "== stage 2: acceptance radius grid (MAX_DOMAINS=1024 so the cap cannot contribute) =="
  run 2 "radius_off" DOM_RADIUS=0 MAX_DOMAINS=1024
  run 2 "margin_off" DOM_RADIUS=1 DOM_RELATIVE=0 MAX_DOMAINS=1024
  for M in 1.0 1.2 1.6; do
    for C in 0 0.5 1.5 2.0 3.0; do
      run 2 "rm${M}_cap${C}" DOM_RADIUS=1 DOM_RMULT=$M DOM_RCAP=$C MAX_DOMAINS=1024
    done
  done
  for Q in 0.75 0.95; do run 2 "rq$Q" DOM_RADIUS=1 DOM_RQ=$Q MAX_DOMAINS=1024; done
fi

# ---- STAGE 3. INTENSIVITY + RECURRENCE. Does the count stop growing with the stream? -------------------------
# THE decisive convergence test. A population that is EXTENSIVE in bytes consumed has not converged, whatever its
# value at 120 kB. PRE-REGISTERED, from the isolated test at 120/240/480 segments: the constants go 64 -> 116 ->
# 193 (extensive), radius alone 18 -> 20 -> 25 (nearly flat), radius+fold 4 -> 4 -> 4 (exact).
if has 3; then
  echo "== stage 3: stream-length doubling x recurrence fold =="
  for L in 120000 240000 480000; do
    SL=$L run 3 "len${L}_head"  DOM_RADIUS=0 DOM_RECUR=0 MAX_DOMAINS=1024
    SL=$L run 3 "len${L}_fix"   DOM_RADIUS=1 DOM_RECUR=1 MAX_DOMAINS=1024
    SL=$L run 3 "len${L}_norec" DOM_RADIUS=1 DOM_RECUR=0 MAX_DOMAINS=1024
  done
  echo "== stage 3b: recurrence horizon / min visits / fold ceiling =="
  for H in 16 32 64; do for V in 2 3; do
    run 3 "h${H}_v${V}" DOM_RADIUS=1 DOM_RECUR=1 DOM_RECUR_HORIZON=$H DOM_MIN_VISITS=$V MAX_DOMAINS=1024
  done; done
  # An UNGUARDED fold collapses to ONE domain (measured). DOM_FOLD_MULT bounds the fold to a multiple of the
  # pooled domain radius; if homogeneity falls while live falls, this is the knob that is too loose.
  for F in 1.0 1.5 2.5; do run 3 "foldmult$F" DOM_RADIUS=1 DOM_RECUR=1 DOM_FOLD_MULT=$F MAX_DOMAINS=1024; done
  # THE CADENCE. Domain management shared MANAGE_EVERY=500 with the expert/world populations, and at 937 steps
  # that pass fired ONCE per run (at 468 steps, NEVER) -- so merge, cull and fold were all off by arithmetic in
  # every domain number this project has reported. It now has its own knob. 500 reproduces the old behaviour.
  for E in 50 100 250 500; do run 3 "mgmt$E" DOM_MANAGE_EVERY=$E MAX_DOMAINS=1024; done
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
# ENC_PROTO is the FRACTION of the InfoNCE batch replaced by reservoir pairs, so 1.0 would be the whole batch --
# it is clamped to ENC_BATCH-1 precisely so some of the signal stays grounded in raw stream locality. This is the
# one genuinely self-referential mechanism in the system (the assembler's partition trains the encoder that
# produces the partition), so the kill criterion is deliberately harsh: kill unless V rises >= 0.05 at matched
# budget AND homogeneity stays >= 0.85. A confirmation collapse shows up as BOTH the count and homogeneity falling.
if has 5; then
  echo "== stage 5: reservoir (prototype) positive =="
  for A in 0.0 0.25 0.5 0.75; do
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
