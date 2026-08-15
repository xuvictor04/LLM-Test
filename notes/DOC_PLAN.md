# DOC_PLAN — how this project gets written up

Plan only. No section below is written yet. Written 2026-08-15 against branch `rm-predict`,
HEAD `a5cc7ea` (259 commits, 7.6k lines of commit message).

## THE CAVEAT (goes verbatim at the top of every file, and again beside every number)

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are
> tiny — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has
> reached 1.227 b/B (`33a9299`), which is larger than the gap between any two architectures
> ever compared here. Several confidently-stated findings were later retracted when the
> measurement turned out to be broken. Every entry records **what was observed under these
> conditions**, never **what is true**. Where a result was later invalidated, the invalidation
> is stated next to it, not in a footnote.

Enforcement rule for every executing agent: a claim without (a) the commit that produced it,
(b) n, and (c) whether it predates the instrument fixes `c76dc74` / `5f4f117`, does not go in.

---

## FILE LAYOUT (exact names, under `notes/`)

| # | File | Section | Effort |
|---|------|---------|--------|
| 0 | `notes/00_INDEX.md` | entry point, caveat, reading order, provenance | S |
| 1 | `notes/01_TIMELINE.md` | dated commit spine every other file cites | L |
| 2 | `notes/02_IDEAS.md` | **A** — the researcher's ideas and what happened to each | M |
| 3 | `notes/03_EXPERIMENTS.md` | **B** — what was tested, why, and the outcome | L |
| 4 | `notes/04_RESULTS.md` | **C** — results tables, each caveated | M |
| 5 | `notes/05_ERRORS.md` | **E** — every error, fixed or not, and how | XL |
| 6 | `notes/06_CONTINUAL_LEARNING.md` | **F** — the target, and what is known about it | M |
| 7 | `notes/07_WIP.md` | **D** — unfinished, known-broken, never-run | M |
| 8 | `notes/08_GLOSSARY.md` | **G** — the project's own vocabulary | M |
| 9 | `notes/09_COMMENT_AUDIT.md` | the source-comment migration pass | L |

Supporting, not prose:
- `notes/_evidence/commit_log.txt` — `git log --format='%H%n%ad%n%s%n%b%n---' --date=short rm-predict`.
  Generate this FIRST. The commit log is the project's primary record and it exists in exactly
  one place. Every file cites into it by hash.
- `notes/_evidence/runs_snapshot.csv` — copy of `runs.csv` at the commit the docs were written,
  so the tables in `04_RESULTS.md` can be re-derived later even after the CSV grows.

Effort key: S ≈ under an hour, M ≈ half a day, L ≈ a day, XL ≈ two days.

---

## 0. `notes/00_INDEX.md` — S

**Purpose.** The one page someone reads first. Not a summary of findings; a map plus the caveat.

**Required contents.**
- The caveat, in full, before anything else.
- What the system is, in five sentences: byte-level LM, dynamic BPE that mints during training,
  a routed population of low-rank experts (the Fabric), a self-organising domain assembler,
  an editable external memory, a world model.
- What it is FOR, quoted from `9d90416`: (1) the output, generation is the deliverable;
  (2) continual learning without exorbitant forgetting; (3) the machinery, only insofar as it
  moves 1 and 2. Domain counts, purity, silhouette, V-measure and specialization are
  **diagnostics, not targets** — and the record shows steering by them consumed weeks.
- Reading order, and which files are safe to read alone (08, 07) vs which need 01 first.
- **Provenance and staleness warning**: `README.md`, `STATE.md`, `CL_TESTBED.md`, `docs/`,
  `handoff/` and `garry/` all date from 2026-07-21..24 and describe a superseded workflow
  (`run_full_unfrozen.sh`, the "B" naming, the "-0.0009 collateral" headline). They are
  historical. Say so here, because they currently read as current.

**Sources.** `9d90416`, `48695599`, `README.md`, `STATE.md`.

---

## 1. `notes/01_TIMELINE.md` — L

**Purpose.** The spine. One line per commit that changed what was being measured, in date order,
so that "which code produced this number" is answerable. Everything else cites this file.

**Required contents.**
- A table: date | short hash | one-line subject | what it changed about the SYSTEM | what it
  changed about the MEASUREMENT. The last column is the one that matters; many commits changed
  only the instrument, and those are the ones that invalidate earlier numbers.
- Explicit **epoch markers** — the dates before which results are not comparable to after:
  - `a5cd9ed` (07-24) D_MODEL_B unread — every earlier benchmark ran at d=128.
  - `c8ba635` (07-26) cadences below the batch accumulator never fired at BATCH_W>1.
  - `7a42f90` + `51889b7` (07-29) six subsystems were off by default in every prior run.
  - `1593c70`/`c33f078` (08-05) the LR schedule is introduced; everything earlier ran at a
    constant 2e-3 for 48k steps.
  - `5f4f117` (08-07) eval passes stopped training the router.
  - `c76dc74` (08-13) five diagnostic→training leaks closed, stream gets its own RNG.
    *"No result in the record predates these fixes safely."*
  - `0f96784`/`79dac6c` (08-13) VMAX stopped re-rolling every weight; per-module seeds.
  - `91fd815`/`a5cc7ea` (08-15) founding experts stopped being immortal.
- Phase headings, roughly: (i) 07-21..22 Verification/reconstruction; (ii) 07-23..25 world model,
  performance, GH200 readiness; (iii) 07-25..29 the domain-assembler campaign; (iv) 07-29..08-02
  the subsystems-were-off audit and the metric battery; (v) 08-03..05 the expert population at
  scale, routing, chaining; (vi) 08-05..07 the LR/tokenizer divergence hunt; (vii) 08-07..12
  config registry, equiv, the vocabulary arms; (viii) 08-13..15 instrument fixes and the
  population 2x2.

