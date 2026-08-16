# 02 — IDEAS

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are tiny
> — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has reached
> 1.227 b/B (`33a9299`), larger than the gap between any two architectures ever compared here.
> Several confidently-stated findings were later retracted when the measurement turned out to be
> broken. Every entry records **what was observed under these conditions**, never **what is true**.
> Where a result was later invalidated, the invalidation is stated next to it, not in a footnote.

---

## What this file is

Section **A**: **the researcher's own ideas**, in his own words, and what became of each one.

This is not a history of the project and it is not a list of Claude's suggestions. Every entry
starts from something the researcher said. Where Claude proposed something and the researcher
merely approved it, that is not an entry here — it belongs in
[`notes/03_EXPERIMENTS.md`](03_EXPERIMENTS.md). Where the researcher *corrected* a Claude proposal,
that is an entry, and the correction is the idea.

### Sources and how quotes were verified

- **Primary**: `notes/_evidence/chat/user_turns.md` — 455 numbered turns, `U0001`..`U0455`,
  verbatim. **Every quote below was located in that file** by literal substring search, and the
  turn id is printed beside it so a reader can check it.
- **Secondary**: `notes/_evidence/chat/extracts/chunk_01.json`..`chunk_12.json` — 12 structured
  extractions covering 2026-07-21 .. 2026-08-15 with no gap (354 ideas, 210 retractions, 301
  errors, 346 tested items). These supplied the candidate list and most of the outcome evidence.
  They are second-hand and were **not** trusted for wording.

**Two caveats on the primary source, found while verifying:**

1. **Nine of the 455 "turns" are not the researcher.** `U0032`, `U0082`, `U0147`, `U0177`, `U0264`,
   `U0309`, `U0370`, `U0417`, `U0448` are auto-compaction summaries written by Claude and injected
   into the conversation as user turns. They quote the researcher extensively, so a naive search
   finds his words there too. No entry below cites one of them as the source of a quote. Genuine
   researcher turns: **446**.
2. **`AskUserQuestion` answers are not in `user_turns.md` at all.** Several early and consequential
   statements — including the north-star wording (2026-07-21), the LR-wavelength clarification
   (2026-08-11) and the 2026-08-14 mid-run-expansion note — were given through that tool and
   survive only in Claude's paraphrase or in `handoff/`. Those entries are marked
   **[quote unconfirmed]** and are paraphrased, not quoted.

**Verification result.** Of the 354 extracted quotes, **26 could not be located in any genuine
researcher turn**. All 26 are `AskUserQuestion` answers, tool-answer placeholders, or a quote the
extraction had stitched across two separate turns. **None of the 26 is reproduced as a quotation
below**: they were dropped, paraphrased under **[quote unconfirmed]**, or (in the culling case,
`A48`) split back into two separately cited turns. The remaining 328 all verify.

### Consolidation

354 raw extracted ideas are consolidated into **103 entries** (`A01`..`A103`), citing **164 distinct
researcher turns** and **216 verified quotations**. Near-duplicates and repeated pushes
on one theme are merged into a single entry that shows how the idea developed and **how many times
it was raised**. The raise count is itself evidence: an instruction given seven times over five
days is a record of it not being followed the first six.

### Verdicts

| verdict | meaning |
|---|---|
| **VINDICATED** | the record supports the call, usually against Claude's stated position at the time |
| **REFUTED** | tested, and it did not hold |
| **OPEN** | built or partly built, never settled by a measurement that survives `05_ERRORS.md` |
| **NEVER IMPLEMENTED** | agreed to, designed, or approved — and no code ever ran |
| **UNCLEAR** | the record does not settle it. Written where that is true, rather than guessing |

### Precedence — cited, never re-derived

- [`notes/01_TIMELINE.md`](01_TIMELINE.md) — the commit spine and the 15 epoch boundaries `E1`..`E15`.
- [`notes/03_EXPERIMENTS.md`](03_EXPERIMENTS.md) — `X01`..`X56`, `O01`..`O16`.
- [`notes/05_ERRORS.md`](05_ERRORS.md) — the invalidation list `INV-01`..`INV-44`. **Authoritative.**
- [`notes/04_RESULTS.md`](04_RESULTS.md), [`notes/06_CONTINUAL_LEARNING.md`](06_CONTINUAL_LEARNING.md),
  [`notes/07_WIP.md`](07_WIP.md), [`notes/08_GLOSSARY.md`](08_GLOSSARY.md),
  [`notes/09_COMMENT_AUDIT.md`](09_COMMENT_AUDIT.md), [`notes/LITREVIEW_FINDINGS.md`](LITREVIEW_FINDINGS.md).
- [`notes/10_HISTORY_FINDINGS.md`](10_HISTORY_FINDINGS.md) already covers **retractions, process
  failures and repeated instructions** drawn from the same transcript. This file does not repeat
  it. Where a thread here is a process finding there, it is cross-referenced and left alone.

---
---

# Phase (i) — 2026-07-21 .. 07-22 · Verification / reconstruction

## A01 — A handoff folder where the filename is the index, one idea per file

**2026-07-21** · `U0003` · raised 4x on the day

> "Ask any questions that may be present. I will present it to the prior context. Lets add a
> separate folder in the repo, for workflow, as context changes and exchanged" — `U0003`

> "Ask me again later. I want the prior context to answer any questions before I jump in to modify
> anything" — `U0004`

**Reading.** Chat context is the scarce resource; the repo, not the conversation, has to carry state.

**Response.** `handoff/` created (`153dc17`), 24 files, grown to 59 by `4f7f1cf`; nested by kind
(`decisions/`, `design-directions/`, `open-questions/`, `process/`, `designed-but-not-built/`), one
idea per file, filenames long and descriptive. The prior chat's four consolidated documents were
explicitly *not* kept as one file.

**Outcome.** **VINDICATED as process.** `DOC_PLAN.md` names the handoff tree as "the researcher's own
framing — quote it, do not paraphrase", and `07_WIP.md` reads `handoff/designed-but-not-built/`
(7 files) and `handoff/open-questions/` directly. It is the only 2026-07-21 artefact still load-bearing.

---

## A02 — The north star, and growability as the sacred invariant

**2026-07-21** · **[quote unconfirmed — delivered via `AskUserQuestion`; no matching human turn]**

**Reading (paraphrased, from `handoff/NORTH_STAR.md`, written the same day and marked `[USER]`).**
A model that learns and reasons, much smaller than conventional models, with an ever-expanding,
updatable knowledge base. When compromises come, **expansion and growability are not to be lost**.
Language is a personal benchmark, not the endpoint. Long-horizon: pluggable multimodality, and a
dashboard that streams the thinking. From scratch for novelty and ownership, not necessity.
Success priorities: conversation > sentence generation > characterized architecture > shipping.

**Response.** `handoff/NORTH_STAR.md` + `STATE.md` §1 "SACRED INVARIANT" (`12a4fcd`). Multimodality
and the dashboard filed under `designed-but-not-built/`.

**Outcome.** **NEVER IMPLEMENTED as a measurable target.** No metric in the project scores
growability. `06_CONTINUAL_LEARNING.md` records exactly one run bearing on the second goal
(`X49`, `a9d7258`, n=1), against dozens on the tokenizer and the expert population. The one place
the invariant did bite is `A28` below — the refusal to freeze anything.

---

## A03 — A redundant, interchangeable base out of which subspecialties emerge

**2026-07-21** · `U0007`, `U0009` · raised 2x

> "The growth and interchangeability is, for me, important, since there is a risk of incorrect
> removal , but also the fact that many tasks, when broken down are similar, and allow
> flexibility." — `U0007`

> "On the interchangeability, ideally, subspecialties will emerge, for specific tasks, breaking
> things down" — `U0009`

**Reading.** Not redundancy *or* modularity. Both: a redundant base, with specialisation as an
emergent property of task decomposition rather than an imposed partition.

**Response.** `handoff/design-directions/interchangeable-base-with-emergent-subspecialties.md`
(`c8705a8`). No code that day. Everything from `A38` onward is downstream of it.

**Outcome.** **OPEN.** The SPECIALIZATION instrument reads 0.000 in almost every run; its first
non-zero value is 0.094 (`fcdfaa7`) and its best 0.135. `X46` tested population *size vs growth*,
never interchangeability vs specialisation. `08_GLOSSARY.md` records "interchangeable" as a term
whose measurement was never settled.

---

## A04 — Subcontracting: no expert solves the whole task

**2026-07-21** · `U0010`

> "I don't want the full task to be done alone. Ideally it is subcontracted in a sense, and spread
> out, via the router base." — `U0010`

**Reading.** A direct rejection of the independence loss, which trained each expert to solve the
whole task alone.

**Response.** Documented as revising the independence-loss premise (`628dfc5`, the `SUBCONTRACTED`
glossary entry). **The independence loss in `self_organize.py` was never changed.** The idea was
realised later and by a different route — the society, then the chained society (`A46`).

**Outcome.** **OPEN.** `X49`'s six-expert fabric contributing +0.373 b/B is the closest thing to
evidence for it; `X24` ("every chaining arm is worse than `FABRIC=0`") is the closest thing against.

---

## A05 — "Sense" means a modality, not a word sense

**2026-07-21** · `U0010`, `U0014` · raised 2x, the second a correction

> "Senses should be integrated via the lowest tokenizer layer, and "discovered" when unknown or
> unusual inputs are recieved, before reconciliation, and understanding" — `U0010`

> "Sense was supposed to be a separate thing, where currently it is built as an LLM, but multimodal
> in and output can be created. Ie I attach a mic to the system, giving it a new sense" — `U0014`

**Reading.** Claude had conflated "sense" with polysemy. Correction: a sense is a perceptual
channel.

**Response.** Definition moved into `designed-but-not-built/multimodality-pluggable-avenues.md`;
the polysemy concept re-parked under a provisional name ("Meaning") that the researcher never
confirmed. Claude: *"thank you for the Sense correction, that's a meaningful one I had wrong."*

**Outcome.** **NEVER IMPLEMENTED.** No modality other than bytes has ever entered the system.

---

## A06 — The knowledge base: memory + retrieval + a polysemy-aware editable embedding

**2026-07-21** · `U0007`

> "The knowledge base would be a combo of current memory system and built in retrieval, where I'm
> thinking of a complex tokenizer embedding system, that's capable of editing and knowing which
> vector if there are multiple meanings" — `U0007`

**Response.** Filed as a design direction. No implementation.

**Outcome.** **NEVER IMPLEMENTED** for the polysemy half. The memory half exists and is
net-negative: `X54`, `INV-06`, and `06_CONTINUAL_LEARNING.md` — memory contributed **−0.111 b/B** in
the one continual-learning run, and every English entry had been evicted by the end of it.

---

## A07 — Tool-experts: experts that end in a script the system wrote itself

**2026-07-21** · `U0011`

> "Another add: is some "experts" can end in a tool call/pre established scripts (but capable of
> being created by the system itself if done often enough)like a token" — `U0011`

**Reading.** The same crystallise-on-repetition primitive as token minting, applied to procedures.

**Response.** `handoff/design-directions/experts-can-be-tool-calls-or-scripts-crystallized-on-repetition.md`
(`b1e6d1f`). No code. Raised again on 2026-08-06 as "ways to replace an expert with a fixed line of
code" (`A61`), and again not built.

**Outcome.** **NEVER IMPLEMENTED.**

---

## A08 — The router as an embedder

**2026-07-21** · `U0011`

> "Maybe routers can act like embedders, taking an input (and source), modification, then embedding
> to determine which expert is most similar, or from learned recognition, allowing it to transfer to
> prior unknown parts" — `U0011`

**Reading.** Routing by similarity in a learned space is what buys transfer to inputs never seen.

**Response.** `keystone_probe.py` (`5cad71a`). The "modification before embedding" step became
cross-content transfer coding. Measured on a synthetic CPU toy, **n=1**: op-purity **0.803**
(functional) vs **0.500** (surface), chance 0.20.

**Outcome.** **OPEN.** The probe supported the keystone; it was never integrated into the real
router in that form. The idea reappears in its strongest form as `A47` (router predicts weights),
which *is* the branch this whole document sits on.

---

## A09 — One primitive underneath every layer: subtokenize → embed → match

**2026-07-21** · `U0011`

> "Much of the ideas involve some sort of subtokenization, to find the right target" — `U0011`

**Response.** Filed explicitly as "HYPOTHESIS to test, not a decision" (`b1e6d1f`). Never probed.

**Outcome.** **NEVER IMPLEMENTED.**

---

## A10 — Surprise is a learning driver, not a truth signal

**2026-07-21** · `U0012`

> "Surprise was supposed to be a mechanic to facilitate the ongoing learning" — `U0012`

**Reading.** The subsystem then called "B" had miscast surprise as a wrongness detector. That
category error, not a tuning problem, is why its precision was ~1%.

**Response.** `decisions/surprise-is-a-learning-driver-not-a-wrongness-or-truth-signal.md`
(`4315c94`); B renamed to Verification. Claude conceded it "gently corrects my last turn, where I
leaned on surprise for the new-vs-wrong call".

**Outcome.** **VINDICATED against Claude's stated position at the time.** The reframe drove the
whole Verification redesign (`A11`).

---

## A11 — Reverse embedders: verification by reconstruction

**2026-07-21** · `U0012`, `U0013`; rescue attempt 2026-07-24 `U0090` · raised 3x

> "Reverse embedders, a part of it, for a certain level of thought, verification, or training" — `U0012`

> "Let's rename B. Perhaps this classification of reconstruction and surprise is needed for the
> learn signals and times / First make sure everything is documented, and the handling set. / Then
> let's build and test." — `U0013`

> "A compromise I am willing to make: the reverse encoder was supposed to help train the system and
> detect places where it went wrong. We can have two paths: reinforce this, probably increasing the
> amount of training for those associated experts. Or adjust it, and have a decompositional back
> pass from the encoder" — `U0090`

**Response.** `verification.py` Reconstructor + `verify()` (`fbdcd50`). Standalone: `X01`/`X02`
AUC 0.978 / 0.980, precision@1% 100% (n=1). In the product loop: `X03` 0.3–0.5% precision across
three runs. `X04` ran 5x the steps and ruled out undertraining as the explanation. Both rescue
paths were refuted the same evening — path 2 algebraically (unit-norm `tcode` makes the
reconstruction-error ranking identical to an LM head), path 1 statistically (0.26% base rate,
AUC ~0.55), and the refutation cited an AUC figure `STATE.md` had already retracted.

**Outcome.** **REFUTED in the loop** — `INV-38`: the standalone AUC stands, the integration failed
at 0.3% precision, and the 100%@1% was an FPR≈0 projection. Retained as a per-candidate check. `VERIFY` defaults to
`selfcon` at HEAD and `07_WIP.md` records that whether the Reconstructor is still reachable is an
open question — no run since 2026-07-22.

---

## A12 — Reject a strict per-domain memory quota

**2026-07-21** · `U0015`

> "I don't like a strict per domain quota. The system sounds like it will break something. Likely,
> a better way is if memory burden is near, the domain can be expanded in terms of experts, possibly
> retrain the experts, or a sign as domain splitting is needed" — `U0015`

**Reading.** A hard quota fights growability (`A02`). Pressure should be a growth signal, not a wall.

**Response.** The quota was rejected: the design file was git-mv'd into `designed-but-not-built/`
and rewritten (`5c711cf`).

**Outcome.** The rejection **stands**; the replacement mechanism (memory pressure → grow / retrain /
split) is **NEVER IMPLEMENTED**.

---

## A13 — The naming pass, and the one rename that did not stick

**2026-07-21** · `U0014`

> "Verification sounds better than V / Yes let's split fabric to the two. I won't use it anymore. /
> Population naming sounds good / Let's keep domain" — `U0014`

**Response.** Bulk rename across the docs (`3500b78`): B → Verification, "Fabric" retired in favour
of Router + Compositor, expert grades kept, "Domain" kept. Code identifiers deliberately left alone.

**Outcome.** **REVERSED IN PRACTICE.** "Fabric" is the term the code, the harness, `runs.csv` and
every other note in this set use. `08_GLOSSARY.md` records the Router/Compositor split as retired.
The B → Verification rename stuck.

