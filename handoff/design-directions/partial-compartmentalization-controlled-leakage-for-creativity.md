# Partial compartmentalization — controlled leakage between compartments, for creativity [USER direction]

**Idea [USER]:** as context is used, a piece of information is often relevant to **several different aspects** at once.
Compartments (domains / experts / meanings / memory) should therefore be **PARTIALLY, not fully, isolated**. Letting
things **slightly MIX is important for CREATIVITY** — full isolation would wall off the cross-connections that new ideas
come from. The degree of isolation is a **dial**, and the target sits in the middle: leaky-on-purpose, not sealed.

## The new angle this adds
The project already tolerates mixing; the USER now makes it a **goal with a reason**. Three shifts:
- **Isolation becomes a tunable design parameter**, not a binary regime pick. "How porous?" is the question, and the
  answer is *some*, deliberately.
- **Leakage is reframed from cost → FEATURE.** Today the docs treat bleed as a downside (e.g. `MEM=1` recall is "richer
  but bleeds across domains"). Here, *slight* bleed is a SOURCE of novelty/creativity, wanted on purpose.
- **Multi-aspect relevance is first-class:** one piece of information legitimately belongs to more than one compartment
  (multi-affiliation), rather than being forced into a single owner.

## Where it connects to what already exists
- **Directly informs Q-regime** (`../open-questions/Q-regime-redundancy-vs-modularity-a-genuine-product-fork.md`). It is
  another argument against either extreme: full REDUNDANCY (`ROUTE_T=1.0`, everything mixes — no compartments to leak
  *between*) and full MODULARITY (`ROUTE_T=0.3`, sharp constituencies — approaches sealed) are both endpoints; the USER
  wants a controlled middle. **Creativity now joins safety, reuse and compliance as a selection criterion on that fork.**
- **Extends `interchangeable-base-with-emergent-subspecialties.md`.** That file argues partial-mixing from SAFETY (redundant
  units survive wrong deletion) and REUSE (shared sub-skills). This adds a THIRD reason — CREATIVITY — and broadens the
  scope from experts to INFORMATION generally (context, memory, meanings), not just the society.
- **Reinforces existing mechanism that already leaks by design:** retrieval is a **global kNN**, domains are provenance
  tags that do NOT partition retrieval, and every measured run has **0 exclusive experts** (soft constituencies, 42–66%
  coverage each). So partial-mixing is already the system's actual behavior — the direction is to *keep and tune* it, not
  to sharpen it away. Consistent with the standing decision "cross-domain composition is OK and EXPECTED — a feature."
- **Couples to polysemy / "Meaning"** (`knowledge-base-editable-polysemy-aware-embedding-plus-retrieval.md`): a surface
  form relevant to several aspects = several meaning-vectors with context selecting among them — a compartmentalization
  question at the embedding layer.

## Tension to surface (do NOT paper over)
The **editability headline pulls the OPPOSITE way.** Surgical deletion-by-provenance is clean precisely because
compartments are *clean* — low collateral means little leakage. **The dial that maximizes creativity (leaky) is the dial
that maximizes deletion collateral.** So "partial isolation for creativity" trades directly against "delete a component
with near-zero blast radius." This is the same family of tension as R21 (consolidation vs editability): the system wants
compartments porous enough to be creative and clean enough to edit. Finding the usable middle IS the design problem.

## Open — mechanism the USER has NOT decided (ASK / flag; do not default)
- **What carries the leakage, and how is it bounded?** Router temperature (an intermediate `ROUTE_T`), soft/overlapping
  affiliations, a "leak budget," retrieval that pulls a few off-domain neighbors on purpose — none chosen.
- **Is the porosity GLOBAL or CONTEXT-DEPENDENT?** Leak more when stuck/exploring (creativity), less when precision or
  clean deletion matters — a mode switch vs a fixed constant. Undecided.
- **Does it apply per LAYER** (tokens/meanings vs domains vs experts vs memory) with different porosity each, or one dial?
- **How to measure "creativity"** so the dial can be tuned at all — otherwise it is untestable. Open.

## Status
Design direction — vision + rationale set by the USER, mechanism open. Informs the Q-regime decision (adds a criterion);
NOT built, no code changed.
**Source:** user, session 2026-07-22.
