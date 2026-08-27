# 06 — CONTINUAL LEARNING

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are tiny
> — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has reached
> 1.227 b/B (`33a9299`), larger than the gap between any two architectures ever compared here.
> Several confidently-stated findings were later retracted when the measurement turned out to be
> broken. Every entry records **what was observed under these conditions**, never **what is true**.
> Where a result was later invalidated, the invalidation is stated next to it, not in a footnote.

---

## What this file is

Continual learning without exorbitant forgetting is **the stated target**. This file is the whole of
what the record has to say about it, which is very little, and the file's first job is to make that
disproportion visible rather than to paper over it.

Dependencies: `01_TIMELINE.md` for the epoch markers `E1`–`E15`; `05_ERRORS.md` for the `INV-` list,
which is the authority on what does not stand; `04_RESULTS.md` §7.3 and §8 for the numbers, which
are quoted from there rather than recomputed; `03_EXPERIMENTS.md` §13 (`X48`, `X49`);
`08_GLOSSARY.md` for *ACROSS THE RUN BOUNDARY*, *retention*, *ACTIVE/ABSENT*.
`notes/_evidence/litreview/11_forgetting_metrics.md` and `10_replay_buffer_selection.md` for the
standard metrics this project did not use.

**Enforcement rule, applied throughout**: every number carries its commit, its n, and its instrument
era. Era key, from `01_TIMELINE` Appendix A:

| era | meaning |
|---|---|
| **pre-both** | before `5f4f117` (08-07) and `c76dc74` (08-13). The router was trained by eval passes and diagnostics were editing the run |
| **mid** | post-`5f4f117`, pre-`c76dc74` |
| **post** | post-`c76dc74`, and — where stated — still pre-`E14` (`91fd815`/`a5cc7ea`, founders immortal) and pre-`E15` (`e25d9b5`/`daf9f89`, the memory-eviction fixes) |

---

## §0. THE DISPROPORTION, stated first

`04_RESULTS.md` renders 42 rows of `runs.csv`. **One of them is a continual-learning run**
(row 30, `continual_eng_py`, commit `b92f358`, recorded at `a9d7258`, 08-14, **n=1**). The other 41
are English-only single-stream runs about the tokenizer, the vocabulary width, the learning-rate
schedule and the expert population.

`03_EXPERIMENTS.md` catalogues 56 experiments. **Two** are in its §13 (`X48`, a plumbing
verification; `X49`, the one real run). The domain-assembler campaign alone runs to ten.

`9d90416` (08-15) is explicit about why that is the wrong shape:

> *Domain counts, purity, silhouette, V-measure and CAN A DOMAIN PREDICT are labelled DIAGNOSTICS,
> NOT TARGETS, with a note that a domain count going up is not a result and that a diagnostic
> disagreeing with 1 and 2 is the diagnostic's problem.*

`DOC_PLAN.md` "WHAT THE RESEARCHER SHOULD KNOW NOW" #8 draws the operational conclusion:

> *One run bears on continual learning (`a9d7258`, n=1) against dozens on the tokenizer and the
> expert population, which are explicitly not the goal. If GPU time is scarce, replicating that one
> run across seeds buys more than any further arm.*

Two invalidations remove most of the rest of the record from consideration before it starts:

- **`INV-02`** (`E2.1`, `7a42f90`) — `FABRIC=0` in **every run before 2026-07-29**. The routed
  expert population was absent from the system being measured. **VOID — measured a different
  system.**
- **`INV-03`** (`E2.3`, `c316813` → `a5ac033`) — `PHASED=0`, shipped in commit 1 and **never once
  executed** before 07-28. Everything before that date ran on a **stationary i.i.d. splice**, which
  *"does not require continual learning at all… it is ordinary training with extra machinery"*.
  **VOID for the continual-learning claim** (the bits/byte numbers stand on their own terms).

So the window in which a continual-learning claim is even in principle available opens on
**2026-07-28**, and the instrument in that window was not fixed until **2026-08-13** (`E11`,
`c76dc74`).

---

## §1. What the target actually is

Quoted from `9d90416` (2026-08-15), which rewrote the reading order in both launchers:

> *The stated goal is the output, continual learning without exorbitant forgetting, and old
> capacities surviving. Domain counts are a diagnostic for those and I have been reporting them as
> if they were the result.*

and the ordering it installed:

> *1. THE OUTPUT (generation first — it IS the deliverable, everything else is a proxy),
> 2. CONTINUAL LEARNING WITHOUT EXORBITANT FORGETTING, 3. the machinery, only insofar as it moves
> 1 and 2.*

The audit that started the subject is `c316813` (2026-07-27), and it is worth quoting in full
because it is the clearest statement in the record of how far the measurement had drifted from the
goal:

> *AUDIT FINDING. The report has fourteen sections. Exactly one of them bears on catastrophic
> forgetting, the defining problem of continual learning: the NON-STATIONARY block behind PHASED=1.
> PHASED was 0 at the time and it had never been executed in any run of this project. Everything we have
> been tuning — purity, homogeneity, completeness, V-measure, fragmentation, silhouette — scores the
> ORGANISATION of a store, against categories we ourselves spliced in, and none of it says whether
> the system keeps what it learns.*

`efb818a` and `5e02cfc` later retracted the two headline results of that tuning campaign anyway
(`INV-37`: V against the seeded corpora is the wrong target; `INV-16`: purity rises monotonically
with fragmentation). **The weeks spent steering by the diagnostics produced no surviving finding
about the target.**

---

## §2. THE CRITICAL CAVEAT — ACROSS THE RUN BOUNDARY is WEIGHTS-ONLY

**This is the most important sentence in the file, and it applies to every retention number below.**

`ACROSS THE RUN BOUNDARY` — the section `08_GLOSSARY` marks **TARGET**, the one the project calls
*"the ONLY number that spans the run boundary"* — **cannot see the memory system at all.** The
memory is half of the architecture and it is the half built to prevent forgetting.

**Verified in the source this session, not recalled.** The call chain, at HEAD:

- `holdout_bpb()` — `self_organize.py:3864`. Its only scoring call is
  `_lg = _eval_logits(model, fab, FABRIC, _X)`.
