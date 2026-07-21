#!/bin/bash
# ============ FULL AUTOMATED TEST on one H100 -- runs the entire EXPERIMENTS.md plan unattended ============
# pre-flight -> data -> baseline (Rung 0) -> single-axis groups (Rung 1) -> within-group sweeps (Rung 2) -> aggregate.
# Each phase is FAULT-ISOLATED: a crash (e.g. OOM) is logged and the run continues to the next phase.
#   tmux new -s full 'bash run_full_test.sh'        (or: python3 control.py fulltest)
#   watch:  tail -f ~/fulltest.log        results:  ~/fulltest_results.txt
# Tunables (env): STEPS (rung length, default 30000), SWEEP_STEPS (8000), D_MODEL (512), NOTIFY_URL (optional ntfy webhook).
set -u
cd ~/overarching-package
LOG=~/fulltest.log; : > "$LOG"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export DATASET=${DATASET:-enwik9} DIVERSE=${DIVERSE:-1} MP_WORKERS=${MP_WORKERS:-4}
say(){ echo "=== $* | $(date +%F_%H:%M:%S) ===" | tee -a "$LOG"; }
notify(){ [ -n "${NOTIFY_URL:-}" ] && curl -s -d "$1" "$NOTIFY_URL" >/dev/null 2>&1 || true; }

STEPS=${STEPS:-30000}; SWEEP_STEPS=${SWEEP_STEPS:-8000}
D_MODEL=${D_MODEL:-512}; N_LAYERS=${N_LAYERS:-8}; N_HEADS=${N_HEADS:-8}; CTX=${CTX:-256}; MAX_LEN=${MAX_LEN:-512}
ARCH="D_MODEL=$D_MODEL N_LAYERS=$N_LAYERS N_HEADS=$N_HEADS CTX=$CTX MAX_LEN=$MAX_LEN VMAX=32768 MIN_PAIR=200"
GROW="NMAX=64 N0=16 GRACE=600 PATIENCE=500 COOLDOWN=300 LR_WARMUP=1500 EVAL_EVERY=1000 CKPT_EVERY=${CKPT_EVERY:-2000}"
T0=$(date +%s)

# 0. PRE-FLIGHT (the only place we abort)
say "PRE-FLIGHT"
if ! python3 control.py check >>"$LOG" 2>&1; then say "PRE-FLIGHT FAILED -- aborting"; notify "fulltest ABORTED: preflight"; exit 1; fi
notify "fulltest: preflight OK, starting the plan"

# 1. DATA
say "DATA SETUP"; [ -f "data/train/eng/${DATASET}.txt" ] || bash setup_lambda.sh >>"$LOG" 2>&1

# shared batch probe at the HEAVIEST footprint (full preset) so every rung fits AND is matched-compute
say "probing batch at TRUE peak (FULL vocab-width logits + max experts + max depth + full length)..."
DMAX=16   # max layers any arm grows to (depth/full presets); probe here so a grown run never exceeds the probed memory
RB=16
# CRITICAL: logit activations are (B, L, V) for the main + recon + MTP heads, and V grows 256 -> VMAX over training.
# PROBE_PEAK forces V=VMAX + experts=NMAX BEFORE the loop, so the probe measures the real end-of-training footprint
# (a 4-step probe otherwise sees V~300 and under-counts head memory ~100x -> the OOMs we just hit). RECON+MTP+EMA
# forced on = the heaviest arm (robust's recon head, train's EMA shadow); COMPOSE off (negligible memory, avoids cache path).
for B in 256 192 160 128 96 80 64 48 32 24; do
  if timeout 280 env $ARCH $GROW BATCH=$B MP_WORKERS=0 WARMUP_STEPS=2 STEPS=3 RUN_DIR=/tmp/fp python3 control.py train --preset full PROBE_PEAK=1 RECON=0.5 MTP_K=1 EMA_DECAY=0.999 COMPOSE_EMB=0 CTX_START=0 DEPTH_GROWTH=0 N_LAYERS=$DMAX N0=64 NMAX=64 >/tmp/fp.log 2>&1; then RB=$B; rm -rf /tmp/fp; break; fi
  rm -rf /tmp/fp
done
say "shared BATCH=$RB | rung STEPS=$STEPS | sweep STEPS=$SWEEP_STEPS"; notify "fulltest: batch=$RB, running rungs"

