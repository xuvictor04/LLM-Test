#!/bin/bash
# =============================================================================================
#  DOMAIN-ASSEMBLY SWEEP -- ENC_POS_MAX x ENC_WARMUP x NEW_DIST, WITH THE CAP HELD OPEN
#
#      bash sweep_domain_grid.sh            # ~30 min on a GH200 at JOBS=6
#      cat sweep_out/SUMMARY.md             # <- paste this back
#
#  Knobs:  JOBS=6  OUT=sweep_out  STAGES=A,B,C,D,E  STREAM_LEN=120000  MAX_MIN=180
#          KEY_SRC=model  BIG=auto  FORCE=0  DRY=1
# =============================================================================================
#
#  WHY THIS SWEEP EXISTS
#  ---------------------
#  The run under investigation ended at 64 live domains for 4 corpora with MAX_DOMAINS=64. That
#  coincidence is NOT evidence that the cap did the work. `s.capped` is incremented in
#  DomainAssembler._assign and then PRINTED BY NOTHING in the entire file -- so "the cap is
#  binding" has never been measured, only inferred from 64 == 64. Every cell below therefore runs
#  at MAX_DOMAINS=4096 so the cap CANNOT bind, and the patched copy prints `capped` so we can
#  prove it. A cell with capped>0 is VOID and is excluded from every conclusion.
#
#  AXES
#    ENC_POS_MAX  256 512 1024 2048  (2,4,8,16 x WIN). The splice segment is 700-1800 B, mean
#                                    1250, so at the default 256 the InfoNCE positive is drawn
#                                    from INSIDE the same 256 bytes and the encoder is trained to
#                                    call two distant windows of the SAME corpus dissimilar.
#                                    Only >=1024 gives it segment-scale invariance -- at the cost
#                                    of cross-domain positives (measured 9.8% -> 32.9% -> 52.9%).
#    ENC_WARMUP   0 800 3000         How much of that objective is applied before assembly runs.
#                                    The claim under test is that MORE training makes assembly
#                                    WORSE; this axis is what falsifies or confirms it.
#    NEW_DIST     0.35 0.50 0.65     SHIFT_DIST moves with it at the shipped ratio (0.30/0.35),
#                                    so the boundary detector is not left behind at a threshold
#                                    calibrated for a differently-scaled metric.
#
#  PRE-REGISTERED KILL CRITERIA  (fixed here BEFORE any run; sweep_domain_report.py scores them)
#    K1 CAP INVARIANCE. Stage A runs ONE config at MAX_DOMAINS = 8 / 64 / 4096. If live domains
#       move with the cap, the cap is the mechanism and the grid is measuring the wrong variable.
#       If they do not move (and capped==0), the cap is irrelevant -- and from then on "the number
#       went down" is inadmissible as evidence on its own.
#    K2 A CELL COUNTS ONLY IF capped == 0. Otherwise VOID.
#    K3 SUCCESS = completeness >= 0.80 AND V-measure >= 0.85 AND live in [4,8] for NP=4.
#       Purity and homogeneity are reported but are NOT admissible: both rise monotonically with
#       fragmentation (62 clusters / 4 classes scores homogeneity 1.00, completeness 0.34).
#    K4 BOUNDARY RECALL >= 0.85 is a HARD GATE on any cell claiming success. A cell can reach 4
#       domains by detecting almost no boundaries (measured: 15 found for ~96 true switches at
#       ENC_POS_MAX=8*WIN). That is a dead detector, not convergence. The found/true column and
#       this gate exist to stop that result being reported as a win.
#    K5 EXTENSIVITY. 64 was a truncated linear ramp (0.072 domains/step, still rising at the last
#       step), not a fixed point. Stage D re-runs the winner at STREAM_LEN 120k/240k/480k; live
#       domains must stay FLAT within +/-1. If the count scales with the stream, the population is
#       extensive in bytes consumed and nothing converged -- the run merely ended.
#    K6 BIGRAM CONTROL. SIG_MODE=bigram needs no training. If no learned cell beats it on
#       V-measure, the binding defect is the InfoNCE objective, not the thresholds, and tuning
#       ENC_POS_MAX/NEW_DIST is treating a symptom.
#
#  WHAT IS HELD FIXED, AND WHY (each would otherwise confound an axis)
#    MAX_DOMAINS=4096      the entire point (Stage A varies it deliberately).
#    DOM_ADAPTIVE=0        the shipped adaptive rule is thr = max(NEW_DIST, median + K*MAD): it can
#                          only RAISE the threshold, so with it on the NEW_DIST axis is partly
#                          shadowed and a null result on that axis would be uninterpretable.
#                          Stage C runs the A/B at the winner.
#    MANAGE_MERGE=0        0 makes manage() fall through to MERGE_FRAC*NEW_DIST, so the MERGE scale
#                          moves WITH the CREATE scale. The shipped default 0.12 is a constant
#                          unrelated to NEW_DIST; sweeping NEW_DIST against a frozen merge
#                          threshold would sweep two different definitions of "a domain" at once.
#                          Stage C runs the A/B (0 vs the shipped 0.12) at the winner.
#    ENC_WARMUP_MIN=1e9    disables the ADAPTIVE early stop inside the warmup loop, which
#                          otherwise silently truncates ENC_WARMUP>3000 on a separation plateau.
#                          Without this the ENC_WARMUP axis is not the axis you think it is.
#    D_MODEL=128, MEM_CAP=50000, EVAL_N=32, WRONG_CHECK=0, GENERATE=0, PROBE=0
#                          the LM cannot affect assembly at all (sig_of is no_grad; the encoder is
#                          trained only by contrastive_step), so it is sized for speed. It is
#                          IDENTICAL in every cell, which is what makes the memory-contribution
#                          column comparable row to row. PROBE=0 also removes a 12 s sleep/cell.
#    SEED=0 for the grid; Stage E repeats winner and baseline at seeds 1,2, because a 4-class
#                          score over ~937 windows is noisy and a one-seed winner is a guess.
#
#  RUNTIME
#    53 cells. The script times ONE smoke cell first and projects the real total before committing
#    (15 s abort window); it refuses to start if the projection exceeds MAX_MIN.
#      JOBS=6 (default) ..... ~25-40 min wall   <- expected on the GH200
#      JOBS=1 ............... ~2.5-3.5 h wall
#    Per cell: ~937 LM steps + <=3000 warmup steps + the eval battery ~= 1.5-3 min. Cells are
#    batch-1 and launch-bound, so one cell leaves a GH200 nearly idle and 6 concurrent cells cost
#    almost nothing in wall-clock. The price is that steps/min is then measured UNDER CONTENTION;
#    the smoke cell and Stage A run ALONE so there is one clean throughput number to quote.
#    If the projection is too high: KEY_SRC=frozen roughly halves each cell (it removes the
#    _model_key rekey path, which is the dominant dispatch cost) at the price of making the
#    memory-contribution column a frozen-key baseline rather than the product path.
#
set -u
export LC_ALL=C

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO" || exit 1