- `_eval_logits(model, fab, FABRIC, x)` — `self_organize.py:3178`. Its entire body is
  `return fab_logits(model, fab if FABRIC else None, model.encode(x))`.
- `fab_logits(...)` — `self_organize.py:3219`. Base head, or the fabric ensemble, then `mask_dead`.
  **There is no `mem.read`, no `mem_key`, no blend on this path.**

Compare the *other* held-out estimator in the same file, `bpb_true()` — `self_organize.py:6480` —
whose signature is `bpb_true(p, use_exp=EXPERTS, use_mem=True, pin=True, use_fab=FABRIC)` and whose
body contains, explicitly:

```
if use_mem:
    dist, _cf, _, _ = mem.read(mem_key(X))
    pmem = dist.reshape(X.size(0), X.size(1), V)
    hp   = _mem_hp(dist, _cf, dim=-1).reshape(X.size(0), X.size(1), 1)
    pp   = (1 - hp) * pm + hp * pmem
```

So the project has two held-out estimators, one memory-aware and one not, and **the continual-
learning metric is the one that is not**. Established at `f8599b7` (08-15, found by an outside
reader) and carried in `05_ERRORS` as **`INV-25` — DEGRADED**.

### What the measurement does and does not include

| included | excluded |
|---|---|
| base LM weights (`model.encode`, `model.head`) | **the entire external memory** — no retrieval, no blend, no `mem.read` |
| the fabric ensemble, if `FABRIC=1`, blended at the prediction level | the memory's contribution to retention, which is the thing the architecture exists to produce |
| `halt_blend` / `mask_dead` | the world model's feedback path is present only insofar as it was baked into training |
| the *same held-out windows* every run, keyed by domain NAME with a deterministic seed (`471318c`) | — |

One further limitation on the same path, visible in the source and not previously recorded: at
`fab_logits:3232` the eval path **fabricates a zero gist** (`gist = torch.zeros(...)`) because there
is no signature at eval time. The fabric therefore routes the held-out windows *without a real
signature*, on the halt/centroid arithmetic alone. So the number is weights-plus-fabric-without-
routing-signal, not weights-plus-system. (The zero gist is also the mechanism of `E4.3`/`INV-12`; it
is now read-only, `learn_regions=False`, but it is still a placeholder rather than a measurement.)

**Consequence, stated plainly.** Every "HELD" verdict in this file is a claim about the *parametric*
component. In the one run where it matters, that is not a technicality: **every English memory entry
had been evicted** (§4), so the memory contribution to English retention at the end of that run was
not merely unmeasured — it was, by the run's own eviction report, **zero**. The weights-only number
and the system number happen to coincide there. That is a coincidence of that run, not a property of
the metric.

**The literature says this is not a variant of BWT but a different metric.** From
`notes/_evidence/litreview/11_forgetting_metrics.md`:

> *There is no weights-only version of BWT in the literature. If your evaluation path bypasses
> memory, you are not computing BWT on your system — you are computing BWT on a different, ablated
> system. That ablated number is not wrong, it just answers a question you didn't ask.*

§6 below takes up what to do about it.

---

## §3. The mechanisms that were built

| mechanism | commit | date | what it is | status at HEAD |
|---|---|---|---|---|
| `PHASED` + generated phase schedule | `a5ac033`, `c411ac7`, `a3ed1a9` | 07-28..31 | processes ENTER and FADE across `PHASES` phases; schedule **derived from NP** rather than tabulated (`a3ed1a9`), after the hard-coded 4-process table gave NP=2 a final phase that was the *least* non-stationary and never faded process 0 (`c411ac7`) | **default ON** (`_SPEC` `PHASED: ("i", 1)`); `PHASED=0` warns at startup that the run does not test continual learning |
| whole-stream retention | `c316813` | 07-27 | first fifth vs last fifth of the stream | **superseded one day later** |
| per-process retention | `a5ac033` | 07-28 | each process's earliest windows against its own latest, conditioned on the label — because under `PHASED` the first and last fifths are **disjoint corpora**, so the original was measuring which corpus is harder | live; verdicts `RETAINED` <0.10 / `DRIFTING` <0.40 / `CATASTROPHIC` |
| learning curve with ACTIVE / ABSENT columns | `01c1cd3` | 07-29 | b/B per process on the `RATE_EVERY` cadence, each marked active or absent — the sample-efficiency half | live. Found and fixed two of its own bugs: an `except Exception` that made the section vanish silently, and `nbytes()` reading `BLEN`, which is `None` mid-run under `TOK_ONLINE` |
| held-out probe keyed by domain **NAME**, deterministic seed, stored in **every checkpoint** | `471318c` | 07-31 | *"adding a domain shifts every index after it, so an index-keyed probe would silently compare `eng` against `py`"*; per-window rather than pooled, so it carries a standard error | live (`holdout_bpb`, `_save_ckpt` writes `holdout` + `holdout_step`) — **and it is the weights-only one, §2** |
| `holdout.py` | `40de03d` | 08-14 | reconstructs ACROSS THE RUN BOUNDARY from two checkpoints when the log is gone; applies the **same 2σ test** as the in-run report | live, and **verified working this session** (§7) |
| `longrun.sh add` / `pilot-add` | `471318c`, `2ba3ac1` | 07-31, 08-14 | pull a new corpus, resume with the domain appended, write to a **separate** checkpoint so the English one survives a bad addition. `2ba3ac1` added `RESUME_FROM=<dir>` because it had been hardcoded to `$OUT/pilot_$PA`, making every checkpoint from `seeds`/`grid`/`repeat` unreachable | live |
| resume safety for the CL path | `59c6cf4`, `2ba3ac1`, `c8b6991`, `dec9fb3`, `ef412e2`, `a5cc7ea`, `daf9f89` | 07-24..08-15 | `05_ERRORS` §5 in full: every one of these is a defect on the path continual learning depends on | see §5 |

**`DOC_PLAN` cites this last mechanism as `4713186`. That hash does not exist.** The commit is
`471318c` (`471318cd2ec75a5e280ef28edcd276ae40c75faf`), *"english first, then ADD — and the
measurement that makes adding an area meaningful"*, 2026-07-31. Recorded here so the citation can be
fixed rather than re-derived.

