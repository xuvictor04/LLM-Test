# Q3 — Domain isolation in a bounded shared retrieval store

## Short answer

**Per-source quota is not used in any of your five leads. No prior art found for reserving N
slots per domain in a shared non-parametric datastore.**

The field has three ways of avoiding the problem, and none of them is a quota:

1. **Don't bound the store.** (SeMem, Goodtriever) — control *admission* instead of eviction.
2. **Physically partition into separate stores.** (Goodtriever: two datastores)
3. **Prune per-cluster with cluster-local statistics.** (CREAM) — this is the closest structural
   analogue to a quota, and is probably the most useful thing in this file for you.

Only one lead (TraceRetain) actually implements a global capacity bound with eviction, and it
evicts by a global score with no source term at all.

**The cross-domain ~100% occupancy failure mode you asked about: not reported anywhere.** The
nearest thing is a *synthetic* 75%-occupancy stress test in TraceRetain.

---

## Lead-by-lead

### 1. arXiv 2303.01421 — note the retitling

This ID resolves to **two different papers depending on version**, which explains why you had
two names for it:

- **v1 (2023):** *Semiparametric Language Models Are Scalable Continual Learners.*
  Peng, Ge, Chen, Wei, Wang. Peking University / Microsoft.
- **v2 (17 Jul 2026):** *Learn to Memorize: Scalable Continual Learning in Semiparametric
  Models with Mixture-of-Neighbors Induction Memory.* Peng, Ge, Luo, Li, Wang.

I read v1 in full (the SeMem paper).

**Eviction/retention rule as a formula:** there isn't one. SeMem is an **admission** rule:

```
Memorize  if  log P(x_t | x_<t; Θ) < δ
Skip      otherwise                          (Eq. 4, δ = −1.5)

M ← M ∪ {(x̃_<t → x_t) | log P(x_t | x_<t; Θ) < δ}     (Eq. 5)
```

Store only what the model finds hard. The memory grows sublinearly because the model gets
better and finds fewer hard cases — not because anything is removed.

**Per-source? No.** δ is global. Nothing in the rule sees a domain label.

**Explicit statement that nothing is ever evicted** (Section 4.2): the paper attributes its
lack of catastrophic forgetting to the fact that SeMem never erases previous memory or updates
the parametric LM's weights.

**Cross-domain numbers (Table 4, Table 7):**

| Setting | MemRate | PPL |
|---|---|---|
| Bare GPT-2 small on WikiEvent-20H1 (different domain) | 62% | 29.0 |
| After CL on Newscrawl-20H1 → WikiEvent-20H1 | 57% | 27.5 |
| Bare GPT-2 small on Newscrawl-July (same domain) | 60% | 8.8 |
| After CL → Newscrawl-July | 49% | 8.2 |

Retention after a domain stops arriving (Table 7, after subsequently learning ACL papers):
Wiki-103 29.9 → 30.4 (**+0.5**), Newscrawl 8.6 → 9.2 (**+0.6**), while ACL went 40.5 → 22.7.

So: near-zero forgetting across domains — but that is *because the store is unbounded*. This
paper tells you nothing about what happens under a capacity bound. **It is not the paper you
were hoping it was.**

Scale: GPT-2 small/medium/large (123M/355M/774M), Newscrawl-20H1 439.38M tokens, FAISS with
4K centroids, 64-byte quantization, top-1K neighbors from 32 nearest centroids.

**Confidence: high.**

---

### 2. arXiv 2601.02708 — CREAM (KDD '26)

*CREAM: Continual Retrieval on Dynamic Streaming Corpora with Adaptive Soft Memory.*
Son, Kang, Kim, Ho, Kang, Lee, Yoon. Korea University / Yonsei. v1 6 Jan 2026, v2 10 Jan 2026.
DOI 10.1145/3770854.3780281.

**This is the most useful lead for you, and it isn't what its abstract suggests.**

CREAM is about continually training a *retrieval encoder*, not about a kNN-LM datastore. But
its memory-maintenance rule is exactly the structural mechanism you're looking for.

**Eviction rule as a formula (Algorithm 2, Section 4.2.2):**

```
retain x ∈ C   iff   SimDist(x, p_c) < μ_c + γ·σ_c
```

where `p_c` is the cluster prototype, `μ_c` and `σ_c` are the mean and standard deviation of
member distances to that prototype, and γ is a tunable decaying factor. Applied at the end of
each session. Admission uses the same shape with a different constant:

```
assign x to nearest cluster C   iff   SimDist(x, p_c) ≤ μ_c + λ·σ_c
otherwise   AddNewCluster(x)
```

Cluster statistics are kept as a BIRCH-style triplet ⟨N, LS, SS⟩ — count, linear sum of
distances, sum of squared distances — so μ and σ update incrementally and additively.

