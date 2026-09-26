# Proposal 05 — Decision register: B first, A kept open

**Status: decision register. Nothing in it is built.** It rules on every open decision in
Proposals [01](01_MODALITIES.md), [02](02_ROUTER_RECURSION.md), [03](03_AUDIO_VIDEO.md),
[03b](03b_LIVE_CODEC.md) and [04](04_SELF_REGULATION.md). It also rules on the contract questions and
known low items that bear on the owner's two fundamentals, and on 19 new decisions the framing
requires and no document asked. Every ruling is a recommendation. The decisions only the owner can
make are collected in §3.3 and marked **[OWNER]** wherever they appear. Testing decides every other
one: each ruling names its decisive test, whether that test exists or is owed, and who runs it.

**Why it exists.** The owner, 2026-09-26:

> "For the decisions, tell me what would be appropriate under the situation where we want:
> A. To build a universal, or universal capable model.
> That B. Can continually learn, even after training, without risking too much.
> These are the fundamentals. B is a bigger priority than A, since the belief is that with B, we can
> add A later.
> From there, the architecture is my belief / test to get there.
> Document the decisions, especially if any have conflicts. Ultimately, the biggest determiner is
> going to be actual testing, to see what works.
> Flexibility is what I'm looking for to enhance continual learning, and the challenges of an
> unreliable system will force it to generalize, at least by how I believe it"

**How to read it.**
- §1 is the framing and how it is read: what each phrase commits the design to, and where it bites.
- §2 is the priority order used to resolve every conflict, with its justification.
- §3 is the plain-language summary for the owner:
  - §3.1, the ten decisions that matter most for B;
  - §3.2, what changed from the earlier recommendations and why;
  - §3.3, the decisions only the owner can make.
- §4 is the register: one table per group, then notes where a cell is not enough.
- §5 is the new decisions the framing requires, with priority.
- §6 is the conflicts: each with its resolution, the rule used, the residual risk and the test.
- §7 is the owner's unreliability belief: where rulings lean on it, the evidence for and against,
  and the tests that would settle it in this tree.
- §8 is the test plan, grouped by who runs it, in the order that unblocks B soonest.
- Appendix A maps every critic issue to how it was handled. Appendix B states the default of every
  new lever and budget. Appendix C lists the sources.

**How it was produced and checked.**
- **Inventory.** 103 decisions that are open, pending a measurement, superseded, or decided but
  revisable, each with its source lines.
- **Rulings.** Four roles (media; self-regulation; tree and training; pending measurements) ruled
  each item against the framing. They read code, documents and result JSONs, and ran small CPU checks
  from a scratch directory. There were no training runs and no edits to tracked files.
- **Gap finder.** 16 decisions the framing needs that no document asks (NEW-01 to NEW-16). The critic
  added three more needs (NEW-17 to NEW-19).
- **Conflicts.** 45 conflicts (C01-C45), a priority order, and 28 ruling changes.
- **Literature.** A digest on learning after training, the unreliability belief and universality.
  Page fetches were blocked; each claim was checked against an abstract excerpt, an official repo or
  the tree's own documents, and is marked *unverified* otherwise.
- **Critic.** An adversarial review: 2 blocking, 10 major and 11 minor issues, and a 12-item missing
  list. Its fixes are applied in this register. Appendix A maps each one; none was rejected, and three
  were applied with an amendment.
- **This register** is the merge. Where a conflict resolution or a critic fix changed a ruling, the
  register shows only the final ruling, and the Δ column says what moved.

**Every number is traced.**
- Tree facts cite a file and line.
- Toy readings cite their evidence folder under `results/`.
- Arithmetic is marked "(arithmetic)".
- Readings taken by this workflow's scratch scripts cite the script. Those scripts are listed in
  Appendix C and archived under `results/decisions_2026-09-26/`; a bare path such as
  `verify/emp3/acts.py` or `rule_self_regulation/paired.py` is relative to that folder.

**Scale.** Every measurement cited is a CPU toy reading, a single seed, or the one GPU fleet of
2026-09-24. Results are signals, not definitives. The literature disagrees on how forgetting and
modality competition change with scale, so a toy verdict can invert at the owner's scale.

**Legend used in the tables.**
- *Who runs the test:* **[exists]** the measurement exists; **[CPU]** runnable on CPU in a session like
  this one; **[GPU]** the owner's GPU; **[owner]** the owner reads a log or rules, no compute;
  **[none]** a contract ruling that no measurement decides.
- *Δ:* **same** (ruling unchanged from the document's recommendation), **+** (unchanged, with
  additions), **changed**, **new**, **superseded**.
- *Defaults:* ON / OFF is stated for every lever a ruling touches.

---

## 1. The framing, and how it is read

| The owner's words | How they are read | Where they bite in this tree |
|---|---|---|
| "B is a bigger priority than A" | B outranks A in every conflict. | §2's order puts both halves of B, and the flexibility that serves B, above A-openness. |
| "continually learn, even after training" | Learning continues after the main run ends, in deployment or continued training, not only inside a training run. | The tree has no such mode (FRAME-POST-TRAINING, NEW-01). A finished run continues only as a resume that raises `RUN_EPOCHS`, and `RUN_EPOCHS`>1 needs `DATA_RESAMPLE=1` (`src/spine/compose.py:2726-2748`). There is no inference path and no inbox. |
| "without risking too much" | Bounded risk: forgetting, drift, collapse, poisoning by bad inputs, irreversible damage. So reversibility, monitoring and gates. | Nothing says how much is too much (NEW-02). The shipped defaults leave nothing to roll back to: `CKPT_DIR` '' (saving off), `CKPT_EVERY` 0, no best checkpoint can be saved while `CKPT.Retention.consider` is deferred (`src/spine/compose.py:1663-1675`), and the one on-disk older generation (`ckpt.pt.prev`) cannot be resumed (LOW-Q-TOK-13-PREV). |
| "universal, or universal capable" | A is not built now; the architecture must not close doors to modalities or tasks. | Built-OFF arms keep doors open. Irreversible closures go to the owner: a context-locked position table (C43, **O17**). Spending the last 2 wires is owner-routed too, though a `WIRE_BUDGET` raise makes it reversible (03-16.5, **O15**). The 8 kHz grid is not a closure: a grid change goes through a new media block (03b-16.13). |
| "with B, we can add A later" | Adding A is itself a B act: a new modality arrives as a new area after training. | 03-16.1's add-a-modality resume; NEW-14 makes it a standing test. |
| "the architecture is my belief / test to get there" | The architecture is a hypothesis too, and it needs a test against a plain baseline. | NEW-17: an ablation ladder from a plain LM with replay up to the full stack, on B's endpoints. |
| "Flexibility is what I'm looking for to enhance continual learning" | Flexibility is a means to B. | A tie goes to the flexible or self-regulated option if it passes B-safety and is actually exercised (R3, C25). |
| "the challenges of an unreliable system will force it to generalize, at least by how I believe it" | A hypothesis to honour and to test. It is neither established nor dismissed. | §7. It chooses which arms are built and tested first. No default leans on it until the left-out-family reading (R3) reads; then that test (R0), not the belief, sets the default. |
| "the biggest determiner is going to be actual testing" | Pre-registered tests decide. Toy results set defaults and order the tests; they do not close questions. | R0. Every ruling names its test and who runs it (§8). |
| "Document the decisions, especially if any have conflicts" | This register, with conflicts in §6. | 45 conflicts, 28 ruling changes, 23 critic fixes. |

**Standing principles, still in force.** No compromises: never remove or downgrade functionality.
Performance is the deciding factor. Results are signals, not definitives. Nothing frozen or fixed
unless absolutely necessary. Self-regulation for a large part of the system. Context awareness,
including source credibility. Emergence preferred, and it must be observable. Build everything
behind levers; honing picks defaults. Always state defaults (ON/OFF). Recommendations are researched,
with rationale and alternatives.

**How the new framing changes the reading of the old principles.**
- "Performance decides" now means performance on **B's endpoints**: the worst area, time-integrated,
  and read **after further learning**, not the current run's end-state mean (C25, C32).
- "Nothing frozen" now means: **freeze snapshots and instruments, never the live learner** (C27).
  Rollback needs frozen anchors and measurement needs frozen probe sets; both are frozen by design and
  versioned.
- "Never remove functionality" admits gates: **a gate defers or diverts learning, it never deletes
  it** (N1 below; NEW-04).

---

## 2. The priority order

**Constraints N1-N4.** Never traded away. (N for "never", to keep them apart from the conflicts C01-C45 in §6.)
- **N1. Never remove functionality.** Defaults may change; everything stays built and reachable. A
  gate defers or diverts learning; it never deletes it.
- **N2. Nothing in the live learner is frozen** unless id or tensor consistency within a session
  requires it, and then the frozen item names a route by which it can change between sessions.
  Snapshots, probe sets and instruments are frozen by design, and versioned.
- **N3. The owner's explicit rulings stand.** Where one collides with R1, the collision is
  documented and put back to the owner, not overridden. 03b's D-1 to D-10 carry no owner quote (its
  design workflow's decisions, `notes/AGENT_STATE.md:30-43`), so they are revisable under R0
  (03b-16.23, C14, C44) unless the owner says they took one (asked in §8 0.2).
- **N4. Every lever has one stated default.** A protocol is a printed preset of explicit lever values,
  never a mode that computes other levers (the L1 rule, `.rework/PLAN.md:155`, as the contract applies
  it to computed defaults, `docs/04_CONTRACT.md:2557`). A value that depends on the parent (the clip,
  reservoir bytes) is written as a number into the session's manifest by a printed preset builder at
  launch; no lever reads another lever or a mode at run time.

**Tie-break order.** A lower rule applies only where every higher rule is tied or silent.

| Rule | What it protects | How it is applied |
|---|---|---|
| **R0 Evidence** | Testing decides. | A pre-registered measurement on B's endpoints (worst area, time-integrated, read after further learning, paired seeds beyond the nuisance margin) overrides every rule below. Measurement integrity is part of R0: frozen instruments; pairing; pinned levers; held-out data split into a control half and a report half (C11); stream sizing that traverses every phase (Appendix A, critic blocking 2); side paths that leave the learner bit-identical (C06). Toy results set defaults and order tests; they do not close a question. |
| **R1 B-safety** | Bounded, reversible risk. | A snapshot anchor exists before any irreversible change. Worst-area regression stays inside **one owner-set budget ε** (§3.3 O2). Untrusted content is attributed and gated. Monitors have floors. **R1 is a budget, not a lexicographic rule**: inside the budget, R2 is maximised (the ADR form). R1 is never satisfied by freezing the live learner (N2), because a learner that cannot learn fails B. |
| **R2 B-plasticity** | The model keeps learning after training. | No mechanism is tied to an end date. The ability to acquire a new area is measured, as a gain against an absolute reference (NEW-11), and kept. |
| **R3 Flexibility, self-regulation, emergence, where they serve B** | The owner's stated means to B, including the unreliability belief. | A tie goes to the flexible, self-regulated or emergent option only if it passes R1 and is actually exercised, not pinned at a cap (C17, C25). Where a ruling leans on the belief, the belief chooses which arm is built and tested first. No default leans on it until the left-out-family reading (R3) reads; then that test (R0), not the belief, sets the default. |
| **R4 A-openness** | Modalities and tasks stay addable. | Built-OFF arms satisfy it. **An irreversible closure** (for A or for B) is not a tie-break: it is weighed before any reversible cost and goes to the owner. Example: a parent trained with a context-locked position table (C43, O17). |
| **R5 Current-run performance** | The end-state mean of the run in hand. | A late tie-break only. |
| **R6 Cost and elegance** | Wall time, wires, levers, code. | Monitoring cost is priced under R1, not here (C31). |

**Why this order.**
- The owner ranks B above A and qualifies B with "without risking too much". So safety **bounds**
  plasticity rather than competing with it: R1 is the budget and R2 is maximised inside it.
- Both halves of B come before A, because "with B we can add A later".
- Flexibility is stated as a means to continual learning, so it ranks directly under B's two halves
  and above A-openness. It wins only ties, because an untested means must not outrank the end it
  serves.
- A-openness stays above current-run performance because a later measurement cannot reopen a door
  that has been closed. That is also why irreversible closures leave the tie-break altogether.
- "Performance is the deciding factor" and "testing is the biggest determiner" become R0:
  performance measured on B's endpoints decides. Raw end-state performance of the current run is
  kept as a late tie-break (R5).
- The belief is a hypothesis to honour and to test. It steers what is tried (R3) and loses to R1;
  no default leans on it until the left-out-family reading reads, and then the test (R0) sets it.

**This order is itself put to the owner (§3.3 O1).** It differs from the conflicts role's draft in two
places: the draft ranked A-openness (its R3) above flexibility (its R4), and its closure clause
covered A's doors only, where R4 here covers closures for A or B and sends them to the owner. The
critic pointed out that the owner names flexibility as their means to B, and that the draft applied a
different order to tests (R1 > R2 > flexibility-on-B > A) than to decisions. This register uses **one
order for decisions and tests**. In §6, every "rule used" is written under this order; where the draft
said R3 (A-openness) it now says R4, and the reverse.

**How the order applies to testing.** Tests run in the same order (§8):
1. Tests that make B-safety measurable: the per-byte Levels, then the retok fleet with kept
   checkpoints; SR0's probe with NEW-03's two closures; gate calibration against ε; the continuation
   learning-rate arms; the rollback known answers.
2. B-plasticity: the plasticity gain probe and its remedies; replay and reservoir arms.
3. The flexibility and belief families that bear on B, run inside the continue protocol.
4. A: the media stages S3-S8.

Anything that runs on CPU runs in parallel with the GPU queue.

---

## 3. Summary for the owner

### 3.1 The ten decisions that matter most for B

1. **Give B an operating mode: chained sessions launched from a printed `continue` preset.**
   Today the only way to learn after training is "one more epoch" over a redrawn stream. A session is
   a resume with declared new material, its own length in windows or bytes, and a gate at its end.
   The preset is a versioned file of explicit lever values, not a mode that switches defaults.
   Serving uses the last promoted, cooled checkpoint while a shadow learner trains (**[OWNER] O4**).
   → NEW-01, FRAME-POST-TRAINING, C15.
2. **Make learning observable.** One missing callable, the scored-system `logits_fn`, blocks the
   whole observe-and-use side: memory is write-only, no best checkpoint is ever kept, and there is no
   divergence alarm. Build both closures (memory off and on), generation, `CKPT.Retention.consider`
   and a blow-up Reading in the same commit as 04's SR0 probe. Split every held-out block into a
   control half (read by gates and controllers) and a report half (read only for verdicts).
   → NEW-03, 04-6.2, C11.
3. **Put a number on "too much", and size the instrument to it.** The owner sets ε, the worst-area
   regression allowed per session, and a cumulative creep budget (**[OWNER] O2**). Probes are then
   sized so the gate has a family-wise false-rollback rate of at most 5% **and** at least 80% power to
   catch a regression of ε. One pre-registered rule combines the gate's readings. The gate gives its
   verdict at session end, on a cooled branch, after a settle window; that it may act on one
   session's reading rests on **[OWNER] O10**. → NEW-02, NEW-04, C03, C04.
4. **Make rollback real.** Rotate the vocabulary file with `ckpt.pt.prev` now: it is the only older
   generation on disk, and it cannot be resumed today. Feed the probe to `CKPT.Retention.consider`, so
   a best checkpoint can exist. A rollback restores a whole generation (TOK, LM, codec, MEM, DOM,
   FAB, OPT, replay segment). Keep the pre-promotion anchor of every session that admitted a new
   origin. → LOW-Q-TOK-13-PREV, 04-Q10, C09, C35.
5. **Name the continuation learning rate.** Today a finished run continues as one more epoch
   (`RUN_EPOCHS` 2, `DATA_RESAMPLE` 1, `src/spine/compose.py:2726-2748`), re-tokenized with the
   parent's grown vocabulary, and the rate it resumes at is set by the parent's shape, not chosen. A
   parent with a revision log (a tokenizer act fired) resumes at the floor (5% of peak) for good. A
   no-log parent resumes, with no ramp, at the cosine rate for its step E priced against 2·W1, W1
   being its epoch re-tokenized with the grown vocabulary: about 0.48 of peak at the 756 KB CPU
   shape, about 0.22 at the 3.78 MB whole-epoch shape, and the floor only for a full 20 MB epoch
   (about 102,000-106,000 windows, a shape no planned run uses; seeds 0 and 1;
   `verify/emp3/k0_epoch_child.py`, `k0child_*.out`). So at the 3.78 MB whole-epoch shape the
   register runs (the retok fleet, E1-E6, the WORLD re-run), a finished act-parent continues at the
   floor and a finished k0 parent at about 0.22 (an act-parent stopped early resumes at its own
   rate, `verify/emp2/lrcont.py`). A new lever,
   `OPT_LR_CONTINUE`, keeps today's behaviour as its default (labelled on every resume) and lets the
   continue preset choose the rate a session starts at. Cheap CPU arms pick the preset's value before
   it ships (**[OWNER] O6**). Groups born after the anchor (new rows, new experts, media rows) get
   their own warm-up clock. → NEW-05, C01, C02.
6. **Replay after training, carried with the model.** Build `DATA_REHEARSE_PARENT` (default OFF, ON in
   the continue preset; **[OWNER] O9**) and an in-checkpoint replay reservoir kept disjoint from the
   probe set. Pure-add stays the measurement protocol, so the architecture's own retention can still
   be read. → 04-Q4, NEW-06, CONTRACT-Q-DATA-7, C10, C16.
7. **Untrusted input goes to memory first.** New material is written to a quarantine on a read-only
   side path (no optimizer step, no minting, no routing updates), carries its origin, and reaches the
   weights only in a consolidation session after a delay and corroboration by certified-independent
   origins, under per-origin caps and canary probes (**[OWNER] O5**, **O18**). → NEW-07, NEW-18,
   04-Q12, C05-C08.
8. **Size every experiment so its phases actually happen.** At the pre-registered 20 MB /
   20,000-window shape (four 5 MB phases) no run reaches the last phase: with frozen segmentation
   (`d97779d`, or `TOK_RETOK_EVERY=0`) it reads about 3.8 MB and never leaves phase 1; at HEAD's k3000,
   acts raise bytes per window from about 190 to about 307, so it reads about 5.19-5.23 MB and enters
   phase 2 only in its last ~790-940 windows (seeds 0-2; `verify/emp2/actsim.py`,
   `verify/emp3/acts.py`). E1-E6 (04 runs all six at that
   shape), the WORLD re-run and the U-series are resized to one whole epoch, and a run that does not
   consume the whole epoch is reported invalid. → 04-Q1, PENDING-WORLD_FEEDBACK, NEW-12, Appendix A
   (critic blocking 2).
9. **Build the per-byte Levels before the retok fleet, and keep the fleet's checkpoints.** The fleet
   then measures the configuration that will ship, gives the post-repair GPU rate, and leaves
   checkpoints from which the first owner-scale continuation test can start. → TREE-S0b-LEVELS, C12,
   PENDING-GPU-RETOK-FLEET.
10. **Test the belief and the architecture, not only the components.** The U-series ladder reads
    every perturbation family on a family left out of training, including unreliable system
    components (family h; scope **[OWNER] O3**). An ablation ladder tests the whole architecture
    against a plain LM with replay on B's endpoints. → NEW-12, NEW-17, §7.

### 3.2 What changed from the earlier recommendations, and why

**Two conclusions the owner was told are corrected.**
- *What the 2026-09-24 WORLD fleet measured:* prequential loss on a stationary two-area (eng + py)
  synthetic mixture, about 3.8 MB of a 20 MB stream whose phases are 5 MB wide, with segmentation
  frozen (no mid-epoch act at `d97779d`) and the LR still about 0.92 of peak at the stop. No area
  arrived or faded; num and c were never read. Its `WORLD_FEEDBACK` null is about a stationary
  stream, not continual learning (PENDING-WORLD_FEEDBACK).
