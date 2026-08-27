# Domain deletion RELEASES a domain's experts — it does NOT cascade-kill them — SETTLED [USER rejected cascade]

**Decision:** deleting a domain removes its memory entries and RELEASES its expert affiliations (stops routing traffic to
them); it never directly deletes an expert's parameters. An expert left with zero constituency is later removed by the
population's normal selection pressure; an expert still serving other domains is untouched.
**Why:** cascade-deleting a domain's experts reintroduces exactly the large-blast-radius forgetting the independence design
exists to prevent. The affiliation map confirmed 0 exclusive experts (every expert serves most domains) in every run.
**Status:** semantics agreed; the actual `delete_domain()` wiring is DESIGNED-BUT-NOT-BUILT (see `../designed-but-not-built/`).
**Source:** context export Phase 7, §11.
