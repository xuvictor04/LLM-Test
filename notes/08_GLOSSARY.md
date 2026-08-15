# 08 — GLOSSARY

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are tiny
> — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has reached
> 1.227 b/B (`33a9299`), larger than the gap between any two architectures ever compared here.
> Several confidently-stated findings were later retracted when the measurement turned out to be
> broken. Every entry records **what was observed under these conditions**, never **what is true**.
> Where a result was later invalidated, the invalidation is stated next to it, not in a footnote.

---

## How to read this file

This file is **safe to read standalone**. It does not depend on `01_TIMELINE.md`; where a term has a
history, the commit hash is given inline so you can `git show <hash>` yourself.

Written against branch `rm-predict` at `92a967b` (2026-08-15, 267 commits). Sources: the frozen
commit log at `notes/_evidence/commit_log.txt`, the `_SPEC` knob registry at the top of
`self_organize.py`, and the modules `memory.py`, `tokenizer.py`, `world_model.py`,
`verification.py`, `vocab.py`, `datastream.py`, `levers.py`, `longrun.sh`.

**Three warnings before anything else.**

1. **Terms changed meaning.** Section 1 lists every one this file could establish from a commit.
   Older commit messages and older docs use the OLD sense of each and do not say so. If a term in
   section 1 appears in text dated before the commit given there, read it in its old sense.
2. **A term existing does not mean the thing ran.** Several entries below describe machinery that is
   inert at current defaults, or that has never executed in any recorded run. Those entries say so
   explicitly, in bold: **INERT AT DEFAULTS** or **NEVER RUN**.
3. **`README.md`, `STATE.md`, `CL_TESTBED.md`, `docs/`, `handoff/` and `garry/` all date from
   2026-07-21..24** and describe a superseded workflow (`run_full_unfrozen.sh`, the "B" naming, the
   "-0.0009 collateral" headline). `handoff/GLOSSARY.md` is the earlier attempt at this file and is
   itself stale in at least three places (see §2). They read as current. They are not.

---

## 1. TERMS WHOSE MEANING CHANGED

The highest-value section in this file. Each row: what it used to mean, what it means now, the commit
that changed it, and what to watch for in older text.

### 1.1 `B` → `Verification`

- **Old (before 2026-07-21):** "B" was one of the three lettered subsystems — A (edit/unlearn),
  B (detect wrong info), C (self-assemble domains). B detected wrongness by *self-consistency on
  surprise*.
- **New:** `Verification` — verification by RECONSTRUCTION: reverse-embed the association and compare,
  a signal explicitly DECOUPLED from surprise. `verification.py`, class `Reconstructor`.
- **Changed by:** `61eb8f3` (2026-07-21, docs), locked in `3500b78`, built in `fbdcd50`.
  The reframe that motivated it is `4315c94`: *surprise is a learning driver, not a truth signal* —
  casting surprise as wrong-detection is the category error behind B's ~1% precision.
- **Watch for:** `CL_TESTBED.md`, `README.md` and `STATE.md` all still use "B". Code identifiers were
  deliberately NOT renamed (`is_wrong`, `selfcheck`, `sweep_wrong`, `WRONG_*` knobs), so the OLD name
  survives in the source at HEAD. `WRONG_*` knobs are B, not Verification.
- **Status:** the reconstruction path (`VERIFY=recon`) failed in-loop at 0.3–0.5% precision
  (`9df85b8`, `d7c141b`, `f5303d6`). Default is `VERIFY=selfcon` — i.e. the *old* B mechanism is
  what actually runs at HEAD.

### 1.2 `Fabric` — retired as a name, then never actually retired

- **Old:** the routed expert population, its routing and its blending, all under one name.
- **"New" (2026-07-21, `3500b78`):** the name was declared RETIRED and split into **Router** (selects
  which experts) + **Compositor** (blends their outputs, `fab_logits`). `handoff/GLOSSARY.md` records
  this as settled.
- **What actually happened:** the rename was never carried into code and was abandoned in practice.
  At HEAD the class is `Fabric`, the node class is `FabricNode`, the knob is `FABRIC`, and every
  commit message from 2026-08 onward says "fabric". **Treat `handoff/GLOSSARY.md`'s "Fabric — RETIRED
  name" entry as wrong at HEAD.** Router and Compositor are useful *concepts* (the two jobs are real
  and separable) but are not names anything is called.

### 1.3 `FabricNode` — residual MLP → low-rank adapter

- **Old:** a full residual MLP `d → 2d → d`. 2.36M parameters per expert at d=768, which is what
  capped the population at 64.
- **New (`2e3a464`, 2026-08-03):** the low-rank `d → r → d` form `ExpertBank` already used
  (`FAB_RANK=8`), 12.3k parameters each. `FAB_NMAX` default 64 → 4096 in the same commit.
- **Watch for:** "expert" before 2026-08-03 means a ~2.36M-parameter MLP; after, a ~12.3k-parameter
  adapter. Any parameter-count or capacity statement crossing that date is not comparable.
- **Note:** the `FabricNode` class still exists in `self_organize.py` (~line 1096) with its old
  residual-MLP docstring; the live population is the preallocated tensor pair inside `Fabric`.

### 1.4 `grace` — steps → SELECTIONS (and three different graces exist)

- **Old:** wall-clock age. `FAB_GRACE=3000` meant 3000 *training steps* since birth.
- **New (`9146136`, 2026-08-15):** grace is a **use-age** — selections since birth or rescue
  (`fab.uage`). `FAB_GRACE` 3000 steps → **48 selections**. `_SPEC` carries the comment
  `# fabric -- IN SELECTIONS, not steps`.
- **Why:** under a wall clock an expert the router rarely calls reads as fully-aged after 3000 steps
  of receiving almost no gradient — "culled for failing at a job it was never given".
- **Also changed in the same commit:** the per-expert LR became Smith triangular2 clocked in
  selections (`FAB_LR_CYCLE` is a half-cycle in selections, not steps); `FAB_CULL_FRAC` 0.08 → 0.02;
  `FAB_LR_OWN` 0 → 1; `FAB_LR_BOOST` 1.0 → 2.0; `FAB_LR_SPAN` retired outright.
- **Three graces, three units — do not conflate:**
  - `FAB_GRACE` = 48 **selections** (fabric experts).
  - `DOM_GRACE` = 500 **steps** (domains, `self_organize.py:479`).
  - `EXPERT_GRACE` = 3000 **steps** (the legacy `ExpertRouter`/`ExpertBank` path, `EXPERTS=1`).
- **Watch for:** every "grace" in a commit message before 2026-08-15 is in steps.

### 1.5 `society` — one architecture, then two, then a default that is neither

- **Old (through 2026-08-04):** "society" = `SOCIETY=1` — independent experts, ONE round, blended at
  the prediction level; nobody sees anybody, nothing composes. Contrasted with "chaining"
  (`SOCIETY=0`), where mass flows expert→expert through a learned transition matrix.
- **New (`7b18214`, 2026-08-05):** a third path, **chained society** — run the society, feed its
  result back in, run it again; every round re-routes FROM SCRATCH with the society's own router,
  with the current state in the query. No transition matrix, no SRC. Reached by
  `SOCIETY=0` + `CHAIN_ROUTE=soc`, and made the default in `53fbae5`.
- **The trap:** at HEAD `SOCIETY` defaults to **0**, and `SOCIETY=0` used to mean *chaining*. It no
  longer does. The default path is CHAINED SOCIETY. `SOCIETY=1` selects the *single-round* society.
  Reading `SOCIETY=0` in a HEAD config as "chaining" is wrong; reading it that way in a pre-08-05
  log is right.
