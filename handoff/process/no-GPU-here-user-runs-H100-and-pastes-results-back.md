# No GPU in this chat environment — the user runs the H100 and pastes results back

The chat/dev environment is CPU-only and ephemeral. **Never run the real suite here and never invent
measured numbers.** The loop: assistant writes/edits code → user runs `bash run_full_unfrozen.sh` (or
`garry/`) on their own H100 → user pastes the output → assistant records numbers in `STATE.md §7`
WITH the run's config, and adds a `garry/`-style comparison. CPU smoke tests to verify a code path are
fine; measurements are not.

**Source:** user, session 2026-07-21 (GPU-runs question).
