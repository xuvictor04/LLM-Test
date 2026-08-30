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

`tests/test_contract.py` parses those blocks. 257 of the 259 declared levers are named by at least
one stub as read by it; the two that are not are in **UNCONSUMED LEVERS** below with a disposition.
**Naming is not calling**: which stubs the composition root actually reaches is section 3, and 110
of the 117 entry points are named by a row with the remaining seven declared deferred.

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
`spine/assemble.py`. The ledger went from 13 rows / 10 wires to **22 rows / 19 wires of 25
budgeted**.

| new row | src | why it is a wire and not an argument |
|---|---|---|
| `LM.d_max_token_bytes` | `TOK.max_bytes` | `ByteComposer.__init__(s, d, maxb=16)` at `:1441` is constructed as `ByteComposer(d)` at `:1549` so the default always wins, and `:1487` truncates. With `MAX_TOK > 16` two long tokens sharing their first 16 bytes get **identical composites** — the composer's whole property, inverted, silently (ISSUES M21). `lm/levers.py:165` names the field; `tok/levers.py:337` records the row as missing. The defaults agreeing today is luck. |
| `CAP.d_expert_slots` | `FAB.slots` | `CAP_FAB_START = 0` is a **sentinel meaning "start at the hard ceiling"**, and `lever.py` refuses a default computed from another lever — so 0 stood for a number nothing supplied. `capacity/levers.py:119`, and `:123` says in as many words that the row is absent. |
| `CAP.d_vocab_slots` | `LM.vocab_slots` | The same sentinel on the other target. `capacity/levers.py:244` records that TOK holds no ceiling of its own to give. |
| `CAP.d_mask_dead_rows` | `LM.mask_dead_rows` | The honesty precondition on the vocabulary arm: 8192 reserved against 2048 minted is 6144 rows in the softmax denominator indexing nothing, so the run measures the reservation and not the mechanism. LM owns the output layer; CAP does not get to decide this. |
| `CAP.d_operating_population` | `FAB.pressure × FAB.slots` | The irreducible coupling the valve must **declare rather than remove**: a soft cap above the cull's settling point never pins, so the pin clock never accumulates and the valve is dead while looking armed. A second landing of the identical `derive.operating_population` call, so the fabric's setpoint and the valve's refusal cannot disagree. |
| `DOM.d_comp_ema` | `FAB.comp_ema` | One smoothing rate for two populations, or "this domain beats the population" is a comparison between two differently smoothed series. `fabric/levers.py:693` names both this and the next; `self_organize.py:6720` is the direct attribute reach it replaces. |
| `DOM.d_comp_protect` | `FAB.comp_protect` | One brake policy for two populations. The domain cull is the mechanism that deleted 200,000 memory entries under a phased schedule. |
| `FAB.d_base_lr` | `OPT.lr` | `:7252` builds the per-expert envelope from the **peak**. Until some name lands, `FAB_LR_OWN=1` has no legal way to learn the number — which is what makes ISSUES H15 (`NameError: _lrv`) spellable. Named `d_base_lr` and not `d_lr_peak` because the **receiver** already declares that spelling (`fabric/levers.py:756`) and the receiver's `grep d_` is the one that has to find it. This settles the open name conflict `opt/levers.py:186` records. |
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
| `d_residual_ratio` | `MintReport.residual_ratio` → argument to `judge_probation` | read off a live tensor. Until it arrives, TOK's `probation_by="embed"` arm is Gate-declared unreachable rather than silently running the "use" test (ISSUES M41). |
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

### DATA — `src/data/api.py` (17 levers)

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

`resolve` · `build_model` · `encode` · `decode` · `lm_loss` · `anchor_term` · `on_mint` ·
`state_dict` · `load_state` · `counters`.

**Wires read:** `d_pos_max` (the refusal, not a clamp), `d_max_token_bytes`.
**Receives:** `device`/`seed` ← RUN; `live_vocab`/`retired_ids`/`mints`/`id2bytes` ← TOK;
`n_layers` ← MEM's `key_depth`; `sig_emb` ← SIG; `token_seen` ← the loop; `extra` ← WORLD's forecast.
**Supplies:** `decode` as a plain callable to FAB; `MintReport.residual_ratio` to TOK.
**Checkpointed:** the module, the composer's `born` tensor, the counters, the resolved
`LMGeometry`. **Not:** the derived byte-index tensors (rebuilt on load) or the dead-row mask cache.

A resume across a `compose` flip is **refused in both directions** and named — under compose,
`emb`/`head` are not constructed at all. That is a real operational restriction and P7's add-area
entry point must know it before planning an arm table.

### OPT — `src/opt/api.py` (12 levers)

Owns every rate and the size of the batch it acts on. **OPT maintains its own optimizer-step
counter**, so `units.Steps` becomes literally true and no `Windows→Steps` conversion is written —
`spine/derive.py` has no such function, verified.

`build` · `lr_at` · `scaled_backward` · `maybe_step` · `counters` · `state_dict` · `load_state`.

**Wires read:** `d_effective_batch_windows`.
**Receives:** `param_groups` (plain lists the packages returned — OPT never walks a module tree),
`run_windows`, `best_bpb` (a Reading carrying its seed count), `shift_at`, `saved`.
**Checkpointed:** both AdamW states, `n_backward`, `opt_step`, `lr_prev`, `restart_amp`,
`cycle_best`, `cycle_index`, the resolved `Horizon`, the counters. The old checkpoint saved
`opt_m`/`opt_e` and *nothing else from this package*.
**The invariant `counters()` asserts:** `backward // accum == step`.

