# Q7 — Cache eviction policy from the systems literature

You were right that this is the cheapest place to find a better rule. And you were right to be
worried: **LRU-on-retrieval is precisely the pattern the caching field spent the last five
years moving away from**, and your "new domain floods the store" is the textbook scan.

---

## (a) What workload makes pure LRU fail

Three classic pathologies, in descending order of relevance to you:

**1. Scans.** A burst of items accessed once each, in sequence, longer than the cache. Every
access is a miss, every miss inserts at the MRU end, and the entire working set is pushed out.
**This is your new-domain flood, exactly.** LRU has no defence: recency is maximal for the
newest thing, which is the thing least likely to be useful.

**2. One-hit wonders.** Objects requested once and never reused while resident. The SIEVE and
S3-FIFO authors identify this as *the* dominant problem in production traces — a large fraction
of objects in real cache traces are never reused. LRU handles them worst, because it uses
**passive demotion**: an object only sinks to the eviction end by having everything else
promoted past it, which takes O(cache size) accesses. So a useless object squats for a long time.

**3. Cyclic access larger than the cache.** Scan a working set of size C+1 repeatedly with a
cache of size C, and LRU achieves a 0% hit rate — it always evicts exactly the item about to be
requested. Pathological but real in loops.

The framing worth internalizing, from the SIEVE paper: LRU does **eager promotion + passive
demotion**. Every hit costs a promotion (and a lock), and demotion is slow. The field's
correction is **lazy promotion + quick demotion**: decide about promotion only at eviction time,
and remove most objects quickly after insertion.

**Your LRU-on-retrieval is eager promotion + passive demotion.** You implemented the thing the
field moved off.

## (b) What makes pure LFU fail

- **No aging / cache pollution.** An object that was extremely popular during a burst
  accumulates a count that never decays and becomes immortal, even after its popularity ends.
- **Newcomer starvation.** A newly-inserted object has count 1 and is the immediate eviction
  candidate, so genuinely-popular new items can never accumulate enough count to survive. This
  is the mirror image of the scan problem and it matters for you: a newly-written entry from
  your surprise gate has zero retrievals by construction.
- **Low-frequency indistinguishability.** From the S3-FIFO analysis: TinyLFU cannot distinguish
  among the many objects sharing the same low frequency (e.g. 2), whereas LIRS's inter-recency
  metric can. At scale most objects live in the low-frequency bucket, so frequency carries
  almost no signal there.

## (c) Which hybrids are deployed, and why

| Policy | Structure | Scan-resistant? | Notes |
|---|---|---|---|
| **ARC** | Two LRU lists (recency + frequency) + two ghost lists; adapts the split | Yes | No *explicit* parameters, but its adaptation uses implicit ones. LRU-like: delinks on hit. |
| **2Q** | ~25% FIFO probationary queue + LRU main + ghost queue | Yes | The design closest to S3-FIFO. Probation is what gives scan resistance. |
| **LIRS** | Reuse (LRU stack) distance; **1% queue** for one-hit wonders | Yes | The tiny queue is the "secret sauce" — it's quick demotion. More complex to implement. |
| **W-TinyLFU** | Small LRU window + frequency-sketch admission filter to a main SLRU | Partly | Widely deployed (Caffeine). Frequency-based admission. |
| **S3-FIFO** | Small FIFO (~10%) + main FIFO (~90%) + ghost FIFO | **Yes** | Objects insert into small; promoted to main on reuse; ghost tracks evicted keys for fast readmission. |
| **SIEVE** | One FIFO + one "hand" pointer + one visited bit per object | **NO** | Simplest of all. **But its own authors state it is not scan-resistant.** |

**The unifying insight across all the scan-resistant ones is the same: a probationary
segment.** New items go somewhere small, and only earn a place in the main store by being
retrieved while still in probation. That is the mechanism, whatever the surrounding machinery.

### Numbers worth having

From the S3-FIFO evaluation (NSDI'24 / the authors' write-ups), across **6,594 traces from 14
datasets**:
- S3-FIFO achieved a lower miss ratio than **each of 12 state-of-the-art algorithms**.
- On some traces it reduced LRU's miss ratio by as much as **72%**.
- It matched LRU's hit ratio using roughly **46% less memory**.
- At 16 threads it sustained about **6× the throughput** of an optimized LRU.

SIEVE, plugged into other algorithms as a primitive, reduced LeCaR's miss ratio by **4.5% on
average** and improved 2Q and ARC.

**S3-FIFO's known adversarial workload:** traces where most objects are accessed exactly twice
and the second access falls outside the small FIFO. Then the second request always misses. This
is adversarial for every space-partitioning policy (TinyLFU, LIRS, 2Q, CACHEUS) for the same
reason: the probation partition is smaller than the cache.

## (d) The one-hit-wonder / scan problem and how policies handle it