---

## §4. EVERY continual-learning measurement that exists

Eight, in date order. Only the last is a continual-learning result at pilot scale on a fixed
instrument.

### M1 — first whole-stream retention reading
**`c316813`, 2026-07-27. n=1.** Default 80 kB run.
`first fifth 4.106 → last fifth 3.873`, **forgetting +0.233 b/B, DRIFTING**.
**Era pre-both.** **VOID as a continual-learning number** — `INV-03` (the run was stationary),
`INV-02` (`FABRIC=0`), and the *metric itself* was retracted the next day by `a5ac033`: first-fifth
vs last-fifth is only meaningful when the stream is stationary. Kept here because it is the first
time the question was asked at all.

### M2 — non-stationary run vs a matched stationary control
**`c316813`, 2026-07-27. n=1 per arm, 80 kB, 4 corpora.**

| | value |
|---|---|
| faded set (`p0,p1`), non-stationary | **4.819 b/B** |
| active set (`p2,p3`), non-stationary | **3.411 b/B** |
| matched stationary control, per process | 3.811 / 4.520 / 3.639 / 4.303 |
| faded-set baseline → observed | 4.166 → 4.819 = **FORGETTING +0.65 b/B** |
| active-set baseline → observed | 3.971 → 3.411 = **IMPROVED −0.56** |
| memory surviving | **p0=0 p1=0** p2=2198 p3=4778 |
| unlearn-a-faded-process test | *"SKIPPED — only 0 entries left (evicted); test would be vacuous"* |

**Era pre-both.** **This is the only measurement in the entire record shaped like the literature's
forgetting test** — a matched control, a distribution shift, the old material re-measured. It is
also the one with the worst provenance for a different reason: `INV-02` (`FABRIC=0`, two days before
`7a42f90`), `INV-22` (`SIG_WIN`, until `98e3301` on 08-02), `INV-05` (`MANAGE_EVERY=500` exceeded
the run), `INV-13`, and 80 kB is a toy scale. **VOID as evidence; retained as a design.**
Its second conclusion produced **`INV-26`**: every *"unlearning is surgical and local"* result in the
project was measured on ACTIVE material, and *"deleting what the bounded store has already evicted is
a no-op"* (also `9909349`).

### M3 — `PHASED=1` vs `PHASED=0`, per-process retention
**`a5ac033`, 2026-07-28. n=1 per arm, 80 kB, 4 corpora.**

| arm | per-process | mean | verdict |
|---|---|---|---|
| `PHASED=1` | p1 −0.203 · p2 +0.048 · p3 +0.226 | **+0.024** | **RETAINED** |
| `PHASED=0` | p0 +0.025 · p1 −0.048 · p2 +0.049 · p3 +0.561 | **+0.147** | **DRIFTING** |

**Era pre-both.** `INV-02`, `INV-13`. The **stationary** run reports the **worse** retention —
*"the sort of inversion the old whole-stream version could not have surfaced."* The commit itself
says both are single runs at small scale and that *"the point of the change is that the number now
means what it says."* **Not evidence that `PHASED=1` retains better; evidence that the metric is no
longer measuring corpus difficulty.**

### M4 — the ACTIVE / ABSENT columns, first reading
**`01c1cd3`, 2026-07-29. n=1, toy stream.**
`+0.902 b/B per 150 steps while ACTIVE` · `+0.192 per 150 steps while ABSENT` (both improving).
Process 2 sits at **7.60** while unseen and drops to **3.53** the step it enters.
**Era pre-both.** `INV-02` does not apply (`7a42f90` landed 07-29) but `INV-13` does, as does the
toy scale. Its value is the observation that *absent* processes still improved slightly rather than
decaying — *"a better result than the eviction numbers had led me to expect."*

### M5 — the held-out probe verified end to end
**`471318c`, 2026-07-31. n=1.** Train `eng,py` → resume with `eng,py,num`:
`eng was 4.263 → 4.486, +0.223 ± 0.047 WORSE (forgetting)` · `py 4.314 → 4.006, −0.308 ± 0.141
better` · `num 3.637 ± 0.040 NEW` · mean inside the noise.
**Era pre-both.** A **plumbing verification**, not a result: it establishes that the probe survives a
run boundary, keys correctly by name, and carries an error bar.

### M6 — the pilot → pilot-add chain
**`61b9d23`, 2026-08-02. n=1.** (`03_EXPERIMENTS` `X48`.)
`eng was 5.171 @ step 172 → now 4.466, −0.706 ± 0.162, better` · `py 4.680 ± 0.093 NEW`.
**Era pre-both.** Labelled **not a continual-learning result at the time it was made**, which is why
it needs no invalidation: *"the baseline was 172 steps and so undertrained that continued training
helped more than a second domain hurt."* What it establishes is that the measurement fires.
**Re-derived from the surviving checkpoints this session — see §7.**

### M7 — the store had evicted all but one domain
**`9909349`, 2026-07-29. n=1**, full-subsystem smoke, `PHASED` default.
Surviving memory: **p0=0 p1=0 p2=4976 p3=0**. A 6000-entry store under the non-stationary stream had
evicted everything except the most recent material, leaving one domain with entries — so the
IS THE PARTITION INFORMATIVE section had nothing to compare and *"correctly declines"*. It had been
declining **silently**, via a bare `if len(_doms) >= 2:` with no `else`.
**Era pre-both.** Bears on continual learning as the second independent observation of the eviction
behaviour that §5 explains.

### M8 — THE ONE REAL RUN
**`a9d7258` (record) / `b92f358` (run), 2026-08-14. n=1. `runs.csv` row `continual_eng_py`.**
**Era post-`c76dc74`, pre-`E14`, pre-`E15`.** Its own section follows.

---

## §5. The one real run — `a9d7258`

**Header block** (from `04_RESULTS` §7.3/§8, not recomputed).

