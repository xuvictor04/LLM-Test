# Continual Learning & External Editable Memory — Literature Reference

**Compiled:** 2026-08-15. **Audience:** the author of this codebase (`memory.py` + the continual-learning
machinery in `self_organize.py`), who has already built a surprise-gated, re-keyed, bounded, provenance-tagged
kNN memory and wants to know what the field has already tried.

## Status of sources

Web **search** worked. Web **fetch** did **not**: `arxiv.org` and `openreview.net` are blocked by this
environment's egress proxy (`EGRESS_BLOCKED`), so no paper was read end-to-end. Everything below is therefore
either (a) grounded in search-result text, or (b) recalled knowledge. Claims are tagged:

- **[S]** — supported by text returned in a web search this session; URL given.
- **[M]** — **from memory, UNVERIFIED** in this session. Treat as a lead to check, not as a citation.
- **[CODE]** — read directly from this repository.

arXiv IDs marked **[M]** should be verified before citing in anything public.

---

# PART 0 — What this codebase is (so Part C has something to compare against)

Read from `/home/user/LLM-Test/memory.py` (all 318 lines) and the continual-learning sections of
`/home/user/LLM-Test/self_organize.py`. **[CODE]**

| Property | Implementation |
|---|---|
| **Store** | `EditableMemory`: fixed `cap` slots, each = (normalized key `d`-dim, next-token `tok`, provenance `src`, byte position `pos`, optional raw context window `ctx`, usage count, last-use tick, `selfcon`, `recon`) |
| **Write gate** | surprise = `1 - p_model(true token)`. Three modes: fixed threshold; additive controller on the threshold targeting a write fraction; **quantile gate** (default, `quantile_gate=True`) — threshold = EMA of the `1 - gate_target` quantile of the batch's surprise. The quantile mode exists because an absolute threshold cannot track a surprise distribution squeezed against 1.0 on a large vocabulary (`memory.py:81-105`) |
| **Read** | kNN over active, not-flagged entries; cosine sim → `softmax(sim/tau)` → soft vote into a token distribution + a confidence. Interpolated with the parametric distribution at eval (`bpb_true`, `self_organize.py:6264-6270`: `pp = (1-hp)*pm + hp*pmem`) — i.e. **kNN-LM interpolation** |
| **Rekey** | raw `ctx` windows stored per entry; `_rekey_amortized` re-encodes a slice of the store every step with the *current* encoder, so the whole store is refreshed on a rolling cadence (`self_organize.py:3859-3867`, `4739-4742`) |
| **Eviction** | global: circular FIFO (`evict="recency"`) or sampled least-used (`evict="usage"`, an LFU with write-count decay). Partitioned (`n_own>1`): contiguous per-expert blocks of `quota` slots, per-owner **true LRU** on last-use tick; reads stay global |
| **Provenance** | `src` = self-assembled domain id; `delete_src()`, `reassign_src()` — deletion by origin is the product claim |
| **Self-check** | `selfcheck()` runs the model on each entry's *own* stored context and records the fraction of vocab ranked above the stored token; `is_wrong()` flags the high tail via adaptive median + k·MAD |
| **Verification** | parallel signal on reconstruction error (`recon`, `is_unverified()`) |
| **Non-stationarity** | `PHASE_SCHED` — a sliding window of `w` active processes over `n`, across `p` phases; every process enters, is active for a stretch, and fades. Guaranteed that the last phase excludes at least one process |
| **Retention metrics** | `holdout_bpb()` — per-domain bits/byte on held-out tails, windows seeded by domain **name**; `report_holdout()` — compares against the probe stored in the resumed checkpoint ("ACROSS THE RUN BOUNDARY"); a within-stream earliest-vs-latest-windows retention block; a per-process learning curve tagged active/absent |
| **Unlearn test** | delete every self-domain belonging to one true process; measure target Δbpb vs others' Δbpb (LOCAL vs LEAKED) |

**One structural fact that matters for Part C:** `holdout_bpb()` and the within-stream RETENTION block call
`_eval_logits(model, fab, FABRIC, X)` — **model + fabric, no memory**. Only `bpb_true(..., use_mem=True)`
mixes the store in. So the headline cross-run retention number currently measures the **weights**, not the
system. **[CODE]**

---

# PART A — Exhaustive list of continual-learning methods

Organised by family. For each: mechanism → cost → known failure modes.

## A.1 Regularisation (penalise moving important weights)

The shared idea: after task *t*, estimate a per-parameter importance Ω, then add `Σ_i Ω_i (θ_i − θ*_i)²` to
future losses. They differ only in how Ω is computed. Requires no stored data — which was their entire selling
point in 2017 and is why they still appear in privacy-constrained settings.

### EWC — Elastic Weight Consolidation (Kirkpatrick et al., 2017)
- **Mechanism.** Ω = diagonal of the Fisher information matrix at θ*. Laplace approximation to the posterior of
  the old task; a quadratic spring pulls each weight back toward θ* with stiffness ∝ Fisher. **[S]**
  <https://arxiv.org/pdf/1612.00796>
- **Cost.** One extra copy of θ and one Ω vector per task (or a running sum, "online EWC"). A Fisher estimation
  pass over data from the old task at each boundary. No replay buffer.
- **Failure modes.**
  - Diagonal Fisher ignores parameter interactions; the true posterior is not axis-aligned. **[M]**
  - **Gradient vanishing / importance underestimation**: Fisher is computed at a converged point where gradients
    are small, so importances are systematically underestimated. **[S]**
    <https://arxiv.org/html/2603.18596v1>
  - Requires task boundaries to know *when* to snapshot θ* and recompute Ω. Useless on a task-free stream
    without modification. **[M]**
  - Ω accumulates monotonically over tasks → the network progressively freezes (loss of plasticity). **[M]**
  - Numerically fragile; the stiffness coefficient λ typically needs per-benchmark tuning over orders of
    magnitude. **[S]** <https://arxiv.org/abs/2109.10021>
  - Empirically weak on class-incremental settings; it protects weights, not decision boundaries between
    classes never seen together. **[M]**

### SI — Synaptic Intelligence (Zenke, Poole, Ganguli, 2017)
- **Mechanism.** Ω accumulated **online during training** as the path integral of (gradient × parameter update)
  — how much each parameter contributed to reducing the loss along the trajectory. **[S]** (definition
  confirmed in survey text) arXiv 1703.04200 **[M]**
- **Cost.** Cheaper than EWC — no separate Fisher pass; one running accumulator per parameter.
- **Failure modes.** Path integral is trajectory-dependent, so importance depends on optimiser and LR schedule;
  noisy under large-batch / high-LR training; same freezing and same task-boundary dependence as EWC. **[M]**

### MAS — Memory Aware Synapses (Aljundi et al., 2018)
- **Mechanism.** Ω = sensitivity of the **squared L2 norm of the network output** to each parameter — label-free,
  so it can be computed on unlabeled data at test time. **[S]** (described as an EWC-family importance
  weighting) <https://link.springer.com/article/10.1007/s10845-021-01793-0>; arXiv 1711.09601 **[M]**
- **Cost.** One backward pass per sample over the output norm; unsupervised.
- **Failure modes.** **Over-restricts irrelevant parameters, producing redundant protection** and thus excess
  rigidity. **[S]** <https://arxiv.org/html/2603.18596v1>

### Also in this family
- **LwF — Learning without Forgetting** (Li & Hoiem, 2016): distil the *old model's outputs* on new-task inputs
  instead of penalising weights. Cheap, no old data. Fails when the new-task input distribution doesn't cover
  the old task's input space — the distillation targets are then uninformative. arXiv 1606.09282 **[M]**
- **Functional regularisation of memorable past** (FROMP) — regularise in function space at a small set of
  memorable points rather than in weight space. **[S]** <https://arxiv.org/pdf/2004.14070>
- **Verdict for the family.** In the last several years of benchmark work, regularisation methods are
  consistently beaten by even small replay buffers; they are used today mostly as an *additional* term
  alongside replay, not alone. **[M]**

## A.2 Replay / rehearsal (re-show old data)

### Experience Replay (ER) with reservoir sampling
- **Mechanism.** Maintain a fixed-size buffer; on each step, mix a minibatch of buffer samples into the
  gradient. **Reservoir sampling** keeps the buffer a uniform random sample of the whole stream seen so far,
  without knowing stream length or task boundaries. **[S]**
  <https://proceedings.neurips.cc/paper/2020/file/b704ea2c39778f07c617f6b7ce480e9e-Paper.pdf>
- **Cost.** Buffer memory (raw data), and roughly 2× the gradient work per step. Requires the right to *retain*
  raw data — often the blocking constraint in privacy/licensing settings.
- **Failure modes.**
  - **Reservoir starves new data over time**: acceptance probability decays as 1/n, so late-arriving skills get
    fewer and fewer slots. This is the consolidation/plasticity tradeoff *hidden inside* the buffer. **[S]**
    <https://arxiv.org/abs/2504.20932>
  - Overfitting to a small buffer; the model memorises the exemplars rather than the old distribution. **[M]**
  - Class/domain imbalance under non-stationarity — a domain that appears briefly gets a proportionally tiny
    slice. Motivates **stratified / multiple buffers**, an explicit proposed improvement. **[S]** (same paper)

