# Wrongness (B) = self-consistency, DETECT-ONLY — never deletes — SETTLED [USER]

> RENAMED (2026-07-21): "B / wrongness" is retired in favor of **Verification** — reconstruction-based, decoupled from
> surprise. This file documents the OLD, broken surprise-based approach as the record + the root-cause that motivated V.
> See `B-renamed-to-Verification-reconstruction-based.md`.


**Decision:** B flags entries via self-consistency but does NOT delete (`WRONG_SWEEP=0`).
**Why:** the write gate stores SURPRISING tokens and B flags SURPRISING tokens, so genuine-novel and
wrong are conflated — high recall, ~1–2% precision across runs. Deleting at that precision would gut
the store. A (edit/unlearn on command) does not need B.
**Open follow-up:** whether to attempt a corroboration-based B or cut B entirely — see
`../open-questions/Q3-B-direction-attempt-corroboration-or-cut-B-and-ship-A.md`.
**Root-cause direction:** surprise is a LEARNING driver, not a truth signal
(`surprise-is-a-learning-driver-not-a-wrongness-or-truth-signal.md`); verification should come from reverse-embedding
RECONSTRUCTION, not surprise (`../design-directions/reverse-embedders-for-thought-verification-and-training.md`).
**Source:** `STATE.md §2` Design decisions; `CL_TESTBED.md` §B.
