# Q6 — Growth rate vs final size: is newborn fraction the damaging quantity?

## Answer

**No prior art found.** No published result isolates *the fraction of the population added at
once* as the damaging quantity, holding final size and total growth constant.

And there's a structural reason, which is more useful than the bare negative: **the growth
literature has never varied that axis, because nearly every published growth operator is a
doubling.** Newborn fraction is pinned at ~100% across the field. What gets varied instead is:

1. **When** to grow (stage length, step threshold)
2. **How** to initialize the new parameters (function-preserving or not)
3. **Which dimension** to grow (depth vs width vs FFN vs sequence length)
4. **How many hops** (one-shot vs multi-stage)

Your experiment varies a fifth axis nobody has isolated.

---

## What the literature actually varies

### Gong et al. 2019, progressive stacking — ablates *time*, not fraction

Doubles BERT depth by copying: layer *i* ≤ L maps to layer (i + L). Optimizer state reset at
each stage; LR carried over. Heuristic schedule: 50K steps at 3 layers, 70K at 6 layers, 280K
at 12 layers.

Their ablation examined sensitivity to **the number of steps before applying the growth
operator**, and concluded there is a threshold: switching to the larger model *before* the
threshold gave compute savings, switching after did not.

**That is a timing threshold, not a size-fraction threshold.** Newborn fraction is 100% in every
condition.

*Source: described in Shen et al., "Staged Training for Transformer Language Models,"
arXiv:2203.06211 / PMLR v162, Related Work.* **Confidence: high** (read in the citing paper's
own words; I did not fetch Gong et al. directly).

### Shen et al. 2022, Staged Training — ties savings to *stage length*

Their finding, in their words in the same section: compute saving is closely related to the
**stage length**. Transfers the entire training state — parameters, optimizer state, LR
schedule — through the growth operator. Uses loss-preserving operators and shows in Figure 3
that non-loss-preserving operators (Gu et al.'s 4x4 width-FFN growth, Gong et al.'s 2x2 depth
copy) start at higher initial loss.

**Relevant to you:** their diagnostic for growth damage is *initial loss discontinuity at the
growth event*. If your 3→4096 damage shows up as a loss spike at the growth step that never
fully recovers, that's the quantity this literature would measure. If your damage shows up
*without* an initial-loss spike, you have something they'd consider new.

### Net2Net and the function-preserving family — vary the *operator*

Net2Net expands width and depth while preserving the function, by randomly splitting existing
neurons and injecting identity layers. Bert2BERT extends the widthwise version to BERT. Lemon
adds a parameter to the split to break weight symmetry. LiGO learns a linear map from small to
large parameters. StagedGrow doubles width by concatenating two identical layers and halving
the final loss.

*Source: "A Closer Look at Model Growth for Efficient LLM Pre-Training," NeurIPS 2024
(papers.nips.cc/paper_files/paper/2024/file/143ea4a156ef64f32d4d905206cf32e1).*

**Every one of these is a doubling or a one-shot expansion.** The entire research program is
about making a 100%-newborn-fraction event survivable via initialization, not about reducing
the fraction.

### MSG (arXiv:2305.02869) — the closest thing to a granularity comparison

Masked Structural Growth notes that Bert2BERT and LiGO focus on **one-stage growth where all
dimensions expand simultaneously**, and argues each growth dimension has a different impact on
training dynamics. The NeurIPS 2024 survey above describes MSG as designed for gradual
"mini-step" growth, in contrast to their own single-step approach.

**This is the nearest published multi-hop vs one-hop comparison.** But it compares *dimensions*
being grown in stages, not *fractions of a population* per stage, and the two are confounded
with the choice of operator.

### AutoProg — learns the schedule, doesn't characterize it

Growth schedules discovered via one-shot/zero-shot proxy metrics (elastic supernets,
NTK-based condition-number statistics). *Li et al. 2022, 2024.* An automated schedule search
does not yield a "grow at most X% per step" rule, and I found none stated.

**Confidence: moderate** — this is from a secondary aggregator, not the primary papers.