OUT=${OUT:-sweep_out}
JOBS=${JOBS:-6}
STAGES=${STAGES:-A,B,C,D,E}
SL=${STREAM_LEN:-120000}
MAX_MIN=${MAX_MIN:-180}
KEY_SRC_V=${KEY_SRC:-model}
BIG=${BIG:-auto}
FORCE=${FORCE:-0}
DRY=${DRY:-0}
SKIP_GPU_CHECK=${SKIP_GPU_CHECK:-0}        # only to lint the sweep on a CPU box; never for a real run
SO="$OUT/self_organize_sweep.py"           # patched COPY -- self_organize.py is never modified

mkdir -p "$OUT/cells"
: > "$OUT/preflight.txt"
say () { echo "$@" | tee -a "$OUT/preflight.txt"; }
die () { echo "!! $*" | tee -a "$OUT/preflight.txt" >&2; exit 1; }

say "=============================================================================="
say " DOMAIN-ASSEMBLY SWEEP   $(date -u '+%Y-%m-%d %H:%M:%SZ')"
say "=============================================================================="

# ---------------------------------------------------------------------------------------------
# 0. RUNTIME ENVIRONMENT. These are NOT read by self_organize.py -- they are consumed by
#    torch/OpenMP and by glibc. Preflight flagged 64 intra-op threads being spawned for batch-1
#    work: every one of them costs a barrier on a 128-element GRU step. Set here, VERIFIED below
#    through torch itself rather than assumed.
# ---------------------------------------------------------------------------------------------
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8
export MALLOC_ARENA_MAX=4
# the patched copy lives in $OUT, so sys.path[0] is $OUT and `from memory import ...` would fail
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"

