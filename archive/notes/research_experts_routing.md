# Mixture-of-Experts and Routed Expert Populations — Reference for the `Fabric` Design

**Date:** 2026-08-15
**Subject under comparison:** `self_organize.py`, `class Fabric` (lines ~1096–2217), plus `PlateauGrowth` (~2219) and the
per-expert learning-rate block in `main()` (~5098–5142).

---

## 0. Provenance and verification status

**Web access: partially available.**

- `WebSearch` **worked**. Every paper in Part A whose arXiv ID appears below was confirmed to exist by search, and the
  one-line characterisations of the method are drawn from the returned abstract/snippet text.
- `WebFetch` against `arxiv.org` was **blocked by the network egress proxy** (`EGRESS_BLOCKED`). So I could not read
  full texts. Nothing below is quoted from a full paper body.

Labelling convention used throughout:

| Tag | Meaning |
|---|---|
| **[S]** | Confirmed by a web search this session — title, authors/venue and the substance of the claim came back in the search result. |
| **[M]** | **From memory, unverified this session.** Treat numbers and fine detail with suspicion; the shape of the claim should be right. |
| **[I]** | Inference/judgement of mine, not a claim about any paper. |

A second caveat on recency: several search hits carried 2026 arXiv IDs (`26xx.xxxxx`). Those are real hits from this
session but I have only snippet-level knowledge of them, and they are recent enough that they are not settled results.
They are marked **[S, recent]**.

---

## 1. What `Fabric` actually is (so the comparison is grounded)

Read from the source, not summarised from the docstrings alone.

**The population.** `A: (cap, d, r)`, `B: (cap, r, d)`, preallocated to `FAB_NMAX` (default 4096), `r = FAB_RANK`
(default 8). An expert is the residual low-rank map `h + (h @ A_i) @ B_i`. `B` is zero-initialised, so an unused slot is
an *exact identity*. `n_live` grows into the preallocated cap; the tensors never change identity, so the optimizer's
parameter references stay valid. Cost `2·NMAX·d·r`.

**Routing.** Two summed terms, both producing logits over `N` live experts plus a HALT column:
1. **Grounded / centroid**: `cosine(normalize(gist), normalize(cent[i])) / route_t`, `route_t = 0.1`. `cent` is a
   **buffer**, EMA'd under `no_grad` toward the signatures each expert served (`ground_update`, `CENT_EMA = 0.02`,
   top-`FAB_CENT_TOPK = 8` experts move, share-weighted).
2. **Learned**: `cosine(q_route(gist) + qextra, K_i) / route_t`, where **`K_i` and `SRC_i` are not free parameters** —
   they are produced by `eemb`, an MLP over the expert's *entire flattened adapter* `[A_i ; B_i]` (`2·d·r` numbers).
   Routing identity is a function of the expert's weights.

`gist` is a **per-window domain signature** from a separate `SigEncoder`, detached — not the token hidden state.
`hproj(h.mean(1))` injects the current state into the query on the chaining paths.

**A hypernetwork on the other side.** `edec` inverts `eemb` (tied by `ae_loss`, an autoencoder round trip plus a
variance/decorrelation term). `spawn_from` reads the router's query as *"the expert I want"*, and if nothing in the
population is closer than `spawn_mult × (population's own median nearest-neighbour distance)`, it **decodes the query
into actual weights** and instantiates that expert.

**Three forward modes.**
- `society()`: one hop, top-`k` experts by routing mass computed per window, each decodes its own logits via `head`,
  blended at the **prediction** level over the top `ENS_K = 2`.
- `forward()` with `CHAIN_ROUTE=transition` (legacy): multi-hop. A learned transition
  `R[n→m] = softmax((q_route(gist) + SRC[n] + ctrl(summary)) · K[m])` moves mass expert→expert. HALT is an **absorbing**
  operator. Under `CHAIN_VOTE=1` the mass that halts at hop *t* takes hop *t*'s prediction.
- `forward()` with `CHAIN_ROUTE=soc` (**default**): re-route from scratch every round with the society router, current
  state in the query, no transition matrix and no `SRC`. Stopping is a **per-round probability**:
  `alive ← alive·(1−p_halt)`, output is `Σ_t alive_t · p_halt,t · logits_t`.

**Population dynamics.**
- **Growth**: `PlateauGrowth` fires on loss plateau *or regression burst*; `grow()` replicates a parent sampled by
  fitness (marginal contribution, else utilisation) from a **relevance shortlist** (nearest centroids to the birth
  signature), with a per-parent birth **quota** (`FAB_PARENT_MAX = 0.20`), heavy-tailed **mutation** scaled to the
  parent's own std, and **crossover of whole rank slices** (`FAB_XOVER = 0.35`).
- **Culling**: two routes. (a) sustained-error, at any occupancy, using a **fast/slow error EMA pair** so an expert
  adapting to a shift is protected rather than culled; (b) bottom `cull_frac` by **utilisation**, only under capacity
  pressure > 0.75, with grace, and protected by positive **marginal contribution** (leave-one-out) or better-than-
  population competence. A first-time cull candidate gets a **rescue mutation** instead of removal.
- **Forced exploration**: `FAB_EXPLORE = 0.15` of *rows* have their last top-k slot hard-overwritten with a uniformly
  chosen expert from the coldest `max(8, N/16)` by utilisation. Training passes only.
- **Load balance**: `fab_bal(w) = N · Σ_i mean_b(w_bi)²`, weighted by `max(0, 1 − step/BAL_WARM)` — i.e. **decayed to
  exactly zero by step 4000**. Plus a hard **breadth cap** (`dom_ban`): an expert already serving ≥ `EXP_DOM_FRAC`
  (10%) of live domains is masked to `-inf` for any new domain.
- **Per-expert learning rates** (`FAB_LR_OWN`): each expert on its own cosine schedule clocked from its birth step,
  implemented by **rescaling the realised optimizer update** (`W ← W_pre + ratio·(W_post − W_pre)`), clamped at ×4.

---

# PART A — Exhaustive list of expert / routing architectures in the literature

Grouped by family. For each: **routing rule**, **expert granularity**, **load balancing**, **known failure modes**.

## A.1 The classical mixtures

### Original MoE — Jacobs, Jordan, Nowlan & Hinton (1991); Hierarchical MoE — Jordan & Jacobs (1994) **[M]**
- **Routing**: a softmax **gating network** over the full input produces a probability per expert; the output is the
  **convex combination of every expert's prediction**, `Σ_i g_i(x) · f_i(x)`. Dense — all experts run.
- **Granularity**: each expert is a *complete predictor* for the task. Hierarchical MoE nests gates into a tree.
- **Load balance**: none needed and none provided — training is an EM-flavoured competition; the gate's likelihood term
  naturally splits the input space.
- **Failure modes**: **winner-take-all collapse** (one expert absorbs all the gate mass and the rest never receive
  gradient) is the original, named pathology; cost is linear in the number of experts because nothing is sparse; and
  the tree in HME is fixed a priori.
- **This is the family Fabric's `society()` mode belongs to** — mixing at the *prediction* level, not the hidden state.

### Product of Experts — Hinton (2002) **[M]**
Multiplicative rather than additive combination (`∏ p_i(x)^{w_i}`, renormalised). Sharpens rather than blurs; needs
normalisation tricks. Almost entirely absent from modern LLM MoE. Relevant only as the contrast to Fabric's additive
prediction-level blend.

## A.2 Sparse conditional computation — the modern line

### Sparsely-Gated MoE — Shazeer et al., ICLR 2017 — [arXiv:1701.06538](https://arxiv.org/abs/1701.06538) **[S]**
The paper that started modern MoE. Up to thousands of FFN sub-networks, >1000× capacity increase at minor compute cost.
- **Routing**: **noisy top-k gating**. `G(x) = softmax(topk(x·W_g + StandardNormal()·softplus(x·W_noise), k))`. The
  tunable Gaussian noise is *explicitly there to aid load balancing and exploration* **[M on the exact form; S on the
  paper]**.
- **Granularity**: a whole FFN per expert, one MoE layer between LSTM layers, k = 2 or 4.
- **Load balance**: **two auxiliary losses** — an *importance* loss (CV² of the summed gate values) and a *load* loss
  (CV² of a smooth estimate of the number of examples per expert). The distinction matters: importance can be equal
  while load is not.
- **Failure modes**: the paper names the **self-reinforcing gate** — an expert that wins early gets more gradient, gets
  better, wins more. That is why noise + aux loss exist. Also: severe communication cost at scale; batch shrinkage per
  expert (each expert sees `k·B/N` examples).
- **Direct relevance to Fabric**: this is the canonical treatment of exploration *and* the canonical statement of the
  failure Fabric's `FAB_EXPLORE` is aimed at.

### GShard — Lepikhin et al., 2020 — [arXiv:2006.16668](https://arxiv.org/abs/2006.16668) **[S for ID/title; M for detail]**
- **Routing**: **top-2** token→expert. Second expert kept with probability proportional to its gate weight. Adds a
  **capacity factor** `C`: each expert accepts at most `C · tokens/N`; overflow tokens are **dropped** (pass through the
  residual unchanged). Local group dispatching so balancing is per-group, not global.
- **Granularity**: FFN per expert; MoE replaces every other FFN layer.
- **Load balance**: differentiable auxiliary loss ≈ `N · Σ_i f_i · P_i` (fraction dispatched × mean gate prob) plus the
  hard capacity cap.
- **Failure modes**: **token dropping** at low capacity factor materially hurts quality; capacity factor is a
  quality/throughput knob with no free setting; all-to-all communication dominates at scale.

### Switch Transformer — Fedus, Zoph & Shazeer, 2021 — [arXiv:2101.03961](https://arxiv.org/abs/2101.03961) **[S]**
First stable trillion-parameter MoE; per-token compute roughly constant.
- **Routing**: **top-1**. Simplification of GShard; the gate value multiplies the expert output so the router stays
  differentiable through the chosen expert only.
- **Granularity**: FFN per expert, up to thousands.
- **Load balance**: the now-standard aux loss `α · N · Σ_i f_i · P_i` with `α ≈ 0.01`; plus capacity factor with
  dropping.
- **Failure modes** **[S for the existence of the instability discussion, M for detail]**: **training instability in
  bf16/low precision** driven by router logit magnitude — fixed by selective fp32 in the router; **expert collapse /
  dead experts** if the aux loss weight is too low; fine-tuning overfits far more readily than the dense equivalent.

### ST-MoE — Zoph et al., 2022 — "Designing Effective Sparse Expert Models" **[S for the z-loss attribution]**
- **Contribution**: the **router z-loss**, `(1/B)Σ_b (log Σ_i e^{x_i})²`, penalising router logit magnitude. Identified
  *router logit growth* as the primary cause of large-MoE instability. Also the standard reference for MoE fine-tuning
  recipes and expert-dropout.
- **Failure modes it names**: instability from unbounded logits; quality/stability tension (things that stabilise often
  cost quality).
- **Direct relevance to Fabric**: `route_t = 0.1` multiplies routing logits by 10. That is the *opposite* direction from
  z-loss. See Part C.