- **Watch for:** any knob documented as "gated on SOCIETY" is gated on the single-round path and is
  therefore off at defaults. This has bitten the project repeatedly — `DIV_W` was a silent no-op on
  `CHAIN_ROUTE=soc` for a whole pilot (`b14d60e`); per-expert memory, the affiliation map and the
  utilization the cull rule needs were all gated on `SOCIETY` (`2a262a2`, `ff0f0fa`).

### 1.6 `surprise` — renamed from `novelty`, then reframed

- The write-gate signal was called **novelty**; it was renamed **surprise**
  (`handoff/decisions/write-gate-signal-is-surprise-renamed-from-novelty.md`).
- Separately and more importantly, `4315c94` (2026-07-21) reframed what surprise *is for*: a driver
  of ongoing learning, **not** a wrongness or truth signal. Old text treats high surprise as evidence
  something is wrong. It is not.

### 1.7 `MEM_PER_EXPERT` — documented off, actually on, for the project's whole life

- The comment beside it recorded a measurement and a decision ("DEFAULT OFF"). The code read
  `_i("MEM_PER_EXPERT", 1)`. **Every run in this project before `e25d9b5` (2026-08-15) used the
  partitioned store**, whatever the docs said. Fixed in `e25d9b5`; default is genuinely 0 now.
- Consequence recorded in the same commit: owners are experts folded mod `MEM_OWNERS`, and intra-block
  eviction is LRU on write-recency, so a domain that stops being written is evicted oldest-first by
  construction. That is the mechanism behind the vanished English domain in the continual run.

### 1.8 `domain` — the target changed, twice

- **Old target:** recover the four seeded corpora. Domain quality was V-measure against those labels.
- **Retracted (`efb818a`, 2026-07-25):** the four corpora are a **SCAFFOLD** — how the stream is
  built, not what the system is asked to find. V-measure against 4 labels actively PENALISES the
  intended behaviour (English splitting into narrative and dialogue *lowers* V while being exactly
  what is wanted). The headline metric became **RECURRENCE** — is a domain re-entered?
- **Retracted again (`5e02cfc`, 2026-07-25):** "domain assembly works, purity 0.54 → 0.96" was
  withdrawn. Purity rises MONOTONICALLY with fragmentation; one window per cluster gives purity 1.0.
- **Superseded entirely (`9d90416`, 2026-07-31):** domain counts, purity, silhouette, V-measure and
  specialization are labelled **DIAGNOSTICS, NOT TARGETS**. See §3 under each metric.

### 1.9 `ramp` — a step window → a population target that latches

- **Old:** `FAB_RAMP` (default 4000) was read as a step count, and the ramp was armed while
  `n < ramp_to * cap` — i.e. while the CURRENT population was below target.
- **The defect (`ff0f0fa`, 2026-08-05):** culling holds the population just under the cap
  indefinitely, so the ramp stayed armed for entire runs and re-fired every `cool//8` = 187 steps.
  At the cap it added nothing — it **REFILLED**, within 187 steps, whatever the last cull removed.
  Across three pilots ~10062 grown = ~4093 building the population once + ~5969 refilling 5969 culls.
  "4096 nodes (10062 grown)" was the only trace and reads as healthy growth.
- **New:** the ramp LATCHES on first arrival at `ramp_to * cap` and does not re-arm
  (`FAB_RAMP_LATCH=1`; setting it to 0 restores the never-terminating ramp). After the latch, growth
  must come from a REGRESSION or a stall.
- **Watch for:** any pre-`ff0f0fa` population figure describes a population being replaced ~1.5x over,
  with ~10% freshly-initialised at any moment — and the identity space every `eemb` key and every
  centroid is defined over IS that churning set.

### 1.10 `spread` — three unrelated meanings, all printed

- **seed spread** — max minus min held-out b/B across nominally identical runs. Reached 1.227 b/B
  (`33a9299`); 0.060/0.174 on paired pilots (`6bd226c`); 1.594 b/B same-seed with `SAVE_CKPT` toggled.
  This is the noise floor every comparison in the project lives under.
- **SPREAD** (the report line in the domain-genuineness section) — the **median silhouette** across
  live domains, chosen because it is scale-free where the mean is not.
- **`_spread`** (the variable behind the `SPECIALIZATION` line) — mean |node − population| bits/byte,
  i.e. expert specialization, not dispersion at all.

### 1.11 `bits/byte` — and the bytes/token bias that flipped sign

- Bits/byte has always been the unit (see §3), but the *conversion* was wrong twice:
  `37100fb` and `8a8fb69` (both 2026-08-14) found bytes/token was computed as an **unweighted mean
  over the vocabulary** rather than weighted by occurrence, and that the sign of the resulting bias
  **depends on vocabulary size**. Any b/B figure that crossed a vocabulary-size change before
  2026-08-14 carries an unknown-signed bias.

### 1.12 `held-out` anchors — the order-1 anchor was once fitted on the held-out text

- `aac17f7` (2026-07-28) introduced the anchors and initially fitted the order-1 baseline **on the
  held-out text it was scoring** — "a model that has seen the answers", an unfairly strong anchor.
  Now fitted on TRAIN, scored on HELD-OUT (`self_organize.py` ~5952). Pre-fix "beats order-1 by X"
  figures understate the model.
- Separately, the corpus was re-fetched between the 8-epoch arms and `ep18_big` and order-1 moved
  **3.440 → 3.747** (`ac79e92`). Always quote a held-out figure against its OWN run's order-1.

### 1.13 `PHASED` — shipped off, never once run, now the default

- `PHASED=0` shipped in commit 1 and was never turned on in any run (`c316813`, 2026-07-27). Of
  fourteen report sections, exactly one bore on catastrophic forgetting and it sat behind `PHASED=1`.
- `a5ac033` (2026-07-28) made non-stationary the default; `_SPEC` reads `PHASED=1` at HEAD.
- **Watch for:** every result before 2026-07-28 was measured on a stationary stream, whatever the
  surrounding prose about continual learning said.

### 1.14 `MANAGE_MERGE` — 0.12 → 0.45 → 0.28

- 0.12 for the project's whole life, overriding the intended fallback and 3x tighter than the
  creation scale `NEW_DIST=0.35`, so everything in between was permanent (`13e787a`, 2026-07-27).
- 0.45 maximises V-measure against the four seeded corpora — and was rejected for exactly that
  reason once the seeded labels were disowned.
- **0.28 at HEAD** = `MERGE_FRAC * NEW_DIST`, restoring create/consolidate consistency. It is a
  POLICY knob (how finely do you want to be able to forget?), not a correctness one.

### 1.15 `knob registry` size — 274 → 279 → 310

- `6f4c534` (2026-08-07) created `_SPEC` with **274** knobs. `f279fd0` (2026-08-11) closed a hole and
  reported coverage **279/279** — the number `DOC_PLAN.md` quotes. At HEAD `_SPEC` holds **310**.
  Any "279 knobs" phrasing is historical.

### 1.16 `Sense`

- Fixed at `3500b78` (2026-07-21) as a **MODALITY** (one sense today = language; mic → audio, camera
  → vision), explicitly NOT polysemy (provisionally "Meaning"). Earlier design text conflates the two.

---

## 2. RETIRED / DEAD TERMINOLOGY

You will meet these in `README.md`, `STATE.md`, `CL_TESTBED.md`, `docs/`, `handoff/` and `garry/`.
None of them describes the system at HEAD.