# ---------------------------------------------------------------------------------------------
# 1. TORCH / GPU
# ---------------------------------------------------------------------------------------------
python3 - <<'PYEOF' 2>&1 | tee -a "$OUT/preflight.txt"
import os, torch
print("torch %s | cuda_available %s | intra-op threads %d (OMP_NUM_THREADS=%s)"
      % (torch.__version__, torch.cuda.is_available(), torch.get_num_threads(),
         os.environ.get("OMP_NUM_THREADS")))
if torch.cuda.is_available():
    p = torch.cuda.get_device_properties(0)
    print("gpu %s | %.1f GiB | sm_%d%d" % (p.name, p.total_memory / 2**30, p.major, p.minor))
if torch.get_num_threads() > int(os.environ.get("OMP_NUM_THREADS", "0")):
    print("!! torch.get_num_threads()=%d EXCEEDS OMP_NUM_THREADS -- this torch is ignoring the env "
          "var and every cell will oversubscribe the CPU on batch-1 work" % torch.get_num_threads())
PYEOF
if [ "$SKIP_GPU_CHECK" != "1" ]; then
  python3 -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" \
    || die "torch imports but torch.cuda.is_available() is False. Run: bash preflight.sh"
fi
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total,driver_version \
  --format=csv,noheader 2>&1 | tee -a "$OUT/preflight.txt"
say "repo $(git rev-parse --short HEAD 2>/dev/null || echo no-git) | self_organize.py sha256 \
$(sha256sum self_organize.py | cut -c1-16) | $(wc -l < self_organize.py) lines | KEY_SRC=$KEY_SRC_V"

# ---------------------------------------------------------------------------------------------
# 2. DATA. DATA_MODE=real is set on EVERY cell. The default is DATA_MODE=synthetic, which swaps
#    the four real corpora for four synthetic Markov processes and silently answers a different
#    question -- a launch has already been lost to exactly this.
# ---------------------------------------------------------------------------------------------
for d in eng py num c; do
  [ -d "data/train/$d" ] || die "missing data/train/$d -- the 4-corpus grid needs eng,py,num,c"
done
say "corpora: $(du -sb data/train/eng data/train/py data/train/num data/train/c 2>/dev/null \
  | awk '{printf "%s=%.1fMB ", $2, $1/1048576}')"

# data_mix: eng from the 40 GB fineweb-edu, py/num/c from data/. Only Stage D needs it. A 480k
# stream draws ~120 kB of eng, so with data/'s 3.3 MB the three stream lengths would partly reuse
# the same text and the "does the count scale with BYTES" test would be reading its own tail.
# Symlinks only -- nothing is copied, nothing is downloaded.
MIXDIR="data"; DEXTRA=""
if [ "$BIG" != "0" ] && [ -d "data_big/train/eng" ]; then
  MIXDIR="$OUT/data_mix"; mkdir -p "$MIXDIR/train"
  ln -sfn "$REPO/data_big/train/eng" "$MIXDIR/train/eng"
  for d in py num c; do ln -sfn "$REPO/data/train/$d" "$MIXDIR/train/$d"; done
  DEXTRA="DATA_DIR=$MIXDIR DISK_STREAM=1 CORPUS_CAP=2000000000"
  say "extensivity stage draws eng from data_big ($(du -sh data_big/train/eng 2>/dev/null | cut -f1)) via $MIXDIR"
else
  say "extensivity stage uses data/ (no data_big/train/eng) -- eng segments may repeat at 480k"
fi

