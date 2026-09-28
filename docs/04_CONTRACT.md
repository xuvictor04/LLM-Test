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

`tests/test_contract.py` parses those blocks. **All 273** of the declared levers are named by at
least one stub as read by it — **261, not 259, since 2026-09-02: there are now TWO CENSUS
AMENDMENTS, `OPT_GRAD_CLIP` under Q-OPT-3 and `MEM_JUDGE_FRAC` under Q-MEM-8** (see
`.rework/CENSUS.md`, section `amendments`, which holds both and states that the census's 328 is
unchanged by either; *2026-09-26: that section now holds eight — `DATA_DRAW` (P1-H58) and
§8 1.4's five OPT levers, `OPT_HORIZON_REVISE`, `OPT_LR_CONTINUE`, `OPT_LR_PLATEAU`,
`OPT_LR_REWARM` and `OPT_LR_CONT_WARM`, under Q-OPT-12, each with a reader*) — and
**261 read, not 258, also since 2026-09-02**: Q-FAB-1 and Q-FAB-2 gave the last two unread levers
(`FAB.hop_mode`, `FAB.merge_dist`) readers rather than dropping either, so **UNCONSUMED LEVERS**
below is now an empty table with the two rulings under it. K4 reads that table, so a future lever
with no reader still lands there with a reason or the check fails.
**Naming is not calling**: which stubs the composition root actually reaches is section 3, and 118
of the entry points (§7 holds the count, and it is the only place that does — this sentence was one
of five copies) are named by a row — 102 in a row's entry column and 16 by a call written
into a row's note (2026-09-26, after 03b S0b's act rows and its MEM remap) — with the remaining
**18 declared deferred**, each with the argument that has no
producer as the reason. That number was seven until the order tables grew a `produces` column and
the same standard was applied to every row rather than to EVAL alone (§3.6). *(This sentence said
"14" while `DEFERRED_ENTRY_POINTS` held 15; corrected 2026-09-02. K6 prints all three numbers, so
the count is checkable from the suite rather than from here.)*

**Executable today.** `python3 -c "import sys;sys.path.insert(0,'src');from spine.compose import
compose; compose(environ={})"` runs the composition root through all 41 rows in `ASSEMBLY_ORDER` and
returns a System at stage `'assembled'` with no refusal — measured 2026-09-27. *(Until Q-EVAL-12's
review this said it stopped with `NotImplementedError: CAP.startup_refusals: P4 (capacity) fills
this in` at "the **29th** of the 41 rows": wrong twice, because `CAP.startup_refusals` has a body and
the `probe` row made it the **30th**. Before that it named `RUN.process_setup`, until 2026-09-04, and
had been wrong since that entry point got a body: the root then reached past the resume, the
corpus, the vocabulary, the model, the fabric, the store, the partition and `CAP.new_valve` before it
halted. Three further copies of the same stale claim — §3.8, §5's `Q-DERIVE-1`, and
`capacity/api.py::<module>` — were corrected in the same edit, both times. A claim about where the
root stops is a copy of a fact and rots the way a count does; **K13 could not see any of the four**,
because what rots here is a symbol name and K13 reads digits.)*

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
| `LM.d_max_token_bytes` | `TOK.max_bytes` | `ByteComposer.__init__(s, d, maxb=16)` at `:1441` is constructed as `ByteComposer(d)` at `:1549` so the default always wins, and `:1487` truncates. With `MAX_TOK > 16` two long tokens sharing their first 16 bytes get **identical composites** — the composer's whole property, inverted, silently (ISSUES P1-M21). `lm/levers.py::<module>` names `d_max_token_bytes` as an incoming value it expects. `tok/levers.py::TOKLevers` recorded this coupling as *not in* `spine/assemble.py::COUPLINGS` until 2026-09-06 — it has been a row since, so the luck the defaults were running on has been replaced by the wire, and that comment now says so. |
| `CAP.d_expert_slots` | `FAB.slots` | `CAP_FAB_START = 0` is a **sentinel meaning "start at the hard ceiling"**, and `lever.py` refuses a default computed from another lever — so 0 stood for a number nothing supplied. `capacity/levers.py::<module>` records the row as declared and read by `capacity/api.py::new_valve`; it said the opposite — that CAP had no wires at all — for several commits, and the correction is dated in the file. |
| `CAP.d_vocab_slots` | `LM.vocab_slots` | The same sentinel on the other target. `capacity/levers.py::CAPLevers` records that TOK holds no ceiling of its own to give — the census moved `VMAX` to LM as `LM_VOCAB_SLOTS` — so the wire is `d_vocab_slots` from LM and a row declared against TOK would fail at `build()` and read like a missing lever. |
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

## 0.5 What a lever DECLARATION can refuse, what it cannot, and the twenty-four orders of magnitude between them

**Added 2026-09-14.** Until this date a lever declaration carried a default, a unit, a help string
and an optional `choices=` enumeration, and nothing else — so every numeric refusal in this tree was
written by hand in the body that read the number, by whoever wrote that body, at whatever time they
got to it. Three mechanisms landed in `src/spine/lever.py` and they change what a declaration is
able to say. This section is what they are, what turning each off costs, and — the part that matters
more than the other two — **what none of them buys.**

### The three mechanisms

**`domain=(lo, hi)` on the declaration.** An optional keyword in the shape `choices=` already has:
checked at declaration against the lever's own default, checked again in `Lever.coerce` after
coercion, refusing with a `LeverError` that names the **generated** environment name and the value,
at the first read, before anything is derived from it. **The interval is CLOSED at both ends** — a
declaration needing an open end writes the closed pair that *contains* its interval and keeps the
strict clause at the read site, so the declaration under-refuses by exactly one endpoint and never
over-refuses. **Either end may be `None`, meaning unbounded on that side.** **Eight declaration
shapes are refused outright**, and all eight were planted at the constructor on 2026-09-14 and all
eight came back `LeverError`: a non-numeric default, a `domain=` that is not a pair, `(None, None)`,
a fractional endpoint on an int lever, an `inf` endpoint, a `nan` endpoint, `lo > hi`, and a default
outside its own pair. Four controls in the same run built: a closed pair, an open top, a negative
low end, and int ends on an int lever. **A tree carrying one of the eight does not import** —
`import spine.assemble` raises `LeverError: default 1.0 is outside its own domain [0.0, 0.5]`,
measured with exactly that plant in a scratch copy of `src/opt/levers.py`, which is why none of the
eight is restated as a check in `tests/`: a check for them could only ever fire on a tree that
`tests/test_census.py` and `tests/test_assemble.py` cannot import in the first place.

**Thirty-three levers carry one today, and they are exactly the thirty-three the research named.**
The set declared in the tree and the "both ends obvious" set in `.rework/audits/options_domain.json`
were compared name by name on 2026-09-14: 33 against 33, nothing in the report undeclared, nothing
declared the report did not name. The other **174** of the 207 numeric levers carry no pair, and
that is the honest state rather than an unfinished one — see the ceiling population below.

**`spine/lever.py::REFUSE_NON_FINITE_FLOAT` — the floor.** `nan`, `inf` and `-inf` are refused on a
**float** lever inside `Lever.coerce`. Its scope is the 97 float levers and nothing else: the 110
int levers already refused every non-finite spelling before this constant existed, because
`int(float(raw))` raises `ValueError` at `nan` and `OverflowError` at `inf`, and both are in
`coerce`'s except tuple. The same rule is stated a second time at the *declaration*, because a
literal `Lever(float("inf"), …)` default never passes through `coerce` at all.

**`spine/lever.py::REFUSE_INEXACT_INT`.** An int lever resolves to the integer its string denotes,
or it is refused. The rule is **losslessness, not notation**: `"8.0"` and `"1e3"` denote integers
exactly and resolve normally; `"0.4"` does not, and `"1e26"` does not either — `float` cannot
represent 10²⁶, so the value that would run is 100000000000000004764729344, a twenty-seven digit
number 4764729344 larger than the one typed. The class it closes is worse than the arithmetic:
`MEM_REKEY_EVERY=0.4` used to truncate to `0`, and `0` is that lever's **declared disarm**, so an
operator asking for the tightest cadence silently received the off switch with `Config.given()` still
reporting `'0.4'` beside a mechanism running at zero.

### Both constants are SWITCHABLE, and the switch is a code edit

This document already records, for `src/ckpt/api.py::REFUSE_NEGATIVE_PERIOD` and its four siblings,
that a refusal kept behind a switch is kept honestly and that the switch is not reachable from a
shell. **The same sentence is owed to these two and is written here.** There is no `SPINE_REFUSE_*`
environment name. Neither constant takes a census row, nor a row in the lever document `docs/04_LEVERS.md` is
planned to generate.
**An operator holding only a shell cannot reach either one**: turning either off means editing
`src/spine/lever.py` and rebuilding.

That is deliberate and the alternative was refused for a reason, not left unconsidered. A
lever-shaped switch is circular — these rules run *inside* `Lever.coerce`, before any `Config`
exists — so the only environment form available is a raw `os.environ` read inside `coerce`. That
read is legal in this one file and it is refused anyway: it would be the tree's first environment
name that is not a lever, invisible to `spine/registry.py`, to `tests/test_census.py`, whose N1 and
N2 join on lever names, and to the **planned** `docs/04_LEVERS.md` — which does not exist on disk
yet, and which three `levers.py` files already name as the consumer that will render these
declarations. That is precisely the failure `src/spine/lever.py`'s own header exists to end.

**What turning the floor off costs.** `nan`, `inf` and `-inf` resolve into frozen `Config`s again on
all 97 float levers. What is then left standing is the five per-package by-name refusals that exist
today — `src/fabric/api.py::build`, `src/sig/api.py::build`, `src/opt/api.py::build`,
`src/tok/api.py::build_vocabulary` and `src/data/api.py::data_plan` — and they cover only the levers
those bodies actually read. Roughly 288 cells across the six sweep reports are recorded
`UNREACHABLE_TODAY` because the consumer is a P4/P5/P6 stub, and **a body that does not exist cannot
refuse anything.** That is the cost and it is also the argument for the rule: a per-package refusal
is written by whoever writes the body, whenever they get to it; this one is written once, now.

**What turning `REFUSE_INEXACT_INT` off costs.** `int(float(raw))` truncates in silence again and
the `MEM_REKEY_EVERY` class comes back: a fractional cadence lands on a lever's declared disarm with
no warning and no record except the string in `given()`. Off is the pre-2026-09-14 behaviour exactly.

**`domain=` has no switch, and that asymmetry is deliberate rather than an omission.**
`src/spine/lever.py::<module>` states the ground in its own words — the two constants govern a rule
true of a whole declared TYPE, where `domain=` is a **per-lever judgement** whose *"blast radius is
one lever and deleting the kwarg is the switch"*. A reader should draw the consequence for D17 rather than
the comfort: a wrong pair is withdrawn by editing one declaration, and a wrong pair is therefore the
easy failure to reverse. The hard one is the pair **nobody wrote**, which no switch reaches and no
check reports, because `hi=None` is indistinguishable from a ceiling that was considered and
declined. **No check in the suite asks whether a lever's range was ever considered**: O14 and O15
both read `domain=`, and both have as their population the levers that **carry** one, so the 174
that do not are outside every check this section describes. `tests/test_census.py` joins on lever
NAMES and reads no other `Lever` field.

### The floor and the domain are COMPLEMENTS, not alternatives

A reader who has just been told there is a floor *and* a pair will reasonably assume one of them is
redundant. Neither is. **Any finite endpoint refuses `nan` for free**, because the comparison in
`coerce` is written as an inverted chain (`not lo <= v`) rather than as `v < lo` — every comparison
against `nan` is False, and `not` turns that into a refusal rather than a pass. **Only a finite HIGH
end refuses `+inf`.** Driven on one real float lever, the same five values, with the floor first on
and then switched off in the same process so the pair's own contribution is isolated:

| | `nan` | `inf` | `-inf` | `0` | `1e26` |
|---|---|---|---|---|---|
| floor ON, `domain=(0.0, 1.0)` | REFUSED | REFUSED | REFUSED | pass | REFUSED |
| floor ON, `domain=(0.0, None)` | REFUSED | REFUSED | REFUSED | pass | pass |
| **floor OFF**, `domain=(0.0, 1.0)` | REFUSED | REFUSED | REFUSED | pass | REFUSED |
| **floor OFF**, `domain=(0.0, None)` | REFUSED | **pass** | REFUSED | pass | pass |
| **floor OFF**, no domain | pass | pass | pass | pass | pass |

Read the fourth row. An open-topped pair with the floor off admits `+inf`, and **an open top is the
common case**: under an honest, evidence-led population `163 of the 207` numeric levers get no
ceiling, 53 of them floats (`.rework/audits/options_domain.json`). So `domain=` alone would leave
`+inf` legal on 53 float levers — including `OPT_LR`, `OPT_WEIGHT_DECAY`, `SIG_VAR_WEIGHT`,
`SIG_COV_WEIGHT` and `FAB_ROUTE_T`, five of the sweep's own critical findings. Neither rule is a
subset of the other.

### WHAT NEITHER BUYS, AND THE NUMBER IS NOT CLOSE

**Nothing in this section makes any lever safe, bounded or validated, and no docstring in
`src/spine/lever.py` says it does.** A reader who comes away from the three mechanisms above
believing the levers are now bounded has read this document exactly backwards, and the measurement
that says so is the reason the section exists.

**The finiteness boundary and the harm boundary are twenty-four orders of magnitude apart.** Driven
end to end, five stages per row (`.rework/audits/options_domain.json`):

```
OPT_LR=1.0     five stages OK   p_finite=True    p_sample=[0.7911476492881775, ...]
OPT_LR=100.0   five stages OK   p_finite=True    p_sample=[-0.07620048522949219, ...]
OPT_LR=1e6     five stages OK   p_finite=True    p_sample=[-3928.56640625, ...]     <- model destroyed
OPT_LR=1e20    five stages OK   p_finite=True    p_sample=[-3.933397707569234e+17, ...]
OPT_LR=1e30    five stages OK   p_finite=FALSE   p_sample=[nan, nan, nan]
```

`OPT_LR=1e6` sits **twenty-four orders of magnitude below the first setting on that ladder at which
this lever produces a non-finite parameter** (1e6 against 1e30), and fourteen below the largest
setting that ladder still records as finite (1e6 against 1e20). It passes every rule described
above, runs all five stages reporting OK, reports `p_finite=True`, and leaves every parameter at
−3928. `FAB_ALPHA=1e26` is finite, passes every rule described above, prints an
ordinary-looking loss pair — `aux 0.5150710`, `composed 2.943258` — and already leaves 15 of 23
gradient-carrying tensors non-finite, which is **worse** than `+inf`, since `+inf` at least comes
back `nan` where a report can see it. **No ceiling chosen to stop `nan` is a ceiling that stops
harm.**

And a ceiling mostly does not exist to choose. Of the 207 numeric levers, **131 have no derivable
ceiling at all** — the harmful value is a floating-point dynamic-range or memory property of the
mechanism and not of the declaration, so no honest reading of the declaration produces a number.
**15** have a high end that is *another lever or a wire* (`LM_CTX ≤ d_pos_max`,
`WORLD_N0 ≤ WORLD_NMAX`, `MEM_KEY_DEPTH ≤ LM_LAYERS`), which no per-lever pair can express; **16**
have a high end this tree has **explicitly declined to set**; and **1** has no ceiling at all.
*(An earlier revision of this section declined to quote those three parts, recording that the
published breakdown did not sum to its own total. Re-added on 2026-09-14: 44 + 16 + 15 + 131 + 1 =
207 and 16 + 15 + 131 + 1 = 163, so the high-end breakdown does sum, in both the part and the
whole, and the same holds of the low-end breakdown — 149 + 46 + 5 + 2 + 2 + 1 + 1 + 1 = 207. The
figures are quoted.)*

**Three things a reader must not infer from a `domain=`.**

1. **That the values inside it are safe.** They are not, and several of the thirty-three declarations
   say so in as many words. Each of the five settings below was driven through the real
   `spine.assemble.build` on 2026-09-14 in a fresh process and **every one resolved**:
   `TOK_DROPOUT=1.0`, which builds a vocabulary while skipping every available merge;
   `OPT_LR_RESTART_DAMP=1.0`, the identity at which no losing cycle can ever damp;
   `FAB_HALT_MAX=1.0`, precisely the absorbing state its declaration's comment exists to warn about;
   and `DOM_MERGE_DIST` at `0.12` and at `0.80`, the 8× fragmentation and the counterfeit-4 settings
   (purity 0.71) this tree has already measured and recorded as wrong. A pair bounds a **spelling**.
2. **That `U.FRACTION` means `(0.0, 1.0)`.** It does not, and this tree has ruled that way three
   times — `src/fabric/api.py::build`, `src/tok/levers.py::TOKLevers` and
   `src/capacity/api.py::new_valve` each say in their own words that the unit is a **label the
   census renders and not a bound**. 75 levers carry `U.FRACTION` and 5 carry `U.PROBABILITY`, and
   among them `OPT_GRAD_CLIP` is a gradient-**norm** threshold where 5.0 is ordinary, and `SIG_TEMP`
   and `EVAL_GEN_TEMP` are temperatures. Five of the thirty-three pairs that landed carry the
   `fraction 0..1` label and a declared domain of `(0.0, 2.0)` — `DOM_MERGE_DIST`, `DOM_SHIFT_DIST`,
   `DOM_SPAWN_DIST`, `FAB_DISCOVER`, `FAB_MERGE_DIST` — because every one of them is a **cosine
   distance** between unit vectors and runs on [0, 2]. A reflexive `(0.0, 1.0)` taken off the label
   would have refused a pooled radius of 1.24 that this tree has measured on this geometry. Two
   independent owners reached `(0.0, 2.0)` on their own levers without contact.
3. **That `0` is out of bounds because it looks like a disarmed setting.** 46 of the 207 have a
   declared or measured-legitimate zero (`.rework/audits/options_domain.json`, counted over all 207)
   — "never", "every window", "no cap", "start at the hard ceiling", "disarm" — and **only 22 of the
   207 mention their special value in the help string at all**, so the zero is learned from the
   reader's body and not from the declaration, and a reflexive `lo=1` deletes a working mechanism.
   Two levers have a genuinely **negative** natural low end:
   `EVAL_GENUINE_SIL` is a silhouette in [−1, 1] and `MEM_MATCH_FLOOR` is a cosine similarity, so a
   reflexive `lo=0.0` is simply wrong on both.

### What the suite now checks about it, including the part that is RED

`tests/test_ownership.py::check_o14_domain_endpoints_are_literals` requires every `domain=` endpoint
to be a literal. `_domain_ends` cannot see this, because it `isinstance`-tests the **value** and a
computed endpoint is a perfectly good number: `domain=(0.0, _CEILING)` and
`domain=(0.0, float(FabricLevers.slots.default))` are both accepted at declaration today, and the
second is a range endpoint read out of **another package's declaration** with no wire, no coupling
row and nothing in `affects()` to print it.

`tests/test_ownership.py::check_o15_domain_agrees_with_read_site` reads the hand-written refusals in
the package bodies and compares their intervals with the declared pairs, in both directions — a
declaration **narrower** than a refusal that pins both ends stops a configuration the shipped body
accepts, and a declaration that covers everything a refusal refuses leaves that refusal unable to
run again. **It went RED the hour the pairs landed, with six findings in four packages**, and that
was the check working rather than the check being wrong: the pairs were written after the refusals,
so `OPT_LR_DECAY`, `OPT_LR_RESTART_DAMP` (twice), `FAB_DISCOVER`, `SIG_WARMUP_MIN_FRAC` and
`TOK_DROPOUT` each had a by-name refusal the declaration now reaches first. A guard whose condition
cannot be satisfied is the **untrippable-guard family** — the second-largest class in this
project's founding census — so populating `domain=` did not merely find six of them, it **made**
them, in the same commit, and the check is the only reason anyone knows.

**THE FORK IS RETIRE-OR-DROP AND NEVER BOTH, AND IT IS DECIDED PER LEVER.** Either the read-site
clause is retired and everything it argued moves to the declaration, or the pair is dropped and the
ruling stays where it was argued. What is refused is keeping both and reading the dead one as a
second line of defence, because the second line cannot be reached from any environment and the
first one carries no argument. **Four of the six were closed by taking the RETIRE arm, each decided
on its own lever and not as one answer**, and in every case the measurement moved rather than being
deleted: `src/fabric/api.py::build` dropped its `_gated_off` entry for `FAB_DISCOVER` and
`src/fabric/levers.py::FABLevers` now carries what that clause knew, and `src/opt/api.py::build`
dropped `decay`'s inverted chain and both of `damp`'s clauses into `src/opt/levers.py::OPTLevers`.
Retiring was not a tidy-up in either place: the declaration refuses **more** than the clause did
— `FAB_DISCOVER=3.0` resolved on this tree until the pair landed — so dropping the pair to keep
the clause would have removed a working refusal to make a check green. One sentence did not survive
the move intact and is recorded as corrected rather than requoted: `damp > 1.0`'s message said a
value above 1.0 amplifies every failed restart, and `src/opt/api.py::maybe_step` guards its one
`st.restart_amp *= …` with `float(opt.lr_restart_damp) < 1.0`, so above 1.0 the loop goes inert
and amplifies nothing. **That prose had rotted while it could still print**, which is the sharpest
argument in this section against leaving a measurement inside a `raise`.

**Two are open, and they are named here rather than carried silently** — `SIG_WARMUP_MIN_FRAC` at
`src/sig/api.py::warm_up` and `TOK_DROPOUT` at `src/tok/api.py::build_vocabulary`, both owned
outside this document. Driven 2026-09-14 through the real `spine.assemble.build`, one configuration
per fresh process, and in each case the **declaration** is what answers:

```
SIG_WARMUP_MIN_FRAC=-0.5  LeverError: SIG_WARMUP_MIN_FRAC=-0.5 is outside its declared domain [0.0, 1.0] -- BOTH ENDS INCLUSIVE
SIG_WARMUP_MIN_FRAC=0.0   resolved        SIG_WARMUP_MIN_FRAC=1.0   resolved
TOK_DROPOUT=-0.5          LeverError: TOK_DROPOUT=-0.5 is outside its declared domain [0.0, 1.0] -- BOTH ENDS INCLUSIVE
TOK_DROPOUT=1.5           LeverError: TOK_DROPOUT=1.5 is outside its declared domain [0.0, 1.0] -- BOTH ENDS INCLUSIVE
TOK_DROPOUT=1.0           resolved        TOK_DROPOUT=0.0           resolved
```

`src/sig/levers.py::SIGLevers` describes that lever's negative end as *"refused TWICE now"*. Both
rules do exist; what the sentence does not say is that only one of them can be reached by setting an
environment variable, which is the whole of O15's finding and is why the fork is a **ruling** and
not a cleanup. `tests/test_fabric.py::check_f4_negative_magnitude_levers_refused` was the same fact
arriving behaviourally; it was repaired by moving its subject rather than its value — it still
drives `-0.5`, and now asserts **which layer owns which lever**, reads that split off the
declarations instead of a list typed into the test, and drives a second door where a `Config` built
directly reaches the body with no `coerce` behind it. `tests/test_fabric.py` is green.

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
named as such. **Because the loop owns it, the root checkpoints it** — under the payload key
`"LOOP"`, which no package owns — and `compose` puts it back on a resume (Q-CKPT-4); until 2026-09-24
nothing saved it and every resumed process started it at `None`.

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
and FAB. `src/domains/levers.py::DOMLevers.tokc_decay` already states the receiving end, in the
comment under its declaration: **DOM must not read this cadence;
the retok arrives as a SIGNAL.**

**Decision.** `on_window` returns `Due.retok`; the composition root calls `tokenize`, receives the
new `Segmentation` and a `RetokEvent`, and hands the event to `MEM.maintain(resegment=...)`,
`DOM.on_retokenize(...)`, SIG and FAB. No package other than TOK reads `retok_every`, and no package
other than the root knows who reacts. `LOOP_ORDER` in `spine/compose.py` is where that distribution
is written down. **As built (2026-09-24):** a mid-epoch `Due.retok` is deferred to the next epoch roll
(Q-RUN-8), and the roll is the act — `TOK.tokenize` re-segments, `MEM.maintain(resegment=...)` hears on
the first flush after it, and `DOM.on_retokenize(dom, part)` is its own `E` row, called when the match
table moved since the last segmentation (Q-DOM-2). SIG and FAB still have no retokenize entry point.

---

## 2. The packages

Each section: purpose, public surface, what it receives and from whom, state, checkpoint, counters.
The full prose — every measured defect, every line number — lives in the stub docstrings, which are
the normative text. This is the index.

### DATA — `src/data/api.py` (19 levers)

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
offsets and sizes and, since 2026-09-27, each block's digest (Q-DATA-9's review),
`bytes_present`/`bytes_taken`, the counter vector — all checkpointed. The cached
`Stream` at `resample=False` is **not**: it is rebuilt from `(seed, epoch)`. Nor is
`Areas.parent_names`, the area list the resumed checkpoint recorded, which `restore_stream_state`
fills in place from the record on every resume (empty on a fresh run; Q-DATA-9). **`Areas.drawn`
is** (2026-09-28, Q-FAB-18's review): every area the lineage's streams have drawn a byte from, in
the order first drawn — filled in place from the record by `restore_stream_state`, extended by
`draw_stream`, recorded by `stream_state`. A record written before it carries none, and every area
it declares is then assumed drawn and named in `data.drawn_assumed` ([] where the record carried
its list; ABSENT on a fresh run).
**Counters:** `data.area_open`, `corpus_cap_trip`, `holdout_block`, `val_cap_trip`, `area_refused`,
`stream_draw`, `segment`, `contig_wrap`, `resample`, `phase_entered`, `phase_resolved`,
`state_written/restored/refused` (with `state_written_here`, the process twin of the lineage
`state_written`, Q-CKPT-4), `holdout_admitted` with `holdout_admitted_names` (Q-DATA-9; seeded
only on a resume at `source="synthetic"`, `synth_holdout=True`, and ABSENT elsewhere),
`drawn_assumed` (Q-FAB-18's review), and three Gates (`exposure_max`, `exposure_skew`,
`splice_window`). **Printed at R since 2026-09-27**, in the root's `DATA(areas.counters)`,
`DATA(areas.gates)`, `DATA(plan.counters)` and `DATA(stream.counters)`
rows beside the older `DATA(stream.gates)` (Q-DATA-9); before that no row printed them.

**The schedule's faded sets (2026-09-28, Q-FAB-18; register §8 3.1, NEW-10 and C37).** `Plan`
gains `faded` — per phase, every area live in an earlier phase and not in this one (index tuples in
Plan order; `[(), (0,), (0,), (0, 1)]` on the generated four-area schedule) — and `parent_faded`,
the areas the resumed lineage drew (`Areas.drawn`; `Areas.parent_names`, every area the record
declares, until Q-FAB-18's review) that no phase of this schedule makes live.
Both are computed by `data_plan` at startup, move no byte of the stream and are not checkpointed;
they are printed as the readings `data.phase_faded` (every run) and `data.parent_faded` (only where
a parent record was restored). The root hands their union to `FAB.manage` as area ids. **An area's
id** is `spine/derive.py::area_id` of its label (crc32, 31 bits), the key FAB's area books and MEM's
area column share, and `open_areas` refuses two labels on one id beside the label and key
collisions, naming both and `data.area_id_collision`, whose Gate reads 0 beside
`data.area_label_collision`'s in every `Areas` that exists (Q-FAB-18's review).

**The synthetic source's held-out law is a lever (2026-09-27, Q-DATA-9).** At `synth_holdout=True`
`open_areas` runs the real sources' carve on each generated body **verbatim** — size, per-area child
stream, removal, seam, overlap, val-cap tally, and the 0-byte refusal (whose message then names
`DATA_SYNTH_HOLDOUT` too). At `False`, the build default until 04-Q5's flip, it holds nothing out,
as before, and the OFF record's `why` names `DATA_SYNTH_HOLDOUT=0`. **The resume admits one move:** a
record of key None and size 0 against a synthetic block now (a real one is a change of source and
stays refused), counted **per area** in `data.holdout_admitted` (a four-area parent admits 4), each
admitted area's `seg_contig` cursor mapped onto the carved body (below the block unchanged, past it
down by the block's size, inside it to the block's offset), and the parent's training on the
block's bytes said in a warning. A block then and none now is refused naming both settings that
write one, `DATA_SYNTH_HOLDOUT=1` and `DATA_SOURCE=real`.
`data.holdout_overlap` is this run's reading and is no longer overwritten by the parent's. **A
synthetic block rides on a generated body** (Q-DATA-9's review): its length is max(`seg_max` + 1,
5000, `stream_bytes` // `n_processes`) × 2, shared by every area, and its text is the alphabet the
area's position in `areas` picks. So on this arm a resume keeps the parent's length and the parent's
areas' positions — an added area is appended, with `stream_bytes` raised in proportion — or is
refused naming what moved; the admission holds only where both are the parent's; and on either
source the record's block digest refuses a text that moved under agreeing offset, size and key.

Two levers (`dir`, `corpus_cap`) are **arm-dead** under `source="synthetic"`, and two more
(`holdout_frac`, `val_cap`) are there at `synth_holdout=False` only; `n_processes` and `synth_holdout`
are arm-dead under `source="real"`. That is a declared arm reported through a Gate, not an unread
lever. (`seg_contig` was listed here as arm-dead under `source="synthetic"` until 2026-09-27, and it
is not: `draw_stream` reads it on both sources.)
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
| `tokenize(tok, vocab, data, labels=None, *, start=0, regularize=False, seed=0, view=None)` | DATA; compose's resume rebuild (`view=`) | `Segmentation` |
| `view_of(vocab)` | the loop's act; compose's segmentation log | `(size, retired)` — the match table's view, what a segmentation records so a resume can cut at it again |
| `splice(tok, vocab, seg, data, labels=None, *, at, regularize=False, view=None)` | the loop's mid-epoch act (stage X) | `Segmentation` — the unconsumed tail re-segmented, the consumed prefix kept (03b S0b) |
| `on_window(tok, vocab, ids, *, step)` | RUN (`Windows`) | `Due` |
| `mint_burst(tok, vocab, *, step)` | RUN | `list[Mint]` |
| `judge_probation(tok, vocab, *, step, appearances, residual_ratio=None)` | the loop, LM | `Judgement` |
| `lift_vocab_cap(tok, vocab, *, to)` | **CAP, as an event** | `int` |
| `save_vocabulary` / `vocab_state` / `restore_vocab` | CKPT | path / dict / — |

**Wires read:** `d_vocab_ceiling` (hard, on every path **including a resume**), `d_vocab_save_path`,
`d_vocab_read_path`, `d_cap_lift_period` (reporting only).
**State:** `merges` (append-only; the merge list **is** the mint log), the `seq2id` match table
(diverges from `id2bytes` after a retirement — which is why the retok skip test stamps
`(size, len(seq2id))` and not `size`), the pair tally and `tally_seen`, `prov`, `retired`,
`soft_cap`, `v0`, and the three cadence clocks (`tok.<key>_seeded_window`, kept in `counters` by
`_due`). **Where each crosses a checkpoint:** the merges and the measured `bytes_per_token` in the
vocabulary FILE (`save_vocabulary`), which a resume replays and whose recorded `bytes_per_token` it
**adopts** rather than re-measuring (Q-TOK-13), with the file's own ordinal, `vocab_saved`, which a
replaying resume restores as `tok.vocab_saved` (Q-CKPT-4), and since build 1.6's review a
`TOK_MODE=bytes` resume too, reading that one key; `prov`, `retired`, `soft_cap`, `v0`, the tally and
`tally_seen` (exactly, as parallel int arrays) and the counters in `payload['TOK']` (`vocab_state`),
put back by `restore_vocab` after its merge-count refusal. The match-table revision `rev` is
per-process and deliberately not carried. A save/load round trip **used to undo every retirement**
(D-T3) and **used to restart the tally from zero** (Q-TOK-13); both are carried now.
**The file rotates with `ckpt.pt<suffix>.prev`** (2026-09-26, register LOW-Q-TOK-13-PREV):
`save_vocabulary` moves `<base><suffix>.dyntok.json` to `<base><suffix>.prev.dyntok.json` — the path
`derive.checkpoint_base` resolves for `CKPT_RESUME=<dir>/ckpt.pt<suffix>.prev` — before the new file
lands, by CKPT's own rule (rotate iff the current file exists). A failed rotation still writes the
new generation. A run resumed from `<dir>/ckpt.pt.prev` that saves into `<dir>` rotates onto
`d_vocab_read_path` too, counted as `vocab_rotated_in_place` (corrected 2026-09-27; it skipped,
and the parent's newer generation lost its vocabulary). See Q-TOK-13's closing note.
**Counters:** `tok.build_pass/build_mint/v0`, `load_reconciled`, `bpt_adopted`/`bpt_mismatch`,
`tally_restored`, `mint` + eight mint-outcome counters, `retok`/`retok_noop`, `dropout_skip`,
`mint_frozen_at`, `probation_*`, `cap_lift`, `vocab_saved` (lineage) with `vocab_saved_here`
(process, Q-CKPT-4),
`vocab_rotated`/`vocab_rotate_failed`/`vocab_rotated_in_place` (per process, and read by the
report after the final save; `vocab_rotated_in_place` is present only on the in-place arm), `state_*`,
and Gates `mint_pmin` and `probation_embed`.

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
The counters were written and never read back until 2026-09-24; `load_state` now restores them
(except `lm.resolve.*`), and its `LoadReport` is bound by the root — a refusal stops the run (Q-CKPT-4).

A resume across a `compose` flip is **refused in both directions** and named — under compose,
`emb`/`head` are not constructed at all. That is a real operational restriction and P7's add-area
entry point must know it before planning an arm table.

### OPT — `src/opt/api.py` (19 levers, seven of them census amendments — `OPT_GRAD_CLIP`, §8 1.4's five and `OPT_DAMP_SOURCE`)

Owns every rate and the size of the batch it acts on. **OPT maintains its own optimizer-step
counter**, so `units.Steps` becomes literally true — and the horizon's `Windows→Steps` division is
`spine.derive.opt_steps_from_windows`. *(This paragraph said "no `Windows→Steps` conversion is
written — `spine/derive.py` has no such function, verified" until 2026-09-02. That was true when it
was written and stopped being true when the inline `run_windows // d_effective_batch_windows` in
`build`'s horizon block was named; corrected under Q-OPT-2, which is otherwise RESOLVED-as-already-
adopted.)*

`build` · `lr_at` · `scaled_backward` · `maybe_step` · `revise_horizon` · `counters` · `state_dict` ·
`load_state`. `revise_horizon` (03b S0b, Q-OPT-10) re-maps the rest of the schedule when the
mid-epoch act re-measures the run: LR-continuous, logged in `st.horizon_revisions`, checkpointed.

**Two §8 1.4 mechanisms, kept apart on purpose (Q-OPT-12, 2026-09-26; C01).** `OPT_HORIZON_REVISE`
(default `True`) is the in-run revision's off arm: at `False` `revise_horizon` is inert and counts
every declined revision (`opt.horizon.revise_inert`, `opt.horizon.revise_declined`), and it never
gates `load_state`'s resume revision. Since 2026-09-27 (build 1.4's review) it also KEEPS each
declined revision (`st.horizon_declined`, checkpointed) and counts one only where `True` would have
logged one; a continued run applies them to its log, so an act-parent's flag cannot move its
continued child's rate either (C01 through the parent). `OPT_LR_CONTINUE` (default `'as_logged'`) is
the rate a continued run starts at: at a **session boundary** — a resume `load_state` re-prices, i.e.
a horizon that differs from the checkpoint's or a new revision on a logged parent, and (since
2026-09-27) that does not continue the checkpoint's epoch mid-way — `'floor'`, `'plateau'`
(`OPT_LR_PLATEAU`, `OPT_LR_CONT_WARM`) and `'rewarm'` (`OPT_LR_REWARM`, `OPT_LR_CONT_WARM`) are
anchored into the checkpointed record `st.continuation` and priced by their closed forms;
`'as_logged'` is today's pricing, bit-identical; `'regulated'` is refused at `build` with `NotBuilt`
(NEW-04). Every resume prints the regime in force as the ledger label `opt.continue.regime`, and
(since 2026-09-27) the branch that priced it as `opt.continue.pricing`.

**`OptState` names its two optimizers `base` and `encoder`** (Q-OPT-7) — the same words as `build`'s
`param_groups` keys. `maybe_step` writes `lr` into **both** and steps **`base` only**; the encoder is
stepped by `SIG.train_step`, on SIG's cadence, behind SIG's InfoNCE floor gate (Q-OPT-6).

**Wires read:** `d_effective_batch_windows`.
**Receives:** `param_groups` (plain lists the packages returned — OPT never walks a module tree),
`run_windows`, `best_bpb` (a Reading carrying its seed count), `shift_at`, `saved`, and (since
2026-09-27, Q-OPT-12) `continuing` — `System.resume_pos is not None`, the root's continuing
mid-epoch resume; a defaulted keyword, so an OPT-level caller that passes nothing gets the rule it
had. **`build` no longer takes `resume`** — `load_state` is the whole restore path (Q-OPT-4, a frozen
signature moved).
**Checkpointed:** both AdamW states, `n_backward`, `opt_step`, `lr_prev`, `restart_amp`,
`cycle_best`, `cycle_index`, the resolved `Horizon`, **`param_group_shape`**, the counters,
`horizon_revisions` (Q-OPT-10), the **continuation record** `continuation` (Q-OPT-12) and, since
2026-09-27, `horizon_declined` (the off arm's declined revisions, Q-OPT-12). The old
checkpoint saved `opt_m`/`opt_e` and *nothing else from this package*. `param_group_shape` was
missing from `state_dict`'s enumeration while `load_state` refused on it — an untrippable L50 guard,
repaired 2026-09-02 with Q-OPT-4. A **dim-0 widening** (FAB_SLOTS, LM_VOCAB_SLOTS) is restored with
zero-padded moments rather than refused (Q-OPT-8), and a remaining refusal stops the run (Q-CKPT-4).
**The invariant `counters()` asserts:** `backward // accum == step`.
**What `counters()` renders and does not compute:** `opt.grad_norm.p50/p99` (base group). The norm is
**read in `maybe_step`**, between the gradient's last use and the `zero_grad`; taken in `counters` it
would be a norm over zeroed gradients — 0.0 for a whole run with every check green (Q-OPT-3).
**Defaults, stated because they change what a run is:** `grad_clip = 0.0` (**OFF** — a new lever and
a census amendment; see Q-OPT-3), `weight_decay = 0.0`, `lr_sched` on, `lr_restarts`
fitting exactly one cycle at the shipped run length, `OPT_HORIZON_REVISE = True` (the in-run revision
on, as before it had a lever) and `OPT_LR_CONTINUE = 'as_logged'` (today's resume pricing, labelled on
every resume as `opt.continue.regime`; Q-OPT-12).

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
**On a restored encoder `warm_up` trains nothing** and returns the parent's report (Q-SIG-2).
**Where they are called (§3):** `warm_up` is an `ASSEMBLY_ORDER` row after both stream rows and the
optimizer row; `cadence_due` → `train_step` are stage-`A` rows **before** `encode`; `counters` is a
stage-`R` row and is the encoder cadence's **only** did-it-fire surface, because its two-arm gate
cannot go through `Cadences.due`. Until those rows existed the run trained no encoder at all.

### FAB — `src/fabric/api.py` (83 levers, all 83 read, one of them a census amendment — `FAB_FADED_CULL`)

The expert population. D1 rules it stays. **One forward pass, both arms**: `society=True` is the soc
loop at depth 1 with per-expert logits retained.

`build` · `forward` · `observe` · `contribution` · `manage` · `grow_check` · `own_lr_scale` ·
`counters` · `state_dict` · `load_state_dict`.

**Wires read:** `d_operating_population`, `d_manage_period`, `d_cap_lift_period` (reporting),
`d_base_lr`, `d_lr_min_frac`.
**Receives:** `d_model` ← LM, `signature_dim` ← SIG, `h`/`head` ← LM, `signature` ← SIG,
`targets` ← the loop, `domain_id`/`live_domains` ← DOM, `soft_cap` ← CAP, `memory_pressure` ← MEM,
`applied_lr` ← OPT, `baseline_logits_fn` and `per_window_loss` ← the loop, and since 2026-09-28
`area_id` and `faded` ← the loop, off DATA's labels and schedule as `spine/derive.py::area_id`
numbers (Q-FAB-18).
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
**The loop hands `FAB.forward` its `head` and `targets`** (**Q-FAB-8**, 2026-09-24) — it passed
neither before, so the shipped `hop_vote` never formed and **the default objective changed** when it
did. `live_domains` is `DOM.census`'s `n_live` (**Q-FAB-9**), `observe` takes one domain id per
window (**Q-FAB-10**), and the two control arms `FAB_ON=0` / `FAB_NORM_ONLY=1` run end to end,
with `FAB_ON=0` handing OPT no fabric parameter (**Q-FAB-11**), and neither grows, culls or merges
(2026-09-27, register LOW-FAB_NORM_ONLY-GROWS).
**`manage` gained a step 7, FADED AREAS** (**Q-FAB-18**, 2026-09-28; register §8 3.1, NEW-10 and
C37). `observe(..., area_id=None)` credits each computed expert's new area book
(`Population.area_use`, routing mass per area, one of `_BOOKS`, checkpointed) under its window's
area, and `manage(..., faded=None)` reads every expert it removes against the root's faded set --
DATA's `Plan.faded` for the window's phase plus `Plan.parent_faded` — counting
`fab.culled_faded_area`, `fab.merged_faded_area` and `fab.faded_unknown`, each with a per-pass gauge
(`..._last_pass`). **`FAB_FADED_CULL`** (a census amendment) is `'as_is'`, shipped, where no decision
reads a book, or `'defer'`, an E2 arm and C37's preset value until `FAB.contribution` works, where
such a removal is skipped and counted and **every other decision of the pass is the one `'as_is'`
takes**: the rest of the pass reads the population `'as_is'` would hold, so a deferred victim keeps
its slot in the utilization cull's budget, a deferred absorbee pairs with nobody else, the pressure
gate is sized without the deferred, and no live-area expert is merged or culled in a deferred one's
place (Q-FAB-18's review).

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
disarmed a live mechanism at the run boundary — the victim generator `gen` (Q-CKPT-4), and each
row's `area` (Q-MEM-16).
**Occupancy by area** (**Q-MEM-16**, 2026-09-28; register §8 3.1, NEW-10). `write(..., areas=None)`
takes one `spine/derive.py::area_id` per POSITION, beside `positions`, into a new int32 `area` column
(-1 = no area booked; not `src`, which is DOM's domain); `census` returns `StoreCensus.by_area`,
active entries per id, and the root prints `store.occupancy.<area>` for every area of the run and
`store.occupancy_unknown` in the R row `MEM.census(reconcile=True)`. Nothing that writes, evicts,
reads or rekeys an entry reads the column.
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

### DOM — `src/domains/api.py` (29 levers, one of them a census amendment — `DOM_LEVELS`)

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
**`DOM_LEVELS` (Q-DOM-5) is read by the ROOT, which converts before `note_competence`:** at the
default the book is folded in bits per build-time token, at 0 in bits per token. The inputs are the
window's bytes and TOK's build-time bytes per token, neither of which this package may hold; DOM reads
the lever only to stamp the checkpointed book's unit and compare it on a resume.
**Checkpointed additions:** the reservoirs (the uncensored sample the measured radius needs),
`tokc`, `comp`/`comp_glob`, the adjacent-distance history, the RNG stream `rng` (Q-CKPT-4), and
`comp_unit`, the unit the saving run folded the competence book in, with `comp_carry`, the share of
each EMA still in the other unit after a resume that changed it (Q-DOM-5, corrected 2026-09-27). The
boundary clock **must not restart** on resume; `grace` **does**, and the asymmetry is deliberate.
**Where they are called (§3):** `rekey` is a stage-`A` row on `Cadences.due('dom.rekey',
MEM.rekey_every, clock)` **after** `observe` — without it `accept_rule="radius"` silently degenerates
to the constant rule, because `rekey` is the only site that measures a radius; `census` is at `A`
(its `live` list is `apply_domain_plan`'s `live_sources`) and at `R`; `on_retokenize` is delivered at
the `E` epoch roll, which is where the deferred retok is performed (Q-RUN-8), and only when the match
table moved since the last segmentation (Q-DOM-2) — it had no call site at all until 2026-09-24;
`prior` is at `R`, asked once per live domain, which is where the old tree read it while paying for
the histogram every window; `state_dict` is a stage-`C` row. `rekey` runs **after** `observe` and only
at `SIG_MODE=learned` since 2026-09-24 (Q-DOM-3); before that it ran first in the `A` block and on
both arms.

### RUN — `src/train/api.py` (7 levers)

Owns the shape of the run. **Declares no cadence and no threshold** — a claim a reader can test by
grepping the package for `%` and for a threshold literal.

`process_setup` · `mode` · `streams` · `new_clock` + `RunClock.{begin_epoch,revise_epoch_length,
advance,note_backward,counters}` · `new_cadences` + `Cadences.{due,ledger,state,restore}` · `bench_summary` ·
`startup_refusals`.

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
**What crosses a resume (Q-RUN-9, Q-RUN-10):** `payload['RUN']` carries `Cadences.state()` (a C row;
put back by the `Cadences.restore` row after `new_cadences`) and the clock's epoch position off
`RunClock.counters` (a C row as well). `new_clock` seeds `backwards` and `opt_steps` from OPT's
restored counts, so four of the six counters resume and `flushes` / `dropped_windows` are this
process's. A resume of a finished run is refused; a mid-epoch one keeps the declared replay and is
warned.

### CKPT — `src/ckpt/api.py` (5 levers)

A resume is not a convenience, it is the experiment.

`saving_on` · `save_period` · `save` · `install_save_signal` · `resume_source` · `load` ·
`check_geometry` · `new_retention` + `Retention.{consider,state,counters}`.

**`payload` is opaque**; `geometry` is a manifest of `GeometryField(value, rule, env_name, why)`
records the packages produced, and **the rules are the owner package's** because the legal direction
differs per field. **A missing field is a refusal, not a skip** — the comparison is driven off the
manifest's key set, so `if recorded and recorded != live` is not writable here.
**The suffix applies to the whole snapshot**, tokenizer bytes included (M46).
**So does the one kept generation** (2026-09-26): `ckpt.pt<suffix>.prev`'s vocabulary is
`<base><suffix>.prev.dyntok.json`, rotated by TOK, which owns the file, inside `save_vocabulary`.
The root calls that only when `save` returned True, so the two rotations happen in one save or not
at all. CKPT's own failed rotation is still uncounted (`_SAVES` has no reader in the report).
**A run directory named for another run's snapshot is refused** (2026-09-27, build 1.1's review):
`saving_on`, which stands where a per-lever parse hook would, raises `LeverError` at compose for a
`CKPT_DIR` whose last component ends in `.prev`, `.best` or `.best<N>`. A run base is the one name a
checkpoint and its vocabulary share, so `<X>.prev` saved its own vocabulary to the file TOK moves run
`<X>`'s previous generation onto (driven: a 190-entry file held 183 entries after `<X>` saved twice,
uncounted), and `resume_source` loaded `<X>.prev/ckpt.pt` for `CKPT_RESUME=<X>/ckpt.pt.prev` once
that directory existed. Any other name saves the same run; `CKPT_RESUME` is not refused, so a
directory with such a name made before this date can still be resumed from, and its ambiguity against
`<X>/ckpt.pt.prev` is stated, not closed.
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
not_stalled | threshold | at_hard_ceiling | dead_rows_unmasked` — because *"0 lifts" alone cannot
distinguish "never full" from "never plateaued", and those have completely different fixes.*
**`dead_rows_unmasked` is new on 2026-09-04 and it is the refusal this package had owed since the
honesty precondition was declared.** `d_mask_dead_rows` bought a *report line* and nothing else: the
vocabulary arm could be armed, the mask off, the precondition tested and not met — and the lift
happened anyway, with `new_valve`'s `cap.vocab_arm_honest` Gate saying in its own printed reason
that nothing in the tree refused it. It bites on the **vocabulary arm only** (an unmasked output
layer says nothing about reserving *expert* slots), and it is evaluated **last, after
`at_hard_ceiling`** — placed first, with the other configuration-shaped reason `targets_off`, it
would answer every call on an unmasked run and the histogram would never learn whether that arm ever
pinned and stalled, which is the very collapse this closed set exists to end. Last, it counts
exactly the lifts that were *earned and then declined for dishonesty*. **It is deliberately not a
startup refusal, and the ground for that is narrower than this paragraph said until 2026-09-04.** It
read that a startup refusal *"would make `CAP_TARGETS=vocab` unrunnable at the shipped
`LM_MASK_DEAD_ROWS=False`"*, which reads as though the valve **works** on that configuration. It does
not: no vocabulary lift can happen there under either design — this block reason refuses every one,
and `new_valve`'s `cap.valve` now reports that arm **UNREACHABLE** for exactly it. **The lifting
capability is absent either way**, so it is not what separates the two designs. What separates them
is what the operator gets instead: a startup refusal ends the process and produces **no measurement
at all**, while this refuses the *lift* and lets the *run* proceed — it trains, the expert arm still
works at `targets=both`, and the histogram carries a **count** of the lifts that were earned and then
declined, which is a number no other line in the run produces. `spine/assemble.py`'s
`CAP.d_mask_dead_rows` row still names the stricter repair as **the owner's to ask for**; what it no
longer says is that the stricter repair would need no wire. It carried *"a valve that refused to lift
the vocabulary at all while the mask is off would need no flag"* until 2026-09-04 and now answers its
own sentence — ***"IT WOULD: a valve that refuses ON A CONDITION must READ that condition to know
when to refuse"*** — so quoting the retracted half here, as this paragraph did, cited the one sentence
a future reader would use to delete the wire the refusal rests on. The flag is frozen onto the `Valve`
at `new_valve` as `counters["cap.mask_dead_rows"]`, the way the two hard ceilings are, so `observe`
keeps reading no wires of its own.
**`new_valve` refuses two lever values at startup, added 2026-09-04: `CAP_LIFT < 0` and
`CAP_LIFT_MIN < 0`, and either one alone trips the refusal.** `derive.lift_to` is
`cap + max(int(floor), int(frac × cap))`, so everything a lift does to a cap is decided by that one
`max`, and **a `max` is negative only when BOTH of its operands are.** That is the whole rule, and it
is arithmetic rather than a sample: **a lift lowers a cap exactly when `int(CAP_LIFT_MIN) < 0` AND
`int(CAP_LIFT × cap) < 0`.** Two consequences follow with no sweep behind them. `CAP_LIFT_MIN < 0` is
**necessary** for every lowering there is, so a negative `CAP_LIFT` **alone** never lowers a cap —
at any cap, above zero, at zero or below it — and that half of the refusal rests on the second ground
below rather than on this one. And the proportional operand goes negative only when the fraction and
the cap carry **opposite signs** *and* `int()` does not truncate their product to zero, which is why
the guard is an `or` and not an `and`: `CAP_LIFT_MIN < 0` reaches a lowering with a **non-negative**
`CAP_LIFT`, at any cap far enough below zero to survive the truncation.
**Compute those two operands; do not read a regime label off this page.** Two earlier generations of
this paragraph named regimes instead. The first said only the two **together** lower a cap; the
second replaced that with three narrower labels — *"Both negative, at a cap above zero"* **shrinks**,
*"`CAP_LIFT_MIN` negative alone, at a cap below zero"* lowers, and *"Below zero neither identity
holds"* — and each of the three was refuted at a cap inside the regime it named, the last of them at
`CAP_FAB_START=-5`, the one below-zero cap that same paragraph offered as reachable. Worked pairs,
run rather than reasoned about:
`lift_to(12, -0.5, -100) = 6` lowers while `lift_to(1, -0.5, -100) = 1` does not, both with **both**
levers negative; `lift_to(-5, 0.5, -1) = -6` lowers against `lift_to(-5, 0.5, 0) = -5` while
`lift_to(-12, 0.08, -1) = -12` does not, both with the **floor alone** negative below zero. The
second pair is reachable — `new_valve` resolves `CAP_FAB_START=-5` to `cap_experts = -5` with
`origin[0] = "operator (fab_start=-5)"` — and a lowering is against this package's founding sentence,
*"raised, by a little, never lowered"*. *(This paragraph said until 2026-09-05 that only the two
**together** lower a cap; from 2026-09-05 to 2026-09-06 it replaced that false universal with three
narrower false ones. `capacity/api.py` and `capacity/levers.py` still carry the second shape in their
own copies and are filed with exact replacements.)* Before the refusal, `compose()`
carried `CAP_LIFT=-0.5` as far as `new_valve` without a word and `cap.valve` printed
*"one lift → 6"* beside *"ONE EARNED LIFT DOES NOT MOVE IT"* on one line; **`build()` carries it
still**, because the refusal is in the body of `new_valve` and not in the Lever machinery —
`assemble.build(environ={"CAP_LIFT": "-0.5"})` returns a frozen `Config` with `lift = -0.5`, and it
is `compose()`, one row later, that raises. **THE SECOND GROUND is the same `max` read the other
way**: each negative is a redundant spelling of a legal value for exactly as long as the `max` picks
the operand it would have picked at the zeroed lever. With `CAP_LIFT_MIN` at or above 0 a negative
`CAP_LIFT` is arithmetically `CAP_LIFT=0` while `int(CAP_LIFT × cap) ≤ CAP_LIFT_MIN`; with `CAP_LIFT`
at or above 0 a negative `CAP_LIFT_MIN` is arithmetically `CAP_LIFT_MIN=0` while
`int(CAP_LIFT × cap) ≥ 0`. **At a cap at or above zero both conditions hold automatically, so there
the two identities are unconditional.** Below zero they are a computation, and **neither is empty
there**. Take the shipped `CAP_LIFT_MIN=8` against `CAP_LIFT=-0.5`, and the shipped `CAP_LIFT=0.08`
against `CAP_LIFT_MIN=-1`, at the reachable `cap = -5`:
`lift_to(-5, -0.5, 8) = 3 = lift_to(-5, 0, 8)` and `lift_to(-5, 0.08, -1) = -5 = lift_to(-5, 0.08, 0)`
— **both identities hold at the cap this document names as reachable.** At *those two lever pairs*
the first identity first fails at `cap = -18` (`lift_to(-18, -0.5, 8) = -9` against
`lift_to(-18, 0, 8) = -10`) and the second at `cap = -13` (`-14` against `-13`); both boundaries move
with the levers, which is the reason they are computed here and not quoted as a rule.
`lift_to(-100, -0.5, 8) = -50` against `lift_to(-100, 0, 8) = -92` — the pair this paragraph used to
print as if it were the whole of below-zero — is far past both.
**Where each identity stops holding, the two levers part company**, and this is the join the three
regime labels kept getting wrong. Where a negative `CAP_LIFT_MIN`'s identity breaks, the lowering has
already begun: that *is* the first ground, so nothing is left over. Where a negative `CAP_LIFT`'s
identity breaks, no lowering is possible — the floor is at or above 0, so the `max` is too — and what
is left over is a **lift that grows with how far below zero the cap sits** (`+50` at `cap = -100`
against the flat `+8` a legal value gives), which is not a lowering and is not a second spelling of
anything declared either. So both are refused: one because it can lower, the other because it is
redundant where it is legal and undeclared where it is not.
**`CAP_LIFT > 1` is deliberately *not* refused** — `U.FRACTION`'s unit string is a label the census
renders and not a bound (`spine/lever.py::Lever` carries `choices` and, since 2026-09-14, an
optional `domain=(lo, hi)` — **CAP declares one on neither lever**; §0.5), and a lift
of 2.0 is a large lift, not a lowering one. It lives in `new_valve`
rather than in `startup_refusals` because that entry point is declared for refusals that need **two**
packages' numbers, is a stub today, and runs *after* the valve row — a Gate reason would render
first. `src/lm/api.py::resolve` is the precedent, and **the general ground it states is now out of
date in one half and still standing in the other.** That file says today, word for word, *"a Lever
has no range facility and `choices=` enumerates rather than bounds, so these cannot be
declarations"*. **The first clause stopped being true on 2026-09-14** — a Lever carries
`domain=(lo, hi)` and LM declares one, on `LM_DROPOUT` (§0.5) — **and the conclusion it draws is now
true of some of that function's refusals and not of others, which is a sharper statement than the
one the sentence makes and points at work rather than closing it.** `resolve` refuses nine things.
Two genuinely cannot be declarations at all: `LM_WIDTH` divisible by `LM_HEADS` is a coupling
between two of this package's own levers, and `ctx > pos_max` compares a lever against an incoming
wire, and no per-lever pair states either. One has a strictly open end (`LM_ANCHOR_USES > 0`) and a
closed pair can only contain it. **The remaining counts — `LM_WIDTH`, `LM_HEADS`, `LM_CTX` and
`LM_VOCAB_SLOTS` at `< 1`, and `LM_LAYERS` at `< 0` — are expressible as pairs and do not carry
one**, and neither does `CAP_LIFT` at `< 0`. That is a per-lever ruling nobody has made, not a fact
about the machinery, and this document does not make it here: §0.5's third caution is why —
`LM_LAYERS=0` is a declared sentinel meaning "this arm's default", so the pair is `(0, None)` and
not `(1, None)`, and getting that wrong deletes a working mechanism. The quotation is left exactly
as `src/lm/api.py::resolve` carries it rather than
silently modernised; the repair to that file belongs to its owner and is filed, and whoever makes it
must requote here in the same commit or `tests/test_ownership.py::check_o13_citations_resolve` will
say so.
*(`src/capacity/api.py::new_valve` carries a **second** quotation of the same kind, attributing to
`src/sig/levers.py::SIGLevers` a sentence about `choices` and "no numeric range" that `SIGLevers`
**no longer contains** — that file was rewritten on 2026-09-14 and now says `Lever` carries
`choices` and an optional `domain=`, which exactly one of its levers declares. O13 does not reach
that one: its quotation arm skips a span carrying code punctuation, and this span carries `::`. So
it is a false quotation that no check will report, filed against `capacity`'s owner with the
replacement text, and named here because this document has now recorded the same failure twice in
the same function.)*
`Caps.headroom(n)` exists so the negative clamp (C30) **cannot be written** at a call site.

**An overshooting lift is CLAMPED at the hard ceiling, not refused — the owner's ruling of
2026-09-04, `.rework/DECISIONS.md` D16.** A soft cap set just under its ceiling makes the **first**
earned lift overshoot: `lift_to(4095, 0.08, 8) = 4422` against a ceiling of 4096, and at the shipped
`CAP_LIFT=0.08` / `CAP_LIFT_MIN=8` every start from 3794 to 4095 is such a cap — 302 of them, each
of which a refusal would strand below its ceiling and refuse every lift forever, spending the
evidence that earned the lift on nothing. The lift is **taken** and held at the ceiling by
`capacity/api.py::_clamped_lift`, whose `max` is there because `min(lift_to(…), hard)` from a cap
*above* the ceiling would **lower** it, and lowering is the one thing this valve may never do.
**The state and the call are BOTH reachable, and the guard runs today:** `CAP_FAB_START=5000`
against `FAB_SLOTS=4096` resolves `cap_experts = 5000` above its own hard ceiling, and
`capacity/api.py::new_valve` hands exactly that cap to `_clamped_lift` at startup — its local
`_one_lift` computes `_clamped_lift(5000, 4096, 0.08, 8)` on the line *before* it tests
`c >= hard`, and the call returns 5000 where a bare `min` would return 4096. **Two things about
that call are still unreached, and this paragraph said the call itself was, until 2026-09-05.** The
first is the value: `_one_lift` discards `got` on the `c >= hard` branch and prints the
`at_hard_ceiling` refusal instead, so the `max` changes no printed number *on that branch* — it
keeps the function's own invariant, that the return is never below `cap_value`. The second is
`observe`'s call, which is unreached twice over: `at_hard_ceiling` refuses `cap >= hard` before any
lift is computed, and `capacity/api.py::observe` is `raise NotImplementedError` today, which is why
`_clamped_lift`'s docstring names `_lift_moves`, `_one_lift` and the mask-and-inert test as every
executing caller. The guard is kept on the ground its docstring gives — the refusal is a **caller's
discipline** and this is where the arithmetic lives — and a reader who takes it for decoration has
read `observe`'s contract and not `new_valve`'s code. **`at_hard_ceiling` is
unchanged**: it tests `cap >= hard` **before** the lift is computed, so the closed set above does not
grow and the clamp bites **once per arm** — full lifts, then one clamped lift, then `at_hard_ceiling`
on every flush after it. **Of the two readings of *"until it goes down"*, `capacity/api.py::observe`
takes the STATELESS one** — per-lift arithmetic, not a state pinned at the ceiling and released when
demand falls — and its docstring records why: a cap may never be lowered, `CAP.state`'s payload
carries no clamp flag, and no demand *level* reaches that call. It also records how an owner would
tell the readings apart from a report alone: under the stateless one a cap never prints smaller than
it printed on an earlier flush. **A clamped lift is neither a clean fire nor a refusal**, so it is
absent from the block-reason histogram and carries numbers of its own — `Decision.clamped` for the
one flush, and `counters["cap.lifts_clamped_experts"]` / `counters["cap.lifts_clamped_vocab"]` for
the run, seeded at 0 by `new_valve` the way the two hard ceilings and `cap.mask_dead_rows` are, which
takes that ledger from eight keys to ten. Its DID IT FIRE surface is a **third** Gate, `cap.clamp`,
built by `capacity/api.py::_clamp_gate`, with four readings: UNREACHABLE (no lift can be **held at
a hard ceiling** — which is *not* "no lift can be earned": an arm whose earned lifts are refused by
name, and one whose applied lifts move nothing, both reach this verdict with lifts earned all along),
*"0 clamped of 0 lifts"* (none was earned), *"0 clamped of N lifts"* (every earned lift applied in
full) and FIRED, *"M clamped of N lifts"*. **This paragraph read "UNREACHABLE (no lift can be earned
at all)" until 2026-09-05**, which was the gate's own wording until the round before, when it was
retired from `src/` as a self-contradiction: the reason printed that sentence beside its own clause
saying lifts *are* earned here. After that repair this document was the tree's last present-tense
carrier of the retired sentence, and a P4 author would have implemented it from here. Which of the clamp's three
preconditions failed first is carried per arm as `dead_facts` and written by
`capacity/api.py::_clamp_blocked_clause`, whose closed set has **six** grounds; the gate reports
UNREACHABLE on all six, which is **five more than `D16` ruled on** and is flagged for the owner as
`Q-CAP-1`. `clamped > lifts` is refused rather than printed: a clamped lift is a lift *taken*, so
the inequality is not a ledger this gate can read. **P4 must call it and increment the two
counters**; until it does, a real run can only reach the first two readings.
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
**`world_proj` is born ZERO**, like FAB's `A`/`B` and WORLD's own `preds`, and `load_into` re-zeroes
it when the checkpoint says no forecast ever reached it — by the saved `proj_trained` field, or for a
blob that predates the field by `world.forecasts` being absent from its counters (**Q-WORLD-10**).
Five undeclared constants (`w_cov=0.04`, `w_bal=0.01`, `min_mass=1e-3`, `tau=1.0`, the plateau pair)
become **named module constants with a written reason** — not levers; the census never voted on them.
**`nmax` caps LIVE predictors and a mint at the cap takes the lowest DEAD SLOT** (**Q-WORLD-8**,
RESOLVED (b), 2026-09-02). The help string's meaning changed; **the default is still 6**. A dead
predictor is **skipped in the forward**, not down-weighted at `1e-6`. `geometry`'s `n` is the
**allocated** count `len(preds)` and never the live count — `n ≤ nmax` becomes an invariant, and
`live` is a `ManageResult` reading and a `state_dict` buffer, not a shape.
**No period enters WORLD's Config** (C3), and **Q-WORLD-6 is RESOLVED (b)**: no wire, a `NOT_WIRES`
entry instead — the ledger stays at **19 of 25, 23 declared couplings**.

### EVAL — `src/eval/api.py` (19 levers, two of them census amendments — `EVAL_RETENTION_EVERY` and `EVAL_RETENTION_N`)

Everything that measures the run and nothing that changes it.

`curve_period` (P3) · `retention_period`, `pin_holdout`, `holdout_probe`, `blowup`, `generate`
(the retention probe, built 2026-09-27 and off at `EVAL_RETENTION_EVERY=0` — **Q-EVAL-12**) ·
`curve_probe`, `null_excess` (P5) · `coherence`, `verdicts`, `wrongness_probe`,
`verification_fit` (P6).

**All 19 levers now have a declared reader.** The five P6 instruments are declared here — with
signatures, not bodies — precisely so that `EVAL_GEN_TEMP` is a knob whose consumer is written down
rather than one of the 57 armed-but-inert records. What P6 owns is the body.
**Two rules every function obeys:** G7 (an instrument may not leave the model in a different mode or
move an RNG stream) and the one-logits-path rule (`logits_fn` is passed in, never constructed).
`null_excess` **refuses `null_draws < 2` at construction**: at 0 it is a `ZeroDivisionError` that
takes the rest of the report with it, and at 1 the sd is exactly 0.0 so the 2σ test becomes a rubber
stamp.
**Where they are called (§3):** since 2026-09-27 (Q-EVAL-12) `pin_holdout` has an ASSEMBLY row,
`retention_period` sits in the cadence row's mapping beside `curve_period`, `holdout_probe` and
`blowup` have `B` rows, and `holdout_probe` and `generate` have `R` rows. The other **six** are
deferred, four for an argument that has no producer and two — `curve_probe` and `coherence`, whose
producers exist since the probe landed — as scope deferrals, not "a later phase", which by itself
is no reason at all. *(This paragraph said `curve_probe` "has a row" and that the deferrals
were **seven** and "the whole of `compose.DEFERRED_ENTRY_POINTS`". Both were true when written and
neither is now: §3.6 moved `curve_probe` into the deferrals — that move is the finding the `produces`
column was written to expose — and the table grew past EVAL, so EVAL's eight became eight of
twenty-three. Corrected 2026-09-04; EVAL's are six of eighteen since 2026-09-27. The numbers here are
words, which is why `K13` could not see them.)*

**Two declared outputs had no channel in the signature that must produce them, and both closed on
2026-09-04 — `Q-EVAL-11`.** `curve_probe` gained `step` (RUN's window counter, which `CurveReading`
carries and no argument supplied) and `verification_fit` gained `verify_mode` (`MEM.verify`, which
its declared Gate reads and no argument supplied). Both are **arguments the composition root
passes**, both were referred twice for want of an agent owning the document and the tree at once,
and **EVAL still declares no wires and receives none** — see the ruling for why a wire was not
available for the first and was refused on its merits for the second.

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
whose arguments nothing supplies"* — and then `EVAL.curve_probe`, whose signature was then
**byte-identical** to `holdout_probe`'s (`ev: Config, *, units_by_domain, logits_fn, rng` — it gained
`step` on 2026-09-04 under `Q-EVAL-11`, which changes nothing about this argument), carried
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
| `RunClock.step` | `step` (TOK ×3, `Retention.consider`, `CKPT.save`, `EVAL.holdout_probe`), `step_windows` (SIG, FAB ×3; the probe's closures pass `clock.step + 1`, Q-EVAL-12), `now` (MEM ×2, DOM ×2) |
| `Snapshot.payload` | `state` (DATA, TOK, CAP), `saved` (LM, OPT), `sd` (SIG, FAB, WORLD), `restored` (MEM, DOM, CAP, CKPT), `resume` (OPT), `snapshot` (CKPT) |
| `LM.lm_loss`'s two returns | `per_window_loss` (FAB.observe), `flush_loss` (FAB.manage/grow_check), `baseline_loss` (FAB.contribution), `bits` (DOM.note_competence; over ln 2, and in bits per build-time token at `DOM_LEVELS`, Q-DOM-5), and one summand of the objective |
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
window), and `Due` (asked per window at `A`, acted on per flush at `B`). A fourth, `best_bpb`, is
`System.probe_reading` since 2026-09-27: the retention probe's last forwarded control mean, set after
one flush and read by the next `OPT.maybe_step` (Q-OPT-13, Q-EVAL-12), written into that row's note.

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
| `_sample_window` | `windows` for `SIG.encode` and **the same object** as `sample_window` for `DOM.observe`, which `domains/api.py:96` requires. The loop passes the window's own 0-based index, so the slice **ends at the window's first byte** and holds none of its targets (Q-FAB-7). |
| `_key_fn` / `_head` / `_sig_encode_fn` | `key_fn` (MEM ×2), `head` (FAB), `encode` (`DOM.rekey` **and**, since 2026-09-02, `EVAL.coherence` — Q-EVAL-10; the *same* callable under the *same* name, because two encoders would be two signature spaces) — entry points partially applied. The callable class of argument has no other producer. |
| `_n_params` / `_bytes_per_window` | `RUN.bench_summary`'s two measured arguments. `_n_params` sums **both** param groups; summing only the base list undercounts by the whole encoder. |
| `_geometry_manifest` / `_run_windows` / `_windows_in_epoch` / `_signature_width` / `_alphabet_size` / `_base_parameters` / `_sidecar` / `_signature_stream` / `_signature_units` | the assembly-side joins, unchanged except where §3.8 records a repair. |
| `_logits_fn(sysm, *, use_memory, view=None, live_domains=None, live_vocab=None)` | `logits_fn` (`EVAL.holdout_probe`, `EVAL.generate`) — **the two closures**, `memory-off` and `memory-on`, each `fn(x, *, prefix_bytes) -> (B, L, V)` along the path the run trained, at the next window's routing clock, under `no_grad` in eval mode; the only place `softmax → MEM.read(promote=False) → MEM.blend → log` is written (Q-EVAL-12, Q-MEM-10). A resume's start reading passes its parent's `view` and `live_domains`; generation passes `live_vocab`, the live vocabulary it may draw from. |
| `_holdout_units` / `_holdout_tokenize` / `_gen_prompts` | `units_by_domain` (the arrived areas' pinned `(prefix, window)` pairs, with `seen_by_parent`), `tokenize_fn` (`TOK.tokenize` at the last cut's view, no labels, no regularizer) and `prompts_by_domain` (report-half windows — each its routing prefix, its bytes and their cut at that view) — Q-EVAL-12. |
| `_phase_of` / `_phase_windows` / `_probe_notices` | the phase a window's first byte falls in (the phase-start read's test) and the startup notices, printed and never applied — Q-EVAL-12. |
| `_area_ids` / `_window_areas` / `_faded_ids` | `area_id` (`FAB.observe`: one per window, its first token's area), `areas` (`MEM.write`: one per position, beside `positions`) and `faded` (`FAB.manage`: `Plan.faded` at the window's phase plus `Plan.parent_faded`), each as `spine/derive.py::area_id` numbers over `Stream.area_names` — Q-FAB-18, Q-MEM-16. |

What is deliberately **not** there, because writing it would be inventing a producer rather than
naming one: an `improving` EMA pair (FAB already keeps one, and a second would be two mechanisms
deciding the same question); an `owners` rule beyond the old tree's; a `plateau` boolean (WORLD
holds that state); and a scorer of the `(ctx, src)` arity `MEM.judge` and `EVAL.wrongness_probe`
declare — the closures route on prefix bytes, which a stored entry does not have. *(A `logits_fn`
headed this list until 2026-09-27, "it must be the path the run trained … and so needs the flush's
own novelty, live_domains and training"; Q-EVAL-12 names what each of those became.)*

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
| `A` | per WINDOW, above the accumulator | `MEM.census` (before `DOM.manage`, whose `memory_counts`/`mem_floor_entries` had **no producer**), `DOM.manage`, `DOM.census` (supplying `live_sources` and `live_domains`), `FAB.manage`, `SIG.cadence_due` → `SIG.train_step` (before `encode`), `SIG.encode`, `DOM.observe`, `DOM.rekey` (after `observe`), `TOK.on_window`, `RunClock.advance`. `MEM.judge` and `WORLD.manage` **were here and are now deferred** (§3.6). |
| `B` | per FLUSH | the flush body, plus `TOK.judge_probation`, event-driven on the `Due.probation` `TOK.on_window` already asked at `A`. `CAP.observe` and `FAB.contribution` **were here and are now deferred**. Since 2026-09-27, per WINDOW after the flush and the act: the retention probe's `EVAL.holdout_probe` → `EVAL.blowup` → `CKPT.Retention.consider`, behind its arm test (Q-EVAL-12). |
| `C` | the CHECKPOINT FAN-OUT — an **event**, entered from `B` (periodic/SIGUSR1, and a `BestAction` since 2026-09-27, followed by `Retention.note_saved`) and `R` (final) | the twelve `state_dict`/`state`/`vocab_state`/`stream_state`/`Retention.state`/`WORLD.geometry` calls that build the payload and the recorded manifest, then `TOK.save_vocabulary`, then `CKPT.save`. *(2026-09-26: the driver, `spine/loop.py::_save`, calls `CKPT.save` first and `TOK.save_vocabulary` only when it wrote, and since this date that order is load-bearing: the vocabulary's rotation with `ckpt.pt.prev` must not run for a checkpoint CKPT refused. The rows list the reverse order and are unchanged, since K6 checks reach, not order.)* |
| `R` | once, after `Tick.finished` | the retention probe's boundary reading (`EVAL.holdout_probe`, both closures, at the head), `DOM.prior`, both censuses, every `counters()`, `Cadences.ledger()`, `RUN.bench_summary`, the `reason="final"` save, and `EVAL.generate` after it. `MEM.read` and `MEM.blend` **were rows here until 2026-08-30**; since 2026-09-27 they are reached through the memory-on closure the R probe row's note names (Q-MEM-10, amended). |

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

**A continuing mid-epoch resume checks its stream before it replays the log (2026-09-27,
Q-DATA-9).** At the `segment` stage — after the `stream` row redraws the resumed epoch, before
`_replay_segmentation` cuts the parent's log over it — the root raises `RefusedRun` (a fourth stop,
on this path only) on a hold-out admission (`data.holdout_admitted` > 0, naming
`DATA_SYNTH_HOLDOUT=0` or an epoch-boundary resume) and on a redrawn stream whose digest
(`_stream_digest`: the bytes and the segment table) differs from the one the log's first event
recorded, naming the draw-shaping levers. A log written before the digest warns once and keeps the
rebuilt-length check at the `epoch0` stage; the child's copy of the log then records its own stream.

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
nothing drew a stream. It now measures `(len(Segmentation.ids) - 1) // LM.ctx` through the named join
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

**All five accessors now REFUSE a negative period, and the refusal is switchable — the owner's
ruling of 2026-09-04, `.rework/DECISIONS.md` D17.** `EVAL.curve_period`, `DOM.manage_period`,
`FAB.manage_period`, `MEM.rekey_period` and `CKPT.save_period` each raise the spine's `LeverError` on
a negative value of **their own** lever, naming the lever and the value, and each fires **before**
the `units.Windows` is constructed, so nothing is derived from the bad number. **A period of 0 is
untouched by all five** — zero means something different for each of these levers and only some of
those meanings are declared, so the ruling stops at the sign. The switch is `REFUSE_NEGATIVE_PERIOD`,
a module constant in each owning `api.py`, with **no environment name**, no census row and nothing
for the planned `docs/04_LEVERS.md` to render. **D17 asks for more than this shape gives, and the gap
is recorded here rather than closed.** Its second sentence (*"if it has a bad effect, we can turn off
the refusal"*) is read in `.rework/DECISIONS.md` as meaning the refusal must be turn-off-able
**without editing code**, and D17 closes by saying the switch exists so that revisiting the ruling
costs an environment variable rather than a commit. Flipping `REFUSE_NEGATIVE_PERIOD` costs a **code
edit in five files** — less than a revert, and more than an environment variable. So the answer to
*"is the refusal turn-off-able without editing code"* is **no**, and this sentence said otherwise
until 2026-09-06 by paraphrasing the requirement down to *"not a revert"*, which is the half the
shipped shape happens to meet. What the shape does buy against D4 — a mechanism kept for future use
is kept **with a switch**, not as a code path that rots — is that OFF is a first-class named state
instead of a deleted branch; what it still owes the owner is a way to reach that state from a shell.
The argument for paying a code edit rather than minting five levers or spending five of the six
remaining edges is written once, at
`ckpt/api.py::REFUSE_NEGATIVE_PERIOD`, and the four siblings point at it rather than restating it;
that file states the same cost plainly and does not soften it. **The choice this leaves open is the
owner's**, because D17 instructed the implementing agent to REPORT rather than spend a wire, and the
report is the one `ckpt/api.py` writes: it checked the wire-free routes one at a time and each is
closed by a green check — O1 on `os.environ`, O8 on `from_env`, O10 on imports, and
`Config.owned_by` at the read site — so either a code edit is accepted, or five per-package levers
are minted, or O10's allowlist gains a spine module, which is an edit to `tests/`. It is not settled
here, and it must not be settled by a paraphrase.
**`FAB.manage_period`'s guard is the second line and not the first:** `FAB_MANAGE_EVERY` is also the
source of the declared coupling `OPT.batch_windows → FAB.d_manage_period`, and since 2026-09-05
`spine/derive.py::flush_period_windows` raises a `UnitError` on a negative there — at **build**,
before any accessor is called — where it used to floor the value to `Flushes(1)`, the tightest
cadence in the system. FAB's own guard is unreachable through `assemble.build` because of it, and
kept for the caller that builds a `Config` any other way, which is D4's rule and not an oversight.
**What the ruling does NOT reach, said so this is not read as covering every cadence in the tree.**
The sixth entry in `compose.py`'s `_periods` is `RUN.PROGRESS_WINDOWS`, a module constant rather than
a lever, so no environment value can make it negative. Of the three **unledgered** comparisons in the
table above, MEM's probe and MEM's internal rekey read `probe_every` and `rekey_every` inside
`MEM.maintain`, which is a stub — there is nothing to guard yet, and when P4 writes it the guard
belongs at the first read of the lever under that package's own `REFUSE_NEGATIVE_PERIOD`, which is
already declared — while `SIG.cadence_due` **is written**, reads `train_every`, `train_every_idle`
and `dense_window`, and carries no such refusal. Whether it should is SIG's to answer.

**One gate, one ask.** `Cadences.due` *records* the fire and returns True, so asking a second time
under the same key **consumes** the event — that is how a shared `_due` key made minting never fire
at all in the old tree. The management block therefore asks `dom.manage` **once** and runs three rows
inside that one answer: `MEM.census` → `DOM.manage` → `DOM.census`. (`MEM.judge` was the fourth and
is deferred — **Q-MEM-8 rules that it returns to the END of this same answer, never a second `due()`
under this key**; `WORLD.manage` rode `fab.manage`'s single answer **without its row saying so**, and its
deferral records that when it returns it must either be written inside that answer, in the shape this
block uses, or take a key of its own.)

Everything else that fires is **event-driven and says so**: `Retention.consider` (a retention
reading's control mean arrived, finite — which at the shipped `EVAL_RETENTION_EVERY=0` it never
does), `SIG.train_step` (`cadence_due` said yes),
`TOK.judge_probation` (`Due.probation`), `DOM.on_retokenize` (the epoch roll's re-segmentation at a
moved match table — Q-DOM-2), and the whole `C`
stage (a save site). **`SIG.cadence_due` is the one periodic gate that cannot go through
`Cadences.due`** — it selects between `train_every` and `train_every_idle` on `dense_window`, and
`due` takes one period — so it has **no ledger key**, and `SIG.counters` at stage `R` is the only
did-it-fire surface the encoder's cadence has. That is stated in its row rather than left for a
reader to discover from a missing ledger line.

### 3.6 `DEFERRED_ENTRY_POINTS` — eighteen, and no longer only EVAL

`{"PFX.entry": "the phase that will call it, and why it cannot be called now"}`. K6 reads it **both
ways**: an entry no row names is accepted, and an entry a row **now** names is reported as *stale*
and must be deleted. That is what stops it becoming the place orphans go to be forgotten.

**It was seven, all EVAL, and that was the finding.** The seven were deferred for a stated reason —
an argument with no producer — while seven rows elsewhere in the tables named calls with exactly the
same gap. The `produces` column made every one of them decidable, and the seven added below are the
rows where nothing among the entry points (§7 holds the count) supplies a required argument and no
join in `compose.py` honestly can. **None is deferred for being late**, and none because a body is missing:
the whole tree was stubs. **Since 2026-09-27 the retention probe (Q-EVAL-12) has closed five** —
`EVAL.holdout_probe` and `EVAL.generate` have rows, `CKPT.Retention.consider` has its caller, and
`MEM.read` and `MEM.blend` are reached through the memory-on closure — and turned two more
(`EVAL.curve_probe`, `EVAL.coherence`) into **scope** deferrals, whose producers exist. The table
below holds the ten deferred for an argument or a scope; the eight deferred for want of a CALLER
(accessors and RUN.Timing's two) are listed in `spine/compose.py` with their reasons.

| entry | phase | why there is no row |
|---|---|---|
| `EVAL.curve_probe` | P5 | **A SCOPE DEFERRAL SINCE 2026-09-27.** Every argument has a producer now — `units_by_domain` from the retention probe's pinned `ProbeSet`, `logits_fn` the memory-off closure, `step` `RunClock.step`, `rng` an `eval` child (Q-EVAL-12) — and it is not built because no row of the register's §8 builds it: a learning curve at `EVAL_CURVE_EVERY` on unpinned windows would be a second instrument answering the retention probe's question. *(Until then: byte-identical signature to `holdout_probe` until `step` landed, Q-EVAL-11, and the same gap — nothing produced `units_by_domain` or `logits_fn`.)* |
| `EVAL.null_excess` | P5 | **Reason corrected.** It said `real` and `permute` come from "the verdict machinery, which is P6's" — but `EVAL.verdicts` takes `domain_sizes`, `silhouettes`, `affiliation`, `coherence_reading` and is this function's **consumer**, not its producer. `real` is the measured statistic under test and `permute` the label-permuting redraw of it, so the candidates are the silhouette and affiliation statistics — which have **no producer in the tree**, the very gap `verdicts` is deferred for — and nothing returns a permutation callable. **Neither exists.** |
| `EVAL.coherence` | P6 | **A SCOPE DEFERRAL SINCE 2026-09-27.** Its arguments all have producers — `logits_fn` and `units_by_domain` as `curve_probe`'s, `encode` `_sig_encode_fn`'s callable (the one `DOM.rekey` takes), `rng` an `eval` child — and no row of the register's §8 builds it. The `sample` parameter was resolved away on 2026-09-02: **Q-EVAL-10**. |
| `EVAL.verdicts` | P6 | Three of four arguments — `silhouettes`, `affiliation`, `coherence_reading` — have no producer; the fourth, `domain_sizes`, comes from `DOM.census`, which stage `R` already collects. |
| `EVAL.wrongness_probe` | P6 | Takes a **copy** of the store so the instrument cannot edit what it measures; MEM's surface produces no copy, and adding one is a signature change. Its `scorer` is the same missing logits callable as `MEM.judge`'s **and takes the same arity, `scorer(ctx, src) -> logits`** (Q-MEM-8/Q-MEM-10, 2026-09-02). |
| `EVAL.verification_fit` | P6 | Same missing copy; its inner loop is genuine `units.Steps` and must never be compared against `curve_every`. **`verify_mode` landed 2026-09-04 (Q-EVAL-11) and is not part of the gap**: it is `MEM.verify`, a frozen lever the root holds, passed the way `vocab_slots=LM.vocab_slots` and `lm_kind=LM.arch` already are into `MEM.open_store`. `K12` computes "produced" from the order tables' prose and a deferred entry point has no row, so **until `compose.DEFERRED_ENTRY_POINTS` names it, K12 reads `verify_mode` as a second gap** — the residue is one clause and it is recorded below in §5. |
| `MEM.judge` | P4/P5 | `scorer(ctx, src) -> logits` is needed by the **default** arm (`MEM.verify` defaults to `selfcon`) and must be *the same forward path training used* (M47). **Since 2026-09-27 that path exists as a closure, and its ARITY is the gap:** `_logits_fn` is `fn(x, *, prefix_bytes)` and routes on the bytes before the window (Q-EVAL-12), while a **stored** entry has no prefix bytes and carries `Store.src` — so the declared shape is two arguments (Q-MEM-8), and a scorer that routes on a stored id is a second routing rule nobody has ruled on. **Q-MEM-8 is RESOLVED and names the row to write when the scorer lands:** at the END of the `dom.manage` block, inside that block's single `Cadences.due` answer. Because `scorer` carries a default, **no check can see it**: a row calling `judge(mem, store)` passes everything and yields `n_checked = 0` forever, which `memory/api.py:350-352` itself names as the inert state. |
| `FAB.contribution` | P4 | `candidates` is the eligible past-grace set, which lives in `Population`'s books — no entry point exports it and O10 forbids the root reaching into `pop` — and `targets` is the flush's own shifted cut, the loop's slice with no row. `baseline_logits_fn` has a candidate since 2026-09-27, the memory-off closure, and it is still not this argument: the whole C3/H11 repair is that the baseline comes from **the same callable** that produced `baseline_loss`, which is the training flush's forward, not a held-out closure over prefix bytes. |
| `CAP.observe` | P4 | **New.** `improving` = `(slow - fast)/|slow|` off the growth controller's EMAs, which live **inside FAB** and are on no returned record; `observations` is the valve-evaluation count tied to a hardcoded 0.998 EMA rate the caller cannot see. The root must **not** maintain a second EMA pair over the same loss to manufacture them — two mechanisms deciding independently whether the run has stalled is the recorded defect where the valve fired hardest exactly when the run was degrading worst. `blackout`'s home is now half-built: **Q-FAB-6** gave `FAB.grow_check` the `shift_at` stamp and put the resulting blackout state on `GrowReport`, so CAP neither reads FAB's `cooldown` at the call site nor has to mint a blackout-window lever it has no census row for; what is still missing is the root join and the two EMAs. |
| `WORLD.manage` | P4 | **New.** `plateau` contradicts the package's own `state_dict`, which says the plateau state `(_wl_ema, _wl_lastgrow)` **moves inside this package** and travels in the checkpoint — if the state is inside, the boolean is computed inside, and both sentences cannot hold. `add_param_group` needs OPT to name one of its two AdamW instances (**Q-OPT-7**). `latent` is real but arrives **backwards** (`loss_terms` is a `B` row, this pass was `A`). |

**A later phase is not by itself a reason to defer.** Each reason above is about an **argument with
no producer**, which is the only kind that survives the backwards check.

**What the deferrals cost, said plainly**, because a deferral that hides its cost is the
shape it replaces: the run has no capacity valve (nothing lifts a cap, so `CAP.caps` returns the
starting ceilings and every block reason reads *unreachable*), no WORLD growth, no learning-curve
probe at `EVAL_CURVE_EVERY`, no per-expert contribution and so no informed spare rule, and no
wrongness sweep. *(This paragraph also listed no best-model save, no restart damping and no memory
retrieval until 2026-09-27: the retention probe (Q-EVAL-12) supplies the first and the reading the
second judges on, and the memory-on closure is the report path's retrieval — built OFF, so at the
shipped `EVAL_RETENTION_EVERY=0` `Retention.counters().inert_reason` still reports "no curve value
has ever arrived" and `OPT_DAMP_SOURCE='off'` keeps the damping unjudged. The in-package read probe
reached `MEM.read` from 2026-09-21, Q-MEM-9.)* **All of that was already inert**: the rows
named calls whose arguments nothing supplies. The deferral does not remove a mechanism, it stops the
tables claiming one, and it names the producer each is waiting on.

### 3.7 What could NOT be placed, and is therefore reported rather than rowed

* **The self-inflicted-shift notification to the fabric — PLACED 2026-09-02, and this entry is kept
  as the record of why it could not be before.** At an epoch roll, at a retok and at an LR restart
  the old tree calls `fabgrow.note_shift(step)` (`:6515`, `:7787`, `:7120`) to open a growth
  blackout. No FAB entry point accepted it: `manage`, `observe` and `grow_check` took `step_windows`
  and losses, not a shift event, so the valve half had a route (`CAP.observe`'s `blackout`) and the
  fabric half did not. **Q-FAB-6 is RESOLVED**: `FAB.grow_check` gained `shift_at=None`, typed
  `units.Windows` — a **frozen-signature move**, made now because most of the entry points are stubs
  and the same change after P4 writes the WATCH→BURST→RECOVER machine is a body rewrite. It went on
  `grow_check` and **not** on `manage` as the question proposed, because in the old tree the blackout
  gates **growth**: `note_shift` sets `blackout` at `:2948` and two of its three consumers are
  `:3004` and `:3012`, both inside `PlateauGrowth.step`, which is `grow_check` here. (The third is
  `:7397`, the loop's own capacity valve, which is `CAP.observe`'s `blackout` — see Q-FAB-6.)
  `manage` is cull-and-spare and has no cooldown to suppress.
* **A resegment for MEM at an epoch roll — SUPERSEDED; the roll now re-segments and tells MEM and
  DOM.** This entry said `MEM.maintain(resegment=...)` is documented for a *retokenization* and that
  an epoch redraw is a new stream, not a new segmentation. Both premises moved: the roll now calls
  `TOK.tokenize` at the vocabulary as it then stands — which is where every deferred retok is
  performed (Q-RUN-8) — so `spine/loop.py` hands MEM `resegment=` on the first flush after every
  roll, and `DOM.on_retokenize` when the match table moved (Q-DOM-2). Kept as the record of why the
  call was once refused.
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
  **2026-09-27 (04-Q11 (b), register C02, Proposal 05 §8 1.6):** `FAB_LR_OWN=1` at
  `OPT_LR_SCHED='none'` runs and stays finite — 30 windows at `FAB_N0=256`, `fab.lr_calls` equal to
  the optimizer steps, every live expert scaled, the table in [0.7625, 1.0]
  (`tests/test_fabric_forward.py` W9). ISSUES P1-H15 cannot arise here (the applied rate is the
  `applied_lr` argument and the endpoints are wires), and `fabric/levers.py`'s *"UNFIXED CRASH"*
  comment is corrected. **OWED, and larger than a low fix:** the table still reaches no parameter —
  W9 pins the loss curve equal to `FAB_LR_OWN=0`'s bit for bit, and must flip when a consumer lands —
  so 04-Q11 (b)'s on-against-off sweep arm measures nothing until one exists. The consumer is a
  frozen-signature move (a parameter on `OPT.maybe_step`, or a FAB rescale around the step), and
  C02's `'newborn'` scope depends on it.
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
is a signature change, and none was reached by the stub-only `compose(environ={})` of their day: it
halted at `CAP.startup_refusals`, and the rows carrying these six either sat past that point or are
on the resume path an empty environment never takes. That is the shape this file's own header calls
*"a defect hidden behind an earlier stub, this project's oldest"*. *(This paragraph said
`RUN.process_setup` "raises several rows earlier" until 2026-09-04. It was true when written and had
not been for some time — `RUN.process_setup` is the first row and has had a body since **D12**. The
shape is unchanged; only the name of the stub these defects hide behind has moved. And it said
"halts on the **29th** of the 41 rows in `ASSEMBLY_ORDER`" until Q-EVAL-12's review: nothing halts
it now — `compose(environ={})` returns a System at stage `'assembled'` (measured 2026-09-27) — and
`CAP.startup_refusals` is the **30th**. The six sit past a stub no longer; the resume path is still
one an empty environment never takes.)*

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
   a non-`Windows` (ISSUES P1-H51: all 37 Clock-unit levers resolve to bare ints and the typing is real
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

**Two `sidecar` refusals were disarmed — Q-CKPT-2's residue, RESOLVED 2026-09-22, and the producer
it asked for existed the whole time.** `SIG.load_state_dict` and `FAB.load_state_dict` take a
`sidecar` that `_sidecar(sysm, restored, PFX)` read as `Snapshot.geometry[PFX]` — a **nested** key.
The recorded map is flat and prefixed, so the lookup could never match and both received `None` on
every real resume; `_sidecar` recorded the disarmed state on `System.warnings` rather than letting a
dead guard look armed.

**The sidecar is in the package's own payload slice, written by the package**, and this document's
own SIG section has said so in prose the whole time: *"Checkpointed: … plus a sidecar carrying
`width_units`, `alphabet_size`, `space`, `d`, `mode`"*. Read off a real checkpoint rather than
inferred: `payload['SIG']['sidecar']` carries all five fields `SIG.load_state_dict` compares,
`payload['FAB']['sidecar']` all four of FAB's, and the flat manifest's `sig.*` is only
`sig.d`/`sig.space`/`sig.mode` — three of five, **missing `width_units` and `alphabet_size`**, which
are the two the refusal is really about. So the prefix-*slice* alternative this paragraph used to
pose as the open question is the worse of the two answers, and the claim that **`FAB.state_dict`
never has to emit the sidecar it never claimed to emit** was true of an earlier tree: it emits one.
`_sidecar` now reads the payload slice and keeps the old lookup as a fallback. **No frozen signature
moved** — the root hands back what the producer wrote.

**Driven, not argued.** A clean resume from a pristine checkpoint passes with `sig.width_units 192`
against the sidecar's 192 and both warnings gone. A checkpoint whose sidecar was edited to
`width_units: 999` is refused by name: *"SIG resume refused on width_units: the checkpoint was
written at 999 and this run resolves 197."* The other end fires too — `rank: 999` gives *"FAB resume
refused on rank: the checkpoint was written at 999 and this run resolves 8. This is an INNER
dimension … a same-shaped restore would be a different decomposition wearing the right shape."* And the 197 in that message is itself a finding, **but not the one this
paragraph first recorded.** It said the 197 came from pairing an early blob with the final
vocabulary file. **That attribution was wrong** (corrected 2026-09-23): a checkpoint paired with its
**own** vocabulary file resolved a different width too. The cause was `build_vocabulary`'s replay
arm **re-measuring `bytes_per_token` on the replayed vocabulary**, which carries every token the
parent minted online, so the width moved as soon as the parent had minted once — measured on a
default parent at 210 windows (6 tokens minted at window 201): recorded 192, resolved 194, *"SIG
resume refused on width_units"*, on every default run resumed after its first mint burst. The
refusal was right to fire; the width it compared against was wrong. The replay arm now adopts the
value the file recorded (Q-TOK-13) and the same resume passes at 192.

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
the 273 declared levers is named `LEVERS READ:` by a stub.** Neither of the two was dropped, and
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

### Q-CAP-1 — `cap.clamp` reports UNREACHABLE on six grounds and `D16` ruled on one of them — **OPEN 2026-09-05: AN EXTENSION OF THE RULING, FLAGGED RATHER THAN TAKEN AS READ**

*The framing, and it is a question about scope rather than about a defect.* `.rework/DECISIONS.md`
`D16` gives the valve's state table exactly one UNREACHABLE row, on one ground: *"no lift can ever be
earned | `CAP_TARGETS` excludes the arm | UNREACHABLE, per D15"*. Its next paragraph names two
further cases — a lift refused as `dead_rows_unmasked`, and `derive.lift_to` returning the cap
unchanged — as things that *"must not be mistaken for a clamp"*, and stops there: it does not say
what verdict `cap.clamp` should carry on them.

*What the implementation does, measured rather than described.* `capacity/api.py::_clamp_gate`
reports UNREACHABLE on **all six** grounds in `capacity/api.py::_CLAMP_BLOCKED_KINDS`. Swept over
25,344 configurations (`CAP_TARGETS` × `CAP_FAB_START` × `CAP_VOCAB_START` × `CAP_LIFT` ×
`CAP_LIFT_MIN` × `LM_MASK_DEAD_ROWS` × `FAB_SLOTS` = 4 × 11 × 8 × 4 × 3 × 2 × 3), a fresh
`assemble.build` per cell: **19,574 UNREACHABLE, 5,770 reachable**, and the 39,148 per-arm grounds
printed on those unreachable cells divide `unarmed` 22,247, `at_ceiling` 9,243, `refused_unmasked`
2,732, `nonpositive` 2,395, `never_pins` 1,372, `inert` 1,159. So **22,247 of 39,148 arm-grounds are
`D16`'s own row**; 2,395 + 1,372 more reach the *state* that row names — no lift can ever be earned —
through a cause the ruling does not mention; and **13,134 do not reach it at all**, because there
lifts ARE earned and are then refused by name or applied to no effect.

*Why the extension is probably right.* `D16`'s verdict transfers on its own logic — where no lift is
earned, none can be clamped — but the verdict this gate carries is about the CLAMP, not the lift. A
clamp needs an applied lift that overshoots a hard ceiling, and on all six grounds no such lift can
exist, so the question is INAPPLICABLE rather than merely unmet, which is what UNREACHABLE means
under `D15`. Reporting *"0 clamped of 0 lifts"* on those 13,134 arm-grounds instead would read as a
clamp that was live and never had to hold anything — the inert-versus-absent confusion this package
exists to refuse.

*Why it is still the owner's.* An implementation that widens a ruling's population by a factor of
about two, on grounds the ruling explicitly set aside as *"must not be mistaken for a clamp"*, is
making a decision and not reading one. `capacity/api.py::_clamp_gate`'s docstring argued the case
inside itself until 2026-09-05, which is how an inference becomes indistinguishable from a ruling;
it now states the argument and says plainly that the owner has not ruled.

**What the owner has to decide.** (a) CONFIRM the extension: UNREACHABLE wherever no lift can be
HELD AT A HARD CEILING, whatever the ground, and `D16`'s table gains a row saying so. (b) SPLIT the
verdict: UNREACHABLE only where no lift can be EARNED (26,014 of the 39,148 arm-grounds) and
armed-but-0 where lifts are earned and lost (13,134), which buys a sharper reading of the word and
pays for it with a *"0 clamped of 0 lifts"* line on configurations where no clamp is possible.
**The recommendation is (a)**, and nothing in the tree fails either way: no check compares a Gate's
verdict against `.rework/DECISIONS.md`, which is why this is a question and not a finding.

**2026-09-27 (register CONTRACT-Q-CAP-1, Proposal 05 §8 1.6), reporting only:** every arm's clause
now prints its ground by name — `(expert, ground unarmed)` through `(vocabulary, ground
refused_unmasked)` — at the R stage and at startup, and in the ledger-disagrees and ledger-agrees
branches that quote them. Before, each clause described its ground in words, so the names the
sweep above counted were on no line a run printed, and the bare word `inert` appeared only in the
UNREACHABLE boilerplate. The verdict and the classification are unchanged, and (a)/(b) is still the
owner's (register O19). Known answer: `tests/test_tok_dom_cap.py` C2, one configuration per ground,
which also pins the closed set (a seventh ground fails it).

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
because `compose()` **then** stopped at `RUN.process_setup`, long before the valve. *(That is no
longer where it stops, and this sentence said it was until 2026-09-04: `compose(environ={})` then
halted at `CAP.startup_refusals`, which is **past** `CAP.new_valve`. It halts nowhere now, and this
sentence said "now halts on the 29th of the 41 rows" until Q-EVAL-12's review: it returns a System
at stage `'assembled'` (measured 2026-09-27), and `CAP.startup_refusals` is the 30th row. Either
way the valve is built on every `compose()` today and all three of its Gates — `cap.valve`,
`cap.vocab_arm_honest`, `cap.clamp`; "both" here until the same review, one Gate behind
`capacity/api.py` — are readable without writing a line. The reading that found this one still had
to be done by hand; what has changed is that the next one of its kind need not be.)*

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
`src/` that name a defect ID *beside* the line number. **All three legs of that proof were wrong by
2026-09-05, and none of them survives as a live citation.** Two stood in `src/capacity/levers.py` —
`capacity/levers.py::CAPLevers` citing `ISSUES.md:417` for `M38`, and `capacity/levers.py::<module>`
citing `ISSUES.md:409` for `M36` — and both were converted to IDs that day (`ISSUES P1-M38`,
`ISSUES P1-M36`), which closes the class in `src/capacity/`; three more line citations in that
package went with them (`ISSUES P3-C30` twice and `ISSUES P3-C5`), each confirmed against the
defect's own text. Six other citations had already been confirmed the same way, by matching the
citing sentence against the defect body (`M65`, `M77`, `M24`, `L69`, `M20`, `C19`).
**The third leg had been dead since `0e056e7`** — `src/tok/levers.py` citing `ISSUES.md:357` for
`M23` — because that commit converted that file's citations to IDs. `357` appears nowhere in
`src/tok/levers.py`, which is exactly what the next paragraph says was done to `src/tok/`: this
sentence offered as live evidence a citation the sentence after it reports as converted away.
Both survivors were also cited *here* by line — `capacity/levers.py:346` and `:363` — and both of
those had rotted too: the sentences had moved out from under them inside `src/`, which is why this
paragraph names them by symbol and gives no line number of its own.
**AND THE `+88` HAD ITSELF DRIFTED, WHICH IS THIS PARAGRAPH'S OWN ARGUMENT ARRIVING ON THIS
PARAGRAPH.** The offset was measured on 2026-09-03. Re-measured 2026-09-05, before the conversion:
`.rework/ISSUES.md` is 2327 lines, `P1-M38`'s header sat at `:553` and `P1-M36`'s at `:545` —
**+136 on both**, not +88 — and `417 + 88 = 505` landed on `P1-M26`, a third defect again. `:417`
itself is `P1-M4` and `:409` is `P1-M2`. The sentence that read *"the `+88` line owns that ID"* was
true when written and false within two days. **The bare ID was ambiguous as well**, which is the
second reason the line went: `P3-M38` and `P3-M36` are different defects from `P1-M38` and `P1-M36`,
so `(M38, ISSUES.md:417)` named neither one thing nor the other once the line stopped resolving.

**Repaired in `src/data/` and `src/tok/` only: 17 citations, converted to the defect's ID
(`ISSUES P1-M77`), which does not move.** The `[so-config/facts]` entries have no ID and are now cited by
their opening words. **39 `:<line>` references into `.rework/ISSUES.md` are left in `src/` — counted 2026-09-05
after `src/capacity/` was converted, as every `:NNN` ref attached to an `ISSUES` mention, spread over
ten directories (`capacity`, `ckpt`, `data`, `domains`, `eval`, `fabric`, `memory`, `sig`, `spine`,
`world`) — and no single offset rebases them.** Two of the 39 are not live citations at all but the
quotations inside `src/data/api.py`'s and `src/capacity/levers.py`'s own cited-by-ID-not-by-line
records; the rest are, including several appended to an ID that already resolves without them. The
"50 … in the other twelve packages, all wrong by the same 88/90" this sentence carried until
2026-09-05 was a count, a package total and an offset that had all moved underneath it. They are not silently rebased here: a blind `+88` is the wrong repair — the two offsets
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
should know this half is now done.** *(2026-09-27, Q-DATA-9: the normalisation is
`spine/derive.py::stream_key`, which `data/api.py::_holdout_key` delegates to, so SR0's probe keys
its EVAL draw by the same rule without importing DATA.)*

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
`TOK.d_vocab_ceiling` row **then** cited *"lm/levers.py:127-141 and tok/levers.py:87"* as the two
files that *"record it as the outstanding repair"*, so the pointer from the file that made the repair
led to a paragraph calling it outstanding. *(That row has been rewritten twice since: it now cites
both files by SYMBOL rather than by line and retracts the "both record it" clause by name, so neither
line citation quoted here is in `src/` any more. This sentence was in the present tense until
2026-09-05 and quoting it that way was a claim about a file that had moved.)* **(a)** said `assemble.py` declares
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

**What that edit did not repair, and what closed it on 2026-09-05.** `src/tok/levers.py::<module>`
carried the mirror of LM's conflict (a) — a `TOK.vmax` → `LM.d_softmax_width` `Coupling` described in
the **present tense**, together with the `build()` failure it predicts — and was left for whoever
touched TOK next, because `assemble.py`'s row named both files together. **That is a live false
attribution and not a stale aside:** `assemble.py::COUPLINGS` exists, so the citation *opens* and
every mechanical check passes while what it is said to declare has not been in the file since the
census was applied. It is now written in the AS RECORDED / WHAT IS TRUE NOW shape
`src/lm/levers.py::<module>` uses, with the reversal, the absent `LM.d_softmax_width`, and the two
surviving **non-row** spellings of `TOK.vmax` in `spine/assemble.py` named one by one — the module
docstring's list of names that do not exist, and `spine/assemble.py::_Fields`'s undeclared-read
example, which that paragraph had attributed to `Coupling.__init__`, a symbol that exists and has
never held it. Conflict **(b)** of the same block was stale the same way and went with it: the
`Windows → Flushes` conversion it recorded as not existing is `spine/derive.py::flush_period_windows`,
and the row it describes has taken `("OPT.batch_windows", "CAP.pin_windows")` through that function
since `pin_windows` was re-typed. **That repair left its own summary table asserting the retracted
reading, forty lines below itself, for a further day:** the same docstring's WHAT IS DELIBERATELY
ABSENT block sourced `d_cap_lift_period` *"from TRAIN.batch_w x TRAIN.grow_cap_every"* — a package
that does not exist, two field names the census renamed, and a **product** where the declared row
divides — and produced the right number anyway at the shipped `OPT_BATCH_WINDOWS=1`. Corrected
2026-09-06, with the retraction kept beside it. **A paragraph repaired while its own summary table
keeps the retracted reading is the shape conflict (b) is about**, and it is the same failure as the
CAP paragraph above, where one false universal was replaced by three narrower false ones: a
correction scoped to the sentence that was reported rather than to the class it belongs to.
**Two carriers now point the wrong way and neither is in this owner's
line:** `spine/assemble.py`'s `TOK.d_vocab_ceiling` row still calls `tok/levers.py::<module>` *"the
half that is still outstanding"* — and `tools/render_wiring.py` republishes that reason into
`docs/03_WIRING.md`, so the stale carrier is once again the auto-rendered one — while
`src/memory/levers.py::<module>` still records of the same conversion that *"there is today no legal
conversion from a Windows-typed cadence to the flush clock"*. Both are filed with exact
replacements.

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
the other — and, since 2026-09-05, a **negative** window count and a divisor that is not an `int` —
and **has no oracle row at all**. The frozen replay is `.rework/oracle/`, and it is eight tables —
`_phases`, `blowup_stale`, `bwt_of`, `cull_gate_open`, `curve_verdict`, `forgetting_of`, `lift_to`,
`pin_tick` — of which none is this function; the *575 cases, 0 mismatches* that
`tests/test_derive.py` prints are those eight replayed, and they contain no case of it. What covers
this function instead is a block of **hand-derived known answers** in `tests/test_derive.py::smoke`,
which gives the reason there rather than leaving the absence to be read as an oversight: an oracle in
this tree means values CAPTURED from the frozen old tree by `.rework/capture_oracle.py`, which lifts
**module-level functions** out of `self_organize.py`, and the old tree resolved its LR horizon
somewhere else entirely — in a closure inside `main()`, by a different computation, with the divisor
this function takes never formed at all. So the row is not merely absent, it is **impossible**: there
is no behaviour of this shape to capture. Hand-derived answers are a weaker artefact than a frozen
table and are named as the weaker one here. *(This clause claimed
oracle coverage until 2026-09-06. The claim was inherited, and the parenthetical added on 2026-09-05
— that only "the two newest refusals have no oracle row yet" — entrenched it by implying the rest of
the function had one.)* The alternatives are
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
branch — and reachable in fact only since **Q-FAB-8**, when the loop began passing `head` and
`targets`); and `FAB.state_dict` **no longer claims to save `ctrl`** — `ctrl` exists only on the
transition arm (`:1907`, read at `:2827`), `FAB.build` allocates none, so the contract was promising
to checkpoint a parameter nothing creates. It returns to that list with the arm and not before.
**Since 2026-09-24 the refusal is PRINTED as one:** `FAB.build` raises `spine.gate.NotBuilt` inside
`compose()`, before `System.refusals` is printed, so `FAB_HOP_MODE=transition` died as a traceback
with rc=1 — a sweep reads that as a crash. `run.py` now catches `NotBuilt` around `compose()` and
prints `REFUSED: <message>` and exits **2**, exactly like the startup refusals.

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

**2026-09-27 (register LOW-FAB-MERGED-REPORT, Proposal 05 §8 1.6): one merge gate per scope.**
`fabric/api.py::_three_state` renders a gate's count from the ledger key of the gate's own name, and
the per-pass verdict was named `fab.merged` — the name of the RUN-total counter — so the report
paired the ledger's total with the last pass's verdict. On the register's I10 configuration (seed 3,
`FAB_GRACE=1`, `FAB_MANAGE_EVERY=25`, 300 windows, run.py's defaults) it printed `fab.merged 4`
beside `gate:fab.merged ('armed-but-zero', 4, '0 vs 0.1 -- 476 expert(s) were past grace at entry
and no pair with a past-grace member sat within FAB_MERGE_DIST=0.1 cosine; ...')`. **Ruling: a gate
named like a ledger counter takes that counter's scope.** `gate:fab.merged` is now the **run-scope**
verdict — lineage, since FAB's ledger crosses a resume — FIRED iff the ledger's `fab.merged` is
positive, with that total as its count, UNREACHABLE only when nothing merged and no pass in the
ledger had a past-grace expert at entry with merging on (a new counter, `fab.merge_armed_passes`,
counts those passes), and armed-but-zero otherwise; its reason quotes the residual quantiles of the
last pass that merged and the cumulative `fab.merge_declined_grace`. The per-pass verdict, its
fields and its reasons move unchanged to **`gate:fab.merged_last_pass`**, whose count is a new gauge
of the same name written on every pass. `ManageReport` is unchanged. A checkpoint written before
this build carries no `fab.merge_armed_passes`, so its passes read as unarmed in the run gate's
reason (a merge it recorded still fires the gate). **After**, on the same
configuration: `gate:fab.merged ('fired', 4, '4 vs 0.1')` and `gate:fab.merged_last_pass
('armed-but-zero', 0, ...)`, with `fab.merge_armed_passes 11` of 11 passes, and the loss curve
byte-identical to the unfixed tree's (reporting only). The register's expected "2 fired" predates
this tree; the known answers pin the structure, not the count: `tests/test_fabric_internals.py` I13
(a pass that merges one pair and one that merges none; nothing past grace; `FAB_MERGE_DIST=0`) and
`tests/test_fabric_forward.py` W8 (the I10 configuration). Left alone, because no run-scope counter
shares their names and the ruling does not reach them: `gate:fab.cull_gate`,
`gate:fabric.cull_eligible`, `gate:fab.growth_armed` and `gate:fab.lr_own` still print a count
nothing counts beside a verdict (for example `('fired', 0, ...)`).

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
the only in-loop retrieval is `MEM.maintain`'s job 1, its `probe_contexts` **had no producer** when
this was ruled, and `MEM.read` is a **deferred** entry point for want of `queries`. Therefore `n_promoted ≡ 0`,
probation ≡ 100% of the store, every eviction takes the probation branch, `n_evict_main ≡ 0` and
`pressure` is **exactly 0.0 for every setting** — not "≈0 at the measured ratio". *(That chain is
HISTORY as of 2026-09-21: `spine/loop.py::_flush` passes the previous flush's batch as
`probe_contexts`, and since 2026-09-24 the probe issues `MEM_PROBE_ROWS` per-position queries per
fire — Q-MEM-12. Promotion, main-branch eviction and a reachable verdict are live at the defaults;
the ruling itself — keep the definition, keep 0.80, measure before retuning — stands.)* Retuning either
lever against a structural constant is unfalsifiable, which is why (b) is refused; (c) throws away
the one thing the definition gets right (evicting never-read junk is not scarcity); (d) is refused
by D3 and by the owner's standing rule that a broken instrument does not convict a mechanism.

**The Gate reports a STATE, not a number.** With `n_promoted == 0` over the interval it prints
UNREACHABLE and never `0.000` — naming, from the counters and `maintain`'s own `mem.probe` Gate,
WHICH no-promotion state holds (`MEM_PROBE_EVERY=0`; no query row issued yet; rows issued and
nothing promoted yet — Q-MEM-12; it printed *"no promotion path: probe_contexts has no producer"*
until then) — and it names the **second** cause as well, because there are two: no promotion, *and*
the arm is not selected (`src_share=0.5 > 0` makes `quota_arm` `"reservoir"`, and `FAB.grow_on_mem_pressure` ships
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
windows. Nothing about the level should move before that run. *(The loop now supplies the previous
flush's batch, which is that stub with a one-flush lag; but every run before 2026-09-24 probed at ONE
query per probe, not 64 — Q-MEM-12 — so no run taken before that date is this measurement.)*
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
bare `int` for all 37 Clock-unit *levers* (ISSUES P1-H51, three of five gates handed bare ints until
2026-08-30); a module constant has no `Config` to drop its kind, so it is written `units.Windows` at
its definition. That is a **construction, not a conversion** — it re-attaches a kind, it does not
cross one. *(This sentence said "four" until 2026-09-03. It is the sixth count this document has got
wrong, and the one K13 cannot catch: **`four` is a word, and the check reads digits.** It is listed
in K13's own docstring as the worked example of what it does not see.)*

**And this gate has no row**: rows are entry-point calls and no entry point prints the progress line
— the loop driver does, the way it owns the window cut `_window_bounds` names. So seven keys since
2026-09-27 (`'retention'`, Q-EVAL-12), six of them rowed, and that asymmetry is stated at `_periods`,
at `new_cadences` and in the `cadence` row.

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
4. **Budget.** 19 of 25 wires, 23 declared couplings. This would spend a line on the
   least reachable case. *(Ledger unchanged by this ruling: still **19 of 25**, **23 couplings**,
   and `NOT_WIRES` is now **7 entries** — Q-OPT-1 added one in the same round.)*
   *(This point read **"one of the last lines"** until 2026-09-04. The three numbers beside it were
   and are correct, so this is not the `eval/api.py` miscount — but the phrase carries the same
   belief the miscount did, and **six of the twenty-five remain**, which is not "the last". Corrected
   because this ruling is one of the ones later readers cite when weighing a wire against an
   argument, and the reason it gives should not be scarcity it does not have. **The ruling itself is
   untouched: it rests on points 1–3, and point 4 was never the one carrying it** — `affects()` sees
   no cadence reach for any gate, so a single WORLD row would make the graph look more complete than
   it is, and that is true at any budget.)*

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
signature moves and no lever default changes. *(That clause is about **this** ruling and stays true
of it. `curve_probe`'s signature did move later, on 2026-09-04 under **Q-EVAL-11**, on unrelated
grounds — `step`, which `CurveReading` already declared. The sample size, `ev.windows`, is
untouched.)*

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
lever read the root already does — eight new entry points on a surface where most of the 132 are already
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
`(len(Segmentation.ids) - 1) // ctx` **every epoch**, and online minting lengthens tokens and shortens
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
**And it was inert regardless, in the state that had to be reported:** `probe_contexts` had no
producer when this was ruled, so with the default `None` the honest reading was `n_probe_fired`
counting the **cadence** with `n_probe_rows == 0` — **armed-but-0, not unreachable and not silence**,
which is `maintain`'s own rule that a probe which fires and retrieves nothing is a different finding
from one that never fires. *(Superseded 2026-09-21: the loop passes the previous flush's batch, so
that reading now holds only on the first flush of a run and of each epoch. "Strides `probe_rows`
rows out of `probe_contexts`" is read, since Q-MEM-12, as rows of the per-position key windows —
one query per position, the write path's own keying — and not as rows of the batch.)*

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
`encode`. `logits_fn` is untouched there, so this ruling still holds in both directions. `curve_probe`
and `verification_fit` were reopened on 2026-09-04 by **Q-EVAL-11**, on their own grounds again —
`step` is a stamp and `verify_mode` a Gate input, neither is a scoring hook, `logits_fn` is untouched
on every EVAL signature and no body gains arithmetic, so what (c) was refused for does not arrive
through them either.)

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

**AMENDED 2026-09-27 (Q-EVAL-12, Q-MEM-15): THE HELPER IS WRITTEN, THE RESIDUAL IS RESOLVED, AND
BLEND IS CREDITED THROUGH A ROW.** `_logits_fn(sysm, *, use_memory)` exists beside `_key_fn` /
`_head` / `_sig_encode_fn`, and the four data the residual paragraph above named are ruled in
Q-EVAL-12: `signature` off the pinned prefix before the window, `domain_id` from `DOM.nearest`,
`live_domains` the count the next training window will use, and **`novelty` as zeros, named** —
still the one datum with no honest source off the training path, now said at the call rather than
left open. The sentence that `blend` "is called from that spine helper and never from a row"
changes in one respect: the helper is still the only caller, and `MEM.encode_queries(...)`,
`MEM.read(promote=False, ...)` and `MEM.blend(...)` are written as calls in the note of the `R`
`EVAL.holdout_probe` row, which is how K6 credits an entry point reached inside another row's
reading. And `read(promote=False)` counts nothing now (Q-MEM-15), where this ruling's text had it
counting the read.

**Literature bore, narrowly.** kNN-LM (Khandelwal et al., ICLR 2020) interpolates **in probability
space** — `p = (1-λ)·p_LM + λ·p_kNN` — and reports the perplexity of that mixture, i.e. it takes the
log of the interpolated distribution and scores it. So `MEM.blend`'s probability-space signature is
the standard formulation and option (a) is what the field already does. The literature does **not**
bear on where the join lives in this tree; that is settled by O10 and by the C8/C9 record.

### Q-CKPT-3 — `CKPT.save` never wrote `best_state`, so every resume overwrote its parent's best model — **RESOLVED 2026-09-21: ⚠ A FROZEN SIGNATURE MOVED — `save(..., reason, best_state=None, suffix="")`**

`ckpt/api.py::load` reads `blob.get("best_state")` and its docstring says in as many words that
"`best_state` IS IN THE CHECKPOINT (ISSUES P1-M45)". `save` built its blob from four keys —
`payload`, `geometry`, `step`, `epoch`, `reason` — and **never put `best_state` in it**. So
`Snapshot.best_state` was `None` on every checkpoint this tree has ever written,
`new_retention(restored=None)` started cold in every child process, and the first post-resume probe
satisfied *"no best yet"* and overwrote the parent's best model. That is **M45 itself, live, inside
the function whose entire purpose is to prevent it** — and `LOOP_ORDER`'s own C row for
`CKPT.Retention.state` states the consequence in advance: *"Without it the first post-resume probe
satisfies 'no best yet' and overwrites the parent's best model (M45)."*

**Why the signature and not the payload.** `payload` is the composition root's opaque per-package
mapping and the C row is explicit that `best_state` is *"a FIELD OF ITS OWN and not part of
payload"*; `Snapshot` declares it beside `payload`, not inside it, because retention is CKPT's own
state rather than a package's. There is no route into the blob that does not go through this
signature.

**It is DEFAULTED, and that costs a counter.** `best_state=None` means no existing caller breaks —
the same shape `Q-FAB-6` established when `grow_check` gained `shift_at=None`. A defaulted argument
is invisible to K10, so `_SAVES` gains `best_state_supplied` / `best_state_absent`: without the
pair, *"the composition root never wired it"* and *"it was wired and the retention had no best to
record yet"* are one number, which is the state this ruling is repairing.

**Found by calling it.** Nothing had compared `save`'s blob against `load`'s reader, because the
loop driver that writes checkpoints was itself only written this month.

### Q-WORLD-9 — `WORLD.geometry` reported `lat` under the name `hid` — **RESOLVED 2026-09-21: read it off the module the lever built. No signature moves**

`world.hid` was `int(w.preds.shape[-1])`. `WORLD_HID` is spent in exactly one place —
`build`'s `nn.Sequential(nn.Linear(d_model, hid), nn.Tanh(), nn.Linear(hid, lat))` — and `preds` is
`(n, lat, lat)`, carrying **no `hid` axis at all**. At the shipped defaults the field reported 32
where the lever said 128: a recorded geometry field naming one quantity and carrying another, under
an **EXACT** rule, inside the instrument that decides whether a resume is allowed to happen.

**Nothing could have caught it, because nothing called the function.** It is the only `geometry()`
in the tree (Q-CKPT-1) and `spine/loop.py::_save` did not invoke it until 2026-09-21. The first
comparison ever made refused a legitimate resume by name — *"WORLD_HID: the checkpoint was written
at world.hid=32 and this run resolves 128"* — which is the good outcome: a loud refusal on the
first call rather than a quiet acceptance on the thousandth.

It now reads `int(w.encoder[0].out_features)`, so a change to the encoder's shape moves the recorded
field with it. The root additionally **cross-checks the five fields the live manifest and
`WORLD.geometry` both carry**, because the root is the only thing that sees both producers, and a
field with two producers and no comparison is the shape this whole document is organised against.

### Q-WORLD-10 — `WORLD.forecast` was held back from its call site — **RESOLVED 2026-09-24: `world_proj` is born ZERO, re-zeroed on load when no forecast ever reached it, and the call site exists (`spine/loop.py::_flush`, a `WORLD.forecast` LOOP_ORDER row). No signature moves.** (HELD 2026-09-22; the text down to the ruling is that hold, kept as history.)

`forecast` was written on 2026-09-22 and is the one finished entry point in this tree that is
deliberately left without a caller. The reason is not the body — it is what the body computes with.

**Measured, at the shipped defaults, on a built `World`:**

| what | reading |
|---|---|
| `WORLD_FEEDBACK` | **`True` at the time — the lever shipped ON (it ships False since 2026-09-24)**, so the only thing withholding the forecast is the missing call site |
| `hasattr(world, "parameters")` | **`False` when this was written; `True` as of the same day.** `World` is a `__slots__` record, not an `nn.Module`, so `OPT.build` could not reach its tensors and every run printed *"WORLD.world exposes no parameters(), so it contributes NOTHING to the 'base' param group"*. `World.parameters()` closes it: 10 tensors, 31,944 elements, all ten in the `base` group, and the warning is gone |
| `preds` after `build` | **all zeros**, `(6, 32, 32)`, 3 slots live |
| `max abs(pop(z) - z)` | **`1.19e-07`** — float32 round-off. `_route` is residual (`outs = z + einsum(z, preds[live])`) and `preds` is identically zero, so every live predictor returns `z` and a convex blend of identical rows is `z`. **The population half of the forecast is the identity, exactly** |
| `world.forecast_rms` on one call | ~~`0.11047`~~ — **WRONG, corrected 2026-09-24: `0.002974` at the real call site, 7.6% of h's RMS `0.039029`.** `0.11047` was taken on a unit-variance synthetic input (`randn(4, 64, 128)` gives `0.1051`); `LM.embed`'s RMS at init is `0.0219` |

When this was written, `world_proj(pop(z))` was `world_proj(encoder(obs_emb))` with **both maps at
their random initialisation and no gradient path to move them**, and `forecast`'s own body recorded
`max abs(delta)` over 60 windows as **exactly 0.0 for `encoder`, `qproj`, `preds` and `keys`**.

**The first half of that is now false and the second half is not.** `World.parameters()` puts
WORLD's tensors in OPT's `base` group, and the same 60-window measurement re-taken reads **preds
7.955e-02, encoder 8.078e-02 / 8.075e-02, keys 1.737e-03, qproj 1.156e-03** — and **`world_proj`
exactly 0.0**. That one is not an oversight and cannot be fixed from the loss side: `world_proj`
appears in **no expression in the package but the forecast's**, so *the forecast's own call site is
the only gradient path it will ever have*.

**So the hold now rests on one thing instead of two.** The population is no longer the identity and
the latent is no longer a random draw, but a first call still adds `world_proj`'s
`uniform(-0.1, 0.1)` projection — one measured call returns `world.forecast_rms` **0.002974, 7.6%
of h** (the `0.11047` first written here was a synthetic-input reading; see the table) — and
`WORLD_FEEDBACK` already ships `True`, so a call site is the only thing withholding it. That is a
**bootstrap**, which is what adding any head looks like, except that this tree has a rule for it and
`world_proj` does not follow it: `fabric/api.py::build` zero-inits `A`/`B` so *"every expert is born
an identity, so adding one never disrupts what already works"*, and `world/api.py::build` zero-inits
`preds` citing the same sentence. `world_proj` is the third tensor of that kind and is drawn uniform.

**What has to be true before it is wired**, in this order: (1) ~~WORLD's tensors reach a param
group~~ — **DONE**, `World.parameters()`, and the startup warning is gone; (2) **settle
`world_proj`'s initialisation** — born-an-identity like every other tensor this tree adds mid-run,
or born random and allowed to disrupt — which costs nothing to answer while there is no caller and
is expensive to answer after; (3) only then a call site, at which point `world.forecast_rms` beside
`lm.encode.extra_applied` prices what it contributes. Until (2), this is **BUILT BUT NOT WIRED, ON
PURPOSE**, and that is a third state beside `notes/07_WIP.md`'s three — worth naming, because the
other two ways to leave it (no body, or a body and a call site) are both worse than this one.

**THE RULING, 2026-09-24.** Step (2) is settled as **born-an-identity** and step (3) is done:

- `world/api.py::build` zeroes `world_proj`'s weight and bias **after** the uniform draw, so the
  generator stream is unchanged and `encoder`, `qproj` and `keys` hold exactly the values they held
  before (`tests/test_world.py` W1 replays the draw and compares).
- `spine/loop.py::_flush` passes `WORLD.forecast(...)` to `LM.encode` as `extra`, inside the same
  autocast block; LOOP_ORDER gains a `("B", "WORLD", "forecast", ...)` row between `LM.embed` and
  `encode/decode/lm_loss`, and `_CALLS["B"]` names it.
- `WORLD.load_into` re-zeroes a `world_proj` no forecast ever reached. **Decided by a saved field,
  not by a counter:** `WORLD.state_dict` now writes `proj_trained` (whether `forecast` has ever
  returned a tensor in this lineage — the only way `world_proj` can have had a gradient), and
  `load_into` uses it when present. Only a blob that predates the field falls back to "`world.forecasts`
  absent from the saved counters". The report says which: `world.proj_trained_basis` (a string gauge
  for this load) and `world.proj_zeroed_on_load` (re-zeroing loads, counted across the lineage like
  `world.state_restored`, written **after** the counter merge so a parent's value cannot mask this
  load's).
- `LM.encode` writes two float gauges on its `extra` arm, `lm.encode.extra_ratio` (the latest
  RMS(extra)/RMS(h), h taken before the add) and `lm.encode.extra_ratio_max`. `world.forecast_rms`
  is half a reading, and only `encode` holds both halves. Both are ABSENT when no `extra` arrives.

**Measured on this tree** (`DATA_STREAM_BYTES=200000`, one thread, CPU, 128-wide GRU; the
"unwired" arm is the parent commit, and `WORLD_FEEDBACK=0` on this commit reproduces it exactly):

| what | reading |
|---|---|
| flush-0 LM loss, wired against unwired | **equal to the bit**: 8.354218 / 8.277447 / 8.332117 on seeds 0 / 1 / 2, and 8.313601 at `LM_ARCH=transformer` |
| the forecast at flush 0 | **exactly 0**; ‖dL/dW‖ on `world_proj.weight` **0.4197** (seed 0) — the path learns from the first backward |
| ‖W‖ of `world_proj` | 0.00122 after one step, 1.027 after 60 windows, 2.195 after 300 (seed 0) |
| `WORLD_FEEDBACK=0` against the parent commit | **bit-identical** loss curve over 300 flushes (max\|diff\| 0.0) |
| wired minus unwired, paired by seed, 300 windows, seeds 0-4 (mean ± SE, seeds lower) | full run **-0.028 ± 0.020** (4/5); last 150 flushes **-0.058 ± 0.029** (4/5); last 100 **-0.099 ± 0.033** (5/5). Per seed, last 100: -0.183 / -0.023 / -0.170 / -0.076 / -0.042. SMALLER than the design round's -0.195 ± 0.022 (5 seeds, 400 windows), which was measured on the tree before the causality fix (Q-FAB-7) and is not comparable with it |
| `lm.encode.extra_ratio` at 300 windows | latest 0.41-1.87, `extra_ratio_max` 0.74-3.08 over seeds 0-4 — the forecast is already the size of h |
| resume of a 150-window **pre-wiring** checkpoint | restored ‖W‖ **3.70398**; without the re-zero the first flush reads **5.584440** with the forecast at 4.0% of h; with it **5.591557**, exactly the parent tree's own resume. `world.proj_zeroed_on_load` 1, basis the counter fallback |
| resume of a 150-window **wired** checkpoint | `world_proj` restored trained (‖W‖ 1.6209), `world.proj_zeroed_on_load` 0, basis the saved field |

**The contract's `0.11047` was wrong** (see the corrected row in the hold's table): at the real call
site a first call of the old uniform `world_proj` added `world.forecast_rms` **0.002974, 7.6% of h's
0.039029**.

**Why the saved field and not the counter alone.** A counter-keyed guard re-zeroes a TRAINED
`world_proj` the day anyone prunes or resets WORLD's counters before a save, silently, on the next
resume. The field costs one payload key and no signature. The counter inference is kept only as the
fallback for blobs written before the field existed — every such blob predates the call site too, so
for them "no `world.forecasts`" and "never trained" are the same statement.

**Rejected, with the numbers the design round measured (on the parent of the causality fix,
3 to 5 seeds, 400 windows):**
- *A learned gate `alpha = 0` over the uniform draw.* `dL/dW = alpha·(…)` is exactly 0 at birth
  (`alpha` was 0.036 at step 100); pooled paired gain -0.017, i.e. nothing. It also adds a tensor to
  OPT's `base` group (38 → 39), and every existing checkpoint's AdamW restore is then refused as
  `param_group_shape` — which `spine/compose.py` discarded when this was written (the `LoadReport`
  returned by `opt_api.load_state` was not read; the only trace was `opt.ckpt.refused 1`). That
  discard was a separate defect, filed on its own and closed by Q-CKPT-4: the refusal now stops the
  run by name.
- *A scheduled ramp `alpha = min(1, k/R)`.* Needs a new lever, a frozen-signature change and a clock
  that survives a resume: `clock.opt_steps` restarts at 0 on resume while `clock.step` carries on, so
  a ramp on the first restarts and a ramp on the second is already at 1 over an untrained draw.
- *Wiring the uniform draw as it is.* Not exact at step 0 or across a resume, and the tree's own
  rule ("every expert is born an identity") says no.
- **The double-zero trap:** a zero gate ON TOP OF the zero `world_proj` left every gradient at
  exactly 0.0 for 60 steps. Never add a multiplicative zero to this path.
- *normal(std 1e-3) instead of zero.* Indistinguishable at step 0 (within 0.13% of h) and not
  rankable on loss at this scale (two near-identical inits differ by up to 0.48 nats per 100-flush
  block); zero is chosen for exactness and for the rule. It is the fallback if the GPU runs show the
  zero start costs anything.

**Open for the owner:**
- The LM loss becomes the WORLD encoder's main teacher (0.196 of encoder[0]'s 0.204 gradient norm at
  flush 300, design round), and WORLD's own loss rises (last-100 mean 0.443 → 0.530, seed 0).
  Feeding `world_proj` `pop(z).detach()` would keep WORLD's loss at baseline for about half the LM
  gain; not chosen, because performance decides and `forecast`'s docstring calls the coupling
  deliberate.
- **Nothing bounds the forecast's magnitude.** `lm.encode.extra_ratio_max` makes growth visible; it
  does not prevent it.
- MEM's keys come from `LM.encode` WITHOUT `extra` (`_key_fn`), while FAB and the readout see
  h + forecast. Invisible until MEM.blend lands.
- **Every default run from this commit on differs from earlier ones**, which stay comparable only at
  `WORLD_FEEDBACK=0`. `sweep_world.sh`'s `feedback_off` arm is now the unwired control.

**THE GPU EXPERIMENT RAN (2026-09-24) AND `WORLD_FEEDBACK` NOW SHIPS `False`, by the rule below.**
`gpu_world.sh` on one 140 GiB card, 12 runs at a time under MPS; 20,000 windows per run, seeds 0-4,
RUN_EPOCHS=1; the same seed run twice was **bit-identical**, so every difference is the arm's.
Last half of the per-flush loss, arm minus feedback-off, paired by seed:

| arm | last half | full run | seeds lower |
|---|---|---|---|
| feedback on | +0.0033 ± 0.0031 | +0.0271 ± 0.0101 | 2/5 |
| forecast trained by the LM loss alone (`WORLD_PREDICT_W=0 WORLD_COLLAPSE_W=0`) | +0.0904 ± 0.0683 | +0.3329 ± 0.1688 | 1/5 |
| `WORLD_ENABLED=0` | −0.0027 ± 0.0016 | +0.0041 ± 0.0114 | 4/5 |

The CPU gain (−0.099 at 300 windows) does not survive 20,000 windows: at this scale the forecast is
a per-token feature the LM learns for itself, which the design judge's first dissent predicted.
Without WORLD's own objectives the forecast path is **unstable**: latent_std fell to 0.13-0.85
(1.01-1.05 elsewhere), `lm.encode.extra_ratio_max` reached 31.2, and one seed lost 0.358. WORLD's
losses are what keep the forecast bounded. `WORLD_ENABLED=0` is better by 0.0027 in 4/5 seeds, under
2 SE; **WORLD stays enabled** -- the owner keeps it as the plug-in point for video and audio -- and
the question is re-asked once the synthetic corpus varies with the seed (DEFECT D-A13: all five
seeds trained on the same text, so this result spans initialisations, not data). The call site, the
zero-born `world_proj` and the gauges all stay; `WORLD_FEEDBACK=1` restores the wired arm exactly.
Results: `results/gpu_world_2026-09-24/ANALYSIS.txt`.
**CORRECTION 2026-09-26 (the decision register's verification, `docs/proposals/05_DECISIONS.md` note
WORLD; scripts under `results/decisions_2026-09-26/verify/`).** The numbers above stand; two readings
of them change. (1) *D-A13 did not apply to this fleet.* At d97779d, as at HEAD, `RUN_SEED` already
chose the synthetic text: seeds 0, 1 and 2 give three different stream hashes and twelve different
area bodies, identical between the two trees (`verify/emp2/seedvar.out`, `verify/emp3/seeds_d977.out`),
because the `make_proc` repair (`.rework/ISSUES.md`, "WHAT IT ALSO CLOSED") predates the fleet, and
`gpu_world.sh` passes `RUN_SEED` per run (`d97779d:gpu_world.sh:346`). The fleet's archive,
uploaded 2026-09-26 (`results/gpu_world_2026-09-24/ARCHIVE_READS.md`), shows `=== data plan:
protocol=generated` in all 21 logs with `EXTRA=''`: the default synthetic source. So the five seeds
trained on five texts and the spread spans data as well as initialisation. (2) *The fleet
read phase 1 only.* At `DATA_STREAM_BYTES=20000000` an epoch is about 102,000-106,000 windows and the
first phase bound (5 MB) falls near window 26,000; 20,000 windows at about 190 bytes each read
3.75-3.84 MB of eng + py (`verify/emp/pc_d977_s0.txt`, `verify/emp2/pp_*.txt`). Every arm therefore
trained on one stationary two-area mixture, with no phase change to forget across, and the cosine LR
at the stop was still about 0.92 of peak. The result is about WORLD's forecast on a stationary
mixture; it says nothing about retention. The re-ask is the whole-epoch, post-SR0 WORLD re-run the
register pre-registers (note WORLD), not a re-run at this shape.
**THE FLEET RAN ~15x SLOWER THAN ITS OWN CALIBRATION, AND THE CAUSE WAS THE MERGE SCAN (repaired
2026-09-25).** Calibration measured 461.6 windows/s over 12 runs in the first 150 windows; the fleet
then averaged ~25 windows/s over 21 runs x 20,000 windows (4.6 h against a 0.3 h estimate).
FAB.manage's step 0 built its merge pairs with an n^2/2 loop of scalar `sim[i, j]` reads -- one
device sync each on a GPU -- and the first manage pass is at window 501, past the calibration's
reach. `_merge_pairs` is now one tensor pass: on CPU 14 s -> 0.033 s at n=2049 and 53 s -> 0.23 s at
n=4001. It returns the scalar scan's list exactly (fabric-internals I10 holds it against the old loop,
including thresholds one double-ulp under an entry), and a 300-window run with merges firing
(`FAB_GRACE=1 FAB_MANAGE_EVERY=25`, seed 3, 2 merges) gives a byte-identical loss curve and log
against d97779d, so **every number in the table above stands.** The GPU rate after the repair is a
projection until the owner's next fleet measures it; `gpu_world.sh`'s ETA is still calibrated on
windows before the first manage pass.
**2026-09-27 (register LOW-GPU-WORLD-ETA, PENDING-GPU-THROUGHPUT-REBASELINE; Proposal 05 §8 1.5).**
`EXP=retok` and the new `EXP=world_epoch` calibrate on 600 windows (`CAL_WINDOWS`), past the manage
pass at window 501. `EXP=world` keeps 150 until the retok fleet's ETA-against-wall reading says
otherwise: its paste-back block prints the ratio and, past 1.5x, names this item. The post-fix rate
is measured inside that fleet and labelled "post-fix rate at the retok shape": windows/s and bytes/s
per arm off each log's own loop time, the act's per-byte cost against k0 (whose rate includes its
periodic saves, and says so; corrected 2026-09-27, build 1.5's review, under Q-RUN-8: that figure is
mostly k0's saves, so no arm is the plain-text rate and the act's cost is its own `loop.act_seconds` +
`loop.act_remap_seconds` over the arm's loop time, with the k0 figure printed qualified), and the
aggregate as every run's windows over the fleet's recorded wall at the chosen PAR, beside the GPU
model, PAR, MPS and NCPU. `EXP=world_epoch` is the WORLD re-run's shape (register note WORLD 3): one
whole WINDOWS x 189-byte epoch with the window cap out of reach, "RAN OUT OF STREAM" replaced by a
window-cap flag, and `TOK_RETOK_EVERY` and `DATA_DRAW` pinned; it refuses to launch before SR0.
`EXP=world`'s analysis of this fleet's archive is byte-identical to the script's before the change
(`tests/test_gpu_world.py` F11).

**`WORLD_FEEDBACK` stayed `True` pending the GPU experiment in `sweep_world.sh`** (history, as written before the run) (5 seeds per arm,
paired by seed, mean of loss_curve differences over the last half; flip the default if the gain is
within noise). The command is `SEEDS="0 1 2 3 4" ONLY=shipped,feedback_off bash sweep_world.sh`, and
the number is the summary's `Q-WORLD-10: shipped - feedback_off` block: per seed, the mean over the
last half of the flushes of the per-flush loss difference (from `run.py --loss-curve`), then mean ±
SE and the count of seeds where shipped is lower. The script's arm table is **not** this statistic —
it is an unpaired tail mean of progress lines against the first baseline arm it ran — and until
2026-09-24 it was the only thing the script printed.

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

**Why now rather than "when the surface opens": the surface is open.** Most of the entry points are
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
memory_pressure, signature, shift_at=None)`. Made **now** because most of the entry points are stubs
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

### Q-CKPT-2 — what does the SAVE side write for the geometry gate, and who emits FAB's sidecar? — **FIRST HALF RESOLVED 2026-08-30; RESIDUE (1) RESOLVED 2026-09-22 — BOTH SIDECARS HAD A PRODUCER ALL ALONG. (2) RULED 2026-09-27: THE ROW-LEVEL REFUSAL STAYS, AND IS TESTED.**

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

**The residue:**

1. ~~**The two sidecars have no producer.**~~ — **RESOLVED 2026-09-22, AND THE QUESTION WAS ASKED
   IN THE WRONG DIRECTION.** `_sidecar` read `Snapshot.geometry[PREFIX]`, a nested key a flat
   prefixed manifest can never have, so SIG's refusal (`width_units`, `alphabet_size`, `space`, `d`,
   `mode`) and FAB's (`slots`, `rank`, `dk`, `signature_dim`) were disarmed on every resume. But the
   producer was never missing: **each package writes a `sidecar` key into its own payload slice**,
   and this document's SIG section has described that in prose since the record was specified. Read
   off a real checkpoint, `payload['SIG']['sidecar']` carries all five of SIG's fields and
   `payload['FAB']['sidecar']` all four of FAB's, against three in the manifest's `sig.*`. So the
   manifest does **not** subsume them and the two `sidecar` parameters stay: `width_units` cannot be
   in the manifest at all, because `derive.signature_width_bytes` reads a **measured**
   `bytes_per_token`. No frozen signature moved. The sentence above that `FAB.state_dict` "does not
   even claim to emit a sidecar" was true of an earlier tree; it emits one.
   **What re-arming it caught immediately:** a resume resolving `width_units` 197 against a recorded
   192, which every resume before it had accepted in silence. This entry first blamed that on
   pairing an early blob with the final vocabulary file; **the attribution was wrong** (corrected
   2026-09-23). The cause was the replay arm of `build_vocabulary` **re-measuring `bytes_per_token`**
   on a vocabulary grown by the parent's online mints, so any checkpoint written after the first
   mint burst — paired with its own vocabulary file — resolved a different width (192 recorded, 194
   resolved on a default parent at 210 windows). Repaired under **Q-TOK-13**: the replay adopts the
   value the file recorded.
2. **WORLD's grown population count is the one quantity that genuinely needs a live object**, so it
   cannot join the manifest — `_geometry_manifest` is computed before any package is built, which is
   the point of it. It is re-refused by `WORLD.load_into` (M43) at its own row, and whether that is
   sufficient is the remaining question.
   **RULED 2026-09-27 (register CONTRACT-Q-CKPT-2-R2, Proposal 05 §8 1.6): it is.** No gate check
   is added — the manifest is computed before any build, by design. Under Q-WORLD-8 (b) the
   allocated population is `WORLD_NMAX` and `world.nmax` is `EXACT` at the gate, so a lever-driven
   mismatch is refused **first by the gate**, by name (`WORLD_NMAX: the checkpoint was written at
   world.nmax=6 and this run resolves 4` — or 8). M43 is the backstop for a blob whose population
   disagrees with its own recorded extent, and nothing in `tests/` drove it until
   `tests/test_world.py` W4: a 6-predictor blob into `WORLD.load_into` at `WORLD_NMAX=4` and 8 is
   refused (`WORLD_NMAX: ...` and `WORLD_N0/WORLD_NMAX: ...`) with no live tensor moved; through
   `compose`, both lever directions are refused at the gate; a snapshot whose WORLD tensors are cut
   to 4 rows or padded to 8 (its recorded `world.n` edited to match) passes the gate and is refused
   by M43 before any System returns; and afterwards the parent's files hash identically, nothing new
   is on disk and no child `CKPT_DIR` exists. No source changed.

**For the owner:** (1) needed no decision in the end — the tree answered it, and nothing frozen
moved. (2) is ruled (register CONTRACT-Q-CKPT-2-R2): the grown counts stay checked at the row, and
the row is now tested.

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

### Q-EVAL-11 — `CurveReading.step` and `verification_fit`'s Gate read values the frozen signatures lack a channel for — **RESOLVED 2026-09-04: BOTH SIGNATURES WIDEN, AND EVAL STILL RECEIVES NO WIRES**
`eval/api.py::<module>` recorded two declared outputs that the functions declaring them could not
produce, found 2026-09-03 and **referred twice** because closing either needs this document and the
tree changed together and no agent owned both:

* **`CurveReading.step`.** `curve_probe(ev, *, units_by_domain, logits_fn, rng)` returns a
  `CurveReading` whose declared fields include `step` — RUN's window counter, which is what makes a
  curve a curve and what `CKPT.Retention.consider` orders one reading against another by. No
  argument carried it, EVAL owns no clock, and `units_by_domain` carries material rather than
  position.
* **`verification_fit`'s Gate.** Its `DID IT FIRE` declares a Gate on `verify != "off"` — `MEM`'s
  lever — *"rendered from the value the composition root passed"*, against
  `verification_fit(ev, *, store_copy, rng)`, which had no such parameter. Re-checked against
  `memory/api.py::Store` on 2026-09-04: its `__slots__` are the entry arrays, the block partition
  and the census, with **no** `verify` field, so `store_copy` cannot carry it either, and reading
  MEM's `Config` inside EVAL is what `owned_by` refuses.

**RULING: `curve_probe(ev, *, units_by_domain, logits_fn, step, rng)` and
`verification_fit(ev, *, store_copy, verify_mode, rng)`.** Both values arrive as **arguments the
composition root passes**, both signature lines move here and in `src/eval/api.py` in the same edit,
and `K1` stays green in both directions.

**The alternatives, and what separates them.**
*(a) Widen the signature — taken.* Costs one `def` line, one line in §7, and one row in the order
tables when P5/P6 land them. *(b) Spend a wire.* **It was never available for `step`:** a
`Coupling.compute` receives only frozen `Config`s and a `Config` freezes when `build()` returns, so
a per-window counter is refused on exactly the ground **§0's "Candidates examined and refused as
wires" table** already refuses `d_curve_bpb` and `d_shift_at` on — that table's preamble states
this ground verbatim, and both rows are there for it (`d_curve_bpb` is a held-out **measurement**
produced thousands of windows into the run; `d_shift_at` is an optimizer step index, runtime state).
***This sentence cited `NOT_WIRES` until 2026-09-04 and that was false in both directions.***
`spine/assemble.py::NOT_WIRES` holds **seven** rows — `RUN.seed`, `RUN.epochs → OPT.d_lr_horizon`,
`SIG.d_signature_width_bytes`, `EVAL.gist`, the run length in windows, `MEM.cap`,
`FAB.manage_every → WORLD.d_manage_period_windows` — and neither candidate is among them. The two
tables are genuinely different and **this document already draws the distinction the sentence
erased**: §0's own rows mark which of *their* entries are additionally in `NOT_WIRES`
(*"already refused in `assemble.NOT_WIRES`"*, *"`d_seed` is refused by name in `NOT_WIRES`"*), which
would be noise if membership were universal. **The ruling does not rest on the citation and is not
weakened by correcting it:** the ground is a property of `Coupling.compute`, held down by
`tests/test_couplings.py`'s C2 (*"every reach past the declared sources is REFUSED at
construction"*), not by which table records it. Only the *place* was wrong. No check catches this
class — `tests/test_ownership.py::check_o12_citations_name_symbols` checks citation **form** and
says in its own docstring that a citation *"naming a symbol that exists and is the wrong one"* is
beyond it. Corrected in all three sites that carried it: here, `src/eval/api.py::<module>` and
`src/eval/api.py::curve_probe`. For `verify_mode` a wire **was** mechanically available — `MEM.verify` is a frozen
lever — and it lost on its merits: **EVAL declares no wires and receives none**, which is a design
statement (*"everything that measures the run and nothing that changes it"*) rather than an
accident, and a value consumed to render a **Gate** never reaches a mechanism. The precedent runs
the same way: the root already passes another package's frozen lever as a named argument —
`MEM.open_store(vocab_slots=LM.vocab_slots, lm_kind=LM.arch)`,
`DOM.open_partition(sig_dim=SIG.d, …)`. *(c) Recover the mode from `store_copy`* — refused: the
field does not exist, and inferring it from whether `Store.recon` or `Store.selfcon` holds values
reads a **configuration off the data**, which is the shape the instrument line exists to refuse.
*(d) Mint an `EVAL_VERIFY_MODE` lever* — refused: it would be a second declaration of `MEM.verify`,
and a run with `MEM_VERIFY=off` and `EVAL_VERIFY_MODE=selfcon` would print a Gate that lies. That is
the L1 shape this whole spine removes. *(e) Delete the field and the Gate* — refused, and it is the
one option that is not on the table: it trades a recorded gap for a silently missing reading.

**Price, stated because the earlier brief got it wrong.** The wire ledger stands at **19 of 25**
budgeted, so **six edges remain** — the *"two left"* counted declared couplings as wires, which they
are not; four of the twenty-three are intra-package, and an intra-package coupling books no edge,
which is exactly the four the two numbers differ by. **Nothing here spends one.**

***That correction named `eval/api.py` as the carrier when there were five, and the count of
carriers is the part that matters*** — a miscount surviving in four more files is the same miscount.
Found 2026-09-04; all five are corrected — the fifth landed last, by that file's owner, and is
dated in the table:

| carrier | what it said | status |
|---|---|---|
| `src/eval/api.py::<module>` | *"two left"* | corrected 2026-09-04 (the original find) |
| `src/capacity/levers.py::CAPLevers` | *"has room for two more edges in total — so acting on the sentence would fail at `build()` with an over-budget refusal"* | **corrected 2026-09-04.** Both halves were wrong: adding the four couplings it discusses takes the ledger 19 → 23 of the 25 and `build()` does **not** refuse it |
| `src/eval/levers.py::<module>` | *"`WIRE_BUDGET` leaves room for two more edges in the whole tree"* | **corrected 2026-09-04 by that file's owner**, after being filed here as residue. It now reads *"so SIX edges remain in the whole tree"* and carries its own note — *"an earlier revision of this sentence said 'two more edges'; that was a miscount and it travelled — do not propagate it"*. **This row said "still standing" until 2026-09-04**, which was true when written and false by the time anyone read it: a status is a copy of a fact and rots exactly the way a count does |
| §Q-WORLD-6 point 4, this document | *"This would spend one of the last lines"* | the numbers beside it are right against the live ledger — **19 of 25** wires and **23 couplings** — so it is the **rhetoric** alone that implied near-exhaustion; corrected and dated below. *(Stated in the present tense here on purpose: as a past-tense aside these two numbers were `K13`-skipped, and inserting the row below this one moved them out of the window in which `K13` recognised them at all — a claim that stops being read is the failure this table is about, one level down.)* |
| `src/spine/assemble.py` — the `WORLD.d_manage_period_windows` `NOT_WIRES` row | *"It would also spend one of the last coupling lines on a `WORLD.manage` that is itself deferred today"* | **corrected 2026-09-04 by that file's owner — in the *same commit* that added this row**, so the status recorded here was false in the commit that wrote it and there is no tree a reader could have checked out in which it was true. It now reads *"It would also spend one of the six cross-package edges that remain on a `WORLD.manage` that is itself deferred today"*, and `tools/render_wiring.py` has carried that correction into `docs/03_WIRING.md`. This was the one carrier of the five that is **auto-rendered**, so the miscount was being *published* rather than merely written — and so is the repair. The sentence was rewritten once more the same day to put its four live figures in the shapes `K13` can read, two of them having been spelled as words. The row above says a status is a copy of a fact and rots exactly the way a count does; this row is that sentence proved on itself |

**Why this is not bookkeeping.** A budget number that is wrong in the **scarce** direction does not
merely misinform — it silently biases every choice that weighs a wire against a widened signature,
and it biases it **toward the signature**, the option nobody has to justify at `build()`. *This
paragraph gave a different reason until 2026-09-04, and the reason was unsupported and backwards:*
it read ***"at least two agents declined to widen a signature partly because they believed the wire
alternative was nearly exhausted."*** Nothing in `src/`, `docs/`, `tools/` or `.rework/` records any
agent taking that decision — the only two occurrences of the sentence were this one and its copy in
`src/capacity/levers.py::CAPLevers` — and a budget believed nearly exhausted is an argument **for**
widening a signature and against spending a wire, so it cannot be why one was declined. It also
contradicted the next clause of its own sentence. **The bias is recorded in the sentences themselves
rather than in anybody's stated motive**, which is what the table above is for: `capacity/levers.py`
told a porter that four couplings which *already exist* would be refused at `build()`; §Q-WORLD-6
point 4 called a legal row *"one of the last lines"*; `src/eval/levers.py` told a reader that only
two edges were left in the whole tree; and `src/spine/assemble.py`'s `NOT_WIRES` row argued
against a row on its price. Four of the five carriers argued **against a wire because of what it
costs**, and the cost was wrong by a factor of three. Both verbs are past because none of the five
says it now — all five carry the live figure, the last of them since 2026-09-04.
`tests/test_couplings.py`'s C4 and `spine/assemble.py::render` print the live figures; **any prose
copy is one that can go stale in silence**, which is the rule §0 already states about these same four
numbers and which five files broke anyway. The count is not searched for by `K13` — its own output
says *"NOT SEARCHED FOR: a number written in words"*, and *"two"* is a word in every carrier.

**Why this is a second reopening of EVAL's surface, and why it is not the one Q-MEM-10 refused.**
`Q-EVAL-10` closed by saying `Q-MEM-10`'s ruling *"deliberately left room for exactly one, and this
is it"*. What `Q-MEM-10` refused is **option (c) of that question** — adding `blend_fn` to four
scoring entry points, which puts `softmax → blend → log` inside four instrument bodies (C8/C9
rebuilt in the instrument line). Neither parameter here is a scoring hook: `step` is a stamp and
`verify_mode` is a Gate input, `logits_fn` is untouched on every EVAL signature, and no body gains
arithmetic. `Q-MEM-10`'s ruling holds in both directions and is not reopened.

**What would change the answer.** If `RUN` ever hands instruments a `RunClock` rather than a bare
index, `step` should ride on that record instead of as a scalar — one object, not one argument per
field. And if a **second** EVAL entry point turns out to need `MEM.verify`, the argument stops being
cheaper than the wire: two call sites passing one frozen lever is the shape the nine promotions in
§0 were made from, and `EVAL.d_verify_mode` should then be declared against the six remaining edges.

**What did NOT change.** No lever moved, no default moved, no census row, no wire, no record type.
`LEVERS READ` is unchanged on both functions (`windows`; `verify_fit_steps`). Both stay **deferred** —
`units_by_domain` and `logits_fn` still have no producer, and neither does the `store_copy`.

**Residue owed outside this edit, and the check it holds down.** `K12` computes "produced" from the
order tables' prose, and a deferred entry point has no row, so it reads `verify_mode` as a second
argument with no producer and requires the deferral reason to name it. The reason lives in
`spine/compose.py`, which this edit does not own. **`DEFERRED_ENTRY_POINTS["EVAL.verification_fit"]`
must gain a clause naming `verify_mode` and saying it is *not* a gap** — the root reads it off MEM's
frozen `Config`, the way `MEM.open_store`'s row already spells `vocab_slots=LM.vocab_slots` — and
`K12` fails on that one entry until it lands. `step` needs no such clause: `K12` already counts it
as produced.

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

### Q-RUN-8 — a mid-epoch retok needs `windows_in_epoch` revised with the epoch cursor kept — **RESOLVED 2026-09-26: (a), BUILT AS 03b STAGE S0b. The mid-epoch act (LOOP_ORDER stage X) performs the retok after the flush that raised it; `RunClock.revise_epoch_length` keeps the cursor; a mid-epoch resume continues (Q-RUN-16). The text below, to the next heading, is the question as it stood, kept as history**

**THE RULING (2026-09-26).** The owner: *"Stream rebuilding sounds important. I think it's a good way
for the llm to learn"*, and, of 03b, *"I don't want anything frozen or fixed unless absolutely
necessary."* The act runs right after the flush whose `TOK.on_window` Due asked for it, with the
batch empty: `TOK.splice` keeps every unit up to and including the one under the cursor and
re-segments the rest at the vocabulary as it now stands; `RunClock.revise_epoch_length` takes the new
length with the cursor kept (at `n == in_epoch` the next advance rolls without counting a window);
`OPT.revise_horizon` re-maps the rest of the schedule LR-continuously (Q-OPT-10); `DOM.on_retokenize`
is told when the view moved; MEM hears `resegment=` on the next flush; the shift is stamped. A request
whose view (`TOK.view_of`) has not moved is refused as a no-op (`tok.retok_noop`, `loop.acts_noop`) --
the archive's 2.189 b/B case had 22 of 23 retoks adding zero tokens. `tok.retok_deferred` and
`tok.retok_satisfied_by_roll` are gone: nothing is deferred. **The measurement below is superseded by
the ship-rule measurement 03b §13 S0b names** (prequential bits/byte, `TOK_RETOK_EVERY` {0, 3000, 1000},
3 paired seeds, non-inferiority against a nuisance-seed control; that rule is now O14's choice read by
the ε rule per phase, 2026-09-27, below); until it runs, `TOK_RETOK_EVERY`
keeps its shipped 3000 and runs past window 3000 change. Driven: `tests/test_continuation.py` S4.

**2026-09-27 (register PENDING-GPU-RETOK-FLEET, note retok fleet (1); Proposal 05 §8 1.5): THE
SHIP-RULE FLEET KEEPS ITS CHECKPOINTS, AND A PERIODIC SAVE CHANGES NO NUMBER.** `EXP=retok bash
gpu_world.sh` gives every run `CKPT_DIR=$OUT/ckpt/<arm>.s<seed>` (the script's `KEEP_CKPT`, on at
`EXP=retok` and off elsewhere, so `EXP=world`'s command lines are the ones it ran before). The act
arms save once, at the end (`CKPT_EVERY=0`); k0, k0_nuis and k0_rerun save every `KEEP_EVERY`
windows, by default the gcd of the act cadences (1000); and k0's saves are hard-linked aside as
`$OUT/ckpt/keep/k0.s<seed>.w<step>`, with the vocabulary beside each as `<that base>.dyntok.json`,
because CKPT's ring keeps only `ckpt.pt` and `.prev` (`ckpt/api.py::save`). That is the layout
`derive.checkpoint_base` resolves, so `CKPT_RESUME=<keep>/k0.s0.w3001` resumes directly (into a new
`CKPT_DIR`, with the run's own `RUN_SEED`, `RUN_DEVICE` and `DATA_STREAM_BYTES`: corrected 2026-09-27,
below). A generation is taken once its vocabulary is no older than its checkpoint -- the root
writes the vocabulary only after `CKPT.save` returned True (§3 stage `C`) -- and each copy is named
for the step read off the file and checked coherent, its TOK merge count against its vocabulary's
entries. A periodic save of period P lands at window iP+1 and an act of cadence K at jK+1, so at
P = 1000 every k1000 act window, and every k3000 one, has a k0 model of the same maturity: the
offline control note retok fleet (4) sets each act's spike against. **Known answer: the saves are
invisible to the run.** S4's two runs (`TOK_GROW_EVERY=30`, `TOK_RETOK_EVERY` 40 and 0, 130 windows,
no save), rebuilt with `CKPT_EVERY=40`, reproduce their loss curves exactly and act at the same
windows, and the ring's older generation is the periodic save at window 121 -- the last act's window
-- beside its own vocabulary. So arm − k0 pairs a saving control with arms that save only at the end
without bias, and M and the run-to-run check compare like with like as well (k0_nuis and k0_rerun
save at k0's cadence): both remedies note retok fleet (1) offered. Driven:
`tests/test_continuation.py` S11. On CPU (`WINDOWS=200`, `EXTRA="TOK_GROW_EVERY=30"`,
`RETOK_ARMS='40 20'`, operation only; corrected 2026-09-27, below: the `WINDOWS=80` run first recorded
here fired no act) k40 acted at windows 121 and 161 and k20 at 101, 121, 161 and 181; k0 kept w21 to
w181, all nine coherent, their merge counts rising from 256 to 273, covering k40's acts 2/2 and k20's
4/4; and a resume from w121 into a new directory, by the block's resume line, reproduced k0's own
losses for windows 122-131 exactly. The verdict, the rates, the secondaries and the kept copies come
back as the script's paste-back block, and `tests/test_gpu_world.py` holds the analysis, the block and
the archive to known answers on synthetic fleets.
**CORRECTED 2026-09-27 (build 1.5's review) — a fleet launched into a used OUT keeps its own copies,
the CPU record above is one where acts fire, and the resume line carries the run's seed, device and
stream.** (i) *A reused OUT.* A launch truncated `SUMMARY.txt` and left the rest of the previous fleet
where it was, and the index dropped a save as "a duplicate step" whenever its `k0.s<seed>.w<step>`
name was taken. The default `gpu_retok_out` is reused between fleets (a `WINDOWS=5000` look before the
full fleet; C12's re-run of the k0 vs chosen-cadence pair after Levels), so a second fleet deleted its
own save at every step the first had kept, and the first fleet's read-only copy stayed under the
name, trained on another stream and perhaps at another commit. KEPT.txt and the block called those
copies coherent and counted them against the new fleet's act windows: the spike test's
maturity-matched control was replaced without a word. The watcher also took the old ring's final
`ckpt.pt` as a save of the new run, and the analysis read the logs of seeds or arms the new fleet did
not run as its own. Driven by the review: `WINDOWS=80` and then `WINDOWS=100` (streams of 15120 and
18900 bytes) into one OUT left the first fleet's w21, w41 and w61 in place, inodes and mtimes
unchanged, and one new copy. **Ruling: a launch never writes into a previous fleet.** One found in OUT
(`SUMMARY.txt`, `logs/` or `ckpt/`) is moved aside whole, beside it, as `<OUT>.<its launch stamp>`.
Nothing is deleted, and `OUT=<that name> bash gpu_world.sh --analyze` still reads it. OUT's own
directory moves, so a symlinked OUT keeps its link and its disk; an OUT that is the checkout or holds
it is refused. Each keep directory is stamped with its launch (`.fleet`), and `keep_index` refuses one
stamped by another launch: it indexes nothing and drops nothing there, and the block prints INDEX
REFUSED. A repeated step is dropped as a duplicate only within one launch; a keep directory with no
stamp (a fleet launched at 5560342) is indexed as before. On CPU at this commit, `WINDOWS=80` and then
`WINDOWS=200` into one OUT: the first fleet moved aside with its three copies' inodes and mtimes
unchanged, and the second kept its own nine, none dropped. (ii) *The CPU record fired no act.* At
`WINDOWS=80`, `RETOK_ARMS='40 20'`, k40 read `acts 0 noop 1` and k20 `acts 0 noop 3`: each Due was
refused as a no-op, because nothing had been minted yet (minting starts near window 120-200). The
analysis printed NO ACT FIRED for both and DECISION: UNDECIDED, k0's copies covered 0/0 act windows,
and every copy held 256 merges, so the coherence check compared nothing that could differ. The
"k40's one act and k20's three" first written above were those no-op acts. Reproduced at this commit.
The record above is now `WINDOWS=200` with `TOK_GROW_EVERY=30`, the size the review found to act,
driven here. (iii) *The resume line.* `run_job` sets `RUN_SEED`, `RUN_DEVICE` and
`DATA_STREAM_BYTES` on every run and EXTRA carries none of them, so the resume the script printed
(`CKPT_RESUME=... CKPT_DIR=... TOK_RETOK_EVERY=0` plus EXTRA) was refused when followed literally:
from w121 of the 200-window fleet, "the segmentation rebuilt from the checkpoint's log holds 635
windows, and the parent's epoch held 199". The block's "resume one" line and the script's header now
carry `OMP_NUM_THREADS=1 RUN_SEED=<seed> RUN_DEVICE=<device> DATA_STREAM_BYTES=<the fleet's>` and
EXTRA, and that line is the one that reproduced windows 122-131 above. (iv) *"Not in this tree."* The
secondaries named every §8 1.3 key no log printed as missing from the tree, but under DID IT FIRE an
ABSENT key is unreachable: `tok.bpt_tail` is written only when an act splices, and
`fab.blackout_windows` is seeded only at a stamp and at `FAB_COOLDOWN` > 0. The `WINDOWS=80` fleet,
on a tree that holds both, printed "absent (§8 1.3 not in this tree): tok.bpt_tail". The launch now
records in `SUMMARY.txt` which of the four the tree's Python names and whether `run.py` has
`--flush-bytes`; a key the tree lacks is "not in this tree", and one it has that no log printed is
"unreachable in these runs", with the reason its seeding gives. A `SUMMARY.txt` without the record
says it cannot tell the two apart. Where the tree has `fab.blackout_windows`, a run with
`fab.shift_notifications` 0 reads 0 windows blacked out even when no run in the fleet was stamped.
(v) *The act's cost.* Every k0-family run saves every `KEEP_EVERY` windows inside its loop time and
the act arms only after it, so no arm of the fleet is the plain-text rate, and an act arm's per-byte
time against k0 is mostly k0's saves: k40 read -19.6% at 200 windows while its acts and their MEM
re-cuts took 0.15% of its loop time. The act lines now carry that share, `loop.act_seconds` +
`loop.act_remap_seconds` over the arm's own loop time, and the figure against k0 is still printed,
qualified. Register row PENDING-GPU-THROUGHPUT-REBASELINE records that k0's rate includes its saves.
(vi) *The block's cut.* It said rank 0 is never cut, but the per-seed rows were rank 0 and came first,
so past about 60 seeds the truncation from the end took the alarms, then the margin, the verdicts and
the DECISION, while every seed's row survived. The rows are now fitted into the room the rest leaves:
the ones that set M, fail the margin or miss a reading first, then the others in seed order, and one
line counting what was left out. (vii) *The watcher.* Its only exit was the stop file `run_job`
writes after its run, so a `run_job` killed by a signal or the OOM killer left it polling for ever.
It is given `run_job`'s pid, and when that is gone it takes a last look and returns. **Driven:**
`tests/test_gpu_world.py` F2 (60 and 72 seeds: the margin, the verdicts, the DECISION and both alarms
survive, and the rows that set M and fail it are kept), F4 (the tree record, the unreachable line,
the act's share), F7 (the resume line; a keep directory stamped by another launch), F10 (a stand-in
`run.py` that saves as CKPT and TOK do: the tripwire passes, every periodic save is kept beside its
own vocabulary, and a second launch into the same OUT moves the first aside and keeps its own copies),
F12 (`keep_sweep` over staged rings: a checkpoint whose vocabulary has not landed, a vocabulary just
rotated, two missed saves, a save landing between the look and the link) and F13 (a killed
`run_job`'s watcher exits). Run against the script before this correction, F2, F4, F7, F10 and F13
fail and F12 passes: the sweep was right and had no known answer.
**2026-09-27 (Proposal 05 O14 and O2; §8 1.5's owed items): THE RETOK FLEET'S DECISION IS O14's
CHOICE, READ BY THE ε RULE PER PHASE, AND ITS BLACKOUT IS SPLIT WHERE THE POOL FILLS.** `analyze_retok`
read 03b's rule: M = max over seeds |k0 − k0_nuis|, a cadence non-inferior when arm − k0 ≤ M at every
seed, the lower mean among those shipping, and 0 shipping when none was. That rule carries no owner
words, fails a harmless 3000 about 30% of the time at 3 seeds by the register's simulation, and its
"ships 0" branch would end the act the owner approved. **Ruling (O14, read by O2's ε rule).** The
endpoint is prequential bits/byte per phase: the stream's N equal byte ranges of `DATA_STREAM_BYTES`
(`data_plan`'s bounds, N off each log's `data.phase_entered` gate), each flush placed by its run's
cumulative per-flush bytes (`run.py --flush-bytes`), and a phase's value sum(loss × LM_CTX) / ln 2 /
sum(bytes) over its flushes, the whole-run formula restricted to them, so a run's phases average,
byte-weighted, back to its whole-run value. A fleet without the per-flush bytes is read whole-run as one
phase, and the analysis says so. Per cadence and phase, the paired differences arm − k0 give one-sided
t bounds, mean ± t × sd/√n, with the Student-t quantile computed in the script (the regularized
incomplete beta and bisection; the GPU box has no numpy or scipy promised). A cadence **FAILs** if some
phase's lower bound exceeds ε, the t taken at 1 − a/N (Bonferroni over the phases) with Holm's a across
the cadences (the stronger evidence of harm at 0.05/2, the other at 0.05, none after the first that
does not FAIL); it **PASSes** if every phase's one-sided 95% upper bound is at most ε; otherwise, and
always at n < 2, it is **UNRESOLVED**. ε is the script's `EPS`, default 0.05 bits/byte, printed, and
read when the analysis runs, so `--analyze` can read a fleet against another ε. 3000 is the incumbent:
1000 replaces it only if 1000 does not FAIL and (3000 FAILs, or the one-sided 95% upper bound of the
whole-run paired 1000 − 3000 is below 0); otherwise 3000 stays, UNRESOLVED readings included, and an
incumbent that never acted is not read, so it stays. 0 is never shipped by the rule: when every cadence
FAILs the DECISION is ESCALATE (the act stays ON at 3000 until the owner answers; the remedy arms run
next, register O14). M and the per-arm means are printed as "reported, decides nothing (O14)", and the
run-to-run line stays. The block carries each cadence's per-phase means and bounds, its verdict, ε, n,
and the choice with its reason. `RETOK_INCUMBENT` (default 3000) names the incumbent for operation checks
at a shorter shape; `EPS` and `RETOK_INCUMBENT` are the script's own knobs, clear of every package
prefix. **The blackout split (O14, "Holds meanwhile").** The 2026-09-24 archive's pool reached
`FAB_SLOTS` in 20 of 21 runs (median window 6,501), and past that growth is held by the ceiling whatever
the acts do, so an unsplit C13 alarm would blame the acts for the capacity ceiling.
`fab.blackout_windows` is now reported before and after the first progress line with n_live ≥
`FAB_SLOTS` (read off the growth gate's text, else EXTRA, else 4096; a pool that never fills is all
before), each part as a share of its own windows, with n_live at the end per arm, and C13's alarm reads
the part before only (without the counter, an upper bound built from the acts before the fill: the
split's review, below). The counter is cumulative and no log carries a per-window series, so the split is
an estimate built from the act windows: each act blacks out up to `FAB_COOLDOWN` windows from its window
(a later act restarting it, as `grow_check`'s latest stamp does), those windows are counted either side
of the fill, and the counter is split in that proportion; the analysis says so. **Driven:**
`tests/test_gpu_world.py` F14 (the script's own t quantile against t(0.95, 2) = 2.919986, t(0.95, 4) =
2.131847, t(0.975, 2) = 4.302653 and six more), F15 (a harmless cadence PASSes, a harmful one FAILs, a
noisy one and one at n < 2 are UNRESOLVED, one harmful phase is enough to FAIL, Holm's levels and its
stop, on the rule and on synthetic per-phase fleets), F16 (1000 replacing 3000 on each ground, 3000
staying on UNRESOLVED readings and on 1000's FAIL, ESCALATE, UNDECIDED, the whole truth table, and 0
never an answer) and F17 (the split, `FAB_SLOTS` off the gate text, a pool that never fills, and the
alarm on the part before); F1, F2, F4 and F6 now hold the new rule. **On CPU (operation only),**
`EXP=retok DEVICE=cpu WINDOWS=200 SEEDS='0 1' PAR=3 EXTRA='TOK_GROW_EVERY=30 FAB_SLOTS=2100'
RETOK_ARMS='40 20' RETOK_INCUMBENT=40`: 9 runs rc=0, 4 phases off the logs' gate, and each run's
phases averaged back to its whole-run value (k0.s0 6.398962). Phases 1 and 2, before the first act,
read differences of exactly 0 against k0 at both seeds; k40 and k20 read UNRESOLVED at n = 2 (k20's
phase 4: +0.0668, bounds −3.1976 and +0.4715); k20 − k40 over the whole run read +0.0259 with upper
bound +0.2017, so the DECISION was "stays 40". M read 0.15957, reported. The pool reached 2100 by the
first progress line (window 101) in every run, before any act, so every blackout window fell after
it: k40 read 0.0% before and 78.8% after, with no alarm, where its unsplit 38.1% would have sounded one.
At `WINDOWS=300 FAB_SLOTS=2180 KEEP_CKPT=0` the pool filled at window 201, between the acts at 121 and
161 and those at 201-281. k40.s0's 174 blacked-out windows (from the act at 121 to its 295th window,
the estimate's total, equal to the counter in all four act runs) split into 80 before, 39.8% of the 201
windows before the fill, and 94 after, 100% of those after. The alarm sounded on the 39.8%.
**2026-09-27 (Proposal 05 O20, NEW-20; §8 1.5's owed archive reads): A FLEET'S ARCHIVE NOW SAYS HOW
LONG THE POOL SAT AT ITS CEILING AND HOW MANY SLOTS A MANAGE PASS FREED THERE.** Under each run's
counters, `tools/read_fleet_archive.sh` prints one more row. It gives `FAB_SLOTS` (the growth gate's
text, else any `FAB_SLOTS=` in the log, else SUMMARY.txt's EXTRA, else 4096, labelled "assumed") and
the first progress window with n_live ≥ `FAB_SLOTS`. It gives the windows from there to the run's end
(its `=== N windows` line) and their share of the run, and how many of the progress lines from there
on read `FAB_SLOTS`. Slots freed per manage pass are the drops in n_live between consecutive progress
lines whose earlier line is within 2% of `FAB_SLOTS` (median, max and count). Beside them is the whole
run's `fab.merged` + `fab.cull_fail` + `fab.cull_util` over `fab.manage_passes`, each of which frees
one slot. One pooled line follows the rows; arms named `*_rerun` are replicates and are left out of it.
The pooled line notes when passes come closer together than the lines, since a drop can then span
several passes. No log holds a per-pass count, and spawns refill slots between lines 100 windows
apart, so the freed figure is a LOWER BOUND from the sampling, and the block says so. A line one window
after a pass reads that pass's dip, so the line count is a sample, not the time spent at the ceiling. On
the 2026-09-24 archive (`results/gpu_world_2026-09-24/archive_reads.txt`, ARCHIVE_READS.md item 2),
with the replicate left out: the stretch from the fill to the end is 34.0-78.5% of each filling run
(median 68.0%), and 74.5-80.9% of the progress lines in it read 4096. A pass frees a median of at least
27 slots (6-61, 460 passes), as `results/decisions_2026-09-26/revise/o16_dc/churn.out` read it, beside 629-1,199 merges and FAB
culls per run over its 39 passes. **Driven:** `tests/test_gpu_world.py` F5, on a synthetic fleet: the
fill, the share and the lines at the ceiling, with `FAB_SLOTS` read off the gate text and off EXTRA;
the drops near the ceiling, merged + culled, and the pooled line without the replicate, with its note.
**On CPU (operation only),** `EXP=retok DEVICE=cpu WINDOWS=400 SEEDS=0 PAR=4 FILL=0
EXTRA='TOK_GROW_EVERY=30 FAB_SLOTS=2100 FAB_MANAGE_EVERY=200 FAB_GRACE=1' RETOK_ARMS='40 20'
RETOK_INCUMBENT=40` ran 5 runs, all rc=0, and k40 and k20 acted 7 and 9 times. The reader, run on the
packed `.tgz`, took 2100 off the gate text. Every run reached the ceiling by window 101, with 74.0-74.8%
of the run still to go, and its one pass (before the line at window 201) dropped n_live by 432-452. That is 1 below the
counters' exact 433-453 in every run, one spawn between the pass and the line: the bound held, and was
nearly tight.
**2026-09-27 (the split's review; §8 1.5): WITHOUT THE COUNTER, C13 READS A BOUND BUILT FROM THE ACTS
BEFORE THE FILL, AND A FLUSH'S PHASE HAS A KNOWN ANSWER THAT ONLY ITS BYTES GIVE.** Two findings on
1bd51c5. (1) When a log carries no `fab.blackout_windows` (a tree before §8 1.3), C13's alarm reads an
upper bound on the part before the fill, and that bound was every `fab.shift_notifications` × cooldown
over the windows before the fill, so the acts after the fill were charged to the part before. On a
synthetic fleet of 2000 windows whose pool was full at window 101 and whose every act came later (k3000
at 1501; k1000 at 1001, 1501 and 1901; cooldown 400) both arms read 100.0% before and alarmed. The
whole-run bound the split replaced read 20.0% for k3000, with no alarm. **Ruling.** The bound is built
from the acts before the fill: the windows their cooldowns cover ([act, act + cooldown), merged and
clipped at the run's end, the cover the estimate uses) that fall before the fill, over the windows before
it. A stamp no act line places (`fab.shift_notifications` above the act lines, as an epoch roll's
would be) is charged a whole cooldown before the fill. Only a log with no act window falls back to every
notification × cooldown. The split row prints the bound where the part is missing ("no counter: at most
X% by the act windows x cooldown"), the block prints "<= X%", and the alarm names the bound. The fleet
above now reads 0.0% for both, with no alarm. (2) No test placed a flush by its bytes. Every synthetic
run had equal flushes, and there index quarters place flushes as bytes do, so a placement that ignored
the bytes passed. A real act arm's flushes grow after its act. **Driven:** `tests/test_gpu_world.py`
F15 adds an act arm whose flushes grow after its act (15 of 63,000 bytes, then 30 of 94,500). It reads
its known phases, 2.0100, 2.1200, 2.2400 and 2.6000 bits/byte, +0.0100, +0.0200, +0.0400 and +0.3000
against k0, and FAILs by phase 4. F17 adds the review's fleet (0.0%, no alarm) and a second one: acts
before the fill bounded by their cover (800 of 1001 windows, 79.9%), a stamp no act line places (400 of
1001, 40.0%), and the fallback with no act window (3 × 100 of 1001, 30.0%). Run against mutants in a
scratch copy: index quarters in place of the byte placement fail only the new F15 check (its p2 reads
−0.0020); placing by a flush's end fails it, F4's by-phase check and F15's one-harmful-phase fleet; 1bd51c5's script fails both new F17 checks (100.0%,
two alarms). **On CPU (operation only),** `EXP=retok DEVICE=cpu WINDOWS=300 SEEDS='0 1' PAR=4 FILL=0
KEEP_CKPT=0 EXTRA='TOK_GROW_EVERY=30 FAB_SLOTS=2180' RETOK_ARMS='40 20' RETOK_INCUMBENT=40`: 9 runs
rc=0, "stays 40" (both cadences UNRESOLVED at n = 2). The pool filled at window 201 in every run.
k40 acted at 121, 161, 201, 241 and 281 and k20 at 121, 161, 181, 221, 241 and 281, and
`fab.shift_notifications` equalled the act lines in all four act runs. The no-op acts (`loop.acts_noop`
2 and 8) printed no line and stamped nothing. With the counter both arms read 39.8% before and 100% after,
and the alarm sounded on the 39.8%. With `fab.blackout_windows` removed from copies of the logs and from
the tree record, the bound read 39.8% for both arms (80 of 201 windows, [121, 201)), equal to the
estimate, and the alarm sounded on it, labelled an upper bound; 1bd51c5's script read 100.0% there. At
`WINDOWS=200 FAB_SLOTS=2100` (9 runs rc=0) the pool was full at window 101, before every act (k40 at
121 and 161; k20 at 101, 121, 161 and 181). With the counter both arms read 0.0% before, with no alarm.
Without it the bound read 0.0% and nothing sounded, where 1bd51c5's script read 100.0% and alarmed both.
The act arms' flushes grow after their first act: k40.s0's mean flush was 189.0 bytes over windows
1-120 and 193.5 after, k0.s0's 189.0 and 189.4.
**2026-09-27 (O20's review; §8 1.5): THE ARCHIVE READER'S 2% BAND, THE ORDER IT READS `FAB_SLOTS` IN
AND ITS LINE COUNT ARE HELD.** Three findings on 5bffd3f. (1) No test held the band on the drops. Every
synthetic drop started inside it, so a reader counting every drop in `n_live` passed F5. On the
2026-09-24 archive that reader reads a median of 26 slots per pass (1-80, 567 drops) where the band
reads 27 (6-61, 460). (2) No test held the order `FAB_SLOTS` is read in. The synthetic gate text and
EXTRA both said 3000, and no log read the assumed 4096. (3) The block grew by 24 lines on the 21-run
archive, not one per run, because the '-- per run' header had become three lines. **Ruling.** The
arithmetic is unchanged. The row's legend moves into the '-- per run' header line, and the LOWER BOUND
caveat and "the rest read a pass's dip" move into the pooled line. The reads now add one row per run
and the pooled line: `archive_reads.txt` is 78 lines (56 before O20, 80 at 5bffd3f), and every number
in it stands. **Driven:** F5's synthetic fleet has EXTRA `FAB_SLOTS=3500`. k0 reads 3000 off its gate
text over a stray `FAB_SLOTS=3200` above it. k3000 has no gate text and reads the stray 3200, k1000
reads EXTRA's 3500, and a fleet with an empty EXTRA reads "4096 (assumed)". k0's passes are every 500
windows, and its dips sit on the lines one window after them (1001, 1501, 2001). Its dip from 2500 to
2400 at 501, before the fill, is not counted. k1000's drop of 29 from 3429 is outside 3500's band and
its drop of 30 from 3430 inside. A check holds the block to one row per run and the pooled line (20
lines for 4 logs, 15 before O20). In a scratch copy F5 fails each of these mutants: every drop counted;
the band's edge exclusive, or 3% wide; EXTRA read first with the gate text dropped (the review's); the
gate text dropped; the log's `FAB_SLOTS=` skipped; "(assumed)" dropped; one more legend line.
**On CPU (operation only),** from a scratch clone: `EXP=retok DEVICE=cpu WINDOWS=600 SEEDS=0 PAR=4
FILL=0 KEEP_CKPT=0 EXTRA='TOK_GROW_EVERY=30 FAB_SLOTS=2100 FAB_MANAGE_EVERY=200 FAB_GRACE=1'
RETOK_ARMS='40 20' RETOK_INCUMBENT=40` ran 5 runs, all rc=0. k40 and k20 acted 12 and 16 times (2 and
12 of them no-ops), and the DECISION read "stays 40". Each run made two passes, at windows 200 and 400.
The reader, run on the packed `.tgz`, took 2100 off the gate text. k0, k0_rerun, k40 and k20 were full
at window 101, and k0_nuis peaked there at 2093, inside the band (2058 and up). The first pass's drop
(299-363) is counted. The second pass's dip (166-391) starts at 1827-1898, below the band, and is not.
Each row reads one drop, and the pooled line reads a median of 309 (299-363, 4 drops). Both dips
together stay within each run's merged + culled (k0: 363 + 259 = 622 of 710), so the bound held. With
the band dropped the same archive reads 8 drops, median 301 (166-391).

**THE QUESTION AS IT STOOD.**

`TOK.on_window` raises `Due.retok` on its own `retok_every` cadence, and the act it asks for is to
re-segment the stream with the vocabulary as it now stands — which is the only route by which an id
the run minted can appear in the run's own training data. `spine/loop.py` cannot perform it
mid-epoch, and the reason is one line in `RunClock`:

```
rolled = self._in_epoch >= self.windows_in_epoch
```

Re-segmenting changes how many **windows** the epoch holds, so `windows_in_epoch` must be revised.
The only public way to set it is `begin_epoch`, and `begin_epoch` **zeroes `_in_epoch`** — *"the only
quantity a roll may zero"*, in its own words. Calling it mid-epoch therefore restarts the epoch and
re-trains on material already consumed. The archive did the other half (*"refresh the token stream
with the grown vocab; remap position by byte"*, `self_organize.py:702`) and the byte remap is
writable in the loop today; what is not writable is **a new length with the position kept**.

**What the loop does instead, and what it costs.** Each fire adds one to `System.retok_pending` (a
count since 2026-09-24; it was a flag, so four fires read as one); the next epoch roll re-segments
and adds the count to `tok.retok_satisfied_by_roll`. A retok that no roll ever reaches is counted, one
per fire, in `tok.due_dropped` — the counter Q-TOK-12 says must read 0 from flush discards — with a
warning naming why, so `retok_satisfied_by_roll + (due_dropped's retok share) == tok.retok_deferred`
on a fresh run (driven: `TOK_RETOK_EVERY=10 RUN_EPOCHS=2 DATA_RESAMPLE=1`, 21 + 20 = 41). **At `RUN_EPOCHS=1` that is every retok the run raises**, because the single roll a
one-epoch run takes is the one that also finishes it and `Tick` requires `finished` to be tested
first. At `TOK_RETOK_EVERY=3000` over a 262,601-window run that is ~87 deferred fires, all of them
lost.

**Options.** (a) `RunClock.revise_epoch_length(n)` — a new entry point, the frozen set grows by one;
the loop remaps by byte and the clock keeps its cursor. (b) `begin_epoch(n, at=None)` — a defaulted
keyword, so no caller breaks, but it makes one entry point mean two things and a defaulted argument
is invisible to K10. (c) Leave it deferred to the roll and document that a single-epoch run cannot
retok — cheapest, and it makes `TOK_RETOK_EVERY` set-but-inert at the shipped `RUN_EPOCHS = 1`,
which is the defect class this document exists to refuse.

**Recommendation: (a).** It is the only one that names what is actually happening — the epoch's
length was re-measured, the run did not restart — and `(c)` leaves a shipped lever that cannot fire
at the shipped configuration. **It is MEASURABLE before it is decided**: run two epochs with
`DATA_RESAMPLE=1` and compare `tok.retok_satisfied_by_roll` against `tok.retok_deferred`; if a roll
reaches every fire at realistic epoch lengths, (c) is adequate and (a) is not worth a signature.

**Measured 2026-09-24: `TOK_RETOK_EVERY` decides nothing today at ANY `RUN_EPOCHS`, not only at 1.**
The roll re-segments at the current vocabulary whether or not a retok is pending, so the lever's
value moves only counters: `RUN_EPOCHS=2 DATA_RESAMPLE=1 DATA_STREAM_BYTES=40000` gave a bit-identical
418-flush loss curve at `TOK_RETOK_EVERY=0` and `=10` (sum 2243.0572724342346 both, re-driven on the
tree after Q-DOM-3's rekey reorder; 2243.0572657585144 on the commit before it), and `0` does not
mean what its help says ("leaves already-emitted ids alone forever"). Making `0` real needs the roll
to segment at a vocabulary that excludes what was minted since the last segmentation, and making a
positive value real needs (a) — both are this question, left for the owner.

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
the same key; **unreachable at `batch_windows = 1`**, so since 2026-09-24 the root seeds it at the
second window of a batch rather than `TOK.on_window` seeding it on every arm — Q-TOK-14) and
`tok.due_dropped`, whose flush-discard share is **0 by construction** under (b); its other share is
Q-RUN-8's retoks that no roll reached, one per fire. A counter that must read zero is how a later reader can tell which reading
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
over `src/` returned exactly the count declared in §7's ```contract block (the count lives in §7), all
distinct. Per package: CAP 7, CKPT 11, DATA 5, DOM 10, EVAL 9, FAB 11, **LM 12**, MEM 10, OPT 8,
RUN 16, SIG 10, TOK 9, **WORLD 9** (RUN's two since 2026-09-24 are `Cadences.state` and
`Cadences.restore`, Q-RUN-9; OPT's eighth, the same day, is `remap_rows`, Q-FAB-13); on 2026-09-26 03b S0b made it OPT 9, RUN 17 and TOK 11 with `revise_horizon`, `RunClock.revise_epoch_length`, `splice` and `view_of`). LM's twelve are `anchor_term`, `build_model`, `counters`, `decode`,
**`embed`**, `encode`, `lm_loss`, `load_state`, `on_mint`, **`residual_ratios`**, `resolve`,
`state_dict` — the two additions are both present and both in §7, so 121 + 2 = 123 is the arithmetic
and the tree agrees with it in both directions.

### Q-TOK-13 — a resume re-measured `bytes_per_token`, restarted the pair tally from zero, and wrote its reconciliation keys under other names — **RESOLVED 2026-09-23: THE FILE'S RECORDED MEASUREMENT WINS ON A RESUME; THE TALLY TRAVELS EXACTLY; ONE SPELLING FOR THE KEYS. NO SIGNATURE MOVES, NO FORMAT BREAKS**
Three persistence defects in TOK, one ruling each, all driven.

**(1) The width.** `build_vocabulary`'s replay arm measured `bytes_per_token` again on the replayed
vocabulary, which carries every token the parent minted online. `_signature_width` turned the new
value into a new `width_units` and `SIG.load_state_dict` refused: a default parent at 210 windows
(6 minted at window 201) recorded 1.50266 / width 192, the resume measured 1.51876 / 194, and every
default run longer than 200 windows could not be resumed. **Ruling: the value the vocabulary file
recorded wins** (`save_vocabulary` has always written it, so every checkpoint already on disk is
resumable with no format change), and `DATA.data_plan` receives the same recorded value because it
reads the same field. `derive.signature_width_bytes` already says the width is *"FIXED FOR THE
LIFETIME OF THE RUN"*, and a resume is the same run. **The measurement still runs**, on the parent's
BUILD-TIME vocabulary (ids at or above the file's `v0` masked for that one call): it is the fallback
for a file that predates the field (`tok.bpt_adopted` 0) and the reconciliation when it does not
(`tok.bpt_mismatch`, present only at `TOK_DROPOUT=0`, where it is exact — measured 0 on the default
resume, 1 at `TOK_BUILD_BYTES=20000`, 1.50384 against 1.50266). **A mismatch is reported, not
refused**: a different corpus across a resume is a legitimate continual-learning experiment, and
the width is a fact about the run the centroids were measured in. **Rejected:** taking `width_units`
from SIG's sidecar (the plan would still get the re-measured value, and SIG's width refusal would
compare the sidecar against itself); carrying the value only in `payload['TOK']` (every checkpoint
already written would stay unresumable); refusing on a mismatch (it would forbid resuming on new
data, which is goal B's experiment).

**(2) The tally.** `vocab_state` wrote `pair_digest = len(vocab.pair)`, the length of a different
structure, under a comment saying the counts were carried; `restore_vocab` read nothing. The tally is
cumulative and is the only evidence `mint_burst` draws on, so a parent at 160 windows resumed to 202
reached the window-201 burst with `sum(tally)` 5248 and 0 eligible pairs and minted **0**, where the
uninterrupted run had 25728, 62 eligible and minted **6**. **Ruling: the whole tally and
`tally_seen` are saved exactly**, as three parallel int64 arrays each, and restored after the
merge-count refusal; `tally_pairs`/`tally_sum` let the restore check the arrays against themselves
(`tok.tally_restored` counts the pairs put back and is absent on a checkpoint that predates the
field). **Rejected:** a top-K or a count floor — a resumed run would still rank differently, since a
pair just under the cutoff restarts from zero, and the `mint_pmin` arm's per-left-token marginal is
computed over the whole tally. At ~1.4k pairs the payload cost is negligible; if it ever is not,
the answer is a declared cap with a Gate, not a silent truncation.

**(3) The reconciliation keys.** `_replay_merges` compared `min_pair`, `max_tok`, `dropout` and `vmax`,
and `save_vocabulary` wrote none of them, so `tok.load_reconciled` read 0 — *compared and agreed* —
on a resume at `TOK_MAX_BYTES=12`, `TOK_MIN_PAIR=7`, `LM_VOCAB_SLOTS=8192` against a file written at
16/50/4096. **Ruling: `save_vocabulary` writes all four from the RESOLVED CONFIG**, and `vmax` is the
wire `d_vocab_ceiling`, never `vocab.ceiling`, which the fixed arm narrows to the achieved size and
would make every fixed-mode resume report a false mismatch (driven: a fixed-mode save/replay at
unchanged levers reads 0). A file written before the keys is still checked for `max_tok`, falling
back to its `max_bytes` — the same number. **And the reconciliation rows now survive
`restore_vocab`**: its `counters.update` used to overwrite this resume's `tok.load_reconciled` and
`tok.bpt_*` with the parent's copies whenever the parent was itself a resume; the parent's copies
are dropped and this process's are kept.

**Not in this ruling:** a `ckpt.pt.prev` generation has no vocabulary file of its own
(`save_vocabulary` does not rotate, and `CKPT_RESUME=<dir>/ckpt.pt.prev` resolves a
`d_vocab_read_path` nothing writes, so `build_vocabulary` refuses it by name). That is a property of
the `CKPT.resume -> TOK.d_vocab_read_path` coupling, not of this package's state, and is left open.
**CLOSED 2026-09-26 (register LOW-Q-TOK-13-PREV; Proposal 05 §8 1.1).** The coupling was never the
problem: `derive.checkpoint_base` already resolved `CKPT_RESUME=<dir>/ckpt.pt<suffix>.prev` to
`<dir><suffix>.prev.dyntok.json`, and nothing wrote that file. **Ruling: `save_vocabulary` rotates
its own file with `ckpt.pt<suffix>.prev`.** It moves `<base><suffix>.dyntok.json` to exactly that
path — the file a save under the suffix `<suffix>.prev` would write — in CKPT's order (the new file
is written to a `.tmp`, the current one is rotated iff it exists, the `.tmp` then replaces it) and
by CKPT's failure rule (a failed rotation is counted and the new generation is written anyway). No
lever, no signature change and no new entry point: it is a persistence invariant, and TOK renames
only the file it owns. TOK does not ask whether CKPT rotated; the root (`spine/loop.py::_save`)
calls `save_vocabulary` only when `CKPT.save` returned True, and every CKPT refusal returns before
CKPT touches a file, so the two rotations happen in one save or not at all (§3 stage `C`). **DID IT
FIRE:** `tok.vocab_rotated` and `tok.vocab_rotate_failed` are seeded at 0 on every save with saving
on and are ABSENT with saving off; `tok.vocab_rotate_failed_detail` names the paths and the error of
the last failure; the in-place arm below has a row of its own (`tok.vocab_rotate_refused` as ruled
here, `tok.vocab_rotated_in_place` since the correction). All four are
per process (`restore_vocab` drops a parent's copies, as it does the replay rows), while
`tok.vocab_saved` stays lineage-cumulative — §8 1.6 (LOW-RESUME-SAVED-COUNTERS) rules on `saved`
counters and does not cover these. **In place — ruled here as a skip, CORRECTED 2026-09-27 to a
rotation (see the correction below):** a run resumed from `<dir>/ckpt.pt.prev` that saves into
`<dir>` has `d_vocab_read_path` as its rotation target. This ruling skipped the rotation there, on
the claim that skipping never destroys a consistent parent pair where rotating could; that claim was
false in the common case, where `ckpt.pt` is present. In-place rollback policy is §8 4.4 (C09).
**The root warns** after the final save whenever a rotation failed or ran in place, because the
report's `TOK(vocab.counters)` is snapshotted before that save (the report's rotation rows are
re-read there too since the correction, (ii) below).
**Driven:** `tests/test_continuation.py` S7 — a parent saved twice (a periodic save at step 101, the
final at 135, with 256 and 259 merges), resumed from `ckpt.pt.prev`, continues for 34 windows equal
to the uninterrupted run's losses exactly, minting three tokens on the way; either checkpoint beside
the other generation's vocabulary is refused by the merge count (256 against 259, both directions);
the older checkpoint with no vocabulary is still refused by name; a failed rotation keeps the new
generation; and the in-place case as corrected below.
`tests/test_tok_persist.py` P5 drives the same through the entry points alone (byte-equal rotation,
which proves the order; the suffixed form; the failure; the in-place rotation; saving off; the rows
staying per process), and `tests/test_couplings.py` C5 pins the two read-side spellings. **Residual,
stated and not closed:** a pairing that slips (either side's rotation failing, a crash between the
two calls) is caught only when a mint separates the two generations. On one lineage the merge list
is append-only, so equal counts there mean equal files; across two lineages (a reused `CKPT_DIR`)
equal merge counts are not proof of equal vocabularies. CKPT's own failed rotation is still
uncounted.
**CORRECTED 2026-09-27 (build 1.1's review) — the in-place arm rotates, the report reads the rows
after the final save, and a run directory named for a snapshot is refused.** (i) *In place.* `CKPT.save`
runs first in the same save and moves `ckpt.pt` onto `ckpt.pt.prev`, so the checkpoint the file at
`d_vocab_read_path` paired with is gone before `save_vocabulary` runs, and the file at
`<dir>.dyntok.json` is the vocabulary of the checkpoint CKPT just moved. The skip left that file where
the new one replaced it, and the in-place condition holds for the whole run, so every later save
skipped too. Driven on the tree that skipped: S7's parent (steps 101 and 135, 256 and 259 merges)
and an in-place child that saved once left `ckpt.pt.prev` at step 135 beside the 256-merge file,
refused at resume by the merge count, with the 259-merge vocabulary nowhere on disk; S7 pinned that
refusal as expected. **Ruling: the in-place arm rotates like every other**, counted as
`tok.vocab_rotated` and `tok.vocab_rotated_in_place` (seeded only on that arm; it replaces
`tok.vocab_rotate_refused`, which `restore_vocab` still drops from a blob that carries it), and the
root warns. Nothing is lost to the running process: `build_vocabulary` replayed `d_vocab_read_path`
at compose and nothing reads it again. The new file is still never written onto
`d_vocab_read_path`. What an in-place save costs is CKPT's one-generation ring: the generation the run
resumed from is gone from disk in both halves. Refusing the configuration at compose was the other
fix offered, and it was not taken because it would remove in-place rollback, a configuration that
runs. **Residual, stated:** the rotation follows CKPT's rule, rotate iff the current file exists, so
it keeps the pair only while a checkpoint and its vocabulary exist together. A rollback that deleted
`ckpt.pt` but kept `<dir>.dyntok.json` has split them; CKPT then rotates nothing, TOK rotates the kept
file onto the one the run resumed from, and `restore_vocab`'s merge count refuses that `.prev` pair
whenever a mint separates the two. (ii) *The report.* The rotation rows are seeded inside
`save_vocabulary`, and `_report` snapshots `TOK(vocab.counters)` before the final save, so a saving
run whose only save is the final one printed them ABSENT, the unreachable reading, and a final-save
rotation reached no output line. `spine/loop.py::run` now copies the live rotation rows into the
report after the final save; they stay ABSENT when no vocabulary save ran in the process. TOK could
not seed them at build: its one view of saving is `d_vocab_save_path`, which is `off.dyntok.json`
at `CKPT_DIR=off`, a spelling CKPT reads as saving off. On these rows alone the report is one save
ahead of the final blob, which `restore_vocab` never reads them from; the save counts keep the
snapshot (Q-CKPT-4). (iii) *A directory named for a snapshot* — see the CKPT section: `saving_on`
refuses a `CKPT_DIR` ending in `.prev`, `.best` or `.best<N>`, whose vocabulary is the file this
ruling rotates run `<X>`'s previous generation onto. **Driven:** S7 now asserts that `ckpt.pt.prev`
is the parent's step-135 checkpoint beside its own vocabulary after an in-place save, and that it
resumes; that the report counts the final save's rotation and failure and prints no row with saving
off; that a child resumed from the failed-rotation run's final blob, which carries
`tok.vocab_rotate_failed` and its detail, holds no rotation row before it saves (the check it
replaces resumed from the step-101 blob, which carries none, so it could not fail); and that
`CKPT_DIR=<X>.prev` and `<X>.best3/` are refused at compose. P5 asserts the in-place rotation byte
for byte on two successive saves. **Not changed, and stated:** a resume from `<dir>/ckpt.pt` that
saves into `<dir>` makes `save_vocabulary`'s own destination `d_vocab_read_path`, and the older rule
still raises there at the first save, after CKPT has written.

**Not in this ruling, and OPEN — the tally round-trips exactly, the mint bursts after a mid-epoch
resume still do not match the uninterrupted run.** (2) makes the pair tally the parent's to the count,
but `TOK.on_window` is then fed different ids from the ones the uninterrupted run tallies at the same
step, so the first post-resume mint burst ranks different pairs (on the commit that made (2): vp vy
up wr px tv resumed, against vp vy cn up tv wr uninterrupted). Driven 2026-09-24 at `DATA_STREAM_BYTES=150000`, a 160-window parent: the uninterrupted run
feeds step 161 `[479, 100, 100, 470, 285, 111]`, step 162 `[106, 104, 373, 375, 431, 439]`; the resume
feeds step 161 `[477, 429, 419, 489, 68, 117]`, step 162 `[454, 121, 112, 121, 268, 121]`, and its
step 161 is window **0** of its epoch (`loop._window_bounds` called with `i=0`). That is Q-RUN-10's
declared mid-epoch replay, on a stream re-segmented at the saved vocabulary: the child restarts the
epoch rather than resuming at the parent's stream position. **Nothing TOK holds can close it**; it
closes when DATA and the loop restore the stream position (the byte-cursor remap, Q-RUN-8 option
(a)). Until then a goal-B resume is the same run in its state and **not** in the text it trains on
next, and any comparison of post-resume vocabulary growth against an uninterrupted run is comparing
two different streams.
**CLOSED 2026-09-26 by Q-RUN-16 (03b S0b, c8d8e33):** a mid-epoch resume rebuilds the parent's exact
stream, so `on_window` is fed the uninterrupted run's ids; `tests/test_continuation.py` S5, "a save
between a mint and the next act continues exactly". Register LOW-Q-TOK-13-PREV (1).

### Q-FAB-7 — the fabric's routing saw the window's own targets — **RESOLVED 2026-09-24: THE SIGNATURE ENDS AT THE WINDOW'S FIRST BYTE, THE ROUTE STATE IS h[:, 0], AND A FLUSH ROUTES ON ITS FIRST WINDOW'S DOMAIN. ⚠ EVERY LOSS NUMBER TAKEN BEFORE THIS DATE WAS MEASURED ON A NON-CAUSAL FORWARD AND IS NOT COMPARABLE WITH ONE TAKEN AFTER IT**
Routing is **one decision per window**, applied at every position, so whatever the decision reads,
position 0 is scored with it. Three channels fed it text the window is scored on predicting; nothing
in the tree declared the routing non-causal, and `spine/compose.py::_sample_window` already said the
opposite (*"a run that encodes the units AHEAD of the cursor is encoding text the model has not
trained on"*) — the window being predicted is ahead of that cursor, because nothing has trained on it
when its logits are computed. All three are driven by `tests/test_causality.py`, which fails four
checks on the tree before this ruling and passes all eight after it (C4, added with (4) below,
adds three more, which fail before (4) and pass after it).

**(1) The signature cursor.** The loop passed `win_in_epoch` *after* its increment (the window's index
plus one) to `_sample_window`, so the `SIG.encode` / `DOM.observe` sample ended at the **last
target's** first byte and covered the whole window: window 149 of a default run has x bytes
[28402, 28599) and was routed on a sample over [28407, 28599). The domain id `FAB.forward` bans on is
assigned from the same sample. `SIG.train_step`'s `seen_units` read the same cursor, so an encoder
anchor could be drawn from the text the same window was about to be routed on. **Ruling: both take the
window's own 0-based index**, so the sample is the `width_units` units ending at the window's first
byte. Ordinal 0 — the first window of every epoch — is now called too and its sample is all pad
(`_sample_window` left-pads what the stream does not have); that is what a generator starting cold
holds. **It costs more than one window per epoch** (measured 2026-09-24 at `DATA_STREAM_BYTES=30000
RUN_EPOCHS=2 DATA_RESAMPLE=1`, 315 windows): `DOM.observe` founds the run's first domain on the all-pad
sample (windows 0 and 1, 191 and 12 pad units), the domain stays alive, and epoch 1's second window
(17 pad units) is pulled back into it with `boundary=True`, window 159 following — `part.n_boundaries`
34 and `n_created` 14 against 32 and 13 on the tree before this ruling, whose epoch-1 opening stayed in
the running domain. Keeping a pad-dominated sample out of `DOM.observe` needs a domain id for a window
DOM did not assign, so it is left to the owner; the numbers are the price of not doing it. **Rejected:** ending the sample at byte_pos[first + 1]
(it would add x[0], which every position already sees, and it needs a second cursor arithmetic beside
`_signature_cursor`'s ordinal one).

**(2) The route state.** `fabric/api.py::_route_query` added `hproj(h.mean(1))`, a mean over every
position. With the signature held fixed and a window's tokens [t+1:] replaced, max|Δlogit| at positions
≤ t through `LM.encode -> FAB.forward -> LM.decode` was 2.4e-6 at window 2, 1.1e-4 at window 150 and
8.2e-4 at window 600 (`LM.encode` alone: exactly 0.0) — growing as the router learned. **Ruling: the
state is `h[:, 0]`**, the hop's hidden state at the window's first position: the only per-window
summary of the window's own tokens every position may see (causal on both LM arms), and it still moves
between hops, because each hop's mixture is added at every position, position 0 included — which is
what the term exists for (the old tree measured I(domain; (hop0, hop1)) = I(domain; hop0) without it).
After the ruling the same measurement reads **exactly 0.0** at windows 2, 150 and 600. **Rejected:**
per-position routing on a causal running mean (a (B, L, n) routing distribution with an L-times-wider
expert gather, and `use`/`uage`, the halt EMA and the balance term re-denominated from windows to
positions — a different fabric, not a repair); the previous window's pooled state (identical at every
hop, which is exactly what this term exists not to be).

**(3) The flush's domain.** `FAB.forward` takes one `domain_id` per flush and its breadth ban masks
every row. The loop passed the **last** window's id, assigned from a sample over the earlier rows' own
text at `OPT_BATCH_WINDOWS > 1`. **Ruling: the flush's first window's id (`dids[0]`)**, whose sample
precedes every row. At the shipped `OPT_BATCH_WINDOWS=1` the two are one id. `FAB.observe`,
`DOM.note_competence` and `MEM.write` book what already happened and reach no logit of the flush;
since **Q-FAB-10** all three take one id **per window** (the first two took the last window's id for
the whole flush until then). **(3) alone did not make `OPT_BATCH_WINDOWS > 1` causal; (4) did.**

**(4) The two batch-wide writes inside the training forward (added 2026-09-24).** At
`OPT_BATCH_WINDOWS > 1` row k's signature is the `width_units` bytes before row k's first byte — row
0's own text and targets — and two mechanisms of a `training=True` pass wrote a mean over **every** row
into state that row 0's routing then read: `fabric/api.py::_spawn_check` decoded a new expert from
`query.mean(0)` before the hop loop, and `fabric/api.py::_ground_update` moved `pop.cent` toward
`normalize(signature).mean(0)` between hops. Measured with `tests/test_causality.py` C4's probe (a
2-row batch of consecutive windows after 40 training windows at `OPT_BATCH_WINDOWS=2`, each forward on a
copy of the population, a repeat differing by exactly 0.0; replace **only row 1's signature**, read row
0's logits): 4.8e-7 at the shipped depth (the spawn channel: 0.0 at `FAB_SPAWN=0`), 1.3e-3 at
`FAB_DEPTH0=0 FAB_SPAWN=0` (the grounding channel) and 1.5e-4 at `FAB_DEPTH0=0` with both. The eval pass
(`training=False`) read 0.0 throughout, which is why C2 (one row, eval) could not see either.
**Ruling: the spawn test reads row 0's query alone, and at a batch of more than one row the grounding
EMA is applied after the walk** — the same updates, in the same hop order, once no row is still being
routed. At a batch of one both are the tensors they were (row 0 is the batch, and its own signature
precedes it), so the shipped arm is bit-identical; after the ruling all three probes read exactly
0.0. **Rejected:** grounding on row 0 alone (it throws the other rows' signatures away — a loss of
function the deferral does not pay); spawning from the previous flush's query (it changes the shipped
batch-of-one arm, which was already causal); deferring the spawn (a birth writes `pop.A` in place and
must precede the graph). The per-hop routing between hops at `B > 1` no longer sees this flush's
centroid moves; at the shipped `B = 1` it still does. The 80-window loss curves at
`DATA_STREAM_BYTES=60000` are bit-identical at `B = 1` on both depths (sum 484.8295 shipped, 486.1608
at `FAB_DEPTH0=0`); at `OPT_BATCH_WINDOWS=2 FAB_DEPTH0=0` the 40-flush sum moves 250.192 → 251.705
(mean 6.255 → 6.293), one seed, which is the price of no longer training row 0 on its own targets.

**What the leak was worth, measured.** On a model trained 600 windows at `DATA_STREAM_BYTES=120000`,
the CE of 32 windows from the last 100 with their training-time signature minus the CE with the
window-start one: mean −0.264 nats, negative on 14/32, min −5.474 (area `c` −0.368, `num` +0.00003) on
the pre-ruling tree; on a tree trained causally, −0.002 (min −0.063). **The leaky tree trained worse,
not better**, over the same 600 windows (mean of the last 100 flush losses, RUN_SEED 0 / 1): leaky
6.480 / 6.991; causal 4.601 / 4.846; signature repaired alone 4.650 / 4.874; route state repaired alone
4.504 / 5.934. **The gap is all after the stream's area switch near window 450**: over windows 0–449
the mean flush loss is leaky 4.942 / 4.955 against causal 4.954 / 4.967, and over 450–599 it is leaky
6.412 / 7.015 against causal 4.903 / 5.625. Repairing the signature alone recovers it on both seeds
(4.878 / 5.584); repairing the route state alone recovers it on one (4.758 / 6.371). The
default 300-window run (`DATA_STREAM_BYTES=200000`) is **not** bit-identical: flush 0 agrees (B is zero
at birth, so routing reaches no logit yet) and every later flush differs; mean flush loss 5.443 → 5.509,
last 100 5.235 → 5.283, final 5.8673 → 5.1638. Two seeds on one geometry is a direction, not a result;
the owner's GPU runs are what settle it. **Generation:** before this ruling no generation path could
reproduce the training-time signature — it was a function of the text being generated; after it,
the signature, the domain id, the novelty (the previous window's) and the route state are all formed
from material a generator holds before it emits the window's second token (`EVAL.generate` itself is
still in `DEFERRED_ENTRY_POINTS`).

**Not in this ruling — the load-balance term's reach into the LM (a measurement, no change).** The
balance/ponder aux term reaches `LM.body` and `emb` through the route state. On the pre-ruling tree
at flush 1, ‖∂aux/∂`body.bias_ih_l0`‖ 4.777 against the LM loss's 1.376 and ‖∂aux/∂`emb.weight`‖
0.608 against 0.306; 0.022 / 0.003 by flush 30 (≈2% and 1%). After the ruling it reaches them
through `h[:, 0]` alone: 1.507 / 1.376 and 1.088 / 0.306 at flush 1 (the embedding share now lands on
the first tokens' rows), 0.016 / 0.010 by flush 30. At `FAB_BALANCE=0` the flush-1 aux gradient is
0.073 / 0.009 before and 0.023 / 0.016 after. No docstring says the routing regulariser must not reach
the language model, so nothing is changed; if the first steps' steer matters, a `detach()` on the
route state or a balance warm-up is the lever to measure, not to assume.

### Q-FAB-8 — the loop never handed `FAB.forward` a `head` or `targets` — **RESOLVED 2026-09-24: BOTH ARE PASSED, THE VOTE'S LOGITS ARE THE PREDICTION, AND THE LAST PASS'S GATES ARE PRINTED. ⚠ THE SHIPPED DEFAULT OBJECTIVE CHANGED: `FAB_HOP_VOTE=True` FORMED FOR THE FIRST TIME**
`spine/loop.py::_flush` called `FAB.forward` with `h, signature, novelty, step_windows, domain_id,
live_domains, training` and nothing else, although this contract's FAB section says `head` ← LM and
`targets` ← the loop and `compose.py`'s LOOP_ORDER row says *"head=LM.decode ... bound by _head"*.
With `head=None` and `targets=None` the per-hop vote (`FAB_HOP_VOTE`, **on** by default), the society
arm's prediction-level blend and its halt-on-base spend, the independence loss (`FAB_IND_W`) and deep
supervision (`FAB_HOP_SUP`) cannot run: `FAB_SOCIETY=1`, `FAB_HOP_VOTE=0` and `FAB_IND_W=0` gave the
default's `=== loss 8.3247 -> 4.4490` over 60 windows, `FAB_HOP_SUP=0.3` was bit-identical to its
absence, and the report printed `fab.ind_applied 0` / `fab.hopsup_applied 0` — G4's "armed, did not
fire" — while the pass's own gates said *"no head was supplied"* on `FabricOut.gates`, which nothing
printed. **Every society-vs-chaining comparison (D7) taken before this date measured the default
forward.** `tests/test_fabric_forward.py` drives this ruling and Q-FAB-9 .. Q-FAB-11 through the real
loop (W1–W6); tests/test_fabric.py could not see any of them, because it hands FAB.forward a head and
targets of its own.

**Ruling, and the four choices inside it.** (1) **`head` is `compose.py::_head`, now a one-argument
callable that binds the vocabulary and reads it at call time** (`live_vocab=Vocabulary.size()`,
`retired_ids=Vocabulary.retired`) — it was `lambda h, **kw: decode(...)`, which raises `TypeError` on
FAB's `head(x)` because decode's two vocabulary arguments are keyword-only and required; `targets` is
`y`. (2) **When `FabricOut.logits` is present it is the prediction** — `lm_loss`, the surprise and the
next flush's novelty all read it — and `hidden` is re-decoded only when nothing voted, which is
`FabricOut`'s own rule (the H11 offset). (3) **FAB floors the head's masked `-inf` rows at `_NEG`**
(`fabric/api.py::_decode`): the vote and the society blend multiply logits by weights that are
exactly zero at `FAB_HALT=0`, and `0 × -inf` is nan — measured, `LM_MASK_DEAD_ROWS=1 FAB_HALT=0` without
the floor raises `DOM.note_competence: bits is nan` on flush 0; with it the flush reads 6.247313, the
same as `LM_MASK_DEAD_ROWS=1` alone. `exp(-1e4 - max)` is 0.0 in fp32 and bf16, so the masked
distribution is unchanged. (4) **FAB calls the head only when something consumes it** (the vote, the
society arm, `hop_sup > 0`): LM.decode applies dropout, so an unconsumed decode would move the RNG and
make `FAB_HOP_VOTE=0` a different run rather than the same run minus the vote. **The last training
pass's gates are kept on `Population.pass_gates`** (re-earned, replaced each pass) **and
`FAB.counters` renders them** beside the build gates; and **`fab.ind_applied`, `fab.hopsup_applied`
and `fab.halt_spent_on_base` are seeded only on the arm that can reach them** (G4: absent is
UNREACHABLE), still before the branch that bumps them. The same pass's `fab.depth_curriculum` gate now
reads UNREACHABLE on the society arm, which pins the walk at one hop: it printed "armed" beside
`fab.depth_now 4` while `fab.hops_taken` read 60 over 60 passes.

**Measured.** `FAB_SOCIETY=1 FAB_HOP_SUP=0.3`, 4 windows: `fab.ind_applied 4`, `fab.halt_spent_on_base
4`, `gate:fab.independence` in the report; `hop_sup` UNREACHABLE with the reason *"depth=1 (FAB_SOCIETY=1
pins the walk at one hop)"*. `FAB_HOP_SUP=0.3 FAB_DEPTH0=0`: `fab.hopsup_applied 4`. The four 60-window
arms above now give four different reports (`FAB_SOCIETY=1` ends 4.4598, `FAB_HOP_VOTE=0` 4.4635, the
default 4.4631). **The default 300-window run (`DATA_STREAM_BYTES=200000`) is not bit-identical:**
flush 0 agrees (every expert is born an identity, so the vote is the decode), flush 2 is the first to
differ (8.3407917 → 8.3407936), and the mean flush loss is 7.4519 → 7.4519 over flushes 0–49,
5.0696 → 5.0699 over 50–99, 4.9200 → 4.9270 over 100–199 and **5.0998 → 4.9704 over 200–299**; the
final flush 7.2565 → 5.1147 (one window, noisy). **`FAB_HOP_VOTE=0` on the new tree reproduces the old
default curve bit for bit (300 of 300 flushes)**, so the whole default change is the vote. Wall time
76.1 s → 80.4 s on the shared 4-core CPU (ens_k=2 head calls per hop instead of one decode). One seed
on one geometry is a direction; the owner's GPU runs re-baseline the default before any arm is
compared with it.

**Rejected:** refusing `FAB_SOCIETY=1` / `FAB_HOP_SUP>0` at compose until the wiring landed (it leaves
the shipped `hop_vote` and `ind_w` silently inert, and removes an arm the owner asked to measure);
forming the head in `loop.py` (the composition root is where entry points are partially applied, and
`_head` already existed for exactly this — it only had to be made callable); masking at `-inf` and
guarding each weighted sum inside FAB (four sites, and the next consumer would be a fifth);
decoding `hidden` anyway and ignoring the vote (that is H11, and it keeps the shipped lever inert).

### Q-FAB-9 — `live_domains` was the literal 1 — **RESOLVED 2026-09-24: IT IS `DOM.census`'s `n_live`, CARRIED FROM THE dom.manage PASS, AND 1 UNTIL THAT PASS FIRST FIRES**
The flush passed `live_domains=1`, so the breadth cap's limit `max(FAB_DOM_MIN, int(FAB_DOM_FRAC ×
live_domains))` was `FAB_DOM_MIN` on every pass: `FAB_DOM_FRAC=0.1` and `0.9` gave identical
300-window runs at `DATA_STREAM_BYTES=120000` (limit 4 on 300/300 passes, 103 passes with a ban, 1322
bans, final loss 4.016625 on both) while `DOM.census` held 15 live domains. The breadth cap is the
fabric's own guard against one expert absorbing every domain — forgetting control for goal B.
**Ruling:** the loop carries `DOM.census`'s `n_live` from the census the dom.manage pass already takes
(the wire LOOP_ORDER's DOM.census row names, with the staleness it declares) and passes it every
flush. **After:** `FAB_DOM_FRAC=0.1` limit 4 on all 300 passes (`max(4, int(0.1 × n))` is 4 for every n below
50, so the shipped default's cap is still decided by `FAB_DOM_MIN` alone), 825 bans; `FAB_DOM_FRAC=0.9`
limits 4 / 7 / 9 on passes 1–100 / 101–200 / 201–300 (live_domains 1 / 8 / 10) and 0 bans — the two
arms now separate. **Before the first pass fires (windows 1–100 at the shipped `DOM_MANAGE_EVERY`) the
value is 1**, which FAB's own `max(1, ...)` floor already treats as "no census yet", and
`fab.breadth_cap`'s gate prints the count it was handed. **Rejected:** a census at loop entry (a
`DOM.census` call at no LOOP_ORDER row, which bumps `part.n_censuses` on a schedule nobody declared —
it would matter most on a resumed run, where the stale window is up to 100 windows of routing at
`live_domains=1` against a restored partition, and that is the case to measure if it is revisited);
a census every flush (a stage-B call to a stage-A row, and `part.n_censuses` would become a flush
count); recomputing the count in the loop from `dids` (a second answer to a question DOM owns).

### Q-FAB-10 — a flush was filed under its last window's domain — **RESOLVED 2026-09-24: `FAB.observe` AND `DOM.note_competence` TAKE ONE ID PER WINDOW; THE BREADTH BAN STAYS BATCH-WIDE AND IS COUNTED. ⚠ A FROZEN SIGNATURE WIDENED**
At `OPT_BATCH_WINDOWS > 1` the loop handed `FAB.observe` and `DOM.note_competence` the last window's
id for the whole flush, and `note_competence` the flush **mean** as a Python float, which slipped past
its own refusal of a batch vector (*"averaging it here would attribute a whole batch's windows to
whichever domain the last one landed in"*). Measured at `OPT_BATCH_WINDOWS=4`, 240 windows: 21 of 60
flushes spanned more than one domain and `FAB.observe` affiliated some window under another window's
domain on all 21 (flush 0: windows `[0, 0, 1, 1]`, booked `[1]`); `note_competence` was called 60 times
for 240 windows. **Ruling:** (1) `note_competence` is called once per window with that window's `did`
and its own per-window loss in bits — 240 calls, one per window, each on its own id; (2)
`FAB.observe`'s `domain_id` **accepts one id per row** (a length-B sequence or (B,) tensor; an int still
broadcasts, exact at batch 1) and `dom_of` is written per row — after: 0 of 21 mixed flushes
mis-affiliated, flush 0 booked `[0, 0, 1, 1]`; (3) `FAB.forward`'s breadth ban **stays batch-wide on
`dids[0]`** (Q-FAB-7's causal choice) because `domain_id` is one int in its frozen signature and the
ban mask is built once per pass — **a per-row ban is the owner's call** (it widens a frozen signature
and builds a (B, n) mask), and until then the loop's own book counts **`loop.flush_mixed_domain`**
(seeded only when `OPT_BATCH_WINDOWS > 1`, printed at R under `LOOP(flush books)`): 21 of 60 above.
Bit-identical at the shipped `OPT_BATCH_WINDOWS=1`. **Rejected:** splitting a flush by domain (it
changes the batch and the optimizer step — a different experiment); averaging per domain before
`note_competence` (the callee's own refusal names it).

### Q-FAB-11 — the two fabric control arms crashed, and `FAB_ON=0` trained 8.9M parameters it never used — **RESOLVED 2026-09-24: BOTH ARMS RUN; AT `FAB_ON=0` THE POOL IS ALLOCATED BUT OUT OF THE OPTIMIZER AND EVERY FABRIC MECHANISM RETURNS BEFORE ACTING**
`FAB.forward` returns `weights=None` on `FAB_ON=0` and `FAB_NORM_ONLY=1` by declaration, and
`loop._flush` raised on `weights is None` at the first flush — after a full compose and SIG warm-up,
naming no lever — so neither ablation could run. Behind the crash, `FAB_ON=0` still put the population
in the optimizer (`=== 10130057 trainable parameter(s)`, 8,929,984 of them the fabric's) and
`FAB.grow_check`, which never read `fab.on`, grew expert 2049 into the switched-off fabric
(`fab.grown_regression 1` beside `gate:fab.growth_armed fired`), contradicting gate `fab.on`'s own
*"every gate below this one reports UNREACHABLE"*. **Ruling:** (1) on those two arms MEM's `owners` is
the window's **domain folded onto the owner blocks** (`sources % d_owner_blocks`), counted per flush
as `loop.owners_from_domain` (seeded on those arms only) because it is a different quantity under the
same argument name; a `None` on the routed arm is still refused. (2) `Population.parameters()` is
**empty at `FAB_ON=0`**: the banner reads `1200072` and AdamW holds no fabric state. (3) `FAB.manage`,
`FAB.grow_check` and `FAB.own_lr_scale` **return before seeding** at `FAB_ON=0`, so their families are
ABSENT (G4: unreachable) — `fab.births` and `fab.rescued`, which `FAB.counters` reads off `Population`
state rather than the ledger, included (they printed present-and-0 until a later 2026-09-24 fix) — and the build gates `fab.growth_armed` and `fab.lr_own` are UNREACHABLE with a
`FAB_ON=0` reason. (4) **The pool is still allocated and checkpointed** at `FAB_ON=0`, so MEM's owner
width, CAP's `n_live` and CKPT's shapes are the same on both arms; the cost is host/device memory for
tensors nothing reads, not compute or optimizer state. `FAB.observe` is unchanged on both arms: it
already counts `fab.observe_unrouted`. **After** (60 windows, `DATA_STREAM_BYTES=120000`): `FAB_ON=0`
rc 0, `=== loss 8.3167 -> 4.3369`, `fab.forward_identity 60`, `fab.n_live 2048`, `loop.owners_from_domain
60`, `fab.lr_calls` ABSENT; `FAB_NORM_ONLY=1` rc 0, `=== loss 8.3248 -> 4.6325`, 10,130,057 trainable (the
arm keeps the experts in the optimizer by design). **Rejected:** a startup refusal naming both levers
(safe, and leaves both ablations unrunnable); owners all in block 0 (collapses provenance, which the
guard's own message refused); a zero-size pool at `FAB_ON=0` (every consumer of `Population` —
`MEM` owner width, `CAP` headroom, `CKPT` restore, the report — would need an arm-conditional path,
turning one crash into several); skipping `FAB.observe` on those arms (it would turn its
`fab.observe_unrouted` reading into an absence).

**2026-09-27 (register LOW-FAB_NORM_ONLY-GROWS, Proposal 05 §8 1.6): `FAB_NORM_ONLY=1` grows, culls
and merges nothing.** `FAB.manage` and `FAB.grow_check` tested `fab.on` alone, so the control arm —
whose forward reads no expert — kept selecting over experts nothing computes: at `FAB_N0=256
FAB_SLOTS=512 FAB_GRACE=1 FAB_MANAGE_EVERY=25` (`DATA_STREAM_BYTES=60000 SIG_WARMUP=20`) a
100-window run grew expert 257 at window 81 (`fab.grown_regression 1`) and ran three manage passes,
with `gate:fab.cull_gate` FIRED and the cull counters present-and-0. **Ruling, on this entry's own
precedent:** both entry points **return before seeding** on that arm, as at `FAB_ON=0`, so the
manage and grow families are ABSENT; the build gates `fab.growth_armed`, `fab.cull_gate` and
`fab.depth_advance` read UNREACHABLE naming `FAB_NORM_ONLY=1` (the default arm's lines are
byte-identical); a resume re-renders none of them (`_refresh_build_predictions` returns on that
arm); and `fab.births` / `fab.rescued` are ABSENT by clause (3)'s rule. That departs from the
register row's wording, which gives the known answer as `fab.births` 0 (stated 2026-09-27, build
1.6's review): the answer is met as `Population.births` == 0, which W7 asserts on the record, while
the counter is ABSENT because growth cannot happen on this arm. The experts stay in the
optimizer and the checkpoint — the arm's point is unchanged, and `FAB.own_lr_scale`, which the ruling
does not name, is left as it was. **After**, on the same configuration: 256 live, no birth, the
family ABSENT, and the loss curve **identical** to the unfixed tree's for all 100 windows (the
norm-only forward reads no expert, and at 256 or 257 live its normalization depth is `hops` either
way). Known answers: `tests/test_fabric_internals.py` I12 (unit: the same inputs merge one pair and
grow one expert at `FAB_NORM_ONLY=0`, and nothing at 1) and `tests/test_fabric_forward.py` W7.

### Q-CKPT-4 — the root discarded both restore verdicts, and three pieces of state did not cross a resume — **RESOLVED 2026-09-24: A REFUSED LM OR OPT RESTORE IS A NAMED REFUSAL THAT STOPS THE RUN; `loop.run` REFUSES A SYSTEM CARRYING ONE; THE LM COUNTERS, MEM's GENERATOR, DOM's STREAM AND `token_seen` NOW CROSS. NO SIGNATURE MOVES**
`LM.load_state` and `OPT.load_state` refuse by **returning** a `LoadReport(refused=True, reason=…)`,
and `compose` called both as bare statements. Driven on a 160-window parent: a child at
`TOK_MAX_BYTES=12` passed the geometry gate, restored **0 of 8** LM tensors, restored OPT at
`opt_step 160`, printed **0 refusals**, and trained a random model under the parent's optimizer (its
first three resumed losses 8.14 / 8.07 / 7.92 against 7.35 / 7.40 / 7.43 on the unchanged control;
ln 4096 = 8.32). **Ruling:** both reports are bound (`System.lm_load`,
`System.opt_load`) and a refusal is **appended to `System.refusals`** with the package's own sentence
— run.py already stops on any refusal before a tensor is trained — and `loop.run` now raises on a
System that carries one, so a driver that skips run.py's check cannot train through it either. The
LM refusal now names `TOK_MAX_BYTES (LM.d_max_token_bytes)` and `LM_CTX (LM.d_pos_max)` instead of
upper-casing a wire's field name (`LM_MAX_TOKEN_BYTES` is not a lever). **And the driving case was
itself a false refusal, corrected later on 2026-09-24:** `max_token_bytes` sizes only the composer's
byte tables, and the composer cannot be built (`LM_COMPOSE=1` raises `NotBuilt`), so on the only arm
that runs a `TOK_MAX_BYTES` move leaves every LM tensor its shape — a copy of the parent with only the
saved field edited to 12 restored 8 of 8 tensors and trained the control resume's first three losses
bit-for-bit. `LM.load_state` now refuses it only when compose is on at either end; otherwise it counts
`lm.ckpt.max_token_bytes_moved`, names the move in its reason, and the root warns
(`tests/test_resume.py` R1b; R1 now drives the refusal with a `pos_max` the live model lacks). **Rejected:** raising at the
`restore.lm` stage (run.py reads `sysm.base_params` and `sysm.process` before it prints refusals, so
an early exit turns a named refusal into a traceback — **superseded by Q-RUN-13**, where the exception
carries the System and run.py prints from it); adding `lm.max_token_bytes` to the geometry
manifest as `EXACT` (every checkpoint written before it lacks the field, and `check_geometry` refuses a
missing field — every existing checkpoint would become unresumable at unchanged levers).
**State that did not cross, each driven:** (1) `LM.state_dict` wrote `"counters"` and `load_state`
never read them — the child reported `lm.embed.calls` 1 against the parent's 160; they are restored
except `lm.resolve.*`, this process's own. (2) MEM's victim generator `store.gen` and DOM's `part.rng`
were re-seeded on every resume while SIG, FAB and WORLD save theirs (child: generator byte-identical
to a fresh `memory.torch` stream; DOM draws 0 against the parent's 79); both now travel, MEM as
`gen` and DOM as `rng`, in the shapes the other three use. (3) `System.token_seen` — the loop-owned
counter of C5 — was never saved, so `LM.anchor_term` re-held every minted row and
`TOK.judge_probation` counted only post-resume appearances; the root writes it under a payload key
**no package owns, `"LOOP"`**, and puts it back as a prefix of the live `LM.vocab_slots`. Older
checkpoints carry none of the new keys and restore as before. **FAB's sidecar recorded `d_model`
under the name `dk`** (`pop.A.shape[1]`), so FAB's own dk refusal could never fire on `FAB_DK` and
`FAB_EMB_HID` was not recorded; it now records `d_model`, `dk` and `emb_hid` off the modules they
size, and reads an old sidecar's `dk` as the `d_model` it was. A checkpoint written by this tree is
refused by an OLDER tree's FAB on `dk` — the one forward incompatibility here, stated. **The geometry
manifest compares `lm.arch`, `lm.compose` and `sig.mode` first**, because `LM_LAYERS=0` resolves per
arch and an `LM_ARCH` change was refused as `LM_LAYERS`. `world.nmax` is **`EXACT`**, not
`MAY_WIDEN`: under Q-WORLD-8 (b) it is the allocation extent of `preds`/`keys`, and `WORLD.load_into`
refuses any difference — the gate let a wider `WORLD_NMAX` through to die after LM, SIG and FAB were
built. `CKPT_RESUME`'s three documented spellings (`runs/x`, `runs/x/`, `runs/x/ckpt.pt`) and a
trailing-slash `CKPT_DIR` share one string rule, `derive.checkpoint_base`, with `resume_source`; only
the bare form resumed before (tests/test_couplings.py C5 pins all of them).

**2026-09-27 (register LOW-RESUME-SAVED-COUNTERS, Proposal 05 §8 1.6): one semantics for the save
counters.** After a resume the packages disagreed about how many saves there had been: a parent that
saved k = 3 times and a child that saved j = 2 times before its report (a 60-window parent and a
40-window child at `CKPT_EVERY=20`, `DATA_STREAM_BYTES=60000 SIG_WARMUP=20 FAB_N0=256
FAB_SLOTS=512`) read **k − 1 + j = 4** on
`lm.ckpt.saved`, `sig.state_written`, `fab.state_written`, `world.state_written`,
`store.n_state_dicts`, `tok.state_written` and `tok.vocab_saved` (each copied its ledger into the
payload before counting the save), **k + j = 5** on `opt.ckpt.saved` (bumped first), and **j = 2** on
`part.n_state_dicts` and `cap.state_written` (their ledgers do not travel). **Ruling:** each package's
save counter is **lineage-cumulative and counts the save that writes it** (and, OWED, a save CKPT
refuses as non-finite: the correction below) — bumped before the ledger
is copied, as `opt.ckpt.saved` always was — and beside it sits a **process-local twin**, the same
name with `_here`, which no restore touches: `lm.ckpt.saved`, `opt.ckpt.saved`, `sig.state_written`,
`fab.state_written`, `world.state_written`, `store.n_state_dicts`, `part.n_state_dicts`,
`cap.state_written`, `tok.state_written`, `tok.vocab_saved` and `data.state_written`, each with its
`_here` (ABSENT before its process saves, and 0 or ABSENT in the report by whether saving is on:
the correction below). The names are the packages' own (renaming to `*.ckpt.saved` would drop
report names a fixture reads); the register's `*` names the role. **DOM's and CAP's ledgers still
do not travel** — each is the record of what this open or this build resolved — so each payload
carries this one count (`payload['DOM']['n_state_dicts']`, `payload['CAP']['state_written']`), put back by
`DOM.open_partition` and `CAP.restore`. **TOK's vocabulary file is written after its blob**
(`spine/loop.py::_save`), so a blob's `tok.vocab_saved` is always one file short; the file is the
record that knows itself, so `TOK.save_vocabulary` writes its **ordinal in the lineage** into the
file (key `vocab_saved`), `build_vocabulary`'s replay puts it on the ledger, and `TOK.restore_vocab`
keeps it over the blob's count — so a blob from the lineage's first save, which carries no count at
all, restores 1. A file older than the key, or a resume at `TOK_MODE=bytes` (which reads no file),
leaves the blob's count standing, one short (the `TOK_MODE=bytes` half is repaired in the correction
below). The file gains one key and older trees ignore it.
**The R stage precedes the final save**, so a report shows (k + j, j) with j the saves before R,
and the final blob holds exactly one more than the report on these keys — `tok.vocab_saved`
excepted, for the reason above. That is a deliberate exception to
the R row's *"the checkpointed counter vectors are the ones the report printed"*: a blob that did not
count itself would restore one save short. **Measured after**, same configuration: (5, 2) on all ten
report rows, the child's final blob 6 on every save count it carries (`data.state_written_here` 3,
`tok.vocab_saved` 5), and a grandchild resumed from it restores 6, `tok.vocab_saved` included, with no
twin crossing. **Older checkpoints** resume unchanged and read one short on LM, SIG, FAB, WORLD, MEM,
TOK and DATA (their blobs never counted themselves); DOM and CAP start from this process's saves;
OPT is exact. Nothing corrects them, because nothing in an old blob says which tree wrote it.
Three neighbours that are **not** this pair: `opt.encoder_steps_here` is an older and different
"here" (the package, Q-OPT-6); LM's tally is process-global (`lm/api.py::_COUNTS`), so an in-process
test clears it for each System that stands for its own process; and CKPT's own per-route record and
the loop's `CKPT.save: N checkpoint(s) written by this process` line count this process. Known answer:
`tests/test_continuation.py` S10. In §2, DATA's and TOK's counter lists name the twins.
**CORRECTED 2026-09-27 (build 1.6's review) — one rule for the twin, `TOK_MODE=bytes` at k + j, and a
refused save still counted (OWED).** (i) *The twins disagreed about what ABSENT means.* No package can
tell whether saving is on. That is `CKPT.saving_on`'s answer, recorded once as `System.saving`, and
TOK's `d_vocab_save_path` cannot tell either (it reads `off.dyntok.json` at `CKPT_DIR=off`). Two
packages guessed. OPT seeded `opt.ckpt.saved_here` 0 at build and `CAP.counters` printed
`cap.state_written_here` 0 for a missing key, while the other eight printed ABSENT until their first
save. So the register's (k + j, j) failed at j = 0, which is the case at the shipped `CKPT_EVERY=0`,
whose one save follows R. Driven at be2382a (the review's scratch `stage1/review/saved_j0.py`): a child
resumed from a 30-window `CKPT_EVERY=0` parent (k = 1), with `CKPT_DIR` set, read `(1, ABSENT)` on eight
rows after 10 windows and `(1, 0)` on OPT and CAP. With `CKPT_DIR=''` OPT and CAP read 0 ("armed, did
not fire") beside eight ABSENT, and S10's grandchild check asserted that split as correct. A saving-off
run's final save also built the payload after the report, although CKPT refuses at saving off before it
reads one. So every package's ledger ended the run one save up with nothing written (driven: after a
fresh 10-window `CKPT_DIR=''` run, 1 and 1 on every package's pair). **Ruling:** no package seeds either
key. OPT's build seed is removed, and `CAP.counters` prints the twin only once the ledger holds it.
`spine/loop.py::_save` builds the payload only where `System.saving` is True; `CKPT.save` is still
called and still counts `refused_off`. `spine/loop.py::_report` renders the armed state over one table,
`_SAVE_COUNTS` (the ten rows; eleven since Q-DATA-9, 2026-09-27, which gave DATA's pair an R row).
With saving on, each row's lineage count and twin read 0 when nothing is counted yet. With saving off
nothing is added, and every twin is ABSENT. The root renders it because only the root holds both
facts: it records `saving_on`, and it is the only caller of the state_dicts. That is the shape of
`part.n_retok_events`, which the root seeds, and of TOK's rotation rows, which it
re-reads (Q-TOK-13's 1.1 correction). A `CKPT.dir` wire was not taken: it needs one wire per receiving
package, eight or nine, and the budget has six left (19 of 25 spent). Nor was a build or restore
argument taken: that is a frozen-signature move in eight packages for a report twin. **The twin,
stated:** on a ledger, `<key>_here` is ABSENT until its process's first save and never crosses a resume.
In the R report it is 0 where saving is on and no save preceded R, and ABSENT where saving is off.
**Residue, stated:** at saving off the lineage keys stay each package's own. `opt.ckpt.saved` and
`cap.state_written` print 0 (`tests/_baseline_fixture.json` pins both at the default), and the other
eight print ABSENT on a fresh run. A restored lineage count prints on every package. **After**, same
scratch: the j = 0 child reads `(1, 0)` on all ten rows, a child resumed from a 3-save parent's
`ckpt.pt.prev` at j = 0 reads `(2, 0)`, and a fresh saving run at `CKPT_EVERY=0` reads `(0, 0)`. A
`CKPT_DIR=''` resume reads `(1, ABSENT)` and ends with every ledger's lineage count as restored, and a
fresh `CKPT_DIR=''` run has no twin on any row or ledger. (ii) *`TOK_MODE=bytes` read `tok.vocab_saved`
one short, and this entry did not mark it owed.* That arm replays nothing, so it never opened the
parent's file, and the blob's count stood: parent k = 2 and child j = 1 at `TOK_MODE=bytes
CKPT_EVERY=20` (`saved_j0.py bytes`) read (3, 1) on nine rows and (2, 1) on `tok.vocab_saved`.
**Repair:** `build_vocabulary`'s bytes arm reads the one key `vocab_saved` from `d_vocab_read_path` when
the file exists (`tok/api.py::_file_ordinal`; nothing is replayed), and `restore_vocab` keeps any count
on the ledger before its restore, which at compose only that read or the replay arm can have put there.
After: (3, 1) on all ten. A missing file, which this arm never needed and still does not refuse without,
or a file older than the key, leaves the blob's count one short, as on the replay arm. (iii) *A refused
save is counted — OWED.* Each state_dict counts before CKPT scans the payload, so a save `CKPT.save`
refuses as non-finite writes nothing and is still counted on every package's lineage count and twin.
Driven (the review's scratch `stage1/review/saved_refused.py`): with a NaN in `fabric.A`,
`loop._save(..., 'periodic')` returned False with no file, and every package read 1 and 1. (i) repairs
the saving-off half. The non-finite half is not repaired: taking the count back needs each package told
after the write (a new entry point in each) or the root rewriting ten ledgers, one of them LM's
module-private tally. So "counts the save that writes it", above, reads **counts every payload built for
a save: each written save, and each save refused as non-finite (OWED)**. The twin then reads one more
than the loop's `CKPT.save: N checkpoint(s) written by this process` line for each refusal, and the loop
warns each one. "Exactly one more than the report" holds for the final blob when no earlier save was
refused. `tok.vocab_saved` is not affected, because the root writes the file only after CKPT wrote. (iv)
S10 now also drives j = 0 (the grandchild at `CKPT_EVERY=0`, and a fresh saving run), saving off (a
resume and a fresh run) and `TOK_MODE=bytes`. Its grandchild check asserts that no twin is on any
ledger, and it pins (iii) as it stands. No lever, wire, signature, entry point or LOOP_ORDER row moved.
At the default (saving off) the report prints the same counters, less the two twins be2382a listed as
new.

### Q-OPT-8 — a MAY_WIDEN resume dropped every AdamW moment — **RESOLVED 2026-09-24: A DIM-0 WIDENING IS RESTORED WITH ZERO-PADDED MOMENTS; EVERY OTHER SHAPE CHANGE IS STILL REFUSED**
The geometry gate admits `fab.slots`, `fab.cap` and `lm.vocab_slots` widening, `LM.load_state` and
`FAB.load_state_dict` widen by prefix, and `OPT.load_state` compared `param_group_shape` exactly and
refused — which the root discarded (Q-CKPT-4): driven at `FAB_SLOTS=640` on a 512-slot, 160-window
parent, the child had 0 of 38 moment entries, `opt_step 0`, `lr_prev 0.0`, and after three windows it
stood at `opt_step 3` and a rate of 7.6e-5 — the warmup re-run — against 1.94e-3 once restored. **Ruling:** the shape test admits exactly a dim-0 widening — group names, tensor
counts and order equal, rank and every trailing dimension equal, live dim 0 ≥ saved — and pads
`exp_avg`/`exp_avg_sq` of the widened tensors with **zeros** for the new rows, keeping each tensor's
`step`; counted as `opt.ckpt.moments_widened` (seeded 0 on every restore that reaches the test).
**Zero is exact for FAB slot rows, and for LM rows only under `LM_MASK_DEAD_ROWS=1`:** in a run built
wide from the start, an unoccupied FAB slot gets an exactly zero gradient every step and its moments
stay zero, and nothing in the tree resets a slot's moments on birth or mint. **At the shipped
`LM_MASK_DEAD_ROWS=0` a never-minted head row is in the softmax denominator**, so its true moments are
small but nonzero (2026-09-24, 2 default windows: `head.weight` `exp_avg_sq` nonzero on 3584 of 3584
never-minted rows, mean 4.0e-12, `head.bias` likewise; 0 of 3584 under the mask; `emb.weight` 0
either way). For an `LM_VOCAB_SLOTS` widening zero padding is therefore an approximation: the new
head rows' first updates are close to sign-SGD at the full rate, pushing down logits no target uses.
It is kept (OPT does not know which rows are minted, so the saved never-minted rows' mean is not
available to it without a new argument, and the difference was not measured to matter). An
`LM_VOCAB_SLOTS` child is not loss-identical to its control for a separate reason as well: the new
head rows keep their init and join the unmasked softmax. After: `FAB_SLOTS=640` on a 512-slot parent restored 2 widened tensors, `opt_step 160`,
and its first three resumed losses were **bit-identical** to the unwidened control's. Anything else
still refuses (ISSUES P1-L50), and the refusal now names the first differing tensor, since the
per-group summary is identical on both sides of a pure shape change. `counters()`'s
`opt.ckpt.horizon_changed` gate no longer says "no checkpoint has been loaded" for a restore that was
offered and refused. **Rejected:** a cold-optimizer opt-in lever (nothing asks for it once widening
restores); copying a neighbouring row's moments into new rows (no row is a neighbour of an
unoccupied slot).

### Q-SIG-2 — `SIG.warm_up` re-trained the restored encoder at every resume — **RESOLVED 2026-09-24: ON A RESTORED ENCODER `warm_up` TRAINS NOTHING AND RETURNS THE PARENT'S REPORT**
No ruling chose re-warming: `WarmupReport`'s "`warm_up` REPLACES `SigState.warmup_curve`" rules on how
a curve is kept, while this contract lists the "warmup curve **and its verdict**" as checkpointed and
the legacy tree skipped the warm-up on resume. Driven on a 160-window parent: the encoder AdamW went
from step 956 to 1756, mean cosine between parent and resumed signatures over the same 160 windows
was 0.53, and **101 of 160** windows changed nearest restored DOM centroid. **Ruling:**
`SIG.load_state_dict` marks `SigState.encoder_restored`, and `warm_up` then returns a `WarmupReport`
rebuilt from the checkpointed curve and `sig.warmup_*` counters, takes no draw off the restored stream,
counts `sig.warmup_skipped_resume` (seeded 0 on the learned arm) and prints Gate `sig.adaptive_stop`
UNREACHABLE with a `RESUMED` reason. The root's collapsing-verdict warning reads the parent's verdict,
so a collapsed parent still marks its child. After: encoder identical to the checkpoint, cosine 1.0,
0 of 160 centroid changes. **`SIG_WARMUP` is therefore inert on a resume**, and an operator who
sets it explicitly there gets a startup warning saying so (added later on 2026-09-24; before it a
resume at `SIG_WARMUP=1500` skipped the warm-up with no word naming the lever). **Rejected:** a `SIG_REWARM_ON_RESUME` lever (the lever's own note says
more steps degrade the encoder past 1000–4000, and re-warming stacks per resume; it can be added the
day someone asks for the behaviour by name); warming then restoring the saved encoder (pays the
budget to discard it).

### Q-CAP-3 — a resumed valve took its caps from the wrong place, under the wrong key — **RESOLVED 2026-09-24: `new_valve` READS THE KEY `CAP.state` WRITES, ONLY ON AN ARM ARMED NOW AND AT SAVE; `CAP.restore` NO LONGER WRITES CAPS**
`new_valve` looked up `restored["fab_start"]` while `CAP.state` writes `cap_experts`, so its checkpoint
branch never ran; `CAP.restore` then wrote the saved caps onto every unpinned arm, including under the
shipped `CAP_TARGETS=off` and after a slot widening, without touching `Valve.origin` (driven: a clean
`FAB_SLOTS=1024` resume of a 512-slot parent came back at `cap_experts 512` against a hard ceiling of
1024, origin "off"; a checkpoint doctored to `cap_experts = n_live` declined a regression birth at
headroom 0). **Ruling:** `CAP.state` records each arm's provenance (`armed_*`, `hard_*`); `new_valve`
takes a saved cap only on an arm armed now **and** at save, follows the live ceiling when the saved cap
was at its saved ceiling (the sentinel's state), clamps to the live hard ceiling, and says which in
`origin`; `CAP.restore` restores the pin clocks and high-water marks and still counts
`cap.state_refused` when an operator's value beat a saved cap **that `new_valve` would have taken**
(armed now, not saved unarmed, not at its saved ceiling — until a later 2026-09-24 fix it also counted
caps never on offer, e.g. a parent saved with `armed_experts` False resumed at `CAP_TARGETS=experts
CAP_FAB_START=400` read `state_refused 1`). A checkpoint without provenance keys is
taken as the old restore took it, on an armed arm only, and `origin` says it carries none.
**Rejected:** reading the saved hard ceiling from the snapshot's geometry manifest at the root (a
second producer for a CAP fact); keeping the cap writes in `restore` behind a `targets` test (two
places deciding the starting cap is how the two disagreed).

### Q-DOM-1 — `DOM_ENABLED=0` restored a trained partition in silence while `WORLD_ENABLED=0` refuses — **RESOLVED 2026-09-24: STATED BEFORE THE FIRST WINDOW, NOT REFUSED**
Driven: a `DOM_ENABLED=0` child of a 160-window parent restored 8 domains with 0 refusals and 0
warnings, then sent `did=0` for every window — and 0 is a real id, so the parent's surviving domain 0
received every window's memory source and token prior. **Ruling:** a startup warning naming the count
and what `did=0` does to the restored partition. **Why not WORLD's refusal:** `WORLD_ENABLED=0` builds
a NULL world with nowhere to load into; DOM builds the identical `Partition` on both arms, so the
restore is sound, and `DOM.census` already prints `partition_off` for exactly this configuration
("A run with DOM_ENABLED=0 that restored domains from a checkpoint still has a live-looking partition
and is still off") — the tree already treats it as a run to report, not to refuse. Refusing would
remove an ablation-from-checkpoint that runs. **Rejected:** skipping the DOM restore when disabled
(discards trained state a later `DOM_ENABLED=1` resume of the same child would want).

### Q-RUN-9 — a resumed clock restarted `backwards`, `opt_steps` and every cadence seed at zero — **RESOLVED 2026-09-24: THE CLOCK IS SEEDED FROM OPT'S RESTORED COUNTS, THE GATE SCHEDULE IS CHECKPOINTED, AND THE ACCUMULATION INVARIANT COUNTS MULTIPLES CROSSED**
Three defects, one boundary. **(1) Accumulation phase.** `RunClock.note_backward` decided a step with
`accum_due(clock.backwards)` and `OPT.maybe_step` re-decided it with `accum_due(st.n_backward)`; the
clock restarted at 0 while OPT restored the parent's count, so a parent saved partway through an
accumulation put the two gates out of phase for the whole child. Driven at `OPT_ACCUM=4`: a 30-window
parent (backward=30, step=7) resumed to 60 took **0** optimizer steps in 30 backward passes, then
`OPT.counters` raised at R — which ran before the final save, so no checkpoint was written. Any
epoch whose backward count is not a multiple of accum ends misaligned. **Ruling:** `new_clock` gains
two DEFAULTED keywords, `resume_backwards` and `resume_opt_steps`, which the root fills from the
restored `OptState.n_backward` / `opt_step`; the loop compares the clock's backward count with
`OPT.scaled_backward`'s every flush and raises if they ever differ; `OPT.counters` measures the steps
due since the resume as `floor(n/k) − floor(base/k)` (the multiples of accum crossed), not
`floor((n − base)/k)`, which differs exactly on a misaligned base and raised on a correct schedule;
the parent's lost partial accumulation is counted as `opt.ckpt.partial_accum_dropped`
(`n_backward % accum` at load — no checkpoint carries `.grad`; **the parent's accum**, which
`OPT.state_dict` records since a later 2026-09-24 fix, with the live accum as the fallback for older
checkpoints, flagged by `opt.ckpt.partial_accum_basis` 0 — it was the live accum, so a parent at
accum 1 with nothing pending resumed at accum 4 reported 2 dropped; the live remainder is kept as
`opt.ckpt.first_step_short_by`, the passes the child's first step lacks); and the loop takes the final save
before re-raising a failed R stage. After: the same child took 8 steps (7 → 15), printed
`opt.accum.invariant: FIRED (60 // 4 - 30 // 4 vs 8)` and `partial_accum_dropped 2`, and wrote its
checkpoint. `opt_steps` in the report is now a run total, like `step`, which is what
`RunClock.counters`' horizon comparison always assumed. **(2) Cadence schedule.** `Cadences.due`
seeds lazily at the resumed step, so every gate first fired a full period late on the child
(`dom.manage` at 261 instead of 201 on a 160-window parent, `dom.rekey` at 361 instead of 201) and a
run resumed in chunks shorter than a period never managed at all. **Ruling:** RUN entry points
`Cadences.state()` (a C row, written as `payload['RUN']['cadences']`) and
`Cadences.restore(state)` (an ASSEMBLY_ORDER restore row after `new_cadences`), which restores the
keys still declared and treats a missing `'RUN'` key — every pre-fix checkpoint — as "seed lazily, as
before". The ledger's checks and fires become run totals, as MEM's and TOK's restored counters
already are. **Rejected:** letting `OPT.maybe_step` alone decide and changing `note_backward` to
record its answer (the same fix with a moved signature and a reordered B row, and the per-flush
cross-check gives the single-decision guarantee without it); refusing a misaligned resume at compose
(refuses the natural end-of-epoch checkpoint at any `OPT_ACCUM > 1`); flushing the partial
accumulation at save time (takes a step the parent's own invariant does not allow); reading
`Cadences`' private slots from `spine/loop.py` (the root builds the payload through declared entry
points only).

### Q-RUN-10 — `max_windows`, a finished resume and a mid-epoch resume each trained unrequested or repeated windows — **RESOLVED 2026-09-24: `max_windows` COUNTS THIS PROCESS'S WINDOWS AND STOPS BEFORE A ROLL; A FINISHED RESUME IS REFUSED; A MID-EPOCH RESUME KEEPS THE DECLARED REPLAY AND WARNS. THE REPLAY IS SUPERSEDED BY Q-RUN-16 (2026-09-26) FOR EVERY CHECKPOINT CARRYING THE SEGMENTATION LOG; IT REMAINS FOR ONE THAT PREDATES IT**
**`max_windows`.** It was compared with the absolute `tick.step`, which a resume restores, so any
resume given `--max-windows N` ≤ its restored step trained exactly one window (driven: a 60-window
parent resumed with `--max-windows 40` printed `61 windows, 1 flushes`), and the test sat after the
epoch roll's `continue`, so a stop landing exactly on a boundary drew the next epoch and trained one
window of it (driven: `max_windows=157` on a 157-window epoch ran 158 and saved one window into epoch
1). **Ruling:** it is a DRIVER argument about the process it is handed to, so it counts the windows
THIS call trains, and it is tested before the roll — a stop on a boundary leaves the clock at the new
epoch with `in_epoch` 0, so the final checkpoint is a true boundary checkpoint. `RunResult` gains
`windows_here`, and `run.py`'s banner prints run totals (windows, optimizer steps, epochs) apart from
this process's (windows trained, flushes, the rate) on a resume. **Rejected:** keeping the absolute
reading and documenting it (every chained resume would need arithmetic on the parent's step to
express "N more").
**A finished resume.** The loop's first act is `clock.advance()`, so a resume from a completed run
trained one unrequested window and overwrote the final checkpoint at step+1 (driven: a finished
157-window parent resumed as `158 windows, 1 flushes, 1 optimizer steps`, `1 checkpoint(s) written`),
while `RunClock.counters` published `epochs_target` for exactly this question. **Ruling:** refused at
compose, after the `epoch0` row, the way `RUN_EPOCHS=0` is — the refusal names the epoch reached and
says to raise `RUN_EPOCHS` — and `loop.run` raises on the same predicate for a System built another
way. **Rejected:** skipping straight to the report with zero windows (every R surface would be asked
about a run that made no passes, and the add-an-area continuation that forgot `RUN_EPOCHS` would exit
0 with a warning — the goal-B case where a silently empty child costs most).
**A mid-epoch resume.** `train/api.py::new_clock` DECLARES that a mid-epoch resume replays its epoch
from window 0, and that stays: restoring the cursor needs the child's segmentation to cut the epoch
where the parent's did, and it need not — the child tokenises the redrawn stream with the SAVED
vocabulary, which can hold merges minted after the epoch began, so a saved window index can name
different bytes. The byte-cursor remap Q-RUN-8's option (a) describes is the route when it is built.
What was undeclared is that the operator heard nothing: a 120-window parent of a 211-window epoch
resumed to 331 windows, trained windows 0..119 twice and ran 120 optimizer steps past a 211-step
horizon, silently. **Ruling:** the loop checkpoints the clock's position (`RunClock.counters`' new
`in_epoch` / `windows_in_epoch`, under `payload['RUN']['clock']`), and compose WARNS on a mid-epoch
resume with the windows it replays and the optimizer step it will end near against the OPT horizon; a
pre-fix checkpoint at epoch 0 is still exact (`in_epoch = step`), and at a later epoch it is warned as
unknown. **Rejected:** seeding `in_epoch` from the saved index now (see above); refusing mid-epoch
resumes (every `CKPT_EVERY` checkpoint is one, and the replay is a declared, working behaviour).

### Q-RUN-16 — a mid-epoch resume replayed its epoch, since the child cut its stream at a later vocabulary than the parent — **RESOLVED 2026-09-26 (03b S0b): THE CHECKPOINT CARRIES THE EPOCH'S SEGMENTATION LOG AND THE LOOP'S CARRIED STATE; A RESUME REBUILDS THE PARENT'S EXACT STREAM AND CONTINUES. ⚠ SIGNATURE MOVES: `RUN.new_clock(..., resume_in_epoch=0, resume_windows_in_epoch=None)`, `TOK.tokenize(..., view=None)`, `TOK.splice(..., view=None)`; +1 ENTRY POINT `TOK.view_of`**

**What stood in the way (Q-RUN-10).** The child tokenised the redrawn stream at the SAVED vocabulary,
which can hold ids minted after the epoch began (TOK mints every `TOK_GROW_EVERY`, acts every
`TOK_RETOK_EVERY`), so the saved window index named different bytes; and the critic of 03b found the
same shape blocking any "re-segment at resume" rule. **The ruling is 03b's option (b): resume at the
last act's recorded state.**
- `payload['LOOP']['seg_log']` is the epoch's log: its first cut and every act's splice, each with the
  match table's VIEW (`TOK.view_of`: `(size, retired)`) and the BPE-dropout stream's state just before
  it, plus that stream's state at the save. `TOK.tokenize(view=)` / `TOK.splice(view=)` cut at a
  recorded view by rebuilding the table from the append-only `id2bytes[:size]` minus the view's
  retirements -- not by filtering today's `seq2id`, which `_retire` pops.
- compose replays the log at the 'segment' row, refuses if the rebuilt epoch length differs from the
  saved one, and opens the clock at the saved position through `new_clock`'s two keywords; the
  'epoch0' row then does not call `begin_epoch`, which would zero the cursor.
- `payload['LOOP']['carried']` holds what the loop reads at the very next window -- the last flush's
  per-window losses (`System.novelty`), the pending Due, the shift stamps, MEM's probe and pressure,
  the live domain count, SIG's boundary run, FAB's manage losses -- mirrored before every save.
- DOM's checkpoint gains `position` (the current domain, the run, its signature, a pending switch, the
  boundary clocks at birth); compose passes it only to a continuing resume, and any other resume
  re-arms as before.
- OPT: a checkpoint with a horizon revision log is priced on its saved build-time horizon plus the
  log (Q-OPT-10), not on the resumed build's post-act horizon.
**Driven:** `tests/test_continuation.py` S5 -- a run saved at window n1 and resumed for n2 windows
reproduces the uninterrupted run's losses EXACTLY with no act, with a save between a mint and the
next act, with a save after an act, and at `TOK_DROPOUT` 0.1. A checkpoint without the log still
replays and is warned (`tests/test_resume_clock.py` C9).

### Q-MEM-13 — stored memory contexts stayed spelled in the vocabulary that wrote them — **RESOLVED 2026-09-26 (03b S0b): `MEM.maintain(..., remap=None)`, A ROOT-COMPOSED RE-CUT. ⚠ A SIGNATURE MOVED; `TOK.Vocabulary.decode` LEAVES `DEFERRED_ENTRY_POINTS` (24 → 23)**
A stored context is a fixed-width window of token ids. Ids never change meaning (the vocabulary is
append-only), but after an act the same text is spelled in newer, longer tokens, so a context written
earlier encodes to a key in a different part of key space than the query the model now forms for the
same text -- the archive measured 82.3% of contexts stale after one growth step. The act records its
view as `System.mem_remap` (data, so a save before the next flush carries it in `loop_carried`); the
next flush builds the re-cut (`spine/loop.py::_mem_remap_fn`: strip the 0 pad, `TOK.Vocabulary.decode`,
`TOK.tokenize(view=)` with no labels, which counts `tok.segment_remap`) and hands it to `MEM.maintain`,
which keeps the last `key_win` ids, left-pads with 0 as the write path does, leaves the stored target
id alone (it names the same bytes), and retakes the rekey snapshot so the keys follow. MEM may not
import TOK (O10), which is why the callable is the root's. Counters: `store.n_remap_events`,
`store.n_remapped_entries` (ABSENT until a remap). Driven: `tests/test_continuation.py` S6 (a re-cut
decodes to the same bytes in the newer token; an act in a run remapped 448 entries).

### Q-OPT-10 — revising the LR horizon mid-run — **RESOLVED 2026-09-26 (03b S0b): `OPT.revise_horizon`, LR-CONTINUOUS, AN APPEND-ONLY CHECKPOINTED LOG; IT REOPENS Q-OPT-5's (b) AND ANSWERS BOTH OF ITS GROUNDS. +1 ENTRY POINT**
The act re-measures the run (minting merges bytes, so it shortens), and a horizon fixed at build
would then overshoot -- Q-OPT-5's under-anneal inside every run. Q-OPT-5 refused revision on two
grounds. **Moving target:** the revision is an append-only `st.horizon_revisions` log of
(opt_step, run_steps), checkpointed; the build-time `Horizon` is never rewritten and a resume rebuilds
the same map from the same base. **History (the old `_project` jumped and latched):** each revision is
one continuous re-map anchored at the current step -- `_effective_step` prices step s at
e0 + (s − a)·(R − e0)/(R' − a) on the build-time horizon -- so lr(now) is unchanged and the cosine ends
at the floor at the revised end. Inert, with `opt.horizon.revise_inert`, when more than one restart
cycle was fitted or `lr_sched` is 'none', or `OPT_HORIZON_REVISE` is False. Driven:
`tests/test_continuation.py` S2.
*2026-09-26 (Proposal 05 §8 1.4, Q-OPT-12):* the revision has an off arm, `OPT_HORIZON_REVISE`
(default `True`). At `False` `revise_horizon` is inert in-run and counts it twice over —
`opt.horizon.revise_inert` = 1 and `opt.horizon.revise_declined`, one per declined revision, seeded
at 0 by `build` on that arm only — and the run ends above the floor by Q-OPT-5's under-anneal, which
is the arm's measured cost. **`load_state`'s resume revision on a logged parent is not gated by the
lever** (C01): the rate a resume starts at is `OPT_LR_CONTINUE`'s. `counters()` now carries Gate
`opt.horizon.revise`, which prints the inert reason this entry promised and nothing printed. Driven:
`tests/test_continuation.py` S2b and S8, `tests/test_lr_continue.py` L4.
*2026-09-27 (build 1.4's review):* a declined revision is now KEPT — `st.horizon_declined`,
checkpointed, never read in-run — and counted only where `True` would have logged one (the no-op
test first, at the effective batch). A continued run applies the declines to its log; a crash-resume
of the `False` run keeps them declined and its horizon as built. See Q-OPT-12's correction.

### Q-OPT-12 — the rate a continued run starts at, and an off arm for the in-run horizon revision — **RESOLVED 2026-09-26 (Proposal 05 §8 1.4; NEW-05, C01, TREE-OPT_HORIZON_REVISE-LEVER): `OPT_LR_CONTINUE` ∈ {as_logged, floor, plateau, rewarm, regulated}, DEFAULT 'as_logged' = TODAY'S PRICING, BIT-IDENTICAL; `OPT_HORIZON_REVISE` (DEFAULT True) IS IN-RUN ONLY. ⚠ FIVE NEW LEVERS, FIVE CENSUS AMENDMENTS; 'regulated' REFUSED (NotBuilt, NEW-04); `OPT_BORN_CLOCK` DEFERRED (C02, §8 4.2). NO SIGNATURE MOVES, NO WIRE**
The number is Q-OPT-12 because 03b and the register already reserve Q-OPT-11 for the AUD
codec-schedule ruling. **What was asked.** A continued run — a resume whose horizon differs from its
parent's, the post-training session of NEW-05 — started at a rate the parent's SHAPE set: a parent
with a revision log resumed at the floor for good once it had finished its run, and a no-log parent
resumed with no ramp at the cosine for its step E against the resumed build's horizon (about 0.48 of
peak at the 756 KB CPU shape, 0.22 at the 3.78 MB whole-epoch shape, the floor only for a full 20 MB
epoch;
`verify/emp3/k0_epoch_child.py`). And the in-run revision (Q-OPT-10) had no off arm, while the draft
that added one gated `load_state`'s resume revision as well — which would have switched a continued
act-parent from the floor to the no-log re-pricing, about 0.37-0.45 of peak at 3.78 MB, without anyone
asking for a new rate (C01).

**The ruling, as built.** Two levers for two questions, in `src/opt/levers.py` section 6.
* **`OPT_HORIZON_REVISE`** (U.FLAG, default `True`): in-run only; see the dated note on Q-OPT-10.
* **`OPT_LR_CONTINUE`** (U.NAME, default `'as_logged'`). **The session boundary is where `load_state`
  already re-prices, and nowhere else:** a horizon that differs from the checkpoint's
  (`opt.ckpt.horizon_changed`), or a new revision appended to a logged parent. Every other resume
  continues the parent's schedule exactly, under every regime. At a boundary, with j = step − anchor
  (the anchor is the resumed step, so the first step re-priced is anchor + 1), W = `OPT_LR_CONT_WARM`
  (default 1000, the tree's warmup; refused below 0), s0 = the rate the restored base optimizer holds
  over peak (the parent's last applied rate) and f = `lr_min_frac`:
  - `'as_logged'`: no regime. The rate is today's function of the horizon and the log, bit-identical,
    and every `LoadReport` reason is the one `load_state` returned before this entry.
  - `'floor'`: f from the first resumed step.
  - `'plateau'`: s0 + (t − s0)·j/W while j < W, then t, held; t = `OPT_LR_PLATEAU` (default 0.25,
    provisional; domain [0, 1]).
  - `'rewarm'`: the same ramp to t = `OPT_LR_REWARM` (default 0.5, provisional; domain [0, 1], which
    admits the 1.0 arm), then f + (t − f)·(1 + cos πp)/2 with p running 0 → 1 from anchor + W to the
    session end — the resumed build's run_steps, at least anchor + W + 1. The session's own mid-epoch
    acts re-map that decay LR-continuously through the same `_effective_step` map Q-OPT-10 uses; under
    'floor' and 'plateau' they are logged and move nothing.
  - `'regulated'`: declared and **not built** — it sets each session's plateau from the previous
    session gate's margin, and that gate (NEW-04, §8 4.4) does not exist. `OPT.build` refuses it on
    every run with `spine/gate.py::NotBuilt`, message starting `OPT_LR_CONTINUE='regulated'` and naming
    NEW-04 — the `FAB_HOP_MODE` / `LM_COMPOSE` / `MEM_KEY_SRC` precedent, never a silent fallback.
  The shift re-warm still attenuates a regime (§8 4.2 runs its arms in the continuation harness) and
  the floor clamp still bounds it; the restart damping and the envelope do not apply, because past the
  anchor no as-built cycle is priced. At `OPT_LR_SCHED=none` a regime is inert and counted
  (`opt.continue.inert`), the revise_horizon precedent.
* **Frozen at the boundary, checkpointed.** A regime is written into `OptState.continuation` — regime,
  anchor, start_frac, target_frac, warm, end, rev_base — which `state_dict` carries and `load_state`
  restores (an older checkpoint restores None). A resume at the parent's horizon keeps it, and so
  (since 2026-09-27, see the correction below) does a continuing mid-epoch resume whatever the
  resumed build projects, so a session saved and resumed continues its closed form exactly and never
  re-reads the lever; an
  operator who asks for another regime there gets the recorded one, and the report says so in words.
  A boundary under `'as_logged'` clears any record a parent carried.
* **No phantom restart.** Anchoring a regime clears `lr_prev` (counted in `opt.ckpt.lr_prev_cleared`),
  as the horizon-changed branch already did for its own boundary, and `maybe_step` does not consult
  the restart detector on a step a regime priced: a regime's ramp is not a cosine wrap, and stamping it
  `restart=True` would feed `FAB.grow_check` a self-inflicted shift. `opt.restart.wraps` still counts
  the as-built horizon's cycle-index advances under a regime; on a continued run read it as a fact
  about a horizon the rate no longer follows.
* **Said on every resume.** The returned ledger carries `opt.continue.regime` — a string label, the
  anchored record's regime or `'as_logged'`, ABSENT on a fresh run and never written into
  `st.counters` — and one `opt.continue:` report line: the asked and the in-force regime, the boundary,
  the anchor, start, target, ramp and end, the steps priced, and the first resumed step's rate as a
  fraction of peak. Counters: `opt.continue.boundary` (1 or 0 on every restore), `opt.continue.priced`
  (seeded 0 when a regime is anchored) and `opt.continue.inert` — ABSENT on a fresh run, so a default
  run's ledger gains no key. **The session end is a projection:** the resumed build's horizon is this
  epoch's length × `RUN_EPOCHS`, the same projection 'as_logged' prices against, so a parent whose
  epochs were longer than the child's can leave it at or before anchor + W; 'rewarm' then has no decay
  phase until a child act revises the end, and the report line says so. Which session length the
  arms should use is a GPU question (§8 5.2), not a CPU one.
* **`OPT_BORN_CLOCK` is deferred to §8 4.2 (C02) and is not declared.** A per-group warm-up clock for
  capacity born after the anchor needs a born-row signal OPT may not import (O10) and no wire carries,
  a per-ROW rate inside one tensor that AdamW's per-group lr cannot express, and checkpointed per-group
  clocks; §8 4.2 builds it with `FAB_LR_OWN` scope 'newborn'. A refuse-only lever would have cost a
  census amendment for nothing.
**Bit-identity.** `st.continuation` is None on every fresh run and under 'as_logged', and `_schedule`
enters the regime branch only when it is not, so no float operation on the existing path moved;
`build` seeds no new counter at the defaults. `tests/test_baseline.py` reproduces the d32e2ce fixture
(80 losses, 244 integer counters, no new counter on a fresh run). The fixture has no resume, so the
continued run was compared against the tree before this entry (148786f), in-process at the test base
(`DATA_STREAM_BYTES=60000`), for four children at `RUN_EPOCHS=2 DATA_RESAMPLE=1` over 40 windows each —
a 12-window no-log parent's boundary child, a whole-epoch no-log parent's, a whole-epoch act parent's
(`TOK_GROW_EVERY=30 TOK_RETOK_EVERY=40`, which resumes at the floor: 1.0e-4), and a 135-window act
parent resumed mid-epoch (the log branch's append): loss curves, `lr_at` over every child step,
`lr_prev`, the `LoadReport` reason, the revision log and every integer OPT counter other than the new
`opt.continue.*` are identical.
**What CPU establishes:** operation only — each regime starts at and follows its closed form, the
counters fire, a session resumes exactly. Which regime a post-training session should use is §8 5.2's
GPU question ([OWNER] O6). Driven: `tests/test_lr_continue.py` L1-L8, `tests/test_continuation.py` S2b,
S8 and S5's regime case, `tests/test_prose_guards.py` G2.
*2026-09-27 (build 1.4's review; six confirmed findings, all fixed). ⚠ A SIGNATURE MOVED:
`OPT.load_state` gains one defaulted keyword, `continuing=False` (§7). No lever, no wire, no entry
point.*
1. **C01 through the parent (major).** An act-parent at `OPT_HORIZON_REVISE=False` declined its
   revisions and checkpointed no log, so its continued child — at every default — took the no-log
   re-pricing. Driven through compose (`TOK_GROW_EVERY=30 TOK_RETOK_EVERY=40`, a whole epoch, then
   `RUN_EPOCHS=2 DATA_RESAMPLE=1`): 0.5503 of peak against 0.0500 for the same parent at `True`, both
   labelled 'as_logged'. `revise_horizon` now keeps each declined pair in `st.horizon_declined`
   (checkpointed, never read in-run), and `load_state` takes such a checkpoint through the log branch
   on its *would-be* log — the log with the declines merged in by step. Where that resume re-prices,
   the declines join the child's log before the resume revision (`opt.horizon.declined_applied`), so
   the child prices as the logged parent it would have been: 0.0500 after the fix, whichever flag
   either run has. A ramping regime still starts from the child's own parent's last rate — continuity
   with what the parent's in-run arm left — on the same log and target. Where the resume does not
   re-price, the run continues on its unrevised horizon with the declines carried, which also makes
   the `False` run's own crash-resume exact: it used to take the resumed build's post-act horizon as a
   changed one (driven: 317 → 315 steps after one act, 0.7176 → 0.7140 of peak at the first resumed
   step). The alternative offered, accepting the parent route in writing, was not taken: this build's
   known answer is that the lever leaves a continued run's LR unchanged, and C01 names exactly this
   parent.
2. **A crash-resume of a session re-anchored it (major).** "Re-priced" cannot tell a crash-resume from
   a new run length: the resumed build's horizon is this epoch's length × `RUN_EPOCHS`, and acts and
   `DATA_RESAMPLE=1` move this epoch's length under a run that changed nothing. Driven at 117f9b6's
   OPT with identical settings: a 'rewarm' session saved 200 windows into its epoch 1, after one of
   its own acts, was re-anchored at step 517 (the log branch appended 592 against the log's 613) and
   ramped 0.1907, 0.2069, 0.2232 of peak where the uninterrupted session decayed 0.1721, 0.1698,
   0.1675; a session with no act, saved 30 windows into epoch 2 of three, met 465 against its 474 in
   the no-log branch and was re-anchored the same way. OPT's horizons cannot separate the two cases,
   and keeping a record whenever the log branch appends (the fix offered) would also have stopped a
   finished logged session from ever starting another. So the root says which resume it is:
   `spine/compose.py` passes `continuing=System.resume_pos is not None`, the continuing mid-epoch
   resume that DOM's stream position already crosses on. A continuing resume of a checkpoint that keeps
   its own horizon — a session's record, or the off arm's declines — is restored **verbatim**: the
   horizon, log, declines and record come back as saved, nothing is appended, no regime is anchored,
   no lever is re-read, and the resumed build's projection is counted where it was held back
   (`opt.ckpt.horizon_held`: 0 when it agreed, else its run_steps). Every mid-run save (periodic,
   `SIGUSR1`, a stop) is mid-epoch, so a crash-resume is continuing; a continued run starts from a
   finished run's final checkpoint, at an epoch boundary, and is still a session boundary. After the
   fix both drives are exact, rates and losses. A checkpoint with no record and no declines — every
   run at the defaults — is never held, so 'as_logged' keeps its log-branch append on a continuing
   resume: the small LR-continuous inexactness it already had at 148786f, not repaired here.
   Residuals, stated: a crash-resume from an epoch-boundary checkpoint is not continuing and takes the
   old test; and a continuing resume never re-anchors a session in progress, so raising `RUN_EPOCHS`
   mid-session continues the recorded session (a checkpoint with no record, continued mid-epoch at a
   larger `RUN_EPOCHS`, still starts one).
3. **The floor Gate ignored a regime (minor).** A 'plateau' or 'rewarm' target below `lr_min_frac`, or
   a ramp from a parent stopped inside its warm-up, is clamped by the floor, and Gate `opt.lr.min_frac`
   read UNREACHABLE beside the count while `_stale_note` blamed it on a configuration no longer in
   force (driven: `OPT_LR_PLATEAU=0.01`, `floor_applied=50`). A regime whose target or first ramp rung
   is below the floor is now a reachable route, and both reasons name it. The ramp still starts from
   the parent's true rate, and the one discontinuity a regime has is now stated in `_continued` and
   here: **a parent below the floor rises to it at the boundary** (driven: 0.02 of peak at step 2 of a
   100-step warm-up, then 0.05, 0.05, 0.05 under 'plateau'), counted in `opt.lr.floor_applied`.
4. **A no-op call counted as a decline (minor).** The `False` arm returned before the step conversion,
   so at an effective batch above 1 a window change that rounds to the same step count read
   `revise_declined=1` (driven: `OPT_BATCH_WINDOWS=4`, 200 → 201 windows, 50 steps both). The
   conversion and the no-op test now run first, against the log the run would hold at `True`.
5. **`opt.horizon.revise_inert` reached a child that cannot be inert (minor).** It is dropped on
   restore unless the live configuration can be inert — `OPT_LR_SCHED=none`, more than one cycle, or
   the off arm, recognised by the counter `build` seeds for it, so `load_state` still reads no
   `OPT_HORIZON_REVISE`.
6. **The label did not say which pricing applied (minor).** A second label, `opt.continue.pricing` —
   'logged parent: floor', 'logged parent: re-mapped', 'no-log parent: re-priced', 'continues',
   'record' or 'flat (OPT_LR_SCHED=none)' — and the `opt.continue:` line names the branch in words
   (CONTRACT-Q-DATA-7). It reads `opt.ckpt.log_at_load`, the log's length once the restore settled the
   horizon (0 = a no-log resume).
Three new counters, each describing its own restore, never restored from a parent and ABSENT on a
fresh run: `opt.ckpt.horizon_held`, `opt.horizon.declined_applied`, `opt.ckpt.log_at_load`. **Defaults
are bit-identical:** at `OPT_HORIZON_REVISE=True` nothing is declined, and a checkpoint with no record
and no declines takes both horizon branches as before. Driven: `tests/test_lr_continue.py` L9-L12 and
L7's three compose-level checks.

### Q-RUN-17 — instruments for the mid-epoch act's secondaries — **RESOLVED 2026-09-26 (Proposal 05 §8 1.3; PENDING-S0b-SECONDARIES, 03b-16.26, 03b-16.33): SIX READINGS, ONE NEW `RunResult` FIELD (`flush_bytes`) AND ONE DRIVER FLAG (`run.py --flush-bytes`). NO SIGNATURE MOVES, NO LEVER, NO WIRE; A DEFAULT RUN REPRODUCES THE BASELINE FIXTURE**
The retok fleet (Proposal 05 note retok fleet (2)) reports secondaries beside its ship rule, and 03b
named them before any of them could be read: the FAB growth blackout's share of windows, how long a
minted id waits for the re-segmentation that brings it into the stream, the act's wall cost, bytes
per token over the re-segmented tail (the SIG-width gauge), and bytes per flush so prequential
bits/byte can be split by phase. Each is now read where its owner sees it:
- **`fab.blackout_windows`** (FAB, `fabric/api.py::grow_check`): the WINDOWS whose flush's growth
  check found the stamp's cooldown open, credited as (max(previous check, stamp), this check], so a
  flush of several windows counts all of them and a window before the stamp never counts.
  `fab.growth_blackout_suppressed.*` still count the refused ASKS. ABSENT at `FAB_ON=0`, `FAB_GROW=0`
  or `FAB_COOLDOWN` ≤ 0, where no stamp can block growth, and until the first stamp arrives, where
  the `fab.growth_blackout` Gate reads UNREACHABLE; PRESENT-and-0 is a stamp no later check inside
  its cooldown reached (corrected 2026-09-27, below: it was seeded on every check and read
  PRESENT-and-0 beside that UNREACHABLE). `state_dict` carries the previous check's step
  (`checked_at`); a checkpoint written before the key existed counts from the stamp. **This is 03b's
  `fab.cooldown_windows`, under the one name the register uses; that name is retired.**
- **`tok.mint_wait_windows` and `tok.mint_waited`** (in `vocab.counters`, seeded and written by the
  ROOT, the only place that sees both an id's birth in `TOK.mint_burst` and the act or epoch roll
  that re-segments it): the summed windows each minted id waited, and how many ids the sum covers.
  A retired id is dropped uncounted (the cut did not bring it into the stream). The open waits
  (`mint_open`, [id, born] pairs) cross a save in `payload['LOOP']['carried']`, so a continuation
  closes its parent's waits. ABSENT unless `TOK_MODE` is online with `TOK_GROW_EVERY` > 0 and either
  `TOK_RETOK_EVERY` > 0 or an epoch roll lies ahead.
- **`loop.act_seconds` and `loop.act_remap_seconds`** (the loop's flush books, beside `loop.acts`):
  wall seconds spent in mid-epoch acts, and the part spent re-cutting MEM's stored contexts inside
  `_mem_remap_fn`. FLOATS, so `tests/test_baseline.py`'s integer channel never compares them; ABSENT
  wherever `loop.acts` is: at `TOK_RETOK_EVERY=0`, and off `TOK_MODE=online`, where TOK raises no
  retok Due (corrected 2026-09-27, below: the mode test was missing).
- **`tok.bpt_tail`** (TOK, `TOK.splice`): A READING, not a count: bytes per token over the tail the
  last splice cut, at the vocabulary as it then stood (`derive.bytes_per_token`, six places). ABSENT
  until an act cuts a tail; a resume's log replay splices again and writes the same value. The act's
  warning line prints the tail's bytes/token before and after and against the build-time value SIG's
  width was derived from (03b-16.33's trigger).
- **`RunResult.flush_bytes`** and **`run.py --flush-bytes PATH`**: the bytes each flush's windows'
  targets cover, one entry per `--loss-curve` entry, summing to `loop.bytes_scored` (with
  `never_backward` 0). A separate file, because `tests/test_baseline.py` and `gpu_world.sh` read
  `--loss-curve` as a flat list of floats. A driver argument, not a lever: it changes no computation.
**What CPU establishes:** operation only. `tests/test_baseline.py` reproduces the fixture recorded at
d32e2ce (80 losses, 247 integer counters; the new counters are listed as new). A cross-commit
comparison against the base commit (scratch `stage1/actpath_trace.py`: cases with acts, dropout,
`OPT_BATCH_WINDOWS=4`, two epochs, and resumes after an act and between a mint and an act) gives
identical losses and parameter hashes. Known answers: `tests/test_continuation.py` S5 (open waits and
the blackout split across a save) and S9 (each reading fires, equals its recomputation, and is ABSENT
where disarmed), `tests/test_tok_dom_cap.py` T4-T5, `tests/test_fabric_internals.py` I11. What the
readings say about retok cadences is the GPU fleet's question (§8 2.1).
**CORRECTED 2026-09-27 (build 1.3's review) — the act's books and the blackout count are ABSENT
where they cannot fire, and a continuing resume's double count is recorded.** (i) *The act's books.*
`spine/loop.py::run` seeded `loop.acts`, `loop.acts_noop`, `loop.act_seconds` and
`loop.act_remap_seconds` on `TOK_RETOK_EVERY` > 0 alone. `TOK.on_window` raises a retok Due only at
`TOK_MODE=online` (`retok = bool(online and _due(...))`) and seeds `tok.due_retok` on that arm alone,
so at `TOK_MODE=fixed` or `bytes`, with the shipped `TOK_RETOK_EVERY=3000`, all four read
PRESENT-and-0 ("armed, did not fire") beside `tok.due_retok` ABSENT. Driven: 60 windows at
`tests/test_continuation.py`'s base, on both modes. They are now seeded on TOK's own predicate,
`TOK_MODE=online` and `TOK_RETOK_EVERY` > 0, which is the mode test the mint wait already made. The
shipped arm is online at 3000, so a default run seeds the same keys, and none of them is in the
baseline fixture. (ii) *The blackout count.* `fab.blackout_windows` was seeded on every check at
`FAB_GROW` on and `FAB_COOLDOWN` > 0. A run that no stamp reached (the retok fleet's k0 control, and
`TOK_MODE=fixed` or `bytes`, at `RUN_EPOCHS=1`) therefore read it PRESENT-and-0, while the
`fab.growth_blackout` Gate beside it printed UNREACHABLE ("0 notifications means the blackout cannot
open at all"). The ruling above answered that with `fab.shift_notifications`; DID IT FIRE puts the
answer in the key itself. The key is now seeded at the first check that holds a stamp
(`pop.growth['shift_seen']`), which is where the Gate turns reachable. `state_dict` carries the stamp
and the counters carry the key, so a resumed child agrees with its parent. `gpu_world.sh` reads an
ABSENT key beside a present `fab.shift_notifications` of 0 as 0 blacked-out windows, so an arm's
blackout share still averages every seed, and a seed that never stamped reads the 0 it read before.
(iii) *A continuing resume counts the replayed acts twice. Recorded here, not repaired.*
`spine/compose.py` runs `TOK.restore_vocab`, which puts the parent's counters back, before
`_replay_segmentation` rebuilds the epoch's segmentation from the log. The replay's `TOK.tokenize` at
the recorded view counts only in `tok.segment_view` (Q-TOK-15). Its `TOK.splice` at a view counts
as a live act does: `tok.retok` and `tok.retok_mid_epoch` +1 per replayed act, `tok.byte_fallback`
plus the replayed tail's fallbacks, and at `TOK_DROPOUT` > 0 `tok.dropout_skip` plus the replayed
draws' skips. By the same code path, not driven, `tok.retok_empty_tail` also counts again for an act
that found no tail. So every act the parent took before its save is counted twice in the child. Driven
on `tests/test_continuation.py` S5's shapes (the uninterrupted run against the child):
`after_act` (`TOK_GROW_EVERY=30`, `TOK_RETOK_EVERY=40`, saved at 135, resumed for 25) reads
`tok.retok` 1 against 2, `tok.retok_mid_epoch` 1 against 2 and `tok.byte_fallback` 33900 against
46596. The same shape at `OPT_BATCH_WINDOWS=4` (saved at 136) reads 1 against 2 and 33699 against
46194. `dropout` (`TOK_DROPOUT=0.1`, three acts before the save) reads 3 against 6, 76346 against
129084, and `tok.dropout_skip` 6475 against 11003. A save before the first act (`mint_then_act`)
reads equal, because nothing is spliced in the replay. The losses, the segmentation, every reading
this ruling added, and `tok.bpt_tail` (a reading the replay rewrites with the same value) are exact.
No decision reads the doubled keys. Two repairs are possible: `TOK.splice` at a view could count
apart, as `tokenize` does since Q-TOK-15, or the replay could run before the restore. Either one
changes TOK's counter contract, which this build does not take on.
(iv) Q-RUN-15 (a) had an undated sentence on `RunResult.flush_bytes` inside its 2026-09-24 ruling.
It is removed, and this ruling is where the field is documented. 03b's six other mentions of
`fab.cooldown_windows` now name `fab.blackout_windows`. **Driven:** `tests/test_tok_dom_cap.py` T2
(the four books ABSENT at `TOK_MODE=fixed` and `bytes`), `tests/test_fabric_internals.py` I11 (ABSENT
with no stamp; PRESENT-and-0 at a stamp that no later check reached), `tests/test_continuation.py` S9
(ABSENT at `TOK_RETOK_EVERY=0`, beside `fab.shift_notifications` 0 and the Gate's UNREACHABLE), and
`tests/test_gpu_world.py` F4 (a k0 seed with the key ABSENT reads 0.0%).

### Q-DOM-5 — DOM's competence was a per-token level, so every act moved it — **RESOLVED 2026-09-26 (Proposal 05 §8 1.2; register TREE-S0b-LEVELS, C12; 03b 0b.5): `DOM_LEVELS`, DEFAULT ON — THE ROOT HANDS `note_competence` BITS PER BUILD-TIME TOKEN; OFF IS TODAY'S PER-TOKEN UNIT, BIT FOR BIT. ⚠ ONE NEW LEVER, A CENSUS AMENDMENT; A DEFAULT RUN'S COMPETENCE VALUES CHANGE. NO SIGNATURE MOVES, NO WIRE**
**What was asked.** `DOM.note_competence` folds each window's mean cross-entropy / ln 2 into the
domain's EMA and the population's `comp_glob`: a level PER TOKEN, since the mean runs over the
window's `ctx` targets. A mid-epoch act re-spells the unconsumed tail in longer tokens, so the same
text costs more bits per token after it than before, and every domain's EMA shifts by the act's
bytes-per-token ratio — about 1.47x across a bytes-to-build splice (`tests/test_levels.py` L3 reads
1.4656). The cull's competence spare, the book's one consumer (`domains/api.py::manage`, brake two),
then reads a change the model did not make. The register rules one lever per consumer, default ON,
OFF = today's unit, and the DOM half built before the retok fleet (C12).

**The ruling, as built.**
* **`DOM_LEVELS`** (U.FLAG, default `True`; `src/domains/levers.py` section 8; a census amendment,
  since the old tree had no switch over the unit). At ON, `spine/loop.py::_flush` hands each window's
  reading as (nats / ln 2) × (bpt_build / `derive.bytes_per_token`(window bytes, window tokens)) —
  bits per byte × bpt_build, i.e. bits per build-time token. The window's tokens are its targets
  ids[a+1:b], ctx of them; its bytes are what they span off `Segmentation.byte_pos`, through
  `spine/loop.py::_window_bytes`, which `loop.bytes_scored` now sums too, so the two readings cannot
  disagree about a window's bytes. Row k of a flush's per-window loss is rescaled by window k's bytes
  at every `OPT_BATCH_WINDOWS`. OFF is `float(nats) / ln 2`, the expression before this entry,
  untouched.
* **bpt_build is `Vocabulary.bytes_per_token`**, TOK's measurement over the build sample, recorded in
  the vocabulary file and adopted on every resume (Q-TOK-13, `tok.bpt_adopted` 1), so the unit is a
  constant of the model's lineage across continuation sessions; the stream's own
  `Segmentation.bytes_per_token` is re-measured per stream and is not. At the shipped default the two
  differ by 1.58% (1.5018 against 1.4784 over the 120 KB stream). A vocabulary file older than the
  recorded field re-measures at the resume (`tok.bpt_adopted` 0), and the unit then follows the
  child's measurement.
* **The order of operations is chosen for the identity known answer.** As a ratio of two bytes-per-
  token values, a window whose measured value equals the build-time one gives x / x = 1.0 exactly, so
  ON equals OFF to the bit there. The register's left-to-right (mean nats × tokens / ln 2 / bytes) ×
  bpt_build is the same arithmetic, but it rounds at each step and does not promise that.
* **Why the root converts.** Both inputs are ones DOM may not hold: `byte_pos` is the cut's, and the
  bytes per token is TOK's, measured after assembly, so it cannot be a wire (SIG's width is the same
  case). **What DOM reads the lever for:** `state_dict` stamps the book's unit as `comp_unit`
  (`'build_token'` / `'token'`), and `open_partition` compares it with this run's unit on a resume.
  `part.n_comp_unit_changed` is ABSENT on a fresh partition, 0 on a restore in the same unit or of a
  book with no reading, and 1 on a book folded in the other unit; a blob older than the key reads as
  `'token'`, the only unit there was. That book is KEPT — not converted, since there is no per-domain
  bytes history to convert with, and not dropped, which would disarm the spare for every domain the
  child does not feed — and the root STATES it before the first window, on the Q-DOM-1 precedent: the
  warning names `DOM_LEVELS` and both units, says each EMA moves to the new unit at the `d_comp_ema`
  rate as its own windows arrive while an unfed domain keeps the parent's, and says a clean arm
  resumes at the parent's value. That is C12's "pre-Levels" fleet checkpoint continued at the default.
  (The stamp alone was the saving run's lever, not the book's unit; since 2026-09-27 the blob also
  carries `comp_carry` and the restore counts `part.n_comp_carried`. See the correction below.)
* **Counters.** `loop.levels_rescaled` (the loop's flush books): the windows whose factor was not
  exactly 1.0. ABSENT at `DOM_LEVELS=0`; PRESENT-and-0 when armed and no window left the build-time
  value (`TOK_MODE=bytes`); this process's windows, like `loop.bytes_scored`. `part.n_comp_unit_changed`
  as above. The R report's `DOM.census` row now prints `comp_glob` beside `comp_unit`, the unit it is in.
  `part.n_comp_carried` since 2026-09-27 (the correction below).
* **Text only, and DOM's half only.** MEM's rescaled surprise (Q-MEM-14, the register's (c)), CAP's
  improving test (inert until `CAP.observe` is rowed at P4, (d)) and FAB's stamped-act known answer
  ((b)) are not built here; each gets its own lever when it is. A media window's unit is a different
  conversion (03b item 16). At `DOM_ENABLED=0` the one `did=0` book is converted too, harmlessly.
* **Order-table prose.** The `DOM.note_competence` row names the unit, and `LM.lm_loss`'s produces
  column no longer calls `bits` "bits per byte": it was bits per token before this entry.

**What the default changes.** Competence VALUES change from the first window: at the shipped default
no window's bytes per token equals the build-time value (targets span 166-218 bytes against ctx ×
bpt_build = 192.2, factors 0.88-1.16, over the 634 windows of the 120 KB stream). The book's one
consumer is `DOM.manage`'s competence spare, so a default run's loss curve and counters move only from
the first cull decision the new unit decides differently, which needs a non-empty cull budget (ten or
more live domains at `DOM_CULL_FRAC` 0.1) and a candidate past `DOM_GRACE` and `DOM_CULL_STALE` (500
windows each). **The baseline fixture is unaffected and is not re-recorded:** no `DOM.manage` pass runs
in its 80 windows (the fixture has no `part.n_manage_calls`), and `tests/test_baseline.py` B1 passes
against the d32e2ce fixture (80 losses, 248 integer counters) with `loop.levels_rescaled` listed as new.

**What CPU establishes:** operation only — the unit reaches DOM, its known answers hold, the
counters fire, a resume is exact. Against the tree before this entry (072df9a), `DOM_LEVELS=0` over a
240 KB epoch with `TOK_RETOK_EVERY=200 DOM_GRACE=50 DOM_CULL_STALE=50 DOM_CULL_FRAC=0.5` (1230 windows,
6 acts, 12 manage passes, 8 culls, 4 competence spares) gives a byte-identical loss curve and all 323
integer counters equal. The default ON on that configuration gives the same curve and counters (the
same 4 spares; `loop.levels_rescaled` 1230 of 1230): no spare decision moved in that run.
The register's k1000 pair (`TOK_RETOK_EVERY=1000 DATA_STREAM_BYTES=760000 RUN_SEED=0`, one whole
epoch, ON against OFF, everything else at its default): 3815 windows and 3 acts on each arm, finite;
`part.n_created` 99 and `part.n_culled` 0 on both, and the loss curves and every integer counter
equal. The unit reached DOM — `comp_glob` 2.690 bits per build-time token against 2.951 bits per
token, `loop.levels_rescaled` 3815 — but the spare it feeds was never consulted: the cull budget was
empty at 34 manage passes out of 38 (the population ends at 4 live domains after 87 merges and 8 folds),
and the 4 cull candidates were inside `DOM_GRACE`. At the default shape, then, the unit decides
nothing yet; the (h) family's GPU arms are where it can. (This pair reported end-of-run totals only;
the register asks for readings at the acts, and `part.n_culled` never fired. The correction below
gives the per-act readings, and a substitute pair where the cull fires.)
Whether the unit improves domain management is read on GPU (U-series family (h), S5 (iii)), and an
adverse reading there returns the lever to OFF. Driven: `tests/test_levels.py` L1-L8,
`tests/test_continuation.py` S5 (now at ON by default).
**CORRECTED 2026-09-27 (build 1.2's review) — the checkpoint carries a mixed book's split, L2 proves
the spare's comparison ran, and the k1000 known answer is read at the acts.** (i) *The stamp was the
saving run's lever, not the book's unit.* `state_dict` wrote `comp_unit` from `DOM_LEVELS`, so a
child that resumed into the other unit (`part.n_comp_unit_changed` 1, warned) and saved a few
windows later stamped a book still mostly in its parent's unit as wholly its own. Driven at d4b010d
(the review's scratch `stage1/review/mixed_stamp.py`): a `DOM_LEVELS=0` parent saved at window 120
(12 domains, `'token'`) was resumed at `DOM_LEVELS=1` for 3 windows and saved. Its blob read
`'build_token'`, and 11 of the 12 domains' `comp` were still exactly the parent's per-token values.
A `DOM_LEVELS=1` grandchild read `part.n_comp_unit_changed` 0 and was not warned; a `DOM_LEVELS=0`
one was warned that the book was "folded in bits per build-time token". The `DOM.census` `comp_unit`
label, taken from the lever, had the same blind spot. **Repair:** the blob also carries
`comp_carry`, which is None when the book is wholly in `comp_unit`. Otherwise it holds the unit the
rest of the book is in, and each EMA's share of it: the population baseline's and each domain's. A
share is the EMA's own arithmetic, not an estimate. Every fold multiplies an EMA's past by (1 −
`d_comp_ema`), so `note_competence` multiplies the carried share of the two EMAs it folds into by
the same factor. A share below 2⁻⁵³ (`domains/api.py::_CARRY_FLOOR`, float64's unit roundoff: below
it the other unit weighs less than the rounding of one fold) counts as refolded and is dropped. At
0.02 that is an EMA's 1,819th fold in the new unit. `manage`'s tidy drops the shares of domains that
leave. `open_partition` re-reads the shares against this run's unit. They are kept as saved when the
stamp is this run's unit, and complemented when it is not: `DOM_LEVELS` is a flag, so the carried
readings are then in this run's unit and every other reading is not. A new gauge,
`part.n_comp_carried`, is ABSENT on a fresh partition. On a restore it counts the EMAs still holding
the other unit, falls as they are refolded or their domains leave, and reads 0 once none does.
`part.n_comp_unit_changed` is now 1 when that count is above 0 at the restore. That is unchanged for
every blob written in one unit, and it is 1 for both grandchildren above. The root's warning names
the carried unit (the one this run does not hand DOM) and counts the carried EMAs. It says the
checkpoint carries the shares, and gives the clean arm as a resume where `part.n_comp_carried` reads
0. That is the other `DOM_LEVELS` only when the parent's book is wholly in one unit; a mixed book is
whole in neither. While the count is above 0 the `DOM.census` label adds "k restored EMA(s) still
carry" the other unit. A blob written between d4b010d and this correction carries no shares, so a
mixed one of them still reads as wholly in its stamp: nothing in it can recover the split. No
default moves. `comp_carry` is None on every run that did not change the unit, and none of the new
branches is entered. Driven: `tests/test_levels.py` L6 (a book in one unit, resumed in the other,
carries every EMA: 13 of 13) and L8. L8 drives the case above. The child's blob carries each
restored EMA at (1 − `d_comp_ema`)^k for its k readings, to the bit. The `DOM_LEVELS=1` grandchild
reads `part.n_comp_unit_changed` 1 with 13 of 13 EMAs carried, and is warned in bits per token. The
`DOM_LEVELS=0` grandchild carries 2 of 13 (the one domain the child fed, and the baseline) and is
warned in bits per build-time token. A share that one fold takes below 2⁻⁵³ leaves the carry. 3 + 3
windows across the child's checkpoint end with the uninterrupted 6's shares, `comp` and `comp_glob`,
to the bit. L8 also checks the census label. (ii) *L2's setup check did not prove the spare's
comparison ran.* It asserted that the key `part.n_spared_by_competence` exists. But `manage` seeds
that key at the top of every pass with protection on, before any candidate is examined. At
`TOK_MODE=bytes` without the reach levers (300 windows; the review's scratch
`stage1/review/l2_setup.py`) the predicate held with 2 candidates, 2 grace skips, 0 culled and 0
spared. It now also requires `part.n_culled` + `part.n_spared_by_competence` > 0. A candidate
reaches brake two only past grace, the activity test and brake one, and leaves it either spared or
culled. On L2's reach configuration the sum is 6: 5 culled and 1 spared. (iii) *The register's k1000
known answer was not met, and this entry did not say so.* TREE-S0b-LEVELS asks for `part.n_created`
and `part.n_culled` read at the acts, and for counters that fire. The pair was re-run at 1f69a29
through a driver that reads DOM's counters as each act calls `DOM.on_retokenize` (scratch
`stage1/k1000c/drive.py`). Both arms act at windows 1001, 2001 and 3001. At those acts, both read
`part.n_created` 71, 82, 96 (99 at the end) and `part.n_culled` 0, 0, 0 (0 at the end), with equal
curves, as above. **At the k1000 defaults the register's "counters fire" is therefore unmet for
`part.n_culled`.** The cull budget was zero at 6, 16 and 26 of the 10, 20 and 30 passes before each
act (`DOM_CULL_FRAC` 0.1 needs ten live domains, and the population held 10, 3 and 4 at the acts).
The 4 candidates examined were all inside `DOM_GRACE`. **The substitute makes the cull reachable:**
the same pair plus `DOM_GRACE=50 DOM_CULL_STALE=50 DOM_CULL_FRAC=0.5`, the reach levers of the 240
KB run above. Each arm ran 3815 windows and 3 acts, finite. At the three acts, ON reads
`part.n_created` 77, 127, 138, `part.n_culled` 12, 15, 18 and `part.n_spared_by_competence` 9, 11,
13. OFF reads 80, 126, 146; 14, 16, 18; and 5, 8, 11. At the end, ON reads 140 / 18 / 13 and OFF 149
/ 18 / 11. The losses are equal for the first 700 flushes and differ from the 701st on. So on this
shape the unit decides spares, which the default shape never let it do. That is operation: the
counters fire, and the arms separate where the spare is consulted. It says nothing about which arm
manages domains better. The end losses (1.947 ON, 2.039 OFF) are one seed on CPU.

### Q-DATA-9 — the synthetic source's held-out block, its one resume admission, and the stream a continuing resume replays — **RESOLVED 2026-09-27 (Proposal 05 §8 3.1; register 04-Q5; Proposal 04 §1 item 7 and SR0): `DATA_SYNTH_HOLDOUT`, BUILT `False` — 04-Q5 RULES IT ON, AND THE FLIP LANDS LAST AND ALONE; ONE RESUME ADMISSION, COUNTED PER AREA; A CONTINUING MID-EPOCH RESUME REFUSED ACROSS IT AND ACROSS A REDRAWN STREAM (A DIGEST IN `seg_log`); `Areas.parent_names`; `derive.stream_key`; DATA's ROWS AT R. ⚠ ONE NEW LEVER, A CENSUS AMENDMENT. NO SIGNATURE MOVES, NO WIRE**
**What was asked.** The synthetic source held nothing out (`open_areas` set `n_hold = 0` on it), so
no held-out number could be read on the shipped default source: not SR0's retention probe, not E1's
primary reading, not the focusbed readings goal B is decided on. 04-Q5 rules `DATA_SYNTH_HOLDOUT`
ON, built at SR0 under the real sources' law, with the one resume admission (key None, size 0 → n,
counted as `data.holdout_admitted`), and names the pin rule for fleets that pair with earlier runs.
Proposal 04 rejected the judge's variant (held-out text drawn from a separate child, bodies left
whole) as a second holdout law whose block is a continuation drawn after the body, not a sample of
it.

**The ruling, as built.**
* **The lever and the law.** `DATA_SYNTH_HOLDOUT` (U.FLAG, `src/data/levers.py` §4 beside
  `holdout_frac`; a census amendment, the tenth: the old generator had no switch). At `True`,
  `open_areas` runs the real sources' carve on each generated body **verbatim**: min(int(body ×
  `DATA_HOLDOUT_FRAC`), `DATA_VAL_CAP`) bytes, the start from `rng_for("data.holdout.<key>", seed)`
  (one child per area, keyed by name, Q-DATA-6), the block removed from the body, its seam gate and
  overlap reading, the val-cap tally, and the 0-byte refusal, whose message on this source also names
  `DATA_SYNTH_HOLDOUT`. `data.holdout_block` and `data.val_cap_trip` take the real arm. At the
  shipped stream a synthetic area is generated at 60,000 bytes and holds out 3,000, training on a
  57,000-byte body (the generator sizes each area at twice what the sampler needs, so the floor is
  never near). At `False` the synthetic branch runs the statements it ran before, in order, and mints
  no `data.holdout.<key>` child; its OFF record keeps key None, offset 0, size 0, seam None, and its
  `why` reads *"DATA_SYNTH_HOLDOUT=0 holds nothing out on this source"* (it read *"source=synthetic
  holds nothing out"*, which the lever made untrue); the two gates read UNREACHABLE naming
  `DATA_SYNTH_HOLDOUT=0`. On a real source the lever is inert.
* **Built OFF, ruled ON.** At ON every synthetic body is a block shorter, so every default run's
  stream changes and no run before the change pairs with one after it. The flip is therefore its own
  commit, last, after SR0's bit-identity (§8 3.1), with 04-Q5's pins for the fleets that pair with
  earlier runs.
* **The one admission** (`restore_stream_state`). A record of key None **and** size 0 against a
  block now **on the synthetic source** is admitted: all three fields move, and no across-the-boundary
  number is broken, because the parent had no block for one to read. **Synthetic only, which is
  narrower than 04-Q5's words and is its move:** only a synthetic run at 0 writes that record (a real
  area's empty block is refused in `open_areas`), so the same record against a *real* block is a change
  of source under the same area names. Taken literally, the admission would have let that through;
  driven at ae70638 it is refused (a two-area synthetic parent resumed at `DATA_SOURCE=real` names
  the moved offset), and it still is. **The unit is the area**: each admitted area counts one in
  `data.holdout_admitted` and is named in `data.holdout_admitted_names`, so a four-area parent admits
  4 and SR0's written "`data.holdout_admitted` 1" is the single-area case. Both keys are ABSENT on a
  fresh run and read 0 and `[]` on a resume at `DATA_SOURCE=synthetic` `DATA_SYNTH_HOLDOUT=1`, the
  one arm the admission can fire on, and ABSENT on every other (corrected 2026-09-27, below: they
  read 0 and `[]` on every resume). **The parent trained on
  every byte of an admitted block**, so it is text the lineage has seen, not a clean held-out sample:
  the root prints that in one warning naming the areas, before the first window (the Q-DOM-1
  precedent; DATA prints nothing). **The read cursor is mapped, not copied**, because it indexed the
  whole body: below the block it stays, past it it moves down by the block's size, inside it (text
  now held out) it moves to the block's offset, the first byte after the block in the carved body,
  reduced mod the carved length as `draw_stream` stores it (`data/api.py::_carved_cursor`). All of
  that holds only where this run generates the parent's text for the area, which the admission
  now checks first: the same position and the same length (corrected 2026-09-27, below). **The
  reverse is refused naming both settings that write a block**, `DATA_SYNTH_HOLDOUT=1` and
  `DATA_SOURCE=real` (corrected 2026-09-27, below: it named the first alone): a block in the record
  and none now would train on the text the parent held out. Every other move of a recorded block is
  refused as before.
* **`Areas.parent_names`** (a list field, default empty, filled in place by the restore): the
  record's area names, in its order. It is the one place a later build can ask which areas a parent
  trained on; §8 3.1's probe and §8 3.3's parent rehearsal are the builds that will read it, and
  nothing reads it yet.
* **`data.holdout_overlap` survives the restore.** It is a reading of this run's blocks, which
  `open_areas` computed a moment before, and the restore copied the parent's over it: an admitted
  child read *"no block to measure"* beside its block, and an add-an-area child lost the new area's
  reading. Driven at ae70638, a real-source parent over `eng` and a child over `eng,py`
  (`DATA_CORPUS_CAP=200000`): the child's own `{'eng': 0.0741, 'py': 0.1142}` became `{'eng':
  0.0741}` at the restore. The skip list gains it, with the admission pair. `data.area_added`,
  whose docstring promised "0 on an ordinary resume", is now seeded 0 there; it was ABSENT, and the
  new report row made the difference visible.
* **A continuing mid-epoch resume checks its stream before replaying the log** (`spine/compose.py`,
  the `segment` stage; §3.3). (a) An admission there is refused by name, `RefusedRun` naming
  `DATA_SYNTH_HOLDOUT=0` or an epoch-boundary resume, because an admitted body is a block shorter and
  the redraw is not the stream the parent was reading. (b) Otherwise the redrawn stream's digest is
  compared with the one the log's first event recorded, and a mismatch is refused naming the
  draw-shaping levers with this run's values (and, on a real source, the corpus on disk). (c) A log
  written before the digest warns once and keeps the rebuilt-length check at the `epoch0` stage, and
  the child's copy of the log records its own stream. Both refusals raise at the `segment` stage, a
  fourth stop on this path only
  (Q-RUN-13's three are unchanged): neither needs the model, and the replay would cut the parent's
  log over other text. **The digest** (`_stream_digest`) is blake2b over `Stream.bytes`, then per
  segment its start (8 bytes, little-endian), its area label and a separator, then the stream's
  length. `Stream.labels` is one label per byte and constant within a segment, so the segment table
  covers bytes and labels exactly at O(segments) cost. `_seg_event(vocab, kind, at=None,
  stream=None)` writes it as the `stream` key of the epoch's first event, at compose's fresh log and
  at stage E's roll; a splice carries none. It is a dict key in `LOOP.seg_log`: no draw and no
  counter.
* **`derive.stream_key(label)`** is the one normalisation of an area label into an rng key
  (lowercased, every character outside `[a-z0-9_]` → `_`). `data/api.py::_holdout_key` delegates to
  it, and SR0's probe keys its pinned draw per area and half by the same function (the register's
  C11 halves are EVAL's, drawn from each block, and are §8 3.1's probe build, not this one). DATA
  and EVAL may not import each other, so a second copy would be two answers to "which stream is this
  area's".
* **DATA's rows at R.** `spine/loop.py::_report` prints `DATA(areas.counters)`,
  `DATA(areas.gates)` (through `spine/gate.py::three_state`), `DATA(plan.counters)` and
  `DATA(stream.counters)` beside the older `DATA(stream.gates)`, read off the records as MEM's and
  TOK's are. `_SAVE_COUNTS` gains DATA's pair, so `data.state_written` and its twin print (k + j, j)
  under the build 1.6 rule, and Q-CKPT-4's table has eleven rows. Until these rows, "PRINTED" in
  DATA's own DID IT FIRE lines (`data.area_added`, the overlap reading) had nothing behind it.

**What the default changes.** No training number. At `DATA_SYNTH_HOLDOUT=0` the synthetic branch runs
the statements it ran before and draws nothing new; the digest is computed off the drawn stream and
changes no draw; the restore's skip changes one reading, equal to the recorded one for a carried
area; and the new refusals fire only where the tree before this ruling trained on bytes other than
the parent's or died unnamed at the rebuilt-length check. `tests/test_baseline.py`'s six workloads
reproduce their fixtures. The report gains four rows, and their integer counters are listed as new,
never compared: every leg lists `data.segment`, `data.phase_resolved` and `data.phase_name_resolved`;
a leg with saving on adds the `data.state_written` pair; a resumed child adds the restore's own,
`data.state_restored` and `data.area_added` (and listed `data.holdout_admitted` too until the
correction below, which leaves it ABSENT on the shipped arm).

**Recorded, not repaired: a continuing mid-epoch resume at `DATA_SEG_CONTIG=1` cannot continue.**
`draw_stream` advances each area's cursor for the whole epoch when it draws it, so the checkpointed
cursors are the ones after the parent's draw, and the child's redraw of that epoch starts past the
parent's segments. Driven at ae70638 (tests/test_continuation.py's base at `DATA_SEG_CONTIG=1`, saved
at window 60): the child died at the rebuilt-length check, 317 windows against 316, naming no lever.
The digest now refuses it at the `segment` stage, and the message says the refusal is expected with
every lever unchanged at `DATA_SEG_CONTIG=1`. A boundary resume is unaffected. The repair (the
epoch-start cursors in the log) is a change to the log's format and is left to the owner.

**What CPU establishes:** operation only. `tests/test_holdout.py` (new): H1, at 0 the synthetic
bodies are the generated text whole with no `data.holdout.<key>` child, the OFF record compares as
before, and on a real source the carve equals the law recomputed from disk for three areas, a slash
entry among them, with the lever inert there; H2, at 1 each shipped area holds out 3,000 of 60,000
bytes at the offset `rng_for('data.holdout.<key>', seed).randint(0, 57000)` draws (seed 0: eng
41591, py 39908, num 37668, c 53336; seed 1 differs in all four), adding a fifth area at the same
per-area size moves no block (and at the shipped `DATA_STREAM_BYTES` moves every one: corrected
below), the val cap binds, and `DATA_HOLDOUT_FRAC=0.0` is refused naming all
three levers; H3, the admission per area (4, and 1 for a single-area parent, through compose from a
finished parent too), the cursor map (hand-computed, and on the cursors a `DATA_SEG_CONTIG=1` parent
saved), `Areas.parent_names`, the warning, the R row and the overlap; H4, the reverse, a doctored
offset and a synthetic parent resumed at `DATA_SOURCE=real` refused; H5, the continuing refusals (0 → 1 with and without a digest, `DATA_SEG_MAX` 1800 →
1700), one segment's label changing the digest, an exact continuation that reads the admission pair
0 (ABSENT since the correction below), and a digest-stripped log that warns once and continues exactly, all again at epoch 1, where stage
E wrote the log; H6, `tests/test_continuation.py`'s `plain` and `mint_then_act` shapes continue
exactly at 1; H7, `derive.stream_key` is `_holdout_key`. `tests/test_continuation.py` S10 reads
eleven rows. Whether a held-out reading on these blocks measures anything is §8 3.1's probe and the
GPU readings after it.

**CORRECTED 2026-09-27 (§8 3.1's review) — a synthetic block rides on a generated body, so its
refusals say what it rides on; the admission holds only on the parent's text; the record carries
each block's digest; the admission pair is ABSENT where it cannot fire; the reverse names both
writers; and the restore declares what it reads.** (i) *A synthetic block moves with the body it is
carved from.* `_synthetic_areas` generates every area at max(`DATA_SEG_MAX` + 1, 5000,
`DATA_STREAM_BYTES` // `DATA_N_PROCESSES`) × 2 bytes (now `data/api.py::_synthetic_length`, the one
formula), and at `DATA_SYNTH_HOLDOUT=1` the carve's size is a fraction of that length and its offset
is drawn over it, so the three levers move every area's block together. Driven at 2d201d0: a fifth
area at `DATA_STREAM_BYTES` 120000, Q-DATA-4's add-an-area run with only the area and
`DATA_N_PROCESSES` changed, took each body from 60,000 bytes to 48,000 and each block from 3,000 to
2,400 (eng: offset 41591, size 3000 → 41591, 2400), and the resume was refused naming only the size;
one area to two was refused naming only the offset (166367 → 83183), and `DATA_STREAM_BYTES` 120000
→ 160000 at four areas the same (41591 → 66805). The ruling said a fifth area "at the same per-area
size moves no block", which is true and was all H2 built (at 150,000 bytes, scaled by hand), while
the restore's docstring said adding an area could not move another's block, on either source.
**Ruling:** the law stays the real sources' verbatim. A carve independent of the generated length
would be a second law, sized by a length that is not the body's: from `DATA_SEG_MAX` and the floor
alone, max(1801, 5000) × 2 = 10,000 bytes at the shipped values, it holds out 500 bytes per area
where C11 splits the shipped 3,000 into two halves of 1,500, and any larger length is a literal no
lever declares. On this arm the refusal says what the block rides on: this run's length with the
three levers' values,
the parent's recorded length (`bytes_taken`), the `DATA_STREAM_BYTES` that gives it back where one
does (150000 for a fifth area), and `DATA_SOURCE=real`, which records the same fields. The
docstring's claim is scoped to the real sources. **Along a lineage at 1 the generated length is
fixed:** an add-an-area resume raises `DATA_STREAM_BYTES` with `DATA_N_PROCESSES`. (ii) *And it
holds the text the area's position picks.* Found while ruling (i): the generator takes each area's
alphabet by position, `_ALPHABETS[i % 5]` (the old `make_proc`'s `ALPHA[s % len(ALPHA)]`), and
`_synthetic_areas`' docstring said inserting an entry no longer moved every later area's text,
which only its per-child draws made true. Driven at 2d201d0: `eng,rust,py,num,c` at 150,000 over a
parent at `eng,py,num,c` was admitted with py's, num's and c's blocks other bytes under the parent's
offset, size and key, and `py,eng,num,c` the same for eng and py: across-the-boundary numbers over
two texts, admitted in silence. A carried area whose alphabet moved is now refused at 1 naming
`DATA_AREAS`: the parent's areas keep their positions and new ones are appended. The alphabet stays
positional, because keyed by name it would move the shipped four areas' text, which every synthetic
run pairs with. (Three of the five alphabets hold 15 symbols and two hold 14; the comments said
five of 15.) (iii) *The admission's premise.* Its warning says each admitted body is the parent's a
block shorter and that the parent trained on the block, and the cursor map assumes the same text;
none of it holds at another length or with the alphabet moved. Driven at 2d201d0: a child at
`DATA_STREAM_BYTES` 400000 was admitted with all four blocks past the parent's 60,000 bytes (eng at
166367), and a reordered child with eng's and py's blocks cut from other text. The admission is now
refused unless this run generates the parent's text for the area, at the same position and the same
length as the record's `bytes_taken`. The refusal names what moved, with `DATA_SYNTH_HOLDOUT=0` as
the resume that continues as before. (iv) *The block's digest.* A real block and a synthetic one of
the same length draw the same offset from one keyed stream over one range. Driven at 2d201d0: a real
parent over eng (`DATA_CORPUS_CAP=200000`: offset 166367, size 10000) resumed on the synthetic source
at 1 and `DATA_STREAM_BYTES` 400000 was admitted, as an add-an-area run over py, num and c, with
English held out in the checkpoint and generated text held out now. Offset, size and key say where a
block sits, and the refusal's own reason is about what it holds. `stream_state` now records each
block's blake2b (`_block_digest`: 16 bytes, `person` `data.holdout`), and the restore compares it after
the fields and the position, refusing a text that moved under agreeing fields and naming both
sources. A record without it, written before this correction, is compared on the three fields, as
it was. It also refuses what no field could see: a real corpus changed on disk under an unchanged
cap, or a synthetic generator changed between the two runs. The cost is one hash over at most
`DATA_VAL_CAP` bytes per area per save. (v) *DID IT FIRE.* `data.holdout_admitted` and its names were
seeded on every resume, so the shipped arm and every real-source resume printed "armed, did not
fire" for an admission that cannot run there: at 0 no synthetic block exists, and a real one is
never admitted. They are now seeded only at `DATA_SOURCE=synthetic` `DATA_SYNTH_HOLDOUT=1` and are
ABSENT elsewhere (the Q-FAB-8 precedent: `fab.ind_applied` is seeded only on the arm that can reach
it). `tests/test_baseline.py`'s B3r and B6r children no longer list `data.holdout_admitted` as new;
`data.area_added`, armed on every arm, still reads 0. (vi) *The reverse refusal* named
`DATA_SYNTH_HOLDOUT=1` as "the setting that wrote the block", but a real parent resumed at the shipped
source takes the same branch. Driven at 2d201d0, following that advice was refused again (offset
166367 → 41591), and the resume that works, `DATA_SOURCE=real`, was never named. The record cannot
say which source wrote a block, so the message names both. (vii) *LEVERS READ.* `restore_stream_state`
declared none and read `source` and `synth_holdout`. It now declares those two and the three that
size a synthetic body, which its refusals print. **No default moves.** On the shipped arm the restore
compares two equal empty-block digests and seeds one key pair fewer, and no training number changes:
`tests/test_baseline.py`'s six workloads reproduce their fixtures. **What CPU establishes:** operation
only. H2: the add-an-area run as ruled, refused at 120,000 naming the three levers, both lengths and
150000, admitted appended at 150,000 with no block moved, and refused inserted and reordered naming
`DATA_AREAS`. H3: the pair on each of the four arms, and the admission refused at 400,000 and
reordered, admitted appending a fifth area at the parent's length. H4: the reverse naming both
writers; a real parent at the shipped source refused and restored at `DATA_SOURCE=real`; the digest
refusing that parent at 400,000, and a real corpus with one byte changed inside its block on disk (a
byte changed in the training body restores); a digest-stripped record compared as before; a
doctored digest refused. H5: the pair ABSENT on the shipped continuation. H8 (new): every DATA stub's `LEVERS READ:`
names exactly the levers its body reads, through the helpers it hands `dat` to.

### Q-RUN-11 — a resume drew epoch 0's stream whatever epoch it resumed in — **RESOLVED 2026-09-24: THE `stream` ROW DRAWS `Snapshot.epoch`**
The `stream` row passed `epoch=0` unconditionally. Driven at `RUN_EPOCHS=2 DATA_RESAMPLE=1`: the
parent's epoch-1 draw hashed `65cd298845`; its child, resumed at epoch 1, drew `cfacafbe13` (epoch
0's) and trained its first window on epoch 0's first window. **Ruling:** the row draws the resumed
epoch; `DATA.draw_stream` still owns whether the epoch changes the draw. The `DATA_RESAMPLE=0` arm
at epoch ≥ 1 cannot train at all — `RUN.startup_refusals` refuses `RUN_EPOCHS > 1` without
resampling, and at `RUN_EPOCHS=1` epoch 1 is the finished resume Q-RUN-10 refuses — so what
`draw_stream` does there (it replays epoch 0 only from its in-process cache) is never trained on. It is also what Q-RUN-10's declared replay means by "the epoch it was
interrupted in". **Rejected:** drawing epoch 0 and fast-forwarding the DATA rng (the draw is a
function of `(seed, epoch)` already; there is nothing to fast-forward).

### Q-RUN-12 — `_windows_in_epoch` counted a window that lacks its final target — **RESOLVED 2026-09-24: `(len(ids) − 1) // ctx`**
A window needs `ctx + 1` ids, so an epoch holds `(len(ids) − 1) // ctx` windows; `len(ids) // ctx`
overcounted by one exactly when `len(ids)` is a multiple of `ctx`. The loop skipped that window and
called it arithmetic, but the clock had counted it, and on a flush tick it closed a flush with no
backward: driven on a 768-id segmentation at `ctx=128`, 6 flushes against 5 backward passes at
`OPT_BATCH_WINDOWS=1`, and at 2 the fifth window was accumulated, never trained and not counted in
`dropped_windows`. **Ruling:** the named division is `(len(ids) − 1) // ctx`, so the empty tail never
exists and the loop's no-material branch is a defect detector only. Every run whose `len(ids)` is not
a multiple of `ctx` gets the same number as before. **Rejected:** flushing the partial batch on the
tail tick (leaves the clock's empty flush at `OPT_BATCH_WINDOWS=1`); un-counting the flush in the
clock (a second place a counter moves).

### Q-MEM-12 — the read probe issued one query per batch row, the eviction counters counted free placements twice, and the R stage dropped the MEM, DATA and grow_check gates — **RESOLVED 2026-09-24: ONE QUERY PER POSITION; AN EVICTION IS A VICTIM; THE ROOT RENDERS THOSE GATES THROUGH `spine/gate.py::three_state`. ⚠ EVERY MEM ARM, EVICTION AND PROBATION NUMBER TAKEN BEFORE THIS DATE WAS MEASURED AT ~1/64 OF THE DECLARED READ RATE**
**The probe.** `maintain` took `probe_contexts[::stride][:probe_rows]` over the **batch** dimension
and keyed each row's last `key_win` tokens, so a probe issued `batch_windows` queries whatever
`MEM_PROBE_ROWS` said — **one** at the shipped `OPT_BATCH_WINDOWS=1`. Driven over 80 default windows:
`n_probe_fired 4, n_probe_rows 3, n_promoted 24`, and `MEM_PROBE_ROWS=1` gave identical counters.
The lever's help (*"how many query rows each probe read issues"*), its sizing comment, this
contract's "64/25 query rows per window" arithmetic in Q-MEM-4 and the frozen tree
(`mem_ctx(x) = _windows(x, KW).reshape(-1, KW)`, strided at `self_organize.py:7558`) all count
per-position windows, and so does the write path, which keys every position through `_key_windows`.
**Ruling:** the probe forms `_key_windows(probe_contexts, key_win).reshape(-1, key_win)` and issues
`q[(w % stride)::stride][:probe_rows]` with `stride = max(1, n // probe_rows)` — the frozen tree's
deterministic stride **and** its `step % stride` rotating offset, so the probe does not query the
same positions of every window for a whole run and still draws no RNG. `n_probe_rows` counts rows
actually issued. After: `n_probe_rows 192` (64 per fire that had contexts), `n_promoted 508`,
`n_evict_main 256`; `MEM_PROBE_ROWS=1` now gives 3 rows. The encode cost rises from `B` to
`probe_rows` rows of `key_win` tokens per fire. **Rejected:** keeping one query per row and
re-documenting the lever as "rows of the batch" (it would leave the lever inert at the shipped batch
width and the probe querying a different key shape than the write path stores); a random draw of
positions (the probe must not consume RNG — `memory/levers.py`, probe_rows).
**What this does to earlier numbers:** promotion out of probation and the lru/usage rankings are the
Goal-B retention mechanism, and every run before this date ran them at ~1/64 of the declared rate —
MEM arm comparisons (`MEM_EVICT`, `MEM_PROBATION_FRAC`, `MEM_WRITE_MODE`), `probation_share`,
`n_evict_main` and the pressure reading must be re-taken. The training loss does not read the store
(`MEM.blend` is deferred), so the loss curve is unaffected on the default arm.

**The eviction counters.** `_commit_window` returned `m` — every committed row — as the eviction
count whenever the block ran short of free slots, so a commit that filled 8 free slots and overwrote
57 entries counted 65 evictions **and** 8 free placements. Driven on an 80-window
`MEM_WRITE_MODE=quantile` run: `n_writes_committed 2393` against `free + probation + main = 2075 +
509 + 0 = 2584`, with 318 entries actually overwritten. **Ruling:** the count is `vic.numel()`, the
victims `_victims` chose, and `free_used + evicted == committed` is refused by name if it ever fails.
After: `2075 + 318 + 0 = 2393`. The default fixed arm is unchanged (a block there is always wholly
free or wholly full). **Not taken:** per-victim branch labels (`store.prob[vic]` before the
overwrite). The branch is what `pressure` is defined over (Q-MEM-4, `_victims`' docstring), and
changing the definition is the retune that ruling defers.

**The gates at R.** `loop._report` copied MEM's census numbers and dropped `StoreCensus.gates`, never
read `Stream.gates`, and `FAB.grow_check`'s `GrowReport` was a bare expression statement's value —
so the seven `mem.*` gates, the four `data.*` stream gates and the five grow-check gates reached no
report, and the LOOP_ORDER R row claimed the MEM census was where two of them *became visible*.
**Ruling:** a shared renderer, `spine/gate.py::three_state(gates) -> {name: (state, arithmetic)}` in
the package copies' state words, used by the root for exactly the gates no `counters()` entry point
renders: `gate:mem.*` inside the `MEM.census(reconcile=True)` row, a `DATA(stream.gates)` row read off
`sysm.stream` at R (stage E redraws it), and a `FAB.grow_check(last call's gates)` row from
`System.grow_gates`, which holds the last call's **gates tuple only** — never the record. It has no
count column: none of these gates has a ledger key of its own name, and a column would print
`fired, 0`. **Rejected:** importing `fabric/api.py::_three_state` (O10 — a package private); holding
the last `FabricOut` or `GrowReport` on the System (a live forward graph, and a record CKPT might try
to serialise); refactoring LM/SIG/FAB's own copies onto the shared renderer in this commit (their
count column is a ledger lookup this renderer deliberately lacks, and the three packages are other
slices' work).

**Two orderings and the seeds that go with them.** The R stage copied `store.counters` **before**
`MEM.census(reconcile=True)` and `DOM(part.counters)` before `DOM.prior`, so the report printed
`store.n_census_reconciles` and `part.n_prior_reads` ABSENT while the final checkpoint carried 1 —
against the save row's *"the checkpointed counter vectors are the ones the report printed"*. Both
calls now run before the copies. And per G4, counters are seeded on the arm that can bump them,
before the branch: `n_probe_fired/rows/hits` when `MEM_PROBE_EVERY > 0` **and** `MEM_PROBE_ROWS > 0`
(the rows clause added later on 2026-09-24: `MEM_PROBE_ROWS=0` comes due and issues no row, so it is
the second disarmed arm — counters ABSENT, Gate `mem.probe` UNREACHABLE naming it — and it had read
present-and-0 beside a pressure reason blaming the loop's lag; the same fix makes `mem.probe` fire on
`n_probe_rows > 0` rather than on the cadence, so a probe that fired and issued nothing renders
armed-but-zero, as its reason says); `n_rekey_passes/slices/
entries` when the rekey is armed (it read ABSENT mid-pass beside 79 slices), plus
`n_keys_at_capped_depth` only on a transformer at `key_depth > 0`; `n_dup_refused` and
`n_src_underflow` on every commit; `n_write_truncated` only when `ctx > quota` (at the shipped 128 ≤
128 it is structurally unreachable and stays ABSENT); and the kept-nothing early return of `write`
seeds the eviction and floor counters beside `n_writes_committed`. None of these seeds is in
`open_store`'s seed dict, whose keys the counter restore skips.
`tests/test_mem_probe.py` drives every part of this ruling.

---

### Q-FAB-12 — the failure cull judged "above the population" against a mean that counted never-selected experts as perfect — **RESOLVED 2026-09-24: THE POPULATION IS `comp_glob`; `comp_protect` SPARES THE BETTER EXPERT; THE REACHABILITY GATES CARRY THE ENTRY COUNT**
`FAB.manage` formed `ef_pop` / `es_pop` as the mean over **every** live expert, and `observe` says in
writing that `ef = es = 0.0` is "never attributed", told apart from a zero loss only by the selection
count. Driven on a default 200 kB run: at window 1001, 1148 of 2950 live experts had never been
selected, the all-live mean was 2.940 against 4.813 over the selected, so the bar sat at 3.09 and
**11 of 13** eligible experts were culled (the other 2 spared as adapting), every one of them *below*
the selected mean; at window 501 the one eligible expert was culled. The same pass printed
`fabric.cull_eligible` as `2 vs 48` (the post-cull remainder) and `fab.merged` as armed-but-zero with
an "unreachable" reason. The documented criterion — "both error EMAs sit above the population by
fail_tol" (`fabric/levers.py`, `FAB.manage` step 1) — does intend to cull a well-selected expert
that is still failing; what it does not intend is a baseline under every selected expert.
**Ruling:** (1) the baseline is **`comp_glob`**, the flush-mean loss EMA `observe` keeps — the old
tree's own `failing(e, comp_glob)` (self_organize.py:2189-2194, fed `asm.comp_glob` at :6718); at
window 1001 above (comp_glob 3.660) the same pass culls 3 of 13. `comp_glob` None (nothing attributed
yet) means no failure cull. The additive `fail_tol` is unchanged. (2) the failure path also spares
`contrib > 0`, the old tree's rule (inert while `FAB.contribution` is deferred). (3) the
**`comp_protect` spare compared `comp > comp_glob`**; comp is a LOSS, so it spared the worse experts
(at window 1001 it would have spared the six at comp 3.72-8.12 and left the seven at 3.38-3.61 to the
cull). It is `<` now, as the lever's help and the old tree's :2271 say. (4) `fabric.cull_eligible`,
`fab.merged`'s reachability and `ManageReport.eligible` carry the eligible count **at entry**, and the
reason says how many the pass removed, so a pass that culled cannot print 'unreachable' (Q-FAB-5's
own condition); `fab.merged` has its own armed-and-did-not-fire sentence. **Rejected:** the mean over
experts with `uage > 0` (a once-selected expert's EMA is its first window's loss, seeded early and
never decayed — that mean sat ~0.9 nats over the flush mean and made the cull nearly inert); the mean
over the eligible set (a lone eligible expert IS the mean and can never fail); extending
`comp_protect` to the failure path (after (3) a failing expert is by construction above `comp_glob`).

### Q-FAB-13 — AdamW's moments did not move with the expert rows the fabric moved — **RESOLVED 2026-09-24: FAB NAMES ROW EVENTS ON `FabricOut.row_events`; THE NEW `OPT.remap_rows(opt, st, row_events)` APPLIES THEM BEFORE THE BACKWARD. A FROZEN SURFACE GREW BY ONE ENTRY POINT AND ONE RECORD FIELD**
FAB's banks are one `(cap, …)` parameter each, so `exp_avg` / `exp_avg_sq` row *i* belongs to whoever
occupies slot *i*. `_remove`'s swap-with-last moved an expert's A/B rows and zeroed the old slot;
nothing moved the moments. Driven at `FAB_MANAGE_EVERY=30 FAB_GRACE=1`, 45 windows: **154 of 154**
moved experts took their next step on the culled expert's `exp_avg`, and all **159** slots zeroed and
not reborn held non-zero A/B again (max|B| 1.1e-2) — dead rows stepped on residual momentum, and a
birth into one inherited it. **Ruling:** `_remove` and `_claim_slot` append `("move", src, dst)`,
`("clear", slot)`, `("birth", slot)` to `Population.row_events`; `FAB.forward` drains them on
TRAINING passes only into `FabricOut.row_events` (a `RowEvents(tensors=(A, B), events)`); the root
calls `OPT.remap_rows` between the forward and `OPT.scaled_backward` — the one point every event since
the previous backward (grow_check's births, manage's culls, forward's spawns) has happened and the
next gradient has not landed. OPT applies them in order to both moments and any accumulated `.grad`:
move copies then zeroes the source; clear and birth zero the row. **After** (same arm): 71 of 74
checked moves carry their own moments at the next step (the 3 others are the intermediate slot of an
expert moved twice in one pass, which the in-order application lands at its final slot —
tests/test_fabric_internals.py I5 pins the chain), 0 of 66 dead slots non-zero, `opt.rows.moved 77`.
**A birth gets zero moments**, which is exactly what a never-used slot is born with (it receives no
gradient before birth), so at the default 300 windows — no manage pass, every birth into a fresh
slot — the remap changes nothing. **Rejected:** calibrating a newborn's `exp_avg_sq` to its parent's
row or the live median (a better-conditioned first step than AdamW's ~3x zero-state step, but it
changes every one of the ~150 spawns in a 200-window run — a behaviour change to the common path with
no measurement behind it); remapping the merge's and rescue's in-place rewrites (Q-FAB-2 rules their
moments stale-by-statement; the merge's removal of the absorbed expert IS a `_remove` and IS remapped);
events on `ManageReport` / `GrowReport` (manage runs on windows, not flushes, and the root would need
a new System slot to carry them to the next backward).
**Pending events cross a checkpoint (added later on 2026-09-24).** Because manage runs on windows,
at `OPT_BATCH_WINDOWS > 1` it can fire on a window that ends no batch, and a periodic save there held
A/B with the experts moved beside moments still at the old rows; `Population.row_events` was not in
`FAB.state_dict`, so the resumed process never applied those moves (driven, batch 4, manage every 30:
143 pending moves at the window-91 save). `FAB.state_dict` now carries the pending list and
`load_state_dict` restores it, so the child's first training pass hands it to `OPT.remap_rows`
against the restored moments — what the uninterrupted run does at its next flush
(`tests/test_resume.py` R7). **Rejected:** draining at `loop._save` (the root would need a new FAB
entry point to drain the list, or would call a FAB private, which O10 forbids).

### Q-FAB-14 — HALT competed with the whole population's mass — **RESOLVED 2026-09-24: THE HALT LOGIT CARRIES +log(n_live), SO HALT COMPETES WITH ONE EXPERT. ⚠ THE SHIPPED DEFAULT BEHAVIOUR CHANGED: HALT MASS AT n0=2048 GOES FROM ~1e-3 TO TENS OF PERCENT**
`FAB.forward` scored HALT as one more column of the softmax over the n live experts, so its mass is
sigmoid(halt_logit − logsumexp(experts)) and logsumexp grows with log n. Driven over 100 default
windows at 120 kB: halt mass 2.1e-04 at the first flush (logsumexp 9.73 against a halt logit of
1.26), training EMA 0.00085 at the end; the same code at `FAB_N0=8` put 51% of the first flush's mass
on halt and ended at an EMA of 0.67. `FAB_HALT` ("HALT as a real operator") and `FAB_PONDER` were
live at test widths and near-inert at the shipped population. **Ruling:** `_halt_logit` adds
`log(n_live)`, so halt's mass is sigmoid(halt_logit − log-MEAN-exp(experts)): equal evidence gives
halt what one expert gets, at every population size, and n = 1 is the old column exactly. `halt_b`'s
zero init and the halt-off pin are unchanged. **After** (same 100 windows): 30% at the first flush,
and at depth 1 — where `hop_vote` makes the vote independent of the halt mass, so only the ponder
charge pulls on it — the mass climbs to the `halt_max` clamp (EMA 0.50, 15 clamped rows); with
`FAB_PONDER=0.5` unannealed, EMA 0.63. At full depth (`FAB_DEPTH0=0`, 150 windows) the operator
responds to the LM loss instead (mass 0.02-0.32, EMA 0.30, 0 clamped), and FAB_HALT on/off differ by
0.015 nats in the mean of the last 50 flushes (4.8105 / 4.7960) — inside this run length's noise,
where one flush's loss has a 1.6-nat standard deviation. **At depth 1 the prediction does not depend
on the halt mass** (the vote spends `ph` and `1 − ph` on the same hop), so the shipped default's loss
moves only through the ponder term's small gradient into the shared query modules. **FOR THE OWNER:**
once staged depth advances, a halt mass sitting at the clamp means hop 1 answers ~90% of the vote
until the LM loss pulls it down; `FAB_HALT=0` is the one-lever ablation and a long GPU run at
`FAB_DEPTH0=0` is the measurement that settles whether this operator pays. **Rejected:** a separate
sigmoid gate outside the softmax (n-free too, but halting would no longer compete with the experts,
and at the frozen zero init of `halt_b` it would start every run at ph ≈ 0.5 — a new init that changes
what a saved `halt_b` means); `log(n / chain_k)` (a coupling of halt's prior to a routing width
nothing rules on).

### Q-FAB-15 — `FAB_DEPTH_STAGE_MAX` capped depth instead of ending a stage, and the plateau test compared one flush with another — **RESOLVED 2026-09-24: A STAGE ENDS ON THE PLATEAU TEST OR AFTER `depth_stage_max` CHECKS; `flush_loss` IS THE MEAN SINCE THE PREVIOUS PASS; `fab.depth_advance` SAYS WHEN**
The lever's help is "Depth-checks after which a stage ends regardless of the plateau test" and
`fabric/levers.py` records it as the fix for depth pinned at 1 on an underfit model; `FAB.manage` read
it only as `depth_now < min(hops, depth_stage_max)`. Driven over 60 checks on a loss falling 0.05 nats
per check: depth 1 at stage_max 2, 40 and 1000 alike; on a flat loss stage_max=2 capped depth at 2.
**Ruling:** the old tree's rule (self_organize.py:2533): a per-stage check count `depth_seen` on
`pop.growth` (so it crosses a resume), advance when `depth_wait >= depth_patience` OR
`depth_seen >= depth_stage_max`, ceiling `hops` alone (forward keeps its own `2 + n_live // 2` walk
cap). `fab.depth_forced` (seeded only when the curriculum is on) counts the advances the cap decided;
`fab.depth_now` on the ledger now follows the population. **After:** falling loss, stage_max 40 →
depth 2 at check 40 (forced); stage_max 2 → depth 4 by check 7; flat loss at stage_max 2 → depth 4.
**The plateau test's input** was one raw flush loss 500 windows from the previous one, against
`FAB_DEPTH_EPS`'s own "smoothed flush loss": over the last 100 flushes of a default 300-window run one
flush's loss has a standard deviation of 1.61 nats (2.32 bits) against a 0.01-bit threshold. The root
now passes the **mean of the flush losses since the previous pass**. **The new gate
`fab.depth_advance`** is an UNREACHABLE prediction at build ("no fab.manage pass has run yet … the
earliest advance is check 7, window 3500") and after each pass prints the stage's check count and
the window by which the cap forces the next advance, so a default run reads why it stayed at one hop.
**Rejected:** reading `pop.growth['slow']` as the smoothed loss (it is not advanced at `FAB_GROW=0`);
adding the `2 + n_live // 2` cap to `depth_now` (it would couple curriculum state to population size).
Changing the ceiling is a behaviour change for anyone who used a small stage_max as a depth cap.

### Q-FAB-16 — the identity round trip trained a fixed prefix of 256 experts — **RESOLVED 2026-09-24: A ROTATING BLOCK OF 256, KEYED ON `fab.ident_trained`**
`aux += ae_w * _ae_loss(pop, min(n, 256), …)` scored `A[:256]` on every pass: the gradient of the exact
aux expression reached rows 0..255 and nothing else. After 200 default windows the prefix carried
4.65e-3 B power against 5.36e-4 for rows 256..2047, was selected 0.40 against 0.74 per expert, and
`edec` — which decodes nearly every spawn — reconstructed the prefix at 0.434 relative error and the
rest at 0.842. **Ruling:** `_ae_rows(n, passes)` takes rows `(passes*256 + 0..255) mod n`, `passes`
being `fab.ident_trained` (checkpointed, and not the window step, which advances `batch_windows` at a
time and would visit few offsets). Every live row is scored once per ceil(n/256) passes; at n ≤ 256 it
is exactly the old prefix, so every test-width result is unchanged. **After** (same run): B power
7.52e-4 / 7.93e-4, selections 0.68 / 0.72, reconstruction 0.729 / 0.723, newborns 0.291 (0.444
before). **Rejected:** the round trip over every live row (8x the cost the comment capped, and
`F.mse_loss`'s mean would cut each row's gradient ~8x and silently retune `FAB_AE_W`); a seeded
permutation (the same coverage plus a draw a lever could shift).

### Q-OPT-9 — the epoch roll never reached `OPT.maybe_step`, and one roll was counted once per flush — **RESOLVED 2026-09-24: THE ROOT STAMPS `System.shift_at_steps = units.Steps(clock.opt_steps + 1)` BESIDE THE WINDOWS TWIN; BOTH PACKAGES COUNT ONE NOTIFICATION PER DISTINCT STAMP**
LOOP_ORDER's E row has always said the root stamps `clock.opt_steps` as the `shift_at` maybe_step
consumes; the loop stamped only `System.shift_at_windows` and called `maybe_step` with no `shift_at`.
Driven at `RUN_EPOCHS=2 DATA_RESAMPLE=1 OPT_LR_SHIFT_WARM=20 DATA_STREAM_BYTES=30000` (315 windows,
roll at 157): `opt.shift.notifications 0`, `opt.lr.shift_warm_applied 0`, while
`fab.shift_notifications` read **158** for the one roll. **Ruling:** a fifth System slot,
`shift_at_steps`, stamped at the roll off `clock.opt_steps` (seeded from OPT's restored count since
Q-RUN-9) and passed on every stepped flush; `maybe_step` counts a notification only when the stamp
differs from `st.shift_at`, and `grow_check` only when it differs from `pop.growth['shift_seen']`,
where FAB now keeps the stamp — so the blackout is measured from it even when a resumed root holds
none. **After:** `opt.shift.notifications 1`, `opt.lr.shift_warm_applied 19`, `fab.shift_notifications
1`. **19 was one short, corrected later on 2026-09-24:** `maybe_step` increments `opt_step` before it
prices the step, so a stamp of `clock.opt_steps` (the steps already taken) put the first post-roll
step at `step − shift_at = 1` — the ramp skipped its first rung, re-warmed W−1 steps, and
`OPT_LR_SHIFT_WARM=1` was fully inert (notifications 1, applied 0). The stamp is now
`clock.opt_steps + 1`, the step the shift applies to, as the old tree stamped it; WARM=N re-warms N
steps (driven at `DATA_STREAM_BYTES=12000 RUN_EPOCHS=2 DATA_RESAMPLE=1`: WARM=1 applied 1, was 0;
WARM=20 applied 20; `tests/test_fabric_internals.py` I9 pins WARM=1). The retok and LR-restart stamps remain undriven, and the gate reasons now say so instead of
"NOBODY IS SUPPLYING shift_at". **Rejected:** clearing the stamp after maybe_step accepts it (OPT
already keeps it; the edge belongs in the package that counts it).

### Q-DOM-2 — `DOM.on_retokenize` had no call site, so `DOM_TOKC_DECAY` was inert everywhere — **RESOLVED 2026-09-24: AN `E` ROW, DELIVERED AT THE EPOCH ROLL WHEN THE MATCH TABLE MOVED SINCE THE LAST SEGMENTATION**
The roll re-segments at the grown vocabulary and told only MEM. Driven at `RUN_EPOCHS=2
DATA_RESAMPLE=1 DATA_STREAM_BYTES=40000`: vocabulary 518 at the roll, `on_retokenize` calls 0,
`part.n_retok_events` ABSENT — this tree's "unreachable" on an arm that had just re-segmented — and
the per-domain histograms mixed two segmentations. **Ruling:** `("E", "DOM", "on_retokenize")` after
`begin_epoch`, in `_CALLS["E"]`, called when `Vocabulary.rev` (the monotone match-table revision
`tokenize`'s own staleness stamp reads) moved since the last segmentation. **After:** events 1,
decays 1, 12 domains decayed; with minting off (`TOK_GROW_EVERY=0`) the roll's warning says DOM was
not told and why, and the keys stay absent (`part.n_retok_events` reads present-and-0 there since the
second follow-up below). **Why gated when MEM is not:** DOM's histograms are over
token ids, which mean the same text at an unchanged table, so a decay there discards valid counts;
MEM holds ids AND byte offsets into the previous epoch's stream, which the redraw invalidates either
way. **Rejected:** calling on every roll (decays valid counts; the verifier's caveat); gating on
`tok.mint` alone (misses retirements and reinstatements, which also move the table); a loop-side
book for skipped rolls (the roll warning already states it per roll). Only the report's
`DOM.prior(live)` numbers move in multi-epoch runs — nothing in training reads the prior.
**Two follow-ups (later on 2026-09-24).** (1) *A resume.* The child re-segments at the SAVED
vocabulary, so when the parent's table had moved since its last segmentation (mints after its last
roll) the restored histograms were counted under a table the child's stream is never cut at — and
`_rev_at_last_seg` started from the child's own revision, so DOM was never told and the roll warning
called the histograms valid (driven: `DATA_STREAM_BYTES=40000 RUN_EPOCHS=2 DATA_RESAMPLE=1
TOK_GROW_EVERY=50 TOK_FREEZE_AT=120`, a 150-window parent with 2 mints; the resumed run's
`on_retokenize` calls 0). The loop now writes `payload['LOOP']['seg_table_moved']`, and compose sets
`System.rev_at_last_seg` to −1 when it is true, so the child's first roll tells DOM and its warning
says the parent's histograms were under another table (after: calls 1, `n_retok_events 1`,
`n_retok_decays 1`). The first roll and not compose, because `on_retokenize` is an `E` row; the child's
pre-roll windows therefore add new-table counts to old-table histograms until that roll decays both.
A checkpoint written before the field carries no answer, and the roll warning says the provenance is
unknown. (2) *The G4 reading of a roll that did not tell DOM.* `part.n_retok_events` was ABSENT
there — "unreachable" on an arm that could retok and had rolled. The root now seeds it at every roll
before the test (the `tok.due_merged` precedent), so it reads present-and-0; ABSENT means no roll.

### Q-DOM-3 — `DOM.rekey` ran before the encoder stepped, and on the frozen-bigram arm — **RESOLVED 2026-09-24: AFTER `observe`, ONLY AT `SIG_MODE=learned`, AS THE ROW ALWAYS SAID**
The row reads "the arm test is SIG.mode == 'learned' … AFTER observe"; the loop asked the cadence
first in the `A` block and made no arm test. Driven at the first fire of a default run: the order was
`dom.manage, rekey, train_step, encode, observe`, so the partition was re-keyed against an encoder
the same window's `SIG.train_step` then moved; `SIG_MODE=bigram` over 260 windows read
`n_rekey_passes 1`, `n_radius_measured 3`. **Ruling:** the rekey block moved below `DOM.observe` and
the `since_boundary` update, and `SIG.mode == "learned"` is tested BEFORE `Cadences.due` so no fire is
recorded for a rekey that cannot run (`dom.rekey` reads `checks=0` on bigram, the ledger's own
"never evaluated"). **After:** `observe, rekey, encode…` in one window; bigram `n_rekey_passes`
ABSENT. **Cost, stated (corrected later on 2026-09-24):** on `SIG_MODE=bigram` no radius is ever
measured **and there is no pooled radius either** — only the rekey measures one — so every radius-arm
re-entry is decided against `DOM_SPAWN_DIST` (`part.n_bootstrap_spawn_dist`), not "the pooled
bootstrap" this sentence first said; `DOM_RADIUS_Q`, `DOM_RADIUS_MULT` and `DOM_RADIUS_CAP` are inert on
that arm. Driven at `SIG_MODE=bigram DATA_STREAM_BYTES=120000`, 260 windows: `n_bootstrap_radius 0`,
`n_bootstrap_spawn_dist 98`, pooled radius 0.0 (the tree before this ruling, as driven in its review: rekey 1,
`n_bootstrap_spawn_dist 82`, pooled 0.395; the loss curves are identical, sum 1460.0561). That is
the archive's bigram control (`if SIG_MODE == "learned" and SELF_ORG: asm.rekey(enc)`,
`self_organize.py:6689`): without a rekey its `_r` stayed None and re-entry fell through to the
`NEW_DIST` threshold (`self_organize.py:3536-3546`), which is what `DOM_SPAWN_DIST` ports, and every
recorded bigram number was taken so.
**Rejected:** keeping the rekey on bigram for its radius (it would make the control differ from its
recorded self and from the contract's row; re-opening that is a separate owner question about what
the control controls for). **Measured on the shipped `learned` arm:** the default 300-window run's
loss curve is bit-identical; the rekey now encodes 170 reservoir windows (the rekey window's own
sample included) against 169, `pooled_radius` 0.05454 → 0.05455 and `n_bootstrap_radius` 3 → 2. A
two-epoch run (`DATA_STREAM_BYTES=40000`, 418 flushes) moves in its last digits (final flush loss
4.586279 → 4.586286).

### Q-TOK-14 — the gated-call-site report counted Dues, not calls, and TOK seeded counters on arms that cannot fire — **RESOLVED 2026-09-24: PER-CALL KEYS, ONLINE-ONLY SEEDING, `due_merged` SEEDED BY THE ROOT**
Driven: `OPT_BATCH_WINDOWS=4 TOK_GROW_EVERY=2` printed "TOK.mint_burst: fired 19 time(s)" for 10
calls; `TOK_MODE=fixed` printed "ARMED BUT 0 … never came due in this run's length" and
`tok.mint_frozen_at=30`; `TOK_MODE=fixed TOK_PROBATION_USES=3` printed "judge_probation: fired 1"
beside `tok.probation_judged 0`; the gated lines printed "(TOK_PROBATION_USES=0 makes it
unreachable)" on a run with 3; `tok.due_merged` was present-and-0 at `batch_windows=1`.
**Ruling:** `tok.mint_bursts` and `tok.probation_calls`, bumped on entry to `mint_burst` and
`judge_probation`, seeded by `on_window` beside their cadences and read by `spine/loop.py::_GATED`;
every cadence counter, `tok.due_dropped` and `tok.mint_frozen_at` seeded only at `TOK_MODE=online`,
and the probation Due AND-ed with it; `tok.due_merged` seeded by the root at the second window of a
batch, only when TOK seeded a cadence key; `TOK(vocab.gates)` rendered at R, so
`tok.probation_embed`'s "unreachable (no residual_ratio supplied)" reaches the report beside a
judge_probation call count. **Rejected:** `tok.due_mint − tok.due_merged` (due_merged counts a merge on
any key and goes negative); refusing `TOK_PROBATION_BY=embed` at `LM_COMPOSE=0` at compose (the
tree already rules that a legal configuration, `tok/api.py::judge_probation`; the report now says
what it did instead).

### Q-CAP-4 — the R-stage `cap.clamp` said "an armed arm has room" at `CAP_TARGETS=off` — **RESOLVED 2026-09-24: THE STARTUP `dead_facts` ARE KEPT ON THE VALVE AND PASSED AT R**
`CAP.counters` rebuilt the gate without `dead_facts`, so its UNREACHABLE branch could not open, and
`valve.gates` (where the startup line says UNREACHABLE) is never rendered. **Ruling:**
`Valve.clamp_dead_facts`, set by `new_valve` on every build (a resume's included) and not carried by
`CAP.state`; `CAP.counters` passes it. **After:** UNREACHABLE at R on `off` and `vocab`, matching the
startup gate. **Rejected:** recomputing the facts from the current caps at R (after a lift to the
ceiling it reads `at_ceiling` and claims the startup analysis refused a lift the run took); reusing
`valve.gates`' gate at 0/0 only (leaves the lifts > 0 clauses without the startup facts). Beside it,
an arm `CAP_TARGETS` does not name now reads origin "off for this arm (…)" instead of the sentinel's
"no room to earn" sentence; the cap value is unchanged.

### Q-RUN-13 — startup refusals were a list `compose()` built past, and two unbuilt arms died at the first flush — **RESOLVED 2026-09-24: `compose()` RAISES `RefusedRun` AT THREE STOP POINTS; `LM_COMPOSE=1` AND `MEM_KEY_SRC=frozen` ARE REFUSED AT BUILD WITH `NotBuilt`**
`RUN.startup_refusals` said "the entry point raises on a non-empty list BEFORE ANY TENSOR IS
ALLOCATED" and `compose()` only appended it: driven at `RUN_EPOCHS=2` with resampling off, it built
the 10,130,057-parameter model, ran the SIG warm-up and returned `stage='assembled'`; only run.py read
the list (the `loop.run` guard of Q-CKPT-4 stopped the training, not the build). **Ruling:**
`spine/compose.py::RefusedRun(RuntimeError)`, carrying the partial System, raised by
`_stop_if_refused` at (1) the `refuse` stage — RUN/WORLD refusals depend on Configs alone, so they
now fire before geometry and before any model tensor; (2) after `CAP.startup_refusals`, which needs
the built population and therefore cannot precede allocation (a refused LM restore stops here too);
(3) after the finished-resume check, before the SIG warm-up (a refused OPT restore stops here).
**Each stop pre-empts the later ones, so "every refusal in one run" holds only within a stop point**
(stated later on 2026-09-24; this paragraph and the code comments had claimed it for the whole
configuration): driven at `RUN_EPOCHS=2 CAP_FAB_START=100 CAP_TARGETS=experts`, `compose` raises at
`refuse` with the RUN refusal alone, and the CAP refusal appears only on the next attempt — the tree
before this ruling reported both at once, after building everything. The trade is deliberate: stop
(1) is what keeps a Config-only refusal from allocating the model, and CAP's and the restores'
refusals need that allocation. Collecting CAP's Config-only clause (a cap ≤ 0) at stop (1) would
recover the common pair and needs a CAP entry point split; it is left to the owner. A
System `compose()` returns carries no refusal; `loop.run` raises the same type for one built another
way; run.py catches it, prints the banner and every `REFUSED:` line and exits 2 as before. **This
supersedes Q-CKPT-4's rejected alternative** ("raising at the `restore.lm` stage … turns a named
refusal into a traceback"): the exception carries the System, so nothing is lost. **Rejected:**
raising at every append (one refusal per attempt even within a stop point); keeping the
list and guarding only `loop.run` (the warm-up — 800 steps at the shipped `SIG_WARMUP` — is spent
before a refused run stops). **Two declared-and-not-built arms** composed with 0 refusals and raised
`NotBuilt` at the first flush, after the whole warm-up: `LM_COMPOSE=1` (`_LM.composed_table`) and
`MEM_KEY_SRC=frozen` (`MEM.write`). `LM.build_model` and `MEM.open_store` now raise `NotBuilt`
naming the lever before allocating — the owning package, the `FAB_HOP_MODE=transition` precedent
(Q-FAB-1), and run.py already prints `NotBuilt` as `REFUSED:` with exit 2. **Rejected:** a string on
`System.refusals` written by the root (the root would be re-deriving a package's arm).
*(2026-09-27, Q-DATA-9: a continuing mid-epoch resume has a fourth stop, at the `segment` stage,
before the log's replay — a hold-out admission and a redrawn stream that is not the parent's are
refused there, since neither needs the model. The three above are unchanged.)*

### Q-RUN-14 — a non-finite loss stepped the optimizer and nothing stopped a non-finite checkpoint — **RESOLVED 2026-09-24: THE LOOP STOPS BEFORE THE STEP; `CKPT.save` SCANS THE PAYLOAD; THE LAST FINITE STATE IS KEPT. NOT A DIVERGENCE ALARM**
Driven before: one flush with a nan loss stepped AdamW on nan gradients, **8 of 8** LM tensors went
non-finite, and the run died a flush later inside `DOM.note_competence` ("`bits` is nan for domain 1")
— a refusal naming domain competence, not the loss, the step or a lever. A single finite loss of
`1e30` completed a 20-window run and wrote `ckpt.pt` with **inf `exp_avg_sq` in every base group
entry** (grad² overflows fp32), which freezes those parameters for every resume (`m / sqrt(inf) = 0`).
**Ruling:** `spine/gate.py::NonFinite`. (1) `spine/loop.py::_flush` forms `isfinite(total)` before
the backward and reads it after (the host waits on the backward it just enqueued rather than
stalling between forward and backward; `OPT.maybe_step`'s grad-norm read syncs at the same point),
and raises before `note_backward`/`maybe_step` with the window, flush, optimizer step, epoch, the
non-finite terms and the likely lever (`OPT_LR` with the last applied rate and grad norm, or the term's
own weight lever). (2) `CKPT.save` scans every floating tensor in the payload and `best_state`
(python floats are exempt: counter dicts carry legitimate `inf` readings) and raises before the file
is touched, counting `refused_nonfinite`; `spine/loop.py::_save` turns that into a run warning and
the run continues (the 1e30 case above now ends with its report and "a checkpoint was NOT written
-- … /payload/OPT/base/state/0/exp_avg_sq (16384 of 16384) …" instead of an inf-moment `ckpt.pt`). (3) On (1), the loop attempts the `final` save of the
pre-step state — the Q-RUN-9 principle that a stop is a reason to distrust what follows, not to lose
what came before — and (2) refuses it if the forward already poisoned something (driven: an inf
signature wrote nan into `FAB.A`/`B`/`cent` inside `FAB.forward`, and the save named them).
run.py prints `=== RUN STOPPED:` and exits 3. **Measured before the scan shipped:** zero non-finite
tensors in the payloads of a 250-window default run and three other arms, so the scan refuses
poisoned state, not sentinels. **Rejected:** checking before the backward (an extra host sync
between forward and backward on every GPU flush); scanning only parameters (a nan MEM key, DOM
centroid or AdamW moment is the same permanent forgetting); a divergence alarm on a finite loss
(EVAL's, deferred — `OPT_LR=0.9` at loss 708 still runs).
**Two follow-ups (later on 2026-09-24).** (4) *The 1e30 case was caught only on the save path*: the
run itself trained on with 29 of 123 optimizer state tensors non-finite, silently at the default
`CKPT_DIR` (rc 0) and with every later save refused where one was set. `OPT.maybe_step` now refuses
a due step whose base gradient norm — the one it already read, so no new sync — is non-finite, or at
or above √(the parameters' dtype max) with `OPT_GRAD_CLIP` off (some g² would overflow the second
moment): it raises `NonFinite` before `opt_step` advances or a rate is written, counting
`opt.step.refused_nonfinite`, and the loop's existing path saves the last finite state (driven: the
1e30 flush now stops at optimizer step 10 with 0 non-finite optimizer tensors and the pre-step
`final` checkpoint written). (5) *The stopping save's backward count was one high*: `scaled_backward`
had counted the nan pass before the loop raised, and `note_backward` had not, so the final checkpoint
carried OPT `n_backward` 8 against the clock's 7 (driven at `OPT_ACCUM=3`, nan at flush 8) and a
resume, which seeds the clock from OPT, phase-shifted its first group. The loop now un-counts that
pass (`n_backward`, `opt.backward`) and drops its gradients before the save: saved 7, clock 7.

### Q-RUN-15 — end-of-run partial batches, `RUN_PROFILE`, and two counters present on arms that cannot reach them — **RESOLVED 2026-09-24**
(a) **A partial batch at the end was silent.** The finishing roll drops it into `dropped_windows`
but `finished` is tested before `rolled`, so the mid-run roll's warning was unreachable; a
`max_windows` stop leaves one no roll counts (driven: `OPT_BATCH_WINDOWS=16`, 157 windows, 13 never
reached a backward, and nothing said so). **Ruling:** one check after the loop covers both exits;
`RunResult.never_backward` = `dropped_windows` + the batch a `max_windows` stop left; run.py prints
it on its own line when non-zero, so the `=== N windows, …` line keeps the shape `sweep_gpu.sh`
parses; `RUN.RunClock.counters` is rendered at R (it was in `_CALLS` and rendered nowhere).
(b) **`RUN_PROFILE=1` was inert:** no span was opened and `bench_summary` got no Timing. **Ruling:**
spans around the per-window calls, the flush and six calls inside it (`flush/…`), and the periodic
save; the Timing reaches `bench_summary` and an R row `RUN.Timing.spans` when profiling (so profile
without bench still prints). On CUDA a span synchronises at both ends (the lever's own condition for
attributing kernel time). Off, every span is the shared no-op and the run is bit-identical.
(c) **G4 on two off arms.** At `SIG_MODE=bigram` the encoder group is empty and
`opt.lr.writes.encoder` read 12; it is now seeded only when the group holds a parameter and the
report says UNREACHABLE. At `FAB_SPAWN=0` `fab.spawned`/`fab.spawn_declined` were present-and-0 beside
gate `fab.spawn` reading UNREACHABLE; they are now seeded only when `FAB_SPAWN` is on. **Not changed,
on existing rulings:** gate `fab.on` at `FAB_ON=0` (ruled a switch read false, `fabric/api.py::build`),
`fab.lr_own` at `FAB_LR_OWN=False` ("an ARMED arm that chose not to scale", `own_lr_scale`) and
`fab.growth_armed` at `FAB_GROW=0`, whose `grow_check` family is seeded on that arm the same way.

### Q-EVAL-12 — the retention probe: what it reads, through which closure, at which routing clock, and who consumes its readings — **RESOLVED 2026-09-27 (Proposal 04 SR0 and NEW-03; register §8 3.1/3.2): BUILT OFF AT `EVAL_RETENTION_EVERY=0`. TWO NEW LEVERS, BOTH CENSUS AMENDMENTS; `EVAL.holdout_probe` MOVES; `EVAL.pin_holdout`, `EVAL.retention_period` AND `EVAL.blowup` ARE NEW; `_logits_fn`'s TWO CLOSURES ARE WRITTEN. NO WIRE**
**What was asked.** Goal B is decided on held-out readings taken *during* training, and the tree
had none: `EVAL.holdout_probe` was deferred for want of `units_by_domain` and a `logits_fn`, so
`CKPT.Retention.consider` never heard a value, `OPT.maybe_step`'s `best_bpb` had no producer, the
blow-up alarm had no series and `EVAL.generate` had no prompts. Proposal 04's SR0 fills
`holdout_probe` as the retention probe and ships it ON only after a test proves it is telemetry;
NEW-03 binds the closures, generation, the consumers and the blow-up Reading to the same commit.

**The ruling, as built.**
* **The levers.** `EVAL_RETENTION_EVERY` (`U.Windows`, built **0**: the whole subsystem off — no
  `ProbeSet`, no stream, no reading, no consumer input, no generation; 04-6.2's 1000 plus
  phase-start reads flips in its own commit) and `EVAL_RETENTION_N` (6 per arrived area, split 3 + 3,
  domain `(1, None)`). `EVAL_HOLDOUT_WINDOWS` (32) is now the BOUNDARY reading's size. A negative
  `EVAL_RETENTION_EVERY` is refused by `EVAL.retention_period` under this package's
  `REFUSE_NEGATIVE_PERIOD`; `_periods` carries it as `'retention'`, the seventh gate.
* **The pinned windows (`EVAL.pin_holdout`, the `probe` ASSEMBLY row after SIG's restore row).**
  Each area's held-out block (`Areas.holdout`) splits at its **midpoint** into **control** (first
  half) and **report** (second half). Each (area, half) draws its window starts once, sequentially
  and without repeats, from `rng_for("eval.holdout.<derive.stream_key(area)>.<half>", seed)`, in
  `[prefix_bytes, half_len - window_bytes]` — so a window **and its routing prefix** stay inside one
  half and neither half reads the other's text. A half draws the larger of its share of
  `EVAL_RETENTION_N` and of `EVAL_HOLDOUT_WINDOWS` (the odd one to control); both readings take the
  **first n**, so the cadence items are a prefix of the boundary items and the two are paired too. A
  short half records `shortfall`; a half that cannot hold one window behind its prefix draws nothing
  and mints no stream, an area neither of whose halves can is left out of `items`, and where no half
  anywhere can the `ProbeSet` is empty, its reason naming the geometry, the halves and
  `DATA_HOLDOUT_FRAC` / `DATA_VAL_CAP` — the probe unarmed (the review, below). **Geometry:**
  `window_bytes = LM.ctx + 1` — a window of ctx+1 bytes tokenizes to at most ctx+1 ids, so its
  inputs fit the model's context at any vocabulary — and `prefix_bytes` = the SIG width. Both are
  recorded in `LOOP.eval`, so a resume re-pins its parent's windows even where its own geometry
  moved.
* **Who is read.** The arrived set: the areas live in every phase this run has entered, plus, on a
  resume, the parent's arrived set from `LOOP.eval` — or, for a parent that armed no probe (one
  before the probe, or one run with it off, whose `LOOP.eval` is at most the geometry and the
  book's counts it inherited — the review, below), `Areas.parent_names`, **assumed** and said so
  in a warning, and on a continuing resume the areas of the phase the parent's last window fell in.
  An area whose phase has not begun is left out (`eval.holdout.areas_unarrived`, a gauge); its
  reading would be of text the run never trained on. Each row carries `seen_by_parent`.
* **The closures (`spine/compose.py::_logits_fn(sysm, *, use_memory)`, Q-MEM-10's ruling carried
  out).** **Convention: `fn(x, *, prefix_bytes) -> (B, L, V)`**, x the token ids and
  `prefix_bytes` the bytes before each row's first byte. The path is the flush's: `SIG.encode` on
  the width_units units ending at the window's first byte (left-padded like `_sample_window`'s
  opening windows; under `SIG_SPACE='tokens'` the byte prefix is cut at the view and yields fewer
  tokens than width_units, so that arm's signature is more padded than a training window's — a
  known approximation on an arm the tree does not ship), then **`DOM.nearest`** (Q-DOM-6: the id
  `DOM.observe` would assign, with nothing written; **-1** where it would spawn, which bans exactly
  what a newborn id would, counted `eval.holdout.domain_spawn`), then under `Process.autocast`
  `LM.embed`, `WORLD.forecast`, `LM.encode(extra=)`, `FAB.forward(training=False)` with the head
  (wrapped to count decodes), `targets=None`, **novelty ZEROS** (named: the one datum with no honest
  source off the training path — a held-out window has no previous flush), `System.live_domains` —
  and **`step_windows = clock.step + 1`**. Then the vote's logits, or `LM.decode` of the routed hidden.
  All under `no_grad`, every module put in eval mode and each submodule's own mode restored.
  `use_memory=True` adds `softmax → MEM.encode_queries → MEM.read(promote=False) → MEM.blend → log`
  with the `(B*L, key_dim)` reshape; each reading names its closure (`memory-off`, `memory-on`). At
  `MEM_BLEND_MAX=0` `MEM.blend` hands back the model's distribution itself and the memory-on closure
  returns the memory-off logits unchanged — not their log-softmax, whose rounding would part the two
  closures' generations at a boundary draw.
* **Why `clock.step + 1` (the routing clock).** FAB's identity cache hands a pass at the SAME step
  the keys the training pass computed **before** the optimizer stepped. At `clock.step` an in-run
  reading therefore routed on stale keys while a resumed child, whose cache is empty, computed fresh
  ones — so a start reading could never equal the uninterrupted run's reading at the same weights.
  At `+1` the keys are recomputed at `FAB_EMB_EVERY=1` (shipped) and are the next window's cached
  ones at larger values; nothing else `FAB.forward` reads from the step moves on an eval pass
  (`_ae_rows`, spawn and the learn guard are learn-gated; the anneals are aux-loss only).
* **The view.** `tokenize_fn` is `TOK.tokenize` at the view the stream was **last cut** at
  (`seg_log`'s last event), `labels=None`, `regularize=False` — no draw, no cache, counted
  `tok.segment_remap` and booked `eval.holdout.cuts`. The live table would score a window in a
  segmentation the run never trained on.
* **When it reads.** At B, after the flush and the act and before the checkpoint gate: the **arm
  test first** (a pinned `ProbeSet`), then `Cadences.due('retention', ...)`, plus a **phase-start
  read** at the first window of every phase k ≥ 0 of every epoch (the window's first byte against
  `Stream.phase_bounds`, against the (epoch, phase) `LOOP.eval` last read — or, on a continuing
  resume whose parent recorded none, the phase of the parent's last window, so only a real phase
  change reads: the review, below) — one memory-off reading of `EVAL_RETENTION_N` per arrived
  area. **Boundary readings** — `EVAL_HOLDOUT_WINDOWS` per area, both closures — happen at **R**
  (inside the guard that saves when R raises) and at a **resume's start**, and nowhere else. The
  start reading uses the **parent's** last-cut view and live-domain count from `LOOP.eval`, so at
  the same weights it equals the parent's final R reading (**like for like**); a later reading's
  difference is what this process changed. Boundary readings are
  reported, **never consumed**. A continuing resume reproduces every memory-off reading the
  uninterrupted run takes; its later memory-on readings do not, because MEM's rows depart after any
  continuing resume (`memory/api.py::maintain` retakes its rekey snapshot rather than checkpointing
  it — recorded in `tests/_state_digest.py` before the probe existed, not repaired here).
* **Who consumes, and what.** Consumers read the **control mean** of a cadence or phase reading,
  as `Reading(value, seed_count=1, at=step)`, and only when finite (the rest are not forwarded:
  `eval.holdout.nonfinite` counts those where a control window scored non-finite,
  `eval.holdout.empty` those whose control half scored no window at all):
  `CKPT.Retention.consider` (its `BestAction` saved on the spot, `_carry()` first, then
  `Retention.note_saved` — Q-CKPT-6), `EVAL.blowup` (reports only), and
  `System.probe_reading`, the next flush's `best_bpb` (Q-OPT-13). The report half feeds nothing.
  **The all-area mean drifts with the arrived set, and only the alarm corrects for it.** An arriving
  area's held-out text is text the run has barely trained on, so the mean steps up at each arrival;
  the blow-up series re-arms there (below), while `Retention.consider` keeps judging every reading
  against the best so far, so on a phased run the `.best` checkpoint stays at a pre-arrival reading
  — driven in `tests/test_probe.py` P6: best at window 41 of 200, `num` arriving at 80 and no later
  reading beating it. Recorded, not repaired: the plan's R7 sends the gates NEW-04 builds to the
  per-area rows.
* **`EVAL.blowup`.** blowup_test.py's call-site rule over each area's control series and an
  all-area series that **re-arms at every arrival** (the mean steps up when an area arrives, so the
  stale-80 rule would otherwise fire ~80 readings after it on a healthy run); its horizon is
  `derive.blowup_horizon` — `blowup_stale`'s own `stale` default read off its signature, times the
  period through `derive.windows_for_readings` — because O11 refuses that arithmetic elsewhere.
* **Generation.** `EVAL.generate` after the **final save**, through both closures, on report-half
  prompts cut at the last-cut view, drawing by inverse CDF from `rng_for('eval.generate', seed)`,
  minted **once per System** at the `probe` stage (a second `loop.run` would otherwise raise
  `RngError`). **The closure owns generation's window and prefix**: handed more than `LM.ctx` tokens
  it keeps the last `LM.ctx` and appends the dropped ids' bytes (`TOK.Vocabulary.decode`) to the
  prefix, because EVAL can read neither. Each `Sample` row records the prompt window's bytes as
  `prompt` — the text the model continued — and the routing prefix before it as `prefix` (the
  review, below). **Generation's closures are capped at the live vocabulary**
  (`live_vocab = TOK.Vocabulary.size()`, every id at or above it set to `-inf` after the whole path):
  at the shipped `LM_MASK_DEAD_ROWS=0` a never-minted row keeps some mass, and one drawn has no bytes
  — driven, a 30-window run's generation drew one and `decode` raised after the final save, taking
  the report with it. The frozen tree's `vlim` ("never sample untrained ids"). Readings never pass
  it: they are scored on the distribution the run trains on.
* **The books.** `System.eval_books`: `eval.holdout.{calls, cadence_reads, phase_reads,
  boundary_reads, resume_reads, windows, cuts, forwards, decodes, sig_calls, areas_unarrived,
  shortfall, nonfinite, empty, domain_spawn}`, `eval.mem.{reads, key_encodes, empty, blends}` (one
  read, one blend per memory-on pass; `key_encodes` counts the query **rows** those reads encoded,
  `B·L` each, not calls), `eval.blowup.fired` (and `since_best`, a gauge) — **ABSENT** unarmed,
  **PRESENT-and-0** armed;
  `eval.holdout.seconds` and `eval.mem.blend_weight_sum` are floats outside the integer channel and
  the seconds are never checkpointed; `eval.generate.{samples, tokens}` ABSENT at `EVAL_GENERATE=0`
  or with no `ProbeSet`. Generation's own closure passes are counted there and **only** there — one
  forward per generated token per closure — and the rest of the book is put back as R read it,
  because the package rows were read at R, before generation, and the accounting below pairs the
  two. (A second `run()` over one System — a test's shape; `run.py` makes one call per process, and a
  checkpoint is written before generation — therefore reads the first call's generation passes in
  the package rows and not in the book.) The root seeds `fab.eval_passes` when armed (Q-FAB-17). The gated-call
  report reads `eval.holdout.calls` and `eval.generate.samples`.
* **THE SIGNATURE MOVE, AND ONE DEPARTURE FROM THE PLAN THAT WROTE IT.**
  `holdout_probe(ev, *, units_by_domain, logits_fn, tokenize_fn, step, boundary=False,
  previous=None)`. `rng` left (the draw is `pin_holdout`'s, made once); `tokenize_fn` arrived because
  EVAL may not import TOK. **`step` is the departure**: the plan's signature had none, and the
  Readings it returns carry `at` — the window, which EVAL owns no clock to know. It is the Q-EVAL-11
  precedent exactly (`curve_probe` gained `step` for `CurveReading.step`).
* **THE EXACT-ACCOUNTING AMENDMENT OF `docs/proposals/04_SELF_REGULATION.md:1396-1397`.** That line
  asks for "every counter but `eval.*` and `tok.segment_remap`" equal with the probe on and off. The
  closures run the flush's entry points, and those count their calls, so the honest statement is
  exact rather than empty: **losses, parameters, optimizer state and every counter are equal, except
  the probe's own book and a named set each of which moves by exactly the book's own count** —
  `tok.segment_remap` by `eval.holdout.cuts`; `fab.eval_passes`, `lm.embed.*`, `world.forecast.calls`
  and `.inert` by `eval.holdout.forwards`; `lm.decode.calls` by `eval.holdout.decodes`;
  `sig.encode_calls` and `sig.encode_windows` by `eval.holdout.sig_calls`; `lm.encode.calls` by
  `eval.holdout.forwards` plus `eval.mem.reads` — one key-encode call per MEM read, because
  `MEM.encode_queries` encodes a pass's `B·L` query rows in one `LM.encode` call (this said "plus
  the memory-on closure's key encodes" until the review: `eval.mem.key_encodes` counts those rows,
  and the full epoch's 128 reads encoded thousands); `lm.encode.key_path_truncated` by
  `eval.mem.reads` where the key path truncates (the transformer at `MEM_KEY_DEPTH > 0`);
  `lm.mask.*` with the decodes at `LM_MASK_DEAD_ROWS=1` (`lm.mask.applied` by `eval.holdout.decodes`;
  `rows_masked` is a gauge); and `Retention.counters()`.
  `tests/test_probe.py` P1/P2 hold that set to it (`expected_delta`).
* **What it costs.** A reading is `EVAL_RETENTION_N` forwards per arrived area under `no_grad`;
  where `CKPT_DIR` is set, a `.best` checkpoint on every new best — the first reading of a run is
  always one — which owner fleets with `CKPT_DIR` pay in I/O (listed as a risk; `Saves.best` per run is
  what `tests/test_probe.py` P6 reads). CPU runs establish operation only.

**AMENDED 2026-09-27 — THE REVIEW OF THIS RULING.** Seven findings, each measured on the tree before
it (CPU, operation only). The five that moved behaviour are repaired and held by
`tests/test_probe.py`, each failing there on the tree before; the accounting sentence and the stale
prose are corrected where they stood:
* **A run the probe is off on carries none of its parent's reading state.** `LOOP.eval` passed
  through such a run unchanged, and it wrote the record into every checkpoint as its own, so a
  probe-on descendant read its grandparent's arrived set and last phase as its parent's — driven: a
  grandparent at `EVAL_RETENTION_EVERY=20` for 41 windows, a probe-off child for 150 across three
  phases, a probe-on grandchild; its start read left out `num`, which the child had trained, called
  `num` unseen by its parent, paired against a reading two generations old and read a phase start at
  its first window, with no ASSUMED warning. **Ruled:** an unarmed run keeps only the snapshot's
  `geometry` and its book's counts (the two gauges, `areas_unarrived` and `since_best`, dropped with
  the arrived set and the series they read), unchanged; a descendant re-pins the same windows,
  totals the lineage's book, and takes the ASSUMED path above for everything else.
  `System.eval_carried` is None only where the snapshot carried nothing (the 'probe' stage). P12.
* **Pairing is by item, not by position.** `holdout_probe` kept a half's finite values alone, so after
  one skipped window every later pair compared two different windows — driven on P14's planted case:
  one non-finite window in the earlier of two readings paired windows 10 with 20 and 20 with 30 (`n`
  2, mean −0.012, SD 0.255) where both true differences were exactly 0, and a window cut to fewer
  than two ids did the same. Each half now keeps **one slot per item read**, in pin order,
  `None` where the window gave no value (`<half>_nonfinite` counts the non-finite ones per area), and
  a pair is taken only where both slots hold one — a `previous` restored from `LOOP.eval` included,
  which carries the slots as they stood. P14.
* **A block with no room is no block.** With every half shorter than `prefix_bytes + window_bytes`,
  `pin_holdout` returned every area with two empty halves and no reason; the root counted that armed,
  and every reading scored nothing and was booked non-finite while the gated report said the probe
  fired and CKPT's inert reason blamed `EVAL_RETENTION_EVERY=0` or `DATA_SYNTH_HOLDOUT=0` — driven at
  `DATA_STREAM_BYTES=20000`: 250-byte halves against 192 + 129 bytes, 7 readings of 0 windows,
  `eval.holdout.nonfinite` 5. Now a half that can hold no window draws nothing and mints no stream,
  an area with no window is unpinned, and with none anywhere the `ProbeSet` is empty with a reason
  naming the geometry, the halves and `DATA_HOLDOUT_FRAC` / `DATA_VAL_CAP`, so the arm test fails and
  every row prints UNREACHABLE. An armed B reading whose control half scored no window is booked
  **`eval.holdout.empty`**, apart from `eval.holdout.nonfinite` — nothing was read to be non-finite —
  and CKPT's inert reason names every cause, the EVAL(holdout) row the one that held. P1's third off
  arm, P4 and P14.
* **A resume whose parent recorded no phase starts in the phase its parent stopped in.** A continuing
  resume from a parent that armed no probe had no last (epoch, phase), so its first window read as a
  phase start wherever it fell — driven: a probe-off parent stopped at window 41 and its probe-on
  child read `'phase'` at 42, mid-phase 0, with `eval.holdout.phase_reads` 1 and the consumers fed (a
  `.best` save with `CKPT_DIR`). The loop now seeds the record from the parent's last window —
  window `in_epoch - 1` of the replayed stream, its epoch and the phase its first byte falls in —
  and adds that phase's areas to the arrived set, seen by the parent. At `in_epoch` 0 (a fresh run,
  an epoch-boundary resume, a resume that replays its epoch from the first window) the first window
  opens a phase of the stream this process reads, and nothing is seeded. P12.
* **`lm.encode.calls` moves by `eval.holdout.forwards + eval.mem.reads`** (the accounting bullet
  above): the ruling said the key encodes, and `eval.mem.key_encodes` counts query rows —
  measured, a 120-window arm at 20 on the real source moved `lm.encode.calls` by 264 with 200
  forwards, 64 reads and 5,169 key-encode rows. `expected_delta` already used the reads.
* **Generation's rows name the text continued.** `Sample.population` rows recorded the routing prefix
  under `prompt`; they carry `prefix` and `prompt` (the window's bytes, which the root now hands
  beside the ids — EVAL has no vocabulary to decode them) apart. P9.
* **Stale prose the build left or re-edited**: `CAP.startup_refusals` is the **30th** of the 41
  `ASSEMBLY_ORDER` rows, not the 29th, and `compose(environ={})` no longer stops there or anywhere —
  it returns a System at stage `'assembled'` (§ executable-today, §3.8, `Q-DERIVE-1`,
  `capacity/api.py`, `spine/compose.py`, `spine/derive.py`, `ckpt/api.py`); `_head`'s "not formable
  today" (the probe formed it); `OPT.maybe_step`'s "`best_bpb` HAS NO PRODUCER" (it is
  `System.probe_reading`, counted once per `at`); and EVAL's negative-period switch, which governs
  `EVAL_RETENTION_EVERY` as well as `EVAL_CURVE_EVERY`.

### Q-OPT-13 — where the restart damping's held-out Reading comes from — **RESOLVED 2026-09-27 (Proposal 04 NEW-03): `OPT_DAMP_SOURCE`, BUILT `'off'`; `'probe'` HANDS IT THE RETENTION PROBE'S CONTROL MEAN; `st.reading_at` CHECKPOINTED. ⚠ ONE NEW LEVER, A CENSUS AMENDMENT. NO SIGNATURE MOVES, NO WIRE**
`OPT.maybe_step`'s `best_bpb` is the one held-out measurement that crosses back into a training
decision, and it had no producer. It has one now (`System.probe_reading`, Q-EVAL-12), and whether
it crosses is a lever rather than a consequence of turning the probe on. **`'off'` (shipped):**
`maybe_step` sets `best_bpb = None` before `_reading` reads it, so `opt.restart.readings` stays 0 and
the damping gate's reason names `OPT_DAMP_SOURCE='off'` (a new arm, ahead of the "no Reading has
ever arrived" arm, which would otherwise send a reader to EVAL for a Reading OPT declined).
**`'probe'`:** the Reading is `Reading(control mean, seed_count=1, at)`; one run is one seed, so every
losing restart is **refused** under PLAN 3.8 and counted in `opt.restart.damp_refused_n1` — the
restart amplitude never moves, which is what a single-seed run can honestly say. The root hands the
same Reading over on every flush until the next reading; a Reading whose `at` equals the last one
counted is that measurement re-delivered and counts **once** (the `opt.shift.notifications` rule,
2026-09-24), with `st.reading_at` on `OptState`, in `state_dict` and in `load_state` (absent → None).
**The Reading crosses a save too**: `LOOP.eval` carries the last forwarded one (`reading`) and the
loop puts it back on a resumed System that holds none, so a child's first flushes hand `maybe_step`
what the uninterrupted run's would — without it a continuing child read `None` until its own first
reading and, under `'probe'`, departed at the first restart inside that gap; the restored
`reading_at` keeps it counted once.
`'probe'` with `EVAL_RETENTION_EVERY=0` is **refused at startup** (`RefusedRun`, the `refuse` stage):
a source that can never produce is the armed-but-inert state this tree refuses by name. The backward
edge is written in the `maybe_step` row's note, not in `ROW_ARGUMENTS_ELSEWHERE`: `maybe_step` has
no required parameter, so K10 would report an entry there stale.

### Q-DOM-6 — the domain a held-out window would be routed to, asked read-only — **RESOLVED 2026-09-27 (Q-EVAL-12): `DOM.nearest(dom, part, *, signature)`, `_assign`'s DECISION FACTORED INTO ONE PURE HELPER. NO LEVER, NO WIRE**
The closures route windows the run did not train on, and `DOM.observe` advances the boundary clock,
drags a centroid, feeds the reservoir and counts the visit — a reading through it would move the
partition it reads. `_assign`'s three exclusive arms moved whole into `_decide(part, q, ...)`, which
returns `(kind, did, bumps)` and writes nothing; `_assign` applies the same drag and the same
counters in the same order (the drag now precedes the radius arm's bootstrap counters; they touch
disjoint state, and B3 reproduces its fixture). `DOM.nearest` applies the same decision to one
normalised signature and returns the id `_assign` would re-enter, the nearest at `d_expert_slots`,
**-1** where it would spawn (the empty partition included) and **0** at `DOM_ENABLED=0`. It skips the
boundary test — a held-out window is not the stream's next window — writes, bumps and draws nothing,
and its caller books the -1 answers. LEVERS READ: `enabled`, `accept_rule`, `spawn_dist`, `margin`;
WIRES READ: `d_expert_slots`.

### Q-MEM-15 — the report path's queries, and what a `promote=False` read counts — **RESOLVED 2026-09-27 (Q-EVAL-12): `MEM.encode_queries(mem, *, contexts, key_fn)`; A `promote=False` READ SEEDS AND BUMPS NO STORE COUNTER; `MEM.blend` HAS A BODY AND IS BOOKED BY ITS CALLER. NO LEVER, NO WIRE**
* **`encode_queries`** returns `(B*L, key_dim)` unit-norm queries, one per position, built from the
  `key_win` tokens ending at it (`_key_windows`) and encoded at `key_depth` (`_encode_keys`) — the
  write path's own helpers, so the report path queries the store in the key space it was written in.
  Flat because `MEM.read` takes 2-D queries; `MEM_KEY_SRC='frozen'` is refused as in `write`.
* **A `promote=False` read moves no counter** (amending Q-MEM-10's and `read`'s wording, which said
  it "still counts `n_reads` and the wrong_* trio"): the six are the store's ledger, which `census`
  and the `mem.pressure` Gate read as the in-package probe's retrievals, so a report-path reading
  would move the numbers that Gate judges (G7), and at `MEM_PROBE_EVERY=0` an unarmed report path
  would print them PRESENT-and-0 for a probe that cannot run. The wrong-flag **exclusion** still
  applies on both arms; only the count is the promoting read's. The caller books its own:
  `eval.mem.reads`, `eval.mem.empty`, `eval.mem.key_encodes` (the query rows `encode_queries`
  encoded, `B·L` per read in one `key_fn` call — so `lm.encode.calls` moves by the reads, Q-EVAL-12).
* **`blend`'s body** re-asserts the weight (read's ramp recomputed from `conf` under this Config's
  `match_floor` and `blend_max`, refusing a record that departs), returns `model_probs` untouched at
  `blend_max == 0`, mixes `(1-w)·p + w·dist` otherwise, and clamps and renormalises only rows at
  `w >= 1`. It writes no store counter; its declared `store.n_blends` / `store.blend_weight_sum`
  were never written, and the closure books `eval.mem.blends` and `eval.mem.blend_weight_sum`.

### Q-CKPT-6 — the answer a best save hands back to the retention policy — **RESOLVED 2026-09-27 (Q-EVAL-12): `Retention.note_saved(self, ok, slot=None)`, CALLED ONLY AFTER BEST AND bestN SAVES. NOTHING NEW IS CHECKPOINTED. NO LEVER, NO WIRE**
`new_retention`'s obligation (1) said `best_saved` and the ring meant "ordered", because nothing
carried `CKPT.save`'s answer back. `consider` now stashes what it ordered — the slot's previous
resident and the pointer before it — and `note_saved(ok)` sets `best_saved` from the global `.best`
save's return, while `note_saved(ok, slot)` on a refused slot save puts the resident back and returns
the pointer, so the ring advances only on a written file, as the old tree's `if _save_ckpt(...)`
did. `rotations` keeps counting orders; `counters()` gains `saves_refused`. A note nothing ordered is
refused. The stash is not in `state()`: `_STATE_FIELDS` is unchanged, because a restore refuses a
missing field and old blobs must still load. **Recorded, not repaired:** when one reading earns both,
the `.best` blob is written first and holds the ordered slot, so a refused `.best<k>` save leaves that
one blob naming a slot whose file was never written. The row is `('C', 'CKPT',
'Retention.note_saved')`, fed `ok` by the C `CKPT.save` row's `produces` column.

### Q-FAB-17 — which passes FAB's did-it-fire counters count — **RESOLVED 2026-09-27 (Q-EVAL-12): TRAINING PASSES ONLY; AN EVAL PASS COUNTS `fab.eval_passes`. NO TRAINING-PATH NUMBER MOVES**
Until now nothing but the training flush called `FAB.forward`, so its counters never had to say
which passes they count. The retention probe's closures call it with `training=False`, and a reading
must not move the ledger that describes training. Every counter the body wrote on a solo pass —
`fab.route_calls`, `hops_taken`, `halt_clamped`, `explored_rows`, `explore_distinct_targets`,
`discovered`, `discover_targets`, `banned_experts`, `ec_applied`, `halt_spent_on_base`,
`div_applied`, `ind_applied`, `hopsup_applied`, `forward_identity`, `norm_only_passes` — is now
bumped on **learn** passes only (training and not a counterfactual), which is every pass it counted
before; an eval pass bumps `fab.eval_passes` (the twenty-fifth key the body writes). **Two more than
the plan's list**: `fab.ind_applied` and `fab.hopsup_applied` need targets, which an eval pass does
not hand in, so they could not fire there — gated anyway, so the rule is one rule. `fab.holdout_applied`
(the counterfactual's) is unchanged. The root seeds `fab.eval_passes` at 0 when the probe is armed,
because FAB cannot see whether it is (the `tok.due_merged` precedent).

### Q-WORLD-11 — the forecast's gauges on a pass outside training — **RESOLVED 2026-09-27 (Q-EVAL-12): `world.forecast_rms`, `world.forecasts` AND `_proj_trained` ARE WRITTEN ONLY UNDER GRAD. NO TRAINING-PATH NUMBER MOVES**
`WORLD.forecast` returns the forecast on every call and counts `world.forecast.calls` /
`world.forecast.inert` as before; the gauge, the fire count and the `_proj_trained` flag — which
`load_into` reads to decide whether a restored `world_proj` was ever trained — describe training and
are written only when `torch.is_grad_enabled()`. A probe pass under `no_grad` therefore leaves them
where the last flush left them.

### Q-LM-14 — encode's `extra` gauges on a pass outside training — **RESOLVED 2026-09-27 (Q-EVAL-12): `lm.encode.extra_ratio`, `extra_ratio_max` AND `extra_applied` ARE WRITTEN ONLY UNDER GRAD. NO TRAINING-PATH NUMBER MOVES**
The forecast is still added to the hidden state on every call — the closures score the path the run
trained — but the ratio gauges and the applied count describe the training flush, so a `no_grad`
probe pass neither measures nor counts them. `lm.encode.calls` still counts every call; it is in the
probe's exact-accounting set (Q-EVAL-12).

### Q-FAB-18 — which experts the management pass removes from a faded area, and whether it may wait — **RESOLVED 2026-09-28 (Proposal 05 §8 3.1; register NEW-10, C37 and CONTRACT-Q-FAB-5): `FAB.observe(..., area_id=None)` KEEPS A PER-EXPERT AREA BOOK; `FAB.manage(..., faded=None)` COUNTS EVERY REMOVAL WHOSE EXPERT MOSTLY SERVED A FADED AREA; `FAB_FADED_CULL`, BUILT `'as_is'` — `'defer'` IS THE E2 ARM, AND A DEFERRED VICTIM KEEPS ITS BUDGET SLOT. ⚠ ONE NEW LEVER, A CENSUS AMENDMENT; TWO FROZEN SIGNATURES WIDENED WITH A DEFAULTED KEYWORD. NO WIRE, AND NO NUMBER A DEFAULT RUN PRODUCES MOVES**
**What was asked.** NEW-10 rules that from SR0 on every training run reports "faded-area expert
culls", C37 that the continue preset defers "culls and merges of experts whose most-served area is
faded ... (not executed, counted)" until `FAB.contribution` works, with training runs unchanged and
the deferral an E2 arm, and CONTRACT-Q-FAB-5 asks, per manage pass, for "the count of culled or
merged experts whose most-served area is faded". At the owner's shape both removals are reached
(the fleet archive: 481-1,002 experts past grace, 203-810 `cull_fail` and 336-648 merges per run),
and nothing in FAB knew which area an expert served.

**The ruling, as built.**
* **An area's number.** `spine/derive.py::area_id(label)` — crc32 of the label's UTF-8 bytes masked
  to 31 bits. A function of the label alone, so a checkpointed book means the same area in a child
  whose `DATA_AREAS` inserted, appended or reordered areas (a position in `Areas.names` would not,
  and Python's `hash` is salted per process); 31 bits, so MEM's int32 column keeps -1 for "none".
  `DATA.open_areas` refuses two labels on one id beside its label and key collisions, naming both
  and `data.area_id_collision`, a Gate that reads 0 in every `Areas` that exists (a Gate since
  the review below; the name was declared and written nowhere).
* **The faded set.** DATA's `Plan.faded[k]` — every area live in a phase before k and not in k — and
  `Plan.parent_faded` — the areas the resumed lineage's streams drew (`Areas.drawn`, which
  `stream_state` records; every area the record declared, `Areas.parent_names`, until the review
  below) that no phase of this schedule makes live (the DATA section). At each `fab.manage` pass
  the root hands `faded` = the ids of
  `Plan.faded` at the phase this window's first byte falls in (the byte the probe's phase-start test
  reads) together with `Plan.parent_faded`, through the join `compose.py::_faded_ids`. **The parent's
  half is what makes the count, and the deferral, mean anything in the continue preset C37 is about**:
  a pure-add child's own schedule fades nothing, while every expert it inherits served the parent's
  areas.
* **The area book.** `Population.area_use`, per expert `{area id: mass}`. `FAB.observe`'s new
  `area_id` (one id per window, in `domain_id`'s shapes; the root passes each window's FIRST token's
  area, read off `Segmentation.labels` through `compose.py::_window_areas`) credits each computed
  expert the routing mass `use` gets — so, where every window's area is known, an expert's book sums
  to its `use` — and a negative id credits nothing. It is one of `_BOOKS`: `_remove` moves it with its
  expert and clears the vacated last row with a fresh dict, `_claim_slot` clears it, `_merge_into`
  sums the absorbed book into the survivor's. `fab.area_windows` counts the booked windows (ABSENT
  until a routed call is handed an area). It is checkpointed in `FAB.state_dict`'s books as sorted
  `[id, mass]` pairs, and a blob without it restores empty books. A DOMAIN IS NOT AN AREA: `dom_of`
  is DOM's learned partition, which merges, splits and culls; an area is a corpus the schedule fades
  by name.
* **The count** (`FAB.manage`'s step 7). The pass decides first; then every expert it removes — the
  merge's absorbee, either cull's victim — is read against its book. Its most-served area is the
  argmax of the book, the smallest id on a tie (never a dict's order, which a checkpoint round trip
  need not keep). A faded one counts `fab.merged_faded_area` or `fab.culled_faded_area`; an EMPTY
  book (no area ever booked: a founder no window reached, or every expert restored from a checkpoint
  older than the book) counts `fab.faded_unknown` instead, so a 0 over empty books is not read as a 0
  over read ones. The three are cumulative, PRESENT-and-0 from the first pass handed a set (an empty
  set included: phase 0 hands one) and ABSENT while none was. **Per pass** — CONTRACT-Q-FAB-5's
  "per manage pass" — each has a gauge, `fab.culled_faded_area_last_pass`,
  `fab.merged_faded_area_last_pass` and `fab.faded_unknown_last_pass`, as `fab.merged_last_pass` is
  `fab.merged`'s (since the review below: the pass's counts lived only on the `ManageReport`, which
  the root files nowhere); `fab.faded_areas_last_pass` is the pass's set size. The four gauges are
  written on every pass handed a set and dropped on one handed none. `ManageReport` carries the
  pass's own counts (`culled_faded_area`, `merged_faded_area`, `faded_unknown`,
  `cull_faded_deferred`, `merge_faded_deferred`).
* **`FAB_FADED_CULL`** (`'as_is'` | `'defer'`, U.NAME; a census amendment, the fourteenth;
  `fabric/levers.py` section 6). **`'as_is'`** (shipped): no decision reads a book, and the pass
  removes exactly what it removed before the book existed. **`'defer'`** (NEW-10's and C37's E2 arm,
  and C37's preset value until `FAB.contribution` works, §8 3.5): a removal whose expert's most-served
  area is faded is SKIPPED — the pair is not merged (its other expert stays free for the rest of the
  scan), the expert is not culled — and counted as an EVENT, `fab.merge_faded_deferred` /
  `fab.cull_faded_deferred` (an expert deferred on a later pass counts again), beside
  `fab.faded_deferred_experts`, the distinct experts this pass deferred (a gauge; a deferred expert
  leaves the pass's remaining decisions, so each is deferred once and the gauge is the pass's
  events); all three are ABSENT at `'as_is'`. **Every other decision of the pass is the one
  `'as_is'` takes** (the review below): the rest of the pass reads the population `'as_is'` would
  hold, so a deferred absorbee pairs with nobody else, the failure cull walks, and the pressure
  gate and the utilization budget count, the population without the deferred, **a deferred
  utilization-cull victim keeps its budget slot** (the ranked walk stops at `budget` victims plus
  deferrals — deferral, not substitution, the critic's finding on the draft), and the survivor of a
  pair left apart is ranked, paired and read by the use, uage and book the merge would have given
  it. So a `'defer'` pass removes exactly what `'as_is'` would remove from the same population, less
  the faded removals. An empty book is not faded and is removed at either value. **The cost is stated, not
  discovered:** with the pool at `FAB_SLOTS` a deferred expert holds a slot a new area could have been
  born into (NEW-20). `'contrib'` (a removal gated on `FAB.contribution <= 0`) is §8 3.5's and joins
  the choices with that build rather than ahead of its producer.
* **Rescue is not deferred.** `FAB_RESCUE`'s heavy mutation is neither a cull nor a merge and keeps
  the expert's slot and book; it is OFF at the shipped 0.0, and whether a faded-area expert may be
  rescued is the question of an arm that turns it on beside `'defer'`. At `'defer'` the pass rescues
  the experts `'as_is'` would rescue (the review below) — never a deferred one, which `'as_is'` had
  removed.

**What the rule does not see (recorded, not repaired).** (a) The faded set is the schedule's within
one epoch: at an epoch roll the schedule restarts, so an area only the previous epoch's later phases
trained is not faded in the next epoch's early phases (the shipped `RUN_EPOCHS=1` has no roll). (b)
A parent area a child schedules in a later phase is not faded before that phase; only one the child
never schedules is `parent_faded`. (c) A window straddling a segment seam books its routing mass to
its first token's area. Each is a rule a later build may widen; none moves a number a run produces.

**Found while building it, and not repaired (a ruling is owed).** The failure cull walks the
`eligible` list `FAB.manage` took at entry, before the merge's removals renumbered the population by
swap-with-last, so an expert moved into a merged-away slot is judged under that slot's past-grace
entry. Driven on a scripted pass (`FAB_GRACE=2`; one merge absorbs slot 0 and moves the last expert —
`uage` 0, both error EMAs above `comp_glob + FAB_FAIL_TOL` — into it): that expert, inside grace, was
failure-culled. B3's shape never reaches it (its six passes, recounted, removed no expert inside
grace), and at the shipped defaults no expert is past grace; at the owner's shape, where merges and
failure culls both run, it can cull an expert inside grace. Recomputing the list after the merge
changes which experts a pass can remove there, so it is left for its own ruling; step 7 counts the
expert actually removed either way.

**Bit-identity.** Both new arguments default to None and the loop hands both; nothing in the forward
pass reads a book, at `'as_is'` no decision in FAB does, and no draw is taken — so a default run
removes, keeps and trains exactly what it did. B1, B3, B3r, B5, B6 and B6r reproduce their fixtures
and list the new keys as new and nothing else: `fab.area_windows` and Q-MEM-16's five
`store.occupancy.*` keys on every leg, and `fab.culled_faded_area`, `fab.merged_faded_area`,
`fab.faded_unknown` and `fab.faded_areas_last_pass` on the three legs that reach a manage pass (B3
and both of B3r's).

**Known answers** (`tests/test_faded.py`, CPU, operation only). F1 `Plan.faded` on the generated
four-area schedule is `[(), (0,), (0,), (0, 1)]`, and hand-computed on five explicit schedules and on
a parent record. F2 `area_id`'s pinned values, and `open_areas` refusing a full crc32 collision
(`qh9par8f`, `gd221zva`) and one only the mask makes (`g4bgcsbc`, `gyz44zl0`). F3 the book under
scripted routing, merge, removal, birth and a state_dict round trip. F4 the count on scripted passes
through each removal path, and `faded=None` leaving every step-7 key ABSENT. F5 `'defer'` on the same
populations: the utilization cull removes exactly the non-faded members of `'as_is'`'s five victims
and not the next live-area expert. F6 on B3's shape (314 windows, six passes over phases 0, 1, 1, 2,
3, 3): every pass handed `Plan.faded` at its window's phase, and the counts (2 merged, 23 culled, 0
unknown of 146 removals) equal an independent recount of what was removed. F7 `'defer'` on the same
workload removes no faded-area expert after the fade (55 cull and 15 merge deferrals). F8 a pure-add
child of an eng-only parent hands every pass `{eng}` from its first. F9 continuing resumes at both
values are exact and end with the uninterrupted run's books, counts and deferrals; a checkpoint
stripped of the book resumes exactly, and the removals of experts whose books were not refilled
count as `fab.faded_unknown`. (F5, F6, F7 and F9 as the review below left them are in its last
paragraph.)

**CORRECTED 2026-09-28 (Q-FAB-18's review) — `'defer'` takes every decision `'as_is'` takes and
drops only the faded removals; `Plan.parent_faded` is read off the areas the lineage drew; the count
is reported per pass; the reasons name the deferrals; `data.area_id_collision` has its row.** (i)
*The deferral leaked on three paths the budget rule did not reach, and a fourth found while
repairing them.* The ruling promised that no live-area expert is culled in a deferred one's place,
and the build kept the promise only inside the utilization cull's walk. Driven on scripted passes at
the build: a failure-cull deferral stayed in the recounted eligible set, so the budget
`int(cull_frac * n_elig)` grew — four eligible experts at `FAB_CULL_FRAC` 0.5, expert 0 failing and
faded: `'as_is'` removed 0 and 1, `'defer'` 1 and 2, live expert 2 in 0's place; a merge deferral
left `n_live` one larger, so `derive.cull_gate_open` read 6/12 = 0.500, OPEN, at `FAB_PRESSURE` 0.5
where `'as_is'` read 5/12, SHUT, and `'defer'` culled live experts `'as_is'` kept; a deferred
absorbee stayed pairable, so with (0, 1) and (0, 2) close and 0 faded `'defer'` merged live expert 2
into 0 where `'as_is'` merged 0 into 1 and paired 0 with nobody else; and the survivor of a pair
left apart was ranked by its own `use`, without the absorbee's mass the merge gives it — 0 (use 50)
and 1 (use 1) close, 0 faded: `'as_is'` ranked 1 at 51 and culled 2 and 3, `'defer'` ranked 1 first
and culled it. On B3's shape, each `'defer'` pass against `'as_is'` run on a copy of the population
that entered it: at the pass of window 201 one live-area expert was removed that `'as_is'` kept, and
five of the six passes counted more deferral events than `'as_is'` made faded removals from the same
populations (55 cull and 15 merge events over the run, against 48 and 10). **Ruling:** a `'defer'`
pass removes exactly what `'as_is'` would remove from the same population, each the same way, less
the faded removals, and defers exactly those. `FAB.manage` names each expert by its slot at entry
and keeps two layouts through the pass, the population's own and the one `'as_is'` would hold
(`fabric/api.py::_drop`, `_remove`'s renumbering on a list), and every step after a deferral reads
the second: a deferred absorbee is consumed for the scan as an absorbed one is; the failure cull
walks the entry list over `'as_is'`'s layout, so a slot the merge refilled holds the expert
`'as_is'` would judge there (the defect recorded above is inherited, so the two values judge one set
until its ruling moves both); the recount, the pressure gate, the budget, the ranking and the rescue
list are `'as_is'`'s; and the survivor of a pair left apart, and whoever later absorbs it, is
ranked, paired and read by the use, uage and book the merge would have given it
(`fabric/api.py::_sum_books`, the one book sum `_merge_into` also makes). A deferred expert
therefore leaves the pass's remaining decisions and is deferred once per pass, so
`fab.faded_deferred_experts` is the pass's events. `fab.cull_gate` prints `'as_is'`'s population at
`'defer'` (the pair its verdict was taken on) and its reason says how many deferred experts stand
beside it. At `'as_is'` the two layouts are one list and no value is overridden, so every read is
the read it was: 400 seeded scripted passes (merges that chain, failure culls over refilled slots,
budgets, gates, spares, ties, rescue on a third) leave books, banks, ledger, gate reasons,
`ManageReport` and row events bit-identical to the build at `'as_is'` and at `faded=None`, bar the
three per-pass gauges of (iii); over 2,000 such passes `'defer'` removed exactly `'as_is'`'s
removals less the faded ones in every one whose `comp_glob` is set (1,057 of the 2,000 deferred
something). **Found while repairing it, and not repaired (a ruling is owed):** where the failure
cull does not run — `comp_glob` None, no window attributed yet — the utilization cull ranks the
`eligible` list taken at entry, which a merge's removals have renumbered: it reads slots past the
population, dead rows `_remove` leaves holding a moved expert's `use`, and "culling" one moves the
last live expert into it. Driven at the build on scripted passes: four of 400 took `n_live` below
zero (−8 at `FAB_N0=22`, `FAB_MERGE_DIST=0.9`, `FAB_CULL_FRAC=0.8`). The path is ae70638's
(2026-09-24), and no loop run reaches it — the first routed `observe` sets `comp_glob`, and a
population restored from a checkpoint carries it — but a scripted population with an area book and
no `comp_glob` can, and there `'defer'` ranks the same entry list in `'as_is'`'s layout without the
dead slots, which is the one place the two values' decisions can part. (ii) *A declared area is not
a trained one.* `Plan.parent_faded` was read off `Areas.parent_names`, every area the parent's
record declares. Driven at the build (`DATA_AREAS=eng,py`, `DATA_PHASE_SCHED=eng|eng|eng|eng`,
`DATA_STREAM_BYTES` 20000, `FAB_MANAGE_EVERY` 25, `FAB_GRACE` 2): the uninterrupted 85-window run
handed its passes at 26, 51 and 76 the empty set; a parent stopped at window 60 and its continuing
child continued exactly, but the child's `Plan.parent_faded` was (1,), `data.parent_faded` ['py'],
its pass at 76 was handed py's id and `fab.faded_areas_last_pass` read 1 against 0 — py, which
nothing in the lineage ever drew. **Ruling:** `Areas.drawn`, every area the lineage's streams have
drawn a byte from, in the order first drawn — filled in place by `restore_stream_state` from the
record, extended by `draw_stream`, recorded by `stream_state` — and `Plan.parent_faded` is read off
it. A continuing resume draws its parent's schedule, so its set is the uninterrupted run's; an
epoch- boundary child's lineage drew every area its epochs held. A record written before the list
carries none, and then every area it declares is assumed drawn and named in `data.drawn_assumed` ([]
where the record carried the list; ABSENT on a fresh run). (iii) *CONTRACT-Q-FAB-5 asks for the
count per manage pass,* and the pass's counts lived only on the `ManageReport`, which the root files
nowhere; the report carried lineage totals. Each of the three counts now has a gauge written on
every pass handed a set, `fab.culled_faded_area_last_pass`, `fab.merged_faded_area_last_pass` and
`fab.faded_unknown_last_pass`, as `fab.merged_last_pass` is `fab.merged`'s; the four per-pass gauges
of step 7 (with `fab.faded_areas_last_pass`) are dropped on a pass handed no set, so an earlier
pass's numbers never read as this one's. On B3's shape the six passes read (culled, merged, unknown)
(0, 0, 0), (2, 2, 0), (10, 0, 0), (6, 0, 0), (5, 0, 0), (0, 0, 0), each its own recount. (iv) *The
reasons had no word for a deferral.* A pass whose every close pair was deferred printed "no pair
with a past-grace member sat within `FAB_MERGE_DIST`" in both merge gates, and
`fabric.cull_eligible` printed "0 culled, 0 spared" of an expert that failed and was kept. Each
reason now names the deferrals where they are armed — this pass's at `'defer'`, and the ledger's
`fab.merge_faded_deferred` in the run-scope gate — and an `'as_is'` reason reads as it did. (v)
*`data.area_id_collision` was declared and written nowhere:* no Gate, no counter, and neither the
refusal nor `data.area_refused`'s reason named it. It is a Gate beside
`data.area_label_collision`'s, reading 0 against the entries compared; the refusal names it, and
`data.area_refused`'s reason lists the area-id collision. **Bit-identity:** at the shipped `'as_is'`
nothing a run trains on moves; B1, B3, B3r, B5, B6 and B6r reproduce their fixtures and list as new,
beside the build's, the three per-pass gauges on the three legs that reach a manage pass
(`data.drawn_assumed` and the new Gate are not integer counter lines). **Known answers**
(`tests/test_faded.py`, CPU, operation only; 52 checks): F1 adds a parent that declared c, eng and
py and drew eng alone — `parent_faded` (0,), not (0, 3); F2 the refusal's name, the Gate and
`data.area_refused`'s reason; F4 the per-pass gauges and their drop on a pass handed none; F5
`'defer'` against `'as_is'` down each path — the utilization cull, the failure cull then the budget,
a merge then the gate, the merge scan, the survivor's mass, the failure cull's walk over a refilled
slot — and a seeded sweep of 150 random populations, all exactly `'as_is'` less the faded removals
(the build matched 74 of the 150), with the deferral clauses in both merge gates and in
`fabric.cull_eligible`; F6 each pass's gauges are its own recount; F7 every `'defer'` pass of B3's
shape against `'as_is'` on a copy of the population that entered it (six passes, five deferring; 47
cull and 10 merge deferrals over the run); F9 the declared-but-undrawn continuation (the record's
drawn list ['eng'], every child pass handed the uninterrupted run's set, `data.drawn_assumed` [])
and a record stripped of the list (py assumed, printed, and handed to the child's pass).

### Q-MEM-16 — which area each stored entry came from, and the store's occupancy by area — **RESOLVED 2026-09-28 (Proposal 05 §8 3.1; register NEW-10): `MEM.write(..., areas=None)` FILLS A NEW PER-ENTRY `area` COLUMN; `MEM.census` RETURNS `by_area`; THE ROOT PRINTS `store.occupancy.<area>` BY NAME. A FROZEN SIGNATURE WIDENED WITH A DEFAULTED KEYWORD. NO LEVER, NO WIRE, AND NO NUMBER A DEFAULT RUN PRODUCES MOVES**
NEW-10 rules that from SR0 on every training run reports "memory occupancy by area" — the reading
that says whether a parent leaves training with its faded areas' memory evicted (the old tree's
phased run a9d7258 evicted every English entry). The store kept `src`, DOM's learned domain, which
folds, splits and is culled (`MEM.apply_domain_plan` rewrites it), and no record of the corpus an
entry came from.
* **The column.** `Store.area`, int32, one per row: `spine/derive.py::area_id` of the DATA area the
  entry came from, and **-1 for "no area was booked"** — every row of a fresh store, every entry a
  caller wrote without `areas`, every entry restored from a checkpoint older than the column.
  `_commit_window` writes it beside `tok` and `pos` on every commit, so an overwritten slot never
  keeps the evicted entry's area.
* **`write(..., areas=None)`** takes a (B, L) integer tensor, one id per POSITION: the input token's
  area, whose byte offset `positions` records, so an entry's area and its `pos` name one byte. It is
  refused by name when mis-shaped, like the other per-row arguments. No gate, eviction, floor, read or
  rekey reads it, so a write with and without it keeps and evicts the same entries.
* **`census` returns `StoreCensus.by_area`**: `{area id: active entries}`, ascending ids, an exact
  count over the active rows' column on every call, so it sums to the active entries by
  construction. A reading; it moves no counter. It is keyed by id because MEM never sees a name, and
  it is not `counts`, whose keys are DOM's domains.
* **The root prints it by name** in the R row `MEM.census(reconcile=True)`: `store.occupancy.<area>`
  for every area of the run — 0 where none of its entries survive, which is the reading NEW-10 exists
  for — and `store.occupancy_unknown` for the -1 entries and any id the run does not name. The plan
  wrote `.unknown`; it is underscored because `DATA_AREAS` may label an area "unknown", and the two
  would print under one key.
* **Checkpointed per row** (`"area"`); a row without the key restores -1, so a checkpoint written
  before the column resumes exactly, its restored entries counted as unknown until they are evicted.
**Known answers** (`tests/test_faded.py`). F6: on B3's shape the four areas' occupancies (eng 346, py
2,867, num 2,746, c 569 at the end of the epoch — eng, faded since phase 1, holds the fewest)
sum to the 6,528 active entries, and every active entry's area is the label of the byte its `pos`
records. F9: a checkpoint stripped of the column resumes exactly with every restored entry at -1, and
the child's report counts the survivors as `store.occupancy_unknown`.

## 6. What `tests/test_contract.py` checks

| check | what it proves | how it can fail |
|---|---|---|
| K1 | every name this document declares exists in the tree **with the signature it claims** | rename a parameter; drop a function |
| K2 | `spine.compose` imports and `compose()` raises **only `NotImplementedError`, from a stub** | a typo in the root surfaces as `AttributeError`/`TypeError`, not as a missing body |
| K3 | no package imports another (O10 restated at the contract boundary) | add `from fabric import api` to `src/memory/` |
| K4 | every one of the 273 declared levers is named `LEVERS READ:` by a stub, or is in the UNCONSUMED table above **with a reason** | declare a lever and give it no reader |
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

Everything above is prose about these 147 entry points — 121 until 2026-09-02, when Q-TOK-11 added
`LM.residual_ratios` (122) and Q-LM-12 added `LM.embed` (123); 133 from 2026-09-15, when P4 wrote
`CAP.caps` and the `Caps` record it returns brought `Caps.headroom(n)` with it; **134 since
2026-09-22, when `World.parameters(self)` closed the hole `spine/compose.py::_base_parameters` had
been warning about on every run** — WORLD's tensors took gradient from a loss that was in the
objective and were never STEPPED, because that helper harvests by
`getattr(obj, "parameters", None)` and `World` had no such method. It is the same shape as
`FAB: Population.parameters(self)`, which is in this block for the same reason. **136 from
2026-09-24**, when RUN's `Cadences.state(self)` and `Cadences.restore(self, state)` carried every
cadenced gate's schedule across a resume (Q-RUN-9); **137 since later that day**, when
`OPT.remap_rows(opt, st, row_events)` gave AdamW's per-row moments a way to follow the expert rows
FAB moves (Q-FAB-13); **140 on 2026-09-26**, when 03b's stage S0b added the mid-epoch act's
three: `TOK.splice`, `RunClock.revise_epoch_length` and `OPT.revise_horizon` (Q-RUN-8 option (a),
Q-OPT-10); 141 later that day, with `TOK.view_of`, the match-table view a segmentation
records so a continuing resume can cut at it again (Q-TOK-15, Q-RUN-16); **147 since 2026-09-27**,
when the retention probe (Proposal 04 SR0 and NEW-03) added six: `EVAL.retention_period`,
`EVAL.pin_holdout` and `EVAL.blowup` (Q-EVAL-12), `DOM.nearest` (Q-DOM-6), `MEM.encode_queries`
(Q-MEM-15) and `CKPT.Retention.note_saved` (Q-CKPT-6) -- and MOVED one, `EVAL.holdout_probe`, whose
`rng` left for `pin_holdout` and which gained `tokenize_fn`, `step`, `boundary` and `previous`
(Q-EVAL-12). Neither of the two before them
is a new ruling: this document has said since the record was specified that "`Caps.headroom(n)`
exists so the negative clamp (C30) **cannot be written** at a call site", and it became an ENTRY
POINT the moment a body existed to carry it. A record's public method is public surface, which K1
and K6 both
say in the only way that matters — they went red on it the first run after it landed. Both are LM, both landed on the same
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
a reordered one, a changed default or a positional-that-became-keyword-only all fail. The three
moves of 2026-09-28 are that kind and were made here with the tree: §8 3.1's faded-area counters
widened `FAB.observe` with `area_id=None` and `FAB.manage` with `faded=None` (Q-FAB-18), and
`MEM.write` with `areas=None` (Q-MEM-16) — each a defaulted keyword at the end, so every existing
call is the call it was, and none was added, so the count stands at 147.

Ten implementation agents work against this list independently. **It does not move without an edit
to this document and to the tree in the same commit**, which is the only thing keeping them
compatible.

```contract
CAP: new_valve(cap: Config, *, restored=None)
CAP: observe(cap: Config, valve, *, elapsed_windows, live_experts, live_vocab, improving, observations, blackout)
CAP: caps(cap: Config, valve)
CAP: Caps.headroom(self, n)
CAP: startup_refusals(cap: Config, valve, *, live_experts)
CAP: state(valve)
CAP: restore(cap: Config, valve, state)
CAP: counters(cap: Config, valve)
CKPT: saving_on(ckpt: Config)
CKPT: save_period(ckpt: Config)
CKPT: save(ckpt: Config, *, payload, geometry, step, epoch, reason, best_state=None, suffix='')
CKPT: install_save_signal()
CKPT: resume_source(ckpt: Config)
CKPT: load(ckpt: Config)
CKPT: check_geometry(ckpt: Config, snapshot, geometry)
CKPT: new_retention(ckpt: Config, *, restored=None)
CKPT: Retention.consider(self, curve_bpb, step)
CKPT: Retention.note_saved(self, ok, slot=None)
CKPT: Retention.state(self)
CKPT: Retention.counters(self)
DATA: open_areas(dat: Config, *, seed: int)
DATA: data_plan(dat: Config, areas, *, epochs: int, win_tokens: int, bytes_per_token: float)
DATA: draw_stream(dat: Config, areas, plan, *, epoch: int, seed: int)
DATA: stream_state(dat: Config, areas)
DATA: restore_stream_state(dat: Config, areas, state)
DOM: open_partition(dom: Config, *, sig_dim, vocab_slots, device, rng, restored=None)
DOM: observe(dom: Config, part, *, signature, sample_window, tokens, now)
DOM: nearest(dom: Config, part, *, signature)
DOM: rekey(dom: Config, part, *, encode)
DOM: note_competence(dom: Config, part, *, did, bits)
DOM: manage(dom: Config, part, *, now, memory_counts, mem_floor_entries)
DOM: on_retokenize(dom: Config, part)
DOM: prior(dom: Config, part, *, did)
DOM: census(dom: Config, part)
DOM: state_dict(dom: Config, part)
DOM: manage_period(dom: Config)
EVAL: curve_period(ev: Config)
EVAL: retention_period(ev: Config)
EVAL: pin_holdout(ev: Config, *, blocks, seed, window_bytes, prefix_bytes)
EVAL: curve_probe(ev: Config, *, units_by_domain, logits_fn, step, rng)
EVAL: holdout_probe(ev: Config, *, units_by_domain, logits_fn, tokenize_fn, step, boundary=False, previous=None)
EVAL: blowup(ev: Config, *, series)
EVAL: null_excess(ev: Config, *, real, permute, rng)
EVAL: generate(ev: Config, *, logits_fn, prompts_by_domain, rng)
EVAL: coherence(ev: Config, *, logits_fn, units_by_domain, encode, rng)
EVAL: verdicts(ev: Config, *, domain_sizes, silhouettes, affiliation, coherence_reading)
EVAL: wrongness_probe(ev: Config, *, store_copy, scorer, rng)
EVAL: verification_fit(ev: Config, *, store_copy, verify_mode, rng)
FAB: build(fab: Config, *, d_model, signature_dim, device, generator)
FAB: Population.n(self)
FAB: Population.parameters(self)
FAB: forward(fab: Config, pop, *, h, signature, novelty, head=None, targets=None, step_windows, domain_id, live_domains, training, hold_out=None)
FAB: observe(fab: Config, pop, out, *, per_window_loss, domain_id, area_id=None)
FAB: contribution(fab: Config, pop, *, h, signature, novelty, head, targets, baseline_loss, baseline_logits_fn, step_windows, domain_id, live_domains, candidates)
FAB: manage(fab: Config, pop, *, step_windows, flush_loss=None, faded=None)
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
MEM: write(mem: Config, store, *, contexts, tokens, surprise, sources, owners, positions, key_fn, now, areas=None)
MEM: read(mem: Config, store, *, queries, promote=True)
MEM: encode_queries(mem: Config, *, contexts, key_fn)
MEM: blend(mem: Config, model_probs, retrieval)
MEM: maintain(mem: Config, store, *, now, key_fn, probe_contexts=None, resegment=None, remap=None)
MEM: apply_domain_plan(mem: Config, store, *, folds, deletions, live_sources)
MEM: judge(mem: Config, store, *, scorer=None, reconstructor=None)
MEM: census(mem: Config, store, *, reconcile=False)
MEM: state_dict(mem: Config, store)
MEM: rekey_period(mem: Config)
OPT: build(opt: Config, *, param_groups, run_windows)
OPT: lr_at(opt: Config, st, opt_step)
OPT: scaled_backward(opt: Config, st, total)
OPT: maybe_step(opt: Config, st, *, best_bpb=None, shift_at=None)
OPT: revise_horizon(opt: Config, st, *, run_windows)
OPT: remap_rows(opt: Config, st, row_events)
OPT: counters(opt: Config, st)
OPT: state_dict(opt: Config, st)
OPT: load_state(opt: Config, st, saved, *, continuing=False)
RUN: process_setup(run: Config)
RUN: mode(run: Config)
RUN: Timing.span(self, name)
RUN: Timing.spans(self)
RUN: streams(run: Config, subsystems)
RUN: new_clock(run: Config, *, batch_windows, accum, resume_step=0, resume_epoch=0, resume_backwards=0, resume_opt_steps=0, resume_in_epoch=0, resume_windows_in_epoch=None)
RUN: RunClock.begin_epoch(self, windows_in_epoch)
RUN: RunClock.revise_epoch_length(self, windows_in_epoch)
RUN: RunClock.advance(self)
RUN: RunClock.note_backward(self)
RUN: RunClock.counters(self)
RUN: new_cadences(run: Config, *, periods)
RUN: Cadences.due(self, key, period, clock)
RUN: Cadences.ledger(self)
RUN: Cadences.state(self)
RUN: Cadences.restore(self, state)
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
TOK: tokenize(tok: Config, vocab, data, labels=None, *, start=0, regularize=False, seed=0, view=None)
TOK: Vocabulary.decode(self, ids)
TOK: Vocabulary.blen(self, i)
TOK: Vocabulary.size(self)
TOK: Vocabulary.live_size(self)
TOK: Vocabulary.at_cap(self)
TOK: view_of(vocab)
TOK: splice(tok: Config, vocab, seg, data, labels=None, *, at, regularize=False, view=None)
TOK: on_window(tok: Config, vocab, ids, *, step)
TOK: mint_burst(tok: Config, vocab, *, step)
TOK: judge_probation(tok: Config, vocab, *, step, appearances, residual_ratio=None)
TOK: lift_vocab_cap(tok: Config, vocab, *, to: int)
TOK: save_vocabulary(tok: Config, vocab, *, suffix='')
TOK: vocab_state(tok: Config, vocab)
TOK: restore_vocab(tok: Config, state, vocab)
WORLD: build(world: Config, *, d_model, device, ctx_tokens, rng)
WORLD: World.parameters(self)
WORLD: loss_terms(world: Config, w, obs_emb)
WORLD: forecast(world: Config, w, obs_emb)
WORLD: manage(world: Config, w, *, latent, plateau, add_param_group)
WORLD: geometry(world: Config, w)
WORLD: state_dict(world: Config, w)
WORLD: load_into(world: Config, w, sd)
WORLD: startup_refusals(world: Config, *, ctx_tokens)
```
