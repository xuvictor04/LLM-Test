# Decisions — the owner's rulings, dated

Binding. Where a ruling supersedes an earlier one, both are shown. Everything here is a DECISION or a
PREFERENCE; the only DEFINITIVES remain the two goals.

---

## D1 · 2026-08-28 · The Fabric stays
> "fabric must stay, it has been crucial in learning process. A lot of the info there may be from old runs."

**Ruling: keep.** And the correction is upheld — the evidence I offered against it was bad on three counts:

1. `nofabric` ties `pop1024` and "the base model is 0.285 b/B worse standalone" are both **round9**,
   pre-git-era, before 2026-08-15 and dozens of subsequent fixes.
2. "479 experts buy −0.002 b/B" comes from SUFFICIENCY, which calls `fab.society(...)` unconditionally
   while the shipped default is `SOCIETY=0` chaining — it measures a forward path the run never trained.
   **Void**, same class as `compose_test`.
3. The whole routing/specialization instrument set is void independently, via the one-byte eval signature.

Recorded as a correction against myself: stale numbers from a void instrument were presented as evidence
against the core of the architecture. The project's own carry-forward note already said it — *"Never infer
coverage from a config file — infer it from a log."*

**Consequence:** Q1 no longer blocks P3. The fabric is in the rebuild. Whether it specializes becomes a
question the new instruments answer at P6, not a question settled by old numbers.

## D2 · pending · The continual-learning protocol
> "that is up for decision. I'm not too sure of the differences."

**Open.** Recommendation on the table: `PURE_ADD` as the headline measurement, rehearsed as a named
comparison arm, both run every time. Rehearsal is a solution, not a measurement — with it on by default,
the architecture's own contribution to retention is indistinguishable from replay's.

## D3 · 2026-08-28 · Reservoir quota, with the literature kept as an arm
> "lets test literature, but for now adopt the reservoir quota"

**Ruling: adopt the reservoir quota as the default.** The 2026-07-21 ruling (a strict per-domain quota
fights growability; pressure should be a signal, not a wall) is **superseded as the default** but retained
as a selectable arm, so the two are measurable against each other on the add-area benchmark.

Note the reason it moved: the observed failure was one source ending up owning 88% of a 200,000-entry
store, which is the exact dilution the class-balanced reservoir literature addresses.

## D4 · 2026-08-28 · The world model stays, and is cleanly switchable
> "stay, since we will use it in future. Maybe it can be off in some tests"

**Ruling: keep, and make OFF a first-class configuration** rather than a code path that rots. Its record
(413 measurements, none above baseline) is a reason to keep it *measured*, not a reason to cut it.

Open sub-question: my Q4 also covered reconstruction-based **Verification** (dead at the base-rate wall,
report line in zero logs). Read as covered by the same ruling unless told otherwise — kept, switchable.

## D5 · 2026-08-28 · `rm-predict` is frozen
> "freeze rm-predict"

**Ruling: frozen** as the historical baseline. All work continues on `rm-predict-DC`. This supersedes the
standing constraint *"commit and push to rm-predict only."* The last commit on it is `aee4a52`.

## D6 · 2026-08-28 · The compaction summaries are the record for the lost window
> "the exchanges are with you, use them"

Verified: the raw transcript for 2026-08-15 → 08-17 does not exist on disk — one transcript file, no other
project directories, and its line 2 is a compaction summary. **Four** compaction summaries survive
(63,000 chars total), preserved verbatim in `.rework/COMPACTION_SUMMARIES.md`:

| line | timestamp | chars | covers |
|---|---|---|---|
| 2 | 2026-08-17T20:30 | 17,935 | **the lost window — unique record** |
| 1888 | 2026-08-22T04:51 | 15,700 | condenses raw lines still present |
| 3928 | 2026-08-27T15:09 | 15,657 | condenses raw lines still present |
| 6544 | 2026-08-28T00:37 | 13,674 | condenses raw lines still present |

**Ruling: use them.** The line-2 summary is treated as the record for that window, marked in the timeline
as summary-not-transcript. The session's *work product* — the entire `notes/` corpus — survives intact and
is the stronger evidence of what was decided there.

## D7 · 2026-08-28 · Interchangeability is not automatically a failure
> "likely the system will need to be trained more, another way to enhance specialization, or accept the
> interchangeability, since some skills are inherently interchangeable"

**Ruling: three live hypotheses, none foreclosed.** `SPECIALIZATION` reading INTERCHANGEABLE may mean
(a) undertrained, (b) specialization needs a different mechanism, or (c) **the correct answer for skills
that genuinely overlap**. (c) is now an accepted possible outcome rather than a defect to be fixed.

This connects to the owner's own foundational statement of what the fabric is for, 2026-07-31:

> "The expectation is that none of the individual experts are sufficient for the tasks at hand, but
> aggregate, they are. The hope is that the structure of selection drives this..."

If **aggregate** sufficiency is the goal, then overlap among experts serving overlapping skills is the
expected state, not a fault. The instrument must therefore be able to report "interchangeable, and that is
correct here" — which the current binary verdict cannot express. Filed as a requirement on P6.

## D2 · 2026-08-28 · `PURE_ADD` is the default continual-learning protocol
> "Pure add seems to be for testing of adding new domains, lets keep it as default for now."

**Ruling: `PURE_ADD=1` is the default.** The added area streams alone; the previously-learned area is not
rehearsed. Rehearsed (`PHASE_SCHED` `[[0],[0],[1],[1]]`) is retained as a named comparison arm.

The reasoning that settled it: rehearsal is a *solution*, not a *measurement*. With it on by default the
architecture's own contribution to retention cannot be separated from replay's. The two arms disagreed 10x
on the same toy (`+0.046 HELD` rehearsed vs `+0.444 WORSE` pure), so the choice decides whether the system
appears to satisfy goal B.

"for now" is recorded: this is a default, not a definitive, and it is expected to be revisited once the
rebuilt instruments can measure the two arms against each other honestly.

## D8 · 2026-09-02 · The exposure draw law is a lever, and `planned` is the default
> "We can make H58 a lever, and make planned default."

