#!/bin/bash
# ==================================================================================================
# IS THE WORLD MODEL'S LOSS EARNING ITS PLACE IN THE LANGUAGE MODEL'S OBJECTIVE?
# ==================================================================================================
# WHY THIS SWEEP EXISTS, AND IT IS NOT A TUNING QUESTION. WORLD.loss_terms' return is added to the
# LM's loss in spine/loop.py::_flush -- `total = mean + aux + world_loss + anchor` -- and it is
# computed on LM.embed's OUTPUT rather than a detached copy, so its gradient reaches the language
# model. Measured at initialisation, one seed, 4 windows of 64 tokens at the shipped defaults:
#
#     LM loss    8.3185   |grad| on emb.weight 0.006371   whole model 0.093273
#     WORLD loss 0.9875   |grad| on emb.weight 0.005194   whole model 0.005194
#
# 45% OF THE EMBEDDING'S GRADIENT, and the world loss touches nothing else in the model, so it is
# not diluted anywhere. Until 2026-09-22 the network producing it was never STEPPED -- World had no
# parameters() and spine/compose.py::_base_parameters could not reach it -- so that 45% came from a
# frozen uniform(-0.1, 0.1) draw. World.parameters() closed that. What this sweep asks is the
# question the closure raises and cannot answer: now that the term is LEARNED rather than random,
# is it worth what it takes from the embedding?
#
# THE ARMS DECOMPOSE THE TERM RATHER THAN TOGGLING IT. loss_terms returns
# `predict_w * pop_loss + collapse_w * (var_loss + W_COV * cov_loss)`, which is two mechanisms with
# one switch: a forward-prediction objective and a VICReg-style anti-collapse penalty. They are
# different claims about why the embedding should move, and `off` cannot tell them apart.
#
#   off             WORLD_ENABLED=0. The null world -- no term, no cost, no gradient. The control.
#   shipped         the defaults: WORLD trained, its forecast NOT fed to the LM (WORLD_FEEDBACK
#                   ships False since the 2026-09-24 GPU fleet, Q-WORLD-10). Same run as feedback_off.
#   feedback_on     WORLD_FEEDBACK=1: the forecast fed into LM.encode (world_proj born zero).
#   collapse_only   WORLD_PREDICT_W=0. Anti-collapse alone: the embedding is pushed to spread, and
#                   nothing asks it to be predictable forward.
#   predict_only    WORLD_COLLAPSE_W=0. Prediction alone, WITH the collapse risk that penalty
#                   exists to prevent -- a latent that goes constant predicts itself perfectly.
#                   Watch world.latent_std: if it falls toward 0 this arm is winning by collapsing.
#   feedback_off    WORLD_FEEDBACK=0 at the shipped weights: the UNWIRED CONTROL. Since the
#                   forecast got its call site (Q-WORLD-10, RESOLVED 2026-09-24) `shipped` feeds
#                   world_proj(pop(z)) into LM.encode as `extra`, and this arm withholds it --
#                   BIT-IDENTICAL to the tree before the call site existed (driven: the same loss
#                   curve, max|diff| 0.0). `shipped` minus this arm prices the forecast itself;
#                   this arm minus `off` prices the world loss alone. Tripwires: here
#                   world.forecast.inert == calls and world.forecasts / lm.encode.extra_ratio are
#                   ABSENT; on `shipped`, world.forecasts == lm.encode.extra_applied == flushes.
#
# WHAT IT MEASURES AND WHAT IT CANNOT. There is no held-out number in the loop: run.py prints a
# TRAINING loss and the EVAL battery is not wired, so every column below is training loss and must
# not be quoted as bits/byte on held-out text. The headline is the mean of the last TAIL progress
# lines rather than loss_last, because loss_last is ONE flush -- measured on this tree, adjacent
# progress lines swing by more than 0.5 while the arm-to-arm gap is around 0.05, so a single-flush
# comparison reads noise. Seeds are the only defence and three is not many: notes/07_WIP.md records
# a measured seed spread of 1.227 b/B on one arm, LARGER than the gap between any two architectures
# ever compared in this project. TREAT A SEPARATION SMALLER THAN THE SEED SPREAD AS NOTHING.
#
#     bash sweep_world.sh                                  # 5 arms x 3 seeds
#     SEEDS="0 1 2 3 4" WINDOWS=4000 bash sweep_world.sh
#     SEEDS="0 1 2 3 4" ONLY=shipped,feedback_off bash sweep_world.sh   # Q-WORLD-10's deciding run
#
# THE WORLD_FEEDBACK DECISION IS READ OFF THE PAIRED LINE, NOT THE TABLE (2026-09-24). Q-WORLD-10
# flips the default on "5 seeds per arm, paired by seed, mean of loss_curve differences over the
# last half"; until then this script printed only unpaired tail means against `off` and never formed
# shipped minus feedback_off. run.py --loss-curve now writes each run's per-flush curve beside its
# log, and the summary prints, per seed, the mean over the last half of the flushes of
# (shipped - feedback_off), then their mean +- SE and how many seeds are negative (shipped better).
#     ONLY=off,shipped bash sweep_world.sh
#     cat world_out/SUMMARY.txt
#
# IT WRITES NO CHECKPOINTS AND TOUCHES NOTHING IN runs/. CKPT_DIR is left unset on purpose.
set -u

