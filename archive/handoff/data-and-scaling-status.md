# Data and scaling status

**Corpora**
- Bundled/default: ~5.7MB useful (eng/py/num/c), ~3.7MB effectively seen — the ceiling for most of the project's history.
- `fetch_data.sh` (default): ~85MB (44MB English), NLTK-derived + CPython source, over GitHub — verified in-sandbox, safe and fast.
- `fetch_data.sh BIG=1`: adds large GitHub-hosted Gutenberg mirrors → ~1GB, still in-allowlist (a 101MB single source was actually downloaded + inspected as a check).
- `fetch_big.py`: streams slices (never the whole set) from FineWeb-Edu / C4 / OpenWebText / Wikipedia / OpenAssistant(oasst1, dialogue) / The Pile via HuggingFace `datasets` streaming. **NOT exercisable from the sandbox** (HF outside the allowlist) — only non-network paths verified with a stub; the USER must run the real download and report errors.

**Where the big data lives (provenance — so it's not "lost" next session)**
- Training data is STREAMED/FETCHED on demand and **NEVER committed to git** (only the ~7MB bundled `data/train/` is in the repo).
- The few-TB public sources (FineWeb-Edu / C4 / The Pile / …) live on HuggingFace — always upstream, re-pullable; you only ever keep local SLICES.
- Slices land on the DISK of the machine that ran the pull, under `--out`/`DATA_DIR` (e.g. `data_big/train/<domain>/`). A
  fresh clone or a new/ephemeral environment will NOT have them — check `du -sh data_big` on the box, or re-pull.
- Example (a ~20GB slice done in a prior context): `python3 fetch_big.py --dataset fineweb-edu --gb 20 --out data_big`. Point a run at it with `DATA_DIR=data_big`.

**Throughput**
- `BATCH_W` batches the LM's forward/backward over multiple windows while keeping domain assembly + memory writes strictly per-window/sequential (stream order + provenance preserved). **Caveat: `STREAM_LEN` must scale WITH `BATCH_W`** or the model sees fewer optimizer steps and trains LESS.

**The honest scale gap (stated to the user)**
- To GPT-2-small-level coherence: ~5× params and ~325× tokens beyond the post-Phase-10 model (and GPT-2-small still can't converse).
- To real conversation (Llama-2-7B-chat class): ~284× params, ~65,000× tokens, PLUS dialogue-structured data and instruction-tuning + RLHF — none of which exists anywhere in this project yet.
- This is not a reason to stop; it is the shape of the remaining distance, so the next phase is scoped honestly.

**Source:** context export §10, §12; `../STATE.md §7`.
</content>
