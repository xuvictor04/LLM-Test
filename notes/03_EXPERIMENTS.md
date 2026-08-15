# 03 — EXPERIMENTS

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are tiny
> — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has reached
> 1.227 b/B (`33a9299`), larger than the gap between any two architectures ever compared here.
> Several confidently-stated findings were later retracted when the measurement turned out to be
> broken. Every entry records **what was observed under these conditions**, never **what is true**.
> Where a result was later invalidated, the invalidation is stated next to it, not in a footnote.

---

## What this file is

Section **B**: what was TESTED, WHY, and what the OUTCOME was. One entry per experiment.

The column that matters most is the gap between **CONCLUDED AT THE TIME** and **STANDS NOW**. This
project retracted a great deal, and it retracted it in public, in the commit messages. An entry
whose two conclusions agree is rarer here than one whose two conclusions disagree.

Two categories, kept strictly apart, because conflating them is where most over-claiming happened:

- **Part I — GENUINE EXPERIMENTS.** An arm comparison (or a paired A/B) *intended in advance* to
  answer a stated question. 56 of them.
- **Part II — INCIDENTAL OBSERVATIONS.** A number that fell out of a run done for another reason,
  and was then quoted as though it were an experiment. 16 of them. **Nearly every one is on the
  invalidation list.**

### Authority and precedence

- [`notes/01_TIMELINE.md`](01_TIMELINE.md) — the commit spine and the 15 ancestry-verified **EPOCH
  BOUNDARIES** (`E1`..`E15`). Epochs are cited from there, never re-derived here.
- [`notes/05_ERRORS.md`](05_ERRORS.md) — the **INVALIDATION LIST** (`INV-01`..`INV-44`). It is
  authoritative. Where it voids a result, the `INV` id appears **inline next to the number**, and
  the result is not restated as if it stood.
- [`notes/08_GLOSSARY.md`](08_GLOSSARY.md) — vocabulary, including the 16 terms that changed
  meaning. Current senses are used throughout; where a commit message uses an older sense, it is
  flagged in the entry.

### How to read an entry

    ARM / NAME        the name in longrun.sh `_flags_for`, or the commit's own
    CONFIG            flags verbatim, plus the harness defaults they inherit
    QUESTION          what it was meant to answer
    n                 said out loud, always
    RESULT            numbers as printed
    CONCLUDED         what was concluded AT THE TIME
    STANDS NOW        stands | superseded | INVALIDATED (with the INV id) | degraded
    ERA               instrument era (below)

### Instrument-era key

Per `01_TIMELINE.md`, the two named fixes are in ancestry order
`5f4f117` (08-07) → `c76dc74` (08-13) → HEAD, so nothing is post-`c76dc74` but pre-`5f4f117`.

| tag | meaning |
|---|---|
| **pre-both** | predates `5f4f117` and `c76dc74`. Eval passes were training the router (`E8`) *and* diagnostics were editing the run (`E11`). |
| **mid** | post-`5f4f117`, pre-`c76dc74`. Router no longer trained by eval; diagnostics still editing the run. |
| **post-both** | post-`c76dc74`. Still pre-`E14` (founders immune to culling) and pre-`E15` (`MEM_PER_EXPERT` actually on, eviction ranking a constant) unless stated. |

**`INV-13` applies globally to every `pre-both` and `mid` entry**: *"No result in the record predates
these fixes safely: every arm comparison was measured through an instrument that was changing the
thing it measured."* Each entry additionally names whatever is specific to it. And **`INV-35`**
applies to every single-run architecture comparison in the branch, whatever its era.

---
---

# PART I — GENUINE EXPERIMENTS

## §1. Verification / reconstruction

The project's original "B" subsystem (detect wrong information). Per `08_GLOSSARY` §1.1, **`B` was
renamed `Verification` on 2026-07-21** (`61eb8f3`, `3500b78`) and reframed by `4315c94` — *surprise
is a learning driver, not a truth signal*. Code identifiers (`is_wrong`, `WRONG_*`) were deliberately
left at the old name, so `WRONG_*` in source is B, not Verification.

### X01 — Reconstruction vs self-consistency, standalone (CPU)
- **ARM / NAME** `verify_console_test.py`, self-contained console A/B
- **CONFIG** small GRU trained on the real corpora; surprise-gated genuine negatives; base-rate-honest metrics
- **QUESTION** Does verification-by-RECONSTRUCTION beat B's self-consistency at flagging injected corruption, in the regime B actually fails in?
- **n** n=1 (one CPU run; the first version was discarded as methodologically wrong before it produced a quoted number)
- **RESULT** reconstruction AUC **0.978** vs B **0.903**; precision@1% base rate **100%** vs **30.5%** (`213820d`)
- **CONCLUDED** *"the reframe holds"* — reconstruction is decoupled from surprise and does not false-positive on surprise-gated genuine entries
- **STANDS NOW** **Stands as a standalone / per-candidate result only.** `INV-38` voids it as a claim about the product loop. The 100%@1% is explicitly *"an FPR≈0 projection that doesn't hold on the real heterogeneous store"*. Worth recording that building the test **caught its own methodology error**: the first version used 50% cross-domain corruption, the easy regime B already handles at ~97%.
- **ERA** pre-both

### X02 — The same A/B on GPU
- **ARM / NAME** GPU confirmation of X01
- **CONFIG** as X01, on GPU
- **QUESTION** Does the CPU standalone result reproduce on real hardware?
- **n** n=1
- **RESULT** AUC **0.980** vs **0.907** (`c88fb7a`)
- **CONCLUDED** confirmed
- **STANDS NOW** Stands, with `INV-38` — the standalone stands, the integration did not.
- **ERA** pre-both

### X03 — Verification in the product loop
- **ARM / NAME** full product-loop GPU test, `VERIFY=recon`
- **CONFIG** Reconstructor trained JOINTLY in the loop (`RECON_W>0`), `VERIFY_SWEEP` on
- **QUESTION** Does the standalone result survive integration into the running system?
- **n** n=1
- **RESULT** **0.3% precision** — *worse than B's 1%* — and `VERIFY_SWEEP` deleted **~21k of 292k** store entries, *"mostly genuine"* (`9df85b8`)
- **CONCLUDED** Root cause identified as a moving target: the online tokenizer re-tokenizes the stream (256→6176) and keys are re-keyed, so the genuine-association manifold moves under the Reconstructor. Fix: fit post-hoc on the settled store (`VERIFY_FIT=3000`), joint training off (`RECON_W=0`).
- **STANDS NOW** **Stands** — this is a negative result that was reported against the author's own prior claim. `INV-38`.
- **ERA** pre-both

### X04 — Post-hoc fit, and the 5x-steps control
- **ARM / NAME** re-test after the `9df85b8` fix; then the undertraining control
- **CONFIG** post-hoc `VERIFY_FIT=3000`; then `STREAM_LEN=30M` (~5x steps, ~22 min)
- **QUESTION** (a) Does fitting post-hoc recover the standalone's winning condition? (b) Is the failure just undertraining?
- **n** (a) n=1 → **0.5%**, essentially unchanged (`d7c141b`). (b) **n=3** → **0.3 / 0.5 / 0.3** at 5x steps (`f5303d6`)
- **RESULT** Precision does not move. At ~0.26% injection, a ~5% false-positive rate on a noisy underfit store sinks precision regardless.
- **CONCLUDED** *"Reconstruction does NOT beat the base-rate wall for store-wide wrong-detection."* Locked as a dead end for store-wide use; reframed as a strong per-candidate/pairwise discriminator (~98%) whose home is the reconcile→understand gate. `VERIFY_SWEEP` stays off. *"Owned the earlier overclaim off the standalone."*
- **STANDS NOW** **Stands.** This is the cleanest retraction in the project: n=3, a stated alternative hypothesis (undertraining), and a control that ruled it out. Per `08_GLOSSARY` §1.1, note the irony at HEAD: `VERIFY=selfcon` is the default, i.e. **the old B mechanism is what actually runs**.
- **ERA** pre-both

---

## §2. World model

### X05 — DynamicsPopulation vs a param-matched monolith
- **ARM / NAME** `WORLD_MODEL=1 WORLD_GROW=1` vs param-matched monolith
- **CONFIG** routed society of forward-dynamics predictors (route by fitness, blend, grow-on-plateau, soft-cull), on a toy multi-regime probe
- **QUESTION** Does splitting the world model into a routed population improve accuracy over one model of the same size?
- **n** n=1
- **RESULT** In-loop: grows 1→3, soft-culls, held-out beats persistence **+53.4%**, no collapse. Against the param-matched monolith: **−5.1% (worse)**, routing purity **0.32** (`74d10d8`)
- **CONCLUDED** *"Honest limitation recorded... separation does not improve accuracy or specialize on these tests. Structural value real; accuracy benefit unproven."*
- **STANDS NOW** **Stands** — reported as a negative at the time and never overturned. Hypothesis offered but never tested: route by domain context, not `z` alone.
- **ERA** pre-both

### X06 — The anti-collapse term at full strength
- **ARM / NAME** `WORLD_VAR` (default 1.0)
- **CONFIG** the integration had been scaling the VICReg-style variance/decorrelation term by `WORLD_W=0.1`, i.e. running it at 1/10 strength
- **QUESTION** Was the observed latent collapse (std 0.24) caused by our own scaling of the anti-collapse term?
- **n** n=1, CPU
- **RESULT** latent std **0.24 → 0.97**; forward-pred vs persistence **+13.6% → +34.1%** (`a1767b7`)
- **CONCLUDED** Yes; fixed.
- **STANDS NOW** **Stands as a CPU smoke result.** It does not carry to the full stack — see X07, where the same subsystem reads latent std **0.07**.
- **ERA** pre-both

### X07 — First full-stack reading of the world model
- **ARM / NAME** the all-subsystems-on verification run
- **CONFIG** 4 corpora, `BATCH_W=16`, 100 kB, every subsystem on for the first time (`51889b7`)
- **QUESTION** What does the world model actually do when the whole system runs?
- **n** n=1
- **RESULT** *"beats baseline **−84.7%** | latent std **0.07**"* — by its own printed criterion (std ≈ 0 = collapsed) it **has not learned dynamics**
- **CONCLUDED** Stated plainly in the commit as a first reading, not a regression: *"It has never been run, so this is its first reading."*
- **STANDS NOW** **`INV-39` — OPEN / UNMEASURED.** It has **not been measured since 2026-07-29**, and it **defaults ON**, so every post-07-29 run in this file carries an untested world model inside the loop. Note also `E2` (`c8ba635`): this run was at `BATCH_W=16`, where four cadences below the batch accumulator never fired — see `INV-07`.
- **ERA** pre-both

---

## §3. Performance and equivalence A/Bs (`457c9d0`..`ffb6bf8`, 2026-07-24)

The one block in this project where the experiments are **exact** rather than statistical: each asks
"is this optimisation equivalent?", and the answer is a bit-comparison, not a mean. These are the
highest-confidence results in the record — and they are about plumbing, not about learning.

### X08 — KEY_PREGATE
- **ARM / NAME** `KEY_PREGATE=0` vs `=1`
- **CONFIG** seeded A/B; memory keys encoded *after* the surprise gate rather than for every position (~88% were being discarded)
- **QUESTION** Is encoding keys behind the gate exactly equivalent?
- **n** n=1 seeded pair (deterministic, so n=1 is sufficient for an equivalence claim)
- **RESULT** `mem_keys`, `mem_tok`, `mem_src`, `mem_pos`, `mem_ctx` and **all model weights bit-identical over 20,364 entries** (`457c9d0`)
- **CONCLUDED** Exactly equivalent; shipped on.
- **STANDS NOW** **Stands.**
- **ERA** pre-both (era is largely irrelevant to a bit-identity claim, which is why these survive)

### X09 — ENC_FUSE
- **ARM / NAME** `ENC_FUSE=1`
- **CONFIG** anchor and positive batches fused into one encoder pass
- **QUESTION** Is the encoder fusion equivalent?
- **n** n=1 seeded pair
- **RESULT** Memory (keys/tok/src/pos/ctx over 23,707 entries) and model weights identical; **encoder weights differ ~1e-5 relative**. Wall 70s/73s → 62s/64s (~12%); encoder share 87%/86% → 81%/82% (`62e78d9`)
- **CONCLUDED** *"the earlier 'exactly equivalent' wording was too strong"* — mathematically equivalent, not bit-for-bit, because fusing changes the GRU kernel's batch shape and float addition is not associative. `ENC_FUSE=0` restores the bit-level guarantee.
- **STANDS NOW** **Stands**, including its own self-correction.
- **ERA** pre-both

### X10 — Isolating the two contrastive_step changes
- **ARM / NAME** gather-only (`ENC_FUSE=0`) vs fused (`ENC_FUSE=1`)
- **CONFIG** both halves of the `contrastive_step` change, separated
- **QUESTION** Which half costs the bit-identity, and which half carries the speed?
- **n** n=1 seeded pair per half
- **RESULT** `ENC_FUSE=0`: 69s vs 70s baseline (~1%), **bit-identical** in encoder, model and memory. `ENC_FUSE=1`: 62s/64s (~11%), equivalent only (`c95e187`)
- **CONCLUDED** *"nearly all the speed sits in the half that costs bit-identity"*; the device-resident gather is free and strictly safe.
- **STANDS NOW** **Stands.** A model entry for how to separate two changes that shipped together — the failure this project repeated most often (see X38, X43, `INV-10`).
- **ERA** pre-both

