# The Overarching System — Complete Reference

A single place capturing everything in this project: the vision, what's built and verified, what we
tried, what we learned, and what remains ideated-but-unbuilt. Written to be honest about the difference
between *works*, *runs*, and *helps* — because on this project those are three different claims.

---

## 0. The three claims (read this first)

Throughout, a feature is in one of three states, and they are NOT the same:
- **Works / verified** — the mechanism is correct and does what's intended (checked on CPU at small scale).
- **Runs / integrates** — it executes end-to-end without crashing, cumulatively with everything else.
- **Helps / unproven** — whether it improves the actual metric (OOD bits/byte). *Almost nothing is in this
  state yet*, because the benefit of most changes only appears with real training, which needs the GPU. The
  CPU sandbox can verify correctness but cannot resolve benefit — it truncates before the point where
  schedules/curricula/objectives express themselves. This is the single most important caveat in the project.

---

## 1. Vision & philosophy

A speculative, modular, continually-learning "cognitive" language model built in PyTorch. Guiding principles:
- **Emergence over hand-engineering.** Prefer mechanisms where structure/behavior emerges from pressure
  (growth, selection, compression) rather than being designed in.
- **Capability tracks compute × data, not module count.** Read every ablation at *matched compute*.
- **Intellectual honesty as the deliverable.** Negative results and "this didn't help" are the point.
- **Judge it as a compressor.** It's a next-token model (~few-hundred-M params), not a chatbot. The metric is
  **OOD bits/byte** (lower = better; nats/ln2; uniform-byte floor = 8.0) plus qualitative completions.

Naming: **Greg** = the original dense expert-fabric model. **Barry** = the sparse top-k MoE evolution. They
are one `OverarchingSystem` class with a `FABRIC` knob (`dense` = Greg, `sparse` = Barry). Greg is untouched
and remains the default; all recent work is Barry.

---

## 2. Architecture

One class, one forward path, a knob for the fabric. Pipeline:

```
tokens ─► embed (MoE embedders + sense book + optional compositional atoms)
       ─► encode_ ─► [correction hook?] ─► FABRIC (dense recurrent | sparse MoE stack) ─► [correction hook?]
       ─► readout (memory recall + gate) ─► logits  (+ MTP heads, + reconstruction head)
```

### Greg (FABRIC=dense)
A recurrent stack of dense experts with ponder/depth (adaptive computation), re-encode, counterparts
(invertibility). Proven but capacity-limited; dense experts don't scale in count.

### Barry (FABRIC=sparse) — the current focus
Greg's dense recurrent loop is replaced by a **stack of SparseMoE layers** (`barry.py`). Each SparseMoE =
- **top-k router** (`MOE_K`, default 2) — per token, only its top-k experts run. This is the *runtime*
  selector: with a big population, each token still touches only 2 experts.
- **capacity dispatch** — scatter/gather by index (no dense mask), capacity = `CAP_FACTOR`×fair-share.
- **VecExperts** — a stacked-weight bank run as one batched matmul (`bmm`), **no Python loop over experts**.
- **gated combine + residual**, **load-balance loss** (Switch-style), optional **counterparts** (stacked
  inverse bank + invertibility loss).
Verified: matches brute-force top-k to 1e-6, flat-in-N (≈7× faster than dense at 64 experts, gap widens),
trainable, self-balancing. Barry has everything Greg has (MoE embedders, sense book, mirror memory, surprise,
growth, replay, counterparts) and omits re-encode (proven dead weight — see findings).

### Core components (both fabrics)
- **MoE embedders** (`M_EMBED`) — a routed mixture of embedding tables, not one.
- **Sense book** (`SENSE_K`) — context picks a per-token sub-meaning branch (disambiguates the same token
  by local context via a causal gist).
- **Mirror memory** (`MEMORY=mirror`) — a recall store read at readout, gated into the final hidden.
- **Surprise** (`SURPRISE=reverse`, ReverseSurprise) — scores positional novelty; drives replay.
- **Replay** — rehearses buffered "surprising" rows alongside fresh batches.
- **Growth** — adds experts on plateau (see §5).

---

## 3. The tokenizer

Two implementations in `tokenizer.py`:
- **ByteBPE** — a classic frozen byte-BPE (train once to a fixed vocab). Lossless; slow to train
  (~197s for 8192 vocab on 7MB).
