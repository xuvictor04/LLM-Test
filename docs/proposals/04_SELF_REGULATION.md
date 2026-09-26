# Proposal 04 — Self-regulation: the run chooses its focus, weighs its sources, and shows what emerged

**Status: design, judged, reviewed (sound with fixes), reproduced, revised. Not built.** It adds to
the tree and replaces nothing. Every mechanism enters behind a lever. At the shipped defaults the
tree changes in three places, listed in §6 as default behaviour changes:
- the retention probe reads held-out windows as telemetry;
- the source-reliability book runs in observe mode;
- synthetic areas now hold out a block, so every synthetic-source run trains on a different stream.

This revision is binding over the judge's draft, which is preserved as
`prototypes/judge/04_SELF_REGULATION.md`. The review's decisions R-1 to R-10 and its minor fixes are
applied below, each with its reason, and the alternatives are recorded rather than deleted.
`prototypes/rev/checklist.md` maps every critic issue and every "missing" item to the place that
answers it.

**Why it exists.** The owner, 2026-09-26: *"I was thinking, a certain level of self regulation (ie
in how much the llm focuses on what it wants to, for frame rate, but also in general.) a part of my
beliefs are for the system's self regulation for a large part of it. ... Lastly, I was thinking a
degree of 'context awareness' needs to occur, ie awareness of credibility of sources and other
things. I hope much of what I want and more will come out from emergence, which is part of the
questions."*

---

## The honest headline

Read this before anything else in the document.
- **At toy scale the self-regulated draw ties one hand-set number.**
  - A fixed 27% replay of faded areas, spread by deficit scheduling, gets the same mean held-out
    gap as the self-regulated draw, within seed spread.
  - Self-regulated minus replay, mean6 at seeds 0-4: +0.033 / −0.074 / −0.016 / −0.009 / −0.004
    bits/byte.
  - Its one clear win, the newest area (late gap 0.26-0.38 bits/byte better at 5 of 5 seeds), is
    an exposure effect. A hand-set "replay plus a fixed boost to the newest area" reproduces it:
    late gap 1.888 / 1.733 against the self-regulated 1.839 / 1.727, at the critic's 2 seeds.
- **At the owner's shipped schedule, what is regulated in practice is one number.**
  - The generated sliding window has 2 live areas per phase, and pure-add has 1.
  - Under the judge's draft cap (0.5), 2 live areas are forced to 0.5 / 0.5 whatever the run
    measures.
  - So only the rehearsal rate ρ was regulated. On the toy ρ sat at its hand-set cap
    `DATA_REHEARSE_MAX` 0.3 in 26-47 of 48-49 last-phase re-plans.
  - R-1 makes the cap relative, so a 2-area split can move (each area between 0.15 and 0.85 of
    live bytes). Whether the run uses that room is unmeasured. The new gauge
    `data.focus.alloc_freedom` says so on every run.
- **Source tags are the cheapest mechanism with the best evidence.**
  - Wall cost is about 0%. Against today's draw, the tagged read lowers the mean gap by
    0.17-0.40 bits/byte at 5 of 5 seeds.
  - The untagged read, the common case for generation, is +0.04 to +0.09 worse at 4 of 5 seeds.
- **The literature predicts the toy tie may not hold at scale.**
  - Aioli (abstract): no existing online mixer consistently beats stratified sampling, and some
    are up to 6.9 perplexity points worse. Aioli's own estimator beats it by 0.27 on average.
  - No Train No Gain (abstract): selection gains vanish once selection compute is charged against
    a fully decayed learning rate.
  - Either way, the tie can move in either direction.
- **So everything is built behind levers, and the GPU experiment E1 decides.**
  - E1 is pre-registered: all-area end-state bits/byte, 5 paired seeds, a paired test, and compute
    charged to the self-regulated arm (§7).
  - On a statistical tie the self-regulated arm wins, because the owner has stated a standing
    preference for self-regulation. That tie-break is an **owner ruling to confirm** (§8 Q2).

---

**How to read it.**
- It is a build specification, not an essay.
- §0 is the plain-language summary for the owner.
- §1 is the default stack, each item with its reason and alternatives. §1.0 lists what the review
  changed.
- §2 is the measured basis: every claim with per-seed numbers, harness, reproduction verdict and
  evidence path.
- §3 says what is built, what is left to emerge, and the gauges that observe emergence.
- §4 is risks and guards.
- §5 is tree fit: packages, entry points, arguments, levers, counters, checkpoint and resume
  including S0b, and contract accounting.
- §6 lists every default, ON and OFF, with the default behaviour changes flagged.
- §7 is the staged build plan and the GPU experiments.
- §8 is the open questions, each with a recommendation.

**How it was produced and checked.**
- A tree map (seed 0, CPU) and a literature review came first. The review could not open arXiv or
  venue pages (egress refused), so every literature number here is quoted from abstracts.
- A shared testbed was built (by d2). Three designs were prototyped on it independently:
  - **d1**, a learning-progress (LP) bandit over areas, with gradient-consistency source trust;
  - **d2**, a per-token source-tag channel with tag dropout and a model-internal source-agreement
    readout; its lagged-self selective loss was tested and failed;
  - **d3**, retention-paced focus: LP allocation plus forgetting-paced rehearsal driven by an
    online held-out probe, with claim-level truth discovery for credibility.
- A judge scored the three on one common scoreboard. It extended d3 to a third seed, ran the
  d2 + d3 graft, emulated the tree's act constraint, and drafted this proposal (winner d3, with
  d2 and d1 grafts).
- An adversarial critic returned *sound with fixes*: 1 blocking issue, 9 major, 7 minor and a
  10-item "missing" list. It ran its own arms: a hand-set newest-area boost at 2 seeds, and
  model-free truth-discovery stress worlds.
- An independent reproduction tested 12 claims: 10 reproduced and 2 reproduced-weaker. It reran 13
  seed-0 runs, all bit-identical, and 26 runs at new seeds 3 and 4.
- This revision applies the owner-side decisions R-1 to R-10 on the critic's issues (§1.0). It
  also recomputes the goal-B readings the review asked for, from the preserved run JSONs, with no
  new training: `rev/metrics.py`, output `rev/metrics.txt`.

**Evidence** lives under `results/self_regulation_design_2026-09-26/`. Paths below are relative to
its `prototypes/` unless they start with `workflow_result.json`.
- `workflow_result.json`: the whole workflow. Its keys are `map`, `lit`, `designs`, `judge`,
  `critic` and `repro`. The literature review lives only here, under `lit`.
- `map/`: the tree map's probe scripts and seed-0 readings.
- `testbed/`: `testbed.py` and `CHANGELOG.txt` (the PYTHONHASHSEED determinism fix).
- `d1/`, `d2/`, `d3/`: each design's `run.py`, analysis, `out/*.json` and `logs/`.
- `judge/`:
  - `score.py` and `compare.py`, with outputs `scoreboard.{json,txt}` and `compare.txt`;
  - `w/d3/run_tags.py` (the graft) and `w/d3/run_act.py` (the act emulation);
  - `w/*/out/` (the reruns);
  - `04_SELF_REGULATION.md`, the superseded draft.
- `critic/`:
  - `w/d3/run.py` (d3 plus the `replay_late` arm) and `w/d3/out/`;
  - `td_stress.py` (model-free claim truth discovery under stress) and its outputs
    `out/td_*.json`;
  - `q_td.sh`, the exact commands.
- `repro/`: copied code, `out/` at seeds 0, 3 and 4, and `newseeds.py`, `ns.txt` and `cmp.py`.
- `rev/`: this revision's `metrics.py`, `metrics.txt` and `checklist.md`.

**Every number is a CPU prototype reading at toy scale.**
- The model is a 1-layer GRU of width 128.
- The corpus is 16-letter synthetic bytes in 7 areas, 4,000,000 bytes, 1953 optimizer steps of
  16 × 128-byte windows. The tree runs 1 window per step.
- The draw is online, so no act is needed.
- The toy has no tokenizer, no FAB, no MEM and no DOM.
- It is a signal, not a result. The GPU experiments in §7 decide the defaults.

**Words used below.**
- *Area*: a DATA area (a source directory or a synthetic generator). *Live*: in the current phase's
  schedule. *Faded*: live in an earlier phase of this run, not now.
- *Phases*: the testbed has P0-P3 of equal bytes. P0-P2 have six live areas (hard, easy, noise,
  cred, false, corrob). In P3, late arrives while hard and easy fade.
- *Planned*: today's `DATA_DRAW='planned'`, an even split of each phase's bytes across its live
  areas (stratified sampling). *m27*: fixed replay at 27% of P3 to the faded areas, deficit-spread.
- *Gap*: held-out bits/byte minus the generator's optimum ("oracle") on the same bytes, read with
  no tag. *mean6*: the mean end-state gap over the six learnable areas (hard, easy, cred, false,
  corrob, late). *mean5* drops the liar (false).
- **Goal-B primary readings (R-2):**
  - the per-area **end-state gap**;
  - the **time-integrated gap**: the mean over the 8 evaluation points (fraction 0.125 to 1.0 of
    the run) of an area's gap, counted from its first live point (late: 0.875 and 1.0);
  - the **fade-period gap**: the mean over P3's two points.
  The time-integrated and fade-period gaps are computed post hoc by `rev/metrics.py` from each
  run's `curve`.
- **Secondary, level-relative:** *forget_X* is X's end gap minus its gap at the end of P2, just
  before X fades. Its reference point is that P2-end level. A draw that lowers the P2-end level
  (by promoting X in P2) raises forget_X without making the end state worse (§2 row 7).
- *Qc*: the 24 contested facts that only the credible source and the liar state. *Qa*: the 24
  agreed facts. *Qc share*: p(true) / (p(true) + p(lie)). Each class is 24 items, so accuracy moves
  in steps of 0.042.
- *Act*: S0b's post-flush, empty-batch re-segmentation of the unconsumed tail, built at HEAD
  (commits 54378b8, c8d8e33, c5768be):
  - `TOK.splice`, `RunClock.revise_epoch_length`, `OPT.revise_horizon`;
  - stage X in `spine/loop.py`;
  - the per-epoch `seg_log`, replayed on resume (Q-RUN-16);
  - MEM's re-cut at a moved view (Q-MEM-13).

---

## 0. In plain words, for the owner

**What the tree does today.**
- It regulates its own *structure*: FAB halting depth, grown and culled experts, DOM's discovered
  domains, TOK's minted vocabulary.
- It does not regulate its *focus*:
  - which bytes it reads, in what proportion, and whether it ever revisits an old area are all
    fixed before the first window;
  - once an area leaves the schedule it is never seen again;
  - nothing at runtime measures what is being forgotten. `EVAL.holdout_probe` is a stub, and the
    synthetic source holds nothing out.

**What this adds, and what in it is self-regulated.**
- A **retention probe** (default ON, telemetry). The run reads a small, fixed set of held-out
  windows per area and records bits/byte per area. This is the runtime forgetting signal the tree
  lacks.
- A **self-regulated draw**, `DATA_DRAW='retention'` (built OFF). From the probe readings the run
  decides:
  - how to split each phase's bytes among the areas that are live (more to areas it is still
    improving on, less to mastered or unlearnable ones);
  - which faded areas to bring back, and in what proportion, from how much each one's probe loss
    has risen. The timing is in effect built: on the toy the first rehearsal came at the first
    probe after every fade;
  - how much to rehearse, up to a hand-set ceiling.
- A **fixed-rehearsal draw**, `DATA_DRAW='replay'` (built OFF). It is the hand-set control. It is
  laid at startup and needs no runtime machinery.
- A **source-reliability book**, `DATA_TRUST='observe'` (default ON, observe only). DATA finds
  claims that different sources state differently and scores each source by agreement, never by
  fluency. In observe mode it changes nothing.
- A **source channel**, `DATA_TAG` (built OFF). Each token carries its source's id, and a quarter of
  segments go untagged. The model learns who says what.

**What is not self-regulated, and why.**
- *Which areas exist and when each is available* (the phase schedule). That is the experiment: the
  owner decides what the world offers when. It includes `DATA_PHASE_LIVE`, which sets how many
  areas are live at once. Its value 3 is an owner question (§8 Q3).
- *The total byte budget.* That is compute.
- *The held-out and probe sets.* A probe that moved with the focus would measure its own choices.
- *The guards*: the floor per live area, the relative cap, the rehearsal ceiling `DATA_REHEARSE_MAX`
  and the trust floor. They bound the controller's mistakes. At the shipped schedule the rehearsal
  ceiling is effectively the rehearsal amount (next point).
- **At the shipped schedule, only ρ is regulated in practice.**
  - The generated sliding window has 2 live areas, and ρ is the rehearsal rate.
  - On the toy ρ sat at its ceiling most of the time.
  - Under R-1's relative cap the 2-area split has room to move, but that is unmeasured, and
    `data.focus.alloc_freedom` reports it.
  - Pure-add has 1 live area and, unless the parent's areas are admitted for rehearsal (§8 Q4),
    nothing faded. There 'retention' trains exactly as 'planned' (the plan never moves, so no act
    is taken), but it still pays the probe.

**What emerges and what is built.**
- *Built:* the probe, the rule that turns readings into shares, the floors and caps, when
  rehearsal starts (at the first probe after an area fades, by construction), the rehearsal
  ceiling, the reliability ranking of sources (an explicit truth-discovery algorithm), and the
  source channel.
- *Emerged on the toy:*
  - the schedule, in the known-answer sense: noise demoted (in P1 and P2), the mastered area
    demoted, the hard area promoted, with no area told what it was;
  - given a source tag, the model's per-source conditionals: answering "as the credible source"
    got 0.83-1.00 of contested facts right at 5 seeds.
- *Did not emerge:* trust inside the model without a tag (no credible default), and recognising a
  source from its style.
- *Failed where the toy was stressed:* in P3 the conflicting new area made noise's held-out loss
  drift. The toy rule read the drift as progress, and noise out-drew both credible sources over
  P3 as a whole at 5 of 5 seeds. The whole-run gauge hid it. R-4 changes the rule for live areas to
  count only improvement, and makes the gauges per phase.

**What the measurements say.**
- Against today's draw, the self-regulated draw lowered the mean held-out gap by 0.19-0.34
  bits/byte at 5 of 5 seeds. So did 27% fixed replay (0.18-0.32).
- Catastrophic forgetting of the easy area fell from 0.9-1.9 bits to under 0.05 under either.
- Against replay, it is a tie on the mean, as the headline says. By area:
  - it is better on the newest area (5 of 5), which a hand-set boost reproduces;
  - on the hard old area it is as good or better at 4 of 5 seeds on the end state;
  - it is worse on the easy old area at 4 of 5 seeds;
  - it is worse on noise calibration and on the two credible sources at 5 of 5 seeds.
  The judge's "fixed replay protects hard 4-7x better" was an artefact of measuring forgetting from
  a level the self-regulated draw had already lowered (R-2, §2 row 7).
- Credibility by agreement moved contested facts from a 0.45-0.87 true share to 0.68-0.96 at 5 of 5
  seeds. It is defeated by a lying majority (3 of 3 seeds tested, weaker at the new seeds). It is also
  defeated by a truthful source that writes its facts in another format, because the prototype
  measures agreement with the majority's surface form. So it stays observe-only, and the build
  target is a format-normalised claim (R-5).

**Defaults, in one line each.**

| Mechanism | Default | Why |
|---|---|---|
| `DATA_DRAW` | 'planned' (unchanged); 'replay' and 'retention' built OFF | E1 decides; a tie goes to 'retention' (owner ruling to confirm) |
| Retention probe | ON, telemetry | the runtime forgetting signal; proven bit-neutral to training at SR0 before it ships ON |
| Synthetic held-out block | ON: **a default behaviour change** | evaluation needs held-out data; it withholds bytes from training |
| Reliability book | ON, observe | measures on the owner's corpus; actuation OFF, and may never default on while a truthful different-format source is floored |
| Source tag | OFF | E4 decides; recommendation ON if the untagged cost is within noise at owner scale |
| Selective loss, MIR, gradient trust | OFF, ablations | measured negative, inert or weak |
| Frame rate | 03b's 'measured' stays | 'progress' is an OFF arm at 03b S3, with no measurement here |

---

## 1. Decisions — the default stack

### 1.0 What the review changed

Each row is a decision already taken on a critic issue, with its reason. The alternative is kept
as a lever value or a recorded option.

