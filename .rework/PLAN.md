# Implementation plan — the rm-predict-DC rework

Status: **proposed, not started.** Nothing in `src/` exists yet. This document is the "first implementation
instructions and details" and is the thing to argue with before any code is written.

Built from: `.rework/survey/` (16 areas, 1,149 facts, 558 lever records, 475 bugs, 305 carry-forward),
`.rework/COMMIT_RECORD.md` (379 commits), four independently-produced architectures, three judges with
different lenses, and a completeness critic. The synthesis agent that was meant to write this died on an
output limit; the merge below is mine, and the reasoning is stated so it can be checked.

---

## 0. What decided the architecture

The survey's bug classes, counted:

```
98  wrong-measurement    the number printed is not the quantity named
60  untrippable-guard    a guard whose condition cannot be satisfied
57  armed-but-inert      a mechanism switched on that never runs
47  coupling             one lever changes another's meaning
39  recorded-never-read  data stored, nothing consumes it
32  unit-mismatch        produced in one unit, consumed in another
29  silent-overwrite     state destroyed with no error
25  crash
```

This system's characteristic failure is not that mechanisms break. **It is that instruments report on
something other than what they name** — 130 of 475 records are wrong-measurement or unit-mismatch. The two
defects I confirmed by reading the source are both in that family:

- `self_organize.py:3919` — `_eval_sig` uses `[-max(1, SIG_WIN):]`. `SIG_WIN` defaults to 0, which the
  training path (`:5676`) resolves to a derived width (614 B in the last run) and this path resolves to
  **one byte**. Every eval-path routing decision in every report is made on a one-byte signature.
- `self_organize.py:3727` — `compose_test` builds `pm` from `model(X)[0]`, the plain LM head, while the
  held-out path uses `_eval_logits(model, fab, FABRIC, x)`. With `FABRIC=1`, three report sections
  (PERFORMANCE, CROSS-SEGMENT COMPOSITION, IS THE PARTITION INFORMATIVE) score a system the run never
  trained.

So the architecture is chosen to make an untrustworthy number **hard to produce**, and lever isolation is
the second requirement rather than the first — not because it matters less, but because the coupling class
is a third the size of the measurement class.

## 1. The architecture: two orthogonal disciplines

Two of the four proposals scored within noise of each other across three judges (Ownership Spine 96, The
Instrument Line 94, Bedrock 90, Declared Graph 83) and the judges split 2-1 between them. They split
because **the two designs solve different problems and neither solves the other's**. They compose.

### A. The ownership spine — governs where a lever may be read

A lever is a field on exactly one package's frozen config record. Its environment name is **generated**
from its owner (`PREFIX + FIELD` -> `FAB_N0`), so ownership cannot drift the way the current `_SPEC` drifted
(`LOSS_MASK_DEAD` is tagged `# tokenizer` inside the domains block, and 41 knobs are filed under `misc`).
One module — `spine/lever.py` — is the only place in the tree that may name `os.environ`. A package
receives only its own record as a parameter, so `def cull(pop, fab: FabricLevers, ...)` has no `mem`, `tok`
or `dom` in scope: reading a foreign lever is a NameError at author time, not a policy.

### B. The instrument line — governs what may be measured and how it is reported

One hard line: above it, code that changes the model; below it, code that measures it. Everything below
takes an immutable `Snapshot` plus a named, provenance-carrying `Sample` and returns a `Reading`. A
`Reading` **cannot be constructed** without its value, its unit, the `Sample` it came from, its estimator
(pooled vs per-window), and the null it was compared against. The renderer prints those off the object, not
from a format string.

Both confirmed defects are impossible under this: `compose_test` cannot exist because there is one logits
path and instruments do not construct their own; the one-byte signature cannot exist because the signature
width is a `Bytes`-typed derived value resolved once, and `Sample` carries the width it was built at.

### Why not the other two

**Bedrock** (ruthless subtraction) scored well on implementability and was rejected by all three judges for
the same reason: it deletes the self-assembling domain partition and the contrastive signature encoder —
two of the four things this project's own statement names as the architecture — and substitutes the corpus
directory name for discovered domain identity. That converts goal B from "did the system preserve what it
learned" into "did the file labels stay put." It also converts *never measured correctly* into *does not
work* across the whole selective layer, on evidence that is largely the confirmed-inert findings. Those
findings are evidence about the measurement, not about the mechanism. **Its best ideas are grafted below.**