- **DynamicTokenizer** — an **emergent** byte-BPE that grows its vocab *during training*: it tallies byte
  pairs and mints a new token when a pair crosses `MIN_PAIR`, up to `VMAX`. This is the one we use
  (`TOKENIZER=dynamic`). Lossless (round-trips everything incl. unicode/control/dropout), memory-bounded.

### Speed (single-core, ~8× total, all verified)
It was the CPU bottleneck (crawled at ~1.1 it/s at batch 256). Three stacked optimizations
(226 → 28.5 ms/step at batch 256): **(1)** cache segmentations per window (id-keyed, valid because vocab
only grows; a small `refresh_frac` folds in new tokens); **(2)** vectorized pair-tally via `numpy.unique`
(not 65k Counter increments); **(3)** pruned the segmentation inner loop with a first-byte max-length table.
Plus a **background prefetch thread** (`PREFETCH=1`) that overlaps tokenization with the GPU (GIL released
during CUDA). `encode` rewritten to `torch.frombuffer` (no billion-element Python list for enwik9). Result:
**GPU-bound at batch 256** — the tokenizer is no longer the bottleneck at practical sizes.

### Multiprocess tokenizer (`MP_WORKERS`, verified, off by default)
For enwik9-scale cold cache / very large batch where one core still can't keep up: N worker **processes**
segment in parallel (`mp_tokenizer.py`). Hard-won design lessons:
- **spawn, not fork** — by the time training starts, torch/numpy have spawned BLAS/OpenMP threads, and
  forking a multithreaded process leaves inherited dead locks that hang workers. Spawn = fresh interpreters.
- **memory-mapped corpus** — workers mmap a shared `.npy` of byte windows, so spawn doesn't pickle gigabytes.
- **plain lists through the queue** — torch tensors through a multiprocessing queue break on a shared-memory
  fd; numpy/lists pickle by value.
- Workers hold vocab replicas; main pulls batches, tallies + mints, and broadcasts new merges back. Correct
  because the vocab only grows (stale replicas still emit valid ids). Verified end-to-end via the real
  (guarded) train.py. **Lower value now** since the tokenizer isn't the bottleneck — measure it/s before using.

### Tokenizer findings (from the merged test harness)
- **Lossless & memory-safe** — all round-trips PASS; pair counter bounded.
- **Compression (bytes/token):** frozen ByteBPE@8192 → eng 3.66, code ~2.3. Dynamic (one streaming pass,
  grew to ~1.6–2.6k) → eng ~2.7–3.0. The dynamic tokenizer **under-grows per pass** and compresses worse
  until many training steps accumulate — a real efficiency gap.
- **Brittle to typos** — a single-char error inflates a word to **1.2–1.8× tokens** with **23–36% byte
  fallback** (a typo breaks the learned merge). This motivated the correction/robustness work.

---

## 4. Growth & evolution (the "ecology")

Growth exists in both fabrics; the **evolutionary** layer is Barry-specific and is the project's most
original bet: *let expert specialization emerge from survival pressure rather than design.*