**Ruling: lever.** `DATA_DRAW`, choices `("planned", "uniform")`, **default `"planned"`**.

ISSUES P1-H58 measured that `DATA.data_plan`'s exposure gates tested the SCHEDULED per-area split
while `DATA.draw_stream` chose an area uniformly at random per segment — so the run trained on a draw
from that distribution rather than the distribution, with a worst per-area deviation of **47.9%** over
eight seeds. The guard against P3-H22 could therefore read *"armed, did not fire"* on a run whose
realized exposure had crossed its threshold.

* **`planned`** gives every live area its scheduled share of the phase and randomises only the
  segment order and the offsets each is read from. Verified **0.00%** deviation over eight seeds,
  with `len(Stream.bytes) == DATA_STREAM_BYTES` still exact.
* **`uniform`** is the law every recorded result in this project was taken under, kept — not dropped —
  under the standing rule that a mechanism kept for future use is kept with a switch. Verified
  **47.93%**, unchanged.

`planned` is the default because it is the only value under which the startup gate is EXACT, and a
startup gate is the only thing that can refuse a bad configuration *before* it spends GPU time.

**Not superseded:** reporting realized whole-run exposure at the end of a run still proves what
`planned` only predicts, and is the only thing that would catch a `uniform` run that went wrong. It
stays open as P5/P9 work — realized exposure does not exist until the last epoch is drawn.

## D9 · 2026-09-02 · Everything is documented on the GitHub page; the README is a live document
> "For everything we are doing, make sure that it's being documented as I've previously mentioned in
> the GitHub page."

**Ruling: standing requirement, not a one-off task.** `README.md` is this project's GitHub landing
page and it is part of the deliverable, not a courtesy. Two obligations follow, and they are checkable
rather than aspirational:

1. **It describes the tree that exists.** At the time of this ruling the README documented the OLD
   tree exclusively, and three of the files it tells a reader to "Start here" with — `STATE.md`,
   `garry/GARRY.md` and `CL_TESTBED.md` — had been moved under `archive/`. A landing page that names
   paths the repository does not have is the citation-rot class (O12, N7) on the one file every
   reader opens first.

   **CORRECTION, same day, against myself.** The first version of this entry also asserted that
   `run_full_unfrozen.sh` and `self_organize.py` had moved under `archive/`. They have not: both are
   still at the repository root, alongside 48 other top-level scripts, and `self_organize.py` is
   828 KB of live code. A research agent verified the filesystem and contradicted me; I had inferred
   the move from the fact that the REBUILD lives in `src/` and never checked. The consequence for the
   page is the opposite of what I wrote — the old tree's COMMANDS still work, and what is stale is
   narrower and more specific than "everything". Recorded rather than quietly fixed, because the
   error is the same shape as the defects this project exists to catalogue: a plausible claim about
   a tree, asserted without reading it.
2. **It republishes no retracted number.** The README's headline paragraph quoted measured figures
   sourced to `STATE.md §7`, and ISSUES P2-C3 records that that section is headed *"authoritative"*
   while every headline number in it is void under a later invalidation. Any figure on the landing
   page must survive the same test every number in `docs/` does: name where it comes from, and check
   whether anything retracts it.

**Consequence for how work proceeds:** a change that moves a number, a path, a default or a claim the
landing page makes is not finished until the page agrees with it. This sits alongside the owner's
earlier standing instruction — *"tell me the defaults, so I know what is off and on"* — which the page
is the natural place to satisfy for a reader who is not in this conversation.

## D10 · 2026-09-02 · Ultracode is the default working mode; the assistant supervises
> "I want ultracode to always be default, but I'm unable to set it. You should be offloading as much
> of your load to these agents, since we are working on large and many changes."

**Ruling: standing.** Substantive work is decomposed to agents and orchestrated, not performed in the
main context. The assistant's primary job is **supervision, correctness assurance, and memory
management for those agents**:

* **Supervision** — hand agents a CONSISTENT baseline (suite green, nothing half-applied), read what
  they return rather than trusting it, and verify a fix before it is committed.
* **Correctness assurance** — findings are adversarially verified before they are acted on, and a
  repair is audited as new code rather than credited as a fix. Three defects in this project were
  "fixed" on one branch and left live on another, so a repair's *coverage* is checked, not assumed.
* **Memory management** — durable state goes on disk where an agent can read it, not through the
  conversation. Round 1's 66 findings live at `.rework/audits/p4_round1_findings.json` for exactly
  this reason: the next round reads the file instead of being retold.

This ruling is about METHOD and does not touch the two definitive goals.

## D11 · 2026-09-03 · A recommendation is a researched artefact, not a generated one

> "From now on your recommendations, if you haven't, should be researched and thought out, with
> rationales, alternatives, etc… I don't want material plain generated from you."

**Ruling: standing, and it binds the assistant rather than the code.** When the assistant proposes a
course of action — what to fix next, which of two repairs to take, whether a mechanism should be a
lever, what a default should be — that proposal must be the OUTPUT OF RESEARCH, not the output of
fluency. Concretely, a recommendation that reaches the owner carries:

1. **What was actually read or run.** The files, the measurements, the commands. A recommendation
   with no evidence trail is an opinion wearing a recommendation's clothes, and this project's whole
   subject is plausible statements that were never checked. The assistant has already produced two of
   those in this session — asserting the old tree had moved under `archive/` (it had not, and an
   agent checking the filesystem contradicted it), and blaming concurrency for an API failure that
   was model capacity (four runs and ~50 lost agents before a controlled A/B settled it).
2. **The alternatives that were considered and why they lost.** Not a strawman pair. If there is only
   one option, say that and say why the space is that narrow.
3. **What it costs and what it forecloses.** Including the case where the answer is "do nothing yet".
4. **What would change the answer** — the measurement that would settle it, since the owner has ruled
   that *"the ultimate deciding factor will be performance"* and *"if anything needs gpu time, I will
   run it"*. A recommendation that cannot name its own falsifier is not yet finished.

