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
#   bash longrun.sh smoke     does every pilot arm still REACH ITS REPORT? minutes, run before any grid
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
# _cfgsig -- the RUN-SHAPING settings, as one line. A completed log is only interchangeable with a new run if
# these match. TAG is derived from ARMFLAGS alone, so it is blind to every one of these, and the resume-skip below
# compares only "did a log with this name finish". That combination silently answers the wrong question:
#   EPOCHS=8  bash longrun.sh seeds 3      # runs, writes default_seed{0,1,2}.log
#   EPOCHS=18 bash longrun.sh seeds 3      # SKIPS ALL THREE and re-prints the 8-epoch numbers as the 18-epoch result
# Same for STREAM_LEN, D_MODEL, SIG_WIN, MEM_QUOTA, DEVICE, PILOT_DIR and the commit -- `seeds` reads all of them
# from the environment and none of them reach the log's name. The SEEDS SUMMARY then globs those stale logs and
# prints their held-out numbers under the new banner, so the wrong answer is not merely kept, it is REPORTED.
# EVERY KNOB THE ENVIRONMENT SETS, not a hand-picked list. This used to name seven variables plus ARMFLAGS, so
# any knob passed through the environment rather than as an arm flag was invisible to it -- and the log NAME is
# derived from ARMFLAGS too, so two arms differing only by an exported knob got the same filename AND the same
# signature, and the second run was skipped as "already complete". That is exactly what happened to the
# FAB_LR_CYCLE bisect: two arms, one log, one result, silently.
# The knob list comes from _SPEC in self_organize.py, so adding a knob extends this automatically -- the same
# property the config audit gets by deriving its families from the registry instead of restating them. Read by
# sed rather than by importing, because importing self_organize.py runs a great deal of module-level setup.
_knobs() {
  sed -n 's/^    "\([A-Z][A-Z0-9_]*\)": (.*/\1/p' "$(dirname "$0")/self_organize.py" 2>/dev/null | sort -u
}
# THE CORPUS IS PART OF THE CONFIGURATION, and a PATH is not the corpus. `data=data_pilot` was all this
# recorded, so a box that fetched a fresh corpus into the same directory produced an identical signature for
# materially different runs -- which is exactly what happened: one box's data_pilot has order-1 3.742 and
# another's, freshly pulled into the same path, has 3.440. Numbers from the two are not comparable, and nothing
# said so. Fingerprint = total bytes + file count + a hash of the first megabyte, which is cheap and catches a
# re-fetch, a truncation, or a different shard set.
_corpsig() {
  _cd="${PILOT_DIR:-data_pilot}/train"
  [ -d "$_cd" ] || { echo "none"; return; }
  _cb=$(find "$_cd" -name '*.txt' -type f -printf '%s\n' 2>/dev/null | awk '{t+=$1} END{print t+0}')
  _cn=$(find "$_cd" -name '*.txt' -type f 2>/dev/null | wc -l | tr -d ' ')
  _ch=$(find "$_cd" -name '*.txt' -type f 2>/dev/null | sort | head -1 | xargs -r head -c 1048576 2>/dev/null \
        | sha1sum 2>/dev/null | cut -c1-12)
  echo "b${_cb}n${_cn}h${_ch:-?}"
}
_cfgsig() {
  printf 'commit=%s data=%s corpus=%s flags=%s' \
    "$(git rev-parse --short=10 HEAD 2>/dev/null || echo '?')" "${PILOT_DIR:-data_pilot}" \
    "$(_corpsig)" "${ARMFLAGS:-}"
  for _k in $(_knobs); do
    eval "_v=\${$_k+set}"
    [ -n "${_v:-}" ] && { eval "_vv=\$$_k"; printf ' %s=%s' "$_k" "$_vv"; }
  done
  printf ' dev=%s\n' "${DEVICE:-cuda}"
}
# _reusable <log> -- a completed log MAY be reused only if it was produced by this same configuration. Anything
# else stops the run with a message naming the difference, rather than being silently adopted or silently
# overwritten: both of those turn a config change into a result nobody can trace.
_reusable() {
  _rl="$1"; _rc_file="$1.cfg"
  if [ ! -f "$_rc_file" ]; then
    echo "!! $_rl is complete but has no .cfg beside it, so the configuration that produced it is unknown."
    echo "   It predates this check. Move it aside or point SEED_DIR/GRID_DIR/REPEAT_DIR at a fresh directory."
    return 1
  fi
  if [ "$(cat "$_rc_file")" = "$(_cfgsig)" ]; then return 0; fi
  echo "!! $_rl is complete but was produced by a DIFFERENT configuration:"
  echo "     stored:  $(cat "$_rc_file")"
  echo "     current: $(_cfgsig)"
  echo "   Reusing it would report the stored run's numbers under this run's banner. Use a fresh output"
  echo "   directory, or delete that log if you meant to replace it."
  return 1
}
# _stopped -- a sweep asked to stop cleanly. `touch runs/<dir>/STOP` (or STOP_FILE=<path>) and the loop finishes
# the run it is on, then stops before starting the next. No signal, no Ctrl-C, no partial log: the run in flight
# writes its report and its checkpoint exactly as it would have.
#   Ctrl-C kills the CURRENT run too, losing however many hours it is into it, and killing the shell leaves the
# python orphaned. Neither is what "stop after this one" means, and there was no third option.
_stopped() {
  _sf="${STOP_FILE:-$1/STOP}"
  [ -e "$_sf" ] || return 1
  echo; echo "== stop requested ($_sf) -- finishing here. Remove that file to run the rest."
  return 0
}
# _done <log> -- true if that log reached the end of a run (the final line every complete report prints).
_done() { [ -f "$1" ] && grep -aq "SIG_MODE=learned -- learned = the unfrozen product path" "$1"; }

# _pilot_corpus [dir] -- guarantee <dir>/train/eng has text, pulling it if it does not.
# EVERY pilot-scale subcommand needs this and it used to be copy-pasted into `pilot` and `grid` only. `seeds`
# and `repeat` were added later without it, so they set up a whole run, printed their banner, and then died
# inside the model on "no corpus files in data_pilot/train/eng/" -- a setup failure reported as a config error,
# after the harness had already claimed it was starting. One definition, called by all four.
_pilot_corpus() {
  _pc="${1:-data_pilot}"
  [ -n "$(ls "$_pc/train/eng"/part*.txt 2>/dev/null)" ] && return 0
  echo "[corpus] $_pc/train/eng is empty -> pulling ${PILOT_GB:-0.06} GB of ${PILOT_SRC:-fineweb-edu} (resumable)"
  python3 -c "import datasets" 2>/dev/null || {
    echo "!! need: pip install datasets   (use a THROWAWAY venv -- upgrading numpy under an NGC torch breaks"
    echo "   its ABI; see preflight.sh). Or pull it yourself, then re-run this command:"
    echo "     python3 fetch_big.py --dataset ${PILOT_SRC:-fineweb-edu} --domain eng --gb ${PILOT_GB:-0.06} --out $_pc --resume"
    exit 1; }
  python3 fetch_big.py --dataset ${PILOT_SRC:-fineweb-edu} --domain eng --gb ${PILOT_GB:-0.06} --out "$_pc" --resume || exit 1
  # A pull that "succeeds" but writes nothing is the failure that wasted the setup in the first place.
  [ -n "$(ls "$_pc/train/eng"/part*.txt 2>/dev/null)" ] || {
    echo "!! fetch_big.py exited 0 but $_pc/train/eng is still empty -- nothing to train on"; exit 1; }
  echo "[corpus] ready: $(du -sh "$_pc/train/eng" 2>/dev/null | cut -f1) in $_pc/train/eng"
}

