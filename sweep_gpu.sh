#!/bin/bash
# ==================================================================================================
# WHAT SHOULD THIS RUN BE, TO USE THE GPU?  Measured, one process per arm, on the card itself.
# ==================================================================================================
# THE QUESTION IS NOT "HOW FAST IS IT" AND THE ANSWER IS NOT WINDOWS PER SECOND. Learning tracks
# OPTIMIZER STEPS, not windows: at OPT_BATCH_WINDOWS=32 a fixed 400-window budget left the loss at
# 6.67 where batch 1 reached 3.94, because 400 windows is 400 steps at batch 1 and 12 at batch 32.
# So every arm below reports steps/s BESIDE windows/s, and an arm that wins on windows/s and loses
# on steps/s has bought throughput with learning.
#
# WHY THIS TREE CANNOT FILL AN H100 BY TRYING HARDER. One window at the shipped geometry is roughly
# half a GFLOP counting the backward -- the decode (128x128x4096) and MEM.write's key encode are the
# two biggest pieces -- so a 250,000-window run is under a minute of H100 arithmetic. The wall clock
# is KERNEL LAUNCHES and Python, and the dominant launch count is the GRU: LM_CTX sequential
# timesteps per window that nothing can batch away. That is why the arms are what they are:
#
#   batch*   MORE WORK PER LAUNCH, FEWER LAUNCHES -- and fewer optimizer steps per window. The one
#            axis that trades directly against learning, which is why it is measured and not assumed.
#   w*/big   BIGGER KERNELS, THE SAME NUMBER OF THEM. On a launch-bound step this is close to free
#            in wall clock and is the only axis that makes the MODEL better while spending the card
#            (goal A). Watch tokens/s: if it barely moves from base to w1024l2, the step was never
#            compute-bound and the width is being had for nothing.
#   xf*      arch=transformer replaces LM_CTX sequential GRU steps with ONE attention+FFN per layer.
#            If the step is launch-bound this is the largest single lever there is, and it is the
#            question the old tree's bench_gpu.sh asked third and never got an answer to.
#   amp      bf16. Helps arithmetic, not launches, so it should do little HERE and a lot on the
#            wider arms -- which is itself the diagnostic.
#
# A GEOMETRY CHANGE MAKES A RUN NON-COMPARABLE WITH THE EXISTING BASELINE. The 8.3610 -> 1.4920
# curve was taken at width 128, gru, ctx 128; an arm that changes any of those is a new experiment,
# not another sample of that one. The loss column below is for spotting a broken arm, NOT for
# ranking geometries against each other.
#
#     bash sweep_gpu.sh                    # ~15-25 min on an H100
#     WINDOWS=800 ONLY=base,xf,big bash sweep_gpu.sh
#     cat sweep_out/SUMMARY.txt
#
# IT WRITES NO CHECKPOINTS AND TOUCHES NOTHING IN runs/. CKPT_DIR is left unset on purpose: saving
# is the most expensive operation in the loop and a benchmark that pays for it is measuring the
# disk. Nothing here is a training run and none of it should be quoted as one.
set -u

OUT=${OUT:-sweep_out}
WINDOWS=${WINDOWS:-400}
# BIG ENOUGH THAT EVERY ARM REACHES THE BUDGET. At LM_CTX=512 the shipped DATA_STREAM_BYTES=120000
# is 158 windows, so the ctx arms would stop early and be timed on a different amount of work --
# a comparison of two run LENGTHS wearing the labels of two geometries.
BYTES=${BYTES:-6000000}
ONLY=${ONLY:-base,amp,batch8,batch32,w512,w1024l2,xf,xf_amp,big}
# THE SECOND ROUND, OFF BY DEFAULT: ONLY=w2048l2,w1024l4,w1024l2_amp bash sweep_gpu.sh
# The first round stopped at 92M parameters and 1.823 GiB of an H100's 79.2 -- 2.3% of the card --
# with the best arm at 30.8% utilization, so the width curve was nowhere near either wall. These
# three go further along the axis the first round found was cheap, and the third re-asks the bf16
# question where it can actually matter: `amp` was tested at the SHIPPED geometry, where the step
# is not compute-bound and bf16 therefore has nothing to speed up even when it is working.

mkdir -p "$OUT"
S="$OUT/SUMMARY.txt"
: > "$S"

_have() { [[ ",$ONLY," == *",$1,"* ]]; }

echo "=== environment ===" | tee -a "$S"
python3 - <<'PY' 2>&1 | tee -a "$S"
import torch
print("torch", torch.__version__, "cuda_available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device", torch.cuda.get_device_name(0),
          f"{torch.cuda.get_device_properties(0).total_memory/2**30:.1f} GiB")
PY
if ! python3 -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"; then
  echo "!! no CUDA device visible. Every arm below hardcodes RUN_DEVICE=cuda and RUN.process_setup" | tee -a "$S"
  echo "!! takes that string VERBATIM with no is_available() guard, so each arm would raise at its" | tee -a "$S"
  echo "!! first .to() after paying for the corpus and the vocabulary build. Stopping here instead." | tee -a "$S"
  exit 1
fi
echo "=== $WINDOWS windows per arm, DATA_STREAM_BYTES=$BYTES, no checkpoints ===" | tee -a "$S"
echo | tee -a "$S"

