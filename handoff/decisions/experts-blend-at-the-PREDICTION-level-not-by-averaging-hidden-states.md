# Experts blend at the PREDICTION level (Σ wᵢ·head(oᵢ)), not by averaging hidden states — SETTLED [fix]

**Decision:** the ensemble combines experts' DECODED predictions (`Σ wᵢ·head(oᵢ)`, via `fab_logits`), never their
averaged hidden states then decoded (`head(Σ wᵢ·oᵢ)`).
**Why:** averaging hidden states produces a representation no individual expert was ever trained to emit; decoding it is
near-noise (measured: degenerate character-salad generation, broken self-consistency check). This was one of the
highest-value corrections in the project — it's what made generation readable at the Garry milestone.
**Source:** context export §6 / Phase 6; `../GLOSSARY.md`; `../history/phase-06-the-fabric-port-and-mixture-vs-society.md`.
