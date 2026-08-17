# External research brief #2 — why don't the experts differentiate?

Companion to `EXTERNAL_RESEARCH_BRIEF.md`. Same audience: a session or human with unrestricted web access, ideally
able to open PDFs. Same conventions — every claim brought back should carry an evidence label:

| label | meaning |
|---|---|
| `[F]` | fetched in full — the paper was actually read |
| `[S]` | search-verified — title and URL are real, the claim comes from a search snippet |
| `[M]` | memory only — recollection, no source opened |
| `[R]` | derived from this repository |

`[M]` claims are the ones that have burned this project before. Prefer "I could not open this" over a confident
paraphrase.

**Network status in this container, re-measured 2026-08-17:** `WebSearch` works, `WebFetch` to any external host is
still `EGRESS_BLOCKED`. So everything in §1 below is `[S]` and is a *lead*, not a result.

---

## 0. Why this brief exists

Three separate interventions this session tried to make experts differ from one another. All three failed, and they
failed in the same shape — the intervention moved the loss slightly or not at all, and **specialization did not
improve at any setting**:

| intervention | what it does | result |
|---|---|---|
| `DIV_W` (0 / 0.02 / 0.1) | penalize correlation between expert outputs, weighted by routing mass | 1.971 / 1.932 / 2.103 b/B. The 0.02 gain (0.039) is exactly the replication floor. Every arm scored **below its own shuffled-assignment null** |
| `FAB_LR_OWN` | give each expert its own cyclical LR clocked on its own use | 2.023 vs 2.019 over three paired seeds — 0.0040 b/B, thirty times below the floor |
| `FAB_LR_CYCLE` | tune the wavelength of that per-expert schedule | flat across a ×64 sweep |

The shuffled-assignment null deserves emphasis, because it is the strongest single fact here. We compute a
specialization score, then recompute it after randomly permuting which expert handled which input. **The real
assignment does not beat the random one.** Whatever the router is doing, it is not sorting inputs by anything that
makes experts different from each other.

The question this brief wants answered is therefore not "which diversity regularizer should we use" but the one
underneath it: **under what conditions do MoE experts specialize at all, and is our setup one of them?**

---

## 1. Leads already surfaced by search — verify these, don't re-derive

Four threads came back with enough signal to be worth someone opening the actual papers.

### 1a. Specialization may be a property of the *encoder's* geometry, not of the routing mechanism

- *The Myth of Expert Specialization in MoEs: Why Routing Reflects Geometry, Not Necessarily Domain Expertise* —
  arXiv 2604.09780. `[S]`

The claim, as summarized: MoE routers are **linear maps**, so hidden-state similarity is both necessary and
sufficient to explain expert-usage similarity. Expert specialization is an emergent property of the representation
space, not of the routing architecture.

**Why this matters here, specifically.** Our router scores experts against a `gist` — a low-dimensional signature of
the input — through a linear key match. If that paper is right, then no amount of pressure applied to the *experts*
(which is what `DIV_W` does — it penalizes correlation between their outputs) can produce specialization, because
specialization is determined upstream, by whether the encoder's representation of two different domains is
separable in the first place. We would be pushing on the wrong end of the pipe.

**What to bring back:**
1. Does the paper actually establish this, or is it a weaker correlational claim? What is the experimental design?
2. Does it offer a *diagnostic* — a way to measure, before training a router, whether the representation space
   supports specialization at all?
3. If the representation is the bottleneck, what interventions do they or anyone else propose? (Contrastive
   pretraining of the encoder? Auxiliary domain-prediction loss on the gist? Something else?)

### 1b. Jointly-trained ensembles with a diversity term can cheat — "learner collusion"

- *Joint Training of Deep Ensembles Fails Due to Learner Collusion* — arXiv 2301.11323. `[S]`

This may be the precise failure mode of `DIV_W`. The reported mechanism: when you jointly train an ensemble under a
diversity penalty, the members can satisfy the diversity term by adding **large, mutually cancelling components** to
their outputs. Measured diversity goes up, the ensemble prediction is unchanged, and no useful specialization
occurred. The penalty is optimized without the thing it was a proxy for.

Our `DIV_W` is a negative-correlation-learning term in all but name, applied to jointly-trained experts, and our
diagnostic result is exactly "diversity pressure applied, specialization did not improve." That is what collusion
looks like from the outside.

**What to bring back:**
1. The precise mechanism and the diagnostic they use to *detect* collusion. If there is a measurable signature we
   can compute in our own run, that is the single most valuable thing in this brief.