| field | value |
|---|---|
| tag / row | `continual_eng_py`, row 30 of 42 |
| run commit / record commit | `b92f358` / `a9d7258`, 2026-08-14 |
| configuration | **RESUME from `nogrow_s2`** (English, held-out **1.989 ± 0.077**, row 29) **+ Python from the-stack**, `DOMAINS="eng,py"` |
| phase schedule | `PHASE_SCHED [[0],[0],[1],[1]]` — English **absent for the second half of every epoch, eight times**, and the run **ends on a Python-only phase** |
| epochs / VMAX / steps | 8 / 2048 / 110,131 (continuing `nogrow_s2`'s counter from 48,157) |
| corpus | **C4** = English + Python. order-1 **3.644**, uniform **4.695**. A different stream by construction |
| n | **1. No seed replication at all.** |
| instrument | **post-`c76dc74`**; **pre-`E14`** (founders immortal, `fab_born` unpersisted) and **pre-`E15`** (partitioned store, `EVICT` ranking a constant) |

### The readings

| reading | value | verdict | status |
|---|---|---|---|
| `eng` **across the run boundary** | **1.998 @ step 48157 → 2.050**, **+0.052 ± 0.075** | **HELD** (inside 2σ) | **DEGRADED — `INV-25`.** Weights-only (§2) |
| `py` 🅒 | **2.276 ± 0.086** | **NEW** — no baseline, nothing to forget yet | read against the **GitHub** anchor, below |
| combined held-out | **2.243 ± 0.078**, beating its own order-1 (3.644) by **+1.402** | — | own-anchor figure; `04_RESULTS` footnote 3 notes the CSV's rounded columns give +1.401 |
| learning curve **ACTIVE** | **+0.116 b/B per 2000 steps** | — | *"about four times faster than it forgets"* |
| learning curve **ABSENT** | **−0.029 b/B per 2000 steps** | — | **the first data this column has ever carried at pilot scale** |
| English trajectory | worst **2.19** during an early absence, back to **2.00** by the end | — | **recovers rather than ratcheting** |
| fabric contribution | **+0.373 b/B with SIX experts** | — | the **largest fabric contribution in the record, from the smallest population** — *"while the ramp elsewhere tries to build 4096"* |
| memory contribution | **−0.111 b/B** | — | net **negative**; and deleting a live domain's entries **improved both it and the others** |
| English memory entries surviving | **0 — every one evicted** | — | the faded-process unlearn test **skipped itself**, 0 entries left |

**🅒 The Python figure must not be read against the web-text anchor.** Per `04_RESULTS` §0.5 and
§10.2, from `LITREVIEW_FINDINGS.md` §4: `08_GLOSSARY`'s scale marker *"GPT-2-small sits near 1.0–1.2
b/B on comparable text"* is **English web text only** — Pile-CC 1.0878, OpenWebText2 1.1111. The
**GitHub (code)** figure is **1.7912 b/B**. `continual_eng_py` is the **only row in `runs.csv` that
contains code** (`pilot-add` is the one subcommand that sets `DOMAINS="eng,$NAME"`; every other runs
`DOMAINS=eng`). Against 1.7912, `py 2.276` is **0.48 b/B** from a reference model rather than the
~1.1 the web-text anchor implies. **This does not make it a good number; it makes the previous
reading of it too harsh.** The four reference figures come from a review whose sources could not be
opened (`WebFetch` blocked for every paper host) and are *"the review's word"*.

### The two invalidations, both partial

- **`INV-25` — DEGRADED.** `holdout_bpb` → `_eval_logits` does not consult memory. The +0.052 ± 0.075
  HELD is a **weights-only** retention figure, though *"the ONLY number that spans the run boundary"*
  implies otherwise. Consistent with every English memory entry having been evicted. **§2.**
- **`INV-43` — PROVENANCE DEGRADED.** `pilot-add` never ran `mkdir -p "$OUT"`, and `tee` opens its
  output file at process start, so the entire report went to a closed pipe (`40de03d`). *"Hours of
  GPU, a valid checkpoint, no record."* The `runs.csv` numbers are hand-transcribed from a terminal
  copy.
- Also **`INV-24`** — the eviction mechanism, §6 below.
- Also **`INV-06`** — `MEM_PER_EXPERT` read `_i(...,1)` against a comment saying DEFAULT OFF, so this
  run, like every other, used the **partitioned** store, measured at **−0.555 b/B** against the
  global store at the scale tested (`242e021`).

**The single most important run in the project is the one with the weakest provenance, and it is n=1
with no seed replication at all.**

---

## §6. Why all the English memory vanished

The run's most surprising line is that **English held while every English memory entry was gone**.
The cause is not that English became less useful. It is that nothing in the system could observe
usefulness at all.

**Root cause, quoted from `daf9f89` (2026-08-15):**

> *The eviction rules ranked a constant. `mem.read()` was called from exactly two places, `generate()`
> and `bpb_true()`, both eval-only, so during training `use` stayed 0 for every entry and `last` was
> never written at all on the global store (`read()` stamped it only when `n_own > 1`, and `_store()`
> only on the partitioned path). `EVICT=usage` therefore broke ties arbitrarily and every other path
> evicted by write order, whatever the knob said.*
>
> *That is the mechanism behind the vanished English domain: English was not less useful after the
> Python run, it had merely stopped being WRITTEN, and nothing in the training loop could observe
> that its entries were still being retrieved.*

`e25d9b5` (the commit before it) names the second half of the mechanism, the partition:

> *owners are experts folded mod `MEM_OWNERS`, both domains route to overlapping experts, and
> intra-block eviction is LRU on `last`, which is write-recency — so a domain that stops being
> written is evicted oldest-first by construction.*

**Read against the current source** (`memory.py`, verified this session):

- `memory.py:44-57` now documents the three rules and states the condition on which any of them is
  real: *"Both are only real if reads HAPPEN during training; with reads confined to eval, `use`
  stays 0 everywhere and `last` stays at write time, and both degenerate to FIFO."*
- `memory.py:187` — the partitioned path: `lru = blk[self.last[blk].argsort()][:need]`, *oldest
  last-use within this owner only*. Under the pre-fix regime `last` was write time, so this is
  literally oldest-write-first, per owner block.
- `memory.py:192-208` — the global path: `EVICT in ("usage","lru")` samples a candidate pool and
  kills the lowest `use` or the lowest `last`. Both were constants.
- `memory.py:209-211` — `self.tick += 1; self.last[idx] = self.tick` on write, with the comment
  *"The global path never stamped `last` at all before this line existed."*
- `memory.py:262-269` — `read()` now stamps `last` **unconditionally**; the comment records that it
  *"used to be gated on `n_own > 1`"*.

**The fixes, and what they cost.**

| fix | commit | what changed |
|---|---|---|
| `MEM_PER_EXPERT` default 0 | `e25d9b5` (08-15) | honours the documented decision; the partition had measured **−0.555 b/B** and was on in every run anyway. The same commit changed the call site but **not** the `_SPEC` declaration, which would have been a `SystemExit` at the read — caught by the registry in `daf9f89` |
| `MEM_PROBE_EVERY` / `MEM_PROBE_N` | `daf9f89` (08-15) | a cadenced **read probe inside the training loop**: real retrievals against the text being trained on. **Deterministic stride, not a random draw** — *"consuming stream RNG would make the probe cadence change the trajectory"* (the lesson of `E4`/`c76dc74`, applied by construction). Nothing it does feeds the forward pass or the loss. Defaults 25 / 64 |
| `last` stamped on every path | `daf9f89` | `read()` unconditional; `_store()` on both the partitioned and global paths |
| `EVICT=lru` becomes the default | `daf9f89` | least-recently-**RETRIEVED** dies. *"A quiet domain that still answers queries survives and a loud one nothing asks for does not"* |
| `RESUME` restores `last`/`tick` on the global store | `daf9f89` (`E5.7`) | without it *"every restored entry is the oldest thing in the store and is evicted before anything written after the resume — the same failure at the boundary."* **`a9d7258` predates this fix and is the only resume run in the record** |
| the epoch line reports retrieved-count and probe-count, and shouts if the probe ran and nothing was retrieved | `daf9f89` | *"A selection rule with no signal was invisible for the whole project; it is not invisible now"* — the standing rule from `05_ERRORS` §Recurring patterns: **a mechanism with no counter is indistinguishable from one that stopped** |
| `mem_evict_test.py` | `daf9f89` | drives a store two ways — a domain retrieved but not written vs neither — and asserts it can tell them apart, with `EVICT=recency` as the control that cannot. **Measured: lru keeps 70/100 of a read domain and 0/100 of an unread one; recency keeps 0 either way** |

**What this does to the run's memory numbers.** `INV-24` **VOIDs** *"any reading of `EVICT=usage` /
eviction policy as having selected anything"*. The **−0.111** memory contribution stands only as an
observation under an eviction rule with no signal, on a partitioned store (`INV-06`), whose contexts
were queried in a segmentation they were not written in (`INV-23`, `8bdeca4`: **82.3%** mismatch
after **one** growth step, where a pilot does about sixteen). `04_RESULTS` §7.2 states the
conclusion: *"Every 'memory contributes X' figure in this project is downstream of all three. The
editable external memory is the project's original thesis and there is no trustworthy number for
it."*

**And the one thing the eviction story does not explain.** The fixes are all in **after** `a9d7258`.
Nothing has been re-run. The claim *"weights and the fabric carried the retention"* rests on
elimination — English held while its memory was gone — and that elimination is only as strong as the
weights-only metric permits (§2). **It has not been shown that memory would not have helped had it
survived; only that it did not survive.**

---

## §7. What was actually run in `a9d7258` — DOC_PLAN question #3, investigated

`DOC_PLAN` "QUESTIONS I COULD NOT ANSWER" #3 asks: *"What actually ran in the one continual-learning
run (`a9d7258`)? Its log was lost. Was it `FAB_GROW=0`? `runs.csv` records `fab_nmax 4096` while the
note says 'RESUME from nogrow_s2'. Try `holdout.py` on any surviving checkpoint and look for a `.cfg`
beside it."*

Six findings, all from local sources.

**1. There is no `.cfg`, and there could not have been one.** `_cfgsig > "$LOG.cfg"` is written by
exactly two subcommands — `longrun.sh:675` (`grid`) and `longrun.sh:754` (`seeds`).
**`pilot-add` never writes one.** A repo-wide search returns **no `.cfg` file anywhere in this
checkout**. The `.cfg` countermeasure (`42d8686`) does not cover the continual-learning path.

**2. No checkpoint from that run survives on this machine.** The newest checkpoint under `runs/` is
`runs/rerun_0807_1654/smoke_ck/ckpt.pt` (2026-08-07); the newest anywhere on this filesystem is
2026-08-05, in the working scratchpad. Nothing from 08-14 exists here. **`holdout.py` cannot be run
on the `a9d7258` pair from this checkout.** Per `DOC_PLAN` #4 the GPU results from 08-10 onward exist
only in commit messages and `runs.csv`; the checkpoint, if it exists, is on the GPU box.

**3. `holdout.py` works, and this is the first time it has been exercised.** The `61b9d23` pilot →
pilot-add pair **does** survive locally (`…/scratchpad/pv/pilot_gru/` and `…/pv/pilot_gru_py/`,
2026-08-02). Run this session:

```
python3 holdout.py <parent> <child>
  step 172 | eng 5.171 +/- 0.109
  step 330 | eng 4.466 +/- 0.120 | py 4.680 +/- 0.093
  === ACROSS THE RUN BOUNDARY (reconstructed from the checkpoints) ===
    eng   was 5.171  ->  now 4.466   -0.706 +/- 0.162   better
    py    4.680 +/- 0.093   NEW -- no baseline, nothing to forget yet
```

**Byte-for-byte the numbers `61b9d23` reported from the live log.** The recovery tool is verified,
n=1, against a commit-recorded result. **If the `a9d7258` checkpoint exists on the GPU box, its
retention figure is recoverable and this proves it.**

**4. What a checkpoint can and cannot answer about configuration.** Dumped the non-tensor keys of a
surviving checkpoint. `_save_ckpt` (`self_organize.py:4021-4081`) stores `fab_cfg` =
`{n, rank, cap, dk, alpha, max_steps, hid_mult, min_steps, norm_only, society, grounded, route_t,
route_learn, ens_k, halt_on, halt_max}`, plus `fab_born`, `fab_uage`, `holdout`, `holdout_step`,
`tok_vocab`, `tok_merges`, `asm`, `world_cfg`. **`cap` = `fab.cap` = `FAB_NMAX` is recorded** (added
at `2e3a464`, verified an ancestor of `b92f358`). **`FAB_GROW` is not recorded anywhere.** So a
surviving checkpoint would settle the cap and the final population size, and would **not** settle
whether growth was enabled.

**5. `runs.csv`'s `fab_nmax 4096` and "RESUME from `nogrow_s2`" are not in conflict, and the answer
to "was it `FAB_GROW=0`?" is almost certainly no.** `pilot-add` (`longrun.sh:395-447`) passes a
**fixed** env block and **sets no fabric flag at all** — no `FAB_GROW`, no `FAB_N0`, no `FAB_NMAX`,
and no `ARMFLAGS` hook. The run therefore inherited the `_SPEC` defaults. Read out of
`git show b92f358:self_organize.py`:

| knob | default at `b92f358` | consequence |
|---|---|---|
| `FAB_GROW` | **1** | growth **ON** |
| `FAB_N0` | **2048** (was **3** until 2026-08-17) | — (overridden on resume: `self_organize.py:3574` restores `n_live` from `fab_cfg["n"]`) |
| `FAB_NMAX` | **4096** | matches `runs.csv`'s `fab_nmax 4096` exactly |
| `FAB_BURST` | 3 | `FAB_NEW_FRAC` **did not yet exist** — the newborn-fraction mitigation was not in |
| `MEM_PER_EXPERT` | **1** | partitioned store — `INV-06` |
| `EVICT` | **`"recency"`** | write-order eviction — `INV-24`, and §6 |
| `PHASED` | **1** | non-stationary, as intended |

`runs.py` reads `fab_nmax` from the log's `[config] EFFECTIVE` line (`runs.py:32,53-56`), never by
hand, and its manual path (`cmd_manual`) stamps `commit="(no log)"` — the signature carried by rows
9–11. Row 30 carries a real parsed commit (`b92f358698`) and a full complement of parsed columns, so
it went through `parse()` on a file that no longer exists on this machine. **Inference, flagged as
such**: the terminal copy was saved to a file, ingested with `runs.py add`, and not retained. On that
reading `fab_nmax=4096` is the EFFECTIVE-line value — *what ran*, not what was intended.

**So: "RESUME from `nogrow_s2`" names the checkpoint, not the arm.** The run took arm A's *weights*
and ran them under the **HEAD default fabric configuration — `FAB_GROW=1`, cap 4096 — which
`04_RESULTS` §3 and `f8599b7` identify as arm D** (mean 3.384, spread 2.074, the arm the 2x2 found
fatal). The only way it was `FAB_GROW=0` is if the operator exported it on the command line, which
would have appeared on the lost EFFECTIVE line and is unrecorded.

**6. And that leaves a genuine puzzle, recorded rather than resolved.** With growth on and a cap of
4096, the run finished with **six experts**. Arm A drifts 3 → ~6 through `spawn_from`, which ignores
`FAB_GROW` and the soft cap entirely (`E3.11`, `41d2c5d`) — so six is exactly the population
`nogrow_s2` handed over, and `PlateauGrowth` appears to have added **nothing** across ~62,000
further steps. Either the plateau condition never fired after a resume, or the ramp never latched in
this configuration. **This is the most consequential unresolved fact about the run**: it means the
best continual-learning result on record was produced by a *small* population under a configuration
nominally set to ramp, and `DOC_PLAN` "know NOW" #1 — *does the current default reproduce arm D?* —
is entangled with it.

---

## §8. Our metric against the standard ones

From `notes/_evidence/litreview/11_forgetting_metrics.md`. The field's apparatus is the T×T matrix
`R[i,j]` = performance on task `j` after finishing task `i` (Lopez-Paz & Ranzato, NeurIPS 2017).
Four metrics come off it: **ACC** (mean final performance), **BWT** (final minus just-after-learning,
negative = forgetting), **FWT** (zero-shot before training, against a baseline), and the
**Forgetting Measure** `F` (best-ever minus current, Chaudhry et al., ECCV 2018).

The adaptation to language modelling is small and the review recommends the version this repo is
already positioned for:

> *use bits-per-byte differences, not perplexity ratios. b/B is already a log-scale quantity, so a
> difference in b/B is a ratio in probability terms, and it's tokenizer-invariant — which matters
> uniquely for you, since you are minting BPE merges during training and your token count is not
> fixed. A perplexity ratio across a vocabulary change is not a meaningful quantity.*

```
BWT_bpb = (1/(D−1)) Σ_d ( bpb_{d,d} − bpb_{T,d} )              # negative = forgetting
F_bpb   = (1/(D−1)) Σ_d ( bpb_{T,d} − min_{l<T} bpb_{l,d} )    # positive = forgetting
```

### What ours is, and what it cannot see

| | ACROSS THE RUN BOUNDARY (`471318c`) | the standard matrix |
|---|---|---|
| what it compares | the probe stored in the checkpoint you resumed **from**, against the same probe **now** | every task after every task — `R[i,j]` for all `i,j` |
| coverage | **two points: the last save of the parent, the last save of the child.** One row of `R`, one column deep | `T²` evaluations |
| what it evaluates | **weights + fabric only** (§2) | *"the current system… Model weights, optimizer state, and — critically for you — any external memory are all in whatever state the run has left them in"* |
| forward transfer | **not measured.** `py` is reported `NEW — nothing to forget yet`; there is no zero-shot reading of `py` before training on it, and no from-scratch `py` baseline | FWT, against `b̄_j` |
| best-ever vs just-after | only just-after. **`F` cannot be computed** — nothing retains the intermediate rows | BWT *and* F; the review says **report both**, and F is the more conservative |
| error bar | **yes** — per-window, 2σ verdict. This is where ours is *better* than the standard presentation, which usually reports a bare mean | commonly none |
| a matched no-retrieval arm | **no** | not standard either — but see below |

**Three things ours cannot see, stated concretely.**

1. **The memory's contribution to retention.** The review's fix is not to replace the metric but to
   **report a matched pair** — `R^full` with retrieval enabled and `R^weights` with it disabled —
   because `R^full − R^weights` *"is the memory's contribution, per domain, per checkpoint. That
   difference is the thing your architecture exists to produce and you currently have no number for
   it."* And it separates two failure modes this project currently conflates: *"if the memory
   contribution on an old domain decays over phases while its weights-only number is flat, you have
   an eviction problem, not a forgetting problem. If both decay, you have a forgetting problem."*
   Given §6, **that is the exact distinction `a9d7258` needed and could not draw.**
2. **Whether English was ever *better* than 1.998.** `F_bpb` needs `min_{l<T}`, i.e. the probe at
   every intermediate save. `_save_ckpt` writes `holdout` on the `CKPT_EVERY` cadence, so the data
   *could* exist; at `pilot-add`'s `CKPT_EVERY=10000` over 62k steps that is ~6 intermediate rows —
   **and they are overwritten, since one checkpoint path is reused.** The `.best` copy is the only
   survivor. So `F` is not recoverable from what the harness keeps.
3. **Anything about a third domain, a re-addition, or a revisit.** Ours is a single 2-domain,
   one-direction, one-addition reading.

**One thing the review adds that costs nothing**: *"Log the store's per-domain occupancy alongside
`R`. Not a standard metric, but it is the direct measurement of the Q3 question that no published
paper reports, and you'd be generating novel data essentially for free."* The project already prints
`memory surviving: p0=… p1=…` (M2, M7) — it has simply never been recorded next to a retention
number.

**And the reframing the review calls its most useful** (`10_replay_buffer_selection.md`):

> *replay buffers are read during training by construction, and that is why this field developed
> retrieval-selection rules (MIR) while the kNN-LM field did not… **You are in the replay-CL regime,
> not the kNN-LM regime**, and you should be reading this literature as your primary reference.*

Two consequences bear directly on §6. **Plain reservoir sampling guarantees the failure mode
observed here as a theorem** — `E[slots held by A] = M·N_A/N → 0` as a new domain streams
indefinitely; *"the old domain is not evicted by a bad decision. It is diluted to zero by a correct
one."* And the fix the retrieval literature does not have exists in replay CL: **per-source /
class-balanced reservoir quotas** (CBRS, iCaRL). This project *has* a partition — `MEM_PER_EXPERT`,
owners folded mod `MEM_OWNERS` — but it is keyed on **expert**, not on domain, and both domains route
to overlapping experts (`e25d9b5`), so it is not a per-source quota and does not protect a faded
domain. `5c711cf` records the researcher explicitly **rejecting** a strict per-domain memory quota;
the literature says that is the one structure known to work, so the rejection deserves re-examination
rather than inheritance.

---

## §9. What would actually establish continual learning here, and what it costs

**Nothing above establishes it.** One run, n=1, no log, a weights-only metric, an eviction rule with
no signal, and no from-scratch control. What follows is a concrete design, sized against
`04_RESULTS` §2.2's per-arm σ and the pairing / `P(A>B)` recommendation in `LITREVIEW_FINDINGS.md`
§1.

### Step 0 — the code change, which is not a run (hours, no GPU)

Make the probe report a **matched pair**. `holdout_bpb` takes a `use_mem` argument and is called
twice; the report prints `R^weights`, `R^full`, and their difference per domain. **The machinery
already exists**: `bpb_true` (`self_organize.py:6480`) has the identical `use_mem` branch —
`mem.read(mem_key(X))`, `_mem_hp`, the `(1−hp)·pm + hp·pmem` blend — and `holdout.py` stores whatever
`_save_ckpt` writes, so both columns land in the checkpoint and the recovery path keeps working.
Also store the per-domain occupancy alongside. **This is the highest-value change in the file and it
costs no GPU time.** Without it every seed spent below buys a weights-only answer.

### Step 1 — measure σ for the retention delta, which has never been measured (3 runs)

**We have no σ for this quantity at all.** The `±0.075` on `+0.052` is a *within-run* combination of
two window-sampling standard errors, not seed variance. The only σ available are `04_RESULTS` §2.2's
end-of-run held-out σ: **arm B 0.047**, **arm A 0.193**, arm D 1.225 — and *"σ is not a property of
the measurement, it is a property of the arm."*

The parents already exist as three seeds (`nogrow_s0/s1/s2`, rows 27–29, or `popB_*`, rows 31/33/35).
**Three `pilot-add` runs, seed-paired to those parents**, is the entire marginal cost. It converts
`a9d7258` from n=1 to n=3 and produces the first σ for a retention delta in the project's history.

Sizing, using the review's machinery (`P(A>B) = Φ(d/√2)`; paired-design `n ≈ 2(z_{α/2}+z_β)²/d²`,
α=0.05, β=0.2 — **the same arithmetic as `04_RESULTS` §2.3, and equally noisy**):

