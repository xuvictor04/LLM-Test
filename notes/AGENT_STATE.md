# Agent state — read this first after a session reset

Updated 2026-09-26 (the decision register, Proposal 05) on `rm-predict-DC` (the only branch pushed to; no PRs unless asked).

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
- DONE: docs/proposals/03b_LIVE_CODEC.md is committed, binding over 03. It was verified by
  wf_68221f90-158 (serious findings 7 -> 4 -> 4, tree-fit clean), then by hand fixes and a targeted
  check. Its record is in results/live_codec_design_2026-09-25/prototypes/rev/.
  Owner, 2026-09-26: stream rebuilding (S0b) approved ("a good way for the llm to learn").
  Owner beliefs, to carry into design: SELF-REGULATION (the model regulates where it focuses: the
  frame rate, and in general); CONTEXT AWARENESS (the credibility of sources, and more); EMERGENCE
  preferred over hand-built behaviour.
  S0b step 0 DONE: tests/test_baseline.py plus tests/_baseline_fixture.json (80-window trace at the
  base commit).
  S0b BUILT:
  - 54378b8: the act.
  - c8d8e33: the continuing resume, bit-exact, and gpu_world.sh EXP=retok.
  - next commit: the MEM remap (Q-MEM-13).
  Owed:
  - the owner's GPU ship-rule fleet (EXP=retok bash gpu_world.sh);
  - the CPU regression check in scratch/s0b (4000 windows, seeds 0-1, k0 vs k1000).
  DONE (superseded the 4000-window check, which compared unequal bytes): the CPU equal-bytes pre-read,
  one whole 760,000-byte epoch per run: k1000 - k0 = +0.0003 (seed 0), +0.0078 (seed 1) prequential
  bits/byte; k1000 used 4.5-4.8% fewer windows. Owed: the two k0_nuis runs for a margin (05 §8 0.3).
  Evidence: results/decisions_2026-09-26/s0b/.
  DONE: self-regulation design workflow wf_3b1b5d92-dc4. Evidence is in
  results/self_regulation_design_2026-09-26/. The judge picked d3 (retention-paced focus plus
  claim-level truth discovery) with d2's source tags grafted on. The critic returned
  sound-with-fixes: 1 blocking (at the default of 2 live areas the allocation cannot move) and
  9 major. The honest headline is that self-regulated focus ties a hand-set 27% replay at toy
  scale.
  DONE: docs/proposals/04_SELF_REGULATION.md, revised under decisions R-1..R-10. It went through two
  independent checks: 22 findings, then 2 more, all fixed. Its record is in
  results/self_regulation_design_2026-09-26/prototypes/rev/.
  AWAITING the owner's rulings on 04 §8, including the tie-break: a tie goes to self-regulation.
  The next build is SR0: DATA_DRAW='replay' and the probe as telemetry.
  (history) was IN FLIGHT: self-regulation design workflow wf_3b1b5d92-dc4 (scratch mm3/). It produces
  docs/proposals/04_SELF_REGULATION.md text; commit its evidence under
  results/self_regulation_design_2026-09-26/.
  AWAITING the owner's rulings on the rest of 03b §16. The next build is S0b, the mid-epoch act (Q-RUN-8
  option b-resume), which is text-only and independent of the media rulings.
- (history) wf_c04d7ab1-d11 was DONE: .../scratchpad/mm2/rev/03_live_codec.md (228k chars) and checklist.md.
  The last fix pass was never re-checked, so verify loop wf_68221f90-158 is IN FLIGHT and must end
  on a clean check. Plan: commit it as docs/proposals/03b_LIVE_CODEC.md (binding over 03), and copy
  rev/{probe_time,audit_d1}.{py,txt} to results/live_codec_design_2026-09-25/prototypes/rev/.
- (history) wf_c04d7ab1-d11 wrote the revised §0b plus section deltas to
  .../scratchpad/mm2/rev/03_live_codec.md and checks them. Next: fold that into
  docs/proposals/03_AUDIO_VIDEO.md, then report to the owner.

## THE OWNER'S FUNDAMENTALS, 2026-09-26 (the frame for every decision)
> "A. To build a universal, or universal capable model. That B. Can continually learn, even after
> training, without risking too much. These are the fundamentals. B is a bigger priority than A,
> since the belief is that with B, we can add A later. From there, the architecture is my belief /
> test to get there. Document the decisions, especially if any have conflicts. Ultimately, the
> biggest determiner is going to be actual testing, to see what works. Flexibility is what I'm
> looking for to enhance continual learning, and the challenges of an unreliable system will force
> it to generalize, at least by how I believe it"

- B (keeps learning after training, with bounded risk) ranks above A (universal-capable).
- "The unreliability forces generalization" belief is a hypothesis to honour AND test.
- DONE: docs/proposals/05_DECISIONS.md, the decision register (workflow wf_2f1a0a9c-86c, then the
  verify loop wf_8696bab5-0f5, a round-3 fixer, a round-4 adversarial check fixed by hand). Evidence
  and the fix log: results/decisions_2026-09-26/. It rules 103 inventory items, 45 conflicts and
  NEW-01..19 under the priority order R0 evidence > R1 B-safety (a budget eps) > R2 B-plasticity >
  R3 flexibility serving B > R4 A-openness > R5 current-run performance > R6 cost.
  AWAITING the owner's rulings O1-O20 (§3.3; above all O2, eps and the creep budget) and the
  D-1..D-10 confirmation (§8 0.2).
- Empirical corrections found by the register's checkers (the contract now carries them):
  the 2026-09-24 WORLD fleet read ~3.8 MB of a 20 MB stream, phase 1 (eng + py) only, LR ~0.92 of peak
  at the stop; its seeds did vary the data (D-A13 was already closed); a finished continuation's LR is
  shape-dependent (revision-log parent: floor for good; k0 parent: ~0.48 of peak at 756 KB, ~0.22 at
  3.78 MB, the floor only for a full 20 MB epoch).

## Next
0. Proposal 05 §8 orders everything: Stage 0 (owner rulings O1-O20; the fleet-archive reads; the
   k0_nuis pair; phase-traversal resizing), then Stage 1's small builds (vocab `.prev` rotation, DOM
   Levels, counters, OPT_LR_CONTINUE 'as_logged', gpu_world.sh kept checkpoints) before the owner's
   retok fleet (Stage 2), then SR0 (Stage 3).
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
