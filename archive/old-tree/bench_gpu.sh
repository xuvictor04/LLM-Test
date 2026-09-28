#!/bin/bash
# ============ GPU THROUGHPUT BENCH ============
# Answers, with measurements rather than argument, the questions blocking the multi-epoch run:
#
#   1. Where does the step time actually GO on a GPU?     -> [BENCH profile] per-component shares
#   2. Is the step LAUNCH-BOUND rather than compute-bound? -> GPU utilization while training. Low SM utilization
#      (say <40%) together with a slow step means the GPU is idling between kernel launches, and a BIGGER card will
#      not help. That is the single most expensive thing to get wrong before renting the big machine.
#   3. Does MODEL=transformer fix it? (parallel over the sequence instead of WIN sequential GRU launches)
#   4. Does AMP=bf16 help, and does TF32 alone already get most of it?
#   5. What does ENC_FUSE cost/buy on a GPU, where it halves sequential launches?
#   6. What is the REAL GB-of-text-per-day, so the multi-epoch run can be sized honestly against GPT-2?
#
# Each config trains a short fixed slice and stops (BENCH=1 skips the eval battery, which is a large fixed cost
# that would swamp a short timing run). Everything is written to bench_out/ and summarized at the end.
#
# Run on a FRESH GPU box:
#     git clone <repo> && cd LLM-Test
#     bash bench_gpu.sh                 # ~25-40 min total
#     cat bench_out/SUMMARY.txt         # <- paste this back
#
# Knobs:  STEPS=2000  GB=1  SKIP_FETCH=1  ONLY=A,C   bash bench_gpu.sh
set -u

OUT=bench_out; mkdir -p "$OUT"
STEPS=${STEPS:-1800}                 # training steps per config (steps ~= STREAM_LEN / WIN)
GB=${GB:-1}                          # how much text to fetch if data is missing
DATA=${DATA:-data_bench}
ONLY=${ONLY:-A,B,C,D,E}

# ---------- 0. environment ----------
echo "=== environment ===" | tee "$OUT/env.txt"
python3 -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),
torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')" 2>&1 | tee -a "$OUT/env.txt"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1 | tee -a "$OUT/env.txt"
if ! python3 -c "import torch" 2>/dev/null; then echo "!! torch missing: pip install -r requirements.txt"; exit 1; fi
# GATE ON CUDA, NOT ON IMPORT. Every arm below hardcodes DEVICE=cuda, so a torch that imports but cannot see the
# GPU burns the 1 GB fetch and then fails all 5 arms one at a time. That is the default outcome on a fresh aarch64
# box installed with an old pin: torch<=2.3's aarch64 wheels were CPU-ONLY, and `torch>=2.1` in requirements.txt
# is happily satisfied by one. Fail here instead, with the fix in the message.
python3 -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" || {
  echo "!! torch imports but torch.cuda.is_available() is False."
  echo "   arch=$(uname -m) torch=$(python3 -c 'import torch;print(torch.__version__)')"
  echo "   On aarch64/Grace this is almost always a CPU-only wheel or a driver older than the wheel's CUDA major."
  echo "   Run: bash preflight.sh   (it prints the exact install command for this box)"; exit 1; }

# ---------- 1. data ----------
# The bench only needs enough text that the stream never wraps; 1 GB is ample and costs one download.
if [ "${SKIP_FETCH:-0}" != "1" ] && [ ! -d "$DATA/train/eng" ]; then
  echo "=== fetching ${GB}GB of text -> $DATA ==="
  pip install -q datasets 2>&1 | tail -1
  python3 fetch_big.py --dataset fineweb-edu --gb "$GB" --out "$DATA" || { echo "!! fetch failed"; exit 1; }
fi
[ -d "$DATA/train/eng" ] || { echo "!! no data at $DATA/train/eng (use SKIP_FETCH=1 DATA=<dir>)"; exit 1; }
echo "corpus: $(du -sh "$DATA" | cut -f1)"

