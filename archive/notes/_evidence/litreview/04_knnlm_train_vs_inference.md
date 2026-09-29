# Q4 — Is the kNN-LM datastore ever read during training?

## Answer

**No. Retrieval is inference-only in kNN-LM and in every descendant I checked.** The datastore
is built from a forward pass over the training set after the LM is already trained, and is
consulted only at test time. The base LM is never trained through the retrieval path.

This is stated consistently by three independent secondary sources that I read in full, all
describing Khandelwal et al. (ICLR 2020):

- **SeMem (arXiv 2303.01421, Section 6):** kNN-LM stores previously seen text examples and uses
  the memory at test time to enhance the parametric LM's prediction, with no training or
  retraining required.
- **Goodtriever (arXiv 2310.07589, Appendix A):** describes kNN-LM as extending a *pretrained*
  LM by linearly interpolating its next-word distribution with a kNN model, eliminating the need
  for training or retraining.
- **SeMem itself is inference-time only** — Section 4.2 attributes its lack of forgetting to
  the fact that it never updates the parametric LM's weights.

**Confidence: high.** Three independent statements, and it follows from the architecture: the
keys are the LM's own hidden states, so reading during training would make the datastore a
moving target relative to the encoder producing the queries.

---

## Is the datastore static in the original kNN-LM?

**Yes.** SeMem's v2 abstract (July 2026) makes the criticism explicit — semiparametric LMs
utilize non-parametric memory as **static storage**, which lacks learning capability and remains
disconnected from the internal information flow of the parametric model.

The v1 formalization (Eq. 3):

```
M = { (x̃_≤t → x_t) | x_t ∈ D }
```

One entry per training token, key = contextualized representation of the leftward context
(last-layer hidden state before the FFN), value = the target token. SeMem calls this
"full memorization" (FullMem). L² distance.

---

## The form of the interpolation weight λ — all three variants exist

### Original kNN-LM: fixed hyperparameter

```
P(y|x; Θ) = (1−λ)·P(y|x; θ)  +  λ·P(y|x̃; M)      (SeMem Eq. 2)
```

λ is a scalar hyperparameter tuned once on a validation set and held constant. Goodtriever
refers to it as a tuned parameter used to interpolate the two distributions.

### SeMem: learned, confidence-gated, per-token

SeMem replaces the constant with a neural calibrator predicting λ per token (Eq. 6):

```
θ*_c = argmax_{θ_c}  (1 − λ(x; θ_c))·P(y|x; θ) + λ(x; θ_c)·P(y|x̃; M)
```

A 4-layer MLP (128-d hidden, LeakyReLU per-feature encoders, Adam 3e-4, dropout 0.2) over
three feature families:

- **Distribution:** x̃ (context representation), `conf(x) = max_y P(y|x;θ)`, `ent(x)`
- **Lexical:** log freq of last context token, log #distinct values of last context token
- **Density:** L² distance to each of the top-10 retrieved neighbors; log #distinct values
  among top-10 retrieved values

**Ablation (Table 13) — the density features dominate:**

| Features | PPL |
|---|---|
| All | 8.6 |
| − density | **12.0** |
| − distribution | 9.9 |
| − lexical | 8.9 |

And calibration helps SeMem far more than it helps a full store (Table 12):

| | FullMem | RandMem | SeMem |
|---|---|---|---|
| Constant λ | 9.0 | 15.0 | 14.3 |
| NN calibrator | 8.3 (−0.7) | 12.5 (−2.5) | **8.6 (−5.7)** |

**This is the single most actionable number in this file for you.** A selectively-populated
store is nearly useless with a constant λ (14.3) and competitive with a full store once λ is
confidence-gated (8.6 vs 9.0, at 53% of the memory). If your store is selectively populated or
aggressively evicted, a constant λ will make it look like the store isn't working when the
actual problem is the gate.

### Goodtriever: neither — product of experts, not interpolation

Goodtriever explicitly abandons the interpolation form because kNN-LM only supports one
datastore, and uses `softmax(z_t + α(z_t⁺ − z_t⁻))` with a tuned α (Eq. 5). Worth knowing if
you ever need more than one store.

---

## Does anyone discuss the implication for a store that must be evicted online?

**Not directly — no paper frames "retrieval is inference-only" as a problem for online
eviction.** But there are two relevant threads:

1. **SeMem's admission decision is time-dependent and the paper says so.** Section 3.1 notes
   the memorization decision changes over time for the *same* case, because M keeps growing:
   once a case is memorized, similar cases become less likely to be memorized, since the LM no
   longer finds them hard. The memorization rate falls month over month (Figure 3), and drops
   from 53% (GPT-2 small) to 42% (GPT-2 large) at fixed data.

   **Implication for you:** if admission is confidence-gated and confidence depends on current
   store contents, then admission and eviction are coupled through a feedback loop. Evicting an
   entry raises the probability that a similar entry is admitted later. Nobody has analyzed
   this loop. It is a real hazard for an online-managed store and it is unstudied.

2. **The calibrator is trained online in SeMem** (Appendix A.2): 10 validation articles added
   per day to the calibrator's training set, epochs reduced from 5 to 1 over time to avoid
   overfitting; index rebuilt daily. So while *retrieval* isn't in the LM's training loop, the
   *gate* is trained continually against a growing store. That's the closest published thing to
   managing a live store, and it's a small MLP, not the LM.

**Confidence: high** on (1) and (2) as descriptions; **high** that no paper analyzes the
admission/eviction feedback loop, though as always a negative is weaker than a positive.