# === WHAT EACH ARM IS, IN ONE PLACE ==========================================================================
# Defined at TOP LEVEL, not inside `grid)`. A function defined in one case branch does not exist in another,
# so `smoke` calling _flags_for while it lived under grid) would have run every arm with an EMPTY flag set --
# seven identical runs reported as seven passing arms. Verified: `case smoke in grid) f(){...};; smoke) type f`
# reports UNDEFINED. Both grid and smoke resolve arms through this, so they cannot describe different runs.
_flags_for() {
  case "$1" in
    base)      echo "" ;;
    # RETOK OFF, ON A GROWING VOCABULARY -- not the same experiment as frozen_nr. There the vocabulary was
    # fixed, so re-segmentation was a provable no-op and turning it off cost nothing. Here minting runs the
    # whole way, so the question is real: does re-segmenting MID-EPOCH earn its side effects?
    #   RETOK_EVERY=0 does NOT stop re-segmentation. _resample() rebuilds the stream at every epoch boundary
    # and calls _retok itself, firing the same lookahead flush and fabric-growth blackout. So this arm moves
    # re-segmentation from every 3000 steps to once per ~6000-step epoch; newly minted tokens still reach the
    # stream, just up to one epoch later than they would have.
    base_nr)   echo "RETOK_EVERY=0" ;;
    vote)      echo "CHAIN_VOTE=1" ;;
    socloop)   echo "CHAIN_ROUTE=soc CHAIN_VOTE=1" ;;
    socloop_w) echo "CHAIN_ROUTE=soc CHAIN_VOTE=1 ROUTE_REGION_W=0 FAB_KEY_NORM=1" ;;
    vote_w)    echo "CHAIN_VOTE=1 ROUTE_REGION_W=0 FAB_KEY_NORM=1" ;;
    vote_soc)  echo "CHAIN_VOTE=1 FAB_STEPS=1" ;;
    noban)     echo "CHAIN_BAN=0" ;;
    nolatch)   echo "FAB_RAMP_LATCH=0" ;;
    bytes)     echo "TOKENIZER=0" ;;
    # UNCAPPED VOCABULARY. VMAX is the model's vocab DIMENSION and the tokenizer's ceiling; nothing has run
    # above 2048. Reachable as an arm flag only since the precedence fix -- before it, the hardcoded VMAX=2048
    # below silently won and the log was named after a value that never took effect.
    #
    # RAISING VMAX ALONE DOES NOT RAISE THE VOCABULARY: minting is rate-limited, not threshold-limited. One
    # grow event every GROW_EVERY=100 steps, GROW_BURST=12 per event, ~5.7k steps/epoch = ~540 tokens per
    # epoch, so 8192 from a 512 seed needs ~14 epochs. Under EPOCHS=8, vmax8k reached only 4823.
    #
    # FOUR RUNS, AS A 2x2 (held-out bits/byte, and the dead fraction from the [vocab] line):
    #                    EPOCHS=8              EPOCHS=18
    #     VMAX=4096    2.140  ( 0% dead)     3.250  ( 0% dead)      +1.110 for the extra 10 epochs
    #     VMAX=8192    3.561  (41% dead)     4.383  ( 0% dead)      +0.822
    #                 +1.421 for 2x VMAX    +1.133
    #
    # DEAD ROWS ARE NOT WHAT DRIVES THIS, and the hypothesis that they were is falsified here rather than
    # quietly dropped. vmax8k@18ep filled its vocabulary COMPLETELY -- 8192/8192, 0% never minted, 1.3%
    # ordinary turnover -- and is the WORST of the four: 4.383 b/B against a uniform anchor of 3.305, i.e.
    # about 4 bits/token WORSE than assigning equal probability to every token. 19% real words. It is the
    # only run of any arm with a POSITIVE train/held-out gap (+0.267; every other run underfits), and the
    # only one whose held-out curve is still RISING at the end (+0.194 b/B per 10k steps through the second
    # half). Its loss bottomed at step 3935 and rose for the remaining 82656 steps. The dead-row instrument
    # earned its place by ruling itself out; do not read the [vocab] line as an explanation of a bad number.
    #
    # TWO CELLS ARE UNCONTAMINATED (both vocabularies completely filled):
    #     vmax4k@8  vs vmax4k@18    +1.110    differ in EPOCHS -- and therefore in the LR schedule
    #     vmax4k@18 vs vmax8k@18    +1.133    differ in VMAX ONLY
    # The second is the clean one: at 18 epochs, doubling a FULL vocabulary from 4096 to 8192 costs +1.133
    # b/B with no dead rows on either side. The first is confounded until LR_EPOCHS pins the schedule --
    # EPOCHS moved the LR 11x between these two runs (see the LR_EPOCHS block in self_organize.py).
    #
    # SO THE NEXT GRID FIXES THE SCHEDULE AND VARIES ONE THING AT A TIME:
    #     GRID_CKPT=0 GRID_DIR=runs/vmax_lr EPOCHS=18 LR_EPOCHS=8 bash longrun.sh grid "vmax4k vmax8k"
    # vmax4k@18/LR8 against vmax4k@8 (2.140) isolates run length at a fixed schedule; vmax4k@18/LR8 against
    # vmax8k@18/LR8 isolates VMAX at fixed length AND fixed schedule.
    #
    # These arms carry NO growth and NO schedule knobs -- pass EPOCHS/LR_EPOCHS on the command line, so the
    # arm name never implies a schedule it does not set. self_organize.py predicts a minting shortfall in a
    # [config] COUPLING line BEFORE training starts; its estimate is measured at the seed vocabulary and runs
    # ~25% optimistic on this data, so treat it as a floor. Read the [vocab] line before the held-out number:
    # its first gap (width vs minted) can invalidate a comparison, the second (minted vs used) is ordinary
    # turnover and ran 1-2% on every filled run here.
    # Filling 8192 from a 512 seed needs ~7680 mints, ~14 epochs at the measured ~540/epoch, so at the grid's
    # default EPOCHS=8 this arm ran 4823/8192 = 41% dead and scored 3.561. Arm flags come LAST in the env
    # line, so this EPOCHS wins over the grid's. EPOCHS is the right lever, not GROW_BURST (see above).
    vmax8k)    echo "VMAX=8192 EPOCHS=18" ;;
    vmax4k)    echo "VMAX=4096" ;;
    # --- THE PILOT BUNDLE. Every arm here is read against `base`, and the three tokenizer arms are SEPARATED
    # on purpose: the last round ran TOK_MINT_UNTIL=1 and RETOK_EVERY=0 together, so when the result came back
    # 1.4 b/B worse there was no way to tell which did it. They are not the same idea. TOK_MINT_UNTIL stops
    # MINTING; RETOK_EVERY stops RE-SEGMENTING, and a re-segmentation that produces an identical stream is
    # still not a no-op -- it clears the lookahead queue and blacks out fabric growth for FAB_COOLDOWN steps.
    # VMAX MUST MATCH THE VOCABULARY THE ARM WILL ACTUALLY HAVE. Freezing minting does not narrow the
    # softmax: the grid hardcodes VMAX=2048, so TOK_MINT_UNTIL=1 alone leaves 1536 rows (75%) that are never
    # a target, sitting in the cross-entropy denominator at their initialisation for the whole run.
    # MEASURED, and not subtly: that arm scored 6.114 b/B with 4% real words, against 2.239 and 75% for base
    # on the same corpus and the same commit. It was not measuring a frozen tokenizer -- it was measuring the
    # dead-row failure at the largest dose recorded here. Pinning VMAX makes the arm mean what its name says.
    # BOTH ENDS PINNED, not just VMAX. Setting VMAX=512 alone assumes SEED_VOCAB is 512, which is only the
    # self_organize default -- the smoke harness sets 256, and the arm was straight back to 50% dead rows.
    # An arm has to state the whole configuration it tests, or a harness default silently redefines it.
    frozen)    echo "TOK_MINT_UNTIL=1 SEED_VOCAB=512 VMAX=512" ;;   # frozen at the seed; retok still fires
    # `frozen` freezes at SEED_VOCAB=512, so it conflates two different ideas: a FIXED vocabulary, and a TINY
    # one. At 512 the model has almost no whole-word units and must spell everything -- measured 3.07 tokens
    # per generated word against base's 2.52. These freeze at a seed the size base ENDS at, so the comparison
    # is fixed-vs-growing rather than small-vs-large.
    frozen2k)  echo "TOK_MINT_UNTIL=1 SEED_VOCAB=2048 VMAX=2048" ;;   # VMAX stated, not inherited
    frozen1k)  echo "TOK_MINT_UNTIL=1 SEED_VOCAB=1024 VMAX=1024" ;;   # was 50% dead without the VMAX
    frozen_nr) echo "TOK_MINT_UNTIL=1 SEED_VOCAB=512 VMAX=512 RETOK_EVERY=0" ;;   # ...and re-segmentation off
    # --- REGULARISATION. Every run so far reports UNDERFIT with a NEGATIVE gap (held-out scoring better than
    # train), so the expectation is that these cost rather than help. Worth measuring anyway: DROPOUT also
    # perturbs the hidden state the router reads, so it is an expert-dynamics lever, not only a generalisation one.
    drop)      echo "DROPOUT=0.1" ;;
    wdecay)    echo "WEIGHT_DECAY=0.01" ;;
    reg)       echo "DROPOUT=0.1 WEIGHT_DECAY=0.01" ;;
    mintinit)  echo "WARMSTART_MODE=last/first" ;;
    # --- THE MEANING GATE ON MINTING. Frequency alone cannot tell a UNIT ("th"+"e") from a pair that
    # straddles a boundary everything crosses ("e"+" "). H(next|a) can: low means `a` reliably predicts
    # what follows, so there is no boundary to glue across. Measured on a constructed case, H(next|"t")
    # = 1.32 bits against H(next|"e") = 2.05, which is the separation the threshold sits in.
    # These arms change WHICH TOKENS EXIST, so read them against `base` on vocabulary size and on the
    # [vocab] gate line (how many candidates were rejected), not on held-out alone.
    # The threshold is p(b|a), not an entropy. An absolute H(next|a) cut-off does not survive real text:
    # over 400 kB of English at the byte level H has median 3.48 bits and p90 4.39, and it is ANTI-correlated
    # with frequency -- a common left token is common because many things follow it -- so an entropy gate
    # rejects the useful merges first. p(b|a) asks the same question scale-free. Measured vocabulary reached,
    # 1024-cap, 400 kB, 4 passes:  pmin 0.10 -> 1010,  0.15 -> 623,  0.25 -> 353.
    # 0.10 IS NOW THE DEFAULT, so `pgate` would have been an alias for `base` -- an arm that changes nothing
    # while reading as though it tests something. The informative arm is the one that turns the gate OFF.
    nogate)    echo "TOK_MINT_PMIN=0" ;;                     # the pre-gate baseline; reproduces old vocabularies
    pgate_t)   echo "TOK_MINT_PMIN=0.15" ;;                  # tighter than default
    pgate_c)   echo "TOK_COMPOSE=1" ;;                       # default gate + the composed table it complements
    # --- PROBATION. Mint provisionally, judge once the token has been trained, un-merge on failure.
    prob_use)  echo "TOK_PROBATION=200" ;;                          # earn 200 appearances or be retired
    prob_emb)  echo "TOK_PROBATION=200 TOK_PROBATION_BY=embed TOK_COMPOSE=1" ;;   # ||delta||/||composite||
    # --- TOKEN PARAMETERISATION. TOK_COMPOSE is now ON by default, so every arm below states BOTH knobs
    # explicitly. pilot_gru_8 ran compose AND mintnovel together and cannot be attributed to either; these
    # four arms are the 2x2 that separates them, plus the anchor.
    nocompose) echo "TOK_COMPOSE=0 TOK_MINT_NOVEL=0" ;;    # neither -- the control the good runs were on
    compose)   echo "TOK_COMPOSE=1 TOK_MINT_NOVEL=0" ;;    # composed table alone
    mintnovel) echo "TOK_COMPOSE=0 TOK_MINT_NOVEL=0.5" ;;  # novelty-ranked minting alone
    composenov) echo "TOK_COMPOSE=1 TOK_MINT_NOVEL=0.5" ;; # both -- reproduces pilot_gru_8
    noanchor)  echo "TOK_COMPOSE=1 TOK_ANCHOR=0 TOK_MINT_NOVEL=0" ;;  # composer without the residual anchor
    # --- FABRIC SATURATION. pilot_gru_8 turned upward at ~step 36k, which is when the population reached
    # 100% of FAB_NMAX, the ramp latched off, and culling-under-capacity-pressure started.
    bigpop)    echo "FAB_NMAX=16384" ;;                    # does the turn track hitting the CAP?
    # Freezing at step 6000 buys only ~570-720 mints on top of the 512 seed, landing near 1100 of 2048 --
    # about 45% dead. VMAX=1024 binds before the freeze does, so width == vocabulary.
    freeze6k)  echo "TOK_MINT_UNTIL=6000 VMAX=1024" ;;
    freeze20k) echo "TOK_MINT_UNTIL=20000" ;;
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
    # === IDENTITY-SPACE COLLAPSE ===============================================================================
    # 31 of 40 archived runs print ">> COLLAPSED: every expert embeds to essentially the SAME identity", with a
    # nearest-neighbour distance median of 0.0009-0.0093 against a spawn bar of 0.0200. When the identity space is
    # collapsed the router has nothing to discriminate on, so specialization reads 0.000, FAB_SPAWN can never fire
    # (the query sits 0.0000 from its nearest identity), and HALT cannot win a softmax it enters far too small.
    # Every FAB_KEY_NORM=1 run is NON-collapsed (4/4, NN 0.0195-0.0722) and the three of those that report HALT
    # have HALT mass 0.917 against 0.0000 nearly everywhere else. FAB_EMB_VAR is the coefficient the report itself
    # names ("Raise FAB_EMB_VAR"); it has never been varied -- it is in notes/07_WIP.md's list of untested knobs.
    embvar4)   echo "FAB_EMB_VAR=4.0" ;;                   # is collapse fixable WITHOUT touching routing?
    embvar16)  echo "FAB_EMB_VAR=16.0" ;;
    keynorm_ev) echo "FAB_KEY_NORM=1 FAB_EMB_VAR=4.0" ;;   # both levers on the same space
    # === HALT ==================================================================================================
    # HALT's logit is a RAW DOT at FAB_KEY_NORM=0 and a cosine over route_t at 1 (see Fabric, the halt_key sites),
    # so key_norm is not merely a routing knob -- it sets whether HALT has any dynamic range at all.
    mintok)    echo "TOK_MINT_UNTIL=1" ;;                  # the minimum tokenizer: seed vocabulary, no live minting
    mintok_kn) echo "TOK_MINT_UNTIL=1 FAB_KEY_NORM=1" ;;
    # === DOMAINS OFF ===========================================================================================
    # SELF_ORG=0 is one bucket, no provenance, no management. The partition has been measured NOT to earn its keep
    # for prediction (own-domain 1.924 vs random-other 2.144, gap +0.220, against a shuffled null of +0.223), and
    # per-expert memory keys off the EXPERT rather than the domain, so it survives this.
    nodom)     echo "SELF_ORG=0" ;;
    # DOMAINS OFF *AND* MEMORY PER EXPERT -- drop the domain partition and put the expert partition in its place,
    # rather than dropping the partition altogether (which is what plain `nodom` does: MEM_OWNERS collapses to 1
    # and the store becomes one global pool). MEM_PER_EXPERT defaults OFF at HEAD and the reason is recorded at
    # its read site: global 200k slots contributed -0.097 b/B against 32 owners x 64 at -0.652, and the partition
    # is what made a FADED DOMAIN VANISH -- owners are experts folded mod MEM_OWNERS, both domains route to
    # overlapping experts, and eviction inside a block was LRU on WRITE-recency, so whichever domain stopped
    # being written was evicted oldest-first by construction. Every English entry gone, measured.
    # That failure mode is the one the eviction-clock work targeted: `last` is now last-RETRIEVAL and the read
    # probe makes it real during training rather than eval-only. So this arm is a RETEST of a known-bad
    # configuration on the machinery that was built to fix it, and the retention section is what it is read on --
    # not bits/byte. If English still vanishes here, per-expert memory is not a replacement for domains.
    nodom_mem) echo "SELF_ORG=0 MEM_PER_EXPERT=1" ;;
    nodom_mem_kn) echo "SELF_ORG=0 MEM_PER_EXPERT=1 FAB_KEY_NORM=1" ;;
    # === NEVER MEASURED ========================================================================================
    # Each of these is a mechanism that is BUILT, SHIPPED and OFF BY DEFAULT, and has never produced a number.
    # They are listed here so that "we have this" and "we know whether it helps" stop being the same sentence.
    #   mask     LOSS_MASK_DEAD alone. Excludes never-minted ids from the softmax DENOMINATOR. Isolated from
    #            growcap on purpose: growcap needs the mask, so bundling them would confound the valve with it.
    #   growcap  the capacity valve (A91). Soft caps that lift by GROW_LIFT rows when the cap is BOTH pinned and
    #            the loss has plateaued. FAB0 starts at the initial population so it is pinned from step 0;
    #            VOCAB0 starts below where minting saturated last run (2048) so the vocabulary half can lift too.
    #   ecw      FAB_EC_W, the expert-choice deficit bonus -- a per-expert logit bonus proportional to how far
    #            below its fair share of traffic an expert sits. The comment at its own site says it "has never
    #            once been set above 0 in a real run". 0.5 against a measured routing spread of ~2.3 is ~20% of
    #            the decision, chosen to be visible without dominating; the value is a guess and the arm is a
    #            direction test, not a tuning.
    #   rescue   FAB_RESCUE, mutate-instead-of-cull for a threatened expert (A92). Built, toy scale only. 0.35
    #            is the value the config-audit note quotes, so it is at least the number the design had in mind.
    mask)      echo "LOSS_MASK_DEAD=1" ;;
    growcap)   echo "GROW_CAP=1 LOSS_MASK_DEAD=1 GROW_CAP_FAB0=2048 GROW_CAP_VOCAB0=1024" ;;
    ecw)       echo "FAB_EC_W=0.5" ;;
    rescue)    echo "FAB_RESCUE=0.35" ;;
    # === WHICH GATE? ===========================================================================================
    # FAB_N0=2048 against FAB_NMAX=4096 parks occupancy at 0.50, permanently below FAB_PRESSURE=0.75, so the
    # utilization cull never runs -- and the utilization spare and FAB_RESCUE live inside that same branch.
    # Measured: "24 culled total, of which 24 for SUSTAINED error". Three ways to reopen it, one knob apart each,
    # so the runs decide rather than an argument does.
    #   gate_nmax  the population IS its own cap. Occupancy 1.0, closest to the pre-regression behaviour, but no
    #              preallocated headroom -- growth then has nowhere to go unless GROW_CAP lifts the soft cap.
    #   gate_press just lower the bar to below the standing occupancy. Keeps the headroom; the cost is that the
    #              threshold becomes a number fitted to one population size rather than a property.
    #   gate_soft  judge pressure against the OPERATING ceiling (the GROW_CAP soft cap) instead of against
    #              preallocation. Needs GROW_CAP on to mean anything, so it necessarily bundles the valve --
    #              read it against growcap from round4, not against base.
    # READ THESE ON DID IT FIRE FIRST. The question is whether the cull, the spare and the rescue become
    # reachable at all; bits/byte at n=1 cannot separate them, since base alone spans 1.969-2.100 across two
    # seeds. An arm that opens the gate and costs nothing is the answer; b/B is the tiebreak, not the test.
    gate_nmax)  echo "FAB_NMAX=2048" ;;
    gate_press) echo "FAB_PRESSURE=0.45" ;;
    gate_soft)  echo "FAB_PRESS_SOFT=1 GROW_CAP=1 LOSS_MASK_DEAD=1 GROW_CAP_FAB0=2048 GROW_CAP_VOCAB0=1024" ;;
    # ...and the rescue measurement that round4 could not make, on the gate most likely to open. If gate_nmax is
    # not the winner this needs re-running on whichever is; it is here so the grid produces a first FAB_RESCUE
    # number rather than none at all.
    gate_nmax_resc) echo "FAB_NMAX=2048 FAB_RESCUE=0.35" ;;
    nodom_kn)  echo "SELF_ORG=0 FAB_KEY_NORM=1" ;;
    # AN UNKNOWN ARM NAME MUST NOT SILENTLY BE base. Returning "" meant a typo ran the DEFAULT configuration
    # under the misspelled arm's log name -- a result filed against an experiment that never happened, which is
    # the most expensive quiet failure available here. base is a real arm at the top of this case; anything
    # that reaches the wildcard is a mistake, and the callers refuse it.
    *)         echo "__UNKNOWN_ARM__" ;;
  esac
}

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
  _pilot_corpus "$P_DD"
  mkdir -p "$OUT"
  P_SL=${STREAM_LEN:-4000000}; P_EP=${EPOCHS:-8}
  # Report the ACTUAL settings, not the defaults -- a banner that lies when overridden is how a run gets filed
  # under the wrong description weeks later.
  echo "pilot: ONE English corpus, domains self-assembled | $((P_SL/1000)) kB/epoch x $P_EP epochs = $((P_SL*P_EP/1000)) kB consumed | ~$((P_SL*P_EP/614)) steps"
  # BOTH ARCHITECTURES. The base LM is a GRU by default and every number this project has produced is a GRU
  # number; MODEL=transformer (4 layers, 8 heads, causal) HAS been run here -- two pilots, held-out 2.130 and
  # 2.184 at d768 L4 -- but both under FAB_GROW=1 to 4096 experts and before the instrument fixes, and both show
  # the broken-base signature (model ALONE 4.680/4.952 with the fabric carrying +2.6/+2.8). So it has never run
  # in a HEALTHY configuration, and those two numbers say nothing about the architecture. If proper language is the goal
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
  # RESUME FROM ANY CHECKPOINT, not only the one `pilot` happens to write. This was hardcoded to
  # $OUT/pilot_$PA, so every checkpoint produced by `seeds`, `grid` or `repeat` -- which is now most of them,
  # since SEED_CKPT=1 -- was unreachable, and continual learning could only be attempted from a run shape nobody
  # was using. RESUME_FROM=<dir> points it anywhere.
  # CONSUMED HERE, AND STRIPPED BEFORE PYTHON SEES IT. RESUME_FROM is a harness knob -- it selects which
  # checkpoint this script resumes from and self_organize.py has no business reading it. But it stays in the
  # environment the run inherits, where the config audit sees a RESUME-family variable that nothing read and
  # reports "NOTHING READ THESE: RESUME_FROM ... This run used the DEFAULTS for whatever was meant". That
  # warning is the one that catches real typos, so a standing false positive in it is expensive. `env -u`
  # below removes it for the child rather than adding an allow-list here that would go stale.
  FROM=${RESUME_FROM:-$OUT/pilot_$PA}
  [ -f "$FROM/ckpt.pt" ] || { echo "!! no checkpoint at $FROM/ckpt.pt -- run 'bash longrun.sh pilot' first (PILOT_ADD_ARCH=gru|transformer), or set RESUME_FROM=<dir containing ckpt.pt>"; exit 1; }
  # THE TOKENIZER TRAVELS WITH THE CHECKPOINT. The restored embedding is indexed by the vocabulary that trained
  # it; pairing it with a different one is silent, because VMAX fixes the row count so every shape still matches.
  # self_organize.py refuses on a vocabulary mismatch, and this finds the right file so it does not have to.
  if [ -z "${TOKENIZER_PATH:-}" ]; then
    for _tc in "$FROM.dyntok.json" "${FROM%.ckpt}.dyntok.json" "$(dirname "$FROM")/$(basename "$FROM" .ckpt).dyntok.json"; do
      [ -f "$_tc" ] && { TOKENIZER_PATH="$_tc"; break; }
    done
  fi
  [ -n "${TOKENIZER_PATH:-}" ] || { echo "!! cannot find the tokenizer that goes with $FROM -- set TOKENIZER_PATH=<the .dyntok.json saved beside it>"; exit 1; }
  # $OUT MUST EXIST BEFORE tee OPENS ITS FILE. `pilot` mkdir -p's it, `pilot-add` never did -- and tee opens its
  # output at process start, before python writes a byte. So on any box that has run `seeds` but not `pilot`,
  # runs/long/ does not exist, tee fails instantly, and the entire report goes to a closed pipe. The run itself
  # still finishes and still writes its checkpoint, which is the worst version: hours of GPU, a valid model, and
  # no record of what it measured.
  mkdir -p "$OUT" || exit 1
  # ONE name for the checkpoint and its log. _reserve was called twice, independently, so a second add could put
  # the checkpoint at pilot_gru_py-2 and its log at pilot_py.log -- a result filed under a name that does not
  # match the model that produced it.
  _PA_CK=$(_reserve "$OUT/pilot_${PA}_$NAME"); _PA_LOG="$_PA_CK.log"
  echo "pilot-add: resuming $FROM with vocabulary $TOKENIZER_PATH"
  # SAY WHERE THE OUTPUT GOES, before spending the GPU. The log lands under $OUT, which is not where the
  # checkpoint being RESUMED lives, and there is no way to guess that from the command line.
  echo "           checkpoint -> $_PA_CK"
  echo "           log        -> $_PA_LOG"
  if [ -z "$(ls "$P_DD/train/$NAME"/part*.txt 2>/dev/null)" ]; then
    # FETCH_ARGS passes anything else through to fetch_big.py -- notably --data-dir for datasets organised by
    # directory rather than config (the-stack: --data-dir data/python), and --token for gated ones.
    # shellcheck disable=SC2086
    python3 fetch_big.py --dataset "$DS" --domain "$NAME" --gb "$GB" --out "$P_DD" --resume ${FETCH_ARGS:-} || exit 1
  fi
  env -u RESUME_FROM DATA_MODE=real DATA_DIR="$P_DD" DOMAINS="eng,$NAME" DEVICE=${DEVICE:-cuda} DISK_STREAM=1 \
      CORPUS_CAP=100000000000 STREAM_LEN=${STREAM_LEN:-4000000} EPOCHS=${EPOCHS:-8} D_MODEL=${D_MODEL:-768} \
      WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 \
      SIG_WIN=${SIG_WIN:-614} \
      ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MEM_CAP=200000 MEM_QUOTA=${MEM_QUOTA:-3125} \
      CKPT_EVERY=10000 RATE_EVERY=2000 PROFILE=0 RESUME="$FROM" TOKENIZER_PATH="$TOKENIZER_PATH" \
      MODEL=$PA LAYERS=$([ "$PA" = transformer ] && echo ${TF_LAYERS:-4} || echo 1) \
      SAVE_CKPT="$_PA_CK" python3 self_organize.py 2>&1 | tee "$_PA_LOG"
  echo; echo ">> the number this run exists for is in ACROSS THE RUN BOUNDARY: what adding $NAME did to the English."
  echo ">> log: $_PA_LOG"
  echo ">> if that file is missing or truncated, the probe survives in the checkpoint itself:"
  echo ">>   python3 holdout.py $FROM $_PA_CK"
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
  _pilot_corpus "$P_DD"
  G_SL=${STREAM_LEN:-4000000}; G_EP=${EPOCHS:-8}
  # NAMED PRESETS: `bash longrun.sh grid ablate` runs just the set that answers the current question, in the
  # order that leaves the most informative partial result if it is stopped early.
  case "${2:-}" in
    # ORDERED BY INFORMATION VALUE, so stopping the block early still leaves the most useful subset: the control
    # first, then the tokenizer question, then the two changes that were confounded, then regularisation.
    pilots)  ARMS="base frozen frozen_nr drop wdecay reg" ;;
    ablate)  ARMS="nocompose composenov compose mintnovel noanchor nogrow bigpop" ;;
    tokens)  ARMS="nocompose compose mintnovel composenov noanchor" ;;
    fabric)  ARMS="nogrow bigpop nofabric smallpop" ;;
    # === ROUND 3: THE IDENTITY SPACE ==========================================================================
    # 31 of 40 archived runs print ">> COLLAPSED: every expert embeds to essentially the SAME identity" (NN
    # distance median 0.0009-0.0093 against a spawn bar of 0.0200). That one fact accounts for specialization
    # reading 0.000 and losing its own shuffled null, for FAB_SPAWN firing ~5x a run, and for HALT mass sitting
    # at 0.0000 -- the router cannot discriminate, so nothing downstream of it can either. Every arm here is
    # read FIRST on the identity-space line and the DID IT FIRE counters, and only then on bits/byte.
    #
    # ORDERED BY INFORMATION VALUE, so stopping early still leaves a readable comparison, and the two arms the
    # question was actually asked about (mintok, nodom) sit against base ONE KNOB APART rather than buried in a
    # combination. Their _kn partners come later, because they are only worth reading if keynorm lands.
    #   base       the control at HEAD -- growth fix, latched ramp, FAB_N0=2048. Everything is read against it.
    #   keynorm    the single highest-value arm: 4/4 archived key_norm runs are NON-collapsed, and the 3 of those
    #              that report HALT sit at 0.9170 against 0.0000 nearly everywhere else.
    #   embvar4    the coefficient the report itself names. Tests whether collapse is fixable WITHOUT touching
    #              routing at all -- if it is, key_norm's win is about scale and not about the embedding.
    #   mintok     TOK_MINT_UNTIL=1, one knob from base. The two archived runs with it reach HALT 0.4048, but
    #              four others sit at 0.0000, so alone it is the weaker lever and this is the arm that says so.
    #   nodom      SELF_ORG=0, one knob from base. The partition is measured not to earn its keep for prediction
    #              (own-domain gap +0.220 against a shuffled null of +0.223), so this asks what it costs to drop.
    #   embvar16   the second rung -- a coefficient with no measured direction needs more than one point.
    #   mintok_kn / nodom_kn / keynorm_ev   the combinations, only informative once keynorm has a verdict.
    round3)  ARMS="base keynorm embvar4 mintok nodom nodom_mem embvar16 mintok_kn nodom_mem_kn keynorm_ev" ;;
    # === ROUND 4: THINGS THAT HAVE NEVER PRODUCED A NUMBER =====================================================
    # Every arm here is a shipped mechanism sitting at its off-by-default value. The point is not to find a
    # winner, it is to stop carrying machinery whose effect is unknown -- and each arm ALSO answers a DID IT FIRE
    # question, which is the cheaper half of the result: growcap must print [capacity @ ...], rescue must move
    # fabric.rescue off "ARMED AND INERT", prob_use must retire tokens. An arm that changes nothing AND never
    # fires is a different finding from one that fires and changes nothing, and only the second is about the idea.
    #   base       control, re-run in this directory so the comparison is same-session
    #   frozen2k   07_WIP.md calls it "the highest-value unrun arm per unit of GPU": it separates FIXED vocabulary
    #              from TINY vocabulary, which every frozen-vs-growing comparison so far has confounded
    #   mask       LOSS_MASK_DEAD alone, so growcap's result can be attributed
    #   growcap    the capacity valve, measured for the first time
    #   ecw        the only implemented term that rewards experts for taking traffic they are short of
    #   rescue     mutate-instead-of-cull
    #   prob_use   TOK_PROBATION: do minted tokens that never get used earn their slot back
    round4)  ARMS="base frozen2k mask growcap ecw rescue prob_use" ;;
    # === ROUND 5: WHICH GATE REOPENS THE UTILIZATION CULL ======================================================
    # base is the control and is EXPECTED to show the cull off -- that is the regression, restated as a measured
    # baseline. Every other arm is judged first on whether [experts @ ...] reports culls "under capacity
    # pressure", whether fabric.spare leaves zero, and whether fabric.rescue stops reading UNREACHABLE.
    round5)  ARMS="base gate_nmax gate_press gate_soft gate_nmax_resc" ;;
    "")      ARMS=${GRID_ARMS:-$GRID_ARMS_DEFAULT} ;;
    *)       ARMS="$2" ;;
  esac
  ARMS=${GRID_ARMS:-$ARMS}
  echo "grid -> $GRID | arms: $ARMS | $((G_SL/1000)) kB/epoch x $G_EP epochs each"
  echo "  (re-running this command SKIPS completed arms and never overwrites a finished log)"
  trap 'echo; echo "grid interrupted -- completed arms are kept; re-run the same command to continue"; exit 130' INT TERM
  for ARM in $ARMS; do
    LOG="$GRID/$ARM.log"
    _stopped "$GRID" && break
    if _done "$LOG"; then _reusable "$LOG" || exit 1; echo "== $ARM: already complete, skipping"; continue; fi
    if [ -f "$LOG" ]; then
      _pn=1; while [ -e "$LOG.partial-$_pn" ]; do _pn=$((_pn+1)); done
      mv "$LOG" "$LOG.partial-$_pn"
      echo "== $ARM: previous attempt was incomplete -> kept as $LOG.partial-$_pn"
    fi
    FLAGS="$(_flags_for "$ARM")"
    case "$FLAGS" in __UNKNOWN_ARM__) echo "!! unknown arm '$ARM' -- not in _flags_for. Nothing run."; exit 1 ;; esac
    echo; echo "################  arm: $ARM  ${FLAGS:-(defaults)}  ################"
    _t_start=$(date +%s)
    # set +e around the arm: one crash must not end the grid. SAVE_CKPT is reserved, so a retry cannot stomp a
    # checkpoint an earlier attempt left behind.
    set +e
    # ARM FLAGS LAST, SO THEY WIN. `env A=1 A=2` keeps the LAST assignment, and $FLAGS used to come FIRST --
    # so every knob hardcoded below (VMAX, WIN, BATCH_W, RATE_EVERY, CKPT_EVERY, GROW_*, SEG_*, DATA_DIR, ...)
    # silently DISCARDED an arm flag of the same name. `grid 3 VMAX=512` ran at 2048 and labelled the log 512.
    # The loop's own SEED stays after the flags: varying it is the whole point of the subcommand.
    env MODEL=gru LAYERS=1 HEADS=${HEADS:-8} \
        DATA_MODE=real DATA_DIR="$P_DD" DOMAINS=eng DEVICE=${DEVICE:-cuda} DISK_STREAM=1 \
        CORPUS_CAP=100000000000 STREAM_LEN=$G_SL EPOCHS=$G_EP D_MODEL=${D_MODEL:-768} \
        WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 \
        SIG_WIN=${SIG_WIN:-614} ENC_WARMUP=2000 ENC_WARMUP_MIN=500 \
        MEM_CAP=200000 MEM_QUOTA=${MEM_QUOTA:-3125} \
        CKPT_EVERY=10000 RATE_EVERY=2000 PROFILE=0 PROBE_WAIT=0 \
        TOKENIZER_PATH="$GRID/$ARM.dyntok.json" \
        SAVE_CKPT="$([ "${GRID_CKPT:-1}" = 1 ] && _reserve "$GRID/$ARM" || echo 0)" \
        $FLAGS \
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
    # THE UNIT-STABLE NUMBER, NOT THE PER-TOKEN ONE. This used to grep "since the minimum", which is per-TOKEN
    # cross-entropy. The tokenizer mints throughout a run, so each token comes to carry more bytes and that loss
    # rises MECHANICALLY while the model improves per byte. The log says so itself, three lines further down:
    # "NOT DIVERGING -- the per-token rise is the growing vocabulary, not the model. Judge this run on bits/byte."
    # The summary was surfacing the misleading figure and hiding the correct one directly beneath it, and a whole
    # session of conclusions was drawn off the difference -- frozen2k and growcap reading +0.000 against base
    # +0.285 is ENTIRELY this artifact: on bits/byte both read +0.000. A grid summary is what gets quoted, so it
    # has to carry the number the log tells you to judge on.
    _cv=$(grep -a -oE "CROSS-CHECK \(held-out bits/byte[^)]*\): [-+][0-9.]+" "$L" | head -1 | awk '{print $NF}')
    # Fall back to the per-token figure only if the unit-stable one is absent (too few held-out points), and MARK
    # it, so a reader never mistakes one for the other.
    [ -n "$_cv" ] || _cv="$(grep -a -oE "since the minimum [-+][0-9.]+" "$L" | head -1 | awk '{print $NF}')~tok"
    _ex=$(grep -a -oE "[0-9]+ distinct experts won" "$L" | head -1 | awk '{print $1}')
    _tp=$(grep -a -oE "top expert took [0-9.]+%" "$L" | head -1 | awk '{print $NF}')
    _mx=$(grep -a -oE "spread [0-9.]+ \([0-9]+%\) vs WEIGHT-PREDICTION term spread [0-9.]+ \([0-9]+%\)" "$L" | head -1 | sed -E 's/spread [0-9.]+ \(([0-9]+%)\).*\(([0-9]+%)\)/region \1 weight \2/')
    printf "  %-9s %-7s %-13s %-11s %-9s %-22s %s\n" "$ARM" "${_ho:--}" "${_o1:--}" "${_cv:--}" "${_ex:--}" "${_tp:--}" "${_mx:--}"
  done
  echo
  echo "  curve = held-out BITS/BYTE since this run's own minimum. Positive means it really got worse. A value"
  echo "  marked ~tok is the per-TOKEN fallback and is NOT comparable across arms whose vocabularies differ:"
  echo "  minted tokens carry more bytes, so per-token loss rises even while bits/byte falls."
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
  # DETERMINISM: asserted here for a long time without a test, then tested. Three runs at the same seed and
  # config came back byte-identical in every reported number, and `equiv.sh` reproduces that across commits. So
  # the spreads below ARE seed variance, not run-to-run jitter, and `repeat` has served its purpose -- it is kept
  # as a regression check for after a driver or GPU change, not as a routine measurement.
  # What determinism does NOT buy is robustness: a run reproduces itself exactly, while ANY difference between
  # two runs -- including ones that should not matter -- can move the result by more than a bit/byte. n=1 is
  # enough to reproduce a config; it is not enough to attribute a difference BETWEEN two configs.
  #   bash longrun.sh seeds 3 SOCIETY=1        # 3 seeds of one arm
  #   SEEDS="0 1 2 3" bash longrun.sh seeds -- CHAIN_ROUTE=soc
  # CHECKPOINTS ON BY DEFAULT, matching `grid` (GRID_CKPT:-1). This defaulted to 0, so the sweep that produces
  # the models worth continuing from was the one that threw them away -- and continual learning, the target,
  # needs a checkpoint to resume. Roughly a GB per seed at MEM_CAP=200000 (the memory keys dominate);
  # SEED_CKPT=0 opts out when the disk matters more than the ability to build on the result.
  N=${2:-3}
  case "$N" in ''|*[!0-9]*) N=3;; esac
  shift $([ "${2:-}" = "$N" ] && echo 2 || echo 1) 2>/dev/null || true
  [ "${1:-}" = "--" ] && shift
  ARMFLAGS="$*"
  SEEDLIST=${SEEDS:-$(seq 0 $((N-1)))}
  _pilot_corpus "${PILOT_DIR:-data_pilot}"
  SD=${SEED_DIR:-runs/seeds}
  mkdir -p "$SD"
  TAG=$(echo "${ARMFLAGS:-default}" | tr ' =' '__' | cut -c1-40)
  echo "seeds: arm [${ARMFLAGS:-defaults}] over seeds [$(echo $SEEDLIST | tr '\n' ' ')] -> $SD"
  for SEED in $SEEDLIST; do
    LOG="$SD/${TAG}_seed$SEED.log"
    _stopped "$SD" && break
    if _done "$LOG"; then _reusable "$LOG" || exit 1; echo "== seed $SEED: already complete, skipping"; continue; fi
    [ -f "$LOG" ] && { _pn=1; while [ -e "$LOG.partial-$_pn" ]; do _pn=$((_pn+1)); done; mv "$LOG" "$LOG.partial-$_pn"; }
    echo; echo "################  seed $SEED  ${ARMFLAGS:-(defaults)}  ################"
    set +e
    # ARM FLAGS LAST, SO THEY WIN. `env A=1 A=2` keeps the LAST assignment, and $FLAGS used to come FIRST --
    # so every knob hardcoded below (VMAX, WIN, BATCH_W, RATE_EVERY, CKPT_EVERY, GROW_*, SEG_*, DATA_DIR, ...)
    # silently DISCARDED an arm flag of the same name. `grid 3 VMAX=512` ran at 2048 and labelled the log 512.
    # The loop's own SEED stays after the flags: varying it is the whole point of the subcommand.
    env MODEL=gru LAYERS=1 DATA_MODE=real DATA_DIR="${PILOT_DIR:-data_pilot}" DOMAINS=eng \
        DEVICE=${DEVICE:-cuda} DISK_STREAM=1 CORPUS_CAP=100000000000 \
        STREAM_LEN=${STREAM_LEN:-4000000} EPOCHS=${EPOCHS:-8} D_MODEL=${D_MODEL:-768} \
        WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 \
        SIG_WIN=${SIG_WIN:-614} ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MEM_CAP=200000 \
        MEM_QUOTA=${MEM_QUOTA:-3125} CKPT_EVERY=10000 RATE_EVERY=2000 PROFILE=0 PROBE_WAIT=0 \
        TOKENIZER_PATH="$SD/${TAG}_seed$SEED.dyntok.json" \
        SAVE_CKPT=$([ "${SEED_CKPT:-1}" = 1 ] && _reserve "$SD/${TAG}_seed$SEED.ckpt" || echo 0) \
        $ARMFLAGS SEED=$SEED \
        python3 self_organize.py > "$LOG" 2>&1
    _rc=$?
    # STAMP WHAT PRODUCED IT, next to it. Without this the resume-skip can only ask "did a log with this
    # name finish", which is not the same question as "is this run interchangeable with the one I want".
    if [ "$_rc" = 0 ] && _done "$LOG"; then _cfgsig > "$LOG.cfg"; fi
    echo "== seed $SEED: rc=$_rc"
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
    # SPEC NEVER WITHOUT ITS NULL. The bare number is meaningless and reliably over-read: a DIV_W ladder showed
    # 0.000 / 0.120 / 0.047 and the 0.120 looked like the distinctness reward finally working. It was not -- the
    # log's own shuffled-assignment null for that run was 0.138 +/- 0.062, so the "improvement" sat BELOW the bar
    # it must clear, and all three arms were INTERCHANGEABLE. Specialization is a difference from a null, not a
    # level, and printing the level alone invites exactly that mistake.
    rows.append((re.search(r"seed(\d+)", f).group(1), g(r"held-out ([0-9.]+)"),
                 g(r"beats order-1 by \+([0-9.]+)"), g(r"SPECIALIZATION[^0-9]*([0-9.]+)"),
                 g(r"shuffled-assignment null\s+([0-9.]+)"),
                 g(r"shuffled-assignment null\s+[0-9.]+ \+/- ([0-9.]+)")))
