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
