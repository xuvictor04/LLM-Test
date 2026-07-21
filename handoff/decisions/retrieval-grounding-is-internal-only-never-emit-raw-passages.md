# Retrieval grounding is INTERNAL only — never emit raw passages to the user — SETTLED [USER correction]

**Decision:** `GROUND=1` recall silently conditions the model's generation on relevant retrieved source material; the
visible output is ALWAYS the model's own generated language, never a quoted/emitted passage.
**Why:** the user explicitly corrected an earlier version that emitted raw passages — retrieval may only occur internally.
**Source:** context export Phase 10 (correction 1); `prompt.py` `_recall`/`respond`.
