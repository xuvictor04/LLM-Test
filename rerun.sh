#!/usr/bin/env bash
# ---------------------------------------------------------------------------------------------------------------
# rerun.sh -- the reruns that became necessary when the audit found six subsystems defaulting OFF.
#
# Every result this project produced before commit 51889b7 was measured on the base LM + memory + domains, with
# the routed expert population, the expanding tokenizer, the world model and the per-expert memory partition all
# absent, so those results describe a different system. This re-measures on the whole one.
#
# The +0.709 for FABRIC that this file used to quote is RETRACTED. It was the report's own
# "model ALONE -> +FABRIC" figure, which is an eval-time KNOCKOUT of a component the model TRAINED with, and the
# report itself prints a caveat saying it overstates. The retrained ablation is the honest test and says 3.089 vs
# 3.090: no bits/byte at all. The largest retrained effect measured so far is the WORLD MODEL (+0.103).
#
#   bash rerun.sh            # all of it (~15 min on a GH200)
#   bash rerun.sh mix        # just the 4-corpus run
#   bash rerun.sh eng        # just the single-corpus run
#   bash rerun.sh ablate     # what each subsystem is worth, one at a time
#   bash rerun.sh smoke      # RUN THIS FIRST. Every arm at toy scale on CPU, ~2 min, exit codes only.
#
# smoke exists because the first rerun lost the ab_no_world arm to a crash: WORLD_GROW defaults ON and its step
# hook dereferenced world_fwd OUTSIDE the `if WORLD_MODEL:` block, so WORLD_MODEL=0 died at the first
# MANAGE_EVERY. An ablation flag is the least-exercised path in the file -- the one arm nobody runs until the
# night it matters. Two CPU minutes buys the whole grid.
#
# READ IN THIS ORDER. It is the order of what the project is FOR, and nothing else earns a place above it:
#
#   1. THE OUTPUT
#      GENERATION       read the samples. This is the deliverable; every number below is a proxy for it.
#      ANCHORS          does the model beat order-1 on the same held-out text? the one unmoored-number check
#      COHERENCE        does a continuation stay in its seed's domain? read WITH its +/- and its floor
#
#   2. CONTINUAL LEARNING WITHOUT EXORBITANT FORGETTING
#      ACROSS THE RUN BOUNDARY  what this run did to what was already known. The only figure that spans runs.
#      RETENTION        is what it saw first still modelled as well as what it saw last?
#      LEARNING CURVE   how fast a process is picked up, and what happens once it leaves
#
#   3. THE MACHINERY, only insofar as it moves 1 and 2
#      EXPERTS          is the population specialized, or evenly loaded and interchangeable? how many nodes UNUSED?
#      FABRIC           what the routed population contributes, and whether the router HALTs instead of routing
#
# DIAGNOSTICS, NOT TARGETS: domain counts, purity, silhouette, V-measure, CAN A DOMAIN PREDICT. They exist to
# explain movement in 1 and 2. Steering by them is what produced most of this file's history, and a domain count
# going up is not a result. If a diagnostic disagrees with 1 and 2, the diagnostic is what needs re-examining.
set -u

WHICH=${1:-all}
OUT=${OUT:-runs/rerun_$(date +%m%d_%H%M)}
mkdir -p "$OUT"
SL=${STREAM_LEN:-4000000}
D=${D_MODEL:-768}

# CORPUS_CAP: without it every corpus is capped at 2 MB regardless of what is on disk.
# MEM_QUOTA: the per-expert partition DERIVES the store as n_own x quota, silently overriding MEM_CAP. At the
#   default 64 x 128 that is 8192 slots -- a 24x cut against MEM_CAP=200000. 3125 keeps the store whole. Set
#   MEM_QUOTA=128 instead to test the small-quota design deliberately; the run warns either way.
COMMON="DATA_MODE=real DATA_DIR=data DEVICE=cuda DISK_STREAM=1 CORPUS_CAP=100000000000 \
STREAM_LEN=$SL D_MODEL=$D WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100 GROW_BURST=12 \
ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MEM_CAP=200000 MEM_QUOTA=${MEM_QUOTA:-3125} \
CKPT_EVERY=2000 PROFILE=0 RATE_EVERY=1000"