---

## Is there a prescribed "add at most X% of current width per step" rule anywhere?

**No. No prior art found.** I searched the growth literature and the MoE literature and found
no such prescription in any form — not as a rule of thumb, not as a derived bound, not as a
tuned hyperparameter.

---

## The MoE side: expert-count ablations are all *static*, not growth

This matters because it's where your result could be misread. Many papers ablate "number of
experts" and find degradation past some point. **Every one of these varies the *architecture*,
not the *growth event*.** Models are trained from scratch at each expert count. They are not
evidence about newborn fraction and should not be cited as such:

- **CoSMoEs** (arXiv 2503.00245): quality increases near-linearly with total expert count
- **Graph-Integrated MCBM** (2510.00701): gains 2→8 experts, plateau beyond
- **FreqMoE** (2501.15125): degradation with more experts, attributed to frequency fragmentation
- **LadderMoE** (2510.01651): dip at 9 experts, best at 36
- **One-shot forecasting** (2601.11977): 4→8 improves, 16 slightly degrades

### The one genuine growth data point — and it confounds exactly what you separated

**Nvidia, "Upcycling Large Language Models into Mixture of Experts," arXiv:2410.07524,
Section 3.6.** Upcycled Nemotron 2B and Nemotron-4 15B from 8 experts up to 64, 128, 256, held
iso-FLOP by scaling expert hidden size down with topK.

- Nemotron 2B: 64 experts beat 8 experts
- Nemotron-4 15B: improvement **maxed out at 64**; **256 experts performed slightly worse than
  64 or 128**

Their hypothesis for the degradation: the experts were all copies, and as the count grows the
network finds it harder to reach new superior minima.

**Why this doesn't answer your question.** In going 8 → 256 they changed final size, growth
amount, and newborn fraction all at once, and every condition is a single one-shot upcycle
(newborn fraction ≈ 97% at 8→256). They attribute the damage to *copy-initialization at high
counts*, which is an initialization story, not a rate story. Your design separates these:
3→4096 and 2048→4096 have identical final size and identical architecture, differing only in
the fraction born at once.

**Confidence: high** on the numbers, **high** that the confound is present.

---

## Assessment of your result

Your measurement:

| Condition | Final experts | Newborn fraction | b/B |
|---|---|---|---|
| 3 → 4096 | 4096 | ~99.93% | **3.384** |
| 2048 → 4096 | 4096 | 50% | **2.009** |
| fixed 2048 | 2048 | 0% | **1.999** |

**What is well-supported by this design:** final size is controlled between rows 1 and 2, and
the 1.69× damage ratio is far too large to be seed noise. The claim "damage does not track
final size" is clean.

**Where I'd push back before you write it up:**

1. **Total growth is not held constant between rows 1 and 2.** Row 1 adds 4093 experts; row 2
   adds 2048. So the comparison is consistent with "damage tracks *absolute number added*" just
   as well as with "damage tracks *fraction*." To separate them you need a condition with the
   same absolute growth but different fraction — e.g. **2048 → 4096** vs **4096 → 6144** (both
   +2048, fractions 50% vs 33%), or **1024 → 3072** vs **2048 → 4096** (both +2048, fractions
   67% vs 50%). Right now fraction and absolute count are collinear across your three rows.

2. **The 2.009 vs 1.999 comparison is 0.5%** and, per file 05, plausibly within seed variance
   for a single run. It's carrying the claim that growing to 4096 is nearly free. Needs seeds.

3. **A useful third framing the literature would suggest:** damage may track the *ratio of
   newborn to mature parameters receiving gradient per step*, which in a top-k routed MoE is
   not the same as newborn fraction of the population — it depends on how routing mass
   distributes over newborns. Worth logging.

**If the fraction result survives (1), it is novel.** I found nothing like it, and the framing
"the damaging quantity is the newborn fraction, not the final size and not the total growth"
would be a genuinely new contribution to a literature that has spent six years varying *when*
and *how* to grow while holding *how much at once* fixed at 100%.