**WHY THIS IS NOT ALREADY COVERED BY D10.** D10 says substantive WORK is decomposed to agents. This
says the same of JUDGEMENT. The two failure modes differ: D10 guards against the assistant doing by
hand what a fleet should do, while D11 guards against the assistant *summarising* agent output into a
confident recommendation the agents never actually supported. The second is harder to see, because
the prose reads the same either way.

**WHAT IT DOES NOT MEAN.** It does not mean every question goes to a workflow before it can be
answered — a factual lookup is a lookup, and stalling on ceremony is its own failure. It binds
RECOMMENDATIONS: proposals about what the project should do next.

This ruling is about METHOD and does not touch the two definitive goals.

---

## D12 · 2026-09-03 · `RUN.process_setup` owns torch's global generator, and says what that does not buy

The `lm` fixer found a defect it could not fix inside its own package and referred it up: nothing in
the tree seeds torch's PROCESS-GLOBAL default generator, so at `LM_DROPOUT>0` two runs at the same
`RUN_SEED` diverge and G2's determinism floor absorbs the difference. `nn.Dropout`,
`nn.TransformerEncoderLayer` and `torch.nn.functional.dropout` take no `generator=` argument at torch
2.13.0+cu130, so the per-subsystem streams this tree is built on structurally cannot reach them.

**Four options were weighed.**

| | option | why it lost, or won |
|---|---|---|
| (a) | seed the global inside `RUN.process_setup` | **CHOSEN**, refined — see below |
| (b) | declare `"torch.global"` in `compose.RNG_SUBSYSTEMS` so `RUN.streams` mints it like any other | rejected: `rng_for` raises on re-issue, so the name could be minted once per process and `process_setup` could not be called twice; and it would advertise a *stream* where what exists is a *seed* |
| (c) | thread an explicit generator to every consumer | rejected on evidence, not taste: the three call sites have no parameter to receive one. Checked at the installed torch version rather than assumed |
| (d) | leave it, and make the non-determinism merely REPORTABLE | its argument is **correct** and is answered rather than dismissed — see below |

**Option (d)'s objection is the important one, and it shaped the fix.** A silent process-wide
mutation is exactly what the ownership spine exists to prevent, so the answer is not to decline the
mutation but to make it *declared and checkable*. `Process` gains a frozen `torch_seed` field READ
BACK out of `torch.initial_seed()` after the write — the same shape `Process.tf32_applied` already
has, which records "THE PAIR OF VALUES ACTUALLY WRITTEN, not the requested flag". The read-back is
the load-bearing half of the ruling, not decoration: it is what turns seeding into a DID IT FIRE
line instead of an invisible side effect. No new idiom enters the package.

On the docstring's own phrase — "the process-wide arithmetic settings ONCE, before any package is
built" — the ruling is that this is not being stretched. A generator seeded from OS entropy is
process-wide in the same sense tf32 is, and is strictly *narrower*: tf32 moves the arithmetic, while
seeding changes nothing about what is computed and everything about whether two runs of it agree.
The call is placed before the tf32 writes so "before any package is built" is literally true.

`"torch.global"` IS A DERIVATION LABEL, NOT A MINTED STREAM. It goes through
`spine/rng.py::derive_seed`, a pure blake2b of (run seed, name) that mints nothing, so the function
stays callable twice in one process — which `rng_for` would not be. Nobody should grep for it in
`rng.py::issued()`.

**WHAT THIS DOES NOT BUY, stated because a determinism claim that overreaches is worse than none.**
Seeding gives every run at one seed the same sequence. It does NOT give each package an independent
one: every consumer that cannot take a `generator=` still draws from one shared stream, so torch
DRAW ORDER remains a channel between packages that no wire covers. That is a real remaining coupling
and it is recorded here rather than papered over.

**NARROWED 2026-09-04, because the sentence above was wider than the tree.** As first written this
paragraph continued: *"Adding a package that draws from the global, or reordering two that do, still
moves the numbers of every package downstream of it."* An independent verifier measured both halves
of that instead of reasoning about it, and only one half holds. Overstating a limitation is the same
failure as overstating a guarantee, so the measured version replaces it:

- **The build-time half is NOT true of this tree today.** Inserting 1 or 3 extra global draws between
  `LM.build_model`'s return and the rest of `compose()` — exactly what n extra dropout masks would do
  — leaves all 363 built values byte-identical (digest `34acff0aeb14dd4b` in all three runs) while
  moving `LM.encode` (`26905f11…` → `773820fb…` → `0b850362…`). On a real lever, `LM_LAYERS` 2 vs 4
  moves NOTHING outside LM: zero non-LM keys differ. The reason is structural — every package that
  constructs an `nn.Module` then OVERWRITES every parameter from its OWN named stream
  (`lm/api.py::build_model`'s `named_parameters` loop, `sig/api.py::_Encoder.__init__`,
  `fabric/api.py::build`'s `pop.modules` loop, `world/api.py::build`'s three loops).
- **The runtime half is SINGLE-ENDED.** An exhaustive grep for every RNG-consuming torch call in
  `src/` (`rand`, `randn`, `randint`, `randperm`, `multinomial`, `bernoulli`, `normal`, `poisson`,
  the `*_like` family, `nn.init.*`, the in-place samplers, functional dropout) returns exactly three
  hits, all in `src/sig/api.py` and all passing `generator=`. The only implicit consumers left are
  `nn.Dropout` and `nn.TransformerEncoderLayer`'s internals — so **LM is the only package that draws
  from the global generator at runtime**, which is why the demonstration below needs a bare probe as
  its downstream consumer rather than another package.

**The channel is real, and it is exhibited rather than asserted.** At `LM_DROPOUT=0.2`, `LM_LAYERS` 2
vs 4 moves a downstream consumer's draws (`5f87be0f…` vs `36dc18c1…`, next `torch.rand(3)`
`[0.180, 0.733, 0.012]` vs `[0.621, 0.406, 0.741]`); **the control is what makes it a measurement** —
the same two depths at `LM_DROPOUT=0.0` give identical downstream values. So the honest statement is
that the coupling ARMS the moment a SECOND package draws from the global at runtime, or a package is
built lazily after a forward. Today neither is the case.