# ---------------------------------------------------------------------------------------------
# 3. PATCH A COPY. self_organize.py is left byte-identical. Two PRINT-ONLY additions:
#      [sweep-audit]          created / merged / culled / capped / cap_binding / cluster counts /
#                             median windows per domain. `capped` is the falsifier for K1 and the
#                             file prints it NOWHERE, so without this the sweep cannot be scored.
#      [sweep-audit-resolved] purity/homogeneity/completeness/V recomputed over asm.resolve(d).
#                             The shipped metrics use the RAW domain id recorded at assign time
#                             (assigns.append((bpos, did, ...))), never resolved through the merge
#                             chain -- so a run that consolidates 64 domains into 4 BY MERGING
#                             still scores as 64 clusters, and any fix that works through merge is
#                             invisible to the shipped V-measure. Both are reported side by side.
# ---------------------------------------------------------------------------------------------
cp -f self_organize.py "$SO" || die "cannot copy self_organize.py"
python3 - "$SO" <<'PYEOF' || die "audit patch failed"
import sys
p = sys.argv[1]
src = open(p).read()
ANCHORS = ["    biggest = max(by, key=lambda d: sum(by[d].values())); tgt = s2t[biggest]",
           "    biggest = max(by, key=lambda d: sum(by[d].values()))"]
anchor = next((a for a in ANCHORS if src.count(a) == 1), None)
if anchor is None:
    sys.exit("no unique anchor in self_organize.py -- the eval block moved. Re-point ANCHORS at a "
             "unique line that runs AFTER `assigns`, `by`, `_ct` and `_hc` exist.")
BLOCK = '''
    # ---- [SWEEP AUDIT] inserted by sweep_domain_grid.sh. PRINT ONLY: no state read or written. ----
    _res = {}
    for _bp, _d, _t in assigns: _res.setdefault(asm.resolve(_d), Counter())[_t] += 1
    _n2 = max(1, len(assigns))
    _ck2 = {k: sum(c.values()) for k, c in _res.items()}
    _hck2 = -sum(c[t] / _n2 * _m.log((c[t] / max(1, sum(c.values()))) or 1) for c in _res.values() for t in c)
    _hkc2 = -sum(_res[d][t] / _n2 * _m.log((_res[d][t] / max(1, _ct[t])) or 1) for d in _res for t in _res[d])
    _hk2 = -sum(v / _n2 * _m.log(v / _n2) for v in _ck2.values() if v)
    _hom2 = 1.0 if _hc == 0 else max(0.0, 1 - _hck2 / _hc)
    _com2 = 1.0 if _hk2 == 0 else max(0.0, 1 - _hkc2 / _hk2)
    _v2 = 0.0 if (_hom2 + _com2) == 0 else 2 * _hom2 * _com2 / (_hom2 + _com2)
    _pur2 = sum(c.most_common(1)[0][1] for c in _res.values()) / _n2
    _sz = sorted(_ck2.values(), reverse=True)
    print(f"[sweep-audit] live={len(asm.cent)} created={asm.created} merged={len(asm.merged)} "
          f"culled={asm.created - len(asm.merged) - len(asm.cent)} capped={asm.capped} "
          f"max_domains={MAX_DOMAINS} cap_binding={'YES' if asm.capped > 0 else 'no'} "
          f"clusters_raw={len(by)} clusters_resolved={len(_res)} windows={len(assigns)} "
          f"median_wins={_sz[len(_sz) // 2] if _sz else 0} largest={_sz[0] if _sz else 0} "
          f"new_dist={NEW_DIST} shift_dist={SHIFT_DIST} enc_pos_max={_i('ENC_POS_MAX', 2 * WIN)} "
          f"enc_warmup={_i('ENC_WARMUP', 800)} sig_mode={SIG_MODE} stream_len={STREAM_LEN} seed={_i('SEED', 0)}")
    print(f"[sweep-audit-resolved] purity={_pur2:.3f} homogeneity={_hom2:.3f} "
          f"completeness={_com2:.3f} vmeasure={_v2:.3f}")
'''
if "[sweep-audit]" not in src:
    open(p, "w").write(src.replace(anchor, BLOCK + anchor, 1))
