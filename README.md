# Continual-learning system with a society of independent experts — how to use

An autonomous continual-learning system driven by ONE unlabeled stream:
**self-assemble domains → grow a society of independent experts → detect wrong info → edit/unlearn cleanly.**
Nothing is frozen, nothing is labeled, and every population (tokenizer, domains, experts) grows, replicates and culls
under its own selection pressure. Runs on a CUDA GPU (an H100 is plenty; CPU works only for tiny smoke tests).

**Headline result:** deleting an entire expert's WEIGHTS costs **-0.0009** collateral — cleaner than deleting memory
rows (0.0303) and ~25,000x cleaner than gradient-ascent unlearning (24.79) measured in the same run. Weights are hard
to edit *because they're entangled*; an independent-expert society makes them as deletable as database rows.

**Start here:**
- `garry/GARRY.md` — the frozen known-good milestone: exact config, measured results, honest limitations.
- `STATE.md` — the living ledger: every decision, what's included/excluded, open questions, full changelog.
- `bash run_full_unfrozen.sh` — the whole system in one command (`RUN_NAME=<tag>` to isolate a run).
- `python3 prompt.py CKPT=runs/<tag>` — message the trained model.
- `DATA_DIR=/path/to/corpus` — point any copy at a different (e.g. much larger) corpus.

## Setup (once, on the GPU machine)
    unzip -o overarching-package.zip && cd overarching-package
    # deps: pip install torch numpy   (see requirements.txt)

## 1. Run the whole system (trains + measures + saves a checkpoint)
    tmux new -s full 'bash run_full_unfrozen.sh'
Runs everything with all features on (unfrozen model key, expanding tokenizer, adaptive gate, self-consistency B
detect-only, silhouette genuineness, composition, performance, generation, plus the mechanics). Output → `~/full.txt` (or `~/<RUN_NAME>.txt`).
Partway through it saves the trained model + tokenizer + memory to `runs/full/` (or `runs/<RUN_NAME>/`; the `runs/ck` examples below assume you launched with `RUN_NAME=ck`).
(tmux keeps it alive if SSH drops: `Ctrl-b d` to detach, `tmux attach -t full` to return.)

## 2. Message the trained model
    python3 prompt.py CKPT=runs/ck
Type a line; the model CONTINUES it in the style it learned (prose → prose, code → code). It is not a chatbot — it does
not answer questions or follow instructions, and it is semi-coherent, not fluent. `Ctrl-C` to quit.
    MEM=1  python3 prompt.py CKPT=runs/ck            # blend the editable memory in (richer, but bleeds across domains)
    GEN_TEMP=0.4  python3 prompt.py CKPT=runs/ck     # more conservative sampling (try 0.4–0.7)
    GEN_LEN=300   python3 prompt.py CKPT=runs/ck     # longer continuations
    PROMPT="def add(a, b):"  python3 prompt.py CKPT=runs/ck   # one-shot, no typing

## The pieces (run individually if you want)
- `python3 self_organize.py`  — the product loop only (assemble → detect-wrong → perform → compose → generate → edit).
  Add `SAVE_CKPT=runs/ck` to save a promptable model. Byte-level by default; `TOKENIZER=1` for the expanding tokenizer.
- `python3 cl_bench.py`       — mechanics only (forgetting vs replay, editability vs weights, drift, wrongness).
- `python3 prompt.py`         — message a saved checkpoint.

## Docs
- `CL_TESTBED.md` — what each part does, the current findings, and the full knob list.
- `STATE.md`      — living project ledger: decisions, what's included/deferred, open questions, latest results.

## Honest status (see STATE.md §7 for numbers)
A (editing by provenance): PROVEN — surgical unlearn of a whole process, ~1000× less collateral than weights.
C (self-assembly): works, over-segments (harmless — segments compose at retrieval).
B (wrong-detection): DOES NOT WORK in the realistic regime (~1% precision); runs detect-only, never deletes.
Generation: semi-coherent with the tokenizer (~1.7 bits/byte); the small base model is the ceiling on fluency.