### SIG — `src/sig/api.py` (18 levers)

Owns the one function from a window to a unit vector. `encode` is the only way to obtain a
signature, on any path; `sig.encode_width_mismatch` must be 0 and a nonzero value is C4 reintroduced.

`build` · `encode` · `cadence_due` · `train_step` · `warm_up` · `counters` · `state_dict` ·
`load_state_dict` · `encoder_parameters` · `encoder_embedding`.

**Wires read:** none. **Receives:** `width_units` (from `derive.signature_width_bytes`, computed
once by the root), `alphabet_size`, the unit stream, `seen_units`, the encoder optimizer built by
OPT, `windows_since_boundary` ← DOM, `reservoir` ← DOM.
**Checkpointed:** encoder, counters, warmup curve **and its verdict**, the RNG stream, plus a
sidecar carrying `width_units`, `alphabet_size`, `space`, `d`, `mode` — a resume that disagrees
about any of them fails **here**, naming the field.
**`warm_up` returns one of three verdicts, never a binary**; `collapsing` is a run-level failure.
**Where they are called (§3):** `warm_up` is an `ASSEMBLY_ORDER` row after both stream rows and the
optimizer row; `cadence_due` → `train_step` are stage-`A` rows **before** `encode`; `counters` is a
stage-`R` row and is the encoder cadence's **only** did-it-fire surface, because its two-arm gate
cannot go through `Cadences.due`. Until those rows existed the run trained no encoder at all.

### FAB — `src/fabric/api.py` (82 levers, 80 read)

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
`grace=48` was set against a clock that ticked once per window. On P9's list; see **Q-FAB-5**.

### MEM — `src/memory/api.py` (25 levers, 24 read directly)

The editable store, and the one component whose failure mode *is* forgetting, mechanically.

`open_store` · `write` · `read` · `blend` · `maintain` · `apply_domain_plan` · `judge` · `census` ·
`state_dict`.

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
**Where they are called (§3):** `census` is a stage-`A` row **before** `DOM.manage`, whose
`memory_counts` and `mem_floor_entries` had no other producer, and again at `R`; `judge` is an event
on that same management pass (**Q-MEM-8**); `read(promote=True)` is `maintain`'s probe (**Q-MEM-9**)
while `read(promote=False)` + `blend` are stage-`R` rows, because retrieval has never entered the
training distribution in this project and moving it there is an unmeasured behaviour change
(**Q-MEM-10** is the interface that path still lacks); `state_dict` is a stage-`C` row.

### DOM — `src/domains/api.py` (28 levers)

The self-assembling partition; `did` is the **unit of forgetting**, and its granularity is what makes
a delete cost 1.6% of memory rather than 30%.

`open_partition` · `observe` · `rekey` · `note_competence` · `manage` · `on_retokenize` · `prior` ·
`census` · `state_dict`.

**Wires read:** `d_expert_slots` (at exactly one site, the at-cap absorb), `d_comp_ema`,
`d_comp_protect`.
**`manage` returns a PLAN; this package never touches memory.** The old tree read three of MEM's
internals inline at `:3688`, including a private method.
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

`spine/compose.py` holds two tables of rows, `ASSEMBLY_ORDER` and `LOOP_ORDER`, and one dictionary,
`DEFERRED_ENTRY_POINTS`. Together they are the normative answer to a question **K4 does not ask**:
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

### 3.1 The stages

`ASSEMBLY_ORDER` gained four stage values — `resume`, `restore`, `stream`/`segment`, `persist` —
and `LOOP_ORDER` gained three stage letters. **There is still no third table**, for two reasons and
the second is the load-bearing one: every level below is driven by the **same** `RunClock`, and
`tests/test_contract.py:879` reads the tables **by name** (`ASSEMBLY_ORDER`, `LOOP_ORDER`) — a third
table would be invisible to the one check that exists because these rows were missing, and *a level
with a table of its own that no check can see is still an orphan.*

| stage | when | what is in it |
|---|---|---|
| `E` | before the first window of an epoch, and again whenever `RunClock.advance` returns `Tick.rolled` | `DATA.draw_stream` → `TOK.tokenize` → `RunClock.begin_epoch`. The root also stamps `clock.opt_steps` here as the `shift_at` `OPT.maybe_step` consumes — a resample is a **self-inflicted** shift, and the old tree carried that fact in a closure variable (`:6518-6521`). |
| `A` | per WINDOW, above the accumulator | unchanged rows, plus `MEM.census` (before `DOM.manage`, whose `memory_counts`/`mem_floor_entries` had **no producer**), `DOM.census` (after it, supplying `live_sources`), `MEM.judge`, `SIG.cadence_due` → `SIG.train_step` (before `encode`), and `DOM.rekey` (after `observe`). |
| `B` | per FLUSH | unchanged rows, plus `TOK.judge_probation`, event-driven on the `Due.probation` `TOK.on_window` already asked at `A`. |
| `C` | the CHECKPOINT FAN-OUT — an **event**, entered from `B` (periodic/SIGUSR1), `A` (a `BestAction`) and `R` (final) | the twelve `state_dict`/`state`/`vocab_state`/`stream_state`/`Retention.state`/`WORLD.geometry` calls that build the payload and the recorded manifest, then `TOK.save_vocabulary`, then `CKPT.save`. |
| `R` | once, after `Tick.finished` | `MEM.read(promote=False)` + `MEM.blend`, `DOM.prior`, both censuses, every `counters()`, `Cadences.ledger()`, `RUN.bench_summary`, and the `reason="final"` save. |

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
| `curve` | `EVAL.curve_period(ev)` ← `EVAL.curve_every` | EVAL |
| `dom.manage` | `DOM.manage_every` | DOM |
| `fab.manage` | `FAB.manage_every` | FAB |
| `dom.rekey` | **`MEM.rekey_every`** | MEM — delivered by the spine, with the `SIG.mode == "learned"` arm also evaluated here, because the old line made *two foreign reads in one line* (`:6688-6689`) |
| `ckpt` | `CKPT.save_period(ck)` ← `CKPT.every` | CKPT |
| MEM's probe/rekey | `MEM.probe_every`, `MEM.rekey_every`, compared inside `maintain` against a Windows `now` | MEM |

