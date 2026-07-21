# STATE.md — living project ledger

**PROTOCOL (binding, for the assistant):**
1. Update this file BEFORE responding, every turn. Add to the Changelog (§6); edit any section that changed.
2. Before making ANY choice, check §2 (Decisions) and §5 (Config). If the user decided it, follow it — never override
   with a default. If they did NOT decide it, either ASK, or label it `[my default]` in the reply so they can correct.
3. Keep the explicit **Included / Not included / Deferred** accounting (§3) current — report adds/removes/omissions.
4. `[USER]` = the user's explicit call (do not override). `[me]` = my default/assumption (must be flagged when relied on).

---

## 0. GARRY — frozen milestone checkpoint
`garry/` is a FROZEN, independently runnable snapshot of the T33 state (numbers in `garry/GARRY.md`): the first version
where the whole architecture works at once and expert-deletion collateral hit **-0.0009** with end-to-end **1.967**.
NOTE: root is T33's DESCENDANT, not a byte-copy — it adds a later retrieval-grounding / source-`pos` feature set
(`cl_bench.py`/`tokenizer.py` are identical; see `docs/FILES.md`).
- Do NOT edit `garry/`. Development continues in the package root.
- It reads the shared corpora via `DATA_DIR=../data` and namespaces its runs (`~/garry.txt`, `runs/garry/`), so it
  never collides with development runs. `garry/GARRY.md` records the exact config, the measured results, and the
  known limitations.
- Purpose: a known-good reference to fall back to and to compare every later change against.
- Side benefit of building it: `DATA_DIR` is now configurable in both `self_organize.py` and `cl_bench.py`, which
  also closes the long-standing "point it at a bigger corpus" gap.

## 1. What this is
**TWO CHARACTERIZED REGIMES (choose per use case):**
- **REDUNDANCY** (`ROUTE_T=1.0`, = frozen `garry/`): **1.967** b/B, expert deletion FREE (-0.0009), no specialization.
- **MODULARITY** (`ROUTE_GROUNDED=1 ROUTE_T=0.3`): **2.002** b/B, expert deletion **+0.127 CONCENTRATED** on the
  domains that expert served -- real specialization for +0.035 b/B.

Autonomous continual-learning system. One stream (bytes, or tokens if the expanding tokenizer is on) →
self-ASSEMBLE domains (C) → detect WRONG info (B) → EDIT / unlearn by provenance (A).
Code: `memory.py` (the store), `self_organize.py` (product loop), `cl_bench.py` (mechanics). Deliverable: this package + zip.

## 2. Decisions
### Standing directives [USER]
- Report every add/remove/change AND every omission, explicitly.
- End each build with a Recommended Next Step + WHO does it (me = build / user = test or decide). Flag when it's the user's call.
- Everything built for the UNFROZEN final product; frozen only as a labeled TESTING baseline.
- Estimate wall-clock BEFORE any GPU run.
- Bias toward pruning / simplification.
- Over-segmentation is fine IF domains are genuine; self-assembly is a hard requirement.
- **Stop defaulting to my own choices; keep this ledger current; flag my defaults.** [USER, current turn]

### Design decisions [USER]
- Memory key = the model's OWN representation (unfrozen) + periodic re-keying. Frozen key = baseline only.
- Wrongness (B) = SELF-CONSISTENCY (not the old retrieval running-mean). B is **DETECT-ONLY** — it is broken in the
  realistic regime (~1-2% precision across runs), so it reports but does NOT delete.
- Genuineness = SILHOUETTE (coh+sep-1), not size — but the COUNT is arbitrary; PERFORMANCE is what matters.
- Write-gate signal is SURPRISE (1 − p_model(true token)); the name "novelty" was a misnomer, renamed.
- Tokenizer = the EXPANDING `DynamicTokenizer` (online mint-on-repetition), NOT the static ByteBPE.
- Dead code removed (reverse model, retrieval-wrongness); legacy LM-era code archived in `legacy/`, not deleted.
- **Full test = ALL ideas ON** in `run_full_unfrozen.sh`: expanding tokenizer + adaptive gate + unfrozen model key +
  self-consistency B (detect-only) + silhouette + composition + performance + generation. [USER]
