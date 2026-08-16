# 10 — HISTORY FINDINGS

> Nothing in this project has been optimised. Strategy is still being built. Sample sizes are tiny
> — usually n=1, occasionally n=3 — and the measured seed spread on a single arm has reached
> 1.227 b/B (`33a9299`), larger than the gap between any two architectures ever compared here.
> Several confidently-stated findings were later retracted when the measurement turned out to be
> broken. Every entry records **what was observed under these conditions**, never **what is true**.
> Where a result was later invalidated, the invalidation is stated next to it, not in a footnote.

---

## What this file is

The other nine files were written from the commit log and the source. **This one is written from the
conversation**, and covers only what the conversation records and the repository does not: claims
made and withdrawn, time lost to infrastructure, decisions agreed and never implemented,
instructions the researcher had to give twice, and how the 26 days were actually spent.

A repo-derived file cannot contain any of this. A commit records the fix; it does not record that the
same claim was asserted confidently for ten turns first, that a GPU-day was spent on a run that saved
nothing, or that an instruction was given three times before it landed. Those are the facts most
likely to repeat, so they are the ones worth writing down.

**Primary source**: `notes/_evidence/chat/user_turns.md` — all 455 human turns, verbatim, in order
(`U0001`..`U0455`), and `notes/_evidence/chat/chunks/` — the full distilled transcript in 12
chronological chunks. Every quotation below is cited to one of these and was checked against it.

**Citation convention.**

| form | means |
|---|---|
| `U0189` (2026-07-31) | a turn the researcher typed, in `user_turns.md` |
| `chunk_07.md:6892` | an assistant turn, cited by chunk file and line |

`user_turns.md` excludes harness-injected turns, which means **AskUserQuestion answers are not in
it** even though they are genuine researcher input. Where such an answer is quoted it is cited to
`chunks/` and labelled, never given a turn number.

**Dependencies.** `05_ERRORS.md`'s `INV-01`..`INV-44` list is **authoritative** on what does not
stand, and §1 below cross-references it rather than re-deriving it. `01_TIMELINE.md`'s `E1`..`E15`
epoch boundaries are cited by id. `06_CONTINUAL_LEARNING.md` §0 establishes the disproportion that §5
here dates. `04_RESULTS.md` owns the numbers.

**Counts used here.** 455 human turns; 279 commits on `rm-predict` as of `86fd64a` (the other files
were written against earlier snapshots and cite 259 and 267 — the log grew while they were being
written, which is itself a fact about how this record was made); 42 rows in `runs.csv`.

---

# §1. RETRACTIONS

The highest-value section, because a retraction is the only direct evidence that a claim was believed
before it was tested — and the record contains **210 of them**, one for roughly every two commits.

## §1.1 How to read this

Each entry gives the claim as asserted, dated; the correction, dated; and an **INV** column.

- **`INV-nn`** — the invalidation reached the repo record via `05_ERRORS.md`.
- **`— not in INV`** — **the retraction happened in conversation and never reached the repo record.**
  This is the flag the section exists for. A claim withdrawn only in chat is a claim that will be
  rediscovered from the commit log, the code comments, or the run logs, all of which still assert it.

Where the withdrawn claim was *written into the source or a commit message*, that is stated, because
those are the copies that survive.

## §1.2 Retractions that DID reach the repo record

Listed compactly; `05_ERRORS.md` is the authority and holds the detail. These are here only so the
conversational form of each is on record beside the ones that got lost.

