# External research brief — what to hand a session that can read papers

Written for a non-Claude-Code session (or a human) with unrestricted web access. Paste a section at a time; each one
is self-contained and states what to bring back and in what form.

---

## 0. Network status in this container (measured, 2026-08-15)

Re-measure before assuming — this changes between containers.

| capability | status | evidence |
|---|---|---|
| `WebSearch` | **WORKS** | returns titles, URLs, and snippet-level summaries |
| `WebFetch` any external host | **BLOCKED** | `EGRESS_BLOCKED` on `arxiv.org`, `www.semanticscholar.org` |
| `curl`/`pip` to package registries | works | `pypi.org`, `files.pythonhosted.org` etc. are in the proxy `noProxy` allowlist |

The egress proxy allowlists package registries and `anthropic.com` and blocks everything else, so `WebSearch` works
(it runs on Anthropic's side) and `WebFetch` does not (it dials the host directly). Check with:

```bash
curl -sS "$HTTPS_PROXY/__agentproxy/status"
```

**Consequence for this brief:** I can find papers and read *summaries of snippets*. I cannot read a paper. Everything
in section 1 below is snippet-level and should be treated as a lead, not a result. Section 2 is what actually needs
someone who can open a PDF.

**Alerting.** Blocked access is now reported rather than absorbed: any agent dispatched for research is instructed to
state `BLOCKED: <host>` in its report rather than silently substituting its own recollection. The four existing
`notes/research_*.md` files already do this correctly: every claim carries an evidence label — `[F]` fetched in full,
`[S]` search-verified (title/URL real, claim from the search engine's summary), `[M]` memory only, `[R]` derived from
this repo. Read the label before trusting the claim; the `[M]` material is recollection and the `[S]` numbers are
second-hand.

---

## 1. Already answered by search — verify, don't re-derive

### 1a. The LR schedule shape asked for has a name

The requested shape — *"start high, gradually lower, fluctuating, but lowering in the peak of the fluctuations"* — is
**cyclical LR with a decaying envelope**, and it is standard:

- **`triangular2`** (Smith, cyclical learning rates): triangular oscillation whose **maximum is halved after each
  cycle**. This is literally the described shape. It is in PyTorch as `torch.optim.lr_scheduler.CyclicLR(mode='triangular2')`.
- **`exp_range`**: same, with an exponential rather than halving envelope.
- **SGDR / `CosineAnnealingWarmRestarts`**: cosine decay with restarts; `T_mult` lengthens successive cycles. Vanilla
  SGDR restarts to the *same* peak — the decaying-peak variant is the one wanted here.

Reported rationale (snippet-level): high phases escape sharp minima and cross saddle points, low phases settle into
flat valleys, and the decaying maximum anneals so late training stabilises. Verify against the primary sources.

> **Status in this repo:** `LR_DECAY` already implements the decaying envelope over `LR_EPOCHS` wavelength with
> `LR_RESTARTS`. The open question is not *whether* to do it but section 2a below.

### 1b. Dead experts are not necessarily permanently dead

The classic argument is a rich-get-richer trap: no tokens → no gradient → worse representation → fewer tokens. Search
surfaced a 2026 MoE-ecology paper claiming the opposite empirically — dead-expert count on TinyImageNet-200 peaking at
12 around epoch 10 and falling to 4 by epoch 80, i.e. **8 experts resuscitated** — and attributing revival *solely* to
the load-balance loss (KL on routing importance + variance penalty on assignment counts) forcing periodic
re-exploration. Also claimed: `K=2` warmup then `K=2→4` gives 0% dead experts at 256 experts vs 0–6% for `K=1→4`.

This matters directly. It is the same claim as the project's evolutionary framing (*"if they contain error, ideally
they will eventually be replaced by their own new successors"*) but with a specific mechanism — **balance loss, not
culling** — as the thing that does the work. **Needs the actual paper**; see 2b.

### 1c. Eviction in agent/LLM memory is moving toward utility-aware retention

Snippet-level consensus: long-horizon memory wants *utility-aware retention, adaptive eviction, subject-balanced
allocation, retrieval-time filtering over a larger store* — and that eviction interacts with embedding retrieval
rather than with parametric forgetting. That is the direction this repo just moved in (`EVICT=lru` on retrieval
recency, `MEM_PROBE_EVERY`). Nobody found saying *write*-recency is correct.

---

## 2. What actually needs full-text access

For each: the question, why this project cares, and **the specific thing to extract**. Prefer a quote or a number
over a paraphrase — a paraphrase is what we already have.

### 2a. Per-parameter-group LR schedules that are independent of each other

**Question.** Is there prior work where different parameter groups (experts, modules, layers) run *independent* LR
schedules with independent phase — not just different *scales* (layerwise LR decay, LARS/LAMB, discriminative
fine-tuning), which are all a single global schedule times a per-group constant?

**Why.** This repo's per-expert LR is currently a per-expert *multiplier* on one global schedule, applied by rescaling
the Adam update (Adam is invariant to constant gradient scaling, so the multiplier must be applied to the update, not
the gradient). The stated goal is stronger: *"having LR Epochs as a per expert effect rather than system encompassing
is more conductive to the evolutionary learning."* That means each expert has **its own wavelength and its own phase**,
anchored to its own birth step, so experts are at different points in their exploration/consolidation cycle at the same
wall-clock step. I have found no prior art for that and want to know if it exists before building it.

**Extract:** any paper with per-group *phase*, not just per-group scale. Search terms that have not been tried:
"asynchronous learning rate schedules", "per-module cyclical learning rate", "decoupled schedules mixture of experts",
"birth-anchored warmup", population-based training with per-member schedules (PBT is the closest thing I know of and
is *not* the same — it perturbs hyperparameters across a population of whole models, not groups within one).
If it genuinely does not exist, say so explicitly; that is a useful answer.

### 2b. The MoE-ecology dead-expert-revival result

Paper: *"E = T·H/(O+B): A Dimensionless Control Parameter for Mixture-of-Experts Ecology"*, arXiv 2605.06415
(`https://arxiv.org/abs/2605.06415`, HTML at `/html/2605.06415v1`).

**Extract:**
1. The exact definition of `E = T·H/(O+B)` — what each of T, H, O, B is, and in what units.
2. The balance-loss form: the KL term on routing importance and the variance penalty on assignment counts, with
   coefficients.
3. The ablation table that identifies balance loss as the *sole* essential revival mechanism — specifically, what else
   was ablated and what happened. (This repo culls and re-seeds instead of balancing; if culling was ablated and found
   unnecessary, that is directly load-bearing.)
4. Scale: model size, expert count, dataset. TinyImageNet-200 is vision — say whether there is any LM result.
5. Whether "dead" is defined by routing mass, by gradient norm, or by something else.

**Why.** This repo culls the bottom `FAB_CULL_FRAC` and re-seeds, and has just added an LR boost for bottom-ranked
experts past their grace period. If the literature says the router's balance loss does the whole job and culling is
unnecessary, that is a cheaper mechanism and an argument that the culling machinery is solving a problem it created.

### 2c. Domain isolation in a shared retrieval store

**Question.** When one non-parametric store serves multiple domains and capacity is bounded, what actually prevents a
newly-streaming domain from evicting an older one? Specifically: is per-source *quota* (reserve N slots per domain)
used in practice, and does anyone report the failure mode where the store is technically shared but one domain has
100% occupancy?

**Why.** Measured here: after a Python run, **every** English entry was gone. The mechanism was that eviction ran on
write recency and English had stopped being written. That specific bug is fixed. The remaining question is the design
one: the user's position is *"overlap between experts is OK and expected, but having ALL experts be overlapped is the
issue"* — i.e. the target is partial, graded isolation, not a partition. Retrieval-recency eviction is one answer.
Per-source floors are another. Which does the literature actually use?

Candidate leads from search (all unread):
- *Semiparametric Language Models Are Scalable Continual Learners* / *Learn to Memorize* — arXiv 2303.01421
- *CREAM: Continual Retrieval on Dynamic Streaming Corpora with Adaptive Soft Memory* — arXiv 2601.02708
- *Selective Memory Retention for Long-Horizon LLM Agents* — arXiv 2606.29178
- *Rethinking Memory in LLM based Agents: Representations, Operations, and Emerging Topics* — arXiv 2505.00675
- *Goodtriever* — arXiv 2310.07589 (a datastore that is edited per-domain at inference)

**Extract:** for each, the eviction/retention rule in one formula, whether it is per-source, and any reported number
for cross-domain occupancy or retention after a domain stops arriving.

### 2d. kNN-LM interpolation weight, and whether memory should be read during training

**Question.** In kNN-LM and its descendants, is the datastore ever *read during training*, or only at inference? If
only at inference, does anyone discuss what that implies for a datastore that must also be *managed* (evicted) during
training?

**Why.** This is exactly the bug just fixed here: reads happened only at eval, so every during-training utility signal
was a constant and eviction silently ran on write order. If the field only ever reads at inference, then nobody has
had to confront this, and the read probe is a genuinely new requirement that comes from the store being *bounded and
online* rather than built-once-and-frozen. Worth knowing which it is.

**Extract:** whether the datastore is static in the original kNN-LM; the form of the interpolation weight λ (fixed vs
learned vs confidence-gated); anything on datastore *maintenance* over time.

### 2e. Bits/byte reference points

**Question.** Published bits-per-byte for small models on English web text and on code, at parameter counts in the
1M–100M range, measured on held-out data.

**Why.** This project reports bits/byte specifically because it is tokenizer-neutral, and currently anchors against
uniform / order-0 / order-1 and a remembered "GPT-2-small ≈ 1.0–1.2 b/B". That number is recalled, not sourced, and
everything is being judged against it. Current standing results here: **1.999 b/B** English (best), 2.276 Python,
2.681 transformer arm, with order-1 at ~3.74.

**Extract:** a small table — model, params, corpus, bits/byte, source. The Pile paper and the Chinchilla/Gopher
evaluation appendices are the likeliest sources. **If GPT-2-small's actual b/B on a comparable corpus is materially
different from 1.0–1.2, that is the single most valuable correction on this list**, because it moves the target every
result here is measured against.

### 2f. Growth schedules — the fraction-newborn finding

**Question.** In net2net / progressive-growing / expert-growth work, is there any result on the *fraction of the
population added at once* being the damaging quantity, as opposed to the final size or the total amount of growth?

**Why.** Measured here and it is the strongest result the project has: growing 3 → 4096 experts gives 3.384 b/B, while
2048 → 4096 gives 2.009 and a fixed 2048 gives 1.999. Same final size, same architecture, same seed handling. The
damage tracks *the fraction of the population that is newborn at one time*, not the size and not the growth. I would
like to know whether this is known.

**Extract:** any explicit statement about growth *rate* or newborn *fraction*, and any prescribed schedule
(e.g. "add at most X% of current width per step"). Leads: Net2Net, Progressive GANs, gradual layer stacking / MSG,
LiGO, staged training for LLMs.

---

## 3. Format to bring back

Per question: **Answer / Source (title, arXiv id, section or table) / Verbatim quote or number / Confidence /
Does it contradict what section 1 says**.

Contradictions are the most valuable output. Section 1 is snippet-level summarisation of search results, and the
`[S]`/`[M]` material in `notes/research_*.md` is second-hand or recalled — all of it reads as authoritative and none
of it has been read at the source. Say plainly when something could not be found; "no prior art located" is a result here
and it changes what gets built.
