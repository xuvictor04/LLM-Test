# Overarching Cognitive System — test & training package

A self-contained byte-level system that composes a trainable deep transformer base with a
gist-routed mixture of embedders, a growable/self-halting/prunable router fabric (with re-embed
and re-encode operators), an adaptive-tokenizer **novelty signal**, and an episodic **one-shot
memory**. The routers decide whether to re-encode, and they are recurrent (each step's control is
fed back into the next routing decision).

**What this architecture showed at small scale** (the thing to reproduce/stress at larger scale):
it *decouples in-distribution fit from out-of-distribution degradation*. Memory carries familiar
inputs via recall, so the base is spared from over-memorizing — in-distribution held loss drops
**without** unseen-source (OOD) loss getting worse, which is the failure mode a plain bigger model
hits. The modular machinery earns its keep not by lowering raw cross-entropy but by this decoupling.

---

## 1. Install
```
pip install -r requirements.txt        # torch + numpy
```
GPU is auto-detected (CUDA, else Apple MPS, else CPU). Force it with `DEVICE=cuda` etc.

## 2. Get the data (once)
```
python get_data.py
```
Downloads public-domain prose + open-source code into `data/train/<domain>/` and held-out **entire
sources** into `data/ood/<name>/`, and generates the numeric domain. Re-running is safe (skips
existing files). **To scale the corpus, just drop more `.txt` files into any `data/train/<domain>/`
folder** — they're concatenated automatically. Domains whose name starts with `eng` are treated as
prose (Gutenberg headers stripped).

## 3. Train
```
python train.py
```
Auto-resumes if `runs/ckpt.pt` exists. Override any knob via env vars, e.g.:
```
STEPS=50000 DEVICE=cuda BATCH=48 D_MODEL=192 python train.py
```
Training: a short base-only language pretrain (`WARMUP_STEPS`), then joint training of everything
(base + embedders + routers + experts + memory gate) with growth/pruning of fabric nodes.

## 4. Evaluate a checkpoint
```
python evaluate.py
```
Prints in-distribution-held CE, out-of-distribution CE (held-out sources), the novelty signal and
memory-recall confidence on each, and the per-domain embedder mix.

---

## Outputs (weights & logs)
Everything lands in `runs/`:
- **`runs/ckpt.pt`** — full resumable state: all weights, fabric topology (variable node count),
  optimizer state, the novelty frequency table, and the episodic memory buffer. Saved every
  `CKPT_EVERY` steps and at the end. Delete it to start fresh.
- **`runs/train_log.jsonl`** — one JSON record per eval (`EVAL_EVERY` steps) with `step`, `train_ce`,
  `ema`, `nodes`, `reenc_share`, `in_held`, `held_by_domain`, `ood`, `ood_by_domain`,
  `nov_held`/`nov_ood`, `memconf_held`/`memconf_ood`. Easy to plot:
  ```python
  import json; rows=[json.loads(l) for l in open("runs/train_log.jsonl")]
  ```

## Scope of training
- **Task:** next-byte prediction (vocab 256, no external tokenizer). Loss is cross-entropy in nats.
- **Training domains:** `eng` (prose), `py` (Python), `c` (C), `num` (generated numeric rows). The
  embedders specialize per domain via the gist router (watch the `embedder_mix`).
- **Two eval sets:**
  - *in-distribution held* — unseen chunks of the **same files** (measures fit + recall).
  - *OOD* — **entirely unseen sources** (`eng_OOD` = a different book, `code_OOD` = Rust). This is
    the real generalization test; the in-distribution number alone is optimistic.
- **What's in the model:** trainable deep base (the floor-lever), gist-routed embedder mix,
  gist-routed growable/halting/prunable fabric, re-embed + re-encode operators, recurrent routing,
  novelty signal, episodic one-shot memory. **Not included:** comparative-select/real-combine
  routing and separate-headed experts (these are incompatible with the trainable base — they need a
  frozen representation — so they were intentionally left out of this configuration).

## What to watch (reference behavior from the small-scale run)
- **The decoupling:** `in_held` should fall while `ood` stays roughly flat (does **not** climb as
  `in_held` improves). At ~1.4k steps on the small reference config, in-held reached ~1.71 while
  OOD-code held ~4.1–4.5. If `ood` climbs steadily as `in_held` drops, the memory gate isn't
  carrying the load — check `memconf_*`.
- **Novelty signal:** `nov_held` should be low (~0.07–0.15) and `nov_ood` clearly higher
  (~0.35–0.55). It learns what it hasn't seen.
- **Memory:** `memconf_held` high (~0.9) and `memconf_ood` lower — it recalls the familiar and
  hesitates on the novel, so recall doesn't corrupt OOD.
- **Self-limiting:** the fabric grows under pressure and prunes underused nodes; expect it to settle
  below `NMAX` rather than pinning the ceiling once memory offloads work.
- **Re-encode:** with `REENC_COST=0` the router decides freely; in the reference run it drove the
  re-encode share toward 0 (re-perception rarely helps these inputs). `reenc_share` in the log shows
  this. The router's call, not a penalty.

## Important notes
- **Compute:** the expensive op is **re-encode** (it runs the latent through the whole base again,
  every fabric step). On CPU this dominates. For the larger scale **use a GPU** (`DEVICE=cuda`), or
  set `ENABLE_REENCODE=0` to drop it for a big speedup at little cost (the router de-emphasizes it
  anyway). The novelty tracker is a Python trigram loop and is CPU-bound; it's cheap at these sizes
  but scales with `BATCH*CTX`.
- **Scaling levers (in `config.py` or via env):** `D_MODEL`, `N_LAYERS` (depth lowers the floor),
  `CTX`, `BATCH`, `STEPS`, `MEMCAP`, `NMAX`. More/diverse **data** is the dominant lever for OOD —
  scale the corpus folders, not just the model.
- **Regularization:** `DROPOUT` (default 0.1) and `WEIGHT_DECAY` (0.02) are on; for the cleanest OOD
  story, prefer best-checkpoint selection on the `ood` metric from the log over training to the end.
- **Determinism:** `SEED` fixes the run; results still vary across hardware/threads.
- **Honest caveats:** absolute OOD on cross-language code (Rust) stays high — it's genuinely far from
  the training code. The in-held gain is partly recall (intended) and is gated out of OOD, so it
  doesn't inflate the OOD number. The decoupling is the result that matters; verify it holds as you
  scale.

## Config reference
See `config.py` — every knob has a comment and an env-var override. Key ones:
`DEVICE, D_MODEL, N_LAYERS, CTX, BATCH, STEPS, WARMUP_STEPS, LR, WEIGHT_DECAY, DROPOUT,
M_EMBED, DK, ALPHA, N0/NMAX/MINN, TARGET, THROTTLE, PONDER, REENC_COST, ENABLE_REENCODE,
MEMCAP, DATA_CAP, HELD, OOD_N`.

## Files
`config.py` knobs · `get_data.py` corpus · `data_utils.py` loading · `system.py` the model +
train/eval/save/load helpers · `train.py` training loop · `evaluate.py` eval-only ·
`language.py` + `identity.py` the ByteLM base (dependencies).