---

## A14 — Commands must work from a phone, on a box that did not exist ten minutes ago

**2026-07-21 .. 07-22** · `U0019`, `U0024`, `U0027` · raised 3x

> "Never mind, I made it public for now, but I want the git to be through the python console so I
> can copy and paste when on mobile" — `U0019`

> "Send test message, default to bash unless I specify python" — `U0024`

> "For the bashes, assume I am starting clear, since sometimes I need to terminate the cloud GPU" — `U0027`

**Response.** Self-cloning console block, then a bash default, then a fresh-box preamble in
`COMMANDS.md`; it also forced the fix of a dead hardcoded `cd ~/overarching-package` in two
launchers (`9c6661a`).

**Outcome.** **VINDICATED as process** — these became standing rules for the rest of the project,
and the whole GPU workflow (`A34`) depends on them.

---

## A15 — The runs are too short for the negative results to mean anything

**2026-07-22** · `U0029`

> "To a certain extent, I still like the idea of memory, being native to the system, to be useful.
> If this is not the right course, that is ok. I am concerned, however, that some results may be
> misleading since the runs are so short." — `U0029`

**Response.** A 5x-steps run (`STREAM_LEN=30000000`, ~22 min), `X04`.

**Outcome.** **MIXED, and both halves are informative.** Memory held or improved (+2.117 b/B at
that scale); Verification stayed at 0.3%, refuting undertraining as its excuse. The run also
surfaced the memorization gap moving +0.046 → +0.249. The instinct was right about *one* of the two
negatives, and the experiment is what separated them.

---
---

# Phase (ii) — 2026-07-23 .. 07-25 · World model, performance, GH200 readiness

## A16 — Use a real corpus from HuggingFace

**2026-07-22** · `U0033`; the 40 GB fetch 2026-07-25 `U0127`

> "Why not use a set of data from hugging face?" — `U0033`

> "Provide me a script to download the 40G that we wanted, so I can initiate this, for the multi
> epoch later." — `U0127`

**Response.** Claude conceded it had framed HF as a fallback: *"It's the primary path."*
`fetch_big.py` streaming FineWeb-Edu / C4 / Pile; then `fetch_40g.sh` and a resumable fetch
(`c46a32f`) — which exposed that `fetch_big.py` always reopened `part000` and re-streamed from
doc 0, so a failure at 30 GB would have silently overwritten everything.

**Outcome.** **VINDICATED.** Every corpus in `runs.csv` is HF-streamed. The 40 GB set was fetched
(79 shards) and **the run it was fetched for never happened** — see `A63`.

---

## A17 — Checkpointing: the most-repeated instruction in the record

**2026-07-23 .. 2026-08-14** · `U0036`, `U0037`, `U0048`, `U0053`, `U0055`, `U0298`, `U0427` ·
**raised at least 7x over 23 days**

> "I am surprised that we stopped checkpointing. The estimates given are always wrong and longer
> than expected. Is there a way to inject code to pause and force checkpoint?" — `U0036`

> "No, I consider this as stopping checkpointing, because the end as a checkpoint doesn't really
> count. […] If the data is stored on the system, it must be retrievable, I believe" — `U0037`

> "I am still quite upset that the checkpoints were not saved in the last run , while this is
> ongoing, how long should it take?" — `U0048`

> "You keep on turning off checkpoints, so we cant do it yet." — `U0427`

