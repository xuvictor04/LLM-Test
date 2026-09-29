# 04 — RESULTS

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are tiny
> — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has reached
> 1.227 b/B (`33a9299`), larger than the gap between any two architectures ever compared here.
> Several confidently-stated findings were later retracted when the measurement turned out to be
> broken. Every entry records **what was observed under these conditions**, never **what is true**.
> Where a result was later invalidated, the invalidation is stated next to it, not in a footnote.

---

## What this file is

Section **C**: the tables. It is a **reference, not a narrative**. A reader consults it to find out
what a number is and whether it can be trusted, and leaves. The prose is deliberately thin; the
columns carry the argument.

**Authority.** This file re-derives nothing. It cites:

- [`notes/01_TIMELINE.md`](01_TIMELINE.md) — the commit spine, the 15 ancestry-verified **EPOCH
  BOUNDARIES** (`E1`..`E15`), **Appendix A** (every `runs.csv` row resolved against the instrument
  fixes) and **Appendix B** (corpus lineage). Instrument and corpus eras below are copied from
  there, not recomputed.
- [`notes/05_ERRORS.md`](05_ERRORS.md) — the **INVALIDATION LIST** (`INV-01`..`INV-44`).
  **Authoritative.** Where it voids a number, the `INV` id sits in the row, inline, and the number
  is not restated as if it stood.
- [`notes/03_EXPERIMENTS.md`](03_EXPERIMENTS.md) — the 56 experiments (`X01`..`X56`) and 16
  incidental observations (`O01`..`O16`) that produced these numbers.
- [`notes/08_GLOSSARY.md`](08_GLOSSARY.md) — what each metric *is*, and which metrics are
  **DIAGNOSTICS, NOT TARGETS**.
- [`notes/LITREVIEW_FINDINGS.md`](LITREVIEW_FINDINGS.md) — an external literature check already
  verified against this repo. Two of its findings are applied throughout this file (§0.5, §0.6).

**Data sources.** `runs.csv` (42 data rows), mirrored byte-identically at
`notes/_evidence/runs_snapshot.csv` — verified with `diff` at time of writing, so every table below
is re-derivable. Column semantics from `runs.py` (**every column is parsed out of a log, never
typed** — except the five `(no log)` rows, which are transcribed from source comments and say so).
Commit text from `notes/_evidence/commit_log.txt`.

> **Count correction.** `DOC_PLAN.md` specifies *"the 43 rows of `runs.csv`"*. The file has **42**
> data rows (43 lines including the header). `01_TIMELINE.md` Appendix A independently says 42.
> **42 is used throughout.**

---

# §0. THE SIX RULES FOR READING EVERY TABLE BELOW

These are not preamble. A number lifted out of this file without them is not the number that was
measured.

## 0.1 `held_out` is the FINAL model. Never `.best`. Every row, no exceptions.

`runs.py:71-72` parses `held_out` off the line `train X +/- a | held-out Y +/- b`:

```
row["held_out"] = _grab(r"train [\d.]+(?: \+/- [\d.]+)? \| held-out ([\d.]+)", t)
```

That line is emitted at `self_organize.py:5934`, inside `=== MEMORIZATION CHECK: train vs HELD-OUT
===`, which scores the **live in-memory model** after training has finished. Nothing reloads
`.best` before it. `runs.py:63` corroborates: the `steps` column is keyed to the literal text
`SAMPLED FROM: the FINAL model, step (\d+)`. `_best_bpb` (`self_organize.py:4761-4770`) tracks the
mid-run **learning curve** instead, writes `<SAVE_CKPT>.best`, is reported only as prose in the
GENERATION section — and **`runs.py` never parses it**. Established in full at
`03_EXPERIMENTS.md` Part IV.

Two consequences that matter here:

- **`.best` and `held_out` are not the same measurement.** They disagreed by **1.6 b/B** on `base_5`
  (curve 3.764 vs check 2.182, `E9`). This is exactly why **`INV-18` voids the curve-derived
  claims but explicitly spares the end-of-run figures** — so `runs.csv` is on the right side of it.
- **The `past_min` column already tells you the final-vs-best gap.** `+0.000` on **19 of the 42
  rows** (final *is* best); up to `+3.219` on `frozen_8ep_75pct_dead`.

## 0.2 Every number carries four markers, and all four are load-bearing

| marker | why |
|---|---|
| **n** | said out loud in every table header. Most of this file is n=1. |
| **commit** | which code produced it. `01_TIMELINE` resolves it to an epoch. |
| **INSTRUMENT era** | pre/post `c76dc74`. Below this line, arm comparisons were measured through an instrument that was editing the run (`INV-13`). |
| **CORPUS era** | which corpus the held-out slice came from. `held_out` is **not comparable across this boundary at all**. |

## 0.3 CORPUS ERA — why `held_out` cannot be read down the table

The corpus was **re-fetched larger and harder** before `ep18_big` (`ac79e92`, 08-15): order-1 moved
**3.440 → 3.747**. `runs.csv` has **no corpus column**. `01_TIMELINE` Appendix B reconstructs the
lineage from the `order1` / `uniform` anchors, and this file adds **CORPUS** as an explicit column
so the boundary cannot be missed.

The trap this closes, in the commit's own words:

> *"the corpus was re-fetched larger for this run and got HARDER (order-1 3.440 → 3.747), so the raw
> held-out is not comparable to the 8-epoch arm B. Against each run's own order-1 anchor it is
> **1.411 vs 1.441** — 18 epochs bought nothing, and did not cost the 0.34 the raw numbers suggest
> either."* — `ac79e92`

**The 18-row problem.** Corpus era **C2** (order-1 3.438–3.440) holds **18 rows** spanning `1a113f5`
(08-11) through `e9f2e58` (08-14) — i.e. it **straddles `c76dc74`**. Corpus constant, instrument
changed. That is the only group in the file where the instrument boundary is isolated, and it is
also the group most likely to be read as one homogeneous block. **It is not one block.** Both
columns are required.

**Practical rule, from `01_TIMELINE` Appendix B and `08_GLOSSARY` §1.12:** quote every held-out
figure against its **own** run's order-1, never against another row's. This file computes that
column (`Δ order-1`) for every row that has an anchor.

> **Verification of the derived column.** `Δ order-1 = order1 − held_out`, computed here from
> `runs.csv`. Mean over `ep18_big_s{0,1,2}` = **1.411**; mean over `popB_n2048_s{0,1,2}` =
> **1.441**. Those are `ac79e92`'s two published figures, reproduced exactly. The column is
> arithmetic on the CSV, not a new measurement.

## 0.4 Voided results are marked in the row, with their INV id

Per `05_ERRORS.md`'s status key:

| status | meaning |
|---|---|
| **VOID** | does not stand; must not be quoted as evidence. |
| **UNATTRIBUTABLE** | measured, but cannot be assigned to the variable it was labelled with. |
| **UNCONTROLLED** | real observation, no control, supports no comparison. |
| **SUPERSEDED** | correct at the time, replaced by a better measurement. |
| **DEGRADED** | still usable, with a stated caveat attached. |
| **RELABELLED** | valid as a measurement of something other than its name. |

Three invalidations apply so widely that they are stated once here rather than in all 42 rows:

- **`INV-13`** — *"Every arm comparison in the record before 2026-08-13."* Applies to **every
  pre-`c76dc74` row in this file** (18 with commits + 3 `707f1af` + 2 unresolvable = 23 of 42).
- **`INV-35`** — *"Every single-run architecture comparison in this branch."* Applies to **every
  n=1 row**, whatever its era. The widest invalidation in `05_ERRORS.md`.
- **`INV-06` / `INV-23` / `INV-24`** — between them, **every "memory contributes X" figure in the
  project is unattributable**. See §7.2.

And two that apply to every **post**-`c76dc74` row, because "post-fix" does not mean clean:

- **`E14`** (`91fd815`/`a5cc7ea`) — founders had no birthday and were permanently immune to
  culling. All 19 post-fix rows predate it.
- **`E15`** (`e25d9b5`/`daf9f89`) — `MEM_PER_EXPERT` was actually **on** for the project's whole
  life, and the eviction rules were ranking a constant. All 19 post-fix rows predate it.

## 0.5 THE BITS/BYTE ANCHOR IS WRONG FOR CODE

From `LITREVIEW_FINDINGS.md`, verified against this repo. `08_GLOSSARY` §Measurement offers
*"GPT-2-small sits near 1.0–1.2 b/B on comparable text"* as the scale marker. That figure is for
**English web text only**:

| reference corpus | GPT-2-small b/B |
|---|---|
| Pile-CC (web) | **1.0878** |
| OpenWebText2 (web) | **1.1111** |
| Pile aggregate (mixed) | **1.2253** |
| **GitHub (code)** | **1.7912** |

**There is no single scale marker across text and code.** Every Python/code result in this project
has been read against the web-text anchor and has therefore **looked worse than it was**.

**What this touches in `runs.csv`:** the pilot harness runs `DOMAINS=eng` (English only) at every
subcommand in `longrun.sh` except `pilot-add`, which runs `DOMAINS="eng,$NAME"`. So **exactly one
row contains code**: `continual_eng_py` (`DOMAINS="eng,py"`, Python from the-stack). Its figures
are flagged with 🅒 in the master table and re-read against the correct anchor in §7.3 and §10.2.
The four-corpora domain campaign (§9) also included non-English material, and its b/B figures
inherit the same correction.

## 0.6 SEED VARIANCE IS A PROPERTY OF THE ARM, NOT OF THE MEASUREMENT