go () {   # go <label> <extra env...>
  local L="$1"; shift
  echo "=== $L"
  env $COMMON "$@" SAVE_CKPT="$OUT/$L/ck.pt" python3 self_organize.py > "$OUT/$L.log" 2>&1
  local rc=$?
  printf "  exit %s | %s\n" "$rc" "$(grep -ac Traceback "$OUT/$L.log" | sed 's/^/tracebacks /')"
  grep -a -E "!! CONFIG WARNING|!! ENCODER COLLAPSE|SEGMENT/WINDOW" "$OUT/$L.log" | cut -c1-150 | sed 's/^/  !! /'
  for k in "order-1 .* THIS MODEL" "beats order-1|DOES NOT BEAT" "model ALONE .*model\+MEMORY .*ceiling" \
           "mean drift" "fabric \+[0-9.]+" "own vs global" "SELF-ASSEMBLED [0-9]+ LIVE"; do
    grep -a -oE "$k.*" "$OUT/$L.log" | head -1 | cut -c1-130 | sed 's/^/    /'
  done
  echo
}

if [ "$WHICH" = smoke ]; then
  # Same FLAGS as the real grid, tiny everything else. Asserts only "it reaches the report without a traceback" --
  # the numbers here are meaningless at 40 KB and are deliberately not printed, so nobody reads them as results.
  # SIZED FROM A MEASUREMENT, NOT A GUESS. At the first cut (40 KB, forced CPU) one arm cost 51 s and the grid cost
  # more than the 4 MB GPU grid it was protecting -- a gate nobody would run. Splitting the cost: BENCH=1 (skip the
  # eval battery) took an arm from 51 s to 19 s, so two thirds is the report. The report STAYS: the sig_tokens bug
  # crashed there and BENCH=1 would have passed it. Shrink the stream instead, and use the GPU if there is one.
  SMDEV=${DEVICE:-$(python3 -c "import torch;print('cuda' if torch.cuda.is_available() else 'cpu')" 2>/dev/null || echo cpu)}
  TINY="DATA_MODE=real DATA_DIR=data DOMAINS=eng,py,num,c STREAM_LEN=${SMOKE_LEN:-12000} D_MODEL=64 WIN=64 BATCH_W=4 \
DEVICE=$SMDEV MANAGE_EVERY=20 DOM_MANAGE_EVERY=20 ENC_WARMUP=50 ENC_WARMUP_MIN=20 SAVE_CKPT=0 \
COH_N=2 COH_LEN=96"
  # vocab_growth is the arm that would have caught the signature-width regression: it grows the vocabulary and
  # re-keys repeatedly inside one short run. Every other arm runs 12 kB, where the vocabulary barely moves, the
  # stride stays put, and asm.wins never holds two widths -- so the gate passed a change that killed BOTH pilot
  # arms at their first rekey. A gate only covers what it exercises.
  # COH_N/COH_LEN pinned DOWN here on purpose. The real defaults (16 x 384) are 32 autoregressive generations per
  # arm; dropping them into the gate took an arm from 25 s to 3.3 min and blew the grid straight back past the run
  # it protects. The gate asks "does this arm reach the report", which 2 short continuations answer as well as 32.
  # Resolution is the MEASUREMENT's job, and the measurement runs on the GPU.
  echo "smoke: 11 arms on $SMDEV, ${SMOKE_LEN:-12000} B each. Asserting only that every arm REACHES THE REPORT."
  bad=0
  for arm in "full:" "no_fabric:FABRIC=0" "no_world:WORLD_MODEL=0" "no_perexp:MEM_PER_EXPERT=0" \
             "no_tok:TOKENIZER=0" "no_domains:SELF_ORG=0" "no_phased:PHASED=0" "no_experts:EXPERTS=0" \
             "no_manage:MANAGE=0" "sig_tokens:SIG_SPACE=tokens" \
             "vocab_growth:VMAX=1024 GROW_EVERY=20 GROW_BURST=8 REKEY_EVERY=200 STREAM_LEN=200000"; do
    L=${arm%%:*}; E=${arm#*:}
    env $TINY $E python3 self_organize.py > "$OUT/smoke_$L.log" 2>&1
    rc=$?; tb=$(grep -ac Traceback "$OUT/smoke_$L.log")
    [ "$rc" = 0 ] && [ "$tb" = 0 ] || { bad=1; printf "  FAIL %-12s exit %s | %s tracebacks\n" "$L" "$rc" "$tb"
      grep -a -A4 Traceback "$OUT/smoke_$L.log" | tail -4 | sed 's/^/       /'; }
    [ "$rc" = 0 ] && [ "$tb" = 0 ] && printf "  ok   %s\n" "$L"
  done
  echo; [ $bad = 0 ] && echo "all arms run. safe to spend the GPU." || echo "FIX THE ABOVE before launching the real grid."
  exit $bad
fi

case "$WHICH" in
  all|mix) go mix_4corpora DOMAINS=eng,py,num,c SEG_MIN=8000 SEG_MAX=20000 ;;