| # | Critic issue | Decision applied | Reason | Alternative kept | Where |
|---|---|---|---|---|---|
| R-1 (blocking) | At 2 live areas the 0.5 cap forces 0.5 / 0.5, so only ρ is regulated | Relative cap `cap_a = min(DATA_FOCUS_CAP_MULT / n_live, 1 − Σ_{b≠a} floor_b)`; gauge `data.focus.alloc_freedom` (ABSENT at n_live ≤ 1); a 'focusbed' owner-shape arm and an E1 arm at `DATA_PHASE_LIVE` ≥ 3; the plain statement that only ρ is regulated at the shipped schedule | A cap should bind only when one area would take more than a multiple of its even share. An absolute cap at 2 live areas is a hand schedule | Absolute cap applied only at n_live ≥ 3 | §0, §1 item 1, §3, §6, §7 E1, §8 Q3 |
| R-2 | "Replay protects hard 4-7x better" is level-relative | Goal-B primary readings are per-area end-state gaps and a time-integrated gap; forget_X is secondary with its reference point stated; the dissent, E1's rule and the rehearsal-floor question are rewritten on end states; `DATA_REHEARSE_MIN` is dropped | On the end state the self-regulated draw is as good or better on hard at 3 of 3 original seeds (−0.008 / −0.293 / −0.145) | forget_X, reported as secondary | Words, headline, §2 rows 5-7, §7 E1, §8 Q6 |
| R-3 (and R-9) | The newest-area advantage is exposure; E1 ignores compute | E1 adds a hand-set "replay + newest boost" arm (`DATA_REPLAY_NEWEST` 0.34 of phase bytes, the critic's control) and a compute-matched replay arm; per-phase byte shares beside every per-area gap; pre-registered on all-area end-state bits/byte, 5 seeds and a paired test, compute charged; a tie goes to the self-regulated arm, **an owner ruling to confirm** | A one-number hand schedule reproduced the newest-area gain (critic, 2 seeds). Performance decides, so the probe's compute is charged | The judge's rule (within 1 paired SD plus a newest-area tie-break), recorded as superseded | §2 rows 8-9, §7 E1, §8 Q1-Q2 |
| R-4 | Absolute LP re-attracts noise under interference in P3 | Live areas use signed improvement on the held-out probe (decrease only); absolute or negative slope is used only for faded areas' need; gauges per phase; a known-answer test for the P3 interference case | A rising loss on a live area is not learning progress. The whole-run gauge hid a whole-phase failure | `DATA_FOCUS_LP='abs'` (the toy rule) and `'net'` (LP net of a drift estimate) | §1 item 1, §3, §4, §7 SR2 |
| R-5 | Claim truth discovery measures conformity to the majority's surface form | `DATA_TRUST` stays 'observe'; the build target is aligned (key, value) claims with a normalised key (`DATA_TRUST_CLAIM='kv'`); the byte-context rule is the prototype (`'ctx'`) and is declared to measure surface conformity; format-variant, impersonation, stale-truth and mixed-reliability worlds join 'focusbed' and E5; the K sweep and the Qa cost are reported; 'loss+draw' may never default on while a truthful different-format source is floored; copy detection comes before any actuation; `DATA_TRUST_CTX` is in TOK units | The critic's stress runs floored a truthful different-format source at 2 of 2 seeds, and K=5 equals the record prefix length | 'ctx', and the rules 'peer', 'residual' and 'fluency' | §1 item 8, §2 rows 15-17, §6, §7 E3/E5, §8 Q8/Q12 |
| R-6 | The resume order in the draft is not bit-exact | A redraw is an event kind INSIDE S0b's `seg_log` (at_byte, shares, rng child), replayed strictly in act order, with the stream rebuilt at each redraw | Each splice was cut on the bytes as they stood at its act | None: the draft's order was wrong | §1 item 4, §5, §7 SR1 |
| R-7 | Retok acts move the probe's tokenization and read as progress or forgetting | The books rebase at every act that moved the view (drop the interval spanning it, reset best, Lf and Ls to the first post-act reading), counted as `data.focus.rebased`; the probe's step per act is measured at SR2 on real text | The unit is bits/byte, but the model's ids for the same bytes change | A fixed-view probe, cut at a recorded view with `TOK.tokenize(view=)` | §1 item 6, §4, §7 SR2 |
| R-8 | "Telemetry only" is untested, and the synthetic holdout is not free | SR0 test: probe ON against OFF gives bit-identical training losses and state. `DATA_SYNTH_HOLDOUT` has a resume rule admitting 0 → n held-out bytes under a named counter; recommended ON and listed as a DEFAULT BEHAVIOUR CHANGE | Evaluation needs held-out data, and withholding changes every synthetic-source stream | Ship `DATA_SYNTH_HOLDOUT` OFF | §1 items 6-7, §6, §7 SR0 |
| R-10 | 'replay' is wrongly behind the act | `DATA_DRAW='replay'` is built at SR0 inside `data_plan` / `draw_stream` from the phase schedule, with exact startup exposure gates, no redraw log and no act. Only 'retention' sits behind the act-dependent stage | Faded sets are known at startup | None | §1 item 2, §5, §7 SR0 |
| Minors | 7 minor issues | All adopted; one partly (below) | — | — | §1.0 minors |

**Minor fixes, all adopted, one partly:**
- **m1. ReplayFixed iterated a Python set, so it was not deterministic across processes.**
  - The critic's rerun of m27 s1 under another hash seed gave mean6 1.4002 against 1.4000.
  - Every policy iterates areas in AREAS or name order. The tree's 'replay' breaks deficit ties by
    `Plan` order (§1 item 2).
  - The effect is under 0.004 bits/byte, so no conclusion moves. The critic's `replay_late` arm
    carries the same order effect.
- **m2. Rehearsal onset and amount were listed as emergent.**
  - Adopted: both move to "built". The onset is the first probe after a fade by construction.
  - A gauge `data.focus.rho_at_cap_frac` is added.
  - *Partly:* on the toy the amount was at the ceiling in 26-47 of 48-49 re-plans under
    'focus' and 'fulltd'. In d3's `rehearse` arm, whose live split is even (the closest toy analogue
    of a split with no allocation freedom), ρ averaged 0.197 / 0.193 in P3, and the ceiling bound
    once in 46 / 47 re-plans (`d3/out/rehearse_s{0,1}.json`).
  - So the amount is "built as the ceiling wherever the gauge reads near 1", not unconditionally.
- **m3. Emergence was mislabelled.**
  - The ranking of sources and `credibility.emerged` for tag-TD are built by explicit truth
    discovery.
  - The emergence claim is limited to per-source conditionals given the tag. Trust inside the
    model did not emerge (§3).
- **m4. The graft headline compared a tagged read against a null read.**
  - It now leads like for like: graft tagged against tags-only tagged (§1 item 9, §2 row 20).
- **m5. The tag enters LM.encode's output h, which feeds FAB routing and MEM keys.**
  - E4 adds FAB expert-area purity and MEM hit-area purity, with the tag on and off.
  - The alternative kept: add the tag only at the LM head input, after routing.
- **m6. Tree-fit details (a)-(f).**
  - (a) A redraw-only act branch.
  - (b) `fab.blackout_windows`. OPT's re-warm is inert at `OPT_LR_SHIFT_WARM` 0.
  - (c) `DATA_EXPOSURE_MAX` converted to a byte ceiling.
  - (d) Per-segment cursor snapshots.
  - (e) The probe fills the deferred `EVAL.holdout_probe` instead of adding an entry point.
  - (f) `interference_probe` uses functional parameter copies.
  - All are in §5.
- **m7. The testbed is too easy for the owner's risks.**
  - 'focusbed' gains the owner's schedule shape (sequential fades, 2 live, pure-add), batch 1, a
    tokenizer in the loop, and format-varied fact records (§3, §7 SR0).

Rejected minor fixes: none.

---

**1 — FOCUS: A SELF-REGULATED DRAW, `DATA_DRAW='retention'`, BUILT OFF.**

The d3 controller, revised by R-1, R-4 and R-7.
- *Probe.*
  - `EVAL.holdout_probe` (item 6) reads each seen area's first `EVAL_RETENTION_N` (6) pinned
    held-out windows every `EVAL_RETENTION_EVERY` windows. The retention arms set 160 (§1 item 6).
  - The reading is bits per byte, the only unit comparable across areas and across TOK views.
- *Books per area.*
  - Fast and slow EMAs `Lf`, `Ls` (`DATA_FOCUS_EMA_FAST` 0.3, `_SLOW` 0.05 per probe).
  - A jitter EMA, and the running best.
- *Live areas (R-4).*
  - `LP_a = max(0, Ls − Lf − jitter)`: signed improvement. Only a falling held-out loss counts.
  - An area with fewer than `DATA_FOCUS_WARM` (10) probes gets the best live score. This optimism
    means new material is not avoided.
- *Faded areas.* `need_a = max(0, Lf − best − jitter)`: measured forgetting. Here a rise is the
  signal, which is what "absolute or negative slope only for faded areas" means.
- *Rehearsal fraction.* ρ = min(`DATA_REHEARSE_MAX` 0.3, Σneed / (Σneed + ΣLP)), and ρ = 0 when
  nothing is being lost.
