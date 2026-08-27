#!/bin/bash
# ============ WHOLE SYSTEM, FULLY UNFROZEN, ALL IDEAS ON, ONE RUN (H100) ============
# EVERYTHING ON: unfrozen model key + re-key | ONLINE expanding tokenizer (mints throughout) | ROUTER FABRIC
#   (soft routing + node->node transition matrix + HALT + growth on loss plateau) | ADAPTIVE write-gate | self-consistency B (detect-only) | silhouette | cross-segment
#   composition | performance | generation | checkpoint (-> prompt.py). GRU base (best for online batch-1).
# Nothing frozen anywhere on the product path. Output: ~/$RUN_NAME.txt (default ~/full.txt).
# Set RUN_NAME=<tag> to isolate a run's log + checkpoint + tokenizer from every other run.
#
#   PART A  MECHANICS (cl_bench): forgetting vs replay | editing: memory-delete vs weights-unlearn |
#           drift-survival (model key + re-key) | wrongness self-consistency               <- the capability numbers
#   PART B  PRODUCT LOOP (self_organize, model key end-to-end):
#           self-assemble domains from an UNLABELED real stream (C)
#           -> detect wrong info by self-consistency (B, detect-only: it does NOT delete, because on a
#              surprise-gated store its precision is too low to sweep safely -- reported honestly)
#           -> memory earns-its-keep performance (model alone vs model+memory)
#           -> cross-segment composition (do the segments work together)
#           -> GENERATION (does it produce comprehensible text)
#           -> EDIT/unlearn a whole process by self-provenance (A)
#
# Run:  cd ~ && unzip -o overarching-package.zip && cd overarching-package
#       tmux new -s full 'bash run_full_unfrozen.sh'
set -u
cd ~/overarching-package
# RUN_NAME namespaces EVERY artifact (log, checkpoint, tokenizer) so concurrent or successive runs never clobber
# each other. Default "full" reproduces the historical paths.
# --- GARRY: frozen T33 milestone. Do not edit. Links the shared corpora and namespaces its own runs. ---
export DATA_DIR=${DATA_DIR:-../data}                 # Garry reads the shared corpora from the parent
RUN=${RUN_NAME:-garry}
R=~/${RUN}.txt; : > "$R"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
say(){ echo "" | tee -a "$R"; echo "======== $* | $(date +%H:%M) ========" | tee -a "$R"; }
clean(){ grep -vE "UserWarning|warnings.warn|Consider using|FutureWarning"; }

# ---- CONFIG (override via env if desired) ----
D=${D_MODEL:-256}; STEPS=${STEPS_PER_DOMAIN:-2000}; SEQ=${SEQ:-256}; BATCH=${BATCH:-64}   # D = PART A (mechanics)
DB=${D_MODEL_B:-512}                                    # D for PART B (the product loop; wider = better LM)
MEMCAP=${MEM_CAP:-300000}; DOMS=${DOMAINS:-eng,py,num,c}
# STREAM_LEN is in TOKENS when the tokenizer is on (~1.5M tok ~= 4M bytes of text)
STREAM=${STREAM_LEN:-6000000}          # ONLINE mode counts BYTES -> 6M bytes ~= 62.5k steps at WIN=96
# ---- ALL-IDEAS-ON switches (override via env) ----
TOKZ=${TOKENIZER:-1}; VMAXV=${VMAX:-8192}; MINP=${MIN_PAIR:-80}; MAXT=${MAX_TOK:-16}; GPASS=${GROW_PASSES:-10}; TGCAP=${TOK_GROW_CAP:-1500000}
ADAPT=${WRITE_ADAPTIVE:-1}; WTGT=${WRITE_TARGET:-0.4}
MODELT=${MODEL:-gru}; NHEADS=${HEADS:-8}; MXLEN=${MAXLEN:-512}
# LAYERS must be ARCHITECTURE-AWARE: a deep GRU trains far slower per step (4-layer GRU was ~10x slower + undertrained)
if [ "$MODELT" = "transformer" ]; then NLAYERS=${LAYERS:-4}; else NLAYERS=${LAYERS:-1}; fi
# ---- ROUTER FABRIC (soft distribution over nodes + transition matrix + HALT + plateau growth) ----
FAB=${FABRIC:-1}; FN0=${FAB_N0:-3}; FNMAX=${FAB_NMAX:-6}; FSTEPS=${FAB_STEPS:-3}; FDK=${FAB_DK:-32}
FMINS=${FAB_MIN_STEPS:-0}; FALPHA=${FAB_ALPHA:-0.5}; FPLAT=${FAB_PLATEAU:-0.002}; FCOOL=${FAB_COOLDOWN:-1500}; FWARM=${FAB_WARMUP:-2000}; PND=${PONDER:-0.01}
ONLINE=${TOK_ONLINE:-1}; SEEDV=${SEED_VOCAB:-1024}; GEVERY=${GROW_EVERY:-40}; GBURST=${GROW_BURST:-10}; RETOK=${RETOK_EVERY:-3000}   # ONLINE minting ON (STREAM_LEN is BYTES in this mode)
EXP=${EXPERTS:-0}; MEXP=${MAX_EXPERTS:-256}; ER=${EXPERT_R:-8}; END=${EXPERT_NEW_DIST:-0.55}
ERM=${EXPERT_REP_MULT:-2.5}; ECF=${EXPERT_CULL_FRAC:-0.2}; ECS=${EXPERT_CULL_STALE:-3000}
EGR=${EXPERT_GRACE:-5000}
# removal is RANK-relative + density-dependent, and redundant experts MERGE (keeping their learning) as domains do
CMODE=${CULL_MODE:-rank}; ECR=${EXPERT_CULL_RANK:-0.08}; EPR=${EXPERT_PRESSURE:-0.75}; EMD=${EXPERT_MERGE_DIST:-0.10}; EFW=${EXPERT_FIT_WIN:-4000}