Also from `LITREVIEW_FINDINGS.md`. Across the four arms of the `cc0a377` 2x2 — **3 seeds each, same
day, same instrument, one knob apart** — the estimated σ ranges **0.047 (fixed 2048)** to
**1.225 (ramp 3→4096)**. That is **26×**.

**Do not pool.** A single pooled σ is the wrong model and this file never reports one. Every spread
below is **per-arm**. And the pattern is legible: **instability tracks ramping**. Arm D is not
merely worse on the mean — it is unstable, and *"whether the mean difference or the variance
difference is the real phenomenon has never been asked here, and the variance is the larger
effect."*

---

# §1. MASTER TABLE — all 42 rows of `runs.csv`

**Header block (applies to the whole table).**

| field | value |
|---|---|
| source | `runs.csv` == `notes/_evidence/runs_snapshot.csv` (verified identical) |
| rows | 42 data rows |
| `held_out` | **FINAL model, end-of-run, re-tokenised memorization check** (§0.1) — never `.best` |
| n | **1 per row.** Where three rows share an arm they are marked; the arm is n=3, each row is n=1 |
| corpus column | reconstructed from anchors per `01_TIMELINE` Appendix B — `runs.csv` has no corpus field |
| `SAVE_CKPT` | **not a column in `runs.csv`.** Known: `grid` and `seeds` both default checkpoints ON (`GRID_CKPT:-1`, `SEED_CKPT:-1`, `longrun.sh:590,669`); the `seeds` default was itself a fix, and `nogrow_s2` demonstrably wrote one because `continual_eng_py` RESUMEd from it. Two other subcommands hardcode `SAVE_CKPT=0` (`longrun.sh:750,819`). **It matters:** two runs with byte-identical code and the same seed, differing *only* in whether `SAVE_CKPT` was set, came back at **3.694 vs 2.100** — 1.594 b/B (`5f4f117`, `O09`, `INV-12`) |
| `Δ order-1` | derived here as `order1 − held_out`. Positive = beats a two-line bigram table. **This is the only column comparable across corpora** |

**Instrument era key** (from `01_TIMELINE` Appendix A; ancestry-verified, not inferred from dates):

- **mid** = post-`5f4f117`, pre-`c76dc74`. Router no longer trained by eval passes; diagnostics
  still editing the run. **Every row in `runs.csv` that has a commit is post-`5f4f117`.**
- **post** = post-`c76dc74`. Still pre-`E14`, pre-`E15`.
- **?** = era unresolvable from `runs.csv` alone.

**Corpus era key** (from `01_TIMELINE` Appendix B):

| id | order-1 | uniform | what it is |
|---|---|---|---|
| **C1** | 3.228–3.353 | 3.305–3.523 | the 08-11..08-13 VMAX grid corpus. Note the 4096 rows cluster at 3.351–3.353 and the 8192 rows at 3.228–3.321 — 0.12 of movement *within one grid*, so order-1 identifies a corpus only coarsely |
| **C2** | 3.438–3.440 | 3.780–3.783 | the pre-refetch pilot corpus. **18 rows. Straddles `c76dc74`** |
| **C3** | 3.747 | 4.079 | the re-fetched, larger, **harder** corpus (`ac79e92`) |
| **C4** | 3.644 | 4.695 | English **+ Python** — a different stream by construction 🅒 |
| **C5** | 3.525 | 4.819 | the frozen-vocabulary arms. **uniform 4.819 shows the vocabulary dominates these rows**, and the arms were themselves defective — not attributable to corpus |
| **C6** | 3.316 | 3.927 | `base_8ep_gate_starved` alone; its vocabulary was starved to 1439/2048, which moves both anchors |
| **C7** | 3.495 | *(none)* | the 07-29 English 120 kB run. Dates the `fabric_*` pair; matches no other group |
| **C?** | *(no anchors)* | — | the three `707f1af` comment-sourced rows carry no anchors at all |

## The table

🅒 = contains code; read against the GitHub anchor 1.7912, not 1.09–1.11 (§0.5).