**One gate, one ask.** `Cadences.due` *records* the fire and returns True, so asking a second time
under the same key **consumes** the event — that is how a shared `_due` key made minting never fire
at all in the old tree. The management block therefore asks `dom.manage` **once** and runs four rows
inside that one answer: `MEM.census` → `DOM.manage` → `DOM.census` → `MEM.judge`.

Everything else that fires is **event-driven and says so**: `Retention.consider` (a curve value
arrived), `MEM.judge` (the management pass), `SIG.train_step` (`cadence_due` said yes),
`TOK.judge_probation` (`Due.probation`), `DOM.on_retokenize` (the RetokEvent), and the whole `C`
stage (a save site). **`SIG.cadence_due` is the one periodic gate that cannot go through
`Cadences.due`** — it selects between `train_every` and `train_every_idle` on `dense_window`, and
`due` takes one period — so it has **no ledger key**, and `SIG.counters` at stage `R` is the only
did-it-fire surface the encoder's cadence has. That is stated in its row rather than left for a
reader to discover from a missing ledger line.

### 3.6 `DEFERRED_ENTRY_POINTS` — seven, all EVAL

`{"PFX.entry": "the phase that will call it, and why it cannot be called now"}`. K6 reads it **both
ways**: an entry no row names is accepted, and an entry a row **now** names is reported as *stale*
and must be deleted. That is what stops it becoming the place orphans go to be forgotten.

| entry | phase | why there is no row |
|---|---|---|
| `EVAL.holdout_probe` | P5 | Needs `units_by_domain` drawn in **byte** coordinates from `Areas.holdout` together with a `logits_fn`, and the root has no join producing that pair. A row now would name a call whose arguments nothing supplies. |
| `EVAL.null_excess` | P5 | `real` and `permute` are produced by the verdict machinery, which is P6's. |
| `EVAL.generate` | P6 | `prompts_by_domain` has **no producer** among the 117 entry points. |
| `EVAL.coherence` | P6 | Runs on its own seeded `Sample`; nothing in the tree returns a `Sample`. |
| `EVAL.verdicts` | P6 | Three of four arguments — `silhouettes`, `affiliation`, `coherence_reading` — have no producer; the fourth, `domain_sizes`, comes from `DOM.census`, which stage `R` already collects. |
| `EVAL.wrongness_probe` | P6 | Takes a **copy** of the store so the instrument cannot edit what it measures; MEM's surface produces no copy, and adding one is a signature change. |
| `EVAL.verification_fit` | P6 | Same missing copy; its inner loop is genuine `units.Steps` and must never be compared against `curve_every`. |

**A later phase is not by itself a reason to defer** — `EVAL.curve_probe` is P5 and has an `A` row.
Each reason above is about an **argument with no producer**, which is the only kind of reason that
survives the backwards check.

### 3.7 What could NOT be placed, and is therefore reported rather than rowed

* **The self-inflicted-shift notification to the fabric.** At an epoch roll and at a retok the old
  tree calls `fabgrow.note_shift(step)` (`:6515`, `:7787`) to open a growth blackout. **No FAB entry
  point accepts it** — `manage`, `observe` and `grow_check` take `step_windows` and losses, not a
  shift event. `CAP.observe` takes a `blackout` argument, so the valve half of the mechanism has a
  route and the fabric half does not. Escalated as **Q-FAB-6**; no row was written for a call the
  frozen surface cannot receive.
* **A resegment for MEM at an epoch roll.** `MEM.maintain(resegment=...)` is documented for a
  *retokenization*. An epoch redraw is a new stream, not a new segmentation, and the old tree does
  not resegment the store there. Inventing the call would have been the easiest row in this edit and
  the least defensible.
* **`SIG.train_step`'s `reservoir`.** `sig/api.py:113-114` says the pairs are "drawn from ONE domain's
  reservoir by DOM", and **no DOM entry point returns reservoir windows** — `census` returns radii,
  counts and `comp_glob`. At `prototype_frac = 0.0` (the default) nothing is lost; above it,
  `sig.prototype_pairs` reads 0 and the declared Gate must print *unreachable*, not *armed*. The row
  is written with `reservoir` optional, as the signature has it, and the gap is **Q-SIG-1**.
* **`residual_ratio` for the `embed` probation arm.** `tok/api.py:232-234` sources it from LM's
  `MintReport`, i.e. from **mint time**, when a new token's residual is zero by construction — so
  `keep iff earned AND residual >= probation_residual` would retire every candidate. The old tree
  recomputes it at judgement time from live tensors (`:7601-7605`), and **no entry point among the
  117 exposes that read**. The `B` row passes `residual_ratio` through; whether the arm is reachable
  is **Q-TOK-11**.

