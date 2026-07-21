# Q-compute — what to run next at GPU scale, and at what budget? — OPEN, needs USER decision

**Question:** the two blockers to the language goal are resolved in code — DATA (corpus expansion via
`fetch_data.sh`/`fetch_big.py`) and THROUGHPUT (batched training via `BATCH_W`) — but **nothing has actually been run at
the new scale.** This is the highest-information experiment available: the first honest read on language quality with data
that could plausibly support it.
**The catch to size deliberately:** at realistic batched throughput on one H100, a GPT-2-scale token budget (~10B tokens)
is **weeks** of continuous training, not an afternoon. Decide the scale on purpose rather than discovering it mid-run.
**Who decides / does:** USER (runs it on the H100). Assistant can prepare the exact command and scale `STREAM_LEN` to `BATCH_W`.
**Source:** `../../STATE.md §4 Q-compute`; context export §10, §12.