### X11 — KEY_BATCH
- **ARM / NAME** `KEY_BATCH=0` vs `=1`, SEED=7
- **QUESTION** Is batching the memory-key encodes equivalent, and does it speed anything up?
- **n** n=1 seeded pair
- **RESULT** `mem_tok`/`mem_src`/`mem_pos`/`mem_ctx` and **model weights bit-identical**; `mem_keys` **82 of 23,237 rows differ**, max abs **4.2e-8**, min per-key cosine **0.99999976**. CPU wall **142s → 144s: no speedup** (`f2fd2be`)
- **CONCLUDED** Equivalent to ~1000x tighter than `ENC_FUSE`, and **non-compounding** (stored keys are detached, nothing trains on them). The no-speedup outcome was the **pre-registered prediction** — a dispatch-count fix on a platform with no dispatch overhead.
- **STANDS NOW** **Stands.** The GPU speed claim was explicitly *not* made and remains unmeasured.
- **ERA** pre-both

### X12 — SIG_BATCH
- **ARM / NAME** `SIG_BATCH`
- **CONFIG** (a) 4-domain stress case, `RETOK_EVERY=200`, 2 epochs; (b) single-domain, cadence throttled to `ENC_EVERY_IDLE=12`
- **QUESTION** Is batching `sig_of` over the span where the encoder is provably frozen equivalent, and what does it buy?
- **n** n=1 per case
- **RESULT** (a) fully **bit-identical** — memory, model, encoder weights, 33 domains, next_id 39 — but `SIG_BATCH` **self-disables** there by construction, so *"that A/B measured the no-op case"*. (b) `sig_of` **9% → 3%** of the loop, **492 → 543 steps/min, +10.4%** (`ffb6bf8`). Pre-registered prediction was *"sig_of falls to ~3-8%"*.
- **CONCLUDED** Equivalent and worth +10.4% where the gain lives; explicitly noted that the A100 at d=768 has `sig_of` at 46%, so the GPU gain should be larger — *"that is not yet measured and no GPU number is claimed"*.
- **STANDS NOW** **Stands**, including its own admission that the bit-identity check tested the no-op case.
- **ERA** pre-both

### X13 — REKEY_CHUNK and AMP=bf16, both rejected on measurement
- **ARM / NAME** `REKEY_CHUNK=16`, `AMP=bf16`
- **QUESTION** Do these two speed knobs pay?
- **n** n=1 each
- **RESULT** Both **rejected on measurement** (`ffb6bf8`, recorded in `STATE.md` R40). Same block records: the transformer's LM is competitive on time (**1.532 ms** GRU/28.7M vs **1.572 ms** TRF/53.9M, +2.6% for 1.9x params) and loses only because `KEY_SRC=model` routes the memory-key path through it; boundary density swings throughput **~2.7x** between single- and multi-domain runs.
- **CONCLUDED** Not adopted.
- **STANDS NOW** **Stands as a rejection.** But the parameter counts quoted alongside (28.7M / 53.9M) are the *intended* d=768 figures — see `INV-01` and `E1` (`a5cd9ed`): `D_MODEL_B` was read by nothing, so the **A100 throughput bench itself ran at d=128 (4.31M / 5.07M)** and is **VOID**. The timing comparison above post-dates the fix in the same commit series; the earlier component ranking does not.
- **ERA** pre-both

---

## §4. The domain-assembler campaign (2026-07-25 .. 07-31)

The largest block of experiments in the project, and the one whose **target was later declared
wrong**. Read `08_GLOSSARY` §1.8 first: `domain` changed meaning twice — the four seeded corpora
were disowned as a **scaffold** (`efb818a`), *"domain assembly works, purity 0.54→0.96"* was
**retracted** (`5e02cfc`), and finally domain counts, purity, silhouette, V-measure and
specialization were relabelled **DIAGNOSTICS, NOT TARGETS** (`9d90416`).

Two invalidations sit under almost the whole campaign: **`INV-04`** (`MANAGE_MERGE=0.12` overrode
the intended 0.28 fallback for the project's whole life, so creation ran at 0.35 against
consolidation at 0.12) and **`INV-05`** (`MANAGE_EVERY=500` exceeded the run length, so merge, cull
and fold executed **zero** or **one** times). Both mean the consolidation half of the mechanism was
switched off while it was being tuned.

### X14 — Domain configs A / B / C / D
- **ARM / NAME** configs A, B, C, D (`6397041`)
- **CONFIG** A = fixed `NEW_DIST`/`SHIFT_DIST`, `ENC_WARMUP=30000`; B = adaptive spawn (censored), 30000; C = relative + q75*2.0, 4000; D = relative + q50*1.5, 1000
- **QUESTION** Do the adaptive/relative spawn rules beat the fixed constants?
- **n** n=1 per config
- **RESULT** A: 142 domains, recall 0.96, **V=0.42** · B: 53, 0.96, 0.38 · D: 77, 0.22, 0.12 · C: 1, 0.01, 0.00
- **CONCLUDED** *"Every change I made since the original lowered the primary metric."* `DOM_ADAPTIVE`, `DOM_RELATIVE`, `SHIFT_REL` all reverted to 0; repo behaves as config A. Honest note in the same commit: runs C and D changed the threshold rule **and** `ENC_WARMUP` together, *"so neither can be attributed"*.
- **STANDS NOW** **`INV-37` — VOID as a ranking.** V-measure against four seeded corpora is the wrong target (`efb818a`), and *"the four configurations measured so far need re-ranking on recurrence"*. Also **`INV-05`**: the 142-domain figure specifically is void — consolidation never ran. The self-flagged C/D confound stands as stated.
- **ERA** pre-both

### X15 — The encoder loss floor vs the assign rule
- **ARM / NAME** `constants` / `radius+fold` / `floor K=8` / `floor K=8 + radius+fold` / `floor K=4 + radius+fold`
- **CONFIG** real text, 60 kB, 4 corpora, `ENC_WARMUP=4000`, one variable at a time; `DOM_MANAGE_EVERY=100` introduced here so management actually fires
- **QUESTION** Is the fragmentation caused by the assign rule, or by the encoder's budget?
- **n** n=1 per arm (5 arms). Stated in the commit: *"one run per arm, one stream length, one seed."*
- **RESULT** constants: 50 live, 34% recurrent, V 0.42 · radius+fold: 36, 61%, V 0.40 · floor K=8: 23, 48%, **V 0.49** · K=8+radius+fold: 16, **88% recurrent**, **V 0.50** · K=4+radius+fold: 6, 83%, **V 0.54** (`510c695`)
- **CONCLUDED** *"THE ASSIGN RULE WAS NOT THE MAIN PROBLEM."* The encoder loss floor dominates; `ENC_FLOOR_K` defaulted ON at 8. Also the discovery that **`manage()` never ran** — `MANAGE_EVERY=500` against a 468-step run.
- **STANDS NOW** **Superseded, then partially withdrawn.** `3f44ce3` (X17) explicitly withdraws the *"encoder budget dominates the assign rule"* reading two days later, on direct geometric evidence. The **discovery** that management never ran stands and is `INV-05`. The V-measure ranking is `INV-37`.
- **ERA** pre-both

### X16 — MANAGE_MERGE 0.12 vs 0.45, with a falsification series
- **ARM / NAME** `MANAGE_MERGE`
- **CONFIG** 4 MB GPU run, long segments, everything else fixed; then a CPU sweep 0.45 / 0.60 / 0.80 / 1.00
- **QUESTION** Was the fragmentation this project spent weeks attributing to the assign rule actually a threshold inconsistency?
- **n** n=1 per threshold (GPU pair), n=1 per point on the CPU falsification series
- **RESULT** GPU: **0.12 → 25 live**, purity 0.97, completeness 0.60, V 0.72, 8x fragmentation. **0.45 → 4 live**, purity 0.97, completeness 0.89, **V 0.89**, clean bijection to the four corpora, every one recurrent. CPU falsification: 0.45→7 live (purity 0.96), 0.60→6 (0.88), 0.80→4 (**purity 0.71** — *"COUNTERFEIT 4"*), 1.00→5 (0.60) (`13e787a`)
- **CONCLUDED** `manage()` computed `md = merge_dist if merge_dist > 0 else MERGE_FRAC*NEW_DIST`; `MANAGE_MERGE=0.12` is non-zero, so the intended 0.28 **had never once run**. *"Domains could be created three times more readily than they could be joined, which is the whole of the fragmentation this project has spent weeks attributing to the assign rule, the encoder, and the creation threshold in turn."*
- **STANDS NOW** **The defect stands and is `INV-04`.** The *threshold choice* does not: `8914dd1` reverted 0.45 → 0.28 because **0.45 maximised V against the four seeded corpora, which is the wrong target** (`INV-37`). Per `08_GLOSSARY` §1.14, HEAD is **0.28** = `MERGE_FRAC*NEW_DIST`, and it is a **policy** knob (how finely can you forget?), not a correctness one. The falsification series — that "4 domains" is reachable two ways and the count alone cannot tell them apart — is the durable part.
- **ERA** pre-both