---

## 4. UNCONSUMED LEVERS

The union of the five `levers_unconsumed` lists is **15**. Thirteen of them were EVAL's, and all
thirteen were given a declared reader by writing the P6 instrument signatures into
`src/eval/api.py`. **Two remain, both FAB's.** Neither is silently dropped.

| lever | env name | why it has no reader | disposition |
|---|---|---|---|
| `FAB.hop_mode` | `FAB_HOP_MODE` | This contract ports the **soc** hop loop only, not the learned successor walk (the `R` matrix, per-expert `SRC` marks, the `ctrl` summary). The measurement points that way: `H(hop1\|hop0)` was **0.533 bits** over 202k transitions on the soc loop against **0.005–0.058** on every arm that used the transition matrix — one decision then a fixed successor. Three other levers were inert *only* because the transition arm was not the default (`hop_sup` reads `fab._hops`, the mid-chain spawn reads `fab._hopq`, and `:8399-8401` claims the default path *is* the transition matrix), but those records are about **wiring, not the mechanism**, and the owner has ruled that a mechanism never observed to fire is not thereby proven useless. | **P4 collects per-hop states on the soc loop**, which makes `hop_sup` reachable on the path that runs (a one-line repair). `FAB_HOP_MODE` itself is escalated: **Q-FAB-1**. It must not ship inert — a knob whose only effect is an error message is the armed-but-inert family with better manners, and it reads as a live capability in `docs/04_LEVERS.md`. |
| `FAB.merge_dist` | `FAB_MERGE_DIST` | The only merge-rather-than-kill mechanism in either expert population — the legacy router averaged the two adapters and summed their use, so both experts' learning survived where culling destroys it (`:3063-3085`). That is a **goal-B** argument and a strong one. But the fabric has no merge today (`manage` does cull and spare only; `xover` is birth-from-parents, not consolidation of two live nodes), and the mechanism has a consequence **outside this package**: memory ownership is `expert_id % n_own`, so merging two experts changes which owner block holds whose entries, and `remove()`'s swap-with-last renumbering compounds it. **A merge specified without the MEM contract is a silent-overwrite record waiting to be written.** | The lever's own comment sets the condition: *"IF THE FABRIC DOES NOT GAIN THE MERGE AT PORT, this must return to the census as a drop rather than ship as an inert default."* The join found what it needs: **one named MEM entry point, "reassign the entries owned by expert i to expert j"**, which `MEM.apply_domain_plan` is shaped like but does not cover. Escalated: **Q-FAB-2**. |

**Not unconsumed, but stated so a grep does not misread it:** `MEM.owners` is read by
`spine/assemble.py` to compute `d_owner_blocks` and `d_capacity`, and by nothing in `src/memory/`.
It changes both wires and the whole partition, so it is fully consumed — through the wire.

---

## 5. FOR THE OWNER

Unioned from the five specs, deduplicated, with everything resolvable from the source already
resolved above. What is left needs a ruling.

### Q-CLOCK-1 — retire `FAB.d_cap_lift_period` and `TOK.d_cap_lift_period`?
Three specs recommend it. This contract **keeps both rows as reporting wires** and adopts pin-clock
repair (a) so the valve reads neither. **Options:** (a) keep as reporting wires (what is written);
(b) delete both rows, freeing 2 of the 25-wire budget and removing the trap where a later reader
re-connects them; (c) retarget to `CAP`, which would be wrong — under repair (a) a converted period
is the 16×-early fault. **Recommendation: (b) once the owner confirms the valve is CAP's alone**,
because a row nothing but the report reads is a row a future author will "fix" by connecting it.
Changing a declared ledger row is the owner's call.

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

### Q-DATA-4 — `data/continual/` and `data/ood/` are unreachable from any DATA lever
`datastream.py:72` hardcodes `{data_dir}/train/{d}/*`. The repository ships
`data/continual/{01_rust,02_sawyer,03_dracula,04_num2}` (1.5 MB) and `data/ood/` (764 KB) — **the
material the add-an-area benchmark exists for** — and `grep` finds them read only by
`archive/legacy/*`. D2 makes PURE_ADD the default protocol; the areas prepared for it are
unreachable except by moving files on disk, which is a configuration change no Sample can record.
**Recommendation:** allow an `areas` entry to contain a `/` and join it under `dir` verbatim, with
`train/` remaining the implicit prefix when there is no slash (`DATA_AREAS="eng,continual/01_rust"`).
The area **label** is the basename, with a startup refusal on a collision. It adds no lever and no
default moves, but it changes what a declared lever's string means.

### Q-DATA-7 — how is D2 (PURE_ADD) actually produced?
`PURE_ADD` is not and never was a knob (0 occurrences in `self_organize.py`); it is `longrun.sh`
shorthand expanding to `PHASE_SCHED="1|1|1|1"`, and only because that harness runs exactly two
areas. **Options:** (a) the last entry of `DATA.areas` is the arriving area — general at any n, no
new lever, but it makes area ORDER load-bearing in a way nothing states today; (b) infer it from
`CKPT.resume` — refused, a cross-package read of a value DATA does not own; (c) require the launcher
to write the schedule explicitly and have the resolver only **name** what it was handed.
**Recommendation: (c) now, (a) later.** (c) cannot be wrong and gets the protocol name onto the
Sample immediately, which is the part D2 actually needs.