### GLaM — Du et al., 2021 — [arXiv:2112.06905](https://arxiv.org/abs/2112.06905) **[S for ID/title; M for detail]**
1.2T total / ~97B activated, top-2 routing, 64 experts per MoE layer, MoE in every other layer. Notable for the
**energy/FLOPs argument**: ~1/3 the training energy of GPT-3 at better zero/one/few-shot quality. Routing and balancing
are GShard's. Failure modes: same family; the paper is an existence proof of the compute argument rather than a routing
innovation.

### Mixtral 8x7B — Jiang et al., 2024 — [arXiv:2401.04088](https://arxiv.org/abs/2401.04088) **[S for ID/title; M for detail]**
- **Routing**: top-2 of 8 experts per layer, every layer. 47B total, 13B active.
- **Granularity**: standard SwiGLU FFN per expert — deliberately **coarse** (only 8).
- **Load balance**: standard aux loss.
- **Notable empirical finding [M]**: the paper's own analysis found **little topical/domain specialisation** among
  experts — routing correlated with *syntax and position* far more than with subject matter, and consecutive tokens
  were often routed identically. This is an important negative result for anyone assuming experts become domain
  specialists on their own.

### DeepSeekMoE — Dai et al., ACL 2024 — [arXiv:2401.06066](https://arxiv.org/abs/2401.06066) **[S]**
Two ideas that are now near-universal:
- **Fine-grained expert segmentation**: split each FFN's intermediate dimension into *m* pieces to get *m·N* smaller
  experts and activate *m·k* of them, at constant parameter count and constant FLOPs. Rationale: with more, smaller
  experts, the number of achievable *combinations* explodes, so knowledge can be decomposed more finely and each expert
  can retain a higher level of specialisation. **[S]**
- **Shared expert isolation**: reserve a small number of experts that **every token always goes through**, to absorb
  common knowledge and stop the routed experts from all redundantly learning it.
- **Load balance**: expert-level *and* device-level aux losses. Later (V3) replaced by the loss-free bias, below.
- **Failure modes addressed**: knowledge hybridity (each coarse expert must be a jack of all trades) and knowledge
  redundancy (every expert relearns the same common patterns).

### DeepSeek-V2 / V3 — [arXiv:2405.04434](https://arxiv.org/abs/2405.04434) **[S for V2]**
Carry DeepSeekMoE forward at 236B/671B scale; V3 adopts auxiliary-loss-free balancing (below) and node-limited routing.

### Auxiliary-Loss-Free Load Balancing — Wang et al., 2024 — [arXiv:2408.15664](https://arxiv.org/abs/2408.15664) **[S]**
- **Routing**: before top-k, add a **per-expert bias** `b_i` to the routing scores. `b_i` is updated by a simple rule
  from the expert's *recent load* (increment if under-loaded, decrement if over-loaded); the bias affects **selection
  only**, not the gate value used to weight the output.
- **Why it matters**: an aux loss injects **interference gradients** into training that are orthogonal to the LM
  objective and cap achievable quality. Removing them raised the quality ceiling while keeping balance. Validated to 3B
  and used to train DeepSeek-V3. **[S]**
- **Status**: this is, as of now, the **default recommendation** for load balancing in new MoE work. **[I]**

### Expert Choice routing — Zhou et al., NeurIPS 2022 — [arXiv:2202.09368](https://arxiv.org/abs/2202.09368) **[S]**
- **Routing**: **invert the argmax**. Instead of each token picking its top-k experts, **each expert picks its top-k
  tokens** from the batch. A token may therefore be processed by a variable number of experts (including zero).
- **Load balance**: **perfect by construction** — every expert gets exactly its bucket size. No aux loss, no capacity
  factor, no dropping in the usual sense.
- **Results**: >2× faster convergence than Switch top-1 and GShard top-2; better on 7 of 11 GLUE/SuperGLUE tasks than
  dense T5 at lower activation cost. **[S]**
- **Failure modes**: it is **not causal** — expert-side top-k over a batch leaks information across positions, so it is
  awkward or invalid for autoregressive decoding without modification; and some tokens receive *no* expert at all.

### BASE Layers — Lewis et al., ICML 2021 — [arXiv:2103.16716](https://arxiv.org/abs/2103.16716) **[S]**
- **Routing**: formulate token→expert assignment as a **linear assignment problem** and solve it optimally (a
  parallelisable **auction algorithm**) so every expert receives exactly the same number of tokens.
- **Load balance**: perfect by construction, and — the paper's selling point — **no new hyperparameters and no auxiliary
  loss**. **[S]**
- **Failure modes** **[M]**: the assignment solve is a global, non-local operation (train/inference mismatch — at
  inference you fall back to greedy argmax); optimality is per-batch, so assignment is unstable step to step; solving
  cost is nontrivial.

### Hash Layers — Roller et al., NeurIPS 2021 — [arXiv:2106.04426](https://arxiv.org/abs/2106.04426) **[S]**
- **Routing**: **no learned router at all**. Hash the current token ID into a fixed expert bucket.
- **Load balance**: **balanced hashes precomputed from token frequency** — balance is a property of the hash, not of
  training. No routing parameters, no aux loss, no assignment algorithm.
- **Result**: *outperforms or is competitive with* Switch Transformers and BASE Layers; the best-performing hashes were
  **balanced random hashes on the most local features**. **[S]**
- **Why this is the most important negative result in the field [I]**: if a fixed random hash matches a learned router,
  then whatever a learned router is buying, it is not much — at least at the scales and tasks tested. Any argument that
  a *cleverer* router is the key lever has to get past this paper.

### Soft MoE — Puigcerver et al., ICLR 2024 — [arXiv:2308.00951](https://arxiv.org/abs/2308.00951) **[S]**
- **Routing**: **fully differentiable, no hard assignment**. Each expert receives a fixed number of *slots*; each slot
  is a learned **weighted combination of all input tokens** (soft dispatch), and outputs are soft-combined back.
- **Granularity**: FFN per expert, but the *unit of assignment* is a slot, not a token.
- **Load balance**: perfect by construction; there is nothing to balance.
- **Results**: Soft MoE H/14 with 128 experts × 16 layers has **>40× the parameters of ViT-H/14 at +2% inference time**
  and substantially better quality; beats both Token Choice and Expert Choice on vision. **[S]**
- **Failure modes**: like Expert Choice, it mixes across the whole token set, so it is **not directly usable for causal
  decoding** — it is a vision/encoder result. Cost is linear in slots × experts.

### Mixture-of-Depths (MoD) — Raposo et al., 2024 — [arXiv:2404.02258](https://arxiv.org/abs/2404.02258) **[S]**
- **Routing**: routes over **layers rather than experts**. A static per-layer budget caps the number of tokens `k` that
  participate in that block's attention+MLP; a top-k router selects them; the rest take the residual path around the
  block.
- **Load balance**: **by construction** — the budget is a fixed `k`, chosen statically, so the compute graph is static.
- **Failure modes** **[M]**: top-k over a sequence is non-causal at inference, so the paper needs an auxiliary
  predictor to decide per token online; gains are FLOP-efficiency gains rather than quality gains at equal params.
- **Relevance to Fabric**: MoD is "should this token be computed at all", which is precisely what Fabric's HALT operator
  is, with the difference that MoD makes it a *static budget* and Fabric makes it a *learned probability*.

### Mixture-of-Recursions — 2025 — [arXiv:2507.10524](https://arxiv.org/html/2507.10524v1) **[S, recent]**
Token-level adaptive recursion depth over a shared block. Combines parameter sharing with per-token dynamic depth.
Structurally very close to Fabric's `soc`-loop-with-HALT.

## A.3 Retrieval-style and very-large expert populations

### Product-Key Memory — Lample et al., NeurIPS 2019 — [arXiv:1907.05242](https://arxiv.org/abs/1907.05242) **[S]**
- **Routing**: a query is split in half; each half does exact k-NN against a small **sub-key** codebook; the Cartesian
  product of the two sub-key shortlists gives the top-k of a **huge** key set at `O(√M)` cost instead of `O(M)`.
- **Granularity**: an "expert" is a **single memory value vector** — the finest possible grain. Up to a billion
  parameters at negligible compute.
- **Load balance**: **batch normalisation on the query** is the trick used to keep key usage from collapsing onto a few
  memories. **[M]**
- **Result**: a 12-layer memory-augmented model beat a 24-layer baseline and was 2× faster at inference. **[S]**
- **Failure modes**: memory **under-utilisation** (a large fraction of slots never accessed) is the named problem;
  sensitive to the query normalisation.

### PEER — "Mixture of A Million Experts", Xu Owen He (DeepMind), 2024 — [arXiv:2407.04153](https://arxiv.org/abs/2407.04153) **[S]**
- **Routing**: product-key retrieval (as above) over **>1 million tiny experts**.
- **Granularity**: each expert is a **single-neuron MLP** (a rank-1 map: one down-projection vector, one activation, one
  up-projection vector). Retrieves and combines ~16 of them.
- **Motivation**: the **fine-grained MoE scaling law** — higher granularity gives better performance — but existing MoE
  is capped at a small expert count by compute/optimisation. PEER is the attempt to go all the way. **[S]**
- **Result**: better performance-compute trade-off than dense FFWs and coarse-grained MoEs on LM. **[S]**
- **Failure modes** **[I/M]**: sparse gradient per expert (each expert sees vanishingly few tokens), and the retrieval
  index has the same under-utilisation risk as product-key memory. Not, to my knowledge, reproduced at frontier scale.
- **This is the single closest architectural relative to Fabric's population design.**

### Ultra-Sparse Memory Network (UltraMem) — 2024 — [arXiv:2411.12364](https://arxiv.org/pdf/2411.12364) **[S, snippet only]**
Memory-layer line, addressing PKM's memory-access cost at inference.

### Memory Layers at Scale — Meta, 2024 — [arXiv:2412.09764](https://arxiv.org/html/2412.09764v1) **[S, snippet only]**
Scales trainable product-key memory layers to LLM pretraining scale; argues memory layers beat dense and MoE baselines
on factual tasks at matched compute.

### Fine-Grained MoE Scaling Laws — Krajewski et al., 2024 — [arXiv:2402.07871](https://arxiv.org/pdf/2402.07871) **[S]**
Establishes **granularity** as a first-class scaling variable alongside parameters and tokens: for a fixed compute
budget there is an optimal granularity, and it is finer than the field was using. This is the theoretical backing for
DeepSeekMoE and PEER.

## A.4 Adapter / low-rank experts (PEFT ∩ MoE)

### LoRA — Hu et al., 2021 **[M]**
`W + (α/r)·B·A`, with `A` random Gaussian and **`B` zero**, so the adapted model at step 0 is **exactly the base
model**. Rank `r` from 1 to 64. Not routed — a single always-on adapter. **The zero-init of `B` is the direct ancestor
of Fabric's identity-born expert.**

