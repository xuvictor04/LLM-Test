# The domain signature encoder reads the BYTE stream, never the token stream — SETTLED [fix]

**Decision:** the contrastive signature encoder (part C) always reads raw BYTES; the LM keeps using tokens for efficiency.
**Why:** a domain is fundamentally a byte-level property. When the encoder read the TOKEN stream, every online re-derivation
of that stream (as the vocab grew) moved the encoder's input out from under it — collapsing domain assembly to a single
domain, purity 0.33, and making editing LEAK across processes. Reading bytes restored stability (12–24 live domains, purity ~0.87–0.92).
**Source:** context export Phase 4; `../history/phase-04-online-tokenizer-collapse-and-the-byte-stream-fix.md`.
