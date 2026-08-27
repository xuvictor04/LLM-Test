# Active learning: self-generated reference → prompt → reproduce closed-book [USER direction]

**Idea:** once the system reaches a competence threshold ("a certain level"), it AUTHORS ITS OWN CURRICULUM. Each item
is a triple: (1) a **reference article** it generates, (2) a **prompt** about that reference, (3) the requirement to
**reproduce the answer with the reference removed from context**. Open-book first, then closed-book. The point is to
move knowledge OUT of retrieval/context and INTO the model's own weights/memory — to internalize, not just look up.

**Why it fits the whole design:**
- It is the missing BRIDGE between the two halves already here: retrieval-grounding keeps knowledge *in memory* (read
  internally, never emitted raw), and this loop is the mechanism that *transfers* that knowledge into the weights —
  reference-conditioned (open book) → reproduce alone (closed book).
- The LEARNING SIGNAL already exists: the surprise on the closed-book attempt (target = the reference-conditioned
  output) is exactly the `1 − p_model(true token)` gate that drives writes/updates today. High surprise = not yet
  internalized = write/update.
- It is CONTEXT / SELF-DISTILLATION: teacher = model+reference, student = model alone. A known, sound technique — worth
  naming so we don't reinvent it.
- VERIFICATION-by-reconstruction is the natural scorer for "did it reproduce faithfully" (reconstruct the closed-book
  output against the reference).
- It serves the north star directly: a system that generates its own training data is autonomous and ever-expanding;
  self-authored curriculum is self-directed learning.
- The "certain level" gate = curriculum ordering — only attempt closed-book once open-book works.

**Open:**
- What is the GROUND-TRUTH target for the closed-book loss — the reference-conditioned output, or the reference itself?
  (If the open-book output is wrong, naive self-distillation would internalize a hallucination — need the reference as
  the anchor.)
- Self-generated references risk a degenerate/self-reinforcing loop (the model trains on its own possibly-wrong prose);
  what keeps generated references grounded (retrieved real passages as the reference source?).
- How is the competence threshold measured, and per-domain or global?
- Does the reproduction update WEIGHTS, MEMORY, or both — and how does that interact with the surprise write-gate?
**Source:** user, session 2026-07-23. Not built (explicit: capture only, continue current work).
