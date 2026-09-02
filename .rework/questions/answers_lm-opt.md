## Q-OPT-1 — `run_windows` as an argument

**What I read**
`docs/04_CONTRACT.md:60-90` (the §0 "candidates examined and refused" table), `:1004-1010` (the question), `src/spine/assemble.py:85-135` (header prose), `:1117-1160` (the whole `NOT_WIRES` tuple), `:1435-1448` (`render()`'s "considered and rejected" block), `src/spine/compose.py:1822-1860` (`_run_windows`), `src/opt/api.py:98-102` (`build`'s RECEIVES), `tests/test_assemble.py:780-816` (A4).

**What is true today**
The question is LIVE and its premise is exact. `NOT_WIRES` holds **five** entries and I read all five: `RUN.seed → every package's d_seed`, `RUN.epochs → OPT.d_lr_horizon`, `SIG.d_signature_width_bytes …`, `EVAL.gist → the eval-path signature width`, `MEM.cap as its own lever`. There is **no** row for `d_run_steps` / `d_total_steps`. The rejection *is* written down twice elsewhere — `docs/04_CONTRACT.md:76` and `compose.py:1824-1832`, both of which say in as many words that this is the *second* ground (measurement-after-freeze) and not the `RUN.epochs` ground — but not in the one table `render()` prints into `docs/03_WIRING.md`.

The distinction is real and I checked the arithmetic behind it: `_run_windows` (`compose.py:1858-1860`) returns `units.Windows(_windows_in_epoch(sysm) * RUN.epochs)`, and `_windows_in_epoch` is `len(Segmentation.ids) // LM.ctx` — a value that does not exist until `TOK.tokenize` has run, which is several assembly rows after every `build()` has frozen.

**The options**
(a) Add the row. Cost: five lines of data in a tuple; `render()` prints it and A4 automatically requires it (the check iterates `NOT_WIRES` itself, so it cannot go stale). Buys: the printed wiring document states both rejections, side by side, with the distinct reasons — which is the whole stated purpose of that table.
(b) Leave it. Cost: the printed graph asserts the ledger is complete while omitting the most-proposed rejected candidate in the tree; the next reader re-derives it from `compose.py` prose or, worse, proposes it again. Buys: nothing.
(c) Fold it into the existing `RUN.epochs → OPT.d_lr_horizon` reason. Cost: merges two rejections with different grounds into one, which is precisely what `docs/04_CONTRACT.md:76` warns against ("both rejections are real and they are different").

**Recommendation**
**(a) — add one `NOT_WIRES` entry.** The tuple's own preamble says a rejection with a reason "is the only thing that stops the same candidate being added next quarter by someone who cannot tell it was considered", and this candidate was named by more than one spec.

**Why it fits the framework**
`NOT_WIRES` is DATA, not prose: `render()` (assemble.py:1442-1448) walks it and A4 (test_assemble.py:791-795) requires every entry to appear in the rendered text. Adding a row therefore extends a checked surface rather than adding an unchecked sentence. It touches no signature, no lever, no wire budget (still 19/25 — I built the ledger and printed it), and no `Coupling`. Adopted the other way, nothing breaks mechanically; what breaks is the claim `render()` makes about its own completeness.

**What changes**
`src/spine/assemble.py`, inside `NOT_WIRES`, one 2-tuple. Candidate string something like `"the run length in windows -> OPT.d_run_steps / d_total_steps"`; reason must contain the two clauses the tree already has: the stream length in windows depends on the tokenization, which has not happened when `build()` freezes; and this is a **different** ground from `RUN.epochs → OPT.d_lr_horizon`, which is rejected because it *is* the defect. Point at `compose.py:_run_windows` as the named computation. No test edit needed. No signature moves.

**Confidence**
High. I read the whole tuple and the A4 loop that consumes it.

**Literature**
NOT APPLICABLE. This is entirely about this tree's internal freeze semantics; no paper can say whether a value is computable before `Config.build()` returns.

---

## Q-OPT-2 — the LR schedule indexed by optimizer steps

