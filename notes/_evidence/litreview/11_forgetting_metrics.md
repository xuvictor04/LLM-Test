# Q10 — Standard forgetting metrics

## The matrix everything is built on

Train on tasks 1..T in order. After finishing task i, evaluate on the held-out test set of
**every** task j (including future ones). This gives a T×T matrix R, where

```
R_{i,j} = test performance on task j after training has finished on task i
```

Diagonal R_{j,j} = performance on a task right after learning it. Below the diagonal
(i > j) = retention. Above the diagonal (i < j) = zero-shot transfer.

**Source: Lopez-Paz & Ranzato, "Gradient Episodic Memory for Continual Learning," NeurIPS
2017.** This paper defines ACC, BWT and FWT and is the citation for all three.

## The four standard metrics

### Average Accuracy (ACC) — Lopez-Paz & Ranzato 2017
```
ACC = (1/T) Σ_{j=1}^{T}  R_{T,j}
```
Mean performance over all tasks, measured at the end. Higher is better.

### Backward Transfer (BWT) — Lopez-Paz & Ranzato 2017
```
BWT = (1/(T−1)) Σ_{j=1}^{T−1}  ( R_{T,j} − R_{j,j} )
```
For each old task, final performance minus performance right after learning it, averaged.
**Negative = forgetting.** Large negative = catastrophic forgetting. Positive BWT means later
tasks *helped* earlier ones. Undefined for the last task.

### Forward Transfer (FWT) — Lopez-Paz & Ranzato 2017
```
FWT = (1/(T−1)) Σ_{j=2}^{T}  ( R_{j−1,j} − b̄_j )
```
Zero-shot performance on task j before training on it, minus a baseline b̄_j (random-init test
accuracy in the original; some papers use an independently-trained single-task model R_j^ind
instead, which measures something different — read the definition before comparing numbers
across papers).

### Forgetting Measure / Average Forgetting — Chaudhry et al., "Riemannian Walk for Incremental Learning," ECCV 2018
```
f_j^k = max_{l ∈ {1..k−1}} ( R_{l,j} − R_{k,j} )
F_k   = (1/(k−1)) Σ_{j=1}^{k−1}  f_j^k
```
The difference between the **best-ever** performance on task j and its current performance.
Higher = more forgetting (sign convention is opposite to BWT).

**BWT vs Forgetting Measure — the distinction people get wrong.** BWT measures against
performance *immediately after* learning the task. The forgetting measure measures against the
task's *best-ever* performance at any checkpoint. If a task keeps improving for a while after
you stop training on it (positive backward transfer, then decay), BWT and F will disagree, and
F is the more conservative number. **Report both.**

## Adapting to language modelling

Two things change and one doesn't.

**What doesn't change:** the matrix. R_{i,j} is still "evaluate the current model on domain j's
held-out data." You just replace accuracy with a loss-like metric.

**What changes 1 — the sign.** Perplexity and b/B are lower-is-better, so the differences flip.
Either negate, or define explicitly, but state which you did.

**What changes 2 — differences vs ratios.** A 2-point perplexity rise means something very
different at PPL 10 than at PPL 200. The convention I found in current work is a
**relative-degradation** form. From arXiv:2605.15053 (TFGN), which states its adaptation
explicitly: let M[t,d] be held-out perplexity on domain d after phase t; BWT is defined as the
average of per-domain **relative** degradations from the just-trained perplexity to the
final-phase perplexity. BWT = 0 means no forgetting, BWT < 0 means forgetting, and the scale is
unbounded below.

**My recommendation for you specifically: use bits-per-byte differences, not perplexity
ratios.** b/B is already a log-scale quantity, so a *difference* in b/B is a *ratio* in
probability terms, and it's tokenizer-invariant — which matters uniquely for you, since you are
minting BPE merges during training and your token count is not fixed. A perplexity ratio across
a vocabulary change is not a meaningful quantity; a b/B difference is. This is a real advantage
your setup has and you should use it.

```
BWT_bpb = (1/(D−1)) Σ_{d=1}^{D−1} ( bpb_{d,d} − bpb_{T,d} )      # negative = forgetting
F_bpb   = (1/(D−1)) Σ_{d=1}^{D−1} ( bpb_{T,d} − min_{l<T} bpb_{l,d} )   # positive = forgetting
```

## Is the old data re-evaluated with the current model only?

**Yes — and nothing else is held fixed.** R_{T,j} is the *current* system evaluated on task j's
*fixed* held-out set. The held-out set is the only frozen thing. Model weights, optimizer
state, and — critically for you — any external memory are all in whatever state the run has
left them in.

This is not an oversight in the metric; it is the point. The metric measures the deployed
system's retention, whatever the system consists of.

## Your "ACROSS THE RUN BOUNDARY" problem

You found your metric is weights-only, so it can't see the retrieval store. Here is what the
standard metrics say about that, and it's more useful than "just use BWT":

**1. The standard metric would have caught it, because R_{i,j} is defined on the system, not
the weights.** There is no weights-only version of BWT in the literature. If your evaluation
path bypasses memory, you are not computing BWT on your system — you are computing BWT on a
different, ablated system. That ablated number is not wrong, it just answers a question you
didn't ask.

**2. The fix is not to replace your metric but to report a matched pair.** Compute the full
matrix twice:

- `R^full` — evaluation with retrieval enabled. This is your system's actual retention.
- `R^weights` — evaluation with retrieval disabled. This is the parametric component alone.

Then `R^full − R^weights` **is the memory's contribution, per domain, per checkpoint.** That
difference is the thing your architecture exists to produce and you currently have no number
for it. It is also the quantity that would tell you whether your bounded store is being
diluted (file 10) — if the memory contribution on an old domain decays over phases while its
weights-only number is flat, you have an eviction problem, not a forgetting problem. If both
decay, you have a forgetting problem. **The two-metric decomposition separates the two failure
modes you cannot currently distinguish.**

**3. Log the store's per-domain occupancy alongside R.** Not a standard metric, but it is the
direct measurement of the Q3 question that no published paper reports, and you'd be generating
novel data essentially for free.

**4. Precedent for the paired ablation:** Goodtriever's continual experiment (file 03) reports
per-domain results at every step as new domains are added, and the contrast between its
retrieval-based curve and the parametric multitask/continual-finetune curves is exactly this
decomposition, done across methods rather than within one system.

## Cautions

- **BWT is not defined for the last task**, and the first task's FWT is undefined. Off-by-one
  errors here are common.
- **The T×T matrix costs T² evaluations.** With D domains and many checkpoints this dominates.
  A common shortcut is evaluating only the final row plus the diagonal, which gives you ACC and
  BWT but *not* the forgetting measure (which needs the max over all earlier rows).
- **Definitional drift is real.** The medical-imaging CL review (arXiv:2312.17004) catalogues at
  least four different published BWT variants — computed at the last episode, after each
  subsequent task, or averaged over tasks. Always print your formula next to your number.
