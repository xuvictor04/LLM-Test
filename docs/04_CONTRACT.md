# docs/04_CONTRACT.md — the frozen mechanism contract

Written at the contract phase from five independent mechanism specs covering disjoint slices of the
old system. The five agents did not talk to each other. This document is the **join**: the
reconciliation, the conflicts resolved from the source, the wires that were missing and are now
declared, the levers that still have no reader, and the questions left for the owner.

**What is frozen here is the SIGNATURE SET.** Ten implementation agents will fill these bodies in
independently, and the only thing keeping them compatible is that the names, the parameters and the
return shapes below do not move. Everything else — the internal module split inside a package, the
private helpers, the tensor layout — is P4's business.

**How to read a signature.** Every entry point in `src/<pkg>/api.py` carries, in its docstring, in
this exact machine-readable form:

```
LEVERS READ: <comma-separated field names this package owns>
WIRES READ:  <comma-separated d_ fields, or "none">
DID IT FIRE: <the counters that prove the mechanism executed, in G4's three states>
```

`tests/test_contract.py` parses those blocks. **All 262** of the declared levers are named by at
least one stub as read by it — **261, not 259, since 2026-09-02: there are now TWO CENSUS
AMENDMENTS, `OPT_GRAD_CLIP` under Q-OPT-3 and `MEM_JUDGE_FRAC` under Q-MEM-8** (see
`.rework/CENSUS.md`, section `amendments`, which holds both and states that the census's 328 is
unchanged by either) — and
**261 read, not 258, also since 2026-09-02**: Q-FAB-1 and Q-FAB-2 gave the last two unread levers
(`FAB.hop_mode`, `FAB.merge_dist`) readers rather than dropping either, so **UNCONSUMED LEVERS**
below is now an empty table with the two rulings under it. K4 reads that table, so a future lever
with no reader still lands there with a reason or the check fails.
**Naming is not calling**: which stubs the composition root actually reaches is section 3, and 108
of the entry points (§7 holds the count, and it is the only place that does — this sentence was one
of five copies) are named by a row — 94 in a row's entry column and 14 by a call written
into a row's note — with the remaining **23 declared deferred**, each with the argument that has no
producer as the reason. That number was seven until the order tables grew a `produces` column and
the same standard was applied to every row rather than to EVAL alone (§3.6). *(This sentence said
"14" while `DEFERRED_ENTRY_POINTS` held 15; corrected 2026-09-02. K6 prints all three numbers, so
the count is checkable from the suite rather than from here.)*

**Executable today.** `python3 -c "import sys;sys.path.insert(0,'src');from spine.compose import
compose; compose(environ={})"` runs the composition root against the stubs and stops at the first
unimplemented one with `NotImplementedError: RUN.process_setup: P4 (train) fills this in`.

---

## 0. What was added to the wiring, and why

The five specs between them named **nine** cross-package values that are resolvable from frozen
levers and that every receiving package's own `levers.py` already records as an expected `d_` field
it does not receive. Each one was arriving — or failing to arrive — as an argument the composition
root would have been free to compute differently, which is invisible to `affects()`, and
`affects()` is the only oracle the L3 isolation sweep has. All nine are now rows in
`spine/assemble.py`. The ledger went from 13 rows / 10 wires to **23 coupling rows — 19
cross-package wires of a 25 budget, plus 4 intra-package — and 7 rejected candidates in
`NOT_WIRES`**. *(This sentence said "22 rows"; corrected 2026-09-02 while Q-OPT-1 added the
`d_run_steps` rejection. Do not restate these numbers elsewhere: `tests/test_assemble.py`'s A4
prints all four from the live tables and `render()` embeds the ledger summary, so any prose copy is
one that can go stale in silence — this one had.)*

| new row | src | why it is a wire and not an argument |
|---|---|---|
| `LM.d_max_token_bytes` | `TOK.max_bytes` | `ByteComposer.__init__(s, d, maxb=16)` at `:1441` is constructed as `ByteComposer(d)` at `:1549` so the default always wins, and `:1487` truncates. With `MAX_TOK > 16` two long tokens sharing their first 16 bytes get **identical composites** — the composer's whole property, inverted, silently (ISSUES P1-M21). `lm/levers.py:165` names the field; `tok/levers.py:337` records the row as missing. The defaults agreeing today is luck. |
| `CAP.d_expert_slots` | `FAB.slots` | `CAP_FAB_START = 0` is a **sentinel meaning "start at the hard ceiling"**, and `lever.py` refuses a default computed from another lever — so 0 stood for a number nothing supplied. `capacity/levers.py:119`, and `:123` says in as many words that the row is absent. |
| `CAP.d_vocab_slots` | `LM.vocab_slots` | The same sentinel on the other target. `capacity/levers.py:244` records that TOK holds no ceiling of its own to give. |
| `CAP.d_mask_dead_rows` | `LM.mask_dead_rows` | The honesty precondition on the vocabulary arm: 8192 reserved against 2048 minted is 6144 rows in the softmax denominator indexing nothing, so the run measures the reservation and not the mechanism. LM owns the output layer; CAP does not get to decide this. |
| `CAP.d_operating_population` | `FAB.pressure × FAB.slots` | The irreducible coupling the valve must **declare rather than remove**: a soft cap above the cull's settling point never pins, so the pin clock never accumulates and the valve is dead while looking armed. A second landing of the identical `derive.operating_population` call, so the fabric's setpoint and the valve's refusal cannot disagree. |
| `DOM.d_comp_ema` | `FAB.comp_ema` | One smoothing rate for two populations, or "this domain beats the population" is a comparison between two differently smoothed series. `fabric/levers.py:693` names both this and the next; `self_organize.py:6720` is the direct attribute reach it replaces. |
| `DOM.d_comp_protect` | `FAB.comp_protect` | One brake policy for two populations. The domain cull is the mechanism that deleted 200,000 memory entries under a phased schedule. |
| `FAB.d_base_lr` | `OPT.lr` | `:7252` builds the per-expert envelope from the **peak**. Until some name lands, `FAB_LR_OWN=1` has no legal way to learn the number — which is what makes ISSUES P1-H15 (`NameError: _lrv`) spellable. Named `d_base_lr` and not `d_lr_peak` because the **receiver** already declares that spelling (`fabric/levers.py:848`) and the receiver's `grep d_` is the one that has to find it. This settles the open name conflict `opt/levers.py`'s conflict (b) records — **and that paragraph said "neither in `spine.assemble.COUPLINGS`" until 2026-09-03, when the row had been in the ledger for a day; it now records which spelling lost.** |
| `FAB.d_lr_min_frac` | `OPT.lr_min_frac` | `:7251` is `_lo = LR * LR_MIN_FRAC`, needed in the same block; shipping one endpoint without the other leaves the fabric with half a rate. |

Consequences recorded in the fixtures rather than hidden: `affects("FAB_SLOTS")` widens to
`{FAB, DOM, MEM, CAP}`, `affects("FAB_PRESSURE")` from `{FAB}` to `{FAB, CAP}` (it previously fed
only a LOCAL coupling, which books no edge), `affects("LM_VOCAB_SLOTS")` to `{LM, TOK, CAP}`, and
**TOK is no longer a pure sink** — it sources `LM.d_max_token_bytes`, so it appears in the package
graph as a key as well as a target. That is legal and is not chaining: no coupling reads a `d_`
field, so `affects()` stays one hop.

### Candidates examined and refused as wires

Each of these was named by at least one spec as a `d_` field and **cannot be one**, because a
`Coupling.compute` receives only frozen Configs and `Config` freezes when `build()` returns. They
arrive as named arguments the composition root passes. Saying so here is the point: *a
promote-to-wire that quietly became nothing is indistinguishable from one nobody noticed.*

| named as | actual route | reason it cannot be a wire |
|---|---|---|
| `EVAL.d_holdout_bytes` | `Areas.holdout_bytes` → argument, recorded as a Sample field | the held-out size depends on how many bytes are on disk; `build()` would have to stat the corpus, which puts IO inside the ownership spine and makes startup non-reproducible. Wiring `DATA.val_cap` instead would print the **ceiling** as the size — a wrong-measurement record waiting to happen. |
| `d_curve_bpb`, `d_best_bpb` | arguments to `Retention.consider` / `maybe_step` | held-out **measurements**, produced thousands of windows into the run. `d_best_bpb` additionally carries a seed count, because a damped restart is a verdict and PLAN 3.8 forbids a verdict on n=1. |
| `d_run_steps` / `d_total_steps` | `run_windows` argument to `opt.build` | the stream length in windows depends on the **tokenization**, which has not happened at freeze. This is the *second* NOT_WIRES ground, not the `RUN.epochs → d_lr_horizon` one; both rejections are real and they are different. |
| `d_shift_at` | argument to `maybe_step` | the optimizer step of the last self-inflicted shift is runtime state. The old form read it as a **closure variable** written by DATA's resample branch (`:6518-6521`). |
| `d_residual_ratio` | `LM.residual_ratios(lm, model)` → argument to `judge_probation` | read off a live tensor **after `build()` freezes**, so no compute can see it. It was routed from `MintReport.residual_ratio` until 2026-09-02, which is mint time — zero by construction (Q-TOK-11). At `lm.compose = False` the call returns None and TOK's `probation_by="embed"` arm is Gate-declared unreachable rather than silently running the "use" test (ISSUES P1-M41). |
| `d_live_vocab`, `d_retired_ids` | arguments to `decode` | change on every mint. |
| `d_live_domains` | argument to `fab.forward` | changes at every domain manage pass. `fabric/levers.py:408` calls it a wire; this is a correction to that comment, not a disagreement with L2 — the value still arrives from outside and the reader still never names the foreign lever. |
| `d_last_boundary`, `d_prototype_reservoir` | arguments to `cadence_due` / `train_step` | same shape; `sig/levers.py:385` calls the first a wire. |
| `d_mem_floor_entries` | argument to `dom.manage`, from `MEM.census()["floor_entries"]` | the floor is `src_share × capacity / live_eligible_sources` and the divisor is live state — 125 sources holding entries against 27 live domains on a measured run, a 4.6× swing. A wire quietly recomputed at the call site is `self_organize.py:3688` under a new name. |
| `SIG.d_signature_width_bytes` | `_signature_width()` in `compose.py` → argument to `sig.build` | already refused in `assemble.NOT_WIRES`: `bytes_per_token` is measured on a corpus the tokenizer has not seen. |
| `d_device`, `d_seed` | arguments / `rng_for(name, seed)` | `d_seed` is refused by name in `NOT_WIRES`; what a package needs is its own named stream, and `rng.issued()` is the check that catches deriving under the wrong name. `device` is a torch object, not a lever value, at the point of use. |
| `FAB.d_model_width`, `FAB.d_signature_dim` | constructor arguments | judged not to clear the bar: no recorded defect from the two ends disagreeing, and the checkpoint-geometry failure they were proposed for (`:4678-4684`, "can be failing on FAB_EMB_HID, SIG_D or D_MODEL") is answered by `CKPT.check_geometry`'s named manifest instead. Recorded as a live candidate; the budget has 6 rows left. |

---

## 1. Conflicts between the five specs, and how each was decided

Every one was decided **from the source**, not by averaging.

### C1 — `d_base_lr`: the frozen peak or the live rate?

Spec 2 (TOK/OPT slice, Q5) recommends declaring `d_base_lr` as a wire. Spec 3 (SIG/FAB) says the
opposite: *"the levers file's `d_base_lr` would be the frozen PEAK, which is not what the ratio
clamp needs"*, and makes it a call argument.

**Read the source.** `self_organize.py:7251-7252`:

```
_lo = LR * LR_MIN_FRAC
_oa = _lo + (LR - _lo) * (1.0 - _x).clamp_min(0.0) * _amp
```

`LR` there is the module-global **peak**. Three lines later the code clamps *"ratio to what the
optimizer is ABOUT to apply"*. So there are **three** numbers, not two, and each spec saw one half.

**Decision: both.** `FAB.d_base_lr` and `FAB.d_lr_min_frac` are build-time wires (the envelope's two
endpoints, which are levers); `own_lr_scale(fab, pop, *, applied_lr)` takes the **live** rate as an
argument for the `lr_maxr` ratio clamp, from `OPT.maybe_step`'s `StepOutcome.lr`. Neither spec's
signature survives unchanged, and the resulting one is what the code actually does.

### C2 — the cap-lift period: a wire, an event, or both?

Three specs independently recommend retiring `FAB.d_cap_lift_period` and `TOK.d_cap_lift_period`
from `COUPLINGS`, on the ground that the valve is CAP's and hands over a value, not a period.
Spec 5 goes further and shows the trap: `capacity/levers.py:88-108` records two legal repairs for
the pin-clock unit fault, and **applying both at once fires the valve 16× too EARLY** — repair (b)
is precisely what those two rows do.

**Decision: adopt repair (a), keep both rows, and do not let the valve read them.**
`derive.pin_tick` accumulates `units.Windows`, the threshold stays `CAP.pin_windows` (Windows), and
**no conversion happens anywhere in the valve**. `Windows(...) >= Flushes(...)` raises, so applying
both repairs is refused by the type system rather than by discipline.

The two rows survive as **reporting wires**: `tok.vocab_state` and `fab.grow_check` read them and
print the cadence beside their lift/decline counters, because round6 measured **0 vocabulary lifts**
on `gc_real` and it was a clock-unit fault, not the plateau condition — *"0 lifts" alone cannot
distinguish "never full" from "never plateaued", and those have completely different fixes.*
Retiring a declared ledger row is the owner's call, not the contract phase's: see **Q-CLOCK-1**.

### C3 — is `manage_every` one cadence or two?

Spec 3 (FAB, Q8) says two: `manage()` on a Windows gate above the batch early-out, `contribution()`
and `maybe_deepen()` on the Flushes gate below it, from one lever. Spec 5 (WORLD) says WORLD's
growth hook is **also** on that lever and is evaluated **above** the early-out, so it is Windows and
must not receive `FAB.d_manage_period`, which the ledger types as Flushes.

Both are right and they are the same finding from two sides: `:6716`, `:6764` and `:6768` test
`step % MANAGE_EVERY == 0` above the early-out where `step` is per-window, while `:6819`, `:6836`,
`:6961`, `:6988`, `:7077` and `:7325` write `_nbwd % max(1, MANAGE_EVERY // max(1, BATCH_W))` below
it. **One number compared against two clock kinds in one file.**

**Decision.** `FAB.manage_every` drives **both**, and both firing counts are printed side by side so
a cadence that never coincides is visible as a zero rather than an absence. `WORLD.manage` is called
from the composition root through RUN's Windows-typed `Cadences.due` with `FAB.manage_every` — no
period enters WORLD's Config, so no Flushes wire can reach it. `maybe_deepen` was **never called** in
a real run at BATCH_W=4; that is what the pairing exists to surface.

### C4 — `_nbwd` is two clocks

Spec 2 records it as the accumulation counter; spec 5 found it is **simultaneously** the flush
counter for six management cadences. Both readings are correct today only because there is exactly
one backward per flush.

**Decision.** `RunClock` holds `backwards: Backwards` and `flushes: Flushes` as distinct kinds.
`Clock._same` raises across them, so the two cannot be one variable — and microbatching inside a
flush, the obvious next optimisation, cannot silently change six periods.

### C5 — who owns `token_seen`?

LM's anchor releases a token once it has been **trained** enough; TOK's probation judges it once it
has been **seen** enough (`:1531` says so in as many words). One counter, one increment site
(`:6804`), two consumers in two packages.

**Decision: the training loop owns it and passes it to both.** The increment happens on the training
batch, which is the loop's object, and it is sized from `LM.vocab_slots`, which LM already
publishes. Neither alternative is legal: a per-step-mutated tensor cannot be carried by a wire,
which is a value frozen at build. It is the one shared mutable tensor in this contract and it is
named as such.

### C6 — `RUN` vs `TRAIN`

Spec 5 flagged that `spine/assemble.py` names a package `TRAIN` in its `NOT_WIRES` prose while the
directory is `src/train/`, the class is `RUNLevers` and `PREFIX = "RUN"`.

**Verified**: `build(environ={})` resolves with no `TRAIN` package and the batch-width rows now read
`OPT.batch_windows`. The two stale strings survive only inside rejection prose. Recorded, not
edited — the rejection's *reasoning* is about the value, not the prefix, and rewriting reason text
this phase did not author is how a reason drifts from what it explained.

### C7 — where the retok's side effects go

`retok_every` is TOK's lever, but a retok invalidates `_VALT`/`_BL`, remaps `mem.ctx`, decays
`asm.tokc`, clears `_sigq` and blacks out fabric growth (`:7766-7788`) — it reaches SIG, MEM, DOM
and FAB. `domains/levers.py:615` already states the receiving end: **DOM must not read this cadence;
the retok arrives as a SIGNAL.**

**Decision.** `on_window` returns `Due.retok`; the composition root calls `tokenize`, receives the
new `Segmentation` and a `RetokEvent`, and hands the event to `MEM.maintain(resegment=...)`,
`DOM.on_retokenize(...)`, SIG and FAB. No package other than TOK reads `retok_every`, and no package
other than the root knows who reacts. `LOOP_ORDER` in `spine/compose.py` is where that distribution
is written down.

---

## 2. The packages

Each section: purpose, public surface, what it receives and from whom, state, checkpoint, counters.
The full prose — every measured defect, every line number — lives in the stub docstrings, which are
the normative text. This is the index.

### DATA — `src/data/api.py` (18 levers)

Owns the only bytes the system sees and the only split it is honestly measured on. Goal B needs a
**non-stationary** stream: `phase_sched` is not a parameter of the continual-learning experiment, it
*is* the experiment.

| entry point | receives from outside | returns |
|---|---|---|
| `open_areas(dat, *, seed)` | `seed` ← RUN | `Areas` |
| `data_plan(dat, areas, *, epochs, win_tokens, bytes_per_token)` | RUN, LM, TOK (measured) | `Plan` |
| `draw_stream(dat, areas, plan, *, epoch, seed)` | RUN | `Stream` |
| `stream_state(dat, areas)` / `restore_stream_state(dat, areas, state)` | CKPT | dict / — |

**Wires read:** none. **State:** per-area read cursors (load-bearing across epochs), holdout block
offsets and sizes, `bytes_present`/`bytes_taken`, the counter vector — all checkpointed. The cached
`Stream` at `resample=False` is **not**: it is rebuilt from `(seed, epoch)`.
**Counters:** `data.area_open`, `corpus_cap_trip`, `holdout_block`, `val_cap_trip`, `area_refused`,
`stream_draw`, `segment`, `contig_wrap`, `resample`, `phase_entered`, `phase_resolved`,
`state_written/restored/refused`, and three Gates (`exposure_max`, `exposure_skew`,
`splice_window`).

Five levers (`dir`, `corpus_cap`, `holdout_frac`, `val_cap`, `seg_contig`) are **arm-dead** under
`source="synthetic"`, and `n_processes` under `source="real"`. That is a declared arm reported
through a Gate, not an unread lever.
**Where they are called (§3):** `draw_stream` is the first statement of stage `E` **and** an
`ASSEMBLY_ORDER` row for epoch 0, called UNCONDITIONALLY so `dat.resample` is a state this package
REPORTS rather than a branch the caller takes; `restore_stream_state` is a row immediately after
`open_areas` and before `data_plan`; `stream_state` is a stage-`C` row. Before this edit nothing in
either table drew a stream at all.

### TOK — `src/tok/api.py` (18 levers)

Owns one vocabulary and the policy that grows it. The largest single effect in the project's records
is a lever in this file: two arms with identical vocabularies differing only in whether
re-segmentation fired scored **4.364 against 2.175** held-out b/B.

| entry point | receives | returns |
|---|---|---|
| `build_vocabulary(tok, *, area_heads, seed, soft_cap=None)` | DATA, RUN, CAP | `Vocabulary` |
| `tokenize(tok, vocab, data, labels=None, *, start=0, regularize=False, seed=0)` | DATA | `Segmentation` |
| `on_window(tok, vocab, ids, *, step)` | RUN (`Windows`) | `Due` |
| `mint_burst(tok, vocab, *, step)` | RUN | `list[Mint]` |
| `judge_probation(tok, vocab, *, step, appearances, residual_ratio=None)` | the loop, LM | `Judgement` |
| `lift_vocab_cap(tok, vocab, *, to)` | **CAP, as an event** | `int` |
| `save_vocabulary` / `vocab_state` / `restore_vocab` | CKPT | path / dict / — |

**Wires read:** `d_vocab_ceiling` (hard, on every path **including a resume**), `d_vocab_save_path`,
`d_vocab_read_path`, `d_cap_lift_period` (reporting only).
**State:** `merges` (append-only; the merge list **is** the mint log), the `seq2id` match table
(diverges from `id2bytes` after a retirement — which is why the retok skip test stamps
`(size, len(seq2id))` and not `size`), the pair tally with a monotonic `version`, `prov`, `retired`,
`soft_cap`, `v0`, the cadence `_fired` map. All checkpointed; today a save/load round trip **undoes
every retirement** and loses probation entirely.
**Counters:** `tok.build_pass/build_mint/v0`, `load_reconciled`, `mint` + eight mint-outcome
counters, `retok`/`retok_noop`, `dropout_skip`, `mint_frozen_at`, `probation_*`, `cap_lift`,
`vocab_saved`, `state_*`, and Gates `mint_pmin` and `probation_embed`.

### LM — `src/lm/api.py` (12 levers)

Goal A's engine. **One logits path**: `decode` is the only place logits are produced, for training,
eval and the fabric.

`resolve` · `build_model` · `embed` · `encode` · `decode` · `lm_loss` · `anchor_term` · `on_mint` ·
`residual_ratios` · `state_dict` · `load_state` · `counters`.

**Three layers, three entry points, and the distinction is now structural.** `embed` returns the
token vectors (the lowest layer, no positional term, no dropout); `encode` returns the hidden
**undropped** — the memory-key source and the fabric's input; `decode` performs the **regularised
readout** and is the only place logits are produced. The readout dropout moved off `encode`'s return
into `decode` on 2026-09-02 (Q-LM-9): arithmetically identical on the gru arm, and it is what makes
the memory keys train/eval consistent by construction rather than by whoever last set the module's
mode.

**Wires read:** `d_pos_max` (the refusal, not a clamp), `d_max_token_bytes`.
**Receives:** `device`/`seed` ← RUN; `live_vocab`/`retired_ids`/`mints`/`id2bytes` ← TOK;
`n_layers` ← MEM's `key_depth`; `sig_emb` ← SIG; `token_seen` ← the loop; `extra` ← WORLD's forecast.
**Supplies:** `decode` as a plain callable to FAB; `encode` as `key_fn` to MEM; `embed(model, x)` to
WORLD as `obs_emb`, on a `B` row before `encode/decode` — **added 2026-09-02, Q-LM-12**;
`residual_ratios(model)` to TOK's probation `embed` arm, as an argument on a `B` row gated by
`Due.probation` — **added 2026-09-02, the 122nd in the set** (Q-TOK-11). `MintReport.residual_ratio`
is still produced at mint time and is still the right number *for the mint*; it is not the number the
probation test wanted. **Both LM additions landed the same day from two independent rulings and the
set is 123, not 122 — §7 holds the count.**
**Checkpointed:** the module, the composer's `born` tensor, the counters, the resolved
`LMGeometry`. **Not:** the derived byte-index tensors (rebuilt on load) or the dead-row mask cache.

A resume across a `compose` flip is **refused in both directions** and named — under compose,
`emb`/`head` are not constructed at all. That is a real operational restriction and P7's add-area
entry point must know it before planning an arm table.

### OPT — `src/opt/api.py` (13 levers, one of them a census amendment — there are two in the tree)

Owns every rate and the size of the batch it acts on. **OPT maintains its own optimizer-step
counter**, so `units.Steps` becomes literally true — and the horizon's `Windows→Steps` division is
`spine.derive.opt_steps_from_windows`. *(This paragraph said "no `Windows→Steps` conversion is
written — `spine/derive.py` has no such function, verified" until 2026-09-02. That was true when it
was written and stopped being true when the inline `run_windows // d_effective_batch_windows` in
`build`'s horizon block was named; corrected under Q-OPT-2, which is otherwise RESOLVED-as-already-
adopted.)*

`build` · `lr_at` · `scaled_backward` · `maybe_step` · `counters` · `state_dict` · `load_state`.

**`OptState` names its two optimizers `base` and `encoder`** (Q-OPT-7) — the same words as `build`'s
`param_groups` keys. `maybe_step` writes `lr` into **both** and steps **`base` only**; the encoder is
stepped by `SIG.train_step`, on SIG's cadence, behind SIG's InfoNCE floor gate (Q-OPT-6).

