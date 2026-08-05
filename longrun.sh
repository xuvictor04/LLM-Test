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

# === NEVER OVERWRITE ANYTHING UNDER runs/ ====================================================================
# Every subcommand here used to write $OUT/<name>.log and SAVE_CKPT=$OUT/<name> directly, so re-running a pilot
# silently destroyed the previous one -- including the checkpoint that `pilot-add` and the ACROSS THE RUN BOUNDARY
# section need as their baseline. Results are the expensive part of this project; they are now append-only.
# _reserve <path> echoes a path that does not exist yet, suffixing -2, -3, ... if it has to.
_reserve() {
  _rp="$1"
  if [ ! -e "$_rp" ]; then echo "$_rp"; return; fi
  _rn=2
  while [ -e "${_rp%.log}-$_rn.log" ] || [ -e "$_rp-$_rn" ]; do _rn=$((_rn+1)); done
  case "$_rp" in
    *.log) echo "${_rp%.log}-$_rn.log" ;;
    *)     echo "$_rp-$_rn" ;;
  esac
}
# _done <log> -- true if that log reached the end of a run (the final line every complete report prints).
_done() { [ -f "$1" ] && grep -aq "SIG_MODE=learned -- learned = the unfrozen product path" "$1"; }

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
  # GRU ONLY by default. The architecture question is ANSWERED: GRU beat the transformer on both pilots,
  # 2.064/2.200 vs 2.130/2.184 bits/byte and coherence 0.17 vs 0.02. Running both again costs an hour and
  # buys nothing. PILOT_ARCH="gru transformer" to re-open it.
  for ARCH in ${PILOT_ARCH:-gru}; do
  echo; echo "################  base LM: $ARCH  ################"
  env MODEL=$ARCH LAYERS=$([ "$ARCH" = transformer ] && echo ${TF_LAYERS:-4} || echo 1) HEADS=${HEADS:-8} \
      DATA_MODE=real DATA_DIR="$P_DD" DOMAINS=eng DEVICE=${DEVICE:-cuda} DISK_STREAM=1 \
      CORPUS_CAP=100000000000 STREAM_LEN=$P_SL EPOCHS=$P_EP D_MODEL=${D_MODEL:-768} \
      WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 \
      SIG_WIN=${SIG_WIN:-614} \
      ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MEM_CAP=200000 MEM_QUOTA=${MEM_QUOTA:-3125} \
      CKPT_EVERY=10000 RATE_EVERY=2000 PROFILE=0 \
      SAVE_CKPT="$(_reserve "$OUT/pilot_$ARCH")" PROBE_WAIT=${PROBE_WAIT:-12} \
      python3 self_organize.py 2>&1 | tee "$(_reserve "$OUT/pilot_$ARCH.log")"
  done
  echo
  echo "=== SIDE BY SIDE (the only number that compares them directly) ==="
  # GRU ONLY by default. The architecture question is ANSWERED: GRU beat the transformer on both pilots,
  # 2.064/2.200 vs 2.130/2.184 bits/byte and coherence 0.17 vs 0.02. Running both again costs an hour and
  # buys nothing. PILOT_ARCH="gru transformer" to re-open it.
  for ARCH in ${PILOT_ARCH:-gru}; do
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

