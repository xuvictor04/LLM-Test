#!/usr/bin/env bash
# === DO THE INSTRUMENTS STILL WORK? ==============================================================================
#
# Three measurement tools were built to stop this project drawing conclusions from things that never happened:
#
#   1  DID IT FIRE        an end-of-run table naming every ARMED mechanism that did nothing. Built because
#                         FAB_RESCUE fired zero times for a whole investigation, maybe_deepen was never called in
#                         a real run, and TOK_ANCHOR's loss term has never once entered the loss.
#   2  FORGOTTEN/EVICTED  the retention probe re-scored WITH and WITHOUT memory, plus BWT and the forgetting
#                         measure. Built because the boundary number was weights-only, so a domain whose memory
#                         was deleted scored the same as one whose weights degraded.
#   3  compare.py         P(A>B) with a bootstrap CI, paired by seed. Built because every architecture claim here
#                         was made by comparing two numbers against a seed spread larger than the effect.
#
# All three are themselves code that can silently stop working -- which is precisely the failure they exist to
# catch, and the DID IT FIRE report has already died on its own NameError once and printed nothing but that.
# So they get a test. Run it after any change to the report sections, the memory store, or compare.py.
#
#   bash selftest.sh            full: unit tests + a real train + a real resume   (~10 min on CPU)
#   bash selftest.sh --quick    unit tests only, no training                      (seconds)
#
set -u
QUICK=0; [ "${1:-}" = "--quick" ] && QUICK=1
FAIL=0
OUT=${SELFTEST_DIR:-$(mktemp -d -t selftest-XXXXXX)}
mkdir -p "$OUT"
echo "selftest: artefacts under $OUT"

_ck() {  # _ck <label> <file> <pattern...>   every pattern must appear
  local label=$1 file=$2; shift 2
  for pat in "$@"; do
    if ! grep -aqF -- "$pat" "$file"; then
      echo "  FAIL  $label -- expected to find: $pat"; FAIL=1; return
    fi
  done
  echo "  ok    $label"
}
_nck() {  # _nck <label> <file> <pattern>    the pattern must NOT appear
  local label=$1 file=$2 pat=$3
  if grep -aqF -- "$pat" "$file"; then
    echo "  FAIL  $label -- found what must not be there: $pat"; FAIL=1
  else
    echo "  ok    $label"
  fi
}

echo; echo "--- unit tests -------------------------------------------------------------------"
python3 mem_evict_test.py > "$OUT/evict.txt" 2>&1 && echo "  ok    mem_evict_test (eviction clock + per-source floor)" \
  || { echo "  FAIL  mem_evict_test:"; sed 's/^/          /' "$OUT/evict.txt"; FAIL=1; }
python3 compare_test.py  > "$OUT/cmp.txt"   2>&1 && echo "  ok    compare_test (known-answer decision rule)" \
  || { echo "  FAIL  compare_test:"; sed 's/^/          /' "$OUT/cmp.txt"; FAIL=1; }
python3 growth_test.py   > "$OUT/grow.txt"  2>&1 && echo "  ok    growth_test (a new area reaches the REGRESSION trigger)" \
  || { echo "  FAIL  growth_test:"; sed 's/^/          /' "$OUT/grow.txt"; FAIL=1; }
python3 proj_test.py     > "$OUT/proj.txt"  2>&1 && echo "  ok    proj_test (the LR horizon knows how long the run is)" \
  || { echo "  FAIL  proj_test:"; sed 's/^/          /' "$OUT/proj.txt"; FAIL=1; }
python3 cap_test.py      > "$OUT/cap.txt"   2>&1 && echo "  ok    cap_test (one earned lift means the same at every cap size)" \
  || { echo "  FAIL  cap_test:"; sed 's/^/          /' "$OUT/cap.txt"; FAIL=1; }
python3 ramp_test.py     > "$OUT/ramp.txt"  2>&1 && echo "  ok    ramp_test (the capacity valve does not disarm the population ramp)" \
  || { echo "  FAIL  ramp_test:"; sed 's/^/          /' "$OUT/ramp.txt"; FAIL=1; }
python3 lr_test.py       > "$OUT/lr.txt"    2>&1 && echo "  ok    lr_test (the LR schedule means the same thing at every corpus size)" \
  || { echo "  FAIL  lr_test:"; sed 's/^/          /' "$OUT/lr.txt"; FAIL=1; }
python3 blowup_test.py   > "$OUT/blow.txt"  2>&1 && echo "  ok    blowup_test (the divergence alarm fires on divergence and not on wander)" \
  || { echo "  FAIL  blowup_test:"; sed 's/^/          /' "$OUT/blow.txt"; FAIL=1; }
