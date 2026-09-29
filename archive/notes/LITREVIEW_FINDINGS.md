# Literature review — what it says, and where it is wrong about us

The review is archived verbatim at `notes/_evidence/litreview/`. It is good, and most of it stands.
This file records only the parts I **checked against this repo**, because four of its
recommendations are aimed at a version of this project that no longer exists, and two of its
warnings do not apply to code we actually run.

Checked 2026-08-15 against `rm-predict`. Every claim below was verified against the source or
`notes/_evidence/commit_log.txt`, not recalled.

---

## 1. The seed analysis is right, but its σ is from the wrong era — CORRECTED

The review computes **σ ≈ 0.596 b/B** from the 1.227 b/B spread at `33a9299`, and derives seed
requirements from it. Two problems, both verifiable:

**(a) `33a9299` is PRE-`c76dc74`.** Verified with `git merge-base --is-ancestor 33a9299 c76dc74`
→ true. That is the commit where diagnostics were drawing from the same RNG as the stream, so
*how much you measured decided what you trained on*. The 1.227 spread was measured through the
broken instrument. `05_ERRORS.md` INV-13 voids every arm comparison from that era; the σ derived
from one is not exempt.

**(b) Its recommended first step is already done and it passed.** The review says: pin
nondeterminism, run 5× with all seeds fixed, and find out whether 1.227 is stochasticity or a
bug. `33a9299`'s own message records the answer — *"the determinism check (base and nogate
byte-identical)"* — and `longrun.sh`'s `seeds)` block records three runs at one seed and config
coming back byte-identical in every reported number, with `equiv.sh` reproducing it across
commits. **Do not spend those 5 runs.** Determinism at fixed seed and fixed config holds.

### What σ actually is, post-fix

From the 2×2 at `cc0a377` (2026-08-15), three seeds per arm, post-`c76dc74`. σ estimated from
the range with the small-sample factor (d₂ = 1.693 at n=3):

| arm | mean | range | σ (est) |
|---|---|---|---|
| A  fixed N0=3 | 2.117 | 0.326 | 0.193 |
| B  fixed N0=2048 | 1.999 | 0.080 | **0.047** |
| C  ramp NMAX=64 | 2.091 | 0.180 | 0.106 |
| D  ramp 3→4096 | 3.384 | 2.074 | **1.225** |
| ramp 2048→4096 | 2.009 | 0.160 | 0.095 |

**σ is not a property of the measurement. It is a property of the arm** — it ranges 26× across
four arms of one experiment, run the same day on the same instrument. A single pooled σ is the
wrong model, and it is the model the review's arithmetic assumes.

