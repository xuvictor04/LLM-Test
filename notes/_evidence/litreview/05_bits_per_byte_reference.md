# Q5 — Bits-per-byte reference points

**You asked me to lead with it if your anchor is materially different. It is.**

---

## Your anchor vs the published numbers

You have been using "GPT-2-small ≈ 1.0–1.2 b/B" as a single scale marker across all results.

**Source: Gao et al., "The Pile: An 800GB Dataset of Diverse Text for Language Modeling,"
arXiv:2101.00027, Table 2.** Evaluated per-document on one-tenth of the Pile test set,
converted to bits per UTF-8 byte.

| Corpus | GPT-2 small (124M) |
|---|---|
| Pile-CC (English web) | **1.0878** |
| OpenWebText2 (English web) | **1.1111** |
| **GitHub (code)** | **1.7912** |
| **The Pile (aggregate)** | **1.2253** |
| Wikipedia (en) | 1.1285 |
| Stack Exchange | 1.2981 |
| Books3 | 1.1959 |

**Verdict:**
- On **English web text**, your anchor is correct. 1.088–1.111 sits inside 1.0–1.2.
- On the **aggregate Pile**, your anchor is too low. 1.2253 is above your ceiling.
- On **code**, your anchor is off by ~50%. GPT-2-small is at 1.7912 on GitHub, not 1.0–1.2.

**The deeper problem: b/B on code is not a stable quantity at all.** From Table 4 of the same
paper, a 1.3B GPT-2-style model *trained on* the Pile scores **0.5597** on GitHub. So GitHub
b/B ranges from 0.5597 to 1.7912 — a **3.2× spread** — driven purely by whether the model saw
code in training. Web text is far more stable: Pile-CC spans 0.9989 (Pile-trained) to 1.0878
(GPT-2 small), a 1.09× spread.

If you have been quoting a single "≈1.1" scale marker across both web and code results, the
code comparisons need redoing. And any statement of the form "our model is X× worse than
GPT-2-small" needs the corpus named.

**Confidence: high.** Read directly from Table 2 and Table 4 of the primary source.

---

## Full reference table

### Zero-shot GPT-2 / GPT-3 on the Pile (Table 2, arXiv:2101.00027)

| Component | GPT-2 small | GPT-2 medium | GPT-2 large | GPT-2 xl | GPT-3 ada | babbage | curie | davinci |
|---|---|---|---|---|---|---|---|---|
| Pile-CC | 1.0878 | 0.9992 | 0.9582 | 0.9355 | 0.9212 | 0.8483 | 0.7849 | 0.7070 |
| OpenWebText2 | 1.1111 | 1.0073 | 0.9539 | 0.9171 | 0.8727 | 0.7921 | 0.7199 | 0.6242 |
| **Github** | **1.7912** | 1.3180 | 1.7909 | 1.6486 | 0.8761 | 0.7335 | 0.6415 | 0.5635 |
| Stack Exchange | 1.2981 | 1.1075 | 1.0806 | 1.0504 | 1.0096 | 0.8839 | 0.8004 | 0.7321 |
| Wikipedia (en) | 1.1285 | 1.0213 | 0.9795 | 0.9655 | 0.8757 | 0.7863 | 0.7047 | 0.5953 |
| Books3 | 1.1959 | 1.1063 | 1.0588 | 1.0287 | 0.9778 | 0.9005 | 0.8284 | 0.7052 |
| ArXiv | 1.3548 | 1.2305 | 1.1778 | 1.1381 | 1.0304 | 0.9259 | 0.8453 | 0.7702 |
| DM Mathematics | 2.6911 | 2.5448 | 2.4833 | 2.4377 | 2.3249 | 2.2015 | 2.1067 | 2.0228 |
| **The Pile** | **1.2253** | 1.0928 | 1.0828 | 1.0468 | 0.9631 | 0.8718 | 0.7980 | 0.7177 |

Full 22-component table is in `pile_bits_per_byte.csv`.

Note the non-monotonicity on GitHub: GPT-2 large (1.7909) is *worse* than GPT-2 medium
(1.3180). If you see non-monotone scaling on code in your own runs, there is precedent.

### 1.3B models trained on 40GB, evaluated on Pile heldout (Table 4)

