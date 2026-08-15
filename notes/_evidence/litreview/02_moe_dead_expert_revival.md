# Q2 — arXiv 2605.06415, "E = T·H/(O+B)": full audit

**Zhang Qingjun** (single author). School of Integrated Circuits, Wuxi Taihu University,
Dept. of Communication Engineering. arXiv:2605.06415v1 [cs.LG], submitted 7 May 2026.
HTML version dated 26 May 2026. Code: github.com/zqj323/expert-ecology

**The paper is real and I read it in full.** Below, each of your five sub-questions, then a
credibility section you should read before acting on any of it.

---

## (a) Definition of E and each of T, H, O, B, with units

**Eq. 1 / Eq. 2:**

```
E = T · H / (O + B)
```

| Symbol | Definition (Section 3.2) | Units as stated |
|---|---|---|
| T | routing softmax temperature; higher T → softer routing, more exploration | **none given** |
| H | routing entropy loss weight | **none given** |
| O | oracle supervision weight (pushes router toward a teacher signal) | **none given** |
| B | load balance loss weight (KL divergence from uniform routing) | **none given** |

**The paper gives no units for any of the four.** "Dimensionless" is asserted in the title and
abstract, never derived. This is not a nitpick: T is a temperature in logit space, while H, O
and B are auxiliary-loss weights whose units are [total loss]/[component loss]. T·H/(O+B) is
not dimensionless under any consistent assignment. Treat E as a heuristic ratio, not a
dimensionless group in the Reynolds-number sense the Discussion claims.

**A concrete failure of the formula.** The paper's own recipe (Section 5, Practical engineering
implications) is: set λ_o = 0, choose T and H so that E ≥ 0.5, let experts self-organize. And
the abstract says E ≥ 0.5 removes the need for load-balancing auxiliary losses. But if O = 0
*and* B = 0, then E = T·H/0 — undefined. Every reported experiment has B > 0 (values 0.40 and
0.85 in Table 4). The claim "no auxiliary load-balancing loss is needed" is never actually
tested; B is nonzero throughout.

**Confidence: high.** This is arithmetic on the paper's own equations.

---

## (b) The balance-loss form, with coefficients

**Not in the paper.** This is the single biggest gap relative to what you asked for.

Section 4.7 gives prose only: the balance loss (B = 0.40) combines a KL-divergence term on the
routing importance distribution with a variance penalty on expert assignment counts.

That is the entire specification. There is:
- no equation for the balance loss,
- no coefficient on the KL term,
- no coefficient on the variance term,
- no statement of how the two are weighted relative to each other,
- only the aggregate weight B = 0.40.

Section 2 attributes the KL-to-uniform form to Shazeer et al. 2017 (reference [1]), so the KL
component is presumably the standard sparsely-gated-MoE importance loss. The variance penalty
on assignment counts is not attributed and not defined.

If you need the actual formula, you would have to read the repo at
`github.com/zqj323/expert-ecology`. I have not verified that the repo exists or contains it.

**Confidence: high** that it is absent from the paper. I searched the full text.

---

## (c) The ablation table identifying balance loss as the sole essential revival mechanism

**Not in this paper.** Section 4.7 and the Discussion both defer it:

> a systematic six-condition ablation study, "reported separately in [14]"

Reference [14] is: *Q. Zhang. Expert revival: Dead experts can resuscitate in hierarchical
mixture-of-experts. arXiv preprint, 2026.* **No arXiv ID.** I searched for it directly and it
returns no hits — no abstract page, no listing, no citation by any other work. Same for
reference [15] (*Prototype orthogonalization causes dead experts…*), also "arXiv preprint,
2026" with no ID.

**What the parent paper claims the ablation found (unverifiable):**

| Component | Verdict |
|---|---|
| **Balance loss** (weight 0.40) | **Sole essential mechanism.** Without it: DEAD stalls at 12, zero recovery over 80 consecutive epochs |
| Divergence loss | individually non-essential |
| Temperature annealing | individually non-essential |
| Routing entropy | individually non-essential |
| Prototype vectors | individually non-essential |