This is worth more than the correction: **instability tracks ramping.** Arm D is not merely
worse on the mean, it is unstable (σ = 1.225 against arm B's 0.047). Whether the *mean*
difference or the *variance* difference is the real phenomenon has never been asked here, and
the variance is the larger effect.

### Seed requirements, recomputed per-arm

Same machinery as the review (P(A>B) = Φ(d/√2); Noether with α=0.05, β=0.2, γ=0.75), with
per-arm σ instead of pooled:

| comparison | Δ b/B | d | P(A>B) | paired seeds | review said |
|---|---|---|---|---|---|
| D 3→4096 vs B fixed-2048 | 1.385 | 1.13 | 0.788 | **≈ 12** | ≈ 9 |
| ramp 2048→4096 vs B fixed-2048 | 0.010 | 0.09 | 0.527 | **≈ 1,450** | ≈ 80,000 |
| A fixed-3 vs B fixed-2048 | 0.118 | 0.60 | 0.663 | ≈ 39 | — |

The review's headline conclusions survive: the growth finding is affordable to establish, and
the 2.009-vs-1.999 question is not. But the second is 55× cheaper than stated and still
infeasible, and the first needs ~12 rather than 9 — its σ was too small for arm D and too large
for arm B, and the two errors nearly cancelled.

### What to actually adopt

- **Pairing** (same seed, same data order, same init for both arms of a comparison). Free, and
  the review is right that it is worth more here than anything else, because our arms share
  almost all machinery.
- **Report P(A>B) with a percentile-bootstrap CI**, not mean±std, as the decision rule. Their
  Figure 6: mean-difference at k=50 misses ~90% of real effects.
- **Randomize data order and data sampling, not just init.** We vary `SEED` only, which their
  Figure 1 says probes the *small* variance source.

Caveat on my own arithmetic: range→σ from n=3 is a very noisy estimator. These σ are indicative,
not measured. Computing the actual sample std from the four 2×2 arms is nearly free and should
be done before anyone plans a seed budget on this table.

---

## 2. Two warnings that do not apply — CHECKED, NO ACTION

**"You may have a 4096× error in your balance loss."** No. `fab_bal(w) = w.size(1) * (w.mean(0)
** 2).sum()` — the factor of N is present. Verified numerically: perfectly uniform routing gives
exactly 1.0 at N = 8, 64 and 4096, and full collapse gives N. Correctly normalised at any expert
count.

One real difference remains, smaller than the review feared: Switch uses `N · Σ fᵢ·Pᵢ` with `f`
the hard dispatch fraction; ours uses `N · Σ Pᵢ²`. Near-uniform routing the gradient is 2 for
ours against ~1 for Switch — a factor of 2, not 4096, and it folds into `FAB_BALANCE`.

**"Check whether you're also rescaling weight decay."** We are, and that is correct rather than a
bug. PyTorch AdamW's total step is `−lr·(wd·p + adam_step)`, so rescaling the whole realised
delta by `r` is exactly `lr' = r·lr` — including the decay term, which is what a per-row learning
rate should do. Separately: `WEIGHT_DECAY` defaults to 0 and is set by only two arms (`wdecay`,
`reg` in `_flags_for`), so it is inert in every recorded run regardless.

The review's main Adam point stands and is useful: Adam's `m` and `v` depend on gradients only,
so update-rescaling cannot corrupt them. **Open, not resolved:** its caution that a cycle shorter
than ~1/(1−β₂) ≈ 1000 steps never lets `v` equilibrate. Our `FAB_LR_CYCLE` is 24 *selections*,
and how many optimizer steps that spans depends on the selection rate, which the running pilot
is the first thing to measure. Read `cycle min..max` on the `[lr]` line.

---

## 3. The cache-eviction finding — this one lands, and we should act on it

`notes/_evidence/litreview/09_cache_eviction.md`. The claim: **we moved FIFO → LRU; the caching
field spent five years moving LRU → FIFO-with-structure**, and our "new domain floods the store"
is the textbook *scan*, which plain LRU has no defence against. Its framing: LRU is eager
promotion + passive demotion; the correction is lazy promotion + quick demotion.

I have not verified this against a primary source (`WebFetch` is blocked for every paper host)
and it contradicts a design decision made here last week, so it should be read as a strong lead,
not a settled result. But it is testable cheaply and internally: **compare the new domain's
occupancy share under `EVICT=lru` against `EVICT=recency` after a domain switch.** If LRU's share
is *higher*, the mechanism is confirmed with no literature needed. `mem_evict_test.py` already
has the harness for exactly this shape of test.

Its concrete proposal is S3-FIFO: a ~10% probationary FIFO that new writes enter, promotion to
the main region only on retrieval while still in probation, plus a keys-only ghost list of
recently-evicted entries. The ghost list is the cheapest part and measures something currently
unmeasured — our own eviction error rate.

**One point of theirs is already half-implemented and worth finishing.** They observe that a
cosine-kNN "hit" is not binary — an entry returned at similarity 0.4 is not evidence of the same
thing as one at 0.95 — and recommend a similarity-weighted hit count. `mem.use` already does
this: `use.index_add_(0, gi, w)` accumulates the softmax weight, not a count. But `mem.last`, the
clock that `EVICT=lru` actually ranks on, is stamped by *any* retrieval regardless of weight. So
the graded signal exists and the eviction rule ignores it. That is a small change to code we
already have.

---

## 4. The findings I have no basis to check

Recorded as-is, from a source I cannot open. Treat as the review's word:

- **Our b/B anchor is wrong for code.** GPT-2-small is 1.0878 on Pile-CC and 1.1111 on
  OpenWebText2 — the remembered 1.0–1.2 is fine for English web text — but **1.7912 on GitHub**
  and 1.2253 on the Pile aggregate. Our Python result (2.276) has been read against a web-text
  anchor. There is no single scale marker across text and code.
- **No prior art** for per-group LR schedules with independent phase (Q1), per-source quota in a
  bounded retrieval store (Q3), or a controlled newborn-fraction-vs-final-size study (Q6). The
  last means our growth result appears to be unpublished.
- **The nearest LR prior art cuts against our design.** Decoupled Relative Learning Rate
  Schedules (arXiv 2507.03526) tunes MoE experts *low early, high late* — specifically to prevent
  early specialization freezing the router. Our birth-anchored peak is the opposite move.
- **The MoE ecology paper does not contain the ablation we wanted.** It is deferred to an
  unfindable reference; the balance-loss formula is not given; its language results are at
  WikiText-2 perplexity 33,163–37,812, i.e. a model that learned nothing. **It does not license
  dropping cull-and-reseed.**
- **Reservoir sampling guarantees our feared failure mode** as a theorem: an old domain's
  expected buffer share is `M·N_old/N_total → 0` under indefinite new-domain streaming.
- **Per-source quotas do exist**, in replay-based continual learning (class-balanced reservoir,
  iCaRL) rather than the retrieval literature.
- **Our store is read during training, which puts us in replay-based CL, not kNN-LM.** Four of
  the twelve questions turned out to be one question in four vocabularies.
