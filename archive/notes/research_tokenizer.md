# Adaptive / Dynamic / Online Tokenization — Literature Reference

**Written for:** the author of `tokenizer.py::DynamicTokenizer` + the `TOK_*` machinery in `self_organize.py`.
**Date:** 2026-08-15.

---

## 0. Research conditions — read this before trusting a citation

Web access was **partially available**:

- `WebSearch` **worked**. Every URL in this document came back from a live search and is real as far as the search index is concerned.
- `WebFetch` was **blocked by the network egress proxy for every domain tried** — `arxiv.org`, `aclanthology.org`, `openreview.net`, `huggingface.co`, `en.wikipedia.org`, `themoonlight.io` all returned `EGRESS_BLOCKED` (proxy status confirmed `403 to CONNECT` for arxiv/openreview). Raw `curl` from the sandbox is likewise blocked.

**Consequence:** I could read *search-result summaries* (abstract-level, sometimes a sentence or two of method detail) but **could not read a single full paper**. So:

- Claims tagged **[V]** are supported by text I actually received from a search result in this session.
- Claims tagged **[M]** are from my own model knowledge and are **unverified in this session** — treat as a pointer to check, not as a fact. Failure-mode analysis is mostly **[M]**, because failure modes live in the discussion sections that I could not read.
- Where I give a number (e.g. "33% fewer tokens"), it is **[V]** if it appeared in a snippet, **[M]** otherwise.

Nothing here was fabricated; but anything **[M]** should be re-checked against the paper before it goes in a write-up.

---

## 1. The system under review (so this document is self-contained)

From `/home/user/LLM-Test/tokenizer.py` (`DynamicTokenizer`) and `/home/user/LLM-Test/self_organize.py`:

