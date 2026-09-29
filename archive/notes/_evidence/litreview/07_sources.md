# Sources, with verification status

Legend:
- **[FULL]** — I fetched and read the full text (or the full HTML/PDF extraction) in this session
- **[PARTIAL]** — I read abstract + search excerpts only
- **[CITED]** — I only saw it described inside another paper I read
- **[UNVERIFIED]** — I could not reach it; nothing in this bundle depends on it
- **[NOT FOUND]** — searched for, does not appear to exist publicly

---

## Primary sources read in full

**[FULL]** Zhang Qingjun. *E = T·H/(O+B): A Dimensionless Control Parameter for Mixture-of-Experts
Ecology.* arXiv:2605.06415v1 [cs.LG], 7 May 2026 (HTML dated 26 May 2026). Wuxi Taihu University.
→ https://arxiv.org/abs/2605.06415 · code: github.com/zqj323/expert-ecology
Used for: Q2 (all parts). See file 02 for credibility caveats.

**[FULL]** Peng, Ge, Chen, Wei, Wang. *Semiparametric Language Models Are Scalable Continual
Learners.* arXiv:2303.01421**v1**, Mar 2023. Peking University / Microsoft.
→ https://arxiv.org/abs/2303.01421
Note: **v2 (17 Jul 2026) is retitled** *Learn to Memorize: Scalable Continual Learning in
Semiparametric Models with Mixture-of-Neighbors Induction Memory* (Peng, Ge, Luo, Li, Wang) —
different author list, different method (MoNIM as a learnable FFN-like bypass layer). Your two
names for this ID are two versions.
Used for: Q3 (SeMem), Q4 (λ calibrator, static store).

**[FULL]** Son, Kang, Kim, Ho, Kang, Lee, Yoon. *CREAM: Continual Retrieval on Dynamic Streaming
Corpora with Adaptive Soft Memory.* arXiv:2601.02708v1/v2, Jan 2026. KDD '26.
DOI 10.1145/3770854.3780281 · code: github.com/DAIS-KU/CREAM
Used for: Q3 (per-cluster radius pruning — the most transferable mechanism in the bundle).
Not read: Appendix A.9 "Qualitative Analysis of Memory Dynamics."

**[FULL]** Pranath Reddy. *Selective Memory Retention for Long-Horizon LLM Agents.*
arXiv:2606.29178v1 [cs.AI], 28 Jun 2026. Also OpenReview id 9JiPHfleLn.
Used for: Q3 (TraceRetain — only lead with a real capacity bound).

**[FULL]** Pozzobon, Ermiş, Lewis, Hooker. *Goodtriever: Adaptive Toxicity Mitigation with
Retrieval-augmented Models.* arXiv:2310.07589, Oct 2023. EMNLP Findings 2023
(aclanthology.org/2023.findings-emnlp.339). Cohere For AI · code: github.com/for-ai/goodtriever
Used for: Q3 (two-store partition, five-domain continual experiment), Q4.

**[FULL]** Ludziejewski, Małaśnicki, Pióro, Krutul, Ciebiera, Stefaniak, Krajewski, Sankowski,
Cygan, Adamczewski, Jaszczur. *Decoupled Relative Learning Rate Schedules.*
arXiv:2507.03526v1 [cs.LG], 4 Jul 2025. University of Warsaw / IDEAS NCBR.
Used for: Q1 (the nearest prior art, incl. Tables 2–5 and Appendix A).

**[FULL]** Gao, Biderman, Black, Golding, Hoppe, Foster, Phang, He, Thite, Nabeshima, Presser,
Leahy. *The Pile: An 800GB Dataset of Diverse Text for Language Modeling.* arXiv:2101.00027,
Dec 2020. EleutherAI. → https://pile.eleuther.ai/
Used for: Q5 (Tables 1–4, Section 3.1 bpb conversion). **The authoritative source for your anchor.**

---

## Partial

**[PARTIAL]** Hübotter et al. *Efficiently Learning at Test-Time: Active Fine-Tuning of LLMs.*
arXiv:2410.08020, Appendix A Table 2. Used only as a secondary aggregation of Pile b/B across
larger models. Its GPT-2 124M figure (1.241) differs slightly from the Pile paper's 1.2253 —
prefer the primary.

**[PARTIAL]** He, Wang, et al. *Upcycling Large Language Models into Mixture of Experts.*
arXiv:2410.07524, Section 3.6 + Figure 10. Nvidia. Used for Q6 (8→256 expert upcycling).

