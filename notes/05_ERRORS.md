# 05 — ERRORS

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are tiny
> — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has reached
> 1.227 b/B (`33a9299`), larger than the gap between any two architectures ever compared here.
> Several confidently-stated findings were later retracted when the measurement turned out to be
> broken. Every entry records **what was observed under these conditions**, never **what is true**.
> Where a result was later invalidated, the invalidation is stated next to it, not in a footnote.

---

## What this file is

The complete catalogue of defects found in this project: measurement bugs, dead code paths, wrong
defaults, retracted findings, and infrastructure failures. It is the largest file in the write-up
because the project's history is largely a history of measurement bugs, and this file is what stops
them recurring.

**Primary source**: `notes/_evidence/commit_log.txt` — 267 commits, full messages, read start to
finish. Secondary: the source itself (`self_organize.py`, `tokenizer.py`, `memory.py`, `levers.py`,
`longrun.sh`), whose comments are in many places post-mortems of specific bugs.

**Every entry cites at least one commit hash. No hash, no entry.**

### Schema

Each entry is:

> **`Ex.y` — title**
> One-or-more sentences on what it was and why it mattered.
> **Found** `hash` — *how*. **Introduced** `hash` or *unknown*. **Fix** `hash` or **NOT FIXED**.
> **Recurred** yes/no. **Blast radius** — what it invalidates.

