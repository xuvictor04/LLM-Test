# STATE.md — living project ledger

**PROTOCOL (binding, for the assistant):**
1. Update this file BEFORE responding, every turn. Add to the Changelog (§6); edit any section that changed.
2. **Verify your edit actually landed** — re-read (or grep) the changed lines before claiming success. (This ledger
   once silently stopped saving for ~30 turns while turns kept narrating edits to it; never trust an unverified write.)
3. Before making ANY choice, check §2 (Decisions) and §5 (Config). If the user decided it, follow it — never override
   with a default. If they did NOT decide it, either ASK, or label it `[my default]` in the reply so they can correct.
4. Keep the explicit **Included / Not included / Deferred** accounting (§3) current — report adds/removes/omissions.
5. `[USER]` = the user's explicit call (do not override). `[me]` = my default/assumption (must be flagged when relied on).

> SOURCES OF TRUTH: the CODE is ground truth for *what the system is*. `handoff/PROJECT_CONTEXT_EXPORT` content (now
> folded into `handoff/history/` + the decisions/glossary/commands files) is the authoritative NARRATIVE of how it got
> here — it reconstructed the full history that this ledger had lost. `garry/GARRY.md` holds the frozen milestone
> numbers. When older docs disagree on turn labels ("T33" vs "T18/T24" vs "Phase N"), the **phase** framing (§6) is canonical.

---

## 0. GARRY — frozen milestone checkpoint
`garry/` is a FROZEN, independently runnable snapshot of the best-verified **redundancy-regime** state ("Garry"): the
first version where the whole architecture worked at once and expert-deletion collateral hit **-0.0009** with
end-to-end **1.967** b/B. (Older docs label this T33 / T18–T19; the label is inconsistent — the state is what matters.)
NOTE: root is Garry's DESCENDANT, not a byte-copy — it adds later retrieval-grounding / source-`pos`, batched training
(`BATCH_W`), and corpus-fetch tooling (`cl_bench.py`/`tokenizer.py` are identical; see `docs/FILES.md`).
- Do NOT edit `garry/`. Development continues in the package root.
- Reads shared corpora via `DATA_DIR=../data`; namespaces its runs (`~/garry.txt`, `runs/garry/`). Config + numbers in `garry/GARRY.md`.
- Purpose: a known-good reference to fall back to and compare every later change against.
- The MODULARITY regime is NOT frozen separately — it reproduces from Garry's own code with `ROUTE_GROUNDED=1 ROUTE_T=0.3`
  (freezing it would duplicate ~72KB for a two-env-var difference). `[me, flagged]`

## 1. What this is
Autonomous continual-learning system. One unlabeled stream (bytes, or tokens if the expanding tokenizer is on) →
self-ASSEMBLE domains (C) → VERIFY by reconstruction (Verification, formerly "B / detect wrong info") → EDIT / unlearn by
provenance (A). Nothing frozen, nothing labeled.

**NORTH STAR [USER] (full statement in `handoff/NORTH_STAR.md`):** a SMALL model (much smaller than conventional LLMs)
that LEARNS and does complex REASONING, with an ever-EXPANDING, UPDATABLE knowledge base. **SACRED INVARIANT: when
compromises are forced, EXPANSION and GROWABILITY must NOT be lost.** Language capability is a personal BENCHMARK, not the
endpoint. Longer-horizon goals: MULTIMODALITY (pluggable "avenues") and an observability DASHBOARD streaming the
thinking/processes live. From-scratch (not a pretrained base) = for NOVELTY + full OWNERSHIP. Compute = rented H100, as
long as needed (scale is feasible; "small" means capability-per-parameter via architecture, not brute scale).
**Success priorities (most→least) [USER]: (1) conversation → (2) sentence generation → (3) characterized architecture → (4) shipping** (importance ranking; (1) depends on (2) in practice).

**TWO CHARACTERIZED REGIMES (a genuine product fork — see §4 Q-regime):**
- **REDUNDANCY** (`ROUTE_T=1.0`, = frozen `garry/`): **1.967** b/B, expert deletion FREE (-0.0009), no specialization.
- **MODULARITY** (`ROUTE_GROUNDED=1 ROUTE_T=0.3`): **2.002** b/B, expert deletion **+0.127 CONCENTRATED** on the
  domains that expert served (~7× ratio) — real specialization for +0.035 b/B. Still 0 exclusive experts (soft constituency).

Code: `memory.py` (the store), `self_organize.py` (product loop + society/fabric), `cl_bench.py` (mechanics).

## 2. Decisions
### Standing directives [USER]
- Report every add/remove/change AND every omission, explicitly. Never silently drop something.
- End each build with a Recommended Next Step + WHO does it (me = build / user = test or decide on GPU). Flag the user's calls.
- Everything built for the UNFROZEN final product; frozen only as a labeled TESTING baseline.
- Estimate wall-clock BEFORE any GPU run (use the built-in probe).
- Bias toward pruning / simplification over accumulating options.
- Over-segmentation is fine IF domains are genuine; self-assembly (no hand labels) is a hard requirement, never relaxed.
- **Stop defaulting to my own choices; keep this ledger current; flag my defaults.** [USER]
- Name blockers the sandbox can't reach EXPLICITLY (GPU, large downloads, HuggingFace) and hand off ready-to-run commands
  — the user runs them on their H100. Never silently substitute a smaller local approximation or pretend it's equivalent. [USER]

### Design decisions [USER]
- Memory key = the model's OWN representation (unfrozen) + periodic re-keying. Frozen key = baseline only.
- **Verification — RENAMED from B (wrongness) [USER]:** the middle of the loop is verification by RECONSTRUCTION
  (reverse-embed → compare), NOT wrongness-detection on surprise. The old B (self-consistency on surprise) was a category
  error — surprise drives LEARNING, not truth — hence its ~1% precision. Verification is decoupled from surprise. Old `is_wrong`/
  `selfcheck` code persists until the build replaces it. (see `handoff/decisions/B-renamed-to-Verification-...`)
- Genuineness = SILHOUETTE (coh+sep-1), not size — the COUNT is arbitrary; PERFORMANCE is what matters.
- Write-gate signal is SURPRISE (1 − p_model(true token)); "novelty" was a misnomer, renamed.
- Tokenizer = the EXPANDING `DynamicTokenizer` (online mint-on-repetition), NOT the static ByteBPE. Mints DURING training (`TOK_ONLINE=1`).
- **The domain SIGNATURE ENCODER reads the BYTE stream, never the token stream** — a domain is a byte-level property;
  reading tokens let the churning vocab destabilize domain boundaries (the online-tokenizer collapse, Phase 4). [fix]
- **Experts are INDEPENDENT AGENTS** blended at the PREDICTION level (`Σ wᵢ·head(oᵢ)`), NOT by averaging hidden states;
  nothing frozen; new experts cloned from the live base; DOMAINS are collections of experts; independence makes removal clean. [USER] → `SOCIETY=1`.
- **Society mode, not chained mixture** (`SOCIETY=1`, not `SOCIETY=0`): experts compute independently from the same
  shared hidden state; the chained mixture entangled every expert's gradient and degraded the base model. [fix]
- **Retrieval grounding is INTERNAL only** — recall conditions generation on source passages but NEVER emits raw passages to the user. [USER correction]
- **Do NOT build on a pretrained base** (Llama/Mistral/etc.) — the goal is the full novel model trained by us. [USER]
- **Domain deletion RELEASES a domain's expert affiliations, it does NOT cascade-kill experts** — an orphaned expert is
  later culled by normal selection; one still serving other domains is untouched. [USER rejected cascade]
- GRU is the default base model; a Transformer needs big batches and underperforms at batch-1 online streaming. `MODEL=transformer` exists.
- `fab_logits()` is the SINGLE path from hidden state to output logits — training, eval, wrongness, and generation all
  use it, so a fabric-trained checkpoint is never run through a fabric-less path (that bug hit 3× — §7, bug pattern). [invariant]