| σ proxy | d for Δ=0.052 | P(A>B) | paired seeds |
|---|---|---|---|
| arm B, 0.047 | 1.11 | 0.784 | **≈ 13** |
| arm A, 0.193 | 0.27 | 0.575 | ≈ 215 |

**The spread between those two rows is the reason to measure σ before planning a budget.** If the
add-run behaves like arm B, the question is affordable; if like arm A, an unpaired design is
hopeless and only pairing rescues it. **Pairing is free and worth more than seeds here** — same seed,
same data order, same parent checkpoint, per `LITREVIEW_FINDINGS` §1 — because the two arms share
almost all machinery. And report **`P(A>B)` with a percentile-bootstrap CI**, not mean ± std: their
Figure 6 finds mean-difference at k=50 misses ~90% of real effects.

### Step 2 — the control that has never been run (3 + 3 runs)

`04_RESULTS` §11 and `05_ERRORS` both record that **catastrophic forgetting in the literature sense —
learn a task, shift the distribution, re-measure the original against a from-scratch control — has
never been run** at pilot scale. M2 (`c316813`) is the only attempt and it is void on five counts.

Minimal T=2 matrix, three arms, seed-paired, each scored on **both** held-out sets and **both**
retrieval settings:

| arm | what it is | already exists? |
|---|---|---|
| `A_eng` | English only — the parent | **yes**, ×3 seeds (rows 27–29 / 31/33/35) |
| `A_add` | resume `A_eng`, add Python — the `a9d7258` shape | ×1; needs ×3 |
| `A_joint` | English + Python **from scratch**, same total steps — the multitask ceiling | **no** |
| `A_py` | Python only from scratch — the FWT baseline `b̄_j` | **no** |

