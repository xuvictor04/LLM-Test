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

## Owner's instruction, 2026-09-25 (supersedes parts of Proposal 03)
> "I don't like the idea of frozen codecs, I don't want anything frozen or fixed unless absolutely
> necessary. I am also reconsidering the hz. Otherwise things look pretty good."

- The frozen codec (AUD_FREEZE_AT) and the hand-fixed 25 Hz in 03 are **rejected**. The rest of 03 stands.
- "Frozen" here means LEARNED things frozen or fixed. Frozen Configs and frozen entry-point signatures
  are software contracts and stay.
- Finding: the TEXT tokenizer is already effectively frozen at RUN_EPOCHS=1. Minted ids never reach
  training data because every retok waits for an epoch roll (Q-RUN-8), and TOK_RETOK_EVERY decides
  nothing at any epoch count. A live codec and an adaptive rate need the same mid-epoch
  re-segmentation (Q-RUN-8 option a), so that mechanism is now a prerequisite.
- DONE: design workflow wf_ba08e76a-a28. Evidence is in results/live_codec_design_2026-09-25/
  (eac5e59). The judge picked D3 (EMA teacher + lattice-coordinate rows + nested multi-rate) with
  D1's act mechanics grafted on. The critic returned sound-with-fixes: 1 blocking (resume vs mint
  cadence) and 9 major.
- Decisions taken on the critic's open points (applied by the revision workflow wf_c04d7ab1-d11):
  - D-1: resume segments at vocab.rev as of the last act.
  - D-2: AUD_ARCH 'spec' is the default; 'nested' is an arm.
  - D-3: AUD_RATE_MODE='measured' picks the stride from rate-distortion at readiness, before any
    media is consumed.
  - D-4: default plasticity is the regime measured to cost nothing (D1 low-plasticity), and
    AUD_REWARM is off.
  - D-5: codes come from a snapshot refreshed at each act; EMA just-in-time is an arm.
  - D-6: coordinate rows are the default, justified as sample efficiency, with media rehearsal
    0.25 and 'table' kept as an arm.
  - D-7: anchor on, with 0 as an arm.
  - D-8: SIG sees media through lattice coordinates, and every snapshot refresh stamps a shift.
  - D-9: the splice goes after the unit under the cursor, and TOK owns it.
  - D-10: labels are honest about seeds and budget.
- wf_c04d7ab1-d11 is DONE: .../scratchpad/mm2/rev/03_live_codec.md (228k chars) and checklist.md.
  The last fix pass was never re-checked, so verify loop wf_68221f90-158 is IN FLIGHT and must end
  on a clean check. Plan: commit it as docs/proposals/03b_LIVE_CODEC.md (binding over 03), and copy
  rev/{probe_time,audit_d1}.{py,txt} to results/live_codec_design_2026-09-25/prototypes/rev/.
- (history) wf_c04d7ab1-d11 wrote the revised §0b plus section deltas to
  .../scratchpad/mm2/rev/03_live_codec.md and checks them. Next: fold that into
  docs/proposals/03_AUDIO_VIDEO.md, then report to the owner.

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