### DER / DER++ — Dark Experience Replay (Buzzega et al., NeurIPS 2020)
- **Mechanism.** Store the **logits** at insertion time alongside the sample, and regularise current logits
  toward the stored ones (a self-distillation through time). No task boundaries needed; reservoir buffer.
  **[S]** <https://proceedings.neurips.cc/paper/2020/file/b704ea2c39778f07c617f6b7ce480e9e-Paper.pdf>
- **Cost.** Buffer stores logits too. Still 2× compute.
- **Why it matters.** It is *the* "strong, simple baseline" that new methods are expected to beat, and often
  don't. **[S]** (title + NeurIPS review) <https://proceedings.neurips.cc/paper_files/paper/2020/file/b704ea2c39778f07c617f6b7ce480e9e-Review.html>
- **Failure modes.** Stored logits go **stale** — they were produced by an older, worse model, so the
  distillation target drags the model backwards. Recent work explicitly proposes "correction of past outputs"
  and "blocking of replaying inconsistent data" to fix exactly this. **[S]** <https://arxiv.org/abs/2504.20932>
  *(Note: this is the direct analogue of your rekey problem — see Part C.2.)*

### Generative replay (Deep Generative Replay, Shin et al., 2017)
- **Mechanism.** Train a generator alongside the classifier; at each new task, sample pseudo-data from the
  generator for old tasks and train on it. No raw data retained. arXiv 1705.08690 **[M]**
- **Cost.** A whole second model, trained continually itself.
- **Failure modes.** The generator forgets too, and errors **compound across generations** — a well-documented
  degradation, since each replay round trains on samples of samples. Doesn't scale to high-fidelity domains.
  **[M]**
- **LLM-scale descendant: Self-Synthesized Rehearsal (SSR)** — the model generates its own rehearsal examples
  for previously learned instruction data. **[S]**
  <https://github.com/Wang-ML-Lab/llm-continual-learning-survey>

### Exemplar selection: what to *put* in the buffer
- **iCaRL herding** — pick exemplars whose mean approximates the class mean. arXiv 1611.07725 **[M]**
- **GSS — Gradient-based Sample Selection** (Aljundi et al., NeurIPS 2019): choose samples to **maximise
  gradient diversity** in the buffer. A greedy variant is efficient and beats other selection strategies.
  **[S]** <https://arxiv.org/abs/1903.08671>
- **MIR — Maximally Interfered Retrieval**: retrieve for replay the buffer items whose loss would increase most
  under the pending update. arXiv 1908.04742 **[M]**
- **Prioritised Experience Replay (PER)** (Schaul et al., 2016): priority = |TD error| = surprise. Directly
  relevant to your write gate. **[S]** <https://arxiv.org/pdf/2209.00532> (Actor-PER, describes the mechanism);
  arXiv 1511.05952 **[M]**
  - **Known failure mode of surprise-priority:** it concentrates on high-error transitions, which under noise
    are disproportionately the *noisy or aberrant* ones, and it introduces a sampling bias that must be
    corrected with importance-sampling weights. Uncertainty-aware variants exist specifically because raw TD
    error conflates *epistemic* (learnable) with *aleatoric* (noise) surprise. **[S]**
    <https://rlj.cs.umass.edu/2025/papers/RLJ_RLC_2025_45.pdf>

### At LLM scale: replay is a *data mixture ratio*
- **Mechanism.** Mix a few percent of the original pretraining distribution into the continued-pretraining
  corpus, plus LR re-warming and re-decaying. **[S]** <https://arxiv.org/abs/2403.08763>
- **Result.** This combination **matches full retraining from scratch on all data**, at 405M and 10B scale,
  across weak (En→En) and strong (En→De) shifts. **[S]** (same)
- **Cost.** Trivial — it's a config change. This is why it won.

## A.3 Parameter isolation (give each task its own weights)

### PackNet (Mallya & Lazebnik, CVPR 2018)
- **Mechanism.** Train task *t*, prune (~60%) the least important weights, **freeze** the surviving weights for
  *t* forever, retrain, then use the freed weights for task *t+1*. Per-task binary masks at inference. **[S]**
  <https://openaccess.thecvf.com/content_cvpr_2018/papers/Mallya_PackNet_Adding_Multiple_Tasks_to_a_Single_Network_by_Iterative_Pruning_CVPR_2018_paper.pdf>
- **Cost.** A mask per task (1 bit/weight/task); prune-and-retrain cycle per task.
- **Failure modes.** **Hard capacity ceiling**: each successive task gets fewer free parameters, and the ceiling
  is set by the pruning rate and the task count. **[S]** <https://arxiv.org/html/2604.24637> Requires **task
  identity at inference** to pick the mask. Zero backward transfer *and* zero forward transfer into frozen
  weights.

### HAT — Hard Attention to the Task (Serrà et al., ICML 2018)
- **Mechanism.** Learn per-task, near-binary **attention masks over units** from a task embedding, trained
  jointly with the network; a sparsity penalty keeps masks small so capacity remains for future tasks; gradients
  to units claimed by earlier tasks are annealed to zero. **[S]** <https://arxiv.org/pdf/1801.01423>
- **Cost.** Task embeddings + mask machinery; a sparsity/stability hyperparameter that is notoriously touchy.
- **Failure modes.** Same capacity saturation, same task-id-at-inference requirement. **[S]**
  <https://arxiv.org/html/2604.24637>

### Progressive Neural Networks (Rusu et al., 2016)
- **Mechanism.** Instantiate a **new column** per task, freeze all previous columns, add lateral adapters from
  old columns into the new one. Zero forgetting by construction, plus explicit forward transfer. **[S]**
  <https://pengxiang-wang.com/posts/architecture-based-continual-learning>; arXiv 1606.04671 **[M]**
- **Cost.** **Linear growth in parameters and memory with task count.** **[S]** (same)
- **Failure modes.** Doesn't scale past a handful of tasks; needs task id; no backward transfer at all.

### Adapters / LoRA per task; O-LoRA
- **Mechanism.** Freeze the backbone; train a small adapter or LoRA per task. Zero forgetting *of the backbone*.
  **O-LoRA** constrains each task's LoRA to a low-rank subspace **orthogonal** to previous tasks' subspaces to
  minimise interference. **[S]**
  <https://www.semanticscholar.org/paper/Orthogonal-Subspace-Learning-for-Language-Model-Wang-Chen/28fde851680a40fbbc5c6a44bd3ac6f5ca4ad284>;
  arXiv 2310.14152 **[M]**
- **Cost.** Small (0.1–1% params per task), but **you must know which adapter to load**, and merging many
  adapters degrades.
- **Failure modes.** Task-id requirement; orthogonality budget exhausts as rank accumulates; adapters cannot
  add genuinely *new* knowledge that the frozen backbone's features cannot express; routing between many
  adapters is an unsolved problem in practice. **[M]**
- **Adjacent finding.** LoRA fine-tuning forgets *less* than full fine-tuning, largely because it changes less
  — it also learns less. The "LoRA learns less and forgets less" framing is a standard result. arXiv 2405.09673
  **[M]**

### MoE / expert routing
- Sparse experts as soft parameter isolation, with the router deciding partitioning. Failure modes: router
  collapse, load imbalance, and the fact that routing is learned on the *current* distribution and therefore
  drifts under non-stationarity. **[M]** *(This codebase's `n_own` per-expert memory partition is the memory-side
  analogue.)*

## A.4 Optimisation-based / gradient-projection

### GEM — Gradient Episodic Memory (Lopez-Paz & Ranzato, NeurIPS 2017)
- **Mechanism.** Keep a small episodic memory per task. Treat "loss on stored task-*k* samples must not
  increase" as **inequality constraints**; if the current gradient violates them, project it to the nearest
  gradient in the feasible cone via a QP. Explicitly permits *decrease* → allows positive backward transfer.
  **[S]** <https://arxiv.org/abs/1706.08840>
- **Cost.** One backward pass **per stored task** per step, plus a QP with as many variables as tasks. Expensive
  and scales badly.
- **Failure modes.** Cost grows with task count; needs task boundaries to organise per-task memories; the
  constraint is evaluated on a small sample so the projection is noisy.

### A-GEM — Averaged GEM (Chaudhry et al., ICLR 2019)
- **Mechanism.** Replace the per-task constraints with a **single** constraint on the average gradient of a
  random buffer sample; the projection becomes a closed-form scalar rescaling. **[S]**
  <https://arxiv.org/pdf/2504.03793> (description); arXiv 1812.00420 **[M]**
- **Cost.** One extra backward pass per step. Practical.
- **Failure modes.** The averaged constraint is much weaker than GEM's; empirically A-GEM often lands near plain
  ER, and plain ER is simpler. **[M]**

