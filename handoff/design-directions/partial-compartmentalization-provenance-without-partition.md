# Partial compartmentalization: provenance WITHOUT partition (leak on purpose, for creativity) [USER direction]

**Idea:** information relevant to several aspects should be **partially — not fully — isolated**. Full isolation (hard
walls between experts/domains/memory) prevents cross-pollination; a controlled amount of MIXING is important **for
creativity** and transfer. So: compartmentalize enough to stay organized and editable, but deliberately allow leakage.
The isolation is for CONTROL (edit / unlearn by provenance); the mixing is for CREATIVITY and reuse. Both matter.

**Why it fits the whole design:**
- It sharpens the CENTRAL tension already in the system: the independence loss pushes experts to solve tasks ALONE
  (which is what makes deletion clean), but this says full isolation is a mistake — blending isn't only for capability,
  it's for creativity. So independence must be a DIAL, not maxed out.
- The system already half-implements the resolution — **provenance without partition**: memory entries are TAGGED by
  `src`/`domain` (so they stay editable and removable) but kNN retrieval is NOT domain-restricted (so a memory written
  in one domain can surface in another). Keep the tags; keep the leak.
- Consistent with decisions already made: the per-domain memory QUOTA was rejected (no hard partition); experts have 0
  exclusive members (soft constituency); domain deletion releases affiliations rather than cascade-killing.
- FUNCTIONAL-similarity routing (keystone: same operation across different contents) is the transfer channel — a skill
  learned in one domain applying in another IS the deliberate leak.
- The two characterized regimes BRACKET this: REDUNDANCY = more mixing, MODULARITY = more isolation. Partial
  compartmentalization is a deliberate, tunable MIDDLE — chosen for creativity, not only for editability.

**Open:**
- What is the MECHANISM and the DIAL of "partial"? Candidate knobs already present: routing temperature (`ROUTE_T`),
  retrieval scope, independence weight (`IND_W`). Which one(s) control the leak, and how is the target set?
- How is EDITABILITY preserved when information is deliberately shared — does "delete domain 0 cleanly" still hold if
  domain 0's material has leaked into others? (Provenance tags should still bound the removal, but this needs testing.)
- How do we MEASURE the sweet spot — creativity/transfer gained vs contamination/interference introduced?
- Is the leak symmetric, or directional (some domains inform others but not vice-versa)?
**Source:** user, session 2026-07-23. Not built (explicit: capture only, continue current work).