| Term | Where it appears | Status |
|---|---|---|
| **B** / "detect wrong info" / "wrongness" | `README.md`, `CL_TESTBED.md`, `STATE.md`, and the source identifiers `is_wrong`/`selfcheck`/`sweep_wrong`/`WRONG_*` | Renamed to Verification 2026-07-21 (`61eb8f3`, `3500b78`). Code names deliberately kept. |
| **Router + Compositor** | `handoff/GLOSSARY.md`, `handoff/STRUCTURES.md` | The 2026-07-21 replacement for "Fabric" (`3500b78`) that was never adopted. "Fabric" is the live name. |
| **Node** | old comments, `handoff/GLOSSARY.md`, the `SPECIALIZATION` report line | = today's "expert". Both words still appear in the source and in report text at HEAD. |
| **`run_full_unfrozen.sh`** | `README.md`, `docs/` | The 07-22 workflow. Superseded by `longrun.sh` (pilot / grid / seeds / repeat / smoke / add). |
| **"-0.0009 collateral"** headline | `README.md`, `garry/GARRY.md` | The frozen `garry/` milestone's number. Not reproducible at HEAD and not the project's stated goal (`9d90416`). |
| **"the FABRIC is worth +0.709 b/B"** | `rerun.sh` header before `9d90416` | Retracted. That was the eval-time knockout; the retrained ablation says 3.089 vs 3.090 (`e60b8e0`). |
| **`FAB_LR_SPAN`** | pre-08-15 commit messages | Retired in `9146136`. It scaled a per-expert cosine across a wall-clock lifetime; under a selection clock it has nothing to denominate. Deliberately deleted rather than left declared-but-dead, "which would have made it settable and silent". |
| **`ExpertBank` / `ExpertRouter`** (`EXPERTS=1`) | `self_organize.py` ~2363–2480 | The legacy pre-Fabric population, 1:1 with domains. Mutually exclusive with `FABRIC` via an elif chain, which `51889b7` calls "arguably a bug". `EXPERTS` defaults 0. **INERT AT DEFAULTS.** |
| **`Garry`** | `garry/` | A frozen snapshot, not a component. Do not read `garry/self_organize.py` as current code. |
| **"D_MODEL_B"** as a live width control | pre-`a5cd9ed` runs | Was read by nothing; every direct run silently ran d=128 (`a5cd9ed`, 2026-07-24). Now an alias for `D_MODEL`. |
| **the "seeded corpora" as a target** | the whole 07-25..29 domain campaign | Disowned as a SCAFFOLD (`efb818a`), then demoted to diagnostic (`9d90416`). |

---

## 3. THE GLOSSARY (A–Z)

Definitions are of the term as used **at HEAD** unless the entry says otherwise. Where a term has a
history, §1 has the detail.

### Populations, routing, experts

**affiliation map (`dom_exp`, `fab.dom_of`)** — which experts serve which domains and by how much. A
DIAGNOSTIC, not a deletion mechanism; it exists to preview the blast radius of deleting a domain. It
drives the breadth cap. It found 0 exclusive experts in every run, which is why domain deletion
RELEASES affiliations rather than cascade-killing experts.

**blackout** — `PlateauGrowth.note_shift(t)` marks a step after which growth is suppressed for one
cooldown, because the loss jump was OURS (a retokenisation or an epoch resample), not the data's.
Without it a retok looks like a distribution shift and triggers a growth burst.

**breadth cap (`EXP_DOM_FRAC`=0.10, `EXP_DOM_MIN`=4)** — an expert may serve at most 10% of live
domains (floor 4). Introduced `763e9f2`. It was **INERT on the default path** until `ff0f0fa`:
`dom_ban` was computed in the society branch and never passed to `forward()`, so a handful of experts
absorbed everything (top expert 79.5% of traffic).

**burst (`FAB_BURST`=1, `GROW_BURST`=6)** — how many experts a single growth event adds. `PlateauGrowth`
returns an INT, not a bool: a burst on an unexpected regression, a single node on a stall.

**chained society** — the default forward path: `SOCIETY=0` + `CHAIN_ROUTE=soc`. The society run
`FAB_STEPS` times over; each round re-routes from scratch with the current state in the query; the
round's experts vote on the OUTPUT; the state carries into the next round. No transition matrix, no
SRC. See §1.5. Its H(hop1|hop0) = 0.533 bits over 202k transitions, against 0.005–0.058 for every
transition-routed arm — the only configuration that has ever produced real multi-hop routing.

**chaining (`CHAIN_ROUTE=transition`)** — the older path: mass flows expert→expert through a learned
transition matrix `R[n→m] = softmax((q_route(gist) + SRC[n] + ctrl(summary)) · K[m])`. Lost the 18-arm
grid to `FABRIC=0` entirely (`ffd39b8`). Its H(hop1|hop0) of 0.007–0.058 bits is the "rail": one
decision, then a fixed successor, because the query is dominated by the holder's identity and a
signature that does not change between hops.

**competence (`COMP_EMA`)** — per-expert (and per-domain) EMA of bits/window on the material that
expert WINS. Distinct from utilization: load is not competence.

**competence protection (`COMP_PROTECT`=1)** — spare a low-use expert that is nonetheless competent.
Reported "spared 0" in every run, because `router.manage` is gated on `EXPERTS`, which is mutually
exclusive with `FABRIC` — the fabric had no culling at all (`2a262a2`).

**crossover (`FAB_XOVER`=0.35)** — a newborn inherits connected rank-slices of its parents rather than
a fresh init (`580cd62`).

**cull / soft_cull** — remove the bottom `FAB_CULL_FRAC` (0.02) of the eligible population by
utilization. "Eligible" now means past `FAB_GRACE` in SELECTIONS, and the ranking happens WITHIN the
eligible set — before `9146136` the bottom of a raw ranking was by definition the least-aged, so the
whole budget was spent on entries guaranteed to be skipped and nobody was ever removed.

**discovery (`FAB_DISCOVER`=0.35)** — when a signature is far from EVERY centroid, it is material
nothing owns; discovery routes it to a new or low-use expert instead of the argmax. Was structurally
impossible before `580cd62` (updating the argmax winner only means the winner drifts toward
everything).

**exploration (`FAB_EXPLORE`=0.15)** — a fraction of steps force an off-policy expert into the
selection, so unselected experts can accrue gradient. Note `c76dc74`: eval-time exploration was one of
the five diagnostic→training leaks.

**expert** — the unit of the population. At HEAD: a low-rank `d → r → d` adapter (`FAB_RANK`=8, 12.3k
parameters) over the base model's hidden state, born as an exact identity (B zero-init) so adding one
never disturbs what already works. Before `2e3a464` it was a full residual MLP (§1.3). Individually
weak on purpose: "no single one is meant to suffice."

**Fabric** — the routed expert population as a whole: the preallocated key/adapter tensors, the
router, the transition matrix, HALT, and the blend. `FABRIC=1` at HEAD. **`FABRIC=0` in every run of
the project until `7a42f90` (2026-07-29)** — the single largest silent-default error in the record.

**FabricNode** — see §1.3. Class still present; not the live population representation.

**founder** — an expert present at `FAB_N0`, i.e. from step 0. Founders had **no birthday** and read
as age 0 forever, so the founding population was permanently immune to culling (`91fd815`,
`a5cc7ea`, 2026-08-15). Arm B (`FAB_N0=2048`, all founders) therefore ran with **zero culls for its
whole life** — the best result on record ran with no selection at all.

**grace** — see §1.4. Three of them, three units.

**HALT** — an ABSORBING operator in the routing distribution, so depth is adaptive. On the
chained-society path it is a per-round STOP PROBABILITY: `alive` starts at 1, each round takes
`alive * p_stop`. HALT measured **0.0000 in all 18 grid arms** on the hidden-state chaining path,
because stopping early bought it nothing.

**hop / depth** — one iteration of the fabric. `FAB_STEPS`=4 is the maximum. "mean routed depth" is
the report figure.

