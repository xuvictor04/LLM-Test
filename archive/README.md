# archive/ — what in this tree is HISTORY, and must not be read as current

Everything under `archive/` is a frozen record. It is kept deliberately — this project's whole method is
that a record of what was believed, and when, is worth more than a tidy tree — but every item here holds
code or prose that was true once and is not true now. Grepping the repository without knowing that is
how the two most expensive documentation errors here happened (below). For what the system does now,
read `src/` (run by `run.py`), `docs/04_CONTRACT.md` and `docs/05_DEFAULTS.md`; the root `README.md` maps
the whole tree.

This file says what each item was, why it is kept, and where every moved path went. It was the root's
`ARCHIVE.md` until 2026-09-28 and moved here with `git mv`, so `git log --follow archive/README.md` keeps
its history. `garry/`, `legacy/`, `handoff/`, `docs/`, `STATE.md` and `CL_TESTBED.md` moved here from
the root on 2026-08-27, so that a repository-wide grep does not return them beside live code;
`agent-transcripts/` was committed here directly. Nothing live imports or executes any of it.

| path | what it was | why it is kept | frozen since |
|---|---|---|---|
| `garry/` | a working snapshot of the whole system at milestone T33: a 957-line `self_organize.py`, against the old tree's 9,859 | the known-good reference its own `GARRY.md` promised; `src/memory/api.py` cites its `self_organize.py` by line | 2026-07 |
| `legacy/` | the pre-rewrite package, a different architecture with the same vocabulary | where the vocabulary came from; its `build_continual_data.py` wrote `data/continual/`, and `docs/04_CONTRACT.md` (Q-DATA-4) cites it | 2026-07 |
| `handoff/` | the 2026-07-21 handover folder: phase notes, decisions, open questions, design directions | what a fresh session was told on 2026-07-21; the notes corpus and `.rework/ISSUES.md` cite it | 2026-07-21 |
| `docs/` | `FILES.md` (a file-by-file map written from a read of the code) and `HANDOFF.md` (the pick-up guide beside it), the root's `docs/` of 2026-07-21 — not today's `docs/` | the same handover | 2026-07-21 |
| `agent-transcripts/` | the raw transcripts of the multi-agent workflows behind `.rework/`, `src/`, `tests/` and `docs/`; its `MANIFEST.md` lists them | the only copy: the container that ran them is ephemeral | as committed |
| `STATE.md` | a "living project ledger" whose own header calls its protocol **binding for the assistant** and instructs it to be updated every turn. Last updated 2026-08-15 and carrying `FAB_N0=3`. A stale file that tells the reader it is authoritative is the worst kind. | the headline results the root `README.md` retracts (ISSUES P2-C3) came from its §7, which the retraction cites | 2026-08-15 |
| `CL_TESTBED.md` | the continual-learning testbed description from the import | what `cl_bench.py` and `run_full_unfrozen.sh` were written to test | 2026-08-15 |

## The trap, concretely

`archive/garry/self_organize.py` still reads `_i("FAB_N0", 3)`. The default has been **2048** since
`6380519`/`25aba88` (2026-08-17), in the old tree's `_SPEC`, and `src/` declares the same 2048 for its
`FAB_N0` (`src/fabric/levers.py`). A repo-wide grep for `FAB_N0` returns all three, and the wrong one is in
a file that looks exactly like the right one.

That is not hypothetical: nine files in `notes/` stated `FAB_N0=3` as the current default a week after it
changed, and it was `00_INDEX`'s "five things to know before spending any GPU time" item #1. Separately,
`02_IDEAS` filed a built mechanism as NEVER IMPLEMENTED and its own correction records the cost — "it was read
during the 0.75 GB planning and used to tell the user the mechanism did not exist".

## Where to look instead

- **Defaults of the system that runs now:** `docs/05_DEFAULTS.md`, generated from the lever registry by
  `tools/render_defaults.py`; `tests/test_assemble.py`'s A10 fails if it drifts.
- **Defaults of the old tree:** `notes/CURRENT_DEFAULTS.md`, generated from `self_organize.py`'s `_SPEC`
  by `notes_check.py` (in `selftest.sh`), which fails if that file drifts, if `README.md` or any
  `notes/*.md` states a default `_SPEC` contradicts without saying it is history, or if this file is
  missing.
- **Current behaviour:** `src/`, run by `run.py`; its surface is `docs/04_CONTRACT.md`.
- **What was true before:** everything in this directory, and the 2026-08 notes corpus in `notes/`
  (`notes/00_INDEX.md` first). Correct as records. Where one has since been overtaken, it carries a dated
  correction rather than an edit.

## Rules

1. Do not edit anything under `archive/`. `archive/garry/GARRY.md` said this already; it applies to all of it.
   The one exception is this README, the label, which is updated whenever something is archived or moves.
   `notes_check.py` fails if `archive/` exists without it, so the label cannot quietly go missing.
2. Do not cite them for what the system does now.
3. When a note is overtaken, append a dated correction. Do not rewrite the original — the record of a wrong
   belief is the most useful thing in the corpus, and this project has re-learned that twice.

## Where each moved path went

Records written before a move keep the paths of their day and are not rewritten: the notes corpus, the
dated entries of `.rework/`'s ledgers, the survey and audit JSON, `results/`, the agent transcripts and
the commit messages. This table resolves them.

| was | is | moved |
|---|---|---|
| `garry/`, `legacy/`, `handoff/`, `docs/FILES.md` and `docs/HANDOFF.md`, `STATE.md`, `CL_TESTBED.md`, at the root | the same names under `archive/` | 2026-08-27 |
| `ARCHIVE.md` | `archive/README.md` | 2026-09-28 |
