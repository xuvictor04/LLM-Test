#!/bin/bash
# The CPU operation check's direct runs, beside its fleet (checks.py has the order):
#     bash direct.sh <the scratch copy's root, holding the fleet's gpu_heldout_real_out> <a new directory>
# (1) k40.s0's final, continued into a second epoch with the probe on (RUN_EPOCHS=2 DATA_RESAMPLE=1), at the fleet's toy
#     shape and pins: a real-text final is a parent that continues.
# (2) The draw pair without SIG's pre-loop warm-up: k40 at 'planned' and at 'replay' 0.27, seeds 0 and 1, the fleet's
#     shape and pins with SIG_WARMUP=0, 30 windows each. The warm-up draws its pairs from the whole epoch-0 stream
#     (spine/compose.py::_signature_units), which 'replay' changes after phase 1; without it nothing reads past the
#     window being trained but OPT, whose rate prices each draw's epoch.
# run.py runs from the copy's root, as the fleet's runs do.
set -u
C=$(cd "$1" && pwd) || exit 2
mkdir -p "$2" && D=$(cd "$2" && pwd) || exit 2
cd "$C" || exit 2
BASE=(PATH="$PATH" HOME="$HOME" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1 RUN_DEVICE=cpu
      DATA_STREAM_BYTES=64800 TOK_GROW_EVERY=20 OPT_LR_WARMUP=20 DATA_SOURCE=real DATA_DRAW=planned EVAL_RETENTION_EVERY=30
      EVAL_HOLDOUT_WINDOWS=256 EVAL_RETENTION_N=24 EVAL_GENERATE=0 TOK_MINT_NOVEL=0 TOK_RETOK_EVERY=40)
env -i "${BASE[@]}" RUN_SEED=0 RUN_EPOCHS=2 DATA_RESAMPLE=1 CKPT_RESUME="$C/gpu_heldout_real_out/ckpt/k40.s0" \
    CKPT_DIR="$D/child" python3 run.py --max-windows 60 --loss-curve "$D/child.json" \
    --probe-series "$D/child.probe.json" --trust-series "$D/child.trust.json" > "$D/child.log" 2>&1 &
for s in 0 1; do
  env -i "${BASE[@]}" RUN_SEED=$s SIG_WARMUP=0 python3 run.py --max-windows 30 --loss-curve "$D/nowarm.s$s.json" \
      --flush-bytes "$D/nowarm.s$s.bytes.json" > "$D/nowarm.s$s.log" 2>&1 &
  env -i "${BASE[@]}" RUN_SEED=$s SIG_WARMUP=0 DATA_DRAW=replay DATA_REPLAY_SHARE=0.27 python3 run.py --max-windows 30 \
      --loss-curve "$D/nowarm_replay.s$s.json" > "$D/nowarm_replay.s$s.log" 2>&1 &
done
wait
for f in child nowarm.s0 nowarm_replay.s0 nowarm.s1 nowarm_replay.s1; do
  echo "$f: $(grep -h "^=== [0-9]* windows" "$D/$f.log")"
done