# ---------- 2. config matrix ----------
# name|MODEL|AMP|ENC_FUSE|what it isolates
CONFIGS=(
  "A|gru|off|1|BASELINE - current defaults"
  "B|gru|bf16|1|does bf16 help the GRU path"
  "C|transformer|off|1|does a parallel-over-sequence model beat the sequential GRU"
  "D|transformer|bf16|1|the two wins combined"
  "E|gru|off|0|what the fused encoder pass is worth on a GPU"
)
# NOTE ON A-vs-C: LAYERS defaults to 4 for transformer and 1 for GRU -- at d=768 that is 28.7M vs 53.9M params
# (1.9x), which is the configuration each would actually be RUN at. So "C beats A" is a stronger result than it
# looks, while "C is slower" is NOT evidence the transformer is worse per-parameter. The [BENCH] line prints each
# param count; TRF_LAYERS=1 reruns C/D at matched depth. (The FIRST bench ran at d=128 because D_MODEL_B was read
# by nothing, making both models ~84% vocab tables and the LM a rounding error -- that is fixed above.)
TRF_LAYERS=${TRF_LAYERS:-4}

WIN=${WIN:-256}
# STREAM_LEN is in BYTES but the loop iterates the TOKEN stream, so steps = STREAM_LEN/(WIN*bytes_per_token).
# The first bench asked for 1800 and got 976 because the seeded BPE compresses ~1.84 bytes/token. Scale by it.
BPT=${BPT:-1.85}
STREAM_LEN=$(python3 -c "print(int($STEPS*$WIN*$BPT))")

run_one() {
  local tag=$1 model=$2 amp=$3 fuse=$4 desc=$5
  case ",$ONLY," in *",$tag,"*) ;; *) echo "-- skip $tag"; return;; esac
  local layers=1; [ "$model" = transformer ] && layers=$TRF_LAYERS
  echo ""; echo "=== [$tag] MODEL=$model LAYERS=$layers AMP=$amp ENC_FUSE=$fuse -- $desc ==="
  local log="$OUT/$tag.log" util="$OUT/$tag.util"

  # Sample GPU utilization during the run. READ THIS CAREFULLY: `utilization.gpu` is the FRACTION OF TIME any
  # kernel was resident -- NOT FLOP efficiency -- and this average also covers tokenizer seeding and ENC_WARMUP,
  # which run before the loop is timed. Both effects push it DOWN. The summary reports a tail average (post-startup)
  # alongside the full one; treat a low number as "look closer", never as proof of anything.
  ( nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits -l 1 > "$util" 2>/dev/null ) &
  local sampler=$!

  local t0=$(date +%s)
  DEVICE=cuda DATA_MODE=real DATA_DIR="$DATA" DISK_STREAM=1 CORPUS_CAP=100000000000 \
  STREAM_LEN="$STREAM_LEN" EPOCHS=1 WIN="$WIN" BATCH_W=${BATCH_W:-16} ACCUM=${ACCUM:-2} \
  D_MODEL=${D_MODEL:-768} MODEL="$model" AMP="$amp" ENC_FUSE="$fuse" LAYERS="$layers" \
  TOKENIZER=1 TOK_ONLINE=1 VMAX=${VMAX:-16384} SEED_VOCAB=512 \
  WORLD_MODEL=1 WORLD_FEEDBACK=1 WRITE_ADAPTIVE=1 WRITE_TARGET=0.12 \
  ENC_WARMUP=300 ENC_WARMUP_MIN=150 PROBE=0 PROFILE=1 RATE_EVERY=250 BENCH=1 SEED=7 \
  TOKENIZER_PATH="$OUT/dyntok_$tag.json" \
  python3 self_organize.py > "$log" 2>&1
  local rc=$? t1=$(date +%s)

  kill $sampler 2>/dev/null; wait $sampler 2>/dev/null

  local util_avg="n/a"
  [ -s "$util" ] && util_avg=$(awk -F, '{a[n++]=$1} END{if(!n)exit; s=0;for(i=0;i<n;i++)s+=a[i];
      h=int(n/2); t=0; for(i=h;i<n;i++)t+=a[i]; printf "%.0f%% (tail %.0f%%)", s/n, t/(n-h)}' "$util")
  if [ $rc -ne 0 ]; then
    echo "  FAILED (exit $rc) -- last lines:"; tail -5 "$log" | sed 's/^/    /'
    printf "%-3s %-12s %-5s %-5s %-28s %s\n" "$tag" "$model" "$amp" "$fuse" "FAILED (exit $rc)" "$util_avg" >> "$OUT/rows.txt"
    return
  fi
  local bench=$(grep -m1 "^\[BENCH\]" "$log" | sed 's/^\[BENCH\] //')
  local prof=$(grep -m1 "^\[BENCH profile\]" "$log" | sed 's/^\[BENCH profile\] //')
  echo "  $((t1-t0))s wall | GPU util avg $util_avg"
  echo "  $bench"; echo "  $prof"
  printf "%s\t%s\t%s\t%s\t%ss\t%s\t%s\t%s\n" "$tag" "$model" "$amp" "$fuse" "$((t1-t0))" "$util_avg" "$bench" "$prof" >> "$OUT/rows.txt"
}

