# Additional notes — things you didn't ask for

Marked separately, as requested. This is my judgement, not retrieved literature.

## 1. The single highest-value thing in this bundle

File 08. Not because seeds are interesting, but because of the specific numbers:

- Your headline growth result (3→4096 vs 2048→4096) has **P(A > B) ≈ 0.95** at your estimated
  σ, needing **≈ 9 paired seeds** to establish. That is affordable today.
- Your secondary claim (2048→4096 ≈ fixed 2048) needs **≈ 80,000 seeds**. It is not a
  measurable quantity at your current σ.

In my first response I told you the 0.5% gap was "plausibly within seed variance" and implied
the whole growth result needed shoring up. With your actual σ, that was too pessimistic about
the big effect and not nearly pessimistic enough about the small one. The correct action is
narrower and cheaper than "get more seeds for everything."

## 2. Three of your problems are the same problem

Reading files 08–11 together, a pattern:

- **Newborn experts** get culled before they can prove themselves → grace period
- **Newly-minted tokens** get weight-decayed to zero before they accumulate updates
- **Newly-written store entries** have zero retrievals, so any frequency-based eviction kills
  them; and under LRU they're protected for the wrong reason (recency, not usefulness)

All three are: *a new unit cannot survive a competition scored on evidence it has not had time
to accumulate.* Three literatures solved it independently and gave it three names — NEAT's
**speciation protection**, the cache literature's **probationary segment**, and the vocabulary
literature's **progressive unfreezing**.

They also converge on the same shape of answer: **a protected region of bounded size with an
explicit promotion criterion**, not a softer scoring function. S3-FIFO's small queue is 10%.
LIRS's is 1%. 2Q's is 25%. If you're going to build one mechanism this quarter, build the
generic version once and apply it in all three places.

## 3. What I'd fix first, in order

1. **Check whether the `N` factor is in your balance loss** (file 12). At 4096 experts, its
   absence is a 4096× error and would explain a lot. Five minutes.
2. **Run the all-seeds-pinned determinism check** (file 08). ~5 runs. Determines whether your
   σ = 0.6 is stochasticity or a bug. Everything downstream depends on the answer.
3. **Add a ghost list to the store** (file 09). Keys only, cheap. Gives you your own eviction
   error rate, currently unmeasured.
4. **Compute the paired R^full / R^weights matrices** (file 11). Turns your broken metric into
   two useful ones and separates "eviction problem" from "forgetting problem."
5. **Then** the 9-seed growth experiment.

Items 1–4 are all under a day and three of them are measurement, not architecture. Given that
your seed floor currently exceeds every effect you've measured, measurement work has a much
better expected return right now than architecture work.

## 4. A correction to my own framing from last time

In file 03 I reported "no prior art found for per-source quota in a bounded shared store." That
was accurate for the retrieval literature you gave me leads into. It is **wrong as a general
statement** — file 10 shows class-balanced reservoir sampling and iCaRL's per-class exemplar
allocation are exactly that, and they're standard in replay-based continual learning.

The two fields genuinely don't cite each other, and I searched only one of them because your
leads pointed there. **Worth remembering as a general lesson about this bundle: my negatives
are only as broad as the search terms your leads implied.** When I say "no prior art found,"
read it as "not in the neighbourhood I searched," and the neighbourhood was largely set by you.

## 5. The reframing I'd actually push

Your store is **read during training**. That single fact puts you in replay-based continual
learning, not in semiparametric/kNN-LM territory, where retrieval is inference-only (file 04).

Consequences if you accept the reframing:
- Reservoir sampling and its balanced variants become your baseline, not an exotic option
- MIR raises a design axis you aren't using: *which* entries to replay, as distinct from which
  to keep — cosine top-k is a retrieval rule you inherited, not one you chose
- BWT/forgetting-measure become your natural metrics, with the two-matrix decomposition
- GSS's framing — buffer selection as *constraint reduction* in gradient space — is a
  better-motivated alternative to your surprise gate, and is source-agnostic

Four of your twelve questions were, underneath, the same question asked in four vocabularies.
Picking one field to be your primary reference would save you a lot of parallel searching.

## 6. Two things I'd stop doing

- **Stop reporting n=1 comparisons internally**, even informally. At σ = 0.6, an n=1 comparison
  under 1 b/B is a coin flip, and the cost isn't the wrong conclusion — it's that the team
  builds a mental model out of coin flips and then defends it.
- **Stop using one b/B scale marker across web text and code** (file 05). Code b/B spans 3.2×
  on training mix alone. Name the corpus next to every number.

## 7. Open items across the whole bundle

| Item | Why it matters | Cost |
|---|---|---|
| Gopher Table A7 (arXiv:2112.11446) | sub-100M b/B anchor | 1 fetch |
| arXiv:2408.15664 loss-free bias balancing | likely better than expert-choice for you — stays causal | 1 read |
| arXiv:2604.16656 Defragmenting LMs | closest work to minting merges during training | 1 read |
| arXiv:2604.01622 EC for decoders | whether expert-choice is usable in an autoregressive LM at all | 1 read |
| CBRS per-class reservoir | the per-source quota, verified | 1 read |
| PathNet | whether within-network evolution + backprop has a precedent | 1 search |
| arXiv:2505.00675 | the fifth Q3 lead, still unread | 1 read |
| Dodge et al. "Show Your Work" | the reporting paper you asked for and I didn't reach | 1 read |
