# Q8 — Replay-buffer selection in continual learning

You were right that this field had to solve your problem. And it produced the thing you were
looking for in Q3 and didn't find: **class-balanced reservoir sampling is a per-source quota.**

---

## (a) Admission rules

### Reservoir sampling — the baseline for bounded store / unbounded stream

Vitter's algorithm, used as the memory-update rule in ER (Chaudhry et al. 2019), DER/DER++,
GSS, MIR, GCR, and essentially everything else:

```
for the i-th item of the stream, buffer size M:
    if i ≤ M:            store it
    else:                j ~ Uniform{1..i}
                         if j ≤ M:  buffer[j] ← item
                         else:      discard
```

Guarantee: after N items, every item seen is in the buffer with probability M/N, and the buffer
is a uniform sample of the stream so far. This is the principled answer to "bounded store,
unbounded stream" and it is one screenful of code.

### The property you actually asked about, stated exactly

**Yes — this is a mathematical consequence, and it is the answer to your question about an old
task's buffer share.**

Under reservoir sampling, the expected buffer share of a domain is its share of the *stream so
far*. If domain A supplied N_A items and the stream total is N, then

```
E[slots held by A] = M · N_A / N
```

So if a new domain streams **indefinitely**, N grows without bound while N_A is fixed, and

```
E[slots held by A]  →  0
```

The old domain is not evicted by a bad decision. It is diluted to zero by a correct one.
Reservoir sampling is *supposed* to do this — it is faithfully representing a stream in which
the old domain is a vanishing fraction. That is exactly wrong if your objective is retention
rather than representativeness.

**The literature states the failure mode in a related form.** The GSS paper (Aljundi et al.,
NeurIPS 2019, arXiv:1903.08671) frames it as: reservoir sampling makes the buffer follow the
already-seen data distribution, and **minor modes in the distribution with small probability
mass may fail to be represented**. An old domain under indefinite new-domain streaming *is* a
minor mode. Their proposed remedy in that discussion is coverage maximization using Euclidean
distance, which they then criticize as uninformative in high dimensions.

**Confidence: high** on the math; **high** on the GSS characterization, which I read.

### The fix: class-balanced / per-source reservoir

The standard remedy is to run reservoir sampling **per class or per source**, with quotas that
rebalance as new sources appear (a new source's quota is carved out of the largest existing
one, rather than out of everyone uniformly). This is what CBRS (class-balanced reservoir
sampling) does, and it is what iCaRL does structurally by keeping a fixed exemplar count per
class.

**This is the per-source quota you looked for in Q3 and I reported as absent from the retrieval
literature.** It is standard in replay-based CL. The two fields did not talk to each other. If
you want a citable precedent for reserving N slots per domain in a bounded store, it is here,
not in the kNN-LM/RAG literature.

**Confidence: moderate.** I did not read the CBRS paper directly this session; the per-class
structure of iCaRL I am confident about, the specific CBRS rebalancing rule I am reporting from
general knowledge and it should be verified before citing.

---

## (b) Eviction / selection rules

### GSS — Gradient-based Sample Selection (Aljundi et al., NeurIPS 2019)

**Criterion:** diversify the gradients of buffered samples. The paper's framing is that
continual learning is a constrained optimization problem — optimize loss on the current
example(s) without increasing loss on previously learned examples — and therefore **buffer
selection is a constraint reduction problem**. Keeping a sample whose gradient direction is
already represented by another buffered sample adds a redundant constraint.

GSS-Greedy scores a candidate by its **maximal cosine similarity to the gradients of a random
subset of buffered samples**, and prefers low-similarity (i.e. novel-direction) samples.

**Per-source? No — global.** It is source-agnostic by construction; it operates in gradient
space. It will *implicitly* preserve a distinct domain, because a distinct domain has distinct
gradient directions — which is arguably a better-motivated form of domain isolation than a
quota, since it protects what is *functionally* distinct rather than what is *labelled*
distinct. Worth considering for your Fabric.

### MIR — Maximally Interfered Retrieval (Aljundi et al., NeurIPS 2019)

**This is a retrieval rule, not an eviction rule.** Important distinction for you — it answers
"what do I replay," not "what do I keep." Admission is still reservoir sampling.