- *Live shares (R-1).*
  - (1 − ρ) · [floor_a + (1 − `DATA_FOCUS_FLOOR`) · LP_a / ΣLP], with floor_a =
    `DATA_FOCUS_FLOOR` / n_live (0.3 split evenly).
  - The bracket, an area's share of live bytes, is capped at `cap_a = min(DATA_FOCUS_CAP_MULT /
    n_live, 1 − Σ_{b≠a} floor_b)` and at the area's exposure byte ceiling (§5). The excess is
    redistributed.
  - With `DATA_FOCUS_CAP_MULT` 3:
    - 6 live areas: cap 0.5 (the toy's measured cap);
    - 5 live: 0.6;
    - 3 live: 0.8;
    - 2 live: 0.85, so each area can move between 0.15 and 0.85.
- *Faded shares.* ρ · [(1 − `DATA_REHEARSE_EVEN`) · need_a / Σneed + `DATA_REHEARSE_EVEN` /
  n_faded] (item 3).
- *Realisation.* Deficit scheduling per segment: bytes since the last re-plan against the plan,
  with ties broken in `Plan` order.
- *Startup prior.* The epoch is laid at startup with the 'planned' shares and no rehearsal. The
  first act in each phase (item 4) replaces it. This matches the toy, where rehearsal began at the
  first probe after a fade.
- *Tree.* The plan is recomputed at every probe. The tail is re-laid only at an act.
- *Rebase (R-7).* At every act that moved the TOK view, the books drop the interval spanning it and
  reset best, Lf and Ls to the first post-act reading (item 6).

*Reason.*
- Against today's draw it wins at 5 of 5 seeds. mean6 (d3 'focus'): −0.284 / −0.338 / −0.264 /
  −0.188 / −0.231. d1's LP bandit: −0.296 / −0.237 / −0.191 / −0.217 / −0.154 (§2 rows 1-2).
- On the goal-B end state it is as good as or better than replay on the hard old area at 4 of 5
  seeds (focus − m27: −0.008 / −0.293 / −0.145 / +0.033 / −0.105). The time-integrated all-area gap is lower than m27's at 5 of 5 seeds (−0.026 to
  −0.105; post hoc, §2 row 6), though the hand-set newest boost gets all of it at s0 and 41% at
  s1 (rl − m27 −0.037 / −0.043 against focus − m27 −0.026 / −0.105).
- It meets the owner's belief. Allocation (where it has room), the split of rehearsal across faded
  areas and the rehearsal amount below its ceiling are the run's.

*Why OFF at build.*
- It ties a matched hand-set replay on the mean (mean6 +0.033 / −0.074 / −0.016 / −0.009 /
  −0.004).
- Its one clear win, the newest area, is reproduced by a hand-set boost (§2 row 8).
- It is worse than replay on the easy old area's end state at 4 of 5 seeds, on noise calibration
  at 5 of 5, and on cred and corrob at 5 of 5 (§2 rows 5, 10, 11).
- Its probe costs compute that replay does not. That is 4.3% of toy wall without MIR, the default
  (`d3/out/focus_nomir_s{0,1}.json`), and 18-19% with MIR.
- At the owner's shipped schedule the allocation had no room under the draft's cap (R-1). Under the
  relative cap the room is unmeasured.
- E1 (§7) decides, under a pre-registered rule.

*Alternatives, all built as values or levers.*
- `'planned'`, today's draw and the build default. It is stratified sampling, a strong baseline
  (Aioli), not a strawman.
- `'replay'` (item 2), with `DATA_REPLAY_NEWEST` for the hand-set newest boost.
- `DATA_FOCUS_LP='abs'`, the toy's absolute LP.
  - Measured: it re-attracts noise under interference in P3 (§2 row 10).
  - It is kept because ALP-GMM and TSCL use absolute LP to catch live-area forgetting. Under
    'signed', a live area whose loss rises draws only its floor.
- `DATA_FOCUS_LP='net'`: LP minus a drift estimate, the median signed slope over live areas at
  the same probe. Unmeasured.
- `DATA_FOCUS_SIGNAL='stream'`: the free in-stream loss instead of the probe. Measured near-null
  (mean6 −0.116 / +0.035 / −0.040 / −0.012 against planned) and blind to forgetting. It is kept as
  the ablation that shows the probe is load-bearing.
- `DATA_FOCUS_RULE='loss'`, loss-seeking: the noisy-TV rule. Measured noise share 0.218 / 0.217
  against 0.175.
- `DATA_FOCUS_RULE='exp3'`, d1's explore mixing in place of the floor. Rejected as the shipped
  regulator, built as a value: d1's LP minus matched replay, mean6 +0.021 / +0.028 / +0.056 /
  −0.039 / +0.073, worse at 4 of 5 seeds.
- `DATA_FOCUS_MIR`: MIR-style predicted interference in the need, built OFF. Measured inert
  (focus_nomir 1.462 / 1.324 against focus 1.467 / 1.326) and costly (a backward pass per probe).
- An absolute cap of 0.5 applied only at n_live ≥ 3 (the critic's other form of the R-1 fix).
  Recorded, not built. At 2 and at 6 live areas it gives the same bounds as the relative cap at 3
  (0.85 and 0.5). It differs at 3-5 live areas (0.5 against 0.8-0.6), where the relative cap
  leaves more room.

**2 — A FIXED-REHEARSAL DRAW, `DATA_DRAW='replay'`, BUILT OFF, LAID AT STARTUP (R-10).**
- *What it does.*
  - Each phase with faded areas gives `DATA_REPLAY_SHARE` (0.27) of its bytes to them, split
    evenly. The live areas share the rest evenly.
  - `DATA_REPLAY_NEWEST` (0.0, off) is the newest-arrived live area's share of the phase's bytes.
    When set, the other live areas split 1 − `DATA_REPLAY_SHARE` − `DATA_REPLAY_NEWEST` evenly.
    This is the critic's `replay_late` control exactly (`critic/w/d3/run.py:159-164`): late 0.34,
    each of the other 4 live areas (1 − 0.27 − 0.34) / 4 = 0.0975.
  - Phases with no faded areas are 'planned'.
- *Where it is built.*
  - `DATA.data_plan` computes the per-phase, per-area budgets from the phase schedule. The faded
    set of every phase is known at startup.
  - `DATA.draw_stream` lays them by deficit scheduling: at each segment, the area with the largest
    (target share × phase bytes so far − realised bytes), ties broken in `Plan` order.
  - The startup exposure Gates stay exact. There is no redraw log and no act.
- *Reason.*
  - It is the control 'retention' must beat, and the literature's goal-B baseline. Ibrahim 2024
    (abstract): replay plus LR re-warm and re-decay matches retraining.
  - Measured against planned (d3 m27): mean6 −0.317 / −0.265 / −0.248 / −0.178 / −0.226.
  - End-state easy gap: 0.532 / 0.583 / 0.499 / 0.499 / 0.502 against planned's
    2.482 / 2.310 / 1.753 / 1.362 / 1.805.
  - 0.27 matches the self-regulated arms' measured last-phase ρ:
    - 'focus' 0.279 / 0.280 / 0.293;
    - 'fulltd' 0.286 / 0.299 / 0.277. The draft attributed these values to 'focus'; the critic
      corrected it.
- *Implementation rule, from the judge's check.* Rehearsal bytes are spread across the phase.
  - d1's uniform pick among budgets front-loads them and loses most of the benefit.
  - Easy forgetting at the same 20%: 0.398 / 0.371 (d1) against 0.050 / 0.030 (d3), seeds 0 / 1.
    At seeds 3 / 4: 0.269 / 0.242 against 0.026 / 0.041 (reproduced-weaker, claim 11).
  - The tree's 'planned' law (uniform among areas with budget left) would front-load the same way
    when faded budgets are smaller than live ones, so 'replay' does not reuse it.
- *Alternatives.*
  - 0.2, measured: hard end gap 1.669 / 1.695 against 1.599 / 1.629 at 0.27.
  - `DATA_REPLAY_NEWEST` 0.34, the E1 boost arm: focus's realised P3 share of late, as the critic
    set it (§2 row 8).
  - A compute-matched variant (E1): the same shares with `DATA_STREAM_BYTES` raised by the retention
    arm's probe compute.

**3 — REHEARSAL INSIDE 'retention': ρ, ITS CEILING, AND HOW IT IS SPLIT (R-2).**
- `DATA_REHEARSE_MAX` 0.3 caps ρ.
  - On the toy it bound in 37 / 28 / 46 / 26 / 42 of 49 / 49 / 48 / 49 / 49 last-phase re-plans
    ('focus').
  - At the shipped schedule this hand-set number is effectively the rehearsal amount. The gauge
    `data.focus.rho_at_cap_frac` reports it per phase.
- `DATA_REHEARSE_EVEN` (0.0, the measured value) is the share of ρ split evenly across faded areas.
  The rest is split by need.
  - *Re-derived rationale.* On the end state, 'focus' left easy worse than m27 at 4 of 5 seeds
    (+0.103 / +0.048 / +0.117 / −0.003 / +0.117).
  - Easy got 0.079-0.119 of P3 under 'focus' against 0.135 under m27 (§2 row 9).
  - Easy's measured forgetting is slow, so its need, and with it its share of ρ, is small.
  - An even floor inside ρ protects a slow-forgetting faded area without raising ρ. It is
    unmeasured; E2 tests 0.5.
- **`DATA_REHEARSE_MIN` (a floor on ρ) is dropped.**
  - Its rationale was the level-relative hard-forgetting gap (0.21-0.27 against 0.04-0.05), which
    R-2 retired: on the end state hard is not worse under 'focus'.
  - Moreover ρ sits at its ceiling most of the time, so a floor on ρ could bind only in the first
    probes after a fade.
  - It is recorded here as the rejected alternative.
- `DATA_REHEARSE_HREC` (10 probes) is the recovery horizon d3 used for need. It is unchanged.

**4 — THE FOCUS ACTS AT THE S0B ACT, RATE-LIMITED; A REDRAW IS A `seg_log` EVENT (R-6).**
- *Why an act is needed.*
  - The tree materialises the epoch up front. S0b's act (stage X, after the flush, batch empty)
    is the only point at which the unconsumed tail can change.
  - Under 'retention', `DATA.note_retention` raises `act_wanted`, as TOK raises a retok. The root
    relays it.
- *When.*
  - At the first probe after each phase entry, and otherwise at most every `DATA_FOCUS_ACT_EVERY`
    (6) probes (960 windows at 160).
  - In both cases **only when the plan differs from the laid tail by total variation (TV) of at
    least `DATA_FOCUS_SHIFT_TV` (0.1)**. A zero-TV act is refused, so a run whose plan never moves
    (pure-add with nothing faded) takes no act and consumes no dropout stream.
  - Withheld requests count as `data.focus.acts_withheld`.
- *The act, in order:*
  1. Append `{"kind": "redraw", "at": k0, "at_byte": byte_pos[k0+1], "shares": {area: share},
     "rng_key": "data.stream.e{E}.a{k}", "view": view_of(vocab)}` to `seg_log`, before the cut.
     The key is `rng_key`, not `rng`: S0b's `rng` field holds the dropout stream's state, which the
     replay passes to `setstate`. The `view` is kept, so the loop's no-op test can still read the
     last event's view.
  2. `DATA.redraw_tail` rebuilds bytes, labels, tags and sources from at_byte. [0, at_byte) stays
     byte-identical.
  3. Append the splice event, and call `TOK.splice(at=k0)` on the rebuilt stream.
  4. `_c_signature_stream`: SIG's signatures come from bytes, so the redrawn tail needs new ones.
  5. `RunClock.revise_epoch_length` and `OPT.revise_horizon` when the length moved.
  6. The shift stamp when TV ≥ `DATA_FOCUS_SHIFT_TV` (item 5).
- *Branches in stage X (minor m6a).* HEAD's branch (`spine/loop.py` ~1198-1250):
  - it refuses an act whose view has not moved only at `TOK_DROPOUT` 0 (`tok.retok_noop`);
  - otherwise it splices, sets `mem_remap` and `resegment`, and stamps a shift;
  - it calls `DOM.on_retokenize` only when the view moved.
  - *Redraw only* (no retok due): a new branch, counted as `loop.acts_redraw`.
    - It performs steps 1-6 at the current view.
    - It sets no `mem_remap` and no MEM `resegment`: the view has not moved, and stored contexts
      come from the unchanged prefix.
    - It does not call `DOM.on_retokenize`.
  - *Redraw with a retok due*: one act. The redraw event, then one splice at the new view, then
    HEAD's retok tail (`mem_remap`, `resegment`, `DOM.on_retokenize` when the view moved). The two
    share one splice.
  - *Retok only*: HEAD's branch, unchanged.
  - *TOK's counters.* `TOK.splice` counts every splice as `tok.retok` and `tok.retok_mid_epoch`
    (`tok/api.py` ~1712-1713), redraws included. TOK is not told why it splices, so the separation
    is the root's counter: retok acts = `tok.retok_mid_epoch` − `loop.acts_redraw`.
- *Resume (R-6).*
  - `compose._replay_segmentation` replays `seg_log` strictly in event order, **dispatching on
    `kind` before any dropout rewind**:
    - `tokenize` and `splice` rewind the dropout stream to their `rng` and cut the stream as it now
      stands, as at HEAD;
    - `redraw` touches no dropout state. It calls `DATA.redraw_tail` with the logged at_byte,
      shares and `rng_key`, and the rebuilt stream replaces the current one.
  - A change to a private helper: `_replay_segmentation(tok, vocab, stream, log) -> seg` becomes
    `_replay_segmentation(tok, vocab, stream, log, *, dat=None, areas=None, plan=None) ->
    (stream, seg)`. Its caller at the 'segment' row keeps the returned stream as
    `System.stream`. A log holding a redraw event with `dat` None is refused.
  - A checkpoint with no redraw events replays exactly as at HEAD.
- *Reason.*
  - The emulated spacing cost nothing on the toy. 'fulltd' applied its plan at 35 acts
    instead of 195 re-plans. The emulation acted every 6 probes unconditionally
    (`judge/w/d3/run_act.py:260-264`), so the TV gate is unmeasured. act6 mean6 1.500 / 1.449 / 1.483 / 1.459 against
    1.536 / 1.452 / 1.495 / 1.485 at every re-plan (seeds 0, 1, 3, 4; reproduced, claim 9).
  - Every act re-segments the whole tail, so fewer acts are cheaper.
  - At the owner's ~20,000 windows that is at most about 21 focus acts plus phase entries (fewer
    where the TV gate withholds), besides TOK's retok acts (`TOK_RETOK_EVERY` 3000, about 6).
- *Alternatives.*
  - An act at every probe (about 125 per run): rejected on cost.
  - A bounded look-ahead draw: DATA materialises only the next K windows. It breaks "whole epoch up
    front" and turns the startup exposure gate into a projection (§8 Q9).
- *Owed.* `TOK.splice` timing on a 17 MB tail (E2; also owed by 03b).

**5 — A PLAN CHANGE AT AN ACT IS A SELF-CAUSED SHIFT; ITS COST IS COUNTED (minor m6b).**
- An act that moves the plan by at least `DATA_FOCUS_SHIFT_TV` stamps `shift_at_windows` and
  `shift_at_steps`, as the roll does. Counter: `data.focus.shift_stamps`.
- *Reason.* CAP's recorded runaway (2048 → 8192 in 19 lifts) was a self-caused loss jump read as a
  stall.
- *What the stamp does at the shipped defaults.*
  - OPT's re-warm is inert: `OPT_LR_SHIFT_WARM` is 0.
  - FAB growth blacks out for `FAB_COOLDOWN` (400) windows per stamp.
  - At about 21 focus acts plus about 6 retok acts in a 20,000-window run, the upper bound is
    27 × 400 = 10,800 blackout windows, 54% of the run.
  - New counter `fab.blackout_windows`, reported by E2. If E2 reads above 20%, the recommendation
    is to stamp redraw-only acts for OPT but not for FAB growth (§8 Q9).
- *Not measured.* The toy has no FAB.

**6 — THE RETENTION PROBE: ON BY DEFAULT AS TELEMETRY, BY FILLING `EVAL.holdout_probe` (minor m6e, R-7, R-8).**
- *What it is.*
  - The deferred `EVAL.holdout_probe(ev, *, units_by_domain, logits_fn, rng)` (`src/eval/api.py:271`)
    is already the retention probe.
  - Its contract pins everything a focus signal needs:
    - byte-coordinate windows, which survive re-segmentation;
    - window starts drawn once per area from `rng_for("eval.holdout.<name>", seed)`, so readings are
      paired across probes and resumes;
    - a per-area key. "Domain" in its docstring is the DATA area: the launcher's `DOMAINS=`.
  - This proposal fills it rather than adding `EVAL.retention_probe`.
- *Signature move:* `holdout_probe(..., n_windows=None, tokenize_fn=None)`.
  - `n_windows` reads the first n of the pinned draw (default `EVAL_HOLDOUT_WINDOWS` 32). The
    cadenced reading uses `EVAL_RETENTION_N` 6, and the run-boundary report reads all 32. A prefix
    of one pinned draw keeps both readings paired.
  - `tokenize_fn` exists because EVAL draws the byte windows and may not import TOK (O10).
- *Producers (M7).* Its deferral reason is that the root has no join producing `units_by_domain`
  and a `logits_fn`. Two root joins are added to `compose.py` (contract §3.0.2) and named in
  `ROW_ARGUMENTS_ELSEWHERE["EVAL.holdout_probe"]`:
  - `units_by_domain`: `Areas.holdout` keyed by area name, passed as bytes;
  - `_holdout_tokenize(sysm)` → `tokenize_fn`: `TOK.tokenize(..., view=TOK.view_of(vocab))` -- the view must be passed explicitly, or the call writes the one-slot `_retok_cache` and counts `tok.segment` (`tok/api.py` ~1521-1540) -- with no labels and `regularize=False`, so it draws nothing from the dropout stream and counts `tok.segment_remap`;
  - `_eval_logits_fn(sysm)` → `logits_fn`: `LM.encode`, then `FAB.forward(training=False)` with no
    `step_windows` advance and the last flush's carried `novelty` and live-domain count
    (`loop_carried`), then the head.
  §3.0.2's sentence that a `logits_fn` is deliberately absent is amended: this is the path the run
  trained, built from the state the last flush carried.
  - TOK counts every unlabelled cut as `tok.segment_remap`. The probe's cuts are counted by the root
    as `eval.holdout.cuts`, so MEM's remap count is `tok.segment_remap − eval.holdout.cuts`.
- *Cadence (M5).* `EVAL_RETENTION_EVERY` defaults to the literal 1000, and 0 turns it off (ABSENT).
  - It is not derived from `DATA_DRAW`. A default that depends on another package's lever is a
    wire (`spine/lever.py:268`), and one cadence does not earn a wire.
  - Instead the root refuses `DATA_DRAW='retention'` with `EVAL_RETENTION_EVERY=0`, because the
    draw would have no signal. It prints a startup notice when the value is above 160, the only
    measured cadence.
  - This is a check over two frozen Configs, not a derived value. The E1 and E2 retention arms set
    160 explicitly.
  - Alternative: declare the wire (20 of 25).
- *Cost (M8).*
  - **At the shipped defaults the cadenced probe does not fire.** `DATA_STREAM_BYTES` 120000 gives
    about 506-937 windows, and `Cadences` seeds at window 1, so the first 1000-window fire would be
    window 1001. A default run reads `eval.holdout.calls` PRESENT-and-0 for the cadence. The only
    added reads are the run-boundary reports: 32 windows per area at each save site and at the end.
  - At the owner's 20,000-window runs: 4 areas × 6 = 24 forward windows per 1000, 2.4% extra
    windows.
  - At 160 windows: 15% extra windows, about 5% of compute if a forward is a third of a step
    (an estimate).
  - Measured on the toy without MIR: 4.3% of wall (`d3/out/focus_nomir_s{0,1}.json`, 4.5 / 104.3 s
    and 4.6 / 106.3 s). With MIR: 18-19%.
- *R-8. It ships ON only after SR0 proves it is telemetry.*
  - Probe ON against OFF must give bit-identical training losses, parameters, optimizer state and
    every counter except `eval.*` and `tok.segment_remap`. The test runs at a cadence that fires
    several probes (for example `EVAL_RETENTION_EVERY` 50 over at least 500 windows), with FAB and
    MEM on at their defaults.
  - The probe runs under `torch.no_grad`, with FAB `forward(training=False)` and no `step_windows`
    advance, MEM reads that write no counter or state the training path reads, and no draw from
    any training rng stream.
  - If it cannot be made bit-neutral, the default flips to 0 (off). This is recorded as the
    alternative.
- *R-7. Rebase at view changes.*
  - Probe windows are fixed bytes cut at the current TOK view, so an act that mints ids moves the
    reading.
  - At every S0b act that moved the view (the act's `_moved`), the focus books:
    - drop the probe interval spanning the act;
    - reset best, Lf and Ls to the first post-act reading. Resetting Ls as well is this
      document's addition, so the slow − fast difference cannot manufacture LP from the step;
    - keep the jitter EMA;
    - count `data.focus.rebased`;
    - record `data.focus.rebase_step[area]`, the first post-act reading minus the last pre-act one.
  - Redraw-only acts do not move the view and do not rebase.
  - The step per act is measured at SR2 on real text. `TOK_GROW_EVERY` 200 mints and
    `TOK_RETOK_EVERY` 3000 acts, so a 20,000-window run rebases about 6 times.
  - *Alternative:* a fixed-view probe, cut with `TOK.tokenize(view=)` at a recorded view. It avoids
    steps but reads text in a spelling the run no longer trains on.
- *Why ON.*
  - The tree has no runtime forgetting signal. The probe gives an online R matrix, and its row is
    ABSENT for an area never seen.
  - It is the yardstick every emergence gauge in §3 reads.
  - It is also the only candidate producer for OPT's restart-damping `best_bpb` (§8 Q10).

**7 — `DATA_SYNTH_HOLDOUT`: ON, A DEFAULT BEHAVIOUR CHANGE (R-8).**
- *What it does.*
  - The synthetic source now holds out a block per area under the real sources' law:
    min(`DATA_HOLDOUT_FRAC` × body, `DATA_VAL_CAP`), a seeded contiguous block from
    `rng_for("data.holdout.<key>", seed)`, removed from the body, not masked.
  - Today `open_areas` sets `n_hold = 0` for synthetic (`src/data/api.py:381`).
  - Synthetic bodies are generated at twice what the sampler needs, so the 5% removal cannot
    breach the area floor.
- ***Default behaviour change.*** It withholds bytes from training. Every synthetic-source run's
  stream changes (the default `DATA_SOURCE` is synthetic), so no pre-change run pairs with a
  post-change one.
- *Resume rule.*
  - `restore_stream_state` refuses a resume whose held-out block moved (`src/data/api.py:1678`).
  - `stream_state` records only offset, size and key per area (`src/data/api.py:1660-1663`), and
    `restore_stream_state` compares offset, then size, then key (`:1739-1747`). A synthetic record
    is `{offset 0, size 0, key None}`, and turning the holdout on moves all three fields.
  - The one admission: when the recorded key is None **and** the recorded size is 0, all three
    fields may move. The restore prints the admission and counts `data.holdout_admitted`.
  - The parent had no held-out number, so no comparison across the run boundary is broken.
  - n → 0, or any other move, is still refused.
- *Reason.* Evaluation needs held-out data. The probe, E1's primary reading and every goal-B number
  on 'focusbed' require it. One holdout law for both sources also means a held-out block is a
  sample of the same generated text, not a separately drawn continuation.
- *Alternatives.*
  - Ship it OFF. The probe is then ABSENT on synthetic runs.
  - The judge's variant: generate held-out text from a separate rng child and leave bodies
    byte-identical, so the stream does not change. Rejected: it makes synthetic and real sources
    two holdout laws, and its block is a continuation drawn after the body, not a sample of it.

**8 — CREDIBILITY: A SOURCE-RELIABILITY BOOK IN OBSERVE MODE, `DATA_TRUST='observe'` (R-5).**
- *Build target: `DATA_TRUST_CLAIM='kv'`, aligned (key, value) claims.*
  - Candidate positions are units from a delimiter class `DATA_TRUST_DELIMS`: the bytes `=` and
    `:`, and the space-bounded copulas ` is `, ` are `, ` was `, ` were `.
  - The key is up to `DATA_TRUST_CTX` (5) TOK units before a candidate, normalised: decoded to
    bytes, case-folded, punctuation and delimiter bytes stripped, whitespace collapsed.
  - The value is the next `DATA_TRUST_VAL` (1) unit(s) after the delimiter, up to the next
    delimiter or punctuation, normalised the same way.
  - So `@EEE=V;` and `@EEE:V;` are one claim with value V. Surface form no longer decides agreement.
  - It is unprototyped. E5's format-variant world is its acceptance test.
- *Prototype: `DATA_TRUST_CLAIM='ctx'`, d3's byte-context rule, kept as an arm.*
  - A claim is a raw K-unit context and its next unit.
  - **It measures conformity with the majority's surface form, not truth.** On the testbed K = 5
    is len('@EEE='), so the known answer was tuned to the record format.
  - `DATA_TRUST_CTX` is in TOK units. After minting, 5 units span more than 5 bytes, so the toy's
    known answer does not port to the tree.
- *Shared machinery.*
  - Claims are admitted if seen at least `DATA_TRUST_MIN_N` (3) times with a top-value share of at
    least `DATA_TRUST_SELF` (0.8). A count sketch pre-filters (hot at `DATA_TRUST_HOT` 20).
  - Only conflicted claims count: at least 2 sources and at least 2 values.
  - Truth is the reliability-weighted vote, and a tie decides nothing.
  - Reliability r_s = (agree + 1) / (n + 2), iterated 10 times.
  - Trust t_s = clip(r_s / max r, `DATA_TRUST_MIN` 0.3, 1), set only with at least
    `DATA_TRUST_MIN_EV` (10) conflicted claims. Below that it is ABSENT and trust stays 1.
- *Observe mode.* It logs r, t, conflicted-claim counts and would-be weights, and changes nothing.
- *Actuation values, built OFF.*
  - `'loss'`: per-token loss weight t, renormalised to mean 1, through
    `LM.lm_loss(token_weights=)`.
  - `'loss+draw'`: also multiplies live LP by t (d3's fulltd).
- ***Standing actuation rules:***
  - (1) Neither value may become a default while E5 shows a truthful source in another format
    floored (`data.trust.format_split_floored` > 0 on 'focusbed').
  - (2) Copy detection (the ACCU-COPY family: sources sharing false values are discounted as
    dependent; Dong, Berti-Equille and Srivastava, VLDB 2009, cited from memory, not from this
    session's review) is built and passes E5's majority-false and impersonation worlds before any
    actuation default is proposed.
- *Reason for the book.*
  - It is the only estimator that moved contested facts consistently. fulltd Qc share
    0.739 / 0.802 / 0.956 / 0.676 / 0.846 against planned 0.450 / 0.536 / 0.870 / 0.485 / 0.535,
    and against the same draw without trust 0.346 / 0.396 / 0.858 / 0.329 / 0.266.
  - It reads no model output and no loss level, so fluency cannot game it. One vote per source per
    claim means volume cannot either.
  - LP focus without it amplified the liar at 4 of 5 seeds: drawn false 0.179 / 0.197 / 0.110 /
    0.216 / 0.221 against cred 0.125 / 0.135 / 0.161 / 0.132 / 0.123 (not at s2).
- *Why observe only.* The critic's model-free stress worlds (`critic/out/td_*.json`, planned draw)
  and d3's majority-false arm (`d3/out/mf_*`, `repro/d3/out/mf_*`):

  | World | Result |
  |---|---|
  | Truthful cred writes `@EEE:V;` (format variant) | cred is floored (r 0.001, t 0.3) and the liar is trusted (r 0.999) at 2 of 2 seeds |
  | Liar switches delimiter | The liar is still floored, but only for its format (1635 conflicted claims at seed 1, all delimiter) |
  | Impersonation: the liar's segments labelled cred | At 30%, the liar is floored (t 0.3) and cred trusted. At 50%, corrob is floored and the liar trusted (r 0.973) (seed 0) |
  | Stale truth: a late source states updated values for 24 W entities | It is down-weighted to t 0.58 (seed 0) |
  | Majority lies (corrob also lies; d3 `mf_*`) | Qc accuracy 0.125 against 0.333 without trust (s0); 0.167 / 0.250 against 0.208 / 0.292 (s3 / s4); trust inverted at step 100 at 3 of 3 seeds |
  | Mixed-reliability area (right on some topics, wrong on others) | **Untested**; added to 'focusbed' |

  - The K sweep (seed 0, base world, `ctx` rule):
    - K = 3 floors the harmless easy area (r 0.016, t 0.3) and only reduces the liar to t 0.612;
    - K = 5 floors the liar (r 0.016 at the end);
    - K = 8 finds 0 conflicted claims through step 500, 1 at step 1000 and 11 at the end, and trust
      never actuates.
  - Costs:
    - fulltd costs agreed facts: Qa 0.917 / 0.875 / 1.000 / 0.792 / 1.000 against planned
      1.000 / 1.000 / 1.000 / 0.833 / 1.000;
    - down-weighting the liar costs its true content (false gap +0.87 / +0.81, s0 / s1);
    - fulltd's mean6 is +0.102 / +0.052 / 0.000 / +0.018 / +0.090 against m27.
  - Qc is 24 items per class, and planned's own Qc accuracy spread across seeds (0.25-0.92) dwarfs
    most per-seed differences. E5 uses 4 × the entities.
  - Observe mode on the owner's corpus is how real-text behaviour gets measured (E3).
- *Alternatives, built as rule values.*
  - `'peer'`: d1's gradient-consistency trust. It ranked the liar lowest, but it moved facts at 2
    of 3 seeds only (full − lp Qc share −0.009 / +0.133 / +0.102), and at post-fix seed 0 it cut Qa
    to 0.625.
  - `'residual'`: d3's model-internal calibration residual. Measured harmful: hard gap +0.327 /
    +0.306 against planned, and it floored hard, noise and the new true source. It is an ablation
    only.
  - `'fluency'`: trust by low loss, the gaming demonstration (d1: false weight 1.187 / 1.177
    against cred 1.118 / 1.073).

**9 — CONTEXT AWARENESS INSIDE THE MODEL: A SOURCE CHANNEL, `DATA_TAG='off'` AT BUILD.**
- *What it is.* Each splice segment carries its source id as a per-token embedding added at the
  LM's input. `DATA_TAG_DROP` (0.25) of segments go untagged. The mask is a pure function of
  (seed, epoch, splice index), drawn from `rng_for("data.tag.e{E}", seed)`, a child of a new
  parent `data.tag` added to `RNG_SUBSYSTEMS` (declared, never drawn, as `data.holdout` is; K8).
  It needs no checkpointed state.
- *Reason: the cheapest mechanism with the best evidence.*
  - Wall cost about 0% (d2).
  - Tagged-read mean6 1.352 / 1.337 / 1.425 / 1.481 / 1.286 against planned
    1.751 / 1.665 / 1.621 / 1.655 / 1.621.
  - Noise gap under its tag 0.030 / 0.033 / 0.011.
  - Easy forgetting read under its tag +0.31 / +0.29 / +0.28, against planned's +1.87 / +1.65 /
    +1.23. The tags arm's own untagged read is 1.585 / 1.656 / 1.317 (`d2/out/tags_s*.json`).
  - The model's own tag-conditioned truth discovery trusts the credible source at 5 of 5 seeds.
  - Trusted-tag Qc accuracy 0.958 / 0.917 / 1.000 / 0.833 / 0.833.
- *It composes with item 1 (judge's graft; like-for-like first, minor m4).*
  - Graft tagged mean5 against tags-only tagged: −0.081 / −0.165 / −0.143 / −0.183 / −0.062.
  - The controller rehearsed less: last-phase ρ 0.181 / 0.236 / 0.236 / 0.206 / 0.225 against
    fulltd's 0.286 / 0.299 / 0.277 / 0.286 / 0.292.
  - Under the tag, noise did not out-draw a credible source in P3 at 2 of 3 seeds (§2 row 10).
  - Against fulltd's null read, graft tagged mean5 was 1.335 / 1.197 / 1.209 / 1.292 / 1.270
    against 1.422 / 1.319 / 1.285 / 1.385 / 1.337.
- *Why OFF at build.* Untagged generation, the common case for goal A, is neutral to worse:
  - tags alone against planned: −0.015 / +0.092 / +0.049 / +0.092 / +0.037;
  - graft against fulltd: +0.086 / +0.048 / +0.117 / +0.044 / +0.092;
  - the graft also lowers Qa (0.792 / 0.917 / 0.875 / 0.750 / 0.833).
  E4 decides. The recommendation is to flip it ON if the untagged cost at owner scale is within
  noise, because the tagged gains are large and the owner asked for context awareness.
- *Structure risk (minor m5).*
  - The tag enters `LM.encode`'s output h, which feeds FAB routing (`spine/loop.py:1890`) and MEM
    keys, so experts and memory may key on the given label.
  - E4 reports FAB expert-area purity and MEM hit-area purity with the tag on and off.
  - Alternative: add the tag only at the LM head input, after routing.
- *Alternatives.*
  - `DATA_TAG_DROP=0` is rejected: untagged mean6 2.246 / 2.214 / 2.064.
  - `'domain'` uses DOM's domain id: discovered, not given, so it is the more emergent arm.
    Unmeasured. DOM's did→area purity is 0.803 real / 0.82 synthetic (map).
  - A prefix token (MeCo) is rejected: windows are cut mid-segment, so most windows would lack it.

**10 — MODEL-SIDE SELECTIVE LOSS, `LM_SEL='off'`, BUILT AS AN ABLATION.**
- d2's lagged-self token weighting (reference = an EMA of the weights, 0.99 per step).
- Measured negative on every reading:
  - learnable gap worse in 6 of 6 pairs (mean6 1.815 / 1.713 / 1.697, +0.064 / +0.048 / +0.076);
  - noise's gradient weight 1.04-1.11 times its draw share, the opposite of avoidance;
  - +30% wall.
- It is built because the phase is "build everything" and only one reference was tested.
- *Alternative:* Rho-1's frozen or small reference model (literature, not prototyped).

**11 — FRAME RATE: 03b'S MEASURED RULE STAYS; THIS CONTROLLER IS AN ARM THERE.**
- 03b's `AUD_RATE_MODE='measured'` stays the default: the coarsest stride within `AUD_RATE_TOL` of
  stride 1 on recover exact.
- A value `'progress'` (built OFF at 03b S3) lets item 1's controller choose among the strides
  03b's readiness Gate admits:
  - reward: held-out progress per unit of token cost, with signed LP;
  - floor: the coarsest admissible stride;
  - cap: stride 1;
  - optimism at each area's arrival;
  - a shift stamp at every rate change.
- *Evidence:* **none for media**. 03b measured that a fixed stride beat or tied per-segment
  adaptive rates at toy scale. This study found the same shape for rehearsal: a fixed replay ties
  the adaptive draw. It is judged against 'measured' at a matched frame budget.

**12 — NOTHING IN THE OPERATOR'S EXPERIMENT MOVES.**
These stay hand-set, each because it is the experiment or a measurement contract:
- the pool of areas (`DATA_AREAS`);
- availability: the phase schedule, including `DATA_PHASE_LIVE`;
- whether a pure-add child may rehearse the parent's areas (§8 Q4);
- the total byte budget;
- the held-out and probe sets.
Allocation within the guards, which faded areas are rehearsed and in what proportion, the rehearsal
amount below its ceiling, trust (when actuated) and the rate among admissible strides become the
run's. Rehearsal onset is built (minor m2).

---

## 2. The measured basis

**Setup.**
- Everything is on the shared testbed (`testbed/testbed.py`, md5 89ad38c5…), 4,000,000 bytes.
- Seeds are listed in the order s0 / s1 / s2 / s3 / s4.
  - s0-s2 are the designers' and the judge's runs.
  - s3-s4 are the reproduction's new seeds (`repro/*/out/`, run under a different PYTHONHASHSEED).
  - "–" means not run.
- Planned = `d2/out/base_s{0,1,2}.json` and `repro/d2/out/base_s{3,4}.json`. d1's and d3's baseline
  code paths reproduce d2's bit for bit.
- Pairing was checked: the cred oracle is identical per seed across every arm in `rev/metrics.txt`.
- Paired differences are per seed.

**Verdicts.**
- *reproduced (claim N)* and *reproduced-weaker (claim N)* are the reproduction's verdicts.
- *critic* marks a critic measurement that nobody reran.
- *rev* marks a reading recomputed in this revision from the preserved JSONs (`rev/metrics.py`,
  output `rev/metrics.txt`), with no new training.
- *not rerun* means only the designer's or judge's run exists.

**Rounding.** Differences in `rev/metrics.txt` are taken on unrounded values. They can differ in the
last digit from `judge/compare.txt`, which subtracts rounded means. For example, focus − m27 mean6
at s2 is −0.016 here and −0.017 there, and the hard end gap at s0 is −0.008 here and −0.007 in the
critic's text.

**Harness names.**

| Harness | Command |
|---|---|
| d3 | `d3/run.py --arm {focus, fulltd, replay_fixed --replay 0.27 --tag _m27, rehearse, focus_nomir, mf_*, trust_td}` (s2: the judge's copy in `judge/w/d3/`) |
| d1 | `d1/run.py --arm {lp, lp_train, loss, replay, full, trust_fluency}` |
| d2 | `d2/run.py --arm {base, tags, sel}` |
| graft | `judge/w/d3/run_tags.py --arm fulltd --tags 1` |
| act6 | `judge/w/d3/run_act.py --arm fulltd --act_every 6` |
| rl | `critic/w/d3/run.py --arm replay_late` |
| tds | `critic/td_stress.py --scen … --K …` |

| # | Claim | Per-seed numbers | Harness | Verdict | Evidence |
|---|---|---|---|---|---|
| 1 | The self-regulated draw beats today's | focus mean6 1.467 / 1.326 / 1.357 / 1.468 / 1.391 against planned 1.751 / 1.665 / 1.621 / 1.655 / 1.621 (−0.284 / −0.338 / −0.264 / −0.188 / −0.231) | d3 | reproduced (1) | `d3/out/focus_s{0,1}.json`, `judge/w/d3/out/focus_s2.json`, `repro/d3/out/focus_s{3,4}.json` |
| 2 | d1's LP bandit beats today's | lp mean6 1.455 / 1.428 / 1.430 / 1.438 / 1.468 (−0.296 / −0.237 / −0.191 / −0.217 / −0.154) | d1 | reproduced (1) | `d1/out/lp_s*.json`, `repro/d1/out/lp_s{3,4}.json` |
| 3 | Matched fixed replay (27%) beats today's by as much | m27 mean6 1.434 / 1.400 / 1.374 / 1.477 / 1.395 (−0.317 / −0.265 / −0.248 / −0.178 / −0.226) | d3 | reproduced (2) | `d3/out/replay_fixed_m27_s{0,1}.json`, `judge/w/d3/out/replay_fixed_m27_s2.json`, `repro/d3/out/replay_fixed_m27_s{3,4}.json` |
| 4 | **Headline: self-regulated ties replay on the mean** | focus − m27 mean6 +0.033 / −0.074 / −0.016 / −0.009 / −0.004; mean5 +0.021 / −0.061 / −0.035 / +0.005 / +0.023. lp − m27 mean6 +0.021 / +0.028 / +0.056 / −0.039 / +0.073 | rows 1-3 | reproduced (2) | `rev/metrics.txt`, `judge/compare.txt`, `repro/ns.txt` |
| 5 | **Goal-B end state (R-2, primary)** | hard gap: focus 1.592 / 1.336 / 1.338 / 1.663 / 1.450; m27 1.599 / 1.629 / 1.483 / 1.630 / 1.555; planned 2.023 / 2.013 / 1.912 / 1.980 / 1.927; focus − m27 −0.008 / −0.293 / −0.145 / +0.033 / −0.105. easy gap: focus 0.635 / 0.631 / 0.616 / 0.496 / 0.619; m27 0.532 / 0.583 / 0.499 / 0.499 / 0.502; planned 2.482 / 2.310 / 1.753 / 1.362 / 1.805; focus − m27 +0.103 / +0.048 / +0.117 / −0.003 / +0.117 | rows 1, 3 | critic (s0-s2); rev (s3-s4) | `rev/metrics.txt` (gap_end); `workflow_result.json` → critic issue 2 |
| 6 | **Time-integrated gap (R-2, primary; post hoc)** | mean over the 6 learnable areas: focus 1.577 / 1.466 / 1.456 / 1.570 / 1.520; m27 1.603 / 1.570 / 1.506 / 1.607 / 1.575; planned 1.678 / 1.619 / 1.573 / 1.674 / 1.621; rl 1.566 / 1.527 / – / – / –. focus − m27 −0.026 / −0.105 / −0.050 / −0.038 / −0.055; rl − m27 −0.037 / −0.043; focus − rl +0.011 / −0.061. Fade period (P3) hard: focus − m27 +0.009 / −0.278 / −0.140 / +0.047 / −0.102 | rows 1, 3, 8 | rev | `rev/metrics.txt` |
| 7 | Level-relative forgetting (secondary; reference = the end of P2) | forget_hard: focus 0.251 / 0.212 / 0.269 / 0.142 / 0.205; m27 0.051 / 0.054 / 0.036 / 0.019 / 0.037. The reference itself, hard gap at the end of P2: focus 1.341 / 1.124 / 1.069 / 1.521 / 1.245; m27 1.548 / 1.575 / 1.447 / 1.611 / 1.518. forget_easy: planned 1.871 / 1.650 / 1.231 / 0.895 / 1.310; focus 0.010 / −0.001 / 0.046 / −0.027 / 0.041; m27 0.003 / −0.002 / −0.003 / 0.003 / 0.010 | rows 1, 3 | reproduced (3); interpretation corrected (critic issue 2) | `rev/metrics.txt` |
| 8 | **The newest-area gain is exposure; a hand-set boost reproduces it (R-3)** | late gap: focus 1.839 / 1.727 / 1.702 / 1.825 / 1.799; m27 2.221 / 2.090 / 2.061 / 2.114 / 2.060; rl 1.888 / 1.733 / – / – / –. late share of all bytes: focus 0.085 / 0.086 / 0.084 / 0.086 / 0.086; m27 0.037 / 0.037 / 0.036 / 0.036 / 0.037. P3 share: focus 0.340 / 0.344 / 0.334 / 0.345 / 0.343; m27 0.146; rl 0.339 / 0.340. rl mean6 1.441 / 1.395 (rl − m27 +0.008 / −0.005). rl's 0.34 was taken from focus's realised share (post hoc), and rl carries minor m1's set-order effect (about 0.003) | rl | critic, 2 seeds | `critic/w/d3/out/replay_late_s{0,1}.json`, `rev/metrics.txt` |
| 9 | Per-phase byte shares behind the per-area gaps | P2 hard: focus 0.371 / 0.328 / 0.419 / 0.241 / 0.280 against 0.167. P3 hard: focus 0.175 / 0.198 / 0.207 / 0.160 / 0.189 against m27 0.135. P3 easy: focus 0.097 / 0.081 / 0.079 / 0.119 / 0.081 against m27 0.134-0.135. P2 easy (mastered): focus 0.095 / 0.074 / 0.113 / 0.112 / 0.096 against 0.167 | d3 | rev (from `phase_drawn_share`) | `rev/metrics.txt` |
| 10 | Noise: demoted overall, re-attracted in P3 under interference (R-4) | whole-run noise share: focus 0.104 / 0.104 / 0.113 / 0.092 / 0.102 against 0.175. Noise share of each phase's live bytes, divided by the even live share, per phase P0 / P1 / P2 / P3: s0 0.80 / 0.44 / 0.43 / 0.94; s1 0.80 / 0.42 / 0.56 / 0.84; s2 0.85 / 0.44 / 0.69 / 0.86; s3 0.83 / 0.45 / 0.47 / 0.52; s4 0.85 / 0.42 / 0.51 / 0.75. In P3 noise out-draws cred and corrob at 5 of 5 seeds (and false at s0 and s2). P3 LP: noise 0.0009-0.0040 against cred 0-0.0005 (s0 / s1 logs). Graft (tags) P3: 0.46 / 0.44 / 0.56, out-drawing a credible source at s2 only. Noise gap: focus 0.361 / 0.473 / 0.419 / 0.348 / 0.438; m27 0.266 / 0.255 / 0.259 / 0.257 / 0.293; planned 0.189 / 0.286 / 0.184 / 0.155 / 0.223 | d3, graft | critic (P3 logs); rev (per-phase gauge) | `rev/metrics.txt`, `d3/out/focus_s{0,1}.json` (`focus_log_sample`) |
| 11 | Slow-progress valuable areas are under-drawn | cred gap focus − m27 +0.209 / +0.088 / +0.066 / +0.130 / +0.191; corrob +0.183 / +0.212 / +0.149 / +0.155 / +0.174. P3 shares: cred 0.064 / 0.066 / 0.107 / 0.075 / 0.061, corrob 0.065 / 0.061 / 0.072 / 0.070 / 0.075, against m27 0.146 | d3 | rev | `rev/metrics.txt` |
| 12 | ρ mostly sits at its ceiling under focus; not with an even live split | ceiling binds: focus 37 / 28 / 46 / 26 / 42 of 49 / 49 / 48 / 49 / 49 last-phase re-plans; fulltd 36 / 47 / 39 / 38 / 43 of 49 / 49 / 48 / 48 / 49. Last-phase ρ: focus 0.279 / 0.280 / 0.293 / 0.279 / 0.281; fulltd 0.286 / 0.299 / 0.277 / 0.286 / 0.292. d3 `rehearse` (even live split): ρ 0.197 / 0.193, ceiling bound 1 of 46 / 1 of 47; mean6 1.442 / 1.339 (against m27 +0.008 / −0.061) | d3 | critic (s0-s2); rev (s3-s4, rehearse) | counters `focus.rho_cap_binds` and `focus.rehearse_fired`; `d3/out/rehearse_s{0,1}.json` |
| 13 | The held-out probe is load-bearing | lp_train (in-stream loss) mean6 against planned −0.116 / +0.035 / – / −0.040 / −0.012; forget_easy 1.685 / 1.850 / – / 1.131 / 1.228 against planned 1.871 / 1.650 / – / 0.895 / 1.310 | d1 | reproduced (4) | `d1/out/lp_train_s*.json`, `repro/d1/out/lp_train_s{3,4}.json` |
| 14 | Loss-seeking reproduces the noisy TV | noise share 0.218 / 0.217 against 0.175; mean6 −0.004 / +0.020 | d1 | not rerun | `d1/out/loss_s*.json` |
| 15 | Claim truth discovery finds the liar and moves contested facts | fulltd Qc share 0.739 / 0.802 / 0.956 / 0.676 / 0.846 against planned 0.450 / 0.536 / 0.870 / 0.485 / 0.535 and focus 0.346 / 0.396 / 0.858 / 0.329 / 0.266. Step 100: 48 / 45 / 48 / 48 / 47 conflicted claims, r_false 0.02, r_cred 0.98. Qa cost: 0.917 / 0.875 / 1.000 / 0.792 / 1.000 against 1.000 / 1.000 / 1.000 / 0.833 / 1.000 | d3 | reproduced (5); Qa cost critic + rev | `d3/out/fulltd_s*.json`, `judge/w/d3/out/fulltd_s2.json`, `repro/d3/out/fulltd_s{3,4}.json`, `d3/out/trust_td_s0.json` |
| 16 | …but it measures the majority's surface form (R-5) | format variant: cred r 0.001, t 0.3 and liar r 0.999 (s0, s1). K sweep (s0): K=3 floors easy (t 0.3), liar t 0.612; K=5 liar r 0.016; K=8 0 conflicted claims through step 500, 11 at the end, never actuates. Impersonation 30%: liar floored; 50%: corrob floored, liar r 0.973. Stale truth: late t 0.582 | tds (model-free, planned draw) | critic | `critic/out/td_{fmt_cred,base_K3,base_K5,base_K8,imp_K5_i0.3,imp_K5_i0.5,stale_K5}_*.json` |
| 17 | Truth discovery fails when the majority lies | Qc acc with trust against without: 0.125 / 0.167 / 0.250 against 0.333 / 0.208 / 0.292 (s0 / s3 / s4); Wc 0.083 / 0.000 / 0.000 against 0.250 / 0.042 / 0.167; trust inverted at step 100 at 3 of 3 | d3 `mf_*` | reproduced-weaker (6) | `d3/out/mf_*_s0.json`, `repro/d3/out/mf_*_s{3,4}.json` |
| 18 | Gradient-consistency trust is weak | full − lp Qc share −0.009 / +0.133 / +0.102; post-fix s0 Qa 0.625 (d1's pre-fix +0.170 was unpaired) | d1 | reproduced (10) | `judge/w/d1/out/full_judge_s0.json`, `d1/out/full_s{1,2}.json` |
| 19 | Source tags: large tagged gain, small untagged cost | tagged mean6 1.352 / 1.337 / 1.425 / 1.481 / 1.286; untagged − planned −0.015 / +0.092 / +0.049 / +0.092 / +0.037; trusted-tag Qc 0.958 / 0.917 / 1.000 / 0.833 / 0.833; the model's TD trusts cred at 5 of 5 | d2 | reproduced (7) | `d2/out/tags_s*.json`, `repro/d2/out/tags_s{3,4}.json` |
| 20 | Tags compose with focus (like for like first) | graft tagged mean5 − tags-only tagged −0.081 / −0.165 / −0.143 / −0.183 / −0.062; untagged mean6 − fulltd +0.086 / +0.048 / +0.117 / +0.044 / +0.092; last-phase ρ 0.181 / 0.236 / 0.236 / 0.206 / 0.225; Qa 0.792 / 0.917 / 0.875 / 0.750 / 0.833 | graft | reproduced (8) | `judge/w/d3/out/fulltd_tags_s*.json`, `repro/d3/out/fulltd_tags_s{3,4}.json` |
| 21 | Selective loss (lagged self) is negative | mean6 1.815 / 1.713 / 1.697 (+0.064 / +0.048 / +0.076); noise weight/draw 1.04 / 1.06 / 1.11; +30% wall | d2 | not rerun | `d2/out/sel_s*.json` |
| 22 | The tree's act spacing costs nothing here (the TV gate was not emulated: `judge/w/d3/run_act.py:260-264` acts every 6 probes unconditionally) | fulltd at 35 acts (counter `focus.acts`) instead of 195 re-plans: mean6 1.500 / 1.449 / – / 1.483 / 1.459 against 1.536 / 1.452 / – / 1.495 / 1.485; mean5 1.383 / 1.317 / – / 1.354 / 1.323 against 1.422 / 1.319 / – / 1.385 / 1.337 | act6 | reproduced (9) | `judge/w/d3/out/fulltd_act6_s{0,1}.json`, `repro/d3/out/fulltd_act6_s{3,4}.json` |
| 23 | Credibility inside the model did not emerge untagged | style gap ≤ 0.083 in every arm; untagged Qc share moves with the seed at fixed exposure (planned 0.45 / 0.54 / 0.87 at exposure 0.494-0.50) | d1 and d2 gauges | not rerun | `d1/gauges.py`, `d2/exposure.py`, `d2/out/*` |
| 24 | Probe and trust cost on the toy | probe share of wall: focus without MIR 0.043 / 0.043 (s0 / s1); with MIR 0.184 / 0.183 / 0.189 / 0.187 / 0.193. Trust book: 16.7 / 241.1 s, 16.2 / 243.5 s, 7.9 / 124.7 s (fulltd s0-s2, 6.3-6.9%) | d3 | critic (MIR walls); rev (no-MIR) | `d3/out/focus_nomir_s{0,1}.json` (`wall`, `wall_probe`), `d3/out/fulltd_s*.json` (`wall_trust`) |
| 25 | Compute matters at this scale | planned given 15.6% more bytes (d1's probe windows as training): mean6 1.659 / 1.554 against 1.751 / 1.665 (−0.092 / −0.111) | d1 `base_cm` | not rerun (paired, post-fix oracle) | `d1/out/base_cm_s{0,1}.json` |
| 26 | Front-loaded replay is a weak control | forget_easy at 20%: d1 replay 0.398 / 0.371 / – / 0.269 / 0.242 against d3 replay 0.050 / 0.030 / – / 0.026 / 0.041. lp − the spread 20% control mean6: +0.016 / +0.025 / – / −0.042 / +0.066 (a wash) | d1, d3 | reproduced-weaker (11) | `d1/out/replay_s*.json`, `d3/out/replay_fixed_s*.json`, `repro/*/out/replay*_s{3,4}.json` |
| 27 | Determinism | 13 of 13 seed-0 reruns bit-identical under PYTHONHASHSEED 2718; the judge's under 12345 / 999 / 31. **Exception:** d3's ReplayFixed is not bit-identical across hash seeds (m27 s1: mean6 1.4002 against 1.4000) | all | reproduced (12); critic (exception) | `repro/cmp.py`, `judge/w/queue_*.sh`, `critic/w/d3/out/replay_fixed_m27crit_s1.json` |

**Literature**, quoted from abstracts only (`workflow_result.json` → `lit`, every finding
`verified=false`):
- Aioli (2411.05735): no existing mixing method consistently beats stratified sampling, some are
  up to 6.9 perplexity worse; Aioli beats it on 6 of 6 datasets by 0.27 on average.
- No Train No Gain (2307.06440): the gains of batch selection vanish against a fully decayed LR at
  a fixed compute budget.
- Ibrahim (2403.08763): replay plus LR re-warm and re-decay matches retraining (the replay fraction
  was not confirmed).
- MeCo (2501.01956) and PoLM 3.3 (2404.05405): source conditioning helps; hashed ids suffice.
- Truth discovery survey (1505.02463): reliability and truth estimated jointly; extensions handle
  evolving truths.
- Burda (1808.04355): prediction-error curiosity is trapped by a noisy TV. Learning-progress
  monitoring (2509.25438) avoids it.
- Schaeffer (2304.15004): apparent emergence depends on the metric (as cited by the judge).

---

## 3. What is built, what is left to emerge, and how emergence is observed

**Built explicitly (minor m2 and m3 relabel):**
- the retention probe (the filled `EVAL.holdout_probe`) and its rebase at view changes;
- the focus books, the signed-LP rule, the floor, the relative cap, optimism, deficit realisation,
  the act rate limit and the shift stamps;
- **rehearsal onset.** It is the first probe after a fade: need is positive there on every toy seed
  (critic, from the s0 log at step 1480: need easy 0.0033, ρ 0.3 at once);
- **the rehearsal amount wherever ρ sits at `DATA_REHEARSE_MAX`**. `data.focus.rho_at_cap_frac`
  says where;
- the fixed-replay control and its newest boost;
- **the ranking of sources by reliability.** It is computed by an explicit truth-discovery
  iteration (claims 'kv' or 'ctx'), not emergent;
- **`credibility.emerged` under tags.** It is an explicit truth discovery run over the model's
  tag-conditioned answers, so it is built too;
- the source channel and its dropout, and the selective-loss ablation;
- every counter and gauge below.

**Left to emerge, and what the toy says:**
- *Which live area gets bytes when,* within the floor and cap. Nothing is written per phase.
  - Toy (6 live): hard promoted in P2 to 0.24-0.42 of bytes, mastered easy demoted to 0.07-0.11,
    at 5 of 5 seeds.
  - At the owner's 2-live shape it is unmeasured. `data.focus.alloc_freedom` says whether the run
    uses its room.
- *How much to rehearse below the ceiling,* and how to split rehearsal across faded areas.
  - Toy: ρ was below its ceiling in 2-23 of 48-49 re-plans under 'focus', and averaged 0.19-0.20
    with an even live split.
- *Avoidance of unlearnable material and demotion of mastered material.*
  - Toy: noise demoted in P1 and P2 at 5 of 5 seeds.
  - It **failed in P3** under interference at 5 of 5 seeds (R-4; the fix is built, its known-answer
    test is SR2).
- *Inside the model, given a source tag: per-source conditionals.*
  - Emerged: steer gap > 0.05 in 20 of 21 area-seed cells (d2). The model's tag-conditioned
    answers rank the credible source first at 5 of 5 seeds.
- *Inside the model, without a tag:*
  - trust in an untagged "credible default": **did not emerge**. d2's gauge cleared its threshold
    at 3 of 3 seeds, but planned drifted as much at fixed exposure, so it is not reported as
    emergence;
  - recognising a source from its style: **did not emerge** (style gap ≤ 0.083 everywhere).

**Gauges.**
- Each gauge has a pre-set threshold on a continuous metric, since apparent emergence depends on
  the metric.
- Each has three states: ABSENT (no producer, key missing), PRESENT-and-0 (armed, did not fire),
  and a count or value.
- **Per-phase gauges replace whole-run gauges (R-4).**

| Gauge | Fires when | Toy reading (s0 / s1 / s2 / s3 / s4) |
|---|---|---|
| `data.focus.alloc_freedom` | fraction of acts whose live plan differs by TV ≥ 0.01 from the plan the same floor and cap give with every live area at equal LP; ABSENT at n_live ≤ 1 | not logged on the toy. Under the draft cap at 2 live areas it is 0 by construction: LP {1,0}, {0.9,0.1}, {0.01,0.02} and {0.5,0.5} all give 0.5 / 0.5 (critic, d3 `FocusPolicy.replan`) |
| `data.focus.rho_at_cap_frac.P{k}` | ρ at `DATA_REHEARSE_MAX` / re-plans with faded areas, per phase | P3: focus 0.76 / 0.57 / 0.96 / 0.53 / 0.86; fulltd 0.73 / 0.96 / 0.81 / 0.79 / 0.88; rehearse 0.02 / 0.02 |
| `data.focus.noise_demoted.P{k}` | known answer: noise's share of phase k's live bytes ≤ 0.7 × the even live share | P0 0.80-0.85 (no: optimism while warming); P1 0.42-0.45 (yes 5 / 5); P2 0.43-0.69 (yes 5 / 5); P3 0.94 / 0.84 / 0.86 / 0.52 / 0.75 (yes 1 / 5) |
| `data.focus.noise_outdraws.P{k}` | known answer: the learnable live areas noise out-draws in phase k (target 0) | P3: 3 / 2 / 3 / 2 / 2 (focus); 0 / 0 / 2 (graft s0-s2). The P3 interference known-answer test (SR2) requires 0 at 3 of 3 seeds |
| `data.focus.mastered_demoted.P{k}` | known answer: the mastered area's share of phase k < 0.85 × even while its LP ≈ 0 | P2 easy / even: 0.57 / 0.44 / 0.68 / 0.67 / 0.57 (yes 5 / 5) |
| `data.focus.rehearse_onset_windows` | windows from a fade to its first rehearsal byte (built: equals the probe cadence) | 160 on every seed |
| `data.focus.rehearse_fired` | re-plans with faded need > 0; ABSENT under `DATA_FOCUS_SIGNAL='stream'` | 49 / 49 / 48 / 49 / 49 |
| `data.focus.rebased`, `rebase_step[area]` | acts that moved the view / the probe's step at each | toy has no tokenizer: ABSENT; measured at SR2 |
| `data.focus.floor_binds`, `cap_binds` | the guard bound | focus 100 / 76 / 127 / 105 / 112 and 53 / 40 / 56 / 40 / 40 |
| `data.trust.ranked_liar_last` | known answer: r_false < r_cred and r_corrob | fired at step 100 at 5 of 5 ('ctx') |
| `data.trust.conflicted_claims` | count of conflicted claims | 48 / 45 / 48 / 48 / 47 at step 100 (fulltd); ABSENT below `MIN_EV` |
| `data.trust.format_split_floored` | known answer ('focusbed' format-variant world): a truthful source whose facts use another format is floored (target 0) | 'ctx' rule: 1 at 2 of 2 seeds (critic); 'kv' unmeasured |
| `eval.src.steer_gap[area]` | bits/byte under a wrong tag minus under the true tag > 0.05 | 20 of 21 cells (d2); ABSENT at `DATA_TAG='off'` |
| `eval.src_agree.trusted` | built TD over tag-conditioned answers names the credible source | cred 5 / 5 (tags); 3 / 3 (graft) |
| `eval.src.default_trust` | untagged Qc share − untagged exposure share > 0.10 at every seed AND beyond planned's own drift | did not fire: planned drifts +0.37 at s2 at fixed exposure |
| `eval.src.style_gap` | acc(credible-style prefix) − acc(liar-style prefix) > 0.10 | PRESENT-and-0: ≤ 0.083 |
| `fab.expert_area_purity`, `mem.hit_area_purity` (E4, minor m5) | reported with the tag on and off; a rise with the tag on is label-driven structure | ABSENT on the toy (no FAB or MEM) |

**What counts as emergence here.**
- A gauge fires on the known-answer corpus at 3 of 3 seeds, the paired baseline does not fire it,
  and the mechanism that fires it is not an explicit algorithm computing the same quantity.
- Single-seed firings are not reported as emergence.

**Known-answer corpus: `DATA_SYNTH_KIND='focusbed'` (minor m7).**
- It is a port of `testbed.py`'s generators into DATA. The generators vary with the seed, share
  one alphabet, and print their oracle entropies at startup:
  - an order-2 hard area and a quickly mastered easy area;
  - an i.i.d. noise area;
  - a credible source, a more fluent liar and a corroborator, each with fact records;
  - a conflicting late arrival.
- Additions for the owner's risks:
  - **Schedules.**
    - The testbed shape: 6 live, one fade.
    - **The owner shape**: 4 areas on the generated sliding window, 2 live, sequential fades.
    - Pure-add.
    - `DATA_PHASE_LIVE` 3.
  - **Fact worlds.**
    - Base.
    - Majority-false.
    - **Format variant**: a truthful source writes `@EEE:V;`.
    - **Delimiter-switching liar.**
    - **Impersonation**: 30% and 50% of the liar's segments labelled as cred.
    - **Stale truth**: a late source restates 24 values.
    - **Mixed-reliability area**: one source right on W entities, wrong on Q.
    - **Paraphrased records**: the same fact in two surface templates.
    - 4 × the entities, so Qc is 96 items.
- In the tree it runs at batch 1 with the tokenizer in the loop, so the toy's two largest
  deviations are gone.
- Without it, "emergent" allocation cannot be told apart from noise. The owner's real areas (eng,
  py, num, c) have no noise area and no mastered area, so the known-answer gauges can fire only on
  'focusbed'.

---

## 4. Risks and guards

- **A hand schedule in disguise (R-1).**
  - Risk: guards so tight that the plan is whatever the floor and cap force.
  - Guards: the relative cap, and `data.focus.alloc_freedom` on every run. `rho_at_cap_frac` does
    the same for rehearsal.
  - Residual: at the shipped schedule 'retention' may still reduce to ρ at its ceiling, which is
    close to fixed replay at 0.3. E1 measures exactly that.
- **Collapse onto easy or mastered material.**
  - Guard: signed LP is about 0 on mastered material.
  - Measured: easy demoted to 0.07-0.11 of P2, and still protected by rehearsal. Its end gap is
    0.50-0.64 against planned's 1.36-2.48.
- **Avoiding hard-but-learnable material.**
  - Guards: optimism for new areas, the floor (0.3 of live bytes, split evenly), and the relative
    cap.
  - Measured: hard promoted to 0.24-0.42 of P2.
- **Under-drawing slow-progress, valuable areas.**
  - Measured: cred and corrob end gaps are worse than m27 at 5 of 5 seeds (+0.07 to +0.21), and
    their P3 shares are 0.061-0.107 against 0.146.
  - LP measures learnability, not value, and the floor protects recall but not bits/byte (§8 Q7).
- **Noisy TV, including under interference (R-4).**
  - Guards:
    - LP subtracts its jitter;
    - live areas count only improvement (signed), so a loss drifting up under interference
      attracts nothing;
    - rehearsal only draws faded areas;
    - the per-phase gauges `noise_demoted.P{k}` and `noise_outdraws.P{k}`.
  - Measured under the toy's absolute rule: P3 re-attraction at 5 of 5 seeds (§2 row 10). The
    signed rule is unmeasured, and its known-answer test is SR2.
  - Residual: seeing less noise makes the model overconfident on it (noise gap +0.17 to +0.24
    against planned). Under the source tag this largely disappears (tagged noise gap 0.011-0.033).
  - Signed LP has its own cost: a live area whose loss rises draws only its floor. The recorded
    alternative 'net' addresses that.
- **Starving old areas (goal B), read on end states (R-2).**
  - Guards: forgetting-paced rehearsal, `DATA_REHEARSE_MAX`, `DATA_REHEARSE_EVEN`.
  - Measured on end states:
    - hard: as good as or better than m27 at 4 of 5 seeds;
    - easy: worse at 4 of 5 (+0.05 to +0.12), because a slow-forgetting faded area gets a small
      need-weighted share (§1 item 3).
  - Per-phase byte shares are reported beside every per-area gap, so exposure effects are visible.
- **The probe reads the tree's own acts (R-7).**
  - Guard: rebase at every act that moved the view (`data.focus.rebased`).
  - Residual: the rebase drops one interval per retok act, about 6 per run. The step size is
    measured at SR2.
- **The probe perturbs training (R-8).**
  - Guard: the SR0 bit-identity test (probe ON against OFF). The default flips to off if it fails.
- **Resume divergence (R-6).**
  - Guard: the redraw is a `seg_log` event, and replay runs in act order. SR1's test covers a retok
    before and after a redraw, `TOK_DROPOUT` 0.1, and a unit at the cursor whose longest match on
    the redrawn bytes would have crossed at_byte.
- **Feedback between focus and its signal.**
  - Guard: the reward reads a fixed held-out probe, never the windows the controller chose. The
    in-stream variant is measured near-null (§2 row 13).
  - The trust-draw loop (down-weight, under-learn, look worse) is avoided because the claim rules
    read DATA's bytes, not model output. The 'residual' rule showed that loop live (hard gap +0.33 /
    +0.31).
- **Gaming, conformity and collusion (R-5).**
  - Trust never reads the loss level. LP focus alone is gamed at 4 of 5 seeds (§1 item 8).
  - The 'ctx' claim rule rewards the majority's surface form: a truthful different-format source is
    floored, and a 50% impersonation flips trust.
  - Guards: observe by default; the 'kv' normalised claim; the two standing actuation rules (no
    default while a format split is floored; copy detection first); `DATA_TRUST_MIN` 0.3 and "a tie
    decides nothing" bound the damage.
- **Self-caused shift misread as new material, and its cost.**
  - Guard: a shift stamp at every act that moves the plan.
  - Cost: FAB growth blackout, up to 54% of a 20,000-window run in the worst case (§1 item 5).
    It is counted by `fab.blackout_windows` and bounded by E2.
- **The tag becomes the structure (minor m5).**
  - FAB routing and MEM keys may key on the given label. E4 measures expert-area and hit-area
    purity with the tag on and off.
- **Instability.**
  - Guards: EMAs, jitter subtraction, deficit scheduling, the act rate limit and the TV threshold.
  - Measured: no oscillation in the plan logs. ρ is nearly bang-bang under 'focus'; with tags it
    relaxed (ceiling bound 1-4 times).
  - Trust was a step function: floored at step 100, then held.
- **Cost.**
  - The probe is 4.3% of toy wall without MIR (the default) and 18-19% with it. The trust book is
    6.3-6.9%.
  - In the tree at 160 windows and 4 areas, the probe is 15% extra forward windows (an estimate).
  - The claim sketch is 16 MB of int32. The claim table grows with distinct contexts and is bounded
    by `DATA_TRUST_TABLE`.
  - Acts re-segment the tail, with the splice timing owed.
  - The trust book is ON by default, so E3 must show at most 2% wall at owner shape, or
    `DATA_TRUST_EVERY` lengthens.
- **Toy-to-tree gap.**
  - The toy differs from the tree in: batch 16 against 1; a GRU against the tree's arms; no
    tokenizer; 4 MB against about 20 MB; one fade against sequential fades; exact byte records
    against real text.
  - 'focusbed' at batch 1 with a tokenizer removes two of these. Every default decision waits for
    §7's GPU runs.

---

## 5. Tree fit

**Ownership.**
- DATA owns the focus books, the plan, the replay budgets, the redraw, the claim index and trust:
  areas, splices and bytes are DATA's.
- EVAL owns the probe (the filled `holdout_probe`), the interference probe and the agreement
  readout.
- LM owns the loss and the source table. TOK maps the new per-byte channels.
- The root (`spine/loop.py`, composed in `spine/compose.py`) passes numbers, never decisions, and
  keeps no second EMA pair.
- There are no cross-package imports (O10).

**Wires.** 0 new. Every runtime value is an argument, because `Coupling.compute` sees only frozen
Configs. `EVAL_RETENTION_EVERY` is a literal default with a two-Config startup check, not a derived
default (M5). 19 of `WIRE_BUDGET` 25 stay used.

**Entry points: 141 → 152 (+11). One deferred entry point is filled.**
- **Filled, not added:** `EVAL.holdout_probe(ev, *, units_by_domain, logits_fn, rng,
  n_windows=None, tokenize_fn=None) -> Reading{area: bits/byte}`. Its producers are in §1 item 6.
  - Stage A, cadenced on `EVAL_RETENTION_EVERY` (U.Windows), and at the run-boundary report with
    `n_windows=None` (all `EVAL_HOLDOUT_WINDOWS`).
  - `units_by_domain` is keyed by area name and carries `Areas.holdout`.
  - It leaves `DEFERRED_ENTRY_POINTS` (23 → 22).
- New:
  1. `EVAL.interference_probe(ev, *, units_by_area, loss_fn, params_fn, direction)`.
     - Stage A, only when `DATA_FOCUS_MIR`, ABSENT otherwise.
     - It evaluates the virtual step on a functional copy (`torch.func.functional_call` over
       copied tensors), never in-place `sub_` / `add_`, which is not exactly reversible in floating
       point (minor m6f).
  2. `EVAL.source_agreement(ev, *, probes, answer_fn, n_sources) -> Reading{rel, trusted,
     steer_gap, style_gap}`. Stage A on `EVAL_SRC_EVERY`, ABSENT at `DATA_TAG='off'`.
  3. `DATA.note_retention(dat, focus, *, reading, step, view_moved) -> FocusPlan{shares,
     act_wanted}`.
     - Stage A, right after the probe row.
     - `view_moved` is the last act's `_moved`, which drives the R-7 rebase.
  4. `DATA.redraw_tail(dat, areas, plan, stream, *, at_byte, shares, rng_key, seed) -> Stream`. `seed` is RUN.seed, as `draw_stream` takes it: `rng_for(rng_key, seed)` needs it, and neither `Plan` nor `Areas` carries one. The replay helper's new DATA keywords carry it too.
     - Stage X, and compose's replay.
     - It keeps bytes, labels, tags and sources in [0, at_byte) byte-identical.
     - It re-lays the tail within each phase's live and faded sets, with budgets from the shares
       minus the realised bytes.
     - It keeps `len == stream_bytes` (P1-L22).
     - It restores seg_contig cursors from `Stream`'s per-segment cursor snapshots (minor m6d).
       A segment cut at at_byte continues from its snapshot + (at_byte − segment start), and the
       cut counts as `data.redraw_cut_segments`.
  5. `DATA.note_windows(dat, focus, *, labels, nats, token_bytes, step)`.
     - Stage B: the free in-stream per-area books, from the per-window loss (`loop.py` `_flush`)
       and `Segmentation.labels`, which today nothing reads.
     - It is telemetry, plus the 'stream' signal ablation.
  6. `DATA.claims_observe(dat, focus, *, ids, sources, step, decode)`.
     - Stage B, at the consumed cursor.
     - `decode` is a root-composed callable from TOK ids to bytes, for 'kv' key normalisation. It
       is passed as MEM's remap is, because DATA may not import TOK.
  7. `DATA.token_weights(dat, focus, sources) -> (B, L) weights | None`. Stage B. It returns None
     unless `DATA_TRUST` actuates.
  8. `DATA.new_focus(dat, areas, plan) -> Focus`: the producer (K10) of the `focus` record that rows
     3, 5, 6 and 7 take. It is an assembly row after `data_plan`. `Focus` is a new record type
     holding the books, shares and trust state.
  9. `EVAL.retention_period(ev) -> units.Windows`;
  10. `EVAL.src_period(ev) -> units.Windows`;
  11. `DATA.trust_period(dat) -> units.Windows`.
  Items 9-11 are typed period accessors. `Cadences.due` refuses bare ints, and K9 requires every
  value in `compose._periods` to be a typed accessor, as `EVAL.curve_period` and
  `CKPT.save_period` are.

**Signature moves (7):**
- `EVAL.holdout_probe(..., n_windows=None, tokenize_fn=None)`, above.
- `DATA.stream_state(dat, areas, *, focus=None)` and `DATA.restore_stream_state(dat, areas, state,
  *, focus=None)` (`src/data/api.py:1635`, `:1678`). The focus and trust state are checkpointed
  here, so both calls take the record. `restore` fills it in place.
- `LM.lm_loss(lm, logits, y, *, token_weights=None)`: mean-1 normalised (`src/lm/api.py:833`).
- `LM.encode(lm, model, x, *, n_layers=None, extra=None, source_ids=None)`: adds `src(source_ids)`.
  `embed` is unchanged, so WORLD's `obs_emb` does not move.
- `TOK.tokenize(..., channels=None)` and `TOK.splice(..., channels=None)`: map each per-byte channel
  (`tags`, `sources`) through `byte_pos` exactly as `labels` are (`tok/api.py:1724-1725` in splice).

**Unchanged surfaces that gain behaviour.**
- `DATA.data_plan` and `DATA.draw_stream` read `DATA_DRAW` values 'replay' and 'retention'
  (startup prior), `DATA_REPLAY_SHARE` and `DATA_REPLAY_NEWEST`.
- 'replay' is laid by deficit scheduling with ties in `Plan` order. It is not the 'planned' law,
  which would front-load small budgets.
- `open_areas` holds out synthetic blocks under `DATA_SYNTH_HOLDOUT`.
- `restore_stream_state` admits the synthetic 0 → n holdout (§1 item 7).

**New record fields.**
- `Stream.tags` (per byte: 0, or 1 + area index), `Stream.sources` (per byte: a source id finer
  than the area, a file or document; for synthetic, the generator), and `Stream.seg_cursor` (the
  area cursor at each segment start).
- `Segmentation.tags` and `Segmentation.sources`.
- `Areas.sources`: the manifest `open_areas` computes today and drops. `_read_area` records
  document boundaries instead of concatenating blindly.

**Root plumbing (`spine/loop.py`).**
- Per flush, it slices `segmentation.labels`, `.tags` and `.sources` by the flush's token bounds
  and hands them to `note_windows`, `claims_observe`, `token_weights` and `LM.encode`.
- **Stage X** (§1 item 4) keeps three branches: retok only (HEAD, unchanged), redraw only (new), and
  redraw with retok (one splice).
  - A redraw appends a `{"kind": "redraw", ...}` event to `sysm.seg_log["events"]` before the cut,
    beside HEAD's `_c_seg_event(vocab, "splice", at=k0)`.
  - The redraw-only branch calls `_c_signature_stream`, `revise_epoch_length` and `revise_horizon`
    as HEAD's does. It sets no `mem_remap` and no `resegment`, and does not call
    `DOM.on_retokenize`.

**Runtime Gates (under 'retention' only).**
- `data.exposure_max` and `data.exposure_skew` are re-evaluated at every act on realised plus
  planned bytes.
- `DATA_EXPOSURE_MAX` is a repetition multiple (bytes drawn × epochs / bytes on disk), not a share
  (minor m6c). It becomes a per-area byte ceiling, floor(`DATA_EXPOSURE_MAX` × body bytes /
  `RUN_EPOCHS`), which the share cap respects. Counter: `data.focus.exposure_binds`.
- Under 'replay' the startup Gates are exact, because nothing re-lays.

**Checkpoint, resume, geometry.**
- `DATA.stream_state(..., focus=)` writes a `focus` block keyed by area name:
  - `Lf`, `Ls`, best, jitter, n, the last reading;
  - the current shares and the bytes-since-replan snapshot;
  - the probe count at the last act.
- **The redraw log is not in DATA.** It is the `redraw` events in `LOOP.seg_log`, so one log orders
  every act (R-6).
- Trust state: the claim table (bounded by `DATA_TRUST_TABLE`) and the sketch, r and t per source
  name, and first-seen per source.
- The LM `src` table goes in `LM.state_dict`. The `LM_SEL` shadow, only when on, goes in OPT's
  state.
- **Resume**, bit-exact because every quantity is a function of the seed, the stream and the
  logged decisions:
  1. `draw_stream(epoch)`, which already lays 'replay' and the 'retention' prior;
  2. `compose._replay_segmentation` walks `seg_log` in order, rebuilding the stream at each redraw
     event and cutting each tokenize or splice on the stream as it then stands, with the dropout
     stream rewound per event;
  3. MEM's pending remap (Q-MEM-13) is carried in `loop_carried` as at HEAD.
- **Geometry rules.**
  - A new area gets no row (ABSENT), then the optimism prior (the `data.area_added` rule).
  - A vanished area is refused (`data.area_vanished`).
  - A synthetic holdout 0 → n is admitted (`data.holdout_admitted`). Every other holdout move is
    refused.
  - A new source gets trust 1 and ABSENT evidence.
  - LM `src` rows are appended at zero, never recycled. Shrinking `LM_SRC_SLOTS` below the live rows
    is refused.
  - The sketch size is fixed at build and refused if it changes.

**S0b interaction, in full.**
- 'replay', `DATA_TAG`, `DATA_TRUST` (all modes) and the probe need no act. They build at SR0,
  SR3 and SR4.
- 'retention' needs the act (SR1). It builds on what HEAD has:
  - the stage-X act;
  - `TOK.splice` with `view=`;
  - `revise_epoch_length` and `revise_horizon`;
  - the per-epoch `seg_log` replayed on resume (Q-RUN-16);
  - the MEM re-cut at a moved view (Q-MEM-13).
- It adds the redraw event kind and the redraw-only branch.
- The probe interacts with every act that moves the view (R-7), whatever the draw.

**Clock kinds.**
- The probe, trust and agreement cadences are U.Windows, through typed accessors (§5 entry points).
  `DATA_FOCUS_ACT_EVERY`, `DATA_FOCUS_WARM` and `DATA_REHEARSE_HREC` count probes (U.COUNT).
- EMA rates are per probe. The selective-loss EMA is per optimizer step (U.Steps).
- Shares, floors, ρ and `DATA_REPLAY_NEWEST` are U.FRACTION. `DATA_FOCUS_CAP_MULT` is U.RATIO.

**Counters.** ABSENT when unreachable; PRESENT-and-0 when armed and not fired.
- `data.focus.*`:
  - probes, replans, acts, acts_withheld, shift_stamps;
  - lp_active, floor_binds, cap_binds, exposure_binds, optimistic_prior;
  - forgetting_seen, rehearse_fired, rho_cap_binds, rho_at_cap_frac.P{k}, rehearsal_bytes;
  - trust_gated, mir_evals, mir_positive;
  - noise_demoted.P{k}, noise_outdraws.P{k}, mastered_demoted.P{k}, rehearse_onset_windows;
  - alloc_freedom, rebased, rebase_step[area].
- `data.replay.*`: fixed_phases, bytes, newest_boosted.
- `data.redraw_cut_segments`, `data.holdout_admitted`.
- `data.trust.*`: updates, conflicted_claims, claims_kv, claims_ctx, ranked_liar_last,
  format_split_floored, actuations, floor_binds, weighted_batches, evidence_absent,
  table_evictions.
- `data.tag.*`: segments_tagged, segments_dropped.
- `lm.src.*`: tagged_tokens, untagged_tokens, rows_live, refused (must be 0).
- `lm.sel.*`: batches, floor_bound_frac, cap_bound_frac, wshare_over_draw.
- `loop.acts_redraw`, `fab.blackout_windows`.
- `eval.holdout.*`: calls, windows, cuts. `eval.src_agree.*`, `eval.src.*`, `fab.expert_area_purity`,
  `mem.hit_area_purity`.

**Contract accounting.**
- +11 entry points (141 → 152): 7 mechanism entry points, `DATA.new_focus`, and 3 typed period
  accessors. One deferred entry point is filled (`DEFERRED_ENTRY_POINTS` 23 → 22). There are 7
  signature moves, plus a change to the private helper `compose._replay_segmentation`. There are new
  record types `Focus` and `FocusPlan`, and the new `Reading` shape the probe returns.
- The restated count moves at all its places in the same commit (`docs/04_CONTRACT.md` §7's block
  is the count).
- Stage rows:
  - A: `holdout_probe` (cadenced), `note_retention`, `interference_probe` (MIR only),
    `source_agreement`;
  - B: `note_windows`, `claims_observe`, `token_weights`;
  - X: `redraw_tail`.
  - Compose's 'segment' row gains the redraw replay.
- +2 runtime Gates ('retention' only). 0 wires.
- A new `seg_log` event kind, `redraw`, whose child is under `rng_key`. Checkpoints without it
  replay as at HEAD.
- New RNG parent: `data.tag` in `RNG_SUBSYSTEMS` (K8).
- **Levers: +44 (K4: 262 → 306).**
  - DATA: +35, 18 → 53. That is the 34 new DATA levers in §6 plus `DATA_REHEARSE_PARENT`, which is built
    only if §8 Q4 is answered yes.
  - EVAL: +3, 17 → 20 (`EVAL_RETENTION_EVERY`, `_N`, `EVAL_SRC_EVERY`).
  - LM: +5, 12 → 17 (`LM_SRC_SLOTS`, `LM_SEL`, `_EMA`, `_FLOOR`, `_CAP`).
  - OPT: +1, 13 → 14 (`OPT_DAMP_SOURCE`).
  - The K13 headings in `docs/04_CONTRACT.md` ("DATA (18 levers)", "EVAL (17)", "LM (12)",
    "OPT (13)") move with them.
  - Each new lever needs a census amendment row in its package's `levers.py`, a stub naming it in
    `LEVERS READ:` (K4), and a re-render of `docs/05_DEFAULTS.md` (A10).
  - `DATA_SYNTH_KIND` is **new**: today the synthetic source is hard-wired order-2
    (`src/data/api.py:751`). Its default 'order2' names that generator, so it changes nothing.
- New values: `DATA_DRAW` += 'replay', 'retention'; `DATA_SYNTH_KIND` += 'focusbed';
  `AUD_RATE_MODE` += 'progress' (at 03b S3).
- Nothing removed.

---

## 6. Defaults, ON and OFF

**Default behaviour changes: what a run at the shipped defaults does differently after this lands.**
1. **`DATA_SYNTH_HOLDOUT` ON.** Synthetic areas withhold a held-out block from training, so every
   synthetic-source run's stream changes and no pre-change run pairs with a post-change one. A
   resume of an older synthetic checkpoint is admitted (`data.holdout_admitted`).
2. **The retention probe ON** at a 1000-window cadence.
   - On a shipped-default run (`DATA_STREAM_BYTES` 120000, about 506-937 windows) the cadence never
     fires: `eval.holdout.calls` reads PRESENT-and-0 for it. The change there is the run-boundary
     read, 32 windows per area at each save site and at the end.
   - At the owner's 20,000-window runs, it adds 2.4% extra forward windows at 4 areas.
   - Training numbers are unchanged. SR0's bit-identity test proves it, at a cadence that fires
     several probes with FAB and MEM on, before it ships.
3. **The reliability book ON in observe mode.** It adds wall (6-7% on the toy, owed at owner
   shape: E3's ≤ 2% rule). Training numbers are unchanged, proven by SR3's bit-identity test.
Everything else below is OFF, or unchanged unless a lever is set.

**At the shipped schedule** (the generated sliding window, 2 live areas; pure-add, 1):
- if `DATA_DRAW='retention'` is set, what it regulates in practice is ρ;
- on the toy ρ sat at `DATA_REHEARSE_MAX` most of the time;
- the relative cap gives the 2-area split room, whose use `data.focus.alloc_freedom` reports;
- at pure-add with no admitted parent areas, 'retention' trains as 'planned' and pays only the
  probe.

| Lever | Default | Unit | ON/OFF | Meaning |
|---|---|---|---|---|
| `DATA_DRAW` | 'planned' | name | self-regulation **OFF** | + 'replay' (SR0), 'retention' (SR2). E1 decides the flip |
| `DATA_REPLAY_SHARE` | 0.27 | U.FRACTION of a phase's bytes | used under 'replay' | fixed share to faded areas, split evenly, deficit-spread |
| `DATA_REPLAY_NEWEST` | 0.0 | U.FRACTION of a phase's bytes | OFF at 0 | the newest live area's share; the other live areas split the rest evenly. E1's hand-set arm uses 0.34 (the critic's control) |
| `DATA_FOCUS_SIGNAL` | 'probe' | name | — | 'stream' is the measured-null ablation |
| `DATA_FOCUS_RULE` | 'lp' | name | — | 'loss' (noisy TV) and 'exp3' (d1's explore mix) are ablations |
| `DATA_FOCUS_LP` | 'signed' | name | — | R-4. 'abs' (the toy rule) and 'net' (drift-corrected) |
| `DATA_FOCUS_FLOOR` | 0.3 | U.FRACTION of live bytes | — | split evenly across live areas |
| `DATA_FOCUS_CAP_MULT` | 3.0 | U.RATIO × the even live share | — | R-1. cap_a = min(M / n_live, 1 − the others' floors); equals the toy's 0.5 at 6 live areas. Replaces `DATA_FOCUS_CAP` |
| `DATA_FOCUS_WARM` | 10 | probes | — | optimism until an area has this many probes |
| `DATA_FOCUS_EMA_FAST` / `_SLOW` | 0.3 / 0.05 | per probe | — | LP books |
| `DATA_REHEARSE_MAX` | 0.3 | U.FRACTION | — | ceiling on ρ; at the shipped schedule it is effectively the rehearsal amount |
| `DATA_REHEARSE_EVEN` | 0.0 | U.FRACTION of ρ | OFF | even floor across faded areas (§1 item 3). Replaces the dropped `DATA_REHEARSE_MIN` |
| `DATA_REHEARSE_HREC` | 10 | probes | — | forgetting recovery horizon |
| `DATA_FOCUS_MIR` | False | bool | **OFF** | interference estimate (measured inert), functional copies |
| `DATA_FOCUS_ACT_EVERY` | 6 | probes | — | minimum act spacing (960 windows at 160) |
| `DATA_FOCUS_SHIFT_TV` | 0.1 | TV distance | — | plan change that triggers an act and a shift stamp |
| `EVAL_RETENTION_EVERY` | 1000 | U.Windows | **ON** (telemetry): **default behaviour change 2** | literal default, no wire (M5). 'retention' with 0 is refused, and above 160 prints a notice. The retention arms set 160. 0 = off (ABSENT) |
| `EVAL_RETENTION_N` | 6 | windows per area | — | a prefix of the pinned `holdout_probe` draw |
| `EVAL_HOLDOUT_WINDOWS` | 32 | windows per area | unchanged | the full read at the run-boundary report |
| `DATA_SYNTH_HOLDOUT` | True | bool | **ON: default behaviour change 1** | synthetic areas hold out under the real sources' law |
| `DATA_SYNTH_KIND` | 'order2' | name | — | **new lever**: 'order2' names today's hard-wired generator (`src/data/api.py:751`), so it changes nothing. 'focusbed' is the known-answer corpus with its schedules and worlds |
| `DATA_REHEARSE_PARENT` | False | bool | OFF; built only if §8 Q4 says yes | a pure-add child may rehearse the parent's areas as faded from window 0 |
| `DATA_TRUST` | 'observe' | name | **ON as telemetry: default behaviour change 3; actuation OFF** | 'off' / 'observe' / 'loss' / 'loss+draw'. Actuation may never default on while a truthful different-format source is floored, nor before copy detection |
| `DATA_TRUST_RULE` | 'claims' | name | — | 'peer', 'residual' and 'fluency' are ablations |
| `DATA_TRUST_CLAIM` | 'kv' | name | — | R-5. Normalised (key, value) claims, the build target. 'ctx' is the prototype: it measures surface conformity |
| `DATA_TRUST_CTX` | 5 | **TOK units** (not bytes) | — | maximum key length ('kv') or the context length ('ctx') |
| `DATA_TRUST_VAL` | 1 | TOK units | — | value length ('kv') |
| `DATA_TRUST_DELIMS` | '=', ':', ' is ', ' are ', ' was ', ' were ' | byte strings | — | the delimiter class for 'kv' keys (unmeasured) |
| `DATA_TRUST_HOT` / `_SELF` / `_MIN_N` | 20 / 0.8 / 3 | count / share / count | — | claim admission |
| `DATA_TRUST_MIN_EV` | 10 | conflicted claims | — | below this, evidence is ABSENT and trust is 1 |
| `DATA_TRUST_MIN` | 0.3 | loss-weight multiplier | — | trust floor |
| `DATA_TRUST_EVERY` | 160 | U.Windows | — | truth-discovery cadence (testbed: 10 steps × 16); lengthened if E3 measures > 2% wall |
| `DATA_TRUST_SKETCH` | 4194301 | buckets (int32) | — | fixed at build (geometry) |
| `DATA_TRUST_TABLE` | 200000 | contexts | — | LRU bound (unmeasured on real text) |
| `DATA_TAG` | 'off' | name | **OFF** | 'area', 'domain'. E4 decides |
| `DATA_TAG_DROP` | 0.25 | U.FRACTION of segments | — | untagged share (0 rejected) |
| `LM_SRC_SLOTS` | 64 | rows | — | zero-initialised source table |
| `EVAL_SRC_EVERY` | 2000 | U.Windows | active only when `DATA_TAG` ≠ off | agreement readout |
| `LM_SEL` | 'off' | name | **OFF** | 'abs', 'pos', 'loss' (measured negative) |
| `LM_SEL_EMA` / `_FLOOR` / `_CAP` | 0.99 / 0.25 / 4.0 | per U.Steps / U.FRACTION / × mean | — | selective-loss arm |
| `OPT_DAMP_SOURCE` | 'off' | name | **OFF** | 'probe' would feed the mean probe bits/byte to OPT's restart damping (§8 Q10) |
| `AUD_RATE_MODE` | 'measured' (03b) | name | unchanged | + 'progress' at 03b S3, OFF |

**Numbers with no toy measurement behind them.**
- `DATA_FOCUS_CAP_MULT` away from 6 live areas.
- `DATA_REHEARSE_EVEN`, `DATA_FOCUS_LP='signed'`, `DATA_REPLAY_NEWEST` 0.34 away from the toy.
- `DATA_FOCUS_SHIFT_TV`: the act emulation acted every 6 probes unconditionally
  (`judge/w/d3/run_act.py:260-264`), so the TV gate was never exercised.
- The whole 'kv' spec (`DATA_TRUST_CLAIM`, `_VAL`, `_DELIMS`), `DATA_TRUST_EVERY` and
  `DATA_TRUST_TABLE`.
- Each has an owner experiment in §7.

**Unchanged:** everything else in the tree, including the phase schedule, `DATA_PHASE_LIVE` (0,
derived: 2 at 4 areas) and `DATA_EXPOSURE_MAX` (2.0).

---

## 7. Staged build plan, and the GPU experiments that decide the defaults

Stages are named SR0-SR6, to avoid colliding with 03's S-series.

- **SR0 — measurement, and the startup-laid control.**
  - Build:
    - `DATA_SYNTH_HOLDOUT` and its resume rule;
    - `DATA_SYNTH_KIND='focusbed'` with its schedules and worlds (§3);
    - `EVAL.holdout_probe` filled, with its two root joins and `EVAL.retention_period`, at the
      telemetry cadence;
    - the `DATA.note_windows` books;
    - **`DATA_DRAW='replay'` inside `data_plan` / `draw_stream`** (R-10);
    - the per-phase share gauges.
  - Tests:
    - **probe ON against probe OFF gives bit-identical training losses, parameters, optimizer state
      and every counter but `eval.*` and `tok.segment_remap`**. It runs at `EVAL_RETENTION_EVERY` 50
      over at least 500 windows, so several probes fire, with FAB and MEM on (R-8, M8);
    - with `DATA_SYNTH_HOLDOUT=0` and the probe off, the run is bit-exact against HEAD;
    - holdout resume: admit 0 → n with `data.holdout_admitted` 1; refuse n → 0 and any moved block;
    - 'replay' realises each phase's planned shares within one segment, with no front-loading (the
      faded share of each quarter of a phase is within 0.05 of the target);
    - 'replay' is identical across PYTHONHASHSEED values (minor m1);
    - the probe's row for an area that has not arrived is ABSENT.
- **SR1 — the act for DATA.**
  - Build:
    - `DATA.redraw_tail` with cursor snapshots;
    - the redraw event in `seg_log` and event-ordered replay in `compose._replay_segmentation`;
    - the redraw-only and combined stage-X branches;
    - the runtime exposure Gates with the byte ceiling;
    - shift stamps and `fab.blackout_windows`.
  - Known answer: a redraw with the current shares and the same rng child reproduces the tail byte
    for byte.
  - **Resume test (R-6):** saved at n1 and resumed for n2, a run reproduces the uninterrupted
    run's losses exactly, with:
    - a retok act before a redraw and another after it;
    - `TOK_DROPOUT` 0.1;
    - a unit at the cursor whose longest match on the redrawn bytes would have crossed at_byte;
    - a save between a redraw and the next flush.
- **SR2 — 'retention'.**
  - Build: `DATA.new_focus` and the `Focus` record, `stream_state` / `restore_stream_state(focus=)`,
    the books with signed LP, the relative cap, `DATA_REHEARSE_EVEN`, the rebase, the
    zero-TV act refusal, the 'retention' / `EVAL_RETENTION_EVERY=0` startup refusal, and every
    focus gauge.
  - Tests on 'focusbed', each at 3 of 3 seeds:
    - testbed shape: `noise_demoted.P1` and `.P2` and `mastered_demoted.P2` fire;
    - **the P3 interference known answer (R-4): `noise_outdraws.P3` = 0**;
    - owner shape: `alloc_freedom` is reported; a fixed-LP unit test at n_live 2, 3 and 6 checks the
      relative cap (LP {1, 0} at 2 live gives 0.85 / 0.15);
    - **rebase test (R-7):** a forced retok act moves the view; `data.focus.rebased` counts 1;
      `rehearse_fired` does not count the step.
  - **On the owner's real text, measure `rebase_step` per act** and report it.
- **SR3 — sources and trust (observe).**
  - Build:
    - `Stream.sources`, `Areas.sources` and document boundaries;
    - the TOK channels;
    - `DATA.claims_observe` with 'kv' and 'ctx', and `DATA.trust_period`;
    - `DATA.token_weights` and `LM.lm_loss(token_weights=)`.
  - Tests:
    - 'observe' against 'off' is bit-exact on training numbers;
    - on 'focusbed', 'ctx' reproduces the critic's K sweep and format-variant flooring;
    - 'kv' does not floor the format-variant truthful source (`format_split_floored` 0), or the
      result is reported as a failure of the spec.
- **SR4 — the context channel.**
  - Build: `Stream.tags` (the `data.tag` RNG parent), `LM.encode(source_ids=)`,
    `EVAL.source_agreement` with `EVAL.src_period`, and the purity gauges.
  - Test: a zero-initialised table with all tags 0 is bit-exact against off.
- **SR5 — ablations.** `LM_SEL`; `DATA_FOCUS_MIR` with functional copies; the rules 'peer',
  'residual' and 'fluency'; 'exp3'; `DATA_FOCUS_LP` 'abs' and 'net'.
- **SR6 — copy detection** (the ACCU-COPY family), before any trust actuation is proposed as a
  default. Test: E5's majority-false and 50%-impersonation worlds.

**GPU experiments for the owner.**
- Run shape: `RUN_EPOCHS=1`, about a 20 MB stream, about 20,000 windows, `OPT_BATCH_WINDOWS=1`.
- The synthetic corpus varies with `RUN_SEED`. Seeds are paired across arms.
- The judge's packing figure is 12 runs per 140 GiB card.
- **Every rule below is fixed before the runs.**

**E1 — the draw, pre-registered (R-1, R-2, R-3).**
- *Shapes:*
  - (a) 'focusbed' at the owner shape: 4 areas, generated sliding window, 2 live;
  - (b) the owner's real areas at the shipped generated schedule (2 live);
  - (c) the owner's real areas at `DATA_PHASE_LIVE=3`: an arm, not a default change (§8 Q3);
  - (d, optional) 'focusbed' at the testbed shape (6 live), which replicates the toy at the owner's
    run shape.
  Pure-add is not an E1 shape unless §8 Q4 admits parent areas: with 1 live and nothing faded,
  'retention' trains as 'planned' and differs only by the probe's cost.
- *Arms:*
  - `planned`;
  - `replay` (0.27);
  - **`replay_cm`**, compute-matched: `replay` with `DATA_STREAM_BYTES` raised by the retention
    arm's measured probe compute, (`eval.holdout.windows` / 3) × the bytes per window, so the
    probe's FLOPs come back as training bytes;
  - **`replay_newest`**: `replay` with `DATA_REPLAY_NEWEST` 0.34 (the critic's control);
  - `retention` (`EVAL_RETENTION_EVERY` 160).
- *Seeds:* 5 per arm, paired. That is 3 shapes × 5 arms × 5 seeds = 75 runs, plus 25 for (d).
- *Pairing caveat (minor 13).* On synthetic sources the body size scales with `DATA_STREAM_BYTES`
  (`src/data/api.py:730`), and with it the held-out block's position. So `replay_cm` is **unpaired**
  on shapes (a) and (d) and is compared there by Welch's t. On real areas, (b) and (c), bodies and
  held-out blocks do not depend on the stream size, so it stays paired.
- *Primary endpoint:* **all-area end-state held-out bits/byte**, the mean over every area ever live
  of its final `EVAL.holdout_probe` reading with all 32 windows.
- *Test:* the per-seed paired difference, one-sided paired t at α = 0.05 (4 degrees of freedom).
  "A beats B" means significant in A's favour. "Tie" means neither beats the other.
- *Rule:*
  1. If 'retention' beats `planned`, and none of `replay`, `replay_cm` and `replay_newest` beats
     'retention', the default becomes `DATA_DRAW='retention'` **with `EVAL_RETENTION_EVERY` 160** -- the cadence every retention arm ran at; at the literal 1000 the probe-count levers would stretch sixfold (`DATA_FOCUS_WARM` 10 probes = 10,000 windows), a configuration never tested. That is two default changes, listed together. **A tie with a hand-set arm goes to
     'retention', because the owner has a standing preference for self-regulation. This tie-break
     is an owner ruling to confirm (§8 Q2).**
  2. Otherwise, if `replay` or `replay_newest` beats `planned`, the better of them by mean
     primary becomes the default. `replay_cm` is a compute control and is never a default
     candidate.
  3. Otherwise `planned` stays.
  Shape (b) decides. (a) and (c) are reported beside it, and a disagreement between (b) and (c) is
  reported to the owner as a finding about his schedule.
- *Secondaries, reported and not decisive:*
  - per-area end-state gaps, each **beside its per-phase byte shares**;
  - the time-integrated all-area gap;
  - the newest-area gap;
  - the noise calibration gap ('focusbed');
  - `alloc_freedom`, `rho_at_cap_frac`, `noise_outdraws.P{k}`;
  - wall, FLOPs and `fab.blackout_windows`.
- *Superseded rule, recorded:* the judge's "within 1 paired SD of replay AND a better newest-area
  gap". It is biased toward the costly arm, and its tie-break was an exposure effect.

| # | Experiment | Arms | Decides | Rule, fixed in advance |
|---|---|---|---|---|
| E2 | Retention internals and act cost | `DATA_FOCUS_ACT_EVERY` 3 / 6 / 25; `DATA_FOCUS_CAP_MULT` 2 / 3; `DATA_REHEARSE_EVEN` 0 / 0.5; `DATA_FOCUS_FLOOR` 0.3 / 0.5; `DATA_FOCUS_LP` signed / abs; timed `TOK.splice` on the 17 MB tail; `fab.blackout_windows` | these levers' defaults | 3 paired seeds, shapes (a) and (b). Each lever keeps its default unless the alternative beats it on E1's primary endpoint (one-sided paired t, α 0.05). Spacing: the largest within noise of 3, at most +10% wall. Blackout above 20% of windows triggers the OPT-only stamp for redraw-only acts |
| E3 | Trust on real text, observe only | 'kv' against 'ctx'; `DATA_TRUST_CTX` 5 / 8 units | whether actuation is ever proposed | a manual audit of 100 sampled conflicted claims per rule must be dominated by content, not boilerplate; table size recorded; the book costs at most 2% wall or `DATA_TRUST_EVERY` lengthens |
| E4 | Source channel | `DATA_TAG` off / area / domain, drop 0.25 | `DATA_TAG` default | ON if untagged mean held-out bits/byte is not worse than off (one-sided paired t, α 0.05, 5 seeds); FAB expert-area and MEM hit-area purity reported with the tag on and off |
| E5 | Credibility stress on 'focusbed' | trust off / observe / loss / loss+draw × claims kv / ctx × worlds (base, majority-false, format variant, delimiter liar, impersonation 30% / 50%, stale truth, mixed reliability, paraphrase); K 3 / 5 / 8 | the actuation guard | an actuation value is eligible only if: Qc share rises at 5 of 5 seeds in the base world; `format_split_floored` = 0 in every world; the majority-false world loses at most 0.1 Qc accuracy; Qa falls by at most one item (0.010 of 96) at any seed; and SR6's copy detection is on |
| E6 | Probe cadence cost | `EVAL_RETENTION_EVERY` 160 / 500 / 1000 | the telemetry cadence | the densest cadence costing at most 2% wall (after SR0's bit-identity test) |

---

## 8. Open questions, each with a recommendation

- **Q1. Which draw becomes the default?**
  - *Recommendation:* E1's pre-registered rule (§7).
  - *Why open:* the toy tie (focus − m27 mean6 +0.033 / −0.074 / −0.016 / −0.009 / −0.004) is
    within seed spread. The newest-area win is reproduced by a hand-set boost. The literature
    predicts the tie may move either way at scale.
- **Q2. Owner ruling to confirm: on a statistical tie, does the self-regulated arm win?**
  - *Recommendation:* yes. The owner has stated a standing preference for self-regulation ("a part
    of my beliefs are for the system's self regulation for a large part of it").
  - The tie-break is fixed before E1 runs. It applies only when no hand-set arm beats 'retention'
    at α 0.05 over 5 paired seeds, with compute charged through `replay_cm`.
  - *Why open:* it trades a measured-neutral outcome for a belief. "Performance decides" is the
    owner's other standing rule, and only the owner can rank the two.
- **Q3. Should E1 include `DATA_PHASE_LIVE=3`, and should the shipped schedule ever change?**
  - *Recommendation:* include it as E1 shape (c). Do not change the shipped schedule on this
    evidence.
  - Availability stays hand-set because it is the experiment. At 2 live areas, allocation has
    little to decide, so shape (c) is where the self-regulated allocation can show itself.
  - *Why open:* only the owner decides the protocol.
- **Q4. Pure-add: may the child rehearse the parent's areas?**
  - *Recommendation:* no by default. Pure-add measures unprotected forgetting.
  - If yes, build `DATA_REHEARSE_PARENT` (False) as an arm (it is counted in the 306 on that condition; 305 if not): areas present in `DATA_AREAS`, in the parent's
    record, and live in no phase of the child count as faded from window 0.
  - *Why open:* it is an availability decision, so the owner's.
- **Q5. Confirm the default behaviour change `DATA_SYNTH_HOLDOUT` ON.**
  - *Recommendation:* ON. Evaluation needs held-out data, and every goal-B reading on 'focusbed'
    requires it.
  - *Why open:* it changes every synthetic-source run's stream, so no pre-change run pairs with a
    post-change one.
- **Q6. How should rehearsal be split across faded areas?** (This replaces the draft's rehearsal
  floor question, re-derived on end states per R-2.)
  - *Recommendation:* build `DATA_REHEARSE_EVEN` at 0 and test 0.5 in E2.
  - *Why open:* on end states hard is fine under 'focus', but easy is worse than m27 at 4 of 5
    seeds (+0.05 to +0.12), with 0.08-0.12 of P3 against 0.135. A slow-forgetting faded area gets a
    small need-weighted share. `DATA_REHEARSE_MIN` is dropped: its rationale was level-relative,
    and ρ sits at its ceiling anyway.
- **Q7. How should slow-progress, valuable areas be protected?**
  - *Recommendation:* test `DATA_FOCUS_FLOOR` 0.5 against 0.3 in E2, and report per-area gaps
    beside per-phase shares.
  - *Why open:* LP measures learnability, not value. cred and corrob are worse than m27 at 5 of 5
    seeds (+0.07 to +0.21).
- **Q8. What is a claim on real text?**
  - *Recommendation:* 'kv' (normalised key, value after a delimiter class) is the build target. Keep
    'ctx' as the prototype arm. Consider MEM's stored context keys as a later aligner (d1's
    proposal). Everything stays in observe until E3's audit and E5's worlds pass.
  - *Why open:* 'ctx' measures surface conformity (§2 row 16), and 'kv' is unprototyped.
- **Q9. Full-tail acts or a bounded look-ahead draw, and how should acts stamp?**
  - *Recommendation:* full-tail acts, rate-limited. Revisit if E2's splice timing exceeds +10% wall.
    If `fab.blackout_windows` exceeds 20% of the run, stamp redraw-only acts for OPT only.
  - *Why open:* the `TOK.splice` timing on a 17 MB tail is owed, and the blackout is an upper-bound
    estimate.
- **Q10. Should the probe produce the missing `best_bpb` for OPT's restart damping?**
  - *Recommendation:* yes, as an argument (the mean probe bits/byte) behind `OPT_DAMP_SOURCE`
    ('off' by default). It makes an existing self-regulator reachable at no new compute.
  - *Why open:* unmeasured. `EVAL.curve_probe` stays deferred.
- **Q11. The other built-but-off self-regulation arms the map found.**
  - The arms: the MEM 'quantile' write gate (the fixed 0.3 gate admits 100%: 70,656 of 70,656
    real), `FAB_LR_OWN`, the DOM 'relative' shift rule, and a SIG floor from DOM's live count.
  - *Recommendation:* include them in the honing sweep. Self-weighting of auxiliary losses deserves
    its own proposal.
  - *Why open:* this study did not measure them.
- **Q12. Collusion and impersonation.**
  - *Recommendation:* observe mode, `DATA_TRUST_MIN` 0.3, and copy detection (SR6) before any
    actuation default.
  - *Why open:* majority-false inverts trust at 3 of 3 seeds, and 50% impersonation flips it
    (1 seed).
- **Q13. Tag id: area, DOM domain or document? And where does the tag enter?**
  - *Recommendation:* 'area' first (measured), then 'domain' in E4 as the emergent arm. Keep the
    input-embedding entry unless E4's purity gauges show label-driven structure. In that case, move
    it to the LM head input.
  - *Why open:* 'domain' is unmeasured, and DOM's purity (0.80-0.82) means a domain id mixes areas.
- **Q14. Should `LM_SEL` be built at all?**
  - *Recommendation:* build it OFF at SR5, last. A Rho-1 small frozen reference is the untested
    alternative.
- **Q15. Frame rate.**
  - *Recommendation:* 03b's 'measured' stays the default. 'progress' is built OFF at 03b S3 and
    judged against 'measured' at a matched frame budget.
  - *Why open:* this study made no media measurement at all.