print(f"  {'seed':>4}  {'held-out':>9}  {'vs order-1':>11}   {'spec vs its shuffled null':<34}")
for s, h, o, sp, nu, ns in rows:
    if sp is None:   _sc = "-"
    elif nu is None: _sc = f"{sp}  (null not reported)"
    else:            _sc = (f"{sp:.3f} vs {nu:.3f}+/-{(ns or 0):.3f}  "
                            + ("SPECIALIZED" if sp > nu + (ns or 0) else "interchangeable"))
    print(f"  {s:>4}  {h if h else '-':>9}  {o if o else '-':>11}   {_sc:<34}")
hs = [r[1] for r in rows if r[1]]
if len(hs) > 1:
    print(f"\n  held-out: mean {st.mean(hs):.3f}  spread {max(hs)-min(hs):.3f}  "
          f"sd {st.pstdev(hs):.3f}  over {len(hs)} seeds")
    print(f"  >> an architecture difference SMALLER than the spread is not a result. The four best arms in this")
    print(f"     project sit inside 0.06 b/B of each other; measured seed spread has reached 0.174.")
PY
  ;;

repeat)
  # === THE SAME SEED, N TIMES -- IS THIS SYSTEM EVEN REPRODUCIBLE? ============================================
  # Every comparison in this project assumes a run is a function of (config, commit, SEED). That assumption has
  # never been tested, and it is now load-bearing: two runs at the SAME default config and the SAME seed, twelve
  # commits apart, came out 2.275 and 3.694 held-out -- and an exhaustive per-commit review found nothing in
  # between that touches the optimised computation at those defaults. Either the review missed something, or
  # runs at a fixed seed simply do not land in the same place.
  #
  # This answers it directly and it is the cheapest decisive test available:
  #   spread << 0.2  -> runs are reproducible, the +1.42 is real and owned by code, keep bisecting
  #   spread ~ 1.4   -> runs are NOT reproducible at fixed seed, and no single-run comparison in this project
  #                     has ever measured what it claimed to measure, including every architecture ranking
  #
  #   bash longrun.sh repeat 3                 # 3 runs of HEAD defaults at SEED=0
  #   SEED=1 bash longrun.sh repeat 3          # ... at SEED=1
  #   bash longrun.sh repeat 3 SOCIETY=1       # 3 runs of one arm
  N=${2:-3}
  case "$N" in ''|*[!0-9]*) N=3;; esac
  shift $([ "${2:-}" = "$N" ] && echo 2 || echo 1) 2>/dev/null || true
  [ "${1:-}" = "--" ] && shift
  ARMFLAGS="$*"
  RSEED=${SEED:-0}
  _pilot_corpus "${PILOT_DIR:-data_pilot}"
  RD=${REPEAT_DIR:-runs/repeat}
  mkdir -p "$RD"
  TAG=$(echo "${ARMFLAGS:-default}" | tr ' =' '__' | cut -c1-40)
  echo "repeat: arm [${ARMFLAGS:-defaults}] at SEED=$RSEED x $N runs -> $RD"
  echo "  (re-running SKIPS completed runs and never overwrites a finished log)"
  trap 'echo; echo "repeat interrupted -- completed runs are kept; re-run to continue"; exit 130' INT TERM
  for R in $(seq 1 "$N"); do
    LOG="$RD/${TAG}_seed${RSEED}_run$R.log"
    _stopped "$RD" && break
    if _done "$LOG"; then _reusable "$LOG" || exit 1; echo "== run $R: already complete, skipping"; continue; fi
    [ -f "$LOG" ] && { _pn=1; while [ -e "$LOG.partial-$_pn" ]; do _pn=$((_pn+1)); done; mv "$LOG" "$LOG.partial-$_pn"; }
    echo; echo "################  run $R/$N  SEED=$RSEED  ${ARMFLAGS:-(defaults)}  ################"
    set +e
    # ARM FLAGS LAST, SO THEY WIN. `env A=1 A=2` keeps the LAST assignment, and $FLAGS used to come FIRST --
    # so every knob hardcoded below (VMAX, WIN, BATCH_W, RATE_EVERY, CKPT_EVERY, GROW_*, SEG_*, DATA_DIR, ...)
    # silently DISCARDED an arm flag of the same name. `grid 3 VMAX=512` ran at 2048 and labelled the log 512.
    # The loop's own SEED stays after the flags: varying it is the whole point of the subcommand.
    env MODEL=gru LAYERS=1 DATA_MODE=real DATA_DIR="${PILOT_DIR:-data_pilot}" DOMAINS=eng \
        DEVICE=${DEVICE:-cuda} DISK_STREAM=1 CORPUS_CAP=100000000000 \
        STREAM_LEN=${STREAM_LEN:-4000000} EPOCHS=${EPOCHS:-8} D_MODEL=${D_MODEL:-768} \
        WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 \
        SIG_WIN=${SIG_WIN:-614} ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MEM_CAP=200000 \
        MEM_QUOTA=${MEM_QUOTA:-3125} CKPT_EVERY=10000 RATE_EVERY=2000 PROFILE=0 PROBE_WAIT=0 \
        TOKENIZER_PATH="$RD/${TAG}_run$R.dyntok.json" \
        SAVE_CKPT=0 \
        $ARMFLAGS SEED=$RSEED \
        python3 self_organize.py > "$LOG" 2>&1
    _rc=$?
    if [ "$_rc" = 0 ] && _done "$LOG"; then _cfgsig > "$LOG.cfg"; fi
    echo "== run $R: rc=$_rc"
    set -e 2>/dev/null || true
  done
  echo; echo "=== REPEAT SUMMARY: [${ARMFLAGS:-defaults}] at SEED=$RSEED ==="
  python3 - "$RD" "$TAG" "$RSEED" <<'PY'