| # | tag | commit | date | ep | VMAX | **held_out** ±SE | order-1 | **Δ order-1** | past_min | words% | **INSTR** | **CORPUS** | STATUS — inline invalidation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `vmax4k_8ep` | `a21a721` | 08-11 | 8 | 4096 | 2.140 | 3.352 | +1.212 | +0.000 | 87 | **mid** | **C1** | **UNATTRIBUTABLE — `INV-31`** (VMAX re-rolled every weight). Also `INV-13`, `INV-35` |
| 2 | `vmax8k_8ep` | `a21a721` | 08-11 | 8 | 8192 | 3.561 | 3.321 | **−0.240** | +0.659 | 31 | **mid** | **C1** | **VOID as named — `INV-42`** (arm configured to guarantee 41% dead rows). Also `INV-34`, `INV-31`, `INV-13` |
| 3 | `vmax4k_18ep_oldLR` | `2c705c7` | 08-11 | 18 | 4096 | 3.250 | 3.352 | +0.102 | +0.439 | 43 | **mid** | **C1** | **UNATTRIBUTABLE — `INV-31`.** One of the four runs of one nominal arm that spread 1.227 (`INV-35`). No `LR_EPOCHS` |
| 4 | `vmax8k_18ep_oldLR` | `2c705c7` | 08-11 | 18 | 8192 | 4.383 | 3.228 | **−1.155** | +1.152 | 19 | **mid** | **C1** | **UNATTRIBUTABLE — `INV-31`.** Filled its vocabulary **completely** (0% dead) and is the **worst** of four — the row that falsified the dead-row story (§5). Only row in the file with a **positive** memorization gap (+0.267) |
| 5 | `vmax4k_18ep_lr8` | `f279fd0` | 08-11 | 18 | 4096 | **2.023** | 3.352 | **+1.329** | +0.000 | 89 | **mid** | **C1** | CSV note says *"best on record"*. **`INV-35` VOID as a ranking** — this is one of the four runs of one arm that spread **1.227 b/B**. Also `INV-31`, `INV-13` |
| 6 | `vmax8k_18ep_lr8` | `5239ebb` | 08-11 | 18 | 8192 | 3.377 | 3.230 | −0.147 | +0.436 | 33 | **mid** | **C1** | **UNATTRIBUTABLE — `INV-31`.** Also `INV-13`, `INV-35` |
| 7 | `vmax8k_30ep_lr8` | `ec9813e` | 08-11 | 30 | 8192 | 3.368 | 3.230 | −0.138 | +0.373 | 58 | **mid** | **C1** | CSV note: *"12 extra epochs bought 0.009"* (vs row 6). The **schedule property** behind it stands (`X32`, verified against `_lr_at`); the **run pair** is n=1 and `INV-13`/`INV-31` |
| 8 | `frozen512_18ep_oldLR` | `ec9813e` | 08-11 | 18 | 512 | 5.540 | 3.525 | **−2.015** | +2.875 | 37 | **mid** | **C5** | **VOID as named — `INV-42`.** *"freeze at step 1"*; vocabulary dominates the anchors |
| 9 | `base_8ep_707f1af` | *(no log)* | — | 8 | 2048 | 1.962 | — | *n/a* | — | — | **mid**¹ | **C?** | Source: `self_organize.py:4624` comment, 6-arm pilot at `707f1af`. **No log, no anchors.** `X37` |
| 10 | `frozen_8ep_707f1af` | *(no log)* | — | 8 | 2048 | 2.072 | — | *n/a* | — | — | **mid**¹ | **C?** | Same source. **`INV-42`** (defective frozen arms) and **`INV-10`** for the pair below |
| 11 | `frozen_nr_8ep_707f1af` | *(no log)* | — | 8 | 2048 | 2.365 | — | *n/a* | — | — | **mid**¹ | **C?** | Same source. **`INV-10` UNATTRIBUTABLE** — `RETOK_EVERY=0` also silently disabled signature batching, so `frozen` vs `frozen_nr` differs in **two** ways |
| 12 | `fabric_off` | *(none)* | — | — | — | 3.543 | 3.495 | **−0.048** | — | — | **?**² | **C7** | **VOID — `INV-36`.** An eval-time **knockout**, not a retrained ablation. See §7.1 |
| 13 | `fabric_on` | *(none)* | — | — | — | 3.441 | 3.495 | +0.054 | — | — | **?**² | **C7** | **VOID — `INV-36`.** The +0.709 this pair encodes justified defaulting `FABRIC` ON and was **retracted** (`e60b8e0`, `9d90416`) |
| 14 | `base_8ep_gate_starved` | `136461c` | 08-11 | 8 | 2048 | 3.600 | 3.316 | **−0.284** | +0.910 | 33 | **mid** | **C6** | Stands **only** as the observation that a `TOK_MINT_PMIN=0.10` gate starved minting to 1439/2048 (29.7% dead) and caused the fail-open fix (`X41`). **Not a baseline.** `INV-13` |
| 15 | `base_8ep_pilot2` | `1a113f5` | 08-11 | 8 | 2048 | 2.239 | 3.438 | +1.199 | +0.000 | 75 | **mid** | **C2** | Stands as a **regression check** — *"reproduces 2.239 on this corpus"* (`b6952da`). `INV-13` for any arm comparison |
| 16 | `nogate_8ep_pilot2` | `1a113f5` | 08-11 | 8 | 2048 | 2.239 | 3.438 | +1.199 | +0.000 | 75 | **mid** | **C2** | **Byte-identical** to row 15, same final step 48133 — a **determinism** result (`X51`), not an arm result. The gate default is 0 |
| 17 | `frozen_8ep_75pct_dead` | `1a113f5` | 08-11 | 8 | 2048 | 6.114 | 3.525 | **−2.589** | +3.219 | 4 | **mid** | **C5** | **VOID as named — `INV-42`.** Arm defect: `VMAX=2048` with vocab frozen at 512. Also the 75% point of the `INV-34` dead-row series |
| 18 | `frozen_8ep_clean` | `25c37eb` | 08-12 | 8 | 512 | 4.364 | 3.525 | −0.839 | +1.533 | 26 | **mid** | **C5** | Clean re-run replacing row 17. 0% dead; retok fires 22× on a frozen vocabulary. **`INV-10` UNATTRIBUTABLE** as half of the `frozen`/`frozen_nr` pair |
| 19 | `frozen_nr_8ep_clean` | `25c37eb` | 08-12 | 8 | 512 | 2.175 | 3.525 | **+1.350** | +0.000 | 94 | **mid** | **C5** | CSV note: *"BEST: 94% real words; identical vocab to frozen, retok off"*. **`INV-10` UNATTRIBUTABLE** — the 2.189 gap to row 18 was quoted as *"the largest single effect on record"* and the two arms differ in **two** knobs |
| 20 | `base_18ep_guard` | `d0728fe` | 08-13 | 18 | 2048 | 3.241 | 3.440 | +0.199 | +0.833 | 43 | **mid** | **C2** | `INV-13`, `INV-35`. Guard on |
| 21 | `vmax4k_18ep_guard` | `d0728fe` | 08-13 | 18 | 4096 | 2.132 | 3.353 | +1.221 | +0.000 | 77 | **mid** | **C1** | **UNATTRIBUTABLE — `INV-31`.** Second of the four runs of one arm (`INV-35`) |
| 22 | `vmax8k_18ep_guard` | `d0728fe` | 08-13 | 18 | 8192 | 3.989 | 3.230 | **−0.759** | +1.192 | 31 | **mid** | **C1** | **UNATTRIBUTABLE — `INV-31`.** Also `INV-13` |
| 23 | `vmax4k_18ep_norestart` | `e200178` | 08-13 | 18 | 4096 | 3.054 | 3.351 | +0.297 | +0.433 | 49 | **mid** | **C1** | **VOID — `INV-35`.** Predicted to show restarts net-negative; showed the opposite; then the arm's own four runs spread **1.227 b/B**. *"It refutes the premise under every single-run comparison in this record"* (`X33`) |
| 24 | `seedfloor_s0` | `451459d` | 08-14 | 8 | 2048 | 4.327 ±0.120 | 3.440 | **−0.887** | +0.656 | 35 | **post** | **C2** | **= arm D of the 2x2.** Stands as a **noise-floor** measurement (`X52`). Pre-`E14`/`E15` |
| 25 | `seedfloor_s1` | `451459d` | 08-14 | 8 | 2048 | 3.572 ±0.038 | 3.439 | −0.133 | +0.944 | 18 | **post** | **C2** | = arm D. Same |
| 26 | `seedfloor_s2` | `451459d` | 08-14 | 8 | 2048 | 2.253 ±0.098 | 3.440 | +1.187 | +0.000 | 88 | **post** | **C2** | = arm D. Same. **Arm spread 2.074** — larger than any architectural difference in the record |
| 27 | `nogrow_s0` | `451459d` | 08-14 | 8 | 2048 | 2.047 ±0.086 | 3.440 | +1.393 | +0.000 | 94 | **post** | **C2** | **= arm A of the 2x2.** Stands (`X52`). Pre-`E14`/`E15`. **See the label discrepancy below the table** |
| 28 | `nogrow_s1` | `451459d` | 08-14 | 8 | 2048 | 2.315 ±0.110 | 3.439 | +1.124 | +0.043 | 85 | **post** | **C2** | = arm A. Same |
| 29 | `nogrow_s2` | `451459d` | 08-14 | 8 | 2048 | **1.989** ±0.077 | 3.440 | **+1.451** | +0.000 | 95 | **post** | **C2** | = arm A. Same. **This is the checkpoint `continual_eng_py` RESUMEs from** |
| 30 | `continual_eng_py` 🅒 | `b92f358` | 08-14 | 8 | 2048 | 2.243 ±0.078 | 3.644 | +1.401³ | +0.000 | 68 | **post** | **C4** 🅒 | **DEGRADED ×2 — `INV-25`** (the retention figure is **weights-only**; `holdout_bpb` does not consult memory) **and `INV-43`** (log lost to the `pilot-add` mkdir bug; numbers **hand-transcribed from a terminal copy**). Also `INV-24`. **n=1, no seed replication.** See §8 |
| 31 | `popB_n2048_s0` | `e9f2e58` | 08-14 | 8 | 2048 | 1.998 ±0.044 | 3.440 | +1.442 | +0.000 | 86 | **post** | **C2** | **= arm B. DEGRADED + NOT REPRODUCIBLE AT HEAD — `INV-15`** |
| 32 | `popC_nmax64_s0` | `e9f2e58` | 08-14 | 8 | 2048 | 2.163 ±0.109 | 3.440 | +1.277 | +0.000 | 92 | **post** | **C2** | = arm C (`FAB_NMAX=64`). Stands as measured; pre-`E14`/`E15` |
| 33 | `popB_n2048_s1` | `e9f2e58` | 08-14 | 8 | 2048 | **1.960** ±0.047 | 3.439 | **+1.479** | +0.000 | 90 | **post** | **C2** | = arm B. *"The single best number this project has produced"* — **`INV-15`**: measured under **zero culling** |
| 34 | `popC_nmax64_s1` | `e9f2e58` | 08-14 | 8 | 2048 | 2.127 ±0.083 | 3.439 | +1.312 | +0.000 | 91 | **post** | **C2** | = arm C. Stands as measured |
| 35 | `popB_n2048_s2` | `e9f2e58` | 08-14 | 8 | 2048 | 2.040 ±0.074 | 3.440 | +1.400 | +0.000 | 90 | **post** | **C2** | = arm B. **`INV-15`** |
| 36 | `popC_nmax64_s2` | `e9f2e58` | 08-14 | 8 | 2048 | 1.983 ±0.062 | 3.440 | +1.457 | +0.000 | 88 | **post** | **C2** | = arm C. Stands as measured |
| 37 | `rampfrom2048_s0` | `e9f2e58` | 08-14 | 8 | 2048 | 1.994 ±0.047 | 3.440 | +1.446 | +0.000 | 89 | **post** | **C2** | **RELABELLED — `INV-19`.** Six knobs set on a build predating all of them; every one ignored. **Valid as a ramp 2048→4096; VOID as a `GROW_CAP`/`LOSS_MASK_DEAD` test** |
| 38 | `rampfrom2048_s1` | `e9f2e58` | 08-14 | 8 | 2048 | 2.097 ±0.054 | 3.439 | +1.342 | +0.000 | 90 | **post** | **C2** | **RELABELLED — `INV-19`** |
| 39 | `rampfrom2048_s2` | `e9f2e58` | 08-14 | 8 | 2048 | 1.937 ±0.049 | 3.440 | **+1.503** | +0.000 | 88 | **post** | **C2** | **RELABELLED — `INV-19`.** Lowest raw held-out in the file, and it measures an arm nobody asked for |
| 40 | `ep18_big_s0` | `bf53d40` | 08-15 | 18 | 2048 | 2.243 ±0.081 | **3.747** | +1.504 | +0.001 | 78 | **post** | **C3** | **DEGRADED — `INV-32`.** Different, **harder** corpus. **Do not compare raw held-out to anything above.** LR restart at 100% of peak mid-run |
| 41 | `ep18_big_s1` | `bf53d40` | 08-15 | 18 | 2048 | 2.200 ±0.089 | **3.747** | +1.547 | +0.007 | 88 | **post** | **C3** | **DEGRADED — `INV-32`** |
| 42 | `ep18_big_s2` | `bf53d40` | 08-15 | 18 | 2048 | 2.564 ±0.104 | **3.747** | +1.183 | +0.309 | 79 | **post** | **C3** | **DEGRADED — `INV-32`.** *"The two seeds whose base model reads 5.612 and 5.268 are the ones that ended near a restart... That is the entire 0.364 spread"* (`ac79e92`) |

**Footnotes.**

1. Rows 9–11 carry `(no log)` in the commit column but their source pilot is `707f1af` (2026-08-10),
   which `01_TIMELINE` Appendix A verified as **post-`5f4f117`, pre-`c76dc74`** with
   `git merge-base --is-ancestor`. Era **mid**. Provenance is a **source comment**
   (`self_organize.py:4624`), not a parsed log.
2. Rows 12–13 carry **no commit and no date**. `01_TIMELINE` Appendix A: their era **cannot be
   resolved from `runs.csv` alone**. The order-1 of 3.495 matches `7a42f90`'s *"LOSES to order-1
   (3.495)"* exactly, dating them to the 07-29 English 120 kB run — i.e. **pre-both fixes**, and
   also pre-`E3` in substance since that is the commit that discovered `FABRIC=0`.
3. `a9d7258` states **+1.402**; the CSV's rounded columns give **+1.401**. The 0.001 is rounding in
   the CSV, not a disagreement. The commit's figure is the primary one.

**Distribution.** 18 rows **mid** (with commits) + 3 **mid** (comment-sourced) + 2 **unresolvable**
= **23 pre-`c76dc74`**; **19 post-`c76dc74`**. By corpus: C1 = 10, C2 = 18, C3 = 3, C4 = 1, C5 = 4,
C6 = 1, C7 = 2, C? = 3.