### OGD — Orthogonal Gradient Descent (Farajtabar et al., AISTATS 2020)
- **Mechanism.** Store the gradient directions of old tasks' *predictions*; project new-task gradients into the
  orthogonal complement of that span. **[S]** <https://arxiv.org/pdf/1910.07104>
- **Cost.** Storing a basis of gradient directions — dimensionality of the parameter space is the problem;
  memory grows with the number of stored directions.
- **Failure modes.** In a *d*-dimensional parameter space the orthogonal complement shrinks with every task
  until no descent direction remains (loss of plasticity); requires task boundaries; the stored basis is
  computed at old parameter values and becomes stale as θ moves. **[M]**
- **Descendants.** GPM (Gradient Projection Memory), Adam-NSCL, and the LLM-scale O-LoRA above are all "project
  into a subspace that doesn't disturb the old" methods. **[M]**

## A.5 Retrieval / RAG / kNN-LM — memory-based alternatives to weight updates

**This is the family your system belongs to.** The claim of the family: knowledge lives in an external store,
so updating knowledge = updating the store, and forgetting is not a gradient phenomenon at all.

### kNN-LM (Khandelwal et al., ICLR 2020)
- **Mechanism.** Run a trained LM over a corpus; save (context-representation → next token) pairs into a
  datastore. At inference, kNN the current context representation, softmax over negative distances → a
  distribution over next tokens, **interpolated** with the parametric distribution:
  `p = (1−λ)·p_LM + λ·p_kNN`. **[S]** <https://openreview.net/pdf?id=ARDbU7beLp>; arXiv 1911.00172 **[M]**
- **Cost.** Datastore ≈ one *d*-dim vector per training token — enormous (WikiText-103 → ~10⁸ entries);
  ANN index build; per-token retrieval latency at inference.
- **What is known about *why* it works.** Not simply "memorisation of the training set". Analyses attribute the
  gain to the **softmax bottleneck** — the kNN distribution provides an ensemble/second output head that
  escapes the low-rank constraint of the LM's softmax — and to sharpening on under-fit tokens. **[S]**
  <https://openreview.net/pdf?id=ARDbU7beLp>
- **Failure modes.**
  - Gains **concentrate on long-tail / rare phenomena**; on frequent, well-modelled tokens retrieval adds
    little and can hurt. **[S]** <https://arxiv.org/pdf/2503.22426> ("Long-Tail Crisis in Nearest Neighbor
    Language Models"), <https://arxiv.org/pdf/2210.15859>
  - Effectiveness is largest with a **very large datastore, orders of magnitude bigger than the training
    corpus**. Small datastores give small gains. **[S]** <https://arxiv.org/pdf/2503.22426>
  - Retrieval on every token is wasteful; ~50% of retrievals can be skipped adaptively with no perplexity
    cost. **[S]** <https://arxiv.org/pdf/2109.04212>
  - Perplexity gains do **not** reliably translate into better open-ended generation or downstream task
    performance. **[M]** — worth verifying; it is a widely-repeated criticism.
  - A fixed global λ is wrong; adaptive/learned λ (per-token confidence gating) is a standard fix. **[S]**
    <https://arxiv.org/pdf/2211.07828>

### Efficiency / pruning of the datastore
- **Greedy merging** — merge entries with the same target token whose keys are close: **prunes 40% of the
  datastore at a cost of 0.2 perplexity**. **[S]** <https://arxiv.org/pdf/2109.04212>
- **Adaptive retrieval** — skip retrieval when the LM is confident: **50% of retrievals removed, ~2× speed-up,
  comparable perplexity**. **[S]** (same)
- **PCA dimension reduction** — 3.6× faster with a *slight perplexity improvement*. **[S]** (same)
- **RetoMaton** — build a weighted finite automaton over datastore states so retrieval can be *saved* across
  consecutive tokens. **[S]** <https://arxiv.org/pdf/2201.12431>

### Memorizing Transformers (Wu et al., ICLR 2022)
- **Mechanism.** A non-differentiable external memory of recent (key, value) pairs at one attention layer, with
  approximate kNN lookup; the layer gates between local attention and memory attention. Scales to 262K tokens
  of memory. **[S]** <https://arxiv.org/pdf/2203.08913>
- **Eviction.** After each training step, local-context (k,v) pairs are **appended and the oldest are dropped**
  — plain FIFO. **[S]** (same)
- **Staleness.** They explicitly confront the problem that stored keys were encoded by an *older* model. Their
  fix is **key/query normalisation**, so old and new keys keep consistent magnitudes; they report the model
  copes with limited staleness by adjusting its queries, rather than re-encoding memory. **[S]** (same)
  → **Directly relevant prior art for `rekey` — see Part C.2.**
- **Failure modes.** Memory is per-layer and non-semantic (attention keys, not document ids); no provenance,
  no deletion story; benefit saturates with memory size.

### REALM (Guu et al., ICML 2020)
- **Mechanism.** A learned retriever over a document index trained **jointly** with the LM through the
  retrieval marginal. **[S]** <http://proceedings.mlr.press/v119/guu20a/guu20a.pdf>
- **The staleness solution.** Because the retriever's parameters change every step, **the index goes stale
  every step**. REALM runs a **secondary index-builder job asynchronously**: the trainer ships a parameter
  snapshot, the builder re-embeds and re-indexes *all* documents in the background, and the fresh index is
  swapped in — roughly every several hundred steps. The index is slightly stale between refreshes, and they
  show empirically that optimisation is stable **provided refreshes are frequent enough**. **[S]** (same)
  → **This is the canonical prior art for `rekey`.**
- **Cost.** A second machine/job continuously re-embedding the corpus. This cost is why almost nobody else does
  it.
- **Failure modes.** Cold-start retriever collapse (needs ICT-style warmup); the async refresh doubles
  infrastructure.

### RETRO (Borgeaud et al., 2021) and Atlas (Izacard et al., 2022)
- **RETRO.** Chunked cross-attention over neighbours retrieved from a **trillion-token** database with a
  **frozen BERT retriever** — freezing is precisely what makes the index never go stale, so it need be built
  only once. arXiv 2112.04426 **[M]**
- **Atlas.** Studies retriever/index refresh strategies and their cost in few-shot retrieval-augmented
  training. **[S]** <https://arxiv.org/pdf/2208.03299>
- **Failure mode of the family.** Generalisation questions: whether gains come from retrieval or from test-set
  leakage into the datastore. **[S]** <https://arxiv.org/pdf/2302.12128>

### SILO (Min et al., ICLR 2024) — the paper closest to this project's *thesis*
- **Mechanism.** Train the parametric LM **only** on permissively-licensed text (Open License Corpus, 228B
  tokens), and put all high-risk/copyrighted text **exclusively** in a nonparametric datastore queried at
  inference. **[S]** <https://arxiv.org/abs/2308.04430>
- **Why it matters here.** It gives exactly the three properties this codebase claims — *use of restricted data
  without training on it, sentence-level attribution, and opt-out by removing content from the store* — and it
  spells out the condition under which removal actually works: **the parametric model must never have trained
  on the removed data.** **[S]** (same)
- **Failure modes.** A parametric model trained on a restricted corpus is weaker; the domain gap between the
  permissive training corpus and the datastore's distribution costs quality; retrieval infrastructure at
  inference.

### Agent memory systems (Generative Agents, MemGPT, A-MEM, Mem0)
- **Generative Agents** (Park et al., 2023): a memory stream scored by a weighted blend of **recency,
  importance, relevance**, where importance is an LLM's 1–10 rating; hand-set weights; the score governs
  *retrieval only*, not encoding or forgetting. **[S]** <https://arxiv.org/pdf/2606.12945>; arXiv 2304.03442
  **[M]**
- **MemGPT** (Packer et al., 2023): context as **paged virtual memory** with explicit eviction; eviction driven
  by recency and capacity pressure, not by learned value; FIFO queue in context, "recall" and "archival"
  external stores; memory operations triggered by memory pressure. **[S]** <https://arxiv.org/pdf/2606.12945>;
  arXiv 2310.08560 **[M]**
- **A-MEM / Mem0**: explicit memory operations — extraction, updating, linking, consolidation. **[S]**
  <https://arxiv.org/pdf/2606.12945>
- **State of the art, honestly stated by the field itself:** "Agent memory systems evict by FIFO, lifecycle
  stage, or store size, or delete locally, **without relevance**… ad-hoc replacement policies." **[S]** (same).
  A 2026 survey frames every consolidation policy as four levers — **Importance** (what becomes a memory at
  all), **Merge**, **Decay**, **Eviction**. **[S]**
  <https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation>

### Test-time / surprise-driven neural memory
- **Titans** (Behrouz et al., 2025): a deep neural long-term memory module updated **at test time** by a
  gradient-based **surprise** metric with **momentum** (momentary + accumulated past surprise), plus an
  **adaptive forgetting gate** (weight decay) that discards less-surprising information to prevent overflow.
  Reported to beat baselines at 340M–760M and on needle-in-a-haystack to 16K. **[S]**
  <https://arxiv.org/html/2501.00663>
  → **This is the closest published relative of your surprise gate + decayed usage + eviction.**