import sys, glob, re, statistics as st
rd, tag, sd = sys.argv[1], sys.argv[2], sys.argv[3]
rows = []
for f in sorted(glob.glob(f"{rd}/{tag}_seed{sd}_run*.log")):
    b = open(f, errors="ignore").read()
    def g(p):
        m = re.search(p, b)
        return float(m.group(1)) if m else None
    rows.append((re.search(r"run(\d+)\.log", f).group(1),
                 g(r"held-out ([0-9.]+)"),          # the fresh end-of-run number
                 g(r"model ALONE ([0-9.]+)  ->  \+ FABRIC"),   # base model, fabric ablated
                 g(r"top expert took ([0-9.]+)%")))
print(f"  {'run':>4}  {'held-out':>9}  {'model ALONE':>12}  {'top-expert%':>12}")
for r, h, m, t in rows:
    print(f"  {r:>4}  {h if h else '-':>9}  {m if m else '-':>12}  {t if t else '-':>12}")
hs = [h for _, h, _, _ in rows if h]
ms = [m for _, _, m, _ in rows if m]
if len(hs) > 1:
    sp = max(hs) - min(hs)
    print(f"\n  held-out    mean {st.mean(hs):.3f}  spread {sp:.3f}  sd {st.pstdev(hs):.3f}  over {len(hs)} runs")
    if ms and len(ms) > 1:
        print(f"  model ALONE mean {st.mean(ms):.3f}  spread {max(ms)-min(ms):.3f}  (fabric ablated -- "
              f"a base-model spread means the instability is NOT in the routing)")
    print()
    if sp < 0.2:
        print(f"  >> REPRODUCIBLE at fixed seed (spread {sp:.3f}). The 2.275 -> 3.694 gap is real and owned by")
        print(f"     code; keep bisecting. Every past single-run comparison remains as valid as its seed spread.")
    else:
        print(f"  >> NOT REPRODUCIBLE at fixed seed (spread {sp:.3f}). Same config, same seed, same commit.")
        print(f"     No single-run comparison in this project has measured what it claimed to, and the whole")
        print(f"     architecture ranking has to be re-established from repeated runs, not from one run per arm.")