**[PARTIAL]** Shen, Walsh, Tu, Zaheer, Hajishirzi, et al. *Staged Training for Transformer
Language Models.* arXiv:2203.06211 / PMLR v162. Used for Q6 (stage length; Related Work's
descriptions of Gong et al. and Gu et al.).

**[PARTIAL]** *Masked Structural Growth for 2x Faster Language Model Pre-training.*
arXiv:2305.02869. Used for Q6 (multi-hop vs one-hop growth framing).

**[PARTIAL]** *A Closer Look at Model Growth for Efficient LLM Pre-Training.* NeurIPS 2024.
Used for Q6 (taxonomy of Net2Net / Bert2BERT / Lemon / LiGO / StagedGrow / StackedBert).

**[PARTIAL]** *Sequential Bayesian Neural Subnetwork Ensembles.* arXiv:2206.00794, Appendix G.
Used for Q1 (global cyclic exploration/exploitation LR — the cycle *shape* precedent).

**[PARTIAL]** Rae et al. *Scaling Language Models: Methods, Analysis & Insights from Training
Gopher.* arXiv:2112.11446, Appendix D.2 + Table A7. **Flagged as the open item for Q5** — the
likeliest source of sub-100M-parameter b/B values, not yet read.

**[PARTIAL]** MoE expert-count ablations cited in Q6 as *not* answering the question:
CoSMoEs (arXiv:2503.00245), Graph-Integrated MCBM (2510.00701), FreqMoE (2501.15125),
LadderMoE (2510.01651), one-shot price forecasting (2601.11977), DOT-MoE (2606.01666).

---

## Cited but not read directly

**[CITED]** Khandelwal, Levy, Jurafsky, Zettlemoyer, Lewis. *Generalization through Memorization:
Nearest Neighbor Language Models.* ICLR 2020 (arXiv:1911.00172). The original kNN-LM. My Q4
answer rests on three independent secondary descriptions (SeMem §6, Goodtriever App. A,
SeMem v2 abstract), not on the original. **If Q4 is load-bearing for you, read it directly.**

**[CITED]** Gong et al. 2019 (progressive stacking); Gu et al. 2021 (CompoundGrow);
Chen et al. 2022 (Bert2BERT); Wang et al. 2022 (LiGO); Li et al. 2022/2024 (AutoProg);
Chen et al. 2016 (Net2Net). All via Q6 secondary sources.

**[CITED]** Sun et al. 2019 (layerwise LR decay); Howard & Ruder 2018 (discriminative
fine-tuning); Everett et al. 2024 (arXiv:2407.05872, per-layer LR); Hayou et al. 2024 (LoRA+);
Yang et al. 2022 (Tensor Programs V / muP). All via RLRS §5.

**[CITED]** Shazeer et al. 2017 (sparsely-gated MoE, KL balance loss); Fedus et al. 2022
(Switch); Lepikhin et al. 2021 (GShard); Zhou et al. 2022 (expert choice); Zoph et al. 2022
(ST-MoE); Wang et al. 2024 (auxiliary-loss-free balancing, arXiv:2408.15664).

---

## Not found

**[NOT FOUND]** Q. Zhang. *Expert revival: Dead experts can resuscitate in hierarchical
mixture-of-experts.* Cited as "arXiv preprint, 2026" (ref [14] of 2605.06415) with **no arXiv
ID**. Returns no hits on direct search — no abstract page, no listing, no third-party citation.
**This is the paper containing the six-condition ablation you asked for in Q2(c).**

**[NOT FOUND]** Q. Zhang. *Prototype orthogonalization causes dead experts in hierarchical
mixture-of-experts.* Ref [15] of 2605.06415, same situation.

---

## Not reached

**[UNVERIFIED]** arXiv:2505.00675 — *Rethinking Memory in LLM based Agents.* The one Q3 lead I
did not get to. Nothing in this bundle depends on it.

---

## Open items, ranked by value to you

1. **Gopher Table A7** (arXiv:2112.11446) — for the sub-100M b/B anchor. One fetch.
2. **arXiv:2505.00675** — the fifth Q3 lead.
3. **github.com/zqj323/expert-ecology** — the only possible route to the actual balance-loss
   formula and the six-condition ablation.
4. **Khandelwal et al. 2020 directly** — if Q4 is load-bearing.
5. **CREAM Appendix A.9** — possible cross-domain occupancy numbers.