esac
case "$WHICH" in
  # SEG_MIN/SEG_MAX matter on ONE corpus too, and the first rerun missed it. seg_from() draws each segment from a
  # RANDOM OFFSET in the corpus, so at the 700/1800 default the English stream jumps somewhere else in English every
  # ~1250 bytes = 3.3 analysis windows. That is a stream of discontinuities, not a stream of English, and the 71
  # domains it assembled are partly a count of the splices we introduced. Same widening as the 4-corpus arm.
  all|eng) go eng_only DOMAINS=eng SEG_MIN=8000 SEG_MAX=20000 ;;
esac
case "$WHICH" in
  all|ablate)
    # WHAT IS EACH SUBSYSTEM WORTH? One off at a time against the full stack, on the 4-corpus stream. This is the
    # measurement that could not exist while they were all off, and it is the honest way to justify each default.
    go ab_full        DOMAINS=eng,py,num,c SEG_MIN=8000 SEG_MAX=20000
    go ab_no_fabric   DOMAINS=eng,py,num,c SEG_MIN=8000 SEG_MAX=20000 FABRIC=0
    go ab_no_world    DOMAINS=eng,py,num,c SEG_MIN=8000 SEG_MAX=20000 WORLD_MODEL=0
    go ab_no_perexp   DOMAINS=eng,py,num,c SEG_MIN=8000 SEG_MAX=20000 MEM_PER_EXPERT=0
    go ab_no_tok      DOMAINS=eng,py,num,c SEG_MIN=8000 SEG_MAX=20000 TOKENIZER=0
    go ab_no_domains  DOMAINS=eng,py,num,c SEG_MIN=8000 SEG_MAX=20000 SELF_ORG=0
    ;;
esac

# THE ONE TABLE THAT MATTERS. Each arm's report carries its own caveat that "model ALONE" is an eval-time KNOCKOUT
# of a component the model TRAINED WITH, so it overstates. The honest comparison is across arms: this run's
# "+FABRIC+MEMORY" against the FABRIC=0 run's "model+MEMORY". Print it, because reading it off six logs by hand is
# how a knockout number got used to justify a default in the first place.
if [ -n "$(ls "$OUT"/ab_*.log 2>/dev/null)" ]; then
  echo "=== ABLATION TABLE (bits/byte on held-out text, lower=better; order-1 is the same-text anchor) ==="
  printf "  %-14s %8s %8s %8s   %s\n" arm order-1 MODEL "+mem" "domains / notes"
  for f in "$OUT"/ab_*.log; do
    L=$(basename "$f" .log)
    a1=$(grep -a -oE "order-1 [0-9.]+" "$f" | head -1 | awk '{print $2}')
    mm=$(grep -a -oE "THIS MODEL [0-9.]+" "$f" | head -1 | awk '{print $3}')
    # ANCHOR ON "FABRIC + MEMORY". Matching bare "MEMORY [0-9.]+" also hits the COHERENCE line's "model+MEMORY 0.50",
    # and `tail -1` then picked whichever came last in that arm's log -- so the first table printed 0.50 (a coherence
    # FRACTION) for five arms and 2.618 (bits/byte) for the sixth, in one column, with no units. Two different
    # quantities under one heading is worse than a missing column.
    fm=$(grep -a -oE "FABRIC \+ MEMORY [0-9.]+" "$f" | tail -1 | awk '{print $4}')
    nd=$(grep -a -oE "SELF-ASSEMBLED [0-9]+ LIVE" "$f" | head -1 | awk '{print $2}')
    printf "  %-14s %8s %8s %8s   %s\n" "${L#ab_}" "${a1:--}" "${mm:--}" "${fm:--}" "${nd:--} domains"
  done
  echo "  read DOWN the MODEL column against ab_full. A subsystem that moves it by less than the run-to-run"
  echo "  spread is not paying for itself on bits/byte -- check COHERENCE and RETENTION in its log before"
  echo "  concluding it does nothing, since those are what the fabric and memory actually moved."
  echo
fi
echo "logs + checkpoints under $OUT"
echo
echo "next, on whichever checkpoint you want to interrogate:"
echo "  python3 probe_ckpt_geometry.py CKPT=$OUT/mix_4corpora/ck.pt N=512   # is the encoder separating kinds?"
echo "  python3 prompt.py CKPT=$OUT/eng_only/ck.pt                          # read what it generates"
