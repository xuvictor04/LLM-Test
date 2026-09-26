# Fix log for dec/DECISIONS.md

## Round 1 (FIXER), 2026-09-26

I checked every major finding against its source before applying it, and rejected none. Minor
findings were applied where the fix fit in a line or a clause. The document went from 1204 to 1238
lines. The growth is the corrected-conclusions block in §3.2 (instructed), O16-O18, and two
Appendix C rows. Table column counts were re-checked by script, and every row is consistent.

### Verification done before applying
- **O11, 7.2%.** Read `docs/proposals/04_SELF_REGULATION.md:587-591`. 24 extra windows every 333
  windows is 7.2% more windows. With a forward costing 1/3 of a step that is 2.4% of wall; at the
  toy's 4.3%-of-wall per 15%-extra-windows ratio (0.29) it is 2.1% of wall. Confirmed.
- **Full-run WORLD statistic.** `docs/04_CONTRACT.md:3563-3567` quotes the full run for all three
  arms. Confirmed.
- **FAB blackout counters.** `src/fabric/api.py:4310-4311`, `:4411`, `:4442` and `:4619` (Gate
  `fab.growth_blackout`) exist, so the tree already counts suppressed growth passes. 400/cadence is an
  upper bound. Confirmed.
- **02-R11.** `.rework/ISSUES.md:32` marks P1-C3 "(unverified)". `src/fabric/api.py:1699-1701`
  applies `hold_out`. `:3339-3370` raises `NotImplementedError`. `src/spine/compose.py:1808-1818`
  names three missing producers, including the memory-off `baseline_logits_fn`. Confirmed.
- **E1-E6 shape.** `docs/proposals/04_SELF_REGULATION.md:1452-1455` states one run shape for every
  GPU experiment, and E2's row at `:1507` times the 17 MB tail. Confirmed.
- **`CKPT_BEST_KEEP` 0.** `src/ckpt/levers.py:256-262` and `src/ckpt/api.py:1125-1128` say 0 means
  a single rotating `.best`, not "off". Confirmed.
- **ε basis.** I re-ran `rule_self_regulation/paired.py`. The six-area mean's MDE is 0.05295. Per
  area, (2.132+0.941)·sd/√5 gives easy 0.072, cred 0.086 and hard 0.176. Confirmed.
- **D8.** `.rework/DECISIONS.md:108-112` is the owner's ruling "make planned default". Confirmed.
- **03b caveats.** Read `docs/proposals/03b_LIVE_CODEC.md:64`, `:108` and `:246-252`. Confirmed.
- **Draft priority order.** `result.json` conflicts.priority_order already had "R1 bounds R2 ...
  (the ADR form)". Confirmed.
- **FAB_MUT and jitter.** `src/fabric/levers.py:686-713` gives mechanical reasons for both.
  Confirmed.
- **`fab.cap` MAY_WIDEN.** Found in `src/spine/compose.py` in the 3238-3300 block. Confirmed.
- **`LM.anchor_term`.** `src/lm/api.py:908-915` holds minted tokens near their byte composite; there
  is no snapshot. Confirmed.
- **`gpu_world.sh`.** Lines `:67-70` and `:144` show that a plain `BYTES=` override raises "RAN OUT
  OF STREAM". Confirmed.
- **The rest.** For the remaining minor findings I checked the verifiers' scratch
  (`verify/emp/lr.py`, `k1000_1300.log`, `pc_*_s0.txt`) and the arithmetic, and all hold.

### Applied (major)
1. **O11 / C03 / 04-6.2 / C31 / App A 20.** The claim now reads "about 7.2% extra forward windows,
   about 2.1-2.4% of wall, marginally above E6's 2% cap". O11 stays an owner item.
2. **§3.2 PENDING-WORLD_FEEDBACK and App A 15.** They now say "the ruling applied the last-half
   statistic only; the full-run column (`04_CONTRACT.md:3565`) was not weighed".
3. **03b-16.26 (§3.2 row, register row, note, secondaries (c), §8 1.3).** They name the existing
   `fab.growth_blackout_suppressed.{regression,stall}` counters and Gate. `fab.blackout_windows`
   extends them rather than adding a parallel surface. 40% and 13% are labelled "up to, by
   construction" wherever they appeared (03b-16.15, S0b hazards).
4. **02-R11.** It is restated as "build `FAB.contribution` and its producers after NEW-03". The claim
   that P1-C3 carries over to the new tree is dropped, with cites. §8 1.7 moved to a new 3.5 after
   3.2. The C37 deferral is the NOW action (02-R11, C37, §3.2).