grid)
  # === UNATTENDED ARM GRID =====================================================================================
  # Built for `sleep 2h && git pull && bash longrun.sh grid`, so: nothing interactive, one arm at a time, an arm
  # that dies does not take the grid with it, and RE-RUNNING IT RESUMES rather than repeats or overwrites. Every
  # completed arm is skipped on a second invocation, so the same command can be fired repeatedly and safely.
  #
  # Nothing under runs/ is ever overwritten. Each arm writes $GRID/<arm>.log; if a log exists and is COMPLETE the
  # arm is skipped, and if it exists but is partial (a kill, an OOM) it is MOVED ASIDE to <arm>.log.partial-N
  # before the retry. Checkpoints go to $GRID/<arm>/ and are reserved the same way.
  GRID=${GRID_DIR:-runs/grid}
  P_DD=${PILOT_DIR:-data_pilot}
  mkdir -p "$GRID"
  # THE ARMS. name:overrides. Ordered so that stopping the grid early still leaves a readable comparison: the two
  # that answer the current question come first, and each later arm is a control for a different explanation.
  #   weights  -- routing decided ENTIRELY by predicted weights (this branch's premise; measured at 2% before)
  #   base     -- the control at HEAD. Answers on its own whether the growth-ramp latch fixed the divergence,
  #               since every pilot so far bottomed early and rose for the rest of the run.
  #   keynorm  -- region AND weight prediction on ONE scale (66/34 rather than 98/2). The middle position.
  #   society  -- SOCIETY=1 with every fix. The path control: how much of any change is chaining vs the fixes.
  #   curric   -- staged depth, which has never actually run (it sat behind a cadence that never fired).
  # ORDERED BY INFORMATION VALUE, so stopping the grid at any point leaves the most informative set that fits.
  # Roughly 20 min per arm on a GH200; the whole list is ~6 h.
  #
  # -- the control, first, because every other arm is read against it -----------------------------------------
  #   base       defaults at HEAD. On its own it answers whether the growth-ramp latch fixed the divergence that
  #              every pilot so far has shown (bottom at ~step 5900, then +1.1 to +1.6 for the rest of the run).
  #   weights    ROUTE_REGION_W=0 -- routing decided ENTIRELY by predicted weights. Best selection result so far
  #              (specialization 0.094 vs 0.000, top expert 44.5% vs 79.5%) but measured on a diverging run.
  #
  # -- WHY DOES IT DIVERGE? each arm removes one suspect ------------------------------------------------------
  #   nofabric   FABRIC=0. THE partition: if the bare GRU diverges too, none of the expert machinery is the
  #              cause and every routing arm here is measuring something downstream of the real problem.
  #   balance    BAL_WARM huge -- load-balance pressure never decays. It currently decays to 0 by step 4000 and
  #              the loss turns at ~5900, which is the closest coincidence in the whole timeline.
  #   frozvocab  TOK_ONLINE=0. Per-TOKEN loss rises mechanically as minted tokens get longer, so part of the
  #              "divergence" may be a units artifact. Freezing the vocabulary makes the curve unit-stable.
  #   smallpop   FAB_NMAX=256. Does the turn track reaching the CAP rather than a step number?
  #   nomem      MEM_PER_EXPERT=0. The store fills to MEM_CAP early; this removes the partitioned-write path.
  #
  # -- the chain makes ONE decision and then follows a rail (H(hop1|hop0) = 0.018 bits, measured) -------------
  #   softroute  ROUTE_T=0.3. A sharp transition iterated over hops is a power iteration and converges on one
  #              successor; softening it is the most direct counter to the rail.
  #   curric     staged depth -- never actually ran before (it sat behind a cadence that never fired).
  #   stateq     the transition query sees the CURRENT state, not just the input signature + who holds it.
  #   chainsup   per-hop deep supervision. Measured WORSE on a 24-expert toy, which is not this system.
  #
  # -- specialization and scale -------------------------------------------------------------------------------
  #   keynorm    both routing terms on ONE scale (66/34 rather than 98/2). The middle position.
  #   divw       DIV_W=0.05 -- the only term that rewards experts for DIFFERING, never once switched on.
  #   society    SOCIETY=1 path control, with every fix, to separate chaining from the fixes.
  #   explore    FAB_EXPLORE=0.40. Exploration is the mechanism meant to break concentration and it has only
  #              ever run at 0.15; if the rail and the top-expert share are breakable by off-policy traffic,
  #              this is the arm that shows it.
  #
  # -- combinations, blind but cheap --------------------------------------------------------------------------
  #   wt_bal     weights + balance: the two most likely individual wins together.
  #   wt_div     weights + DIV_W: best routing plus the only distinctness pressure.
  #   kitchen    weights + balance + DIV_W + softroute.
  # ROUND 2. The first grid answered its question: chaining loses to FABRIC=0 and society wins outright. These
  # arms test the hybrid that the two paths' difference implies, and separate the two changes that regressed base.
  #   vote      CHAIN_VOTE=1 -- multi-hop, but experts blended at the PREDICTION level at every hop. The society's
  #             combination rule with chaining's depth, and the only configuration in which HALT has a job:
  #             the mass that halts at hop t SELECTS hop t's answer. Measured 0.0000 -> 0.2213 immediately.
  #   vote_w    the same, routing on predicted weights alone (best specialization of any chaining arm).
  #   vote_soc  the same at depth 1 -- which IS the society path, and so isolates depth from the blend rule.
  #   noban     CHAIN_BAN=0 and nolatch FAB_RAMP_LATCH=0: the two changes that landed between pilot 6 (+1.438)
  #             and grid base (+2.287) and were never separated.
  GRID_ARMS_DEFAULT="socloop socloop_w vote vote_w society base noban nolatch vote_soc weights nofabric \
                     balance keynorm divw smallpop curric wt_bal chainsup explore kitchen"
  _flags_for() {
    case "$1" in
      base)      echo "" ;;
      vote)      echo "CHAIN_VOTE=1" ;;
      socloop)   echo "CHAIN_ROUTE=soc CHAIN_VOTE=1" ;;
      socloop_w) echo "CHAIN_ROUTE=soc CHAIN_VOTE=1 ROUTE_REGION_W=0 FAB_KEY_NORM=1" ;;
      vote_w)    echo "CHAIN_VOTE=1 ROUTE_REGION_W=0 FAB_KEY_NORM=1" ;;
      vote_soc)  echo "CHAIN_VOTE=1 FAB_STEPS=1" ;;
      noban)     echo "CHAIN_BAN=0" ;;
      nolatch)   echo "FAB_RAMP_LATCH=0" ;;
      nogrow)    echo "FAB_GROW=0 FAB_N0=1024" ;;
      nogrow_s)  echo "SOCIETY=1 FAB_GROW=0 FAB_N0=1024" ;;
      weights)   echo "ROUTE_REGION_W=0 FAB_KEY_NORM=1" ;;
      nofabric)  echo "FABRIC=0" ;;
      balance)   echo "BAL_WARM=100000000" ;;
      frozvocab) echo "TOK_ONLINE=0" ;;
      softroute) echo "ROUTE_T=0.3" ;;
      keynorm)   echo "FAB_KEY_NORM=1" ;;
      divw)      echo "DIV_W=0.05" ;;
      smallpop)  echo "FAB_NMAX=256" ;;
      curric)    echo "CHAIN_CURRIC=1" ;;
      society)   echo "SOCIETY=1" ;;
      stateq)    echo "CHAIN_STATE_Q=1" ;;
      chainsup)  echo "CHAIN_SUP=0.3" ;;
      nomem)     echo "MEM_PER_EXPERT=0" ;;
      explore)   echo "FAB_EXPLORE=0.40" ;;
      wt_bal)    echo "ROUTE_REGION_W=0 FAB_KEY_NORM=1 BAL_WARM=100000000" ;;
      wt_div)    echo "ROUTE_REGION_W=0 FAB_KEY_NORM=1 DIV_W=0.05" ;;
      kitchen)   echo "ROUTE_REGION_W=0 FAB_KEY_NORM=1 BAL_WARM=100000000 DIV_W=0.05 ROUTE_T=0.3" ;;
      *)         echo "" ;;
    esac
  }
  if [ -z "$(ls "$P_DD/train/eng"/part*.txt 2>/dev/null)" ]; then
    python3 -c "import datasets" 2>/dev/null || { echo "need: pip install datasets (throwaway venv -- see preflight.sh)"; exit 1; }
    python3 fetch_big.py --dataset ${PILOT_SRC:-fineweb-edu} --domain eng --gb ${PILOT_GB:-0.06} --out "$P_DD" --resume || exit 1
  fi
  G_SL=${STREAM_LEN:-4000000}; G_EP=${EPOCHS:-8}
  ARMS=${GRID_ARMS:-$GRID_ARMS_DEFAULT}
  echo "grid -> $GRID | arms: $ARMS | $((G_SL/1000)) kB/epoch x $G_EP epochs each"
  echo "  (re-running this command SKIPS completed arms and never overwrites a finished log)"
  trap 'echo; echo "grid interrupted -- completed arms are kept; re-run the same command to continue"; exit 130' INT TERM
  for ARM in $ARMS; do
    LOG="$GRID/$ARM.log"
    if _done "$LOG"; then echo "== $ARM: already complete, skipping"; continue; fi
    if [ -f "$LOG" ]; then
      _pn=1; while [ -e "$LOG.partial-$_pn" ]; do _pn=$((_pn+1)); done
      mv "$LOG" "$LOG.partial-$_pn"
      echo "== $ARM: previous attempt was incomplete -> kept as $LOG.partial-$_pn"
    fi
    FLAGS="$(_flags_for "$ARM")"
    echo; echo "################  arm: $ARM  ${FLAGS:-(defaults)}  ################"
    _t_start=$(date +%s)
    # set +e around the arm: one crash must not end the grid. SAVE_CKPT is reserved, so a retry cannot stomp a
    # checkpoint an earlier attempt left behind.
    set +e
    env $FLAGS \
        MODEL=gru LAYERS=1 HEADS=${HEADS:-8} \
        DATA_MODE=real DATA_DIR="$P_DD" DOMAINS=eng DEVICE=${DEVICE:-cuda} DISK_STREAM=1 \
        CORPUS_CAP=100000000000 STREAM_LEN=$G_SL EPOCHS=$G_EP D_MODEL=${D_MODEL:-768} \
        WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 \
        SIG_WIN=${SIG_WIN:-614} ENC_WARMUP=2000 ENC_WARMUP_MIN=500 \
        MEM_CAP=200000 MEM_QUOTA=${MEM_QUOTA:-3125} \
        CKPT_EVERY=10000 RATE_EVERY=2000 PROFILE=0 PROBE_WAIT=0 \
        SAVE_CKPT="$([ "${GRID_CKPT:-1}" = 1 ] && _reserve "$GRID/$ARM" || echo 0)" \
        python3 self_organize.py > "$LOG" 2>&1
    _rc=$?
    set -e 2>/dev/null || true
    _t_end=$(date +%s)
    printf "%s\trc=%s\t%ss\n" "$ARM" "$_rc" "$((_t_end-_t_start))" >> "$GRID/_status.tsv"
    if [ "$_rc" = 0 ] && _done "$LOG"; then echo "== $ARM: OK ($((_t_end-_t_start))s)"
    else echo "== $ARM: FAILED rc=$_rc after $((_t_end-_t_start))s -- see $LOG (grid continues)"; fi
  done
  echo; echo "=== GRID SUMMARY ==="
  printf "  %-9s %-7s %-13s %-11s %-9s %-22s %s\n" arm held-out vs-order-1 curve experts top-share routing-mix
  for ARM in $ARMS; do
    L="$GRID/$ARM.log"; [ -f "$L" ] || continue
    _ho=$(grep -a -oE "held-out [0-9.]+" "$L" | head -1 | awk '{print $2}')
    _o1=$(grep -a -oE "beats order-1 by \+[0-9.]+" "$L" | head -1 | awk '{print $NF}')
    _cv=$(grep -a -oE "since the minimum [-+][0-9.]+" "$L" | head -1 | awk '{print $NF}')
    _ex=$(grep -a -oE "[0-9]+ distinct experts won" "$L" | head -1 | awk '{print $1}')
    _tp=$(grep -a -oE "top expert took [0-9.]+%" "$L" | head -1 | awk '{print $NF}')
    _mx=$(grep -a -oE "spread [0-9.]+ \([0-9]+%\) vs WEIGHT-PREDICTION term spread [0-9.]+ \([0-9]+%\)" "$L" | head -1 | sed -E 's/spread [0-9.]+ \(([0-9]+%)\).*\(([0-9]+%)\)/region \1 weight \2/')
    printf "  %-9s %-7s %-13s %-11s %-9s %-22s %s\n" "$ARM" "${_ho:--}" "${_o1:--}" "${_cv:--}" "${_ex:--}" "${_tp:--}" "${_mx:--}"
  done
  echo
  echo "  curve = change SINCE THE MINIMUM. Positive means the run got worse after its best point; every pilot so"
  echo "  far has been +1.1 to +1.4, and whether the growth-ramp latch fixed that is what 'base' answers."
  echo "  Also worth grepping in each log: POPULATION CHURN, CHAIN ORDER, ROUTING MIX, GRADIENT REACH."
  echo
  echo "  logs: $GRID/*.log   status: $GRID/_status.tsv"
  ;;