# ---------- one arm ----------
# THE GPU SAMPLER RUNS BESIDE THE ARM AND NOT INSIDE IT. torch's own utilization reading is a
# driver call from the process being measured, so it perturbs the thing it measures on a step this
# short; `nvidia-smi -l 1` in another process does not. Its mean over the arm is what answers "is
# the card idling between launches", which is the whole question.
arm() {
  local name="$1"; shift
  _have "$name" || return 0
  local log="$OUT/$name.log" smi="$OUT/$name.smi"
  echo "---- $name : $* ----" | tee -a "$S"
  nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits -l 1 > "$smi" 2>/dev/null &
  local pid=$!
  # env -i IS NOT USED, DELIBERATELY: the arms differ by the levers named here and nothing else, and
  # a scrubbed environment would also drop the proxy and locale settings the corpus fetch needs.
  # Every lever an arm sets is on its own command line, so the SUMMARY line and the run agree.
  env RUN_DEVICE=cuda DATA_STREAM_BYTES="$BYTES" "$@" \
      python3 run.py --max-windows "$WINDOWS" --quiet > "$log" 2>&1
  local rc=$?
  kill $pid 2>/dev/null; wait $pid 2>/dev/null
  if [[ $rc -ne 0 ]]; then
    echo "  FAILED (exit $rc). Last lines:" | tee -a "$S"
    tail -5 "$log" | sed 's/^/    /' | tee -a "$S"
    echo | tee -a "$S"
    return 0
  fi
  python3 - "$log" "$smi" "$name" "$WINDOWS" >> "$S" <<'PY'
import re, sys
log, smi, name, windows = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
t = open(log).read()
m = re.search(r"=== (\d+) windows, (\d+) flushes, (\d+) optimizer steps, \d+ epoch\(s\) in ([\d.]+)s", t)
loss = re.search(r"=== loss ([\d.naif-]+) -> ([\d.naif-]+)", t)
mem = re.search(r"=== peak CUDA memory ([\d.]+) GiB allocated, ([\d.]+) GiB reserved", t)
params = re.search(r"=== (\d+) trainable parameter", t)
if not m:
    print(f"  {name}: could not parse the run summary out of {log}")
    sys.exit(0)
w, fl, st, secs = int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))
utils, mems = [], []
try:
    for line in open(smi):
        a, b = line.split(",")
        utils.append(float(a)); mems.append(float(b))
except Exception:
    pass
# THE SAMPLES BEFORE THE FIRST WINDOW ARE THE CORPUS AND THE VOCABULARY BUILD, which are CPU work
# on a cold GPU, so a mean over the whole file reports a card that was idle for reasons that have
# nothing to do with the step. The tail is taken instead, and the count is printed so a reader can
# see how much of the arm it covers.
tail = utils[len(utils) // 2:] if len(utils) >= 4 else utils
gpu = f"{sum(tail)/len(tail):5.1f}% mean, {max(tail):5.1f}% peak, n={len(tail)}" if tail else "no samples"
print(f"  {name:<9} {w:>6} win {st:>6} steps {secs:8.1f}s "
      f"| {w/max(secs,1e-9):8.2f} win/s {st/max(secs,1e-9):8.2f} STEP/s "
      f"| loss {loss.group(1) if loss else '?'} -> {loss.group(2) if loss else '?'} "
      f"| {params.group(1) if params else '?'} params "
      f"| {mem.group(1) if mem else '?'} GiB peak | GPU {gpu}")
PY
  echo >> "$S"
}

arm base
arm amp      RUN_AMP=bf16
arm batch8   OPT_BATCH_WINDOWS=8
arm batch32  OPT_BATCH_WINDOWS=32
arm w512     LM_WIDTH=512
arm w1024l2  LM_WIDTH=1024 LM_LAYERS=2
arm xf       LM_ARCH=transformer LM_WIDTH=512 LM_LAYERS=4
arm xf_amp   LM_ARCH=transformer LM_WIDTH=512 LM_LAYERS=4 RUN_AMP=bf16
arm big      LM_WIDTH=768 LM_LAYERS=3 LM_CTX=256
arm w2048l2       LM_WIDTH=2048 LM_LAYERS=2
arm w1024l4       LM_WIDTH=1024 LM_LAYERS=4
arm w1024l2_amp   LM_WIDTH=1024 LM_LAYERS=2 RUN_AMP=bf16

echo "==================================================================================" | tee -a "$S"
echo "READ STEP/s, NOT win/s. An arm that wins on win/s and loses on STEP/s has bought" | tee -a "$S"
echo "throughput with learning -- 400 windows is 400 optimizer steps at batch 1 and 12" | tee -a "$S"
echo "at batch 32, and the loss column shows what that costs over one fixed budget." | tee -a "$S"
echo "READ GPU% AGAINST win/s. Low utilization WITH a slow step means the card is idling" | tee -a "$S"
echo "between kernel launches, and a bigger card will not help -- only bigger kernels" | tee -a "$S"
echo "(width, layers, ctx) or fewer of them (arch=transformer) will." | tee -a "$S"
echo "THE LOSS COLUMN DOES NOT RANK GEOMETRIES. Different width/arch/ctx are different" | tee -a "$S"
echo "experiments; it is there to spot an arm that is broken, not one that is better." | tee -a "$S"
echo "==================================================================================" | tee -a "$S"
cat "$S"
