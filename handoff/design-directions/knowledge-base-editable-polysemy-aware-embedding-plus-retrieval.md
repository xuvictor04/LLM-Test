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

**Sense discovery (USER direction, 2026-07-21):** senses live at the **LOWEST tokenizer layer** (not a separate higher
layer). A new sense is **DISCOVERED when an UNKNOWN or UNUSUAL input is received** — novelty/surprise-triggered — and this
happens **BEFORE reconciliation and understanding** (a staged pipeline: unusual input → provisional sense at the
tokenizer layer → reconcile against known senses → integrate/understand). Reuses existing signals: the tokenizer already
mints on REPETITION; sense discovery adds branching on SURPRISE (the same `1 − p_model(true token)` signal the write gate uses).
**How I read the stages (confirm):** *reconciliation* = align/merge the provisional new sense with existing senses (is
this genuinely new, or a variant of a known one?); *understanding* = integrate the reconciled sense so it can be used and edited.

**Still open:** how many vectors per surface form and how that's bounded; how a sense-edit propagates to memory entries
written under the old sense; whether SENSES and DOMAINS are the same emergent mechanism at different granularities.

**Status:** design direction, not specified or built.
**Source:** user, session 2026-07-21.
</content>
