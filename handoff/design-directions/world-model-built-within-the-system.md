# A GENERAL world model built within the system [USER direction — core / near-north-star]

**Idea (corrected & sharpened by USER):** the system should build a **GENERAL world model** — a model of EXTERNAL
REALITY, not of its own internal state. Three defining properties:
- **PHYSICS-LIKE:** it learns how the world WORKS and EVOLVES — dynamics, cause→effect, consequences — the way a
  physics engine models how things behave (learned, not hand-coded equations).
- **MULTIMODAL:** it integrates other MODALITIES ("senses" — text now; a mic, a camera later), which enter through the
  LOWEST tokenizer/embedding layer (the sense-integration point USER specified earlier). The world model is of a
  multi-sensory world, not just text.
- **REASONED-OVER:** "complex reasoning" (north star) = reasoning that runs over this world model (imagine consequences,
  plan, verify).
NOT a self-model / not latent-dynamics-of-its-own-hidden-state (an earlier misread). It models the WORLD.

**"Maybe it is all 3" [USER]:** the general world model likely UNIFIES the three mechanisms previously listed, all
turned OUTWARD at the world:
1. **Latent forward dynamics** — predict how the WORLD's latent state evolves (the physics-like core; JEPA-style —
   predict the representation of the future, not raw tokens/pixels).
2. **Structured / relational knowledge** — entities and relations in the world, held in EditableMemory
   (declarative, provenance-tagged, editable/removable).
3. **Generative reconstruction** — decode the latent back to a modality to IMAGINE / VERIFY (reuses the reverse-embedder).

**Architecture sketch (how it sits on what exists):**
- **Shared modality-agnostic LATENT** every sense maps into via the lowest layer = the integration point for new senses.
- **Forward-dynamics model** over that latent = the "physics" (self-supervised: predict future latent from past).
- **Relational memory** grounds the latent in editable facts; **reconstruction** imagines/checks; **reasoning** = rollouts + composition over the dynamics.
- Provenance-without-partition keeps it coherent (mixing) yet editable; active-learning closed-book loop internalizes it into weights.

**Open (the real design questions):**
- The minimal FIRST buildable increment (text-only, but modality-agnostic by construction so senses plug in later).
- Latent objective: JEPA-style latent prediction vs reconstruction vs contrastive — which for v1.
- How reasoning consumes the dynamics (rollout depth, planning).
- How the relational layer is extracted without labels (self-assembly, as domains are).
- Measurement: what says "the world model is correct" (forward-prediction accuracy, consequence tests, cross-modal).
**Source:** user, session 2026-07-23. Foundational — candidate to fold into the north-star statement. Design before build.