print("audit patch applied")
PYEOF
grep -q "\[sweep-audit\]" "$SO" || die "audit patch verification failed"
python3 -c "import ast; ast.parse(open('$SO').read())" || die "patched copy does not parse"
say "patched copy: $SO   (self_organize.py untouched)"

# ---------------------------------------------------------------------------------------------
# 4. KNOB VERIFICATION -- every variable this script sets must actually be READ by
#    self_organize.py. This is the check that would have caught D_MODEL_B, which was read by
#    nothing, so an entire GPU bench ran at d=128 while reporting d=768.
# ---------------------------------------------------------------------------------------------
SET_KNOBS="DEVICE DATA_MODE DATA_DIR DOMAINS CORPUS_CAP DISK_STREAM STREAM_LEN WIN SEED
D_MODEL MODEL SIG_MODE SIG_D SIG_DIM SUSTAIN NEW_DIST SHIFT_DIST KEY_SRC
ENC_POS_MAX ENC_WARMUP ENC_WARMUP_MIN ENC_WARMUP_EPS ENC_BATCH
MAX_DOMAINS MERGE_FRAC DOM_ADAPTIVE DOM_SPAWN_K DOM_GRACE
MANAGE MANAGE_EVERY MANAGE_MERGE MANAGE_STALE
MEM_CAP EVAL_N EPOCHS RATE_EVERY PROBE GENERATE WRONG_CHECK TF32 AMP"
miss=""
for k in $SET_KNOBS; do
  grep -qE "(_i|_f)\(\"$k\"|os\.environ\.get\(\"$k\"" self_organize.py || miss="$miss $k"
done
[ -z "$miss" ] || die "these knobs are NOT read by self_organize.py:$miss
   Setting them would be a silent no-op. Fix the name or drop it before running anything."
say "knob check: all $(echo $SET_KNOBS | wc -w) knobs this script sets are read by self_organize.py"

# 4b. INHERITED-KNOB GUARD. Anything self_organize.py reads that is already exported in the
#     calling shell but NOT pinned here would leak into every cell and silently redefine the
#     experiment. Abort rather than produce an unattributable table.
LEAK=$(SET_KNOBS="$SET_KNOBS" python3 - <<'PYEOF'
import os, re
src = open("self_organize.py").read()
known = set(re.findall(r'(?:_i|_f)\("([A-Z][A-Z_0-9]*)"', src)) | \
        set(re.findall(r'os\.environ\.get\("([A-Z][A-Z_0-9]*)"', src))
pinned = set(os.environ["SET_KNOBS"].split())
print(" ".join(sorted(k for k in known - pinned if k in os.environ)))
PYEOF
)
if [ -n "$LEAK" ]; then
  if [ "$FORCE" = "1" ]; then say "!! inherited knobs present, continuing under FORCE=1:$LEAK"
  else die "these self_organize.py knobs are already set in your shell and would leak into every cell:
     $LEAK
   run:  unset $LEAK    (or re-run with FORCE=1 if you meant it)"; fi
fi

# ---------------------------------------------------------------------------------------------
# 5. THE CELL RUNNER
# ---------------------------------------------------------------------------------------------
BASE="DATA_MODE=real DATA_DIR=data DOMAINS=eng,py,num,c CORPUS_CAP=4000000 DISK_STREAM=0
DEVICE=cuda TF32=1 AMP=off MODEL=gru D_MODEL=128 WIN=128 SIG_MODE=learned SIG_D=64 SIG_DIM=512
SUSTAIN=2 SEED=0 EPOCHS=1 STREAM_LEN=$SL KEY_SRC=$KEY_SRC_V
MAX_DOMAINS=4096 DOM_ADAPTIVE=0 DOM_SPAWN_K=3.0 MANAGE=1 MANAGE_MERGE=0 MERGE_FRAC=0.8
MANAGE_EVERY=500 MANAGE_STALE=500 DOM_GRACE=500 ENC_BATCH=48
ENC_WARMUP_MIN=1000000000 ENC_WARMUP_EPS=0
MEM_CAP=50000 EVAL_N=32 WRONG_CHECK=0 GENERATE=0 PROBE=0 RATE_EVERY=100"

