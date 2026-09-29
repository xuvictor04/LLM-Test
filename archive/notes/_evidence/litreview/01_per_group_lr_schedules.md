# Q1 — Independent per-group LR schedules with independent phase

## Answer

**No prior art found** for what you described: per-group schedules with independent wavelength
and independent phase, anchored to each group's own birth, such that at a fixed global step
different experts occupy different points in an exploration/consolidation cycle.

What exists is a spectrum, and every published point on it collapses to *one global clock*:

| Family | Per-group scale? | Per-group shape? | Per-group **phase**? |
|---|---|---|---|
| Layerwise LR decay (Sun et al. 2019) | yes | no | no |
| Discriminative fine-tuning (Howard & Ruder 2018) | yes | no | no |
| LARS / LAMB | yes (from norms) | no | no |
| Per-layer strategies (Everett et al. 2024, arXiv 2407.05872) | yes | no | no |
| LoRA+ (Hayou et al. 2024) | yes (2 groups) | no | no |
| **RLRS (arXiv 2507.03526)** | **yes** | **partially** | **no** |
| Population-based training | across models | across models | n/a — not within-model |

RLRS is the closest thing published and is worth reading closely, because it goes one step
further than you assumed the field had gone — but not the step you care about.

---

## Source: Decoupled Relative Learning Rate Schedules

**Ludziejewski, Małaśnicki, Pióro, Krutul, Ciebiera, Stefaniak, Krajewski, Sankowski, Cygan,
Adamczewski, Jaszczur.** arXiv:2507.03526v1 [cs.LG], 4 Jul 2025. University of Warsaw / IDEAS NCBR.

### What it actually does (Section 2, Eqs. 1–2)

For each component *m*, two scaling factors on a shared cosine curve:

```
η^m_start = η_base × λ^m_start
η^m_end   = η_base × α_end × λ^m_end
```

The base cosine is `η_t = η_end + ½(η_start − η_end)(1 + cos(tπ/T))`.

**Why this is more than "one global schedule times a per-group constant":** because
λ_start ≠ λ_end, each component traces a *differently shaped* curve. A component with
λ_start = 5, λ_end = 0.6 decays steeply; one with λ_start = 0.3, λ_end = 1.125 actually
*rises*. Figure 2 in the paper shows two components' effective LRs crossing. So your framing —
that everything published is a global schedule times a per-group constant — is **not quite
right**, and this paper is the counterexample.

**Why it is still not what you want:**
- Every component shares the same `T` (total steps) and the same cosine argument `tπ/T`.
- Every component is anchored to global step 0. No birth anchoring.
- No periodicity. One monotone half-cosine, no repeated exploration/consolidation cycles.
- Phase offset is identically zero for all components.
- Critically for you: **components are layer *types*, not individual experts.** All 8 experts
  share one λ^Expert pair. There is zero per-expert individuation.

### Verbatim (Section 2)

The paper defines decoupling as <15-word direct quote: they call it
"a separate learning rate schedule for different layer types".

That is the whole scope. Layer types, not instances.

### The tuned MoE values (Table 4) — this is the part that should worry you

| Component | λ_start | λ_end |
|---|---|---|
| Embedding | 5 | 0.6 |
| Unembedding | 0.6 | 0.4 |
| Router | 0.6 | 1 |
| **Experts** | **0.3** | **1.125** |
| Attention | 1 | 1 |

Experts want a *low* LR early and a *high* LR late. The paper's Section 4.1 reasoning: starting
experts at 0.3 aids stability while the router is essentially random, and prevents early expert
specialization — which is what causes the router to freeze prematurely.

**Contradiction with your design:** birth-anchored warmup gives a newborn expert a high LR
immediately. This paper's tuned result says the opposite is what helps, and gives a mechanism
(premature router lock-in). Your setting differs — you have expert *birth* mid-training, they
have all experts present from step 0 — so this isn't a refutation. But it's the only tuned
evidence in the neighbourhood and it points the other way. Worth an ablation.

### Scale and results

Models: Dense34M, MoE8×34M (210M total), Dense113M, MoE8×113M (708M), Dense906M, MoE8×906M
(5.67B). C4 dataset, GPT-2 tokenizer, AdamW, 8 experts top-1, z-loss 0.001, load balance 0.01.

Speedups (Tables 2–3): MoE8×34M **22.8%**, Dense34M 17.2%, Dense113M 19.0%, MoE8×113M 19.0%,
MoE8×113M overtrained 14.6%, Dense906M 8.7%, MoE8×906M 13.6%.

Also relevant: Figure 4 shows the baseline MoE8×906M exhibiting loss spikes that RLRS removes.
So decoupling bought stability, not just speed.

### Confidence

**High** on what the paper does and does not do — I read the full text including the appendix.
**High** that no phase-decoupled work exists in the searched space; **moderate** that none
exists at all, since a negative result over all of ML is not something searches can establish.

---

## Your untried search terms — outcome

| Term | Result |
|---|---|
| "asynchronous learning rate schedules" | Hits are all systems/distributed-training asynchrony (async SGD, staleness), not schedule phase |
| "per-module cyclical learning rate" | Nearest hit is Sequential Bayesian Neural Subnetwork Ensembles (arXiv 2206.00794), which uses cyclic exploration/exploitation LR — but **globally**, one cycle for the whole model, not per module |
| "decoupled schedules mixture of experts" | Lands on RLRS (2507.03526). This is the productive term |
| "birth-anchored warmup" | No hits. Term appears to be yours |

## Adjacent thing worth knowing about

**Sequential Bayesian Neural Subnetwork Ensembles** (arXiv 2206.00794) has the
exploration/consolidation *cycle* structure you want — repeated exploration phases at high LR,
exploitation phases decaying 0.01 → 0.001, with sudden LR restoration after each perturbation
step. It is global, not per-group. But if you need a citable precedent for the *cycle shape*
itself, that's where it lives, and it inherits from SGDR (Loshchilov & Hutter, warm restarts).

**Composition claim you can make:** your contribution is not the cycle (SGDR), and not
per-group decoupling (RLRS). It is *per-instance* decoupling with a *birth-relative time
origin*. Framed that way, it is novel and the novelty is precise.