**identity space (`eemb` / `edec`)** — `eemb` embeds an expert's flattened WEIGHTS to a vector (the
router can RECOGNISE an expert by what it is); `edec` maps a point in that space back to weights (the
router can SPECIFY one). `FAB_AE_W`=0.5 weights the round trip that keeps `edec` honest. A newborn's
weights ARE `edec(query)`, so the LM loss backpropagates into `q_route` — this is
**spawn-by-specification**. Note the measured failure mode: identity-space variance of 0.000, every
expert embedding to the same vector, leaves routing nothing to work with.

**interchangeable / redundant vs modular** — the two characterised regimes. Redundancy: every expert
substitutable, deletion free, no specialization. Modularity: experts specialize, deletion costs
something but concentrated on what that expert served. A genuine open fork, not a bug either way.

**latch** — see §1.9.

**lineage / parent quota (`FAB_PARENT_K`=8, `FAB_PARENT_MAX`=0.20)** — a newborn's parent is sampled by
fitness among the nearest region-owners; no parent may account for more than 20% of births.

**marginal contribution (`fab.contrib`)** — EMA of (loss WITHOUT this expert − loss with it). The
fitness signal selection uses where it has been measured; utilization is the fallback.

**minting** — see the tokenizer section.

**mutation (`FAB_MUT`=0.25, `FAB_MUT_BIG`=6.0, `FAB_MUT_BIG_P`=0.1)** — perturbation applied at
replication, as a fraction of the parent's own weight std; 10% of births get a 6x jump.

**newborn fraction (`FAB_NEW_FRAC`=0.04, `FAB_NEW_WIN`)** — at most 4% of the population may be newly
born within one window. Added `f4b2e9b`/`6d5e6d7` (2026-08-15) to bound the churn §1.9 exposed.
**Never validated at pilot scale.**

**PlateauGrowth** — the growth state machine (`self_organize.py:2282`). WATCH → BURST → RECOVER.
WATCH looks for an UNEXPECTED worsening (loss above the slow EMA by `FAB_Z`=4 robust deviations,
running MAD so it is scale-free) and also fires on the RAMP early on; BURST returns several experts at
once; RECOVER refuses to re-arm while the model is re-learning, since the burst itself causes a
transient worsening. `FAB_GROW=0` freezes the population at `FAB_N0` — no ramp, no regression burst,
no stall growth — while leaving culling, routing, selection and replication running. That is arm B.

**ponder (`PONDER`=0.01, `PONDER_WARM`=8000)** — a cost charged for depth, so the router is pressured
toward stopping. `PONDER_WARM=8000` is longer than a 4 MB pilot run (~6,500 steps at WIN=256), so the
schedule **peaked at 0.81 and never reached full strength** in the early runs: "the fabric is worth ~0
bits/byte" was a measurement of a warmup that never completed (`33355b2`, `longrun.sh` header).

**probation (fabric sense)** — not a fabric term; see the tokenizer section.

**rescue (`FAB_RESCUE`=0.0)** — the idea from `e2db890`: selection should raise the mutation rate, not
only prune. An expert due to be culled gets a large mutation INSTEAD, the first time it comes up.
**Default 0 = OFF, and it fired zero times for an entire investigation with nothing in the log saying
so** — which is why the rescue counter now exists.

**replication (`FAB_REPLICATE`=1)** — copy a fit expert into a free slot with a perturbation.

**retirement (fabric sense)** — not used; experts are culled or rescued. See the tokenizer section for
`retire`.

**SRC** — the outgoing signature mark expert `n` puts on a message, used only by the transition-routed
path. The chained-society default has no SRC.

**soft cap (`GROW_CAP`=0 master switch, `GROW_CAP_FAB`, `GROW_CAP_VOCAB`, `GROW_LIFT`=2.0)** — a cap
below `FAB_NMAX`/`VMAX` that LIFTS when a plateau earns it; nothing lowers it. **INERT AT DEFAULTS**
(`GROW_CAP=0`). Six `GROW_CAP*` knobs were once set deliberately on a build that predated them
(`c909918`).

**society** — see §1.5.

**specialization** — the report line `SPECIALIZATION (mean |node − population|)`, introduced
`9d90416`. Measures whether the material an expert WINS is modelled differently by that expert than by
the population, **against a shuffled-assignment null** (20 shuffles, spread reported), because
per-expert bits/byte is mostly material difficulty. First reading: 0.179 against a null of
0.161 ± 0.054 → **INTERCHANGEABLE**. **DIAGNOSTIC, NOT A TARGET** (`9d90416`).

**sufficiency** — the report check "does the POPULATION beat its best single member?"

---

### Domains and the assembler

**assembler (`DomainAssembler`, `SELF_ORG`=1)** — reads the stream, computes a signature per window,
and creates / merges / culls / folds domains online. Its only functional job is **PROVENANCE**:
memory entries (and, on the single-round society path, routing traffic) are tagged by domain so a
domain can be looked up and its memory deleted.

**boundary** — where the assembler switches domain. Boundary precision/recall against the splice
segments is reported; `3f44ce3` warns that when a splice segment is only a few analysis windows long,
purity/homogeneity measure the transition rather than the domain.

**`did`** — the domain id. **Consumed in exactly three places**: `mem.src` (provenance →
`delete_src`/`reassign_src`), `dom_exp` (reporting), and the clustering report. **ROUTING DOES NOT USE
IT** — fabric and experts route on the continuous `gist`. So the domain COUNT has essentially no
effect on prediction; what it sets is the **granularity of forgetting**. Measured: unlearning one
process at 25 domains is 20 deletes of ~1.6% each; at 4 domains it is a single delete of 30%.

**fold (`DOM_RECUR`=1, `DOM_FOLD_MULT`=1.5)** — merge a domain that never RECURS into its nearest
neighbour, refusing to fold further than 1.5x the pooled radius (unguarded, it collapses to one
domain).

**gist** — the continuous signature vector actually used for routing. Distinguish from `did`.

**radius (`DOM_RADIUS`=1, `DOM_RQ`=0.85, `DOM_RCAP`, `DOM_RMULT`)** — a PER-DOMAIN acceptance radius,
the 0.85 quantile of distance from that domain's own reservoir windows to its centroid, rather than
one global `NEW_DIST`.

**recurrence / visit** — a **visit** is a maximal run of consecutive windows assigned to one domain;
**recurrence** is how many visits a domain gets. Made the headline domain metric in `efb818a`: real
structure recurs, a splice artifact is visited once. The measurement that motivated it: 96 domains
against 89–96 splice segments at a mean of 9.5 windows each — a near one-to-one map onto our own
seek points.

**reservoir (`DOM_WINS`=40)** — sample windows kept per domain; the basis for rekeying and for the
per-domain radius.

**scaffold** — the four seeded corpora (`DOMAINS=eng,py,num,c`). How the stream is built, NOT what the
system is asked to find (`efb818a`).

**signature / SigEncoder (`SIG_*`, `ENC_*`)** — a learned encoder over the **BYTE** stream (not the
token stream), trained by InfoNCE (nearby windows positive, random negative), producing the vector the
assembler clusters and the router queries. `SIG_SPACE=bytes` at HEAD; `SIG_SPACE=tokens` exists and
has never been measured at pilot scale.

**splice segment (`SEG_MIN`=700, `SEG_MAX`=1800, `SEG_CONTIG`)** — a contiguous run drawn from one
corpus when the stream is built. `SEG_MIN/SEG_MAX` were chosen when `WIN` was in bytes (`3f44ce3`).
`SEG_CONTIG` is DERIVED: contiguous when there is one corpus, random-offset when several — because on
a single corpus, random offsets meant more than half of English's "domains" were our own seek points
(`98f19fa`).

**SUSTAIN (`SUSTAIN`=2)** — a shift must be sustained for this many consecutive windows before it
counts, so a single spike cannot spawn a domain.

