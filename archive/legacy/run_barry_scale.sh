#!/bin/bash
# ============ BARRY AT SCALE (full capability) ============
# Sparse fabric + counterparts + MoE embedders + sense + memory + surprise + growth,
# high expert ceiling (Barry's flat-in-N speed makes this cheap), on the FIXED full-enwik8 corpus.
#   STEPS=30000 NMAX=128 tmux new -s barry 'bash run_barry_scale.sh'
#   watch: watch -n 15 python3 greg_status.py ~/barry_scale.log
set -u
cd ~/overarching-package
LOG=~/barry_scale.log; touch "$LOG"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
say(){ echo "=== $* | $(date +%H:%M) ===" | tee -a "$LOG"; }
notify(){ [ -n "${NOTIFY_URL:-}" ] && curl -s -H "Title: Barry scale" -d "$1" "$NOTIFY_URL" >/dev/null 2>&1 || true; }
export DATASET=${DATASET:-enwik9}          # full 1GB Wikipedia by default (not enwik8)
export DIVERSE=${DIVERSE:-1}               # web + code + reddit by default
[ -f "data/train/eng/${DATASET}.txt" ] || bash setup_lambda.sh >>"$LOG" 2>&1
python3 -c "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)" || { say "NO CUDA"; exit 1; }

STEPS=${STEPS:-50000}; NMAX=${NMAX:-128}; N0=${N0:-16}; MOE_K=${MOE_K:-2}; FABRIC_LAYERS=${FABRIC_LAYERS:-2}
D_MODEL=${D_MODEL:-512}; N_LAYERS=${N_LAYERS:-8}; N_HEADS=${N_HEADS:-8}; CTX=${CTX:-256}; MAX_LEN=${MAX_LEN:-512}
VMAX=${VMAX:-32768}; MIN_PAIR=${MIN_PAIR:-200}          # bigger vocab ceiling + more eager minting (was 8192/400)
BASE="D_MODEL=$D_MODEL N_LAYERS=$N_LAYERS N_HEADS=$N_HEADS CTX=$CTX MAX_LEN=$MAX_LEN MEMCAP=65536 SURPRISE=reverse DEPTH_GROWTH=0"
DYN="TOKENIZER=dynamic VOCAB=256 VMAX=$VMAX MIN_PAIR=$MIN_PAIR MINT_PER_STEP=4 TOK_DROPOUT=0.1"
FULL="FABRIC=sparse MOE_K=$MOE_K FABRIC_LAYERS=$FABRIC_LAYERS CAP_FACTOR=1.25 LB_COST=0.01 COUNTERPARTS=1 M_EMBED=4 SENSE_K=3 SENSE_POS=1 MEMORY=mirror"

# probe batch at the high population (N0=NMAX) so it's safe for the whole grown run
say "probing batch for Barry@scale (d$D_MODEL, up to $NMAX experts, k=$MOE_K, counterparts on)..."
RB=${BATCH:-0}
if [ "$RB" -eq 0 ]; then RB=16
  for B in 256 192 128 96 64 48 32 24 16; do
    if timeout 260 env $BASE $DYN $FULL NMAX=$NMAX N0=$NMAX BATCH=$B WARMUP_STEPS=2 STEPS=4 EVAL_EVERY=99 CKPT_EVERY=999 RUN_DIR=/tmp/bp python3 train.py >/tmp/bp.log 2>&1; then RB=$B; rm -rf /tmp/bp; break; fi
    rm -rf /tmp/bp; echo "  batch=$B OOM" | tee -a "$LOG"
  done
fi
LR=$(python3 -c "import math;print(min(1.5e-3, round(6e-4*math.sqrt($RB/16.0),6)))")
say "BATCH=$RB LR=$LR | experts $N0 -> $NMAX | k=$MOE_K layers=$FABRIC_LAYERS | STEPS=$STEPS"
notify "Barry@scale start: batch=$RB, experts->$NMAX, steps=$STEPS"

env $BASE LR=$LR $DYN $FULL NMAX=$NMAX N0=$N0 BATCH=$RB GRACE=600 PATIENCE=500 COOLDOWN=300 \
    STEPS=$STEPS EVAL_EVERY=2000 CKPT_EVERY=5000 EARLY_STOP=5 LR_WARMUP=1500 RUN_DIR=barry_scale python3 train.py 2>&1 | tee -a "$LOG"
say "DONE"; python3 read_results.py barry_scale 2>/dev/null | tee -a "$LOG"
notify "Barry@scale DONE"