**Verified, by the supervisor, after the agent's own verifier was killed by the session limit.** Two
fresh processes at `RUN_SEED=0, LM_DROPOUT=0.2` now report identical `torch.initial_seed()`
(3734753547471956429) and identical `LM.encode()` sums (0.768035); `RUN_SEED=7` gives a different
seed and a different sum (4.814884), reproducibly. Both halves matter — a fix that made every seed
agree would be a worse bug than the one it replaced.

---

## D13 · 2026-09-03 · `FAB.state_dict`'s list and `FAB.build`'s allocation must agree name for name

`FAB.build` allocated five of the nine module-level names `FAB.state_dict`'s docstring lists as
checkpointed Parameters. `halt_b`, `norm`, `q_entry` and `nov_proj` were declared and never built —
so a checkpoint round-trip silently lost each of them.

The fixer that referred this up gave a blocking premise: that these names "have no specified shape
anywhere in the reachable tree". **That premise is false**, and establishing so is what unblocked the
ruling — all four are minted with exact constructors in the frozen old tree at
`self_organize.py:1733` and `:1907-1908`.

Re-reading the call sites splits the four cleanly, so no single answer covers them:

- `norm`, `nov_proj`, `halt_b` are read on the walk **this tree ports**, so `FAB.build` now builds
  them, to the old tree's own constructors.
- `q_entry`'s readers all belong to arms this rebuild has **explicitly dropped**. It is
  therefore dropped from `state_dict`'s list, exactly as `ctrl` was, with the reason recorded —
  which **reverses** that docstring's own earlier ruling that "q_entry and nov_proj stay, because
  both walks use them". Half of that sentence survives; half does not, and the reversal is written
  down rather than quietly applied.

**CORRECTED 2026-09-04 — the count in this ruling was wrong, though the ruling was not.** This entry
said "only three readers", and the `fabric+ckpt` repair agent measured **six** by AST; the
`FAB.forward` author independently found the same six plus a seventh consumer that reads the name
rather than the attribute, and the verifier established that this seventh is already cited at HEAD
inside `FAB.state_dict`'s own docstring as the "audit loop". So **seven** consumers, not three.

**None of them changes the verdict** — every one still belongs to a dropped arm, which is the fact
the ruling turns on — but the number was carried into a decision entry from a filing rather than
measured, and a decision that cites a count it did not check is the thing D11 exists to stop. The
count is corrected here rather than in place, so the error and its correction are both legible.

The rejected alternative was raising `NotBuilt` at the point of use for names P4 has not reached.
It loses because these names are not deferred mechanisms — three are needed by a walk that exists,
and the fourth belongs to a walk that does not. `NotBuilt` would encode "not yet" for a case that is
actually "never".

---

## D14 · 2026-09-03 · `CKPT.save_period` keeps its return type and carries its Gate on it

`CKPT.save_period` returned a bare `units.Windows` and declared no Gate, though its own DID IT FIRE
line has always claimed one for the dir-set-but-`every==0` condition — "the only saves are the final
one plus SIGUSR1", which is precisely the armed-but-0 versus UNREACHABLE distinction `spine/gate.py`
exists for.

**The return type does not change.** Widening it to a `(Windows, Gate)` pair or a new record would
touch `spine/compose.py`, which the ruling's owner did not own, and would make the call shape a
second thing to keep in sync. Instead `Gate('ckpt.periodic_armed', ...)` rides on the returned
`Windows` as a `.gates` tuple — the same convention FAB, CAP and MEM already use — with all three of
`gate.py`'s states spelled out. Unchanged type, unchanged call shape, and the declared Gate now
exists.

What is still owed is recorded rather than taken: CKPT has no package-wide DID IT FIRE accessor, and
giving it one needs `docs/04_CONTRACT.md` and `spine/compose.py` together. Referred, not spent.

---

## D15 · 2026-09-03 · A Gate's reachability is keyed on the arm it reports, not on the package switch

`capacity/api.py::new_valve` built `Gate cap.vocab_arm_honest` so that on the **shipped defaults**
(`CAP_TARGETS=off`, `LM_MASK_DEAD_ROWS=False`) it printed "armed, did not fire" — a reachable,
unfired reading — for a mechanism that could not fire on any configuration of `LM_MASK_DEAD_ROWS`,
because `CAP_TARGETS=off` means no vocabulary lift ever happens. Its sibling `cap.valve`, two lines
above, evaluated the same condition correctly. Every stock run of this tree printed it.

The filed fix proposed keying reachability on `targets == "off"`. **The ruling is narrower and the
difference is the point:** reachability is keyed on whether the VOCABULARY ARM is armed —
`targets in ("vocab", "both")` — and the unreachable arm prints `targets` against `'vocab|both'` as
its arithmetic, mirroring `cap.valve`, with `LM_MASK_DEAD_ROWS`'s value carried in the reason so
nothing is hidden.

The filed fix would have been right on the shipped default and **wrong at `CAP_TARGETS=experts`**,
where the valve is on, the package switch is not "off", and yet no vocabulary lift can happen either.
A Gate reports one mechanism; its reachability belongs to that mechanism's own arm, not to the
package-level switch that merely happens to disable everything at the default. Generalised: when a
Gate and its package switch appear to ask the same question, they agree only at the defaults.

This is the first finding filed against `capacity/`, which — with `eval/` — had never been audited by
anyone: neither appears in any findings file and neither had an entry in `.rework/audits/todo/`.
That pass found six further defects, among them a mutable default shared across every `Valve` in the
process and a sentinel collision in which an explicitly-set `CAP_FAB_START=0` resolves a soft expert
cap of zero.

---

## D16 · 2026-09-04 · An overshooting lift is soft-clamped at the ceiling, not refused

> "let's soft clamp if a ceiling is overshot, until it goes down."

