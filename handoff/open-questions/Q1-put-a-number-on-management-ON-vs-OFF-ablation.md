# Q1 — Put a NUMBER on memory-management ON vs OFF — OPEN (sub-item), needs a run

**Status:** the non-stationary / phased-stream test is BUILT (`PHASED=1`). What remains is an ablation:
run the phased stream with memory management (merge/cull/reassign) ON vs OFF and measure how much it
actually buys — does memory stay bounded + useful across the shift, and does editing stay clean on both
active and faded processes?
**Who decides / does:** USER runs it on the H100 (assistant can wire the ablation flag).
**Source:** `STATE.md §4 Q1`.