**Criterion:** take a virtual gradient step on the incoming batch to get estimated parameters
θ^v, then select the C buffered samples with the largest estimated **increase in loss** under
θ^v — the samples about to be forgotten.

Reported hyperparameters: C = 50 with the sMI-2 criterion for MNIST Split / Permuted MNIST;
M = 50, C = 50 with sMI-1 for CIFAR-10. Replay batch size fixed equal to the incoming batch
size (10). Evaluated on 25 examples for Mini-ImageNet, 50 for other datasets.

**Per-source? No — global.** It naturally concentrates replay on whichever domain is currently
being interfered with, which is a dynamic, self-targeting form of domain protection.

**Known limitation:** AdaER (arXiv:2308.03810) reports MIR failing in boundary scenarios where
τ = 1, and proposes combining example-interference and task-association buffers.

### Herding — iCaRL (Rebuffi et al., CVPR 2017)

**Criterion:** greedily select exemplars so that the running mean of the selected exemplars'
features best approximates the class mean feature vector. Select p_k to minimise
‖μ − (1/k)(φ(p_k) + Σ_{j<k} φ(p_j))‖.

**Per-source? Yes, per class, by construction.** iCaRL maintains a fixed number of exemplars
per class and shrinks the per-class allocation as classes accumulate. This is the cleanest
example in the file of a quota-structured bounded store.

### GCR — Gradient Coreset (Tiwari et al., CVPR 2022)

Selects a weighted subset whose summed gradient approximates the gradient over all data seen so
far. Uses reservoir sampling in the pipeline and adaptive sampling from a combined candidate
pool. Works with task boundaries or with "streaming boundaries or regular intervals of data
samples as boundaries," i.e. it can be made task-agnostic — relevant to you, since you don't
have clean domain boundaries.

---

## Summary table

| Method | Admission | Eviction | Retrieval | Per-source? |
|---|---|---|---|---|
| ER | reservoir | reservoir (implicit) | random | no |
| **CBRS / iCaRL herding** | per-class quota | per-class | — | **yes** |
| GSS | gradient-diversity | replaces most-redundant | random | no (implicit via gradient space) |
| MIR | reservoir | reservoir | **max estimated loss increase** | no (dynamic) |
| DER++ | reservoir | reservoir | random + logit matching | no |
| GCR | gradient coreset | coreset re-selection | adaptive | no |

Reported accuracies vary a lot by benchmark and buffer size, and the GCR paper's own table
shows ER (a plain reservoir baseline) beating GSS, GEM, iCaRL and MIR on Sequential CIFAR-10 at
several buffer sizes. **The simple baseline is competitive.** Read that the way you should read
TraceRetain and SIEVE: sophisticated selection wins in specific regimes, not generally.

---

## What this means for your design

1. **Your ad-hoc rule may be worse than reservoir sampling, and reservoir is trivial to
   implement.** Run it as a baseline. If your surprise gate doesn't beat uniform reservoir
   sampling on b/B, that's important to know and cheap to find out.

2. **But do not adopt plain reservoir if retention is your objective.** The dilution math above
   means it *guarantees* the failure mode you're worried about. Use per-source reservoir with
   quotas.

3. **The distinction between admission, eviction, and retrieval is load-bearing and your
   architecture currently conflates two of them.** You have a surprise gate (admission) and
   LRU-on-retrieval (eviction). You have no *retrieval selection* rule — you take cosine top-k.
   MIR says the choice of what to replay matters independently. In your setting the analogue is:
   should the kNN return the nearest entries, or the entries whose loss would most increase
   under the current update? That's a real design axis you haven't used.

4. **The strongest cross-field observation in this whole bundle:** replay buffers are read
   during training by construction, and that is why this field developed retrieval-selection
   rules (MIR) while the kNN-LM field did not (file 04: retrieval is inference-only there). You
   are building a system where the store *is* read during training. **You are in the replay-CL
   regime, not the kNN-LM regime, and you should be reading this literature as your primary
   reference rather than the semiparametric-LM one.** That is probably the single most useful
   reframing in this addendum.
