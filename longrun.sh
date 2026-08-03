#!/usr/bin/env bash
# ---------------------------------------------------------------------------------------------------------------
# longrun.sh -- the multi-day run. Everything before this measured a system inside its own warmup.
#
#   bash longrun.sh pilot     MB PROOF OF CONCEPT first: 60 MB English, 8 epochs, ~15-20 min. Run before the GB run.
#   bash longrun.sh pilot-add py <hf-dataset> 0.06    add an area at MB scale and measure what it cost
#   bash longrun.sh fetch     pull 20 GB of English (hours; resumable)
#   bash longrun.sh add NAME DATASET GB    add a NEW area to the trained system and measure what it costs
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
# SIG_WIN=614 IS SET DELIBERATELY. The signature width is fixed for a run while the LOOP STRIDE grows with the
# tokenizer: at WIN=256 the stride starts near 384 B and reaches ~614 B once the vocabulary has compressed. Left
# at its default the signature encoder starts at 100% coverage and ends around 62% -- labelling material it never
# read. 614 covers the stride throughout. The cost is real and worth stating: early in the run the window is
# wider than one loop step, so consecutive signatures overlap and boundary detection is slightly smoothed. Full
# coverage of the material being labelled is the better end of that trade.
#
# ENGLISH FIRST, THEN ADD -- and English is ONE corpus, not two.
# Splitting English into `eng` and `web` was us imposing a partition on material that has none, and then scoring
# the system against our own split. Every domain in an English-only run is DISCOVERED by the assembler; nothing
# here tells it where the boundaries are. A single corpus does mean the spliced phase schedule degenerates to
# stationary -- and that is honest, because the non-stationarity that matters is not a splice we manufactured.
# It is a genuinely new area ARRIVING, which is what `add` does to an already-trained system.
# What makes that measurable is the held-out probe keyed by domain NAME, stored in every checkpoint. Every other
# retention figure is computed on the CURRENT stream, so the moment a new domain appears it cannot answer the one
# question that matters -- did adding it damage the English? The cross-boundary section reports exactly that,
# with an error bar, and says HELD when the change is inside it.
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
  # BALANCED ON PURPOSE. build_stream picks each segment with random.choice(act) -- UNIFORM over the active
  # domains, never weighted by corpus size -- so every domain contributes the SAME stream volume however much text
  # it has. An unbalanced pull does not give the big domain more attention; it gives the SMALL one more REPETITION.
  # That is also why `add` takes a --gb comparable to these: a 100 MB new area against 10 GB of English is not a
  # small addition, it is the same fraction of the stream read a hundred times over.
  # ENGLISH FIRST, and English is ONE corpus. The abstract and structured material (code, maths, dialogue) is
  # deliberately NOT here -- it gets ADDED LATER, to a system that has already learned English, which is the
  # actual continual-learning claim. Front-loading every domain would have tested "can it learn four things at
  # once", a question nobody asked.
  set -x
  python3 fetch_big.py --dataset ${ENG_SRC:-fineweb-edu} --domain eng --gb ${ENG_GB:-20} --out "$DD" --resume
  set +x
  echo; echo "on disk:"; du -sh "$DD"/train/* 2>/dev/null
  echo "re-run 'bash longrun.sh fetch' to continue any pull that stopped short -- --resume skips what it already has."
  ;;

run|resume)
  for d in eng; do
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
  env DATA_MODE=real DATA_DIR="$DD" DOMAINS=eng DEVICE=cuda DISK_STREAM=1 \
      CORPUS_CAP=100000000000 STREAM_LEN=$SL EPOCHS=$EP D_MODEL=${D_MODEL:-768} WIN=256 BATCH_W=16 \
      VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 SIG_WIN=${SIG_WIN:-614} \
      ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MEM_CAP=200000 MEM_QUOTA=${MEM_QUOTA:-3125} \
      CKPT_EVERY=${CKPT_EVERY:-50000} RATE_EVERY=5000 PROFILE=0 $R \
      SAVE_CKPT="$OUT/ck" nohup python3 self_organize.py >> "$OUT/run.log" 2>&1 &
  echo "pid $! -> $OUT/run.log"
  echo "  bash longrun.sh watch      # progress"
  echo "  kill -USR1 $!              # checkpoint NOW without stopping"
  echo "  bash longrun.sh resume     # after a crash or reboot"
  ;;

pilot)
  # THE MB PROOF OF CONCEPT, before 20 GB of anything. Same corpus, same code path, ~1/300th the data.
  # Sized so it is a real test rather than a toy: STREAM_LEN 4 MB x 8 epochs = 32 MB consumed, which at
  # ~6,500 steps per epoch is ~52,000 steps -- the FIRST configuration in this project to pass PONDER_WARM=8000
  # and BAL_WARM=4000, so the fabric schedule completes here too. ~15-20 min on a GH200.
  P_DD=${PILOT_DIR:-data_pilot}
  # ONE corpus. English is English -- splitting it into `eng` and `web` was us imposing a partition on material
  # that has none, and then measuring the system against our own split. The domains in an English-only run come
  # from the ASSEMBLER, discovered in the stream. Nothing here tells it where the boundaries are.
  if [ -z "$(ls "$P_DD/train/eng"/part*.txt 2>/dev/null)" ]; then
    python3 -c "import datasets" 2>/dev/null || { echo "need: pip install datasets (throwaway venv -- see preflight.sh)"; exit 1; }
    python3 fetch_big.py --dataset ${PILOT_SRC:-fineweb-edu} --domain eng --gb ${PILOT_GB:-0.06} --out "$P_DD" --resume || exit 1
  fi
  mkdir -p "$OUT"
  P_SL=${STREAM_LEN:-4000000}; P_EP=${EPOCHS:-8}
  # Report the ACTUAL settings, not the defaults -- a banner that lies when overridden is how a run gets filed
  # under the wrong description weeks later.
  echo "pilot: ONE English corpus, domains self-assembled | $((P_SL/1000)) kB/epoch x $P_EP epochs = $((P_SL*P_EP/1000)) kB consumed | ~$((P_SL*P_EP/614)) steps"
  # BOTH ARCHITECTURES. The base LM is a GRU by default and every number this project has produced is a GRU
  # number; MODEL=transformer (4 layers, 8 heads, causal) has never been run here. If proper language is the goal
  # then the 1-layer GRU may be the ceiling rather than the system, and the only way to know which is to run both
  # on the identical stream. ~2x the time, and it settles how much of the bits/byte gap is architecture.
  for ARCH in ${PILOT_ARCH:-gru transformer}; do
  echo; echo "################  base LM: $ARCH  ################"
  env MODEL=$ARCH LAYERS=$([ "$ARCH" = transformer ] && echo ${TF_LAYERS:-4} || echo 1) HEADS=${HEADS:-8} \
      DATA_MODE=real DATA_DIR="$P_DD" DOMAINS=eng DEVICE=${DEVICE:-cuda} DISK_STREAM=1 \
      CORPUS_CAP=100000000000 STREAM_LEN=$P_SL EPOCHS=$P_EP D_MODEL=${D_MODEL:-768} \
      WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 \
      SIG_WIN=${SIG_WIN:-614} \
      ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MEM_CAP=200000 MEM_QUOTA=${MEM_QUOTA:-3125} \
      CKPT_EVERY=10000 RATE_EVERY=2000 PROFILE=0 \
      SAVE_CKPT="$OUT/pilot_$ARCH" python3 self_organize.py 2>&1 | tee "$OUT/pilot_$ARCH.log"
  done
  echo
  echo "=== SIDE BY SIDE (the only number that compares them directly) ==="
  for ARCH in ${PILOT_ARCH:-gru transformer}; do
    printf "  %-12s %s\n" "$ARCH" "$(grep -a -oE 'order-1 [0-9.]+ \| THIS MODEL [0-9.]+' "$OUT/pilot_$ARCH.log" 2>/dev/null | head -1)"
  done
  echo
  echo "READ IN THIS ORDER -- what the project is FOR, in order:"
  echo "  GENERATION   the samples. THE deliverable -- everything else is a proxy for these."
  echo "  ANCHORS      must beat order-1. If it does not, nothing below is worth reading."
  echo "  GENERATION   the samples you judge by eye. This is the real instrument at 2 domains."
  echo "  COHERENCE    [SELF-ASSEMBLED reference] on one corpus: floor is 1/n_domains. Weaker evidence -- read it"
  echo "               next to the samples, not instead of them."
  echo "  ACROSS THE RUN BOUNDARY  empty on a first run; it is the baseline the NEXT run compares against."
  echo "  EXPERTS      specialized or interchangeable, and how many nodes the router never calls on."
  echo "  (domain counts and clustering scores are DIAGNOSTICS -- they explain the above, they are not targets)"
  echo
  echo "then add an area and see what it costs:  bash longrun.sh pilot-add py bigcode/the-stack-dedup 0.03"
  ;;

pilot-add)
  NAME=${2:-}; DS=${3:-}; GB=${4:-0.03}; P_DD=${PILOT_DIR:-data_pilot}
  [ -n "$NAME" ] && [ -n "$DS" ] || { echo "usage: bash longrun.sh pilot-add <name> <hf-dataset> [gb]"; exit 1; }
  PA=${PILOT_ADD_ARCH:-gru}
  [ -f "$OUT/pilot_$PA/ckpt.pt" ] || { echo "!! no pilot checkpoint at $OUT/pilot_$PA/ckpt.pt -- run 'bash longrun.sh pilot' first (PILOT_ADD_ARCH=gru|transformer)"; exit 1; }
  if [ -z "$(ls "$P_DD/train/$NAME"/part*.txt 2>/dev/null)" ]; then
    python3 fetch_big.py --dataset "$DS" --domain "$NAME" --gb "$GB" --out "$P_DD" --resume || exit 1
  fi
  env DATA_MODE=real DATA_DIR="$P_DD" DOMAINS="eng,$NAME" DEVICE=${DEVICE:-cuda} DISK_STREAM=1 \
      CORPUS_CAP=100000000000 STREAM_LEN=${STREAM_LEN:-4000000} EPOCHS=${EPOCHS:-8} D_MODEL=${D_MODEL:-768} \
      WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 \
      SIG_WIN=${SIG_WIN:-614} \
      ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MEM_CAP=200000 MEM_QUOTA=${MEM_QUOTA:-3125} \
      CKPT_EVERY=10000 RATE_EVERY=2000 PROFILE=0 RESUME="$OUT/pilot_$PA" MODEL=$PA LAYERS=$([ "$PA" = transformer ] && echo ${TF_LAYERS:-4} || echo 1) \
      SAVE_CKPT="$OUT/pilot_${PA}_$NAME" python3 self_organize.py 2>&1 | tee "$OUT/pilot_$NAME.log"
  echo; echo ">> the number this run exists for is in ACROSS THE RUN BOUNDARY: what adding $NAME did to the English."
  ;;

add)
  # ADD A NEW AREA to the system that already learned English. This is the continual-learning claim, run as an
  # experiment rather than asserted: pull the new corpus, resume from the trained checkpoint with the new domain
  # appended to DOMAINS, and let the cross-boundary probe say what it cost the English.
  #   bash longrun.sh add py bigcode/the-stack-dedup 10
  # DOMAINS ORDER MATTERS ONLY IN THAT THE NEW NAME GOES LAST -- the probe is keyed by NAME, so the existing
  # domains keep their baselines wherever they end up, but appending keeps the phase schedule sensible.
  NAME=${2:-}; DS=${3:-}; GB=${4:-10}
  [ -n "$NAME" ] && [ -n "$DS" ] || { echo "usage: bash longrun.sh add <name> <hf-dataset> [gb]"; exit 1; }
  [ -f "$OUT/ck/ckpt.pt" ] || { echo "!! nothing to add to -- no checkpoint at $OUT/ck/ckpt.pt. Run the English run first."; exit 1; }
  if [ -z "$(ls "$DD/train/$NAME"/part*.txt 2>/dev/null)" ]; then
    python3 fetch_big.py --dataset "$DS" --domain "$NAME" --gb "$GB" --out "$DD" --resume || exit 1
  else
    echo "$DD/train/$NAME already has data -- skipping the pull"
  fi
  mkdir -p "$OUT"
  env DATA_MODE=real DATA_DIR="$DD" DOMAINS="eng,$NAME" DEVICE=cuda DISK_STREAM=1 \
      CORPUS_CAP=100000000000 STREAM_LEN=$SL EPOCHS=$EP D_MODEL=${D_MODEL:-768} WIN=256 BATCH_W=16 \
      VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 SIG_WIN=${SIG_WIN:-614} \
      ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MEM_CAP=200000 MEM_QUOTA=${MEM_QUOTA:-3125} \
      CKPT_EVERY=${CKPT_EVERY:-50000} RATE_EVERY=5000 PROFILE=0 RESUME="$OUT/ck" \
      SAVE_CKPT="$OUT/ck_$NAME" nohup python3 self_organize.py >> "$OUT/add_$NAME.log" 2>&1 &
  echo "pid $! -> $OUT/add_$NAME.log   (new checkpoint at $OUT/ck_$NAME, the English one is left intact)"
  echo "  read the ACROSS THE RUN BOUNDARY section: eng carries a baseline, $NAME will show as NEW."
  ;;

watch)
  [ -f "$OUT/run.log" ] || { echo "no $OUT/run.log yet"; exit 1; }
  echo "=== last progress"; grep -a -E "\[rate\]|\[epoch |\[PHASE |\[saved checkpoint" "$OUT/run.log" | tail -12
  echo; echo "=== anything wrong"; grep -a -E "!! |Traceback|Error" "$OUT/run.log" | tail -8
  echo; echo "=== live"; tail -3 "$OUT/run.log"
  ;;

*) echo "usage: bash longrun.sh [pilot|pilot-add <name> <ds> [gb]|fetch|run|resume|add <name> <ds> [gb]|watch]"; exit 1 ;;
esac