| Eval set | Trained on Pile | CC-100 (en) | Raw CC (en) |
|---|---|---|---|
| Pile-CC | 0.9989 | 1.0873 | 1.0287 |
| OpenWebText2 | 0.9938 | 1.2222 | 1.0732 |
| **Github** | **0.5597** | 1.6509 | 0.9301 |
| Stack Exchange | 0.8152 | 1.5414 | 1.1292 |
| Wikipedia (en) | 0.8961 | 1.1807 | 1.0252 |
| DM Mathematics | 1.5206 | 3.1774 | 2.6229 |

And Table 3, size-controlled, same 1.3B architecture:

| Training set | Pile val (b/B) | Pile test (b/B) |
|---|---|---|
| The Pile | 0.9281 | 0.9433 |
| CC-100 (en) | 1.3143 | 1.3293 |
| Raw CC | 1.1180 | 1.1275 |

### Larger models (secondary source)

From arXiv:2410.08020 Appendix A, Table 2 (aggregating published Pile b/B):

| Model | b/B |
|---|---|
| GPT-2 (124M) | 1.241 |
| GPT-2 (774M) | 1.093 |
| Llama-3.2 (1B) | 0.697 |
| Phi-3 (3.8B) | 0.679 |
| GPT-3 (175B) | 0.666 |
| Phi-3 (14B) | 0.651 |

Note the 1.241 vs 1.2253 discrepancy for GPT-2 small — a rounding or protocol difference
between the aggregation and the Pile paper's own table. Use 1.2253 and cite the Pile paper
directly. **Confidence on the secondary table: moderate.**

---

## The 1M–100M range: no prior art found

**I could not find published bits-per-byte for models below 124M parameters on a standard
held-out corpus.** The Pile table starts at GPT-2 small.

The Gopher paper (arXiv:2112.11446, Appendix D.2, Table A7) reports loss per UTF-8 byte for
Gopher and its family of smaller models on a subset of Pile components, and that family reaches
down to 44M parameters. **I did not verify Table A7's values in this session.** That is the
single most likely place to find your sub-100M anchor and it is one fetch away — I'm flagging
it rather than reporting numbers I haven't read.

Practical note: below ~100M params the choice of tokenizer, context length, and document-level
vs concatenated evaluation start to dominate. The Pile paper computes perplexity **per
document**, not by concatenating — Section 3.1 explicitly flags this as a departure from common
practice, and it makes their numbers *higher* than concatenated evaluation would. If you
concatenate, your numbers are not comparable to this table.

---

## The conversion, so you can check your own pipeline

Pile paper, Section 3.1:

```
bpb = (L_T / L_B) · log₂(e^ℓ) = (L_T / L_B) · ℓ / ln(2)
```

L_T = dataset length in tokens, L_B = length in UTF-8 bytes, ℓ = mean NLL per token in nats.

**L_T / L_B = 0.29335 GPT-2-tokens per byte across the Pile.** Per-component values differ and
are in the paper's Table 7. This ratio is the thing people get wrong: if you use a different
tokenizer than GPT-2 you must recompute it, and if you assume the Pile average for a code
corpus you will be materially off, because Github has among the lowest bytes-per-token in the
Pile (Figure 6).

---

## Your measurements in context

Your reported 3.384 / 2.009 / 1.999 b/B all sit **above every model in the table on every
corpus except DM Mathematics** (which is 2.69 for GPT-2 small — a synthetic symbolic corpus, not
a fair comparison).

That is not necessarily bad — a from-scratch model at your scale trained on your token budget
should be worse than GPT-2 — but it does mean:

1. The interesting quantity in your growth result is the **ratio** 3.384 / 1.999 = 1.69×, not
   the absolute values.
2. Your 2048→4096 (2.009) vs fixed-2048 (1.999) gap is **0.010 b/B, or 0.5%**. Before treating
   that as "growth is nearly free," check it against seed variance. The nearest published
   analogue — TraceRetain's per-epoch stability analysis, and the MoE ecology paper's
   E91–E99 study (mean per-epoch σ = 0.28% on accuracy) — suggests run-to-run noise at small
   scale can be the same order as a 0.5% effect. **If you have one seed per condition, that
   comparison isn't yet supported.** The 3.384 result is far outside noise; the 2.009/1.999
   distinction may not be.