2. Do they propose a fix, or only a diagnosis? Is there a formulation of a diversity penalty that is collusion-proof?
3. Related: *Generalized Negative Correlation Learning for Deep Ensembling* (arXiv 2011.02952) `[S]` — does it
   characterize when NCL helps vs. when it does nothing? Classical NCL is Liu & Yao 1999 (*Ensemble learning via
   negative correlation*, Neural Networks) — is the deep-network negative result well-established or contested?

### 1c. Representation collapse in sparse MoE routers, and the hypersphere fix

- *On the Representation Collapse of Sparse Mixture of Experts* — Chi et al., NeurIPS 2022, arXiv 2204.09179. `[S]`

Summarized claim: routing by dot product between token hidden states and expert embeddings **encourages tokens to
cluster around expert centroids**, which is itself a collapse pressure. Their fix (X-MoE) is to project hidden
vectors into a lower-dimensional space and **L2-normalize both the token representation and the expert embedding**,
so routing scores are computed on a low-dimensional hypersphere. Reported consistent gains on seven multilingual
benchmarks plus more consistent routing.

**Why this matters here.** We have a knob that is nearly this: `FAB_KEY_NORM`, currently defaulting to `0` — i.e.
**off**. If Chi et al. are right, we are running the exact configuration their paper identifies as collapse-prone.
This is the cheapest actionable item in the whole brief.

**What to bring back:**
1. Is the gain from the L2 normalization, the dimensionality reduction, or both? Their ablation, if they have one.
2. What dimensionality? Ours would be the gist width.
3. Does normalized routing interact badly with a load-balance loss, or with a temperature?
4. Follow-up: *Eigenvectors of Experts are Training-free Non-collapsing Routers* (arXiv 2605.30992) `[S]` — a router
   derived from the experts themselves rather than learned. Plausible? Applicable to a population that is being
   culled and replaced?

### 1d. Measuring specialization, and knowing early that it failed

- *Geometric Metrics for MoE Specialization: From Fisher Information to Early Failure Detection* — arXiv 2604.14500. `[S]`
- *MoE Routing Testbed: Studying Expert Specialization and Routing Behavior at Small Scale* — arXiv 2604.07030. `[S]`

The first reportedly defines a **Fisher Specialization Index (FSI)** with a practical guideline — target
`FSI > 0.6 × FSI_max`, and treat early plateauing as a signal of under-differentiation — plus an `FHS` measured at
10% of training with an intervention threshold. The second is explicitly a small-scale testbed, which is our regime.

**Why this matters here.** Our specialization measurement is home-grown (a score plus a shuffled-assignment null).
The null is a good idea and we should keep it. But a *published* metric with a published threshold would let us say
"our fabric is under-differentiated by an external standard" rather than "our number did not beat our null," and the
early-detection angle would let a 10%-of-training checkpoint kill a bad config instead of a full run.

**What to bring back:** the actual definitions of FSI and FHS, in enough detail to implement. Whether the thresholds
are scale-dependent. And from the testbed paper: **at what scale does specialization first appear**, in parameters,
tokens, expert count, and top-k — the numbers, not the narrative.

---

## 2. The questions search could not answer

These need someone who can read papers, and they are ordered by how much they would change what we do next.

### 2a. Is expert specialization emergent, or does it require explicit supervision?

The search returned both answers, which is exactly why it needs a real reader. On the emergent side: a
Mixture-of-Experts VLA action head reportedly decomposes tasks into reusable interpretable primitives with no
pre-specified decomposition (arXiv 2607.20771) `[S]`; *EMO: Pretraining Mixture of Experts for Emergent Modularity*
(arXiv 2605.06663) `[S]`. On the supervised side: *TEXAS: Task-Expert-Aware Supervision* (arXiv 2608.06396) `[S]`;
MoE with intermediate CTC supervision for accented speech (arXiv 2602.01967) `[S]`; MoELoRA using contrastive
learning to guide the experts (arXiv 2402.12851) `[S]`.

**The question to actually answer:** what distinguishes the settings where specialization emerges from the settings
where it has to be supervised? Candidate axes — scale, whether the task has a natural discrete decomposition,
whether inputs carry a domain label at all, top-k, expert granularity.

**Why it decides something for us.** We have domain labels. We train on `eng`, `py`, and others, and we know which
domain each window came from. If the literature says specialization at our scale needs supervision, then the right
move is an **auxiliary loss that makes routing predictable from the domain** — cheap, direct, and we already have
the label. If it says emergence is the norm and we are simply misconfigured, the right move is §1c and §1a instead.
These lead to completely different work, so this is the highest-value question in the brief.