### Adapters — Houlsby et al., 2019; AdapterFusion — Pfeiffer et al., EACL 2021 — [arXiv:2005.00247](https://arxiv.org/abs/2005.00247) **[S for AdapterFusion]**
- **AdapterFusion routing**: a **two-stage** scheme. Stage 1 trains N task-specific adapters independently. Stage 2
  freezes them and learns an **attention** mechanism (query from the layer's hidden state, keys/values from each
  adapter's output) that composes them **non-destructively**. **[S]**
- **Granularity**: one adapter per *task*, hand-assigned, not discovered.
- **Load balance**: none — every adapter is computed, the fusion attention is dense.
- **Failure modes**: cost is linear in adapters; requires a pre-existing task decomposition; **[M]** later work found
  fusion attention often concentrates on one or two adapters.
- **Relevance**: AdapterFusion's attention over adapter outputs is *architecturally* Fabric's `society()` — a dense
  attention over a bank of low-rank modules — but with a fixed, externally-supplied population.

### MoV / MoLORA — Zadouri et al., 2023 — [arXiv:2309.05444](https://arxiv.org/abs/2309.05444) **[S]**
"Pushing Mixture of Experts to the Limit." Makes the **experts themselves parameter-efficient**: MoLORA routes over a
bank of LoRA modules; MoV routes over a bank of (IA)³-style scaling **vectors**. Reaches parity with full fine-tuning
while updating **<1% of parameters**. **[S]** This is the clearest precedent for "the expert *is* a low-rank adapter."

### LoRAMoE, MoELoRA, MoLA ("Higher Layers Need More LoRA Experts", [arXiv:2402.08562](https://arxiv.org/pdf/2402.08562)), SMoRA ("Each Rank Could be an Expert", [arXiv:2501.15103](https://arxiv.org/html/2501.15103v1)) **[S for existence; M for detail]**
A large and still-growing family. Notable for Fabric: **SMoRA treats each individual rank of a LoRA as a separately
routable expert** — i.e. exactly Fabric's crossover unit (a rank-1 slice `A[:,i] ⊗ B[i,:]`) elevated to the routing
unit. **MoLA** finds the optimal number of experts is **not uniform across depth** — higher layers want more.

### EPnG — "Adaptive Expert Prune-and-Grow for Parameter-Efficient MoE Fine-tuning" — [arXiv:2607.01789](https://arxiv.org/pdf/2607.01789) **[S, recent]**
Reallocates LoRA capacity **during fine-tuning** using expert importance derived from router gate probabilities:
**prunes under-utilised experts and grows high-importance ones by rank growth**, at a fixed parameter budget. This is
the nearest published relative to Fabric's `manage()` + `grow()` loop.

## A.5 Routing-by-agreement / iterative routing

### Dynamic Routing Between Capsules — Sabour, Frosst & Hinton, 2017 — [arXiv:1710.09829](https://arxiv.org/abs/1710.09829) **[S]**
- **Routing**: **iterative routing-by-agreement**. A lower capsule predicts the higher capsule's pose via a
  transformation matrix; coupling coefficients are updated over ~3 iterations by the **agreement** (dot product) between
  a prediction and the current higher-capsule output. Softmax over *outgoing* couplings, so a lower capsule's mass is
  conserved and distributed.
- **Granularity**: a capsule is a vector-valued unit; whole-part hierarchy is the intended semantics.
- **Load balance**: implicit — the outgoing-softmax normalisation is a per-source conservation constraint.
- **Failure modes**: **does not scale** — the routing iterations are expensive and the approach never transferred beyond
  small image datasets; agreement routing is unstable/degenerate in deeper stacks; the result on MNIST/MultiMNIST did
  not carry to ImageNet-scale problems.
- **Relevance**: Fabric's transition matrix `R[n→m]` with mass conservation and multiple hops is **structurally a
  routing-by-agreement scheme**, and Fabric's measured failure (mass concentrates as it flows; hop 2 carries almost no
  independent information) is the same class of pathology capsules hit.

### Chain-of-Experts (CoE) — Wang et al., 2025 — [arXiv:2506.18945](https://arxiv.org/abs/2506.18945) **[S]**
**The closest published work to Fabric's chaining mode, and it validates the `soc` variant over the `transition` one.**
- **Routing**: **sequential expert communication *within* a layer**. Tokens are processed iteratively across a chain of
  experts, and — critically — **a dedicated router runs at each iteration**, so tokens **re-evaluate and select
  different experts each round** rather than being statically assigned or handed along a learned successor edge.
- **Result**: on math reasoning, validation loss 1.20 → 1.12 vs standard MoE at fixed compute; **2× iterations matches
  3× expert selections in width, at 17.6–42% less memory**. Benefits attributed to the *iterative residual structure*
  and to *enhanced expert specialisation empowered by iterative routing*. **[S]**
- Code: <https://github.com/ZihanWang314/coe>

### Universal Transformer — Dehghani et al., 2018 — [arXiv:1807.03819](https://arxiv.org/html/1807.03819v3); ACT — Graves, 2016; PonderNet — Banino et al., 2021 — [arXiv:2107.05407](https://arxiv.org/pdf/2107.05407) **[S]**
- **ACT**: a **halting unit** emits a per-step probability; computation stops when cumulative halting probability crosses
  `1−ε`; output is the halting-probability-weighted mean of the per-step states; a **ponder cost** penalises depth.
- **PonderNet**: reformulates halting **probabilistically** — a per-step Bernoulli continue/stop, giving a proper
  distribution over halting steps, trained by a weighted per-step loss **plus a KL term to a geometric prior** that
  controls expected depth. **[S for the reformulation; M for the KL/geometric detail]**
- **Failure modes of ACT** **[M]**: the halting objective is ill-posed — the model collapses to always-halt or
  always-continue depending on the ponder-cost weight, and the weight has an extremely narrow useful range. PonderNet
  exists precisely because of this.
- **Fabric's `soc` loop `alive ← alive·(1−p_halt)` with per-round output weighting is PonderNet's formulation,
  independently arrived at.**

## A.6 Representation-geometry and prototype routing

### X-MoE — "On the Representation Collapse of Sparse Mixture of Experts", Chi et al., NeurIPS 2022 — [arXiv:2204.09179](https://arxiv.org/abs/2204.09179) **[S]**
- **The finding**: learning a router **encourages token representations to cluster around expert centroids**, which is a
  trend toward **representation collapse** — the hidden states lose the variation the rest of the model needs.
- **The fix**: estimate routing scores on a **low-dimensional hypersphere** — project the token down, L2-normalise both
  token and expert embedding, take the cosine, divide by a **learnable temperature**. Gains across seven multilingual
  benchmarks, and more **consistent** routing (fewer assignment flips). **[S]**
- **This is directly load-bearing for Fabric**: Fabric's `FAB_KEY_NORM` + `route_t` is X-MoE's dimension-reduced cosine
  router, and Fabric's centroid EMA is *deliberately doing* the thing X-MoE identifies as the collapse mechanism.

### Latent Prototype Routing — 2025 — [arXiv:2506.21328](https://arxiv.org/abs/2506.21328) **[S, recent]**
Explicit **prototype-based routing** framework, presented as a generalisation of existing routers, aimed at **near-
perfect load balancing** without hurting downstream quality. Motivated by the observation that in deployed MoE systems
only a small subset of experts is consistently activated.

### Equifinality in Mixture of Experts — 2026 — [arXiv:2604.14419](https://arxiv.org/abs/2604.14419) **[S, recent — treat as preliminary]**
**The most directly threatening result for Fabric's central bet, and it must be read.**
- **Setup**: 62 controlled experiments on WikiText-103 at 76–84M params trained to convergence (50K steps, 1.64B
  tokens). The authors built a geometric ST-MoE using **cosine-similarity routing against learned centroids in a
  low-dimensional space with `d_space = 64`** — the same construction *and the same dimensionality* as Fabric's
  `SIG_D = 64` grounded router.
- **Result**: **routing topology does not determine asymptotic perplexity** — five cosine-routing variants were
  statistically equivalent within a 1-PPL margin.
- **Mechanism offered**: **"routing absorption"** — the ~80:1 parameter asymmetry between expert weights and gate
  parameters means experts continuously **co-adapt to compensate for whatever routing mask is imposed**.
- **Stated scope limit**: the claim is for *language modelling perplexity*. Concurrent work on vision/diffusion MoE
  reports routing topology mattering critically there. **[S]**

