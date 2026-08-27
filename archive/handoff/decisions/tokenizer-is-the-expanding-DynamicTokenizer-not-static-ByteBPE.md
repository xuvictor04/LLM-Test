# Tokenizer = the expanding DynamicTokenizer, not the static ByteBPE — SETTLED [USER]

**Decision:** Use the emergent `DynamicTokenizer` (online mint-on-repetition, byte-grounded/lossless),
not the static `ByteBPE`. `TOKENIZER=1` in the full run.
**Why:** word-pieces instead of character salad; cut ~0.5 bits/byte and made generation readable;
cleaner domain separation.
**Source:** `STATE.md §2` Design decisions; `tokenizer.py`.
