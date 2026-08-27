#!/bin/bash
# ============ TRAINING-METHODS sweep (each lever ISOLATED vs base) ============
# Fixed base architecture (features off); each arm changes ONE training method, so the OOD delta is attributable.
# Arms: base(control) cosine wsd ema ls zloss mtp gacc lion  + trainall (the training bundle).
#   STEPS=8000 tmux new -s tsw 'bash run_training_sweep.sh'   (via control: python3 control.py sweep training)
set -u
cd ~/overarching-package
LOG=~/tsw.log; touch "$LOG"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
say(){ echo "=== $* | $(date +%H:%M) ===" | tee -a "$LOG"; }
export DATASET=${DATASET:-enwik9}; export DIVERSE=${DIVERSE:-1}; export MP_WORKERS=${MP_WORKERS:-4}
[ -f "data/train/eng/${DATASET}.txt" ] || bash setup_lambda.sh >>"$LOG" 2>&1
python3 -c "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)" || { say "NO CUDA"; exit 1; }

STEPS=${STEPS:-8000}
D_MODEL=${D_MODEL:-512}; N_LAYERS=${N_LAYERS:-8}; N_HEADS=${N_HEADS:-8}; CTX=${CTX:-256}; MAX_LEN=${MAX_LEN:-512}
BASE="D_MODEL=$D_MODEL N_LAYERS=$N_LAYERS N_HEADS=$N_HEADS CTX=$CTX MAX_LEN=$MAX_LEN MEMCAP=65536 SURPRISE=reverse DEPTH_GROWTH=0"
DYN="TOKENIZER=dynamic VOCAB=256 VMAX=${VMAX:-32768} MIN_PAIR=${MIN_PAIR:-200} MINT_PER_STEP=4 TOK_DROPOUT=0.1"
# fixed BASE architecture: sparse Barry with the NEW features OFF, so only the training method varies
ARCH="FABRIC=sparse MOE_K=2 FABRIC_LAYERS=2 CAP_FACTOR=1.25 LB_COST=0.01 COUNTERPARTS=1 M_EMBED=4 SENSE_K=3 SENSE_POS=1 MEMORY=mirror \
      EXPERT_HIDDEN_MULT=4 MUTATE=0 PRUNE_ECO=0 COMPOSE_EMB=0 CORRECT_AT=none RECON=0 DENOISE=0 FUZZY=0 CTX_START=0 GROWTH_START=0"
GROW="NMAX=64 N0=16 GRACE=600 PATIENCE=500 COOLDOWN=300 LR_WARMUP=1500"

say "probing batch (d$D_MODEL)..."
RB=${BATCH:-0}
if [ "$RB" -eq 0 ]; then RB=16
  for B in 256 192 128 96 64 48 32; do
    if timeout 260 env $BASE $DYN $ARCH NMAX=64 N0=64 BATCH=$B MP_WORKERS=0 WARMUP_STEPS=2 STEPS=3 PROBE_PEAK=1 RECON=0.5 MTP_K=1 EMA_DECAY=0.999 COMPOSE_EMB=0 EVAL_EVERY=99 CKPT_EVERY=999 RUN_DIR=/tmp/tp python3 train.py >/tmp/tp.log 2>&1; then RB=$B; rm -rf /tmp/tp; break; fi
    rm -rf /tmp/tp
  done
fi
LR=$(python3 -c "import math;print(min(1.5e-3, round(6e-4*math.sqrt($RB/16.0),6)))")
ST="STEPS=$STEPS EVAL_EVERY=1000 CKPT_EVERY=${CKPT_EVERY:-3000}"
say "BATCH=$RB LR=$LR STEPS=$STEPS | MP_WORKERS=$MP_WORKERS"

run(){ label="$1"; RD="$2"; shift 2; say "$label"
  env $BASE LR=$LR $DYN $ARCH $GROW $ST RUN_DIR="$RD" "$@" python3 train.py >>"$LOG" 2>&1; }

ARMS=${ARMS:-"base wsd ema ls mtp difficulty"}
for a in $ARMS; do case $a in
  base)     run "base [constant LR] = control"          ts_base     LR_SCHEDULE=constant ;;
  wsd)      run "WSD (stable-then-decay)"                ts_wsd      LR_SCHEDULE=wsd WSD_DECAY_FRAC=0.2 ;;
  ema)      run "weight EMA"                             ts_ema      LR_SCHEDULE=constant EMA_DECAY=0.999 ;;
  ls)       run "label smoothing"                        ts_ls       LR_SCHEDULE=constant LABEL_SMOOTH=0.05 ;;
  mtp)      run "multi-token prediction (k=2)"           ts_mtp      LR_SCHEDULE=constant MTP_K=2 ;;
  difficulty) run "difficulty curriculum (easy windows first)" ts_diff DIFFICULTY_CURR=4000 ;;
esac; done

say "TRAINING-METHODS RESULTS (vs ts_base; lower OOD = better):"
python3 read_results.py $(ls -d ts_base ts_wsd ts_ema ts_ls ts_mtp ts_diff 2>/dev/null) | tee -a "$LOG"
echo "each arm changes ONE training knob vs ts_base, so its OOD delta is attributable to that lever." | tee -a "$LOG"
