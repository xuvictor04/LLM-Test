# Literature check for a continual-learning LM project

Compiled 2026-08-15. Six questions, answered from primary sources fetched in full where the
full text was reachable. Every claim below is traceable to a specific paper, section, or table.

**Note on method:** I don't have sub-agent spawning in this interface, so this was done as a
single sequential pass — roughly 20 searches and full-text fetches. Anthropic's Cowork app and
the Advanced Research feature do run parallel multi-step retrieval if you want that workflow
for the next round.

---

## Read this first: the four things that contradict what you said you believe

### 1. Your bits-per-byte anchor is wrong in the direction that matters (Q5)

You've been carrying "GPT-2-small ≈ 1.0–1.2 b/B" as a single scale marker for every result.
The actual published numbers (Pile paper, Table 2):

| Corpus | GPT-2 small (124M) b/B |
|---|---|
| Pile-CC (English web) | **1.0878** |
| OpenWebText2 (English web) | **1.1111** |
| GitHub (code) | **1.7912** |
| The Pile (all 22 components) | **1.2253** |

Your remembered range is defensible **for English web text only**. It is wrong for the
aggregate (1.2253, above your ceiling) and badly wrong for code (1.7912, ~50% above your
ceiling). Worse, a 1.3B model *trained on* the Pile scores **0.5597** on GitHub — code b/B
spans a 3.2× range depending purely on training mix. There is no single number that serves as
a scale marker across web text and code. If you have been comparing a code result against a
web-text anchor, or vice versa, that comparison is invalid.

### 2. There is no per-group *phase* decoupling in the literature — but the closest paper's findings cut against your design (Q1)

Decoupled Relative Learning Rate Schedules (arXiv 2507.03526) is the nearest prior art and it
is still one global cosine curve. But its tuned values for MoE are Experts 0.3 → 1.125
(low early, high late) and Router 0.6 → 1.0. The paper's stated reason for keeping expert LR
*low* early is to **prevent early expert specialization**, which freezes the router. A
birth-anchored warmup — high LR right after an expert is born — is the opposite move. That
doesn't make you wrong, but it means your design is betting against the one tuned result in
this space.

### 3. The MoE ecology paper does not contain the ablation table you asked for, and its language results are not usable (Q2)

- The six-condition revival ablation is **not in arXiv 2605.06415**. It is deferred to a
  reference ("[14]") that has no arXiv ID and returns no search hits. It may not exist publicly.
- The balance-loss formula you asked for is **not given**. Only prose and an aggregate weight
  B = 0.40. No KL coefficient, no variance-penalty coefficient, no equation.
- The "cross-modal validation" language results report WikiText-2 perplexity of
  **33,163–37,812**. Against a ~50k BPE vocabulary, that is a model that has learned nearly
  nothing. DEAD=0 in a model that hasn't trained is not evidence about expert ecology.
- The paper's central claim (E ≥ 0.5 removes the need for balance loss) is in direct tension
  with its revival claim (balance loss is the sole essential revival mechanism), since B sits
  in the denominator of E. See file 02 for the full internal-inconsistency list.

**Bottom line on your culling question:** this paper does not license dropping your cull-and-
reseed step. Its revival evidence is 16 vision experts on TinyImageNet-200, and the supporting
ablation is unpublished.

### 4. Nobody has run your growth experiment (Q6) — because the literature varies a different axis

The growth literature (Net2Net, progressive stacking, staged training, LiGO, MSG) holds newborn
fraction at ~100% (doubling is the standard operator) and varies *when to grow* and *how to
initialize*. Gong et al.'s ablation is on **steps before growth**, not fraction. Shen et al.
tie compute saving to **stage length**. No prescribed "add at most X% of current width per
step" rule exists anywhere I could find. Your 3→4096 / 2048→4096 / fixed-2048 comparison —
same final size, same architecture, damage tracking newborn fraction — appears to be a
controlled experiment that has not been published.

---

## Where I found nothing (stated plainly, not filled in)

- **No prior art** for per-group learning-rate schedules with independent wavelength and
  independent phase anchored to group birth. (Q1)
- **No prior art** for per-source quota in a bounded shared retrieval datastore. Not one of
  your five leads implements it. (Q3)
- **No prior art** for a controlled study isolating newborn fraction from final size and total
  growth. (Q6)
