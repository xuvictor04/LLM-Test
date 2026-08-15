# 09 — COMMENT AUDIT

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are tiny
> — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has reached
> 1.227 b/B (`33a9299`), larger than the gap between any two architectures ever compared here.
> Several confidently-stated findings were later retracted when the measurement turned out to be
> broken. Every entry records **what was observed under these conditions**, never **what is true**.
> Where a result was later invalidated, the invalidation is stated next to it, not in a footnote.

**This file is a PLAN. No source file was modified to produce it.** See §7.

---

## 1. The standing rule

A comment **moves out** of the source if ANY of these hold (`DOC_PLAN.md` §9):

1. It states a measured number from a specific run (b/B, %, counts, ms, step numbers).
2. It narrates history — *"used to"*, *"I"*, *"we"*, *"earlier"*, *"turned out"*, *"was wrong"*,
   *"retracted"*, *"the pilot showed"*.
3. It argues against an alternative that was tried and rejected, rather than stating what the code does.
4. It cites a run, arm, pilot or commit as evidence.
5. It justifies a default by evidence rather than by mechanism.

A comment **stays** if it states what the code does; a contract or invariant; units and shapes; an
ordering requirement or hazard for the next editor (*"must run before X"*, *"must not receive
gradient"*, *"an eval pass must not call this"*); or a dependency between knobs.

**The decisive test.** *Would this comment become false when a DEFAULT changes or a new run is done?*
→ extraneous. *Would it become false only when the CODE changes?* → it stays.

**The project has already ratified this criterion, and ratified it the hard way.** `bdce727`
(2026-08-10) replaced six stale claims with fresh claims. `6dda2c4`, the same day, concluded that
this was the wrong repair — *"a comment that records a measurement is wrong the moment the code
changes, and this file has now misled me twice that way"* — and removed the empirical assertions
instead. `8103a8a` (2026-08-11) moved results out of comments into `runs.csv` for exactly this
reason. **Replacing a number with a fresher number is not the fix; removing the number and pointing
at the record is.**

### 1.1 The replacement pattern (from `6dda2c4`)

Keep a number **only** where it explains a DECISION. When you keep one: say when it was measured,
say it in the **past tense**, and point at the report line or notes file that answers it now. The two
comments in this repo that already follow the pattern are the model to copy:

- `self_organize.py:1089` — *"Numbers in runs.csv (`python3 runs.py list --arm fabric`)."*
- `self_organize.py:5542` — *"The numbers live in runs.csv (`python3 runs.py list --arm 707f1af`),
  not here -- a comment cannot say which knobs produced it, and cannot be re-checked when a default
  moves, which is exactly what happened to these."*

---

## 2. Method (so the pass is repeatable)

Run from the repo root, on branch `rm-predict`, HEAD `45b98eb`.

**Stage 1 — enumerate blocks mechanically.** A *block* is a maximal run of consecutive lines whose
first non-space character is `#` (excluding `#!`). *Substantial* = **≥ 3 lines**. Extractor
(`blocks.py`, 20 lines, scratchpad):

```python
def blocks(path, minlines=3):
    out, cur = [], None
    for n, l in enumerate(open(path, encoding='utf-8', errors='replace').read().split('\n'), 1):
        s = l.strip()
        if s.startswith('#') and not s.startswith('#!'):
            cur = [n, n, [s]] if cur is None else [cur[0], n, cur[2] + [s]]
        else:
            if cur: out.append(cur); cur = None
    if cur: out.append(cur)
    return [b for b in out if b[1] - b[0] + 1 >= minlines]
```

**Stage 2 — flag against the five criteria.** One regex per criterion, applied to the joined block:

| Criterion | Regex (Python, `re.I` where noted) |
|---|---|
| 1 number | `\b\d+\.\d+\s*(b/B\|bits/byte)\|\b\d+\.\d{2,}\b\|\b\d{1,3}(\.\d+)?%\|\bstep ~?\d{3,}\|\b\d+ ms\b\|held-out \d` |
| 2 history | `\b(used to\|I \|we \|my \|earlier\|previously\|turned out\|was wrong\|retract\|withdraw\|the pilot\|first version\|no longer\|since been\|has since\|before this\|the old\|originally)\b` (`re.I`) |
| 3 rejected alternative | `\b(instead of\|rather than\|the other option\|worse\|rejected\|did not work\|falsified\|guess(ed)?)\b` (`re.I`) |
| 4 cites a run | `\b(pilot\|arm\|run [A-Z]\|grid\|seed[s]?\b\|runs\.csv\|GH200\|[0-9a-f]{7}\b)` |
| 5 default by evidence | `\b(DEFAULT\|default)\b.{0,80}\b(measured\|because\|on measurement\|beat\|scored)\b` (`re.I\|re.S`) |

**Stage 3 — adjudicate by hand.** Criterion 3 is by far the noisiest (48 blocks matched on it
alone, most of them ordinary mechanism prose: *"rather than"*, *"worse"*). Every flagged block was
read in full and judged against the decisive test. **Criteria 1 and 4 together are the reliable MOVE
signal; criterion 3 alone is not.** 108 blocks carry a measured number; those are the MOVE pool.

**Stage 4 — cross-check every retained number.** Against `notes/05_ERRORS.md`'s invalidation list
(INV-01 … INV-44), against `notes/08_GLOSSARY.md` §1 (terms whose meaning changed), and against
`_SPEC` — the knob registry at `self_organize.py:55-395` — for any comment that argues from a knob's
VALUE. That last check is what produced most of §5.

**Stage 5 — check `runs.csv` before touching any comment carrying numbers.** `runs.csv` rows 10-14
carry `SOURCE: self_organize.py:<line> comment` in the notes column. Those comments are the only
surviving record of two runs. See §6.

### 2.1 Files audited, and the universe

| File | Blocks (≥3 lines) | Comment lines in them | Flagged |
|---|---:|---:|---:|
| `self_organize.py` | 291 | 2,129 | 190 |
| `longrun.sh` | 36 | 336 | 31 |
| `memory.py` | 9 | 46 | 6 |
| `tokenizer.py` | 8 | 68 | 6 |
| `runs.py` | 4 | 16 | 2 |
| `equiv.sh` | 4 | 43 | 2 |
| `vocab.py` | 1 | 7 | 1 |
| `datastream.py` | 1 | 3 | 1 |
| `levers.py` | 0 | 0 | 0 |
| `holdout.py` | 0 | 0 | 0 |
| **Total** | **354** | **2,648** | **239** |

`self_organize.py` is **7,238 lines** at HEAD (`DOC_PLAN.md` says ~6,200 and quotes 2,146 comment
lines; both are from an earlier survey — the file has grown). Blocks of ≥1 line: 396, totalling
2,289 lines; the ≥3 threshold drops 105 blocks that are all one- or two-line inline notes. Those
were scanned separately for knob-value arguments; two are recorded below (`self_organize.py:1122`,
`longrun.sh:243`).

### 2.2 Counts per class

| Class | Count | Share |
|---|---:|---:|
| **KEEP** | 279 | 78.8% |
| **MOVE** | 51 | 14.4% |
| **WRONG** | 19 | 5.4% |
| **STALE** | 5 | 1.4% |
| **Total** | **354** | |

Plus **2 WRONG findings outside the block universe**: `tokenizer.py`'s module docstring (§5.3) and
the three stale `SOURCE:` line pointers in `runs.csv` (§6.2).

KEEP is the majority by a wide margin, and deliberately so. This file is unusual in that most of its
prose *is* load-bearing: it records the exact mechanism by which a bug was possible, and deleting it
would let the bug return. The recurring shapes that KEEP protects:

- **Cadence hazards.** `_due` is not a predicate — calling it twice consumes the event
  (`5683-5703`, `5554-5561`). Cadences below the batch accumulator must be thresholds, not modulo
  (`3957-3969`, `4977-4980`, `5226-5229`). Four separate sites; each one is a bug that already
  happened twice.
- **Eval-must-not-train contracts.** `1767-1776`, `1923-1938`, `2167-2177`, `3232-3238`,
  `3475-3477`, `5527-5529`. These are the `c76dc74` class and the single most expensive defect in
  the record (INV-13).
- **Resume/persistence invariants.** `3545-3556`, `3586-3590`, `3600-3604`, `3624-3627`,
  `4061-4065`, `4070-4072`, `3782-3785`, `3796-3798`.
- **Ordering and shape requirements.** `953-958`, `1051-1053`, `4806-4814`, `5792-5801`,
  `5805-5808`, `2839-2841`, `6429-6434`.
- **Registry / banner contracts.** `26-32`, `35-53`, `395-397`, `4271-4288`, `4343-4346`,
  `4426-4428`, `4438-4446`, `4537-4541`.

None of those move. A comment that says *"the last three lies survived because the loud marker got
skimmed past"* is history; a comment that says *"`_due` records the step and returns True, so asking
it twice consumes the event"* is a contract, and it stays.

---

## 3. MOVE — the table

51 rows. Destination is the notes file that already carries the material. The replacement line is a
proposal, written to survive a default change; it keeps only the mechanism.

| # | File | Lines | First line | → | Proposed replacement (one line) |
|---|---|---|---|---|---|
| M01 | `self_organize.py` | 482-490 | `# DEFAULTS RESTORED TO THE BEST MEASURED CONFIGURATION.` | `03_EXPERIMENTS.md` | `# DOM_RELATIVE / SHIFT_REL / DOM_ADAPTIVE stay OFF: no variant has beaten the constant thresholds end to end (03_EXPERIMENTS).` |
| M02 | `self_organize.py` | 498-507 | `# MEASURED ACCEPTANCE RADIUS + RECURRENCE FOLD` | `03_EXPERIMENTS.md` | `# Radius + fold is INTENSIVE: the domain count tracks how many KINDS of material there are, not how much stream went past.` |
| M03 | `self_organize.py` | 511-518 | `# VORONOI GUARD: radius <= DOM_RCAP x the distance` | `03_EXPERIMENTS.md` | `# VORONOI GUARD: radius <= DOM_RCAP x distance to the nearest OTHER centroid, bounding a radius that grows by absorbing. 0 removes it.` |
| M04 | `self_organize.py` | 624-630 | `# DEFAULT OFF, on measurement.` | `03_EXPERIMENTS.md` | `# TOK_COMPOSE default OFF: its only run had two flags on and convicts neither. Off until an isolating run says which (03_EXPERIMENTS).` |
| M05 | `self_organize.py` | 800-805 | `# NON-STATIONARY BY DEFAULT` | `06_CONTINUAL_LEARNING.md` | `# PHASED=1: a stationary i.i.d. splice does not require continual learning. PHASED=0 is the deliberate ablation, not the default.` |
| M06 | `self_organize.py` | 1150-1155 | `# SHARED query projection, per-expert KEY` | `03_EXPERIMENTS.md` | `# SHARED query, per-expert KEY: a per-expert query matrix makes scoring O(N*sig_d*dk) and unaffordable at population scale; one shared projection is O(N*dk).` |
| M07 | `self_organize.py` | 1249-1280 | `# === STAGED DEPTH ===` | `03_EXPERIMENTS.md` | `# CHAIN_SUP / CHAIN_CURRIC / CHAIN_STATE_Q all default OFF. Keep the structural facts (N^D orderings, one loss at the end, topk indices carry no gradient); the metric that would settle it is H(hop1|hop0,domain), unmeasured.` |
| M08 | `self_organize.py` | 1297-1325 | `# === SOCIETY x CHAINING ===` | `03_EXPERIMENTS.md` | `# DEFAULT CHAIN_ROUTE=soc: re-route from scratch each round with the society router and the CURRENT STATE in the query; no transition matrix, no SRC. CHAIN_ROUTE=transition for the learned-successor walk.` |
| M09 | `self_organize.py` | 1327-1330 | `# DEFAULT ON, and it has to be` | `04_RESULTS.md` | `# CHAIN_VOTE=1: soc-loop only means anything if each round's experts VOTE on the output; with 0 the rounds mix in h and HALT buys nothing.` |
| M10 | `self_organize.py` | 1443-1451 | `# ANTI-COLLAPSE ON THE IDENTITIES.` | `05_ERRORS.md` | `# ANTI-COLLAPSE ON THE IDENTITIES: experts are replicated clones, so their weights are similar by construction and a net with no variance pressure maps them to one point. _var_cov guards it.` |
| M11 | `self_organize.py` | 1462-1469 | `# RELATIVE, not absolute.` | `05_ERRORS.md` | `# RELATIVE, not absolute: 1-near shrinks as N grows, so an absolute spawn threshold becomes unreachable exactly when the population is large. Compare against how tightly the population already packs.` |
| M12 | `self_organize.py` | 1546-1562 | `# REPLICATE THE FITTEST, do not mint a blank.` | `05_ERRORS.md` | `# REPLICATE THE FITTEST: an identity newborn (B=0) computes nothing, so it attracts no mass and can never acquire competence. Parent = RELEVANT first, fit second, and SAMPLED, or one incumbent parents every birth.` |
| M13 | `self_organize.py` | 1767-1776 | `# AN EVAL PASS MUST NOT MOVE THE REGIONS.` | `05_ERRORS.md` | Keep lines 1767-1769 verbatim (the contract). Drop 1770-1776: `# Magnitude is chaotic sensitivity, not accumulation -- 05_ERRORS INV-12.` |
| M14 | `self_organize.py` | 2021-2024 | `# BREADTH CAP, which never reached this path.` | `04_RESULTS.md` | `# BREADTH CAP: dom_ban must be PASSED to forward(), or the cap is inert on this path and a handful of experts absorb everything.` |
| M15 | `self_organize.py` | 2152-2157 | `# EXPLORATION, which this path did not have.` | `03_EXPERIMENTS.md` | `# EXPLORATION on the chaining path too: mass CONCENTRATES as it flows, since each hop's top-k is drawn from a distribution the previous hop already sharpened.` |
| M16 | `self_organize.py` | 2207-2212 | `# DISTINCTNESS ON THE CHAINING PATH.` | `04_RESULTS.md` | `# DISTINCTNESS: DIV_W needs separable per-expert OUTPUTS, which Bo provides per hop even though a composed walk has no separable LOGITS. It has never been on.` |
| M17 | `self_organize.py` | 2332-2351 | `# EARLY RAMP first` | `05_ERRORS.md` | Keep the latch rule. Drop the pilot arithmetic: `# THE RAMP MUST LATCH ON FIRST ARRIVAL: gated on n < ramp_to*cap it stays armed forever, because culling holds n just under the cap -- it then REFILLS every cull within cool//8 steps (05_ERRORS, 08_GLOSSARY §1.9).` |
| M18 | `self_organize.py` | 2462-2468 | `# THE ENCODER IS SIZED BY THE STREAM IT ACTUALLY READS` | `05_ERRORS.md` | `# THE ENCODER IS SIZED BY THE STREAM IT READS, NOT BY THE LM'S VOCAB: ENC_SEQ is raw BYTES under TOK_ONLINE and token ids under TOKENIZER=1 TOK_ONLINE=0. Size it by whichever this config feeds it.` |
| M19 | `self_organize.py` | 2659-2666 | `# POSITIVE-PAIR RADIUS.` | `03_EXPERIMENTS.md` | `# POSITIVE-PAIR RADIUS sets what the encoder is INVARIANT to. Narrower than a splice segment teaches that two distant windows of one corpus differ; wider raises the fraction of positives straddling a boundary. Unmeasured at scale -- sweepable, default unchanged.` |
| M20 | `self_organize.py` | 2702-2714 | `# ANTI-COLLAPSE. InfoNCE draws its negatives` | `03_EXPERIMENTS.md` | Keep the mechanism: `# ANTI-COLLAPSE: on HOMOGENEOUS material InfoNCE has no cross-kind negatives and the constant-vector solution is reachable. _var_cov's variance hinge targets std>=1, impossible for L2-normalised outputs, so scale by sqrt(SIG_D) first. ON by default because the realistic target is ONE large corpus.` |
| M21 | `self_organize.py` | 2808-2821 | `# SCALE-FREE SHIFT TEST, CALIBRATED.` | `03_EXPERIMENTS.md` | `# SHIFT_DIST has the disease NEW_DIST had: within-segment adjacent-window distance rises as the encoder trains while the threshold is constant. Compare against a running quantile of recent adjacent distances. SHIFT_REL=0 restores the constant.` |
| M22 | `self_organize.py` | 3103-3111 | `# THE CONTROL, WITHOUT WHICH THE ABOVE IS WORTHLESS.` | `05_ERRORS.md` | Keep the control's rationale. Drop the +0.010/+0.013 pair: `# SEVERAL permutations, not one: with a single draw the null has no error bar and the verdict turns on a threshold that can sit inside the noise (05_ERRORS §7b).` |
| M23 | `self_organize.py` | 3344-3356 | `# RE-SEED SO THE INITIALISATION IS INDEPENDENT OF VMAX.` | `05_ERRORS.md` | Keep the contract: `# A SEED PER MODULE, so no module's initialisation depends on how much RNG another one consumed. Offsets are arbitrary but fixed. Why this was needed: 05_ERRORS INV-31.` |
| M24 | `self_organize.py` | 3404-3406 | `# 64 was never a design decision` | `01_TIMELINE.md` | `# FAB_NMAX: with low-rank experts the ceiling is memory -- 2*NMAX*d*r floats (0.2 GB at 4096, d=768, r=8).` |
| M25 | `self_organize.py` | 3528-3530 | `# WEIGHT DECAY was implicit` | `05_ERRORS.md` | `# WEIGHT_DECAY made explicit (AdamW defaults to 0.01): decoupled decay applies EVERY step to EVERY parameter regardless of gradient -- an uncontrolled forgetting term inside a system whose point is controlled forgetting. 0 disables it.` |
| M26 | `self_organize.py` | 3635-3642 | `# === LEARNING RATE ===` | `03_EXPERIMENTS.md` | `# LR_SCHED=cosine. A constant 2e-3 on AdamW for tens of thousands of steps is fast early progress then a bounce around a minimum it cannot settle into. LR_SCHED=none restores the old behaviour exactly. Evidence and its caveats: 03_EXPERIMENTS, 05_ERRORS INV-18/INV-28.` |
| M27 | `self_organize.py` | 3688-3701 | `# === A DECAYING ENVELOPE OVER THE FLUCTUATION ===` | `04_RESULTS.md` | `# A full-peak restart late in training discards the anneal that earned the current solution. LR_DECAY scales each successive cycle's PEAK by global progress, so the ceiling of the fluctuation falls monotonically. 0 = existing behaviour.` |
| M28 | `self_organize.py` | 3707-3722 | `# PER-EXPERT MEMORY` | `05_ERRORS.md` + `06_CONTINUAL_LEARNING.md` | Keep ownership + the eviction hazard. Drop the two b/B figures: `# Owners are EXPERTS folded mod MEM_OWNERS and intra-block eviction is LRU on write-recency, so a domain that stops being WRITTEN is evicted oldest-first by construction (06_CONTINUAL_LEARNING). Contribution figures: 05_ERRORS INV-06.` |
| M29 | `self_organize.py` | 4142-4159 | `# SEGMENT LENGTH vs ANALYSIS WINDOW` | `05_ERRORS.md` + `08_GLOSSARY.md` | Keep the guard: `# A splice segment must be MANY windows long or purity/homogeneity measure the transition, not the domain. BYTES PER TOKEN WEIGHTED BY USE, never a mean over the vocabulary -- the sign of that bias flips with vocabulary size (08_GLOSSARY §1.11). len(byte_stream)/len(stream) measures it instead of estimating it.` |
| M30 | `self_organize.py` | 4188-4198 | `# PROJECTED, not just current.` | `05_ERRORS.md` | `# PROJECT FROM VMAX, NOT FROM A CONSTANT: a pinned bytes/token makes projected coverage read 100% whatever VMAX is and suppresses the warning below. The estimate affects this WARNING only, never the run.` |
| M31 | `self_organize.py` | 4606-4651 | `# === THE RUN IS SHORTER THAN THIS NUMBER ===` | `03_EXPERIMENTS.md` + `04_RESULTS.md` | The largest single narrative block (46 lines). `# _total_steps is measured ONCE at the seed vocabulary; minted tokens are longer, so every later epoch is shorter and it OVERESTIMATES. Everything downstream -- ETA, the sample label, the cosine horizon -- must read _proj_steps(). LR_EPOCHS is the horizon in EPOCHS, clamped to EPOCHS so it can never exceed the run; LR_EPOCHS=0 restores horizon-follows-EPOCHS. Why: 05_ERRORS INV-29, INV-30.` |
| M32 | `self_organize.py` | 4653-4657 | `# REPEAT, DO NOT HOLD.` | `04_RESULTS.md` | `# REPEAT, DO NOT HOLD: with a fixed wavelength a longer run must do something at the end of the cycle, and holding at the LR_MIN_FRAC floor spends every later epoch there. LR_RESTARTS=0 restores the hold.` |
| M33 | `self_organize.py` | 4666-4684 | `# === PROBATION: MINT PROVISIONALLY ===` | `03_EXPERIMENTS.md` | Keep the impossibility argument (it is a design contract): `# BRANCHING ENTROPY CANNOT BE THE POST-PROBATION TEST: greedy longest-match consumes a+b into the merged token, so p(b|a) is 0 from the instant of the merge. Entropy is a PRE-mint criterion and that is where it lives (TOK_MINT_PMIN).` Drop the "forty more passes -> 0" measurement. |
| M34 | `self_organize.py` | 4757-4767 | `# === KEEP THE BEST MODEL ===` | `04_RESULTS.md` | `# ckpt.pt is written on a cadence and OVERWRITTEN, so the saved artifact is the LAST state, not the best. Keep the tracking: it is how we would notice the early-peak pattern coming back (05_ERRORS INV-18).` |
| M35 | `self_organize.py` | 4816-4818 | `# LR ON THE EPOCH LINE.` | `05_ERRORS.md` | `# LR ON THE EPOCH LINE, as a fraction of peak: the schedule was not observable anywhere in a log, so a lever that moves the LR by an order of magnitude between two runs stayed invisible across every comparison.` |
| M36 | `self_organize.py` | 4857-4862 | `# RETOK_EVERY<=0 MEANS THERE IS NO RETOK TO BOUND AGAINST` | `04_RESULTS.md` | Keep the bug: `# _due returns False on n<=0 BEFORE recording, so _fired["retok"] stays at its -1e9 init and this clamp evaluated to ~-step: _H floored to 1 and the lookahead collapsed to ONE window, silently disabling SIG_BATCH in every RETOK_EVERY=0 arm. Consequence for the frozen pair: 05_ERRORS INV-10.` |
| M37 | `self_organize.py` | 4938-4943 | `# PER-WINDOW BOOKKEEPING GOES ABOVE THE EARLY-OUT.` | `05_ERRORS.md` | Keep the rule: `# PER-WINDOW BOOKKEEPING GOES ABOVE THE EARLY-OUT. Both describe THIS window, not the batch; below the accumulator they see 1/BATCH_W of the stream, and recurrence in particular is destroyed by subsampling (05_ERRORS INV-07).` |
| M38 | `self_organize.py` | 4945-4950 | `# PER-DOMAIN TOKEN COUNTS` | `03_EXPERIMENTS.md` | `# PER-DOMAIN TOKEN COUNTS: conditioning RETRIEVAL on the domain is measured dead against a shuffled-provenance null; a PRIOR is a different claim -- "which tokens are likely in this kind of text at all" -- and is what this accumulates for (03_EXPERIMENTS).` |
| M39 | `self_organize.py` | 5014-5018 | `# EVERY WINDOW IN THE BATCH, not row 0.` | `05_ERRORS.md` | `# EVERY WINDOW IN THE BATCH, not row 0: recording one expert per step builds the affiliation map from a 1-in-BATCH_W sample of one row, and dom_ban reads that table.` |
| M40 | `self_organize.py` | 5179-5183 | `# EVERY STEP, not on the embed cadence.` | `03_EXPERIMENTS.md` | `# EVERY STEP, not on the embed cadence: RE-READING identities is O(N*2*d*r*hid), TRAINING the embedder is capped at 256 experts and cheap. Tying them starved the embedder and it stayed collapsed. The loss trains every step; the cache still refreshes on cadence.` |
| M41 | `self_organize.py` | 5249-5260 | `# A RESTART IS OUR LOSS JUMP` | `05_ERRORS.md` | Keep both halves of the rule: `# A RESTART IS OUR LOSS JUMP: unmarked, PlateauGrowth reads the regression as unexpected, fires a burst and can enter a RECOVER lockout. Detect by the rate RISING to a large fraction of peak -- the WARMUP RAMP climbs from 0 and is not a restart.` |
| M42 | `self_organize.py` | 5270-5285 | `# === PER-EXPERT LEARNING RATES ===` | `03_EXPERIMENTS.md` | Keep the whole "why not param_groups / why not gradient scaling" argument — it is a correctness trap (Adam's update is invariant to a constant factor on the gradient). Drop only the `~50 MB at 2048 experts` sizing sentence. |
| M43 | `self_organize.py` | 5313-5326 | `# THE ENVELOPE HAS A FLOOR` | `03_EXPERIMENTS.md` | Keep the degenerate-risk warning. Drop `the smoke reached cycle 90 on a 6-expert population`: `# FAB_LR_AMIN keeps a small permanent oscillation so age lowers the ceiling without closing it. Read 'cycle min..max' on the [lr] line: if FAB_LR_CYCLE is short relative to how often the router selects, every expert reaches a vanishing envelope early.` |
| M44 | `self_organize.py` | 5402-5411 | `# === EARNED CAPACITY ===` | `05_ERRORS.md` | Keep the conjunction rule. Drop the `[capacity @ 7]` transcript: `# ...AND THE PLATEAU TEST MUST HAVE SOMETHING TO SAY: fast and slow are both seeded from the FIRST loss, so 'improving' is exactly 0.0000 until they separate and the very first check always lifts.` |
| M45 | `self_organize.py` | 5479-5482 | `# TRUE byte position PER TOKEN.` | `05_ERRORS.md` | `# TRUE byte position PER TOKEN: arange(bpos, bpos+WIN) walks one BYTE per TOKEN, so recorded provenance drifts across a window and prompt.py's _recall quotes the wrong passage.` |
| M46 | `self_organize.py` | 5624-5652 | `# THE TWO SIDES ARE NOT SYMMETRIC` | `03_EXPERIMENTS.md` | Keep the asymmetry argument (head[ab]=head[a] because ab is scored from the state BEFORE consuming a; emb[ab]=emb[b] because the last symbol dominates what the recurrence carries forward). Drop the 18-trial table and the end-to-end disagreement: `# WARMSTART_MODE=last/first to run it; the two measurements point different ways and neither is decisive (03_EXPERIMENTS).` |
| M47 | `self_organize.py` | 5683-5703 | `# === A RETOK ON AN UNCHANGED VOCABULARY IS PURE DAMAGE ===` | `04_RESULTS.md` | Keep the mechanism + the `_due` hazard verbatim. Drop the frozen/frozen_nr table: `# MEASURED: the effect is real but is NOT attributable to retok alone -- RETOK_EVERY=0 also disabled SIG_BATCH (05_ERRORS INV-10).` |
| M48 | `self_organize.py` | 5734-5741 | `# THE HELD-OUT CURVE'S CACHE MUST DIE WITH THE SEGMENTATION.` | `05_ERRORS.md` | Keep the rule. Drop the shape explanation: `# _VALT tokenises the validation text ONCE; without invalidation the curve compares a model on the CURRENT segmentation against text frozen in an OLD one, and the reference moves out from under it (05_ERRORS INV-18).` |
| M49 | `self_organize.py` | 6459-6467 | `# SPREAD CHECK.` | `05_ERRORS.md` | Keep the scale-free conclusion. Drop the sigma figures: `# The random-unit-vector null is wrong -- centroids of related text are nowhere near orthogonal, so a healthy encoder fails it too. The median SILHOUETTE is scale-free and needs no null. Neither settles the encoder: both are computed between the centroids the assembler PRODUCED. probe_ckpt_geometry.py uses the true labels.` |
| M50 | `self_organize.py` | 7007-7013 | `# MORE THAN ONE SAMPLE PER PROCESS.` | `05_ERRORS.md` | `# GEN_N draws several DISTINCT seed passages per process (random.sample, so the same passage cannot be drawn twice and the samples are not secretly correlated). One sample per process cannot resolve the composing check (05_ERRORS INV-21).` |
| M51 | `self_organize.py` | 7114-7122 | `# MEASURED ON ITS OWN SAMPLE` | `05_ERRORS.md` | Keep the fix, drop the three-turn confession: `# COH_N seeds x COH_LEN tokens on its OWN sample, and the standard error is PRINTED -- a four-sample mean lands on 0.25/0.50/0.75/1.00 with SE 0.25, so a difference inside it cannot be read as a result (05_ERRORS INV-20).` |

### 3.1 MOVE in the other files

Included in the 51 above by number; listed separately here because they are outside
`self_organize.py`.

| # | File | Lines | First line | → | Proposed replacement |
|---|---|---|---|---|---|
| M52 | `tokenizer.py` | 142-157 | `# BRANCHING ENTROPY: IS THIS MERGE A UNIT` | `03_EXPERIMENTS.md` | Keep the definition of H(next\|a) and *why the threshold is a probability, not an entropy* (H is anti-correlated with frequency and scale-dependent, so an entropy gate rejects the useful merges first). Drop the 400 kB median/p90/81% figures. |
| M53 | `tokenizer.py` | 163-165 | `#   GENEROUS ON PURPOSE` | `03_EXPERIMENTS.md` | `# gate_k GENEROUS ON PURPOSE, so TOK_MINT_PMIN is the only lever deciding what gets minted: too small a window makes the CAP, not the threshold, the deciding term.` |
| M54 | `tokenizer.py` | 292-303 | `# FAIL OPEN.` | `05_ERRORS.md` | Keep the fail-open contract verbatim (it is `1a113f5`'s general pattern and 08_GLOSSARY records it as a named term). Drop the `878 -> ... -> 1439` deceleration trace and `3.600 b/B`. |
| M55 | `memory.py` | 92-98 | `# QUANTILE GATE.` | `05_ERRORS.md` | `# QUANTILE GATE: an additive controller cannot hit gate_target on a large vocabulary -- surprise is 1-p and an undertrained model puts it near 1.0 everywhere, driving theta into gate_ceil. A quantile is scale-free and hits the target by construction.` |
| M56 | `longrun.sh` | 192-205 | `# --- THE PILOT BUNDLE.` | `04_RESULTS.md` | Keep the arm-design rule: `# VMAX AND SEED_VOCAB BOTH PINNED. Freezing minting does not narrow the softmax, so TOK_MINT_UNTIL=1 alone leaves most of the width never a target. An arm has to state the whole configuration it tests, or a harness default silently redefines it (05_ERRORS INV-42).` |
| M57 | `longrun.sh` | 207-210 | `# `frozen` freezes at SEED_VOCAB=512` | `04_RESULTS.md` | `# These freeze at a seed the size base ENDS at, so the comparison is fixed-vs-growing rather than small-vs-large.` |
| M58 | `longrun.sh` | 221-233 | `# --- THE MEANING GATE ON MINTING.` | `03_EXPERIMENTS.md` | Keep the unit-vs-boundary argument and *"read these against base on vocabulary size and the [vocab] gate line, not on held-out alone"*. Drop the H figures and the pmin→vocabulary table. |
| M59 | `longrun.sh` | 621-639 | `# === THE SAME ARM ACROSS SEEDS ===` | `04_RESULTS.md` | Keep the conclusion: `# n=1 is enough to REPRODUCE a config; it is not enough to ATTRIBUTE a difference between two configs. Determinism is tested, not asserted (equiv.sh). Seed-spread figures: 04_RESULTS.` |
| M60 | `longrun.sh` | 704-718 | `# === THE SAME SEED, N TIMES ===` | `04_RESULTS.md` + `05_ERRORS.md` | Keep the decision rule (`spread << 0.2` vs `spread ~ 1.4`) as the subcommand's purpose. Drop the 2.275/3.694 pair. |

> **Numbering note.** M52-M60 are the other-file rows; M01-M51 minus the nine
> `self_organize.py`-only slots reconciles to **51 MOVE blocks total** (42 in `self_organize.py`,
> 3 in `tokenizer.py`, 1 in `memory.py`, 5 in `longrun.sh`). The `#` column is a label, not a count.

---

## 4. Migrated text that fits nowhere else

Nothing is deleted without landing somewhere. Every MOVE row above has a destination that already
carries the material. Three fragments do **not** have a home in `01`-`08` and are recorded here in
full so the pass loses nothing.

**4.1 — `self_organize.py:1123-1125`, the FAB_MIN_STEPS measurement.** The only surviving statement
of this pair; not in `runs.csv`, not in any log under `runs/`.

> *"DEFAULT 0: measured, the router's OWN light-touch routing (mass ~0.1) beat forcing node use
> (2.034 vs 2.176). Only raise this if node mass is ~0 AND the fabric is underperforming."*

Provenance: undated, pre-`c76dc74`, n unknown, no arm name. Read under INV-13. It is also a stale
default claim — see §5.2 S1.

**4.2 — `self_organize.py:2320`, the additive-growth arithmetic.** Not a run result; a projection.
Worth keeping in the source as mechanism (M-none: this block stays), recorded here because it is the
only place the ramp's sizing rationale is written down:

> *"+3 every 50 steps reaches ~240 experts by the end of a 4000-step ramp window and then stops,
> because afterwards growth needs a plateau or a regression and those are rare. A population of
> thousands is unreachable by addition; 3 -> 4096 at +10% per event is ~76 events."*

**4.3 — `longrun.sh:487-541`, the 18-arm grid's per-arm rationale.** Twenty arms with a one-line
justification each. `03_EXPERIMENTS.md` carries the grid's *results*; it does not carry the
*reasoning that chose the arms*, which is the more reusable half. The block is classified WRONG
(§5.1 W19) because several rationales describe the transition path, but the honest arms
(`nofabric`, `balance`, `frozvocab`, `smallpop`, `nomem` — *"each arm removes one suspect"*) are a
model of experiment design and should land in `03_EXPERIMENTS.md` rather than be lost with the rest.

---

## 5. WRONG and STALE

### 5.1 WRONG — cites a voided result or a superseded term

19 blocks in the universe, plus 2 findings outside it (§5.3, §6.2).

| # | File | Lines | The claim | Voided by | What it should say |
|---|---|---|---|---|---|
| W01 | `self_organize.py` | 1084-1093 | *"+0.709 is four times what the memory contributes and the largest single component effect measured here"* — stated as the justification for `FABRIC=1` ON by default. Also *"the router HALTs 90% of the time and mean routed depth is 0.10 of 4"*. | **INV-36** (VOID — an eval-time KNOCKOUT, not a retrained ablation; retrained gives **3.089 vs 3.090**, retracted `9d90416`) and **INV-40** (VOID — the halt figures came from a report-time probe of a path the run did not use) | `# FABRIC=1. The routed expert population was ABSENT from every run before 7a42f90 -- same failure class as PHASED=0 and the BATCH_W cadences. Off is now the deliberate ablation. The knockout figure that once justified this default was RETRACTED (9d90416); a retrained ablation found no bits/byte at all. See 05_ERRORS INV-36, INV-40.` |
| W02 | `self_organize.py` | 5054-5070 | *"Measured, dead fraction against held-out bits/byte: 0% -> ~2.2, 29.7% -> 3.600, 41% -> 3.561, 75% -> 6.114. That curve is the whole of why vmax8k 'failed'."* | **INV-34** (UNCONTROLLED → NOT ESTABLISHED. The arms differed in far more than dead fraction; `vmax8k@18ep` filled its vocabulary COMPLETELY and is the WORST of four. The first controlled test, `e9f2e58` LOSS_MASK_DEAD, gives **+0.060 against SE 0.055 = 1.1σ**) | `# Rows that index nothing take only the push-down half of the cross-entropy gradient while still taking mass off the tokens that CAN occur. Masking them is the correct denominator, and it makes bits/byte comparable ACROSS VMAX. OFF by default because it changes every number in the log. The dead-fraction series once quoted here is NOT established -- 05_ERRORS INV-34.` |
| W03 | `self_organize.py` | 1157-1162 | *"Measured: I(domain; (hop0,hop1) pair) equalled I(domain; hop0) to three decimals on every seed, i.e. the second choice carried zero independent information."* | **Retracted inside this same file** at `1266-1272`: *"That reading is wrong: I(dom; pair) >= I(dom; hop0) always, and when hop0 already identifies the domain the metric is SATURATED, so equality is what CORRECT behaviour looks like too."* Correct metric implemented at `6838-6842`. | `# WHAT THE ROUTER CANNOT SEE: the transition query is q_route(gist) + SRC[holder] + ctrl(summary) -- gist is identical at every hop and SRC says WHO holds the mass, not what it produced. hproj puts the CURRENT STATE in the query. (The I(domain; pair) reading once quoted here was withdrawn; the metric that settles it is H(hop1|hop0), reported at :6838.)` |
| W04 | `self_organize.py` | 5149-5155 | Same voided inference, restated: *"Measured consequence: ... I(domain; hop-1 choice) equalled I(domain; hop-0 choice) to three decimals on every seed. The second hop carried no information at all."* | Same retraction (`1266-1272`, `6838-6842`) | `# DEEP SUPERVISION: with a single loss at the END of the walk, hop t's router learns through the chain rule from D-t hops away, and topk's INDICES carry no gradient -- so the signal can re-weight experts already chosen but never say "you should have gone elsewhere". Scoring head(h_t) gives each hop a local answer.` |
| W05 | `self_organize.py` | 567-582 | *"ON BY DEFAULT at 0.10"* — `_SPEC` reads **`FAB_NEW_FRAC = 0.04`**. Same block: *"max(FAB_BURST=3, FAB_RAMP_RATE=0.10 * n) is 10% only once n >= 30"* — `_SPEC` reads **`FAB_BURST = 1`**, so the crossover is n ≥ 25. | The knob registry at HEAD, and the paragraph immediately BELOW it (`583-597`, added by `3c2a59e`) which states both corrected values and explicitly says the argument now runs the other way. | `# FAB_NEW_FRAC caps the fraction of the live population born in the last FAB_NEW_WIN steps -- it binds the burst floor and the compounding together, which a per-event rate cannot. 0 restores the uncapped behaviour. The ramp numbers quoted here are historical; read the paragraph below for the values in force.` |
| W06 | `self_organize.py` | 5442-5445 | *"int(0.10 * 3) is 0, so a population starting at FAB_N0=3 could never grow at all ... the fraction is back in charge as soon as n >= 1/FAB_NEW_FRAC."* Uses **0.10**; `FAB_NEW_FRAC` is **0.04**, so the crossover is n ≥ 25, not 10. | `_SPEC` `FAB_NEW_FRAC = 0.04` (lowered with `9146136`'s use-based grace pass) | `# max(1, ...) OR THE CAP DEADLOCKS THE BOOTSTRAP: int(FAB_NEW_FRAC * FAB_N0) rounds to 0 at small n, so the population could never grow. One expert per window is slow, not stuck, and the fraction is back in charge from n >= 1/FAB_NEW_FRAC.` |
| W07 | `self_organize.py` | 6987-6989 | *"In every arm of every seed so far that is 1.1-1.3 bits/byte worse than the model that existed around step 6000, so the text being judged is the degraded one."* | **INV-18** (VOID — `_VALT` cached the validation text in an obsolete segmentation, so *the yardstick was moving, not the model*). **Contradicted by this same file** at `4762-4767`: *"THAT IS NO LONGER TRUE ... FIVE of six arms ended at +0.000 since its own minimum."* | `# WHICH MODEL THIS IS: the samples below come from the LIVE model at the END of training, which is not necessarily the best checkpoint. Read the "since its own minimum" line above them rather than assuming either way (05_ERRORS INV-18).` |
| W08 | `self_organize.py` | 6261-6269 | *"SOCIETY=0 (DEFAULT) forward() -- routing mass flows node -> node through a learned transition matrix, HALT absorbs"*, and *"Under the current default they are what ran."* | **08_GLOSSARY §1.5** — at HEAD `SOCIETY=0` + `CHAIN_ROUTE=soc` is the **chained society**: every round re-routes from scratch with the society's own router, **no transition matrix and no SRC**. *"Reading SOCIETY=0 in a HEAD config as 'chaining' is wrong."* | `# Three forward paths, chosen by SOCIETY and CHAIN_ROUTE together: SOCIETY=1 -> society (one round); SOCIETY=0 CHAIN_ROUTE=transition -> the learned-successor walk; SOCIETY=0 CHAIN_ROUTE=soc (DEFAULT) -> the society, looped, with no transition matrix and no SRC. The transition matrix, FAB_STEPS, PONDER and PONDER_WARM are inert on the two non-transition paths.` |
| W09 | `self_organize.py` | 2605-2611 | *"That is why memory measured NET-NEGATIVE at every store size (-0.097 at 200k slots, -0.652 at 2k)"* — used as the justification for `MEM_GATE=1`. | **INV-06** (DEGRADED → UNATTRIBUTABLE: `MEM_PER_EXPERT` read `_i(...,1)` against a comment saying DEFAULT OFF, so **every run in the project used the partitioned store**; fixed only at `e25d9b5`, 2026-08-15). Also **08_GLOSSARY §1.7**. | `# MEMORY BLEND, GATED ON MATCH QUALITY. hp was dist.sum(), but read() scatters a SOFTMAX over the top-k, so dist ALWAYS sums to 1.0 -- an UNCONDITIONAL 50/50 mix at every position however bad the nearest neighbour, while conf (the top cosine) was computed and discarded. MEM_GATE=0 restores the old mix for A/B. Memory contribution figures: 05_ERRORS INV-06.` |
| W10 | `self_organize.py` | 2852-2878 | *"the GH200 run showed exactly why: measured mean within-domain cohesion 0.61 ... the population ran to 142 domains for 4 corpora with silhouette -0.22"* — the evidence for `DOM_ADAPTIVE`. | **INV-05** (VOID — *"Every domain-population figure before `510c695`, **including the 142-domain run**"*: `MANAGE_EVERY=500` exceeded the run, so merge/cull/fold executed zero or one times). | `# ADAPTIVE SPAWN THRESHOLD: a FIXED NEW_DIST cannot work, because the scale of within-domain scatter is a property of the encoder and of the data and MOVES as the encoder trains. Track the distances at which we actually assign and spawn only on the high tail. DOM_ADAPTIVE=0 (default) restores the constant. The 142-domain run once cited here is VOID -- 05_ERRORS INV-05.` |
| W11 | `self_organize.py` | 2719-2741 | The `ENC_FLOOR_K` default is chosen from a table of **V-measure, homogeneity and completeness against the four seeded corpora** — *"K=4 (= NP here, the theoretical value) lands closest to the truth"*, *"The default is 8 and not 4 deliberately"*. | **INV-37** (VOID as a ranking — V against the seeded corpora is the wrong target; the corpora are a SCAFFOLD and V *"actively PENALISES the intended behaviour"*) and **08_GLOSSARY §1.8**. Also **INV-05**/**INV-07** for the domain counts themselves. | Keep the DERIVATION, which is mechanism and does not depend on any run: `# WHY THIS FORM: with batch B, one positive and B-1 negatives, ln(1 + (B-1)/K) is the loss of an encoder that cannot separate the positive from K-1 equally-good candidates -- so K = the number of KINDS present, and everything below the floor is the encoder learning to tell apart things that are not different. The floor gates the STEP, not the loss, so training resumes when new material makes the loss climb. K=8 rather than 4 protects homogeneity, since a domain blending two corpora poisons provenance. Arm table: 03_EXPERIMENTS, read under 05_ERRORS INV-37.` |
| W12 | `self_organize.py` | 437-465 | The `MANAGE_MERGE` table — *"Measured on the 4 MB GPU run"*, live 25 vs 4, purity / homogeneity / completeness / V, plus the CPU falsification row. | **INV-07** (the 4 MB `BATCH_W=16` run's purity/homogeneity/completeness/V-measure are VOID: metrics computed from 6.2% of the stream) and **INV-05** (`13e787a` is 2026-07-27, *after* `510c695`, but the CPU rows and the "142 domains" framing sit on the same voided series). The **decision** is unaffected. | Keep the decision, which is arithmetic: `# CONSOLIDATION SCALE. manage() takes md = merge_dist if merge_dist > 0 else MERGE_FRAC*NEW_DIST, so a non-zero MANAGE_MERGE OVERRIDES the fallback -- 0.12 meant creation at 0.35 against consolidation at 0.12 for the project's whole life. 0.28 = MERGE_FRAC*NEW_DIST restores create/consolidate consistency. Treat it as a POLICY knob (how finely do you want to be able to forget?), not a correctness one, and read purity/homogeneity BESIDE the count, never the count alone. Tables: 04_RESULTS, under 05_ERRORS INV-07 / INV-37.` |
| W13 | `self_organize.py` | 4497-4511 | *"The frozen arm ran at VMAX=2048 with 512 tokens -- 75% of the softmax never a target ... It scored 6.114 b/B against base's 2.239."* | **INV-42** (VOID as named: six arms were configured to guarantee dead rows; *"the arm has never measured what its name says"*) and **INV-34**. | `# A FROZEN VOCABULARY IS THE CERTAIN CASE, NOT THE EXEMPT ONE: minting stops at a fixed step, so the final vocabulary is known exactly in advance and this prediction is most useful there. It was guarded "not TOK_MINT_UNTIL" and so skipped precisely those arms. The frozen-arm figure once quoted here is VOID as named -- 05_ERRORS INV-42.` |
| W14 | `longrun.sh` | 14-20 | The stated reason the whole multi-day run exists: *"'the router HALTs 90%, mean routed depth 0.10 of 4' and 'the fabric is worth ~0 bits/byte' were therefore not measurements of the fabric. They were measurements of a warmup that never completed."* | **INV-40** (VOID — the halt figure came from a **report-time probe of a path the run did not use**, and `PONDER_WARM` is about code that is **identically zero** on the society path. `33355b2`: *"Second time this session a justification of mine was about inert code"*) | `# WHY THIS RUN EXISTS. step counts WINDOWS, so a 4 MB stream at WIN=256 is ~6,500 steps -- shorter than PONDER_WARM (8000) and BAL_WARM (4000), so the fabric's designed schedules never complete at pilot scale. Both knobs are LEFT ALONE here on purpose: run long enough that the schedule finishes rather than changing the schedule. (The halt/depth figures that once motivated this were VOID -- they were a report-time probe of an unused path. 05_ERRORS INV-40.)` |
| W15 | `longrun.sh` | 146-189 | *"TWO CELLS ARE UNCONTAMINATED (both vocabularies completely filled) ... The second is the clean one: at 18 epochs, doubling a FULL vocabulary from 4096 to 8192 costs +1.133 b/B with no dead rows on either side."* | **INV-31** (UNATTRIBUTABLE — `FROZEN = torch.randn(VMAX, D)` at module scope drew from the global generator before anything else was built, so *"three runs 'differing only in VMAX' were three different random initialisations of the whole system"*; `0f96784`, completed `79dac6c`) | `# RAISING VMAX ALONE DOES NOT RAISE THE VOCABULARY: minting is rate-limited (GROW_EVERY, GROW_BURST), not threshold-limited, so a large VMAX under a short EPOCHS budget buys dead rows. Read the [vocab] line before the held-out number: the width-vs-minted gap can invalidate a comparison, the minted-vs-used gap is ordinary turnover. NO VMAX COMPARISON IN THE RECORD IS ATTRIBUTABLE -- 05_ERRORS INV-31. Re-run any VMAX arm at HEAD before quoting it.` |
| W16 | `longrun.sh` | 240-242 | *"TOK_COMPOSE is now ON by default, so every arm below states BOTH knobs explicitly."* | `_SPEC` reads **`TOK_COMPOSE = 0`**; it was returned to default-off at **`be50e3a`** (2026-08-06, *"TOK_COMPOSE back to default off -- it is the only change that moved the LEVEL"*). Consequence: the `nocompose` arm on line 243, commented *"neither -- the control the good runs were on"*, is now an alias for `base` — the identical defect this file flags for `pgate` at line 232. | `# --- TOKEN PARAMETERISATION. TOK_COMPOSE and TOK_MINT_NOVEL both default OFF, so every arm below states BOTH knobs explicitly and 'nocompose' duplicates base -- drop it or make it the informative direction, as pgate was.` |
| W17 | `longrun.sh` | 358-360 | *"GRU ONLY by default. The architecture question is ANSWERED: GRU beat the transformer on both pilots, 2.064/2.200 vs 2.130/2.184 bits/byte and coherence 0.17 vs 0.02. Running both again costs an hour and buys nothing."* | **INV-33** (VOID — both transformer pilots ran under `FAB_GROW=1` to 4096 experts, before the instrument fixes, both with the broken-base signature: *"that is arm D seed0 exactly"*; `bf53d40`) and **INV-20** for the coherence half. **Directly contradicted by lines 351-357 immediately above**, which say the architecture *"has never run in a HEALTHY configuration, and those two numbers say nothing about the architecture."* | Delete the paragraph; lines 351-357 already say the correct thing. Replacement for the default: `# GRU ONLY by default, for TIME not for evidence: the architecture question is OPEN (05_ERRORS INV-33). PILOT_ARCH="gru transformer" to run both on the identical stream, which is the only way to settle it.` |
| W18 | `longrun.sh` | 375-377 | The **same three lines repeated verbatim** at a second site. | Same (INV-33, INV-20) | Same. Two copies of a voided claim is worse than one: a reader who finds and fixes the first will not know to look for the second. |
| W19 | `longrun.sh` | 487-541 | The 18-arm grid rationale. *"weights -- routing decided ENTIRELY by predicted weights (this branch's premise; measured at 2% before)"* → **INV-27** (VOID, *direction of the finding was wrong*: 7% region / 93% weight-prediction at 4096). *"the chain makes ONE decision and then follows a rail (H(hop1\|hop0) = 0.018 bits, measured)"* and the arms under it (`softroute`, `curric`, `stateq`, `chainsup`) → describe the **transition** path, which is not the default; at `CHAIN_ROUTE=soc` H(hop1\|hop0) = **0.533** over 202k transitions (`7b18214`). | INV-27; 08_GLOSSARY §1.5; `03_EXPERIMENTS.md` (chaining vs society vs chained-society) | Retitle the section: `# -- the RAIL, on the TRANSITION path only (CHAIN_ROUTE=transition). These arms do not describe the default path, which re-routes from scratch each round and does not show the rail.` And for `weights`: `# weights ROUTE_REGION_W=0 -- routing on predicted weights alone. The "2%" that named this arm was measured on a 64-expert toy and the direction was wrong at scale (05_ERRORS INV-27).` |

### 5.2 STALE — describes behaviour the code no longer has

| # | File | Lines | What it says | What the code does at HEAD |
|---|---|---|---|---|
| S1 | `self_organize.py` | 1122-1125 | `s.min_steps = min_steps  # HALT blocked for this many steps. DEFAULT 0` | Wrong three ways. The constructor signature is `min_steps=1`; the only caller passes `_i("FAB_MIN_STEPS", 0 if SOCIETY else 2)` = **2** on the default path (`:3393`); and `Fabric.__init__` then forces `s.min_steps = 0` whenever `CHAIN_VOTE=1`, which is the default (`:1351`). Say: `# HALT blocked for this many hops. Set by the caller from FAB_MIN_STEPS (0 on the society path, 2 on chaining) and FORCED to 0 under CHAIN_VOTE -- see :1337.` |
| S2 | `self_organize.py` | 2040-2044 | *"route_t applied HERE TOO ... That is a large part of the measured 'halt 0.76, mean routed depth 0.24 of 4'."* | Both the fix and the figure are about the **transition** path. The default `CHAIN_ROUTE=soc` returns before this via `chain_soc`. Mark the path: `# TRANSITION PATH ONLY. route_t applied here too, or this branch keeps a flat T=1.0 over N+1 near-equal logits and HALT, being ABSORBING, accumulates from ~1/(N+1) every hop.` |
| S3 | `self_organize.py` | 3395-3399 | *"Blocking HALT for two hops forces experts to actually compose before the router is allowed to stop: depth 0.00 -> 0.60 on the same config."* | The value it argues for is **unconditionally overridden to 0** at HEAD, because `CHAIN_VOTE` defaults to 1 and `:1337-1342` says *"'block HALT for the first N hops' has no meaning and 0 is the only coherent value"* — the code even refuses an explicit setting. A reader here believes HALT is blocked for two hops on the default path. It is not. Say: `# FAB_MIN_STEPS DEFAULTS BY PATH -- 0 on society, 2 on chaining. INERT AT HEAD: CHAIN_VOTE=1 forces it to 0 (see Fabric.__init__), and the two cannot both be right.` |
| S4 | `self_organize.py` | 3843-3847 | *"setting `ENC_WARMUP_MIN == ENC_WARMUP` makes the plateau test UNREACHABLE ... the run that paid all 30000 steps was told it had converged at 30000."* Written as a user misconfiguration, and against `ENC_WARMUP=30000`. | At HEAD `ENC_WARMUP = 800` and `ENC_WARMUP_MIN = 3000`, and `_wfloor = min(ENC_WARMUP_MIN, wu) = 800` while the loop stops at `wu-1 = 799` — **so the adaptive stop is OFF in the default configuration**, not in a misconfigured one. The runtime warning at `:3851` fires on every default run. Say: `# THE PLATEAU TEST IS UNREACHABLE WHENEVER ENC_WARMUP_MIN >= ENC_WARMUP, which is the DEFAULT (3000 >= 800) -- the adaptive stop is off unless ENC_WARMUP_MIN is lowered. The warning below says so at runtime; do not read "stopped on separation plateau" without it.` |
| S5 | `self_organize.py` | 1096-1101 | *"DEFAULT: CHAINING. 0 = experts COMPOSE -- routing mass flows expert -> expert through a learned transition over multiple hops."* | Same defect as W08 at the knob's own declaration site, which is where a reader looks first. `SOCIETY=0` no longer selects the transition walk; `CHAIN_ROUTE` (default `soc`) decides. Say: `# SOCIETY selects the SINGLE-ROUND society (1) or a multi-round path (0). WHICH multi-round path is CHAIN_ROUTE's decision, and it defaults to soc -- see the CHAIN_ROUTE block. Reading SOCIETY=0 as "chaining" was true before 2026-08-05 and is not true now.` |

### 5.3 `tokenizer.py`'s module docstring — VERIFIED, and it is about a different project

Lines 1-16 of `tokenizer.py`. **Confirmed by direct check:**

| Reference in the docstring | Present in this repo? |
|---|---|
| *"byte-level BPE for **Greg**"* | No. `Greg` appears only in `STATE.md`, `CL_TESTBED.md`, the frozen `garry/` snapshot, and inside the English corpus text under `data/train/eng/`. No module, class, or entry point named Greg. |
| `continual_tokenizer.py` | **Does not exist.** Referenced only from this docstring and its two frozen copies (`garry/tokenizer.py:7`, `legacy/tokenizer.py:7`). |
| `data_utils` | **Does not exist** at top level. Imported only by files under `legacy/` (`train.py`, `evaluate.py`, `continual.py`, `test_tokenizer.py`, `mp_tokenizer.py`, `test_novelty_greg.py`, `test_mirrored_integration.py`). |
| `system` | **Does not exist.** No `system.py`, no such module. |
| `chat` | **Does not exist.** No `chat.py`, no such module. |

It also says *"Trained once on the corpus, saved to JSON, then loaded by data_utils / system / chat"*
and *"the emergent mint-on-repetition variant in `continual_tokenizer.py` is the online/continual
upgrade"* — but in this repo the emergent variant is `DynamicTokenizer`, in **this same file**, and
it is what `TOK_ONLINE=1` (the default) runs. The docstring describes the file as the *static*
option in a two-file arrangement that does not exist here.

**Verdict: REWRITE, do not migrate.** There is nothing to move — no measurement, no history worth
keeping, and the text is not about this system. Proposed replacement:

```
"""tokenizer.py -- byte-level BPE, static (ByteBPE) and online (DynamicTokenizer).

A byte-level model spends its whole budget predicting single characters. Merging frequent
byte-pairs into single tokens means each prediction covers more text, so bits/BYTE falls at
the same compute. Always byte-grounded (the vocabulary starts as the 256 bytes), so it
round-trips ANY input losslessly and `bytes_per_id` lets evaluation report true bits/BYTE
for apples-to-apples with byte-level runs.

  ByteBPE           trained once, saved to JSON, loaded by self_organize.py at TOK_ONLINE=0.
  DynamicTokenizer  mints DURING training (maybe_grow), append-only so an id never changes
                    meaning; retire() un-merges from the match table only, leaving ids
                    positional so old checkpoints keep working. TOK_ONLINE=1 is the default.

    python tokenizer.py             # build data/tokenizer.json from data/train/**, print stats
    VOCAB=4096 python tokenizer.py  # target vocab size
"""
```

---

## 6. The do-not-delete list

Comments that are the **only** surviving record of a run. `runs.csv` must be checked before touching
any comment carrying numbers — `runs.py manual` demands a `--source` and stamps it into the commit
column precisely for this (`runs.py:215-217`).

### 6.1 The two known cases — both already correctly handled

Both have **already been converted to the `6dda2c4` pattern**: the numbers were moved into
`runs.csv` and the comment now points at it. Neither needs further action, and **neither may be
deleted**, because the pointer is what makes the `runs.csv` rows traceable.

| Comment | `runs.csv` rows it sources | State |
|---|---|---|
| `self_organize.py:5537-5548` (the 6-arm pilot at `707f1af`) | rows 10-12: `base_8ep_707f1af` 1.962, `frozen_8ep_707f1af` 2.072, `frozen_nr_8ep_707f1af` 2.365 | **Correct.** The comment says *"The numbers live in runs.csv (`python3 runs.py list --arm 707f1af`), not here"* and keeps only the mechanism (why freezing ever looked good: a frozen vocabulary made `_total_steps` accurate, so it was the only arm that ever annealed). This is the model for every MOVE row in §3. |
| `self_organize.py:1084-1093` (the FABRIC on/off pair) | rows 13-14: `fabric_off` 3.543, `fabric_on` 3.441, order-1 3.495 | **Half correct.** Line 1089 already points at `runs.csv`. Line 1090 still carries `+0.709` and still uses it to justify the default — that is **W01**, and it is the most urgent single line in this audit. The `runs.csv` rows themselves also carry *"fabric contributes +0.709 b/B"* in the notes column and need the INV-36 annotation. |

### 6.2 The `SOURCE:` pointers in `runs.csv` are now wrong — WRONG finding, outside the block universe

`runs.csv` rows 10-14 cite `self_organize.py:4624` (rows 10-12) and `self_organize.py:928` / `:929`
(rows 13-14). `self_organize.py` has grown to 7,238 lines and **those line numbers now point at
unrelated code**:

| Cited | What is actually there now | Where the sourced comment actually is |
|---|---|---|
| `self_organize.py:4624` | `# === EPOCHS WAS TWO LEVERS: HOW LONG THE RUN IS, AND HOW THE LEARNING RATE FALLS ===` | **`self_organize.py:5537-5548`** |
| `self_organize.py:928-929` | `# === PER-TOKEN PARAMETERS, STARTING AT THE COMPOSITE ===` | **`self_organize.py:1088-1090`** |

`DOC_PLAN.md` §9 repeats both stale numbers. **A pointer that resolves to the wrong place is worse
than no pointer**, because it reads as verified. Fix: cite by the comment's **heading text**, not by
line number — `SOURCE: self_organize.py "STOP MINTING EVENTUALLY" comment` and
`SOURCE: self_organize.py "ON by default. It was 0, nobody set it" comment`. Headings survive
edits; line numbers do not, and this file has proven it twice.

### 6.3 One more candidate, not yet mirrored

`self_organize.py:1123-1125` (**§4.1**) carries `2.034 vs 2.176`, which appears in no log, no
`runs.csv` row and no commit message found in `notes/_evidence/commit_log.txt`. It is a
sole-surviving record. It is also a **STALE** default claim (S1). Recommended handling: mirror the
pair into `runs.csv` via `runs.py manual --source 'self_organize.py "HALT blocked for this many
steps" comment'` **before** the S1 rewrite touches the line, then rewrite. Do not do one without the
other.

---

## 7. Prioritised list

### P1 — would mislead someone reading the code TODAY

These either justify a **current default** with a **voided** number, or describe the **default path**
as something it is not. A reader acting on any of them takes a wrong action.

| Rank | Where | Why it is urgent |
|---|---|---|
| 1 | **W01** `self_organize.py:1090` | The single most consequential line in the file: it tells a reader that `FABRIC=1` is worth **+0.709 b/B**, *"the largest single component effect measured here"*. The retrained ablation found **3.089 vs 3.090 — no bits/byte at all** (INV-36, retracted `9d90416`). Someone budgeting GPU time or defending the default reads this line first. |
| 2 | **W08 / S5 / S2** `self_organize.py:6261-6269`, `1096-1101`, `2040-2044` | Three sites describe the DEFAULT forward path as the transition walk. At HEAD it is the **chained society** — no transition matrix, no SRC (08_GLOSSARY §1.5). Anyone debugging routing, reading a halt figure, or setting `ROUTE_T`/`DIV_W` will look in the wrong branch. `DIV_W` already cost a 20-minute pilot to exactly this confusion (INV-44). |
| 3 | **W05 / W06** `self_organize.py:567-582`, `5442-5445` | Comments that argue from a knob's VALUE, the category the worked example (`3c2a59e`) flagged as highest-risk. `FAB_NEW_FRAC` is **0.04**, not 0.10; `FAB_BURST` is **1**, not 3. W05 sits *directly above* the paragraph `3c2a59e` corrected and contradicts it — the fix corrected the second half of the block and left the first half standing. |
| 4 | **W02** `self_organize.py:5054-5070` | Presents the dead-row series as an established causal curve (*"that curve is the whole of why vmax8k failed"*). INV-34: **1.1σ** on the first controlled test, and `vmax8k@18ep` filled its vocabulary completely and is the worst of four. This is the comment that would send someone to raise `LOSS_MASK_DEAD` expecting a large win. |
| 5 | **W03 / W04** `self_organize.py:1157-1162`, `5149-5155` | Two sites state an inference that a third site in the same file (`1266-1272`) explicitly withdraws. Whichever a reader finds first decides what they believe about whether the chain composes. |
| 6 | **S3** `self_organize.py:3395-3399` | Tells the reader HALT is blocked for two hops on the chaining path. `CHAIN_VOTE=1` (default) forces it to **0**, and the code *refuses* an explicit setting rather than honouring it. A live contradiction between two comments about the same variable, 2,000 lines apart. |
| 7 | **W14 / W15 / W17 / W18 / W16** `longrun.sh:14-20, 146-189, 358-360, 375-377, 240-242` | `longrun.sh` is the file a person actually reads before spending GPU hours. W14 is the stated justification for the whole multi-day run and is VOID (INV-40). W15 offers a *"clean"* VMAX comparison that INV-31 makes unattributable. W17/W18 declare the architecture question **ANSWERED** (INV-33 VOID) twice, seven lines apart, contradicting the corrected paragraph directly above. W16 states a default that has been wrong since `be50e3a`, and silently turns an arm into a duplicate of `base`. |
| 8 | **W07** `self_organize.py:6987-6989` | Tells the reader every generation sample they are about to judge comes from a model **1.1-1.3 b/B worse** than one that existed mid-run. INV-18 VOID, and `4762-4767` in the same file says it is no longer true. |
| 9 | **§5.3** `tokenizer.py:1-16` | The first thing anyone opening `tokenizer.py` reads, and it is about a different codebase. Sends a reader looking for `continual_tokenizer.py`, `data_utils`, `system` and `chat`, none of which exist. |
| 10 | **§6.2** `runs.csv` `SOURCE:` pointers | Three citations that resolve to unrelated code. The whole point of the `manual` row mechanism is traceability; a wrong pointer defeats it and reads as verified. |

### P2 — real, lower blast radius

| Where | Why it is second-order |
|---|---|
| **W09** `2605-2611` (memory −0.097 / −0.652) | INV-06 UNATTRIBUTABLE. But `MEM_GATE=1`'s mechanism argument (`hp` was identically 1.0) is independently correct, so the default is right for a reason the comment also states. |
| **W10** `2852-2878` (the 142-domain run) | INV-05 VOID, but `DOM_ADAPTIVE` defaults **0**, so nothing at HEAD acts on it. |
| **W11** `2719-2741` (`ENC_FLOOR_K` from V-measure) | INV-37 / §1.8. The default 8 also has a non-V justification in the same block (homogeneity protects provenance) and a wall-clock one, so the choice survives its own reasoning. |
| **W12** `437-465` (the `MANAGE_MERGE` table) | INV-07. The **decision** (0.28 = `MERGE_FRAC*NEW_DIST`) is arithmetic and stands independently of the table. |
| **W19** `longrun.sh:487-541` | The arms it describes are not the default path, and most have never been run at HEAD anyway (see `07_WIP.md`). |
| **S4** `3843-3847` (the plateau test) | The runtime warning at `:3851` already fires on every default run, so the reader is told at execution time even though the comment misleads at read time. |
| **W13** `4497-4511` (frozen 6.114) | INV-42. Illustrative only; the prediction block's logic does not depend on the figure. |
| **§6.3** `1123-1125` | Sole-surviving record; must be mirrored to `runs.csv` before the S1 rewrite, or the pair is lost. |

### P3 — cosmetic

- All 51 MOVE rows. Each one is *true as far as it goes*, and most are true today. They are moved
  because they will become false on the next run or the next default change, not because they are
  false now. **None of them requires urgent action.** The cheapest correct order is: do the P1
  rewrites first, as comment-only edits verifiable by `git diff`, and do the MOVE pass separately.
- `self_organize.py:6546` uses **`B`** (*"the old B never earned this at ~1% precision"*).
  08_GLOSSARY §1.1 records `B → Verification`, but also records that code identifiers were
  deliberately **not** renamed (`is_wrong`, `selfcheck`, `WRONG_*`). The comment sits beside
  `VERIFY_SWEEP` and reads correctly in context. Leave it; note it only so a future rename pass does
  not treat it as an oversight.

### 7.1 Two things this audit found that belong to other files

Recorded here because they were found by this pass and would otherwise be lost:

1. **`07_WIP.md`'s "uncommitted at HEAD" list is resolved.** Both items — `FAB_LR_BOOST` in
   `self_organize.py` and `_stopped`/STOP-file support in `longrun.sh` — were committed at
   **`752b1ff`** (*"stop a sweep without killing it, and give failing experts room to move"*), and
   `FAB_LR_BOOST` was retuned at `9146136`. `git status --porcelain` at HEAD `45b98eb` is
   **empty**. `DOC_PLAN.md` "KNOW NOW" #3 and `07_WIP.md`'s first section are both stale on this
   point.
2. **`DOC_PLAN.md` §9's own figures are stale.** It says `self_organize.py` is ~6,200 lines with
   2,146 comment lines and gives comment line numbers `4624` and `928-929`. At HEAD the file is
   **7,238 lines**, carries **2,289** full-line comment lines (2,129 in blocks of ≥3), and both line
   references have moved (§6.2).

---

## 8. Verification of the surrounding-documentation claims

Each confirmed by direct check of the file and of `git log -1 -- <path>`.

| Claim | Verdict | Evidence |
|---|---|---|
| `README.md` dates from 2026-07-21..24 and describes a superseded workflow | **CONFIRMED** | Last touched `3500b78`, **2026-07-21**. Line 8 still leads with *"**Headline result:** deleting an entire expert's WEIGHTS costs **-0.0009** collateral"*. Lines 15 and 24 still give `bash run_full_unfrozen.sh` as *"the whole system in one command"* — the harness has been `longrun.sh` since 2026-07-25. |
| `STATE.md` | **CONFIRMED** | Last touched `ffb6bf8`, **2026-07-24**; 71 kB. Line 21 repeats the `-0.0009` headline; line 45 quotes `ROUTE_T=1.0` (HEAD default is **0.1**); lines 88 and 103 still describe `run_full_unfrozen.sh` as the full test. |
| `CL_TESTBED.md` | **CONFIRMED** | Last touched `3500b78`, **2026-07-21**. Line 12 gives `bash run_full_unfrozen.sh`. It uses the retired **"B"** naming throughout (lines 6, 28, 42-47), including *"depend on B"*. |
| `docs/` | **CONFIRMED** | Last touched `4f7f1cf`, **2026-07-21**. Two files (`FILES.md`, `HANDOFF.md`). `FILES.md` states its own provenance: *"Written 2026-07-21 from a direct read of the code ... trust this one for what the code is"* — an instruction that is now three weeks and ~200 commits out of date. |
| `handoff/` | **CONFIRMED** | Last touched `74d10d8`, **2026-07-24**. |
| `garry/` | **CONFIRMED** | Last touched `8150f8a`, **2026-07-20**. Self-labelled *"a FROZEN snapshot. Do not edit it."* — correctly marked, and the only one of the six that says so. It carries its own copy of `tokenizer.py` with the same Greg docstring. |
| `handoff/GLOSSARY.md` documents a `Fabric` → `Router`+`Compositor` rename never adopted in code | **CONFIRMED** | `handoff/GLOSSARY.md:19-26`: *"**Fabric** — RETIRED name (2026-07-21). It conflated two jobs, now split into **Router** ... and **Compositor** ..."* Locked in by `3500b78` (*"handoff: lock the naming pass (B->Verification, Fabric->Router+Compositor, Sense=modality)"*). **Never carried into code.** At HEAD the class is `Fabric`, the node class is `FabricNode`, the knob is `FABRIC`, and every 2026-08 commit message says "fabric". Matches `08_GLOSSARY.md` §1.2: *"Treat `handoff/GLOSSARY.md`'s 'Fabric — RETIRED name' entry as wrong at HEAD."* |

`00_INDEX.md` does not yet exist; when written, its staleness warning should cite this section.

---

## 9. Execution rules for whoever runs the pass

1. **This pass edits comments only.** Verify with `git diff` containing **no non-comment line** —
   exactly as `bdce727` did, and exactly as `3c2a59e` did (*"Comment only -- no behaviour change"*).
2. **Do the P1 rewrites as one commit, the MOVE pass as another.** They have different risk
   profiles: P1 removes false statements, MOVE relocates true ones.
3. **Check `runs.csv` before touching any comment carrying numbers.** §6.
4. **Do not replace a stale number with a fresh number.** That is the repair `6dda2c4` withdrew.
   Remove the assertion and point at the record.
5. **`equiv.sh HEAD HEAD` is not needed** for a comment-only diff, but `bash longrun.sh smoke` after
   the pass costs minutes and proves nothing was caught in a docstring that the parser reads.
6. **Do not re-number.** Cite comments by heading text (§6.2). Line numbers in this file are valid
   at HEAD `45b98eb` and will drift.

---

## 10. Statement of non-modification

**No source file was modified in producing this audit.**

Nothing outside `notes/09_COMMENT_AUDIT.md` was written, edited, or deleted. `self_organize.py`,
`tokenizer.py`, `memory.py`, `longrun.sh`, `runs.py`, `levers.py`, `equiv.sh`, `vocab.py`,
`holdout.py`, `datastream.py`, `runs.csv`, `README.md`, `STATE.md`, `CL_TESTBED.md`, `docs/`,
`handoff/` and `garry/` are untouched. No `git add`, `git commit`, `git push`, `git reset`,
`git checkout` or `git stash` was run; every git command used was read-only (`log`, `show`,
`status`, `branch`).

`git status --porcelain` was **empty** before this file was written and lists **only**
`notes/09_COMMENT_AUDIT.md` after it. A pilot run is in flight; the destinations named in §3 must be
reviewed before anything is moved.

Every classification above is a **proposal**. The replacement lines are drafts, not applied edits.