| Property | Implementation |
|---|---|
| Base alphabet | 256 raw bytes; byte-grounded, lossless round-trip; `blen()` gives bytes/token so eval reports true bits/**byte** |
| Vocabulary growth | **Mint-on-repetition during training.** `segment()` tallies adjacent-pair counts on the live stream; `maybe_grow()` promotes a pair crossing `min_pair` to a new id. Called on a `GROW_EVERY` cadence with `GROW_BURST` mints per event |
| Softmax width | **`VMAX` fixed at construction**; vocabulary grows *into* it. Unminted rows exist from step 0 |
| Which pair | `most_common(k)` optionally re-ranked by **novelty** `(c - seen)/(1+seen)^novel` — deliberately *not* the globally most frequent pair, so a new domain buys vocabulary for itself instead of rewriting existing spellings |
| Merge gate | **Branching-entropy family**, but thresholded on `p(b\|a) >= TOK_MINT_PMIN`, not on `H(next\|a)`. `H` is computed and *reported* only. Gate **fails open** (`gate_forced`) rather than ever leaving rows dead |
| Warm start | New embedding/head row = mean of the two parent rows (`WARMSTART`); optional `TOK_COMPOSE` byte-composer where a token *is* `composite(bytes) + zero-initialised residual`; `TOK_ANCHOR` decays a pull toward the composite over the token's own appearances |
| Re-segmentation | `RETOK_EVERY` re-segments the stream with the grown vocabulary (`RETOK_TAIL=1` → unconsumed tail only, legal because minting is append-only). Also invalidates the val cache `_VALT`, re-segments stored memory contexts (`remap_mem_ctx`), decays per-domain token histograms (`TOKC_DECAY`), and tells the growth controller the loss jump is self-inflicted (`note_shift`) |
| Un-merging | `retire(tid)` / `retire_stale()` — **soft**: pops from `seq2id` only, leaving `id2bytes` intact, because ids are positional (`merges[]` replay). Text re-segments to the parts; the row simply stops being indexed |
| Probation | `TOK_PROBATION`: a minted token is provisional; it must reach N appearances within `TOK_PROBATION_STEPS`, else retired. `TOK_PROBATION_BY=use` (appearances) or `embed` (`‖delta‖/‖composite‖` — did the whole exceed the sum of its parts) |
| Dead rows | `LOSS_MASK_DEAD` sets logits of never-minted ids to `-inf`, applied at **both** the loss and every eval path (masking only at the loss measured *worse* than not masking: 6.100 vs 4.746 b/B on an 86.7%-dead config) |

Two design commitments that the literature comparison keeps coming back to:
1. **Ids are append-only and positional.** Nothing renumbers. This is what makes retire soft, tail-retok safe, and checkpoints survivable.
2. **Dead softmax rows are treated as the worst failure mode of the system**, which is why the entropy gate is allowed to reorder but never to prevent minting.

---

# PART A — Exhaustive list of tokenization approaches

Grouped by what they actually do, because "adaptive tokenization" is used for at least four unrelated things in the literature.

## A.1 Static subword induction (train once, freeze, then train the model)

### A.1.1 BPE (Byte-Pair Encoding)
**Mechanism.** Originally a compression algorithm (Gage 1994 **[M]**); brought to NMT by Sennrich, Haddow & Birch, ACL 2016 **[M]**. Start from characters; repeatedly merge the most frequent adjacent pair; record the merge list. Encoding replays merges in learned rank order. Typically constrained by a *pre-tokenizer* (whitespace/regex) so merges never cross word boundaries. **[V]** BPE "iteratively merg[es] frequently co-occurring pairs of tokens until the desired vocabulary size is reached."
**Failure modes.**
- Frequency is not meaning: a pair can be frequent because it is a unit or because it straddles a boundary everything crosses. (Exactly the observation motivating your `_predictable` gate — and it is the stated motivation for entropy-informed pre-tokenization for Chinese **[V]**, https://arxiv.org/abs/2506.15889.)
- **Intermediate merge residues**: tokens created as stepping stones to longer tokens, retained in the vocabulary, then almost never emitted. **~10% of tokens in major tokenizers are residues** **[V]** (LiteToken, https://arxiv.org/abs/2602.04706).
- Greedy/rank-ordered encoding is not the shortest segmentation; the merge ordering is a path dependence baked in forever **[M]**.
- Data-mixture leakage: the merge list leaks the training mix **[V-ish]** (https://arxiv.org/pdf/2407.16607).
- Numbers, code indentation, and morphology get segmented inconsistently **[M]**.
- Tokenizer/model training are decoupled → glitch tokens (see A.6.1).

### A.1.2 Byte-level BPE
**Mechanism.** Alphabet = the 256 bytes rather than Unicode characters, so any input round-trips losslessly and there is no `<unk>`. GPT-2 (Radford et al. 2019) **[M]**; used by GPT-3/4, Llama-family, most modern LMs **[M]**. This is what your `ByteBPE` and `DynamicTokenizer` are.
**Failure modes.** Non-Latin scripts pay 2–4 bytes per character before any merge, so they are structurally disadvantaged at a fixed vocabulary size **[M]**. Byte-level merges can produce tokens that are not valid UTF-8 boundaries, so decoding must be buffered **[M]** (your `decode` uses `errors="replace"`, which is the honest version of this).

### A.1.3 WordPiece
**Mechanism.** BERT-family. Same greedy-merge shape as BPE, but the merge score is likelihood-based — roughly `count(ab) / (count(a) * count(b))` — rather than raw `count(ab)` **[M]**. Encoding is greedy longest-match-first (`MaxMatch`) with `##` continuation markers **[M]**.
**Note for you:** WordPiece's score is a *normalised* pair statistic — the same instinct as your `p(b|a)` gate, i.e. "is this pair more frequent than its parts predict", vs your "does `a` predict `b`". Yours is directional and asymmetric; WordPiece's is symmetric PMI-like. Worth citing as the nearest classical relative of `TOK_MINT_PMIN`.
**Failure modes.** Still frequency-driven; `##` markers make word-initial vs word-internal variants of the same string distinct tokens, doubling the cost of common strings **[M]**.

### A.1.4 Unigram LM / SentencePiece
**Mechanism.** Kudo 2018 **[M]**. **Top-down, not bottom-up**: "initializes a large number of units as its vocabulary and progressively removes units that have low contributions to the likelihood of the training corpus, until a pre-defined vocabulary size is obtained" **[V]**. EM for unit probabilities, Viterbi for segmentation, so it produces a *distribution over segmentations*, not one segmentation **[V]**.
**Relevance to you:** Unigram is the canonical prior art for **removing tokens from a vocabulary as a first-class operation** — pruning by marginal likelihood loss. Your probation is the same *shape* (mint provisionally, judge, remove) with a different evidence source (model-side usage / residual norm rather than corpus likelihood).
**Failure modes.** Needs a seed vocabulary and multiple EM passes → much slower to train than BPE **[M]**. Probabilistic segmentation at inference is nondeterministic unless you fix to the Viterbi-best **[M]**. Recent work questions which components are actually load-bearing **[V-ish]** ("Which Pieces Does Unigram Tokenization Really Need?", https://arxiv.org/pdf/2512.12641).

### A.1.5 VOLT — vocabulary learning via optimal transport
**Mechanism.** Xu et al., **ACL 2021 best paper** **[V]**. Frames vocabularization as optimal transport; introduces **MUV (Marginal Utility of Vocabularization)** — "the benefits (entropy) a corpus can get from an increase of cost (size)" **[V]** — and maximises it instead of trial-training many vocabulary sizes. Reported: **70% vocabulary size reduction and +0.5 BLEU on En-De; search cost 384 → 30 GPU hours** **[V]**. https://aclanthology.org/2021.acl-long.571/
**Relevance to you:** this is the principled version of "is this row worth its slot", answered offline from corpus statistics. Your probation answers the same question online from model evidence.
**Failure modes.** Optimises a corpus-side proxy (entropy vs size), not downstream loss; validated on NMT rather than large-scale LM pretraining **[M]**.

### A.1.6 Morfessor / MDL morphology induction
**Mechanism.** Creutz & Lagus **[V]**. Minimum Description Length: "favors lexicons with fewer and shorter sub-words" **[V]**, jointly costing the lexicon and the corpus-given-lexicon. Goldsmith's Linguistica uses MDL to accept/reject heuristic-proposed morphological changes **[V]**.
**Relevance to you:** MDL is the classical formalisation of "does this token earn its slot" — the *description-length* answer to your probation question. If you want a principled objective for `retire`, MDL is it: keep a merge iff `Δ(corpus bits) > Δ(lexicon bits)`.
**Failure modes.** Tuned for morphology, not compute-efficiency; MDL's lexicon cost has no notion of a *fixed* slot budget like your `VMAX` **[M]**.

### A.1.7 PathPiece / "Tokenization Is More Than Compression"
**Mechanism.** Schmidt, Reddy et al., EMNLP 2024 **[V]**. **PathPiece** "segments text into the minimum number of tokens for a given vocabulary" **[V]** — i.e. optimal (not greedy) segmentation, isolating the compression variable.
**Headline finding.** "When comparing compression and downstream accuracy across experimental settings, **no clear relationship was found between the two**" **[V]**. https://aclanthology.org/2024.emnlp-main.40.pdf
**Why this matters to you.** Your run reports bits/byte, and bytes/token is your compression proxy. This paper is the standing caution that *more compression at fixed vocabulary is not automatically better modelling*. It is the single most useful negative result in this bibliography for your project's framing.
**Also referenced:** **Rényi efficiency** as an intrinsic tokenizer metric that accounts for the frequency distribution (Zouhar et al. 2023, `tokenization-scorer`) **[V]**. This is a directly usable diagnostic for your vocabulary — it penalises exactly the degenerate distributions your minter could drift into.

### A.1.8 SuperBPE
**Mechanism.** COLM 2025 **[V]**. A **pretokenization curriculum**: Phase I merges only *within* whitespace-delimited units; Phase II lifts the pretoken boundary and allows "superword" merges spanning whitespace **[V]**. At 200k vocabulary: **up to 33% fewer tokens than BPE, +4.0% average accuracy over 30 downstream tasks** **[V]**. https://arxiv.org/abs/2503.13423, https://superbpe.github.io/
**Relevance to you.** Your tokenizer has **no pre-tokenizer at all** — `segment()` runs greedy longest-match over raw bytes, so multi-word tokens are reachable from step 0. SuperBPE is the evidence that this is an advantage, not a bug, *provided* the early vocabulary is forced through a subword stage first. Their finding that the **curriculum ordering matters** (subwords before superwords) is a live question for your novelty-weighted minting, which has no such staging.
**Failure modes.** Superword tokens are context-brittle; sequence-length gains do not transfer uniformly across languages **[M]**. A related follow-up exists on faster superword tokenization (https://arxiv.org/pdf/2604.05192) **[V-listing only]**.

### A.1.9 Boundless BPE
**Mechanism.** "Breaking the Pre-tokenization Barrier" **[V-listing]** — allows merges across pretoken boundaries. https://arxiv.org/html/2504.00178v1. Same family as SuperBPE. **[M]** on details.

## A.2 Stochastic / multiple segmentation (regularization)

### A.2.1 Subword regularization
**Mechanism.** Kudo 2018 **[V]**. Sample from the unigram LM's distribution over segmentations during training so the model sees the same string spelled many ways; requires the unigram LM + Viterbi sampling **[V]**.
**Failure modes.** Requires the unigram machinery; train/inference mismatch if inference is deterministic **[M]**; hurts if the sampling temperature is too aggressive **[M]**.

### A.2.2 BPE-dropout
**Mechanism.** Provilkov, Emelianenko & Voita, ACL 2020 **[V]**. During segmentation, **each merge is skipped with probability p**, producing varied segmentations from a *standard* BPE merge table; "training can be done without training any segmentations other than BPE and inference uses the standard BPE" **[V]**. https://aclanthology.org/2020.acl-main.170.pdf
**This is exactly your `DynamicTokenizer.dropout`** — your docstring's "preferential, not strict; falling back toward the raw byte" is BPE-dropout, implemented against a longest-match matcher rather than a merge-rank replay. Cite Provilkov et al. directly.
**Failure modes.** Best p is task/vocabulary dependent (~0.1 typical) **[M]**; degrades compression during training, so bits/byte measured *during* training is not comparable to eval **[M]** — relevant to you since `segment(count=True)` applies dropout while `count=False` does not.
**Variant:** MaxMatch-Dropout for WordPiece, COLING 2022 **[V]**, https://aclanthology.org/2022.coling-1.430.pdf.

## A.3 No vocabulary at all (character / byte models)

### A.3.1 ByT5
**Mechanism.** T5 on raw UTF-8 bytes, no tokenizer **[V]**. "Outperform[s] T5 in scenarios sensitive to the presence of noise in text and on tasks sensitive to spelling" **[V]**.
**Failure modes.** Sequence lengths ~4–5× longer → quadratic attention cost; needs a rebalanced encoder/decoder depth; slow inference **[M]**. This is precisely the "a byte-level model spends its whole budget predicting single characters" observation in your `tokenizer.py` header.

### A.3.2 CANINE
**Mechanism.** Character-level (Unicode codepoint) counterpart to mBERT, with **convolutional downsampling** before a 12-layer Transformer encoder **[V]**; hash-based codepoint embeddings to avoid a huge table **[M]**.
**Failure modes.** Encoder-only; downsampling rate is fixed and content-agnostic **[M]**.

### A.3.3 MambaByte
**Mechanism.** Token-free selective state-space model over bytes **[V-listing]**, https://arxiv.org/pdf/2401.13660. SSM's linear cost partly neutralises the long-sequence penalty of byte modelling **[M]**.

### A.3.4 MegaByte
**Mechanism.** Byte-level decoder that "segment[s] sequences into **fixed-length patches**", with a large global model over patches and a small local model within them **[V]**.
**Failure modes.** **[V]** the fixed patches "may not align with meaningful units of text" — the exact failure that motivated everything in A.4.

### A.3.5 SpaceByte
**Mechanism.** NeurIPS 2024 **[V]**. Like MegaByte but "uses a **simple rule** to dynamically partition the bytes into patches that are aligned with word and other language boundaries" (i.e. patch on space-like bytes) **[V]**. "Significantly outperforms all other byte-level architectures and consistently outperforms the subword Transformer when using GPT-2 tokens" **[V]**. https://proceedings.neurips.cc/paper_files/paper/2024/file/e1f418450107c4a0ddc16d008d131573-Paper-Conference.pdf
**Relevance to you.** Note that your `ByteBPE.train`/`encode` chunk on `0x20`/`0x0a` — a space-boundary rule — while `DynamicTokenizer` does not. SpaceByte is evidence that the cheap space rule captures most of the benefit of learned boundaries in English-like text.
**Failure modes.** Fails on unsegmented scripts (Chinese, Japanese, Thai) and on code/binary where whitespace is not a boundary **[M]**.

## A.4 Learned / dynamic segmentation *inside* the model (no vocabulary to grow)

This is where "dynamic tokenization" most commonly means something in 2023–2026. Note that **none of these grow a discrete vocabulary** — they replace it with a boundary predictor. That is the deepest structural difference from your system.

### A.4.1 Charformer / GBST
**Mechanism.** ICLR 2022 **[V]**. Gradient-Based Subword Tokenization: "a position-wise **soft selection over candidate subword blocks** using a scoring network", learning "interpretable latent subwords" **[V]**. Enumerate block sizes 1..M, score each, softmax-blend, downsample. https://arxiv.org/pdf/2106.12672
**Failure modes.** Soft blending means no discrete tokens, so no discrete vocabulary to inspect or reuse; fixed downsampling rate; blocks are enumerated at fixed strides so boundaries are quantised **[M]**.

### A.4.2 MANTa
**Mechanism.** Godey, Castagné, de la Clergerie & Sagot, Findings of EMNLP 2022 **[V]**. "Module for Adaptive Neural TokenizAtion", **differentiable, trained end-to-end with the LM** **[V]**: a sliding-window attention Transformer assigns each byte a **separation probability**, and those probabilities weight the byte contributions to pooled block representations — "blocks with smooth borders" **[V]**. Claimed explainable because it emits an explicit segmentation. Improves robustness to character perturbations and out-of-domain data **[V]**. https://aclanthology.org/2022.findings-emnlp.207/
**Failure modes.** Trades speed against byte-model expressiveness; soft borders mean the "segmentation" is only a readout, not a commitment **[M]**.

### A.4.3 Dynamic Token Pooling
**Mechanism.** Nawrot, Chorowski, Łańcucki & Ponti, **ACL 2023** **[V]**. Predicts segment boundaries **autoregressively** and pools between them. They compare boundary sources: "end-to-end learning through **stochastic re-parameterisation**, supervised learning (based on segmentations from subword tokenizers or **spikes in conditional entropy**), as well as linguistically motivated boundaries" **[V]**. Result: jointly segmenting and modelling is "both faster and more accurate than vanilla Transformers and fixed-length pooling within the same computational budget" **[V]**. https://aclanthology.org/2023.acl-long.353/, code https://github.com/PiotrNawrot/dynamic-pooling
**Relevance to you.** The single most useful ablation in the literature for your entropy gate: they *directly compare* entropy-spike boundaries against learned and against tokenizer-derived boundaries in one controlled setting. If you want an answer to "is my entropy criterion competitive", this is the paper to read in full.
**Failure modes.** Gumbel/reparameterised boundary learning is unstable and needs a boundary-rate regulariser or it collapses to all-boundaries or no-boundaries **[M]**.

### A.4.4 Byte Latent Transformer (BLT)
**Mechanism.** Meta, Dec 2024, **ACL 2025** **[V]**. Two models: a small **entropy model (patcher)** that predicts next-byte entropy, and the main Local Encoder → Global Transformer → Local Decoder **[V]**. Patch boundaries from next-byte uncertainty by one of two rules: **global threshold** (entropy exceeds a fixed value) or **relative / approximate-monotonicity** (entropy breaks a monotonic decrease within the patch) **[V]**. Explicitly "allocat[es] more compute and model capacity where increased data complexity demands it" **[V]**. First FLOP-controlled byte-level scaling study to 8B params / 4T bytes **[V]**. https://arxiv.org/abs/2412.09871, https://aclanthology.org/2025.acl-long.453/
**Relevance to you — read carefully.** BLT's entropy is **next-byte predictive entropy under a learned model**, i.e. `H(next | full left context)`. Your `branch_entropy` is `H(next | a)`, a **unigram-conditioned corpus statistic**. These are different objects with the same name; BLT's is much stronger (uses context) and much more expensive (needs a second model). Your project note that absolute `H` thresholds "do not survive contact with real text" is consistent with BLT needing the *relative/monotonic* variant rather than a pure global threshold — they hit the same problem and solved it by making the threshold relative rather than by switching to a probability, as you did.
**Failure modes.** Requires training and serving a separate entropy model; patch boundaries at inference depend on that model, so it is a second thing that can drift; the global-threshold variant is sensitive to the threshold and to domain **[M]**. Follow-up work on speed exists ("Fast Byte Latent Transformer", https://arxiv.org/pdf/2605.08044) **[V-listing]**.

### A.4.5 H-Net / dynamic chunking
**Mechanism.** Hwang et al. 2025 **[V]**. "Fully end-to-end, tokenizer-free… learns how to segment and compress byte-level inputs through a dynamic chunking (DC) mechanism" **[V]**. Hierarchical U-Net (encoder → DC → main network → decoder); boundaries learned "via **similarity routing** and smoothing, optimized with a **ratio loss** and straight-through estimator" **[V]**. Results: 1-stage H-Net matches BPE Transformer perplexity; **2-stage H-Net outperforms a BPE Transformer with 2× the parameters at matched compute**, learning ~**4.7 bytes/chunk** (comparable to GPT-2 BPE) **[V]**. https://arxiv.org/pdf/2507.07955
**Relevance to you.** The **ratio loss** is the mechanism H-Net needs to stop chunking from collapsing — an explicit target compression rate enforced as a loss term. Your analogue is `min_pair` + `VMAX` + the fail-open gate, which control the same quantity by construction rather than by gradient. Also: 4.7 bytes/chunk is a useful yardstick for your `bytes_per_id` reporting.
**H-Net++** extends it to morphologically rich languages (Persian): 0.159 BPB reduction vs BPE GPT-2-fa, 73.8% F1 against gold morphological boundaries **[V]**. https://arxiv.org/abs/2508.05628
**Failure modes.** STE + ratio loss is the fragile part; chunk-boundary collapse is the known failure **[M]**.

### A.4.6 AU-Net (From Bytes to Ideas)
**Mechanism.** FAIR/Meta + INRIA, 2025 **[V]**. Autoregressive U-Net over raw bytes with a **fixed multi-scale hierarchy**: Stage 1 raw bytes → Stage 2 pool at word boundaries → Stage 3 every two words → Stage 4 every four words (or sentence end) **[V]**. "Eliminates the need for predefined vocabularies and large embedding tables while preserving BPE performance with higher compression"; matches strong BPE baselines under controlled compute **[V]**. https://arxiv.org/abs/2506.14761
**Failure modes.** The splitting rule is largely hand-specified (whitespace/sentence), so it inherits SpaceByte's script dependence **[M]**.

### A.4.7 MrT5
**Mechanism.** "Dynamic Token Merging for Efficient Byte-level Language Models" **[V-listing]**, https://arxiv.org/abs/2410.20771 — learns to *delete/merge* byte tokens inside the encoder rather than to segment up front. **[M]** on details.

### A.4.8 Learn Your Tokens
**Mechanism.** "Word-Pooled Tokenization for Language Modeling" **[V-listing]**, https://arxiv.org/pdf/2310.11628 — pool bytes/chars within words, predict the word's characters from the pooled representation. **[M]** on details.

### A.4.9 Retrofitting LLMs with Dynamic Tokenization
**Mechanism.** Feher, Vulić & Minixhofer (Cambridge), **ACL 2025** **[V]**. Decide token boundaries **per input batch** with a BPE-inspired subword-merging algorithm — "merges frequent subword sequences **in a batch**", then a pretrained **embedding-prediction hypernetwork computes the token embeddings on the fly** **[V]**. Encoder (XLM-R): >20% shorter sequences across 14 languages at <2% performance loss; decoder (Mistral-7B): up to 17% shorter with minimal degradation **[V]**. Notes explicitly that "dynamic tokenization can result in an **unbounded vocabulary** when applied to autoregressive generation", handled by expanding to a large but bounded vocabulary **[V]**. https://aclanthology.org/2025.acl-long.1444/
**This is the closest thing in the literature to "the vocabulary is minted from the live stream", except it is per-batch and transient, and the embedding comes from a hypernetwork rather than from a warm start.** Read this one.

### A.4.10 Generation with Dynamic Vocabulary
**Mechanism.** EMNLP 2024 **[V]**. "A dynamic vocabulary … can involve **arbitrary text spans** during generation, with these text spans acting as basic generation bricks, akin to tokens in traditional static vocabularies"; multi-token atomic generation improves MAUVE by 25% and cuts latency 20% **[V]**. https://aclanthology.org/2024.emnlp-main.1053/
**Relevance to you.** Prior art for *adding emittable units to the output distribution at runtime*. Their spans get embeddings computed on demand rather than trained. Directly comparable to your minted rows entering the head mid-run.

### A.4.11 Others in this family (listing only, **[V-listing]**)
- HAMburger: "Accelerating LLM Inference via Token Smashing" — https://arxiv.org/pdf/2505.20438
- Adaptive Targeted Dynamic Chunking — https://arxiv.org/pdf/2605.30080
- Scratchpad Patching: "Decoupling Compute from Patch Size in Byte-Level LMs" — https://arxiv.org/pdf/2605.09630
- Compute Optimal Tokenization — https://arxiv.org/pdf/2605.01188
- DynaMo: dynamic multi-token sampling, NAACL 2024 — https://aclanthology.org/2024.naacl-long.182/

## A.5 Adapting an existing tokenizer to a new language or domain

### A.5.1 Vocabulary expansion + continual pretraining (CPT)
**Mechanism.** Add target-language/domain tokens to the vocabulary, initialise their embeddings, continue pretraining. **[V]** "Vocabulary extension is an efficient way to adapt pretrained LLMs to new languages, but the **initialization of newly added token embeddings can strongly affect CPT efficiency**."
**Initialisation strategies, ranked by a 2026 systematic study of >20 methods** ("Beyond Initialization Loss", https://arxiv.org/abs/2608.03494) **[V]**:
- **Subword composition methods outperform both vocabulary averaging and external/learned initialisation** (FOCUS, top-k semantic retrieval, residual MLP mappings) **[V]**.
- Asymmetric variants (different rules for input embedding vs output head) achieve the lowest early validation loss **[V]**.
- Best observed config: input embeddings = uniform subword averaging + **language-specific norm calibration**; output head = **character-length-weighted** subword averaging **[V]**.
- **Warning:** "Initialization loss and initialization bits-per-byte are **unreliable predictors of downstream convergence**"; only lightweight CPT gives a reliable signal **[V]**.
- Norms matter: "a token can achieve a high logit simply by having a **large embedding norm**", creating systemic bias **[V]**.
**Failure modes.** Catastrophic forgetting of the source language/domain; the larger the extension, the longer the CPT needed **[V]**; embedding-norm mismatch between old and new rows distorts the softmax **[V]**.
**Other entries:** "How Can We Effectively Expand the Vocabulary of LLMs with 0.01GB of Target Language Text?" (Computational Linguistics 52:1) **[V-listing]**, https://direct.mit.edu/coli/article/52/1/295/134270/ ; HYPEROFA (hypernetwork-based init) https://arxiv.org/pdf/2504.21018 **[V-listing]**; KL-based self-distillation for vocabulary expansion https://arxiv.org/pdf/2508.15807 **[V-listing]**.

### A.5.2 Tokenizer transplantation / zero-shot tokenizer transfer
- **ZeTT** (Minixhofer & Ponti, **NeurIPS 2024**) **[V]**: train a **hypernetwork that takes a tokenizer as input** and predicts embedding parameters for it; trained over a *distribution* of tokenizers. Generalises to XLM-R and Mistral-7B, "preserves accuracy to 1% on average, sequences 14% shorter, inference >16% faster"; the residual gap closes with <1B tokens of continued training; a hypernetwork trained for a base model transfers to its fine-tunes **[V]**. https://arxiv.org/abs/2405.07883
- **Training-free transplantation via Orthogonal Matching Pursuit** **[V]**: "represents each new token's donor embedding as a **sparse combination of shared token embeddings**, replicating those same sparse coefficients in the base model's embedding space" — geometry-preserving, no training. https://arxiv.org/pdf/2506.06607
- **WECHSEL / FOCUS** **[M]**: initialise new embeddings from external aligned static word embeddings (WECHSEL) or from overlapping-token combinations (FOCUS).
- **Model-Aware Tokenizer Transfer** https://arxiv.org/pdf/2510.21954 **[V-listing]**; **Universal Cross-Tokenizer Distillation** https://arxiv.org/pdf/2503.20083 **[V-listing]**; **TokenAdapt / heuristic adaptation + supertoken learning** https://arxiv.org/html/2505.09738 **[V-listing]**.
- **Tokenizer swapping is cheap and works**: "Language Adaptation on a Tight Academic Compute Budget: **Tokenizer Swapping Works** and Pure bfloat16 Is Enough" https://arxiv.org/pdf/2408.15793 **[V-listing]** — and, importantly for you, its mid-training-swap result: **[V]** "directly after reinitializing the new embeddings, tokenizer swapping performs worse than keeping the original tokenizer … However, tokenizer swapping quickly catches up at the next evaluation interval and obtains a slight advantage during further training." Also **[V]**: "there's a tradeoff in when to change tokenizers: **too early and the tokenizer is not representative enough yet; too late may introduce other inefficiencies**." That is a direct empirical statement about your `TOK_MINT_UNTIL` question.

### A.5.3 Domain-adaptive tokenization
- **Adaptive Tokenization** (Sachidananda, Kessler et al., SustaiNLP@EMNLP 2021) **[V]**: "domain-specific subword sequences can be determined efficiently directly from **divergences in the conditional token distributions** of the base and domain-specific corpora" — then those sequences are added to the vocabulary and initialised from their subword pieces. https://aclanthology.org/2021.sustainlp-1.16/
- **exBERT** (EMNLP 2020) **[V]**: "extends pre-trained models with domain-specific vocabulary under constrained training resources" — adds an *extension module* and extension vocabulary rather than editing the base.
- **AVocaDo** (EMNLP 2021) **[V]**: adapt vocabulary to the downstream domain, with a regulariser against over-fitting the new vocabulary.
- **Task-Adaptive Tokenization** **[V]**: uses subword regularization to reduce sequence length on the target task.
- Domain Word Extension via curriculum learning (Sensors 2023) **[V-listing]**, https://www.mdpi.com/1424-8220/23/6/3064.
- Chemistry: "The Tokenization Bottleneck: How Vocabulary Extension Improves Chemistry Representation Learning" https://arxiv.org/pdf/2511.14365 **[V-listing]**.
- Summarization: parameter-efficient vocabulary adaptation https://arxiv.org/html/2605.17379 **[V-listing]**.

### A.5.4 Continued BPE training / "Teaching Old Tokenizers New Words"
**Mechanism.** **[V]** "A recent approach is **continued BPE training**, which extends a pre-trained tokenizer by **continuing the BPE merge learning process on new data**, with experiments showing this approach improves tokenization efficiency and better utilization of added vocabulary." https://arxiv.org/pdf/2512.03989
**This is the closest published analogue to `DynamicTokenizer` mechanically** — append new merges on top of an existing merge list, preserving all existing ids — but it is done *between* training phases, not concurrently with training. **[M]** on whether they also re-segment already-seen data.
Also relevant: **[V]** "Incremental BPE systems learn to generate vocabulary introduced online. An incremental BPE system starting from a lower vocabulary and later adding a higher vocabulary is correctly able to generate newly introduced terms" (from "Optimizing Segmentation Granularity for NMT", https://arxiv.org/pdf/1810.08641) — this is 2018 prior art for *incrementally added merges being usable by an already-trained model*.

## A.6 Shrinking / cleaning a vocabulary

### A.6.1 Detecting under-trained ("glitch") tokens
**Mechanism.** Land & Bartolo, "Fishing for Magikarp", **EMNLP 2024** **[V]**. "The **disconnect between tokenizer creation and model training** allows for specific inputs, such as the infamous `SolidGoldMagikarp` token, to induce unwanted model behaviour"; glitch tokens are "present in the tokenizer vocabulary but nearly or entirely absent during model training" **[V]**. Detection: examine the **unembedding matrix**, normalise by removing the constant component, then measure **cosine distance between the mean unused-token embedding and each row** **[V]**. https://arxiv.org/abs/2405.05417, https://aclanthology.org/2024.emnlp-main.649.pdf
**Directly relevant to your `LOSS_MASK_DEAD`:** this is the canonical description of the pathology you are pre-empting, and it gives you a **ready-made diagnostic for your never-minted `VMAX` rows** — they should cluster tightly around the mean unused embedding; if a *minted* row does too, it never earned its slot (an alternative probation test to `‖delta‖/‖composite‖`).
**Related:** GlitchMiner (gradient-based mining) https://arxiv.org/pdf/2410.15052 **[V-listing]**; AnomaLLMy (black-box detection via low-confidence single-token predictions) https://arxiv.org/pdf/2406.19840 **[V-listing]**.

### A.6.2 Vocabulary trimming (VT)
**Mechanism.** Findings of EMNLP 2023 **[V]**. "Reduce a multilingual LM vocabulary to a target language by **deleting potentially irrelevant tokens**"; sort by corpus frequency, keep top-K, "the embedding associated with pruned tokens is removed and the **token IDs and embedding matrices are reorganized accordingly**" **[V]**. Result: top-40K per language gave **no measurable performance loss** **[V]**. https://aclanthology.org/2023.findings-emnlp.981/, TextPruner toolkit https://arxiv.org/pdf/2203.15996
**Note the contrast with your `retire`:** VT **renumbers**. You explicitly refuse to, because ids are positional in your merge replay. VT can renumber because it happens *once, offline, after* training.
**Failure modes.** Post-hoc only; the trimmed model can no longer represent the removed material at all (no byte fallback in a non-byte-grounded vocabulary) **[M]**.

### A.6.3 Picky BPE — **the key citation for un-merging during tokenizer training**
**Mechanism.** Chizhov et al., **EMNLP 2024** **[V]**. "A BPE modification that implements **removing of the intermediate tokens during tokenizer training**" **[V]**. Criterion: **Intersection over Self (IoS)** = "the ratio of pair frequency to token frequency, showing how often a token occurs as part of a specific pair compared to all occurrences of that token. If this value is too high (close to 1), a token is highly likely an **intermediate token**, an integral part of a longer, more meaningful token" **[V]**. When a merge `a+b → ab` is made and `IoS(a)` is above threshold, `a` is dropped from the vocabulary and its slot is freed **[M]** (mechanism inferred; the snippet confirms removal and IoS but not the exact slot bookkeeping).
**Reported effects [V]:** "more efficient usage of the limited vocabulary and embedding parameters, **reduces the number of tokens that are likely to be under-trained**, and frees space for higher-quality word-initial tokens"; and, unlike other trimming procedures, "**does not compromise text compression**".
https://aclanthology.org/2024.emnlp-main.925/, https://arxiv.org/abs/2409.04599, code https://github.com/pchizhov/picky_bpe

**Compare to yours, precisely.** IoS is `count(a,b) / count(a)` — the *same ratio* as your `_predictable`'s `p(b|a) = count(a,b) / Σ_b' count(a,b')`, since `Σ_b' count(a,b')` is essentially `count(a)` as a left half. **You and Picky BPE compute the same statistic and use it in opposite directions:**
- Picky BPE: `IoS(a)` **high** → `a` is a mere stepping stone → **delete `a`**.
- Yours: `p(b|a)` **high** → `a` predicts `b` → **mint `ab`**.
These are consistent — a high ratio says "`a` mostly lives inside `ab`", which simultaneously licenses the merge and condemns the part. **Your gate and Picky's pruner are two halves of one criterion, and you have only implemented the minting half.** The natural extension: when `p(b|a) ≥ pmin` triggers a mint, also test whether `a` is now dead weight and `retire(a)`. Your `retire` is already the exact primitive needed, and unlike Picky you can afford it because byte fallback guarantees losslessness.

### A.6.4 LiteToken
**Mechanism.** 2026 **[V]**. Removes "**intermediate merge residues**" from an *already-trained* BPE tokenizer: corpus-driven statistical detection of candidates, filtering to retain linguistically meaningful roots/affixes, then a **re-merging algorithm that ensures the pruned vocabulary can still tokenize the original corpus** **[V]**. ~10% of tokens in major tokenizers are residues **[V]**. Key claim: "because the affected tokens are **rarely used, pretrained models can often accommodate the modified tokenizer without additional fine-tuning**" **[V]**. https://arxiv.org/abs/2602.04706
**Directly relevant to you:** this is empirical support that **retiring rarely-used tokens mid-life is cheap for the model** — the strongest external evidence for your `retire_stale` design. The re-merging algorithm is also the thing your `retire` gets for free from byte-grounding.

### A.6.5 Unigram pruning
Covered in A.1.4 — the original "remove units with low likelihood contribution" loop, and the oldest prior art for a vocabulary that shrinks by evidence **[V]**.

## A.7 Growing a vocabulary *during* model training

This is the narrow question, so this section is deliberately complete.

### A.7.1 Vocabulary Curriculum (**the closest published prior art to your system**)
**Mechanism.** Feb 2025 **[V]**. "Modern language models rely on static vocabularies fixed before pretraining"; this method **"alternates between entropy-guided vocabulary expansion and model optimization"**, so the model "learn[s] transferable representations across diverse tokenization granularities" **[V]**. Concretely: 5 iterations of expansion from a **base vocabulary of 92**, then models at **4359 → 7941 → 11382 → 14819 → 18276** **[V]**. Claim: **log-linear scaling gains relative to vocabulary size** **[V]**.
**Emergent behaviour reported [V]:** "an optimal computation allocation pattern: **longer tokens capture predictable content, while shorter tokens focus on more complex, harder-to-predict contexts**" — the same allocation principle BLT engineers explicitly.
https://arxiv.org/abs/2502.17910, https://huggingface.co/papers/2502.17910
**Caveats [V]:** small-scale GPT models only; the authors state they plan to extend to larger models and diverse domains.
**What I could not verify [M]:** how they initialise the new rows, whether the softmax is resized or pre-allocated, whether tokens are ever removed, and what they do about already-trained embeddings when segmentation shifts. **These are exactly your open questions and this is the paper to obtain in full.**

### A.7.2 Continued BPE training / incremental BPE
See A.5.4. **[V]** for the mechanism; growth is *between* phases rather than continuous.

### A.7.3 Retrofitting with Dynamic Tokenization (A.4.9) and Generation with Dynamic Vocabulary (A.4.10)
Both add emittable units at runtime, both sidestep the trained-row problem by *computing* embeddings (hypernetwork / span encoder) instead of training them. **[V]**

### A.7.4 Batching BPE tokenization merges
https://arxiv.org/pdf/2408.04653 **[V-listing]** — merges applied in batches rather than one at a time during tokenizer training; relevant to your `GROW_BURST`. **[M]** on findings.

### A.7.5 Federated / privacy-preserving tokenizer training
"Training a Tokenizer for Free with Private Federated Learning" https://arxiv.org/pdf/2203.09943 **[V-listing]** — learns the vocabulary from the live federated stream, i.e. from data never seen centrally. Another instance of "vocabulary from a live stream" **[M]** on details.

## A.8 Criteria and diagnostics used to judge vocabularies

| Criterion | Origin | Normally used for |
|---|---|---|
| Raw pair frequency | Gage 1994 / Sennrich 2016 **[M]** | BPE merges |
| Likelihood ratio ≈ PMI | WordPiece **[M]** | merge scoring |
| Corpus likelihood loss | Unigram LM **[V]** | pruning |
| MDL (lexicon + corpus bits) | Morfessor, Goldsmith **[V]** | morphology induction |
| MUV / optimal transport | VOLT **[V]** | choosing vocabulary size |
| **Branching entropy / accessor variety** | Harris 1955; Kempe 1999; Tanaka-Ishii 2005; **Jin & Tanaka-Ishii COLING/ACL 2006** **[V]** | **unsupervised word segmentation** — see Part C.4 |
| Next-byte predictive entropy | BLT **[V]**, Dynamic Token Pooling **[V]** | patch/segment boundaries |
| PMI + left/right entropy | Entropy-Driven Pre-Tokenization for BPE, ICML 2025 workshop **[V]** | Chinese pre-tokenization before BPE |
| Compression (bytes/token) | ubiquitous | tokenizer comparison — **but see PathPiece: no clear relation to downstream accuracy [V]** |
| Rényi efficiency | Zouhar et al. 2023 **[V]** | frequency-distribution-aware quality |
| IoS | Picky BPE **[V]** | identifying removable intermediate tokens |
| Unembedding-row geometry | Fishing for Magikarp **[V]** | detecting under-trained tokens |
| Compute-optimal vocabulary size | Tao et al., **NeurIPS 2024** **[V]** | sizing `V` — see Part B |

---

# PART B — What is actually used in practice, ranked

Ranking is by share of deployed/serious-pretraining systems as of mid-2026 **[M for the ranking itself; the individual facts are cited]**.

**1. Byte-level BPE with a regex pre-tokenizer.** *Dominant by a wide margin.*
Why: deterministic; no `<unk>` ever; trivially cacheable; the merge table is a small JSON; every serving stack, every quantization tool, every eval harness assumes it. GPT-2 through GPT-4/5, Llama, Mistral, Qwen, DeepSeek, Gemma **[M]**. The regex pre-tokenizer (splitting on whitespace/punctuation/digit-run boundaries) is now as standard as the merges themselves and does most of the work of preventing pathological tokens **[M]**.

**2. Unigram / SentencePiece.** *Second, and mostly on the multilingual and encoder side.*
Why: better morphological alignment, principled subword regularization, language-agnostic (no whitespace assumption). T5, mT5, ALBERT, XLNet, many multilingual encoders **[M]**. Loses on ecosystem inertia rather than on quality.

**3. WordPiece.** *Legacy but enormous installed base.* BERT and its descendants **[M]**. Almost nobody chooses it for a new model.

**4. Larger vocabularies as a deliberate scaling decision.** *Rapidly ascending since 2024.*
"Scaling Laws with Vocabulary: Larger Models Deserve Larger Vocabularies" (Tao et al., **NeurIPS 2024**) **[V]**: optimal vocabulary grows with compute budget; **most LLMs use insufficient vocabulary sizes**; "the optimal vocabulary size of Llama2-70B should have been at least **216K**, 7× larger than its 32K"; 32K→43K improved ARC-Challenge 29.1→32.0 at the same 2.3e21 FLOPs **[V]**. https://arxiv.org/abs/2407.13623
This is why 128K–256K vocabularies are now normal (Llama-3's 128K, Gemma's 256K) **[M]**.

**5. Vocabulary expansion + continual pretraining for a new language/domain.** *The standard industrial recipe* whenever a base model must be adapted **[V]** — dozens of national-LLM efforts (PLLuM for Polish **[V-listing]**, Komodo for Indonesian **[V-listing]**, etc.).

**6. BPE-dropout / subword regularization.** *Standard in MT, niche in LLM pretraining* **[M]**. The compute cost of losing cache-ability at LLM pretraining scale is the usual reason it is skipped.

**7. Vocabulary padding to a multiple of 64/128.** *Universal, unremarked.* Karpathy: raising nanoGPT's vocab 50257 → **50304** (nearest multiple of 64) gave "**~25% speedup**… calculates added useless dimensions but goes down a different kernel path with much higher occupancy" **[V]**. https://x.com/karpathy/status/1621578354024677377, https://github.com/karpathy/nanoGPT/blob/master/model.py
**Everyone ships dead softmax rows on purpose.** See Part C.2.

**8. Vocabulary trimming.** *Common in deployment*, near-absent in research training **[V/M]**.

**9. Entropy/learned dynamic patching (BLT, H-Net, AU-Net, dynamic pooling).** *The most active research frontier; essentially zero production deployment as of mid-2026* **[M]**. BLT has a HuggingFace `transformers` model doc **[V]**, which is the furthest any of them has got toward mainstream. The blocker is not quality — H-Net beats a 2×-parameter BPE Transformer at matched compute **[V]** — it is that the entire tooling ecosystem (KV caching, speculative decoding, structured output, logit biasing, tokenizer-level safety filters) assumes discrete tokens.

**10. Pure byte/char models (ByT5, CANINE, MambaByte).** *Used where robustness to noise or script-agnosticism dominates* — spelling tasks, OCR post-correction, low-resource scripts **[V/M]**. Not competitive on cost-per-quality for general LM.

**11. Vocabulary growth during training (your category).** *Research-stage, one or two papers.* Vocabulary Curriculum **[V]** is the only entry I found that grows a discrete vocabulary during pretraining as its central claim.

**12. Picky BPE / LiteToken-style refinement.** *Emerging.* Picky BPE is EMNLP 2024 **[V]**; LiteToken 2026 **[V]**. Neither is standard practice yet, but "don't ship intermediate residues" is becoming received wisdom.

---

# PART C — Direct comparison to this codebase

## C.1 Is minting DURING training known to be done? And what happens to trained embedding rows when segmentation shifts under them?

### C.1a Is it done?

**Yes, but rarely, and never in exactly your form.** Four families, in decreasing similarity:

1. **Vocabulary Curriculum** (A.7.1) **[V]** — the genuine match. Alternates entropy-guided vocabulary expansion with model optimization, 92 → ~18k over 5 rounds, claiming log-linear gains in vocabulary size. Small-scale GPT only. **Differences from yours:** staged/phased rather than continuous (5 expansions vs your `GROW_EVERY=200` × `GROW_BURST=6`); no probation or removal that I could verify; entropy is used for *expansion guidance*, not as a per-merge gate; and I could not verify whether the softmax is pre-allocated (your `VMAX`) or resized.
2. **Continued / incremental BPE** (A.5.4) **[V]** — merges appended to an existing table between phases, ids preserved. The 2018 NMT result that an "incremental BPE system starting from a lower vocabulary and later adding a higher vocabulary is correctly able to generate newly introduced terms" **[V]** is the earliest direct evidence that your setup is viable at all.
3. **Runtime/dynamic vocabularies** (A.4.9, A.4.10) **[V]** — units added per batch or per generation, embeddings *computed* by a hypernetwork or span encoder, never trained. They avoid your problem rather than solving it.
4. **Tokenizer swap mid-training** (A.5.2) **[V]** — one discrete change rather than continuous growth, but the measured dynamics are informative: performance dips immediately after reinitialisation, then "quickly catches up at the next evaluation interval and obtains a slight advantage during further training" **[V]**.

**What is *not* in the literature, as far as I can find:** a fixed-width softmax that a vocabulary grows into, novelty-weighted merge selection, and probation with un-merge, all in one online loop. Your combination appears novel. The individual pieces each have prior art (below), which is the honest framing: **novel assembly, mostly non-novel parts.**

### C.1b What happens to already-trained rows when segmentation shifts?

**There is no paper I found that studies this directly.** **[M for the gap claim.]** What the literature gives you is indirect and it is worth stating exactly what each piece does and does not license:

- **Your append-only invariant is the thing that saves you, and the literature agrees it is the right invariant.** Because `id2bytes` never changes meaning, a row trained on `"th"` is still a row for `"th"` after `"the"` is minted; it just becomes *rarer*. Contrast with the tokenizer-swap literature, where **[V]** "you cannot reuse embeddings from a model trained on a different tokenizer … the embedding layer no longer matches what it was trained on" — that failure comes from ids *changing meaning*, which yours never do. Your `RETOK_TAIL` justification (prefix stays valid because minting is append-only) is exactly this argument and it is sound.
- **The real cost is distributional, not semantic: rows go stale rather than wrong.** After `"the"` is minted, `"th"` collects gradient only from residual contexts, so its representation freezes at whatever it was, while the contexts that *did* update it are now routed through the new row. This is the mechanism behind Picky BPE's finding that intermediate tokens are the population most likely to be **under-trained** **[V]** and behind LiteToken's finding that residues are "frequent during merge learning … but rarely emitted" **[V]**. Note that both papers observe this in a *static* tokenizer; in yours it is happening continuously and to rows that already carry trained weight. **Your system is a stronger generator of exactly the pathology those two papers identify** — which is an argument for making C.3's extension (retire the parent) rather than an argument against minting.
- **Warm-starting from the parents is the empirically best-supported choice you could have made.** "Beyond Initialization Loss" (>20 strategies, 2026) **[V]**: "**subword composition methods outperform both vocabulary averaging and external/learned initialization**", and the best configuration is **asymmetric** — input embedding by uniform subword averaging with norm calibration, output head by **character-length-weighted** subword averaging **[V]**.
  **Two concrete, cheap improvements for you, both directly from that paper:**
  (i) You use `0.5*(emb[a]+emb[b])` for **both** `model.emb` and `model.head`. The evidence says the head wants **length-weighted** composition — i.e. `(len(a)*emb[a] + len(b)*emb[b]) / (len(a)+len(b))` — and the input wants uniform. Asymmetric init is a two-line change.
  (ii) **Norm calibration.** "A token can achieve a high logit simply by having a large embedding norm" **[V]**. A mean of two vectors has smaller norm than either parent (unless they are colinear), so your fresh rows are systematically *under-normed* relative to the live vocabulary, which biases them toward never being predicted — a self-fulfilling path to failing probation. Rescaling the warm-started head row to the mean norm of live rows is worth an A/B.
- **Your own measured result is the most relevant data point that exists**, and it deserves to be written up: masking dead rows *only at the loss* scored 6.100 b/B against 4.746 unmasked — i.e. train/eval mask asymmetry is worse than no masking. I found nothing in the literature reporting this. **[M]**
- **Your `WARMSTART_OPT` finding is also, to my knowledge, unreported**: that Adam's step counter is per-tensor so bias correction *damps* a fresh row rather than amplifying it (measured 5.4e-4 with `v=0` vs 1.0e-3 with inherited moments). That is a correct and non-obvious observation and it contradicts the folk argument for optimizer-state inheritance. **[M]** — I found no paper on optimizer state for newly added vocabulary rows.
- **The one thing the literature does say about timing** **[V]**: "too early and the tokenizer is not representative enough yet; too late may introduce other inefficiencies". That is the empirical statement of your `TOK_MINT_UNTIL` trade-off, from the tokenizer-swap paper (https://arxiv.org/pdf/2408.15793).

**Practical suggestion.** The measurement nobody has published — and which you are uniquely positioned to make — is: **track the embedding rows of parent tokens across a mint.** Log `‖emb[a]‖`, gradient norm on `emb[a]`, and its usage count, before and after `"ab"` is minted. If parents freeze at their pre-mint value and stop receiving gradient, you have the first direct measurement of the phenomenon Picky BPE and LiteToken infer statistically, and it is publishable on its own.

## C.2 Dead/unused softmax rows in the cross-entropy denominator — is masking standard?

**Short answer: no, masking is not standard — but that is because in mainstream practice the dead-row fraction is tiny (<0.1%), not because anyone has shown masking is wrong. At your fractions (measured up to 86.7%) the mainstream precedent does not transfer, and your masking is clearly correct.**

**What is standard [V]:**
- Everyone deliberately pads the vocabulary to a hardware-friendly multiple and leaves the extra rows in the softmax. nanoGPT: 50257 → **50304**, "~25% speedup … calculates added useless dimensions" **[V]**. 47 dead rows out of 50304 = 0.09%. Nobody masks them.
- Reserved/special-token slots (`<extra_id_*>`, `<|reserved_special_token_N|>`) ship unused in most modern tokenizers **[M]**. Also unmasked.
- The **consequence of not masking** is exactly the glitch-token literature: those rows never receive positive gradient, drift toward the mean unused embedding, and become detectable anomalies (Fishing for Magikarp **[V]**) and exploitable ones (GlitchMiner **[V]**).

**What the literature has instead of masking [V]:** a large body on **restricting the softmax to a candidate subset** for *speed* — "vocabulary selection, also known as lexical shortlisting or candidate selection … restrict the softmax to a subset of likely candidates given the source" **[V]**, with 4× softmax speedup / 2× overall reported for incremental selective softmax **[V]**, and SVD-Softmax needing only 5–10% of the vocabulary as candidates **[V]**. Critically, there is also a **cautionary paper**: "The Devil is in the Details: **On the Pitfalls of Vocabulary Selection** in Neural Machine Translation" (https://arxiv.org/pdf/2205.06618) **[V-listing]** — worth reading before you generalise your mask beyond never-minted rows, because the failure modes of restricting a softmax are documented there.
Note the difference in kind: vocabulary selection restricts to a *content-dependent* subset and is an approximation with accuracy risk. Your mask removes rows that **cannot ever be a correct target** — that is not an approximation, it is the correct denominator. Different operation, and the pitfalls paper's failure modes do not apply.

**Why masking is right in your setting, stated as an argument you can defend:**
1. A never-minted id has probability exactly 0 under the data distribution. Including it in `Z = Σ exp(logit_j)` charges the model `log Z` for mass it must place on impossible outcomes. That is not regularization; it is a constant-ish bias on every token's loss that scales with the dead fraction.
2. Your bits/byte numbers are only comparable across `VMAX` settings if the denominator contains the same support. Without the mask, "raise `VMAX`" and "make the model worse" are confounded — which your own note about a run "retired for having too large a vocabulary" describes happening.
3. **Your measured asymmetry result is the important one**: masking at the loss only (6.100) was worse than not masking at all (4.746). The mechanism you give is right — the model is never taught to push dead rows down, then eval scores it with them in. **The rule this establishes: a mask must be applied at every site where logits become a distribution, or not at all.** Your `mask_dead` placement (training path via `fab.society()`/`fab()`, eval via `fab_logits`) implements that.
4. **[V]** support for the underlying premise from Picky BPE: freeing/avoiding under-trained rows "leads to more efficient usage of the limited vocabulary and **embedding parameters**".

**Two cautions.**
- Masking with `-inf` and then `clone()`ing per call has a real cost at large `VMAX` **[M]**; an in-place `masked_fill_` on the pre-softmax tensor, or simply slicing `logits[..., :vocab_size]` when the live vocabulary is a prefix (which it always is, since minting is append-only and `retire` doesn't shrink `vocab_size`), is cheaper and equivalent. Your dead set *is* a suffix — `lg[..., _v:] = -inf` already exploits that. A `narrow()` would avoid the clone entirely.
- **Retired tokens are not masked, and arguably should not be** — a retired id can no longer be produced by `segment()`, so it becomes a dead row *mid-run* with a trained embedding. It sits in the denominator forever, holding whatever it learned. This is a genuine hole: `mask_dead` masks `[vocab_size:]` but `retired` ids are below `vocab_size`. Either add `TOK.retired` to the mask, or note explicitly that retired rows are deliberately left in so they can be revived. Right now the behaviour is accidental rather than chosen. **[This is an observation about your code, not a literature claim.]**

## C.3 Is there prior art for UN-MERGING or retiring a token?

**Yes — and it is stronger and more recent than you may expect. Three independent lines.**

**1. Picky BPE (EMNLP 2024) — un-merging during tokenizer training.** See A.6.3. **[V]** "removing of the intermediate tokens during tokenizer training", criterion = **IoS = pair frequency / token frequency**, "**seamlessly collects the vocabulary of the desired size without data-specific heuristics**", "**does not compromise text compression** unlike other trimming methods". This is the direct precedent for your `retire`, and — as shown in A.6.3 — **its criterion is algebraically your `p(b|a)` read in the other direction.** That correspondence is the single most useful thing in this document: it means your entropy gate already computes the statistic needed to decide what to un-merge, at zero extra cost, and you are throwing half of it away.

**2. LiteToken (2026) — retiring tokens from an already-trained tokenizer under a trained model.** See A.6.4. **[V]** Detects "intermediate merge residues" (~10% of major tokenizers), removes them, re-merges so the corpus still tokenizes, and — the load-bearing claim for you — "**because the affected tokens are rarely used, pretrained models can often accommodate the modified tokenizer without additional fine-tuning**". That is external evidence that your `retire_stale(min_use=3.0)` is safe for the model, not just for the tokenizer.

**3. Unigram LM (2018) — vocabulary as a shrinking population.** See A.1.4. **[V]** Start from a large candidate set, iteratively "remove units that have low contributions to the likelihood of the training corpus". The oldest and most principled framing: a token's right to a slot is its marginal contribution to corpus likelihood. Also **vocabulary trimming** (A.6.2) **[V]** as the post-hoc deployment version.

**Where yours is genuinely novel — and I could find no prior art at all [M]:**
- **Judging a token on *model-side* evidence rather than corpus statistics.** Picky BPE, LiteToken, Unigram and VT all judge from corpus counts. Your `TOK_PROBATION_BY=embed` test — `‖delta‖ / ‖composite‖`, "how much this token had to become that its parts did not already say" — asks the model whether the merge earned anything. **I found nothing like it.** It is a genuinely good idea and it is closely related to (but distinct from) the Magikarp unembedding-geometry diagnostic **[V]**, which measures "was this row trained" rather than "did this row need to exist".
- **A deadline as the test.** Your note that "judging only on reaching the threshold can never retire anything — the ones that fail are precisely the ones that never get there, so the deadline IS the test" is correct and, as far as I can tell, unstated anywhere. Any probation scheme in any population-management setting has this property.
- **Soft retire preserving positional ids.** Vocabulary trimming explicitly **renumbers** **[V]**; you explicitly refuse to, because `merges[]` is replayed positionally. Your design (pop from `seq2id`, keep `id2bytes`, keep the row) is the only one compatible with an online, checkpointable system, and it is the reason retirement costs you nothing but a dead row. Worth stating as a contribution.
- **Your negative result is also unreported and worth keeping**: branching entropy cannot serve as the post-mint test, because greedy longest-match consumes `a+b` into `ab` so `p(b|a)` is 0 from the instant of the merge — measured, and a re-test retired 100% of candidates. This is a clean, correct observation about the interaction of a segmentation algorithm with a segmentation criterion, and it generalises: **any criterion computed over the current segmentation is destroyed by acting on it.** Nobody hits this in the static-tokenizer literature because nobody re-measures after merging.

## C.4 Branching entropy as a merge criterion — where does it come from, what is it normally for?

**Provenance.** The chain is:
- **Zellig Harris (1955)** — the linguistic hypothesis: morpheme/word boundaries occur where the number of possible successor phonemes/letters spikes. Known as **Harris's hypothesis** or the successor-variety principle. **[V]** — confirmed via "The approach follows Harris's Hypothesis in Kempe (1999) and Tanaka-Ishii's (2005) reformulation".
- **Kempe (1999)** — entropy formulation. **[V]**
- **Tanaka-Ishii (2005, IJCNLP)** — "Entropy as an indicator of context boundaries — an experiment using a web search engine". **[V]**
- **Jin & Tanaka-Ishii, "Unsupervised Segmentation of Chinese Text by Use of Branching Entropy", COLING/ACL 2006 poster** **[V]** — https://aclanthology.org/P06-2056/ , https://dl.acm.org/doi/10.5555/1273073.1273129 . **This is the canonical citation for the criterion you implemented.**
- **Zhikov, Takamura & Okumura**, "An Efficient Algorithm for Unsupervised Word Segmentation with Branching Entropy and MDL" **[V]** — combines branching entropy with MDL; "improved on Jin and Tanaka-Ishii (2006) by adding **normalization and Viterbi-decoding**, which enabled removal of most thresholds and parameters from their model while achieving near state-of-the-art results with a simpler system" **[V]**. https://www.jstage.jst.go.jp/article/tjsai/28/3/28_347/_pdf
- **Accessor Variety** (Feng et al. 2004) **[M]** — the non-entropic sibling: count *distinct* successors rather than their entropy. **[V]** "Accessor Variety and Branching Entropy are word extraction techniques designed as intuitive statistics based on … Zellig Harris's assumptions about word boundaries." See also https://lovit.github.io/nlp/2018/04/09/branching_entropy_accessor_variety/ **[V]**.

**What it is normally used for.** **Unsupervised word segmentation of unsegmented scripts — Chinese, Japanese, Thai — and unsupervised morphology/term extraction.** It is a *boundary detector*: high `H(next|prefix)` → boundary; low → keep going. It is essentially never used as a *merge* criterion inside a BPE-style vocabulary builder. That inversion — using a boundary detector to decide what may be glued rather than where to cut — is unusual, though logically equivalent (no boundary ⇒ merge permitted).

**Modern reappearances of the same idea:**
- **Entropy-Driven Pre-Tokenization for BPE** (ICML 2025 workshop) **[V]** — "**pointwise mutual information and left/right entropy** to identify coherent character spans" as a **pre-tokenizer** feeding standard BPE, for Chinese; substantial gains in segmentation P/R/F1 over standard BPE **[V]**. https://arxiv.org/abs/2506.15889. **This is the closest published thing to what you built**, and the closeness matters: they use entropy to *constrain where BPE may merge*, exactly your gate, and they publish it as a novel contribution in 2025. Your gate is not a re-derivation of something long-solved; it is a contemporaneous instance of an active idea.
- **BLT** **[V]** and **dynamic pooling** **[V]** use *model-predicted* next-symbol entropy for the same purpose. Note the distinction stressed in A.4.4: theirs is `H(next | full context)` from a learned model; yours is `H(next | a)` from a corpus tally. Yours is much cheaper and much weaker.

**On your specific finding.** Your measured claim — that over 400 kB of English at byte level, `H(next|a)` has median 3.48 / p90 4.39 bits, a 1.5-bit gate rejects 81% of left tokens, `H` is anti-correlated with frequency, and `H` shrinks as the vocabulary merges, therefore an absolute entropy threshold is not usable and `p(b|a)` is the scale-free replacement — **is consistent with the literature's own history and I found nothing contradicting it.** Specifically:
- Zhikov et al.'s contribution was precisely **adding normalization** to remove thresholds from Jin & Tanaka-Ishii's model **[V]** — i.e. the field independently found the raw-entropy threshold unstable and fixed it with normalisation. You fixed it by switching statistic. Same diagnosis.
- BLT needed a **relative / monotonicity-breaking** criterion alongside the global threshold **[V]** — again, an absolute entropy cutoff was insufficient.
- Your `H`-is-anti-correlated-with-frequency point is the sharpest version of this argument I have seen stated, and I did not find it in any source. **[M]** Worth writing down as a result.

**One caveat to check.** `p(b|a)` is the *conditional probability of the top successor*, which is `1 - (normalized uncertainty)` only loosely. The literature's normalised alternatives are: **conditional entropy normalised by `log(successor count)`**, and **accessor variety** (distinct-successor count, threshold-free and scale-free by construction). Accessor variety in particular is nearly free for you — `len(agg[x])` in `_succ` already computes it and you discard it. It would be a one-line third gate to A/B against `p(b|a)`, and it has 20 years of segmentation literature behind it. **[V for AV's existence and rationale; [M] for the claim that it would work better.]**

## C.5 How do people add a new DOMAIN to a model whose vocabulary is already saturated?

Five approaches, in descending order of how often they are actually used:

**1. Extend the vocabulary and continually pretrain (the default).** **[V]**
Add `N` new domain tokens, grow the embedding and head matrices, initialise the new rows, continue training on a mixture of domain and replay data. Initialisation matters a lot and is the subject of an entire literature (A.5.1): **subword composition beats averaging beats external/learned init**, and asymmetric input/output init plus norm calibration is currently best **[V]**. Domain-specific token *selection* is best done by **KL divergence between the base and domain conditional token distributions** (Adaptive Tokenization, SustaiNLP 2021) **[V]** — this is a direct alternative to your novelty score `(c - seen)/(1+seen)^novel`, and the more principled one, since it measures "this domain's distribution differs here" rather than "this pair got more common".
*Failure modes:* catastrophic forgetting of the original domains; CPT length scales with extension size **[V]**; new-row embedding norms out of calibration with old rows, distorting the softmax **[V]**.

**2. Extend into *reserved* slots.** **[M]**
Modern tokenizers ship dozens-to-hundreds of `<|reserved_special_token_N|>` slots, and the padded-to-multiple-of-64 rows (Part B.7) are the same thing by accident. Repurposing them costs no tensor reallocation. **This is the mainstream analogue of your `VMAX` headroom + `GROW_CAP_VOCAB` soft cap**, and it is the argument that your design is not exotic: you have simply made reserved slots the *majority* of the vocabulary and given the run a mechanism to fill them. Your note that "the vocabulary lift is only honest with `LOSS_MASK_DEAD=1`" is the piece the mainstream gets away with ignoring only because their reserved fraction is negligible.

**3. Replace the tokenizer entirely and re-project the embeddings.** **[V]**
ZeTT hypernetwork (accuracy within 1%, 14% shorter sequences, gap closed with <1B tokens) **[V]**; training-free transplantation by **orthogonal matching pursuit** over shared-token embeddings **[V]**; WECHSEL/FOCUS **[M]**; cross-tokenizer distillation **[V-listing]**. Used when the existing vocabulary is not merely saturated but actively wrong for the target (e.g. an English BPE applied to Kazakh).
*Failure modes:* needs the hypernetwork (expensive to train, though reusable); the residual gap still requires continued training **[V]**.

**4. Extension modules rather than vocabulary edits.** **[V]**
exBERT "extends pre-trained models with domain-specific vocabulary under constrained training resources" **[V]** by adding a parallel extension module, leaving the base model's vocabulary untouched. Modern equivalent: adapters/LoRA over an extended embedding **[M]**.

**5. Don't extend — let byte fallback handle it.** **[M]**
Byte-level BPE never fails on new material, it just spells it inefficiently. Many teams accept 2–3× worse compression on a minority domain rather than touch the tokenizer at all. This is the null hypothesis your novelty-weighted minting is competing against, and it deserves to be the baseline arm in any experiment.

**How your system differs, stated honestly.**
Everything above treats "add a domain" as a **discrete offline event** performed by a human: choose tokens, resize tensors, initialise, restart training. Yours makes it **a continuous property of the run** — the tokenizer notices new material and mints for it, `TOK_MINT_NOVEL` biases minting toward it specifically, the model's headroom absorbs it without reallocation, `LOSS_MASK_DEAD` keeps the unspent headroom free, and `retire` reclaims slots from material that stopped mattering. **I found no published system that does this.** The closest in spirit is Vocabulary Curriculum **[V]** (growth during training, but scheduled and monotone, and driven by compute-efficiency rather than by domain novelty).

**Two literature-grounded criticisms of your approach to this, worth pre-empting:**
- **Your novelty score is a *recency* measure, not a *divergence* measure.** `(c - seen)/(1+seen)^novel` rewards pairs that grew since the last look. A pair that is common in *both* domains but happens to spike in a burst scores highly. Adaptive Tokenization's KL-between-conditional-distributions **[V]** is the criterion that actually isolates "this domain differs here". If you have domain labels — and `self_organize.py` does, via `asm` and `mem.src` — you could compute per-domain pair distributions and mint on divergence rather than on recency. That is a well-motivated upgrade with a citation behind it.
- **"Larger models deserve larger vocabularies"** **[V]** cuts against reserving a lot of headroom at small scale. Tao et al.'s compute-optimal vocabulary is a function of the compute budget; at your pilot scales the compute-optimal `V` is small, so a large `VMAX` is not merely "free with masking" — it is *free of loss cost* but still spends parameters, memory and the initialisation RNG. Your own audit already caught the RNG-stream confound from `VMAX`. The scaling-law paper is the citation for choosing `VMAX` rather than defaulting it.

---

## Appendix: the ten papers to actually read, in order

I could not read any of these; this ordering is my judgment of value-per-page for your specific system.

1. **BPE Gets Picky** (EMNLP 2024) — https://arxiv.org/abs/2409.04599 — un-merging during training; IoS is your `p(b|a)` inverted. Code: https://github.com/pchizhov/picky_bpe
2. **Scaling LLM Pre-training with Vocabulary Curriculum** — https://arxiv.org/abs/2502.17910 — the only real prior art for growing a vocabulary during pretraining. Find out how they init rows and size the softmax.
3. **Efficient Transformers with Dynamic Token Pooling** (ACL 2023) — https://aclanthology.org/2023.acl-long.353/ — the controlled comparison of entropy-spike vs learned vs tokenizer boundaries.
4. **Jin & Tanaka-Ishii** (COLING/ACL 2006) — https://aclanthology.org/P06-2056/ — cite this for branching entropy; plus Zhikov et al. for the normalisation fix.
5. **Tokenization Is More Than Compression** (EMNLP 2024) — https://aclanthology.org/2024.emnlp-main.40.pdf — the standing warning about bytes/token as a proxy; plus Rényi efficiency as a better diagnostic.
6. **Beyond Initialization Loss** (2026) — https://arxiv.org/abs/2608.03494 — asymmetric init and norm calibration for your `WARMSTART`.
7. **Byte Latent Transformer** (ACL 2025) — https://arxiv.org/abs/2412.09871 — the entropy-patching reference point and the global-vs-relative threshold lesson.
8. **Retrofitting LLMs with Dynamic Tokenization** (ACL 2025) — https://aclanthology.org/2025.acl-long.1444/ — minting from the live batch, with hypernetwork embeddings.
9. **Fishing for Magikarp** (EMNLP 2024) — https://arxiv.org/abs/2405.05417 — the dead-row pathology and a ready-made diagnostic for your `VMAX` headroom.
10. **Scaling Laws with Vocabulary** (NeurIPS 2024) — https://arxiv.org/abs/2407.13623 — how to choose `VMAX` on purpose.

Runner-up if you pursue the un-merge extension: **LiteToken** — https://arxiv.org/abs/2602.04706.

---

## Sources

- [Byte Latent Transformer: Patches Scale Better Than Tokens](https://arxiv.org/abs/2412.09871) · [ACL 2025](https://aclanthology.org/2025.acl-long.453/) · [Meta AI](https://ai.meta.com/research/publications/byte-latent-transformer-patches-scale-better-than-tokens/)
- [BPE Gets Picky: Efficient Vocabulary Refinement During Tokenizer Training](https://aclanthology.org/2024.emnlp-main.925/) · [arXiv](https://arxiv.org/abs/2409.04599) · [code](https://github.com/pchizhov/picky_bpe)
- [LiteToken: Removing Intermediate Merge Residues From BPE Tokenizers](https://arxiv.org/abs/2602.04706)
- [Scaling LLM Pre-training with Vocabulary Curriculum](https://arxiv.org/abs/2502.17910) · [HF paper page](https://huggingface.co/papers/2502.17910)
- [Efficient Transformers with Dynamic Token Pooling](https://aclanthology.org/2023.acl-long.353/) · [code](https://github.com/PiotrNawrot/dynamic-pooling)
- [Dynamic Chunking for End-to-End Hierarchical Sequence Modeling (H-Net)](https://arxiv.org/pdf/2507.07955) · [H-Net++](https://arxiv.org/abs/2508.05628)
- [From Bytes to Ideas: Language Modeling with Autoregressive U-Nets](https://arxiv.org/abs/2506.14761)
- [SpaceByte: Towards Deleting Tokenization from Large Language Modeling](https://proceedings.neurips.cc/paper_files/paper/2024/file/e1f418450107c4a0ddc16d008d131573-Paper-Conference.pdf)
- [Charformer / GBST](https://arxiv.org/pdf/2106.12672) · [MANTa](https://aclanthology.org/2022.findings-emnlp.207/) · [MrT5](https://arxiv.org/abs/2410.20771) · [MambaByte](https://arxiv.org/pdf/2401.13660) · [Learn Your Tokens](https://arxiv.org/pdf/2310.11628)
- [BPE-Dropout: Simple and Effective Subword Regularization](https://aclanthology.org/2020.acl-main.170.pdf) · [MaxMatch-Dropout](https://aclanthology.org/2022.coling-1.430.pdf) · [SentencePiece](https://github.com/google/sentencepiece)
- [Unsupervised Segmentation of Chinese Text by Use of Branching Entropy (Jin & Tanaka-Ishii, 2006)](https://aclanthology.org/P06-2056/) · [ACM](https://dl.acm.org/doi/10.5555/1273073.1273129) · [Branching Entropy & Accessor Variety explainer](https://lovit.github.io/nlp/2018/04/09/branching_entropy_accessor_variety/) · [Zhikov et al., branching entropy + MDL](https://www.jstage.jst.go.jp/article/tjsai/28/3/28_347/_pdf)
- [Entropy-Driven Pre-Tokenization for Byte-Pair Encoding](https://arxiv.org/abs/2506.15889) · [ICML 2025 listing](https://icml.cc/virtual/2025/47789)
- [Tokenization Is More Than Compression (PathPiece)](https://aclanthology.org/2024.emnlp-main.40.pdf)
- [SuperBPE: Space Travel for Language Models](https://arxiv.org/abs/2503.13423) · [site](https://superbpe.github.io/) · [Boundless BPE](https://arxiv.org/html/2504.00178v1) · [Faster Superword Tokenization](https://arxiv.org/pdf/2604.05192)
- [Vocabulary Learning via Optimal Transport (VOLT), ACL 2021](https://aclanthology.org/2021.acl-long.571/) · [blog](https://jingjing-nlp.github.io/volt-blog/)
- [Morfessor / unsupervised morpheme segmentation (Creutz & Lagus)](https://ufal.mff.cuni.cz/~hana/2014/docs/creutz-lagus-2007.pdf)
- [Fishing for Magikarp: Automatically Detecting Under-trained Tokens](https://arxiv.org/abs/2405.05417) · [EMNLP 2024 PDF](https://aclanthology.org/2024.emnlp-main.649.pdf) · [GlitchMiner](https://arxiv.org/pdf/2410.15052) · [AnomaLLMy](https://arxiv.org/pdf/2406.19840)
- [Efficient Multilingual LM Compression through Vocabulary Trimming](https://aclanthology.org/2023.findings-emnlp.981/) · [TextPruner](https://arxiv.org/pdf/2203.15996)
- [Zero-Shot Tokenizer Transfer (ZeTT), NeurIPS 2024](https://arxiv.org/abs/2405.07883) · [Training-Free Tokenizer Transplantation via OMP](https://arxiv.org/pdf/2506.06607) · [Model-Aware Tokenizer Transfer](https://arxiv.org/pdf/2510.21954) · [Cross-Tokenizer Distillation](https://arxiv.org/pdf/2503.20083) · [TokenAdapt / supertoken learning](https://arxiv.org/html/2505.09738)
- [Beyond Initialization Loss: Token Embedding Initialization Strategies for LLM Vocabulary Extension](https://arxiv.org/abs/2608.03494) · [HYPEROFA](https://arxiv.org/pdf/2504.21018) · [KL self-distillation vocabulary expansion](https://arxiv.org/pdf/2508.15807) · [Expanding vocabulary with 0.01GB of text](https://direct.mit.edu/coli/article/52/1/295/134270/)
- [Efficient Domain Adaptation of Language Models via Adaptive Tokenization](https://aclanthology.org/2021.sustainlp-1.16/) · [Amazon Science](https://www.amazon.science/publications/efficient-domain-adaptation-of-language-models-via-adaptive-tokenization) · [Domain Word Extension Using Curriculum Learning](https://www.mdpi.com/1424-8220/23/6/3064)
- [Teaching Old Tokenizers New Words: Efficient Tokenizer Adaptation for Pre-trained Models](https://arxiv.org/pdf/2512.03989) · [Optimizing Segmentation Granularity for NMT (incremental BPE)](https://arxiv.org/pdf/1810.08641) · [Batching BPE Tokenization Merges](https://arxiv.org/pdf/2408.04653)
- [Language Adaptation on a Tight Academic Compute Budget: Tokenizer Swapping Works](https://arxiv.org/pdf/2408.15793)
- [Retrofitting Large Language Models with Dynamic Tokenization, ACL 2025](https://aclanthology.org/2025.acl-long.1444/) · [arXiv](https://arxiv.org/abs/2411.18553) · [Generation with Dynamic Vocabulary, EMNLP 2024](https://aclanthology.org/2024.emnlp-main.1053/) · [DynaMo, NAACL 2024](https://aclanthology.org/2024.naacl-long.182/)
- [Scaling Laws with Vocabulary: Larger Models Deserve Larger Vocabularies, NeurIPS 2024](https://arxiv.org/abs/2407.13623) · [code](https://github.com/sail-sg/scaling-with-vocab)
- [Vocabulary selection / restricted softmax: pitfalls](https://arxiv.org/pdf/2205.06618) · [Attention-based vocabulary selection](https://arxiv.org/pdf/1706.03824) · [SVD-Softmax](https://proceedings.neurips.cc/paper_files/paper/2017/file/4e2a6330465c8ffcaa696a5a16639176-Paper.pdf) · [Learning to Screen for Fast Softmax Inference](https://openreview.net/pdf?id=ByeMB3Act7)
- [nanoGPT model.py (vocab padded to 50304)](https://github.com/karpathy/nanoGPT/blob/master/model.py) · [Karpathy on the 25% speedup](https://x.com/karpathy/status/1621578354024677377)
- [Data Mixture Inference from BPE tokenizers](https://arxiv.org/pdf/2407.16607) · [Beyond Text Compression: Evaluating Tokenizers Across Scales](https://arxiv.org/pdf/2506.03101) · [Which Pieces Does Unigram Tokenization Really Need?](https://arxiv.org/pdf/2512.12641)