seeds)
  # === THE SAME ARM ACROSS SEEDS =============================================================================
  # Every architecture claim in this project was made from ONE run per arm. Paired pilots at SEED=0 and SEED=1
  # measured the seed spread for the first time: 0.060 b/B for the society arm and 0.174 for the chained society,
  # against a 0.06 b/B band separating the four best architectures. The spread is larger than the effect, so a
  # single run cannot rank two arms -- and two claims made off single runs (specialisation 0.132, a flat curve)
  # did not survive a second seed.
  # Runs are deterministic given (config, commit, SEED), so this is pure seed variance, not run-to-run jitter.
  #   bash longrun.sh seeds 3 SOCIETY=1        # 3 seeds of one arm
  #   SEEDS="0 1 2 3" bash longrun.sh seeds -- CHAIN_ROUTE=soc
  N=${2:-3}
  case "$N" in ''|*[!0-9]*) N=3;; esac
  shift $([ "${2:-}" = "$N" ] && echo 2 || echo 1) 2>/dev/null || true
  [ "${1:-}" = "--" ] && shift
  ARMFLAGS="$*"
  SEEDLIST=${SEEDS:-$(seq 0 $((N-1)))}
  SD=${SEED_DIR:-runs/seeds}
  mkdir -p "$SD"
  TAG=$(echo "${ARMFLAGS:-default}" | tr ' =' '__' | cut -c1-40)
  echo "seeds: arm [${ARMFLAGS:-defaults}] over seeds [$(echo $SEEDLIST | tr '\n' ' ')] -> $SD"
  for SEED in $SEEDLIST; do
    LOG="$SD/${TAG}_seed$SEED.log"
    if _done "$LOG"; then echo "== seed $SEED: already complete, skipping"; continue; fi
    [ -f "$LOG" ] && { _pn=1; while [ -e "$LOG.partial-$_pn" ]; do _pn=$((_pn+1)); done; mv "$LOG" "$LOG.partial-$_pn"; }
    echo; echo "################  seed $SEED  ${ARMFLAGS:-(defaults)}  ################"
    set +e
    env $ARMFLAGS SEED=$SEED \
        MODEL=gru LAYERS=1 DATA_MODE=real DATA_DIR="${PILOT_DIR:-data_pilot}" DOMAINS=eng \
        DEVICE=${DEVICE:-cuda} DISK_STREAM=1 CORPUS_CAP=100000000000 \
        STREAM_LEN=${STREAM_LEN:-4000000} EPOCHS=${EPOCHS:-8} D_MODEL=${D_MODEL:-768} \
        WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 \
        SIG_WIN=${SIG_WIN:-614} ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MEM_CAP=200000 \
        MEM_QUOTA=${MEM_QUOTA:-3125} CKPT_EVERY=10000 RATE_EVERY=2000 PROFILE=0 PROBE_WAIT=0 \
        SAVE_CKPT=0 python3 self_organize.py > "$LOG" 2>&1
    echo "== seed $SEED: rc=$?"
    set -e 2>/dev/null || true
  done
  echo; echo "=== SEEDS SUMMARY: [${ARMFLAGS:-defaults}] ==="
  python3 - "$SD" "$TAG" <<'PY'
