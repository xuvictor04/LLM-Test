# The unifying primitive: subtokenize → embed → match, at every layer [HYPOTHESIS, user-reinforced]

**The recurring theme across every direction:** "much of the ideas involve some sort of SUBTOKENIZATION, to find the
right target" [USER]. One primitive appears at every granularity:

> **SUBTOKENIZE** (break input into sub-units) → **EMBED** into a signature space → **MATCH** by similarity (nearest
> existing unit) → if nothing matches, **DISCOVER** a new unit (surprise / novelty-gated) → **CRYSTALLIZE** it when it
> recurs (repetition-gated).

**Applied at each layer:**
- bytes → **tokens** — mint on repetition. *(already built)*
- tokens → **senses** — branch on unknown/unusual input, at the lowest tokenizer layer. *(direction)*
- stream windows → **domains** — assemble / merge / cull in signature space. *(already built)*
- sub-tasks → **experts / sub-skills** — route by embedding-similarity; born when a recurring sub-pattern is handled poorly. *(direction)*
- recurring procedures → **tool-experts / scripts** — crystallize on repetition, like tokens. *(direction)*

**Why it matters:** if senses, domains, experts, and tools are ONE mechanism at different granularities, the architecture
is far SMALLER than it looks — a single subtokenize-embed-match-discover-crystallize primitive, reused — which is exactly
the "much smaller than conventional models" north star (`../NORTH_STAR.md`). **This is the most promising thread in the whole design.**

**The make-or-break sub-problem:** the EMBEDDING SPACE. Matching only reuses a unit if "similar" means the right thing at
each layer — and for experts/sub-skills that means FUNCTIONAL similarity, not just CONTENT similarity (see
`routing-is-embedding-plus-similarity-for-reuse-and-transfer.md`). Solve the embedding space and the rest composes; don't, and it fragments.

**Reverse path:** the same embedding space also runs BACKWARD — reverse embedders decode from it for THOUGHT, VERIFICATION
(reconstruction, not surprise), and TRAINING. Forward = learn (surprise-gated); reverse = think/verify (reconstruction-gated).
See `reverse-embedders-for-thought-verification-and-training.md`.

**Status:** HYPOTHESIS to test, not a decision. The cheapest first probe: does one clustering/discovery mechanism, retargeted, serve two layers at once?
**Source:** user, sessions 2026-07-21 (reinforced across several turns).
</content>
