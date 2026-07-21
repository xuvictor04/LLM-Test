# Recommended next steps (priority order)

From the context export §15. The first three are the substance; items 1–3 of the "four decisions" (`open-questions/`) gate them.

1. **Decide redundancy-vs-modularity** as the standing default, or keep both per-run — a genuine product decision, the USER's to make (`open-questions/Q-regime...`).
2. **Run corpus-expansion + batched training at real GPU scale** — the first honest read on language quality with data that could plausibly support it, and the direct test of the stated end goal. Highest-information experiment available. Size the budget deliberately (weeks, not hours) (`open-questions/Q-compute...`).
3. **Implement release-don't-kill domain deletion** — small, well-specified, completes the architecture as the user described it (`designed-but-not-built/release-dont-kill...`).
4. **Fix `STATE.md`'s reliability** — DONE this repo turn (rebuilt from the export + a self-verify protocol step added). Keep verifying edits land.
5. Lower priority, no order: `retire_stale` wiring, memory-pressure → grow-experts/retrain/domain-split (replaces the rejected quota), `ROUTE_T`/`DIV_W` specialization sweep, a `fetch_big.py` live-network debugging pass once the user has run it. (B is now Verification — built.)

**Source:** context export §15; `../STATE.md §4`.
</content>