**Declared Graph** keeps ~240 of 328 levers and a hand-typed `owner=` field beside each name — which is the
artifact that already failed here. Its static unit checker is a type-inference engine implemented as AST
walks with no type system underneath. Rejected; its set-but-never-read audit is grafted.

## 2. Grafts — ideas taken from the losing designs

Every one of these was named by two or three judges independently.

| # | From | Graft | Kills |
|---|---|---|---|
| G1 | Bedrock | `affects(L)` is **computed** as `{owner(L)} ∪ {owner(d) : L ∈ reads(d)}` from the derivation/wire tables, never hand-written | the isolation sweep's oracle being authored by the same person whose leak it should catch |
| G2 | Bedrock | `tests/test_determinism.py` runs **first**: two identical seeded CPU runs establish the machine's measured float noise floor | an isolation sweep that assumes zero and reads noise as a leak |
| G3 | Bedrock + IL | `tests/test_lever_isolation.py`: flip each lever, 200 seeded CPU steps, diff **per-package integer fingerprints** — tokenizer `id2bytes` order, memory `(slot, src, key-hash)` table, fabric routing histogram + `n_live`, stream label histogram, ledger counter vector | coupling through shared state, RNG draw order or the data — which no AST check can see |
| G4 | Bedrock | Three-state DID IT FIRE: `fired N` / `armed but 0` / `unreachable (gate fabric.cull false: 1838/4096 = 0.449 < 0.45)`, from `Gate(name, reads, pred, covers)` objects declared in one file and never written inline | the untrippable-guard class (60 records) and `def armed(h): return True` |
| G5 | Bedrock | The `d_` prefix: any value computed from more than one lever is written to a `d_`-named field, so `grep d_` enumerates every coupling with no tooling | couplings laundered by arriving under a local name |
| G6 | IL | `Sample` and `Reading` as constructor-enforced records | wrong-measurement (98) — a number cannot be printed without saying what it was measured on |
| G7 | IL | Digest **scoped down**: hash the small mutable state in full (per-expert dicts, `use`/`use_age`, eviction clocks, centroid EMAs, merge list, RNG fingerprint), skip the big weight tensors; asserted around every instrument call at run time, not only in tests | instruments that mutate what they measure, without needing a sound `ReadOnlyTensor` in torch |
| G8 | Bedrock | The R matrix (area × checkpoint) persisted **in** the checkpoint, reported as both `R_full` and `R_weights` | conflating an eviction problem with a forgetting problem |
| G9 | Declared Graph | End-of-run audit of environment names that matched no lever, reported as probable typos | a mis-typed knob silently running the default |
| G10 | Spine | `tools/lever_census.py`: all 328 old knobs classified kept / renamed / merged / dropped, each drop requiring a line in `docs/dropped_levers.md` | a lever disappearing without a decision |
| G11 | Spine | Capture golden tensors from the old tree **before** deleting it | the port having no oracle |
| G12 | IL | `docs/10_GLOSSARY.md` — terms whose meaning changed, each dated | the same word meaning two things across eras |

## 3. Repairs to the named fatal flaws

The judges found nine flaws that would have shipped. Each is answered here.

1. **"All ten Spine checks are AST/scope — blind to coupling through shared state, RNG order or data."**
   True, and unfixable by static analysis. Answered by G3: the isolation sweep is *behavioural*, runs the
   real code, and compares integer fingerprints against the G2 noise floor. The AST checks prove a module
   cannot *name* a foreign lever; the sweep proves it cannot *reach* one.
2. **"Wires launder couplings — `fab.nmax` arrives in `domains` as `expert_slots` and looks owned."**
   Answered by G5: it arrives as `d_expert_slots`. The prefix survives the rename because the wire ledger
   assigns the name, and `tests/test_ownership.py` asserts every wire's destination field is `d_`-prefixed.
3. **"`WIRE_BUDGET=25` is raisable, and a reason is prose that passes an AST check."**
   The budget stays as a speed bump, but the load-bearing check is that the declared wire set must equal
   the set derivable from `assemble.py`'s AST **and** every wire must show up as a `d_` field. A coupling
   that is not declared fails; a declared coupling that does not exist fails.
4. **"`armed()` predicates are as strong as the author chooses."** Answered by G4: `armed()` is deleted.
   A mechanism is unreachable only via a declared `Gate` whose predicate is a pure function of named
   inputs, and the report prints the gate's **arithmetic**, so a false gate shows its own numbers.
