# ROUTE_T sweep below 0.3, and DIV_W — for HARDER specialization — not run / not tuned

**What:** if harder specialization is wanted (fewer than the current 42–66% domain-coverage-per-expert, toward real
exclusivity), the natural next experiments are: sweep `ROUTE_T` below 0.3 (sharper routing), and tune `DIV_W` — an
explicit distinctness-reward loss term that is built but default-off and never tuned.
**Caveat:** the likely ceiling on exclusivity is the SIGNATURE ENCODER's separability, not more training — its own loss
curve had already converged. More/better DATA could plausibly help; more passes over the same data will not.
**Source:** context export §9, §11.