From these: `ACC`, `BWT_bpb`, and `FWT` in the review's b/B forms, computed twice (`R^full`,
`R^weights`), with the memory contribution as their difference. `F_bpb` needs the intermediate rows
and therefore needs `CKPT_EVERY` saves kept under distinct names — a harness change, not a run.

### Cost

**9 pilot-shape runs** (3 `A_add`, 3 `A_joint`, 3 `A_py`) plus the two code changes.
The pilot shape is 4 MB/epoch × 8 epochs ≈ 52k steps, quoted at **~15–20 minutes** at `c411ac7`;
`40de03d` describes the actual add run as *"hours of GPU"*. Take the conservative figure: **on the
order of a day of GPU, plus a morning of code**, against a record in which dozens of runs went to
arms the project's own reading order labels *"the machinery, only insofar as it moves 1 and 2."*

### Two preconditions

1. **Re-run the parent, or pin its config.** `INV-15`/`E14`: arm B ran with **zero culls** because
   founders had no birthday, and `a5cc7ea` closed it — so the parents as measured are **not
   reproducible at HEAD**. A new `A_eng` is not the old `A_eng`.
2. **Decide what fabric configuration the add-run should use, deliberately.** §7 finding 5: the
   default is arm D. It should be *chosen*, printed, and stored beside the log — and `pilot-add`
   should write a `.cfg` like `grid` and `seeds` do. **That is a three-line change to `longrun.sh`
   and it is the direct cause of `DOC_PLAN` question #3 existing.**

