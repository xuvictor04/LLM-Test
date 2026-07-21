# Memory pressure → grow experts / retrain / split the domain — NOT a per-domain quota [USER direction]

**The problem:** under a bounded memory store, a process that stops appearing has its knowledge fully EVICTED.
`EVICT=recency` (default) evicts it; `EVICT=usage` does NOT fix it by construction (faded ≡ least-used — the same signal).

**REJECTED [USER]:** a strict reserved-capacity-PER-DOMAIN quota. A hard cap bolted onto a system whose whole premise is
GROWTH fights the sacred growability invariant and "sounds like it will break something."

**Preferred direction [USER]:** treat approaching memory burden as a signal for a STRUCTURAL adaptation, not a cap —
when a domain's memory pressure is near, do one of:
- **Expand the domain in terms of EXPERTS** — add expert capacity where the load actually is (grow, don't cap), and
- **possibly RETRAIN those experts** so the added capacity absorbs what memory was holding, and/or
- **read it as a DOMAIN-SPLIT signal** — the domain has grown heterogeneous enough that it should divide.

This moves faded/overflowing knowledge from the volatile memory store INTO expert weights (or into a cleaner sub-domain),
which is consistent with the architecture's own growth mechanisms rather than a foreign quota.

**Open:** what "memory pressure near" threshold triggers it; how to decide expand-vs-retrain-vs-split; how the moved
knowledge is transferred from memory into the (re)trained experts without disrupting other domains.
**Status:** direction (replaces the rejected quota); not built.
**Source:** user, session 2026-07-21.
</content>
