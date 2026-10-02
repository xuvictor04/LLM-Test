#!/bin/bash
# The CPU operation check's two direct runs, beside its fleet (checks.py has the order):
#     bash direct.sh <the scratch copy's root, holding the fleet's gpu_heldout_out> <a new directory>
# (1) k0 at seed 0, the fleet's toy shape and pins, run twice: at the fleet's probe sizes and at the
#     defaults (EVAL_HOLDOUT_WINDOWS and EVAL_RETENTION_N unset). The probe's size moves no training number.
# (2) k40.s0's final, continued into a second epoch with the probe on (RUN_EPOCHS=2 DATA_RESAMPLE=1).
# run.py runs from the copy's root, as the fleet's runs do.
set -u
C=$(cd "$1" && pwd) || exit 2
mkdir -p "$2" && D=$(cd "$2" && pwd) || exit 2
cd "$C" || exit 2
BASE=(PATH="$PATH" HOME="$HOME" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1 RUN_DEVICE=cpu RUN_SEED=0
      DATA_STREAM_BYTES=56700 TOK_GROW_EVERY=20 DATA_DRAW=planned DATA_SYNTH_HOLDOUT=1 EVAL_RETENTION_EVERY=50
      EVAL_GENERATE=0 TOK_MINT_NOVEL=0 TOK_RETOK_EVERY=0)
env -i "${BASE[@]}" EVAL_HOLDOUT_WINDOWS=256 EVAL_RETENTION_N=24 python3 run.py --max-windows 900 \
    --loss-curve "$D/raised.json" --flush-bytes "$D/raised.bytes.json" --probe-series "$D/raised.probe.json" \
    > "$D/raised.log" 2>&1 &
env -i "${BASE[@]}" python3 run.py --max-windows 900 \
    --loss-curve "$D/default.json" --flush-bytes "$D/default.bytes.json" --probe-series "$D/default.probe.json" \
    > "$D/default.log" 2>&1 &
env -i "${BASE[@]}" TOK_RETOK_EVERY=40 EVAL_HOLDOUT_WINDOWS=256 EVAL_RETENTION_N=24 RUN_EPOCHS=2 DATA_RESAMPLE=1 \
    CKPT_RESUME="$C/gpu_heldout_out/ckpt/k40.s0" CKPT_DIR="$D/child" python3 run.py --max-windows 60 \
    --loss-curve "$D/child.json" --probe-series "$D/child.probe.json" > "$D/child.log" 2>&1 &
wait
for f in raised default child; do echo "$f: $(grep -h "^=== [0-9]* windows" "$D/$f.log")"; done
