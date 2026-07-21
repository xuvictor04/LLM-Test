# Experts are INDEPENDENT agents blended at a router (the Fabric society) — SETTLED [USER]

**Decision:** Experts are independent agents (nothing frozen; new experts cloned from the live base),
ensembled at the PREDICTION level (`Σ wᵢ·head(oᵢ)`), not by averaging hidden states. Domains are
collections of experts. Independence is what makes weight-deletion clean. Runs as `FABRIC=1 SOCIETY=1`.
**Note:** the earlier low-rank-adapter population (`EXPERTS=1`) is SUPERSEDED by the Fabric; `EXPERTS=0`
by default. Do not confuse the two "expert" mechanisms.
**Why it matters:** this is the headline result — deleting a whole expert's weights costs −0.0009.
**Source:** `STATE.md §2` Design decisions; `garry/GARRY.md`.