5. **Irreversible closures (two findings).**
   - New O17, the position-table door. C43, NEW-13, §2 R4 and App A 12 are tagged O17.
   - The 8 kHz grid is removed from §1's closure list: 03b-16.13's new-block route makes a change
     reversible. 03b-16.13 now says so.
   - I chose not to add an audio-grid O-item. The grid is only reversible because of the new-block
     route, so an O-item would contradict 03b-16.13's own ruling.
6. **E2-E6 resize.**
   - §3.1 #8, 04-Q1 note 7, App A 2 and §8 0.4 now cover E1-E6. 0.4's "Decides" column lists
     04-Q6/Q7/Q13 and NEW-10.
   - §8 5.3 marks E2 at whole-epoch sizing.
   - The E2 splice-cost comparison was re-derived at 3.78 MB (see minor 13).
7. **04-Q10, §1 and §5 fact 4.** The best-checkpoint anchor is "live once `consider` is fed and
   `CKPT_DIR` is set". "No best checkpoint" is attributed to the deferred `Retention.consider`. The
   same fix went into LOW-Q-TOK-13-PREV and note 03-16.1.
8. **O2 and 04-Q1 note 2.** 0.05 is relabelled as the all-area-mean MDE. Per-area MDEs of 0.07-0.18
   are stated, with the consequence for NEW-02 sizing.
9. **O16 (D8 collision).**
   - New O16: the training-run `DATA_DRAW` default, 'replay' 0.27 once SR0 builds it versus
     'planned' per D8.
   - 04-Q1, §3.2 and App B are tagged O16.
   - It also states that the flip changes every default run (minor finding 21).
10. **E1's primary endpoint.**
    - Note 04-Q1 item 1 now makes the time-integrated all-area gap primary, with shape (e) read
      after its continuation.
    - Item 3 demotes the end-state mean to a tie-break after 04-Q2 (R5).
    - Note WORLD 4(a) now tests on the time-integrated gap, with end-state reported beside it.
    - §3.2's 04-Q1 row is updated, and the "tie" MDE sentence now gives both figures (0.042
      time-integrated, from paired.py's TIG sd 0.0302; 0.053 end-state).
11. **03b-16.17.** 'table' returns if coord's BWT or worst media-area regression is worse by more
    than ε, whatever the end-level gain.
12. **The `OPT_LR_CONTINUE` interim.**
    - App B now reads "no value until §8 4.2 reads (O6)".
    - O6 is reworded as the choice among 4.2's arms under R1-as-budget, with the downgrade framing
      qualified (minor 4 and 22).
    - C01 says "no interim value", and its rule label is changed to R1-as-budget.
13. **NEW-10 / Q-FAB-5 / C37 / App A 9.**
    - The arms run in E2 only (§8 5.3).
    - The occupancy-by-area and faded-cull counters are built with SR0 (§8 3.1). The retok fleet
      runs before they exist.
14. **O18.** New item: `DATA_SRC_CAP` and the trust floor's N. The recommendation is about 25
    documents' worth of bytes per unpromoted origin per session (a tenth of the ~250-document figure,
    provisional), with N equal to the cap. The alternative is no cap and one pass per session.
    - App B, NEW-07 and its note are tagged.
    - §8 0.1 and App A 5 now say O1-O18.
    - **The owner should check this recommendation.** It is a provisional number with no
      measurement behind it.

### Applied (minor)
- **§3.1 #5 and O6.** The 0.53-0.61 range is qualified as holding for one more equal-length epoch.
  O6 adds that parents with a revision log are already at the floor.
- **03b-16.33 (both places).** Now reads "run average +5.0% k1000 arm vs k0 arm (three acts); +6.8%
  post-act is an estimate; measured first act +8% locally, +4.2% whole tail". The trigger's firing
  depends on the reading, and the owed ruling is unchanged.
- **Q-OPT-3.** Now "about 102,000-105,000 windows (seed-dependent)".
- **Note secondaries (a).**
  - Added the whole-epoch figures: k1000 about 18 s of splice, k3000 about 6 s, at most about 3.4%
    and 1% of wall at 38 windows/s, and about 20 s to resume.
  - Corrected 165 to 163, and "under 2%" to "0.5-2.4%".
  - C36 gives both shapes. 04-Q9 carries the whole-epoch comparison.