**Ruling: clamp.** A soft cap set just under the hard ceiling makes the FIRST earned lift overshoot,
and nothing in the tree said whether `CAP.observe` refuses that lift or clamps it. Two independent
agents found the gap while driving other work and both declined to close it, correctly — it is a
question about what the valve is *for*, not a bug with an obvious repair.

**Why clamp is the right answer, stated so it can be overturned on evidence.** A refusal WASTES THE
EVIDENCE. The valve exists to lift a cap when the population has earned it; a run that earns a lift
and is told "no, that would overshoot" has paid for the observation and received nothing, and the
next evaluation starts from the same place. Clamping spends the evidence on the largest lift
available — which at the ceiling is the distance remaining — and leaves the cap where the operator
set the hard limit. The module's founding sentence is that a ceiling is *"raised, by a little, NEVER
lowered"*; clamping honours it and refusing does not engage with it at all.

**THE CLAMP IS A THIRD READING AND MUST NOT COLLAPSE INTO THE OTHER TWO.** This valve's whole
recorded history is mechanisms that fired or did not fire without saying which, so a clamped lift —
neither a clean fire nor a refusal — needs its own counter and its own Gate arm. There are now FOUR
states the ledger must distinguish, and three of them are already occupied by different mechanisms:

| state | meaning | already owned by |
|---|---|---|
| no lift earned | the condition was evaluated and not met | the armed-but-0 arm |
| lift earned, applied in full | the ordinary case | fired |
| lift earned, CLAMPED at the ceiling | **this ruling** | new |
| no lift can ever be earned | `CAP_TARGETS` excludes the arm | UNREACHABLE, per D15 |

and two further not-moving cases must not be mistaken for a clamp: a lift refused by name as
`dead_rows_unmasked` when `LM_MASK_DEAD_ROWS` is off, and `derive.lift_to` returning the cap
unchanged when both its terms round to zero — the case `capacity/levers.py` already records as the
reason `lift_min` exists.

**ON "UNTIL IT GOES DOWN", WHICH CARRIES REAL INTERPRETIVE LATITUDE.** Two readings are available:
the clamp is a STATE, pinned at the ceiling and released when demand falls; or the clamp is a
per-lift arithmetic operation with no state, and the phrase merely describes what a later evaluation
asking for less will do. The implementing agent was instructed to establish which the mechanism can
actually support — whether `Valve` persists anything across flushes — to take that one, to record
which reading it took *in the docstring*, and to report whether the other reading behaves
differently and how the owner would tell. A ruling implemented under an unstated interpretation is
how a decision quietly becomes something else, and this project has the receipts.

---

## D17 · 2026-09-04 · A negative period is refused, and the refusal is switchable

> "On the periods, let's refuse for now. If it has a bad effect, we can turn off the refusal."

**Ruling: refuse.** `CKPT.save_period` was given a refusal for a negative `CKPT_EVERY` after its Gate
was found printing `CKPT_EVERY=0` beside a rendered value that was not 0 — the false-equation class.
That made CKPT the second package raising the spine's `LeverError` from a body, `CAP` being the first
(for a negative `CAP_LIFT`, on the ground that a mechanism running backwards on the evidence it
should run forwards is a defect arriving through a lever *value* rather than a guard). The open
question was whether the other four period accessors — `EVAL.curve_period`, `DOM.manage_period`,
`FAB.manage_period`, `MEM.rekey_period` — should do the same. They should.

**THE SECOND SENTENCE IS AS BINDING AS THE FIRST.** *"If it has a bad effect, we can turn off the
refusal"* means the refusal must be turn-off-able **without editing code**. That is this tree's
standing rule, set in D4: a mechanism kept for future use is kept WITH A SWITCH, not as a code path
that rots. A refusal that can only be withdrawn by reverting a commit fails the instruction.

The implementing agent was asked to weigh three carriers under D11 and to recommend rather than
assume:

- **one RUN-owned switch read by all five accessors** — but a lever crossing a package boundary is a
  WIRE, and five wires is unaffordable against the six edges remaining of `WIRE_BUDGET=25`, so this
  only survives if the accessors can reach it without spending one;
- **one lever per owning package** — no wire, but five declarations and five census rows;
- **no lever**, on the reading that the owner would revert rather than flip a switch — which is the
  reading D4 exists to rule out.

It was instructed that if a wire is genuinely required it must **report** rather than spend one.

**WHAT MUST BE CHECKED BEFORE EACH REFUSAL LANDS.** For several of these levers a period of **0** is
a legitimate sentinel meaning *"never"* or *"every window"*, and refusing negatives must not disturb
it. Each accessor is to state what 0 means for its own lever, what a negative does today, and what
the refusal changes — and where an accessor already refuses, or structurally cannot receive a
negative, to say so rather than invent work.

**This ruling is explicitly provisional.** "For now" is recorded. The refusal is expected to be
revisited if it turns out to forbid a configuration someone wants, and the switch exists so that
revisiting it costs an environment variable rather than a commit.

---

## D18 · 2026-09-14 · Where a lever's upper end lives — the declared domain and the finiteness floor, adopted together

The options were researched under D11, put to the owner as a comparison of five carriers, read, and
the **recommended pair was chosen**: a finiteness floor inside `Lever.coerce` *and* an optional
`domain=(lo, hi)` on the declaration, plus the integrality clause the report filed as its first
amendment. All three landed in `src/spine/lever.py` in one commit.

**THE QUESTION WAS NEVER "SHOULD LEVERS HAVE RANGES", AND READING IT THAT WAY LOSES THE RULING.**
That question was already answered YES, by thirteen packages that had written ranges by hand, one
body at a time, whenever their author got to it. The open question was **where the upper end of a
number lives** — and, underneath it, whether *"this lever has no ceiling"* is a sentence somebody
has to **type** or a sentence that is true **by default because nobody typed anything**. The
tree's own record answers that before the ruling does: of the ten OPT levers carrying a startup
refusal, seven were bounded **below only**, and those seven are exactly the ones the sweep found
harmful. That is not carelessness and it is not placement. A careful author holding the mechanism
writes the bound whose violation they can *picture* — a negative rate — and omits the one they
cannot: a rate twenty-four orders of magnitude too large. **Moving the check to the declaration does
not fix that by itself, because `hi=None` is one keystroke**, and this ruling does not claim it does.