PY
  ;;

smoke)
  # === DOES THE CODE STILL RUN? ==============================================================================
  # Not "is it good" -- that is what the pilot is for. This asserts only that every configuration the pilot
  # will use REACHES ITS REPORT, which is the failure this project actually keeps hitting: a knob that crashes
  # a diagnostic, a name collision that swallows the metrics, a gate that starves the vocabulary. Each arm is
  # a few minutes on a GPU. Run it before spending hours.
  #   Deliberately tiny AND deliberately NOT a quality measurement: at 40 kB the held-out numbers are noise,
  # and reading them as a result is how a smoke test turns into a wasted day.
  _pilot_corpus "${PILOT_DIR:-data_pilot}"
  SMK=${SMOKE_DIR:-runs/smoke}; mkdir -p "$SMK" || exit 1
  echo "smoke: ${SMOKE_ARMS:-every pilot arm} at 40 kB / 3 epochs on ${DEVICE:-cuda}."
  echo "  Asserting only that each REACHES ITS REPORT. The held-out numbers at this size are noise --"
  echo "  reading them as a result is how a smoke test turns into a wasted day."
  _fail=0
  for ARM in ${SMOKE_ARMS:-base nogate frozen pgate_t prob_use prob_emb compose}; do
    # ONE DEFINITION OF WHAT AN ARM IS. This case block used to repeat _flags_for's contents, and they had
    # already drifted apart within the hour: smoke ran TOK_PROBATION=150 where the grid runs 200, and its
    # `compose` was missing TOK_MINT_NOVEL=0. A smoke test that greenlights a configuration the grid does not
    # run is worse than no smoke test, because it reports confidence about something nobody will execute.
    SX=$(_flags_for "$ARM")
    case "$SX" in __UNKNOWN_ARM__) echo "!! unknown arm '$ARM' -- not in _flags_for. Nothing run."; exit 1 ;; esac
    rm -f "$SMK/$ARM.dyntok.json"
    set +e
    env DATA_MODE=real DATA_DIR="${PILOT_DIR:-data_pilot}" DOMAINS=eng DISK_STREAM=1 \
        CORPUS_CAP=100000000000 MODEL=gru LAYERS=1 DEVICE=${DEVICE:-cuda} SEED=0 \
        SAVE_CKPT=0 PROBE_WAIT=0 PROFILE=0 CKPT_EVERY=0 \
        D_MODEL=64 WIN=32 BATCH_W=4 STREAM_LEN=40000 EPOCHS=3 \
        VMAX=512 SEED_VOCAB=256 GROW_EVERY=20 GROW_BURST=8 RETOK_EVERY=200 \
        FAB_NMAX=32 FAB_N0=3 MEM_CAP=4800 MEM_QUOTA=150 \
        MANAGE_EVERY=50 DOM_MANAGE_EVERY=50 ENC_WARMUP=60 ENC_WARMUP_MIN=30 SIG_WIN=64 \
        RATE_EVERY=500 GEN_LEN=20 GEN_N=1 EVAL_N=4 COH_N=2 COH_LEN=32 HOLDOUT_N=4 \
        TOK_PROBATION_STEPS=1500 \
        \
        TOKENIZER_PATH="$SMK/$ARM.dyntok.json" \
        $SX python3 self_organize.py > "$SMK/$ARM.log" 2>&1
    _rc=$?
    set -e 2>/dev/null || true
    if [ "$_rc" = 0 ] && _done "$SMK/$ARM.log"; then
      printf "  ok    %-9s %s\n" "$ARM" "$(grep -aoE 'train [0-9.]+ \| held-out [0-9.]+' "$SMK/$ARM.log" | head -1)"
    else
      _fail=1
      printf "  FAIL  %-9s rc=%s -- %s\n" "$ARM" "$_rc" "$SMK/$ARM.log"
      grep -a -E "Traceback|Error|!! " "$SMK/$ARM.log" | tail -3 | sed 's/^/          /'
    fi
  done
  echo
  if [ "$_fail" = 0 ]; then echo "all arms reached the report. safe to spend the GPU."
  else echo "!! at least one arm did not finish -- fix that before the pilot."; exit 1; fi
  ;;