**purity** — fraction of windows in a domain belonging to its majority true label. **Rises
MONOTONICALLY with fragmentation** — one window per cluster gives 1.0. Measures nothing about whether
the partition is useful. **DIAGNOSTIC, NOT A TARGET** (`9d90416`); the "0.54 → 0.96 domain assembly
works" claim built on it was **retracted** (`5e02cfc`).

**homogeneity / completeness / V-measure** — homogeneity = 1 − H(true|domain), high for ANY
pure-but-shattered clustering; completeness = 1 − H(domain|true), which FALLS with fragmentation;
V-measure is their harmonic mean. The **completeness formula was actually homogeneity** until
`b1fe6ed` (2026-07-25), so every V-measure before that date is wrong. V-measure is computed against
the four seeded labels and therefore penalises the intended over-segmentation (§1.8). **All three are
DIAGNOSTICS, NOT TARGETS**, and the record shows steering by them consumed weeks (`9d90416`).

**silhouette / genuineness (`GENUINE_SIL`=0.10, `GENUINE_MIN`=20)** — cohesion + separation − 1 per
domain; a domain is "genuine" if it is both large enough and separated enough. Separation was once a
**min order statistic**, which shrinks mechanically as the population grows and penalises exactly the
fragmentation it was meant to detect (`2cffa47`, 2026-07-27). What is scale-free is the MEDIAN
silhouette, reported as `SPREAD`. **DIAGNOSTIC, NOT A TARGET** (`9d90416`).

**fragmentation** — self-domains per true process. Reported beside purity precisely because purity
alone cannot see it.

---

### Tokenizer and vocabulary

**minting** — the online BPE merge: during training, `maybe_grow()` promotes a frequent adjacent pair
to a new token id. `TOK_ONLINE=1` is the default; the tokenizer is the "expanding DynamicTokenizer",
not a static ByteBPE.

**mint gate (`TOK_MINT_PMIN`)** — a **p(b|a)** predictability threshold on candidate merges, not an
entropy threshold, and it **filters rather than aborts** (`93c1733`). It **starved the vocabulary in
the first real pilot**, so it now **fails open** — if the gate rejects everything, minting proceeds
(`1a113f5`). `TOK_MINT_GATE_K`=1024 is how far down the candidate ranking the gate looks; it was
**never read through `_env`** for a period (`904742c`).

**fail-open** — the general pattern established by `1a113f5`: a gate that can starve a population must
release rather than block when it rejects everything.

**novelty minting (`TOK_MINT_NOVEL`=0.0)** — mint on novelty rather than frequency. **OFF; never
measured at pilot scale.**

**probation (`TOK_PROBATION`=0, `TOK_PROBATION_STEPS`, `TOK_PROBATION_BY`=use|embed,
`TOK_PROBATION_MIN`)** — mint provisionally, train, then judge: a minted token must earn its slot by
appearing N times (`by=use`) or by developing a delta of at least `TOK_PROBATION_MIN` relative to its
composite (`by=embed`) before a deadline, or it is un-merged (`9f8412b`). **OFF at defaults; never
measured at pilot scale.**

**retire (tokenizer sense, `retire()` / `retire_stale()`)** — un-merge a token, freeing its id. A
retired id is BELOW `vocab_size`, is never a target again, and is **not a suffix** of the id range —
which is why `mask_dead` missed them until `f8599b7`. **`retire_stale` has never been executed**; its
wiring is in `handoff/designed-but-not-built/`.

**retok / re-segmentation (`RETOK_EVERY`=3000, `RETOK_TAIL`=1)** — re-segment the stream with the
current vocabulary so the same text maps to the new ids. **An unchanged-vocabulary retok is NOT a
no-op**: greedy longest-match over the same vocabulary produces a byte-identical stream, but the retok
still clears the lookahead queue and blacks out fabric growth. Measured cost of 23 retoks, 22 of them
adding zero tokens: **2.189 b/B** (`046fd81`). The guard that skips them then **killed re-segmentation
entirely** because `_due` is not a predicate — calling it twice consumes the event (`d0728fe`).

**dead rows / never-minted / minted-then-unused** — three distinct `[vocab]` lines. **never minted** =
softmax width the tokenizer never filled; **minted, unused** = ordinary turnover, ids minted then not
present in the final stream. `LOSS_MASK_DEAD`=0 masks never-minted ids out of the distribution; the
first controlled test gives **+0.060 against a combined SE of 0.055 (1.1σ)** (`e9f2e58`) — the
monotone "dead rows explain everything" story is **not established**, and `0279709` falsified it
outright: `vmax8k@18ep` filled its vocabulary completely and was the WORST of the four.

**seed vocab vs VMAX vs softmax width** — three different numbers. `SEED_VOCAB`=512 is what the
pre-pass builds; `VMAX`=4096 is the cap minting may reach; **softmax width** is what the model
allocates embedding/head rows for, which is `VMAX` regardless of how much of it gets minted. An
unfilled `VMAX` is dead rows.

**warm start (`WARMSTART`=1, `WARMSTART_MODE`=mean, `WARMSTART_OPT`=0)** — a newly minted id's
embedding is initialised from its two constituents. Minted-token init is **asymmetric** and averaging
both sides loses most of the benefit (`c92d104`, 18 trials) — but the end-to-end run disagreed with
the trial result, and `mean` remains the default.

**composite / `TOK_COMPOSE`** — compute a token's vector FROM ITS BYTES so minting allocates nothing
(`e8df6fe`), corrected so minted tokens DO get parameters but START at their composite and grow into
themselves (`ed04aac`). Back to **default OFF** (`be50e3a`) because it was the only change that moved
the LEVEL. **INERT AT DEFAULTS.**

**residual anchor (`TOK_ANCHOR`=0.05, `TOK_ANCHOR_TAU`=4000, `TOK_ANCHOR_USES`=400)** — holds a new
token near its composite, releasing it after that many APPEARANCES (`_USES`>0) or STEPS (`_USES`=0).
The anchor is a method of `ByteComposer`, which is constructed **only when `TOK_COMPOSE=1`**. Since
`TOK_COMPOSE` defaults to 0, **the anchor term never enters the loss at defaults** — see §5, question 2.

**`_due`** — the cadence helper. **It is not a predicate.** Calling it twice consumes the event. This
killed retokenisation for three 18-epoch runs and was armed for `grow` and `probation`
(`d0728fe`, `0f96784`).

---

### Memory and the world model

**EditableMemory (`memory.py`)** — the external key→token store. Key = the model's own representation
of the context (`KEY_SRC=model`), value = the stored next token, plus per-entry provenance (`src` =
domain id), context (`ctx`, so keys can be re-encoded), and byte position (`pos`). Writes are
surprise-gated (`WRITE_GATE`, `MEM_GATE`). Reads are a **global kNN** — memory is never partitioned
for retrieval, only for eviction.

**rekey (`REKEY_EVERY`=200, `REKEY_AMORTIZED`=1, `REKEY_CHUNK`=1)** — re-encode stored keys with the
current model, because the model that wrote them has moved. This is the whole drift-survival
mechanism; `active_ctx` is its input. ~200,000 entries in 2.0s on the retok cadence.

**drift (memory sense)** — the model's representation moving away from what the store was keyed in.
Distinct from **drift (retention sense)**, the `DRIFTING` verdict below, and from **`no_rng_drift`**,
a decorator asserting a diagnostic does not move the run's RNG.

**owners / quota (`MEM_OWNERS`=64, `MEM_QUOTA`=128, `MEM_PER_EXPERT`)** — an "owner" is an **eviction
bucket, not an identity**: expert ids fold mod `MEM_OWNERS`. See §1.7 — the partition was on in every
run until `e25d9b5` despite being documented off.

**provenance / `delete_src` / `reassign_src`** — deletion by provenance is the oldest and most
consistently reproduced result in the project. Caveat from `c316813`/`9909349`: every "unlearning is
surgical and local" result was measured on **ACTIVE** material, and deleting what a bounded store has
already evicted is a no-op.

