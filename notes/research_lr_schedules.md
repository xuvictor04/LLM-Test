# Learning-Rate Schedules: A Reference for Continual-Learning LM Training

Compiled 2026-08-15.

---

## 0. Read this first — web access status and evidence labels

**Web access was PARTIAL.**

- `WebSearch` **worked**. It returns real result titles + URLs plus a search-engine-generated summary of page content.
- `WebFetch` and direct `curl` were **blocked by the network egress proxy** for essentially every paper host:
  `arxiv.org`, `ar5iv.labs.arxiv.org`, `openreview.net`, `semanticscholar.org`, `emergentmind.com`,
  `en.wikipedia.org`, and assorted blogs all returned `EGRESS_BLOCKED` / `CONNECT tunnel failed, response 403`.
  Only `github.com` was reachable for full-text fetch.

**Consequence: I could not read most of the primary papers this session.** Where a claim came from a search-engine
summary of a page I did not read in full, it is labelled as such. Please treat `[S]` claims as "the title, venue and
URL are real and the gist is corroborated, but I did not read the PDF".

### Labels used throughout

| Label | Meaning |
|---|---|
| **`[F]`** | **Fetched** in full this session. Only `github.com/facebookresearch/schedule_free` qualifies. |
| **`[S]`** | **Search-verified**: the paper/page exists at the cited URL and the claim comes from the search engine's summary of that page. Numbers quoted this way are second-hand. |
| **`[M]`** | **Memory only.** Not verified this session. Could be wrong in detail (especially exact hyperparameter values, dates, and author lists). Treat as a lead, not a citation. |
| **`[R]`** | **Repo-derived**: read directly out of this project's own source/comments at `/home/user/LLM-Test/self_organize.py`. Verified, but it is this project's own prior measurement, not published literature. |

---

# PART A — Exhaustive catalogue of learning-rate schedules

Organised by family. "Shape" is the LR as a function of step.

## A.1 Fixed and monotone-decay classics

### Constant learning rate
- **Shape:** flat line. `η(t) = η₀`.
- **Origin:** as old as SGD itself; the Robbins–Monro (1951) conditions say a *constant* rate does **not** converge to
  a stationary point, only to a noise ball around it. `[M]`
- **Good for:** online / never-ending training where there is no "end" to anneal into; debugging; as a baseline.
  It is also the honest default for continual learning, since any schedule that anneals to ~0 cannot learn anything
  that arrives afterwards. `[M]`
- **Weakness:** final loss is worse than any decayed schedule — the decay phase is where a large fraction of the
  loss drop happens in LLM pretraining. `[S]` (this is the central observation motivating WSD; see A.5)

### Step decay / piecewise-constant ("multi-step")
- **Shape:** flat, then drop by a factor γ (typically 10× or 2×) at hand-picked milestones.
- **Origin:** standard practice in the ImageNet CNN era; the canonical instance is ResNet (He et al. 2016), ÷10 at
  epochs 30/60/90. `[M]`
- **Good for:** vision classification, reproducing 2015–2019 baselines. Extremely robust, zero tuning subtlety
  beyond where to put the steps.
- **Weakness:** milestones are a free parameter tied to total budget; the discontinuities cause transient loss
  spikes; almost entirely displaced by cosine/linear in modern work. **Mostly historical.**

### Exponential decay
- **Shape:** `η(t) = η₀ · γ^t` (equivalently `η₀ · exp(−λt)`), a smooth geometric decay.
- **Origin:** classical; `torch.optim.lr_scheduler.ExponentialLR`. `[M]`
- **Good for:** RL and long-horizon training where you want a smooth version of step decay. Also the basis of
  `exp_range` cyclical LR (A.4).
- **Weakness:** never reaches a small value at a controlled *time* — the half-life, not the budget, sets the shape.
  Tends to spend too long at tiny LRs.

### 1/t decay (Robbins–Monro) and polynomial / power decay
- **Shape:** `η(t) = η₀ / (1 + kt)` for 1/t; more generally `η(t) = η₀ · (1 − t/T)^p` (polynomial, `p=1` gives
  linear) or `η₀ · t^(−p)`.
- **Origin:** Robbins & Monro (1951) stochastic approximation; the conditions `Σηₜ = ∞, Σηₜ² < ∞` are satisfied by
  `1/t^p` for `0.5 < p ≤ 1`. `[M]`
- **Good for:** convex/theoretical guarantees; `PolynomialLR` with `p=1` (= linear decay) is the default in many
  segmentation and BERT-family codebases. `[M]`
- **Weakness:** 1/t decays far too fast in practice for deep nets; almost never used raw today.
- **Related, recent:** *Stepsize anything: A unified learning rate schedule for budgeted-iteration training*
  (2025) frames profiles like this as a unified family — https://arxiv.org/html/2505.24452v4 `[S]`

### Inverse-square-root ("Noam", Transformer schedule)
- **Shape:** linear warmup for `w` steps, then `η ∝ 1/√t`. The original formula:
  `lr = d_model^(−0.5) · min(step^(−0.5), step · warmup^(−1.5))`. `[S]`
- **Origin:** Vaswani et al., *Attention Is All You Need* (2017). Named "Noam" after Noam Shazeer in the
  tensor2tensor/AllenNLP implementations. `[S]` — formula confirmed via
  https://docs.allennlp.org/main/api/training/learning_rate_schedulers/noam/ and
  https://github.com/allenai/allennlp/blob/main/allennlp/training/learning_rate_schedulers/noam.py
- **Good for:** budget-agnostic training — you don't have to know `T` in advance, which is why it dominated NMT and
  early Transformer work. Pairs naturally with Adafactor.
- **Weakness:** the `d_model^(−0.5)` coupling makes the peak LR an awkward implicit function of width; it decays too
  slowly at the end, so it loses to cosine/linear at a fixed budget. **Mostly historical for LLM pretraining**, but
  still alive in speech and NMT. See *Transformers without Tears* (Nguyen & Salazar 2019) on warmup + normalization
  interactions — https://arxiv.org/pdf/1910.05895 `[S]`

### Linear warmup (a prefix, not a schedule on its own)
- **Shape:** `η(t) = η_peak · t/w` for `t < w`, then hand off to any decay.
- **Origin:** popularised by Goyal et al. 2017 ("Accurate, Large Minibatch SGD", 5-epoch gradual warmup) `[M]`
  and by the Transformer paper. `[S]`