## A.6 Model editing (surgical weight edits)

### ROME — Rank-One Model Editing (Meng et al., NeurIPS 2022)
- **Mechanism.** Causal tracing localises a factual association to a mid-layer MLP; treat that MLP as a linear
  associative memory and apply a **closed-form rank-one update** to write (subject, relation) → new object.
  arXiv 2202.05262 **[M]**; overview **[S]** <https://www.emergentmind.com/topics/rank-one-model-editing-rome>
- **Cost.** Seconds per edit, no gradient training. Needs covariance statistics of the layer's inputs.
- **Failure modes.** One fact at a time; poor generalisation to paraphrases and to *ripple effects* (edit
  "capital of France" and the model still says Paris elsewhere); degrades under sequencing.

### MEMIT — Mass-Editing Memory in a Transformer (Meng et al., ICLR 2023)
- **Mechanism.** Spread thousands of edits across a *range* of MLP layers with a least-squares update.
  arXiv 2210.07229 **[M]**
- **Cost.** Batch edits at ~10⁴ scale in one pass.
- **Failure modes — this is where the family breaks, and it is well documented:**
  - **Both ROME and MEMIT stay stable only for small edit counts (≤50); past ~100 edits, downstream performance
    declines across all tasks.** **[S]** <https://arxiv.org/html/2401.04700>
  - **At 300 edits, MEMIT left GPT2-XL largely unchanged but dropped LLaMA-2 / LLaMA-3 to nearly zero.** **[S]**
    <https://arxiv.org/html/2405.16821>
  - **Mechanism of collapse:** the **condition number of the edited matrix** grows with edit count, so each new
    edit perturbs the model more; the failure is numerical, not semantic. **[S]** (same)
  - Broader pitfalls: knowledge conflict and knowledge distortion when edits interact. **[S]**
    <https://aclanthology.org/2024.findings-emnlp.550.pdf>
- **Mitigations.** PRUNE (condition-number restraint), spectral/energy regularisation on the edited matrix.
  **[S]** <https://arxiv.org/html/2405.16821>, <https://arxiv.org/pdf/2510.01172>
- **The field's own conclusion is drifting toward retrieval:** "Knowledge Updating? No More Model Editing!
  Just Selective Contextual Reasoning." **[S]** <https://arxiv.org/pdf/2503.05212>

## A.7 Machine unlearning

- **Exact unlearning.** SISA-style: shard the data, train one model per shard, retrain only the affected shard
  on a deletion request. Gives a *guarantee*; costs a partitioned training pipeline and hurts quality.
  arXiv 1912.03817 **[M]**
- **Approximate unlearning — gradient ascent (GA)** on the forget set, usually with a retain-set term (GA+GD,
  KL-retain, NPO).
  - **Cost.** Cheap relative to retraining.
  - **Failure modes.** **"Gradient ascent does not invert the original training trajectory; it introduces a new
    one that leaves underlying representations largely intact."** **[S]**
    <https://arxiv.org/html/2508.06467v1>
  - **Benign relearning attacks:** fine-tuning on innocuous, *related* public data restores the "unlearned"
    content — the knowledge was obfuscated, not removed. **[S]** <https://arxiv.org/pdf/2406.13356>
  - **Embedding-space / soft-prompt attacks** recover unlearned content (ROUGE ≥ 0.49 on TOFU). **[S]**
    <https://arxiv.org/pdf/2402.09063>
  - **Utility collapse:** "no baseline method achieves statistically perfect forgetting on small forget sets
    without severely degrading utility." **[S]** <https://www.emergentmind.com/topics/tofu-and-wmdp-benchmarks>
- **Benchmarks.** TOFU (fictitious authors, so there is a clean ground truth for "should not know");
  WMDP (hazardous bio/cyber/chem knowledge, measured as MMLU-style accuracy drop); RWKU (real public figures).
  **[S]** <https://www.emergentmind.com/topics/tofu-and-wmdp-benchmarks>; TOFU arXiv 2401.06121, WMDP arXiv
  2403.03218 **[M]**
- **Survey of the state of the art.** **[S]** <https://ai.stanford.edu/~kzliu/blog/unlearning/>
- **Datastore deletion as unlearning.** The pragmatic industry answer: delete the embedding from the vector DB.
  **Instant, zero compute** — but "the underlying model still *knows* the information; it just isn't being fed
  it actively," and **"deleting a PDF from your knowledge base does not remove the information if you
  fine-tuned the model on that PDF."** **[S]**
  <https://petronellatech.com/blog/clear-the-plate-enterprise-ai-unlearning-across-fine-tunes-rag-and/>,
  <https://arxiv.org/abs/2410.15267>
  → **This is the single most load-bearing external claim for Part C.5.**

## A.8 Knowledge injection by fine-tuning — failure modes

- **New knowledge is learned slowly and causes hallucination.** Fine-tuning examples that introduce knowledge
  *new* to the model are learned significantly slower than examples consistent with existing knowledge; and as
  they are eventually fitted, they **linearly increase the model's tendency to hallucinate**. **[S]**
  <https://arxiv.org/abs/2405.05904>
  - Interpretation the authors support: LLMs acquire factual knowledge in **pretraining**; fine-tuning teaches
    them to *use* it. Fine-tuning is the wrong instrument for adding facts.
- **RAG beats unsupervised fine-tuning for knowledge injection**, both for knowledge seen in pretraining and
  for entirely new knowledge; fine-tuning helps somewhat, but exposure to many *paraphrases* of the same fact
  is needed for it to stick at all. **[S]** <https://arxiv.org/abs/2312.05934>
- **Continual fine-tuning causes general forgetting, and it gets worse with scale (1B→7B)** — plausibly because
  the larger model had more to lose. **[S]** <https://arxiv.org/abs/2308.08747>
- **The stability gap.** On a distribution shift, performance **drops sharply and then slowly recovers**; a
  naive single-epoch pass over a large domain corpus spends most of its budget in the trough. Mitigations:
  multiple epochs over a properly-sized subset; high-quality sub-corpus only; a data mixture close to the
  pretraining distribution. **[S]** <https://arxiv.org/pdf/2406.14833>,
  <https://openreview.net/forum?id=4y6Q98hJzr>
- **Fresh knowledge is not free even when it works:** the "new-knowledge-induced factual hallucination" line of
  work analyses the mechanism. **[S]** <https://arxiv.org/pdf/2511.02626>

---

# PART B — What actually works at LLM scale, ranked

Ranking criterion: *would a team shipping a real model use this, and does the published evidence support it at
≥1B parameters?*

### Tier 1 — Works, is used in production, evidence is strong

1. **Replay as a data-mixture ratio + LR re-warming/re-decaying.**
   The single highest-value result in this literature: LR re-warm + re-decay + replay of a few percent of the
   previous distribution **matches full retraining from scratch**, validated at 405M and 10B. **[S]**
   <https://arxiv.org/abs/2403.08763>
   *Why it wins:* costs nothing to implement, no task boundaries, no architecture change, no inference cost.
   *Caveat:* it presumes you still **have** the old data. That is the assumption your project deliberately
   refuses.

2. **Retrieval augmentation (RAG / kNN-LM / SILO-style datastores) for knowledge that changes.**
   RAG consistently outperforms unsupervised fine-tuning for injecting knowledge. **[S]**
   <https://arxiv.org/abs/2312.05934> Knowledge in a store is *updatable, deletable, and attributable*, which
   weights are not. **[S]** <https://arxiv.org/abs/2308.04430>
   *Caveat:* it changes what the system *says*, not what it *knows*.

3. **Parameter-efficient isolation (LoRA/adapters) when you control task identity.**
   Zero backbone forgetting; small; deployable. O-LoRA's orthogonal subspaces are the credible continual
   variant. **[S]**
   <https://www.semanticscholar.org/paper/Orthogonal-Subspace-Learning-for-Language-Model-Wang-Chen/28fde851680a40fbbc5c6a44bd3ac6f5ca4ad284>
   *Caveat:* needs a router or a task id; caps at "adapting", not "learning new facts".

4. **Data-curriculum fixes for the stability gap** — multi-epoch on right-sized high-quality subsets, mixture
   close to pretraining. Cheap, effective, boring. **[S]** <https://arxiv.org/pdf/2406.14833>

### Tier 2 — Works in the literature, rarely used at scale

5. **DER / DER++ (logit-replay).** The strongest simple *academic* baseline; but at LLM scale it collapses into
   "replay", and storing logits over a 100k-vocab is expensive. **[S]**
   <https://proceedings.neurips.cc/paper/2020/file/b704ea2c39778f07c617f6b7ce480e9e-Paper.pdf>
6. **Buffer-selection methods (GSS, MIR, herding).** Real gains at small buffer sizes; the gains shrink as the
   buffer grows, and at LLM scale buffers are large. **[S]** <https://arxiv.org/abs/1903.08671>
