# Q3 — B direction: attempt corroboration-based detection, or cut B and ship A? — OPEN, needs USER decision

**Question:** autonomous wrong-detection (B) is broken in the realistic regime — ~1% precision in EVERY run, because
self-consistency conflates surprising with wrong (the write gate stores surprising tokens; B flags surprising tokens).
- (a) Attempt a fundamentally different signal — **corroboration / contradiction** (does an entry disagree with its
  nearest neighbors in the store, given enough neighbor evidence?). Hard, speculative, may still fail.
- (b) **Cut** autonomous B and ship clean-unlearning-on-command (A already delivers and does not need B).
**Prior-context recommendation (not decided on your behalf):** **(b) cut B** — corroboration-B is a real research detour
from where the project's attention now is (language quality).
**Who decides:** USER.
**Source:** `../../STATE.md §4 Q3`; `CL_TESTBED.md` §B.
