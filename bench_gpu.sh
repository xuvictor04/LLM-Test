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
# NOTE ON A-vs-C: LAYERS defaults to 4 for transformer and 1 for GRU, so C/D carry ~8x the parameters of A/B.
# That is deliberate -- it is the configuration each would actually be RUN at -- but it means "C is faster than A"
# is a stronger result than it looks (more model for less time), while "C is slower" is NOT evidence that the
# transformer is worse per-parameter. The [BENCH] line prints the parameter count of each so the two can be read
# apart, and TRF_LAYERS=1 reruns C/D at matched depth if the headline numbers come out ambiguous.
TRF_LAYERS=${TRF_LAYERS:-4}

WIN=${WIN:-256}
STREAM_LEN=$(( STEPS * WIN ))

run_one() {
  local tag=$1 model=$2 amp=$3 fuse=$4 desc=$5
  case ",$ONLY," in *",$tag,"*) ;; *) echo "-- skip $tag"; return;; esac
  local layers=1; [ "$model" = transformer ] && layers=$TRF_LAYERS
  echo ""; echo "=== [$tag] MODEL=$model LAYERS=$layers AMP=$amp ENC_FUSE=$fuse -- $desc ==="
  local log="$OUT/$tag.log" util="$OUT/$tag.util"

  # sample GPU utilization DURING the run: this is what distinguishes "slow because the GPU is saturated"
  # from "slow because the GPU is waiting for kernel launches".
  ( nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits -l 1 > "$util" 2>/dev/null ) &
  local sampler=$!

  local t0=$(date +%s)
  DEVICE=cuda DATA_MODE=real DATA_DIR="$DATA" DISK_STREAM=1 CORPUS_CAP=100000000000 \
  STREAM_LEN="$STREAM_LEN" EPOCHS=1 WIN="$WIN" BATCH_W=${BATCH_W:-16} ACCUM=${ACCUM:-2} \
  D_MODEL_B=${D_MODEL_B:-768} MODEL="$model" AMP="$amp" ENC_FUSE="$fuse" LAYERS="$layers" \
  TOKENIZER=1 TOK_ONLINE=1 VMAX=${VMAX:-16384} SEED_VOCAB=512 \
  WORLD_MODEL=1 WORLD_FEEDBACK=1 WRITE_ADAPTIVE=1 WRITE_TARGET=0.12 \
  ENC_WARMUP=300 ENC_WARMUP_MIN=150 PROBE=0 PROFILE=1 RATE_EVERY=250 BENCH=1 SEED=7 \
  TOKENIZER_PATH="$OUT/dyntok_$tag.json" \
  python3 self_organize.py > "$log" 2>&1
  local rc=$? t1=$(date +%s)

  kill $sampler 2>/dev/null; wait $sampler 2>/dev/null

  local util_avg="n/a"
  [ -s "$util" ] && util_avg=$(awk -F, '{s+=$1;n++} END{if(n)printf "%.0f%%",s/n}' "$util")
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
  echo "steps/config: $STEPS | WIN=$WIN BATCH_W=${BATCH_W:-16} D_MODEL_B=${D_MODEL_B:-768}"
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
  echo "  * GPU util well under ~40% with a slow step = LAUNCH-BOUND. A bigger card will not help;"
  echo "    a parallel-over-sequence model (C/D) or CUDA graphs is what helps."
  echo "  * If C/D beat A/B by a lot, the sequential GRU -- not the encoder's workload -- is the real ceiling."
  echo "  * GB/day x days-you-will-run vs GPT-2's ~40GB tells you what data scale is actually reachable."
} > "$OUT/SUMMARY.txt"
cat "$OUT/SUMMARY.txt"
echo ""; echo "=== paste bench_out/SUMMARY.txt back ==="
