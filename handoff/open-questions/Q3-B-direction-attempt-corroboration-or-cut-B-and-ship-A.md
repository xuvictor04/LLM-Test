# Q3 — B direction — SUPERSEDED (2026-07-21): B is renamed V and reframed (reconstruction), not corroboration-vs-cut

> RESOLUTION: the old fork (attempt corroboration-B vs cut B) is moot. B is RENAMED **V (Verify)** and reframed as
> reconstruction-based verification decoupled from surprise — see
> `../decisions/B-renamed-to-V-verify-reconstruction-based-not-wrongness.md`. What remains is a BUILD, not a decision.
> Original question kept below as the record.

---


**Question:** autonomous wrong-detection (B) is broken in the realistic regime — ~1% precision in EVERY run, because
self-consistency conflates surprising with wrong (the write gate stores surprising tokens; B flags surprising tokens).
- (a) Attempt a fundamentally different signal — **corroboration / contradiction** (does an entry disagree with its
  nearest neighbors in the store, given enough neighbor evidence?). Hard, speculative, may still fail.
- (b) **Cut** autonomous B and ship clean-unlearning-on-command (A already delivers and does not need B).
**Prior-context recommendation (not decided on your behalf):** **(b) cut B** — corroboration-B is a real research detour
from where the project's attention now is (language quality).
**Who decides:** USER.
**Source:** `../../STATE.md §4 Q3`; `CL_TESTBED.md` §B.
