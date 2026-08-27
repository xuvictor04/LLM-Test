# The end goal is a FULL NOVEL MODEL trained from scratch — not built on a pretrained base — SETTLED [USER]

**Decision:** the objective is a full, novel model trained by us from scratch, capable of intelligible language and
eventually real conversation. Do NOT port the memory/editing/domain machinery onto an existing pretrained model
(Llama/Mistral/etc.) — the user rejected that path directly.
**Consequence:** the two real constraints to reach it are TRAINING THROUGHPUT (addressed by `BATCH_W`) and DATA VOLUME
(addressed by `fetch_data.sh`/`fetch_big.py`); compute is now the binding one — a GPT-2-scale budget is weeks of H100 time.
**Source:** context export Phase 10 (correction 2), §1; `../STATE.md §1`.