Four distinct mechanisms, and it's worth knowing which one you're buying:

1. **Probationary partition** (2Q, S3-FIFO, LIRS's 1% queue, W-TinyLFU's window). New items are
   quarantined in a small region and must earn promotion.
2. **Admission filtering** (TinyLFU, Bloom-filter LRU). Decide *whether to insert at all* based
   on a frequency sketch. B-LRU rejects all one-hit wonders outright — and is **worse than LRU
   in most cases**, because the second request to every object becomes a miss. A cautionary
   data point for anyone tempted to tighten an admission gate.
3. **Reference bit + sweep** (CLOCK, SIEVE). One bit per object, a hand sweeps and evicts
   unvisited objects. Cheap, but SIEVE's version is not scan-resistant because a scan sets no
   visited bits *and* still occupies the list, so popular objects get intermingled with scan
   objects.
4. **Ghost lists.** Remember recently-*evicted* keys. If an evicted key comes back quickly, you
   learn the eviction was wrong and can readmit at higher priority (S3-FIFO) or shift the
   recency/frequency balance (ARC). This is the cheapest way to get feedback on your own
   mistakes, and I think it's the single most under-appreciated idea here for your setting.

## Learned / ML-driven eviction

Real but a minority position, and the recent trend is *away* from it:

- **LRB (Learning Relaxed Belady)** — trains a model to approximate the Belady optimal policy
  by predicting next-access time. The most-cited learned cache.
- **LeCaR** — reinforcement-learning-style adaptive mix of LRU and LFU with a learning rate.
- **CACHEUS** — extends LeCaR with adaptive experts.
- **LHD (Least Hit Density)** — ranks by expected hits per unit of space-time, with decay rate
  and age granularity as parameters.

The honest summary from the SIEVE paper's parameter discussion: LeCaR, CACHEUS and LHD all
carry explicit tuned parameters (learning rate, decay rate, age granularity), and SIEVE — which
has none — beats or matches them. **The field's recent verdict is that the win came from
structure (quick demotion), not from learned ranking.** That is a direct parallel to what
TraceRetain found in file 03: a learned scorer only separated from FIFO under injected noise.

There is also a throughput taxonomy worth knowing (arXiv:2404.16219): **LRU-like** policies
(LRU, ARC, LIRS, TinyLFU, LeCaR, CACHEUS, LFU) lose throughput as hit ratio rises, because they
delink on every hit; **FIFO-like** policies (FIFO, CLOCK, SIEVE, S3-FIFO, Hyperbolic, LHD, LRB,
Random) gain throughput with hit ratio. If your store is on the hot path, this matters.

---

## What I'd do with your store

Your setup: bounded, admission by a surprise gate, retrieval by cosine kNN, just switched from
write-order (FIFO) to least-recently-retrieved (LRU).

**You moved from FIFO to LRU. The literature's last five years moved from LRU back to FIFO —
with structure added.** Specifically:

1. **You did not gain scan resistance by switching to LRU; you may have lost some.** Plain FIFO
   at least evicts a scan's own entries in order, so a flood self-clears after one cache-length.
   LRU keeps whichever flood entries happened to be retrieved once, and evicts your older
   domain entries that weren't retrieved recently. Check this against your occupancy logs — if
   the new domain's share is *higher* under LRU than it was under FIFO, that's the mechanism.

2. **The cheapest fix is a probationary segment, not a better ranking function.** Split the
   store: ~10% small FIFO for newly-written entries, ~90% main. Entries are written into small.
   An entry promotes to main only if it is retrieved while still in small. Entries evicted from
   small go to a **ghost list** of keys only (no vectors — cheap); a key readmitted from ghost
   goes straight into main. That is S3-FIFO, and it directly solves the flood: a new domain's
   entries occupy at most the small queue until they prove themselves by being retrieved.

3. **Do not use SIEVE**, despite it being the simplest and most fashionable. Its authors state
   plainly that it is not scan-resistant, and scans are your stated problem.

4. **One thing no cache policy handles, and you should design for it yourself.** In a cache, a
   "hit" is binary. In your store, retrieval is cosine kNN — an entry can be returned in the
   top-k with similarity 0.4 (nearly useless) or 0.95 (decisive). Treating both as "retrieved"
   throws away the signal that separates them. TraceRetain's diagnostic (file 03) is exactly
   this failure: unbounded memory had the *highest* mean similarity, 0.87, and the *lowest*
   precision — being retrieved is not evidence of being useful. **A similarity-weighted or
   utility-weighted hit count is a better promotion signal than a raw retrieval count**, and it
   is a small change to code you already have.

5. **Add the ghost list even if you change nothing else.** It costs keys-only storage and it
   tells you your own eviction error rate, which is currently unmeasured. If evicted keys are
   frequently re-queried, your policy is wrong and you'll know within one run.