> **Flagged discrepancy, not resolved here.** `03_EXPERIMENTS.md` `X46` and `cc0a377` both describe
> arm A as **`FAB_GROW=0 FAB_N0=3` (~6 experts)** and assign it the seed values 2.047 / 2.315 /
> 1.989 — which are exactly rows 27–29, tagged `nogrow_*`. But `longrun.sh:255` defines the arm
> `nogrow` as **`FAB_GROW=0 FAB_N0=1024`**, and `X52` repeats that definition. The three rows'
> `held_out` values are identical in both accounts, so **nothing in this table changes either way**;
> what is unresolved is which `FAB_N0` those three runs actually used. Recorded, not guessed. It
> matters to §3's "growth OFF, 6 → 2048" axis, and it should be settled from the run's own config
> banner before that axis is quoted again.

---

# §2. THE NOISE FLOOR — read this before any comparison table

This section is placed **before** the comparison tables deliberately. Every difference in §3–§9
must be read against it.

## 2.1 Seed spread, per arm

**Header.** Corpus: mixed (see per-row). Harness: pilot/grid. `SAVE_CKPT`: varies — and that is
itself one of the entries. n stated per line.

| what | n | held-out values | **spread** | commit | INSTR | CORPUS | status |
|---|---|---|---|---|---|---|---|
| paired pilots, `society` | 2 seeds | 2.067 / 2.007 | **0.060** | `6bd226c` | pre-both | — | Stands (`X50`) |
| paired pilots, chained society | 2 seeds | 2.101 / 2.275 | **0.174** | `6bd226c` | pre-both | — | Stands (`X50`) |
| one nominally identical arm, four runs | 4 runs | 2.023 / 2.132 / 3.054 / 3.250 | **1.227** | `33a9299` | mid | C1 | Stands; **is `INV-35`** (`X33`). Word quality swings **43%–89%** across the same four |
| same seed, same code, `SAVE_CKPT` toggled | 2 runs | 3.694 / 2.100 | **1.594** | `5f4f117` | pre-fix | — | **DEGRADED — `INV-12`.** The *difference* is real; the *accumulation* attribution is not (~125 centroid nudges against ~240,650 training steps = 0.05%). It stands as evidence of **chaotic sensitivity** (`O09`) |
| **arm D** (`seedfloor_*`, rows 24–26) | **3 seeds** | 4.327 / 3.572 / 2.253 | **2.074** | `451459d` | **post** | C2 | Stands (`X52`) |
| **arm A** (`nogrow_*`, rows 27–29) | **3 seeds** | 2.047 / 2.315 / 1.989 | **0.326** | `451459d` | **post** | C2 | Stands (`X52`) |
| **arm B** (`popB_*`, rows 31/33/35) | **3 seeds** | 1.998 / 1.960 / 2.040 | **0.080** | `e9f2e58` | **post** | C2 | Stands; the arm is `INV-15` |
| **arm C** (`popC_*`, rows 32/34/36) | **3 seeds** | 2.163 / 2.127 / 1.983 | **0.180** | `e9f2e58` | **post** | C2 | Stands |
| **ramp 2048→4096** (rows 37–39) | **3 seeds** | 1.994 / 2.097 / 1.937 | **0.160** | `e9f2e58` | **post** | C2 | `INV-19` relabelled; the spread stands |
| `ep18_big` (rows 40–42) | **3 seeds** | 2.243 / 2.200 / 2.564 | **0.364** | `bf53d40` | **post** | C3 | `INV-32` on the raw values; the spread stands, and `ac79e92` attributes **all of it** to where each seed landed in the LR restart cycle |

## 2.2 σ per arm — and why a pooled σ is the wrong model

From `LITREVIEW_FINDINGS.md`, σ estimated from the range with the small-sample factor
(d₂ = 1.693 at n=3), all four arms from `cc0a377`, **same day, same instrument, post-`c76dc74`,
corpus C2**:

| arm | mean | range | **σ (est)** |
|---|---|---|---|
| A `FAB_GROW=0` fixed small | 2.117 | 0.326 | 0.193 |
| **B `FAB_GROW=0 N0=2048`** | 1.999 | 0.080 | **0.047** |
| C `FAB_GROW=1 NMAX=64` | 2.091 | 0.180 | 0.106 |
| **D `FAB_GROW=1` ramp→4096** | 3.384 | 2.074 | **1.225** |
| ramp 2048→4096 | 2.009 | 0.160 | 0.095 |

**σ ranges 26× across four arms of one experiment.** It is a property of the **arm**, not of the
instrument. **Instability tracks ramping.**

**Caveat on the σ column, stated by its own author:** range→σ at n=3 is a very noisy estimator.
*"These σ are indicative, not measured. Computing the actual sample std from the four 2x2 arms is
nearly free and should be done before anyone plans a seed budget on this table."* **Not done.**

## 2.3 Seed budget, recomputed per-arm

Same machinery as the literature review (P(A>B) = Φ(d/√2); Noether with α=0.05, β=0.2, γ=0.75),
with **per-arm** σ substituted for the review's pooled σ:

| comparison | Δ b/B | d | P(A>B) | **paired seeds needed** | review said |
|---|---|---|---|---|---|
| D (ramp 3→4096) vs B (fixed 2048) | 1.385 | 1.13 | 0.788 | **≈ 12** | ≈ 9 |
| ramp 2048→4096 vs B (fixed 2048) | 0.010 | 0.09 | 0.527 | **≈ 1,450** | ≈ 80,000 |
| A (fixed small) vs B (fixed 2048) | 0.118 | 0.60 | 0.663 | ≈ 39 | — |

The growth finding is affordable to establish. The 2.009-vs-1.999 question is **55× cheaper than
the review stated and still infeasible**.

## 2.4 Determinism — what the noise is NOT

| what | evidence | commit | status |
|---|---|---|---|
| three identical-config pilots | **byte-identical** | `6bd226c` | Stands |
| `base_8ep_pilot2` vs `nogate_8ep_pilot2` (rows 15/16) | **byte-identical**, same final step 48133 | `b6952da` | Stands |
| six one-knob runs | verified | `c76dc74` | Stands |
| `equiv.sh` across commits | reproduces | `c14f876` vs `37ecb20` | Stands |
| GPU | training bit-reproducible; nondeterminism confined to **memory retrieval** | `c6f54e6` | Stands — **but the noise baseline `equiv.sh HEAD HEAD` was never established**, so the INERT verdicts built on it are not trustworthy |

So the spreads in §2.1 are **seed variance**, not run-to-run jitter. `bdce727` adds the necessary
caveat: *"reproducing a config is not the same as attributing a difference between two configs."*

**The literature review's recommended first step — pin nondeterminism, run 5× at fixed seed — is
already done and it passed. Do not spend those 5 runs.**

---

# §3. THE POPULATION 2x2 — `cc0a377`

**Header block.**

| field | value |
|---|---|
| commit | `e9f2e58` (runs) / `cc0a377` (analysis) |
| corpus | **C2**, pilot corpus, order-1 3.438–3.440 — **the same corpus as rows 15–39** |
| epochs / VMAX | 8 / 2048 |
| **n** | **3 seeds per arm, 4 arms, one knob apart — the largest properly-seeded design in the project** |
| INSTRUMENT era | **post-`c76dc74`**; pre-`E14`, pre-`E15` |
| `SAVE_CKPT` | on (`seeds`/`grid` default) — `nogrow_s2`'s checkpoint demonstrably survived |
| in `runs.csv` | arm A = rows 27–29 · arm B = 31/33/35 · arm C = 32/34/36 · arm D = rows 24–26 |

| arm | config | seeds | **mean** | **spread** | σ (est) |
|---|---|---|---|---|---|
| **A** | `FAB_GROW=0`, small ⚠ | 2.047 2.315 1.989 | 2.117 | 0.326 | 0.193 |
| **B** | `FAB_GROW=0 FAB_N0=2048` | 1.998 1.960 2.040 | **1.999** | **0.080** | 0.047 |
| **C** | `FAB_GROW=1 FAB_NMAX=64` | 2.163 2.127 1.983 | 2.091 | 0.180 | 0.106 |
| **D** | `FAB_GROW=1 FAB_NMAX=4096` | 4.327 3.572 2.253 | 3.384 | 2.074 | 1.225 |

⚠ arm A's `FAB_N0` is the flagged discrepancy under §1 (3 per `cc0a377`/`X46`, 1024 per
`longrun.sh:255`/`X52`). The **values** are not in dispute.