- A diagnostic must NEVER be able to crash a training run — late-run diagnostics are wrapped in try/except. [invariant]
- Cross-domain interactions (composition) are OK and EXPECTED — a feature, not a bug. Memory MANAGEMENT + EDITING (A) are the core. [USER]
- Dead code removed (reverse model, retrieval-wrongness); legacy LM-era code archived in `legacy/`, not deleted.
- **Full test = ALL ideas ON** in `run_full_unfrozen.sh`. [USER]

## 3. Included / Not included / Deferred
### INCLUDED — active, in root
- `memory.py` — EditableMemory: surprise-gated write (+source `pos`), model|frozen key, re-key, delete/delete_src (A),
  self-consistency `is_wrong` (old B), reconstruction `is_unverified`/`set_recon` (Verification), optional adaptive gate, selectable eviction, stats.
- `verification.py` — **Verification** (renamed B): `Reconstructor` (reverse embedder, cross-reconstructs the expected
  token-code from the context key), `recon_loss`, `verify()`. Standalone CPU probe validates the core claim (AUC ~0.93 on structured data).
- `run_verify_test.py` — one-shot copy-paste A/B test: Garry-like config + `VERIFY=recon`, runs the product loop, prints reconstruction precision vs old-B precision.
  Reads now EXCLUDE unverified entries (no-op until `verify()` runs); `VERIFY_SWEEP=1` DELETES them (detect-AND-remove — the old B never earned this at ~1% precision).
- `verify_console_test.py` — self-contained (torch + `data/` only) A/B; the faithful surprise-gated-regime test (validated AUC 0.980 vs B 0.907).
- `self_organize.py` — product loop: byte-signature assembly (C) → B detect-only → performance → composition →
  generation → unlearn (A); online tokenizer; the society/fabric of experts; affiliation map; validation/memorization check.
- `cl_bench.py` — mechanics: forgetting vs replay, editability (memory-delete vs weights-unlearn), drift, wrongness.
- `prompt.py` — message the trained model (plain / `MEM=1` / `GROUND=1` internal-only recall).
- `tokenizer.py` (DynamicTokenizer + retire_stale), `run_full_unfrozen.sh` (RUN_NAME-namespaced), `run_cl_test.sh`.
- `fetch_data.sh` (~85MB GitHub-sourced, verified; `BIG=1` ~1GB), `fetch_big.py` (HF streaming — network UNTESTED from sandbox).
- Docs: `README.md`, `CL_TESTBED.md`, `STATE.md`, `docs/FILES.md`, `docs/HANDOFF.md`.
- `handoff/` — chat-to-chat context-exchange folder [USER]: `README.md` bootstrap + `NORTH_STAR.md`, `GLOSSARY.md`,
  `COMMANDS.md`, and atomic one-idea files under `process/`, `decisions/`, `open-questions/`, `design-directions/`,
  `designed-but-not-built/`, `history/`, `migrations/`.

### NOT INCLUDED — built but OFF by default, or archived
- Frozen memory / frozen key: baseline only. Adaptive write-gate: ON in the full run, toggleable off for byte baselines.
- Dropout / weight-decay: built, DEFAULT OFF (model is underfit, not overfit — turn on only if the memorization check shows a gap).
- `retire_stale` (tokenizer un-merge): exists, NOT wired into the online loop (vocab only grows).
- `BATCH_W` (batched-window LM training): built + verified — but `STREAM_LEN` must scale WITH it or the model trains LESS.
- ~57 legacy files in `legacy/` (Barry/Greg LM architecture) — unused; the fabric was ported forward from `legacy/system.py`.

### DEFERRED — awaiting a user decision (see §4)
- B redesign (corroboration/contradiction) vs dropping autonomous detection.
- Redundancy vs modularity as the standing default.
- The first real-GPU-scale run on the expanded corpus + batched training (the direct test of the language goal).

### FUTURE DIRECTIONS — north-star goals, not yet designed (see `handoff/NORTH_STAR.md` + `handoff/designed-but-not-built/`)
- MULTIMODALITY: pluggable "avenues" to add modalities beyond text. [USER, long-horizon]
- OBSERVABILITY DASHBOARD: stream the model's thinking / internal processes live. [USER, long-horizon]
- Reasoning + a genuinely small footprint with growth intact — the capability-per-parameter bet.

## 4. Open questions — awaiting the user's call (I should ASK, not default)
- **Q0 — expert evolution type?** Verified: fitness = pure OCCUPANCY (`fit = use/age`), NO loss term. Never approved — accreted `[me]`.
  Weakness: a frequently-routed BAD expert still wins (cheap-to-reach beats good). **Prior-context rec: (a) Darwinian
  per-expert-LOSS fitness** (the clearly-wrong piece first). Alternatives: (b) tournament vs argmax; (c) adapter crossover;
  (d) self-adaptive mutation; (e) age-layered protection. **USER's call — not decided.**
- ~~**Q3 — B direction?**~~ SUPERSEDED by the Verification reframe: neither corroboration-B nor cut-B — REPLACE B with **Verification**,
  reconstruction-based verification decoupled from surprise (see §2 and `handoff/decisions/B-renamed-to-Verification-...`). What
  remains is a BUILD, not a decision.
- **Q-regime — REDUNDANCY vs MODULARITY as the standing default?** Genuine product fork, both measured (§7). No recommendation —
  redundancy = losing any component costs nothing; modularity = components mean something, deletion cost small + attributable
  (stronger for a machine-unlearning/compliance framing). **USER's call.**
- **Q-compute — what to run next at GPU scale?** Data + throughput blockers are resolved (corpus expansion + `BATCH_W`), but
  NOTHING has been run at the new scale. A GPT-2-scale token budget is WEEKS of H100 time, not hours. Size the next run deliberately. **USER's call.**

### RESOLVED (previously open)
- Management ON/OFF ablation — RUN. No prediction-quality cost either way; management's real job is bounding domain-record GROWTH (a narrower claim than "essential"). (§7)
- Online minting "hurts" — REFUTED. Online == frozen at matched vocab+memory; the regression was undertraining + smaller vocab. Online minting KEPT.
- Base model — GRU is the standing default (Transformer needs big batches). `MODEL=transformer` available.
- Tokenizer default — ON for the full test; standalone modules keep byte-level for clean baselines.

## 5. Config — run-command values, provenance
Unless marked `[USER]`, treat as `[me]` and flag when used in a command.
- **Garry (redundancy, the reference)** `[measured]`: `MODEL=gru D_MODEL_B=512 STREAM_LEN=6000000 WIN=96 FABRIC=1 SOCIETY=1
  ENS_K=2 IND_W=0.5 IND_K=2 FAB_N0=3 FAB_NMAX=6 TOKENIZER=1 TOK_ONLINE=1 VMAX=8192 KEY_SRC=model MEM_CAP=300000 EVICT=recency MANAGE=1 EXPERTS=0`.
- **Modularity**: the above + `ROUTE_GROUNDED=1 ROUTE_T=0.3`.
- Data: real corpora eng/py/num/c `[USER]`. Bundled ~5.7MB unique (~3.7MB effectively seen). `fetch_data.sh` → ~85MB; `BIG=1` → ~1GB.
- Scale-up template `[me]`: `DATA_DIR=data_big CORPUS_CAP=2e9 WIN=256 BATCH_W=16 ACCUM=4 D_MODEL_B=768 VMAX=16384` — **scale `STREAM_LEN` WITH `BATCH_W`.**
- Wrongness: `WRONG_SWEEP=0` (detect-only) `[USER-aligned]`. Regularization: `DROPOUT=0.1 WEIGHT_DECAY=0.01` only if the memorization check shows a gap.

## 6. Changelog (newest first)
> NUMBERING: project HISTORY is reconstructed as **Phases 0–11** (full detail in `handoff/history/`, from the context
> export). Older docs' turn labels (T0–T4 here, "T33" in GARRY.md) are inconsistent and superseded by the phase framing.
> **This ledger silently stopped saving to disk after ~T4 in the original environment** while later turns narrated edits
> to it — the root cause of every drift; disclosed, not papered over. Saving is verified working in the current repo.

