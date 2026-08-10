#!/usr/bin/env bash
# ---------------------------------------------------------------------------------------------------------------
# equiv.sh -- did a code change alter what the model DOES?
#
#   bash equiv.sh <ref>              # compare HEAD against <ref>, e.g.  bash equiv.sh c14f876
#   bash equiv.sh <ref> <ref2>       # compare two arbitrary commits
#   SCALE=deep bash equiv.sh <ref>   # slower, reaches more code paths (see SCALE below)
#
# WHY THIS EXISTS. `rerun.sh smoke` asserts every arm REACHES THE REPORT -- it catches crashes, not changes. To
# claim a refactor is inert you have to show the numbers are the SAME, and the three one-off command lines I
# improvised to do that were all broken in the same way: they depended on a shell variable still being set, or
# wrote their output INSIDE a git worktree that the next line then deleted. So this is a script, it derives every
# path from its own location rather than from $(pwd), it creates and checks the output directory BEFORE running
# anything, and it never removes a worktree until the logs are safely outside it.
#
# WHAT IT COMPARES. Both commits run the SAME config, SAME seed, SAME corpus, on the same machine, one after the
# other. Training is deterministic given (config, commit, seed) -- measured, three runs byte-identical -- so if
# the change is inert every number in both reports must match exactly. Volatile lines (wall-clock, rates, pids,
# paths) are stripped before the diff; everything else must be identical.
#
# WHAT THE SCALES REACH. The smoke gate runs 12 kB, which never exercises the paths a real run spends its time
# in. These configs force those paths quickly instead of waiting for them:
#   fast (default)  ~2-4 min/side.  Vocabulary is driven to its cap (GROW_EVERY=20, GROW_BURST=8, VMAX=1024),
#                   the fabric is driven to ITS cap (FAB_NMAX=64), retokenisation fires (RETOK_EVERY=300), and
#                   EPOCHS=3 forces two epoch RESAMPLES. Small model so it runs anywhere, including CPU.
#   deep            ~15-25 min/side. Same paths at pilot width (D_MODEL=768, FAB_NMAX=512) -- use when `fast`
#                   says identical but the change touched something width- or population-dependent.
# A pass at `fast` is strong evidence, not proof: it is a small model, and only a full pilot exercises the
# fabric's growth ramp over thousands of experts. It is the cheapest thing that can FALSIFY inertness.
set -u

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)          # this repo, however it was invoked
[ -d "$ROOT/.git" ] || { echo "!! $ROOT is not a git repo"; exit 1; }

A=${1:-}; B=${2:-HEAD}
[ -n "$A" ] || { echo "usage: bash equiv.sh <ref> [ref2]   (compares <ref> against ${2:-HEAD})"; exit 1; }
for r in "$A" "$B"; do
  git -C "$ROOT" rev-parse --verify -q "$r^{commit}" >/dev/null || { echo "!! not a commit: $r"; exit 1; }
done
SA=$(git -C "$ROOT" rev-parse --short "$A"); SB=$(git -C "$ROOT" rev-parse --short "$B")
# SAME COMMIT TWICE = A DETERMINISM SELF-TEST, not an error. This matters before trusting any verdict on GPU:
# the comparison assumes a run is a function of (config, commit, seed), and cuDNN's GRU backward plus atomic
# scatters are not bit-reproducible in general. If the machine is nondeterministic, equiv reports DIFFERS for
# two commits that are actually identical -- so run this first on any new device and believe nothing until it
# comes back IDENTICAL.
SELFTEST=0
if [ "$SA" = "$SB" ]; then SELFTEST=1; echo "SELF-TEST: same commit twice -- asking whether THIS MACHINE is deterministic."; fi

