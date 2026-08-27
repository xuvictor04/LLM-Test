#!/bin/bash
# ============ FULL continual-learning test suite (H100) ============
# 1. wall-clock ESTIMATE (the safeguard)  ->  15s abort window
# 2. EDITABLE-MEMORY scale-test: forgetting vs replay | editing vs weights-unlearn | wrongness | drift fix   (cl_bench)
# 3. SELF-ORGANIZE: self-assemble domains from an UNLABELED real stream, edit by self-provenance             (self_organize)
# Everything on REAL corpora (eng/py/num/c). Results -> ~/cl_results.txt
#   edit the CONFIG block, then:  tmux new -s cl 'bash run_cl_test.sh'
set -u
cd ~/overarching-package
R=~/cl_results.txt; : > "$R"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
say(){ echo "" | tee -a "$R"; echo "======== $* | $(date +%H:%M) ========" | tee -a "$R"; }
clean(){ grep -vE "UserWarning|warnings.warn|Consider using|FutureWarning"; }

# ---- CONFIG (tune these; the estimate tells you the cost of each) ----
D=${D_MODEL:-256}; STEPS=${STEPS_PER_DOMAIN:-2000}; SEQ=${SEQ:-256}; BATCH=${BATCH:-64}
MEMCAP=${MEM_CAP:-300000}; DOMS=${DOMAINS:-eng,py,num,c}; STREAM=${STREAM_LEN:-2000000}
COMMON="DEVICE=cuda DATA_MODE=real DOMAINS=$DOMS D_MODEL=$D SEQ=$SEQ BATCH=$BATCH MEM_CAP=$MEMCAP REKEY=1 LAMBDA=0.5 STEPS_PER_DOMAIN=$STEPS"

python3 -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" || { echo "NO CUDA -- run on the H100"; exit 1; }

say "1. WALL-CLOCK ESTIMATE (should be minutes; Ctrl-C in 15s if not)"
env $COMMON ESTIMATE=1 python3 cl_bench.py 2>&1 | clean | tee -a "$R"
echo ">> if the TOTAL above is more than you want, Ctrl-C now and lower STEPS_PER_DOMAIN / MEM_CAP / D_MODEL" | tee -a "$R"
sleep 15

say "2. EDITABLE-MEMORY scale-test (forgetting vs replay | editing vs weights-unlearn | wrongness | drift fix)"
env $COMMON UNLEARN_STEPS=100 python3 cl_bench.py 2>&1 | clean | tee -a "$R"

say "3. SELF-ORGANIZE (unlabeled real stream -> self-assembled domains -> edit by self-provenance + GENUINENESS)"
echo "   [part 3 is bounded by STREAM_LEN=$STREAM (~$((STREAM/128)) windows); learned encoder adds warmup+contrastive -- expect a few min each]" | tee -a "$R"
say "3a. LEARNED signature + UNFROZEN MODEL memory key (full product path: learned sig + model key + re-keying + management)"
echo "   [watch the training-curve line: if loss still dropping / separation still rising at the end, raise ENC_WARMUP further]" | tee -a "$R"
env DEVICE=cuda DATA_MODE=real DOMAINS=$DOMS D_MODEL=$D STREAM_LEN=$STREAM WIN=128 SEG_MIN=800 SEG_MAX=2000 \
    SIG_MODE=learned SIG_D=64 ENC_WARMUP=${ENC_WARMUP:-30000} ENC_EVERY=2 ENC_BATCH=128 TEMP=0.1 SHIFT_DIST=0.30 SUSTAIN=2 NEW_DIST=0.35 \
    REKEY_EVERY=300 MANAGE_EVERY=${MANAGE_EVERY:-250} MANAGE_MERGE=${MANAGE_MERGE:-0.22} MANAGE_MIN=20 MANAGE_STALE=3000 GENUINE_MIN=30 EVAL_N=128 \
    KEY_SRC=model MEM_CAP=$MEMCAP python3 self_organize.py 2>&1 | clean | tee -a "$R"
say "3b. LEARNED signature + FROZEN memory key (baseline: isolates whether the unfrozen key fixes edit-leakage)"
env DEVICE=cuda DATA_MODE=real DOMAINS=$DOMS D_MODEL=$D STREAM_LEN=$STREAM WIN=128 SEG_MIN=800 SEG_MAX=2000 \
    SIG_MODE=learned SIG_D=64 ENC_WARMUP=${ENC_WARMUP:-30000} ENC_EVERY=2 ENC_BATCH=128 TEMP=0.1 SHIFT_DIST=0.30 SUSTAIN=2 NEW_DIST=0.35 \
    REKEY_EVERY=300 MANAGE_EVERY=250 MANAGE_MERGE=0.22 MANAGE_MIN=20 MANAGE_STALE=3000 GENUINE_MIN=30 EVAL_N=128 \
    KEY_SRC=frozen MEM_CAP=$MEMCAP python3 self_organize.py 2>&1 | clean | tee -a "$R"

say "3c. bigram signature (frozen byte-stat baseline, for comparison)"
env DEVICE=cuda DATA_MODE=real DOMAINS=$DOMS D_MODEL=$D STREAM_LEN=$STREAM WIN=128 SEG_MIN=800 SEG_MAX=2000 \
    SIG_MODE=bigram SIG_DIM=512 SHIFT_DIST=0.22 SUSTAIN=2 NEW_DIST=0.35 GENUINE_MIN=30 MEM_CAP=$MEMCAP python3 self_organize.py 2>&1 | clean | tee -a "$R"

say "FULL CL TEST COMPLETE -> ~/cl_results.txt"
echo "paste ~/cl_results.txt back for analysis." | tee -a "$R"