| # | claim, as asserted | correction | INV |
|---|---|---|---|
| R1 | *"Verification is real"* — AUC 0.980 vs 0.907, precision@1% 100% (07-21T22:41) | *"My earlier 'Verification is real' was **overclaimed off the standalone**; the full loop is the truth, and I should have hedged harder"* (`chunk_01.md:6152`, 07-22T14:31). Product loop: 0.3% precision, three runs | `INV-38` |
| R2 | *"Your hypothesis is confirmed, decisively"* — domain assembly works, purity 0.54→0.96 (`chunk_03.md:6924`, 07-25T04:46) | *"**I have to retract what I told you.** … That metric cannot support the claim. Purity rises monotonically with fragmentation"* (`chunk_03.md:7591`, 07-25T08:06) | `INV-16` |
| R3 | *"1 of 4096 experts used"* — held ~10 turns, four fixes built on it | *"I read it as evidence of catastrophic concentration for something like ten turns, and built four failed fixes on top of that reading"* (`chunk_07.md:90`, 08-04T19:48). Whole-run: 84 distinct, top 3.9% | `INV-17` |
| R4 | *"Freezing the vocabulary removes the divergence entirely"* | *"**Freezing the tokenizer hurts.** … The entire tokenizer hypothesis … was measuring the LR bug"* (`chunk_09.md:2060`, 08-10T19:12) | `INV-29`, `INV-30` |
| R5 | *"a single run of this system carries roughly ±1.5 b/B of irreducible noise"* (`chunk_11.md:255`, 08-13T22:10) | *"**Found it, and it isn't noise.**"* — diagnostics drew from the same RNG as the stream, so *how much you measured decided what you trained on* (`chunk_11.md:3525`, 08-13T23:07) | `INV-13` (= `E11`) |
| R6 | *"B IS THE BEST ARM ON RECORD"* — mean 1.999, spread 0.080 | Founders had no birthday, so arm B ran with **zero culls for its entire life**; not reproducible at HEAD | `INV-15` (= `E14`) |
| R7 | *"`MODEL=transformer` has never been run at pilot scale"* | *"It has already run twice — and I need to correct what I told you last turn"*; both runs are arm D, pre-instrument-fix | `INV-33` |
| R8 | *"FABRIC alone is worth +0.709 bits/byte"* — used to justify the `FABRIC=1` default | Eval-time knockout, not a retrained ablation. Retrained: **3.089 vs 3.090** | `INV-36` |
| R9 | *"vmax8k is eliminated — tested three ways"* | Every vmax8k run carried a known defect; *"vmax8k goes back in the candidate set, untested"* (08-12T21:36, after `U0407` objected) | `INV-31` |
| R10 | *"staged depth did not help"* (the researcher's own proposal, reported as failed) | `maybe_deepen` had never executed; *"I'm **withdrawing** the numbers I gave against them rather than standing on them"* | `INV-08` |
| R11 | *"the weight-prediction term is 1–2% of the routing decision"* | Measured on a 64-expert toy; at 4096 it is 93%. *"the direction of that finding was wrong"* | `INV-27` |
| R12 | *"Saving a checkpoint corrupts the router. That's the 1.594"* | 125 corrupting nudges against 240,650 real = 0.052%. *"That cannot accumulate to 1.594 bits/byte"* | `INV-12` |
| R13 | The dead-row series *"0% → 2.2, 41% → 3.561, 75% → 6.114"*, repeated as monotone and catastrophic | First controlled test: **+0.060 at 1.1σ**. *"I have been repeating it as though it were [established]"* | `INV-34` |
| R14 | *"memory now HELPS coherence"* / *"the fabric buys coherence"* / *"memory HURTS coherence"* | All three were one sample flipping in a four-sample mean with SE 0.25 | `INV-20` |
| R15 | *"RETOK_EVERY=0 is harmless cleanup"* | It costs 0.293 b/B — and later, it also silently disabled signature batching, so the pair was never single-knob | `INV-10` |
| R16 | *"the retok guard is verified working — 11 skipped on frozen, zero on base"* | At real scale **both** branches were dead; three 18-epoch runs report nothing about re-segmentation | `INV-09` (= `E9`) |
| R17 | *"the DIV_W=0.05 pilot"* | Byte-identical to the DIV_W=0 run in every figure. *"Twenty minutes of GPU time measured the previous configuration"* | `INV-44` |
| R18 | *"the router HALTs 90%, mean routed depth 0.10 of 4"* + *"PONDER_WARM never completes"* — used to justify the pilot's length | Both were about code the run did not execute. *"Second time this session a justification of mine was about inert code"* | `INV-40` |
| R19 | *"8 epochs beat 18"* | `EPOCHS` set the cosine horizon too — 11.0× different LR at step 44000 | `INV-30` |
| R20 | The A100 bench component ranking and parameter counts | `D_MODEL_B` was read by nothing; both models ran at d=128 | `INV-01` (= `E1`) |

## §1.3 Retractions that did NOT reach the repo record — **flagged**

These withdrawals exist only in the conversation. Each is a live hazard: the claim is still asserted
somewhere durable, or the reasoning that produced it is still uncorrected.

### R21 — *"The T5–T32 gap is real and unrecoverable from the repo"*
**Asserted** 2026-07-21T18:19, and **written into `docs/HANDOFF.md`**: *"That history lived in the
migrated chat and on the GPU logs; it is not recoverable from the repo. Do not fabricate it."*
(`chunk_01.md:812`)
**Retracted** 2026-07-21T19:06: *"My earlier claim that the **T5–T32 history was 'unrecoverable'**
was wrong. The prior context reconstructed the entire history (Phases 0–11) from the still-visible
conversation."* Root cause: `STATE.md` had **silently stopped being written to disk after ~T4** while
later turns kept narrating edits to it (`chunk_01.md:1241`).
**Why it matters** — this is the project's founding lesson (a written record that stops being written
while everything continues to reference it), and it is the same failure class as `INV-06`
(`MEM_PER_EXPERT`'s comment recording a decision the code never implemented) fully three weeks later.
Not in INV; the handoff note was corrected, the pattern was not carried forward. **— not in INV**

### R22 — *"It survived and finished on its own — the day is saved"*
**Asserted** 2026-07-23T20:51 (`chunk_02.md:1572`), on seeing `WHOLE SYSTEM RUN COMPLETE`.
**Retracted** 2026-07-23T20:57: *"I have to correct myself — I got ahead of the facts and I'm sorry
for the false relief. **There is no checkpoint. The day's compute is lost for a promptable model.**
… `WHOLE SYSTEM RUN COMPLETE` printed anyway because that line is in the bash script *after* the
Python call. I read that line as success. It wasn't."*
The researcher had already verified it: `ls: cannot access 'runs/fineweb/ckpt.pt': No such file or
directory` (`U0045`).
**Why it matters** — a ~22-hour H100 run reaching ~432k steps produced nothing, and a success banner
printed over the failure. The banner-prints-over-failure class recurs at least four more times
(`R31`, `R33`, `INV-41`). Absent from both the INV list and `05_ERRORS.md`. **— not in INV**

### R23 — *"the only thing standing between you and readable language is clean large data"*
**Asserted** 2026-07-22T21:47: the 12x-data corpus is *inherently* dirty, so FineWeb is required.
**Retracted** 2026-07-22T21:51: the corpus was not inherently dirty — `fetch_data.sh`'s tag-stripper
matched `[A-Z$]` while NLTK Brown tags every token in **lowercase**. *"you don't need fineweb just to
get clean text — the same fast 85MB NLTK corpus is clean now."*
The one-line bug is in `05_ERRORS.md` (§`E`, "lowercase"); **the strategic conclusion drawn from it —
that data volume was the blocker — is not invalidated anywhere.** It shaped the next several days of
fetch work. **— not in INV**

### R24 — the bottleneck, asserted three times, wrong three times
1. *"we're CPU-bound — online re-tokenization + managing ~700 domains, none of which touch the GPU.
   That's also why 4×H100 wouldn't help"* (07-23/24) — **asserted without ever profiling**.
2. Retracted 07-24T03:43: *"I asserted 'CPU-bound' without ever profiling it — that's exactly the
   unverified-claim habit I said I'd stop."* Deferred to the researcher's *"gpu bound, due to the
   reverse encoders"* (`U0069`).
3. The 5-agent profile then refuted **the researcher too**: the Reconstructor is OFF by default
   (`VERIFY=selfcon`) and contributes zero — *"effectively a red herring for the GPU-bound symptom."*
   The real driver was the **forward** contrastive encoder.
4. Then *"mem_key is the dominant cost"* → *"The profiler overturned my hypothesis. It is not — it's
   4-5%."*

**Why it matters** — four bottleneck claims, three wrong, one of them the researcher's, all before a
single profiler run existed. `PROFILE=1` was built *after* this sequence, not before it.
**— not in INV**

### R25 — *"the encoder is 85% of the loop"*
**Asserted** repeatedly 07-24 as the profile finding and used for throughput planning.
**Retracted** 07-24T18:10: `contrastive_step` is shift-gated. Every profile shown used the
4-domain mix, which switches constantly; **on single-domain data the gate throttles ~12× and the
encoder is 33%.** *"true for multi-domain streams, and not a general fact."* The ~12% speedup was
also measured under the encoder-heavy condition only.
**Why it matters** — the single-domain English regime is what every later pilot runs, so the headline
profile number never described the runs it was used to plan. **— not in INV**

### R26 — *"the cap is doing the work"*
**Asserted** 07-25T15:29: 64 live domains equalled `MAX_DOMAINS=64`, so the ceiling was setting the
population.
**Retracted** 07-25T16:24: with `MAX_DOMAINS=10⁶` the identical run still ends at 64 domains and
`asm.capped == 0`. Cap-**invariant**. *"The 64 was coincidence, and I read a matching number as
causation."* **— not in INV**

### R27 — *"the signatures do not form corpus-level clusters — within-domain spread is 2.4× the between-domain distance. No clustering algorithm can recover clusters that overlap 2.4:1"*
**Asserted** 07-25T16:17 as the root cause of the whole fragmentation campaign.
**Retracted** 07-25T16:24 (`chunk_04.md:578`): *"**false.** 1-NN corpus accuracy is **84-95%** at
every N ≥ 200, against 25% chance. The untrained **bigram control alone scores AUC 0.887**. … My
within/between = 2.4:1 was computed over *domain* centroids — 53 fragments of 4 corpora — so of
course they overlapped. **I measured the symptom and called it the cause.**"*
**Why it matters** — this is the clearest single instance of the dominant failure mode, and the
phrase names it. Not in INV. **— not in INV**

### R28 — the completeness metric was homogeneity
**Asserted** 07-25T15:29: the DomainAssembler rewrite improved things — *"64 domains, completeness
0.89, V-measure 0.91."*
**Retracted** 07-25T15:30: the formula computed `H(true|domain)`, which is **homogeneity**, and
behaves like purity. Proven synthetically (62 clusters / 4 classes → homogeneity 1.00, completeness
0.34, V 0.51). *"That's **twice now** I've shipped a metric that flattered the result."*
**Why it matters** — a self-authored metric that inflated a self-authored result, caught only because
Claude built the synthetic control. The *first* of the two is `R28a` below. **— not in INV**

### R28a — the `COLLAPSE CHECK` verdict
Shipped one commit earlier, then fired *"signature space is COLLAPSED -- fix the ENCODER, not the
assign rule"* at −5.2σ on a run whose encoder was measurably healthy (true silhouette +0.25, 1-NN
0.90, which itself scores −4.8σ). Retracted and pushed as `ab3a311` 07-27T19:11.
**Present in `05_ERRORS.md` as `E7.3` but absent from the INV list** — worth noting because it means
the INV list is not a complete index of retracted findings even for findings the file records.

### R29 — *"1-NN accuracy peaks around N=1000-4000 and degrades after; more encoder training makes corpus identity WORSE"*
**Asserted** repeatedly 07-25 → 07-27 from the probe and the sweep, and used to argue
`ENC_WARMUP=30000` was past optimum.
**Retracted** 07-27T15:50: a dedicated probe on the real corpora shows 1-NN rising **monotonically**
to 0.982 at 8000 steps. *"I should not have repeated it as established."* What degrades is the
between/within *ratio*, because `d_within` inflates 8.7× while `d_between` saturates.
**— not in INV**

