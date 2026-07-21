# Q0 — What TYPE of evolution should the experts use? — OPEN, needs USER decision

**Question:** The expert-evolution scheme was never chosen by the user — it is an assistant default `[me]`.
**Current `[me]` scheme (flagged, not user-approved):** steady-state (no generations), mutation-only
(no crossover), LAMARCKIAN (gradient-trained weights inherited by offspring), niche-based speciation
(new expert when nothing matches within `EXPERT_NEW_DIST`), and **fitness = OCCUPANCY** (how often the
router picks it), NOT task performance.
**Biggest weakness:** a frequently-routed BAD expert still wins.
**Alternatives to weigh:** (a) Darwinian performance fitness (per-expert loss reduction); (b) tournament
instead of argmax; (c) crossover between adapters; (d) self-adaptive mutation rates; (e) age-layered
protection for young experts.
**Who decides:** USER. Do not default further.
**Source:** `STATE.md §4 Q0`.