- **Why it works:** for Adam-family optimizers the second-moment estimate `v` has very large variance in the first
  steps, so the adaptive scaling cannot be trusted; warmup is a variance-reduction device. This is the RAdam
  argument (Liu et al., *On the Variance of the Adaptive Learning Rate and Beyond*,
  https://arxiv.org/abs/1908.03265). `[S]`
- **Quantitatively:** *On the Adequacy of Untuned Warmup for Adaptive Optimization*
  (https://arxiv.org/pdf/1910.04209) argues linear warmup over roughly `2/(1−β₂)` steps is functionally equivalent
  to RAdam across a wide range of settings. `[S]` At `β₂ = 0.95` that is ~40 steps; at `β₂ = 0.999`, ~2000 steps.
  Useful sanity check on any warmup length you pick.
- **Also:** *Analyzing & Reducing the Need for Learning Rate Warmup in GPT Training*
  (https://arxiv.org/pdf/2410.23922) `[S]`

### Linear decay to zero (D2Z) / linear decay to a floor
- **Shape:** straight line from peak down to 0 (or to a floor).
- **Origin:** BERT (Devlin et al. 2019) used linear warmup + linear decay to 0, which made it the NLP default for
  years. `[M]` Revived rigorously by **Bergsma et al., "Straight to Zero: Why Linearly Decaying the Learning Rate
  to Zero Works Best for LLMs", ICLR 2025** (Cerebras) — https://arxiv.org/abs/2502.15938 `[S]`
- **Claimed good for:** *best final loss at compute-optimal token budgets.* The paper reports D2Z beating other
  schedules across model sizes, batch sizes, datasets and vocabularies, with the advantage **growing with dataset
  size**; headline number: a 610M model at 80 tokens-per-parameter with D2Z beats the same model at 200 TPP with a
  10×-decay schedule — ~**60% compute saving**. `[S]` (second-hand; I did not read the PDF)
- **Mechanism claimed:** interpreting AdamW as an EMA of weight updates, linear D2Z optimally trades "get away from
  init early" against "average over more updates late to cancel gradient noise". `[S]`
- **Relevance to you:** this is the strongest single piece of evidence that **decaying to a *small* value matters**,
  and that a 10%-of-peak floor leaves performance on the table. Your 5% floor is closer to D2Z than most.

### ReduceLROnPlateau / step-decay-on-plateau
- **Shape:** hold; when a monitored metric stops improving for `patience` evals, multiply by γ.
- **Origin:** folklore/engineering; ubiquitous in Keras/PyTorch. `[M]`
- **Good for:** training with no known budget and a reliable validation signal. Common in speech, tabular, small-scale.
- **Weakness:** noisy validation makes it fire early or late; not reproducible; essentially unused in LLM
  pretraining. Included as a baseline in the REX comparison. `[S]`

## A.2 Cosine family

### Cosine annealing (to zero or to a floor)
- **Shape:** `η(t) = η_min + (η_peak − η_min)·½(1 + cos(π·t/T))`. Slow at the top, fast in the middle, slow at the
  bottom.
- **Origin:** introduced as the *within-cycle* shape of SGDR — Loshchilov & Hutter, *SGDR: Stochastic Gradient
  Descent with Warm Restarts*, ICLR 2017, https://arxiv.org/pdf/1608.03983 `[S]`. Adopted without restarts as the
  standard LLM schedule.
- **Good for:** best-in-class final loss at a *known* budget; smooth, no discontinuities, one hyperparameter (`T`).
- **Concrete LLM users:**
  - **GPT-3** (2020): cosine to 10% of peak. `[M]`
  - **Chinchilla / Hoffmann et al. 2022:** 10× LR decay with **the cosine cycle length matched to the number of
    training tokens**; the paper explicitly reports that overshooting the cycle length by >25% noticeably degrades
    performance, and that too-long cycles give sub-optimally-trained models. `[S]` —
    https://proceedings.neurips.cc/paper_files/paper/2022/file/c1e2faff6f588870935f114ebe04a3e5-Paper-Conference.pdf
  - **Llama 2**, **Mistral 7B**: cosine. `[S]`
  - **Llama 3 405B**: AdamW, peak LR 8e-5, **8,000-step linear warmup**, cosine decaying to 8e-7 over 1,200,000
    steps (i.e. to 1% of peak). `[S]` — https://arxiv.org/pdf/2407.21783
  - **OLMo 2**: warmup 0→peak over **2,000 steps**, then cosine calibrated to reach **10% of peak** at the max token
    count. `[S]` — https://arxiv.org/pdf/2501.00656
- **Weakness — this is the big one:** *cosine commits you to a token budget up front.* You cannot stop early or
  extend without being off-schedule, and intermediate checkpoints are not "properly annealed" models, which makes
  scaling-law sweeps expensive (one run per budget). This is the explicit motivation for WSD and for Hägele et al.
  `[S]`

### Cosine with warm restarts (SGDR)
- **Shape:** cosine decay over `T₀` steps, then **jump back to the initial LR** and repeat, with the period
  multiplied by `T_mult` each cycle.
- **Origin:** Loshchilov & Hutter, ICLR 2017 — https://arxiv.org/pdf/1608.03983 `[S]`. Note the restart is
  *warm*: the weights are kept, only the LR is reset; the paper is explicit that "the amount of this increase
  controls to which extent previously acquired information (e.g. momentum) is used". `[S]`
- **Claimed good for:** (a) faster anytime performance on CIFAR/ImageNet-scale vision; (b) **snapshot ensembles** —
  the model at the bottom of each cycle is a usable, diverse ensemble member (Huang et al. 2017,
  "Snapshot Ensembles"). `[M]` for the Huang attribution, `[S]` for the fact that SGDR-style
  end-of-cycle checkpoints are used this way.
- **Variants:** implementations commonly add a **restart decay factor** so each restart returns to `γ^k · η₀`
  rather than `η₀` — e.g. `timm`'s SGDR supports a `decay_rate` such that `decay_rate=0.5` halves the peak at each
  restart. `[S]` — https://timm.fast.ai/SGDR. **This is the published precedent for your "decaying envelope".**
- **Status in LLMs:** essentially abandoned. See Part C.2 for the detailed argument and evidence.
- **Skeptical follow-up worth knowing:** *A Closer Look at Deep Learning Heuristics: Learning rate restarts,
  Warmup and Distillation* (https://arxiv.org/pdf/1810.13243) examines whether restarts do what they are claimed to
  do (escape to wider minima) — my recollection is that it finds the "restarts find flatter minima" story does not
  hold up cleanly, but **I did not verify this** `[M]`.

## A.3 Cyclical family (Leslie Smith)

### Cyclical Learning Rates — `triangular`, `triangular2`, `exp_range`
- **Origin:** Leslie N. Smith, *Cyclical Learning Rates for Training Neural Networks* (2015/WACV 2017) —
  https://sands.kaust.edu.sa/classes/CS290E/F19/papers/clr.pdf `[S]`
- **Shape:** LR oscillates linearly between `base_lr` and `max_lr` with a fixed step size, per *batch*, not per epoch.
  - **`triangular`** — constant amplitude, symmetric up/down ramp.
  - **`triangular2`** — the amplitude (`max_lr − base_lr`) is **halved at the end of each cycle**. `[S]`
    This is another direct precedent for a decaying envelope over a cyclic schedule.
  - **`exp_range`** — amplitude scaled by `γ^iteration`, i.e. an exponentially decaying envelope. `[S]`
- **Good for:** removing LR tuning (Smith's argument: cycling through a range means you pass through the good value
  regardless); the associated **LR range test** for finding `max_lr` is still widely used and is arguably the most
  durable contribution.
- **Weakness:** the oscillation makes intermediate checkpoints non-comparable; almost never used at LLM scale.
  **Mostly historical**, but the LR range test survives.

### One-cycle policy / super-convergence
- **Shape:** *one* long cycle: LR ramps up to a very large `max_lr`, ramps back down, then a final tail that goes
  **several orders of magnitude below** the initial LR. Usually paired with an inverse momentum cycle
  (momentum high→low→high).
- **Origin:** Smith & Topin, *Super-Convergence: Very Fast Training of Neural Networks Using Large Learning Rates*
  (2017) — https://arxiv.org/pdf/1708.07120 `[S]`; popularised by fast.ai.
- **Claimed good for:** dramatic wall-clock reductions ("one to several orders of magnitude faster") on
  small/medium vision tasks with limited data; strong regularisation effect from the large-LR phase.
- **Weakness:** the large-LR phase is unstable for Transformers at scale; the claims are strongest on
  CIFAR-scale problems. Not used in LLM pretraining. **Mostly historical / niche**, though `OneCycleLR` remains a
  PyTorch built-in and is a good default for fine-tuning small models.

### Slanted triangular learning rates (STLR)
- **Shape:** a short sharp linear increase to a peak, then a long linear decay — i.e. an asymmetric triangle.
- **Origin:** Howard & Ruder, *ULMFiT* (2018). `[S]` —
  see https://slds-lmu.github.io/seminar_nlp_ss20/transfer-learning-for-nlp-i.html
- **Good for:** fine-tuning. Rationale given: converge quickly to a suitable region, then refine. `[S]`
- **Status:** superseded in practice by warmup + linear/cosine decay, which is the same shape with different
  parameterisation. **Historical.**

## A.4 Trapezoidal / constant-with-cooldown family (the modern challenger)

### Warmup-Stable-Decay (WSD) / trapezoidal / "constant + cooldown"
- **Shape:** linear warmup → **long constant plateau at peak** → short rapid decay over the final ~10–20% of steps.
- **Origin:** **MiniCPM** (Hu et al. 2024) named and popularised WSD; the "constant + cooldown" framing and the
  scaling-law analysis is **Hägele et al., "Scaling Laws and Compute-Optimal Training Beyond Fixed Training
  Durations", NeurIPS 2024** (EPFL/HuggingFace) — https://arxiv.org/abs/2405.18392 `[S]`
- **Typical config:** constant until ~90% of training, then decay over the last 10%. `[S]`
- **Why it is winning:**
  1. **No pre-committed budget.** You can train arbitrarily long at the plateau and decide *later* where to
     cooldown. `[S]` This is the single most-cited advantage over cosine.
  2. **Cheap scaling laws.** One long run + several short cooldown branches replaces N independent cosine runs;
     Hägele et al. report scaling experiments at significantly reduced GPU hours. `[S]`
  3. **Matches cosine's final loss.** Reported as scaling "predictably and reliably similar to cosine". `[S]`
  4. **Weight averaging is a free extra.** Stochastic weight averaging along the plateau improves performance along
     the trajectory at no extra training cost. `[S]`
- **Concrete users:** **MiniCPM**, **DeepSeek-V2**, **DeepSeek-V3**, **ERNIE 4.5**, and (per one source)
  **Llama-3.1**. `[S]` — I would independently double-check the Llama-3.1 claim; the Llama 3 paper text I saw
  describes a cosine schedule for the 405B run `[S]`, so the two search summaries are in tension. **Flagged as
  unresolved.**
- **Theory:** *Understanding Warmup-Stable-Decay Learning Rates: A River Valley Loss Landscape Perspective*
  (https://arxiv.org/html/2410.05192v1) `[S]` — the plateau travels fast along a "river" (a flat valley floor),
  and the cooldown drops the model down the valley walls, which is where the visible loss drop comes from.
- **Cooldown-phase dynamics:** *Training Dynamics of the Cooldown Stage in Warmup-Stable-Decay*
  (https://arxiv.org/pdf/2508.01483) `[S]`
- **Directly relevant to you:** **WSD-S** is a WSD variant explicitly aimed at *continual* training — it reuses the
  checkpoint before the decay and does repeated short decays. `[S]` I have the name and purpose verified but not
  the details; worth chasing.

### Infinite learning rate schedules (continual-pretraining variant of WSD)
- **Shape:** warmup → decay to a **non-zero constant** → hold there indefinitely → optionally a final anneal
  whenever you want a deployable checkpoint.
- **Origin:** *Beyond Cosine Decay: On the effectiveness of Infinite Learning Rate Schedule for Continual
  Pre-training* — https://arxiv.org/html/2503.02844v2 `[S]`
- **Claimed good for:** **exactly your setting.** The pitch is that these schedules "circumvent the pathologies of
  re-warming" — i.e. you never have to jump the LR back up when new data arrives, because you never annealed to
  zero in the first place. `[S]`
- **This is the schedule family I would point at hardest for a continual-learning LM.** See Part C.

### WSM (decay-free via checkpoint merging)
- **Shape:** no decay phase at all; instead merge checkpoints from the plateau to *simulate* the decay.
- **Origin:** *WSM: Decay-Free Learning Rate Schedule via Checkpoint Merging for LLM Pre-training* (2025) —
  https://arxiv.org/pdf/2507.17634 `[S]`
- **Claim:** establishes a formal connection between LR decay and checkpoint merging; the merge substitutes for the
  cooldown. Relates to the SWA result in Hägele et al. `[S]`

### Power Scheduler
- **Shape:** a power-law schedule whose parameters are argued to be **independent of batch size and token count**.
- **Origin:** *Power Scheduler: A Batch Size and Token Number Agnostic Learning Rate Scheduler* (IBM, 2024) —
  https://arxiv.org/pdf/2408.13359 `[S]`
- **Good for:** transferring a tuned LR across batch sizes and budgets (complements µP, which transfers across
  *width*).

### Knee / elbow schedule (explore–exploit)
- **Shape:** constant high LR for a minimum "explore" duration, then a **parameter-less linear decay to zero**
  ("exploit"). Functionally a trapezoid with a long decay leg.
- **Origin:** Iyer, Thejas, Kwatra, Ramjee, Sivathanu — *Wide-minima Density Hypothesis and the Explore-Exploit
  Learning Rate Schedule*, **JMLR 24 (2023)** — https://www.jmlr.org/papers/v24/21-0549.html `[S]`
- **Hypothesis:** wide minima are *rarer* than narrow ones, so you must spend a minimum time at high LR to find one,
  after which you descend into it.
- **Reported gains:** up to **+0.84% absolute accuracy** at the same budget, or up to **57% reduced training time**
  to match the original accuracy, across image and NLP datasets. `[S]`
- **Note:** this is essentially WSD, published earlier, with a theoretical justification and a longer decay leg. If
  you cite WSD you should probably cite this too.

### REX (Reflected EXponential)
- **Shape:** a profile that stays high longer than cosine and then drops faster — "reflected exponential" —
  combined with a choice of *sampling rate* (how often the LR is actually updated from the profile).
- **Origin:** John Chen, Cameron Wolfe et al., *REX: Revisiting Budgeted Training with an Improved Schedule*,
  **MLSys 2022** — https://arxiv.org/abs/2107.04197,
  https://proceedings.mlsys.org/paper_files/paper/2022/file/77cdf4ffbd2afd02541e02533ec56820-Paper.pdf `[S]`
- **Claimed good for:** **budgeted training** — when you have fewer steps than you'd like. REX beats linear in the
  low-budget regime and matches/exceeds linear, step, exponential, cosine, plateau-decay and OneCycle in both high
  and low budget regimes, **with no extra compute, storage, or hyperparameters**. `[S]`
- **Key framing worth stealing:** schedule = (continuous *profile*) × (*sampling rate*). Most schedules only vary
  the profile.

## A.5 Layer-wise, group-wise, and structural LR assignment

### Discriminative fine-tuning / layer-wise LR decay (LLRD)
- **Shape:** LR is per-layer, `η_l = η · ξ^(L−l)` with `ξ ≈ 0.65–0.95`; earlier layers get smaller rates.
- **Origin:** Howard & Ruder, ULMFiT (2018) `[S]`; carried into BERT fine-tuning practice and into ELECTRA/DeBERTa
  recipes. `[M]`
- **Rationale:** early layers hold general features needing little adaptation; later layers are task-specific. `[S]`
- **Good for:** **fine-tuning**, especially with small target datasets — it is a plasticity/stability knob.
- **Related:** **gradual unfreezing** (unfreeze one layer at a time from the top) — same paper. `[S]`
- **Status:** still standard for encoder fine-tuning and for vision-transformer fine-tuning (BEiT/MAE recipes use
  LLRD). Rare in pretraining.

### Per-parameter-group LRs in pretraining
- Common practice, but not usually called a "schedule": embeddings vs. body vs. output head often get different
  rates or different weight decay; µP (below) formalises this. `[M]`

### µP / µTransfer (maximal-update parameterisation)
- **Shape:** not a time schedule — a **width-dependent rescaling** of per-tensor LRs so that the optimal LR is
  invariant to model width, letting you tune LR on a small proxy model and transfer it.
- **Origin:** Yang, Hu et al., *Tensor Programs V / µTransfer* (2022). `[M]` — not verified this session.
- **Good for:** avoiding LR sweeps at scale. Used by Cerebras, and the "Straight to Zero" work is from the same
  group, which is why they can talk about "the optimal peak LR" so confidently. `[M]`

### LARS (Layer-wise Adaptive Rate Scaling)
- **Shape:** per-layer LR set so the update magnitude is proportional to the **weight norm** of that layer:
  `η_l ∝ ||w_l|| / ||∇w_l||`, on top of a global schedule.
- **Origin:** You, Gitman, Ginsburg, *Large Batch Training of Convolutional Networks* (2017) —
  https://arxiv.org/pdf/1708.03888 `[S]`
- **Good for:** **very large batch** SGD training. Enabled AlexNet and ResNet-50 at batch size **16K**. `[S]`
- **Status:** still the standard for large-batch SSL (SimCLR/BYOL) and MLPerf ResNet.

### LAMB (Layer-wise Adaptive Moments for Batch training)
- **Shape:** Adam's per-dimension second-moment normalisation **plus** LARS-style per-layer trust-ratio normalisation.
- **Origin:** You et al., *Large Batch Optimization for Deep Learning: Training BERT in 76 Minutes* —
  https://arxiv.org/pdf/1904.00962 `[S]`
- **Good for:** large-batch Transformer pretraining. Scaled BERT pretraining to batch **64K**, cutting training from
  ~3 days to **~76 minutes**, without accuracy loss. `[S]`
- **Status:** partly historical — modern LLM pretraining mostly uses plain AdamW with a warmup and a global
  schedule, plus gradient clipping, rather than LAMB. `[M]`

## A.6 Adaptive optimizers where the "schedule" is implicit

These are not schedules, but they change what a schedule needs to do. Included because they interact.

- **AdaGrad** (Duchi et al. 2011): per-coordinate `η/√(Σg²)`. Monotonically decaying effective rate — an *automatic*
  1/√t-ish decay per coordinate. Decays too aggressively for deep nets. `[M]`
- **RMSProp** (Tieleman & Hinton 2012): EMA of `g²` instead of a sum, removing the monotone decay. `[M]`
- **Adam / AdamW** (Kingma & Ba 2015; Loshchilov & Hutter 2019 — https://arxiv.org/pdf/1711.05101 `[S]`):
  per-coordinate normalisation by `√v̂`, plus bias correction that acts like a *built-in* short warmup. AdamW's
  contribution is decoupling weight decay from the LR — relevant to you, because under coupled L2 a decaying LR also
  decays your regularisation, whereas under AdamW it does not. `[S]` for the AdamW paper's existence/URL; `[M]` for
  the mechanism description.
  - Useful mental model from "Straight to Zero": AdamW's iterate is approximately an **EMA of unit-norm updates**
    with timescale set by `η`, which is why annealing `η` ≈ averaging over more updates. `[S]`
- **Adafactor** (Shazeer & Stern 2018): factored second moments (sublinear memory) **and its own default relative
  step size that decays as `1/√t`**, plus update clipping. i.e. Adafactor ships with an inverse-sqrt schedule baked
  in unless you override it with an external LR. `[M]` — the search result explicitly noted it did *not* confirm
  Adafactor's decay for me, so treat the `1/√t` detail as memory.
- **RAdam** (Liu et al. 2020, https://arxiv.org/abs/1908.03265): rectifies the variance of the adaptive rate,
  *replacing* the need for warmup. `[S]`
- **Lion, Sophia, Muon, Shampoo/SOAP**: newer optimizers with different effective step geometry; all still use an
  external warmup + decay schedule in practice. `[M]`

## A.7 Parameter-free / schedule-free methods

### D-Adaptation
- **Idea:** estimate the distance to the solution `D` online, and set the step size from it — no LR to tune.
- **Origin:** Defazio & Mishchenko, *Learning-Rate-Free Learning by D-Adaptation* (ICML 2023 best paper) —
  https://arxiv.org/pdf/2301.07733 `[S]`

### Prodigy
- **Idea:** an improved `D` estimator; provably converges faster than D-Adaptation by a factor
  `O(√log(D/d₀))`. `[S]`
- **Origin:** Mishchenko & Defazio, *Prodigy: An Expeditiously Adaptive Parameter-Free Learner*, **ICML 2024** —
  https://proceedings.mlr.press/v235/mishchenko24a.html, https://arxiv.org/abs/2306.06101 `[S]`
- **Evidence:** tested on logistic regression, VGG11/ResNet-50 on CIFAR10, ViT on ImageNet, LSTM on IWSLT14, DLRM
  on Criteo, VarNet on knee MRI, and **RoBERTa/GPT training on BookWiki**; consistently beats D-Adaptation and
  reaches test accuracy close to hand-tuned Adam. `[S]`
- **Caveat:** "close to hand-tuned Adam" is the honest summary — parameter-free methods buy you tuning time, not a
  better optimum. Widely adopted in the diffusion/LoRA fine-tuning community. `[M]`
- **Related:** **DoG / DoWG** (Ivgi et al.), **Mechanic** (Cutkosky et al.) — same genre. `[M]`

### Schedule-Free SGD / AdamW (Defazio et al.)
- **Idea:** eliminate the schedule entirely. Replace momentum with **a combination of interpolation and averaging**,
  maintaining three parameter sequences, where **evaluation happens at a different point than gradient
  computation** (`y` for gradients, `x` = an average for evaluation, `z` the base sequence). Theory unifies
  scheduling with iterate averaging. `[F]` (README) + `[S]` (paper)
- **Origin:** Defazio, Yang, Mehta, Mishchenko, Khaled, Cutkosky, *The Road Less Scheduled*, **NeurIPS 2024** —
  https://arxiv.org/abs/2405.15682, code https://github.com/facebookresearch/schedule_free `[S]`/`[F]`
- **Claim:** SOTA versus schedules across convex problems through large-scale deep learning, with **no extra
  hyperparameters** over momentum SGD/AdamW. Core algorithm behind a winning entry to the **MLCommons 2024 AlgoPerf
  self-tuning track**. `[S]`
- **Practical caveats — read these, they are from the README I actually fetched `[F]`:**
  - Training is **"more sensitive to the choice of β than you may expect"**; default `β=0.9`, but **0.95–0.98 is
    recommended for long runs**.
  - Schedule-Free SGD wants LRs **10–50× larger** than classical SGD; Schedule-Free AdamW wants **1–10× larger**.
  - **Warmup is still recommended** (`warmup_steps` parameter) for stability. So it is "schedule-free" in the decay
    sense, not the warmup sense.
  - You must call `.train()` / `.eval()` at the right points to swap the evaluated iterate; **BatchNorm needs
    special handling**; FP16 caches and GradScalers may need manual updates.
  - "**Won't necessarily outperform a schedule approach without also tuning regularization and learning rate
    parameters.**" — the authors' own words.
- **Relevance to you:** genuinely attractive for continual learning, because there is no horizon to commit to.
  The `β` sensitivity and the eval-mode bookkeeping are the practical costs.

## A.8 Meta-learned, searched, and online-adapted LRs

### Hypergradient descent
- **Idea:** differentiate the objective w.r.t. the learning rate itself and do gradient descent on the LR online.
  Costs one extra copy of the gradient in memory and essentially no extra compute.
- **Origin:** Baydin, Cornish, Rubio, Schmidt, Wood, *Online Learning Rate Adaptation with Hypergradient Descent*,
  **ICLR 2018** — https://arxiv.org/abs/1703.04782, https://gbaydin.github.io/assets/pdf/baydin-2018-hypergradient.pdf,
  code https://github.com/gbaydin/hypergradient-descent `[S]`
- **Claim:** improves SGD, SGD+Nesterov, and Adam across a range of problems; reduces sensitivity to the initial LR.
  `[S]`
- **Weakness:** greedy/myopic (one-step lookahead), so it tends to keep LR too high; introduces a hyper-LR you now
  have to pick. `[M]`
- **Follow-up:** *Provable and practical online learning rate adaptation with hypergradient descent*, ICML 2025 —
  https://dl.acm.org/doi/10.5555/3780338.3780752 `[S]`

### Population-Based Training (PBT)
- **Idea:** train a population of models in parallel; periodically **exploit** (copy weights from better members)
  and **explore** (perturb hyperparameters, notably the LR). The result is a *learned, non-parametric LR schedule*
  discovered online.
- **Origin:** Jaderberg et al., DeepMind, *Population Based Training of Neural Networks* (2017). `[M]` — not
  verified this session.
- **Good for:** RL and GAN training where the best LR genuinely changes over training and there is no analytic
  schedule. Used in AlphaStar and in DeepMind RL work. `[M]`
- **Weakness:** N× compute; the discovered schedules are often jagged and not transferable.
- **Note for you:** PBT is the closest published analogue to "a population of learners each with its own LR",
  which is one framing of your per-expert idea — but PBT *selects* over LRs by fitness, it does not clock them
  from birth.

### AutoLRS
- **Idea:** Bayesian optimisation on the fly to choose the LR for the next interval by short trial runs.
- **Origin:** *AutoLRS: Automatic Learning-Rate Schedule by Bayesian Optimization on the Fly* —
  https://arxiv.org/pdf/2105.10762 `[S]`

### Learned optimizers (L2O)
- **Idea:** meta-learn the whole update rule (VeLO, Metz et al.), which subsumes the schedule.
- **Status:** impressive demos, poor generalisation to new scales; not used in production LLM training. `[M]`

### Other automatic-tuning work
- *Revisiting Learning Rate Control* (2025) — https://arxiv.org/pdf/2507.01724 `[S]`
- *A Simple Dynamic Learning Rate Tuning Algorithm For Automated Training of DNNs* —
  https://arxiv.org/pdf/1910.11605 `[S]`
- *Gradient descent with generalized Newton's method* — https://arxiv.org/pdf/2407.02772 `[S]`
- *Online hyperparameter optimization by real-time recurrent learning* — https://arxiv.org/pdf/2102.07813 `[S]`

## A.9 Other things that occupy the same design slot

### "Don't decay the LR, increase the batch size"
- Smith, Kindermans, Ying, Le (ICLR 2018). Increasing batch size has the same effect on the SGD noise scale as
  decaying the LR, and parallelises better. `[M]` — not verified this session. Worth knowing because it means
  **batch-size ramps are a schedule in disguise**, and several LLM recipes (GPT-3, Llama 3) ramp batch size
  during training, which partially confounds LR-schedule comparisons. `[M]`

### Weight averaging as a substitute for decay
- **SWA** (Izmailov et al. 2018) `[M]`; **EMA of weights**; **LAWA** (latest weight averaging); and the
  Hägele et al. result that SWA along a constant-LR plateau improves the trajectory for free `[S]`; and **WSM**,
  which formalises merging as a stand-in for decay `[S]`. Relevant to you: **if you want the benefit of an anneal
  without actually annealing (which continual learning cannot afford), weight averaging is the published way to
  get it.**

### Multi-Power Law / loss-curve prediction across schedules
- *A Multi-Power Law for Loss Curve Prediction Across Learning Rate Schedules* —
  https://arxiv.org/pdf/2503.12811 `[S]`. Predicts the loss curve for an arbitrary schedule, and can therefore be
  used to *optimise* the schedule directly. Genuinely useful if you want to compare candidate schedules without
  running them.

### Anytime / horizon-free schedules
- *Anytime Pretraining: Horizon-Free Learning-Rate Schedules with Weight Averaging* —
  https://arxiv.org/pdf/2602.03702 `[S]`
- *WSqD: A Horizon-Free Learning Rate Schedule for Large Model Training* — https://arxiv.org/pdf/2607.10959 `[S]`
- These are the newest generation of the "don't commit to a budget" line. Both post-date my reliable knowledge;
  I have only the titles/URLs from search.

### Curriculum-coupled and data-dependent schedules
- Not really LR schedules, but they occupy the same slot: sequence-length ramps, batch-size ramps, replay ratios,
  and data-mixture annealing (OLMo's "micro-anneal" / mid-training on high-quality data during the cooldown).
  In modern practice **the LR cooldown and the data-mixture change are done together**, which is a confound to be
  aware of when reading claims about cooldowns. `[M]`

---

# PART B — What is actually used now, ranked

## B.1 The ranking

**Tier 1 — dominant in modern LLM pretraining**

1. **Linear warmup → cosine decay to a small floor (5–10% of peak, sometimes 1%).**
   Still the single most common recipe. Concrete: GPT-3 (10% floor) `[M]`; Chinchilla (10× decay, cycle matched to
   tokens) `[S]`; Llama 2 `[S]`; Mistral 7B `[S]`; **Llama 3 405B** (8e-5 peak, 8k warmup, → 8e-7 over 1.2M steps)
   `[S]`; **OLMo 2** (2k warmup, cosine to 10% of peak) `[S]`.
   **Why:** best-understood, best-validated final loss at a known budget; one hyperparameter; smooth.
   **Why it's losing ground:** commits to a token budget; intermediate checkpoints aren't annealed; every scaling-law
   point needs its own run.

2. **Warmup–Stable–Decay / trapezoid / constant + cooldown.**
   Concrete: MiniCPM, DeepSeek-V2, **DeepSeek-V3**, ERNIE 4.5 `[S]`.
   **Why:** budget-agnostic, cheap scaling laws, matches cosine's loss, cooldown branches let you ship a model at
   any point, and the cooldown is a natural place to switch to a high-quality data mixture.
   This is the schedule with the most momentum right now, and the most relevant one for continual learning.

3. **Linear warmup → linear decay (to zero or a floor).**
   The BERT-era default `[M]`, revalidated as **the best choice at compute-optimal budgets** by Bergsma et al.,
   ICLR 2025 `[S]`. Used across most fine-tuning and instruction-tuning code (HF `get_linear_schedule_with_warmup`
   is probably the most-executed LR schedule in existence).

**Tier 2 — active, credible, but niche or newer**

4. **Infinite / horizon-free LR schedules** (constant tail, optional anneal on demand) — the continual-pretraining
   specialisation of WSD `[S]`.
5. **Schedule-Free AdamW** — real, competitive, AlgoPerf-winning, with real caveats `[S]`/`[F]`. Adoption is
   growing but it is not yet a frontier-lab default as far as I know `[M]`.
6. **Prodigy / D-Adaptation** — heavily used in the LoRA / diffusion fine-tuning community; rare in pretraining `[M]`.
7. **LARS / LAMB** — still standard for large-batch self-supervised vision and MLPerf `[S]`.
8. **Layer-wise LR decay (LLRD)** — still standard for encoder and ViT fine-tuning `[M]`.
9. **One-cycle** — a good default for small-model fine-tuning, kept alive by fast.ai and `torch.optim.OneCycleLR`.
10. **REX, Knee/explore-exploit, Power Scheduler** — well-motivated, cited, but not widely adopted as defaults `[S]`.

**Tier 3 — mostly historical**

11. **Inverse-sqrt / Noam** — the Transformer/NMT default 2017–2020; still used in speech and NMT, gone from LLM
    pretraining `[S]`/`[M]`.
12. **Step decay** — the CNN-era default; robust, but nobody chooses it for new work `[M]`.
13. **Cyclical LR (`triangular` / `triangular2` / `exp_range`)** — the *LR range test* survived, the cycling did
    not `[S]`/`[M]`.
14. **Cosine warm restarts (SGDR)** — see below. **Historical for LLMs.**
15. **Exponential decay, 1/t decay, ReduceLROnPlateau** — legacy defaults, still fine outside LLMs `[M]`.
16. **Hypergradient descent, PBT-for-LR, AutoLRS, learned optimizers** — research directions, not production
    practice for LLM pretraining `[M]`.

## B.2 The specific status of warm restarts

One of my searches returned this summary directly: *"cyclical learning rate schedules like SGDR (periodic warm
restarts mid-training) represent a pre-LLM research direction that is mostly historical. In modern LLM pretraining,
AdamW with cosine decay is the most popular optimizer and learning rate scheduler."* `[S]`

The same search also found **no paper directly demonstrating that SGDR is harmful for LLM pretraining** — the
honest statement is **"abandoned, not refuted"**. Part C.2 assembles the indirect evidence, which is substantial.

## B.3 The one structural fact behind the whole ranking

Every Tier-1 schedule has the same three-part anatomy: **(warmup) → (long phase at high LR) → (anneal to something
small)**. Cosine, WSD, linear-D2Z, knee, and REX differ only in how they distribute time between the middle and the
end. The *anneal* is not decoration — it is where a large share of the final loss improvement appears (the "river
valley" account `[S]`, the AdamW-as-EMA account `[S]`, and the wide-minima account `[S]` are three different
explanations of the same empirical fact). **Anything that discards the anneal discards its benefit.** Hold that
thought for Part C.

---

# PART C — Directly relevant to this project

Project configuration as described, and as confirmed in
`/home/user/LLM-Test/self_organize.py` `[R]`:

- `LR=2e-3`, `LR_SCHED=cosine`, `LR_WARMUP=1000`, `LR_MIN_FRAC=0.05`, AdamW (`_lr_at`, lines ~3542–3605)
- `LR_RESTARTS=1` (default **on**), wavelength `LR_EPOCHS=8` epochs, cycles fitted to a whole number over the run
- `LR_DECAY` envelope (default 0.0 = off), lines ~3587–3604
- `FAB_LR_OWN` / `FAB_LR_MAXR=4.0` / `FAB_LR_BOOST`, per-expert rates clocked from birth, lines ~5100–5156

## C.1 AdamW, peak 2e-3, 1000-step linear warmup, cosine to 5% of peak

**Verdict: this is a mainstream, defensible configuration. The two things I'd interrogate are the peak and the floor.**

**Warmup length.** 1000 steps is squarely in the normal band — OLMo 2 uses 2,000 `[S]`, Llama 3 405B uses 8,000
`[S]`. The theoretical target is roughly `2/(1−β₂)` steps `[S]`: at PyTorch's default `β₂=0.999` that is ~2000, so
1000 is *slightly short* by that rule but the same order. If you ever see early instability, the cheap fix is
`β₂=0.95` (which makes 1000 steps generously long) rather than a longer warmup.
Note the guard already in the code: warmup is clamped to `total//10` so short runs don't spend their whole life in
warmup `[R]` — good, and a real bug class.

**Peak LR of 2e-3.** This is **high in absolute terms** for a Transformer — Llama 3 405B used 8e-5 `[S]`. But peak
LR scales down with model width, and small models legitimately train at 1e-3–3e-3. If your model is small
(hundreds of M params or less) 2e-3 is normal `[M]`. The thing worth knowing: **the "Straight to Zero" result is
explicitly conditioned on the peak LR being optimal** — "under an optimal peak learning rate, D2Z consistently
outperforms" `[S]`. Schedule comparisons at a mis-set peak are not informative. If you have not done an LR sweep at
the current width, that is a higher-value experiment than any schedule change.

**Floor at 5% of peak.** This is *better* than the common 10% and worse than decay-to-zero. The literature is
unusually clear here: Bergsma et al. find linear decay **to zero** beats 10×-decay so decisively that 80 TPP with
D2Z beat 200 TPP with 10× decay `[S]`. Chinchilla used 10× decay `[S]`; OLMo 2 uses 10% `[S]`; Llama 3 goes to 1%
`[S]`. So the trend in frontier practice is toward *lower* floors.

**But your floor is deliberate and I think correct for this project.** The code comment says it outright: *"this is
a continual-learning system and a schedule that anneals to nothing cannot learn anything that arrives late"* `[R]`.
That is exactly the tension the "infinite LR schedule" line of work exists to resolve `[S]`. The published
resolution is **not** "keep a 5% floor forever" but rather:
- hold at a **non-zero constant** (your floor is a fine choice of constant), and
- **anneal only when you want a deployable checkpoint**, from a branch, discarding the annealed weights afterward
  and continuing from the pre-anneal state. This is the WSD-S / cooldown-branch pattern `[S]`.

**Known failure modes for this configuration:**
1. **Horizon mis-specification.** Chinchilla: overshooting the cosine cycle length by >25% noticeably degrades
   performance `[S]`. Your code already fights this — `LR_EPOCHS` decouples the wavelength from `EPOCHS`, with a
   comment recording that stretching the cosine over a projected end that the run never reached meant the LR floor
   was never touched (`cosine reached p=0.760, LR floor never touched`) `[R]`. Good. Keep the monotone clamp on
   the projection; a schedule that steps back *up* mid-run is worse than one that is merely wrong `[R]`.
2. **Loss spikes** from too-high a peak / too-short a warmup — the standard diagnosis is "peak too high, warmup too
   short, or a peak that was tolerable at small batch but not at production batch size" `[S]`.
   See *Spike No More: Stabilizing the Pre-training of Large Language Models*,
   https://arxiv.org/pdf/2312.16903 `[S]`.
3. **Weight decay coupling.** AdamW decouples WD from LR `[S]`, so as the LR decays 20× the *relative* strength of
   weight decay rises 20×. Usually benign, occasionally not — worth being aware of if late-training behaviour looks
   over-regularised.

## C.2 Optional cosine warm restarts that return to 100% of peak

**Direct answer to the question asked: yes — returning to full peak late in training is expected to be harmful, and
this is well-supported *indirectly*, though I found no paper that runs exactly this ablation on an LLM.**

Here is the evidence, strongest first.

**(a) The continual-pretraining re-warming literature is the closest direct evidence, and it is damning for full-peak
jumps.**

*Continual Pre-Training of Large Language Models: How to (re)warm your model?* (Gupta, Ibrahim et al., 2023) —
https://arxiv.org/pdf/2308.04014, TMLR version https://openreview.net/pdf?id=DimPeeCxKO `[S]`. Findings as
summarised by search:
- **"LR re-warming causes unwanted forgetting"**, and *"rewarming the learning rate appears to be a significant
  cause of the increase in loss seen when starting to continue to pre-train, as evidenced by the increase in
  perplexity when re-warming the learning rate **while training on the same distribution**."* `[S]`
  That last clause is the key one: **the loss increase is caused by the LR jump itself, not by the data change.**
  A warm restart inside a single run is precisely "re-warming on the same distribution".
- **"Higher values of maximum learning rate lead to more forgetting and more adaptation while the opposite is true
  for lower values… the higher the re-warming, the more pronounced this effect is."** `[S]`
  A restart to **100%** of peak is the maximum-forgetting end of that curve.
- The exact length of the re-warmup matters much less than the peak you re-warm *to*. `[S]`

*Simple and Scalable Strategies to Continually Pre-train LLMs* (Ibrahim et al., 2024) —
https://arxiv.org/abs/2403.08763 `[S]` — shows re-warming + re-decaying + **replay** matches full retraining. Note
the third ingredient: re-warming is only safe *when paired with replay of old data*. A bare restart with no replay
is the configuration the literature warns about.

*Beyond Cosine Decay: Infinite Learning Rate Schedules for Continual Pre-training* —
https://arxiv.org/html/2503.02844v2 `[S]` — proposes infinite LR schedules explicitly to **"circumvent the
pathologies of re-warming."** The word "pathologies" is the field's summary judgement on LR jumps.

**(b) The anneal is load-bearing, so throwing it away costs you.**
Every account of why the decay phase works — river-valley `[S]`, AdamW-as-EMA-of-updates `[S]`, wide-minima
`[S]` — implies that raising the LR back to peak *undoes* the consolidation. The AdamW-as-EMA framing makes this
sharpest: annealing works because it averages over more updates to cancel gradient noise `[S]`; jumping the LR back
up shortens the averaging window and re-injects the noise you just spent the cycle averaging out.

**(c) Warm-starting is a known plasticity/generalisation hazard.**
Ash & Adams, *On the Difficulty of Warm-Starting Neural Network Training* (2020) `[S]`, and the follow-up DASH
(NeurIPS 2024, https://arxiv.org/html/2410.23495v2) `[S]`: warm-starting *"often leads to loss of plasticity …
resulting in worse generalization than training from scratch … even under stationary data distributions."*
This cuts *both ways* for you: it is an argument that a high-LR phase can be restorative (the usual motivation for
restarts), and simultaneously evidence that shaking a converged model is not free.

**(d) SGDR's own framing does not support late full-peak restarts.**
SGDR uses `T_mult > 1` so cycles get *longer*, meaning late cycles have long anneals; and the standard
implementations offer a **restart decay factor** so peaks come down over time (`timm`: `decay_rate=0.5` halves the
peak each restart) `[S]`. The `triangular2` and `exp_range` CLR policies do the same thing `[S]`. **The published
cyclic schedules that people actually use mostly do not return to full peak repeatedly.** Constant-amplitude
`triangular` is the exception and it is the least used of the three.

**(e) Your own measurement already says this.** From the code comments `[R]`:
> *"The repeating cosine returns to 100% OF PEAK at every restart, forever. Measured on an 18-epoch run:
> `[lr @ 201925] cosine restart: 1.00e-04 -> 2.00e-03 (100% of peak)` and the held-out curve after it swings
> 1.5 b/B and never resettles (3.82 3.29 3.04 4.01 3.39 4.04 4.08 … 3.92 3.19 2.58 3.85 3.63). Two of three seeds
> ended with a base model at 5.6 and 5.3; the one that landed away from a restart read 3.0. That is the entire
> spread of the arm."*

This is a textbook instance of the failure mode the re-warming literature describes, and the fact that the seed
which *"landed away from a restart"* was the good one is the tell: **final quality is being determined by where
the run happens to stop relative to the restart phase.** That is a schedule that makes your results
non-comparable, independent of whether the restarts help on average.

**One more failure mode specific to your implementation.** The code notes the restart is *"5% -> 100%, a 20x jump,
with no per-cycle warmup by design"* `[R]`, on the reasoning that warmup exists for cold optimizer state, which is
only cold once. That reasoning is **half right and worth revisiting**. Warmup's purpose is to let Adam's
second-moment estimate `v` become trustworthy `[S]`. After an anneal to 5% of peak, `v` is an EMA calibrated to
*small* gradients in a *converged* region. Jumping to 20× the step size in one step means the first few post-restart
updates are sized by a stale `v` under a much larger `η` — the same variance pathology warmup was invented to
prevent, arriving at the worst possible moment. **If you keep restarts at all, give each cycle a short warmup
(a few hundred steps).** It is cheap insurance and I would expect it to remove a good part of that 1.5 b/B swing.

**Where restarts genuinely do help, for balance:** anytime/snapshot use (a usable model at the bottom of every
cycle) `[S]`, and populations that need a diversity source. Neither is the same as "better final loss".

## C.3 The newly added decaying envelope

**Verdict: this is the right correction, it has direct published precedent, and the main thing to check is that the
envelope reaches a genuinely low value by the end.**

**Precedent.** Decaying the peak of successive cycles is not novel — it is:
- CLR **`triangular2`**: amplitude halved at the end of each cycle `[S]`;
- CLR **`exp_range`**: amplitude scaled by `γ^iteration` — an exponentially decaying envelope `[S]`;
- SGDR implementations with a **restart `decay_rate`** `[S]`.
Your version — envelope = a cosine over *global* run progress, multiplying a cosine over *cycle* progress — is a
cleaner parameterisation than any of those (it guarantees the run ends annealed), but it is the same idea. **You can
cite `triangular2` and `timm`'s SGDR `decay_rate` as prior art.** `[S]`

**Why it addresses the actual problem.** The re-warming literature's finding is not "never raise the LR", it is
**"the *maximum* you re-warm to controls how much you forget"** `[S]`. An envelope is exactly a schedule on that
maximum. It preserves what restarts are for (each cycle gets a high phase to move and an anneal to consolidate)
while removing what makes them dangerous (a full-peak jump at 90% of the run). The code comment states this
correctly: *"A full-peak jump late in training is not a fresh exploration phase, it is discarding the anneal that
earned the current solution."* `[R]`

**The design detail that matters most, and which your code gets right:** the envelope is a function of **global**
progress, never of cycle progress, so it cannot itself oscillate `[R]`. An envelope driven by per-cycle progress
would produce a beat pattern and be much harder to reason about.

**Things to watch:**

1. **`LR_DECAY=1` gives you the strong version, and I'd default to it or near it.** The comment says
   `LR_DECAY=1` makes the last cycle peak near the floor so the run "ends annealed twice over" `[R]`. Given the
   D2Z evidence that lower final rates are strictly better `[S]`, and given the measured harm from full-peak
   restarts `[R]`, the intermediate settings mostly interpolate toward the known-bad end. If restarts are on, I
   would run `LR_DECAY=1` as the default and treat lower values as the ablation, not the reverse.

2. **The envelope multiplies the cycle value including its floor**, i.e. `_cyc * ((1−D) + D·env)` `[R]`. At
   `LR_DECAY=1` and end-of-run, the effective LR approaches `LR·min_frac²` = `2e-3 · 0.0025` = **5e-6**, i.e.
   0.25% of peak. That is *lower* than Llama 3's 1% floor `[S]` — probably fine and arguably good, but be aware
   that the composition squares the floor rather than reaching it. If you want the run to end at exactly 5% of
   peak, the envelope should apply to the *amplitude* only, not to the floor:
   `LR·(min_frac + (1−min_frac)·cycle_amp·env_amp)`. Worth deciding deliberately rather than inheriting.

3. **An envelope re-introduces horizon dependence.** The whole point of `LR_EPOCHS` was that the rate at step N
   depends only on position within a cycle, so it is the same in an 8-, 18- or 30-epoch run `[R]`. The envelope is
   a function of `_run_end`, which breaks that invariance: the same step in a longer run now gets a different rate.
   That is a *deliberate* trade (you cannot have both a fixed-shape schedule and a run-length-aware envelope), but
   it means **runs of different `EPOCHS` are no longer directly comparable under `LR_DECAY>0`**, and any
   projection error in `_run_end` now perturbs the envelope as well as the cycle. Your monotone-clamped projection
   `[R]` limits the damage; just don't forget the invariance is gone.

4. **No literature I found evaluates a decaying envelope at LLM scale.** The precedents are all CIFAR/ImageNet-era
   `[S]`. So this is a well-motivated extrapolation, not a validated technique. **Label it as such in any writeup.**

5. **The alternative the literature actually endorses.** If the goal is "keep learning late without a destructive
   jump", the published answer for continual settings is the **infinite LR schedule** — hold at a constant
   non-zero rate and anneal only on branches `[S]` — plus **weight averaging** to recover the anneal's benefit
   without annealing `[S]`. That is strictly simpler than an enveloped restart schedule and has direct empirical
   support in your exact setting. **I would treat "constant-tail + cooldown branches + EMA" as the baseline your
   envelope has to beat**, not cosine-with-full-peak-restarts (which is a strawman you have already shown to be bad).

## C.4 Per-expert learning rates clocked from each expert's own birth step

**Verdict: the motivating problem is real and well-documented; the specific mechanism has no direct literature
support that I could find; and there are three failure modes I'd watch.**

**The problem is real.** The code's diagnosis — *"an expert born at step 40000 is born into whatever rate the run
has decayed to and can never move far enough to differentiate, which is why late births arrive dead"* `[R]` — is
the same observation the continual-pretraining literature makes about new capacity generally: adaptation to new
material *stagnates* if you don't raise the LR, which is why re-warming exists at all `[S]`. Newly initialised
parameters at a decayed LR is the canonical "arrives dead" scenario.

**Closest published analogues (none is a direct match):**
- **Discriminative / layer-wise LRs** (ULMFiT) `[S]` — establishes that per-group LRs are a legitimate,
  well-behaved thing to do, with the rationale being exactly plasticity-vs-stability by group.
- **Population-Based Training** `[M]` — a population of learners with individually evolving LRs. But PBT selects
  LRs by *fitness*, not by *age*.
- **Model growth / progressive stacking**: when new layers are added mid-training the standard treatment is a local
  warmup for the new parameters `[S]` (search summary of the mid-training survey,
  https://arxiv.org/pdf/2510.23081, notes that mid-training LR scheduling across stages is an open area and that
  larger peak LR boosts plasticity and downstream adaptation but induces catastrophic forgetting).
- **Grouped learning-rate strategies in MoE-ish systems**: one search result described adopting *"a grouped
  learning-rate strategy to rapidly adapt models to new control capabilities while preserving generation priors
  inherited from pretraining"* `[S]` — same shape of idea, different domain. I could not fetch the source to
  confirm details.
- I found **no paper that clocks a per-expert LR schedule from the expert's birth step.** Treat this as novel.

**The implementation is sound, and one detail deserves highlighting.** The code correctly notes that scaling an
expert's *gradient* does nothing under Adam, because `m̂/(√v̂+ε)` is invariant to a constant factor on the gradient
`[R]`. Rescaling the **realised update** post-step is the correct fix and is optimizer-agnostic. This is a real
trap that a lot of per-group-LR implementations fall into; good catch.

**Failure modes to watch:**

1. **Adam's moments are shared per-tensor, and the rescale fights them.** `fab.A`/`fab.B` are single tensors, so
   Adam maintains one `m`/`v` per *element*, which is fine — but the post-hoc rescale means the update Adam
   *thinks* it applied is not the update that landed. Momentum then carries the *un*rescaled direction forward.
   For a boosted newborn (×4) the realised trajectory over-shoots relative to what `m` encodes; for a damped mature
   expert (<1) it under-shoots. The effect is a mild, persistent mismatch between the optimizer's internal state
   and reality. **It won't diverge, but it means the effective per-expert rate is not exactly `_own_lr`.** Worth
   measuring rather than assuming.

2. **The ×4 clamp (`FAB_LR_MAXR`) is doing a lot of load-bearing work, and its right value depends on the global
   rate.** A newborn at global-rate 5%-of-peak wants `LR_MIN_FRAC⁻¹ = 20×` to be at its own peak; the clamp gives
   it 4×. So late-born experts still arrive at 20% of the peak rate, not 100% — the mechanism is *attenuating* the
   problem rather than solving it. That is probably the safe choice (an unbounded multiple of a step Adam sized
   for a different regime is exactly the stale-`v` hazard from C.2), but be clear-eyed that at `FAB_LR_MAXR=4` a
   late birth is not really getting a fresh schedule. **If late births still arrive dead, the clamp is the first
   thing to raise — and the fix that makes raising it safe is a per-expert warmup**, for the same second-moment
   reason as C.2 `[S]`.

3. **Per-expert high LRs interact with the router, and the interaction is known to be unstable.** Search surfaced
   the finding that *"the router tends to favor faster-learning experts rather than encouraging task-aligned
   specialization, which can self-reinforce and collapse into a de facto single-expert network"* `[S]`
   (see also *Three Phases of Expert Routing*, https://arxiv.org/html/2604.04230v1 `[S]`, and Expert-Choice
   routing, https://research.google/blog/mixture-of-experts-with-expert-choice-routing/ `[S]`).
   **Giving newborns a 4× LR makes them the fastest-learning experts by construction.** That is either exactly what
   you want (newborns claim their region quickly) or a router-collapse accelerant (newborns keep out-competing
   incumbents, churn rises, nothing specialises). This is the interaction I would instrument first: track
   routing entropy / load balance with `FAB_LR_OWN` on vs. off. `FAB_LR_BOOST` on the cull-eligible bottom
   compounds this — it hands extra plasticity to precisely the experts the router is already ignoring, which is a
   reasonable rescue heuristic but also a way to keep dead experts twitching.

4. **Age-based annealing assumes birth-time is the right clock.** An expert born early into a region that only
   becomes important later will have annealed itself out of plasticity before its data arrives. A usage-based or
   fitness-based clock (anneal by cumulative tokens routed, not by wall-clock age) would be more robust and is
   closer to what PBT does `[M]`. Cheap to try: replace `fab.age(i, step)/span` with
   `cumulative_use(i)/expected_use`.

5. **Combined with C.2/C.3, you now have three interacting schedules** (global cycle, global envelope, per-expert
   age). Each is defensible; the product is hard to attribute. **Ablate them one at a time**, and given the
   measured seed-spread from restarts `[R]`, use enough seeds that a 1.5 b/B swing can't masquerade as an effect.

## C.5 Concrete recommendations, in priority order

1. **Turn `LR_RESTARTS` off, or turn `LR_DECAY` to 1, before running anything else.** Full-peak restarts are the
   one component with direct measured harm in this repo `[R]` and direct literature support for that harm `[S]`.
2. **Baseline against the schedule the literature actually recommends for continual training**: warmup → constant
   at peak → hold at a non-zero floor indefinitely, with **cooldown branches** whenever you want a deployable
   model, plus **weight averaging/EMA** along the plateau `[S]`. If your enveloped-restart schedule cannot beat
   that, use that.
3. **If you keep any restart, give each cycle a short (100–500 step) warmup.** The "warmup is only for cold
   optimizer state" reasoning misses the second-moment-staleness argument `[S]`.
4. **Sweep the peak LR at the current model width before drawing schedule conclusions** — the D2Z result is
   explicitly conditional on an optimal peak `[S]`.
5. **Decide deliberately whether the envelope multiplies the floor or only the amplitude** (C.3 item 2).
6. **Instrument router entropy / expert load when `FAB_LR_OWN` is on** (C.4 item 3).
7. **Consider a usage clock rather than an age clock for per-expert LRs** (C.4 item 4).

---

## Appendix — source list

Verified to exist at these URLs via search this session (`[S]`), fetched in full (`[F]`), or noted as memory-only.

**Fetched in full `[F]`**
- Schedule-Free Learning (code + README) — https://github.com/facebookresearch/schedule_free

**Search-verified `[S]`**
- SGDR: Stochastic Gradient Descent with Warm Restarts — https://arxiv.org/pdf/1608.03983
- Decoupled Weight Decay Regularization (AdamW) — https://arxiv.org/pdf/1711.05101
- Cyclical Learning Rates for Training Neural Networks — https://sands.kaust.edu.sa/classes/CS290E/F19/papers/clr.pdf
- Super-Convergence / one-cycle — https://arxiv.org/pdf/1708.07120
- Noam schedule implementation — https://docs.allennlp.org/main/api/training/learning_rate_schedulers/noam/ ,
  https://github.com/allenai/allennlp/blob/main/allennlp/training/learning_rate_schedulers/noam.py
- Transformers without Tears — https://arxiv.org/pdf/1910.05895
- On the Variance of the Adaptive Learning Rate and Beyond (RAdam) — https://arxiv.org/abs/1908.03265
- On the Adequacy of Untuned Warmup for Adaptive Optimization — https://arxiv.org/pdf/1910.04209
- Analyzing & Reducing the Need for Learning Rate Warmup in GPT Training — https://arxiv.org/pdf/2410.23922
- Training Compute-Optimal LLMs (Chinchilla) — https://proceedings.neurips.cc/paper_files/paper/2022/file/c1e2faff6f588870935f114ebe04a3e5-Paper-Conference.pdf
- The Llama 3 Herd of Models — https://arxiv.org/pdf/2407.21783
- 2 OLMo 2 Furious — https://arxiv.org/pdf/2501.00656
- Scaling Laws and Compute-Optimal Training Beyond Fixed Training Durations — https://arxiv.org/abs/2405.18392
- Understanding Warmup-Stable-Decay: River Valley Loss Landscape — https://arxiv.org/html/2410.05192v1
- Training Dynamics of the Cooldown Stage in WSD — https://arxiv.org/pdf/2508.01483
- WSM: Decay-Free LR Schedule via Checkpoint Merging — https://arxiv.org/pdf/2507.17634
- Power Scheduler — https://arxiv.org/pdf/2408.13359
- A Multi-Power Law for Loss Curve Prediction Across LR Schedules — https://arxiv.org/pdf/2503.12811
- Anytime Pretraining: Horizon-Free LR Schedules with Weight Averaging — https://arxiv.org/pdf/2602.03702
- WSqD: A Horizon-Free Learning Rate Schedule — https://arxiv.org/pdf/2607.10959
- Straight to Zero (D2Z), ICLR 2025 — https://arxiv.org/abs/2502.15938
- REX: Revisiting Budgeted Training with an Improved Schedule — https://arxiv.org/abs/2107.04197 ,
  https://proceedings.mlsys.org/paper_files/paper/2022/file/77cdf4ffbd2afd02541e02533ec56820-Paper.pdf
- Stepsize anything: unified LR schedule for budgeted-iteration training — https://arxiv.org/html/2505.24452v4
- Wide-minima Density Hypothesis and the Explore-Exploit LR Schedule (JMLR 24) — https://www.jmlr.org/papers/v24/21-0549.html
- Continual Pre-Training of LLMs: How to (re)warm your model? — https://arxiv.org/pdf/2308.04014 ,
  https://openreview.net/pdf?id=DimPeeCxKO
- Simple and Scalable Strategies to Continually Pre-train LLMs — https://arxiv.org/abs/2403.08763
- Beyond Cosine Decay: Infinite LR Schedule for Continual Pre-training — https://arxiv.org/html/2503.02844v2
- A Survey on LLM Mid-Training — https://arxiv.org/pdf/2510.23081
- Spike No More: Stabilizing the Pre-training of LLMs — https://arxiv.org/pdf/2312.16903
- A Closer Look at Deep Learning Heuristics: LR restarts, Warmup and Distillation — https://arxiv.org/pdf/1810.13243
- DASH: Warm-Starting NN Training without Loss of Plasticity (NeurIPS 2024) — https://arxiv.org/html/2410.23495v2
- On the Difficulty of Warm-Starting Neural Network Training (Ash & Adams) — https://www.researchgate.net/publication/336684851_On_the_Difficulty_of_Warm-Starting_Neural_Network_Training
- Maintaining Plasticity in Continual Learning via Regenerative Regularization — https://arxiv.org/pdf/2308.11958
- Large Batch Training of Convolutional Networks (LARS) — https://arxiv.org/pdf/1708.03888
- Large Batch Optimization for Deep Learning (LAMB) — https://arxiv.org/pdf/1904.00962
- ULMFiT / discriminative fine-tuning + STLR — https://slds-lmu.github.io/seminar_nlp_ss20/transfer-learning-for-nlp-i.html
- Learning-Rate-Free Learning by D-Adaptation — https://arxiv.org/pdf/2301.07733
- Prodigy (ICML 2024) — https://proceedings.mlr.press/v235/mishchenko24a.html , https://arxiv.org/abs/2306.06101
- The Road Less Scheduled (NeurIPS 2024) — https://arxiv.org/abs/2405.15682
- Online Learning Rate Adaptation with Hypergradient Descent — https://arxiv.org/abs/1703.04782 ,
  https://gbaydin.github.io/assets/pdf/baydin-2018-hypergradient.pdf
- Provable and practical online LR adaptation with hypergradient descent (ICML 2025) — https://dl.acm.org/doi/10.5555/3780338.3780752
- AutoLRS — https://arxiv.org/pdf/2105.10762
- Revisiting Learning Rate Control — https://arxiv.org/pdf/2507.01724
- timm SGDR with restart decay_rate — https://timm.fast.ai/SGDR
- Three Phases of Expert Routing (MoE load balance) — https://arxiv.org/html/2604.04230v1
- Mixture-of-Experts with Expert Choice Routing — https://research.google/blog/mixture-of-experts-with-expert-choice-routing/

**Memory-only, unverified this session `[M]`** — Robbins & Monro (1951); He et al. ResNet step decay; Goyal et al.
(2017) gradual warmup; Devlin et al. BERT linear decay; GPT-3 cosine-to-10%; Huang et al. Snapshot Ensembles;
Jaderberg et al. PBT; Izmailov et al. SWA; Smith et al. "Don't Decay the LR, Increase the Batch Size";
Yang et al. µP/µTransfer; Duchi AdaGrad; Tieleman & Hinton RMSProp; Kingma & Ba Adam; Shazeer & Stern Adafactor
(including its `1/√t` internal decay); Metz et al. VeLO; Ivgi et al. DoG; Cutkosky et al. Mechanic;
OLMo micro-annealing; the claim that Llama 2 / Mistral 7B used cosine floors of ~10%.

**Unresolved conflict** — one search summary lists **Llama-3.1** among WSD adopters while the Llama 3 paper summary
describes a cosine schedule for the 405B run. Both are `[S]`. Do not cite either without checking the paper directly.