- **§5 fact 7.** `fab.cap` is added to the MAY_WIDEN list.
- **04-Q5 risk.** Now reads "a 5% smaller synthetic body; training bytes unchanged".
- **Dropped caveats.**
  - 03b-16.24 and C45 now carry the 64-clip, one-beyond-noise and tones/contour qualifiers.
  - C44 and 03b-16.14 carry "weakly" and why, and C44's risk reads "possibly".
  - Note 03b-16.14 adds "4 live seeds against a single frozen reading, not pairs".
- **§3.2 04-Q2.** It is now R-1-aware and labelled as toy.
- **04-Q4.** The lever count is dropped.
- **S0b-ship evidence.** It cites `s0b/preq_eq.py` and `s0b/eq/*.json`. App C lists them with their
  true location, beside `dec/`, along with `verify/emp/`.
- **03-16.9.** The anchor arm is declared as a new snapshot-anchor term, not `LM.anchor_term`.
- **Note WORLD 3.** It recommends an `EXP=world_epoch` sizing (added to §8 1.5) and explains why a
  plain `BYTES=` override misfires.
- **Q-CAP-2.** Now reads "mean use reaches grace 48 at ≈ 12,288 windows".
- **`critic/td_stress.py`.** Prefixed with its results path in 04-Q8 and §8 0.6. The other bare
  `d2/…` and `judge/…` cites are unambiguous in context (each sits beside a results-folder cite), so
  they are left.
- **[OWNER] markers.** NEW-04 (O10), Q-DATA-7 continue (O9), App B `EVAL_RETENTION_EVERY` preset
  (O11) and NEW-12 (O3).
- **O1 alternative.** Now reads "A-openness above flexibility (it too made R1 a budget)".
- **§7.1 row 5.** It gives the mechanical reasons for `FAB_MUT` and jitter, not "history and
  belief".
- **§7.2 NEW-11 status.** Corrected.
- **03b-16.22 test cell.** Carries the 18-sites / 17-execute / 17-PASS reconciliation. App A 23
  points to it.
- **C18 rule label.** Now "The owner's trade (O7): R1 against R4".
- **Stage 5 reordered.** 5.2 is now the B-safety instruments (E6, E3, E5 once SR6 exists), ahead of
  E2 (5.3) and E1 (5.4). E4 moves to 5.6. Cross-references in App A 9 and 11 are updated.
- **FRAME (2) and Q-DATA-7.** Both spell out `DATA_DRAW='replay'`, `DATA_REPLAY_SHARE` 0.27 and
  `DATA_REHEARSE_PARENT` True.
- **NEW-10 a9d7258.** Now "the old tree's phased run a9d7258, recorded in
  `notes/05_ERRORS.md:602-607`".

### Outside the findings (one factual update)
- **The CPU S0b seed-1 pair has finished.** The results are in `scratchpad/s0b/eq/s1_k0.json` and
  `s1_k1000.json`, same script and settings, written 18:07-18:08:
  - k0: 2.78799 over 3895 windows;
  - k1000: 2.79578 over 3721 windows, 3 acts;
  - difference: +0.0078, against seed 0's +0.0003.

  I recorded this in the S0b-ship evidence, the decisive-test cell, PENDING-CPU-S0b-SEED1 (now just
  the two nuisance runs), §7.2 and §8 0.3. There is still no nuisance margin, so M is unknown and
  nothing is concluded from it.

### Not changed
- The §3.2 lead block states the two corrected fleet conclusions: what the WORLD fleet measured, and
  that its seeds varied the data. It uses the checkers' confirmed facts.
- LOW-D-A13 keeps its banner condition. The archive is not in the repo, and the condition costs the
  owner one log read.

## Round 2 (FIXER), 2026-09-26

I checked all 37 findings against their sources and rejected none. On two findings I changed the
direction of the fix, and both are explained below. The document went from 1238 to 1272 lines. The
growth comes from the rows and cites the findings asked for: five Appendix B rows, one Appendix C
row plus the code list, N3/N4, and the phase-split text. I tightened and reflowed the paragraphs I
touched. A script re-checked table column counts, and every table is consistent. The pre-round copy
is `verify/DECISIONS.round2.before.md`. The edits are scripted in `verify/patch_round2.py` and
`patch_round2b.py`, and each replacement was asserted to match exactly once.

