# .rework/ — staging for the rm-predict-DC regeneration

PROVISIONAL. This directory holds the raw evidence the rework is being built from. It is not part of the
regenerated system; the implementation plan decides what of it survives into the final tree and in what
form. Nothing here should be read as documentation — it is the source material documentation is written
FROM.

## survey/
One JSON file per surveyed area, produced by 16 independent reader agents over the repository as it stood
at rm-predict @ aee4a52. Each file has the same shape: facts (with file:line evidence), levers (name,
effect, owner, what it couples with), bugs, junk, carry_forward (knowledge that must survive a rebuild),
open_questions.

Areas: so-config, so-fabric, so-model, so-loop, so-report (the five regions of the 9,859-line
self_organize.py), subsys (memory/tokenizer/datastream/world_model), harness (longrun.sh + shell), tests,
tools, notes-num, notes-research, archive, chat-a/b/c (this session's transcript, 8,072 entries),
chat-early (2026-07-21..08-15, from notes/_evidence/chat/, whose raw transcript no longer exists).

Totals: 1,149 facts | 558 lever records | 475 bug records | 196 junk | 305 carry-forward | 174 questions.

These are AGENT OUTPUT, not verified truth. Each carries its own evidence pointer; anything load-bearing
must be checked against the source before it is written into documentation.