run_cell () {                       # run_cell NAME "K=V ..."   (later K=V wins inside `env`)
  local name="$1"; shift
  local ov="$*"
  local log="$OUT/cells/$name.log"
  if [ "$DRY" = "1" ]; then echo "DRY $name: env $BASE $ov python3 $SO"; return 0; fi
  ( t0=$(date +%s)
    env $BASE $ov python3 "$SO" > "$log" 2>&1
    rc=$?
    echo "[sweep-cell] name=$name rc=$rc wall_s=$(( $(date +%s) - t0 )) jobs=$JOBS env=$ov" >> "$log"
    echo "  . $name rc=$rc $(grep -o 'live=[0-9]* .*capped=[0-9]*' "$log" | head -1)"
  ) &
}
throttle ()   { while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do sleep 2; done; }
has_stage ()  { case ",$STAGES," in *",$1,"*) return 0;; *) return 1;; esac; }

# ---------------------------------------------------------------------------------------------
# 6. SMOKE CELL + HONEST PROJECTION. One real cell, alone, timed, so the total is projected from a
#    measurement rather than a guess -- and the script aborts itself if the projection is absurd.
# ---------------------------------------------------------------------------------------------
NCELLS=53
if [ "$DRY" != "1" ]; then
  say ""; say "--- smoke cell (alone) ---"
  run_cell smoke "ENC_POS_MAX=256 ENC_WARMUP=800 NEW_DIST=0.35 SHIFT_DIST=0.30"; wait
  grep -q "\[sweep-audit\]" "$OUT/cells/smoke.log" \
    || { tail -40 "$OUT/cells/smoke.log"; die "smoke cell never reached the audit line -- see $OUT/cells/smoke.log"; }
  SMOKE_S=$(grep -o 'wall_s=[0-9]*' "$OUT/cells/smoke.log" | tail -1 | cut -d= -f2)
  say "  $(grep '\[sweep-audit\]' "$OUT/cells/smoke.log" | head -1)"
  say "  $(grep '\[sweep-audit-resolved\]' "$OUT/cells/smoke.log" | head -1)"
  say "  $(grep 'clustering purity' "$OUT/cells/smoke.log" | head -1)"
  say "  $(grep 'boundary detection' "$OUT/cells/smoke.log" | head -1)"
  say "  smoke wall ${SMOKE_S}s alone | last rate: $(grep -o '[0-9]* steps/min' "$OUT/cells/smoke.log" | tail -1)"
  # Stage D's 240k/480k cells cost ~2x and ~4x a grid cell -> count them as +5 cell-equivalents.
  J=$JOBS; [ "$J" -lt 1 ] && J=1
  PROJ=$(( (NCELLS + 5) * SMOKE_S / 60 / J + 1 ))
  say "  PROJECTED TOTAL ~${PROJ} min for $NCELLS cells at JOBS=$JOBS"
  [ "$PROJ" -le "$MAX_MIN" ] || die "projection ${PROJ} min > MAX_MIN=${MAX_MIN}.
   Cut it: STAGES=A,B  |  STREAM_LEN=60000  |  KEY_SRC=frozen  |  raise MAX_MIN."
  say "  Ctrl-C within 15 s to abort."; sleep 15
fi

# ---------------------------------------------------------------------------------------------
# STAGE A -- CAP INVARIANCE (K1). The falsifier. Identical config, three caps. Run SERIALLY so
# steps/min here is one uncontended reference number for the whole sweep.
# ---------------------------------------------------------------------------------------------
if has_stage A; then
  say ""; say "--- STAGE A: cap invariance, MAX_DOMAINS 8 / 64 / 4096 (serial, uncontended) ---"
  for mx in 8 64 4096; do
    run_cell "A_cap${mx}" "MAX_DOMAINS=$mx ENC_POS_MAX=256 ENC_WARMUP=800 NEW_DIST=0.35 SHIFT_DIST=0.30"
    wait
  done
fi

