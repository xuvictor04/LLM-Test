# Continual-learning testbed — editable-memory thesis

An autonomous continual-learning system with a three-part loop, tested on one **unlabeled** byte stream that
secretly switches between latent processes:

    self-ASSEMBLE domains (C)  ->  detect WRONG info (B)  ->  EDIT / unlearn by provenance (A)

Byte-level by default (vocab = 256, raw UTF-8 bytes); an optional **expanding subword tokenizer** is available via
`TOKENIZER=1` — an online byte-BPE that GROWS its vocabulary by mint-on-repetition (byte-grounded, lossless; can also
un-merge stale tokens via `retire_stale`). Improves textual output (word-pieces instead of character salad). Entry points:

    bash run_full_unfrozen.sh    # WHOLE system, unfrozen, one run (mechanics + product loop) -> ~/full_unfrozen.txt
    python3 cl_bench.py          # MECHANICS only: forgetting, editability, drift, wrongness
    python3 self_organize.py     # PRODUCT LOOP only: assemble -> detect-wrong -> perform -> compose -> generate -> edit

(The old `control.py` entry point is retired to `legacy/`. The Barry/Greg language-model architecture also lives in
`legacy/` — this testbed is the current, separate design.)

## The three parts and their status

### A — EDIT / unlearn by provenance  — PROVEN
Each memory entry is tagged with the self-assigned domain that wrote it, so a whole process can be deleted on command.
- Unlearn a whole process (GPU, real data): ~400 self-domains / ~80k entries deleted -> target forgotten (Δ +0.2 to
  +0.3 bits/byte), every other process Δ~0.005 (LOCAL).
- vs weights gradient-ascent unlearn: memory-delete is ~6000x faster and ~1250x less collateral (weights-unlearn
  destroys entangled domains — ~22-25 bits of collateral).
- **This is the defensible product: clean unlearning on request (GDPR / copyright / factual removal). It does NOT
  depend on B.**

### C — self-ASSEMBLE domains  — WORKS, over-segments
A small encoder trained ONLINE + self-supervised (InfoNCE: nearby windows together, random apart) produces a domain
signature; boundaries = signature shift; the assembler opens new / merges redundant / culls stale domains, and memory
follows by provenance (reassign/delete). Kept LIVE with re-keyed centroids.
- Real corpora (eng/py/num/c): clustering purity 0.96; the learned signature separates domains (eng vs c) that
  byte-statistic signatures fundamentally cannot.
- OVER-SEGMENTS: ~350-418 fine domains for 4 true processes (boundary precision ~0.44 — fires ~3x too often). This is
  proven HARMLESS — see COMPOSITION below.
- Genuineness (silhouette = cohesion + separation - 1): ~12-19 of ~416 domains are "genuine" by the threshold. This is
  a diagnostic, **not** a capability metric — the system works regardless of the count, and the count is just where the
  silhouette cutoff sits.

### V — VERIFY (reconstruction)  — renamed from "B (detect WRONG info)", reframed
> RENAMED (2026-07-21): "B / detect wrong info" is retired. The old approach below (self-consistency on SURPRISE) was a
> category error — surprise drives learning, not truth — which is why it stuck at ~1% precision. The replacement, **V**,
> verifies by RECONSTRUCTION (reverse-embed → compare), decoupled from surprise. The old approach is kept here as the record.

**(historical) B — detect WRONG info — DOES NOT WORK in the realistic regime**
Self-consistency: run the model on each stored entry's OWN context; flag entries whose stored token the model ranks in
the high tail of implausibility (adaptive median + k·MAD threshold; single-shot per entry, so every entry is judged).
- Works for CATEGORICALLY wrong info (cross-domain corruption): ~78-86% recall/precision in `cl_bench`, domain recovers.
- FAILS in the product loop (~2% precision on a realistic <1% injection): the write gate stores SURPRISING tokens, and
  B flags SURPRISING tokens — so genuine-novel and wrong are conflated. The earlier high precision was inflated by
  injecting ~32% corruption; at a realistic fraction it collapses.
- Therefore B runs **DETECT-ONLY** in the product loop (`WRONG_SWEEP=0`): it reports honestly but does not delete,
  because deleting at 2% precision would gut the store. A does not need it.

## Memory mechanics (`cl_bench.py`)