"How it was found" is the field that generalises; it is never omitted. The tally is in
[§ How these were found](#how-these-were-found).

### Organisation

Entries are grouped by **class**, not chronology, because the classes recurred and the chronology
does not predict them.

| § | Class | Entries |
|---|-------|---------|
| 1 | [Knobs read by nothing](#1-knobs-read-by-nothing) | 11 |
| 2 | [Defaults that silently decided the experiment](#2-defaults-that-silently-decided-the-experiment) | 14 |
| 3 | [Cadence bugs](#3-cadence-bugs) | 11 |
| 4 | [Diagnostics that mutated training state](#4-diagnostics-that-mutated-training-state) | 7 |
| 5 | [Resume / persistence](#5-resume--persistence) | 9 |
| 6 | [Populations that could not be culled](#6-populations-that-could-not-be-culled) | 12 |
| 7 | [Measurement and metric errors](#7-measurement-and-metric-errors) | 50 |
| 8 | [Attribution errors — measuring at the wrong scale](#8-attribution-errors--measuring-at-the-wrong-scale) | 31 |
| 9 | [Harness and plumbing](#9-harness-and-plumbing) | 35 |
| 10 | [Self-inflicted regressions during this work](#10-self-inflicted-regressions-during-this-work) | 46 |
| 11 | [Not fixed at HEAD](#11-not-fixed-at-head) | 12 (cross-linked) |
| — | **[THE INVALIDATION LIST](#the-invalidation-list)** | **44 rows** |

**226 catalogued errors, 44 invalidated results.**

Then: **[THE INVALIDATION LIST](#the-invalidation-list)** — the table `03_EXPERIMENTS.md` and
`04_RESULTS.md` depend on. Then [recurring patterns](#recurring-patterns), [countermeasures]
(#the-countermeasures-and-what-each-one-catches), and [how these were found](#how-these-were-found).

### Two epoch markers that dominate everything below

- **`c76dc74` (2026-08-13)** — five diagnostic→training leaks closed; the stream gets its own RNG.
  The commit's own verdict, quoted: *"No result in the record predates these fixes safely: every arm
  comparison was measured through an instrument that was changing the thing it measured."*
- **`5f4f117` (2026-08-07)** — eval passes stopped training the router; the LR horizon became live;
  arm flags stopped being silently discarded.

Any result whose producing commit is an ancestor of these carries the corresponding era marker.

---

## 1. Knobs read by nothing

The single most expensive class in this project by its own assessment (`ff8754a4`: *"the single most
expensive class of bug this project has hit"*).

> **`E1.1` — `D_MODEL_B` was read by nothing; every direct run silently used d=128**
> `self_organize.py` reads `D_MODEL`; only `run_full_unfrozen.sh` translated `D_MODEL_B` into it, so
> a direct `D_MODEL_B=768 python3 self_organize.py` fell back to the d=128 default. Proven by exact
> parameter counts: GRU d128/V16384/L1 = 4,309,760 ("4.3M") and transformer d128/L4 = 5,069,312
> ("5.1M"), against 28.7M and 53.9M at the intended d=768. Both benched models were ~84% vocab
> tables, which is why lm fwd+bwd looked like a rounding error.
> **Found** `a5cd9ed` — by reading parameter counts back against the intended geometry, i.e. by
> audit, not by any failure. **Introduced** pre-`8150f8a` (inherited). **Fix** `a5cd9ed` (alias).
> **Recurred** no, but `c46a32f` records `fetch_big.py` still *suggesting* `D_MODEL_B` in its next-
> command line afterwards. **Blast radius** — the entire A100 throughput bench (`0c00652`,
> `096094b`): the "85% encoder share", the component ranking, "the LM is a rounding error", and the
> original pilot command. See [INV-01](#the-invalidation-list).

> **`E1.2` — 8 of 36 sweep knobs were read by nothing**
> `sweep_domain_grid.sh` set 36 knobs; eight were read nowhere. Five of those were entirely
> unimplemented (`DOM_RECUR`, `DOM_RECUR_HORIZON`, `DOM_MIN_VISITS`, `ENC_FLOOR_K`, `ENC_PROTO`).
> The commit states the consequence precisely: *"a sweep is the worst place for it because each
> unread knob turns a stage into duplicate rows that read as a clean null result."*
> **Found** `6397041` — by the guard added in the same commit (a sweep now refuses to start if any
> knob it sets is unread). **Introduced** unknown. **Fix** `6397041`. **Recurred** the same shape as
> `E1.1`. **Blast radius** — any stage of the domain sweep whose "null result" came from a knob that
> did nothing. The sweep results are not separately recorded in `runs.csv`.

> **`E1.3` — `TOK_MINT_GATE_K` was declared but never read through `_env`**
> `tokenizer.py` read it from `os.environ` directly, so `_ENV_READ` never saw it and the config
> audit reported a registry knob nobody reads.
> **Found** `904742c` — by the pilot-matrix audit. **Fix** `904742c` (mirrored from
> `self_organize` the way `TOK.pmin` already was). **Recurred** no. **Blast radius** — none on
> results; the value was in force, only the audit was blind to it.

> **`E1.4` — a dead module-level `ROUTE_T` with a different default from the one that routes**
> `ROUTE_T = _f("ROUTE_T", 1.0)` sat at module scope, assigned and never read, while the value that
> actually routes is `Fabric.route_t` with default 0.1. *"Two names for one env var with disagreeing
> defaults is how a config gets misread."*
> **Found** `3e67b5d` — by verifying the arms of the 18-arm grid instead of assuming them.
> **Fix** `3e67b5d` (removed). **Recurred** no.

> **`E1.5` — six `GROW_CAP*` knobs set on a build that predated all of them**
> `GROW_CAP`, `GROW_CAP_FAB0`, `GROW_CAP_VOCAB0`, `GROW_CAP_EVERY`, `GROW_CAP_PLATEAU` and
> `LOSS_MASK_DEAD` were set deliberately on build `e9f2e58`, which predated every one of them. All
> ignored, the run said nothing, and *"an hour of GPU produced a different experiment from the one
> requested."* The net built for exactly this did not fire, because it was an **allowlist** of
> prefixes (`FAB_`, `ROUTE_`, `TOK`…) — and a brand-new family is precisely when the mistake is most
> likely.
> **Found** `c909918` — by noticing the runs did not behave as configured. **Fix** `c909918`
> (families now derive from `_SPEC`, so registering a knob extends the net automatically; generic
> tokens like MAX/MIN/USE/NEW dropped; the message names the commit). **Recurred** — this *is* the
> recurrence of `E1.1`/`E1.2`, three weeks and two countermeasures later.
> **Blast radius** — the three runs recorded as `rampfrom2048_s{0,1,2}` in `runs.csv` measure a ramp
> 2048→4096, not the `GROW_CAP` experiment. They were kept and relabelled. See [INV-19](#the-invalidation-list).

> **`E1.6` — `TOK_ANCHOR=0.05` printed on the EFFECTIVE line of every run while contributing nothing**
> `TOK_ANCHOR` and `TOK_ANCHOR_TAU` are gated on `TOK_COMPOSE`, which defaults to 0 — so they have
> done nothing in every run of this investigation while being printed as active configuration.
> **Found** `3464ba7` (identified as a banner lie), **confirmed empirically** `d05d919` — an
> adversarial audit ran three end-to-end runs at identical seed differing only in `TOK_ANCHOR`
> (0.05/tau=4000, 25.0/tau=1.0, 0) and got byte-identical reports apart from the banner line.
> **Fix** `3464ba7` (banner), `fec2285` (the never-fired audit extended to cover `TOK_ANCHOR`, and
> it names the reason: gated on `TOK_COMPOSE`). **Recurred** — this is the same shape as `E10.21`
> (`DIV_W` read-but-unreachable) which had already been fixed once.

> **`E1.7` — 4 of 279 registry knobs were not in `_SPEC` at all, and all four were derived**
> `MAX_DOMAINS ← FAB_NMAX`, `ENC_EVERY_IDLE ← ENC_EVERY`, `D_MODEL ← D_MODEL_B`, `PHASE_W ← PHASES`.
> The derived class is where drift is most likely and least visible. `FAB_NMAX` silently setting the
> **domain** cap is a cross-subsystem tie nothing stated.
> **Found** `f279fd0` — by deriving the lever graph from the AST rather than from the comments.
> **Fix** `f279fd0` (`levers.py` re-derives all of it and fails on drift in either direction;
> coverage 279/279). **Recurred** no.

> **`E1.8` — `CHAIN_ROUTE` switched the entire routing architecture and never appeared in the
> effective-config table**
> Two pilots ran under it and neither log could say which architecture produced its numbers. This
> happened *one commit after* the declarative table was introduced to make exactly this impossible.
> **Found** `99ba0f4` — by asking what the table did not cover. **Fix** `99ba0f4` (a
> NOTHING-READ-THESE / not-verified audit at the *end* of the run, since several knobs are read only
> inside the report). **Blast radius** — the two chaining pilots' architecture attribution.

> **`E1.9` — five knobs read with two different defaults in two places**
> `VMAX` (the tokenizer targeted 4096 while `ByteComposer` sized `delta`/`dbias` to 2048, so an
> unset `VMAX` indexed past the end of both per-token tables — a crash waiting for the first direct
> invocation); `DOMAINS` (the **checkpoint** recorded `_env("DOMAINS", "")`, i.e. an empty domain
> list on any run that did not set it — and `report_holdout` keys its retention probe on exactly
> that field); `RESUME`; `SAVE_CKPT` (in four places); `LAYERS` (genuinely context-dependent, made
> exempt). Before this, 211 of 274 knobs appeared in no declaration at all.
> **Found** `6f4c534` — by building the registry and letting `_env` compare every read against it.
> **Fix** `6f4c534`. **Recurred** no — the class is now structurally impossible.
> **Blast radius** — the `DOMAINS` one is the dangerous one: any checkpoint written without an
> explicit `DOMAINS` carries an empty domain list, and the retention probe keys on it.

> **`E1.10` — `CHAIN_VOTE=1` (the default) forces `FAB_MIN_STEPS=0`, discarding an explicit setting**
> An explicit `FAB_MIN_STEPS=2` was accepted, printed in the banner, written to the checkpoint, and
> discarded. *"The one that is a bug rather than a design."*
> **Found** `4603b06` (made to print itself), **refused** `f279fd0`. **Blast radius** — none
> measured: nothing that has run sets both, so no configuration anyone used is affected.

> **`E1.11` — the `LR_EPOCHS` default was changed in one place and not two**
> Moving the declared default 0→8 left the EFFECTIVE line and the COUPLING banner still asking for
> 0. Without the guard the banner would have printed one horizon while the schedule used another.
> **Found** `18d4f8f` — by the registry guard, at config time, before any GPU was spent.
> **Fix** `18d4f8f`. This is the countermeasure working; it is listed as an error because it is
> exactly the class that had already cost the project weeks.

---

## 2. Defaults that silently decided the experiment

> *"A flag that defaults off is a decision nobody makes and everybody inherits."* — `51889b7`

> **`E2.1` — `FABRIC=0` in every run of the project**
> The routed expert population — the core of the architecture — was absent from every run up to
> 2026-07-29: "fabric nodes 0" in every phase table, no FABRIC section in any report.
> **Found** `7a42f90` — by a subsystem audit reading the defaults, not by any failure.
> **Introduced** `8150f8a` (commit 1). **Fix** `7a42f90` (defaulted ON). **Recurred** no.
> **Blast radius** — *every* conclusion the project drew about domains, coherence and bits/byte
> before 07-29 was measured on a system missing its routing layer. See [INV-02](#the-invalidation-list).

> **`E2.2` — five more subsystems were off by default**
> `TOKENIZER`/`TOK_ONLINE` (the expanding byte-BPE), `WORLD_MODEL`, `WORLD_GROW`, `WORLD_FEEDBACK`,
> `MEM_PER_EXPERT`. The "full system" being measured was the base LM plus memory plus domains and
> nothing else.
> **Found** `51889b7` — by continuing the audit that found `E2.1`. **Fix** `51889b7` (all defaulted
> ON; off becomes the deliberate ablation). **Blast radius** — as `E2.1`. Also: the world model's
> *first ever reading* came from this commit and was "beats baseline **-84.7%**, latent std 0.07",
> which by its own printed criterion (std ≈ 0 = collapsed) means it had **not** learned dynamics.

> **`E2.3` — `PHASED=0`: shipped in commit 1 and never once turned on**
> Of fourteen report sections, exactly one bore on catastrophic forgetting — the NON-STATIONARY
> block behind `PHASED=1` — and it had never been executed in any run. Everything being tuned
> (purity, homogeneity, completeness, V, fragmentation, silhouette) scored the *organisation* of a
> store against categories the project spliced in itself.
> **Found** `c316813` — by auditing the report against the stated goal. **Introduced** `8150f8a`.
> **Fix** `a5ac033` (`PHASED=1` becomes the default; `PHASED=0` warns at startup that the run does
> not test continual learning). **Blast radius** — every number in the project up to 2026-07-28 was
> measured on a stationary i.i.d. splice, which does not require continual learning at all. See
> [INV-03](#the-invalidation-list).

> **`E2.4` — `MANAGE_MERGE=0.12` overrode the fallback for the project's whole life**
> `manage()` computes `md = merge_dist if merge_dist > 0 else MERGE_FRAC*NEW_DIST`. `MANAGE_MERGE`
> defaulted to 0.12, which is non-zero, so it overrode the 0.28 that `MERGE_FRAC*NEW_DIST` was
> written to produce **under a comment reading "ONE scale for create AND consolidate"**. Creation
> ran at 0.35, consolidation at 0.12: domains could be created three times more readily than joined.
> **Found** `13e787a` — by reading the code path rather than the comment. **Introduced** unknown
> (present "since the start"). **Fix** `13e787a`. **Blast radius** — *"the whole of the
> fragmentation this project has spent weeks attributing to the assign rule, the encoder, and the
> creation threshold in turn."* See [INV-04](#the-invalidation-list).

> **`E2.5` — `MANAGE_EVERY=500` was longer than the run**
> Domain management shared `MANAGE_EVERY=500` with the expert and world-model populations. A 60 kB
> run is 468 steps, so `step % 500 == 0` was never true and merge, cull and fold executed **zero**
> times; the 120 kB GH200 runs are 937 steps, so it fired **once**.
> **Found** `510c695` — by the first end-to-end A/B of the radius+fold work on real text.
> **Fix** `510c695` (`DOM_MANAGE_EVERY=100`). **Blast radius** — *every* domain-population figure
> the project had reported, including the 142-domain run, was produced with the consolidation half
> of the mechanism switched off. See [INV-05](#the-invalidation-list).

> **`E2.6` — `SEG_MIN`/`SEG_MAX` were chosen when `WIN` was bytes**
> 700/1800 was chosen when `WIN` was ~96 **bytes** (≈13 analysis windows per splice segment) and
> never revisited when `WIN` became 256 **tokens**. At the 4 MB run's ~1.9 B/token that is ~486 B
> per window, so a segment is 2.6 windows long and `SUSTAIN=2` of those are spent *detecting* the
> boundary — under one settled window per segment survives. Falsified two-sidedly on CPU: V is
> monotone in segment length (0.19 / 0.50 / 0.68 at 2.5 / 9.8 / 39.0 windows per segment) while the
> live count barely moves (15/16/12), so it is not a fragmentation effect.
> **Found** `3f44ce3` — by arithmetic on the testbed after a geometry probe cleared the encoder.
> **Fix** — a **guard only**; the defaults were not changed. **Blast radius** — the whole 4 MB
> domain campaign; and it retracts "the encoder budget dominates the assign rule" (see `E8.19`).

> **`E2.7` — `MEM_PER_EXPERT`: a documented decision the code never implemented**
> The comment recorded a measurement and a decision ("DEFAULT OFF"); the code read
> `_i("MEM_PER_EXPERT", 1)`. **Every run in this project used the partitioned store.**
> **Found** `e25d9b5` (2026-08-15) — by reading the comment against the call site.
> **Introduced** `242e021` (which measured the partition at −0.555 b/B and said it would stay off).
> **Fix** `e25d9b5`. **Recurred immediately in a new form**: the same commit changed the call site
> but not the `_SPEC` declaration, which would have been a `SystemExit` at the read — caught by the
> registry in `daf9f89`. **Blast radius** — every memory result in the project ran with a partition
> that measured −0.555 b/B against the global store at the scale tested; and the partition is the
> mechanism behind the vanished English domain in the one continual-learning run `a9d7258`
> (owners are experts folded mod `MEM_OWNERS`, both domains route to overlapping experts, and
> intra-block eviction is LRU on write-recency, so a domain that stops being written is evicted
> oldest-first by construction). See [INV-06](#the-invalidation-list).

> **`E2.8` — `SEED_CKPT=0` while `GRID_CKPT=1`**
> The sweep that produces the models worth continuing from was the one that threw them away — and
> continual learning, the stated target, needs a checkpoint to resume from.
> **Found** `e0dbf0c` — because a reordering test came back with nothing to resume from.
> **Fix** `e0dbf0c` (default 1). The commit's own note: *"I also dropped the flag from a command I
> recommended… A default is the fix for that, not remembering to type it."*

> **`E2.9` — `CORPUS_CAP` defaults to 2 MB and the product script never set it**
> A multi-day run would have trained on 2 MB of text.
> **Found** `535f5f6` — by a full capability audit. **Fix** — warning only (`535f5f6`), plus a
> preflight check (`ff8754a4`).

> **`E2.10` — `EXPERTS` is a no-op whenever `FABRIC=1`**
> The forward pass is an `elif` chain and `FABRIC` wins, so the expert bank never receives gradient
> while the end-of-run report still prints expert counts.
> **Found** `535f5f6` (warned), and the consequence found separately at `4554d6b1`: the gate's
> `no_experts` arm was therefore **vacuous** and had passed in every gate run since it was added,
> reporting coverage it never had. **Fix** — warning + the arm replaced with
> `expert_bank:EXPERTS=1 FABRIC=0`. **NOT FIXED**: the exclusivity itself stands at HEAD
> (`self_organize.py:427`), described in `51889b7` as *"arguably a bug"*.

> **`E2.11` — `FAB_LR_OWN=0`: per-expert rates were off by default after being built**
> `91fd815` built per-expert learning rates and shipped them off. `9146136` flipped the default to 1
> along with `FAB_CULL_FRAC` 0.08→0.02 and `FAB_GRACE` 3000 steps→48 selections.
> **Found/Fix** `9146136`. **Blast radius** — nothing measured ran with them on.

> **`E2.12` — `WRITE_TARGET` was silently ignored**
> Surprise is `1 - p_model(true token)`, so with V=16384 an undertrained model sits near 1.0 almost
> everywhere; the additive controller drives `gate_theta` straight into `gate_ceil=0.95` within ~40
> calls and the kept fraction ran 1.00/0.93/0.80 against a requested 0.12, filling `MEM_CAP` by step
> ~831 rather than ~6510.
> **Found** `a5cd9ed` (recorded as STATE R39). **Fix** `c1348302` (quantile gate).
> **Recurred**: `write()` kept its own inline copy of the additive controller, so the quantile fix
> *silently did nothing* whenever `KEY_PREGATE=0` or `KEY_BATCH=0` sent writes down the per-window
> path — recorded and fixed at `memory.py:113-115`. **Blast radius** — every memory result before
> `c1348302`: the store was ~8x over-full and saturated 8x early.

> **`E2.13` — `ROUTE_T=1.0` made routing near-uniform at any N**
> Signature and centroid are unit vectors in `SIG_D=64`, so cosine logits have std ≈ 1/√64 = 0.125
> and at T=1.0 the top-vs-mean weight ratio is ~1.37x **regardless of N** — at N=64 that is
> w ≈ 0.016 ± 12%, so top-k selects noise and nothing can specialize.
> **Found** `020c157` — by arithmetic on the logit spread. **Fix** `020c157` (default 0.1).
> **Recurred inverted**: at N=4096 `ROUTE_T=0.1` concentrates nearly all mass on a handful
> (`763e9f2`: *"ROUTE_T=0.1 was tuned when N was 64 and its own comment reasons about N=64"*).
> **Blast radius** — *"a better explanation of the historical '0 exclusive experts' and '12/17 idle'
> than any of the growth theories."*

> **`E2.14` — `ENC_WARMUP=30000` was well past the encoder's optimum**
> The GH200 signature probe measured 1-NN corpus accuracy **peaking at N=1000–4000 and degrading
> after** (posmax4: 98.5% at N=1000 → 80.4% at N=16000).
> **Found** `d6acf20` — by the probe. **Fix** — recorded, **not acted on** at the time; later
> partly addressed by `ENC_FLOOR_K` (`f0375c5`, on by default at 8 from `510c695`).
> **Blast radius** — the 4 MB GH200 domain runs, all of which used `ENC_WARMUP=30000`.

---

## 3. Cadence bugs

Four distinct mechanisms, all producing the same symptom: a knob that is set, read, reported — and
whose code never executes.

> **`E3.1` — four cadences below the batch accumulator never fired when `BATCH_W > 1`**
> The main loop accumulates `BATCH_W` windows before the LM step and `continue`s; `step` advances on
> **every** window, but everything after that line executes only on flush steps, which land on a
> fixed residue mod `BATCH_W`. `step % N == 0` below it therefore asks for a simultaneous solution
> to two congruences that usually has none. Simulated over 200k windows: **zero** mint and retok
> events for *every* `BATCH_W > 1` tested, odd ones included.
> Dead below the line: `GROW_EVERY` (minting), `RETOK_EVERY`, `CKPT_EVERY` (*a multi-day run would
> never have saved a checkpoint*), and the LM loss-curve sample. Subsampled to 1/`BATCH_W`:
> `assigns.append(...)` — which every clustering metric is computed from — and the tokenizer's live
> pair tally.
> **Found** `c8ba635` — **observed, not theorised**: the 4 MB `BATCH_W=16` GH200 run printed
> `[tokenizer @ 6000] vocab 512/16384 (minting live; +0 since last retok)` and finished at vocab
> 512, i.e. a model sized for 16384 ids running on the 512 the seed passes had produced.
> **Fix** `c8ba635` (per-window bookkeeping hoisted above the accumulator; every cadence becomes
> elapsed-since-last-fire, which is phase-independent and resume-safe).
> **Blast radius** — the 4 MB `BATCH_W=16` run: live minting and re-tokenization both dead; its
> purity / homogeneity / completeness / V-measure computed from **6.2% of the stream**; two
> recurrence figures that disagreed by 6x (assembler counter 598 entries vs report block 100 visits)
> because `assigns` held one window in sixteen and recurrence counts maximal consecutive runs, which
> subsampling destroys. See [INV-07](#the-invalidation-list).

> **`E3.2` — `maybe_deepen` had the same bug, so "staged depth did not help" came from code that
> never ran**
> It sat behind `step % MANAGE_EVERY == 0` below the accumulator; at `BATCH_W=4, MANAGE_EVERY=20`
> the intersection is empty. *"I reported 'staged depth did not help' from a run in which it had not
> executed."* `_greach` and two newer instruments had it too — *"the third instance of the same
> cadence bug in this file"*.
> **Found** `e0ce4f7` — by auditing what actually reaches the routing decision.
> **Fix** `e0ce4f7` (all four keyed on the backward counter). **Recurred** yes — third instance.
> **Blast radius** — the `CHAIN_CURRIC` result is **withdrawn**, not upheld. See
> [INV-08](#the-invalidation-list).

> **`E3.3` — `_due` is not a predicate: the retok guard killed re-segmentation entirely**
> `_due` **records** the step and returns True, so asking it twice in one `if`/`elif` consumes the
> event: the first call fired, the vocabulary test failed, the second returned False. The retok
> never ran. And `_last_vsz` is written only inside the retok body, so it stayed at the seed value
> forever and the SKIP branch could never fire either. **Both paths dead, silently.**
> **Found** `d0728fe` — by noticing three 18-epoch runs had **zero** `[tokenizer @ N]` lines and
> zero "retok(s) skipped" lines. **Introduced** `046fd81` (the guard). **Fix** `d0728fe` (one `_due`
> call, nested branches). **Recurred** — see `E3.4`.
> **Blast radius** — three 18-epoch runs at `04cbe89` (`base_5`, `vmax8k_5`) trained with **no**
> mid-epoch re-segmentation and reported nothing about it. It also **reintroduced `E7.12`**: with no
> retok firing, `_VALT` was never invalidated and a growing vocabulary drifted from a frozen
> reference — showing as a 1.6 b/B disagreement between the curve's final value and the end-of-run
> memorization check (`base_5`: 3.764 vs 2.182). `frozen_nr` is unaffected on both counts.
> See [INV-09](#the-invalidation-list).

> **`E3.4` — the same `_due` double-call was still armed for `grow`**
> ```
> 4682: if ONLINE and TOK_PROBATION > 0 and TOK.prov and _due("grow", ...)
> 4710:     if _due("grow", GROW_EVERY):        # -> TOK.maybe_grow()
> ```
> The probation block would have consumed the grow event and minting would never have run — the
> vocabulary stops filling `VMAX` and the run fills with dead rows. Inert **only** because
> `TOK_PROBATION` defaults to 0 and short-circuits before `_due` is reached.
> **Found** `0f96784` — by re-auditing every `_due` site after `E3.3`. **Fix** `0f96784` (own
> cadence key). **Blast radius** — none realised; *"it would have fired on the first `prob_use` or
> `prob_emb` run."*

> **`E3.5` — `RETOK_EVERY=0` silently disabled signature batching**
> `_due` returns False on `n<=0` **before** recording, so `_fired["retok"]` never advances and the
> lookahead clamp evaluated to about `-step`, flooring `_H` to 1 for the whole run. Every
> `RETOK_EVERY=0` arm therefore differed from its comparator in **two** ways.
> **Found** `79dac6c` — by re-reading `_due`'s early-return after `E3.3`/`E3.4`. **Fix** `79dac6c`
> (skipped entirely when there is no retok to bound). **Blast radius** — the `frozen` 4.364 /
> `frozen_nr` 2.175 pair, quoted in the source as *"the largest single effect on record"* and used
> to justify the retok guard, **is not a clean single-knob comparison**. See
> [INV-10](#the-invalidation-list).

> **`E3.6` — the adaptive warmup's plateau test was unreachable when `MIN == budget`**
> `_wfloor = min(ENC_WARMUP_MIN, wu)` and the test is `t >= _wfloor`, but the loop runs
> `for t in range(wu)` and never reaches `t == wu`. Setting `ENC_WARMUP_MIN == ENC_WARMUP` therefore
> makes the early stop unreachable — the one setting that silently disables the whole feature. The
> message printed "stopped at N/N on separation plateau" **unconditionally**.
> **Found** `5a72970` — by reading the message against the loop bound. **Fix** `5a72970` (says which
> of the two happened; warns when MIN ≥ budget). **Blast radius** — the 4 MB GH200 run set both to
> 30000, consequently paid all 30000 contrastive steps, **and was told it had converged**.

> **`E3.7` — the per-expert rate diagnostic printed on `step//20000`**
> Which never advances in a short run, so it fired once at step 3 — when everything genuinely *is*
> newborn and every ratio *is* clamped, i.e. the one moment it cannot say anything.
> **Found/Fix** `91fd815` (moved to `RATE_EVERY`). Notable because the *broken* form of this
> diagnostic is nevertheless what surfaced `E6.4`.

> **`E3.8` — `PH_BOUNDS` was appended to inside `build_stream`**
> `build_stream` runs once per epoch under `DISK_STREAM`, and the current phase is read as
> `sum(1 for b in PH_BOUNDS if bpos >= b) - 1`; with 4 entries added per epoch that index reached 8
> by epoch 3 for a position whose phase was 2 — past the end of `PHASE_SCHED`. **`PHASED=1` would
> have failed in exactly the multi-epoch configuration it exists for.**
> **Found** `a5ac033` — by trying to turn `PHASED` on. **Fix** `a5ac033`.

> **`E3.9` — `manage()` counted cull eligibility *after* the capacity-pressure gate**
> So a below-pressure population reported "0 past their grace" in the same line as a successful cull
> from the sustained-error route, while experts sat at use-age 4287.
> **Found/Fix** `9146136` — by reading the log line against the population state.

> **`E3.10` — the cull ranked globally and then skipped the ungraced, so it removed nobody, ever**
> *"The bottom of a raw utilization ranking is by definition the population with the least use-age,
> so taking the bottom `cull_frac` globally and then skipping the ungraced spends the whole budget
> on entries it is guaranteed to skip."*
> **Found/Fix** `9146136` (the cull now ranks **within** the eligible set).
> **Blast radius** — compounds `E6.4`: two independent reasons the population was not under
> selection.

> **`E3.11` — `spawn_from` ignored `FAB_GROW` and the soft cap**
> It creates an expert whenever a mid-chain router query finds no near match, independently of
> `PlateauGrowth`. *"Which is why a `FAB_GROW=0` run still drifts 3 → 6 experts, and why 'population
> frozen at `FAB_N0`' was never quite true. A cap that binds one of two doors is not a cap."*
> **Found/Fix** `41d2c5d`. **Blast radius** — arm A of the population 2x2 (`FAB_GROW=0, N0=3`) ran
> at **~6** experts, not 3; `cc0a377` records it as "(~6)".

---

## 4. Diagnostics that mutated training state

The headline class. In this project the instrument was repeatedly wired into the circuit it was
measuring, and the mechanism that made it matter is stated once, at `c76dc74`:

> `build_stream()` picks every segment's length with a draw from the **global** random stream, and
> `seg_from` turns that length into a read cursor. The stream is rebuilt every epoch. So the bytes
> epoch 2 trains on are a function of where the global generator happened to be standing when
> `_resample()` was called — and every diagnostic in the file was drawing from that same generator
> on its own cadence. **Two runs with the same seed, the same code and the same corpus, differing
> only in HOW MUCH THEY MEASURED, trained on different text.**

Measured, on a 3-epoch smoke: 250,027 global draws, **23,835 of them (9.5%) taken inside evaluation
passes**. Changing `HOLDOUT_N` from 4 to 16 — a knob that must not touch training — moved 48 report
lines, including "model ALONE 3.494" → "4.306" and a sign flip on the domain-provenance verdict.

> **`E4.1` — the independence test removed the busiest expert and never restored it**
> The expert-independence test calls `fab.remove()` on the **busiest** expert and never put it back,
> so every eval after that point — including the generation samples used to judge coherence — ran on
> a damaged model.
> **Found** `535f5f6` — by a full capability audit ("does the multi-epoch test contain everything?").
> **Fix** `535f5f6` (deep-copied, ablated, measured, restored; `load_state_dict` cannot repopulate a
> `ModuleList` that `remove()` shrank, so the restore swaps containers directly).
> **Blast radius** — invalidated the coherence evidence up to 2026-07-24. See
> [INV-11](#the-invalidation-list).

> **`E4.2` — `fab.cent` was a plain attribute, not a buffer**
> With `ROUTE_GROUNDED=1` (the default) those centroids **are** the routing function, and they were
> absent from `state_dict()`: never saved, never resumed, never moved to device. `prompt.py` routed
> every generation with untrained centroids.
> **Found/Fix** `535f5f6` — same audit. **Blast radius** — every generation read through `prompt.py`
> before 07-24.

> **`E4.3` — `ground_update` on a fabricated zero gist dragged centroids to the origin on every eval**
> `fab_logits` is the eval path (learning curve, holdout probe, `bpb_true`, generation, `prompt.py`)
> and it invents `gist = torch.zeros(...)` so the routing arithmetic has the right shape.
> `Fabric.forward` and `route_w` then read that placeholder as a real signature and call
> `ground_update`, which does `F.normalize(gist).mean(0)` — zero — and drags the top-`FAB_CENT_TOPK`
> experts' region centroids toward the origin. **Five times per forward on the soc path.**
> **Found** `5f4f117` — by asking why two runs whose model code was byte-identical and whose seed was
> the same, differing only in whether `SAVE_CKPT` was set (which gates the extra `holdout_bpb`
> calls), read **held-out 3.694 vs 2.100**. A diagnostic's sampling frequency was changing the final
> model by 1.594 b/B.
> **Fix** `5f4f117` (`learn_regions=False` on every non-training caller).
> **Correction to the finding itself** — `bdce727` withdrew the *attribution*: the extra passes are
> ~125 centroid nudges against ~240,650 from training, **0.05%**, which cannot accumulate to 1.594.
> The 3.694-vs-2.100 difference is real; what it demonstrates is **chaotic sensitivity**, not
> accumulation. The fix stands on correctness — a diagnostic must not train the router.
> **Blast radius** — every held-out figure produced before 08-07, and specifically the `TOK_COMPOSE`
> comparison, which compared one run against a band assembled from different harness modes. See
> [INV-12](#the-invalidation-list).

> **`E4.4` — the five leaks of `c76dc74`**
> Each one an eval pass writing training state:
> 1. **Eval-time exploration.** `Fabric.society`/`Fabric.forward` explored during eval;
>    `learn_regions=False` was applied to the centroids alone. Exploration is a *gradient* device and
>    an eval pass has no backward, so it bought nothing and cost twice: it drew from the global
>    stream, and it routed **15% of every scored window to a deliberately sub-optimal cold expert**.
>    *"Every held-out number in this project's record was read through a randomly degraded router."*
> 2. **Eval-time utilization recording.** The chaining path recorded `use` during eval. `use` ranks
>    the cull, seeds the cold set, and names the expert discovery hands novel material to — so **how
>    often we measured decided which experts died.**
> 3. **The timing probe called `.backward()`** and cleaned up by naming the modules it *thought* it
>    had touched. That enumeration went stale when `WORLD_FEEDBACK` began wrapping `model.encode`, so
>    29 world-model parameters entered the loop holding gradients computed from random tokens.
>    Bisected: forward-only matches `PROBE=0` exactly; with backward the runs split at the second
>    logged step (6.1199 vs 6.1125) from byte-identical weights, stream and memory, and never rejoin.
> 4. **`halt_ema` and `_mass_ema` averaged eval passes** into a figure the report prints as "during
>    TRAINING".
> 5. **The remaining probes drew directly from the global RNG** — window shuffles, the coherence
>    pair, generation.
> **Found** `c76dc74` — prompted by the researcher's instruction *"Why are we trying to measure the
> noise? Let's fix the issue that's coming up, or first find it."* The instinct was right and the
> planned noise-floor measurement would have been wasted.
> **Fix** `c76dc74` — `frozen_rng()`/`@no_rng_drift` around every probe, `torch.autograd.grad` in
> place of `.backward()`, **and the stream gets its own generator seeded from (SEED, epoch)**,
> because even with the leaks closed two arms differing in a training knob take different numbers of
> draws in epoch 1, so epoch 2 hands them different text.
> **Verified**: six runs, same seed, one knob each — rerun 0 differing lines; `SAVE_CKPT` 0→1 three
> lines, all filenames; `PROBE` 1→0 training bit-identical; `HOLDOUT_N` 4→16 two lines; `EVAL_N` 4→16
> training bit-identical. Before: 48, 104 and 115 differing lines on the same comparisons.
> **Blast radius** — **everything before 2026-08-13.** See [INV-13](#the-invalidation-list).

> **`E4.5` — `_sep_probe` drew from the global stream, before the training loop**
> `_sep_probe` draws window starts from the global random stream on the `ENC_WARMUP_PROBE` cadence,
> so how often the warmup *measured* separation shifted every draw after it. *"The same class as the
> diagnostics already closed, missed because it sits before the training loop rather than inside
> it."*
> **Found/Fix** `e0dbf0c` — by re-sweeping for the class after `c76dc74`. **Recurred** yes — this is
> the sixth leak, found a day after the five.

> **`E4.6` — the headline `train | held-out` line was printed bare**
> It is a mean over at most `min(24, EVAL_N)` windows — ~15 kB of text at the pilot's `WIN=256` — and
> carried no error bar, so *"part of what has been read as a difference between arms was the sampling
> error of the instrument."* `EVAL_N` 4 vs 16 moves it **0.35 b/B** on an otherwise byte-identical
> run.
> **Found/Fix** `c76dc74`. **Blast radius** — every single-number arm comparison in the record before
> 08-13; and it broke `runs.py` (see `E9.13`).

> **`E4.7` — the rule the class produced** *(countermeasure, recorded here because it is the lesson)*
> The memory read probe added at `daf9f89` uses a **deterministic stride, not a random draw** —
> *"consuming stream RNG would make the probe cadence change the trajectory"* — and nothing it does
> feeds the forward pass or the loss. `e0dbf0c` states the general form: **a cadence is not a
> training knob, and any diagnostic that touches the global RNG makes it one.**

---

## 5. Resume / persistence

Every entry here bears on continual learning, because `RESUME` is how continual learning is meant to
work in this system.

> **`E5.1` — resume re-seeded the tokenizer from scratch**
> Under `TOK_ONLINE=1` the tokenizer always re-seeded, so a restored embedding table would have been
> indexed by a different vocabulary.
> **Found** `59c6cf4` — by an audit of the pilot's own code path before launching a multi-day run.
> **Fix** `59c6cf4` (resume loads the saved `dyntok.json`).

> **`E5.2` — the checkpoint recorded `tok_path` and nothing ever read it back**
> So resume paired the saved model with whatever `TOKENIZER_PATH` the new command carried. **Both
> failure modes are silent**, because `VMAX` fixes the row count so every shape matches and
> `load_state_dict` is happy:
> - *wrong file* — resume `runs/seeds/..._seed2.ckpt` without setting `TOKENIZER_PATH` and you get
>   `data/dyntok.json`: seed2's weights, **another run's merges**.
> - *no file* — that path missing sends setup down the else branch, which mints a **fresh 512-token
>   vocabulary**; 2048 trained rows are then read with 512 ids' meanings.
> **Found** `2ba3ac1` — by an exhaustive audit answering "is anything saved and possibly used by a
> following run?". **Fix** `2ba3ac1` (records `tok_vocab` and `tok_merges` — *"a filename does not
> certify contents"* — and refuses on mismatch). **Blast radius** — none realised: the audit found
> only two read-back sites in the whole tree, both gated on `RESUME`, and *"the lever for doing it on
> purpose already exists and has never been used"* before `a9d7258`.

> **`E5.3` — `asm.born` / `asm.act` unsaved, so every resumed run crashed at the first merge**
> `_absorb` reads `s.born[a]` with **no default**, so the first domain merge after any resume died
> with `KeyError: 0` — i.e. every resumed run crashed within `DOM_MANAGE_EVERY` steps. *"That is the
> entire recovery path for a run measured in days."* `act` is the decayed use that drives culling;
> empty on restore, every domain looks unused and the first `manage()` invites a mass cull.
> **Found** `c8b6991` — by testing `RESUME` end-to-end for the first time instead of assuming it.
> **Fix** `c8b6991`.

> **`E5.4` — an empty param group appended per growth event discarded every Adam moment on resume**
> Since the population became preallocated tensors, `fab.grow()` returns `[]` — the rows are already
> in the optimizer — but the caller still ran `om.add_param_group` on that return value. A checkpoint
> after 60 growths carried 60 phantom groups, `load_state_dict` refused the count mismatch, and every
> Adam moment was discarded on every resume.
> **Found** `dec9fb3`. **Introduced** `cc04c21`/`2e3a464` (the tensor refactor).
> **Retraction attached**: `4554d6b1` had described this as *inherent* — "remapping moments across a
> different flattening would attach them to the wrong tensors, the transient is safer than the fix" —
> and `dec9fb3` withdraws that: *"That was wrong, and I had not looked closely enough to say it."*
> **Fix** `dec9fb3` (one line). **Blast radius** — a ~1000-step Adam re-warm on every resume before
> the fix; and a wrong architectural claim in the record for four days.

> **`E5.5` — the per-expert memory partition would have been silently destroyed on restore**
> The existing restore packs active entries into the first N slots, which under a partitioned store
> reassigns every entry to the wrong owner block.
> **Found** `ef412e2` — by reading the restore path. **Fix** `ef412e2` (rebuilds in place at
> `owner*quota+slot`; refuses outright if `n_own` does not match). Described at the time as *"latent
> until `MEM_PER_EXPERT` is switched on"* — which, per `E2.7`, it always was. **Blast radius** — any
> resume before `ef412e2` on a partitioned store; no such run is in `runs.csv`.

> **`E5.6` — `fab_born` unpersisted, so restored experts were immortal**
> `fab_cfg` recorded how **many** experts a checkpoint had and not one birthday, so every `RESUME`
> rebuilt the founders-are-immortal bug (`E6.4`) on the path continual learning depends on: 2048
> experts restored, ages all reading 0, none ever cullable.
> **Found** `a5cc7ea` — by asking what `91fd815` had *not* closed. **Fix** `a5cc7ea` (checkpoint
> carries `fab_born`; a pre-existing checkpoint gets its experts backfilled to step 0, **with a line
> saying how many**, because *"'these are old because we know they are' and 'these are old because we
> know nothing' should not look the same in a log"*).
> **Blast radius** — the one continual-learning run `a9d7258` resumed from `nogrow_s2`.

> **`E5.7` — memory `last`/`tick` not restored on the global store**
> Without it every restored entry is the oldest thing in the store and is evicted before anything
> written after the resume — *"the same failure at the boundary."*
> **Found/Fix** `daf9f89`. **Blast radius** — `a9d7258` (the only resume run in the record) predates
> the fix; consistent with every English memory entry having been evicted during the Python phases.

> **`E5.8` — `_V == VMAX` is not an invariant**
> `DynamicTokenizer.load` restores the `vmax` saved **in the file**, not env `VMAX`, so resuming
> against a tokenizer written by a larger-`VMAX` run gives `len(id2bytes) > delta.size(0)`;
> `table()` and `anchor()` then index `delta[:_V]` on a shorter tensor — *"a bare shape error
> thousands of lines from its cause."* Not clampable: the LM head is `VMAX`-wide too, so the extra
> ids have nowhere to be predicted.
> **Found** `d05d919` — by an adversarial audit of the anchor path. **Fix** `d05d919` (fails with a
> message naming the mismatch). Raised from theoretical to reachable by per-arm `TOKENIZER_PATH`
> (`ec9813e`).

> **`E5.9` — a restored population was handed a fresh grace period and a fresh high-LR cycle**
> Under the use-age clock, `uage` must be backfilled to the grace threshold on resume or a restored
> population is uncullable and re-enters exploration.
> **Found/Fix** `9146136` — designed in, having learned the shape from `E5.6`/`E5.7`.

---

## 6. Populations that could not be culled

Selection is the mechanism this architecture rests on. It did not run.

> **`E6.1` — the fabric had no culling at all; the expert population was grow-only**
> `router.manage()` — create/replicate/cull — is gated on `EXPERTS`, which is mutually exclusive with
> `FABRIC` and therefore 0 in every default run. The only other `fab.remove()` is inside the expert
> independence test, which restores immediately. *"So the fabric ramped to its cap and nothing ever
> removed a node. A population that only grows is not under selection whatever its growth rule is."*
> **Found** `2a262a2` — by reading the gating of `manage()`. **Fix** `2a262a2` (`fab.manage()`).
> **Blast radius** — every fabric run before 08-03. It also **explains a standing puzzle**:
> *"COMPETENCE PROTECTION spared 0, every single run"* — the protection was wired into
> `router.manage`, a code path that never executes with the default config.
> See [INV-14](#the-invalidation-list).

> **`E6.2` — cumulative `size` made any domain over 15 windows uncullable**
> `size` was cumulative and inflated on merge, so any domain reaching `MANAGE_MIN`=15 windows could
> never be culled. Compounding it, `MANAGE_STALE=2000` exceeded a 937-step pilot entirely, so zero
> culls could ever fire.
> **Found/Fix** `5e02cfc` (decayed activity counter plus grace; `MANAGE_STALE` 2000 → 500).

> **`E6.3` — the empty-domain AND-clause could never be satisfied**
> The rule needed `act < min_size AND unseen > stale` — a conjunction an empty domain can fail
> forever, since `act` decays toward zero without reaching it and `last` only moves when the domain
> is fed. *"That is why the pilot logged zero culls against 5-8 merges per manage: domains
> consolidated but were never selected OUT."*
> **Found** `763e9f2` — by reading the rule against the observed zero. **Fix** `763e9f2` (empty is
> now literal: no memory carries its provenance, no sample windows).

> **`E6.4` — the founding population had no birthday and was permanently immune to culling**
> `s.born` was written only by `grow()`, so the initial `FAB_N0` experts had no entry and every
> reader fell back to `step` — reading their age as **0, forever**. Three things ran on that:
> `soft_cull` skips anything younger than `FAB_GRACE`, so **the founding population was permanently
> immune**; the `FAB_NEW_FRAC` budget undercounted recent births by exactly the founders; per-expert
> rates handed every founder the newborn rate for the whole run.
> **The direction of failure was the dangerous one.** `s.born.get(i, step)` returns `step` for a
> missing entry, i.e. reports the expert as *newly born* — and everything downstream **protects the
> young**.
> **Found** `91fd815` — *by a diagnostic that was itself broken*: it printed
> `experts 2.00e-03..2.00e-03 (x4.00..x4.00)`, every expert identical and clamped, *"which is not a
> schedule"*. **Fix** `91fd815` (stamp founders in `__init__`) + `a5cc7ea` (persistence, and
> `fab.age` now defaults to born-at-0 so an unrecorded expert reads as maximally **old** —
> *"no future creation path that forgets to stamp a birthday can bring this back"*).
> **Measured**, same config and seed, 24 founders at `FAB_GRACE=100`: `ac79e92` (before) **0 culls**,
> population stays 24; HEAD (after) **6 culls**, population 24 → 8.
> **Blast radius** — **arm B of the population 2x2 (`FAB_N0=2048`, all founders) ran with zero culls
> for its entire life.** Arm B is the best result on record. *"That is what 'arm B ran with no
> selection at all' meant, and this is the run that shows it rather than infers it."* Arm B as
> measured is **not reproducible at HEAD**. See [INV-15](#the-invalidation-list).

> **`E6.5` — the growth ramp never latched off; the population was replaced 1.5x over**
> `PlateauGrowth`'s ramp is armed while `n < ramp_to * cap` — *current* population below target — and
> culling holds the population just under the cap indefinitely, so the ramp stayed armed for entire
> runs and re-fired every `cool//8 = 187` steps. The arithmetic is counter-intuitive and was got
> wrong first: growth is clamped by `FAB_NMAX - n`, so **at** the cap the ramp adds nothing; what it
> does is **refill**, within 187 steps, whatever the last cull removed. Across three pilots ~10062
> grown = ~4093 building the population once + ~5969 refilling 5969 culls. *"The population reads as
> a stable 4096 while being replaced about 1.5x over; a tenth of it is freshly-initialised at any
> moment; and the identity space every `eemb` key and every centroid is defined over IS that churning
> set."*
> **Found** `ff0f0fa` — flagged by the researcher, then confirmed by simulation against the real
> dynamics. **Fix** `ff0f0fa` (latches on first arrival at `ramp_to * cap`).
> **Outcome recorded as a clean negative**: `ffd39b8` — the latch worked (churn ~10062/5969 →
> ~4210/1205, population settling ~3000) **and did not help**: divergence got **worse**
> (+1.438 → +2.287 for base). *"The cull-refill cycle was real and was not the cause."*

> **`E6.6` — the load-balance weight decayed to exactly zero, and an unselected expert had no route
> back**
> After `BAL_WARM` nothing pushed routing mass outward: no traffic, no gradient, no improvement,
> still no traffic. Under the use clock it is also frozen at its use-age, **so the cull can never
> reach it either**.
> **Found/Fix** `9146136` (`BAL_FLOOR` = 0.15 × `FAB_BALANCE` = 0.0015). *"Balance and use-age are
> one mechanism."* Note this had been suspected long before: `a71820a8` names `BAL_WARM` decaying
> the only counter-pressure to zero by step 4000 *"which is where the pilot's loss turned."*

> **`E6.7` — growth could outpace selection, and compounded**
> `max(FAB_BURST=3, FAB_RAMP_RATE=0.10 * n)` is 10% only once n ≥ 30; at n=3 it is **100%**, at 6
> 50%, at 12 25%. And 10% every `FAB_COOLDOWN//8 = 50` steps **compounds** — over 400 steps the
> population doubles, so "10% per event" permits **~114% new per cooldown window**. Meanwhile the
> cull considers `FAB_CULL_FRAC=0.08`: *"pressure ran the wrong way."*
> **Found** `f4b2e9b` — by asking what differed between two ramps to the same destination.
> **Measured**: same ramp, same destination of 4096, differing only in where it started —
> ramp 3 → 4096: 4.327 / 3.572 / 2.253 (mean 3.384, spread 2.074); ramp 2048 → 4096: 1.994 / 2.097 /
> 1.937 (mean 2.009, spread **0.160**). *"The damaging quantity is the FRACTION newborn at once, not
> the count — 4096 experts are fine if they arrive slowly enough."*
> **Fix** `f4b2e9b` (`FAB_NEW_FRAC`, on by default at 0.10) + `6d5e6d7` (burst floor 3 → 1, cap 4%
> against an 8% cull). **Note the cadences are still NOT matched** and the source says so: growth is
> capped per `FAB_NEW_WIN` (400 steps) while the cull runs every `MANAGE_EVERY` (50).

> **`E6.8` — the newborn-fraction cap deadlocked the bootstrap**
> `int(0.10 * 3)` is 0, so the first version blocked growth completely: a population starting at
> `FAB_N0=3` reached 7 (via `spawn_from`, per `E3.11`) instead of 256, every ramp event declined.
> **Found** `f4b2e9b` — by the test written alongside it. **Fix** same commit (`max(1, ...)`).

> **`E6.9` — `FAB_GRACE=3000` on an 1800-step run: the rescue path fired zero times**
> *"…and I nearly reported it as working."* It also had no counter in the log, *"which is the same
> shape as `retire_stale` and `fuzzy_segment`: a maintenance path with no counter cannot be told from
> one that silently stopped."*
> **Found/Fix** `e2db890` — by the test.

> **`E6.10` — the plateau gate lifted at step 7 on `improving +0.0000`**
> Fast and slow EMAs are both seeded from the **first** loss, so "not improving" was an
> initialisation, not a reading.
> **Found/Fix** `e2db890` (requires `GROW_CAP_EVERY` observations first).

> **`E6.11` — `Fabric.remove(j)` never pruned `cent`**
> It rebuilt bodies/keys/qproj but left the centroid list, so `society()` read `cent[:N]` against the
> shifted body list and **every expert above j was routed by its neighbour's region**. Silent
> misrouting of the whole population after any removal, and a corrupted independence test.
> **Found** `020c157` — by re-reading the fabric while adding burst growth. **Fix** `020c157`.

> **`E6.12` — a rescued expert inherited the removed expert's "already had its chance"**
> The rescued set must be renumbered alongside `remove()`'s swap-with-last, or a survivor is culled
> on sight. Also `9146136`: *"guard against `remove()`'s renumbering invalidating a precomputed
> ranking."*
> **Found/Fix** `e2db890`, `9146136`.

---

## 7. Measurement and metric errors

The largest class, and the one that contains the retractions. Sub-grouped for navigation.

### 7a. Retracted findings

> **`E7.1` — RETRACTED: "domain assembly works, purity 0.54 → 0.96"**
> *"That was wrong. Purity rises MONOTONICALLY with fragmentation — one window per cluster scores 1.0
> — so the number went up precisely BECAUSE the partition was falling apart."* Measured elsewhere:
> purity **1.00 at 1431 clusters with completeness 0.18**. What was actually happening: `build_stream`
> emits 89–96 splice segments in a 120k stream and the assembler produced **96 live domains** — one
> domain per *segment*, mean size 9.5 windows, below `MANAGE_MIN`, so "per-domain provenance" was a
> ~1.2 kB slice.
> **Claimed** pre-`5e02cfc` (also called the earlier failure "an undertraining artifact").
> **Retracted** `5e02cfc` — by printing completeness and a fragmentation ratio alongside purity.
> *"Purity alone is what let this hide for several turns."* See [INV-16](#the-invalidation-list).

> **`E7.2` — the completeness formula was homogeneity**
> `H(true|domain)` was computed and printed as completeness. That behaves like purity and is high for
> any pure-but-shattered clustering, so a 16x-fragmented partition reported "completeness 0.89" and
> looked fine. Completeness is the other conditional, `H(domain|true)`.
> **Found** `b1fe6ed` — one commit after the metric was added to stop over-segmentation hiding, i.e.
> *the metric added to catch the bug had the bug*. Verified on a synthetic 62-cluster/4-class
> fragmentation: homogeneity 1.00, completeness 0.34, V 0.51 against 1.00/1.00/1.00 for the correct
> partition. **Fix** `b1fe6ed`.

> **`E7.3` — RETRACTED: the COLLAPSE CHECK verdict**
> A check comparing median centroid separation against a random-unit-vector null printed *"signature
> space is COLLAPSED — fix the ENCODER, not the assign rule"* below −3σ, and fired at −5.2σ on the
> 4 MB rerun.
> **Claimed** `2cffa47`. **Retracted** `ab3a311`, **one commit later, on one measurement**:
> `probe_ckpt_geometry.py` on a checkpoint whose encoder is measurably *healthy* (true-corpus
> silhouette +0.25, 1-NN accuracy 0.90, d_between/d_within 2.68) scores **−4.8σ**. *"−4.8 for a good
> encoder against −5.2 for the one under suspicion. The test could not separate the two cases it
> existed to separate."* Centroids of related text are nowhere near orthogonal, so the null was never
> the right one. **Fix** — the line now reports the numbers and says plainly that it cannot attribute
> them; replaced by median silhouette (scale-free, needs no null: +0.62 healthy vs +0.00 on the
> rerun).

> **`E7.9` — RETRACTED: "1 of 4096 experts used"**
> That figure was measured on **32 eval windows**. It answers "how many experts serve this small
> probe", not "how many did the router ever choose". `ROUTER SELECTION` over the whole run: **84
> distinct experts won at least one window, top expert took 3.9%, half the traffic went to 21
> experts.** *"I read it as catastrophic concentration for ten turns and built four failed fixes on
> it. `fab.use` had the real answer the whole time and nothing reported it."*
> **Found/Retracted** `b610b89` — by reporting the whole-run number for the first time.
> See [INV-17](#the-invalidation-list).

> **`E7.10` — RETRACTED: "expert identities have collapsed"**
> The 0.000 that the collapse was diagnosed from was a **stale variable**: it was captured inside
> `spawn_from`, which only runs when the spawn bar is **met** — *"so the number meant to diagnose the
> collapse was recorded only on the path the collapse prevents. A diagnostic that depends on the thing
> it diagnoses is not a diagnostic."* Measured unconditionally: 196 experts, nearest-neighbour median
> 0.0349, mean pairwise 0.8571 — **DISTINCT**.
> **Claimed** one turn earlier; **retracted** `b610b89`. Two changes made on the false diagnosis were
> kept on their own merits (`_var_cov` on the identity embeddings; training the embedder every step).

> **`E7.11` — the training-curve verdict read its own sign backwards**
> `_d8` is prev-minus-current, so negative means the loss went **up**, and the text asserted "still
> FALLING" regardless of sign. Read back against a 48k-step chaining pilot that bottomed at 3.56 at
> step 5903 and rose to 4.68 by 47231 — **91% of the run spent getting worse** — the report printed
> *"-0.059: still FALLING = more passes/steps will help"*. Two points also cannot see a 40k-step
> trend.
> **Found/Fix** `a5c893a`. **Blast radius** — every "still improving" verdict before 08-05; the
> society pilot has the same shape, *"so this is not a property of chaining. It has been happening on
> every long run and the report has been reporting it as healthy."*

> **`E7.12` — `_VALT` was frozen in an obsolete segmentation, so "best at step 6000" was the
> yardstick moving**
> `_VALT` tokenises the held-out validation text **once** and was never invalidated, while the
> training stream is re-segmented at every mint. After the first mint the learning curve compares a
> model trained on the *current* segmentation against validation text frozen in an *old* one, and the
> mismatch grows with every mint. The shape follows exactly: the curve degrades over the minting
> window and goes **flat the moment minting stops**. *"A model that suddenly stops degrading at the
> exact step its vocabulary stops changing is a drifting yardstick, not a model. And 'best at ~6000',
> identical in every arm at every seed, is the last sample where the cache still matched."*
> **Found** `18fdd6c` — by asking why the best lands at ~6000 when nothing else changes there.
> **Fix** `18fdd6c` (`_VALT` and `_BL` cleared with every re-tokenisation).
> **Verified by placement, not by execution** — the path was unreachable at toy scale.
> **Recurred** `d0728fe` (`E3.3`) reintroduced it exactly.
> **Blast radius** — the per-process **curve** and everything read off it: the "+1.220 b/B since its
> own minimum" used to call the divergence *real* rather than a units artifact, and the claim that
> model-alone quality degrades while memory masks it. The **end-of-run** held-out figures re-tokenise
> before evaluating and are unaffected. See [INV-18](#the-invalidation-list).

> **`E7.26` — generation sampled the LAST model, never the best**
> There was no best-checkpoint tracking anywhere; `ckpt.pt` is written on a cadence and overwritten,
> so the saved artifact is the *last* state. *"Every text sample judged in this project, including
> every one I put in front of you, came from the degraded model."*
> **Found/Fix** `3f67bfc` (`.best` written as held-out improves; the GENERATION section states which
> model it sampled).
> **The "1.1–1.3 b/B worse" figure attached to it was itself substantially `E7.12`**, and was
> retracted as a standing claim at `bdce727`: *"No longer true, and the tracking is what shows it:
> five of six arms in the pilot ended at +0.000 since their own minimum."*

### 7b. Statistics with no resolution

> **`E7.6` — coherence was a four-sample statistic, and three contradictory claims were made from it**
> Every coherence number this project printed landed exactly on 0.25/0.50/0.75/1.00 — the signature
> of a mean over four samples. The metric scored the `GEN_PROCS=4` printed generations, and a ~200-
> token continuation at `WIN=256` with stride `WIN//2` is about **two windows**. The standard error
> of a four-sample mean here is **0.25**, so every difference quoted off this line was one sample
> flipping:
> - *"memory now HELPS coherence (0.50 → 0.75)"*
> - *"the fabric buys coherence (0.75 vs 0.50)"* — **used to defend the `FABRIC` default**
> - *"memory HURTS coherence (0.75 → 0.50)"* — the same measurement, next run, opposite sign
>
> *"Coherence is the metric closest to 'is this proper language', which is the one thing that is
> supposed to matter, and it had no resolution at all."*
> **Found** `6f24bed` — by noticing every value was a multiple of 0.25. **Fix** `6f24bed`
> (`COH_N=16` × `COH_LEN=384`, SE printed, verdict gated at 2σ). First run of the fixed version:
> model ALONE 0.47 ± 0.10, +MEMORY 0.44 ± 0.09, **NEUTRAL**.
> **Blast radius** — every coherence claim before 07-31, including the `FABRIC` default's
> justification. See [INV-20](#the-invalidation-list).

> **`E7.6b` — the ablation table's `+mem` column was matching the wrong number**
> It matched a bare `MEMORY [0-9.]+` and so picked up the COHERENCE line's "model+MEMORY 0.50" for
> five arms and the FABRIC line's bits/byte for the sixth — **two different quantities in one
> unlabelled column**.
> **Found/Fix** `6f24bed`, same commit.

> **`E7.8` — the informativeness null was a single permutation and the verdict flipped on noise**
> Two 4 MB English runs differing only in **SEED** came back at excess +0.010 and +0.013 against a
> hard cutoff of 0.010, and printed **opposite conclusions**: "NOT distinguishable from a random
> partition" and "the partition CARRIES INFORMATION". The threshold was inside its own noise band.
> **Found** `3e2393d` — by running the same configuration twice. **Fix** `3e2393d` (`INFO_NULLS=5`,
> mean ± sd, verdict requires 2σ). Measured: null spread ±0.020, excess +0.000. *"Both GPU runs sit
> well inside ±2σ, so both are correctly NOT distinguishable, and the disagreement was never real."*
> **The negative result stands**: with 64–68 well-formed, recurring, boundary-detecting domains from a
> single English corpus, the partition carries no predictive information beyond a random partition of
> the same shape.

> **`E7.25` — every text judgement in this project rested on one 200-token sample**
> `GEN_PROCS` caps how many **domains** get a continuation; this project runs one corpus, so it has
> always been one domain and therefore exactly **one sample**. The composing check scored "% of
> generated words that appear in the training text" on **64–91 words**. *"91% (83/91) against 71% and
> 31% were being read as a real signal off a few dozen words."*
> **Found/Fix** `c14f876` (`GEN_N`, default 4, via `random.sample` so a passage cannot be drawn twice
> and the samples are not silently correlated). **Blast radius** — every `words_pct` figure in
> `runs.csv` before 08-07, and every coherence probe reading `_gen_keep`.
> See [INV-21](#the-invalidation-list).

> **`E7.5` — domain sizes read from a subsampled `assigns`, and separation was a min order statistic**
> Two defects in the domain-genuineness block, both making the 4 MB run look worse than it was.
> (i) `sizes` was built from `assigns`, which sat below the batch accumulator (`E3.1`), so every size
> read **1/`BATCH_W` of the truth** — the run printed "size 134" for a domain of roughly 2100 windows
> and the `size>=20` half of the GENUINE test was **16x too strict**.
> (ii) `sep` is a **min** over the other N−1 centroids — an extreme order statistic that shrinks
> mechanically as the population grows, *"so it penalises exactly the fragmentation the recurrence
> fold exists to reduce."* For overlapping self-assembled domains, which is the stated design intent,
> "is anything nearby" is the wrong question.
> **Found/Fix** `2cffa47` (reads `asm.size`; prints median separation alongside min, with a
> silhouette against each).

### 7c. Anchors, units and scale

> **`E7.7` — the order-1 anchor was first fitted on the held-out text**
> i.e. a baseline that had already seen the answers. It reported order-1 at **2.627** and a gap of
> **−1.640**. Correcting it (fit on train with add-k smoothing, score out of sample) **halved the
> apparent gap**.
> **Found/Fix** `aac17f7`, within the same commit that introduced the anchors. *"That is an unfairly
> STRONG anchor, which is the opposite of the mistake worth making."*

> **`E7.13` — bytes/token was a mean over the vocabulary, and the sign of the bias depends on
> vocabulary size**
> `sum(bytes_per_id)/vocab_size` weights a token minted once and never seen again as heavily as one
> in every window, *"and the tail is long and rare BY CONSTRUCTION, which is why those tokens were
> minted late."* Every number in the `[signature]` banner is about how far the loop strides through
> the text, and the loop strides in the proportions the stream uses.
> **Found/Fix** `37100fb` (now `len(byte_stream)/len(stream)` — measured, not estimated).
> **Then corrected again** `8a8fb69`: the claim that it *overstates and the overstatement grows with
> VMAX* is wrong at small vocabularies — at 512 tokens it reads 1.50 against 1.85 as used, because the
> 256 single-byte seeds dominate the entry count. *"A bias whose SIGN depends on vocabulary size is
> worse than a constant one… The fix itself is unchanged and was already right. Only the reasoning in
> the comments was wrong, and it is the reasoning that gets read next time."*
> **Blast radius** — `SIG_WIN=614` was chosen off the old figure; the figure is **not comparable
> across VMAX**, which is the axis these runs were being compared along.

> **`E7.14` — `SIG_PROJ_BPT` pinned at 2.4 suppressed the coverage warning**
> The default 2.4 is the end-of-run bytes/token for a `VMAX≈2048` byte-BPE, and it was used for every
> vocabulary size. The projected stride came out `256*2.4 = 614 B`, **exactly `SIG_WIN`**, so
> projected coverage was 100% whatever `VMAX` was and the warning clause was suppressed. Three
> 18-epoch runs printed "covers 100% now" while ending at:
> `VMAX=2048` 2.91 B/tok → stride 745 B → **82%** · `4096` 3.41 → 872 B → **70%** · `8192` 3.93 →
> 1006 B → **61%**. *"At 8k it was reading three fifths."*
> **Found/Fix** `e200178` (projected from `VMAX`: `0.5*log2(V) - 2.59`, fitting the three measured
> points to within 0.02 B/token — *"an estimate from three runs on one corpus, not a law"*).
> **Important non-implication, stated in the commit**: the defect is **monotone in VMAX**, so it
> penalises larger vocabularies and predicts 2048 > 4096 > 8192 — the **opposite** of what was
> measured. It does **not** explain why 4096 beat 2048; it makes vmax4k's win more impressive and part
> of vmax8k's loss artifactual.

> **`E7.32` — the signature encoder was reading 42% of the stream**
> `SIG_WIN=0` meant "use `WIN`" — 256 **bytes** — while the loop advances `WIN` **tokens**. Early in a
> run one token is about one byte and the two agree, *"which is why this survived: it is correct at
> the start of every run and drifts wrong as the tokenizer earns its compression."* By ~2.4
> bytes/token the loop strides 614 bytes and the encoder characterises the first 256 of them.
> *"Nothing downstream could detect it, because every window still produced A signature — just one
> computed from the opening fragment of the material it claims to describe."*
> **Found** `98e3301` — in the pilot's own output while readying it. **Fix** `98e3301` (recomputed
> live) — **and that fix was itself wrong**, see `E10.1`. **Blast radius**, quoted: *"Every domain
> result this project has produced was measured through this, at whatever coverage that run's
> vocabulary happened to imply."* See [INV-22](#the-invalidation-list).

### 7d. Memory and provenance

> **`E7.15` — memory contexts were queried in a segmentation they were not written in**
> `mem.ctx` holds KW **token ids** captured under whatever segmentation was in force when the entry
> was written, and it is the input to the whole drift-survival machinery: `_rekey_amortized`
> re-encodes keys from it on a cadence precisely so keys track the model. **It was re-encoding a stale
> token sequence.** A query builds its key from the *current* segmentation, so the same text on the
> two sides produced different id sequences and therefore different keys, and the gap widened at every
> mint. The rekey pass could not close it — *"it was faithfully re-encoding the wrong input."*
> **Measured** on the probe corpus growing 647 → 1024 — **one** growth step where a pilot does about
> sixteen: **82.3% of stored contexts no longer match** what the tokenizer produces for the same bytes.
> **Found/Fix** `8bdeca4` (`remap_mem_ctx()` re-segments every active entry at each retok and once
> more after the final one, before any of the report battery reads the store; exact in id space
> because minting is append-only; 200,000 entries in 2.0s).
> **NOT FIXED, and quantified**: an entry's **VALUE** ("the next token was X") cannot be remapped —
> those entries vote for a target the model was retrained away from; the report now says how many
> (4.0% of live entries predict an id the final stream never carries). Nor the **SPAN**: 75% of
> windows re-segment shorter, so a remapped window spans less text and is left-padded. Fixing that
> means storing bytes instead of ids, which changes the checkpoint format.
> **Blast radius** — *"None of this touches the training loss… It decided whether 'memory contributes
> +0.698' was measuring anything."* See [INV-23](#the-invalidation-list).

> **`E7.17` — the epoch roll carried a stale batch, so memory provenance pointed at unrelated text**
> The roll sits above the accumulator, so on any epoch whose last window lands mid-batch — at
> `BATCH_W=16`, **fifteen times in sixteen** — up to `BATCH_W-1` windows of the *old* stream were
> still queued. `_bp` holds `(bpos, i)` where `i` indexes the **old** `tok_bs`, and `_resample()`
> replaces `tok_bs`, so `_posv` read the **new** table at the old stream's offsets. Those entries went
> into memory with provenance pointing at unrelated text. **The short-slice padding hid it** — no
> `IndexError`, just wrong bytes — and `prompt.py`'s grounded recall reads a 220-byte span around that
> position, *"so the passage it quoted was not the passage stored."*
> **Found/Fix** `37100fb` (batch dropped at the roll: ≤15 windows of ~15,000 per epoch).

> **`E7.18` — memory provenance positions were byte/token misaligned**
> `mem.pos` was written as `arange(bpos, bpos + WIN)`; `bpos` is a **byte** coordinate but the
> `arange` steps once per **token**. Under the online tokenizer (~1.85 B/token) the recorded
> provenance had drifted **200+ bytes** by the end of a `WIN=256` window, while `prompt.py`'s `_recall`
> reads only a 220-byte span around the stored position. *"Grounded passage retrieval was therefore
> pointing at roughly the wrong text, and the same positions are what make provenance-based unlearning
> meaningful."*
> **Found** `dd7ceb0` — *"while grounding the self-training design against the code, not by testing."*
> **Fix** `dd7ceb0`.

> **`E7.24` — the eviction rules ranked a constant**
> `mem.read()` was called from exactly two places, `generate()` and `bpb_true()`, **both eval-only**,
> so during training `use` stayed 0 for every entry and `last` was never written at all on the global
> store (`read()` stamped it only when `n_own > 1`, and `_store()` only on the partitioned path).
> `EVICT=usage` therefore broke ties arbitrarily and **every other path evicted by write order,
> whatever the knob said**.
> **Found/Fix** `daf9f89` (`MEM_PROBE_EVERY`/`MEM_PROBE_N` — a cadenced read probe in the training
> loop; `read()` stamps `last` unconditionally; `EVICT=lru` becomes the default; the epoch line shouts
> if the probe ran and nothing was ever retrieved). Verified with `mem_evict_test.py`: lru keeps
> 70/100 of a read domain and 0/100 of an unread one; recency keeps 0 either way.
> **Blast radius** — *"That is the mechanism behind the vanished English domain: English was not less
> useful after the Python run, it had merely stopped being WRITTEN, and nothing in the training loop
> could observe that its entries were still being retrieved."* See [INV-24](#the-invalidation-list).

> **`E7.34` — the memory blend was unconditional**
> `read()` scatters a softmax, so `dist` always sums to exactly 1.0 — verified numerically — so
> `hp = dist.sum()` was identically 1.0 and the blend was **a fixed 50/50 mix at every position
> however bad the nearest neighbour**, while `conf` (the real similarity) was computed and discarded
> by all three call sites.
> **Found/Fix** `0b08b74`. Measured effect small (−0.168 → −0.146) *"because at this store size
> retrieval genuinely returns poor neighbours with high cosine anyway, so this is a partial fix, not a
> solved problem."*

> **`E7.40` — turning `MEM_PER_EXPERT` on silently shrank the store 24x**
> `memory.py:35` reads `if self.n_own > 1: cap = self.n_own * self.quota`, so at the defaults
> `FAB_NMAX=64` and `MEM_QUOTA=128` the store is **8192 slots** and `MEM_CAP=200000` is discarded.
> *"Every memory result scales with that number."*
> **Found** `4869559` — while preparing the reruns the subsystem audit made necessary.
> **Fix** — warns, states the reduction factor, and names the `MEM_QUOTA` that would preserve the
> requested cap; `rerun.sh` sets `MEM_QUOTA=3125`. Combined with `E2.7` (the partition was always on),
> this is a live hazard for every memory number in the record.

> **`E7.41` — ACROSS THE RUN BOUNDARY is a weights-only number, and the wording implies otherwise**
> `holdout_bpb()` calls `_eval_logits`, which does not consult memory. So *"the ONLY number that spans
> the run boundary"* measures **weights alone**; `bpb_true` is the only path that interpolates the
> store.
> **Found** `f8599b7` — by a literature agent, **verified against this code**. **NOT FIXED** (the
> wording is unchanged at HEAD). **Blast radius** — the `eng 1.998 → 2.050, +0.052 ± 0.075 HELD`
> result in `a9d7258` measured the weights. *"Consistent with every English memory entry having been
> evicted, but it is not what the line's wording implies."* See [INV-25](#the-invalidation-list).

### 7e. Tokenizer, minting and the loss denominator

> **`E7.42` — `mask_dead` missed retired ids, which are not a suffix**
> The mask covered `[vocab_size:]` — the never-minted tail — and nothing else. But probation
> **retires** a token by popping it from `seq2id` while leaving `id2bytes` intact, deliberately, so
> ids stay positional and old checkpoints keep loading. A retired id is therefore **below**
> `vocab_size`, can never be a target again, and went straight through the mask.
> *"Not a rounding error on the arms that use it: `prob_use` and `prob_emb` retired **217 and 224 of
> 256** minted tokens. Those rows sat in the softmax denominator for the whole run, which is the exact
> condition `LOSS_MASK_DEAD` exists to remove."*
> **Found** `f8599b7` — by the tokenizer-literature agent. **Fix** `f8599b7` (cached boolean over the
> full width, keyed on `(vocab_size, retired count)`, both of which only grow). Verified directly.

> **`E7.43` — the retok guard used the wrong invariant**
> `retire()` pops from `seq2id` and leaves `id2bytes` alone, so `vocab_size` is unchanged while the
> match table — and the segmentation — is not. Verified: `retire()` ×10 left `vocab_size` at 321 and
> moved the segmentation **3478 → 3765 tokens**. *"Latent, and wrong in the direction that produces a
> stale held-out cache"* — i.e. it would have reintroduced `E7.12` a third time.
> **Found/Fix** `79dac6c` (the guard stamps `(vocab_size, len(seq2id))`).

> **`E7.44` — a `break` on a list that is no longer frequency-ordered**
> `maybe_grow`'s candidate loop exits at the first entry below `min_pair`, commented *"the list is
> frequency-ordered: none below"*. After a `TOK_MINT_NOVEL` re-sort it is not — the score is
> `(c - seen)/(1+seen)^novel`, so a rarely-seen pair at count 30 can outrank a worked-over one at 500,
> and the break would discard every viable candidate below it. Latent, and **reachable by default**
> once `TOK_MINT_PMIN=0.10` (the `mintnovel` and `composenov` arms are exactly `novel>0 AND pmin>0`).
> **Found** `904742c` — by the pilot-matrix audit; *"I could not trigger it on the corpus to hand, but
> the premise the comment states is demonstrably false, so it is fixed rather than left to fire on
> data that does invert the order."* **Fix** `904742c`.

> **`E7.45` — telling the composer the vocabulary grew was nested inside `WARMSTART`**
> `if _i("WARMSTART", 1):` sits at indent 20; the `if TOK_COMPOSE:` that calls `set_vocab` and
> `note_born` sat at indent 24, **inside it**. With `WARMSTART=0` and `TOK_COMPOSE=1` the mint still
> happened, but the composer was never told: the new token got an all-zero byte mask, so its composite
> was `proj(length(0))`, **identical for every token minted that way** — *"the indistinguishable fresh
> row `ByteComposer` exists to abolish, reintroduced by an ablation flag about something else."*
> `note_born` went with it, so `born` stayed −1e9 and the anchor held nothing either.
> **Found/Fix** `d05d919` — by an adversarial audit of the anchor path.

> **`E7.46` — the anchor released a token on a clock unrelated to whether it had been trained on**
> `TOK_ANCHOR_TAU` decayed the anchor over tau **steps**, while the docstring claimed this made the
> token *"free once it has seen enough of its own material"* — which steps do not measure. *"A token
> minted early appears constantly and is thoroughly trained inside tau; one minted late is rare BY
> CONSTRUCTION, which is why it was minted late… release was anti-correlated with readiness."*
> Unit-tested on two tokens of identical age, one seen 500× and one seen 2×: weights **0.905/0.905**
> under steps, **0.007/0.980** under appearances.
> **Found/Fix** `3464ba7` (`TOK_ANCHOR_USES`, weight `exp(-seen/N)`). A side benefit recorded: under
> the step rule `TOK_ANCHOR_TAU=4000` and `RETOK_EVERY=3000` **overlap**, so a token is re-segmented
> underneath itself while still anchored; `seen` only advances in a training batch, so the two
> schedules cannot interfere by construction.

> **`E7.47` — the entropy mint gate was wrong in two independent ways, both caught end-to-end**
> *Wrong statistic*: an absolute `H(next|a)` cut-off does not survive real text. Measured over 400 kB
> of English at byte level: H has median 3.48 bits, p90 4.39, max 5.33 — so `TOK_MINT_HMAX=1.5`
> rejected **81% of left tokens**. Worse, H is **anti-correlated with frequency** (a common left token
> is common precisely because many things follow it), so an entropy gate rejects the most useful
> merges first; the top pair in that corpus (`' '+' '`, ×31432) sits at H=4.39.
> *Wrong control flow*: a rejected candidate returned `None`, which ends the grow burst, and
> `self_organize.py` breaks its loop on `None` — so **one blocked pair stopped minting for that
> event**. Since the highest-frequency pair is the one most likely to straddle a boundary, that
> stopped minting almost entirely: the end-to-end run reached vocabulary **256 of 1024 with 100% of
> candidates blocked**, and 75% of the softmax never minted.
> **Introduced** `c214c21`. **Found/Fix** `93c1733`, **within the hour**, *"both caught by running it
> end to end rather than on the constructed case that motivated it."*

> **`E7.48` — `TOK_MINT_GATE_K=64`: the window was deciding, not the threshold**
> At `pmin=0.10` the vocabulary reached **419 of 1024** at `gate_k=64` against **1010** at
> `gate_k=1024`.
> **Found/Fix** `93c1733` (default 1024, *"kept generous so `TOK_MINT_PMIN` is the only lever that
> decides"*).

> **`E7.49` — the mint gate starved the vocabulary in the first real pilot**
> `TOK_MINT_PMIN=0.10` was defaulted **on** on the strength of a 400 kB test where it filled the
> vocabulary, flagged only as untested at `VMAX=8192`. It broke at `VMAX=2048`, the project's standard
> pilot config: minting decelerated and asymptoted ~600 short of the cap (1439/2048, **29.7% never
> minted**), held-out **3.600**, best 2.829 at step 6000, +0.910 past its own minimum — against an
> ungated baseline near 1.96. The median `p(b|a)` of everything judged was **0.029** against a 0.10
> threshold, so once the top-1024 window held no passing candidate the gate minted nothing at all,
> permanently.
> **Found** `1a113f5` — *"The `[vocab]` never-minted instrument is what caught this, in one line, in
> the first pilot that used the new default."* **Fix** `1a113f5` — **fail open** (the gate may
> *reorder* what gets minted and may never *prevent* a mint; `gate_forced` is reported) **and default
> back to 0** (*"a filter that produced 30% dead rows at the standard config has not earned a
> default"*). **Blast radius** — `runs.csv` row `base_8ep_gate_starved`.

> **`E7.50` — `pgate` was an alias for `base`**
> With 0.10 the default, an arm reading `TOK_MINT_PMIN=0.10` changes nothing while *"reading as though
> it tests something."*
> **Found/Fix** `904742c` (becomes `nogate`, `TOK_MINT_PMIN=0` — which is also the arm that reproduces
> pre-gate vocabularies). The audit confirmed independently that `TOK_MINT_PMIN=0` reproduces the old
> vocabulary **exactly** (same `id2bytes`, 758 tokens). Also measured, and worth keeping: at 400 kB,
> pmin 0 → 1024 tokens and pmin 0.10 → 1010, but **only 307 shared** — *"the gate does not trim the
> vocabulary at this scale, it REPLACES most of it."*

> **`E7.51` — branching entropy cannot be the post-probation test, structurally**
> *"Minting DESTROYS the evidence that criterion reads: greedy longest-match consumes a+b into the
> merged token, so the pair never occurs again."* Measured — mint `'t'+'h'`, then read the pair count
> after forty more passes of the same text: **0**, and 0 at the instant of the merge. *"A re-test can
> only ever fail, and did: 0 kept, 8 un-merged, 100%."*
> **Recorded** `9f8412b`. Not a defect that shipped; a design dead end proved before shipping.

> **`E7.16` — the final re-tokenization invalidated nothing**
> The in-loop retok re-points `ENC_SEQ` and clears `_VALT`/`_BL` because the segmentation moved; the
> final one did neither. Under `SIG_SPACE=tokens` every signature in the report battery indexed a
> stale table at the new stream's offsets, and the end-of-run held-out probe scored validation text
> tokenised with the **pre-final** vocabulary. *"Inert on the default path (`SIG_SPACE=bytes`), which
> is why it sat there."*
> **Found/Fix** `37100fb`.

### 7f. Sections that vanished

Five separate instances of a report section disappearing without saying it had been attempted. The
project's own rule, from `9909349`: **declining silently is the same failure as `except: pass`.**

> **`E7.21` — SUFFICIENCY printed nothing since routing went per window**
> `int(_os[j])` was `int()` of a whole row and raised `ValueError` into the section's own `except`.
> **Found/Fix** `30e635d`.

> **`E7.22` — the entire EXPERTS and SUFFICIENCY output disappeared**
> A stale `fab.keys` left by the tensor refactor raised inside a `try/except` that printed a one-line
> message. *"The ENTIRE EXPERTS and SUFFICIENCY output disappeared from the report with no sign it had
> been attempted."*
> **Found/Fix** `763e9f2` — and the handler now prints the full traceback, *"the message alone would
> not have located it."*

> **`E7.23` — the learning-curve sampler was wrapped in `except Exception: model.train()`**
> Which swallowed the error and printed **nothing at all** — the section simply never appeared. What
> it was swallowing: `nbytes()` reads `BLEN`, which is `None` until the final re-tokenization whenever
> `TOK_ONLINE` is set, so it is unusable mid-run.
> **Found/Fix** `01c1cd3`.

> **`E7.22b` — IS THE PARTITION INFORMATIVE simply absent**
> Its guard was a bare `if len(_doms) >= 2:` with no `else`. *"Its absence was the interesting part.
> Surviving memory: p0=0 p1=0 p2=4976 p3=0"* — under the non-stationary stream a 6000-entry store had
> evicted everything except the most recent material.
> **Found/Fix** `9909349`. **Blast radius** — it *"puts a bound on the earlier 'unlearning is surgical
> and local' claims — they were measured on stores that still contained the material being deleted."*
> See [INV-26](#the-invalidation-list).

> **`E7.40b` — the domain-prior section produced nothing, and the claim about it was also wrong**
> `f75d574` records both halves: *"I claimed this section never fires. That was wrong"* — it needs 16
> held-out windows and draws `min(48, EVAL_N)` per domain, so it runs at the pilot's `EVAL_N=64` and
> did not run in a smoke with `EVAL_N=4`. *"The section was fine; my test config was too small to
> reach it."* What **was** worth fixing is that it produced no section, no skip line, and no hint that
> the per-window `asm.tokc` histogram was being paid for and never read — *"the same shape as
> `retire_stale` and `fuzzy_segment`."*
> **Found/Fix** `f75d574`.

### 7g. Encoder and boundary detection

> **`E7.30` — the adaptive warmup could not tell convergence from collapse**
> The stop condition `_sep <= _prev_sep*(1+eps)` is equally true of a flat curve and a **falling**
> one. Signature separation fell 0.16 → 0.05 — a **69% collapse** — and it called that convergence and
> stopped. After which `SHIFT_DIST` never fired, the assembler never created a second domain, and *"the
> whole domain apparatus sat inert behind a page of perfect scores"*: purity 1.00, homogeneity 1.00,
> V-measure 1.00, silhouette +0.95, "1/1 GENUINE" — **a partition of one is perfect by construction.**
> **Found/Fix** `d460e92` (tracks peak separation; warns when the final value is below 70% of it or
> below 0.15 absolute, naming the consequence and the levers).
> **Cause found separately** `c1aadda`: the encoder was collapsing on **homogeneous** text, and the
> other corpora had been hiding it. `DOMAINS=eng` plateaus at encoder loss 3.83/3.78 against
> `ln(ENC_BATCH=48) = 3.871` — *"exactly the loss of an encoder that emits ONE CONSTANT VECTOR."*
> InfoNCE draws its negatives from the same stream, so with a single corpus there are no cross-kind
> negatives and the trivial solution is reachable. **This inverts the standing hypothesis**: the extra
> corpora were not throwing the system off, they were *"the only thing PREVENTING a collapse."*
> Fixed with `ENC_VREG` (VICReg-style, default 5.0), which needed one correction of its own — its
> variance hinge targets std ≥ 1, unreachable for L2-normalised outputs.

> **`E7.31` — `q75*2.0` switched boundary detection off**
> `SHIFT_Q`/`SHIFT_MULT = 0.75/2.0` shipped alongside a `DOM_MARGIN` that *had* been validated against
> all 20 cells of the signature probe. *"The second was a guess and it was wrong in the opposite
> direction from the bug it was fixing."* Against the probe's measured distances, from N=1000 the
> threshold sits **above** the across-splice distance and the detector stops firing.
> **Consequence**: a GH200 run at `ENC_WARMUP=4000` found **14 boundaries for 3213 true switches**
> (recall 0.01), collapsed to **one** domain, V-measure 0.00, **and unlearn deleted the entire store**.
> **Found/Fix** `9ef27f0` (recalibrated to `q50*1.5`, which fires at every stage the probe measured).

> **`E7.33` — `ENC_POS_MAX` above its default crashed `contrastive_step`**
> `hi = seen - 3*WIN` only leaves room for a positive at the **default** radius. *"In a real run it
> would survive while the read position was far from the end and then crash at the end of the epoch."*
> **Found/Fix** `3800129` — verified at 2×/4×/8×/16×/32× `WIN`.

> **`E7.29` — `probe_stability.py` would have printed a finding-shaped string for an experiment that
> never happened**
> With one domain per run it would have computed NMI over a constant labelling — **0 by construction**
> — and printed "NO MORE THAN CHANCE".
> **Found/Fix** `d460e92` (refuses, and points at the collapse warning).

### 7h. World model

> **`E7.36` — the world model was never checkpointed while the LM trained on its output**
> With `WORLD_FEEDBACK=1` the base LM is trained as `h += world_proj(forecast)`, but the saved
> checkpoint had no world state and `prompt.py` had no world path — *"so generation ran a different
> network than training, silently invalidating any coherence judgement."*
> **Found/Fix** `59c6cf4`. **Related, and the same shape**: `f9d33f2` — training added
> `world_proj(forecast)` inline while `bpb_true`, `generate`, `compose_test` and `selfcheck` all called
> `model.encode` directly, *"so every in-script number described a different network than the one being
> trained."* Fixed centrally by folding the feedback into `model.encode` itself. `_model_key`
> deliberately keeps the raw encode, since memory keys must stay comparable with stored keys.

> **`E7.37` — the anti-collapse term ran at 1/10 strength**
> The integration scaled the variance/decorrelation term by `WORLD_W=0.1`, so the latent collapsed
> (std 0.24).
> **Found/Fix** `a1767b7` (`WORLD_VAR`, default 1.0): std 0.24 → 0.97, forward-pred vs persistence
> +13.6% → +34.1%.

### 7i. Corpus contamination

> **`E7.38` — `fetch_data.sh` leaked Brown POS tags into the eng corpus**
> The eng tag-stripper matched only **uppercase** tags (`[A-Z$]`), but NLTK's Brown corpus tags every
> token in **lowercase** (`the/at movie/nn`), so all of Brown's POS tags leaked into training *"and
> surfaced as generation artifacts in the 12x-data run."*
> **Found/Fix** `b77ba2c` (widened to `[A-Za-z$]` while excluding digits/dots so dates and URLs
> survive).

> **`E7.39` — `open_corpus` spliced the fetch manifest into the corpus as training text**
> It globbed `*` and picked up `fetch_big.py`'s `_fetch_manifest.json`. *"Harmless at 300 bytes and
> undetectable by anything downstream, but a 40 GB pull writes one per domain."*
> **Found/Fix** `c8b6991`.

### 7j. Verdict lines that contradicted their own numbers

> **`E7.27` — two verdict lines contradicted the numbers printed beside them**
> `vmax4k@18ep/LR8` came back 2.023 b/B, best == final, 89% real words — and its report said *"FLAT:
> the second half bought nothing. The model is not learning at this setting any more"* on the same
> line as its own **2.04 → 1.97**, and then *"turned upward at the very end -- watch it"* six lines
> after *"NOT DIVERGING"*.
> **Found/Fix** `5239ebb` — both were wording, not thresholds. The "turned upward" line fired on the
> **per-token** curve alone, *"the same curve the line above had just said to ignore."*

> **`E7.27b` — the CHAINING report hardcoded a measured value as a fact**
> It printed *"depth is 0.00 of 4"* as a fact while the comment seven lines below states a different
> value.
> **Found/Fix** `2c705c7` (points at the measured figure).

---

## 8. Attribution errors — measuring at the wrong scale

Not bugs in code. Comparisons that could not carry the weight put on them.

> **`E8.1` — "the weight-prediction term is 2% of the routing decision" was measured on a 64-expert toy**
> At 4096 experts, `base` measures **7% region / 93% weight-prediction** — the weight term was already
> dominant at scale — and `FAB_KEY_NORM=1` **reduces** it (41/59) rather than rescuing it.
> **Claimed** `e0ce4f7` (and acted on in `fcdfaa7`, which built `ROUTE_REGION_W` on the strength of
> it). **Retracted** `ffd39b8`, in the commit's own words: *"The direction of that finding was wrong,
> and it was wrong because I measured it at a scale the user had already told me was
> unrepresentative."* **What still holds**: routing on predicted weights alone gives the best
> specialization of any chaining arm (0.142 against a 0.000 null). See [INV-27](#the-invalidation-list).

> **`E8.2` — the tokenizer explanation for the divergence was presented as a finding while untestable**
> *"I could not test it: the one arm with minting off (`frozvocab`, `TOK_ONLINE=0`) also builds the
> full 2048 vocabulary up front instead of seeding 512 and minting, so it is a different run from the
> start — and it went NaN from step 20000 anyway. The hypothesis was untested and I presented it as a
> finding."*
> **Claimed** `53fbae5`. **Retracted** `1593c70`, which found the real common cause: **there was no
> learning-rate schedule** — lr=2e-3 constant, no warmup, no decay, for 48,000 steps, across all 17
> pilots (GRU and transformer, `FABRIC=0` and every fabric variant, society, transition-chaining and
> soc-loop), all bottoming at ~2.4 around step 6000 and rising to ~3.8–4.1 by 48000. *"A cause common
> to all of them cannot be the fabric, the router, or the blend rule."* See [INV-28](#the-invalidation-list).

> **`E8.3` — "frozen tokenizer" and "schedule that anneals" were the same experiment**
> `_total_steps = EPOCHS × (tokens // WIN)`, measured **once**, at the seed vocabulary. Minted tokens
> are longer, so every later epoch is shorter. Four runs at one seed, everything else identical:
>
> | arm | projected | ran | over | cosine reached | ended at |
> |---|---|---|---|---|---|
> | E8 minting | 63,024 | 48,130 | 31% | p=0.760 | 18% of peak |
> | E12 minting | 94,536 | 70,368 | 34% | p=0.742 | — |
> | E18 minting | 141,804 | 103,805 | 37% | p=0.730 | 21% of peak |
> | FROZEN vocab | 118,776 | 118,743 | **0%** | **p=1.000** | **5% of peak — as designed** |
>
> *"The frozen-vocabulary run is the only one that has ever annealed, and only because a vocabulary
> that does not grow makes the projection exact… the tokenizer conclusion I drew from those four runs
> was not supported."*
> **Diagnosed** `a3c610d` (the ETA half), **fixed** `5f4f117` (`_lr_at` reads `_proj_steps(step)`,
> clamped to its running minimum). **Blast radius** — `8c8d20b`'s *"freezing the vocabulary removes
> the divergence entirely"* is confounded with the LR schedule. It also means **EPOCHS was never just
> run length**: at step 48,130 the E18 schedule was at 1.52e-3 and E8 at 3.58e-4. See
> [INV-29](#the-invalidation-list).

> **`E8.4` — `EPOCHS` silently set the learning rate at every step**
> Measured on the `vmax4k` pair — identical config, identical vocabulary trajectory:
> step 20000 → 1.4×, step 40000 → 7.6×, step 44000 → **11.0×** apart. *"Step 44000 is where the
> 8-epoch run posted its best held-out (2.059) at 5% of peak, while the 18-epoch run was at 56% and
> moving away from its own minimum. **'8 epochs beat 18' and 'a low LR beat a high one' were the same
> observation.**"* The 18-epoch run filled its vocabulary completely, so dead rows do not explain it.
> **Found/Fix** `9fabba4` (`LR_EPOCHS`), default fixed at 8 in `c214c21`.
> **Compounding it**: *"The LR appeared in no log line anywhere, which is how a lever moving the rate
> 11x stayed invisible across every comparison made so far."*
> See [INV-30](#the-invalidation-list).

> **`E8.5` — the `frozen`/`frozen_nr` pair was not a clean single-knob comparison**
> Per `E3.5`, `RETOK_EVERY=0` also silently disabled signature batching, so the two arms differed in
> **two** ways.
> **Found** `79dac6c`. **Blast radius** — the 4.364 vs 2.175 gap quoted in the source as *"the largest
> single effect on record"* and used to justify the retok guard. See [INV-10](#the-invalidation-list).

> **`E8.6` — `VMAX` was silently re-rolling every weight in the system**
> `FROZEN = torch.randn(V, D)` sat at **module scope, unconditional**, with `V == VMAX`. It drew `V*D`
> numbers from the global generator **before anything else was built**, so changing `VMAX` shifted the
> RNG stream for every module constructed after it — including the ones that are not `VMAX`-shaped at
> all. Verified directly: `enc.weight_ih[0,:3]` and the fabric's routing centroids differ across
> `VMAX` 2048 / 4096 / 8192.
> *"Three runs 'differing only in VMAX' were three different random initialisations of the whole
> system."* And `FROZEN` is dead weight anyway — `key_frozen` is reached only under `KEY_SRC=frozen`
> and the default is `model`, so at `VMAX=8192` it was an 8192×D tensor allocated on device and never
> read.
> **Found** `0f96784` — by asking why the VMAX ordering was non-monotonic. **Fix incomplete on the
> first attempt**: re-seeding once before the construction line was not enough, because `build_lm()`
> draws `V*d + d*V + V` and `enc` is built on the **same line** after it — measured after that
> attempt, encoder step-0 loss **7.20 at VMAX=2048 against 6.93 at 4096**, on a module that is not
> VMAX-shaped and must not move at all. **Fully fixed** `79dac6c` (a seed per module: model, enc,
> world, fabric).
> **Blast radius** — the whole VMAX field: the `VMAX × EPOCHS` 2×2 (`0279709`), the six-run 18-epoch
> field (`9ca8057`), and *"the non-monotonic VMAX ordering that looked like a bug worth hunting."*
> The commit puts the magnitude in context: a 0.05% perturbation (`SAVE_CKPT`) produced a 1.594 b/B
> spread, and *"a full re-roll of every weight is vastly larger than 0.05%, so the non-monotonic
> ordering needs no further explanation and the comparison cannot be attributed to VMAX."*
> See [INV-31](#the-invalidation-list).

> **`E8.7` — the "two uncontaminated cells" of the VMAX×EPOCHS 2×2**
> `0279709` argued `vmax4k@8 vs vmax4k@18` (+1.110) differ in EPOCHS *hence in the LR*, so confounded;
> and `vmax4k@18 vs vmax8k@18` (+1.133) *"is clean: doubling a FULL vocabulary costs +1.133 b/B at
> fixed epochs."* **That second claim is superseded by `E8.6`** — the two arms had different
> initialisations of every module.

> **`E8.8` — the restart comparison was confounded with the retok guard**
> `9ca8057` states it in the commit: both arms run with and without restarts came back worse with
> them, *"but that is confounded with the retok guard, which is present only in the restart runs."*
> Then `33a9299` refuted the whole reading (see `E8.15`).

> **`E8.9` — `pilot_gru_8` ran `TOK_COMPOSE` and `TOK_MINT_NOVEL` at once**
> and so cannot be attributed to either.
> **Recorded/Fix** `d79c4ba` (a 2×2 separating them; every token arm now states both knobs
> explicitly, since `TOK_COMPOSE` becoming the default had made the existing `compose` and `mintnovel`
> arms stale — *"both would have ridden on top of the composer"*).

> **`E8.10` — the `TOK_COMPOSE` comparison mixed harness modes**
> It compared one run against a band assembled from **different** harness modes, *"which we later
> found shifts a result by more than a bit/byte on its own"* (`SAVE_CKPT` gating extra holdout passes
> — `E4.3`).
> **Found** `bdce727`. **Fix** — caveats stated; `GRID_CKPT=0` pinned in `707f1af` so the mode is
> constant across a bundle.

> **`E8.11` — configs C and D of the domain campaign changed two things at once**
> Both changed the threshold rule **and** `ENC_WARMUP`, so neither can be attributed.
> **Recorded** `6397041`.

> **`E8.12` — `ep18_big` is not comparable to the 8-epoch arms on raw held-out**
> The corpus was re-fetched larger for that run and got **harder**: order-1 moved **3.440 → 3.747**.
> Against each run's own order-1 anchor it is 1.411 vs 1.441 — *"18 epochs bought nothing, and did not
> cost the 0.34 the raw numbers suggest either."*
> **Recorded** `ac79e92`. **Rule this establishes**: quote every held-out figure against its **own**
> run's order-1. See [INV-32](#the-invalidation-list).

> **`E8.13` — `MODEL=transformer` has run twice and neither run means anything yet**
> `longrun.sh` said it *"has never been run here"*. It has: two pilots at d768 L4, held-out **2.130 and
> 2.184**. But both ran under `FAB_GROW=1` to 4096 experts, **before the instrument fixes**, and both
> carry the broken-base signature the 2×2 later explained — model ALONE **4.680 and 4.952**, with the
> fabric compensating by **+2.625 and +2.801**. *"That is arm D seed0 exactly."*
> **Found/Fix** `bf53d40` (the comment now says which of the two things is true).
> **Blast radius** — the architecture has never been evaluated in a configuration where the base model
> survives; and the GRU-vs-transformer comparison quoted in `245bc68` (GRU 2.064/2.200 vs transformer
> 2.130/2.184, coherence 0.17 vs 0.02) inherits both this and `E7.6`. See [INV-33](#the-invalidation-list).

> **`E8.14` — the dead-row series is not established**
> The claim *"the dead fraction ordered the results 0% → ~2.2, 41% → 3.561, 75% → 6.114"* was
> **removed** at `0279709`: `vmax8k@18ep` filled its vocabulary completely (8192/8192, 0% never
> minted, 1.3% ordinary turnover) and is **the worst of the four runs** at 4.383 — 0% dead produced
> the worst number. Then `e9f2e58` ran the **first controlled test** (`LOSS_MASK_DEAD`, same seed,
> same config, one knob): **+0.060 against a combined SE of 0.055 = 1.1σ.** *"A hint, not a finding…
> The correlation may still be real at pilot scale and on a longer run; it is not established, and I
> have been repeating it as though it were."*
> Note the earlier arms it was drawn from differed in far more than their dead fraction and were
> measured through the instrument that was editing runs. See [INV-34](#the-invalidation-list).
> `e9f2e58` also records a placement error caught by the measurement: **masking at the loss only is
> worse than not masking** (unmasked 4.746 ± 0.043, masked-at-loss-only 6.100 ± 0.074, masked
> everywhere 4.686 ± 0.034) — because the model is never taught to push the dead rows down and every
> eval path then scores it with those untrained rows still in the denominator.

> **`E8.15` — the seed floor refutes the premise under every single-run comparison in the record**
> `6bd226c` (2026-08-05) measured seed variance for the first time: paired pilots at SEED=0/1 give
> society 2.067/2.007 (spread 0.060) and chained society 2.101/2.275 (spread **0.174**). *"The four
> best architectures in this project sit inside 0.06 b/B of each other."* **Two claims withdrawn in
> that commit**: *"SPECIALIZATION 0.132, the highest recorded, and emergent"* → **0.009 at seed 1**;
> *"the only arm whose curve is flat, −0.007"* → **+0.298 at seed 1**. *"Both were seed artifacts
> presented as findings."*
> `33a9299` (2026-08-13) then measured **four runs of one nominally identical arm**: 2.023 / 2.132 /
> 3.054 / 3.250 — **spread 1.227 b/B**, word quality swinging **43% to 89%**. Two of them share a
> schedule setting and differ by 1.227 on their own.
> *"So the run does not refute restarts either. It refutes the premise under every single-run
> comparison in this record, including the ones I drew this session: 'vmax4k is the best regime',
> 'restarts are net-negative', '2048 misbehaves at 18 epochs'. The arm's own four runs span more than
> the gap to every other arm."*
> **What survives** by the commit's own accounting: what is exact (the determinism check) or far
> outside 1.6 b/B, and the code defects themselves.
> See [INV-35](#the-invalidation-list) — this is the single widest invalidation in the file.

> **`E8.16` — the `+0.709` FABRIC number was a knockout, not an ablation, and it justified a default**
> `7a42f90` measured *"fabric contributes +0.709 bits/byte (3.905 → 3.196), four times what the memory
> contributes"* and defaulted `FABRIC` ON on the strength of it. That is an **eval-time knockout** of a
> component the model trained with. The **retrained** ablation says **3.089 vs 3.090** — no bits/byte
> at all.
> **Corrected** `e60b8e0` (*"Using the knockout number (+0.709) to justify defaulting FABRIC ON was
> exactly that mistake"*). **Retracted from the source** `9d90416`. Note the fallback justification
> offered at `e60b8e0` — coherence 0.75 vs 0.50 — is itself `E7.6`.
> See [INV-36](#the-invalidation-list).

> **`E8.17` — V-measure against the seeded corpora was the wrong target, for weeks**
> *"The four corpora are a SCAFFOLD — they are how the stream is built, not what the system is asked
> to find… V-measure against 4 labels actively PENALISES the intended behaviour: discovering that
> English splits into narrative and dialogue lowers V while being exactly what is wanted. I had
> inherited the seeded labels as the optimisation target and spent four attempts tuning toward them."*
> It also explains why the seeded metrics contradicted each other all session: **purity rises with
> fragmentation, completeness falls with it, and neither can see whether anything recurs.**
> **Found** `efb818a` — which replaced the headline with **recurrence** (visits per domain; the
> fraction visited exactly once; the fraction recurring ≥3 times).
> **Consequence stated in the commit**: *"the four configurations measured so far need re-ranking on
> recurrence. Config A scored best on V-measure, but if its 142 domains are all single-visit while
> another produces 30 that recur, A is the worse system by the criterion that matches the design."*
> See [INV-37](#the-invalidation-list).

> **`E8.18` — `MANAGE_MERGE=0.45` was tuned to the wrong target and reverted**
> 0.45 maximised V-measure against the four seeded corpora, *"which is the wrong target, and it was
> bought with the one property the domain id actually controls"* — the granularity of forgetting.
> Measured: unlearning one process at 25 domains is 20 deletes of ~1.6% each; at 4 domains it is a
> single delete of 30%. *"Coarser domains do not predict better, they only make editing blunter."*
> **Reverted** 0.45 → 0.28 at `8914dd1`. Also recorded there: the falsification test from `13e787a`
> showing "4 domains" is reachable two ways and **the count alone cannot distinguish them** (0.45 → 4
> live at purity 0.97; 0.80 → 4 live at purity 0.71, "COUNTERFEIT 4"), and that 0.45 gives 7 on CPU
> and 4 on GPU, *"so the threshold is a scale, not a target."*

> **`E8.19` — "the encoder budget dominates the assign rule" — withdrawn**
> `probe_ckpt_geometry.py` on the 4 MB rerun's own encoder settles it: mean true-corpus silhouette
> **+0.24**, 1-NN corpus accuracy **0.984**, d_between/d_within **1.71**. *"The encoder separates the
> kinds. It is not the bottleneck, and the earlier 'encoder budget dominates the assign rule' reading
> is withdrawn."* The real constraint was arithmetic in the testbed (`E2.6`).
> **Retracted** `3f44ce3`.

> **`E8.20` — the InfoNCE-straddling hypothesis is refuted, and runs the wrong way**
> The hypothesis that InfoNCE positives straddling domain boundaries explains the `eng,py` two-domain
> collapse: measured over **400k sampled pairs** at `SEG_MIN/MAX=700/1800`, `WIN=128` — NP=2 gives
> 11.8% straddling / 6.6% cross-domain, NP=4 gives 17.3% / 9.7%. *"Contamination is HIGHER with four
> domains, so the effect runs opposite to what the hypothesis requires."*
> **Refuted** `b3ce153`.

> **`E8.21` — four failed router fixes built on a 32-window probe**
> See `E7.9`. Recorded here because the cost was four interventions, not one wrong number.

> **`E8.22` — the Verification standalone result did not transfer, and the overclaim was owned**
> The standalone console A/B on real data gave AUC **0.978 vs 0.903** and precision@1% **100% vs
> 30.5%** (`213820d`), GPU-confirmed at AUC 0.980 vs 0.907 (`c88fb7a`). In the product loop it read
> **0.3% precision, worse than the thing it replaced**, and `VERIFY_SWEEP` gutted the store (~21k of
> 292k deleted, mostly genuine) (`9df85b8`).
> `d7c141b`: *"The standalone's 100%@1% was an FPR≈0 projection that doesn't hold on the real
> heterogeneous store… Owned the earlier overclaim off the standalone."*
> `f5303d6`: the 5x-steps run ruled out undertraining — **0.3% precision at 5x steps** (0.3/0.5/0.3
> across three runs). *"Locked as a dead end for store-wide use; per-candidate check only."*
> **Status** — reframed honestly: reconstruction is a strong per-candidate discriminator (~98%) whose
> home is the reconcile→understand gate, **not** a store-wide auto-delete. See
> [INV-38](#the-invalidation-list).

> **`E8.23` — the Verification integration failure had a mechanism, and it is the project's own
> tokenizer**
> The Reconstructor was trained **jointly** during the loop, but the online tokenizer re-tokenizes the
> stream (256 → 6176) and keys get re-keyed, *"so the genuine-association manifold is a moving target
> → the signal is noise."*
> **Found/Fix** `9df85b8` (`verify()` fits the Reconstructor **post-hoc** on the final, settled store;
> joint training off by default, `RECON_W=0`).

> **`E8.24` — the verification test's first version measured the easy regime**
> It used 50% cross-domain corruption — *"the EASY regime B already handles (~97%)"*. Rewritten
> faithful (surprise-gated genuine negatives, base-rate-honest metrics) **before it produced a
> number**.
> **Caught** `213820d`, in the building of it.

> **`E8.25` — the naive joint autoencoder gave AUC ~0.65 because the key dominated**
> and diluted the token signal. *"Caught on CPU and fixed to cross-reconstruction before any GPU
> run."*
> **Caught** `fbdcd50`.

> **`E8.26` — the bench's ~85% encoder share does not generalize, and its two configs were not matched**
> `contrastive_step` is **shift-gated**: it runs every step near a detected boundary and every
> `ENC_EVERY_IDLE` (12) steps when the stream is stable. Every profile so far used the 4-domain mix,
> which switches constantly, *"so the encoder was effectively always at the dense cadence."* A short
> single-domain run drops it to **33%**. And `LAYERS` was 4 for transformer and 1 for GRU, so
> comparing config A against C would have compared models differing **~8x in parameter count**.
> **Found/Fix** `096094b` (LAYERS set explicitly per config; parameter count reported; the summary
> sheet says the ranking is data-dependent).

> **`E8.27` — "low GPU util = launch-bound" was wrong guidance**
> `utilization.gpu` is time-occupancy, not FLOP efficiency, and the average covered ~10s of pre-loop
> startup; **in-loop it was ~40–50%, not 16–22%**.
> **Corrected** `a5cd9ed` (tail average reported alongside the full one). Replaced with the real
> diagnosis: the step is dominated by `_model_key`, which ran ~1952 times per 976 steps on tiny tensors
> against ~61 real LM forwards — a **dispatch-count** problem, 90.5% of the transformer's deficit.

> **`E8.28` — `STREAM_LEN` is in bytes but the loop iterates the token stream**
> So `STEPS=1800` produced **976** steps (the BPE compresses ~1.84 B/tok).
> **Found/Fix** `a5cd9ed` (scaled by a BPT factor).

> **`E8.29` — the world model's status is an honest negative that was never re-measured**
> Against a **param-matched** monolith on a toy multi-regime probe the population is **−5.1%** with
> routing purity 0.32 — *"separation does not improve accuracy or specialize on these tests"*
> (`74d10d8`). Its first and only full-stack reading is *"beats baseline **−84.7%** | latent std
> 0.07"*, which by its own printed criterion means it **has not learned dynamics** (`51889b7`,
> 2026-07-29). **NOT re-measured since. It defaults ON.**
> See [INV-39](#the-invalidation-list).

> **`E8.30` — `I(dom; pair) == I(dom; hop0)` was read as "the second hop carries zero information"**
> *"That reading is wrong. `I(dom; pair) >= I(dom; hop0)` always, and when hop0 already identifies the
> domain at ~0.83 the metric is saturated — equality is also what CORRECT behaviour looks like."*
> **Claimed and retracted** across `e0ce4f7` / `7e9612d`. The diagnosis was reported **before** it was
> tested; the three interventions built on it (`CHAIN_SUP`, `CHAIN_CURRIC`, `CHAIN_STATE_Q`) are
> evidence *against* it, and are all off by default.
> **Replaced by** `H(hop1 | hop0)` measured at the run's own scale — 0.007–0.058 bits for every
> transition arm against **0.533** for the soc-loop.

> **`E8.31` — the depth and ponder figures described a path the run did not use**
> Two corrections in `33355b2`, both explicit:
> 1. *"'the router HALTs 90%, mean routed depth 0.10 of 4' — I quoted this for several rounds as
>    evidence about the system. It comes from a report-time probe call to `forward()`, not from
>    anything that trained. It describes a path the run did not use."*
> 2. *"I built the case for the whole pilot on 'PONDER_WARM=8000 never completes'. On the society path
>    the ponder cost is identically zero, so `PONDER_WARM` does nothing at all. That justification was
>    wrong. **Second time this session a justification of mine was about inert code.**"*
> **Blast radius** — every depth/HALT figure before 2026-08-04, and the framing of the pilot itself.
> See [INV-40](#the-invalidation-list).

---

## 9. Harness and plumbing

> **`E9.1` — `SAVE_CKPT=0` wrote checkpoints to a directory literally named `0`, and it got committed**
> Every other switch in the file is an integer flag, so `SAVE_CKPT=0` is the obvious way to turn
> checkpointing off — but `SAVE_CKPT` is a **path**, and `"0"` is a truthy string in Python.
> `if not ck: return` never fired, `os.makedirs("0")` ran, and runs wrote `ckpt.pt` / `ckpt.prev.pt` /
> `source.bin` into a directory named `0` in the repo root. `.gitignore` did not catch it —
> `source.bin` is not `*.pt` and `0/` is not `runs/` — so `git add -A` picked it up: **3.7 MB of
> checkpoint plus a 60 kB `source.bin` committed and pushed**.
> **Found** `7ca2061` — noticed in a pull as `create mode 100644 0/source.bin`. **Fix** `7ca2061`
> (normalises the disabled spellings `"0" "" off no none false` once, before any of the four call
> sites; removes `0/` from the index; adds `/0/` and `source.bin` to `.gitignore`).
> **Related**: `_save_ckpt` also returned early on `SAVE_CKPT=0` without saying so, and the caller
> assumed success — *"the log read 'saved to None.best' on a run that saved nothing"* (`8c8d20b`).

> **`E9.2` — arm flags placed before hardcoded env were silently discarded**
> `env A=1 A=2` keeps the **last** assignment, and `$FLAGS`/`$ARMFLAGS` came **first**, so every knob
> hardcoded after them — `VMAX`, `WIN`, `BATCH_W`, `RATE_EVERY`, `CKPT_EVERY`, `GROW_*`, `SEG_*`,
> `DATA_DIR`, `LAYERS`, `MODEL` — overrode the arm. **`grid 3 VMAX=512` ran at 2048 and named the log
> 512.**
> **Found/Fix** `5f4f117` (flags last, with the loop's own `SEED` after them). **Blast radius** —
> *"the earlier `grid base VMAX=8192` would have run at 2048 and named the log 8192"* (`c6f54e6a`);
> `SEED_VOCAB` was not in grid's hardcoded env list so it did reach (`a21a721`). Any pre-`5f4f117` log
> whose name mentions a knob in that list is suspect. See [INV-41](#the-invalidation-list).

> **`E9.3` — "already complete, skipping" was not asking whether the run matched the config**
> `TAG` is derived from `ARMFLAGS` alone. It is blind to `EPOCHS`, `STREAM_LEN`, `D_MODEL`, `SIG_WIN`,
> `MEM_QUOTA`, `DEVICE`, `PILOT_DIR` and **the commit** — every one of which `seeds` reads from the
> environment. So:
> ```
> EPOCHS=8  bash longrun.sh seeds 3     # runs, writes default_seed{0,1,2}.log
> EPOCHS=18 bash longrun.sh seeds 3     # SKIPS ALL THREE
> ```
> *"and the SEEDS SUMMARY then globs those logs and prints the 8-epoch held-out numbers under the
> 18-epoch banner. **The wrong answer is not merely kept, it is reported.**"* Same shape in `grid` and
> `repeat`.
> **Found** `42d8686` — by an exhaustive audit of cross-run state (39 candidate channels, each
> adversarially verified; **exactly one real channel, and it is not model state — it is the reported
> number**). **Fix** `42d8686` (a `.cfg` stamped beside every log; the skip compares it; a log with no
> `.cfg` stops and names the reason). **Did NOT affect the 3-seed pilot**: fresh `SEED_DIR`, all three
> logs carry the same commit and a complete report.

> **`E9.4` — an unknown arm name ran the defaults under the misspelled name**
> `_flags_for` returned `""` for an unknown arm, *"so a typo ran the DEFAULT configuration under the
> misspelled arm's log name — a result filed against an experiment that never happened."*
> **Found/Fix** `b6952da` (sentinel; both callers refuse it).

> **`E9.5` — six arms were configured to guarantee dead rows**
> `frozen` came back **6.114 b/B with 4% real words**. *"That is not a measurement of a frozen
> tokenizer."* `frozen` was `TOK_MINT_UNTIL=1` and nothing else, and the grid hardcodes `VMAX=2048`,
> so the softmax was 2048 wide over a vocabulary frozen at 512: **1536 rows (75%) never a target**,
> holding their initialisation in the denominator for 48k steps. An audit of all 46 arms found five
> more:
>
> | arm | defect | dead | fix |
> |---|---|---|---|
> | `frozen` | `TOK_MINT_UNTIL=1` | 75% | `VMAX=512` |
> | `frozen_nr` | `TOK_MINT_UNTIL=1 RETOK_EVERY=0` | 75% | `VMAX=512` |
> | `frozen1k` | `SEED_VOCAB=1024`, VMAX left at 2048 | 50% | `VMAX=1024` |
> | `freeze6k` | freeze at 6000 buys ~600 mints | ~45% | `VMAX=1024` |
> | `vmax8k` | 8192 needs ~14 epochs, grid runs 8 | 41% | `EPOCHS=18` |
>
> **Found/Fix** `b6952da`. **The fix was itself incomplete**, caught by the predictor added in the same
> commit: it pinned `VMAX` while assuming `SEED_VOCAB=512`, true of `self_organize`'s default and not
> of the smoke harness, which sets 256 — *"so `frozen` under smoke was straight back to 50% dead rows
> with a different pair of numbers."* Completed `25c37eb`.
> **Blast radius** — *"the recorded `frozen_nr` result (2.365) was measured under 75% dead rows and is
> not a clean measurement of 'no re-segmentation' either."* See [INV-42](#the-invalidation-list).

> **`E9.6` — `equiv.sh`'s completion marker matched line 8 of every log**
> `run_side` checked for `SIG_MODE=learned`, which is in the **header** of every run. *"So a run that
> died at startup counted as complete, and a partial log counted as 'already done, reusing'… Either
> path yields a verdict computed from logs that were never comparable — **a false IDENTICAL, which is
> worse than no test.**"*
> **Found** `37ecb20` — *"because a verification I was watching reported its first side 'reached the
> report' while the log was 1.4 kB and the process was still running."* **Fix** `37ecb20` (uses the
> full sentence `longrun.sh`'s `_done()` uses, in both places).

> **`E9.7` — the DIRTY flag counted untracked files**
> `git status --porcelain` lists untracked as well as modified, and a tree that has ever run a pilot is
> full of them — so a freshly-pulled, unmodified checkout reported DIRTY. *"A false alarm about the one
> thing it exists to certify."*
> **Found/Fix** `4da76b8` (tracked modifications only; `data_pilot/`, `data_big/`, `data_grid/` added
> to `.gitignore`).

> **`E9.8` — smoke duplicated the arm definitions, and `_flags_for` was defined inside another `case`
> branch**
> The smoke test repeated `_flags_for`'s contents instead of calling it, and the two had already
> drifted — `prob_use` 150 vs 200, `prob_emb` likewise, `compose` missing `TOK_MINT_NOVEL=0`. *"Three
> of seven arms were configurations the grid will never run. A smoke test that greenlights something
> nobody executes is worse than no smoke test."*
> Calling `_flags_for` exposed a larger problem: it was defined **inside the `grid)` case branch**, and
> a function defined in one branch does not exist in another — *"smoke would have resolved every arm to
> the empty string: seven identical runs reported as seven passing arms."* Verified minimally:
> `case smoke in grid) f(){...};; smoke) type -t f` → UNDEFINED.
> **Found/Fix** `136461c` (both hoisted to top level).

> **`E9.9` — `TOK_PROBATION_STEPS=5000` never elapses at 3 epochs**
> So probation would silently never judge anything *"and the arm would pass while testing nothing."*
> **Found/Fix** `136461c` (moved to smoke's COMMON env as a scale adaptation, not part of the arm).

> **`E9.10` — `pilot-add` never created `$OUT`, so a finished run lost its entire report**
> `pilot` runs `mkdir -p "$OUT"`; `pilot-add` never did. **`tee` opens its output file at process
> start, before python writes a byte**, so on any machine that has run `seeds` but not `pilot` the
> directory does not exist, `tee` fails instantly, and the whole report goes to a closed pipe. *"The
> worst version of a failure: hours of GPU, a valid checkpoint written, and no record of what it
> measured."*
> **Found** `40de03d` — after it happened. **Fix** `40de03d` (`mkdir -p` before the run; both paths
> printed before the GPU is spent) **plus `holdout.py`**, which reconstructs ACROSS THE RUN BOUNDARY
> from the `holdout`/`holdout_step` dicts every checkpoint already stores, applying the same 2σ test.
> **Blast radius** — **the one continual-learning run's log (`a9d7258`) was lost; its numbers come
> from a terminal copy.** See [INV-43](#the-invalidation-list).

> **`E9.11` — `_reserve` was called twice, so a checkpoint and its log could get different names**
> A second `add` could put the checkpoint at `pilot_gru_py-2` and its log at `pilot_py.log` — *"a
> result filed under a name that does not match the model that produced it."*
> **Found/Fix** `40de03d`.

> **`E9.12` — `pilot-add` could not reach the checkpoints that exist**
> It hardcoded `RESUME="$OUT/pilot_$PA"`, *"so everything written by seeds/grid/repeat was unreachable
> and continual learning could only be attempted from a run shape nobody uses."*
> **Found/Fix** `2ba3ac1` (`RESUME_FROM=<dir>`, finding the `.dyntok.json` saved beside it).

> **`E9.13` — `runs.py` could not ingest any post-fix log**
> Adding the error bar (`E4.6`) changed `train X | held-out Y` into
> `train X +/- a | held-out Y +/- b (...)`, and the registry's regex predates it. Every run since
> failed with *"has no 'train … | held-out …' line — did the run reach its report?"*, **which reads as
> a broken RUN rather than a broken parser.** *"A registry that silently stops accepting new runs is
> worse than no registry: the gap only shows up later, as an absence."*
> **Found/Fix** `ed8af6b` (optional group matches both spellings; the standard error becomes its own
> column — *"it is the number that says whether two rows differ"*).

> **`E9.14` — `seeds` and `repeat` never fetched the corpus**
> `pilot` and `grid` each carried their own copy of the fetch-if-empty guard; `seeds` and `repeat`
> were added later and got neither, so they parsed arguments, created their output directory, printed
> their banner, **and then died inside the model** on "no corpus files in `data_pilot/train/eng/`" —
> a setup failure surfacing as a config error after the harness had said it was starting.
> **Found/Fix** `adbc07a` (one `_pilot_corpus()` called by all four; it also re-checks afterwards,
> because `fetch_big.py` exiting 0 while writing nothing is the same wasted setup one step later).

> **`E9.15` — `prompt.py` was completely dead, and broke twice more afterwards**
> It carried its own **duplicated copy of `Fabric`**, which went stale the moment the population became
> tensors: `load_state_dict` failed on ~300 missing keys. *"That is the tool used to read GENERATIONS
> — the deliverable — and it would have failed silently until someone tried it."* Dead for several
> commits.
> **Found/Fix** `763e9f2` (69 lines of duplicated model code deleted; imports the real `Fabric`).
> **Recurred twice**: `e44b5b0` — per-window routing threw the moment `idx` became `(B,k)`, because it
> still carried its own copy of the ensemble **logic** even after importing the classes; and
> `7b28570` — the chaining branch did `_h = FAB(...)`, assigning the whole `(h, depth, mass, bal)`
> tuple and handing a tuple to `model.head`, *"a guaranteed TypeError the instant a chaining checkpoint
> was sampled."* Also `7b28570`: `prompt.py` took the routing **path** from the environment, so a
> checkpoint trained as a society would be generated as a chain purely because the default had changed
> since it was saved — the checkpoint decides now.
> **Countermeasure** `4554d6b1`: *"Nothing in the pipeline ever loaded a checkpoint after writing one,
> which is exactly how `prompt.py` sat completely dead for several commits."* The read-back gate arm
> was added, and `e44b5b0` records the first time it earned its keep.

> **`E9.16` — the gate's `no_experts` arm was vacuous and had always passed**
> See `E2.10`. *"It has been reporting coverage it never had."*
> **Found/Fix** `4554d6b1`.

> **`E9.17` — two ablation arms were broken because they had never been run**
> `ab_no_world` exited 1 and produced no data: `WORLD_GROW` defaults ON and its step hook called
> `world_fwd.n()` outside the `if WORLD_MODEL:` block, so `WORLD_MODEL=0` died at the first
> `MANAGE_EVERY`. *"The one ablation that would have said what the world model is worth was the one
> that could not run."*
> The smoke added in the same commit immediately found a second: **`SIG_SPACE=tokens` crashed in the
> eval battery** — the training loop converted the loop index into `ENC_SEQ` correctly
> (`i if SIG_SPACE == "tokens" else bpos`) while every **eval** site did `tok_bs[s]` unconditionally,
> which under `SIG_SPACE=tokens` scales a token index by ~2.5 and reads a window from the wrong place.
> *"That is silently wrong first and loudly wrong only at the tail."*
> **Found/Fix** `e60b8e0` (both; conversions go through one helper, `encpos`/`encwin`).

> **`E9.18` — the gate passed a change that killed both pilot arms in under two minutes**
> Every smoke arm ran 12 kB, *"where the vocabulary barely moves, the stride stays put, and `asm.wins`
> never holds two widths."* **"A gate only covers what it exercises."**
> **Found/Fix** `2a682d7` (a `vocab_growth` arm — 200 kB, `VMAX=1024`, `GROW_EVERY=20`,
> `REKEY_EVERY=200` — which reproduces the failure and now guards it).

> **`E9.19` — `generate()` did not sanitize its distribution, and four of eighteen arms lost their
> entire report**
> `multinomial` raises a device-side CUDA assert on any non-finite entry, **inside the report** — so
> four arms finished training and then lost everything at the last step. *"A diverged run produces
> exactly that. Generation is a DIAGNOSTIC of a possibly-broken model and must survive one."*
> **Found/Fix** `ffd39b8`. **Blast radius** — 4 of the 18-arm grid's arms have no report.

> **`E9.20` — every arm was overwriting the same tokenizer file**
> `longrun.sh` never set `TOKENIZER_PATH`, so `grid`/`seeds`/`repeat` all wrote `data/dyntok.json` and
> **each run destroyed the previous arm's vocabulary** — *"the same class of overlap as the levers,
> with the arm's identity not reaching its artifact."*
> **Found/Fix** `ec9813e`. Safe historically because under `TOK_ONLINE` without `RESUME` the loader
> never reads the file back — but it means no pre-`ec9813e` arm's vocabulary survives for inspection.

> **`E9.21` — re-running a pilot destroyed the previous one**
> Every subcommand wrote `$OUT/<name>.log` and `SAVE_CKPT=$OUT/<name>` directly, *"including the
> checkpoint `pilot-add` and the ACROSS THE RUN BOUNDARY section use as their baseline."*
> **Found/Fix** `09e3d60` (`_reserve()` suffixes `-2`, `-3`, …; `runs/` is append-only).
> *"Results are the expensive part of this project."*

> **`E9.22` — run scripts had a dead hardcoded `cd ~/overarching-package`**
> From the old zip layout; it errors on every run since the repo was flattened. *"The run only
> continued because cwd happened to be the repo."*
> **Found/Fix** `9c6661a`.

> **`E9.23` — `fetch_big.py` could not open a gated dataset, three ways**
> (i) **No auth at all** — `load_dataset` was called with no token, so it worked only if the ambient
> `huggingface-cli` credential happened to be there: *"works on my machine", an opaque 401 anywhere
> else.* (ii) **Wrong field** — the-stack keeps its text in `content`, the fallback preset uses `text`,
> *"that fails with a KeyError AFTER authenticating, which reads like an auth problem and is not one."*
> (iii) **No way to select a language** — the-stack is organised as directories, not configs.
> Also: a gated repo and a bad token raise indistinguishable errors, and the fixes differ.
> **Found/Fix** `b92f358` (`--token` with `$HF_TOKEN` fallback, both `token=` and `use_auth_token=`
> spellings, presets, `--data-dir`; the message now states whether the process saw a token at all).
> **Still untested against the network** — the sandbox reaches GitHub and PyPI only.

> **`E9.24` — `fetch_big.py`'s "Next:" suggestion invited an unrecoverable run**
> It always printed the heavy 22-hour config (`WIN=256 D_MODEL_B=768 VMAX=16384`) **with no
> `CKPT_EVERY`**, on any size of pull.
> **Found/Fix** `c685407` (heavy knobs only for corpora ≥250 MB; always include `CKPT_EVERY` and
> `RUN_NAME`). And it suggested `D_MODEL_B`, the name `self_organize.py` silently ignored — fixed
> `c46a32f`.

> **`E9.25` — `fetch_big.py` was not resumable**
> It always opened `part000` and re-streamed from document 0, *"so a failure at 30 GB meant starting
> over and silently overwriting what was already there."*
> **Found/Fix** `c46a32f` (manifest after every shard; `--resume` skips consumed documents).

> **`E9.26` — `smoke` and `repeat` were not in the usage line**
> *"I spent part of a session concluding `smoke` had been lost because `longrun.sh smoke` printed a
> usage line that did not mention it."*
> **Found/Fix** `451459d`.

> **`E9.27` — parallelising the gate introduced two bugs**
> `$JOBS` used in the banner before it was defined (`set -u`, instant death), and
> `grep -c || echo 1` **appending** to grep's own "0" so every arm compared unequal and reported FAIL
> at exit 0.
> **Found/Fix** `b610b89`.

> **`E9.28` — `prompt.py` only read `CKPT` from the environment**
> So the documented `python3 prompt.py CKPT=runs/<tag>` silently fell back to `runs/ck`.
> **Found/Fix** `e77b60e`.

> **`E9.29` — an injected rescue produced no visible result**
> `rescue_ckpt.py`'s injected-thread `print()` is buffered/lost. **Found/Fix** `5c59781` (durable
> `~/rescue_status.txt`, flushed). `6220031` records the honest correction that followed: **no
> checkpoint was saved.**

> **`E9.30` — the container rolled back at least three times, and unpushed work was at risk**
> `b6952da`: *"the container rolled back to 2c705c7 twice today and I restored from origin both
> times"* — and it produced a false audit finding (`_flags_for` reported as nested inside `grid)`,
> *"true of the checkout it read but not of the repo"*; every other finding was re-verified against the
> restored file). `046fd81`: *"the container has rolled back three times today and unpushed work is the
> only thing at risk"* — that commit was pushed with its end-to-end verification still running.
> **NOT FIXED** — infrastructure. Mitigation of record: push early, and `DOC_PLAN.md` item 4
> ("consider pushing the branch").

> **`E9.31` — editing `longrun.sh` while a background bash was executing it**
> *"bash reads a script by byte offset, so the hoist shifted the file under the running interpreter and
> it resumed in another branch."* Diagnosed at `136461c`; cost a diagnosis, not a result.

> **`E9.32` — no GPU noise baseline exists, so `equiv.sh`'s INERT verdicts are untrusted**
> `c6f54e6` establishes that the GPU is nondeterministic in exactly one subsystem (memory
> **retrieval**; every model-only and model+fabric figure matches exactly) and requires
> `equiv.sh HEAD HEAD` once per machine to write `runs/equiv_noise_<device>.txt` before any comparison
> is trusted. **Verified at HEAD: no `runs/equiv_noise_*` file exists in this checkout.**
> **NOT FIXED / OPEN.** Cross-ref `DOC_PLAN.md` open question 9.

> **`E9.33` — three improvised equivalence invocations were each broken the same way**
> They depended on a shell variable still being set, or wrote their output **inside a git worktree
> that the next line then deleted**. *"One of them would have destroyed the result it was asked to
> produce."*
> **Found/Fix** `2d93a3e` (a script, tested before use; every path from `${BASH_SOURCE[0]}`; output
> directory created and write-checked before anything runs; logs never inside a worktree).

> **`E9.34` — `_flags_for` resolves to empty for an arm that does not exist on the older commit**
> *"The trap in the last command I sent."* `equiv.sh` passes config directly rather than through
> `_flags_for`.
> **Found/Fix** `2d93a3e`. Note the same silent-empty failure as `E9.4`, in a second place.

> **`E9.35` — the corpus fetch was unbalanced, and the stream samples domains uniformly**
> `build_stream` picks each segment with `random.choice(act)` — **uniform over active domains, never
> weighted by how much text a domain has**. *"So an unbalanced pull does not give the big domain more
> attention: it gives the SMALL one more REPETITION."* The shipped sizes 20/8/10/1 GB over a 40 GB
> stream are **one half-pass of fineweb against roughly a hundred passes of oasst1** — the dialogue
> domain memorised while the web domain was barely read, *"on a run whose whole point is continual
> learning rather than memorisation."*
> **Found/Fix** `10842e8` (10/10/10/10; oasst1 dropped as too small).

---

## 10. Self-inflicted regressions during this work

Defects introduced by the work in this branch, listed because the pattern — *a fix that is itself a
bug* — recurs often enough to be a class.

### 10a. Fixes that broke what they were fixing

> **`E10.1` — recomputing `SIG_WIN` live killed both pilot arms, and the gate passed it**
> Closing the 42%-coverage gap (`E7.32`) by recomputing `_sigw` live as the tokenizer grew crashed
> both arms of the pilot at the first rekey: `ValueError: expected sequence of length 384 at dim 1
> (got 426)` — `asm.wins` holds sample windows captured at the **old** width and `rekey` concatenates
> them into one batch.
> *"The crash is the lesser problem. Domain centroids ARE means of encoded windows, so changing the
> width mid-run makes signatures taken before and after incomparable — every centroid, radius and
> boundary test would straddle two different measurements, silently. **Live update was wrong in
> principle, not just in implementation.**"*
> **Introduced** `98e3301`. **Found/Fix** `2a682d7`, one commit later, by running the pilot.
> See also `E9.18` — the gate certified it.

> **`E10.2` — the `main()` split: four bugs, then a revert at a 136-value seam**
> - `7de4daf` inserted `from types import SimpleNamespace` by replacing the first `import os`, hit a
>   **multi-import line**, and produced `from types import SimpleNamespace, math, random, glob, sys`.
>   *"`7de4daf` could not start at all — I committed and pushed a file that does not import."* It
>   **compiled clean**, so `py_compile` did not catch it; the smoke gate would have, but only after 11
>   arms. *"What caught it in four minutes was `equiv.sh` refusing to compare a side that never reached
>   the report."* Fixed `13099a1`.
> - `6732448`: the context carried 39 values and needed 50 — the free-variable analysis walked
>   assignment targets only and **missed the six functions `main()` defines** (`_retok`, `_save_ckpt`,
>   `_config_audit`, `encpos`, `encwin`, `report_holdout`). `NameError` at the first line of `_report`.
>   *"Two process failures, not one. The analysis was wrong, and I handed the run sheet over while my
>   own verification was still in flight."*
> - `9c59a84`: correcting for the read-and-write case took the context from 39 to **136**, including
>   `a, b, c, i, k, p, s, t, v, x`. *"That last number is the finding… There is no clean seam to cut
>   along."* **Reverted.**
> **NOT FIXED** — `main()` is ~2,940 lines with 658 locals at HEAD. Splitting it properly requires a
> rename pass first. Cross-ref `07_WIP.md`.

> **`E10.3` — `_units` was rewritten into infinite recursion**
> The regex that rewrote the call sites also rewrote the **body of `_units` itself**, leaving
> `return _units(TOK, USE_TOK, text)`. **It compiled without complaint.** *"What caught it was an AST
> assertion that neither helper appears in its own body, not the compiler and not reading the diff."*
> **Found/Fix** `343bfd7`, in the same commit.

> **`E10.4` — a two-character name collision silently deleted the retention section**
> `_hb` is the held-out probe dict carried in from a RESUME, assigned around line 3121 and read by
> `report_holdout` ~1700 lines later. The gate's report line reused `_hb` for a block **count**, so
> `report_holdout` got an `int` and died on `k in prev` — **inside the `try/except` that wraps the
> whole MEMORIZATION CHECK**.
> *"The cost was not a crash. It was `[memorization check skipped: TypeError…]` in place of
> train/held-out/gap, the ANCHORS, and ACROSS THE RUN BOUNDARY — **the retention measurement the
> continual-learning claim rests on**. A one-line message where the run's primary metrics should be."*
> **Found/Fix** `98f6c66`. *"658 locals in one 3000-line function, and a two-character name picked for
> a print statement quietly destroyed the headline result of every run that used the new knob. The
> registry catches knobs that disagree with their declared defaults; **nothing catches this**."*
> **Blast radius** — every run using the new knob between its introduction and `98f6c66`.

> **`E10.5` — the retok guard killed re-segmentation entirely** — see `E3.3` (`046fd81` → `d0728fe`).

> **`E10.6` — the mint gate starved the vocabulary in the first real pilot** — see `E7.49`
> (`fec2285` defaulted it on → `1a113f5` fail-open and default off).

> **`E10.7` — a `KeyError` armed by a rename 30 minutes earlier**
> Renaming probation's cadence to `_due("probation", ...)` was right, but `_fired` is a plain dict
> indexed **unguarded**, initialised with only `grow`/`retok`/`ckpt`/`lmcurve`. The first run with
> `TOK_PROBATION>0` would have died on `KeyError('probation')` with no `try/except` around it — *"i.e.
> **the fix for the armed grow bug was itself armed**."*
> **Found/Fix** `79dac6c` (`_fired` is now a `defaultdict`, so a new cadence can never crash a run).

> **`E10.8` — the VMAX re-roll fix did not work on the first attempt** — see `E8.6`
> (`0f96784` → `79dac6c`).

> **`E10.9` — the warmup ramp was reported as a cosine restart**
> The detector fires on the rate **rising**, which is right for a restart and wrong for the warmup:
> it climbs from 0, so the first few steps multiply the rate by far more than 1.5. An 18-epoch run
> reported three "cosine restarts" — at step 15 (2% of peak), step 31 (3%), and step 201925 (100%).
> **Only the third is one.** *"A log that cries restart is a log nobody greps for restarts."*
> **Found/Fix** `ac79e92` (a real restart must also return the rate to a large fraction of peak).

> **`E10.10` — the cosine restart was not marked self-inflicted**
> `note_shift` exists for *"the jump is OURS, not the data's"* and is called for retok and resample,
> **but not for the restart** — which takes the rate from the `LR_MIN_FRAC` floor to full peak in one
> step, a 20x jump, *"the largest self-inflicted loss jump in a multi-cycle run."* Unmarked,
> `PlateauGrowth` reads the regression as unexpected, fires a growth burst and can enter a RECOVER
> lockout of up to `FAB_RECOVER_MAX` steps; `maybe_deepen` resets `dp_wait` on the same spike.
> **Found/Fix** `79dac6c`.

> **`E10.11` — restarts did not replicate at 8 epochs, i.e. the one configuration that had to**
> When the wavelength **is** the run, `_prog` reaches 1.0 and `1.0 % 1.0 == 0.0` — **the rate jumped
> back to peak on the final steps of every 8-epoch run.** *"The one configuration that has to reproduce
> earlier results was the one it broke."*
> **Introduced** `c341921`. **Found/Fix** `fec2285` (fits a whole number of cycles to the run, rounding
> to the nearest and stretching the period to divide it exactly; truncating instead left a 30-epoch run
> with 2 cycles and a third of its length parked at the floor). Verified: 8-epoch max
> |restarts − hold| = 0.000e+00, bit-identical.

> **`E10.12` — `LR_EPOCHS` defaulting to `EPOCHS` reintroduced the never-anneals bug at short lengths**
> Clamping to `min(8, EPOCHS)` was required: *"without that a 3-epoch pilot would anneal over 8 and end
> near 76% of peak, reintroducing the original never-anneals bug as a default."*
> **Recorded/Fix** `c214c21`.

### 10b. Built to the wrong spec

> **`E10.13` — `TOK_COMPOSE` was built to the opposite of the requested spec**
> *"I built the wrong thing and you corrected it. `TOK_COMPOSE` removed per-token parameters entirely;
> the goal was the opposite — keep them, but make the TRANSITION from a mint to its composite easy."*
> **Introduced** `e8df6fe`. **Rebuilt** `ed04aac` (vector = composite(bytes) + a zero-init free
> residual). **Then defaulted back off** `be50e3a`: across every pilot log in the project, eleven runs
> across five commits sit in a 2.0–2.2 band; the two runs outside it are the two deliberate controls
> (`LR_SCHED=none` 4.193, `TOKENIZER=0` 4.378); *"the third is `pilot_gru_8` at 5.360, the one run with
> the composed token table."* Recorded in the same commit, correcting an earlier claim: *"minting is
> not costing level. Full minting gives 2.007–2.275; `TOK_MINT_UNTIL=6000` gives 2.189, worse than the
> median minting run and inside the seed spread."*

> **`E10.14` — the first `ByteComposer` sized its table to the live vocabulary**
> *"which made any lag between a mint and the refresh an IndexError on the training stream — which is
> exactly what the first version did."*
> **Found/Fix** `e8df6fe` (sized to `VMAX`; unused rows cost nothing when there are no per-token
> parameters).

> **`E10.15` — `WARMSTART_OPT`: the reason for adding it was disproved by checking it**
> The argument was that a never-gradiented row has v=0, so its first update is Adam's maximum step.
> *"Checked it directly and it does not hold: Adam's step counter is **PER-TENSOR**, not per-row, so by
> the time a token is minted the bias correction already reflects thousands of steps and **DAMPS** a
> fresh row."* Measured on a 5-step toy: the new row's first update was 5.4e-4 with v=0 and 1.0e-3 with
> inherited moments — *"inheritance makes the first step LARGER, the opposite of the motivation."*
> **Recorded** `1e62eff` — it ships **off**, with the disproof next to it.

> **`E10.16` — the composite-lever layer was built and reverted whole**
> `4e91275` added four levers (`TOKENIZER_MODE`, `PATH_MODE`, `ROUTE_SCORE`, `POP_MODE`) resolving to
> primitives; `a0df9a6` reverted it the same day; `4603b062` replaced it with making the three hidden
> couplings **print themselves**, *"this is the isolation the reverted lever layer was reaching for,
> done by making the machine state legible instead of adding a fifth control surface on top of four."*

> **`E10.17` — the first `DOM_RADIUS` estimated the radius from a censored sample and could not
> bootstrap**
> It used the distances at which a domain was **matched** — *"matching needs a radius, so nothing
> matched, no samples accumulated, and the radius never activated: **0 of 143 domains ever learned
> one**, and a pooled prior over the same censored sample did not fix it (the pool held 3–5
> entries)."*
> **Found/Fix** `f0375c5` (the reservoir is uncensored: a window is in it because it was assigned,
> whatever the threshold said).

> **`E10.18` — `DOM_RCAP=0.5`, the value tried first, was the worst in the table**
> 65 live / V 0.82 — *"it strangles the radius back to the baseline it exists to fix, because the cap
> is set by a SAME-corpus sibling."*
> **Recorded/Fix** `f0375c5` (calibrated rather than assumed; default 2.0).

> **`E10.19` — three constants validated on probe geometry, not on the loop, all shipped, all lowered
> the metric**
> `DOM_ADAPTIVE`, `DOM_RELATIVE`, `SHIFT_REL`. *"The scale analysis behind them is sound and the probe
> data is real… but a constant validated on probe geometry is not validated on the loop, and I shipped
> three that were not."*
> **Reverted** `6397041` (all three default 0; the repo behaves as config A).

### 10c. Terms that were never runnable

> **`E10.20` — `DIV_W` was un-runnable on both paths, and had been since routing went per-window**
> (i) On the **chaining** path `DIV_W` was read as a **local of `main()`**, so the implementation
> raised `NameError` on the first hop — *"that would have killed every chaining arm in the grid — 15 of
> 18."*
> (ii) On the **society** path it indexed `_O` (rank-ordered) with a **global expert id** from
> `_w.mean(0).topk()` — `IndexError` the first time anyone set `DIV_W > 0`. *"Nobody ever had, because
> it defaults to 0 — so **the one term in this system that rewards experts for DIFFERING has been
> un-runnable since routing went per-window, and silently**."*
> **Found** `3e67b5d` — *"both found by verifying the arms instead of assuming them."* **Fix**
> `3e67b5d`.

> **`E10.21` — `DIV_W` was then a silent no-op on `CHAIN_ROUTE=soc`, and the config audit certified it**
> The `DIV_W=0.05` pilot came back **byte-identical** to the `DIV_W=0` run: held-out 2.893, order-1
> +0.545, since-min +0.683, H(hop1|hop0) 0.533, specialization 0.000, top expert 25.2%, 424 distinct
> experts — **every figure.** The soc-loop branch returns early, before the transition path's
> distinctness term. *"Twenty minutes of GPU time measured the previous configuration."*
> **And the check that should have caught it did not**: the config audit verifies a knob's **value**
> was read and matches the live object — *"it cannot see whether the code path that USES it was ever
> reached. So it certified `DIV_W=0.05` as correct on a run where `DIV_W` was inert."*
> **Found/Fix** `b14d60e`, which added **the third layer**: auxiliary loss terms now report whether
> they actually contributed. *"A value can be wrong (banner), unread (typo), or read-but-unreachable
> (this). Each needed its own check because each is invisible to the others."*
> See [INV-44](#the-invalidation-list).

> **`E10.22` — the chaining transition did not depend on which expert held the mass**
> Verified directly rather than by reading: **all mass on expert 0 and all mass on expert 4 produced
> the identical next distribution.** `nxt = sum_n nm[n] * R[n]` collapsed to (total routed mass) ×
> (one global re-route), *"and the identity of the current expert was discarded every hop… 'expert A
> hands to expert B' was not a relation the router could represent, let alone learn."*
> *"That was mine. The original carried a per-expert `Linear(sig_d, dk)`… I collapsed it to one shared
> `q_route` when tensorising for scale — it was the O(N·sig_d·dk) term measured at 345 ms for N=65536
> — and did not notice what it removed, because the SOCIETY path never evaluates R at all."*
> **Found/Fix** `012a2e0` (restored as an outgoing signature per expert, `dk`-vector each, so the 345
> ms does not come back).

> **`E10.23` — chaining OOM'd at 972 experts, and then chained nothing anyway**
> *"I recommended `SOCIETY=0` having already written the comment saying the chaining path is O(N) and
> 'a chained fabric of 10,000 experts is not a thing you want'. That was careless: it OOM'd at 972
> experts."* `Bo` was `(B,N,L,d)` — 12 GB for **one** hop, times the depth budget, times the autograd
> graph.
> With the OOM gone, **mean routed depth was 0.00 of 4**: HALT absorbs on the very first hop because
> `FAB_MIN_STEPS` defaulted to 0 — *"chaining switched ON and nothing chained… **A composition
> mechanism that is enabled but never entered is worse than one that is off, because it reads as
> tested.**"*
> **Found/Fix** `c4000c6` (top-k per hop; `FAB_MIN_STEPS` defaults **by path**: 0 under SOCIETY, 2
> under chaining).

> **`E10.24` — `Fabric._ids` cached graph-attached tensors, and never fired**
> A cache hit would have backwarded through a freed graph. *"It never fired only because the training
> loop calls `society()` without `step=`, so the cadence test always failed and the embed was
> recomputed every single step — **the O(N·2dr·hid) cost the cache exists to amortize was being paid
> in full at N=4096, 50x more often than intended.**"*
> **Found/Fix** `7b28570` (cached detached; two kinds of reuse split — *"same step must return the LIVE
> tensors… a later step must return DETACHED copies"*).

> **`E10.25` — `FAB_EMB_EVERY=50` was a gradient switch dressed as a cache cadence, live on one path
> only**
> The routing keys are `eemb(A,B)`, so *"the identity channel is the ONLY one that reaches every expert
> — routing computes k of N, but `eemb` reads all N sets of weights."* At 50 it throttled that channel
> to one step in 50 and routed on keys up to 50 steps stale, **and it silently did so on the default
> path only** (live on chaining, which passes `step=`; dead on society, which did not).
> **Found/Fix** `8a1e3a7` (default 1; both paths pass `step=`; the report says which regime ran).

> **`E10.26` — router parameters that received no gradient, repeatedly**
> `9b05bd3`: *"Routing received no gradient at all."* With `ROUTE_GROUNDED=1` (the default) the router
> ran off the centroid buffer, updated by EMA under `no_grad`, against a signature `sig_of` already
> detaches. Measured: **`keys`, `qproj`, `q_entry`, `nov`, `ctrl` and `halt_key` all reported "no
> grad"** — *"the documented learned transition matrix, absorbing HALT and recurrent routing query were
> inert in the configuration that runs."*
> `8a1e3a7`: `halt_b` was *"allocated, optimized, decayed, never gradiented"* on what had become the
> default path one commit earlier.
> **Fix** `9b05bd3` (a per-expert bilinear term revives them), `8a1e3a7` (HALT is one operator on both
> paths) **plus a standing countermeasure**: a ROUTER LEARNING report line naming which router
> parameters actually received gradient. *"This project has shipped a dead router parameter more than
> once… nothing else in the report can distinguish an allocated-but-untrained parameter from a working
> one."*

> **`E10.27` — the society computed every expert and used two**
> The caller formed its logits from `_O[:, j]` for the top `ENS_K=2` and assigned the dense blend to
> `h`, where nothing read it — *"so every expert beyond the k-th was computed, discarded and never
> gradiented. **That is why raising the expert count changed nothing.**"*
> **Found/Fix** `9b05bd3` (sparse top-k).

### 10d. Design errors that made a mechanism impossible

> **`E10.28` — only the argmax winner's centroid ever moved**
> `j = int(w.mean(0).argmax()); s.cent[j] = EMA(s.cent[j], gist)`. *"The winner therefore drifted
> toward every region it won and became closer still, while every other centroid stayed frozen at its
> initialisation. A newcomer cannot win because its region never moved, and its region never moves
> because it never wins. **Rich-get-richer with no path in — which is why 4096 experts produced ONE
> used node, and why that was never going to be fixed by breeding or by culling.**"*
> **Found/Fix** `580cd62` (shared centroid updates over the top-`FAB_CENT_TOPK`; novelty → discovery;
> exploration; rank-slice crossover). First run with all four: SPECIALIZATION 0.206 against a shuffled
> null of 0.054 ± 0.055 — **SPECIALIZED**, where *"every previous run in this project said
> INTERCHANGEABLE."*

> **`E10.29` — routing was at BATCH granularity, which is why three mechanisms changed nothing**
> `idx = w.mean(0).topk(kk).indices` — one expert set for all `BATCH_W` windows. *"All 16 windows in a
> batch were served by the same experts at the same weights, so an expert could never come to own a
> KIND of text — only a batch average that happened to contain it."*
> The pilot fired every mechanism and moved none: **3081 novelty handoffs, 436 off-policy routings,
> 1770 crossover births — and still 3 of 4096 experts used, still INTERCHANGEABLE, and bits/byte
> WORSE, 2.064 → 2.200. Paid 0.14 bits for nothing.** *"They could not have worked."*
> **Found/Fix** `e44b5b0` (per window, at no cost — the einsum already computed every b×k pair).
> **Honest state recorded**: it fixed a real defect and did **not** fix the concentration.

> **`E10.30` — every newborn was an exact identity, which is a trap with no exit**
> `B=0`. *"Identity birth was chosen so that adding a node could never disrupt what already works, and
> that reasoning is sound in isolation. But an identity computes NOTHING, so it has no competence, so
> it attracts no routing mass, so it never gets traffic, so it can never ACQUIRE competence… 4095 blank
> identities losing to one trained node is exactly what it predicts."*
> **Found/Fix** `e714531` (growth clones the fittest plus jitter). On a 256-node test used nodes went
> 1 → 4.

> **`E10.31` — `FAB_CLONE_JITTER=0.02` was an absolute number against an unknown scale**
> *"so a 'clone' was an exact copy in practice."*
> **Found/Fix** `8565246` (25% of the parent's own std, with 10% of births taking a 6x jump —
> *"without the tail a population converges on its founder however many members it has"*).
> Same commit: **parent selection was a global argmax**, so every birth went to the same incumbent and
> *"the population becomes one lineage wearing 4096 hats. Diversity of a POPULATION is not diversity of
> its ANCESTRY."* Fixed with a relevance shortlist + fitness-proportional sampling + a 20% parent quota
> (`245bc68`: 91 distinct parents, largest share 4%).

> **`E10.32` — the two populations designed as duals ran 15,625x apart**
> `MAX_DOMAINS` was then 64 with the comment *"hard cap, MIRRORING the expert bank's fixed slot
> pool"* — and every launcher then set `MAX_DOMAINS=1000000` while leaving `FAB_NMAX` at 64.
> *"Hundreds of domains routed through 64 experts means expert granularity was coarser than domain
> granularity by more than 100x, so 'experts competing within a domain' could not happen at all."*
> **Found/Fix** `cc04c21` (`MAX_DOMAINS` defaults to `FAB_NMAX`; launcher overrides removed).
> The 64 cap itself *"was three separate ceilings, none of them a decision"* — parameters, Python
> object iteration, and slot reallocation — plus a fourth found only by measuring: parameters scaled
> and **time did not** (345 ms at N=65536), because every expert had its own `sig_d × dk` query matrix.
> One shared query projection took it to 15 ms.

> **`E10.33` — a growth burst seeded several experts at one signature as exact clones**
> With identical regions, so they could never differentiate.
> **Found/Fix** `020c157` (`BIRTH_JITTER=0.15`).

> **`E10.34` — `route_t` was applied only on the society path**
> So the chaining path softmaxed raw logits at T=1.0. *"With N+1 near-equal logits HALT starts at
> ~1/(N+1) and, being an ABSORBING operator, accumulates every step — which is most of the measured
> 'halt 0.76, mean routed depth 0.24 of 4 steps'."*
> **Found/Fix** `b3ce153`.

> **`E10.35` — the learned key term was an unbounded dot added to a bounded cosine**
> `logits = cos(gist, centroid)/T` (bounded, ±10 at T=0.1) `+= q_route(gist) @ K.t()` (**unbounded**).
> *"So an expert whose key norm grows scores high for every input with any positive projection
> regardless of its region, and gradient descent grows one key because that lowers loss fastest early."*
> **Found** `b8f7837` — **and deliberately NOT shipped as a fix**: normalising both terms is the
> principled form and *"measured on a 100 kB toy it went the WRONG way, 3 used experts to 1. At that
> size the number is 1-vs-3 out of 32 windows, which is noise, and **this would have been the fourth
> unvalidated router change in a row**."* Ships as `FAB_KEY_NORM`, default 0.

### 10e. Banners that lied

> **`E10.36` — the banner lied at least three times, and was rebuilt structurally**
> *"'per-expert memory ON' for a whole 48k-step run where it was off from step 0"* (`MEM_PER_EXPERT`
> was `… and SOCIETY`); *"'grounded region + learned bilinear' on a path with no region term"*;
> *"`FAB_MIN_STEPS=2` while the code ran 0"*. *"Each was fixed by hand while the next one was already
> sitting there. Fixing them one at a time was never going to converge, because the failure is
> structural: the banner re-read `os.environ`, which is what was ASKED FOR, while the code ran an
> effective value that is often an AND with something else."*
> **Found** `a5c893a` / `a71820a8` / `78c3c1e` (one at a time). **Fix** `22a708d` — derived, not
> written: every read goes through `_env`; one declarative table maps env name → the **live object's**
> value (47 knobs); the divergence check is a **loop over that table, not a human remembering** — *"it
> reproduces all three historical lies as failures without being told about them."* `!!` is reserved
> for a divergence nobody registered, *"otherwise the loud marker stops meaning anything and gets
> skimmed, which is how the last three survived."*
> Other instances: `2a262a2` — *"it printed 'experts off' while the expert population was ON… Saying
> 'experts off' about a run with thousands of routed experts is worse than saying nothing."*;
> `8565246` — a line printed "competence protection" twice, from an edit that left the tail of the
> string it replaced.
> Same commit added run provenance: *"every log now opens with `[build] branch … commit … clean …`.
> Arms get compared across days and commits, and without this 'pilot 6 vs the grid' is a comparison
> between two things nobody can identify afterwards."*

> **`E10.37` — the `FAB_MIN_STEPS` override was applied where nobody reading the config would find it**
> Forcing it off inside `forward()` with a local conditional left `s.min_steps` reading 2 while the
> effective value was 0 — *"and the `[config]` banner, the CHAINING report section and the SAVED
> CHECKPOINT all print or store it. The checkpoint line was worse still: it wrote
> `_i("FAB_MIN_STEPS", 0)`, the env var with the wrong default, **so a resume could rebuild the fabric
> with a different depth policy than the run that saved it**."*
> **Found/Fix** `78c3c1e` — *"A value that is overridden has to be overridden where it LIVES."*

> **`E10.38` — the CHAIN ORDER line reported a 1-sample artifact as a finding**
> On the society path `forward()` runs only in the report probe.
> **Found/Fix** `ffd39b8` (suppressed on that path).

> **`E10.41` — the COUPLING banner described the retok-on-unchanged-vocabulary cost for weeks without
> anyone knowing the price**
> *"'each retok rebuilds an identical stream while still clearing the lookahead queue and blacking out
> fabric growth' — without anyone knowing the price."* The price is **2.189 b/B** (`frozen` 4.364 vs
> `frozen_nr` 2.175 on identical vocabularies; `frozen` fired 23 retoks and **22 of them added zero
> tokens**). *"It is not only the frozen arms. EVERY run enters this state once minting saturates
> `VMAX`."*
> **Found/Fix** `046fd81` (a retok is refused when nothing has been minted since the previous one).
> **Caveat** — the 2.189 figure is `E3.5`/`E8.5`: not a clean single-knob comparison.

### 10f. Crashes at the worst possible moment

> **`E10.39` — probation made the stream finer, and a report assumed a fixed window length**
> The domain-genuineness reservoir raised `ValueError` on a ragged stack **and killed the run after the
> metrics had printed.**
> **Found/Fix** `9f8412b` (the reservoir refuses a window that does not match what it holds; the report
> keeps the modal length and counts what it dropped rather than dying).

> **`E10.43` — a single-domain run crashed in the eval battery after training completed**
> `random.choice([z for z in procs if z != p])` — the wrongness-injection test builds a synthetic wrong
> pair from two different processes, undefined with a single source. *"It threw after training and the
> checkpoint had completed, taking the rest of the eval battery (generation, unlearn, verification)
> with it."*
> **Found/Fix** `3b7844d`.

> **`E10.44` — `TOKENIZER=1` with the default `DATA_MODE=synthetic` died on a bare `AttributeError`**
> inside `_retok`, because `TOK` is only constructed on the real-data branch. *"This bit a real launch
> — a command missing `DATA_MODE=real` ran for a while and then crashed somewhere unrelated to the
> mistake."*
> **Found/Fix** `b1fe6ed`.

### 10g. Errors in the very newest work (2026-08-15)

> **`E10.46` — the `LR_DECAY` envelope multiplies the floor as well as the peak — NOT FIXED**
> `LR_DECAY=1` lands near **0.25% of peak** rather than the intended 5%, and it **re-introduces the
> horizon dependence `LR_EPOCHS` exists to remove**, so runs at different `EPOCHS` stop being
> comparable.
> **Found** `9645050` — by a research agent reviewing the code written the same session.
> **Verified NOT FIXED at HEAD**: `self_organize.py:3695-3698` multiplies `_cyc` (which already
> contains the `LR_MIN_FRAC` floor) by `_env` (which itself only bottoms at `LR_MIN_FRAC`), giving
> `LR_MIN_FRAC²` = 0.0025; and `_env` is computed from **global** progress `_gp`.
> **Mitigation** — `LR_DECAY` was 0, so nothing measured was affected. **Open.**

**CORRECTION 2026-08-26.** No longer mitigated by being off: `LR_DECAY` now defaults to **1.0**. It was
flipped on when the same failure this entry describes recurred on the 0.75 GB run — three cosine restarts
returning a converged model to peak, costing +0.725 b/B that never came back. Turning it on was only safe
once the envelope was gated to multi-cycle schedules (`_n > 1`); ungated it also squeezed single-cycle runs,
which is why it had sat at 0 since it was written. Every result recorded before this date came from a
single-cycle schedule and is unaffected. See `LR_RESTART_DAMP`, added at the same time, which halves a
restart that failed to beat the best it inherited.

> **`E10.47` — the per-expert LR envelope decays to zero, pinning survivors at the floor**
> `gamma^(cyc-1)` goes to zero and use-age has no horizon: *"the smoke reached cycle 90 on six experts,
> i.e. **every survivor permanently pinned at the floor and unable to respond to a shift**. Age should
> lower the ceiling, not close it."*
> **Found/Fix** `9146136` (`FAB_LR_AMIN`), then `95aa336` raised it to 0.15, naming the degenerate case
> it guards: *"if `FAB_LR_CYCLE` is short relative to how often the router selects, every expert reaches
> a vanishing envelope early and the population trains at ~0 for most of the run."*

> **`E10.48` — two obvious implementations of per-expert learning rates do nothing**
> *"NOT via `param_groups`: `fab.A` and `fab.B` are single `(cap,d,r)` tensors — the whole population is
> two parameters, so a group cannot carry a per-expert rate. **NOT via gradient scaling either, and
> this is the trap**: Adam's update is `m_hat/(sqrt(v_hat)+eps)`, invariant to a constant factor on the
> gradient, so the obvious implementation does exactly nothing."*
> **Recorded** `91fd815`. The working form rescales the **update**: keep the pre-step weights, let the
> optimizer step at the global rate, move each row back along its own delta.

> **`E10.49` — `MEM_PER_EXPERT`'s call site was changed without its declaration**
> which would have been a `SystemExit` at the read.
> **Introduced** `e25d9b5`. **Caught** `daf9f89` — by the registry (`E1.9`'s countermeasure working).

---

## 11. Not fixed at HEAD

Cross-linked, not duplicated. `07_WIP.md` carries the full unfinished-work inventory; these are the
**defects** among them.

| ref | Defect | Why it is still open |
|---|---|---|
| `E2.10` | `EXPERTS` is mutually exclusive with `FABRIC` (an `elif` chain) | *"Arguably a bug"* (`51889b7`); `EXPERTS=0` by default so it costs nothing today |
| `E7.15` | Memory entry **VALUES** cannot be remapped across a re-segmentation; the stored **SPAN** shrinks | Fixing it means storing bytes, which changes the checkpoint format — *"and RESUME is how continual learning is meant to work here"* (`8bdeca4`) |
| `E7.41` | ACROSS THE RUN BOUNDARY is weights-only while its wording implies otherwise | Identified `f8599b7`; wording unchanged |
| `E10.2` | `main()` is ~2,940 lines with 658 locals; the split was attempted and reverted | The seam is 136 values wide and needs a rename pass first (`9c59a84`) |
| `E10.46` | `LR_DECAY` multiplies the floor; re-introduces horizon dependence | Found `9645050`; verified unfixed at HEAD; `LR_DECAY=0` by default |
| `E9.32` | No GPU noise baseline: `runs/equiv_noise_*` does not exist | Requires one `equiv.sh HEAD HEAD` on the GPU box; without it `c6f54e6`'s INERT verdicts are untrusted |
| `E9.30` | The container has rolled back at least three times | Infrastructure; mitigation is to push |
| `E2.6` | `SEG_MIN`/`SEG_MAX` still sized for byte `WIN` | `3f44ce3` added a guard and deliberately did not change the defaults |
| `E2.14` | `ENC_WARMUP` still above the measured 1-NN optimum | Recorded `d6acf20`, never revisited |
| `E8.29` | The world model's only full-stack reading says it has not learned dynamics — and it defaults ON | Never re-measured since `51889b7` (2026-07-29) |
| — | `retire_stale`, `fuzzy_segment`, `track_usage` — defined, costed, **never called** | The recurring *"no counter cannot be told from silently stopped"* pattern (`self_organize.py:5763-5764`) |
| `E6.7` | Growth and cull cadences are **not** matched (`FAB_NEW_WIN`=400 vs `MANAGE_EVERY`=50) | Stated deliberately in `6d5e6d7`: *"if a population trends DOWN, that asymmetry is the first place to look"* |

---

# THE INVALIDATION LIST

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are tiny
> — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has reached
> 1.227 b/B (`33a9299`), larger than the gap between any two architectures ever compared here.
> Several confidently-stated findings were later retracted when the measurement turned out to be
> broken. Every entry records **what was observed under these conditions**, never **what is true**.
> Where a result was later invalidated, the invalidation is stated next to it, not in a footnote.

**This is the list `03_EXPERIMENTS.md` and `04_RESULTS.md` must consult before quoting any number.**

**Status key** — **VOID**: the result does not stand and must not be quoted as evidence.
**UNATTRIBUTABLE**: the number was measured but cannot be assigned to the variable it was labelled
with. **UNCONTROLLED**: real observation, no control, so it supports no comparison.
**SUPERSEDED**: correct at the time, replaced by a better measurement. **DEGRADED**: still usable,
but with a stated caveat attached.

| # | Result / claim | Where stated | Why it does not stand | Killed by | Status |
|---|---|---|---|---|---|
| INV-01 | The A100 throughput bench: "the encoder is 85% of the loop", "lm fwd+bwd is a rounding error", the component ranking, the parameter counts | `0c00652`, `096094b` | `D_MODEL_B` was read by nothing, so both models ran at **d=128** (4.3M / 5.1M), ~84% vocab table, not the intended d=768 (28.7M / 53.9M) | `a5cd9ed` (`E1.1`) | **VOID** |
| INV-02 | Every conclusion about domains, coherence and bits/byte drawn before 2026-07-29 | all pre-`7a42f90` runs | `FABRIC=0` in every run: the routed expert population was absent from the system being measured | `7a42f90` (`E2.1`) | **VOID** — measured a different system |
| INV-03 | Every number before 2026-07-28 as evidence about **continual learning** | all pre-`a5ac033` runs | `PHASED=0`, never once executed. A stationary i.i.d. splice does not require continual learning; *"it is ordinary training with extra machinery"* | `c316813`, `a5ac033` (`E2.3`) | **VOID** for the CL claim; the bits/byte numbers stand on their own terms |
| INV-04 | Every fragmentation diagnosis attributing over-segmentation to the assign rule, the encoder, or the creation threshold | the whole 07-25 → 07-27 domain campaign | `MANAGE_MERGE=0.12` overrode the 0.28 fallback for the project's whole life: creation at 0.35, consolidation at 0.12 | `13e787a` (`E2.4`) | **VOID** — *"the whole of the fragmentation this project has spent weeks attributing"* elsewhere |
| INV-05 | Every domain-population figure before `510c695`, **including the 142-domain run** | `1e9c6b2`, `6397041`, and earlier | `MANAGE_EVERY=500` exceeded the run: merge, cull and fold executed **zero** times (60 kB = 468 steps) or **once** (120 kB = 937 steps) | `510c695` (`E2.5`) | **VOID** — consolidation was switched off |
| INV-06 | Every memory result in the project, and the "global store" framing | all runs | `MEM_PER_EXPERT` read `_i(...,1)` against a comment saying DEFAULT OFF: **every run used the partitioned store**, which measured **−0.555 b/B** against global at the scale tested | `e25d9b5` (`E2.7`), measured `242e021` | **DEGRADED → UNATTRIBUTABLE** for any memory contribution figure |
| INV-07 | The 4 MB `BATCH_W=16` GH200 run: purity / homogeneity / completeness / V-measure; both recurrence figures; the vocabulary trajectory | pre-`c8ba635` | Four cadences below the batch accumulator never fired: minting and retok **dead**, metrics computed from **6.2% of the stream**, recurrence figures disagreeing 6x | `c8ba635` (`E3.1`) | **VOID** |
| INV-08 | "Staged depth did not help" (`CHAIN_CURRIC`) | `7e9612d` | `maybe_deepen` sat behind a cadence that never coincided with a flush step — *"I reported it from a run in which it had not executed"* | `e0ce4f7` (`E3.2`) | **VOID — withdrawn, not upheld** |
| INV-09 | The three 18-epoch runs at `04cbe89` (`base_5`, `vmax8k_5`) and their held-out curves | `04cbe89` | The retok guard consumed its own `_due` event: **no mid-epoch re-segmentation at all**, and `_VALT` drifted — a 1.6 b/B disagreement between the curve and the memorization check | `d0728fe` (`E3.3`) | **VOID** |
| INV-10 | `frozen` 4.364 vs `frozen_nr` 2.175 = **2.189 b/B**, quoted in the source as *"the largest single effect on record"* and used to justify the retok guard | `046fd81` | `RETOK_EVERY=0` also silently disabled signature batching, so the arms differ in **two** ways | `79dac6c` (`E3.5`, `E8.5`) | **UNATTRIBUTABLE** — the effect is real, its size is not attributable to retok alone |
| INV-11 | Every coherence judgement and every generation sample before 2026-07-24 | pre-`535f5f6` | The independence test removed the busiest expert and never restored it: **every subsequent eval ran a mutilated model** | `535f5f6` (`E4.1`) | **VOID** |
| INV-12 | The 3.694 vs 2.100 pair, and its published interpretation *"a diagnostic's sampling frequency changed the model by 1.594 b/B through accumulation"* | `5f4f117` | The **difference is real**; the **attribution was wrong** — ~125 centroid nudges against ~240,650 from training is 0.05% and cannot accumulate to that. It demonstrates **chaotic sensitivity** | `bdce727` (`E4.3`) | **DEGRADED**: the number stands as evidence of chaotic sensitivity, not of accumulation |
| INV-13 | **Every arm comparison in the record before 2026-08-13** | everything | Diagnostics were editing the run. Eval-time exploration routed 15% of every scored window to a deliberately sub-optimal cold expert; eval-time `use` decided which experts died; the timing probe's `.backward()` fed 29 world-model parameters gradients from random tokens; `build_stream` draws from the global RNG, so **how much you measured decided what you trained on**. `HOLDOUT_N` 4→16 moved 48 report lines | `c76dc74` (`E4.4`) | **VOID** — *"No result in the record predates these fixes safely"* |
| INV-14 | *"COMPETENCE PROTECTION spared 0"*, reported as a puzzle for several rounds; and every fabric run before 08-03 as evidence about **selection** | pre-`2a262a2` | The fabric had **no culling at all** — `router.manage` is gated on `EXPERTS`, mutually exclusive with `FABRIC`. The protection was wired into a code path that never executes | `2a262a2` (`E6.1`) | **VOID** for any selection claim |
| INV-15 | **Arm B of the population 2×2** (`FAB_GROW=0 FAB_N0=2048`: 1.998 / 1.960 / 2.040, mean 1.999, spread 0.080) — *"B IS THE BEST ARM ON RECORD"* | `cc0a377` | Founders had no birthday and read as age 0 forever, so **arm B (all founders) ran with zero culls for its entire life**. Measured directly: `ac79e92` 0 culls / HEAD 6 culls on the same config and seed | `91fd815`, `a5cc7ea` (`E6.4`) | **DEGRADED + NOT REPRODUCIBLE AT HEAD** — the number stands as measured, but it measures a population under no selection, and the fix is now in. Re-run arm B or pin the reproducing config before comparing anything to it |
| INV-16 | *"Domain assembly works, purity 0.54 → 0.96"*, and the earlier failure called an undertraining artifact | pre-`5e02cfc` | Purity rises **monotonically with fragmentation**; the number went up because the partition was falling apart (purity 1.00 at 1431 clusters with completeness 0.18). The assembler was producing one domain per **splice segment** | `5e02cfc` (`E7.1`) | **VOID — explicitly retracted** |
| INV-17 | *"1 of 4096 experts used"* — and the four router fixes built on it | pre-`b610b89` | A **32-window eval probe** read as if it were the run. Whole-run: 84 distinct experts, top 3.9%, half the traffic to 21 | `b610b89` (`E7.9`) | **VOID** |
| INV-18 | *"Best at ~step 6000, identical in every arm at every seed"*; *"+1.220 b/B since its own minimum"* used to call the divergence real; *"model-alone quality degrades while memory masks it"*; *"the final model is 1.1–1.3 b/B worse than the one around step 6000"* | `53fbae5`, `3f67bfc` | `_VALT` cached the validation text in an obsolete segmentation and was never invalidated — **the yardstick was moving, not the model** | `18fdd6c`, and the standing claim retracted at `bdce727` (`E7.12`, `E7.26`) | **VOID** for the curve-derived claims. The **end-of-run** held-out figures re-tokenise first and are unaffected |
| INV-19 | The runs recorded as `rampfrom2048_s{0,1,2}` as a test of `GROW_CAP` / `LOSS_MASK_DEAD` | `c909918` | Six knobs were set on a build that predated all of them; every one was ignored. The runs measure a **ramp 2048→4096**, which is worth having, *"just not what was asked for"* | `c909918` (`E1.5`) | **RELABELLED** — valid as a ramp-from-2048 measurement, void as a `GROW_CAP` test |
| INV-20 | *"Memory now HELPS coherence (0.50→0.75)"*; *"the fabric buys coherence (0.75 vs 0.50)"* — **used to defend the `FABRIC` default**; *"memory HURTS coherence (0.75→0.50)"* | three separate turns, pre-`6f24bed` | Coherence was a **four-sample mean** with SE **0.25**; every value landed on 0.25/0.50/0.75/1.00. Each claim was one sample flipping | `6f24bed` (`E7.6`) | **VOID — all three, including the one that justified a default** |
| INV-21 | Every "% of generated words appearing in the training text" figure before 08-07, and every coherence probe reading `_gen_keep` | pre-`c14f876` | One domain → **one 200-token sample**; the composing check scored on **64–91 words**. *"91% (83/91) against 71% and 31% were being read as a real signal off a few dozen words"* | `c14f876` (`E7.25`) | **VOID** as a comparison; the `words_pct` column in `runs.csv` is post-fix and stands |
| INV-22 | *"Every domain result this project has produced"* before `98e3301` | all pre-`98e3301` domain runs | `SIG_WIN=0` meant WIN **bytes** against a loop striding WIN **tokens** — the signature encoder characterised **42% of the stream**, at whatever coverage that run's vocabulary happened to imply | `98e3301` (`E7.32`) | **DEGRADED → UNATTRIBUTABLE** — every window still produced *a* signature, computed from the opening fragment of what it claims to describe |
| INV-23 | *"Memory contributes +0.698"* and every per-entry memory retrieval figure | pre-`8bdeca4` | `mem.ctx` was queried in a segmentation it was not written in; **82.3% of stored contexts no longer matched** after ONE growth step, where a pilot does about sixteen. The rekey pass was faithfully re-encoding the wrong input | `8bdeca4` (`E7.15`) | **VOID** — *"it decided whether 'memory contributes +0.698' was measuring anything"* |
| INV-24 | Any reading of `EVICT=usage` / eviction policy as having selected anything | pre-`daf9f89` | `mem.read()` was called only from eval-only paths, so `use` stayed 0 and `last` was never written on the global store. **Every path evicted by write order whatever the knob said** | `daf9f89` (`E7.24`) | **VOID** — and it is the mechanism behind the vanished English domain in `a9d7258` |
| INV-25 | *"eng 1.998 → 2.050, +0.052 ± 0.075 HELD"* read as retention of the **system** | `a9d7258` | `holdout_bpb` calls `_eval_logits`, which does not consult memory — ACROSS THE RUN BOUNDARY is a **weights-only** number, though *"the ONLY number that spans the run boundary"* implies otherwise | `f8599b7` (`E7.41`) | **DEGRADED** — the number stands as a **weights-only** retention figure. Consistent with every English memory entry having been evicted |
| INV-26 | *"Unlearning is surgical and local"* — every instance | pre-`9909349` | Measured on **ACTIVE** material only. Under the non-stationary stream a bounded store had already evicted the faded material, so the faded arm of the test skipped itself: *"deleting what the bounded store has already evicted is a no-op"* | `c316813`, `9909349` (`E7.22b`) | **VOID** as a claim about faded material |
| INV-27 | *"The weight-prediction term is 2% of the routing decision"* — and `ROUTE_REGION_W`, which was built on it | `e0ce4f7`, `fcdfaa7` | Measured on a **64-expert toy**. At 4096 it is **7% region / 93% weight-prediction**; `FAB_KEY_NORM=1` **reduces** it (41/59) rather than rescuing it | `ffd39b8` (`E8.1`) | **VOID — direction of the finding was wrong** |
| INV-28 | *"The divergence is the tokenizer"* — presented as a finding | `53fbae5` | Untestable at the time: the one minting-off arm (`frozvocab`) was a different run from the start and went NaN from step 20000. The real common cause is that **there was no LR schedule** — 2e-3 constant for 48,000 steps, across all 17 pilots on every architecture | `1593c70` (`E8.2`) | **VOID as stated**; the tokenizer contribution is separately real (`3f67bfc`) but was never the whole account |
| INV-29 | *"Freezing the vocabulary removes the divergence entirely — the model never stops improving"* (held-out 2.189, best IS final) | `8c8d20b` | *"'Frozen tokenizer' and 'schedule that anneals' were the same experiment"*: `_total_steps` was measured once at the seed vocabulary, so **only the frozen-vocabulary run has ever annealed** (0% over-projection, p=1.000, ended at the 5% floor; every minting run ended at 18–21% of peak) | `5f4f117` (`E8.3`) | **UNATTRIBUTABLE** — *"the tokenizer conclusion I drew from those four runs was not supported"*. The run also used ~44% more optimizer steps for the same bytes |
| INV-30 | *"8 epochs beat 18"*; *"E18 is dragged"* | pre-`9fabba4` | `EPOCHS` set the cosine horizon as well as the run length: **11.0× different LR at step 44000**. *"'8 epochs beat 18' and 'a low LR beat a high one' were the same observation"* | `9fabba4` (`E8.4`) | **VOID** |
| INV-31 | The whole VMAX field — the `VMAX × EPOCHS` 2×2 (`0279709`), the six-run 18-epoch table (`9ca8057`), and *"the non-monotonic VMAX ordering"*; incl. *"doubling a FULL vocabulary costs +1.133 b/B"* | `0279709`, `9ca8057` | `FROZEN = torch.randn(VMAX, D)` at module scope drew from the global generator **before anything else was built**, so changing `VMAX` re-rolled every module — verified on the encoder and the fabric centroids, neither of which is VMAX-shaped. *"Three runs 'differing only in VMAX' were three different random initialisations of the whole system"* | `0f96784`, completed `79dac6c` (`E8.6`) | **UNATTRIBUTABLE** |
| INV-32 | `ep18_big_s{0,1,2}` held-out (2.243 / 2.200 / 2.564) compared to the 8-epoch arms | `ac79e92`, `runs.csv` | The corpus was **re-fetched larger and got harder** (order-1 3.440 → 3.747). Against each run's own order-1 anchor: 1.411 vs 1.441 — *"18 epochs bought nothing, and did not cost the 0.34 the raw numbers suggest either"* | `ac79e92` (`E8.12`) | **DEGRADED** — quote only against its own run's order-1 |
| INV-33 | *"`MODEL=transformer` has never been run here"*; and the GRU-vs-transformer comparison (GRU 2.064/2.200 vs TRF 2.130/2.184, coherence 0.17 vs 0.02) | `longrun.sh`, `245bc68` | It **has** run twice — both under `FAB_GROW=1` to 4096 experts, before the instrument fixes, both with the broken-base signature (model ALONE 4.680 / 4.952, fabric compensating +2.625 / +2.801) — *"that is arm D seed0 exactly"*. The coherence half is `INV-20` | `bf53d40` (`E8.13`) | **VOID** — the architecture has never been evaluated where the base model survives |
| INV-34 | The dead-row series *"0% → ~2.2, 41% → 3.561, 75% → 6.114"*, quoted repeatedly as monotone and catastrophic | `2c705c7`, `b6952da`, `1a113f5` | The arms differed in far more than their dead fraction and were measured through the editing instrument; `vmax8k@18ep` filled its vocabulary **completely** and is the **worst** of four runs (4.383). The first **controlled** test gives **+0.060 against a combined SE of 0.055 = 1.1σ** | `0279709`, `e9f2e58` (`E8.14`) | **UNCONTROLLED → NOT ESTABLISHED**. *"I have been repeating it as though it were"* |
| INV-35 | **Every single-run architecture comparison in this branch**, including *"vmax4k is the best regime"*, *"restarts are net-negative"*, *"2048 misbehaves at 18 epochs"*, *"SPECIALIZATION 0.132, the highest recorded, and emergent"*, *"the only arm whose curve is flat, −0.007"* | throughout | Seed spread: paired pilots 0.060 / 0.174 (`6bd226c`); **four runs of one nominally identical arm spread 1.227 b/B** with word quality 43%–89% (`33a9299`). The arm's own four runs span more than the gap to every other arm | `6bd226c`, `33a9299` (`E8.15`) | **VOID** — the widest invalidation in this file. *"No architectural conclusion in this branch survives that unless replicated"* |
| INV-36 | *"FABRIC alone is worth +0.709 bits/byte"* — **used to justify defaulting `FABRIC` ON** | `7a42f90`, `rerun.sh` header | An **eval-time knockout** of a component the model trained with, not a **retrained** ablation. Retrained: **3.089 vs 3.090**, no bits/byte at all. The fallback justification offered (coherence 0.75 vs 0.50) is `INV-20` | `e60b8e0`, retracted `9d90416` (`E8.16`) | **VOID** |
| INV-37 | The ranking of domain configs A/B/C/D by V-measure (A best at 0.42), and `MANAGE_MERGE=0.45` chosen to maximise it | `6397041`, `13e787a` | V against the four **seeded** corpora is the wrong target — the corpora are a scaffold, and V *"actively PENALISES the intended behaviour"*. Purity rises with fragmentation, completeness falls with it, and neither sees recurrence | `efb818a`, `8914dd1` (`E8.17`, `E8.18`) | **VOID as a ranking** — *"the four configurations measured so far need re-ranking on recurrence"* |
| INV-38 | *"Verification (reconstruction) works: AUC 0.980, precision@1% 100%"* as a claim about the **product loop** | `213820d`, `c88fb7a` | The standalone stands; **the integration failed at 0.3% precision**, and the 100%@1% was *"an FPR≈0 projection that doesn't hold on the real heterogeneous store"*. `VERIFY_SWEEP` deleted ~21k of 292k entries, mostly genuine. 5x steps ruled out undertraining | `9df85b8`, `d7c141b`, `f5303d6` (`E8.22`) | **VOID for store-wide use**; stands as a per-candidate discriminator (~98%) |
| INV-39 | The world model as a working subsystem | `51889b7` | Its only full-stack reading is *"beats baseline **−84.7%**, latent std 0.07"* — by its own printed criterion it **has not learned dynamics**. Against a param-matched monolith it is **−5.1%**. Never measured since 2026-07-29, **and it defaults ON** | `51889b7`, `74d10d8` (`E8.29`) | **OPEN / UNMEASURED** — every post-07-29 run carries an untested world model in the loop |
| INV-40 | *"The router HALTs 90%, mean routed depth 0.10 of 4"*; and *"`PONDER_WARM=8000` never completes, so the fabric's schedule has never finished"* — which justified the pilot | quoted for several rounds pre-`33355b2` | The first came from a **report-time probe** of a path the run did not use. The second is about code that is **identically zero** on the society path. *"Second time this session a justification of mine was about inert code"* | `33355b2` (`E8.31`) | **VOID** |
| INV-41 | Any pre-`5f4f117` log whose filename names a knob in `{VMAX, WIN, BATCH_W, RATE_EVERY, CKPT_EVERY, GROW_*, SEG_*, DATA_DIR, LAYERS, MODEL}` | `grid`/`seeds`/`repeat` | Arm flags came **before** the hardcoded env, and `env A=1 A=2` keeps the last: the flag was discarded and the log named after a value that never took effect. *"`grid 3 VMAX=512` ran at 2048 and named the log 512"* | `5f4f117` (`E9.2`) | **VOID** — the log's name does not describe the run |
| INV-42 | `frozen` 6.114 as a measurement of a frozen tokenizer; `frozen_nr` 2.365; `frozen1k`; `freeze6k`; `vmax8k@8ep` 3.561 | pre-`b6952da` | Six arms were configured to guarantee dead rows (75% / 75% / 50% / ~45% / 41%). *"The arm has never measured what its name says"* | `b6952da`, completed `25c37eb` (`E9.5`) | **VOID as named**; the clean re-runs (`frozen_8ep_clean` 4.364, `frozen_nr_8ep_clean` 2.175) replace them, subject to `INV-10` |
| INV-43 | The one continual-learning run `a9d7258` — its log | `a9d7258` | `pilot-add` never created `$OUT`, so `tee` wrote to a closed pipe. **Hours of GPU, a valid checkpoint, no record.** The numbers in `runs.csv` come from a **terminal copy** | `40de03d` (`E9.10`) | **PROVENANCE DEGRADED** — n=1, no log, numbers hand-transcribed. `holdout.py` can reconstruct ACROSS THE RUN BOUNDARY from the checkpoint if it survives |
| INV-44 | The `DIV_W=0.05` pilot | pre-`b14d60e` | Byte-identical to the `DIV_W=0` run in **every figure** — the soc-loop branch returns before the distinctness term. *"Twenty minutes of GPU time measured the previous configuration."* The config audit **certified it as correct** | `b14d60e` (`E10.21`) | **VOID** — it is a duplicate of the `DIV_W=0` run |

## What survives

Short, and it should be. From `33a9299`'s own accounting — *"what is exact or far outside 1.6 b/B"* —
plus what later work added:

1. **Determinism given (config, commit, seed) on CPU.** Three identical-config pilots byte-identical
   (`6bd226c`); `base` and `nogate` byte-identical (`b6952da`); six one-knob runs verified at
   `c76dc74`. On GPU, training is bit-reproducible and the nondeterminism is confined to **memory
   retrieval** (`c6f54e6`) — though see `E9.32`, the noise baseline was never established.
2. **The LR schedule effect.** cosine 2.101 vs none 4.193, with the constant-LR arm oscillating
   3.4–7.8 for the whole run and ending at 5.16 (`c33f078`). *"The one architecture-independent
   effect far outside seed spread."*
3. **The retok-on-unchanged-vocabulary cost is real** (`046fd81`) — even though its magnitude is
   `INV-10`.
4. **Arm B's spread of 0.080 across three seeds** (`cc0a377`) — *"the first configuration stable
   enough for a 0.1 b/B difference between two arms to mean anything"* — subject to `INV-15`, which
   explains **why** it is stable.
5. **The code defects themselves.** They are facts about the source, independently checkable, and
   they are most of this file.

---

## Recurring patterns

Nine classes recurred *after* a countermeasure for that exact class was already in place.

| Pattern | First | Recurrences | Why the countermeasure missed it |
|---|---|---|---|
| A knob is set and read by nothing | `a5cd9ed` | `6397041`, `904742c`, `c909918` | `preflight.sh`'s trap greps a **fixed list of launch commands**; `c909918`'s audit was an **allowlist of prefixes**, and a brand-new family is when the mistake is most likely |
| A cadence never coincides with a flush step | `c8ba635` | `e0ce4f7` (×4 sites), `d0728fe`, `0f96784`, `79dac6c`, `5a72970`, `91fd815` | Each instance is a different *mechanism* (`%` vs accumulator; `_due` consumed; `_due` early-return; `step//N`); only the symptom is shared |
| A diagnostic writes training state | `535f5f6` | `5f4f117`, five leaks at `c76dc74`, `e0dbf0c` | Nothing enumerated the eval-vs-training boundary until `frozen_rng`/`@no_rng_drift` existed; `e0dbf0c` sat *before* the training loop and so was outside the sweep |
| A value is read but its code path is unreachable | `3e67b5d` (`DIV_W`) | `b14d60e` (`DIV_W` again, other path), `fec2285` (`TOK_ANCHOR`) | *"A value can be wrong (banner), unread (typo), or read-but-unreachable. Each needed its own check because each is invisible to the others"* (`b14d60e`) |
| A report section vanishes silently | `763e9f2` | `01c1cd3`, `9909349`, `30e635d`, `f75d574` | `except Exception: pass` and bare `if …:` guards with no `else`; the standing rule (*say why you cannot run*) postdates all of them |
| A maintenance path has no counter, so "never ran" and "stopped working" look identical | `retire_stale` | `fuzzy_segment`, `track_usage`, the domain-prior section, `FAB_RESCUE` (`e2db890`), `remap_mem_ctx` (`8bdeca4`), the memory probe (`daf9f89`) | Named explicitly at `self_organize.py:5763-5764` and now designed against — every new maintenance path ships with a count |
| A comment records a measurement, and the measurement goes stale | `bdce727` | `6dda2c4`, `8a8fb69` | `bdce727` replaced stale claims with **fresh claims**; `6dda2c4` concluded a week later that this was the wrong repair — *"a comment that records a measurement is wrong the moment the code changes, and this file has now misled me twice that way"* — and **removed** the empirical assertions instead. `8103a8a` moved results into `runs.csv` |
| A fix is shipped that is itself broken | `98e3301`→`2a682d7` | `7de4daf`→`13099a1`→`6732448`→`9c59a84`; `c214c21`→`93c1733`; `fec2285`→`1a113f5`; `046fd81`→`d0728fe`; `0f96784`→`79dac6c`; `f4b2e9b` (deadlock); `e25d9b5`→`daf9f89`; `c341921`→`fec2285` | The gate covers only what it exercises (`E9.18`); `py_compile` accepts infinite recursion and a broken import (`E10.2`, `E10.3`) |
| A comparison is made at a scale the answer does not hold at | `e0ce4f7` (64-expert toy) | `b610b89` (32 windows), `6f24bed` (4 samples), `c14f876` (1 sample), `2a682d7` (12 kB gate), `e8df6fe`/`ed04aac`/`1e62eff` (400-step toys) | *"It was wrong because I measured it at a scale the user had already told me was unrepresentative"* (`ffd39b8`) |

Two meta-observations the record makes about itself:

- **`b14d60e`** — *"That is the third distinct layer of the same failure: a value can be wrong
  (banner), unread (typo), or read-but-unreachable (this)."*
- **`c76dc74`** — the researcher's instinct *"Why are we trying to measure the noise? Let's fix the
  issue that's coming up, or first find it"* was **right**, and the planned noise-floor measurement
  would have been wasted. Record this prominently: the most valuable finding in the project came from
  refusing to characterise noise before looking for its cause.

---

## The countermeasures, and what each one catches

Built in response to the classes above. Listed with what each **cannot** catch, because that is where
the next one came from.

| Countermeasure | Commit | Catches | Does not catch |
|---|---|---|---|
| `preflight.sh` knob trap | `ff8754a4`, widened `4869559` | A launch command setting a knob read by nothing (56/56 at the time) | Knobs not in the greped command; new families |
| Sweep unread-knob guard | `6397041` | A sweep stage that would produce duplicate rows reading as a null | Only that sweep |
| The `_SPEC` registry (274 → 279 knobs) | `6f4c534` | Two reads with different defaults; a knob with no declaration; a call site changed without its declaration (`daf9f89`) | Whether the code path runs |
| `levers.py`, AST-derived | `f279fd0` | A derived knob that is undeclared, or declared and not derived; a refused override | Runtime reachability |
| Banner derived from live objects (47-knob table) | `22a708d` | A banner that describes what was **asked for** rather than what **ran** — reproduces all three historical lies without being told about them | A knob whose effective value is correct but whose code path is dead |
| `NOTHING READ THESE` / `not verified` audit | `99ba0f4` | A typo that trained for twenty minutes on the default | Read-but-unreachable |
| `!! knob was ON and its loss term NEVER FIRED` | `b14d60e`, extended `fec2285` | Read-but-unreachable, for anything reaching the loss through `_term` | Terms that do not go through `_term` |
| Family-derived config audit | `c909918` | A knob from a **different commit**; a brand-new family | Values that are wrong but read |
| `frozen_rng()` / `@no_rng_drift` | `c76dc74` | A probe drawing from the global RNG — *"including the ones added later by someone who does not know this rule exists"* | A probe that writes non-RNG training state directly |
| Per-module seeds | `79dac6c` | One module's init depending on how much RNG another consumed | — |
| `equiv.sh` | `2d93a3e`, `7ff2af0`, `37ecb20`, `c6f54e6` | A refactor that is not inert; a side that never reached the report (caught the broken import in **four minutes**) | Anything without a noise baseline on that machine (`E9.32`) |
| `longrun.sh smoke` | `05475cb`, fixed `136461c` | An arm that does not reach its report | Anything the 40 kB / 3-epoch scale does not exercise (`E9.18`) |
| The read-back gate arm | `4554d6b1` | A checkpoint that cannot be loaded — *"had this existed the breakage would have surfaced the hour it was introduced"* | — |
| `.cfg` beside every log | `42d8686` | A skip that reuses a result from a different configuration | — |
| `runs.py` + `runs.csv` + `stale` | `8103a8a`, fixed `ed8af6b` | A result quoted under defaults that have since moved; every column parsed from a log, never typed | A parser that silently stops accepting logs (it did, `E9.13`) |
| `[vocab]` never-minted vs minted-then-unused | `ce8d4ea`, split `2c705c7` | A run whose softmax width is mostly rows that index nothing — **caught `E7.49` in one line, in the first pilot** | — |
| Error bar on the headline line, SE as a column | `c76dc74`, `ed8af6b` | Two rows quoted as differing when they do not | — |
| Nulls on every verdict (shuffled / permuted / matched-size) | `8914dd1`, `3e2393d`, `9d90416` | *"Without the control this would have been reported as 'English sub-domains carry information', and it would have been wrong"* | A null with no spread (it had none, `E7.8`) |
| AST assertion that a helper does not appear in its own body | `343bfd7` | Infinite recursion the compiler accepts | — |
| `holdout.py` | `40de03d` | A lost log, if the checkpoint survives | A lost checkpoint |
| `[build] branch … commit … clean` on every log | `22a708d`, DIRTY fixed `4da76b8` | A number that cannot be traced to code | — |
| `mem_evict_test.py` | `daf9f89` | An eviction rule with no signal, with `EVICT=recency` as the control that cannot tell them apart | — |

---

## How these were found

The tally, because it is the field that generalises. Counted over the ~180 entries above.

| How | Share | Notes |
|---|---|---|
| **By reading the code** (audit, adversarial audit, "what does this actually do") | ~40% | The largest source by a wide margin, and the cheapest. `7a42f90`, `51889b7`, `c316813`, `2a262a2`, `13e787a`, `dd7ceb0`, `d05d919`, `904742c`, `42d8686`, `2ba3ac1`, `e25d9b5` |
| **By a gate, guard or registry firing** | ~15% | `18d4f8f`, `25c37eb`, `1a113f5`, `f279fd0`, `daf9f89`, `13099a1` (equiv), `4554d6b1`, `2d93a3e` |
| **By a run failing or producing an impossible number** | ~15% | `c8ba635` (vocab 512/16384), `d0728fe` (zero retok lines), `91fd815` (every expert clamped), `1a113f5` (609 never minted), `b6952da` (6.114 with 4% words), `9c6661a` |
| **By running the thing twice** | ~8% | `3e2393d` (two seeds, opposite verdicts), `6bd226c`, `33a9299`, `5f4f117` (3.694 vs 2.100), `c6f54e6` |
| **By writing a test for the new mechanism** | ~8% | `f4b2e9b` (deadlock), `e2db890` (two bugs, both mine), `9f8412b`, `343bfd7` |
| **By measuring at the real scale after a toy** | ~7% | `ffd39b8` (2% → 93%), `b610b89`, `6f24bed`, `c14f876` |
| **By an outside reader / literature agent** | ~4% | `f8599b7` (retired ids; the weights-only holdout), `9645050` (`LR_DECAY` floor) |
| **By the researcher pushing back** | ~3% | `c76dc74` (*"why measure the noise"* — the single most consequential), `1593c70` (doubting the tokenizer explanation), `ed04aac`, `c92d104`, `7b18214`, `580cd62` |

Three things follow, and they are the operational content of this file:

1. **Reading beat running, by a wide margin.** The most expensive defects — `FABRIC=0`, `PHASED=0`,
   `MANAGE_MERGE=0.12`, `MEM_PER_EXPERT=1`, no culling at all — were all found by reading the
   defaults against the comments, and none of them ever produced a crash or an implausible number.
2. **Running the same thing twice found what one run could not**, every time it was tried, and it was
   tried rarely. `3e2393d` and `33a9299` are the two cheapest and most destructive measurements in
   the project.
3. **A mechanism with no counter is indistinguishable from one that stopped.** This is the single
   most transferable rule the record produces, and it is now applied by construction to every new
   maintenance path.
