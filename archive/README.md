# What in this tree is HISTORY, and must not be read as current

Four directories here are frozen records. They are kept deliberately — this project's whole method is that a
record of what was believed and when is worth more than a tidy tree — but every one of them contains code and
prose that was true once and is not true now. Grepping the repository without knowing that is how the two most
expensive documentation errors here happened.

Everything below now lives under **`archive/`**, moved there 2026-08-27 so that a repository-wide grep does
not return them alongside live code. Nothing live imports, executes or reads any of it — checked before the
move; the only references were two comments, since amended.

| path | what it is | frozen since |
|---|---|---|
| `archive/garry/` | a working snapshot of the whole system at milestone T33, ~957 lines against today's ~8,450 | 2026-07 |
| `archive/legacy/` | the pre-rewrite package, a different architecture with the same vocabulary | 2026-07 |
| `archive/handoff/` | phase notes and decisions written for a handover | 2026-07-21 |
| `archive/docs/` | a file-by-file manifest written from a read of the code at the time | 2026-07-21 |
| `archive/STATE.md` | a "living project ledger" whose own header calls its protocol **binding for the assistant** and instructs it to be updated every turn. Last updated 2026-08-15 and carrying `FAB_N0=3`. A stale file that tells the reader it is authoritative is the worst kind. | 2026-08-15 |
| `archive/CL_TESTBED.md` | the continual-learning testbed description from the import | 2026-08-15 |

## The trap, concretely

`archive/garry/self_organize.py` still reads `_i("FAB_N0", 3)`. The live default has been **2048** since
`6380519`/`25aba88` (2026-08-17). A repo-wide grep for `FAB_N0` returns both, and the wrong one is in a file
that looks exactly like the right one.

That is not hypothetical: nine files in `notes/` stated `FAB_N0=3` as the current default a week after it
changed, and it was `00_INDEX`'s "five things to know before spending any GPU time" item #1. Separately,
`02_IDEAS` filed a built mechanism as NEVER IMPLEMENTED and its own correction records the cost — "it was read
during the 0.75 GB planning and used to tell the user the mechanism did not exist".

## Where to look instead

- **Current defaults:** `notes/CURRENT_DEFAULTS.md`. Generated from `_SPEC`, never hand-written, and
  `notes_check.py` (in `selftest.sh`) fails if it drifts, or if any markdown OUTSIDE `archive/`
  contradicts it — top-level files included, which is what `STATE.md` slipped through before.
- **Current behaviour:** `self_organize.py` and `longrun.sh` at HEAD. Nothing else.
- **What was true before:** everything else in `notes/`, and the four directories above. Correct as records.
  Where one has since been overtaken, it carries a dated correction rather than an edit.

## Rules

1. Do not edit anything under `archive/`. `archive/garry/GARRY.md` said this already; it applies to all of it.
   `notes_check.py` fails if `archive/` exists without this file, so the label cannot quietly go missing.
2. Do not cite them for what the system does now.
3. When a note is overtaken, append a dated correction. Do not rewrite the original — the record of a wrong
   belief is the most useful thing in the corpus, and this project has re-learned that twice.
