# Phase 4 — the online tokenizer: pre-pass → concurrent, a real collapse, and the byte-stream fix

Built `TOK_ONLINE=1`: model pre-sized to max vocab, tokenizer mints live as it reads, token stream periodically
re-derived from bytes as vocab grows.

**First full run looked catastrophic:** domain assembly collapsed from hundreds to ONE, purity 0.33, editing LEAKED
(unlearning one process damaged all others — the exact failure the thesis exists to avoid). First hypothesis
(expert-selection churn) was tested and REFUTED. Real root cause: the domain **signature encoder was reading the TOKEN
stream**, which churns every time the vocab re-derives it — moving the encoder's input out from under it. **Fix: the
signature encoder always reads the BYTE stream** (a domain is a byte-level property; the LM keeps tokens for efficiency).
Restored 12–24 live domains, purity ~0.87–0.92, local editing.

The user pushed back on an earlier "online minting hurts" claim: **"I refuse to compromise on the new minting."**
Controlled experiments: undertraining CONFIRMED (more steps monotonically better); online minting EXONERATED (== frozen at
matched vocab+memory); the real deltas were smaller vocab reached online + Transformer underperforming GRU at batch-1.
**GRU became the standing default.**
</content>
