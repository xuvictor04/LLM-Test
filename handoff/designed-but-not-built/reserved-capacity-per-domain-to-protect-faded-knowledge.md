# Reserved-capacity-per-domain quota (protect faded knowledge) — IDENTIFIED, not built

**What:** under a bounded memory store, a process that stops appearing has its knowledge fully EVICTED. `EVICT=recency`
(default) evicts it; `EVICT=usage` does NOT fix it by construction (faded ≡ least-used — the same signal). Only an
explicit reserved-capacity-PER-DOMAIN quota would protect faded knowledge.
**Status:** diagnosed via the `PHASED=1` non-stationary test; the quota mechanism was never built.
**Source:** context export §11, Phase-10 non-stationary finding; `../../STATE.md §7`.
