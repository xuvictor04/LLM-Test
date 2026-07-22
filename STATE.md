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
- ACTIVE LEARNING — self-generated CLOSED-BOOK curriculum: at a competence gate the system authors its own items
  (reference article → prompt → reproduce WITHOUT the reference) and trains to close the open-book/closed-book gap
  (drives knowledge memory→weights). Mechanism open; tension with the editability invariant flagged.
  See `handoff/design-directions/active-learning-self-generated-closed-book-curriculum.md`. [USER, R21]
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
- **R21 (current):** [USER: added to the vision — "do not write code, just update the context handler"] Captured a new
  design direction: **ACTIVE LEARNING via a self-generated closed-book curriculum** — once the system reaches a certain
  competence level it authors its own items (reference article → prompt → reproduce the output WITHOUT the reference), and
  is graded on regenerating the target once the reference is removed. Cast in the project's own terms: it is the REVERSE /
  reconstruction path (Verification) at the passage/task level, and the training-time twin of internal-only grounding —
  alternate open-book/closed-book and train to CLOSE THE GAP, driving knowledge from the editable store into weights.
  Flagged the open mechanism (the competence GATE; scoring; where the reference comes from) and the real TENSION with the
  editability invariant (consolidating into entangled base weights could forfeit clean deletion — candidate fix:
  consolidate into an EXPERT, still a deletable unit). Wrote `handoff/design-directions/active-learning-self-generated-closed-book-curriculum.md`
  and added it to §3 FUTURE DIRECTIONS. NO code changed. Belongs after the first green GPU-scale run (needs fluency first).
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
- **Verification PRODUCT-LOOP test [USER GPU run] — FAILED as first wired, then FIXED:** in the full loop (fabric +
  online tokenizer 256→6176 + rekey + underfit base 7.2 b/B) reconstruction gave **0.3% precision / 8.3% recall** (worse
  than B's 1%) and `VERIFY_SWEEP` gutted the store (~21k of 292k deleted, mostly genuine). Root cause: the Reconstructor
  trained JOINTLY on a CHURNING store (a moving target) → noise. FIX: fit it POST-HOC on the FINAL settled store
  (`VERIFY_FIT=3000`; `RECON_W=0` default, joint training off) — reproduces the standalone's winning condition. **Awaiting a
  GPU re-test** (keep `VERIFY_SWEEP=0` until precision is re-confirmed). Standalone (AUC 0.980) stands; only the integration was broken.
- **Keystone (functional vs content embedding) — MECHANISM VALIDATED (CPU, `keystone_probe.py`):** an embedding trained as
  a REUSABLE code that must TRANSFER across content (derive z from one input→output pair, require it to transform a NEW
  input under the same op) organizes by FUNCTION — k-NN op-purity **0.80 vs 0.50 surface** (chance 0.20), gap +0.30. So
  functional similarity IS learnable (the make-or-break for routing/reuse), and the "modification before embedding" step
  is concretely: cross-content transfer training. Toy synthetic; the real integration is future.
- **Management ablation:** no prediction-quality cost ON vs OFF; its job is bounding domain-record growth.
- **Non-stationary (`PHASED=1`):** system adapts (domains grow/cull, memory bounded, editing clean on active + faded) — BUT bounded `EVICT=recency` fully evicts a faded process's knowledge; `EVICT=usage` does not fix it (faded ≡ least-used). A per-domain quota is REJECTED [USER]; the direction is memory-pressure → grow experts / retrain / domain-split (see `handoff/designed-but-not-built/memory-pressure-...`). Unbuilt.
- **Data reality:** product loop trained on ~3.7MB effectively seen — thousands× less than a small LM. Fluent language was never in reach at that scale, independent of architecture.
- **Scale gap (stated to USER):** ~300× more tokens for GPT-2-small-level coherence (which still can't converse); ~3 more orders of magnitude + dialogue data + instruction-tuning/RLHF for real conversation. None of that exists yet.
</content>
