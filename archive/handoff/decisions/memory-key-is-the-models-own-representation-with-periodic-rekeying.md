# Memory key = the model's OWN (unfrozen) representation + periodic re-keying — SETTLED [USER]

**Decision:** Key memory on the model's own, drifting representation (`KEY_SRC=model`), and periodically
re-encode stored keys (`REKEY`) so they survive drift. A frozen key is a TESTING BASELINE only.
**Why:** the product path must be unfrozen; re-keyed model key (+1.19) beats a static frozen key (+1.73
on forgetting) once drift is accounted for.
**Source:** `STATE.md §2` Design decisions.