**Read along the axes** (`cc0a377`'s own reading):

| axis | movement | reading |
|---|---|---|
| growth OFF, small → 2048 | 2.117 → 1.999 | a large population is **fine** |
| growth ON, 64 → 4096 | 2.091 → 3.384 | a large population is **fatal** |
| at 4096, growth OFF → ON | 1.999 → 3.384 | **the entire effect** |

**Fabric contribution per arm:** B **+0.225 / +0.293 / +0.106** · C **+0.022 / +0.001 / −0.006**
(64 experts contribute nothing) · D seed0 **+6.183**, *"meaningless... only large because the base
model it is compensating for reads 10.338"*.

## STATUS

**B is the best arm on record — and `a5cc7ea` established that B ran with no culling at all.**

**`INV-15` — DEGRADED + NOT REPRODUCIBLE AT HEAD.** `s.born` was written only by `grow()`, so the
initial `FAB_N0` experts had no birthday and read as age 0 forever; `soft_cull` skips anything
inside `FAB_GRACE`. At `FAB_N0=2048` that is the **entire population**. Measured directly on the
same config and seed: **before 0 culls, after 6 culls, population 24 → 8**. The number stands *as
measured*, but it measures a population **under no selection**, and the fix is now in.
**Re-run arm B, or pin the reproducing config, before comparing anything to it.**

**Two things `INV-15` does not touch:**

1. **The structure of the 2x2 — the interaction, not either term — is the most durable
   architectural finding in the record.** All four arms sat under the same defect.
2. **`f8599b7` records that HEAD's fabric defaults (`FAB_GROW=1`, `FAB_N0=3`, `FAB_NMAX=4096`) are
   arm D** — mean 3.384, spread 2.074 — **not arm B.** A default run today is not arm B.
   `FAB_NEW_FRAC=0.04` and `FAB_BURST=1` were added afterwards to bound the newborn fraction and
   should mitigate it; **that has never been measured at pilot scale.**

Also `08_GLOSSARY` §1.4: `FAB_GRACE` changed **units** at `9146136` (3000 steps → 48 selections),
so any grace figure in a pre-08-15 message is in steps.

---

# §4. VMAX × EPOCHS 2x2 — `0279709` · **NOT ATTRIBUTABLE**

**Header block.** Commit `0279709` (analysis) / rows 1, 3 (VMAX=4096) and 2, 4 (VMAX=8192) in
`runs.csv`. Corpus **C1**. **n = 1 per cell, 4 cells.** INSTRUMENT era **mid** (pre-`c76dc74`) and,
decisively, **pre-`0f96784`/`79dac6c` (`E10`)**.

| | EPOCHS=8 | EPOCHS=18 |
|---|---|---|
| **VMAX=4096** | 2.140 (0% dead) | 3.250 (0% dead) |
| **VMAX=8192** | 3.561 (41% dead) | **4.383 (0% dead)** |

**`INV-31` — UNATTRIBUTABLE, including the cell that was declared "the clean one".**

`FROZEN = torch.randn(VMAX, D)` sat at **module scope** and drew `VMAX*D` numbers from the global
generator **before anything else was built**, so **changing `VMAX` re-rolled every weight in the
system** — verified directly on `enc.weight_ih` and the fabric centroids, **neither of which is
VMAX-shaped**. *"Three runs 'differing only in VMAX' were three different random initialisations of
the whole system."*

For scale: the VMAX field spans 2.132–3.989 = **1.857**, and a **0.05%** perturbation once produced
**1.594** (§2.1). *"The non-monotonic ordering needs no further explanation."*

**What survives from this 2x2:** the **falsification of the dead-row hypothesis** — `vmax8k@18ep`
filled its vocabulary completely (8192/8192, 0% never minted) and is the **worst** of the four.
That is not an attribution claim, and it is independently confirmed in §5.

---

# §5. THE DEAD-ROW SERIES — **UNCONTROLLED, NOT ESTABLISHED**

## 5.1 The series as it was quoted

**Header block.** Three rows run for **three different reasons** and compared after the fact on one
column of the `[vocab]` line. **n=1 each. Different commits, different arms, different corpora.**

| dead rows | held-out | tag | commit | INSTR | CORPUS |
|---|---|---|---|---|---|
| 0% | ~2.2 | `base_8ep_pilot2` (2.239) | `1a113f5` | mid | **C2** |
| 41% | 3.561 | `vmax8k_8ep` | `a21a721` | mid | **C1** |
| 75% | 6.114 | `frozen_8ep_75pct_dead` | `1a113f5` | mid | **C5** |

**`INV-34` — UNCONTROLLED → NOT ESTABLISHED.** *"I have been repeating it as though it were."*

Three independent reasons it does not stand:

1. **The corpora differ** — C2, C1 and C5. `held_out` is not comparable across them (§0.3).
2. **The arms differ in far more than their dead fraction**, and both the 41% and 75% arms are
   **`INV-42` VOID as named** — six arms were configured to *guarantee* dead rows.
3. **`vmax8k@18ep` filled its vocabulary completely and is the worst run of the four** (§4).

## 5.2 The first CONTROLLED test — `LOSS_MASK_DEAD`, `e9f2e58`

**Header block.** Same seed, same config, **one knob**, three arms, on a configuration with
**86.7% of the width never minted**. **n=1 per arm, with per-window SEs.** Post-`c76dc74`.
Not in `runs.csv`.

| arm | held-out | SE |
|---|---|---|
| unmasked | 4.746 | ±0.043 |
| masked at the loss only | **6.100** | ±0.074 |
| masked everywhere | 4.686 | ±0.034 |

**Controlled effect: +0.060 against a combined SE of 0.055 = 1.1σ.** *"A hint, not a finding."*

Two things worth keeping:

- **Masking at the loss only is WORSE than not masking** — the model is never taught to push the
  dead rows down while every eval path still scores it with them in the denominator. A placement
  error, not a magnitude error.
- The knob is **left off by default deliberately**, *"because it changes every number, and it
  should be adopted as a measured arm rather than assumed"* — so it is a knob with a controlled
  result and **no adoption**.

**The monotone story is not established.** `X47` is the entry that converted `INV-34` from a claim
into a retraction.

---

# §6. LEARNING RATE — the one effect far outside seed spread

## 6.1 Cosine vs no schedule — `c33f078`

**Header block.** Paired pilots at `1593c70`, **both pure defaults**, same corpus, same seed
pairing. **n=1 each, paired.** INSTRUMENT era **pre-both**. Not in `runs.csv`.

| arm | held-out | last two thirds | vs order-1 | generated text |
|---|---|---|---|---|
| `LR_SCHED=cosine` | **2.101** | −0.007 | +1.337 | English |
| `LR_SCHED=none` | **4.193** | +1.668 (ends at 5.16) | — | noise |

Constant LR **oscillates between 3.4 and 7.8 for the whole run**; the schedule settles to a flat
3.7–3.8 plateau.

**STATUS: STANDS.** *"The one architecture-independent effect in the record that is far outside
seed spread."* `6bd226c` re-affirms it explicitly at n=2 seeds. Context (`E6`): before `1593c70`
there was **no LR schedule at all** — `lr=2e-3` constant, no warmup, no decay, for **48,000 steps**,
across **all 17 pilots**, on every architecture. *"Every architecture comparison made before this
was measured through a degrading optimiser."*

**Not part of this result:** the same commit's *"SPECIALIZATION 0.132, the highest recorded, and
emergent"* and *"the only arm whose curve is flat, −0.007"* — **`INV-35`/`O12` VOID**, both
withdrawn by their own author at seed 1 (0.009 and +0.298).

## 6.2 The rest of the LR field

| what | result | n | commit | INSTR | status |
|---|---|---|---|---|---|
| `LR_EPOCHS` — horizon vs run length | LR ratio E8:E18 = **1.4× @20k, 7.6× @40k, 11.0× @44k**. At step 44000 the 8-epoch run was at **5% of peak**, the 18-epoch run at **56%** | n=1 pair + exact verification (19 sample points, 0 mismatches) | `9fabba4` | mid | **Mechanism stands.** Killed `INV-30`: *"'8 epochs beat 18' and 'a low LR beat a high one' were the same observation"* |
| `LR_RESTARTS` | **12 extra epochs at the floor bought 0.009 b/B** (rows 7 vs 6). First cycle identical under both, so an 8-epoch run is unchanged | n=1 | `c341921` | mid | **Stands as an exact schedule property.** `fec2285` then fixed a real regression: `1.0 % 1.0 == 0.0` sent the rate **back to PEAK on the final steps of every 8-epoch run** — re-verified at max\|restarts − hold\| = **0.000e+00** |
| `LR_RESTARTS=0` arm | 3.054 vs 2.132 with restarts ON — **opposite of the prediction** | **n=1, and that is the finding** | `e200178` | mid | **VOID — `INV-35`.** The arm's own four runs then spread **1.227** |
| Late restart at 100% of peak | Real restart at step **201925**: 1.00e-04 → 2.00e-03, a **20× jump**. Held-out curve after it swings **1.5 b/B and never resettles** | **n=3** | `bf53d40`/`ac79e92` | post | **Mechanism stands**; the held-out values are `INV-32` (§10.1) |
| `LR_DECAY` | peaks **100/100/100%** at 0 · **100/88/64%** at 0.5 · **100/76/29%** at 1.0 | n=1, schedule arithmetic over three cycles | `91fd815` | post | **Stands as a schedule property.** **Never run end-to-end as an arm** — no `runs.csv` row carries a non-zero `LR_DECAY` |

---

# §7. COMPONENT CONTRIBUTIONS

## 7.1 FABRIC — knockout vs retrained ablation

**Header block.** English, 120 kB, everything else identical. **n=1 per arm, both times.**
INSTRUMENT era **pre-both**. Corpus **C7** for the knockout pair (rows 12–13).

| measurement | kind | numbers | commit | status |
|---|---|---|---|---|
| `FABRIC=0` vs `FABRIC=1` | **eval-time KNOCKOUT** | 3.543 vs 3.441; *"fabric contributes **+0.709** b/B (3.905 → 3.196), four times what the memory contributes"* | `7a42f90` | **VOID — `INV-36`** |
| `nofabric` as a retrained arm | **RETRAINED ABLATION** | **3.089 vs 3.090** — no bits/byte at all | `e60b8e0` | The correction |

**`INV-36` — VOID.** *"Using the knockout number (+0.709) to justify defaulting FABRIC ON was
exactly that mistake."* The claim was retracted from `rerun.sh`'s header at `9d90416`.

**The fallback justification offered at the time — coherence 0.75 vs 0.50 — is `INV-20`**, a
**four-sample mean with SE 0.25** where every value landed on 0.25/0.50/0.75/1.00. **The default
was justified twice and both justifications are void.**

The commit's own caveat, worth keeping even though the number is dead: at those settings the router
HALTs 90% and mean routed depth is 0.10 of 4, *"so +0.709 is the population being PRESENT, not the
routing working"* — and **that HALT figure is itself `INV-40`** (a report-time probe of a path the
run did not use).