python3 -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" || { echo "NO CUDA -- run on the H100"; exit 1; }

say "0. WALL-CLOCK ESTIMATE (should be minutes; Ctrl-C in 15s if not)"
env DEVICE=cuda DATA_MODE=real DOMAINS=$DOMS D_MODEL=$D SEQ=$SEQ BATCH=$BATCH MEM_CAP=$MEMCAP REKEY=1 LAMBDA=0.5 \
    STEPS_PER_DOMAIN=$STEPS ESTIMATE=1 python3 cl_bench.py 2>&1 | clean | tee -a "$R"
echo ">> too slow? Ctrl-C now and lower STEPS_PER_DOMAIN / MEM_CAP / D_MODEL" | tee -a "$R"; sleep 15

say "PART A -- MECHANICS: forgetting vs replay | memory-delete vs weights-unlearn | drift | wrongness"
env DEVICE=cuda DATA_MODE=real DOMAINS=$DOMS D_MODEL=$D SEQ=$SEQ BATCH=$BATCH MEM_CAP=$MEMCAP REKEY=1 LAMBDA=0.5 \
    WRITE_ADAPTIVE=$ADAPT WRITE_TARGET=$WTGT \
    STEPS_PER_DOMAIN=$STEPS UNLEARN_STEPS=100 python3 cl_bench.py 2>&1 | clean | tee -a "$R"

say "PART B -- PRODUCT LOOP (unfrozen model key end-to-end): assemble -> detect-wrong -> perform -> compose -> generate -> edit"
env DEVICE=cuda DATA_MODE=real DOMAINS=$DOMS D_MODEL=$DB STREAM_LEN=$STREAM WIN=96 SEG_MIN=800 SEG_MAX=2000 \
    TOKENIZER=$TOKZ VMAX=$VMAXV MIN_PAIR=$MINP MAX_TOK=$MAXT GROW_PASSES=$GPASS TOK_GROW_CAP=$TGCAP TOKENIZER_PATH=${TOKENIZER_PATH:-data/tok_$RUN.json} \
    MODEL=$MODELT LAYERS=$NLAYERS HEADS=$NHEADS MAXLEN=$MXLEN \
    TOK_ONLINE=$ONLINE SEED_VOCAB=$SEEDV GROW_EVERY=$GEVERY GROW_BURST=$GBURST RETOK_EVERY=$RETOK \
    FABRIC=$FAB FAB_N0=$FN0 FAB_NMAX=$FNMAX FAB_STEPS=$FSTEPS FAB_DK=$FDK FAB_ALPHA=$FALPHA FAB_MIN_STEPS=$FMINS \
    FAB_PLATEAU=$FPLAT FAB_COOLDOWN=$FCOOL FAB_WARMUP=$FWARM PONDER=$PND \
    EXPERTS=$EXP MAX_EXPERTS=$MEXP EXPERT_R=$ER EXPERT_NEW_DIST=$END EXPERT_REP_MULT=$ERM EXPERT_CULL_FRAC=$ECF EXPERT_CULL_STALE=$ECS EXPERT_GRACE=$EGR \
    CULL_MODE=$CMODE EXPERT_CULL_RANK=$ECR EXPERT_PRESSURE=$EPR EXPERT_MERGE_DIST=$EMD EXPERT_FIT_WIN=$EFW \
    WRITE_ADAPTIVE=$ADAPT WRITE_TARGET=$WTGT \
    SIG_MODE=learned SIG_D=64 ENC_WARMUP=${ENC_WARMUP:-30000} ENC_EVERY=2 ENC_BATCH=128 TEMP=0.1 SHIFT_DIST=0.30 SUSTAIN=2 NEW_DIST=0.35 \
    REKEY_EVERY=300 MANAGE_EVERY=${MANAGE_EVERY:-250} MANAGE_MERGE=${MANAGE_MERGE:-0.22} MANAGE_MIN=20 MANAGE_STALE=3000 GENUINE_MIN=30 \
    EVAL_N=128 WRONG_INJECT=8 WRONG_SWEEP=0 GEN_LEN=${GEN_LEN:-160} GEN_TEMP=${GEN_TEMP:-0.5} \
    SAVE_CKPT=${SAVE_CKPT:-runs/$RUN} \
    KEY_SRC=model MEM_CAP=$MEMCAP python3 self_organize.py 2>&1 | clean | tee -a "$R"

say "WHOLE SYSTEM RUN COMPLETE -> $R  |  message the model: python3 prompt.py CKPT=runs/$RUN  (add MEM=1 to blend memory)"
