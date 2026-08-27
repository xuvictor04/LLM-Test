# GARRY — frozen milestone (T33)

**This directory is a FROZEN snapshot. Do not edit it.** Development continues in the parent directory.
Garry exists so there is always a known-good reference to fall back to and to compare against.

## What Garry is

The first version where the whole architecture works at once, and where **weights became as deletable as
database rows** — which inverts the premise the project started from.

## Measured results (H100, real corpora eng/py/num/c, 6M-byte stream)

| metric | value | meaning |
|---|---|---|
| **expert-deletion collateral** | **−0.0009** | deleting a whole expert's WEIGHTS is free |
| memory-delete collateral (same run) | 0.0303 | deleting memory rows costs *more* |
| weights gradient-ascent (same run) | 24.79 | the entangled baseline this replaces |
| **end-to-end bits/byte** | **1.967** | vs 2.394 no fabric, 2.668 byte-level start |
| memory contribution | +1.639 | memory still earns its keep |
| cross-segment composition | +0.237 | segments compose (over-segmentation harmless) |
| B (wrongness) recall | 96% | precision still ~1% — unresolved, see below |
| domains self-assembled | 468 | from an UNLABELED stream, purity 0.92 |
| tokenizer | 256 → 6241 | minted online DURING training |
| experts | 3 → 6 | grown on loss plateau, mass [0.15,0.14,0.14,0.14,0.14] |
| process unlearn | target +0.3525, others Δ0.0205 | LOCAL |
| speed | 4.5 ms/step | ~13 min for the full run |

## The configuration that produced it

```
MODEL=gru  D_MODEL_B=512  STREAM_LEN=6000000  WIN=96
FABRIC=1  SOCIETY=1  ENS_K=2  IND_W=0.5  IND_K=2
FAB_N0=3  FAB_NMAX=6  FAB_STEPS=3  FAB_DK=32  FAB_MIN_STEPS=0  PONDER=0.01  PONDER_WARM=8000
TOKENIZER=1  TOK_ONLINE=1  VMAX=8192  SEED_VOCAB=1024  MIN_PAIR=80  GROW_EVERY=40  GROW_BURST=10
KEY_SRC=model  MEM_CAP=300000  EVICT=recency  MANAGE=1  EXPERTS=0
```

## What makes it work

1. **Experts are independent agents.** Each maps the same base representation to its OWN output — no chaining, so
   expert i never depends on expert j.
2. **They are ensembled at the PREDICTION level** (`Σ wᵢ·head(oᵢ)`), not by averaging hidden states. Averaging
   hiddens produces representations no expert was trained to emit; that was what broke generation.
3. **An independence loss** trains each of the top-`IND_K` experts to solve the task ALONE, weighted by its routing
   mass — making the population an ENSEMBLE (survives losing a member) rather than a DECOMPOSITION (does not).
4. **Targeted birth**: a new expert's key is seeded where the router will actually send that region, and its body is
   identity at birth so it inherits the current (ever-changing) base. Random keys produced dead experts.
5. **Selection keeps running**: create on plateau, replicate, cull, merge — for experts, domains, and the tokenizer.

## Run it
```
cd garry && bash run_full_unfrozen.sh            # writes ~/garry.txt, runs/garry/, data/tok_garry.json
python3 prompt.py CKPT=runs/garry                # message it (fabric included)
```
It reads the shared corpora via `DATA_DIR=../data` and namespaces its own outputs, so it never collides with
development runs. Point `DATA_DIR` elsewhere to run Garry on a different (e.g. much larger) corpus.

## Known limitations (honest)

- **B precision ~1%.** Autonomous wrong-detection still does not work: the write gate stores SURPRISING tokens and B
  flags SURPRISING tokens, so genuine-novel and wrong are conflated. Recall is high, precision is not. Detect-only.
- **`model ALONE` in the FABRIC readout overstates the fabric** — it ablates a component the model trained with,
  including its normalization. The honest figure is run-vs-run: 1.967 with the fabric against 2.394 without.
- **Faded knowledge is evicted** under a bounded store (circular buffer). `EVICT=usage` does NOT fix this — faded
  means unretrieved means least-used. Only an explicit per-domain quota would.
- **Domains are an editing index**, not a knowledge organization: they do not partition retrieval, and management
  buys bounded metadata rather than prediction quality.
- Base model is a small GRU; generation is coherent but not fluent. That ceiling is the base model, not the architecture.
