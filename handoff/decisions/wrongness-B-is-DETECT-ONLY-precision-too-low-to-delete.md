# Wrongness (B) = self-consistency, DETECT-ONLY — never deletes — SETTLED [USER]

**Decision:** B flags entries via self-consistency but does NOT delete (`WRONG_SWEEP=0`).
**Why:** the write gate stores SURPRISING tokens and B flags SURPRISING tokens, so genuine-novel and
wrong are conflated — high recall, ~1–2% precision across runs. Deleting at that precision would gut
the store. A (edit/unlearn on command) does not need B.
**Open follow-up:** whether to attempt a corroboration-based B or cut B entirely — see
`../open-questions/Q3-B-direction-attempt-corroboration-or-cut-B-and-ship-A.md`.
**Source:** `STATE.md §2` Design decisions; `CL_TESTBED.md` §B.
