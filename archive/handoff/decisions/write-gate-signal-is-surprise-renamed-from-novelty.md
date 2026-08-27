# The write-gate signal is SURPRISE (1 − p_model(true token)); "novelty" was a misnomer — SETTLED [USER]

**Decision:** The memory write gate fires on SURPRISE, i.e. `1 − p_model(true token)`. The old name
"novelty" was wrong and was renamed (user caught the misnomer). The optional adaptive gate
(`WRITE_ADAPTIVE=1`) self-calibrates the threshold to hold a target write fraction as the scale drifts.
**Source:** `STATE.md §2` Design decisions; `memory.py`.
