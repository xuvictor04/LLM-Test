#!/usr/bin/env bash
# ---------------------------------------------------------------------------------------------------------------
# longrun.sh -- the multi-day run. Everything before this measured a system inside its own warmup.
#
#   bash longrun.sh fetch     pull ~39 GB across FOUR distinct distributions (hours; resumable)
#   bash longrun.sh run       launch. survives disconnect. writes runs/long/
#   bash longrun.sh resume    continue from the last checkpoint after a crash or a reboot
#   bash longrun.sh watch     what it is doing right now
#
# WHY THIS RUN EXISTS, in one number. `step` counts WINDOWS, so a 4 MB stream at WIN=256 is ~6,500 steps. Two
# schedules in the fabric are longer than that:
#     PONDER_WARM = 8000    _pw = min(1.0, step/8000)  -- peaked at 0.81 and never reached full strength
#     FAB_MIN_STEPS = 0     HALT never blocked, so the router could write the nodes off in the first few hundred
# "the router HALTs 90%, mean routed depth 0.10 of 4" and "the fabric is worth ~0 bits/byte" were therefore not
# measurements of the fabric. They were measurements of a warmup that never completed. Both knobs are LEFT ALONE
# here on purpose: the point is to run long enough that the designed schedule finishes, not to change the schedule.
#
# FOUR DISTINCT SOURCES, not one big one. PHASED tests catastrophic forgetting by having processes enter and fade,
# which needs >= 2 processes that are genuinely different -- a single-corpus run degenerates to stationary and the
# forgetting test becomes vacuous. 40 GB of fineweb into `eng` alone would have bought scale and thrown away the
# experiment. These four are different registers (web / encyclopedic / dialogue / mixed-incl-code), so a domain
# boundary is a real distribution change rather than a change of paragraph.
set -u

WHICH=${1:-run}
OUT=${OUT:-runs/long}
DD=${DATA_DIR:-data_big}

# Per-epoch stream size. NOT the corpus size: build_stream materialises STREAM_LEN in RAM as a Python list, so this
# is bounded by memory, while EPOCHS x STREAM_LEN is what actually gets consumed. 32 MB/epoch x 1250 epochs ~ 40 GB.
# Each epoch RESAMPLES from the mmap under DISK_STREAM=1, so an epoch is fresh material, not a replay.
SL=${STREAM_LEN:-32000000}
EP=${EPOCHS:-1250}

case "$WHICH" in
fetch)
  python3 -c "import datasets" 2>/dev/null || { echo "need: pip install datasets  (use a THROWAWAY venv -- upgrading numpy under an NGC torch breaks its ABI; see preflight.sh)"; exit 1; }
  set -x
  python3 fetch_big.py --dataset fineweb-edu --domain eng  --gb 20 --out "$DD" --resume
  python3 fetch_big.py --dataset wikipedia   --domain wiki --gb  8 --out "$DD" --resume
  python3 fetch_big.py --dataset pile        --domain mix  --gb 10 --out "$DD" --resume
  python3 fetch_big.py --dataset oasst1      --domain chat --gb  1 --out "$DD" --resume
  set +x
  echo; echo "on disk:"; du -sh "$DD"/train/* 2>/dev/null
  echo "re-run 'bash longrun.sh fetch' to continue any pull that stopped short -- --resume skips what it already has."
  ;;

run|resume)
  for d in eng wiki mix chat; do
    [ -n "$(ls "$DD/train/$d"/part*.txt 2>/dev/null)" ] || { echo "!! $DD/train/$d is empty -- run 'bash longrun.sh fetch' first"; exit 1; }
  done
  mkdir -p "$OUT"
  R=""
  if [ "$WHICH" = resume ]; then
    [ -f "$OUT/ck/ckpt.pt" ] || { echo "!! no checkpoint at $OUT/ck/ckpt.pt to resume from"; exit 1; }
    R="RESUME=$OUT/ck"
    echo "resuming from $OUT/ck (weights + both optimizers + memory store + domain centroids + recurrence clock)"
  fi
  # CKPT_EVERY at ~50k steps is roughly half-hourly at the observed ~54 steps/s. Two generations are kept
  # (ckpt.pt + ckpt.prev.pt), so budget ~2x the checkpoint size; the memory store dominates it at MEM_CAP=200000.
  env DATA_MODE=real DATA_DIR="$DD" DOMAINS=eng,wiki,mix,chat DEVICE=cuda DISK_STREAM=1 \
      CORPUS_CAP=100000000000 STREAM_LEN=$SL EPOCHS=$EP D_MODEL=${D_MODEL:-768} WIN=256 BATCH_W=16 \
      VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 \
      ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MAX_DOMAINS=1000000 MEM_CAP=200000 MEM_QUOTA=${MEM_QUOTA:-3125} \
      CKPT_EVERY=${CKPT_EVERY:-50000} RATE_EVERY=5000 PROFILE=0 $R \
      SAVE_CKPT="$OUT/ck" nohup python3 self_organize.py >> "$OUT/run.log" 2>&1 &
  echo "pid $! -> $OUT/run.log"
  echo "  bash longrun.sh watch      # progress"
  echo "  kill -USR1 $!              # checkpoint NOW without stopping"
  echo "  bash longrun.sh resume     # after a crash or reboot"
  ;;

watch)
  [ -f "$OUT/run.log" ] || { echo "no $OUT/run.log yet"; exit 1; }
  echo "=== last progress"; grep -a -E "\[rate\]|\[epoch |\[PHASE |\[saved checkpoint" "$OUT/run.log" | tail -12
  echo; echo "=== anything wrong"; grep -a -E "!! |Traceback|Error" "$OUT/run.log" | tail -8
  echo; echo "=== live"; tail -3 "$OUT/run.log"
  ;;

*) echo "usage: bash longrun.sh [fetch|run|resume|watch]"; exit 1 ;;
esac