**The one fabric contribution measured post-`c76dc74`:** §3's per-arm figures — B +0.225/+0.293/
+0.106, C +0.022/+0.001/−0.006, D seed0 a meaningless +6.183 — and §7.3's **+0.373 with six
experts**, the largest in the record, from the smallest population.

## 7.2 MEMORY — every figure is unattributable

**Header block.** Sources and eras differ per line; all n=1.

| reading | value | commit | INSTR | status |
|---|---|---|---|---|
| "memory-native-and-useful is already proven" | **+2.5 b/B** | `0075807` (07-22) | pre-both | From **~4-min underfit runs**, and the same commit says so |
| at 5× steps | **+2.1** | `f5303d6` (07-22) | pre-both | Held at 5× steps — *"real, not artifacts"* at the time |
| unconditional blend fixed | −0.168 → **−0.146** | `0b08b74` (07-25) | pre-both | *"a partial fix, not a solved problem"* |
| global 200k slots | **−0.097** | `242e021` (07-24) | pre-both | Already **net-negative** with the global store |
| 32 owners × 64 (partitioned) | **−0.652** | `242e021` | pre-both | **The partition costs 0.555 b/B** |
| "memory contributes +0.698" | +0.698 | various | pre-both | **VOID — `INV-23`** |
| in the one continual run | **−0.111** | `a9d7258` (08-14) | post | And **deleting a live domain's entries improved both it and the others** |

**Three invalidations stack on all of it:**

- **`INV-06`** — `MEM_PER_EXPERT` read `_i(...,1)` against a comment saying DEFAULT OFF, so
  **every run in this project used the partitioned store**, the one measured at −0.555. *"The
  decision recorded here was never the decision that ran."*
- **`INV-23`** — `mem.ctx` was queried in a segmentation it was not written in: **82.3%** of
  stored contexts stopped matching after **one** growth step, where a pilot does about sixteen.
- **`INV-24`** — `mem.read()` was called only from eval-only paths, so `use` stayed 0 and `last`
  was never written on the global store. **Every path evicted by write order whatever `EVICT`
  said.** This is also the mechanism behind the vanished English domain in §8.

**Every "memory contributes X" figure in this project is downstream of all three.** The editable
external memory is the project's original thesis and there is no trustworthy number for it.

## 7.3 The one continual-learning run — component breakdown 🅒

**Header block.** `continual_eng_py`, row 30. Commit `b92f358` (run) / `a9d7258` (record). Corpus
**C4** = English + Python. **n=1. No log** (`INV-43`). Post-`c76dc74`, pre-`E14`/`E15`.

| component | contribution | note |
|---|---|---|
| **fabric** | **+0.373 b/B with SIX experts** | The **largest fabric contribution in the record, from the smallest population** — *"while the ramp elsewhere tries to build 4096"* |
| **memory** | **−0.111** | Net negative. **Every English memory entry was EVICTED** during the Python phases; the faded-process unlearn test skipped itself with **0 entries left** |
| weights | carried the retention | By elimination — English held while its memory was gone |

**🅒 Anchor correction (§0.5).** `py 2.276 ± 0.086` has been read against a web-text anchor of
1.0–1.2 b/B. **The correct code anchor is GPT-2-small at 1.7912 b/B on GitHub.** Against that, the
Python result is **0.48 b/B** from a reference model rather than the ~1.1 the web-text anchor
implies. Combined held-out **2.243** is a mixed eng+py stream and sits between the two reference
scales. **This does not make it a good number — it makes the previous reading of it too harsh.**

---

# §8. CONTINUAL LEARNING — the target, n=1

**Header block.** As §7.3. Cross-reference `06_CONTINUAL_LEARNING.md`; this is the table only.

Configuration: RESUME from `nogrow_s2` (English, held-out **1.989**, row 29) + Python from
the-stack, under `PHASE_SCHED [[0],[0],[1],[1]]` — English **absent for the second half of every
epoch, eight times**, and the run **ending on a Python-only phase**.

| reading | value | verdict | status |
|---|---|---|---|
| `eng` across the run boundary | 1.998 @ step 48157 → **2.050**, **+0.052 ± 0.075** | **HELD** | **DEGRADED — `INV-25`**: `holdout_bpb` calls `_eval_logits`, which **does not consult memory**. This is a **weights-only** retention figure, though *"the ONLY number that spans the run boundary"* implies otherwise |
| `py` 🅒 | **2.276 ± 0.086** | **NEW** | Read against **1.7912** (GitHub), not 1.09–1.11 (§0.5) |
| combined held-out | **2.243**, beating order-1 (3.644) by **+1.402** | — | Own-anchor figure; corpus C4 |
| learning curve ACTIVE | **+0.116 b/B per 2000 steps** | — | *"About four times faster than it forgets"* |
| learning curve ABSENT | **−0.029 b/B per 2000 steps** | — | **First data this column has ever carried** |
| English trajectory | worst **2.19** during an early absence, back to **2.00** by the end | — | **Recovers rather than ratcheting** |

**`INV-43` — PROVENANCE DEGRADED.** `pilot-add` never created `$OUT`, so `tee` wrote to a closed
pipe. **Hours of GPU, a valid checkpoint, no record.** The `runs.csv` numbers are **hand-transcribed
from a terminal copy**. `holdout.py` can reconstruct ACROSS THE RUN BOUNDARY from the checkpoint if
it survives — **not attempted here.**

**The single most important run in the project is the one with the weakest provenance, and it is
n=1 with no seed replication at all.**

---

# §9. THE 18-ARM GRID AND THE DOMAIN METRICS

## 9.1 The 18-arm grid — `ffd39b8`

**Header block.** `MODEL=gru LAYERS=1 D_MODEL=768 WIN=256 BATCH_W=16 VMAX=2048 GROW_EVERY=100
GROW_BURST=12 SEG_MIN=8000 SEG_MAX=20000 ENC_WARMUP=2000 MEM_CAP=200000`, 4 MB/epoch × 8 epochs.
**n=1 per arm, 18 arms.** 18/18 trained; **4 lost their report to a crash**. INSTRUMENT era
**pre-both**. Not in `runs.csv`.

| arm | since-min | held-out | vs order-1 | specialization |
|---|---|---|---|---|
| `society` | +0.605 | **2.058** | +1.381 | 0.126 |
| `nofabric` | +0.670 | **2.118** | +1.320 | n/a |
| `divw` | +2.151 | 2.324 | +1.115 | 0.000 |
| `base` | +2.287 | 3.124 | +0.314 | 0.000 |
| `weights` | +2.434 | 3.989 | n/a | 0.142 |
| `kitchen` | +2.637 | 3.221 | +0.217 | 0.105 |

**STATUS: the ranking is `INV-35` — VOID.** n=1 per arm against a seed spread later measured at
1.227; **the 0.060 between `society` and `nofabric` is far inside it**. The `divw` row is
additionally **`INV-44` VOID** — the flag did nothing and the run is a byte-identical duplicate of
`DIV_W=0`.

**What survives:**

1. **The qualitative finding** — *"every chaining arm is worse than FABRIC=0"* — corroborated by
   the **generated text** rather than by a decimal. Society and nofabric produce English; every
   chaining arm produces degraded noise.
2. **The mechanism, measured across all 18 arms and unmoved by any intervention:** depth **1.00 of
   4** and HALT mass **0.0000** in every arm; **H(hop1|hop0) = 0.007 to 0.058 bits everywhere**.
   `softroute`, `curric`, `stateq`, `chainsup` all leave it there. *"One decision, then a rail."*
   `CHAIN_ROUTE=soc` later moved it to **0.533** (`7b18214`) — the one intervention that did.
3. **The ramp-latch negative, pre-registered and clean:** churn fell from ~10062 grown / 5969 culled
   to **~4210 / 1205**, latched in every arm, population settling ~3000 instead of pinned at the
   cap — and **divergence got WORSE** (+1.438 → +2.287 for base). *"The cull-refill cycle was real
   and was not the cause."*

## 9.2 Domain metrics across the campaign — **DIAGNOSTICS, NOT TARGETS**

**Read `9d90416` before this table.** Domain counts, purity, silhouette, V-measure and
specialization are **DIAGNOSTICS, NOT TARGETS** — and the record shows **steering by them consumed
weeks**. Two invalidations sit under almost the whole campaign: **`INV-04`** (`MANAGE_MERGE=0.12`
overrode the intended 0.28 for the project's whole life) and **`INV-05`** (`MANAGE_EVERY=500`
exceeded the run, so merge/cull/fold executed **zero** or **one** times). **The consolidation half
of the mechanism was switched off while it was being tuned.**

**Header block.** All CPU or small-GPU, 60–80 kB unless stated, 4 seeded corpora, **n=1 per arm**
except where marked. INSTRUMENT era **pre-both** throughout. **Also `E4`**: the signature encoder
was reading **42% of the stream** until `98e3301`.

