# A world model built WITHIN the system [USER direction — core, previously under-expressed]

**Idea:** the system should build an internal WORLD MODEL — not just predict the next token, but hold a structured,
updatable internal representation of how things work, that REASONING can run over (predict consequences, plan, verify).
The user flags this as something wanted from early on but not fully expressed until now; treat it as near-north-star.

**Why it fits the whole design (much of the scaffolding is already pointed at this):**
- The predictive LM is already a PROTO world model — it models "what comes next" in its data-world. The goal is to make
  that model richer and reasoned-over, not just sampled from.
- The EditableMemory + provenance is the DECLARATIVE half of a world model — facts/knowledge that stay updatable and
  removable. A world model that can be EDITED (unlearn a wrong fact) is exactly the editable-knowledge thesis.
- Reverse embedders / reconstruction (Verification) are a GENERATIVE-and-checking internal model — the system
  regenerating/among-verifying its own representations is world-model machinery.
- The active-learning closed-book loop is HOW the world model gets internalized into weights (reference → reproduce
  without it) rather than living only in retrieval.
- "Complex REASONING" (north star) is precisely reasoning OVER a world model. Multimodality ("senses") feeds the world
  model additional modalities so the model is of a richer world, not just text.
- Partial compartmentalization keeps the world model coherent (mixing) yet editable (provenance) — the same tension.

**Open (the real design questions):**
- What KIND of world model: implicit (the LM's latent state), a learned latent-dynamics model (predict future
  latent states / consequences, à la model-based RL), or a structured/relational store? Likely a blend.
- How does reasoning RUN over it — rollouts/simulation of consequences, or retrieval+composition, or both?
- How does it stay UPDATABLE and consistent as new experience arrives (ties directly to EditableMemory + editing-by-provenance)?
- Is the world model a SEPARATE module, or an emergent property of experts + memory + prediction? (Design bias so far:
  emergent, not a bolted-on module — but this needs deciding.)
- How is "the world model is correct/coherent" measured?
**Source:** user, session 2026-07-23. Not built (capture). Elevate toward the north-star statement if the user confirms priority.