### Q-DATA-6 — the held-out split becomes a seeded random block
`holdout_frac` currently takes the **last** fraction of each area, which is a sample only if the
corpus was written in no particular order. Measured: py held out at **5.061 ± 0.560** against 2.922
in-stream while eng (shuffled upstream) was 2.273 against 2.303 — the gap was the ordering, and the
run reported it as a property of Python. This contract writes the seeded-random-block rule into
`open_areas`. **The consequence must be stated loudly: every historical held-out number becomes
non-comparable with the rebuild's**, because the text being scored changes. That is a deliberate
break and the Sample must carry the split rule so the two eras are distinguishable rather than
silently mixed. **Confirmation requested.**

### Q-DATA-8 — steps per epoch, and what a "window" is measured in
`steps = STREAM_LEN // WIN` (`:4317`, `:4719`) divides a **byte** budget by a **token** window.
Under `mode="bytes"` a window really is `LM.ctx` bytes; under `fixed`/`online` it is `LM.ctx`
**tokens**. So "a window is WIN bytes" is true on one arm of one lever and false on the others, and
the overstatement is the compression ratio (~2.5× at a grown vocabulary) — which the LR horizon and
every ETA were computed from. This contract computes `run_windows` from the token stream that
actually exists (`_run_windows` in `compose.py`). **Confirmation requested**, with the report
printing `stream_bytes`, the resulting step count and the measured bytes/token together.

### Q-TOK-3 — does `dropout` reach the training stream, or only the build tallies?
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

### Q-TOK-9 — `build_passes` had a per-arm default (2 online, 8 offline)
`:1225` is `_passes = _i("SEED_PASSES", 2) if TOK_ONLINE else _i("GROW_PASSES", 8)`. A Lever carries
one default. `tok/levers.py:284-289` proposes carrying the 8 "inside this package's build code",
which is a second literal in a second place — the thing L1 exists to end. **Recommendation:** one
literal (2) on both arms, with a startup line saying the offline build historically used 8 and
recommending `TOK_BUILD_PASSES=8` for `mode="fixed"`. A value the operator cannot see in
`docs/04_LEVERS.md` will disagree with the registry within a month.

### Q-OPT-1 — `run_windows` as an argument
Recorded and acted on above (see §0, refused candidates). **The ask:** add a `NOT_WIRES` row for
`d_run_steps` with the *measurement* reason, so the next reader does not have to re-derive that the
rejection is real and is **not** the `RUN.epochs` one. The contract phase did not add it because
`NOT_WIRES` is prose about candidates, and adding a rejection is as much an owner statement as
adding a row.

### Q-OPT-2 — the LR schedule indexed by optimizer steps
At the shipped defaults (`batch_windows=1`, `accum=1`) the new counter and the old one are
identical, so **no recorded result moves**; at `fetch_big.py`'s own recommended heavy-run command
(`WIN=256 BATCH_W=16 ACCUM=4`) they differ by **64×**, and one of the two readings makes a warmup
written in steps complete 64 times sooner than it says. This contract adopts the honest counter.
**Belongs on P9's list of numbers that moved, with this reason attached.**

### Q-OPT-3 — nothing in this system clips gradients
Verified by exhaustive grep: no `clip_grad_norm_`, no `clip_grad_value_`, no manual norm clamp
anywhere in `self_organize.py`; every match for "clip" is prose. Neither package declares a lever
and the census has no dropped row for one. This matters because unclipped gradients are a **second,
independent** explanation for the exact curve shape `lr_sched` exists to ablate (bottom ~2.4 at step
6000, rise to 3.8–4.1 by 48,000) and the two are confounded. **What this contract does without a
ruling:** `OPT.counters` reports the observed global gradient norm (`opt.grad_norm.p50/p99`), which
costs one `torch.norm` per step, needs no lever, and answers the question with data before anybody
argues about a default. **Minting `OPT_GRAD_CLIP` is escalated** — the census never voted on it.

