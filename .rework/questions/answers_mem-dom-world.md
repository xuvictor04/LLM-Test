## Q-MEM-4 — `pressure()` cannot reach `pressure_thresh`

**What I read**
`docs/04_CONTRACT.md:1060-1069` (the question), `src/memory/api.py:14-19, 66-113, 114-141, 165-205, 269-299` (`write`, `read`, `maintain`, `census`), `src/memory/levers.py:181-263` (`evict`, `use_decay_every`, `src_share`, `probation_frac`, `pressure_thresh`), `:320-343` (`probe_every`, `probe_rows`), `src/fabric/api.py:254-309` (`grow_check`), `src/fabric/levers.py:624-634` (`grow_on_mem_pressure`), `src/spine/compose.py:669-694` (the `A MEM census` row), `:906-926` (the `B MEM write/maintain` row), `:1207-1222` (the `MEM.read` / `MEM.blend` deferrals), `.rework/ISSUES.md:228-231` (H33), `.rework/PLAN.md:94` (G4's three-state rule). Resolved defaults by running `spine.assemble.build(environ={})`.

**What is true today**
The question's premise is TRUE, and the reason it gives is not the operative one.

Verified defaults (from `build(environ={})`): `d_capacity=8192`, `d_owner_blocks=64`, `quota=128`, `probation_frac=0.10`, `pressure_thresh=0.80`, `src_share=0.5`, `probe_every=25`, `probe_rows=64`, `topk=8`, `evict='lru'`.

The chain that pins `pressure` at exactly 0 today is shorter and harder than the write:read ratio the question cites:

1. `pressure` is `main/(main+prob)` over eviction *branches* (`src/memory/api.py:283`). The probation branch is taken whenever the never-retrieved region is over `probation_frac`.
2. Only a retrieval promotes out of probation (`src/memory/levers.py:236-238`).
3. The only in-loop retrieval is `MEM.maintain`'s job 1 — and `compose.py:918-921` records that **`probe_contexts` has no producer**, so the probe has no material. `MEM.read` is in `DEFERRED_ENTRY_POINTS` (`compose.py:1207-1214`) for want of `queries`, so there is no second promoting path either.
4. Therefore `n_promoted ≡ 0`, probation ≡ 100% of the store, eviction is *always* the probation branch, `n_evict_main ≡ 0`, `pressure ≡ 0.0` — exactly, for every configuration, not "≈0 at the measured ratio".

So the instrument is not merely mis-tuned, it is **structurally 0 until P5 lands `probe_contexts`**, and re-tuning either lever now would be tuning against a constant.

Two more things the question does not say and P4 needs:
- `pressure_thresh`'s **only reader is `MEM.census`** (`memory/api.py:289`). `FAB.grow_check` takes a `memory_pressure` argument and reads no threshold (`fabric/api.py:291-293`); its prose is *"when supplied and `grow_on_mem_pressure` is set, makes growth eligible"*. So the comparison against 0.80 happens inside MEM, and no wire is needed or wanted. Whatever the root passes as `memory_pressure` must therefore already be MEM's verdict, or `fab.grow_mem_eligible` fires on every flush.
- The default arm is not even selected: `quota_arm` is `"reservoir"` at `src_share=0.5`, and `grow_on_mem_pressure` defaults `False`. So the honest three-state answer today has **two** named causes, not one.

The question's forward-looking arithmetic is worth stating because it is not obviously favourable either. Once the probe lands: ~`64/25 = 2.56` query rows per window × `topk=8` ⇒ up to ~20 entry-touches per window, against ~1 gated write per window (`gate_theta` evolves once per window, `memory/api.py:69-71`). Promotion capacity exceeds the write rate by ~20×, so probation *can* fall under 10% — at which point `pressure` jumps toward 1.0 and sits **above** 0.80 permanently. The probe's queries are drawn from the material currently being trained on, so promotion is concentrated, and the steady-state probation share is the share of entries never retrieved *once* — which is unknowable without running it. Both pinned-at-0 and pinned-at-1 are live outcomes.

**The options**
(a) **Keep the definition; declare the Gate; measure before retuning** (the question's own recommendation). Cost: the number stays uninformative until P5. Buys: no change to a definition nobody has yet measured, and no confounded "changed the instrument and its setting in one commit".
(b) Retune `probation_frac` and/or `pressure_thresh` now. Cost: tuning against a value that is identically zero for structural reasons; unfalsifiable. Buys: nothing.
(c) Redefine `pressure` as an occupancy or turnover measure. Cost: throws away the one thing the current definition gets right — *"share of evictions destroying entries somebody actually retrieved"* is a defensible reading of "short of room", because evicting never-read junk is not scarcity. Buys: a signal that varies before the probe exists.
(d) Drop `pressure_thresh` and the `pressure_signal` arm. Cost: D3 explicitly retains the arm; the lever's own comment says the mechanism has never fired *only because its input is pinned* — the broken-instrument case, which does not convict a mechanism.

**Recommendation**
**(a), with the reason corrected and the Gate's third state made mandatory.** Keep `pressure = main/(main+prob)`; keep `pressure_thresh = 0.80`; declare a `Gate` that prints `probation_share/probation_frac` beside `pressure/pressure_thresh` **and** `n_probe_fired / n_promoted`, and that reports **`unreachable (no promotion path: probe_contexts has no producer, n_promoted=0)`** rather than `0.000` whenever `n_promoted == 0` over the interval. Re-tune only after G2 measures the post-probe steady state, and expect the retune to be *upward* pressure, not downward.

**Why it fits the framework**
- **DID IT FIRE (G4).** `PLAN.md:94` defines the three states as `fired N` / `armed but 0` / `unreachable (<arithmetic>)`. `pressure = 0.0` printed as a number is the exact defect H33 names: *"a signal that cannot reach its threshold is indistinguishable from a healthy one."* The repair is a state label with arithmetic, not a new value.
- **Ownership spine.** `pressure_thresh` is MEM's and its only reader is MEM's own `census`. Nothing here asks a package to read a foreign lever, and nothing here wants a wire — a runtime measurement can never be a wire anyway, which is why `memory_pressure` is an argument (and why `fabric/levers.py:629`'s phrase *"arrives here as a wire"* is stale prose, not a design).
- **Frozen signatures.** Nothing moves. `census(mem, store, *, reconcile=False)` already reads `pressure_thresh`, and the counters the Gate needs (`n_promoted`, `n_probe_fired`) already exist on `Store` via `read`'s and `maintain`'s DID IT FIRE rows.
- **What it would break the other way:** adopting (b) or (c) now produces exactly the pathology the project's history names — a number changed at the same time as the instrument that reports it, with no attributable before/after.

**What changes**
- `src/memory/api.py:283-292` — `census`'s docstring gains one sentence: the Gate reports `unreachable` with the promotion-path arithmetic when `n_promoted == 0`, and names `n_probe_fired`/`n_promoted` as the Gate's `reads`. Docstring only, **no signature moves**.
- P5's `Gate(...)` declaration file (per `PLAN.md:182`) gains `mem.pressure`, with `covers` naming both causes: no promotion path, and arm not selected (`src_share > 0` ⇒ `quota_arm == "reservoir"`).
- `docs/04_CONTRACT.md:1060-1069` — replace "measured 82% of the store / write:read ratio" with the structural reason (no producer for `probe_contexts`), and record that a re-tune is expected to raise, not lower, the threshold.
- **One adjacent hole P4 must be told about, because two readings give different code:** neither `write`'s nor `census`'s docstring says whether `probation_frac` (and hence the eviction branch, and hence `pressure`'s denominator) is measured **per owner block** (128 rows ⇒ a budget of 12.8 entries) or **over the store** (8192 ⇒ 819). `write`'s "probation narrowing … run INSIDE that set" (`api.py:74-78`) points at per-block; nothing states it. Settle it in the same edit.

**Confidence**
High on "unreachable today, and for a stronger reason than the question gives" — it follows from two deferrals I read in `compose.py` plus the frozen prose, not from a run. Medium on the post-probe prediction (~20 promotion-touches/window vs ~1 write/window); it assumes one gated candidate per window, which I inferred from `gate_theta` evolving "for every window … IN WINDOW ORDER" rather than from a declaration. What would raise it: one P4 smoke run with `probe_contexts` stubbed from the training batch itself, printing `probation_share` and the two eviction counters for 2,000 windows.

**Literature**
NOT APPLICABLE, as briefed. The default `probation_frac=0.10` is already sourced in-file (S3-FIFO 10%, LIRS 1%, 2Q 25%, `memory/levers.py:240-241`); no paper can say whether *this* tree's probation region can be promoted out of, which is the whole question.

---

## Q-MEM-8 — which management cadence does `MEM.judge` run on?

**What I read**
`docs/04_CONTRACT.md:1170-1180` (the question), `:334-356` (§MEM), `:589` (the stage-`A` row list), `:704-737` (§3.6, the fourteen deferrals), `src/memory/api.py:236-267` (`judge`), `:269-299` (`census`), `src/spine/compose.py:669-694` (the `dom.manage` pass), `:703-710` (the `fab.manage` row), `:1223-1233` (the `MEM.judge` deferral), `:757-770` (the `dom.rekey` row), `src/train/api.py:230-250` (`Cadences.due`, `ledger`), `self_organize.py:4048-4060` (the old `selfcheck`), `memory.py:585-591` (the flag rule).

**What is true today**
**The question's statement of the tree's position is STALE.** It says *"`LOOP_ORDER` places `judge` as an event on the `dom.manage` pass"*. `grep -n judge src/spine/compose.py` returns **no `LOOP_ORDER` row for `MEM.judge`**; it is in `DEFERRED_ENTRY_POINTS` (`compose.py:1223-1233`), and `docs/04_CONTRACT.md:589` already says so (*"`MEM.judge` and `WORLD.manage` were here and are now deferred"*). The deferral's last sentence hands this question forward verbatim: *"Q-MEM-8 still owns WHICH management pass it rides when it returns."*

So the question is **live but not urgent**: it decides a P5 row, not a P4 body. Two facts the question does not carry:

1. **The stated reason for (a) does not survive inspection.** The question justifies the `dom.manage` pass as *"the moment the store's provenance has just been rewritten by folds and deletions"*. `judge` reads `verify, wrong_read, wrong_sweep, recon_hid, recon_tok` and scores `(ctx, tok)` per entry (`api.py:238-247`); **nothing in its inputs is provenance**. A fold relabels `src`; it does not change what the model thinks of a stored token. The right reason for (a) is different and better — see below.
2. **The cost is not small, and it depends on a design choice nobody has made.** The old implementation is `self_organize.py:4048-4060`: *"single pass, every entry judged"*, chunked at 8192. At `d_capacity=8192` and `key_win=8`, one full pass is **65,536 forward tokens**. One hundred Windows of training is `100 × ctx(128) = 12,800` forward tokens (≈38k with backward). So a full-store judge **every 100 Windows costs ~1.7× the entire training compute of the interval**; on the 500-Window `fab.manage` cadence it is ~0.34×. But `selfcon` is a persistent per-entry field with `-1` meaning unchecked (`memory.py:79, 492`) and the flag rule already reads *all* entries with `selfcon >= 0` (`memory.py:585-591`), so **judging can be incremental** — score only entries written since the last pass (~50-100 per 100 Windows, ≈800 tokens, ~6% of the interval) while flagging over the whole checked population. If judging is incremental, the cadence is nearly free either way and the cost argument vanishes.

**The options**
(a) **The `dom.manage` pass (100 Windows), inside the one `Cadences.due('dom.manage', …)` answer.** Costs: 1.7× training compute if full-store, ~6% if incremental; a `wrong_sweep=True` deletion lands after `MEM.census` has already fed `DOM.manage`. Buys: no new key, no new lever, no new period; MEM's cadenced store work stays on one pass; the *next* pass's `census(reconcile=True)` bounds the count staleness a sweep introduces to 100 Windows.
(b) **The `fab.manage` pass (500 Windows).** Costs: staleness after a sweep up to 500 Windows; `judge` becomes the only MEM row on a FAB-keyed pass, which is the thing `compose.py:703-710` warns about for WORLD (a pass riding another package's answer without saying so). Buys: 5× cheaper if full-store.
(c) **A new `MEM.judge_every`.** Refused by the frozen docstring (`api.py:253`) and by K4/N2 discipline — it would be a lever minted to solve a scheduling question the spine already answers.
(d) **A new key `mem.judge` on the existing `MEM.rekey_period`** (200 Windows, MEM's own threshold, its own ledger line, no new lever). Costs: makes `rekey_every` drive **three** mechanisms — `compose.py:768-771` already flags the current two as "ONE LEVER, TWO MECHANISMS" — so re-timing the rekey would silently re-time judging. Reject.

**Recommendation**
**(a) — the `dom.manage` pass — placed at the END of that pass, after `MEM.apply_domain_plan` and `DOM.census`, and conditional on `judge` being incremental** (checked set = entries whose `selfcon` is `-1`, plus, if P4 needs drift coverage, an amortized slice in the shape `maintain`'s job 2 already uses). If P4 determines a full-store rescore is required every pass, the cadence must move to **(b)**, and that trade must be recorded as the 1.7× number, not as a shrug.

**Why it fits the framework**
- **`Cadences.due` records the fire; asking twice under one key CONSUMES it** (`compose.py:671-674`). So "which pass" is not decoration — a row that asks `due('dom.manage', …)` a second time is the defect that made minting never fire. (a) is written *inside the one answer*, which is the shape the block already uses.
- **No new lever, no new key, no new period.** `_periods` (`compose.py:2132+`) stays five entries; `Cadences.ledger()['dom.manage']` remains the DID IT FIRE surface, which is what `rekey_period`'s docstring calls the pattern (`memory/api.py:337-339`).
- **Ordering follows from `census`'s own contract.** `census(reconcile=True)` "recomputes the per-source counts EXACTLY from (src & active) and reports the drift" (`api.py:271-274`). Putting `judge` at the end of the pass means any sweep-caused drift is reconciled by the *next* pass's first row — the shorter cadence is what bounds that window, and that is the real argument for 100 over 500. At the shipped default `wrong_sweep=False` nothing is deleted at all, so the ordering costs nothing today.
- **What it would break the other way:** (b) puts a MEM row on FAB's answer with no MEM period in sight — the same untracked ride `compose.py:705-710` calls out for WORLD; (c) mints a lever the frozen docstring forbids; (d) overloads `rekey_every` a third time.

**What changes**
- `src/spine/compose.py` — when `judge` un-defers, one `("A", "MEM", "judge", …)` row inside the `dom.manage` block, after the `DOM.census` row, with the note that it is the *same* answer and not a second `due`; delete the `"MEM.judge"` entry from `DEFERRED_ENTRY_POINTS` (K6 reads that table backwards and will report it stale otherwise).
- `src/memory/api.py:253` — replace "the management cadence the spine already imposes" with "the `dom.manage` pass, at its end", and state that the checked set is the stale-`selfcon` set, so `n_checked` per pass is a number rather than a policy.
- **A signature-shaped item, and it is the thing that actually unblocks `judge`:** the deferral says the scorer needs *"a domain id per stored entry, which nothing produces either"*. `Store` carries `src` per entry (`api.py:15-17`), so the datum exists — what cannot carry it is the declared callable shape **`scorer(ctx) -> logits`** (`api.py:238`). If the run's true forward path routes through `FAB.forward` (it does — `compose.py:2113-2117`), the scorer must be `scorer(ctx, src) -> logits`. That is prose, not a `def`, so it is free to change now and expensive after P4 writes against it. **Say it loudly, and change it in the same edit as Q-MEM-10.**
- `docs/04_CONTRACT.md:1170-1180` — mark the "LOOP_ORDER places judge…" sentence as superseded by §3.6 and record the corrected reason.

**Confidence**
High that the question is stale as written (no row exists; two independent places in the tree say so). Medium on the recommendation, because it turns on the incremental-vs-full-store choice, which no frozen text settles. What would raise it: a one-line statement from the owner that stale-`selfcon` scoring is acceptable — after which (a) is unambiguous.

**Literature**
NOT APPLICABLE. Which of this tree's two existing management passes carries an event is a question about `LOOP_ORDER` and `Cadences.due`; no paper can answer it, and the cost arithmetic is this tree's own numbers.

---

## Q-MEM-9 — does `MEM.maintain`'s read probe call `MEM.read`?

**What I read**
`docs/04_CONTRACT.md:1181-1189` (the question), `src/memory/api.py:114-141` (`read`), `:165-205` (`maintain`), `src/spine/compose.py:906-926` (the `B MEM write/maintain` row, whose last sentence names this question), `:1207-1214` (the `MEM.read` deferral), `src/memory/levers.py:320-343` (`probe_every`, `probe_rows`), `tests/test_contract.py:582-635` (K5) and the K6/K12 self-test cases at `:1027-1056`.

**What is true today**
The question is **live, and the answer it proposes is the only one the frozen surfaces admit** — but the decisive evidence is not the sentence it quotes. It is `read`'s parameter list:

- `read(mem, store, *, queries, promote=True)` declares `LEVERS READ: topk, blend_max, match_floor, wrong_read, verify` (`api.py:131`) — **no key lever, and no `key_fn`**. `conf` is "the top cosine similarity" (`api.py:120`). A function with no encoder and no key levers cannot encode anything, so **`queries` are already key-space vectors**.
- `maintain(mem, store, *, now, key_fn, probe_contexts=None, resegment=None)` declares `LEVERS READ: probe_every, probe_rows, rekey_every, key_src, key_depth, key_win` (`api.py:196`) — it holds the encoder *and* the three key levers.

So the probe path decomposes exactly one way: `maintain` strides `probe_rows` rows out of `probe_contexts`, narrows them to `key_win`, encodes with `key_fn` at `key_depth`, and hands the result to `read(..., queries=keys, promote=True)`. There is no second legal arrangement.

Two further verified facts:
- **Legality.** An in-package call is not a cross-package import; O10/K3 are untouched. K6 requires every entry point to be *named by a row* or deferred with a reason — `MEM.read` still has no row, so the deferral stays valid and is not reported stale. Confirmed by reading K5/K6's implementations and by the suite running green.
- **The probe is inert regardless.** `compose.py:918-921` records that `probe_contexts` has no producer. With the default `probe_contexts=None`, `maintain` is called every flush and job 1 has no material: the honest DID IT FIRE reading is `n_probe_fired` counting the *cadence* and `n_probe_rows == 0` — **armed-but-0**, not unreachable, and not silence. That distinction is the whole point of `maintain`'s own note that "a probe that fires and retrieves nothing is a DIFFERENT finding from a probe that never fires" (`api.py:198-200`).

**The options**
(a) **The probe IS `read(..., promote=True)`**, stated in `maintain`'s docstring. Cost: a docstring sentence; `MEM.read` is then reached in-package while remaining deferred at the row level, which one reader could mistake for a stale deferral. Buys: one retrieval path, so `n_reads`, `n_promoted`, `n_wrong_reads`, `n_wrong_read_hit`, `n_wrong_blocked` describe the same path that moves `use`/`last`/`prob`.
(b) **Open-code a second kNN inside `maintain`.** Cost: the C8/C9 shape one layer down — the counters describe one path while the store is moved by another; `wrong_read` and `match_floor` would have a second implementation free to drift; and `blend` would then be computable from a `Retrieval` MEM did not build, which `blend`'s own docstring exists to refuse (`api.py:149-151`). Buys: nothing.
(c) Leave it unstated. Cost: P4 picks by accident, and K6 cannot see either choice. Buys: nothing.

**Recommendation**
**(a) — confirm it, in `maintain`'s docstring, in the terms the parameter lists already force.** Add the one thing the question does not ask for and P4 needs: **the probe calls `read` with `queries` it encoded itself**, so `read`'s `queries` are documented as key-space vectors, not contexts.

**Why it fits the framework**
- **Ownership spine.** MEM calling MEM is inside the allowlist; the alternative (the root producing `queries`) would need the root to narrow to `key_win` and encode at `key_depth` — reading two MEM levers at a spine call site and duplicating the narrowing that `maintain` already owns. That is the "one quantity resolved in two places" defect (`assemble.py:105-114`, the SIG_WIN case).
- **DID IT FIRE.** One path ⇒ one set of counters. `maintain` owns `n_probe_fired / n_probe_rows / n_probe_hits`; `read` owns `n_reads / n_promoted / n_wrong_*`. Under (b) those two families would describe different events with no way to say so.
- **G7 / frozen RNG.** `read` draws no randomness; the stride is deterministic (`api.py:174-178`). The probe therefore cannot move the training trajectory, which is the property `probe_rows`' comment calls the reason the mechanism is honest.
- **Frozen signatures: nothing moves.** Both signatures already fit.

**What changes**
- `src/memory/api.py:174-181` — `maintain`'s job 1 gains: *"the probe IS `read(mem, store, queries=key_fn(stride(probe_contexts)[:, -key_win:], depth=key_depth), promote=True)`; there is no second retrieval implementation in this package"*, plus one clause noting that a `None`/empty `probe_contexts` yields `n_probe_fired` with `n_probe_rows == 0` — armed-but-0.
- `src/memory/api.py:114-118` — one clause on `read`: `queries` are keys in the store's key space, produced by the same `key_fn`/`key_depth` the write path used.
- `src/spine/compose.py:1207-1214` — the `MEM.read` deferral gains one sentence: it is deferred as a *row*, and is reached in-package by `maintain`; K6 is satisfied by the absence of a row, not by the absence of a call.
- `docs/04_CONTRACT.md:1181-1189` — record the confirmation.

**Confidence**
High. The conclusion is forced by two `LEVERS READ:` lists and one absent parameter, all of which I opened; and all six test files run green on this tree today (`test_ownership` 11 checks + 18 self-tests, `test_contract` 12 + 34, `test_census` 5, `test_assemble` 7, `test_couplings` 4 over 23 declared couplings, `test_derive` 575 oracle cases, **0 failing** in each).

**Literature**
NOT APPLICABLE. "Does this package's function call its own sibling" is internal by construction.

---

## Q-MEM-10 — `MEM.blend` returns probabilities; every scoring hook takes `logits_fn`

**What I read**
`docs/04_CONTRACT.md:1190-1202` (the question), `:727` (the `MEM.blend` deferral row), `src/memory/api.py:114-164` (`read`, `blend`), `src/eval/api.py:1-30` (the ONE LOGITS PATH rule), `:71-145` (`curve_probe`, `holdout_probe`, `generate`), `:167+` (`coherence`), `src/fabric/api.py:169-190` (`contribution`, `baseline_logits_fn`), `src/spine/compose.py:1051-1056` (why the R rows were deleted), `:1207-1222` (the two deferrals), `:2005-2021` (what is deliberately not a compose helper — the `logits_fn`), `:2100-2118` (`_key_fn`, `_head`, `_sig_encode_fn`).

**What is true today**
Everything the question states is verified, and the gap is wider than "an interface": **the `logits_fn` does not exist for any consumer, with or without memory.** `compose.py:2015-2018` says so explicitly — it is "deliberately not here" because it must be *the path the run trained*, which runs through `FAB.forward` and needs the flush's own novelty, `live_domains` and `signature`. Four EVAL entry points and `FAB.contribution` are all deferred on that same missing callable.

`grep logits_fn src/*/api.py` returns exactly six hits: `eval/api.py:27, 71, 95, 147, 167` and `fabric/api.py:169, 188`. Nothing else in the tree takes logits as a callable. `MEM.blend(mem, model_probs, retrieval)` is the only probability-space interface, and `MEM` and `EVAL` cannot import each other (K3, green).

One fact that changes the option ranking and appears nowhere in the question: **`log(p)` is not "pseudo-logits" — it is exact.** `softmax(log p) = p` identically; temperature, top-k and nucleus sampling all operate correctly on it; cross-entropy over `log p` is exactly the bits/byte of the blended distribution. And the blend cannot produce `log(0)`: `blend` returns `(1-w)·model_probs + w·dist` with `w ≤ blend_max`, and `model_probs` from a softmax are strictly positive, so the result is `≥ (1-blend_max)·p_model > 0` **for every `blend_max < 1`**. `blend_max` is a `FRACTION` lever defaulting to `0.5`; at exactly `1.0` with `conf = 1.0` the guarantee lapses. That is one named clamp, not an argument against the option.

**The options**
(a) **The spine forms the closure: `softmax → read(promote=False) → blend → log`.** Cost: "ONE LOGITS PATH" must be restated, because there are now two closures (memory-off, memory-on) — and they score two different systems. Buys: no frozen signature moves; the mix is written exactly once, in the composition root, where every consumer shares it; the `MEM.read` deferral partially closes because the closure is itself the producer of `queries` (it holds `_key_fn`).
(b) **A second optional `probs_fn` hook on the scoring entry points.** Cost: four EVAL signatures move *and* every instrument grows two code paths, one of which is untested; two ways to score is the C3/H11 shape (a baseline from a different callable than the number it is compared against). Buys: nothing (a) does not.
(c) **Pass `blend_fn` into the scoring entry points** (the question's recommendation). Cost: **four EVAL signatures move**, and each of the four bodies must then implement `softmax → blend → log` for itself — i.e. **four copies of the mix inside the instrument line**. The tree's two recorded instances of this exact defect are `prompt.py` (C8) and `cl_bench.py` (C9): the ungated 50/50 mix recomputed at a consumer site. `blend`'s own docstring exists to stop it: *"THE ARITHMETIC LIVES IN THIS PACKAGE so the mixing weight never travels"* (`api.py:145-147`). Buys: one probe call could in principle produce both numbers.

**Recommendation**
**(a) — the spine forms the closure — and the answer to "which side's frozen signature moves" is NEITHER.** `MEM.blend` keeps `model_probs` as probabilities; EVAL keeps `logits_fn`. The join is composition-root work, which is what the composition root is for.

Three conditions make it honest rather than a quiet redefinition:
1. **One named helper, once.** `_logits_fn(sysm, *, use_memory)` beside `_key_fn`/`_head`/`_sig_encode_fn` in `compose.py`, and it is the only place `softmax → read → blend → log` is written anywhere in the tree.
2. **Two closures, two systems, named in the report.** `use_memory=False` is the trained path; `use_memory=True` is the trained path plus retrieval, which *has never entered training* (`docs/04_CONTRACT.md:352-356`). The `-0.097 → +0.085` b/B price of retrieval is the difference between the two, so the pair is the deliverable, not an inconvenience. `FAB.contribution`'s `baseline_logits_fn` must be the **memory-off** closure, always.
3. **The rule is rewritten, not stretched.** `eval/api.py:27-30` becomes: *one closure per scored system, formed in the composition root, passed in, never constructed here; the reading names which closure produced it.* A docstring edit, not a signature edit.

**Why it fits the framework**
- **Callable-passing is the established idiom, and the spine is where callables are formed.** `_key_fn`, `_head` and `_sig_encode_fn` already exist for exactly this reason (`compose.py:2100-2130`): an entry point partially applied is "the one class of argument no return value can produce" (`compose.py:761-763`). The `logits_fn` is the fourth member of that family, and `compose.py:2015-2018` already files it as the one that is not formable *yet* — it does not file it as illegal.
- **O10 / K3.** EVAL cannot import MEM. Under (a) it never needs to; under (c) it must be handed MEM's arithmetic four times over.
- **The C8/C9 record is decisive.** The tree's stated reason for keeping the mix inside MEM is that a weight read at a consumer site *is* the recorded defect. (c) re-creates it inside the instrument line — the one place `eval/api.py:2-3` says must measure and never change.
- **K10's blind spot argues the same way.** `compose.py:1215-1222` notes `model_probs` is the first positional after the Config and K10 drops it as "the package's own live object" — which it is not. Under (a) `MEM.blend` is called from a spine helper, never from a row, so the blind spot is retired rather than papered over.
- **What it would break the other way:** (c) moves four frozen EVAL signatures *and* re-implements one arithmetic in four bodies. If the owner nonetheless chooses (c), **it must be done now** — `eval/api.py`'s four `def`s change shape, and P5/P6 write against them.

**What changes**
- `src/spine/compose.py` — one new helper `_logits_fn(sysm, *, use_memory)` in the helper block (~`:2100-2130`), named by the rows that consume it, exactly as `_key_fn` is; and the two deferral reasons at `:1207-1222` rewritten to say what now closes them (the closure supplies `queries`; the remaining blocker for the EVAL probes is `units_by_domain`, not the mix).
- `src/eval/api.py:27-30` — the ONE LOGITS PATH paragraph restated as one-closure-per-scored-system. **No `def` line changes.**
- `src/memory/api.py:143-164` — one clause on `blend`: the caller that consumes the result for scoring takes `log` of it, and `blend_max == 1.0` with `conf == 1.0` is the single case that must be clamped away from `log(0)`. **No signature change.**
- `docs/04_CONTRACT.md:727, 1190-1202` and `:352-356` — record the ruling and retire Q-MEM-10.
- **Hazard to hand P4/P5 with it:** `read`'s `queries` must be narrowed to `key_win` and encoded at `key_depth`. `maintain` does that narrowing internally (it reads both levers); the closure would be a **second** narrowing site. Write it once, in the helper, and say in `read`'s docstring that the two sites must agree — otherwise the store is queried in one key space and written in another, which is the drift `rekey_every` exists to prevent.

**Confidence**
High that no signature needs to move and that (c) rebuilds C8/C9. High that `log(mixture)` is exact. Medium on the residual: the closure still needs `signature` and `domain_id` for `FAB.forward` on held-out windows without mutating `DOM` (G7) — that is the *other* half of why `logits_fn` does not exist, it is not resolved by this ruling, and it is the same missing datum as `MEM.judge`'s scorer.

**Literature**
**It bore, narrowly and usefully.** Retrieval-augmented LMs interpolate **in probability space** and then evaluate the log of the interpolated distribution: kNN-LM computes `p = (1-λ)·p_LM + λ·p_kNN` and reports perplexity of that mixture (Khandelwal et al., ICLR 2020). So `MEM.blend`'s probability-space signature is the standard formulation, not an eccentricity, and "take the log of the mixture and score it" is what the field already does — which is option (a) exactly. The literature does **not** bear on where the join lives in this tree; that is settled by O10 and by the C8/C9 record, and no paper overrides it.
Sources: [kNN-LM (Khandelwal et al., ICLR 2020)](https://arxiv.org/abs/1911.00172), [OpenReview PDF](https://openreview.net/pdf?id=HklBjCEKvH)

---

## Q-MEM-11 — `MEM.census` and `DOM.census` return record types neither file declares

**What I read**
`docs/04_CONTRACT.md:1314-1326` (the question), `src/memory/api.py:14-19` (RECORD TYPES) and `:269-299` (`census`), `src/domains/api.py:18-23` (RECORD TYPES), `:171-176` (`manage`'s signature) and `:273-291` (`census`), `src/fabric/api.py:254-303` (`grow_check`), `src/spine/compose.py:669-699` (the `produces` columns that name the four crossing arguments), `tests/test_contract.py:1954-2040` (K11's implementation).

**What is true today**
Verified in full, and the question is live. `memory/api.py:14-19` declares `Store`, `WriteReceipt`, `Retrieval` and nothing for `census`, whose fields (`floor_entries`, `quota_arm`, `pressure`, the per-source counts) live only in prose at `:269-292`. `domains/api.py:18-23` declares `Partition`, `Assignment`, `Plan` and nothing for `census`, whose fields (`live`, `n_live`, `comp_glob`, radii, `collapsed_at`, …) live only in prose at `:274-282`. Four required arguments cross those boundaries — `DOM.manage`'s `memory_counts` and `mem_floor_entries` (`domains/api.py:171`), `FAB.grow_check`'s `memory_pressure` (`fabric/api.py:254`), `FAB.forward`'s `live_domains`.

What the question does not say, and what settles the *spelling* half of it:

**K11 is a name-appearance check.** Its own docstring (`tests/test_contract.py:1975-1980`) says: *"The name must appear somewhere in the entry point's docstring or its module's — which is where every package declares its RECORD TYPES RETURNED. It cannot tell a returned field from a mention, and it does not try."* So the four `produces` entries pass today **only because the words appear in prose**, and K11 explicitly prints the count of entry points with no discoverable return text as a thing worth reporting. Declaring the records turns a prose coincidence into the thing the check was designed to read.

And the question's parenthetical — *"ideally as the consuming names so the rename disappears"* — is the half I would not adopt:
- It would put `memory_counts`, `mem_floor_entries` and `memory_pressure` **on MEM's own record**. A package prefixing its own fields with its own name is the doubled-name defect the census already corrected (`WORLD_NMAX`→`nmax`, `FAB_FAB_N0`, `world/levers.py:306`).
- It inverts the mechanism `assemble.py:41-47` is built on: *"THE WIRE NAMES THE FIELD, NOT THE RECEIVER … The receiving package is never handed a chance to choose a name."* The symmetric rule is that the **producer** does not carry the consumer's spelling either. A record laundered into a consumer's vocabulary is the same leak read backwards.
- The rename is **already recorded and already machine-checked** in the place built for it: the `produces` column, in the declared form `alias = real -- why` that K11 admits (`test_contract.py:980-983`) and K10 consumes.

**The options**
(a) **Declare both returns in the RECORD TYPES blocks, spelling the fields under each producer's own names**, and leave the renames in the `produces` column. Cost: two docstring edits plus two prose corrections in `compose.py`. Buys: K11 reads a declaration instead of a coincidence; P4 has one place to define the record; `TOK.vocab_state`'s D-T3 — a live defect *caused* by an undeclared key — does not get a sibling.
(a′) Same, but with the consumer's spellings on the producer's record. Cost: doubled names inside MEM, producer carrying foreign vocabulary. Reject.
(b) **Leave the prose.** Cost: P4 invents the field names; the four `produces` entries then certify a round trip nothing can verify; K10 trusts K11, and K11 cannot tell a returned field from a mention.

**Recommendation**
**(a), with the producer's own spellings.** Name them distinctly so `grep` stays unambiguous across packages: **`StoreCensus`** in `memory/api.py` and **`PartitionCensus`** in `domains/api.py` — not two records both called `Census`.

**Why it fits the framework**
- **It is a docstring change inside a frozen signature.** `census(mem, store, *, reconcile=False)` and `census(dom, part)` do not move. This is the cheapest class of edit the contract admits, and the question is right that it should be taken.
- **The `produces` column is the declared home for a rename** (`compose.py:167-170`, K10/K11). Moving the rename into the record would empty a checked mechanism into an unchecked one.
- **Uniqueness fails for the consumer-spelling idea anyway**, and the tree already shows it: `DOM.census`'s `live` reaches MEM as `live_sources` while its `n_live` reaches FAB as `live_domains` (`compose.py:694-699`). One record feeding two packages under two vocabularies is normal here; "the consuming name" is not a function.
- **What it would break the other way:** (b) leaves the fields undeclared, and the tree's own example of that outcome is `TOK.vocab_state` — an undeclared key that became a live defect (Q-TOK-10).

**What changes**
- `src/memory/api.py:14-19` — add `StoreCensus  counts (per source), floor_entries, quota_arm, pressure, probation_share, live_src, nsrc/nsrc_max, census_drift, n_census_reconciles, and every store.n_* counter passed through`. `:269-299` — one line pointing at it.
- `src/domains/api.py:18-23` — add `PartitionCensus  live, n_live, created, capped, merged, culled, folded, held, spared, emptied, boundaries, windows, per-domain visits/born/last/radius, pooled_radius, comp_glob, collapsed_at, partition_off, every part.n_* counter`. `:273-291` — one line pointing at it.
- `src/spine/compose.py:676-681` and `:697-699` — the two prose claims *"MEM.census DECLARES NO RECORD TYPE"* / *"DOM.census declares no record type either"* become stale the moment this lands; correct them in the same commit or K-check prose and the tree disagree.
- `docs/04_CONTRACT.md:334-356`, `:365-372`, `:1314-1326` — record the declaration and retire Q-MEM-11.

**Confidence**
High. Every claim here is a line I opened, and K11's own docstring states the weakness this edit removes.

**Literature**
NOT APPLICABLE. Whether two docstrings in this tree declare their return types is not an empirical question.

---

## Q-WORLD-6 — WORLD's Windows-denominated cadence

**What I read**
`docs/04_CONTRACT.md:1089-1095` (the question), `:133-150` (**C3, the frozen decision**), `src/world/api.py:111-158` (`manage`), `src/world/levers.py:304-360` (`nmax`, `grow`, and the cadence note), `src/spine/assemble.py:30-115` (the wire rules, CROSS vs LOCAL), `:660-700` (the table header and `_owner_blocks`), `:700-800` (the `DOM.d_expert_slots` and `FAB.d_manage_period` rows), `:1117-1160` (`NOT_WIRES`), `src/spine/wire.py:43-54` (`WIRE_BUDGET`), `src/train/api.py:230-250` (`Cadences.due`/`ledger`), `src/fabric/api.py:403-426` (`manage_period`), `src/spine/compose.py:703-710` (the `fab.manage` row), `:1262-1275` (the `WORLD.manage` deferral), `tests/test_contract.py:582-635` (K5).

**What is true today**
Three verified facts, and together they answer it.

1. **C3 has already decided this, in the contract, in these words** (`docs/04_CONTRACT.md:146-150`): *"`WORLD.manage` is called from the composition root through RUN's Windows-typed `Cadences.due` with `FAB.manage_every` — **no period enters WORLD's Config**, so no Flushes wire can reach it."* `world/api.py:119-121` repeats it. A new `WORLD.d_manage_period_windows` row contradicts a decision this document already froze.
2. **WORLD has no `d_` field at all** (`grep -n d_ src/world/*.py` finds only prose), and **`WORLD.manage` is deferred** (`compose.py:1262-1275`) for three unrelated reasons: `plateau` contradicts WORLD's own `state_dict`, `add_param_group` needs `OptState` to name one of its two AdamW instances (Q-OPT-7), and `latent` arrives backwards. So **the reach does not exist in the running system today**. Declaring it now would print an edge that is not made — which is precisely the failure `assemble.py:128-134` calls the untrippable-guard shape ("the printed graph shows an edge that was never made, `affects()` hands the L3 sweep a reach the run does not have, and the sweep reads as passing because nothing moved").
3. **K5 would force a decorative read.** `tests/test_contract.py:611-618`: every declared destination must be named under `WIRES READ:` by a stub in its own package, or the check reports *"a wire nobody reads spends budget, prints an edge, and delivers a value that arrives nowhere."* Since the root evaluates the gate and calls `manage` only when it fires, WORLD's body has no arithmetic to do with the period — the read would be `_ = world.d_manage_period_windows` forever. And the budget is real: **23 of 25 couplings are declared** (`tests/test_couplings.py` prints "23 declared coupling(s)"), so this spends one of the last two.

A fourth fact reframes the question's motive. The reach the question wants `affects()` to see is a **cadence reach through the root's call order**, and the tree already has several that no wire declares: `DOM.manage_every` gates `MEM.census`, `DOM.manage`, `DOM.census` **and** `MEM.apply_domain_plan` (`compose.py:669-699`) with no `DOM→MEM` wire anywhere. So WORLD's case is not special; it is one instance of a **general blind spot**, and a single WORLD row would be a spot repair that makes the graph look more complete than it is. Note also that `FAB.d_manage_period` is not a counter-example: it exists because FAB's own below-the-early-out sites need a **Flushes** conversion (`assemble.py:765-784`), which is arithmetic. WORLD needs no conversion — `FAB.manage_period(fab)` already returns typed `Windows` (`fabric/api.py:403-421`) and `Cadences.due` refuses anything else (`train/api.py:242`).

**The options**
(a) **Add the row** `FAB.manage_every → WORLD.d_manage_period_windows`, `Windows(manage_every)`. Cost: contradicts C3; spends 1 of 2 remaining budget lines; requires a decorative `WIRES READ` in a deferred entry point to satisfy K5; declares an edge no run makes today. Buys: `affects("FAB_MANAGE_EVERY")` gains `WORLD` — for one of many unbooked cadence reaches.
(b) **No row; a `NOT_WIRES` entry with the reason**, and the reach recorded where cadence reach is already recorded: `Cadences.ledger()['fab.manage']` (or a `world.grow` key), the C3 decision, and §3.5's cadence table. Cost: `affects()` still returns `{"FAB"}`, so the L3 sweep would read a WORLD fingerprint move as WORLD leaking. Buys: no budget, no fake read, no contradiction, and the gap is named rather than half-patched.
(c) **Fix the general blind spot**: teach the L3 oracle to union in cadence reach from `_periods` + `LOOP_ORDER`, which the root already holds as data. Cost: new machinery, and it is not this question's to build. Buys: the correct answer for all six gates instead of one.

**Recommendation**
**(b) — do not add the wire. Add a `NOT_WIRES` entry, and file (c) as the real repair.** Say plainly, in the same edit, that `affects()` does not see cadence reach *for any gate*, so the L3 sweep must obtain it from `Cadences.ledger()` / `LOOP_ORDER`, not from the wire ledger.

**Why it fits the framework**
- **C3 is a frozen decision and this contradicts it.** "No period enters WORLD's Config" is not a preference; it is the sentence that keeps the Flushes wire out, and a Windows wire into the same field re-opens the door the sentence closed.
- **`NOT_WIRES` is the declared home for exactly this.** `assemble.py:1117-1160` holds candidates that are real couplings and must not be wires, each with a reason, and `render()` prints them into `docs/03_WIRING.md` (`:1445-1448`). The `RUN.seed` entry is the same shape: a genuine reach whose per-package edges would add noise without adding an oracle.
- **DID IT FIRE already covers the visibility need.** `Cadences.ledger()` is *"the DID IT FIRE surface for every periodic gate in the run, in one place, whoever owns the threshold"* (`train/api.py:248-250`). That sentence is the answer to "make the reach visible".
- **What it would break the other way:** (a) contradicts a frozen decision, spends scarce budget, and requires a read that exists only to satisfy a check — the pattern this tree calls an untrippable guard.

**What changes**
- `src/spine/assemble.py:1117-1160` — one `NOT_WIRES` entry: *"`FAB.manage_every → WORLD.d_manage_period_windows` — the reach is real and the root makes it, but the period never enters WORLD's Config (C3): the gate is evaluated by the composition root through `FAB.manage_period(fab)`, already typed `Windows`, and WORLD does no arithmetic on it. A wire would need a decorative `WIRES READ` to satisfy K5 and would book one of six cadence reaches while five others stay unbooked. The did-it-fire surface is `Cadences.ledger()`."*
- `docs/04_CONTRACT.md:1089-1095` — resolve the question against C3 and record the general `affects()` blind spot for L3.
- `src/spine/compose.py:703-710` — when `WORLD.manage` un-defers, its row states which answer it rides (inside `fab.manage`'s single answer, or a `world.grow` key of its own — asking `due` twice under one key consumes the fire).
- **No wire, no budget change, no signature change.**

**Confidence**
High. C3, the empty WORLD `d_` set, the 23/25 budget and K5's text are all things I read or ran. The only judgement is whether the owner values `affects()` completeness enough to accept a decorative read — and even then, the WORLD row alone would not make `affects()` correct.

**Literature**
NOT APPLICABLE. This is internal consistency between C3, the wire ledger and `Cadences`.

---

## Q-WORLD-8 — `soft_cull`'s irreversibility: which half gets fixed?

**What I read**
`docs/04_CONTRACT.md:1096-1105` (the question), `src/world/api.py:111-158` (`manage`, including the frozen `blocked_reason` set) and `:160-180` (`geometry`), `:201-215` (`load_into`), `src/world/levers.py:120-140` (the five undeclared constants), `:304-355` (`nmax`, `grow`), `world_model.py:70-128` (`DynamicsPopulation.__init__`, `route`, `forward`, `grow`, `soft_cull`), `.rework/ISSUES.md:609-620` (M69/M70/M71).

**What is true today**
The question's facts check out in the old source, and one of them is worse than stated:

- `world_model.py:83` — `register_buffer("alive", torch.ones(nmax))  # soft-cull mask (reversible: params kept)`; `:127` — `s.alive[i] = 0.0` is the only write. Irreversible. **M69 confirmed.**
- `world_model.py:110` — `if s.n() >= s.nmax: return None`, and `n()` is `len(s.preds)`. **M70 confirmed.**
- `world_model.py:92-94` — `outs = torch.stack([p(z) for p in s.preds], 1)`: a culled predictor is **still run every forward and still receives gradient**, held down only by `+ torch.log(s.alive.clamp_min(1e-6))` inside `route` (`:88`). The "soft" penalty is `1e-6` of relative routing mass, so the cost claim in the question ("still costs forward compute and gradient while contributing ~1e-6") is exact.

And here is what neither the question nor the contract's recommendation accounts for:

**"Fix M70 only (count live)" is not implementable as written.** `fit`, `mass` and `alive` are buffers of width `nmax` (`world_model.py:81-83`), and `world/levers.py:304-305` says `nmax` *"also sizes the per-predictor fitness, routing-mass and alive buffers."* If `grow()` compares **live** against `nmax` while still `s.preds.append(...)`-ing, then `n()` exceeds `nmax`, and `update_fitness`'s `for i in range(s.n()): s.mass[i] = …` (`:101-105`) indexes past the end. Counting live while appending also means unbounded forward compute and a checkpoint whose `n` exceeds its own `nmax` — which `WORLD.geometry` (`api.py:161-162`: *"nmax MAY_WIDEN, n … MAY_WIDEN AND MAY_NARROW"*) and `load_into`'s two-directional refusal (`api.py:201-210`) are built to prevent.

There is exactly one way to satisfy "count live" without breaking the buffers: **the mint takes a dead slot.**

And the frozen surface already says so. `world/api.py:148-149` declares `blocked_reason` as one of `{grow_off, at_live_cap, no_plateau, cooldown, null_world}`. **`at_live_cap` — not `at_total_cap`.** A `grow()` that refuses because `n() == nmax` while `live < nmax` has **no legal `blocked_reason` to report**. The frozen enum forces the live-cap semantics, and the fixed-width buffers force slot reuse as the only implementation of it.

**The options**
(a) **Fix M70 by appending when `live < nmax`** (the contract's recommendation, read literally). Cost: buffer overflow at `n() > nmax`; unbounded forward compute; a checkpoint geometry the resume gate must refuse. **Not implementable.**
(b) **Fix M70 by slot reuse: `grow()` mints into the lowest dead slot** — clone the fittest into it, reset `fit`/`mass`, set `alive=1`; `soft_cull` stays one-way in the sense that matters (a culled predictor's *learning* is never restored); the "reversible: params kept" claim is deleted from both docstrings; dead predictors are **skipped in the forward** so the hard routing penalty is real rather than `1e-6`. Cost: the population can churn at the cap — the oscillation the contract fears — and the newborn's parameters are a clone, so the culled specialist is gone. Buys: `at_live_cap` becomes truthful; buffers, geometry and `load_into` unchanged; capacity is reusable; the compute the question calls "a real cost" actually stops being paid.
(c) **Fix both — restore `alive=1.0`.** Cost: the contract's objection stands, and it is stronger than stated: resurrection restores a predictor whose `mass` is *by definition* below `min_mass`, so it is culled again at the next pass unless something else changed. Buys: nothing (b) does not.
(d) **Fix neither.** Cost: `grow` is permanently disarmed after the first cull, silently — which is M70 as a live defect and `blocked_reason` reporting a state its enum cannot name.

**Recommendation**
**(b) — slot reuse, plus a genuinely hard routing penalty, plus the docstring correction.** This is the contract's "fix M70 only, leave `soft_cull` one-way, stop claiming reversibility" — but implemented the only way the buffers and the frozen enum permit, and with the compute cost actually removed rather than merely deplored.

The oscillation objection is answered by measurement, not by refusal:
- fix C6 (`mass` initialised on birth) so a newborn is not culled at the next pass — the contract already lists this as a plumbing fix;
- the plateau predicate and the `4 × MANAGE_EVERY` cooldown already bound the mint rate (`world/levers.py:137-139`), and both become Gate parameters that print their own arithmetic;
- **count reused-slot mints separately from fresh mints**, so "minting and culling at the cap indefinitely" is a number the report states, not a hypothesis the design has to pre-empt. `ManageResult(grow_attempted, grown, soft_culled, live, blocked_reason)` already carries four of the five terms.

**Why it fits the framework**
- **The frozen `blocked_reason` enum forces it.** `at_live_cap` is in the declared set and `at_total_cap` is not. Under (d) the mechanism reports a state it cannot name; under (a) the buffers break. (b) is the only reading under which the frozen DID IT FIRE row is true.
- **The geometry manifest forces it.** `nmax MAY_WIDEN`, `n MAY_WIDEN AND MAY_NARROW`, and `load_into` refuses in both directions on population size (M43). `n() > nmax` is a checkpoint the resume gate must reject; slot reuse keeps `n() ≤ nmax` by construction.
- **DID IT FIRE.** `ManageResult.live` vs `n()` is, as the contract says, "the number that says whether the population has silently become mostly dead" — under (b) that gap is transient and its churn is counted, instead of being a one-way ratchet nothing reports.
- **What it would break the other way:** (a) breaks torch buffers and the resume gate; (c) mints an oscillation with no counter that would show it; (d) leaves a growth mechanism that dies silently at the first cull, which is M70 exactly.

**What changes**
- `src/world/api.py:126-141` — the M70 clause becomes: *the cap is on LIVE predictors; a mint claims the lowest dead slot, resets `fit`/`mass`/`alive` for it and clones the fittest into it; `n()` never exceeds `nmax`. A dead predictor is skipped in the forward, not merely down-weighted — the `log(1e-6)` routing penalty left it paying full forward and gradient cost for `~1e-6` of the blend (`world_model.py:88, 92-94`). `soft_cull` is one-way: a culled predictor's learning is never restored, and the "reversible: params kept" claim is deleted here and in the port of `world_model.py:83, 121`.* Add `n_slots_reused` beside `grown` in the DID IT FIRE row so churn is visible. **No signature change** — `manage(world, w, *, latent, plateau, add_param_group)` is untouched, and `ManageResult`'s field set already covers it.
- `src/world/levers.py:316-323` — the M69/M70 comments follow the same correction; `nmax`'s "hard cap" text says *cap on LIVE predictors, and the width of the fit/mass/alive buffers* — one sentence that makes the buffer constraint impossible to miss.
- `docs/04_CONTRACT.md:1096-1105` — replace "fix M70 only (count live)" with "fix M70 as slot reuse", and record why the literal reading is not implementable (buffer width, geometry, `at_live_cap`).
- P5's `Gate` file — the plateau predicate (`_winv > 0.9·_wl_ema`) and the `4 × MANAGE_EVERY` cooldown as declared Gates printing their own arithmetic, per `world/levers.py:137-139`.

**Confidence**
High on the mechanics: the buffer widths, the append, the `n()` definition, the `alive`-only-to-0.0 write and the full-population forward are all lines I opened in `world_model.py:70-128`, and `at_live_cap` is in the frozen docstring. Medium on the oscillation risk being acceptable — that is an empirical claim about a mechanism that has never once been observed to add a working predictor in the product loop, and only a run with the counters in place will settle it.

**Literature**
**It bore, and it points the same way.** The continual-learning capacity literature treats a dormant unit's slot as capacity to be **re-initialised**, not as a unit to be **restored**. ReDo (Sokar, Agarwal, Castro & Evci, ICML 2023) periodically detects dormant neurons and *reinitialises* their incoming weights, zeroing the outgoing ones — recycling the slot, discarding the dead unit's parameters. Continual backpropagation (Dohare et al., *Nature*, 2024) reinitialises a small proportion of the least-used units every step to maintain plasticity, and states the trade-off this question is really about: reinitialise too much and stored information is lost; too little and plasticity loss persists — i.e. **the churn is a real cost to be measured, not a reason to refuse reuse**. Both support option (b) over (c): nothing in that literature restores a culled unit; it overwrites the slot. The literature does **not** bear on the buffer-width or `blocked_reason` argument — those are this tree's, and they are the load-bearing half.
Sources: [The Dormant Neuron Phenomenon in Deep RL (ReDo)](https://arxiv.org/abs/2302.12902), [ReDo, ICML 2023 PDF](https://proceedings.mlr.press/v202/sokar23a/sokar23a.pdf), [Loss of plasticity in deep continual learning (Nature 2024)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11338828/), [Maintaining Plasticity in Deep Continual Learning](https://arxiv.org/pdf/2306.13812)