Six conditions = baseline + five removals, presumably. Revival is claimed to proceed in every
condition where balance loss is present.

**What this means for your culling design.** You asked: if balance loss alone does the job, is
culling unnecessary? The honest answer is that **this paper does not establish that**, because:
1. The load-bearing ablation is unpublished and possibly nonexistent.
2. The revival evidence is 16 experts on a 200-class vision task (Table 7: DEAD 12 → 4 over
   epochs E10 → E80).
3. The paper itself reports that scaling *up* expert count makes things worse, not better —
   see (d).

Do not drop culling on the strength of this. If you want to test it, the cheap version is a
single run at your scale with balance loss on and culling off, and check whether bottom-ranked
experts recover routing mass on their own.

**Confidence: high** that the ablation is not publicly available.

---

## (d) Scale, expert count, dataset, and whether there is any language result

**There are language results.** Your suspicion that it's vision-only is wrong on the facts —
but right in effect, because the language results are unusable.

### Architecture (Section 3.1)
- **Vision:** WideResNet-28-10 encoder → 256-d features → MoE heads
- **Language:** GPT-2 style Transformer, **8 layers, 512 hidden, 8 heads**, RoPE, MoE FFN layers
- **Router:** two-layer MLP 256 → 128 → 16, top-2 softmax gating
- **Experts:** 16 total (tiers 8:4:4 or 4:4:4:4); one 32-expert run (16:8:8)
- Batch size 128 vision / 64 language. AdamW, LR 1e-4 encoder, 1e-3 experts+router

### Datasets
CIFAR-10, CIFAR-100, TinyImageNet-200 (vision); WikiText-2, WikiText-103 (language).

### The language results (Table 3, E = 0.545, 16 experts top-2)

| Dataset | ortho | **PPL** | DEAD | Active |
|---|---|---|---|---|
| WikiText-2 BPE | 0.00 | **35,041** | 0 | 16/16 |
| WikiText-2 BPE | 0.02 | **33,493** | 0 | 16/16 |
| WikiText-2 BPE | 0.05 | **35,737** | 0 | 16/16 |
| WikiText-2 BPE | 0.10 | **33,163** | 0 | 16/16 |
| WikiText-2 BPE | 0.20 | **37,812** | 0 | 16/16 |
| WikiText-103 | 0.00 | **6,918** | 0 | 16/16 |

**This is the finding you should take away.** A uniform distribution over a ~50k GPT-2 BPE
vocabulary gives perplexity ≈ 50,257. These models are at 33k–38k. They are barely above
chance. A competent small LM on WikiText-2 lands in the tens. So "DEAD = 0 across all language
runs" is a statement about models that have not learned the task — the router had no signal
strong enough to concentrate on any expert, which is exactly the condition under which no
expert dies. It is a null result presented as cross-modal validation.

WikiText-103 at PPL 6,918 is better but still far outside any usable range, and Section 4.8
describes it as severe overfitting — on WikiText-103, which is 103M tokens. That framing is
itself suspect.

**Expert revival is vision-only.** Table 7 (TinyImageNet-200) is the sole revival trajectory.
No language revival is reported.

### Scaling behaviour — directly relevant to your 4096-expert setting

Table 6, attempted fixes for TinyImageNet-200 collapse:

| Configuration | E | Experts | Top-1 (E40) | DEAD (E40) |
|---|---|---|---|---|
| Baseline | 0.545 | 16 | 33.41% | 7 |
| Raise E | 1.000 | 16 | 27.19% | 7 |
| **More experts** | 0.545 | **32** | **26.99%** | **25** |

Doubling experts from 16 to 32 took DEAD from 7/16 to **25/32** and *lowered* accuracy. The
paper's own Limitations section concedes it does not test 100+ experts or billion-parameter
scale. You are at 4096. Nothing here extrapolates to you, and the one scaling data point
present points the wrong way.