---

## §10. Open questions

**Q1 — What did `a9d7258` actually run?** Partly answered in §7: no `.cfg` (and `pilot-add` writes
none), no surviving checkpoint on this machine, `fab_nmax=4096` reconciled as the EFFECTIVE-line
value of a run that set no fabric flags and inherited `FAB_GROW=1`. **Still open:** whether the
operator exported `FAB_GROW=0`, which only the lost log could say; and whether the GPU box still
holds the checkpoint pair, which would settle the cap and the population and let `holdout.py`
reconstruct the boundary figure — **proven to work, §7 finding 3**.

**Q2 — Why did a run with growth ON and cap 4096 end with six experts?** §7 finding 6. Unresolved,
and it is entangled with `DOC_PLAN` "know NOW" #1.

**Q3 — Does memory help retention at all?** Unmeasured, and unmeasurable with the current metric
(§2). In the one run that mattered it was net **−0.111** and fully evicted (§5), under an eviction
rule that was ranking a constant (`INV-24`) on a partition measured at −0.555 (`INV-06`) with 82.3%
of its contexts stale (`INV-23`). **The project's original thesis has no trustworthy number.**

**Q4 — Is the retention real, or is it seed noise?** n=1. σ for a retention delta has never been
measured. §9 step 1.

**Q5 — Does anything hold beyond two domains, one addition, one direction?** Nothing has tested a
third area, a **re**-addition, or **revisiting** a faded area. The one run ended on a Python-only
phase, so the last thing the model saw was the new domain — the easiest possible ordering for the
new domain and the hardest for the old.