7. **Model editing (ROME/MEMIT)** for a *bounded, small* number of targeted factual corrections — genuinely
   useful under ~50–100 edits. **[S]** <https://arxiv.org/html/2401.04700>
8. **Test-time neural memory (Titans and successors).** Promising, recent, evidence at 340M–760M, not yet at
   frontier scale. **[S]** <https://arxiv.org/html/2501.00663>

### Tier 3 — Mostly of historical/benchmark interest at LLM scale

9. **EWC / SI / MAS.** Still cited, still implemented, essentially never the deciding factor in a shipped LLM.
   Their evidence base is small-image-benchmark; the known failure modes (diagonal-Fisher error, importance
   underestimation, over-restriction, progressive rigidity) are all documented. **[S]**
   <https://arxiv.org/html/2603.18596v1>
10. **GEM / A-GEM / OGD.** GEM's per-task backward passes and QP do not survive contact with a 7B model; A-GEM
    degenerates toward plain ER; OGD's stored basis is unaffordable in a billion-dimensional parameter space.
    **[S]** <https://arxiv.org/abs/1706.08840>, <https://arxiv.org/pdf/1910.07104>
11. **PackNet / HAT / Progressive Nets.** Zero forgetting, but a hard capacity ceiling and a task-id requirement
    at inference — both fatal for an open-ended stream. **[S]** <https://arxiv.org/html/2604.24637>
12. **Generative replay.** Compounding degradation across replay generations. Survives at LLM scale only in the
    "self-synthesized rehearsal" form, and only for instruction data. **[M]/[S]**

### Honest list of what is known **not** to work

- **Fine-tuning to add new facts.** It is slow to learn and it **linearly increases hallucination** as the new
  facts are absorbed. **[S]** <https://arxiv.org/abs/2405.05904>
- **Sequential model editing past a few hundred edits.** ROME/MEMIT collapse; on modern LLaMA-class models,
  ~300 edits took downstream performance to ~zero. **[S]** <https://arxiv.org/html/2405.16821>
- **Gradient-ascent unlearning as a deletion guarantee.** It leaves representations intact and is reversed by
  benign relearning and by embedding-space attacks. **[S]** <https://arxiv.org/html/2508.06467v1>,
  <https://arxiv.org/pdf/2406.13356>, <https://arxiv.org/pdf/2402.09063>
- **Deleting from a datastore as unlearning of something the model was also trained on.** Doesn't work, by
  construction. **[S]** <https://petronellatech.com/blog/clear-the-plate-enterprise-ai-unlearning-across-fine-tunes-rag-and/>
- **Regularisation alone (EWC-family) as a general answer.** Beaten by small replay buffers across the
  benchmark literature. **[M]**
- **Recency-only buffers/caches under non-stationarity.** Reservoir exists precisely because FIFO does not give
  a representative sample of the stream. **[S]**
  <https://proceedings.neurips.cc/paper/2020/file/b704ea2c39778f07c617f6b7ce480e9e-Paper.pdf>
- **Reservoir sampling as a *complete* answer either.** Its acceptance probability decays, so it progressively
  stops absorbing new skills. **[S]** <https://arxiv.org/abs/2504.20932>
- **Ad-hoc agent-memory eviction.** The field says so about itself. **[S]** <https://arxiv.org/pdf/2606.12945>

---

# PART C — Direct comparison to this codebase

## C.1 — Is a surprise-gated write standard? What else is used to decide what to store?

**Short answer: surprise-gating is real prior art, but it is *not* standard in the retrieval/kNN-LM family your
read path belongs to — it is standard in the RL-replay and neural-memory families. Your system is a hybrid,
and that hybrid is where the risk lives.**

**Prior art for surprise as the write/priority signal:**

| System | Surprise signal | Used for |
|---|---|---|
| Prioritised Experience Replay | \|TD error\| | *sampling* priority (stores everything) **[S]** <https://arxiv.org/pdf/2209.00532> |
| Titans | gradient-based surprise + momentum | *how much* to write into neural memory; decay gate forgets low-surprise **[S]** <https://arxiv.org/html/2501.00663> |
| Novelty-gated encoding (cognitive science) | prediction error | hypothesised gate on episodic encoding **[S]** <https://www.nature.com/articles/s41539-023-00166-x> |
| Surprise-gated robot episodic memory | Bayesian surprise / prediction error | **decides when to store** a memory trace **[S]** <https://arxiv.org/pdf/2606.03787> |
| Generative Agents | LLM-rated "importance" 1–10 | retrieval score only, *not* encoding **[S]** <https://arxiv.org/pdf/2606.12945> |

**What the kNN-LM family actually does: no gate at all.** kNN-LM stores **every training token**; Memorizing
Transformers append **every** local (k,v) pair and drop the oldest. **[S]**
<https://arxiv.org/pdf/2203.08913> Selectivity in that family is applied *after* the fact, as pruning
(greedy merging by key-proximity + same target token) or *at read time* (adaptive retrieval gated on LM
confidence). **[S]** <https://arxiv.org/pdf/2109.04212>

**The alternative write policies the literature uses:**

1. **Store everything** (kNN-LM, Memorizing Transformers, RETRO) — then prune by redundancy.
2. **Uniform random / reservoir** (ER, DER) — the *unbiased* choice; specifically designed for streams with no
   boundaries. **[S]**
3. **Gradient diversity** (GSS) — pick items whose gradients span the most directions; a **coverage** criterion,
   not a difficulty criterion. **[S]** <https://arxiv.org/abs/1903.08671>