**re-segmentation mismatch** — memory contexts were queried in a segmentation they were not written
in: **82.3% mismatch after one growth step** (`8bdeca4`). Entry VALUES cannot be remapped across a
re-segmentation and the stored SPAN shrinks; fixing it changes the checkpoint format. **NOT FIXED.**

**world model (`WORLD_MODEL`=1, `world_model.py`)** — an encoder to a latent (`WORLD_LAT`=32) plus a
routed `DynamicsPopulation` of forward predictors, trained to predict the next observation's latent,
with a variance/covariance term against collapse. `WORLD_FEEDBACK`=1 feeds it back into the LM.
**Defaults ON.** Its last reading (`51889b7`, 2026-07-29) was "beats baseline −84.7%, latent std 0.07"
— by its own collapse criterion it had **not learned dynamics**. Not measured since.

**Verification (`VERIFY`=selfcon | recon, `verification.py`)** — see §1.1. `recon` builds a
`Reconstructor` (cross-reconstruction: from the context KEY, reconstruct the EXPECTED token code).
Standalone CPU probe AUC 0.978/0.980; in-loop precision 0.3–0.5% (`9df85b8` 2026-07-21, `d7c141b` and
`f5303d6` 2026-07-22). **`VERIFY=recon` has not been run since.**

---

### Measurement

**bits/byte (b/B)** — the project's unit for every loss and every anchor. **Why bytes and not tokens:
tokenizer-neutrality.** A token spans a variable number of bytes and that number changes during a run
as the vocabulary compresses, so bits/token silently rewards a bigger vocabulary and makes two runs at
different `VMAX` incomparable. Bits/byte divides by the true byte count (`nbytes()`,
`TOK.bytes_per_id`) and is the same quantity regardless of how the text was segmented. It is the
**TARGET** (via generation quality and retention, which it proxies). Caveat §1.11: the bits/token →
bits/byte conversion itself was biased until 2026-08-14 (`37100fb`, `8a8fb69`).

**the anchors (`uniform` / `order-0` / `order-1`)** — fitted on TRAIN, scored on the SAME held-out
text, in the same units:
- **uniform** = log2(vocab size) scaled to bytes — what assigning equal probability to every token
  costs. A model above it is worse than guessing.
- **order-0** = a single add-k-smoothed unigram histogram.
- **order-1** = an add-k-smoothed bigram table. *"If the model does not clearly beat ORDER-1, none of
  the architecture is doing work that a two-line frequency table could not."*

  They measure **whether a b/B number is worth anything at all**; they do NOT measure progress
  between architectures, and they are **not comparable across corpora** — the corpus was re-fetched
  and order-1 moved 3.440 → 3.747 (`ac79e92`). **DIAGNOSTIC**, but a mandatory one: a b/B figure
  quoted without its own run's order-1 is uninterpretable. For scale, GPT-2-small sits near
  1.0–1.2 b/B on comparable text.

**held-out (`VAL_FRAC`=0.05)** — a tail of each corpus never sampled into the training stream. The
headline number. **TARGET.**

**memorization gap** — train b/B minus held-out b/B. gap < ~0.3 = UNDERFIT (regularisation would
HURT); gap > ~0.5 = MEMORIZING. Almost every run in this project underfits; `vmax8k@18ep` is the only
run with a positive gap (+0.267). **DIAGNOSTIC.**

**held-out SE / the noise band** — the report prints `± SE` on train and held-out and then states the
band: *a difference between two runs smaller than ~2(SE_train + SE_val) b/B is inside this
instrument's noise*. Two arms inside it are not distinguishable however different the means look.

**seed spread** — see §1.10. The binding constraint on every comparison in the project.

**ACROSS THE RUN BOUNDARY** — the report section (and `holdout.py`) that compares the per-domain
held-out probe stored in the checkpoint you RESUMED FROM against the same probe now. Keyed by domain
NAME with a deterministic seed, so it survives a change of stream. Verdicts per domain: `WORSE
(forgetting)` if the change exceeds 2σ, `better` if it exceeds 2σ the other way, `HELD (inside the
noise)` otherwise, and `NEW this run -- no baseline, nothing to forget yet`. **It is the ONLY number
that spans the run boundary** — every other retention figure is computed on the current stream and
cannot see what was known before this run started. **TARGET.**

**retention / `RETAINED` / `DRIFTING` / `CATASTROPHIC`** — the within-run retention verdict: each
process's EARLIEST windows against its LATEST windows, conditioned on the label. <0.10 = RETAINED,
<0.40 = DRIFTING, above = CATASTROPHIC. Must be compared PER PROCESS — the first version took the
first fifth against the last fifth and under `PHASED` those are disjoint sets of corpora, so it was
measuring which corpora are intrinsically harder (`a5ac033`).

**the learning curve's ACTIVE / ABSENT columns** — b/B change per 2000 steps while a process is in the
active phase versus while it is not. The one real continual run reports +0.116 while active vs −0.029
while absent (`a9d7258`).

**knockout vs retrained ablation** — a **knockout** disables a component at eval time on an already-
trained model; a **retrained ablation** trains a fresh model without it. They disagree badly: FABRIC
knockout said +0.709 b/B, the retrained pair said 3.089 vs 3.090 (`7a42f90` vs `e60b8e0`). The
knockout number justified a default and was **retracted** (`9d90416`). Prefer retrained.

**the null (shuffled / permuted / matched-size)** — every specialization or informativeness verdict is
scored against a null in which the assignment is shuffled, because the raw statistic is mostly
material difficulty. `3e2393d`: the informativeness null was a **single permutation** and the verdict
flipped on noise — it now carries an error bar.

**coherence (`COH_N`=16, `COH_LEN`=384)** — a generation-quality statistic. It was a **four-sample
statistic and three mutually contradictory claims were made from it** (`6f24bed`). Read as a smell
test, never as a finding.

**real words / tokens per word** — the `words_pct` column: what fraction of generated output is real
words. A cheap sanity check on generation, which is the stated deliverable.

**the instrument** — the collective name for the measurement code, after `c76dc74` established that it
was *wired into the circuit*: five diagnostics were editing training state. **"No result in the record
predates these fixes safely."** The mechanism that made it matter: `build_stream` drew segment lengths
from the GLOBAL RNG, so **how much you measured decided what you trained on**. The stream now has its
own RNG.

**instrument era** — informal shorthand for pre- vs post-`c76dc74` (2026-08-13) and pre- vs
post-`5f4f117` (2026-08-07, eval passes stopped training the router). `runs.csv` has **no column for
it**.

**`equiv.sh`** — the inertness harness: run two commits with the same config, seed and corpus on the
same machine, strip volatile lines, and require every remaining number to be identical. Training is
deterministic given (config, commit, seed) — measured, three runs byte-identical. `equiv.sh HEAD HEAD`
is the **per-machine noise baseline / determinism self-test**, and must be run on any new device
before believing a verdict, because cuDNN's GRU backward and atomic scatters are not bit-reproducible
in general. **No `runs/equiv_noise_*` exists in this checkout.**

**`_done`** — `longrun.sh`'s completion test: does the log contain the final line every complete report
prints. Combined with a TAG derived from ARMFLAGS alone, it once caused an 18-epoch sweep to skip and
re-print the 8-epoch numbers under an 18-epoch banner (`42d8686`); `_cfgsig` now records the
run-shaping settings alongside.

---

### Configuration and the config banner

**`_SPEC`** — the knob registry near the top of `self_organize.py`: **every** environment knob the file
reads, with its type and default, in one place. `_env` checks every read against it and **stops the
run** if a call site disagrees with the table. It exists because five knobs were once read with
DIFFERENT defaults in different places — `VMAX` sized one tensor for 4096 ids and another for 2048.
**310 knobs at HEAD** (§1.15).