- FORGETTING (bits/byte gained on old domains; lower = less forgetting):
  weights-only +2.27 | REPLAY +0.39 | mem[frozen key] +1.73 | mem[model key + re-key] +1.19.
  -> Replay BEATS memory on forgetting. Forgetting is table stakes; **EDITABILITY is the differentiator** — pitch that.
- DRIFT: keying memory on the model's OWN representation goes stale as the model drifts, UNLESS stored keys are
  periodically re-encoded (`REKEY=1`). With re-keying, the model key (+1.19) beats a static frozen key (+1.73) and
  survives drift. The frozen key is a TESTING BASELINE only; the product path is the unfrozen, re-keyed model key.

## Performance, composition, generation (`self_organize.py`)

- PERFORMANCE (does memory earn its keep): model alone -> model+memory = **+0.15 to +0.40 bits/byte** (~15% reduction)
  even on a well-trained model. Memory holds what the weights haven't absorbed; the contribution is largest while the
  model is still learning (for a clean, already-mastered domain, memory can slightly hurt).
- COMPOSITION (do the over-segmented domains work together): retrieval is a single GLOBAL kNN with **no src filter** —
  segments are a provenance overlay for EDITING, not a retrieval partition. Measured: retrieval spans ~6.4 distinct
  segments per position; GLOBAL retrieval beats siloing to the nearest segment by +0.07 to +0.09 bits/byte.
  **Over-segmentation is harmless because knowledge composes across segments.**
- GENERATION (comprehensible text): byte-level. At GPU scale the trained model produces semi-coherent English/code with
  real words and domain-appropriate structure, and near-perfect numeric streams — but not fluent prose (~2.3 bits/byte;
  fluent byte-level ≈ 1). This is a **base-model-capacity** limit, separable from the editable-memory layer.

## Optional: adaptive write-gate
The surprise scale drifts as the base trains (3.4 -> 2.3 bits), so a FIXED write gate is too permissive early / too
strict late. `WRITE_ADAPTIVE=1 WRITE_TARGET=<frac>` self-calibrates the threshold (rises when firing above target,
falls when quiet) to hold a stable write fraction at any scale. **Off by default** (baselines unchanged).

## Knobs
- Shared: `DEVICE, DATA_MODE=real, DOMAINS=eng,py,num,c, D_MODEL, MEM_CAP, WRITE_GATE, TOPK, KEY_SRC=model|frozen`
- `cl_bench.py`: `STEPS_PER_DOMAIN, SEQ, BATCH, LAMBDA, REPLAY_FRAC, REKEY, CORRUPT_MODE=cross|shuffle, ESTIMATE=1`
- `self_organize.py`: `STREAM_LEN, WIN, SIG_MODE=learned|bigram|unigram, SIG_D, ENC_WARMUP, ENC_EVERY, ENC_BATCH, TEMP,
  SHIFT_DIST, SUSTAIN, NEW_DIST, REKEY_EVERY, MANAGE_EVERY, MANAGE_MERGE, MANAGE_MIN, MANAGE_STALE, GENUINE_MIN,
  GENUINE_SIL, EVAL_N, WRONG_INJECT, WRONG_SWEEP, GEN_LEN, GEN_TEMP`
- Tokenizer (expanding): `TOKENIZER=1, VMAX=4096, MIN_PAIR=50, MAX_TOK=16, TOK_DROPOUT=0.0, GROW_PASSES=8,
  TOK_GROW_CAP, TOKENIZER_PATH=data/dyntok.json`. Grows 256 -> VMAX by minting frequent byte-pairs; bits/byte stays
  true bits/BYTE via per-token byte lengths (apples-to-apples with byte runs). Built once, cached to JSON.
- Adaptive gate: `WRITE_ADAPTIVE, WRITE_TARGET`

## Open problems / directions
1. **B** needs a fundamentally different signal — corroboration/contradiction (does an entry conflict with repeated
   evidence?), not self-consistency — OR drop autonomous detection and ship clean-unlearning-on-command (A delivers).
2. **Base model** is too weak for fluent generation. The EXPANDING subword tokenizer (`TOKENIZER=1`, online
   mint-on-repetition) is integrated and helps (word-pieces instead of byte salad), but full fluency still needs a
   bigger base model / Transformer. It may also give B a better chance (a wrong subword is more implausible than a
   wrong byte) — untested at scale.
3. **Over-segmentation** is harmless (composition proves it) — coarsening is cosmetic and deprioritized.