**Confidence: high.**

---

## (e) How "dead" is defined

**Routing mass, on the test set. Not gradient norm.**

Section 3.3, the six-category ecology taxonomy is a lookup on usage (U) and accuracy (A):

| Category | Usage | Accuracy |
|---|---|---|
| PURE_CORE | ≥ 3% | ≥ 50% |
| BROAD_CORE | ≥ 3% | 30–50% |
| WEAK_CORE | ≥ 3% | < 30% |
| EDGE | 1–3% | ≥ 25% |
| NOISE | 1–3% | < 25% |
| **DEAD** | **< 1%** | **any** |

So DEAD = an expert receiving under 1% of top-1 test-set routing, regardless of its accuracy or
its gradient. Measured during a standard evaluation pass, at a fixed evaluation temperature.

Two consequences worth noting for your own metric design:
- The threshold is **absolute (1%)**, not relative to uniform. At 16 experts, uniform is 6.25%,
  so DEAD means <16% of fair share. At your 4096 experts, uniform is 0.024% — every expert
  would be "DEAD" by this definition. **The taxonomy does not port to your scale at all.**
- Section 4.11 finds routing is temperature-invariant across a 50× scan (T ∈ [0.1, 5.0]) —
  logits so peaked that temperature can't change the top-2. The paper calls this "routing
  lockdown." If you measure occupancy at a different temperature than you train at, this paper
  says the ecology numbers still hold but the accuracy numbers do not.

**Confidence: high.**

---

## Credibility assessment — read before citing

I would not cite this paper as evidence for a design decision. Reasons, in rough order:

1. **Load-bearing citations are to nonexistent works.** [13] is a GitHub repo. [14] and [15]
   are "arXiv preprint, 2026" with no IDs and no search presence. The revival ablation — the
   exact thing you need — is in [14].

2. **Internal contradiction on the central claim.** Abstract: E ≥ 0.5 removes the necessity of
   load-balancing losses. Section 4.7: balance loss is the sole essential revival mechanism.
   B appears in the denominator of E, so raising B lowers E. The paper simultaneously argues
   that the balance term is unnecessary and that it is the only thing that works.

3. **The language validation is a null result.** PPL 33k–38k, addressed above.

4. **Version drift in the claims.** The arXiv v1 abstract says 12 experiments (8 vision, 4
   language), 11,000+ epochs. The HTML says 18 experiments, 17,000+ epochs. The contribution
   list grew from 6 additional findings to 13.

5. **Thirteen numbered contributions from a single-author 16-expert study**, several of which
   are framed as firsts ("first empirical documentation of spontaneous tier collapse", "first
   documented case of reversal of the MoE death spiral").

6. **Reference [19] is Hartle & Hawking, "Wave function of the universe," Phys. Rev. D 28:2960
   (1983).** It is not cited anywhere in the body text I read. Its presence in the bibliography
   of an MoE paper is a signal about how the reference list was assembled.

7. Author contact is a QQ address; no institutional email; no evidence of peer review.

None of this makes the empirical observations false. TinyImageNet expert revival may well be
real. But the paper cannot bear the weight of a design decision about culling at 4096 experts.

---

## Findings from this paper that are still worth your attention

Setting credibility aside, two observations are cheap for you to test and would matter:

- **Warmup is optional (Section 4.9, Table 8).** Four conditions on CIFAR-100 all reach DEAD=0.
  No-warmup showed *milder* peak collapse (9 vs 13) and *faster* recovery (E60 vs E80). If you
  use random-routing warmup for newborn experts, this is a free ablation.
- **Overfitting is decoupled from ecology (Section 4.8).** Whether or not the WikiText-103 run
  supports it, the claim that expert health and generalization are orthogonal diagnostic axes
  is a useful hypothesis to hold — you can have healthy occupancy and bad b/B simultaneously,
  so don't use occupancy as a proxy for progress.