- **No published bits-per-byte figures for language models in the 1M–100M parameter range** on
  a standard corpus. The Pile table starts at 124M. Gopher's family reaches down to 44M but I
  did not verify its Table A7 values within this session — flagged as unresolved. (Q5)

## Files

| File | Question |
|---|---|
| `01_per_group_lr_schedules.md` | Independent per-group LR schedules with phase |
| `02_moe_dead_expert_revival.md` | arXiv 2605.06415 full audit |
| `03_domain_isolation_bounded_store.md` | Five leads on eviction / per-source quota |
| `04_knnlm_train_vs_inference.md` | Is the datastore read during training? |
| `05_bits_per_byte_reference.md` | b/B reference table + your anchor |
| `06_growth_rate_vs_final_size.md` | Newborn fraction vs final size |
| `07_sources.md` | Full bibliography with verification status |
| `pile_bits_per_byte.csv` | Machine-readable b/B table |

---

# ADDENDUM (questions 7–12 + tangents)

Added after the first pass. **The most important finding in the entire bundle is in file 08**,
and it changes what you should do next more than anything in files 01–07.

## The headline

Your reported seed spread — 4 runs of one config over 1.227 b/B — implies **σ ≈ 0.60 b/B**.
Running your growth numbers through Bouthillier's recommended test with Noether's sample-size
formula:

| Comparison | Δ b/B | P(A>B) | Paired seeds needed |
|---|---|---|---|
| 3→4096 vs 2048→4096 | 1.375 | **0.949** | **≈ 9** |
| 2048→4096 vs fixed 2048 | 0.010 | 0.505 | **≈ 80,000** |

So: **your headline growth result is probably real and costs ~9 paired seeds to establish.**
Your secondary claim is not measurable at this σ and should be retired as a question. In my
first pass I was too pessimistic about the first and not pessimistic enough about the second.

Before spending those seeds: σ = 0.6 b/B is large enough that some of it is probably a bug or
hardware nondeterminism rather than seed variance. File 08 has the diagnostic (~5 runs).

## Other things worth knowing before you read the files

- **You may have a 4096× error in your balance loss.** The Switch loss is `α·N·Σ f_i P_i` — the
  factor of N is what makes α mean the same thing at any expert count. If it's missing, at
  4096 experts your balance floor is effectively off. File 12. Check this first; it's minutes.
- **You moved from FIFO to LRU; the caching field spent five years moving the other way.**
  Scan resistance is your flood problem, and LRU has none. Do not adopt SIEVE despite its
  popularity — its own authors state it is not scan-resistant. File 09.
- **Update rescaling under Adam is safe** — m and v depend on gradients only. But check whether
  you're also rescaling weight decay, and note that a cycle shorter than ~1/(1−β₂) ≈ 1000 steps
  never lets v equilibrate. Newborn experts are the risk case. File 13.
- **Per-source quotas do exist** — in replay-based continual learning, not in the retrieval
  literature I searched for Q3. Class-balanced reservoir sampling and iCaRL are exactly the
  thing I reported as absent. A correction to my earlier framing; see file 15, note 4.
- **Reservoir sampling guarantees your feared failure mode.** An old domain's expected buffer
  share is M·N_old/N_total → 0 under indefinite new-domain streaming. That's the answer to your
  "what happens to an old task's share" question, and it's a theorem, not an observation. File 10.
- **Your store is read during training.** That puts you in replay-based CL, not kNN-LM. Four of
  your twelve questions are the same question in four vocabularies. File 15, note 5.

## Addendum files

| File | Question |
|---|---|
| `08_seeds_and_variance.md` | Q9 — seeds. **Read first.** |
| `09_cache_eviction.md` | Q7 — LRU/LFU/ARC/2Q/LIRS/S3-FIFO/SIEVE, scan resistance |
| `10_replay_buffer_selection.md` | Q8 — reservoir, GSS, MIR, herding |
| `11_forgetting_metrics.md` | Q10 — BWT, FWT, forgetting measure, LM adaptation |
| `12_moe_aux_loss_expert_choice.md` | Q11 — Switch α, expert-choice routing |
| `13_adam_cyclical_and_rescaling.md` | Q12 — Adam correctness question |
| `14_tangents.md` | neuroevolution × backprop; online vocabulary growth |
| `15_additional_notes.md` | unrequested observations, ranked action list, open items |
