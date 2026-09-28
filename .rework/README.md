# .rework/ — the rework's ledgers, and the evidence they were built from

It began as the staging area for the rm-predict-DC regeneration, when nothing here was meant to be read
as documentation. Part of it is live now: the tests read `census.json`, `ISSUES.md` and `oracle/`, and
`src/`, `docs/` and `tests/` cite its ledgers. The rest is the record the rework was built from. The tests name this folder by its path (`tests/test_census.py`, `tests/test_contract.py`,
`tests/test_derive.py`), so it keeps its name.

| path | status | what it is |
|---|---|---|
| `DECISIONS.md` | live, append-only | the owner's rulings, dated, D1 onward. `docs/proposals/05_DECISIONS.md` cites it by line, so a new ruling goes at the end |
| `CENSUS.md` + `census.json` | live | every old knob and where it went; a new lever needs a row. `tests/test_census.py` reads `census.json`, and `tests/test_contract.py`'s K13 counts its rows |
| `ISSUES.md` | live | every defect the survey found, in four parts, each id qualified by its part (`P1-C11`, `P2-C3`); `tests/test_census.py`'s N7 checks every citation of an id in the tree against it |
| `oracle/` + `capture_oracle.py` | test fixture | 575 known-answer cases lifted from the old tree's `self_organize.py` by `capture_oracle.py` at P0 and replayed by `tests/test_derive.py`. Run from the repository root, `capture_oracle.py` reads `archive/old-tree/self_organize.py` and reproduces them |
| `PLAN.md` | record; its lever rule binds | the phase plan P1–P9, and the lever rule (§4): L1 and L2, which `tests/test_ownership.py` enforces, and L3, whose `tests/test_lever_isolation.py` is not written yet. The staged test plan in `docs/proposals/05_DECISIONS.md` §8 orders the work now |
| `audits/` | record | the multi-agent audits of P4's entry-point bodies: the harness, its inputs and its outputs (its own `README.md`). Cited from `src/`, `tests/` and `docs/04_CONTRACT.md` |
| `survey/` | record | one JSON file per surveyed area, from 16 reader agents over rm-predict @ aee4a52: facts with file:line evidence, levers, bugs, junk, carry-forward, open questions. Agent output, not verified truth; `ISSUES.md` and `PLAN.md` were built from it |
| `questions/` | record, since ruled | the raw output of the p3-questions workflow on the 38 contract questions (its own `README.md`), ruled since in `docs/04_CONTRACT.md` and Proposal 05. It stays here and not in `archive/` because N7 reads its citations of `ISSUES.md` ids and does not read `archive/` |
| `reviews.json` | record | three adversarial reviews: two of the P1 spine, one of the P2 census |
| `COMMIT_RECORD.md` | record | the commit history of 2026-07-21 .. 2026-08-28, rebuilt from `notes/_evidence/commit_log.txt` (before 2026-08-15, where git history begins) and from git |
| `COMPACTION_SUMMARIES.md` | record | the four compaction summaries; D6 makes them the record of the lost 2026-08-15 .. 08-17 window |

The survey areas: so-config, so-fabric, so-model, so-loop, so-report (the five regions of the
9,859-line `self_organize.py`), subsys (memory/tokenizer/datastream/world_model), harness (`longrun.sh`
and the shell scripts), tests, tools, notes-num, notes-research, archive, chat-a/b/c (the session's
transcript, 8,072 entries) and chat-early (2026-07-21 .. 08-15, from `notes/_evidence/chat/`, whose raw
transcript no longer exists). Totals: 1,149 facts, 558 lever records, 475 bug records, 196 junk,
305 carry-forward, 174 questions. Each carries its own evidence pointer, and anything load-bearing is
checked against the source before it is written into documentation. The files the survey read at the
root are in `archive/old-tree/` since 2026-09-28.

Moved out on 2026-09-28: `QUESTIONS.md`, the owner questions Q1–Q7, ruled on 2026-08-28 as `DECISIONS.md`
D1–D7, is `archive/rework/QUESTIONS.md`. Its closing environment block is still open, as
`docs/02_OPERATIONS.md` §5.