### R30 — expert-identity collapse
**Asserted** 08-04T19:24 → 19:30: every expert embeds to an identical identity vector, nearest-
neighbour distance **0.000**. Presented as the root cause of routing concentration; **two changes
were shipped on it** (VICReg on identities, per-step embedder training).
**Retracted** 08-04T19:34 (`chunk_07.md:25`): *"**Identities were never collapsed.** The `0.000` I
diagnosed collapse from was the **stale variable** — captured inside `spawn_from`, which only runs
when the spawn bar is met, so it printed its initialiser. I read an uninitialised number as a
measurement and drew a confident conclusion from it. Mean pairwise separation is 0.857."*
The two changes were kept, but *"they were not fixing what I said they were fixing."*
**Why it matters** — `INV-17` covers the sibling misreading (*"1 of 4096"*) from the same hour;
this one, which shipped code, is not covered. **— not in INV**

### R31 — *"SOCIETY=1 cannot satisfy your requirement by construction"*
**Asserted** 08-04T21:02: the society path is one-shot, *"there is no HALT and nothing to complete."*
**Retracted** 08-04T22:05, after `U0263` objected: *"**You're right, and my 'cannot by construction'
was wrong.** HALT *is* computed on the society path — and then thrown away"* — the learned branch
built a softmax over N+1 operators and sliced off column N. **— not in INV**

### R32 — the shared `q_route` refactor
**Asserted** during the 4096-expert scale work: collapsing the per-expert query projection into one
shared `q_route` was a pure scale optimisation (345 ms → 15 ms) with *"same expressiveness class."*
**Retracted** 08-04T16:49: *"I optimised away the thing that made the chain a chain"* — it removed
the transition's dependence on which expert held the mass. Verified numerically: all mass on expert 0
vs expert 4 gave an **identical** next distribution (`True`).
**Why it matters** — the chaining path, which is the architecture's stated point, was memoryless for
the entire period it was being measured. **— not in INV**

### R33 — `DIV_W=0` printed under **"OFF ON PURPOSE"**
**Asserted** by the config banner on every run from 08-03: `[config] OFF ON PURPOSE DIV_W=0.0 (expert
distinctness reward)` — i.e. a deliberate choice.
**Retracted** 08-05T03:45 (`chunk_07.md:6892`): society `DIV_W` indexed `_O` (rank-ordered) with a
global expert id → `IndexError` the instant anyone set it. *"**the one term in this system that
rewards experts for differing has been un-runnable since routing went per-window**, silently. That's
why `DIV_W=0` has sat in 'OFF ON PURPOSE' all this time; **it wasn't a choice, it was broken.**"*
It has still never been shown to change an outcome (the one pilot that tried is `INV-44`).
**— not in INV**