DEV=${DEVICE:-$(python3 -c "import torch;print('cuda' if torch.cuda.is_available() else 'cpu')" 2>/dev/null || echo cpu)}
case "${SCALE:-fast}" in
  fast) CFG="D_MODEL=96 WIN=64 BATCH_W=4 STREAM_LEN=${LEN:-120000} EPOCHS=3 \
             VMAX=1024 SEED_VOCAB=256 GROW_EVERY=20 GROW_BURST=8 RETOK_EVERY=300 \
             FAB_NMAX=64 FAB_N0=3 MEM_CAP=20000 MEM_QUOTA=300 \
             MANAGE_EVERY=50 DOM_MANAGE_EVERY=50 ENC_WARMUP=100 ENC_WARMUP_MIN=40 \
             SIG_WIN=128 RATE_EVERY=500 GEN_LEN=40 GEN_N=2 EVAL_N=8 COH_N=4 COH_LEN=64 HOLDOUT_N=8" ;;
  deep) CFG="D_MODEL=768 WIN=256 BATCH_W=16 STREAM_LEN=${LEN:-1000000} EPOCHS=3 \
             VMAX=2048 GROW_EVERY=100 GROW_BURST=12 RETOK_EVERY=1500 \
             FAB_NMAX=512 FAB_N0=3 MEM_CAP=100000 MEM_QUOTA=1500 \
             SIG_WIN=614 ENC_WARMUP=1000 ENC_WARMUP_MIN=400 RATE_EVERY=2000" ;;
  *) echo "!! SCALE must be fast or deep"; exit 1 ;;
esac
# Constant across both sides. SAVE_CKPT=0 on purpose: checkpointing gates extra holdout_bpb passes, which is a
# real behavioural difference and would be comparing two things at once.
PDIR=${PILOT_DIR:-$ROOT/data_pilot}
COMMON="DATA_MODE=real DATA_DIR=$PDIR DOMAINS=eng DISK_STREAM=1 CORPUS_CAP=100000000000 \
        MODEL=gru LAYERS=1 DEVICE=$DEV SEED=${SEED:-0} SAVE_CKPT=0 PROBE_WAIT=0 PROFILE=0 CKPT_EVERY=0"

OUT=$ROOT/runs/equiv_${SA}_vs_${SB}
mkdir -p "$OUT" || { echo "!! cannot create $OUT"; exit 1; }
[ -w "$OUT" ] || { echo "!! $OUT is not writable"; exit 1; }
echo "equiv: $SA  vs  $SB   | scale=${SCALE:-fast} device=$DEV seed=${SEED:-0}"
echo "  output -> $OUT      (created and writable; nothing here is inside a worktree)"

if [ "$(cat "$PDIR/train/eng"/part*.txt 2>/dev/null | wc -c)" -lt 50000 ]; then
  echo "!! $PDIR/train/eng has under 50 kB of text -- not enough to run. Pull it first:"
  echo "   python3 fetch_big.py --dataset fineweb-edu --domain eng --gb 0.06 --out $PDIR --resume"
  exit 1
fi

# THE COMPLETION MARKER MUST BE THE LAST LINE A RUN PRINTS, NOT ANY LINE. This first matched
# "SIG_MODE=learned", which is on line 8 of EVERY log ("self-organize | ... | SIG_MODE=learned | data real").
# So a run that died at startup counted as having reached the report, and a partial log counted as "already
# done, reusing" and was never re-run. Either yields a verdict from logs that were never comparable. Use the
# full sentence -- the same one longrun.sh's _done() uses.
run_side() {                                              # run_side <sha> <logfile>
  _sha=$1; _log=$2
  if [ -s "$_log" ] && grep -aq "SIG_MODE=learned -- learned = the unfrozen product path" "$_log"; then echo "  $_sha: already done, reusing"; return 0; fi
  _wt=$(mktemp -d "/tmp/equiv_${_sha}_XXXX")
  git -C "$ROOT" worktree add -q --detach "$_wt" "$_sha" || { echo "  !! worktree failed for $_sha"; return 1; }
  echo "  $_sha: running in $_wt"
  ( cd "$_wt" && env $COMMON $CFG python3 self_organize.py ) > "$_log" 2>&1
  _rc=$?
  # The log lives in $OUT, never in $_wt, so removing the worktree cannot destroy the result.
  git -C "$ROOT" worktree remove --force "$_wt" 2>/dev/null
  if [ "$_rc" != 0 ] || ! grep -aq "SIG_MODE=learned -- learned = the unfrozen product path" "$_log"; then
    echo "  !! $_sha did not reach the report (rc=$_rc). Last lines:"; tail -6 "$_log" | sed 's/^/       /'; return 1
  fi
  echo "  $_sha: reached the report"
}

LA=$OUT/$SA.log; LB=$OUT/$SB.log
[ "$SELFTEST" = 1 ] && { LA=$OUT/${SA}_run1.log; LB=$OUT/${SB}_run2.log; }
run_side "$SA" "$LA" || exit 1
run_side "$SB" "$LB" || exit 1

