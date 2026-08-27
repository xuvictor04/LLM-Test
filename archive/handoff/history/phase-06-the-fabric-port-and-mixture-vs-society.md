# Phase 6 — the user's real fabric, ported; mixture→society; the Garry milestone

Reading `legacy/system.py` revealed a more capable mechanism: routing as a SOFT distribution over operators, a learned
TRANSITION MATRIX (mass flows node→node across steps), an absorbing HALT operator with a ponder cost (adaptive depth),
and growth on LOSS PLATEAU with pruning OFF by default (its own docs warned fixed-threshold pruning causes a grow/prune
sawtooth — exactly what the flat bank reproduced). Ported as `FABRIC=1`; it beat the flat bank.

But the initial port was a **chained mixture** (each step's blended hidden fed the next), entangling every expert's
gradient — degrading the base model as the fabric absorbed function, hurting generation. The user reframed: experts as
independent agents blending OUTPUTS at a router, nothing frozen, domains as collections of experts. Rebuilt as a
**society**: independent experts from the same shared hidden state, and — the key fix, found only after a bad run + the
user's rejection — **blend at the PREDICTION level** (`Σ wᵢ·head(oᵢ)`), NOT by averaging hidden states.

Same GPU run once fixed: expert-deletion collateral **−0.0009**, end-to-end **1.967 b/B** (project best), B recall 96%,
and **generation genuinely readable**. Frozen as the reference checkpoint, **"Garry"**. The independence test (delete the
busiest expert's weights, measure damage on every process) produced the headline number.
</content>