### Q-LM-9 — the gru arm's third dropout site is the memory-key source
`:1556-1558` has three dropout sites and the lever's help text names two. The **third** drops out the
returned hidden state, and the source's own comment on that line says `(B,L,D) hidden -- also the
memory-key source`. So with `dropout > 0` the memory keys written during training are computed from
a dropped-out hidden state while the keys used at eval are not — **a train/eval key mismatch in the
store goal B is measured on.** Inert at the 0.0 default. **Ruling needed:** should the output dropout
apply to the memory-key path? It is LM's lever and MEM's blast radius, and no wire records it.

### Q-FAB-1 — port the transition hop arm, or drop `FAB_HOP_MODE`?
See UNCONSUMED above. **Options:** (a) port both arms (cost: `SRC_p` as a live parameter, the `R`
softmax, `ctrl`, per-hop query bookkeeping, and a second forward to keep correct); (b) port `soc`
only, drop the lever to `docs/dropped_levers.md` with the 0.533-vs-0.058 measurement as the reason,
and make `hop_sup` reachable by collecting hop states on the soc loop; (c) keep the lever as a
startup refusal. **Recommendation: (b).** (c) is the worst of the three — it looks like a live
capability in `docs/04_LEVERS.md`.

### Q-FAB-2 — does the fabric gain the merge?
See UNCONSUMED above. **Recommendation: implement it in `selection.py` before the cull, over the
eligible set, on cosine distance in identity space — but only with an explicit MEM entry point
"reassign the entries owned by expert i to expert j".** If MEM's spec does not offer one, drop the
lever and say so in `docs/dropped_levers.md`. This is the one item the specs handed to the join
rather than deciding, and the join can now name exactly what it needs.

### Q-FAB-5 — splitting `use` from `uage` re-denominates `grace`
`grace=48` was set against a clock that ticked once per window for the argmax expert only.
Crediting `chain_k` experts per hop over `hops` hops makes it tick up to **32× faster**. The split is
required — without it, eligibility and the cull's ranking key are the same number (H12) and every
non-argmax expert is permanently uncullable (H13) — but the level is now wrong. **Recommendation:
split as specified and flag the re-tune as required**, on P9's list. Re-expressing `grace` as a
multiple of `chain_k × hops` is tempting and wrong: that makes it a computed value of two other
levers, which is the L1 defect.

### Q-MEM-4 — `pressure()` cannot reach `pressure_thresh`
H33: every write lands on probation, only retrieval promotes, probation is over budget (measured
82% of the store), eviction takes the probation branch almost always, and `pressure` reads ~0
whatever the store is suffering. D3 keeps the pressure-signal rule as a selectable arm, and **an arm
needs a threshold that can fire**. **Recommendation: keep the definition, print the Gate's
arithmetic, and MEASURE BEFORE RETUNING** — capacity is now 8,192, not the 200,000 the pilot ran at
(11.7M writes against 1,469 probes), so at the same probe rate promotion covers a far larger share
of the store per pass and the region may sit inside its budget for the first time. Changing an
instrument's definition and its configuration in one step is how this project produced numbers
nobody could attribute.

### Q-RUN-1 — the progress/ETA log cadence has a described owner and no declaration
`eval/levers.py` says the split is deliberate and that the progress line takes "a separate RUN-owned
log cadence"; `train/levers.py` states, as a testable claim, that **RUN declares no cadence and no
threshold**, and the census gives RUN no such row. **Recommendation: a fixed module constant in
`src/train/` (`PROGRESS_WINDOWS`), documented as a property rather than a knob**, the way
`PLATEAU_WARM = 1000` is justified. A progress line is a property of a human watching a terminal;
nothing in the two goals turns on it. If it later needs to be tunable, that is one census row and
one lever, added deliberately.

### Q-RUN-7 — `RUN.bench`'s second job
`prompt.py:41` sets `os.environ["BENCH"]="1"` before importing `self_organize`, purely so that
sampling from a checkpoint does not trigger a full report. **Recommendation: "do not run the report"
is the entry point choosing which half to run, not a lever.** `bin/sample` calls the composition
root with the battery disabled; `RUN_BENCH` keeps only its throughput meaning. One flag doing both
jobs is how the throughput arm and the sampler ended up sharing a switch — and `prompt.py` then
receives the frozen EVAL Config instead of re-reading the environment, which also removes its own
`GEN_LEN` and `GEN_TEMP` second defaults.

### Q-WORLD-6 — WORLD's Windows-denominated cadence
`FAB.manage_every` reaches WORLD through RUN's `Cadences.due` and no period enters WORLD's Config
(§1, C3). **If the owner wants the reach visible in `affects()` — and it should be — that is one new
row, `FAB.manage_every → WORLD.d_manage_period_windows`, valued `Windows(manage_every)`.** The
contract phase left it out because the composition root already imposes the ordering and the budget
question belongs to whoever also rules on Q-CLOCK-1.

### Q-WORLD-8 — `soft_cull`'s irreversibility: which half gets fixed?
M69 says `alive` is only ever written to 0.0 and nothing restores it; M70 says `grow()` counts
**total** predictors against `nmax`, not live ones. **Fixing both** lets the population oscillate at
the cap indefinitely, minting and culling. **Recommendation: fix M70 only** (count live), leave
`soft_cull` one-way, and **rename it and its docstrings so they stop claiming reversibility** — both
currently say "reversible: params kept". A dormant predictor that still costs forward compute and
gradient while contributing ~1e-6 of the blend is a real cost, and the honest repair is a hard
routing penalty, not resurrection. `ManageResult.live` vs `n()` is the number that says whether the
population has silently become mostly dead.

### Q-EVAL-5 — the curve probe's sample size
`:6396` draws `range(16)` while `EVAL.curve_every`'s own help text quotes that 16 **as though it
were declared**. This contract reads `ev.windows`, which raises the default probe cost 4× and makes
every recorded curve number incomparable. **Recommendation: read the lever.** The old `EVAL_N` was
*unraisable* — five of its six readers wrapped it as `min(24, EVAL_N)` or `min(48, EVAL_N)`, so
`EVAL_N=256` drew 24 — and hardcoding 16 here rebuilds exactly that. The 4× cost belongs in the
equivalence report as a number expected to move.

### Q-EVAL-9 — does `holdout_windows` stay at 32?
`research_continual_memory.md:743-745` warns that the 2σ rule at n=32 will report "HELD (inside the
noise)" for real effects of moderate size, and recommends 128–256 if a null result is going to be
published as a claim. **Recommendation: leave it at 32**, because that is the literal the runs used,
and raise it only after G2 has measured this machine's noise floor. Raising it silently would change
what every recorded retention number means.


### Q-CKPT-1 — the geometry manifest has one producer and eleven packages
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

### Q-OPT-4 — `OPT.build(resume=...)` and `OPT.load_state(opt, st, saved)` overlap
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

### Q-OPT-5 — the horizon is a projection and the epoch length is a measurement
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

### Q-MEM-8 — which management cadence does `MEM.judge` run on?
`memory/api.py:253` says *"the management cadence the spine already imposes; no new lever (see FOR
THE OWNER Q-MEM-8)"* — **and Q-MEM-8 did not exist in this document.** It does now. The spine
imposes two: `DOM.manage_every` (100 Windows) and `FAB.manage_every` (500 Windows). `LOOP_ORDER`
places `judge` as an **event on the `dom.manage` pass**, immediately after the plan is applied,
because that is the moment the store's provenance has just been rewritten by folds and deletions —
so it invents no key and reads no foreign period at the call site, the spine delivers the event.
**Options:** (a) the `dom.manage` pass (what is written); (b) `fab.manage`, 5× cheaper; (c) a new
`MEM.judge_every`, which the docstring explicitly forbids. **Recommendation: (a)**, with the cost
noted: `judge` is a forward pass over checked entries and 100 Windows is the shorter of the two.

### Q-MEM-9 — does `MEM.maintain`'s read probe call `MEM.read`?
`maintain`'s job 1 is *"probe_rows real retrievals against probe_contexts"*; `read`'s own docstring
says `promote=False` is *"the read that MUST NOT MOVE THE STORE… the report path uses it"*, which
implies the in-loop probe is `promote=True`. The `B` row states it that way, because if the probe
open-codes a **second** retrieval then `n_reads`, `n_promoted` and the three `wrong_*` counters
describe one path while the store is moved by another — the C8/C9 shape one layer down.
**Ask:** confirm in `maintain`'s docstring that the probe **is** `read(promote=True)`. K6 cannot see
an in-package call, so prose in the row is the only place this can be written down today.

### Q-MEM-10 — `MEM.blend` returns probabilities; every scoring hook takes `logits_fn`
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

### Q-TOK-10 — `TOK.save_vocabulary` takes no suffix, so M46 is not closed
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

### Q-TOK-11 — `residual_ratio` is sourced at mint time, when it is zero by construction
`judge_probation`'s `embed` arm keeps a token iff `earned AND residual_ratio[t] >=
probation_residual`. `tok/api.py:232-234` sources `residual_ratio` from LM's `MintReport`, produced by
`LM.on_mint` **at the moment the row is created**, when the free residual *starts at zero* — so the
arm would retire 100% of candidates. The old tree recomputes it at judgement time from
`model.compose.table()` and `.delta` (`:7601-7605`), which is the right measurement: *how much this
token had to become that its parts did not already say* is a question about training that has
happened. **No entry point among the 117 exposes that read.** **Options:** (a) add
`LM.residual_ratios(lm, model)`, a pure read — a signature-set change; (b) cache the last
`MintReport` — this is the bug; (c) leave `residual_ratio=None` and let the declared Gate print
*unreachable (no residual_ratio supplied)*. **Recommendation: (a)** when the surface opens, (c)
until then — and (c) must be printed, because M41 is the record of what happens when the embed arm
silently runs the `use` test while the banner says `embed`.

### Q-SIG-1 — `prototype_frac` has no supplier and is therefore structurally unreachable
`SIG.train_step`'s `reservoir` is documented as *"a list of (window, window) pairs drawn from ONE
domain's reservoir by DOM"*, and **no DOM entry point returns reservoir windows** — `DOM.census`
returns radii, counts, `comp_glob` and `collapsed_at`. At the default `prototype_frac = 0.0` nothing
is lost; above it, `sig.prototype_pairs` reads 0 forever. **Options:** (a) add
`DOM.reservoir_pairs(...)` — a signature-set change; (b) carry the reservoir on `DOM.census`, which
runs on the 100-Windows management cadence while `train_step` runs per window, so the sample would
be up to 100 windows stale and *"two windows the assembler already believes belong together"* would
no longer be true; (c) declare the arm unreachable and print the reason.
**Recommendation: (c) now, (a) when the surface opens.** Do not fake it with (b).

### Q-OPT-6 — does `OPT.maybe_step` step the ENCODER optimizer?
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

### Q-OPT-7 — `OptState` declares "both AdamW instances" and names neither
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

### Q-FAB-6 — nothing can tell the fabric a shift was self-inflicted
At an epoch roll and at a retok the old tree calls `fabgrow.note_shift(step)` (`:6515`, `:7787`) to
open a growth blackout, so the loss jump *we caused* does not read as a distribution the fabric must
grow into. `CAP.observe` takes a `blackout` argument, so the **valve** half has a route.
**No FAB entry point accepts a shift event** — `manage`, `observe` and `grow_check` take
`step_windows` and losses. So `LOOP_ORDER` has no row for it, and this is recorded rather than
invented. **Options:** (a) add a `shift_at`-style keyword to `FAB.manage` — a signature change;
(b) route it through the existing `blackout`-shaped path if `grow_check` can be given one;
(c) accept that fabric growth treats a resample like new material. **Recommendation: (a)**, and
until then the report must say the blackout is unreachable rather than armed.

---

## 6. What `tests/test_contract.py` checks

| check | what it proves | how it can fail |
|---|---|---|
| K1 | every name this document declares exists in the tree **with the signature it claims** | rename a parameter; drop a function |
| K2 | `spine.compose` imports and `compose()` raises **only `NotImplementedError`, from a stub** | a typo in the root surfaces as `AttributeError`/`TypeError`, not as a missing body |
| K3 | no package imports another (O10 restated at the contract boundary) | add `from fabric import api` to `src/memory/` |
| K4 | every one of the 259 declared levers is named `LEVERS READ:` by a stub, or is in the UNCONSUMED table above **with a reason** | declare a lever and give it no reader |
| K5 | every `d_` field the ledger declares is read by a stub in its own package, and no stub reads an undeclared one | add a wire nobody consumes |
| K6 | every entry point is **named by a row** in `ASSEMBLY_ORDER` or `LOOP_ORDER`, or is in `compose.DEFERRED_ENTRY_POINTS` with a reason | declare a mechanism the root never calls; or leave a deferral in place after a row starts naming it — the check reads that table **backwards** and reports the stale entry |

**K6 is the check K4 is not, and the gap was 56 entry points wide.** K4 asks whether some stub's
docstring *names* a lever; K6 asks whether that stub is ever *called*. K4 passed at 257 named / 2
unconsumed / 0 unaccounted while nothing trained the signature encoder, nothing read memory, nothing
called `DOM.rekey`, and nothing drew a stream. Reading them together: a lever is accounted for when
some stub names it **and** some row reaches that stub. K6 still cannot see whether the loop, once
written, executes a row — the tables are data and P4 writes the code — nor an entry point reached
only from inside another body, which is why `OPT.lr_at` is credited by being **named in the prose of
the row that calls it** (`OPT.maybe_step`, step 2) rather than given a row of its own.

Each carries a `_report()` line printing **the size of the population it examined**, and
`selftest()` trips every one of the six against a synthetic tree in a temp directory. That is not
ceremony: this repository has **sixty** untrippable guards on record, and one of them was written
into `tests/test_ownership.py` *by the patch that was fixing `tests/test_ownership.py`*. A check
nobody has watched fail is indistinguishable from a check that cannot fail.

---

## 7. THE FROZEN SIGNATURE SET

Everything above is prose about these 117 entry points. This block is the normative list, and
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
EVAL: curve_period(ev: Config)
EVAL: curve_probe(ev: Config, *, units_by_domain, logits_fn, rng)
EVAL: holdout_probe(ev: Config, *, units_by_domain, logits_fn, rng)
EVAL: null_excess(ev: Config, *, real, permute, rng)
EVAL: generate(ev: Config, *, logits_fn, prompts_by_domain, rng)
EVAL: coherence(ev: Config, *, logits_fn, sample, rng)
EVAL: verdicts(ev: Config, *, domain_sizes, silhouettes, affiliation, coherence_reading)
EVAL: wrongness_probe(ev: Config, *, store_copy, scorer, rng)
EVAL: verification_fit(ev: Config, *, store_copy, rng)
FAB: build(fab: Config, *, d_model, signature_dim, device, generator)
FAB: forward(fab: Config, pop, *, h, signature, novelty, head=None, targets=None, step_windows, domain_id, live_domains, training, hold_out=None)
FAB: observe(fab: Config, pop, out, *, per_window_loss, domain_id)
FAB: contribution(fab: Config, pop, *, h, signature, novelty, head, targets, baseline_loss, baseline_logits_fn, step_windows, domain_id, live_domains, candidates)
FAB: manage(fab: Config, pop, *, step_windows, flush_loss=None)
FAB: grow_check(fab: Config, pop, *, flush_loss, step_windows, soft_cap, memory_pressure, signature)
FAB: own_lr_scale(fab: Config, pop, *, applied_lr)
FAB: counters(fab: Config, pop)
FAB: state_dict(fab: Config, pop)
FAB: load_state_dict(fab: Config, pop, sd, *, sidecar)
LM: resolve(lm: Config)
LM: build_model(lm: Config, geom, *, device, seed)
LM: encode(lm: Config, model, x, *, n_layers=None, extra=None)
LM: decode(lm: Config, model, h, *, live_vocab, retired_ids)
LM: lm_loss(lm: Config, logits, y)
LM: anchor_term(lm: Config, model, *, token_seen)
LM: on_mint(lm: Config, model, mints, id2bytes, *, at_window, sig_emb=None)
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
OPT: build(opt: Config, *, param_groups, run_windows, resume=None)
OPT: lr_at(opt: Config, st, opt_step)
OPT: scaled_backward(opt: Config, st, total)
OPT: maybe_step(opt: Config, st, *, best_bpb=None, shift_at=None)
OPT: counters(opt: Config, st)
OPT: state_dict(opt: Config, st)
OPT: load_state(opt: Config, st, saved)
RUN: process_setup(run: Config)
RUN: mode(run: Config)
RUN: streams(run: Config, subsystems)
RUN: new_clock(run: Config, *, batch_windows, accum, resume_step=0, resume_epoch=0)
RUN: RunClock.begin_epoch(self, windows_in_epoch)
RUN: RunClock.advance(self)
RUN: RunClock.note_backward(self)
RUN: RunClock.counters(self)
RUN: new_cadences(run: Config)
RUN: Cadences.due(self, key, period, clock)
RUN: Cadences.ledger(self)
RUN: bench_summary(run: Config, clock, *, elapsed_s, bytes_per_window, n_params, timing=None)
RUN: startup_refusals(run: Config, *, disk_stream)
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
TOK: on_window(tok: Config, vocab, ids, *, step)
TOK: mint_burst(tok: Config, vocab, *, step)
TOK: judge_probation(tok: Config, vocab, *, step, appearances, residual_ratio=None)
TOK: lift_vocab_cap(tok: Config, vocab, *, to: int)
TOK: save_vocabulary(tok: Config, vocab)
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