| experiment | arm | live domains | purity | completeness | **V** | recurrence | commit | status |
|---|---|---|---|---|---|---|---|---|
| `X14` configs | A | 142 | — | — | **0.42** | — | `6397041` | **VOID — `INV-37`** (ranking) + **`INV-05`** (the 142 count specifically) |
| | B | 53 | — | — | 0.38 | — | | |
| | D | 77 | — | — | 0.12 | — | | C and D changed **two** things — self-flagged, *"neither can be attributed"* |
| | C | 1 | — | — | 0.00 | — | | |
| `X15` encoder floor | constants | 50 | — | — | 0.42 | 34% | `510c695` | **Superseded, then partly withdrawn** by `X17`. The *discovery* that `manage()` never ran stands = `INV-05` |
| | radius+fold | 36 | — | — | 0.40 | 61% | | |
| | floor K=8 | 23 | — | — | 0.49 | 48% | | |
| | K=8+radius+fold | 16 | — | — | 0.50 | **88%** | | |
| | K=4+radius+fold | 6 | — | — | **0.54** | 83% | | |
| `X16` MANAGE_MERGE (GPU, 4 MB) | 0.12 | **25** | 0.97 | 0.60 | 0.72 | — | `13e787a` | **The defect stands = `INV-04`.** The *threshold choice* does not — 0.45 maximised V against the **seeded** corpora, the wrong target; HEAD is **0.28** |
| | 0.45 | **4** | 0.97 | 0.89 | **0.89** | all | | |
| `X16` CPU falsification | 0.45 | 7 | 0.96 | — | — | — | `13e787a` | **The falsification series is the durable part**: *"4 domains"* is reachable two ways and **the count alone cannot tell them apart** |
| | 0.60 | 6 | 0.88 | — | — | — | | |
| | 0.80 | **4** | **0.71** | — | — | — | | *"COUNTERFEIT 4"* |
| | 1.00 | 5 | 0.60 | — | — | — | | |
| `X17` segment length | 2.5 win/seg | 15 | 0.54 | — | **0.19** | — | `3f44ce3` | **Stands as a two-sided falsification.** V is monotone in segment length while the live count barely moves. Geometry probe on the real encoder: silhouette **+0.24**, 1-NN corpus accuracy **0.984**, d_between/d_within **1.71** — *"the encoder separates the kinds and is not the bottleneck"* |
| | 9.8 | 16 | 0.87 | — | 0.50 | — | | |
| | 39.0 | 12 | 0.88 | — | **0.68** | — | | |
| `X18` SEG_CONTIG | random offset | **31** | — | — | — | — | `98f19fa` | **Stands.** *"More than half the domains were seek artefacts. 13 is the number that is about English"* |
| | contiguous | **13** | — | — | — | — | | |
| `X19` ENC_VREG | 0 | 2 | — | — | — | — | `c1aadda` | **Stands** — the diagnosis is mechanistic (encoder loss **3.83/3.78** against **ln(48) = 3.871**, exactly a constant vector), not statistical |
| | 1.0 | 5 | — | — | — | — | | |
| | **5.0** | **17** | — | — | — | — | | Defaulted ON at 5.0 |
| | 5.0+CREG | 24 | — | — | — | — | | |
| | `DOMAINS=eng`, collapsed | **1** | **1.00** | — | **1.00** | — | | Silhouette **+0.95**, *"1/1 GENUINE"* — **a permanent warning about this report battery**: *"a partition of one is perfect"* |

**Purity is the retracted one.** *"Domain assembly works, purity 0.54 → 0.96"* is **`INV-16` VOID —
explicitly retracted** (`5e02cfc`): **purity rises monotonically with fragmentation.** Measured
elsewhere: purity **1.00 at 1431 clusters with completeness 0.18**. The assembler was producing
**one domain per splice segment** (96 domains against 89–96 segments). Separately, **the
completeness formula was homogeneity** until `b1fe6ed`.

## 9.3 The two experiments in the campaign that shipped with a null — and both stand

**These are the methodological high points of the project.**

| experiment | condition | own | comparator | null | **excess** | verdict | status |
|---|---|---|---|---|---|---|---|
| `X20` informativeness | 4 corpora | 4.167 | foreign 4.527 (+0.360) | +0.265 | **+0.095** | **informative** | **Stands** |
| | English alone | 3.635 | foreign 3.920 (+0.286) | **+0.341** | **−0.055** | **NOT** | *"The raw English gap of +0.286 looks convincing and is below chance"* |
| `X21` error bar on that null (**n=2 seeds**) | two 4 MB English runs | +0.010 | +0.013 | cutoff 0.010 | **+0.000**, spread ±0.020 | printed **opposite conclusions** | **Stands.** *"The threshold was inside its own noise band... the disagreement was never real"* |
| `X22` domain prior | eng only, 31 domains | 3.503 | global 3.539 / random 3.524 | — | own−global **+0.016**, own−random **+0.000** | label does **not** predict | **Stands** |
| | 4 corpora, 6 domains | 3.912 | global 3.970 / random 3.982 | — | **+0.050 / +0.063** | label predicts | *"Without the random-domain arm that would have read as a success"* |
| `X23` stability (**n=2 seeds**) | NMI A vs B | **0.757** | seeded corpora A 0.655 / B 0.760 | shuffled floor **0.002** [0.000–0.005 / 20 draws] | — | **the discovery signature** | **Stands at the scale run** (60 kB, D=64, 3 domains, CPU). **Never repeated at pilot scale** |

**`X21`'s negative, stated plainly:** with 64–68 well-formed, recurring, boundary-detecting English
domains, **the partition carries no predictive information beyond a random partition of the same
shape** — consistent with the code, since `did` is consumed only by `mem.src`, `dom_exp` and the
clustering report, and **nothing in the prediction path reads it**.

**The pattern across §9.** *"Every experiment in this file that carried a pre-specified control or
permutation null still stands. Almost every one that did not, does not."*

---

# §10. THE ANCHORS

## 10.1 What the anchors are, and the one rule

Per `08_GLOSSARY` §Measurement — fitted on **TRAIN**, scored on the **SAME held-out text**, in the
same units:

| anchor | definition | in `runs.csv`? |
|---|---|---|
| **uniform** | log2(vocab size) scaled to bytes — what assigning equal probability to every token costs. **A model above it is worse than guessing.** Tracks the **vocabulary**, not the corpus | yes, `uniform` |
| **order-0** | add-k-smoothed unigram histogram | no |
| **order-1** | add-k-smoothed bigram table. *"If the model does not clearly beat ORDER-1, none of the architecture is doing work that a two-line frequency table could not"* | yes, `order1` |
| **model** | the held-out figure | yes, `held_out` |

**Two history items that change what the column means (`08_GLOSSARY` §1.12):**

- `aac17f7` (07-28) introduced the anchors and **initially fitted the order-1 baseline on the
  held-out text it was scoring** — *"a model that has seen the answers"*, an unfairly **strong**
  anchor (it reported order-1 at 2.627 against a corrected 3.568). Now fitted on TRAIN, scored out
  of sample. **Pre-fix "beats order-1 by X" figures understate the model.**
- **The corpus was re-fetched and order-1 moved 3.440 → 3.747** (`ac79e92`).

**THE RULE: always quote a held-out figure against its OWN run's order-1.** The anchors *"are not
comparable across corpora"* and *"do NOT measure progress between architectures"* — they measure
**whether a b/B number is worth anything at all**. **DIAGNOSTIC, but a mandatory one.**

**The worked example** — `ep18_big` vs arm B, the reason `INV-32` exists:

| | raw held-out | own order-1 | **Δ order-1** |
|---|---|---|---|
| `ep18_big` (rows 40–42, corpus **C3**) | 2.243 / 2.200 / 2.564 → mean 2.336 | 3.747 | **1.411** |
| arm B (rows 31/33/35, corpus **C2**) | 1.998 / 1.960 / 2.040 → mean 1.999 | 3.438–3.440 | **1.441** |

Raw, 18 epochs look **0.337 worse**. Against each run's own anchor they are **0.030 apart** —
*"18 epochs bought nothing, and did not cost the 0.34 the raw numbers suggest either."* Both
arms are n=3; 0.030 is well inside arm B's own spread of 0.080.

## 10.2 The reference scale — and the correction for code 🅒

**`08_GLOSSARY` offers *"GPT-2-small sits near 1.0–1.2 b/B on comparable text."* That is
English web text only.** Corrected per `LITREVIEW_FINDINGS.md` §4:

| reference corpus | GPT-2-small b/B | what it anchors here |
|---|---|---|
| Pile-CC | 1.0878 | the `DOMAINS=eng` rows — the correct anchor for **41 of 42 rows** |
| OpenWebText2 | 1.1111 | same |
| Pile aggregate | 1.2253 | mixed streams |
| **GitHub (code)** | **1.7912** | **`continual_eng_py`'s `py 2.276`**, and the code portion of the four-corpora campaign (§9) |

**There is no single scale marker across text and code.** Every code result in this repo has been
read against a web-text anchor and has therefore **looked worse than it was**.

**Caveat on the caveat:** these four figures come from a literature review whose sources
`LITREVIEW_FINDINGS.md` was **unable to open** (`WebFetch` blocked for every paper host). They are
recorded as *"the review's word"* and are not independently verified here. They are still a better
anchor for code than 1.09.

## 10.3 Where every row sits against its own anchor

Sorted by `Δ order-1`, best first. **This is the only cross-corpus-comparable ranking in the file
— and it is still not an arm ranking**, because `INV-35` voids every single-run comparison and the
rows differ in commit, era, arm and epoch count.