**`_env` / `_i` / `_f`** — the only sanctioned readers. `_ENV_ASKED` records what the environment set;
`_ENV_READ` records every key the code asked for.

**derived (`_DERIVED`)** — a knob whose DEFAULT is computed from another knob, so leaving it unset ties
it to that other knob's value. Nine at HEAD, e.g. `MAX_DOMAINS` follows `FAB_NMAX`, `SEG_CONTIG`
follows `DOMAINS`, `SIG_LOOK` follows `ENC_EVERY_IDLE` follows `ENC_EVERY` (two hops).

**override** — a knob that is read and then REASSIGNED, so an explicit setting is DISCARDED. `levers.py`
calls this "the one that is a bug rather than a design".

**lever** — `levers.py`'s term: a knob is only a lever if moving it moves ONE thing. It re-derives
DERIVED / OVERRIDE / UNKNOWN from the AST and fails on drift in either direction.

**`[config] SUBSYSTEMS`** — the banner line saying what is actually ON, read from the LIVE object, never
re-read from `os.environ`. It exists because the banner **has lied three separate times** — "per-expert
memory ON" for a whole 48k-step run where it was off from step 0, among others.

**`[config] EFFECTIVE`** — one declarative table of env name → the LIVE value that ran. A knob whose
effective value is an AND with something else reports the AND, not the request.

**`[config] DERIVED`** — separates knobs that are following another knob from knobs that were set
explicitly.

**`[config] COUPLING`** — prose lines for knobs whose effective value was decided by ANOTHER knob, e.g.
`EPOCHS` setting both run length AND the cosine horizon (two runs differing only in `EPOCHS` are two
different schedules), and the `TOK_ANCHOR`-is-inert warning.

**`[config-audit]`** — three layers: (a) **typo** — set but never read; (b) **unverified** — set and
read but not checked against a live value; (c) **never fired** — a loss-weight knob that was ON and
whose term never entered the loss (`DIV_W`, `IND_W`, `CHAIN_SUP`, `TOK_ANCHOR`). Layer (c) prints
*"This run is identical to `<knob>`=0."* Family detection was hardcoded until `c909918`.

---

### Process

**arm** — a named flag-set in `longrun.sh`'s `_flags_for` (46 of them). An arm name that `_flags_for`
does not know once ran the DEFAULTS under the misspelled name (`b6952da`).

**grid** — run a list of arms sequentially. **seeds** — the same arm at N seeds. **repeat** — the same
arm and seed N times, which is how the 1.227 b/B spread was found.

**smoke** — every pilot arm at 40 kB / 3 epochs: does each still REACH ITS REPORT. It catches crashes,
not changes. *"Reading them as a result is how a smoke test turns into a wasted day."* Use `equiv.sh`
for inertness.

**the gate** — `preflight.sh` plus the smoke run: what must pass before GPU time is spent. Includes the
knob trap (a set-but-unread knob fails the gate).

**pilot / `pilot-add`** — `longrun.sh pilot` is the MB-scale proof of concept (60 MB English, 8 epochs,
~15–20 min) run before any GB run. `pilot-add` adds a new area to an already-trained checkpoint and
measures what it cost — the only continual-learning workflow. Its `$OUT` directory was never created,
so a finished run lost its entire report (`40de03d`), which is why the one real continual run's
numbers come from a terminal copy.

**probe sidecar (`probe.pt`)** — the per-domain held-out probe saved beside every checkpoint, keyed by
domain NAME with a deterministic seed. This is what makes ACROSS THE RUN BOUNDARY possible and what
`holdout.py` reconstructs from when the log is lost.

**best checkpoint (`.best`, `BEST_TRACK`=1)** — the best-by-held-out snapshot, distinct from the final
model. Generation sampled the LAST model, never the best, until `3f67bfc`. Beware `18fdd6c`: "best at
step 6000" was largely the yardstick moving — `_VALT` was frozen in an obsolete segmentation.

**`SAVE_CKPT`** — checkpointing. `SAVE_CKPT=0` wrote checkpoints to a directory literally named `0`
(`7ca2061`), and toggling it changed a result by **1.594 b/B** on the same seed — one of the clearest
demonstrations of the noise floor.

---

## 4. KNOB FAMILIES IN `_SPEC`

`_SPEC` groups its 310 knobs by comment tag. What each family controls:

| Family | Prefixes | Controls | Notes |
|---|---|---|---|
| **data** | `CORPUS_CAP`, `DATA_*`, `DISK_STREAM`, `DOMAINS`, `EPOCHS`, `PHASE*`, `STREAM_LEN`, `VAL_FRAC`, `WIN` | the corpus, how the stream is spliced, the phase schedule, the held-out fraction | `EPOCHS` is coupled to the LR horizon — it is not just run length |
| **tokenizer** | `TOK_*`, `VMAX`, `SEED_VOCAB`, `SEED_PASSES`, `GROW_PASSES`, `MIN_PAIR`, `MAX_TOK`, `RETOK_*`, `WARMSTART*`, `LOSS_MASK_DEAD` | vocabulary construction, online minting, the mint gate, probation, composition, re-segmentation | most of the family is off at defaults |
| **fabric** | `FAB_*`, `CHAIN_*`, `ROUTE_*`, `EXP_DOM_*`, `SOCIETY`, `EXPERTS`, `ENS_K`, `IND_*`, `DIV_W`, `PONDER*`, `AFF_MIN` | the expert population: size, growth, culling, replication, routing, chaining depth, per-expert LR | the largest family; `FAB_GROW`/`FAB_N0`/`FAB_NMAX` alone decide which 2x2 arm you are running |
| **domains** | `DOM_*`, `MANAGE*`, `SEG_*`, `SHIFT_*`, `MERGE_FRAC`, `NEW_DIST`, `SUSTAIN`, `SELF_ORG`, `TOKC_DECAY` | the assembler: creation radius, merge/cull/fold policy, splice-segment shape, management cadence | `MANAGE_EVERY`=500 was once longer than the whole run (`510c695`) |
| **memory** | `MEM_*`, `KEY_*`, `REKEY_*`, `EVICT`, `WRITE_*`, `RECON_*`, `VERIFY*`, `WRONG_*` | the store: capacity, key source, write gating, eviction, rekeying, verification | `WRONG_*` is the retired "B" (§1.1) |
| **encoder** | `ENC_*`, `SIG_*` | the signature encoder: batch, warmup, regularisation, signature width and space | `SIG_WIN` must cover the loop stride or the encoder labels material it never read |
| **world** | `WORLD_*` | the forward-dynamics world model and its population | ON by default, not measured since 2026-07-29 |
| **optim** | `LR*`, `ACCUM`, `BATCH_W`, `AMP`, `TF32`, `SEED`, `DROPOUT`, `WEIGHT_DECAY`, `BAL_*` | optimiser, schedule, precision, batching | `LR_SCHED`/`LR_EPOCHS` produced the one architecture-independent effect far outside seed spread |
| **capacity** | `GROW_CAP*`, `GROW_LIFT` | the soft caps that lift on a plateau | **INERT AT DEFAULTS** (`GROW_CAP=0`) |
| **report** | `BENCH`, `BEST_TRACK`, `COH_*`, `EVAL_N`, `GEN_*`, `HOLDOUT_N`, `PROBE*`, `PROFILE`, `RATE_EVERY` | end-of-run measurement only — *nothing here changes training*, which is exactly the invariant `c76dc74` found violated | |
| **plumbing** | `CKPT_EVERY`, `DEVICE`, `D_MODEL*`, `HEADS`, `LAYERS`, `MAXLEN`, `MODEL`, `RESUME`, `SAVE_CKPT` | paths, device, model shape, checkpointing | `MODEL=transformer` has run twice and neither run means anything yet (`bf53d40`) |
| **misc** | `EXPERT_*` (legacy bank), `GENUINE_*`, `COMP_*`, `CULL_MODE`, `TEMP`, `TOPK`, `USE_DECAY`, `GROW_*`, `N_PROCESSES`, `VAL_CAP`, … | the not-yet-grouped remainder, including the entire legacy `ExpertBank` path | most of `EXPERT_*` is unreachable at defaults (`EXPERTS=0`) |