5. **"The Instrument Line's acceptance gate anchors the new `bpb` against the current `holdout_bpb` to
   1e-6."** Rejected outright. `holdout_bpb` runs through `_eval_logits`, so it is one of the instruments
   that survives — but the *routing* inside it is fed by the confirmed-broken `_eval_sig`. Equivalence
   anchors are taken **only** against components confirmed sound (see §5, phase P2), and every number
   expected to move is listed in advance with the reason.
6. **"`ReadOnlyTensor` + full content digest is the hardest thing here to make sound in torch."**
   Answered by G7: no `ReadOnlyTensor`. Digest the small mutable state completely; the big tensors are
   covered by the fact that instruments never receive an optimizer or a `.backward()`.
7. **"Dropping ByteComposer and the world model removes the only structural story for 'room for additional
   modalities'."** Accepted. **ByteComposer and the anchor stay.** Goal A explicitly says *with room for
   additional inclusions*; a byte-grounded composer is the mechanism that makes a new symbol space
   attachable. The world model is a §6 question for you, not a decision I make.
8. **"No seed budget, no replication floor."** Accepted and made a hard rule: the record's between-seed
   spread (0.066–0.131 b/B) **exceeds every architectural difference this project has ever claimed**. No
   comparison may be reported from fewer than two seeds; every `Reading` carries its seed count; the
   renderer refuses to print a verdict on n=1.
9. **"First end-to-end run lands at step 6 of 10; steps 3-5 produce nothing launchable."** Fixed by the
   phase order in §5: a runnable end-to-end system exists at **P3 of 9**, on synthetic data, before any
   instrument is ported.

## 4. The lever rule, and the test that enforces it

"Levers should not affect each other" needs an operational definition or it is aspiration. Some couplings
are **physically irreducible** — `FAB_PRESSURE` is a setpoint, so the population equilibrates at
`pressure × cap` and cannot be made independent of the cap. The requirement is therefore three testable
properties, not independence:

> **L1 — single declaration.** Every lever is declared exactly once, in its owner package's `levers.py`,
> with one literal default. No second default anywhere. *Enforced:* `tests/test_ownership.py` (AST) —
> `os.environ` may be named in exactly one file; a lever's default must be an `ast.Constant`; no two
> packages may share a PREFIX.
>
> **L2 — single reader.** A lever is read only by the package that owns it. Cross-package values arrive as
> `d_`-prefixed fields assigned by one wiring file, and appear in the printed coupling graph.
> *Enforced:* AST — no module may bind a foreign `LeverSet`; every `d_` field must correspond to a
> declared wire and vice versa.
>
> **L3 — no undeclared reach.** Flipping a lever must change only the packages in its computed
> `affects()` set. *Enforced:* `tests/test_lever_isolation.py` — behavioural, against the `test_determinism`
> noise floor, on integer fingerprints. **This is the load-bearing one.** L1 and L2 constrain what can be
> written; L3 is the only check that can see a coupling through shared state, RNG draw order or the data.

Irreducible couplings are declared, printed with their reason, and listed in `docs/03_WIRING.md`. The claim
the project makes is *"every coupling in this system is declared and enumerable"* — not *"there are none."*

## 5. Phases

Each is independently verifiable. **P3 is the first launchable system**, deliberately early.

| # | Phase | Deliverable | Verified by |
|---|---|---|---|
| P0 | Freeze the oracle | Golden tensors + fixtures captured from rm-predict @ aee4a52 **before** anything is deleted (G11): `build_stream` bytes at fixed seed, `_lr_at` over a step grid, tokenizer segmentation on a fixed corpus, `cull_gate_open` truth table, `widen_prefix` cases | the captures replay against the old tree byte-identically |
| P1 | The spine | `spine/{lever,registry,assemble,wire,derive,clock,rng,units}.py` + `tests/test_ownership.py` + `tests/test_determinism.py` (G2) | ownership checks pass on an empty tree; two seeded runs agree to the measured floor |
| P2 | Lever census | `tools/lever_census.py` output: all 328 knobs classified kept/renamed/merged/dropped, every drop with a written reason (G10) | every old knob appears exactly once in the census; count reconciles |
| P3 | **Mechanism, runnable** | `data/ tok/ lm/ sig/ fabric/ memory/ domains/ opt/ train/ ckpt/` — the system trains end to end on synthetic AND real data, with **no report at all** beyond loss | `tests/test_default_runs.py`: empty environment, 200 steps, reaches the end; both data paths; **AND at least one arm at `OPT_BATCH_WINDOWS=16`** — see the amendment below |