| Δ order-1 | rows |
|---|---|
| **+1.40 to +1.55** | `rampfrom2048_s2` +1.503 · `popB_n2048_s1` +1.479 · `popC_nmax64_s2` +1.457 · `nogrow_s2` +1.451 · `rampfrom2048_s0` +1.446 · `popB_n2048_s0` +1.442 · `popB_n2048_s2` +1.400 · `ep18_big_s1` +1.547 · `ep18_big_s0` +1.504 |
| **+1.15 to +1.40** | `nogrow_s0` +1.393 · `frozen_nr_8ep_clean` +1.350 · `rampfrom2048_s1` +1.342 · `vmax4k_18ep_lr8` +1.329 · `popC_nmax64_s1` +1.312 · `popC_nmax64_s0` +1.277 · `vmax4k_18ep_guard` +1.221 · `vmax4k_8ep` +1.212 · `base_8ep_pilot2` / `nogate_8ep_pilot2` +1.199 · `seedfloor_s2` +1.187 · `ep18_big_s2` +1.183 · `nogrow_s1` +1.124 · `continual_eng_py` +1.401 🅒 |
| **0 to +0.31** | `vmax4k_18ep_norestart` +0.297 · `base_18ep_guard` +0.199 · `vmax4k_18ep_oldLR` +0.102 · `fabric_on` +0.054 |
| **NEGATIVE — loses to a two-line bigram table** | `fabric_off` −0.048 · `seedfloor_s1` −0.133 · `vmax8k_30ep_lr8` −0.138 · `vmax8k_18ep_lr8` −0.147 · `vmax8k_8ep` −0.240 · `base_8ep_gate_starved` −0.284 · `vmax8k_18ep_guard` −0.759 · `frozen_8ep_clean` −0.839 · `seedfloor_s0` −0.887 · `vmax8k_18ep_oldLR` −1.155 · `frozen512_18ep_oldLR` −2.015 · `frozen_8ep_75pct_dead` −2.589 |
| **no anchor** | `base_8ep_707f1af` · `frozen_8ep_707f1af` · `frozen_nr_8ep_707f1af` |

**Twelve of 42 rows lose to order-1.** Two of them (`seedfloor_s0`, `seedfloor_s1`) are the **HEAD
default configuration** at two of three seeds (§3).

---

# §11. WHAT SURVIVES

Short, and it should be. This is `05_ERRORS.md`'s list, unchanged, with this file's table
references attached.

| # | what | evidence | where |
|---|---|---|---|
| 1 | **Determinism given (config, commit, seed) on CPU.** On GPU, training is bit-reproducible and nondeterminism is confined to **memory retrieval** — though the `equiv.sh HEAD HEAD` noise baseline was **never established**, so the INERT verdicts built on it are not trustworthy | `6bd226c`, `b6952da`, `c76dc74`, `c6f54e6` | §2.4 |
| 2 | **The LR schedule effect.** cosine **2.101** vs none **4.193**, constant LR oscillating 3.4–7.8 and ending at 5.16. *"The one architecture-independent effect far outside seed spread"* | `c33f078`, re-affirmed `6bd226c` | §6.1 |
| 3 | **The retok-on-unchanged-vocabulary cost is real** — even though its **magnitude** is `INV-10` (two knobs moved, not one) | `046fd81`, `79dac6c` | rows 18–19 |
| 4 | **Arm B's spread of 0.080 across three seeds** — *"the first configuration stable enough for a 0.1 b/B difference between two arms to mean anything"* — subject to `INV-15`, which explains **why** it is stable: no selection was running | `cc0a377`, `a5cc7ea` | §2.2, §3 |
| 5 | **The code defects themselves.** Facts about the source, independently checkable, and they are most of `05_ERRORS.md` | throughout | — |

To which this file adds three of its own, all structural rather than numerical:

6. **The interaction structure of the 2x2** — that ramping to a large population, not the
   population size, is what destroys the base model. All four arms sat under the same defect, so
   the *comparison* survives `INV-15` even though the *level* does not. §3.
7. **Every experiment that shipped with a pre-specified null still stands** (`X20`, `X21`, `X22`,
   `X23`); almost every one that did not, does not. §9.3.
8. **`Δ order-1` is the only column in `runs.csv` that is comparable across corpora**, and it is
   reproducible from the CSV to three decimals against `ac79e92`'s published pair. §0.3, §10.3.

---

# §12. WHAT CAN I ACTUALLY CONCLUDE

The honest accounting. Stated as bluntly as the record deserves.

## 12.1 Concludable

1. **The optimiser was the problem, and fixing it is the largest reproducible win in the file.**
   4.193 → 2.101 is far outside every measured seed spread including the 1.227 one. Everything
   measured before `1593c70` was measured through a degrading optimiser. (§6.1)
2. **Ramping to a large expert population destroys the base model; holding one from step 0 does
   not.** The interaction survives `INV-15` because all four arms shared the defect, and it is
   supported by a mechanism (the ramp injects ~4000 mutated clones into the path between the base
   representation and the loss over ~600 steps, with HALT mass 0.0000 so the base head has no direct
   path out). **This is the only architectural finding in the branch with 3 seeds per cell.** (§3)
3. **Seed variance is a property of the arm.** 26× across four arms of one experiment, and it
   **tracks ramping**. Whether the *variance* difference or the *mean* difference is the real
   phenomenon **has never been asked**, and the variance is the larger effect. (§2.2)
4. **The system is deterministic given (config, commit, seed) on CPU.** So the spread is seed
   variance, not jitter, and n seeds of one arm is the only way to see it. (§2.4)
5. **A partition that looks informative usually is not, and only a null can tell you.** `X20`,
   `X21` and `X22` each changed their own verdict when a null was added. (§9.3)
6. **Twelve of 42 rows lose to a two-line bigram table**, including the HEAD default at two of
   three seeds. (§10.3)

## 12.2 NOT concludable — the list is longer

| claim | why not |
|---|---|
| **Any arm ranking** | `INV-35` voids every single-run comparison in the branch; the seeded ones (§3, §2.1) all predate `E14`/`E15` |
| **Anything about VMAX** | `INV-31` — changing it re-rolled every weight in the system. Ten rows, one field, no attribution |
| **The dead-row story** | `INV-34` — the series was uncontrolled and cross-corpus; the first controlled test gives **1.1σ** |
| **Anything about memory** | `INV-06` + `INV-23` + `INV-24`. The project's original thesis has **no trustworthy number** |
| **Anything about the world model** | `INV-39` — its only full-stack reading is *"beats baseline −84.7%, latent std 0.07"*, i.e. by its own criterion it **has not learned dynamics**. Unmeasured since 2026-07-29 — **and it defaults ON**, so every post-07-29 row above carries it untested |
| **Anything about the tokenizer's contribution to divergence** | `INV-28` void as stated; `INV-29` unattributable — *"'frozen tokenizer' and 'schedule that anneals' were the same experiment"* |
| **`frozen` vs `frozen_nr`, the "largest single effect on record"** | `INV-10` — two knobs, not one |
| **`FABRIC` is worth anything** | `INV-36` — knockout +0.709 VOID; retrained is **3.089 vs 3.090**. The default was justified twice and both justifications are void (`INV-20` for the second) |
| **GRU vs transformer** | `INV-33` — the transformer has run twice, **both times as arm D**, and has **never been evaluated where the base model survives** |
| **Continual learning, beyond n=1** | One run, no log (`INV-43`), retention figure weights-only (`INV-25`), no seed replication. **Catastrophic forgetting in the literature sense has never been run** |
| **Any domain metric as a target** | `9d90416`: purity, V, silhouette, specialization and domain counts are **DIAGNOSTICS**. `INV-16` retracted the headline purity result outright |
| **That arm B is reproducible** | `a5cc7ea` — founders were immune to culling, the fix is in, **arm B as measured no longer exists at HEAD** |

## 12.3 The three things a reader should carry away

1. **`held_out` cannot be read down the master table.** Two columns govern it — INSTRUMENT and
   CORPUS — and 18 rows share one corpus **while straddling the instrument boundary**. Use
   `Δ order-1` or use nothing.
2. **The seed floor is the binding constraint on everything.** The default configuration's own
   three-seed spread is **2.074 b/B**, larger than any architectural difference in the record. Arm
   B's 0.080 is the first configuration stable enough for a 0.1 b/B difference to mean anything —
   and it is not reproducible at HEAD.
3. **A number that merely appeared in a report almost never survived.** `03_EXPERIMENTS.md`'s
   tally: of the 56 genuine experiments, **15 are INVALIDATED or UNATTRIBUTABLE** and 11 more stand
   only in part; of the 16 incidental observations — numbers that fell out of a run done for another
   reason — **14 of 16 are VOID, UNATTRIBUTABLE or RELABELLED**. The retractions are in the commit
   messages, in public, usually within days, and most were written by the person who produced the
   number. *"A number that was designed to answer a question survived about half the time; a number
   that merely appeared in a report survived about an eighth of the time."*

---

## What this file does not establish

- **No causal claim.** Every table records what was observed under the stated conditions.
- **No arm ranking**, at any n in this file.
- **Nothing re-derived.** Every era, invalidation and experiment id is cited from `01_TIMELINE.md`,
  `05_ERRORS.md` or `03_EXPERIMENTS.md`. The only arithmetic performed here is
  `Δ order-1 = order1 − held_out`, which reproduces `ac79e92`'s published pair (1.411 / 1.441)
  exactly and is shown so it can be checked.
- **One open discrepancy, flagged not resolved:** arm A's `FAB_N0` (§1, footnoted under the master
  table). It does not move any number in this file.
- **`runs/` holds nothing newer than the `equiv` pair.** Every GPU result from 2026-08-10 onward
  exists only in commit messages and `runs.csv`. There is no log behind rows 24–42 other than the
  commit text quoted here, and rows 9–13 and 30 have no log at all.