4. **Class/prototype coverage** (iCaRL herding). **[M]**
5. **Interference-based** (MIR) — store/replay what *would* be damaged. **[M]**
6. **Learned importance** (Generative Agents' LLM rating; the 2026 "multi-factor value model" line). **[S]**
   <https://arxiv.org/pdf/2606.12945>
7. **Redundancy/dedup** (greedy merging). **[S]** <https://arxiv.org/pdf/2109.04212>

**The known pathology your quantile gate inherits — and your own logs already found it.**
Raw error-magnitude priority conflates *epistemic* surprise (learnable, worth storing) with *aleatoric*
surprise (noise, worth discarding). This is precisely why PER needs importance-sampling correction and why
uncertainty-aware PER variants exist. **[S]** <https://rlj.cs.umass.edu/2025/papers/RLJ_RLC_2025_45.pdf>
Your `CL_TESTBED.md` records the same collision from the other end: *"the write gate stores SURPRISING tokens,
and B flags SURPRISING tokens — so genuine-novel and wrong are conflated"*, giving ~2% precision at a realistic
1% corruption rate. **[CODE]** That is not a bug in your self-consistency check; it is the documented failure
mode of surprise-as-value, and no threshold tuning fixes it. The literature's answer is to **use a second,
independent axis** — which is exactly what your Verification-by-reconstruction rename is doing, and it is the
right instinct.

**Also note a subtle property of your quantile gate specifically:** it targets a *constant write fraction*
(`gate_target`) by construction. That makes the store's composition **proportional to how much of each domain
is in the stream**, not to how much of each domain is *worth remembering*. It is a stratified-by-time policy,
not a stratified-by-domain one. Under `PHASED`, time-proportional means a faded domain's share monotonically
decays. See C.5.

**Recommendations grounded in the above:**
- Add an **unconditional reservoir slice** (e.g. 10–20% of `cap` filled by reservoir sampling regardless of
  surprise) as an unbiased control population. It costs almost nothing and it gives you a directly comparable
  arm to attribute the gate's value.
- Add a **redundancy check at write** (greedy-merge style: if a near-duplicate key with the same `tok` exists,
  bump its `use` instead of allocating a slot). Published cost: 40% of the store recovered for 0.2 ppl. **[S]**
- Treat surprise as **priority**, not as a hard admission gate — PER's actual design.

## C.2 — The rekey idea: is re-encoding stored keys as the encoder drifts prior art?

**Yes, unambiguously — this is REALM's central engineering problem, and REALM's solution is your solution.**

- **REALM**: "The search index becomes stale every time model parameters are updated." Their fix: an
  **asynchronous index-builder job** that re-embeds and re-indexes **all** documents from a parameter snapshot
  every several hundred steps, running concurrently with the trainer. They report that optimisation is stable
  **provided the refresh is frequent enough**. **[S]**
  <http://proceedings.mlr.press/v119/guu20a/guu20a.pdf>
  Your `_rekey_amortized` is the same idea with a different scheduling strategy: instead of a periodic global
  rebuild, you re-encode a slice per step so every entry is refreshed on a rolling cadence with no spike. The
  code comments say exactly this. **[CODE]**
- **Memorizing Transformers** took the *opposite* branch: rather than re-encode, they **normalise keys and
  queries** so old and new keys keep comparable magnitudes, and report the model learns to compensate by
  adjusting its queries. **[S]** <https://arxiv.org/pdf/2203.08913> — Note that your `_commit`/`rekey` both
  `F.normalize` the keys, so you already have their mitigation *as well as* the re-encode.
- **RETRO** took the third branch: **freeze the retriever entirely** (a fixed BERT), so the index is built once
  and can never go stale. arXiv 2112.04426 **[M]**
- **Atlas** studies refresh strategy and cost explicitly. **[S]** <https://arxiv.org/pdf/2208.03299>
- **DER's stale-logit problem is the same phenomenon in the replay family**: stored targets were produced by an
  older model, and recent work explicitly proposes "correction of past outputs". **[S]**
  <https://arxiv.org/abs/2504.20932>

**So: rekey is not novel. What *is* comparatively unusual in your setup:**

1. **Token-level rather than document-level.** REALM re-embeds documents; you re-encode per-entry raw context
   windows to regenerate token-level datastore keys. Standard kNN-LM builds its datastore **once, after
   training, from a frozen LM** — the staleness problem does not arise there because the model is done.
   Re-keying a *token-level* datastore continuously **during from-scratch training** is a combination I did not
   find published. **[M — absence of evidence; verify before claiming novelty.]**
2. **Amortized/rolling rather than batch-refresh.** REALM's snapshot-refresh has a discrete staleness sawtooth;
   your rolling refresh has a uniform staleness distribution bounded by the cycle length. Arguably better
   engineering; not a research contribution on its own.
3. **You store the raw `ctx` to enable it.** That is the necessary cost, and it is the same cost REALM pays by
   keeping the raw document corpus. Worth stating explicitly in any writeup: a re-keyable store cannot be
   key-only.

**What the literature would want you to measure, and you currently don't:**
- REALM's finding is a **cadence** result: stability holds *if refresh is frequent enough*. You have
  `REKEY_CHUNK` and `REKEY_AMORTIZED` as knobs. The publishable experiment is the **staleness–performance
  curve**: sweep the effective refresh period (including ∞ = frozen keys, and the Memorizing-Transformers arm =
  normalise-only, no re-encode) and plot retrieval hit quality and bpb. Your `cl_bench` already reports
  `mem[frozen key] +1.73` vs `mem[model key + re-key] +1.19` **[CODE]** — that's two points of exactly this
  curve and is your strongest rekey evidence. Fill the curve in.

## C.3 — Bounded stores and eviction policy choices

**Bounded stores are the exception, not the rule, in the retrieval-LM literature.** kNN-LM, RETRO and SILO all
scale the datastore *up* — kNN-LM's effectiveness is explicitly tied to the datastore being orders of magnitude
larger than the training corpus. **[S]** <https://arxiv.org/pdf/2503.22426> Bounded stores appear in three
other places:

| Setting | Bound | Policy | Source |
|---|---|---|---|
| Memorizing Transformers | fixed window (up to 262K tokens) | **FIFO** — append local, drop oldest | **[S]** <https://arxiv.org/pdf/2203.08913> |
| Replay buffers (ER/DER) | fixed *k* samples | **reservoir sampling** (uniform over the stream) | **[S]** <https://proceedings.neurips.cc/paper/2020/file/b704ea2c39778f07c617f6b7ce480e9e-Paper.pdf> |
| MemGPT | context pages | **recency + capacity pressure**, FIFO queue | **[S]** <https://arxiv.org/pdf/2606.12945> |
| Agent memory generally | store size | FIFO / lifecycle / local delete, **"without relevance"** | **[S]** (same) |
| kNN-LM pruning | offline | greedy merge of near-duplicate keys with equal target | **[S]** <https://arxiv.org/pdf/2109.04212> |

**How your choices map:**

- `evict="recency"` (circular overwrite) ≡ **Memorizing Transformers / MemGPT FIFO**. Well-precedented, and
  well-known to be the *weak* choice for retaining old material — reservoir exists because FIFO isn't a
  representative sample.
- `evict="usage"` (sampled least-retrieved, with write-count decay) ≡ **LFU with aging** from cache theory; the
  decay term is the classic fix for LFU's "cache pollution by historically-popular items". Your sampled top-k
  (O(m) not O(cap)) is standard practice for approximate-LRU/LFU in production caches (Redis does the same).
  **[M]**
- `n_own > 1` per-owner blocks with `quota` and per-owner **true LRU** ≡ **stratified / multiple buffers**,
  which is exactly what the 2025 DER-improvement paper proposes as a fix to plain reservoir's imbalance.
  **[S]** <https://arxiv.org/abs/2504.20932> Your writes-compartmentalised / reads-global split is a sensible
  design and I did not find it stated that way in the retrieval literature. **[M — possible small novelty.]**
- **Missing from your set, and cheap:** reservoir sampling. It is the one policy with a *statistical guarantee*
  about what the buffer represents, and it needs no task boundaries — the exact regime you're in.

**The specific hazard in your configuration.** LRU and FIFO are both **recency-correlated**, and your `PHASE_SCHED`
makes recency perfectly correlated with **domain identity**: when a process fades, *every* one of its entries
stops being written and (mostly) stops being read, so both policies delete the entire domain. Cache theory calls
this the **scan/one-shot access pattern**, the classic LRU pathology. `evict="usage"` partially resists it (a
faded-but-still-retrieved entry survives), but `use_decay` re-couples it to time by decaying on *write count*,
which under a faded domain means decaying toward zero with nothing to replenish it. **[CODE]** Your run
observed exactly this — 100% eviction of faded material. **[CODE]**

**Concrete options if you want faded-domain retention:**
1. **Partition by `src`/process, not by expert** (or in addition), with a **floor quota** per domain. You
   already have the machinery — `own` is just being keyed on the wrong field for this purpose.
2. **Per-domain reservoir sampling.** Each domain's slice is a uniform sample of that domain's whole history,
   independent of when it occurred. This is the principled answer.
3. **Decay `use` on wall-clock/step count rather than on global write count**, so a quiet domain's entries decay
   at the same rate as a busy one's rather than being punished for the stream's composition.
4. **Protected/consolidated tier**: entries that survive N rekey cycles *and* pass Verification get promoted to
   a non-evictable partition. This is the CLS "consolidation" analogue and would give you a two-timescale store
   to match your two-timescale system.
5. Note the **learning-augmented cache replacement** line of work aimed exactly at semantic retrieval buffers —
   the observation being that classic policies fail there. **[S]** <https://arxiv.org/pdf/2607.00394>

**One honest framing point.** Your code comment says *"whether faded knowledge SHOULD be protected is a design
decision, not a bug."* **[CODE]** That is correct and well-put — but note that it decides the outcome of your
headline unlearning claim. If eviction removes faded domains, then "unlearn by provenance" is only ever
demonstrable on *active* domains, i.e. on knowledge the system was about to be tested on anyway. The literature
would read that as a significantly weaker claim. Make the design decision explicitly and defend it.

## C.4 — How is retention normally measured, and is your measure sound?

**The standard protocol (classification lineage):** train on tasks 1..T; after each task, evaluate on **all**
tasks, producing a T×T matrix R. From it:
- **ACC** = mean final performance across tasks
- **BWT (backward transfer)** = mean of (final performance on task *i*) − (performance on task *i* right after
  learning it). **BWT < 0 is forgetting**; BWT ≥ 0 means no catastrophic forgetting on average.
- **FWT (forward transfer)** = performance on task *i* before training on it, vs a random-init baseline.
- **Forgetting Measure (FM)** = *maximum* drop per task over the sequence, not just the endpoint.
**[S]** <https://arxiv.org/abs/1706.08840>, <https://arxiv.org/pdf/1810.13166>,
<https://towardsdatascience.com/the-metrics-of-continual-learning-08f2d1cd959b/>

**The LM/continual-pretraining adaptation is *exactly your metric*:**
> "For each phase and each domain, the perplexity is recorded on the held-out split of domain after training
> has finished. The full per-condition output is a T × D matrix… The Backward Transfer (BWT) metric, adapted to
> perplexity, measures the averaged relative degradation… a Forgetting Measure (FM) captures the maximum
> per-domain forgetting over the sequence." And: **"Bits-per-byte (BPB) normalizes by character/byte count and
> is the right comparison metric across tokenizer families."** **[S]**
> <https://arxiv.org/pdf/2605.15053>, and see <https://arxiv.org/pdf/2402.17400>,
> <https://arxiv.org/pdf/2205.09357>

**Verdict on "held-out bits/byte per domain, compared across a run boundary": sound, and in several respects
better than what is typically published.** Specifically:

✅ **Bits/byte is the right unit** — it is the tokenizer-neutral normalisation, and it is not optional for you,
because your vocabulary *grows during the run* (`TOKENIZER=1`, minting). Any perplexity-per-token number would
be incomparable across a retok. Your `holdout_bpb` uses `TOK.bytes_per_id` for an exact byte denominator.
**[CODE]** This is correct and many published comparisons get it wrong.

✅ **Held-out tail, not training text** — avoids scoring memorisation.

✅ **Name-keyed, name-seeded window draw** — the code comment explains why (index-keyed probes silently compare
`eng` against `py` after a domain is inserted). This is a real bug class and you've closed it. **[CODE]**

✅ **Per-window mean ± standard error, with a 2σ decision rule** and an explicit "inside the noise, do not read
this as forgetting" message. **[CODE]** Most CL papers report point estimates with no error bars at all. This
is strictly better practice than the literature norm.

✅ **The cross-run-boundary comparison is a legitimate two-point BWT** — it is exactly "performance on domain
*d* at the end of phase *t*, versus at the end of phase *t+k*", which is the R-matrix comparison, just sparse.

Now the problems, in order of severity:

⚠️ **1. It measures the weights, not the system.** `holdout_bpb()` calls `_eval_logits(model, fab, FABRIC, X)`
— **no memory**. `bpb_true()` is the function that interpolates the store (`pp = (1-hp)*pm + hp*pmem`).
**[CODE]** So your headline "ONLY number that spans the run boundary" is a *parametric* retention number for a
project whose thesis is that retention lives in the store. **This is the single most important fix in this
document.** Report **both** arms — `holdout_bpb(use_mem=False)` and `holdout_bpb(use_mem=True)` — and their
difference is the store's marginal contribution per domain over time. That decomposition is also the direct
answer to C.5 and would be the most interesting plot in the project.

⚠️ **2. No "right after learning it" reference point per domain, so it is not a true BWT.** BWT needs
`R[i,i]` — performance on domain *i* immediately after its phase ends. You have the raw material: the
`LEARNING CURVE` block already snapshots per-process bpb every `RATE_EVERY` steps with an active/absent flag.
**[CODE]** Promote that into the T×D matrix and compute BWT and FM from it; then `report_holdout` becomes one
column of a proper matrix rather than a standalone number.

⚠️ **3. No control arm.** A retention number is uninterpretable alone. The literature always needs at least:
(a) a **joint/stationary control** (same total tokens, no phase structure) — you ran one once and got
+0.65 b/B for faded material; **[CODE]** and (b) an **independent-expert / retrain-from-scratch upper bound**
per domain. Without (a) you cannot separate forgetting from "this corpus is intrinsically harder"; without (b)
you cannot say how much of the achievable performance you're keeping. Your `ANCHORS` block (uniform / order-0 /
order-1 baselines) is a good *floor*; you have no ceiling. **[CODE]**