**P3's exit criterion was amended on 2026-08-30, because as first written it could not see this project's flagship defect.** At the shipped defaults `OPT.batch_windows=1` and `OPT.accum=1`, so one window *is* one flush *is* one backward pass *is* one optimizer step — every clock kind is numerically identical. A Windows/Flushes confusion, which is the single most repeated defect in the survey and the reason `spine/units.py` exists at all, is **invisible** at those numbers. A 200-step run at the defaults that reaches the end is therefore evidence that the code runs and no evidence at all about units. Every historical instance of the defect — the pin clock reading 43,645 as 2,650, `MANAGE_EVERY` compared against two clock kinds, accumulation gated on a window counter — needed `BATCH_W > 1` to appear. So the criterion now requires a second arm at `OPT_BATCH_WINDOWS=16`, and the two arms must differ only where the units say they should.

**A second amendment, from ISSUES C11.** At the shipped defaults a run is at most 937 windows (~506 at measured compression) and ten cadence defaults are longer than that, so a green P3 would otherwise certify a system in which every cadenced mechanism fired zero times. `RUN.cadence_audit` now states which gates cannot fire before the first window, and the P3 run must print that list — an empty list included, since silence is indistinguishable from the audit not having run.|
| P4 | Isolation | `tests/test_lever_isolation.py` over every lever (G1, G3) | every lever's measured reach ⊆ its computed `affects()` |
| P5 | The line | `eval/{sample,samples,reading,nulls}.py`, `report/{ledger,driver,render}.py`, `Gate` objects (G4, G6, G7) | `tests/test_instruments_pure.py`: digest unchanged around every instrument × sample; no `Reading` constructible without its null |
| P6 | Instruments | one module per section, each declaring its `Sample` | `tests/test_samples.py`: the bytes each Sample yields actually come from where it says |
| P7 | Harness + CL | `bin/`, the arm table, `add-area` as a first-class entry point, the R matrix in the checkpoint (G8) | an add-area run produces `R_full` and `R_weights` from two seeds |
| P8 | Documentation | the full `docs/` set (§6) | every owner requirement maps to a named file; no unverified claim quoted |
| P9 | Equivalence report | the written list of numbers that moved and why | each is attributable to a named fixed defect |

**Explicit non-goal:** the new tree will not reproduce rm-predict's numbers, and must not be judged on it.
You chose clean-break; two of the confirmed defects mean several old numbers were measuring the wrong
thing, so agreement with them would be evidence of a bug faithfully carried forward.

## 6. Documents to be generated

| File | Purpose | Sourced from |
|---|---|---|
| `docs/00_START_HERE.md` | what this is, the two definitives, how to run it | this plan |
| `docs/01_GOALS.md` | the two definitives, and **everything else marked as a preference with its date** | survey `facts` across chat-early/a/b/c |
| `docs/02_OPERATIONS.md` | your machine and what it can do; my environment and what it cannot; what I assumed and got wrong | this session + your answers to §7 |
| `docs/03_WIRING.md` | the coupling graph, incl. the irreducible ones with reasons | generated from `assemble.py` |
| `docs/04_LEVERS.md` | every lever: namespace, default, unit, purpose | generated from the registry |
| `docs/05_INSTRUMENTS.md` | every number the report prints: what, over which Sample, against which null | generated from `eval/samples.py` |
| `docs/06_HISTORY.md` | the timeline, with the **08-15→08-17 gap marked as unrecoverable** | `.rework/COMMIT_RECORD.md` + chat survey |
| `docs/07_RESEARCH.md` | what the literature says, per-claim evidence labels, and **what is still open** | `notes/_evidence/litreview/` + new sourcing |
| `docs/08_ISSUES.md` | the live list, filtered to what survives the rebuild | `.rework/ISSUES.md` |
| `docs/09_PREFERENCES.md` | every non-definitive preference, dated, with its evidence | survey `facts` |
| `docs/10_GLOSSARY.md` | terms whose meaning changed, dated (G12) | survey + archive |
| `docs/dropped_levers.md` | every dropped knob and why (G10) | `tools/lever_census.py` |
| `docs/evidence/` | the two irreplaceable primary sources, verbatim | `notes/_evidence/commit_log.txt`, `chat/user_turns.md` |