# Strip only what genuinely varies between two runs of the same code: wall-clock, throughput, pids, temp paths,
# and the build banner (which names the commit, and so differs BY CONSTRUCTION).
_norm() { grep -av -E '\[rate @|elapsed|steps/min|kB/s|GB of text|\[pid |ms/step|\[build\]|h left|checkpoint-on-demand|/tmp/equiv_' "$1"; }
_norm "$LA" > "$OUT/a.norm"; _norm "$LB" > "$OUT/b.norm"

# KNOWN-NOISY LINES. Training is bit-reproducible on the GPUs measured, but the MEMORY store's retrieval is
# not -- a self-test on CUDA differs on 'model + MEMORY', 'flagged N implausible' and the figures derived from
# them, while every model-only and model+fabric number matches exactly. A comparison that just says DIFFERS
# because of that is useless. So: the self-test WRITES the set of line-patterns that vary run-to-run on this
# machine, and a later comparison SUBTRACTS them and judges on what is left.
NOISE=$ROOT/runs/equiv_noise_${DEV}.txt
if [ "$SELFTEST" = 1 ]; then
  diff "$OUT/a.norm" "$OUT/b.norm" | grep '^[<>]' | sed 's/^[<>] //' | sed -E 's/[0-9]+\.[0-9]+/NUM/g; s/[0-9]+/N/g' \
    | sort -u > "$NOISE"
  echo "  noise baseline for $DEV written: $(wc -l < "$NOISE") pattern(s) -> $NOISE"
fi
_strip_noise() {                                          # drop diff lines whose shape matches the baseline
  if [ -s "$NOISE" ]; then
    diff "$OUT/a.norm" "$OUT/b.norm" | grep '^[<>]' | sed 's/^[<>] //' \
      | sed -E 's/[0-9]+\.[0-9]+/NUM/g; s/[0-9]+/N/g' | sort -u | comm -23 - "$NOISE"
  else
    diff "$OUT/a.norm" "$OUT/b.norm" | grep '^[<>]' | sed 's/^[<>] //' | sort -u
  fi
}
echo
if diff -q "$OUT/a.norm" "$OUT/b.norm" >/dev/null; then
  echo "  ================================================================"
  echo "   IDENTICAL -- every number in both reports matches."
  if [ "$SELFTEST" = 1 ]; then
    echo "   This machine is DETERMINISTIC at scale=${SCALE:-fast}. Verdicts from equiv.sh can be trusted here."
  else
    echo "   $SB is behaviourally inert with respect to $SA at scale=${SCALE:-fast}."
  fi
  echo ""
  echo "  ================================================================"
  echo "   Caveat worth keeping: this is a small model. If the change touched anything"
  echo "   width- or population-dependent, confirm with SCALE=deep before trusting it."
  exit 0
else
  _n=$(diff "$OUT/a.norm" "$OUT/b.norm" | grep -c '^[<>]')
  _real=$(_strip_noise | grep -c . || true)
  if [ "$SELFTEST" != 1 ] && [ -s "$NOISE" ] && [ "$_real" = 0 ]; then
    echo "  ================================================================"
    echo "   INERT -- $_n lines differ, but every one of them matches a pattern this machine varies on"
    echo "   run-to-run (see $NOISE, written by 'equiv.sh HEAD HEAD')."
    echo "   $SB is behaviourally inert with respect to $SA at scale=${SCALE:-fast}."
    echo "  ================================================================"
    diff "$OUT/a.norm" "$OUT/b.norm" | head -12 | sed 's/^/     /'
    exit 0
  fi
  echo "  ================================================================"
  echo "   DIFFERS -- $_n changed lines."
  if [ "$SELFTEST" = 1 ]; then
    echo "   THIS MACHINE IS NOT DETERMINISTIC. Two runs of the SAME commit disagree, so a DIFFERS verdict"
    echo "   between two different commits would prove nothing here. Fix this before trusting any comparison."
  else
    echo "   $SB is NOT inert with respect to $SA."
  fi
  echo "  ================================================================"
  echo "   first differences:"
  diff "$OUT/a.norm" "$OUT/b.norm" | head -24 | sed 's/^/     /'
  echo
  echo "   full logs:  $LA   $LB"
  echo "   full diff:  diff $OUT/a.norm $OUT/b.norm"
  exit 2
fi