### Verification done before applying
- **Phases at HEAD (F1).** I read `verify/emp2/actsim.py` and its outputs.
  - Its k1000 run matches `verify/emp/k1000_1300.log` bit for bit: act at window 1001, vocab 542,
    13443285 → 12902198 ids.
  - At k3000: 5,188,394 B (seed 0) and 5,192,282 B (seed 1) read by window 20000. The 5 MB bound is
    crossed at window 19,208 (seed 0).
  - The whole-tail change at the first k3000 act is +8.8%, computed on tail ids: 13,059,157 →
    12,000,056 after subtracting 3001 × 128 prefix ids. The whole-stream ratio (+8.6%) is not the
    right figure. Bytes per window over the next 3000 windows is +18-19% after the first act and
    +62-63% after the fifth.
- **Seeds (F2, F23).** `seedvar.out` gives the same three per-seed hashes at HEAD and at `d97779d`.
  `git show d97779d:gpu_world.sh` line 346 passes `RUN_SEED`.
- **ρ at cap (F3).** I grepped `focus.rho_cap_binds` / `rehearse_fired` in all d3/judge/repro
  outputs:
  - focus, fulltd and act6: 26-47 of 48-49;
  - tags: 1-4;
  - full_s1: 3;
  - rehearse: 1.
- **Continuation LR (F4).** `lrcont.out` case C: 0.9169 → 0.092.
- **Replay record (F6).** `src/spine/loop.py:448-450` and `compose.py:2299-2330` show an event log
  (kind, at, view, rng). 03b:415 is the per-position design.
- **Composition n (F8).**
  - `design-world/proto/make_data.py:8` builds 200 combo prompts.
  - stage3 combo exact is 0-0.15 (0.03 for prefix_world_8).
  - design-hybrid `lm_mask.json` has held-out n of 16 (understand) and 12 (generate).
- **Probe floor (F9).** 04:584-585: the first fire is at window 1001. 945,000 / 189.62 = 4,984
  windows, so phase 1 gets 4 readings.
- **Other sources.**
  - `.rework/DECISIONS.md:95` (D2 quote).
  - `.rework/PLAN.md:155` (L1).
  - `04_SELF_REGULATION.md:541` (54%, §1 item 5).
  - `notes/01_TIMELINE.md:343` (79dac6c caveat).
  - 03b:472 (tgtgrad, 1 seed).
  - `verify/numbers/lr_check.py`, re-run: 0.0565 / 0.0757 / 0.1072.
  - `notes/AGENT_STATE.md:30-43` (D-1..D-10).

### Applied (major)
1. **F1, phases at the 20 MB shape.** §3.1 #8, note 04-Q1 item 7 and App A #2 now split the claim.
   - At `d97779d` or k0 a run reads 3.75-3.84 MB and stays in phase 1.
   - At HEAD's k3000 it reads about 5.19 MB and fades eng only in its last ~790 windows. Phases 3
     and 4 never come.
   - The validity rule now reads "a run that does not consume the whole epoch is invalid".
2. **F6, 03b-16.22 risk.** The record is acts + 1 events per epoch. What grows is resume time. The
   10 B/position figure is 03b's design for the unbuilt media extension.
3. **F7/F29, SIG trigger (changed direction).** The finding asked to soften "has fired" to "at its
   threshold". The checkers' own actsim shows that at HEAD's default k3000 the first act already
   moves bpt +8.8% (whole tail) and +18% (local), and the fifth act about +62%. So I made 03b-16.33
   and §3.2 match the stronger statement instead:
   - the trigger has fired for default runs;
   - it sits at the 5% line only at the CPU k1000 760 KB shape (+4.2% / +5.0%);
   - PENDING-S0b-SECONDARIES and C27 now say "has fired at HEAD's k3000 cadence".

   This also covers F5.
4. **F8, composition readings.** Note 03-16.4, C23 and §7.1 row 3 are corrected. The design world's
   0.94 → 0.03 at n = 200 is informative. The 03b prototypes (6-12 prompts) and Route 3 (12-16) are
   not. The ruling (pilot first) is kept.
5. **F9, probe floor.** In 04-6.2, 1000 fails the floor: phase 1 gets 4 readings, and acts shorten
   phases. The floor now caps the cadence at the shortest phase's windows / 5 or adds a phase-start
   reading, and E6's arms are checked against it. App A #2 is corrected.
6. **F10/F33, `DATA_SRC_CAP`.** 04-Q12 now reads "per unpromoted origin per session (a training
   run counts as one session; O18)", matching O18 and App B.