**Response.** `CKPT_EVERY` mid-run saves (`9a049fc`); a `SIGUSR1` handler (`4bc56a5`);
`rescue_ckpt.py` (`ad6f69e`) — which **failed twice**, `pyrasite` silently no-op'ing and `gdb
PyRun_SimpleString` hitting SIGSEGV in `libcuda.so.1` because CUDA releases the GIL. Claude:
*"the cooperation has to come from the code."* Later `.best` tracking (`3f67bfc`, prompted by
`U0298`), and finally `SEED_CKPT` default 0 → 1 (`e0dbf0c`) on 2026-08-14.

**Outcome.** **VINDICATED, repeatedly and expensively.** A full day of H100 was lost to a run that
saved nothing. `SAVE_CKPT=0` wrote checkpoints to a directory literally named `0`, and it got
committed (`7ca2061`, `05_ERRORS.md` §9). On 2026-08-12 Claude conceded every grid command it had
handed over used `GRID_CKPT=0`: *"Nothing we ran this session can be added to."* **The one real
continual-learning run in the project (`X49`) was only possible because he forced the default
change two days later.** See also `10_HISTORY_FINDINGS.md` for the process side.

---

## A18 — The vocabulary is capped at 1k and minting stops after seeding

**2026-07-23** · `U0049`

> "As this is going on, I want to address: why is tokens only 1k? This is a hard limit. Second, I
> wanted tokenization to be ongoing, but reports make it seem like it's only occurring at the
> beginning" — `U0049`

**Response.** Traced: 1024 was `SEED_VOCAB`, `VMAX` was the real cap, and minting did run every
step. Only the *reporting* was missing; a `[tokenizer @ step] vocab N/VMAX` line was added.

**Outcome.** **REFUTED as stated** — but the missing instrument was real, and every vocabulary
figure quoted after this date exists because of the question.

---

## A19 — Active learning: self-generated reference, then reproduce closed-book

**2026-07-23** · `U0050`

> "a sort of active learning, where once we reach a certain level, the system generates like such:
> a reference article, followed by a prompt, then reproduce the output without the reference. Do not
> write code yet." — `U0050`

**Response.** Documented (`8143537`). Designed once more on 2026-07-24 with four coherence gates
(G1–G4, described as ~10 lines each) and a recommendation to retrieve a real passage rather than
generate the reference. Never coded.

**Outcome.** **NEVER IMPLEMENTED.**

---

## A20 — Partial compartmentalization: provenance without partition

**2026-07-23** · `U0050`; revisited 2026-08-15 `U0445`

> "Another thing I realized is a question is compartmentalization of information, as context is
> being used, some information may be relevant to different aspects, and to partially (not fully)
> isolate. Allowing things to mix is important for creativity." — `U0050`

**Reading.** Deliberate leakage — a middle position between independence and blending.

**Response.** Realised as per-expert memory **WRITES** with **global READS** (`242e021`) — see `A33`.

**Outcome.** **REFUTED at the scale tested, and for a reason nobody intended.** `INV-06`:
`MEM_PER_EXPERT` read `_i(...,1)` against a comment saying DEFAULT OFF, so **every run in the
project used the partitioned store**, measuring −0.555 b/B against global. The isolation test
(`X54`) attributes only −0.058 of that to the partition and −0.497 to the capacity cut — the design
was nearly free, the way it was configured was not.

---

## A21 — A general, physics-like, multimodal world model, with the same selection dynamics as everything else

**2026-07-23 .. 07-24** · `U0060`, `U0062`, `U0067`, `U0072` · raised 4x

> "Also, part of what I wanted, but don't know if fully expressed, is a world model built within the
> system" — `U0060`

> "Build the world model as a general world model.  Not of its own situation. I wanted integration of
> other modalities. This would require a physics like model. […] Maybe it is all 3" — `U0062`

> "As a requirement, does the learning model have a similar selection capacity that we have in the
> rest of the system?" — `U0067`

> "Physics does not necessarily have to be the target, as long as it is simulating the world in a
> real sense. Is there anything more for the world model?" — `U0072`

**Reading.** Two separate corrections in sequence: (a) Claude proposed a model of the system's own
internal dynamics; the researcher wanted a model of external reality; (b) it must grow, route and
cull like the rest of the system, not sit as the one static net.

**Response.** `world_model.py`, a JEPA/VICReg-style latent forward-dynamics core reading observation
embeddings (`39c6765`, `b6c0076`, `74d10d8`); then `DynamicsPopulation` — routed, fitness-tracked,
grow-on-plateau, soft-cull (`2cf106d`); then the feedback link into the LM (`a1767b7`).

**Outcome.** **OPEN, and stale.** `X05`: the honest negative — routed population **−5.1%** against a
param-matched monolith. `X07`, the first full-stack reading (`51889b7`, 2026-07-29): beats baseline
by −84.7% with **latent std 0.07**, i.e. by its own criterion it had not learned dynamics.
**It defaults ON and has not been measured since.** `INV-39` records it as not a working subsystem
on its own printed criterion; `07_WIP.md` carries it as an open question.

---

## A22 — Every run so far has been under one epoch

**2026-07-23 .. 07-24** · `U0062`, `U0065` · raised 2x

> "If the generation time is not enough, it may be a false negative result. I'll wait for it for a
> bit." — `U0062`

> "Now for the evaluations. They should be robust and reasonable. […] is it vastly undertrained?
> Because I thought we need to run them for a few epochs." — `U0065`

**Response.** Verified in code: the training loop did a single pass; there was **no epoch loop**.
`fw_small` was ~0.2 epochs at its 100k checkpoint. Claude: *"every run we've done has been under one
epoch… the evaluation has been invalid."* `EPOCHS=N` was built and smoke-verified.

**Outcome.** **VINDICATED.** Everything from `X30` onward, including the entire LR finding (`A54`),
depends on the epoch mechanism this question produced.

---

## A23 — It is GPU-bound on the reverse encoders; do not remove them; confirm before acting

**2026-07-24** · `U0068`

> "I'm pretty sure it's not cpu bound since I've seen (and have told the other context) that it's gpu
> bound, due to the reverse encoders. I don't want to get rid of it, but you are allowed to think of
> ways around it. I must confirm before action." — `U0068`

**Response.** A per-component profiler (`PROFILE=1`) was built rather than argued about. It
overturned Claude's unprofiled "CPU-bound" claim: **encoder (contrastive) 87% | memory key+write 4% |
lm fwd+bwd 4%**.

**Outcome.** **MOSTLY VINDICATED.** The Reconstructor proper was off (`VERIFY=selfcon`) and
contributed zero, so the specific attribution was wrong; the encoder family was the bottleneck, and
Claude recorded that *"the user's instinct that the ENCODERS were the problem was the closest."*
The confirm-before-action constraint was honoured throughout.

---

## A24 — "I asked for no compromise" — do not buy speed by removing function

**2026-07-24** · `U0073`, `U0074`, `U0075` · raised 3x, including one retraction of his own

> "Let's fix the sig encoder. Do the domains do anything? Let's put it in standstill, and disable.
> / Why are we adding everything to the key?" — `U0073`

> "I asked for no compromise, but what you did was exactly that, by removing sections and only using
> "tested and approved". That isn't what I asked for." — `U0074`

> "Yes, let's build the amortized rekey. Perform the other fixes if possible. And make sure that the
> domains are not disabled, since I was running on the assumption that they weren't used" — `U0075`

**Reading.** The middle message is the idea. The third is the researcher withdrawing his own
disable-domains instruction from the first once he learned domains were live.

**Response.** Claude conceded fully and rebuilt with equivalence-preserving fixes: amortized rekey
(`REKEY_AMORTIZED=1`, a rotating cursor spreading the same whole-store re-encode) and a shift-gated
encoder. Smoke-verified with 38 live domains still assembling (`98e3a54`).

**Outcome.** **VINDICATED as a standing constraint.** It is the rule that later blocked
`REKEY_CHUNK` and `AMP=bf16` on measurement (`X13`) rather than on taste.

---

## A25 — Send several agents at it rather than reasoning about it

**2026-07-24, 2026-08-13, 2026-08-15** · `U0069`, `U0412`, `U0444` · raised 3x

> "I don't know if it is just the reverse encoder. I think it would be nice if you did a few agents
> trying to do a few different things to see what is the case and what would fix the issue, without
> compromising anything, and telling me the options." — `U0069`

> "Send out an agent, to see if there may be a bug." — `U0412`

**Response.** 2026-07-24: a 5-agent profiling workflow (292k subagent tokens, 28 min) returning a
ranked list of drivers. 2026-08-13: three agents with distinct hypotheses, two of which found the
`FROZEN` RNG re-roll and the still-live `_due` double-call (`A72`). 2026-08-15: four literature
agents (`A81`).

**Outcome.** **VINDICATED.** Two of the project's largest findings (`INV-31`, the VMAX
non-attribution, and the `_due` predicate class in `05_ERRORS.md` §3) came out of agent dispatches
he asked for. One counter-example is recorded honestly: on 2026-07-27 he asked
*"The tasks have been going on for a while. I'm a bit concerned check up on them."* (`U0150`) and the
container had been reclaimed — the workflow was **dead, not slow**, and Claude's "~2 more hours"
estimate was wrong.

---

## A26 — Build the disk-streaming loader first

**2026-07-24** · `U0079`

> "Disk streaming loader sounds good and important let's build it first" — `U0079`

**Response.** `datastream.py` `MmapConcat`, probe-verified drop-in correct (300 random slices
byte-identical to read-all-into-RAM), integrated behind `DISK_STREAM=1` with per-epoch fresh
resampling (`eae40ca`).

**Outcome.** **BUILT.** It is what makes `EPOCHS>1` mean new data rather than a byte-identical
replay — a distinction that later mattered for the anti-overfitting reading (`A62`).

---

## A27 — GPT-2 is the benchmark, for training size and for quality

**2026-07-24** · `U0078`

> "Lets prep the test for the multi epoch then, and see what we can do. Our rough benchmark is GPT 2,
> in terms of training size and quality" — `U0078`

**Response.** The honest gap was stated rather than papered over: ~29M params vs GPT-2's 124M; an
in-RAM stream capping at ~100–150M tokens vs GPT-2's ~8B; ~2.0 b/B vs ~1.0.

**Outcome.** **OPEN.** The anchor stayed in use for a month. `LITREVIEW_FINDINGS.md` later revised
the GPT-2 bits/byte figure itself — one of three external claims that changed a project reading.

---

## A28 — "Does the multi epoch test contain everything?" — the audit thread

**2026-07-24 .. 2026-08-11** · `U0100`, `U0101`, `U0108`, `U0125`, `U0171`, `U0172`, `U0204`,
`U0208`, `U0210`, `U0389` · **raised at least 10x over 18 days**

> "This sounds good so far, however, I must know. Since I've been burned on this a few times: does
> the multi epoch test contain everything? Full scale with surprise, experts, reverse, tokenizer,
> constant learning capacity, checkpoints, pause optionality, etc… ?" — `U0100`

> "Yes please, otherwise the multi epoch test would be a waste, since it would not be testing our
> actual system, and reproving existing llm architecture works. Something that we already know." — `U0101`

> "I want to fix all issues before a full multi-epoch, with some preliminary testing, and affirmation
> that we are doing it with full feature activity" — `U0125`

> "Change defaults to have things on. Since things were off in prior tests, do we need a rerun?" — `U0172`
> *(sent three times, `U0172`/`U0173`/`U0174`, after two 529 API errors)*

> "I suspect much more is broken or not working as intended. Go through everything again please" — `U0204`

> "Triple check stuff if they are broken. I'm not sure everything is done. It must be completely
> thorough. I don't want any issues." — `U0208`

> "Tell me what is on (and off) before I do the run" — `U0389`

**Response.** Each raise produced a fresh audit and each audit found something. `535f5f6` (five
criticals + five startup CONFIG WARNING guards), `7a42f90` (`FABRIC=0`), `51889b7` (five more
subsystems off), `4869559` (`MEM_CAP` silently cut 24x), `3440634` (the `[config] SUBSYSTEMS /
SELECTION / OFF ON PURPOSE` banners), `6f4c534` (the 279-knob `_SPEC` registry).

**Outcome.** **THE MOST VINDICATED IDEA IN THE RECORD.** It is the direct cause of `INV-01`
(`D_MODEL_B` unread — every earlier benchmark at d=128), `INV-02` (`FABRIC=0` in every run),
`INV-03` (`PHASED` never once executed), `INV-05` (`MANAGE_EVERY` exceeding the run) and `INV-22`
(the signature encoder characterising 42% of the stream, found on the pilot-readiness raise).
Claude's own verdict on the first one: *"Your instinct to ask was correct."*
And the thread is not closed: the tenth raise (`U0389`, 2026-08-11) still turned up four
default-behaviour changes meaning *"base today is not the old base"*.

---

## A29 — The expert count is far too low

**2026-07-24, 2026-08-03** · `U0100`, `U0105`, `U0200` · raised 3x

> "I hope and expect to see a large increase in experts (upon initial sight) to occupy the different
> subspecialties emerging, and new domain. This would be an ultimate test." — `U0100`

> "128 was arbitrary, but I did not expect experts to be such a low count. We may need to clarify on
> what is an expert, since I imagined it as series of layered neural networks." — `U0105`

> "I don't understand why experts is capped at 64, my expectation is much higher. Thousands or even
> millions. Selection at a scale of tens is pointless." — `U0200`

**Response.** The audit answered *"EXPERT GROWTH EXPECTATION MET: NO"* — growth was loss-plateau
only, and `FAB_NMAX=6-8` allowed three events total. Then sparse top-k and `FAB_NMAX` 8→64
(`9b05bd3`, `020c157`); then the node form itself changed — `FabricNode` became a low-rank d→r→d
adapter, 2.36M → 12.3k params, `FAB_NMAX` default 4096 (`2e3a464`), with `society(top-4)` latency
at N=65536 falling 345.2 ms → 15.2 ms.

**Outcome.** **VINDICATED as a scale change, REFUTED as a quality lever.** One reading along the way was itself
void: *"1 of 4096 experts used"*, which drove four router fixes, was a 32-window eval probe
(`INV-17`; whole-run: 84 distinct experts, top 3.9%). `X46`, the cleanest
experiment in the project: arm B (`FAB_GROW=0 FAB_N0=2048`) **1.999 ± 0.080** vs arm D (ramp 3→4096)
**3.384 ± 2.074**. The population can be large; ramping *to* large is what breaks. And `04_RESULTS.md`
records that **the default configuration at HEAD is arm D**.

---

## A30 — Grow on unexpected worsening, in bursts, and do not re-arm until progress stalls

**2026-07-24** · `U0105`, `U0102` · raised 2x

> "Why just stall? Not when unexpected worsen? ( brief burst, which will result in some worsening,
> but not resetting till stall)" — `U0105`

> "Also, I was rethinking the statement about the delayed growth. I want to see rapid initial
> growth." — `U0102`

**Response.** Claude: *"you're more right than I said"* — worsening already passed the plateau test;
the binding limit was the rate cap. Built exactly as specified: WATCH (loss above a slow EMA by z
robust MAD deviations) → BURST → RECOVER → WATCH, plus `note_shift()` so retokenisation and epoch
resampling do not masquerade as distribution shifts. First attempt fired once and stalled (Claude's
own bug: RECOVER min 600 > ramp cadence 50); fixed, then verified 3 → 57/64 experts (`020c157`).

**Outcome.** **BUILT, then implicated.** The ramp **never latched off** (`ff0f0fa`) — culling held
the population just under the cap forever, refilling every cull within 187 steps. And the ramp is
precisely the arm-D behaviour `X46` found fatal. `07_WIP.md`: `FAB_NEW_FRAC=0.04` and `FAB_BURST=1`
were added to bound it and **have never been measured at pilot scale**.

---

## A31 — What is an expert, actually? Re-explain the node

**2026-07-24** · `U0105`, `U0107` · raised 2x

> "Re explain what a node is, and how it works, and what it interacts with. I want to re evaluate
> this idea" — `U0107`

**Response.** Claude ran an empirical gradient check rather than reading the docstring, and found
**the entire routing apparatus inert** — `keys`, `qproj`, `q_entry`, `halt_key`, `nov`, `ctrl` all
"no grad". Conclusion: *"The fabric as documented is an interesting adaptive-depth architecture. The
fabric as configured is a soft mixture with a clustering router."* Led directly to the `ROUTE_LEARN`
bilinear fix.

**Outcome.** **VINDICATED.** A request for an explanation found a defect. This pattern recurs —
`A40`, `A48`, `A52`, `A60`, `A72`, `A83` are all the same shape: a question about how something works,
answered by finding that it did not.

---
---

# Phase (iii) — 2026-07-25 .. 07-29 · The domain-assembler campaign

## A32 — Domains overlap naturally and should self-assemble; the four seeded corpora are a scaffold

**2026-07-25 .. 07-31** · `U0144`, `U0160`, `U0171`, `U0188`, `U0189` · **raised 5x**

> "Domain was a question from original building, where it was classified, as the four domains, where
> I questioned whether it should be as such […] My view was these domains are naturally overlapping,
> and instead make it self assembling" — `U0144`

> "Let's rehash the ideas of domain. Why are we going to 4? More or less domains do not matter too
> much for me. I'm inclined for more, to reflect sub specialization." — `U0160`

> "Not why domain at all? But why the 4 domains when we are doing English only. We can keep the
> domains, since I expect some to appear within the English only environment" — `U0188`

> "No, domains are not a major concern for me. […] The end all is the resulting output, and capacity
> for continual learning without exorbitant forgetting […] The domains are only a concern because you
> have been driving it up, and improperly interpreting it." — `U0189`

**Response.** `efb818a` reframed the metric to RECURRENCE and relabelled V-measure "vs the 4 SEEDED
corpora (a SCAFFOLD, not the target)"; `9d90416` put output and retention above the domain scores
and marked domain/clustering numbers "DIAGNOSTICS, not targets"; `5e02cfc` retracted the
"domain assembly works, 0.54→0.96" headline once purity was shown to rise monotonically with
fragmentation (`INV-16`; `INV-37` separately voids the A/B/C/D V-measure ranking). Claude conceded: *"I drifted into optimizing V-measure against the four seeded labels."*

**Outcome.** **VINDICATED.** `04_RESULTS.md` carries both retractions. The cost is the finding: the
campaign that this idea corrected was **the largest single block of work in the project**, and its
target was wrong the whole time.

---

## A33 — Per-expert memory: a small quota counted in entries, ranked by last use

**2026-07-24, re-opened 2026-08-15** · `U0102`, then `U0447` · raised 2x, three weeks apart

> "Also, a note on the memory, I believe that it should be keyed such that each expert has their own,
> and they have a max quota. Not in terms of bytes or bits. It should be in number of entries. Since
> I expect a large number of experts, their max should be relatively low, possibly 16 to 128 max
> entries. (Ranked on when last utilized)" — `U0102`

> "Use based recency is better I think." — `U0447`

**Response, 2026-07-24.** `MEM_PER_EXPERT` / `MEM_QUOTA` with owner×quota+slot addressing,
argmax-routed ownership, write-partitioned / read-global, checkpoint persistence with in-place
restore (`242e021`, `ef412e2`). A new `last`/`tick` LRU clock was added specifically because
`mem.use` was a decayed count, not a timestamp.

**Response, 2026-08-15 — and this is the entry.** Reading `memory.py` after his own eviction
complaint (`A82`) established that: `owner` is an argmax-routed expert folded `%64`, **not** a
domain; `src` is never consulted in eviction; `last` was **WRITE**-recency, because `mem.read()` was
only ever called from `generate()` and `bpb_true()`; and `use` was **0 for every entry during
training**. Claude's summary: *"Every eviction rule claiming to rank by utility was ranking a
constant."* Fixed by `MEM_PROBE_EVERY` / `MEM_PROBE_N` — cadenced real retrievals during training
on a deterministic stride — and `EVICT=lru` redefined as least-recently-**retrieved** (`daf9f89`).

**Outcome.** **VINDICATED, and the entry is the three-week gap.** The specification was given on
2026-07-24 in one sentence. It was not actually in force until 2026-08-15, and nothing in between
noticed, because the store reported plausible numbers the whole time. Caveat: the literature review
returned the same day flagged **LRU-on-retrieval as precisely the scan pathology this system
exhibits** — unresolved. See `X54`, `INV-06` (every memory result in the project), `INV-24` (no
eviction policy ever selected anything, because `use` stayed 0), `06_CONTINUAL_LEARNING.md`.

---

## A34 — GPU access is intermittent; say what must run there, and I will run it

**2026-07-30 .. 2026-08-11** · `U0179`, `U0181`, `U0252`, `U0355`, `U0356`, `U0397` · **raised 6x**

> "Although I plan on using a GH200, I wont always be using it, so if something must be run there,
> let me know." — `U0179`

> "I am running. Your CPU smoke is taking longer than what I think the GPU would take." — `U0181`

> "Yes, but my point is, you take too long, it is better for me to do it for you." — `U0252`

> "I can run the tests. Send it to me. My system is likely faster" — `U0355`

> "You are saying no gpu, but if it is faster with a gpu, let's do it, since it's available anyways" — `U0356`

**Response.** A `probe.pt` sidecar so the geometry probes stopped needing an 18 MB checkpoint
(187 KB at D=64, `80a4533`); the smoke stream cut 40 kB → 12 kB with CUDA auto-detect, 10 arms in
253 s instead of ~20 min (`7de037d`); a standing instruction to stop running the gate locally; and
from 2026-08-11 the researcher ran every pilot and uploaded the logs.

**Outcome.** **VINDICATED as process, and it is why the evidence base looks the way it does.**
`03_EXPERIMENTS.md` notes that all but the `equiv_*` pair of the 481 logs under `runs/` predate
2026-08-08 — **every GPU result from then on exists only in commit messages and `runs.csv`**,
because they were produced on a machine this repo never saw.

---

## A35 — Do not optimise for our arbitrary metrics; if a metric disagrees with the system, suspect the metric

**2026-07-27 .. 2026-08-12** · `U0161`, `U0189`, `U0289`, `U0290`, `U0406` · **raised 5x over 16 days**

> "As a reminder, I don't want to optimize for our arbitrary metrics. Their use is only as proxies […]
> If a metric isn't working, but the system itself is improving, that does not mean the system is at
> wrong, but the metrics and how we are using them" — `U0161`

> "What are we optimizing for right now? Remember, the ultimate goal is textual, not arbitrary
> metrics." — `U0289`

> "Output quality will always trump other metrics. They, however are useful for my design sake." — `U0290`

> "the final goal is for language, not optimizing specifically the tokenizer, vmax, or different ways
> to freeze the structure . I need to be able to carry and build off the results we get" — `U0406`

**Response.** The 2026-07-27 raise produced the 14-section report audit (`c316813`) that found
`PHASED` had never been run. The 2026-08-05 raise produced Claude's concession *"I have been
optimizing mechanism, and it is not paying"* and the observation that the run with the best routing
diversity produced the second-worst text while `nofabric` was within 0.06 b/B of the best. The
2026-08-12 raise produced the checkpoint concession in `A17`.

**Outcome.** **VINDICATED AND REPEATEDLY NOT FOLLOWED.** Five raises is the finding. The correction
was needed again each time because the intervening work had drifted back onto whatever was
measurable. See `10_HISTORY_FINDINGS.md` for the process account; the point here is that the
researcher identified the failure mode on 2026-07-27 and it recurred four more times.

---

## A36 — Non-stationarity is the whole point; why is it off?

**2026-07-28** · `U0162`

> "Why is non stationary off? I thought forgetting was essential" — `U0162`

**Response.** Claude: *"There is no good reason. Nobody ever questioned it, including me."*
`PHASED` flipped to default 1 with a warning on `PHASED=0`, and two latent bugs fixed
(`PH_BOUNDS` accumulating across epochs; the retention metric's stationarity assumption) — `a5ac033`.

**Outcome.** **VINDICATED.** `INV-03`: `PHASED=0` shipped in commit 1 and was never once turned on,
so **every number before 2026-07-28 is void as evidence about continual learning**. The project's
stated target had never been switched on. See `06_CONTINUAL_LEARNING.md`.

---

## A37 — Add the instruments that are missing, and keep adding

**2026-07-28 .. 07-29** · `U0163`, `U0164` · raised 2x

> "Add the metrics you think is missing, there's probably more, but we can include as we go along." — `U0163`

> "Build the two, then let's follow up" — `U0164`

**Response.** ANCHORS (uniform / order-0 / order-1) and COHERENCE (`aac17f7`); then the per-process
LEARNING CURVE with ACTIVE/ABSENT columns and `probe_stability.py` (`01c1cd3`).

**Outcome.** **BUILT — and three of the instruments were themselves defective.** `05_ERRORS.md` §7:
the order-1 anchor was first fitted on the held-out text (`aac17f7`); coherence was a four-sample
statistic from which three mutually contradictory claims were drawn (`6f24bed`, `INV-20`); the completeness
formula was homogeneity (`b1fe6ed`). The ACTIVE/ABSENT columns are the one that paid off — they are
the only quantitative statement in `06_CONTINUAL_LEARNING.md` about learning vs forgetting rates.

---

## A38 — Run English alone; maybe the other three corpora are throwing the system off

**2026-07-29** · `U0167`

> "Let's do English only. I don't know why we went back to the 4 domains. Maybe the other 3 are
> throwing off the system" — `U0167`

**Response.** Run. `X19`: English-only encoder loss plateaued at 3.83/3.78 against
ln(`ENC_BATCH`=48) = 3.871 — the constant-vector solution — while four corpora reached 2.10.

**Outcome.** **REFUTED, in the opposite direction, and productively.** *"The other three corpora
weren't throwing the system off. They were the only thing preventing a collapse."* The refutation
produced `ENC_VREG` (`c1aadda`) and 17 → 24 domains from a single corpus. Two days later he pushed
back on the result itself — *"It feels wrong for English to only have one domain, double check the
test or metric, and if you optimized it for the wrong thing earlier"* (`U0171`) — and that was right
too (`A39`).

---

## A39 — The router fabric must not be off

**2026-07-29** · `U0171`

> "It feels wrong for English to only have one domain, double check the test or metric, and if you
> optimized it for the wrong thing earlier. […] Why has the router fabric been turned off? It is
> essential for the current system design. […] The final goal will always be proper language" — `U0171`

**Response.** Grep found `FABRIC = bool(_i("FABRIC", 0))` — **"fabric nodes 0" in every phase table
of every run in the project to that date**. Claude also conceded picking `ENC_VREG=5.0` on a domain
statistic and dropped the stability chase. `FABRIC` defaulted ON (`7a42f90`).

**Outcome.** **VINDICATED — this is `INV-02`,** which voids every conclusion about domains,
coherence and bits/byte drawn before 2026-07-29 as "measured a different system". One caveat, and
it cuts the other way: the **+0.709 knockout number that justified the new default was itself
retracted** — `INV-36` / `X53`, the retrained ablation, gives 3.089 vs 3.090 (`e60b8e0`, `9d90416`).

---

## A40 — Why a byte-level signature encoder when we have a variable-length tokenizer?

**2026-07-27** · `U0155`

> "Lets do the runs. I want to flush out what we are doing more. What is the encoder, and why byte
> level? Don't we have the variable length tokenizer?" — `U0155`

**Response.** The question made Claude inspect the window construction and find an unintended defect
he says he had not noticed: `ew = byte_stream[bpos:bpos+WIN]` is 256 **bytes** wide while `i += WIN`
strides 256 **tokens** (~486 bytes) — the encoder saw ~53% of the stream, **and the fraction drifts
as the tokenizer compresses better**. Three fixes implemented as `SIG_WIN` / `SIG_SPACE` (`97acf05`).

**Outcome.** **VINDICATED.** The same defect resurfaced at pilot readiness (`98e3301`, 42% coverage)
and again as `SIG_PROJ_BPT` pinned at 2.4 suppressing the coverage warning (`e2001782`). See
`05_ERRORS.md` §7.

---

## A41 — Do not freeze anything

**2026-07-27** · `U0157`

> "Let's do all 3, but I don't like the idea of freezing, as we can see in 3. Frozen material does
> not bode well for my idea of learning" — `U0157`

**Reading.** A direct application of the sacred invariant (`A02`) to a design choice: option 3 had
proposed freezing a subword vocabulary for the signature space.

**Response.** Redesigned as `SIG_SPACE=tokens` with an **append-only growing** vocabulary — ids never
change meaning, only segmentation shifts. Measured on CPU: bytes W=128 (67% coverage) V 0.74; bytes
W=256 (100%) V 0.67; tokens-growing V 0.73 with a third fewer domains. Claude called it "promising
but not yet a reason to switch"; left OFF.

**Outcome.** **OPEN.** `07_WIP.md` carries `SIG_SPACE=tokens` as built, off, never measured at pilot
scale. The principle held; the mechanism was never tested where it would count.

---

## A42 — Domains should earn their keep — as prediction, or as a driver of expert discovery

**2026-07-29** · `U0169`, `U0170` · raised 2x

> "Domains were a result of the llm creation. It can serve a purpose, but does not need to exist. If
> we can use as a prediction mechanism it would be nice to" — `U0169`

> "One way we can use the domains is for router discovery of other experts and new experts discovery.
> Consider this when you are done with what you will say" — `U0170`

**Response.** Prediction: per-domain token histograms + `DOM_PRIOR` blend + a four-arm held-out test
(`7b481a1`, `X22`). Result **conditional**: four corpora own-vs-random +0.063 ("DOMAINS PREDICT");
English-only +0.000, no signal; and every prior arm still worse than the model alone at those
weights. Discovery: Claude analysed it as well-founded — the Fabric's `cent` and the
DomainAssembler's centroids live in the same `sig_d` space and never talk, and `dom_exp` affiliation
is already computed and discarded — and then designed it and never built it.

**Outcome.** Prediction **REFUTED as a general effect** (it worked only on the spliced corpus that
`A32` had already established was a scaffold). Domain-driven expert discovery: **NEVER IMPLEMENTED.**

---

## A43 — English first; add harder areas later, as the continual-learning demonstration

**2026-07-31 .. 2026-08-14** · `U0185`, `U0197`, `U0434` · raised 3x

> "Let's not do Wikipedia yet, and start out with an English language focus. The system would should
> continual learning, so we can tack more linear, complex and abstract areas later." — `U0185`

> "Let's just do English. Python, programming languages and sciences can be added later. The key is
> to build capabilities to lead up to it, starting with English foundation and using the continual
> learning to build off it." — `U0197`

> "I want english to be done well in a pilot before fully committing to adding new domains, and the
> continual learning." — `U0434`

**Response.** The first raise also carried a correct objection: every RETENTION figure was being
computed on the **current** stream, so "did adding an area damage English?" was unanswerable. Claude
built a held-out probe keyed by domain NAME with a deterministic seed, stored in every checkpoint
(`4713186`), plus `longrun.sh add` / `pilot-add`.

**Outcome.** **VINDICATED — this is the sequencing that eventually produced the only
continual-learning result in the project.** `X49` (`a9d7258`): RESUME from an English run, add
Python from the-stack; `eng 1.998 → 2.050, +0.052 ± 0.075 HELD`; `py 2.276 NEW`; combined 2.243,
beating order-1 by +1.402. **n=1, no seed replication, and its log was lost** — `INV-43`, `pilot-add` never created `$OUT`,
so the numbers in `runs.csv` come from a terminal copy. `INV-25` further limits it: ACROSS THE RUN
BOUNDARY is a **weights-only** number, because `holdout_bpb` does not consult memory. Full account
in `06_CONTINUAL_LEARNING.md`.

---

## A44 — An MB-scale pilot before the GB run, and stop hardcoding the schedule

**2026-07-31** · `U0186`, `U0187` · raised 2x

> "I want to run a short multi epoch first, in the level of MB, as a pilot to the GB run, and mini
> proof of concept." — `U0186`

> "Why are we going by domain? I thought we're doing English only / I don't like how there's
> something hardcoded in again, especially with something as arbitrary as the domains. Make it more
> flexible." — `U0187`

**Response.** `longrun.sh pilot` (2 domains × 30MB, 8 epochs, ~52k steps); running multi-epoch for
the first time immediately surfaced the `PHASE_SCHED` bug (`c411ac7`). The hardcoded table was
replaced by a generated `_phases(n,p,w)` sliding window, verified at n=1,2,3,4,6, with a
`PHASE_SCHED=` env override (`a3ed1a9`).

**Outcome.** **BUILT.** The pilot became the project's standard unit of evidence. The GB run it was
a proof of concept for **never happened** (`A63`).

---
---

# Phase (iv)–(v) — 2026-07-31 .. 08-05 · The expert population at scale, routing, chaining

## A45 — Individually insufficient, collectively sufficient; utilization is the resource; protect the rare

**2026-07-31** · `U0190`, `U0191`, `U0193` · raised 3x

> "The expectation is that none of the individual experts are sufficient for the tasks at hand, but
> aggregate, they are. […] What is the main resource for competition? Utilization. In a sense, the
> attention each expert gets. Rarely used experts and domains for niche tasks still needs to be
> protected." — `U0190`

> "How is competency done? One way we can do it is through seeing their impact on the overall system
> for their messages, and how far they contribute, however may incentivize noise." — `U0191`

> "Measurement of sufficiency can be seen in resulting outcomes" — `U0193`

> "Experts not being strictly within a domain is ok, maybe operate by taking the limited resources of
> domains, and some freedom of stretch." — `U0191`

**Response.** A SUFFICIENCY report section measured on bits/byte exactly as specified; `COMP_PROTECT`
competence protection (`bcd3fd5`); and competence rebuilt from a correlational loss-EMA into a
**leave-one-out counterfactual** on `society()`'s already-computed per-expert outputs (`54e55a2`) —
Claude argued the noise worry does not apply because a noisy expert's removal improves loss, so its
contribution goes negative.

**Outcome.** **REFUTED as measured, and the protection mechanism was inert.** SUFFICIENCY reported
**NOT AGGREGATE on every run** — the pilot: population 2.055 vs best single expert 2.059, the
population buying **+0.004**. COMPETENCE PROTECTION reported "spared 0" for days, and `A48` found
why: there was no culling at all to spare anything from.

---

## A46 — A percentage-based cap on how many domains one expert may serve

**2026-07-31, 2026-08-03** · `U0191`, `U0204` · raised 2x

> "Cap the number of domains a single expert can be part of. It should be percentage based. We can
> cull domains when they are empty. I suspect more will be emptied." — `U0204`

**Response.** `EXP_DOM_FRAC=0.10`, floor 4, enforced by masking the routing softmax; `DOM_CULL_EMPTY=1`
(`763e9f2`).

**Outcome.** **BUILT, THEN FOUND INERT, TWICE.** `dom_ban` was computed but never passed to
`forward()` on the chaining path (`ff0f0fa` audit); and `fab.note_dom(int(_w[0].argmax()), did)`
recorded **one expert per step at `BATCH_W=16`**, so 4053 of 4096 read "serving none" and the cap had
nothing to act on (`99e5da0`). Separately, the empty-domain cull could never fire — the AND-clause
was unsatisfiable (`763e9f2`, `05_ERRORS.md` §6).

---

## A47 — Growth must replicate the successful, with relevance-weighted parents, mutation and crossover

**2026-08-03** · `U0220`, `U0222`, `U0224` · raised 3x in one evening

> "One node carrying so much is not too surprising, if the growth mechanism was done incorrectly.
> Part of what I wanted was replication of successful or (most successful for targeted task at
> hand)" — `U0220`

> "Growth should not just be the fittest, since a more niche may be more relevant. Newborn should
> also have some randomness / mutation injected" — `U0222`

> "We can add on to the randomness mechanism by allowing (completely random) new experts to take
> random connected sections of other experts." — `U0224`

**Response.** Confirmed first: **every newborn was B=0**, an exact identity that computes nothing,
gets no mass, and can never acquire competence. `FAB_REPLICATE` (`e714531`); parent sampled by
fitness among the `FAB_PARENT_K=8` nearest region-owners, mutation raised from an absolute 0.02 to
25% of the parent's own std with a 10%-of-births ×6 heavy tail (`8565246`); rank-slice crossover
(`580cd62`).

**Outcome.** **OPEN.** The toy flipped to SPECIALIZED 0.206 vs null 0.054 ± 0.055. The pilot fired
all three mechanisms (3081 / 436 / 1770 events) and **moved nothing**, with bits/byte getting worse
(2.064 → 2.200). Claude reported the non-improvement honestly. Never resolved at pilot scale.

---

## A48 — "Inability to discover a new expert is almost catastrophic to the idea"

**2026-08-03 .. 08-05** · `U0224`, `U0213`, `U0215` · raised 3x

> "The router issue is very big. We need to fix it, inability to discover a new expert is almost
> catastrophic to the idea. How can we do it?" — `U0224`

> "Is there an expert culling mechanism?" — `U0213`

> "And it said experts off when I was looking at it" — `U0215`

**Response.** The discovery half: top-8 centroid updates (previously **only the argmax winner's
centroid moved**, making discovery impossible), a novelty → least-used handoff, 15% off-policy
exploration (`580cd62`). The culling half found something worse: **the fabric had no culling at all**
— `router.manage()` is gated on `EXPERTS`, which is mutually exclusive with `FABRIC` — so the fabric
was grow-only, and that is also why COMPETENCE PROTECTION had always reported "spared 0".
`fab.manage()` added (`2a262a2`).

**Outcome.** **VINDICATED as a diagnosis; OPEN as a fix.** `INV-14` voids *"COMPETENCE PROTECTION
spared 0"* and every fabric run before 2026-08-03 as evidence about selection. `05_ERRORS.md` §6
carries the whole "populations that could not be culled" class, including its final instalment on 2026-08-15 (`A83`).

---

## A49 — Selection on sustained backprop error, protecting genuine adaptation

**2026-08-04** · `U0229`

> "Another way we can add more selection is through backprop: if there consistently is too much, then
> cull. However learning should still be preserved, like if old news changes, which might cause the
> same effect." — `U0229`

**Response.** Built as specified (`245bc68`): per-expert fast/slow error EMAs; fast ≈ slow and both
above population → cull; fast ≫ slow → **protected as adaptation**. Toy: 152 culled, 72 for sustained
error, 173 spared. Pilot: 4293 culled, 126 for sustained error, 7038 spared.

**Outcome.** **BUILT, never separately measured.** No arm isolates it.

---

## A50 — The dominant expert parents every birth, so the population becomes one lineage

**2026-08-04** · `U0231`

> "And how can we get more expert variety to be chosen and taught? Or perhaps enhance culling, since
> I'd think the main expert being use would be most likely to replicate, and therefore lose its
> competitive edge over time." — `U0231`

**Response.** Confirmed and fixed with a parent quota (max 20% of recent births): "LINEAGE: 91
distinct parents in the recent-birth window | largest share 4% (cap 20%)".

**Outcome.** **VINDICATED as a diagnosis, and it did not fix the symptom.** Used-expert count stayed
at 1. The real cause turned up two days later (`A52`).

---

## A51 — The router should emit the weights of the expert it wants, and spawn one if nothing is close

**2026-08-04** · `U0242`, `U0239`, `U0244`, `U0246`, `U0247` · raised 5x including the branch requests

> "Can we use this system for expert creation and discovery? Where routers output its desired expert
> (by weights), and we will route to closest, but if there is a wildly different, than the predicted
> to be, for the new to be created. This way routers can be trained to discover and created." — `U0242`

> "I thought we held predetermined signatures on where each message came from. The original version
> would will need to be modified though." — `U0239`

> "Since this is an interesting new mechanism, I'd like to have it be pushed as a separately named
> branch. Call it "R M Predict"" — `U0244`

> "I want you to be working on this branch from now on" — `U0246`

> "Please push again. I don't see it in branches on github. Also, are you running anything in the
> background agenticaly or shell?" — `U0247`

**Reading.** Discovery becomes differentiable: the router's *output* is a specification, matching is
nearest-neighbour, and a far query is itself the birth signal.

**Response.** `eemb` maps full adapter weights (2·d·r) → (K, SRC), so an expert's routing identity is
derived from its actual weights — verified by mutating expert 3 and seeing its identity shift 0.3361
while every other shifted 0.0 (`59945e5`). Then `edec`, `spawn_from`, and an autoencoder tie
`FAB_AE_W=0.05` (`f4fc6c7`). Branch `rm-predict` created at `f4fc6c7`. The `U0239` correction restored
the per-expert **SRC** vector the tensorisation had collapsed into one shared `q_route`: the
identical-next-distribution check went True → False, max abs difference 0.056 (`012a2e0`).

**Outcome.** **BUILT — and it is the branch every other file in this set describes.** Two later
readings bear on it: `SPAWNED BY SPECIFICATION: 0` until `ROUTE_REGION_W` made it fire 7 times
(`fcdfaa7`); and `INV-27` — the weight-prediction term was dismissed as "2% of the routing decision"
on a 64-expert toy, and at 4096 experts it is **93%** (`ffd39b8`). The push request was also
warranted: Claude had been holding it on a gate for about an hour, and pushed immediately when asked.

---

## A52 — Provenance in the routing query; the router, not a loop counter, decides completion

**2026-08-04** · `U0256`, `U0263`, `U0265`, `U0266` · raised 4x over 24 hours

> "I want the router fabric input to include the source's weights. Since that's the only way to know
> where it's from. The router should be the one who determines when to complete, not go directly from
> expert to head." — `U0256`

> "Chaining is being run, but, halt should have been set on this" — `U0263`

> "Make sure whenever I run, it is including chaining, unless specified otherwise. Now, how is back
> propagation done? If it only hits one expert, it may explain some issues with training" — `U0265`

> "But, does this mean that the routers will be learning as well? Instead, using new, updated weights
> as training material for its back propagation?" — `U0266`

**Response.** Four distinct findings, one per raise:
1. HALT gating implemented — mean routed depth 0.50 → 1.00 of 4 (`d7994ea`) — **and it exposed that
   `use[]` was never written on the chaining path**, silently disabling culling, the breadth cap and
   discovery on every chaining run.
2. Claude had claimed `SOCIETY=1` could not support HALT: *"You're right, and my 'cannot by
   construction' was wrong. HALT is computed on the society path — and then thrown away."* (`30e635d`)
3. The gradient-reach probe: at N=1024 the compute path touches 20.9 (society) / 30.7 (chaining)
   experts per step — **2–3% of the population**; distinct over 60 steps 261 (25%) vs 78 (8%).
4. A per-parameter gradient audit caught `FAB_EMB_EVERY` defaulting to 50 and acting as a gradient
   switch — live on chaining, dead on society. Default changed to 1; `halt_b` wired in (`8a1e3a7`).

**Outcome.** **VINDICATED four times over.** The backprop-reach hypothesis in particular was
substantially confirmed and is the best single explanation on record for why so few experts were ever
used.

---

## A53 — "First fix the banner lie" — the config report must be derived from what ran

**2026-08-05** · `U0268`, `U0285`, then the endorsement `U0293` · raised 3x

> "First fix the banner lie. It is a lie you constructed. Then, let's evaluate the issue. I believe it
> has to do something with a backprop failure, when chaining occurs, and which expert something should
> go to is unclear. This would help explain why so many experts would form, from a poor routing." — `U0268`

> "Fix all banner lies. They are distracting. Make them automatic and based off what's run. Also have
> the exact pull branch be announced in each log." — `U0285`

> "You are right. This is why we needed the commit numbers." — `U0293`

**Response.** An `_env()` recorder; 72 direct `os.environ.get` calls converted; one declarative table
mapping env name → live object value with an automatic divergence loop; `!!` reserved for
unregistered divergences; a `[build] branch … commit … clean|DIRTY` line (`22a708d`). All three
historical banner lies were reproduced as failing cases first. The DIRTY flag then false-positived on
untracked files and was fixed (`4da76b8`) — Claude: *"That was my bug, not your tree."*

**Outcome.** **VINDICATED, and it paid for itself within a week.** The `[build]` line caught a pilot
running three commits behind, byte-identical to two earlier ones. Claude: *"it cost about an hour of
GH200 time to find out"* — and the third quote above is the researcher noting his own instruction had
just saved the next one. The chaining hypothesis in the same message was also confirmed: an 8-domain
probe gave I(domain;expert)/H = 0.343–0.871 on society and **exactly 0.000 on chaining**, because
chaining had its own weaker entry router with no region term and no centroid update (`a71820a`).

---

## A54 — The toy probes are not the system

**2026-08-05** · `U0270`

> "Your implementation is unusual, why 6 domains? why only 24 experts? It feels very different from
> what the tests are. It rarely leaving 1 is only a sign of underlearning. Also, weights? I thought we
> are using a different system, of router predicting weights of which experts will be better." — `U0270`

**Response.** Claude: *"All three criticisms were right, and the third one found the biggest thing in
this branch."* Produced ROUTING MIX and CHAIN ORDER instruments running in the **real** run; found
`maybe_deepen` had never fired (the third instance of the cadence-bug class); and found the
weight-prediction term measured at toy scale (`e0ce4f7`).

**Outcome.** **VINDICATED.** This is `INV-27` in `05_ERRORS.md` §8 — "attribution errors: measuring at
the wrong scale" — and the researcher named the error class before the file existed.

---

## A55 — Staged / curriculum depth: extend the chain by one hop when it stops improving

**2026-08-05** · `U0269`

> "The issue with chain is how to select among the 4k in terms of order, and also for the possibility
> of the desired not being close. Maybe a staged learning: where after the end expert is found, the
> backprop will happen, and the corresponding router. If it is minimal loss, then we go down a layer,
> to the next expert" — `U0269`

**Response.** Implemented as `CHAIN_CURRIC`, alongside `CHAIN_SUP` (deep supervision) and
`CHAIN_STATE_Q`. All three measured negative on a 6-domain toy and left OFF (`7e9612d`).

**Outcome.** **NEVER ACTUALLY TESTED** — `INV-08`. Claude withdrew the verdict the same night:
`maybe_deepen` sat behind a cadence that never coincided with a flush step, so *"staged depth did not
help"* was reported from a run in which it had not executed (`e0ce4f7`). `07_WIP.md` carries all three
as built, off, never measured.

---

## A56 — The chained society: the society, allowed to loop over and over

**2026-08-05** · `U0279`, `U0287`, `U0290` · raised 3x, the middle one a correction

> "I was conversing with another chat, let's do a test combining society and chaining: the multi hop
> and prediction elements of the system. Then address halt" — `U0279`

> "Just to confirm, my idea for chain_vote was the society system, but allowed to loop over and over,
> (in chains)" — `U0287`

> "Use the most updated, use the chaining society, it should be the default." — `U0290`

**Response.** Claude built `CHAIN_VOTE` first — keeping the learned transition matrix and bolting a
vote on. The correction: *"You're right, and what I built isn't what you described."* `CHAIN_ROUTE=soc`
re-routes from scratch each iteration, with no transition matrix and no SRC (`7b18214`).

**Outcome.** **VINDICATED, and it is the default at HEAD.** `X28`: H(hop1|hop0) = **0.533** bits over
202,130 transitions, against **0.005–0.058** for every transition-matrix arm ever run. The first
non-trivial value that measurement had ever produced. Caveat, from `X24`: every chaining arm,
including this one, still loses to `FABRIC=0` on bits/byte.

---

## A57 — Diversity should be emergent, not imposed

**2026-08-05** · `U0290`

> "Diversity would ideally be emergent. As niches develop and certain experts become more reliable, it
> should keep on improving. Output quality will always trump other metrics." — `U0290`

**Response.** Recorded; no mechanism built for it directly. The nearest thing is the balance floor of
2026-08-15 (`A84`), which is the opposite move — a small imposed pressure so that emergence has
something to emerge from.

**Outcome.** **OPEN.**

---

## A58 — An unattended, crash-tolerant, resumable multi-arm harness

**2026-08-05** · `U0273`, `U0276` · raised 2x

> "prep for next pilot, and if desired multiple separate pilots. I will run for a while and we can
> make most of it, and provide all when done. My plan is to use a sleep 2h && git pull to run, so make
> it safe for that." — `U0273`

> "Are there more for the grid? I am running it for the next 6 hours" — `U0276`

**Response.** `longrun.sh grid` — sequential arms, crash-tolerant (verified against a real SIGTERM,
rc=143 logged and the grid continued), resumable, `runs/` append-only (`09e3d60`). Expanded to 18 arms
ordered by information value (`3e67b5d`), and building it caught two bugs that would have killed 15 of
the 18: `DIV_W` was a local of `main()` invisible to `Fabric.forward` (NameError), and society `DIV_W`
indexed `_O` with a global expert id (IndexError).

**Outcome.** **BUILT**, and it produced `X24`, the 18-arm grid.

---
---

# Phase (vi) — 2026-08-05 .. 08-07 · The LR / tokenizer divergence hunt

## A59 — "I don't think it is it" — refusing the tokenizer explanation, twice

**2026-08-05, 2026-08-07, 2026-08-11** · `U0291`, `U0322`, `U0373` · **raised 3x, and it is the
largest finding in the project**

> "But the minting tokenizer seemed to have done fine in earlier rounds? I don't think it is it." — `U0291`

> "Look deeper. I don't think it's because longer epoch that it worsened. Was there an otherwise
> change?" — `U0322`

> "This is the 4k. 8k is running. Please isolate the different levers. I believe the LR scheduling has
> affected this run" — `U0373`

**Response, raise 1.** Claude tried to test its own claim, found the only minting-off arm was NaN from
step 20k and therefore non-discriminating, and conceded: *"My hypothesis was untested and I presented
it as a finding."* The search then found `lr=2e-3` **constant, with no schedule at all** — `1593c70`,
then `c33f078`.

**Response, raise 2.** `EPOCHS` set the cosine horizon, so it changed the learning rate at **every**
step: at the same step 48,130 the arms trained at 3.58e-4 / 1.04e-3 / 1.52e-3 (E8/E12/E18) — E18 at
4.3× E8's rate. Minting runs also overestimate their own length by 31–37% because minted tokens are
longer, so *"freezing the vocabulary accidentally fixes the learning-rate schedule"* and the frozen run
was the only one ever to anneal to `LR_MIN_FRAC`. Claude: *"my 'the moving tokenizer is the cause' was
not supported. Second time your instinct has beaten my read."*

**Response, raise 3.** `LR_EPOCHS` separated the schedule horizon from run length (`9fabba4`), verified
to match `EPOCHS=8` at 19/19 sample points.

**Outcome.** **VINDICATED three times, and it produced three invalidations.** `INV-28` voids
*"the divergence is the tokenizer"*; `INV-29` voids *"freezing the vocabulary removes the divergence"*
(freezing and annealing were the same experiment); `INV-30` voids *"8 epochs beat 18"*.
`X30`: cosine **2.101** vs none **4.193**, and the constant-LR
oscillation 3.4–7.8 — `04_RESULTS.md` calls it *the one architecture-independent effect far outside
seed spread*. `X31` decomposes the vmax4k@18 regression as **schedule −1.227, length −0.117**, and the
corrected run returned **2.023**, the best in the project at the time. Every one of these came from the
researcher declining Claude's explanation and asking for another pass.

---

## A60 — Which checkpoint did that text come from? And why is the best at step 6k?

**2026-08-05** · `U0298`, `U0299` · raised 2x

> "Before the run happens, I want to address the losses pattern seen, going from 3 to 2 to 8 to 3, and
> which checkpoint was used for generation" — `U0298`

> "Another issue then is why is the best bit/byte at step 6k? When the tokenizer didn't even cap out,
> and there is still learning for the embedder and overall system" — `U0299`

**Response.** The first found that `generate()` sampled the **live** model at end of training with no
best-checkpoint tracking anywhere: *"Every text sample I've shown you came from a model ~41,000 steps
past its best."* `<SAVE_CKPT>.best` plus a SAMPLED FROM line (`3f67bfc`). The second found `_VALT`/`_BL`
cached the tokenised held-out text once and never invalidated it, so the curve compared a current model
against validation text frozen in an old segmentation — *"best at step 6000" was the yardstick moving*
(`18fdd6c`).

**Outcome.** **VINDICATED, both** — `INV-18` voids *"best at ~step 6000, identical in every arm at
every seed"* and the interpretations built on it. Caveat: the `_VALT` fix did **not** remove the early best, and the
project's two held-out instruments were then found to have disagreed by 1.53 b/B for the whole branch.
See `05_ERRORS.md` §7.

---

## A61 — The fault is in how new tokens are taught, and they must keep parameters

**2026-08-05 .. 08-06** · `U0301`, `U0303`, `U0304`, `U0305` · raised 4x

> "How about this, lets test with the minimum sized tokenizer. From there, we can move on. I'm thinking
> an issue is stemming with how we are teaching with the new tokens, and what we do with newly minted
> tokens and their learning" — `U0301`

> "I dont think that will help, unless we fix the issue with the way that the system learns the new
> tokens" — `U0303`

> "Can the tokens, instead of something complex, use its integer values as id's instead?" — `U0304`

> "We want minted tokens to start with parameters. My original goal was to make the transition, between
> new mint and its composite, much easier. I want these tokens to be trained on even with the loss, but
> we need to do it differently." — `U0305`

**Response.** The floor was measured and ruled out — `X44`, `TOKENIZER=0` at 123,983 steps: held-out
4.378 vs order-1 3.840, *does not beat order-1*. `WARMSTART_MODE` was built and measured over 18 trials
(6 pairs × 3 seeds): last/first **1.4822** vs current mean/mean **1.8222**, −0.340 at 31× its own sd —
and shipped **DEFAULT OFF** because the end-to-end toy disagreed. Then Claude implemented `TOK_COMPOSE`
by **removing** per-token parameters, which is the opposite of what was asked; the fourth quote is the
correction. Rebuilt as `token vector = composite(bytes) + zero-init residual` with `TOK_ANCHOR`
(`ed04aac`), mechanism verified directly (delta 0.0 at birth; anchor 0.25 young → 0.0017 at age 20k).
Claude: *"I built the wrong thing and you corrected it."*

**Outcome.** **UNCLEAR — the strongest sub-experimental result in the tokenizer work is off by
default.** `X39` (`WARMSTART_MODE`) is 31σ on its own measurement and disagrees with the end-to-end
toy; nobody ever ran the arm that would settle it. `TOK_COMPOSE`'s only pilot scored 5.360, the worst in
the project, **but it also had `TOK_MINT_NOVEL=0.5` on, so it attributes to neither**, and it was
reverted to off (`be50e3a`). See `07_WIP.md`.

---

## A62 — Between the shocks, is the loss actually falling? And minting is non-negotiable

**2026-08-06** · `U0306`, `U0307` · raised 2x

> "I don't expect the shocks to completely disappear. Their existence is ok. Now, another important
> question that I want confirmation: has loss been dropping with our architecture if we look away from
> the tokenizer disruptions?" — `U0306`

> "Has this been true in past runs? Token minting is critical for my idea of continual learning." — `U0307`

**Response.** A slope table over all 25 logs: **19 of 21 all-run-minting logs FLAT or WORSE**
(+0.0175 to +0.2170 per 10k steps); only the frozen and bytes arms improved. Claude: *"with minting on,
the whole second half is flat or slightly rising… they arrive faster than recovery completes."* A
`STILL LEARNING?` instrument was added to every report (`23099fc`). The constraint in the second quote
reframed the work: rather than turning minting off, Claude found `maybe_grow()` mints
`most_common(1)` — the globally most frequent pair, i.e. the most disruptive possible choice — and
built `TOK_MINT_NOVEL`.

**Outcome.** **VINDICATED as a question** — it produced the project's only measure of whether training
was working at all — and the constraint held: minting was never switched off in a default configuration.
`TOK_MINT_NOVEL` remains default 0, never cleanly measured.

---

## A63 — "We are over-optimising for a single metric again, this time the spike"

**2026-08-06** · `U0310`

> "I think we are overoptimizing for a single metric again, this time the spike. Spikes are ok, just
> that it wasn't lowering as much as I thought would happen. Maybe we should go back" — `U0310`

**Response.** Claude pulled held-out from every pilot log — eleven runs across five commits sitting in
a 2.0–2.2 band with minting on **or** frozen — dropped the LR bug as the explanation (*"I found a
genuine bug and then reached for it as the explanation because I was staring at the spike. It isn't."*)
and reverted `TOK_COMPOSE` so HEAD's defaults matched `c33f0781`.

**Outcome.** **VINDICATED.** The third instalment of `A35`, and the one where the correction landed
fastest.

---

## A64 — The frozen arm was only half switched off

**2026-08-06** · `U0319`

> "Let's keep the tokenizer system available, but no minting or otherwise activity. I believe we only
> shut off part of it, not all, giving more load to the system." — `U0319`

**Response.** Confirmed by the log: **39 retokenizations fired in the "frozen" run, every one a no-op**
("vocab 512/2048 (minting live; +0 since last retok)"), each dropping `_sigq`, clearing `_VALT`/`_BL`,
and calling `fabgrow.note_shift(step)` — blacking out fabric growth for `FAB_COOLDOWN`=400 of every 3000
steps, **~13% of the run**. `RETOK_EVERY=0` was identified as the flag that stops it and added to the
next test pair.

**Outcome.** **VINDICATED, and it produced one of the largest single-knob effects on record.**
`X37`/`X43`: `frozen` **4.364 b/B, 26% real words** vs `frozen_nr` **2.175 b/B, 94% real words**, with
**identical vocabularies** (512 minted, 441 used, 0% dead), differing only in `RETOK_EVERY=0`
(`046fd81`). Two caveats, both from `05_ERRORS.md`: **`INV-10`** rules the 2.189 b/B magnitude
**UNATTRIBUTABLE** — the effect is real, its size is not — because `RETOK_EVERY=0` also silently
disabled signature batching, so the arms differ in **two** ways (`79dac6c`); and **`INV-42`** voids
the earlier `frozen`/`frozen_nr` numbers (6.114 / 2.365) as measured under 75% dead rows, the clean
re-runs above replacing them.

---

## A65 — The spikes are the system searching for new subspecialties

**2026-08-06** · `U0319`

> "I agree that its's the best, but it's also the longest running. […] Maybe the others need to go
> through a longer training as well before we can see such a crash. It's possible that when there are
> spikes, new subspecialties are in demand and in search for." — `U0319`

**Response.** Tested directly against the growth log: 67 growth events before step 26000, **zero during
the 26k–42k plateau** (27 culls instead), and the first growth after recovery at step 51,903 — **8,000
steps after the loss had already recovered**.

**Outcome.** **REFUTED.** Recorded here because Claude *reframed* rather than refuted at the time
("why didn't the search fire when the system was visibly stuck?"), which left the original hypothesis
looking less dead than it is. The run-length confound the same message raised was separately correct
and led to the E18 comparison.

---

## A66 — Do not under-read the fabric's contribution

**2026-08-06** · `U0319`

> "I don't think it means the fabric contribution was that much worse, since it has been instrumental
> for our expert selection and learning of it." — `U0319`

**Response.** Claude conceded overstating: "model ALONE 2.057" is a model that trained **with** the
fabric for 118k steps; the ablation also strips the fabric LayerNorm; and the fabric was working harder
than in any previous run (gradient reach 23.8% vs ~9.7%, 636 distinct experts vs 238, HALT 0.4048 after
reading 0.0000 in every prior chaining run).

**Outcome.** **UNCLEAR.** `X53` / `INV-36` is the honest state of it: eval-time knockout **+0.709**,
retrained ablation **3.089 vs 3.090**. The knockout number justified a default and was retracted
(`9d90416`).
Nothing in the record separates "the fabric contributes" from "the model adapted to the fabric".

---

## A67 — An uncapped vocabulary later, but the small tokens will go stale

**2026-08-06** · `U0320`

> "I want to try uncapped tokenizer later, however, one concern I have is underutilization of some of
> the basic or smaller tokens." — `U0320`

**Response.** Confirmed by data the next turn, without a dedicated experiment: the run that minted to
2048 produced **31% real words**; the one held at 512 produced **92%**. Claude: *"That is exactly the
mechanism you described, showing up in the data before we went looking for it."* The token-utilization
instrument he proposed in response (per-id occurrence histogram bucketed by length, fraction of vocab
receiving zero gradient) was **not built** then; a partial version — the `[vocab]` "never minted" vs
"minted, unused" split — landed on 2026-08-11 (`2c705c7`).

**Outcome.** **VINDICATED, on evidence that already existed.**

---

## A68 — A self-judged update gate, cross-referencing, and fixed-op experts

**2026-08-06** · `U0320`

> "And the continual training. I want the system to be able to decide, when it is sufficient, when to
> or not to backprop when there is a difference. Ideally this would include cross referencing, other
> ways for it to use its own judgement. Also ways to replace an expert with a fixed line of code or
> action, for it to learn to use." — `U0320`

**Response.** Design sketched only — gate on the existing `surprise` scalar; cross-referencing mapped
onto the per-expert output spread already computed each hop; a fixed-op expert modelled on the HALT
reserved-mass branch rather than a tensor slot. Staged behind three fixes and never revisited.

**Outcome.** **NEVER IMPLEMENTED.** The third clause is `A07` from 2026-07-21, raised a second time and
still not built.

---

## A69 — Test standard anti-overfitting in the real runs

**2026-08-06 .. 08-10** · `U0320`, `U0322`, `U0330`, `U0335` · **raised 4x**

> "We also should test if typical anti overfitting can works, and use it. In our runs" — `U0320`

> "And let's use the anti overfitting mechanisms in it" — `U0322`

> "I messed something up with the run, let's do it again. Let's bundle the rest of the pilots and anti
> antioverfit while we are at it" — `U0335`

**Response.** Claude flagged that every run reports UNDERFIT with a **negative** gap, so regularization
points at a problem that has not appeared — then agreed to run them as arms. `707f1af` added a `pilots`
preset (base, frozen, frozen_nr, drop, wdecay, reg); all six ran.

**Outcome.** **REFUTED at this scale, after four raises to get it run.** `X37`: base **1.962**,
frozen 2.072, frozen_nr 2.365, drop 2.323, wdecay 2.277, reg 3.725. Every regularized arm is worse.
The value of the thread is that the question was closed with a measurement instead of an argument.

---

## A70 — The long 40 GB run

**2026-08-06** · `U0320`

> "Two things left: a major and long run, originally would have been called the multi epoch, but will
> be an expanded run with the desired 40GB training  set" — `U0320`

**Response.** Blocked on three defects that worsen with run length (the zero-gist `ground_update`, the
stale `_total_steps` LR horizon, the harness precedence bug — all fixed 2026-08-07 in `5f4f117`) plus
an untested RESUME path. Then blocked again, and again.

**Outcome.** **NEVER RUN.** The 40 GB corpus was fetched on 2026-07-25. At the end of the transcript the
largest run in `runs.csv` is a 30 MB pilot.

---

## A71 — Methodology: one run each is enough for a rough estimate

**2026-08-06 .. 08-07** · `U0302`, `U0314`, `U0329` · raised 3x

> "This is only one seed, the other did not complete, but I dont think its worth it" — `U0302`

> "This is the results. I only ran 1. I think it is conclusive enough." — `U0314`

> "I don't want to run multiple tests yet, first each once, because once is enough for a rough
> estimate." — `U0329`

**Reading.** A deliberate methodology call: screen at n=1, spend replication only on what survives.

**Outcome.** **REFUTED by the project's own instrument, and it is the most consequential wrong call in
the record** — `INV-35` voids **every single-run architecture comparison in this branch**. `X50`/`X52`: four runs of one nominally identical arm spread **1.227 b/B** (`33a9299`);
the population 2x2's arm D spread **2.074** across three seeds (`X46`). `04_RESULTS.md` puts the seed
table **before** the comparison tables for exactly this reason, and `LITREVIEW_FINDINGS.md` returned an
external answer on per-arm σ that changed the reading again. In fairness to the call: the very same
message that produced `U0314` was byte-identical to two earlier runs and thereby demonstrated
determinism, and on 2026-08-14 he ran a reorder control himself when one was needed (`A74`).

---

## A72 — Are the different seeds actually separate runs? And show me more generated text

**2026-08-07** · `U0327`, `U0328` · raised 2x

> "Are the different seeds separate runs?" — `U0327`

> "What is the difference between a repeat and seed? Also,  for the sample generations, we should do a
> few more." — `U0328`

**Response.** The first: yes — one sequential process per seed, `SEED_CKPT=0`, RESUME unset — **but the
question surfaced a hazard**: `data/dyntok.json` is written unconditionally by every online run, and
with `TOK_ONLINE=0` it **is** loaded, making seeds non-independent and order-dependent for the
`frozvocab` arm and any past grid arm using it. A per-run `TOKENIZER_PATH` was offered and **not done**.
The second: `GEN_N` added, default 4 passages per process (`c14f876`) — revealing that with one corpus,
`GEN_PROCS=4` meant **every text judgement in the project had come from a single 200-token
continuation**, and the 91% / 71% / 31% "real words" figures were computed on 64–91 words.

**Outcome.** **VINDICATED, both.** The second is `INV-21`, which voids every "% of generated words
appearing in the training text" figure before 2026-08-07 and every coherence probe reading
`_gen_keep`. The `dyntok.json` hazard is still open — see `07_WIP.md`.

---
---

# Phase (vii) — 2026-08-07 .. 08-13 · Config registry, equivalence, the vocabulary arms

## A73 — Disentangle the code into clean orthogonal levers, with no behavioural change and a table of what moved

**2026-08-07 .. 08-11** · `U0330`, `U0331`, `U0333`, `U0348`, `U0350`, `U0371`, `U0375` · **raised 7x
over 5 days**

> "I want you to normalize and disentangle the code, since there are so many interrelated things, some
> unnecessary. This way we have clearer levers. Create a table of what was modified, in the end. Ensure
> that nothing is functionally different, just that things are disentangled." — `U0330`

> "Did you edit the code? I wanted clearer, and better defined code, and a table of those changes" — `U0331`

> "Has the total clutter been fixed and levers fully isolated yet?" — `U0350`

> "Have those levers been separated and isolated? I thought I asked for that." — `U0371`

> "This is why we need to fix the levers and their connections, so they do not overlap and improperly
> change things" — `U0375`

**Response.** The first attempt added a **fifth layer of indirection** on top of the four tangled ones
and was reverted entirely at his direction (`4e91275` → `a0df9a6`, 91 deletions). Then the real pass:
all 274 knobs into one `_SPEC` registry with `_env` enforcing defaults (`6f4c534`), verified 13/13 smoke
arms byte-identical against a pre-refactor worktree; then an AST audit finding 4 of 279 knobs absent
from the registry and `levers.py` as a standing drift check (`f279fd0`); then a COUPLING banner
(`4603b06`). The `main()` split was attempted and **fully reverted** after four bugs (`9c59a84`).

**Outcome.** **VINDICATED AND STILL OPEN.** The registry is real and is what `07_WIP.md` and
`05_ERRORS.md` §1 both key off. But `07_WIP.md` records `main()` at HEAD as **~2,940 lines with 658
locals**, with the split blocked on a 136-value seam that needs a rename pass first. Seven raises, and
the central complaint is unresolved.

---

## A74 — The misleading clutter is outdated comments, not code

**2026-08-10, 2026-08-15** · `U0348`, `U0349`, `U0354`, `U0447` · raised 4x

> "you estimated the tests will take 2hrs, they ended up taking 6, for something about architecture when
> I asked for if anything was changed. I suspect that there's a lot of unnecessary stuff in the files
> that are throwing you off." — `U0348`

> "What I meant for my hypothesis is that there are comments inside the code that are outdated and do
> not hold" — `U0349`

> "Your comment audit is not good. It's stating things like facts when they are not. We've proven halt
> works and has worked in the 512 v tokenizer. […] Remove anything that makes claims subject to
> change." — `U0354`

> "Treat past comments as a rough statement, never as anything definitive, especially since it can
> drastically change with different structures and architecture." — `U0447`

**Response.** The hypothesis was tested and confirmed: **302 comment blocks, 80 asserting a measurement,
44 touching topics that had moved that same session.** Six were corrected in `bdce727` — including one
where Claude recorded *"I read my own comment saying the tokenizer was the failure mode, and spent days
building on it."* Then the third quote corrected the repair itself: replacing stale claims with fresh
claims is the same mistake, and one of the fresh claims (HALT never engaging) was already false.
`6dda2c4` stripped the empirical assertions instead — *"a comment that records a measurement is wrong the
moment the code changes, and this file has now misled me twice that way."*

**Outcome.** **VINDICATED, and it is the criterion `09_COMMENT_AUDIT.md` is built on.** That file cites
`bdce727` → `6dda2c4` as the project ratifying the rule, and classifies 354 blocks / 2648 lines:
KEEP 279, MOVE 51, WRONG 19, STALE 5. It is a plan — **no comment has been moved yet.**

---

## A75 — Redesign the tests: a proper reusable equivalence check

**2026-08-10** · `U0346`, `U0340`, `U0343` · raised 3x

> "What do you mean by test conclusion? Our main goal was whether the edits to the levers have broken
> anything" — `U0340`

> "Where is it saved? I don't see a new folder in runs" — `U0343`

> "Redesign the tests. I don't like it, and what you give out seems to be broken. Do a new set to test
> if anything has changed post lever modification." — `U0346`

**Response.** The middle quote caught a bad command of Claude's own: `GRID_DIR=runs/pre_check` resolved
relative to a temporary worktree that its own `git worktree remove --force` then deleted. Claude:
*"That's a bad command and it's mine."* Then `equiv.sh` (`2d93a3e`) — a reusable A-vs-B at fast scale,
returning IDENTICAL in ~8 min on CPU, plus a determinism self-test (same commit twice) added in
`7ff2af0`.

**Outcome.** **VINDICATED.** `equiv.sh` went on to catch **four separate bugs in Claude's own edits**
and to establish that the GPU is nondeterministic in the memory subsystem. Caveat from `07_WIP.md`: no
`runs/equiv_noise_*` baseline was ever established on the GPU box, so `c6f54e6`'s INERT verdicts are not
fully trustworthy.

---

## A76 — Something is wrong in the frozen setup; dig deeper

**2026-08-11** · `U0366`, `U0367`, `U0368`, `U0369` · raised 4x in 15 minutes

> "What is frozen in the frozen run?" — `U0366`

> "Let's rerun the min tokenizer run then, since it diverges from the prior so much" — `U0367`

> "Yes, different corpus and epoch count, but those shouldn't matter even if deterministic. Something is
> likely wrong in the frozen setup. Dig deeper" — `U0368`

> "The random initialization is likely why, let's run the capless properly then" — `U0369`

**Response.** Bits/token analysis showed the frozen arm using **3% of its headroom** (8.73 vs uniform
9.00) against base's 47%. Root cause proposed: `V = VMAX = 2048` with 512 live ids, so **1,536 rows only
ever take negative gradient**. A `[vocab]` instrument was added (`ce8d4ea`), then split into "never
minted" (invalidating) vs "minted, unused" (normal turnover) at his insistence (`2c705c7`).

**Outcome.** **VINDICATED as a defect, REFUTED as the explanation.** The audit found six arms configured
to guarantee dead rows (`b6952da`, `25c37eb`) — a real harness defect. But the dead-row story itself was
falsified four hours later: `vmax8k@18ep` filled **8192/8192 with 0% dead** and still scored worst
(4.383). `INV-34` marks the dead-row series (0% → ~2.2, 41% → 3.561, 75% → 6.114) as not the monotone story
it was quoted as, `INV-42` voids the six mis-configured arms as named, and the first controlled test
(`X47`, `LOSS_MASK_DEAD`) gives **+0.060 against a combined SE of 0.055 = 1.1σ**.

---

## A77 — Run longer rather than mint more per event; minted-but-unused is normal

**2026-08-11** · `U0371`

> "A better solution, than making more minted at a time, is to make the run last longer. Also, some
> minted tokens not being used is ok, a good percentage is still being used. The 4k and 8k vmax already
> started before the change. We can rerun later" — `U0371`

**Response.** `GROW_BURST=24` reverted from `vmax8k`; the justifying comment rewritten to "RAISING VMAX
ALONE DOES NOT RAISE THE VOCABULARY, AND THE MISSING LEVER IS EPOCHS"; the `[vocab]` split measured
15.3% unused in a broken run and 16.7% in a healthy one, confirming his point that the figure alone is
not a defect signal (`2c705c7`).

**Outcome.** **VINDICATED.**

---

## A78 — The cosine must repeat, not hold at the floor — and the change must first replicate

**2026-08-11** · `U0388`, `U0389`, `U0390` · raised 3x

> "Can we have LR EPOCHS last the full run by default, but intervals stay the same, like before?" — `U0388`

> "No, I don't want a clamp, it should continue with the cosine waves. The goal is to repeat." — `U0389`

> "The key for LR Epoch is: we had runs where 8 epochs would be nice. The LR Epochs should, a replicate,
> and b improve on those results." — `U0390`

**Response.** `LR_RESTARTS`, default 1 (`c341921`), later refined so whole cycles fit the run and it
always ends annealed. The **replicate-first requirement in the third quote exposed a real bug**: at
`EPOCHS == LR_EPOCHS`, `_prog` hits 1.0 and `1.0 % 1.0 == 0.0`, so the LR jumped back to **peak** on the
final steps of every 8-epoch run. After the fix: max |restarts − hold| = 0.000e+00 on the 8-epoch
replication.

**Outcome.** **The requirement VINDICATED; the mechanism REFUTED.** `X32`/`X33`: vmax4k **2.023** (hold)
vs **2.132** (restarts); vmax8k **3.377** vs **3.989**. Claude, 2026-08-13: *"LR restarts look
net-negative, and that's my default."* `LR_RESTARTS=1` is still the default at HEAD — `07_WIP.md` carries
it as built, on, never validated at scale.

---

## A79 — Anchor release by appearances, not steps; and keep retok out of the anchor window

**2026-08-11** · `U0383`, `U0388` · raised 2x

> "TOK_ANCHOR_TAU=4000 / RETOK_EVERY=3000 / Can Resegmentation trigger during the Anchor Period? I don't
> want it to trigger incorrectly / I want to keep the two separated" — `U0383`

> "I also want to modify anchor, so instead of 4000 steps, it triggers after a certain amount of
> appearances, ensuring training." — `U0383`

> "Anchor uses should not default to 0. Lets make it 400" — `U0388`

**Response.** Solved by construction: the appearance counter can only advance when a token is in a
training batch, which a re-segmentation cannot do (`3464ba7`). Unit-tested: two tokens of identical age
seen 500× vs 2× score 0.905/0.905 under steps and **0.007/0.980** under appearances. `TOK_ANCHOR_USES`
default set to 400 (`c214c21`).

**Outcome.** **NEVER MEASURED.** The whole mechanism is gated on `TOK_COMPOSE`, which defaults to 0, so
`TOK_ANCHOR` has never fired in a real run. `A80` below is the audit he asked for that proves it.

---

## A80 — Extend the never-fired audit to every loss-term knob

**2026-08-11** · `U0390`

He pasted a line of the project's own code back at it, then:

> "self_organize.py already has the check that would have caught the inert anchor years of runs ago —" — `U0390`

> "Make the change" — `U0390`

**Response.** The audit, previously covering only `DIV_W`, `IND_W` and `CHAIN_SUP`, was extended to
`TOK_ANCHOR` and every loss-term knob (`fec2285`). It fired unprompted in a real run twelve minutes
later: *"`[config-audit] !! TOK_ANCHOR=0.05` was ON and its loss term NEVER FIRED — it is gated on
`TOK_COMPOSE`, which is 0 here."*

**Outcome.** **VINDICATED within the hour.** It is one of the countermeasures `05_ERRORS.md` credits with
catching the "knobs read by nothing" class.

---

## A81 — A meaning gate on minting, and probationary tokens

**2026-08-11** · `U0388`, `U0389`, `U0390`, `U0394` · raised 4x

> "I knew we had a quality control, before minting as permanent, where we check if the overall meaning of
> them is more than the composites, or has a useful meaning.  I've been thinking we were using it." — `U0388`

> "Maybe we can do something like branching entropy, where two tokens , a and b are merged, and I guess
> used, when a can reliably predict b." — `U0388`

> "For the quality control, the goal was to have a sort of embedder test, where we see if the sum of
> components is different from them separately. Lets shelf this for later." — `U0389`

> "Branching entropy should default on. We'll need to figure how to go about, since aim is learn and
> verify before fully minting token" — `U0390`

> "Judgement of merge or unmerge should correspond to either: the branching entropy that was built, or an
> embedding system that sees if the sum is more than the parts. Let's build the probationary mechanism
> then" — `U0394`

**Response.** The recollection in the first quote was **falsified**: `git log -S` over `tokenizer.py`
found no such gate in any commit — *"No such gate has ever existed."* The gate was then built three
times: v1 (absolute H(next|a) ≤ 1.5 bits) blocked 100% of candidates; v2 switched to his actual
criterion p(b|a) but still aborted the grow burst; v3 filters instead of aborting (`c214c21`, `93c1733`).
Probation shipped as `TOK_PROBATION` / `_BY` / `_STEPS` with soft retirement (`9f8412b`) — and of his two
proposed criteria, **entropy is structurally impossible post-mint**: greedy longest-match consumes the
pair, so p(b|a) = 0 forever ("0 kept, 8 un-merged, 100% failed"). Replaced with a `use` deadline;
`embed` survived.

**Outcome.** **REFUTED as a default.** Defaulted on at `TOK_MINT_PMIN=0.10`, it starved the first real
pilot: vocab asymptoted at 1439/2048, **29.7% never-minted rows**, held-out 3.600 against a best of
2.829 at step 6000; median p(b|a) was 0.029 against a 0.10 threshold. Fixed to **fail-open** — the gate
may reorder, never prevent — and the default returned to 0 (`1a113f5`, `X40`/`X41`). Claude: *"A filter
that produces 30% dead rows at the standard config hasn't earned a default. It's an arm."* Probation
(`X42`) is built, off, **never run at pilot scale**. The embedding test he actually wanted is still
unbuilt at scale.

---

## A82 — Record runs in a CSV, not in source comments

**2026-08-11** · `U0393`

> "Instead of recording in self organize, use a csv to keep track of past runs. We can add that new
> series to the queue of tests. Let's go back to what we were in the middle of adjusting" — `U0393`

**Response.** `runs.py` + `runs.csv` (`8103a8a`), seeded with 13 rows; `runs.py stale` reads today's
defaults out of `_SPEC` and reports per row what must be overridden to reproduce it.

**Outcome.** **VINDICATED, and it is why `04_RESULTS.md` exists.** `runs.csv` is the primary source for
that file, every column is parsed from a log rather than typed, and it survived several container
rollbacks via origin. It is also the same principle as `A74`, applied one day earlier and to the right
target. `09_COMMENT_AUDIT.md` records two comments that are the **only** surviving record of a run and
are now mirrored into `runs.csv` — the do-not-delete list.

---

## A83 — Are the smoke tests even updated?

**2026-08-11** · `U0399`

> "Why always the smoke tests? Are they even updated?" — `U0399`

**Response.** Within the hour: the smoke had **duplicated `_flags_for` instead of calling it**, and three
of seven arms had already drifted (`prob_use` 150 vs 200; `compose` missing `TOK_MINT_NOVEL=0`). Claude's
first fix was **also** broken — `_flags_for` was defined inside the `grid)` case branch, so smoke would
have resolved every arm to the empty string and reported seven identical runs as seven passing arms.
Hoisted to top level (`136461c`).

**Outcome.** **VINDICATED.** A one-line question found a test harness that had been silently passing.

---

## A84 — vmax8k was not eliminated on good evidence

**2026-08-12** · `U0408`, `U0406`, `U0407` · raised 3x in one exchange

> "the final goal is for language, not optimizing specifically the tokenizer, vmax, or different ways to
> freeze the structure . I need to be able to carry and build off the results we get, and a stumbling
> block has been the levers I've wanted split, but not, and interfering with our runs… Remember that a
> target has been and still is the continual learning." — `U0406`

> "Why is vmax8 eliminated? I don't think we ran it properly, and that statement constrains us a lot" — `U0408`

**Response.** Full retraction: **every `vmax8k` run on record carried a known defect** — 41% dead rows at
8ep; the old stretched LR at 18ep; 56% and 73% of the run pinned at the 5% LR floor for the lr8 runs,
which predate `LR_RESTARTS`. *"vmax8k goes back in the candidate set, untested."*

**Outcome.** **VINDICATED** — and the re-run was itself later withdrawn once the `FROZEN` RNG bug
surfaced (`A85`). The first quote is the fifth and last instalment of `A35`; the checkpoint concession it
produced is in `A17`.

---

## A85 — The VMAX non-monotonicity is a bug, not a property

**2026-08-13** · `U0411`, `U0412` · raised 2x

> "I will run, but in the meanwhile, why would it work in the 4k, not either other? This is an interesting
> constrain on our system, if the continual learning needs to be around 4k tokens. I suspect a bug may
> have occured." — `U0411`

> "Send out an agent, to see if there may be a bug." — `U0412`

**Response.** Two defects, either of which is disqualifying. (1) `SIG_PROJ_BPT` was **pinned at 2.4** —
the `VMAX=2048` value — so the coverage banner printed "covers 100%" for every VMAX while real end-of-run
coverage was 82% / 70% / 61% (`e2001782`); monotone, so it does not explain the ordering. (2)
`FROZEN = torch.randn(V, D)` at **module scope**, re-rolling the RNG for every non-VMAX-shaped module —
so the three arms were **three different random initialisations**, against a documented same-seed spread
of 1.594 b/B (`0f96784`).

**Outcome.** **VINDICATED.** `INV-31` marks the **whole VMAX field** unattributable — the
`VMAX × EPOCHS` 2x2 (`X45`), the six-run 18-epoch table, and the non-monotonic ordering itself. The same dispatch also found the `_due` double-call still armed for `grow`, which would
have silently frozen minting the first time `TOK_PROBATION>0` ran.

---

## A86 — "Why are we trying to measure the noise? Let's fix the issue"

**2026-08-13** · `U0416`

> "Why are we trying to measure the noise? Let's fix the issue that's coming up, or first find it" — `U0416`

**Reading.** Claude had proposed spending GPU time characterising the run-to-run variance. The researcher
declined and asked for the cause instead.

**Response.** The diagnostics were drawing from the **global RNG that `build_stream()` uses to pick
segment lengths** — so a run that measured more trained on different text. Measured: **23,835 of 250,027
global draws (9.5%) taken inside eval passes.** Five leaks fixed — eval-time exploration, eval-time
utilization recording, the timing probe's `.backward()`, halt/mass EMAs averaging eval passes, and probes
drawing from the global RNG — plus a dedicated stream RNG (`c76dc74`). Post-fix, `PROBE 1→0` and
`EVAL_N 4→16` became **bit-identical**, and the 1.594 b/B same-seed spread went to **0**.

**Outcome.** **VINDICATED, and it is the single most consequential call in the record.** It is `E11` in
`01_TIMELINE.md` and `INV-13` in `05_ERRORS.md`: *"No result in the record predates these fixes safely:
every arm comparison was measured through an instrument that was changing the thing it measured."*
**The planned measurement would have characterised an artefact and been wasted.**

---

## A87 — Fix the memory-context drift before spending GPU on anything

**2026-08-14** · `U0421`, `U0418` · raised 2x

> "Fix the issues, then we can test again" — `U0418`

> "Before we do, address the mem.tok issues, since they may cause a drift" — `U0421`

**Response.** `remap_mem_ctx()` (`8bdeca4`). Measured: **82.3% of stored contexts stale across one growth
step** (vocab 647 → 1024); in-run remaps of 2553 / 3601 / 2917 / 1585 / 1928 / 1754 / 1521 / 967 / 597
contexts over nine retoks. The unrepairable remainder is now reported as a number: **4.0%** (255 of 6382)
of entries predict an id the final stream never carries.

**Outcome.** **VINDICATED** — `INV-23` voids *"memory contributes +0.698"* and every per-entry
retrieval figure before `8bdeca4`. Still limited at HEAD: `07_WIP.md` records that memory entry **values**
cannot be remapped across a re-segmentation and the stored SPAN shrinks, and that fixing it changes the
checkpoint format.

---

## A88 — The state-leak hypothesis, and the control he ran himself

**2026-08-14** · `U0424`, `U0425`, `U0426`, then `U0427` · raised 4x

> "I think you are looking at bit spread incorrectly, since it seems to be dropping from seed 0 to 2, and
> building off each other. Is this possible?" — `U0424`

> "Is there a location where state leak is occuring? It does not look like it is just reported numbers,
> since text quality differs between the runs, and relatively good in the last" — `U0425`

> "Or rather, is there anything that is being kept, saved, and possibly used in the following runs? It
> likely is not the tokenizer." — `U0426`

> "I ran these in order 2, 0, 1 . Now we need to figure out why seed 0 is so much worse than 2." — `U0427`

**Response.** Claude argued against it three times — seed 2 starts worst at step 2000, the lead changes
hands five times over 24 samples, word percentages are not ordered, all three print a fresh tokenizer —
then ran a **39-channel code audit**, ruling out 38 and finding one real but cross-invocation channel:
the `_done`/TAG resume-skip re-printing stale numbers, so an 18-epoch sweep skipped and reported the
8-epoch numbers under an 18-epoch banner (`42d8686`). The third quote reframed the question into an
exhaustive persistence inventory, which established that only two read sites exist in the whole tree and
both are gated on RESUME. Then the researcher **ran the control himself**: seed 2 first, results identical
to three decimals.

**Outcome.** **REFUTED — by his own control — and it paid for itself anyway.** The order hypothesis was
retired, GPU determinism was confirmed (retiring a separate `index_add_` nondeterminism concern), and one
genuine harness defect was found. The right entry for how the hypothesis was pressed is
`10_HISTORY_FINDINGS.md`; the point here is that the researcher designed and executed the experiment that
killed his own idea.

---

## A89 — Turn the leak into a designed capability

**2026-08-14** · `U0426`

> "Also, state leak would be bad in one sense, however, we can utilize this for our system, building off
> of it (intentionally), to get more efficient. We still need to control for it when applicable, but it
> is a helpful lever" — `U0426`

**Reading.** Deliberate cross-run carry-over is not a contaminant; it is what continual learning *is*.

**Response.** Claude identified RESUME as exactly that lever — fully implemented, **never used**, and
unsafe: the checkpoint recorded `tok_path` and nothing read it back, so a resume could silently pair
weights with a different run's merges or with a fresh 512-token vocabulary. `2ba3ac1` records
`tok_vocab`/`tok_merges` and refuses on mismatch; `pilot-add`'s hardcoded RESUME path was replaced with
`RESUME_FROM=<dir>`.

**Outcome.** **VINDICATED — the researcher used it that same evening for the project's only
continual-learning run** (`X49`, `06_CONTINUAL_LEARNING.md`). The idea, the hardening it required, and the
run are all within about six hours of each other.

---
---

# Phase (viii) — 2026-08-14 .. 08-15 · Instrument fixes, the population 2x2, memory, per-expert LR

## A90 — The population 2x2: growth vs size

**2026-08-14** · **[quote unconfirmed — an `AskUserQuestion` selection, "Growth vs size first"]** · and
`U0433`

> "Lets first address why the seeds varied so differently earlier. Then we can run and try this, with a
> different series of configs that we should decide together. We can relook into the 8kvmax again." — `U0433`

**Reading.** Isolate whether the damage comes from having many experts or from *ramping to* many experts —
the sequencing instruction in the verified quote is his, the 2x2 choice is recorded only as a tool answer.

**Response.** Arms specified and plumbing verified (`cap = max(n0, FAB_NMAX)`; `MAX_DOMAINS` pinned for
arm C), then run at 3 seeds each (`cc0a377`).

**Outcome.** **The cleanest experiment in the project, and it is OPEN.** `X46`: A 2.117 ± 0.326 ·
B 1.999 ± 0.080 · C 2.091 ± 0.180 · D 3.384 ± 2.074. B is the best on record — and `INV-15` / `a5cc7ea` then
established that **B ran with no culling at all**, because founders had no birthday (`A93`). `04_RESULTS.md`
and `07_WIP.md` both record that arm B as measured **is no longer reproducible at HEAD**, and that HEAD's
defaults are arm D.

---

## A91 — Mid-run expandable VMAX and expert count, when both are at cap and the loss has plateaued

**2026-08-14** · **[quote unconfirmed — survives only inside a Claude-written compaction summary]** ·
approval verified at `U0434`

> "Build all 3." — `U0434`

**Reading (paraphrased).** Growability applied to the two hard caps: lift them during a run rather than
choosing them before it.

**Response.** Claude scoped both — expert count is cheap (the cap is already preallocated and unused rows
are zero-B identities, so it is a policy change) while expandable VMAX depends on `LOSS_MASK_DEAD` working,
since building at 8192 means carrying 6,144 dead rows from step 0. Approval given.

**Outcome.** **NEVER IMPLEMENTED.** No commit implements either. Of the three things "Build all 3"
approved, only the rescue mechanism (`A92`) was built.

---

## A92 — Rescue before cull: raise the learning rate or mutation for a threatened expert

**2026-08-14 .. 08-15** · `U0444`, `U0447` (verified); 2026-08-14 origin **[quote unconfirmed]** · raised 2x

> "Fifth, SInce we have the custom learning rates per expert, lets have a mechanism, where if the expert
> is near bottom, it has an increased LR or mutation chance. (since its already pretty poor)" — `U0444`

> "For 5, on the bottom ranked experts, this is assuming they are outside of their safe phase." — `U0447`

**Reading.** Selection should raise the mutation rate, not only prune — a threatened expert is a candidate
for change, not only for removal.

**Response.** Claude endorsed the shape — *"selection pressure raising mutation rate is how you escape a
local optimum"* — and built `FAB_RESCUE` (`e2db890`) and `FAB_LR_BOOST` (`752b1ff`), verified at
`FAB_LR_BOOST=3` with experts spanning 1.00e-04..4.24e-03 while the global rate had annealed to 1.54e-04, a
27× spread. Then gated on grace per the second quote (`e25d9b5`, re-anchored to the use-clock in `9146136`).

**Outcome.** **NEVER MEASURED.** Toy scale only. `07_WIP.md` records `FAB_LR_BOOST` as **uncommitted in the
working tree at HEAD**, appearing in no commit message.

---

## A93 — Founders had no birthday, so the founding population was immortal

**2026-08-15** · `U0443`

> "You mentioned you uncovered something. Fix the issue, since its a pretty big one" — `U0443`

**Reading.** Short, and correctly weighted: this is the one that invalidates the best result in the project.

**Response.** `a5cc7ea` — `fab_born` added to the checkpoint with resume backfill, and `fab.age()`
defaulting to born-at-0 so a missing record fails toward **OLD** rather than toward immune. Measured
contrast on identical config and seed against a genuinely pre-fix commit: **0 culls / 24 experts before, 6
culls / 24 → 8 after.**

**Outcome.** **VINDICATED.** `INV-15`, `05_ERRORS.md` §6, `01_TIMELINE.md` `E15`. Consequence: arm B
(`FAB_N0=2048`, all founders) had **zero culls for its entire life**, so the best number on record was
produced by a configuration with no selection in it — and the fix means it cannot be reproduced at HEAD
without pinning the old behaviour.

---

## A94 — Baseline on arm B, then layer gradual growth on top; and cap the newborn fraction

**2026-08-15** · `U0436`, `U0437`, `U0438`, `U0439` · raised 4x

> "Yes we can do that, then add on a gradual increase in experts and perhaps vmax to the mix, we may get
> the better scalable results, and hopefully reproduce the 2048 results with the 4096 […] We can
> temporarily set it as the baseline." — `U0436`

> "How does it look? Did it expand?" — `U0437`

> "The goal is to get safely below 2, ideally hit 1.5 this run. For the ramping, what is the maximum rate
> it can do, in terms of percent new? If there is none, lets set one" — `U0438`

> "Lets change instead to burst of 1, and 4%, since cull is 8%" — `U0439`

**Response.** Arm B adopted as the baseline for every subsequent recommended run. `GROW_CAP` built
(`e2db890`, `41d2c5d`); `FAB_NEW_FRAC` added (`f4b2e9b`), measured as uncapped population 256 with a
worst single event of 100% new vs capped population 15 with a worst event of 33%; then `FAB_BURST` 3 → 1
and the newborn cap 10% → 4% (`6d5e6d7`).

**Outcome.** **UNCLEAR, through an accident that was itself informative** — `INV-19`. The pilot
meant to test `GROW_CAP` **ran on a stale commit (`e9f2e58`) that predates it**, so the knobs were silently ignored and
it became an unconditional ramp 2048 → 4096: mean **2.009**, spread **0.160**. The intended run was never
executed. What the accident established is worth keeping: **ramp 2048 → 4096 is harmless where ramp
3 → 4096 (arm D, 3.384) is not.** Two further caveats: the 1.5 b/B target was not met — best on record
stayed 1.960 — and the comment justifying the 4% cap was later found wrong, because `MANAGE_EVERY` is 500
not 50 and `FAB_CULL_FRAC` subsequently became 0.02, **inverting** the property the change was made to
guarantee.

---

## A95 — Four times more English, from a source that is actually genuine text

**2026-08-15** · `U0439`

> "Since the target goal is lower, lets allow for a larger data set. Lets do 4x larger english. Also make
> sure to use a good source, since when I look at some of the seeded samples, they dont always look like
> genuine text." — `U0439`

**Response.** Checked: the seeds were genuine fineweb-edu prose, and the apparent junk was an artefact of
110-character mid-sentence seed windows. `--min-score` / `--score-field` added to `fetch_big.py`
(`6d5e6d7`), and `STREAM_LEN=16000000` with a 0.5 GB re-fetch used for the 18-epoch run.

**Outcome.** **The re-fetch silently changed the corpus** — order-1 moved **3.440 → 3.747** —
confounding that run (`INV-32`: against each run's own order-1 anchor, 18 epochs bought nothing). `01_TIMELINE.md` Appendix B is the corpus lineage this created; without it the `held_out` column
is not comparable down the table.

---

## A96 — The learning rate should be a decaying envelope over an oscillation, and it should be per-expert

**2026-08-15** · `U0442`, `U0447`, `U0449` · raised 3x, developing each time

> "I am starting to think cosine may not be the right way to go. It should start high, but gradually
> lower, fluctuatging, but lowering in peak of fluctuations. Also, I want to have the LR schedules of each
> expert to be independent, running on what I described" — `U0442`

> "Importantly, having LR Epochs as a per expert effect rather than system encompassing is more conductive
> to the evolutionary learning, at least in my perspective." — `U0447`

> "Lets use Smith's Cyclical LR, but implemented in a per expert scale then, with each expert counting
> down their age. Lets adjust things to only be when the specific expert is selected, so age is dependent
> on the expert's use. Lets make the safe period dependent on this instead" — `U0449`

**Reading.** A population of experts born at different times should not share one global schedule phase.
The clock should be the expert's own **selections**, not the run's steps.

**Response.** `LR_DECAY` envelope and `FAB_LR_OWN` (`91fd815`) — peaks 100% / 76% / 29% at decay=1.0,
experts spanning 1.00e-04..1.99e-03 while global sat at 9.65e-04. Then Smith triangular2 per expert,
clocked in **selections** on `fab.uage`, phase-shifted so a newborn starts at peak, with `FAB_GRACE` 3000
steps → 48 selections (`9146136`, `95aa336`). Building `LR_DECAY` is also what uncovered `A93`.

**Outcome.** **OPEN, and unvalidated.** Toy and smoke scale only — the pilot the researcher launched at
17:08 on 2026-08-15 had not reported by the end of the transcript. Two known flaws in the envelope were
found by the LR literature agent and **not fixed**: it multiplies the floor as well as the peak, and it
re-introduces horizon dependence. And the literature search came back **empty** on prior art for
per-group independent LR *phase* — which makes it either novel or unexamined, and the record does not say
which.

---

## A97 — An expert aging out is acceptable; keep culling, but give everyone a route back

**2026-08-15** · `U0447`, `U0449` · raised 2x

> "Since the system relies much on an evolutionary mechanism, certain experts "aging out" and not learning
> is not a large issue. If they contain error, ideally, they will eventually be replaced by their own "new
> successors", with long enough runs." — `U0447`

> "Balance loss can be implemented on a smaller scale. I still want culling since it is semicritical to our
> evolutionary mechanism. Balance will help ensure that each expert has a chance." — `U0449`

**Response.** Claude partly pushed back and acted: when the envelope decayed to zero for **every** survivor
it added `FAB_LR_AMIN` (0.05, raised to 0.15), arguing *"Your framing tolerates an individual aging out; it
shouldn't be imposed on every survivor by construction, or birth-and-death is the only adaptation left."*
`BAL_FLOOR=0.15` added because `BAL_WARM` previously decayed the balance weight to **exactly zero**, after
which an unselected expert had no route back — and under the new use-clock an unselected expert is also
frozen at its use-age, so the cull can never reach it either.

**Outcome.** **BUILT, never measured.** The two asks turned out to be one mechanism.

---

## A98 — Total memory overlap is a design failure, and the store must produce a real signal

**2026-08-15** · `U0445`, `U0447` · raised 2x

> "Another note: the fact that the memories from the python run has largely overwritten the english, it
> means that the domains have not been fully isolated. Better memory control is likely also needed. We
> need to re evaluate how it currently works." — `U0445`

> "On memory, overlap experts is ok and expected, but having all experts have been overlapped is an
> inherent issue. Likely separation or distinction, on router level between python and english is not
> sufficient. Use based recency is better I think. […] Lets give a real signal." — `U0447`

**Response.** This is the second half of `A33`; the findings and the fixes (`daf9f89`, `MEM_PROBE_EVERY`
/ `MEM_PROBE_N`, `EVICT=lru` redefined as least-recently-**retrieved**) are recorded there.

**Outcome.** **VINDICATED.** The observation was correct and the mechanism was worse than suspected —
every eviction rule claiming to rank by utility was ranking a constant (`INV-24`).

---

## A99 — "Default 1 sounds like a poor and faulty decision in your past"

**2026-08-15** · `U0447`

> "Fix the bugs that you've mentioned. Default 1 sounds like a poor and faulty decision in your past. Treat
> past comments as a rough statement, never as anything definitive, especially since it can drastically
> change with different structures and architecture." — `U0447`

**Response.** `MEM_PER_EXPERT` flipped to 0 in both the read site and the `_SPEC` registry, and its comment
rewritten to say the cited numbers are "a rough indication from one configuration, not a verdict"
(`e25d9b5`).

**Outcome.** **VINDICATED.** This is `INV-06`: the knob read `_i(...,1)` against a comment saying DEFAULT
OFF, so every run in the project used the partitioned store, degrading **every memory result in the record**
to unattributable. The general instruction is the one `09_COMMENT_AUDIT.md` builds its highest-risk category
around: comments that argue from a knob's value. See also `A74`.

---

## A100 — A graceful stop for a running sweep

**2026-08-15** · `U0444`

> "Second, I want to stop the second and 3rd seed without ctrl C or force kill. How would I do so?" — `U0444`

**Response.** `_stopped` / STOP-file handling in `longrun.sh`, wired into `seeds`/`grid`/`repeat` (`752b1ff`),
smoke-verified; plus a manual workaround for the run already in flight.

**Outcome.** **BUILT — and uncommitted at HEAD.** `07_WIP.md` lists it, with `FAB_LR_BOOST`, as sitting in
the working tree in a repo whose container has rolled back at least three times.

---

## A101 — Survey the literature, with agents, and then outside Claude Code

**2026-08-15** · `U0444`, `U0447`, `U0450`, `U0451`, `U0452` · raised 5x

> "Third, Send an agent to look at existing research for the learning rates, to see what has been tried.
> Make a list of all. Then The most popular ones. / Fourth, Do the third for each aspect of what we have
> created, with separate agents. These will be for me to review." — `U0444`

> "Since webfetch was blocked, provide me what to tell a non claude code session, and I will provide to you
> or digest myself. (also it should alert me if something is blocked)" — `U0447`

> "I've run the research prompt and gotten an answer. Before I pass it to you, is there anything else I
> should add? or tangential areas of search that would be relevant and helpful?" — `U0451`

> "This is its report. No subagents were used. I was mistaken about the abilities, but it should be
> fine" — `U0452`

**Response.** Four surveys — `research_lr_schedules.md` (882 lines), `research_tokenizer.md` (500),
`research_experts_routing.md` (1082), `research_continual_memory.md` (943) — all committed and all flagged
as *"model recollection, not sourced literature"* because WebFetch was `EGRESS_BLOCKED` at the proxy. Then
`notes/EXTERNAL_RESEARCH_BRIEF.md` (`cc544ce`) with a measured egress status and a paste-ready prompt; the
researcher ran it elsewhere and returned 16 files, archived verbatim to `notes/_evidence/litreview/`.

**Outcome.** **VINDICATED — the blocked-network instruction in particular.** Every doc agent since has been
required to report the literal word BLOCKED. `LITREVIEW_FINDINGS.md` records what survived checking: **three
claims changed a project reading** (the GPT-2 b/B anchor, per-arm σ, and LRU-on-retrieval as a scan
pathology — which contradicts `A98`, unresolved), and **two warnings were checked and rejected** (the
4096× balance-loss error, weight-decay rescaling). One agent finding was verified and fixed as `f8599b7`.

---

## A102 — "At minimum, it needs to include suggested ideas, by me"

**2026-08-15** · `U0444`, `U0450`, `U0455` · raised 3x

> "Sixth, Have an agent or series of agents to go through our entire chat history, and document them on the
> github page. At minimum, it needs to include suggested ideas, by me. What was tested, results." — `U0444`

> "(Also note that although you will say it definitively means something, it is likely often wrong, since
> there is a high likelihood that it was either due to chance, since we have not optimized anything, and are
> still building out strategy, or had an inherent error in interpretation or why it was done." — `U0444`

> "Notes in the code that are extranoues and do not describe the usage should be moved to the notes. I
> expect this to be long and thorough" — `U0444`

> "I want the agents to go through the entire history, even if it is outside your current context
> window." — `U0455`

**Response.** `notes/DOC_PLAN.md`, then the file set. The second quote became **the caveat block at the top
of this and every other file**, adopted verbatim, with the enforcement rule that a claim without its commit,
its n, and its instrument era does not go in. The fourth quote forced the transcript extraction that this
file is written from: 42 MB of session JSONL → 455 turns in `user_turns.md`, 12 chunk files, and 12
structured extractions.

**Outcome.** **BUILT — this file is the direct answer to the first quote,** and the extraction the fourth
quote demanded is the only reason it could be written from the researcher's words rather than from commit
messages. The third quote is `09_COMMENT_AUDIT.md`, which is **a plan, not an executed pass**: 354 blocks
classified, no comment moved.

---

## A103 — Validate the new lifecycle changes in a pilot before reviewing the documentation

**2026-08-15** · `U0449`

> "I want to test the new changes in a pilot run before I go through the doc" — `U0449`

**Response.** Pilot launched (`seeds 2`, `FAB_GROW=0 FAB_N0=2048 EPOCHS=18 SEED_CKPT=1`); confirmed running
at 17:08.

**Outcome.** **OPEN.** The transcript ends before it reported. Nothing in `runs.csv` corresponds to it, so
the per-expert LR work (`A96`), the rescue mechanism (`A92`), the balance floor (`A97`) and the memory read
probe (`A98`) are all **unvalidated at pilot scale at HEAD**.

---
---

# Thematic index

Follow one thread. Entry ids are `A01`..`A103`; **bold** marks the entries where the record most clearly
supports the researcher against Claude's position at the time.

### Tokenizer and minting
`A18` vocabulary cap · `A41` reject freezing · `A59` **it isn't the tokenizer** · `A61` minted tokens keep
parameters · `A62` minting is non-negotiable · **`A64` the frozen arm was only half off** · `A67` small
tokens go stale · `A77` run longer, don't mint harder · `A79` anchor by appearances · `A81` the meaning gate
and probation · `A85` VMAX non-monotonicity

### Expert population, routing, selection
`A03` redundancy with emergent subspecialty · `A04` subcontracting · `A29` the count is too low ·
`A30` burst growth · **`A31` what is a node** · `A45` insufficient individually · `A46` breadth cap ·
`A47` replication, mutation, crossover · **`A48` discovery and the missing cull** · `A49` selection on
sustained error · `A50` lineage · **`A51` the router predicts weights (`rm-predict`)** · **`A52` provenance,
HALT, gradient reach** · `A54` toy scale · `A55` staged depth · **`A56` the chained society** ·
`A57` emergent diversity · `A90` the population 2x2 · `A92` rescue before cull · **`A93` founders had no
birthday** · `A94` newborn fraction · `A97` aging out and the balance floor

### Memory
`A06` the knowledge base · `A12` reject the quota · `A20` partial compartmentalization · **`A33` per-expert
quota, ranked by use — specified 07-24, in force 08-15** · `A87` context drift · **`A98` total overlap and
the real signal** · **`A99` default 1 was a bad decision**

### Learning rate
**`A59` the schedule, not the tokenizer** · `A78` restarts vs hold · `A96` decaying envelope, per-expert,
clocked in selections

### Continual learning
`A02` the north star · **`A36` non-stationarity was never on** · `A43` English first, add later ·
`A62` minting is critical to it · `A70` the 40 GB run that never ran · **`A89` carry-over as a designed
capability** · `A91` mid-run expansion · `A103` the unvalidated pilot

### World model, verification, senses
`A05` sense = modality · `A07`/`A68` tool-experts · `A08` router as embedder · **`A10` surprise is a learning
driver** · `A11` verification by reconstruction · `A19` active learning · `A21` the world model

### Domains
`A24` don't disable them for speed · **`A32` a scaffold, not a target** · `A38` English-only ·
**`A39` the fabric was off** · `A40` byte-level signatures · `A42` domains as prediction

### Methodology and measurement
`A15` the runs are too short · `A22` under one epoch · `A27` GPT-2 as the anchor · **`A28` "does it contain
everything?"** · `A35` don't optimise the proxy · `A37` add the instruments · `A60` which checkpoint ·
`A63` over-optimising the spike · `A65` spikes as search · `A66` fabric contribution · `A69` anti-overfitting ·
`A71` **n=1 — the wrong call** · `A72` seed independence and sample size · `A76` the frozen defect ·
`A84` vmax8k reopened · **`A86` fix the amplifier, don't measure the noise** · **`A88` state leak — refuted by
his own control**

### Process, tooling, provenance
`A01` the handoff tree · `A13` naming · `A14` phone-and-fresh-box commands · **`A17` checkpoints (7 raises)** ·
`A16` real data · `A25` send agents · `A26` disk streaming · `A34` who runs what, where · `A44` pilot before
GB · `A53` **the banner lies and the commit line** · `A58` unattended grid · **`A73` disentangle the levers
(7 raises, still open)** · **`A74` outdated comments** · `A75` redesign the tests · `A80` the never-fired
audit · `A82` runs.csv · `A83` are the smoke tests updated · `A100` graceful stop · `A101` the literature
survey · `A102` this documentation set

---

## What this file does not establish

- **It does not rank the ideas.** Verdicts describe what the record shows, not what is true. Under the
  caveat at the top, a **VINDICATED** on n=1 means "the measurement agreed", not "the idea is right".
- **It does not cover Claude's proposals.** Many mechanisms in this system were proposed by Claude and
  approved without comment. Those live in `03_EXPERIMENTS.md` and `07_WIP.md`.
- **Attribution before 2026-07-22 is thinner than it looks.** The earliest strategic statements were given
  through `AskUserQuestion` and are not in `user_turns.md`; `handoff/NORTH_STAR.md` is a same-day record of
  them, not a transcript.
- **Counting raises is not counting emphasis.** A theme raised once and acted on immediately (`A93`) can
  matter more than one raised seven times (`A73`). The raise count measures how often the instruction had to
  be repeated, which is a fact about the response, not about the idea.