**Is it per-source? Effectively yes, structurally, without ever naming a source.** Each cluster
prunes *only its own members*, using *only its own* μ and σ. A newly-streaming domain cannot
evict an older domain's entries, because:
- new points too far from every existing prototype trigger `AddNewCluster` rather than
  displacing anything;
- pruning is intra-cluster and threshold-based, not competitive across clusters;
- there is no global capacity bound at all, so clusters never compete for slots.

Queries are then retained by random sampling *proportional to the number of retained documents
in each cluster* — which is a proportional-allocation rule, the nearest thing to a quota
anywhere in your five leads.

**This is the design pattern I'd steal.** Relative-radius pruning per cluster gives you domain
isolation as an emergent property of the eviction rule, without needing domain labels, without
a per-source counter, and without a global LRU that a burst can dominate. The cost is that
capacity is not actually bounded — you'd need to add a bound and decide what happens when
cluster count grows.

**Other numbers:** 12-bit RP-LSH → H = 2^12 = 4,096 hash buckets; prototype is a
(4,096 × 768) matrix. LOTTE: ~2,430 queries and 500,000 documents per session, ~80M token
embeddings/session. Token-pair operations drop from 1.7×10^12 to 1.1×10^9 (~1.6×10^3 ×
reduction). Reported gains: +27.79% Success@5, +44.5% Recall@10 over the strongest label-free
baseline. Sufficient LSH bitsize theorem: ⌈log₂(8 ln M / ε²)⌉ at ε* = 1/(3√e) ≈ 0.2.

**No cross-domain occupancy number is reported.** Appendix A.9 is titled "Qualitative Analysis
of Memory Dynamics" — I did not retrieve it and it may contain something. Flagged as unresolved.

**Confidence: high** on the rule; **moderate** on the absence of occupancy numbers, since I
didn't read the appendices.

---

### 3. arXiv 2606.29178 — TraceRetain

*Selective Memory Retention for Long-Horizon LLM Agents.* Pranath Reddy (independent
researcher, Huntsville AL). v1 28 Jun 2026. Also on OpenReview (id 9JiPHfleLn).

**The only lead with a real capacity bound and real eviction.**

**Rule (Section 3):**

```
s_i = wᵀ φ(m_i, t)
if |M_t| > K:  evict lowest-scoring entries
```

φ components: success/failure, normalized age, last-access gap, log access frequency,
specificity, redundancy, step efficiency, observed downstream utility, utility-count
confidence, last retrieval similarity, average retrieval similarity. K = 50.

Two scorers: TraceRetain-Linear (fixed hand-set weights) and TraceRetain-CEM (cross-entropy
method search over the same weights, tuned on a 20-task subset).

**Per-source? No.** φ has no source or domain term. `redundancy` is the only feature that
indirectly resists one source flooding the bank, and it is a similarity statistic, not a quota.

**The occupancy number you asked for — closest available, and it's synthetic.** Under the
noisy-write stress, each real write is followed by three failed same-task distractors, so the
bank is **75% synthetic noise by construction**, and unbounded memory grows to **400 entries by
episode 100**.

Results under that stress (Table 2, T=100, seed 42):

| Policy | Mem | Success | Steps | P@5 |
|---|---|---|---|---|
| TR-CEM-K50 | 50 | 97/100 | 11.61 | 16.6% |
| TR-Linear-K50 | 50 | 96/100 | 12.34 | 15.4% |
| Unbounded | 400 | 95/100 | 12.57 | 12.4% |
| FIFO-K50 | 50 | 94/100 | 12.63 | 3.8% |
| No memory | 0 | 88/100 | 18.35 | 0.0% |

Clean → noisy Precision@5 transition: Unbounded 20.2% → 12.4%; FIFO 15.8% → **3.8%**;
TR-CEM 16.9% → 16.6%; TR-Linear 16.1% → 15.4%.

**The mechanism finding is the transferable part.** Unbounded memory had the *highest* mean
retrieval similarity (0.87) and the *lowest* precision. Pollution manifests as high embedding
similarity to bad entries, not low similarity. FIFO has comparable similarity (0.81) to
TR-CEM but collapses to 3.8% precision, because insertion-order eviction is blind to this.

**Read the paper's honesty too.** On clean ALFWorld at T=100–200 with gpt-5-mini, all bounded
policies fall within overlapping Wilson 95% CIs, and the author states plainly that clean
ALFWorld does not naturally exhibit the pollution retention is designed to address. Random-K50
ties TraceRetain-Linear on seed 43. So: **bounded retention only differentiates from cache
heuristics when the stream is demonstrably noisy.** If your domains are all "clean," a simple
heuristic may be indistinguishable from anything clever.

Scale: ALFWorld, gpt-5-mini, text-embedding-3-large, top-5 retrieval, ~4000 episodes total, no
parameter updates. Single-seed for the T=200, noisy, and eval-seen conditions.

**Confidence: high.**

---