7. **F21, D-5 (option b).** Where the D-x decisions came from:
   - `notes/AGENT_STATE.md:30-43` records D-1..D-10 as "decisions taken on the critic's open points
     (applied by the revision workflow)". There is no owner quote. The owner's rulings are quoted
     elsewhere, e.g. "Owner, 2026-09-26: ...".
   - 03b itself says "the revision folded in the critic's fixes under recorded decisions D-1 to
     D-10" (03b:28).

   N3 now states this, with "unless the owner says he took one". 03b-16.23, C14 and C44 are
   relabelled accordingly. AUD_ANCHOR_W is cited as D-4 and D-7, since D-7 is "anchor on".
8. **F22, joint budget (note 03b-16.26).** The note is rewritten as the finding asked:
   - 'opt' stamping is the default;
   - the 20% alarm orders the stamp-scope arm and the k1000 cooldown arm.
9. **F23, seeds.** The §3.2 lead now carries the banner condition, and the contract text is "wrong
   unless the banner shows otherwise".
10. **F24, C18/O7.** The trade is relabelled "R1 against R1": tagged retention against the untagged
    regression on served prompts of unknown origin. O7's reason says so.
11. **F25, preset values.** N4 and C15:
    - Parent-dependent values (the p99 clip, reservoir bytes) are written as numbers into the
      manifest by a printed preset builder at launch.
    - App B / FRAME `EVAL_RETENTION_EVERY` and `CKPT_EVERY` take explicit values: 1000, or 333 at
      k1000, or 667 with media's 2000 refresh.
    - `CKPT_BEST_KEEP` is 2 in App B, FRAME (3) and the NEW-04 note.
12. **F26/F19, E2's rule.** 04-Q6, and 04-Q7 through it, now adopt 0.5 on the worst faded area's
    time-integrated gap (end-state beside it), with no area and not the all-area mean worse than ε.
13. **F27, [OWNER] tags.**
    - O9 in §3.1 #6, FRAME (2), NEW-06 and App B.
    - O13 in PENDING-WORLD_FEEDBACK.
    - O18 in §3.1 #7.
    - O3 in §3.1 #10.

### Applied (minor)
- **F2.** Cites `verify/emp2/seedvar.out` and `d97779d:gpu_world.sh:346`, in §3.2 and LOW-D-A13.
  It adds the mint-budget note. The App C row for `phase_cross.py` is now labelled seed 0.
- **F3.** The ρ-at-cap figure is scoped to the focus/retention arms (tags 1-4), in §3.2 04-Q2 and
  04-6-UNMEASURED.
- **F4.** "A parent that finished its run" appears in §3.1 #5, the §3.2 row and O6. §3.1 #5 notes
  that a stopped act-parent resumes at its own rate.
- **F11.** C37 cites `compose.py:1808-1818`, not P1-C3.
- **F12.** O9 quotes D2 exactly.
- **F13.** 0.06 / 0.07-0.08 / 0.10-0.11, with the warmup-inclusive values.
- **F14.** C04: 36-46% at 4-8 areas (25% at 20).
- **F15.** The 54% figure is cited to 04 §1 item 5.
- **F16.** Added the 79dac6c caveat.
- **F17.** Added "1 seed" and "not pairs".
- **F18.** N4 and C15 cite `.rework/PLAN.md:155`. App C was updated to match.
- **F19/F34.** A tie now has one definition, in 04-Q2 (b) and C25: within ε on the time-integrated
  gap and not significantly different.
- **F20.** The App C code list gained the missing lines, plus `loop.py:448-450`.
- **F28.** NEW-04 now has:
  - KL and flip thresholds calibrated on nuisance pairs (provisional until §8 4.1);
  - a defined canary trip;
  - stability-gap depth as report-only;
  - an App B row.
- **F30.** App A #9 is marked amended. The headers now say three amendments.
- **F31 (added, not dropped).** New `'regulated'` value (built after NEW-04) and `OPT_LR_REWARM`
  (0.5 provisional, arm 1.0), in NEW-05, C01, FRAME (1), §8 4.2 and App B.
- **F32.** The ε-margin rule is scoped to B-endpoint comparisons. Codec-attribute criteria keep
  their SE margins. Changed in the NEW-02 note, C04 and App A #1.
- **F35.** §2 lists the R4 widening as the second difference from the draft. C07 and C42 are
  relabelled in budget form.
- **F36.** NEW-08 goes to §8 4.7 and NEW-09 to 4.2. The composition pilot moved from 0.7 to 4.12;
  old 0.8 is now 0.7, and nothing referenced it.
