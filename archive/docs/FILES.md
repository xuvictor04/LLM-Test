# FILES.md — file-by-file map of the repository

A documentation manifest for every **active** file, plus the frozen `garry/` snapshot, the
`legacy/` archive, and the `data/` corpora. Written 2026-07-21 from a direct read of the code
(not from the other docs), so where this disagrees with an older doc, trust this one for
*what the code is* — but see `docs/HANDOFF.md` §Reconciliation for measured-number provenance.

> Terminology: a **domain** is a self-assigned cluster the assembler opens from the unlabeled
> stream (there are hundreds; over-segmentation is harmless — see `CL_TESTBED.md`). An **expert**
> is an independent agent in the Fabric/society blended at the prediction level. **Provenance** =
> the domain id tagged onto each memory entry, which is what makes clean unlearning (A) possible.

---

## Active code — repository root

| file | lines | what it is |
|---|---|---|
| `self_organize.py` | ~1094 | **The product loop** (`main()`). Reads one unlabeled byte/token stream that secretly switches between latent processes → self-assembles growing "domains" → writes surprise-gated, provenance-tagged entries to `EditableMemory` → measures assembly, wrong-detection (B, detect-only), performance, cross-segment composition, generation, and clean unlearning (A). |
| `cl_bench.py` | ~300 | **The mechanics testbed.** One controlled pass to quantify the thesis: forgetting arms (weights / +replay / +memory[frozen] / +memory[model-key]), editability (memory-delete vs weights gradient-ascent unlearn: cost + collateral), and wrongness (inject corruption, flag via self-consistency). `ESTIMATE=1` prints a wall-clock predictor first. |
| `memory.py` | ~187 | **`EditableMemory`** — the standalone torch-only external store. Surprise-gated `write` (optional self-calibrating adaptive gate), kNN `read` → soft token distribution, `rekey` (drift fix), `delete`/`delete_src`/`reassign_src`/`sweep_wrong` (the editability = A), `is_wrong`/`set_selfcon` (self-consistency = B), usage/recency eviction, `stats`. Root version also tracks per-entry source `pos` for grounded retrieval. |
| `prompt.py` | ~257 | **Interactive / one-shot inference** on a saved checkpoint. Loads `ckpt.pt` (model, optional Fabric + SigEncoder, optional tokenizer, optional memory + `source.bin`), routes a typed message by its signature, and continues it. Optional memory blending (`MEM=1`) and retrieval **grounding** (`GROUND=1`, conditions on source passages never shown). |
| `tokenizer.py` | ~303 | **Two byte-grounded (lossless) tokenizers.** `ByteBPE` (static, train-once → JSON) and the emergent `DynamicTokenizer` the loop uses: online **mint-on-repetition** vocab growth (`maybe_grow`), greedy longest-match `segment`, `retire_stale` un-merge, thread-safe. `blen`/`bytes_per_id` keep metrics as true bits/**byte**. |
| `fetch_big.py` | — | Streams a GB-sized slice of a Hugging Face dataset (fineweb-edu / c4 / openwebtext / wikipedia / oasst1 / pile presets, or any HF id) into the `DATA_DIR/train/<domain>/` shard layout. `argparse` CLI. Needs `pip install datasets` + network. |
| `fetch_data.sh` | — | Builds a larger (~35–45 MB) local corpus into `data_big/train/{eng,py,num,c}/` from NLTK Gutenberg/Brown/Reuters, CPython `Lib/*.py` + `Objects|Python|Modules/*.c`, and synthesized numeric tables. `BIG=1` adds hundreds of MB of Gutenberg. |
| `run_full_unfrozen.sh` | — | **The whole system in one command.** All features on: online expanding tokenizer + Fabric society + adaptive gate + unfrozen model key + self-consistency B (detect-only) + silhouette + composition + performance + generation + mechanics. Writes `~/<RUN_NAME>.txt` and a checkpoint at `runs/<RUN_NAME>/`. **Requires CUDA** (hard-exits otherwise). See §Run config below for knobs. |
| `run_cl_test.sh` | — | H100 suite: estimate → `cl_bench` scale-test → three `self_organize` variants (3a learned-sig + unfrozen model key; 3b learned-sig + frozen-key baseline; 3c bigram frozen baseline). Writes `~/cl_results.txt`. |
| `requirements.txt` | — | `torch>=2.1`, `numpy>=1.21`. That's all. |
| `README.md` | — | Setup → run → message-the-model → the pieces → honest status. |
| `CL_TESTBED.md` | — | What each part does, current findings, and the full knob list. The conceptual reference. |
| `STATE.md` | — | The living project ledger + binding assistant protocol. See §Reconciliation in HANDOFF for its stale sections. |

### Key internal components (all in `self_organize.py`)
- **`MiniLM` / `TinyTransformer`** — the base LM (GRU by default, `MODEL=gru`; decoder-only Transformer via `MODEL=transformer` for the H100).
- **`SigEncoder`** — a small encoder trained **online + self-supervised** (InfoNCE) that emits a domain *signature*; signature shift = a domain boundary. Separates eng-vs-c that byte statistics cannot.
- **`DomainAssembler`** — opens new / merges redundant / culls stale domains with stable ids; memory follows by provenance (reassign/delete).
- **`Fabric` / `FabricNode`** — the **society**: a router over independent zero-init experts blended at the *prediction* level (`Σ wᵢ·head(oᵢ)`, not by averaging hidden states), with a node→node transition matrix, a HALT/ponder cost, and plateau-triggered growth. This is what makes expert deletion clean.
- **`ExpertBank` / `ExpertRouter`** — an *alternate* low-rank-adapter expert population (create/replicate/merge/cull). **OFF by default** (`EXPERTS=0`); the default society path is the Fabric.
- **`PlateauGrowth`** — the shared "grow on loss plateau" controller.

---

## `garry/` — the frozen T33 milestone (do NOT edit)

`garry/` is a self-contained, independently runnable snapshot of the **T33** state — the first version
where the whole architecture worked at once and expert-deletion collateral hit **−0.0009** with
end-to-end **1.967** b/B. It reads shared corpora via `DATA_DIR=../data` and namespaces its outputs
(`~/garry.txt`, `runs/garry/`), so it never collides with development runs. Full config + measured
results + honest limitations live in `garry/GARRY.md`.

**`garry/` is NOT a byte-identical copy of root — it is root's ancestor.** Root = garry T33 **plus**
a later retrieval-grounding / source-passage feature set. Per-file:

| file | garry vs root |
|---|---|
| `cl_bench.py`, `tokenizer.py`, `requirements.txt`, `run_cl_test.sh` | **identical** |
| `memory.py` | root **added** per-entry source-`pos` tracking (grounded retrieval); garry lacks it (~7 lines) |
| `run_full_unfrozen.sh` | garry pins `DATA_DIR=../data` and `RUN=garry`; root uses `RUN=full`, no DATA_DIR export (~4 lines) |
| `prompt.py` | root added retrieval **grounding** (`_recall`, `GROUND`, `source.bin`); garry is pre-grounding (~52 lines) |
| `self_organize.py` | root added the `pos`/source-passage plumbing, `source.bin` checkpoint export, an affiliation diagnostic (~164 lines) |

---

## `legacy/` — archived, unused (~55 files)

The earlier **Barry/Greg language-model architecture** and its harness (`control.py`, `barry.py`,
`continual.py`, `mp_tokenizer.py`, the greg/novelty tests, old sweeps and data utils). Kept for
reference, **not** imported by any active file. Do not treat anything here as current.

---

## `data/` — corpora

| tree | contents | read by |
|---|---|---|
| `data/train/` | **the active training corpora**, 4 domains: `eng` (~3.35 MB, 8 files), `py` (~1.11 MB), `num` (~1.42 MB), `c` (~1.20 MB, CPython `*object.c` + sds) | active `self_organize.py` / `cl_bench.py` — **this tree only** |
| `data/continual/` | 4 arriving-domain phases: `01_rust`, `02_sawyer`, `03_dracula`, `04_num2` | **only** `legacy/` code |
| `data/ood/` | held-out: `code_OOD/rust.txt`, `eng_OOD/sherlock.txt` | **only** `legacy/` code |

> Note: `data/continual/` and `data/ood/` are referenced only by legacy code. The active phased-stream
> test (`PHASED=1`) constructs its non-stationary stream from `data/train/`, not from `data/continual/`.

---

## Run config — root `run_full_unfrozen.sh` (defaults, all `${VAR:-…}` overridable)

- **Naming:** `RUN_NAME=full` → log `~/full.txt`, checkpoint `runs/full/`, tokenizer cache.
- **Part A (cl_bench):** `D_MODEL=256 STEPS_PER_DOMAIN=2000 SEQ=256 BATCH=64`.
- **Part B (self_organize) width:** `D_MODEL_B=512`.
- **Shared:** `MEM_CAP=300000 DOMAINS=eng,py,num,c STREAM_LEN=6000000`.
- **Tokenizer:** `TOKENIZER=1 TOK_ONLINE=1 VMAX=8192 SEED_VOCAB=1024 MIN_PAIR=80 MAX_TOK=16 GROW_PASSES=10 GROW_EVERY=40 GROW_BURST=10 RETOK_EVERY=3000 TOK_GROW_CAP=1500000`.
- **Write gate:** `WRITE_ADAPTIVE=1 WRITE_TARGET=0.4`.
- **Model:** `MODEL=gru HEADS=8 MAXLEN=512 LAYERS=1` (4 for transformer).
- **Fabric (society, ON):** `FABRIC=1 FAB_N0=3 FAB_NMAX=6 FAB_STEPS=3 FAB_DK=32 FAB_ALPHA=0.5 FAB_PLATEAU=0.002 FAB_COOLDOWN=1500 FAB_WARMUP=2000 PONDER=0.01`.
- **Experts (adapter population, OFF):** `EXPERTS=0` (+ many `EXPERT_*` defaults).
- **Hardcoded in the Part-B call:** `SIG_MODE=learned SIG_D=64 ENC_WARMUP=30000 WIN=96 KEY_SRC=model REKEY_EVERY=300 EVAL_N=128 WRONG_INJECT=8 WRONG_SWEEP=0 SAVE_CKPT`.
</content>
</invoke>