- **Cross-domain interactions (in generation / retrieval) are OK and EXPECTED** — not a bug to fix. Composition is a feature. [USER]
- **Memory MANAGEMENT (merge/cull/reassign + turnover) and EDITING (A) are the important part for continual learning.** [USER]
- **Tokenizer mints DURING training (ongoing), not just a pre-pass.** [USER] -> implemented as `TOK_ONLINE=1`.
- **Experts are INDEPENDENT AGENTS blended at a router layer; nothing frozen; new experts cloned from the live base;
  DOMAINS are collections of experts; independence is what makes removal clean.** [USER] -> `SOCIETY=1`.
- **Build expanding/selective per-domain EXPERTS + router, accept the weights-editability tension.** [USER] -> `EXPERTS=1` (superseded by the Fabric society; `EXPERTS=0` by default).
- **Experts+domains are DUAL populations; the router is a FABRIC that reroutes within itself and node->node.** [USER] -> `FABRIC=1`.
  -> Priority shifts toward these as the CL-defensible core (B is broken; generation is base-model-limited).

## 3. Included / Not included / Deferred
### INCLUDED — active, in root
- `memory.py` — EditableMemory: surprise-gated write, model|frozen key, re-key, delete / delete_src (A),
  self-consistency `is_wrong` (B), optional adaptive gate, stats.
- `self_organize.py` — product loop: learned-signature assembly (C) → B detect-only → performance (model vs model+mem)
  → cross-segment composition → generation → unlearn a process (A); optional expanding tokenizer.
- `cl_bench.py` — mechanics: forgetting vs replay, editability (memory-delete vs weights-unlearn), drift, wrongness.
- `run_full_unfrozen.sh` (whole system, one command; now also writes a checkpoint), `prompt.py` (message the
  trained model interactively), `run_cl_test.sh`, `README.md`, `CL_TESTBED.md`, `STATE.md`, `tokenizer.py`, `data/`.
- `docs/FILES.md` — file-by-file map (read from source). `docs/HANDOFF.md` — pick-up-here guide + reconciliation ledger.
- `handoff/` — chat-to-chat context-exchange folder [USER]: blank-chat bootstrap (`handoff/README.md`) + atomic one-idea
  files under `process/`, `decisions/`, `open-questions/`, `migrations/`. Filename-as-index; points back to this ledger.

