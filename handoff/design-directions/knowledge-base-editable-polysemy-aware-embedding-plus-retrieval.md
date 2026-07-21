# Knowledge base = editable memory + built-in retrieval + a polysemy-aware embedding system [USER direction]

**What the user wants the knowledge base to be** — a combination of:
1. the CURRENT `EditableMemory` (provenance-tagged, surgically deletable), plus
2. BUILT-IN RETRIEVAL, plus
3. a "complex tokenizer embedding system" that is:
   - **EDITABLE** — you can correct / update an entry, and
   - **POLYSEMY-AWARE** — when a token / concept has MULTIPLE MEANINGS it has multiple VECTORS, and the system KNOWS
     WHICH VECTOR applies (sense disambiguation), rather than one blurred vector per surface form.

**How I read it (CONFIRM / correct):** disambiguation is by CONTEXT at encode/retrieval time (pick the right sense-vector
for the surrounding context); "editing" means correct / update ONE sense without disturbing the others.

**Where it connects to what already exists:** the tokenizer already mints byte-grounded tokens online; memory already
keys by the model's representation, tags provenance, does global kNN retrieval, and records per-entry source `pos`. A
sense-vectored, editable embedding layer would sit around these — multiple keys per surface form, editable per sense,
retrieval selecting the sense that fits the context.

**Open sub-questions (undecided):** how senses are discovered (emergent, like domains? on collision?); how many vectors
per surface form and how that's bounded; how a sense-edit propagates to memory entries written under the old sense.

**Status:** design direction, not specified or built.
**Source:** user, session 2026-07-21.
</content>