**WHY THE FLOOR AND THE DOMAIN ARE COMPLEMENTS AND WERE BUILT TOGETHER, WHICH IS THE ONE RESULT
THAT DECIDED IT.** They are not a weaker and a stronger version of one rule; they cover **disjoint
halves** of the special-value surface, and this was measured rather than argued. Any finite endpoint
refuses `nan` for free, because the comparison is written as an inverted chain. A finite **low** end
refuses `-inf`. But **only a finite HIGH end refuses `+inf`** — and `hi=None` **admits** it. Under an
honest, evidence-led population, **163 of the 207** numeric levers get no ceiling, **53 of them
floats**, which is where `+inf` can be coerced at all. So `domain=` **alone** would have left `+inf`
legal on 53 float levers, including `OPT_LR`, `OPT_WEIGHT_DECAY`, `SIG_VAR_WEIGHT`, `SIG_COV_WEIGHT`
and `FAB_ROUTE_T` — five of the sweep's own critical findings. Taking exactly one of the two would
not have been choosing a lighter rule; it would have been choosing **which half of the surface to
leave open**.

**THE LIMIT, IN THE RULING ITSELF, SO NOBODY READS THE RULING AS MORE THAN IT IS.** The finiteness
boundary and the harm boundary are **twenty-four orders of magnitude apart**. `OPT_LR=1e6` runs all
five stages reporting OK, reports `p_finite=True`, and leaves every parameter at **−3928** — the
model destroyed, and finite, so every `isfinite` check in the tree passes over it. `FAB_ALPHA=1e26`
is finite, prints an ordinary-looking loss pair (`aux 0.5150710`, `composed 2.943258`), and already
leaves **15 of 23** gradient-carrying tensors non-finite, which is *worse* than `+inf`, since `+inf`
at least comes back `nan` where a report can see it. And a ceiling mostly does not exist to choose:
of the 207, **131 have no derivable ceiling at all** — the harmful value is a floating-point
dynamic-range or memory property of the mechanism, not of the declaration — **16 have one this tree
has explicitly DECLINED to set**, and **15 have a ceiling that is another lever or a wire**
(`LM_CTX ≤ d_pos_max`, `WORLD_N0 ≤ WORLD_NMAX`, `MEM_KEY_DEPTH ≤ LM_LAYERS`) and **cannot be a pair
at all**. Those fifteen belong at the read site permanently, which is why the read-site option does
not go away under this ruling or any other.

**WHAT WAS DELIBERATELY NOT DONE, AND THIS IS THE SENTENCE THAT STOPS THE MISREADING.** Only **33 of
the 207** levers were given a pair — the 33 whose *both* ends are obvious from the declaration with
no measurement, no policy choice and no ruling overturned. **NOT ONE of the seven levers the sweep
filed as critical for a magnitude is among them**: `FAB_ALPHA`, `FAB_CENT_EMA`, `FAB_ROUTE_T`,
`OPT_LR`, `OPT_WEIGHT_DECAY`, `SIG_VAR_WEIGHT`, `SIG_COV_WEIGHT` carry no pair and are not going to
get one from taste. **THE 33 ARE REAL AND THEY ARE NOT WHERE THE HARM IS.** Nothing here makes any
lever safe, bounded or validated; no docstring in `src/spine/lever.py` says otherwise, and none may.
Populating further is a **per-lever measurement**, not a typing exercise — 46 of the 207 have a low
value whose meaning is a declared or measured-legitimate sentinel, and only 22 of the 207 mention
their special value in the help string at all, so an author writing a pair from the declaration
alone would get 24 of those 46 wrong and delete a working mechanism each time.

**THE FLOOR IS SWITCHABLE, UNDER D17'S STANDING RULE, AND WHAT TURNING IT OFF COSTS IS WRITTEN
DOWN.** `spine/lever.py::REFUSE_NON_FINITE_FLOAT` is a module constant carrying its own cost in its
own docstring, in the shape D17 settled on. **The switch is a code edit and not an environment
variable, and that is a deliberate shortfall against D17's second sentence, not an oversight.** A
lever-shaped switch is circular — the rule runs *inside* `Lever.coerce`, before any `Config` exists
— and the only environment form left would be a raw `os.environ` read inside `coerce`: legal in
that one file, and the tree's first environment name that is not a lever, invisible to
`spine/registry.py`, to `tests/test_census.py`'s N1/N2 join, and to the planned
`docs/04_LEVERS.md` (named by three `levers.py` files, not yet on disk). That is the
exact failure `src/spine/lever.py` exists to end, so the spelling was refused and the shortfall
recorded. **Off costs this**: `nan`, `inf` and `-inf` resolve into frozen `Config`s again on all 97
float levers, and what is left standing is the five per-package by-name refusals, which cover only
the levers those bodies actually read — and roughly 288 cells across the six sweep reports are
`UNREACHABLE_TODAY` because the consumer is a P4/P5/P6 stub. **A body that does not exist cannot
refuse anything.** `domain=` itself carries **no** switch, and that asymmetry is intended: its blast
radius is one lever and deleting the kwarg is the switch.

**`REFUSE_INEXACT_INT` IS A BEHAVIOUR CHANGE TO EVERY INT LEVER, AND THE SCAN IS RECORDED HERE
BECAUSE A FUTURE READER WILL ASK.** An int lever now resolves to the integer its string denotes or
is refused; the rule is **losslessness, not notation**, so `"8.0"` and `"1e3"` resolve normally and
`"0.4"` and `"1e26"` do not. The blast radius was **scanned, not estimated**: every assignment site
of every int lever's environment name across `src/`, `tests/`, `tools/`, `docs/` and the root
scripts — **1093 sites in 78 files — and exactly ONE is non-exact**, `MEM_QUOTA=0.4`, which is prose
inside a comment in `src/memory/api.py` describing this very defect, not a configuration. No script,
sweep, test or recorded configuration in this tree sets an int lever to a non-exact value. *(Re-run
independently on 2026-09-14 under a narrower pattern and file set — 520 sites in 54 files — which
found the same four textual hits and no fifth: all four are prose, in `src/memory/api.py`,
`src/spine/lever.py` twice and `docs/04_CONTRACT.md`. The two scans disagree on population size and
agree exactly on the answer: zero live configurations break.)* The class it closes is worse than the
arithmetic it corrects: `MEM_REKEY_EVERY=0.4` used to truncate to `0`, and `0` is that lever's
**declared disarm**, so an operator asking for the tightest cadence silently received the off switch
with `Config.given()` still reporting `'0.4'`.

