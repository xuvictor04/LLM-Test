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
