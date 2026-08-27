# What in this tree is HISTORY, and must not be read as current

Four directories here are frozen records. They are kept deliberately — this project's whole method is that a
record of what was believed and when is worth more than a tidy tree — but every one of them contains code and
prose that was true once and is not true now. Grepping the repository without knowing that is how the two most
expensive documentation errors here happened.

| directory | what it is | frozen since |
|---|---|---|
| `garry/` | a working snapshot of the whole system at milestone T33, ~957 lines against today's ~8,450 | 2026-07 |
| `legacy/` | the pre-rewrite package, a different architecture with the same vocabulary | 2026-07 |
| `handoff/` | phase notes and decisions written for a handover | 2026-07-21 |
| `docs/` | a file-by-file manifest written from a read of the code at the time | 2026-07-21 |

## The trap, concretely

`garry/self_organize.py` still reads `_i("FAB_N0", 3)`. The live default has been **2048** since
`6380519`/`25aba88` (2026-08-17). A repo-wide grep for `FAB_N0` returns both, and the wrong one is in a file
that looks exactly like the right one.

That is not hypothetical: nine files in `notes/` stated `FAB_N0=3` as the current default a week after it
changed, and it was `00_INDEX`'s "five things to know before spending any GPU time" item #1. Separately,
`02_IDEAS` filed a built mechanism as NEVER IMPLEMENTED and its own correction records the cost — "it was read
during the 0.75 GB planning and used to tell the user the mechanism did not exist".

## Where to look instead

- **Current defaults:** `notes/CURRENT_DEFAULTS.md`. Generated from `_SPEC`, never hand-written, and
  `notes_check.py` (in `selftest.sh`) fails if it drifts or if any note contradicts it.
- **Current behaviour:** `self_organize.py` and `longrun.sh` at HEAD. Nothing else.
- **What was true before:** everything else in `notes/`, and the four directories above. Correct as records.
  Where one has since been overtaken, it carries a dated correction rather than an edit.

## Rules

1. Do not edit the frozen directories. `garry/GARRY.md` says this already; it applies to all four.
2. Do not cite them for what the system does now.
3. When a note is overtaken, append a dated correction. Do not rewrite the original — the record of a wrong
   belief is the most useful thing in the corpus, and this project has re-learned that twice.
