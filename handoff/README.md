# handoff/ — START HERE (assume you have ZERO prior context)

You are (most likely) a fresh chat with no memory of earlier sessions. This project **migrates chats
when context can no longer be compressed**, and *this folder is how context is exchanged between chats.*
Read it and you can continue without the prior conversation.

## Read in this order
1. **This file.**
2. `../README.md` — what the project is (the pitch).
3. `migrations/` — newest dated file = the latest state of play (what the last chat did).
4. `../docs/HANDOFF.md` — current-state snapshot + reconciliation ledger.
5. `../docs/FILES.md` — what every file in the repo is.
6. `../STATE.md` — the LIVE ledger: §2 decisions you must honor, §4 open questions, §5 config, §6 changelog.
7. `../garry/GARRY.md` — the frozen **T33** milestone; the authoritative *newest* measured numbers.
8. `process/`, `decisions/`, `open-questions/` here — atomic, one idea per file.

## How this folder is organized
**One idea per file. The filename IS the summary — run `ls` on each subfolder and you have the map.**
- `process/`        — standing rules for HOW we work. Honor these every turn.
- `decisions/`      — settled calls `[USER]`. Do NOT re-litigate; do NOT override with a default.
- `open-questions/` — unresolved; each needs a USER decision. **ASK, don't default.**
- `migrations/`     — one dated file per chat hand-off; newest = current.

## Relationship to STATE.md (how to avoid drift)
`STATE.md` is the single **LIVE ledger and source of truth**. The files here are the **blank-chat
bootstrap + atomic index** — short, pointing back to the STATE.md section that holds the full detail.
When something changes: update `STATE.md` first (its protocol), then reflect the headline here.

## How to hand off when THIS chat is retired
Add a new dated file to `migrations/` (e.g. `2026-08-01-<what-happened>.md`) covering: what changed,
what is now true, what is still open, and anything the next chat must NOT repeat. Descriptive filename.
Assume the reader knows nothing.

## The project in one paragraph
An autonomous continual-learning system driven by **one unlabeled stream**: it self-assembles domains,
grows a society of independent experts (the Fabric), writes surprise-gated memory tagged by provenance,
detects wrong info (B, detect-only), and edits/unlearns by provenance (A). Headline, defensible result:
**deleting a whole expert's weights is essentially free** (−0.0009 collateral) — independence makes
removal clean. Runs on a CUDA GPU (H100). **This chat environment has no GPU** — the user runs the real
suite on their own H100 and pastes results back.