⚠️ **4. `HOLDOUT_N=32` windows.** The SE is reported so this is self-policing, but the 2σ rule at n=32 will
declare "HELD (inside the noise)" for real effects of moderate size. If a null result is going to be a claim,
power it: 128–256 windows costs one extra eval pass.

⚠️ **5. Cross-run comparability depends on the eval *harness* being unchanged too.** The probe is seeded by
domain name and the byte denominator is exact, so vocabulary growth is handled. But `_eval_logits` routes
through `fab if FABRIC else None` — if `FABRIC`, `EXPERTS`, or the routing changes between runs, the comparison
silently changes what is being scored. Store the relevant config hash alongside the probe in the checkpoint and
refuse (or loudly warn on) a cross-boundary comparison when it differs. You already do a `_config_audit()`;
wire it into `report_holdout`.

⚠️ **6. The within-stream RETENTION block (earliest vs latest windows of the same process) is a *drift*
measure, not a forgetting measure, when both ends were trained on within the same run.** Your comment already
says "both ends were TRAINED on… so a positive number is FORGETTING, not generalisation" **[CODE]** — that's
right for a *single pass* stream, but under `DISK_STREAM` multi-epoch resampling the "earliest windows" are
from an earlier epoch's *different text*, and the comparison then partly measures which sample is harder.
Confirm the single-pass assumption holds in the configuration you report.

## C.5 — What does the literature predict about a domain whose memory entries are all evicted while the weights retain it?

**This is a predicted, well-understood outcome, and it has a name in three different literatures.**

**Prediction 1 — CLS / systems consolidation: this is what "consolidated" looks like.**
Complementary Learning Systems theory: a fast hippocampal store learns specifics quickly; a slow neocortical
system gradually extracts structure; **"systems-level consolidation is considered complete when memory
retrieval can occur without the hippocampus."** **[S]**
<https://www.cell.com/trends/cognitive-sciences/abstract/S1364-6613(16)30043-2>,
<https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9606815/>
On that reading, a domain whose entries are all gone but whose bpb is intact is a domain the *weights have
consolidated*. That is a **success** of the two-store architecture, not a failure — provided you can show the
weights actually did the work, which requires the with-memory/without-memory decomposition from C.4.1.

**Prediction 2 — kNN-LM: the store's marginal value is concentrated where the parametric model is weak, so a
well-modelled domain loses little when its entries go.**
- Retrieval gains concentrate on **long-tail / rare phenomena**; on frequent, well-fit tokens retrieval adds
  little. **[S]** <https://arxiv.org/pdf/2503.22426>, <https://arxiv.org/pdf/2210.15859>
- The mechanistic account is that kNN-LM helps where the LM is **under-fitting** (softmax bottleneck /
  under-trained tokens). **[S]** <https://openreview.net/pdf?id=ARDbU7beLp>
- Adaptive retrieval can skip **half** of all retrievals with no perplexity cost — i.e. **half the time the
  store contributes nothing measurable**. **[S]** <https://arxiv.org/pdf/2109.04212>
→ **Therefore: near-zero Δbpb when a domain's entries are evicted is the *expected* result for any domain the
weights fit well.** It is evidence about *where* the knowledge is, not evidence that the memory is useless.
The corresponding prediction is quantitative: **the store's marginal contribution per domain should be largest
early in that domain's phase and decay as the weights absorb it**, and should be persistently larger for
rare/high-entropy domains. That is a testable curve and you have every ingredient to plot it.

**Prediction 3 — Unlearning: memory deletion cannot unlearn what the weights learned, and everyone in that
field knows it.**
- **"Deleting a PDF from your knowledge base does not remove the information if you fine-tuned the model on
  that PDF."** **[S]**
  <https://petronellatech.com/blog/clear-the-plate-enterprise-ai-unlearning-across-fine-tunes-rag-and/>
- Datastore deletion is "instant, zero compute" but **"the underlying model still knows the information; it
  just isn't being fed it actively."** **[S]** (same); see also **[S]** <https://arxiv.org/abs/2410.15267>
- **SILO's whole architecture exists to satisfy the precondition that makes store-deletion a real deletion:**
  train the parametric LM *only* on data you will never need to remove; keep removable data *exclusively* in
  the datastore. **[S]** <https://arxiv.org/abs/2308.04430>

**The consequence for this project's headline claim, stated plainly.**
Your system **trains the weights on the same stream that writes the memory**. Every domain is therefore in both
places. So:
- Your unlearn result on an ACTIVE domain (target +0.2 to +0.3 b/B, others ~0.005) is a measurement of the
  **retrieval channel's contribution**, not of knowledge removal. A reader from the unlearning literature will
  say so immediately.
- Your unlearn result on a FADED domain is **vacuous by construction** — the code already detects this and
  skips the test when `< 50` entries remain. **[CODE]** That check is honest and should stay.
- The observation you actually made — *all entries evicted, weights still retain it* — is the empirical
  demonstration that memory-deletion ≠ unlearning **in an architecture where the weights also trained on the
  data**. That is a genuine, reportable negative result, and it is consistent with the entire unlearning
  literature.

**What to do about it — three coherent positions, pick one and defend it:**

1. **The SILO position (strongest for the product claim).** Introduce a class of data that goes **only** into
   memory and never into the gradient. Then deletion is real deletion and you can prove it: bpb on that
   material should return to the never-trained baseline after `delete_src`. This is a small change (a per-source
   flag that suppresses the LM loss for those windows) and it converts your headline claim from "retrieval
   contribution removed" to "knowledge removed", which is a categorically stronger statement. **[S]**
   <https://arxiv.org/abs/2308.04430>
2. **The CLS position (strongest for the science claim).** Own the consolidation framing: the store is a fast
   buffer whose job is to carry a domain until the weights absorb it, and eviction of a consolidated domain is
   correct behaviour. Then the metric that matters is the **with-memory minus without-memory gap per domain
   over time**, and the result is "the gap closes as consolidation proceeds". This is a clean, publishable
   curve and it reframes your eviction observation from an embarrassment into the main finding. **[S]**
   <https://www.cell.com/trends/cognitive-sciences/abstract/S1364-6613(16)30043-2>
3. **The retention position.** If faded-domain retention *in the store* is the goal, change the eviction policy
   per C.3 (per-domain reservoir or floor quotas) and show the resulting retention/plasticity tradeoff curve.
   Be aware this trades against plasticity in the way the DER/reservoir literature documents. **[S]**
   <https://arxiv.org/abs/2504.20932>

**One more prediction worth pre-empting.** If you do protect faded domains' entries, expect the *read* side to
degrade: a store full of stale keys for absent domains raises the chance of cross-domain false neighbours, and
your `read()` is deliberately global across owners. The literature's mitigation is read-side confidence gating
(adaptive λ / adaptive retrieval) rather than store-side purity — you already have `hp = _mem_hp(dist, conf)`,
which is the right hook. **[S]** <https://arxiv.org/pdf/2211.07828>, <https://arxiv.org/pdf/2109.04212>