**Sources.** `notes/_evidence/commit_log.txt`, whole. Read it start to finish once.

**Effort.** A day. 259 commits, but only ~120 need a row.

---

## 2. `notes/02_IDEAS.md` — M (section A)

**Purpose.** The researcher's ideas, in the researcher's framing, and the fate of each. This is
the file that answers "what did I ask for and what became of it".

**Required contents.** One entry per idea, with this schema:

    IDEA — as stated (quote the commit's own wording)
    WHEN / WHERE   commit hash, date, and the handoff/ file if one exists
    WHAT WAS BUILT  code, flag name, default
    WHAT HAPPENED   measured / not measured / built and inert / rejected / superseded
    STATUS AT HEAD  on by default | off by default | unreachable | never built

At minimum these, all traceable in the log:
1. North star: a small model that learns and reasons with an ever-expanding updatable knowledge
   base; **growability is the sacred invariant**; language is a benchmark, not the endpoint (`12a4fcd`).
2. Redundant/interchangeable expert base WITH emergent subspecialties — not a binary (`c8705a8`).
3. Subcontracting: no expert solves the whole task; work is spread across the router base (`628dfc5`).
4. Senses live at the lowest tokenizer layer; Sense = modality, not polysemy (`628dfc5`, `3500b78`).
5. Tool-experts: experts as scripts, self-authored when a procedure recurs (`b1e6d1f`). Not built.
6. Router-as-embedder; the content-vs-functional similarity keystone (`b1e6d1f`, probed `5cad71a`).
7. The unifying primitive: subtokenize → embed → match → discover → crystallize (`b1e6d1f`).
8. Surprise is a learning driver, not truth (`4315c94`) — the reframe that renamed B→Verification.
9. Reverse embedders / verification by reconstruction (`4315c94`, built `fbdcd50`, failed in-loop
   `9df85b8`, `d7c141b`, `f5303d6`).
10. Reject a strict per-domain memory quota; memory pressure → grow/retrain/split (`5c711cf`).
11. A GENERAL, physics-like, multimodal world model built inside the system (`39c6765`, `b6c0076`).
12. Active learning: self-generated reference → prompt → reproduce closed-book (`8143537`). Not built.
13. Partial compartmentalization: provenance without partition, leak on purpose (`8143537`;
    realised as per-expert memory WRITES with global READS, `242e021`).
14. "The society, allowed to loop over and over" — the correction that produced `CHAIN_ROUTE=soc`
    (`7b18214`), now the default.
15. Newborns should inherit connected sections of other experts → rank-slice crossover (`580cd62`).
16. Minted tokens should KEEP parameters but start at their composite — the correction to
    `TOK_COMPOSE` (`e8df6fe` → `ed04aac`).
17. Doubt about the tokenizer explanation, which produced the LR-schedule finding (`1593c70`).
18. "Why measure the noise? find the issue" — which produced the diagnostics-mutate-training
    discovery (`c76dc74`). Record this one prominently: the user's instinct was right and the
    planned measurement would have been wasted.
19. Selection should raise the mutation rate, not only prune → `FAB_RESCUE` (`e2db890`).
20. A meaning gate on minting (`c214c21` → `93c1733` → `1a113f5` fail-open).
21. Probationary minting: mint, train, then judge (`9f8412b`).
22. Do NOT optimise the tokenizer or expert count for their own sake (`9d90416`, `98f19fa`).
23. Breadth cap: an expert may serve at most X% of live domains (`763e9f2`).
24. Designed but never built: multimodality, the observability dashboard, corroboration-based
    wrongness, release-don't-kill deletion, `retire_stale` wiring —
    see `handoff/designed-but-not-built/` (7 files).

**Sources.** `handoff/design-directions/` (11 files), `handoff/decisions/` (~9),
`handoff/open-questions/`, `handoff/NORTH_STAR.md`, and the commits above. The handoff/ tree is
the researcher's own framing and should be quoted rather than paraphrased.

---

## 3. `notes/03_EXPERIMENTS.md` — L (section B)

**Purpose.** What was actually run. Configuration, the question it was meant to answer, the
result, and whether the result survived.

**Required contents.** One entry per experiment, schema:

    NAME / arm         the name in longrun.sh _flags_for, or the commit's own name
    CONFIG             the flags, verbatim, plus the harness defaults they inherit
    QUESTION           what it was trying to decide
    n                  seeds / runs. Say "n=1" out loud.
    RESULT             the numbers as printed
    STATUS             stands | superseded | INVALIDATED (and by what)
    INSTRUMENT ERA     pre- or post- c76dc74 / 5f4f117

Groups to cover:
- **Verification / reconstruction**: standalone CPU probe (AUC 0.978/0.980), the product-loop
  failure (0.3–0.5% precision), the 5x-steps run that ruled out undertraining. `213820d`,
  `c88fb7a`, `9df85b8`, `d7c141b`, `f5303d6`.
- **World model**: DynamicsPopulation, the honest negative vs a param-matched monolith (-5.1%),
  the feedback link, the first full-stack reading ("beats baseline -84.7%, latent std 0.07").
  `74d10d8`, `2cf106d`, `a1767b7`, `51889b7`.
- **Performance / equivalence A/Bs**: KEY_PREGATE (bit-identical), ENC_FUSE (equivalent, not
  bit-identical, ~1e-5), KEY_BATCH (82/23237 rows, 4.2e-8), SIG_BATCH (bit-identical on the
  stress case, +10.4% single-domain), REKEY_CHUNK and AMP=bf16 both rejected on measurement.
  `457c9d0`..`ffb6bf8`.
- **The domain-assembler campaign** — the largest block, and the one whose target was later
  declared wrong. Configs A/B/C/D (`6397041`), the encoder loss floor (`510c695`), MANAGE_MERGE
  0.12 vs 0.45 (`13e787a`), segment length vs V (`3f44ce3`), SEG_CONTIG (`98f19fa`),
  ENC_VREG (`c1aadda`), the informativeness test and its null (`8914dd1`, `3e2393d`), the domain
  prior (`7b481a1`), stability across seeds (`80a4533`).
- **The 18-arm grid** (`ffd39b8`): full table, plus "every chaining arm is worse than FABRIC=0".
- **Chaining vs society vs chained-society**: `33355b2`, `c4000c6`, `9b179b5`, `7b18214`,
  `53fbae5`. Include H(hop1|hop0) = 0.007–0.058 for transition arms vs 0.533 for soc-loop.
- **Chain credit assignment**: CHAIN_SUP / CHAIN_CURRIC / CHAIN_STATE_Q — all three measured,
  all three off, and the curriculum result later withdrawn because the code never ran (`7e9612d`,
  `e0ce4f7`).
- **LR**: cosine vs none (`c33f078`), LR_EPOCHS (`9fabba4`), LR_RESTARTS (`c341921`, `fec2285`),
  the restart-late-in-training swing (`ac79e92`), LR_DECAY (`91fd815`).
- **Tokenizer**: TOK_MINT_UNTIL freeze (`8c8d20b`) and its later reversal (`bdce727`, `707f1af`),
  TOK_COMPOSE (`e8df6fe`→`ed04aac`→`be50e3a` back off), WARMSTART_MODE 18-trial result vs the
  end-to-end disagreement (`c92d104`), TOK_MINT_NOVEL, the p(b|a) gate and its fail-open
  (`93c1733`, `1a113f5`), probation (`9f8412b`), retok-on-unchanged-vocabulary (`046fd81`).
- **VMAX × EPOCHS 2x2** (`0279709`) and why it is not attributable (`0f96784`).
- **The population 2x2** (`cc0a377`) — arms A/B/C/D, 3 seeds each. The cleanest experiment in
  the project; give it its own subsection.
- **Continual learning**: the pilot→pilot-add chain (`61b9d23`), the one real run (`a9d7258`).
  Cross-reference `06_CONTINUAL_LEARNING.md` rather than duplicating.

**Sources.** commit log; `longrun.sh` `_flags_for` (46 arms, lines ~129–275); `runs.csv`; 481 logs
under `runs/` (note: all but the `equiv_*` pair predate 2026-08-08 — the recent GPU results exist
only in commit messages and `runs.csv`).

---

## 4. `notes/04_RESULTS.md` — M (section C)

**Purpose.** The tables. Nothing here without its conditions attached.

**Required contents.**
- The 43 rows of `runs.csv`, rendered, with **two columns added that the CSV does not have**:
  `instrument era` (pre/post `c76dc74`) and `status` (stands / invalidated / uncontrolled).
- Per table, a header block: corpus, epochs, VMAX, seeds, harness mode (`SAVE_CKPT` on/off —
  it changed a result by 1.594 b/B once), and the commit.
- Tables to build:
  1. The population 2x2 (`cc0a377`): A 2.117±0.326 / B 1.999±0.080 / C 2.091±0.180 / D 3.384±2.074.
     State plainly that B is the best on record — and immediately that `a5cc7ea` showed B ran with
     no culling at all.
  2. The VMAX × EPOCHS 2x2 (`0279709`) — with the `0f96784` finding attached: VMAX re-rolled every
     weight, so the arms were three different initialisations and the comparison is not attributable.
  3. The dead-row series (0% → ~2.2, 41% → 3.561, 75% → 6.114) — **marked as uncontrolled**. The
     first controlled test (`e9f2e58`, LOSS_MASK_DEAD) gives +0.060 against a combined SE of 0.055,
     1.1 sigma. The monotone story is not established.
  4. LR: cosine 2.101 vs none 4.193, and the constant-LR oscillation 3.4–7.8 (`c33f078`).
     This is the one architecture-independent effect far outside seed spread.
  5. Seed spread (`6bd226c`, `33a9299`): 0.060 / 0.174 on paired pilots; 1.227 across four runs of
     one nominally identical arm. Put this table BEFORE the comparison tables, not after.
  6. Component contributions: eval-time knockout vs retrained ablation. FABRIC knockout +0.709
     (`7a42f90`) vs retrained 3.089 vs 3.090 (`e60b8e0`). The knockout number was used to justify a
     default and was retracted (`9d90416`). Memory: +2.5 early, later net-negative (`242e021`,
     `0b08b74`), -0.111 in the continual run.
  7. The 18-arm grid summary (`ffd39b8`).
  8. Domain metrics across the campaign (live count, purity, homogeneity, completeness, V,
     recurrence) — with the `efb818a` warning that V against the four seeded corpora was the wrong
     target, and `5e02cfc`'s retraction that purity rises with fragmentation.
  9. The anchors: uniform / order-0 / order-1 / model, on held-out (`aac17f7`). Every held-out
     figure should be quoted against its OWN run's order-1, because the corpus changed
     (`ac79e92`: order-1 3.440 → 3.747 after a re-fetch).
- A short "what survives" list, and it should be short. Candidates: determinism given
  (config, commit, seed) on CPU; the LR schedule effect; the retok-on-unchanged-vocabulary cost;
  arm B's low spread; and the code defects themselves, which are facts about the source.

**Sources.** `runs.csv`, `runs.py` (column semantics — every column is parsed from a log, never
typed), commit log.

---

## 5. `notes/05_ERRORS.md` — XL (section E)

**Purpose.** The complete error catalogue. This is the largest and most valuable file: the project
is largely a record of defects found, and several classes recurred.

**Schema per entry** (keep it rigid — there are ~90):

    WHAT           the defect, in one sentence
    CLASS          silent no-op | unread knob | dead default | cadence | instrument-mutates-training
                   | resume/persistence | selection | measurement/metric | harness | crash
    FOUND          commit + how it was found (by reading / by a gate / by a run failing / by audit)
    BLAST RADIUS   which results it invalidates
    FIX            what was changed; or NOT FIXED
    RECURRED?      whether the same class came back later

**Organise by class, not chronologically.** The classes, with the entries each must contain
(hashes are the minimum set — the agent should sweep the log for more):

1. **Knobs read by nothing / set and never read.** `D_MODEL_B` — every direct run silently at
   d=128 (`a5cd9ed`); 8 of 36 sweep knobs unread (`6397041`); `TOK_MINT_GATE_K` never read through
   `_env` (`904742c`); a dead module-level `ROUTE_T` with a different default (`3e67b5d`);
   six GROW_CAP* knobs set on a build that predated them (`c9099188`). The countermeasures:
   `preflight.sh` knob trap, the 279-knob `_SPEC` registry (`6f4c534`), `levers.py` (`f279fd0`),
   the typo/unverified/never-fired three-layer audit (`99ba0f4`, `b14d60e`, `fec2285`).
2. **Defaults that silently decided the experiment.** `FABRIC=0` in every run (`7a42f90`);
   five more subsystems off (`51889b7`); `PHASED=0`, shipped in commit 1 and never once turned on
   (`c316813`, `a5ac033`); `MANAGE_MERGE=0.12` overriding the fallback for the whole project's
   life (`13e787a`); `MANAGE_EVERY=500` longer than the run (`510c695`); `SEG_MIN/SEG_MAX` chosen
   when WIN was bytes (`3f44ce3`).
3. **Cadence bugs.** Four cadences below the batch accumulator, dead for every BATCH_W>1
   (`c8ba635`); `maybe_deepen` the same, so a reported "staged depth did not help" came from code
   that never ran (`e0ce4f7`); `_due` is not a predicate — calling it twice consumes the event,
   which killed retokenisation entirely for three 18-epoch runs (`d0728fe`) and was armed for
   `grow`/`probation` (`0f96784`); `RETOK_EVERY=0` silently disabled signature batching (`79dac6c`);
   the adaptive warmup's plateau test unreachable when MIN==budget (`5a72970`).
4. **Diagnostics that mutated training state.** The headline class. The independence test removed
   the busiest expert and never restored it, so every subsequent eval — including the generations
   used to judge coherence — ran a mutilated model (`535f5f6`); `ground_update` on a fabricated
   zero gist dragged centroids to the origin on every eval pass (`5f4f117`); the five leaks of
   `c76dc74` (eval-time exploration, eval-time utilization recording, the timing probe's
   `.backward()`, halt/mass EMAs averaging eval passes, probes drawing from the global RNG) — and
   the mechanism that made it matter: `build_stream` draws segment lengths from the global RNG, so
   how much you measured decided what you trained on; `_sep_probe` (`e0dbf0c`).
5. **Resume / persistence.** Resume re-seeded the tokenizer from scratch so a restored embedding
   was indexed by a different vocabulary (`59c6cf4`); the checkpoint recorded `tok_path` and never
   read it back, so resume paired weights with another run's merges — or with a fresh 512-token
   vocabulary (`2ba3ac1`); `asm.born`/`asm.act` unsaved, so every resumed run crashed at the first
   merge (`c8b6991`); an empty param group appended per growth event discarded every Adam moment on
   every resume (`dec9fb3`); the per-expert memory partition would have been silently destroyed on
   restore (`ef412e2`); `fab_born` unpersisted, so restored experts were immortal (`a5cc7ea`).
6. **Populations that could not be culled.** The fabric had no culling at all — `router.manage` is
   gated on `EXPERTS`, mutually exclusive with `FABRIC` (`2a262a2`); which also explains
   "COMPETENCE PROTECTION spared 0" in every run. Domains: cumulative `size` made any domain over
   15 windows uncullable (`5e02cfc`); the empty-domain AND-clause could never be satisfied
   (`763e9f2`). Founders had no birthday and read as age 0 forever, so the founding population was
   permanently immune (`91fd815`, `a5cc7ea`) — and the direction of the fallback was the dangerous
   one. Growth: the ramp never latched, refilling every cull within 187 steps (`ff0f0fa`).
7. **Measurement and metric errors, with the retractions.** Purity rises monotonically with
   fragmentation — "domain assembly works, 0.54→0.96" retracted (`5e02cfc`); the completeness
   formula was homogeneity (`b1fe6ed`); the COLLAPSE CHECK could not separate a healthy encoder
   from a suspect one and was retracted (`ab3a311`); profile attribution divided a window by the
   whole run (`96236e7`); domain sizes read from a subsampled `assigns` and separation was a min
   order statistic (`2cffa47`); coherence was a four-sample statistic and three mutually
   contradictory claims were made from it (`6f24bed`); the order-1 anchor was first fitted on the
   held-out text (`aac17f7`); the informativeness null was a single permutation and the verdict
   flipped on noise (`3e2393d`); "1 of 4096 experts used" was a 32-window probe (`b610b89`);
   the identity-collapse diagnostic was a stale variable captured on the path the collapse
   prevents (`b610b89`); the training-curve verdict read its own sign backwards (`a5c893a`);
   `_VALT` was frozen in an obsolete segmentation, so "best at step 6000" was the yardstick moving
   (`18fdd6c`); bytes/token was a mean over the vocabulary, and the sign of the bias depends on
   vocabulary size (`37100fb`, `8a8fb69`); `SIG_PROJ_BPT` pinned at 2.4 suppressed the coverage
   warning (`e2001782`); memory contexts were queried in a segmentation they were not written in,
   82.3% mismatch after one growth step (`8bdeca4`).
8. **Attribution errors — measuring at the wrong scale.** "The weight-prediction term is 2% of the
   routing decision" was measured on a 64-expert toy; at 4096 it is 93% (`ffd39b8`). The tokenizer
   explanation for divergence was presented as a finding and was untestable at the time
   (`1593c70`). The whole `frozen`-vs-`frozen_nr` pair, quoted as the largest single effect on
   record, was not a clean single-knob comparison (`79dac6c`).
9. **Harness / plumbing.** `SAVE_CKPT=0` wrote checkpoints to a directory literally named `0`, and
   it got committed (`7ca2061`); arm flags placed before hardcoded env were silently discarded, so
   `grid base VMAX=8192` ran at 2048 and named the log 8192 (`5f4f117`); "already complete,
   skipping" compared only ARMFLAGS, so an 18-epoch sweep skipped and then reported the 8-epoch
   numbers under an 18-epoch banner (`42d8686`); an unknown arm name ran the defaults under the
   misspelled name (`b6952da`); six arms were configured to guarantee dead rows (`b6952da`,
   `25c37eb`); `equiv.sh`'s completion marker matched line 8 of every log (`37ecb20`); the DIRTY
   flag counted untracked files (`4da76b8`); the smoke test duplicated the arm definitions and had
   drifted, and `_flags_for` was defined inside another `case` branch (`136461c`); `pilot-add`
   never created `$OUT`, so a finished run lost its entire report (`40de03d`); `runs.py` stopped
   being able to ingest any post-fix log (`ed8af6b`); `seeds`/`repeat` never fetched the corpus
   (`adbc07a`); `prompt.py` was completely dead for several commits (`763e9f2`) and broke again on
   per-window routing (`e44b5b0`) and on the chaining tuple (`7b28570`).
10. **Self-inflicted regressions during this work.** Recomputing `SIG_WIN` live killed both pilot
    arms and the gate passed it (`2a682d7`); the `main()` split broke the import and was reverted
    at a 136-value seam (`13099a1`, `6732448`, `9c59a84`); `_units` was rewritten into infinite
    recursion and caught only by an AST assertion (`343bfd7`); a two-character name collision
    (`_hb`) silently deleted the retention section from every run using the new knob (`98f6c66`);
    the retok guard killed re-segmentation entirely (`d0728fe`); the mint gate starved the
    vocabulary in the first real pilot (`1a113f5`); a `KeyError` armed by a rename 30 minutes
    earlier (`79dac6c`).
11. **Not fixed / still open.** See `07_WIP.md` and cross-link; do not duplicate.

**Sources.** The whole commit log. Read every message; the defects are usually in the body, not
the subject. Grep aids: `-i "retract\|withdraw\|I was wrong\|does not stand\|silently\|never\|inert\|no-op"`.

**Effort.** Two days. This file is the reason the documentation exists.

---

## 6. `notes/06_CONTINUAL_LEARNING.md` — M (section F)

**Purpose.** The stated target, treated as its own subject. It is the thinnest-evidenced part of
the project and the file must say so.

**Required contents.**
- **The audit finding that started it** (`c316813`): of fourteen report sections, exactly one bore
  on catastrophic forgetting, it was behind `PHASED=1`, and `PHASED` had never been executed in any
  run. Everything being tuned — purity, homogeneity, completeness, V, fragmentation, silhouette —
  scored the ORGANISATION of a store against categories the project spliced in itself.
- **The mechanisms built**: `PHASED` + the generated phase schedule (`c411ac7`, `a3ed1a9`);
  the whole-stream retention metric and its correction to a per-process conditioning (`a5ac033`);
  the learning curve with active/absent columns (`01c1cd3`); the held-out probe keyed by domain
  NAME with a deterministic seed, stored in every checkpoint (`4713186`); `holdout.py`, which
  reconstructs the boundary comparison from checkpoints when the log is lost (`40de03d`);
  `longrun.sh add` / `pilot-add` (`4713186`, `2ba3ac1`).
- **Every measurement that exists**, and there are few:
  - first whole-stream reading: +0.233 b/B, "DRIFTING" (`c316813`).
  - the explicit non-stationary run vs a matched stationary control: faded set +0.65 b/B forgetting;
    active set improved -0.56 (`c316813`).
  - PHASED=1 mean +0.024 RETAINED vs PHASED=0 mean +0.147 DRIFTING — the stationary run reporting
    the worse retention (`a5ac033`). n=1 each.
  - the first pilot→pilot-add chain: English IMPROVED while Python was added, because the baseline
    was 172 steps and undertrained. Not a continual-learning result; a proof the measurement fires
    (`61b9d23`).
  - **the one real run** (`a9d7258`, row `continual_eng_py` in `runs.csv`): RESUME from `nogrow_s2`
    (English held-out 1.989) + Python from the-stack, `PHASE_SCHED [[0],[0],[1],[1]]`.
    `eng was 1.998 → 2.050, +0.052 ± 0.075 HELD`; `py 2.276 ± 0.086 NEW`; combined 2.243, beating
    order-1 by +1.402. Learning +0.116 b/B per 2000 steps while active vs -0.029 while absent —
    about 4x faster than it forgets. English recovered rather than ratcheting.
- **Where the retention came from is not where the design assumes.** Every English memory entry was
  evicted during the Python phases — the faded-process unlearn test skipped itself, 0 entries left
  — yet English held. Weights and the fabric carried it. The fabric contributed +0.373 b/B with SIX
  experts, the largest fabric contribution in the record, from the smallest population. Memory went
  NEGATIVE (-0.111), and deleting a live domain's entries improved both it and the others.
- **What remains unknown**, explicitly:
  - n=1. No seed replication of the continual run at all.
  - Its log was lost to the `pilot-add` mkdir bug; the numbers come from a terminal copy. What can
    still be recovered from the checkpoint via `holdout.py`?
  - Only two domains, one addition, one direction. Nothing tested a third area, a re-addition, or
    re-visiting a faded area.
  - The editable memory — the original thesis of the project — is net-negative and fully evicted in
    the one run that mattered. Whether memory contributes anything to retention is untested.
  - Every "unlearning is surgical and local" result in the record was measured on ACTIVE material;
    deleting what a bounded store has already evicted is a no-op (`c316813`, `9909349`).
  - Catastrophic forgetting in the literature sense (a task learned, then a distribution shift,
    then the original task re-measured against a from-scratch control) has never been run.

**Sources.** `c316813`, `a5ac033`, `01c1cd3`, `9909349`, `4713186`, `c411ac7`, `a3ed1a9`,
`61b9d23`, `a9d7258`, `2ba3ac1`, `40de03d`; `holdout.py`; `runs.csv` row `continual_eng_py`;
`CL_TESTBED.md` (historical framing only).

---

## 7. `notes/07_WIP.md` — M (section D)

**Purpose.** What is unfinished, broken, inert, or never run. Written so it can be picked up.

**Required contents.**
- **Uncommitted at HEAD** (verify with `git diff` before writing — it may have moved):
  `FAB_LR_BOOST` in `self_organize.py` (raises the own-rate for the cull-eligible bottom) and
  `_stopped`/STOP-file support in `longrun.sh`. Neither appears in any commit message.
- **Built, on, and never validated at scale**: `FAB_NEW_FRAC=0.04` and `FAB_BURST=1` (`f4b2e9b`,
  `6d5e6d7`); `TOK_ANCHOR_USES=400`; `LR_RESTARTS=1`; the retok guard.
- **Built and off by default, never measured at pilot scale**: `TOK_COMPOSE`, `TOK_MINT_NOVEL`,
  `TOK_MINT_PMIN`, `TOK_PROBATION` (use/embed), `LOSS_MASK_DEAD`, `GROW_CAP` family, `FAB_RESCUE`,
  `FAB_LR_OWN`, `LR_DECAY`, `WARMSTART_MODE=last/first`, `CHAIN_SUP`, `CHAIN_CURRIC`,
  `CHAIN_STATE_Q`, `DOM_ADAPTIVE`, `DOM_RELATIVE`, `SHIFT_REL`, `DOM_RADIUS`, `ENC_PROTO`,
  `SIG_SPACE=tokens`, `MEM_PER_EXPERT` variants, `VERIFY=recon`, `VERIFY_SWEEP`.
- **Known-broken or structurally limited**: `EXPERTS` is mutually exclusive with `FABRIC` (an elif
  chain) and the exclusivity is "arguably a bug" (`51889b7`); the chaining path computes all N
  without `FAB_CHAIN_K`; memory entry VALUES cannot be remapped across a re-segmentation, and the
  stored SPAN shrinks (`8bdeca4`) — fixing it changes the checkpoint format; `main()` is ~2,940
  lines with 658 locals and the split was attempted and reverted (`9c59a84`) — the seam is 136
  values wide and needs a rename pass first.
- **Never executed**: `retire_stale`, `fuzzy_segment` (present, costed, never run — the recurring
  "no counter cannot be told from silently stopped" pattern); most of the 46 arms in `_flags_for`;
  `MODEL=transformer` in any configuration where the base model survives (`bf53d40`).
- **Designed and not built**: everything in `handoff/designed-but-not-built/`.
- **Open questions the project itself recorded**: `handoff/open-questions/` (Q0, Q3, Q-regime,
  Q-compute) — say whether each is still open at HEAD.

**Sources.** `git diff`; `_SPEC` in `self_organize.py`; `longrun.sh` `_flags_for`;
`handoff/designed-but-not-built/`, `handoff/open-questions/`; the "flagged, not resolved" and
"left undone on purpose" passages throughout the commit log.

---

## 8. `notes/08_GLOSSARY.md` — M (section G)

**Purpose.** This project has invented a lot of vocabulary and reuses ordinary words in specific
ways. Nothing else is readable without it.

**Required contents.** Alphabetical; per term: the definition, where it lives in the code, and any
history that changed its meaning. Minimum set:

*Populations and structure* — Fabric (and the retired Router+Compositor renaming, `3500b78`);
expert; FabricNode (was a residual MLP, now a low-rank d→r→d adapter, `2e3a464`); ExpertBank /
ExpertRouter (the legacy path); society vs chaining vs chained-society (`CHAIN_ROUTE=soc`);
arm; grid; seeds; repeat; smoke; gate; ramp; latch; burst; newborn fraction; grace; soft cap;
cull; rescue; replication / crossover / mutation / lineage / parent quota; breadth cap; discovery;
exploration; spawn-by-specification; identity space (`eemb`/`edec`); SRC / outgoing signature;
HALT; ponder; depth; hop; the transition matrix; gradient reach; specialization; sufficiency;
marginal contribution; competence; interchangeable.

*Domains* — the assembler; gist / signature; SigEncoder; splice segment; boundary; SUSTAIN;
reservoir; radius; fold; recurrence; visit; provenance; `did`; purity / homogeneity /
completeness / V-measure / silhouette / fragmentation (and why they disagree); the seeded corpora
as a SCAFFOLD, not a target.

*Tokenizer* — minting; mint order and cohort; retok (re-tokenisation, and why an unchanged-vocabulary
retok is not a no-op); dead rows / never-minted / minted-then-unused; warm start; composite
(`TOK_COMPOSE`) and the residual anchor; probation; fail-open; the p(b|a) mint gate; novelty
minting; seed vocab vs VMAX vs softmax width.

*Measurement* — bits/byte vs bits/token; the anchors (uniform / order-0 / order-1); memorization
gap; held-out; retention; the learning curve's ACTIVE and ABSENT columns; ACROSS THE RUN BOUNDARY;
coherence (and its four-sample history); real words / tokens per word; knockout vs retrained
ablation; the null (shuffled / permuted / matched-size) and why every verdict here needs one;
seed spread; the instrument; `equiv.sh` and the per-machine noise baseline; `_done`; the config
banner / EFFECTIVE / DERIVED / COUPLING / config-audit; `_SPEC`, `_env`, lever, derived, override.

*Process* — the gate; the arm; the pilot; `pilot-add`; probe sidecar (`probe.pt`); best checkpoint.

**Sources.** `handoff/GLOSSARY.md` and `handoff/STRUCTURES.md` (the earlier, partly superseded
attempt — reconcile rather than copy; several terms were renamed in `3500b78` and renamed back in
practice), plus the code and the commit log.

---

## 9. `notes/09_COMMENT_AUDIT.md` — L

**Purpose.** Define and execute the pass that moves narrative out of source comments into these
notes, leaving comments that describe usage and mechanism.

**The criterion for "extraneous"** — a comment moves out if ANY of these hold:
1. It states a measured number from a specific run (b/B, %, counts, ms, step numbers).
2. It narrates history — "used to", "I", "we", "earlier", "turned out", "was wrong", "retracted",
   "the pilot showed".
3. It argues against an alternative that was tried and rejected, rather than stating what the code
   does.
4. It cites a run, arm, pilot or commit as evidence.
5. It justifies a default by evidence rather than by mechanism.

A comment STAYS if it states: what the code does; a contract or invariant; units and shapes; an
ordering requirement or hazard for the next editor ("this must run before X", "this must not
receive gradient", "an eval pass must not call this"); or a dependency between knobs.

**The decisive test**: *would this comment become false when a DEFAULT changes or a new run is
done?* Then it is extraneous. *Would it become false only when the CODE changes?* Then it stays.

**The project has already ratified this criterion** and the executing agent should cite it:
`bdce727` replaced six stale claims with fresh claims; `6dda2c4` concluded a week later that this
was the wrong repair — "a comment that records a measurement is wrong the moment the code changes,
and this file has now misled me twice that way" — and removed the empirical assertions instead;
`8103a8a` moved results out of comments into `runs.csv` for exactly this reason.

**Required contents of the file.**
- The criterion above, stated once, as the standing rule.
- An inventory table: file | line | first words of the comment | verdict (move / keep / rewrite) |
  destination (`04_RESULTS.md`, `05_ERRORS.md`, `03_EXPERIMENTS.md`, ...).
- The migrated text itself, if it does not fit any other file. Nothing is deleted without landing
  somewhere.
- A **do-not-delete list**: comments that are the ONLY surviving record of a run. Two are already
  known and already mirrored into `runs.csv` with `SOURCE: ... comment; log not retained` —
  `self_organize.py:4624` (the 6-arm pilot at `707f1af`) and `self_organize.py:928-929`
  (the FABRIC on/off pair). Check `runs.csv` before touching any comment that carries numbers.
- The replacement pattern, taken from `6dda2c4`: keep a number only where it explains a DECISION,
  say when it was measured, in the past tense, and point at the report line that answers it now.

**Scale.** `self_organize.py` has 2,146 comment lines. A first-pass grep for the narrative markers
returns ~180 candidates:

    grep -nE "^\s*#.*(measured|Measured|MEASURED|b/B|bits/byte|retract|used to|earlier|previously|turned out|the pilot|held-out|WRONG|was wrong)" self_organize.py

That grep is a starting set, not the answer — long narrative blocks (e.g. `self_organize.py`
lines ~400–620, ~1100–1500, ~1690–1900, ~2530–2760) run for dozens of lines and need reading.
Also audit `tokenizer.py`, `memory.py`, `longrun.sh`, `runs.py`, `levers.py`, `equiv.sh`.

**One stale docstring found while surveying, unrelated to the narrative pass**: `tokenizer.py`'s
module docstring describes a different project — it names "Greg", `continual_tokenizer.py`,
`data_utils`, `system` and `chat`, none of which exist in this repo. Rewrite, do not migrate.

**Rule for the executing agent**: this pass edits source comments only. Verify with
`git diff` containing no non-comment line, exactly as `bdce727` did.

---

## ORDERING AND DEPENDENCIES

    1. _evidence/commit_log.txt        (mechanical; do first, everything cites it)
    2. 01_TIMELINE.md                  (no dependencies; every other file depends on it)
    3. 08_GLOSSARY.md                  (needs 01 for term history; unblocks readable prose elsewhere)
    4. 05_ERRORS.md                    (needs 01; produces the invalidation list 03/04 depend on)
    5. 03_EXPERIMENTS.md               (needs 01, 05)
    6. 04_RESULTS.md                   (needs 03, 05 — it cannot mark a result invalidated before
                                        05 exists)
    7. 06_CONTINUAL_LEARNING.md        (needs 03, 04)
    8. 02_IDEAS.md                     (needs 01, 03 — "what happened to it" is an experiment outcome)
    9. 07_WIP.md                       (needs 03, 05; and a fresh `git diff`)
   10. 09_COMMENT_AUDIT.md             (LAST — the destinations must exist before anything is moved)
   11. 00_INDEX.md                     (last prose file; it is the map, so it is written when the
                                        territory is fixed)

02, 06, 07 and 08 can be written in parallel by different agents once 01, 03 and 05 exist.
04 must not run in parallel with 05.

---

## QUESTIONS I COULD NOT ANSWER — the executing agents must resolve these from sources

1. **Which `runs.csv` rows predate the instrument fixes?** Resolve per row with
   `git merge-base --is-ancestor <row commit> c76dc74` and the same for `5f4f117`. Do not guess
   from dates alone — the CSV's `date` column is the log's build date, not the commit's.
2. **Do the `runs.csv` `held_out` values describe the FINAL model or the `.best` checkpoint?**
   `3f67bfc` added best-tracking; `runs.py`'s regex must be read to see which line it parses.
3. **What actually ran in the one continual-learning run (`a9d7258`)?** Its log was lost. Was it
   `FAB_GROW=0`? `runs.csv` records `fab_nmax 4096` but the note says "RESUME from nogrow_s2".
   Try `holdout.py` against any surviving checkpoint, and check whether `.cfg` files exist beside it.
4. **Which of the 46 arms in `_flags_for` have ever been run at pilot scale?** Cross the arm list
   against `runs.csv` tags and the commit log. Arms never run should be listed as such in `07_WIP.md`.
5. **Which of the 279 registry knobs have never been set by any harness, arm or documented command?**
   `levers.py` and a grep of `longrun.sh`/`rerun.sh`/`equiv.sh` will answer it.
6. **Is `MEM_PER_EXPERT` actually live under the current default path?** At HEAD it reads
   `bool(_i(...)) and FABRIC` (line ~3616), but `a5c893a` describes a version ANDed with `SOCIETY`,
   which now defaults to 0. Confirm which is in force and whether any recorded run had it on.
7. **What is the world model's status?** Its last reading was "beats baseline -84.7%, latent std
   0.07" — i.e. by its own criterion it had not learned dynamics (`51889b7`, 2026-07-29). Has it
   been measured since? It defaults ON at HEAD.
8. **What is `VERIFY`/`verification.py`'s status?** Default is `selfcon`. Is the Reconstructor
   still constructed, still costed, still reachable? Was it ever run after `f5303d6` (07-22)?
9. **Did `equiv.sh HEAD HEAD` ever establish a noise baseline on the GPU box?** No
   `runs/equiv_noise_*.txt` exists in this checkout. Without it, `c6f54e6`'s INERT verdicts are
   not trustworthy. Check the GPU machine.
10. **What did `runs/equiv_c14f876_vs_37ecb20` conclude?** The logs and `.norm` files are present;
    read them and record the verdict.
11. **How many of the 481 logs under `runs/` are still readable and which arms do they cover?**
    All but the equiv pair predate 2026-08-08. Decide whether any are worth parsing into `runs.csv`
    via `runs.py add`, or whether they are superseded and should be labelled as such.
12. **Was the corpus re-fetched between the 8-epoch arms and `ep18_big`?** `ac79e92` says yes and
    that order-1 moved 3.440 → 3.747. Which earlier rows share which corpus? Without this, the
    `held_out` column is not comparable down the table.
13. **Are `TOK_ANCHOR`, `TOK_ANCHOR_TAU`, `TOK_ANCHOR_USES` still printed on the EFFECTIVE line
    while inert?** `fec2285` added a never-fired audit for `TOK_ANCHOR`; confirm it fires today,
    since `TOK_COMPOSE` defaults to 0.
14. **Does the current default configuration reproduce arm D?** See "know NOW" #1 below — this is
    the single most consequential open question and needs an answer before any more GPU time.

---

## WHAT THE RESEARCHER SHOULD KNOW NOW, NOT AT THE END

1. **The default configuration at HEAD is the arm the 2x2 found fatal.** `_SPEC` reads
   `FAB_GROW=1`, `FAB_N0=3`, `FAB_NMAX=4096` — that is arm D (ramp 3→4096: mean 3.384, spread
   2.074), not arm B (`FAB_GROW=0 FAB_N0=2048`: mean 1.999, spread 0.080). `FAB_NEW_FRAC=0.04`
   and `FAB_BURST=1` were added afterwards to bound the newborn fraction and should mitigate it,
   but that has never been measured at pilot scale. Until it is, a default run is not arm B.
2. **The best result on record ran with no selection at all.** `a5cc7ea` established that founders
   had no birthday and were permanently immune to culling — so arm B (`FAB_N0=2048`, all founders)
   had zero culls for its whole life. That fix is now in, which means arm B as measured is no
   longer reproducible at HEAD. Either pin the reproducing config explicitly or re-run arm B before
   comparing anything to it.
3. **Two uncommitted changes are sitting in the working tree**: `FAB_LR_BOOST` in
   `self_organize.py` and STOP-file handling in `longrun.sh`. The commit log records the container
   rolling back at least three times (`b6952da`, `046fd81`). Commit them.
4. **The primary record is the commit log and it lives in one place.** The GPU results from
   2026-08-10 onward exist only in commit messages and `runs.csv`; `runs/` holds nothing newer than
   the `equiv` pair. Export `notes/_evidence/commit_log.txt` before anything else, and consider
   pushing the branch.
5. **`runs.csv` has no column for instrument era.** Rows from `a21a721` through `e2001782` were
   measured through the instrument that was editing training runs. They currently sit in the same
   table as post-fix rows with no marker. Add the column, or the results file will mix them.
6. **The top-level docs are stale enough to mislead.** `README.md` still leads with the
   "-0.0009 collateral" headline and `run_full_unfrozen.sh`; `STATE.md` (71 kB) stops at 2026-07-24;
   `CL_TESTBED.md` still uses the "B" naming retired on 07-21. Anyone new reads those first.
7. **`tokenizer.py`'s module docstring is about a different project** ("Greg",
   `continual_tokenizer.py`, `data_utils`, `system`, `chat` — none exist here).
8. **The measurable target is under-measured relative to everything else.** One run bears on
   continual learning (`a9d7258`, n=1) against dozens on the tokenizer and the expert population —
   which are explicitly *not* the goal. If GPU time is scarce, replicating that one run across
   seeds buys more than any further arm.
9. **The seed floor is the binding constraint on every comparison.** `33a9299`: four runs of one
   nominally identical arm spread 1.227 b/B. No architectural conclusion in this branch survives
   that unless it is replicated. Arm B's 0.080 spread is the first configuration stable enough for
   a 0.1 b/B difference to mean anything — which is itself a reason to make it the baseline.