### X17 — Segment length vs V-measure
- **ARM / NAME** `SEG_MIN`/`SEG_MAX` at 180-460 B / 700-1800 B / 2800-7200 B
- **CONFIG** CPU, d64, WIN=128 bytes, 4 corpora, 60 kB, `ENC_WARMUP=4000`, varying only segment length
- **QUESTION** Is the low V-measure a property of the assembler, or arithmetic in the testbed?
- **n** n=1 per arm (3 arms), plus `probe_ckpt_geometry.py` on the 4 MB rerun's own encoder
- **RESULT** 2.5 windows/segment → 15 live, purity 0.54, V **0.19** · 9.8 → 16, 0.87, V **0.50** · 39.0 → 12, 0.88, V **0.68**. V is monotone in segment length while the live count barely moves (15/16/12). Geometry probe: mean true-corpus silhouette **+0.24**, 1-NN corpus accuracy **0.984**, d_between/d_within **1.71** (`3f44ce3`)
- **CONCLUDED** The encoder separates the kinds and **is not the bottleneck** — *"the earlier 'encoder budget dominates the assign rule' reading is withdrawn"* (i.e. X15's headline). What the run was up against was arithmetic: 3213 true switches over 4,000,000 bytes = 1245 bytes/segment, against ~486 bytes per analysis window = **2.6 windows per segment**, of which `SUSTAIN=2` are spent detecting the boundary. `SEG_MIN`/`SEG_MAX` (700/1800) were chosen when WIN was ~96 **bytes** and never revisited when WIN became 256 **tokens**.
- **STANDS NOW** **Stands as a two-sided falsification**, and it is one of the better-designed experiments here: it named the confound, varied one knob, and reproduced the GPU run's numbers at the matching window count. Still `INV-37` for any V-measure *target* reading, and `E4` applies — the signature encoder was reading 42% of the stream until `98e3301`.
- **ERA** pre-both

### X18 — SEG_CONTIG: were the domains our own seek points?
- **ARM / NAME** `SEG_CONTIG=0` vs `=1`
- **CONFIG** same seed, same everything, only the read mode differing; one English corpus
- **QUESTION** On a single corpus, how many "domains" are artefacts of `seg_from` drawing from a random offset every `SEG_MIN..SEG_MAX` bytes?
- **n** n=1 paired
- **RESULT** random offset: **31 LIVE domains**, order-1 3.500 | MODEL 3.349. contiguous: **13 LIVE domains**, order-1 3.498 | MODEL 3.513 (`98f19fa`)
- **CONCLUDED** *"More than half the domains were seek artefacts. 13 is the number that is about English."* Contiguous is also the harder stream (bits/byte worse), which is the expected direction. Default: contiguous for one corpus, random for several.
- **STANDS NOW** **Stands.** Cleanly paired, one knob, and the direction of the bits/byte change was predicted. `INV-13` era caveat applies. Note this makes the earlier *"eng_only reporting 71 domains"* figure (`e60b8e0`) partly a count of our own splices.
- **ERA** pre-both

### X19 — ENC_VREG: contrastive collapse on homogeneous text
- **ARM / NAME** `ENC_VREG` at 0 / 1.0 / 5.0 / 5.0+CREG
- **CONFIG** English only, 80 kB
- **QUESTION** Why does going English-only destroy the domain structure?
- **n** n=1 per arm (4 arms); commit states *"single run per..."*
- **RESULT** `DOMAINS=eng` encoder loss plateau **3.83/3.78** against **ln(ENC_BATCH=48) = 3.871** — exactly the loss of an encoder emitting one constant vector. Four corpora plateau at 2.10/2.18. Downstream: separation 0.16→0.05, 0 boundaries, **1 domain**, and a report page of purity 1.00 / V 1.00 / silhouette +0.95 / "1/1 GENUINE", *"because a partition of one is perfect"*. With `ENC_VREG`: 0 → 2 domains, sep 0.01, loss 3.85 · 1.0 → 5, 0.44, 3.70 · **5.0 → 17, 0.97, 1.69** · 5.0+CREG → 24, 0.96, 1.85. Cost on mixed material: V 0.56→0.52, 4.322→4.384 b/B (`c1aadda`)
- **CONCLUDED** Textbook contrastive collapse; the extra corpora had been the only thing *preventing* it, which **inverts** the standing hypothesis that they were throwing the system off. `ENC_VREG` defaulted ON at 5.0. Also: the constant `SHIFT_DIST` works again once the scale is healthy — `SHIFT_REL` had merely been compensating for a collapsed space.
- **STANDS NOW** **Stands.** The diagnosis is mechanistic (loss exactly at `ln(batch)`), not statistical, which is what makes it survive n=1. The perfect-scores-on-a-partition-of-one observation is a permanent warning about this report battery.
- **ERA** pre-both

### X20 — Is the partition informative? (with a permutation null)
- **ARM / NAME** own-domain vs random-other-domain retrieval, at matched restriction
- **CONFIG** 60 kB; deliberately **not** own-vs-global; re-run against a random permutation of the provenance tags
- **QUESTION** Does the domain label carry predictive information the memory keys do not already have?
- **n** n=1 per corpus condition
- **RESULT** 4 corpora: own 4.167 vs foreign 4.527 = +0.360, null +0.265, **EXCESS +0.095 → informative**. English alone: own 3.635 vs foreign 3.920 = +0.286, null **+0.341**, **EXCESS −0.055 → NOT** (`8914dd1`)
- **CONCLUDED** *"The raw English gap of +0.286 looks convincing and is below chance. Without the control this would have been reported as 'English sub-domains carry information', and it would have been wrong."*
- **STANDS NOW** **Stands, and is the methodological high point of the campaign** — a pre-specified null that changed the verdict on the first thing it was pointed at. Caveats printed at the time: n=1, 60 kB, small model, predictive utility only.
- **ERA** pre-both

### X21 — Putting an error bar on that null
- **ARM / NAME** `INFO_NULLS` (default 5 permutations, 2σ verdict)
- **CONFIG** two 4 MB English runs differing **only in SEED**
- **QUESTION** Was the informativeness verdict stable, or was it flipping on noise?
- **n** **n=2 seeds** (the whole point of the entry)
- **RESULT** The two runs came back at excess **+0.010** and **+0.013** against a hard cutoff of 0.010 and printed **opposite conclusions**. With a proper null: spread **±0.020**, excess **+0.000**; both sit well inside ±2σ = ±0.040 (`3e2393d`)
- **CONCLUDED** *"The threshold was inside its own noise band... the disagreement was never real."* The negative result stated plainly: with 64-68 well-formed, recurring, boundary-detecting English domains, **the partition carries no predictive information beyond a random partition of the same shape** — consistent with the code, since `did` is consumed only by `mem.src`, `dom_exp` and the clustering report, and nothing in the prediction path reads it.
- **STANDS NOW** **Stands.** A rare case of the project measuring its own instrument's noise *before* the conclusion hardened.
- **ERA** pre-both

### X22 — The domain prior: making domains available to prediction
- **ARM / NAME** model alone | + GLOBAL prior | + OWN-domain prior | + RANDOM-domain prior
- **CONFIG** per-domain token histograms blended via `DOM_PRIOR`; evaluated on **held-out** text, eval windows assigned the way the assembler assigns them
- **QUESTION** If prediction is *given* the domain label, does it earn its keep? (Two nulls needed: OWN must beat GLOBAL to show the partition adds over plain frequency, and beat RANDOM to show the *label* is doing it.)
- **n** n=1 per arm, three conditions
- **RESULT** eng only, 31 domains: 3.503 | 3.539 | 3.523 | 3.524 → own−global **+0.016**, own−random **+0.000**. 4 corpora, 6 domains: 3.912 | 3.970 | 3.919 | 3.982 → **+0.050 / +0.063**. 4 corpora, weight 0.05: 3.912 | 3.928 | 3.910 | 3.932 → +0.018 / +0.021 (`7b481a1`)
- **CONCLUDED** On four distinct corpora the label predicts. On a single English corpus it does not — own and random are identical to three decimals. *"Without the random-domain arm that would have read as a success."*
- **STANDS NOW** **Stands.** Same two-null design as X20. Since the production target is one large corpus, the operative half is the negative one.
- **ERA** pre-both

### X23 — Domain stability across seeds
- **ARM / NAME** `probe_stability.py` on two CPU seeds
- **CONFIG** 60 kB, D=64, 3 domains, CPU
- **QUESTION** Is the discovered partition reproducible across seeds, and is it the same as our seeded labels?
- **n** **n=2 seeds**
- **RESULT** Agreement A vs B (NMI) **0.757**; shuffled-B floor **0.002** [0.000–0.005 over 20 draws]; agreement with the seeded corpora **A 0.655 / B 0.760** (`80a4533`)
- **CONCLUDED** *"The two runs agree with EACH OTHER (0.757) more than run A agrees with the categories we spliced in (0.655). That is the discovery signature."* Caveat printed loudly in the same commit: 60 kB / D=64 / 3-domain CPU run, **not** the 4 MB configuration.
- **STANDS NOW** **Stands at the scale it was run**, and it is the only direct evidence in the project bearing on how arbitrary the four seeded domains are. It has never been repeated at pilot scale. The probe had **never once produced a number** before this commit.
- **ERA** pre-both

---

## §5. The 18-arm grid

### X24 — The 18-arm grid: chaining loses to no fabric at all
- **ARM / NAME** `base weights nofabric balance frozvocab softroute keynorm divw smallpop curric society stateq wt_bal wt_div nomem chainsup explore kitchen` (the `GRID_ARMS_DEFAULT` as of `ffd39b8`)
- **CONFIG** grid harness: `MODEL=gru LAYERS=1 D_MODEL=768 WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100 GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 ENC_WARMUP=2000 MEM_CAP=200000`, 4 MB/epoch × 8 epochs, plus each arm's own flags from `_flags_for`
- **QUESTION** Across the whole knob surface at once, which configuration is best — and does chaining beat having no fabric?
- **n** **n=1 per arm, 18 arms.** 18/18 trained; **4 lost their report to a crash** (`generate()` hitting a device-side CUDA assert on a non-finite distribution — a diverged run produces exactly that; fixed in the same commit)
- **RESULT**

  | arm | since-min | held-out | vs order-1 | specialization |
  |---|---|---|---|---|
  | society | +0.605 | **2.058** | +1.381 | 0.126 |
  | nofabric | +0.670 | **2.118** | +1.320 | n/a |
  | divw | +2.151 | 2.324 | +1.115 | 0.000 |
  | base | +2.287 | 3.124 | +0.314 | 0.000 |
  | weights | +2.434 | 3.989 | n/a | 0.142 |
  | kitchen | +2.637 | 3.221 | +0.217 | 0.105 |

- **CONCLUDED** *"Every chaining arm is worse than FABRIC=0."* The generation agrees with bits/byte — society and nofabric produce English, every chaining arm produces degraded noise. Mechanism, measured across all arms and unmoved by any intervention: **depth 1.00 of 4 and HALT mass 0.0000 in every arm**; **H(hop1|hop0) = 0.007 to 0.058 bits everywhere**; `softroute`, `curric`, `stateq`, `chainsup` all leave it there. *"One decision, then a rail."*
- **STANDS NOW** **The ranking is `INV-35` — VOID as an arm ranking** (n=1 per arm against a seed spread later measured at 1.227 b/B; the 0.060 between `society` and `nofabric` is far inside it). What survives is (a) the **qualitative** finding, corroborated by the generated text rather than by a decimal — chaining produces noise; (b) the **mechanistic** finding H(hop1|hop0) ≈ 0.007–0.058, which is a structural measurement across 18 arms and is the thing `7b18214` later moved (X28); (c) the **ramp-latch negative** below.
- **ALSO IN THIS ENTRY — the ramp latch, a clean pre-registered negative.** Churn fell from ~10062 grown / 5969 culled to **~4210 / 1205**, latched in every arm, population settling ~3000 instead of pinned at the cap — and **divergence got WORSE** (+1.438 → +2.287 for base). *"The cull-refill cycle was real and was not the cause. Recorded as a clean negative for the hypothesis."* See `08_GLOSSARY` §1.9 for `ramp`'s changed meaning.
- **ALSO** — the correction the project owed itself: *"The weight-prediction term is 2% of the routing decision"* was measured on a 64-expert **toy**; at 4096 it is **7% region / 93% weight-prediction**, and `FAB_KEY_NORM=1` **reduces** it (41/59). See `INV-27` and O12.
- **ERA** pre-both

---

## §6. Chaining vs society vs chained society

Read `08_GLOSSARY` §1.5 before this section. **`society` changed meaning twice.** Through 08-04,
`SOCIETY=1` = independent experts, one round, blended at the prediction; `SOCIETY=0` = chaining
through a learned transition matrix. From `7b18214` there is a **third** path, *chained society*,
reached by `SOCIETY=0` + `CHAIN_ROUTE=soc`, and made the default at `53fbae5`. **At HEAD,
`SOCIETY=0` does not mean chaining.** Any pre-08-05 log that says `SOCIETY=0` does mean chaining.

### X25 — Do the experts chain at all?
- **ARM / NAME** the audit at `33355b2` (not an arm comparison; an inspection with two retractions)
- **QUESTION** Do experts chain via the router?
- **n** n/a — a code-path audit, reported as such
- **RESULT** They do not, and never have. Every run of the project used `society()`, where every expert maps the same `h` and expert *i* never sees expert *j*; `_dep` is zeros. The transition matrix, HALT, `FAB_STEPS`, `PONDER` and `PONDER_WARM` are all present and **inert on the default path**.
- **CONCLUDED** Two self-corrections: (1) *"the router HALTs 90%, mean routed depth 0.10 of 4"* came from a **report-time probe of a path the run did not use**; (2) the whole pilot had been justified on *"PONDER_WARM=8000 never completes"*, but on the society path the ponder cost is **identically zero**. *"Second time this session a justification of mine was about inert code."*
- **STANDS NOW** **Stands, and both retracted claims are `INV-40` (VOID).** This entry exists because it is the reason several later experiments were run at all.
- **ERA** pre-both

### X26 — Chaining, once it could actually run
- **ARM / NAME** `SOCIETY=0` with `FAB_CHAIN_K=8`
- **QUESTION** Does the chaining path work when it is not OOMing?
- **n** n=1 (verification run, 343 experts)
- **RESULT** Chaining OOM'd at **972 experts** — `Bo` was (B,N,L,d) = 12 GB for one hop. Top-k-by-current-mass per hop fixes it. Then, with the OOM gone: **mean routed depth 0.00 of 4** — HALT absorbing on the first hop because `FAB_MIN_STEPS` defaulted to 0. *"Chaining switched ON and nothing chained."* Fixed by defaulting `FAB_MIN_STEPS` per path (0 under society, 2 under chaining): depth **0.00 → 0.60** (`c4000c6`)
- **CONCLUDED** *"A composition mechanism that is enabled but never entered is worse than one that is off, because it reads as tested."*
- **STANDS NOW** **Stands.** Its consequence is that the chaining arms in X24 are the *first* chaining runs that chained at all.
- **ERA** pre-both

### X27 — CHAIN_VOTE: separating depth from where the experts combine
- **ARM / NAME** `vote` (`CHAIN_VOTE=1`)
- **CONFIG** multi-hop with the society's combination rule — experts vote on the OUTPUT at every hop, `h` still carries each hop's result forward
- **QUESTION** The two paths differ in **two** ways at once — DEPTH (one hop vs many) and WHERE THE EXPERTS COMBINE (prediction vs hidden state). Which one does society win on?
- **n** n=1, toy config
- **RESULT** HALT **0.0000 → 0.2213**; held-out **5.361 → 5.191** (`9b179b5`)
- **CONCLUDED** *"the only configuration in which HALT has a job"* — under voting, mass that halts at hop *t* selects hop *t*'s prediction, so stopping early is rewarded exactly when later hops are worse. HALT's 0.0000 across all 18 arms of X24 was *"the gradient's CORRECT answer to the question the architecture asks"*.
- **STANDS NOW** **Superseded by X28**, which found `CHAIN_VOTE` was not the idea it was meant to implement. The held-out numbers are toy-scale and are not pilot results; `vote` has **never run at pilot scale** (see §15).
- **ERA** pre-both

### X28 — CHAIN_ROUTE=soc: the society, actually looped
- **ARM / NAME** `society` / `vote` / `socloop` / `socloop_w`
- **CONFIG** `socloop` = `CHAIN_ROUTE=soc CHAIN_VOTE=1`; `socloop_w` adds `ROUTE_REGION_W=0 FAB_KEY_NORM=1`. Every iteration re-routes **from scratch** with the society's own router, current state in the query. No transition matrix, no SRC.
- **QUESTION** `CHAIN_VOTE` changed only *where* experts combine and kept the learned transition matrix, so each hop still routed from the holder's identity — *"chaining with a vote bolted on, and it is where the rail lives"*. Does re-routing from scratch break the rail?
- **n** **n=1 per arm, toy scale.** The commit says so: *"Toy signal, and it is only a toy."*
- **RESULT** society: held-out 5.044 · vote: H(hop1|hop0) −0.000, HALT 0.328, 5.191 · **socloop: −0.000, 0.345, 4.918** · **socloop_w: H 0.270, HALT 0.690, 4.925** (`7b18214`). Then at pilot scale after the default flip: **H(hop1|hop0) = 0.533 bits over 202k transitions**, against 0.005–0.058 for every transition-matrix arm (`53fbae5`)
- **CONCLUDED** 0.270 (toy) and then 0.533 (real) are *"the first non-trivial value this measurement has ever produced"* — the second routing choice genuinely varies given the first. `CHAIN_ROUTE=soc + CHAIN_VOTE=1` became the default at `53fbae5`.
- **STANDS NOW** **The H(hop1|hop0) contrast stands** — it is a structural measurement over 202k transitions against a band established across 18 arms and both pilots, which is about as far from n=1 as this project gets. **The held-out numbers do not**: the toy figures are toy, and the arms `socloop`, `socloop_w`, `vote`, `vote_w` have **never run at pilot scale under their own names** (§15) — the configuration reached pilot scale only by becoming the default.
- **ERA** pre-both

---

## §7. Chain credit assignment

### X29 — CHAIN_SUP / CHAIN_CURRIC / CHAIN_STATE_Q
- **ARM / NAME** `chainsup` (`CHAIN_SUP=0.3`), `curric` (`CHAIN_CURRIC=1`), `stateq` (`CHAIN_STATE_Q=1`)
- **CONFIG** a synthetic task where each domain needs an **ordered pair** of transforms: 6 domains, 24 experts, depth 4, uniform-guess loss 3.871
- **QUESTION** The only loss is one cross-entropy at the end of the walk, reaching hop *t* through D−*t* LayerNorms; `topk`'s indices are not differentiable, so the gradient can re-weight an expert already chosen but can never say "you should have gone elsewhere". Can any of three interventions fix credit assignment through the chain?
- **n** **n=3 seeds per arm** — one of only three experiments in the project with n=3
- **RESULT** baseline **2.52 / 3.00 / 2.72** · `CHAIN_SUP=0.3` **3.17 / 3.50 / 3.64 — WORSE on all seeds** · `CHAIN_CURRIC=1` *"depth rarely left 1; where it reached 2, worse"* · `CHAIN_STATE_Q=1` **2.79 / 2.71 / 2.74 — neutral** (`7e9612d`)
- **CONCLUDED** All three off by default, *"reports that the attempts did not work rather than shipping them"*.
- **STANDS NOW** **Two of three stand; the curriculum result is `INV-08` — VOID, withdrawn.** `e0ce4f7`: `maybe_deepen` sat behind `step % MANAGE_EVERY == 0` while that block runs only on 1-in-`BATCH_W` flush steps, so the intersection was empty and **it was never called in a real run**. *"I reported 'staged depth did not help' from a run in which it had not executed."* The commit notes this was the **third instance of the same cadence bug** in the file (see `E2`, `INV-07`). `CHAIN_SUP` and `CHAIN_STATE_Q` stand as measured — and note both are n=3 on a synthetic task, not on the pilot corpus.
- **ERA** pre-both

---

## §8. Learning rate

The one place this project found an effect **far outside** its own noise floor.

### X30 — Cosine vs no schedule
- **ARM / NAME** `LR_SCHED=cosine` vs `none`
- **CONFIG** paired pilots at `1593c70`, **both pure defaults**
- **QUESTION** Is the degradation every pilot shows the architecture, or the optimiser? Before this there was **no LR schedule at all**: `lr=2e-3` constant, no warmup, no decay, for 48,000 steps, across all 17 pilots (`E6`).
- **n** **n=1 each, paired**
- **RESULT** cosine held-out **2.101**, last two thirds **−0.007**, order-1 +1.337. none held-out **4.193**, last two thirds **+1.668**, ending at 5.16. Constant LR **oscillates between 3.4 and 7.8 for the whole run**; the schedule settles to a flat 3.7–3.8 plateau. Generated text: English vs noise (`c33f078`)
- **CONCLUDED** *"the degradation every pilot in this project has shown was substantially the optimizer — not the fabric, not the router, not the tokenizer. Every architecture comparison made before this was measured through it."*
- **STANDS NOW** **Stands — and it is the one architecture-independent effect in the record that is far outside seed spread.** `6bd226c` re-affirms it explicitly: *"the LR schedule effect is far outside seed spread (4.193 → 2.101)"*. The 2.101 arm's **specialization 0.132** claim from the same commit does **not** stand — see O13 and `INV-35`.
- **ALSO** the verdict fix in the same commit: measuring only from the global minimum cannot distinguish "rose early then settled" from "still rising", so `NOT DIVERGING` / `PLATEAUED` / `DIVERGING` are now decided on the **recent** slope. Replaying: cosine → PLATEAUED, none → DIVERGING.
- **ERA** pre-both

### X31 — LR_EPOCHS: separating the schedule horizon from run length
- **ARM / NAME** `LR_EPOCHS`
- **CONFIG** the `vmax4k` pair — identical config, identical vocabulary trajectory, both reaching 4096 near step 40k
- **QUESTION** `EPOCHS` set both the run length **and** the cosine horizon. Were "8 epochs" and "18 epochs" two lengths, or two schedules?
- **n** n=1 pair, plus an exact verification (`_lr_at`/`_project` lifted from source, 19 overlapping sample points, zero mismatches)
- **RESULT** LR ratio E8:E18 at step 20000 **1.4x**, at 40000 **7.6x**, at **44000 11.0x**. Step 44000 is where the 8-epoch run posted its best held-out (2.059) at **5% of peak**, while the 18-epoch run was at **56%** and moving away from its own minimum. The 18-epoch run filled its vocabulary completely (4096/4096, 0% never minted), **so dead rows do not explain it** (`9fabba4`)
- **CONCLUDED** *"'8 epochs beat 18' and 'a low LR beat a high one' were the same observation."*
- **STANDS NOW** **The defect stands; the claim it killed is `INV-30` — VOID.** This is a mechanism finding verified by lifting the function out of the source, not by a run, which is why it survives n=1.
- **ERA** mid (`9fabba4`, 08-11: post-`5f4f117`, pre-`c76dc74`)

### X32 — LR_RESTARTS: does the cosine repeat or hold at the floor?
- **ARM / NAME** `LR_RESTARTS`
- **QUESTION** A run longer than the wavelength was saturating at 5% of peak. Is that wasted?
- **n** n=1 (the 30-epoch comparison), plus exact schedule verification
- **RESULT** **12 extra epochs at the floor bought 0.009 b/B** (`vmax8k_30ep_lr8` 3.368 vs `vmax8k_18ep_lr8` 3.377 in `runs.csv`) (`c341921`). Verified against `_lr_at`: at step 46000 RESTARTS=1 gives 100% of peak, RESTARTS=0 gives 5%; **the first cycle is identical under both**, so an 8-epoch run is unchanged.
- **CONCLUDED** Restarts adopted; each cycle gets a fresh high-rate phase and a fresh anneal.
- **STANDS NOW** **Stands as an exact schedule property.** The follow-up `fec2285` found and fixed a real regression in it: when the wavelength **is** the run, `_prog` reaches 1.0 and `1.0 % 1.0 == 0.0`, so **the rate jumped back to PEAK on the final steps of every 8-epoch run** — *"the one configuration that has to reproduce earlier results was the one it broke"*. Fixed by fitting a whole number of cycles; re-verified at **max |restarts − hold| = 0.000e+00** over a whole 8-epoch run. That property is what `runs.py:153-160` relies on when it declines to flag 8-epoch rows as stale.
- **ERA** mid

### X33 — The LR_RESTARTS=0 arm, and what it actually refuted
- **ARM / NAME** `vmax4k_18ep_norestart` (`LR_RESTARTS=0`, guard on)
- **CONFIG** `EPOCHS=18 LR_EPOCHS=8`, `VMAX=4096`, commit `e200178`
- **QUESTION** Are the restarts net-negative? (Prediction: yes.)
- **n** n=1 — *and that is the finding*
- **RESULT** **3.054** against **2.132** with restarts ON — the opposite of the prediction. Then the four runs of this nominally identical arm:

  | run | held-out | words | past-min | restarts |
  |---|---|---|---|---|
  | `vmax4k_18ep_lr8` | 2.023 | 89% | +0.000 | pre |
  | `vmax4k_18ep_guard` | 2.132 | 77% | +0.000 | 1 |
  | `vmax4k_18ep_norestart` | 3.054 | 49% | +0.433 | 0 |
  | `vmax4k_18ep_oldLR` | 3.250 | 43% | +0.439 | pre |

  **spread 1.227 b/B** on one arm; word quality swings **43%–89%** (`33a9299`)
- **CONCLUDED** *"So the run does not refute restarts either. It refutes the premise under every single-run comparison in this record."* Named as withdrawn in the same commit: *"vmax4k is the best regime"*, *"restarts are net-negative"*, *"2048 misbehaves at 18 epochs"*.
- **STANDS NOW** **The 1.227 b/B spread stands and is `INV-35`, the widest invalidation in `05_ERRORS`.** The restart comparison itself is void in both directions. What the commit says survives: the determinism check, and the code defects themselves.
- **ERA** mid (all four rows pre-`c76dc74`, per `01_TIMELINE` Appendix A)

### X34 — The late restart at 100% of peak
- **ARM / NAME** `ep18_big_s{0,1,2}`
- **CONFIG** 18 epochs + 4x stream on a **re-fetched, larger, harder** corpus, commit `bf53d40`
- **QUESTION** What does a cosine restart deep into training cost?
- **n** **n=3 seeds**
- **RESULT** A real restart at step **201925**: **1.00e-04 → 2.00e-03, a 20x jump back to full peak**. The held-out curve after it swings by **1.5 b/B and never resettles** (3.82 3.29 3.04 4.01 3.39 4.04 4.08 … 3.92 3.19 2.58 3.85 3.63). The two seeds whose base model reads 5.612 and 5.268 are the ones that ended near a restart; the one at 3.023 landed better in the cycle — *"That is the entire 0.364 spread."* Held-out **2.243 / 2.200 / 2.564** (`ac79e92`)
- **CONCLUDED** The restart detector was also firing on the warmup ramp (three "restarts" reported at steps 15, 31 and 201925; only the third is one); fixed to require a return to a large fraction of peak.
- **STANDS NOW** **Stands as a mechanism**, but the held-out figures are **`INV-32` — DEGRADED**: the corpus was re-fetched and got harder (order-1 **3.440 → 3.747**), so these are **not comparable on raw held-out** to the 8-epoch arms. Against each run's own order-1 anchor: **1.411 vs 1.441** — *"18 epochs bought nothing, and did not cost the 0.34 the raw numbers suggest either."* This is the worked example behind `01_TIMELINE` Appendix B's rule: **quote every held-out figure against its own run's order-1**.
- **ERA** post-both (but pre-`E14`/`E15`)

### X35 — LR_DECAY: a falling envelope over the restarts
- **ARM / NAME** `LR_DECAY`
- **QUESTION** If every restart returns to 100% of peak forever, and X34 shows what that costs late in a run, can the fluctuation be kept while the ceiling comes down?
- **n** n=1 (measured over three cycles, schedule arithmetic)
- **RESULT** peaks **100/100/100%** at `LR_DECAY=0` (unchanged) · **100/88/64%** at 0.5 · **100/76/29%** at 1.0 (`91fd815`)
- **CONCLUDED** Adopted as a knob; `LR_DECAY=0` reproduces prior behaviour exactly.
- **STANDS NOW** **Stands as a schedule property.** It has **not** been run end-to-end as an arm — no `runs.csv` row carries a non-zero `LR_DECAY`. The same commit is `E14`: it surfaced that `s.born` was written only by `grow()`, so **founders were permanently immune to culling** — see X46 and `INV-15`.
- **ERA** post-both

---

## §9. Tokenizer

The longest-running argument in the project, and the one that reversed most often. Sequence:
freezing looks decisive (X36) → freezing is confounded with the LR horizon (`INV-29`) → the 6-arm
pilot says minting the whole run is **best** (X37) → and the largest effect turns out to be
re-segmentation on an unchanged vocabulary (X43), which is itself unattributable (`INV-10`).

### X36 — TOK_MINT_UNTIL=6000: freezing the vocabulary
- **ARM / NAME** `freeze6k` (`TOK_MINT_UNTIL=6000`), chained society, commit `18fdd6c`
- **QUESTION** Is the "divergence" every pilot shows caused by re-tokenisation?
- **n** n=1
- **RESULT** Minting frozen at step 6015, vocab 740. Curve falls monotonically for 60k steps after the freeze and is **still falling at the end**. *"best 3.70 @ step 57071 | final 3.70 @ step 57071 | since the minimum +0.000"*; bits/byte −0.607 over the last two thirds. **Held-out 2.189**, beats order-1 by +1.307 (`8c8d20b`)
- **CONCLUDED** *"the 'divergence' was the re-tokenisation, in two ways at once: the shocks themselves, and a held-out cache frozen in an obsolete segmentation."* Caveat stated **at the time**: a vocabulary frozen at 740 means shorter tokens, so the same byte budget is 67,872 steps instead of 47,231 — **~44% more optimizer steps**; and +1.307 against order-1 is inside seed spread of society's +1.381 and nofabric's +1.320, *"not yet a quality win"*.
- **STANDS NOW** **`INV-29` — UNATTRIBUTABLE.** *"'Frozen tokenizer' and 'schedule that anneals' were the same experiment"*: `_total_steps` was measured once at the seed vocabulary, so **only the frozen-vocabulary run has ever annealed** (0% over-projection, ended at the 5% floor; every minting run ended at 18–21% of peak). *"the tokenizer conclusion I drew from those four runs was not supported."* The commit's own compute caveat had already flagged half of it.
- **ERA** pre-both

### X37 — The 6-arm pilot bundle, with the two confounded knobs separated
- **ARM / NAME** `base` · `frozen` · `frozen_nr` · `drop` · `wdecay` · `reg` (the `pilots` preset)
- **CONFIG** `base` = defaults · `frozen` = `TOK_MINT_UNTIL=1` · `frozen_nr` = `TOK_MINT_UNTIL=1 RETOK_EVERY=0` · `drop` = `DROPOUT=0.1` · `wdecay` = `WEIGHT_DECAY=0.01` · `reg` = both. Run with `GRID_CKPT=0` (`SAVE_CKPT=0`) deliberately, because checkpointing gates extra `holdout_bpb` passes and mixing modes is what made the 3.694-vs-2.100 pair uncomparable (see O09).
- **QUESTION** The previous round ran `TOK_MINT_UNTIL=1` and `RETOK_EVERY=0` **together** and came back 1.4 b/B worse with no way to tell which did it. They are not the same idea: one stops MINTING, the other stops RE-SEGMENTING — and a re-segmentation producing a byte-identical stream is still not a no-op, because it clears the lookahead queue and blacks out fabric growth for `FAB_COOLDOWN` steps. So: one arm each.
- **n** n=1 per arm, 6 arms
- **RESULT** `base` **1.962** · `frozen` **2.072** · `frozen_nr` **2.365** (`707f1af`; recorded in `runs.csv` as the three `(no log)` rows sourced from `self_organize.py:4624`). Regularisation arms expected to cost, since every run reports UNDERFIT with a negative gap.
- **CONCLUDED** **The reversal.** `bdce727`: *"TOK_MINT_UNTIL — 'the project's own continual-learning failure mode, caused by our tokenizer'. **Backwards.** base 1.962 / frozen 2.072 / frozen_nr 2.365 — minting the whole run is BEST. What made freezing look good was the LR schedule."*
- **STANDS NOW** **Stands as the correction to X36**, with two caveats. (a) These three rows are `(no log)` — the numbers survive only in a source comment, which is the reason `runs.py` has a `manual` subcommand that stamps `--source` into the commit column. (b) `INV-42`: `frozen_nr`'s 2.365 was measured under **75% dead rows** and is not a clean measurement of "no re-segmentation" either; the clean re-runs are in X43.
- **ERA** mid (`707f1af`, 08-10, verified post-`5f4f117` / pre-`c76dc74` in `01_TIMELINE` Appendix A)

### X38 — TOK_COMPOSE: computing a token's vector from its bytes
- **ARM / NAME** `compose` / `nocompose` / `mintnovel` / `composenov`, and the run that motivated them
- **CONFIG** `e8df6fe` built a `ByteComposer` giving each token a vector computed from its bytes (no per-token parameters at all). `ed04aac` **rebuilt it to the opposite spec after correction**: keep per-token parameters, but start each at its composite plus a zero-init residual, with `TOK_ANCHOR` (0.05, tau 4000) holding a young token near its composite and releasing it as it accumulates material.
- **QUESTION** Does making a mint *continuous* — the token's vector already meaning something the instant it exists — remove the shock?
- **n** n=1 (`pilot_gru_8`, which ran `TOK_COMPOSE` **and** `TOK_MINT_NOVEL` together)
- **RESULT** Held-out across every pilot log in the project: **eleven runs across five commits sit in a 2.0–2.2 band**, with minting on or frozen, society or chained. The two runs outside it are the deliberate controls (`LR_SCHED=none` 4.193, `TOKENIZER=0` 4.378). **The third is `pilot_gru_8` at 5.360 — the one run with the composed token table** (`be50e3a`)
- **CONCLUDED** Back to default **off**: *"it is the only change that moved the LEVEL"*. And the honest note: *"minting is not costing level. Full minting gives 2.007–2.275; `TOK_MINT_UNTIL=6000` gives 2.189, worse than the median minting run and inside the seed spread."*
- **STANDS NOW** **Stands as a decision, not as an attribution.** `pilot_gru_8` confounded two knobs, so 5.360 cannot be assigned to `TOK_COMPOSE`. `d79c4ba` created the 2x2 (`nocompose` / `compose` / `mintnovel` / `composenov`) precisely to separate them — and **none of those four arms has ever been run** (§15). The isolating experiment is designed, built, and unrun. Also `bdce727` records that the original `TOK_COMPOSE` comparison *"compared one run against a band assembled from DIFFERENT harness modes, which we later found shifts a result by more than a bit/byte on its own"*.
- **ERA** pre-both

### X39 — WARMSTART_MODE: how a minted token should be initialised
- **ARM / NAME** `mintinit` (`WARMSTART_MODE=last/first`)
- **CONFIG** measured on the **immediate post-mint loss** — what the model has to climb back from at every mint
- **QUESTION** `WARMSTART` set both sides to the mean of the parents. But head and embedding are not symmetric: `head[ab]` scores "next is ab" from the state at position *t* (the same decision as "next is a"), while `emb[ab]` is what the recurrence *consumes* after `ab`. So should it be `head[ab]=head[a]`, `emb[ab]=emb[b]`?
- **n** **n=18 trials (6 pairs × 3 seeds) — the largest n in this project**
- **RESULT** random **2.1699** sd 0.120 · mean/mean (old) **1.8222** sd 0.078 · mean/first **1.6252** sd 0.071 · **last/first 1.4822 sd 0.011** · sum/first **1.6518** sd 0.100. last/first beats the old warm start by **0.340, i.e. 31x its own sd** (`c92d104`)
- **CONCLUDED** **Left OFF by default anyway**, because the only end-to-end check disagrees: a short toy with minting on gave held-out **5.214** with last/first against **5.100** with mean.
- **STANDS NOW** **Stands, and is the most statistically solid single result in the file** — on its own metric. The disagreement between an 18-trial microbenchmark and one end-to-end toy was never resolved: `mintinit` **has never run at pilot scale** (§15). This is the clearest case in the project of a well-measured proxy left unconnected to the deliverable.
- **ERA** pre-both

### X40 — The mint gate: p(b|a), not entropy
- **ARM / NAME** `nogate` (`TOK_MINT_PMIN=0`), `pgate_t` (0.15), `pgate_c`
- **QUESTION** Frequency alone cannot tell a UNIT ("th"+"e") from a pair straddling a boundary everything crosses ("e"+" "). Can a conditional-probability gate?
- **n** n=1 per threshold on 400 kB, 4 passes
- **RESULT** The entropy version shipped an hour earlier was wrong twice, both caught by running it end to end. **Wrong statistic**: over 400 kB of English at byte level H has median **3.48** bits, p90 4.39 — so `TOK_MINT_HMAX=1.5` rejected **81%** of left tokens; and H is **anti-correlated with frequency**, so an entropy gate rejects the most useful merges first (the top pair, `b' '+b' '` ×31432, sits at H=4.39). **Wrong control flow**: a rejected candidate returned `None`, which ends the grow burst, so **one blocked pair stopped minting entirely** — the end-to-end run reached vocab 256 of 1024 with 100% blocked. Vocabulary reached at 1024-cap: pmin **0.10 → 1010**, **0.15 → 623**, **0.25 → 353** (`93c1733`)
- **CONCLUDED** `TOK_MINT_PMIN` replaces `TOK_MINT_HMAX`; the gate walks down the ranking rather than aborting; H stays as a **diagnostic**, not a gate.
- **STANDS NOW** **Stands.** Note `08_GLOSSARY`: `pgate` was dropped as an arm name because 0.10 became the default, *"an arm that changes nothing while reading as though it tests something"* — the informative arm is `nogate`, which turns it off.
- **ERA** mid

### X41 — The gate starved the vocabulary; fail open
- **ARM / NAME** `base_8ep_gate_starved` (`TOK_MINT_PMIN=0.1`), commit `136461c`
- **QUESTION** Does the 0.10 default hold on the project's standard pilot config? (It had been validated only on a 400 kB test, with the risk flagged for `VMAX=8192`.)
- **n** n=1 — and it broke at `VMAX=2048`, not 8192
- **RESULT** Minting decelerated and asymptoted ~600 short of the cap: epoch 2: 878 → epoch 8: **1439**. `[vocab] never minted 609 (29.7% of width)`. **Held-out 3.600**, best 2.829 at step 6000, **+0.910 past its own minimum**, against an ungated baseline near 1.96. Median p(b|a) of everything judged was **0.029** against a 0.10 threshold, so once the top-1024 window held no passing candidate the gate minted nothing **permanently** (`1a113f5`)
- **CONCLUDED** **FAIL OPEN**: the gate may REORDER what gets minted and may never PREVENT a mint. Verified over 8 passes at `VMAX=2048`: pmin 0 / 0.10 / 0.15 all reach 2048/2048, with 734 and 1103 **forced** mints respectively; `gate_forced` is now reported.
- **STANDS NOW** **Stands.** The `nogate_8ep_pilot2` row in `runs.csv` is the confirmation: **byte-identical to `base_8ep_pilot2`** (2.239, same final step 48133) once the default returned to 0 — which doubles as a free determinism check.
- **ERA** mid

### X42 — Probationary minting
- **ARM / NAME** `prob_use` (`TOK_PROBATION=200`), `prob_emb` (`+ TOK_PROBATION_BY=embed TOK_COMPOSE=1`)
- **QUESTION** `TOK_MINT_PMIN` judges a merge from co-occurrence **before the model has seen it once**. Can a token be minted, trained, and *then* judged?
- **n** **Smoke scale only.** `prob_use` and `prob_emb` appear in the seven-arm smoke set; measured effect: they **retired 217 and 224 of 256 minted tokens**
- **RESULT** A structural negative worth keeping: **branching entropy cannot be the post-probation test**, because minting *destroys the evidence it reads* — greedy longest-match consumes a+b into the merged token, so the pair never occurs again. Measured: mint 't'+'h', read the pair count after forty more passes → **0**, and 0 at the instant of the merge. A re-test can only ever fail, and did: **0 kept, 8 un-merged, 100%**. The two tests that *can* see something after the merge are `use` (reach `TOK_PROBATION` appearances in `TOK_PROBATION_STEPS`) and `embed` (‖delta‖/‖composite‖) (`9f8412b`)
- **CONCLUDED** Entropy is a **pre-mint** criterion by nature, and that is where it already is. Retirement is soft, because ids are positional.
- **STANDS NOW** **The structural argument stands** (it is a proof about greedy longest-match, not a measurement). **The arms have never run at pilot scale** (§15), and the 217/224-of-256 retirement rate is a **smoke** number — at smoke `VMAX` is 256, so it says nothing about pilot behaviour except that the mechanism fires hard. `0f96784` also records that a `_due` double-call *"would have fired on the first `prob_use` or `prob_emb` run"* — i.e. the first real run of these arms would have hit a live bug, inert only because `TOK_PROBATION` defaults to 0.
- **ERA** mid

### X43 — A retok on an unchanged vocabulary
- **ARM / NAME** `frozen_8ep_clean` (`RETOK_EVERY=3000`) vs `frozen_nr_8ep_clean` (`RETOK_EVERY=0`), commit `25c37eb`
- **CONFIG** `TOK_MINT_UNTIL=1 SEED_VOCAB=512 VMAX=512` on both — **identical vocabularies**: 512 minted, 441 used, **0% dead**
- **QUESTION** With the vocabulary frozen, re-segmentation is provably a no-op on CONTENT (same tokens, same greedy longest-match, byte-identical stream). What does it cost anyway?
- **n** n=1 each, paired
- **RESULT** `frozen` **4.364**, 26% real words, best at step 2000 then **+1.533** past its minimum. `frozen_nr` **2.175**, **94% real words**, best IS final, still improving. **Difference 2.189 b/B.** `frozen` fired 23 retoks and **22 of them added zero tokens**; each still discarded the lookahead queue, dropped the held-out token caches, and blacked out fabric growth for `FAB_COOLDOWN` steps (`046fd81`)
- **CONCLUDED** *"That is the whole 2.189 b/B"* — quoted in source as **the largest single effect on record** and used to justify the retok guard (refuse a retok when nothing has been minted since the last one).
- **STANDS NOW** **`INV-10` — UNATTRIBUTABLE.** `79dac6c` found that **`RETOK_EVERY=0` also silently disabled signature batching**, so the two arms differ in **two** ways, not one. The effect is real; its size is not attributable to retok alone. Two further caveats: `frozen_nr_8ep_clean` (2.175) is the **best held-out in `runs.csv`** and is a 512-token vocabulary against `base`'s 2048 — and the retok guard built on this result immediately caused `E9`/`INV-09`, because `_due` records the step and returns True, so calling it twice in one `if/elif` consumed the event and **killed re-segmentation entirely** in the three 18-epoch runs at `04cbe89`.
- **ERA** mid

### X44 — TOKENIZER=0: the byte-level floor
- **ARM / NAME** `bytes` (`TOKENIZER=0`)
- **QUESTION** What is the floor — no minting, no re-tokenisation ever, and the only setting where bits/byte and bits/token are the same number so nothing can drift?
- **n** n=1 pilot, plus a toy
- **RESULT** Pilot: **4.378** (`be50e3a`), one of only two runs outside the 2.0–2.2 band and a deliberate control. Second-half slope: **5.46 → 4.34, −0.0354/10k — improving, from a level that loses to order-1** (`f9d676c`). Toy, same budget: bytes 4.720 | freeze 4.691 | mint 4.995–5.100 (`2946`-region commit), *"on a run far too short to mean anything"*
- **CONCLUDED** Kept as the cleanest available floor.
- **STANDS NOW** **Stands as a control.** Its main use is in `f9d676c`'s survey across **21 logs**: with all-run minting, **19 are FLAT or WORSE** (+0.0175 to +0.2170/10k) on both architectures, fabric and `FABRIC=0`, society, chaining and soc-loop — while the two settings where the vocabulary stops moving are the two that keep improving. That survey is n=21 logs and is one of the better-supported observations in the project, though it is a **survey, not a controlled comparison**.
- **ERA** pre-both

---

## §10. VMAX × EPOCHS

### X45 — The VMAX × EPOCHS 2x2
- **ARM / NAME** `vmax4k` (`VMAX=4096`) × `vmax8k` (`VMAX=8192`), at `EPOCHS=8` and `EPOCHS=18`
- **CONFIG** grid harness; arm flags last so they win (post-`5f4f117`, see `INV-41`)
- **QUESTION** Does a larger softmax width help or hurt, and is the "dead row" fraction the mechanism?
- **n** **n=1 per cell, 4 cells**
- **RESULT**

  | | EPOCHS=8 | EPOCHS=18 |
  |---|---|---|
  | **VMAX=4096** | 2.140 (0% dead) | 3.250 (0% dead) |
  | **VMAX=8192** | 3.561 (41% dead) | **4.383 (0% dead)** |

  `vmax8k@18ep` filled its vocabulary **completely** — 8192/8192, 0% never minted, 1.3% ordinary turnover — and is the **worst** of the four. 4.383 against a uniform anchor of 3.305 is ~4 bits/token worse than assigning equal probability to every token; 19% real words; the **only** run of any arm with a positive train/held-out gap (+0.267); the only one still rising at the end (+0.194 b/B per 10k through the second half); its loss bottomed at step 3935 and rose for the remaining 82,656 (`0279709`)
- **CONCLUDED** Two things at once. (a) **The dead-row hypothesis is falsified** and *"is removed rather than left standing: 0% dead produced the worst number here"*. (b) Two cells declared uncontaminated: `vmax4k@8` vs `vmax4k@18` = +1.110 (confounded by LR, see X31), and `vmax4k@18` vs `vmax8k@18` = **+1.133, "differ in VMAX ONLY"**, called *"the clean one"*.
- **STANDS NOW** **`INV-31` — UNATTRIBUTABLE, including the "clean" cell.** `0f96784`: `FROZEN = torch.randn(VMAX, D)` sat at module scope and drew `VMAX*D` numbers from the global generator **before anything else was built**, so changing `VMAX` re-rolled **every module**, including ones that are not VMAX-shaped. Verified directly on `enc.weight_ih` and the fabric centroids at 2048/4096/8192. *"Three runs 'differing only in VMAX' were three different random initialisations of the whole system."* Given the VMAX field spans 2.132–3.989 = 1.857 and a 0.05% perturbation once produced 1.594 (O09), *"the non-monotonic ordering needs no further explanation"*. **Part (a) survives**: the falsification of the dead-row story is not an attribution claim, and it is independently confirmed by X47.
- **ERA** mid (all `runs.csv` VMAX rows are pre-`c76dc74` and pre-`0f96784`, per `01_TIMELINE` Appendix A)

---

## §11. The population 2x2

### X46 — Size vs growth: the cleanest experiment in the project
- **ARM / NAME** arms A / B / C / D, commit `e9f2e58`, recorded as `popB_n2048_s{0,1,2}` and `popC_nmax64_s{0,1,2}` in `runs.csv`
- **CONFIG** A = `FAB_GROW=0 FAB_N0=3` (~6 experts) · **B = `FAB_GROW=0 FAB_N0=2048`** · C = `FAB_GROW=1 FAB_NMAX=64` · D = `FAB_GROW=1 FAB_NMAX=4096` (= HEAD's defaults). 8 epochs, `VMAX=2048`, pilot corpus
- **QUESTION** Is a large expert population bad, or is *ramping to* a large population bad? These had never been separated.
- **n** **n=3 seeds per arm, 4 arms, one knob apart — the largest properly-seeded design in the project**
- **RESULT**

  | arm | seeds | mean | spread |
  |---|---|---|---|
  | A `FAB_GROW=0, N0=3` (~6) | 2.047 2.315 1.989 | 2.117 | 0.326 |
  | **B `FAB_GROW=0, N0=2048`** | 1.998 1.960 2.040 | **1.999** | **0.080** |
  | C `FAB_GROW=1, NMAX=64` | 2.163 2.127 1.983 | 2.091 | 0.180 |
  | D `FAB_GROW=1, NMAX=4096` | 4.327 3.572 2.253 | 3.384 | 2.074 |

  Read along the axes: growth OFF, 6→2048 experts: 2.117 → 1.999 (**a large population is fine**). Growth ON, 64→4096: 2.091 → 3.384 (**a large population is fatal**). At 4096, growth OFF vs ON: 1.999 → 3.384 (**the entire effect**). Fabric contribution: +0.225/+0.293/+0.106 in B, against +0.022/+0.001/−0.006 in C and a meaningless +6.183 in D seed0 *"where it is only large because the base model it is compensating for reads 10.338"* (`cc0a377`)
- **CONCLUDED** *"It is the interaction, not either term. RAMPING to 4096 is what destroys the base model"* — the ramp injects ~4000 mutated clones into the path between the base representation and the loss over ~600 steps, and HALT mass is 0.0000 so the base head has no direct path out. **"B IS THE BEST ARM ON RECORD"**, spread 0.080 against 2.074 for the current default; seed1's 1.960 *"is the single best number this project has produced"*. *"For the first time a configuration is reproducible enough that a 0.1 b/B difference between two arms would mean something."*
- **STANDS NOW** **`INV-15` — DEGRADED + NOT REPRODUCIBLE AT HEAD.** `91fd815`/`a5cc7ea` (`E14`) found `s.born` was written only by `grow()`, so founders read as age 0 forever and `soft_cull` skips anything inside `FAB_GRACE` — meaning **arm B, all founders, ran with zero culls for its entire life**. Measured directly: same config and seed, **before 0 culls, after 6 culls, population 24 → 8**. The number stands **as measured**, but it measures a population **under no selection**, and the fix is now in. **Re-run arm B, or pin the reproducing config, before comparing anything to it.**
  Two further notes: the **structure** of the 2x2 (the interaction, not either term) is not touched by `INV-15` and is the most durable architectural finding here; and `f8599b7` records that HEAD's fabric defaults (`FAB_GROW=1, FAB_N0=3, FAB_NMAX=4096`) **are arm D** — the arm that measured mean 3.384, spread 2.074.
  Also `08_GLOSSARY` §1.4: `FAB_GRACE` changed units at `9146136` (3000 **steps** → 48 **selections**), so any grace figure in a pre-08-15 message is in steps.
- **ERA** post-both (pre-`E14`, pre-`E15`)

---

## §12. Dead rows, controlled

### X47 — LOSS_MASK_DEAD: the first controlled test of the dead-row story
- **ARM / NAME** `LOSS_MASK_DEAD` — unmasked / masked-at-the-loss-only / masked-everywhere
- **CONFIG** same seed, same config, one knob; a configuration with **86.7% of the width never minted**
- **QUESTION** Ids between the live vocabulary and `VMAX` index no byte sequence and can never be a target, yet take mass off tokens that can occur. Is masking them the correct denominator — and is the "dead rows are catastrophic" curve real?
- **n** n=1 per arm, 3 arms, with per-window SEs
- **RESULT** unmasked **4.746 ± 0.043** · masked at the loss only **6.100 ± 0.074 (worse)** · masked everywhere **4.686 ± 0.034**. So the controlled effect is **+0.060 against a combined SE of 0.055 = 1.1σ** (`e9f2e58`)
- **CONCLUDED** *"a hint, not a finding."* And the placement error is instructive: masking at the loss only is **worse** than not masking, because the model is never taught to push the dead rows down while every eval path still scores it with them in the denominator.
- **STANDS NOW** **Stands, and it is the entry that converts `INV-34` from a claim into a retraction.** *"The 'dead rows are catastrophic and monotone' curve this repo has been quoting (0% → ~2.2, 41% → 3.561, 75% → 6.114) came from comparing arms that differed in far more than their dead fraction, measured through the instrument that was editing runs. This is the first CONTROLLED test of it... and it does not reproduce that magnitude. It is not established, and I have been repeating it as though it were."* Left **off by default** deliberately, *"because it changes every number, and it should be adopted as a measured arm rather than assumed"* — so it is a knob with a controlled result and no adoption.
- **ERA** post-both

---

## §13. Continual learning

Cross-reference `06_CONTINUAL_LEARNING.md`; only the experimental facts are here.

### X48 — The pilot → pilot-add chain, executed for the first time
- **ARM / NAME** `longrun.sh pilot` → `longrun.sh pilot-add`
- **QUESTION** Does the path that produces the forgetting number actually run end to end? (It never had.)
- **n** n=1
- **RESULT** `eng` was 5.171 @ step 172 → now **4.466, −0.706 ± 0.162, better**. `py` 4.680 ± 0.093, NEW (`61b9d23`)
- **CONCLUDED** Stated immediately as **not** a continual-learning result: *"the baseline was 172 steps and so undertrained that continued training helped more than a second domain hurt."* What it establishes is that the measurement fires, spans the run boundary, keeps old and new apart, and carries an error bar.
- **STANDS NOW** **Stands, as a plumbing verification and nothing more** — correctly labelled at the time, which is why it needs no invalidation. Note `INV-03`/`E3`: before `a5ac033` (07-28) `PHASED=0` had never once run, so *"a stationary i.i.d. splice does not require continual learning"*.
- **ERA** pre-both

### X49 — The one real continual-learning run
- **ARM / NAME** `continual_eng_py`, commit `b92f358`
- **CONFIG** RESUME from `nogrow_s2` (English, held-out 1.989) + Python from the-stack, under `PHASE_SCHED [[0],[0],[1],[1]]` — English **absent for the second half of every epoch, eight times**, and the run ending on a Python-only phase
- **QUESTION** Does English survive while Python is learned?
- **n** **n=1**
- **RESULT** `eng` was 1.998 @ step 48157 → now **2.050, +0.052 ± 0.075, HELD**. `py` 2.276 ± 0.086, NEW. Combined held-out 2.243, beating order-1 (3.644) by +1.402. The **ABSENT column has data for the first time**: **+0.116 b/B per 2000 steps while active against −0.029 while absent** — *"about four times faster than it forgets"*, and English recovers rather than ratcheting (worst 2.19 during an early absence, back to 2.00 by the end) (`a9d7258`)
- **CONCLUDED** *"Where the retention came from is not where the design assumes."* **Every English memory entry was EVICTED** during the Python phases (the faded-process unlearn test skipped itself: 0 entries left), yet English held — so the **weights and the fabric** carried it. The fabric carried **+0.373 b/B with six experts**, the largest fabric contribution in the record, from the smallest population, *"while the ramp elsewhere tries to build 4096"*. Memory went **negative (−0.111)**.
- **STANDS NOW** **Two invalidations, both partial.** **`INV-25` — DEGRADED**: `holdout_bpb` calls `_eval_logits`, which **does not consult memory**, so ACROSS THE RUN BOUNDARY — *"the ONLY number that spans the run boundary"* — is a **weights-only** retention figure (`f8599b7`). That is consistent with every English memory entry having been evicted, but it is not what the line's wording implies. **`INV-43` — PROVENANCE DEGRADED**: `pilot-add` never created `$OUT`, so `tee` wrote to a closed pipe — **hours of GPU, a valid checkpoint, no log**. The `runs.csv` numbers are **hand-transcribed from a terminal copy**. `holdout.py` can reconstruct the boundary figure from the checkpoint if it survives.
  Also **`INV-24`**: `mem.read()` was called only from eval-only paths, so `use` stayed 0 and every path evicted by write order whatever `EVICT` said — that is the mechanism behind the vanished English domain here.
  **n=1, no log.** The single most important run in the project is the one with the weakest provenance.
- **ERA** post-both (pre-`E14`, pre-`E15`)

---

## §14. The noise floor, and determinism

These are experiments **about the instrument**, and they are the reason so much else is void.

### X50 — Seed spread, measured for the first time
- **ARM / NAME** paired pilots at SEED=0 and SEED=1, commit `c33f078`
- **QUESTION** How large is seed variance, relative to the architecture differences being claimed?
- **n** **n=2 seeds × 2 arms**
- **RESULT** society **2.067 / 2.007, spread 0.060** · chained society **2.101 / 2.275, spread 0.174** (`6bd226c`)
- **CONCLUDED** *"The four best architectures in this project sit inside 0.06 b/B of each other. Seed spread on one arm reaches 0.174. A single run cannot rank two arms."* Two claims **withdrawn in the same commit**: *"SPECIALIZATION 0.132, the highest recorded, and emergent"* → **0.009 at seed 1**; *"the only arm whose curve is flat, −0.007"* → **+0.298 at seed 1**. What survives two seeds: society ahead on both, and the LR effect far outside spread.
- **STANDS NOW** **Stands**, and is superseded only in magnitude by X33 (1.227). Feeds `INV-35`.
- **ERA** pre-both

### X51 — Determinism given (config, commit, seed)
- **ARM / NAME** three identical-config pilots; `nogate` vs `base`; `equiv.sh`
- **QUESTION** Is the noise seed variance specifically, or run-to-run jitter?
- **n** three byte-identical pilots (`6bd226c`); `base_8ep_pilot2` vs `nogate_8ep_pilot2` **byte-identical, same final step 48133** (`b6952da`); `equiv.sh` across commits (`c14f876` vs `37ecb20`)
- **RESULT** Deterministic on CPU given (config, commit, SEED).
- **CONCLUDED** So the spread in X50/X33 is **seed variance**, and n seeds of one arm is the only way to see it.
- **STANDS NOW** **Stands — and it is on `05_ERRORS`'s short "what survives" list.** `bdce727` adds the necessary caveat: *"reproducing a config is not the same as attributing a difference between two configs."* `equiv.sh` later needed its own noise baseline *"because the GPU is nondeterministic in exactly one subsystem"* (`c6f54e6`).
- **ERA** X50/X51 span pre-both through mid

### X52 — The post-instrument-fix seed floor
- **ARM / NAME** `seedfloor_s{0,1,2}` and `nogrow_s{0,1,2}`, commit `451459d`
- **CONFIG** 8 epochs, `VMAX=2048`, pilot corpus; `nogrow` = `FAB_GROW=0 FAB_N0=1024`
- **QUESTION** What is the noise floor **after** `c76dc74`?
- **n** **n=3 seeds per arm**
- **RESULT** `seedfloor` **4.327 / 3.572 / 2.253** (spread **2.074**) · `nogrow` **2.047 / 2.315 / 1.989** (spread **0.326**) (`runs.csv`, with per-row `held_out_se` populated for the first time: 0.038–0.120)
- **CONCLUDED** The default configuration's own three-seed spread is **2.074 b/B** — larger than any architectural difference in the record. `nogrow`'s 0.326 is nearly an order of magnitude tighter.
- **STANDS NOW** **Stands**, and these two rows are arms A and D of X46 measured a day earlier. This is the measurement that made X46 interpretable: *"Next measurement to make is the noise floor itself — seeds, with checkpoints — not another arm"* (`33a9299`) was acted on.
- **ERA** post-both

---

## §15. Component contributions

### X53 — FABRIC: eval-time knockout vs retrained ablation
- **ARM / NAME** `FABRIC=0` vs `FABRIC=1`; then `nofabric` as a **retrained** arm
- **CONFIG** English, 120 kB, everything else identical
- **QUESTION** What is the routed expert population worth? (Context: `7a42f90` had just found **`FABRIC` defaulted to 0 in every run of the project** — `E3`, `INV-02`.)
- **n** n=1 per arm, both times
- **RESULT** Knockout: `FABRIC=0` **3.543**, loses to order-1 (3.495) by 0.048; `FABRIC=1` **3.441**, beats it by 0.054; *"fabric contributes **+0.709** bits/byte (3.905 → 3.196), four times what the memory contributes"* (`7a42f90`). **Retrained ablation: 3.089 vs 3.090 — no bits/byte at all** (`e60b8e0`)
- **CONCLUDED** At the time: *"the largest single component effect measured in this project"*, and it **flips the sign of the comparison against a bigram table**. Defaulted ON. The commit's own caveat: at these settings the router HALTs 90% and mean routed depth is 0.10 of 4, *"so +0.709 is the population being PRESENT, not the routing working"* — and that HALT figure is itself `INV-40`.
- **STANDS NOW** **`INV-36` — VOID.** An **eval-time knockout of a component the model trained with** is not a retrained ablation. `e60b8e0` states the retrained comparison (3.089 vs 3.090) and names the error: *"Using the knockout number (+0.709) to justify defaulting FABRIC ON was exactly that mistake."* `9d90416` then retracted the claim from `rerun.sh`'s header. The **fallback** justification offered at the time — coherence 0.75 vs 0.50 — is **`INV-20`**, a four-sample mean with SE 0.25. So the default was justified twice and both justifications are void.
  The two `runs.csv` rows `fabric_off` (3.543) / `fabric_on` (3.441) encode this comparison, carry **no commit and no date**, and per `01_TIMELINE` Appendix A their era **cannot be resolved from `runs.csv` alone** (the order-1 3.495 dates them to the 07-29 run, i.e. pre-both).
- **ERA** pre-both

### X54 — Memory: global store vs per-expert partition
- **ARM / NAME** `MEM_PER_EXPERT=0` vs `=1`
- **CONFIG** same seed, same config, only the store differs: global 200k slots vs 32 owners × 64
- **QUESTION** What does compartmentalising memory writes per expert cost?
- **n** n=1 paired
- **RESULT** global: memory contributes **−0.097** b/B · 32 owners × 64: **−0.652** b/B. **The partition costs 0.555 b/B** at the scale tested. Separately: *"memory is already slightly net-negative even with the global store"* (`242e021`)
- **CONCLUDED** Default OFF, on measurement.
- **STANDS NOW** **`INV-06` — DEGRADED → UNATTRIBUTABLE, and the reason is the worst kind.** `e25d9b5` (`E15`, 08-15) found the code read `_i("MEM_PER_EXPERT", 1)` against a comment saying DEFAULT OFF — **so every run in this project used the partitioned store**, the one measured at −0.555. See `08_GLOSSARY` §1.7. The decision recorded here was never the decision that ran.
  Compounding it: **`INV-23`** (`mem.ctx` queried in a segmentation it was not written in — **82.3%** of stored contexts no longer matched after ONE growth step, where a pilot does about sixteen) and **`INV-24`** (`mem.read()` called only from eval-only paths, so eviction ranked a constant). **Every "memory contributes X" figure in the project is downstream of all three.**
- **ERA** pre-both

### X55 — DIV_W: twenty minutes of GPU that measured nothing
- **ARM / NAME** `divw` (`DIV_W=0.05`)
- **QUESTION** Does a distinctness penalty produce specialization?
- **n** n=1
- **RESULT** **Byte-identical to the `DIV_W=0` run in every figure**: held-out 2.893, order-1 +0.545, since-min +0.683, H(hop1|hop0) 0.533, specialization 0.000, top expert 25.2%, 424 distinct experts (`b14d60e`)
- **CONCLUDED** The soc-loop branch **returns before the transition path's distinctness term**, so the flag did nothing. *"Twenty minutes of GPU time measured the previous configuration."*
- **STANDS NOW** **`INV-44` — VOID; it is a duplicate of the `DIV_W=0` run.** The important part is the third failure mode it exposed: **the config audit certified `DIV_W=0.05` as correct**, because it verifies a knob's *value* was read and matches the live object — it **cannot see whether the code path that uses it was ever reached**. Auxiliary loss terms now report whether they actually fired. *"A value can be wrong (banner), unread (typo), or read-but-unreachable (this). Each needed its own check because each is invisible to the others."*
  Note this also means the `divw` row in the 18-arm grid (X24, held-out 2.324) is suspect for the same reason — see `08_GLOSSARY` §1.5 on knobs gated on `SOCIETY`.
- **ERA** pre-both

### X56 — GRU vs transformer
- **ARM / NAME** `PILOT_ARCH="gru transformer"`
- **CONFIG** transformer at d768, L4, 8 heads, causal, on the identical stream
- **QUESTION** Is the bits/byte level the architecture or the system?
- **n** n=2 pilots per architecture
- **RESULT** GRU **2.064 / 2.200** vs transformer **2.130 / 2.184**; coherence 0.17 vs 0.02. `longrun.sh` concluded *"the architecture question is ANSWERED... Running both again costs an hour and buys nothing."*
- **STANDS NOW** **`INV-33` — VOID.** `bf53d40`: both transformer runs were **under `FAB_GROW=1` to 4096 experts, before the instrument fixes**, and both carry the broken-base signature the 2x2 later explained — **model ALONE 4.680 and 4.952, with the fabric compensating by +2.625 and +2.801**. *"That is arm D seed0 exactly."* So the transformer has **never been evaluated in a configuration where the base model survives**, and the four held-out numbers are within seed spread of each other anyway (`INV-35`). The coherence half (0.17 vs 0.02) is **`INV-20`**.
  `longrun.sh` at HEAD still carries the "answered" comment **and** the correction; the correction is right.
- **ERA** pre-both

---
---

# PART II — INCIDENTAL OBSERVATIONS

Numbers that came out of runs done for **another** reason and were then quoted as findings. This is
where the over-claiming happened, and it is why the two categories are separated. **14 of the 16
below are on the invalidation list.**

| # | The observation, as stated | Where it came from | Status |
|---|---|---|---|
| **O01** | *"FABRIC alone is worth +0.709 b/B"* — used to default `FABRIC` ON | an eval-time knockout printed by the report of the 07-29 subsystem-audit run, not an ablation anyone designed | **`INV-36` VOID.** Retrained: 3.089 vs 3.090. See X53. |
| **O02** | The dead-row series *"0% → ~2.2, 41% → 3.561, 75% → 6.114"*, quoted repeatedly as monotone and catastrophic | three arms run for three different reasons, compared after the fact on one column of the `[vocab]` line | **`INV-34` UNCONTROLLED → NOT ESTABLISHED.** First controlled test: +0.060 vs SE 0.055 = 1.1σ. See X47. |
| **O03** | *"Best at ~step 6000, identical in every arm at every seed"*; *"the final model is 1.1–1.3 b/B worse"* | the learning-curve panel of every run | **`INV-18` VOID.** `_VALT` cached the held-out text in an obsolete segmentation and was never invalidated — *"the yardstick was moving, not the model"* (`E7`). **End-of-run** held-out figures re-tokenise first and are unaffected. |
| **O04** | *"1 of 4096 experts used"* — and four router fixes built on it | a **32-window eval probe** read as if it were the run | **`INV-17` VOID.** Whole-run: 84 distinct experts, top 3.9%, half the traffic to 21. |
| **O05** | *"Memory now HELPS coherence (0.50→0.75)"*; *"the fabric buys coherence (0.75 vs 0.50)"*; *"memory HURTS coherence (0.75→0.50)"* | the COHERENCE line of three different runs, on three separate turns | **`INV-20` VOID — all three**, including the one that justified a default. Coherence was a **four-sample mean with SE 0.25**; every value landed on 0.25/0.50/0.75/1.00, so each claim was one sample flipping. |
| **O06** | *"91% of generated words appear in the training text"* vs 71% vs 31% | the composing check, scored on **64–91 words** from **one 200-token sample** | **`INV-21` VOID as a comparison.** The `words_pct` column in `runs.csv` is post-`c14f876` and stands. |
| **O07** | *"Memory contributes +0.698"* | the report battery of runs done for other purposes | **`INV-23` VOID.** `mem.ctx` was queried in a segmentation it was not written in; **82.3%** of stored contexts stopped matching after one growth step. |
| **O08** | *"The weight-prediction term is 2% of the routing decision"* — and `ROUTE_REGION_W`, built on it | a **64-expert toy** | **`INV-27` VOID — direction was wrong.** At 4096: 7% region / 93% weight-prediction; `FAB_KEY_NORM=1` **reduces** it (41/59). Owned in `ffd39b8`: *"it was wrong because I measured it at a scale the user had already told me was unrepresentative."* |
| **O09** | *"A diagnostic's sampling frequency changed the model by 1.594 b/B through accumulation"* | two runs with byte-identical code and the same seed differing **only** in whether `SAVE_CKPT` was set: **3.694 vs 2.100** | **`INV-12` DEGRADED.** The **difference is real**; the **attribution was wrong** — ~125 centroid nudges against ~240,650 from training is 0.05% and cannot accumulate to that. It stands as evidence of **chaotic sensitivity**, which is arguably the more alarming reading. |
| **O10** | *"Domain assembly works, purity 0.54 → 0.96"* | the clustering panel across the 07-25 campaign | **`INV-16` VOID — explicitly retracted** in `5e02cfc`. Purity rises **monotonically with fragmentation**; measured elsewhere, purity 1.00 at 1431 clusters with completeness 0.18. The assembler was producing **one domain per splice segment** (96 domains against 89–96 segments). |
| **O11** | *"Doubling a FULL vocabulary costs +1.133 b/B"* — the one cell of the VMAX 2x2 declared clean | X45 | **`INV-31` UNATTRIBUTABLE.** `VMAX` re-rolled every weight in the system. |
| **O12** | *"SPECIALIZATION 0.132, the highest recorded, and emergent"*; *"the only arm whose curve is flat, −0.007"* | the cosine arm of X30, a run about the LR schedule | **`INV-35` VOID.** At seed 1: **0.009** and **+0.298**. Withdrawn by their own author in `6bd226c`. |
| **O13** | *"`MODEL=transformer` has never been run here"* | a comment in `longrun.sh` | **`INV-33` VOID** — it had run twice. See X56. |
| **O14** | The `rampfrom2048_s{0,1,2}` runs, recorded as a test of `GROW_CAP` / `LOSS_MASK_DEAD` | six knobs set on a build that predated all of them; every one ignored | **`INV-19` RELABELLED.** Valid as a **ramp 2048→4096** measurement (1.994 / 2.097 / 1.937), void as a `GROW_CAP` test. *"Worth having, just not what was asked for."* |
| **O15** | *"Unlearning is surgical and local"* | the unlearn panel, measured on **ACTIVE** material only | **`INV-26` VOID** as a claim about faded material — under a non-stationary stream the bounded store had already evicted it, so *"deleting what the bounded store has already evicted is a no-op"*. |
| **O16** | *"COMPETENCE PROTECTION spared 0"*, reported as a puzzle for several rounds | the fabric panel | **`INV-14` VOID.** The fabric had **no culling at all** — `router.manage` is gated on `EXPERTS`, mutually exclusive with `FABRIC`. The protection was wired into a path that never executes. |

**The pattern.** Twelve of these sixteen came from a **report line that a run printed anyway**. The
project's report battery has ~14 sections and prints dozens of figures per run; each one reads as a
measurement, and none of them was designed as one. `9d90416` is the commit that names the disease —
domain counts, purity, silhouette, V-measure and specialization are **DIAGNOSTICS, NOT TARGETS** —
and it did not stop O01–O16 from continuing to happen afterwards.

---
---

# PART III — THE ARM INVENTORY

**Open question from `DOC_PLAN.md`: which of the arms in `longrun.sh` `_flags_for` have EVER been
run at pilot scale?**

**First, a count correction.** `DOC_PLAN.md` says *"46 arms, lines ~129–275"*, written against
`a5cc7ea`. At HEAD (`38b02ae`) `_flags_for` defines **52 arms**, lines 127–279. `b6952da` (08-12)
also says *"an audit of all 46 arms"*. Six were added after that audit — `frozen1k`, `frozen2k`
(`a21a721`), and the `nocompose`/`compose`/`mintnovel`/`composenov`/`noanchor`/`bigpop` group minus
the two that already existed (`d79c4ba`). **Use 52.**

"Pilot scale" here means the `pilot`/`grid` configuration — 4 MB/epoch × 8 epochs, `D_MODEL=768`,
`WIN=256`, `BATCH_W=16`, ~48k steps — i.e. a run that produced a held-out figure comparable to the
rest of this file. Smoke (~40 kB), toy (~400 steps) and CPU rerun scales do **not** count, and are
noted where they exist.

## Run at pilot scale — 29 of 52

| arm | evidence |
|---|---|
| `base` | `runs.csv` ×5, the 18-arm grid, the 6-arm pilot |
| `weights` `nofabric` `balance` `frozvocab` `softroute` `keynorm` `divw` `smallpop` `curric` `society` `stateq` `wt_bal` `wt_div` `nomem` `chainsup` `explore` `kitchen` | the 18-arm grid at `ffd39b8` — *"18/18 arms trained"* (X24). `frozvocab` ran and **went NaN from step 20000** (`INV-28`); `divw` ran and measured nothing (`INV-44`) |
| `frozen` `frozen_nr` `drop` `wdecay` `reg` | the 6-arm `pilots` preset at `707f1af` (X37); `runs.csv` rows for the first two; uploaded logs for all five |
| `vmax4k` `vmax8k` | `runs.csv` ×5 each (X45) |
| `nogate` | `runs.csv` `nogate_8ep_pilot2` (X41) |
| `nogrow` | `runs.csv` `nogrow_s{0,1,2}` (X52) |
| `freeze6k` | `TOK_MINT_UNTIL=6000` pilot, held-out 2.189 (X36) |
| `bytes` | `TOKENIZER=0` pilot, held-out 4.378 (X44) |

## NEVER run at pilot scale — 23 of 52 → **for `07_WIP.md`**

| arm | flags | what exists instead |
|---|---|---|
| `base_nr` | `RETOK_EVERY=0` | **Nothing.** Question posed in the arm's own comment — *"does re-segmenting mid-epoch earn its side effects on a GROWING vocabulary?"* — and never answered. X43 answered it only for a **fixed** vocabulary. |
| `vote` | `CHAIN_VOTE=1` | toy only: 5.191 (X27) |
| `socloop` | `CHAIN_ROUTE=soc CHAIN_VOTE=1` | toy only: 4.918 (X28). The **configuration** reached pilot scale by becoming the default at `53fbae5`, but never as a controlled arm. |
| `socloop_w` | `+ ROUTE_REGION_W=0 FAB_KEY_NORM=1` | toy only: 4.925, H(hop1\|hop0) 0.270 (X28) |
| `vote_w` | `CHAIN_VOTE=1 ROUTE_REGION_W=0 FAB_KEY_NORM=1` | exit-0 verification only |
| `vote_soc` | `CHAIN_VOTE=1 FAB_STEPS=1` | exit-0 verification only. Designed to separate DEPTH from the BLEND RULE — the isolating arm of §6, unrun. |
| `noban` | `CHAIN_BAN=0` | exit-0 verification only |
| `nolatch` | `FAB_RAMP_LATCH=0` | exit-0 verification only. Restores the never-terminating ramp; the latch's effect was measured **only** inside X24. |
| `frozen1k` | `TOK_MINT_UNTIL=1 SEED_VOCAB=1024 VMAX=1024` | added `a21a721` (08-11). Earlier defective form ran at 50% dead rows — `INV-42`. |
| `frozen2k` | `TOK_MINT_UNTIL=1 SEED_VOCAB=2048 VMAX=2048` | added `a21a721`. **This is the arm that separates "fixed vocabulary" from "tiny vocabulary"** — at `frozen`'s 512, the model has almost no whole-word units and spells everything (3.07 tokens/word vs base's 2.52). Until it runs, every frozen-vs-growing comparison in §9 confounds the two. |
| `mintinit` | `WARMSTART_MODE=last/first` | X39's 18-trial result, and one contradicting toy. *"The pilot decides."* It never ran. |
| `pgate_t` | `TOK_MINT_PMIN=0.15` | smoke only |
| `pgate_c` | `TOK_COMPOSE=1` | smoke only |
| `prob_use` | `TOK_PROBATION=200` | smoke only (retired 217/256) |
| `prob_emb` | `TOK_PROBATION=200 TOK_PROBATION_BY=embed TOK_COMPOSE=1` | smoke only (retired 224/256) |
| `nocompose` | `TOK_COMPOSE=0 TOK_MINT_NOVEL=0` | **Nothing.** |
| `compose` | `TOK_COMPOSE=1 TOK_MINT_NOVEL=0` | smoke only |
| `mintnovel` | `TOK_COMPOSE=0 TOK_MINT_NOVEL=0.5` | toy only (6.034 vs 5.764, called *"meaningless here"*) |
| `composenov` | `TOK_COMPOSE=1 TOK_MINT_NOVEL=0.5` | **Nothing.** Reproduces `pilot_gru_8`. |
| `noanchor` | `TOK_COMPOSE=1 TOK_ANCHOR=0 TOK_MINT_NOVEL=0` | **Nothing.** Note `fec2285`: `TOK_ANCHOR=0.05` printed on the EFFECTIVE line of **every run in this project while contributing nothing**, because it is gated on `TOK_COMPOSE`. |
| `bigpop` | `FAB_NMAX=16384` | **Nothing.** Designed to test whether the turn at ~step 36k tracks hitting the **cap**; X46 has since offered a different answer (the ramp, not the cap). |
| `freeze20k` | `TOK_MINT_UNTIL=20000` | toy only |
| `nogrow_s` | `SOCIETY=1 FAB_GROW=0 FAB_N0=1024` | **Nothing.** `nogrow` ran; the single-round-society variant did not. |

**Notes for the `07_WIP.md` agent.**
1. `nocompose` / `compose` / `mintnovel` / `composenov` / `noanchor` are the **2x2 plus anchor** that `d79c4ba` built specifically to de-confound `pilot_gru_8`, the run that scored 5.360 and is the sole evidence against `TOK_COMPOSE`. **The de-confounding experiment was designed, built, presetted (`grid ablate`, `grid tokens`) and never run.** That is the single largest designed-and-unrun block.
2. `frozen2k` is the highest-value unrun arm per unit of GPU: it is the control the entire frozen-vocabulary argument (X36, X37, X43) has been missing.
3. `prob_use` / `prob_emb` carry a live hazard: `0f96784` records that a `_due` double-call *"would have fired on the first `prob_use` or `prob_emb` run"* — inert only because `TOK_PROBATION` defaults to 0. It is fixed, but the arms have still never run.
4. All 23 would run **post-`c76dc74`** and post-`E14`/`E15` if run today, so they would be the first arms in the project measured through a clean instrument.

---
---

# PART IV — RESOLVED: does `runs.csv`'s `held_out` describe the FINAL model or `.best`?

**Answer: the FINAL model, in every row. No column in `runs.csv` carries the `.best` figure.**

The chain, read out of the source rather than inferred:

1. **What `runs.py` parses.** `runs.py:71-72` reads `held_out` off the line
   `train X +/- a | held-out Y +/- b`:

       row["held_out"] = _grab(r"train [\d.]+(?: \+/- [\d.]+)? \| held-out ([\d.]+)", t)

2. **What emits that line.** `self_organize.py:5934`, inside the `=== MEMORIZATION CHECK: train vs
   HELD-OUT ===` block, which begins at line 5901 with `model.eval()` and scores **the live
   in-memory `model`** — after training has finished and after the final `_save_ckpt(stream)` at line
   5876. Nothing reloads `.best` before it. It is a mean over at most `min(24, EVAL_N)` windows of
   `WIN=256` tokens per domain, ~15 kB of text; its own comment calls it *"the number every arm in
   this project has been compared on."*

3. **Corroboration in the same parser.** `runs.py:63` reads the `steps` column from
   `SAMPLED FROM: the FINAL model, step (\d+)` — the parser is keyed to a line that says **FINAL**
   in its literal text.

4. **Where `.best` actually lives.** `3f67bfc` (08-05) added best-tracking. `_best_bpb` is updated at
   `self_organize.py:4761-4770` from `_CURVE`, the **mid-run learning-curve** samples, and writes
   `<SAVE_CKPT>.best`. It is reported **only** in the GENERATION section (`6983-6999`), as prose:
   *"SAMPLED FROM: the FINAL model, step N ... NOT the best. Best was B at step S."* **`runs.py`
   never parses it.**

**Three consequences that matter for reading the tables:**

- **`.best` and `held_out` are not even the same measurement.** `_best_bpb` tracks the **curve**
  (per-process held-out samples during training); `held_out` is the **end-of-run memorization
  check**, which re-tokenises first. They disagreed by **1.6 b/B** on `base_5` (`E9`: curve 3.764 vs
  check 2.182). This is also why **`INV-18` voids the curve-derived claims but explicitly spares the
  end-of-run figures**: *"The end-of-run held-out figures re-tokenise first and are unaffected."*
  Since `runs.csv` carries only the end-of-run figure, **`runs.csv` is on the right side of `INV-18`.**
- **The `past_min` column is the final-vs-best gap.** `runs.py:78` parses
  `([+-][\d.]+) since its own minimum` from `self_organize.py:6208`, the UNIT-STABLE CROSS-CHECK. So
  every row already states how far the final model is past its own curve minimum: `+0.000` on **19
  of the 42 rows** (final **is** best), up to `+3.219` on `frozen_8ep_75pct_dead`.
- **The "final is 1.1–1.3 b/B worse than step 6000" claim is dead, and the tracking is what killed
  it.** `self_organize.py:4755-4760` and `bdce727` both record it: once the LR schedule read a
  horizon the run reaches and eval passes stopped moving the routing centroids, **five of six arms
  in the 6-arm pilot ended at `+0.000 since its own minimum`**. The exception was `DROPOUT` +
  `WEIGHT_DECAY` together (`reg`), still diverging at **+1.216**.

**Practical rule:** every `held_out` in `runs.csv` and in `04_RESULTS.md` is a **final-model,
end-of-run, re-tokenised** number. If a row's `past_min` is `+0.000`, final and best coincide; where
it is large, a `.best` checkpoint may exist on disk **only if that run had `SAVE_CKPT` on** — and
several deliberately did not (`GRID_CKPT=0`), because checkpointing gates extra `holdout_bpb` passes
and mixing the two modes is what produced the 3.694-vs-2.100 pair (O09).

---
---

# TALLY

**56 genuine experiments** (X01–X56) and **16 incidental observations** (O01–O16).

## Genuine experiments, by what happened to the conclusion

| status | count | which |
|---|---|---|
| **Stands as concluded** | **26** | X01 (narrowed), X02, X03, X04, X05, X08, X09, X10, X11, X12, X17, X18, X19, X20, X21, X22, X23, X26, X30, X32, X40, X41, X44, X48, X50, X51 |
| **Stands only in part** — the mechanism survives, the number or the ranking does not | **11** | X06, X13, X24, X28, X31, X35, X42, X45, X47, X52, X55 |
| **Superseded by a later, better measurement** | **4** | X07→(unmeasured), X15→X17, X27→X28, X36→X37 |
| **INVALIDATED / UNATTRIBUTABLE — the conclusion does not stand** | **15** | X14 (`INV-37`,`INV-05`), X16 threshold (`INV-37`), X25 claims (`INV-40`), X29 curric (`INV-08`), X33 (`INV-35`), X34 raw (`INV-32`), X37 provenance (`INV-42`), X38 attribution, X39 (unconnected), X43 (`INV-10`), X46 (`INV-15`), X49 (`INV-25`,`INV-43`), X53 (`INV-36`), X54 (`INV-06`), X56 (`INV-33`) |

**Roughly half the genuine experiments still support the conclusion drawn at the time; the other
half were narrowed, superseded or voided.** The ones that survived cleanly cluster hard into two
kinds: **bit-exact equivalence A/Bs** (X08–X12) and **experiments that shipped with their own null**
(X20, X21, X22, X23). Every experiment in this file that carried a pre-specified control or
permutation null still stands. Almost every one that did not, does not.

## Incidental observations

**14 of 16 are VOID, UNATTRIBUTABLE or RELABELLED.** The two that survive do so in weakened form:
O09 stands as evidence of **chaotic sensitivity** rather than accumulation (`INV-12`), and O14 stands
**relabelled** as a ramp-from-2048 measurement (`INV-19`).

**This is the file's central finding about its own subject matter:** a number that was designed to
answer a question survived about half the time; a number that merely appeared in a report survived
about an eighth of the time.

## What this file does not establish

- **No arm ranking.** `INV-35` voids every single-run architecture comparison in the branch, and
  the seeded ones (X46, X52) predate `E14`/`E15`.
- **No claim about the world model.** `INV-39` — unmeasured since 2026-07-29, and it defaults ON.
- **No claim about memory.** `INV-06`, `INV-23`, `INV-24` between them make every memory
  contribution figure unattributable.
- **No claim about continual learning beyond n=1**, from a run whose log was lost (`INV-43`).
- **Nothing about 23 of the 52 arms**, which have never been run at all.