python3 curve_test.py    > "$OUT/curve.txt" 2>&1 && echo "  ok    curve_test (end-of-run verdict, BWT sign, cull gate)" \
  || { echo "  FAIL  curve_test:"; sed 's/^/          /' "$OUT/curve.txt"; FAIL=1; }
python3 notes_check.py   > "$OUT/notes.txt" 2>&1 && echo "  ok    notes_check (no note states a default the code contradicts)" \
  || { echo "  FAIL  notes_check:"; tail -20 "$OUT/notes.txt" | sed 's/^/          /'; FAIL=1; }
python3 tok_test.py      > "$OUT/tok.txt"    2>&1 && echo "  ok    tok_test (minting reaches the cap; a rejected candidate is not an exhausted vocabulary)" \
  || { echo "  FAIL  tok_test:"; grep -a FAIL "$OUT/tok.txt" | sed 's/^/          /'; FAIL=1; }
# A TEST NOBODY RUNS IS A TEST THAT DOES NOT EXIST. These two were written alongside the resume and corpus
# work and never wired in here, so the project's own entry point -- the thing anyone runs before a launch --
# was silently skipping 120-odd checks covering every path a continual-learning run takes: the fabric and
# vocabulary widening, the geometry refusals, the restored-vs-new expert split, the growth controller's state,
# the cull budget, the exposure guards, the DN/CORP realignment, and the ACCUM gate. They pass; that was never
# the issue. Nothing was asking them.
python3 corpus_test.py   > "$OUT/corpus.txt" 2>&1 && echo "  ok    corpus_test (a dropped corpus takes its name with it; per-corpus exposure)" \
  || { echo "  FAIL  corpus_test:"; grep -a FAIL "$OUT/corpus.txt" | sed 's/^/          /'; FAIL=1; }
python3 resume_test.py   > "$OUT/resume.txt" 2>&1 && echo "  ok    resume_test (widening, the newborn split, the growth controller, ACCUM, the cull budget)" \
  || { echo "  FAIL  resume_test:"; grep -a FAIL "$OUT/resume.txt" | sed 's/^/          /'; FAIL=1; }
bash harness_test.sh     > "$OUT/harness.txt" 2>&1 && echo "  ok    harness_test (arm resolution + the append-only guarantee)" \
  || { echo "  FAIL  harness_test:"; grep -a FAIL "$OUT/harness.txt" | sed 's/^/          /'; FAIL=1; }
# WHAT THIS FILE DELIBERATELY DOES NOT RUN, said here so the omission is a decision and not an oversight --
# which is how corpus_test and resume_test came to be missing from it for a whole session:
#   run_verify_test.py     a full training run at STREAM_LEN=6,000,000 with VERIFY=recon, comparing the
#                          reconstruction gate against the old self-consistency one. selftest already does one
#                          end-to-end run below; a second heavyweight one does not belong in a fast gate.
#                          Its own docstring gives the CPU smoke form:
#                            DEVICE=cpu STREAM_LEN=4000 D_MODEL=32 WIN=16 ENC_WARMUP=60 FABRIC=0 \
#                              TOKENIZER=0 PROBE=0 python3 run_verify_test.py
#   verify_console_test.py the same A/B, self-contained, needing only torch and data/train/{eng,py,num,c}.
# Both are A/B experiments rather than regression tests: they answer "which gate is better", not "did this
# still work". Run them when that question is live, not before every launch.
python3 levers.py > "$OUT/levers.txt" 2>&1 && echo "  ok    levers (every knob declared and read consistently)" \
  || { echo "  FAIL  levers:"; tail -5 "$OUT/levers.txt" | sed 's/^/          /'; FAIL=1; }

if [ "$QUICK" = 1 ]; then
  echo; [ "$FAIL" = 0 ] && echo "quick selftest passed (training not exercised)" || echo "!! quick selftest FAILED"
  exit $FAIL
fi

# CPU UNLESS DELIBERATELY TOLD OTHERWISE, and it must NOT read $DEVICE. This ran DEVICE=${DEVICE:-cpu}, which
# inherits an ambient DEVICE=cuda -- and longrun.sh sets exactly that, so anyone with it exported who ran the
# test suite on the GPU box would have quietly put a training job on the GPU alongside an 18-epoch run. The
# suite exists to be run often and at any time; that is only safe if running it cannot cost anything. Opting in
# takes a variable nothing else sets.
ST_DEV=${SELFTEST_DEVICE:-cpu}
echo "selftest: training on $ST_DEV (set SELFTEST_DEVICE=cuda to override; \$DEVICE is deliberately ignored)"