**TWO THINGS THE IMPLEMENTATION SETTLED THAT THE RECOMMENDATION HAD LEFT OPEN, RECORDED SO THEY CAN
BE OVERTURNED ON EVIDENCE.** The research asked for the domain to be written as **three** fields —
a pair plus inclusivity — on the ground that one function alone, `src/opt/api.py::build`, held an
open low end, a half-open interval and a closed one. **What shipped is a two-field pair, CLOSED at
both ends**, and the argument is from the levers that were about to use it: on that population both
endpoints are values somebody configures (`src/opt/api.py::build` accepted `OPT_LR_DECAY=1.0` by
name already), so an exclusive end would have **refused a value a shipped body accepts**. A
declaration needing an open end writes the closed pair that *contains* its interval and keeps the
strict clause at the read site — it under-refuses by exactly one endpoint and never over-refuses.
`LM_DROPOUT` and `OPT_LR_MIN_FRAC` are both that shape on the real tree and both were driven: `1.0`
resolves, and the body then refuses it by name. **That is a real trade and the three-field form
remains available**; what it would cost is a second vocabulary in the spine.

**WHAT THE RULING COST ON THE DAY IT LANDED, WHICH IS THE PART A DECISION RECORD USUALLY OMITS.**
Writing a pair over a lever whose body already refused the same interval leaves that body's clause
**unable to run**, and a guard whose condition cannot be satisfied is the **untrippable-guard
family** — the second-largest class in this project's founding census. Populating 33 declarations
created **six** of them in one commit, and the only reason anyone knows is that
`tests/test_ownership.py::check_o15_domain_agrees_with_read_site` was written in the same commit and
reported them. **The fork is RETIRE-OR-DROP and never both, decided per lever**: either the clause
retires and everything it argued moves to the declaration, or the pair is dropped and the ruling
stays where it was argued. Four were closed the same day by retiring, with the measurement carried
across rather than deleted, and one retired sentence was found to have **rotted while it could
still print** — `OPT_LR_RESTART_DAMP`'s message claimed a value above 1.0 amplifies every failed
restart, while `src/opt/api.py::maybe_step` guards its one multiplication with
`float(opt.lr_restart_damp) < 1.0`, so above 1.0 the loop goes inert and amplifies nothing. It is
recorded corrected, not requoted. **Two remain open and are not hidden**: `SIG_WARMUP_MIN_FRAC` at
`src/sig/api.py::warm_up` and `TOK_DROPOUT` at `src/tok/api.py::build_vocabulary`. The standing
instruction for both is the fork above, decided on the lever and not on the convenience of a green
suite.

**WHAT THIS RULING DOES NOT CLOSE, NAMED SO THE COUNT IS NOT READ AS A SCORE.** Of the 37 findings
the non-finite sweep filed, the pair closes 33 and misses four, each for a different reason: a large
finite magnitude (`FAB_ALPHA=1e26`, `OPT_LR=1e30`) on levers whose ceiling is not derivable; a
fractional string truncating into a declared disarm, which no `(lo, hi)` pair catches because `0` is
*inside* the domain and which is why the integrality clause was taken as well; `FAB_SLOTS=0`, where
`0` is legitimate at `FAB.build` and the defect is in `spine/derive.py::operating_population`; and
`FAB_MANAGE_EVERY=0`, half closed, still needing `spine/derive.py::flush_period_windows`. The
falsifier for the whole shape is also on the record and was not run: re-drive the 53 open-topped
float levers at {1e12, 1e20, 1e26, 1e30}. **If** the harm boundary clusters, a single universal
magnitude ceiling becomes defensible and this ruling is too small. **If** each lever's boundary sits
somewhere different — which is what floating-point overflow at different widths predicts, and
`FAB_ALPHA`'s boundary between 1e24 and 1e26 is one data point for it — then no universal ceiling
exists, and the upper end is a per-lever measurement arriving one lever at a time, with `domain=`
as the place to record it as it arrives.

---

## Q-CAP-2 (OPEN, for the owner). The fabric is born above the point its own cull settles at, so with the expert arm armed there is NO soft cap the startup refusals accept.

**MEASURED 2026-09-15**, building CAP and FAB against `{"CAP_TARGETS": "experts"}` and reading the
resolved values rather than the lever literals:

    FAB_N0     (founding population)   2048
    FAB_SLOTS  (hard ceiling)          4096
    FAB_PRESSURE                       0.45
    d_operating_population             1844     = pressure x slots
    founding population is 204 ABOVE the settling point

`capacity/api.py::startup_refusals` refuses a soft expert cap **below the live population** (the C30
freeze) and refuses one **above the cull's settling point** (the dead valve). At the shipped FAB
defaults a silent configuration would need `cap >= 2048` and `cap <= 1844` at the same time.
Enumerated over every integer cap from 1 to `FAB_SLOTS`: **zero of 4096 trip neither clause.** So
`CAP_TARGETS=experts` cannot be set at the shipped defaults without some refusal firing.