### NOT INCLUDED — built but OFF by default, or archived
- Frozen memory: present, baseline only (not the product path).
- Adaptive write-gate: **ON in `run_full_unfrozen.sh`**; still `WRITE_ADAPTIVE=1/0` toggleable, OFF for standalone byte
  baselines. (Fixed this turn: a ceiling `gate_ceil` so it can't overshoot and starve writes; test injections bypass the gate.)
- Expanding tokenizer: **ON in `run_full_unfrozen.sh`** (`TOKENIZER=1`); byte-level still the standalone default.
- **Full run (`run_full_unfrozen.sh`) turns EVERYTHING on by default**: online tokenizer + experts + adaptive gate + all tests.
- ONLINE tokenizer growth (`TOK_ONLINE=1`): mints throughout training (model pre-sized to VMAX, stream re-tokenized as
  vocab grows, byte-coord metrics). Built + verified (seed 400 -> grew 624 live). OFF by default; enable per run.
- `retire_stale` (tokenizer un-merge / shrink): exists in `DynamicTokenizer`, NOT wired into the loop.
- ~55 legacy files in `legacy/` (Barry/Greg LM architecture, `mp_tokenizer.py`, old data/harness) — unused.

### DEFERRED — awaiting a user decision (see §4)
- B redesign (corroboration/contradiction) vs dropping autonomous detection.
- Bigger base model / Transformer for fluent generation.
- Concurrent-online tokenizer growth (currently pre-pass) + live `retire_stale`.

## 4. Open questions — awaiting the user's call (I should ASK, not default)
0. **What TYPE of evolution for the experts?** Current scheme is `[me]` (never asked): steady-state (no generations),
   mutation-only (no crossover), LAMARCKIAN (gradient-trained weights are inherited by offspring), niche-based
   speciation (vigilance radius `EXPERT_NEW_DIST` -> new expert when nothing matches), and **fitness = OCCUPANCY**
   (how often the router picks it), NOT task performance. Biggest weakness: a frequently-routed BAD expert still wins.
   Alternatives: (a) Darwinian performance fitness (per-expert loss reduction); (b) tournament instead of argmax;
   (c) crossover between adapters; (d) self-adaptive mutation rates; (e) age-layered protection for young experts.
1. ~~Test the CONTINUAL aspect~~ BUILT: `PHASED=1`. Remaining sub-item: a management ON-vs-OFF ablation to put a
   number on how much management matters. [previously:] the testbed distribution is FIXED
   (4 processes throughout). Where management + editing earn their keep is a NON-STATIONARY stream (domains enter/leave
   over time). Proposed test (design `[me]`): phased stream; measure the assembler opens/culls domains, memory stays
   bounded + useful across the shift, editing is clean on both active + faded processes. Optional: management ON/OFF ablation.
2. ~~Online minting hurts~~ RESOLVED: online == frozen at matched vocab+memory. The GPU regression was undertraining
   (Transformer @ 8333 batch-1 steps) + small vocab (1785 vs 4096). Fix = GRU + train longer + grow vocab to 4-8k + bigger
   MEM_CAP. Online minting KEPT. (Transformer would need batched training -- a separate, less-online design -- if ever wanted.)
3. **B direction:** attempt a corroboration-based B (hard, speculative), or cut B and ship clean-unlearning-on-command (A already delivers)?
4. ~~Base model~~ ADDRESSED [USER: expand to H100]: added a `MODEL=transformer` option (scales to the H100). Whether
   it becomes the default depends on the H100 run result.
5. ~~Tokenizer default~~ RESOLVED [USER]: ON for the full test. (Standalone modules keep byte-level default for baselines.)

## 5. Config — run-command values, provenance
Unless a value is marked `[USER]`, treat it as `[me]` and flag it when I put it in a command.
- Tokenizer: `VMAX 4096, MIN_PAIR 50–80, MAX_TOK 16, TOK_DROPOUT 0.0, GROW_PASSES 8–10, TOK_GROW_CAP ~1.5M` — all `[me]`.
- Model/run: `D_MODEL 256, STREAM_LEN 1.5–2M, WIN 96–128, MEM_CAP 300k, ENC_WARMUP 30k, EVAL_N 128` — all `[me]`.
- Wrongness: `WRONG_SWEEP 0` (detect-only) `[USER-aligned]`; `WRONG_INJECT 8` `[me]`.
- Generation: `GEN_LEN, GEN_TEMP` — `[me]`.
- Data: real corpora eng/py/num/c `[USER]`; `CORPUS_CAP 2M` `[me]` (bundled corpora ~1-3M bytes each = the ceiling on "large").
- H100 TRANSFORMER proposal `[me]`: `MODEL=transformer D_MODEL=512 LAYERS=6 HEADS=8 MAXLEN=512 VMAX=8192
  STREAM_LEN=3M MEM_CAP=800k ENC_WARMUP=60k CORPUS_CAP=3M`. NOTE: online batch-1 training underutilizes the H100
  (a Transformer wants big batches) but completes in reasonable time; the PROBE prints the real per-step estimate first.
  Bundled corpora ~1-3M bytes each = ceiling on data (supply more files for a genuinely large corpus).

## 7. Measured results — T2 dev run, ALL ideas ON (GPU, real data, expanding tokenizer VMAX 4096)
> RECONCILIATION (T5): this section is the OLDER T2 dev run and is superseded by the T33 GARRY milestone
> (VMAX 8192, end-to-end **1.967** b/B, expert-deletion **-0.0009**) recorded in `garry/GARRY.md` — treat THAT as the
> newest numbers until a fresher GPU run is pasted in here. The Fabric/society/experts/phased/grounding work that the
> CODE contains (and that §2 decided) was never written into this section; that history is not recoverable from the repo.
- Tokenizer grew 256 -> 4096 (mint-on-repetition, 3 passes); corpora -> 2.12M tokens.
- PERFORMANCE (true bits/byte): model alone **2.124** -> model+memory **1.727** (memory +0.397).
  vs byte-level last run (2.668 -> 2.273): **tokenizer cut ~0.5 bits/byte** off both.
- GENERATION: now semi-coherent — real English prose and recognizable Python/C (identifiers, keywords, braces,
  comments), numeric near-perfect. Big step up from byte-level fragments. NOTE: model-ALONE is cleaner per-domain;
  model+MEMORY bleeds cross-domain (composition helps prediction but hurts free-generation coherence).
- ASSEMBLY: 476 domains, purity 0.96; genuineness up — 62/476 GENUINE, mean silhouette +0.18 (byte-level was +0.07):
  tokens give cleaner domain separation.
- COMPOSITION: retrieval spans 6.67 segments/pos; GLOBAL beats SILOED +0.035 (over-segmentation still harmless).
- A (EDIT): unlearn process 2 = 512 domains / 78851 entries -> target +0.497, others Δ0.0036 (LOCAL). Clean at scale.
- B (WRONGNESS): recall JUMPED to **96%** (tokens make wrong tokens detectable) but precision still **1%** — the
  surprise-vs-wrong conflict is NOT fixed by the tokenizer. Still detect-only. B remains fundamentally broken for the realistic regime.
- MECHANICS: forgetting weights +2.37 / replay +0.36 / mem[model] +1.29 (replay still wins forgetting); editability
  6256x faster, 810x less collateral; drift survived.

## 6. Changelog (newest first)
> CAVEAT: this changelog runs T0–T5, but the frozen milestone is "T33" (`garry/GARRY.md`) — a DIFFERENT counter. The
> Fabric/society/experts/phased-stream/grounding work between them lived in a since-migrated chat + GPU logs and is not
> reconstructable from the repo. §2 (Decisions) WAS kept current through it; §6/§7 were not. See `docs/HANDOFF.md §7`.
- **T6 (current):** [USER: add a separate folder for workflow / context exchange as chats migrate] Created `handoff/` at
  repo root: a blank-chat bootstrap (`handoff/README.md`) plus atomic one-idea-per-file subfolders `process/` (8 files),
  `decisions/` (11), `open-questions/` (3), `migrations/` (1, this session). Filename-carries-the-summary style per user;
  designed so the next chat can rely on it with ZERO prior context. Keeps `STATE.md` as the live source of truth; the
  handoff files are short and point back here to avoid drift. No code changed.
- **T5:** [USER: file documentation + reconciliation + docs for the future] Added `docs/FILES.md` (file-by-file
  map, read from source) and `docs/HANDOFF.md` (pick-up-here guide + reconciliation ledger). Reconciled this file: removed
  dangling §7z/§7x/§7n/§7r/§7c refs, relabeled §7 as the T2 dev run and pointed "newest" at `garry/GARRY.md`, fixed the
  double "(current)" tag, harmonized B precision to "~1–2% across runs". Fixed two doc-vs-code bugs: `README.md` output
  paths (`~/full_unfrozen.txt`→`~/full.txt`, `runs/ck`→`runs/full`) and `cl_bench.py` header (`control.py clbench`→
  `cl_bench.py`). No behavior changed. [me]: chose to FLAG rather than fabricate the missing T5–T32 history.
- **T4:** [USER: how to use] Added top-level `README.md` (setup -> run -> message-the-model, plus the
  pieces and honest status). No code changed.
- **T3:** [USER: message the model] Added checkpoint save (`SAVE_CKPT`, writes model+tokenizer+memory
  before the destructive tests) and `prompt.py` (interactive: type a message -> the model continues it, model-only or
  +memory). Wired `SAVE_CKPT=runs/ck` into the full run. Verified save+load+generate end-to-end.
- **T2:** Ran the full test, ALL ideas ON [USER]. Results in §7. Tokenizer is a clear win (bits/byte down
  ~0.5, generation readable, separation up). B recall 96% but precision still 1% (unchanged core problem). No code
  changed this turn.
- **T1:** [USER: full test, all ideas ON] Turned the expanding tokenizer + adaptive gate ON in
  `run_full_unfrozen.sh`. Found + fixed a bug surfaced by running them together: the adaptive gate overshot on a
  skewed-high (weak-model) surprise distribution and starved writes (blocked the B-test injections) -> added a
  ceiling `gate_ceil`; and made synthetic wrong-injections bypass the write gate. Verified both parts run with all
  features on. Pre-pass tokenizer growth kept `[me]` (open Q1); base model kept small `[me]` (open Q3); B detect-only.
- **T0:** Created this ledger + adopted the protocol. Prior turn swapped static ByteBPE -> expanding
  `DynamicTokenizer` [USER]; growth is pre-pass `[me]` (open Q1).
- Audited all active files for outdated content; fixed stale comments/docstrings + the cl_bench estimate bug
  (was counting removed reverse-training steps); rewrote `CL_TESTBED.md`.
- Added the adaptive write-gate from legacy [USER: "add back what you can"]; tokenizer offered.
- Moved 57 dormant files to `legacy/` [USER]; triple-checked the active API is complete.
- Removed the reverse model + retrieval-wrongness machinery; renamed `novelty → surprise` [USER caught the misnomer].
- Wired B (self-consistency) into `self_organize` as DETECT-ONLY; built `run_full_unfrozen.sh`.
- Added generation, cross-segment composition test, and the performance measure (model vs model+memory).
- Rebuilt genuineness on silhouette; rebuilt B on self-consistency (works on cross-domain, fails realistic regime).