ladder)
  # === ONE KNOB, SEVERAL VALUES, THE SAME SEEDS ================================================================
  # A pair answers "is A better than B". A ladder answers the question actually being asked of an untuned knob:
  # WHICH WAY, and how far. Three or four values over shared seeds cost little more than two and give something
  # a pairwise test cannot -- a TREND. If bits/byte moves monotonically across four values, that is evidence
  # beyond what any single comparison reaches at these sample sizes, where compare.py will usually and correctly
  # refuse to call a 0.2 b/B difference.
  #
  #   bash longrun.sh ladder 4 FAB_LR_CYCLE 8 24 72 216
  #   LADDER_DIR=runs/lr bash longrun.sh ladder 4 LR 1e-3 2e-3 4e-3
  #
  # The FIRST value is the baseline every other is compared against. Every value runs the same seed list into its
  # own directory, so the comparisons are paired by construction.
  N=${2:-3}
  case "$N" in ''|*[!0-9]*) N=3;; esac
  shift 2 2>/dev/null || shift 1
  KNOB=${1:-}; shift 2>/dev/null || true
  [ -n "$KNOB" ] && [ $# -ge 2 ] || { echo "!! usage: bash longrun.sh ladder <seeds> <KNOB> <v1> <v2> [v3 ...]"; exit 1; }
  LD=${LADDER_DIR:-runs/ladder_$(echo "$KNOB" | tr 'A-Z' 'a-z')}
  export SEEDS=${SEEDS:-$(seq 0 $((N-1)))}
  VALS="$*"
  _n_runs=0; for _v in $VALS; do _n_runs=$((_n_runs + N)); done
  [ -n "${LADDER_BASE:-}" ] && _n_runs=$((_n_runs - N))
  echo "ladder: $KNOB over [$VALS] x seeds [$(echo $SEEDS | tr '\n' ' ')] -> $LD"
  echo "        $_n_runs runs; the first value ($1) is the baseline the rest are compared against."
  BASE=$(echo "$VALS" | awk '{print $1}')
  # REUSE A BASELINE ALREADY RUN. Two ladders over different knobs share one rung -- their baseline is the same
  # configuration, the defaults -- and running it twice is a wasted arm's worth of GPU for an identical result.
  # LADDER_BASE=<dir of a completed baseline> skips it here and compares against that instead.
  BASEDIR="$LD/$KNOB=$BASE"
  if [ -n "${LADDER_BASE:-}" ]; then
    BASEDIR="$LADDER_BASE"
    [ -d "$BASEDIR" ] || { echo "!! LADDER_BASE=$BASEDIR does not exist"; exit 1; }
    echo "        baseline rung $KNOB=$BASE reused from $BASEDIR (not re-run)"
    echo "        -- it must be the SAME configuration apart from this knob, or the comparison is not paired;"
    echo "           compare.py checks the commit and the corpus, but it cannot check what else you changed."
  fi
  for _v in $VALS; do
    if [ -n "${LADDER_BASE:-}" ] && [ "$_v" = "$BASE" ]; then continue; fi
    _d="$LD/$KNOB=$_v"
    mkdir -p "$_d"
    echo; echo "################  $KNOB=$_v  ################"
    SEED_DIR="$_d" bash "$0" seeds "$N" -- "$KNOB=$_v" || { echo "!! rung $KNOB=$_v failed"; exit 1; }
    _stopped "$LD" && { echo "ladder: STOP file seen, stopping after $KNOB=$_v"; break; }
  done
  echo; echo "=== LADDER: every rung against the baseline $KNOB=$BASE ==="
  for _v in $VALS; do
    [ "$_v" = "$BASE" ] && continue
    [ -d "$LD/$KNOB=$_v" ] || continue
    echo; echo "---- $KNOB=$_v  vs  $KNOB=$BASE ----"
    python3 compare.py "$LD/$KNOB=$_v"/*_seed*.log -- "$BASEDIR"/*_seed*.log \
        --label-a "$_v" --label-b "$BASE" || true
  done
  echo; echo "  A ladder is read for its TREND as much as its verdicts: compare.py judges each rung on its own"
  echo "  and will refuse small differences at this many seeds, but a consistent direction across rungs is"
  echo "  itself evidence, and a non-monotone ladder says the knob is not doing what its name suggests."
  ;;

pair)
  # === TWO ARMS, ONE KNOB, THE SAME SEEDS ======================================================================
  # The measurement discipline made executable. Every architecture claim in this project was made by comparing
  # two numbers -- INV-35 voids all of them -- and the fix is not a bigger number of runs, it is PAIRING: run
  # both arms over the SAME seed list so they share data order and initialisation, then judge with P(A>B) rather
  # than by eye. The stream RNG is already isolated from the global one (c76dc74), so two arms at one seed see
  # identical text and identical init and differ only by the knob under test. Pairing is therefore free here.
  #
  #   bash longrun.sh pair 3 LR=1e-3 -- LR=2e-3
  #   SEEDS="0 1 2" PAIR_DIR=runs/lr bash longrun.sh pair -- FAB_LR_CYCLE=24 -- FAB_LR_CYCLE=2000
  #
  # It runs `seeds` twice into two directories and then calls compare.py on the result, so the comparison cannot
  # be done unpaired by accident -- which is what happened when the arms were run by hand into one folder.
  N=${2:-3}
  case "$N" in ''|*[!0-9]*) N=3;; esac
  shift $([ "${2:-}" = "$N" ] && echo 2 || echo 1) 2>/dev/null || true
  [ "${1:-}" = "--" ] && shift
  # SPLIT ON THE `--` BETWEEN THE ARMS. Everything before it is arm A's flags, everything after is arm B's.
  A_FLAGS=""; B_FLAGS=""; _side=a
  for _t in "$@"; do
    if [ "$_t" = "--" ]; then _side=b; continue; fi
    if [ "$_side" = a ]; then A_FLAGS="$A_FLAGS $_t"; else B_FLAGS="$B_FLAGS $_t"; fi
  done
  A_FLAGS=$(echo "$A_FLAGS" | sed 's/^ *//'); B_FLAGS=$(echo "$B_FLAGS" | sed 's/^ *//')
  [ -n "$B_FLAGS" ] || { echo "!! usage: bash longrun.sh pair <n> <A flags> -- <B flags>   (the second -- separates the arms)"; exit 1; }
  PD=${PAIR_DIR:-runs/pair}
  A_TAG=$(echo "${A_FLAGS:-baseline}" | tr ' =' '__' | cut -c1-24)
  B_TAG=$(echo "${B_FLAGS:-baseline}" | tr ' =' '__' | cut -c1-24)
  [ "$A_TAG" = "$B_TAG" ] && { echo "!! both arms tag as '$A_TAG' -- they differ by nothing this script can see"; exit 1; }
  export SEEDS=${SEEDS:-$(seq 0 $((N-1)))}
  echo "pair: A=[$A_FLAGS]  B=[$B_FLAGS]  over seeds [$(echo $SEEDS | tr '\n' ' ')] -> $PD"
  echo "      both arms run the SAME seeds, so compare.py can pair them; anything else is not a comparison."
  for _arm in A B; do
    if [ "$_arm" = A ]; then _f="$A_FLAGS"; _d="$PD/$A_TAG"; else _f="$B_FLAGS"; _d="$PD/$B_TAG"; fi
    mkdir -p "$_d"
    echo; echo "################  ARM $_arm  [$_f]  ################"
    # shellcheck disable=SC2086
    SEED_DIR="$_d" bash "$0" seeds "$N" -- $_f || { echo "!! arm $_arm failed"; exit 1; }
  done
  echo; echo "=== PAIRED COMPARISON ==="
  python3 compare.py "$PD/$A_TAG"/*_seed*.log -- "$PD/$B_TAG"/*_seed*.log \
      --label-a "$A_TAG" --label-b "$B_TAG" || true
  echo "  (re-run the comparison any time:  python3 compare.py $PD/$A_TAG/*_seed*.log -- $PD/$B_TAG/*_seed*.log)"
  ;;

watch)
  [ -f "$OUT/run.log" ] || { echo "no $OUT/run.log yet"; exit 1; }
  echo "=== last progress"; grep -a -E "\[rate\]|\[epoch |\[PHASE |\[saved checkpoint" "$OUT/run.log" | tail -12
  echo; echo "=== anything wrong"; grep -a -E "!! |Traceback|Error" "$OUT/run.log" | tail -8
  echo; echo "=== live"; tail -3 "$OUT/run.log"
  ;;

*) echo "usage: bash longrun.sh [pilot|grid|seeds <n> [FLAGS]|pair <n> <A flags> -- <B flags>|ladder <n> <KNOB> <v1> <v2> ...|repeat <n> [FLAGS]|smoke|pilot-add <name> <ds> [gb]|fetch|run|resume|add <name> <ds> [gb]|watch]"; exit 1 ;;
esac
