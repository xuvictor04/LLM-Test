#!/bin/bash
# ============ EVOLUTIONARY BARRY sweep (cumulative: all 4 built levers) ============
# Wires every feature built for the eco work so each is exercised:
#   (1) bottleneck  EXPERT_HIDDEN_MULT   (2) mutation spawn  MUTATE
#   (3) contribution cull  PRUNE_ECO     (4) cull-metric  CULL_METRIC = energy | traffic | blend
# Plus the multiprocess tokenizer (MP_WORKERS) is ON by default so it's exercised during the run.
# All arms share one probed batch + steps -> fair comparison. Reads out OOD at the end.
#   STEPS=8000 tmux new -s eco 'bash run_eco_sweep.sh'
#   watch: watch -n 15 python3 greg_status.py ~/eco.log
# Subset: ARMS="base bn1 full ftraffic".  Extra arms available: bn2 bn05 harsh.
set -u
cd ~/overarching-package
LOG=~/eco.log; touch "$LOG"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
say(){ echo "=== $* | $(date +%H:%M) ===" | tee -a "$LOG"; }
notify(){ [ -n "${NOTIFY_URL:-}" ] && curl -s -H "Title: eco sweep" -d "$1" "$NOTIFY_URL" >/dev/null 2>&1 || true; }
export DATASET=${DATASET:-enwik9}          # full 1GB Wikipedia by default -- the eco levers need scale
export DIVERSE=${DIVERSE:-1}               # web + code + reddit by default -- specialization needs a diverse corpus
export MP_WORKERS=${MP_WORKERS:-4}         # (4) multiprocess tokenizer ON by default so it's exercised (0 to disable)
[ -f "data/train/eng/${DATASET}.txt" ] || bash setup_lambda.sh >>"$LOG" 2>&1
python3 -c "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)" || { say "NO CUDA"; exit 1; }

STEPS=${STEPS:-8000}
D_MODEL=${D_MODEL:-512}; N_LAYERS=${N_LAYERS:-8}; N_HEADS=${N_HEADS:-8}; CTX=${CTX:-256}; MAX_LEN=${MAX_LEN:-512}
BASE="D_MODEL=$D_MODEL N_LAYERS=$N_LAYERS N_HEADS=$N_HEADS CTX=$CTX MAX_LEN=$MAX_LEN MEMCAP=65536 SURPRISE=reverse DEPTH_GROWTH=0"
DYN="TOKENIZER=dynamic VOCAB=256 VMAX=${VMAX:-32768} MIN_PAIR=${MIN_PAIR:-200} MINT_PER_STEP=4 TOK_DROPOUT=0.1"
COMMON="FABRIC=sparse MOE_K=2 FABRIC_LAYERS=2 CAP_FACTOR=1.25 LB_COST=0.01 COUNTERPARTS=1 M_EMBED=4 SENSE_K=3 SENSE_POS=1 MEMORY=mirror"
GROW="NMAX=64 N0=16 GRACE=600 PATIENCE=500 COOLDOWN=300 LR_WARMUP=1500"

# probe once at the largest population an arm will reach. MP_WORKERS=0 here (a 4-step probe shouldn't spawn workers).
say "probing batch (d$D_MODEL, up to 64 experts)..."
RB=${BATCH:-0}
if [ "$RB" -eq 0 ]; then RB=16
  for B in 256 192 128 96 64 48 32; do
    if timeout 260 env $BASE $DYN $COMMON NMAX=64 N0=64 BATCH=$B MP_WORKERS=0 WARMUP_STEPS=2 STEPS=3 PROBE_PEAK=1 RECON=0.5 MTP_K=1 EMA_DECAY=0.999 COMPOSE_EMB=0 EVAL_EVERY=99 CKPT_EVERY=999 RUN_DIR=/tmp/ep python3 train.py >/tmp/ep.log 2>&1; then RB=$B; rm -rf /tmp/ep; break; fi
    rm -rf /tmp/ep
  done
