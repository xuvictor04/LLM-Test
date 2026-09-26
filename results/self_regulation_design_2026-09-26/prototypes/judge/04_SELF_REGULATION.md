# Proposal 04 — Self-regulation: the run chooses its focus, weighs its sources, and shows what emerged

**Status: design, judged, not built.** It adds to the tree; it replaces nothing. Every mechanism
below enters behind a lever, and the tree's behaviour at the shipped defaults changes in exactly
two places, both telemetry: the per-area retention probe and the source-reliability book run in
observe mode (§6).

**Why it exists.** The owner, 2026-09-26: *"I was thinking, a certain level of self regulation (ie
in how much the llm focuses on what it wants to, for frame rate, but also in general.) a part of my
beliefs are for the system's self regulation for a large part of it. ... Lastly, I was thinking a
degree of 'context awareness' needs to occur, ie awareness of credibility of sources and other
things. I hope much of what I want and more will come out from emergence, which is part of the
questions."*

Three threads follow from that:
- **focus** — the run decides what it spends its learning on: which areas, when it rehearses, and
  (for 03b) at what media rate;
- **context awareness** — the run knows where its bytes come from and how far each source can be
  trusted;
- **emergence** — each design says what it builds, what it leaves to emerge, and how emergence is
  observed, with did-it-fire counters. An emergence that cannot be observed is not a result.

**How to read it.**
- It is a build specification, not an essay.
- The plain-language summary is §0.
- The default stack, each item with its reason and alternatives, is §1.
- The evidence table is §2.
- What is built and what is left to emerge, with the gauges, is §3.
- Risks and guards are §4. Tree fit is §5. Every default, on and off, is §6.
- The build order and the GPU experiments that decide the defaults are §7.
- Open questions, each with a recommendation, are §8.

**How it was produced and checked.**
- A tree map (seed 0, one default epoch per source, CPU) and a literature review came first. The
  review could not open arXiv or venue pages (egress refused), so every literature number below is
  quoted from abstracts and marked as such.
- A shared testbed was built (d2), then three designs were prototyped on it independently:
  - **d1**, an explicit meta-controller: a learning-progress bandit over areas plus
    gradient-consistency source trust;
  - **d2**, a source-conditioned LM: a per-token source-id channel with tag dropout, plus a
    model-internal source-agreement readout; a lagged-self selective loss was tested and failed;
  - **d3**, retention-paced focus: learning-progress allocation plus forgetting-paced rehearsal of
    faded areas from an online held-out probe, plus claim-level truth discovery.
- A judge (this document) checked the evidence, reran one headline per design, recomputed every
  design on one common scoreboard, extended d3 to a third seed, and ran two new measurements: the
  d2 + d3 graft and the tree's act constraint (§2 rows 16-17).

