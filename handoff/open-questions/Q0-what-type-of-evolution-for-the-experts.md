# Q0 — What TYPE of evolution should the experts use? — OPEN, needs USER decision

**Question:** the expert-evolution scheme was never approved — it accreted as a `[me]` default.
**Verified against the code (not memory):** fitness = pure OCCUPANCY (`fit = use/age`) — there is NO loss term anywhere.
The rest of the scheme: steady-state (no generations), mutation-only (no crossover), Lamarckian (trained weights
inherited by offspring), niche speciation (new expert when nothing matches within `EXPERT_NEW_DIST`).
**Biggest weakness:** an expert can WIN by being cheap to reach rather than good — a frequently-routed BAD expert survives.
**Prior-context recommendation (not decided on your behalf):** **(a) Darwinian per-expert-LOSS fitness** first, since
occupancy-as-fitness is the most clearly wrong piece. Other options: (b) tournament vs argmax; (c) adapter crossover;
(d) self-adaptive mutation rates; (e) age-layered protection for young experts.
**Who decides:** USER. Do not default further.
**Source:** `../../STATE.md §4 Q0`.
