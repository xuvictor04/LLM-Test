#!/bin/bash
# ============ ROBUST (error-correction) sweep -- each feature ISOLATED vs base ============
# Fixed base architecture; each arm turns on ONE robustness feature. Arms: base denoise recon fuzzy + robustall.
#   STEPS=8000 tmux new -s rsw 'bash run_robust_sweep.sh'   (via control: python3 control.py sweep robust)
set -u
cd ~/overarching-package
LOG=~/rsw.log; touch "$LOG"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
say(){ echo "=== $* | $(date +%H:%M) ===" | tee -a "$LOG"; }
export DATASET=${DATASET:-enwik9}; export DIVERSE=${DIVERSE:-1}; export MP_WORKERS=${MP_WORKERS:-4}
[ -f "data/train/eng/${DATASET}.txt" ] || bash setup_lambda.sh >>"$LOG" 2>&1
python3 -c "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)" || { say "NO CUDA"; exit 1; }

STEPS=${STEPS:-8000}
D_MODEL=${D_MODEL:-512}; N_LAYERS=${N_LAYERS:-8}; N_HEADS=${N_HEADS:-8}; CTX=${CTX:-256}; MAX_LEN=${MAX_LEN:-512}
BASE="D_MODEL=$D_MODEL N_LAYERS=$N_LAYERS N_HEADS=$N_HEADS CTX=$CTX MAX_LEN=$MAX_LEN MEMCAP=65536 SURPRISE=reverse DEPTH_GROWTH=0"
DYN="TOKENIZER=dynamic VOCAB=256 VMAX=${VMAX:-32768} MIN_PAIR=${MIN_PAIR:-200} MINT_PER_STEP=4 TOK_DROPOUT=0.1"
ARCH="FABRIC=sparse MOE_K=2 FABRIC_LAYERS=2 CAP_FACTOR=1.25 LB_COST=0.01 COUNTERPARTS=1 M_EMBED=4 SENSE_K=3 SENSE_POS=1 MEMORY=mirror \
      EXPERT_HIDDEN_MULT=4 MUTATE=0 PRUNE_ECO=0 COMPOSE_EMB=0 CORRECT_AT=none NN_INIT=0 MTP_K=1 CTX_START=0 GROWTH_START=0 \
      DENOISE=0 RECON=0 FUZZY=0"
GROW="NMAX=64 N0=16 GRACE=600 PATIENCE=500 COOLDOWN=300 LR_WARMUP=1500"

say "probing batch (d$D_MODEL)..."
RB=${BATCH:-0}
if [ "$RB" -eq 0 ]; then RB=16
  for B in 256 192 128 96 64 48 32; do
    if timeout 260 env $BASE $DYN $ARCH RECON=0.5 NMAX=64 N0=64 BATCH=$B MP_WORKERS=0 WARMUP_STEPS=2 STEPS=3 PROBE_PEAK=1 RECON=0.5 MTP_K=1 EMA_DECAY=0.999 COMPOSE_EMB=0 EVAL_EVERY=99 CKPT_EVERY=999 RUN_DIR=/tmp/rp python3 train.py >/tmp/rp.log 2>&1; then RB=$B; rm -rf /tmp/rp; break; fi
    rm -rf /tmp/rp
  done
fi
LR=$(python3 -c "import math;print(min(1.5e-3, round(6e-4*math.sqrt($RB/16.0),6)))")
ST="STEPS=$STEPS EVAL_EVERY=1000 CKPT_EVERY=${CKPT_EVERY:-3000}"
say "BATCH=$RB LR=$LR STEPS=$STEPS"
run(){ label="$1"; RD="$2"; shift 2; say "$label"; env $BASE LR=$LR $DYN $ARCH $GROW $ST RUN_DIR="$RD" "$@" python3 train.py >>"$LOG" 2>&1; }

ARMS=${ARMS:-"base denoise unmerge"}
for a in $ARMS; do case $a in
  base)      run "base [no robustness features] = control"    rs_base ;;
  denoise)   run "denoising (corrupt input -> predict clean)"  rs_denoise DENOISE=0.1 DENOISE_MODE=mix ;;
  unmerge)   run "tokenizer un-merge (retire stale merges)" rs_unmerge UNMERGE=2000 UNMERGE_MIN=3 ;;
esac; done

say "ROBUST RESULTS (vs rs_base; lower OOD = better):"
python3 read_results.py $(ls -d rs_base rs_denoise rs_unmerge 2>/dev/null) | tee -a "$LOG"
echo "each arm flips ONE robustness knob vs rs_base, so its OOD delta is attributable." | tee -a "$LOG"