**Wires read:** `d_effective_batch_windows`.
**Receives:** `param_groups` (plain lists the packages returned — OPT never walks a module tree),
`run_windows`, `best_bpb` (a Reading carrying its seed count), `shift_at`, `saved`. **`build` no
longer takes `resume`** — `load_state` is the whole restore path (Q-OPT-4, a frozen signature moved).
**Checkpointed:** both AdamW states, `n_backward`, `opt_step`, `lr_prev`, `restart_amp`,
`cycle_best`, `cycle_index`, the resolved `Horizon`, **`param_group_shape`**, the counters. The old
checkpoint saved `opt_m`/`opt_e` and *nothing else from this package*. `param_group_shape` was
missing from `state_dict`'s enumeration while `load_state` refused on it — an untrippable L50 guard,
repaired 2026-09-02 with Q-OPT-4.
**The invariant `counters()` asserts:** `backward // accum == step`.
**What `counters()` renders and does not compute:** `opt.grad_norm.p50/p99` (base group). The norm is
**read in `maybe_step`**, between the gradient's last use and the `zero_grad`; taken in `counters` it
would be a norm over zeroed gradients — 0.0 for a whole run with every check green (Q-OPT-3).
**Defaults, stated because they change what a run is:** `grad_clip = 0.0` (**OFF** — a new lever and
one of the tree's two census amendments; see Q-OPT-3), `weight_decay = 0.0`, `lr_sched` on, `lr_restarts`
fitting exactly one cycle at the shipped run length.

### SIG — `src/sig/api.py` (18 levers)

Owns the one function from a window to a unit vector. `encode` is the only way to obtain a
signature, on any path; `sig.encode_width_mismatch` must be 0 and a nonzero value is C4 reintroduced.

`build` · `encode` · `cadence_due` · `train_step` · `warm_up` · `counters` · `state_dict` ·
`load_state_dict` · `encoder_parameters` · `encoder_embedding`.

**Wires read:** none. **Receives:** `width_units` (from `derive.signature_width_bytes`, computed
once by the root), `alphabet_size`, the unit stream, `seen_units`, **`OptState.encoder`** — the
encoder AdamW built by OPT, addressable by name as of 2026-09-02 (Q-OPT-7), where the whole
`OptState` crossed before — `windows_since_boundary` ← DOM, `reservoir` ← DOM.
**SIG owns the encoder step.** `OPT.maybe_step` writes `lr` into both optimizers and steps `base`
only; `train_step` is the only place the encoder is stepped in the loop, which is what keeps the
InfoNCE floor gate and `train_every` / `train_every_idle` / `dense_window` load-bearing (Q-OPT-6).
**Checkpointed:** encoder, counters, warmup curve **and its verdict**, the RNG stream, plus a
sidecar carrying `width_units`, `alphabet_size`, `space`, `d`, `mode` — a resume that disagrees
about any of them fails **here**, naming the field.
**`warm_up` returns one of three verdicts, never a binary**; `collapsing` is a run-level failure.
**Where they are called (§3):** `warm_up` is an `ASSEMBLY_ORDER` row after both stream rows and the
optimizer row; `cadence_due` → `train_step` are stage-`A` rows **before** `encode`; `counters` is a
stage-`R` row and is the encoder cadence's **only** did-it-fire surface, because its two-arm gate
cannot go through `Cadences.due`. Until those rows existed the run trained no encoder at all.

### FAB — `src/fabric/api.py` (82 levers, all 82 read since 2026-09-02)

The expert population. D1 rules it stays. **One forward pass, both arms**: `society=True` is the soc
loop at depth 1 with per-expert logits retained.

`build` · `forward` · `observe` · `contribution` · `manage` · `grow_check` · `own_lr_scale` ·
`counters` · `state_dict` · `load_state_dict`.

**Wires read:** `d_operating_population`, `d_manage_period`, `d_cap_lift_period` (reporting),
`d_base_lr`, `d_lr_min_frac`.
**Receives:** `d_model` ← LM, `signature_dim` ← SIG, `h`/`head` ← LM, `signature` ← SIG,
`targets` ← the loop, `domain_id`/`live_domains` ← DOM, `soft_cap` ← CAP, `memory_pressure` ← MEM,
`applied_lr` ← OPT, `baseline_logits_fn` and `per_window_loss` ← the loop.
**Two alarms the report must carry:** `fab.balance_nonzero == 0` while `balance > 0` is **C2** back;
`fab.contrib_distinct_values == 1` is **C3** back.
**`observe` splits `use` from `uage`** — a behaviour change with no measurement behind it, since
`grace=48` was set against a clock that ticked once per window. On P9's list; see **Q-FAB-5**, which
also supplies the number the retune is set from (`fab.mass_per_selection`) and the arithmetic that
makes `fabric.cull_eligible` read **`unreachable`** rather than "armed but 0" at the shipped
defaults.
**`manage` gained a step 0, MERGE** (**Q-FAB-2**), in ΔW space at fixed rank, with **nothing in MEM**
— and it is **on at the shipped default** (`merge_dist = 0.10`). Read that ruling before running
anything whose numbers are meant to compare against a pre-2026-09-02 configuration.
**`grow_check` gained `shift_at=None`** (**Q-FAB-6**, a frozen-signature move), so the growth
controller can be told a loss jump was self-inflicted. `GrowReport` carries the resulting blackout
state, which is also `CAP.observe`'s missing `blackout` boolean.
**`hop_mode` stays and `transition` is refused at startup** (**Q-FAB-1**): the arm is declared and
unported, and `FAB.build` says so rather than silently running `soc`.

### MEM — `src/memory/api.py` (26 levers, 25 read directly, one of them a census amendment)

The editable store, and the one component whose failure mode *is* forgetting, mechanically.

`open_store` · `write` · `read` · `blend` · `maintain` · `apply_domain_plan` · `judge` · `census` ·
`state_dict`.

**⚠ THE 26th LEVER IS A CENSUS AMENDMENT: `MEM.judge_frac`, shipped at `0.0` = the re-score is
OFF**, minted 2026-09-02 under **Q-MEM-8** because the incremental-versus-full-store checked set is
a genuinely open question that performance decides. `.rework/CENSUS.md` and `.rework/census.json`
moved with it; the census's 328 is unchanged. **No other MEM default moved in that edit.**

**Wires read:** `d_capacity`, `d_owner_blocks`, `d_source_slots`. **`owners` is the 25th lever and
this package's own code never reads it** — `spine/assemble.py` reads it to compute two of those
three wires, and MEM reads the results. It is therefore *not* an unread lever, and it is stated here
because "read only through the wire" and "read by nobody" look identical to a grep.
**One write path**; no `if blocks > 1:` branch. **Reads stay global** across owner blocks even when
writes are partitioned: knowledge is owned but not walled off.
**`born` (write tick) is a new field beside `last` (retrieval tick)** — one field carrying both
meanings is what made "LRU" evict the domain that had *stopped being written*.
**Checkpointed additions:** `prob`, `recon`, `nsrc_max`, `gate_theta` — four omissions that each
disarmed a live mechanism at the run boundary.
**Record types are DECLARED, not prose** — `census` returns **`StoreCensus`**, added to the RECORD
TYPES block 2026-09-02 under **Q-MEM-11**, under MEM's own field spellings; the renames into DOM and
FAB stay in `compose.py`'s `produces` column.
**Where they are called (§3):** `census` is a stage-`A` row **before** `DOM.manage`, whose
`memory_counts` and `mem_floor_entries` had no other producer, and again at `R`; `judge` **has no
row today — it is a deferred entry point**, and when it returns it is an event at the END of that
same management pass (**Q-MEM-8**, RESOLVED); `read(promote=True)` is `maintain`'s probe
(**Q-MEM-9**, RESOLVED — and `read` is *deferred as a row*, reached in-package by `maintain`)
while `read(promote=False)` + `blend` are stage-`R` rows, because retrieval has never entered the
training distribution in this project and moving it there is an unmeasured behaviour change
(**Q-MEM-10**, RESOLVED (a): the join is a composition-root closure and **no signature moves on
either side**); `state_dict` is a stage-`C` row.

### DOM — `src/domains/api.py` (28 levers)

The self-assembling partition; `did` is the **unit of forgetting**, and its granularity is what makes
a delete cost 1.6% of memory rather than 30%.

`open_partition` · `observe` · `rekey` · `note_competence` · `manage` · `on_retokenize` · `prior` ·
`census` · `state_dict`.

**Wires read:** `d_expert_slots` (at exactly one site, the at-cap absorb), `d_comp_ema`,
`d_comp_protect`.
**`manage` returns a PLAN; this package never touches memory.** The old tree read three of MEM's
internals inline at `:3688`, including a private method.
**`census` returns `PartitionCensus`**, declared in the RECORD TYPES block 2026-09-02 under
**Q-MEM-11**, under DOM's own field spellings — `live` reaches MEM as `live_sources` and `n_live`
reaches FAB as `live_domains`, and both renames stay in `compose.py`'s `produces` column, because
one record feeding two vocabularies is why "spell it as the consumer does" is not a function.
**`rekey` is an EVENT the spine delivers** — the cadence is MEM's and the arm test is SIG's, and both
were read directly from inside the domain block at `:6688-6689`.
**Checkpointed additions:** the reservoirs (the uncensored sample the measured radius needs),
`tokc`, `comp`/`comp_glob`, the adjacent-distance history. The boundary clock **must not restart** on
resume; `grace` **does**, and the asymmetry is deliberate.
**Where they are called (§3):** `rekey` is a stage-`A` row on `Cadences.due('dom.rekey',
MEM.rekey_every, clock)` **after** `observe` — without it `accept_rule="radius"` silently degenerates
to the constant rule, because `rekey` is the only site that measures a radius; `census` is at `A`
(its `live` list is `apply_domain_plan`'s `live_sources`) and at `R`; `on_retokenize` is delivered by
the RetokEvent at `B`; `prior` is at `R`, which is where the old tree read it while paying for the
histogram every window; `state_dict` is a stage-`C` row.

### RUN — `src/train/api.py` (7 levers)

Owns the shape of the run. **Declares no cadence and no threshold** — a claim a reader can test by
grepping the package for `%` and for a threshold literal.

`process_setup` · `mode` · `streams` · `new_clock` + `RunClock.{begin_epoch,advance,note_backward,
counters}` · `new_cadences` + `Cadences.{due,ledger}` · `bench_summary` · `startup_refusals`.

**`Cadences.due` is elapsed-since-last-fire, not modulo** — this is the load-bearing repair. Over
200,000 simulated windows the mint fired 999 times at BATCH_W=1 and **zero** times at BATCH_W in
{2, 8, 15, 16, 32}; `CKPT_EVERY` sat in that block, so a long run would never have checkpointed.
Because it is phase-independent, a gate may be evaluated per window or per flush and mean the same
thing — which is what lets CKPT's and MEM's Windows cadences need **no** Windows→Flushes conversion.
**`RunClock.advance` is the one site in the tree that increments a counter.**
**Where they are called (§3):** `begin_epoch` is an `ASSEMBLY_ORDER` row for epoch 0 and a stage-`E`
row for every roll — it had **no caller at all** before, together with the epoch level itself;
`RunClock.counters`, `Cadences.ledger` and `bench_summary` are stage-`R` rows, and the ledger is
half of the NEVER-ASKED / ASKED-AND-REFUSED distinction G4 requires.

### CKPT — `src/ckpt/api.py` (5 levers)

A resume is not a convenience, it is the experiment.

`saving_on` · `save_period` · `save` · `install_save_signal` · `resume_source` · `load` ·
`check_geometry` · `new_retention` + `Retention.{consider,state,counters}`.

**`payload` is opaque**; `geometry` is a manifest of `GeometryField(value, rule, env_name, why)`
records the packages produced, and **the rules are the owner package's** because the legal direction
differs per field. **A missing field is a refusal, not a skip** — the comparison is driven off the
manifest's key set, so `if recorded and recorded != live` is not writable here.
**The suffix applies to the whole snapshot**, tokenizer bytes included (M46).
**`best_state` is checkpoint state** (M45), and the blow-up alarm **moves out** to EVAL: gating an
instrument on a checkpoint flag is what this rebuild exists to end.
**Where they are called (§3):** `resume_source` → `load` → `check_geometry` are `ASSEMBLY_ORDER`
rows, the gate placed as **the last row before the first allocation**; `saving_on` is a row of its
own before `new_retention`, whose `inert_reason` needs its answer; `Retention.state` is a stage-`C`
row and `Retention.counters` a stage-`R` one; `save` appears at `B`, `A` (through `BestAction`) and
`R` (`reason="final"`), which is what makes three of its six `Saves` counters reachable at all.
**The payload fan-out is twelve ROWS, not calls inside `save`** — see §3.2 for the three independent
reasons.

### CAP — `src/capacity/api.py` (7 levers)

The earned-capacity valve. **One valve, one owner, one clock.**

`new_valve` · `observe` · `caps` · `startup_refusals` · `state` · `restore` · `counters`.

**Wires read:** `d_expert_slots`, `d_vocab_slots`, `d_mask_dead_rows`, `d_operating_population`.
**FAB receives an integer ceiling per flush; TOK receives an event.** No period crosses either
boundary.
`Decision.block_reason` comes from a closed set — `targets_off | not_pinned | warmup | blackout |
not_stalled | threshold | at_hard_ceiling` — because *"0 lifts" alone cannot distinguish "never
full" from "never plateaued", and those have completely different fixes.*
`Caps.headroom(n)` exists so the negative clamp (C30) **cannot be written** at a call site.
The pin clocks are **now checkpointed**, which is half the M38 fix; the other half is that RUN seeds
the valve's last-called index at the **resumed** step.

### WORLD — `src/world/api.py` (11 levers)

`build` · `loss_terms` · `forecast` · `manage` · `geometry` · `state_dict` · `load_into` ·
`startup_refusals`.

**Wires read:** none. **`enabled=False` returns a NULL WORLD** whose every method is defined and
returns the inert answer — D4's requirement, and the half the old tree failed: the one ablation that
would have priced this package was the one ablation that could not run.
**`forecast` reaches LM through `encode(extra=...)`, a parameter** — the monkey-patch at
`:4158-4169` does not port, and it cost a run where a *timing probe* decided the outcome.
Five undeclared constants (`w_cov=0.04`, `w_bal=0.01`, `min_mass=1e-3`, `tau=1.0`, the plateau pair)
become **named module constants with a written reason** — not levers; the census never voted on them.
**`nmax` caps LIVE predictors and a mint at the cap takes the lowest DEAD SLOT** (**Q-WORLD-8**,
RESOLVED (b), 2026-09-02). The help string's meaning changed; **the default is still 6**. A dead
predictor is **skipped in the forward**, not down-weighted at `1e-6`. `geometry`'s `n` is the
**allocated** count `len(preds)` and never the live count — `n ≤ nmax` becomes an invariant, and
`live` is a `ManageResult` reading and a `state_dict` buffer, not a shape.
**No period enters WORLD's Config** (C3), and **Q-WORLD-6 is RESOLVED (b)**: no wire, a `NOT_WIRES`
entry instead — the ledger stays at **19 of 25, 23 declared couplings**.

### EVAL — `src/eval/api.py` (17 levers)

Everything that measures the run and nothing that changes it.

`curve_period` (P3) · `curve_probe`, `holdout_probe`, `null_excess` (P5) · `generate`, `coherence`,
`verdicts`, `wrongness_probe`, `verification_fit` (P6).

**All 17 levers now have a declared reader.** The five P6 instruments are declared here — with
signatures, not bodies — precisely so that `EVAL_GEN_TEMP` is a knob whose consumer is written down
rather than one of the 57 armed-but-inert records. What P6 owns is the body.
**Two rules every function obeys:** G7 (an instrument may not leave the model in a different mode or
move an RNG stream) and the one-logits-path rule (`logits_fn` is passed in, never constructed).
`null_excess` **refuses `null_draws < 2` at construction**: at 0 it is a `ZeroDivisionError` that
takes the rest of the report with it, and at 1 the sd is exactly 0.0 so the 2σ test becomes a rubber
stamp.
**Where they are called (§3):** `curve_period` and `curve_probe` have `A` rows. The other **seven**
are the whole of `compose.DEFERRED_ENTRY_POINTS`, each with the phase and the argument that has no
producer — not "a later phase", which by itself is no reason at all, since `curve_probe` is P5 and
has a row.

---

## 3. THE ORDER TABLES — what is REACHED, and what is declared deferred

`spine/compose.py` holds two tables of rows, `ASSEMBLY_ORDER` and `LOOP_ORDER`, and three
dictionaries, `DEFERRED_ENTRY_POINTS`, `ROW_ARGUMENTS_ELSEWHERE` and the package map. Together they are the normative answer to a question **K4 does not ask**:
not *"does some stub name this lever"* but *"is the stub that names it ever CALLED"*. K6 checks it,
and it checked it into a failure: applying the composition root's own tables as the test, **56 of
the 117 entry points were named by no row at all** — and they were not 56 scattered omissions, they
were **three whole missing levels and a missing resume path**.

| what was missing | what it cost, from the packages' own docstrings |
|---|---|
| **the epoch level** | Nothing drew a stream, began an epoch, or rolled one. `DATA.draw_stream` — the function that produces the bytes — had no caller; `RUN.epochs` was inert; the LR horizon annealed over a run the loop could not reach; `RunClock.epoch` never left 0, so every save recorded epoch 0. |
| **the checkpoint fan-out and the resume** | Every package's `state_dict`/`load_state` existed and nothing named any of them, so `CKPT.save` would have been handed an empty payload and there was **no resume path in the tables at all** — no `resume_source`, no `load`, no `check_geometry`. M45 (a resume overwrites its parent's best model), M38 (an unearned pin clock), M51/M52/M53/M66/M67 (a live mechanism disarmed at the run boundary) were each reproduced by omission. |
| **the counter collection** | No row collected any `counters()`. For every orphan the evidence was **doubly** unreachable: the owning function was never called *and* its gate never went through `Cadences.due`, so `Cadences.ledger()` had no key for it either. NEVER ASKED and ASKED AND REFUSED became one number, which G4 forbids. |
| **the encoder's training** | `SIG.mode` defaults to `learned`, `compose()` hands SIG's parameters to OPT as an `encoder` param group, and nothing called `SIG.train_step`, `cadence_due` or `warm_up` — so the run routed every window through a randomly initialised encoder while an AdamW stepped it on zero gradients. |

### 3.0 Every row says what it PRODUCES, and K10 reads the column

A row is now **`(stage, PREFIX, entry point, what it receives, what it produces)`**. A row that
yields nothing a later row consumes — a refusal, a save, a counter read — keeps **four** elements,
and that is a statement rather than a default.

**Why the column exists.** The four-column shape claimed a standard it could not check. The header
said a row is *"what it receives"*, and the deferral written for `EVAL.holdout_probe` stated the
rule outright — *"the root has no join that produces that pair; writing a row now would name a call
whose arguments nothing supplies"* — and then `EVAL.curve_probe`, whose signature is
**byte-identical** to `holdout_probe`'s (`ev: Config, *, units_by_domain, logits_fn, rng`), carried
a row whose entire prose was `Cadences.due('curve', EVAL.curve_period(ev), clock)`: neither argument
named, no producer anywhere. The same gap earned a deferral in one place and a row in the other, and
the header cited the rowed one as proof the standard was about arguments rather than phase.

Two mechanical heuristics were tried against it and both failed. *"The row must restate every
required argument"* gave **30** findings, almost all of them rows declining to repeat `h`, `step`,
`now`, `x` — which turns the tables into a second copy of the signatures, the one thing this design
exists to prevent. *"The name must appear somewhere else in compose.py"* gave **25**, flagging
`LM.lm_loss`'s `y` and `FAB.forward`'s `h`, both produced by the row immediately above. Neither can
separate PRODUCED BY AN EARLIER ROW from MENTIONED IN PASSING, because the tables did not record
what a row produces.

**The column spells the CONSUMER's name.** `DATA.open_areas` yields `Areas.bodies` and
`TOK.build_vocabulary` takes it as `area_heads`, so the column says `area_heads` and names the field
beside it — the rename is the root's, which is the root's whole job. Where one value crosses under
several spellings the column lists every one, because a check matching on the producer's field would
report live joins as missing:

| one value | the spellings it is consumed under |
|---|---|
| `RunClock.step` | `step` (TOK ×3, `Retention.consider`, `CKPT.save`), `step_windows` (SIG, FAB ×3), `now` (MEM ×2, DOM ×2) |
| `Snapshot.payload` | `state` (DATA, TOK, CAP), `saved` (LM, OPT), `sd` (SIG, FAB, WORLD), `restored` (MEM, DOM, CAP, CKPT), `resume` (OPT), `snapshot` (CKPT) |
| `LM.lm_loss`'s two returns | `per_window_loss` (FAB.observe), `flush_loss` (FAB.manage/grow_check), `baseline_loss` (FAB.contribution), `bits` (DOM.note_competence), and one summand of the objective |
| `Assignment.did` | `did` (DOM ×2), `domain_id` (FAB ×3), `sources` (MEM.write) |
| `Process.device` | `device`, at six constructors |
| `streams[...]` | `rng` (MEM, DOM, WORLD, EVAL), `generator` (SIG, FAB) |

**What the column may not do** is name a value nothing produces in order to make a row pass. Where an
argument has no producer there are three legal moves: put it in the producing row's column; produce
it with a **named join** in `compose.py` and say so (or list the row in `ROW_ARGUMENTS_ELSEWHERE`);
or move the entry point to `DEFERRED_ENTRY_POINTS` with the missing producer as the reason. Seven
entry points took the third route (§3.6) and each names what would close it.

**The column reads FORWARDS only.** K10 folds `ASSEMBLY_ORDER` then `LOOP_ORDER` in source order and
asks whether an *earlier* row produced each argument, so a value crossing **backwards** cannot live
in it at all. The loop has three such edges and each is written into the consuming row as a
previous-iteration value, with a carrier named on `System`: `novelty` (the previous flush's mean
surprise, `:7499`), `windows_since_boundary` (the boundary `DOM.observe` reported on an earlier
window), and `Due` (asked per window at `A`, acted on per flush at `B`). A fourth, `best_bpb`, has no
producer at all now that the curve probe is deferred.

### 3.0.1 `ROW_ARGUMENTS_ELSEWHERE` — the rule, and the two clearest cases

`{"PFX.entry": "which join in compose.py produces this row's arguments"}`. K10 reads it and skips
those rows; it also reads it **backwards**, so an entry whose row requires nothing is reported stale.
Every *other* helper-supplied argument is named in the consuming row's own note, where a reader meets
it — an exemption table is a place a row stops being read.

**This heading said "two entries, and why only two" while the table held 24, and that is not a style
note — it is the recorded contributing cause of a critical defect filed against nothing.** The
normative answer to Q-CKPT-2's first half (`CKPT.save`'s `geometry` **is** `_geometry_manifest(sysm)`)
lives in that table, and the commit that filed ISSUES P1-C12 as *"every resume raises"* never read it,
because a declaration that says "two, and readers stop here" is a declaration readers stop at. The
`compose.py` header was corrected on 2026-09-02; this heading was the last copy. **The rule the
sentence was reaching for stands and is the thing to keep:** an entry is written here only when
putting the name into the row would be **worse** than not. The two original cases are still the
clearest statements of when that is true:

| entry | why the note would be worse |
|---|---|
| `CKPT.check_geometry` | its argument is spelled with the same word as the **other side** of the comparison (`Snapshot.geometry`, the RECORDED manifest). A row or a column carrying the bare token would satisfy the check against the wrong object. The producer is `_geometry_manifest(sysm)`, the LIVE manifest. |
| `LM.encode` | `x` is the flush batch and **no entry point returns one** — `RunClock.advance` appends to the accumulator and hands back a `Tick`. The producer is this file's own cut, `_flush_bounds`, and stating it once is better than a row that reads as if a package supplied it. |

### 3.0.2 The loop-side joins in `compose.py`

`compose()` does not call these; the loop does. They are in the root for the reason everything else
there is: each spans two packages, O10 forbids a package owning it, and the alternative is the same
arithmetic written inline at a call site — which is how the signature width came out 614 bytes on the
training path and 1 byte on the eval path with every check green.

| join | what it produces, under the consumer's spelling |
|---|---|
| `_window_bounds` / `_flush_bounds` | the cut of `Segmentation.ids` behind `x`, `y`, `contexts`, `tokens`, `targets`, `positions` — contiguous, non-overlapping, `LM.ctx` wide, `OPT.batch_windows` per flush. Returns **bounds, not tensors**: no file in `src/` imports torch at P3 and this file runs no loop. |
| `_signature_cursor` | `seen_units` in the loop — the CURSOR, where `_signature_units` is the whole epoch-0 stream and is `warm_up`'s alone. A unit crossing (Windows → tokens or **true bytes** off `byte_pos`), which is why it has a name. |
| `_sample_window` | `windows` for `SIG.encode` and **the same object** as `sample_window` for `DOM.observe`, which `domains/api.py:96` requires. |
| `_key_fn` / `_head` / `_sig_encode_fn` | `key_fn` (MEM ×2), `head` (FAB), `encode` (`DOM.rekey` **and**, since 2026-09-02, `EVAL.coherence` — Q-EVAL-10; the *same* callable under the *same* name, because two encoders would be two signature spaces) — entry points partially applied. The callable class of argument has no other producer. |
| `_n_params` / `_bytes_per_window` | `RUN.bench_summary`'s two measured arguments. `_n_params` sums **both** param groups; summing only the base list undercounts by the whole encoder. |
| `_geometry_manifest` / `_run_windows` / `_windows_in_epoch` / `_signature_width` / `_alphabet_size` / `_base_parameters` / `_sidecar` / `_signature_stream` / `_signature_units` | the assembly-side joins, unchanged except where §3.8 records a repair. |

