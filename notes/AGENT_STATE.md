# Agent state — read this first after a session reset

Updated 2026-09-25 at `ac94811` on `rm-predict-DC` (the only branch pushed to; no PRs unless asked).

## Where things stand
- **WORLD_FEEDBACK ships False** (d97779d) on the 20k-window GPU fleet: the forecast was within
  noise (docs/04_CONTRACT.md Q-WORLD-10, results/gpu_world_2026-09-24/ANALYSIS.txt). WORLD stays enabled.
- **GPU slowdown repaired** (4feb65f): FAB.manage's scalar merge scan was n^2/2 device syncs from
  window 501 on. The fix is bit-identical (fabric-internals I10 plus a byte-identical 300-window
  merge-firing run). The post-fix GPU rate is **not yet measured**: the owner's next fleet measures it.
- **Audio/video design committed** (ac94811): docs/proposals/03_AUDIO_VIDEO.md. §0 is binding;
  §16 lists the owner's rulings, each with the recommendation that gets built if unruled. Evidence:
  results/multimodal_design_2026-09-25/.

## Next
1. The owner rules on 03 §16, or accepts the recommendations.
2. S1 per 03 Appendix A as amended by §0. **Step 0 is the baseline fixture (R7), before any tree edit.**
   Then derive ids/frames, Areas.media, the aud/tones generator plus DATA.recover, and media_batch.
   Sync the K12/K13 counts.
3. On GPU (the owner): a fleet throughput re-baseline after 4feb65f.

## Known low items, not yet fixed
- The `fab.merged` report line pairs the RUN-TOTAL counter with the LAST-PASS gate, so it prints
  e.g. `('armed-but-zero', 2, 'no pair ... sat within')`. Reporting only; behaviour is unaffected.
- After a resume, the "saved" counters disagree across packages.
- FAB_NORM_ONLY=1 grows one expert.
- Q-TOK-13 is open.
- gpu_world.sh calibrates on 150 windows, before the first manage pass at window 501. Its ETA can
  still miss per-pass costs; `--status` gives the live ETA.
- Next hunt classes: lever isolation, efficacy vs labels, long-horizon mechanisms, SIGUSR1 saves.

## Working rules this repo has taught
- Never run python with cwd = repo root except run.py and tests/*: the root memory.py shadows src/memory.
- OMP_NUM_THREADS=1. Stage explicit paths, never `git add -A`. test_determinism rewrites
  tests/_noise_floor.json: `git checkout` it afterwards.
- The runs/ folder is never overwritten.
