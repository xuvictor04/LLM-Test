#!/bin/bash
# ============ ARCH (representation) sweep -- each feature ISOLATED vs base ============
# Fixed base architecture; each arm turns on ONE representation feature, so its OOD delta is attributable.
# Arms: base(control) compose cdepth correct nninit  + archall (all together).
#   STEPS=8000 tmux new -s asw 'bash run_arch_sweep.sh'   (via control: python3 control.py sweep arch)
set -u
cd ~/overarching-package
LOG=~/asw.log; touch "$LOG"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
say(){ echo "=== $* | $(date +%H:%M) ===" | tee -a "$LOG"; }
export DATASET=${DATASET:-enwik9}; export DIVERSE=${DIVERSE:-1}; export MP_WORKERS=${MP_WORKERS:-4}
[ -f "data/train/eng/${DATASET}.txt" ] || bash setup_lambda.sh >>"$LOG" 2>&1
python3 -c "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)" || { say "NO CUDA"; exit 1; }

STEPS=${STEPS:-8000}
D_MODEL=${D_MODEL:-512}; N_LAYERS=${N_LAYERS:-8}; N_HEADS=${N_HEADS:-8}; CTX=${CTX:-256}; MAX_LEN=${MAX_LEN:-512}
BASE="D_MODEL=$D_MODEL N_LAYERS=$N_LAYERS N_HEADS=$N_HEADS CTX=$CTX MAX_LEN=$MAX_LEN MEMCAP=65536 SURPRISE=reverse DEPTH_GROWTH=0"
DYN="TOKENIZER=dynamic VOCAB=256 VMAX=${VMAX:-32768} MIN_PAIR=${MIN_PAIR:-200} MINT_PER_STEP=4 TOK_DROPOUT=0.1"
# fixed sparse Barry, all NEW features OFF -- each arm flips exactly one representation knob
ARCH="FABRIC=sparse MOE_K=2 FABRIC_LAYERS=2 CAP_FACTOR=1.25 LB_COST=0.01 COUNTERPARTS=1 M_EMBED=4 SENSE_K=3 SENSE_POS=1 MEMORY=mirror \
      EXPERT_HIDDEN_MULT=4 MUTATE=0 PRUNE_ECO=0 DENOISE=0 FUZZY=0 CTX_START=0 GROWTH_START=0 \
      COMPOSE_EMB=0 CORRECT_AT=none NN_INIT=0 MTP_K=1 RECON=0"
GROW="NMAX=64 N0=16 GRACE=600 PATIENCE=500 COOLDOWN=300 LR_WARMUP=1500"

say "probing batch (d$D_MODEL, arch features can add params)..."
RB=${BATCH:-0}
if [ "$RB" -eq 0 ]; then RB=16
  for B in 256 192 128 96 64 48 32; do
    if timeout 260 env $BASE $DYN $ARCH COMPOSE_EMB=0.5 CORRECT_AT=emb,fabric NMAX=64 N0=64 BATCH=$B MP_WORKERS=0 WARMUP_STEPS=2 STEPS=3 PROBE_PEAK=1 RECON=0.5 MTP_K=1 EMA_DECAY=0.999 COMPOSE_EMB=0 EVAL_EVERY=99 CKPT_EVERY=999 RUN_DIR=/tmp/ap python3 train.py >/tmp/ap.log 2>&1; then RB=$B; rm -rf /tmp/ap; break; fi
    rm -rf /tmp/ap
  done
fi
LR=$(python3 -c "import math;print(min(1.5e-3, round(6e-4*math.sqrt($RB/16.0),6)))")
ST="STEPS=$STEPS EVAL_EVERY=1000 CKPT_EVERY=${CKPT_EVERY:-3000}"
say "BATCH=$RB LR=$LR STEPS=$STEPS"
run(){ label="$1"; RD="$2"; shift 2; say "$label"; env $BASE LR=$LR $DYN $ARCH $GROW $ST RUN_DIR="$RD" "$@" python3 train.py >>"$LOG" 2>&1; }

ARMS=${ARMS:-"base compose cdepth correct nninit archall coord nnk"}
for a in $ARMS; do case $a in
  base)    run "base [no representation features] = control"  as_base ;;
  compose) run "compositional embeddings (depth 1)"           as_compose COMPOSE_EMB=0.5 COMPOSE_DEPTH=1 ;;
  cdepth)  run "compositional embeddings (recursive depth 3)"  as_cdepth  COMPOSE_EMB=0.5 COMPOSE_DEPTH=3 COMPOSE_REFRESH=8 ;;
  correct) run "correction hooks (emb+fabric stages)"          as_correct CORRECT_AT=emb,fabric ;;
  nninit)  run "nearest-neighbor embedding init"               as_nninit  NN_INIT=1.0 ;;
  archall) run "all representation features together"          as_all     COMPOSE_EMB=0.5 COMPOSE_DEPTH=3 COMPOSE_REFRESH=8 CORRECT_AT=emb,fabric NN_INIT=0.7 ;;
  coord)   run "expert coordination (layer-global context mix)" as_coord EXPERT_COORD=0.5 ;;
  nnk)     run "NN-init blending top-3 neighbors"             as_nnk     NN_INIT=1.0 NN_INIT_K=3 ;;
esac; done

say "ARCH RESULTS (vs as_base; lower OOD = better):"
python3 read_results.py $(ls -d as_base as_compose as_cdepth as_correct as_nninit as_coord as_nnk as_all 2>/dev/null) | tee -a "$LOG"
echo "each arm flips ONE representation knob vs as_base, so its OOD delta is attributable (nninit = the new warm-start)." | tee -a "$LOG"