import sys, glob, re, statistics as st
sd, tag = sys.argv[1], sys.argv[2]
rows = []
for f in sorted(glob.glob(f"{sd}/{tag}_seed*.log")):
    b = open(f, errors="ignore").read()
    def g(p):
        m = re.search(p, b)
        return float(m.group(1)) if m else None
    rows.append((re.search(r"seed(\d+)", f).group(1), g(r"held-out ([0-9.]+)"),
                 g(r"beats order-1 by \+([0-9.]+)"), g(r"SPECIALIZATION[^0-9]*([0-9.]+)")))
print(f"  {'seed':>4}  {'held-out':>9}  {'vs order-1':>11}  {'spec':>7}")
for s, h, o, sp in rows:
    print(f"  {s:>4}  {h if h else '-':>9}  {o if o else '-':>11}  {sp if sp is not None else '-':>7}")
hs = [h for _, h, _, _ in rows if h]
if len(hs) > 1:
    print(f"\n  held-out: mean {st.mean(hs):.3f}  spread {max(hs)-min(hs):.3f}  "
          f"sd {st.pstdev(hs):.3f}  over {len(hs)} seeds")
    print(f"  >> an architecture difference SMALLER than the spread is not a result. The four best arms in this")
    print(f"     project sit inside 0.06 b/B of each other; measured seed spread has reached 0.174.")
PY
  ;;

watch)
  [ -f "$OUT/run.log" ] || { echo "no $OUT/run.log yet"; exit 1; }
  echo "=== last progress"; grep -a -E "\[rate\]|\[epoch |\[PHASE |\[saved checkpoint" "$OUT/run.log" | tail -12
  echo; echo "=== anything wrong"; grep -a -E "!! |Traceback|Error" "$OUT/run.log" | tail -8
  echo; echo "=== live"; tail -3 "$OUT/run.log"
  ;;

*) echo "usage: bash longrun.sh [pilot|grid|seeds <n> [FLAGS]|pilot-add <name> <ds> [gb]|fetch|run|resume|add <name> <ds> [gb]|watch]"; exit 1 ;;
esac
