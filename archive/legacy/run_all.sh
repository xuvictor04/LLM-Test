#!/bin/bash
# =================== THE WHOLE THING, ONE COMMAND ===================
# Runs everything in sequence, resumable, on the H100 ramp:
#   setup -> Greg diagnostic (aggregate + ablations) -> Barry (sparse) -> auto-pick winner -> completion
# All arms share one probed batch + LR (fair). Ctrl-C / crash: just re-run this same command -> it continues.
#
#   launch:   tmux new -s greg 'bash run_all.sh'      (then Ctrl-b d to detach)
#   watch:    watch -n 15 python3 greg_status.py ~/greg_all.log
#   phone:    NOTIFY_URL=https://ntfy.sh/your-topic bash run_all.sh
#   knobs:    FULL=1 (9 ablation arms not 5) | STEPS=8000 (diagnostic) | STEPS_FINAL=40000 (completion)
#             SKIP_COMPLETION=1 (stop after the comparison) | COMPLETION="ENABLE_REENCODE=0" (override winner)
set -u
cd ~/overarching-package
LOG=~/greg_all.log; touch "$LOG"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
say(){ echo "=== $* | $(date +%H:%M) ===" | tee -a "$LOG"; }
notify(){ [ -n "${NOTIFY_URL:-}" ] && curl -s -H "Title: Greg run" -d "$1" "$NOTIFY_URL" >/dev/null 2>&1 || true; }

# ---- setup (idempotent) ----
export DATASET=${DATASET:-enwik9}; export DIVERSE=${DIVERSE:-1}
[ -f "data/train/eng/${DATASET}.txt" ] || bash setup_lambda.sh >>"$LOG" 2>&1
python3 -c "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)" || { say "NO CUDA - ABORT"; notify "ABORT: no CUDA"; exit 1; }

# ---- config (H100 ramp; env-overridable) ----
STEPS=${STEPS:-8000}; STEPS_FINAL=${STEPS_FINAL:-40000}
D_MODEL=${D_MODEL:-512}; N_LAYERS=${N_LAYERS:-8}; N_HEADS=${N_HEADS:-8}; CTX=${CTX:-256}; MAX_LEN=${MAX_LEN:-512}; NMAX=${NMAX:-24}
BASE="D_MODEL=$D_MODEL N_LAYERS=$N_LAYERS N_HEADS=$N_HEADS CTX=$CTX MAX_LEN=$MAX_LEN MEMCAP=65536 SURPRISE=reverse DEPTH_GROWTH=0"
DYN="TOKENIZER=dynamic VOCAB=256 VMAX=${VMAX:-32768} MIN_PAIR=${MIN_PAIR:-200} MINT_PER_STEP=4 TOK_DROPOUT=0.1"
FRZ="TOKENIZER=data/tokenizer.json VOCAB=8192"
ON="M_EMBED=4 SENSE_K=3 SENSE_POS=1 COUNTERPARTS=1 ENABLE_REENCODE=1 MEMORY=mirror"

# ---- probe one batch on Greg's aggregate (memory ceiling); reuse everywhere ----
say "probing max batch (d$D_MODEL, NMAX=$NMAX, re-encode on)..."
RB=${BATCH:-0}
if [ "$RB" -eq 0 ]; then RB=16
  for B in 256 192 128 96 64 48 32 24 16; do
    if timeout 260 env $BASE $DYN $ON NMAX=$NMAX N0=$NMAX BATCH=$B WARMUP_STEPS=2 STEPS=4 EVAL_EVERY=99 CKPT_EVERY=999 RUN_DIR=/tmp/p python3 train.py >/tmp/p.log 2>&1; then RB=$B; rm -rf /tmp/p; break; fi
    rm -rf /tmp/p; echo "  batch=$B OOM" | tee -a "$LOG"
  done
fi
LR=$(python3 -c "import math;print(min(1.5e-3, round(6e-4*math.sqrt($RB/16.0),6)))")
GROW="NMAX=$NMAX N0=3 BATCH=$RB GRACE=600 PATIENCE=500 COOLDOWN=300"
ST="STEPS=$STEPS EVAL_EVERY=1000 CKPT_EVERY=2500"
say "BATCH=$RB LR=$LR | diagnostic STEPS=$STEPS | completion STEPS=$STEPS_FINAL | arms=$([ -n "${FULL:-}" ] && echo full || echo quick)"
notify "run started: batch=$RB, steps=$STEPS"

runarm(){ label="$1"; RD="$2"; shift 2; say "$label"; notify "start: $label"
  env "$@" $ST RUN_DIR=$RD python3 train.py >>"$LOG" 2>&1
  notify "done: $label | $(grep '\[eval@' "$LOG" | tail -1 | sed -E 's/.*(in-held [0-9.]+ . OOD [0-9.]+).*/\1/')"; }

# ---- PHASE 1: Greg diagnostic (agg = the aggregate; abl_* = leave-one-out) ----
runarm "agg (ALL ideas ON)"        agg        $BASE $DYN $GROW $ON
runarm "abl_sense (-sense book)"   abl_sense  $BASE $DYN $GROW $ON SENSE_K=0
runarm "abl_sparse (sense SPARSE)" abl_sparse $BASE $DYN $GROW $ON SENSE_SLOTS=2048 SENSE_PROMOTE=20
runarm "abl_cp (-counterparts)"    abl_cp     $BASE $DYN $GROW $ON COUNTERPARTS=0
runarm "abl_reenc (-re-encode)"    abl_reenc  $BASE $DYN $GROW $ON ENABLE_REENCODE=0
if [ -n "${FULL:-}" ]; then
  runarm "abl_tok (-dynamic, frozen)" abl_tok  $BASE $FRZ $GROW $ON
  runarm "abl_moe (-MoE embedder)"    abl_moe  $BASE $DYN $GROW $ON M_EMBED=0
  runarm "abl_mem (-memory recall)"   abl_mem  $BASE $DYN $GROW $ON MEMORY=off
fi

# ---- PHASE 2: Barry (sparse fabric; re-encode/counterparts are dense-only) ----
runarm "barry (FABRIC=sparse)"     barry      $BASE $DYN $GROW M_EMBED=4 SENSE_K=3 SENSE_POS=1 MEMORY=mirror FABRIC=sparse MOE_K=2 FABRIC_LAYERS=2 CAP_FACTOR=1.25 LB_COST=0.01

say "COMPARISON (lower OOD = better):"
python3 read_results.py $(ls -d agg abl_sense abl_sparse abl_cp abl_reenc abl_tok abl_moe abl_mem barry 2>/dev/null) | tee -a "$LOG"

# ---- PHASE 3: completion on the winner (auto-picked; override with COMPLETION=, skip with SKIP_COMPLETION=1) ----
if [ -n "${SKIP_COMPLETION:-}" ]; then say "SKIP_COMPLETION set -- done after comparison"; notify "comparison done (completion skipped)"; exit 0; fi
WIN=${COMPLETION:-$(python3 pick_winner.py 2>>"$LOG")}
say "COMPLETION on winner: [$WIN]  STEPS=$STEPS_FINAL"; notify "completion start: [$WIN]"
if echo "$WIN" | grep -q "TOK=frozen"; then TK="$FRZ"; WIN=$(echo "$WIN" | sed 's/TOK=frozen//'); else TK="$DYN"; fi
env $BASE LR=$LR $TK $GROW $ON $WIN STEPS=$STEPS_FINAL EVAL_EVERY=2000 CKPT_EVERY=5000 RUN_DIR=greg_final python3 train.py 2>&1 | tee -a "$LOG"
say "ALL DONE"; notify "ALL DONE -- greg_final trained"
