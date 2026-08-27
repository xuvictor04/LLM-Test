# 2026-07-21 — Package added to the repo, docs written, ledger reconciled, handoff/ created

> CORRECTION (see 2026-07-21b): the "history unrecoverable" claim below was superseded — the prior context
> recovered the full history (now in `../history/`). Left here as a point-in-time record.

**Context:** first chat in the migrated-repo era. The user uploaded `overarching-package_12.zip` and is
moving chats because context can no longer be compressed. Repo `xuvictor04/LLM-Test` started EMPTY.

## What this chat did (three commits on branch `claude/hub-addition-1ueehb`)
1. **Added the package** — 121 files placed at the repo ROOT (so `README.md` renders on the homepage) +
   a `.gitignore`. Because the repo was empty, this branch became the repo's DEFAULT branch.
2. **Wrote `docs/FILES.md`** (file-by-file map, read from source) and **`docs/HANDOFF.md`** (current-state
   snapshot + reconciliation ledger).
3. **Reconciled `STATE.md`** and fixed two doc-vs-code bugs (README output paths; `cl_bench.py` header).
4. **Created this `handoff/` folder** — blank-chat bootstrap + atomic process/decisions/open-questions
   index + this migration log (per user request: separate folder, one idea per file, filename-as-index,
   assume the next chat is blank).

## What is TRUE now (state of play)
- A (edit/unlearn by provenance): PROVEN. C (self-assembly): works, over-segments (harmless).
  B (wrong-detection): broken, DETECT-ONLY. Generation: semi-coherent, base-model-limited.
- Frozen milestone = **T33** (`garry/GARRY.md`): end-to-end **1.967** b/B, expert-deletion **−0.0009**.
  Root is T33's DESCENDANT (adds retrieval-grounding / source-`pos`); `cl_bench.py`/`tokenizer.py` identical.
- Authoritative sources when docs disagree: code → `docs/FILES.md`; newest numbers → `garry/GARRY.md`;
  user decisions → `STATE.md §2/§5`.

## Known gap the next chat must NOT try to reconstruct
- The **T5–T32 history** (Fabric/society/experts/phased/grounding development) lived in the now-migrated
  chat + GPU logs and is NOT recoverable from the repo. `STATE.md §2` (Decisions) was kept current
  through it; `STATE.md §6/§7` were left stale (now relabeled). Do not fabricate the missing history.

## Decisions the assistant made this chat (user may reverse)
- No PR (the branch already IS the repo default; nothing to merge into).
- Layout kept flattened at repo root.
- Chose to FLAG the missing history rather than invent it.

## Still open (need USER) — see ../open-questions/
- Q0 expert-evolution type · Q1 management ON/OFF ablation (needs a run) · Q3 B direction.