What is deliberately **not** there, because writing it would be inventing a producer rather than
naming one: a `logits_fn` (it must be *the path the run trained*, `eval/api.py:27-30`, which runs
through `FAB.forward` and so needs the flush's own `novelty`, `live_domains` and `training`); an
`improving` EMA pair (FAB already keeps one, and a second would be two mechanisms deciding the same
question); an `owners` rule beyond the old tree's; a `plateau` boolean (WORLD holds that state).

### 3.1 The stages

`ASSEMBLY_ORDER` gained four stage values — `resume`, `restore`, `stream`/`segment`, `persist` —
and `LOOP_ORDER` gained three stage letters. **There is still no third table**, for two reasons and
the second is the load-bearing one: every level below is driven by the **same** `RunClock`, and
`tests/test_contract.py` reads the tables **by name** in `_named_by_orders` and `_rows_with_prose`
(`ASSEMBLY_ORDER`, `LOOP_ORDER`) — a third
table would be invisible to the one check that exists because these rows were missing, and *a level
with a table of its own that no check can see is still an orphan.*

| stage | when | what is in it |
|---|---|---|
| `E` | before the first window of an epoch, and again whenever `RunClock.advance` returns `Tick.rolled` | `DATA.draw_stream` → `TOK.tokenize` → `RunClock.begin_epoch`. The root also stamps `clock.opt_steps` here as the `shift_at` `OPT.maybe_step` consumes — a resample is a **self-inflicted** shift, and the old tree carried that fact in a closure variable (`:6518-6521`). **At the shipped default these rows never run — see below.** |
| `A` | per WINDOW, above the accumulator | `Retention.consider`, `MEM.census` (before `DOM.manage`, whose `memory_counts`/`mem_floor_entries` had **no producer**), `DOM.manage`, `DOM.census` (supplying `live_sources` and `live_domains`), `FAB.manage`, `SIG.cadence_due` → `SIG.train_step` (before `encode`), `SIG.encode`, `DOM.observe`, `DOM.rekey` (after `observe`), `TOK.on_window`, `RunClock.advance`. `MEM.judge` and `WORLD.manage` **were here and are now deferred** (§3.6). |
| `B` | per FLUSH | the flush body, plus `TOK.judge_probation`, event-driven on the `Due.probation` `TOK.on_window` already asked at `A`. `CAP.observe` and `FAB.contribution` **were here and are now deferred**. |
| `C` | the CHECKPOINT FAN-OUT — an **event**, entered from `B` (periodic/SIGUSR1), `A` (a `BestAction`) and `R` (final) | the twelve `state_dict`/`state`/`vocab_state`/`stream_state`/`Retention.state`/`WORLD.geometry` calls that build the payload and the recorded manifest, then `TOK.save_vocabulary`, then `CKPT.save`. |
| `R` | once, after `Tick.finished` | `DOM.prior`, both censuses, every `counters()`, `Cadences.ledger()`, `RUN.bench_summary`, and the `reason="final"` save. `MEM.read` and `MEM.blend` **were here and are now deferred**. |

**`Tick.rolled` and `Tick.finished`: the precedence, and the E stage on a one-epoch run.**
`advance()` sets `rolled` when the stream is exhausted and the epoch increments, and `finished` when
`epoch >= run.epochs` — so both are True on the same advance whenever the last epoch ends, and
**`finished` wins**: the loop leaves for `R` and does not re-enter `E`. `RUN.epochs` **defaults to 1**
(`train/levers.py:238`), so at the shipped default the only roll a run ever takes is that one, and
**the `E` rows in `LOOP_ORDER` never execute**. Epoch 0's draw, segmentation and `begin_epoch` come
from `ASSEMBLY_ORDER` instead (§3.4). *"Entered once before the first window"* and *"entered on
`Tick.rolled`"* are two different claims and the tables must not blur them: at `epochs=1` the first
is true and the second never happens, so `DATA.resample`, the epoch-roll resegmentation and every
E-stage counter must read **never reached** rather than **ran and did nothing** — the distinction
G4 exists for, arriving through a default rather than through a guard.

### 3.2 Why the checkpoint fan-out is ROWS and not calls inside `CKPT.save`

Three independent reasons, any one of which is sufficient:

1. **The signature.** `save(ckpt, *, payload, geometry, step, epoch, reason, suffix="")` receives
   **no package object and no foreign Config** — no `model`, no `pop`, no `store`, no `vocab`. To
   call `LM.state_dict(lm, model, geom)` it would need two things it is not given. The parameter is
   literally named `payload` and typed as already-assembled.
2. **The timing.** `load(ckpt)` runs **before** the objects it would restore into exist — the
   geometry gate's whole purpose is to refuse before `LM.build_model`. The load fan-out is not
   inconvenient inside CKPT, it is *temporally impossible*.
3. **O10.** `from lm import api` inside `src/ckpt/` is a test failure. `src/spine/` is exempt;
   `src/ckpt/` is not.

### 3.3 The resume path, in order

`resume_source` → `load` (both before the first refusal, because six constructors already take
`restored=`) → `DATA.restore_stream_state` (after `open_areas`, before `data_plan`) →
`TOK.build_vocabulary` → `TOK.restore_vocab` → **`CKPT.check_geometry`** → everything else, with
each remaining restore immediately after its own package's constructor.

**Where the gate sits is the load-bearing part.** `check_geometry` is the last row before
`LM.build_model`, which is the **first allocation** in the whole assembly. The old gate at
`:4413-4468` fired only after the tokenizer had resolved and the corpus had been pulled, so a
`FAB_NMAX` change arrived as five tensor shapes naming no knob, on a warm GPU.

**`WORLD.load_into` is strictly before `OPT.build`.** `WORLD.manage` mints parameters mid-run
through `add_param_group`, so a checkpoint taken after growth has more groups than a freshly built
optimizer; replaying the population first is what lets OPT be built with the **same** group
structure. Placed the other way, `OPT.load_state`'s `param_group_shape` refusal (L50) fires on every
resume of a run that ever grew — and the honest failure is only marginally better than the old
silent one, which attached one tensor's Adam moments to another.

### 3.4 Epoch 0 appears twice, on purpose

`DATA.draw_stream`, `TOK.tokenize` and `RunClock.begin_epoch` are in **both** tables. Epoch 0's
material must exist before the loop, because `OPT.build` needs `run_windows` measured from a
segmentation that exists (`opt/api.py:78`) and `SIG.warm_up` takes the stream; every later epoch's
is drawn at stage `E`. The old tree has the identical duplication — `:4104` and `:6513` both call
`_resample()`.

**One latent defect fell out of writing those rows.** `_run_windows()` in `compose.py` read
`plan.run_windows`, and `run_windows` **is not a field of `Plan`** (`data/api.py:22` declares
`Plan` as `protocol, schedule, phase_bounds, per_area_draw, exposure, gates`) — a latent `AttributeError`
sitting under a docstring that described the correct computation and could not perform it, because
nothing drew a stream. It now measures `len(Segmentation.ids) // LM.ctx` through the named join
`_windows_in_epoch`, which is the same arithmetic `RunClock.begin_epoch` is handed. That the two
then **diverge** across a minting run is Q-OPT-5.

### 3.5 No cadence was invented

Every periodic row names a period a package **declares**, evaluated through
`Cadences.due(key, period, clock)`:

| key | period | owner |
|---|---|---|
| `curve` | `EVAL.curve_period(ev)` ← `EVAL.curve_every` | EVAL — **declared and never asked** while `EVAL.curve_probe` is deferred (§3.6). The period stays in the mapping on purpose: the ledger then carries a key with `checks == 0`, which says DECLARED AND NEVER ASKED, a different statement from armed-and-inert, and G4 needs both. |
| `dom.manage` | `DOM.manage_period(dom)` ← `DOM.manage_every` | DOM |
| `fab.manage` | `FAB.manage_period(fab)` ← `FAB.manage_every` | FAB |
| `dom.rekey` | **`MEM.rekey_period(mem)`** ← `MEM.rekey_every` | MEM — delivered by the spine, with the `SIG.mode == "learned"` arm also evaluated here, because the old line made *two foreign reads in one line* (`:6688-6689`) |
| `ckpt` | `CKPT.save_period(ck)` ← `CKPT.every` | CKPT |
| MEM's probe/rekey | `MEM.probe_every`, `MEM.rekey_every`, compared inside `maintain` against a Windows `now` | MEM — **NOT ledger gates**, see below |

**Five keys go through the ledger; three comparisons do not, and the document and the code must
agree on the count.** The table above has six rows and `Cadences.ledger()` has five keys, because the
last row is **two comparisons inside `MEM.maintain`** and a third, `SIG.cadence_due`, is a row of its
own. None of the three is a ledger gate, and a gate that is not in the ledger has a **"0 fires"
nobody can read** — so each names its own surface instead:

| comparison | why it cannot go through `Cadences.due` | the did-it-fire surface it uses instead |
|---|---|---|
| `SIG.cadence_due` | it selects between `train_every` and `train_every_idle` on `dense_window`, and `due` takes **one** period | `SIG.counters()` at stage `R` |
| `MEM.maintain`'s probe | `probe_every` is compared against the Windows `now` **inside** the call, and `maintain` takes no `due` flag — giving it one is a signature change | `store.n_probe_fired` / `n_probe_rows` / `n_probe_hits`, read by `MEM.census` at `R` |
| `MEM.maintain`'s rekey | same, and `mem.rekey_every` drives **two different mechanisms**: this internal amortized re-encode AND the spine's `dom.rekey` gate, which delivers an event to `DOM.rekey`. **One lever, two mechanisms, two gates, one ledger key** — and the key belongs to DOM's event, not to this one | `store.n_rekey_slices` / `n_rekey_passes` / `n_rekey_entries` |

`MEM.rekey_period`'s own docstring says this in as many words ("MEM.maintain compares this same lever
against a Windows `now` internally; that is the second gate on one lever"). The rows now say it too,
so a reader counting gates from the code and a reader counting them from this table get the same
answer: **five ledger keys, three unledgered comparisons, each with a named counter.**

**One gate, one ask.** `Cadences.due` *records* the fire and returns True, so asking a second time
under the same key **consumes** the event — that is how a shared `_due` key made minting never fire
at all in the old tree. The management block therefore asks `dom.manage` **once** and runs three rows
inside that one answer: `MEM.census` → `DOM.manage` → `DOM.census`. (`MEM.judge` was the fourth and
is deferred — **Q-MEM-8 rules that it returns to the END of this same answer, never a second `due()`
under this key**; `WORLD.manage` rode `fab.manage`'s single answer **without its row saying so**, and its
deferral records that when it returns it must either be written inside that answer, in the shape this
block uses, or take a key of its own.)

Everything else that fires is **event-driven and says so**: `Retention.consider` (a curve value
arrived — which today it never can), `SIG.train_step` (`cadence_due` said yes),
`TOK.judge_probation` (`Due.probation`), `DOM.on_retokenize` (the RetokEvent), and the whole `C`
stage (a save site). **`SIG.cadence_due` is the one periodic gate that cannot go through
`Cadences.due`** — it selects between `train_every` and `train_every_idle` on `dense_window`, and
`due` takes one period — so it has **no ledger key**, and `SIG.counters` at stage `R` is the only
did-it-fire surface the encoder's cadence has. That is stated in its row rather than left for a
reader to discover from a missing ledger line.

### 3.6 `DEFERRED_ENTRY_POINTS` — fifteen, and no longer only EVAL

`{"PFX.entry": "the phase that will call it, and why it cannot be called now"}`. K6 reads it **both
ways**: an entry no row names is accepted, and an entry a row **now** names is reported as *stale*
and must be deleted. That is what stops it becoming the place orphans go to be forgotten.

**It was seven, all EVAL, and that was the finding.** The seven were deferred for a stated reason —
an argument with no producer — while seven rows elsewhere in the tables named calls with exactly the
same gap. The `produces` column made every one of them decidable, and the seven added below are the
rows where nothing among the entry points (§7 holds the count) supplies a required argument and no
join in `compose.py` honestly can. **None is deferred for being late**, and none because a body is missing:
the whole tree is stubs.

| entry | phase | why there is no row |
|---|---|---|
| `EVAL.curve_probe` | P5 | **New.** Byte-identical signature to `holdout_probe`, same gap, and now the same verdict. Nothing produces `units_by_domain` (Areas carries names/bodies/holdout/holdout_bytes/cursors, `DOM.census` returns sizes and radii, `Segmentation` carries ids/byte_pos/labels/bytes_per_token — there is no per-domain window supplier), and nothing produces `logits_fn`. |
| `EVAL.holdout_probe` | P5 | Needs `units_by_domain` drawn in **byte** coordinates from `Areas.holdout` together with a `logits_fn`, and the root has no join producing that pair. |
| `EVAL.null_excess` | P5 | **Reason corrected.** It said `real` and `permute` come from "the verdict machinery, which is P6's" — but `EVAL.verdicts` takes `domain_sizes`, `silhouettes`, `affiliation`, `coherence_reading` and is this function's **consumer**, not its producer. `real` is the measured statistic under test and `permute` the label-permuting redraw of it, so the candidates are the silhouette and affiliation statistics — which have **no producer in the tree**, the very gap `verdicts` is deferred for — and nothing returns a permutation callable. **Neither exists.** |
| `EVAL.generate` | P6 | `prompts_by_domain` has **no producer** among the entry points (§7 holds the count); `logits_fn` is the same missing join. |
| `EVAL.coherence` | P6 | **Reason corrected, and the parameter is gone.** It said "nothing in the tree returns a `Sample`" — `EVAL.generate` does. Two arguments have no producer and both are named: `logits_fn`, and `units_by_domain`, the same per-domain supplier `curve_probe` and `holdout_probe` wait on. `encode` is **not** a gap — `_sig_encode_fn` already forms it for `DOM.rekey`. The `sample` parameter was resolved away on 2026-09-02: **Q-EVAL-10**. |
| `EVAL.verdicts` | P6 | Three of four arguments — `silhouettes`, `affiliation`, `coherence_reading` — have no producer; the fourth, `domain_sizes`, comes from `DOM.census`, which stage `R` already collects. |
| `EVAL.wrongness_probe` | P6 | Takes a **copy** of the store so the instrument cannot edit what it measures; MEM's surface produces no copy, and adding one is a signature change. Its `scorer` is the same missing logits callable as `MEM.judge`'s **and takes the same arity, `scorer(ctx, src) -> logits`** (Q-MEM-8/Q-MEM-10, 2026-09-02). |
| `EVAL.verification_fit` | P6 | Same missing copy; its inner loop is genuine `units.Steps` and must never be compared against `curve_every`. |
| `MEM.read` | P5 | **New.** Nothing produces `queries`. The deleted `R` row named none of them, and the probe contexts it would key on are the same held-out material `holdout_probe`'s `units_by_domain` needs — one missing join, and deferring only one of the two was the inconsistency. **Deferred as a ROW, reached in-package:** Q-MEM-9 (RESOLVED (a)) makes `MEM.maintain`'s job 1 *this call*, with `queries` maintain encoded itself. K6 is satisfied by the absence of a row, not the absence of a call, so this deferral is current and not stale. |
| `MEM.blend` | P5 | **New.** `retrieval` comes from `MEM.read`; `model_probs` are **probabilities** while every scoring hook takes a `logits_fn` (Q-MEM-10, RESOLVED (a) 2026-09-02: the join is a composition-root closure, `_logits_fn(sysm, *, use_memory)`, and **no signature moves on either side** — but the `logits_fn` still has no producer, so this deferral stands) — which the deleted row's own prose conceded while being written anyway. `model_probs` is also the first positional after the Config, which K10 drops as "the package's own live object" — it is not (MEM's is `store`), so the check is structurally blind here and the deferral is the only record. |
| `MEM.judge` | P4/P5 | **New.** `scorer(ctx, src) -> logits` is needed by the **default** arm (`MEM.verify` defaults to `selfcon`) and must be *the same forward path training used* (M47). That callable does not exist, and scoring a **stored** ctx needs a signature — the domain id is `Store.src`, so only the *declared shape* was missing, and it is now two arguments (Q-MEM-8). **Q-MEM-8 is RESOLVED and names the row to write when the scorer lands:** at the END of the `dom.manage` block, inside that block's single `Cadences.due` answer. Because `scorer` carries a default, **no check can see it**: a row calling `judge(mem, store)` passes everything and yields `n_checked = 0` forever, which `memory/api.py:350-352` itself names as the inert state. |
| `FAB.contribution` | P4 | **New.** `candidates` is the eligible past-grace set, which lives in `Population`'s books — no entry point exports it and O10 forbids the root reaching into `pop`. `baseline_logits_fn` is the same missing callable as EVAL's, and it is load-bearing rather than convenient: the whole C3/H11 repair is that the baseline must come from **the same callable** that produced `baseline_loss`. |
| `CAP.observe` | P4 | **New.** `improving` = `(slow - fast)/|slow|` off the growth controller's EMAs, which live **inside FAB** and are on no returned record; `observations` is the valve-evaluation count tied to a hardcoded 0.998 EMA rate the caller cannot see. The root must **not** maintain a second EMA pair over the same loss to manufacture them — two mechanisms deciding independently whether the run has stalled is the recorded defect where the valve fired hardest exactly when the run was degrading worst. `blackout`'s home is now half-built: **Q-FAB-6** gave `FAB.grow_check` the `shift_at` stamp and put the resulting blackout state on `GrowReport`, so CAP neither reads FAB's `cooldown` at the call site nor has to mint a blackout-window lever it has no census row for; what is still missing is the root join and the two EMAs. |
| `WORLD.manage` | P4 | **New.** `plateau` contradicts the package's own `state_dict`, which says the plateau state `(_wl_ema, _wl_lastgrow)` **moves inside this package** and travels in the checkpoint — if the state is inside, the boolean is computed inside, and both sentences cannot hold. `add_param_group` needs OPT to name one of its two AdamW instances (**Q-OPT-7**). `latent` is real but arrives **backwards** (`loss_terms` is a `B` row, this pass was `A`). |

**A later phase is not by itself a reason to defer.** Each reason above is about an **argument with
no producer**, which is the only kind that survives the backwards check.

**What the seven new deferrals cost, said plainly**, because a deferral that hides its cost is the
shape it replaces: the run has no capacity valve (nothing lifts a cap, so `CAP.caps` returns the
starting ceilings and every block reason reads *unreachable*), no WORLD growth, no learning-curve
probe — and therefore **no best-model save** (`Retention.counters().inert_reason` must report "no
curve value has ever arrived") and **no restart damping** (`OPT.maybe_step`'s `best_bpb` has no
producer, so `opt.restart.damped` is unreachable, not zero) — no per-expert contribution and so no
informed spare rule, and no memory retrieval or wrongness sweep (so `evict="lru"` and `evict="usage"`
stay write-order FIFO and probation can never promote). **All of that was already inert**: the rows
named calls whose arguments nothing supplies. The deferral does not remove a mechanism, it stops the
tables claiming one, and it names the producer each is waiting on.

### 3.7 What could NOT be placed, and is therefore reported rather than rowed

* **The self-inflicted-shift notification to the fabric — PLACED 2026-09-02, and this entry is kept
  as the record of why it could not be before.** At an epoch roll, at a retok and at an LR restart
  the old tree calls `fabgrow.note_shift(step)` (`:6515`, `:7787`, `:7120`) to open a growth
  blackout. No FAB entry point accepted it: `manage`, `observe` and `grow_check` took `step_windows`
  and losses, not a shift event, so the valve half had a route (`CAP.observe`'s `blackout`) and the
  fabric half did not. **Q-FAB-6 is RESOLVED**: `FAB.grow_check` gained `shift_at=None`, typed
  `units.Windows` — a **frozen-signature move**, made now because 94 of the 131 entry points are stubs
  and the same change after P4 writes the WATCH→BURST→RECOVER machine is a body rewrite. It went on
  `grow_check` and **not** on `manage` as the question proposed, because in the old tree the blackout
  gates **growth**: `note_shift` sets `blackout` at `:2948` and two of its three consumers are
  `:3004` and `:3012`, both inside `PlateauGrowth.step`, which is `grow_check` here. (The third is
  `:7397`, the loop's own capacity valve, which is `CAP.observe`'s `blackout` — see Q-FAB-6.)
  `manage` is cull-and-spare and has no cooldown to suppress.
* **A resegment for MEM at an epoch roll.** `MEM.maintain(resegment=...)` is documented for a
  *retokenization*. An epoch redraw is a new stream, not a new segmentation, and the old tree does
  not resegment the store there. Inventing the call would have been the easiest row in this edit and
  the least defensible.
* **`SIG.train_step`'s `reservoir`.** `sig/api.py:113-114` says the pairs are "drawn from ONE domain's
  reservoir by DOM", and **no DOM entry point returns reservoir windows** — `census` returns radii,
  counts and `comp_glob`. At `prototype_frac = 0.0` (the default) nothing is lost; above it,
  `sig.prototype_pairs` reads 0 and the declared Gate must print *unreachable*, not *armed*. The row
  is written with `reservoir` optional, as the signature has it. **Q-SIG-1 is RESOLVED 2026-09-02**:
  this state is the ruling — (c), which is what the signature already specified — and the live defect
  was elsewhere, in two `sig/levers.py` comments naming `d_prototype_reservoir` as a wire the port
  owes. A reservoir is runtime state and can never be a wire; both comments are corrected.
* **`residual_ratio` for the `embed` probation arm — CLOSED 2026-09-02, see Q-TOK-11.** It was
  sourced from LM's `MintReport`, i.e. from **mint time**, when a new token's residual is zero by
  construction, so `keep iff earned AND residual >= probation_residual` retired every candidate.
  `LM.residual_ratios(lm, model)` now exposes the judgement-time read the old tree takes at
  `:7601-7605`, on a `B` row carrying `judge_probation`'s own `Due.probation` gate. The declared
  Gate stays alongside it for `lm.compose = False`, where there is no composer to read.
* **`FAB.own_lr_scale`'s return.** It yields per-expert learning-rate multipliers "or None when
  off", and `OPT.maybe_step(opt, st, *, best_bpb=None, shift_at=None)` **has no parameter for them**
  — no signature in the tree does. Its row therefore produces nothing, which is a legal four-element
  row, but it means `fab.lr_scaled_experts` counts an effect this contract never applies: the mirror
  image of an argument with no producer, and the row says so rather than leaving the reader to
  discover it from an unread return.
* **`Stream.splice_starts` and `Stream.area_changes`.** `data/api.py:153-156` argues hard that BOTH
  must leave the package "so no consumer has to guess which one it wanted" — against ISSUES P1-H10,
  where boundary precision/recall was scored on every splice start and on a one-area run all ~96
  "true switches" were artefacts. **No signature in the tree names either.** `DOM.observe` *produces*
  boundaries rather than consuming ground truth, and every boundary-scoring instrument is deferred.
  Not a K10 finding — nothing requires them — but the mirror of one, and the `E`/`stream` rows record
  that they are inert until P5/P6 rather than leaving the fields silent.
* **`RetokEvent`.** `tok/api.py:35` declares it in RECORD TYPES as "the signal the composition root
  hands to SIG, MEM, DOM and FAB", and **no entry point's docstring says it returns one** —
  `TOK.tokenize`'s says `Segmentation`. Of the four named destinations only one exists:
  `MEM.maintain(resegment=...)`. `DOM.on_retokenize(dom, part)` takes **no event parameter at all**
  (`domains/api.py:230`) — the `B` row wrote the call as `on_retokenize(event=RetokEvent)`, an
  argument the signature does not have, and no check saw it because the entry point has no required
  arguments; the row is corrected. SIG and FAB have **no retokenize entry point** in their frozen
  surfaces. A declared record with no declared producer and two destinations that do not exist.

### 3.8 What writing the column found in the root itself

Six defects in `spine/compose.py` that the column exposed and that are repaired here. None of them
is a signature change; all are unreachable today because `RUN.process_setup` raises several rows
earlier, which is the shape this file's own header calls *"a defect hidden behind an earlier stub,
this project's oldest"*.

1. **`new_cadences` was called with no `periods`.** `new_cadences(run: Config, *, periods)` is
   keyword-only with no default, the ASSEMBLY row describes the five-key mapping in detail, and the
   call site passed `run` alone — a `TypeError` on every `compose()` the moment the first stub gets
   a body. The signature was fixed on 2026-08-30 and the call site was not. Now built and passed.
2. **`cadence_audit` was a row nobody called.** `grep` found it only inside its own row prose: the
   one statement that makes ISSUES P1-C11 visible — ten cadence defaults longer than a 937-window run
   — never ran, while K6 credited the row and passed. It now runs, and its lines join
   `System.warnings`; an **empty** list is a real result and must be printed as one.
3. **`_run_windows` returned a bare `int`** into two functions that refuse one:
   `derive.cadences_that_cannot_fire` and `derive.opt_steps_from_windows` both raise `UnitError` on
   a non-`Windows` (ISSUES P1-H51: all 35 Clock-unit levers resolve to bare ints and the typing is real
   only where `derive` puts it back). It now returns `units.Windows`.
4. **`_run_windows`' row said `run_windows=Plan's measured length`.** `Plan` has no such field
   (`data/api.py:22`) — the same wrong fact the helper's own docstring had already caught once, in
   the body, without the fix reaching the row. The row now names the measurement.
5. **`_base_parameters` skipped a missing `parameters()` in silence.** `Population` declares none,
   so if P4 does not add one the fabric contributes **zero** parameters to the optimizer with every
   check green. The absence is now recorded on `System.warnings`. The `OPT.build` row also said
   `'base': LM+FAB+WORLD+MEM params` while the body walks three objects — **MEM has no module and no
   parameters at all** — so the row now matches the body.
6. **`_sidecar` returned `None` on every real resume and said nothing.** See §3.9.

### 3.9 The geometry gate: what the SAVE side writes — **CORRECTED 2026-09-02**

`CKPT.check_geometry(ckpt, snapshot, geometry)` compares a **live** manifest, built by
`_geometry_manifest(sysm)` from `LM.resolve`'s `LMGeometry` and the frozen Configs, against whatever
the snapshot recorded. **Every field in it is a pure function of the frozen Configs**, which is why
it can exist before the first allocation — the whole point of a gate that must refuse in seconds
rather than after a warm GPU.

**THE FIELD COUNT IS NOT WRITTEN HERE, AND THAT IS DELIBERATE.** It was written in four places and
three of them went stale inside one week — 15, 16, 20 — with the sentence added to *un-stale* the
count already stale by four when it landed. The manifest is data; run `_geometry_manifest` if you
need the list. What is worth stating is the **shape**: one FLAT map with PREFIXED keys
(`lm.width`, `sig.d`, `fab.rank`, `world.nmax`), not a map nested by package.

**What this section said until 2026-09-02, and why it was wrong.** It said the recorded side is
`WORLD.geometry` alone — five fields — so ten of fifteen are in the live manifest and absent from
the recording, which `ckpt/api.py` specifies as a **REFUSAL**, and therefore *every resume raises
`GeometryRefusal` the day P4 lands*. **ISSUES P1-C12 was filed on that and is withdrawn as filed.**
`ROW_ARGUMENTS_ELSEWHERE["CKPT.save"]` — which K10 reads in both directions, so it is the
declaration that runs — says `CKPT.save`'s `geometry` **is** `_geometry_manifest(sysm)`. The save
side and the child call the same function over the same frozen Configs, so the recorded key set is
byte-identical to the live one and the missing-field set is **empty by construction**. See
**Q-CKPT-2**. Two further counts were wrong with it: `WORLD.geometry` returns **six** fields, not
five, and "ten" was arithmetic over both errors.

**The direction rule, which is what kept being confused.** In the LIVE manifest and absent from the
RECORDING is a **REFUSAL** — *"A MISSING FIELD IS A REFUSAL, NOT A SKIP … the comparison is driven
off the manifest's KEY SET rather than off truthiness."* **UNCHECKED** is the other direction:
recorded and absent from the manifest, which is where WORLD's grown `n` sits.

**The one quantity that genuinely needs a live object is `world.n`.** `WORLD.geometry(world, w)` is
the only `geometry()` in the tree and is correctly placed on the **save** side, where a built world
exists (Q-CKPT-1). Five of its six fields duplicate the manifest's `world.*`; the sixth, `n` — the
**allocated** predictor count, never the live one (Q-WORLD-8) — is the overlay it contributes,
recorded-only, reported UNCHECKED by the child's gate and re-refused in both directions by
`WORLD.load_into` (M43).

**Two `sidecar` refusals are still disarmed, and that is Q-CKPT-2's residue — HIGH, not blocking.**
`SIG.load_state_dict` and `FAB.load_state_dict` take a `sidecar` that `_sidecar(sysm, restored, PFX)`
reads as `Snapshot.geometry[PFX]` — a **nested** key. The recorded map is flat and prefixed, so the
lookup finds nothing and both receive `None` on every real resume. `_sidecar` records the disarmed
state on `System.warnings` rather than returning `None` in silence, and both restore rows say the
refusal is disarmed until P4. What changed is what is still *owed*: `lm.arch`, `lm.compose`,
`sig.mode` and `fab.emb_hid` joined the manifest on 2026-08-30 and **`fab.cap` on 2026-09-02**, so
`FAB`'s entire declared comparison set is in the manifest and **`FAB.state_dict` never has to emit
the sidecar it never claimed to emit**. SIG's `width_units` is the single field that cannot be
there — `derive.signature_width_bytes` reads `Vocabulary.bytes_per_token`, which is **measured**, so
it fails the wire predicate and travels in SIG's own blob. **The open question is therefore whether
the two `sidecar` parameters survive at all**, or whether a prefix *slice* of the recorded flat
manifest replaces them. That moves two frozen signatures, it is cheap while both are stubs, and it
is the owner's.

### 3.10 Three TOK events are produced at `A` and consumed at `B`

`TOK.on_window` is the ONE place TOK's four cadences are asked, once per **window**, and it returns
`Due(mint, retok, probation, frozen)`. `TOK.mint_burst`, the retok and `TOK.judge_probation` act on
that Due at `B`, once per **flush**. Between them sits the batch accumulator, and **nothing in the
frozen surfaces carries an event across it**: `RunClock.advance` appends to the accumulator and
returns a `Tick`.

So the carrier is named: `System.due`. What crosses is `batch_windows` Dues reaching one flush, and
the choice of what the flush acts on is a real decision with a measured failure behind it — taking
the **last** silently drops up to `batch_windows - 1` fires; **OR**-ing them makes one flush act on a
cadence that fired mid-batch. Both are the class of loss that made minting fire 999 times at
`batch_w=1` and **zero** times at every `batch_w` in {2, 8, 15, 16, 32}. The rows state the carrier so
the choice cannot be made by accident at a call site; **Q-TOK-12** asks the owner which.

Two more values cross a boundary the column cannot express, and both are on `System` for the same
reason: `novelty` (the previous flush's mean surprise, `:7499` — `FAB.forward`'s `novelty` and the
input to `MEM.write`'s `surprise`) and `token_seen` (the per-token appearance counter, which is
`LM.anchor_term`'s `token_seen` and `TOK.judge_probation`'s `appearances` — **one tensor, two
spellings**, owned by the loop and returned by no entry point; C5).

### 3.11 The six findings three reviewers left open, and what each turned out to be — **2026-09-03**

Every one was verified against the tree before it was acted on, because a finding that has already
been fixed is a real outcome and acting on it writes a second wrong sentence. **All six were live.**

1. **`residual_ratio` could never be a wire, and four statements still said to declare one.** All
   four were in `src/tok/levers.py`. Fixed; the fifth copy is the owner's census reason and is
   recorded, not edited — see **Q-TOK-11**.
2. **The manifest's field count lived in three places, all wrong**, and one of them was inside
   `ROW_ARGUMENTS_ELSEWHERE["CKPT.check_geometry"]` — *a declaration a check reads*. Both counts are
   now deleted rather than corrected, which is what **Q-CKPT-1** ruled; the third statement was the
   C-block's "the recorded side carries `WORLD.geometry`'s five fields and the gate refuses the other
   ten", which is arithmetic over the **withdrawn C12 claim** and is rewritten around the
   declaration that runs. **K13 found the first two mechanically and now guards them.**
3. **`_periods`' sixth key was visible to no check.** `K9` read the order tables and `'progress'`
   has no row, so `RUN.PROGRESS_WINDOWS` could have become a bare `100` — the H51 shape, which makes
   `Cadences.due` raise on its first evaluation — with all six suites green. **K9 was widened to read
   the mapping itself**, and three statements that offered the blind spot as an explanation now
   record it as the defect it was. This is the branch the finding demanded: *a check sees it.*
4. **"`blackout`'s only two consumers are `:3004` and `:3012`" was wrong in four places.**
   `self_organize.py:7397` is a third, at the **loop call site**, gating the capacity valve. The
   **Q-FAB-6** ruling is unmoved — both consumers that decide *growth* are in `grow_check` — but the
   corrected sentence is what makes the rebuild's split legible: FAB applies the cooldown, the state
   rides `GrowReport`, and the root joins it into `CAP.observe`'s `blackout`.
5. **Two statements in this document named two different signatures for `EVAL.coherence`.** One
   called the change a `sample` → `seed_units` **rename** and "the only reopening EVAL's frozen
   surface needs"; **Q-EVAL-10** replaced one parameter with **two** (`units_by_domain`, `encode`)
   and refuses `seed_units` by name. The pointer now points at the ruling instead of restating it.
6. **Two line citations written in the previous commit landed on the wrong lines.**
   `memory/api.py:259-261`, cited twice for the `n_checked = 0` inert state, is
   `apply_domain_plan`'s docstring; the state is named at **`:350-352`**. `tok/api.py:108-110`,
   cited for BPE-dropout's train/inference protocol "word for word", is `tokenize`'s opening; the
   sentence is at **`:130-131`**. Both fixed, along with `memory/api.py:265` in
   `tests/test_contract.py` (the same defect, one commit older), `memory/api.py:238-240` in a live
   `compose.py` row note (the scorer's forward-path rule is at `:289`), and `opt/levers.py:559`,
   which the previous pass had *just corrected* from `:499` and which the same day's Q-OPT-3/Q-OPT-4
   edits moved to `:623`. **That last one is the argument, in one line, for citing a defect ID or a
   quoted sentence instead of a number.**

---

## 4. UNCONSUMED LEVERS

The union of the five `levers_unconsumed` lists was **15**. Thirteen of them were EVAL's, and all
thirteen were given a declared reader by writing the P6 instrument signatures into
`src/eval/api.py`. **The last two were FAB's, and as of 2026-09-02 this table is EMPTY: every one of
the 262 declared levers is named `LEVERS READ:` by a stub.** Neither of the two was dropped, and
neither was given a fake reader; each was ruled, and the ruling is what produced the reader.

| lever | env name | why it has no reader | disposition |
|---|---|---|---|

*(no rows — see the two rulings below, and keep the table: a lever added without a reader lands
here with a reason, or K4 fails.)*

**`FAB.hop_mode` — RESOLVED Q-FAB-1, the lever STAYS and `FAB.build` now reads it.** The transition
hop arm (the `R` matrix, per-expert `SRC` marks, the `ctrl` summary) is **not ported**; `soc` is.
The lever is not dropped, because the owner's standing rule is that a mechanism kept for future use
is kept *with a switch*, and dropping it would make the eventual port a census amendment. What was
unacceptable was the silence: with no reader, `FAB_HOP_MODE=transition` passes `choices=` validation
and then runs `soc` — the exact M24 shape (`s.loop_soc = (_env("CHAIN_ROUTE","soc") == "soc")` at
`:1843` made every typo the *other* walk). `FAB.build` now **refuses `transition` at startup**,
naming the arm and this question. See **Q-FAB-1**.

**`FAB.merge_dist` — RESOLVED Q-FAB-2, the merge is implemented and `FAB.manage` now reads it.**
**⚠ THIS TURNS A MECHANISM ON AT THE SHIPPED DEFAULT.** `FAB.merge_dist` resolves to **0.10**, not
0, so a merge pass now runs on every management pass of every default run where one previously did
not exist at all. Its *reachable* set is another matter and is stated in the same breath: the
absorbed expert must be past `grace`, and at the shipped defaults the past-grace set is provably
empty (Q-FAB-5), so `fab.merged` reports **`unreachable` with the arithmetic**, not "armed but 0".
See **Q-FAB-2**.

**Not unconsumed, but stated so a grep does not misread it:** `MEM.owners` is read by
`spine/assemble.py` to compute `d_owner_blocks` and `d_capacity`, and by nothing in `src/memory/`.
It changes both wires and the whole partition, so it is fully consumed — through the wire.

---

## 5. FOR THE OWNER

Unioned from the five specs, deduplicated, with everything resolvable from the source already
resolved above. What is left needs a ruling.

**HOW TO READ A SECTION HERE, AND WHY THE HEADING IS NORMATIVE (convention fixed 2026-09-03).** Every
section keeps three layers, in this order and never fewer: the **heading**, which carries the verdict;
the **original framing**, kept verbatim as the record of what was asked and therefore still describing
the *unfixed* problem in the present tense; and the **ruling**, which states what is true now. A
resolved question is not deleted — it is the record of a decision, and the next reader needs the
question to understand the answer.

That makes the heading the index, and **an index that disagrees with its own bodies is this project's
C12 defect** — a CRITICAL was once filed against prose that a declaration in the same file had already
refuted, and withdrawing it cost a round. On 2026-09-02 nineteen sections were ruled and their bodies
rewritten while their **headings were left stating only the problem**, so a reader scanning `grep
'^### Q-'` under the sentence *"what is left needs a ruling"* would count nineteen open questions that
were not open. Nine of them (`Q-DATA-4`, `Q-DATA-6`, `Q-DATA-7`, `Q-DATA-8`, `Q-TOK-3`, `Q-TOK-9`,
`Q-TOK-10`, `Q-TOK-11`, `Q-TOK-12`) are corrected here.

The remaining ten — `Q-CLOCK-1`, `Q-OPT-1`, `Q-OPT-2`, `Q-OPT-3`, `Q-OPT-4`, `Q-OPT-5`, `Q-OPT-6`,
`Q-OPT-7`, `Q-LM-9`, `Q-LM-12` — **were marked on 2026-09-03, and the index is now complete: every
`### Q-` heading in this section carries its verdict, and `grep '^### Q-'` is an accurate count of
what is open.** Nine of the ten are `RESOLVED` and `Q-CLOCK-1` is `MEASURABLE`; **not one of the
nineteen was ever open**, and the sentence four paragraphs up — *"what is left needs a ruling"* — is
now true only of the sections whose headings say so.

`Q-OPT-3` was the sharpest and is worth keeping as the worked example. Its framing paragraph still
reads *"neither package declares a lever and the census has no dropped row for one"* — which is
correct **as the record of what was asked** and false as a statement about the tree, because
`OPT.grad_clip` is declared, `.rework/CENSUS.md` and `.rework/census.json` carry an `amendments`
group for it, and `tests/test_census.py` N1 examines `amend` rows. Under the three-layer convention
the framing paragraph **stays** and the heading is what tells the reader not to act on it. That is
the whole of the convention in one section.

**And the heading itself is now held to it by a check, which is the part the convention could not
supply (2026-09-03).** `Q-OPT-3`'s heading read *"nothing in this system clips gradients"* — a
present-tense absence claim about a lever declared four hundred lines below it, which is the C12
shape in the one place the convention makes normative. It now reads *"nothing in this system
**clipped** gradients when this was asked, and `OPT.grad_clip` now declares one"*, and
`tests/test_contract.py`'s **K13 arm (b)** refuses the old form mechanically: it matches every
`### Q-` heading that negates something, word by word, against the levers and entry points its own
package declares, and reports one that resolves and is *not named in the heading*. A heading that
names the thing and negates a **property** of it — `Q-SIG-1`'s *"`prototype_frac` has no supplier"*
— is admitted, because naming it is the opposite of claiming it is absent. The check reads headings
and nothing else, so the framing paragraphs stay invisible to it **by design**: they are supposed to
describe the unfixed problem.

**THE DEFAULT `Q-OPT-3` SETS, STATED HERE AND NOT ONLY IN ITS OWN SECTION, because the owner's
standing instruction is "tell me the defaults, so I know what is off and on":** `OPT_GRAD_CLIP =
0.0`, which is **OFF**. The mechanism is declared, reachable from the environment, and does nothing
until somebody sets it. Every number this project has recorded was taken with no clipping, and off
is that configuration exactly.

### Q-CLOCK-1 — retire `FAB.d_cap_lift_period` and `TOK.d_cap_lift_period`? — **MEASURABLE 2026-09-02: (a) STANDS, BOTH ROWS KEPT, AND THE CONDITION THAT FLIPS IT TO (b) IS WRITTEN DOWN. NO WIRE MOVED — LEDGER STAYS 19 OF 25**
Three specs recommend it. This contract **keeps both rows as reporting wires** and adopts pin-clock
repair (a) so the valve reads neither. **Options:** (a) keep as reporting wires (what is written);
(b) delete both rows, freeing 2 of the 25-wire budget and removing the trap where a later reader
re-connects them; (c) retarget to `CAP`, which would be wrong — under repair (a) a converted period
is the 16×-early fault.

**MEASURABLE 2026-09-02 — (a) STANDS FOR NOW, and the condition that flips it to (b) is written
down. NOT resolved, and deliberately not.**

*What was verified.* Both rows exist (`spine/assemble.py`), both compute
`derive.flush_period_windows(Windows(CAP.pin_windows), OPT.batch_windows) → Flushes`, and both are
read exactly once, for reporting (`fabric/api.py`, `tok/api.py`). They are **CAP's only outbound
edges**: the package graph is `CAP → (FAB, TOK)` and nothing else sources CAP. The ledger is **19
wires of 25, 23 couplings**. The pin-clock repair is done and independently confirmed:
`derive.pin_tick` raises `UnitError` on a `Flushes` or `Steps` `held` and on a non-`Windows`
`dstep`, and `tests/test_derive.py` runs 575 oracle cases with 0 mismatches.

*The case for (b), which is real.* `CAP.counters` already declares `pin_windows` in `LEVERS READ`,
already holds the four high-water marks, and already declares **the block-reason histogram**, whose
stated purpose is verbatim what these two wires are for — *"round11 pinned 42,425 against a
threshold of 20,000, lifted nothing, and left no evidence of which of the two remaining conditions
refused."* That is a strictly better answer: it is in the package that owns the valve, in the unit
the valve compares, beside the pinned high-water mark, and it separates *never full* from *never
plateaued* by **naming the blocking condition** rather than leaving it to be inferred from a
cadence. Two report paths formatting one quantity two ways is what `spine/wire.py`'s own docstring
says it exists to prevent.

*Why it is not applied.* **`CAP.counters` is a stub.** Deleting the rows now trades a report line
that exists for a promise about a body nobody has written, and the owner's standing rule is that a
repair which costs capability is the wrong repair. The evaluating agent's own blocking note says the
same thing in one sentence — *"if the CAP slice narrows or defers that histogram, my recommendation
flips to 'keep'"* — and **no slice owns CAP**, so the condition its recommendation rests on has not
been decided by anyone. Keeping is also the reversible arm: (a) → (b) is a pure delete, while
(b) → (a) means re-adding two ledger rows and their reasons.

*What was applied instead, so the two paths cannot drift while both exist.* `fabric/api.py` and
`tok/api.py` now say, in their `WIRES READ` lines, that **CAP's histogram is the authority** and
that these lines print the period and point at it — they may not grow a verdict of their own about
which condition blocked. That removes the drift risk (b) was mostly buying, at zero cost in
capability and zero cost in wires.

**THE MEASUREMENT THAT SETTLES IT — no GPU needed, it is a P4 deliverable.** When `CAP.counters` has
a body, run any configuration that pins the population, and read its report: if the block-reason
histogram plus the pinned high-water mark distinguishes *never full* from *never plateaued* **on its
own**, delete both `Coupling` rows, both `WIRES READ` lines, both `_ =` reads, the paragraph in
`TOK.lift_vocab_cap`, and the two wire names inside `derive.pin_tick`'s `UnitError` message — one
atomic edit across ~8 files, which K5 will force to be atomic by failing loudly if a read outlives
its declaration. Wire budget then goes 19 → 17 of 25. If the histogram ships narrowed or deferred,
these rows are the only surviving answer and (a) is final.

*One reason the contract gave that should not be acted on.* The old recommendation argued from
*"a row nothing but the report reads is a row a future author will 'fix' by connecting it"*. That
trap is already foreclosed **by construction**: `Windows >= Flushes` raises, and `pin_tick` refuses
a `Flushes` by name. Deleting on that ground would be deleting for a danger that cannot happen.

*One repair made 2026-09-03 while re-verifying the above.* `spine/derive.py`'s `pin_tick` docstring
said the two rows are read *"at `fabric/api.py:305` and `tok/api.py:313`"*; the live reads are at
`fabric/api.py:492` and `tok/api.py:438`, and the cited lines had drifted onto unrelated prose. The
same paragraph now also says what this section says — that the two rows are **MEASURABLE, not
permanent** — so a reader who arrives at `pin_tick` first is not left believing the reporting wires
are settled. `pin_tick`'s own point, *do not convert the threshold*, does not rest on them and
survives their deletion; that is stated there too, so the atomic edit this section specifies does not
have to re-derive which half of the message is load-bearing.

### Q-DERIVE-1 — re-type `derive.pin_tick` from `Steps` to `Windows`? — **RESOLVED 2026-08-30, repair (a) adopted**

It was re-typed. `derive.pin_tick` now accumulates `Windows` and raises on `Steps`, `Flushes` or
`Backwards`.

**Why this could not stay open.** It was not a question in one place and an answer in another by
accident — it was the *same* claim, frozen twice with opposite content. `src/capacity/api.py:16` said
"derive.pin_tick **is** re-typed to accumulate units.Windows … NO CONVERSION HAPPENS ANYWHERE" while
`derive.pin_tick` refused a `Windows`, and this document said the repair was done in §CAP and
proposed here. A P4 implementer following the CAP contract writes
`pin_tick(held_windows, pinned, elapsed_windows)`, gets `UnitError` on the first flush, and is left
with `int(held) >= cap.pin_windows` as the only form that runs — which `capacity/levers.py:107` names
as *"the original defect again"*. A reviewer found it by reading both surfaces; nothing executed,
because `compose()` stops at `RUN.process_setup` long before the valve.

**Which side was wrong is not a preference.** `spine/units.py` defines `Steps` as *"Optimizer steps.
What the LR schedule's horizon is denominated in, **and nothing else**"* and `Windows` as *"Stream
windows. What `step` counts."* The clock accumulates `step - _pin_prev`, a window delta. The `Steps`
typing was the original conflation moved out of the arithmetic and into the type added to prevent it
— and `pin_tick`'s docstring called the 43,645 *"REAL STEPS"*, using "steps" for the loop counter one
level below the defect it repaired.

**What moved.** `spine/derive.py` (the kind, the two refusal messages, the docstring),
`tests/test_derive.py` (the typed smoke assertions — the 32 oracle cases record raw ints in and out,
so they pin the arithmetic and never saw the kind), `src/capacity/levers.py:88-108` (from "stated and
not resolved" to settled), and the two `d_cap_lift_period` reason columns in `spine/assemble.py`.

**Repair (b) survives as reporting only.** `FAB.d_cap_lift_period` and `TOK.d_cap_lift_period` are
still wired as a `Flushes` period, read by `fabric/api.py` and `tok/api.py` beside the lift counters,
because *"0 lifts"* cannot otherwise distinguish "never full" from "never plateaued". Nothing compares
them against the clock. Both repairs can no longer be live in the valve at once **by construction**:
`Windows >= Flushes` raises. Applying both would turn 20,000 into 1,250 at `BATCH_W=16` and fire the
valve sixteen times too *early* — harder to see than the original, because a valve that fires looks
like a valve that works.

### Q-DATA-4 — `data/continual/` and `data/ood/` are unreachable from any DATA lever — **RESOLVED 2026-09-02: THE SLASH RULE ADOPTED, PLUS THE TWO STARTUP REFUSALS IT DID NOT NAME. NO LEVER, NO WIRE, NO DEFAULT MOVES**
`datastream.py:72` hardcodes `{data_dir}/train/{d}/*`. The repository ships
`data/continual/{01_rust,02_sawyer,03_dracula,04_num2}` (1.5 MB) and `data/ood/` (764 KB) — **the
material the add-an-area benchmark exists for** — and `grep` finds them read only by
`archive/legacy/*`. D2 makes PURE_ADD the default protocol; the areas prepared for it are
unreachable except by moving files on disk, which is a configuration change no Sample can record.
**Recommendation:** allow an `areas` entry to contain a `/` and join it under `dir` verbatim, with
`train/` remaining the implicit prefix when there is no slash (`DATA_AREAS="eng,continual/01_rust"`).
The area **label** is the basename, with a startup refusal on a collision. It adds no lever and no
default moves, but it changes what a declared lever's string means.

**RESOLVED 2026-09-02 — the recommendation, adopted, plus the refusal it did not name.** An entry
containing `/` is joined under `dir` verbatim; an entry without one keeps `train/` as the implicit
prefix, so **every shipped spelling means exactly what it meant and no default moves**. Two startup
refusals are `open_areas`'s own and both are required: an entry that is absolute or contains `..`
(otherwise `areas` is an arbitrary-path read — a corpus lever that can open `/etc`), and two entries
whose **basenames** collide, printed with both source paths. Forced by goal B: `data/continual/`
holds the four arriving areas the add-an-area benchmark exists for, and the alternative — restructure
the disk — makes the corpus selection a filesystem state no `Sample` can record. A `DATA_SPLIT`
lever was refused twice over: it cannot mix `train/eng` with `continual/01_rust` in one run, which
*is* the experiment, and it has no census ancestor, so N2 has no row and `DEPARTURES` — keyed by
`(family, old_name)` — has no key to write. **Landed:** `src/data/api.py` (`open_areas`, three new
counters), `src/data/levers.py` (`dir` and `areas` help text and the ruling). No lever, no wire, no
signature.

**The 39th question, ruled here because nothing else owns it: `DATA.restore_stream_state`'s name
check.** Read as set-equality it refuses **every add-an-area resume**, i.e. goal B's headline
experiment, at startup. The normative reading is now written into the docstring: every area *the
parent recorded* must come back with the same holdout offset, size and rng key or the resume is
refused **naming the area and the field**; a name present now and absent from the record is
**admitted with a printed `data.area_added` line**; a name in the record and absent now is refused
under its own counter, because "an area arrived" and "an area vanished" are two different statements
and only one is an experiment.

**FIVE LINE CITATIONS IN `src/data/` POINTED AT THE WRONG LINES AND ARE FIXED 2026-09-03.** The
2026-09-02 rulings were written against the tree *before* the same commit edited it, so `levers.py`
and `compose.py` moved under their own citations. `open_areas` cited `eval/levers.py:201-202` for the
KEYED-BY-DOMAIN-NAME quote (now `:221-222` — `:201` is the paired-comparison argument) and
`data/levers.py:349-360` for `seg_contig`'s *"the only boundaries left are the text's own"* (now
`:306-307` — `:349-360` is the `phase_sched` block, a different lever entirely); `data_plan` cited
`data/levers.py:339-343` and `:344-350` for the no-literal-string argument and the 10× disagreement
(now `:381-383` and `:386-389`); `restore_stream_state` cited `compose.py:304-309` for the row that
runs it (that is the `geom` row — the `restore` row is `:323` and the call is `:1802`). None changes a
ruling; all five send a P4 author to the wrong paragraph, which is the same failure as prose that
contradicts a declaration, one indirection out.

**AND THE SAME FAILURE AT SCALE: EVERY `ISSUES:<line>` CITATION IN `src/` POINTS AT THE WRONG
DEFECT.** Found while checking one of them. `src/data/api.py` cited `ISSUES:1421` in four places for
the desynchronised-`DN` defect; line 1421 is **L15**, an `LR_DECAY` default in a research note, and it
has held three different defects across three commits. The drift is mechanical and measurable:
`.rework/ISSUES.md` grew from 1983 to 2270 lines and **every defect header moved down by 88 lines**,
every `[so-config/facts]` entry by **90**. The proof is not the arithmetic but the three citations in
`src/` that name a defect ID *beside* the line number — `capacity/levers.py:346` (`M38`, cited 417),
`capacity/levers.py:363` (`M36`, cited 409), `tok/levers.py:367` (`M23`, cited 357). In all three the
`+88` line owns that ID and the raw line owns a different one, with **no counter-example**; six more
were confirmed by matching the citing sentence against the defect body (`M65`, `M77`, `M24`, `L69`,
`M20`, `C19`).

**Repaired in `src/data/` and `src/tok/` only: 17 citations, converted to the defect's ID
(`ISSUES P1-M77`), which does not move.** The `[so-config/facts]` entries have no ID and are now cited by
their opening words. **50 line citations remain in the other twelve packages and are all wrong by the
same 88/90.** They are not silently rebased here: a blind `+88` is the wrong repair — the two offsets
differ, so it would land some citations one entry off — and each replacement has to be confirmed
against the defect's text, which is the slice owner's read to make. Whoever touches a package next
should convert its citations rather than add another line number.

**`src/opt/` AND `src/lm/` CONVERTED 2026-09-03: 15 more citations, and THE "88/90" ABOVE IS TOO
NEAT.** Every one of the fifteen was confirmed by matching the citing sentence against the defect
body, and the offsets measured are **+56, +88 and +90** — three, not two. `ISSUES.md:441` →
`M44` at 529 (+88, and the raw 441 is `M22`, a different defect the citing sentence does not
describe); `ISSUES.md:1580` → `H12` at 1668/1670 (+88 on the header, +90 on the body sentence
actually quoted); `ISSUES.md:2029` → the `[chat-b/carry_forward]` entry at 2119 (+90);
`ISSUES:170` → `H27` at 224 (**+54 on the header, +56 on the sentence**), which no rebase rule
would have found. That is the evidence for the paragraph above's own conclusion, stated harder:
**a blind offset is not merely risky, it is arithmetically impossible to get right**, because the
file grew unevenly and the drift is a different number in each region. Only content matching works.

**AND ONE HAZARD THE ID CONVERSION ITSELF CARRIES, worth knowing before the remaining 35 are done.**
`ISSUES.md` reuses defect IDs across its parts: `H15` is *both* the `_lrv` `NameError` (PART 1,
`:176`) and *"A corpus smaller than STREAM_LEN duplicates itself"* (PART 3, `:1680`). An ID alone is
therefore ambiguous by construction, so every citation converted here names the **part** as well —
`ISSUES.md PART 1, H15` — and the two PART 4 entries, which have no ID at all, are cited by their
tag and subject (`PART 4, the [archive/facts] D_MODEL_B entry`). The seventeen already converted in
`src/data/` and `src/tok/` carry the bare ID and should gain the part when they are next touched.
### Q-DATA-7 — how is D2 (PURE_ADD) actually produced? — **RESOLVED 2026-09-02: (c), THE PROTOCOL IS RECOGNISED NOT GENERATED, AND A `phase_sched` ENTRY MAY BE AN AREA NAME. `DATA_PHASE_SCHED` DEFAULT UNCHANGED (EMPTY = REHEARSED). THE REHEARSED-vs-PURE ARM IS LEFT MEASURABLE**
`PURE_ADD` is not and never was a knob (0 occurrences in `self_organize.py`); it is `longrun.sh`
shorthand expanding to `PHASE_SCHED="1|1|1|1"`, and only because that harness runs exactly two
areas. **Options:** (a) the last entry of `DATA.areas` is the arriving area — general at any n, no
new lever, but it makes area ORDER load-bearing in a way nothing states today; (b) infer it from
`CKPT.resume` — refused, a cross-package read of a value DATA does not own; (c) require the launcher
to write the schedule explicitly and have the resolver only **name** what it was handed.
**Recommendation: (c) now, (a) later.** (c) cannot be wrong and gets the protocol name onto the
Sample immediately, which is the part D2 actually needs.

**RESOLVED 2026-09-02 — (c), and the half of (a) that was worth having, without making order
load-bearing.** Two things landed and the lever default did **not** move.

**On the owner's ruling, because this needed re-reading rather than overriding.** The ruling is
*"Pure add seems to be for testing of adding new domains, lets keep it as default for now."* The
first clause is the reading: pure-add is **for the add-a-domain test**, and "keep it as default"
means keep it the default **protocol of that experiment** — not the default value of
`DATA_PHASE_SCHED` on every run. Those are different objects and only the second was declined.

The second reading is refused by measurement, not by preference: at the shipped
`DATA_AREAS="eng,py,num,c"` a generated pure-add schedule streams **one** area and leaves three
declared corpora **untrained, silently** — the silent-overwrite family, arriving through a default.
An n-dependent default shape is M18 on the protocol besides.

So pure-add is kept, is now writable order-independently as a name schedule (`"rust|rust|rust|rust"`),
is named on every `Sample` through `Plan.protocol`, and remains what the add-an-area harness (P7)
writes. **What the owner should overrule if the first reading is wrong**: flipping `DATA.phase_sched`
itself, which is one default and one line.

1. **`Plan.protocol` is RECOGNISED, not generated**, by four predicates now written verbatim into
   `data_plan`: empty → `generated`; explicit, one phase, every area live → `stationary`; explicit,
   `n_areas > 1`, every phase the same single area → `pure_add`; otherwise `explicit`. No lever, no
   argument, no signature, and **no change to `derive.phase_schedule`**, which is oracle-pinned at 60
   cases and is the spine's to own.
2. **A `phase_sched` entry may be an area NAME as well as an index**, resolved against `Areas.names`
   at the parse site and refused loudly on a name no area carries. This is what makes *"the added
   area alone"* **writable at any area count** — `"rust|rust|rust|rust"` — which `data/levers.py`
   said no literal string could express, and it removes the order-fragility `longrun.sh:930-932` is
   living with in the open (it hand-types `_AI=1` under a comment claiming the index is computed
   from `DOMAINS`, and nothing reads `DOMAINS`; ISSUES P1-L2).

**THE DEFAULT, STATED BECAUSE THE OWNER ASKED TO BE TOLD WHAT IS ON.** `DATA_PHASE_SCHED=""` still
generates the **rehearsed** sliding window. The owner's ruling — *"Pure add seems to be for testing
of adding new domains, lets keep it as default for now"* — is honoured as the protocol of the
add-an-area experiment: pure-add is kept, is now writable in one order-independent string, and is
**named on every run's Sample**. What is deliberately **not** done is flipping the lever default:
at the shipped `DATA_AREAS="eng,py,num,c"` a generated pure-add schedule streams **one** area and
leaves three declared corpora untrained without saying so, and a default whose shape changes between
`n=2` and `n=4` is M18 (a declared parent that is not the actual one) reproduced on the protocol.

**MEASURABLE — the run that retires the rehearsed-vs-pure question.** The two arms disagreed 10× on
the same toy (+0.046 HELD rehearsed vs +0.444 WORSE pure). One pair, fixed seed, fixed
`DATA_AREAS="eng,<new>"`: arm **R** at `PHASE_SCHED="eng|eng|<new>|<new>"`, arm **P** at
`PHASE_SCHED="<new>|<new>|<new>|<new>"`, reading ACROSS THE RUN BOUNDARY on `eng`'s held-out block at
the end of each. Rehearsal keeps `eng` trained, so only arm P measures what the fabric *preserves*;
if R's `eng` retention is not materially better than P's, rehearsal buys nothing and pure-add is the
honest default everywhere.

### Q-DATA-6 — the held-out split becomes a seeded random block — **RESOLVED 2026-09-02: (b) CONFIRMED, PLUS ONE REPAIR THE QUESTION DID NOT CONTAIN — ONE HOLD-OUT RNG STREAM PER AREA, KEYED BY NAME. ⚠ EVERY HISTORICAL HELD-OUT NUMBER BECOMES NON-COMPARABLE**
`holdout_frac` currently takes the **last** fraction of each area, which is a sample only if the
corpus was written in no particular order. Measured: py held out at **5.061 ± 0.560** against 2.922
in-stream while eng (shuffled upstream) was 2.273 against 2.303 — the gap was the ordering, and the
run reported it as a property of Python. This contract writes the seeded-random-block rule into
`open_areas`. **The consequence must be stated loudly: every historical held-out number becomes
non-comparable with the rebuild's**, because the text being scored changes. That is a deliberate
break and the Sample must carry the split rule so the two eras are distinguishable rather than
silently mixed. **Confirmation requested.**

**RESOLVED 2026-09-02 — (b) confirmed, with one repair the question did not contain and two readings
it did not name.**

**The repair, and it is load-bearing.** The block must be drawn from **one child stream per area,
keyed by the area's label** — `rng_for("data.holdout." + key, seed)` — not from a single
`"data.holdout"` stream. A single stream draws the areas in list order, so every area's block
position is a function of **how many areas were drawn before it**: insert or reorder one entry and
every later area's held-out text moves. Three things then break at once — `restore_stream_state`
refuses the resume by its own stated reason, ACROSS THE RUN BOUNDARY compares two different texts,
and `eval/levers.py:221-222` **already declares the opposite property**: *"KEYED BY DOMAIN NAME, not
by index, so adding a domain does not shift the comparison. That property is part of the lever's
meaning and has to survive the port."* DATA produces the text EVAL then windows, so the two must key
the same way or the paired add-an-area comparison is destroyed on the one run type it exists to
measure. `spine/rng.py:107-109` declares dotted child streams as the supported shape and DATA already
derives `data.stream.e0` itself, so **`RNG_SUBSYSTEMS` does not change**. The key is the label
lowercased with every character outside `[a-z0-9_]` replaced by `_`, and a key collision is the same
startup refusal as the label collision in Q-DATA-4 — which is precisely the objection `rng.py` raises
against normalising a name, answered at startup instead of papered over. **Whoever rules Q-EVAL-9
should know this half is now done.**

**Two additions, both counters rather than levers.** `data.holdout_seam` — removing a *middle* block
leaves exactly one manufactured discontinuity per area in a body `seg_contig=True` reads in order,
and `data/levers.py:349-360` claims the only boundaries left are the text's own; one seam per area
against the thousands `seg_from` manufactures is a good trade, but it must be a **printed number**.
And `data.holdout_overlap`, a **Reading**: the fraction of held-out bytes occurring verbatim in the
training body at a fixed n-gram length, per area, once at startup. It costs no lever, no wire and no
default, and it answers the question the split rule *cannot*: Lee et al. (arXiv:2107.06499) measure
that models *"underestimate perplexity on evaluation documents with near duplicates"* and conclude
benchmarks *"should actively remove contaminated training data, rather than just partitioning held
out splits by documents"* — **neither the tail nor the random block is safe on its own.** The
grouped/temporal-split literature cuts the other way and is worth stating: random splits over
non-independent rows inflate metrics. It does not transfer here, because this randomises **where a
contiguous block sits**, not which rows are sampled.

**Two stale sentences corrected in the same edit.** `src/data/levers.py` asserted, in its header and
again on `val_cap` (the corrected text now sits at `:128-140` and `:478-486`), **that** the resolved
held-out size reaches EVAL as a wire *"declared in spine.assemble (`EVAL.d_holdout_bytes`)"*.
It is not declared and **must not be** — §0 refuses it, on the ground that `build()` would have to
`stat` the corpus. A P4 author following those sentences would try to declare a coupling A1/K5 then
bounces with a message that does not explain why. **Both now cite §0's refused-wires table by
section rather than by line** (2026-09-03): they gave `docs/04_CONTRACT.md:74`, and this document
grew 1908 lines on 2026-09-02, so that number now lands twelve lines above the table it names.

**One thing this ruling wrote two ways, repaired 2026-09-03.** `open_areas` gave the draw as
`rng_for("data.holdout." + label, seed)` in the paragraph that states the rule and as the
**normalised key** three paragraphs down, where the normalisation is defined — while
`spine/compose.py:127` and `src/eval/api.py:141` both say the key. Two readings of one splice in one
docstring is what this whole phase exists to remove, so the rule paragraph now says `+ key` and
points at the normalisation. Nothing else moves: the key *is* the label whenever the label is already
lowercase `[a-z0-9_]`, which every shipped area name is.

**The break is confirmed and belongs on P9's list of numbers that moved:** every historical held-out
number is non-comparable with the rebuild's, because the text being scored changed. The Sample carries
the split rule, the seed and each area's `(offset, size)` and rng key, so the two eras sort apart
rather than mixing silently — which is the half of this ruling that makes the break honest.

**The `OPT.counters` precedent this answer cited is itself defective** and the citation is not
carried: `counters(opt, st)` cannot see a gradient, because `maybe_step` step 5 zeroes them. The rule
being borrowed is *"a Reading costs no lever"*, not that instance.

### Q-DATA-8 — steps per epoch, and what a "window" is measured in — **RESOLVED 2026-09-02: (a) CONFIRMED; AND THIS QUESTION'S OWN ACCOUNT OF THE OLD TREE WAS WRONG AND IS CORRECTED BELOW**
`steps = STREAM_LEN // WIN` (`:4317`, `:4719`) divides a **byte** budget by a **token** window.
Under `mode="bytes"` a window really is `LM.ctx` bytes; under `fixed`/`online` it is `LM.ctx`
**tokens**. So "a window is WIN bytes" is true on one arm of one lever and false on the others, and
the overstatement is the compression ratio (~2.5× at a grown vocabulary) — which the LR horizon and
every ETA were computed from. This contract computes `run_windows` from the token stream that
actually exists (`_run_windows` in `compose.py`). **Confirmation requested**, with the report
printing `stream_bytes`, the resulting step count and the measured bytes/token together.

**RESOLVED 2026-09-02 — (a) confirmed; and the question's own summary was wrong in a way that would
have cost a P4 author a day.** The unit half is settled and enforced: `_run_windows` returns
`units.Windows`, and `derive.cadences_that_cannot_fire` and `derive.opt_steps_from_windows` each
`raise UnitError` on a bare int, so the byte-derived form is *unrepresentable*, not merely
discouraged.

**The correction.** This section, `compose._windows_in_epoch` and `train/api.py`'s `begin_epoch` all
said the LR horizon and every ETA were computed from `STREAM_LEN // WIN`. **They were not.** Of the
28 `STREAM_LEN` sites, `STREAM_LEN // WIN` appears in exactly two live places: the pre-run `[probe]`
ETA banner (`:4317`) and one cadence period, `_due("lmcurve", max(1, (STREAM_LEN // WIN) // 8))`
(`:7319`); `:4719` is prose. The runtime horizon and ETA both went through `_project`, whose
`_total_steps = EPOCHS * (len(stream) // WIN)` (`:6236`) and `_per = max(1, len(stream) // WIN)`
(`:6339`) measure the **token** stream (`:5656` divides `byte_stream` by `stream` to get bytes/token).
So the horizon was already token-measured and its real defect is the **shrinkage projection** at
`:6338-6362` — **Q-OPT-5, and OPT's**. Left standing, this text sends an implementer to fix one bug
twice, differently. All three sites now say so.

**The five-number line belongs to the composition root, not to `RUN.bench_summary`.** `bench_summary
(run, clock, *, elapsed_s, bytes_per_window, n_params, timing)` can reach **none** of the five:
`bytes_per_window` is the *product* `ctx × bytes_per_token` and RUN may not read `LM.ctx` to divide
it back out, and `RunClock` carries `step/flushes/backwards/opt_steps/epoch/batch_len` and nothing
else. It also **returns `None` when `bench` is off** and prints *instead of* the eval battery — so
the line would be invisible on every ordinary run, which is the armed-but-inert shape this project
exists to end. The root holds all five (`sysm.segmentation.ids`, `LM.ctx`,
`Segmentation.bytes_per_token`, `_windows_in_epoch`, `_run_windows`), is the only place that sees
them together, and is exempt from the ownership rule that stops RUN assembling them. It prints once,
after the `segment` stage, **on every run**; the row says so.

### Q-TOK-3 — does `dropout` reach the training stream, or only the build tallies? — **RESOLVED 2026-09-02: (b) CONFIRMED, IT REACHES THE TRAINING STREAM. DEFAULT UNCHANGED AT `TOK_DROPOUT = 0.0`, WHERE BOTH ARMS ARE IDENTICAL**
`tokenizer.py:187` applies dropout only to `count=True` segmentations, and the only `count=True`
call in the tree is the build pass (`:1264`). So at `mode="online"` the regularizer runs during the
seed build and **never again**, while the lever's own purpose says it exists "so byte-level material
still reaches the tally". **Options:** (a) keep the semantics and Gate-declare it unreachable after
the build — faithful, and admits the regularizer has never run; (b) apply it to the training-stream
segmentation, which is what BPE-dropout is for. **This contract writes (b)**, with the retok skip
test disabled whenever `dropout > 0` (the emitted stream is then no longer a deterministic function
of the vocabulary, so "retok on an unchanged match table is pure damage" becomes unsound). Every
record in the project was taken at `dropout=0.0`, where (a) and (b) are identical, so nothing already
measured moves. **Confirmation requested** — it is a semantic change.

**RESOLVED 2026-09-02 — (b) confirmed. It is already written and the confirmation is what was
missing.** `regularize=False` is a frozen parameter of `TOK.tokenize`, the root passes
`regularize=True` at all three segmentation sites, and `"tok.dropout"` is a declared RNG subsystem,
so the process-global draw that shifted the whole run's stream is gone. The literature is decisive
and agrees with what the framework already permits: BPE-Dropout (Provilkov et al., ACL 2020) *is*
dropout during training with deterministic BPE at inference, which is `tok/api.py:130-131` word for
word. (a) would require **removing** a frozen parameter — a signature change in the expensive
direction — to buy a lever that is inert after the seed build at `mode="online"`.

**Two consequences P4 must be told, now written into `TOK.tokenize`:** (1) at `dropout > 0` the run
LENGTH becomes a draw — `len(Segmentation.ids)`, hence `_windows_in_epoch`, `_run_windows` and the LR
horizon, are stochastic in the `tok.dropout` stream. `DATA.draw_stream`'s invariant *"two arms
differing in one unrelated knob still read the same text at epoch 2"* is a statement about **bytes**
and does not extend to tokens. (2) `bytes_per_token` is measured over the **counting** segmentation,
which applies dropout — so `derive.signature_width_bytes` (SIG's one width) and `data_plan`'s
`splice_window` threshold both move with a TOK regularizer. Both consume the measured value and so
follow correctly, but a width that changed with no SIG lever set is explained here.

**Default unchanged: `TOK_DROPOUT=0.0`, where (a) and (b) are identical and no recorded number
moves.**

### Q-TOK-9 — `build_passes` had a per-arm default (2 online, 8 offline) — **RESOLVED 2026-09-02: ONE LITERAL, 2, READ ON ALL THREE ARMS. THE 8 SURVIVES AS A DECLARED GATE. DEFAULT UNCHANGED**
`:1225` is `_passes = _i("SEED_PASSES", 2) if TOK_ONLINE else _i("GROW_PASSES", 8)`. A Lever carries
one default. `tok/levers.py:284-289` proposes carrying the 8 "inside this package's build code",
which is a second literal in a second place — the thing L1 exists to end. **Recommendation:** one
literal (2) on both arms, with a startup line saying the offline build historically used 8 and
recommending `TOK_BUILD_PASSES=8` for `mode="fixed"`. A value the operator cannot see in
`docs/04_LEVERS.md` will disagree with the registry within a month.

**RESOLVED 2026-09-02 — (a), one literal, argued from the registry rather than from a document that
does not exist yet.** `tok/levers.py` told P4 to write `8 if mode == "fixed" else tok.build_passes`
while `tok/api.py` told P4 to write `tok.build_passes` — at `:57` and in its `LEVERS READ:`
line, `:57` and `:75` before the ruling and `:57` and `:88` after it — two frozen surfaces, opposite
instructions, and a different `tok.v0` on the arm carrying the project's largest recorded effect
(4.364 vs 2.175 b/B). The deciding fact is mechanical: **a `Lever` carries exactly one default**, and
L1 is one declaration in one place; a second literal in build code cannot be reached by any generator
or audit that reads the registry. (`docs/04_LEVERS.md` is the *planned* consumer three `levers.py`
files already name — it is not yet on disk, and this ruling does not lean on it.) **`tok/levers.py`
did lean on it, and was brought into line 2026-09-03:** its comment read *"docs/04_LEVERS.md **is
generated** from these declarations"* in the present tense about a file `ls docs/` does not show, and
cited `opt/levers.py:499` for a sentence that is at `:623` (`:559` before the same day's Q-OPT-3/Q-OPT-4 edits moved it, and this correction was itself stale within the hour — which is the argument for citing a defect ID or a quoted sentence rather than a line). It now argues from the `Lever`'s one
default — the fact that does not depend on a document — and names the planned consumer as planned.
The same present-tense phrasing survives at `fabric/levers.py:104` and `domains/levers.py:166`, which
are other slices' files and are **not** touched here; whoever generates that document should correct
them in the commit that creates it. The 8 survives as
a **declared Gate with its predicate**, `tok.build_passes_advice`: on `mode="fixed"` it prints
`build_passes=2; the offline build historically used 8 — set TOK_BUILD_PASSES=8 to reproduce it`, and
on the other arms it prints `unreachable (mode != fixed)`. Advice that appears sometimes and says
nothing when it does not is armed-but-inert applied to prose. **Nothing changed the default (2).** A
`mode="fixed"` run at 2 passes is **not** the offline build of record → P9's moved-numbers list.

### Q-OPT-1 — `run_windows` as an argument — **RESOLVED 2026-09-02: THE `NOT_WIRES` ROW WAS ADDED. `d_run_steps` IS NOW REFUSED BY NAME, ON THE TOKENIZATION GROUND, NOT MERELY UNWRITTEN. NO SIGNATURE, NO LEVER, NO WIRE**
Recorded and acted on above (see §0, refused candidates). **The ask:** add a `NOT_WIRES` row for
`d_run_steps` with the *measurement* reason, so the next reader does not have to re-derive that the
rejection is real and is **not** the `RUN.epochs` one. The contract phase did not add it because
`NOT_WIRES` is prose about candidates, and adding a rejection is as much an owner statement as
adding a row.

**RESOLVED 2026-09-02 — the row was added.** `spine/assemble.py`'s `NOT_WIRES` now carries
*"the run length in windows → OPT.d_run_steps / OPT.d_total_steps"* with the tokenization ground
stated and the difference from `RUN.epochs → OPT.d_lr_horizon` stated beside it. **`NOT_WIRES` is
DATA, not prose, and that is what makes this cheap and safe:** `render()` walks the tuple and A4
iterates it, requiring every entry to appear in the printed graph, so the row extends a *checked*
surface rather than adding an unchecked sentence. It touches no signature, no lever, no `Coupling`
and no wire budget — still **19 of 25**. What it repairs is a claim: the ground was written down
twice already (§0's refused-wires table and `compose.py`'s `_run_windows`) and in **no row of the
one table `render()` prints**, so `docs/03_WIRING.md` asserted a completeness it did not have while
omitting the most-proposed rejected candidate in the tree. Option (c) — folding it into the
`RUN.epochs` row — was refused for the reason §0 already gives: the two rejections are different,
and folded, a reader who fixes the EPOCHS conflation would believe the tokenization objection went
with it.

**AND THE HALF OF THIS QUESTION THE ROW DID NOT CLOSE, REPAIRED 2026-09-03: `src/opt/levers.py` was
still telling the next author to WAIT for the wire this row refuses.** Two places, both in the file a
P4 optimizer author reads first. Its conflict `(c)` ended *"the census says the run length arrives as
`d_run_steps` so the sentinel resolves in one visible place. That coupling does not exist yet
either."* And the `lr_wavelength` sentinel comment said *"the run length arrives as the wire
`d_run_steps` … that coupling does not exist yet (see conflict (c)), so until it does, whoever builds
the schedule must resolve the zero at the single point it is read."* **A candidate refused with a
reason and a candidate that "does not exist yet" are opposite instructions**, and adding the
`NOT_WIRES` row without touching them left the tree holding both. Both now say the wire is refused by
name and that the value arrives as `OPT.build`'s `run_windows` argument, resolved once, with
`opt.build.wavelength_from_sentinel` as the counter that says the sentinel fired.

**The same file's other two "conflicts with the spine" had also been settled and still read as open**,
and they are corrected in the same edit because they are the same defect: `(a)` said `spine/assemble.py`
reads `r["TRAIN"].batch_w` / `r["TRAIN"].accum` in four couplings that all print *"DEFERRED …
package(s) ['TRAIN'] not registered"* and are **not made** — the string `r["TRAIN"]` does not occur in
`assemble.py` at all today, the three flush cadences read `r["OPT"].batch_windows`, and
`d_effective_batch_windows` is `OPT.d_effective_batch_windows`. `(b)` said the peak rate had two
spellings and *"neither in `spine.assemble.COUPLINGS`"* — `FAB.d_base_lr ← OPT.lr` and
`FAB.d_lr_min_frac ← OPT.lr_min_frac` are both rows, and `d_lr_peak` is the spelling that lost. The
file's own `THE WIRES` table said *"five of those eight are not in `spine/assemble.COUPLINGS` today"*;
seven table entries are now answered — four are rows (six `Coupling` rows behind them, because the
flush-cadence entry is three), two (`best_bpb`, `shift_at`) are **arguments**, because a runtime
measurement can never be a build-time wire, and one (`d_run_steps`) is refused. Two counts inside that
table were also wrong independently of any drift: it said *"the FOUR flush cadences FAB/TOK/CAP"* —
there are **three**, there have been three in every version of `spine/assemble.py` in this repository
(checked back to the commit that first wrote the table, where they sit at `:338`, `:350`, `:363`), and
**CAP is a source, never a destination**, which is the same fact `Q-CLOCK-1` states as *"CAP's only
outbound edges"*. The paragraph that has been repaired is the one that predicted its own failure:
*"it will read as 'not ported yet' long after it has become 'ported'."* It did, for every reader
between the port and this edit.

**And one more in the same file, on a different lever.** `lr_shift_warm`'s row said *"the resample step
arrives as `d_shift_at` … that coupling is NOT IN THE LEDGER, so today this lever has nothing to fire
on."* It is not in the ledger and **never can be** — the step of the last self-inflicted shift is a
runtime event, refused on the same ground as `d_run_steps` — and the lever is **not** inert: `shift_at`
is a declared keyword on `OPT.maybe_step`'s frozen signature, the composition root stamps it at the
epoch-resample / retok / add-area events, and `FAB.grow_check` takes the same event since `Q-FAB-6`.
The row now says so, and points at `opt.shift.notifications`, which is the counter that distinguishes
*nobody is supplying `shift_at`* from *`lr_shift_warm` fired zero times*.

**THE IDENTICAL DEFECT IN `src/lm/levers.py`, FOUND BY LOOKING FOR IT, AND REPAIRED IN THE SAME EDIT.**
LM's header carries a `TWO CONFLICTS WITH THE SPINE` block of the same shape, and **both were settled
in `spine/assemble.py` and still read as open** — with an extra turn of the screw: `assemble.py`'s own
`TOK.d_vocab_ceiling` row cites *"lm/levers.py:127-141 and tok/levers.py:87"* as the two files that
*"record it as the outstanding repair"*, so the pointer from the file that made the repair led to a
paragraph calling it outstanding. **(a)** said `assemble.py` declares
`Coupling(src="TOK.vmax", dst="LM.d_softmax_width", …)` and that importing the real packages *"today
raises `TOKLevers has no lever 'vmax'`"* — the edge was reversed to `LM.vocab_slots →
TOK.d_vocab_ceiling`, `LM.d_softmax_width` does not exist anywhere in `src/`, and `assemble.build({})`
does not raise. **(b)** said `d_pos_max`'s coupling did not exist and *"until the coupling exists the
guarantee it buys does not"* — `LM.ctx → LM.d_pos_max` is declared, **local**, exactly the shape (b)
argued for, `LM.build_model` reads it and `LM.encode` **raises** rather than clamps. LM's `THE WIRES`
table said *"six of those nine are not in `spine/assemble.COUPLINGS` today"*; all nine are answered —
**three** are rows (`d_pos_max`, `d_max_token_bytes`, `d_vocab_ceiling`), **five** are arguments
(`live_vocab`, `retired_ids`, `device`, `residual_ratio`, `sig_emb`), and **one** (`d_softmax_width`)
no longer exists because its edge was reversed.

**What I did not repair, named precisely so it is a one-line fix and not a rediscovery:**
`src/tok/levers.py:87` carries the mirror of LM's conflict (a) — *"assemble.py:723-725 declares
`Coupling(src="TOK.vmax", dst="LM.d_softmax_width", …`"* — and is stale for the same reason. It is the
data-tok slice's file and that slice had already finished; `assemble.py`'s row names both files
together, so whoever touches TOK next should take it with this one.

### Q-OPT-2 — the LR schedule indexed by optimizer steps — **RESOLVED 2026-09-02: (a) CONFIRMED, NOT CHOSEN — THE TREE HAD ALREADY ADOPTED IT IN THREE UNIT-ENFORCED PLACES. NOTHING IN `src/` CHANGED; ONE STALE SENTENCE AND THE P9 ENTRY DID**
At the shipped defaults (`batch_windows=1`, `accum=1`) the new counter and the old one are
identical, so **no recorded result moves**; at `fetch_big.py`'s own recommended heavy-run command
(`WIN=256 BATCH_W=16 ACCUM=4`) they differ by **64×**, and one of the two readings makes a warmup
written in steps complete 64 times sooner than it says. This contract adopts the honest counter.
**Belongs on P9's list of numbers that moved, with this reason attached.**

**RESOLVED 2026-09-02 — CONFIRM (a). There was no live decision left; it was verified, not chosen,
and one stale sentence was corrected.** The position is already written in three coordinated places:
`maybe_step` step 1 advances `st.opt_step` (`units.Steps`) and is declared *"the ONLY thing that
advances it"*; `lr_at(opt, st, opt_step)` takes that counter and is declared PURE; and
`derive.opt_steps_from_windows` exists, refuses a non-`Windows` at one end and a divisor below 1 at
the other, and is covered by the oracle table (575 cases, 0 mismatches, run). The alternatives are
not close: indexing by windows makes `units.Steps` — the one type in the system that exists for this
quantity — false, and leaves `opt_steps_from_windows` with no caller; indexing by flushes makes
`accum` change the batch without changing the horizon, a 4× mislabelled schedule at `ACCUM=4`.
**The stale sentence:** §OPT said *"no `Windows→Steps` conversion is written — `spine/derive.py` has
no such function, verified"*. That was true when written and stopped being true when the inline
`run_windows // d_effective_batch_windows` inside `build`'s horizon block — the last unnamed
cross-kind conversion in the tree — was given a name. §OPT now says so.
**The P9 entry, in full, because there is still no P9 document:** *the LR schedule is indexed by
optimizer steps, not by windows; at `batch_windows=1, accum=1` (shipped) the two counters coincide
and no recorded number moves; at `WIN=256 BATCH_W=16 ACCUM=4` — `fetch_big.py`'s own recommended
heavy-run command — they differ by 64×, so `lr_warmup=1000` under the old reading completed 64 times
sooner than its lever text said. Attributable to the ISSUES P3-H29 counter repair.* Whether P9's list
becomes a file or a section is the owner's; the text is here so it is not re-derived.
**Literature agrees and does not decide it:** stepping the scheduler per optimizer update rather
than per micro-batch is standard, and stepping it per micro-batch under gradient accumulation is a
filed bug upstream (`huggingface/accelerate#963`). The framework forced the same answer first.

### Q-OPT-3 — nothing in this system clipped gradients when this was asked, and `OPT.grad_clip` now declares one — **INSTRUMENT RESOLVED 2026-09-02 (THE NORM MOVES TO `maybe_step`); THE CLIP IS MEASURABLE BEHIND A NEW LEVER. ⚠ CENSUS AMENDMENT `OPT_GRAD_CLIP`, AND ⚠ THE DEFAULT IS `0.0` = OFF — DECLARED AND NOT FIRING, WHICH THE REPORT MUST SAY OUT LOUD**
Verified by exhaustive grep: no `clip_grad_norm_`, no `clip_grad_value_`, no manual norm clamp
anywhere in `self_organize.py`; every match for "clip" is prose. Neither package declares a lever
and the census has no dropped row for one. This matters because unclipped gradients are a **second,
independent** explanation for the exact curve shape `lr_sched` exists to ablate (bottom ~2.4 at step
6000, rise to 3.8–4.1 by 48,000) and the two are confounded. **What this contract does without a
ruling:** `OPT.counters` reports the observed global gradient norm (`opt.grad_norm.p50/p99`), which
costs one `torch.norm` per step, needs no lever, and answers the question with data before anybody
argues about a default. **Minting `OPT_GRAD_CLIP` is escalated** — the census never voted on it.

**RESOLVED 2026-09-02 for the instrument. MEASURABLE 2026-09-02 for the clip, with both arms
reachable. ⚠ THIS IS A CENSUS AMENDMENT AND A NEW LEVER — SEE BELOW BEFORE READING ANYTHING ELSE.**

**(1) The instrument was declared in a place it cannot work, and that is now fixed.** `OPT.counters`
claimed to compute the gradient norm *"per optimizer step"*. It cannot: `maybe_step` step 5 does the
`zero_grad`, so a norm read inside `counters` is a norm over freshly zeroed gradients — **0.0 for
the entire run, with every check in this repository green.** A P4 author following the docstring
literally would have written a wrong-measurement record into the report and had no way to see it.
The norm is now **taken in `maybe_step`**, between the gradient's last use and the `zero_grad`, and
`counters` **renders** the accumulated quantiles. Scope is the **base group only**: at flush time the
encoder's gradients belong to SIG's cadence (Q-OPT-6), and folding two schedules into one number
makes it uninterpretable. This is prose inside frozen signatures; **no signature moved.**

**(2) `OPT_GRAD_CLIP` is minted, default `0.0` = OFF, and it is a CENSUS AMENDMENT.** There is no
ancestor knob — `grep -c clip self_organize.py` → 2, both prose about the forgetting measure F — so
there is no `(family, old_name)` key a `DEPARTURES` entry could be written under, and N2 could only
be satisfied by amending the census itself. That was done, loudly and in one edit:
`.rework/census.json` gained an `amendments` group, `.rework/CENSUS.md` gained an `amendments`
section, `src/opt/levers.py`'s accounting header says this package holds **one of the tree's two**
amendments — it said *"the tree's only"* until the same commit found `MEM_JUDGE_FRAC` had been minted
the same day by another slice, and this sentence was the last copy of the wrong word (corrected
2026-09-03) — and **`tests/test_census.py` N1 was widened to check `amend` rows** so that deleting the lever fails
a check instead of leaving an orphaned census row. **The 328 is unchanged**: it counts the old
`_SPEC`'s knobs and this was never one of them.

**Why mint it rather than close the question by argument.** Goal A's leading standing hypothesis is
OPT: all 17 pilots bottom at ~2.4 bits/byte near step 6000 and rise to 3.8–4.1 by 48,000 across GRU
and transformer, fabric and `FABRIC=0`, every routing variant — a cause common to every arm. The
tree names **two** unmeasured explanations for that shape. One of them, the constant `2e-3`, has a
one-flag ablation (`lr_sched="none"`). The other, gradients large enough that the steps overshoot,
had **no switch anywhere in the tree**, so the two hypotheses could not be compared on equal terms.
The literature is unambiguous that global-norm clipping at `max_norm=1.0` is the near-universal
default in transformer/LM recipes, and that clip-by-norm is preferred to clip-by-value because it
preserves gradient direction and rescales magnitude only. Both arms are compatible with this
framework and neither is forced, so the question is settled by measurement, not by argument.

**⚠ THE DEFAULT IS `0.0` — OFF — AND NOTHING MOVES.** Every recorded number in this project was
taken with no clipping; off is that configuration exactly. Turning the standard remedy on by default
would *replace* the confound this question exists to disentangle rather than remove it, and would
silently move every recorded result off its measured setting. `OPT.build` refuses a negative
max-norm at startup and prints `Gate opt.build.grad_clip` as `"off (0.0)"` or as the resolved value,
either way — a run that does not clip says so rather than omitting a line.

**It is not armed-but-inert padding, and that is checkable.** It has a reader (`OPT.maybe_step` step
5, after the norm is recorded and before the step, so the reported p50/p99 are the norms the run
produced and not the clipped ones — an instrument that measures its own remedy answers nothing), a
stated default, a startup refusal, and its own DID IT FIRE counters: `opt.clip.applied` against
`opt.clip.armed_no_clip`, because *clipping on and nothing ever exceeded the norm* is a different
statement from *clipping off* and the report must make both.

**THE THREE STATES, WRITTEN OUT, because a mechanism shipped OFF is the case the discipline is
easiest to fail on.** The framework rule is that every gated mechanism answers *fired* /
*armed-but-0* / *unreachable*, and at the shipped default this one is in the third state on every
run — which is exactly when a report is tempted to print nothing. It may not. **Unreachable/off:**
`grad_clip == 0.0`, and `Gate opt.build.grad_clip` prints `"off (0.0)"` — a printed line, not an
omitted one, so a reader can tell "this run did not clip" from "this report does not mention
clipping". **Armed but 0:** `grad_clip > 0` and `opt.clip.applied == 0` while
`opt.clip.armed_no_clip == opt.step` — the clip was live and no step ever reached the max-norm,
which is a *result* about the gradients and not a configuration fact. **Fired:**
`opt.clip.applied > 0`, with `opt.grad_norm.p99` beside it saying how far over. The three are
distinguishable from the counters alone, without reading the environment, which is the property
that makes the measurement below runnable from a report rather than from a launcher's memory.

**THE MEASUREMENT THAT RETIRES IT — one run, and the owner has offered the GPU time.** Run the
shipped configuration at `OPT_GRAD_CLIP=0` and read `opt.grad_norm.p50` and `opt.grad_norm.p99` from
`OPT.counters` across the whole run, including the window where held-out bits/byte turns from ~2.4
upward near step 6000. **If p99 stays within a small multiple of p50 across that turn, clipping
cannot be the mechanism** — the lever is then retired to `docs/dropped_levers.md` with the number
attached and the LR explanation stands alone. **If p99 spikes at or before the turn**, run the
matched pair `OPT_GRAD_CLIP=0` vs `OPT_GRAD_CLIP=1.0` with everything else fixed, and against the
same seed set as the `lr_sched="none"` ablation so the two explanations are compared on one axis
rather than one after the other. The default moves to `1.0` only on that pair, never on the
literature alone.

### Q-LM-9 — the gru arm's third dropout site is the memory-key source — **RESOLVED 2026-09-02: (b). `LM.encode` RETURNS THE UNDROPPED HIDDEN AND THE READOUT DROPOUT MOVES INTO `LM.decode`. NO SIGNATURE MOVED; `LM_DROPOUT` DEFAULT UNCHANGED AT `0.0`, WHERE NOTHING MOVES — BUT ITS HELP TEXT DID, IT NAMED TWO OF THREE SITES**
`:1556-1558` has three dropout sites and the lever's help text names two. The **third** drops out the
returned hidden state, and the source's own comment on that line says `(B,L,D) hidden -- also the
memory-key source`. So with `dropout > 0` the memory keys written during training are computed from
a dropped-out hidden state while the keys used at eval are not — **a train/eval key mismatch in the
store goal B is measured on.** Inert at the 0.0 default. **Ruling needed:** should the output dropout
apply to the memory-key path? It is LM's lever and MEM's blast radius, and no wire records it.

**RESOLVED 2026-09-02 — (b): `LM.encode` returns the UNDROPPED hidden, and the readout dropout moves
into `LM.decode`, before the head. No signature moved. ⚠ A DEFAULT DID NOT CHANGE — `dropout = 0.0`
— BUT THE LEVER'S HELP TEXT DID, because it named two of its three sites.**

*The invariant, stated plainly:* **`LM.encode` returns the representation; `LM.decode` performs the
regularised readout.** Arithmetically that is the old gru arm exactly — `head(drop(h))` either way —
so the LM's own regularisation is unchanged.

*What it repairs.* `compose.py` binds `key_fn = LM.encode`, and `MEM.write` / `MEM.maintain` take
that callable, so **the memory keys ARE `encode`'s return**. Under the old shape, at `dropout > 0`
with the module in train mode, every key written during the loop was computed through a dropped-out
hidden while at eval the same function returns the undropped one — **the store goal B is measured on
would be queried with keys drawn from a different distribution than the ones it holds**, and FAB's
router would see a different input in train than in eval. This is why the option is structural rather
than conventional: it also removes a hidden dependence on **module mode** from a value three packages
consume, so ISSUES.md:441 — `holdout_bpb`'s `finally` block returning the model to TRAIN
unconditionally — can no longer corrupt the store, because the key path has no dropout left to leave
switched on.

*Why not (c), a `for_key=` keyword on `encode`.* It moves a frozen signature for no gain and puts a
second path flag beside `n_layers`, which the gru arm already ignores. Two path flags with different
arm semantics is precisely how `KEY_LAYERS` became *"silently inert twice over"* (CENSUS.md:250).
Why not (a), the status quo: it leaves a lever whose declared blast radius (LM) is smaller than its
actual one (MEM's store, FAB's router) with **no wire recording it — and no wire can**, because it is
not a value crossing a boundary, it is a code path.

*Two things this changes at `dropout > 0`, both on P9's list, both inert at the 0.0 default.*
(i) FAB's routing input and MEM's keys lose their dropout. (ii) **On the TRANSFORMER arm the readout
site is NEW** — `TinyTransformer.forward` was `head(s.encode(x))` with no readout dropout at all.
That is the same decision as this tree's existing correction on that arm (the old
`nn.TransformerEncoderLayer(dropout=0.0)` hardcode made `LM_DROPOUT` 100% inert on
`MODEL=transformer`), and it is stated here rather than discovered later.

*One stale sentence corrected while doing this.* `lm/levers.py` said that because the GRU's
inter-layer dropout applies only at depth > 1, the knob *"reaches exactly one place — the embedding"*
on the shipped arm. It reached **two**: the old arm applied `s.drop` twice in two lines, and the
second of those was the memory-key source. Off by one, in the direction that mattered.

*The convention this agrees with, stated as a convention and not as a result.* A retrieval
datastore's keys are normally built with the model in **evaluation mode**, so keys are deterministic
and comparable to query-time keys (the kNN-LM line of work). No paper was found measuring the
degradation from building a datastore with dropout active, so this supports (b) and is not the reason
for it; the reason is that (b) is the only option here with no signature cost that makes the property
structural.

### Q-FAB-1 — port the transition hop arm, or drop `FAB_HOP_MODE`? — **RESOLVED 2026-09-02: THE LEVER STAYS, ONE ARM IS PORTED, AND THE OTHER IS REFUSED AT STARTUP**
**Options as put:** (a) port both arms (cost: `SRC_p` as a live parameter, the `R` softmax, `ctrl`,
per-hop query bookkeeping, and a second forward to keep correct); (b) port `soc` only and **drop**
the lever to `docs/dropped_levers.md` with the 0.533-vs-0.058 measurement as the reason; (c) keep
the lever as a startup refusal. This contract recommended **(b)** and the evaluating agent
independently recommended **(b)**.

**(b) IS NOT TAKEN.** A drop retires census row `CHAIN_ROUTE`, and the owner's standing rule is that
a mechanism kept for future use is kept **with a switch**, not deleted — "do not remove or downgrade
functionality to make something simpler". Recovering the arm afterwards would be a census amendment
rather than a body. So: **the lever stays, `soc` is the ported arm, and `FAB.build` now READS
`hop_mode` and REFUSES `"transition"` at startup**, naming the arm and this question. That is
nominally (c), and this contract's objection to (c) — *"it looks like a live capability"* — is
answered by making the lever's own comment and the refusal message say what is built. What (c) must
never become is the state it was actually in: **no reader at all**, so `FAB_HOP_MODE=transition`
passes `choices=` validation and then runs `soc` in silence. That is M24 exactly
(`s.loop_soc = (_env("CHAIN_ROUTE","soc") == "soc")` at `:1843` made every typo the *other* walk),
and it is the one outcome none of the three options may produce.

**Why the arm is not built now, and what would build it.** Two independent old-tree readings point
away from it and neither passes through the C3-voided counterfactual: `H(hop1|hop0)` was **0.533
bits** over 202k transitions on the soc loop against **0.005–0.058** on every transition arm, and
`:2731-2734` records the compute path reaching **25%** of experts under society against **8%** under
chaining, *"because mass CONCENTRATES as it flows"*. Both are D1-suspect old-run numbers, which is
why they defer the arm rather than delete it. Against them sits a real framework cost: **two forward
paths inside one function**, which `fabric/api.py`'s header exists to forbid, and ~20 DID-IT-FIRE
counters becoming arm-conditional. **The measurement that retires the refusal:** port the arm and
re-run both readings on *this* tree's instruments — `H(hop1|hop0)` over the hop choices, and expert
coverage of the compute path — on one seed pair at a run long enough for `maybe_deepen` to fire.

**What changed in the tree:** `FAB.build` reads `hop_mode` and declares the refusal; the §4
UNCONSUMED row is gone because the lever now has a reader; `FAB.forward` states that **per-hop states
are collected on the soc loop**, which is the one-line repair that makes `hop_sup` reachable on the
path that runs (M27: `s._hops.append` occurs at exactly one site, `:2819`, inside the unported
branch); and `FAB.state_dict` **no longer claims to save `ctrl`** — `ctrl` exists only on the
transition arm (`:1907`, read at `:2827`), `FAB.build` allocates none, so the contract was promising
to checkpoint a parameter nothing creates. It returns to that list with the arm and not before.

### Q-FAB-2 — does the fabric gain the merge? — **RESOLVED 2026-09-02: YES, IN ΔW SPACE, WITH NOTHING IN MEM. ⚠ THIS TURNS A MECHANISM ON AT THE SHIPPED DEFAULT**
**The escalation's precondition is false.** This contract escalated on the ground that *"memory
ownership is `expert_id % n_own`, so merging two experts changes which owner block holds whose
entries"*, and therefore required *"one named MEM entry point, reassign the entries owned by expert i
to expert j"*. Three verified reads dismantle it: **`MEM.read` is GLOBAL across owner blocks** even
when writes are partitioned (`memory/api.py`, `read`: *"knowledge is owned but not walled off"*), so
no entry becomes unreadable when an expert disappears; **MEM has no per-expert ownership to
reassign** — an entry's owner is its *row index*, and `d_owner_blocks = _owner_blocks(4096, 64) = 64`
means 64 experts share every block, so *"the entries owned by expert i"* is not a set MEM can name;
and **a cull already does everything a merge would do to MEM, and ships** — `remove()`'s
swap-with-last renumbers the survivor above the hole, changing *its* `expert_id % 64` too. The
merge's MEM blast radius is strictly **smaller** than the cull's. **No MEM entry point is minted.**

**The legacy arithmetic is wrong and the correction is the ruling.** `:3083` averages the **factors**:
`A[a] = ½(A[a]+A[b]); B[a] = ½(B[a]+B[b])`. Since ΔW = A·B is bilinear, that gives
`¼(A₁B₁ + A₁B₂ + A₂B₁ + A₂B₂)` — the intended contribution **halved**, plus two cross terms nobody
trained — and A/B are zero-init at birth with no shared basis, so the factors are not aligned either.
The census's headline claim, *"both experts' learning survives where culling destroys it"*, is not
supported by its own arithmetic. `FAB.manage` step 0 therefore merges in **ΔW space at fixed rank**
(thin QR of `[A_a | A_b]` and `[B_a | B_b]ᵀ`, SVD of the 2r×2r core — O(d·r²), a few thousand flops
at d=128, r=8) and reports the **truncation residual**, which makes the claim falsifiable in-run for
the first time. The merging literature reaches the same place from the other end: MC-SMoE aligns
expert weights by permutation *before* averaging precisely because unaligned factor averaging
destroys both, and the exact-mean LoRA construction needs concatenation at rank 2r, which a
preallocated fixed rank refuses.

**⚠ THE DEFAULT.** `FAB.merge_dist` resolves to **0.10, not 0**. Until now the lever was inert
because the mechanism did not exist; implementing it **turns a merge on for every default run**. The
default is deliberately *not* moved to 0 — that would decide by argument a question the census
already answered, and would leave goal B without its only consolidation path — but the change of
state is stated here, in `fabric/levers.py`, and in §4.

**What is actually REACHABLE at the shipped defaults is a different sentence, and both must be said.**
The absorbed expert `b` must be past `grace` (the absorbing expert need not be: requiring both would
mean merging inside the eligible set, and merging over the whole live set would re-absorb every
`replicate`/`xover` birth, which are near-duplicates by construction, making `replicate` inert). By
**Q-FAB-5**'s arithmetic the past-grace set is **provably empty** at 506–937 windows. So a default run
reports `fab.merged` as **`unreachable`, with that arithmetic printed** — not "armed but 0" and not
"fired". Three states, three counters (`fab.merge_declined_grace`, `fab.merge_declined_residual`,
`fab.merged`), one declared `Gate`. **The evaluating agent's proposed fix for this — "require only
the absorbed expert to be past grace, which resolves the reachability problem" — does not resolve
it**, because *eligible* **is** *past-grace* (rule 3 of `manage`); the honest answer is the
`unreachable` declaration, not a differently-worded gate.

**Also recorded:** the residual is the second gate and costs no lever (if it reads high the operator
lowers `merge_dist`, which is what that lever is for); the Adam moments on `A[a], B[a]` go stale
after an in-place write, as they already do for `rescue`; and the *better* gate — output-space
redundancy from `FAB.contribution` — is unavailable because that entry point is deferred for want of
`candidates` and `baseline_logits_fn`. If it is ever un-deferred, revisit this.

### Q-FAB-5 — splitting `use` from `uage` re-denominates `grace` — **RESOLVED 2026-09-02: SPLIT AS SPECIFIED, `grace` STAYS AT 48, AND THE RETUNE BECOMES A MEASUREMENT**
The split is required — without it, eligibility and the cull's ranking key are the same number (H12)
and every non-argmax expert is permanently uncullable (H13). Re-expressing `grace` as a multiple of
`chain_k × hops` is refused: that makes it a computed value of two other levers, the L1 defect, and
it would move the cull's eligibility threshold through a *default* where `grep -rn d_` cannot see it.

**Two corrections to the "32× faster", because they are different quantities implying different
retunes.** **Per expert** the ceiling is `hops`, not `chain_k × hops` — one expert is selected at
most once per hop — so its own clock ticks at most **4×** faster. **Population-wide** the credit
issued per window goes from 1 to `chain_k × hops`, up to **32×**. And at the **shipped** `depth0 = 1`
the effective factor is **8×**, because the chain starts at one hop and `maybe_deepen` sits on the
`manage_every = 500` cadence, which fires at most once in a default run.

**The number that decides it is not in the question.** At `n0 = 2048` with 8 credits per window, mean
`uage` per expert after a full default run is `506 × 8 / 2048 = 1.98` against `grace = 48`. Reaching
48 needs **12,288 windows** at depth 1 (3,072 at full depth 4) against a run of **506–937**. **The
past-grace set is provably empty at the shipped defaults**, so the utilization cull, `rescue` (which
lives inside it), `lr_boost`'s budget (sized on the eligible count) and the new merge are **all
unreachable** — even though `derive.cull_gate_open(2048, 4096, 0.45)` returns `True`. The gate is
open onto an empty set, and that is a different report line from "the gate never opened". Under the
*old* argmax-only clock the same threshold needed 98,304 windows, so the split improves reachability
by 8–32× and **still leaves grace short by 6–24×**.

**This family is outside the C11 audit's reach BY TYPE.** `derive.cadences_that_cannot_fire` refuses
anything that is not `units.Windows`; `grace` is `units.Selections`. Whoever answers C11 must be told
there is a second unreachable-threshold family here, and if the run length changes this arithmetic
must be re-derived rather than carried.

**What changed in the tree:** `fabric.cull_eligible` (and `fab.merged`) must report **`unreachable`
with their own arithmetic**, never "armed but 0"; and three readings were added, all pure reads of
books FAB already keeps, all fields on P4-defined record types — **`fab.mass_per_selection`**
(`Σuse / Σuage`, the evidential dilution factor, and **the number the P9 retune of `grace` is set
from**), **`fab.uage_per_expert_per_pass`** beside `fab.experts_past_grace_ever` (a cumulative zero
does not say *why*; the rate does), and **`fab.cull_rank_spread`** (max/min `use` inside the eligible
set — at ≈1 the ranking carries no information and H12 survived the split in a new dress, since
routing concentrates and the experts that cross grace first are the *most-used* ones while the cull
then ranks that set by `use` ascending. This is the falsifier for the repair itself). **The level
does not move in this commit**: changing an instrument's definition and its configuration in one step
is how this project produced numbers nobody could attribute, and the split *is* the definition
change. On P9's list, with `mass_per_selection` named as its input.
### Q-MEM-4 — `pressure()` cannot reach `pressure_thresh` — **RESOLVED 2026-09-02: (a), WITH THE REASON CORRECTED AND ONE ADJACENT HOLE CLOSED**
H33: every write lands on probation, only retrieval promotes, probation is over budget (measured
82% of the store), eviction takes the probation branch almost always, and `pressure` reads ~0
whatever the store is suffering. D3 keeps the pressure-signal rule as a selectable arm, and **an arm
needs a threshold that can fire**. **Recommendation: keep the definition, print the Gate's
arithmetic, and MEASURE BEFORE RETUNING** — capacity is now 8,192, not the 200,000 the pilot ran at
(11.7M writes against 1,469 probes), so at the same probe rate promotion covers a far larger share
of the store per pass and the region may sit inside its budget for the first time. Changing an
instrument's definition and its configuration in one step is how this project produced numbers
nobody could attribute.

**RESOLVED (a): keep `pressure = main/(main+prob)`, keep `pressure_thresh = 0.80`, declare the
Gate, measure before retuning. NO DEFAULT MOVED.** What changed is the reason, and the corrected one
is *exact* where H33's is approximate. H33 argues from a write:read ratio; the operative chain on
**this** tree is shorter and admits no configuration: only a retrieval promotes out of probation,
the only in-loop retrieval is `MEM.maintain`'s job 1, its `probe_contexts` **has no producer**, and
`MEM.read` is a **deferred** entry point for want of `queries`. Therefore `n_promoted ≡ 0`,
probation ≡ 100% of the store, every eviction takes the probation branch, `n_evict_main ≡ 0` and
`pressure` is **exactly 0.0 for every setting** — not "≈0 at the measured ratio". Retuning either
lever against a structural constant is unfalsifiable, which is why (b) is refused; (c) throws away
the one thing the definition gets right (evicting never-read junk is not scarcity); (d) is refused
by D3 and by the owner's standing rule that a broken instrument does not convict a mechanism.

**The Gate reports a STATE, not a number.** With `n_promoted == 0` over the interval it prints
`unreachable (no promotion path: probe_contexts has no producer, n_promoted=0)` and never `0.000` —
and it names **both** causes, because there are two: no promotion path, *and* the arm is not
selected (`src_share=0.5 > 0` makes `quota_arm` `"reservoir"`, and `FAB.grow_on_mem_pressure` ships
`False`, so the pressure-signal arm is off at both ends).

**The adjacent hole, closed here because two readings are different code and they differ by 64×.**
Nothing said whether `probation_frac` — and therefore the eviction branch, and therefore `pressure`'s
denominator — is measured **per owner block** or **over the store**. `MEM.write`'s own sentence
settles it: *"The owner NARROWS the candidate SLOT SET to its block; probation narrowing and
per-source floor protection then run INSIDE that set."* It is **per block**. At the shipped
`d_capacity=8192`, `d_owner_blocks=64`, `quota=128`, a `0.10` share is **12.8 entries inside a
block, not 819 across the store**. `census`'s `probation_share` is a store-wide report aggregate and
is **not** the predicate; a Gate printing the aggregate against `probation_frac` compares two
denominators.

**Expect the eventual retune to RAISE this threshold, not lower it.** Once the probe has material,
`probe_rows/probe_every = 64/25` query rows per window at `topk=8` is ~20 entry-touches per window
against ~1 gated write, so probation can fall *under* budget and `pressure` can pin at 1.0, above
0.80, permanently. Both pinned-at-0 and pinned-at-1 are live outcomes.
**The measurement that settles the level:** one P4 smoke run with `probe_contexts` stubbed from the
training batch itself, printing `probation_share` per block and the two eviction counters for 2,000
windows. Nothing about the level should move before that run.
**Not a wire, and never can be:** `pressure_thresh`'s only reader is `MEM.census`; `FAB.grow_check`
takes `memory_pressure` and reads no threshold, so the root must pass **MEM's verdict** or
`fab.grow_mem_eligible` fires on every flush. A store occupancy measured at runtime can never be a
wire. (`fabric/levers.py`'s stale *"arrives here as a wire"* was already repaired by the FAB slice
on 2026-09-02; nothing further is owed.)

### Q-RUN-1 — the progress/ETA log cadence has a described owner and no declaration — **RESOLVED 2026-09-02: (b), THE CONSTANT, PLUS ONE AMENDMENT THE FRAMEWORK FORCES**
`eval/levers.py` says the split is deliberate and that the progress line takes "a separate RUN-owned
log cadence"; `train/levers.py` states, as a testable claim, that **RUN declares no cadence and no
threshold**, and the census gives RUN no such row. **Recommendation: a fixed module constant in
`src/train/` (`PROGRESS_WINDOWS`), documented as a property rather than a knob**, the way
`PLATEAU_WARM = 1000` is justified. A progress line is a property of a human watching a terminal;
nothing in the two goals turns on it. If it later needs to be tunable, that is one census row and
one lever, added deliberately.

**RESOLVED 2026-09-02: the recommendation is taken, and it is amended.** `train/api.py` now declares

```
PROGRESS_WINDOWS = U.Windows(100)
```

a module constant — **not a lever, no environment name, no census row** — driving the progress/ETA
line **and the profiler dump** (the sentence that created this question covers both consumers).
`_periods` gains a sixth key, `'progress'`, so the gate goes through `Cadences.due` like the other
five. **No frozen signature moved. No lever, wire, coupling or default moved. No census amendment.**

**⚠ A NEW DEFAULT EXISTS AND THERE IS NOTHING TO TURN IT OFF WITH.** `PROGRESS_WINDOWS = 100`
Windows. It was chosen to be sane at both ends of the range, because nothing can move it: at the
shipped defaults a run is at most 937 windows and about 506 at the measured 1.85 bytes/token, so 100
fires ~5 times, while the old `RATE_EVERY` default of **2000 would fire zero times** and put this
line straight onto the ISSUES P1-C11 list. It is also the shortest cadence already declared in the tree
(`DOM.manage_every = 100`), so it can never be the reason a report has nothing in it. On a long run
(94 MB, ~400k windows) it is ~4000 lines over hours, which is what an ETA meter is for.

**The question was live in the strongest sense: three statements disagreed and neither object
existed.** `eval/levers.py` and `.rework/CENSUS.md` both said *"a separate RUN-owned log **cadence**"*;
`eval/api.py` said *"RUN's own fixed **constant**"*; and `grep -i progress` over `src/` returned
**nothing** — no lever, no constant, no `_periods` key. A cadence and a constant carry different
obligations (a census row, an environment name, a `Cadences.ledger` key, `cadence_audit` coverage),
so it was a fork and not a wording difference. All three now name the constant.

**Why not (a), a `RUN.progress_every` lever.** `train/levers.py` opens with *"nothing here is a
cadence, a threshold or a weight"* and enumerates the seven numbers RUN owns; an eighth would break
that sentence, which is a testable claim about this package. It would also need a census row, and
the ancestor row — `RATE_EVERY`, verdict `rename` → `EVAL_CURVE_EVERY` — already *contains* the split
this constant implements. And the split's own history is the argument against a knob: `RATE_EVERY`
drove five things at once, so `RATE_EVERY=100000` to quieten a smoke run **suppressed the curve table
entirely** and the curve fix went unverified for a round. A log cadence that can be turned up is a
log cadence that silently disables things.

**Why not (c), wall-clock seconds.** It is the most honest denomination for an ETA meter and it is
immune to C11 — but `U.SECONDS` is a unit string and **not** a `Clock` kind (`CLOCK_KINDS = (Steps,
Flushes, Windows, Backwards, Epochs, Selections)`), so it can never pass through `Cadences.due`, and
RUN would evaluate a sixth gate by a mechanism nothing else in the tree uses. It fights the unit
types instead of fitting them.

**The amendment, and why it is forced rather than a preference.** The answer that proposed it rated
it *medium* confidence, as an inference from the DID IT FIRE discipline. It is not an inference —
two statements in the tree require it, and together they leave no other placement:

1. `compose.py`, sixty lines above `LOOP_ORDER`: *"**Every** PERIODIC gate goes through
   `Cadences.due(key, period, clock)` with a period its OWNING package supplied, **so the modulo form
   that fired zero times at every BATCH_W > 1 is not writable at a call site**."* A progress line
   written `step % PROGRESS_WINDOWS == 0` below the batch early-out is that defect exactly — and it
   is a line whose absence a reader would blame on the run being quiet. The same block permits
   exceptions but requires each to be **named where it happens with its own evidence**; it lists
   three, and this would be a fourth with no evidence of its own.
2. `RUN.new_cadences`: *"**THE KEYS ARE THE ROOT'S, NOT THIS FUNCTION'S.** `compose.py`'s cadence
   table is the authority on which key maps to which owner's period."* So a `due('progress', …)` call
   whose key is not in `_periods` is a key invented at a call site.

Together: it goes through `Cadences`, therefore its key comes from `_periods`. The gain is real and
checkable — `Cadences.ledger()['progress']` is its DID IT FIRE surface, and `RUN.cadence_audit` now
covers **six** gates, so "the progress line cannot fire at this run length" is a sentence the audit
prints rather than a claim in a docstring.

**What it does NOT need, and this is why nothing was minted.** No typed accessor and therefore **no
new entry point**. The **five** accessors — `EVAL.curve_period`, `DOM.manage_period`,
`FAB.manage_period`, `MEM.rekey_period`, `CKPT.save_period` — exist because `Config` hands back a
bare `int` for all 35 Clock-unit *levers* (ISSUES P1-H51, three of five gates handed bare ints until
2026-08-30); a module constant has no `Config` to drop its kind, so it is written `units.Windows` at
its definition. That is a **construction, not a conversion** — it re-attaches a kind, it does not
cross one. *(This sentence said "four" until 2026-09-03. It is the sixth count this document has got
wrong, and the one K13 cannot catch: **`four` is a word, and the check reads digits.** It is listed
in K13's own docstring as the worked example of what it does not see.)*

**And this gate has no row**: rows are entry-point calls and no entry point prints the progress line
— the loop driver does, the way it owns the window cut `_window_bounds` names. So six keys, five of
them rowed, and that asymmetry is stated at `_periods`, at `new_cadences` and in the `cadence` row.

**⚠ THE ASYMMETRY IS NO LONGER ONLY STATED — K9 WAS WIDENED TO READ THE MAPPING (2026-09-03).** This
section said *"`K9` reads the order tables only"*, and that was true and was the defect: the sixth
period was the one period **no check in the suite could see**, so `PROGRESS_WINDOWS` could have been
edited to a bare `100` — the exact H51 shape, which makes `Cadences.due` raise on its first
evaluation — with all six suites green. `K9` now reads the `_periods` mapping itself in addition to
the rows: every value must be a **call** (the typed accessor) or a module-level constant
**constructed with a Clock kind** at its definition, which is what `RUN.PROGRESS_WINDOWS` is. Its
detail line prints `6 period(s) in _periods, 1 of them a module constant with no order-table row`,
so the asymmetry is now a number the suite prints rather than a claim three docstrings make. Two
self-test cases hold it: the constant written `= 100` must fail, and the same constant written
`U.Windows(100)` must pass.

**Where "RUN owns no threshold" stands now.** It is narrowed, in the two places that carry it, to
*no threshold that decides anything the model computes* — and the one log cadence is named as the
exception. A sentence that is false in one case is worse than a sentence with a stated exception.

### Q-RUN-7 — `RUN.bench`'s second job — **RESOLVED 2026-09-02: (c), AND IT NEEDS NO CODE CHANGE — ONLY THIS PARAGRAPH WAS WRONG**
`prompt.py:41` sets `os.environ["BENCH"]="1"` before importing `self_organize`, purely so that
sampling from a checkpoint does not trigger a full report. **Recommendation: "do not run the report"
is the entry point choosing which half to run, not a lever.** `bin/sample` calls the composition
root with the battery disabled; `RUN_BENCH` keeps only its throughput meaning. *(The clause "with the
battery disabled" is **wrong** and is corrected in the resolution below: `compose()` has no such
parameter and needs none.)* One flag doing both
jobs is how the throughput arm and the sampler ended up sharing a switch — and `prompt.py` then
receives the frozen EVAL Config instead of re-reading the environment, which also removes its own
`GEN_LEN` and `GEN_TEMP` second defaults.

**RESOLVED 2026-09-02. The decision was already the tree's position; what was wrong was the
mechanism this paragraph named, and it would have sent a P8 author looking for a parameter that does
not exist.** `src/train/api.py`'s `mode()` already says *"'Do not run the report' is the ENTRY POINT
choosing which half to run, not a lever"* and *"nothing in this package knows what a battery is"*;
`train/levers.py` says the same at `bench`; `eval/api.py` and `eval/levers.py` already require
`prompt.py` to receive the frozen EVAL Config rather than re-read `GEN_LEN`/`GEN_TEMP`. **Nothing in
`src/` conflates the two jobs, and nothing in `src/` changed for this ruling.**

**The correction.** *"`bin/sample` calls the composition root with the battery disabled"* names a
capability that does not exist and is not needed. Verified: `compose(environ=None, *, restored=None)`
has **no** battery parameter, and `bin/` and `src/bin/` **do not exist**. The accurate mechanism is
simpler: **`compose()` BUILDS; it does not run the loop or the battery.** `LOOP_ORDER` is data, and
the `R` stage is executed by whoever drives the loop. A sampler therefore calls `compose()`, takes
the `System`, and calls the generation path directly. **There is nothing to disable, no flag, and no
`compose()` parameter.**

**Why the two options that would add one are refused.** (a) a second lever (`report`/`no_report`)
reintroduces the shared switch under a new name, and two flags can disagree; `train/levers.py`
restricts this package to *which half of the program executes* as a **run mode**, and a sampler is
not a run mode — it is a different program. (b) `compose(..., run_battery=False)` makes the
composition root know what a battery is, which `train/api.py` says in as many words it does not, and
adds a boolean to the one signature every phase writes against. DID IT FIRE argues the same way: with
one flag doing two jobs, `RunMode.bench` cannot distinguish *"timing arm"* from *"sampler suppressing
a report"* — which is how the throughput arm and the sampler came to share a switch in the first
place.

**What this constrains, for whoever writes the P8 entry points.** `bin/sample` calls `compose()`,
takes `configs["EVAL"]` off the `System`, never reads the environment, and never enters the `R`
stage. `RUN_BENCH` keeps only its throughput meaning. `prompt.py` at the repository root is the old
system: it is rewritten or retired, not ported — its `os.environ["BENCH"]="1"` import trick cannot
work under the spine at all, because `from_env` is called once, inside `build()`.

### Q-WORLD-6 — WORLD's Windows-denominated cadence — **RESOLVED 2026-09-02: (b). NO WIRE. A `NOT_WIRES` ENTRY, AND THE GENERAL BLIND SPOT NAMED**
`FAB.manage_every` reaches WORLD through RUN's `Cadences.due` and no period enters WORLD's Config
(§1, C3). **If the owner wants the reach visible in `affects()` — and it should be — that is one new
row, `FAB.manage_every → WORLD.d_manage_period_windows`, valued `Windows(manage_every)`.** The
contract phase left it out because the composition root already imposes the ordering and the budget
question belongs to whoever also rules on Q-CLOCK-1.

**RESOLVED (b), and the document's own recommendation is NOT taken.** Four things decide it and any
one of them would:

1. **C3 already froze this, in these words:** *"`WORLD.manage` is called from the composition root
   through RUN's Windows-typed `Cadences.due` with `FAB.manage_every` — **no period enters WORLD's
   Config**, so no Flushes wire can reach it."* That sentence is what keeps the Flushes wire out. A
   **Windows** wire into the same field re-opens the door it closed; `world/api.py` repeats it.
2. **WORLD has no `d_` field at all and would have no arithmetic to do with one.** The root
   evaluates the gate and calls `manage` only when it fires, and `FAB.manage_period(fab)` already
   returns typed `Windows` while `Cadences.due` refuses anything else. So K5's required
   `WIRES READ:` would be a decorative `_ = world.d_manage_period_windows` forever — the
   untrippable-guard shape this tree has 60 records of.
3. **`WORLD.manage` is deferred** for three unrelated reasons (`plateau` contradicts WORLD's own
   `state_dict`; `add_param_group` needed `OptState` to name an optimizer; `latent` arrives
   backwards). A row would print an edge the run does not make, which is exactly the failure
   `spine/assemble.py` names: *"the printed graph shows an edge that was never made… and the sweep
   reads as passing because nothing moved."*
4. **Budget.** 19 of 25 wires, 23 declared couplings. This would spend one of the last lines on the
   least reachable case. *(Ledger unchanged by this ruling: still **19 of 25**, **23 couplings**,
   and `NOT_WIRES` is now **7 entries** — Q-OPT-1 added one in the same round.)*

**What the entry buys is the honest statement of a bigger gap: `affects()` does not see cadence
reach for ANY gate.** `DOM.manage_every` already gates `MEM.census`, `DOM.manage`, `DOM.census`
**and** `MEM.apply_domain_plan` with no `DOM→MEM` wire anywhere. A single WORLD row would be a spot
repair that makes the graph look *more* complete than it is. **The did-it-fire surface for every
periodic gate is `Cadences.ledger()`**, whoever owns the threshold, and **the L3 isolation sweep must
take cadence reach from `Cadences.ledger()` and `LOOP_ORDER`** — both of which the root already holds
as data — **not from the wire ledger**. Teaching the L3 oracle that union is option (c) and is the
real repair; it is filed in the `NOT_WIRES` entry so it is not lost. **This ruling does not change
if Q-CLOCK-1 frees budget:** the C3 contradiction, the decorative read and the edge-that-is-not-made
all stand on their own.

### Q-WORLD-8 — `soft_cull`'s irreversibility: which half gets fixed? — **RESOLVED 2026-09-02: FIX M70 AS SLOT REUSE. THE LITERAL READING OF THE RECOMMENDATION BELOW IS NOT IMPLEMENTABLE.**
M69 says `alive` is only ever written to 0.0 and nothing restores it; M70 says `grow()` counts
**total** predictors against `nmax`, not live ones. **Fixing both** lets the population oscillate at
the cap indefinitely, minting and culling. **Recommendation: fix M70 only** (count live), leave
`soft_cull` one-way, and **rename it and its docstrings so they stop claiming reversibility** — both
currently say "reversible: params kept". A dormant predictor that still costs forward compute and
gradient while contributing ~1e-6 of the blend is a real cost, and the honest repair is a hard
routing penalty, not resurrection. `ManageResult.live` vs `n()` is the number that says whether the
population has silently become mostly dead.

**RESOLVED: (b) — the cap is on LIVE predictors and a mint at the cap CLAIMS THE LOWEST DEAD SLOT.**
This is the recommendation above, implemented the only way the buffers and the frozen enum permit,
and with the compute cost actually removed instead of merely deplored. **No signature moves**
(`manage(world, w, *, latent, plateau, add_param_group)` is untouched and `ManageResult`'s field set
already covers it) and **no default moves** (`nmax` is still `6`, `grow` still `True`, `n0` still
`3`); what changed is `nmax`'s **help-string meaning** — it caps LIVE predictors — and that is said
loudly here and in `world/levers.py`.

**Why "count live and append" — this document's own literal recommendation — had to be refused.**
`fit`, `mass` and `alive` are buffers of width `nmax` (`world_model.py:81-83`), and `grow()` does
`s.preds.append(...)`. Comparing **live** against `nmax` while still appending drives `n()` past
`nmax`, and `update_fitness`'s `for i in range(s.n()): s.mass[i] = …` then indexes off the end of
all three — besides unbounded forward compute and a checkpoint whose `n` exceeds its own `nmax`,
which `WORLD.geometry` and `load_into`'s two-directional refusal (M43) exist to reject. **The frozen
DID IT FIRE row independently forces the same conclusion:** `blocked_reason` is one of
`{grow_off, at_live_cap, no_plateau, cooldown, null_world}` — **`at_live_cap`, and there is no
`at_total_cap`** — so a `grow()` refusing at `n() == nmax` while `live < nmax` has *no legal reason
to report*. Fixed-width buffers plus that enum leave exactly one implementation: reuse the slot.

**`soft_cull` stays one-way in the sense that matters**, and the "reversible: params kept" claim is
deleted from both docstrings: a culled predictor's *learning* is never restored. Resurrection is
refused for a **stronger** reason than the oscillation this document gives — a resurrected
predictor's `mass` is *by definition* below `min_mass`, so it is culled again on the next pass
unless something else changed. That is a mechanism that cannot work, not one that works badly.
**And the compute cost genuinely stops being paid:** a dead predictor is **skipped in the forward**,
not held down by `log(alive.clamp_min(1e-6))` while still running and taking gradient for ~1e-6 of
the blend. That is the other half of "a hard routing penalty, not resurrection", and a docstring
change alone does not deliver it. **C6 must ride with this** — `mass` initialised on birth — or a
newborn, fresh or reused, is culled by the `soft_cull` in the same block and slot reuse becomes pure
churn.

**Total vs live, ruled once so the resume gate and Q-CKPT-2 do not have to guess.** `WORLD.geometry`
records **`n` = the ALLOCATED count, `len(preds)`** — the number of predictors that *exist*, which is
what decides which tensors are in the checkpoint — and **never the live count**. It keeps its
`MAY_WIDEN AND MAY_NARROW` rule. Under (b), `n()` rises to `nmax` and stops, `n ≤ nmax` becomes an
invariant `load_into` may assert, and **`live` is the number that moves in both directions**: it is a
`ManageResult` reading and a `state_dict` buffer, not a shape. The `alive` mask travels in
`state_dict`, so which slots are dead is *restored*, not re-derived — a resume that rebuilt it would
silently resurrect culled predictors.
**Corrected in the same edit:** `world/api.py`'s `geometry` DID IT FIRE line said it returns *"the
manifest `CKPT.check_geometry` consumes"*. It does not. The live manifest is `compose.py`'s
`_geometry_manifest`, which **deliberately holds no population count at all** (it must run before
anything is built, and `n` needs a built world). `WORLD.geometry` is the **recorded** side, and the
overlay that supplies `world.n`.

**The oscillation objection is answered by measurement, not by refusal.** Count reused-slot mints
separately from fresh ones (`n_slots_reused` beside `grown`), so *"minting and culling at the cap
indefinitely"* is a number the report states. The plateau predicate (`_winv > 0.9·_wl_ema`) and the
`4 × MANAGE_EVERY` cooldown already bound the mint rate and both become Gates printing their own
arithmetic. **The measurement that would settle whether the churn is worth paying:** one run with
`grow=True` past the first cull, reporting `grown`, `n_slots_reused`, `live`, `n()` and the
per-predictor `mass` spread — under (d), "fix neither", growth is permanently and silently disarmed
at the first cull, so there is no baseline to compare against until this lands.

**Literature bore and points the same way.** ReDo (Sokar et al., ICML 2023) reinitialises dormant
neurons — recycling the *slot*, discarding the dead unit's parameters — and continual backpropagation
(Dohare et al., *Nature* 2024) reinitialises a small proportion of the least-used units every step,
stating the trade-off this question is really about: too much reinitialisation loses stored
information, too little loses plasticity, i.e. **the churn is a cost to measure, not a reason to
refuse reuse**. Nothing in that literature *restores* a culled unit. The buffer-width and
`blocked_reason` arguments are this tree's own and are the load-bearing half.

**Blocked on Q-OPT-7, and that is now closed enough to proceed:** slot reuse still mints parameters
mid-run, so `manage` needs `add_param_group`, and `OptState`'s fields are now `base` and `encoder`
(the root writes `sysm.optimizer.base.add_param_group`). What is still missing is the **row**.

### Q-EVAL-5 — the curve probe's sample size — **RESOLVED 2026-09-02: READ THE LEVER, AND THE P9 ENTRY IS CONDITIONED ON RUN LENGTH**
`:6396` draws `range(16)` while `EVAL.curve_every`'s own help text quotes that 16 **as though it
were declared** — an undeclared second default inside the sentence describing the lever, which is the
L1 shape arriving through the document written to end it. **Read the lever.** The old `EVAL_N` was
*unraisable* — five of its six readers wrapped it as `min(24, EVAL_N)` or `min(48, EVAL_N)`, so
`EVAL_N=256` drew 24 — and hardcoding 16 rebuilds exactly that. An operator who wants the old cost
sets `EVAL_WINDOWS=16` and gets it, which is what makes reading the lever strictly better rather than
merely tidier. Minting a curve-specific `EVAL_CURVE_WINDOWS` is refused: it has no census row (N2),
and `eval/levers.py` declares `windows` as the size *"an eval Sample draws **when it does not declare
its own**"* — `curve_probe` declares none, so `ev.windows` **is** the declared answer.

**The cost, with the number and the condition on it.** `ev.windows` resolves to **64**, so the
multiplier is 64/16 = **4×** — checkable now that the resolved value is written down. **But it is 4×
of zero at the shipped defaults**: `curve_every = 2000` against a run of **506–937** windows means
this probe never fires (ISSUES **C11**, which names it *"the one number P3 exists to produce"*). An
unconditional "the default probe cost rose 4×" is a number nobody can reproduce — the exact failure
P9 exists to prevent — so **the P9 entry reads *"4× on runs long enough to probe; does not exist at
the shipped defaults"***. If the C11 ruling raises `DATA.stream_bytes` or `RUN.epochs`, re-read this.
Two things that follow and are already recorded: `curve_probe` is **deferred** to P5 for want of
`units_by_domain` and `logits_fn`, so `CKPT.Retention.consider` can never fire and `OPT.maybe_step`'s
`best_bpb` has no producer either. **What changed in the tree:** `CurveReading` now carries
`units_drawn` — the total the probe spent (windows × `LM.ctx`) — so the sample size is a knob whose
cost is *visible* as well as raisable and lowerable. That asymmetry is what `EVAL_N` failed. No
signature moves and no lever default changes.

### Q-EVAL-9 — does `holdout_windows` stay at 32? — **RESOLVED 2026-09-02: 32 STAYS, AND THE PAIRING IS PINNED — WHICH IS WHAT EARNS IT**
`research_continual_memory.md:743-745` warns that the 2σ rule at n=32 will report "HELD (inside the
noise)" for real effects of moderate size, and recommends 128–256 if a null result is going to be
published as a claim. **32 stays — but the reason given here until now is withdrawn.** *"That is the
literal the runs used"* is not a reason this project may give: PLAN's explicit non-goal is that the
new tree will not reproduce `rm-predict`'s numbers and must not be judged on it, and *"agreement with
them would be evidence of a bug faithfully carried forward"*. Three reasons survive, in order of
weight:

1. **THE COMPARISON IS PAIRED, and `EVAL.holdout_probe` now pins it.** Each domain's window starts are
   drawn **once**, from `rng_for("eval.holdout." + domain_name, seed)`, and are identical at every
   probe of the run and across a resume; the 2σ verdict is computed on the **paired per-window
   differences** and the `Reading` carries the paired SD. On the same windows the per-window
   difficulty term **cancels**. Window-to-window bpb spread in text is order 0.3–0.5 b/B; the paired
   difference's spread is far smaller. So **n=32 paired is a materially stronger instrument than n=32
   unpaired**, and the research doc's warning is calibrated for the unpaired case. Nothing pinned this
   before: `holdout_probe` takes an `rng`, and `spine/rng.py`'s `frozen_rng` explicitly does **not**
   cover streams handed out by `rng_for()`, so a stream that advanced between probes would lose the
   pairing **silently** and no check in this tree would see it. H20's repair fixed *which* windows are
   scored (byte coordinates); this fixes that they are the *same* windows.
2. **G2 has not run against a trained system**, so this machine's noise floor is unmeasured and any
   new n would be as arbitrary as the old one.
3. **The dominant error bar is neither.** PLAN 3.8 records a between-seed spread of **0.066–0.131
   b/B**, which exceeds every architectural difference this project has ever claimed. Raising this
   lever tightens the *within-run* term at 8× the cost while leaving the larger term untouched.

**Order of operations, so it cannot be got wrong: pin the pairing (free), then let G2 measure the
floor, then decide n.** The **precondition is now met upstream**: **Q-DATA-6** made DATA draw each
area's held-out block from its own `"data.holdout.<area>"` child rather than from one order-consumed
stream, so adding an area moves neither the held-out **text** nor the windows drawn over it. Both
halves are needed; either alone leaves the add-an-area comparison broken, and that is the one run
goal B rests on. **Caveat, per C11:** 32 × `LM.ctx = 128` ≈ **7.6 kB per domain**, smaller than one
splice segment, against a 506–937-window run. If `DATA.stream_bytes` rises, re-ask this with the
noise floor in hand. **P9: no entry — this number does not move.** No signature moves; no default
changes.


### Q-CKPT-1 — the geometry manifest has one producer and eleven packages — **RESOLVED 2026-09-02: (c), AND (b) IS STRUCK RATHER THAN DEFERRED**
`CKPT.check_geometry` says the manifest is *"assembled by the composition root from each package's
own `geometry()` call"*. `grep '^def geometry' src/*/api.py` returns **exactly one hit**,
`world/api.py:160` — and that one needs a **built** world, which is the thing the gate exists to
refuse before. So the gate cannot be fed the way its own docstring describes.
`_geometry_manifest()` in `compose.py` therefore assembles the pre-allocation manifest from
`LM.resolve`'s `LMGeometry` and the EXACT fields readable off the frozen Configs, and the **grown**
population counts are reported UNCHECKED — which `check_geometry` already specifies as the correct
reading for an absent field, and which is the H22 state made visible rather than hidden. They are
then re-refused in both directions by `WORLD.load_into` (M43) and `FAB.load_state_dict` at their own
rows. **Options:** (a) leave it as written and print the UNCHECKED set; (b) add `geometry()` to the
eight packages that have a shape — a signature-set change, so K1 and this document move with it;
(c) narrow the docstring to the packages that can refuse before allocation.
**Recommendation: (a) now, (b) when the surface next opens.** Whoever writes the assembler must not
silently pass `{}`: an empty manifest makes `check_geometry` a no-op that reports PASS, which is the
untrippable guard the function exists to replace.
**Second half of the same question:** `GeometryField` is a record type **P4 defines**, so the root
cannot construct one today. `_geometry_manifest` returns the four fields as a plain tuple in the
declared order `(value, rule, env_name, why)`. If P4 makes `GeometryField` a namedtuple this
reconstructs; if it makes it something else, this line and that constructor must land together.

**RESOLVED 2026-09-02: (c). NOT (a), AND "(b) WHEN THE SURFACE NEXT OPENS" IS STRUCK.** The false
sentence in `CKPT.check_geometry` is repaired, and the "eleven packages have no producer" framing is
retired rather than managed. No frozen signature moved; no lever, wire, coupling or default moved.

**Why (b) is not a deferred improvement but the wrong shape, which is why it is struck rather than
left standing as an intention.** The manifest's *defining* property is that it exists **before the
first allocation** — that is what lets the gate refuse in seconds instead of after a warm GPU. A
package's `geometry()` can only be called after that package has built something. So the eight or
eleven new functions would either (i) take a `Config` and no object, at which point each one is a
lever read the root already does — eight new entry points on a surface where 94 of 131 are already
stubs, for zero new information — or (ii) need a built object, and then they cannot be called at the
gate at all. And in either case the **EXACT / MAY_WIDEN rule migrates into the package**, while
`ckpt/api.py` says in as many words that **RULES ARE THE OWNER'S**: a package would be grading the
refusal that protects it, which is precisely why `aff_min` and `genuine_min` live in EVAL and not in
the packages they grade. Leaving "(b) when the surface next opens" in the document is an instruction
someone would eventually follow.

**Why (a) is not enough.** (a) leaves `check_geometry` describing a producer that does not and cannot
exist. That is the *described owner, no declaration* family this rebuild exists to end, and it is
load-bearing here: a P4 author who believes the docstring goes looking for eight `geometry()` calls.

**Why the root is the right owner, positively.** It already owns three named cross-package
arithmetics with exactly this justification — `_signature_width` and `_alphabet_size` (*"the
assembly's own arithmetic over two packages' frozen Configs, which is exactly what the root is
for"*) and `_periods` (*"a mapping spanning six packages is exactly the object O10 forbids any one
of them to build"*). The manifest is the same object and belongs in the same place.

**`WORLD.geometry` is NOT dropped, and (c) must not be read as dropping it.** It is the only
`geometry()` in the tree and it is correctly placed: it is the only producer of a field that needs a
built object — `world.n`, the **allocated** predictor count. It sits on the **save** side, where
that object exists. Its `DID IT FIRE` line said it produced *"the manifest `CKPT.check_geometry`
consumes"*; that was corrected the same day under Q-WORLD-8, and §3.9 now states its role as the
**overlay**.

**Three repairs landed with the ruling, and one of them is a wrong measurement, not prose.**

1. `ckpt/api.py` — *"assembled by the composition root from each package's own `geometry()` call"* is
   replaced by what actually assembles it, and by why it could not be assembled the other way.
2. `_geometry_manifest` now **refuses to build without `sysm.geometry`.** Found by running it: `LM`
   declares `layers = 0` as a **sentinel** and `LM.resolve` replaces it with the real depth, while
   the override loop skips a field `LMGeometry` does not carry — so a manifest built before
   `resolve()` records `lm.layers = 0`, the sentinel. A run at `LM_LAYERS=0` and a run at
   `LM_LAYERS=4` are then **the same model recording two different values**, an EXACT mismatch and a
   spurious refusal of a resume that is actually compatible. That is a wrong measurement inside the
   instrument that decides whether a resume happens, it was reachable by writing two calls in the
   wrong order, and nothing said so. It is now a `RuntimeError` naming the ordering.
3. **`fab.cap` joins the manifest** — the tensor extent, `max(n0, slots)`, `MAY_WIDEN`. `fab.slots`
   alone is **not** the extent: `fabric/levers.py` and `fabric/api.py` both say `cap = max(n0,
   slots)` and `A` is allocated `(cap, d_model, rank)`, so at `FAB_N0 > FAB_SLOTS` a resume that
   lowers `n0` narrows every fabric tensor while `fab.slots` compares equal. This is the same class
   as the four fields added on 2026-08-30 and costs the same: one frozen-Config read. It is also the
   exact recorded failure at ISSUES `fix_resume` — *"trained at `FAB_N0=256 FAB_NMAX=1024`; pilot-add
   pins sixteen env vars and neither of those is among them, so the resume built 2048/4096 and died
   inside torch with five tensor shapes and no knob name"* — a run lost with the tokenizer resolved,
   the corpus pulled and the GPU warm. `n0` arrives **folded into the extent** rather than as its own
   field, deliberately: `n0` changing under a fixed `cap` moves `n_live`, which is a `state_dict`
   buffer and not a shape, so recording it raw would refuse resumes that change no tensor. With
   `fab.cap` in, all five names in `FAB.load_state_dict`'s `LEVERS READ` (`slots, n0, rank, dk,
   emb_hid`) have something to compare against.

**The field count is now written in ONE place: nowhere.** It stood at 15, 16 and 20 in three live
statements at once — including a sentence added to *un-stale* the count that was already stale by
four when it landed. The manifest is data; run the function. Prose states the **shape** (one flat,
prefixed map) and the **rules**, which do not drift.

### Q-OPT-4 — `OPT.build(resume=...)` and `OPT.load_state(opt, st, saved)` overlap — **RESOLVED 2026-09-02: (d), WHICH WAS NOT IN THE OPTION LIST. ⚠ A FROZEN SIGNATURE MOVED — `resume` IS GONE FROM `OPT.build` AND `load_state` IS THE WHOLE RESTORE PATH. `param_group_shape` NOW HAS A PRODUCER, SO THE L50 GUARD STOPS BEING UNTRIPPABLE**
`build`'s `RECEIVES:` block explains `run_windows` and **never mentions `resume`** (`opt/api.py:78-82`),
while `load_state` is documented as the restore-or-refuse — it carries the `param_group_shape`
refusal (L50) and the `opt.ckpt.loaded`/`refused` counters, and its refusal needs the **live** groups,
which do not exist until `build` returns. `ASSEMBLY_ORDER` currently has **both**, in that order, and
`compose()` passes the same blob to each. That is deliberate exposure, not a decision.
**Options:** (a) `build(resume=)` restores the *group structure* and `load_state` attaches the moments
and refuses — write that into `build`'s docstring and the overlap disappears; (b) `build(resume=)`
becomes documented dead weight and the root passes `None`; (c) drop `load_state` — which loses the
only refusal on the path. **Recommendation: (a).** It is the reading that makes both rows do work,
and it is the one the `WORLD.load_into`-before-`OPT.build` ordering already implies.
**The same shape, already resolved, in CAP:** `new_valve(restored=)` takes *the lifted cap* because
`Valve.origin` must record where the STARTING cap came from, and `CAP.restore` puts back the two pin
clocks and the high-water marks — the other half of M38. Two rows, two scopes, both stated.

**RESOLVED 2026-09-02 — (d), which was not in the list above. ⚠ LOUD: A FROZEN SIGNATURE MOVED.**
`OPT.build(opt, *, param_groups, run_windows, resume=None)` → `OPT.build(opt, *, param_groups,
run_windows)`. §7 moved in the same edit (K1 compares both directions), and so did the **live call**
in `compose.py` — a keyword argument `build()` no longer accepts is a `TypeError`, not a row-text
edit, and the row text and the call are two different things.

**Why (a) — the contract's own recommendation — is refused: it describes work that does not exist.**
The live param-group structure is fully determined **before** `OPT.build` is called. `compose.py`
records that the module restores run *"STRICTLY BEFORE OPT.build: replaying the grown population
first is what lets the optimizer below be constructed with the SAME param-group structure the
checkpoint has"*, and `param_groups` is then assembled from those already-restored objects plus
`SIG.encoder_parameters`. There is no group structure left for `build(resume=)` to restore; the
checkpoint's influence on group shape arrives through the module restores, not through OPT. Writing
(a) into the docstring would make the contract assert work the assembly order has already done, and
would create a second restore path with **no counters on it** — `opt.ckpt.loaded` and
`opt.ckpt.refused` live on `load_state`, so state would move through one path while the counters
described another. That is the shape Q-MEM-9 names one layer down. (b) is the fallback if a signature
may not move, but then the parameter must be reported as **armed-but-inert**, not described as
restoring anything.

**Against the owner's `NO COMPROMISES` rule and `D4` (*a mechanism kept for future use is KEPT with a
switch, not deleted*), stated rather than assumed:** removing `resume` removes **no capability**,
because there is no capability behind it to keep. `D4` protects mechanisms — a ported arm, a lever
with an unimplemented branch — and `resume=None` is neither: it is a parameter whose only possible
work (restoring the param-group structure) is already done, before this call, by the module restores,
and every byte of the checkpoint it could have seen reaches OPT through `load_state`. Nothing becomes
unreachable, no arm is lost, and no future run can ask for something it can no longer have. **If the
owner reads it the other way, the reversal is one line in each of three places** — `src/opt/api.py`'s
`build` signature, §7's `contract` block, and `spine/compose.py`'s live call — and the parameter comes
back as `(b)`, documented armed-but-inert. That is the shape of the overrule, written down so it does
not have to be re-derived. **The CAP analogue argues for (d), not (a):** `new_valve(restored=)` takes the
lifted cap alone because `Valve.origin` must record where the starting cap came from — a fact the
constructor cannot obtain any other way. `OPT.build` has no equivalent fact.

**AND THE HALF OF THIS QUESTION THAT SHIPS WHICHEVER OPTION IS TAKEN.** `OPT.load_state` REFUSES
when `saved.param_group_shape` differs from the live one — the ISSUES P1-L50 guard, the one thing
standing between a resume and AdamW moments reattached **positionally** to different tensors after
the population grew. `OPT.state_dict` enumerated optimizers, `opt_step`, `n_backward`, `lr_prev`,
`restart_amp`, `cycle_best`, `cycle_index`, the horizon and the counters — and **not**
`param_group_shape`. **The refusal was armed against a value nothing produced**, which is
untrippable, and an untrippable guard reads exactly like a guard that never had to fire.
`param_group_shape` is now declared on `OptState`, written by `state_dict`, and computed in `build()`
from the live groups, which is the only moment the "live" side of the comparison exists. This is the
same defect Q-CKPT-2 records for the geometry manifest and the FAB/SIG sidecars, and it should be
read with them.

### Q-OPT-5 — the horizon is a projection and the epoch length is a measurement — **RESOLVED 2026-09-02: (a), PRINT THE RESIDUAL AND NAME ITS SIGN (UNDER-ANNEAL). NO SIGNATURE, NO LEVER. THE MAGNITUDE IS UNMEASURED AND THE PRINTED LINE IS WHAT MEASURES IT**
`OPT.build` resolves the LR horizon **once**, from `run_windows`; `RunClock.begin_epoch` re-measures
`len(Segmentation.ids) // ctx` **every epoch**, and online minting lengthens tokens and shortens
every later epoch. Both are `units.Windows`, so nothing raises and nothing reconciles them. The
once-resolved horizon is deliberate — the re-projecting machinery it replaces (`_project`/`_lr_total`
/`_proj_lr`, `:6335-6376`) produced the E8 p=0.760 under-annealing — but it is resolved from epoch 0,
before a token has been minted. **Options:** (a) keep the fixed horizon and **print**
`run_windows` against `sum(observed windows_in_epoch)` at the end, so the bias is measured;
(b) let `begin_epoch` revise it, which reintroduces the machinery that already failed twice;
(c) require `opt.lr_wavelength` to be set explicitly. **Recommendation: (a) plus the printed
comparison**, and file the residual as a known bias with a number attached.

**RESOLVED 2026-09-02 — (a), with the comparison specified so it is legal and so its sign is named.
No signature moved, no lever was added, and that is the point: both halves are already declared
surfaces.** The printed comparison is
`derive.opt_steps_from_windows(Windows(observed_total), d_effective_batch_windows)` against
`st.horizon.run_steps` — **both `units.Steps`, so a mismatch is a subtraction and not a `UnitError`**,
and the cross-kind conversion goes through the one named function, satisfying `units.py`'s rule that
there is no implicit path between kinds. The observed side is `RunClock.counters()`'s window total;
the projected side is `OPT.counters`' resolved horizon; **neither package may read the other, so the
composition root joins them in the report**, which is what the root is for and the same shape as
`_periods` and `_n_params`. `RunClock.counters` now says it publishes the observed side;
`OPT.counters` now says it prints the comparison.

**The direction of the bias, which the question left open, is determined and is stated in the tree.**
Minting *merges* bytes into tokens, so `len(Segmentation.ids)` **falls** over the run and every later
epoch is **shorter** than epoch 0. The observed total therefore comes in **below** the projection,
the run ends **before** the cosine completes, and the schedule finishes at a rate **above**
`lr × lr_min_frac`. That is the **same direction** as the E8 `p=0.760` under-annealing the
once-resolved horizon was introduced to kill: the machinery changed and the sign of the residual did
not. **The magnitude is UNMEASURED** — it depends on the mint rate, which nothing in this tree has
run — and the printed line is what measures it. That is the whole reason to print rather than argue.

**(b) is refused twice over.** Structurally, `begin_epoch` would have to write into a horizon
resolved from a frozen `Config` after `build()` returned, which the freeze forbids — or `OptState`
acquires a mutable horizon, and then `load_state`'s *"REPORTS when the horizon changed"* is comparing
against a moving target. Historically, re-projection is `_project`/`_lr_total`/`_proj_lr`
(`:6335-6376`), which produced E8 `p=0.760`, E18 `p=0.730` and the H17 resume defect where
`_ep_start=0` against a checkpointed `step` inflated epoch 0 and latched every later epoch at half
the last. The literature's own remedy for horizon uncertainty is a horizon-free schedule with weight
averaging — a far larger change than this question, and not re-projection.

### Q-MEM-8 — which management cadence does `MEM.judge` run on? — **CADENCE RESOLVED 2026-09-02 (a); SCOPE LEFT MEASURABLE BEHIND A NEW LEVER (⚠ CENSUS AMENDMENT)**
`memory/api.py:253` says *"the management cadence the spine already imposes; no new lever (see FOR
THE OWNER Q-MEM-8)"* — **and Q-MEM-8 did not exist in this document.** It does now. The spine
imposes two: `DOM.manage_every` (100 Windows) and `FAB.manage_every` (500 Windows). `LOOP_ORDER`
places `judge` as an **event on the `dom.manage` pass**, immediately after the plan is applied,
because that is the moment the store's provenance has just been rewritten by folds and deletions —
so it invents no key and reads no foreign period at the call site, the spine delivers the event.
**Options:** (a) the `dom.manage` pass (what is written); (b) `fab.manage`, 5× cheaper; (c) a new
`MEM.judge_every`, which the docstring explicitly forbids. **Recommendation: (a)**, with the cost
noted: `judge` is a forward pass over checked entries and 100 Windows is the shorter of the two.

**⚠ THE PARAGRAPH ABOVE IS STALE IN TWO PLACES AND BOTH WOULD MISLEAD P4.**
*(i)* **`LOOP_ORDER` does NOT place `judge` anywhere.** `MEM.judge` has **no row**; it is in
`DEFERRED_ENTRY_POINTS` for want of the `scorer`, and §3.6 already says so. "(a) — what is written"
was therefore describing a row that does not exist.
*(ii)* **The reason given for (a) does not survive inspection.** `judge` reads `verify`,
`wrong_read`, `wrong_sweep`, `recon_hid`, `recon_tok` and scores `(ctx, tok)` per entry — **nothing
in its inputs is provenance.** A fold relabels `src`; it does not change what the model thinks of a
stored token.

**CADENCE: RESOLVED (a), on the reason that does survive.** When the scorer exists, `judge` is an
`("A", "MEM", "judge", …)` row at the **END** of the `dom.manage` block — after
`MEM.apply_domain_plan` and `DOM.census`, **inside the one `Cadences.due('dom.manage', …)` answer
that block already asks**, never a second `due()` under that key (asking twice *consumes* the fire —
the defect that made minting never fire). No new lever for the cadence, no new key, and **no key is
added to `spine/compose.py`'s `_periods`**. The reason is `census`'s own contract: a `wrong_sweep`
deletion makes the per-source counts stale, `census(reconcile=True)` is the **first** row of this
same pass, so running `judge` last bounds that staleness to **one** cadence interval — and 100
Windows bounds it five times tighter than 500. At the shipped `wrong_sweep=False` nothing is deleted
at all, so the ordering costs nothing today. (b) is refused because it would make `judge` the only
MEM row riding a FAB-keyed answer with no MEM period in sight — the untracked ride `compose.py`'s
`fab.manage` row records for WORLD. (c) is refused by the frozen docstring and by N2. A fourth
option — a `mem.judge` key on the existing `MEM.rekey_period` — is refused because `rekey_every`
already drives two mechanisms and `compose.py` flags that; a third would make re-timing the rekey
silently re-time judging.

**SCOPE: MEASURABLE, NOT DECIDED — and this is where the cost actually lives.** The cadence is nearly
free or 1.7× of the run depending on a choice **no frozen surface makes**: which entries are checked.
`selfcon` is a persistent per-entry field where `-1` means unchecked (`memory.py:79, :492`) while the
flag rule reads every entry with `selfcon >= 0` (`:585-591`), so **two legitimate checked sets exist**:

| arm | what it scores per pass | cost at the shipped defaults | what it costs in *meaning* |
|---|---|---|---|
| **incremental** (`judge_frac = 0.0`) | entries written since the last pass (`selfcon == -1`), ~100 per 100-Window interval | ~100 × `key_win` 8 = **~800 forward tokens** against 100 × `LM.ctx` 128 = 12,800 training tokens ≈ **6% of the interval** | an entry keeps forever the score it got under the model that wrote it, so the adaptive median + k·MAD population **mixes scores taken thousands of windows apart** |
| **full re-score** (`judge_frac = 1.0`) | the whole store, every pass | 8192 × 8 = **65,536 forward tokens** ≈ **1.7× the entire training compute** of that interval (0.34× on the 500-Window cadence) | every score comes from one model snapshot and the median is meaningful; this is the old tree's semantics on a cadence |

Both are compatible with the framework; neither is forced; they differ ~20× in cost **and** in
meaning. So the arms stay reachable and the question is made measurable:

**⚠ `MEM.judge_frac` — A NEW LEVER, AND THEREFORE A CENSUS AMENDMENT. `.rework/CENSUS.md` and
`.rework/census.json` moved with it (the `amendments` group now holds two rows; the census's 328 is
unchanged, because it counts the old `_SPEC`'s knobs and this was never one). There is no ancestor:
the old `selfcheck` (`self_organize.py:4048-4060`) is "single pass, every entry judged", called once
from the report, with no scope knob and no cadence knob anywhere — so there is no `(family,
old_name)` key a `DEPARTURES` entry could use and N2 could only be satisfied by amending.**

**THE DEFAULT IS `0.0` — THE RE-SCORE IS OFF.** Anything between the endpoints is an amortized
sweep: the checked population is covered once per `ceil(1/judge_frac)` passes, taken by
**deterministic stride** from a rotating cursor, never a random draw (the rule `probe_rows` already
carries — a diagnostic that consumes RNG draws changes the training trajectory). Flagging still runs
over the **whole** checked population whatever `judge_frac` is; the lever sizes the re-score, not the
flag. Why `0.0`: there is **no recorded number under either arm** — in the old tree every write reset
`selfcon` to `-1` and the detector was structurally inert for the whole run — so "preserve the
configuration the numbers were taken under" selects nothing. What decides it is that `1.0` would
**more than double the cost of every run by default**, which is itself a confound and a capability
cost, while `0.0` costs nothing and still checks strictly more than the old tree ever managed
in-loop. It is not inert padding: it has a reader (`MEM.judge`), a stated default, a startup domain
(`FRACTION`), and DID IT FIRE counters — `store.n_rescored` and `store.n_judge_cursor_wraps` beside
`n_checked`. `n_rescored == 0` at `0.0` reports **`armed but 0 (judge_frac=0.0, the re-score is
off)`** and never *unreachable*; `n_judge_cursor_wraps == 0` with `judge_frac > 0` says the sweep
never came round, which is a different finding from a sweep that found nothing.

**THE MEASUREMENT THAT RETIRES THIS LEVER.** Two runs of equal length, identical but for
`MEM_JUDGE_FRAC ∈ {0.0, 1.0}`, with `MEM_VERIFY=selfcon` and `MEM_WRONG_READ=1`, ≥2 seeds (§3.8
forbids a verdict on n=1). Report, per run: wall-clock and tokens-forward attributable to `judge`;
`n_checked`, `n_rescored`, `n_flagged`; the **precision of the flag** against
`EVAL.wrongness_probe`'s injected-wrongness Reading; and held-out b/B. The lever retires toward
`1.0` if the flag's precision at `1.0` is materially better than at `0.0` **and** the b/B cost of
the extra compute is inside the between-seed noise floor; it retires toward `0.0` if precision is
indistinguishable. If precision improves but the compute is not affordable, the answer is an
intermediate value and the lever stays — which is the outcome the amortized-sweep form exists to
represent.

**One shape change rides with this and is free today:** the declared callable is
**`scorer(ctx, src) -> logits`**, not `scorer(ctx)`. The path training used runs through
`FAB.forward`, which routes per row on a `domain_id`; a one-argument scorer either routes every
stored entry as one domain or is not the trained path at all (M47). `Store` carries `src` per entry,
so only the *declared shape* was missing. `EVAL.wrongness_probe`'s `scorer` is the same callable and
takes the same two arguments — written once, in `memory/api.py` and in `compose.py`'s deferral
table, because one callable declared twice with two shapes is how the signature width came out 614
on one path and 1 on the other.

### Q-MEM-9 — does `MEM.maintain`'s read probe call `MEM.read`? — **RESOLVED 2026-09-02: (a), CONFIRMED AND FORCED BY THE PARAMETER LISTS**
`maintain`'s job 1 is *"probe_rows real retrievals against probe_contexts"*; `read`'s own docstring
says `promote=False` is *"the read that MUST NOT MOVE THE STORE… the report path uses it"*, which
implies the in-loop probe is `promote=True`. The `B` row states it that way, because if the probe
open-codes a **second** retrieval then `n_reads`, `n_promoted` and the three `wrong_*` counters
describe one path while the store is moved by another — the C8/C9 shape one layer down.
**Ask:** confirm in `maintain`'s docstring that the probe **is** `read(promote=True)`. K6 cannot see
an in-package call, so prose in the row is the only place this can be written down today.

**RESOLVED 2026-09-02: (a). CONFIRMED, AND FORCED — the parameter lists leave one arrangement.**
The decisive evidence is not the sentence the question quotes, it is the two `LEVERS READ:` lists:
`read(mem, store, *, queries, promote=True)` declares `topk, blend_max, match_floor, wrong_read,
verify` — **no key lever and no `key_fn`** — so it cannot encode anything and its `queries` are
**already key-space vectors**; while `maintain(mem, store, *, now, key_fn, probe_contexts=None,
resegment=None)` holds the encoder *and* all three key levers (`key_src`, `key_depth`, `key_win`).
So the probe decomposes exactly one way: `maintain` strides `probe_rows` rows out of
`probe_contexts`, narrows to `key_win`, encodes with `key_fn` at `key_depth`, and calls
`read(..., queries=keys, promote=True)`. **There is no second retrieval implementation in this
package.** No signature moves; two docstrings and one deferral reason changed.

**What was added beyond the ask, because P4 needs it:** `read`'s docstring now states that `queries`
are **keys in the store's own key space, not contexts**, and that the narrowing site and the write
path must use the same two levers — otherwise the store is queried in one key space and written in
another, the drift `rekey_every` exists to prevent.
**(b) is refused** for the reason the question gives one layer down: an open-coded second kNN puts
`n_reads`/`n_promoted`/`n_wrong_*` on one path while the store is moved by another (C8/C9), gives
`wrong_read` and `match_floor` a second implementation free to drift, and would let `blend` be
computed from a `Retrieval` MEM did not build — which `blend`'s docstring exists to refuse.
**Legality, checked rather than assumed:** an in-package call is not a cross-package import (O10/K3
untouched), and K6 requires an entry point to be named by a **row** or deferred — `MEM.read` still
has no row, so its deferral stays valid and is **not** stale. That sentence is now written into the
deferral itself so the next reader does not "correct" it.
**And it is inert regardless, in the state that must be reported:** `probe_contexts` has no producer,
so with the default `None` the honest reading is `n_probe_fired` counting the **cadence** with
`n_probe_rows == 0` — **armed-but-0, not unreachable and not silence**, which is `maintain`'s own
rule that a probe which fires and retrieves nothing is a different finding from one that never fires.

### Q-MEM-10 — `MEM.blend` returns probabilities; every scoring hook takes `logits_fn` — **RESOLVED 2026-09-02: (a). THE RECOMMENDATION BELOW, (c), IS OVERRULED. NO EVAL SIGNATURE MOVES.**
`blend(mem, model_probs, retrieval)` is explicit that `model_probs` are **PROBABILITIES, not
logits**, and every EVAL entry point that scores anything takes a `logits_fn` — which
`eval/api.py:26-29` makes a rule (*ONE LOGITS PATH… passed in, never constructed here*), and EVAL
cannot import MEM. So the `R`-stage rows for `read(promote=False)` + `blend` have no legal route to
the thing that scores their output. **Options:** (a) the spine's `logits_fn` closure does
`softmax → read → blend → log`, returning pseudo-logits — cheapest, and it quietly redefines "one
logits path"; (b) a second optional `probs_fn` hook; (c) pass `blend_fn` into the scoring entry
points, the way `DOM.rekey` gets `encode` and `MEM.write` gets `key_fn`. **Recommendation: (c)** —
it matches the callable-passing idiom already in the contract and keeps one logits path *and* one
blend path — but it is a **signature change** to EVAL and is therefore the owner's, not this edit's.
Until it is ruled on, the +0.085 b/B retrieval path has rows and no consumer.

**RESOLVED 2026-09-02: (a). THE RECOMMENDATION ABOVE — (c) — IS OVERRULED, AND NO FROZEN SIGNATURE
MOVES ON EITHER SIDE.** `MEM.blend` keeps `model_probs` as probabilities; `EVAL` keeps `logits_fn`;
`curve_probe`, `holdout_probe`, `generate` and `coherence` are **not** reopened *by this ruling*.
The join is
composition-root work, which is what the composition root is for. (`coherence` was reopened later the
same day by **Q-EVAL-10**, on its own grounds and not for the blend: `sample` → `units_by_domain` +
`encode`. `logits_fn` is untouched there, so this ruling still holds in both directions.)

**Why (c) is refused.** It moves four frozen EVAL `def`s **and** then requires each of the four
bodies to implement `softmax → blend → log` for itself — four copies of the mix **inside the
instrument line**. This project has two recorded instances of exactly that defect, `prompt.py` (C8)
and `cl_bench.py` (C9): the ungated 50/50 mix recomputed at a consumer site. `MEM.blend`'s own
docstring exists to stop it — *"THE ARITHMETIC LIVES IN THIS PACKAGE so the mixing weight never
travels"*. (b), a second `probs_fn` hook, buys nothing (a) does not and grows a second untested code
path in every instrument.

**One fact the question does not carry, and it removes (c)'s only advantage: `log(p)` is not a
"pseudo-logit", it is exact.** `softmax(log p) = p` identically, so temperature, top-k and nucleus
sampling operate correctly on it and cross-entropy over `log p` is exactly the bits/byte of the
blended distribution. Nor can the blend produce `log(0)`: the result is `≥ (1-blend_max)·p_model` and
a softmax is strictly positive, so the guarantee holds **for every `blend_max < 1`**. The single case
needing a clamp is `blend_max == 1.0` with `conf == 1.0`, and that clamp belongs in `MEM.blend`, with
the arithmetic — one named clamp, not an argument against the option.

**Three conditions make (a) a ruling rather than a quiet redefinition:**
1. **One named helper, once.** `_logits_fn(sysm, *, use_memory)` beside `_key_fn` / `_head` /
   `_sig_encode_fn`, and it is the **only** place `softmax → read(promote=False) → blend → log` is
   written anywhere in the tree.
2. **Two closures, two systems, and the reading names which.** `use_memory=False` is the trained
   path; `use_memory=True` is the trained path plus retrieval, which **has never entered training**.
   The `-0.097 → +0.085` b/B price of retrieval *is* the difference between them, so **the pair is
   the deliverable**, not an inconvenience. **`FAB.contribution`'s `baseline_logits_fn` must always
   be the memory-off closure** — `fabric/api.py` makes it load-bearing that the baseline comes from
   the same callable that produced `baseline_loss`, and a memory-on baseline there silently undoes
   the C3/H11 repair.
3. **The rule is rewritten, not stretched.** ONE LOGITS PATH now reads: *one closure per scored
   system, formed in the composition root, passed in, never constructed here; the reading names which
   closure produced it.* A docstring edit in `src/eval/api.py`; **no `def` line changes**.

**WHAT THIS DOES NOT DO, stated so nobody reads it as more than it is.** The `logits_fn` **still has
no producer** and `_logits_fn` is **not written yet** — writing it now would be inventing a producer,
which `compose.py`'s "WHAT IS DELIBERATELY NOT HERE" block exists to refuse. What is settled is the
**shape and the owner**, and that is what had to be settled while the surfaces are cheap. The
residual is named rather than defaulted away: `FAB.forward` needs `signature`, `domain_id`, `novelty`
and `live_domains` per row; for a held-out window the closure can encode the signature itself with
`_sig_encode_fn` and supply `training=False` and DOM's live count, and **`novelty` is the one datum
with no honest source off the training path**. For a *stored* entry the domain id is `Store.src` —
which is why the declared callable is **`scorer(ctx, src) -> logits`** (see Q-MEM-8), one arity,
written once.

**Consequence for the EVAL slice, since two agents could otherwise decide this differently:** because
(c) is overruled, **Q-EVAL-10 is the only other question that reopens EVAL's frozen surface.** They
do not have to land in one edit. *(This sentence named the change as a `sample` → `seed_units`
**rename** until 2026-09-03. It is neither. Q-EVAL-10 ruled `coherence(ev, *, logits_fn, sample,
rng)` → `coherence(ev, *, logits_fn, units_by_domain, encode, rng)` — one parameter replaced by
**two**, under a different name — and Q-EVAL-10's own section below **refuses** `seed_units` by
name, because the per-domain keys are load-bearing and `seed_units` would throw the labels away. Two statements in one document naming two different signatures for one entry point is
the C12 shape; the ruling wins, and this sentence now points at it instead of restating it.)*

**Literature bore, narrowly.** kNN-LM (Khandelwal et al., ICLR 2020) interpolates **in probability
space** — `p = (1-λ)·p_LM + λ·p_kNN` — and reports the perplexity of that mixture, i.e. it takes the
log of the interpolated distribution and scores it. So `MEM.blend`'s probability-space signature is
the standard formulation and option (a) is what the field already does. The literature does **not**
bear on where the join lives in this tree; that is settled by O10 and by the C8/C9 record.

### Q-TOK-10 — `TOK.save_vocabulary` takes no suffix, so M46 is not closed — **RESOLVED 2026-09-02: (b), OVERRULING THIS DOCUMENT'S OWN RECOMMENDATION (a). ⚠ A FROZEN SIGNATURE MOVED: `save_vocabulary(tok, vocab, *, suffix="")`**
`CKPT.save` has a `suffix` and says *"THE SUFFIX APPLIES TO THE WHOLE SNAPSHOT"*;
`save_vocabulary(tok, vocab)` has **no suffix parameter** and writes `d_vocab_save_path`, a string
frozen at `build()`. So a `reason="bestN"` save writes `runs/x.best3/ckpt.pt` **and** overwrites the
base `runs/x.dyntok.json` — which is `ck = ck + suffix` against a base tokenizer path, i.e. M46
exactly. `ckpt/api.py:91-92` names the escape — *"the tokenizer bytes go in `payload`"* — but
`TOK.vocab_state` says it carries *"everything a resume needs **that the merge list alone does not
carry**"*, i.e. explicitly not the merges. **Two frozen docstrings disagree about where a snapshot's
vocabulary lives.** **Options:** (a) merges travel in `payload["TOK"]` and `save_vocabulary` becomes
a human-readable sidecar at the base path — no signature moves, and it is what `ckpt/api.py:91-92`
already says; (b) add `suffix` to `save_vocabulary` — a signature change; (c) refuse `best_keep > 0`
with `tok.mode == "online"` at startup. **Recommendation: (a)**, which needs one sentence added to
`vocab_state`'s docstring and no signature edit. Not taken here: it is a decision, not a repair.

**RESOLVED 2026-09-02 — (b). A FROZEN SIGNATURE MOVED: `TOK.save_vocabulary(tok, vocab, *,
suffix="")`.** §7 and `src/tok/api.py` moved in this same edit; K1 compares both directions.

**Why not (a), which this document recommended.** The framework rule decides it: the suffix is
chosen **at runtime** by the retention policy (`BestAction`), and a coupling's compute sees only
frozen `Config`s — so `d_vocab_save_path` structurally *cannot* carry it, and a runtime value reaches
a package as an **argument**. That is the same rule that made `bytes_per_token` an argument to
`data_plan` and `curve_bpb` an argument to `Retention.consider`. (a) is also the larger change, not
the smaller one: `build_vocabulary`'s merge source is the **file** (`tok/api.py:50-56`) and the
payload is not one of its arguments, so (a) costs either a *second* signature change
(`build_vocabulary` gains `saved=`) or re-chartering `restore_vocab` from *refuse on mismatch* to
*install the match table* — throwing away a full corpus build and leaving `bytes_per_token` measured
on a vocabulary that was then replaced — and it strands `d_vocab_read_path`, half of a promote the
census made on purpose. (c) was refused outright: it forbids best-checkpoint retention on exactly the
`mode="online"` arm goal B's headline runs use, which is a capability removed to avoid a repair.

**It is worse than the overwrite this section describes, and (b) closes that half for free.**
Resuming from a best snapshot sets `CKPT.resume` to that snapshot's base, so `d_vocab_read_path`
resolves to `<base>.best3.dyntok.json` — **a file nothing ever wrote**. `build_vocabulary` then falls
through to *"Otherwise: build"*, and the restored embedding table is indexed by a freshly minted,
different vocabulary. **The best-snapshot resume path could not work at all.** With the suffix, the
write produces exactly the file the unchanged read coupling looks for.

**Where the `.dyntok.json` tail now lives, stated so it cannot drift silently:** the two couplings in
`spine/assemble.py` (which already name it once per direction) and the splice in `save_vocabulary`.
Splicing *generically* — before the last dot, or via `splitext` — is **not** equivalent and must not
be written: the tail has two dots, so `splitext` yields `<base>.dyntok.best3.json` while the read side
looks for `<base>.best3.dyntok.json`. The considered alternative — couplings carry `CKPT.dir` /
`CKPT.resume` as bare bases and TOK owns the extension — gives the rule one home but leaves two wires
named `..._path` carrying something that is not a path, and changes both wires' resolved values and
the hand-computed fixtures that pin them. Not taken; recorded so the next reader need not re-derive
it. **`ckpt/api.py`'s *"the tokenizer bytes go in `payload`"* is corrected in the same edit** — that
was the second half of the two-frozen-docstrings disagreement. **A third copy of it survived the
repair and is fixed 2026-09-03:** `save_vocabulary`'s own paragraph pricing the refused option (a)
said moving the merges into `payload` *"would make the snapshot self-contained (which
`ckpt/api.py:96-99` **already claims**)"* — present tense, pointing at the very sentence this same
ruling had just reversed. The disagreement it describes is now history, not a live conflict between
two frozen surfaces, and the text says so.

**Honest priority:** this closes a defect that cannot *fire* until `CKPT.Retention.consider` lands at
P5 (it is deferred, and `Saves.best` can never be non-zero today). It is done now because a frozen
signature costs one line now and a coordinated ten-agent edit later.

### Q-TOK-11 — `residual_ratio` is sourced at mint time, when it is zero by construction — **RESOLVED 2026-09-02: (a) NOW, WITH (c) PERMANENTLY ALONGSIDE. ⚠ THE FROZEN SET GREW 121 → 122 (`LM.residual_ratios`)**
`judge_probation`'s `embed` arm keeps a token iff `earned AND residual_ratio[t] >=
probation_residual`. `tok/api.py:232-234` sources `residual_ratio` from LM's `MintReport`, produced by
`LM.on_mint` **at the moment the row is created**, when the free residual *starts at zero* — so the
arm would retire 100% of candidates. The old tree recomputes it at judgement time from
`model.compose.table()` and `.delta` (`:7601-7605`), which is the right measurement: *how much this
token had to become that its parts did not already say* is a question about training that has
happened. **No entry point among the 121 exposes that read.** **Options:** (a) add
`LM.residual_ratios(lm, model)`, a pure read — a signature-set change; (b) cache the last
`MintReport` — this is the bug; (c) leave `residual_ratio=None` and let the declared Gate print
*unreachable (no residual_ratio supplied)*. **Recommendation: (a)** when the surface opens, (c)
until then — and (c) must be printed, because M41 is the record of what happens when the embed arm
silently runs the `use` test while the banner says `embed`.

**RESOLVED 2026-09-02 — (a) NOW, with (c) permanently alongside. LOUD: THE FROZEN SET GREW,
121 → 122.** `LM: residual_ratios(lm: Config, model)` is in §7, in `src/lm/api.py`, and on a **`B`
row immediately before `TOK.judge_probation`**. `docs/04_CONTRACT.md`'s §0 refused-wires row for
`d_residual_ratio` moved in the same edit, because it named the old route and two frozen documents
naming two different producers is the defect this ruling repairs.

**Why now rather than "when the surface opens": the surface is open.** 94 of 131 entry points are
stubs and LM's bodies are unwritten, so this cost one stub, one §7 line and one row. After P4 it costs
a coordinated edit across ten independent agents. And it is **not new machinery** — `LM.anchor_term`
already computes ‖delta‖/‖composite‖ every flush; what was missing was an entry point that *returns*
the read, and none of the other ten does (`counters` returns `{name: int}`, not a per-token vector).

**The row carries `judge_probation`'s own `Due.probation` gate**, stated on the row. Without it a
per-token norm over the whole vocabulary would run **every flush** for a consumer on a 5000-window
cadence — an instrument computed thousands of times and discarded.

**(c) is required alongside, not instead.** At `lm.compose = False` there is no composer and the call
returns `None`; TOK's Gate must then print *unreachable (no residual_ratio supplied)* rather than
silently running the `use` test, which is ISSUES P1-M41 exactly.

**Default unchanged and worth stating: `TOK_PROBATION_USES = 0`, so the whole probation family is
inert as shipped** — this makes the `embed` arm *correct when switched on* rather than wrong by
construction.

**⚠ THE RULING'S BLAST RADIUS, FINISHED 2026-09-03 — four live statements were still telling the next
author to declare the wire.** `residual_ratio` can never be a `Coupling`: a `compute` sees only frozen
`Config`s and this is a read off a live tensor after `build()` freezes, which is why §0's refused-wires
table carries the row. `src/tok/levers.py` said the opposite in four places — the DELIBERATELY ABSENT
table (`d_residual_ratio … NOT YET IN THE LEDGER`), the paragraph under it (*"no such Coupling exists
in `assemble.COUPLINGS` today. Until it does…"*), the `probation_by` comment (*"the wire that arm needs
is not in the ledger yet"*) and `probation_residual`'s own comment (*"arrives as the wire
`d_residual_ratio` from LM"*). All four now name the **argument** and its producer instead. The
warning those paragraphs carried is kept, because it is still true and is answered by the Gate rather
than by a wire: at `probation_by="embed"` with `lm.compose = 0` the call returns `None`, and the arm
must print *unreachable* rather than run the `use` test (M41).

**THE FIFTH COPY IS THE OWNER'S AND IS DELIBERATELY NOT EDITED.** `TOK_PROBATION_MIN`'s census reason
— `.rework/CENSUS.md`, the `tokenizer` family, and the same string in `.rework/census.json` — still
reads *"The ratio itself is computed from model.compose and so arrives as the wire `d_residual_ratio`
from LM"*. The census is the record of what the old tree's knobs **were** and of the verdict passed on
each; the routing sentence inside a reason is this rebuild's business and this ruling overrules it.
Rewriting a census reason is a census amendment in everything but name, `tests/test_census.py` N3 keys
`DEPARTURES` on `(family, old_name)` and not on reason text, and no check reads the sentence. **The
conflict is recorded here rather than resolved silently**: if the owner wants the ledger to match, the
one-line edit is to that reason, and it changes no identity, no verdict and no default.

**⚠ THE WARNING THIS SECTION CARRIED TO Q-LM-12, AND WHAT CAME OF IT.** This ruling was written not
knowing that Q-LM-12 (`obs_emb`) was, in another slice on the same day, preparing to add an `LM`
entry point of its own and to write "121 → 122" for it. It left a warning here. **Q-LM-12 was ruled
(b) and `LM.embed` landed, so the set is 123, not 122** — the two additions are counted once, in §7's
header, which is the only place the number is normative. Nothing about *this* ruling changed; what
would have gone wrong is the count, and it did not. The mechanism that saved it is the one to keep:
**the count lives in one place and every other mention points at it**, which is why §7's header now
says so in as many words.

### Q-SIG-1 — `prototype_frac` has no supplier and is therefore structurally unreachable — **RESOLVED 2026-09-02: (c), WHICH THE SIGNATURE ALREADY SPECIFIED; THE LIVE DEFECT WAS AN ILLEGAL WIRE IN TWO COMMENTS**
`SIG.train_step`'s `reservoir` is documented as *"a list of (window, window) pairs drawn from ONE
domain's reservoir by DOM"*, and **no DOM entry point returns reservoir windows** — DOM has ten entry
points and `DOM.census` returns radii, counts, `comp_glob` and `collapsed_at`. **(c) is not merely
recommended, it is what the tree already says**: `reservoir=None` is a defaulted keyword, the
`LOOP_ORDER` row supplies `stream`, `seen_units` and `opt` and nothing else, and `sig/api.py` already
declares that `sig.prototype_pairs` reading zero with `prototype_frac > 0` means DOM supplied no
reservoir. (b) is refused for the reason given *plus* a second: `DOM.census` is consumed by FAB, MEM
and the report, so widening it to carry sample windows makes a **training input** out of an
instrument payload, and pairs up to 100 windows stale still *look* like pairs — the arm would report
as firing while training the encoder on a partition that has since moved. (d), the root slicing
`part.reservoir` itself, is refused by **O10**, with the precedent written one question over for
`FAB.contribution`'s `candidates`.

**So the live half of this question was never the ruling — it was two comments, and they are now
corrected.** `sig/levers.py` named **`d_prototype_reservoir`** among "the port's remaining work" and
said *"under L2 the reservoir arrives as `d_prototype_reservoir`"*. **It cannot exist in any form**: a
`Coupling.compute` sees only frozen Configs and a reservoir is a list of stream windows the loop
assigned at runtime — the same class the `("encoder","SIG_WIN")` departure refuses
`d_signature_width_bytes` for, one step further out. The refused-wires table above has said so; the
two comments went on naming it, and this contract calls `grep -rn d_ src/` a **complete** coupling
index, so they were putting a non-coupling into it. They survived because O4 and K5 are AST checks
over *code* and a `d_` name in a comment is invisible to both. Both are rewritten to say the
reservoir arrives as an **argument** and that the supplier, if it lands, is
`DOM.reservoir_pairs(dom, part, *, did, n, rng)` drawing from **DOM's own named stream**.

**Two things stated so they are not re-litigated.** The lever is **not dropped**: `sig/levers.py`'s
group header diagnoses that the positive radius is shorter than a splice segment, so the encoder is
explicitly taught that two distant windows of the same corpus differ and *more* encoder training
makes domain identity *worse* — `prototype_frac` is the only declared remedy for that, and SIG is the
router's only input. And **K4 counts a docstring mention as a reader**, so this lever passes K4 as
consumed while being structurally unreachable; `sig/api.py` now requires the counter to read
`unreachable (no DOM supplier)` and never "armed but 0". The three *other* `d_` fields
`sig/levers.py:66` names (`d_signature_width_bytes`, `d_positive_radius_bytes`, `d_last_boundary`)
are legitimate build-time couplings that are still undeclared; **no question owns them**, and whoever
takes the SIG wiring should take all three together.

### Q-OPT-6 — does `OPT.maybe_step` step the ENCODER optimizer? — **RESOLVED 2026-09-02: NO — (a). IT WRITES `lr` TO BOTH AND STEPS `base` ONLY; SIG OWNS THE ENCODER STEP. NO SIGNATURE MOVED. ONE DECISION WITH Q-OPT-7, WHICH SUPPLIES THE WORD `encoder` THIS ANSWER NEEDS**
`maybe_step` step 5 says *"write `lr` into EVERY param group of BOTH optimizers, then step and
zero_grad both."* **The run of record does not do that.** `self_organize.py:7153-7154` writes the
rate into `om` *and* `oe`; `:7287` steps **`om` alone**; `grep "oe.step"` over 9,859 lines returns
exactly one hit, `:3401`, inside `contrastive_step` — SIG's own step. Two consequences, and the
first is live **today**: with no `SIG.train_step` row the encoder's gradients were structurally
zero, and an AdamW step on zero gradients is not a no-op — decoupled weight decay multiplies the
parameters by `(1 - lr·wd)` every due flush. The second arrives **with** the row now written: the
encoder would be stepped by `train_step` on its Windows cadence **and again** by `maybe_step` on the
flush cadence, and SIG's loss floor — which is designed to gate the STEP, not the loss — would stop
gating anything. **Options:** (a) `maybe_step` writes `lr` to both and steps **`base` only**; SIG
owns the encoder step; (b) `maybe_step` steps both and `SIG.train_step` only computes and backwards
— which makes `train_every`, `train_every_idle` and `dense_window` dead levers.
**Recommendation: (a)** — it is what was measured and it preserves three declared levers and one
measured mechanism. It is a one-clause docstring edit to a frozen surface's **prose**, and it is not
made here: an exception to the freeze is the orchestrator's call. Note that under (a)
`opt.lr.writes == opt.step` must be reworded, because the encoder then gets an `lr` write and no step.

**RESOLVED 2026-09-02 — (a), and it is now written into `maybe_step` step 5 and into the
`SIG.train_step` row. No signature moved.** The measurement is tighter than the question states:
`grep -n "oe\." self_organize.py` returns **exactly two lines in 9,859** — `:5372`
(`oe.state_dict()` into the checkpoint) and `:7154` (`for _g in oe.param_groups: _g["lr"] = _lrv`).
There is **no `oe.step()` and no `oe.zero_grad()` anywhere**; `:7287` is `om.step(); om.zero_grad()`,
the base optimizer alone; the encoder is stepped only inside `contrastive_step` (`:3401`), which
receives `oe` at `:5024` (warm-up) and `:6649` (the loop). SIG owned the encoder step in the run of
record, and step 5's *"step and zero_grad both"* described something that never happened.

**One of the two consequences the question lists is now dead, and the other is live because of the
repair.** *"With no `SIG.train_step` row the encoder's gradients were structurally zero"* — that row
now exists, stage `A`, event-driven on `cadence_due`, and its own text ends *"WITHOUT THIS ROW the
run routes every window through a randomly initialised encoder while an AdamW steps it on zero
gradients."* The reviewer's finding was repaired. The **second** consequence is created by that
repair: under step 5 as written the encoder would be stepped by `SIG.train_step` on its Windows
cadence **and again** by `maybe_step` on the flush cadence.

**One correction to the stated harm, because the report tells the operator to trip it.** *"An AdamW
step on zero gradients is not a no-op — decoupled weight decay multiplies the parameters by
`(1 - lr·wd)`"* is true in general and **inert at the shipped default**: `weight_decay = 0.0`, so
with zero gradients the moments stay zero and the step genuinely is a no-op. The erasure is real only
at `weight_decay > 0` — which the report at `:7990` instructs the operator to set.

**What (b) would destroy, verified in the old source.** `contrastive_step` returns **before touching
the optimizer** when the InfoNCE loss is at the floor (`:3399-3401`), and `sig/api.py` restates it as
*"the step is SKIPPED (loss returned, opt untouched)"*. **The floor gates the step, not the loss** —
if `maybe_step` steps the encoder, the floor gates nothing. And `sig.train_every`,
`sig.train_every_idle` and `sig.dense_window`, plus the `SIG.d_idle_cadence` wire computed from two
of them, become armed-but-inert **by construction**, because a package's cadence lever is only
meaningful if that package's mechanism fires on it.

**What changed, exactly.** `maybe_step` step 5 now reads: write `lr` into every param group of both
optimizers, then read the gradient norm, clip if asked, and step and `zero_grad` **the base
optimizer**; the encoder is stepped by SIG on SIG's cadence. `opt.lr.writes` split into
`opt.lr.writes.base` and `opt.lr.writes.encoder`, each of which must equal `opt.step` — the single
counter could not distinguish a missing encoder write from a missing step. **And a regression counter
was added: `opt.encoder_steps_here`, which MUST BE 0.** Without it the double step can come back
silently, because both call sites look correct in isolation. `src/sig/` needed no edit; its
docstrings were already written for (a).

### Q-OPT-7 — `OptState` declares "both AdamW instances" and names neither — **RESOLVED 2026-09-02: (a). THEY ARE `base` AND `encoder`, `build`'s OWN `param_groups` KEYS. NO SIGNATURE MOVED, AND K11 MAKES `encoder` A CHECKABLE `produces` TOKEN. THIS UNBLOCKED TWO CONSUMERS, NOT ONE**
`SIG.warm_up` and `SIG.train_step` both document their `opt` parameter as **THE ENCODER OPTIMIZER,
BUILT BY OPT AND HANDED IN** — and the hander is the composition root, which holds only the
`OptState` that `OPT.build` returned. `opt/api.py:29-31` describes that record as *"both AdamW
instances, n_backward, opt_step, lr_prev, restart_amp, cycle_best, cycle_index, horizon, counters"*
and gives the two instances **no field names**, so there is no legal expression for "the encoder
one". `compose()` therefore passes the whole `OptState`, which means SIG is currently handed an
object through which it could step the language model. **Options:** (a) name the two fields in the
`RECORD TYPES` block — `base` and `encoder`, matching `build`'s own `param_groups` keys — which is a
documentation edit, not a signature change; (b) add an accessor entry point, which *is* a signature
change; (c) leave it and accept the boundary hole. **Recommendation: (a).** It is one line and it is
the only option that lets `sig/api.py`'s own sentence be true.

**RESOLVED 2026-09-02 — (a). One vocabulary, four places, and no signature moved.** `OptState` now
declares `base` (the AdamW over `param_groups["base"]`) and `encoder` (the AdamW over
`param_groups["encoder"]`) — the same two words as `build`'s own keys. The `OPT.build` row's
`produces` column hands over `opt.base` and `opt.encoder` rather than the whole state; the real
`SIG.warm_up` call passes `sysm.optimizer.encoder`; and the `SIG.train_step` row says the same.

**It was not a latent hole — it was written down as a known hole in three places**, and one of them
was a whole deferred entry point. `compose.py`'s `OPT.build` row said SIG *"is left to guess which
optimizer it may drive — Q-OPT-7"*; the real call said the same and added *"recorded as Q-OPT-7
rather than closed by guessing a field name"*; and the `WORLD.manage` deferral said `add_param_group`
*"is OPT's `optimizer.add_param_group` as a callable, and `OptState` is declared as 'both AdamW
instances' and NAMES NEITHER, so the root cannot address one without guessing a field — the identical
hole recorded for SIG.warm_up as Q-OPT-7, **and one field on OptState closes both**."* So there were
**two** blocked consumers, not one.

**The payoff is enforcement, not clarity, and that is why (a) beats (b).** K11 resolves a `produces`
token by requiring it to appear in the entry point's docstring **or its module docstring — "which is
where every package declares its RECORD TYPES RETURNED"**. Naming `base` and `encoder` there makes
`encoder` a **checkable** provenance token, so the `OPT.build` row can hand SIG the encoder and
K10/K11 police it. (b) would add an entry point and K6 would then require a row or a deferral for it,
buying nothing (a) does not.

**`WORLD.manage`'s deferral was amended in the same edit, as K12 requires.** Half its reason is now
closed: the expression the root would write is `sysm.optimizer.base.add_param_group`, and the guess
is gone. What still has no producer is the **row** — `WORLD.manage` has no `ASSEMBLY_ORDER` or
`LOOP_ORDER` position, so nothing in the assembly hands the callable to WORLD. The deferral says
that, and it also records the ruling the field names make expressible: a mid-run world parameter
joins the **base** group, because putting it in the encoder group would put it under SIG's cadence.

### Q-FAB-6 — nothing can tell the fabric a shift was self-inflicted — **RESOLVED 2026-09-02: (a), ON `grow_check` AND NOT ON `manage`. ⚠ A FROZEN SIGNATURE MOVED**
At an epoch roll, at a retok and at an **LR restart** the old tree calls `fabgrow.note_shift(step)`
(`:6515`, `:7787`, `:7120`) to open a growth blackout, so the loss jump *we caused* does not read as
a distribution the fabric must grow into. No FAB entry point accepted it. **(a) is adopted, with one
correction to where it lands:** the question proposed the keyword on `FAB.manage`; in the old tree the
blackout gates **growth**, not selection — `note_shift` sets `blackout` at `:2948` and **two of its
three consumers** are `:3004` (`if unexpected and t - s.blackout >= s.cool`) and `:3012` (`if
t - s.last < s.cool or t - s.blackout < s.cool: return 0`), both inside `PlateauGrowth.step`, which
in this rebuild is `FAB.grow_check`. `manage` is cull-and-spare and has no cooldown to suppress, so
the keyword would have been unreachable there. **Deciding the wrong entry point costs as much as not
deciding.**

**⚠ "ONLY TWO" WAS WRONG, AND IT WAS WRONG IN FOUR PLACES — corrected 2026-09-03 without moving the
ruling.** `self_organize.py:7397` is a **third** consumer and it sits at the **loop call site**, not
inside `PlateauGrowth.step`: `_blackout = fabgrow is not None and (step - fabgrow.blackout) <
fabgrow.cool`, guarding the `GROW_CAP` capacity valve two lines below. This document said "only two"
here and at §2's `FAB` entry, and `src/fabric/api.py` and `src/fabric/levers.py` said it too. It
changes nothing about **where the keyword lands** — both consumers that decide *growth* are in
`grow_check`, and `manage` still has no cooldown — but it changes what the sentence *proves*: the
old tree read one blackout in **two** places, and the rebuild therefore needs the state in two
places as well. It has it: `FAB.grow_check` applies its own `cooldown` to `step_windows - shift_at`,
and the resulting state rides out on `GrowReport` for the root to join into `CAP.observe`'s
`blackout` boolean — which is exactly the route `ROW_ARGUMENTS_ELSEWHERE["CAP.observe"]` already
named, and the reason CAP mints no blackout-window lever of its own. A sentence that undercounted
the consumers was one sentence away from justifying a second, independent blackout in CAP.

**⚠ THE SIGNATURE:** `FAB.grow_check(fab, pop, *, flush_loss, step_windows, soft_cap,
memory_pressure, signature, shift_at=None)`. Made **now** because 94 of the 131 entry points are stubs
and the same change after P4 has written the WATCH→BURST→RECOVER machine is a body rewrite. The
```contract block, the `compose.py` row and `System.__slots__` moved in the same edit.

**Four things the ruling turns on.** (1) **The threshold stays in the package that declares it**: the
root supplies only the *stamp* and FAB applies its own `cooldown` — the same rule `FAB.manage_period`
exists to enforce. A boolean instead would force the caller to apply FAB's `cooldown`, a foreign
lever read at a call site that `grep -rn d_` could never index, which is why **(b) is not a separate
option**: `grow_check` has no `blackout` parameter to reuse, so (b) *is* (a) with a worse carrier.
(2) **It can never be a wire.** The shift step is measured at runtime and a `Coupling.compute` sees
only frozen Configs; the refused-wires table already says exactly this for OPT's `d_shift_at`.
(3) **Two clocks for one event, on purpose.** OPT's `shift_at` is `units.Steps` (`clock.opt_steps`);
FAB's `cooldown`, `warmup` and `recover_min/max` are `units.Windows` and `grow_check` takes
`step_windows` — so the root stamps `units.Windows(clock.step)` on `System.shift_at_windows`, and
handing OPT's object to FAB raises `UnitError` instead of being `batch_windows`-fold wrong.
(4) **A defaulted argument is invisible to K10** — `compose.py` records that hole for `MEM.judge` —
so it carries the counter OPT already has for the same hazard: **`fab.shift_notifications`** (0 means
nobody is supplying it, and the blackout is **unreachable**, not armed) beside
`fab.growth_blackout_suppressed`, split by leg so a suppressed regression is not filed under a
suppressed stall.

**(c) is what the tree does today and its cost is on the record**: the epoch resample and the retok
are the two largest loss jumps a run produces and `z = 4.0` MAD-deviations above the slow EMA is
exactly how they read, so growth would spend the cap on artefacts we caused and then decline the
next, real regression. `capacity/api.py` records the identical loop on the CAP side —
*"the 0.75 GB run walked 2048 → 8192 in 19 lifts that way"*.

**CAP's half is answered from here without minting anything.** `CAP.observe` takes a `blackout`
**boolean** and CAP declares no blackout-window lever (its seven are `targets, fab_start,
vocab_start, lift, lift_min, pin_windows, stall_band`); in the old tree the boolean was
`(step - fabgrow.blackout) < fabgrow.cool` (`:7397`), i.e. **computed from FAB's `cooldown`**.
`GrowReport` now carries the blackout state, so the root joins a value FAB computed with FAB's own
lever — which is exactly the route `ROW_ARGUMENTS_ELSEWHERE["CAP.observe"]` already named (*"one
field on GrowReport and one root join"*). Naming it in one place is what stops it being chosen twice,
differently. **What is still open and is NOT this question's to close:** `CAP.observe` stays deferred
for `improving` and `observations`, and the root join itself is unwritten.

### Q-CKPT-2 — what does the SAVE side write for the geometry gate, and who emits FAB's sidecar? — **FIRST HALF RESOLVED 2026-08-30; the residue is narrower and is HIGH, not blocking**

**The first half was already answered in the tree, by the declaration a check reads.**
`ROW_ARGUMENTS_ELSEWHERE["CKPT.save"]` says `geometry` **is** `_geometry_manifest(sysm)` — the same
function the child calls on the way back in — so the recorded key set is byte-identical to the live
one and `check_geometry`'s missing-field set is empty by construction. K10 reads that table in both
directions, so the entry is live and normative.

Six other statements in `compose.py` and this document said the save side records `WORLD.geometry`
alone, and **ISSUES P1-C12 was filed against those** — a critical defect asserted against a claim the
same file had already refuted. C12 is withdrawn as filed and the record is kept there. *Where a
declaration and a comment disagree, the declaration is what runs.*

**Every one of the manifest's fields is a pure function of the frozen Configs** — enumerated, all of
them, with no exception. So there is no collection problem: nothing has to be gathered from packages
on the save side, because the save side can compute the same manifest the child will. That is the
option the question's own framing missed by asking *"what does the save side write"* rather than
*"does the save side need to write anything the child cannot recompute"*.

**What the question actually surfaced, and it is worth more than the original.** The gate compared
twelve dimensions and **not one field that decides which tensors exist**: `lm.arch` (gru against
transformer — two different modules producing an identical manifest at the same numbers),
`lm.compose` (when True, `emb` and `head` are **not constructed at all**, so the parameter *set*
changes and no shape comparison can see it), `sig.mode` (a trained encoder against a frozen
hashed-bigram modulus), and `fab.emb_hid` (a real tensor dimension compared *only* against the
sidecar, which is `None` on every resume). All four are frozen-Config reads and cost nothing. Added.
(`fab.cap` joined them on 2026-09-02 under **Q-CKPT-1** — `max(n0, slots)` is the tensor extent and
`fab.slots` alone is not.) **The field count is deliberately not written here**: it stood at 15, 16
and 20 in three live statements at once. Run `_geometry_manifest`.

**The residue, still open, HIGH rather than critical:**

1. **The two sidecars have no producer.** `_sidecar` reads `Snapshot.geometry[PREFIX]` and nothing
   writes a per-prefix key, so SIG's refusal (on `width_units`, `alphabet_size`, `space`, `d`,
   `mode`) and FAB's (on `slots`, `rank`, `dk`) are **disarmed on every resume** — and
   `FAB.state_dict` does not even claim to emit a sidecar, so that one reads a value with no declared
   origin at either end. Now that four of those fields are in the manifest itself, **the question is
   whether the sidecars are still needed at all**, or whether the manifest subsumes them and the two
   `sidecar` parameters should go. That is a frozen-signature decision and is cheap now.
2. **WORLD's grown population count is the one quantity that genuinely needs a live object**, so it
   cannot join the manifest — `_geometry_manifest` is computed before any package is built, which is
   the point of it. It is re-refused by `WORLD.load_into` (M43) at its own row, and whether that is
   sufficient is the remaining question.

**For the owner:** (1) is a straight yes/no on whether the sidecars survive, and the answer changes
two frozen signatures. (2) needs no decision unless you want the grown counts checked at the gate
rather than at the row.

### Q-EVAL-10 — `EVAL.coherence` takes a `sample` and its docstring says it draws its own — **RESOLVED 2026-09-02: A FROZEN SIGNATURE MOVES**
`coherence(ev, *, logits_fn, sample, rng)`, while `eval/api.py:162-168` says it runs "over its OWN
seeded sample, not over the printed generations" and that `coh_seeds` and `coh_len` size a sample
**it draws for itself**. Both cannot be true. This matters beyond tidiness: the recorded failure is
that coherence was scored on the four printed generation samples, ~2 windows each, so every number
landed on 0.25/0.50/0.75/1.00 and "memory HELPS (0.50 → 0.75)" was **one sample flipping**, reported
as a finding twice in opposite directions. **Options:** (a) drop the parameter — the instrument owns
its draw, which is what the docstring argues for; (b) keep it and delete the sentence, making the
caller responsible for a seeded draw of `coh_seeds` × `coh_len`; (c) keep both with the parameter
documented as an override for A/B work. **Recommendation: (a)**, because the parameter is what
allowed the old code to hand it the generation samples in the first place. Note the deferral reason
written here until 2026-08-30 — "no entry point in the tree returns a Sample today" — was simply
**false**: `EVAL.generate` returns one. The real blocker is `logits_fn`.

**RESOLVED 2026-09-02: (a) IN SUBSTANCE, AND A FROZEN SIGNATURE MOVES.**
`coherence(ev, *, logits_fn, sample, rng)` → **`coherence(ev, *, logits_fn, units_by_domain, encode,
rng)`**. The docstring and the levers win over the signature; the instrument owns its draw.

**Why literal (a) — "drop the parameter" — is not writable.** With `sample` gone the function has a
model, a random stream and **no material**. `coh_seeds` counts *seed passages*, which come from the
corpus; EVAL may not import DATA or TOK, and no entry point in the tree produces a `coh_seeds ×
coh_len` sample (`EVAL.generate` is sized by `gen_samples × gen_domains × gen_len`). So a parameter
is needed. What was wrong with it was its **type and its name**: typed as a `Sample`, it *is* the
printed generations — the exact object the sentence forbids, and the one the old code passed.

**Why `units_by_domain` and not `seed_units`.** It is byte-identical in shape and name to what
`curve_probe` and `holdout_probe` already take, so the tree declares one per-domain unit supplier
once instead of two that look alike. The per-domain keys are load-bearing rather than decorative:
HOME is the key of the bucket a seed was cut from, so the strict arm needs no lookup, seeds are
drawn one per domain in rotation, and the **ceiling** — real text of the same length, scored the
same way — is cut from the same material. `seed_units` would have thrown the labels away.

**Why `encode` had to land in the same edit, which is the part the question did not ask.**
`self_organize.py:9693-9800` is the metric this instrument replaces, and its inner `_stay()` calls
the encoder **on every generated window, on both arms** — the measurement *is* "which centroid is
this window of the continuation nearest". EVAL cannot import SIG. The tree's idiom for that boundary
is a passed-in callable, and the composition root **already forms this exact one**: `_sig_encode_fn`,
which `DOM.rekey` takes under the name `encode`. So it costs no new producer and no new entry point,
and it is named `encode` rather than `encode_fn` or `home_fn` so that one callable is not declared
twice under two names. `eval/levers.py`'s *"in the self-referential case HOME is measured per seed by
encoding it and taking the nearest centroid"* is a **second** use of the same callable, not a second
argument. **Passing `centroids` or a `home_fn` instead was refused:** the old file builds
**true-corpus** centroids from the labelled material and calls scoring against the system's *own*
assembled partition the **weaker, self-referential** arm. A `home_fn` supplied by DOM would make that
weak arm the only arm — a capability downgrade, which is the one thing this rework may not do.

**Why the reopening is cheap now and was not deferrable.** 118 of the 123 frozen entry points are stubs,
P6 writes this body, and K1 compares the document against the tree in both directions — so the move
is one `def` line, one line in §7 and one deferral reason today, and a rewrite of P6's instrument
later. Shipping a signature the function provably cannot be written against would have guaranteed a
**second** reopening of EVAL's surface; Q-MEM-10's ruling (`logits_fn` untouched, the blend join
stays in the root) deliberately left room for exactly one, and this is it.

**What did NOT change:** `logits_fn` and `rng` are untouched, `LEVERS READ` is still
`coh_seeds, coh_len, gen_temp`, no lever moved, no default moved, no wire, no census row. The
function stays deferred — `logits_fn` and `units_by_domain` still have no producer, and both are now
named in its deferral reason (K12 reads that in both directions).

**What P6 must still decide, recorded rather than defaulted away:** which arm a given run is on is
**a report field, not a silent choice** — the strict arm needs ≥ 2 labelled buckets in
`units_by_domain`, and the self-referential fallback must be printed as the weaker claim, the way the
old file printed it.

### Q-MEM-11 — `MEM.census` and `DOM.census` return record types neither file declares — **RESOLVED 2026-09-02: (a), WITH THE PRODUCER'S OWN SPELLINGS**
`memory/api.py:14-19` declares `Store`, `WriteReceipt`, `Retrieval` and nothing for `census`, whose
docstring names `floor_entries`, a `quota_arm`, `pressure` and the per-source counts **in prose**.
`domains/api.py:18-23` declares `Partition`, `Assignment`, `Plan` and nothing for `census`, whose
prose names `live`, `n_live`, `comp_glob`, radii and more. Four required arguments cross those two
boundaries — `DOM.manage`'s `memory_counts` and `mem_floor_entries`, `FAB.grow_check`'s
`memory_pressure`, `FAB.forward`'s `live_domains` — so the `produces` columns spell the **consuming**
names against a record whose fields are not declared anywhere. **Options:** (a) add both returns to
the RECORD TYPES blocks and spell the fields, ideally as the consuming names so the rename disappears;
(b) leave the prose and accept that the round trip is unverifiable by inspection.
**Recommendation: (a)** — it is a docstring change inside a frozen signature, and `TOK.vocab_state`'s
D-T3 is a live defect *caused* by an undeclared key.

**RESOLVED 2026-09-02: (a), WITH THE PRODUCER'S OWN SPELLINGS. The parenthetical — "ideally as the
consuming names so the rename disappears" — is NOT adopted.** `MEM.census` returns **`StoreCensus`**
and `DOM.census` returns **`PartitionCensus`**, both declared in their own module's RECORD TYPES
block. Named distinctly rather than both `Census` so a `grep` stays unambiguous across packages. No
signature moves; four docstrings and two `compose.py` prose claims changed.

**What settles the *spelling* half, and it is not in the question: K11 is a name-appearance check.**
Its own docstring says so — *"The name must appear somewhere in the entry point's docstring or its
module's… It cannot tell a returned field from a mention, and it does not try."* So the four
crossing `produces` entries pass today **only because the words happen to appear in prose**.
Declaring the records turns a coincidence into the thing the check was built to read.

**Why the consumer's spellings are refused, three ways:**
1. It would put `memory_counts`, `mem_floor_entries` and `memory_pressure` **on MEM's own record** —
   a package prefixing its own fields with its own name, which is the doubled-name defect the census
   already corrected once (`WORLD_NMAX`→`nmax`, `FAB_FAB_N0`).
2. It inverts the rule `spine/assemble.py` is built on: *"THE WIRE NAMES THE FIELD, NOT THE
   RECEIVER… The receiving package is never handed a chance to choose a name."* The symmetric rule
   is that the **producer** does not carry the consumer's vocabulary either.
3. **"The consuming name" is not a function, and the tree already shows it:** `DOM.census`'s `live`
   reaches MEM as `live_sources` while its `n_live` reaches FAB as `live_domains`. One record feeds
   two packages under two vocabularies.

**The rename stays where it is already declared and already machine-checked** — `compose.py`'s
`produces` column, in the `alias = real -- why` form K11 admits and K10 consumes. Moving it into the
record would empty a checked mechanism into an unchecked one. **(b) is refused** because P4 would
then invent the field names and the four `produces` entries would certify a round trip nothing can
verify — which is `TOK.vocab_state`'s D-T3 exactly, one package over.

### Q-TOK-12 — which window's `Due` does the flush act on? — **RESOLVED 2026-09-02: (b), THE OR, PER CADENCE KEY. IDENTICAL TO (a) AT THE SHIPPED `OPT_BATCH_WINDOWS = 1`; NO SIGNATURE MOVES**
`TOK.on_window` is asked per WINDOW; `mint_burst`, the retok and `judge_probation` act per FLUSH
(§3.10). `batch_windows` Dues therefore reach one flush and nothing in the frozen surfaces says which
one wins. **Options:** (a) the LAST window's — simple, and silently drops up to `batch_windows - 1`
fires; (b) the OR over the batch — no fire is lost, but a flush then acts on a cadence that fired
mid-batch, and `judge_probation`'s `appearances` is the counter the *whole* batch updated; (c) hoist
the three B-stage acts to A, which puts a mint inside the accumulator and invalidates the batch the
model is mid-flush on. **Recommendation: (b)**, with the count of dropped-or-merged fires as a
counter, because the failure this whole cadence design exists to prevent is a fire that silently does
not happen. The root carries the events on `System.due` either way.

**RESOLVED 2026-09-02 — (b), the OR, per cadence key.** The root ORs `mint`, `retok` and `probation`
**separately**, and takes `frozen` from the last window of the batch, which is the same value because
`frozen` is a monotone **state** and not an event (`at step >= freeze_at … True from then on`). The
OR happens in the root because the root is the only thing that can see a batch; `Due` keeps its four
fields and **no signature moves**.

**(a) was refused on arithmetic, not taste.** Every cadence is elapsed-since-last-fire and `_due`
**records** the step, so a `Due` a flush discards is a fire that is silently gone. Under "last", a
`Due` survives only when the window that raised it is last in its batch — a rate of
`gcd(period, batch_windows) / batch_windows`: at `grow_every=200` with `batch_windows=16` that is
**half of all mints and half of all retoks**, and at any period coprime with the batch it is **15 of
16**. That is the same silent non-fire the design exists to prevent (minting fired 999 times at
`batch_w=1` and **zero** at `batch_w ∈ {2,8,15,16,32}` under the modulo form), reintroduced by a
different route. (b)'s cost is bounded latency — a flush acting on a cadence raised up to
`batch_windows-1` windows earlier, **under 8% of one `grow_every` period at `batch_w=16`** — and it
is consistent with `judge_probation`'s other input, the counter *this flush's whole batch* updated.
(c) puts a mint inside the accumulator and invalidates the batch the model is mid-flush on.

**Two counters, and one must read zero.** `tok.due_merged` (a flush where more than one window raised
the same key; **unreachable at `batch_windows = 1`**) and `tok.due_dropped`, which is **0 by
construction** under (b). A counter that must read zero is how a later reader can tell which reading
was actually implemented — under (a) the same counter is the number that says what (a) cost.

**Birth steps are flush-aligned, written down rather than rediscovered:** `step` handed to
`mint_burst` and `judge_probation` is `clock.step` **at the flush**, so a token minted on an OR-ed Due
is born up to `batch_windows-1` windows after the window that raised it. `probation_deadline` compares
`step - birth`, both `Windows`, so nothing raises.

**At the shipped `OPT_BATCH_WINDOWS = 1` the two readings are identical and no recorded result
moves.** The divergence appears at `BATCH_W=16`, which is the heavy-run configuration.

### Q-LM-12 — what call produces `WORLD.loss_terms`' `obs_emb`? — **RESOLVED 2026-09-02: (b), `LM.embed`. ⚠ THE FROZEN SET GREW 122 → 123 (LIVE COUNT RE-VERIFIED 2026-09-03 BY SCRIPT: 123 IN THE TREE, 123 IN §7, LM HOLDS 12). THE CONTRACT'S OWN RECOMMENDATION (a) IS REFUTED ON BOTH ARMS**
`world/api.py:58-63` wants "LM's EMBEDDING of the batch, (B, W, d_model) — the lowest layer, the
point where a new sense plugs in". **LM exposes no embedding entry point**: `LM.encode` returns the
`(B, L, width)` HIDDEN, and its `n_layers` argument "runs only the first n blocks", so `n_layers=0`
is a plausible reading and nowhere a stated one. This is load-bearing for goal A's *room for more
modalities*: if `obs_emb` is silently the GRU/transformer state, then the claim that a second sense
needs only new embedding rows is false and nothing says so. **Options:** (a) state that
`LM.encode(..., n_layers=0)` is the embedding; (b) add an `LM.embed` entry point — a signature
change; (c) let WORLD take the hidden and correct the module docstring's modality claim.
**Recommendation: (a)** if the arm really returns the embedding table's output, otherwise (b).

**RESOLVED 2026-09-02 — (b). ⚠ LOUD: THE FROZEN SIGNATURE SET GREW AGAIN, 122 → 123.**
`LM: embed(lm: Config, model, x)` is in §7, in `src/lm/api.py`, and on a **`B` row before
`encode/decode/lm_loss`** — first of the B rows, because `WORLD.forecast` supplies that row's `extra`
and `forecast` takes `obs_emb` too. **This is the SECOND LM addition of the day**: Q-TOK-11 took the
set 121 → 122 with `LM.residual_ratios` on the same date from an independent ruling, and both were
written believing they were the "121 → 122" edit. **§7's header is the count and this is why**; the
two prose restatements elsewhere in this document and the two in `spine/compose.py` now point at §7
instead of carrying a fifth and sixth copy.

**The contract's own recommendation (a) is REFUTED, on both arms, and the refutation is quoted from
the tree.** `LM.encode`'s docstring says `n_layers` *"runs only the first n blocks **on the
transformer arm** … **On the gru arm it is accepted and ignored, and that is a DECLARED GATE**"*. So
on the **shipped gru arm** `n_layers=0` returns the full GRU hidden — exactly what `obs_emb` must not
be. And on the transformer arm, zero blocks is `s.emb(x) + s.pos(p)` (`:1587`), embedding **plus
positional**, which is not what the old world encoder received either: `:6813` passes `model.emb(x)`
alone. Loading a second meaning onto `n_layers` also repeats the shape CENSUS.md:250 records for
`KEY_LAYERS` — a declared gate one arm ignores, *"silently inert twice over"*.

**The tree already said two different things about this argument, in one file, and the second does
not run.** The `WORLD.loss_terms` row said *"LM EXPOSES NO EMBEDDING ENTRY POINT … whether encode
with `n_layers=0` is the embedding is nowhere stated — Q-LM-12"*, while `ROW_ARGUMENTS_ELSEWHERE`
said `obs_emb` is *"the model's embedding table applied to the same cut LM.encode took, which is a
tensor operation the loop does between two calls."* The second is a decision the first says has not
been made — **and it is an `AttributeError` on every run with `lm.compose = 1`**, because
`build_model` states that under compose `emb` and `head` *"are NOT constructed at all"*. The old tree
hid this: `MiniLM.__init__` always constructed `s.emb` and merely used the ByteComposer's table
instead when compose was on, so `world_enc(model.emb(x))` did not crash at `TOK_COMPOSE=1` — **it fed
the world model an embedding table the LM was not training**. `TOK_COMPOSE` defaulted to 0, so no
recorded run hit it; the new tree turns the same latent confounder into a crash. That entry has been
deleted from `ROW_ARGUMENTS_ELSEWHERE` and replaced by a real producer.

**(c) — WORLD takes the hidden — is refused as an owner-level claim, not a package preference.** It
would make `world/api.py`'s *"a second sense needs new rows in LM's embedding and nothing new here"*
false with nothing in the tree saying so, and that sentence is goal A's **room for more modalities**.
It would also make the world model predict the dynamics of a GRU state under the name of
observations — a different mechanism wearing the same name.

**Why LM and not the root.** Only LM knows whether the token vector table is `emb.weight` or the
ByteComposer's output. Reaching for `model.emb` from the composition root is a package-internals read
the ownership spine forbids in spirit and that **K7 cannot catch** — it checks `Config` reads, and
`model` is not a `Config`, so the check would be green while looking at the wrong surface.
`lm.embed.from_composed_table` vs `lm.embed.from_emb_weight` is the DID IT FIRE pair that makes which
table the world model observed a printed fact.

**Cheap now, expensive later:** LM's bodies are unwritten, so this cost one stub, one §7 line, one
row and one deleted exemption. After P4 it is a coordinated edit across ten independent agents.

**THE COUNT WAS RE-VERIFIED BY SCRIPT ON 2026-09-03, NOT COPIED FROM THIS DOCUMENT**, because
`Q-TOK-11` and this question collided on it once already and a fifth stale count would be the sixth
time. Running `test_contract.api_signatures()` — K1's own AST walk, the same oracle the check uses —
over `src/` returns **131 entry points**, against **131 declared** in §7's ```contract block, all
distinct. Per package: CAP 7, CKPT 11, DATA 5, DOM 10, EVAL 9, FAB 11, **LM 12**, MEM 10, OPT 7,
RUN 14, SIG 10, TOK 9, WORLD 8. LM's twelve are `anchor_term`, `build_model`, `counters`, `decode`,
**`embed`**, `encode`, `lm_loss`, `load_state`, `on_mint`, **`residual_ratios`**, `resolve`,
`state_dict` — the two additions are both present and both in §7, so 121 + 2 = 123 is the arithmetic
and the tree agrees with it in both directions.

---

## 6. What `tests/test_contract.py` checks

| check | what it proves | how it can fail |
|---|---|---|
| K1 | every name this document declares exists in the tree **with the signature it claims** | rename a parameter; drop a function |
| K2 | `spine.compose` imports and `compose()` raises **only `NotImplementedError`, from a stub** | a typo in the root surfaces as `AttributeError`/`TypeError`, not as a missing body |
| K3 | no package imports another (O10 restated at the contract boundary) | add `from fabric import api` to `src/memory/` |
| K4 | every one of the 262 declared levers is named `LEVERS READ:` by a stub, or is in the UNCONSUMED table above **with a reason** | declare a lever and give it no reader |
| K5 | every `d_` field the ledger declares is read by a stub in its own package, and no stub reads an undeclared one | add a wire nobody consumes |
| K6 | every entry point is **named by a row** in `ASSEMBLY_ORDER` or `LOOP_ORDER`, or is in `compose.DEFERRED_ENTRY_POINTS` with a reason | declare a mechanism the root never calls; or leave a deferral in place after a row starts naming it — the check reads that table **backwards** and reports the stale entry |
| K7 | the root reads only names a package **declares** off a Config | `int(lm.depth)` where LM declares `layers` — a crash at whatever stage reaches it, invisible while an earlier stub raises first |
| K8 | every RNG stream the root takes is one `RNG_SUBSYSTEMS` minted, and none is reached with `.get()` | `streams.get("world")` returning `None` into a required `rng=` |
| K9 | every `Cadences.due` period in the tables is a **typed accessor**, not a bare lever read — **and every value in `compose._periods` is a call or a module constant constructed with a Clock kind** (widened 2026-09-03) | `Cadences.due('fab.manage', FAB.manage_every, clock)` — an int where `due` requires `units.Windows`; or `PROGRESS_WINDOWS = 100`, the sixth period, which has no row and which nothing in the suite could see until the mapping half was added |
| K10 | every **required** argument of a rowed entry point is produced by an EARLIER row's `produces` column, named in that row's own note, listed in `ROW_ARGUMENTS_ELSEWHERE`, or the entry point is deferred | write a row for a call whose arguments nothing supplies — which is what `EVAL.curve_probe` was, against a deferral for the byte-identical `EVAL.holdout_probe` |
| K11 | no `produces` entry names a value its entry point does not return | certify a six-field record as the whole geometry comparison by writing the bare token `geometry` in a column |
| K12 | every deferral reason names **every** required argument that has no producer | defer `FAB.contribution` with a reason listing two of the four arguments nothing supplies |
| K13 | every **number the prose writes about a countable thing** equals the tree's number, and no `### Q-` heading says a thing is **absent** that the tree declares | write a field count for the manifest that is one short of the live one, or head a question *"nothing in this system clips gradients"* while `OPT.grad_clip` is declared |

**K6 is the check K4 is not, and the gap was 56 entry points wide.** K4 asks whether some stub's
docstring *names* a lever; K6 asks whether that stub is ever *called*. K4 passed at 257 named / 2
unconsumed / 0 unaccounted while nothing trained the signature encoder, nothing read memory, nothing
called `DOM.rekey`, and nothing drew a stream. Reading them together: a lever is accounted for when
some stub names it **and** some row reaches that stub. K6 still cannot see whether the loop, once
written, executes a row — the tables are data and P4 writes the code — nor an entry point reached
only from inside another body, which is why `OPT.lr_at` is credited by being **named in the prose of
the row that calls it** (`OPT.maybe_step`, step 2) rather than given a row of its own.

**K10 asks about REQUIRED arguments only**, and that is a real limit with a name: a parameter
carrying a default is the author saying the call works without it, so the check cannot see
`MEM.judge(mem, store, *, scorer=None)` yielding `n_checked = 0` forever under a `verify` that
defaults to `selfcon`. Only reading the docstring can, which is why that one is a deferral written by
hand. It is also blind to `MEM.blend`'s `model_probs`, which it drops as "the package's own live
object" — MEM's live object is `store`, and `blend` is the one entry point that does not take it.

**K13 is the one that stops a recurrence rather than a class of defect**, and it is the youngest.
Counts in this document's prose have been wrong **six** times: the geometry manifest's field count
(written 15 and 16, against twenty); `WORLD.geometry`'s width (five, against six);
`CKPT.check_geometry`'s argument count ("two", against four); the size of the frozen signature set
(written 121 in four present-tense places at once, against the 123 that §7 declares); the
rejected-candidate count in `NOT_WIRES` (6, against 7); and the typed-accessor count ("the four
accessors", against five). Every one was found by a human reading and every one was a `grep` away.
*(Those six are written here without the shapes K13 searches for, deliberately: the check found two
of them in the first draft of this paragraph, which is the check doing its job to its own
documentation.)* K13 counts the live tree by AST, searches a listed
set of English shapes for numbers about those quantities, and compares. **It prints the shapes it
searched for and the ones it did not**, because a prose check over English is a heuristic and a
heuristic that will not say what it missed is worse than no check: it cannot read a number written
in **words** (which is exactly how "the four accessors" and §3.6's "fourteen" survived it), it
skips any claim in a past-tense sentence and prints the list of what it skipped, and it sees only
the shapes in its table. Arm (b) reads the 39 `### Q-` headings and nothing else. **It fails when it
finds nothing**, because "no claims found" and "no claims wrong" are the same output from a check
that has stopped reading.

Each carries a `_report()` line printing **the size of the population it examined**, and
`selftest()` trips every one of the thirteen against a synthetic tree in a temp directory. That is not
ceremony: this repository has **sixty** untrippable guards on record, and one of them was written
into `tests/test_ownership.py` *by the patch that was fixing `tests/test_ownership.py`*. A check
nobody has watched fail is indistinguishable from a check that cannot fail.

---

## 7. THE FROZEN SIGNATURE SET

Everything above is prose about these 131 entry points — 121 until 2026-09-02, when Q-TOK-11 added
`LM.residual_ratios` (122) and Q-LM-12 added `LM.embed` (123). Both are LM, both landed on the same
day from two different rulings, and **that is why the count lives here and nowhere else**: the first
of the two wrote "121 → 122" while the second was independently preparing to write "121 → 122" for a
different entry point, and the two together are 123. **THIS BLOCK IS THE COUNT.** The number is restated in prose at four other
places (§0's coverage sentence, §3.6's deferral rule, §3.7's `EVAL.generate` row, and
`spine/compose.py`'s two deferral notes); an amendment to the signature set must move **all of them
in the same commit**, and the next one to touch it should replace those restatements with a pointer
here rather than a sixth copy. This block is the normative list, and
`tests/test_contract.py`'s K1 compares it against `src/<pkg>/api.py` **in both directions**: a name
here that the tree does not have is a failure, and a public entry point in the tree that is not here
is also a failure. The signature text is `ast.unparse` of the argument list, so a renamed parameter,
a reordered one, a changed default or a positional-that-became-keyword-only all fail.

Ten implementation agents work against this list independently. **It does not move without an edit
to this document and to the tree in the same commit**, which is the only thing keeping them
compatible.

```contract
CAP: new_valve(cap: Config, *, restored=None)
CAP: observe(cap: Config, valve, *, elapsed_windows, live_experts, live_vocab, improving, observations, blackout)
CAP: caps(cap: Config, valve)
CAP: startup_refusals(cap: Config, valve, *, live_experts)
CAP: state(valve)
CAP: restore(cap: Config, valve, state)
CAP: counters(cap: Config, valve)
CKPT: saving_on(ckpt: Config)
CKPT: save_period(ckpt: Config)
CKPT: save(ckpt: Config, *, payload, geometry, step, epoch, reason, suffix='')
CKPT: install_save_signal()
CKPT: resume_source(ckpt: Config)
CKPT: load(ckpt: Config)
CKPT: check_geometry(ckpt: Config, snapshot, geometry)
CKPT: new_retention(ckpt: Config, *, restored=None)
CKPT: Retention.consider(self, curve_bpb, step)
CKPT: Retention.state(self)
CKPT: Retention.counters(self)
DATA: open_areas(dat: Config, *, seed: int)
DATA: data_plan(dat: Config, areas, *, epochs: int, win_tokens: int, bytes_per_token: float)
DATA: draw_stream(dat: Config, areas, plan, *, epoch: int, seed: int)
DATA: stream_state(dat: Config, areas)
DATA: restore_stream_state(dat: Config, areas, state)
DOM: open_partition(dom: Config, *, sig_dim, vocab_slots, device, rng, restored=None)
DOM: observe(dom: Config, part, *, signature, sample_window, tokens, now)
DOM: rekey(dom: Config, part, *, encode)
DOM: note_competence(dom: Config, part, *, did, bits)
DOM: manage(dom: Config, part, *, now, memory_counts, mem_floor_entries)
DOM: on_retokenize(dom: Config, part)
DOM: prior(dom: Config, part, *, did)
DOM: census(dom: Config, part)
DOM: state_dict(dom: Config, part)
DOM: manage_period(dom: Config)
EVAL: curve_period(ev: Config)
EVAL: curve_probe(ev: Config, *, units_by_domain, logits_fn, rng)
EVAL: holdout_probe(ev: Config, *, units_by_domain, logits_fn, rng)
EVAL: null_excess(ev: Config, *, real, permute, rng)
EVAL: generate(ev: Config, *, logits_fn, prompts_by_domain, rng)
EVAL: coherence(ev: Config, *, logits_fn, units_by_domain, encode, rng)
EVAL: verdicts(ev: Config, *, domain_sizes, silhouettes, affiliation, coherence_reading)
EVAL: wrongness_probe(ev: Config, *, store_copy, scorer, rng)
EVAL: verification_fit(ev: Config, *, store_copy, rng)
FAB: build(fab: Config, *, d_model, signature_dim, device, generator)
FAB: Population.n(self)
FAB: forward(fab: Config, pop, *, h, signature, novelty, head=None, targets=None, step_windows, domain_id, live_domains, training, hold_out=None)
FAB: observe(fab: Config, pop, out, *, per_window_loss, domain_id)
FAB: contribution(fab: Config, pop, *, h, signature, novelty, head, targets, baseline_loss, baseline_logits_fn, step_windows, domain_id, live_domains, candidates)
FAB: manage(fab: Config, pop, *, step_windows, flush_loss=None)
FAB: grow_check(fab: Config, pop, *, flush_loss, step_windows, soft_cap, memory_pressure, signature, shift_at=None)
FAB: own_lr_scale(fab: Config, pop, *, applied_lr)
FAB: counters(fab: Config, pop)
FAB: state_dict(fab: Config, pop)
FAB: load_state_dict(fab: Config, pop, sd, *, sidecar)
FAB: manage_period(fab: Config)
LM: resolve(lm: Config)
LM: build_model(lm: Config, geom, *, device, seed)
LM: embed(lm: Config, model, x)
LM: encode(lm: Config, model, x, *, n_layers=None, extra=None)
LM: decode(lm: Config, model, h, *, live_vocab, retired_ids)
LM: lm_loss(lm: Config, logits, y)
LM: anchor_term(lm: Config, model, *, token_seen)
LM: on_mint(lm: Config, model, mints, id2bytes, *, at_window, sig_emb=None)
LM: residual_ratios(lm: Config, model)
LM: state_dict(lm: Config, model, geom)
LM: load_state(lm: Config, model, geom, saved)
LM: counters(lm: Config, model)
MEM: open_store(mem: Config, *, key_dim, vocab_slots, device, rng, lm_kind, restored=None)
MEM: write(mem: Config, store, *, contexts, tokens, surprise, sources, owners, positions, key_fn, now)
MEM: read(mem: Config, store, *, queries, promote=True)
MEM: blend(mem: Config, model_probs, retrieval)
MEM: maintain(mem: Config, store, *, now, key_fn, probe_contexts=None, resegment=None)
MEM: apply_domain_plan(mem: Config, store, *, folds, deletions, live_sources)
MEM: judge(mem: Config, store, *, scorer=None, reconstructor=None)
MEM: census(mem: Config, store, *, reconcile=False)
MEM: state_dict(mem: Config, store)
MEM: rekey_period(mem: Config)
OPT: build(opt: Config, *, param_groups, run_windows)
OPT: lr_at(opt: Config, st, opt_step)
OPT: scaled_backward(opt: Config, st, total)
OPT: maybe_step(opt: Config, st, *, best_bpb=None, shift_at=None)
OPT: counters(opt: Config, st)
OPT: state_dict(opt: Config, st)
OPT: load_state(opt: Config, st, saved)
RUN: process_setup(run: Config)
RUN: mode(run: Config)
RUN: Timing.span(self, name)
RUN: Timing.spans(self)
RUN: streams(run: Config, subsystems)
RUN: new_clock(run: Config, *, batch_windows, accum, resume_step=0, resume_epoch=0)
RUN: RunClock.begin_epoch(self, windows_in_epoch)
RUN: RunClock.advance(self)
RUN: RunClock.note_backward(self)
RUN: RunClock.counters(self)
RUN: new_cadences(run: Config, *, periods)
RUN: Cadences.due(self, key, period, clock)
RUN: Cadences.ledger(self)
RUN: bench_summary(run: Config, clock, *, elapsed_s, bytes_per_window, n_params, timing=None)
RUN: startup_refusals(run: Config, *, disk_stream)
RUN: cadence_audit(run: Config, *, run_windows, periods)
SIG: build(sig: Config, *, width_units, alphabet_size, device, generator)
SIG: encode(sig: Config, st, windows)
SIG: cadence_due(sig: Config, st, *, step_windows, windows_since_boundary)
SIG: train_step(sig: Config, st, *, stream, seen_units, opt, reservoir=None)
SIG: warm_up(sig: Config, st, *, stream, seen_units, opt)
SIG: counters(sig: Config, st)
SIG: state_dict(sig: Config, st)
SIG: load_state_dict(sig: Config, st, sd, *, sidecar)
SIG: encoder_parameters(sig: Config, st)
SIG: encoder_embedding(sig: Config, st)
TOK: build_vocabulary(tok: Config, *, area_heads, seed: int, soft_cap=None)
TOK: tokenize(tok: Config, vocab, data, labels=None, *, start=0, regularize=False, seed=0)
TOK: Vocabulary.decode(self, ids)
TOK: Vocabulary.blen(self, i)
TOK: Vocabulary.size(self)
TOK: Vocabulary.live_size(self)
TOK: Vocabulary.at_cap(self)
TOK: on_window(tok: Config, vocab, ids, *, step)
TOK: mint_burst(tok: Config, vocab, *, step)
TOK: judge_probation(tok: Config, vocab, *, step, appearances, residual_ratio=None)
TOK: lift_vocab_cap(tok: Config, vocab, *, to: int)
TOK: save_vocabulary(tok: Config, vocab, *, suffix='')
TOK: vocab_state(tok: Config, vocab)
TOK: restore_vocab(tok: Config, state, vocab)
WORLD: build(world: Config, *, d_model, device, ctx_tokens, rng)
WORLD: loss_terms(world: Config, w, obs_emb)
WORLD: forecast(world: Config, w, obs_emb)
WORLD: manage(world: Config, w, *, latent, plateau, add_param_group)
WORLD: geometry(world: Config, w)
WORLD: state_dict(world: Config, w)
WORLD: load_into(world: Config, w, sd)
WORLD: startup_refusals(world: Config, *, ctx_tokens)
```
