# fab_logits() is the SINGLE hidden→logits path; and a diagnostic must never crash a run — SETTLED [invariants]

**Two structural invariants, both hard-won:**
1. **`fab_logits()` is the only path from hidden state to output logits** — training, evaluation, the wrongness check,
   and generation all go through it. A new consumer of the model's output MUST use it, or it silently runs a
   fabric-trained checkpoint through the wrong forward pass (this bug hit ≥3×: garbled generation; B recall silently
   dropping to ~19–25%; and again after the mixture→society rewrite).
2. **A measurement must never be able to destroy a training run** — late-run diagnostics (e.g. the affiliation report,
   which once crashed a full GPU run on a tensor-shape mismatch) are wrapped in try/except. Apply this to any new late-run diagnostic.
**Source:** context export §10, Phase 7.