OUT=${OUT:-world_out}
WINDOWS=${WINDOWS:-2000}
BYTES=${BYTES:-2000000}
SEEDS=${SEEDS:-"0 1 2"}
TAIL=${TAIL:-5}
ONLY=${ONLY:-off,shipped,collapse_only,predict_only,feedback_off,feedback_on}

mkdir -p "$OUT"
S="$OUT/SUMMARY.txt"
: > "$S"

_have() { [[ ",$ONLY," == *",$1,"* ]]; }

{
  echo "=== WORLD arms: $ONLY"
  echo "=== $WINDOWS windows max, DATA_STREAM_BYTES=$BYTES, seeds: $SEEDS, tail=$TAIL progress lines"
  echo "=== TRAINING loss. There is no held-out number in the loop; do not quote these as b/B."
  echo
} | tee -a "$S"

arm() {
  local name="$1"; shift
  _have "$name" || return 0
  echo "---- $name : $* ----" | tee -a "$S"
  for seed in $SEEDS; do
    local log="$OUT/$name.s$seed.log"
    # env -i IS NOT USED: the arms differ by the levers on their own command line and nothing else,
    # and a scrubbed environment would also drop the proxy and locale settings the corpus needs.
    env RUN_SEED="$seed" DATA_STREAM_BYTES="$BYTES" "$@" \
        python3 run.py --max-windows "$WINDOWS" --loss-curve "$OUT/$name.s$seed.curve.json" \
        > "$log" 2>&1
    local rc=$?
    if [[ $rc -ne 0 ]]; then
      echo "  seed $seed: FAILED (exit $rc). Last lines:" | tee -a "$S"
      tail -4 "$log" | sed 's/^/      /' | tee -a "$S"
      continue
    fi
    python3 - "$log" "$name" "$seed" "$TAIL" >> "$S" <<'PY'
import re, sys
log, name, seed, tail_n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
t = open(log).read()
prog = [float(x) for x in re.findall(r"^\[\d+ windows\] loss=([\d.]+)", t, re.M)]
summ = re.search(r"=== (\d+) windows, \d+ flushes, (\d+) optimizer steps", t)
last = re.search(r"=== loss [\d.]+ -> ([\d.]+)", t)
# world.latent_std IS THE COLLAPSE READING and predict_only is the arm it is printed for: a latent
# that goes constant predicts itself perfectly, so a win on loss with a falling std is not a win.
std = re.search(r"world\.latent_std\s+([\d.]+)", t)
params = re.search(r"=== (\d+) trainable parameter", t)
# A RUN SHORTER THAN ONE PROGRESS CADENCE HAS NO TAIL TO TAKE, and a bare nan in the column the
# comparison sorts on reads as a broken arm rather than as a run that was too short. It falls back
# to loss_last and MARKS ITSELF, because the two are not the same measurement: loss_last is ONE
# flush and is exactly the noise this tail mean exists to average out.
tailv = prog[-tail_n:] if prog else []
mark = " "
if tailv:
    mean = sum(tailv) / len(tailv)
    if len(tailv) < tail_n:
        mark = "~"                      # fewer progress lines than asked for; averaged over what there was
else:
    mean = float(last.group(1)) if last else float("nan")
    mark = "!"                          # NO progress line at all: this is loss_last, one flush
print(f"  {name:<14} seed {seed} | {summ.group(1) if summ else '?':>5} win "
      f"{summ.group(2) if summ else '?':>5} steps | tail{tail_n} mean {mean:7.4f}{mark}"
      f"| last {last.group(1) if last else '?':>7} "
      f"| latent_std {std.group(1) if std else 'ABSENT':>8} "
      f"| {params.group(1) if params else '?'} params")
PY
  done
  echo | tee -a "$S"
}