**What I read**
`docs/04_CONTRACT.md:1011-1017`, `src/opt/api.py:22-46` (the module's own "THE COUNTER IS OPTIMIZER STEPS" paragraph), `:70-75` (the horizon block), `:118-154` (`lr_at`), `:180-235` (`maybe_step`, esp. steps 1-2), `src/spine/derive.py:347-394` (`opt_steps_from_windows`), `src/spine/units.py:100-118` (`Steps`, `Flushes`, `Windows`, `Backwards`), `self_organize.py:7093-7099` and `:7150-7155` (the old `_lr_at(step, …)` call and the `lr` writes), `src/opt/levers.py:339-392` (`lr_warmup`, `lr_wavelength`).

**What is true today**
This question is **largely no longer live as a decision** — the tree has already adopted it, in three coordinated places, and I verified each:
1. `maybe_step` step 1 (`opt/api.py:191-192`) advances `st.opt_step` (`units.Steps`) and calls it "the ONLY thing that advances it".
2. `lr_at(opt, st, opt_step)` takes that counter and is declared PURE.
3. `derive.opt_steps_from_windows` exists, is unit-typed (`Windows` in, `Steps` out, `UnitError` at both ends), and is covered by the oracle table (`tests/test_derive.py`, 575 cases, 0 mismatches — I ran it).

I confirmed the old counter was the *window* counter: `self_organize.py:7094` is `_lrv = _lr_at(step, …)` and `step` advances once per window. And the 64× claim is arithmetic, not rhetoric: `d_effective_batch_windows = batch_windows × accum = 16 × 4` at `fetch_big.py`'s own recommended command, and at the shipped `batch_windows=1, accum=1` the two counters coincide exactly, so no recorded number moves at defaults.

What is genuinely still open is only **accounting**: the contract says this "belongs on P9's list of numbers that moved", and there is no P9 list document — `grep` finds "P9's list" as scattered prose in `docs/04_CONTRACT.md:332, 1016, 1056` and one table row in `.rework/PLAN.md:186`.

**The options**
(a) Confirm the adopted reading and record it on a P9 list. Cost: one entry. Buys: the semantic change is attributable when a heavy-run number moves.
(b) Revert to the window counter. Cost: `units.Steps` becomes a lie again, `opt_steps_from_windows` becomes dead, and `lr_warmup` (a lever whose *name* is steps) means windows. Buys: nothing; it is the defect.
(c) Index by flushes. Cost: `accum` stops affecting the schedule while it does affect the batch — a 4× mis-labelled horizon at ACCUM=4. Buys: nothing.

**Recommendation**
**(a).** Confirm, and add the P9 entry. There is no live design choice left; the code position is already written and unit-enforced.

**Why it fits the framework**
`units.py:101` defines `Steps` as "Optimizer steps. What the LR schedule's horizon is denominated in, **and nothing else**". Indexing the schedule by anything else makes the one type in the system that exists for this quantity false. `opt_steps_from_windows` is also the *only* named cross-kind conversion into `Steps`, added specifically because the horizon division was inline on bare ints; reverting would leave that function with no caller (`K4`/`K6`-adjacent rot). Adopted the other way, `lr_warmup=1000` means "1000 windows" at BATCH_W=16 ACCUM=4 — a warmup that completes 64× sooner than its lever text says.

**What changes**
Nothing in `src/`. One line on whatever artifact P9's list becomes (`.rework/PLAN.md` or a new `docs/` note), attributing the movement to ISSUES P3-H29's counter repair and naming the 64× factor at `WIN=256 BATCH_W=16 ACCUM=4`. No signature moves.

**Confidence**
High for "already adopted and unit-enforced"; high for the arithmetic. Medium only on whether the owner wants the P9 list to be a file or a section.

**Literature**
BORE, and it agrees. Standard practice is unambiguous that the scheduler is stepped per **optimizer update**, not per micro-batch: warmup is "specified as a fixed number of optimizer steps rather than a batch count", and stepping the scheduler on every micro-batch under gradient accumulation is a recognised, filed bug ([huggingface/accelerate #963](https://github.com/huggingface/accelerate/issues/963), "Scheduler always steps when training with gradient accumulation"). See also [Kalra & Barkeshli, *Why Warmup the Learning Rate?*](https://arxiv.org/html/2406.09405v1) and [Ma & Yarats, *On the Adequacy of Untuned Warmup*](https://arxiv.org/pdf/1910.04209) for warmup being reasoned about in update counts. This supports the adopted reading; it does not override anything, because the framework already forces it.

---

## Q-OPT-3 — nothing in this system clips gradients

**What I read**
`docs/04_CONTRACT.md:1018-1027`, `src/opt/api.py:238-270` (`counters`), `:180-235` (`maybe_step`, and its DID IT FIRE list), `src/opt/levers.py:251-600` (all 13 declared levers, by grep of `Lever(`), `tests/test_census.py:DEPARTURES` and `check_n2_every_lever_traces_back`, plus exhaustive greps over the old tree.

**What is true today**
The factual claim is **confirmed, independently**. `grep -c "clip" self_organize.py` returns **2**, and both are prose about the forgetting measure F (`:920`, `:5203`). Across `self_organize.py`, `memory.py`, `tokenizer.py`, `vocab.py`, `datastream.py`, `world_model.py` there is no `clip_grad_norm_`, no `clip_grad_value_`, no manual norm clamp. In `src/`, the only hits are `opt/api.py:255-259` (the reporting proposal) and `derive.py:556-560` (F's clip-at-zero, a different thing). OPT declares 13 levers and none is a clip.

**Two things the question does not say, which I found and which change the shape of the answer:**

1. **The proposed measurement is declared in the wrong entry point.** `OPT.counters(opt, st)` claims to report `opt.grad_norm.p50/p99` "per optimizer step", but a global gradient norm can only be read *while gradients exist* — i.e. inside `maybe_step`, between step 4 and the `zero_grad` in step 5. `maybe_step`'s DID IT FIRE list (`opt/api.py:228-230`) names seven counters and **not** `opt.grad_norm`. A P4 implementer who follows `counters`' docstring literally computes a norm over freshly-zeroed grads and reports **0.0 for the whole run**, with every check green. That is a wrong-measurement record being written into the contract, of exactly the family the survey counts 98 of.

2. **Minting `OPT_GRAD_CLIP` is not merely "escalated" — it currently fails a test.** `tests/test_census.py` N2 requires every declared lever to trace to a census row or to a `DEPARTURES` entry, and `DEPARTURES` is keyed by `(family, old_knob)` — a divergence *from an existing census row*. A clip lever has no ancestor knob at all, so there is no legal `DEPARTURES` key for it; accounting for it requires amending `.rework/CENSUS.md` itself, which is the owner's ledger and not a code edit. N1-N5 are green today (I ran them).

**The options**
(a) **No clip, measure only** (the contract's position), with the measurement moved to `maybe_step`. Cost: one `torch.norm`-class reduction per due step. Buys: the second explanation for the 2.4→3.8-4.1 curve gets a number before anyone argues a default; nothing moves in any recorded result.
(b) Mint `OPT_GRAD_CLIP` defaulting to **0.0 = off**. Cost: a CENSUS.md amendment (owner's ledger) plus a `DEPARTURES` entry with no natural key; a lever shipped inert, which is the armed-but-inert family the survey counts 57 of — although "off by default and reachable" is the tree's own accepted shape for `weight_decay=0.0`. Buys: the ablation becomes runnable without a code change.
(c) Mint it defaulting to **1.0 = on** (standard practice). Cost: every future number is taken under a *different* confound, and the confound with `lr_sched` that this question exists to disentangle is replaced rather than removed; plus the same census cost. Buys: stability that the literature says is near-universal.

**Recommendation**
**(a), with one correction to where the measurement lives: the norm is taken in `OPT.maybe_step` and *reported* by `OPT.counters`.** Measure first, and measure over the **base** group only (under Q-OPT-6(a) the encoder's grads at flush time are SIG's, on a different cadence, and folding them into one number makes it uninterpretable). Do not mint a clip lever in this phase.

The reasoning: this project's stated failure mode is deciding on unmeasured mechanisms. `lr_sched="none"` is the one-flag ablation for the LR explanation; adding clipping *now* means the first heavy run confounds two changes. A recorded p50/p99 answers "were gradients ever large enough to matter" in one run, and if p99 is unremarkable the clip question dies without a lever. If p99 spikes, the case for (b) is then measured rather than borrowed.

**Why it fits the framework**
A measurement taken at runtime can never be a wire (`Coupling.compute` sees only frozen Configs — `assemble.py:107-113`), so a gradient norm is necessarily a counter, and counters belong on the package's own DID IT FIRE surface. `OPT.counters` is declared to *be* that surface, so reporting there is right; *taking* it there is impossible, and DID IT FIRE says a mechanism must be able to answer fired / armed-but-0 / unreachable — a norm computed after `zero_grad` answers "0" while meaning "unreachable", which is the exact distinction the discipline exists to preserve. Minting the lever fights the census spine: N2 is not a style check, it is the thing that stops the tree accumulating settings whose reason was never written down.

**What changes**
`src/opt/api.py`: add `opt.grad_norm.p50/p99` (and the base-group-only scope) to **`maybe_step`**'s DID IT FIRE list, stating that it is read between step 4 and the `zero_grad` of step 5; amend `counters`' paragraph at `:255-259` to say it *renders* the accumulated quantiles rather than computing them. Prose only, inside a frozen signature. **No signature moves.** If the owner instead picks (b) or (c): `src/opt/levers.py` gains a lever, `.rework/CENSUS.md` gains a row, `tests/test_census.py:DEPARTURES` gains an entry — and N2 will tell you loudly if any of the three is missing.

**Confidence**
High on the factual claim (two greps, both quoted) and on the N2 obstacle (I read the check body). High on the `counters`-vs-`maybe_step` defect. Medium on the recommendation itself — it would go to high with one recorded p99 from a real run, which is precisely what (a) produces.

**Literature**
BORE, and it is the clearest case in my slice. Global-norm clipping at `max_norm=1.0` is the near-universal default in transformer/LM training recipes — it is the default in HuggingFace Transformers, PyTorch Lightning and DeepSpeed, and clip-by-norm is preferred over clip-by-value because it preserves gradient direction and rescales magnitude only ([Composer method card](https://docs.mosaicml.com/projects/composer/en/stable/method_cards/gradient_clipping.html), [apxml: gradient clipping for transformers](https://apxml.com/courses/foundations-transformers-architecture/chapter-7-implementation-details-optimization/gradient-clipping-transformers)). So the literature's answer to "should an LM trainer clip?" is *yes, at 1.0*.
**And it does not override the framework here, for a reason worth stating plainly:** the literature establishes clipping as a *default*, not as a diagnosis. This tree's open question is not "is clipping good" but "which of two unmeasured mechanisms produced a measured curve", and turning on the standard remedy before measuring destroys the ablation that the remedy would be justified by. The census constraint (N2) then makes the cheap path — measure now, mint later on evidence — also the framework-compatible one. If the owner overrules and wants the default, the literature backs `1.0` global-norm and nothing else.

---

## Q-OPT-4 — `OPT.build(resume=…)` and `OPT.load_state(opt, st, saved)` overlap

**What I read**
`docs/04_CONTRACT.md:1143-1156`, `:1476-1482` (the frozen signature listing), `src/opt/api.py:59` (the signature), `:98-102` (RECEIVES), `:273-291` (`state_dict`), `:294-310` (`load_state`), `src/spine/compose.py:242-268` (the `CKPT.load` row and its six spellings), `:489-511` (the `optimizer` and `restore` ASSEMBLY_ORDER rows), `:1029-1033` (the `C`-stage `OPT.state_dict` row), `:1635` and `:1670-1680` (the ordering note and the real call), `src/capacity/api.py:46-81, 194-218` (the `new_valve(restored=)` / `CAP.restore` analogue).

**What is true today**
Live, and the overlap is exact: `compose.py:261` says `resume` is "Snapshot.payload again, OPT.build's spelling" and `:255` says `saved` is "Snapshot.payload again, LM.load_state's and OPT.load_state's spelling" — **one object, passed to two entry points, in adjacent rows**. `build`'s RECEIVES block (`:98-102`) explains `run_windows` and never mentions `resume`; `load_state` carries the L50 `param_group_shape` refusal and the `opt.ckpt.loaded/refused` counters.

**What I found that the question does not say, and it decides the answer:** option (a) describes work that does not exist. The live param-group structure is fully determined *before* `OPT.build` is called. `compose.py:1635` records that the module restores run "STRICTLY BEFORE OPT.build: replaying the grown population first is what lets…", and `param_groups` is built at `:1676-1678` from `_base_parameters(sysm)` (walking the already-restored LM/FAB/WORLD objects) plus `SIG.encoder_parameters(...)` (the already-restored encoder). There is no group structure left for `build(resume=)` to restore — the checkpoint's influence on group shape arrives through the module restores, not through OPT.

**A second, related defect sits inside this question and must ship with whatever is decided:** `compose.py:1029-1033` records that `OPT.state_dict` "DOES NOT SAY IT WRITES `param_group_shape`, which `OPT.load_state:297` refuses on and which `OptState` does not declare — a refusal armed against a value nothing produces". I confirmed both ends: `state_dict`'s docstring (`opt/api.py:274-286`) enumerates optimizers, `opt_step`, `n_backward`, `lr_prev`, `restart_amp`, `cycle_best`, `cycle_index`, horizon and counters, and no `param_group_shape`. **The L50 refusal is untrippable as written.**

**The options**
(a) `build(resume=)` restores group structure, `load_state` attaches moments. Cost: it is not true — nothing structural remains; writing it into the docstring makes the contract assert work the assembly order has already done, and creates a second restore path with no counters. Buys: both rows appear to do work.
(b) Documented dead weight; the root passes `None`. Cost: a parameter that can never do anything, which the DID IT FIRE discipline calls a defect even when the code is correct, and which the next reader will try to use. Buys: no signature moves this phase.
(c) Drop `load_state`. Cost: loses the only refusal on the path. Rejected.
(d) **(mine, not in the contract's list) Drop `resume` from `OPT.build`'s signature entirely.** Cost: a frozen signature moves — cheap now (`build` is a stub), expensive after P4. Buys: one restore path, one set of counters, one refusal, and no inert parameter.

**Recommendation**
**(d) — remove `resume=None` from `OPT.build`; `OPT.load_state` is the whole restore path.** If the owner will not move a signature in this phase, **(b)** is the fallback, but it must be labelled armed-but-inert in the report rather than described as restoring anything.

Whichever is chosen, **`OPT.state_dict` must declare that it writes `param_group_shape`** (and `OptState` must carry it), or `load_state`'s L50 refusal is a guard whose condition cannot be satisfied — the untrippable-guard family, 60 records.

**Why it fits the framework**
The DID IT FIRE discipline is decisive. `opt.ckpt.loaded` / `opt.ckpt.refused` live on `load_state`. A second entry point that also restores optimizer state means those counters describe one path while state moves through another — the same shape `Q-MEM-9` names one layer down ("if the probe open-codes a second retrieval then `n_reads` … describe one path while the store is moved by another"). K10 does not force `resume` to stay: it is a defaulted argument, so no producer is required, which is exactly why the hole is invisible to the checks today. And the CAP analogue the contract cites actually argues *for* (d), not for (a): `new_valve(restored=)` takes **the lifted cap alone** because `Valve.origin` must record where the starting cap came from — a fact the constructor genuinely cannot get any other way. `OPT.build` has no equivalent fact.

Adopted as (a): P4 writes a structure-restore in `build` that either duplicates what the module restores already did, or silently disagrees with them, with no counter on either outcome.

**What changes**
**LOUD — a frozen signature moves.** `src/opt/api.py:59` becomes `def build(opt: Config, *, param_groups, run_windows):`; `docs/04_CONTRACT.md:1476` (the signature listing K1 checks against) must move in the same edit or K1 fails. `src/spine/compose.py`: drop `resume` from the `("optimizer", "OPT", "build", …)` row text at `:489-497` and from the `CKPT.load` produces column at `:261`. Also, in every option: `src/opt/api.py:274-286` gains `param_group_shape` in `state_dict`'s enumeration and in the module's `OptState` line at `:49-50`, which also removes the `C`-row complaint at `compose.py:1029-1033`.

**Confidence**
High that (a) as written describes non-existent work — the ordering is stated in `compose.py:1635` and the `param_groups` construction is at `:1676-1678`. High on the `param_group_shape` gap. Medium on (d) over (b): it would go to high if the owner confirms that no future resume path needs OPT to see the blob before its optimizers exist.

**Literature**
NOT APPLICABLE. This is entirely about this tree's assembly order and its counter placement.

---

## Q-OPT-5 — the horizon is a projection and the epoch length is a measurement

**What I read**
`docs/04_CONTRACT.md:1158-1170`, `src/opt/api.py:70-84` (the horizon block and the `_project` history), `src/spine/compose.py:1822-1875` (`_run_windows` and `_windows_in_epoch`), `src/train/api.py:145-186` (`RunClock.begin_epoch`, `advance`, `counters`), `src/spine/derive.py:347-394` (`opt_steps_from_windows`), `:286-346` (`cadences_that_cannot_fire`).

**What is true today**
Live and correctly stated. `_run_windows` (`compose.py:1858-1860`) = `Windows(_windows_in_epoch(sysm) × RUN.epochs)` — epoch 0's measured length, extrapolated. `RunClock.begin_epoch(windows_in_epoch)` is "called once at start **and again after every roll, because a resampling stream is a different length each epoch**" (`train/api.py:150-152`). Both are `Windows`, so nothing raises. `compose.py:1846-1849` already records the mismatch and points at this question.

**The direction of the bias, which the question leaves open:** minting *merges* bytes into tokens, so `len(Segmentation.ids)` **falls** over the run and every later epoch is **shorter** than epoch 0. So the observed total is **less** than the projection, the run ends **before** the cosine completes, and the schedule finishes at a rate **above** `lr × lr_min_frac`. That is the same direction as the E8 `p=0.760` under-annealing the once-resolved horizon was introduced to kill — the machinery changed, the sign of the residual did not. The **magnitude is UNVERIFIED**: it depends on the mint rate, which nothing in this tree has run.

**The options**
(a) Keep the fixed horizon and print the projection against the observed total. Cost: one report line; the bias remains, but it is a number. Buys: an attributable residual instead of a silent one.
(b) Let `begin_epoch` revise the horizon. Cost: reintroduces `_project`/`_lr_total`/`_proj_lr` (`:6335-6376`), which produced E8 `p=0.760` and E18 `p=0.730`, plus the resume defect (H17) where `_ep_start=0` against a checkpointed `step` inflated epoch 0 and latched every later epoch at half the last. Buys: a horizon that tracks reality — if it worked, which it twice did not.
(c) Require `opt.lr_wavelength` explicitly. Cost: pushes the arithmetic onto the operator and makes two runs at different stream lengths incomparable unless the operator re-derives it; the `0` sentinel exists precisely so one visible place resolves it. Buys: nothing the print does not.

**Recommendation**
**(a), and the printed comparison is `derive.opt_steps_from_windows(Windows(observed_total), d_effective_batch_windows)` against `st.horizon.run_steps` — both `Steps`, so they are legally comparable and a mismatch is a subtraction, not a UnitError.** File the residual with the measured number attached and the sign named (under-anneal).

**Why it fits the framework**
This needs **no signature change and no new lever**, and that is the point. Both halves are already declared surfaces: `RunClock.counters()` is "the five typed counters plus the batch flush count" (`train/api.py:184-186`) and the window counter `step` *is* the observed total; `OPT.counters` already reports the resolved horizon. Neither package may read the other, so the **root joins them in the report** — which is what the root is for, and the same shape as `_periods` and `_n_params`. The conversion between the two kinds goes through the one named function, satisfying `units.py:86`. Adopted as (b), `begin_epoch` would have to write into a frozen `Config`-derived horizon after `build()` returned, which the freeze forbids, or `OptState` would acquire a mutable horizon — and then `load_state`'s "REPORTS when the horizon changed" is comparing against a moving target.

**What changes**
Prose only. `src/opt/api.py:238-265` (`counters`): add the comparison to what the report prints, naming `derive.opt_steps_from_windows` as the conversion and stating that the observed side comes from `RunClock.counters()`. `src/train/api.py:184-186` (`RunClock.counters`): state that the window total is one of the five and is the observed-length side of that comparison. Optionally one line in `compose.py`'s report assembly. **No signature moves.**

**Confidence**
High on the mismatch and on the once-resolved horizon being deliberate. High on the *sign* of the bias (minting shortens the token stream, therefore later epochs). **Low on the magnitude — UNVERIFIED, no run in this container.** It would rise to high with one recorded run printing both numbers, which is exactly what (a) delivers.

**Literature**
BORE, weakly, and only in support. Cosine schedules are horizon-dependent by construction and degrade when the actual training length differs from the length the schedule was specified for — "cosine schedules require pre-specifying the maximum learning rate and perform optimally only at the specified horizon", and intermediate/truncated points are "substantially suboptimal" ([Beyond Cosine Decay, CoLLAs 2025](https://arxiv.org/html/2503.02844v1); [Optimal Linear Decay LR Schedules](https://arxiv.org/pdf/2310.07831); [Anytime Pretraining, Kempner Institute](https://kempnerinstitute.harvard.edu/research/deeper-learning/anytime-pretraining-horizon-free-learning-rate-schedules-with-weight-averaging/)). That confirms the residual is worth measuring rather than assuming away. It does **not** recommend (b): the literature's own remedy for horizon uncertainty is a horizon-free/infinite schedule with weight averaging, which is a much larger change than this question, and re-projection-mid-run is precisely the family this tree has failed at twice.

---

## Q-OPT-6 — does `OPT.maybe_step` step the ENCODER optimizer?

**What I read**
`docs/04_CONTRACT.md:1242-1259`, `src/opt/api.py:180-235` (all five steps of `maybe_step`, and its DID IT FIRE list at `:228-230`), `src/opt/levers.py:275-300` (`weight_decay`), `src/sig/api.py:117-151` (`train_step`), `:153-175` (`warm_up`), `:251-268` (`encoder_parameters`), `src/spine/compose.py:722-733` (the `SIG.train_step` LOOP row), `:1702-1712` (the real `warm_up` call), and in the old tree `self_organize.py:3395-3402`, `:4750`, `:5024`, `:6649`, `:7093-7099`, `:7150-7155`, `:7283-7292`.

**What is true today — and half of this question is now STALE**
The measurement is confirmed, tighter than the question states. `grep -n "oe\." self_organize.py` returns **exactly two lines in 9,859**: `:5372` (`oe.state_dict()` into the checkpoint) and `:7154` (`for _g in oe.param_groups: _g["lr"] = _lrv`). There is **no** `oe.step()` and **no** `oe.zero_grad()` anywhere. `:7287` is `om.step(); om.zero_grad()` — the base optimizer alone. The encoder is stepped only inside `contrastive_step` (`:3401`: `opt.zero_grad(); loss.backward(); opt.step()`), which receives `oe` at `:5024` (warm-up) and `:6649` (the loop). So **SIG owned the encoder step in the run of record**, and `maybe_step` step 5's "step and zero_grad both" describes something that never happened.

**The first of the two consequences the contract lists is dead.** It says "with no `SIG.train_step` row the encoder's gradients were structurally zero" — that row now **exists**: `compose.py:722-733`, stage A, event-driven on `cadence_due`, and its own text ends "WITHOUT THIS ROW the run routes every window through a randomly initialised encoder while an AdamW steps it on zero gradients." The reviewer's finding was repaired. The **second** consequence is the live one and it is now *created* by that repair: under `maybe_step` step 5 as written, the encoder would be stepped by `SIG.train_step` on its Windows cadence **and again** by `maybe_step` on the flush cadence.

**One correction to the contract's stated harm.** "An AdamW step on zero gradients is not a no-op — decoupled weight decay multiplies the parameters by `(1 - lr·wd)`" is true in general but **inert at the shipped default**: `opt/levers.py:275` declares `weight_decay = Lever(0.0, …)`. With `wd=0` and structurally zero grads, the moments stay zero and the step genuinely is a no-op. The erasure is real only at `weight_decay > 0`, which the report itself tells the operator to set (`:7990`).

**The gate that option (b) destroys, verified in the old source:** `contrastive_step` returns *before* touching the optimizer when the loss is at the InfoNCE floor (`self_organize.py:3399-3401`, `if _fk > 0 and loss <= log(1 + (B-1)/_fk): return`). `sig/api.py:136` restates it: "The step is SKIPPED (loss returned, opt untouched)". The floor gates **the step**, not the loss. If `maybe_step` steps the encoder, the floor gates nothing.

**The options**
(a) `maybe_step` writes `lr` into every param group of **both** optimizers and steps **`base` only**; SIG owns the encoder step. Cost: `opt.lr.writes == opt.step` must be reworded, because the encoder now receives an `lr` write and no step. Buys: it is what was measured; it preserves `SIG.floor_kinds`' step gate and the three cadence levers `train_every`, `train_every_idle`, `dense_window` (and the `d_idle_cadence` wire that `SIG.cadence_due` reads).
(b) `maybe_step` steps both; `SIG.train_step` only computes and backwards. Cost: kills those three levers dead, kills the floor gate, and puts the encoder on the flush cadence — which is *not* the cadence SIG's `d_idle_cadence` wire exists to modulate. Buys: one step site.

**Recommendation**
**(a), unambiguously.** It matches the only measurement, it preserves four declared mechanisms, and it is the reading `SIG.train_step`'s frozen docstring already asserts ("the step is SKIPPED, opt untouched").

**Add one DID IT FIRE record that makes the regression detectable:** a counter proving `maybe_step` stepped the encoder **zero** times, so the double-step cannot be reintroduced silently. The rewording of `opt.lr.writes` should be: writes are counted per optimizer and both equal `opt.step`; `opt.step` counts **base** steps only; encoder steps are `sig.train_stepped` and live in SIG.

**Why it fits the framework**
Ownership spine: SIG owns the encoder's *objective* and its *cadence* (`sig/levers.py`'s `train_every`, `train_every_idle`, and the local wire `SIG.d_idle_cadence` computed from both). A package's cadence lever is only meaningful if that package's mechanism fires on it; stepping the encoder from OPT's flush gate makes three declared levers armed-but-inert **by construction**, which is the 57-record family. Option (b) would also mean SIG's loss floor — designed to gate the step — is a value nothing acts on. Frozen signatures permit (a) exactly as they stand: `maybe_step(opt, st, *, best_bpb=None, shift_at=None)` needs no new parameter, and `train_step(..., opt, ...)` already takes the optimizer it steps.

**What changes**
`src/opt/api.py:212` — step 5's clause becomes "write `lr` into EVERY param group of BOTH optimizers, then step and `zero_grad` **the base optimizer**; the encoder is stepped by SIG on SIG's cadence." `:228-230` — reword `opt.lr.writes (must equal opt.step, on BOTH optimizers)` per the above and add the encoder-steps-here-must-be-0 counter. This is **prose inside a frozen surface**, so it is the orchestrator's exception to the freeze, not this phase's edit. **No signature moves.** Nothing in `src/sig/` needs to change — its docstrings are already written for (a).

**Confidence**
High. Two greps over 9,859 lines with the full result quoted, plus the three call sites of `contrastive_step`, plus the existence of the `SIG.train_step` row at `compose.py:722`.

**Literature**
NOT APPLICABLE, and deliberately so. "Which of this tree's two optimizers does `maybe_step` step" is a question about this tree's call graph. No paper can answer it, and searching for one would have cost the turn.

---

## Q-OPT-7 — `OptState` declares "both AdamW instances" and names neither

**What I read**
`docs/04_CONTRACT.md:1260-1276`, `src/opt/api.py:48-53` (the RECORD TYPES block), `:59-68` (`build`, and its `param_groups` keys), `src/sig/api.py:117-124` and `:153-158` (both "THE ENCODER OPTIMIZER, BUILT BY OPT AND HANDED IN"), `src/spine/compose.py:489-503` (the `optimizer` row and its produces column), `:722-733`, `:1263-1275` (the `WORLD.manage` deferral), `:1702-1712` (the real call), `tests/test_contract.py` K11 (`check_k11_produces_is_not_fabricated`, in full).

**What is true today**
Live, exactly as stated, and worse than the question's summary in one respect: it is not a latent hole, it is **written down in three places as a known hole**. `opt/api.py:49-50` gives the two instances no field names. `compose.py:497-503`, the `produces` column of the `OPT.build` row, says the whole `OptState` crosses "so SIG is left to guess which optimizer it may drive — Q-OPT-7". `compose.py:1704-1709` says the same at the real call and adds "Recorded as Q-OPT-7 rather than closed by guessing a field name". And `compose.py:1266-1271`, the `WORLD.manage` deferral, says `add_param_group` "is OPT's `optimizer.add_param_group` as a callable, and `OptState` is declared as 'both AdamW instances' and NAMES NEITHER, so the root cannot address one without guessing a field — the identical hole recorded for SIG.warm_up as Q-OPT-7, **and one field on OptState closes both**."

So there are **two** blocked consumers, not one, and one is a whole deferred entry point.

**What I verified about option (a)'s payoff, which the question does not claim:** K11 (`tests/test_contract.py`) resolves a `produces` token by requiring it to appear in the entry point's docstring **or its module docstring — "which is where every package declares its RECORD TYPES RETURNED"**. So naming `base` and `encoder` in `opt/api.py`'s RECORD TYPES block does not merely document the fields; it makes `encoder` a **checkable** `produces` token, so the `OPT.build` row can hand SIG *the encoder* and K10/K11 will police the provenance. Option (a) buys enforcement, not just clarity.

**The options**
(a) Name the two fields — `base` and `encoder` — in the RECORD TYPES block, matching `build`'s own `param_groups` keys. Cost: one line. Buys: `sig/api.py`'s sentence becomes true; the root can pass `opt.encoder`; K11 can check it; `WORLD.manage`'s `add_param_group` gains a producer.
(b) Add an accessor entry point. Cost: a signature change **and** a new entry point, which K6 then requires a row or a deferral for. Buys: nothing (a) does not.
(c) Leave it. Cost: SIG is handed an object through which it can step the language model; `WORLD.manage` stays deferred for a reason that is one line away from being fixed; and P4, writing `SIG.train_step`, must guess a field name — which `compose.py:1707-1709` predicts produces "an AttributeError months from now in a file nobody is looking at".

**Recommendation**
**(a).** Name them `base` and `encoder`, and use the same two words in `build`'s `param_groups` keys, in the `OPT.build` row's produces column, and in the `WORLD.manage` deferral's replacement. One vocabulary, four places.

**Why it fits the framework**
This is the ownership spine at its narrowest. `sig/api.py:122` asserts that `opt` **is** the encoder optimizer; today the root cannot construct that value, so a frozen docstring asserts something the composition root is unable to supply — the same class of defect as `RUN.new_cadences` having no `periods` parameter while its docstring said every period is an argument (`compose.py:1714-1720`), which was found and fixed the same way. K11 makes the fix load-bearing rather than decorative. And it is genuinely **not** a signature change: `OptState` is a record type P4 defines, so naming its fields is prose that P4 then honours, and K1 (which checks signatures) is untouched. Adopted as (c), the boundary hole stays and `Q-OPT-6(a)` cannot even be *written*: under (a)-for-Q-OPT-6, `maybe_step` must write `lr` to both optimizers and step only one, and there is no expression for "the one".

**What changes**
`src/opt/api.py:49-50`: `OptState  base (the AdamW over param_groups["base"]), encoder (the AdamW over param_groups["encoder"]), n_backward (Backwards), opt_step (Steps), lr_prev, restart_amp, cycle_best, cycle_index, horizon, param_group_shape, counters` — note this is the same line that Q-OPT-4 needs `param_group_shape` added to, so both edits land together. `src/spine/compose.py:497-503`: the produces column hands `opt.encoder` to SIG rather than the whole state; `:1710-1712`: the real `warm_up` call passes `sysm.optimizer.encoder`; `:1266-1271`: the `WORLD.manage` deferral drops the `add_param_group` half of its reason (K12 checks that a deferral reason names the arguments with no producer, so this must be edited when the producer appears, not after). **No signature moves.**

**Confidence**
High. Three independent statements of the hole in the tree itself, plus I read K11's resolution rule to confirm the enforcement claim.

**Literature**
NOT APPLICABLE. A record's field names are this tree's vocabulary.

---

## Q-LM-9 — the gru arm's third dropout site is the memory-key source

**What I read**
`docs/04_CONTRACT.md:1028-1034`, `src/lm/api.py:69-112` (`build_model`, esp. the DROPOUT paragraph at `:85-92`), `:114-145` (`encode`), `:148-152` (`decode`), `src/lm/levers.py:337-359` (the `dropout` lever and its whole comment block), `src/spine/compose.py:804` (the `h` produces token), `:906` and `:1408-1412` (`key_fn = LM.encode` bound), `:2099-2107` (`_key_fn`), and in the old tree `self_organize.py:1546-1562` (`MiniLM`) and `:1563-1594` (`TinyTransformer`).

**What is true today**
Live, and the internal disagreement is already visible on two surfaces. `self_organize.py:1556-1558` is three dropout sites — `s.drop = nn.Dropout(DROPOUT)`; `h, _ = s.gru(s.drop(_e))`; `return s.drop(h)` — and the source's own comment on the return line reads `(B,L,D) hidden -- also the memory-key source`. `lm/api.py:85-88` names all three ("the embedding dropout, the inter-layer dropout at depth > 1, AND the dropout on the returned hidden state … three sites, of which the lever's help text names two"). And `lm/levers.py:337-338` still says exactly two: *"Dropout probability on the token embedding, and between GRU layers when depth is greater than one."* That help text is what `docs/04_LEVERS.md` and the operator see.

**The consequence is real and I traced the path:** `compose.py:2107` binds `key_fn = lambda x, **kw: lm_api.encode(lm, sysm.model, x, **kw)`, and `MEM.write` / `MEM.maintain` take that as `key_fn`. So the memory keys **are** `encode`'s return. With `dropout > 0` and the module in train mode, every key written during the loop is computed through a dropped-out hidden; at eval the same function returns the undropped hidden. The store goal B is measured on is then queried with keys drawn from a different distribution than the ones it holds. `FAB.forward` also consumes `h` (`compose.py:804`), so the router's input is dropped out too.

Inert at the `0.0` default — but `lm/levers.py:346-348` records that the report at `:7990` **instructs the operator** to raise it the moment the held-out gap exceeds ~0.5.

**The options**
(a) Status quo: `encode` returns the dropped hidden; keys are dropped out. Cost: a train/eval key mismatch in the store goal B is measured on, plus a router input that differs between train and eval. Buys: bit-identical to the old tree at any `dropout`.
(b) `LM.encode` returns the **undropped** hidden; the output dropout moves into `LM.decode`, applied to `h` before the head. Cost: at `dropout > 0`, `FAB.forward`'s input and the memory keys change (both lose dropout) — a P9 entry; nothing moves at `0.0`. Buys: keys and router input are train/eval consistent **structurally**, the LM's own regularisation is arithmetically unchanged (old: `head(drop(h))`; new: `decode` does `head(drop(h))`), and `nn.Dropout` is inert in eval mode so the eval path needs no flag.
(c) Add a keyword to `LM.encode` (e.g. `for_key=True`). Cost: a frozen signature moves, and a second "which path am I on" flag sits beside `n_layers`, which the gru arm already ignores — two path flags with different arm semantics is how `KEY_LAYERS` became "silently inert twice over" (CENSUS.md:250).

**Recommendation**
**(b) — move the third dropout site out of `encode`'s return and into `decode`, before the head.** Then state the invariant plainly: **`LM.encode` returns the representation; `LM.decode` performs the regularised readout.** And fix `lm/levers.py`'s help text to name all three sites in whatever form survives.

**Why it fits the framework**
It is the only option with **no signature cost** that makes the property structural rather than conventional. `LM.decode` is already declared "THE ONLY PLACE LOGITS ARE PRODUCED" (`lm/api.py:148`), so the readout regulariser belongs with the readout; `encode` is declared "the memory-key source and the fabric's input" (`:114`), and a value three packages consume should not carry one consumer's regulariser. It also removes a hidden dependence on module mode from a cross-package value: under (a), what MEM stores depends on whether some *instrument* left the model in train mode — which is ISSUES.md:441 (`holdout_bpb`'s finally block returning the model to TRAIN unconditionally), recorded in `lm/levers.py:349-353` as a bug the new tree fixes under the G7 instrument line. Under (b) that instrument bug can no longer corrupt the store, because the key path has no dropout to leave switched on.

Option (c) fights the frozen signatures for no gain; option (a) leaves a lever whose declared blast radius (LM) is smaller than its actual one (MEM's store, FAB's router), with **no wire recording it** — and no wire can, because it is not a value, it is a code path.

**What changes**
`src/lm/api.py:85-92` (`build_model`'s DROPOUT paragraph): state that the readout dropout is applied in `decode`, not on `encode`'s return, and why. `:114-116` (`encode`'s first line): state that the returned hidden is **undropped**, and that this is what makes the memory-key path train/eval consistent. `:148-152` (`decode`): state that it applies the readout dropout before the head, and that this is arithmetically the old `head(drop(h))`. `src/lm/levers.py:337-338`: the help text must name all the sites it reaches — currently two of three. Add to P9's list: at `dropout > 0`, FAB's routing input and MEM's keys change. **No signature moves.**

**Confidence**
Medium-high. High on the facts: three sites, the lever text naming two, and `key_fn` being `LM.encode` — all read directly. Medium on the recommendation, because whether removing dropout from **FAB's router input** is desirable is unmeasured (everything was recorded at 0.0), and because MEM's own view of key stability is another slice's (see cross-slice). It would rise to high with MEM confirming that `rekey` re-encodes through the same `key_fn` and therefore inherits the same property.

**Literature**
BORE, but weakly, and I will not overstate it. The relevant standard practice is that a retrieval datastore's keys are the model's hidden representation produced by running the LM forward over a corpus, and that this is done with the model in evaluation mode so keys are deterministic and comparable to query-time keys ([kNN-LM line of work](https://arxiv.org/pdf/2301.02828); [Efficient kNN-LM](https://github.com/jxhe/efficient-knnlm)). I did **not** find a paper that measures the degradation from building a datastore with dropout active — so I am claiming a convention, not a result. It supports (b) and is not the reason for it; the reason is that (b) is the only zero-signature-cost option in this framework.

---

## Q-LM-12 — what call produces `WORLD.loss_terms`' `obs_emb`?

**What I read**
`docs/04_CONTRACT.md:1338-1348`, `src/world/api.py:58-75` (`loss_terms`), `src/lm/api.py:69-112` (`build_model`, esp. the compose paragraph at `:73-79`), `:114-145` (`encode`), `src/spine/compose.py:838-846` (the `WORLD.loss_terms` LOOP row), `:1386-1389` (the `ROW_ARGUMENTS_ELSEWHERE` entry for the same argument), and in the old tree `self_organize.py:1546-1562`, `:1563-1594`, `:4156`, `:4166`, `:6813`, `:8223`.

**What is true today**
Live, and I found two things that settle it.

**First: the tree already says two different things about this argument, in one file.** `compose.py:838-846` (the LOOP row) says "LM EXPOSES NO EMBEDDING ENTRY POINT … whether encode with `n_layers=0` is the embedding is nowhere stated — Q-LM-12". `compose.py:1386-1389` (`ROW_ARGUMENTS_ELSEWHERE`) says "`obs_emb` is LM's embedding of the batch — **the model's embedding table applied to the same cut LM.encode took**, which is a tensor operation the loop does between two calls." The second is a decision the first says has not been made.

**Second: that second answer does not run.** `lm/api.py:76-79` states that under `compose=True` the embedding and head "are **NOT constructed at all**, so the ~6.3M dead parameters ISSUES P1-L13 counts … do not exist." So `model.emb(x)` in the root is an **AttributeError on every run with `LM.compose=1`** — a supported configuration with its own lever. The old tree hid this: `MiniLM.__init__` (`:1549-1550`) *always* constructed `s.emb`, and used the ByteComposer's table instead when compose was on (`:1558`), so `self_organize.py:6813`'s `world_enc(model.emb(x))` did not crash at `TOK_COMPOSE=1` — **it fed the world model an embedding table the LM was not training**. `TOK_COMPOSE` defaults to 0 (`:132`, `:979`), so no recorded run hit it; the new tree turns the same latent confounder into a crash.

**Third: option (a) is false on both arms.** `LM.encode`'s own docstring (`:122-125`) says `n_layers` "runs only the first n blocks **on the transformer arm** … **On the gru arm it is accepted and ignored**, and that is a DECLARED GATE". So on the gru arm — the shipped arm — `n_layers=0` returns the full GRU hidden, which is exactly what `obs_emb` must not be. And on the transformer arm, `self_organize.py:1587` is `h = s.emb(x) + s.pos(p)`, so "zero blocks" is embedding **plus positional**, which is not what the old world encoder received either (`:6813` passes `model.emb(x)` alone).

**The options**
(a) State that `LM.encode(..., n_layers=0)` is the embedding. **Refuted above** on both arms.
(b) Add an `LM.embed(lm, model, x)` entry point returning `(B, L, width)` — the token vector table applied to the ids, which is `s.emb(x)` when compose is off and the ByteComposer's table lookup when it is on. Cost: **a signature change** — a new frozen entry point, which K6 then requires a row for (the `WORLD.loss_terms` row supplies it, so K10's producer hole closes at the same time), and one more of the 121. Buys: works on both arms and under compose; keeps LM's module tree inside LM; makes goal A's modality claim testable rather than asserted.
(c) Let WORLD take the hidden and correct `world/api.py`'s modality claim. Cost: gives up "a second sense needs only new embedding rows" — goal A's *room for more modalities* — and the world model then predicts the dynamics of a GRU state rather than of observations, which is a different mechanism wearing the same name. Buys: no new entry point.
(d) The root reaches into `model.emb` (what `ROW_ARGUMENTS_ELSEWHERE` currently says). **Crashes under `LM.compose=1`**, and puts LM's internal attribute name in the composition root.

**Recommendation**
**(b) — add `LM.embed`.** The contract's own rule was "(a) *if the arm really returns the embedding table's output*, otherwise (b)". It does not, on either arm, and I quoted the lines. So (b).

**Why it fits the framework**
The compose lever is decisive: only LM knows whether the token vector table is `emb.weight` or the ByteComposer's output, and `build_model` is explicit that under compose the former does not exist. Any answer that reaches for the table from outside LM is a package-internals read that the ownership spine forbids in spirit and that `K7` does not catch (it checks `Config` reads, and `model` is not a Config) — an untrippable-guard shape, where the check is green because it is looking at the wrong surface. The `n_layers` precedent also argues for a **named entry point** rather than a magic argument value: `n_layers` is a declared gate that one arm ignores, and CENSUS.md:250 records that being "silently inert twice over"; loading a second meaning onto the same argument repeats it.

Adopted as (c), `world/api.py:6-7`'s claim that a second modality needs only new embedding rows becomes false with nothing in the tree saying so — which the LOOP row at `compose.py:842-845` already identifies as the cost.

**What changes**
**LOUD — a frozen surface gains an entry point, and 116 of 121 are stubs, so this is cheap now and expensive after P4.** `src/lm/api.py`: new `def embed(lm: Config, model, x)` → `(B, L, width)`, with a docstring stating (i) it is the token vector table's output, ByteComposer's under `compose` and `emb`'s otherwise, (ii) it is **not** `encode` and carries no positional term, (iii) it is the point where a new sense plugs in. `docs/04_CONTRACT.md:~1440` (the signature listing K1 reads). `src/spine/compose.py`: a new `("B", "LM", "embed", …)` row producing `obs_emb`, placed before the `WORLD.loss_terms` row; delete the `"WORLD.loss_terms"` entry from `ROW_ARGUMENTS_ELSEWHERE` at `:1386-1389` (it becomes a real producer, and K10 reads the produces column first); amend the `WORLD.loss_terms` row text at `:838-845` to stop naming this as open. `src/world/api.py:60-61` can then say `obs_emb` arrives from `LM.embed`.

**Confidence**
High. The refutation of (a) is quoted from `lm/api.py:122-125` and `self_organize.py:1587`; the refutation of (d) is quoted from `lm/api.py:76-79`; the old tree's `world_enc(model.emb(x))` is at `:6813` and `:8223`.

**Literature**
NOT APPLICABLE. Which tensor this tree's world model should observe is a question about this tree's module structure and its own modality claim. (The general JEPA/latent-forward-dynamics literature would say "predict in a latent space over observations", which is the same thing `world/api.py:58-63` already says; it adds nothing to the choice between these four options.)

---

## Q-CLOCK-1 — retire `FAB.d_cap_lift_period` and `TOK.d_cap_lift_period`?

**What I read**
`docs/04_CONTRACT.md:900-910` (the question), `:112-131` (§C2), `:909-943` (Q-DERIVE-1 RESOLVED and "Repair (b) survives as reporting only"), `src/spine/assemble.py:785-822` (both `Coupling` rows in full), `src/spine/derive.py:424-522` (`pin_tick`, including the two `UnitError` messages), `src/fabric/api.py:285-310` (`grow_check`), `src/tok/api.py:250-316` (`lift_vocab_cap`, `vocab_state`), `src/capacity/api.py:89-100` (`observe`), `:225-239` (`counters`), `src/spine/compose.py:2132-2158` (`_periods`), `src/spine/derive.py:286-346` (`cadences_that_cannot_fire`), `tests/test_contract.py:232-246` (K5's own note about these two wires), `tests/test_census.py:DEPARTURES`.

**What is true today**
The pin-clock repair is done and I verified it independently of the prose: `derive.pin_tick` raises `UnitError` on a `Flushes` or `Steps` `held` (`derive.py:499-507`) and on a non-`Windows` `dstep` (`:508-512`), and `tests/test_derive.py` runs 575 oracle cases with 0 mismatches (I ran it). Both `d_cap_lift_period` rows still exist (`assemble.py:785-800` and `:810-822`), both compute `derive.flush_period_windows(Windows(CAP.pin_windows), OPT.batch_windows)` → `Flushes`, and both are read exactly once, for reporting: `fabric/api.py:306` and `tok/api.py:313`. I built the ledger: **19 wires of a 25 budget, 23 couplings.** The two rows are **CAP's only outbound edges** — the package graph is `CAP → (FAB, TOK)` and nothing else sources CAP.

**What decides it, and it is not in the question's option list.** `CAP.counters` (`capacity/api.py:225-234`) already declares `pin_windows` in `LEVERS READ`, already holds "the four high-water marks", and already declares **THE BLOCK-REASON HISTOGRAM**, whose stated purpose is verbatim the thing the reporting wires exist for: *"round11 pinned 42,425 against a threshold of 20,000, lifted nothing, and left no evidence of which of the two remaining conditions refused."* That is a strictly better answer than a converted period printed in a foreign package: it is in the package that owns the valve, in the unit the valve actually compares (`pin_windows`, Windows), with the pinned high-water mark beside it, and it separates *never full* from *never plateaued* by naming the blocking condition rather than leaving the reader to infer it from a cadence.

So the two reporting wires are a **second report path for a question CAP already answers better** — which `spine/wire.py`'s own docstring names as the failure it exists to prevent ("the old tree had a report path and an audit path formatting one quantity two ways, and they drifted").

I also checked the alternative home I expected to prefer, and it does **not** work: `_periods` (`compose.py:2138-2158`) is the *same object* `RUN.new_cadences` and `RUN.cadence_audit` both receive, and `cadence_audit`'s own row insists on that identity ("or the audit would describe gates other than the ones evaluated"). CAP's valve is not a `Cadences.due` gate — CAP ticks its own clock inside `observe` — so adding `pin_windows` to `_periods` would manufacture a gate RUN evaluates and CAP also evaluates. Rejected.

**One stale statement I found while verifying this, worth reporting:** `tests/test_census.py`, `DEPARTURES[("capacity", "GROW_CAP_EVERY")]`, still says *"derive.pin_tick still accumulates a Steps clock, so the port is not finished and applying both legal repairs at once fires the valve 16x too EARLY."* The first clause is false as of the 2026-08-30 repair. N3 checks that a departure still *lands*, not that its prose is current, so the test is green and the sentence is wrong.

**The options**
(a) Keep both rows as reporting wires (what is written). Cost: two of the 19 wires carry a value nothing compares against; CAP's only outbound edges in the coupling graph are a report line, which misdescribes the real CAP→FAB/TOK relationship (a runtime `Caps` record passed as `soft_cap` / `to`); and the "0 lifts" question gets answered in two places, in two units. Buys: no edits.
(b) Delete both rows. Cost: a joint edit across ~8 files — K5 fails loudly if the rows go and the reads stay, which is the right failure; and `derive.pin_tick`'s `UnitError` message names both wires and must stop. Buys: 2 of 25 budget back (19→17); `grep -rn d_ src/` stops indexing a coupling that carries no decision; CAP becomes a pure sink, which is the truth — CAP hands over **values at runtime**, not periods at build time; and the "0 lifts" answer lives in one place, in the owning package, in the right unit.
(c) Retarget to CAP. Refused, correctly: under repair (a) a converted period is the 16×-early fault.

**Recommendation**
**(b) — delete both rows**, conditional on one thing the owner can confirm in a sentence: that `CAP.counters`' block-reason histogram plus the pinned high-water mark is the report line that answers "0 lifts: never full, or never plateaued?". I read its docstring and it says exactly that.

This agrees with the contract's own recommendation and with three specs — but the contract's stated *reason* ("a row nothing but the report reads is a row a future author will 'fix' by connecting it") is the weakest available one, and I would not act on it: that trap is already foreclosed by construction, because `Windows >= Flushes` raises and `pin_tick` refuses a `Flushes` by name. The reason to delete is the one above: the capability is already owned, in the right package and the right unit, and keeping the wires makes CAP's only ledger edge a duplicate report.

**Why it fits the framework**
The wire rule is that a `d_` field records a **coupling** — a value one package computes from another's levers and *uses*. Under repair (a) these two are the residue of a repair that was applied elsewhere; the ledger's claim is that `grep -rn d_ src/` is a complete index of the couplings, and an index whose entries include values no decision reads is an index that is harder to audit in exact proportion to how carefully it is read (`assemble.py:85-88` makes that argument itself, about local couplings). The DID IT FIRE discipline is satisfied without them, and satisfied better: the histogram distinguishes the two zero-cases by *naming the blocking condition*, which a period cannot do.

Adopted the other way (keep), nothing breaks and the tests stay green — this is the one question in my slice where both answers run. What is lost is that CAP's DID IT FIRE surface and two foreign packages' report lines answer the same question in two units, and the tree's records say that is how report paths drift.

**What changes**
`src/spine/assemble.py`: delete the two `Coupling` rows at `:785-800` and `:810-822`. `src/fabric/api.py:294-297` (the `WIRES READ` line) and `:306` (the `_ =` read) — **must** go in the same edit or K5 fails ("no stub reads an undeclared one"); the sentence about distinguishing "0 lifts" moves to pointing at CAP's histogram. `src/tok/api.py:309` and `:313`, same; plus the paragraph at `:255-259` in `lift_vocab_cap`. `src/spine/derive.py:504-507`: the `UnitError` message must stop naming two wires that no longer exist (its point — do not convert the threshold — stands on its own). Prose corrections: `src/capacity/api.py:21`, `src/capacity/levers.py:112, 140`, `src/opt/levers.py:133`, `src/tok/levers.py:98, 124`, and `docs/04_CONTRACT.md:116-131, 251, 324, 900-908, 936-943`. And separately, whether or not this is adopted: `tests/test_census.py`'s `("capacity","GROW_CAP_EVERY")` departure text is stale and should stop saying the port is unfinished. **No signature moves.** Wire budget 19 → 17 of 25.

**Confidence**
Medium-high. High on every fact (the two rows, the two readers, 19/25, CAP's edges, `CAP.counters`' declared histogram, `_periods` not being the right home, the stale DEPARTURES text). Medium on the recommendation, because it rests on `CAP.counters` — a **stub** — actually rendering the histogram beside the pin high-water mark at P4. If the owner would rather not bet on an unwritten body, (a) is defensible and costs 2 wires of a budget with 6 free.

**Literature**
NOT APPLICABLE. This is a question about one ledger's contents and one package's report surface.
