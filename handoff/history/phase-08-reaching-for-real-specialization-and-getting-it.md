# Phase 8 — deliberately reaching for real specialization, and getting it

Asked whether real specialization was achievable, Claude's first hypothesis (a load-balancing loss forcing uniformity)
was REFUTED — an A/B with it on vs decaying gave byte-identical results (its weight was negligible). The real cause was
more fundamental and Claude's own doing: the **independence loss** (added Phase 6 to make deletion safe) trains every
expert to solve the whole task alone — independence by REDUNDANCY, the opposite of independence by MODULARITY. Both
legitimate but different; Claude had conflated them.

Fix: expert routing keys became **EMA centroids in signature space** (`ROUTE_GROUNDED=1`, exactly like domains) +
**sharper routing temperature** (`ROUTE_T=0.3`). Neither alone sufficed; together they produced real, uneven
constituencies for the first time — deletion damage **concentrated** (~7× ratio most- vs least-affected, and NOT merely
tracking which process was hardest to predict) at ~+0.035 b/B vs redundancy. Both regimes now characterized as a genuine
user-facing dial, not a bug.
</content>
