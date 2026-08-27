# Surprise is a mechanic for ONGOING LEARNING — not a wrongness / truth signal [USER clarification]

**Clarification:** surprise (`1 − p_model(true token)`) exists to **facilitate ongoing learning** — it flags where the
model is wrong-footed so the system writes / adapts / discovers there (memory writes, sense discovery, expert birth). It
is the engine of continual learning.

**What it is NOT:** a truth or wrongness signal. Casting surprise as wrong-detection (B) is a category error — it is
exactly why B sits at ~1% precision (genuine-novel and wrong both look surprising). Do NOT reuse surprise as a verifier.

**Where verification belongs instead:** a SEPARATE mechanism — reverse-embedding reconstruction (see
`../design-directions/reverse-embedders-for-thought-verification-and-training.md`), not surprise.

**Consequence:** reinforces the direction to CUT autonomous B (Q3); keeps LEARNING (surprise-driven) and VERIFICATION
(reconstruction-driven) as separate concerns.
**Source:** user, session 2026-07-21.
</content>