### Related recent geometry work **[S, recent — snippet only]**
- "Routers Learn the Geometry of Their Experts: Geometric Coupling in Sparse MoE" — [arXiv:2605.12476](https://arxiv.org/pdf/2605.12476). Routers empirically align to expert weight geometry *as an emergent property*.
- "Geometric Routing Enables Causal Expert Control in MoE" — [arXiv:2604.14434](https://arxiv.org/pdf/2604.14434).
- "Routing by Analogy: kNN-Augmented Expert Assignment" — [arXiv:2601.02144](https://arxiv.org/abs/2601.02144).

## A.7 Growing, pruning and upcycling expert populations

### Net2Net (2015) / bert2BERT / progressive stacking / Firefly neural architecture descent **[M]**
The **function-preserving growth** family. Net2Net widens a layer by *splitting* a neuron into copies and halving the
outgoing weights, so the function is exactly preserved at the moment of growth; Net2Deeper inserts identity layers.
Firefly grows by picking the *steepest-descent* new neuron directions. Core lesson from this literature: **growth must
be function-preserving at the instant of growth, and the newly added parameters need their own (higher) learning
rate/warmup or they never differentiate.**

### Dynamically Expandable Networks — Yoon et al., ICLR 2018 — [arXiv:1708.01547](https://arxiv.org/pdf/1708.01547) **[S]**
Continual learning. **Selectively retrains** neurons relevant to the new task; **if the loss fails to drop below a
threshold, expands capacity top-down**, then removes unnecessary neurons by group-sparsity, and **splits/duplicates**
neurons whose semantics drifted too far. **This is the closest published relative to `PlateauGrowth` + `manage()`** —
loss-triggered growth plus sparsity-driven culling — but in a task-incremental continual-learning setting, not
single-run pretraining.

### Progressive Neural Networks — Rusu et al., 2016 **[S via snippet]**
Adds a fresh column per task with lateral connections to frozen prior columns. Named drawback: **unbounded,
monotonic growth** — infeasible long-run.

### Sparse Upcycling — Komatsuzaki et al., ICLR 2023 — [arXiv:2212.05055](https://arxiv.org/abs/2212.05055) **[S]**
Initialise an MoE from a **dense checkpoint** by **cloning the dense MLP into every expert** and adding a fresh router;
continue pretraining so the clones gradually specialise. Beats dense counterparts at ~50% of the dense sunk cost. **[S]**
Follow-up **Drop-Upcycling** partially re-initialises the clones because **exact clones fail to diversify**. **[M]**

### EMO — "Frustratingly Easy Progressive Training of Extendable MoE" — [arXiv:2605.13247](https://arxiv.org/html/2605.13247v2) **[S, recent]**
Treats MoE capacity as **expandable memory** and grows the expert pool over the course of training; matches a
fixed-expert setup while improving wall-clock and GPU cost.

### "Beyond Sunk Costs: Orthogonal Growth of Mixture-of-Experts" — [arXiv:2510.08008](https://arxiv.org/pdf/2510.08008) **[S, recent]**
Grows width by adding experts, and finds it **crucial to proportionally increase the number of activated experts** so
that tokens are actually routed into the new capacity. Directly relevant: growing `N` without growing `k` starves the
newborns.

### Expert pruning **[S for existence]**
- "A Provably Effective Method for Pruning Experts in Fine-tuned Sparse MoE" — [arXiv:2405.16646](https://arxiv.org/html/2405.16646v1)
- "Cluster-Driven Expert Pruning for MoE LLMs" — [arXiv:2504.07807](https://arxiv.org/pdf/2504.07807)
- **Dynamic Expert Clustering** — [arXiv:2510.02345](https://arxiv.org/html/2510.02345v1): periodically **regroups
  experts during training** using a **fused metric of parameter similarity and activation similarity**, described as one
  of the first frameworks to use the router's semantic embedding capacity to **dynamically reconfigure the architecture
  during training**. **[S, recent]**

Uniform pattern in this literature: **pruning is done after training or during fine-tuning, with importance scores, and
it is a compression technique.** Culling as an *online evolutionary pressure during pretraining* is not standard.

## A.8 Miscellaneous routing schemes worth knowing

| Method | Routing rule | Note |
|---|---|---|
| **StableMoE** **[M]** | Two-stage: learn a router, then **freeze it** (distil into a lightweight token→expert map) and train experts against the frozen assignment. | Directly opposes online exploration: the diagnosis is that *routing fluctuation* is itself the problem. |
| **THOR** **[M]** | **Stochastic** expert selection — a random expert per input, with a consistency regulariser. | No router at all; nearly free balance. |
| **Task-level / domain MoE** (DEMix layers, BTM/c-BTM) **[M]** | Route by **known domain label**, one expert per corpus domain. Experts trained fully independently, combined at inference. | Fabric's `gist`/domain signature routing is much closer to this than to token routing. |
| **Input Domain Aware MoE** — [arXiv:2510.16448](https://arxiv.org/pdf/2510.16448) **[S, recent]** | Decouples routing decisions from task optimisation. | |
| **Route Experts by Sequence, not by Token** — [arXiv:2511.06494](https://arxiv.org/pdf/2511.06494) **[S, recent]** | Sequence-granularity routing. | The published defence of Fabric's per-window routing granularity. |
| **SMEAR / Soft Merging of Experts with Adaptive Routing** — [arXiv:2306.03745](https://arxiv.org/pdf/2306.03745) **[S]** | Instead of routing to experts, **merge the experts' *parameters*** by the gate weights and run the single merged expert. Fully differentiable, no discrete choice. | Directly relevant to Fabric: merging low-rank adapters by gate weight is cheap (`Σ w_i A_i`, `Σ w_i B_i` is *not* the same as `Σ w_i A_iB_i`, but merging in the rank-concatenated form is). |
| **ReMoE** — [arXiv:2412.14711](https://arxiv.org/pdf/2412.14711) **[S]** | Fully differentiable MoE with **ReLU routing** — sparsity from the ReLU zeroing gates rather than from a top-k. | Removes the non-differentiable-index problem Fabric names in its STAGED DEPTH block. |
| **Unchosen Experts Can Contribute Too** — [arXiv:2405.14507](https://arxiv.org/pdf/2405.14507) **[S]** | Self-contrast between chosen and unchosen expert outputs at inference. | Evidence that the non-top-k experts carry usable signal. |
| **ModuleFormer** — [arXiv:2306.04640](https://arxiv.org/abs/2306.04640) **[S]** | Modularity emerging from MoE; sparse experts + sparse attention heads. | |
| **Tutel / MegaBlocks / DeepSpeed-MoE** **[M]** | Systems work: dropless MoE via block-sparse matmuls, dynamic capacity. | MegaBlocks' point — **capacity factors and token dropping are an artefact of dense-matmul implementations, not a necessity** — is worth internalising. |

---

# PART B — What is actually used, ranked

Ranking by *what a competent team would build today for a frontier-ish LLM*, with the reason.

### 1. Top-k token-choice routing over fine-grained FFN experts + a small number of always-on shared experts, balanced by a loss-free per-expert bias
**Concretely: the DeepSeek-V3 / Qwen-MoE recipe.** This is the current default. **[S for each component; I for the ranking]**
- *Why it won*: top-k token choice is **causal** (unlike Expert Choice and Soft MoE), trivially implementable, and
  compatible with expert parallelism. Fine-graining is backed by an explicit **scaling law** ([arXiv:2402.07871]) and
  by DeepSeekMoE's specialisation argument. Shared experts remove the redundancy every routed expert would otherwise
  have to relearn. The loss-free bias removes the aux loss's **interference gradients**, which is a measured quality
  gain, not a convenience.
- *Typical settings* **[M]**: 64–256 routed experts per layer, top-4 to top-8, 1–2 shared, MoE in most or all layers.

### 2. Classic top-2 (or top-1) over coarse FFN experts + aux load-balance loss + router z-loss
**GShard / Switch / GLaM / Mixtral.** Still the most *deployed* configuration by volume, because it is what the open
weights are. Simple, extremely well understood, well supported by every serving stack. Loses to #1 on quality per FLOP.

### 3. Expert Choice routing
Best available answer when **causality is not required** — encoders, vision, retrieval towers, reward models. Perfect
balance by construction, >2× convergence speedup, no capacity-factor tuning. **[S]** Its adoption is limited almost
entirely by the causality problem.

### 4. Soft MoE
The strongest result in **vision** MoE (>40× params at +2% inference time, beating both Token Choice and Expert Choice
**[S]**). Fully differentiable, nothing to balance, no dropped tokens. Same causality ceiling as #3.

### 5. Low-rank / adapter experts (MoLORA, LoRAMoE, SMoRA, and the whole MoE-PEFT family)
The **dominant approach for adaptation** rather than pretraining. Parity with full fine-tuning at <1% of parameters
**[S]**. If you are building a routed expert population on top of a frozen or mostly-frozen base — which is what Fabric
is — **this is the family you are in, and it is a healthy, active one.**

### 6. Memory-layer / retrieval-style million-expert designs (PKM, PEER, UltraMem, Memory Layers at Scale)
The **research frontier for extreme granularity**. Real published wins on the performance-compute trade-off, real
under-utilisation risk, not yet standard in a frontier production model. **[S for the papers; I for the status]**

### 7. Mixture-of-Depths and adaptive-depth routing
Increasingly seen as a **complement** to MoE (route over layers *and* over experts) rather than a replacement. Practical
adoption limited by the causal-top-k problem and by the fact that the gains are FLOP-efficiency rather than quality.

### 8. Hash / random / frozen routing
**Not used in practice — and that is the anomaly.** Hash Layers were competitive with Switch and BASE **[S]**, and it
never displaced learned routing. Whether that is because learned routing is genuinely better at scale, or because the
field never re-ran the comparison at scale, is **not settled**. Keep it as a *baseline you must beat*.

### 9. BASE layers / optimal-assignment routing
Elegant, principled, largely abandoned — the train/inference assignment mismatch and the solver cost were not worth it.

### 10. Iterative / chained / capsule-style routing
**Historically the graveyard** (capsules), **currently reviving** (Chain-of-Experts, Mixture-of-Recursions). The
reviving version differs from the dead one in a specific and important way: **it re-routes from scratch each iteration
rather than following learned successor edges.** See Part C.

---

# PART C — Direct comparison to `Fabric`

Verdicts: **SUPPORTED** (literature independently arrived at, or explicitly validated, the same choice) ·
**CONTRADICTED** (literature tested something equivalent and it lost, or literature identifies this exact thing as a
failure mode) · **UNTESTED** (I found nothing that has run this) · **MIXED**.

---

## C.1 Low-rank adapters as the unit of expertise — `h + (h@A)@B`, `r = 8`

**Verdict: SUPPORTED, strongly, and this is the least risky choice in the whole design.**

- MoLORA/MoV ([arXiv:2309.05444], **[S]**) is exactly this — a routed bank of LoRA modules — and reaches full-fine-tune
  parity at <1% of parameters. LoRAMoE / MoELoRA / MoLA / SMoRA are the same family.
- Granularity is the *right* direction per the fine-grained MoE scaling law ([arXiv:2402.07871], **[S]**), DeepSeekMoE
  fine-grained segmentation **[S]**, and PEER **[S]**.
- PEER goes further than Fabric: its experts are **rank-1** singleton MLPs, and it runs **>10⁶** of them successfully.
  So `r=8` at `NMAX=4096` is comfortably inside the region the literature says works.
- **Where Fabric differs and it is untested**: standard MoE experts are **FFNs at a specific layer** replacing that
  layer's MLP. Fabric's experts are **residual adapters applied to the whole hidden state at one point**, sitting
  outside the LM's layer stack, and they are *identity-plus-delta* rather than the whole computation. That is
  AdapterFusion's placement with MoE's routing. **[I]** It is a defensible hybrid, but no paper I found evaluates
  precisely this.
- **One concrete gap**: nobody in the low-rank-expert literature uses `r=8` with a *shared* population across all
  depths. MoLA ([arXiv:2402.08562], **[S]**) found the optimal expert count is **depth-dependent** — higher layers want
  more. Fabric has one population and one insertion point, so it cannot express that.

**Actionable**: the rank-slice crossover in `grow()` is, unknowingly, SMoRA's insight (each rank is a semantically
self-contained unit). That is a genuine point of contact worth checking against [arXiv:2501.15103].

---

## C.2 Identity-initialised newborns (`B = 0`)

**Verdict: MIXED — SUPPORTED as a stability mechanism, CONTRADICTED as a birth strategy in a competitive population.
The codebase already discovered both halves independently.**

- **The supported half**: zero-init of the up-projection is *the* standard device for non-disruptive insertion. LoRA
  zeroes `B` **[M]**; LLaMA-Adapter uses a **zero-initialised learnable gate** so the adaptation contributes nothing at
  step 0 and its magnitude grows during training ([arXiv:2303.16199], **[S]**); AdapterTune zeroes the up-projection
  matrix outright ([arXiv:2603.14706], **[S, recent]**); ReZero/Fixup/SkipInit are the same idea for residual branches
  **[M]**. Net2Net's whole framing is **function-preserving growth**. Fabric's stated rationale ("adding a node never
  disrupts what already works") is precisely the literature's rationale.
- **The contradicted half**: in all of those cases the zero-initialised module is **the only one, and it is guaranteed
  gradient**. In a *routed population* it is not. An identity expert computes nothing, therefore earns no routing mass,
  therefore gets no gradient, therefore stays an identity — the **dead-expert trap**, which Fabric's own comment
  documents empirically (*"4096 experts, ONE of them carrying 75% of the mass, 4095 blank identities"*). The literature
  agrees loudly: Sparse Upcycling ([arXiv:2212.05055], **[S]**) **clones the trained dense MLP into every expert**
  rather than zero-initialising, precisely so every expert starts competent; "Orthogonal Growth of MoE"
  ([arXiv:2510.08008], **[S]**) finds you must **also raise `k`** so tokens actually reach new capacity.
- **And there is a third result Fabric should know**: *exact* clones fail to diversify — Drop-Upcycling **[M]** exists
  to add partial re-initialisation for that reason. Fabric's `FAB_MUT` heavy-tailed mutation and `FAB_XOVER` crossover
  are the same fix, arrived at from the evolutionary side rather than the upcycling side. **This is a real
  convergence and it is evidence the current `FAB_REPLICATE=1` default is right.**

**Actionable**: the current design (replicate-and-perturb by default, `B=0` only when there is no parent) is the
literature-supported configuration. The zero-init path should be treated as a fallback, not as the principled choice
the comment presents it as.

---

## C.3 Centroid / prototype routing (grounded cosine to an EMA'd per-expert centroid) + a learned bilinear term

**Verdict: MIXED, and the most important section here. The mechanism is supported; the *premise that it is the lever*
is challenged by a directly comparable experiment.**

**Supported:**
- Cosine routing against learned expert centroids in a **low-dimensional space with L2 normalisation** is exactly
  X-MoE's fix for representation collapse ([arXiv:2204.09179], **[S]**). Fabric's `FAB_KEY_NORM` + `route_t` is X-MoE's
  normalised-cosine-with-temperature router. **Fabric independently re-derived a NeurIPS'22 result.**
- Prototype routing as a *load-balancing* device is Latent Prototype Routing ([arXiv:2506.21328], **[S, recent]**).
- Non-learnable EMA centroids (online k-means over routed hidden states, replacing learned router weights) has been
  tried — a search snippet describes exactly this construction. **[S, snippet only — I could not verify the source
  paper or its result.]**
- "Routers Learn the Geometry of Their Experts" ([arXiv:2605.12476], **[S, recent]**) reports that routers *emergently*
  align with expert geometry. Fabric hardcodes that alignment. That is a coherent design, not a fringe one.

**Challenged, hard:**
- **X-MoE's actual finding is that routing *causes* clustering around expert centroids and that this is the collapse
  mechanism.** X-MoE's fix is to make the routing score *not* a raw high-dimensional dot product; it is **not** an
  endorsement of driving the centroids toward the traffic. Fabric's `ground_update` explicitly moves each centroid
  toward what it served, which is a **positive feedback loop on exactly the quantity X-MoE identifies as dangerous**.
  Fabric's `FAB_DISCOVER` rule (novel signature → move the *coldest* expert's centroid) is the only counter-pressure,
  and it fires only past a hard novelty threshold.
- **The Equifinality result** ([arXiv:2604.14419], **[S, recent]**): 62 controlled runs, cosine routing against learned
  centroids at **`d_space = 64` — the same construction and same dimension as `SIG_D=64`** — found **five cosine-routing
  variants statistically equivalent in perplexity within 1 PPL**, attributed to **"routing absorption"**: experts
  co-adapt to compensate for whatever routing is imposed, because there are ~80× more expert parameters than gate
  parameters. If that generalises, then the entire routing-design axis Fabric is optimising — grounded vs learned,
  region weight, temperature, key normalisation — is **not where the quality is**. It is recent and unreplicated, but
  it is the single most important paper for this project to read and to try to falsify.

**Untested (genuinely novel in Fabric):**
- **Summing two routers** (grounded cosine + learned bilinear) and letting them compete. I found no MoE work that does
  this. Fabric already instruments it (`_rmix` records the std of each term) — that instrumentation is the right
  response and should be treated as a first-class experiment, not a diagnostic.
- **Routing on an external per-window domain signature** rather than on the residual stream. This is closer to DEMix /
  domain-MoE **[M]** and to "Route Experts by Sequence, not by Token" ([arXiv:2511.06494], **[S, recent]**) than to any
  mainstream MoE. Two consequences worth stating plainly: (a) it decouples routing from the actual computation, which
  `hproj` only partially repairs, and (b) it is **much coarser** — one routing decision per window instead of per
  token. Mixtral's own analysis found expert assignment correlates with **syntax and position, not topic** **[M]** —
  which, if it holds here, means a *topic* signature is routing on the wrong variable.

**Actionable, in priority order:**
1. Run the Hash Layers baseline. Replace the whole router with a fixed balanced hash of the domain id and measure. If
   it matches, the router is not the lever, and Equifinality is confirmed on this system.
2. Add X-MoE's **learnable** temperature instead of the fixed `route_t = 0.1`.
3. Consider making the centroids a **learned parameter with gradient** rather than a no-grad EMA buffer, and A/B it.
   Every method in Part B learns its router end-to-end.

---

## C.4 Routing identity derived from the expert's own weights (`eemb`) and expert synthesis from the router's query (`edec`, `spawn_from`)

**Verdict: UNTESTED. This is the most genuinely novel thing in `Fabric`, and correspondingly the least de-risked.**

- **Nothing I found routes by embedding an expert's full weight tensor.** The nearest points of contact:
  - "Dynamic Expert Clustering" ([arXiv:2510.02345], **[S, recent]**) regroups experts online using a **fused metric of
    parameter similarity and activation similarity** — so parameter-space expert identity *is* used in the literature,
    but for clustering, not as the routing key.
  - "Routers Learn the Geometry of Their Experts" ([arXiv:2605.12476], **[S, recent]**) says this alignment emerges by
    itself. **This is a mild argument against `eemb`: if a free learned key converges to the weight geometry anyway,
    `eemb` buys you the convergence rate and an inductive bias, at `O(N · 2dr · hid)` per refresh.** That is a real cost
    Fabric already documents; the literature suggests the benefit may be smaller than assumed.
  - `edec` is a **hypernetwork** producing adapter weights from a latent code — HyperNetworks (Ha et al., 2016) **[M]**,
    hypernetwork-generated adapters (HyperFormer) **[M]**, LoRA-Gen ([arXiv:2506.11638], **[S, recent]**, generates
    LoRA weights online from a description). **The generation of adapters by hypernetwork is well-precedented; using
    the *router's own query* as the latent and instantiating a new population member from it is not.**
- The properties Fabric claims fall out of `eemb` — a replicated child is near its parent in routing space; a mutating
  expert moves its own key; a culled slot cannot leave a stale identity — are real and are genuinely hard to get any
  other way. **[I]** No literature contradicts them.
- **The risk the literature does flag**: embedding networks over similar inputs collapse. Fabric found this (identity
  nearest-neighbour distance measured **0.000** — total collapse) and added `_var_cov`. This is the VICReg
  variance/covariance regulariser **[M]**, correctly applied. Keep the instrumentation permanently; this failure is
  silent and it disables spawning, specialisation measurement, and routing discrimination simultaneously.

**Actionable**: the ablation that settles `eemb` is `FAB_DERIVE_IDS=0` (free `K_p`/`SRC_p`) at matched steps. It exists.
Run it, because the geometric-coupling result predicts a small or null difference.

---

## C.5 Multi-hop chaining: transition matrix with `SRC` marks, vs the `soc` loop

**Verdict: the transition-matrix mode is CONTRADICTED. The `soc` loop (the current default) is SUPPORTED by
Chain-of-Experts. Fabric's own measurements and CoE agree on the same mechanism.**

- **Chain-of-Experts** ([arXiv:2506.18945], **[S]**) is the same architecture as Fabric's `soc` loop and it works:
  sequential expert communication within a layer, **a dedicated router at each iteration**, tokens **re-evaluate and
  select different experts each round**. Result: val loss 1.20 → 1.12 vs standard MoE at fixed compute; **2× iterations
  ≈ 3× width in expert selections, at 17.6–42% less memory**; benefits attributed to the iterative residual structure
  and to **iterative routing improving expert specialisation**.
- **The distinguishing variable is exactly the one Fabric measured.** CoE re-routes from scratch; Fabric's transition
  matrix follows learned successor edges from `SRC[holder]`. Fabric measured `H(hop1 | hop0)` at **0.005–0.058 bits**
  under the transition matrix versus **0.533 bits over 202k transitions** under the soc loop. That is a clean
  replication of CoE's design rationale, arrived at from the opposite direction.
- **The transition-matrix form is a routing-by-agreement scheme** (mass conservation, per-source outgoing softmax,
  multiple iterations), and capsule networks ([arXiv:1710.09829], **[S]**) are the cautionary tale: agreement routing
  did not scale and degenerates in depth. Fabric's observed pathology — mass concentrates as it flows, so each hop's
  top-k is drawn from a distribution the previous hop already sharpened; 8% of experts reached under chaining vs 25%
  under society — is that same degeneration.
- **The `N^D` orderings / non-differentiable-index problem** Fabric names in its STAGED DEPTH block is real and is a
  known open problem. The literature's answers are: (a) re-route each step so no ordering has to be learned (CoE); (b)
  make routing differentiable so gradients can say "go elsewhere" — **ReMoE**'s ReLU routing ([arXiv:2412.14711],
  **[S]**), **Soft MoE**'s soft dispatch ([arXiv:2308.00951], **[S]**), **SMEAR**'s parameter merging
  ([arXiv:2306.03745], **[S]**). Fabric's three attempted fixes (per-hop supervision, staged depth, state-in-query) are
  none of these, and all three measured neutral-to-worse — consistent with the field's experience that **per-hop credit
  assignment is not the fix; removing the discrete choice is.**

**Actionable:**
1. Keep `CHAIN_ROUTE=soc` as the default. It is the configuration with published support.
2. `SMEAR`-style merging is cheap for low-rank experts and would make the whole chain differentiable end-to-end: merge
   the selected `A_i`/`B_i` by gate weight (rank-concatenate, or merge in the `r·k` space) and apply once per hop
   instead of computing `k` adapters and mixing outputs. This is a *directly applicable* untried idea from the
   literature.
3. Fabric's ordering metric `H(hop1 | hop0)` is the right one and I did not find it used in CoE's evaluation. That is a
   contribution.

---

## C.6 HALT — an absorbing operator / per-round stop probability, adaptive depth, ponder

**Verdict: SUPPORTED. Fabric has independently re-derived PonderNet, and the failure modes it hit are the exact ones
this literature documents.**

- **ACT** (Graves 2016) uses a **halting unit** per step, stops when cumulative halting probability crosses `1−ε`,
  outputs the halting-weighted mean of per-step states, and charges a **ponder cost**. **Universal Transformer**
  ([arXiv:1807.03819], **[S]**) puts ACT on a weight-shared Transformer. **MoD** ([arXiv:2404.02258], **[S]**) is the
  static-budget version.
- **Fabric's `transition` mode with `CHAIN_VOTE` is ACT**: absorbing HALT, per-hop prediction weighted by newly halted
  mass. **Fabric's `soc` loop is PonderNet**: `alive ← alive·(1−p_halt)`, output `Σ_t alive_t·p_t·logits_t`, convex by
  construction, with the *never-halted* remainder taking the last round. That is PonderNet's formulation exactly.
- **The failure Fabric measured — `halt` mass 0.76 with routed depth 0.24 of 4, and `PONDER=0.01` measuring 0.0000 in
  all 18 arms — is ACT's canonical pathology.** The halting objective is ill-posed; the ponder-cost weight has a very
  narrow useful range and the model collapses to always-halt or always-continue outside it. **[M]** PonderNet exists
  because of this.
- **What Fabric is missing relative to PonderNet**: PonderNet regularises the halting distribution with a **KL to a
  geometric prior** with a target expected depth, which is far better behaved than a scalar ponder cost. **[S for the
  probabilistic reformulation; M for the KL/geometric-prior detail.]** Fabric instead uses a **hard clamp**
  (`halt_max = 0.9`). The clamp is a reasonable barrier against the absorbing-halt trap, but it does not *shape* the
  depth distribution — it only truncates it.
- Fabric's justification for `halt_max` ("at halt=1 the experts receive no gradient, and an expert that receives no
  gradient can never become worth routing to") is the same argument as Shazeer's noisy gating. Correct.

**Actionable**: replace or supplement `halt_max` + `PONDER` with PonderNet's KL-to-geometric-prior term, parameterised
by a **target expected depth**. It is a small change and it converts an unstable knob into a legible one.

---

## C.7 Society mode — ensembling at the prediction level

**Verdict: SUPPORTED as the oldest form of MoE; CONTRADICTED as modern practice, for cost reasons Fabric already
encountered.**

- `Σ_i w_i · head(norm(o_i))` **is the original Jacobs/Jordan MoE**: a mixture over each expert's *complete prediction*,
  weighted by a gate. **[M]** It is also, structurally, AdapterFusion's composition ([arXiv:2005.00247], **[S]**) —
  attention over a bank of low-rank modules — and a weighted deep ensemble.
- **Nobody in the modern LLM MoE line mixes at the prediction level**, and the reason is arithmetic: each expert's
  decode costs `B·L·V`. Fabric hit this and capped it at `ENS_K = 2`. That cap is the whole story — a "society" of 4096
  that can only ever have 2 members vote is a top-2 mixture with extra bookkeeping. **[I]**
- **But**: Fabric's grid found society **beat** chaining outright, and chaining lost to `FABRIC=0`. That is a real
  measurement on this system and it should be weighted above the literature's preference, which is driven by an
  efficiency constraint (vocabulary-sized decodes) that a research testbed does not have to respect.
- The mechanism the literature would offer for *why* society won: society gives **every expert an independent gradient
  path from the loss**, while a composed walk dilutes one cross-entropy back through every later hop's LayerNorm and
  mixture. That is the "deep supervision" argument, and it is why prediction-level mixing is the easier optimisation
  problem. **[I]**

---

## C.8 Growing the population during training, on loss plateau / regression

**Verdict: MIXED — growth during training is SUPPORTED; the *plateau/regression trigger* is supported only from the
continual-learning literature, not from MoE pretraining.**

- **Supported**: EMO ([arXiv:2605.13247], **[S, recent]**) grows the expert pool during training and matches
  fixed-expert training at better wall-clock; Orthogonal Growth ([arXiv:2510.08008], **[S, recent]**) grows expert
  width in a converged MoE; Sparse Upcycling ([arXiv:2212.05055], **[S]**) is a one-shot growth event; Net2Net /
  bert2BERT / progressive stacking are the function-preserving-growth family **[M]**.
- **The trigger is the difference.** Every MoE growth paper I found uses a **predetermined schedule** (grow at step X,
  or once, from a dense checkpoint). **Loss-triggered growth is a continual-learning idea**: DEN ([arXiv:1708.01547],
  **[S]**) expands capacity precisely when *"selective retraining fails to obtain desired loss below a set threshold"*.
  So `PlateauGrowth` has a clear intellectual ancestor — just not in MoE.
- **Growing on a *regression burst* specifically is UNTESTED** as far as I can find. It is a sensible response to
  distribution shift in a streaming setting, and Fabric's setting *is* streaming with domain phases, so this may be a
  genuinely correct adaptation. **[I]** But note the feedback loop Fabric's own comment names (a rising loss grows the
  population, and a growing population transiently raises the loss).
- **The literature has one hard, actionable warning Fabric may be violating**: Orthogonal Growth found it **crucial to
  increase the number of *activated* experts proportionally when adding experts** — otherwise tokens never reach the new
  capacity. Fabric grows `N` (`n_live`) but `chain_k` / `ENS_K` are **fixed constants** (8 and 2). Every newborn is
  competing for a slot in a top-8 whose width never grows. `FAB_EXPLORE` is the only mechanism forcing traffic to new
  capacity, and it draws by *low utilisation*, not by *recency of birth*.

**Actionable**: make `chain_k` scale with `n_live` (e.g. `k ∝ √N` or a fixed activated fraction), and/or add a birth
grace period during which a newborn is guaranteed some routing mass. This is a specific, literature-backed change.

---

## C.9 Culling during training, with protection for load-bearing experts

**Verdict: MIXED — expert removal is SUPPORTED but almost exclusively as *post-hoc compression*. Online culling during
pretraining is essentially UNTESTED, and there is a literature reason to be nervous.**

- **What exists**: expert pruning with importance scores ([arXiv:2405.16646], **[S]**), cluster-driven pruning
  ([arXiv:2504.07807], **[S]**), and **EPnG** ([arXiv:2607.01789], **[S, recent]**) which prunes and grows *during
  fine-tuning* at fixed budget using **router gate probabilities** as the importance signal. DEN prunes with
  group-sparsity regularisation during continual learning **[S]**.
- **Fabric's importance signal is better than the literature's default.** EPnG uses router gate probability, which is
  utilisation. Fabric uses **leave-one-out marginal contribution** as the primary signal with utilisation as a fallback,
  and explicitly protects the useful-but-rare (*"rarely called is the bottom of a utilization ranking, and it is also
  what a niche expert looks like"*). That distinction is correct and the pruning literature routinely gets it wrong.
  **[I]** Leave-one-out is expensive, which is why the literature uses proxies — Fabric can afford it because the
  society path makes it free.
- **The fast/slow error EMA pair** — protecting an expert whose error is *rising* because it is adapting to a shift, and
  culling one whose error is *persistently* elevated — is, as far as I can find, **UNTESTED in MoE**. It is a standard
  device in change-point detection and in drift-aware streaming learners **[M]**. It is a good idea and I have no
  literature to point at.
- **The reason to be nervous**: Fabric's own `remove()` docstring states it — *"in an entangled mixture it damages
  everyone."* The MoE pruning literature only ever prunes a **converged** model where the damage can be measured and
  the model can be healed by fine-tuning. Mid-pretraining removal is an irreversible, unmeasured edit to a system that
  is still co-adapting, and Equifinality's "routing absorption" ([arXiv:2604.14419], **[S, recent]**) says experts *do*
  continuously co-adapt to whatever structure is imposed — which cuts both ways: it may heal the wound, or it may mean
  the surviving experts have already absorbed dependencies on the one you removed.
- **The `rescue` mutation** (one large jump before removal, grace clock reset, history retained) is a nice idea with a
  clear analogue in simulated annealing and in DEN's neuron-splitting, and no direct MoE precedent I found. **[I]**

**Actionable**: instrument the *cost* of a cull directly — measure held-out bpb immediately before and ~1k steps after
each removal. Nothing in the literature will tell you whether online culling is safe on this system; only that
measurement will.

---

## C.10 Forced exploration (`FAB_EXPLORE = 0.15`, hard overwrite of a top-k slot with a cold expert)

**Verdict: MIXED — the *motivation* is exactly Shazeer's and is canonical. The *implementation* is more aggressive than
anything in the literature, is biased rather than noise-based, and does not anneal.**

- **The motivation is textbook.** Shazeer's original noisy top-k gating ([arXiv:1701.06538], **[S]**) adds tunable
  Gaussian noise to the gate logits *before* the top-k, explicitly for load balancing and exploration, because of the
  **self-reinforcing gate**. Fabric's comment (*"an expert outside the top-k is not merely unused — it is frozen, and
  can never improve into contention... the difference between a population and a leaderboard"*) is the same argument.
- **The implementation differs in a way that matters.** Literature exploration perturbs the **scores**, so:
  (a) routing stays a (noisy) function of the input and remains unbiased in expectation as noise → 0;
  (b) the perturbation magnitude is learnable/annealable;
  (c) the chosen expert's *gate weight* is still its own score.
  Fabric instead **hard-overwrites** `idx[row, -1]` with a **uniformly sampled** member of the coldest `max(8, N/16)`.
  The chosen expert gets *the displaced expert's slot but its own real mass* (`_cv[_r,-1] = nm[_r, _ci[_r,-1]]` — good,
  that part is right), but the *selection* is off-policy, uncorrelated with the input, and constant at 15% for the
  entire run.
- **15% is high and it never decays.** **[I]** For comparison: Switch/GShard/Mixtral use **no** exploration noise at
  all, relying on the aux loss; ST-MoE recommends expert dropout rather than forced routing **[M]**. **StableMoE**
  **[M]** goes the *opposite* way — it argues routing *fluctuation* is itself the problem and freezes the router
  entirely in stage 2. Fabric is at one extreme of an axis whose other extreme also has published support.
- **ProbMoE** ([arXiv:2606.01509], **[S, recent]**) does *stochastic exploration of expert subsets with informative
  router updates while preserving sparse execution* — that is the modern, principled version of what Fabric is doing by
  hand, and it is worth reading.
- **Fabric already found the sharpest edge of this**: exploration was corrupting **evaluation** (15% of scored windows
  routed to a deliberately sub-optimal cold expert) and, worse, **consuming the global RNG stream**, so measurement
  cadence changed which bytes the model trained on. That is fixed by `learn_regions`. Good. **[I] It is a warning that
  the mechanism has more reach than it looks like it does.**

**Actionable, concrete:**
1. **Anneal it.** `FAB_EXPLORE` should decay — like `BAL_WARM` already does — from 0.15 toward ~0.01. The exploration
   argument is strongest early (symmetry breaking) and weakest late (it is just noise on a converged router).
2. **Consider the score-perturbation form instead**: add `σ·softplus(·)·N(0,1)` to the routing logits before the top-k
   (Shazeer's exact mechanism), with `σ` annealed. It gets the same gradient reach without the off-policy bias and
   without touching the RNG in a way that reorders the data stream.
3. **Bias the cold set toward *young* experts, not just low-utilisation ones.** Low utilisation and recent birth are
   different things, and the newborn-starvation problem (C.8) is specifically about age.

---

## C.11 Per-expert learning rates, clocked from birth

**Verdict: mostly UNTESTED in MoE; the underlying *principle* is SUPPORTED by the network-growth literature.**

- **I found no MoE paper with per-expert learning-rate schedules.** **[I]**
- **The principle is standard in growth literature** **[M]**: Net2Net, bert2BERT, progressive stacking and sparse
  upcycling all have to answer "what learning rate do the newly added parameters get", and the answers are always some
  form of a fresh warmup or an elevated rate for the new parameters. Fabric's stated motivation — *"an expert born at
  step 40000 is born into whatever rate the run has decayed to and can never move far enough to differentiate, which is
  why late births arrive dead"* — is exactly the problem that literature is solving. The reasoning is sound.
- Adjacent supported practices: layer-wise LR decay (ULMFiT, ELECTRA) **[M]**; µP/µTransfer's per-tensor LR scaling by
  width **[M]**; LoRA's `α/r` scaling **[M]**.
- **The implementation is clever and the stated reasoning about Adam is correct**: scaling a row's *gradient* does not
  scale its step under Adam (the update `m̂/(√v̂+ε)` is invariant to a constant factor on the gradient), so rescaling
  the **realised update** is the right move. That is a real insight and I have not seen it written down anywhere.
- **Three caveats worth recording** **[I]**:
  1. Adam's second-moment state `v` is per-element, so it is *not* corrupted by the rescale — but it is also *unaware*
     of it, so an expert held at ×0.25 for a long stretch has a `v` sized for a step it never took. The effective
     schedule is therefore not exactly the cosine you wrote.
  2. Weight decay, gradient clipping and any optimizer-level norm are applied to `A` and `B` **as whole tensors**, so
     they are inherently global across the population. Per-expert LR does not make the optimizer per-expert.
  3. The clone-per-step (`n_live·d·r` floats × 2) is cheap now but is `O(N)` — at `NMAX = 10⁴–10⁶` this becomes the
     dominant per-step allocation.

---

## C.12 Load balancing — `fab_bal` decayed to zero, plus the hard breadth cap

**Verdict: the aux-loss form is SUPPORTED but the *decay to zero* is CONTRADICTED by practice. The hard breadth cap is
the form the field has explicitly moved away from.**

- `fab_bal(w) = N · Σ_i mean_b(w_bi)²` is the **importance/`P_i²` variant** of the Shazeer/GShard/Switch auxiliary
  loss. Switch's canonical form is `α·N·Σ_i f_i·P_i` — the product of the **dispatch fraction** and the **mean gate
  probability** — and the distinction is deliberate: Shazeer's original paper separates *importance* from *load*
  precisely because equal importance does not imply equal load. **[M]** Fabric's form only sees importance.
- **`BAL_WARM = 4000`, decaying the weight to exactly zero, is a departure.** Every production MoE keeps balancing
  pressure on for the **entire run**, because collapse is not a transient early-training risk — it is the equilibrium
  the self-reinforcing gate drifts toward at any time. **[I, grounded in the fact that Switch/GShard/GLaM/DeepSeek all
  keep it on.]** Fabric's rationale (equal load is not the goal; specialisation is) is a real tension the field
  acknowledges, and the field's answer to that exact tension is:
- **The loss-free bias** ([arXiv:2408.15664], **[S]**), which is the single most actionable import from this document.
  It resolves Fabric's objection directly: a per-expert bias `b_i` added to the routing **scores before top-k**, updated
  from recent load, **affects selection only and never the output gate weight**, and therefore **injects zero
  interference gradient**. You get load pressure without an objective term fighting the LM loss and without having to
  turn it off. It is what DeepSeek-V3 shipped.
- **The breadth cap (`dom_ban`)** — masking over-broad experts to `-inf` — is a **hard exclusion**, structurally the same
  as GShard's capacity factor with token dropping. That mechanism is known to hurt quality when it binds **[M]**, and
  MegaBlocks' whole argument is that capacity limits are an implementation artefact rather than a necessity **[M]**.
  Fabric's own record is consistent with this: the `CHAIN_BAN` comment names the breadth-cap ban as one of two
  unseparated changes between pilot 6 (+1.438) and the grid (+2.287) regression.
- **Expert Choice** ([arXiv:2202.09368], **[S]**), **BASE** ([arXiv:2103.16716], **[S]**), **Soft MoE**
  ([arXiv:2308.00951], **[S]**) and **Hash Layers** ([arXiv:2106.04426], **[S]**) all get balance **by construction**
  with no loss and no mask. If balance is what you want, one of these is a cleaner answer than either an aux loss or a
  ban.

**Actionable, highest-value change in this document:**
> Replace both `fab_bal`-with-decay **and** `dom_ban` with a **loss-free per-expert bias** on the routing logits,
> updated from recent utilisation. It is ~15 lines, it removes an interference gradient and a hard mask, it eliminates
> the `BAL_WARM` and `EXP_DOM_FRAC` knobs, it can stay on for the whole run without fighting the LM loss, and it is the
> current state of the art with a clean ablation behind it.

---

## C.13 Router temperature `route_t = 0.1`

**Verdict: CONTRADICTED in direction, though the reasoning behind it is right.**

- Fabric's reasoning is correct and well-observed: unit-norm cosines in `SIG_D=64` have std ≈ 0.125, so at `T=1` the
  top-vs-mean weight ratio is ~1.37× regardless of `N`, and top-k picks noise.
- **But the field's response to "routing logits are the wrong scale" is z-loss, which penalises logit magnitude**
  ([ST-MoE, Zoph et al.], **[S]**), because **router logit growth was identified as the primary cause of large-MoE
  training instability**. Multiplying by 10 is the opposite intervention.
- **X-MoE's answer is the one to copy**: normalise to a hypersphere (which Fabric does, via `FAB_KEY_NORM`) and use a
  **learnable** temperature (which Fabric does not). **[S]** A learnable `τ` finds its own sharpness, anneals naturally,
  and does not commit you to a magic constant.

**Actionable**: make `route_t` a learned scalar parameter initialised at 0.1, and add a z-loss on the routing logits if
instability appears.

---

## C.14 Per-window (not per-token) routing

**Verdict: MIXED — supported by a small recent literature, contradicted by all mainstream practice, and there is a
specific negative result you should know.**

- Every method in Part B routes **per token**. Fabric routes per window, on a domain signature. The compute saving is
  real and the coarse decision is more stable.
- **Supported by**: "Route Experts by Sequence, not by Token" ([arXiv:2511.06494], **[S, recent]**), "Input Domain Aware
  MoE" ([arXiv:2510.16448], **[S, recent]**), and the DEMix/BTM domain-expert line **[M]**.
- **The negative result**: Mixtral's own routing analysis found expert assignment correlated with **syntax and position,
  not with topic or domain** — consecutive tokens were frequently routed to the same expert, but *topically similar*
  tokens were not. **[M — I am confident about the finding, less so about the exact framing.]** If that holds here, a
  **domain signature is routing on a variable the experts do not actually specialise along**, and no amount of router
  tuning fixes that.
- Fabric's own numbers are relevant and encouraging: `I(domain; chosen expert)/H(domain)` of 0.34–0.87 on the society
  path means the router *does* separate domains on this data. But domain separability is not the same as domain being
  the right axis for expertise. **[I]**

**Actionable**: measure `I(next-token identity ; chosen expert)` and `I(syntactic position ; chosen expert)` alongside
the domain MI. If experts turn out to be separating on something other than domain, the signature router is a
bottleneck rather than a grounding.

---

## C.15 Things the literature says matter that `Fabric` does not have

1. **A shared / always-on expert.** DeepSeekMoE's shared-expert isolation **[S]** is now near-universal, and the reason
   is directly applicable: without it, every routed expert redundantly relearns the common structure, wasting capacity
   that fine-graining was supposed to free. Fabric's HALT-to-`model.head` is a partial analogue but it is an
   *alternative* to the experts, not an *addition* to them — the mass that halts skips the population entirely. A true
   shared expert would be an always-applied low-rank adapter outside the routing. **This is a small change with a
   strong empirical track record.**
2. **Router z-loss.** No regularisation on routing logit magnitude, and `route_t=0.1` amplifies them.
3. **Any dropless / capacity analysis.** MegaBlocks' framing **[M]**.
4. **Depth-varying expert counts.** MoLA ([arXiv:2402.08562], **[S]**) found the optimum is depth-dependent. Fabric has
   a single insertion point, so this is not expressible — which may itself be a limitation worth noting.
5. **A no-router baseline.** Hash Layers ([arXiv:2106.04426], **[S]**) was competitive with Switch and BASE. Given
   Equifinality ([arXiv:2604.14419], **[S, recent]**), this baseline is not a formality — it is the experiment that
   tells you whether any of the routing machinery is earning its place.

---

## C.16 Summary table

| Fabric design choice | Verdict | Nearest literature |
|---|---|---|
| Low-rank adapter as the expert unit | **SUPPORTED** | MoLORA/MoV [2309.05444], PEER [2407.04153], fine-grained scaling law [2402.07871] |
| `r = 8`, population of thousands | **SUPPORTED** | PEER (rank-1, 10⁶ experts) |
| Rank-slice crossover | **UNTESTED as growth; SUPPORTED as a unit** | SMoRA [2501.15103] routes individual ranks |
| Zero-init `B` → identity newborn | **SUPPORTED for stability, CONTRADICTED as birth strategy** | LoRA, LLaMA-Adapter [2303.16199] / vs Sparse Upcycling [2212.05055] |
| Replicate-fittest + mutate + crossover | **SUPPORTED** | Sparse Upcycling + Drop-Upcycling; EPnG [2607.01789] |
| Preallocated capacity, `n_live` grows in | **[I] engineering, not a research claim** | — |
| Centroid/prototype routing, cosine, `SIG_D=64` | **MIXED** | X-MoE [2204.09179] (mechanism), Equifinality [2604.14419] (may not matter), LPR [2506.21328] |
| Centroids as no-grad EMA buffers | **UNUSUAL** | all mainstream routers are learned end-to-end |
| Two summed routers (grounded + learned) | **UNTESTED** | — |
| Routing key derived from expert weights (`eemb`) | **UNTESTED** | geometric coupling [2605.12476] says it emerges anyway |
| Expert synthesis from router query (`edec`) | **UNTESTED** | hypernetworks; LoRA-Gen [2506.11638] |
| Multi-hop via learned transition + `SRC` | **CONTRADICTED** | capsules [1710.09829]; Fabric's own `H(hop1\|hop0)` = 0.005–0.058 |
| `soc` loop (re-route each round, state in query) | **SUPPORTED** | Chain-of-Experts [2506.18945] |
| HALT as absorbing operator / per-round stop prob | **SUPPORTED** | ACT, Universal Transformer [1807.03819], PonderNet [2107.05407], MoD [2404.02258] |
| `halt_max` clamp instead of a depth prior | **WEAKER THAN LITERATURE** | PonderNet's KL-to-geometric-prior |
| Prediction-level ensembling (society) | **SUPPORTED (classical), CONTRADICTED (modern)** | Jacobs/Jordan; AdapterFusion [2005.00247] |
| Growth during training | **SUPPORTED** | EMO [2605.13247], Orthogonal Growth [2510.08008], Sparse Upcycling |
| Growth **triggered by loss plateau/regression** | **SUPPORTED only from continual learning** | DEN [1708.01547] |
| Fixed `chain_k`/`ENS_K` while `N` grows | **CONTRADICTED** | Orthogonal Growth: must raise activated count too |
| Culling during training | **UNTESTED online; SUPPORTED post-hoc** | [2405.16646], [2504.07807], EPnG [2607.01789] |
| Leave-one-out marginal contribution as the cull signal | **BETTER THAN LITERATURE DEFAULT** | EPnG uses gate probability |
| Fast/slow error EMA (shift vs failure) | **UNTESTED in MoE** | drift detection |
| Rescue mutation instead of cull | **UNTESTED** | DEN neuron splitting is adjacent |
| Forced exploration at 15%, non-annealed, uniform over cold set | **MIXED — motivation canonical, form aggressive** | Shazeer noisy top-k [1701.06538]; ProbMoE [2606.01509]; vs StableMoE |
| Per-expert LR clocked from birth | **UNTESTED in MoE; principle supported** | growth literature (Net2Net/bert2BERT warmups) |
| Update-rescaling trick for per-expert LR under Adam | **UNTESTED; the reasoning is correct** | — |
| Aux balance loss decayed to zero at step 4000 | **CONTRADICTED** | everyone keeps it on; loss-free bias [2408.15664] |
| Hard breadth cap (`dom_ban`) | **CONTRADICTED in form** | GShard capacity dropping; MegaBlocks; loss-free bias |
| `route_t = 0.1` (10× logit sharpening) | **CONTRADICTED in direction** | ST-MoE z-loss; X-MoE learnable temperature |
| Per-window routing on a domain signature | **MIXED** | [2511.06494], [2510.16448] / vs Mixtral's syntax-not-topic finding |
| No shared always-on expert | **GAP** | DeepSeekMoE [2401.06066] |
| No z-loss | **GAP** | ST-MoE |
| No hash/random-router baseline | **GAP** | Hash Layers [2106.04426], Equifinality [2604.14419] |

---

## C.17 The five changes with the best evidence-to-effort ratio

1. **Loss-free per-expert bias** replacing `fab_bal`+`BAL_WARM` and `dom_ban` ([arXiv:2408.15664]). Removes an
   interference gradient, removes a hard mask, removes two knobs, stays on all run.
2. **A shared always-on expert** — one low-rank adapter outside the routing, applied to every window
   ([arXiv:2401.06066]). Cheap, and it is the change with the strongest track record in this document.
3. **Scale `chain_k` / `ENS_K` with `n_live`**, and/or guarantee newborns routing mass for a birth-grace window
   ([arXiv:2510.08008]). Directly attacks the dead-newborn problem that `FAB_EXPLORE` is currently the only defence
   against.
4. **Anneal `FAB_EXPLORE`**, and prefer Shazeer's score-noise form over the hard index overwrite ([arXiv:1701.06538]).
5. **Run the hash-router baseline** and try to falsify Equifinality ([arXiv:2604.14419], [arXiv:2106.04426]) on this
   system. If a fixed balanced hash of the domain id matches the grounded router, the entire routing axis is not where
   the quality is, and effort should move to the population dynamics — which is where Fabric's genuinely novel and
   untested ideas live anyway.

---

## Sources

Confirmed by search this session (titles/IDs verified; substance from returned abstracts/snippets):

- [Outrageously Large Neural Networks: The Sparsely-Gated Mixture-of-Experts Layer — arXiv:1701.06538](https://arxiv.org/abs/1701.06538)
- [GShard — arXiv:2006.16668](https://arxiv.org/abs/2006.16668)
- [Switch Transformers — arXiv:2101.03961](https://arxiv.org/abs/2101.03961)
- [GLaM — arXiv:2112.06905](https://arxiv.org/abs/2112.06905)
- [Mixtral of Experts — arXiv:2401.04088](https://arxiv.org/abs/2401.04088)
- [DeepSeekMoE — arXiv:2401.06066](https://arxiv.org/html/2401.06066v1) · [ACL 2024 PDF](https://aclanthology.org/2024.acl-long.70.pdf)
- [DeepSeek-V2 — arXiv:2405.04434](https://arxiv.org/pdf/2405.04434)
- [Auxiliary-Loss-Free Load Balancing — arXiv:2408.15664](https://arxiv.org/abs/2408.15664)
- [Mixture-of-Experts with Expert Choice Routing — arXiv:2202.09368](https://arxiv.org/abs/2202.09368) · [NeurIPS page](https://papers.nips.cc/paper_files/paper/2022/hash/2f00ecd787b432c1d36f3de9800728eb-Abstract-Conference.html)
- [BASE Layers — arXiv:2103.16716](https://arxiv.org/abs/2103.16716) · [PMLR](https://proceedings.mlr.press/v139/lewis21a.html)
- [Hash Layers For Large Sparse Models — arXiv:2106.04426](https://proceedings.neurips.cc/paper/2021/file/92bf5e6240737e0326ea59846a83e076-Paper.pdf)
- [From Sparse to Soft Mixtures of Experts — arXiv:2308.00951](https://arxiv.org/abs/2308.00951)
- [Mixture-of-Depths — arXiv:2404.02258](https://arxiv.org/abs/2404.02258)
- [Mixture-of-Recursions — arXiv:2507.10524](https://arxiv.org/html/2507.10524v1)
- [Large Memory Layers with Product Keys — arXiv:1907.05242](https://arxiv.org/abs/1907.05242)
- [Mixture of A Million Experts (PEER) — arXiv:2407.04153](https://arxiv.org/abs/2407.04153)
- [Ultra-Sparse Memory Network — arXiv:2411.12364](https://arxiv.org/pdf/2411.12364)
- [Memory Layers at Scale — arXiv:2412.09764](https://arxiv.org/html/2412.09764v1)
- [Scaling Laws for Fine-Grained Mixture of Experts — arXiv:2402.07871](https://arxiv.org/pdf/2402.07871)
- [AdapterFusion — arXiv:2005.00247](https://arxiv.org/abs/2005.00247) · [EACL 2021](https://aclanthology.org/2021.eacl-main.39/)
- [Pushing Mixture of Experts to the Limit (MoV/MoLORA) — arXiv:2309.05444](https://arxiv.org/pdf/2309.05444)
- [Higher Layers Need More LoRA Experts (MoLA) — arXiv:2402.08562](https://arxiv.org/pdf/2402.08562)
- [Each Rank Could be an Expert (SMoRA) — arXiv:2501.15103](https://arxiv.org/html/2501.15103v1)
- [Dynamic Routing Between Capsules — arXiv:1710.09829](https://arxiv.org/abs/1710.09829)
- [Chain-of-Experts — arXiv:2506.18945](https://arxiv.org/abs/2506.18945) · [code](https://github.com/ZihanWang314/coe)
- [Universal Transformers — arXiv:1807.03819](https://arxiv.org/html/1807.03819v3)
- [PonderNet — arXiv:2107.05407](https://arxiv.org/pdf/2107.05407)
- [On the Representation Collapse of Sparse Mixture of Experts (X-MoE) — arXiv:2204.09179](https://arxiv.org/abs/2204.09179)
- [Sparse Upcycling — arXiv:2212.05055](https://arxiv.org/abs/2212.05055)
- [Lifelong Learning with Dynamically Expandable Networks — arXiv:1708.01547](https://arxiv.org/pdf/1708.01547)
- [LLaMA-Adapter (zero-init attention) — arXiv:2303.16199](https://arxiv.org/abs/2303.16199)
- [Soft Merging of Experts with Adaptive Routing (SMEAR) — arXiv:2306.03745](https://arxiv.org/pdf/2306.03745)
- [ReMoE: Fully Differentiable MoE with ReLU Routing — arXiv:2412.14711](https://arxiv.org/pdf/2412.14711)
- [Unchosen Experts Can Contribute Too — arXiv:2405.14507](https://arxiv.org/pdf/2405.14507)
- [ModuleFormer — arXiv:2306.04640](https://arxiv.org/abs/2306.04640)
- [A Survey on Mixture of Experts in LLMs — arXiv:2407.06204](https://arxiv.org/abs/2407.06204v3)
- [A Provably Effective Method for Pruning Experts — arXiv:2405.16646](https://arxiv.org/html/2405.16646v1)
- [Cluster-Driven Expert Pruning — arXiv:2504.07807](https://arxiv.org/pdf/2504.07807)

Recent (2025–2026) hits, snippet-level knowledge only — **treat as preliminary**:

- [Equifinality in Mixture of Experts — arXiv:2604.14419](https://arxiv.org/abs/2604.14419)
- [Latent Prototype Routing — arXiv:2506.21328](https://arxiv.org/abs/2506.21328)
- [Routers Learn the Geometry of Their Experts — arXiv:2605.12476](https://arxiv.org/pdf/2605.12476)
- [Geometric Routing Enables Causal Expert Control in MoE — arXiv:2604.14434](https://arxiv.org/pdf/2604.14434)
- [Routing by Analogy: kNN-Augmented Expert Assignment — arXiv:2601.02144](https://arxiv.org/abs/2601.02144)
- [EMO: Frustratingly Easy Progressive Training of Extendable MoE — arXiv:2605.13247](https://arxiv.org/html/2605.13247v2)
- [Beyond Sunk Costs: Orthogonal Growth of MoE — arXiv:2510.08008](https://arxiv.org/pdf/2510.08008)
- [EPnG: Adaptive Expert Prune-and-Grow — arXiv:2607.01789](https://arxiv.org/pdf/2607.01789)
- [Breaking the MoE LLM Trilemma: Dynamic Expert Clustering — arXiv:2510.02345](https://arxiv.org/html/2510.02345v1)
- [Input Domain Aware MoE — arXiv:2510.16448](https://arxiv.org/pdf/2510.16448)
- [Route Experts by Sequence, not by Token — arXiv:2511.06494](https://arxiv.org/pdf/2511.06494)
- [ProbMoE: Differentiable Probabilistic Routing — arXiv:2606.01509](https://arxiv.org/html/2606.01509v1)
- [LoRA-Gen: Specializing LLMs via Online LoRA Generation — arXiv:2506.11638](https://arxiv.org/pdf/2506.11638)
- [The Evolution of MoE Architectures in LLMs (survey) — arXiv:2608.08650](https://arxiv.org/abs/2608.08650)
- [AdapterTune: Zero-Initialized Low-Rank Adapters — arXiv:2603.14706](https://arxiv.org/html/2603.14706v1)

**From memory, not verified this session** (cited in the text as **[M]**): Jacobs/Jordan/Nowlan/Hinton 1991 and Jordan &
Jacobs 1994 (original MoE / HME); Hinton 2002 (Product of Experts); LoRA (Hu et al. 2021, arXiv:2106.09685); Houlsby
adapters 2019; ST-MoE / "Designing Effective Sparse Expert Models" (Zoph et al. 2022, arXiv:2202.08906 — the z-loss
attribution *was* confirmed by search, the arXiv ID is from memory); Graves ACT 2016 (arXiv:1603.08983); Net2Net
(arXiv:1511.05641); bert2BERT; Progressive Neural Networks (arXiv:1606.04671); StableMoE; THOR; DEMix / Branch-Train-
Merge / c-BTM; MegaBlocks / Tutel / DeepSpeed-MoE; HyperNetworks (Ha et al., arXiv:1609.09106); Drop-Upcycling; VICReg
variance-covariance regularisation; µP/µTransfer; Mixtral's expert-specialisation analysis.
