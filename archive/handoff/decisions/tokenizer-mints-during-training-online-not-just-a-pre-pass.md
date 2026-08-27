# Tokenizer mints DURING training (online), not just a pre-pass — SETTLED [USER]

**Decision:** Vocabulary grows throughout training (`TOK_ONLINE=1`): model pre-sized to VMAX, stream
re-tokenized as vocab grows, byte-coordinate metrics kept true.
**Why:** user directive — minting is ongoing, not a one-shot pre-pass. Verified: online == frozen at
matched vocab+memory (the earlier regression was undertraining + small vocab, not online-ness).
**Source:** `STATE.md §2` Design decisions; §4 Q2 (resolved).