### 2b. Does anyone grow an expert population during training, and does it work?

This project's cleanest experiment (four arms × three seeds, one knob apart) says **ramping to a large population is
catastrophic while starting at that population is fine**:

| arm | held-out b/B (mean of 3) | spread |
|---|---|---|
| growth off, 6 experts | 2.117 | 0.326 |
| **growth off, 2048 experts** | **1.999** | **0.080** |
| growth on, cap 64 | 2.091 | 0.180 |
| growth on, cap 4096 | 3.384 | 2.074 |

Size is not the problem. *Ramping to size* is. The entire effect is the interaction.

And the mechanism became visible this session: in the `DIV_W` runs, the log reads
`[fabric @ 48120] ramp -> grew 5 -> 415/4096 experts` on a run that **ended at step 48140**. Five experts created
twenty steps before the end. Use-age spanning 0..36131 across the population. The ramp never converges on this
schedule, so the fabric is permanently under construction and roughly half of it has barely been trained at any
moment — including at evaluation.

**What to bring back:**
1. Does the progressive/expandable-MoE literature exist, and does it report the same pathology? Search terms that
   might work: expandable MoE, progressive expert expansion, Net2Net-style widening for MoE, lifelong MoE, MoE with
   dynamic expert count.
2. If growing works elsewhere, **what do they do that we don't?** Specific candidates worth checking: is the new
   expert initialized as a *clone* of a parent rather than fresh noise; is there a warmup during which the newborn
   is routed to but its gradient is scaled down; is growth stopped well before the end of training; is the LR reset
   on expansion.
3. Is there any principled schedule for *when to stop growing*? Our ramp terminates on population size, which
   evidently never arrives.

### 2c. The tension between load balancing and specialization

We run a load-balance loss (`BAL_*`, decaying over `BAL_WARM` to a `BAL_FLOOR`) to stop early collapse onto a few
experts. It works — but a load-balance loss pushes toward *uniform* routing, and specialization is by definition
*non-uniform* routing. One search snippet put it sharply: tokens get discarded not because they are uninformative
but because they violate a throughput constraint, "actively preventing the specialization that motivates MoEs."

Our own numbers say the imbalance is real and large: at run level, 173 of 396 experts used, the top expert taking
23.4% of traffic, half of all traffic going to 8 experts.

**What to bring back:** is there a treatment of this tension — a balance loss that equalizes *capacity* without
equalizing *assignment*, or a schedule that trades balance for specialization as training proceeds? What does the
loss coefficient literature actually recommend, and how was it chosen (tuned, or inherited from Switch Transformer
and never revisited)?

### 2d. Evolutionary populations of experts — culling and replacement

We cull the worst experts by a fitness score and respawn from parents. `FAB_CULL_FRAC` is now 0.02. This is closer
to neuroevolution than to standard MoE, and it has an interaction nobody in the MoE literature would encounter:
**the router's keys are defined over a set that is being replaced underneath it.** Our own history recorded 10062
experts grown against 5969 culled to hold a steady 4096 — the population turned over about 1.5× continuously, with
a tenth of it freshly-initialized noise at any moment, while centroids and expert-embedding keys were defined over
exactly that churning set.

**What to bring back:** does anyone combine population-based methods (neuroevolution, PBT, NEAT-like speciation)
with a *learned router*, and how do they keep the router's representation stable across replacement? Is there prior
art on "the keys of a retrieval structure over a mutating population"? This may be better answered in the
continual-learning or the population-based-training literature than in the MoE literature.

### 2e. Is our reward-for-disagreement idea already known, and does it work?

