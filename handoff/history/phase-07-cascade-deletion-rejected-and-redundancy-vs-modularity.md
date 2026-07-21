# Phase 7 — cascade deletion rejected; the affiliation map; redundancy vs modularity

The user rejected an early sketch where deleting a domain cascade-deletes its experts: **"I don't like the idea of
removing everything under the domain."** Agreed — it reintroduces the large-blast-radius failure independence exists to
prevent. New semantics: domain deletion RELEASES a domain's expert affiliations (stop routing to them); an orphaned
expert is later culled by normal selection, one still serving others is untouched. Built an **affiliation map** (which
experts serve which domains, blast-radius preview). First measurement validated the objection: **every expert served
every domain (0 exclusive, 0 idle)** — cascade deletion then would have destroyed the whole population.

Same measurement caught a narration mistake: uniform routing mass across domains is NOT "even specialization" — it's the
OPPOSITE (every expert an interchangeable generalist). Near-zero deletion collateral there reflects REDUNDANCY, not
MODULARITY. Corrected explicitly.

Also: the affiliation diagnostic itself crashed a full GPU run (tensor-shape mismatch as the population grew mid-run) —
wasted run. Fixed the padding and wrapped the diagnostic in try/except: **a measurement must never destroy a training run.**
</content>
