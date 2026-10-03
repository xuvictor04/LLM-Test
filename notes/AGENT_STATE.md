# Agent state — read this first after a session reset

Updated 2026-10-03 (test 6, E2's shape (b) on real text with O16's draw pair and E3's wall, register §8 6.3b: pre-registered, built, checked on CPU, handed to the owner and reviewed; before it, tests 4 and 5, §8 6.3a and 5.3a) on `rm-predict-DC` (the only branch pushed to; no PRs unless asked).

## Where things stand
- **WORLD_FEEDBACK ships False** (d97779d) on the 20k-window GPU fleet: the forecast was within
  noise (docs/04_CONTRACT.md Q-WORLD-10, results/gpu_world_2026-09-24/ANALYSIS.txt). WORLD stays enabled.
- **GPU slowdown repaired** (4feb65f): FAB.manage's scalar merge scan was n^2/2 device syncs from
  window 501 on. The fix is bit-identical (fabric-internals I10 plus a byte-identical 300-window
  merge-firing run). Post-fix GPU rate (the retok fleet): 35.8-39.2 windows/s per arm, 239 at PAR 12.
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
  DONE as an OPERATION check (owner rule: CPU decides nothing about efficacy): whole-epoch CPU runs
  at 760,000 bytes, seeds 0-1, k0 and k1000: the acts fire, the runs finish finite, bytes are
  accounted (k1000 - k0 = +0.0003 / +0.0078 prequential bits/byte, recorded, not a verdict). The CPU
  nuisance pair is dropped; the ship rule is the GPU fleet. Evidence: results/decisions_2026-09-26/s0b/.
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

## OPERATING MODEL, 2026-09-26 (the owner's words; supersedes "the owner rules O1-O20")
> "In a sense, your session is that of a middle manager. You can resolve most of the questions, or we
> will need to do the testing to figure it out. Maintain documentation standards. Your job is to
> figure out how to do it, and implement it. If something is not working out, keep trying. Just
> because one result was bad does not mean the entire path is impractical or impossible. My job is to
> lead and monitor, ensuring that my goals are not being drifted, and adding new ideas, and expanding
> the project. Exact details of how things are run need to be documented thoroughly for future review
> and reference, but do not have to be brought up directly to me. Brought to me should be major issues
> that threaten the project, potential expansions, and testing (from bashes that you create, and with
> quick copy paste roll out. I want to be up to date, but much of the work will need to be done on
> your end"
- The manager (this agent) resolves decisions, designs, builds, documents, runs CPU operation checks,
  writes GPU scripts and reads their results. Rulings are logged in the repo (Proposal 05 and its
  decision log), not brought to the owner.
- Brought to the owner, in notes/OWNER_BRIEF.md and the chat: major issues that threaten A or B,
  potential expansions, and GPU tests as copy-paste blocks. Results come back as each script's
  "PASTE THIS BACK" block (the GPU box has a checkout but no push token).
- Explicit owner rulings stand (D2, D8, D16, Q-RUN-8's stream rebuilding, WORLD kept for A, the CPU
  rule; the rebuilding cadence is the manager's, O14); a GPU
  result that contradicts one is a major issue for the owner. A bad result is a reason to try the next
  arm, not to drop the path.

## OWNER RULE, 2026-09-26: CPU tests operation, GPU tests whether it works
> "CPU check should only be to test operation ability. To test whether something works, it will
> require a gpu."
- CPU: runs, finite, known answers, bit-identity, resume exactness, counters fire, cost/timing,
  model-free replays of the tree's functions, arithmetic. Never an efficacy verdict.
- Efficacy (which arm is better, retention, plasticity, the belief, preset values) is decided only on
  the owner's GPU. Toy readings may order the GPU queue; they set no default.
- O1-O20 are resolved by the manager: Proposal 05 §3.3 and Appendix D (lean form); the detailed
  drafts and checks are in results/decisions_2026-09-26/rulings/. The owner channel is
  notes/OWNER_BRIEF.md (goals check, major issues, expansions, GPU queue, rulings that touch owner
  rulings). One statistical rule governs every GPU comparison against eps (O2); each test's seeds and
  caps are pre-registered when that test is built. TOK_RETOK_EVERY is the manager's value (the owner
  approved stream rebuilding, not a cadence): the interim 3000 until the retok fleet, 1000 since
  (2026-09-27, provisional until E2's held-out re-read).

## Next
- 2026-09-27: Stage 1 (§8 1.1-1.6) built, reviewed and fixed; full suite green at 253bfa1; 1.5's owed
  items built and reviewed (1bd51c5, 5bffd3f, 7728cd4, e8628e4). The retok fleet (§8 2.1) is READY
  and handed to the owner (notes/OWNER_BRIEF.md test 2). While it runs: Stage 3 (SR0 and the
  scored-system join, NEW-03) is the next build; the spike test's offline analysis waits for the fleet.
- 2026-09-27, later: the owner stopped the first retok attempt. Nothing showed it was alive (every
  step's runs build ~15 s on the CPU before touching the GPU), and a second paste had started a second
  fleet. cd70ed1 adds the operation layer: one fleet per OUT (an flock beside OUT, plus a /proc
  scan), $OUT/STATE with a verdict (`bash gpu_world.sh --status`), a heartbeat every 30 s, a block for
  every stop (`--stop`), a private code copy in $OUT/code, tools/fleet_dash.sh (the dashboard) and
  tools/gpu_launch.sh (checks, then `--go`). The brief's test 2 block now uses the launcher, and the
  fleet waits on the owner's relaunch.
- 2026-09-27, review of cd70ed1/39a351e (14 findings, 12 distinct; each reproduced, then fixed in
  8144701): a Ctrl-C reaches the whole process group, and killed each run_job while its run.py
  (ignoring INT) trained on as an orphan holding the lock under a STOPPED fleet. run_job now ignores INT
  and HUP, the stop also finds runs by GW_FLEET_OUT, and it polls the heartbeat watcher instead of
  `wait`ing for it (bash's wait in the trap blocked until a run ended once the watcher had died of the
  same signal); F20 sends INT and HUP to the group. An analysis that died still ended FINISHED with no
  block; it now ends STOPPED ("STOPPED AT THE ANALYSIS: the analysis failed"). A dead `| tee` pipe cut a
  stop short at rc 0; SIGPIPE is ignored and say writes SUMMARY first. A stop in the analysis waits for
  it and ends FINISHED. The fleet sizes itself by the cores, not by an exported OMP_NUM_THREADS (the
  launcher only says it). Every printed command is absolute (a new terminal opens in /workspace or
  /root). The dashboard: rates never count the startup, "finishing" instead of VANISHED while k0 is
  indexed, this container's CPU (cgroup) instead of the host's load, no colour codes in --html, and a
  pre-STATE fleet analysed afterwards reads DEAD; the launcher FAILs on an ended fleet's orphans.
  Startup is quoted as 15-30 s, longer when the CPU is shared: at the retok shape on this 4-core box
  15-16 s, one alone or four at once when the box was idle (the smoke: 16.2 s, median of 4), and 66-71 s
  each while another job's tests shared the CPU; the review's ~28 s for four at once did not reproduce
  on the idle box, so the texts blame a shared CPU, not the count of runs. The owner stopped the
  container because the GPU showed no sign of work: nothing runs, and the relaunch block (test 2)
  stands, its commands now by absolute path.
- 2026-09-27/28, THE RETOK FLEET READ (§8 2.1 done; the owner's H200 at 319f313, 13 of 13 rc=0;
  results/gpu_retok_2026-09-27/RESULTS.md, verified by two analysts and its verify/): **1000 ships**
  (k1000 PASS per phase, k3000 UNRESOLVED, whole-run 1000 - 3000 upper bound -0.0035), B-provisional
  until E2. TOK_RETOK_EVERY, RETOK_INCUMBENT and PIN_RETOK are 1000; F1-F17 read at
  RETOK_INCUMBENT=3000. O14's choice is pinned to the whole run, as 1bd51c5 built it (every phase
  would have kept 3000; the register says so). C13's alarm tripped (k1000 37.9%): the cooldown arm is
  read against k1000 with bounds (F25), and the cooldown fleet is brief test 3 (5 seeds, its cap; the
  exact command ran on CPU, 21 runs rc=0). The arm prices FAB_COOLDOWN whole: it also spaces growth
  firings, so isolating the blackout needs a k0 cooldown control (not built).
  Named risk for E2: per area, num in phase 4 is +0.10 at 1000. Owed: the spike test's offline
  analysis, the continuation (§8 6.1), an ETA priced by waves and a FILL that fills the last wave.
- 2026-09-28, REVIEW OF THE RETOK FLEET READ (88d3fae, 510c3a5; 8 findings, each reproduced, fixed in
  7d9bea1): a fleet of one cadence never escalates -- the cooldown fleet's FAIL of 1000 reads "does
  not ship; 3000 and the remedy arms run next" (O14, note retok fleet (3)), where it read ESCALATE with
  the act ON at 1000; `--analyze` of an unpacked archive keeps and reads its KEPT.txt, and SUMMARY's
  record says "none here" or "KEEP_CKPT off" (it had deleted KEPT.txt and repacked without it), and a
  committed archive is re-read only on a scratch copy; the launcher's ready line carries every knob set
  (it carried EXP alone: pasted after the cooldown knobs it would have launched the default fleet).
  Docs: the register reads the shipped 1000 (C40, hazards, 03b-16.33, C27; 04-Q9 with E2's splice re-run
  at 16 acts: ACT_EVERY 3 about 12% at 0.96 s per act, 9% at the fleet's measured 0.70-0.74 s; the
  preset's CKPT_EVERY and EVAL_RETENTION_EVERY 333), 03b's per-act probe cost is +106%, O20 and NEW-20
  carry the pool re-read (2 of 13 full with the replicate, 122-1,627 slots free at the end: 6.1's W arm
  tops up a partly free pool), LOW-GPU-WORLD-ETA's raise is not taken (the miss was scheduling),
  EXP=world is unpinned (a re-run that decides names the cadence in EXTRA), and RESULTS.md's heartbeat
  ETA (7.5% late, time left) and spike lateness are corrected, the spikes labelled descriptive. The
  brief's test 3 now says the pause is the pool's growth requests (about 1% of births), spawning
  carrying on.
- 2026-09-28, THE FILE-STRUCTURE REORGANISATION, PHASE A (427ab21-e125e9c, then its review's fixes):
  the old tree is in archive/old-tree/ and runs from there (`cd archive/old-tree`, then its old
  commands); ARCHIVE.md is archive/README.md, which says what each frozen record is, how to run the old
  tree and where every moved path went; .rework/QUESTIONS.md is archive/rework/QUESTIONS.md;
  results/README.md indexes the evidence. PHASE B WAITS FOR THE STAGE 3 MERGE: the run.py sweeps move
  to tools/, the 2026-08 notes corpus and its defaults file to archive/notes/, and the lines in Stage 3
  files that still place the old tree at the root are rewritten. docs/REORGANISATION.md is the plan,
  with every reference to update and the searches that re-find them after the merge.
- 2026-09-28, THE COOLDOWN FLEET READ (§8 2.2; H100 PCIe at 5c28ca4, 21/21 rc=0;
  results/gpu_retok_2026-09-28/RESULTS.md): 1000 stays, FAB_COOLDOWN stays 400 (cd100 null), M 0.079
  (seed 1's late loss drop). Per area num in p4 +0.091 [lower +0.065], FAIL level and not
  pre-registered: E2 decides, and O14's remedy arms are owed (a design before E2). Training-run
  endpoints decide after the loss drop; 5.1 calibrates the between-run SD (note NEW-02). No GPU test
  is ready until SR0.
- 2026-09-28, REVIEW OF THE COOLDOWN FLEET READ (a1df33c, b3f826b; 8 findings, 6 distinct, each
  checked against the files, fixed in eade722): FAB_COOLDOWN stays 400 by C13's rule whatever the arm
  reads, and the arm's null reading only records no measured cost (the brief, C13 and §8 2.2 gave it
  as the reason); M overstates an act arm's spread, but k1000 also leaves k0 before its loss drop
  (note S0b-ship); the 2026-09-27 dev/slow correction holds for k1000 only (k3000's 0.140 is a higher
  relative bar); the cooldown fleet kept no checkpoint and gives §8 6.1 no parent (NEW-20, O20); the
  WORLD re-run reads its time-integrated gaps from 20% of the stream on, phase 1 reported only, its
  seeds from the measured spread (note WORLD 4, §8 6.5).
- 2026-09-27/29, STAGE 3 (SR0) BUILT, REVIEWED AND MERGED (register §8 3.1-3.7, `sr0-build`'s 22
  commits a605b59..951c7f0 merged onto b444456 in edb90de): the retention probe, the synthetic held-out
  block, the observe-mode source-reliability book, the 'replay' draw, FAB.contribution, O17's position
  lever and SR6's copy detection, each built OFF with its review; then DATA_SYNTH_HOLDOUT on,
  EVAL_RETENTION_EVERY 1000 with a read at every phase start and DATA_TRUST 'observe' (b1d31b7, the
  flip). 298 levers, 151 entry points (10 stubs, 18 deferred). A fleet that pairs with pre-flip runs
  pins all three (EXP=retok does); EXP=world_epoch waits on O13's two WORLD levers. No GPU test is
  ready: E2's held-out re-read, E6 and the WORLD re-run need their scripts, the re-run O13's levers too.
- 2026-09-29, THE STAGE 3 MERGE (edb90de, `git merge --no-ff sr0-build`; its message has the detail):
  conflicts in gpu_world.sh, tests/test_gpu_world.py, the register and the brief, both sides kept. In
  the new gpu_world.sh the pins and the probe's disk budget are read off the fleet's code copy
  ($CODE_DIR), EXP=world_epoch's runs pass --probe-series to $OUT/code/run.py, and PIN_RETOK is the
  shipped 1000 (PROBE_EVERY 700 still fits: 701-721 at k1000). sr0's F18/F19 are F27/F28; main's F18-F26
  keep theirs. DECIDED, the flip review's open item 1: a fleet that recorded no pin (launched before the
  flip) gets the analysing checkout's pins on its resume line, and a row says whose (F27, F7);
  results/gpu_retok_2026-09-27/CHECKPOINTS.md says so for that fleet's tars. tools/gpu_launch.sh counts
  the probe's best saves by running the script's budget block (F28), knows PROBE_EVERY, and names O13's
  levers for EXP=world_epoch. Fixtures: none re-recorded. Every workload reproduces on the merged tree
  (no default-cadence workload reaches window 1000, so TOK_RETOK_EVERY's move reaches none), and b444456
  reproduces the six pre-SR0 records unpinned. The whole suite and --mutants pass. NEXT: Phase B
  (docs/REORGANISATION.md), the owed items under Known low items, then Stage 4.
- 2026-09-29, REVIEW OF THE STAGE 3 MERGE (edb90de, 0729af8; 6 findings, each checked against the files,
  fixed in the commit after 0729af8): a retok final is a finished epoch, which RUN_EPOCHS=1 refuses on
  the fleet's checkout and every later one, so CHECKPOINTS.md's resume line adds RUN_EPOCHS=2
  DATA_RESAMPLE=1 to the pins (run on CPU against 319f313's tree); the Stage 3 bullet left the head of
  this file, whose owner quotes the register cites by line (a working rule below); 04, 03b and the
  proposals index say what is built; the contract's §6 lists K14-K16; results/README.md and
  REORGANISATION's *At the merge* are corrected.
- 2026-09-29, THE REORGANISATION'S PHASE B (62f67d5, 61d106f, 0431282; docs/REORGANISATION.md has what
  was checked): the run.py sweeps are tools/sweep_gpu.sh and tools/sweep_world.sh, run from any directory,
  their output still at the root; the 2026-08 notes corpus, its _evidence/ and the old tree's
  CURRENT_DEFAULTS.md are in archive/notes/, so notes/ holds this file and OWNER_BRIEF.md alone
  (notes_check.py scans both folders, still 22 files); the lines in Stage 3 files that placed the old
  tree at the root are dated. The brief has one line for both moves. The whole suite passes, and N5, N7,
  O12 and O13 count what they counted at the merge. NEXT: the owed items under Known low items, then
  Stage 4.
- 2026-09-29, REVIEW OF PHASE B (62f67d5..86a11a5; 4 findings, each checked against the files, fixed in
  the commit after 86a11a5): tools/sweep_world.sh prints its summary's absolute path (started elsewhere,
  the relative one did not resolve), and gives Q-WORLD-10's run as ONLY=feedback_on,feedback_off:
  ONLY=shipped,feedback_off has formed no paired line since d97779d made shipped the feedback_off run
  (a dated note in the contract says so). REORGANISATION's record of 86a11a5 and of fleet_dash.sh
  --once's exit code (0; --status exits 2) are corrected.
- 2026-10-02, TEST 4 READY: E2'S RETOK PART AS ITS OWN FLEET (register §8 6.3a; 981306c pre-registers it,
  49a657d and 8672c89 build it, the commit after them checks it on CPU). `EXP=heldout bash
  tools/gpu_launch.sh --go` runs k0, k1000 and k1000_mn (`TOK_MINT_NOVEL` 1.0, O14's first remedy arm) at
  seeds 0-6 and k0_rerun, one whole synthetic epoch each, every run pinned after EXTRA with its arm
  after the pins, finals kept. Its block reads each area's R reading (memory-off, report half) by the ε
  rule over the four areas, Holm across the two arms; choose()'s remedy branch gives the DECISION, and
  UNRESOLVED below 11 seeds prints a top-up's command (`POOL_WITH`, a new knob) whose block pools both
  fleets only where commit, code, card, torch and shape match. The ETA priced by waves is built for
  every EXP. F28-F31 pin it; the CPU check is results/heldout_prereg_2026-10-02/cpu/ (the contract's
  Q-RUN-8 note). Handed to the owner (brief test 4). NEXT: read its block when it comes back; then the
  first post-training sessions from its finals (§8 4.3 with 5.3's after-training half), and E2's shape
  (b) on real text (§8 6.3).
- 2026-10-02, REVIEW OF 981306c..0dfb8e5 (6 findings, each checked against the code, fixed in the commit
  after 0dfb8e5). The rule reads each of its two looks (the 7 seeds; a top-up's pooled 11) at 0.025,
  Bonferroni over them: at 0.05 a look an arm whose num sits at ε PASSed 7.1% of the time over the two.
  power.py says its cells are about 50% power for one area, and simulates an arm at the cited SDs (a null
  arm PASSes 0.67 at 7 seeds, 0.91 by 11). The block prints the finals' pack command on a `pack:` line of
  its own (a top-up's packs none). The launcher sizes a file at 134 MB at EXP=retok, whose pins keep the
  trust book's sketch out, and 151 elsewhere; both disk checks give a fix that fits the experiment; an unset
  EXP's fix and --status's hint name the brief's current test, EXP=heldout (the launcher's CUR_EXP: change
  both with the brief). results/heldout_prereg_2026-10-02/cpu/ stays 8672c89's record (its rule rows at 0.05
  a look, the pack command inline).
- 2026-10-02, TEST 5 READY: THE FIRST POST-TRAINING SESSIONS (register §8 5.3a). b4174c2 pre-registers it,
  ff80b49 builds the launch, 412e828 writes a boundary row's pairing (Q-EVAL-12), 80135f1 the reader, and
  the commit after them checks it on CPU. `EXP=session ... PARENTS=gpu_heldout_out bash tools/gpu_launch.sh
  --go` resumes test 4's finals onto x5 (P, P_parent, P_twin per parent, W at the fullest), or trains the
  parents first in a parents stage. Its block reads F per old area by the ε rule over the parents, O9's
  choice and a top-up of parents 7-10, and reports the anchor, 5.1's SDs and W. Where it departs from the
  judge's plan, the register's row or the code says why: the twin is OPT_LR x 1.0001 (the jitter is read
  only at growth births); each look is at 0.025; W's slots are max(the parent's, n_live + 2048), since a
  resume may widen FAB's slots but never shrink them (src/ckpt/api.py); and the pairing is written on a
  resume or boundary row alone, so a fresh run's series is unchanged. F32-F34 pin it; the CPU check is
  results/session_prereg_2026-10-02/cpu/ (the contract's Q-DATA-7 note). Handed to the owner as brief
  test 5, to run after test 4's blocks. A tiny CPU EXP=heldout fleet at 80135f1 writes cce2d39's curves,
  series and finals byte for byte, its blocks differing only in the commit, the launch and measured seconds
  (cpu/heldout_identity.out). NEXT: read test 4's block, then test 5's; E2's shape (b) on real text (§8
  6.3), whose finals are 6.1's parents.
- 2026-10-02, REVIEW OF b4174c2..b2dba7c (test 5; 3 findings, each checked against the code, fixed in cc17cc3
  and the commit after it; none is wrong). F subtracted the start read at the parent's last cut, but a session cuts
  its epoch at the restored vocabulary, which holds the ids its parent minted after that cut (6, 24, 0, 0, 6, 0, 6
  at seeds 0-6 at test 4's shape; up to 10.9% of c's held-out bytes), in no window either trained: a toy session
  that learned nothing read py -0.437. spine/loop.py now reads a resume's start again at its own first cut
  where that is another view ('resume_own', Q-EVAL-12's amendment), F subtracts it, and the block reports each
  parent's count and what they moved (sessreplay.py counts them; cpu/latecut.out: that session reads 0.000;
  cpu/late_checks.out: a CPU fleet whose parents mint after their last cut, end to end).
  gpu_world.sh prices W's checkpoints at W's own size (it priced every file at W's: about 26 GB where the
  launcher passed at 19.9), the launcher W's at (slots + W_HEADROOM) / slots. The brief's test 5 block has test
  4's clone line, "set R to yours" and a line that unpacks test 4's finals. EXP=heldout's output is byte for
  byte cce2d39's at the fix (cpu/heldout_identity.out): test 4, running at cce2d39, is untouched.
- 2026-10-03, TEST 6 READY: E2'S SHAPE (b) ON REAL TEXT, WITH O16'S DRAW PAIR AND E3'S WALL (register §8 6.3b).
  75e2210 pre-registers it, d166cd0 builds the launch, 2bb0dac the reader, 10724cd a fix its CPU check found, and
  the commit after them checks it on CPU. `EXP=heldout HELDOUT_SOURCE=real SEEDS='0 1 2 3 4 5 6' FILL=0 bash
  tools/gpu_launch.sh --go` runs k0, S (`SHIP_ARM`: 6.3a's shipped configuration, k1000 or k1000_mn) and S_replay (S
  at 'replay' 0.27) at seeds 0-6 and k0_rerun, one whole real-text epoch of 3,780,000 bytes each, into
  gpu_heldout_real_out (test 4's gpu_heldout_out, test 5's parents, is never moved). Its block reads O14 (S against
  k0 per area, 6.3a's rule at one arm) and O16 (S_replay against S, CONFIRMed where every area's upper bound is
  within ε and the time-integrated gap's is below 0; a CONFIRM goes to the owner), each look at 0.025, and E3 (the
  book's seconds over the loop's, against 2%), and packs S's finals, 6.1's real-text parents. Where it departs from
  the judge's plan the register's row says why: the probe at 650 (S's shortest phase / 5 is 670), O16's bound at
  0.025 a look, not 95% (a null 'replay' CONFIRMs 7.75% of the time over two looks at 0.05). Its reader sits beside
  6.3a's, routed by SUMMARY's source line: a tiny EXP=heldout fleet is byte for byte cce2d39's
  (cpu/heldout_identity.out), so test 4, running at cce2d39, is untouched. THE CPU CHECK CORRECTED THE REGISTER
  BEFORE ANY FLEET RAN: S and S_replay part at their second flush, not after OPT's warmup, since SIG's pre-loop
  warm-up draws from the whole epoch-0 stream, which 'replay' changes after phase 1 (the row's dated correction;
  O16's reading is unchanged). It also found the block leaving S_replay's data.exposure_max out of its reported
  gates (10724cd). F35-F37 pin it; the CPU check is results/heldout_real_prereg_2026-10-02/cpu/ (the contract's
  Q-RUN-8 note). Handed to the owner as brief test 6, to run after test 4's blocks. NEXT: read test 4's block, then
  5's and 6's; §8 6.1 continues from test 6's finals.
- 2026-10-03, REVIEW OF 75e2210..2d4a9fb (test 6; 5 findings, two of them one, each checked against the code, fixed in
  a9c03d2 and the commit after it; none is wrong). O16's two looks could give opposite DECISIONs: a top-up's block
  read O16 over the pooled 11 alone, so a CONFIRM at 7 seeds, already with the owner, could be followed by "'planned'
  stays", where power.py's 4.10% counts a CONFIRM at either look. The top-up's block now reads the first fleet's own
  seeds again, the first look, and a CONFIRM there stands, the pooled reading beside it deciding nothing. Each rule
  pairs over the seeds where both its runs hold R's reading: O16 read k0's, so a k0 with no endpoint dropped an O16
  pair; and O14's cap counted k0's readings where the top-up's command counts pairs, leaving the seed run in place of
  a dead S past the cap (found beside it). S_replay - S's per-phase prequential line, with a verdict, compared
  training text that differs by draw (27% faded-area bytes in phases 2-4): only O14's S - k0 is reported, as the
  register lists. The brief's test 6 block: about 22 GB of disk if a top-up follows, and a CONFIRM in either block
  stands. F36 and F37 pin it (257 checks). EXP=heldout's output is byte for byte cce2d39's at a9c03d2
  (results/heldout_real_prereg_2026-10-02/cpu/heldout_identity.out); cpu/PASTE_BACK.txt stays 10724cd's record (its
  S_replay - S prequential line, since dropped).
0. Proposal 05 §8 orders everything: Stage 0 (owner rulings O1-O20; the fleet-archive reads; the
   k0_nuis pair; phase-traversal resizing), then Stage 1's small builds (vocab `.prev` rotation, DOM
   Levels, counters, OPT_LR_CONTINUE 'as_logged', gpu_world.sh kept checkpoints) before the owner's
   retok fleet (Stage 2), then SR0 (Stage 3, merged 2026-09-29), then Stage 4. §8 1.5 DONE
   (2026-09-27): `EXP=retok bash gpu_world.sh` keeps k0's checkpoints at the act windows, reports
   rates and secondaries, and ends in a PASTE THIS BACK block plus a .tgz the owner keeps;
   EXP=world_epoch is sized and refuses to run before SR0.
1. The owner rules on 03 §16, or accepts the recommendations.
2. S1 per 03 Appendix A as amended by §0. **Step 0 is the baseline fixture (R7), before any tree edit.**
   Then derive ids/frames, Areas.media, the aud/tones generator plus DATA.recover, and media_batch.
   Sync the K12/K13 counts.
3. DONE 2026-09-27: the fleet throughput re-baseline after 4feb65f rode in the retok fleet.

## Known low items, not yet fixed
- Fixed in Proposal 05 §8 1.6 (2026-09-27), kept here so the old symptoms are recognisable:
  `gate:fab.merged` is now run-scope and the last pass's verdict is `gate:fab.merged_last_pass`
  (Q-FAB-2); every package's save counter is lineage-cumulative with a process `_here` twin
  (Q-CKPT-4); FAB_NORM_ONLY=1 grows, culls and merges nothing (Q-FAB-11).
- OWED from 1.6: FAB_LR_OWN's table reaches no parameter, so 04-Q11 (b)'s sweep arm is inert until a
  consumer exists (a frozen-signature move; docs/04_CONTRACT.md §3.7).
- OWED from 1.6's review: a save CKPT.save refuses as non-finite is still counted on every package's
  save count and `_here` twin, because each state_dict counts before CKPT scans the payload
  (Q-CKPT-4's correction; tests/test_continuation.py S10 pins it as it stands). With saving off no
  payload is built any more, so that half is fixed.
- Q-TOK-13 is open.
- gpu_world.sh calibrates on 150 windows at EXP=world, before the first manage pass at window 501, so
  its ETA can still miss per-pass costs; `--status` gives the live ETA. EXP=retok and EXP=world_epoch
  calibrate on 600 since §8 1.5 (2026-09-27), and the retok fleet's paste-back block prints its ETA
  against wall: past 1.5x, raise EXP=world's default to >= 520 (LOW-GPU-WORLD-ETA). That fleet missed
  by 1.95x at CAL_WINDOWS 600, so the advice does not fit it: 13 runs at PAR 12 left k0_rerun running
  alone from +590 s to +986 s. The register's row records that the raise is not taken (2026-09-28).
  The ETA priced by waves is built (49a657d, 2026-10-02); owed: a FILL that fills a partial last wave.
- OWED, UNBLOCKED BY THE STAGE 3 MERGE (2026-09-29; the lines are the merged tree's). Text: the two
  places in src/fabric/api.py that Q-RUN-17's correction contradicts, grow_check's docstring on the
  stall counter (:5278-5282) and the "WINDOWS, NOT PASSES" comment above its windows count
  (:5443-5445): .stall counts every waiting check inside a blackout, not refused asks, so a quiet
  loss does not read 0 there (k1000 read 1,897-2,726 against 8-10 stall asks); gpu_world.sh:156's
  "paired noise floor" (M decides nothing); the EXP=world_epoch printout (gpu_world.sh:2500-2514, "5
  paired seeds" and the gap over the whole run) to note WORLD 4's endpoint, before O13's build lifts
  its guard; the C13 alarm's COOLDOWN_ARM=100 advice, read null on 2026-09-28 (with
  tests/test_gpu_world.py:506, which pins it); the block's "at PAR" when fewer runs ran, its ETA on
  nominal windows, and "ESTIMATED" on a split the act windows give exactly; src/tok/levers.py:516-522,
  which still calls mint_novel's fail-open bug (ISSUES P1-M77) open, where src/tok/api.py:2275-2290 and
  :2382 hold its fix (and at TOK_MINT_PMIN 0 the fail-open never runs). Code: a FILL guard for a capped
  seed count at EXP=retok (EXP=heldout's FILL is 0; elsewhere a capped command passes FILL=0); per-area
  cells in analyze_retok (EXP=heldout reads per area).
- OWED (EXP=session, low): without PARENTS the disk check prices the sessions' files at the parents' smoke
  checkpoint (91 MB at cpu/late_checks' shape, where a session's is 94) and W's at its bound; the sessions' smoke
  after the parents stage could re-price both before the sessions start.
- Next hunt classes: lever isolation, efficacy vs labels, long-horizon mechanisms, SIGUSR1 saves.

## Working rules this repo has taught
- Never run python with cwd = repo root except run.py and tests/*: the root's data/ shares src/data's
  name, and with the root first on sys.path src/data wins only because it is a regular package
  (tests/test_census.py N5). The old tree's memory.py, which taught the rule by shadowing src/memory
  from the root, is in archive/old-tree/ since 2026-09-28.
- OMP_NUM_THREADS=1. Stage explicit paths, never `git add -A`. test_determinism rewrites
  tests/_noise_floor.json: `git checkout` it afterwards.
- The runs/ folder is never overwritten.
- The register cites this file by line: the owner's words at 16-17, 47, 89-95, 113-122 and 135-136, the
  D-1..D-10 record at 30-43. An edit above `## Next` keeps its line count; new state goes under `## Next`.