### Repo-era turns (this migrated GitHub repo)
- **R38 (current):** [USER: "GPT-2 parity can't be reached on what we're running on — stronger GPU, make the system more
  efficient"] EFFICIENCY, with the standing no-compromise rule: nothing removed, nothing downgraded, every change either
  exactly equivalent or an explicit opt-in flag.
  - **Instrumented first** (`PROFILE=1`): per-component wall-clock attribution printed with the `[rate]` line. Built
    BEFORE optimizing, because the last bottleneck claim was made without profiling and was wrong.
  - **PROFILE RESULT (this overturned my hypothesis).** I predicted `mem_key` was the dominant cost. It is not — it is
    **4-5%**. Measured share of loop wall-clock (CPU, `D=256 WIN=128 BATCH_W=8 KEY_WIN=32`):
    `encoder(contrastive) 87% | memory key+write 4% | lm fwd+bwd 4% | sig_of 4% | rekey(amortized) 1%`.
    `ENC_EVERY` defaults to **1**, so the SigEncoder's InfoNCE step runs EVERY step over `2*ENC_BATCH(=48)` windows —
    ~12× the LM's own forward work, plus a backward pass. **The language model is 4% of its own training loop.** This is
    exactly why the profiler was built first; the previous two bottleneck claims (mine: `mem_key`; the earlier
    "reverse embedder") were both wrong, and the user's instinct that the ENCODERS were the problem was the closest.
  - **`mem_key(x)` fix (correct, equivalent, but only a 4% component).** It encoded a memory key for EVERY position —
    `(BATCH_W*WIN, KW)` through the LM, i.e. `KW`× more token-positions than the main forward, every step — and then
    `mem.write` discarded the ~88% that fail the surprise gate. `write()` now takes `key_fn` and encodes AFTER the gate,
    so only the survivors pay. Exactly equivalent (the encoder is row-independent; gate, controller and resulting
    entries untouched). `KEY_PREGATE=0` restores the old order for A/B. Equivalence PROVEN by seeded A/B: `mem_keys`,
    `mem_tok`, `mem_src`, `mem_pos`, `mem_ctx` bit-identical over 20364 entries, model weights identical. Speed effect
    at the tested scale: **none** (70s vs 73s, i.e. noise) — it optimizes 4% of the loop.
  - **The real target — `contrastive_step` (87%).** Two changes: (a) `enc(A)`/`enc(P)` fused into ONE concatenated pass
    (`ENC_FUSE=1`, default; rows are independent so the MATHS is identical, at half the sequential GRU launches);
    (b) both batches were built from Python lists (`2*ENC_BATCH*WIN` int conversions per step, then copied to device)
    and are now gathered from a device-resident tensor (`set_enc_tensor`, refreshed on every resample).
    MEASURED: wall 70s/73s → **62s/64s** (~12%), encoder share 87%/86% → **81%/82%**, same config and seed.
  - **EQUIVALENCE — a weaker guarantee here than for the memory-key change, stated honestly.** Old-code vs new-code,
    seeded: memory (`keys/tok/src/pos/ctx`, 23707 entries) and **model weights identical**, but **`enc` weights differ by
    ~1e-5 relative**. Cause: fusing A and P changes the GRU kernel's batch shape and therefore its reduction order, and
    float addition is not associative — so this is mathematically equivalent but NOT bit-identical, unlike
    `KEY_PREGATE`. Nothing discrete diverged at this scale (same domains, same memory, same LM weights), but rounding
    can compound over a multi-day run, so `ENC_FUSE=0` restores the two-pass form and the bit-level guarantee.
  - **ISOLATED — the two halves have different guarantees, and the choice is now explicit.** Running gather-only
    (`ENC_FUSE=0`) against the old code: `enc`, `model` and memory ALL bit-identical. So the device-resident gather is
    free and strictly safe; **the fuse alone causes the ~1e-5 drift, and the fuse alone carries nearly all the speedup**:
      * `ENC_FUSE=0` → **69s** vs 70s baseline (~1%), BIT-IDENTICAL.
      * `ENC_FUSE=1` → **62s/64s** vs 70s (~11%), mathematically equivalent, not bit-identical.
    Default is 1. On GPU the fuse should pay MORE than it does here, since it halves the sequential GRU launches and
    launch latency is what dominates a GPU step — whereas on CPU it only improves BLAS/threading efficiency.
  - **Removed per-step GPU→CPU synchronizations**, each of which stalls the whole pipeline on an async CUDA queue:
    `dom_exp` now accumulates on device and moves to host once in the end-of-run report; `_fab_nov` stays a 0-dim device
    tensor (it is consumed by `expand` next step); the independence-loss weight uses `.detach()` instead of `float()`
    (numerically identical — both stop the gradient); the loss scalar is pulled back ONCE per step instead of twice.
  - **Precision knobs**: `TF32=1` (default on — matmul TF32 is off by default in current torch, leaving most of an
    H100's matmul throughput unused) and `AMP=bf16` (opt-in autocast for the LM step; bf16 shares fp32's exponent range
    so no GradScaler). Memory keys deliberately stay fp32 — retrieval is a dot product over normalized keys, the one
    place reduced precision would change behaviour rather than just speed.
  - **NOT done, deliberately**: `mem.write`'s adaptive-gate controller still syncs once per call (`float(keep.mean())`).
    Moving it on-device would change float64-vs-float32 accumulation in the last bits and could slowly drift which
    entries get written — a real behavioural change for a marginal gain, since the boolean-index sync in the same
    function remains regardless.
- **R37 (current):** [USER: "before I test, is there anything we can or should do before?"] Audited the PILOT'S OWN CODE PATH
  and found three gaps, two of which would have wrecked the run. (1) **World model absent from the checkpoint.** With
  `WORLD_FEEDBACK=1` the base LM is TRAINED as `h += world_proj(forecast)`, but `_save_ckpt` saved no world state and
  `prompt.py` had no world path — so generation would have run a DIFFERENT network than training, silently invalidating the
  coherence judgement that is the whole point of the pilot. Now saved (`world_cfg/world_enc/world_fwd/world_proj`, including
  the GROWN population size) and applied in `prompt.py` at the same place as training (before fabric/head).
  (2) **No RESUME.** Checkpoints were generate-only: a multi-day run that died at hour 20 restarted from zero even though a
  checkpoint existed. `RESUME=runs/x` now reloads model/enc/fabric/experts/world + BOTH optimizer states + step + memory store
  + domain centroids, re-growing fabric nodes and dynamics predictors to their saved sizes BEFORE the optimizers are built so
  Adam moments restore into the right param groups; encoder warmup is skipped (already trained).
  (3) **Resume would have corrupted the vocab**: under `TOK_ONLINE=1` the tokenizer always re-seeded from scratch, so a
  restored embedding table would have been indexed by a DIFFERENT vocabulary — `RESUME` now forces the saved `dyntok.json`.
  Verified end-to-end on CPU: trained → checkpointed → resumed (exit 0), Adam step counters CONTINUED 937→1171 (not reset
  to 1, so the moments and bias correction genuinely restored), memory 105k→130k entries, domains and predictors intact.
  Also found WHY "the estimates are always wrong and longer than expected": `[probe]` extrapolates from a SYNTHETIC
  batch-1 LM forward/backward and ignores `sig_of`, the live contrastive encoder, the amortized re-key, domain assembly
  and memory — i.e. most of the step. It is now labelled a LOWER BOUND, and a `[rate]` meter measures the ACTUAL loop
  every `RATE_EVERY` steps (steps/min, kB/s of corpus, self-correcting ETA, and GB-of-text-per-day vs the GPT-2 target).
  Files: `self_organize.py`, `prompt.py`.
- **R36:** [USER: "disk streaming loader sounds important, build it first"] BUILT the disk-streaming data loader so
  training data is DISK-bounded, not RAM-bounded (the ceiling on GPT-2-scale data). `datastream.py`: `MmapConcat` presents
  on-disk corpus files as ONE indexable byte sequence via mmap (disk-paged, not resident) — CPU-probe verified BYTE-IDENTICAL
  to read-all-into-RAM (300 random slices). Integrated (`DISK_STREAM=1`, gated off): corpus is mmap-backed (`CORPUS_CAP` can
  exceed RAM; only the current `STREAM_LEN` slice is resident), and each EPOCH RE-SAMPLES a FRESH `STREAM_LEN` slice from the
  big corpus — so `EPOCHS × STREAM_LEN` = unique tokens covered (toward GPT-2 data scale) without holding it all in RAM.
  Refactored `_retok`/`_resample` (stream rebuild per epoch), added `SEG_LEN` to bound sampling to the train head without
  slicing the mmap into RAM, capped the materialized held-out set (`VAL_CAP`), and fixed the memorization-check train sample
  to stay in the train region under mmap. IN-RAM PATH UNCHANGED when `DISK_STREAM=0` (default). CPU-smoke-verified end-to-end:
  epoch 2 drew a FRESH sample, memorization gap +0.110 (correct split), domains on, exit 0. Files: `datastream.py`, `self_organize.py`.
- **R35:** [USER: "fill the gaps and any issues already present"] Fixed the known gaps + real bugs, each CPU-verified:
  (1) WORLD-MODEL COLLAPSE BUG — the integration scaled the anti-collapse (variance/decorrelation) term by `WORLD_W`=0.1, so it
  ran at 1/10 strength → latent collapsed (std 0.24). Applied it at FULL strength via a separate `WORLD_VAR` (default 1.0).
  Verified: latent std 0.24 → **0.97** (healthy), and forward-pred vs persistence rose +13.6% → **+34.1%**. (2) RECON_W=0 WASTE
  (workflow finding) — guarded the per-step Reconstructor term with `RECON_W > 0`, skipping a redundant key-encode that was
  computed then multiplied by 0 on the default VERIFY=recon path. (3) MULTI-EPOCH GAP — the loop did a SINGLE pass; added a clean
  `EPOCHS=N` mechanism (build the stream ONCE, reset to start N times, `step` keeps counting) — memory-efficient vs the old
  STREAM_LEN=N×corpus resample. Verified: EPOCHS=2 does two passes, clean. STILL OPEN: async CUDA-stream rekey overlap (GPU-only,
  unverifiable in the CPU sandbox). Files: `self_organize.py`.
- **R34:** [USER: "I asked for NO COMPROMISE — you removed sections / used tested-and-approved. Build amortized rekey +
  other fixes. Do NOT disable domains, I assumed they weren't used."] Owned the critique: my prior "fixes" (SELF_ORG=0,
  SIG_MODE=bigram, lower WRITE_TARGET) were COMPROMISES (remove/downgrade), not the no-compromise engineering asked for.
  Corrected course — built the genuinely non-compromising fixes, all keeping FULL functionality: (1) AMORTIZED REKEY
  (`REKEY_AMORTIZED=1`, now default) — spread the SAME whole-store re-encode across steps via a rotating cursor instead of one
  spike every 300 steps: SAME per-entry refresh rate + freshness + full drift-survival, just no periodic stall; also skips
  re-keying entries that can't be READ (is_wrong/is_unverified) = pure-waste elimination, no retrieval loss. (2) SHIFT-GATED
  ENCODER (`ENC_EVERY_IDLE`/`ENC_SHIFT_WIN`) — throttle the SigEncoder when the stream is STABLE but SNAP BACK to dense updates
  on a detected boundary: full responsiveness, less redundant work. Both CPU-smoke-verified (domains ON — 38 live, no crash).
  DOMAINS CONFIRMED ON: `SELF_ORG` defaults to 1; the disable switch is now only an optional experiment (USER withdrew the disable).
  NOT done: async CUDA-stream overlap (#3) — GPU-only, can't verify in the CPU sandbox; noted as a future GPU optimization.
  Files: `self_organize.py`.
- **R33:** [USER: fix the SigEncoder; do domains do anything? disable them; why everything in the key?; continue world model]
  Traced + answered: (a) DOMAIN LABELS (`did`) = memory provenance (edit/unlearn by domain) + management — **NOTHING for
  prediction**; the SIGNATURE feeds fabric routing (that affects prediction), the label does not. (b) "everything in the key":
  `WRITE_TARGET=0.4` writes ~40% of ALL positions → 283k entries (not selective); each key is the model's full 512-d encode of
  the last 8 bytes (why rekey is costly). Lever: lower WRITE_TARGET (~0.1) → selective memory + smaller rekey. FIXES SHIPPED
  (both CPU-smoke-verified): (1) ADAPTIVE WARMUP — stop the 30k SigEncoder warmup when separation plateaus (`ENC_WARMUP_MIN`/`EPS`);
  smoke: stopped 1201/8000. (2) `SELF_ORG=0` — disable domain self-assembly (one bucket, no provenance/management); smoke: 0 live
  domains, run+unlearn clean. Zero-code levers also noted: `SIG_MODE=bigram` (kills SigEncoder training entirely), lower WRITE_TARGET.
  Honest: SELF_ORG=0 disables DOMAINS but the SigEncoder also feeds fabric, so its cost needs SIG_MODE=bigram/adaptive-warmup (separate
  lever). WORLD-MODEL FEEDBACK LINK BUILT (`WORLD_FEEDBACK=1`, gated off): the world model's forecast (population-blended predicted next
  latent) is projected and ADDED to the LM hidden state BEFORE fabric/head — so generation is conditioned on the forecast, no longer a
  side-head. CPU-smoke-verified end-to-end: LM still trains (loss 6.51→3.4, gap +0.393), world model still learns (+13.6% held-out), no
  crash. HONEST FLAG: latent std 0.24 < 0.5 (partial collapse in the tiny run) — anti-collapse weight may need raising; re-check at scale.
  Files: `self_organize.py`.
- **R32:** [USER: make world model separated like the rest; "a few agents" for the bottleneck; "physics need not be
  the target, just simulate the world"] RESULTS IN (updates the mid-build note): (1) SEPARATED world model `DynamicsPopulation`
  (world_model.py) — routed society of forward-dynamics predictors (route by fitness, blend, grow-on-plateau cloning fittest,
  soft-cull), integrated + gated (`WORLD_MODEL`/`WORLD_GROW`). Integration VERIFIED end-to-end (grew 1→3, soft-culled, held-out
  beats persistence +53.4%, no collapse, exit 0). HONEST NEGATIVE: vs a PARAM-MATCHED monolith on a toy multi-regime probe it's
  −5.1% (worse), routing purity 0.32 — separation does NOT improve accuracy here / does not specialize (regime is inferable from
  the latent, so one net suffices). Structural value (editability/growth/consistency — the stated reason) real; accuracy benefit
  UNPROVEN. Did NOT p-hack. Hypothesis to test: route the population by DOMAIN CONTEXT (sig), not z alone, so predictors specialize
  per-domain. (2) "Physics" reframed [USER]: metaphor for a FAITHFUL world SIMULATION; latent-dynamics already fits. (3) BOTTLENECK
  (5-agent workflow, empirical cProfile + analysis): NOT the reverse-embedder (Reconstructor OFF by default `VERIFY=selfcon` → zero
  — a red herring). It's the FORWARD **SigEncoder** contrastive (30k warmup up front + every-2-steps = ~61% of the loop) and
  **rekey_memory** (re-encodes the WHOLE store every 300 steps, grows with store → late-run stall), plus pure-Python
  `tokenizer.segment`. OPTIONS given (non-compromising): env-only (ENC_WARMUP↓/ENC_EVERY↑/REKEY_EVERY↑); structural (adaptive-warmup
  plateau-stop, adaptive ENC_EVERY on shift signal, rekey rotating-subsample+async = the only fix that kills O(store) growth). CPU
  profile caveat: a GPU profile would settle batch/hidden shrinks. NO fixes applied (confirm-before-action). KEY GAP: the world model
  is a SIDE-HEAD — not yet wired to condition generation/learning, so it doesn't improve the system YET. Files: `world_model.py`, `self_organize.py`.
- **R31:** [USER: robust evals; integrate world model; "is it vastly undertrained? I thought we need a few epochs"]
  DECISIVE FINDING (verified in code): the product loop does a SINGLE pass — `while i+WIN+1 < len(stream)`, no epoch loop;
  "epochs" only come from `STREAM_LEN > corpus` (build_stream resamples with replacement). `fw_small` STREAM_LEN=60M vs
  ~100-110MB corpus = **~0.5 epoch at completion, ~0.2 at the 100k checkpoint**. So EVERY run to date has been <1 epoch —
  we have NEVER trained past one pass, so the "is the architecture capable" question is genuinely UNANSWERED; the incoherent
  generation is an undertraining false-negative, not a verdict. FIX (config, not code): `STREAM_LEN = N×corpus` for N epochs
  (e.g. 400M ≈ 4 epochs). INTEGRATED the world model into the stream (`WORLD_MODEL=1`, gated off): reads OBSERVATION
  EMBEDDINGS (lowest layer = sense point, world not self) -> latent -> forward-predict next latent; added a ROBUST held-out
  eval (unseen VALC windows + persistence baseline + collapse check). CPU smoke-test (tiny, undertrained): beats persistence
  **+58.3%** on held-out, std 0.60 (no collapse), exit 0 — integration verified end-to-end. Files: `self_organize.py`.
- **R30:** [USER: "build the world model"; frustration that we produce talk + walk-backs, not results] BUILT the
  FIRST BRICK and VERIFIED it on CPU in-turn (real numbers, not a projection): `world_model.py` — the latent
  forward-dynamics core of the GENERAL world model. `observation --E--> latent --ForwardModel--> next latent`,
  JEPA/VICReg-style (predict the future REPRESENTATION, not tokens/pixels -> modality-agnostic + physics-like; variance+cov
  reg prevents collapse; residual predictor for stable rollout). Probe on a synthetic world with KNOWN linear dynamics:
  forward-pred MSE 0.0018 vs persistence 0.3073 (**beats "assume no change" by 99.4%**), hidden-state recovery **R²=0.988**,
  latent std 1.15 (no collapse), 5-step rollout bounded. MECHANISM WORKS. Scope honesty: proven on SYNTHETIC data only;
  NOT yet integrated into the real byte/token stream, NOT multimodal yet (single E interface), relational + generative
  bricks pending. Gated (`WORLD_MODEL=0`). Also this turn: fw_small @100k steps generation is INCOHERENT (conceded, no
  hedge) — undertrained + code-heavy data mix + small scale; machinery (tokenizer grew to 8192, checkpoints, 283k mem) works.
- **R29:** [USER: two new design directions; "do not write code yet, continue current work"] Two ideas CAPTURED
  (not built) as granular handoff files: (1) `active-learning-self-generated-closed-book-reproduction.md` — once competent,
  the system authors its own curriculum (reference → prompt → reproduce with reference REMOVED); the bridge that moves
  knowledge from retrieval/memory INTO weights, using the existing surprise gate as the signal (= context/self-distillation,
  Verification-by-reconstruction as scorer). (2) `partial-compartmentalization-provenance-without-partition.md` — info should
  be PARTIALLY isolated: tag by provenance (editable/removable) but LEAK across domains on purpose (kNN retrieval already
  isn't domain-restricted) because mixing drives creativity; independence must be a DIAL not maxed. Both connect tightly to
  existing structures (grounding, surprise, society/independence, regimes). Also this turn: fixed tokenizer visibility — the
  online minter grows 1024(seed)→VMAX live but only logged start+end; added a per-retok `[tokenizer @ step] vocab N/VMAX`
  line. Meanwhile the right-sized `fw_small` FineWeb run is live with `CKPT_EVERY=40000`.
- **R28:** [USER ran gdb rescue; run then "completed"] Rescue outcome + honest correction. pyrasite SILENTLY
  no-op'd; direct `gdb` injection SEGFAULTED (main thread was inside libcuda with the GIL released → `PyRun_SimpleString`
  crashed) but rolled back cleanly — run survived. I then WRONGLY told USER "the day is saved" on seeing `WHOLE SYSTEM RUN
  COMPLETE`; that bash line prints regardless of Python's exit. Reality: **no `runs/fineweb/ckpt.pt`, no save line, no
  eval/generation** — the process DIED at end-of-training-loop (most likely OOM on the final full-stream re-tokenization of
  the 1B-byte stream; possibly gdb aftermath) BEFORE the end-only save. Day's promptable model LOST. Lesson: end-only save
  is the trap; `CKPT_EVERY` (R25) would have banked step-80k+ checkpoints immune to an end crash — vindicated. Also fixed a
  real `prompt.py` bug: it read `CKPT` from ENV only, so the documented `prompt.py CKPT=runs/<tag>` fell back to `runs/ck`
  and errored; now folds `KEY=VALUE` argv into env. Domain fragmentation (~700 on web text): USER says it does NOT affect
  the system (prior context) → dropped as a concern (consistent with "over-seg OK if genuine"). Injection is a dead end for
  a CUDA loop; in-loop checkpointing is the right mechanism. Files: `prompt.py`.
- **R27:** [USER: end-only ≠ checkpointing; likely removed pre-git; live data must be retrievable] Accepted the
  framing (end-only save is NOT checkpointing) and that a pre-git removal is plausible+unverifiable (git only sees from the
  import commit; Phases 0–11 predate VCS). Corrected my overstated injection risk: the weights ARE live in the process and
  ARE retrievable — an injected-thread exception is NON-fatal (training continues), only the GPU→CPU copy carries real risk.
  Added `rescue_ckpt.py`: a `pyrasite`-injected full-checkpoint dump that frame-walks to `main()`'s locals and rebuilds the
  exact save dict → promptable via `prompt.py`. Best-effort, self-wrapped. This salvages the CURRENTLY running old-code run
  without killing it. (⚠ never `kill -USR1` the OLD process — no handler → default action terminates it.)
- **R26:** [USER: surprised checkpointing was absent; estimates always run long; can we inject a forced checkpoint?]
  Verified: mid-run checkpointing was NEVER present — `torch.save` has one commit (the initial import), so it saved only at
  loop end from day one (not a regression). Added CHECKPOINT-ON-DEMAND: a `SIGUSR1` handler sets a flag, the loop saves at
  the next safe step — `kill -USR1 <pid>` forces a checkpoint WITHOUT killing the run (pid is printed at start). Complements
  `CKPT_EVERY` (R25). For a currently-running OLD-code process the only salvage is `pyrasite` frame-walk injection (model/mem
  are `main()` locals, not globals) — risky under CUDA, given to USER with caveats. Estimate criticism ACK'd: `ESTIMATE=1`
  times PART A mechanics only and does NOT model online re-tokenization (the cost that dominates big streams) — it's a floor,
  not a prediction. Only `self_organize.py` changed (py_compile-verified).
- **R25:** [USER: fineweb run at 400k steps after ~a day] Two issues surfaced. (1) The fineweb command I gave was
  OVERSIZED for the question (does clean data fix generation): `VMAX=16384` + `D_MODEL_B=768` + `WIN=256` (GRU is sequential,
  so long windows hurt) + online re-tokenization over a 1B-BYTE stream = ~1–2M step target, ~2–4 days. My sizing error —
  the generation-quality check needs ~200MB, not 1GB. (2) BUG-CLASS GAP: `self_organize.py` saved the checkpoint ONLY at
  loop end, so a long run wasn't killable/promptable and a crash lost everything. FIXED: extracted `_save_ckpt()` + added
  `CKPT_EVERY=N` for mid-run saves (default 0 = end-only, unchanged). Recommend killing the oversized run and relaunching
  right-sized with `CKPT_EVERY` on. Only `self_organize.py` changed (py_compile-verified; no GPU here).
- **R24:** [USER ran the 12×-data run] Two findings: (1) DATA confirms as the lever — memorization gap
  +0.249 → +0.139, domain genuineness 1 → 9 genuine; architecture responds well to more data, still not at a capacity wall.
  (2) Generation showed `the/at movie/nn` POS-tag artifacts → traced to a REAL BUG in `fetch_data.sh`: its eng tag-stripper
  matched UPPERCASE tags only (`[A-Z$]`) but NLTK Brown tags in lowercase (`the/at`), so every Brown POS tag leaked in.
  FIXED the regex to `[A-Za-z$…]` (dates/URLs preserved; verified on a sample). The existing fast 85MB corpus is now clean —
  a proper re-run should generate tag-free text. fineweb stays reserved for a genuinely larger/dialogue corpus, not needed
  just for cleanliness. Only `fetch_data.sh` changed.
- **R23:** [USER ran the 5×-steps run] Decisive: (1) Verification store-wide failure is NOT undertraining —
  0.3% precision even at 30M stream → LOCKED as a dead end (per-candidate check only). (2) The short-run concern is
  RESOLVED for everything else — memory/composition/independence/generation all held or improved at 5× steps, so they're
  real, not artifacts. (3) NEW: the model is now DATA-limited (memorization gap +0.046→+0.249, memorizing ~7MB) — more
  steps is exhausted; MORE DATA is the lever. Recommend pivoting to a data-scaled run (fetch_data / 20GB fineweb) toward the north star.
- **R22:** [USER: memory should stay native+useful; short runs may mislead] Two clarifications recorded: (1)
  memory-native-and-useful is ALREADY proven (this run: memory +2.5 b/B, composition +0.41, editing local) — only
  autonomous store-wide wrong-DETECTION failed, a separable layer. (2) CAVEAT: all product-loop numbers are from ~4-min
  UNDERFIT runs (LM still falling, memorization gap +0.046), so noisy keys may be inflating reconstruction's FPR — the
  base-rate verdict on Verification is NOT final until a properly-trained run. Handed the user a longer well-trained
  command (fetch_data → data_big, higher STREAM_LEN) to de-risk. No code changed.
- **R21:** [USER ran the re-test] Post-hoc-fit fix did NOT recover Verification in the product loop (0.5%
  precision, ~unchanged). HONEST diagnosis: reconstruction hits the SAME base-rate wall as B — at ~0.26% injection its
  ~5% FPR on the noisy underfit store sinks precision. The standalone's 100% was an FPR≈0 projection that doesn't hold.
  No more blind patching. Reframed Verification (§7) as a strong PER-CANDIDATE discriminator (~98% pairwise) for the
  reconcile→understand gate, NOT a store-wide auto-delete; `VERIFY_SWEEP` stays off. Owned the earlier overclaim.
- **R20:** [USER: assume a fresh box; bug surfaced in the GPU run] Fixed a real bug: `run_full_unfrozen.sh` +
  `run_cl_test.sh` had a hardcoded `cd ~/overarching-package` (dead since the repo was flattened) that errored on every
  run — now `cd "$(dirname "$(readlink -f "$0")")"` (the script's own dir), so they work from any clone. `garry/` left
  untouched (frozen); `legacy/` skipped (unused). Test commands are now written fresh-box-safe (clone + deps + run).
- **R19:** [USER ran the full product-loop test] Verification FAILED in the real loop (0.3% precision vs the
  standalone's 100%) — diagnosed: joint Reconstructor training on a churning store (online re-tokenization + rekey +
  underfit base) = a moving target. FIXED: `verify()` now FITS the Reconstructor POST-HOC on the final settled store
  (`VERIFY_FIT=3000`); joint training off by default (`RECON_W=0`). CPU-smoke-tested. Awaiting a GPU re-test (sweep OFF
  until re-confirmed). Honest lesson recorded in §7: the standalone was necessary but not sufficient; the full-loop test caught the integration flaw.
- **R18:** [USER: build whatever you recommend up to a GPU test] Built `keystone_probe.py` and VALIDATED the
  keystone on CPU: functional (operation) similarity IS separable from content similarity — a transfer-coded embedding
  (z from one input→output pair must transform NEW content under the same op) hits k-NN op-purity 0.80 vs 0.50 surface
  (chance 0.20, gap +0.30). Naive same-input coding gave only 0.61 (z cheated with content) — cross-content TRANSFER is
  the key, and it concretely realizes the design's "modification before embedding" step. De-risks routing/reuse. Recorded in §7;
  updated the routing / unifying-primitive / what-is-missing direction files. Toy synthetic — real integration is future.
- **R17:** [USER: continue building] Turned Verification from detect-only into an ACTIONABLE capability (the
  old B stayed detect-only because ~1% precision made deleting suicidal): `memory.read()` now excludes `is_unverified`
  entries (no-op until `verify()` runs), and `VERIFY_SWEEP=1` DELETES them (detect-AND-remove). Opt-in, memory-only,
  CPU-smoke-tested (recon+sweep and the default both run; default unchanged). Deliberately did NOT stack the riskier
  deferred items (`retire_stale`, release-don't-kill) — they touch the collapse-prone online-tokenizer / fabric and need a careful, tested pass.
- **R16:** [USER ran the GPU A/B] Verification CONFIRMED on a GPU-trained model: reconstruction AUC 0.980 vs
  B 0.907, precision@1% 100% vs 36.9%, recall 32% vs 65% — the reframe holds on real trained data. Recorded in §7. (User
  also asked where the "large database" went: the repo ships only the small bundled `data/train/` ~7MB; the ~85MB/GB
  corpora are produced on-demand by `fetch_data.sh`/`fetch_big.py` and are NOT committed — the test capped `PERDOM=400000`.)
- **R15:** [USER: a console script, repo is private] Added `verify_console_test.py` — self-contained A/B
  (torch + `data/` only, no repo imports, no git pull; paste-able via `exec(open(...).read())`). Building it caught a
  REAL methodology error: the first version injected 50% cross-domain corruption = the EASY regime B already handles
  (B ~97%). Rewrote it FAITHFUL: surprise-gated genuine negatives (B's real failure mode) + base-rate-honest metrics
  (AUC, precision@1%). Result on CPU real data (undertrained toy): reconstruction **AUC 0.978 vs B 0.903**, precision@1%
  **100% vs 30.5%** — the reframe holds (reconstruction is decoupled from surprise, doesn't false-positive on
  surprise-gated genuine). Recorded in §7. GPU run still the real validation. torch stays installed for CPU probes.
- **R14:** [USER: rejected the strict per-domain quota] Replaced the rejected faded-knowledge quota with a
  structural direction: memory pressure → GROW the domain's experts / retrain / or split the domain (consistent with the
  growability invariant, not a foreign cap). Renamed the designed-but-not-built file, fixed §7 + recommended-next-steps.
  Also added the copy-paste Verification test to `handoff/COMMANDS.md`. No code changed.
- **R13:** [USER: build Verification + fix broken, as wide as comfortable before testing] FIRST CODE CHANGE.
  Built **Verification** (`verification.py`): a `Reconstructor` (reverse embedder) that CROSS-reconstructs the expected
  token-code from the context key — reconstruction error = the verify signal, decoupled from surprise. Wired into the
  loop ADDITIVE + OPT-IN (`VERIFY=recon`, default `selfcon` → zero change to existing runs): trained in the LM loop,
  `verify()` scores entries, `memory.is_unverified`/`set_recon` added, and the wrongness test now reports recon precision
  vs the old self-consistency B. Validated on CPU: the standalone probe separates genuine vs corrupt at **AUC ~0.93**
  (the naive joint-autoencoder gave only ~0.65 — caught + fixed to cross-reconstruction before any GPU run); end-to-end
  smoke ran (14.6% precision on a tiny undertrained CPU model vs old B ~1%). REAL validation = the GPU A/B (see §7 / handoff).
  Deferred (comfortable-before-test): retire_stale, release-don't-kill, memory-pressure response — behind the first green GPU test. torch installed in-sandbox for the probe.
- **R12:** [USER: confirmed the names] LOCKED the naming pass: B → **Verification**; **Fabric** RETIRED →
  **Router** (selects) + **Compositor** (blends outputs); population grades **Expert → Sub-skill → Tool-expert** confirmed;
  **Domain** kept; **Sense = a MODALITY** (the multimodality axis — one sense = language today; mic → audio) — NOT the
  polysemy idea (that's provisionally "Meaning"). Propagated through STATE/README/CL_TESTBED/GLOSSARY/STRUCTURES, renamed
  the decision file, and fixed the Sense-vs-polysemy confusion in the design directions. Code identifiers unchanged (renamed at build time). No code changed.
- **R11:** [USER: clarify what structures ARE + name them first; then full Verification integration + fix broken] Started a
  NAMING PASS — added `handoff/STRUCTURES.md` clarifying every structure (loop stages, signals, encoders incl. the new
  Reconstructor, the populations at each grain, routing, memory) with proposed canonical names + the overloaded terms to
  settle (Fabric, population grades, Domain-vs-Sense). Name "V" NOT locked pending this. Build approach chosen by USER:
  full Verification integration + fix anything broken — queued behind the naming. No code changed.
- **R10:** [USER: rename B; document + set handling; then build+test] Phase 1 (docs): RENAMED B (wrongness) →
  **Verification** — reconstruction-based, decoupled from surprise; propagated through STATE/README/CL_TESTBED/GLOSSARY and
  superseded Q3 (it's now a build, not a decision). Added `decisions/B-renamed-to-Verification-...`, the learning-signal HANDLING
  spec (`design-directions/learning-signal-classification-surprise-and-reconstruction.md`, incl. the surprise×reconstruction
  2×2), and the build-readiness GAP LIST (`design-directions/what-is-missing-from-the-idea-before-it-is-buildable.md`).
  Historical/frozen docs keep "B". Phase 2 (build+test) plan presented; no code changed yet.
- **R9:** [USER: added to the vision] (1) Clarified SURPRISE is a mechanic for ONGOING LEARNING, not a
  wrongness/truth signal — casting it as wrong-detection is the category error behind B's ~1% precision; verification
  belongs elsewhere. Added `decisions/surprise-is-a-learning-driver-not-a-wrongness-or-truth-signal.md` + noted on the B
  decision. (2) New direction REVERSE EMBEDDERS — decode from the embedding space for THOUGHT, VERIFICATION
  (reconstruction, not surprise), TRAINING; forward=learn / reverse=think-verify symmetry; cross-ref'd the unifying primitive. No code changed.
- **R8:** [USER: added to the vision] Three more design directions: (1) experts can be TOOL CALLS / SCRIPTS,
  self-authored when a procedure recurs (crystallize-on-repetition, like tokens); (2) reusability comes from ROUTER +
  DISCOVERY + SIMILARITY — the router acts as an EMBEDDER (input+source → modification → embed → nearest expert / learned
  recognition), giving transfer to prior-unknown parts; the open crux is CONTENT vs FUNCTIONAL similarity in that space;
  (3) filed the UNIFYING-PRIMITIVE hypothesis (subtokenize→embed→match→discover→crystallize at every layer: tokens, senses,
  domains, experts, tools) — the "much smaller architecture" thread. No code changed.
- **R7:** [USER: refined the vision] Two refinements in `handoff/design-directions/`: (1) the full task should
  NOT be done alone — it is SUBCONTRACTED / spread via the router base (division of labor at the sub-task level), which
  REVISES the independence-loss premise; redundancy/safety then comes from shared reusable SUB-SKILLS, not whole-task
  generalists. Flagged on the GLOSSARY independence-loss entry. (2) senses live at the LOWEST tokenizer layer, DISCOVERED
  on unknown/unusual input (surprise-triggered), BEFORE reconciliation + understanding. No code changed.
- **R6:** [USER: elaborated the vision] Captured two design DIRECTIONS (new `handoff/design-directions/`):
  (1) the expert society should be a redundant/interchangeable BASE **with emergent subspecialties** — redundancy for
  safety-against-incorrect-removal + shared sub-task structure, specialization emerging by task decomposition; this makes
  Q-regime a design challenge (emergent specialization without losing redundancy) and couples it to Q0. (2) knowledge base
  = EditableMemory + built-in retrieval + a polysemy-aware EDITABLE embedding (multiple sense-vectors per surface form,
  with sense selection). Threaded the direction into Q-regime. No code changed.
- **R5:** [USER: answered my strategic questions on the system] Captured the NORTH STAR — small, learning,
  reasoning, ever-expanding/updatable model; growability is the SACRED INVARIANT; language is a benchmark; multimodality
  + an observability dashboard are long-horizon goals; from-scratch for novelty+ownership; rented H100 as-needed; success
  priority convo→sentence-gen→architecture→shipping. Wrote `handoff/NORTH_STAR.md`, updated §1/§3, added multimodality +
  dashboard as `designed-but-not-built/`, noted north-star implications on Q0/Q-regime. No code changed.
- **R4:** [USER: fold the prior-context material in; rebuild STATE.md + self-verify] Rebuilt this ledger from the
  context export: restored the real history (§6 phases), replaced the stale/misleading §7, added the self-verify protocol
  step (§ protocol #2), folded the new architecture decisions into §2, refreshed §3/§4/§5. Folded the export into `handoff/`
  as atomic files: `GLOSSARY.md`, `COMMANDS.md`, `history/` (12 phases), `designed-but-not-built/` (5), new `decisions/`,
  new `process/`, updated `open-questions/` (Q0/Q3 recs; Q1 management → RESOLVED; added Q-regime, Q-compute). Corrected my
  earlier FALSE "T5–T32 history unrecoverable" note — it was recovered by the prior context. No code changed.
- **R3:** [USER: separate folder for context exchange] Created `handoff/` (bootstrap + atomic process/decisions/open-questions/migrations).
- **R2:** [USER: file docs + reconciliation] Added `docs/FILES.md` + `docs/HANDOFF.md`; reconciled stale STATE refs; fixed README output paths + `cl_bench.py` header.
- **R1:** [USER: add the package to the hub] Added the 121-file package at repo root + `.gitignore`; branch became the repo default.

### Project history — reconstructed as Phases (see `handoff/history/` for detail)
- **P11:** Context export to a new chat (this migration).
- **P10:** Scaled data (`fetch_data.sh`/`fetch_big.py`); resolved throughput (`BATCH_W`) + data blockers; two USER corrections
  (grounding must be internal-only; no pretrained base). Compute is now the binding constraint.
- **P9:** Language-goal check — model is UNDERFIT not overfit; declined dropout/decay as defaults; added validation split + memorization check.
- **P8:** Reached real specialization — grounded routing keys + sharper `ROUTE_T` → concentrated deletion cost (modularity regime).
- **P7:** USER rejected cascade deletion → release-not-kill semantics; built the affiliation map (0 exclusive experts); corrected "uniform = redundancy, not specialization."
- **P6:** Ported the legacy fabric (`FABRIC=1`); mixture→SOCIETY rewrite + prediction-level ensembling fix → best run "Garry" (1.967, −0.0009, readable generation).
- **P5:** Flat 1:1 expert-per-domain bank — measured NET NEGATIVE; motivated the fabric pivot.
- **P4:** Online tokenizer (`TOK_ONLINE`) → domain collapse; root cause = signature encoder reading the churning TOKEN stream; fix = read BYTES. Online minting exonerated; GRU default.
- **P3:** Transformer option + timing probe; fixed a silent 30-min stall (stdout buffering — fix put in code, `line_buffering=True`).
- **P2:** First generation results; expanding tokenizer confirmed doing the work; caught a "claimed-but-not-committed" repetition-penalty fix and actually committed it.
- **P1:** Cleanup; moved 57 files to `legacy/`; salvaged the adaptive write-gate; swapped static→expanding tokenizer [USER]; created this ledger.
- **P0:** Foundational build (before the export author had visibility): C→B→A loop, memory-delete ≫ weights-unlearn, replay > memory on forgetting, self-assembly ~0.96, B fails realistic. Several honesty self-corrections set the tone.

## 7. Measured results (authoritative — from real GPU runs on the bundled eng/py/num/c corpora)
> Collateral = mean bits/byte change on OTHER processes after an edit; near-zero = surgical. These supersede the earlier
> "T2 dev run" numbers. Latest ACTUAL GPU numbers are Garry + modularity; everything after P10 (grounding, `BATCH_W`,
> `fetch_big.py`) is built + CPU-tested but NOT yet GPU-run.

- **Headline (A):** delete one EXPERT's weights = **−0.0009** collateral (Garry) / **+0.127 concentrated** (modularity);
  delete MEMORY rows by provenance = ~0.02–0.03; gradient-ascent weights-unlearn = **~22–25**. Weight-deletion ≤ memory-deletion, ~1,000–25,000× < gradient-ascent.
- **Editability:** memory-delete ~4,400–14,400× faster and ~800–1,260× less collateral than weights-unlearn. Consistent across the whole project.
- **Forgetting:** replay wins (+0.36) over memory (+1.2–1.7) — memory's value is EDITABILITY, not forgetting.
- **Best end-to-end (Garry, redundancy):** **1.967 b/B**; readable generation (real C, prose, numerics); ~468 domains purity 0.92; tokenizer 256→6241 live; B recall 96% / precision ~1%.
- **Modularity (spec2):** **2.002 b/B**; deletion +0.127 concentrated (~7× ratio across processes); uneven per-domain expert usage; still 0 exclusive experts (42–66% domain coverage each).
- **Self-assembly (C):** purity 0.90–0.96 vs 4 hidden processes; boundary precision ~0.40–0.44 (fires 2–3× too often) — HARMLESS (composition below).
- **Composition:** GLOBAL retrieval beats siloing to nearest segment by +0.03…+0.56 b/B → over-segmentation is harmless.
- **Tokenizer:** ~−0.5 b/B vs raw bytes, every comparison. Online == frozen at matched vocab/memory.
- **Verification (formerly B):** the old surprise-based B measured recall 92–96% / precision ~1% every realistic run (never
  resolved — surprise ≡ detection signal). **Reconstruction Verification VALIDATED (CPU, `verify_console_test.py`, real
  corpora, undertrained toy GRU):** in the REALISTIC regime (surprise-gated genuine negatives — the hard case B fails on),
  reconstruction **AUC 0.978 vs B 0.903**, and precision-at-1%-base-rate **100% vs 30.5%** (reconstruction does NOT
  false-positive on surprise-gated genuine entries — the exact B failure). **CONFIRMED on a GPU-trained model [USER run, 8000
  steps, cuda]: AUC 0.980 vs 0.907, precision@1% 100% vs 36.9%, recall 32% vs 65%.** (Still the simplified standalone
  harness — small GRU, no fabric/tokenizer; the full product-loop `run_verify_test.py` is the last mile.) NOTE: the naive
  50%-cross-domain test is the EASY regime B already handles (B ~97% there) — not informative.
- **Verification PRODUCT-LOOP test [USER GPU runs] — reconstruction does NOT beat the BASE-RATE wall for store-wide
  detection.** First wiring 0.3% precision; after the POST-HOC-fit fix (fit the Reconstructor on the settled store,
  `VERIFY_FIT=3000`, `RECON_W=0`): **0.5% precision / 9.4% recall — essentially unchanged.** Diagnosis: at the realistic
  ~0.26% injection, reconstruction fires on ~5% of the 292k genuine entries (noisy, token-level, UNDERFIT base) → base
  rate sinks precision to ~0.5% — the SAME wall B hits (1%). The standalone's AUC 0.980 / 100%@1% was a projection
  assuming FPR≈0, which does NOT hold on the heterogeneous real store. **HONEST REFRAME:** reconstruction is a strong
  PER-CANDIDATE / pairwise discriminator (rank 1 corrupt vs 1 genuine ~98%) — its home is the reconcile→understand gate
  (verify ONE provisional sense/expert), NOT a store-wide auto-delete (`VERIFY_SWEEP` stays OFF). Store-wide autonomous
  wrong-detection remains UNSOLVED (B and reconstruction both die on base rate); the standing rec to lean on A
  (edit-on-command, proven) holds. **CONFIRMED not an undertraining artifact [USER, 5× steps]: precision stayed 0.3% at
  30M stream (0.3→0.5→0.3 across 3 runs). Store-wide Verification is a genuine dead end — LOCK it as a per-candidate check.**
  (Contributing factor: token-level 8192-vocab reconstruction is harder than the byte-256 standalone, but base rate dominates.)
- **Short-run "misleading" concern — RESOLVED for the rest [USER, 5× run]:** at 30M stream the core results HELD/improved
  and are NOT artifacts — memory +2.1 b/B, composition +0.54, expert-deletion collateral +0.034, fabric+memory 1.951 b/B,
  generation visibly more coherent. BUT the model is now DATA-limited (memorization gap +0.046 → +0.249, starting to
  memorize the ~7MB corpus). More STEPS is exhausted; the real lever for quality + clean keys is MORE DATA (fetch_data / the 20GB fineweb).
- **Data-scaling run [USER, 12× data, fetch_data ~85MB]:** DATA confirmed as the lever — memorization gap +0.249 → +0.139,
  domain genuineness 1 → 9 genuine (silhouette +0.06 → +0.12); the architecture responds well to data. Absolute b/B across
  runs is NOT comparable (different corpora). The base GRU is still underfit (LM curve falling), not yet at a capacity wall.
- **fetch_data.sh POS-tag bug — FOUND & FIXED [R24]:** the 12× run's generation emitted `the/at movie/nn` artifacts. ROOT
  CAUSE: the eng-corpus tag-stripper was `s#/[A-Z$]…#` (UPPERCASE only), but NLTK's Brown corpus tags tokens in
  **lowercase** (`the/at`, `movie/nn`) — so every Brown token's POS tag leaked into training. Fixed to `[A-Za-z$]` (digits/dots
  excluded so `12/25` and URLs survive; verified on a Brown-format sample). Was a data-quality bug, NOT architecture. The
  same 85MB `fetch_data.sh` corpus is now clean — no need to switch to fineweb just for cleanliness (fineweb/`fetch_big.py`
  remains the path for a genuinely LARGER, dialogue-bearing corpus later).
- **Keystone (functional vs content embedding) — MECHANISM VALIDATED (CPU, `keystone_probe.py`):** an embedding trained as
  a REUSABLE code that must TRANSFER across content (derive z from one input→output pair, require it to transform a NEW
  input under the same op) organizes by FUNCTION — k-NN op-purity **0.80 vs 0.50 surface** (chance 0.20), gap +0.30. So
  functional similarity IS learnable (the make-or-break for routing/reuse), and the "modification before embedding" step
  is concretely: cross-content transfer training. Toy synthetic; the real integration is future.
- **Management ablation:** no prediction-quality cost ON vs OFF; its job is bounding domain-record growth.
- **Non-stationary (`PHASED=1`):** system adapts (domains grow/cull, memory bounded, editing clean on active + faded) — BUT bounded `EVICT=recency` fully evicts a faded process's knowledge; `EVICT=usage` does not fix it (faded ≡ least-used). A per-domain quota is REJECTED [USER]; the direction is memory-pressure → grow experts / retrain / domain-split (see `handoff/designed-but-not-built/memory-pressure-...`). Unbuilt.
- **Data reality:** product loop trained on ~3.7MB effectively seen — thousands× less than a small LM. Fluent language was never in reach at that scale, independent of architecture.
- **Scale gap (stated to USER):** ~300× more tokens for GPT-2-small-level coherence (which still can't converse); ~3 more orders of magnitude + dialogue data + instruction-tuning/RLHF for real conversation. None of that exists yet.