# A REAL RUN, NOT A MOCK. The reports being tested read live state off fab/mem/asm/TOK, so a stub would test the
# stub. Deliberately tiny -- this asserts the instruments produce their sections and are self-consistent, NOT
# that the numbers are any good. At this size they are noise.
COMMON="DATA_MODE=real DATA_DIR=${SELFTEST_DATA:-data} DOMAINS=eng DISK_STREAM=1 CORPUS_CAP=100000000000 \
MODEL=gru LAYERS=1 DEVICE=$ST_DEV PROBE_WAIT=0 PROFILE=0 CKPT_EVERY=0 D_MODEL=48 WIN=32 BATCH_W=4 \
STREAM_LEN=9000 EPOCHS=2 VMAX=320 SEED_VOCAB=256 GROW_EVERY=20 GROW_BURST=8 RETOK_EVERY=200 FABRIC=1 \
FAB_NMAX=8 FAB_N0=4 MEM_CAP=1500 MANAGE_EVERY=50 DOM_MANAGE_EVERY=50 ENC_WARMUP=30 ENC_WARMUP_MIN=15 \
SIG_WIN=64 RATE_EVERY=400 GEN_LEN=12 GEN_N=1 EVAL_N=2 COH_N=1 COH_LEN=24 HOLDOUT_N=4"

echo; echo "--- end to end: a fresh run ------------------------------------------------------"
# shellcheck disable=SC2086
env $COMMON SEED=0 SAVE_CKPT="$OUT/ck" TOKENIZER_PATH="$OUT/t.json" \
    python3 self_organize.py > "$OUT/fresh.log" 2>&1
RC=$?
[ "$RC" = 0 ] || { echo "  FAIL  the run itself exited $RC:"; tail -6 "$OUT/fresh.log" | sed 's/^/          /'; FAIL=1; }

_ck  "1  DID IT FIRE section present"     "$OUT/fresh.log" "=== DID IT FIRE?"
_nck "1  the audit did not die on itself" "$OUT/fresh.log" "[did-it-fire] report FAILED"
_nck "1  no mechanism left uncountable"   "$OUT/fresh.log" "NO COUNTER -- cannot say"
_ck  "1  it reports both states"          "$OUT/fresh.log" "  fired   " "  off     "
_ck  "2  forgotten/evicted decomposition" "$OUT/fresh.log" "forgotten, or evicted?" "weights-only" "+ memory"
_ck  "2  per-source occupancy reported"   "$OUT/fresh.log" "memory per source id now:"
_ck  "memory floor is live"               "$OUT/fresh.log" "src floor 0.5"
_ck  "read probe is live"                 "$OUT/fresh.log" "read probe"
_ck  "run reached its report"             "$OUT/fresh.log" "held-out"

echo; echo "--- end to end: a resume, where retention is measurable --------------------------"
# shellcheck disable=SC2086
env $COMMON SEED=1 RESUME="$OUT/ck" SAVE_CKPT=0 TOKENIZER_PATH="$OUT/t.json" \
    python3 self_organize.py > "$OUT/resume.log" 2>&1
RC=$?
[ "$RC" = 0 ] || { echo "  FAIL  the resume exited $RC:"; tail -6 "$OUT/resume.log" | sed 's/^/          /'; FAIL=1; }

_ck  "2  boundary probe spans the resume" "$OUT/resume.log" "ACROSS THE RUN BOUNDARY" "before this run"
_ck  "2  BWT and F reported"              "$OUT/resume.log" "BWT " "forgetting measure F"
_ck  "2  BWT sign is stated"              "$OUT/resume.log" "negative = old domains IMPROVED"
# ASSERT THE SUCCESS, NOT THE WARNING. The first version looked for the "had no recorded USE-age" line, which
# only prints when the checkpoint FAILED to carry it -- so a clean resume failed the test and a broken one would
# have passed it. Check instead that the resume happened and that the backfill warning is absent.
_ck  "resume actually resumed"            "$OUT/resume.log" "[RESUME]"
_nck "use-age survived the checkpoint"    "$OUT/resume.log" "had no recorded USE-age"
_nck "1  audit still alive after resume"  "$OUT/resume.log" "[did-it-fire] report FAILED"

echo; echo "--- 3  compare.py on the two real logs it will actually be given -----------------"
# They differ by SEED, not by an arm, so there is nothing to find -- which makes NOT SIGNIFICANT the right
# answer and a useful end-to-end check that the parser reads real logs rather than only synthetic ones.
cp "$OUT/fresh.log" "$OUT/x_A_seed0.log"; cp "$OUT/resume.log" "$OUT/x_B_seed1.log"
python3 compare.py "$OUT/x_A_seed0.log" -- "$OUT/x_B_seed1.log" > "$OUT/cmp_real.txt" 2>&1
_ck "3  parses real logs and reports"     "$OUT/cmp_real.txt" "P(A better)"

echo
if [ "$FAIL" = 0 ]; then echo "selftest passed -- all three instruments report and are self-consistent."
else echo "!! selftest FAILED -- see $OUT"; fi
exit $FAIL