- *Whether its data varied with the seed:* it did, provided the fleet ran the default synthetic
  source (one log's data banner settles it; LOW-D-A13, §8 0.2). Each seed gives a different stream,
  with the same per-seed hashes at HEAD and `d97779d` (`verify/emp2/seedvar.out`), and the fleet's
  script passes `RUN_SEED` (`d97779d:gpu_world.sh:346`); the identical vocab 1106 and 594 mints per
  seed are the mint budget (512 + 99 × 6), not the text. `docs/04_CONTRACT.md:3575-3577` ("all five
  seeds trained on the same text") is wrong unless the banner shows otherwise; the contract now carries a dated correction under that paragraph.

| Decision | Earlier recommendation | Now | Why |
|---|---|---|---|
| 04-Q1 the draw | E1 decides on the all-area end-state mean; 'planned' until then | The time-integrated gap as E1's primary endpoint (end-state mean a late tie-break), a worst-area guard at ε, a continuation shape (e), trust-gated eligibility for 'retention'. 'replay' 0.27 recommended as the interim training default once SR0 builds it (**[OWNER] O16**: D8 made 'planned' the default). E1 is resized to a whole epoch and runs after the continuation arms and E2. | The endpoint flips the toy verdict: end-state t −0.81 (tie), time-integrated t −4.05 (retention better), easy +0.076 (t 3.24) and cred +0.137 (t 4.90) worse. 'planned' is the only draw that forgets catastrophically (easy forgets 0.9-1.9 bits against under 0.05 with either rehearsing draw). |
| 04-Q2 tie-break | A tie goes to 'retention' | Only if it passes the per-area guard, is not worse time-integrated, and actually regulates (normalised `alloc_freedom`, C17) (**[OWNER] O8**) | Under the draft cap only ρ was regulated; with R-1's relative cap it is unmeasured whether the split moves. On the toy, in the retention arms (the focus, focus_nomir, fulltd, act6 and full_c08 runs) ρ sat at its cap in 26-47 of 48-49 last-phase re-plans; in the full (focus + trust) arm 0-3; with tags grafted, 1-4 (`verify/emp3/toy_stats.out`). |
| 04-Q4 parent rehearsal | No; build only on the owner's word | Build `DATA_REHEARSE_PARENT`, default False; the continue preset sets it True (**[OWNER] O9**) | Without it a child has nothing faded, so no draw can protect the parent's knowledge. |
| 04-Q13 source tags | E4 reads the untagged mean only | E4 also reads worst-area retention on tagged reads; the R1-against-R1 trade (tagged retention vs untagged served use) goes to the owner (**[OWNER] O7**) | A tag present at read cut the faded easy area's forgetting to +0.28 to +0.31 bits/byte, against +1.23 to +1.87 for a never-tagged model, at 3 of 3 seeds (C18). |
| 04-Q10 restart damping | The probe hands OPT the mean bits/byte | A `Reading` with `seed_count`; its main use is the CKPT best-checkpoint producer | OPT refuses to damp at n=1, and `Saves.best` can never be non-zero today (`src/spine/compose.py:1663-1675`). |
| 03-16.3 continuous insert | Judged on understanding | Judged on held-out-combination grounding per FLOP and on BWT | Its 0.94 understanding is in-distribution; held-out-combination exact is 0.03. |
| 03b-16.17 coordinate rows | Flip on current-area bits/s | Flip on BWT and stability-gap depth | Sample efficiency is not retention; coordinate rows raise interference (+42 to +59 bits/s against +34 to +41). |
| 03b-16.33 SIG width | Watch; revisit above 5% bpt drift | An owed decision: a re-derive at a resume boundary | The trigger has fired for default runs: at HEAD's k3000 the first act raises bytes per token +8.8% over the whole re-segmented tail and +18% over the next 3000 windows, about +62% by the fifth act (`verify/emp2/actsim.py`). At the CPU k1000 shape (about 760 KB, three acts) it sits at the 5% line (+2.9 / +3.8 / +4.8% whole tail at its three acts, +5.0% run average; `verify/emp3/acts_tail.py`); +4.2% whole tail at the first k1000 act on the 20 MB stream (`verify/emp/k1000_1300.log`). |
| TREE-OPT_LR_SHIFT_WARM | Read as the literature's re-warm | Reclassified as an attenuation; kept as a stability-gap arm | `_schedule` can only lower the rate (`src/opt/api.py:468-473`). The decayed-rate problem at media arrival moves to born-group clocks (C02). |
| Continuation LR (new) | Not addressed | `OPT_LR_CONTINUE`, default `'as_logged'` (today's behaviour, labelled) | For a parent that finished its run the rate is set by the parent's shape, not chosen: the floor for good with a revision log; without one, the cosine rate for step E against 2·W1 of the epoch re-tokenized with the grown vocabulary (about 0.48 of peak at 756 KB, 0.22 at 3.78 MB, the floor only for a full 20 MB epoch of about 105,000 windows, which no planned run uses; `verify/emp3/k0_epoch_child.py`). At the 3.78 MB whole-epoch shape the register runs, act-parents continue at the floor and k0 parents at about 0.22. |
| FRAME-POST-TRAINING | No design in any document | The `continue` protocol as a printed preset | B's mode did not exist. |
| LOW-Q-TOK-13-PREV | Low, left open | Fix now | It is the only older generation on disk, and it cannot be resumed. |
| 02-R11 leave-one-out | A prerequisite for a hierarchy | Build `FAB.contribution` and its producers right after NEW-03 (§8 3.5); meanwhile, in the continue preset, defer faded-area culls (C37; training runs unchanged, an E2 arm) | At the owner's shape culls are reachable (mean use about 78 selections at the founding 2048 experts, about 62-64 at the 2,512-2,564 live experts measured at windows 1001-1300, still rising (the population at 20k windows is unread, §8 0.2), against grace 48) and their need signal is void: `FAB.contribution` raises `NotImplementedError` and needs NEW-03's memory-off closure. |
| LOW-D-A13 | Re-ask the WORLD test once the corpus varies with the seed | Closed, on condition the owner confirms one fleet log's data banner | The seeding line is present at `7e902ba` and at `d97779d`; seeds 0-2 give distinct corpora at HEAD and at `d97779d` (`verify/emp2/seedvar.out`). |
| PENDING-WORLD_FEEDBACK | Re-test once D-A13 is met | Re-scoped: a whole-epoch, phase-traversing re-run with a retention endpoint, after SR0; both endpoints reported | The 2026-09-24 fleet read phase 1 only, and the ruling applied the last-half statistic only; the full-run column (`docs/04_CONTRACT.md:3565`) was not weighed. |
| S0b ship | The non-inferiority rule | Unchanged rule, with 3000 firing meanwhile (**[OWNER] O14**); DOM Levels built first; provisional until a held-out worst-area re-read | The fleet must measure what will ship; prequential bits/byte cannot see forgetting. |
| CONTRACT-Q-DATA-7 | Default unchanged; one R vs P pair | A measurement protocol and a continue protocol; a third arm, P+replay; 3 seeds | R vs P alone cannot tell whether replay buys anything. |
| NEW-13 context length | (conflicts draft) make `lm.ctx` MAY_WIDEN on the GRU arm now | EXACT until an identity check and a cadence-rescaling known answer exist | A wider context changes what every cadence in windows means. |
| 04-6.2 retention probe | ON at 1000 | + control and report halves, raw series for gates, a floor of 5 readings per phase | Adaptive reuse overfits one probe; R-7's rebase would hide act damage. |
| 03b-16.26 routing under acts | As designed | A blacked-out-windows count now, beside the existing pass counters; a joint blackout alarm across 03b and 04 | FAB growth is blocked up to 40% of windows at k1000 and 13% at k3000 (by construction). `fab.growth_blackout_suppressed.{regression,stall}` counts suppressed growth passes; no counter reports blacked-out windows. |
| 03b-16.23 codec refresh | At every act | Not at redraw-only acts | Keeps codec holds inside the measured 2000-window regime. |

### 3.3 Decisions only the owner can make

Each has a recommendation and its alternative. Where a recommendation needs a build, nothing is built
until the owner rules; the rest of the register assumes the recommendation meanwhile, except where the
recommendation departs from an owner ruling (O9, O13, O16, O19; for O19, D16's table gains no row), which stands until the owner rules (N3).

| # | Decision | Recommendation | Alternative | Why it is the owner's |
|---|---|---|---|---|
| **O1** | The priority order (§2) | (i) Flexibility that serves B ranks above A-openness; (ii) R1 is a budget, and plasticity is maximised inside it. One order for decisions and tests. | The conflicts draft: A-openness above flexibility (it too made R1 a budget). | It ranks the owner's own stated preferences. |
| **O2** | ε, the per-area worst-case regression allowed per session, and the cumulative creep budget | Start at ε = 0.05 bits/byte per area per session, and creep = 0.10 bits/byte against the release anchor (2ε). Both provisional. 0.05 is the toy's minimum detectable effect for the all-area mean at 5 seeds; per area it was 0.07-0.18 (derived by hand from `rule_self_regulation/paired.py`'s per-area SDs as (2.132 + 0.941) × SD / √5; the script prints only the all-area value), so sizing to ε needs many more windows or runs per area than the toy had. The probe is sized to ε, never ε to the probe. | A noise-calibrated budget (k × the probe's SE; NEW-02's draft), or a budget relative to each area's own gain. | It is the owner's definition of "too much". A noise-derived budget widens silently when probes are halved or areas added (C04, critic blocking 1). |
| **O3** | The scope of the unreliability belief | Test it on inputs, targets, sources **and** system components (U-series family h). No default leans on it until the left-out-family reading (R3) reads. | Inputs only (the conflicts draft's C24). | The belief is the owner's; the critic notes "unreliable system" reads most literally as system components. |
| **O4** | Which copy serves after training | The last promoted, cooled checkpoint serves while a shadow learner trains and is promoted at gates. | Serve from the learner. | A product choice that sets how much risk users are exposed to. |
| **O5** | The root of trust | Until SR6 copy detection passes E5's majority-false and impersonation worlds, only owner-trusted origins promote from quarantine to weights. This applies R1 as a lock rather than as a budget because poisoning is not measurable within ε (a backdoor stays invisible to the per-area probe until its trigger appears), so canaries and the SR6 lock are R1's instrument there. | Any origin promotes after the delay, bounded by per-origin caps and canaries. | The cost is that weights learn nothing from untrusted input until SR6 passes. |
| **O6** | What learning rate a continuation (a post-training learning session) starts at: the `continue` preset's `OPT_LR_CONTINUE` | The arm §8 4.2 picks under R1-as-budget (ACC within ε, then the largest new-area gain); the preset has no value until then. Status quo, measured: a finished parent with a revision log (every k3000 run past window 3000) resumes at the floor (0.05 of peak) for good; a finished no-log parent resumes at the cosine rate for its step E priced against 2·W1, W1 being its epoch re-tokenized with the parent's grown vocabulary: about 0.48 of peak at the 756 KB CPU shape, about 0.22 at the 3.78 MB whole-epoch shape, the floor only for a full 20 MB epoch (about 105,000 windows, which no planned run uses; seeds 0 and 1; `verify/emp3/k0_epoch_child.py`, `k0child_*.out`). At the 3.78 MB whole-epoch shape the register runs, 'floor' keeps act-parents' rate and lowers a k0 parent's from about 0.22; 'plateau' (0.1 or 0.25) and 'rewarm' set the rate explicitly, lifting act-parents off the floor; 'regulated' sets it per session from the gate's margin. | Fix a value now without the arms (e.g. 'plateau' 0.25). | It sets, for every session after training, how fast the model learns against how much it risks (R2 against R1's caution). Today's rate is an accident of the parent's shape, not a choice; at the 756 KB shape and at the register's own 3.78 MB shape 'floor' would lower a k0 parent's rate (0.48 or 0.22 → 0.05 of peak), and only the owner can accept that downgrade if the arms pick it. |
| **O7** | Source tags: R1 against R1 (tagged retention vs untagged served use) | E4 reads both sides. ON if tagged worst-area retention improves beyond ε and the untagged cost stays within ε; otherwise both numbers come to the owner. The drop value is part of the same trade and the owner rules on it with the tags: `DATA_TAG_DROP` 0.25 (the built value) buys untagged use with some tagged retention; 0 keeps tagged retention best; E4's ladder 0 / 0.1 / 0.25 / 0.5 reads both. The model's tag comes from provenance, never from content. | E4's current rule (untagged mean only), which keeps tags OFF on the toy. | Both sides are R1, so §2 cannot break the tie: tagged retention against the untagged regression on served prompts of unknown origin, which carry no provenance tag. A tag cuts faded-area forgetting about fivefold but costs +0.051 bits/byte untagged (t 2.56); tag dropout 0.25 trades tagged retention (+0.28 to +0.31 against +0.15 to +0.25 forgetting) for untagged use. The owner asked for context awareness. |
| **O8** | 04-Q2: does a tie go to the self-regulated draw? | Conditional yes (04-Q2). | A tie keeps the simpler hand-set arm. | "Performance decides" against the preference for self-regulation. |
| **O9** | Parent rehearsal (04-Q4) against D2 ("lets keep it as default for now", `.rework/DECISIONS.md:95`) | Pure-add stays the measurement protocol. `DATA_REHEARSE_PARENT` is built with default False and set True by the continue preset. | Leave the lever unbuilt. | Availability of old data is the owner's call; D2 is an owner ruling (N3). |
| **O10** | PLAN 3.8 and the instrument line | Control actions (logged, reversible, bounded by a budget calibrated on multi-seed nuisance runs) may act at n=1. Verdicts (default changes, reported conclusions) keep PLAN 3.8. | PLAN 3.8 covers gates too, in which case a session gate can never act. | It reinterprets a standing rule (C30; `src/eval/levers.py:146-148`). |
| **O11** | Monitoring floors against wall-time caps | Monitoring is priced under R1; floors hold and caps apply above them. C03's cadence rule sets 333 at k1000 and in every media session at the default k3000 (the 2000∪3000 stamp union has 1000-window gaps, `03b_LIVE_CODEC.md:193`), so its cost applies to every media session, not only to k1000. At today's 6 windows per area it is about 7.2% forward windows (4 areas × 6 windows every 333; each media area adds about 1.8% forward windows, so about 9% and 2.6-3.0% of wall with one audio area), 2.1-2.4% of wall (04's forward ≈ 1/3 step; the toy measured 4.3% of wall at 15% extra windows), marginally above E6's 2% cap (arithmetic). It scales linearly with the ε-sized probe from §8 4.1 (O2: many more windows per area than the toy had), so this is a lower bound; the owner's ruling on O11 waits on §8 4.1's reading. | Caps win; monitoring thins. | Throughput against B-safety (C31). |
| **O12** | A frozen control that wins | It comes to the owner as a "necessary?" question, read after further learning, and never becomes the default by itself. | A winning frozen control becomes the default. | "Nothing frozen" against "performance decides" (03b-16.28). |
| **O13** | WORLD, if it costs B's retention; and Q-WORLD-10's "Open for the owner" list (CONTRACT-Q-WORLD-10-OPEN), folded in here | If the phase-traversing re-run shows WORLD costs retention beyond ε, `WORLD_ENABLED` defaults OFF (still built). On the open list: `WORLD_FEEDBACK` stays OFF; an arm that re-enables it carries the forecast magnitude bound (ON in that arm, 10 × ‖h‖ provisional); WORLD's own objectives stay (no `pop(z).detach()` into `world_proj`); aligning MEM's keys with h + forecast is an arm once `MEM.blend` lands. | Keep WORLD ON for A regardless; on the list, the contract's own options (detach, or no bound, as today). | The owner kept WORLD for A (N3, C33); the contract lists these items as open for the owner (`docs/04_CONTRACT.md:3545`). |
| **O14** | The retok interim default | Reaffirm: `TOK_RETOK_EVERY` 3000 keeps firing until the ship rule runs, with every dependent experiment pinning its cadence. | Pause at 0 until measured. | The owner's Q-RUN-8 ruling; it changed every default run past window 3000 before measurement (C40). |
| **O15** | The wire budget at IMG or ROUTE design | Decide the multi-source ruling, or a raise of `WIRE_BUDGET`, at IMG or ROUTE design time, before the last 2 wires are spent. | Wait until the budget is exhausted. | 25 is itself a hand-set number (03-16.5). |
| **O16** | The training-run `DATA_DRAW` default | 'replay' 0.27 once SR0 builds it: 'planned' is the only draw that forgets catastrophically. It changes every default run's stream (at the shipped 4-area schedule eng fades after phase 1); pending fleets pin 'planned'. E1 can overturn it. | 'planned' per D8 until E1 reads (04's own sequencing, `docs/proposals/04_SELF_REGULATION.md:247`). | D8 is the owner's ruling ("make planned default", `.rework/DECISIONS.md:108-112`); the flip collides with it (N3). |
| **O17** | The position-table door (C43, NEW-13) | Build the extrapolating position arm (relative or rotary) before any transformer-arm checkpoint is kept as a long-lived parent; `LM_ARCH` stays 'gru'. | Accept context-locked transformer parents. | An irreversible closure (R4): a parent trained with the learned absolute table is locked to its context for life. |
| **O18** | Per-origin limits in the preset: `DATA_SRC_CAP` and the trust floor's N | Cap each unpromoted origin at about 25 documents' worth of bytes per session (a tenth of the ~250-document poisoning count, in that origin's median document size; provisional until E5's fixed-count-poison world); N equal to that cap, so every capped admission gets a trust pass. | No cap (0) and one trust pass per session, relying on quarantine, corroboration and canaries. | It trades how fast a genuine new source is learned against poisoning exposure, in units of the owner's own documents (NEW-07, C31). |
| **O19** | Extend owner ruling D16 to the wider population: `cap.clamp` UNREACHABLE on six grounds (CONTRACT-Q-CAP-1) | (a) CONFIRM: UNREACHABLE wherever no lift can be held at a hard ceiling, whatever the ground; D16's table gains a row; every arm keeps printing its ground beside the verdict. | (b) SPLIT: UNREACHABLE only where no lift can be earned (26,014 of the 39,148 arm-grounds), armed-but-0 where lifts are earned and lost (13,134). | It amends an owner ruling (D16, "let's soft clamp if a ceiling is overshot", `.rework/DECISIONS.md:388-390`; N3): widening a ruling's population about twofold "is making a decision and not reading one" (`docs/04_CONTRACT.md:1776-1782`). |
| **O20** | The Q-CAP-2 reading at P4 (DECISIONS-Q-CAP-2): the fabric is born at `FAB_N0` 2048, above its cull's settling point 1844, so no soft expert cap passes the startup refusals | (c) holds only as the status quo until the owner rules: no FAB or CAP default moves (`CAP_TARGETS` 'off', so nothing is refused today); at P4, decide from the settling measurement (does the population settle at 1844 from 2048, and how fast); the lean is (a) as an arm. | (a) `FAB_N0` ≤ 1844 (a FAB default, so every record moves); (b) the below-population clause compares against the settled population or fires only on a resume (weakens the refusal on the resume path, the case it exists for). | The source routes it to the owner: "Q-CAP-2 (OPEN, for the owner)", "none is taken here" (`.rework/DECISIONS.md:612`). |

**[OWNER] One confirmation outside the O-list (§8 0.2):** "did you take any of 03b's D-1..D-10?" N3
treats them as revisable only because they carry no owner quote; 03b-16.23's narrowing of D-5 (and
C14, C44) is conditional on the answer.

---

## 4. The register

Each group has one table, then notes for the rows whose ruling needs more room than a cell. The
tables show the **final** ruling, after the conflict resolutions (§6) and the critic's fixes
(Appendix A). "Status" in the inventory sense is folded into Δ: *superseded*, *built* (decided and in
the tree, revisable) or a ruling on an open or pending item.

### 4.1 Media: Proposal 03 §16

| ID | Decision | Ruling and defaults | Δ | Why for B / for A | Risk → guard | Decisive test [who] | Conf. |
|---|---|---|---|---|---|---|---|
| 03-16.1 | Adopt the S0 rulings | Adopt as 03b amends them (note 03-16.1). Ratify 03b's additions together with S0b's already-resolved Q-RUN-16, Q-MEM-13 and Q-OPT-10. Add: the child's manifest records the parent checkpoint as a named rollback anchor. | + | B: the add-a-modality resume is learning after training. A: transport blocks keep media out of BPE ids; IMG index reserved. | A born modality meets a decayed LR → born-group clocks (C02); rehearsal 0.3; the anchor. | None decides a contract. Known answers owed after S3/S4 [CPU]; the goal-B protocol run **as a resume** [GPU] | high |
| 03-16.2 | 25 or 50 Hz | **Superseded** by 03b-16.2. The spectral 25 vs 50 Hz probe readings (44.4% vs 40.3%) are a prior only. | superseded | — | — | 03b S5 (i) [GPU] | high |
| 03-16.3 | Continuous insert for understanding | Build `LM.encode(..., media=None)` at S5, **OFF**, bit-identical at `None`, K=8 latents as a lever. Default stays discrete-only. Judged on grounding per FLOP on **held-out combinations** and on BWT. | changed (metric) | B: a second input path is an interference surface. A: keeps the continuous door open. | It inserts WORLD latents, and WORLD has not earned its cost on text → OFF, exact no-op. | S8 arm (a) moved to S5, 2+ seeds [GPU] | medium |
| 03-16.4 | Composition near zero: scale or variety? | The width × media-seconds sweep, plus a **combination-diversity axis** (about 32 → 100 → 300 trained combinations, held-out combinations fixed) and a **mixed-perturbation arm** (segmentation noise + codec drift + tag drop). At least 100 held-out-combination prompts per area. Attribution rule pre-registered. CPU pilot of the diversity axis first. | + | B: composing speeds acquisition of new areas. A: grounding beyond memorised pairs. | GPU hours → the attribution rule is fixed first. | Diversity pilot, 1-2 seeds [CPU]; App. B S4/S5 (d) plus both axes [GPU] | medium |
| 03-16.5 | Wire budget with VID | Stay inside 25 (21 at audio stages, 23 with VID). Build-time structure travels as build arguments. Deleting the CAP reporting wires (Q-CLOCK-1 (b)) is admissible only after an equivalence known answer (C28). Decide the multi-source ruling or a `WIRE_BUDGET` raise at IMG or ROUTE design (**[OWNER] O15**). | + | A: the last 2 wires are the next modality's. B: neutral. | Silent exhaustion → `tools/sync_counts.py --check` at every stage. | None (contract) | high |
| 03-16.6 | Where generator code lives | Private functions in `data/api.py`, behind DATA levers. The U-series generators (dynamic meaning, corrupted targets, liar and noise shares) go there too. | same | Neutral. | None. | None | high |
| 03-16.7 | A from-scratch perceptual metric | Evaluation only, as a **frozen, versioned instrument**: trained once per real area on held-out data, never updated in a run it measures, never a training loss of the model it grades. Pretrained metrics stay excluded. It is the B gate reading for real media beside the synthetic canaries. An independently trained instance as a loss: OFF arm, after real data exists. Replacing it needs a bridge session (C27). | + | B: real-media learning needs a gate (03's planned `DATA.recover`, S1, returns None for real areas; `docs/proposals/03_AUDIO_VIDEO.md:352`). A: real audio quality. | The learned probe is fragile (2.3% on reconstructions before augmentation) → canaries primary; the metric reports its calibration. | Calibration against recover exact [CPU]; real-area readings [GPU] | medium |
| 03-16.8 | MEM over media | Default text-only: `MEM_MEDIA` **OFF**, media windows skip MEM. The arm moves from S8 #8 to right after S5, once text MEM shows retention with per-source floors. When built: clip references, never codes; re-key at refresh acts; separate floors for media and text; provenance; delete by source. | changed (priority) | B: memory is the lowest-risk write channel after training. A: retrieval over media. | Media crowds text memory; codec drift stales keys → separate floors, re-keys. | A phased run with source floors [CPU/GPU]; S8 (g) [GPU] | medium |
| 03-16.9 | Protecting text when media arrives | Rehearsal: `DATA_TEXT_SHARE` 0.3 in media phases, `DATA_MEDIA_REHEARSE` 1/3 for earlier media. Pure-add is the lower-bound arm. The lr-shield arm is built on OPT's per-group clocks (C02), not on `OPT_LR_SHIFT_WARM`. An **anchor arm** (L2 or KL toward a snapshot of text rows and experts): a new snapshot-anchor term behind its own lever, not `LM.anchor_term`, which holds a minted token near its byte composite (`src/lm/api.py:908-915`). Freezing rejected (a downgrade). Rehearsal continues after training. Per-area probes are read continuously with a recovery window. Replay budgets never add (C16). | + | B: the best-evidenced mechanism in the tree: 25% replay 1.936 → 1.931 bits/byte against 7.846 pure-add (03 §9). A: text keeps improving as modalities arrive. | A self-regulated draw could starve text → a text-share floor under focus. | App. B S4/S5 (e): pure-add / 0.1 / 0.3 / 0.5 / lr-shield / anchor, 5 seeds [GPU] | high |
| 03-16.10 | Envelope-level audio first | Yes for the synthetic families: spectral codec + Griffin-Lim. 'wave' arm at S3 (a); learned-vocoder arm at S8. | same | A: a quality ceiling, kept open by the arms. | Griffin-Lim may cause part of the timbre loss → recover exact is the acceptance metric. | S3 (a); S8 vocoder [GPU] | high |
| 03-16.11 | Codec retraining on real data | **Superseded** by 03b-16.21, with its widened handover scope. | superseded | — | — | S8 (h) [GPU] | high |
| 03-16.12 | Who owns per-modality baselines | FAB owns them; DOM gets a copy. The root converts each value to a segmentation-invariant unit first (03b's R11). Add: a baseline for a born modality is born at the resume and is ABSENT until N readings; running baselines serve routing only, **never** as a forgetting reference; per-byte levels built now (TREE-S0b-LEVELS). | + | B: normalisation stays consistent across acts and resumes, and gates read fixed references. | Per-token levels move at every act today → Levels first. | Level unchanged across an act on fixed text [CPU]; S5 (iii) [GPU] | medium |

**Note 03-16.1 (the S0 rulings as adopted).**
- M1: one `Windows` kind. Unit labels HZ, FRAMES and SAMPLES only.
- Transport ids, fixed for ever: `MEDIA_ID_BASE` 1<<24, `MEDIA_BLOCK` 1<<20, `MODALITY_INDEX` aud 0 /
  vid 1 / img 2 reserved. They are a contract address, not a live-learner quantity, so N2's route
  rule does not bind them; a new modality or a changed block takes a new block index (as 03b-16.13's
  new media block).
- R-CKPT, the absent-field rule. An absent field reads as its declared off value. An add-a-modality
  resume **borns** the LM media rows, the codec tensors, the WORLD media parameters and the OPT codec
  group; each is listed in the LoadReport and under `ckpt.geometry.born.<field>`. Every other absent
  field is still refused. `lm.media_rows` becomes MAY_WIDEN (03b).
- R-SIG: bytes → typed is the only admitted change of `sig.space`.
- R-OPT: a group missing from the checkpoint is created fresh. The 'freeze shift stamp' clause is
  dropped: the codec group never retires except the frozen control's (through `OPT.retire_group`),
  and stamps come from acts.
- Ratified together: 03b's R-LIVE, R-RESUME-AT-ACT, R-RATE, Q-TOK-15, Q-MEM-13, Q-MEM-14, Q-RUN-16,
  Q-LM-13, Q-SIG-3, Q-OPT-10, Q-OPT-11, Q-DOM-4 and Q-CKPT-5. S0b already put Q-RUN-16, Q-MEM-13 and
  Q-OPT-10 in the contract as RESOLVED (`docs/04_CONTRACT.md`, 2026-09-26), so the S0 ruling that
  contains them should be closed with them.
- Conflicts: no best checkpoint can be saved while `CKPT.Retention.consider` is deferred, and
  `CKPT_BEST_KEEP` 0 adds no `.best1..N` slots (NEW-03 and NEW-04 fix this). With the freeze stamp gone and `OPT_LR_SHIFT_WARM` 0, nothing adjusts the LR at
  media arrival, while the LM's cosine is fitted to the run length, so a late arrival meets a decayed
  rate. Born-group clocks (C02) are the fix.

**Note 03-16.4 (the composition sweep and the belief).** This is the design's clearest test of the
owner's belief in its best-supported form (variable mappings above a diversity threshold, §7).
- For: the literature's form (3), Raventos 2023 and Kirsch 2022 in the digest.
- Against, in the tree: every route and arm reads 0-15% on held-out combinations. The design world's
  are informative: exact 0.94 in-distribution against 0.03 on 200 held-out-combination prompts (SE
  about 0.012; `results/multimodal_design_2026-09-25/prototypes/design-world/proto/make_data.py:8`,
  `stage3_*.json`), so composition fails at this scale. The 03b prototypes (6-12 prompts, 03b 0b.2
  Floors) and Route 3 (12-16, `design-hybrid/run_logs/lm_mask*.json`) are uninformative, hence the
  ruling's floor of 100 prompts per area.
- Attribution: width moves composition → scale; the diversity axis moves it at fixed width →
  variety; neither → the architectural arms (continuous insert; WORLD rollout with the free-running
  loss).
- Falsifier of the strong form: the mixed-perturbation arm improves same-family robustness while
  held-out-combination exact does not beat the paired-seed spread at any width.
- Caveats: `EVAL.grounding` (S5) is not built, so nothing in the tree reads composition yet; modality
  competition turns into synergy only at scale, so a toy verdict could invert.

**Note 03-16.9 (the lr-shield).** 03 relied on `OPT_LR_SHIFT_WARM` for the lr-shield and for R13's
re-warm at media arrival. That lever is an attenuation: `_schedule` multiplies the cycle by
`max(min_frac, ramp)` (`src/opt/api.py:468-473`), so it can only lower the rate and ramp back. A real
shield needs a per-group rate scale on text rows and experts, which is the same mechanism as C02's
born-group clocks. The anchor arm sits between rehearsal and freezing: it keeps text rows near a
snapshot without stopping them.

### 4.2 Media: Proposal 03b §16 and §0b items

| ID | Decision | Ruling and defaults | Δ | Why for B / for A | Risk → guard | Decisive test [who] | Conf. |
|---|---|---|---|---|---|---|---|
| 03b-16.2 | How the frame rate is chosen | `AUD_RATE_MODE='measured'`: the coarsest of 50 / 25 / 12.5 Hz whose per-attribute recover exact is within `AUD_RATE_TOL` 0.05 of stride 1, chosen before any media is consumed. 'fixed' stride 2 is the control. 'alloc', 'bpe', 'router', 'measured_arrival' and 04's 'progress' are built **OFF**. 'measured_arrival' is ranked first among the arms under B. S5's clips must fit `LM_CTX` at every candidate stride. | + | B: no LM work is lost at the choice; 'measured_arrival' is the only arm that re-chooses for an area arriving after training. A: no hand-set Hz. | The rule is unprototyped, and noise biases it toward stride 1 (about 26% false-"out" over 5 cells, 03b §6.3) → `aud.rate.false_out_est`; the S3 noise-fixture known answer. | S3 selection known answer [CPU after S3]; S5 (i) at 2 seeds on 2-4 s clips [GPU] | medium |
| 03b-16.13 | Fixed transforms | Grid (`DATA_AUD_SR` 8000, n_fft 512, hop 160 = 50 frames/s) and lattice (`AUD_LEVELS` 8,5,5,5): fixed per run and exact across a resume; learned alternatives ('wave', 'dmel') are arms. Griffin-Lim stays the default until the learned vocoder (S8) wins on recover exact. A grid or lattice change after training goes through a **new media block** (the versioned handover at a new module index), never in place; so the grid is not an irreversible closure, provided that route stays buildable. | + | B: stable addresses under rows that keep learning. A: 8 kHz caps bandwidth at 4 kHz; the new-block route keeps 16/24 kHz audio addable. | A learned vocoder is one more live part (decode-side only). | S8 vocoder; S3 (a) [GPU] | high |
| 03b-16.14 | Codec plasticity | D1's measured regime (note 03b-16.14). Arms: the 1/4 cadence, anchor 0, `'jit_ema'`, high plasticity, the frozen control. Add: a drift-budget reading of `aud.flip_cum`; an OFF arm anchored to a retained release snapshot; provenance and a per-source cap on codec rehearsal and live codec data after training. Its grounds are the owner's "no frozen codecs" (N3), not the belief (C22). | + | B: the codec's schedule (a floor, never zero, no end date) is the tree's only no-end-date schedule, the template for learning after training. A: the codec adapts to new audio without a rerun. | Owner-scale drift is unmeasured; the anchor was measured against at 5 of 6 readings, weakly (C44) → the S3 replica with its own frozen control before the label transfers. | S3 replica: live vs frozen, anchor 0 vs 10, 2 seeds [CPU after S3]; S5 (ii) [GPU]; U-series family (d) R3 | medium |
| 03b-16.15 | Adopt S0b | **Built** (54378b8, c8d8e33, c5768be; Q-RUN-8 RESOLVED). `TOK_RETOK_EVERY` 3000 keeps firing until the ship rule runs (**[OWNER] O14**). The ship measurement adds a held-out reading under a different segmentation (R2/R3), a plasticity probe, and `fab.blackout_windows`. | + | B: vocabulary must keep reaching the stream after training. A: learned segmentation over bytes. | FAB growth blacked out up to 13% of windows at 3000 → the counter. | `tests/test_continuation.py` [exists]; the ship rule (S0b-ship) [GPU] | high |
| 03b-16.16 | The LR horizon after an act | `OPT.revise_horizon` ON, LR-continuous, inert when `cycles_fitted` > 1 or `lr_sched='none'`. Add `OPT_HORIZON_REVISE` (U.FLAG, default True) for **in-run** revision only; it does not touch continuation pricing (NEW-05). After training there is no horizon: a no-end-date schedule is NEW-05's business. | + | B: prevents under-anneal within a run. | None while ON. | S2 of `tests/test_continuation.py` [exists]; revise ON/OFF pair [CPU/GPU] | high |
| 03b-16.17 | Coordinate rows as default | `LM_MEDIA_ROWS` / `SIG_MEDIA_ROWS` 'coord', `DATA_MEDIA_REHEARSE` 1/3; 'table' a live S5 arm. The flip rule reads B: ACC and BWT per media area and the stability-gap depth after refresh acts. 'table' returns if coord's BWT or worst media-area regression is worse than table's by more than ε, whatever the end-level gain (R1 is the budget); the end-level gain only breaks ties inside ε. | changed (metric) | B: acquisition speed against interference (+42 to +59 bits/s against +34 to +41, 03b 0b.2 row 11). A: coordinates compose; later blocks reuse per-digit vectors. | Interference and code-drift sensitivity (6/6) → rehearsal; the snapshot hold. | S5 (iv) at 20k windows, 10× the prototypes' media LM steps [GPU] | medium |
| 03b-16.18 | The codec's acceptance metric | Recover exact per attribute (mel secondary). The guard runs `AUD_CEIL_ACTION='hold'` on calibrated families, 'count' elsewhere; the longest hold is 4000 windows. `AUD_RECON_LOSS='multires'` is built at S3 before `AUD_REWARM` may turn on. Add: the synthetic families stay as permanent **canaries**; an OFF arm pulls the codec back toward the held snapshot at hold expiry (WiSE-FT style). In the continue preset, hold expiry is a **gate event**, decided by the session-end gate (C34). | + | B: the guard defers, never deletes, and the held snapshot is a rollback point. | Count-only until calibrated, so nothing is protected meanwhile → canaries; 03-16.7's metric for real audio. | S3 `{hold, count}` matrix with calibration [CPU after S3]; S5 (ii) [GPU] | medium |
| 03b-16.19 | Should the LM or WORLD shape the codec? | None by default: `AUD_LM_GRAD` OFF. 'rep' (weight 0.1, 1 nat free bits, collapse gauges, VICReg term) and 'input' (continuous route only) are OFF arms; 'full' only on the continuous route. | same | B: joint likelihood coupling collapses latents (D2's tgtgrad, 1 seed: understanding 0.016 vs 0.078), irreversible damage. A: arms keep an LM-aware codec possible. | None at the default. | S8 'rep' arm with collapse gauges [GPU] | high |
| 03b-16.20 | Media geometry | `DATA_MEDIA_GEOMETRY='inline'`; 'windows' an S8 arm. | same | B: one stream, one rehearsal and one resume mechanism. A: interleaved documents. | A long clip straddles windows → `lm.media.ctx_seconds`. | S8 arm [GPU] | high |
| 03b-16.21 | Codec retraining on real data | In-place live adaptation: own loss, rehearsal, snapshot, guard. Re-warm at arrival stays OFF until S3 clears `AUD_REWARM`. The versioned-block handover is widened to an **arm for a large shift** (e.g. the first real-audio area): a new block with nearest-row init, the old block retained as a snapshot. Both need clip references and retained raw data. | changed (scope) | B: the handover is the additive alternative (new parameters instead of overwriting), which the literature says forgets less. | Code meaning drifts under a trained LM at the first real area → canaries, hold, synthetic rehearsal, rollback snapshot. | S8 (h) on a real-audio area [GPU]. No real-audio measurement exists. | low |
| 03b-16.22 | Resume across acts | Option (b), **built** (c8d8e33; Q-RUN-16 RESOLVED): resume from the last act's view, replay record, run-global rev, dropout-stream state and clock. Extend to media at S3/S4. Start a new replay-record segment at each session boundary; compaction is required before an open-ended stream (C36). | + | B: every post-training session is a resume, and bit-exact continuation lets one be stopped, audited, rolled back and restarted. | The record is small: acts + 1 events per epoch, each a kind, position, view and dropout-stream state (`src/spine/loop.py:448-450`, `src/spine/compose.py:2299-2330`). What grows is resume time, linear in acts (C36; secondaries (a)) → per-session segments, compaction. 03b's 10 bytes per position (`docs/proposals/03b_LIVE_CODEC.md:415`) is its design for the unbuilt media extension (S3/S4). | `tests/test_continuation.py` S5, four cases [exists: 18 `check` sites, 17 execute (lines 94/96 are one `try`'s branches), 17 PASS, `rule_media/cont_test.log`]; media known answers [CPU after S3/S4] | high |
| 03b-16.23 | Codes: snapshot or EMA | `AUD_CODES='snapshot'`; `'jit_ema'` an arm. D-5 (a design-workflow decision, N3) is narrowed, conditional on the owner's answer in §8 0.2 (if the owner took D-5, the narrowing goes back to the owner instead): the codec refreshes at acts that move the text view and at `AUD_REFRESH_EVERY`, **not** at redraw-only acts (C14). | changed | B: discrete drift events can be gated, audited and reversed. | 04's redraw acts would shorten holds → the narrowing; `aud.flip_per_refresh`. | S5 (ii) [GPU] | high |
| 03b-16.24 | Codec architecture | 'spec'. S3 decides at 2 seeds, `AUD_PROBE_N` 400, on the per-attribute criterion with a 2-SE non-inferiority margin, and reports what 'nested' unlocks ('alloc', 'measured_arrival'). The default flips only on the criterion (C45). | + | B: 'nested' would let a post-training area choose its rate, but it lost melody timbre at 3/3 seeds (64 clips, one beyond noise; it was higher on tones exact and melody contour at 3/3). | None at the default. | S3 at 2 seeds [CPU after S3] | medium |
| 03b-16.25 | A mel term or a bigger probe for 'measured' | No mel term; `AUD_PROBE_N` 400, read as a paired difference with its SE and the false-"out" estimate. Add a mel term if 'measured' picks a stride that loses on the primaries; raise n if the paired SE exceeds `AUD_RATE_TOL` / 2. | same | B: the rate rule is a gate, so its error rate must be known. | The stride-1 bias. | S3 noise fixture [CPU]; S5 (i) [GPU] | medium |
| 03b-16.26 | The routing stack under moving tokens and codes | As designed (note 03b-16.26). **Now**, before media, because S0b's text acts are live: add a blacked-out-windows count under one name, `fab.blackout_windows`, beside the existing `fab.growth_blackout_suppressed.*` pass counters, and the per-byte DOM levels and MEM's rescaled surprise (TREE-S0b-LEVELS). A joint blackout budget of 20% across 03b and 04 is an **alarm** that orders the stamp-scope and cooldown arms, not a veto (C13). | + | B: growth is the sparse channel for new areas; self-inflicted shifts misread as domain shifts spawn spurious domains. | Growth starvation → the counter and the alarm. | Counter in the S0b ship measurement [CPU once built]; S5 (iii) [GPU] | medium |
| 03b-16.27 | Readiness data | `AUD_READY_AREAS=''` resolves to the first media area in `DATA_PHASE_SCHED`; '+generic' an arm. | same | B: later areas stay new to the codec, so codec BWT and arrival readings are honest. | A codec readied on one area may transfer worse → the S3 recipe check. | S3 recipe check, 2 seeds [CPU after S3] | medium |
| 03b-16.28 | Live vs frozen fairness | Every S5 plasticity cell reports labelled step-matched and compute-matched frozen controls. A winning frozen control goes to the owner (**[OWNER] O12**). Add a **post-training cell**: a held-back media family (e.g. aud/chirps) arrives after the main run; live and frozen codecs are read on arrival speed and BWT. | + | B: performance must be read after further learning. | A frozen default would close post-training adaptation. | S5 (ii) plus the arrival cell [GPU] | high |
| 03b-16.29 | Readiness recipe | The first media area, at least 750 codec steps per candidate (`AUD_READY_MIN` 3000 / `AUD_READY_EVERY` 4). '+generic' (D1's recipe, about 3000 steps) takes over if S3's readiness-only cell loses to D1 live25 by more than 2 paired SE on any primary; if both fail, both go to the owner. | same | B: a weaker readiness codec may drift more once live. | 5.3× fewer steps than D1 and no generic set, unmeasured → the recipe check. | S3 recipe check [CPU after S3] | medium |
| 03b-16.30 | Probe cost | Probe every 500 windows in readiness; then at every act ('snapshot') or every 500 windows ('jit_ema'); `AUD_PROBE_N` 400. The GPU bench sets n and cadence, above a **floor**: paired SE at most `AUD_RATE_TOL` / 2 per cell and a reading at every refresh. | + | B: probes are the gate's eyes; their cost is a required price (C31). | Probing cut for throughput blinds the guard → the floor. | GPU bench probe row [GPU]; CPU timing `rev/probe_time.txt` [exists] | medium |
| 03b-16.31 | Ceiling-guard threshold | Calibrated per family at S3 (the live-vs-frozen drop + 2 paired SE); count-only until then. A flat 0.05 is rejected (it would fire in the measured regime: D1 s0 drops 0.069 and 0.118). Real areas rely on the canaries and 03-16.7's metric. | + | B: a gate that fires in the measured regime creates an unmeasured one. | No protection before calibration. | S3 calibration [CPU after S3] | high |
| 03b-16.32 | `world_proj` born zero, no gradient | `WORLD_FEEDBACK` **OFF**; `world_proj` born zero. Report both GPU endpoints: last half +0.0033 ± 0.0031 (2 of 5 seeds better), **full run +0.0271 ± 0.0101** (about 2.7 SE worse) (`results/gpu_world_2026-09-24/ANALYSIS.txt`). The media forecast-caption re-test (S6 (b)) is owed. | + | B: an unproven path into the LM is a risk surface; born zero is a no-op. A: cross-modal forecasting is where WORLD could earn its place. | None while OFF. | S6 (b), 5 paired seeds [GPU] | high |
| 03b-16.33 | SIG width fixed at build-time bpt | Fixed **within** a session (a tensor extent; DOM slices by it). The 5% trigger has fired for default runs: at HEAD's k3000 the first act raises bytes per token +8.8% over the whole re-segmented tail (13,059,157 → 12,000,056 tail ids) and +18-19% over the next 3000 windows, and about +62% by the fifth act (`verify/emp2/actsim.py`, seeds 0-1; model-free, bit-exact against a real k1000 run). At the CPU k1000 shape (about 760 KB, three acts) it sits at the line: +2.9 / +3.8 / +4.8% over the whole tail at its three acts (756 KB, seed 0, `verify/emp3/acts_tail.py`) and +5.0% run average (199.16 against 189.62 bytes/window, `rule_pending_measurements/measured.json`); +4.2% over the whole tail at the first k1000 act on the 20 MB stream (`verify/emp/k1000_1300.log`). So the re-derive, with DOM re-slicing, is an owed decision, done as a declared operation at a resume boundary with a known answer. Add an explicit `tok.bpt_tail` counter (not in `src`). | changed | B: signatures stay consistent inside a session, and the width can still change between sessions. | Signature misfit as bpt drifts → the counter and the resume-boundary route. | The re-derive known answer [CPU]; bpt across acts in the retok fleet [GPU] | medium |
| 03b-0b-GPU-BENCH | GPU cost of the live codec | `RUN_BENCH=1 RUN_PROFILE=1` (media off / readiness / live; windows/s and peak memory under MPS) before any S3/S4 default is fixed, after the text throughput re-baseline. Monitoring (probes, acts, re-encodes) is priced as a required cost. | + | B: live learning plus gates has a price, and B needs it known. | None. | [GPU]. CPU exists: about +20% wall; probes about +71% of D1's LM time per area. | high |
| 03b-0b-DRIFT | Codec drift at the owner's shape | Report `aud.flip_cum`; no default change until measured. Add a declared drift-budget reading and a **post-training continuation cell** (run past 20k windows, e.g. +20k with a new area). | + | B: about 530 codec steps per 20k windows (arithmetic) add up without limit after training. | Unbounded cumulative drift → the budget reading. | [GPU]. Toy: cumulative change 26.9 / 26.1% at 1/4 cadence against 24.8 / 28.5% at 1/32 (03b §6.4). | medium |
| 03b-0b3-RESIDUAL | Hand-set media defaults pending measurement | Keep each pending its named measurement (silence pad; fixed clip length per family; stride chosen on readiness areas only; `LM_CTX` 128; the guard thresholds; `AUD_REWARM` 0). Each threshold reports its firings. Add: S5's clips fit `LM_CTX` with their caption at every candidate stride, or those cells are marked non-comparable. | + | B: guard thresholds are gate parameters and must be calibrated before post-training use. | `LM_CTX` 128 holds 2.56 s at 50 Hz, so a 4 s clip at stride 1 is truncated → the fit rule. | S3 calibration [CPU]; S5 [GPU] | medium |

**Note 03b-16.14 (the codec regime as ruled).** After readiness: `AUD_TRAIN_EVERY` 32;
`AUD_CODEC_LR` 1e-3, cosine over 750 codec steps to `AUD_CODEC_LR_MIN_FRAC` 0.05 (5e-5), then that
floor for ever; `OPT_CODEC_BETA1` / `BETA2` 0.8 / 0.99; `OPT_CODEC_WEIGHT_DECAY` 0.01;
`AUD_CODEC_GRAD_CLIP` 1.0; `AUD_ANCHOR_W` 10 toward the act-refreshed snapshot; `AUD_REHEARSE` 0.5;
`AUD_REWARM` 0; `AUD_FREEZE_AT` 0. AUD owns the codec schedule (Q-OPT-11).
- Evidence (03b 0b.2 row 1, `results/live_codec_design_2026-09-25/prototypes/d1`): live against frozen
  at 4 paired LM seeds, bits/s lower in 24 of 24 (codec-dependent); LM-side codec-invariant readings
  show no consistent cost or gain (caption worse 11 of 16, understanding worse 5 of 8, generation exact
  worse 12 of 32 and better 18); codec ceiling a consistent cost (recover exact lower in 7 of 8 plus 1
  tie, 4 live seeds against a single frozen reading per area, not pairs). All on one codec init at
  25 Hz with 4000 pre-train steps.
- Conflicts noticed: the anchor was measured against, weakly, at 5 of 6 readings yet ships by D-4 and
  D-7 (C44: no change until S3's anchor-0 arm); the codec group has weight decay 0.01 while the LM
  base group ships `OPT_WEIGHT_DECAY` 0.0, the setting the plasticity literature flags (C32); and
  "nothing frozen" against the frozen control (C27: the control is an instrument).

**Note 03b-16.26 (the routing stack as ruled).** Coordinate signatures (`SIG.build(media_lattice=)`).
Shift stamps to FAB and OPT (CAP from P4) at acts that move the text view, and at refreshing acts once
media is consumed (`AUD_SHIFT_STAMP='refresh'`; 'flips' and 'always' as arms). `DOM.on_retokenize`
whenever the view moved; the composed `DOM.rekey` at refresh acts at `SIG_MODE=learned` (Q-DOM-4).
Bits per build-time token for DOM (and CAP from P4); MEM's rescaled surprise (Q-MEM-14).
- Tree state: the act's shift stamp and `DOM.on_retokenize` are built (`src/spine/loop.py` around
  1248-1254). The per-byte DOM levels and MEM's rescaled surprise are not; `TOK.Vocabulary.blen` is
  still deferred (`src/spine/compose.py:1634`). Neither `fab.cooldown_windows` (03b's name) nor
  `fab.blackout_windows` (04's name) exists in `src`; what exists is
  `fab.growth_blackout_suppressed.{regression,stall}` (suppressed growth passes) and the
  `fab.growth_blackout` Gate (`src/fabric/api.py:4310-4311`, `:4619`). The new windows count extends
  those, not a parallel surface.
- Blackout arithmetic: every stamp blocks FAB growth for `FAB_COOLDOWN` 400 windows
  (`src/fabric/api.py:4348-4357`). By construction (400 / cadence, an upper bound) that is up to 20%
  of windows at a 2000-window cadence and 27% at the union of 2000 and 3000 (03b 0b.1 item 16), 13% at
  k3000 and 40% at k1000, and up to 54% with 04's redraw acts (04 §1 item 5,
  `04_SELF_REGULATION.md:541`).
- The joint budget: redraw-only acts stamp OPT only by default (`DATA_FOCUS_STAMP` 'opt', C14). If
  the union of stamping acts keeps FAB in cooldown for more than 20% of windows, the alarm orders the
  stamp-scope arm (FAB stamped only at acts that move the text view or flip more than
  `AUD_SHIFT_FLIPS`; OPT keeps every stamp) and, at k1000, the `FAB_COOLDOWN` {400, 100} arm: text
  acts always move the view, so scoping cannot clear the alarm there (C13).

### 4.3 Media: Proposal 01's M-questions and Proposal 02's R-questions

| ID | Decision | Ruling and defaults | Δ | Why for B / for A | Risk → guard | Decisive test [who] | Conf. |
|---|---|---|---|---|---|---|---|
| 01-M1 | One clock kind or several | **Answered**: one `Windows` kind; unit labels only; media horizons in `U.SECONDS`. | same | B: cadences keep one meaning when a modality arrives after training. A: no lever multiplies per modality. | A cadence covering different amounts of content → bits/s and `ctx_seconds` readings. | None | high |
| 01-M2 | One signature space or one per modality | Measure it **earlier**: a CPU pilot as soon as SIG 'typed' exists (S4): train SIG on a mixed stream, read the modality purity of flat DOM domains and whether the leading dimensions separate modality or content. Purity < 0.95 lands the DOM class gate (`DOM.observe(modality=)`) as a lever; otherwise root filtering suffices. Flat, emergent routing is preferred. | changed (earlier) | B: impure domains mean interference between areas. A: decides whether 02's modality top is needed. | Flat signature collapses onto modality → the purity reading. | CPU pilot at S4 [CPU]; S5 (h) [GPU] | medium |
| 01-M3 | Comparable units across modalities | **Answered**: units never mixed; bits/s is codec-dependent, so cross-codec comparisons use codec-invariant readings. | same | B: forgetting read per unit without confounds. | None. | None | high |
| 01-M4 | Package per modality or lever | **Answered**: one package per modality; AUD now, VID at S7, IMG index reserved. | same | A: a modality is a package plus an area. | None. | None | high |
| 01-M5 | Tokenizer per modality or joint vocabulary | **Answered**: per-modality tables at transport ids with a modality mask; coordinate rows (03b). | same | B: codes inside BPE cost 0.64 bits/byte more forgetting and +0.06 on text (03 §14). | None. | Toy [exists]; S4/S5 (b) mask on/off [GPU] | high |
| 01-M6 | Image: one window or patches | Build nothing now (B first). Recorded direction for the IMG design: a code sequence laid inline like a clip (a spatial code grid in raster order between BEGIN and END; in effect a one-frame clip from VID's causal 3-D FSQ codec at T=1, in its own block at index 2); no new clock; 2-D position rows as an arm. | new direction | A: keeps the image door open with the fewest mechanisms (Chameleon, Emu3); addresses the 1-D-positions door-closer. | None now. | Patch count × rate at IMG design [GPU] | low |
| 01-M7 | Generation path | **Answered**: one sampler, `EVAL.generate`, through the whole-path `logits_fn`. A future evaluation-time adaptation lever (NEW-15) enters through the same path. | + | B: no evaluation/training divergence (ISSUES P1-C4/C5); T0 is the no-risk tier. | O(ctx) per token → timed at S5. | S2/S5 timing [GPU] | high |
| 01-M8 | Where cross-modal prediction lives | **Answered**: WORLD, on the tokenizing latent, horizons in seconds; `WORLD_FEEDBACK` OFF. If S6 (a) and (b) show no media gain, the LM's own next-token prediction over the interleaved stream is the cross-modal predictor and WORLD's media head stays an arm. | + | A: cross-modal forecasting. | WORLD does not earn its cost (O13). | S6 (a), (b) [GPU] | medium |
| 01-M9 | Held-out split for media | The synthetic rule stands. Write the **real**-media rule now: per area, a seeded random block of whole recordings (the Q-DATA-6 pattern); a source-disjoint split (speaker, session, device) wherever metadata exists; control and report halves (C11); held-out clips never enter readiness, rehearsal or MEM. | changed (fills gap) | B: gates need fixed, disjoint probes. A: honest splits for real modalities. | Leakage → a disjointness test (03 App. A pattern). | Disjointness test at the first real area [CPU] | medium |
| 01-M10 | Is a modality an area? | **Answered**: yes; rehearsed at `DATA_TEXT_SHARE` 0.3 by default, pure-add the lower bound, read on the R matrix. | same | B: adding a modality **is** the B benchmark. | None. | App. B S4/S5 (e) [GPU] | high |
| 02-R1 | Hops and layers | Coexist behind levers: a hierarchy-depth lever, default 0 (OFF: today's flat population, bit-identical); `FAB.ponder` charges total routed depth. First make `ponder_warm` reachable (8000 exceeds a default run, P1-C11). Conditional on 01-M2. | new | B: depth is priced, not free. | Two unpriced notions of depth. | Hops × depth on a known-partition task [CPU] | low |
| 02-R2 | Back-routing vs result-up | Two upward paths on one buffer mechanism, each with its own counter. Built last. | new | B: observability. | An invisible path. | Counters in the two-level test [CPU] | low |
| 02-R3 | The parent's clock | Flushes; the buffer drains every flush, so it is empty at every save. 'After a budget of pending results' is an arm with a checkpointed buffer. Test at `OPT_BATCH_WINDOWS` 2 and accumulation 2 (P1-H52). | new | B: exact resume with no new state. | The clock choice is invisible at batch 1 → batch-2 tests. | CPU known answers [CPU] | low |
| 02-R4 | Results up once or repeatedly | Once, to the immediate parent; repeated ascent is an arm, terminated by the depth bound. | new | B: bounded. | Non-termination → the depth bound. | Two-level test [CPU] | low |
| 02-R5 | Router death | One level per pass, a newborn grace, counters for deaths and grace-blocked deaths; cascade-in-one-pass an arm. | new | B: bounds structural damage per pass. | Over-firing → grace and counter. | Death-rule test before growth [CPU] | medium |
| 02-R6 | ROUTE package or FAB extension | Inside FAB: no wires, own counters, depth-0 control bit-identical; separability from paired depth arms. Revisit a package only if wires free. | new | A: saves wires for the next modality. | FAB's lever count grows. | Paired depth arms [CPU] | low |
| 02-R7 | RNG per router | One stream per router, derived from its node id, registered through `rng.issued`. | new | B: needed for independence. | None. | The R8 sweep [CPU] | high |
| 02-R8 | Oracle for sibling independence | Build the per-node integer fingerprint and the sibling-independence sweep against `test_determinism`'s floor **first**; it is the falsifier. | same | B: guards against inert mechanisms (the history: 60 guards that could not fire, 57 mechanisms never run). | None. | [CPU] | high |
| 02-R9 | Router signature | Every level routes on the same 64-d signature, parents on their children's centroid aggregates. A coarser top signature is an arm, adopted only if M2 purity < 0.95 and the arm improves purity. | new | B: no new learned encoder. | Levels duplicating work → per-level entropy and purity. | M2, then the two-level test [CPU] | low |
| 02-R10 | Depth limit | A separate hard maximum-depth lever, default 2 levels (a bound, inert while 02-R1's depth is 0). CAP becomes the self-regulated bound once reachable. | new | B: termination and bounded risk. | None. | Owed [CPU] | medium |
| 02-R11 | Does contrib mean anything at a node? | Build `FAB.contribution` and its producers (targets, candidates, NEW-03's memory-off `baseline_logits_fn`) right after NEW-03 (§8 3.5): at the owner's shape culls, rescue and merges are already reachable and their need signal is void (C37). The old tree's P1-C3 (ban1 never applied, unverified) does not carry over: `FAB.forward` applies `hold_out` at every hop (`src/fabric/api.py:1699-1701`); the body raises `NotImplementedError` (`:3339-3370`) and its producers are missing (`src/spine/compose.py:1808-1818`). **Now**: in the continue preset, defer faded-area culls (C37); training runs unchanged, an E2 arm. | changed (priority) | B: culls that spare useful experts guard against forgetting. | A void signal → the build; until then the continue preset defers culls of faded-area experts. | `fab.contrib_distinct_values` > 1 on a run, after NEW-03 [CPU] | high |

---

### 4.4 Self-regulation: Proposal 04

| ID | Decision | Ruling and defaults | Δ | Why for B / for A | Risk → guard | Decisive test [who] | Conf. |
|---|---|---|---|---|---|---|---|
| 04-Q1 | Which draw becomes the default | Build 'replay' at SR0 (`DATA_REPLAY_SHARE` 0.27, `DATA_REPLAY_NEWEST` 0.0) and 'retention' at SR2, both **OFF**. E1 decides, with seven pre-registered changes (note 04-Q1). Interim: `DATA_DRAW='planned'` until SR0 builds 'replay'; then 'replay' 0.27 is recommended as the interim training default for B (**[OWNER] O16**: it overrides D8's 'planned' and changes every default run, since eng fades after phase 1 at the shipped schedule). E1 can overturn it. | changed | B: 'planned' is the only draw that forgets catastrophically; in deployment every moment is an end state, so time-integrated and worst-area readings are B's endpoints. A: draws are over areas, so modality-agnostic; 'retention' scales to many areas where a fixed 0.27 spreads thin (1.35% each at 20 faded areas). | 'retention' starves slow-progress areas → the per-area guard at ε. Flipping to 'replay' breaks pairing → pending fleets pin `DATA_DRAW='planned'`. | E1, 75 + 25 + 20 runs, whole-epoch sizing [GPU]; SR0 'replay' and SR2 P3 known answers [CPU] | medium |
| 04-Q2 | Does a statistical tie go to the self-regulated arm? | Conditional yes (**[OWNER] O8**). A tie goes to 'retention' only if (a) it passes 04-Q1's per-area guard; (b) it is a tie on E1's primary endpoint: within ε on the time-integrated gap and not significantly different (significantly better wins outright; C25); (c) it actually regulates: last-phase `data.focus.rho_at_cap_frac` below 0.8, or `data.focus.alloc_freedom` at least 0.2 **after normalising by its maximum under the floors in force** (C17), raw value reported beside it; (d) compute charged through `replay_cm`. If (c) fails the tie goes to 'replay'. Every tie is reported with its 90% interval. | changed | B: a tie in the mean with worse tails is not neutral for B. | Shipping 'retention' on a tie buys 4.3%+ wall and act complexity for nothing → (a)-(d). | Read from E1 [GPU] | medium |
| 04-Q3 | `DATA_PHASE_LIVE=3` in E1 | Include as E1 shape (c): 25 runs, reported, not deciding. The shipped schedule is unchanged (`DATA_PHASE_LIVE` 0 derives 2 live at 4 areas). Add shape (e) (04-Q1). | + | B: (c) fades only area 0, so it tests allocation more than retention; B's regime is (b) and (e). A: more simultaneous live areas are closer to a mixed stream. | Ambiguity if (b) and (c) disagree → (b) decides; disagreement is reported as a finding. | E1 shape (c) [GPU] | high |
| 04-Q4 | May a pure-add child rehearse its parent? | Build `DATA_REHEARSE_PARENT` (bool, default **False**). Areas in `DATA_AREAS` and in the parent's record but live in no phase of the child count as faded from window 0 under 'replay' or 'retention'; no effect under 'planned'. Pure-add stays the unprotected control (arm P). The continue preset sets it True. Parent areas are read from disk, then from the reservoir (NEW-06), and refused loudly only if neither exists (C16). (**[OWNER] O9**) | changed | B: without it a child has nothing faded to protect; a parent → child resume is the closest existing path to learning after training. A: "add A later" means adding modalities as areas after training. | Parent data absent → a loud refusal and a counter. | Q-DATA-7's pair extended with P+parent, 3-5 seeds [CPU at toy shape; GPU as E1 shape (e)] | high |
| 04-Q5 | `DATA_SYNTH_HOLDOUT` ON | **ON**, built at SR0 under the real sources' law, with the one resume admission (key None, size 0 → n, counted as `data.holdout_admitted`). Each admitted block is split into a **control half** and a **report half** from separate seeded child streams keyed by area name (C11). **The pin rule** applies to pending fleets whose verdict pairs with pre-change runs (the retok fleet: its arms, nuisance margin and CPU pre-read predate the change): if one runs after this lands, it pins `DATA_SYNTH_HOLDOUT=0`, `EVAL_RETENTION_EVERY=0`, `DATA_TRUST='off'` (and `DATA_DRAW='planned'` if that flips). The WORLD re-run is not such a fleet: its four arms pair only with each other, so it runs all four in one post-SR0 commit with `DATA_SYNTH_HOLDOUT` ON and the retention probe ON, `DATA_DRAW` still pinned 'planned' (note WORLD 3). | + | B: every gate needs held-out data disjoint from training; a fixed held-out block is the frozen measurement anchor B needs. A: one holdout law gives any new source a block by construction. | Breaks pairing with pre-change synthetic runs → the pin rule; a 5% smaller synthetic body to draw from, training bytes unchanged (bodies are generated at 2× the sampler's need). | SR0: `DATA_SYNTH_HOLDOUT=0` with the probe off is bit-exact against HEAD; resume admits 0 → n and refuses n → 0 [CPU] | high |
| 04-Q6 | Rehearsal split across faded areas | Build `DATA_REHEARSE_EVEN`, build default 0.0 (inert while 'retention' is OFF). E2 tests 0.5, **before** E1, under B's worst-area rule: 0.5 is adopted if it lowers the worst faded area's time-integrated gap (end-state reported beside it) at 3 of 3 seeds and neither any area nor the all-area mean is worse by more than ε. If E2 cannot separate them, E1's 'retention' arm carries 0.5. | changed | B: need-only splitting starves slow forgetters: easy worse than m27 by +0.076 on average (t 3.24). A: a need-only split concentrates on the fastest forgetter as areas multiply. | 0.5 may erode hard's advantage (−0.104, n.s.) → E2 reads hard; low power at 3 seeds → a tie goes to the guard value. | d3 testbed pre-check, 5 seeds [CPU]; E2, 3 seeds [GPU] | medium |
| 04-Q7 | Protecting slow-progress, valuable areas | Build default `DATA_FOCUS_FLOOR` 0.3; E2 tests 0.5 under the same worst-area rule, reading the credible sources on focusbed. Unresolved → 0.5 into E1's 'retention'. Per-area gaps always reported beside per-phase shares. Trust-weighted allocation ('loss+draw') stays OFF until E5 and SR6. | changed | B: learning progress measures learnability, not value; cred +0.137 (t 4.90) and corrob +0.175 at 5 of 5 are under-drawn. A: an even floor scales as 1/n_live. | Less promotion of hard areas → E2 reads hard; lowers raw `alloc_freedom` → normalised in 04-Q2 (C17). | d3 pre-check at 0.5, 5 seeds [CPU]; E2 [GPU] | medium |
| 04-Q8 | What is a claim on real text | `DATA_TRUST_CLAIM='kv'` is the build target and the default in observe mode; 'ctx' the prototype arm (declared to measure surface conformity); 'mem' (MEM's stored context keys) named as a future OFF value, the modality-agnostic form. Observe only until SR3's format-variant known answer, E3's audit and E5's worlds pass. | + | B: trust guards only if it measures content: 'ctx' floored a truthful different-format source (r 0.001) and trusted the liar (r 0.999) at 2 of 2 seeds. A: 'kv' delimiters are English text; 'mem' is the universal route. | 'kv' is unprototyped → observe only; E3 audit. | SR3 'kv' format-variant world, model-free, by extending `results/self_regulation_design_2026-09-26/prototypes/critic/td_stress.py` [CPU]; E3 audit on the owner's corpus [CPU]; E5 [GPU] | medium |
| 04-Q9 | Full-tail acts, look-ahead, and act stamps | Full-tail acts, rate-limited (`DATA_FOCUS_ACT_EVERY` 6 probes, `DATA_FOCUS_SHIFT_TV` 0.1, zero-TV acts refused). Build `DATA_DRAW_HORIZON` (windows; 0 = whole epoch, the default) **OFF**, after SR2: an open-ended post-training stream cannot be laid up front. One counter name, `fab.blackout_windows`. Redraw-only acts (which do not move the text view) **stamp OPT only**: no FAB stamp, no codec refresh (C14); `DATA_FOCUS_STAMP` default 'opt', 'all' an arm. Revisit full-tail if E2's splice timing exceeds +10% wall. E2's own estimate at the whole-epoch 3.78 MB shape it runs (k3000 retok acts, phase entries and full-tail focus acts at `EVAL_RETENTION_EVERY` 160, 38 windows/s, before the redraw's own DATA rebuild): about 5-6% of wall at `DATA_FOCUS_ACT_EVERY` 6, about 9% at 3, about 2.6% at 25 (arithmetic, `verify/numbers3/e2_splice.py`). The ACT_EVERY-3 arm sits at the +10% revisit line, so the splice timing is a live E2 reading, not a settled one (note secondaries (a); 3.4% / 1% there are the retok fleet's figures only). | changed | B: FAB growth is the sparse channel for new material, and "the whole epoch up front" assumes a known run length. A: arrivals at arbitrary times. | Growth may fire on a self-caused mixture shift (the CAP runaway precedent, 2048 → 8192 in 19 lifts) → read `fab.grown_*` around redraw acts; look-ahead turns the startup exposure Gate into a projection → chunk events in `seg_log`, a resume test. | Splice timing [exists: 8.63 s per 17 MB tail, CPU]; combined blackout share in E2 [GPU]; look-ahead equivalence [CPU] | medium |
| 04-Q10 | Probe as producer for OPT damping | Build `OPT_DAMP_SOURCE`, default **'off'**, 'probe' an arm. The probe hands OPT a `Reading` (value = mean probe bits/byte over seen areas, `seed_count` 1), not a bare float, which `OPT._reading` rejects (`src/opt/api.py:540-561`). At n=1 OPT refuses to damp and counts `opt.restart.damp_refused_n1`, so the arm makes the counters reachable telemetry; damping itself waits on O10. The more important use: the same reading is the producer of `CKPT.Retention.consider`'s `curve_bpb`, the best-checkpoint anchor, live once `consider` is fed and `CKPT_DIR` is set (`CKPT_BEST_KEEP` 0 already keeps one rotating `.best`; > 0 adds `.best1..N`, `src/ckpt/levers.py:256-262`). | changed | B: reversibility is B's core guard, and `Saves.best` can never be non-zero today (`src/spine/compose.py:1663-1675`). | Noisy readings damp a good cycle or save a lucky checkpoint → the n=1 refusal, `CKPT_BEST_KEEP_TOL` 0.02, the 32-window run-boundary read, a recovery window. | The Reading reaches `maybe_step`; `Saves.best` becomes non-zero [CPU]; whether damping helps, under a restarting schedule only [GPU] | medium |
| 04-Q11 | The other built-but-off self-regulators | All four into the honing sweep, **OFF** until measured. Promoted as B-priority: (a) MEM `write_mode='quantile'` (target 0.5) with `MEM_SRC_SHARE` 0.5 and eviction that spares faded sources; (b) `FAB_LR_OWN`, first with a CPU confirmation test at `OPT_LR_SCHED='none'` (replacing the P1-H15 prerequisite, C02), described as use-clocked annealing to an `lr_amin` floor capped at `lr_maxr` × the global rate. DOM 'relative' and a SIG floor from DOM's live count (an argument, not a wire) go to the general sweep. Self-weighting auxiliary losses get their own proposal. | changed (priority) | B: the fixed 0.3 MEM gate admits 100% (70,656 of 70,656), so eviction churn decides what memory keeps; in the one phased run memory contributed −0.111 bits/byte with every English entry evicted. | The quantile gate could starve a quiet source → `MEM_SRC_SHARE`. | Phased run, quantile vs fixed [CPU small / GPU]; the `FAB_LR_OWN` crash test [CPU] | medium |
| 04-Q12 | Collusion and impersonation before trust actuates | Observe mode, `DATA_TRUST_MIN` 0.3, SR6 copy detection passing E5's majority-false and 50%-impersonation worlds before any actuation default. Add: `DATA_SRC_CAP`, a count-based byte ceiling per unpromoted origin per session (a training run counts as one session; value **[OWNER] O18**), built **OFF** at SR3 (poisoning is count-based, about 250 documents regardless of clean volume); an E5 fixed-count-poison world with a canary probe; provenance kept on everything learned. | + | B: removing poison from weights afterwards is unreliable, so guards must be preventive and must not rest on agreement, which collusion defeats. A: impersonation is modality-independent. | `DATA_TRUST_MIN` would floor a truthful minority source if actuated → E5 eligibility (`format_split_floored` 0 in every world). | E5 worlds, model-free [CPU]; actuation arms [GPU]; SR6 test [CPU] | high |
| 04-Q13 | Tag id and entry point | `DATA_TAG` **'off'** until E4. Build 'area' and 'domain', `DATA_TAG_DROP` 0.25. Build the entry point as a lever, `LM_SRC_AT` 'input' (default) / 'head'. Document ids go to the provenance books (`Stream.sources`), not the model's tag table (`LM_SRC_SLOTS` 64). E4 reads **both** worst-area retention on tagged reads and the untagged cost against ε (C18); the drop ladder 0 / 0.1 / 0.25 / 0.5 also reads tagged retention, not only the untagged read (critic). (**[OWNER] O7**) | changed | B, R1 against R1 (tagged retention vs untagged served use): a tag at read localises a source's influence and cut faded-area forgetting about fivefold, while served prompts of unknown origin carry no tag, so the untagged cost is B's too. A: 'head' keeps routing label-free. | Label-driven structure → purity gauges and the entry lever; tags are spoofable → 04-Q12. | E4, 5 seeds, with `fab.expert_area_purity` and `mem.hit_area_purity` [GPU]; `d2/out/tags_*` [exists] | medium |
| 04-Q14 | Should `LM_SEL` be built? | Build it **OFF** at SR5, last. Add a reference value 'anchor': the last kept best checkpoint as a Rho-1-style frozen reference, beside the measured lagged-self 'ema'. No separate frozen model is trained. | changed (slightly) | B: the anchor doubles as B's KL-to-anchor forgetting sensor. | +30% wall; a stale anchor down-weights new material → OFF, SR5 ablation only. | SR5 ablation, toy [CPU]; owner scale [GPU]; `d2/out/sel_s*` [exists] | low |
| 04-Q15 | Frame rate under self-regulation | 03b's 'measured' stays the default; 'progress' built **OFF** at 03b S3, after SR0-SR2 (B before A), judged against 'measured' at a matched frame budget. Every rate change stamps a shift and counts toward the blackout budget. | + | B: a progress-driven rate is a self-caused shift. A: keeps the door open. | Compounding blackout → the unified counter. | 03b S3/S5 [GPU] | high |
| 04-6.2 | Retention probe ON as telemetry | **ON** at `EVAL_RETENTION_EVERY` 1000 plus a reading at each phase start (built at SR0), once SR0's bit-identity test passes (else 0); that is the interim training default until E6 picks. E6 picks the densest cadence costing at most 2% of wall, above a B floor of at least 5 readings per phase at the owner's shape. 1000 does not meet it: at the whole-epoch 3.78 MB shape phase 1 spans about 4,980 windows (189.6 bytes/window) and the first probe fires at window 1001, so phase 1 gets 4 (5 with the phase-start reading); acts shorten phases further (arithmetic; `verify/emp2/actsim.py`). The phase-start reading alone does not reach 5 in every phase at HEAD's k3000: at the 3.78 MB shape seed 0's third phase spans 3,709 windows and gets 3 + 1 = 4 (seed 1 gets 5 in every phase; `verify/final/phase_readings_378.py`, `_s{0,1}.out`). So the default takes both remedies: the phase-start reading, and a cadence capped at the shortest phase's windows / 5 (about 700 at k3000 on that shape). A cap (the shortest phase's windows / 5, from `DATA.data_plan` and the arm's measured bytes per window) is written as a number by the preset builder or the pre-registration, never computed at run time (N4); E6's arms are checked against the floor. Split control/report halves (C11). R-7's rebase stays inside the focus books; gates, `CKPT.Retention.consider` and OPT's Reading read the raw series and `data.focus.rebase_step` (C03). | changed | B: the tree's only runtime forgetting sensor; its per-area rows persist across run boundaries, which is how learning after training is measured. A: a new modality becomes a new row. | Perturbing training → SR0; 6 windows per area is noisy → no gate acts on a single reading. At k1000 and in media sessions at k3000, C03's cadence rule adds about 7.2% forward windows, 2.1-2.4% of wall at today's 6 windows per area, a lower bound that scales with the ε-sized probe (**[OWNER] O11**). | SR0 bit-identity (`EVAL_RETENTION_EVERY` 50, 500+ windows, FAB and MEM on) [CPU]; E6 [GPU] | high |
| 04-6.3 | Source-reliability book ON in observe mode | **ON**: `DATA_TRUST='observe'`, `DATA_TRUST_CLAIM='kv'`, `DATA_TRUST_RULE='claims'`; actuation ('loss', 'loss+draw') **OFF**. Ships after SR3's bit-identity test. E3's 2%-of-wall rule may lengthen `DATA_TRUST_EVERY` only above a **detection floor**: at least one pass per session and per N bytes from any new origin (C31). Report per-source reliability and conflicted-claim counts as a time series (the poisoning early warning). | + | B: untrusted input is the largest post-training risk; observe mode is risk-free telemetry on the owner's real corpus. | 6-7% wall on the toy (16.7 / 241.1 s, 16.2 / 243.5 s, 7.9 / 124.7 s); 'kv' uncalibrated → nothing actuates. | SR3 bit-identity [CPU]; E3 audit and wall [CPU / GPU]; E5 [GPU] | high |
| 04-6-UNMEASURED | Unmeasured numbers kept as defaults | Keep each until its experiment runs; none is changed on literature. Tests made concrete (note 04-6-UNMEASURED), plus two omissions: `DATA_REHEARSE_MAX` 0.2 / 0.3 / 0.4 in E2, and `DATA_REPLAY_SHARE` 0.15 / 0.27 / 0.40 as an E1 secondary if 'replay' becomes the default. Guard-type numbers (floors, caps, `REHEARSE_MAX`, `TRUST_MIN`) are judged on the worst-area rule, not the mean. | changed | B: `DATA_REHEARSE_MAX` bound ρ in 53-96% of P3 re-plans in the retention arms (focus, fulltd, act6; 0-3 of 49 in the full focus + trust arm, 1-4 with tags grafted; `verify/emp3/toy_stats.out`), so it is effectively the rehearsal amount, and only 0.3 was ever run. | The de facto rehearsal amount ships untested → item (g). | SR2/SR3 unit and known-answer tests [CPU]; E2, E3, E5 [GPU; E3 observe on CPU] | medium |

**Note 04-Q1 (the E1 changes).**
1. **Primary endpoint (changed, R0):** the time-integrated all-area held-out gap (the probe series
   over the run), 5 paired seeds, one-sided paired t at α 0.05; shape (e) is read after its
   continuation.
2. **B guard:** any default candidate must be non-inferior per area against the best hand-set arm, at
   the owner's margin ε (O2), fixed in advance. The earlier draft used 0.05 bits/byte, the toy's
   minimum detectable effect for the six-area mean (per area it was 0.07-0.18); that is now the
   recommended starting ε, not a margin derived from noise.
3. **04's all-area end-state mean** (32 windows) is reported, and breaks a tie only after 04-Q2 (R5).
4. **Continuation shape (e):** each shape-(b) end checkpoint resumes as a child on a real area absent
   from the parent's schedule, for 25% of the parent's windows. Arms: planned / replay /
   replay_newest / retention, with `DATA_REHEARSE_PARENT` True for the rehearsing arms (20 runs). It
   runs under the continue preset with the winning `OPT_LR_CONTINUE` and is read on cooled branches
   (C39).
5. **Trust eligibility on focusbed:** 'retention' is eligible only if `noise_outdraws.P3` is 0 and the
   liar's drawn share is at most the credible source's at 4 of 5 seeds.
6. **Sequencing:** the toy continuation arms (NEW-05, C01) first, then E2, then E1 (C39). E1 shapes
   (a)-(d) run at the training-run schedule (single-cycle cosine).
7. **Stream sizing (critic blocking 2):** 04 §7's run shape for every GPU experiment, E1-E6 ("about
   a 20 MB stream, about 20,000 windows", `docs/proposals/04_SELF_REGULATION.md:1453`), never reaches
   the last of the schedule's four 5 MB phases. With frozen segmentation (`d97779d`, or
   `TOK_RETOK_EVERY=0`) it reads 3.75-3.84 MB and never leaves phase 1 (`verify/emp2/phasepos.py`). At
   HEAD's k3000, acts raise bytes per window from about 190 to about 307, so it reads about 5.19-5.23
   MB, fades eng only in its last ~790-940 windows, and never fades py (seeds 0-2;
   `verify/emp2/actsim.py`, `verify/emp3/acts.py`).
   E2's and E4's faded-area readings (04-Q6, Q7, Q13, NEW-10) would have almost nothing to read.
   E1-E6 are sized like `EXP=retok`: `DATA_STREAM_BYTES` = WINDOWS × the measured bytes per window,
   one whole epoch, window cap out of reach. `DATA.data_plan`'s phase bounds go into the
   pre-registration, and a run that does not consume the whole epoch, and so does not reach the last
   phase, is reported **invalid**, not as a tie.

Evidence behind the change (the paired recomputation of the document's own numbers,
`rule_self_regulation/paired.py`; source `results/self_regulation_design_2026-09-26/prototypes/rev/metrics.txt`,
`judge/compare.txt`, `repro/ns.txt`):
- end-state focus − m27: t −0.81 (a tie);
- time-integrated: t −4.05 (retention better);
- worst areas: easy +0.076 (t 3.24) and cred +0.137 (t 4.90) (retention worse).

So the endpoint choice flips the verdict. 'replay' over 'planned' is the strongest result in the
study: −0.178 to −0.317 at 5 of 5 seeds, t −10.8, reproduced. It agrees with 03 §9 and the
literature's dense tier (replay matches retraining). At the shipped 4-area schedule
`derive.phase_schedule` gives [[eng, py], [py, num], [py, num], [num, c]], so eng is unprotected for
75% of the run under 'planned'.

The belief bites here as a hazard, not a benefit: learning-progress focus without trust drew the liar
more than cred at 4 of 5 seeds (0.179-0.221 against 0.123-0.135), and noise out-drew both credible
sources in P3 at 5 of 5. Hence condition 5.

Conflicts noticed: "performance decides" against self-regulation (O8); the instrument line
(`src/eval/levers.py:146-148`) and PLAN 3.8 against a controller that acts on one run (O10); E1
depends on the OPT schedule ruling (C39); a "tie" at 5 seeds means a difference below the minimum
detectable effect (about 0.042 bits/byte on the time-integrated gap, 0.053 on the end-state mean,
`paired.py`), which is not equivalence.

**Note 04-6-UNMEASURED (the concrete tests).**
- (a) `DATA_FOCUS_SHIFT_TV` 0.1: the TV gate was never exercised (the act emulation acted every 6
  probes unconditionally, `judge/w/d3/run_act.py:260-264`). SR2 adds a CPU unit test that a
  sub-threshold plan change is withheld (`data.focus.acts_withheld` > 0); E2 reports acts beside
  acts withheld.
- (b) `DATA_FOCUS_CAP_MULT` 3.0: SR2's fixed-LP unit test at n_live 2 / 3 / 6 (at 2 live, LP {1, 0}
  gives 0.85 / 0.15), then E2 at 2 against 3.
- (c) `DATA_FOCUS_LP` 'signed': SR2's P3 interference known answer (`noise_outdraws.P3` = 0 at 3 of 3
  seeds).
- (d) `DATA_REPLAY_NEWEST` 0.34 is an E1 arm value; the default stays 0.0.
- (e) The 'kv' spec: SR3, E3, E5.
- (f) `DATA_TRUST_EVERY` 160 and `DATA_TRUST_TABLE` 200000: E3's wall and table-size readings.
- (g) `DATA_REHEARSE_MAX` 0.2 / 0.3 / 0.4 in E2 (omitted from the document's list).
- (h) `DATA_REPLAY_SHARE` 0.15 / 0.27 / 0.40 as an E1 secondary if 'replay' becomes the default: the
  literature puts the replay fraction at about 5% for a weak shift and about 25% for a strong one
  (*unverified*).

---

### 4.5 Tree and training: S0b, the optimizer, capacity, the contract and known low items

| ID | Decision | Ruling and defaults | Δ | Why for B / for A | Risk → guard | Decisive test [who] | Conf. |
|---|---|---|---|---|---|---|---|
| S0b-ship | Which `TOK_RETOK_EVERY` ships: 0, 3000 or 1000 | The pre-registered non-inferiority rule is unchanged (note S0b-ship). Additions: DOM's per-byte Levels are built before the fleet (C12); the shipped cadence is **provisional** until a held-out worst-area re-read on SR0's probe passes at margin ε; secondaries reported beside the rule, not in it; the interim default stays 3000 and firing (**[OWNER] O14**); every dependent experiment pins and labels `TOK_RETOK_EVERY`. Shipping 0 changes only the training-run default: the act stays built for resume and AUD. | + | B: at `RUN_EPOCHS=1` the act is the only way minted ids reach training; at 0, about 594 mints per 20k-window run are stranded (99 bursts × 6, arithmetic). A: byte-level online BPE with live re-segmentation is the universal-substrate path. | Resume bit-exactness and the lever revert do not undo damage to old areas (C40, critic) → the real guards are the held-out worst-area re-read and pinned cadences; `CKPT_DIR` recommended in long runs. | The retok fleet [GPU]; equal-bytes +0.0003 (seed 0) and +0.0078 (seed 1) [exists]; nuisance runs [CPU] | medium |
| TREE-S0b-LEVELS | Build Levels before the ship decision? | Build before the retok fleet, one lever per consumer, default **ON** (the build-time-token unit, 03b 0b.5); OFF is today's per-token unit. Order: (a) **DOM** before the fleet: bits per build-time token = (mean nats × tokens in window / ln 2 / bytes in window) × `bpt_build`, bytes from the segmentation's `byte_pos`, so `blen` is not needed; (b) **FAB**: a known answer that a stamped act fires no regression growth; (c) **MEM**: the rescaled surprise needs `TOK.Vocabulary.blen` out of the deferral list (23 → 22) and a written Q-MEM-14, built after DOM, not a fleet blocker (the fixed 0.3 gate admits 100% of writes today); (d) **CAP**: specified now, inert until `CAP.observe` exists (P4). | changed (order) | B: after training, acts keep firing, so per-token levels drift without end and calibrated controllers would read segmentation churn as a change in competence. A: the conversion is text-only; one lever per consumer leaves room for a media unit. | A conversion bug silently changes domain management → known answers (identity at bpt = `bpt_build`; per-byte bits unchanged across an act) and the OFF arm. | k1000, Levels ON vs OFF, reading `part.n_created`, `part.n_culled` at acts, one seed [CPU] | medium |
| TREE-OPT_HORIZON_REVISE-LEVER | Add the off arm | Add `OPT_HORIZON_REVISE` (U.FLAG, default **True**) for **in-run** revision only. When False, `revise_horizon` returns None and `opt.horizon.revise_inert` names the lever. It does **not** change `load_state`'s continuation pricing; `OPT_LR_CONTINUE` governs that (NEW-05, C01). | changed | B: revision becomes measurable without silently switching a continued run from the floor to the shape-dependent no-log re-pricing (NEW-05). | The OFF arm under-anneals slightly: a run shortened by fraction f ends at 0.05 + 0.95 × (1 − cos πf) / 2 of peak, i.e. about 0.06 / 0.07-0.08 / 0.10-0.11 at f = 0.05 / 0.10 / 0.15 (the closed form ignores warmup; the tree's `_schedule` with its 1000-step warmup at a 20,000-step horizon gives 0.057 / 0.076 / 0.107, `verify/numbers/lr_check.py`). | k3000 True vs False, 3 paired seeds [CPU at 4000 windows, or a fifth retok-fleet arm on GPU]; a known answer that the lever leaves a continued run's LR unchanged [CPU] | medium |
| TREE-OPT_LR_SHIFT_WARM | Should self-inflicted shifts re-warm the LR? | Default **0**, unchanged, and reclassified: `_schedule` multiplies the cycle by `max(min_frac, ramp)` (`src/opt/api.py:468-473`), so the lever can only lower the rate and ramp back. At the floor, N > 0 would drop the rate to min_frac², 0.25% of peak. Kept as a stability-gap arm, N ∈ {0, 100, 400} (400 = `FAB_COOLDOWN`). The upward re-warm B needs is `OPT_LR_CONTINUE` and the born-group clocks (C02). | changed (reclassified) | B: every common method dips at a shift, and a smaller step may make the dip shallower (one supporting and one null case in the archive). A: media arrival is the largest self-inflicted shift the tree will cause. | N=400 at k1000 attenuates 40% of steps → default 0; `opt.lr.shift_warm_applied`. | N ∈ {0, 100, 400} at k3000 in the add-an-area resume and at S5 arrival [CPU toy / GPU] | medium |
| FRAME-POST-TRAINING | The mode for learning after training | The **`continue` protocol**: a resume of a parent checkpoint onto an open stream, launched from a versioned preset of explicit lever values, printed at start and recorded in the manifest; OFF unless launched (note FRAME). | new | B: this is B's mode. A: "add A later" is a continuation run in which a modality area arrives. | Poisoning, forgetting, and the plateau pathology → replay, the gate, rollback, the clip, per-origin caps, trust-gated focus. Residual: until `MEM.blend` and the probe land there is no memory channel and no automatic gate. | Continuation arms (C01) [CPU toy / GPU]; gate vs no gate; poisoning canaries [CPU] | medium |
| CONTRACT-Q-CLOCK-1 | Retire the two CAP reporting wires? | (a) keep both (19 of 25 wires). Flip to (b) once `CAP.counters` has a body **and** an equivalence known answer shows the block-reason histogram plus the pinned high-water mark reproduce every distinction the wires made (C28). `CAP.observe` raises `NotImplementedError` today, so the wires report on a dormant valve. | + | A: (b) frees 2 wires for VID's 21-23. B: observability kept. | None now. | A CAP pinning run at P4 on the vocab arm (Q-CAP-2 makes the expert arm unrunnable at defaults) [CPU] | high |
| CONTRACT-Q-CAP-1 | `cap.clamp` UNREACHABLE on six grounds | **[OWNER] O19** (it extends owner ruling D16's population, N3): recommend (a) CONFIRM; D16 gains a row; alternative (b) SPLIT. Either way every arm keeps printing its ground beside the verdict (unarmed, at_ceiling, refused_unmasked, nonpositive, never_pins, inert). | + | B: "the valve wanted capacity and was refused" stays visible. | Reading UNREACHABLE as "never needed" → the printed ground. | The owner's ruling (O19) [owner]; the 25,344-configuration sweep [exists]; a known answer that all six grounds print [CPU] | high (the recommendation) |
| DECISIONS-Q-CAP-2 | The fabric is born above its cull's settling point | **[OWNER] O20** (the source heads it "OPEN, for the owner"): (c) holds only as the status quo until the owner rules at P4: the refusal is doing its job. No FAB or CAP default moves (`CAP.observe` is unbuilt, and `FAB_N0` 2048 is the configuration of every record). Decide (a) or (b) at P4 from the settling measurement; read the owner's fleet logs first (progress lines print `n_live`; 21 runs of 20k windows). Lean at P4: (a) `FAB_N0` ≤ 1844 **as an arm**; avoid (b), which weakens the refusal on the resume path. Settling cannot start before about 12-15k windows (mean use reaches grace 48 at ≈ 48 × 2048 / 8 = 12,288 windows at depth 1 at the founding population, later at the 2,512-2,564 live experts measured at windows 1001-1300 and still rising (the population at 20k windows is unread, §8 0.2), `verify/emp/k1000_1300.log`; arithmetic). | changed | B: resumes are B's main path. A: room to grow into the pressure band helps a later modality. | Moving `FAB_N0` moves every record → an arm only. | Fleet logs [owner]; else one ≥20k-window run at defaults [GPU, or slow CPU] | medium |
| 03b-0b4-CAP | CAP can never lift inside a 20k run | Keep `CAP_TARGETS` 'off' and `CAP_PIN_WINDOWS` 20000 now (`CAP.observe` raises `NotImplementedError`, `src/capacity/api.py:1480`). At P4: the pin threshold stays in **absolute** windows, never a fraction of run length (a run-length fraction repeats the run-length-fitted LR mistake); its default comes from measured pin durations; arm 'vocab' first with `CAP_VOCAB_START` below the model's row count; valve experiments set `CAP_PIN_WINDOWS` explicitly and `RUN.cadence_audit` says "cannot fire in this run". | changed | B: after training there is no run end; an absolute pinned-time threshold works without a horizon, and CAP is B's meter on runaway growth. | A threshold unreachable in experiments hides the valve → explicit settings and the audit. | Build observe at P4 [CPU]; a pinning run on the vocab arm [CPU toy / GPU] | high |
| CONTRACT-Q-DATA-7 | Rehearsed vs pure-add, and what rehearsal buys | Two protocols. **Measurement**: D2 stands (pure-add is the headline of the add-an-area experiment, the rehearsed arm runs beside it every time). **Continue** (**[OWNER] O9**): parent replay ON via `DATA_DRAW='replay'`, `DATA_REPLAY_SHARE` 0.27, `DATA_REHEARSE_PARENT` True. `DATA_PHASE_SCHED`'s default is unchanged. Add a third arm, P+replay; 3 paired seeds. Resumes in the measurement protocol use `OPT_LR_CONTINUE='as_logged'` and state their regime (floor, or the no-log re-priced rate) in the label. | changed | B: 25% replay holds an old area at 1.936 → 1.931 bits/byte while pure-add goes to 7.846 (03 §9); pure-add is the only view of the architecture's own retention. | Pure-add as a post-training default would forget → the protocol split. At the shipped 4 areas a generated pure-add schedule silently leaves 3 areas untrained. | R vs P vs P+replay, eng's held-out block across the run boundary, 3 seeds [CPU toy / GPU]; the toy pair +0.046 held vs +0.444 worse [exists] | medium |
| CONTRACT-Q-OPT-3 | Gradient clipping 0 or 1.0 | Main default **0.0 (OFF)** until the matched pair runs. Read the archive first: the 2026-09-24 fleet stopped at 20k of about 102,000-106,000 windows of a cosine (seed-dependent), so its LR was about 0.92 of peak at the stop (arithmetic), close to the old pilots' constant 2e-3; its curves show whether the upward turn near step 6000 exists in this tree. Instrument gap: a whole-run quantile cannot show p99 across the turn; one run with `CKPT_DIR` set gives the per-step norms from OPT's checkpoint state. The continue preset clips at the parent's recorded `opt.grad_norm.p99` and reports `opt.clip.applied` share per origin (C42). | + | B: the simplest per-step damage bound for unvetted input. A: the unexplained turn is goal A's leading open hypothesis. | A blind 1.0 could clip every step (an LR cut) → the p99 setting and its reported share. | Fleet curves and final p50/p99 [owner]; a ≥8000-window run with a final checkpoint [CPU/GPU]; the pair only if p99 spikes [GPU] | medium |
| CONTRACT-Q-MEM-8 | `MEM.judge` scope | `MEM_JUDGE_FRAC` 0.0, and inert at any value today (`MEM.judge` is deferred for want of `scorer`). When judge is rowed (P5), measure {0.0, 0.1, 1.0}; prefer 0.1 if its flag precision is within paired noise of 1.0 (whole store every 10 passes, at about a tenth of 1.0's roughly 1.7× training compute). Add flag precision by entry age. | + | B: judge is memory's wrongness detector, including poisoned entries; incremental scores go stale without bound after training. | Cost → amortisation. | 3 runs at P5, ≥2 seeds, against `EVAL.wrongness_probe` [CPU toy] | medium |
| CONTRACT-Q-FAB-5 | `FAB_GRACE` retune | 48 stays; the P9 retune from `fab.mass_per_selection` stands. At the owner's 20k windows, mean use per expert is about 20,000 × 8 / 2048 = 78 > 48 at n0 = 2048, and about 62-64 at the 2,512-2,564 live experts measured at windows 1001-1300 (`verify/emp/k1000_1300.log` gate lines; arithmetic; still rising, and the population at 20k windows is unread, §8 0.2). Mean use stays above 48 while fewer than about 3,330 experts are live (20,000 × 8 / 48), so cull, rescue, lr_boost and merge are reachable, and inevitably so after training. Report, per manage pass, the retention change per area and the count of culled or merged experts whose most-served area is faded (counters built with SR0, §8 3.1). E2 carries the deferral arm (C37, critic). | + | B: culling dormant experts that serve faded areas is forgetting after training (the same argument that set `OPT_WEIGHT_DECAY` 0). | Faded-area experts culled → `comp_protect`, the retention reading, the deferral arm. | `fab.experts_past_grace_ever` in fleet logs [owner]; retention across cull passes with `FAB_GRACE` lowered [CPU] | medium |
| CONTRACT-Q-OPT-5 | Residual print or revise | **Superseded** by Q-OPT-10 (RESOLVED 2026-09-26). The continuation consequence is ruled in NEW-05. | superseded | — | — | S2 [exists] | high |
| CONTRACT-Q-CKPT-2-R2 | WORLD's grown count at the geometry gate | Keep the row-level refusal (M43: `WORLD.load_into` raises LeverError before window 0). Add a known-answer test, since nothing in `tests/` covers M43: a WORLD population mismatch in either direction is refused by name before training, and the checkpoint on disk is untouched. | + | B: continuation and rollback must fail closed. | Low. | `tests/test_world.py` or `tests/test_resume.py` [CPU] | high |
| CONTRACT-Q-WORLD-10-OPEN | The feedback path's open items | **[OWNER] O13** (the contract's "Open for the owner" list, folded into O13); recommended: `WORLD_FEEDBACK` OFF; no bound is built while it is off. Re-enabling feedback (e.g. a media arm) requires a magnitude-bound lever, ON in that arm, capping ‖world_proj(forecast)‖ at a multiple of ‖h‖ (default 10, provisional: the instability signature below), gauged by `lm.encode.extra_ratio_max`. WORLD's own objectives stay. Aligning MEM keys with h + forecast is an arm once `MEM.blend` lands. Any re-test uses a whole-epoch, annealed budget. | + | B: the unbounded 'skip' path diverged (`extra_ratio_max` 31.2, `latent_std` 0.13-0.85, one seed +0.358). A: WORLD is the media plug-in point. | WORLD costs a little (O13). | Re-test at S5 with media and the bound [GPU] | medium |
| LOW-D-A13 | Is D-A13 still open? | **Closed, on one condition.** The per-area seeding line is present at `7e902ba:src/data/api.py:733` (2026-09-03) and at `d97779d:src/data/api.py:734` (the commit that recorded the fleet's result), and the fleet's script passes `RUN_SEED` (`d97779d:gpu_world.sh:346`), so the 2026-09-24 fleet's seeds varied the corpus; seeds 0-2 give distinct bodies at HEAD (`inv/seedcheck.py`), with the same per-seed hashes at `d97779d` (`verify/emp2/seedvar.out`); identical vocab 1106 and 594 mints per seed is the deterministic mint schedule (512 + 99 × 6). Condition: the owner confirms from one fleet log's data banner that the source was synthetic (the archive is not in the repo). Then correct the stale texts: Q-WORLD-10's re-ask sentence and `src/data/api.py:150-152` ("Today they are not"). | changed | B: paired-seed verdicts are about data, not only initialisation. | Low. | Banner check [owner]; seedcheck [exists] | high |
| LOW-Q-TOK-13-PREV | What remains of Q-TOK-13 | (1) The mint-burst half is **closed** by S0b (c8d8e33; `tests/test_continuation.py` S5, "a save between a mint and the next act continues exactly"); correct `notes/AGENT_STATE.md`. (2) **Fix now**: when `CKPT.save` rotates `ckpt.pt` to `ckpt.pt.prev`, rotate the vocabulary to the path the read side already resolves for that generation (`derive.checkpoint_base` maps `<dir>/ckpt.pt.prev` to `<dir>.prev`, so `<dir>.prev.dyntok.json`), before the new vocabulary is written. No lever: a persistence invariant. | changed (priority) | B: it is the **only** older generation on disk; no best checkpoint can be saved (`Retention.consider` is deferred) and `CKPT_EVERY` is 0. Without it B has no rollback. A: a failed modality addition must roll back. | A rotation-order bug pairs the wrong vocabulary → the existing mismatch refusals and a known answer. | Save twice, resume from `.prev`, bit-exact against an uninterrupted run [CPU] | high |
| LOW-FAB-MERGED-REPORT | The `fab.merged` line mixes scopes | Fix: the run-total count with a run-scope verdict; the last-pass count with the last-pass gate. | changed | B: merges are consolidation and a forgetting risk; emergence must be observable. | None. | I10 config (`FAB_GRACE=1 FAB_MANAGE_EVERY=25`, seed 3, 300 windows) [CPU] | high |
| LOW-RESUME-SAVED-COUNTERS | `saved` counters disagree after a resume | Fix: `*.ckpt.saved` is lineage-cumulative in every package (restored with state, like `opt.ckpt.saved`), plus a process-local `*.ckpt.saved_here`. | changed | B: post-resume reports are B's measurement path. | Low. | Parent saves k, child j; every package reports (k + j, j) [CPU] | high |
| LOW-FAB_NORM_ONLY-GROWS | `FAB_NORM_ONLY=1` grows an expert | Fix: under `FAB_NORM_ONLY=1`, `FAB.grow_check` and `FAB.manage` return before acting, as under `FAB_ON=0` (the Q-FAB-11 precedent); today both test only `fab.on` (`src/fabric/api.py:3584`, `:4290`). No functionality is removed: growth in a node-less arm is a leak. | changed | B: the norm-only arm measures whether the fabric is a retention channel (the archive: fabric +0.373). | None to the default. | `fab.births` 0, `n_live` = `FAB_N0`, cull and merge ABSENT [CPU] | high |
| LOW-GPU-WORLD-ETA | `gpu_world.sh` calibrates before the first manage pass | Use `CAL_WINDOWS=600` in the retok fleet. If the post-fix ETA is still off by more than 1.5×, raise the script default from 150 to at least `FAB_MANAGE_EVERY` + 20 = 520. Keep `--status`. | changed | Indirect: GPU time must be plannable. | None. | The next fleet's ETA against wall time [GPU] | high |

**Note S0b-ship (the rule, and what surrounds it).**
- **Rule.** M = max over 3 paired seeds of |bpb(k0) − bpb(k0_nuis)|. Cadence c ∈ {3000, 1000} ships
  if bpb_c − bpb_0 ≤ M at **every** seed; among those that ship the lower mean wins; if none ships,
  0 ships. Instrument: prequential bits/byte over the same bytes.
- **Evidence so far** (CPU, equal bytes, `s0b/preq_eq.py`, `s0b/eq/s{0,1}_k{0,1000}.json`). Seed 0:
  k0 2.6892 over 759,988 bytes in 4008 windows; k1000 2.6895 over 759,803 bytes in 3815 windows (4.8%
  fewer), 3 acts; +0.0003. Seed 1 (finished since, same script): k0 2.7880 (3895 windows); k1000
  2.7958 (3721 windows), 3 acts; +0.0078. No nuisance control yet, so M is unknown. The older equal-window runs compared different bytes (756,880 vs 795,938)
  and are superseded. The archive's retok at 3000 gave held-out 4.364 bits/byte against 2.175 at 0
  (not a clean single-knob comparison: `RETOK_EVERY=0` also disabled signature batching, `79dac6c`),
  and 22 of 23 retoks added zero tokens (`src/tok/levers.py`), which the act now refuses as a no-op.
- **Belief.** The cadence belongs to U-series family (a). The ship rule tests "no harm on clean
  prequential" (R1 reading), not "forces generalisation" (the left-out-family reading R3), so the
  ship decision does not lean on the belief.
- **Hazards.** An unmeasured behaviour change in every default run past window 3000; DOM's
  competence operating point drifting at acts until Levels land; FAB growth paused up to 40% of windows
  at k1000; under 04's R-7, every retention-probe interval at `EVAL_RETENTION_EVERY` 1000 spans a k1000
  act (C03).
- **Conflicts noticed.** Q-RUN-8's interim ruling fires 3000 before measurement (O14, C40). Acts write
  Q-OPT-10 revision logs, which set a continued run's LR to the floor for ever under today's pricing
  (NEW-05). A finished k0 parent resumes at about 0.22 of peak at the fleet's 3.78 MB shape and at
  the floor only for a full 20 MB epoch (`verify/emp3/k0_epoch_child.py`), so a continuation from the fleet's kept
  checkpoints differs in rate between arms unless `OPT_LR_CONTINUE` sets one. 04-Q5 changes every synthetic stream, so the paired rule survives but the absolute M does
  not transfer across the change.

**Note FRAME-POST-TRAINING (the `continue` protocol).** A named protocol recognised on the Sample, the
way Q-DATA-7 (c) recognises protocols, and a versioned preset file of explicit lever values (C15). It
never computes other levers. Components, each behind its own lever:
1. **A schedule with no end date.** The core follows `OPT_LR_CONTINUE`, whose preset value is chosen by
   the CPU continuation arms before the preset ships (O6; arms: floor, plateau 0.1 and 0.25, rewarm 0.5
   and 1.0, regulated). 'plateau' ramps from the parent's current rate to `OPT_LR_PLATEAU` ×
   peak over `OPT_LR_CONT_WARM` 1000 steps (the tree's warmup, `src/opt/levers.py:474`), then holds.
   Cooldowns run only on branch children used for evaluation, gating and serving, never on the learner
   (the WSD / infinite-schedule pattern). Groups born after the anchor get their own clocks (C02). Not
   1.0 by default: a constant 2e-3 is where all 17 old pilots turned upward after about 6000 steps
   (Q-OPT-3, INV-28, confounded). The main-run `OPT_LR_SCHED` stays 'cosine' until the arms read; a
   non-inferior 'wsd' main-run arm would win a tie, because it serves B.
2. **Replay ON.** `DATA_DRAW='replay'`, `DATA_REPLAY_SHARE` 0.27, `DATA_REHEARSE_PARENT` True
   (**[OWNER] O9**): the parent's areas, read from disk or the checkpoint's reservoir (NEW-06).
3. **Rollback.** `CKPT_EVERY` 1000, matching the probe cadence (333 at k1000 and in media sessions at
   k3000, where the 2000∪3000 stamp union has 1000-window gaps, `03b_LIVE_CODEC.md:193`; 667 only for
   media at `TOK_RETOK_EVERY` 0);
   `CKPT_BEST_KEEP` 2; the `.prev` vocabulary fix first; the parent checkpoint and the probe set as
   frozen anchors; anchor retention for sessions that admitted a new origin (C35); a rollback restores
   a whole generation (C09).
4. **The gate** (NEW-04): the control half of each held-out block, read at session end after a settle
   window, on a cooled branch, against ε with a pre-registered combination rule.
5. **A per-step damage bound.** `OPT_GRAD_CLIP` at the parent's recorded `opt.grad_norm.p99` (grad
   norms travel in OPT's checkpoint state; the preset builder writes the number, N4);
   `opt.clip.applied` share per origin reported, with the p99.9 and clip-off arms if it binds on more
   than 10% of an admitted origin's steps (C42; Appendix B).
6. **A memory-first channel.** `MEM.read` and `MEM.blend` are deferred (P5), so today the store never
   enters a prediction. Build blend behind a MEM lever, OFF until measured (NEW-03). Quarantine writes
   run on a read-only side path (C06).
7. **Trust.** Source tags from provenance; `DATA_TRUST` 'observe'; per-origin caps on memory writes and
   on consolidation bytes; self-regulated focus gated by trust; the SR6 lock (O5).
8. **Plasticity arms**, read on the plasticity gain (NEW-11): L2 toward the anchor first, then
   shrink-and-perturb and `FAB_RESCUE`, then `OPT_WEIGHT_DECAY` 0.01.

Test-time training with reset (T0, NEW-15) is recorded as owed and not built. The consolidation
session that promotes quarantined material is NEW-18.

### 4.6 Pending measurements

| ID | Decision | Ruling and defaults | Δ | Why for B / for A | Risk → guard | Decisive test [who] | Conf. |
|---|---|---|---|---|---|---|---|
| PENDING-GPU-RETOK-FLEET | Run the ship-rule fleet | Run it **after the DOM half of Levels** lands (C12); if the owner wants GPU time sooner, label it "pre-Levels" and re-run the k0 vs chosen-cadence pair after. One commit, entirely before or entirely after `DATA_SYNTH_HOLDOUT` lands (after, it takes 04-Q5's pin rule). Keep one final checkpoint per run, and in k0 the saves at the act windows (note retok fleet (1)). The joint blackout budget is an alarm that orders a `FAB_COOLDOWN` {400, 100} arm at k1000, not a veto (C13). Verdict labelled **B-provisional** (note retok fleet). | changed | B: the first owner fleet that traverses all four phases (0.945 / 1.89 / 2.835 MB bounds at 3.78 MB, `DATA.data_plan`), and its kept checkpoints make learning after training testable at owner scale. A: AUD reuses the act. | A split across `DATA_SYNTH_HOLDOUT` loses pairing → one commit; prequential cannot see forgetting → the provisional label and the held-out re-read. | The fleet [GPU]; the held-out re-read after SR0 [GPU, in E2]; a continuation from kept checkpoints [GPU / CPU] | high |
| PENDING-CPU-S0b-SEED1 | Finish the CPU equal-bytes check | Finish it with two nuisance runs (the seed-1 pair has since finished: +0.0078, note S0b-ship): s0_k0_nuis and s1_k0_nuis (`SIG_WARMUP=801`), with scratch `s0b/preq_eq.py` at `DATA_STREAM_BYTES=760000` (one whole epoch), `OMP_NUM_THREADS=1`. Read k1000 − k0 per seed against M_cpu = max \|k0 − k0_nuis\|. A pre-read, not the ship rule; report to the owner before the GPU fleet if any seed exceeds M_cpu, crashes or is non-finite. | + | B: cheap checks before expensive ones; the act is already live by default. | Over-reading two CPU seeds → labelled a pre-read. | About 16-17 minutes, two at a time (the seed pairs took 926-1037 s) [CPU] | high |
| PENDING-S0b-SECONDARIES | The S0b secondary readings | Take them in three places (note secondaries): (a) measured today on CPU; (b) read from what the retok fleet already writes; (c) small counters, proven bit-identical against `tests/_baseline_fixture.json`, built before the fleet if a build session gets there first, else in SR1, never blocking the fleet. The SIG-width trigger has fired at HEAD's k3000 cadence (03b-16.33). Resume cost grows linearly with acts. | changed | B: blackout share, mint wait, MEM remap share and resume cost are B's risk gauges for the act. | New gauges could perturb training → counters only, bit-identity. | (a) [exists, CPU]; (b) [GPU, in the fleet]; (c) [CPU]; resume wall time vs number of acts [CPU] | high |
| PENDING-WORLD_FEEDBACK | Re-test `WORLD_FEEDBACK` | Stays **OFF**; `WORLD_ENABLED` stays **ON** (**[OWNER] O13**: OFF if the re-run shows a retention cost beyond ε); `WORLD_FEEDBACK=1` restores the wired arm exactly. Re-run for a different reason and in a different shape (note WORLD): all four arms in one post-SR0 commit with `DATA_SYNTH_HOLDOUT` ON and the retention probe ON, `DATA_DRAW` pinned 'planned'; 04-Q5's pin rule does not apply (the arms pair only with each other). Report both endpoints: last half and full run. | changed | B: the 2026-09-24 fleet read phase 1 only (about 3.8 MB of a 20 MB stream whose phases are 5 MB wide), so its null describes a stationary two-area stream, not continual learning. A: WORLD is the media plug-in point. | Re-running the stationary shape wastes a fleet → whole-epoch shape; a prequential gain hiding a retention cost → retention endpoint. | The phase-traversing re-run with SR0's probe, 5 seeds [GPU]; the data banner [owner]; S6 (b) [GPU] | medium |
| PENDING-GPU-THROUGHPUT-REBASELINE | GPU rate after the merge-scan repair | Fold it into the retok fleet: `CAL_WINDOWS=600`; per-run windows/s from each log; aggregate as total windows over fleet wall time at the chosen PAR; k0 reported separately (the plain-text rate) from the act arms (the act's cost); record GPU model, PAR, MPS, NCPU; add rates to `analyze_retok`. Label it "post-fix rate at the retok shape". | + | B: every owed B measurement is a multi-seed fleet, and none can be budgeted without a real rate. | Approximate comparison (different stream and phases) → the label. | Inside the retok fleet [GPU]; pre-fix: 38 windows/s per run early, 2-3 late, about 25 aggregate over 21 runs; merge scan 14 s → 0.033 s at n = 2049 on CPU [exists] | high |

**Note retok fleet (the command and the B additions).**
- Command: `EXP=retok CAL_WINDOWS=600 bash gpu_world.sh`. Stream 3.78 MB, one whole epoch at
  WINDOWS × 189 bytes, window cap out of reach. Arms k0, k3000, k1000, k0_nuis (`SIG_WARMUP=801`),
  k0_rerun; seeds 0-2, auto-filled with more seeds.
- (1) **Kept checkpoints**: a per-run `CKPT_DIR=$OUT/ckpt/$tag`. The act arms run `CKPT_EVERY` 0 (the
  only saves are the final one plus SIGUSR1, `src/ckpt/api.py:232-233`). The k0 arm runs `CKPT_EVERY`
  1000 and copies each save at a k3000 or k1000 act window aside (the ring keeps only `ckpt.pt` and
  `.prev`, `src/ckpt/api.py:648`), so (4)'s control has a model of the act's maturity. k0_nuis and k0_rerun run the same `CKPT_EVERY`
  1000 as k0, so the margin M = max|k0 − k0_nuis| and the run-to-run check compare like with like
  (or §8 1.5 adds a known answer that periodic saves leave a run bit-identical). This needs a
  small `gpu_world.sh` option, OFF by default and ON for this fleet.
- (2) **Secondaries per arm**: prequential bits/byte per phase; FAB growth and blackout share; the MEM
  remap share; bpt across acts; the act's share of wall; windows/s.
- (3) **B-provisional**: once SR0's `EVAL.holdout_probe` exists, re-read end-state held-out bits/byte
  per area, worst area, with a nuisance-pair margin built the same way, folded into E2. If the shipped
  cadence fails, revert to 0 and name the area that lost. That is the specific B risk live retok adds:
  old areas re-segmented with merges minted from newer areas.
- (4) **The belief's same-family test, made falsifiable (critic).** The draft predicted that the
  per-act loss spike shrinks over successive acts. It would shrink for mechanical reasons alone: later
  merges are longer and rarer, and the cosine lowers the LR through the run. So each spike is
  normalised by the fraction of positions whose segmentation changed and by the LR at the act, and
  compared with a control: the same re-segmentation applied offline to the k0 arm's checkpoint kept at
  the same window (1), so the control matches the act's model maturity. A final-checkpoint-only
  control would compare a fully trained model with act j's model at window ~3000j, confounded by
  maturity (part of the mechanical shrink). Without the matched control the reading is labelled
  descriptive, not a test. It needs the per-flush bytes
  record (secondaries (c)).
- Conflicts noticed: S0b made 3000 live before measurement (O14); 03b specified the measurement "on
  CPU at the owner's shape" and the tree made it a GPU fleet; k1000's 40% blackout breaches 04-Q9's
  20% by construction (C13); if the schedule default moves off cosine for B, `revise_horizon` goes
  inert and the verdict should be re-read; "performance decides" is read inside the run while B needs
  it after further learning, which the kept checkpoints remedy.

**Note secondaries (what was measured and what is owed).**
- (a) **Measured here, CPU, one thread, real text from `data/train`, build vocab 512, dropout 0**
  (`rule_pending_measurements/splice_time.py`, `measured.json`): `TOK.splice` of a full 17 MB tail
  8.63 s, a half tail 4.26 s; `TOK.tokenize` at a view 7.36 s; linear at about 0.5 s/MB (1 MB takes
  0.53 s). At the whole-epoch 3.78 MB shape the fleet and E1-E6 run, the tail shrinks at every act:
  per run k1000 costs about 18 s of splice (about 1 s per act) and k3000 about 6 s, at most about
  3.4% and 1% of wall at the early 38 windows/s rate. Those are the retok fleet's figures only. E2,
  which 04-Q9's +10% line is about, also makes full-tail focus acts (each re-segments the whole tail,
  `04_SELF_REGULATION.md:523-525`; arms `DATA_FOCUS_ACT_EVERY` 3 / 6 / 25, `:1507`) at
  `EVAL_RETENTION_EVERY` 160, beside ~5 retok acts and 3 phase entries: about 5-6% of wall at
  `DATA_FOCUS_ACT_EVERY` 6, about 9% at 3 and about 2.6% at 25, at 38 windows/s, before the redraw's
  own DATA rebuild (`verify/numbers3/e2_splice.py`). The ACT_EVERY-3 arm sits at the +10% line, so
  E2's splice timing is a live reading. At the
  old 20 MB / 20k-window shape the tail stays about 16-17 MB, so k3000 costs about 6 × 8.6 = 52 s and
  k1000 about 19 × 8.6 = 163 s: +10% and +31% at 38 windows/s, 0.5-2.4% at 2-3 windows/s. A resume
  replays the epoch's tokenize plus every act's splice (`compose._replay_segmentation`): near the end
  of a k1000 run about 20 s at 3.78 MB and 7.4 + 163 ≈ 170 s at 20 MB, growing linearly with acts
  (all arithmetic). Caveats: this
  container's CPU, and a vocabulary of about 1100 tokens may cost more per byte than 512.
- (b) **Read from what the fleet already writes:** `fab.grown_regression`, `fab.grown_stall`,
  `fab.births`; `fab.shift_notifications` × 400 / windows (the blackout upper bound);
  `store.n_remapped_entries` and `n_remap_events` (`src/memory/api.py:1967-1979`); `loop.acts`,
  `loop.acts_noop`, `tok.retok_noop`; per-act tail bpt from each act's warning line; the replay
  record's size (acts + 1 events per epoch).
- (c) **Build, counters only, ON, reporting only:** `tok.mint_wait_windows`; `fab.blackout_windows`
  (one name: 04's; 03b's `fab.cooldown_windows` retired), a windows count extending the existing
  `fab.growth_blackout_suppressed.*` pass counters; `loop.act_seconds` (splice and MEM remap
  timed separately); per-flush bytes beside `--loss-curve`; per-run and aggregate windows/s in
  `analyze_retok`.
- For an unbounded post-training stream, resume cost linear in acts is a B risk: the replay record
  needs compaction (e.g. a snapshot of the tail's ids at an act) before an open-ended mode exists
  (C36).

**Note WORLD (the re-scoped re-run).**
1. The stated precondition, D-A13, is met (LOW-D-A13), on the owner's banner check. D-A13 alone does
   not justify GPU time.
2. The B reason: the fleet ran on the pre-S0b tree with segmentation frozen at about 189 bytes per
   window, on a 20 MB stream capped at 20,000 windows, so it read phase 1 (eng + py) only: phase
   bounds from `rule_pending_measurements/phases.py`, bytes read (3.75-3.84 MB, eng and py only) from
   `verify/emp/phase_cross.py` and `verify/emp2/phasepos.py`. It never saw an area arrive or fade.
3. Shape: whole-epoch, equal-bytes sizing as in `EXP=retok`, through a new `EXP=world_epoch` sizing
   (stream = WINDOWS × 189 bytes, window cap out of reach, the out-of-stream flag suppressed). A plain
   `BYTES=` override would flag every run "RAN OUT OF STREAM" and price the ETA on the cap
   (`gpu_world.sh:67-70`, `:144`). Arms fb_off, fb_on,
   skip, world_off, all four in one post-SR0 commit with `DATA_SYNTH_HOLDOUT` ON and the retention
   probe ON, `DATA_DRAW` still pinned 'planned'; 5 paired seeds. 04-Q5's pin rule is scoped to fleets
   that pair with pre-change runs, and this one does not: its arms pair with each other. So the probe
   reads the time-integrated gap and end-state held-out bits/byte per area.
4. Pre-registered rule: `WORLD_FEEDBACK` flips ON only if (a) fb_on beats fb_off on the time-integrated
   all-area held-out gap (one-sided paired t, α 0.05, 5 seeds; end-state reported beside it, R5); (b) fb_on is not worse than ε on the
   worst area; (c) no seed shows the instability signature (`latent_std` < 0.9 or `extra_ratio_max` >
   10). The original last-half prequential statistic is reported beside it.
5. **Both endpoints of the existing fleet** (`results/gpu_world_2026-09-24/ANALYSIS.txt`, critic):
   fb_on vs fb_off last half +0.0033 ± 0.0031, **full run +0.0271 ± 0.0101** (about 2.7 SE worse);
   world_off vs fb_off last half −0.0027 ± 0.0016 (4 of 5 seeds better), **full run +0.0041 ± 0.0114**
   (not better). The full run strengthens `WORLD_FEEDBACK` OFF and weakens the claim that WORLD costs B
   (C33).
6. world_off vs fb_off on retention answers whether WORLD costs B; if it does beyond ε, O13.
7. Priority: after the retok fleet and after SR0. The media version (S6 (b)) is unchanged.
8. A B use noted, not ruled: WORLD's prediction error as a shift or novelty signal for gates, which
   needs no feedback into `LM.encode`.

---

## 5. New decisions the framing requires

The gap finder's finding that shapes most of these: **learning after training has no substrate in
this tree yet.** Its verified tree facts, with file and line, are in `gap/verified_facts.json`:
1. The only way to learn after training is "one more epoch" (`src/spine/compose.py:2726-2748`); there
   is no inference path and no inbox.
2. One missing callable (`logits_fn`) leaves `EVAL.curve_probe`, `holdout_probe`, `generate`,
   `coherence` and `wrongness_probe`, `MEM.blend`, `MEM.judge`, `FAB.contribution` and
   `CKPT.Retention.consider` unbuilt or unreachable (`src/spine/compose.py:1655-1830`). Memory is
   write-only; no best checkpoint is ever kept; there is no divergence alarm.
3. The continuation LR depends on whether an act fired in the parent (a revision log keeps a
   continued run at the floor for good) and, if none did, on how far the parent's grown vocabulary
   shortens the re-tokenized epoch (`src/opt/api.py:642-672`, `:2864-2874`;
   `verify/emp3/k0_epoch_child.py`: about 0.48 of peak at 756 KB, 0.22 at 3.78 MB, the floor only
   for a full 20 MB epoch).
4. `CKPT_DIR` '', `CKPT_EVERY` 0, `OPT_GRAD_CLIP` 0, and no best checkpoint while
   `CKPT.Retention.consider` is deferred (`CKPT_BEST_KEEP` 0 still means one rotating `.best`,
   `src/ckpt/levers.py:256-262`): nothing to roll back to.
5. A child missing an area its parent recorded is refused (`data.area_vanished`,
   `src/data/api.py:1728-1737`), and the checkpoint carries no data.
6. MEM's "source" is the DOM domain id (`src/spine/loop.py:2262`); `MEM_SRC_SHARE` floors only live
   sources (`src/memory/levers.py:294-297`); a DOM cull "self-releases" (`src/domains/levers.py:543-600`).
7. Every geometry field is EXACT across a resume except `lm.vocab_slots`, `fab.slots` and `fab.cap`
   (from `FAB_N0` or `FAB_SLOTS`) (`src/spine/compose.py:3238-3300`).
8. 17 old-tree pilots at a constant 2e-3 degraded from about 2.4 to 3.8-4.1 bits/byte over 48k steps
   (INV-28; confounded, no warmup).

**Defaults.** Every ruling below leaves **training-run** defaults unchanged for now, with three
qualifications: NEW-10's training default may flip after its E2 arm; NEW-08's provenance (default ON)
and NEW-11's plasticity probe (ON once §8 4.6 sizes it) are telemetry that changes no learning, the probe's wall cost
priced under C31. Other new behaviour is scoped to the `continue` preset (OFF until built) or to
telemetry. Appendix B states each value, or names it owner-set or set by §8.

| ID | Question | Ruling and defaults | Priority | Decisive test [who] |
|---|---|---|---|---|
| NEW-01 | What runs after training, and what is the unit of learning? | **Chained sessions**: each a resume with declared new material, its own length in windows or bytes (not `RUN_EPOCHS`) and a gate at its end. Serving: the last promoted, cooled checkpoint while a shadow learner trains (**[OWNER] O4**). Signal: next-byte prediction on admitted external input only. Session mode is the versioned `continue` preset (C15), OFF until built, refusing to start without `CKPT_DIR`. Per-session replay-record segments are required; an open-ended inbox (option b) needs the look-ahead draw and record compaction first (C36). Learning in place in the serving copy is rejected as a default (irreversible between checkpoints); it survives only as T0 (NEW-15). | now | The session chain: base eng, py, num, c; then four sessions from `data/continual/01_rust` .. `04_num2`; 5 paired seeds; per-area R matrix (ACC, BWT, FWT, worst-area regression) after each session, against a joint i.i.d. upper bound and a pure fine-tune lower bound [CPU toy / GPU] |
| NEW-02 | What is "too much" risk? | The owner sets **ε** and a **creep budget** (**[OWNER] O2**; recommended start 0.05 and 0.10 bits/byte). The instrument is sized to ε, not ε to the instrument (note NEW-02). Worst area, never the mean. HARD in sessions (the gate acts; acting on one session's reading rests on **[OWNER] O10**), SOFT in training runs (report). Every self-regulating controller reads it as its constraint (the ADR form). | now | Nuisance-pair calibration at the base checkpoint; validation on benign and harmful sessions reporting the family-wise false-rollback rate **and** the miss rate at ε [CPU toy / GPU] |
| NEW-03 | Build the scored-system join with both closures? | Yes, in the same commit as SR0, reusing its closure: `_logits_fn(sysm, *, use_memory)` with memory off **and** on (Q-MEM-10's "the pair is the deliverable"), `EVAL.generate` over either (modality-agnostic), `CKPT.Retention.consider` live (saves only when `CKPT_DIR` is set), a blow-up Reading that reports (an input to the gate). Probe telemetry ON subject to SR0's bit-identity; both closures reported side by side; memory-on as the **served** path OFF until measured. | now | SR0 bit-identity [CPU]; memory-on minus memory-off per area before and after an add-area session, 5 seeds; memory earns the served path if it lowers faded-area bits/byte beyond ε with no area worse [CPU toy / GPU] |
| NEW-04 | What checks a session, and what happens on failure? | A gate that acts **at session end** (note NEW-04; acting on one session's reading rests on **[OWNER] O10**): pre-registered combination of readings; a settle window; a cooled branch; hard rollback of the whole generation by default. Observe-only verdicts ON in training runs. Rejected material is never deleted. | now | Gate vs no gate on the session chain with harmful sessions injected; false rollbacks, missed harmful sessions, stability-gap depth against W ∈ {0, 1×, 2×} the probe cadence; hard vs graded rollback on the next session's ACC [CPU toy / GPU]; bit-exact resume [exists] |
| NEW-05 | The learning rate after training | `OPT_LR_CONTINUE` ∈ {'as_logged', 'floor', 'rewarm', 'plateau', 'regulated'}, default **'as_logged'**: exactly today's pricing (the floor for good if the parent carries a revision log; if not, the cosine rate for step E against 2·W1, W1 being the epoch re-tokenized with the parent's grown vocabulary, which is shape-dependent: about 0.48 of peak at 756 KB, 0.22 at 3.78 MB, the floor for a full 20 MB epoch of about 105,000 windows, `verify/emp3/k0_epoch_child.py`), with the regime printed on every resume as `opt.continue.regime`. The `continue` preset's value is chosen by the CPU arms before the preset ships (**[OWNER] O6**). 'plateau' uses `OPT_LR_PLATEAU` (0.25 when selected) and `OPT_LR_CONT_WARM` 1000; 'rewarm' ramps to `OPT_LR_REWARM` × peak (0.5 when selected) and re-decays over the session; 'regulated' sets each session's plateau from the previous gate's margin against ε (the ADR form), built after NEW-04. Groups born after the anchor get their own warm-up clock (`OPT_BORN_CLOCK`, OFF by default, ON in the preset; C02). A 'wsd' choice for `OPT_LR_SCHED` is built next as a main-run arm; the main-run default stays 'cosine'. Every arm is read on cooled branches. | now | Session-chain arms: floor / plateau 0.1, 0.25 / rewarm 0.5, 1.0 / regulated, 5 seeds, cooled branches: ACC within ε, new-area gain, worst-area regression [CPU toy]; known answers: 'as_logged' is bit-identical to today, `OPT_HORIZON_REVISE` does not move a continued run [CPU] |
| NEW-06 | Replay after training when the corpora may be gone | A replay **reservoir carried in the checkpoint** (`DATA_RESERVOIR_BYTES` per area: 0 in training runs; in the preset, interim size equal in **bytes** to the area's held-out block, written as a number by the preset builder), plus a **separate, never-drawn probe set**; both hashed and disjointness-tested (C10). Parent areas (**[OWNER] O9**) are read from disk, then the reservoir, and refused only if neither exists. The session operating default is rehearsed (`DATA_REPLAY_SHARE` 0.27 in text sessions); pure-add stays D2's measurement protocol. One replay budget per phase kind; the levers never add (C16). Generative self-replay is a later arm (NEW-16); MEM contexts as a replay source rejected (short retrieval windows). | now | Session chain with corpora withheld; reservoir {0, 64 KB, 256 KB, 1 MB} per area against full-corpus replay at equal share, 5 seeds; the smallest size within ε of full-corpus replay becomes the default [CPU toy] |
| NEW-07 | How untrusted input enters after training | **Memory-first quarantine** in the preset, ON there; not in curated training runs (note NEW-07). Promotion to weights only in a consolidation session (NEW-18). Filtering-only and a trust-weighted loss are arms. (**[OWNER] O5**, **O18**) | next | Poisoning canaries: k ∈ {5, 25, 100} poisoned documents with a trigger, from one origin and split across 2-5 colluding origins and an impersonator; quarantine and caps ON vs OFF; 5 seeds. Pass: attack success near baseline, benign learning delayed by at most one session [CPU toy] |
| NEW-08 | Provenance granularity | A session id and an origin id on every MEM entry, beside the DOM source; a lineage record per checkpoint (parent hash, session id, origins admitted with byte counts, gate readings and verdict, the R row). MEM gains delete-by-session and delete-by-origin. Default ON. Per-document ids an arm once a real inbox exists. | next | Delete-by-session removes exactly the counted entries and nothing else, bit for bit; rollback reproduces the anchor's probe readings exactly [CPU] |
| NEW-09 | Which parameters take up new material first | Tiered, in the preset: MEM learns online (admitted entries); capacity born after the anchor (media rows, new vocabulary rows, new experts) learns on OPT's per-group born-group clocks; the dense core follows `OPT_LR_CONTINUE`; heavier consolidation only in consolidation sessions. `FAB_LR_OWN` gains a scope value 'newborn', OFF by default; the preset does **not** switch on the global `FAB_LR_OWN` (C02). Freezing the core rejected. | next | Session chain, uniform vs tiered; forgetting against new-area gain as a curve; ACC within ε; 5 seeds [CPU toy] |
| NEW-10 | After training, may "not recently fed" still mean "expendable"? | In the preset, once NEW-03 lands: a faded source's entries may be evicted, and its domain culled, only when memory-on minus memory-off on that area is at most ε; an expert tied to a faded area may be culled only when `FAB.contribution` ≤ 0. Interim: a need-based floor for faded areas the model is responsible for. MEM shares are keyed by origin and area responsibility, not live DOM domain; the total faded-floor share is capped at 0.5 of the store with 0.1 reserved for quarantine (Appendix B). Culls and merges of faded-area experts are deferred and counted until 02-R11 lands (C37). **Training runs**: unchanged defaults for now, but the same rules run as arms in E2 (§8 5.3); from SR0 on every training run reports memory occupancy by area and faded-area expert culls (counters built in §8 3.1; the retok fleet runs before they exist); the training default flips if the arm stays within ε (critic). | next | Session chain, as-is vs consolidate-before-forgetting: memory's contribution per area, faded-area bits/byte, occupancy by area [CPU toy]; the training-run arms inside E2 [GPU]; the old tree's phased run a9d7258, recorded in `notes/05_ERRORS.md:602-607` (n=1, every English entry evicted) [exists] |
| NEW-11 | How plasticity is measured and kept | A **plasticity gain** probe, ON as telemetry on a read-only side path (C06) once §8 4.6 sets its N and cadence (OFF until then, N4): the drop in bits/byte on a fresh synthetic area over N windows, trained on a functional copy under a frozen RNG, **normalised by the same probe run on the parent at the training-run LR**, and reported beside a fresh-initialised model of equal size (critic). The gate's plasticity floor: the preset's gain at least 0.8 of the parent reference (provisional). Remedies are OFF arms, tried in order: L2 toward the anchor or initial weights (does not erase dormant experts), then shrink-and-perturb and `FAB_RESCUE` > 0, then `OPT_WEIGHT_DECAY` 0.01 (C32). They are justified as plasticity remedies, not by the belief (critic). `OPT_WEIGHT_DECAY` stays 0.0 in training runs. | next | An 8-session chain; plasticity gain per session against the parent reference, and ACC, under each remedy, 5 seeds; a remedy becomes the default if it keeps the gain at 0.9 or more of the parent reference where the plain preset decays, with ACC within ε [CPU toy] |
| NEW-12 | How the belief is tested | The **U-series** ladder, pre-registered now, runs next (note NEW-12, §7); its scope is **[OWNER] O3**. Perturbation levers become phase-scheduled (a training-run value and a preset value). Defaults unchanged until the ladder reads: `TOK_DROPOUT` 0 (OFF), `LM_DROPOUT` 0 (OFF), `FAB_MUT` 0.25 (ON), `FAB_BIRTH_JITTER` 0.15 (ON), 04's tag dropout as 04-Q13 rules. | now (pre-register, build the generators) / next (runs) | The U-series; the decisive reading is R3, held-out under a family left out of training [CPU toy / GPU] |
| NEW-13 | Is the trained model's shape fixed for ever? | EXACT stays the default; FAB, vocabulary rows and MEM are the growth paths. `lm.ctx` stays **EXACT** until an identity check and a cadence-rescaling known answer exist; then a widening is a declared operation at a resume boundary recorded under `ckpt.geometry` (critic). The extrapolating position arm (relative or rotary) is built **before any transformer-arm checkpoint is kept as a long-lived parent** (C43: an irreversible door; **[OWNER] O17**). Function-preserving dense growth (Net2Net, bert2BERT) later, as an arm with an identity test. Defaults: `LM_ARCH` 'gru', `LM_CTX` 128. | next | Identity: loss unchanged to 1e-6 immediately after a growth or widening resume; cadence rescaling known answer; ctx 128 → 256 plus N windows against trained-at-256 on long-range held-out bits/byte [CPU] |
| NEW-14 | A standing "B can add A later" test | A fixture in `tests/`, run at every stage commit: train a tiny checkpoint, then short sessions adding (i) a text area, (ii) vocabulary-slot widening, (iii) FAB-slot widening, (iv) from 03 S1 on, a synthetic media area, and (v) a continuation under the `continue` preset. Each must not refuse and must keep old-area probes within ε. Not a lever. | next | The test itself [CPU] |
| NEW-15 | Temporary adaptation in use (T0) | An EVAL-side lever: N gradient steps on the current document's prefix, on a functional copy, reset after the document, on the read-only side path (C06); surprising items may be handed to MEM only as quarantined writes (C07). Built **OFF**, after NEW-03. | later | Per-area held-out bits/byte with and without, reset per document, 5 seeds; wall cost [CPU toy / GPU] |
| NEW-16 | May the model learn from its own outputs? | Tagged, **added** to real data (reservoir or inbox), never substituted, with a self-generated origin id (NEW-08) and a cap of at most 0.1 of replay bytes (provisional). Built **OFF** as an arm. Unrestricted self-training rejected (tail collapse). | later | Corpora withheld; reservoir only vs reservoir + tagged self-replay at equal share, 8 sessions; faded-area bits/byte and rare-n-gram recall [CPU toy] |
| NEW-17 | Does the architecture itself earn its place for B? (critic missing 3) | An **ablation ladder** on the session chain, at equal compute and 5 paired seeds: (1) plain LM + replay + the same schedule; (2) + FAB; (3) + DOM and MEM; (4) + WORLD; (5) + live TOK and stamps. Read ACC within ε, worst-area regression and plasticity gain. This is the test that confirms or falsifies the architecture as the owner's route to B. No default changes on it without the owner. | next | The ladder [CPU toy first; GPU at owner shape] |
| NEW-18 | What is a consolidation session? (critic missing 6) | A session whose new material is the quarantine set that passed promotion: a delay of at least 1 session; corroboration by at least 2 SR6-certified independent origins, or one owner-trusted origin (O5); a clean canary; within the per-origin cap. LR: the preset's core rate (NEW-05), born-group clocks for any new capacity; replay `DATA_REPLAY_SHARE` 0.27; the same gate at ε. On rejection the promoted material returns to quarantine, tagged, with its gate readings. | next | Inside NEW-07's canary test: promotion rate of benign vs poisoned material, and the gate's verdict on each consolidation [CPU toy] |
| NEW-19 | When is a toy-set default re-checked at owner scale? (critic missing 10) | Every default whose only evidence is toy-scale carries a "toy" tag in `docs/05_DEFAULTS.md` with its owner-scale test named. The owner-scale test re-decides by the same pre-registered rule. A toy-tagged default with no scheduled owner-scale test is listed in §8's backlog. | next | None: a bookkeeping rule. The tag count is reported with each stage's `sync_counts` run [CPU] |

**Note NEW-02 (sizing the instrument to ε).**
- **Why the draft failed.** NEW-02's draft set k = 2 × each area's paired SE. The arithmetic
  (`critic/arith.txt`, `conflicts/verification_log.json`):

| Areas | Family-wise false rollbacks at k=2 (normal / SE from 5 seeds, t 4 df) | k for 5% family-wise (normal / t 4 df) | Detect a 3-SE regression after C04 + C11 (normal) |
|---|---|---|---|
| 4 | 8.8% / 21% | 2.23 / 3.47 | 46% |
| 8 | 16.8% / 38% | 2.49 / 4.29 | 36% |
| 20 | 36.9% / 70% | 2.80 / 5.56 | 25% |

  Splitting the probe into halves (C11) multiplies each half's SE by about 1.41. A best-ever reference
  over pure noise sits about 1.0 / 1.4 / 1.8 SE below truth after 4 / 8 / 16 sessions, so a cumulative
  rule against best-ever ratchets toward constant rollback, a de facto freeze.
- **The rule now.**
  - ε is an absolute tolerance in bits/byte per area per session, set by the owner.
  - k is set from the null distribution of the maximum over areas, calibrated on nuisance-pair runs
    (the S0b `k0_nuis` precedent), so the family-wise false-rollback rate is at most 5% at the actual
    number of areas.
  - Probe size (windows per area per half) and the number of runs behind the SE are chosen so that a
    single-area regression of ε is caught with at least 80% power. Under normality that needs the
    per-half SE ≤ ε / 3.08 at 4 areas, ε / 3.33 at 8 and ε / 3.64 at 20 (k + 0.84, arithmetic). At
    ε = 0.05 that is 0.016 / 0.015 / 0.014 bits/byte per half. The SE comes from pooled nuisance
    runs, not from each session's seeds, because a 5-seed SE inflates k to 3.47-5.56.
  - The achieved minimum detectable regression is printed beside every verdict (the 03b-16.25
    pattern: "raise n if the paired SE exceeds `AUD_RATE_TOL` / 2").
  - References: the per-session reference is the parent anchor; the cumulative reference is the
    release anchor re-read on the fixed probe, against the creep budget; never a best-ever maximum.
  - Every B-endpoint comparison (per-area bits/byte) has non-inferiority margin ε, fixed in advance,
    not an SE (C04). Codec-attribute criteria (recover exact at S3: 03b-16.24, 03b-16.29) keep their
    pre-registered SE margins: ε is a bits/byte budget and does not transfer to them.
- **Owed:** the per-window variance of probe bits/byte, from nuisance pairs, to turn these ratios
  into window counts. No such reading exists yet.

**Note NEW-04 (the session gate).**
- **Readings:** the worst-area probe regression against ε (control half, raw per-area series, not
  R-7-rebased; `data.focus.rebase_step` as an input); canary trips; the negative-flip rate per probe;
  KL divergence to the anchor on a fixed reference set; the plasticity gain; the stability-gap depth.
- **Combination rule, pre-registered (critic):** rollback **triggers** are a worst-area breach of ε
  after the recovery window, or a canary trip (a canary's trigger-conditioned reading beyond its
  nuisance-calibrated threshold). **Alarms** (reported, escalated after 3 in a row) are KL to the
  anchor and the negative-flip rate above thresholds calibrated on nuisance pairs (provisional until
  §8 4.1), and a plasticity gain below its floor. Stability-gap depth is reported only. Every trigger
  and alarm is in the nuisance calibration, so the 5% family-wise rate covers the rule as a whole.
- **Timing:** the verdict comes only at session end, after a **settle segment** of W windows (W = 2
  probe readings) in which self-caused acts are deferred to the start of the next session, not
  dropped (C03). Mid-session, only NonFinite or the blow-up Reading may stop a session.
- **Cooled branch (critic):** the gate reads a cooled branch cut at session end, at the same cooling
  state as the anchor; the cooldown's cost is charged inside the session. Otherwise plateau and rewarm
  sessions would be rolled back for schedule reasons alone.
- **Rollback forms:** hard (restore the whole generation: TOK, LM, codec, MEM, DOM, FAB, OPT and the
  replay segment) by default; graded (interpolate weights toward the anchor, WiSE-FT) and partial
  (restore the dense core, keep MEM and FAB additions) as arms. A partial rollback is refused by name
  when the vocabulary or codec moved during the session (C09). With TOK live, mints arrive every 200
  windows, so how often a partial rollback is admissible is itself measured.
- **Rejected sessions:** the material is never deleted: it stays in the inbox store (raw bytes and
  provenance, outside the checkpoint), tagged 'rejected', and the rejected weights are kept as a
  named checkpoint. **Retry ladder (critic):** retry once with `DATA_REPLAY_SHARE` raised to 0.40,
  once more with the core LR halved, then escalate to the owner after 3 rejections of the same
  material (the C34 count).
- **Anchors:** the preset requires `CKPT_DIR`, keeps the parent as the anchor, sets `CKPT_BEST_KEEP`
  2, and retains the pre-promotion anchor of every session that admitted a new origin (C35).
- **Conflicts:** "nothing frozen" (resolved: freeze snapshots, not the live system); "never remove
  functionality" (resolved: the gate defers or diverts).

**Note NEW-07 (memory-first quarantine, as ruled).**
- New material is written to MEM at once, on a **read-only side path**: no optimizer step, no TOK
  minting, no DOM, FAB, SIG or CAP update; the trust book may observe; the only persistent write is a
  MEM entry tagged with origin and session (C06). A bit-identity known answer covers the side path.
- It is readable by evaluation and gate paths, **not** by served retrieval, until promoted (C07).
- Promotion to weights happens only in a consolidation session (NEW-18). Corroboration counts only
  origins whose independence SR6 copy detection has certified after E5's majority-false and
  impersonation worlds; until then only owner-trusted origins promote (C05, O5).
- `DATA_SRC_CAP` (count-based per-origin cap; its value is **[OWNER] O18**) and the canary probes bind
  whatever the corroboration.
- In the preset, MEM shares are keyed by origin: quarantined origins get a ceiling and no floor, so an
  origin that splits into many DOM domains cannot multiply its share (C08).
- The belief is limited here, not dismissed: its form (4), tolerance of unreliable content, is graded
  contradicted without attribution (§7). Unreliable sources are attributed and gated, and they stay
  observable in memory and in the trust book.

**Note NEW-12 (the U-series).**
- **Families:** (a) segmentation (`TOK_DROPOUT`, retok cadence); (b) `LM_DROPOUT`; (c) tag drop;
  (d) codec drift; (e) dynamic mapping (a new generator: DATA's synthetic source is order-2 Markov
  only); (f) liar and noise share; (g) corrupted targets; **(h) structural unreliability of the system
  itself (critic):** expert and route dropout during training, MEM retrieval dropout, `FAB_MUT` and
  `FAB_BIRTH_JITTER` levels, and stamps and Levels OFF (C24's arms).
- **Design:** levels 0 / low / mid / high; 5 paired seeds; **matched on bytes and compute** (family (a)
  changes bytes per token, so token-matched arms read different bytes, the confound `EXP=retok` was
  redesigned to remove, `gpu_world.sh:73-77`); both single-pass and replay regimes; streams sized to
  traverse every phase. Family (a) reuses the retok harness (equal bytes plus a nuisance-pair margin).
- **Readings:** R1 clean held-out; R2 held-out under the same family; **R3 held-out under a family
  left out of training (decisive)**; R4 forgetting, stability-gap depth and plasticity gain; R5
  in-context adaptation (including MEM hit rate on the dynamic-mapping area).
- **Verdict rule, pre-registered:** the strong form is **falsified** if R2 improves but no family, at
  any level, improves R1 or R3 beyond the paired-seed spread. It is **supported** if a mixed-family arm
  improves R3 and R4 at equal compute. (f) and (g) are expected to harm without tags.
- **Self-regulated variant:** an ADR arm raises a family's level while ε holds; the plain ladder is its
  control.
- **Evidence corrected (C19).** The digest quoted "1.32-1.66 vs 2.06-2.25" for tag dropout; the first
  numbers are forget_easy, not untagged reads. Like for like, untagged mean6 is 1.736 / 1.757 / 1.670 at
  drop 0.25, 2.246 / 2.214 / 2.064 at drop 0, and 1.751 / 1.665 / 1.621 never tagged
  (`results/self_regulation_design_2026-09-26/prototypes/d2/out/`). Same-family invariance is
  supported; there is no gain in clean generalisation over a never-tagged model.

---

## 6. Conflicts

45 conflicts: 25 between rulings, 5 between a ruling and a principle, 9 between principles, and 6
between the owner's belief and the evidence. Each row gives the resolution, the rule used under
§2's order, the residual risk and the test. The ruling changes these produced are already in §4 and
§5. Where the critic changed a resolution, the row says so.

| ID (kind) | Conflict | Resolution | Rule used | Residual risk → test [who] |
|---|---|---|---|---|
| C01 (ruling vs ruling) | NEW-05, FRAME (1), TREE-OPT_HORIZON_REVISE-LEVER, Q-OPT-5 and S0b-ship designed the continuation LR three ways, and `OPT_HORIZON_REVISE=False` would silently switch a continued run from floor-for-ever to the no-log re-pricing (the cosine rate for step E against 2·W1 of the re-tokenized epoch: a shape-dependent unramped jump; for an act-parent whose log is suppressed, E is its act-shortened epoch, so the rate lands above NEW-05's k0 figures: about 0.37-0.45 of peak at 3.78 MB by the same pricing against 0.22 for a k0 parent, `verify/final/c01_actparent_nolog.py` (approximate inputs); `src/opt/api.py:642-663`, `:2864-2874`; `verify/emp3/k0_epoch_child.py`). | One lever family, `OPT_LR_CONTINUE` ∈ {'as_logged', 'floor', 'rewarm', 'plateau', 'regulated'}; default 'as_logged' (today's pricing, labelled; critic); 'plateau' absorbs 'trunk'; `OPT_HORIZON_REVISE` is in-run only; the preset's value is chosen by the CPU arms (O6); no interim value. | N4; R0 sets the level, with R1 as the budget inside which R2 is maximised | The preset may learn too slowly at the floor → the plateau arm, the plasticity gain. NEW-05's arms and known answers [CPU] |
| C02 (ruling vs ruling) | `FAB_LR_OWN` is one global flag (`src/fabric/levers.py:930`) whose envelope starts from peak and is clamped at 4.0 × the applied rate (`:961`): under a floor core, newborn experts cap at about 0.2 of peak while **old** experts serving faded areas run at up to about 0.19 of peak, nearly 4× the core. Born media rows would sit on a decayed rate, and `OPT_LR_SHIFT_WARM` only attenuates. The tree disagrees with itself on P1-H15 (`levers.py:933` "UNFIXED"; the `own_lr_scale` docstring: unspellable). | Per-group continuation clocks in OPT for groups born after the anchor (also 03-16.9's lr-shield); `FAB_LR_OWN` scope 'newborn', OFF; the preset leaves the global `FAB_LR_OWN` off; a CPU confirmation test replaces the P1-H15 prerequisite; correct the comment. | R1 (old experts must not outrun the core), then R2 (born capacity learns), then R4 (a later modality arrives as a born group) | More checkpoint state; newborn experts disturbing routing → the gate, FAB readings. 'newborn' known answer; floor core ± born clocks, 5 seeds; P1-H15 run [CPU] |
| C03 (ruling vs ruling) | Stamps from TOK acts (3000 or 1000), AUD refreshes (2000 and every act) and 04's redraws leave NEW-04's rollback window rarely open, and never at k1000. 04's R-7 rebase drops every probe interval spanning an act (`docs/proposals/04_SELF_REGULATION.md:603-616`), which would hide act damage from any gate reading the rebased books. | Verdict only at session end after a settle segment in which self-caused acts are deferred; the preset's probe cadence at most a third of the shortest stamp interval; R-7 stays inside the focus books; gates read raw series plus `data.focus.rebase_step`. Critic: at k1000, and in media sessions at k3000 (the 2000∪3000 stamp union), that cadence rule adds about 7.2% forward windows, 2.1-2.4% of wall at today's 6 windows per area, marginally above E6's 2% cap (arithmetic; a lower bound that scales with the ε-sized probe) → O11. | R1 over R3; N1 (deferred, not dropped) | Mint delivery waits up to W; a settle segment could mask brief damage. Gate vs none at k3000 and k1000, W ∈ {0, 1×, 2×}; the `rebase_step` known answer [CPU] |
| C04 (ruling vs ruling) | NEW-02's k = 2 per area gives family-wise false rollbacks of 8.8-70% (NEW-02 note); a best-ever reference drifts below truth and ratchets toward a freeze; four margins exist for one idea. **Critic (blocking):** the draft fix (family-wise k plus split halves) widened the effective tolerance to 3.2-3.5 full-probe SE (normal) or 4.9-6.1 (t) at 4-8 areas, with no power requirement: a regression 1.5× the original budget is caught 36-46% of the time at 4-8 areas (25% at 20). | The owner sets ε and the creep budget (O2); k from the null distribution of the max over areas (nuisance pairs); probes sized for 80% power at ε; parent anchor per session, release anchor cumulative; every B-endpoint margin is ε (codec-attribute criteria keep their pre-registered SE margins). | R0; R1; N2 | Reaching the power target may need large probes → priced under R1 (C31). Nuisance calibration; benign and harmful sessions reporting **both** error rates [CPU toy / GPU] |
| C05 (ruling vs ruling) | NEW-07 promotes on corroboration by ≥2 origins; 04-Q12 records that collusion defeats agreement (majority-false inverted trust at 3 of 3 seeds; 50% impersonation flipped it). | Only SR6-certified independent origins count; until then only owner-trusted origins promote (O5); caps and canaries apply regardless. R1 acts here as a lock, not a budget, because poisoning is not measurable within ε: canaries and the SR6 lock are R1's instrument there. | R1 over R3 | Genuine sources wait; a hand-set root of trust. Canaries with 2-5 colluding origins and an impersonator; E5 worlds, model-free [CPU] |
| C06 (ruling vs ruling) | A forward pass also feeds TOK pair counts and mints, DOM, FAB, SIG and CAP statistics and the trust book, so quarantine writes, T0 adaptation and the plasticity probe would shape vocabulary and routing before any promotion. | One read-only side path for all three: the live learner's parameters and optimizer state untouched (a functional copy may step, as the plasticity probe and T0 do, and is discarded); minting and DOM, FAB, SIG, CAP updates off; the only persistent write is a tagged MEM entry; the trust book may observe. A bit-identity known answer per path. | R1; R0 (side paths must not perturb what they measure); N2 respected | Quarantined keys come from an unadapted model. Bit-identity per path; a canary run counting mints and spawns attributable to the poison origin [CPU] |
| C07 (ruling vs ruling) | Memory is low-risk for weights only: once memory-on is the served path, a quarantined entry steers outputs at once. | Served retrieval reads admitted entries only; quarantine is readable by evaluation and gates; items from use enter as quarantined writes. | R1 as budget (the R2 cost is accepted until arms show ε holds without it) | New facts reach served outputs only after admission. A quarantined canary trigger has zero effect on served logits [CPU] |
| C08 (ruling vs ruling) | `MEM_SRC_SHARE` 0.5 is both floor and ceiling per **live DOM source** (`src/memory/levers.py:294-297`): an untrusted origin forming its own domain gets a floor and can split to multiply its share; faded areas lose theirs. | In the preset, shares are keyed by origin: quarantined origins get a ceiling and no floor; areas the model is responsible for (live or reservoir-held) get floors; the total faded-floor share is capped at 0.5 with 0.1 reserved for quarantine (Appendix B). Training runs unchanged. | R1, then R2 | Only as good as unspoofable origin ids. A spam origin split over many domains, domain-keyed vs origin-keyed shares [CPU] |
| C09 (ruling vs ruling) | Id-space state (minted vocabulary, the LM rows for those ids, the codec snapshot, MEM keys, DOM, the replay record) makes a partial rollback incoherent; a hard MEM rollback would erase quarantine. | A hard rollback restores the whole generation; a partial one only for groups whose id space did not move, else refused by name; quarantine lives in an inbox store outside the checkpoint; the `.prev` vocabulary fix is a prerequisite. Critic: measure how often a partial rollback is admissible (mints arrive every 200 windows). | R1; N1 | Partial rollback is narrow. Hard rollback bit-exact across TOK, codec, MEM; partial refuses when the vocabulary moved; the inbox survives [CPU] |
| C10 (ruling vs ruling) | NEW-06's reservoir was to carry each area's probe bytes, while 01-M9 and 04-Q5 forbid held-out data in rehearsal. | Two disjoint stores (the reservoir; a never-drawn probe set), hashed and disjointness-tested; the interim reservoir is sized in bytes like the held-out block, not the block itself; a new origin's held-out block is cut before any training. | R0; R1 | Storage grows with areas. Disjointness test (03 App. A pattern) [CPU] |
| C11 (ruling vs principle) | One probe per area feeds the 'retention' draw, damping, CKPT best-keep, the ADR controllers, the gate and the ADR noise arm: the crossing the instrument line forbids (`src/eval/levers.py:146-148`). Adaptive reuse overfits one probe. | Each held-out block is split: a control half read by gates and controllers, a report half read only for verdicts and the R matrix. NEW-02's sizing accounts for the halves' larger SE (about 1.41×). | R0 (measurement integrity) | More probe windows. The control-vs-report gap after N controlled sessions [CPU / GPU] |
| C12 (ruling vs ruling) | "Run the retok fleet now" vs "build DOM's Levels before the fleet". | Build the DOM half with its known answers, then run. If the owner wants GPU time sooner, label the fleet "pre-Levels" and re-run the k0 vs chosen-cadence pair afterwards. | R0 (measure what ships); R1 | One small build of delay. Levels known answers; k1000 Levels ON vs OFF [CPU] |
| C13 (ruling vs ruling) | Every stamp blocks FAB growth for 400 windows (`src/fabric/api.py:4348-4357`): 40% at k1000 by construction, and scoping stamps cannot help because text acts always move the view. | The 20% budget is an alarm that orders arms (stamp scope; `FAB_COOLDOWN` {400, 100} at k1000), not a veto on the pre-registered rule. `FAB_COOLDOWN` stays: the CAP runaway precedent (2048 → 8192 in 19 lifts). Growth after training is read in continuations from the kept checkpoints. | R0 over a hand-set threshold; R1 over R3 | Prequential may miss post-training growth starvation. Fleet blackout secondaries; the cooldown arm; continuation acquisition [GPU] |
| C14 (ruling vs ruling) | D-5 refreshes the codec at every act, including 04's redraw-only acts, shortening holds below the measured 2000 windows and adding FAB stamps. | Redraw-only acts stamp OPT only: no FAB stamp, no codec refresh. The codec refreshes at view-moving acts and at `AUD_REFRESH_EVERY`. | R0 (stay in the measured regime); R1; D-5 is a design-workflow decision (N3), pending the owner's answer in §8 0.2 | The codec lags a large mixture shift. `aud.flip_per_refresh` and hold lengths with 'retention' ON vs OFF, S5 [GPU] |
| C15 (ruling vs principle) | Several NEW rulings set "X in sessions, Y in training runs": a mode that computes levers is the L1 defect (`.rework/PLAN.md:155`, applied at `docs/04_CONTRACT.md:2557`), and FRAME itself forbids it. | `continue` is a versioned preset file of explicit lever values, printed at start and recorded in the manifest; no lever reads a mode or another lever; parent-dependent values (the p99 clip, reservoir bytes) are written as numbers by a printed builder at launch; refusals (e.g. "`CKPT_DIR` required") are checks. | N4 | The preset drifts from the documents → the preset file is the source of truth. A preset launch is bit-identical to the same values as explicit levers [CPU] |
| C16 (ruling vs ruling) | Five replay numbers for one concept (0.27; 0.27-0.3; ≥ 0.25; 0.3 of text plus 1/3 of earlier media); a media session could replay about 57% old bytes; 04-Q4 refuses a child with missing parent bodies while NEW-06 admits it; D2 and 04-Q4 default to pure-add while B operates rehearsed. | Pure-add is the **measurement** protocol (N3), rehearsal the **operating** preset. One budget per phase kind, never added: `DATA_REPLAY_SHARE` 0.27 in text sessions (arms 0.15 / 0.27 / 0.40); in a media phase `DATA_TEXT_SHARE` 0.3 for text and `DATA_MEDIA_REHEARSE` for earlier media. Parent areas from disk, then the reservoir, refused only if neither. | N4; N3; R0 (measured 0.25-0.3 in 03 §9, 0.27 in 04) | 0.27 was fitted to one toy, and the right share depends on shift size → the arms. 04-6-UNMEASURED (h); NEW-06 sizes [CPU / GPU] |
| C17 (ruling vs ruling) | 04-Q2 (c) requires `alloc_freedom` ≥ 0.2, while 04-Q6/Q7's safety floors mechanically lower it. | Floors stay; (c) is read on `alloc_freedom` normalised by its maximum under the floors in force; the raw value is reported beside it. | R1, then R3 | Normalising can flatter a tiny range → raw beside. E2 and E1 report both [GPU] |
| C18 (ruling vs ruling) | E4 turns tags ON only if the **untagged** read is not worse (on the toy it is +0.051, t 2.56, so OFF). It ignores retention: easy-area forgetting (P2 end → run end) is +1.87 / +1.65 / +1.23 never-tagged against +0.31 / +0.29 / +0.28 tagged at drop 0.25 and +0.15 / +0.25 / +0.19 at drop 0; hard unchanged (`d2/forget_tag.py`, re-run). | E4 reads both: ON if tagged worst-area retention improves beyond ε and the untagged cost stays within ε; otherwise both numbers to the owner (O7). The tag comes from provenance, never content. Critic: the drop ladder also reads tagged retention, because drop 0.25 trades it (+0.28-0.31 against +0.15-0.25) for untagged use. | The owner's trade (O7): R1 against R1 (tagged retention against the untagged regression on served prompts of unknown origin) | Prompts of unknown origin pay the untagged cost. E4 with per-area forgetting under both reads, 5 seeds [GPU]; `d2/out/tags_*`, `base_*` [exists] |
| C19 (belief vs evidence) | The digest (and NEW-12's draft) quoted tag dropout 0.25 as untagged 1.32-1.66 against 2.06-2.25 without it; the first figures are forget_easy, not untagged reads. | Corrected (NEW-12 note): like for like, drop 0.25 gives 1.736 / 1.757 / 1.670, drop 0 gives 2.246 / 2.214 / 2.064, never-tagged 1.751 / 1.665 / 1.621. Invariance supported; no clean gain; the strong form stays open until R3. | R0 | Toy, 3 seeds, one family. The family (c) ladder with R3 |
| C20 (belief vs evidence) | Form 4 (unreliable sources and targets) against every in-tree reading: learning-progress focus drew the liar more than cred at 4 of 5 seeds; credibility did not emerge untagged; majority-false inverted trust at 3 of 3; pure-add +0.444 against +0.046 rehearsed; the unanchored 'skip' forecast diverged. The literature agrees (about 250 documents backdoor a model; label-noise damage roughly quadratic in the noise rate). | Unreliable content and sources go behind attribution and gates; no default leans on form 4. The belief is honoured by testing it inside the continue protocol: families (f) and (g) with the trust gate ON vs OFF. | R1 over R3 | If the belief holds at scale, gating slows emergent robustness; the test would show it. U-series (f), (g) in the preset; E5 [CPU toy / GPU] |
| C21 (belief vs evidence) | Forms 1-2: injected noise costs in single-pass training and helps with repeated data (dropout hurts single-epoch Pythia at 160M and 1.4B, digest), so one constant value is the wrong shape. `FAB_MUT` 0.25 and `FAB_BIRTH_JITTER` 0.15 are ON without ladder evidence. | Perturbation levers become phase-scheduled (a training value and a preset value); defaults unchanged until the ladder reads; the preset's replay regime is where noise arms are tried first; `FAB_MUT` and `FAB_BIRTH_JITTER` get family (h) (critic). | R0; R3 orders the arms | They stay ON unmeasured until (h) reads. U-series (a), (b), (h), single-pass vs replay [CPU toy] |
| C22 (belief vs evidence) | The live codec was argued partly from the belief; the tree does not support it (caption worse 11 of 16, understanding worse 5 of 8, a ceiling cost at 7 of 8, not pairs; coordinate rows more sensitive to code perturbation at 3 of 3). | Keep the live codec on the owner's ruling "no frozen codecs" (N3) and on B-plasticity (the post-training arrival cell), bounded by the drift budget and canaries; do not cite the belief (critic: this rests on N3, not on R2 over R5, which C45 rejects). The belief is tested by R3: an LM trained on the live codec, read on a held-out perturbed codec. | N3; R0 decides | Within-run codec ceiling cost. S3 replica; S5 (ii) with the arrival cell; family (d) R3 |
| C23 (belief vs evidence) | Form 3 (variable mappings above a diversity threshold) has the best literature support but was never tested here above a threshold: every route reads 0-15% on held-out combinations. The design world's 0.94 → 0.03 at n = 200 is informative evidence that composition fails at this scale; the 03b prototypes (6-12 prompts) and Route 3 (12-16 prompts, about 32 trained combinations) are not; DATA's generator is order-2 Markov. | Neither lean on it nor dismiss it: first the CPU diversity pilot and the dynamic-mapping generator. | R0 | The threshold may lie beyond toy scale. 03-16.4's pilot; U-series (e) with R5 [CPU] |
| C24 (belief vs evidence) | Stamps and Levels tell controllers to ignore self-caused variability; if the belief holds, that removes a chance to adapt. Against: the CAP runaway and spurious DOM spawns. | Stamps and Levels stay ON on the R1 evidence alone. The draft's rationale "the belief is about inputs" is dropped (critic; O3): the OFF arms are part of family (h). | R1 over R3 | Missed adaptation if the belief holds for controllers. Levels ON vs OFF [CPU]; S5 (iii) [GPU]; family (h) |
| C25 (principle vs principle) | "Performance decides" vs "ties go to the flexible or self-regulated option". | B's endpoints decide. A tie (within ε on the time-integrated gap and not significantly different) goes to the flexible option only if it passes R1 and is exercised (not pinned at a cap). Every tie is reported with its 90% interval, never read as equivalence. | R0 > R1 > R3 > R5 | Low-powered ties (3-5 seeds) mostly go to the flexible option. Applied in E1, E2 and the retok fleet |
| C26 (principle vs principle) | Flexibility (live tokenizer, live codec, self-regulated draws, growth) vs "without risking too much": each flexible part is a new path to drift. | Flexibility operates inside ε (ADR form); reversibility, not freezing, makes it safe. The guard against the budget becoming a freeze is the plasticity **gain** against the parent reference (critic: the draft's ratio was inverted and could not detect a freeze). | R1 bounds R2 and R3; N2 | A tight ε turns into a freeze → the plasticity floor alarm. NEW-02 validation plus NEW-11 on an 8-session chain |
| C27 (principle vs principle) | "Nothing frozen" vs anchors, probe sets and instruments, and vs fixed live dimensions (grid, lattice, SIG width, EXACT fields, the depth lever). 03b-16.33's own trigger has fired at HEAD's k3000 cadence. | Freeze snapshots and instruments, never the live learner. A fixed live quantity must be needed for consistency within a session **and** name a route to change at a session boundary, with an identity test. Instruments are versioned; a replacement needs a bridge session in which both read. The SIG-width re-derive is now owed. | N2; R0 | Storage and reading cost. The SIG re-derive known answer [CPU]; NEW-13's identity check; the bridge protocol at the first instrument change |
| C28 (ruling vs ruling) | 03-16.5 rejects deleting the CAP reporting wires to fund the budget; Q-CLOCK-1 plans that deletion once the histogram exists. | A deletion that **moves** a function removes nothing: (b) is admissible after an equivalence known answer, case by case. | N1 | The equivalence may miss a case at scale. P4 pinning run, wires vs histogram [CPU] |
| C29 (principle vs principle) | Emergence preferred vs hand-built trust, quarantine, floors and caps. | Build a guard only where emergence was measured to fail (credibility did not emerge untagged); keep the emergent path as an arm; log every guard decision so emergence stays observable. | R1 over R3; R0 | Guards could mask emergence that appears at scale. E5; trust-gated vs ungated arms (04-Q1 condition 5) |
| C30 (principle vs principle) | PLAN 3.8 (no verdict at n = 1) vs in-run self-regulation and gates: OPT already refuses to damp at `seed_count` 1, so if PLAN 3.8 covers gates, a session gate can never act. | Control actions (logged, reversible, bounded by a budget calibrated on multi-seed nuisance runs) may act at n = 1; verdicts keep PLAN 3.8 (O10). | R1; R0; N3 | Actions on noisy single readings → C04's calibration and C03's recovery window. NEW-04's gate run counts false rollbacks |
| C31 (principle vs principle) | Wall-time caps (04-6.2's 2%, E3's 2%) push toward monitoring less; a longer `DATA_TRUST_EVERY` detects poisoning later. | Monitoring is priced under R1: floors (readings per phase or session; a reading at every codec refresh; ≥ 1 trust pass per session and per N bytes from a new origin) hold, and caps apply above them. Collisions go to the owner (O11); C03's cadence (at least 2.1-2.4% of wall against a 2% cap, at today's 6-window probe) is the first. The plasticity gain probe (NEW-11: N windows on a functional copy per reading, N and cadence per §8 4.6) is priced here too. | R1 over R6 and R5 | Throughput falls at the owner's shape. GPU bench; E3/E6 report cost at the floor |
| C32 (principle vs principle) | Single-pass evidence favours `OPT_WEIGHT_DECAY` 0 (it also protects dormant experts serving faded areas); the plasticity literature favours decay (a worse base model that adapts better); a frozen codec may win within the run and close adaptation after it. | Decisions bearing on B read performance after further learning. WD stays 0 in training runs; the first remedy tried is L2 toward the anchor or initial weights (a snapshot, not zero), then shrink-and-perturb and WD 0.01; a winning frozen control goes to the owner (O12). | R1 > R2 > R5 | L2 toward the anchor may slow new learning → read on the plasticity gain. NEW-11's remedies on 8 sessions; 03b-16.28's arrival cell |
| C33 (principle vs principle) | B > A vs A-openness choices: WORLD kept for A although world_off beat fb_off in the last half (−0.0027 ± 0.0016, 4 of 5); 'kv' claims text-only; the tag entry point trades localisation (B) against label-free routing (A). Critic: over the full run world_off is +0.0041 ± 0.0114, not better, so the "WORLD costs B" reading is weaker than it looked. | A-openness is honoured by built-OFF arms and by components that cost within noise and do not feed the LM. If the phase-traversing re-run shows WORLD costs retention beyond ε, `WORLD_ENABLED` defaults OFF (still built) and the owner confirms (O13). `LM_SRC_AT` 'input' default, 'head' arm; 'mem' claims are the A route. | R1/R2 over R4 over R5; N3 | Toy A verdicts may invert at scale. The WORLD re-run with SR0's probe; E4 with both entry points [GPU] |
| C34 (ruling vs ruling) | 03b-16.18's no-hidden-freeze rule adopts a codec still over threshold at hold expiry; that knowingly breaks a HARD session budget. | In the preset, hold expiry is a gate event, decided by the session-end gate (NEW-04: only NonFinite or the blow-up Reading stops a session mid-session): roll back, pull back by interpolation (arm), or accept on the owner's word; the codec keeps training; escalate after 3 rejections. Training runs unchanged. | R1 over R3; N2 | Repeated rejections starve adaptation to a new audio kind → escalation. S3 `{hold, count}`; S5 (ii); S8 (h) |
| C35 (ruling vs ruling) | Poison discovered after promotion and older than the kept anchors cannot be removed: gradient unlearning is unreliable and the ring holds 1-2 generations. | An anchor-retention lever keeps the pre-promotion anchor of every session that admitted a new origin, for a declared horizon (8 sessions, provisional; Appendix B); NEW-08's lineage names which anchor predates an origin. | R1 over R6 | Disk; very late discovery discards all learning since that anchor. Canary discovery 1, 2 and 4 sessions after promotion; rollback restores the canary baseline [CPU] |
| C36 (ruling vs ruling) | The draw and the resume assume a known epoch; the replay record and resume cost grow with acts (at k1000 near a run's end, about 170 s at 20 MB, about 20 s at the whole-epoch 3.78 MB). | Chained sessions bound each epoch; per-session record segments. Before an open-ended inbox: the look-ahead draw (04-Q9) and record compaction. | R2; R1 | Long sessions still pay resume cost linear in their own acts. Resume wall time vs acts; look-ahead equivalence [CPU] |
| C37 (ruling vs ruling) | At the owner's shape culls, rescue and merges are reachable (mean use about 78 selections at the founding 2048 experts, about 62-64 at the 2,512-2,564 live experts measured at windows 1001-1300, still rising (the population at 20k windows is unread, §8 0.2), against grace 48) while the need signal that should spare useful experts is void (`FAB.contribution` raises `NotImplementedError` and its producers are missing, `src/spine/compose.py:1808-1818`). | NOW: in the preset, culls and merges of experts whose most-served area is faded are deferred (not executed, counted) until `FAB.contribution` works, which 02-R11 builds after NEW-03 (§8 3.5). Training runs report the count from SR0 on, and E2 carries the deferral as an arm (critic). | R1; N1 (deferral, not deletion) | The population grows while culls wait; CAP is inert. `fab.contrib_distinct_values` > 1; retention across culls with `FAB_GRACE` lowered [CPU] |
| C38 (ruling vs ruling) | The digest treats the default schedule as repeated re-warming. The tree's wavelength sentinel 0 fits one cycle to the run (`src/opt/levers.py:605-630`), so restarts never fired in the **new** tree's results. Critic: 04-Q10 cites the **old** tree's 0.75 GB run, where 3 full-amplitude restarts (at 263,965 / 504,894 / 756,851) left 81% of the run getting worse (`src/opt/levers.py:677-685`). | The door-closer is "fitted to the run length" (C01 handles it). Restarts stay an arm. The old-tree run is recorded as in-tree support for the concern that re-warming causes forgetting. 04-Q10's B value is the CKPT producer, not damping. | R0 | None beyond C01's. C01's arms |
| C39 (ruling vs ruling) | 04-Q1 waits for the OPT schedule ruling, whose arms live on the session chain, while E1's shape (e) is itself a continuation. | Order: the toy continuation arms (C01) on CPU; then E2; then E1, shapes (a)-(d) at the training-run schedule and (e) under the preset with the winning `OPT_LR_CONTINUE`, on cooled branches. | R0 (sequencing) | A toy continuation verdict may not transfer. C01, E2, E1 in that order |
| C40 (ruling vs principle) | `TOK_RETOK_EVERY` 3000 fires in every default run past window 3000 before its measurement. | The owner's ruling stands (N3; O14). Critic: bit-exact resume and the lever revert do not undo damage to old areas; the guards that bound the risk are the held-out worst-area re-read and pinned cadences in dependent experiments; `CKPT_DIR` is recommended in long runs. | N3; R0 | Unmeasured damage to old areas until the re-read. The fleet (after C12), the re-read after SR0, CPU seed 1 with nuisance runs |
| C41 (principle vs principle) | Every ruling defers to a test, and the owed tests exceed any plausible GPU budget (the U-series alone is 8 families × 4 levels × 5 seeds × 2 regimes = 320 runs with family (h); E1 is 120). | Tests run in §2's order (§8); anything runnable on CPU runs here in parallel. One order for decisions and tests (critic). | R1 > R2 > R3 > R4, applied to tests; R0 | A's tests wait; toy A verdicts may invert. The throughput re-baseline sets the budget |
| C42 (ruling vs ruling) | A clip at the parent's p99 binds mostly on new-area steps (new material has larger gradients), an LR cut on exactly the new learning, and does not stop poison whose gradients look normal. | Keep it in the preset; report `opt.clip.applied` share per origin; if it binds on more than 10% of an admitted origin's steps while ε holds, run the p99.9 and clip-off arms. | R1 as budget (the R2 cost is accepted until arms show ε holds without it); R0 | Slower acquisition; poison bounded only by caps and quarantine. Clip p99 / p99.9 / off in the continuation arms [CPU] |
| C43 (ruling vs principle) | Any parent trained with the transformer arm's learned absolute position table is locked to its context for life: an irreversible A door. | Default GRU with `LM_CTX` 128. Build the extrapolating position arm **before** any transformer checkpoint is kept as a long-lived parent. `lm.ctx` stays EXACT until an identity check and a cadence-rescaling known answer exist (critic: a wider context changes what every windows cadence means). | R4, as an irreversible closure (weighed first; **[OWNER] O17**) | Transformer runs before then stay locked. NEW-13's tests [CPU] |
| C44 (ruling vs principle) | `AUD_ANCHOR_W` 10 (D-4, D-7) was measured against at 5 of 6 readings (weakly: the codec-only reading is about 1.5 unpaired SE at one seed; the 4 LM readings are confounded with the snapshot, 03b:249-250), and following the refreshed snapshot it does not bound cumulative drift. | No change until S3's anchor-0 arm. B's cumulative-drift guard is the drift budget and the release-anchor arm. | R0 (D-4 and D-7 are design-workflow decisions, N3, pending the owner's answer in §8 0.2) | Possibly a mildly harmful default until S3. S3 replica, anchor 0 vs 10 [CPU after S3] |
| C45 (ruling vs ruling) | 'measured_arrival' (a per-area rate after training, B) needs 'nested', which lost melody timbre at 3 of 3 seeds (64 clips, one beyond noise; higher on tones exact and melody contour at 3 of 3). | Status quo (D-2, 'spec') until the post-training arrival cell reads (R0): S3 reports what 'nested' unlocks; the arrival cell decides, read after further learning (C32). | R0 | Post-training areas get a pre-training stride. S3; the arrival cell |

---

## 7. The unreliability belief

> "the challenges of an unreliable system will force it to generalize, at least by how I believe it"

The register treats this as a hypothesis to honour and to test. It is neither established nor
dismissed. It steers which arms are built and tested first (R3). No default leans on it until the
left-out-family reading (R3) reads; then that test (R0), not the belief, can set the default.

### 7.1 The forms the belief can take, and what the evidence says

| Form | Literature verdict (digest) | In-tree evidence for | In-tree evidence against | Settling test here |
|---|---|---|---|---|
| **1. Invariance**: training under a perturbation makes the model robust to that perturbation | Supported, **same family only** (BPE-dropout up to +2.3 BLEU; domain randomisation). Against transfer: salt-and-pepper training gives no robustness to uniform noise (Geirhos 2018); diversity, not noise, drives robustness (Fang 2022). | Tag dropout 0.25 makes a tagged model usable untagged: untagged mean6 1.736 / 1.757 / 1.670 against 2.246 / 2.214 / 2.064 at drop 0. | No gain in clean generalisation over a never-tagged model (1.751 / 1.665 / 1.621), and tagged retention is worse (C18, C19). | U-series R2 vs R3 per family |
| **2. Regularisation**: noise improves clean generalisation | Depends on the regime: helps with scarce or repeated data (NEFTune 29.79% → 64.69%), hurts in single-pass pretraining (dropout hurts single-epoch Pythia at 160M and 1.4B). | None measured. | Lagged-self selective loss (the opposite of exposure) was also negative, so neither side is supported by that mechanism (04-Q14). | U-series (a), (b) in single-pass vs replay regimes, R1 |
| **3. Variable mappings force adaptation** | Supported **above a threshold** of task diversity, with capacity and memory (ADR; in-context learning from dynamic meanings; Raventos 2023, Kirsch 2022). | None. | Every composition route reads 0-15% on held-out combinations. The design world's 0.03 on 200 prompts (0.94 in-distribution) shows composition failing at this scale; the 6-16-prompt readings are uninformative (C23). | 03-16.4 diversity pilot; U-series (e) with R5 |
| **4. Tolerating unreliable content and sources** | Contradicted **without attribution** (networks fit random labels; accuracy falls roughly quadratically with label noise; about 250 documents backdoor models from 600M to 13B; a domain tag restores knowledge capacity lost to junk). | None. | Learning-progress focus drew the liar more than cred at 4 of 5 seeds (0.179-0.221 against 0.123-0.135); noise out-drew both credible sources in P3 at 5 of 5; credibility did not emerge untagged; majority-false inverted trust at 3 of 3; pure-add +0.444 against +0.046 rehearsed; WORLD's unanchored 'skip' forecast diverged (`latent_std` 0.13-0.85, one seed +0.358). | U-series (f), (g) inside the continue protocol, trust gate ON vs OFF; E5 |
| **5. Unreliable system components** (the literal reading, added on the critic's point; O3) | Not graded by the digest. Stochastic depth (1202 layers, 4.91%) is its example of noise that regularises. | None. | None. `FAB_MUT` 0.25 (a scale-free birth mutation) and `FAB_BIRTH_JITTER` 0.15 (so a growth burst does not mint exact clones) are ON for mechanical reasons (`src/fabric/levers.py:686-713`), not the belief; their levels are unmeasured (C21). | U-series family (h): expert and route dropout, MEM retrieval dropout, `FAB_MUT` and jitter levels, stamps and Levels OFF |

### 7.2 Where the rulings lean on the belief, and how

| Ruling | How it leans | Status |
|---|---|---|
| S0b-ship, 03b-16.15, PENDING-GPU-RETOK-FLEET (live re-segmentation, family a) | The owner's "a good way for the llm to learn". The ship rule tests "no harm on clean prequential" (non-inferiority), so shipping honours the belief without depending on it. The same-family test (spike depth across acts) is made falsifiable by normalising and an offline control. | Honoured, not relied on. CPU +0.0003 (seed 0), +0.0078 (seed 1); no nuisance margin yet. |
| 03b-16.14, 03b-16.21 (live codec drift, family d) | Previously cited as a reason. Now kept on the owner's "no frozen codecs" ruling and on post-training plasticity (C22). | No support yet, no refutation. R3 on a held-out perturbed codec settles it. |
| 04-Q13 (tag dropout, family c) | Tag dropout is justified by invariance (untagged use, robustness to a missing tag), not by "forces generalisation" (C19). | Form 1 supported; strong form not. |
| 03-16.4 (composition, form 3) | The design's clearest test of the best-supported form. | Pilot first. |
| 03b-16.2, 04-Q15 (per-segment and progress-driven rates) | Varying the stride is segmentation perturbation for media. | Toy evidence against: a fixed stride beat or tied every adaptive rate on bits/s, and codec-invariant readings tie. |
| 04-Q1, 04-Q7, NEW-07, 04-Q12 (sources) | Form 4 as a **hazard**: unreliable content exploits self-regulation. Hence trust eligibility, floors, quarantine and caps. | Limited, and tested in (f), (g). |
| NEW-11 (plasticity remedies) | The draft called shrink-and-perturb and `FAB_RESCUE` the belief's best-supported form; they are now justified as plasticity remedies only (critic). | Tested as plasticity remedies in NEW-11 (§8 4.6); the belief is tested separately by the U-series. |
| 03b-16.26, TREE-S0b-LEVELS (stamps and Levels) | They remove self-caused variability from **control** signals. Kept ON on R1 evidence (the CAP runaway, spurious spawns), not on a scope argument (C24). | The OFF arms are in family (h). |
| 04-Q4 (P vs P+parent) | Pure-add is the harsh, unprotected condition; the belief could predict the fabric learns to protect under it. | One toy pair against it (+0.444 pure vs +0.046 rehearsed). P vs P+parent is a direct test. |

### 7.3 The tests that would settle it in this tree

- **The U-series ladder** (NEW-12): families (a)-(h), levels 0 / low / mid / high, 5 paired seeds,
  matched on bytes and compute, single-pass and replay regimes, streams sized to traverse every phase.
  Decisive reading: **R3**, held-out under a family left out of training.
- **Pre-registered verdict:**
  - *Falsified (strong form):* R2 improves, but no family at any level improves R1 or R3 beyond the
    paired-seed spread.
  - *Supported:* a mixed-family arm improves R3 and R4 (forgetting, stability gap, plasticity gain)
    at equal compute.
  - *Expected:* (f) and (g) harm without tags; with the trust gate ON the harm shrinks.
- **The composition diversity pilot** (03-16.4, CPU) and U-series (e): form 3.
- **The retok fleet's same-family test**, normalised by the share of positions re-segmented and the LR
  at each act, against an offline re-segmentation of the k0 arm's checkpoints kept at the same act
  windows (note retok fleet (1), (4)): form 1 for segmentation.
- **P vs P+parent vs R** (04-Q4, Q-DATA-7): does the architecture protect itself under the harsh
  condition?
- **The architecture ladder** (NEW-17): whether the full stack (whose live, varying parts are the
  "unreliable system") beats a plain LM with replay on B's endpoints.

**What a result would change.** If a mixed-family arm improves R3 and R4 at equal compute, the
perturbation levers get preset values ON through their phase schedule and the ADR noise arm becomes a
default candidate under ε. If the strong form is falsified, the belief is kept where it is supported:
as a tool for same-family invariance (untagged use, robustness to missing tags and to segmentation
changes).

---

## 8. The test plan

Ordered to unblock B soonest, under §2's order. **[CPU]** runs in a session like this one;
**[GPU]** on the owner's card; **[owner]** is reading or ruling. CPU work runs in parallel with the
GPU queue.

### Stage 0 — now: no build, no GPU

| # | Test | Decides | Who |
|---|---|---|---|
| 0.1 | Rule on O1-O20, above all **O2 (ε and the creep budget)**, which sizes every gate and margin (O11 after §8 4.1 reads) | §3.3 | [owner] |
| 0.2 | Read the 2026-09-24 fleet archive: one log's data banner (LOW-D-A13); the `n_live` trajectory (Q-CAP-2); `fab.experts_past_grace_ever` and cull counts (Q-FAB-5); per-flush curves and final `opt.grad_norm` p50/p99 (Q-OPT-3). **[OWNER]** confirm: did you take any of 03b's D-1..D-10? | LOW-D-A13, DECISIONS-Q-CAP-2 (O20), CONTRACT-Q-FAB-5, CONTRACT-Q-OPT-3; N3 (03b-16.23's D-5 narrowing, C14, C44) | [owner] |
| 0.3 | Two CPU nuisance runs: s0_k0_nuis, s1_k0_nuis at 760,000 bytes (about 17 min; the seed-1 pair is done) | PENDING-CPU-S0b-SEED1 (pre-read for S0b-ship) | [CPU] |
| 0.4 | Phase-traversal check of every pre-registration with `DATA.data_plan` (seconds); resize E1-E6, the WORLD re-run and the U-series to one whole epoch | 04-Q1, 04-Q6, 04-Q7, 04-Q13, NEW-10, PENDING-WORLD_FEEDBACK, NEW-12 | [CPU] |
| 0.5 | d3 testbed pre-checks: `DATA_REHEARSE_EVEN` 0.5 and `DATA_FOCUS_FLOOR` 0.5, 5 seeds | 04-Q6, 04-Q7 | [CPU] |
| 0.6 | 'kv' format-variant world by extending `results/self_regulation_design_2026-09-26/prototypes/critic/td_stress.py`; E5's truth-discovery worlds, model-free, including colluding and impersonating origins | 04-Q8, 04-Q12, C05 | [CPU] |
| 0.7 | Resume wall time as a function of the number of acts | C36, PENDING-S0b-SECONDARIES | [CPU] |

### Stage 1 — small builds with CPU known answers (unblock the fleet and rollback)

| # | Build and its known answer | Decides | Who |
|---|---|---|---|
| 1.1 | Rotate the vocabulary with `ckpt.pt.prev`; save twice, resume from `.prev`, bit-exact | LOW-Q-TOK-13-PREV, C09 | [CPU] |
| 1.2 | DOM half of Levels, with identity and cross-act known answers; one k1000 run ON vs OFF reading `part.n_created` / `n_culled` | TREE-S0b-LEVELS, C12 | [CPU] |
| 1.3 | Counters, bit-identical against `tests/_baseline_fixture.json`: `fab.blackout_windows` (extending the existing `fab.growth_blackout_suppressed.*`), `tok.mint_wait_windows`, `loop.act_seconds`, per-flush bytes, `tok.bpt_tail` | PENDING-S0b-SECONDARIES, 03b-16.26, 03b-16.33 | [CPU] |
| 1.4 | `OPT_HORIZON_REVISE` (in-run only) and `OPT_LR_CONTINUE` with 'as_logged' bit-identical to today; a continued run's LR unchanged by `OPT_HORIZON_REVISE` | TREE-OPT_HORIZON_REVISE-LEVER, NEW-05, C01 | [CPU] |
| 1.5 | `gpu_world.sh`: a kept-checkpoint option (OFF by default; in k0, the saves at the act windows copied aside; k0_nuis and k0_rerun save at the same cadence), `CAL_WINDOWS=600`, rates in `analyze_retok`, an `EXP=world_epoch` sizing | PENDING-GPU-RETOK-FLEET, PENDING-GPU-THROUGHPUT-REBASELINE, LOW-GPU-WORLD-ETA, PENDING-WORLD_FEEDBACK | [CPU] |
| 1.6 | Low fixes and their tests: `FAB_NORM_ONLY` grows nothing; lineage and process `saved` counters; `fab.merged` scopes; the M43 WORLD-population refusal; `FAB_LR_OWN` at `OPT_LR_SCHED='none'`; all six CAP grounds print | LOW-*, CONTRACT-Q-CKPT-2-R2, 04-Q11, CONTRACT-Q-CAP-1 | [CPU] |

### Stage 2 — the first owner fleet

| # | Test | Decides | Who |
|---|---|---|---|
| 2.1 | `EXP=retok CAL_WINDOWS=600 bash gpu_world.sh` after 1.2 and 1.5, one commit, with kept checkpoints, the secondaries and the normalised spike test; the throughput re-baseline rides inside it; a `FAB_COOLDOWN` 100 arm at k1000 if the blackout alarm trips | S0b-ship (provisional), PENDING-GPU-RETOK-FLEET, PENDING-GPU-THROUGHPUT-REBASELINE, C13 | [GPU] |

### Stage 3 — SR0 and the scored-system join (build, then CPU tests)

| # | Build and its test | Decides | Who |
|---|---|---|---|
| 3.1 | `EVAL.holdout_probe` with control and report halves; `DATA_SYNTH_HOLDOUT`; SR0's bit-identity (`EVAL_RETENTION_EVERY` 50, 500+ windows, FAB and MEM on) and the holdout admission tests; counters for memory occupancy by area and for culled or merged experts whose most-served area is faded | 04-Q5, 04-6.2, C11, NEW-10, C37 | [CPU] |
| 3.2 | Both `logits_fn` closures, `EVAL.generate`, `CKPT.Retention.consider` fed by the probe, a blow-up Reading; `Saves.best` becomes non-zero; the Reading reaches `maybe_step` | NEW-03, 04-Q10 | [CPU] |
| 3.3 | The 'replay' draw and `DATA_REHEARSE_PARENT`; SR0's 'replay' realisation and PYTHONHASHSEED tests | 04-Q1, 04-Q4 | [CPU] |
| 3.4 | The observe-mode trust book and SR3's bit-identity | 04-6.3 | [CPU] |
| 3.5 | `FAB.contribution` and its producers (targets, candidates, 3.2's memory-off closure): `fab.contrib_distinct_values` > 1 on a run | 02-R11, C37 | [CPU] |
| 3.6 | NEW-13's identity known answer (loss unchanged to 1e-6 immediately after a growth or widening resume) and its cadence-rescaling known answer; the extrapolating position arm (relative or rotary) built, if the owner rules so, before any transformer-arm checkpoint is kept as a long-lived parent | NEW-13, C43, O17 | [CPU] |

### Stage 4 — the B core on CPU at toy scale (in parallel)

| # | Test | Decides | Who |
|---|---|---|---|
| 4.1 | Nuisance-pair calibration: per-window variance of probe bits/byte, k for 5% family-wise, probe size for 80% power at ε | NEW-02, C04 | [CPU] |
| 4.2 | Continuation LR arms on the session chain (floor / plateau 0.1, 0.25 / rewarm 0.5, 1.0; 'regulated' runs after 4.4, once the NEW-04 gate it reads exists), born-group clocks ON vs OFF, clip p99 / p99.9 / off, uniform vs tiered uptake, `OPT_LR_SHIFT_WARM` N ∈ {0, 100, 400} at k3000 in the add-an-area resume (stability-gap depth); 5 seeds, cooled branches | NEW-05, NEW-09, C01, C02, C42, TREE-OPT_LR_SHIFT_WARM, O6 | [CPU] |
| 4.3 | R vs P vs P+replay vs P+parent, eng's held-out block across the boundary, 3-5 seeds | CONTRACT-Q-DATA-7, 04-Q4 | [CPU] |
| 4.4 | The gate vs no gate with injected harmful sessions (pure-add of a noise or liar area; corrupted targets); W ∈ {0, 1×, 2×}; hard vs graded rollback; how often partial rollback is admissible; then 4.2's 'regulated' arm on the built gate | NEW-04, C03, C09, C30, NEW-05 ('regulated'), O6 | [CPU] |
| 4.5 | Reservoir sizes {0, 64 KB, 256 KB, 1 MB} with corpora withheld | NEW-06, C10, C16 | [CPU] |
| 4.6 | Plasticity gain against the parent reference, and the remedies, on an 8-session chain; the gain probe's N (windows on the functional copy) and cadence, with its wall cost (C31) | NEW-11, C26, C32 | [CPU] |
| 4.7 | Poisoning canaries with quarantine, caps, colluders and impersonators; consolidation sessions; anchor retention with late discovery; the read-only side path's bit-identity; delete-by-session and delete-by-origin exact, and lineage rollback reproducing the anchor's readings | NEW-07, NEW-08, NEW-18, C05-C08, C35 | [CPU] |
| 4.8 | The architecture ladder (plain LM + replay → + FAB → + DOM, MEM → + WORLD → + live TOK and stamps) | NEW-17 | [CPU] |
| 4.9 | U-series toy families (a), (b), (c), (e), (f), (g), (h) with R3; the dynamic-mapping generator first | NEW-12, §7 | [CPU] |
| 4.10 | Consolidate-before-forgetting; MEM 'quantile' vs 'fixed' in a phased run with source floors | NEW-10, 04-Q11 (a), 03-16.8 | [CPU] |
| 4.11 | The standing "B can add A later" fixture | NEW-14 | [CPU] |
| 4.12 | Composition diversity pilot on the design-world harness, 1-2 seeds (A and the belief, after the B core) | 03-16.4, C23 | [CPU] |
| 4.13 | Once SR2 builds `DATA_DRAW_HORIZON`: the look-ahead equivalence known answer 04-Q9 names, with chunk events in `seg_log` and a resume test | 04-Q9, C36 | [CPU] |

### Stage 5 — the owner's B fleets

| # | Test | Decides | Who |
|---|---|---|---|
| 5.1 | A continuation from 2.1's kept checkpoints onto a new area (e.g. `data/continual/01_rust`), under the preset chosen in 4.2: plasticity and retention at owner scale | FRAME-POST-TRAINING, NEW-01 | [GPU] |
| 5.2 | B-safety instruments first (§2): E6 (probe cadence), E3 (trust audit and wall), E5 (actuation arms, once SR6 exists) | 04-6.2, 04-6.3, 04-Q12 | [GPU; E3 observe on CPU] |
| 5.3 | E2 (3 seeds, whole-epoch sizing), with the retok cadence's held-out worst-area re-read, `REHEARSE_MAX`, the floors, and the training-run arms of NEW-10 and C37 | 04-Q6, 04-Q7, 04-6-UNMEASURED, S0b-ship, NEW-10 | [GPU] |
| 5.4 | E1 at whole-epoch sizing: shapes (a)-(e), 120 runs | 04-Q1, 04-Q2, 04-Q3 | [GPU] |
| 5.5 | The phase-traversing WORLD re-run, 4 arms, 5 seeds, all in one post-SR0 commit with `DATA_SYNTH_HOLDOUT` and the retention probe ON and `DATA_DRAW` pinned 'planned' (04-Q5's pin rule does not apply) | PENDING-WORLD_FEEDBACK, O13 | [GPU] |
| 5.6 | E4 (tags, both sides and the drop ladder) | 04-Q13 | [GPU] |
| 5.7 | Owner-scale U-series for the families that read at toy scale; the architecture ladder at owner shape | NEW-12, NEW-17 | [GPU] |
| 5.8 | `OPT_GRAD_CLIP` pair only if 0.2 shows p99 spiking across the turn; `OPT_HORIZON_REVISE` True vs False as a fleet arm | CONTRACT-Q-OPT-3, TREE-OPT_HORIZON_REVISE-LEVER | [GPU] |

### Stage 6 — A: the media stages

| # | Test | Decides | Who |
|---|---|---|---|
| 6.1 | The GPU bench (`RUN_BENCH=1 RUN_PROFILE=1`) | 03b-0b-GPU-BENCH, 03b-16.30 | [GPU] |
| 6.2 | After the S3 build: the replica live vs frozen with anchor 0 vs 10; the recipe check; per-family ceiling calibration; spec vs nested; the rate-rule noise fixture | 03b-16.14, 16.18, 16.24, 16.25, 16.29, 16.31, C44, C45 | [CPU] |
| 6.3 | After S4: the add-a-modality resume known answers; the M2 purity pilot | 03-16.1, 01-M2 | [CPU] |
| 6.4 | S5: rate sweep on 2-4 s clips that fit `LM_CTX`; the plasticity matrix with frozen controls and the post-training arrival cell; (iii) routing under acts; (iv) coordinate rows; App. B (d) with the diversity and mixed-perturbation axes; (e) with the anchor arm; the continuous insert on held-out combinations | 03b-16.2, 16.17, 16.26, 16.28, 03-16.3, 03-16.4, 03-16.9 | [GPU] |
| 6.5 | S6 (b) forecast-caption; S8 arms (vocoder, 'rep', 'windows', MEM over media, the handover on a real-audio area) | 03b-16.32, 01-M8, 03b-16.13, 16.19, 16.20, 16.21, 03-16.8 | [GPU] |

**Backlog.** Every default tagged "toy" under NEW-19 without a scheduled owner-scale test is listed
here as it is found.

---

## Appendix A. The critic's issues and how each was handled

None was rejected. Three were applied with an amendment, stated in the row.

| # | Severity | Target | Issue | How it was handled | Where |
|---|---|---|---|---|---|
| 1 | blocking | NEW-02, C04, C11, NEW-04 | "Too much" was defined by probe noise; the family-wise fix and the split halves widened the tolerance 1.6-3× without saying so; no power requirement; four of five gate readings had no threshold or combination rule. | **Applied, amended.** The owner sets ε and a creep budget (O2); the probe is sized for ≤ 5% family-wise false rollbacks **and** ≥ 80% power at ε; the minimum detectable regression is printed with every verdict; one combination rule (triggers vs alarms); every B-endpoint margin is ε. *Amendment:* the register also recommends a starting ε (0.05) and creep (0.10), so it can operate before the owner rules; because probes are sized to ε, a different ε resizes the probes rather than re-deriving the budget. | §3.3 O2; NEW-02 and NEW-04 notes; C04 |
| 2 | blocking | 04-Q1 / E1, 04-Q3, 04-6.2 | At the 20 MB / 20,000-window shape E1 never leaves phase 1, so no area fades. | **Applied.** Whole-epoch sizing for E1-E6 (04 runs all six at the 20 MB shape), the WORLD re-run and the U-series; phase bounds in each pre-registration; a run that does not consume the whole epoch is invalid. The premise holds for frozen segmentation; at HEAD's k3000 the shape reaches phase 2 for its last ~790-940 windows only (seeds 0-2; 04-Q1 note 7). 04-6.2's floor recomputed: 1000 gives 4 readings in phase 1, below the floor of 5. | 04-Q1 note (7); 04-6.2; NEW-12; §8 0.4 |
| 3 | major | NEW-05, C01, FRAME (1) | 'floor' as a lever default covered every resume, silently changed D2's measurement protocol, and stacked with other unmeasured guards; no consolidation LR. | **Applied.** Lever default 'as_logged' (today's pricing, labelled); the preset's value chosen by the CPU arms; measurement resumes state their regime; the consolidation session is specified (NEW-18); the owner is told today's measured pricing (O6): 'floor' changes nothing for parents with a revision log, nor, for a full 20 MB epoch (about 105,000 windows, a shape no planned run uses), for no-log parents, which resume at the floor too because their re-tokenized epoch is half as long; it lowers the no-log rate at the 756 KB and 3.78 MB shapes (about 0.48 of peak at 756 KB, 0.22 at 3.78 MB, the shape the register runs; `verify/emp3/k0_epoch_child.py`). | NEW-05; C01; CONTRACT-Q-DATA-7; NEW-18; O6 |
| 4 | major | NEW-11, C26, C32 | The plasticity ratio was inverted and baselined on session 1 under the same preset, so it could not detect a freeze. | **Applied.** A plasticity **gain** normalised by the parent at the training-run LR and reported beside a fresh-initialised model; a floor against that reference; decay tracked separately. | NEW-11; C26 |
| 5 | major | the priority order, C41, C24, NEW-01, NEW-07/C05, NEW-02 | Owner decisions were made for the owner; the order ranked A-openness above flexibility and was applied differently to tests. | **Applied, amended.** An owner register (§3.3, O1-O20). *Amendment:* rather than only listing the order as an owner question, the register adopts the critic-consistent order as its working recommendation (flexibility serving B above A-openness; R1 as a budget; one order for decisions and tests) and offers the draft as the alternative. | §2; §3.3 O1, O3, O4, O5, O6 |
| 6 | major | NEW-12, C24, C21 | No family tests unreliable **system** components; C24 narrowed the belief to inputs. | **Applied.** Family (h) added; C24's rationale replaced by R1 evidence. | NEW-12; §7; C21; C24 |
| 7 | major | PENDING-GPU-RETOK-FLEET | The spike-shrink prediction could not fail (merges get rarer and the LR falls). | **Applied.** Spikes normalised by the re-segmented share and the LR, against an offline re-segmentation of k0's checkpoints kept at the same act windows (so the control matches model maturity); otherwise labelled descriptive. | Note retok fleet (4) |
| 8 | major | NEW-04, NEW-05, C01 | The gate compared an un-cooled trunk with a cooled anchor, biasing against plateau and rewarm. | **Applied.** The gate reads a cooled branch cut at session end; the cooldown is charged inside the session. | NEW-04 note |
| 9 | major | NEW-10, C37, 02-R11 | Training runs keep destroying faded areas' memory and experts, so B starts from a damaged parent. | **Applied, amended** (not in the retok fleet: its counters are built with SR0). The rules run as arms in E2; from SR0 on every training run reports memory occupancy by area and faded-area expert culls; the training default flips if the arm stays within ε. | NEW-10; CONTRACT-Q-FAB-5; C37; §8 3.1, 5.3 |
| 10 | major | 04-Q13, C18 | Tag dropout 0.25 trades tagged retention for untagged use, unflagged. | **Applied.** The drop ladder reads tagged worst-area retention too; the trade, R1 against R1 (tagged retention vs untagged served use), goes to the owner with the drop value (O7). | 04-Q13; C18; O7 |
| 11 | major | NEW-01 | No test of the whole architecture against a plain baseline. | **Applied.** NEW-17, the ablation ladder. | NEW-17; §8 4.8, 5.7 |
| 12 | major | NEW-13, C43 | Widening `lm.ctx` now changes what every windows cadence means, on B's resume path, before its identity test exists. | **Applied.** `lm.ctx` stays EXACT until the identity and cadence-rescaling known answers exist; then a declared resume-boundary operation. C43's requirement (the extrapolating arm before any transformer parent is kept) stays, as **[OWNER] O17**. | NEW-13; C43; O17 |
| 13 | minor | C38 vs 04-Q10 | Disagreement on whether restarts ever fired. | **Applied.** "Never in the new tree"; the old tree's 3-restart run is recorded as support for the re-warm concern. | C38 |
| 14 | minor | LOW-D-A13 vs PENDING-WORLD_FEEDBACK | Closed vs "appears met", with two commit citations. | **Applied.** Closed on the owner's banner check; one citation set (`7e902ba:733`, `d97779d:734`). | LOW-D-A13; note WORLD |
| 15 | minor | 03b-16.32, PENDING-WORLD_FEEDBACK, C33 | The ruling applied the last-half statistic only; the full-run column (`docs/04_CONTRACT.md:3565`) was not weighed. | **Applied.** Both endpoints reported (full run fb_on +0.0271 ± 0.0101; world_off +0.0041 ± 0.0114). | 03b-16.32; note WORLD; C33 |
| 16 | minor | C22 vs C45 | The same situation decided under different rules. | **Applied.** C22 rests on N3 (the owner's "no frozen codecs"). | C22 |
| 17 | minor | many | New levers and budgets without stated defaults. | **Applied.** Appendix B states each, or names it owner-set. | Appendix B |
| 18 | minor | C40, S0b-ship | The stated guards did not bound the stated risk. | **Applied.** The real guards named; `CKPT_DIR` recommended in long runs. | S0b-ship; C40 |
| 19 | minor | NEW-12 | "Matched on tokens" re-creates the confound `EXP=retok` removed. | **Applied.** Matched on bytes and compute. | NEW-12 note |
| 20 | minor | C03, 04-6.2 | The cadence rule's wall cost was not computed. | **Applied.** About 7.2% extra forward windows at k1000 and in media sessions at k3000, 2.1-2.4% of wall at today's 6 windows per area (a lower bound: it scales with the ε-sized probe), marginally above E6's 2% cap → O11, ruled after §8 4.1. | C03; 04-6.2; O11 |
| 21 | minor | NEW-11 | Overstated the belief. | **Applied.** Justified as plasticity remedies only. | NEW-11; §7.2 |
| 22 | minor | C09, NEW-04 | Partial rollback almost never admissible with TOK live; no retry policy. | **Applied.** Admissibility is measured; a retry ladder (replay 0.40, then core LR halved) and escalation after 3 rejections. | NEW-04 note; C09 |
| 23 | minor | 03b-16.15, NEW-04 | 17 PASS cited against a commit message's "18 checks". | **Resolved.** `tests/test_continuation.py` has 18 `check(...)` call sites; the S1 "a length below the cursor is refused" check is written twice, as the two branches of one `try` (lines 94 and 96), so 17 execute. The run here printed 17 PASS, 0 failing, including all four S5 bit-exact cases (`rule_media/cont_test.log`). The citation stands for text; media cases are owed at S3/S4. | 03b-16.22 (test cell) |

**The critic's "missing" list.** (1) ε, creep, power, combination rule → NEW-02, NEW-04, O2. (2) Phase
traversal → 04-Q1 note, §8 0.4. (3) The architecture test → NEW-17. (4) An absolute plasticity
reference → NEW-11. (5) Family (h) and a control for the spike test → NEW-12, note retok fleet.
(6) The consolidation session → NEW-18. (7) The owner register → §3.3. (8) The continuation rule's
effect on measurement protocols → NEW-05 ('as_logged'), CONTRACT-Q-DATA-7. (9) Parent retention inside
training runs → NEW-10, CONTRACT-Q-FAB-5. (10) Re-checking toy defaults at owner scale → NEW-19.
(11) Retry and escalation; partial-rollback admissibility → NEW-04 note. (12) Stated defaults →
Appendix B.

---

## Appendix B. Defaults of the new levers, budgets and preset values

"Provisional" marks a number with no measurement behind it, chosen for the stated reason; its test is
in §8. "Owner-set" marks a number only the owner should set.

| Name | Package | Default (training runs) | `continue` preset | Basis |
|---|---|---|---|---|
| `OPT_LR_CONTINUE` | OPT | 'as_logged' (today's pricing; regime printed as `opt.continue.regime`) | No value until §8 4.2 reads (**[OWNER] O6**) | C01, NEW-05 |
| `OPT_LR_PLATEAU` | OPT | 0.25 (read only under 'plateau') | Per §8 4.2 | FRAME; provisional |
| `OPT_LR_REWARM` | OPT | 0.5 (read only under 'rewarm') | Per §8 4.2 | NEW-05; provisional; arm 1.0 |
| `OPT_LR_CONT_WARM` | OPT | 1000 steps | 1000 | The tree's warmup (`src/opt/levers.py:474`) |
| `OPT_BORN_CLOCK` (born-group clocks) | OPT | OFF | ON: warm over `OPT_LR_CONT_WARM` to 0.25 of peak, then hold | C02; provisional (the plateau arm value) |
| `OPT_HORIZON_REVISE` | OPT | True (in-run only) | True | 03b 0b.5 |
| `OPT_DAMP_SOURCE` | OPT | 'off' | 'off' | 04-Q10 |
| `OPT_GRAD_CLIP` | OPT | 0.0 (OFF) | The parent's recorded `opt.grad_norm.p99`, written as a number by the preset builder (N4) | CONTRACT-Q-OPT-3, FRAME (5) |
| Clip-binding alarm | OPT | — | 10% of an admitted origin's steps | C42; provisional (a p99 clip binds on about 1% of the parent's steps by construction) |
| `OPT_LR_SHIFT_WARM` | OPT | 0 | 0 | Arms {100, 400} |
| `FAB_LR_OWN` scope 'newborn' | FAB | OFF | OFF | C02 |
| `FAB_COOLDOWN` | FAB | 400 | 400 | Arm 100 at k1000 (C13) |
| `DATA_REHEARSE_PARENT` | DATA | False | True (**[OWNER] O9**) | 04-Q4 |
| `DATA_SYNTH_HOLDOUT` | DATA | ON (built at SR0; a pending fleet that pairs with pre-change runs, the retok fleet, pins 0 if it runs after; the WORLD re-run keeps it ON) | ON | 04-Q5 |
| `DATA_DRAW` | DATA | 'planned' (D8); 'replay' recommended once SR0 builds it (**[OWNER] O16**) | 'replay' | 04-Q1 |
| `DATA_REPLAY_SHARE` | DATA | 0.27 (read under 'replay') | 0.27 | 04 (toy); arms 0.15 / 0.40 |
| `DATA_RESERVOIR_BYTES` | DATA | 0 | The area's held-out block size in bytes, written as a number by the preset builder | NEW-06; interim |
| `DATA_SRC_CAP` | DATA | 0 (OFF) | **[OWNER] O18**; recommended about 25 documents' worth of bytes per unpromoted origin per session (provisional) | 04-Q12 |
| `DATA_DRAW_HORIZON` | DATA | 0 (whole epoch) | 0 until an open-ended inbox exists | 04-Q9 |
| `DATA_FOCUS_STAMP` | DATA | 'opt' (redraw-only acts stamp OPT only) | 'opt' | C14 |
| `DATA_REHEARSE_EVEN` / `DATA_FOCUS_FLOOR` | DATA | 0.0 / 0.3 (build defaults) | Per E2 | 04-Q6, 04-Q7 |
| `DATA_TAG` / `DATA_TAG_DROP` / `LM_SRC_AT` | DATA, LM | 'off' / 0.25 / 'input' | Same until E4 | 04-Q13; tags and the drop value **[OWNER] O7** |
| `DATA_TRUST` | DATA | 'observe' (after SR3) | 'observe' | 04-6.3 |
| Trust detection floor | DATA | — | ≥ 1 pass per session and per N bytes of a new origin; **[OWNER] O18**, recommended N = the per-origin cap | C31 |
| `EVAL_RETENTION_EVERY` | EVAL | 1000 plus a reading at each phase start (built at SR0, ON after SR0's bit-identity test), until E6 picks. That alone misses 04-6.2's floor at k3000 (4 readings in a 3,709-window phase), so each pre-registration also writes a cap (the shortest phase's windows / 5, about 700 at k3000 on the 3.78 MB shape) as a number, never computed at run time | 1000 in text sessions at `TOK_RETOK_EVERY` 3000; 333 at k1000 and in media sessions at k3000 (the 2000∪3000 stamp union has 1000-window gaps, `03b_LIVE_CODEC.md:193`); 667 only for media at `TOK_RETOK_EVERY` 0: a third of the shortest stamp interval (**[OWNER] O11**) | 04-6.2, C03 |
| Probe size (windows per area, per half) | EVAL | 6 windows per area (04's current probe) | Sized to ε per NEW-02 (≥ 80% power at ε, ≤ 5% family-wise false rollbacks), from §8 4.1's per-window variance; none until 4.1 reads | NEW-02, O2 (ε owner-set) |
| Probe halves | EVAL | Control 50% / report 50% | Same | C11 |
| Plasticity gain probe | EVAL | OFF until §8 4.6 sets N and cadence (N4: no lever without a stated value); then ON as telemetry on the read-only side path | ON; floor 0.8 of the parent reference | NEW-11; provisional |
| Plasticity gain probe: N (windows on the functional copy) and cadence | EVAL | Set by §8 4.6 (none yet; the probe is OFF until then) | Per §8 4.6, with at least one reading per session for the gate (NEW-04) | NEW-11; wall cost priced under C31 |
| Provenance: session and origin ids on MEM entries; a lineage record per checkpoint | MEM, CKPT | ON (telemetry; NEW-08 "Default ON") | ON | NEW-08 |
| Phase-scheduled perturbation values (`TOK_DROPOUT`, `LM_DROPOUT`, `FAB_MUT`, `FAB_BIRTH_JITTER`, tag drop) | TOK, LM, FAB, DATA | Today's values: 0 / 0 / 0.25 / 0.15 / 04-Q13's | Same as the training value until the U-series reads (§8 4.9, 5.7) | NEW-12, C21 |
| Hold expiry as a gate event (preset-only switch) | AUD, Gate | OFF (training runs unchanged) | ON: at hold expiry the session-end gate decides between rollback, the pull-back arm, or acceptance on the owner's word | 03b-16.18, C34 |
| ε (per-area regression per session) | Gate | SOFT (reported) | HARD; recommended 0.05 bits/byte | O2; owner-set |
| Creep budget | Gate | SOFT | HARD; recommended 0.10 bits/byte against the release anchor | O2; owner-set |
| Gate error rates | Gate | — | Family-wise false rollbacks ≤ 5%; power ≥ 80% at ε | NEW-02 |
| Settle / recovery window W | Gate | — | 2 probe readings | NEW-04 |
| Gate alarm thresholds (KL to anchor, negative-flip rate); canary trip | Gate | — | Calibrated on nuisance pairs inside the 5% family-wise rate; stability-gap depth reported only | NEW-04; provisional until §8 4.1 |
| Escalation after rejections | Gate | — | 3 rejections of the same material | C34, NEW-04; provisional |
| `CKPT_DIR` / `CKPT_EVERY` | CKPT | '' / 0 | Required / 1000 (333 at k1000 and in media sessions at k3000, the 2000∪3000 stamp union, `03b_LIVE_CODEC.md:193`; 667 only for media at `TOK_RETOK_EVERY` 0), matching the probe cadence | FRAME (3) |
| `CKPT_BEST_KEEP` | CKPT | 0 | 2 | NEW-04 |
| Anchor retention | CKPT | OFF | ON, 8 sessions | C35; provisional (the NEW-11 chain length); owner may set |
| Quarantine (memory-first) | DATA, MEM | OFF | ON | NEW-07 |
| MEM shares keyed by origin | MEM | OFF (domain-keyed, as today) | ON | C08 |
| Faded-floor total cap / quarantine reserve | MEM | — | 0.5 of the store / 0.1 | C08; provisional (the `MEM_SRC_SHARE` 0.5 precedent) |
| Memory-on served path (`MEM.blend`) | MEM | OFF | OFF until measured | NEW-03 |
| `MEM_MEDIA` | MEM | OFF | OFF | 03-16.8 |
| Faded-area expert cull and merge deferral | FAB | OFF (an E2 arm) | ON until `FAB.contribution` works | C37, 02-R11 |
| Self-replay | DATA | OFF | OFF; cap 0.1 of replay bytes when ON | NEW-16; provisional |
| T0 dynamic evaluation | EVAL | OFF | OFF | NEW-15 |
| Forecast magnitude bound | WORLD | Inert while `WORLD_FEEDBACK` is OFF | — | 10 × ‖h‖ when feedback is ON (provisional: the instability signature) |
| `WORLD_FEEDBACK` / `WORLD_ENABLED` | WORLD | OFF / ON | Same | PENDING-WORLD_FEEDBACK, O13 |
| `lm.ctx` | geometry | EXACT | EXACT | NEW-13 |
| Session mode | — | OFF until built | — | NEW-01 |

---

## Appendix C. Sources

**Proposals and contract.**
- `docs/proposals/01_MODALITIES.md` (M1-M10, lines 151-160); `02_ROUTER_RECURSION.md` (R1-R11, lines
  145-155); `03_AUDIO_VIDEO.md` (§0, §5, §6.1, §8, §9, §11, §13, §14, §16 lines 812-823, Appendix B;
  the planned `DATA.recover` at line 352);
  `03b_LIVE_CODEC.md` (§0b, 0b.1-0b.6, §6.3, §6.4, §12, §13, §16 lines 1375-1396; lines 193, 249-250,
  415);
  `04_SELF_REGULATION.md` (§2, §6, §7 including line 1453, §8 lines 1517-1590, R-7 lines 603-616;
  lines 247, 523-525, 541, 1507).
- `docs/04_CONTRACT.md`: Q-CLOCK-1 (line 1683), Q-CAP-1 (1748; the owner's question 1776-1782),
  Q-DATA-7 (1938), Q-OPT-3 (2324), Q-FAB-5 (2554), the L1 rule as applied (2557; defined at
  `.rework/PLAN.md:155`), Q-OPT-5 (3132), Q-MEM-8 (3174), Q-WORLD-10 (3435; "Open for the owner"
  3545; the fleet's endpoints 3565, 3575-3577), Q-CKPT-2 (3928), the Q-RUN-8 ruling (4219),
  Q-TOK-13 (4399), Q-RUN-16 (4894), Q-OPT-10 (4936).
- `.rework/DECISIONS.md` (D2, D16 at lines 388-390, Q-CAP-2 at line 612); `.rework/ISSUES.md` (P1-C3, P1-C4/C5,
  P1-C11, P1-H15, P1-H52, P1-H55); `notes/AGENT_STATE.md`; `notes/05_ERRORS.md`;
  `notes/06_CONTINUAL_LEARNING.md`; `docs/05_DEFAULTS.md`.

**Code** (lines as cited in the text): `src/opt/api.py` (468-473, 540-561, 642-672, 2864-2874),
`src/opt/levers.py` (474, 605-630, 677-685), `src/ckpt/api.py` (232-233, 648), `src/fabric/api.py` (1699-1701,
3339-3370, 3584, 4290, 4310-4311, 4348-4357, 4619), `src/fabric/levers.py` (686-713, 930-961),
`src/lm/api.py` (908-915), `src/ckpt/levers.py` (256-262), `src/memory/levers.py` (294-297),
`src/memory/api.py` (1967-1979), `src/domains/levers.py` (543-600), `src/data/api.py` (150-152, 734,
1728-1737; 733 at `7e902ba`), `src/capacity/api.py` (1480), `src/eval/levers.py` (146-148),
`src/spine/compose.py` (1634, 1655-1830, 1663-1675, 1808-1818, 2299-2330, 2726-2748, 3238-3300),
`src/spine/loop.py` (448-450, 1248-1254, 2262), `src/tok/levers.py` (280-290), `gpu_world.sh`
(67-79, 144; 346 at `d97779d`).

**Tests.** `tests/test_continuation.py`; `tests/_baseline_fixture.json`.

**Results.**
- `results/multimodal_design_2026-09-25/prototypes/design-world/` (continuous insert, composition).
- `results/live_codec_design_2026-09-25/prototypes/{d1,d2,d3,judge,critic,repro,rev}/` (live codec,
  rates, coordinate rows, probe timing).
- `results/self_regulation_design_2026-09-26/prototypes/{d2,d3,judge,critic,repro,rev}/` (draws,
  tags, trust, selective loss).
- `results/gpu_world_2026-09-24/ANALYSIS.txt` (the WORLD fleet, both endpoints).

**Commits.** 54378b8, c8d8e33, c5768be (S0b); d97779d (2026-09-24, WORLD_FEEDBACK ships False);
7e902ba (2026-09-03); 4feb65f (2026-09-25, the merge-scan repair). `a9d7258` is the one phased
continual-learning run of the old tree, recorded in `notes/05_ERRORS.md` (lines 255, 602-607, 1030),
not a commit of this branch.

**This workflow's scratch evidence.** Archived under `results/decisions_2026-09-26/`; the paths below
and in the text are relative to that folder. The verification rounds and every fix are logged in
`verify/fixlog.md`; the checkers' findings are in `verify_result.json` (rounds 0-2) and the fix log
(rounds 3-4). Two copies of the `d97779d` tree the checkers ran against are left out: check out
`d97779d` to re-run the `d977` comparisons.

| File | What it holds |
|---|---|
| `inv/seedcheck.py` | Distinct synthetic bodies per seed at HEAD (D-A13) |
| `rule_media/cont_test.log` | `tests/test_continuation.py` run: 17 PASS, 0 failing |
| `rule_pending_measurements/splice_time.py`, `measured.json`, `phases.py` | Splice and tokenize timing on a 17 MB tail; phase bounds at 3.78 MB and 20 MB; bytes per window at CPU seed 0 |
| `rule_self_regulation/paired.py` | The paired recomputation of 04's endpoints |
| `rule_tree_and_training/horizon_probe.py` | Continuation LR under the tree's pure functions (floor with a log; 0.5441 → 0.3566 → 0.05 without, under the equal-length-epoch hypothesis that `verify/emp3/k0_epoch_child.py` replaces) |
| `gap/verified_facts.json` | The gap finder's tree facts, with file and line |
| `conflicts/verification_log.json` | Gate arithmetic, the like-for-like tag numbers, the tree facts behind C01-C45 |
| `critic/arith.txt` | Family-wise false-rollback and power arithmetic |
| `lit/verification_log.json` | Which literature claims were verified, and how |
| `verify/emp/phase_cross.py`, `lr.py`, `k1000_1300.log` | Phase crossing at HEAD and `d97779d` (seed 0); continuation LR by length ratio; the first k1000 act on the 20 MB stream (bytes per window, +4.2% whole tail) and `n_live` 2,512-2,564 by windows 1001-1300 |
| `verify/emp2/actsim.py`, `phasepos.py`, `seedvar.py` (`.out`), `lrcont.py`; `verify/numbers/lr_check.py` | Bytes read and phase reached at HEAD's k3000 (model-free act replay) and frozen; per-seed stream hashes at HEAD and `d97779d`; continuation LR for finished and stopped parents; the horizon off-arm with warmup |
| `verify/emp3/k0_epoch_child.py`, `k0child_{756KB,378MB,20MB_s0,20MB_s1}*.out`; `lr_resume.py` (`.out`) | A finished no-log (k0) parent's child, its epoch re-tokenized with the parent's grown vocabulary, priced by the real `OPT.build` / `load_state` / `lr_at`: first step 0.476 / 0.217 / 0.050 / 0.050 of peak at 756 KB / 3.78 MB / 20 MB seeds 0 and 1; the floor for good for revision-log parents |
| `verify/emp3/acts.py`, `acts_tail.py`, `toy_stats.py` (`.out`) | Bytes read and phase-2 windows at HEAD's k3000, seeds 0 and 2; per-act whole-tail bytes/token at the 756 KB k1000 shape; ρ-at-cap counts per toy arm file |
| `verify/numbers3/e2_splice.py` (`.out`) | E2's splice cost by `DATA_FOCUS_ACT_EVERY` (arithmetic) |
| `verify/final/phase_readings_378.py` (`_s{0,1}.out`), `c01_actparent_nolog.py` (`.out`) | Probe readings per phase at HEAD's k3000 on the 3.78 MB shape; an act-parent's re-priced continuation rate with its log suppressed |
| `s0b/preq_eq.py`, `s0b/eq/s{0,1}_k{0,1000}.json` | The CPU equal-bytes S0b runs, seeds 0 and 1 |

**Literature.** As listed and graded in the literature digest (abstract excerpts, official repos or
the tree's docs; everything else marked *unverified*): replay with LR re-warm and re-decay (Ibrahim
2024); WSD and infinite schedules; loss of plasticity (Dohare 2024); sparse memory fine-tuning (Lin
2025: NaturalQuestions F1 loss 11% against 89% full fine-tuning and 71% LoRA); LoRA learns less and
forgets less (Biderman 2024); forgetting as a power law in parameters touched (Kalajdzievski 2024);
Lifelong-MoE; WiSE-FT; the stability gap; fixed-count poisoning (about 250 documents, 600M-13B);
persistent pre-training poisoning (0.1%); model collapse and accumulation (Shumailov 2024,
Gerstgrasser 2024); RL's Razor (2025); BPE-dropout; Geirhos 2018; Fang 2022; NEFTune; single-epoch
Pythia dropout; ADR; Raventos 2023; Kirsch 2022; stochastic depth; ByT5, bGPT, BLT; ZeTT; Gato,
Unified-IO 2, Chameleon, Emu3, Transfusion; MoMa, MoT; ImageBind; Flamingo (*unverified*); BTX,
Expert Gate, MERA, EMT; dynamic evaluation (Krause); test-time training on ARC; Aioli; No Train No
Gain; Rho-1.