**Q6 — Is unlearning surgical?** **`INV-26` — VOID as a claim about faded material.** Every such
result was measured on ACTIVE material; under the non-stationary stream the bounded store had already
evicted the faded material, so the faded arm skipped itself. *"Deleting what the bounded store has
already evicted is a no-op."*

**Q7 — Has catastrophic forgetting in the literature sense ever been run?** **No.** §9 step 2.

**Q8 — Does `EVICT=lru` actually help, or does it make the scan problem worse?**
`LITREVIEW_FINDINGS.md` §3 flags that this project moved FIFO → LRU while the caching field spent
five years moving LRU → FIFO-with-structure, and that *"a new domain floods the store"* is the
textbook **scan**, which plain LRU has no defence against. It proposes a cheap internal test that
needs no literature: **compare the new domain's occupancy share under `EVICT=lru` against
`EVICT=recency` after a domain switch** — `mem_evict_test.py` (`daf9f89`) already has the harness
shape. **`daf9f89` made `lru` the default before that test was run.**

**Q9 — Should the store have a per-domain quota?** `5c711cf` records the decision to **reject** one
in favour of memory-pressure → grow/retrain/split. `10_replay_buffer_selection.md` says per-source
quotas (CBRS, iCaRL) are the standard remedy and that plain reservoir *guarantees* the observed
failure mode. The existing partition is keyed on **expert**, not domain, and does not do this job.
**The rejection should be re-decided against that, not inherited.**

**Q10 — Do the `RESUME` defect fixes change the picture?** `05_ERRORS` §5 lists nine, and *"every
entry here bears on continual learning, because `RESUME` is how continual learning is meant to work
in this system."* Two land squarely on `a9d7258`, which predates both: **`E5.6`** (`fab_born`
unpersisted — restored experts immortal) and **`E5.7`** (`last`/`tick` unrestored — every restored
entry is the oldest thing in the store). Neither has been re-measured.

---

## What survives, on this subject

Short, and it should be.

1. **The measurement fires, spans a run boundary, keeps old and new apart, and carries an error bar**
   (`471318c`, `61b9d23`) — and it is **weights-only** (`f8599b7`, `INV-25`).
2. **The recovery path works.** `holdout.py` reconstructs the boundary comparison from two
   checkpoints, verified this session against `61b9d23`'s live-log numbers (`40de03d`, §7).
3. **One reading exists at pilot scale**: `eng +0.052 ± 0.075 HELD`, `py 2.276 NEW`, ACTIVE +0.116 vs
   ABSENT −0.029, fabric +0.373 with six experts, memory −0.111 with every English entry evicted.
   **n=1, no log, no seed replication, weights-only, pre-`E14`, pre-`E15`** (`a9d7258`).
4. **The defects are facts about the source**, independently checkable: the eval path does not read
   memory (§2), the eviction rules were ranking a constant (§6), `pilot-add` writes no `.cfg` (§7).
5. **Nothing here is a claim about what is true.** It is a record of what was observed, once, under
   conditions this file has tried to state completely.