The stated intent is to reward experts for disagreeing **conditional on the disagreement improving the output** —
not diversity for its own sake. That conditional is what distinguishes it from plain NCL, and it is also what makes
it hard: it needs a counterfactual (would the prediction have been better without this expert's contribution?).

**What to bring back:** prior art on *conditional* or *utility-weighted* diversity. Candidate framings to check —
diversity terms weighted by marginal contribution; Shapley-value or leave-one-out credit assignment in ensembles;
boosting, where the next learner is rewarded precisely for disagreeing with the current ensemble *on the examples it
gets wrong*. Boosting is the oldest and most successful version of "disagree, but usefully," and the question is
whether a boosting-style residual objective can be applied to a jointly-trained MoE without the collusion of §1b.

---

## 3. What we would do with each answer

Stated up front so the reader can prioritize.

| if the answer is | we would |
|---|---|
| specialization needs supervision at our scale (§2a) | add a domain-prediction auxiliary loss on routing. We already have the labels; this is a small change |
| the encoder's geometry is the bottleneck (§1a) | stop tuning `DIV_W` entirely and measure domain separability of the gist first |
| `DIV_W` is collusion (§1b) | remove it, or replace it with a collusion-proof formulation — and add the collusion diagnostic to the report |
| dot-product routing is collapse-prone (§1c) | flip `FAB_KEY_NORM` to 1 and re-measure. Cheapest item here |
| growth needs parent-cloning or a warmup (§2b) | fix growth rather than disabling it — `FAB_GROW` now defaults off, which sidesteps the problem instead of solving it |
| balance and specialization genuinely trade off (§2c) | schedule the balance coefficient against a specialization metric rather than against step count |
| conditional diversity has prior art (§2e) | implement the published version rather than inventing one |

---

## 4. Context the reader needs about this system

Enough to judge relevance; not a full description.

- **Scale.** Small. Held-out bits/byte in the 1.9–2.1 range on an English corpus whose order-1 entropy anchor is
  ~3.4–3.7 b/B. This is a research testbed, not a production LM, so small-scale findings are *more* relevant here
  than large-scale ones.
- **Experts.** Low-rank adapters, `A: (cap, d, r)` and `B: (cap, r, d)` with `B` zero-initialized, preallocated to a
  slot pool. Rank 4 by default. They are added to a base model's hidden state, not FFN replacements.
- **Routing.** Multi-hop by default (chained, `CHAIN_ROUTE=soc`): the router selects, the selected expert
  contributes, and the result can route again. Selection is a linear key match against a low-dimensional `gist` of
  the input. Top-k, k small.
- **Population dynamics.** Experts are culled by fitness and respawned from parents with mutation. Each expert has a
  **use-age** — a clock that ticks only when that expert is selected — which drives its grace period, its cull
  eligibility, and (until today) its own LR cycle.
- **The measurement bar.** Two runs of an *identical* configuration on this project have differed by up to
  **0.039 b/B**. Any reported effect smaller than that is noise. This has voided several of our own findings and
  should be applied to anything the literature reports too: ask what the paper's own replication spread was.
- **What we actually care about.** Language quality and continual learning without catastrophic forgetting. Expert
  differentiation is instrumental — it matters because a fabric of interchangeable experts cannot plausibly protect
  old domains from new ones. Answers that improve raw perplexity at the cost of making experts *less* separable are
  not what we are looking for.

---

## 5. Sources surfaced so far

All `[S]` — titles and URLs are real, claims are from search snippets, none of these has been opened.

- [The Myth of Expert Specialization in MoEs: Why Routing Reflects Geometry, Not Necessarily Domain Expertise](https://arxiv.org/abs/2604.09780)
- [Joint Training of Deep Ensembles Fails Due to Learner Collusion](https://arxiv.org/pdf/2301.11323)
- [On the Representation Collapse of Sparse Mixture of Experts](https://arxiv.org/abs/2204.09179)
- [Generalized Negative Correlation Learning for Deep Ensembling](https://arxiv.org/abs/2011.02952)
- [Geometric Metrics for MoE Specialization: From Fisher Information to Early Failure Detection](https://arxiv.org/abs/2604.14500)
- [MoE Routing Testbed: Studying Expert Specialization and Routing Behavior at Small Scale](https://arxiv.org/abs/2604.07030)
- [EMO: Pretraining Mixture of Experts for Emergent Modularity](https://arxiv.org/abs/2605.06663)
- [TEXAS: Task-Expert-Aware Supervision for Downstream Mixture-of-Experts LLM Adaptation](https://arxiv.org/abs/2608.06396)
- [Emergent Compositional Skills in Mixture-of-Experts VLAs](https://arxiv.org/abs/2607.20771)
- [MoELoRA: Contrastive Learning Guided Mixture of Experts on Parameter-Efficient Fine-Tuning](https://arxiv.org/abs/2402.12851)
- [Eigenvectors of Experts are Training-free Non-collapsing Routers](https://arxiv.org/abs/2605.30992)
- [Advancing Expert Specialization for Better MoE](https://openreview.net/forum?id=iydmH9boLb)
- [Ensemble learning via negative correlation (Liu & Yao 1999)](https://www.sciencedirect.com/science/article/abs/pii/S0893608099000738)