---

## 5. TWO OPEN QUESTIONS, RESOLVED

### Q5 — which `_SPEC` knobs have NEVER been set by any harness, arm, or documented command?

Method: parse `_SPEC` from the AST of `self_organize.py` (310 knobs at HEAD, no duplicates), then
search for a shell/env **assignment** (`KNOB=`) rather than a mere mention.

- **Crossed against `longrun.sh`, `rerun.sh`, `equiv.sh` and `runs.csv` only (the question as
  written): 223 of 310 knobs have never been set.** That is 72% of the configuration surface.
- Widening the search to every documented command anywhere in the repo — `preflight.sh`,
  `sweep_domains.sh`, `sweep_domain_grid.sh`, `bench_gpu.sh`, `run_full_unfrozen.sh`, `README.md`,
  `STATE.md`, `CL_TESTBED.md`, `docs/`, `handoff/`, `garry/`, **and the full 267-commit log**
  (which is where most GPU command lines live) — **90 knobs have never been set anywhere, by anyone,
  in the project's whole history.** They have only ever run at their declared default:

  `AFF_MIN`, `BAL_FLOOR`, `BEST_TRACK`, `CENT_EMA`, `CHAIN_DEPTH0`, `CHAIN_EPS`, `CHAIN_PATIENCE`,
  `CHAIN_STAGE_MAX`, `COMP_EMA`, `DECAY_EVERY`, `DOM_CULL_EMPTY`, `ENC_CREG`, `ENC_VREG`,
  `EXPERT_NULLS`, `EXP_DOM_FRAC`, `FAB_BALANCE`, `FAB_BIRTH_WIN`, `FAB_CENT_TOPK`, `FAB_DISCOVER`,
  `FAB_EMB_HID`, `FAB_EMB_VAR`, `FAB_ERR_FAST`, `FAB_ERR_SLOW`, `FAB_FAIL_TOL`, `FAB_HALT_MAX`,
  `FAB_HID_MULT`, `FAB_LR_AMIN`, `FAB_LR_CYCLE`, `FAB_LR_GAMMA`, `FAB_LR_MAXR`, `FAB_MUT`,
  `FAB_MUT_BIG`, `FAB_MUT_BIG_P`, `FAB_NEW_WIN`, `FAB_NORM_ONLY`, `FAB_PARENT_MAX`, `FAB_PRESSURE`,
  `FAB_RAMP`, `FAB_RAMP_TO`, `FAB_RECOVER_MAX`, `FAB_RECOVER_MIN`, `FAB_RESCUE`, `FAB_SHIFT_TOL`,
  `FAB_SPAWN`, `FAB_SPAWN_FLOOR`, `FAB_SPAWN_MULT`, `FAB_XOVER`, `FAB_Z`, `GENUINE_SIL`, `GROW_CAP`,
  `GROW_CAP_EVERY`, `GROW_CAP_FAB`, `GROW_CAP_FAB0`, `GROW_CAP_PLATEAU`, `GROW_CAP_VOCAB`,
  `GROW_CAP_VOCAB0`, `GROW_LIFT`, `INFO_NULLS`, `LR`, `LR_MIN_FRAC`, `MEM_CONF0`, `MEM_GATE`,
  `MEM_PROBE_EVERY`, `MEM_PROBE_N`, `MEM_W`, `N_PROCESSES`, `PHASES`, `PHASE_W`, `RECON_HID`,
  `RECON_TOK`, `SEED_PASSES`, `SIG_PROJ_BPT`, `TOK_MINT_GATE_K`, `TOK_PROBATION_MIN`, `TOPK`,
  `USE_DECAY`, `VAL_CAP`, `VAL_FRAC`, `WARMSTART_OPT`, `WORLD_HID`, `WORLD_K`, `WORLD_LAT`,
  `WORLD_N0`, `WORLD_NMAX`, `WORLD_ROUTE`, `WORLD_VAR`, `WRITE_GATE`, `WRONG_MARGIN`, `WRONG_MIN_N`,
  `WRONG_THRESH`.

  Three of these deserve calling out by name:
  - **`LR` itself has never been set.** Every run in the project trained at the declared default
    **2e-3**. Only `LR_SCHED` / `LR_EPOCHS` / `LR_RESTARTS` were ever varied. `1593c70` ("there was no
    learning-rate schedule — 2e-3 constant for 48,000 steps") is about the schedule; the *peak rate*
    was never moved either.
  - **`GROW_CAP` and its entire six-knob family** have never been set, so the soft-cap mechanism
    (`e2db890`, `41d2c5d`) **has never executed outside a smoke test**.
  - **The whole `WORLD_*` sizing family** (`_HID`, `_K`, `_LAT`, `_N0`, `_NMAX`, `_ROUTE`, `_VAR`) has
    never been set, so the world model has only ever run in one shape.

  Note `FAB_RAMP` and `FAB_RAMP_TO` on this list: the growth ramp whose latching defect
  (`ff0f0fa`) reshaped every population figure in the project was **never once tuned**.

### Q13 — are `TOK_ANCHOR` / `TOK_ANCHOR_TAU` / `TOK_ANCHOR_USES` still printed on the `[config] EFFECTIVE` line while inert?

**Yes — and this is now stated three separate times in the same report, deliberately.** Verified by
reading `self_organize.py` at HEAD (`92a967b`):

1. **They are still on the EFFECTIVE line, unconditionally.** Lines 4349–4350 place
   `("TOK_ANCHOR", TOK_ANCHOR)`, `("TOK_ANCHOR_TAU", ...)` and `("TOK_ANCHOR_USES", ...)` in the
   `_EFF` table with no `TOK_COMPOSE` guard. Every run prints `TOK_ANCHOR=0.05 TOK_ANCHOR_TAU=4000
   TOK_ANCHOR_USES=400` whether or not the term exists.
2. **A COUPLING line says so explicitly.** Lines 4461–4465: when `TOK_ANCHOR > 0 and not TOK_COMPOSE`,
   the report prints that these three *"appear on the EFFECTIVE line but have NO EFFECT in this run:
   the anchor is a method of ByteComposer, which is constructed only when TOK_COMPOSE=1 and is 0 here,
   so model.compose is None and the anchor term never enters the loss."*
3. **The never-fired audit `fec2285` added does fire today.** Lines 4299–4311 iterate
   `("DIV_W", "IND_W", "CHAIN_SUP", "TOK_ANCHOR")` and, for any weight that is >0 whose `_term` never
   fired, print `[config-audit] !! TOK_ANCHOR=0.05 was ON and its loss term NEVER FIRED -- it is gated
   on TOK_COMPOSE, which is 0 here, so model.compose is None and the term never enters the loss. This
   run is identical to TOK_ANCHOR=0.` Since `TOK_COMPOSE` defaults to 0, `_anc` at line 5158 is always
   `None` and `_term("TOK_ANCHOR", ...)` at line 5181 is never called — **so the audit fires on every
   default run.**

The commit's own account of why: *"that is exactly how TOK_ANCHOR=0.05 came to be printed on the
EFFECTIVE line of every run in this project while contributing nothing"* — the earlier audit covered
`DIV_W`, `IND_W` and `CHAIN_SUP` only. **`TOK_ANCHOR` and its two release knobs are INERT AT DEFAULTS,
loudly.**