### R34 — *"banner lies are now structurally impossible"*
**Asserted** 08-05T12:42 on shipping the declarative config registry (`chunk_07.md:4890`: *"That
class of lie is now structurally impossible rather than fixed case by case."*)
**Retracted** 08-05T15:49 (`chunk_07.md:8837`): *"`CHAIN_ROUTE` **was not in the effective-config
table** — it switched the entire routing architecture for both of these pilots and neither log said
so. **That's one commit after I introduced the table to make exactly this impossible.**"*
And again 08-11T19:58: `TOK_ANCHOR=0.05` / `TOK_ANCHOR_TAU=4000` printed on the EFFECTIVE banner of
every run while **inert** (gated on `TOK_COMPOSE`, which is 0) — proven by three runs with a 500×
change in the anchor weight producing byte-identical reports. **— not in INV**

### R35 — the noise floor, asserted and reversed three times in nine days
| when | claim |
|---|---|
| 08-06T17:23 | *"The noise floor is 1.6 bits/byte … **every single-run comparison here is unmeasured**"* (`chunk_08.md:5927`) |
| 08-06T19:48 | *"My 'noise floor is 1.6 bits/byte' claim was wrong. **There is no run-to-run jitter.** Same seed, same config, same commit → bit-identical output, three times. So **single runs are valid**"* (`chunk_08.md:6358`) |
| 08-13T22:10 | *"a single run of this system carries roughly **±1.5 b/B** of irreducible noise"* (`chunk_11.md:255`) |
| 08-13T23:07 | *"**Found it, and it isn't noise.**"* → `INV-13` |

Only the last transition is INV'd. The middle reversal — *"single runs are valid"*, which governed
the methodology for a week — **is not**. **— not in INV**

### R36 — *"determinism means n=1 is enough per config"*
**Asserted** 08-06T19:48 and used repeatedly to justify one run per arm.
**Retracted** 08-07T13:59, prompted by `U0326`: *"That undoes something I told you three messages
ago. I said determinism means n=1 is enough per config. It's enough to **reproduce** a config — it is
**not enough to attribute a difference between two configs** … multiple seeds per arm are back on
the table."*
**Why it matters** — this is the methodological claim that most of `runs.csv` was collected under.
`INV-35` voids the single-run comparisons; the *reasoning* that licensed them is not recorded
anywhere in the repo. **— not in INV**

### R37 — the 18-agent bisect
**Asserted** 08-06T15:50: `99e5da0` *"is the one whose fingerprint matches top expert 5.9% → 39.0%"*;
the workflow's own automated verdict agreed.
**Retracted twice**: first 08-06T16:13, refuted on four independent grounds — *"99e5da0 is dead"*;
then entirely 08-06T17:21 (`chunk_08.md:5906`): *"**There was no regression.** Nothing to bisect. I
spent this entire thread chasing a phantom — first blaming `TOK_COMPOSE`, then `18fdd6c`, then
`99e5da0`, and running an 18-agent bisect over a window where nothing had changed. … That doesn't
make up for the GPU time."*
Cost: 1,188,868 subagent tokens, 362 tool uses, 46 minutes, plus the researcher's confirmation run.
**— not in INV**

### R38 — a withdrawn claim that is still in the commit log
Commit `be50e3a`'s message states: *"TOK_COMPOSE back to default off -- it is the only change that
moved the LEVEL."*
**Retracted** 08-06T17:23: *"Including claims I stated flatly, one of them in a commit message …
That was one run. It may still be true … but I don't have the evidence I claimed."*
The commit message is immutable and still says it. **— not in INV**

### R39 — *"the refactor is verified inert"*
**Asserted** 08-07T18:02: 13 of 13 smoke arms byte-identical pre- vs post-refactor.
**Retracted** 08-10T19:15, after `U0348` (*"Our main goal was whether the edits to the levers have
broken anything"*): *"my answer to the actual question is **not certified**."* The one like-for-like
pair differed (pre 3.502 vs post 2.365) and the smoke gate had not tested the question asked.
**— not in INV**

### R40 — the `equiv.sh` IDENTICAL verdict was produced by an unsound check
**Asserted** 08-10T22:09: `c14f876` vs `707f1af` → **IDENTICAL**, taken as proof the refactor was
inert.
**Retracted** 08-10T23:20: `equiv.sh` decided a side had "reached the report" by grepping for
`SIG_MODE=learned`, **which is on line 8 of every log** — so a run that died at startup counted as
complete. *"This means the earlier IDENTICAL verdict … was produced by an unsound check."*
**Why it matters** — the tool built specifically to answer *"has anything changed?"* returned a false
pass on its first real use. **— not in INV**

### R41 — the `main()` split seam
**Asserted** 08-10T23:10 and **committed**: *"The seam is measured and clean — the report battery …
needs exactly **39** values from the training half, out of 658 locals."*
**Retracted** after four bugs (two of which crashed the researcher's GPU runs — `NameError: _retok`,
`UnboundLocalError: assigns`): *"The seam I claimed was 39 values wide is actually **136** — and
eighty of those are leftover loop temporaries … **There is no clean place to cut.**"* Fully reverted
at `9c59a84`. **— not in INV**

### R42 — *"repro is the gate — looking for held-out 1.962"*
**Asserted** 08-11T11:42 as the test of whether prior results reproduce on refactored code.
**Retracted** 08-11T11:44: *"That was wrong — `data_pilot` isn't pinned … The 0.277 gap is a **data**
difference, not a code regression, and **nothing was reproduced or refuted by it.**"* The anchors
(uniform / order-0 / order-1) had moved, proving the held-out text itself differed.
The researcher declined pinning it (`U0372`: *"No, results look good enough"*), so cross-day
comparisons remain unpinned. **— not in INV**

### R43 — `LR_RESTARTS`, made default and then measured net-negative
**Adopted** 08-11T21:20 at the researcher's explicit instruction (`U0387`: *"No, I don't want a
clamp, it should continue with the cosine waves. The goal is to repeat."*), shipped as default 1.
**Retracted** 08-13T19:09: *"**LR restarts look net-negative, and that's my default.** … You asked
for repeating cosine and I made it default; the evidence now points the other way, and I'd rather say
so than let it ride."* (vmax4k 2.023 hold vs 2.132 restarts; vmax8k 3.377 vs 3.989.)
**Then that too was refuted** 08-13T22:06 by the researcher's own `LR_RESTARTS=0` run: **3.054 vs
2.132 — restarts HELP by 0.922.** *"My restart hypothesis is refuted."*
Three positions in two days, on a default that is still 1. **— not in INV**

### R44 — *"the four vmax4k runs are nominally the same arm, spanning 1.227 b/B"*
**Asserted** 08-13T22:10 and used to argue no single-run comparison in the project means anything.
**Retracted** minutes later: *"I overstated the four vmax4k runs as 'the same arm.' They aren't —
they're four **different configurations**"* (different LR horizon, retok guard present/absent,
restarts on/off, four different commits).
**Why it matters** — the 1.227 b/B figure survives (it is in `DOC_PLAN.md`'s caveat and therefore at
the top of every file in this write-up), but the *framing* that gave it force — four runs of one arm
— was withdrawn the same hour. `INV-13` voids it for a different reason (measured through the broken
instrument). The "same arm" gloss is not corrected anywhere. **— not in INV**

### R45 — the GPT-2 anchor, **still wrong in the source**
**Asserted** in every run report since `self_organize.py` gained the ANCHORS block: *"GPT-2-small
sits near 1.0-1.2 b/B on comparable text, for scale."*
**Retracted** 08-15T18:19 on the external literature review (Pile paper, Table 2): GPT-2-small is
1.0878 on Pile-CC, 1.2253 on the Pile aggregate, and **1.7912 on GitHub**. *"**Our b/B anchor is
wrong for code.** … it means Python looked worse than it was."* (`chunk_12.md:7231`)
**Status: NOT FIXED.** `self_organize.py:5986` still prints the 1.0–1.2 line, unconditionally, for
every domain including code. The one continual-learning run's Python result (2.276) was read against
it. `LITREVIEW_FINDINGS.md` records the correction; the code does not. **— not in INV**

### R46 — the external review's σ
**Asserted** by the litreview (08-15): σ ≈ 0.596 b/B within-configuration, implying ~9 paired seeds
for D vs B and **~80,000** for 2.009 vs 1.999.
**Corrected** 08-15T18:16: that spread is from `33a9299`, pre-`c76dc74`, measured through the
instrument `INV-13` voids. Per-arm σ from the post-fix 2×2 ranges **0.047 to 1.225 — 26× across four
arms of one experiment.** *"σ is a property of the arm, not the measurement."* Recomputed: D vs B
~12 paired seeds; 2.009 vs 1.999 ~1,450. Recorded in `LITREVIEW_FINDINGS.md`, not in INV.

### R47 — `ACROSS THE RUN BOUNDARY`, degraded twice
`INV-25` records the first degradation: `holdout_bpb()` calls `_eval_logits`, which never consults
memory, so the project's one retention number is **weights-only**.
A **second** finding on 08-15T19:24 is not in `INV-25`'s text: `fab_logits` also fabricates a **zero
gist**, so held-out windows are routed without a real signature. *"every 'HELD' verdict isn't a BWT
variant, it's BWT on a different, **ablated** system."*
**Extension not in INV.**

### R48 — the memory eviction change, contradicted by the literature the same day
**Shipped** 08-15T16:02 at the researcher's direction (`U0447`: *"Use based recency is better I
think"*): `EVICT=lru` made default, meaning least-recently-**retrieved**, with a three-way test
supporting it (A retrieved 70/100 kept vs 0/100 for never-retrieved).
**Contradicted** 08-15T18:17 by the external review: LRU-on-retrieval *"is precisely the pattern the
caching field spent the last five years moving away from"*, and the new-domain flood is the textbook
**scan** pathology, which plain LRU has no defence against — which is exactly what happened to the
English entries in the one continual-learning run.
Logged as a lead, an internal test proposed, **unresolved at the end of the record.** **— not in INV**

### R49 — what the one continual-learning run actually was
`runs.csv` records `continual_eng_py` as *"RESUME from nogrow_s2"*, which reads as `FAB_GROW=0`.
**Corrected** 08-15T19:24: `pilot-add` sets **no** fabric flags, so at `b92f358` it inherited the
defaults `FAB_GROW=1, FAB_N0=3, FAB_NMAX=4096` — **arm D**, the arm the 2×2 measured at mean 3.384,
spread 2.074 — plus `MEM_PER_EXPERT=1` and `EVICT=recency`. *"'RESUME from nogrow_s2' names the
**checkpoint**, not the arm."* An unexplained residue remains: growth on at cap 4096, yet the run
ended with six experts.
**Why it matters** — this is the only run bearing on the stated target, and what configuration
produced it was not settled until the last hour of the record. `INV-43` degrades its *provenance*
(no log); this degrades its *identity*. **— not in INV**

## §1.4 The researcher's own retractions

Four, all of them cheap and all of them productive — recorded because they show the correction
traffic ran both ways, and because one of them cost real work.

| when | withdrawn | outcome |
|---|---|---|
| `U0089` 2026-07-24T12:50 | *"Yes, let's build the amortized rekey … and **make sure that the domains are not disabled**, since I was running on the assumption that they weren't used"* — retracting his own *"Do the domains do anything? Let's put it in standstill, and disable"* from 23 minutes earlier | `SELF_ORG` confirmed defaulting to 1; the disable was never shipped. Caught before cost. |
| `U0146` 2026-07-25T15:57 | *"I think I meant tasks earlier, not agents"* — retracting *"Please don't automaticallly stop them when I message you"* | Claude had already relaunched a workflow on the strength of the first version. |
| `U0313` 2026-08-06T14:44 | *"I think we are overoptimizing for a single metric again, this time the spike. Spikes are ok … **Maybe we should go back**"* | Reverted `TOK_COMPOSE` to default off; Claude dropped the LR bug as the explanation. |
| `U0386` 2026-08-11T20:47 | *"I knew we had a **quality control, before minting as permanent** … I've been thinking we were using it"* | **Falsified**: `git log -S` over `tokenizer.py` found no such gate in any commit, ever. *"No such gate has ever existed."* The probation mechanism was then built from scratch. |

The last is the mirror image of `R21`/`INV-06`: a mechanism *remembered* as existing, which never
did. Both parties held false beliefs about what the system contained, from opposite directions.

## §1.5 What the retraction record shows

Counting the 210 retractions by what produced them:

- **The dominant cause is reading an instrument rather than the system.** `R26` (a matching number
  read as causation), `R27` (*"I measured the symptom and called it the cause"*), `R28` (a metric
  that flattered its own result), `R30` (an uninitialised variable read as a measurement), `R3`
  (a 32-window probe read as a whole run), `INV-18` (a stale cache read as a model), `INV-13` (the
  instrument editing the run). Claude's own tally at 07-27T19:29: *"**Seven of my predictions have
  now died to measurements this session.** The three findings that survived are all *arithmetic in
  the harness*, not algorithm design … I've been proposing mechanisms when I should have been
  checking whether the measurement meant what it said."* (`chunk_04.md:6503`)
- **The fixes that survive are arithmetic, not design.** `BATCH_W` phase-lock (`E2`), `MANAGE_EVERY`
  never firing, segment/window (`E4`), `_due` consumed twice (`E9`), `FROZEN` re-rolling the RNG
  (`E10`), the global-RNG leak (`E11`). Every `E`-boundary in `01_TIMELINE.md` is of this kind.
- **Comments propagate retracted claims longer than code does.** 08-10T22:12 (`chunk_09.md:2969`):
  *"The `TOK_MINT_UNTIL` one is the clearest case of the harm: **I read my own comment saying the
  tokenizer was the failure mode, and spent days building on it.** It was recording a conclusion
  drawn under two bugs that have since been fixed."* This is what `09_COMMENT_AUDIT.md` exists for,
  and `R45` shows the class is not closed.
- **Self-declared structural fixes failed within one commit twice** (`R34`, `R40`), and a
  "verified inert" refactor was uncertified (`R39`) then reverted (`R41`).

---

# §2. PROCESS FAILURES

## §2.1 Container rollbacks — the single largest infrastructure tax

The working container reverted to commit `2c705c7` repeatedly, wiping the working tree, untracked
tools (`levers.py`, `runs.py`, `vocab.py`, `runs.csv`) and the scratchpad each time.

| date | assistant's own count | citation |
|---|---|---|
| 2026-08-11 | *"the container rolled back **twice today**, to `2c705c7`"* | `chunk_10.md:5930` |
| 2026-08-11 | *"the container rolled back **a third time**"* | `chunk_10.md:6355` |
| 2026-08-14 | *"the container has rolled back **five times** and I don't want to redo this"* | `chunk_11.md:4200` |
| 2026-08-14 | *"The container rolled back **four more times this session**"* | `chunk_11.md:5829` |
| 2026-08-14 | *"the container rolled back **twice more** during this analysis"* | `chunk_11.md:6601` |
| 2026-08-15 | *"a rollback hit mid-edit and my saved copy was from the stale tree; restoring it **deleted 1,101 lines**"* | `chunk_12.md:1301` |

**Direct cost.** Nothing was permanently lost — everything was on `origin` — but:

1. **A whole audit was invalidated.** 08-12T01:16: the arm-audit agents read a rolled-back checkout
   and reported *"`_flags_for` is NOT at top level"*. Artifact. Every other finding from that audit
   had to be re-verified against the restored file before it could be acted on.
2. **A capability was reported lost that was not.** 08-14T12:45: *"The `smoke` subcommand was never
   committed … `git log --all -S'smoke)'` finds nothing."* Retracted 08-14T13:02
   (`chunk_11.md:6033`): *"I was wrong that it was lost. I ran those greps against the rolled-back
   working tree without realising it — `.git` had reverted too."*
3. **A near-miss corruption.** 08-15T03:35: restoring a stale saved copy deleted 1,101 lines from
   `self_organize.py`; caught by `git diff --stat` before commit, discarded, redone.

**Adaptation, and when it arrived.** From `chunk_11` onward every Bash call carries a defensive
preamble — `ls levers.py >/dev/null 2>&1 || { git fetch …; git reset --hard origin/rm-predict; }` —
appearing **5 times in chunk_11 and 8 times in chunk_12, and zero times in chunks 1–10.** The
behavioural change is: *commit and push after every fix rather than batching.* Stated explicitly at
`chunk_11.md:5829` and `chunk_10.md:6376` (*"pushing promptly is the safer trade — I've only avoided
losing work because everything was on origin"*).

## §2.2 Context exhaustion — 9 events in 26 days

Nine turns in `user_turns.md` are harness-generated compaction summaries replayed as user messages
(*"This session is being continued from a previous conversation that ran out of context"*):

`U0032` (07-22), `U0082` (07-24), `U0147` (07-25), `U0177` (07-30), `U0264` (08-04), `U0309`
(08-06), `U0370` (08-11), `U0417` (08-13), `U0448` (08-15).

Roughly one every three days, 16k–27k characters each. Two consequences visible in the record:

- **The first turn of the whole project was caused by one.** `U0002` (07-21T18:06): *"Ask any
  questions, about it. **I am moving chats, because it can't be compressed.** I will pass anything
  you need to the other chat for the status."* The `handoff/` folder, `STATE.md`'s self-verify step
  and the whole context-exchange apparatus exist because of this constraint.
- **Compaction summaries are lossy in a way that matters for this write-up.** Several genuine
  researcher inputs — the north-star statement, the growth-vs-size choice, the mid-run-expandable-
  vmax proposal — survive only inside a summary or in `chunks/`, not as verbatim turns. `U0417`
  reduces one to the stub *"[NORTH STAR statement]"*.

## §2.3 Session-budget exhaustion mid-task

**2026-08-15T18:34** — all four wave-3 documentation agents died simultaneously:
*"You've hit your session limit · resets 7pm (UTC)"*; `09_COMMENT_AUDIT` reported `status=failed`
(`chunk_12.md:7376-7395`). Diagnosed as four parallel agents each burning 200–400k tokens.
Relaunched after the reset (`chunk_12.md:7481`): *"nothing was wrong with the work, they just ran out
of budget mid-flight."*

**2026-07-27T13:52** — a different budget failure, caught only because the researcher asked. `U0149`:
*"The tasks have been going on for a while. I'm a bit concerned check up on them."* The container had
been reclaimed and restarted; the workflow was **dead, not slow** — uptime 1h59m, agent files last
written before this lifetime, zero worker processes. **2 of 5 diagnosis agents had returned; the
verify phase never ran**, and no notification would ever have arrived. Claude's prior estimate of
*"~2 more hours, running at concurrency 2"* was wrong.

**2026-07-24T18:21** — `parallel[1] failed — agent StructuredOutput retry cap (5) exceeded`; 1 of 9
agents lost with no valid output.

## §2.4 GPU work lost or wasted

Ordered by cost. Every entry is time on hardware the researcher was paying for.

| date | what | cost | cause |
|---|---|---|---|
| 07-23 | The 1B-byte FineWeb run: ~432k steps, **no checkpoint**, no promptable model | **~22 hours H100** | End-only saving; process died before the save; bash printed `WHOLE SYSTEM RUN COMPLETE` regardless (`R22`) |
| 08-06 | The phantom-regression hunt: 18-agent bisect over 14 commits where nothing changed | ~1.19M subagent tokens + the researcher's confirmation run | `R37` |
| 08-10 | An architecture grid run instead of the equivalence question asked | **4.5 h** (`_status.tsv` = 16,279 s) | *"I ran the wrong test … it cost 4.5 GPU-hours to answer something you didn't ask"*; estimate given was 2–3 h |
| 08-02 | Both pilot arms killed at the first rekey | full pilot | Claude's own signature-width regression, certified by a smoke gate too small to exercise it |
| 08-04 | `SOCIETY=0` pilot OOM at 11.39 GiB | full pilot | *"I recommended `SOCIETY=0` **having already written the comment saying the chaining path is O(N)** … That was careless and it cost you a run"* |
| 08-05 | A pilot on a checkout 3 commits behind; result byte-identical to two prior runs | **~1 h GH200** | Stale checkout. *"it cost about an hour of GH200 time to find out."* Prompted `U0292`: *"You are right. This is why we needed the commit numbers."* |
| 08-11 | `vmax4k` / `vmax8k` arms run at a commit predating their definition — three runs of plain `base` logged under three arm names | 3 runs | `_flags_for` hit its `*)` fallback |
| 08-14 | The **one continual-learning run**: hours of GPU, a valid checkpoint, and **no log** | full run | `pilot-add` never `mkdir -p`'d `$OUT`, so `tee` wrote to a closed pipe (`INV-43`). Recovered only because the researcher pasted his terminal: `U0431` *"It is lost, but I copied from terminal, so not completely gone"* |
| 08-15 | The gradual-growth run: 8 ramp events, **0 capacity lifts** | ~1 h | Ran on `e9f2e58`, which predates `GROW_CAP`; six deliberately-set knobs silently ignored, because the config audit used a hardcoded prefix allowlist — *"the net designed to catch exactly that never fired"* (`INV-19`) |
| 08-05 | 4 of 18 grid arms trained fully, then lost their entire reports | 4 arms | `generate()` CUDA assert on a degenerate distribution |
| 08-05 | The `DIV_W=0.05` pilot | ~20 min | Byte-identical to `DIV_W=0` (`INV-44`) |

Two further self-inflicted classes:

- **`pkill` killing the assistant's own shell** — three times (08-10T23:19, 08-11T22:42,
  08-13T22:19), each time exit 144, each time taking background tasks with it.
- **Editing a script while a background job was executing it** — 08-11T22:48: bash reads scripts
  incrementally by byte offset, so a 128-line hoist shifted everything under the running interpreter,
  which resumed inside the wrong branch and exited 1 on a smoke that had actually passed.

## §2.5 The pattern

Of the wasted GPU time above, **one item is infrastructure (the rollbacks) and every other is a
verification gap** — a stale checkout, an unset flag, a directory not created, an allowlist that did
not cover the knobs under test, a smoke gate too small to reach the code path it certified. The
researcher named this before the evidence accumulated, at `U0100` (07-24T21:10):

> *"This sounds good so far, however, I must know. **Since I've been burned on this a few times**:
> does the multi epoch test contain everything?"*

The audit that answered him found `FABRIC=0`, `EXPERTS=0`, `VERIFY=selfcon`, `RECON_W=0.0`,
`WORLD_MODEL=0`, `CKPT_EVERY=0` by default (`E3`). Claude's reply: *"Your instinct to ask was
correct."*

---

# §3. DECISIONS MADE AND NOT IMPLEMENTED

Cases where the record shows a decision reached — by measurement, by instruction, or by both — that
the code did not receive. The known example is first; the rest were found by checking every
documented decision against the source at `86fd64a`.

### D1 — `MEM_PER_EXPERT`: documented OFF, read as 1, for the project's entire life
The comment recorded both a measurement and a decision (*"DEFAULT OFF, on measurement"*, at
−0.555 b/B against the global store). The code read `_i("MEM_PER_EXPERT", 1)`.
**Every run in this project used the partitioned store.** Found 2026-08-15T15:31 while answering a
question about why Python memories had evicted English ones; fixed `e25d9b5` (`E15`, `INV-06`).
The researcher's response (`U0447`) generalised it:

> *"Default 1 sounds like a poor and faulty decision in your past. **Treat past comments as a rough
> statement, never as anything definitive**, especially since it can drastically change with
> different structures and architecture."*

**Now fixed.** It is listed first because it is the template for D2–D6.

### D2 — the `FABRIC=1` justification is `INV-36` VOID and still in the source
`self_organize.py:1091-1100` is the comment block that argues for defaulting the fabric ON. It says:

> `# +0.709 is four times what the memory contributes and the largest single component effect measured here.`
> `# … at these settings the router HALTs 90% of the time and mean routed depth is 0.10 of 4 steps`

The first sentence is **`INV-36`** (an eval-time knockout; the retrained ablation is 3.089 vs 3.090 —
no bits/byte at all). The second is **`INV-40`** (a report-time probe of a path the run did not use).
Both were retracted; **neither correction reached this comment.** The fallback justification offered
at the time — coherence 0.75 vs 0.50 — is `INV-20`.
`09_COMMENT_AUDIT.md` lists it in the WRONG category. **NOT FIXED.**

### D3 — `longrun.sh` describes a default that was reverted
`longrun.sh:240` states: *"TOK_COMPOSE is now ON by default, so every arm below states BOTH knobs"*.
`TOK_COMPOSE` was reverted to default **0** at `be50e3a` on 2026-08-06 (`U0313`, *"Maybe we should go
back"*), and `_SPEC` line 100 confirms `("i", 0)`.
**Consequence**: the `nocompose` arm (`TOK_COMPOSE=0 TOK_MINT_NOVEL=0`) is now a **duplicate of
`base`**, so the `ablate` and `tokens` presets each contain a wasted arm that will read as a control.
**NOT FIXED.**

### D4 — the GPT-2 anchor
See `R45`. Corrected in conversation and in `LITREVIEW_FINDINGS.md` on 2026-08-15; `self_organize.py:5986`
still prints *"GPT-2-small sits near 1.0-1.2 b/B on comparable text"* for every domain, code
included. **NOT FIXED**, and it is printed by every future run.

### D5 — `ENC_CREG`: raised at least five times, never ruled on, still 0.0
Claude flagged `ENC_CREG=0.0` as one of two undefended defaults on 2026-07-31 (*"the code's own
comment says encoder collapse on single-corpus runs is not a risk but a certainty"*), and it appears
in the `OFF ON PURPOSE` banner of every subsequent run. The researcher never ruled on it and it was
never flipped. `self_organize.py:268` still reads `("f", 0.0)`.
Its sibling, `DIV_W`, turned out not to be a choice at all (`R33`).
**OPEN — no decision was ever made**, which is different from a decision not implemented, and is
recorded here because five raisings without a ruling is itself a process fact.

### D6 — the growth-vs-cull ordering was inverted by a later change and left that way
`FAB_BURST` 3→1 and `FAB_NEW_FRAC` 10%→4% were adopted 2026-08-15T04:06 at the researcher's explicit
instruction (`U0442`: *"Lets change instead to burst of 1, and 4%, since cull is 8%"*) — the stated
purpose being that growth must not outpace selection.
Later the same day, `FAB_CULL_FRAC` was lowered 0.08 → **0.02** at the researcher's instruction
(`U0450`: *"modify the culling percentv from the either 8% or 4% that it currently is to 2% or 1%"*),
and `MANAGE_EVERY` is 500, not 50.
**The property the first change was made to guarantee is now inverted**: the growth allowance is
twice the cull share rather than half. Claude found this, fixed the comment, and explicitly left the
behaviour to the researcher (`self_organize.py:601`). **OPEN, and the code currently does the
opposite of the stated intent.**

### D7 — `GRAD_CLIP`
Proposed 2026-08-06T17:22 with the observation that there is no gradient clipping anywhere in the
loop, at `lr=2e-3` on AdamW with a GRU, a population growing to 4096 experts and a vocabulary
changing underneath it. Explicitly withheld pending approval. No approval was given and none was
added: `grep GRAD_CLIP self_organize.py` returns nothing. **NOT BUILT — correctly, since it was never
approved**; listed so the open item is not lost.

### D8 — three mechanisms approved with *"Build all 3"* and never built
`U0435` (2026-08-14T22:51): *"Build all 3."* — rescue-before-cull with mutation, expandable expert
count mid-run, expandable VMAX mid-run.
Two of the three later appeared in some form (`FAB_RESCUE`, `GROW_CAP`), but the approval and the
implementation are separated by a session boundary, and the third (expandable VMAX) was never built.
The chunk ends 86 seconds after the instruction. Tracked in `07_WIP.md`.

**What D1–D4 have in common**: in every case the *code* was corrected or the *conversation* was
corrected, and the **prose that justifies the code** was not. That prose is what the next reader —
human or agent — will act on. This is the same mechanism as `R21` (a ledger that stopped being
written while everything kept citing it), 25 days apart.

---

# §4. WHAT THE RESEARCHER HAD TO REPEAT

Repetition is the most actionable signal in the record: an instruction given twice was not followed
the first time. Five threads, each given at least three times.

## §4.1 "Checkpoint properly" — 6 turns over 22 days

| turn | date | text |
|---|---|---|
| `U0036` | 07-23 | *"I am surprised that we stopped checkpointing. The estimates given are always wrong and longer than expected. Is there a way to inject code to pause and force checkpoint?"* |
| `U0037` | 07-23 | *"**No, I consider this as stopping checkpointing, because the end as a checkpoint doesn't really count.**"* |
| `U0048` | 07-23 | *"I am still quite upset that the checkpoints were not saved in the last run"* |
| `U0051` | 07-23 | *"how can I see the checkpoints and if they happen"* |
| `U0054` | 07-23 | *"Also, I don't even think checkpoints were being saved. Since there is no 'runs' folder"* |
| `U0100` | 07-24 | *"does the multi epoch test contain everything? Full scale with surprise, experts, reverse, tokenizer, constant learning capacity, **checkpoints**, pause optionality, etc… ?"* |
| `U0427` | **08-14** | *"**You keep on turning off checkpoints, so we cant do it yet.**"* |

The last is 22 days after the first, and it was justified: `SEED_CKPT` defaulted to 0 while
`GRID_CKPT` defaulted to 1, so **the sweep producing the models worth continuing from was the one
discarding them** — and Claude had additionally dropped `SEED_CKPT=1` from the command it
recommended. Fixed `e0dbf0c`. Two days earlier the same gap had already cost the record: every grid
command handed over used `GRID_CKPT=0`, so *"Nothing we ran this session can be added to"* — including
`frozen_nr` at 2.175, the best arm at the time.
**This is the single most-repeated instruction in the project, and the one whose failure blocks the
stated target**, because both `pilot-add` and `add` require a checkpoint.

## §4.2 "Optimise for output, not for our metrics" — 5 turns over 16 days

| turn | date | text |
|---|---|---|
| `U0161` | 07-27 | *"**As a reminder**, I don't want to optimize for our arbitrary metrics. Their use is only as proxies … If a metric isn't working, but the system itself is improving, that does not mean the system is at wrong, but the metrics and how we are using them"* |
| `U0171` | 07-29 | *"The final goal will always be proper language, working on top of that."* |
| `U0189` | 07-31 | *"The end all is the resulting output, and capacity for continual learning without exorbitant forgetting … The domains are only a concern **because you have been driving it up, and improperly interpreting it.**"* |
| `U0289` | 08-05 | *"What are we optimizing for right now? **Remember**, the ultimate goal is textual, not arbitrary metrics."* |
| `U0406` | 08-12 | *"the final goal is for language, not optimizing specifically the tokenizer, vmax, or different ways to freeze the structure … Remember that a target has been and still is the continual learning."* |

Note the researcher's own signalling — *"As a reminder"* (07-27) and *"Remember"* (08-05, 08-12).
Each was conceded immediately and each was needed again. The 08-05 instance produced the clearest
admission (`chunk_07`, 16:38): *"I have been optimizing mechanism, and it is not paying"* — the run
with the best routing diversity ever measured produced the second-worst text, while `nofabric` was
within 0.06 b/B of the best. The 07-27 instance produced `INV-37` (V-measure tuned against seeded
labels the researcher had already called *"a SCAFFOLD, not the target"*).

## §4.3 "Split the levers" — 6 turns over 5 days, still not done

| turn | date | text |
|---|---|---|
| `U0330` | 08-07 | *"I want you to **normalize and disentangle the code** … This way we have clearer levers. Create a table of what was modified … Ensure that nothing is functionally different"* |
| `U0331` | 08-07 | *"**Did you edit the code?** I wanted clearer, and better defined code, and a table of those changes"* — the composite-lever layer was reverted entirely (`a0df9a6`) |
| `U0347` | 08-10 | *"Let's **first disentangle main**. I don't want to go through the same testing debacle."* |
| `U0353` | 08-10 | *"**Has the total clutter been fixed and levers fully isolated yet?**"* |
| `U0371` | 08-11 | *"**Have those levers been separated and isolated? I thought I asked for that.**"* |
| `U0377` | 08-11 | *"Please **isolate the different levers.** I believe the LR scheduling has affected this run"* |
| `U0379` | 08-11 | *"**This is why we need to fix the levers and their connections**, so they do not overlap and improperly change things"* |

Claude's answer to `U0371` (08-11T12:58): *"Straight answer on the levers: **no, not fully** — and I
should not have said or implied otherwise … what exists is a lever inventory and a coupling reporter,
**not isolated levers.**"*

The instruction was vindicated twice by measurement. `U0377`'s hypothesis was correct and became the
largest single result of that week (`EPOCHS` also set the cosine horizon — `INV-30`, `E8`). And the
root cause of the un-isolated levers turned out to be `E11`: because the stream drew from the global
RNG, *"two arms differing in a training knob take different numbers of draws in epoch 1, so epoch 2
handed them different text — **the knob under test and the data both changed. That is the
levers-not-isolated problem at its root.**"*
`main()` remains unsplit (3,953 lines / 574 locals at last measurement).

## §4.4 "Audit it again, I don't believe it's done" — 5 turns in 5 days

| turn | date | text |
|---|---|---|
| `U0186` | 07-31 | *"However, **double check everything.**"* |
| `U0202` | 08-03 | *"**Look for other issues that may be present.**"* |
| `U0204` | 08-03 | *"**I suspect much more is broken or not working as intended. Go through everything again please**"* |
| `U0206` | 08-03 | *"Fix the explicitly broken. … **Check again for anything left**"* |
| `U0208` | 08-03 | *"**Triple check stuff if they are broken. I'm not sure everything is done.** It must be completely thorough. I don't want any issues. **Fix the issues you mentioned, even though you didn't touch.**"* |

Each pass found something the previous had not. `U0202` found `MAX_DOMAINS` and the expert bank
15,625× apart. `U0204` found a stale `fab.keys` silently deleting the entire EXPERTS/SUFFICIENCY
report, and `prompt.py` dead since a refactor. `U0208` found that the optimizer-moment loss Claude
had declared *inherent* was a one-line bug. And `U0209` (08-03T19:57) — *"Is there an expert culling
mechanism?"* — found that **there was none at all**, which is `INV-14`.
The final clause of `U0208` is the load-bearing one: *"even though you didn't touch"* — Claude had
been scoping items out as latent, and every one of them was live.

## §4.5 "You take too long — give it to me" — 6 turns over 12 days

| turn | date | text |
|---|---|---|
| `U0181` | 07-30 | *"I am running. **Your CPU smoke is taking longer than what I think the GPU would take.**"* |
| `U0252` | 08-04 | *"Yes, but my point is, **you take too long, it is better for me to do it for you.**"* |
| `U0330` | 08-07 | *"I am running what you just provided."* |
| `U0355` | 08-10 | *"**I can run the tests. Send it to me. My system is likely faster**"* |
| `U0356` | 08-10 | *"You are saying no gpu, but **if it is faster with a gpu, let's do it**, since it's available anyways"* |
| `U0397` | 08-11 | *"**If it would be faster on gpu, let me run it**"* |

Measured, this was correct every time: the 12-arm gate took **4 minutes** on the researcher's box
against 701 s → 485 s on the 4-core container, and one gate ran 4,731 s because Claude had two full
gates competing for the same cores. `U0252` became a standing instruction (*"Understood — I'll stop
running it"*), and `U0397` prompted killing a local run mid-flight.
**The division of labour was set on day one** — `chunk_01.md:359` records the AskUserQuestion answer
*"You run on your own H100, paste back"* — and had to be re-established six times.

## §4.6 A note on what repetition bought

In four of the five threads the repeated instruction was **correct on the merits and vindicated by a
later measurement**: `U0377`'s LR hypothesis (`INV-30`), `U0100`'s subsystems suspicion (`E3`),
`U0208`'s "you didn't touch" (`INV-14`), `U0427`'s checkpoint complaint (`e0dbf0c`). The researcher's
hit rate on "I don't think that's right" is high enough that the repetitions are not noise; they are
the mechanism by which most of the `E`-boundaries were found.

---

# §5. TIMELINE OF ATTENTION

## §5.1 The shape of 26 days

23 active days (no activity 08-01, 08-08, 08-09); 455 human turns; 279 commits.

| day | turns | commits | what it was spent on |
|---|---|---|---|
| 07-21 | 26 | 23 | Handoff apparatus, naming pass, Verification built (`E`-free) |
| 07-22 | 7 | 6 | Verification fails in the product loop; corpus tag leak |
| 07-23 | 29 | 11 | The lost 22-hour run; checkpointing; live-injection attempts |
| 07-24 | **57** | **33** | World model; the profiling campaign; the "does it contain everything" audit (`E1`) |
| 07-25 | 29 | 15 | GH200 readiness; the domain-assembler campaign opens |
| 07-26 | 1 | 2 | `BATCH_W` phase-lock found (`E2`) |
| 07-27 | 12 | 9 | Domain metrics; segment/window; the best domain result (V 0.89) |
| 07-28 | 2 | 2 | `PHASED` defaulted on — **the first CL-bearing commit** (`E3` precursor) |
| 07-29 | 12 | 9 | Six subsystems found off (`E3`); metric battery |
| 07-30 | 6 | 3 | Ablation grid; probe sidecar |
| 07-31 | 12 | 10 | English-first decision; experts/competence; phase schedule |
| 08-02 | 6 | 3 | Signature coverage (`E4`); first pilot crashes |
| 08-03 | 26 | 10 | Expert population to 4096; culling found absent (`INV-14`) |
| 08-04 | **41** | 13 | Routing granularity (`E5`); chaining; `rm-predict` branched |
| 08-05 | 35 | **25** | LR schedule found absent (`E6`); `_VALT` (`E7`); the config registry |
| 08-06 | 20 | 9 | The phantom regression; the noise-floor reversals |
| 08-07 | 13 | 7 | Instrument fix 1 (`E8`); the disentangling order |
| 08-10 | 27 | 12 | `equiv.sh`; comment audit; the `main()` split and its revert |
| 08-11 | **39** | 23 | LR horizon isolated (`E8` applied); vocabulary arms; minting quality |
| 08-12 | 8 | 4 | Arm hygiene; the "final goal is language" reset |
| 08-13 | 10 | 7 | `_due` (`E9`), `FROZEN` RNG (`E10`), **the global-RNG leak (`E11`)** |
| 08-14 | 16 | 14 | `mem.ctx` (`E12`), bytes/token (`E13`), **the one continual-learning run** |
| 08-15 | 21 | **29** | Founder birthdays (`E14`), memory eviction (`E15`), the literature review, this write-up |

## §5.2 Where the effort went, by subsystem

Classifying all 279 commit subjects by keyword (approximate — a commit often touches more than one
area, and the primary match wins):

| subsystem | commits | share |
|---|---|---|
| harness / measurement / config / instruments | ~83 | **~30%** |
| experts, router, fabric, chaining, selection | 65 | 23% |
| tokenizer, vocabulary, minting, VMAX | 47 | 17% |
| domains, signature encoder, clustering | 26 | 9% |
| docs / notes | 15 | 5% |
| LR schedule / optimizer | 11 | 4% |
| verification / reconstruction | 10 | 4% |
| **continual learning, retention, forgetting** | **9** | **3%** |
| world model | 8 | 3% |
| memory | 5 | 2% |

## §5.3 The disproportion, dated

`06_CONTINUAL_LEARNING.md` §0 establishes it structurally: **1 of 42 rows in `runs.csv` is a
continual-learning run.** What the transcript adds is *when*, and *why not sooner*.

- **The target was stated on day one.** The north-star answer (07-21T19:26, an AskUserQuestion
  answer, verbatim at `chunks/chunk_01.md:1855` and **not present in `user_turns.md`**): *"The genie
  wish is an LLM capable of learning, complex reasoning, much smaller than conventional models, and
  with an ever expanding and updatable knowledge base … expansion and growability are not to be
  lost."*
- **The mechanism that tests it was off until day 8.** `PHASED=0` — a stationary i.i.d. splice — was
  never once executed until 07-28 (`INV-03`). The researcher found it, not the audit: `U0163`
  (07-28T11:43), *"**Why is non stationary off? I thought forgetting was essential**"*. Claude's
  answer: *"There is no good reason. Nobody ever questioned it, including me."*
- **The first CL-bearing measurement ran on day 25 of 26.** `continual_eng_py`, 2026-08-14T22:21
  (`U0431`), n=1, and its log was lost (`INV-43`). Its result — `eng` +0.052 ± 0.075 **HELD** — is a
  weights-only number (`INV-25`), taken on a system whose memory had evicted every English entry
  (`INV-24`), from an arm that was not the one recorded (`R49`).
- **Every intervening day was spent on prerequisites that turned out to be broken.** That is not a
  digression from the target; `E1`–`E15` are fifteen findings that the measuring apparatus was
  changing what it measured, and until `E11` (day 24) no arm comparison in the record was safe. The
  cost is that the target got one run, at the end, through an instrument that had been fixed nine
  hours earlier.

## §5.4 What the researcher said about the disproportion, in his own words

He raised it three times, and the phrasing sharpens each time:

| turn | date | |
|---|---|---|
| `U0189` | 07-31 | *"The end all is the resulting output, and **capacity for continual learning without exorbitant forgetting, and maintaining old capacities, without significant degradation.** The project should reflect this."* |
| `U0406` | 08-12 | *"a stumbling block has been the levers I've wanted split, but not, and interfering with our runs … **Remember that a target has been and still is the continual learning.**"* |
| `U0435` | 08-14 | *"**I want english to be done well in a pilot before fully committing to adding new domains, and the continual learning.** I know it is undertrained earlier, but how far from english were we?"* |

The last question was never answered — the session ended with Claude pulling generation samples to
answer it. The only anchor in the record is 1.989 b/B best against a GPT-2-small marker that is
itself wrong (`R45`).

`U0406`'s clause — *"I need to be able to carry and build off the results we get"* — names the real
cost of the disproportion better than any count does. Claude's reply conceded the concrete form of
it: every grid command handed over had used `GRID_CKPT=0`, so *"Nothing we ran this session can be
added to."*

---

## What this file does not establish

- **It does not re-adjudicate any number.** `04_RESULTS.md` and `05_ERRORS.md` own those. Where a
  figure appears here it is quoted from the transcript as evidence about the *claim*, not offered as
  evidence about the system.
- **The §5.2 subsystem split is keyword classification of commit subjects**, not an effort
  measurement. It is accurate to roughly ±5 points per row and should be read as shape, not
  accounting. The ~30% / 3% contrast is robust to any reasonable reclassification; the ordering of
  the middle rows is not.
- **The retraction count (210) is the count in the extraction**, and includes minor in-turn
  self-corrections alongside major withdrawals. §1.2 and §1.3 list the consequential ones; the
  ratio between them is the useful figure, not the total.
- **`user_turns.md` excludes AskUserQuestion answers**, so several genuine researcher decisions —
  the north star, the from-scratch rationale, the growth-vs-size choice — exist only in `chunks/`.
  Anything sourced there is labelled. Nothing in this file is quoted from a compaction summary as
  though it were a typed turn.
- **§3 is a floor, not a ceiling.** D1–D6 were found by checking documented decisions against the
  source. `09_COMMENT_AUDIT.md` classifies 51 MOVE and 19 WRONG comment blocks of which two were
  acted on, so the true count of prose that outlived its decision is higher than six.