# ---------------------------------------------------------------------------------------------
# STAGE B -- THE GRID. 4 x 3 x 3, cap open at 4096 in every cell.
# ---------------------------------------------------------------------------------------------
if has_stage B; then
  say ""; say "--- STAGE B: ENC_POS_MAX x ENC_WARMUP x NEW_DIST (36 cells, MAX_DOMAINS=4096) ---"
  for pm in 256 512 1024 2048; do
    for wu in 0 800 3000; do
      for nd in 0.35 0.50 0.65; do
        sd=$(awk -v n="$nd" 'BEGIN{printf "%.3f", n*6/7}')   # keep the shipped SHIFT/NEW ratio
        throttle
        run_cell "B_p${pm}_w${wu}_n${nd}" "ENC_POS_MAX=$pm ENC_WARMUP=$wu NEW_DIST=$nd SHIFT_DIST=$sd"
      done
    done
  done
  wait
fi

# ---- winner: highest resolved V among Stage-B cells with capped==0 AND boundary recall >= 0.85 --
BEST=""
[ "$DRY" != "1" ] && BEST=$(python3 sweep_domain_report.py "$OUT" --pick 2>>"$OUT/preflight.txt")
[ -n "$BEST" ] || BEST="ENC_POS_MAX=1024 ENC_WARMUP=800 NEW_DIST=0.65 SHIFT_DIST=0.557"
say ""; say "winner carried into stages C/D/E:  $BEST"

# ---------------------------------------------------------------------------------------------
# STAGE C -- CONTROLS. Each isolates exactly one thing the grid held fixed, plus the no-learning
# baseline that bounds what the learned encoder is actually buying (K6).
# ---------------------------------------------------------------------------------------------
if has_stage C; then
  say ""; say "--- STAGE C: controls at the winner ---"
  throttle; run_cell C_bigram      "SIG_MODE=bigram ENC_WARMUP=0 NEW_DIST=0.35 SHIFT_DIST=0.30"
  throttle; run_cell C_adaptive_on "$BEST DOM_ADAPTIVE=1"
  throttle; run_cell C_mergestock  "$BEST MANAGE_MERGE=0.12"
  throttle; run_cell C_managefast  "$BEST MANAGE_EVERY=100 DOM_GRACE=200 MANAGE_STALE=250"
  throttle; run_cell C_manageoff   "$BEST MANAGE=0"
  throttle; run_cell C_best_cap64  "$BEST MAX_DOMAINS=64"        # K1 re-run AT the winner
  wait
fi

# ---------------------------------------------------------------------------------------------
# STAGE D -- EXTENSIVITY (K5). Same cell, three stream lengths. A converged population is FLAT in
# stream length; a truncated ramp roughly doubles with it. This is the test 64 would have failed.
# ---------------------------------------------------------------------------------------------
if has_stage D; then
  say ""; say "--- STAGE D: extensivity, STREAM_LEN 120k / 240k / 480k (data: $MIXDIR) ---"
  for sl in 120000 240000 480000; do
    throttle; run_cell "D_len${sl}" "$BEST $DEXTRA STREAM_LEN=$sl"
  done
  wait
fi

# ---------------------------------------------------------------------------------------------
# STAGE E -- SEED REPEATS. A one-seed winner over ~937 windows is a guess, not a result.
# ---------------------------------------------------------------------------------------------
if has_stage E; then
  say ""; say "--- STAGE E: seeds 1,2 for the winner and for the stock baseline ---"
  for s in 1 2; do
    throttle; run_cell "E_best_s${s}"  "$BEST SEED=$s"
    throttle; run_cell "E_stock_s${s}" "ENC_POS_MAX=256 ENC_WARMUP=800 NEW_DIST=0.35 SHIFT_DIST=0.30 SEED=$s"
  done
  wait
fi

# ---------------------------------------------------------------------------------------------
# 7. SUMMARY -- one table to paste back
# ---------------------------------------------------------------------------------------------
if [ "$DRY" != "1" ]; then
  python3 sweep_domain_report.py "$OUT" > "$OUT/SUMMARY.md"
  echo; cat "$OUT/SUMMARY.md"
  echo; echo "=== $OUT/SUMMARY.md written (paste it back) | per-cell logs in $OUT/cells/ ==="
fi
