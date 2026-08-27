# Experimental plan — how to test without confounding

We have many toggleable capabilities. Turning them all on (`--preset full`) proves nothing about which earns
its keep. This is the order to run things so every result is **attributable**. Everything goes through
`control.py`; every arm is measured by held-out **OOD bits/byte** (lower = better) against a fixed baseline.

## Rung 0 — the baseline (run first, always)
```
python3 control.py train --preset base DATASET=enwik9 DIVERSE=1 STEPS=30000
```
This is the number every other run is compared to. Nothing new is on. Save its `best.pt` and its OOD floor.

## Rung 1 — single-axis groups (each vs baseline)
Run each group **alone** so its effect is isolated. Same steps/data as the baseline.
```
python3 control.py train --preset train    # training methods only (no new params)
python3 control.py train --preset eco       # evolutionary experts only
python3 control.py train --preset robust    # denoise + reconstruction + fuzzy
python3 control.py train --preset arch       # compositional embeddings + correction hooks + MTP (param-heavy)
python3 control.py train --preset depth      # DEPTH growth: experts saturate -> controller grows layers (2-tier)
```
Read each OOD vs Rung 0. A group that doesn't beat baseline gets dropped from later combinations.

## Rung 2 — within-group sweeps (only for groups that helped)
Isolate the levers inside a winning group. Each arm changes ONE knob vs its group's control.
```
python3 control.py sweep training        # base vs cosine/wsd/ema/ls/zloss/mtp/gacc/lion + the bundle
python3 control.py sweep eco              # base vs bottleneck/mutation/cull + cull-metric energy/traffic/blend
python3 control.py sweep arch             # base vs compose/compose-depth/correct/NN-init + all-arch
python3 control.py sweep robust           # base vs denoise/recon/fuzzy + all-robust
```
Keep only the levers with a real delta; discard the rest (this is where the confound + param bloat get pruned).

## Rung 3 — justified combinations
Combine ONLY the levers that individually beat baseline (from Rungs 1-2). Example, if train + eco won:
```
python3 control.py train --preset train --preset eco   # (or pass the specific winning knobs)
```
If a combination underperforms the sum of its parts, the levers interact badly -- note it, don't ship it.

## Rung 4 — the winner, at scale
Take the best justified config to a long run (bigger vocab already default; consider d768):
```
python3 control.py sweep scale <winning knobs>          # long run of the winner
```

## Tokenizer aspects (independent of the model rungs, run any time)
```
python3 control.py test correct,compress,robust,fuzzy   # lossless / compression / typo-brittleness / fuzzy correction
python3 control.py test modeling                          # does tokenization lower bits/byte vs raw bytes
python3 control.py test components                        # component correctness tests
```

## Reading rules (so we don't fool ourselves)
- Compare at **matched compute** (same steps, same probed batch) -- the sweeps enforce this.
- A lever must **beat baseline by more than run-to-run noise** to count. If unsure, re-run the arm.
- `--preset full` is a **stress test** (does it stay stable with everything on), NOT evidence any single thing helps.
- Watch **param count / memory** on the `arch` group -- it adds VMAX-sized tables; it must earn that cost.

## Instrumentation (understand, don't just score) -- read-only, safe during a live run
  python3 control.py analyze <run_dir_or_ckpt>            # growth payoff / expert specialization / compose / fuzzy
Verified to surface real signal: experts specialize by domain (dominant-domain share ~0.50 vs 0.25 redundant),
OOD trajectory around growth events, embedding-neighbor byte-overlap, real fuzzy-correction rate.

## Candidate features (EXPERIMENTAL, all OFF by default) -- isolable arms added to the sweeps
  NN_INIT_K        top-K similarity-weighted neighbor blend for NN-init      (arch sweep: as_nnk)
  CROSSOVER        spawn = crossover of the top-2 experts, not just mutation (eco sweep: eco_xover)
  EXPERT_COORD     each MoE layer's output mixes in a layer-global context   (arch sweep: as_coord)
  UNMERGE          retire tokenizer merges that stopped paying off           (robust sweep: rs_unmerge)
  DIFFICULTY_CURR  feed easier (low-byte-diversity) windows first            (training sweep: ts_diff)
These are unproven -- test them the same way (isolated arm vs base) once the core levers are settled. Prune ruthlessly.

## Results-driven pruning (after the first full run)
Noise floor from 5 identical base runs: OOD spread 0.34 bits (σ0.14) -> deltas under ~0.3 are single-seed noise.
The model OVERTRAINS: best OOD at ~5-11k steps, degrades after. Combining features did NOT compound (all "all-on"
bundles >= base); a ~2.0 floor was hit by many single interventions (they don't stack -- mostly redundant regularizers).

REMOVED (clearly hurt OOD, beyond the noise floor):
  cosine LR (+0.18, dominated by WSD) | z-loss (+0.37) | Lion (+0.48) | reconstruction head (+0.25) | fuzzy tokenizer (+0.40)
  (config knobs + implementations + preset/sweep arms removed; fuzzy/recon method bodies left dormant, unreachable via config)

KEPT -- winners (Δ well beyond noise):
  eco levers (cull/mutation/bottleneck, ALL variants ~-1.3; the specific cull-metric barely matters) -- STRONGEST, most robust
  WSD LR decay (-0.98) | EMA (-0.95) | label-smoothing (-1.00) | multi-token prediction (-1.02) | denoising (-0.89)
  Key mechanism: base grows to 64 experts and stalls; eco culls to ~20 and reaches the ~2.0 floor. GROWTH CONTROL matters most.

KEPT -- near-contenders (marginal or noise-band; retained for a seeded re-test, not yet trusted):
  recursive compositional embeddings (as_cdepth -0.46, the one arch signal above noise) | correction hooks (-0.31)
  compose (-0.14) | NN-init + NN_INIT_K (-0.04, noise) | depth growth (-0.12) | grad-accum (utility, memory)

KEPT -- untested candidates (never ran; the mechanisms that would actually test modular COMPOSITION):
  CROSSOVER | EXPERT_COORD | UNMERGE | DIFFICULTY_CURR

NEXT: seed-repeated confirmation (eco alone vs eco+one regularizer, 2-3 seeds, ~8k steps + early-stop), since the winners
are non-additive with eco and may be redundant. And a proper test of ORTHOGONAL (not redundant) mechanisms for compounding.