- **F37.** 02-R1's depth is default 0 (OFF). 02-R10 is a separate max-depth bound. App B gained
  `DATA_SYNTH_HOLDOUT` and the faded-area cull-deferral switch.

### Not changed
- §3.2's WORLD-fleet bullet already ties 3.8 MB to frozen segmentation at `d97779d`, so it stands.
- The whole-epoch recommendation itself stands. F1 only changed which runs the premise describes.

## Round 3 (FIXER), 2026-09-26

Input: the round-2 check (3 checkers; `verify_result.json` round 2): 7 major, 24 minor. All applied;
none left unfixed. Pre-edit snapshot kept out of the archive (the document's history starts here).

### Applied (major)
1. Continuation LR re-priced from the equal-length hypothesis to the measured child epoch
   (`verify/emp3/k0_epoch_child.py`, `k0child_*.out`: 0.476 / 0.217 / 0.050 / 0.050 of peak at
   756 KB / 3.78 MB / 20 MB s0, s1); O6 reframed as "what LR a continuation starts at".
2. E2's splice cost: about 9.3 / 5.5 / 2.6% of wall at `DATA_FOCUS_ACT_EVERY` 3 / 6 / 25
   (`verify/numbers3/e2_splice.py`); 3.4% / 1% kept as retok-fleet figures only.
3. Owner tags: Q-CAP-1 → O19, Q-CAP-2 → O20, the Q-WORLD-10 open list folded into O13; the
   D-1..D-10 confirmation added to §8 0.2; O-count O1-O20.
4. Media cadence 333 at k1000 and in media sessions at k3000; 667 only at `TOK_RETOK_EVERY` 0.
5. 04-Q5's pin rule scoped to the retok fleet; the WORLD re-run runs post-SR0 with the held-out
   data and the probe ON.
6. O11's cost stated as a lower bound that scales with the ε-sized probe.

### Applied (minor)
Seed ranges (5.19-5.23 MB, 790-940 windows); the +4.2% attribution; ρ-at-cap arms named; O2's MDE
cite; 102k-106k windows; mean expert use at the grown population; the EVAL_RETENTION_EVERY floor
remedy; App C cites; `DATA.recover` as planned; note WORLD 2 cites; `loop.py:2262`; "up to +2.3
BLEU"; belief wording (O3's); O7 as R1 against R1; §5 Defaults qualified and App B rows added; §3.3
intro exception; C45's rationale; the retok spike control's maturity; C06's side path; §8 3.6 and
4.13; missing [OWNER] tags; C34 / 03b-16.18 via the session-end gate; O5 / C05 lock rationale;
transport ids as a contract address; owner pronouns (they/them).

## Round 4 (FINAL CHECK, then fixes by hand), 2026-09-26

Checker: one adversarial pass over the round-3 diff (`verify/final/diff.txt`, `wdiff.txt`). All
round-3 fixes verified against their evidence; 1 major, 6 minor new findings, all applied:

1. **Major.** The continuation-LR cells called a full 20 MB epoch "the owner's shape", but the
   register runs the 3.78 MB whole-epoch shape (retok fleet, E1-E6, WORLD re-run), where a finished
   k0 parent resumes at about 0.22 and only act-parents at the floor. §3.1 #5, the §3.2 row, O6
   (recommendation and Why), NEW-05, §5 fact 3, note S0b-ship and App A #3 now say "the floor only
   for a full 20 MB epoch (about 105,000 windows, a shape no planned run uses)".
2. C01: an act-parent with its log suppressed re-prices from its act-shortened epoch, about
   0.37-0.45 of peak at 3.78 MB (`verify/final/c01_actparent_nolog.py`, approximate inputs).
3. 04-6.2 / App B: the phase-start reading alone gives 4 readings in seed 0's 3,709-window third
   phase at k3000 (`verify/final/phase_readings_378.py`); the default takes both remedies (phase-start
   reading plus a cap near 700 written by the pre-registration).
4. Expert population: 2,512-2,564 is a reading at windows 1001-1300, still rising; mean use stays
   above grace 48 only below about 3,330 live experts.
5. Retok fleet (1) and §8 1.5: k0_nuis and k0_rerun save at the same cadence as k0.
6. Plasticity gain probe: OFF until §8 4.6 sets N and cadence (N4); 4.6 now names them.
7. O11: each media area adds about 1.8% forward windows (about 9%, 2.6-3.0% of wall with one audio
   area). §3.3 intro: O19 added to the exceptions that leave an owner ruling standing.