### The idea (yours)
Bottlenecked experts that **must generalize** (can't memorize much) + **must find a niche or die**
(selection) + **reproduce from success** (mutation). This channels the *grokking intuition* (pressure toward
compressed, general solutions) into architecture — even though grokking-the-phenomenon does NOT transfer to
language (wrong capacity/data regime: the model can't memorize 1GB so never enters memorize-then-generalize).

### The four levers (all verified to work; benefit unproven)
1. **Bottleneck** (`EXPERT_HIDDEN_MULT`, default 4.0) — shrink each expert's hidden dim below 4×d so it
   can't memorize and is pushed toward a compressed niche. Try 2 / 1 / 0.5.
2. **Mutation spawn** (`MUTATE=1`, `MUTATE_STRENGTH` 0.05) — new experts are **perturbed copies of the best
   expert** (by the selection signal), not random. (Correction: the old code spawned *random* experts and
   `seed_node` was a no-op for sparse — the "variation" you assumed existed did **not**; now it does.)
3. **Contribution cull** (`PRUNE_ECO=1`, `PRUNE_EVERY`, `NMIN`) — periodically remove the least-contributing
   expert.
4. **Cull-metric** (`CULL_METRIC` = energy | traffic | blend) — *how* to rank experts. `energy` = gated
   output magnitude; `traffic` = how often the router picks it (your "the population selector should follow
   the router's verdict" insight); `blend` = both. Verified the three pick different experts.

### Paired turnover (a bug we caught by testing small)
Growth was plateau-gated but cull was cadence-gated → in a non-plateauing run the population would collapse
to the floor. Fixed: **each generation culls the weakest AND respawns a mutation** — constant-size turnover
(birth-death). Verified the population churns instead of collapsing.

### The open question (only the GPU sweep answers)
The router already selects per-token; cull is a *slower* selector reshaping the pool the router draws from.
Does `eco_full` (bottleneck+mutation+cull) beat `eco_base` (current Barry)? Or does the router's per-token
selection already do the job? And does any of it break the 3.43 floor? **Selection guarantees division of
labor, not that the divisions are grammatical** — an expert can survive on a lazy surface niche. The
bottleneck tilts the odds toward generalizing being the better survival strategy; whether that's enough is
the experiment.

---

## 5. Training methods (all built as knobs, off by default)

The base objective is teacher-forced next-token cross-entropy + auxiliary losses (depth/ponder, re-encode,
counterpart-invertibility, load-balance), AdamW, dropout + weight decay. Everything below is additive and
toggleable. **Correctness verified; benefit needs GPU.**

- **Optimizer** (`OPTIM` = adamw | lion) — Lion is sign-based (half the optimizer memory), auto-scales its
  LR to LR/5. (`optimizers.py`, `make_opt`.)
- **LR schedule** (`LR_SCHEDULE` = constant | cosine | wsd) — the base was warmup-**then-constant** (no
  decay, the clearest weakness). Cosine decays to `LR_MIN_FRAC`; WSD (warmup-stable-decay) holds flat then
  decays only in the last `WSD_DECAY_FRAC` (good when you don't want to fix a step budget). Cosine is a safe
  upgrade over constant on priors — but the default is still `constant` (not changed silently).
- **Label smoothing** (`LABEL_SMOOTH`) — softens the *training* target; eval stays true bits/byte.
- **Z-loss** (`Z_LOSS`) — penalizes large logits (log-sum-exp²), PaLM's stabilizer.
- **Gradient accumulation** (`GRAD_ACCUM`) — N microbatches per optimizer step = larger effective batch.
- **Weight EMA** (`EMA_DECAY`) — eval + best.pt use averaged weights; live weights kept for training/resume;
  re-seeds on grow/cull.
- **Multi-token prediction** (`MTP_K`) — extra heads predict tokens t+2…t+K from the final hidden; their CE
  is an auxiliary loss. Improves sample efficiency in the literature; architecturally interesting here.
- **Denoising** (`DENOISE`, `DENOISE_MODE` = sub | swap | mix) — corrupt the INPUT tokens but keep targets
  CLEAN, so the model predicts correct tokens from corrupted context = **error correction**.
- **Reconstruction / self-correction loop** (`RECON`) — a head predicts the clean token at *every* position
  (a denoising autoencoder). `sysm.reconstruct(x)` runs the loop you specified: reconstruct corrected tokens
  → decode to bytes → **re-route through the tokenizer** (recovering proper merges).
- **Phased curriculum** — `CTX_START`/`CTX_RAMP_STEPS` ramp sequence length (short/easy first), and
  `GROWTH_START` holds all growth+turnover until foundation experts form, so growth borrows from a solid base
  (your rationale: the mutation mechanism inherits from existing experts). Verified: turnover correctly held
  until the set step.

---

## 6. Representation & correction ideas (newest)

- **Compositional token embeddings** (`COMPOSE_EMB`) — your "a token defined as a series of other tokens,
  its vector stored directly instead of forcibly learned." Each token records its **definition** = its 2
  constituent tokens (a `parts` buffer, filled on minting), and its embedding gets
  `+COMPOSE_EMB × mean(constituent atoms)`. Verified: minted tokens carry their definition (e.g. token 256 =
  space+`t`); composition applies and checkpoints. **One-level only** (immediate 2 constituents, not
  recursively down to bytes) — multi-level is a real extension, unbuilt.
- **Stage-agnostic correction hooks** (`CORRECT_AT` = none | embed | fabric) — a residual corrector module
  (identity-initialized) insertable **post-tokenizer** (`embed`) or **mid-model** (`fabric`), learning
  correction via the denoising/recon signal. "Correction at any stage" currently = two hooks; more stages are
  easy to add. It's a *generic* refinement layer trained to correct, not a bespoke correction algorithm.

---

## 7. Data pipeline

- **Base corpus**: enwik8 (~96MB) or **enwik9** (~1GB, 10×) via `DATASET`, auto-fetched by `setup_lambda.sh`
  (2 mirrors, size-verified, loud failure). enwik is a **raw dump** — full MediaWiki markup (`<text>`,
  `{{...}}`, `&lt;math&gt;`) is in the text and consumes capacity (a known trait, not cleaned — see deferred).
- **Extra books**: ~15 Gutenberg titles (best-effort).
- **Diverse sources** (`DIVERSE=1`, `fetch_data.py`): FineWeb (web), GitHub-code **routed per language**
  (py/js/c/cpp/java/go/rust/ts → each becomes its own domain), Reddit, and your own `data/raw_json/*.json`.
  Each source is independent/best-effort. New domain folders auto-become new held-out eval domains — the
  variety the sparse experts can specialize on.
- Current default everywhere: **enwik9 + diverse**, `VMAX=32768`, `MIN_PAIR=200` (no silent downgrades).

---

## 8. Testing & evaluation

- **`test_tokenizer.py`** (merged harness) — toggle sections via `SECTIONS`: `correct` (lossless round-trip),
  `compress` (bytes/token), `robust` (typo inflation + byte-fallback), `recon` (model correction loop).
  `FULL_BPE=1` adds the slow frozen-BPE audit.
- **Live training eval** — held-in and OOD bits/byte per domain, novelty, memory-confidence; `train_log.jsonl`
  updates live; `greg_status.py` is a dashboard; `read_results.py` compares runs.
- **Sweeps** — `run_eco_sweep.sh` now wires all four eco levers + the cull-metric as arms, on enwik9+diverse,
  with the MP tokenizer on by default.
- **The CPU limitation** (again): small-scale runs verify *correctness/mechanics* and catch integration bugs
  (it caught the turnover collapse, the fork-after-threads hang, the FineWeb kwarg clash, an accidental file
  deletion). They do **not** measure *benefit* — that's a scale question for the H100.

---

## 9. Results & findings (what we actually know)

- **The 3.43 OOD floor.** Barry bottoms out around **OOD 3.43 bits/byte** at d512/8-layer. Confirmed it's a
  **capacity/architecture ceiling, not data**: threw 10× data (enwik9) + 4× vocab (32768) at it — still 3.43.
- **Code-switching.** With a diverse corpus, generation fluently *juggles* domains mid-sentence (wiki markup
  ↔ C ↔ LaTeX ↔ prose) — it learned all registers but has no signal to stay in one. This is inherent to a
  base model with no conditioning; more data makes it *worse*, not better. Conditioning (tags) or bigger
  context would address it — but you chose the self-organizing/architectural route.
- **Data bugs that caused earlier "overfitting"** were real bugs (enwik8 never fetched; a per-file cleaning
  bug discarded 96MB), now fixed — the plateau is genuine, not a bug.
- **Re-encode is dead weight** (dropped in Barry). **Counterparts: keep. Sense: optional.**
- **Grokking doesn't transfer**, but the intuition (pressure toward compressed/general solutions) is
  buildable via bottlenecked experts.
- **Tokenizer**: lossless + memory-safe, but under-compresses (dynamic under-grows) and is typo-brittle.

**To push OOD below 3.43, the levers (in order): (a) bigger model (d768/d1024 — Barry's flat-in-N speed makes
this affordable where Greg couldn't); (b) clean the wiki markup; (c) more fabric layers / higher top-k so
experts compose. NOT more data.** Whether the eco levers or training methods help is the open experiment.

---

## 10. Complete knob reference (the toggles)

**Fabric/model:** `FABRIC` (dense|sparse), `D_MODEL`, `N_LAYERS`, `N_HEADS`, `CTX`, `MAX_LEN`, `M_EMBED`,
`SENSE_K`, `SENSE_POS`, `MEMORY`, `SURPRISE`, `COUNTERPARTS`.
**Barry MoE:** `MOE_K`, `FABRIC_LAYERS`, `CAP_FACTOR`, `LB_COST`.
**Growth/evolution:** `N0`, `NMAX`, `GRACE`/`PATIENCE`/`COOLDOWN`, `EXPERT_HIDDEN_MULT`, `MUTATE`,
`MUTATE_STRENGTH`, `PRUNE_ECO`, `PRUNE_EVERY`, `NMIN`, `CULL_METRIC`.
**Tokenizer:** `TOKENIZER` (dynamic|bytebpe), `VOCAB`, `VMAX`, `MIN_PAIR`, `MINT_PER_STEP`, `TOK_DROPOUT`,
`PREFETCH`, `MP_WORKERS`.
**Training:** `LR`, `LR_WARMUP`, `LR_SCHEDULE`, `LR_MIN_FRAC`, `WSD_DECAY_FRAC`, `WEIGHT_DECAY`, `GRAD_CLIP`,
`OPTIM`, `LION_LR`, `LABEL_SMOOTH`, `Z_LOSS`, `GRAD_ACCUM`, `EMA_DECAY`, `MTP_K`, `DENOISE`, `DENOISE_MODE`,
`RECON`, `EARLY_STOP`.
**Curriculum:** `CTX_START`, `CTX_RAMP_STEPS`, `GROWTH_START`.
**Representation/correction:** `COMPOSE_EMB`, `CORRECT_AT`.
**Data:** `DATASET`, `DIVERSE`, `EXTRA_BOOKS`, `WEB_MB`/`CODE_MB`/`REDDIT_MB`, `DATA_CAP`.
**Run:** `STEPS`, `BATCH`, `EVAL_EVERY`, `CKPT_EVERY`, `RUN_DIR`, `HELD`, `OOD_N`, `REPLAY`.

---

## 11. Ideas explored, and what's deferred/unbuilt

**Explored & built (verified to work; benefit unproven):** everything in §2–6.

**Ideated, explicitly NOT built (with the reason):**
- **Bigger model (d768/d1024)** — the single most likely lever to break 3.43. Deferred by you; it's an
  env-var change (fresh run) whenever you want it.
- **Wiki-markup cleaner** — enwik's markup eats capacity. Deferred; you preferred the architectural route.
- **Data-difficulty curriculum** — easy→hard *content* ordering (e.g., Simple Wikipedia → full). We built
  sequence-length + growth-phase curriculum, not content-difficulty.
- **Multi-level recursive composition** — compositional embeddings currently use immediate 2 constituents;
  recursing down to bytes ("word = composition of subwords = composition of chars") is the richer version.
- **Intrinsic error-correcting tokenizer** — a segmenter that *fuzzy-matches* a typo'd byte sequence back to
  the correct token at segmentation time (vs the model-side reconstruction we built). Harder to keep lossless.
- **More correction stages** — currently embed/fabric; correction "at any stage" could add pre-readout,
  per-layer, post-logit, etc.
- **Denoising/objective variants** — span corruption (T5), UL2 mixture-of-denoisers, are not built (we built
  token-substitution denoising + reconstruction).
- **Alternative optimizers beyond Lion** — Sophia, Muon, Adafactor.
- **Conditioning for coherence** — domain tags / register conditioning to stop code-switching (deliberately
  set aside in favor of self-organizing approaches).
- **Instruction/chat tuning** — out of scope; this is a compressor, not a chatbot.

**The meta-open-question:** does *any* of the eco/training/representation machinery move OOD below 3.43, or
is capacity (bigger model) the only real lever? That is what the GPU sweeps are for. Everything is built,
verified to run cumulatively, and gated behind knobs so we can turn aspects on/off to find out.

---

## 12. How to run (quick)

Fresh H100 instance:
```
scp -i <key> overarching-package.zip ubuntu@<IP>:~
ssh -i <key> ubuntu@<IP>
sudo apt-get update -qq && sudo apt-get install -y unzip tmux
unzip -o overarching-package.zip && cd overarching-package
```
Eco sweep (all four levers + cull-metric + MP, on enwik9+diverse):
```
STEPS=8000 ARMS="base bn1 mut cull full ftraffic fblend" tmux new -s eco 'bash run_eco_sweep.sh'
watch -n 15 python3 greg_status.py ~/eco.log
```
Winner / scale run (example, with training methods on):
```
DATASET=enwik9 DIVERSE=1 STEPS=50000 LR_SCHEDULE=cosine EMA_DECAY=0.999 \
  EXPERT_HIDDEN_MULT=1 MUTATE=1 PRUNE_ECO=1 CULL_METRIC=traffic \
  tmux new -s barry 'bash run_barry_scale.sh'
```
Tokenizer harness / chat:
```
python3 test_tokenizer.py                    # correctness + compression + robustness
bash talk.sh "In the early 20th century"     # completions from best.pt
```

See `BARRY_RUN.md` for the detailed runbook, and each `*.py` header for module specifics.