### 4. arXiv 2310.07589 — Goodtriever

*Goodtriever: Adaptive Toxicity Mitigation with Retrieval-augmented Models.*
Pozzobon, Ermiş, Lewis, Hooker. Cohere For AI. EMNLP Findings 2023.

**The one that solves interference by partition rather than by quota.**

Two physically separate datastores: (K⁻, V⁻) from toxic examples, (K⁺, V⁺) from non-toxic.
Combined with the base LM by product-of-experts rather than kNN-LM interpolation:

```
p(w_t|c_t) = softmax(z_t + α(z_t⁺ − z_t⁻))                              (Eq. 5)
p(w_t|c_t) ∝ p_LM(w_t|c_t) · (p⁺_kNN(w_t|c_t) / p⁻_kNN(w_t|c_t))^α      (Eq. 6)
```

with the per-store distribution
`p_kNN(w_t|c_t) ∝ Σ_{(k_i,v_i)∈N} 1[w_t = v_i] · exp(−d(k_i, f(c_t))/T)`  (Eq. 4).

Hyperparameters: α = 2.0 default, T = 100 default, k = 1024 neighbors per store.

**Eviction rule: none. Capacity bound: none. Per-source quota: none.**

**But the continual-learning experiment is directly on point for you.** Section 4: five
sequentially-added toxicity domains from CivilComments-WILDS — Politics, Muslims, Race, LGBTQ,
Christian. The non-toxic datastore is **held fixed at 50K sentences** while the toxic store
grows by appending each new domain.

Final-step EMT per domain (Table 8):

| | Politics | Muslims | Race | LGBTQ | Christians | Overall |
|---|---|---|---|---|---|---|
| GPT-2 large (baseline) | 0.66 | 0.59 | 0.67 | 0.63 | 0.58 | 0.63 |
| **Goodtriever (continual)** | **0.40** | **0.39** | **0.41** | **0.40** | **0.38** | **0.40** |
| DExperts (multitask, upper bound) | 0.34 | 0.39 | 0.40 | 0.39 | 0.34 | 0.37 |
| DExperts (continual finetune) | 0.43 | 0.47 | 0.49 | 0.47 | 0.42 | 0.46 |
| Goodtriever (static, all Jigsaw) | 0.33 | 0.33 | 0.35 | 0.34 | 0.32 | 0.33 |

**Retention after a domain stops arriving:** Politics was domain 1; at the final step it sits at
0.40 against 0.33 for the all-data static upper bound. Degradation of 0.07 EMT after four
subsequent domains arrived. Compare the parametric route: continual-finetuned DExperts sits at
0.43–0.49 and the paper notes its mitigation does not improve as domains are added.

**The finding that matters to you** is in the Figure 8 caption: Goodtriever mitigates each
domain punctually, whereas the multitask fine-tune approach shows entangled results where one
domain impacts others. That entanglement/isolation contrast between a retrieval store and a
parametric model is the cleanest published statement of your intuition — **but it holds
because the store is append-only and unbounded.** Goodtriever does not tell you what happens
when you bound it.

Datastore sizes (Table 5): 41,737,133 non-toxic tokens / 9,378,564 toxic tokens; 1,164,564 and
264,435 comments. Notably, Table 4 shows a *16× smaller* toxic and *40× smaller* non-toxic
auto-labeled store reaching **better** EMT (0.18–0.19 vs 0.22) — capacity is not the binding
constraint in this regime.

**Confidence: high.**

---

### 5. arXiv 2505.00675 — Rethinking Memory in LLM based Agents

**Not verified.** I did not reach this one within the session. Everything I would say about it
would be invention, so I'm saying nothing. Flagged as the one open item on Q3.

---

## Synthesis for your design

| | Bounded? | Evicts? | Per-source? | Isolation mechanism |
|---|---|---|---|---|
| SeMem (2303.01421) | no | never | no | admission threshold δ; growth only |
| CREAM (2601.02708) | no | yes | **structurally** | per-cluster μ + γσ radius |
| TraceRetain (2606.29178) | **yes (K=50)** | yes | no | global learned score |
| Goodtriever (2310.07589) | no | never | no | **physical partition into 2 stores** |
| 2505.00675 | unverified | — | — | — |

Three options that are actually supported by something:

1. **Per-cluster relative-radius pruning** (CREAM). Isolation without labels. My pick.
2. **Physical partition per domain** (Goodtriever). Isolation is total but capacity allocation
   becomes a static decision you have to make up front.
3. **Global learned score with a redundancy term** (TraceRetain). Simplest to bolt on; the
   paper's own evidence says it only beats FIFO when the stream is noisy.

What nobody has published, and what you would be first to report: **the occupancy dynamics of
a bounded shared store under sequential domain arrival.** If you observe an older domain being
driven toward zero occupancy by a newly-streaming one, that is a novel, publishable negative
result, and it is the specific gap in this literature.