fi
LR=$(python3 -c "import math;print(min(1.5e-3, round(6e-4*math.sqrt($RB/16.0),6)))")
ST="STEPS=$STEPS EVAL_EVERY=1000 CKPT_EVERY=${CKPT_EVERY:-3000}"
say "BATCH=$RB LR=$LR STEPS=$STEPS | MP_WORKERS=$MP_WORKERS | DATASET=$DATASET DIVERSE=$DIVERSE"
notify "eco sweep start: batch=$RB steps=$STEPS mp=$MP_WORKERS"

run(){ label="$1"; RD="$2"; shift 2; say "$label"; notify "start $RD"
  env $BASE LR=$LR $DYN $COMMON $GROW $ST RUN_DIR="$RD" "$@" python3 train.py >>"$LOG" 2>&1
  notify "done $RD | $(grep '\[eval@' "$LOG" | tail -1 | sed -E 's/.*(OOD [0-9.]+).*/\1/')"; }

# arms: (1) bottleneck spread  (2) mutation  (3) cull  (4) cull-metric variants of the full ecology
ARMS=${ARMS:-"base bn1 mut cull full ftraffic fblend crossover"}
for a in $ARMS; do case $a in
  base)     run "base (4x, no mutate, no cull) = current Barry"       eco_base     EXPERT_HIDDEN_MULT=4   MUTATE=0 PRUNE_ECO=0 ;;
  bn2)      run "(1) bottleneck 2x"                                   eco_bn2      EXPERT_HIDDEN_MULT=2   MUTATE=0 PRUNE_ECO=0 ;;
  bn1)      run "(1) bottleneck 1x"                                   eco_bn1      EXPERT_HIDDEN_MULT=1   MUTATE=0 PRUNE_ECO=0 ;;
  bn05)     run "(1) bottleneck 0.5x (harsh compression)"             eco_bn05     EXPERT_HIDDEN_MULT=0.5 MUTATE=0 PRUNE_ECO=0 ;;
  mut)      run "(2) 1x + mutation spawn"                             eco_mut      EXPERT_HIDDEN_MULT=1   MUTATE=1 MUTATE_STRENGTH=0.05 PRUNE_ECO=0 ;;
  cull)     run "(3) 1x + cull [energy]"                              eco_cull     EXPERT_HIDDEN_MULT=1   MUTATE=0 PRUNE_ECO=1 PRUNE_EVERY=1000 NMIN=12 CULL_METRIC=energy ;;
  full)     run "full evolution [cull=energy]"                        eco_full     EXPERT_HIDDEN_MULT=1   MUTATE=1 MUTATE_STRENGTH=0.05 PRUNE_ECO=1 PRUNE_EVERY=1000 NMIN=12 CULL_METRIC=energy ;;
  ftraffic) run "(4) full evolution [cull=traffic] (router-follows-selection)" eco_ftraffic EXPERT_HIDDEN_MULT=1 MUTATE=1 MUTATE_STRENGTH=0.05 PRUNE_ECO=1 PRUNE_EVERY=1000 NMIN=12 CULL_METRIC=traffic ;;
  fblend)   run "(4) full evolution [cull=blend]"                     eco_fblend   EXPERT_HIDDEN_MULT=1   MUTATE=1 MUTATE_STRENGTH=0.05 PRUNE_ECO=1 PRUNE_EVERY=1000 NMIN=12 CULL_METRIC=blend ;;
  harsh)    run "0.5x + strong mutation + fast cull [energy]"         eco_harsh    EXPERT_HIDDEN_MULT=0.5 MUTATE=1 MUTATE_STRENGTH=0.1  PRUNE_ECO=1 PRUNE_EVERY=500  NMIN=12 CULL_METRIC=energy ;;
  crossover) run "CROSSOVER of top-2 experts (vs mutation of best)" eco_xover MUTATE=1 CROSSOVER=0.6 ;;
esac; done

say "SWEEP RESULTS (lower OOD = better):"
python3 read_results.py $(ls -d eco_base eco_bn2 eco_bn1 eco_bn05 eco_mut eco_cull eco_full eco_ftraffic eco_fblend eco_harsh eco_xover 2>/dev/null) | tee -a "$LOG"
echo "reads: bottleneck (bn*), mutation (mut), cull (cull), full ecology (full), and cull-metric energy/traffic/blend (full/ftraffic/fblend)." | tee -a "$LOG"
notify "eco sweep complete"
