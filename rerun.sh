#!/usr/bin/env bash
# ---------------------------------------------------------------------------------------------------------------
# rerun.sh -- the reruns that became necessary when the audit found six subsystems defaulting OFF.
#
# Every result this project produced before commit 51889b7 was measured on the base LM + memory + domains, with
# the routed expert population, the expanding tokenizer, the world model and the per-expert memory partition all
# absent. FABRIC alone is worth +0.709 bits/byte and flips English from LOSING to order-1 to beating it, so those
# results describe a different system. This re-measures on the whole one.
#
#   bash rerun.sh            # all of it (~15 min on a GH200)
#   bash rerun.sh mix        # just the 4-corpus run
#   bash rerun.sh eng        # just the single-corpus run
#   bash rerun.sh ablate     # what each subsystem is worth, one at a time
#
# READ IN THIS ORDER. The first two speak to proper language; the rest explain why they moved.
#   ANCHORS          does the model beat order-1 on the same held-out text? the only unmoored-number check
#   COHERENCE        does a continuation stay in its seed's domain? floor = chance, ceiling = real text
#   RETENTION        is what it saw first still modelled as well as what it saw last?
#   LEARNING CURVE   how fast it picks a process up, and what happens once that process leaves
#   FABRIC           what the routed population contributes, and whether the router HALTs instead of routing
#   CAN A DOMAIN PREDICT   own-domain prior vs a global one AND vs a wrong one
# Domain counts, purity, silhouette and V-measure are DIAGNOSTICS. They explain movement in the above; they are
# not targets, and steering by them is what produced most of this file's history.
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
ENC_WARMUP=2000 ENC_WARMUP_MIN=500 MAX_DOMAINS=1000000 MEM_CAP=200000 MEM_QUOTA=${MEM_QUOTA:-3125} \
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

case "$WHICH" in
  all|mix) go mix_4corpora DOMAINS=eng,py,num,c SEG_MIN=8000 SEG_MAX=20000 ;;
esac
case "$WHICH" in
  all|eng) go eng_only DOMAINS=eng ;;
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

echo "logs + checkpoints under $OUT"
echo
echo "next, on whichever checkpoint you want to interrogate:"
echo "  python3 probe_ckpt_geometry.py CKPT=$OUT/mix_4corpora/ck.pt N=512   # is the encoder separating kinds?"
echo "  python3 prompt.py CKPT=$OUT/eng_only/ck.pt                          # read what it generates"