arm off           WORLD_ENABLED=0
arm shipped
arm collapse_only WORLD_PREDICT_W=0.0
arm predict_only  WORLD_COLLAPSE_W=0.0
arm feedback_off  WORLD_FEEDBACK=0
arm feedback_on   WORLD_FEEDBACK=1

# ---------- the comparison, across seeds ----------
# PAIRED BY SEED AND PRINTED AS A SPREAD, NOT AS A MEAN ALONE. compare.py exists in this repo for
# P(A>B) with a bootstrap CI and is the right instrument once there are enough samples to bootstrap;
# three seeds is not enough, so this prints every seed's number beside the mean and leaves the
# reader to see the overlap rather than hiding it behind an average.
python3 - "$S" "$TAIL" >> "$S" <<'PY'
import re, sys
S, tail_n = sys.argv[1], int(sys.argv[2])
rows = {}
for m in re.finditer(r"^  (\S+)\s+seed (\d+) \|.*?tail\d+ mean\s+([\d.]+)[ ~!]", open(S).read(), re.M):
    rows.setdefault(m.group(1), []).append((int(m.group(2)), float(m.group(3))))
if not rows:
    sys.exit(0)
print()
print(f"=== tail{tail_n}-mean training loss by arm (lower is better), every seed shown ===")
# THE BASELINE IS NAMED BY THE ARM ACTUALLY USED. It fell back to `shipped` when `off` was not run
# and was still printed "vs off", so ONLY=shipped,feedback_off labelled a comparison against shipped
# as one against the null world.
bname = "off" if rows.get("off") else ("shipped" if rows.get("shipped") else None)
base = rows.get(bname) if bname else None
bmean = sum(v for _, v in base) / len(base) if base else None
for name, vals in rows.items():
    vs = [v for _, v in sorted(vals)]
    mean = sum(vs) / len(vs)
    spread = max(vs) - min(vs) if len(vs) > 1 else 0.0
    delta = f"{mean - bmean:+.4f} vs {bname}" if bmean is not None else ""
    print(f"  {name:<14} mean {mean:7.4f}  spread {spread:6.4f}  "
          f"seeds {' '.join(f'{v:.4f}' for v in vs)}  {delta}")

# Q-WORLD-10's DECIDING STATISTIC: shipped minus feedback_off, PAIRED BY SEED, over the last half of
# each run's per-flush loss curve. Printed only when both arms have curves for a common seed.
import json, math, os
out_dir = os.path.dirname(S) or "."
def _curve(arm, seed):
    try:
        with open(os.path.join(out_dir, f"{arm}.s{seed}.curve.json")) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None
seeds = sorted({s for s, _ in rows.get("feedback_on", [])} & {s for s, _ in rows.get("feedback_off", [])})
diffs = []
for sd in seeds:
    a, b = _curve("feedback_on", sd), _curve("feedback_off", sd)
    if not a or not b:
        continue
    n = min(len(a), len(b))
    h = n // 2
    if n - h < 1:
        continue
    diffs.append((sd, sum(a[i] - b[i] for i in range(h, n)) / (n - h), n - h))
print()
if diffs:
    print("=== Q-WORLD-10: feedback_on - feedback_off, mean over the last half of the loss curve, "
          "paired by seed (negative = the forecast helps) ===")
    for sd, d, k in diffs:
        print(f"  seed {sd}: {d:+.4f}  (last {k} flushes)")
    ds = [d for _, d, _ in diffs]
    m = sum(ds) / len(ds)
    se = (math.sqrt(sum((x - m) ** 2 for x in ds) / (len(ds) - 1) / len(ds))
          if len(ds) > 1 else float("nan"))
    print(f"  mean {m:+.4f} +- {se:.4f} (SE, {len(ds)} seeds), {sum(1 for x in ds if x < 0)}/{len(ds)} "
          f"seeds negative. Q-WORLD-10: WORLD_FEEDBACK ships 0; a result outside noise is the case for turning it back on.")
elif "feedback_on" in rows or "feedback_off" in rows:
    print("=== Q-WORLD-10's paired feedback_on - feedback_off line needs BOTH arms on a common seed "
          "with a loss curve; it was not formed.")
print()
print("A '~' beside a number means fewer progress lines than TAIL asked for; a '!' means none at")
print("all, so that row is loss_last -- ONE flush, and exactly the noise the tail mean averages out.")
print()
print("A separation smaller than the within-arm spread is NOTHING. notes/07_WIP.md records a")
print("measured seed spread of 1.227 b/B on a single arm, larger than the gap between any two")
print("architectures ever compared in this project.")
PY
echo "=== wrote $S"
