# Phase 10 — scaling data, and two direction corrections; resolving the binding constraints

Built + verified `fetch_data.sh` (~85MB from NLTK-hosted Gutenberg/Brown/Reuters over GitHub, in-allowlist); fixed a
too-aggressive file-size filter silently discarding sources; reached ~85MB (44MB English) ≈ 22× more usable English.

**Two USER corrections:**
1. Retrieval-grounding must NEVER emit raw passages — recall may only occur INTERNALLY, conditioning the model's own
   generation. Fixed immediately.
2. Do NOT port onto an existing pretrained model (Llama/Mistral). **The goal is the full novel model, trained by us.**
   Then: **"Resolve the binding constraints then."**

Resolved both same turn: **`BATCH_W`** (batch the LM step over multiple windows while keeping assembly + memory writes
strictly per-window/sequential — stream order and provenance preserved; caveat: scale `STREAM_LEN` WITH `BATCH_W` or the
model trains LESS), and larger corpora two ways (`fetch_data.sh BIG=1` → ~1GB verified; `fetch_big.py` → HF streaming,
network UNTESTED from the sandbox, including `oasst1` dialogue for turn-taking). **Compute is now the binding constraint:**
a GPT-2-scale budget is weeks of H100 time, not an afternoon.
</content>