**What the judge's check found before scoring** (all in `judge/`):
- **d1's seed-0 baseline and seed-0 full arm were made before the testbed's determinism fix.** The
  testbed's entity order came from a Python set (PYTHONHASHSEED-dependent) until 12:09:49 (file
  mtime; the CHANGELOG says "about 12:20"). `d1/out/base_s0.json` (12:11) and `d1/out/full_s0.json`
  (12:12) have different oracles from every post-fix seed-0 run (cred oracle 1.544821 and 1.54413
  against 1.543928), so d1's seed-0 paired differences against them are not paired. The judge
  reran both with d1's own code: `judge/w/d1/out/base_judge_s0.json` is bit-identical to d2's and
  d3's base_s0, and the post-fix `full_judge_s0.json` erases d1's seed-0 credibility gain (Qc
  share 0.383 against lp's 0.392, where d1 reported +0.170).
- **d1's fixed-replay control front-loads its rehearsal.** It picks uniformly among areas with
  budget left, so the two faded areas' budgets are spent early in the last phase and nothing
  rehearses at its end. d3's fixed replay spreads the same 20% by deficit scheduling. Same share,
  different results: easy forgetting 0.398/0.371 (d1) against 0.050/0.030 (d3), seeds 0/1. d1's
  "LP beats replay" is against the weaker control; against d3's matched 27% replay, d1's lp loses
  on the common metric at 3 of 3 seeds (+0.021/+0.028/+0.056).
- **The designers used different headline metrics.** d1 and d2 average six learnable areas
  including the liar; d3 averages five, excluding it. That flatters d3's full arm, which
  down-weights the liar on purpose. The judge's scoreboard (`judge/score.py`, `judge/compare.py`)
  reports both, for every run, and every comparison below says which.
- **Same testbed, same budget, confirmed.** All three imported `testbed/testbed.py` unchanged
  (md5 89ad38c5…), at 4,000,000 bytes, 1953 steps of 16 × 128-byte windows. d1's and d3's
  baseline code paths reproduce d2's baseline bit for bit.
- **Reruns were bit-identical under a different PYTHONHASHSEED:** d3 fulltd s0, d2 tags s0, d1's
  base s0 (against d2's post-fix file), and d3 focus s0. The last confirms d3's note that its
  `focus_s*.json` files are copies of `full_c08` (trust armed, never actuated).
- The judge's own runs total about 28 process-minutes (15 runs, `judge/w/*/out/*.json` walls).

Evidence lives under `results/self_regulation_design_2026-09-26/`:
- `prototypes/map/`: the tree map's probe scripts.
- `prototypes/lit/`: the literature review (verification status in its header).
- `prototypes/testbed/`: `testbed.py` and `CHANGELOG.txt` (the determinism fix).
- `prototypes/{d1,d2,d3}/`: each design's `run.py`, analysis scripts, `out/*.json` and logs.
- `prototypes/judge/`:
  - `score.py` → `scoreboard.json`, `scoreboard.txt`: every run on one metric set, with a pairing
    flag;
  - `compare.py` → `compare.txt`: the paired head-to-head tables cited below;
  - `w/d3/run_tags.py`: the d2 + d3 graft (d3 plus the source-tag channel);
  - `w/d3/run_act.py`: d3 with the tree's act constraint emulated;
  - `w/{d1,d2,d3}/out/`: the reruns and new runs; `w/queue_*.sh`: their exact commands.
- `prototypes/critic/`, `prototypes/repro/`: the review and reproduction stages that follow this
  judgement.

To rerun a judge row, run from `prototypes/judge/w/d3/` (`w/testbed` is a relative symlink to
`../../testbed`); every other row runs from its designer's directory.

**Every number is a CPU prototype reading at toy scale:** a 1-layer GRU of width 128, a 16-letter
synthetic byte corpus of 7 areas, 16 windows per optimizer step (the tree runs 1), an online draw
(no act needed), 3 seeds unless stated. It is a signal, not a result. The GPU experiments in §7
decide the defaults.

**Words used below.**
- *Area*: a DATA area (a source directory or a synthetic generator). *Live*: in the current phase's
  schedule. *Faded*: live in an earlier phase, not now.
- *Planned*: today's `DATA_DRAW='planned'`, an even split of each phase's bytes across its live
  areas (stratified sampling).
- *Gap*: held-out bits/byte minus the generator's optimum ("oracle") on the same bytes.
- *mean6*: the mean gap over the six learnable areas (hard, easy, cred, false, corrob, late);
  *mean5* excludes the liar (false). *Null read*: no source tag at inference.
- *Forget X*: X's held-out bits/byte at the end minus at the end of phase 2, just before X fades.
- *Qc*: the 24 contested facts that only the credible source and the liar state; *Qa* the 24
  agreed facts. *Qc share*: p(true) / (p(true) + p(lie)).
- *Act*: the S0b post-flush, empty-batch re-segmentation of the unconsumed tail (built in HEAD:
  `TOK.splice`, `RunClock.revise_epoch_length`, `OPT.revise_horizon`, stage X in
  `spine/loop.py`).

---

## 0. In plain words

- **What the tree does today.** It regulates its own *structure*: adaptive depth (FAB halting),
  grown and culled experts, discovered domains, minted vocabulary. It does not regulate its
  *focus*. Which bytes it reads, in what proportion, and whether it ever revisits an old area are
  fixed before the first window. Once an area leaves the schedule it is never seen again, and
  nothing at runtime measures what is being forgotten.
- **What this adds: a draw the run steers itself.**
  - The run keeps a small fixed held-out probe per area and reads it every 160 windows.
  - From those readings it gives more bytes to areas it is still learning, fewer to areas it has
    mastered or cannot learn, and it brings back a faded area when that area's probe loss starts
    rising.
  - The operator still decides which areas exist and when they arrive; that is the experiment.
    The run decides how much of each it reads, and when to rehearse.
- **What that bought, measured.** Against today's draw, mean held-out gap fell by 0.26-0.34
  bits/byte on 3 of 3 seeds. Catastrophic forgetting of the easy area fell from 1.2-1.9 bits to
  under 0.06. The unlearnable noise area's share of the stream fell from 0.175 to about 0.11.
- **What it did not buy, measured.** Most of that gain comes from rehearsing at all.
  - A hand-set 27% replay of faded areas gets nearly the same mean: the self-regulated draw is
    +0.033 / −0.074 / −0.017 bits/byte against it, a tie within seed spread.
  - The two trade differently. Self-regulation learns the newest area much better (−0.36 to −0.38
    bits/byte against replay, 3 of 3). Fixed replay protects the hard old area much better (+0.16
    to +0.23 bits of forgetting against the self-regulated draw, 3 of 3).
  - The literature predicted this (Aioli: no online mixer consistently beats stratified sampling).
- **Context awareness, three routes, all measured.**
  - **Tell the model the source** (d2). Each token carries its area's id, and 25% of segments go
    untagged. The model then learns per-source conditionals:
    - read under the true tag, the mean gap falls 0.20-0.40 bits/byte;
    - read without a tag, it is +0.04 worse on average (−0.015 / +0.092 / +0.049);
    - answering "as the most reliable source" gets 0.92-1.00 of the contested facts right, against
      0.42-0.92 untagged.
  - **Truth discovery over repeated claims** (d3). DATA indexes contexts each source asserts
    consistently and finds where sources disagree. It weighs sources by agreement, never by
    fluency. On the testbed it found the liar within 100 steps. Down-weighting the liar lifted the
    contested-fact true share from 0.45 / 0.54 / 0.87 to 0.74 / 0.80 / 0.96.
    - It is defeated when the majority lies (1 seed).
    - It relies on facts being byte-exact repeated contexts, which real text is not.
  - **Gradient agreement between areas** (d1). It ranked the liar lowest, but its effect on facts
    was null at one seed out of three.
- **Emergence, honestly.**
  - The *schedule* emerged in the known-answer sense on every seed: noise demoted, the mastered
    area demoted, the hard area promoted, rehearsal switched on at the first probe after an area
    faded. No area was told what it was.
  - *Trust inside the model* did not emerge without scaffolding: no untagged "credible default",
    no recognition of a source from its style. The model's own tag-conditioned answers do rank the
    credible source first (3 of 3 seeds); that is emergent given the tag.
- **Defaults.**
  - The self-regulated draw is built OFF. The GPU A/B decides between it, fixed replay and today's
    draw. The recommendation, if it ties replay, is to take it (the owner's belief breaks a tie).
  - The source channel is built OFF until its own A/B.
  - The retention probe and the reliability book run in observe mode by default. They are the
    runtime forgetting signal the tree lacks today, and the yardstick for emergence.
- **Frame rate.** 03b's rate choice is the same allocation problem one level down. §1 item 9 keeps
  03b's measured rule as the default and adds this controller as an arm there.

---

## 1. Decisions — the default stack

Each item gives the default, the reason and the alternatives. Alternatives are recorded, not
deleted.

**1 — FOCUS: A SELF-REGULATED DRAW, `DATA_DRAW='retention'`, BUILT OFF.**
The d3 controller, with d1's floor and cap semantics:
- *Probe.* EVAL reads each seen area's fixed held-out probe windows (`EVAL_RETENTION_N` 6) every
  `EVAL_RETENTION_EVERY` windows (160 under 'retention'), in bits per byte, the only unit
  comparable across areas.
- *Books per area.* Fast and slow EMAs (0.3, 0.05 per probe), a jitter EMA, and the running best.
- *Live areas.* Absolute learning progress, |slow − fast| minus jitter, per interval. An area with
  fewer than `DATA_FOCUS_WARM` (10) probes gets the best live score (optimism, so new material is
  not avoided).
- *Faded areas.* Measured forgetting, (fast − best − jitter)+.
- *Rehearsal fraction.* ρ = min(`DATA_REHEARSE_MAX` 0.3, Σneed / (Σneed + ΣLP)); ρ = 0 when
  nothing is being lost.
- *Live shares.* (1 − ρ)·[`DATA_FOCUS_FLOOR`/n + (1 − floor)·LP_a/ΣLP], each area capped at
  `DATA_FOCUS_CAP` 0.5 and at the runtime exposure ceiling. Faded shares are ρ·need_a/Σneed.
- *Realisation.* Deficit scheduling per segment, bytes since the last re-plan against plan.
- *Tree.* The plan is recomputed at every probe, but the tail is re-laid only at an act (item 3).

*Reason.*
- Against today's draw it wins on 3 of 3 seeds: mean6 −0.284 / −0.338 / −0.264 (d3 focus) and
  −0.296 / −0.237 / −0.191 (d1 lp) (§2 rows 1-2).
- It is the only arm that improves both the old areas and the newest one:
  - late gap −0.089 / −0.112 / −0.283 against today;
  - fixed replay +0.293 / +0.251 / +0.076 against today on late, i.e. worse.
- It meets the owner's belief: the allocation, the rehearsal onset and the rehearsal amount are
  the run's, not the operator's.

*Why OFF at build.*
- Against a matched fixed replay it ties within seed spread (mean6 +0.033 / −0.074 / −0.017).
- It loses on hard forgetting (+0.200 / +0.158 / +0.233) and on noise calibration.
- It costs about 18% of toy wall time for the probe (with MIR) against about 0% for replay.
- The testbed deviates from the owner's run (batch 16, GRU, online draw).
- So the owner-shape A/B (§7 E1) decides. If 'retention' ties 'replay' within seed noise on mean
  held-out bits/byte, the recommendation is 'retention' (the owner's stated belief breaks a tie,
  and it does not trade away the newest area). If it loses beyond noise, 'replay' becomes the
  default and 'retention' stays an arm.

*Alternatives, all built as values or levers.*
- `'planned'`, today's draw, the build default. It is stratified sampling, a strong baseline, not
  a strawman.
- `'replay'`, fixed rehearsal (item 2).
- `DATA_FOCUS_SIGNAL='stream'`: the free in-stream loss instead of the probe. d1 measured it null
  (mean6 −0.116 / +0.035) and blind to forgetting (easy forgetting 1.685 / 1.850 against 1.871 /
  1.650), because a faded area has no in-stream signal. Kept as the ablation that shows the probe
  is load-bearing.
- `DATA_FOCUS_RULE='loss'`: loss-seeking, the noisy-TV rule. d1 measured noise share 0.218 / 0.217
  against 0.175. Kept as the ablation that demonstrates the risk.
- `DATA_FOCUS_MIR`: MIR-style predicted interference in the rehearsal need, built OFF. It was
  inert: focus_nomir matched focus, mean6 1.462 / 1.324 against 1.467 / 1.326. It costs a backward
  pass per probe.
- `DATA_REHEARSE_MIN`: a rehearsal floor inside 'retention', aimed at the hard-forgetting loss.
  Default 0, the measured value. Nonzero is unmeasured (§8 Q2).
- Rejected as the shipped regulator, still built as a rule value: d1's Exp3-style explore mixing
  in place of the floor. It is measured, but loses to fixed replay 3 of 3 on mean6.

**2 — A FIXED-REHEARSAL DRAW, `DATA_DRAW='replay'`, BUILT OFF.**
Each phase with faded areas gives `DATA_REPLAY_SHARE` (0.27) of its bytes to them, split evenly and
spread by deficit scheduling (never front-loaded).
- *Reason.* It is the control 'retention' must beat, and the literature's goal-B baseline (Ibrahim
  2024, abstract: replay plus LR re-warm matches retraining).
  - Measured against today (d3, seeds 0/1, judge s2): mean6 −0.317 / −0.265 / −0.248; hard
    forgetting 0.051 / 0.054 / 0.036 against 0.449 / 0.594 / 0.434.
  - 0.27 matches 'retention's measured mean ρ in the last phase (0.286 / 0.299 / 0.277).
- *Alternative.* 0.2, measured: hard forgetting 0.121 / 0.120.
- *Implementation rule, from the judge's check.* Rehearsal bytes are spread across the phase by
  deficit scheduling. d1's uniform pick among budgets front-loads them and loses most of the
  benefit (easy forgetting 0.398 / 0.371 against 0.050 / 0.030 at the same 20%).

**3 — THE FOCUS ACTS AT THE S0B ACT, RATE-LIMITED, `DATA_FOCUS_ACT_EVERY` 6 PROBES.**
- The tree materialises the epoch up front, so a new plan changes the unconsumed tail only through
  an act: `DATA.redraw_tail`, then `TOK.splice(at=k0)`, then `RunClock.revise_epoch_length`, then
  `OPT.revise_horizon`.
- An act runs at the first probe after each phase entry, then at most every 6 probes (960 windows
  at the default cadence), and only when the plan's total-variation change since the last act is
  at least `DATA_FOCUS_SHIFT_TV` 0.1.
- If a TOK retok act is due at the same flush, the two share one splice.
- *Reason, measured by the judge (§2 row 17).* The emulated constraint (plan applied at 35 acts
  instead of 195 re-plans) did not cost: mean6 1.500 / 1.449 against 1.536 / 1.452 at every probe,
  mean5 1.383 / 1.317 against 1.422 / 1.319, seeds 0/1. Every act re-segments the whole tail, so
  fewer acts is cheaper. At the owner's ~20k windows that is about 21 acts plus phase entries.
- *Alternatives.*
  - An act at every probe (about 125 acts per run, rejected on cost).
  - A bounded look-ahead draw (DATA materialises only the next K windows). It needs no whole-tail
    splice but breaks the "whole epoch up front" invariant and makes the startup exposure gate a
    projection; §8 Q5.
- *Owed.* The `TOK.splice` timing on a 17 MB tail (also owed by 03b).

**4 — EVERY PLAN CHANGE AT AN ACT IS A SELF-CAUSED SHIFT.**
- When an act moves the plan by at least `DATA_FOCUS_SHIFT_TV`, the act stamps `shift_at_windows`
  and `shift_at_steps` as the roll does, so FAB's regression detector and OPT's re-warm read the
  change as self-inflicted rather than as new material. Counter `data.focus.shift_stamps`.
- *Reason.* CAP's recorded runaway (2048 → 8192 in 19 lifts) is a loop in which a self-caused loss
  jump was read as a stall.
- *Not measured.* The testbed has no FAB. S0b's act already stamps a shift for retokenization, so
  this reuses that path.

**5 — THE RETENTION PROBE IS ON BY DEFAULT AS TELEMETRY.**
- `EVAL.retention_probe` runs at every `EVAL_RETENTION_EVERY`, whose default '' resolves to 160
  windows under 'retention' and to 1000 otherwise.
- *Reason.*
  - The tree has no runtime forgetting signal. `EVAL.holdout_probe` is a P5 stub, and the
    synthetic source holds out 0 bytes.
  - The probe is that signal: an online R matrix whose row ABSENT means the area was never seen.
  - At 1000 windows and 4 areas it reads 480 extra forward windows in a 20k-window run, about 2.4%
    of windows. The compute is estimated (not measured) under 1% if a forward is a third of a
    training step.
- *Prerequisite.* The synthetic source generates a held-out block per area from its own rng child
  (`data.synth.<label>.holdout`), leaving the training bodies byte-identical. Real sources already
  hold out `DATA_HOLDOUT_FRAC`.
- *Alternative.* `EVAL_RETENTION_EVERY=0` (off). It is ABSENT in the report, not zero.

**6 — CREDIBILITY: A SOURCE-RELIABILITY BOOK IN OBSERVE MODE, `DATA_TRUST='observe'`, RULE `'claims'`.**
The reliability book is d3's claim-level truth discovery, owned by DATA:
- *Claims.* A context of `DATA_TRUST_CTX` (5) units on which a source is self-consistent: seen at
  least 3 times, top continuation share at least 0.8. A count sketch pre-filters contexts (hot at
  20).
- *Evidence.* Only conflicted claims count: at least 2 claimant sources and at least 2 values.
- *Iteration.* The truth of a claim is the reliability-weighted vote, and a tie decides nothing.
  Reliability r_s = (agree + 1) / (n + 2), iterated 10 times.
- *Trust.* t_s = clip(r_s / max r, `DATA_TRUST_MIN` 0.3, 1), set only for sources with at least
  `DATA_TRUST_MIN_EV` (10) conflicted claims. Below that the evidence is ABSENT and trust stays 1.
- *Observe mode.* It logs r, t, the conflicted-claim count and the would-be weights, and changes
  nothing.
- *Actuation values.*
  - `'loss'`: the per-token loss weight is t, renormalised to mean 1, through
    `LM.lm_loss(token_weights=)`.
  - `'loss+draw'`: also multiplies each live area's LP by t, which is d3's fulltd.

*Reason.*
- It is the only estimator that moved facts consistently at 3 seeds:
  - fulltd Qc share 0.739 / 0.802 / 0.956 against 0.450 / 0.536 / 0.870 today;
  - fulltd against the same draw without trust: 0.346 / 0.396 / 0.858.
- It reads no model output and no loss level, so a fluent liar cannot game it, and neither can
  volume (one vote per source per claim).
- LP focus without it amplified the fluent liar: false drawn 0.179 / 0.197 against cred 0.125 /
  0.135 (d3 focus s0 / s1).

*Why observe, not actuate, by default.*
- It is defeated by a lying majority: Qc 0.125 against 0.333 (d3, 1 seed).
- Down-weighting a source also costs its true content (false gap +0.87 / +0.81).
- On the testbed, facts are byte-exact repeated contexts ('@EEE='), so claims come for free. On
  real text, 5-unit contexts will mostly catch boilerplate. That is unmeasured, and observe mode on
  the owner's corpus is how it gets measured (§7 E3).

*Alternatives, built as rule values.*
- `'peer'`: d1's gradient-consistency trust. False got the lowest realised weight of the three
  fact sources in 5 of 5 post-fix runs (the judge's seed-0 rerun included), but it changed facts in 2 of 3 seeds only,
  and at the post-fix seed 0 it cut agreed-fact recall to 0.625.
- `'residual'`: d3's model-internal calibration residual. Measured harmful: it floored hard, noise
  and the new true source, and scored the liar most consistent. Kept only as an ablation, never a
  default.
- `'fluency'` (trust by low loss): the gameable rule. d1: false weight 1.187 / 1.177 against cred
  1.118 / 1.073. Kept as the gaming demonstration.

**7 — CONTEXT AWARENESS INSIDE THE MODEL: A SOURCE CHANNEL, `DATA_TAG='off'` AT BUILD, ARMS `'area'` AND `'domain'`.**
- Each splice segment carries its source id as a per-token embedding added at the LM's input.
  `DATA_TAG_DROP` (0.25) of segments go untagged, so the model keeps an untagged mode.
- The tag mask is a pure function of (seed, epoch, splice index): no checkpointed state.
- *Reason.*
  - It is the cheapest mechanism with the strongest measured effect when the tag is available at
    inference:
    - tagged-read mean6 1.352 / 1.337 / 1.425 against 1.751 / 1.665 / 1.621 today;
    - noise gap under its tag 0.030 / 0.033 / 0.011;
    - easy forgetting under its tag +0.31 / +0.29 / +0.28 against +1.87 / +1.65 / +1.23 untagged.
  - Its model-internal truth discovery trusts the credible source 3 of 3.
  - It composes with item 1 (§2 row 16): the graft's tagged-read mean5 was 1.335 / 1.197 / 1.209,
    the best of any arm, and the controller rehearsed less (last-phase ρ 0.181 / 0.236 / 0.236
    against 0.286 / 0.299 / 0.277) because tagged separation reduced forgetting.
- *Why OFF at build.* Untagged generation, the common case for goal A, is neutral to worse:
  - mean6 −0.015 / +0.092 / +0.049 against today;
  - +0.086 / +0.048 / +0.117 for the graft against d3 alone.
  §7 E4 decides. The recommendation: flip it on if the untagged cost at owner scale is within
  noise, because the tagged gains are large and the owner asked for context awareness.
- *Alternatives.*
  - `DATA_TAG_DROP=0` is rejected: untagged mean6 2.246 / 2.214 / 2.064.
  - `'domain'` (DOM's did as the id: discovered, not given, so the more emergent arm) is
    unmeasured. DOM's did→area purity is 0.80-0.82 (map).
  - A prefix token instead of an embedding (MeCo) is rejected for the tree: windows are cut
    mid-segment, so a prefix would be absent from most windows.

**8 — MODEL-SIDE SELECTIVE LOSS, `LM_SEL='off'`, BUILT AS AN ABLATION.**
- d2's lagged-self token weighting (reference = an EMA of the weights, 0.99 per step).
- *Reason for off.* Measured negative on every reading:
  - learnable gap worse than its control in 6 of 6 pairs (sel mean6 1.815 / 1.713 / 1.697 against
    1.751 / 1.665 / 1.621);
  - the noise area's gradient weight rose to 1.04-1.11 times its draw share, the opposite of
    avoidance;
  - +30% wall time.
- It is built because the owner's phase is "build everything" and because only one reference
  (lagged self at 0.99) was tested.
- *Alternative.* Rho-1's frozen or small reference model (literature, not prototyped).

**9 — FRAME RATE: 03b'S MEASURED RULE STAYS; THIS CONTROLLER IS AN ARM THERE.**
- 03b's `AUD_RATE_MODE='measured'` (the coarsest stride within `AUD_RATE_TOL` 0.05 of stride 1 on
  recover exact) stays the default. Its readiness Gate decides which strides are admissible.
- A new value `'progress'` lets the item-1 controller choose among admissible strides per area:
  - reward: held-out progress per unit of token cost;
  - floor: the coarsest admissible stride;
  - cap: stride 1;
  - optimism at each area's arrival (03b's 'measured_arrival');
  - a shift stamp at every rate change.
- *Reason.* 03b measured that a fixed stride beat or tied per-segment adaptive rates at toy scale.
  This study found the same shape for rehearsal (fixed replay ties adaptive). Both predict the
  adaptive arm wins mainly by moving budget off segments that do not repay it.
- Unmeasured for media; built at 03b's S3, OFF.

**10 — NOTHING IN THE OPERATOR'S EXPERIMENT MOVES.**
The following stay hand-set, each necessary:
- the pool of areas (`DATA_AREAS`);
- availability (who is live when, the phase schedule);
- the total byte budget (compute);
- the held-out and probe sets (measurement contracts: a probe that moved with focus would measure
  its own choices).
Allocation, rehearsal, trust and the rate among admissible strides become the run's.

---

## 2. The measured basis

All on the shared testbed, 4,000,000 bytes, seeds 0/1/2 unless stated. Base = today's planned draw
(`d2/out/base_s*.json`, identical to d1's rerun and d3's base). Paired differences are per seed.
Paths are under `prototypes/`.

| # | Claim | Per-seed numbers | Harness | Evidence |
|---|---|---|---|---|
| 1 | Self-regulated focus (d3) beats today's draw | mean6 1.467 / 1.326 / 1.357 vs 1.751 / 1.665 / 1.621 (−0.284 / −0.338 / −0.264) | d3 run.py `--arm focus` (s2: judge) | `d3/out/focus_s{0,1}.json`, `judge/w/d3/out/focus_s2.json`, `judge/compare.txt` |
| 2 | d1's LP bandit beats today's draw | mean6 1.455 / 1.428 / 1.430 (−0.296 / −0.237 / −0.191) | d1 run.py `--arm lp` | `d1/out/lp_s*.json` |
| 3 | Matched fixed replay (27%) gets most of it | mean6 1.434 / 1.400 / 1.374 (−0.317 / −0.265 / −0.248) | d3 `--arm replay_fixed --replay 0.27` | `d3/out/replay_fixed_m27_s{0,1}.json`, `judge/w/d3/out/replay_fixed_m27_s2.json` |
| 4 | Focus vs matched replay: a tie on the mean | d3 focus − m27: +0.033 / −0.074 / −0.017; d1 lp − m27: +0.021 / +0.028 / +0.056 | rows 1-3 | `judge/compare.txt` |
| 5 | The trade: plasticity for old-area retention | late gap focus 1.839 / 1.727 / 1.702 vs m27 2.221 / 2.090 / 2.061; forget hard focus 0.251 / 0.212 / 0.269 vs m27 0.051 / 0.054 / 0.036 | rows 1, 3 | same |
| 6 | Catastrophic forgetting of easy removed by any spread rehearsal | forget easy: base 1.871 / 1.650 / 1.231; focus 0.010 / −0.001 / 0.046; m27 0.003 / −0.002 / −0.003 | rows 1, 3 | same |
| 7 | Noise demoted, calibration cost | noise drawn share focus 0.104 / 0.104 / 0.113 vs 0.175; noise gap 0.361 / 0.473 / 0.419 vs 0.189 / 0.286 / 0.184 | row 1 | same |
| 8 | The held-out probe is load-bearing | lp_train mean6 1.634 / 1.700 (−0.116 / +0.035); forget easy 1.685 / 1.850 vs 1.871 / 1.650 (s0/s1) | d1 `--arm lp_train` | `d1/out/lp_train_s*.json` |
| 9 | Loss-seeking reproduces the noisy TV | noise share 0.218 / 0.217 vs 0.175; mean6 −0.004 / +0.020 (s0/s1) | d1 `--arm loss` | `d1/out/loss_s*.json` |
| 10 | LP focus amplifies a fluent liar | drawn false 0.179 / 0.197 vs cred 0.125 / 0.135; Qc acc 0.250 / 0.333 / 0.833 vs base 0.417 / 0.583 / 0.917 | d3 focus | `d3/out/focus_s*.json` |
| 11 | Claim truth discovery fixes it | fulltd Qc share 0.739 / 0.802 / 0.956 vs base 0.450 / 0.536 / 0.870; Qc acc 0.708 / 0.708 / 0.958; liar found at step 100 (48 conflicted claims, r_false 0.02, r_cred 0.98) | d3 `--arm fulltd`, `--arm trust_td` | `d3/out/fulltd_s*.json`, `judge/w/d3/out/fulltd_s2.json`, `d3/out/trust_td_s0.json` trust_log |
| 12 | Truth discovery fails when the majority lies | Qc acc 0.125 vs 0.333, Wc 0.083 vs 0.250, cred trust floored (seed 0 only) | d3 `--arm mf_trust_td` / `mf_base` | `d3/out/mf_*_s0.json` |
| 13 | Gradient-consistency trust is weak | full − lp Qc share −0.009 / +0.133 / +0.102; s0 Qa 0.625 (judge rerun, post-fix) | d1 `--arm full` | `judge/w/d1/out/full_judge_s0.json`, `d1/out/full_s{1,2}.json` |
| 14 | Source tags: large tagged gain, small untagged cost | tagged-read mean6 1.352 / 1.337 / 1.425; untagged 1.736 / 1.757 / 1.670 (−0.015 / +0.092 / +0.049); trusted-tag Qc 0.958 / 0.917 / 1.000; tag-TD trusts cred 3/3 | d2 `--arm tags` | `d2/out/tags_s*.json`, `judge/w/d2/out/tags_judge_s0.json` (bit-identical rerun) |
| 15 | Selective loss (lagged self) is negative | sel mean6 1.815 / 1.713 / 1.697 (+0.064 / +0.048 / +0.076); noise weight/draw 1.04 / 1.06 / 1.11 | d2 `--arm sel` | `d2/out/sel_s*.json` |
| 16 | Tags compose with focus (judge graft) | graft tagged-read mean5 1.335 / 1.197 / 1.209 vs fulltd null 1.422 / 1.319 / 1.285 and tags-only tagged 1.416 / 1.362 / 1.352; untagged mean6 +0.086 / +0.048 / +0.117 vs fulltd; last-phase ρ 0.181 / 0.236 / 0.236 vs 0.286 / 0.299 / 0.277; trusted-tag Qc 0.917 / 0.875 / 0.917 | `judge/w/d3/run_tags.py --arm fulltd --tags 1` | `judge/w/d3/out/fulltd_tags_s*.json` |
| 17 | The tree's act constraint costs nothing here | plan applied at 35 acts, not 195 re-plans: mean6 1.500 / 1.449 vs 1.536 / 1.452; mean5 1.383 / 1.317 vs 1.422 / 1.319 (s0/s1) | `judge/w/d3/run_act.py --arm fulltd --act_every 6` | `judge/w/d3/out/fulltd_act6_s*.json` |
| 18 | Model-internal credibility did not emerge untagged | style gap ≤ 0.083 in every arm; untagged Qc share moves with seed at fixed exposure (base 0.45 / 0.54 / 0.87, exposure 0.494-0.50) | d1 gauges, d2 exposure.py | `d1/gauges.py`, `d2/out/*`, `d2/exposure.py` |
| 19 | Probe cost on the toy | probe 23-24 s of 125-127 s wall (focus s2, fulltd s2, with MIR), about 18-19%; replay_m27 s2 96 s | judge runs | `judge/w/d3/out/{focus,fulltd,replay_fixed_m27}_s2.json` (`wall`, `wall_probe`) |
| 20 | Determinism | reruns bit-identical under PYTHONHASHSEED 12345 / 999 / 31: d3 fulltd s0, d2 tags s0, d3 focus s0, d1-code base s0 (== d2 base s0) | judge queues | `judge/w/queue_{a,b,f}.sh`, `judge/w/*/out/*_judge_s0.json` |

Literature, quoted from abstracts only (arXiv not openable this session):
- Aioli (2411.05735): no mixing method consistently beats stratified sampling (up to 6.9 ppl
  worse).
- No Train No Gain (2307.06440): selection gains vanish against a fully decayed LR.
- Ibrahim (2403.08763): replay plus LR re-warm matches retraining.
- MeCo (2501.01956) and PoLM 3.3 (2404.05405): source conditioning helps, and hashed ids suffice.
- Xie (2305.13300): coherent false evidence is accepted.

---

## 3. What is built, what is left to emerge, and how emergence is observed

**Built explicitly:**
- the retention probe;
- the focus books, rule, floor, cap, optimism, rehearsal pacing and act rate limit;
- the fixed-replay control;
- the claim index and truth discovery, with its actuation values;
- the source channel and its dropout;
- the model-internal agreement readout;
- the selective-loss ablation;
- every counter and gauge below.

**Left to emerge:**
- which area gets bytes when (nothing is written per phase);
- when rehearsal starts and how much;
- the avoidance of unlearnable material and the demotion of mastered material;
- the ranking of sources by reliability (no source is labelled credible);
- inside the model: per-source conditionals given a tag, trust in the untagged default, and
  recognition of a source from its style.

**Gauges.** Each has a pre-set threshold on a continuous metric (Schaeffer 2304.15004: apparent
emergence depends on the metric). Each has three states: ABSENT (no producer; key missing),
PRESENT-and-0 (armed, did not fire) and a count or value.

| Gauge | Fires when | Toy reading |
|---|---|---|
| `data.focus.noise_demoted` | known-answer corpus: noise area's realised share ≤ 0.7 × even share | fired: 0.104 / 0.104 / 0.113 vs even 0.175 (ratio 0.59-0.65) |
| `data.focus.mastered_demoted` | the mastered area's phase share < 0.85 × even share while its probe LP ≈ 0 | fired: easy phase-2 share 0.117 / 0.100 / 0.133 (fulltd) vs 0.167 |
| `data.focus.rehearse_onset_windows` | windows from an area fading to its first rehearsal byte | first probe after the phase change (160 windows) on every seed |
| `data.focus.lp_negative_pulls` / `rehearse_fired` | a faded area drawn because its loss rose | 48-49 of 49 last-phase re-plans (d3); ABSENT under `DATA_FOCUS_SIGNAL='stream'` (no faded signal) |
| `data.focus.floor_binds`, `cap_binds`, `rho_cap_binds` | the guard bound | e.g. fulltd s0: 94, 40, 36 |
| `data.trust.ranked_liar_last` | known-answer corpus: r_false < r_cred and r_corrob | fired at step 100 on every seed ('claims') |
| `data.trust.conflicted_claims` | count of conflicted claims | 48 at step 100 (s0); ABSENT on sources with < `MIN_EV` |
| `eval.src.steer_gap[area]` | bits/byte under a wrong tag minus under the true tag > 0.05 | 20 of 21 area-seed cells (d2); ABSENT at `DATA_TAG='off'` |
| `eval.src_agree.trusted` | model-internal TD over tag-conditioned answers names the credible source | cred 3/3 (tags), 3/3 (graft) |
| `eval.src.default_trust` | untagged Qc share − untagged exposure share > 0.10 in every seed AND beyond base's own drift | did not fire: base drifts +0.37 at s2 at fixed exposure (d2) |
| `eval.src.style_gap` | acc(credible-style prefix) − acc(liar-style prefix) > 0.10 | PRESENT-and-0: ≤ 0.083 everywhere |
| `credibility.emerged` | a model-output ranking of sources matches the claim-TD ranking | PRESENT-and-0 for the residual rule; fires for tag-TD (given tags) |

**What counts as emergence here.** A gauge fires on the known-answer corpus at 3 of 3 seeds, and
the paired baseline does not fire it. Single-seed firings are not reported as emergence: d2's
untagged default-trust cleared its threshold at 3 of 3 seeds but moved as much in the baseline.

**Known-answer corpus.** The mm3 testbed's seven generators become a synthetic kind in DATA
(`DATA_SYNTH_KIND='focusbed'`). They vary with the seed, share one alphabet, and print their oracle
entropies at startup:
- an order-2 hard area and a mastered-quickly easy area;
- an i.i.d. noise area;
- a credible source, a more-fluent liar and a corroborator;
- a conflicting late arrival.

Without that corpus, "emergent" allocation cannot be told apart from noise.

---

## 4. Risks and guards

- **Collapse onto easy or mastered material.**
  - Guard: absolute LP is about 0 on mastered material.
  - Measured: easy demoted to 0.100-0.133 of phase 2 (fulltd), and still protected by rehearsal
    (easy gap 0.525-0.635 under focus and fulltd against 1.753-2.482 today).
- **Avoiding hard-but-learnable material.**
  - Guards: optimism for new or unmeasured areas; the floor (`DATA_FOCUS_FLOOR` 0.3 of live
    bytes); the per-area cap 0.5.
  - Measured: hard promoted to 0.32-0.44 of phase 2.
  - Residual, measured: slow-progress areas are under-drawn. cred gap +0.244 / +0.164 / +0.133
    under focus against today. The floor protects recall but not bits/byte (§8 Q3).
- **Noisy TV.**
  - Guards: LP subtracts its own jitter; rehearsal only ever draws faded areas, and noise never
    fades, so its interference-driven loss rise cannot re-attract it.
  - Measured: noise share 0.104-0.113. The loss-seeking ablation goes the other way (0.218).
  - Residual: seeing less noise makes the model overconfident on it (noise gap +0.17 to +0.24).
    Under the source tag it largely disappears (tagged noise gap 0.011-0.063).
- **Starving old areas (goal B).**
  - Guards: forgetting-paced rehearsal; `DATA_REHEARSE_MAX`; a floor per live area.
  - Residual, measured: hard forgetting 0.21-0.33 (focus, fulltd) against 0.036-0.054 under fixed
    replay. §8 Q2 tests a rehearsal floor.
- **Feedback between focus and its signal.**
  - Guard: the reward reads a fixed held-out probe, never the windows the controller chose.
  - The in-stream variant is measured null (§2 row 8).
  - The trust-draw loop (down-weight → under-learn → look worse) is avoided by construction:
    'claims' reads DATA's bytes, not model output. The residual rule showed this loop live (hard
    floored, +0.33 / +0.31 bits), which is why it is an ablation only.
- **Gaming by fluent-but-false sources.**
  - Trust never reads loss level; `'fluency'` exists only to show it is gamed.
  - LP focus alone is gamed (row 10), so `'loss+draw'` multiplies LP by trust.
  - Majority collusion defeats truth discovery (row 12). The guards `DATA_TRUST_MIN` 0.3 and "a tie
    decides nothing" bound the damage but do not prevent it. Copy detection is not built (§8 Q8).
- **Self-caused shift misread as new material.** A shift stamp at every act that moves the plan
  (item 4). Counters `data.focus.shift_stamps` and `fab.growth_blackout`.
- **Instability.**
  - Guards: EMAs, jitter subtraction, deficit scheduling, the act rate limit and the TV threshold.
  - Measured: no oscillation in the plan logs. ρ is nearly bang-bang: at its cap in 36-47 of 49
    last-phase re-plans; with tags it relaxed to 1-4.
  - Trust was a step function (floored at step 100, held).
- **Cost.**
  - The probe is about 18-19% of toy wall time with MIR (MIR is OFF by default).
  - The tree's projected cost at 160 windows, 4 areas and 6 windows is about 15% extra forward
    windows (estimate).
  - The claim sketch is 16 MB of int32; the claim table grows with distinct self-consistent
    contexts (unmeasured on real text; bounded by an LRU of `DATA_TRUST_TABLE` entries).
  - Acts re-segment the tail (item 3).
- **Toy-to-tree gap.** Batch 16 against 1; a GRU against the tree's arms; synthetic facts as exact
  contexts; 4 MB against ~20 MB. Every default decision waits for §7's GPU runs.

---

## 5. Tree fit

**Ownership.**
- DATA owns the focus books, the plan, the redraw, the claim index and trust, because areas,
  splices and bytes are DATA's.
- EVAL owns the probe and the agreement readout. LM owns the loss and the source table. TOK maps
  the new per-byte channels.
- The root (`spine/loop.py`, composed in `spine/compose.py`) passes numbers, never decisions, and
  keeps no second EMA pair.
- No cross-package imports (O10).

**Wires.** 0 new. Every runtime value is an argument, because `Coupling.compute` sees only frozen
Configs. 19 of `WIRE_BUDGET` 25 stay used.

**New entry points (141 → 149)**, with their stage rows:
1. `EVAL.retention_probe(ev, *, units_by_area, logits_fn) -> Reading{area: bits/byte}`.
   - Stage A, cadenced on `EVAL_RETENTION_EVERY` (U.Windows).
   - Sibling of the deferred `holdout_probe` (`src/eval/api.py:271`), keyed by area rather than
     domain. It can become P5's body.
   - Probe windows come from `Areas.holdout`, drawn once from the rng child `eval.retention.probe`.
2. `EVAL.interference_probe(ev, *, units_by_area, loss_fn, params_fn, direction)`. Stage A,
   only when `DATA_FOCUS_MIR`; ABSENT otherwise.
3. `EVAL.source_agreement(ev, *, probes, answer_fn, n_sources) -> Reading{rel, trusted, steer_gap,
   style_gap}`. Stage A on `EVAL_SRC_EVERY`; ABSENT at `DATA_TAG='off'`.
4. `DATA.note_retention(dat, focus, *, reading, step) -> FocusPlan{shares, act_wanted}`.
   - Stage A, right after row 1.
   - DATA raises the act request (as TOK raises a retok request); the root only relays it.
5. `DATA.redraw_tail(dat, areas, plan, stream, *, at_byte, focus, act, seed) -> Stream`. Stage X.
   - Keeps bytes, labels, tags and sources in [0, at_byte) byte-identical.
   - Re-lays the tail within each phase's live set plus the faded set, with budgets from the
     shares minus the realised bytes.
   - Keeps `len == stream_bytes` (P1-L22).
   - Uses its own rng child `data.stream.e{E}.a{k}`.
   - at_byte = `byte_pos[k0+1]`, k0 = `win_in_epoch * ctx`: exact, with no new TOK accessor (map
     §3).
6. `DATA.note_windows(dat, focus, *, labels, nats, token_bytes, step)`.
   - Stage B: the free in-stream per-area books (bits per byte), from the per-window loss
     (`loop.py` `_flush`) and `Segmentation.labels`, which today are computed and read by nothing.
   - Telemetry, plus the `'stream'` signal ablation.
7. `DATA.claims_observe(dat, focus, *, ids, sources, step)`. Stage B, at the consumed cursor.
   - The tree variant keys claims on TOK ids (tokens, not bytes; §8 Q4).
8. `DATA.token_weights(dat, focus, sources) -> (B, L) weights | None`. Stage B. It returns None
   unless `DATA_TRUST` actuates.

**Signature moves (4):**
- `LM.lm_loss(lm, logits, y, *, token_weights=None)`: mean-1 normalised; `src/lm/api.py:833`.
- `LM.encode(lm, model, x, *, n_layers=None, extra=None, source_ids=None)`: adds `src(source_ids)`
  to the token vectors. `embed` is unchanged, so WORLD's `obs_emb` does not move.
- `TOK.tokenize(..., channels=None)` and `TOK.splice(..., channels=None)`: map each per-byte
  channel (`tags`, `sources`) through `byte_pos` exactly as `labels` are mapped
  (`tok/api.py:1639` in tokenize, `:1724-1725` in splice, at HEAD c5768be).

**New record fields:**
- `Stream.tags` (per byte: 0 or 1 + area index) and `Stream.sources` (per byte: source id finer
  than the area: file or document; for synthetic, the generator);
- `Segmentation.tags` and `Segmentation.sources`;
- `Areas.sources`: the manifest `open_areas` computes today and drops. `_read_area` records
  document boundaries instead of concatenating blindly.

**Root plumbing (`spine/loop.py`).**
- Per flush it slices `segmentation.labels`, `.tags` and `.sources` with the flush's token bounds
  and hands them to rows 6-8 and to `LM.encode`.
- At stage X, when `FocusPlan.act_wanted` is set (or a retok is due):
  1. `DATA.redraw_tail`;
  2. one `TOK.splice(at=k0, channels=…)`;
  3. `RunClock.revise_epoch_length`;
  4. `OPT.revise_horizon`;
  5. `DOM.on_retokenize` when the view moved;
  6. the shift stamp.
- MEM needs no remap for a redraw: the prefix is unchanged, and the tail has not been written.

**Runtime Gates.** `data.exposure_max` and `data.exposure_skew` become runtime Gates re-evaluated
at every act on realised plus planned bytes. `DATA_EXPOSURE_MAX` is a hard ceiling on any share:
an area cannot be drawn past it, even if it wants to be.

**Checkpoint, resume, geometry.** `DATA.stream_state` gains a `focus` block keyed by area name:
- Lf, Ls, best, jitter, n, last L;
- the current shares and the bytes-since-replan snapshot;
- the probe count at the last act;
- an append-only redraw log (act k, at_byte, shares).
Trust state:
- the claim table (bounded by `DATA_TRUST_TABLE`) and the sketch;
- r and t per source name;
- first-seen per source.
The LM's `src` table goes in `LM.state_dict`. The `LM_SEL` shadow, only when on, goes in OPT's
state.

Resume replays `draw_stream(epoch)`, then each logged redraw in order, then S0b's segmentation log
(`seg_log`, `loop.py:448`) — bit-exact, because every quantity is a function of the seed, the
stream and the logged decisions.

Geometry rules:
- A new area gets no row (ABSENT), then the optimism prior (the `data.area_added` rule).
- A vanished area is refused (`data.area_vanished`).
- A new source gets trust 1 and ABSENT evidence.
- LM `src` rows are appended at zero, never recycled. Shrinking `LM_SRC_SLOTS` below the live rows
  is refused.
- The sketch size is fixed at build (refused if it changes).

**Clock kinds.** Probe and act cadences in U.Windows; EMA rates per probe; the selective-loss EMA
per optimizer step (U.Steps); shares and floors in U.FRACTION.

**S0b dependency.**
- 'retention' and 'replay' re-lay the tail and need the act.
- `DATA_TAG`, `DATA_TRUST` (observe and actuation) and the probe do not.
- S0b's first three increments are in HEAD (54378b8, c8d8e33, c5768be): `TOK.splice`,
  `RunClock.revise_epoch_length`, `OPT.revise_horizon`, the act at stage X, and a mid-epoch resume
  that replays the segmentation log.

**Counters.** ABSENT when unreachable; PRESENT-and-0 when armed and not fired.
- `data.focus.*`: probes, replans, acts, acts_withheld, shift_stamps, lp_active, floor_binds,
  cap_binds, exposure_binds, optimistic_prior, forgetting_seen, rehearse_fired, rho_cap_binds,
  rehearsal_bytes, trust_gated, mir_evals, mir_positive, noise_demoted, mastered_demoted,
  rehearse_onset_windows.
- `data.replay.*`: fixed_phases, bytes.
- `data.trust.*`: updates, conflicted_claims, ranked_liar_last, actuations, floor_binds,
  weighted_batches, evidence_absent, table_evictions.
- `data.tag.*`: segments_tagged, segments_dropped.
- `lm.src.*`: tagged_tokens, untagged_tokens, rows_live, refused (must be 0).
- `lm.sel.*`: batches, floor_bound_frac, cap_bound_frac, wshare_over_draw.
- `eval.retention.*`: calls, windows. `eval.src_agree.*`, `eval.src.*`: the gauges in §3.

**Contract accounting.**
- +8 entry points (141 → 149) and 4 signature moves.
- Stage rows: +3 in A (rows 1-3), +1 after them in A (row 4), +3 in B (rows 6-8), +1 in X
  (row 5).
- +2 runtime Gates, 0 wires.
- New levers (§6). New values: `DATA_DRAW` += 'replay', 'retention'; `DATA_SYNTH_KIND` +=
  'focusbed'; `AUD_RATE_MODE` += 'progress' (at 03b S3).
- Nothing removed.

---

## 6. Defaults, ON and OFF

| Lever | Default | Unit | ON/OFF | Meaning |
|---|---|---|---|---|
| `DATA_DRAW` | 'planned' | name | self-regulation OFF | + 'replay', 'retention' (§1 items 1-2); flip decided by §7 E1 |
| `DATA_REPLAY_SHARE` | 0.27 | U.FRACTION of phase bytes | used under 'replay' | fixed rehearsal share, deficit-spread |
| `DATA_FOCUS_SIGNAL` | 'probe' | name | — | 'stream' is the measured-null ablation |
| `DATA_FOCUS_RULE` | 'lp' | name | — | 'loss' is the noisy-TV ablation |
| `DATA_FOCUS_FLOOR` | 0.3 | U.FRACTION of live bytes | — | split evenly across live areas |
| `DATA_FOCUS_CAP` | 0.5 | U.FRACTION | — | max share of one live area (also ≤ exposure_max) |
| `DATA_FOCUS_WARM` | 10 | probes | — | optimism until an area has this many probes |
| `DATA_FOCUS_EMA_FAST` / `_SLOW` | 0.3 / 0.05 | per probe | — | LP books |
| `DATA_REHEARSE_MAX` | 0.3 | U.FRACTION | — | cap on ρ |
| `DATA_REHEARSE_MIN` | 0.0 | U.FRACTION | OFF | rehearsal floor (unmeasured > 0; §8 Q2) |
| `DATA_REHEARSE_HREC` | 10 | probes | — | forgetting recovery horizon |
| `DATA_FOCUS_MIR` | False | bool | OFF | interference estimate (measured inert) |
| `DATA_FOCUS_ACT_EVERY` | 6 | probes | — | min act spacing (960 windows at 160) |
| `DATA_FOCUS_SHIFT_TV` | 0.1 | TV distance | — | plan change that triggers an act and a shift stamp |
| `EVAL_RETENTION_EVERY` | '' → 160 under 'retention', else 1000 | U.Windows | **ON** (telemetry) | 0 = off (ABSENT) |
| `EVAL_RETENTION_N` | 6 | windows per area | — | probe size |
| `DATA_SYNTH_HOLDOUT` | True | bool | **ON** | synthetic areas generate a held-out block from their own rng child; training bodies unchanged |
| `DATA_SYNTH_KIND` | 'order2' | name | — | 'focusbed' = the known-answer corpus |
| `DATA_TRUST` | 'observe' | name | **ON as telemetry, actuation OFF** | 'off' / 'observe' / 'loss' / 'loss+draw' |
| `DATA_TRUST_RULE` | 'claims' | name | — | 'peer', 'residual', 'fluency' are ablations |
| `DATA_TRUST_CTX` | 5 | TOK units | — | claim context length (testbed: bytes) |
| `DATA_TRUST_HOT` / `_SELF` / `_MIN_N` | 20 / 0.8 / 3 | count / share / count | — | claim admission |
| `DATA_TRUST_MIN_EV` | 10 | conflicted claims | — | below: ABSENT evidence, trust 1 |
| `DATA_TRUST_MIN` | 0.3 | loss-weight multiplier | — | trust floor |
| `DATA_TRUST_EVERY` | 160 | U.Windows | — | truth-discovery cadence (testbed: 10 steps × 16) |
| `DATA_TRUST_SKETCH` | 4194301 | buckets (int32) | — | fixed at build (geometry) |
| `DATA_TRUST_TABLE` | 200000 | contexts | — | LRU bound on the claim table (unmeasured size on real text) |
| `DATA_TAG` | 'off' | name | OFF | 'area', 'domain'; flip decided by §7 E4 |
| `DATA_TAG_DROP` | 0.25 | U.FRACTION of segments | — | untagged share (0 rejected) |
| `LM_SRC_SLOTS` | 64 | rows | — | zero-initialised source table |
| `EVAL_SRC_EVERY` | 2000 | U.Windows | active only when `DATA_TAG` ≠ off | agreement readout |
| `LM_SEL` | 'off' | name | OFF | 'abs', 'pos', 'loss' (measured negative) |
| `LM_SEL_EMA` / `_FLOOR` / `_CAP` | 0.99 / 0.25 / 4.0 | per U.Steps / U.FRACTION / × mean | — | selective-loss arm |
| `AUD_RATE_MODE` | 'measured' (03b) | name | — | + 'progress' at 03b S3, OFF |

`DATA_TRUST_EVERY` and `DATA_TRUST_TABLE` are the only new numbers with no toy measurement behind
them (the testbed ran truth discovery every 10 steps with an unbounded table). Both are costs, not
behaviours: E3 measures them.

Everything else in the tree is unchanged.

---

## 7. Staged build plan and the GPU experiments that decide defaults

Stages are named SR0-SR5, to avoid colliding with 03's S-series.

- **SR0 — measurement first.**
  - `DATA_SYNTH_HOLDOUT`; `DATA_SYNTH_KIND='focusbed'` (a port of `testbed.py`'s generators, with
    oracle entropies printed); `EVAL.retention_probe` at the telemetry cadence; `DATA.note_windows`
    books.
  - Test: bit-exact against HEAD with the probe off.
  - Known answer: the probe's row for an area that has not arrived is ABSENT.
- **SR1 — the act for DATA.**
  - `DATA.redraw_tail`; the X-row wiring; runtime exposure Gates; shift stamps; the redraw log in
    `stream_state` and its replay.
  - Test: a mid-epoch resume after 3 redraws is bit-exact.
  - Known answer: a redraw with the current shares and the same rng child reproduces the tail
    byte for byte.
- **SR2 — `'replay'`, then `'retention'`.**
  - Test: on 'focusbed', `data.focus.noise_demoted` and `mastered_demoted` fire at 3 of 3 seeds.
- **SR3 — sources and trust.**
  - `Stream.sources`, `Areas.sources`, document boundaries; `TOK` channels;
    `DATA.claims_observe`, `DATA.token_weights`; `LM.lm_loss(token_weights=)`.
  - Test: 'observe' changes no training number (bit-exact against off).
- **SR4 — context channel.**
  - `Stream.tags`; `LM.encode(source_ids=)`; `EVAL.source_agreement`.
  - Test: a zero-initialised table with all tags 0 is bit-exact against off.
- **SR5 — ablations.** `LM_SEL`; `DATA_FOCUS_MIR`; rule values 'peer', 'residual', 'fluency'.

**GPU experiments for the owner**
- Run shape: `RUN_EPOCHS=1`, ~20 MB stream, ~20k windows, `OPT_BATCH_WINDOWS=1`.
- 3 seeds each, paired; the synthetic corpus varies with `RUN_SEED`.
- 12 runs share one 140 GiB card.
- Thresholds are fixed before the runs.

| # | Experiment | Arms | Decides | Rule fixed in advance |
|---|---|---|---|---|
| E1 | The draw A/B, on 'focusbed' and on the owner's real areas (generated sliding-window schedule and pure-add) | planned / replay 0.27 / retention (± `DATA_REHEARSE_MIN` 0.1) | `DATA_DRAW` default | 'retention' if its mean held-out bits/byte is within 1 paired SD of 'replay' or better AND its newest-area gap is better; else 'replay' if it beats 'planned' beyond 1 paired SD; else 'planned' |
| E2 | Act spacing and cost | retention at `DATA_FOCUS_ACT_EVERY` 3 / 6 / 25; timed `TOK.splice` on the tail | act spacing | the largest spacing whose mean is within 1 paired SD of spacing 3; wall ≤ +10% |
| E3 | Trust on real text, observe only | `DATA_TRUST='observe'`, `DATA_TRUST_CTX` 5 / 8 tokens | whether actuation is ever proposed | conflicted claims must be dominated by content, not boilerplate (manual audit of 100 sampled claims); table size and wall recorded |
| E4 | Source channel | `DATA_TAG` off / area / domain, drop 0.25 | `DATA_TAG` default | ON if untagged mean held-out bits/byte is not worse beyond 1 paired SD |
| E5 | Credibility stress on 'focusbed' | trust off / observe / loss / loss+draw; majority-false world | the actuation guard | 'loss+draw' only if Qc share rises at 3 of 3 seeds and the majority-false world loses ≤ 0.1 Qc accuracy |
| E6 | Probe cadence cost | `EVAL_RETENTION_EVERY` 160 / 500 / 1000 | telemetry cadence | the densest cadence costing ≤ 2% wall |

---

## 8. Open questions, each with a recommendation

- **Q1. Which draw becomes the default?**
  - *Recommendation:* E1's pre-set rule. 'retention' on a tie, because it keeps the newest area
    learnable and makes the decision the run's.
  - *Why open:* the toy tie (+0.033 / −0.074 / −0.017) is within seed spread.
- **Q2. Should 'retention' carry a rehearsal floor?**
  - *Recommendation:* build `DATA_REHEARSE_MIN` (0 by default) and test 0.1 in E1. Fixed replay's
    hard-forgetting advantage (0.036-0.054 against 0.21-0.33) came from steady rehearsal. ρ was
    already at its cap for most of the last phase, so a floor mostly changes the first probes
    after a fade.
  - *Why open:* unmeasured.
- **Q3. How should slow-progress, valuable areas be protected?**
  - *Recommendation:* test `DATA_FOCUS_FLOOR` 0.5 against 0.3 in E1, and report per-area gaps, not
    only the mean.
  - *Why open:* LP measures learnability, not value. cred and corrob lost 0.13-0.31 bits/byte
    under focus (cred +0.244 / +0.164 / +0.133, corrob +0.244 / +0.306 / +0.206), and
    0.05-0.27 under fulltd.
- **Q4. What is a claim on real text?**
  - *Recommendation:* key on TOK ids at the consumed cursor, and later on MEM's stored context
    keys (the natural aligner d1 proposed). Keep 'claims' in observe until E3's audit.
  - *Why open:* byte-exact 5-byte contexts worked only because the testbed's facts are exact
    repeated records.
- **Q5. Full-tail acts or a bounded look-ahead draw?**
  - *Recommendation:* full-tail acts, rate-limited (row 17 says spacing is cheap in quality).
    Revisit if E2's splice timing exceeds +10% wall.
  - *Why open:* the `TOK.splice` timing on a 17 MB tail is owed.
- **Q6. Should the probe produce the missing `best_bpb` for OPT's restart damping?**
  - *Recommendation:* yes, as an argument (the mean probe bits/byte), behind `OPT_DAMP_SOURCE`
    ('off' by default), because it makes an existing self-regulator reachable at no new cost.
  - *Why open:* unmeasured.
- **Q7. What about the other built-but-off self-regulation arms the map found?**
  - The arms: the MEM 'quantile' write gate (the fixed 0.3 gate admits 100%), `FAB_LR_OWN`, the
    DOM 'relative' shift rule, and a SIG floor from DOM's live-domain count.
  - *Recommendation:* include them in the honing sweep. This study did not measure them.
  - Also: self-weighting of the auxiliary loss terms (uncertainty weighting or GradNorm) deserves
    its own proposal.
- **Q8. Collusion.**
  - *Recommendation:* keep `DATA_TRUST_MIN` 0.3 and observe mode, and design copy detection (shared
    false values, the ACCU-COPY family) before any trust actuation defaults on.
  - *Why open:* measured failure (row 12), at 1 seed.
- **Q9. Tag id: area, DOM domain or document?**
  - *Recommendation:* 'area' first (measured), then 'domain' in E4 as the emergent arm.
  - *Why open:* 'domain' is unmeasured. DOM's purity (0.80-0.82) means a domain id mixes areas.
- **Q10. Should `LM_SEL` be built at all?**
  - *Recommendation:* build it OFF as the brief requires, at SR5, last. Only one reference was
    tested; a Rho-1 small frozen reference is the untested alternative.
- **Q11. Frame rate.**
  - *Recommendation:* 03b's 'measured' stays the default; 'progress' is built OFF at 03b S3 and
    judged against 'measured' at matched frame budget.