**THIS IS A STATEMENT ABOUT THE DEFAULTS, NOT ABOUT THE CLAUSES**, and it disproves a sentence the
contract leans on. `startup_refusals`' own docstring says the below-population clause is
"Unreachable on a fresh run; entirely reachable on a resume". That is false at the shipped
`FAB_N0`: the founding population is 2048 on a FRESH run, so any cap at or below the settling point
is below the population before a single window is drawn. The clause was written for the resume case
(523 experts against a gc arm's 160) and reaches a case its author believed it could not.

**THE THREE READINGS, AND NONE IS TAKEN HERE.**

(a) **`FAB_N0` is wrong.** A founding population above the cull's own setpoint means the first
management flushes spend themselves culling experts the run just built. If the intent is for the
population to grow INTO its pressure band, `FAB_N0` belongs at or below 1844. This is the reading
that makes the contract's "unreachable on a fresh run" true again, and it is a FAB default, not a
CAP one -- which is why it is a question and not an edit.

(b) **The below-population clause should not fire on a transient overshoot.** On a fresh run the
cull brings the population down toward 1844, so `cap - population` starts negative and becomes
non-negative on its own; the freeze is transient, not "for the entire run". Under this reading the
clause should compare against the SETTLED population rather than the live one, or fire only on a
resume. The cost is that it stops catching the resume case early, which is the case it exists for.

(c) **Both numbers are right and the pair is simply unrunnable.** `CAP_TARGETS` defaults to "off",
so nothing in the shipped configuration is refused today and the contradiction is only reachable by
an operator who arms the valve. Under this reading the refusal is doing its job: it is telling that
operator that the fabric's own defaults leave the valve no room, which is exactly the dead-valve
state `fab_start`'s levers.py comment spends a paragraph on.

**WHAT WOULD DECIDE IT IS A MEASUREMENT NOBODY HAS RUN**: does the population actually settle at
1844 from a start of 2048, and how many flushes does it take? That is a fabric question, it needs a
run, and until it is answered (a) and (b) are guesses about a mechanism's behaviour rather than
readings of it. Recorded rather than resolved, because guessing here would bake a fabric default
into a capacity refusal on no evidence.

---

## The retirement audit, run 2026-09-15. DID A RETIREMENT LOSE A VALUE? **No — on all four, measured over 72 cells.**

The domain ruling closed four dead read-site refusals by RETIRING them (`2fd3b22`, `901de13`), and
the falsifier it left owed was the obvious one: **every value a retired clause used to refuse must
still be refused by the declaration.** `tests/test_ownership.py::check_o15_domain_agrees_with_read_site`
cannot answer it, and saying why is the point — O15 compares a declared pair against a clause that
**still exists**, and a retired clause is gone from the tree, so the one case the retirement created
is the one case the check that authorised it is blind to.

**METHOD.** The four retired clauses were reconstructed from git rather than from anybody's memory
of them — `git show 2fd3b22 -- src/opt/api.py` and `git show 901de13 -- src/sig/api.py src/tok/api.py`:

    OPT_LR_RESTART_DAMP   `damp > 1.0` and `damp < 0.0`        -> domain (0.0, 1.0)
    OPT_LR_DECAY          `not 0.0 <= decay <= 1.0`            -> domain (0.0, 1.0)
    SIG_WARMUP_MIN_FRAC   `frac < 0.0`                         -> domain (0.0, 1.0)
    TOK_DROPOUT           `not 0.0 <= _drop <= 1.0`            -> domain (0.0, 1.0)

Each clause was then re-run **as a Python predicate** over 18 values spanning both boundaries
(`-1e-320`, `-0.0`, `-0.5`, `-1.0`, `-1e9`, `0.0`, `1e-320`, `0.5`, `1.0`, `0.9999999999999999`,
`1.0000000000000002`, `1.5`, `2.0`, `1e9`, `1e300`, `inf`, `-inf`, `nan`) and compared against what
the live tree does with the same value, one fresh process per cell.

**RESULT: `LOST: []`.** Not one value the old clause refused is admitted today. Both `-0.0` cells
agree in the other direction too, which is the endpoint most likely to drift: `-0.0 < 0.0` is False,
so the shipped bodies accepted it, and `-0.0 == 0.0` so the closed domain accepts it as well.

**WHAT MOVED IS THE OTHER DIRECTION, AND IT IS EIGHT CELLS, NOT A REGRESSION.**

*`OPT_LR_RESTART_DAMP=nan`, one cell.* The old clause was two one-sided comparisons and **every**
comparison against NaN is False, so the shipped body ACCEPTED NaN and handed it to the multiplier.
`REFUSE_NON_FINITE_FLOAT` refuses it now. That is the floor doing exactly the job it was added for,
and the fact that the retired clause missed it is an argument FOR the retirement rather than against.

*`SIG_WARMUP_MIN_FRAC` above 1.0, seven cells.* This is the one that looks like a loss and is not.
The old clause refused only the negative end, so `1.5` was legal. **No behaviour was lost, and this
is measured rather than argued**: the lever's only consumer is the Gate predicate
`int(warmup_min_frac * warmup) < warmup`, and at the shipped `SIG_WARMUP=800` the adaptive stop is
armed at 0.25 and at 0.9999999999999999, and DISARMED at 1.0, 1.0000000000000002, 1.5, 2.0, 1e9 and
1e300 alike. **1.0 is the never-stop-early arm and every value above it is that same arm spelled as
a fraction that cannot be one** — the shape `FAB_PRESSURE` and `MEM_USE_DECAY` both have, and only
one of the two spellings admits what it does. The two non-finite cells are better than benign:
`int(inf * 800)` raises `OverflowError: cannot convert float infinity to integer`, which is the
**precise crash the retired clause's own comment recorded** — the operator got an OverflowError from
inside a `raise` statement instead of the refusal. Refusing `inf` at the declaration repairs it.

**`TOK_DROPOUT` IS NOW CLOSED AND IT WAS ONE OF THE TWO LISTED OPEN.** Its old clause already
refused outside `[0.0, 1.0]`, so the declared pair reproduces it **exactly**: zero lost cells and
zero over-refused cells across all 18. There is nothing left to decide on the RETIRE-OR-DROP fork for
it. `SIG_WARMUP_MIN_FRAC` stays open in form only — the seven cells are enumerated above and every
one is an alias of 1.0 or a crash — so the fork is now a question about SPELLING, not about a
behaviour anybody can still reach.
