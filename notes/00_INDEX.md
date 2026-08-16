# 00 — INDEX

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are tiny
> — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has reached
> 1.227 b/B (`33a9299`), larger than the gap between any two architectures ever compared here.
> Several confidently-stated findings were later retracted when the measurement turned out to be
> broken. Every entry records **what was observed under these conditions**, never **what is true**.
> Where a result was later invalidated, the invalidation is stated next to it, not in a footnote.

---

## Read this before anything else in the repository

**The top-level documentation is stale and reads as current.** `README.md` (2026-07-21),
`STATE.md` (07-24, 71 kB), `CL_TESTBED.md` (07-21), and the `docs/`, `handoff/` and `garry/`
directories all predate the point at which the system acquired the components it is now about.
They describe a superseded workflow (`run_full_unfrozen.sh`), the retired "B" naming, and a
"-0.0009 collateral" headline that no longer means anything. `handoff/GLOSSARY.md` documents a
`Fabric` → `Router` + `Compositor` rename that was **never adopted in the code**. `tokenizer.py`'s
module docstring is about a different project entirely.

Nothing in those files has been deleted, because they are a real record of what was believed at
the time. But they are history, not documentation. **This directory supersedes them.**

## What the system is

A byte-level language model with five things bolted to it, each of which can be turned off:

1. a **dynamic BPE tokenizer** that mints new merges *during* training, so the vocabulary and the
   segmentation both move while the model learns against them;
2. the **Fabric** — a preallocated population of low-rank expert adapters, routed per window, that
   are born, ranked, mutated and culled during the run;
3. a **self-organising domain assembler** that clusters the stream into domains from a learned
   signature space, with no labels;
4. an **editable external memory** — a surprise-gated kNN store of context→token pairs that can be
   read, re-keyed, flagged wrong, and deleted per entry or per source;
5. a **world model** that predicts the next latent state.

## What it is FOR

From `9d90416`, which is the commit that says so most plainly:

> The stated goal is the output, continual learning without exorbitant forgetting, and old
> capacities surviving. Domain counts are a diagnostic for those and I have been reporting them as
> if they were the result.

So, in order: **(1) the output** — generation is the deliverable; **(2) continual learning without
exorbitant forgetting**; **(3) the machinery**, only insofar as it moves 1 and 2.

**Domain counts, purity, silhouette, V-measure and specialization are diagnostics, not targets.**
The record shows steering by them consumed weeks. `06_CONTINUAL_LEARNING.md` documents the
resulting imbalance: essentially **one run** bears on the actual target, against dozens on the
machinery — one row of 42 in `runs.csv`, two experiments of 56.

## Reading order

| # | File | What it is | Lines |
|---|---|---|---|
| **01** | `01_TIMELINE.md` | the commit spine, with 15 ancestry-verified epoch boundaries | 485 |
| 02 | `02_IDEAS.md` | the researcher's ideas and what happened to each | 2500 |
| 03 | `03_EXPERIMENTS.md` | what was tested and why (X01–X56, O01–O16) | 952 |
| 04 | `04_RESULTS.md` | every number, with instrument era and corpus era | 924 |
| **05** | `05_ERRORS.md` | 226 errors and the invalidation list (INV-01–INV-44) | 2455 |
| 06 | `06_CONTINUAL_LEARNING.md` | the target, and what is actually known about it | 720 |
| 07 | `07_WIP.md` | unfinished, never-run, and broken | 687 |
| 08 | `08_GLOSSARY.md` | the project's vocabulary, incl. 16 terms that changed meaning | 847 |
| 09 | `09_COMMENT_AUDIT.md` | a migration plan for the source comments (plan only) | 507 |
| 10 | `10_HISTORY_FINDINGS.md` | what only the transcript knows | 850 |
| — | `LITREVIEW_FINDINGS.md` | external literature, checked against this repo | 162 |

**Start with 01 and 05.** Every other file cites them, and 05's invalidation list is what stops a
reader believing a number that has already been withdrawn. `04_RESULTS.md` in particular is not
safe to read before 05 — a large fraction of its rows carry an INV id.

**Safe to read standalone:** `08_GLOSSARY.md` and `07_WIP.md`. Both are self-contained by design.

**If you have five minutes:** the "what can I actually conclude" section at the end of
`04_RESULTS.md`, and the invalidation summary in `05_ERRORS.md`.

## Provenance

Everything here is derived from committed evidence under `notes/_evidence/`, so any claim can be
re-checked without re-running anything:

- `commit_log.txt` — all 282 commits with full messages. The **primary record**: GPU results from
  2026-08-10 onward exist only here and in `runs.csv`.
- `runs_snapshot.csv` — `runs.csv` as of writing, so `04_RESULTS.md` stays re-derivable.
- `chat/user_turns.md` — 455 turns from the session transcript, verbatim. **9 are flagged as not
  the researcher** (auto-compaction summaries injected with `role=user`); genuine turns: 446.
- `chat/chunks/` — the full 26-day transcript (2026-07-21 → 2026-08-15), distilled and split into
  12 chronological chunks.
- `chat/extracts/` — 12 structured extractions, one per chunk.
- `litreview/` — an external literature review, archived verbatim.

Every quotation in `02_IDEAS.md` was mechanically located in `user_turns.md` before being
reproduced; 26 that could not be were dropped or marked unconfirmed rather than printed.

## Five things to know before spending any GPU time

1. **The default configuration at HEAD is close to the arm the 2×2 found fatal.** `_SPEC` reads
   `FAB_GROW=1`, `FAB_N0=3`, `FAB_NMAX=4096`. `FAB_NEW_FRAC` and `FAB_BURST` were added afterwards
   to bound the newborn fraction, and that mitigation has never been measured at pilot scale.
2. **The best result on record ran with no selection at all.** Founders had no birthday and were
   permanently immune to culling, so arm B (`FAB_N0=2048`) had zero culls for its whole life
   (`a5cc7ea`, INV-15). It is not reproducible at HEAD; pin the config or re-run it.
3. **Seed spread is a property of the arm, not the instrument.** Across the four arms of one 2×2,
   estimated σ ranges 0.047 to 1.225 — 26×, same day, same instrument. Never pool it. And arm B's
   celebrated 0.080 spread did **not** hold at 18 epochs on the current corpus.
4. **`runs.csv` mixes two instrument eras and two corpora with no column for either.**
   `04_RESULTS.md` adds both. Eighteen rows share one corpus while straddling `c76dc74`, so
   differences across them are unattributable.
5. **Check the `[build]` line of every log before reading its numbers.** Two 18-epoch runs were
   spent on a checkout that predated the changes they were meant to evaluate.

## Where this is incomplete

- `09_COMMENT_AUDIT.md` is a **plan**. 51 MOVEs and 19 WRONGs are identified; none has been
  applied to the source.
- Two open questions need the GPU box and cannot be answered from this checkout: no
  `runs/equiv_noise_*` exists, so `c6f54e6`'s INERT verdicts are untrusted; and
  `runs/equiv_c14f876_vs_37ecb20` stores logs but no verdict line.
- The one continual-learning run's log was lost. `holdout.py` reproduces such figures exactly from
  a checkpoint, so it is recoverable **if the GPU box still has one** — see
  `06_CONTINUAL_LEARNING.md`.