# wall-clock projection at the probed batch -- so a multi-day run can't surprise you (timing only, ~30s)
say "estimating wall-clock at BATCH=$RB (peak footprint) ..."
env $ARCH $GROW BATCH=$RB N_LAYERS=$DMAX N0=64 NMAX=64 PROBE_PEAK=1 RECON=0.5 MTP_K=1 EMA_DECAY=0.999 \
    PROF_STEPS=20 PROF_WARMUP=4 STEPS=$STEPS SWEEP_STEPS=$SWEEP_STEPS MP_WORKERS=0 \
    python3 control.py profile --preset full 2>&1 | grep -E "THROUGHPUT|PEAK VRAM|TOTAL ~|Rung 1 \(6" | tee -a "$LOG"
say "^ if TOTAL is more than you want, Ctrl-C now and lower VMAX / drop RECON+MTP / turn off COUNTERPARTS / cut SWEEP_STEPS"
sleep 20   # grace window to abort before committing to the full run

# 2. RUNG 0 baseline + RUNG 1 single-axis groups -- matched batch + steps, fault-isolated
for arm in base train eco robust arch depth; do
  say "RUNG --preset $arm"
  if env $ARCH $GROW BATCH=$RB STEPS=$STEPS RUN_DIR=ft_$arm python3 control.py train --preset $arm >>"$LOG" 2>&1; then
    o=$(grep '\[eval@' "$LOG" | tail -1 | grep -oE 'OOD [0-9.]+'); notify "fulltest: $arm done ($o)"
  else
    say "!! $arm FAILED (likely OOM at BATCH=$RB) -- continuing"; notify "fulltest: $arm FAILED"
  fi
done

# 3. RUNG 2 within-group sweeps (each script probes/runs its own arms at SWEEP_STEPS)
say "SWEEP training methods"; env BATCH=$RB STEPS=$SWEEP_STEPS bash run_training_sweep.sh >>"$LOG" 2>&1 || say "!! training sweep errored"
say "SWEEP eco levers";      env BATCH=$RB STEPS=$SWEEP_STEPS bash run_eco_sweep.sh      >>"$LOG" 2>&1 || say "!! eco sweep errored"
say "SWEEP arch (repr, incl NN-init)"; env BATCH=$RB STEPS=$SWEEP_STEPS bash run_arch_sweep.sh   >>"$LOG" 2>&1 || say "!! arch sweep errored"
say "SWEEP robust";         env BATCH=$RB STEPS=$SWEEP_STEPS bash run_robust_sweep.sh >>"$LOG" 2>&1 || say "!! robust sweep errored"

# 4. AGGREGATE everything into one report
say "AGGREGATING"
{
  echo "===================  FULL TEST RESULTS  ($(date))  ==================="
  echo "elapsed: $(( ($(date +%s)-T0)/3600 ))h$(( (($(date +%s)-T0)%3600)/60 ))m | shared batch $RB | rung steps $STEPS"
  echo; echo "-- Rung 0/1: baseline + single-axis GROUPS (OOD bits/byte, lower is better) --"
  python3 read_results.py $(ls -d ft_base ft_train ft_eco ft_robust ft_arch ft_depth 2>/dev/null) 2>/dev/null
  echo; echo "-- Rung 2: TRAINING-METHODS sweep (each isolated vs ts_base) --"
  python3 read_results.py $(ls -d ts_* 2>/dev/null) 2>/dev/null
  echo; echo "-- Rung 2: ECO sweep (levers + cull-metric vs eco_base) --"
  python3 read_results.py $(ls -d eco_* 2>/dev/null | grep -v eco_sweep) 2>/dev/null
  echo; echo "-- Rung 2: ARCH sweep (compose/correct/NN-init vs as_base) --"
  python3 read_results.py $(ls -d as_* 2>/dev/null) 2>/dev/null
  echo; echo "-- Rung 2: ROBUST sweep (denoise/recon/fuzzy vs rs_base) --"
  python3 read_results.py $(ls -d rs_* 2>/dev/null) 2>/dev/null
  echo; echo "READING RULE: a lever counts only if it beats its baseline by more than run-to-run noise (EXPERIMENTS.md)."
} | tee ~/fulltest_results.txt | tee -a "$LOG"
say "FULL TEST COMPLETE -> ~/fulltest_results.txt"; notify "fulltest COMPLETE -- see ~/fulltest_results.txt"
