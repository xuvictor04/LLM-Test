# Active learning — the system generates its own closed-book curriculum [USER direction]

**Idea [USER]:** once the system reaches **a certain level of competence**, it stops only reading the stream passively and
starts **authoring its own training items**. Each item is three parts:
1. a **reference article** (source material — the "open book"),
2. a **prompt** over that reference,
3. **reproduce the output WITHOUT the reference in context** (the "closed book").

The system is graded on whether it can regenerate the target once the reference is removed. This is *active* learning:
the model drives its own curriculum instead of waiting for the next byte of stream.

## Why this fits the architecture
- **It is the REVERSE / reconstruction path at the passage/task level.** "Reproduce the output without the reference" =
  "can I regenerate this from my own understanding?" — exactly the Verification signal
  (`reverse-embedders-for-thought-verification-and-training.md`), scaled up from a token to a whole passage/task.
- **It is the training-time twin of internal-only grounding.** Recall already conditions generation on source passages
  but never emits them (`../decisions/retrieval-grounding-is-internal-only-never-emit-raw-passages.md`). Active learning
  alternates a **grounded (open-book)** pass and an **un-grounded (closed-book)** pass over the same item and trains to
  CLOSE THE GAP — i.e. it drives knowledge from the editable memory / retrieval store INTO the model's own weights.
- **It lands in the surprise × reconstruction 2×2** (`learning-signal-classification-surprise-and-reconstruction.md`):
  closed-book FAILS while open-book SUCCEEDS = the "memorized/retrieved but not grasped → LEARN deeper" cell. Active
  learning is a concrete way to detect and act on that cell instead of just observing it.
- **Self-authored curriculum = the autonomous ethos**, kin to experts self-authoring as tool-calls on repetition
  (`experts-can-be-tool-calls-or-scripts-crystallized-on-repetition.md`). The system generates its own supervision from
  one unlabeled stream — no new labels introduced, consistent with C→Verification→A.
- Serves the NORTH STAR's "LEARNS and does complex REASONING" clause: closed-book reproduction is a consolidation +
  reasoning drill, not just next-token prediction.

## Open — mechanism the USER has NOT yet decided (ASK / flag; do not default)
- **The GATE — what is "a certain level"?** A b/B threshold? per-domain competence? silhouette genuineness? a global
  metric? This is the trigger that switches the system from passive stream-reading into active self-testing. Undecided.
- **What does closed-book reproduction TRAIN — weights, memory, or both?** The natural goal is weight-*consolidation*
  (move knowledge out of the editable store so it is held natively). **TENSION to surface:** the headline result and the
  SACRED growability/editability invariant rest on knowledge being deletable-by-provenance (memory rows, independent
  experts) precisely BECAUSE it is not baked into entangled weights. Consolidating into base weights could forfeit clean
  deletion. Candidate reconciliation: consolidate into an EXPERT (still an independent, deletable unit), not the base.
- **How is reproduction SCORED?** Reconstruction error via the reverse embedder (reuses Verification's metric — natural
  fit), exact-match, or self-verification. Reconstruction is the obvious first choice.
- **Where does the "reference article" come from?** The USER said the system *generates* it. Generating coherent
  references needs generation quality we do not have yet (semi-coherent at current scale, `../../STATE.md §7`). Likely
  bootstrap: draw references from real corpus passages / memory first; model-*generated* references later, once fluency
  supports it. Flagged as a staging decision, not a settled one.

## Status
Design direction — vision set by the USER, mechanism open. NOT built, no code changed. Belongs after the first
green GPU-scale run (fluency is the precondition for a self-generated curriculum to be worth anything).
**Source:** user, session 2026-07-22.