---

# Appendix — Reading list, grouped, with URLs

**Surveys / entry points**
- Continual Learning of LLMs: comprehensive survey (repo) — <https://github.com/Wang-ML-Lab/llm-continual-learning-survey> **[S]**
- Continual learning in generative models (repo) — <https://github.com/Ghy0501/Awesome-Continual-Learning-in-Generative-Models> **[S]**
- Machine Unlearning in 2024 (Ken Liu, Stanford) — <https://ai.stanford.edu/~kzliu/blog/unlearning/> **[S]**
- New metrics for continual learning — <https://arxiv.org/pdf/1810.13166> **[S]**
- TRACE: continual-learning benchmark for LLMs — <https://arxiv.org/pdf/2310.06762> **[S]**

**Regularisation**
- EWC — <https://arxiv.org/pdf/1612.00796> **[S]**
- EWC done right / Fisher failure analysis — <https://arxiv.org/html/2603.18596v1> **[S]**
- Stabilizing EWC — <https://arxiv.org/abs/2109.10021> **[S]**
- FROMP (functional regularisation) — <https://arxiv.org/pdf/2004.14070> **[S]**

**Replay**
- DER / DER++ — <https://proceedings.neurips.cc/paper/2020/file/b704ea2c39778f07c617f6b7ce480e9e-Paper.pdf> **[S]**
- DER + reservoir improvements (2025) — <https://arxiv.org/abs/2504.20932> **[S]**
- GSS (gradient-based sample selection) — <https://arxiv.org/abs/1903.08671> **[S]**
- Uncertainty-prioritized experience replay — <https://rlj.cs.umass.edu/2025/papers/RLJ_RLC_2025_45.pdf> **[S]**
- Actor-prioritized experience replay — <https://arxiv.org/pdf/2209.00532> **[S]**

**Parameter isolation**
- PackNet — <https://arxiv.org/abs/1711.05769> **[S]**
- HAT — <https://arxiv.org/pdf/1801.01423> **[S]**
- Architecture-based CL overview (PNN etc.) — <https://pengxiang-wang.com/posts/architecture-based-continual-learning> **[S]**
- Capacity-ceiling analysis of PackNet/HAT — <https://arxiv.org/html/2604.24637> **[S]**
- O-LoRA (orthogonal subspace CL for LMs) — <https://www.semanticscholar.org/paper/Orthogonal-Subspace-Learning-for-Language-Model-Wang-Chen/28fde851680a40fbbc5c6a44bd3ac6f5ca4ad284> **[S]**

**Optimisation-based**
- GEM — <https://arxiv.org/abs/1706.08840> **[S]**
- OGD — <https://arxiv.org/pdf/1910.07104> **[S]**
- Improved episodic-memory lifelong learning — <https://proceedings.neurips.cc/paper/2020/file/0b5e29aa1acf8bdc5d8935d7036fa4f5-Paper.pdf> **[S]**

**Retrieval / kNN-LM / external memory**
- Why do kNN-LMs work? — <https://openreview.net/pdf?id=ARDbU7beLp> **[S]**
- Long-tail crisis in kNN-LM — <https://arxiv.org/pdf/2503.22426> **[S]**
- When and how to rely on retrieval in kNN-LM — <https://arxiv.org/pdf/2210.15859> **[S]**
- Efficient kNN-LM (pruning, adaptive retrieval, PCA) — <https://arxiv.org/pdf/2109.04212> **[S]**
- Adaptation approaches for kNN-LM — <https://arxiv.org/pdf/2211.07828> **[S]**
- RetoMaton — <https://arxiv.org/pdf/2201.12431> **[S]**
- Memorizing Transformers — <https://arxiv.org/pdf/2203.08913> **[S]**
- REALM — <http://proceedings.mlr.press/v119/guu20a/guu20a.pdf> **[S]**
- Atlas — <https://arxiv.org/pdf/2208.03299> **[S]**
- Generalisation of retrieval-enhanced transformers — <https://arxiv.org/pdf/2302.12128> **[S]**
- SILO (nonparametric datastore, opt-out by removal) — <https://arxiv.org/abs/2308.04430> **[S]**
- Reliable/adaptable/attributable LMs with retrieval — <https://arxiv.org/pdf/2403.03187> **[S]**

**Memory write policy / surprise gating / agent memory**
- Titans (test-time surprise + momentum + forgetting gate) — <https://arxiv.org/html/2501.00663> **[S]**
- Surprise-gated robot episodic memory — <https://arxiv.org/pdf/2606.03787> **[S]**
- Learning what to remember: multi-factor value model for agentic memory — <https://arxiv.org/pdf/2606.12945> **[S]**
- Is agent memory a database? — <https://arxiv.org/html/2605.26252v1> **[S]**
- Learning-augmented replacement for semantic retrieval buffers — <https://arxiv.org/pdf/2607.00394> **[S]**
- Agent memory consolidation (importance/merge/decay/eviction framing) — <https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation> **[S]**
- Prediction error and episodic memory encoding (npj Sci. Learn.) — <https://www.nature.com/articles/s41539-023-00166-x> **[S]**
- Evidence *against* novelty-gated encoding — <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9400662/> **[S]**

**Model editing**
- Model editing harms general abilities — <https://arxiv.org/html/2401.04700> **[S]**
- PRUNE: perturbation-restrained sequential editing (condition-number analysis) — <https://arxiv.org/html/2405.16821> **[S]**
- Pitfalls of knowledge editing (conflict, distortion) — <https://aclanthology.org/2024.findings-emnlp.550.pdf> **[S]**
- Energy-regularized sequential editing on hyperspheres — <https://arxiv.org/pdf/2510.01172> **[S]**
- "No more model editing! Just selective contextual reasoning" — <https://arxiv.org/pdf/2503.05212> **[S]**

**Unlearning**
- Benign relearning jogs unlearned memory — <https://arxiv.org/pdf/2406.13356> **[S]**
- Soft-prompt / embedding-space attacks on unlearning — <https://arxiv.org/pdf/2402.09063> **[S]**
- Gradient-ratio influence + noise injection (GA critique) — <https://arxiv.org/html/2508.06467v1> **[S]**
- TOFU & WMDP benchmarks overview — <https://www.emergentmind.com/topics/tofu-and-wmdp-benchmarks> **[S]**
- Unlearning meets RAG — <https://arxiv.org/abs/2410.15267> **[S]**
- Practical fine-tune vs RAG deletion distinction — <https://petronellatech.com/blog/clear-the-plate-enterprise-ai-unlearning-across-fine-tunes-rag-and/> **[S]**

**Knowledge injection / continual pretraining**
- Does fine-tuning on new knowledge encourage hallucinations? — <https://arxiv.org/abs/2405.05904> **[S]**
- New-knowledge-induced factual hallucination (mechanism) — <https://arxiv.org/pdf/2511.02626> **[S]**
- Fine-tuning or retrieval? — <https://arxiv.org/abs/2312.05934> **[S]**
- Simple and scalable strategies to continually pre-train LLMs — <https://arxiv.org/abs/2403.08763> **[S]**
- Efficient continual pretraining by mitigating the stability gap — <https://arxiv.org/pdf/2406.14833> **[S]**
- Catastrophic forgetting in LLMs during continual fine-tuning — <https://arxiv.org/abs/2308.08747> **[S]**
- Investigating continual pretraining in LLMs — <https://arxiv.org/pdf/2402.17400> **[S]**
- Continual pretraining mitigates forgetting — <https://arxiv.org/pdf/2205.09357> **[S]**
- Task-free replay-free continual pretraining (T×D perplexity matrix, BPB) — <https://arxiv.org/pdf/2605.15053> **[S]**

**Neuroscience framing**
- CLS theory updated (Kumaran, Hassabis, McClelland) — <https://www.cell.com/trends/cognitive-sciences/abstract/S1364-6613(16)30043-2> **[S]**
- Bidirectional CLS interactions for consolidation — <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9606815/> **[S]**

---

## Priority actions extracted from Part C

1. **Report `holdout_bpb` with and without memory.** Single highest-value change; makes every retention number
   attributable to weights vs store. (C.4.1, C.5)
2. **Promote the LEARNING CURVE snapshots into a proper T×D matrix**; compute BWT and Forgetting Measure from
   it. (C.4.2)
3. **Add a stationary control arm as a standard part of any retention claim.** (C.4.3)
4. **Sweep rekey cadence** (frozen → normalise-only → rolling → per-step) and publish the staleness curve —
   this is your strongest defensible engineering result. (C.2)
5. **Add a reservoir-sampled slice of the store** as an unbiased control against the surprise gate. (C.1)
6. **Decide, explicitly, between the SILO position and the CLS position on eviction.** They imply different
   headline claims and different experiments. (C.5)
7. **Add write-time redundancy merging** — 40% store recovery for 0.2 ppl is published, and your store is
   bounded, so the payoff is larger for you than for kNN-LM. (C.1)
