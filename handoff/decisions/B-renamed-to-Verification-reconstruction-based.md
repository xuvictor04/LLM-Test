# B (wrongness) is RENAMED to VERIFICATION — reconstruction-based [USER; name CONFIRMED]

**Decision (USER):** the middle of the C → Verification → A loop is renamed from "B / detect wrong info" to
**VERIFICATION**, and reframed. ("Verification sounds better than V.")

**What Verification is:** verification by RECONSTRUCTION — take the internal representation, run it BACKWARD through a
reverse embedder (the **Reconstructor**) to regenerate the input/expectation, and measure the error. Low error =
understood; high error = not understood. NOT wrongness-detection, NOT surprise-based.

**Why the reframe:** the old B tried to read TRUTH off SURPRISE — a category error (surprise drives LEARNING, not truth;
see `surprise-is-a-learning-driver-not-a-wrongness-or-truth-signal.md`). That conflation is why B sat at ~1% precision for
the entire project. Verification replaces the signal with a real one, decoupled from surprise (see
`../design-directions/reverse-embedders-for-thought-verification-and-training.md`).

**Scope of the rename:** applied going-forward in the LIVING docs. HISTORICAL / FROZEN records keep "B" (`garry/`,
`handoff/history/`, the STATE changelog). The old CODE names (`is_wrong` / `selfcheck` / `sweep_wrong`) persist until the build replaces them.

**Supersedes:** the old open question "corroboration-B vs cut-B" (Q3) — the answer is NEITHER: replace with Verification (reconstruction).
**Source:** user, session 2026-07-21 (name CONFIRMED).
</content>