rm -f "$OUT/rows.txt"
for c in "${CONFIGS[@]}"; do IFS='|' read -r a b d e f <<< "$c"; run_one "$a" "$b" "$d" "$e" "$f"; done

# ---------- 3. summary ----------
{
  echo "================ GPU BENCH SUMMARY ================"
  cat "$OUT/env.txt"
  echo ""
  echo "steps/config: $STEPS (STREAM_LEN=$STREAM_LEN bytes @ ~${BPT} B/tok) | WIN=$WIN BATCH_W=${BATCH_W:-16} D_MODEL=${D_MODEL:-768}"
  echo ""
  while IFS=$'\t' read -r tag model amp fuse wall util bench prof; do
    echo "[$tag] MODEL=$model AMP=$amp ENC_FUSE=$fuse"
    echo "     wall $wall | GPU util avg $util"
    echo "     $bench"
    echo "     $prof"
  done < "$OUT/rows.txt"
  echo ""
  echo "HOW TO READ THIS:"
  echo "  * The encoder share is DATA-DEPENDENT, so do not carry the ~85% figure over from earlier CPU runs."
  echo "    contrastive_step is shift-gated: it runs every step near a detected domain boundary and every"
  echo "    ENC_EVERY_IDLE (12) steps when the stream is stable. Those CPU numbers came from a 4-domain mix"
  echo "    (eng/py/num/c) that switches constantly; this bench uses single-domain fineweb-edu, where"
  echo "    boundaries are rare and the encoder should throttle itself ~12x. If the encoder is NOT dominant"
  echo "    here, that is the shift-gate working as designed, not a contradiction -- and it means the"
  echo "    bottleneck for the real run depends on which data mix that run uses."
  echo "  * DO NOT read low GPU util as 'launch-bound' on its own. utilization.gpu is time-occupancy, not FLOP"
  echo "    efficiency, and the average includes pre-loop startup. The FIRST bench read 16-22% and the real"
  echo "    in-loop figure was ~40-50%. Use the profile shares and absolute seconds to attribute cost, not util."
  echo "  * The step is dominated by _model_key: it runs ~1952 times per 976 steps on TINY tensors (memory-key"
  echo "    writes + amortized rekey) against ~61 real LM forwards. That is a DISPATCH-COUNT problem, which is"
  echo "    why the transformer loses -- its encode is ~192 aten ops vs the GRU's single fused cuDNN call."
  echo "  * GB/day x days-you-will-run vs GPT-2's ~40GB tells you what data scale is actually reachable."
} > "$OUT/SUMMARY.txt"
cat "$OUT/SUMMARY.txt"
echo ""; echo "=== paste bench_out/SUMMARY.txt back ==="
